"""Dream Checker — Validates Improvement Proposals.

The checker validates maker output before any connector action (PR creation).
Ensures proposals have evidence, are minimal, and follow safety rules.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re

from dream_maker import MakerResult, ProposalArtifact


@dataclass(frozen=True)
class CheckerConfig:
    """Configuration for the dream checker."""
    require_evidence: bool = True
    max_diff_lines: int = 50  # Proposals must be small
    forbid_direct_modification: bool = True


@dataclass(frozen=True)
class CheckResult:
    """Result of the checker phase."""
    passed: bool
    checks: List[str]
    failures: List[str]
    warnings: List[str]
    artifacts_validated: int


def validate_evidence(artifact: ProposalArtifact) -> List[str]:
    """Validate that proposal has proper evidence citation."""
    failures = []
    
    # Check for run dates in evidence
    if not re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', artifact.pr_body):
        failures.append("Evidence missing specific run dates (ISO format)")
    
    # Check for frequency mention
    if not re.search(r'\d+ time', artifact.pr_body, re.IGNORECASE):
        failures.append("Evidence missing failure frequency count")
    
    # Check for status/summary in evidence
    if "STATUS:" not in artifact.pr_body and "status" not in artifact.pr_body.lower():
        failures.append("Evidence missing failure status reference")
    
    return failures


def validate_minimal_change(artifact: ProposalArtifact, config: CheckerConfig) -> List[str]:
    """Validate that the proposed change is minimal."""
    failures = []
    
    # Count diff lines (excluding headers)
    diff_lines = [l for l in artifact.diff.splitlines() if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    if len(diff_lines) > config.max_diff_lines:
        failures.append(f"Proposed change too large: {len(diff_lines)} lines (max {config.max_diff_lines})")
    
    return failures


def validate_no_direct_modification(artifact: ProposalArtifact) -> List[str]:
    """Validate that the proposal doesn't indicate direct modification."""
    failures = []
    
    # The artifact itself should be a PR proposal, not a direct change
    # This is enforced by the architecture - maker only produces artifacts
    # But we can check the PR body doesn't claim direct modification
    if "directly modif" in artifact.pr_body.lower() or "commit directly" in artifact.pr_body.lower():
        failures.append("Proposal appears to suggest direct modification (forbidden)")
    
    return failures


def validate_branch_naming(artifact: ProposalArtifact) -> List[str]:
    """Validate branch name follows claude/ convention."""
    failures = []
    
    if not artifact.branch_name.startswith("claude/"):
        failures.append(f"Branch name must start with 'claude/': {artifact.branch_name}")
    
    if not re.match(r'claude/(fix|delete)-[a-f0-9]{12}$', artifact.branch_name):
        failures.append(f"Branch name format invalid: {artifact.branch_name} (expected claude/fix-<hash> or claude/delete-<hash>)")
    
    return failures


def run_checks(maker_result: MakerResult, config: CheckerConfig) -> CheckResult:
    """Execute the checker phase: validate all proposal artifacts."""
    all_checks = []
    all_failures = []
    all_warnings = []
    
    for artifact in maker_result.artifacts:
        # Validate evidence
        if config.require_evidence:
            evidence_failures = validate_evidence(artifact)
            all_failures.extend(evidence_failures)
            if not evidence_failures:
                all_checks.append(f"Evidence valid for {artifact.target_file}")
        
        # Validate minimal change
        minimal_failures = validate_minimal_change(artifact, config)
        all_failures.extend(minimal_failures)
        if not minimal_failures:
            all_checks.append(f"Minimal change valid for {artifact.target_file}")
        
        # Validate no direct modification
        direct_failures = validate_no_direct_modification(artifact)
        all_failures.extend(direct_failures)
        if not direct_failures:
            all_checks.append(f"No direct modification for {artifact.target_file}")
        
        # Validate branch naming
        branch_failures = validate_branch_naming(artifact)
        all_failures.extend(branch_failures)
        if not branch_failures:
            all_checks.append(f"Branch naming valid for {artifact.target_file}")
    
    passed = len(all_failures) == 0
    
    return CheckResult(
        passed=passed,
        checks=all_checks,
        failures=all_failures,
        warnings=all_warnings,
        artifacts_validated=len(maker_result.artifacts),
    )


if __name__ == "__main__":
    print("Dream Checker module - not meant to run directly")