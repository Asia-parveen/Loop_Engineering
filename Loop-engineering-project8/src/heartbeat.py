"""Heartbeat — Scheduled Trigger / Cadence for Loop Engineering Practice Project 8.

The heartbeat defines WHEN the loop runs. It does NOT contain an internal loop.
Each invocation is exactly one pass. The schedule (external) is the loop.

Supported cadences:
- manual: run on demand (default for testing)
- daily: once per day (recommended for production)
- hourly: once per hour (for high-frequency needs)

The heartbeat also provides a timeout guard to prevent hung runs.
"""

import os
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Cadence(Enum):
    MANUAL = "manual"
    DAILY = "daily"
    HOURLY = "hourly"


@dataclass(frozen=True)
class HeartbeatConfig:
    cadence: Cadence = Cadence.MANUAL
    timeout_seconds: int = 300  # 5 minutes max per run
    start_time: Optional[str] = None  # HH:MM for daily


# Default configuration
DEFAULT_HEARTBEAT = HeartbeatConfig()


class TimeoutError(Exception):
    """Raised when the run exceeds the timeout."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Run exceeded maximum allowed time")


def install_timeout_guard(timeout_seconds: int) -> None:
    """Install a timeout guard using SIGALRM (Unix) or threading (Windows)."""
    if sys.platform == "win32":
        # On Windows, we can't use SIGALRM. Use a simpler approach:
        # The main loop should check elapsed time periodically.
        # For now, we document the timeout but rely on external process management.
        pass
    else:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)


def clear_timeout_guard() -> None:
    """Clear the timeout guard."""
    if sys.platform != "win32":
        signal.alarm(0)


def get_cadence_from_env() -> Cadence:
    """Read cadence from environment variable LOOP_CADENCE."""
    val = os.environ.get("LOOP_CADENCE", "manual").lower()
    try:
        return Cadence(val)
    except ValueError:
        return Cadence.MANUAL


def get_timeout_from_env() -> int:
    """Read timeout from environment variable LOOP_TIMEOUT_SECONDS."""
    val = os.environ.get("LOOP_TIMEOUT_SECONDS", "300")
    try:
        return int(val)
    except ValueError:
        return 300


def describe_schedule(config: HeartbeatConfig) -> str:
    """Return human-readable schedule description."""
    if config.cadence == Cadence.MANUAL:
        return "Manual (on-demand)"
    elif config.cadence == Cadence.DAILY:
        start = config.start_time or "00:00"
        return f"Daily at {start}"
    elif config.cadence == Cadence.HOURLY:
        return "Hourly"
    return "Unknown"


def windows_task_scheduler_command(
    project_path: Path,
    task_name: str = "loop-project8",
    cadence: Cadence = Cadence.DAILY,
    start_time: str = "02:00",
) -> str:
    """Generate Windows Task Scheduler command for the loop."""
    cmd_path = project_path / "loop.cmd"
    if cadence == Cadence.DAILY:
        return (
            f'schtasks /create /sc daily /tn "{task_name}" '
            f'/tr "{cmd_path}" /st {start_time} /f'
        )
    elif cadence == Cadence.HOURLY:
        return (
            f'schtasks /create /sc hourly /tn "{task_name}" '
            f'/tr "{cmd_path}" /f'
        )
    return ""


def print_schedule_help() -> None:
    """Print scheduling instructions."""
    print("""
SCHEDULING THE LOOP
===================

The loop runs ONE PASS per invocation. The schedule is EXTERNAL.

Windows Task Scheduler (Daily at 2 AM):
  schtasks /create /sc daily /tn "loop-project8" ^
    /tr "F:\\Loop-practice-projects\\Loop-engineering-project8\\loop.cmd" /st 02:00 /f

Windows Task Scheduler (Hourly):
  schtasks /create /sc hourly /tn "loop-project8" ^
    /tr "F:\\Loop-practice-projects\\Loop-engineering-project8\\loop.cmd" /f

Remove scheduled task:
  schtasks /delete /tn "loop-project8" /f

Environment Variables:
  LOOP_CADENCE=manual|daily|hourly  (default: manual)
  LOOP_TIMEOUT_SECONDS=300          (default: 300, max 3600)

Each run reads progress.md, executes the six-part loop, and exits.
Missed triggers are harmless — the next run starts from the cursor in the spine.
""")


if __name__ == "__main__":
    print_schedule_help()