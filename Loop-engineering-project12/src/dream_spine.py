"""Dream Spine — Persistent Memory for Dream Loop (Project 12).

Manages reading/writing dreaming-state.md which tracks the weekly improvement loop's
state, log entries, and proposals.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


DREAMING_STATE_PATH = Path(__file__).resolve().parent.parent / "dreaming-state.md"


@dataclass(frozen=True)
class DreamState:
    """Parsed state from dreaming-state.md."""
    last_run: Optional[str]
    last_analyzed_date: Optional[str]
    last_proposal_hash: Optional[str]
    budget: dict
    log_entries: list


def get_dreaming_state_path() -> Path:
    """Get path to dreaming-state.md."""
    return DREAMING_STATE_PATH


def read_dream_state(path: Optional[Path] = None) -> DreamState:
    """Read and parse dreaming-state.md."""
    if path is None:
        path = get_dreaming_state_path()
    if not path.exists():
        return DreamState(
            last_run=None,
            last_analyzed_date=None,
            last_proposal_hash=None,
            budget={},
            log_entries=[],
        )

    content = path.read_text(encoding="utf-8")
    
    # Parse state section
    last_run = None
    last_analyzed_date = None
    last_proposal_hash = None
    budget = {}
    
    state_section = False
    budget_section = False
    log_section = False
    log_entries = []
    
    for line in content.splitlines():
        line_stripped = line.strip()
        
        if line_stripped.startswith("## State"):
            state_section = True
            budget_section = False
            log_section = False
            continue
        elif line_stripped.startswith("## Budget"):
            state_section = False
            budget_section = True
            log_section = False
            continue
        elif line_stripped.startswith("## Log"):
            state_section = False
            budget_section = False
            log_section = True
            continue
        
        if state_section and line_stripped.startswith("- last_run:"):
            last_run = line_stripped.replace("- last_run:", "").strip() or None
        elif state_section and line_stripped.startswith("- last_analyzed_date:"):
            last_analyzed_date = line_stripped.replace("- last_analyzed_date:", "").strip() or None
        elif state_section and line_stripped.startswith("- last_proposal_hash:"):
            last_proposal_hash = line_stripped.replace("- last_proposal_hash:", "").strip() or None
        
        if budget_section and line_stripped.startswith("- "):
            parts = line_stripped[2:].split(":", 1)
            if len(parts) == 2:
                budget[parts[0].strip()] = parts[1].strip()
        
        if log_section and line_stripped.startswith("### "):
            log_entries.append(line_stripped[4:].strip())
        elif log_section and log_entries and line_stripped and not line_stripped.startswith("#"):
            log_entries[-1] += "\n" + line_stripped
    
    return DreamState(
        last_run=last_run,
        last_analyzed_date=last_analyzed_date,
        last_proposal_hash=last_proposal_hash,
        budget=budget,
        log_entries=log_entries,
    )


def write_dream_state(
    last_run: str,
    last_analyzed_date: str,
    last_proposal_hash: Optional[str],
    budget: dict,
    log_entries: list,
) -> None:
    """Write dreaming-state.md with updated state."""
    path = get_dreaming_state_path()
    
    lines = [
        "# Dreaming State",
        "",
        "Persistent memory for Loop Engineering Project 12 — Dream Loop (Weekly Improvement Loop).",
        "",
        "## State",
        f"- last_run: {last_run}",
        f"- last_analyzed_date: {last_analyzed_date}",
        f"- last_proposal_hash: {last_proposal_hash or ''}",
        "",
        "## Budget",
    ]
    
    for key, value in budget.items():
        lines.append(f"- {key}: {value}")
    
    lines.extend(["", "## Log"])
    
    for entry in log_entries:
        lines.append(f"### {entry}")
    
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_dream_log(
    timestamp: str,
    status: str,
    summary: str,
    details: str,
    proposal: Optional[str] = None,
    result: Optional[str] = None,
) -> list:
    """Format a new log entry and return updated log entries list."""
    state = read_dream_state()
    new_entry = f"{timestamp}\nSTATUS: {status}\nSummary: {summary}\nDetails: {details}"
    if proposal:
        new_entry += f"\nProposal: {proposal}"
    if result:
        new_entry += f"\nResult: {result}"
    
    updated_entries = state.log_entries + [new_entry]
    return updated_entries


def format_dream_log_entry(
    status: str,
    summary: str,
    details: str,
    proposal: Optional[str] = None,
    result: Optional[str] = None,
    needs_human: bool = False,
) -> str:
    """Format a log entry for dreaming-state.md."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry = f"{timestamp}\nSTATUS: {status}\nSummary: {summary}\nDetails: {details}"
    if proposal:
        entry += f"\nProposal: {proposal}"
    if result:
        entry += f"\nResult: {result}"
    if needs_human:
        entry += "\nNEEDS HUMAN"
    return entry


if __name__ == "__main__":
    state = read_dream_state()
    print(f"Last run: {state.last_run}")
    print(f"Last analyzed: {state.last_analyzed_date}")
    print(f"Budget: {state.budget}")
    print(f"Log entries: {len(state.log_entries)}")
    for entry in state.log_entries:
        print(f"  {entry[:80]}...")