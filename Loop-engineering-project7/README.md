# Loop Engineering Practice Project 7

> **Sabotage Your Own Loop, Then Diagnose It From the Spine Alone.**

## Goal

Practice **intentional failure injection**, **single-attempt execution**, and
**spine-only diagnosis**. The loop is sabotaged by reading a non-existent file.
It fails once, logs everything needed for diagnosis to `progress.md`, and exits
non-zero. No retries. The schedule (external) would repeat it, but the human
must intervene — `NEEDS HUMAN` is recorded.

## Files

| File                  | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `progress.md`         | The spine. Persistent memory; contains all diagnostic info.    |
| `src/loop.py`         | The loop body. Runs one pass per invocation.                   |
| `loop.cmd`            | Unattended entry point. Runs the loop once, propagates exit code. |
| `tests/test_loop.py`  | Verifies sabotage, single attempt, non-silent failure, etc.    |
| `README.md`           | This file.                                                     |

Only the Python standard library is used. No dependencies to install.

## Concept: Intentional Sabotage & Spine-Only Diagnosis

The loop **intentionally** attempts to read a file that does not exist:
`nonexistent_sabotage_file.txt`. This is not a bug — it is the exercise.

On failure:
- Exit code is **non-zero** (1).
- Failure is **not silent** — error printed to stderr.
- A **timestamped log entry** is appended to `progress.md` containing:
  - **What failed**: "Sabotage triggered — attempted to read non-existent file..."
  - **Why it failed**: The `FileNotFoundError` exception message.
  - **Attempt**: `1/1` (max attempts = 1).
  - **NEEDS HUMAN** — explicit escalation marker.

The failure is **diagnosable from `progress.md` alone** — no replay, no external
logs needed. The spine holds:
- `last_run` — ISO timestamp of the run.
- `attempt` — always `1` (max).
- `last_error` — the exception string.
- `## Log` — the full human-readable entry.

## One Pass Per Invocation

`src/loop.py` has **no internal loop**. `run_pass()` executes exactly once.
The schedule (Windows Task Scheduler firing `loop.cmd`) is the loop.

## Run the Loop Manually

From the project folder:

```
loop.cmd
```

or directly:

```
python src\loop.py
```

Each invocation is exactly one pass, prints its result (or error) to console,
and appends to `progress.md`. The exit code is `1` on sabotage failure.

## Schedule It on Windows (Task Scheduler)

```
schtasks /create /sc daily /tn "loop-project7" ^
  /tr "F:\Loop-practice-projects\Loop-engineering-project7\loop.cmd"
```

`/sc daily` fires once per day. Remove with
`schtasks /delete /tn "loop-project7" /f`.

Because each run is one pass and exits, rescheduling or a missed trigger is
harmless — the next run starts from the spine in `progress.md`.

## Token & Cost Estimation

### Tokens Per Run

| Operation                     | Est. Tokens |
|-------------------------------|-------------|
| Read `progress.md` (~300 chars) | ~75        |
| Write `progress.md` (~500 chars) | ~125       |
| stdout/stderr output            | ~50        |
| **Total per run**               | **~250**   |

### Cadence

**Daily** (1 run per day) — matches the recommended Task Scheduler setting.

### Monthly Token Usage

- Runs per month: 30
- Tokens per run: 250
- **Monthly tokens: ~7,500**

### Assumed Token Price

- **$0.0015 per 1,000 tokens** (representative small-model pricing, 2026).

### Monthly Cost

```
7,500 tokens × ($0.0015 / 1,000 tokens) = $0.01125 ≈ 1.1¢ per month
```

Even at 10× price ($0.015/1k), cost is ~11¢/month. Negligible.

## Verification Checklist

After running the sabotaged loop once:
1. Exit code is **1** (non-zero).
2. `progress.md` contains a log entry with:
   - Timestamp (ISO format).
   - "FAILED: Sabotage triggered..."
   - "Reason: [FileNotFoundError: ...]"
   - "Attempt: 1/1"
   - "NEEDS HUMAN"
3. State fields updated: `last_run`, `attempt: 1`, `last_error: FileNotFoundError: ...`
4. Failure is diagnosable from `progress.md` alone — no replay needed.
5. Tests pass (`python -m pytest tests/` or `python -m unittest tests.test_loop`).
6. Projects 1–6 remain untouched (this is Project 7 only).