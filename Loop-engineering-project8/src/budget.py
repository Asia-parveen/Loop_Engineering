"""Budget / Token Guards for Loop Engineering Practice Project 8.

Provides clear maximum token/cost limits per run with enforcement.
Tracks actual vs estimated usage and escalates to NEEDS HUMAN if exceeded.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BudgetConfig:
    """Budget configuration with hard limits."""
    max_tokens_per_run: int = 5000
    token_price_per_1k: float = 0.0015
    max_cost_per_run_usd: float = 0.0075
    warn_threshold_pct: float = 0.8  # Warn at 80% of budget


@dataclass(frozen=True)
class BudgetResult:
    """Result of a budget check."""
    allowed: bool
    tokens_used: int
    tokens_remaining: int
    cost_usd: float
    cost_remaining_usd: float
    warning: Optional[str] = None
    error: Optional[str] = None


# Default budget from progress.md or environment
DEFAULT_BUDGET = BudgetConfig()


def load_budget_from_env() -> BudgetConfig:
    """Load budget configuration from environment variables."""
    return BudgetConfig(
        max_tokens_per_run=int(os.environ.get("LOOP_MAX_TOKENS", "5000")),
        token_price_per_1k=float(os.environ.get("LOOP_TOKEN_PRICE", "0.0015")),
        max_cost_per_run_usd=float(os.environ.get("LOOP_MAX_COST_USD", "0.0075")),
        warn_threshold_pct=float(os.environ.get("LOOP_WARN_THRESHOLD", "0.8")),
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token (conservative)."""
    return max(1, len(text) // 4)


def calculate_cost(tokens: int, price_per_1k: float) -> float:
    """Calculate cost in USD for given tokens."""
    return (tokens / 1000.0) * price_per_1k


def check_budget(
    estimated_tokens: int,
    config: Optional[BudgetConfig] = None,
    actual_tokens: Optional[int] = None,
) -> BudgetResult:
    """Check if estimated tokens are within budget."""
    if config is None:
        config = DEFAULT_BUDGET

    tokens_to_check = actual_tokens if actual_tokens is not None else estimated_tokens
    cost = calculate_cost(tokens_to_check, config.token_price_per_1k)
    tokens_remaining = max(0, config.max_tokens_per_run - tokens_to_check)
    cost_remaining = max(0.0, config.max_cost_per_run_usd - cost)

    warning = None
    error = None
    allowed = True

    # Check hard limits
    if tokens_to_check > config.max_tokens_per_run:
        allowed = False
        error = (
            f"TOKEN BUDGET EXCEEDED: {tokens_to_check} > {config.max_tokens_per_run} "
            f"(max tokens per run)"
        )
    elif cost > config.max_cost_per_run_usd:
        allowed = False
        error = (
            f"COST BUDGET EXCEEDED: ${cost:.6f} > ${config.max_cost_per_run_usd:.6f} "
            f"(max cost per run)"
        )
    # Check warning threshold
    elif tokens_to_check >= config.max_tokens_per_run * config.warn_threshold_pct:
        warning = (
            f"BUDGET WARNING: {tokens_to_check} tokens "
            f"({tokens_to_check / config.max_tokens_per_run * 100:.0f}% of limit)"
        )
    elif cost >= config.max_cost_per_run_usd * config.warn_threshold_pct:
        warning = (
            f"COST WARNING: ${cost:.6f} "
            f"({cost / config.max_cost_per_run_usd * 100:.0f}% of limit)"
        )

    return BudgetResult(
        allowed=allowed,
        tokens_used=tokens_to_check,
        tokens_remaining=tokens_remaining,
        cost_usd=cost,
        cost_remaining_usd=cost_remaining,
        warning=warning,
        error=error,
    )


def format_budget_report(result: BudgetResult) -> str:
    """Format a human-readable budget report."""
    lines = [
        f"Budget Report:",
        f"  Tokens used: {result.tokens_used} / {result.tokens_used + result.tokens_remaining}",
        f"  Cost: ${result.cost_usd:.6f} / ${result.cost_usd + result.cost_remaining_usd:.6f}",
        f"  Remaining tokens: {result.tokens_remaining}",
        f"  Remaining cost: ${result.cost_remaining_usd:.6f}",
        f"  Status: {'ALLOWED' if result.allowed else 'DENIED'}",
    ]
    if result.warning:
        lines.append(f"  WARNING: {result.warning}")
    if result.error:
        lines.append(f"  ERROR: {result.error}")
    return "\n".join(lines)


class BudgetExceededError(Exception):
    """Raised when budget is exceeded and run must stop."""
    def __init__(self, result: BudgetResult):
        self.result = result
        super().__init__(result.error or "Budget exceeded")


def enforce_budget(
    estimated_tokens: int,
    config: Optional[BudgetConfig] = None,
    actual_tokens: Optional[int] = None,
) -> BudgetResult:
    """Check budget and raise if exceeded."""
    result = check_budget(estimated_tokens, config, actual_tokens)
    if not result.allowed:
        raise BudgetExceededError(result)
    return result


if __name__ == "__main__":
    # Demo
    config = load_budget_from_env()
    print(f"Budget Config: {config}")
    print()

    test_cases = [100, 1000, 4000, 5000, 6000]
    for tokens in test_cases:
        result = check_budget(tokens, config)
        print(format_budget_report(result))
        print()