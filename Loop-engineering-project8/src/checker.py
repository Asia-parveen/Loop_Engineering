"""Checker — Validates Changes for Loop Engineering Practice Project 8.

The checker validates the maker's output before any shipping action.
It ensures the changelog draft is well-formed, accurate, and safe.
No destructive validation; only read-only checks.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re
import hashlib

from .maker import MakerResult
from .skill import Commit


@dataclass(frozen=True)
class CheckResult:
    """Result of the checker validation."""
    passed: bool
    checks: List[str]  # List of check descriptions
    failures: List[str]  # List of failure descriptions
    warnings: List[str]  # List of warnings
    changelog_hash: str  # SHA256 of changelog content for deduplication


@dataclass(frozen=True)
class CheckerConfig:
    """Configuration for the checker."""
    require_non_empty: bool = True
    require_valid_markdown: bool = True
    require_date_headers: bool = True
    require_commit_references: bool = True
    max_changelog_size_kb: int = 100  # Max 100KB changelog


def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content (first 16 chars)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def check_file_exists(path: Path) -> tuple[bool, str]:
    """Check that the changelog file exists."""
    if path.exists() and path.is_file():
        return True, "Changelog file exists"
    return False, f"Changelog file not found: {path}"


def check_non_empty(path: Path) -> tuple[bool, str]:
    """Check that the changelog is not empty."""
    content = path.read_text(encoding="utf-8")
    if content.strip():
        return True, "Changelog is non-empty"
    return False, "Changelog is empty"


def check_valid_markdown(path: Path) -> tuple[bool, str]:
    """Basic markdown structure validation."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    if not lines:
        return False, "No content"

    # Check for header
    if not lines[0].startswith("# "):
        return False, "Missing top-level header (# Changelog Draft)"

    # Check for date headers (## YYYY-MM-DD)
    date_header_pattern = re.compile(r"^## \d{4}-\d{2}-\d{2}$")
    date_headers = [l for l in lines if date_header_pattern.match(l)]
    if not date_headers and "No new commits" not in content:
        return False, "No date headers found"

    return True, f"Valid markdown structure ({len(date_headers)} date sections)"


def check_date_headers(path: Path) -> tuple[bool, str]:
    """Validate date headers are in correct format and descending order."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    date_header_pattern = re.compile(r"^## (\d{4}-\d{2}-\d{2})$")
    dates = []
    for line in lines:
        match = date_header_pattern.match(line)
        if match:
            dates.append(match.group(1))

    if not dates:
        if "No new commits" in content:
            return True, "No new commits (valid empty state)"
        return False, "No date headers found"

    # Check descending order (newest first)
    for i in range(len(dates) - 1):
        if dates[i] < dates[i + 1]:
            return False, f"Date headers not in descending order: {dates[i]} before {dates[i+1]}"

    return True, f"Date headers valid and ordered ({len(dates)} sections)"


def check_commit_references(path: Path, expected_commits: List[Commit]) -> tuple[bool, str]:
    """Verify that all expected commits are referenced in the changelog."""
    content = path.read_text(encoding="utf-8")

    if "No new commits" in content:
        if expected_commits:
            return False, f"Expected {len(expected_commits)} commits but changelog says none"
        return True, "Correctly reports no new commits"

    missing = []
    for commit in expected_commits:
        if commit.hash not in content:
            missing.append(commit.hash)

    if missing:
        return False, f"Missing commit references: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}"

    return True, f"All {len(expected_commits)} commits referenced"


def check_size_limit(path: Path, max_kb: int) -> tuple[bool, str]:
    """Check changelog size is within limit."""
    size_kb = path.stat().st_size / 1024
    if size_kb <= max_kb:
        return True, f"Changelog size OK ({size_kb:.1f} KB <= {max_kb} KB)"
    return False, f"Changelog too large: {size_kb:.1f} KB > {max_kb} KB"


def check_no_destructive_content(path: Path) -> tuple[bool, str]:
    """Ensure changelog doesn't contain dangerous patterns."""
    content = path.read_text(encoding="utf-8")
    dangerous = [
        "rm -rf",
        "DELETE FROM",
        "DROP TABLE",
        "sudo ",
        "chmod 777",
        "git push --force",
        "git reset --hard",
    ]
    found = [d for d in dangerous if d.lower() in content.lower()]
    if found:
        return False, f"Dangerous content detected: {', '.join(found)}"
    return True, "No destructive content detected"


def run_checks(maker_result: MakerResult, config: CheckerConfig) -> CheckResult:
    """Run all validation checks on the maker's output."""
    changelog_path = maker_result.changelog_path
    skill_result = maker_result.skill_result
    commits = skill_result.commits

    checks = []
    failures = []
    warnings = []

    # Define all checks to run
    check_functions = [
        ("File exists", check_file_exists),
        ("Non-empty", check_non_empty) if config.require_non_empty else None,
        ("Valid markdown", check_valid_markdown) if config.require_valid_markdown else None,
        ("Date headers", check_date_headers) if config.require_date_headers else None,
        ("Commit references", lambda p: check_commit_references(p, commits)) if config.require_commit_references else None,
        ("Size limit", lambda p: check_size_limit(p, config.max_changelog_size_kb)),
        ("No destructive content", check_no_destructive_content),
    ]

    for name, check_fn in filter(None, check_functions):
        try:
            passed, msg = check_fn(changelog_path)
            checks.append(f"{name}: {msg}")
            if not passed:
                failures.append(f"{name}: {msg}")
        except Exception as e:
            failures.append(f"{name}: Check failed with exception: {e}")

    passed = len(failures) == 0
    changelog_hash = compute_hash(changelog_path.read_text(encoding="utf-8"))

    return CheckResult(
        passed=passed,
        checks=checks,
        failures=failures,
        warnings=warnings,
        changelog_hash=changelog_hash,
    )


if __name__ == "__main__":
    print("Checker module - not meant to run directly")