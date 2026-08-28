"""Loop body for Loop Engineering Practice Project 3.

Runs exactly ONE pass per invocation:
  1. read progress.md (the spine / persistent memory)
  2. ask git for commits newer than last_seen_commit
  3. write a short summary and update progress.md

No infinite or internal while loop: each run of this script is one pass,
and the schedule is what repeats it.
"""

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "progress.md"

STATE_HEADER_RE = re.compile(r"(?m)^## State *$")
LOG_HEADER_RE = re.compile(r"(?m)^## Log *$")


def read_state(path):
    state = {"last_seen_commit": None, "last_run": None}
    if not path.exists():
        return state
    text = path.read_text(encoding="utf-8")
    for key in state:
        match = re.search(rf"(?m)^- {key}:\s*(.*)$", text)
        if match and match.group(1).strip():
            state[key] = match.group(1).strip()
    return state


def get_commits(cursor, repo_dir):
    spec = f"{cursor}..HEAD" if cursor else "HEAD"
    result = subprocess.run(
        ["git", "log", "--format=%h|%ad|%s", "--date=short", spec],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(
                {"hash": parts[0], "date": parts[1], "subject": parts[2]}
            )
    return commits


def format_summary(cursor, commits):
    described = ", ".join(f"{c['hash']} {c['subject']}" for c in commits)
    if cursor is None:
        return f"First run. Found {len(commits)} commit(s): {described}"
    if not commits:
        return f"No new commits since {cursor}."
    return (
        f"Found {len(commits)} new commit(s) since {cursor}: {described}"
    )


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


def update_progress(path, state, summary):
    today = datetime.date.today().isoformat()
    text = path.read_text(encoding="utf-8") if path.exists() else "# Progress\n\n## State\n\n## Log\n"
    text = set_field(text, "last_seen_commit", state["last_seen_commit"])
    text = set_field(text, "last_run", today)
    entry = f"\n### {today}\n{summary}\n"
    text = text.rstrip() + entry
    path.write_text(text, encoding="utf-8")


def run_pass(progress_path, repo_dir):
    state = read_state(progress_path)
    cursor = state["last_seen_commit"]
    commits = get_commits(cursor, repo_dir)
    if commits:
        state["last_seen_commit"] = commits[0]["hash"]
    summary = format_summary(cursor, commits)
    update_progress(progress_path, state, summary)
    return cursor, summary


def main():
    try:
        cursor, summary = run_pass(PROGRESS, ROOT)
        print(summary)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
