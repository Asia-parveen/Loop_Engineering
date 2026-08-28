# Loop Engineering Project 9: One-Off Runs & Transcript Review

## Overview

This project demonstrates a **one-off manual execution** pattern with full transcript logging to distinguish success from failure. The task summarizes yesterday's Git commits to a `claude/summary` branch.

## Files

| File | Purpose |
|------|---------|
| `summarize-commits.ps1` | Main script - summarizes commits, creates `claude/summary` branch |
| `test-summarize-commits.ps1` | Test suite - verifies success and intentional failure |
| `README.md` | This documentation |

## One-Off Run (Manual "Run Now")

```powershell
# Run successfully (summarizes last 7 days to test branch)
.\summarize-commits.ps1 -Since "2024-01-01" -BranchName "claude/summary-test" -LogFile "run.log"

# Check results
cat run.log
git log claude/summary-test --oneline
```

**Expected success output in log:**
```
[2024-01-15 10:30:00] [INFO] Starting commit summary task...
[2024-01-15 10:30:00] [INFO] Parameters: Since=2024-01-01, BranchName=claude/summary-test
[2024-01-15 10:30:00] [INFO] Git repository verified
[2024-01-15 10:30:00] [INFO] Found 3 commit(s) since 2024-01-01
[2024-01-15 10:30:01] [INFO] Creating/updating branch: claude/summary-test
[2024-01-15 10:30:01] [INFO] Created summary file: COMMIT_SUMMARY.md
[2024-01-15 10:30:01] [SUCCESS] Successfully created/updated claude/summary-test with commit summary
[2024-01-15 10:30:01] [SUCCESS] Task completed successfully
```

## Transcript Review

The **full transcript** (log file) is the source of truth. Key markers:

| Marker | Meaning |
|--------|---------|
| `[SUCCESS]` | Operation succeeded |
| `[ERROR]` | Operation failed |
| `Task completed successfully` | Clean exit |
| `Sabotage triggered` | Intentional failure detected |

**Success transcript contains:** `SUCCESS` + `Task completed successfully`  
**Failure transcript contains:** `ERROR` + failure reason (non-silent)

## Sabotage Test (Intentional Failure)

The test suite includes a **sabotaged script** that deliberately reads a non-existent file:

```powershell
# This fails clearly and non-silently
Get-Content "C:\This\Path\Does\Not\Exist\fake-file.txt" -ErrorAction Stop
```

**Failure transcript shows:**
```
[2024-01-15 10:31:00] [INFO] Starting sabotaged commit summary task...
[2024-01-15 10:31:00] [ERROR] Sabotage triggered - failed to read non-existent file: Cannot find path 'C:\This\Path\Does\Not\Exist\fake-file.txt' because it does not exist.
```

## A5 Lesson: Observability Over Assumptions

> **A5 Lesson**: *Never assume a background job succeeded. Read the transcript.*

- **One-off runs** must produce **auditable logs** with explicit SUCCESS/ERROR markers
- **Transcript review** is the only reliable way to verify outcome
- **Silent failures** are the worst kind - this design makes failure **loud and clear**
- **Test both paths**: The test suite verifies the happy path AND the failure path

## Running Tests

```powershell
# Run full test suite (both success + sabotage failure)
.\test-summarize-commits.ps1
```

**Expected test output:**
```
========== Test 1: Successful run ==========
Verified: Branch created, log contains success markers
PASS: Test 1: Successful run

========== Test 2: Intentional failure (non-existent file) ==========
Verified: Script failed non-silently, log contains error markers
PASS: Test 2: Intentional failure (non-existent file)

========== TEST SUMMARY ==========
Passed: 2
Failed: 0
```

## Design Principles

1. **No recurring schedule** - purely manual/one-off execution
2. **Throwaway/local repo** - uses local git, pushes to `claude/summary` branch
3. **Simple & safe** - no external dependencies, only git + PowerShell
4. **Checkable task** - verifiable output (branch + log file)
5. **Clear failure** - sabotage test proves non-silent failure detection