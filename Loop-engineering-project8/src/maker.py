"""Maker — Produces Changes for Loop Engineering Practice Project 8.

The maker executes the skill to produce a changelog draft in the isolated
worktree. It does NOT validate, ship, or merge — only produces.

Output: A draft CHANGELOG.md in the worktree, plus metadata for the checker.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .skill import SkillConfig, SkillResult, execute_skill
from .budget import BudgetConfig, check_budget, BudgetExceededError
from .worktree import Worktree, WorktreeConfig, generate_run_id


@dataclass(frozen=True)
class MakerConfig:
    """Configuration for the maker."""
    repo_root: Path
    worktree_base: Path
    cursor_commit: Optional[str]
    budget: BudgetConfig
    max_commits: int = 100


@dataclass(frozen=True)
class MakerResult:
    """Result of the maker phase."""
    worktree_path: Path
    changelog_path: Path
    skill_result: SkillResult
    budget_result: 'BudgetResult'
    run_id: str


from .budget import BudgetResult  # forward reference resolved


def run_maker(config: MakerConfig) -> MakerResult:
    """Execute the maker phase: produce changelog draft in isolated worktree."""
    run_id = generate_run_id()

    # Create isolated worktree
    worktree_config = WorktreeConfig(
        base_dir=config.worktree_base,
        run_id=run_id,
        keep_on_failure=True,  # Keep for inspection on failure
        keep_on_success=False,  # Clean up on success (checker will re-create if needed)
    )
    worktree = Worktree(worktree_config)
    worktree_path = worktree.create()

    # Define output path
    changelog_path = worktree_path / "CHANGELOG.md"

    # Prepare skill config
    skill_config = SkillConfig(
        repo_root=config.repo_root,
        worktree_dir=worktree_path,
        changelog_path=changelog_path,
        cursor_commit=config.cursor_commit,
        max_commits=config.max_commits,
    )

    # Execute skill to produce draft
    skill_result = execute_skill(skill_config)

    # Check budget against estimated tokens
    budget_result = check_budget(skill_result.tokens_estimated, config.budget)
    if not budget_result.allowed:
        # Clean up worktree on budget failure
        worktree.cleanup()
        raise BudgetExceededError(budget_result)

    return MakerResult(
        worktree_path=worktree_path,
        changelog_path=changelog_path,
        skill_result=skill_result,
        budget_result=budget_result,
        run_id=run_id,
    )


if __name__ == "__main__":
    print("Maker module - not meant to run directly")