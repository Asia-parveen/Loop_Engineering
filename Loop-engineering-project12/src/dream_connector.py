"""Dream Connector — Git/GitHub Integration for Dream Loop.

The connector creates a Git branch with the proposal and optionally opens
a pull request (via GitHub CLI if available). No auto-merge; human review required.

Key principle: Maker output must pass checker before ANY connector action.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess
import shutil
import os

from dream_checker import CheckResult
from dream_maker import MakerResult, ProposalArtifact


@dataclass(frozen=True)
class DreamConnectorConfig:
    """Configuration for the dream connector."""
    repo_root: Path
    branch_prefix: str = "claude/"
    create_pr: bool = False  # Requires gh CLI
    require_human_approval: bool = True  # Maker-checker gate


@dataclass(frozen=True)
class ConnectorResult:
    """Result of the connector phase."""
    shipped: bool
    branch_name: Optional[str]
    pr_url: Optional[str]
    message: str
    needs_human: bool
    artifacts_shipped: int


def run_git(repo_root: Path, *args: str, capture=True) -> subprocess.CompletedProcess:
    """Run a git command in the repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=capture,
        text=True,
    )


def get_current_branch(repo_root: Path) -> str:
    """Get the current branch name."""
    result = run_git(repo_root, "branch", "--show-current")
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_default_branch(repo_root: Path) -> str:
    """Detect the default branch (main/master) from origin/HEAD."""
    result = run_git(repo_root, "symbolic-ref", "refs/remotes/origin/HEAD")
    if result.returncode == 0:
        return result.stdout.strip().split("/")[-1]
    result = run_git(repo_root, "branch", "--list", "main")
    if result.returncode == 0 and result.stdout.strip():
        return "main"
    return "master"


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    """Check if a branch exists locally or remotely."""
    result = run_git(repo_root, "rev-parse", "--verify", branch_name)
    if result.returncode == 0:
        return True
    # Check remote
    result = run_git(repo_root, "ls-remote", "--heads", "origin", branch_name)
    return result.returncode == 0 and branch_name in result.stdout


def create_branch(repo_root: Path, branch_name: str, base_branch: Optional[str] = None) -> bool:
    """Create a new branch from base_branch."""
    if base_branch is None:
        base_branch = get_default_branch(repo_root)
    # Fetch latest
    run_git(repo_root, "fetch", "origin", base_branch)
    # Create branch
    result = run_git(repo_root, "checkout", "-b", branch_name, f"origin/{base_branch}")
    if result.returncode != 0:
        # Fallback to local base
        result = run_git(repo_root, "checkout", "-b", branch_name, base_branch)
    return result.returncode == 0


def commit_proposal(repo_root: Path, artifact: ProposalArtifact) -> bool:
    """Commit the proposal artifact to the repo."""
    # Write the diff file to a temporary location in the repo
    proposal_dir = repo_root / ".dream_proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    
    diff_path = proposal_dir / f"{artifact.branch_name.replace('/', '_')}.diff"
    diff_path.write_text(artifact.diff, encoding="utf-8")
    
    pr_path = proposal_dir / f"{artifact.branch_name.replace('/', '_')}_pr.md"
    pr_path.write_text(artifact.pr_body, encoding="utf-8")
    
    # Stage and commit
    run_git(repo_root, "add", str(diff_path.relative_to(repo_root)))
    run_git(repo_root, "add", str(pr_path.relative_to(repo_root)))
    
    commit_msg = f"{artifact.pr_title}\n\n{artifact.pr_body[:500]}"
    result = run_git(repo_root, "commit", "-m", commit_msg)
    return result.returncode == 0


def push_branch(repo_root: Path, branch_name: str) -> bool:
    """Push branch to origin."""
    result = run_git(repo_root, "push", "-u", "origin", branch_name)
    return result.returncode == 0


def create_pull_request(repo_root: Path, config: DreamConnectorConfig, branch_name: str, artifact: ProposalArtifact) -> Optional[str]:
    """Create a pull request using GitHub CLI (gh). Returns PR URL or None."""
    if shutil.which("gh") is None:
        return None
    
    base_branch = get_default_branch(repo_root)
    
    result = subprocess.run(
        ["gh", "pr", "create", "--title", artifact.pr_title, "--body", artifact.pr_body, "--head", branch_name, "--base", base_branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def run_connector(
    config: DreamConnectorConfig,
    maker_result: MakerResult,
    check_result: CheckResult,
) -> ConnectorResult:
    """Execute the connector phase: ship validated proposals as PRs.

    PRECONDITION: check_result.passed must be True.
    """
    if not check_result.passed:
        return ConnectorResult(
            shipped=False,
            branch_name=None,
            pr_url=None,
            message="Checker failed - connector aborted",
            needs_human=True,
            artifacts_shipped=0,
        )
    
    if not maker_result.artifacts:
        return ConnectorResult(
            shipped=False,
            branch_name=None,
            pr_url=None,
            message="No artifacts to ship",
            needs_human=False,
            artifacts_shipped=0,
        )
    
    shipped_count = 0
    last_branch = None
    last_pr_url = None
    messages = []
    
    for artifact in maker_result.artifacts:
        # Check if branch already exists (idempotency)
        if branch_exists(config.repo_root, artifact.branch_name):
            messages.append(f"Branch {artifact.branch_name} already exists - skipping (idempotent)")
            continue
        
        # Create branch
        if not create_branch(config.repo_root, artifact.branch_name):
            return ConnectorResult(
                shipped=False,
                branch_name=None,
                pr_url=None,
                message=f"Failed to create branch {artifact.branch_name}",
                needs_human=True,
                artifacts_shipped=shipped_count,
            )
        
        # Commit proposal
        if not commit_proposal(config.repo_root, artifact):
            return ConnectorResult(
                shipped=False,
                branch_name=artifact.branch_name,
                pr_url=None,
                message=f"Failed to commit proposal for {artifact.branch_name}",
                needs_human=True,
                artifacts_shipped=shipped_count,
            )
        
        # Push branch
        if not push_branch(config.repo_root, artifact.branch_name):
            return ConnectorResult(
                shipped=False,
                branch_name=artifact.branch_name,
                pr_url=None,
                message=f"Failed to push branch {artifact.branch_name}",
                needs_human=True,
                artifacts_shipped=shipped_count,
            )
        
        # Optionally create PR
        pr_url = None
        if config.create_pr:
            pr_url = create_pull_request(config, config, artifact.branch_name, artifact)
        
        last_branch = artifact.branch_name
        last_pr_url = pr_url
        shipped_count += 1
        
        msg = f"Created branch {artifact.branch_name}"
        if pr_url:
            msg += f" and PR: {pr_url}"
        else:
            msg += " (PR creation skipped or failed - needs human)"
        messages.append(msg)
    
    if shipped_count == 0:
        return ConnectorResult(
            shipped=False,
            branch_name=None,
            pr_url=None,
            message="; ".join(messages),
            needs_human=False,
            artifacts_shipped=0,
        )
    
    needs_human = last_pr_url is None or config.require_human_approval
    
    return ConnectorResult(
        shipped=True,
        branch_name=last_branch,
        pr_url=last_pr_url,
        message="; ".join(messages),
        needs_human=needs_human,
        artifacts_shipped=shipped_count,
    )


if __name__ == "__main__":
    print("Dream Connector module - not meant to run directly")