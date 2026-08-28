# Loop Engineering Practice Project 12 — Dream Loop

> A weekly improvement loop that analyzes Project 8's execution history,
> detects repeated failures, and proposes minimal fixes via PRs on `claude/` branches.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SCHEDULER                             │
│                     (Weekly - Windows Task)                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ fires loop.cmd (one pass)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DREAM SPINE (Part 1)                           │
│  dreaming-state.md — Persistent memory: last_run, analyzed_date    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DREAM SKILL (Part 2)                           │
│  Analyzes Project 8 progress.md for repeated failures              │
│  Detects patterns (>=2 occurrences), proposes minimal fixes        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DREAM MAKER (Part 3)                           │
│  Produces proposal artifacts (diff + PR description)               │
│  Budget checked BEFORE writing                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DREAM CHECKER (Part 4)                         │
│  Validates: evidence cited, minimal change, no direct mods,        │
│  branch naming (claude/fix-<hash> or claude/delete-<hash>)         │
│  MUST PASS before connector runs                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DREAM CONNECTOR (Part 5)                       │
│  Creates Git branch + optional PR on Project 8 repo                │
│  NEVER auto-merges — human review required                         │
│  Idempotent: skips if branch exists                                │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Principles

1. **Evidence-Based**: Every proposal MUST cite exact run dates, failure frequency, and details from Project 8's `progress.md`
2. **Minimal Changes**: Proposals are the SMALLEST possible fix (max 50 diff lines)
3. **PR Only**: NEVER modifies rules/skill files directly — only creates PRs on `claude/` branches
4. **Maker-Checker Gate**: Checker MUST pass before any connector action
5. **Human Review Required**: All PRs require human approval (no auto-merge)
6. **One Deletion Per Run**: Also proposes ONE outdated/unneeded rule removal with evidence
7. **Weekly Cadence**: Runs once per week, analyzes all entries since last run

## Evidence Source

Uses **Project 8's `progress.md`** as the single source of truth. The log shows:

```
### 2026-08-29T00:55:33
STATUS: CONNECTOR_SKIPPED
Summary: Connector did not ship (idempotent or failed)
Details: Failed to create branch
NEEDS HUMAN
### 2026-08-29T00:55:51
STATUS: CONNECTOR_SKIPPED
Summary: Connector did not ship (idempotent or failed)
Details: Failed to create branch
NEEDS HUMAN
... (5 total occurrences)
```

The Dream Loop detects this 5-time repeated `CONNECTOR_SKIPPED: Failed to create branch` pattern.

## Proposed Fix Example

For the connector branch creation failure, the Dream Loop proposes:

**File**: `src/connector.py`  
**Change**: Add fallback to local base branch when `origin/HEAD` fetch fails  
**Evidence**: "Failure 'CONNECTOR_SKIPPED: Connector did not ship' occurred 5 times on dates: 2026-08-29T00:55:33, 2026-08-29T00:55:51, 2026-08-29T00:56:48, 2026-08-29T00:58:11, 2026-08-29T00:58:43. Example: Failed to create branch"

**Diff**:
```diff
--- a/src/connector.py
+++ b/src/connector.py
@@ -74,7 +74,10 @@ def create_branch(repo_root: Path, branch_name: str, base_branch: Optional[str] = None) -> bool:
     """Create a new branch from base_branch."""
     if base_branch is None:
         base_branch = get_default_branch(repo_root)
-    # Fetch latest
+    # Fetch latest (with fallback if origin/HEAD not set)
     run_git(repo_root, "fetch", "origin", base_branch)
-    # Create branch
+    # Create branch - try with origin/base, fallback to local base
+    result = run_git(repo_root, "checkout", "-b", branch_name, f"origin/{base_branch}")
+    if result.returncode != 0:
+        result = run_git(repo_root, "checkout", "-b", branch_name, base_branch)
     return result.returncode == 0
```

**PR Branch**: `claude/fix-<hash>`  
**PR Title**: `Fix: Add fallback branch creation when origin/HEAD fetch fails`

## Deletion Proposal Example

Also proposes ONE deletion per run:

**File**: `src/budget.py`  
**Change**: Remove outdated hardcoded budget limit comment (now configurable via env)  
**Evidence**: "Budget limit 0.0075 is now fully configurable via LOOP_MAX_COST_USD environment variable; the comment is misleading"

## Safety Guarantees

✅ **No direct file modifications** — only creates PRs  
✅ **No auto-merge/publish** — connector creates branch/PR only  
✅ **Maker output passes checker** — connector never runs if checker fails  
✅ **Budget enforced** — hard limits with NEEDS HUMAN escalation  
✅ **Evidence required** — proposals without dates/frequency rejected  
✅ **Minimal changes enforced** — max 50 diff lines  
✅ **Branch naming enforced** — `claude/fix-<hash>` or `claude/delete-<hash>`  
✅ **Failures not silent** — stderr + dreaming-state.md + non-zero exit  
✅ **Auditable** — complete trace in dreaming-state.md  

## Files Created

```
Loop-engineering-project12/
├── dreaming-state.md         # SPINE - persistent memory
├── loop.cmd                  # Entry point (Windows)
├── README.md                 # This file
├── src/
│   ├── __init__.py
│   ├── dream_spine.py        # Part 1: Persistent memory
│   ├── dream_skill.py        # Part 2: Analysis procedure
│   ├── dream_maker.py        # Part 3: Produces proposals
│   ├── dream_checker.py      # Part 4: Validates proposals
│   ├── dream_connector.py    # Part 5: Git/PR integration
│   └── dream_loop.py         # Main orchestration
└── tests/
    └── test_dream_loop.py    # Comprehensive test suite
```

## Running the Dream Loop

### Manual Run
```cmd
loop.cmd
# or
python src\dream_loop.py
```

### Weekly Schedule (Windows Task Scheduler)
```cmd
schtasks /create /sc weekly /d SUN /tn "loop-project12-dream" ^
  /tr "F:\Loop-practice-projects\Loop-engineering-project12\loop.cmd" /st 03:00 /f
```

### Environment Variables
```cmd
set LOOP_MAX_TOKENS=3000
set LOOP_TOKEN_PRICE=0.0015
set LOOP_MAX_COST_USD=0.0045
set LOOP_WORKTREE_BASE=F:\Loop-practice-projects\Loop-engineering-project12\.worktree
```

## Testing

Run all tests:
```cmd
python -m pytest tests/ -v
```

Test categories:
- `TestDreamSpine` — persistence, state, log formatting
- `TestDreamSkill` — progress parsing, pattern detection, root cause analysis
- `TestDreamMaker` — artifact generation, PR description creation
- `TestDreamChecker` — evidence validation, minimality, safety checks
- `TestDreamConnector` — connector gating on checker
- `TestDreamLoopIntegration` — repeated failure detection, evidence requirement, no direct modifications, human gate
- `TestFullLoop` — full pass structure verification

## Weekly Human Review

1. **Open `dreaming-state.md`** — scan for `NEEDS HUMAN`, `ERROR`, `CHECKER_FAILED`
2. **Check Project 8 GitHub** — review any `claude/fix-*` or `claude/delete-*` branches/PRs
3. **Verify Proposals** — ensure evidence is accurate, changes are minimal
4. **Merge or Close** — human decision on each PR
5. **Clean Proposals** — remove `.dream_proposals/` if disk space concern

## Recovery Process

### 1. Check Dreaming State First
```cmd
type dreaming-state.md
```
Look at `last_status`, `last_run`, `last_analyzed_date`, `NEEDS HUMAN` entries.

### 2. Common Scenarios

| Scenario | Diagnosis | Recovery |
|----------|-----------|----------|
| `CHECKER_FAILED` | Proposal validation failed | Check evidence, minimality, branch naming; fix and re-run |
| `BUDGET_EXCEEDED` | Too many tokens estimated | Reduce scope or increase `LOOP_MAX_TOKENS` |
| `ERROR` | Unexpected exception | Check stderr, fix root cause, re-run |
| `CONNECTOR_SKIPPED` | Branch exists or push failed | Check git remote, branch conflicts, `gh` CLI |

### 3. Manual Re-run
```cmd
# After fixing root cause
loop.cmd
```

### 4. Reset Analysis Date (if needed)
Edit `dreaming-state.md`:
```
- last_analyzed_date: <new-date-or-empty>
```
Next run will re-analyze from new date.

## License

Loop Engineering Practice — Educational/Reference Implementation