"""Worktree — Isolated Workspace for Loop Engineering Practice Project 8.

The worktree provides a clean, isolated directory for the maker to produce
changes and the checker to validate them. It is separate from the main
repository working tree to prevent accidental pollution.

Key properties:
- Created fresh each run (or reused with clean slate)
- Automatically cleaned up on success or explicit request
- Never modifies the main repo directly
- Path is configurable via environment or defaults to .worktree/<run_id>
"""

import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class WorktreeConfig:
    """Configuration for the isolated worktree."""
    base_dir: Path
    run_id: str
    keep_on_failure: bool = True
    keep_on_success: bool = False


class Worktree:
    """Manages an isolated workspace directory."""

    def __init__(self, config: WorktreeConfig):
        self.config = config
        self.path = config.base_dir / config.run_id
        self._created = False

    def create(self) -> Path:
        """Create the worktree directory."""
        self.path.mkdir(parents=True, exist_ok=True)
        self._created = True
        return self.path

    def cleanup(self) -> None:
        """Remove the worktree directory."""
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> Path:
        return self.create()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        should_keep = (
            (exc_type is not None and self.config.keep_on_failure) or
            (exc_type is None and self.config.keep_on_success)
        )
        if not should_keep:
            self.cleanup()


def get_worktree_base_dir() -> Path:
    """Get the base directory for worktrees from environment or default."""
    env_base = os.environ.get("LOOP_WORKTREE_BASE")
    if env_base:
        return Path(env_base).resolve()
    # Default to .worktree in project root
    project_root = Path(__file__).resolve().parent.parent
    return project_root / ".worktree"


def generate_run_id() -> str:
    """Generate a unique run identifier."""
    return f"run-{uuid.uuid4().hex[:8]}"


@contextmanager
def isolated_worktree(
    run_id: Optional[str] = None,
    base_dir: Optional[Path] = None,
    keep_on_failure: bool = True,
    keep_on_success: bool = False,
) -> Path:
    """Context manager for an isolated worktree.

    Yields the worktree path. Cleans up on exit unless keep flags are set.
    """
    if run_id is None:
        run_id = generate_run_id()
    if base_dir is None:
        base_dir = get_worktree_base_dir()

    config = WorktreeConfig(
        base_dir=base_dir,
        run_id=run_id,
        keep_on_failure=keep_on_failure,
        keep_on_success=keep_on_success,
    )
    wt = Worktree(config)
    with wt:
        yield wt.path


def list_worktrees(base_dir: Optional[Path] = None) -> list:
    """List existing worktree directories."""
    if base_dir is None:
        base_dir = get_worktree_base_dir()
    if not base_dir.exists():
        return []
    return sorted([d for d in base_dir.iterdir() if d.is_dir()])


def clean_old_worktrees(base_dir: Optional[Path] = None, max_age_days: int = 7) -> int:
    """Remove worktrees older than max_age_days. Returns count removed."""
    import time
    if base_dir is None:
        base_dir = get_worktree_base_dir()
    if not base_dir.exists():
        return 0

    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for wt_dir in base_dir.iterdir():
        if wt_dir.is_dir():
            try:
                mtime = wt_dir.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(wt_dir, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return removed


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        removed = clean_old_worktrees()
        print(f"Cleaned {removed} old worktrees")
    else:
        base = get_worktree_base_dir()
        print(f"Worktree base: {base}")
        for wt in list_worktrees(base):
            print(f"  {wt.name}")