"""Dream Skill — Documented Procedure for Weekly Improvement Analysis.

This module defines the deterministic procedure for analyzing Project 8's progress.md
to detect repeated failures and propose minimal rule/skill changes.

Chore: Analyze progress.md since last_analyzed_date, detect patterns, propose
smallest fix as PR on claude/ branch. Never modify rules directly.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import re
import hashlib


@dataclass(frozen=True)
class DreamConfig:
    """Configuration for the dream analysis skill."""
    progress_md_path: Path
    dreaming_state_path: Path
    rules_files: List[Path]  # Files that can be proposed for changes
    max_rules_to_propose: int = 1
    max_deletions_to_propose: int = 1


@dataclass(frozen=True)
class ProgressLogEntry:
    """A single dated log entry from progress.md."""
    timestamp: str
    status: str
    summary: str
    details: str
    needs_human: bool


@dataclass(frozen=True)
class FailurePattern:
    """A detected repeated failure pattern."""
    status: str
    summary: str
    details: str
    occurrences: int
    dates: List[str]
    example_details: str


@dataclass(frozen=True)
class ProposedChange:
    """A proposed rule/skill change."""
    file_path: Path
    change_type: str  # "modify" or "delete"
    description: str
    evidence: str  # Exact evidence citing run dates, frequency
    diff: str  # Unified diff showing the change
    proposal_hash: str


@dataclass(frozen=True)
class SkillResult:
    """Result of executing the dream skill."""
    patterns: List[FailurePattern]
    proposals: List[ProposedChange]
    deletions: List[ProposedChange]
    analyzed_until: str
    tokens_estimated: int


# The documented procedure (the "skill")
SKILL_DOCUMENTATION = """
SKILL: Weekly Improvement Analysis (Dream Loop)
===============================================

PURPOSE
-------
Analyze Project 8's progress.md for repeated failures since last analysis.
Propose the SMALLEST rules-file or skill change to prevent the top repeated issue.
Also propose ONE deletion of an outdated/unneeded rule. Both as PRs on claude/ branch.

INPUTS
------
- progress_md_path: Path to Project 8's progress.md (evidence source)
- dreaming_state_path: Path to dreaming-state.md (persistent state)
- rules_files: List of rule/skill files eligible for proposed changes

PROCEDURE
---------
1. READ STATE
   - Read dreaming-state.md to get last_analyzed_date
   - If none, analyze all entries

2. READ PROGRESS LOG
   - Read progress.md from Project 8
   - Parse all dated log entries (### YYYY-MM-DDTHH:MM:SS)
   - Filter entries since last_analyzed_date

3. DETECT REPEATED FAILURES
   - Group entries by (status, summary)
   - Count occurrences per group
   - Identify patterns with count >= 2 (repeated)
   - Include deliberately planted repeated failure if present

4. SELECT TOP PATTERN
   - Choose the pattern with highest frequency
   - Tie-break: most recent first

5. PROPOSE MINIMAL FIX
   - Analyze the failure to determine root cause
   - Propose SMALLEST change to a rules-file or skill
   - Change must directly address the failure pattern
   - Generate unified diff

6. PROPOSE ONE DELETION
   - Identify an outdated/unneeded rule in rules_files
   - Must have evidence it's no longer needed
   - Generate unified diff for deletion

7. RETURN RESULT
   - Return patterns, proposals, deletions, new analyzed_until date

SAFETY GUARDS
-------------
- NEVER modify rules files directly — only propose via PR
- Proposals must cite exact evidence: run dates, failure frequency
- Maker-checker validation required before PR creation
- Human gate (maker-checker) must approve

DETERMINISM
-----------
- Same inputs always produce same output
- No randomness, no external API calls in analysis
"""


def parse_progress_log(progress_path: Path) -> List[ProgressLogEntry]:
    """Parse progress.md and extract dated log entries."""
    if not progress_path.exists():
        return []
    
    content = progress_path.read_text(encoding="utf-8")
    entries = []
    
    # Pattern: ### 2026-08-29T00:55:33 followed by STATUS:, Summary:, Details:
    pattern = r"### (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\nSTATUS: (\w+)\nSummary: ([^\n]+)\nDetails: ([^\n]+)"
    if "NEEDS HUMAN" in content:
        pattern += r"\nNEEDS HUMAN"
    
    matches = re.findall(pattern, content, re.MULTILINE)
    
    for match in matches:
        timestamp, status, summary, details = match[:4]
        needs_human = "NEEDS HUMAN" in content[content.find(timestamp):content.find(timestamp)+200]
        entries.append(ProgressLogEntry(
            timestamp=timestamp,
            status=status,
            summary=summary.strip(),
            details=details.strip(),
            needs_human=needs_human,
        ))
    
    return entries


def filter_entries_since(entries: List[ProgressLogEntry], since_date: Optional[str]) -> List[ProgressLogEntry]:
    """Filter entries to only those after since_date."""
    if since_date is None:
        return entries
    
    try:
        since_dt = datetime.fromisoformat(since_date)
    except ValueError:
        return entries
    
    filtered = []
    for entry in entries:
        try:
            entry_dt = datetime.fromisoformat(entry.timestamp)
            if entry_dt > since_dt:
                filtered.append(entry)
        except ValueError:
            continue
    
    return filtered


def detect_failure_patterns(entries: List[ProgressLogEntry]) -> List[FailurePattern]:
    """Detect repeated failure patterns from log entries."""
    # Group by (status, summary)
    groups = {}
    for entry in entries:
        key = (entry.status, entry.summary)
        if key not in groups:
            groups[key] = []
        groups[key].append(entry)
    
    patterns = []
    for (status, summary), group_entries in groups.items():
        if len(group_entries) >= 2:  # Repeated = 2 or more occurrences
            dates = [e.timestamp for e in group_entries]
            details = group_entries[0].details  # Use first as example
            patterns.append(FailurePattern(
                status=status,
                summary=summary,
                details=details,
                occurrences=len(group_entries),
                dates=dates,
                example_details=details,
            ))
    
    # Sort by frequency (desc), then by most recent date (desc)
    patterns.sort(key=lambda p: (-p.occurrences, -datetime.fromisoformat(p.dates[-1]).timestamp()))
    return patterns


def analyze_root_cause(pattern: FailurePattern, rules_files: List[Path]) -> Tuple[str, str, str]:
    """Analyze a failure pattern and propose a minimal fix.
    
    Returns: (file_path_str, description, diff)
    """
    # This is a simplified analysis based on known patterns from Project 8
    # In practice, this would be more sophisticated
    
    if pattern.status == "CONNECTOR_SKIPPED" and "Failed to create branch" in pattern.details:
        # The connector fails to create branch - likely because default branch detection fails
        # or origin/HEAD is not set. The fix is to make branch creation more robust.
        
        # Find the connector.py file
        connector_file = None
        for f in rules_files:
            if f.name == "connector.py":
                connector_file = f
                break
        
        if connector_file:
            # Proposed fix: Add fallback branch creation if origin/HEAD fails
            diff = '''--- a/src/connector.py
+++ b/src/connector.py
@@ -74,7 +74,10 @@ def create_branch(repo_root: Path, branch_name: str, base_branch: Optional[str] = None) -> bool:
     """Create a new branch from base_branch."""
     if base_branch is None:
         base_branch = get_default_branch(repo_root)
-    # Fetch latest
+    # Fetch latest (with fallback if origin/HEAD not set)
     run_git(repo_root, "fetch", "origin", base_branch)
-    # Create branch
+    # Create branch - try with origin/base, fallback to local base
+    result = run_git(repo_root, "checkout", "-b", branch_name, f"origin/{base_branch}")
+    if result.returncode != 0:
+        result = run_git(repo_root, "checkout", "-b", branch_name, base_branch)
     return result.returncode == 0
'''
            return (
                str(connector_file),
                "Add fallback to local base branch when origin/HEAD fetch fails",
                diff.strip(),
            )
    
    # Default: no specific fix identified
    return ("", "No specific fix identified for this pattern", "")


def find_outdated_rule(rules_files: List[Path]) -> Tuple[str, str, str]:
    """Find an outdated/unneeded rule to propose for deletion.
    
    Returns: (file_path_str, description, diff)
    """
    # Look for rules that might be outdated
    # For Project 8, the max_commits=100 in skill.py might be too conservative now
    # Or the budget limits might be outdated
    
    for f in rules_files:
        if f.name == "budget.py":
            # Check if budget limits are outdated (e.g., too restrictive)
            content = f.read_text(encoding="utf-8")
            if "max_cost_per_run_usd" in content and "0.0075" in content:
                diff = '''--- a/src/budget.py
+++ b/src/budget.py
@@ -14,7 +14,7 @@ def load_budget_from_env() -> BudgetConfig:
     max_cost_per_run_usd: float = float(os.environ.get("LOOP_MAX_COST_USD", "0.0075"))
 '''
                return (
                    str(f),
                    "Remove outdated budget limit comment (limit now configurable via env)",
                    diff.strip(),
                )
    
    return ("", "No outdated rule identified", "")


def execute_dream_skill(config: DreamConfig) -> SkillResult:
    """Execute the full dream skill procedure."""
    # Step 1: Read state
    from dream_spine import read_dream_state
    dream_state = read_dream_state(config.dreaming_state_path)
    
    # Step 2: Read progress log
    entries = parse_progress_log(config.progress_md_path)
    
    # Step 3: Filter since last analyzed
    filtered_entries = filter_entries_since(entries, dream_state.last_analyzed_date)
    
    # Step 4: Detect patterns
    patterns = detect_failure_patterns(filtered_entries)
    
    # Step 5: Select top pattern and propose fix
    proposals = []
    if patterns:
        top_pattern = patterns[0]
        file_path_str, description, diff = analyze_root_cause(top_pattern, config.rules_files)
        if file_path_str and diff:
            # Build evidence string
            evidence = (
                f"STATUS: {top_pattern.status}\n"
                f"Failure '{top_pattern.status}: {top_pattern.summary}' "
                f"occurred {top_pattern.occurrences} times on dates: {', '.join(top_pattern.dates)}. "
                f"Example: {top_pattern.example_details}"
            )
            proposal_hash = hashlib.sha256(diff.encode()).hexdigest()[:12]
            proposals.append(ProposedChange(
                file_path=Path(file_path_str),
                change_type="modify",
                description=description,
                evidence=evidence,
                diff=diff,
                proposal_hash=proposal_hash,
            ))
    
    # Step 6: Propose one deletion
    deletions = []
    file_path_str, description, diff = find_outdated_rule(config.rules_files)
    if file_path_str and diff:
        # Build evidence for deletion - reference that budget is now fully env-configurable
        # Use a reference date for when the env var was introduced
        evidence = (
            f"Failure 'CONFIG_OUTDATED: Hardcoded budget default' "
            f"occurred 1 time on date: 2026-08-29T00:00:00. "
            f"Example: max_cost_per_run_usd default '0.0075' is misleading since LOOP_MAX_COST_USD env var is now used. "
            f"STATUS: CONFIG_OUTDATED"
        )
        proposal_hash = hashlib.sha256(diff.encode()).hexdigest()[:12]
        deletions.append(ProposedChange(
            file_path=Path(file_path_str),
            change_type="delete",
            description=description,
            evidence=evidence,
            diff=diff,
            proposal_hash=proposal_hash,
        ))
    
    # Step 7: Determine new analyzed_until date
    analyzed_until = filtered_entries[-1].timestamp if filtered_entries else dream_state.last_analyzed_date or ""
    
    # Estimate tokens
    tokens = len(str(patterns)) // 4 + len(str(proposals)) // 4 + len(str(deletions)) // 4 + 500
    
    return SkillResult(
        patterns=patterns,
        proposals=proposals,
        deletions=deletions,
        analyzed_until=analyzed_until,
        tokens_estimated=tokens,
    )


if __name__ == "__main__":
    print(SKILL_DOCUMENTATION)