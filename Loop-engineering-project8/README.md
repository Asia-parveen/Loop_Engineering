# Loop Engineering Practice Project 8 — The Capstone: Full Six-Part Loop

> A complete, production-style unattended loop demonstrating all six parts on a real, safe chore: **Changelog Draft Generation** from Git commit history.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SCHEDULER                           │
│                     (Windows Task Scheduler)                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ fires loop.cmd (one pass)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         HEARTBEAT (Part 1)                          │
│  Cadence: daily • Timeout: 300s • One-pass per invocation           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           SPINE (Part 6)                            │
│  progress.md — Persistent memory: cursor, budget, log, state        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  WORKTREE   │    │   SKILL     │    │   BUDGET    │
    │   (Part 2)  │    │   (Part 3)  │    │  (Guard)    │
    │ Isolated    │    │ Documented  │    │ 5000 tokens │
    │ workspace   │    │ procedure   │    │ $0.0075/run │
    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌─────────────────────────────────────────────────┐
    │              MAKER (Part 4)                     │
    │  Executes skill → produces CHANGELOG.draft.md   │
    │  Budget checked BEFORE writing                  │
    └────────────────────┬────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────────────┐
    │              CHECKER (Part 5)                   │
    │  Validates: structure, commits, size, safety    │
    │  MUST PASS before connector runs                │
    └────────────────────┬────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────────────┐
    │            CONNECTOR (Part 6)                   │
    │  Git branch + optional PR (no auto-merge)       │
    │  NEEDS HUMAN for review/merge                   │
    └─────────────────────────────────────────────────┘
```

## Chosen Chore: Changelog Draft Generation

**Why this chore?**
- **Safe**: Read-only Git operations; writes only to isolated worktree
- **Boring**: No business logic, no external APIs, no secrets
- **Valuable**: Real projects need changelogs; draft saves human time
- **Idempotent**: Same cursor → same output; deduplication via content hash
- **Observable**: Clear input (commits), output (draft), decision (ship/skip)

## Six Parts Implementation

### 1. HEARTBEAT — `src/heartbeat.py`
- **Cadence**: Daily (configurable: `LOOP_CADENCE=manual|daily|hourly`)
- **Timeout**: 300 seconds hard limit (`LOOP_TIMEOUT_SECONDS`)
- **One-pass**: No internal loop; external scheduler is the loop
- **Entry point**: `loop.cmd` → `python src/loop.py`

### 2. WORKTREE — `src/worktree.py`
- Isolated directory: `.worktree/run-<uuid>/`
- Created fresh each run; cleaned up on success
- Kept on failure for forensic inspection (`keep_on_failure=True`)
- Never touches main repository working tree

### 3. SKILL — `src/skill.py`
Documented, deterministic procedure:
```
1. Validate inputs (git repo, writable worktree)
2. Fetch commits: git log --format="%h|%ad|%s" <cursor>..HEAD
3. Group by date, format as markdown
4. Write to worktree/CHANGELOG.md
5. Return commits, content, new cursor, token estimate
```
- Max 100 commits/run safety cap
- No randomness, no external calls

### 4. MAKER — `src/maker.py`
- Creates worktree, runs skill, checks budget **before** writing
- Returns `MakerResult` with worktree path, changelog path, skill result, budget result
- Fails fast on budget exceed (cleanup worktree)

### 5. CHECKER — `src/checker.py`
Validates maker output **before any shipping**:
| Check | Purpose |
|-------|---------|
| File exists | Output was written |
| Non-empty | Not blank |
| Valid markdown | Header + date sections |
| Date headers | Descending order (newest first) |
| Commit references | All fetched commits appear |
| Size limit | < 100 KB |
| No destructive content | No `rm -rf`, `git push --force`, etc. |

### 6. CONNECTOR — `src/connector.py`
- Creates branch `changelog-draft/<hash>` 
- Commits `CHANGELOG.draft.md` (not `CHANGELOG.md` — safe name)
- Pushes to origin
- Optionally creates PR via `gh` CLI (disabled by default)
- **Never auto-merges** — human review required
- Idempotent: skips if branch exists

### SPINE (Persistent Memory) — `src/spine.py` + `progress.md`
```
## State
- last_run: 2026-08-29T14:30:00
- last_seen_commit: abc1234
- last_changelog_hash: deadbeef
- last_budget_used: 1234
- last_status: SHIPPED

## Budget
- max_tokens_per_run: 5000
- token_price_per_1k: 0.0015
- max_cost_per_run_usd: 0.0075

## Log
### 2026-08-29T14:30:00
STATUS: SHIPPED
Summary: Changelog draft shipped: changelog-draft/deadbeef
Details: Created branch changelog-draft/deadbeef (PR creation skipped - needs human)
NEEDS HUMAN
```

## Budget Guards

| Parameter | Value | Source |
|-----------|-------|--------|
| Max tokens/run | 5,000 | `LOOP_MAX_TOKENS` |
| Token price | $0.0015/1k | `LOOP_TOKEN_PRICE` |
| Max cost/run | $0.0075 | `LOOP_MAX_COST_USD` |
| Warning threshold | 80% | `LOOP_WARN_THRESHOLD` |

**Enforcement**: Maker calls `check_budget()` before writing; raises `BudgetExceededError` if over. Run exits with code 1, logs `BUDGET_EXCEEDED` + `NEEDS HUMAN`.

**Monthly estimate (daily)**: 30 runs × 5,000 tokens × $0.0015/1k = **$0.225/month** (negligible)

## NEEDS HUMAN Escalation

The loop records `NEEDS HUMAN` in `progress.md` and exits non-zero for:

| Condition | Exit Code | Log Status |
|-----------|-----------|------------|
| Checker validation failed | 1 | `CHECKER_FAILED` |
| Budget exceeded | 1 | `BUDGET_EXCEEDED` |
| Timeout (5 min) | 1 | `TIMEOUT` |
| Unexpected exception | 1 | `ERROR` |
| Connector shipped but no PR | 2 | `SHIPPED` + `NEEDS HUMAN` |
| Connector failed | 1 | `CONNECTOR_FAILED` |

**Exit codes**: `0=OK`, `1=FAILURE (needs human)`, `2=SHIPPED BUT NEEDS HUMAN REVIEW`

## Observability / Logging

- **Console (stderr)**: Real-time structured logs per phase
- **Spine (progress.md)**: Complete audit trail with timestamps
- **Worktree**: Preserved on failure for inspection
- **Git history**: Branch + commits traceable

Example stderr:
```
Starting run (cursor: abc1234)
  CHECK: File exists: Changelog file exists
  CHECK: Valid markdown structure (3 date sections)
  CHECK: All 5 commits referenced
  CHECK: Changelog size OK (12.3 KB <= 100 KB)
  CHECK: No destructive content detected
DONE: STATUS: SHIPPED
Summary: Changelog draft shipped: changelog-draft/deadbeef
Details: Created branch changelog-draft/deadbeef (PR creation skipped - needs human)
NEEDS HUMAN
```

## One-Pass Execution

`src/loop.py:run_pass()` executes **exactly once**:
- No `while True`, no `for` loops over runs
- Reads spine → executes 6 parts → writes spine → exits
- Windows Task Scheduler provides the loop cadence

## Schedule (External)

**Windows Task Scheduler (Daily at 2 AM):**
```cmd
schtasks /create /sc daily /tn "loop-project8" ^
  /tr "F:\Loop-practice-projects\Loop-engineering-project8\loop.cmd" /st 02:00 /f
```

**Hourly:**
```cmd
schtasks /create /sc hourly /tn "loop-project8" ^
  /tr "F:\Loop-practice-projects\Loop-engineering-project8\loop.cmd" /f
```

**Remove:**
```cmd
schtasks /delete /tn "loop-project8" /f
```

**Manual run:**
```cmd
loop.cmd
# or
python src\loop.py
```

## Recovery Process

### 1. Check Spine First
```cmd
type progress.md
```
Look at `last_status`, `last_error`, `last_run`, `NEEDS HUMAN` entries.

### 2. Common Scenarios

| Scenario | Diagnosis | Recovery |
|----------|-----------|----------|
| `CHECKER_FAILED` | Changelog validation failed | Inspect worktree (`.worktree/run-*/CHANGELOG.md`), fix skill/checker, re-run |
| `BUDGET_EXCEEDED` | Too many commits/large changelog | Increase `LOOP_MAX_TOKENS` or reduce `max_commits` in skill |
| `TIMEOUT` | Git operations hung | Check network/git remote, increase `LOOP_TIMEOUT_SECONDS` |
| `CONNECTOR_FAILED` | Push/PR failed | Check git remote auth, branch conflicts, `gh` CLI |
| `SHIPPED` + `NEEDS HUMAN` | Draft ready for review | Review `changelog-draft/*` branch, merge manually |

### 3. Manual Re-run
```cmd
# After fixing root cause
loop.cmd
```

### 4. Cursor Reset (if needed)
Edit `progress.md`:
```
- last_seen_commit: <new-cursor-or-empty>
- last_changelog_hash: 
```
Next run will reprocess from new cursor.

### 5. Clean Stale Worktrees
```cmd
python src\worktree.py clean
```

## Testing

Run all tests:
```cmd
python -m pytest tests/ -v
# or
python -m unittest tests.test_loop -v
```

Test categories:
- `TestSpine` — persistence, state, log formatting
- `TestHeartbeat` — cadence, timeout config
- `TestWorktree` — isolation, cleanup, failure preservation
- `TestBudget` — limits, warnings, enforcement
- `TestSkill` — commit fetching, changelog building, deduplication
- `TestMakerChecker` — maker produces, checker validates
- `TestConnector` — branch creation, push, PR (mock)
- `TestFullLoop` — integration: first run, incremental run
- `TestLoopCmd` — entry point executes
- `TestSafetyGuards` — no auto-merge, no destructive ops, budget in maker, checker before connector
- `TestObservability` — logging, timestamps, append-only log

## Files Created

```
Loop-engineering-project8/
├── progress.md              # SPINE - persistent memory
├── loop.cmd                 # Entry point (Windows)
├── README.md                # This file
├── src/
│   ├── __init__.py
│   ├── spine.py             # Part 6: Progress management
│   ├── heartbeat.py         # Part 1: Cadence, timeout
│   ├── worktree.py          # Part 2: Isolated workspace
│   ├── budget.py            # Guard: Token/cost limits
│   ├── skill.py             # Part 3: Documented procedure
│   ├── maker.py             # Part 4: Produces changes
│   ├── checker.py           # Part 5: Validates changes
│   ├── connector.py         # Part 6: Git/GitHub integration
│   └── loop.py              # Main orchestration
└── tests/
    └── test_loop.py         # Comprehensive test suite
```

## One-Week Unattended Monitoring

### Daily Automated Checks
1. **Task Scheduler History**: Verify `loop-project8` task ran daily (Event Viewer → Task Scheduler)
2. **Spine Log**: `progress.md` should have 7 new `### <date>` entries
3. **Exit Codes**: Task Scheduler shows `0`, `1`, or `2` (not hung)

### Weekly Human Review
1. **Open `progress.md`** — scan for `NEEDS HUMAN`, `ERROR`, `TIMEOUT`, `BUDGET_EXCEEDED`
2. **Check GitHub** — review any `changelog-draft/*` branches/PRs
3. **Verify Budget** — `last_budget_used` should be < 5000 tokens
4. **Clean Worktrees** — run `python src/worktree.py clean` if disk space concern

### Alerting (Manual)
If any run shows `NEEDS HUMAN` in log:
- Check the dated log entry for `Details:`
- Follow Recovery Process above
- Re-run manually after fix

## Safety Guarantees

✅ **No destructive changes** — only reads Git, writes isolated worktree  
✅ **No auto-merge/publish** — connector creates branch/PR only  
✅ **Maker output passes checker** — connector never runs if checker fails  
✅ **Budget enforced** — hard limits with NEEDS HUMAN escalation  
✅ **Timeout guard** — 5-minute max, never hangs indefinitely  
✅ **Failures not silent** — stderr + progress.md + non-zero exit  
✅ **Idempotent** — same cursor → same output; duplicate detection via hash  
✅ **Auditable** — complete trace in progress.md  

## License

Loop Engineering Practice — Educational/Reference Implementation