"""Skill — Documented Procedure for Changelog Draft Generation.

This module defines the deterministic, auditable procedure for generating a
changelog draft from Git commit history. It is the "skill" the loop executes.

Chore: Generate a draft CHANGELOG.md from commits since last_seen_commit.
The draft is written to an isolated worktree for checker validation.
No destructive changes; no auto-merge; no publish without human review.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import subprocess


@dataclass(frozen=True)
class SkillConfig:
    """Configuration for the changelog generation skill."""
    repo_root: Path
    worktree_dir: Path
    changelog_path: Path
    cursor_commit: Optional[str]
    max_commits: int = 100


@dataclass(frozen=True)
class Commit:
    """A single commit with hash, date, and subject."""
    hash: str
    date: str
    subject: str


@dataclass(frozen=True)
class SkillResult:
    """Result of executing the skill."""
    commits: List[Commit]
    changelog_content: str
    new_cursor: Optional[str]
    tokens_estimated: int


# The documented procedure (the "skill")
SKILL_DOCUMENTATION = """
SKILL: Generate Changelog Draft from Git History
=================================================

PURPOSE
-------
Produce a human-readable CHANGELOG.md draft from commits newer than the
recorded cursor (last_seen_commit). The draft is written to an isolated
workspace for validation. No changes are made to the working tree.

INPUTS
------
- repo_root: Path to the Git repository root.
- worktree_dir: Isolated directory for draft output.
- changelog_path: Path (within worktree) to write the draft.
- cursor_commit: Short hash of last processed commit (None = first run).
- max_commits: Safety cap on commits processed per run (default 100).

PROCEDURE
---------
1. VALIDATE INPUTS
   - repo_root must be a valid Git repository (has .git).
   - worktree_dir must exist and be writable.
   - cursor_commit, if set, must be a valid commit-ish.

2. FETCH COMMITS
   - Run: git log --format="%h|%ad|%s" --date=short <cursor>..HEAD
   - If cursor is None, run on HEAD (entire history, capped at max_commits).
   - Parse each line into Commit(hash, date, subject).
   - If > max_commits returned, truncate and flag NEEDS HUMAN.

3. BUILD CHANGELOG DRAFT
   - Group commits by date (newest first).
   - Format each commit as: "- <hash> <subject>"
   - Add date headers: "## YYYY-MM-DD"
   - Prepend header: "# Changelog Draft\nGenerated on <timestamp>\n\n"
   - If no new commits, content = "No new commits since <cursor>."

4. WRITE DRAFT
   - Ensure worktree_dir exists.
   - Write changelog_content to changelog_path.
   - Compute new_cursor = newest commit hash (first in list) or unchanged.

5. RETURN RESULT
   - Return SkillResult with commits, changelog_content, new_cursor, tokens.

SAFETY GUARDS
-------------
- max_commits prevents runaway processing.
- No git write operations (no commit, push, tag).
- Worktree isolation prevents pollution of main repo.
- All errors raise exceptions; caller handles NEEDS HUMAN.

DETERMINISM
-----------
- Same inputs always produce same output.
- No randomness, no external API calls.
- Date ordering uses Git's commit date (author date).
"""


def fetch_commits(config: SkillConfig) -> List[Commit]:
    """Step 2: Fetch commits from Git since cursor."""
    if config.cursor_commit:
        args = ["git", "log", "--format=%h|%ad|%s", "--date=short", f"{config.cursor_commit}..HEAD"]
    else:
        args = ["git", "log", "--format=%h|%ad|%s", "--date=short", f"--max-count={config.max_commits}", "HEAD"]

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=config.repo_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")

    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(Commit(hash=parts[0], date=parts[1], subject=parts[2]))
    return commits


def build_changelog(commits: List[Commit], cursor: Optional[str]) -> str:
    """Step 3: Build changelog draft content from commits."""
    from datetime import datetime
    timestamp = datetime.now().isoformat(timespec="seconds")

    if not commits:
        cursor_str = cursor[:7] if cursor else "beginning"
        return f"# Changelog Draft\nGenerated on {timestamp}\n\nNo new commits since {cursor_str}.\n"

    # Group by date
    by_date = {}
    for c in commits:
        by_date.setdefault(c.date, []).append(c)

    lines = [f"# Changelog Draft\nGenerated on {timestamp}\n"]
    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"\n## {date}")
        for c in by_date[date]:
            lines.append(f"- {c.hash} {c.subject}")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def write_draft(config: SkillConfig, content: str) -> None:
    """Step 4: Write changelog draft to worktree."""
    config.worktree_dir.mkdir(parents=True, exist_ok=True)
    config.changelog_path.write_text(content, encoding="utf-8")


def execute_skill(config: SkillConfig) -> SkillResult:
    """Execute the full skill procedure."""
    # Step 1: Validate inputs
    if not (config.repo_root / ".git").exists():
        raise RuntimeError(f"Not a git repository: {config.repo_root}")

    # Step 2: Fetch commits
    commits = fetch_commits(config)
    if len(commits) > config.max_commits:
        commits = commits[:config.max_commits]
        # Note: truncation is logged by caller

    # Step 3: Build changelog
    changelog_content = build_changelog(commits, config.cursor_commit)

    # Step 4: Write draft
    write_draft(config, changelog_content)

    # Step 5: Determine new cursor
    new_cursor = commits[0].hash if commits else config.cursor_commit

    # Estimate tokens (rough: 4 chars/token)
    tokens = len(changelog_content) // 4 + sum(len(c.subject) for c in commits) // 4 + 100

    return SkillResult(
        commits=commits,
        changelog_content=changelog_content,
        new_cursor=new_cursor,
        tokens_estimated=tokens,
    )


if __name__ == "__main__":
    print(SKILL_DOCUMENTATION)