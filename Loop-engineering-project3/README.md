# Loop Engineering Practice Project 3

> A scheduled loop runs once, reads its own memory, gathers something new,
> writes a short summary, and remembers what it found.

## Goal

Practice an **unattended schedule** (Concept 6) and the **spine / persistent
memory** (Concept 12). The repository information source is **Git commit
history**. Each scheduled run does exactly ONE pass: no infinite loop, no
"am I done?" check — the schedule is the loop.

## Files

| File                  | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `progress.md`         | The spine. The only thing that persists between runs.          |
| `src/loop.py`         | The loop body. Runs one pass per invocation.                   |
| `loop.cmd`            | Unattended entry point. Runs the loop once, propagates exit code. |
| `tests/test_progress.py` | Verifies the deduplication logic against a real temp git repo. |
| `README.md`           | This file.                                                     |

Only the Python standard library and Git are used. No dependencies to install.

## Concept 6: unattended scheduled execution

The loop is the **schedule**, not an internal `while`. `loop.cmd` invokes
`src/loop.py` exactly once and returns its exit code (`0` = ok, non-zero =
failure). Windows Task Scheduler fires the command on a timer; nobody has to
be present. Everything the run learns is written into `progress.md`, so a
run is self-contained and leaves a trace even when nobody watches.

## Concept 12: progress.md as the spine

`progress.md` is the single persistent memory. It stores:

- `last_seen_commit` — the cursor: the newest commit already recorded.
- `last_run` — the date of the most recent run.
- an append-only `## Log` of short, dated summaries.

```
# Progress
## State
- last_seen_commit: 1ffedfe
- last_run: 2026-08-16

## Log
### 2026-08-16
First run. Found 2 commit(s): 887206b added, 1ffedfe project-2
```

Every run starts by reading the spine and ends by rewriting it. That is the
persistent memory: nothing is kept in the agent's head, everything is in the
file.

## First run

`progress.md` has no `last_seen_commit`, so the cursor is empty:

1. `src/loop.py` runs `git log` on `HEAD` — the whole history.
2. Every commit is "new".
3. A short summary is written and appended to the `## Log`.
4. `last_seen_commit` is set to the newest commit (the top of `git log`).
5. `last_run` is set to today's date.

## Second run

The spine is read first, so the cursor is `last_seen_commit` from run 1.

1. `src/loop.py` runs `git log <last_seen_commit>..HEAD`.
2. Git itself returns **only commits newer than the cursor**.
3. The summary mentions only those new commits — never the ones already
   recorded.
4. If nothing is newer, the entry is exactly: `No new commits since <cursor>`.
5. `last_seen_commit` advances only if new commits were found;
   `last_run` is always updated.

## How the cursor prevents repetition

`git log <cursor>..HEAD` means "every commit reachable from `HEAD` but not
from `cursor`". A commit that was already recorded is reachable from the
cursor, so it can never appear again. The cursor moves forward monotonically,
so each run builds on — never repeats — the runs before it.

## Run the loop manually

From the project folder:

```
loop.cmd
```

or directly:

```
python src\loop.py
```

Each invocation is exactly one pass and prints its summary to the console
while also appending it to `progress.md`.

## Schedule it on Windows (Task Scheduler)

```
schtasks /create /sc daily /tn "loop-project3" ^
  /tr "F:\Loop-practice-projects\Loop-engineering-project3\loop.cmd"
```

`/sc daily` fires the task once per day; change it to `/sc hourly` or a
`/st` start time as needed. Remove it with
`schtasks /delete /tn "loop-project3" /f`. Because `loop.cmd` runs one pass
and exits, rescheduling or a missed trigger is harmless — the next run just
starts from the cursor stored in `progress.md`.
