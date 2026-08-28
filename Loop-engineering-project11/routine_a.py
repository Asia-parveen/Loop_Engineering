#!/usr/bin/env python3
"""
Routine A: Manual/One-off Trigger
Creates a reviewable draft on a `claude/` branch with summary.
Does NOT automatically trigger Routine B.
Saves clear state/log evidence.
"""

import os
import sys
import json
import uuid
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


STATE_FILE = "routine_state.json"
LOG_DIR = "logs"


class RoutineAError(Exception):
    """Custom exception for Routine A errors."""
    pass


def ensure_directories() -> None:
    """Ensure required directories exist."""
    Path(LOG_DIR).mkdir(exist_ok=True)


def load_state() -> Dict[str, Any]:
    """Load state from file."""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "routine_a_runs": [],
        "routine_b_runs": [],
        "current_draft": None,
        "human_gate_status": "pending"
    }


def save_state(state: Dict[str, Any]) -> None:
    """Save state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_message(level: str, message: str) -> str:
    """Create a log entry."""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] [{level.upper()}] {message}"
    return entry


def write_log(log_entries: list, run_id: str) -> str:
    """Write log entries to file."""
    log_file = Path(LOG_DIR) / f"routine_a_{run_id}.log"
    with open(log_file, "w") as f:
        f.write("\n".join(log_entries))
    return str(log_file)


def get_git_root() -> Path:
    """Find the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RoutineAError(f"Not a git repository: {result.stderr}")
    return Path(result.stdout.strip())


def get_git_commits(since: Optional[str] = None) -> list:
    """Get git commits since a date or all commits."""
    git_root = get_git_root()
    cmd = ["git", "log", "--oneline", "--format=%h|%ad|%s", "--date=short"]
    if since:
        cmd.append(f"--since={since}")
    result = subprocess.run(cmd, cwd=git_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise RoutineAError(f"Git log failed: {result.stderr}")
    
    commits = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0],
                    "date": parts[1],
                    "message": parts[2]
                })
    return commits


def create_summary(commits: list) -> str:
    """Create a summary from commits."""
    if not commits:
        return "# Commit Summary\n\nNo commits found.\n"
    
    summary = "# Commit Summary\n\n"
    summary += f"Generated: {datetime.now().isoformat()}\n"
    summary += f"Total commits: {len(commits)}\n\n"
    
    by_date = {}
    for commit in commits:
        date = commit["date"]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(commit)
    
    for date in sorted(by_date.keys(), reverse=True):
        summary += f"## {date}\n\n"
        for commit in by_date[date]:
            summary += f"- `{commit['hash']}` {commit['message']}\n"
        summary += "\n"
    
    return summary


def create_claude_branch(branch_name: str, summary: str) -> bool:
    """Create or update a claude/ branch with the summary."""
    git_root = get_git_root()
    try:
        # Check if branch exists locally
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            cwd=git_root, capture_output=True, text=True
        )
        branch_exists = result.returncode == 0
        
        if branch_exists:
            # Switch to branch
            subprocess.run(["git", "checkout", branch_name], cwd=git_root, check=True, capture_output=True)
        else:
            # Create new orphan branch
            subprocess.run(["git", "checkout", "--orphan", branch_name], cwd=git_root, check=True, capture_output=True)
            # Remove all files
            subprocess.run(["git", "rm", "-rf", "."], cwd=git_root, capture_output=True)
        
        # Write summary file
        summary_file = git_root / "COMMIT_SUMMARY.md"
        with open(summary_file, "w") as f:
            f.write(summary)
        
        # Add and commit
        subprocess.run(["git", "add", "COMMIT_SUMMARY.md"], cwd=git_root, check=True, capture_output=True)
        commit_msg = f"chore: commit summary draft ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=git_root, check=True, capture_output=True)
        
        # Push to origin (optional, for reviewability)
        push_result = subprocess.run(
            ["git", "push", "origin", branch_name, "--force"],
            cwd=git_root, capture_output=True, text=True
        )
        
        # Return to main branch
        subprocess.run(["git", "checkout", "main"], cwd=git_root, capture_output=True)
        
        return push_result.returncode == 0
    except subprocess.CalledProcessError as e:
        raise RoutineAError(f"Git operation failed: {e.stderr}")


def run_routine_a(since: Optional[str] = None, branch_suffix: Optional[str] = None) -> Dict[str, Any]:
    """
    Run Routine A: Create reviewable draft.
    
    Args:
        since: Optional date string (YYYY-MM-DD) to filter commits
        branch_suffix: Optional suffix for branch name
        
    Returns:
        Dict with run results
    """
    ensure_directories()
    run_id = str(uuid.uuid4())[:8]
    log_entries = []
    
    log_entries.append(log_message("info", f"Starting Routine A run: {run_id}"))
    log_entries.append(log_message("info", f"Parameters: since={since}, branch_suffix={branch_suffix}"))
    
    state = load_state()
    
    # Generate branch name
    if branch_suffix:
        branch_name = f"claude/{branch_suffix}"
    else:
        branch_name = f"claude/summary-{run_id}"
    
    log_entries.append(log_message("info", f"Target branch: {branch_name}"))
    
    try:
        # Get commits
        commits = get_git_commits(since)
        log_entries.append(log_message("info", f"Found {len(commits)} commit(s)"))
        
        # Create summary
        summary = create_summary(commits)
        summary_hash = hashlib.sha256(summary.encode()).hexdigest()[:12]
        log_entries.append(log_message("info", f"Summary created (hash: {summary_hash})"))
        
        # Create claude branch
        log_entries.append(log_message("info", f"Creating/updating branch: {branch_name}"))
        create_claude_branch(branch_name, summary)
        log_entries.append(log_message("success", f"Branch {branch_name} created/updated successfully"))
        
        # Save draft info to state
        draft_info = {
            "run_id": run_id,
            "branch_name": branch_name,
            "summary_hash": summary_hash,
            "commit_count": len(commits),
            "created_at": datetime.now().isoformat(),
            "status": "ready_for_review",
            "log_file": f"logs/routine_a_{run_id}.log"
        }
        state["current_draft"] = draft_info
        state["routine_a_runs"].append(draft_info)
        state["human_gate_status"] = "awaiting_review"
        save_state(state)
        
        log_entries.append(log_message("info", "State saved. Draft ready for human review."))
        log_entries.append(log_message("info", "Routine A completed. Routine B NOT triggered automatically."))
        log_entries.append(log_message("success", "Routine A completed successfully"))
        
        log_file = write_log(log_entries, run_id)
        
        return {
            "success": True,
            "run_id": run_id,
            "branch_name": branch_name,
            "summary_hash": summary_hash,
            "commit_count": len(commits),
            "log_file": log_file,
            "state_file": STATE_FILE,
            "message": "Draft created successfully. Review the branch before triggering Routine B."
        }
        
    except RoutineAError as e:
        log_entries.append(log_message("error", str(e)))
        log_file = write_log(log_entries, run_id)
        
        error_info = {
            "run_id": run_id,
            "error": str(e),
            "created_at": datetime.now().isoformat(),
            "status": "failed",
            "log_file": log_file
        }
        state["routine_a_runs"].append(error_info)
        save_state(state)
        
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e),
            "log_file": log_file,
            "state_file": STATE_FILE
        }
    except Exception as e:
        log_entries.append(log_message("error", f"Unexpected error: {e}"))
        log_file = write_log(log_entries, run_id)
        
        error_info = {
            "run_id": run_id,
            "error": f"Unexpected error: {e}",
            "created_at": datetime.now().isoformat(),
            "status": "failed",
            "log_file": log_file
        }
        state["routine_a_runs"].append(error_info)
        save_state(state)
        
        return {
            "success": False,
            "run_id": run_id,
            "error": f"Unexpected error: {e}",
            "log_file": log_file,
            "state_file": STATE_FILE
        }


def main():
    """Main entry point for Routine A."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Routine A: Create reviewable draft")
    parser.add_argument("--since", help="Date filter for commits (YYYY-MM-DD)")
    parser.add_argument("--branch-suffix", help="Suffix for claude/ branch name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN: Would create commit summary draft on claude/ branch")
        print(f"  Since: {args.since or 'all commits'}")
        print(f"  Branch suffix: {args.branch_suffix or 'auto-generated'}")
        return 0
    
    result = run_routine_a(since=args.since, branch_suffix=args.branch_suffix)
    
    if result["success"]:
        print(f"\n✅ Routine A completed successfully!")
        print(f"   Run ID: {result['run_id']}")
        print(f"   Branch: {result['branch_name']}")
        print(f"   Commits: {result['commit_count']}")
        print(f"   Summary hash: {result['summary_hash']}")
        print(f"   Log: {result['log_file']}")
        print(f"   State: {result['state_file']}")
        print(f"\n📋 Next step: Review the draft on branch '{result['branch_name']}'")
        print(f"   Then trigger Routine B manually using the documented curl command.")
        return 0
    else:
        print(f"\n❌ Routine A failed!")
        print(f"   Run ID: {result['run_id']}")
        print(f"   Error: {result['error']}")
        print(f"   Log: {result['log_file']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())