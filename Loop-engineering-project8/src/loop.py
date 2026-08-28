"""Main Loop — Loop Engineering Practice Project 8: Full Six-Part Loop.

Orchestrates all six parts:
1. HEARTBEAT — scheduled trigger/cadence (external, one-pass per invocation)
2. WORKTREE — isolated workspace for changes
3. SKILL — documented procedure for changelog draft generation
4. MAKER — produces the changelog draft in the worktree
5. CHECKER — validates the draft before any shipping
6. CONNECTOR — Git/GitHub integration (branch + optional PR)

Also includes:
- SPINE (progress.md) — persistent memory across runs
- BUDGET — token/cost guards with hard limits
- NEEDS HUMAN escalation when loop cannot safely continue
- Clear observability/logging
- One-pass execution; scheduling remains external
"""

import sys
import traceback
from pathlib import Path
from typing import Optional

from .spine import (
    get_progress_path,
    get_root,
    read_state,
    read_budget,
    update_progress,
    format_log_entry,
    estimate_tokens,
)
from .heartbeat import HeartbeatConfig, get_cadence_from_env, get_timeout_from_env, install_timeout_guard, clear_timeout_guard
from .worktree import get_worktree_base_dir
from .budget import BudgetConfig, load_budget_from_env, BudgetExceededError
from .skill import SkillConfig
from .maker import MakerConfig, run_maker
from .checker import CheckerConfig, run_checks
from .connector import ConnectorConfig, run_connector


def run_pass() -> int:
    """Execute exactly ONE pass of the six-part loop. Returns exit code."""
    # === HEARTBEAT: Configure cadence and timeout ===
    heartbeat = HeartbeatConfig(
        cadence=get_cadence_from_env(),
        timeout_seconds=get_timeout_from_env(),
    )
    install_timeout_guard(heartbeat.timeout_seconds)

    # === SPINE: Read persistent state ===
    state = read_state(get_progress_path())
    budget_config = load_budget_from_env()

    cursor = state.get("last_seen_commit")
    last_changelog_hash = state.get("last_changelog_hash")

    run_start_msg = f"Starting run (cursor: {cursor or 'none'})"
    print(run_start_msg, file=sys.stderr)

    try:
        # === WORKTREE: Prepare isolated workspace base ===
        worktree_base = get_worktree_base_dir()

        # === MAKER: Produce changelog draft ===
        maker_config = MakerConfig(
            repo_root=get_root(),
            worktree_base=worktree_base,
            cursor_commit=cursor,
            budget=budget_config,
            max_commits=100,
        )
        maker_result = run_maker(maker_config)

        # === CHECKER: Validate the draft ===
        checker_config = CheckerConfig()
        check_result = run_checks(maker_result, checker_config)

        # Log check results
        for check in check_result.checks:
            print(f"  CHECK: {check}", file=sys.stderr)
        for failure in check_result.failures:
            print(f"  FAIL: {failure}", file=sys.stderr)
        for warning in check_result.warnings:
            print(f"  WARN: {warning}", file=sys.stderr)

        if not check_result.passed:
            # Checker failed - log and escalate
            log_entry = format_log_entry(
                status="CHECKER_FAILED",
                summary=f"Changelog validation failed: {len(check_result.failures)} failure(s)",
                details="; ".join(check_result.failures),
                needs_human=True,
            )
            state["last_status"] = "CHECKER_FAILED"
            state["last_budget_used"] = str(maker_result.budget_result.tokens_used)
            update_progress(PROGRESS, state, read_budget(PROGRESS), log_entry)
            print(f"CHECKER FAILED: {log_entry}", file=sys.stderr)
            return 1

        # Deduplication: Skip if changelog unchanged
        if check_result.changelog_hash == last_changelog_hash:
            log_entry = format_log_entry(
                status="SKIPPED_DUPLICATE",
                summary="Changelog unchanged since last run",
                details=f"Hash: {check_result.changelog_hash}",
            )
            state["last_status"] = "SKIPPED_DUPLICATE"
            state["last_budget_used"] = str(maker_result.budget_result.tokens_used)
            update_progress(get_progress_path(), state, read_budget(get_progress_path()), log_entry)
            print(f"SKIPPED: {log_entry}", file=sys.stderr)
            return 0

        # === CONNECTOR: Ship validated changes ===
        connector_config = ConnectorConfig(
            repo_root=get_root(),
            branch_prefix="changelog-draft/",
            create_pr=False,  # Set True if gh CLI available and desired
        )
        connector_result = run_connector(connector_config, maker_result, check_result)

        # === SPINE: Update persistent state ===
        if connector_result.shipped:
            status = "SHIPPED"
            summary = f"Changelog draft shipped: {connector_result.branch_name}"
            details = connector_result.message
            needs_human = connector_result.needs_human
            state["last_seen_commit"] = maker_result.skill_result.new_cursor
            state["last_changelog_hash"] = check_result.changelog_hash
        else:
            status = "CONNECTOR_SKIPPED"
            summary = "Connector did not ship (idempotent or failed)"
            details = connector_result.message
            needs_human = connector_result.needs_human
            # Still advance cursor if we produced valid output
            state["last_seen_commit"] = maker_result.skill_result.new_cursor
            state["last_changelog_hash"] = check_result.changelog_hash

        state["last_status"] = status
        state["last_budget_used"] = str(maker_result.budget_result.tokens_used)

        log_entry = format_log_entry(
            status=status,
            summary=summary,
            details=details,
            needs_human=needs_human,
        )
        update_progress(get_progress_path(), state, read_budget(get_progress_path()), log_entry)

        print(f"DONE: {log_entry}", file=sys.stderr)

        if needs_human:
            return 2  # Special exit code for NEEDS HUMAN (non-fatal)

        return 0

    except BudgetExceededError as e:
        log_entry = format_log_entry(
            status="BUDGET_EXCEEDED",
            summary="Token/cost budget exceeded",
            details=str(e.result.error),
            needs_human=True,
        )
        state["last_status"] = "BUDGET_EXCEEDED"
        update_progress(get_progress_path(), state, read_budget(get_progress_path()), log_entry)
        print(f"BUDGET EXCEEDED: {e.result.error}", file=sys.stderr)
        return 1

    except TimeoutError:
        log_entry = format_log_entry(
            status="TIMEOUT",
            summary=f"Run exceeded {heartbeat.timeout_seconds}s timeout",
            details="Run terminated by timeout guard",
            needs_human=True,
        )
        state["last_status"] = "TIMEOUT"
        update_progress(get_progress_path(), state, read_budget(get_progress_path()), log_entry)
        print(f"TIMEOUT: Run exceeded {heartbeat.timeout_seconds}s", file=sys.stderr)
        return 1

    except Exception as e:
        log_entry = format_log_entry(
            status="ERROR",
            summary=f"Unexpected error: {type(e).__name__}",
            details=str(e),
            needs_human=True,
        )
        state["last_status"] = "ERROR"
        update_progress(get_progress_path(), state, read_budget(get_progress_path()), log_entry)
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    finally:
        clear_timeout_guard()


def main() -> int:
    """Entry point."""
    return run_pass()


if __name__ == "__main__":
    sys.exit(main())