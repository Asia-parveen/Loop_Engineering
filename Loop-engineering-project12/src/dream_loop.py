"""Main Dream Loop — Loop Engineering Project 12: Dream Loop (Weekly Improvement Loop).

Orchestrates all parts:
1. DREAM SPINE — Read dreaming-state.md (persistent memory)
2. DREAM SKILL — Analyze Project 8's progress.md for repeated failures
3. DREAM MAKER — Produce proposal artifacts (PR descriptions + diffs)
4. DREAM CHECKER — Validate proposals (evidence, minimality, safety)
5. DREAM CONNECTOR — Create PR on claude/ branch (no auto-merge)
6. DREAM SPINE — Update dreaming-state.md with results

Also includes:
- Budget guards
- NEEDS HUMAN escalation
- One-pass execution
"""

import sys
import traceback
from pathlib import Path
from typing import Optional

from dream_spine import (
    get_dreaming_state_path,
    read_dream_state,
    write_dream_state,
    append_dream_log,
    format_dream_log_entry,
)
from dream_skill import DreamConfig, SkillResult, execute_dream_skill
from dream_maker import DreamMakerConfig, run_maker
from dream_checker import CheckerConfig, run_checks
from dream_connector import DreamConnectorConfig, run_connector


def get_project12_root() -> Path:
    """Get Project 12 root directory."""
    return Path(__file__).resolve().parent.parent


def get_project8_root() -> Path:
    """Get Project 8 root directory (evidence source)."""
    return Path(__file__).resolve().parent.parent.parent / "Loop-engineering-project8"


def get_proposal_dir() -> Path:
    """Get directory for proposal artifacts."""
    return get_project12_root() / ".dream_proposals"


def load_budget_from_env():
    """Load budget configuration from environment."""
    import os
    from dataclasses import dataclass
    
    @dataclass(frozen=True)
    class BudgetConfig:
        max_tokens: int = int(os.environ.get("LOOP_MAX_TOKENS", "3000"))
        token_price_per_1k: float = float(os.environ.get("LOOP_TOKEN_PRICE", "0.0015"))
        max_cost_usd: float = float(os.environ.get("LOOP_MAX_COST_USD", "0.0045"))
    
    return BudgetConfig()


def check_budget(budget_config, tokens_estimated: int) -> bool:
    """Check if estimated tokens exceed budget."""
    max_cost = budget_config.max_tokens * budget_config.token_price_per_1k / 1000
    estimated_cost = tokens_estimated * budget_config.token_price_per_1k / 1000
    
    if tokens_estimated > budget_config.max_tokens:
        return False
    if estimated_cost > budget_config.max_cost_usd:
        return False
    return True


def run_pass() -> int:
    """Execute exactly ONE pass of the Dream Loop. Returns exit code."""
    
    # === DREAM SPINE: Read persistent state ===
    dream_state = read_dream_state()
    budget_config = load_budget_from_env()
    
    last_run = dream_state.last_run
    last_analyzed = dream_state.last_analyzed_date
    
    run_start_msg = f"Dream Loop starting (last analyzed: {last_analyzed or 'never'})"
    print(run_start_msg, file=sys.stderr)
    
    try:
        # === DREAM SKILL: Analyze Project 8 progress.md ===
        project8_root = get_project8_root()
        progress_md = project8_root / "progress.md"
        
        if not progress_md.exists():
            log_entry = format_dream_log_entry(
                status="ERROR",
                summary="Project 8 progress.md not found",
                details=f"Expected at {progress_md}",
                needs_human=True,
            )
            updated_log = append_dream_log(
                timestamp="",
                status="ERROR",
                summary="Project 8 progress.md not found",
                details=f"Expected at {progress_md}",
            )
            write_dream_state(
                last_run="",
                last_analyzed_date=last_analyzed or "",
                last_proposal_hash=None,
                budget=dream_state.budget,
                log_entries=updated_log,
            )
            print(f"ERROR: {log_entry}", file=sys.stderr)
            return 1
        
        skill_config = DreamConfig(
            progress_md_path=progress_md,
            dreaming_state_path=get_dreaming_state_path(),
            rules_files=[
                project8_root / "src" / "skill.py",
                project8_root / "src" / "connector.py",
                project8_root / "src" / "checker.py",
                project8_root / "src" / "budget.py",
                project8_root / "src" / "maker.py",
            ],
        )
        
        skill_result = execute_dream_skill(skill_config)
        
        # Budget check
        if not check_budget(budget_config, skill_result.tokens_estimated):
            log_entry = format_dream_log_entry(
                status="BUDGET_EXCEEDED",
                summary="Token budget exceeded in skill phase",
                details=f"Estimated {skill_result.tokens_estimated} tokens > {budget_config.max_tokens}",
                needs_human=True,
            )
            updated_log = append_dream_log(
                timestamp="",
                status="BUDGET_EXCEEDED",
                summary="Token budget exceeded in skill phase",
                details=f"Estimated {skill_result.tokens_estimated} tokens > {budget_config.max_tokens}",
            )
            write_dream_state(
                last_run="",
                last_analyzed_date=last_analyzed or "",
                last_proposal_hash=None,
                budget=dream_state.budget,
                log_entries=updated_log,
            )
            print(f"BUDGET EXCEEDED: {log_entry}", file=sys.stderr)
            return 1
        
        # === DREAM MAKER: Produce proposal artifacts ===
        proposal_dir = get_proposal_dir()
        maker_config = DreamMakerConfig(
            skill_result=skill_result,
            proposal_dir=proposal_dir,
            project8_root=project8_root,
        )
        maker_result = run_maker(maker_config)
        
        # === DREAM CHECKER: Validate proposals ===
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
            log_entry = format_dream_log_entry(
                status="CHECKER_FAILED",
                summary=f"Proposal validation failed: {len(check_result.failures)} failure(s)",
                details="; ".join(check_result.failures),
                needs_human=True,
            )
            updated_log = append_dream_log(
                timestamp="",
                status="CHECKER_FAILED",
                summary=f"Proposal validation failed: {len(check_result.failures)} failure(s)",
                details="; ".join(check_result.failures),
            )
            write_dream_state(
                last_run="",
                last_analyzed_date=last_analyzed or "",
                last_proposal_hash=None,
                budget=dream_state.budget,
                log_entries=updated_log,
            )
            print(f"CHECKER FAILED: {log_entry}", file=sys.stderr)
            return 1
        
        # === DREAM CONNECTOR: Ship validated proposals ===
        connector_config = DreamConnectorConfig(
            repo_root=project8_root,  # Create PRs in Project 8 repo
            create_pr=False,  # Set True if gh CLI available
            require_human_approval=True,
        )
        connector_result = run_connector(connector_config, maker_result, check_result)
        
        # === DREAM SPINE: Update persistent state ===
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        
        # Determine proposal hash for tracking
        proposal_hash = None
        if maker_result.artifacts:
            proposal_hash = maker_result.artifacts[0].branch_name.split("-")[-1]
        
        if connector_result.shipped:
            status = "SHIPPED"
            summary = f"Proposals shipped: {connector_result.artifacts_shipped} artifact(s)"
            details = connector_result.message
            needs_human = connector_result.needs_human
        else:
            status = "CONNECTOR_SKIPPED"
            summary = "Connector did not ship (idempotent or failed)"
            details = connector_result.message
            needs_human = connector_result.needs_human
        
        # Build log entry with proposal info
        proposal_info = None
        if maker_result.artifacts:
            proposal_info = f"{len(maker_result.artifacts)} proposal(s): " + ", ".join(
                f"{a.change_type} {a.target_file}" for a in maker_result.artifacts
            )
        
        result_info = None
        if connector_result.shipped:
            result_info = f"Branch: {connector_result.branch_name}"
            if connector_result.pr_url:
                result_info += f", PR: {connector_result.pr_url}"
        
        log_entry = format_dream_log_entry(
            status=status,
            summary=summary,
            details=details,
            proposal=proposal_info,
            result=result_info,
        )
        
        updated_log = append_dream_log(
            timestamp=now,
            status=status,
            summary=summary,
            details=details,
            proposal=proposal_info,
            result=result_info,
        )
        
        write_dream_state(
            last_run=now,
            last_analyzed_date=skill_result.analyzed_until or last_analyzed or "",
            last_proposal_hash=proposal_hash,
            budget=dream_state.budget,
            log_entries=updated_log,
        )
        
        print(f"DONE: {log_entry}", file=sys.stderr)
        
        if needs_human:
            return 2  # Special exit code for NEEDS HUMAN (non-fatal)
        
        return 0
    
    except Exception as e:
        from datetime import datetime
        now = datetime.now().isoformat(timespec="seconds")
        
        log_entry = format_dream_log_entry(
            status="ERROR",
            summary=f"Unexpected error: {type(e).__name__}",
            details=str(e),
            needs_human=True,
        )
        updated_log = append_dream_log(
            timestamp=now,
            status="ERROR",
            summary=f"Unexpected error: {type(e).__name__}",
            details=str(e),
        )
        write_dream_state(
            last_run=now,
            last_analyzed_date=last_analyzed or "",
            last_proposal_hash=None,
            budget=dream_state.budget,
            log_entries=updated_log,
        )
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


def main() -> int:
    """Entry point."""
    return run_pass()


if __name__ == "__main__":
    sys.exit(main())