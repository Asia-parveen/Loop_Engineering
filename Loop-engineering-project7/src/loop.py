"""Loop body for Loop Engineering Practice Project 7.

Runs exactly ONE pass per invocation:
  1. Read progress.md (the spine / persistent memory)
  2. Attempt to read a non-existent file (intentional sabotage)
  3. On failure, log the failure with timestamp, reason, attempt, and NEEDS HUMAN
  4. Exit with non-zero code

No infinite or internal while loop: each run of this script is one pass,
and the schedule is what repeats it.
"""

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "progress.md"
SABOTAGE_FILE = ROOT / "nonexistent_sabotage_file.txt"
MAX_ATTEMPTS = 1

STATE_HEADER_RE = re.compile(r"(?m)^## State *$")
LOG_HEADER_RE = re.compile(r"(?m)^## Log *$")


def read_state(path):
    state = {"last_run": None, "last_error": None}
    if not path.exists():
        return state
    text = path.read_text(encoding="utf-8")
    for key in state:
        match = re.search(rf"(?m)^- {key}:\s*(.*)$", text)
        if match and match.group(1).strip():
            state[key] = match.group(1).strip()
    return state


def set_field(text, key, value):
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


def update_progress(path, state, log_entry):
    today = datetime.datetime.now().isoformat(timespec="seconds")
    text = path.read_text(encoding="utf-8") if path.exists() else "# Progress\n\n## State\n\n## Log\n"
    text = set_field(text, "last_run", today)
    text = set_field(text, "last_error", state["last_error"])
    entry = f"\n### {today}\n{log_entry}\n"
    text = text.rstrip() + entry
    path.write_text(text, encoding="utf-8")


def run_pass(progress_path):
    state = read_state(progress_path)
    attempt = 1  # Always 1 per invocation

    try:
        with open(SABOTAGE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError as exc:
        state["last_error"] = f"FileNotFoundError: {exc}"
        log_entry = (
            f"FAILED: Sabotage triggered — attempted to read non-existent file '{SABOTAGE_FILE.name}'\n"
            f"Reason: {exc}\n"
            f"Attempt: {attempt}/{MAX_ATTEMPTS}\n"
            f"NEEDS HUMAN"
        )
        update_progress(progress_path, state, log_entry)
        print(f"error: {log_entry}", file=sys.stderr)
        return 1

    log_entry = f"SUCCESS: Read file content ({len(content)} chars)"
    update_progress(progress_path, state, log_entry)
    print(log_entry)
    return 0


def main():
    return run_pass(PROGRESS)


if __name__ == "__main__":
    sys.exit(main())