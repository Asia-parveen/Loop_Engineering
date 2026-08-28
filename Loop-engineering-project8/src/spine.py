"""Spine / Progress management for Loop Engineering Practice Project 8.

The spine is the single persistent memory (progress.md) that survives across runs.
It stores state, budget info, and an append-only log of all runs.
"""

import datetime
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

def get_root() -> Path:
    """Get the repository root (current working directory)."""
    return Path.cwd()


def get_progress_path() -> Path:
    """Get the progress.md path."""
    return get_root() / "progress.md"


# Backward compatibility
ROOT = get_root()
PROGRESS = get_progress_path()

STATE_HEADER_RE = re.compile(r"(?m)^## State *$")
BUDGET_HEADER_RE = re.compile(r"(?m)^## Budget *$")
LOG_HEADER_RE = re.compile(r"(?m)^## Log *$")

DEFAULT_STATE = {
    "last_run": None,
    "last_seen_commit": None,
    "last_changelog_hash": None,
    "last_budget_used": "0",
    "last_status": None,
}

DEFAULT_BUDGET = {
    "max_tokens_per_run": "5000",
    "token_price_per_1k": "0.0015",
    "max_cost_per_run_usd": "0.0075",
}


def read_state(path: Path) -> Dict[str, Optional[str]]:
    """Read state fields from progress.md."""
    state = {k: None for k in DEFAULT_STATE}
    if not path.exists():
        return state
    text = path.read_text(encoding="utf-8")
    for key in state:
        # Match only until end of line, not across lines
        # Use [ \t]* instead of \s* to avoid matching newlines
        match = re.search(rf"(?m)^- {key}:[ \t]*([^\n]*)$", text)
        if match and match.group(1).strip():
            state[key] = match.group(1).strip()
    return state


def read_budget(path: Path) -> Dict[str, str]:
    """Read budget fields from progress.md."""
    budget = DEFAULT_BUDGET.copy()
    if not path.exists():
        return budget
    text = path.read_text(encoding="utf-8")
    for key in budget:
        match = re.search(rf"(?m)^- {key}:[ \t]*([^\n]*)$", text)
        if match and match.group(1).strip():
            budget[key] = match.group(1).strip()
    return budget


def set_field(text: str, key: str, value: Optional[str]) -> str:
    """Set or update a field in the markdown text."""
    if value is None:
        return text
    line = f"- {key}: {value}"
    field_re = re.compile(rf"(?m)^- {key}:.*$")
    if field_re.search(text):
        return field_re.sub(line, text, count=1)
    state_header = STATE_HEADER_RE.search(text)
    if state_header:
        pos = state_header.end()
        return text[:pos] + "\n" + line + text[pos:]
    log_match = LOG_HEADER_RE.search(text)
    tail = text[log_match.start():] if log_match else "## Log\n"
    return f"# Progress\n\n## State\n{line}\n\n" + tail


def set_budget_field(text: str, key: str, value: Optional[str]) -> str:
    """Set or update a budget field in the markdown text."""
    if value is None:
        return text
    line = f"- {key}: {value}"
    field_re = re.compile(rf"(?m)^- {key}:.*$")
    if field_re.search(text):
        return field_re.sub(line, text, count=1)
    budget_header = BUDGET_HEADER_RE.search(text)
    if budget_header:
        pos = budget_header.end()
        return text[:pos] + "\n" + line + text[pos:]
    log_match = LOG_HEADER_RE.search(text)
    tail = text[log_match.start():] if log_match else "## Log\n"
    return f"# Progress\n\n## Budget\n{line}\n\n" + tail


def update_progress(
    path: Path,
    state: Dict[str, Optional[str]],
    budget: Dict[str, str],
    log_entry: str,
) -> None:
    """Update progress.md with new state, budget, and log entry."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    text = path.read_text(encoding="utf-8") if path.exists() else initial_progress_text()

    for key, value in state.items():
        text = set_field(text, key, value)
    text = set_field(text, "last_run", now)

    for key, value in budget.items():
        text = set_budget_field(text, key, value)

    entry = f"\n### {now}\n{log_entry}\n"
    text = text.rstrip() + entry
    path.write_text(text, encoding="utf-8")


def initial_progress_text() -> str:
    """Return the initial progress.md content."""
    return """# Progress

Persistent spine for Loop Engineering Practice Project 8 -- Full Six-Part Loop.
Chosen chore: **Changelog Draft Generation** from Git commit history.
Each scheduled run reads this file, executes the six-part loop, and appends a dated result below.

## State
- last_run: 
- last_seen_commit: 
- last_changelog_hash: 
- last_budget_used: 0
- last_status: 

## Budget
- max_tokens_per_run: 5000
- token_price_per_1k: 0.0015
- max_cost_per_run_usd: 0.0075

## Log
"""


def format_log_entry(
    status: str,
    summary: str,
    details: Optional[str] = None,
    needs_human: bool = False,
) -> str:
    """Format a log entry for the progress.md log section."""
    lines = [f"STATUS: {status}", f"Summary: {summary}"]
    if details:
        lines.append(f"Details: {details}")
    if needs_human:
        lines.append("NEEDS HUMAN")
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return max(1, len(text) // 4)


def calculate_cost(tokens: int, price_per_1k: float) -> float:
    """Calculate cost in USD for given tokens."""
    return (tokens / 1000.0) * price_per_1k


if __name__ == "__main__":
    print("Spine module - not meant to run directly")
    sys.exit(1)