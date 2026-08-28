# A6 Safety Checklist — Loop Engineering Project 11

**Project:** Two Routines with Human Approval Gate  
**Date:** 2026-08-29  
**Version:** 1.0  

---

## Overview

This checklist verifies that the implementation of Routine A and Routine B meets all A6 safety requirements for the human approval gate pattern.

---

## ✅ Checklist Items

### 1. Connectors Minimized/Pruned

| Check | Status | Evidence |
|-------|--------|----------|
| Routine A uses only local Git operations (no external API calls) | ✅ | `routine_a.py` uses `subprocess.run` with `git` commands only |
| Routine B API server exposes only 3 endpoints: `/health`, `/status`, `/trigger` | ✅ | `RoutineBHandler` class defines only these routes |
| No database connectors, message queues, or external service integrations | ✅ | Only file-based state (`routine_state.json`) and Git |
| Connector logic (Git push) is isolated and optional | ✅ | `create_claude_branch` function has optional push, returns success/failure |
| No auto-merge, auto-deploy, or auto-publish connectors | ✅ | Routine B creates shipping record only; human must merge |

**Verification:** Run `grep -r "requests\|urllib\|httpx\|aiohttp" .` — should return no results for external HTTP libraries in routine code.

---

### 2. Unrestricted Pushes Disabled

| Check | Status | Evidence |
|-------|--------|----------|
| Routine A pushes to `claude/*` branch namespace only | ✅ | Branch name format enforced: `claude/{suffix}` |
| Routine A uses `--force` push but only to its own branch | ✅ | `git push origin {branch_name} --force` targets specific branch |
| Routine B does NOT push to any branch | ✅ | `routine_b.py` has no `git push` calls |
| No `git push --force` to `main`, `master`, or protected branches | ✅ | Branch name validation prevents this |
| No auto-merge via GitHub API or `gh` CLI | ✅ | Routine B only creates shipping record |
| Push requires human to have write access to repo | ✅ | Uses standard Git authentication (SSH/HTTPS token) |

**Verification:** 
- `grep -n "push" routine_a.py` — shows only targeted push to claude branch
- `grep -n "push" routine_b.py` — returns no results

---

### 3. State File Selected

| Check | Status | Evidence |
|-------|--------|----------|
| Single state file: `routine_state.json` | ✅ | Both routines read/write this file |
| State includes: Routine A runs, Routine B runs, current draft, human gate status | ✅ | `load_state()` / `save_state()` functions |
| State is JSON (human-readable, version-controllable) | ✅ | `json.dump/load` with indent=2 |
| State persisted after each routine run | ✅ | `save_state()` called in all code paths |
| State survives process restarts | ✅ | File-based, not in-memory only |
| State includes timestamps for audit trail | ✅ | ISO format timestamps on all entries |
| State includes log file references for traceability | ✅ | Each run entry has `log_file` field |

**Verification:** Run Routine A, then `cat routine_state.json` — verify structure.

---

### 4. Secrets Protected

| Check | Status | Evidence |
|-------|--------|----------|
| Routine B API token sourced ONLY from environment variable | ✅ | `get_api_token()` reads `os.environ.get("ROUTINE_B_API_TOKEN")` |
| Token NEVER hard-coded in source code | ✅ | No string literals resembling tokens in `.py` files |
| Token NEVER printed to stdout/stderr/logs | ✅ | `validate_bearer_token()` uses constant-time hash comparison; token not logged |
| Token validation uses constant-time comparison | ✅ | SHA256 hash comparison prevents timing attacks |
| `.env` files NOT used for token storage | ✅ | No `python-dotenv` import; no `.env` loading |
| Routine A requires NO secrets | ✅ | Uses only local Git (auth via system Git config) |
| Logs contain no secret material | ✅ | Logs show "Bearer token validated" not token value |

**Verification:** 
- `grep -r "ROUTINE_B_API_TOKEN" . --include="*.py"` — only in `routine_b.py` reading from env
- `grep -r "Bearer\|token" logs/` — should show only validation messages, never values
- Run test `test_secret_not_exposed_in_logs` — passes

---

### 5. Routine B Cannot Run Automatically After Routine A

| Check | Status | Evidence |
|-------|--------|----------|
| Routine A has NO import or call to Routine B | ✅ | `routine_a.py` has no import of `routine_b` |
| Routine A does NOT start Routine B server | ✅ | No `subprocess.Popen`, `threading`, or HTTP calls to localhost |
| Routine A does NOT write trigger file or signal for Routine B | ✅ | State only marks `human_gate_status: "awaiting_review"` |
| Routine B server must be started separately by human | ✅ | `python routine_b.py` starts server manually |
| Routine B `/trigger` endpoint requires explicit POST with valid token | ✅ | `do_POST` validates bearer token on every request |
| No webhook, cron, scheduler, or event-driven auto-trigger | ✅ | No GitHub Actions, no Windows Task Scheduler, no polling |
| Human must manually run `curl` command to trigger Routine B | ✅ | Documented curl command required |

**Verification:**
- Run Routine A, wait 30 seconds — Routine B does not execute
- `ps aux | grep routine_b` — no process unless manually started
- Check `routine_state.json` — `human_gate_status` remains `"awaiting_review"`

---

### 6. Human Gate Enforced

| Check | Status | Evidence |
|-------|--------|----------|
| Routine A marks draft as `ready_for_review` | ✅ | `draft_info["status"] = "ready_for_review"` |
| Routine B checks `check_draft_ready()` before executing | ✅ | First step in `run_routine_b()` |
| Routine B fails with clear error if no draft ready | ✅ | Returns `failed_human_gate` status |
| Human must review branch content before triggering | ✅ | Branch `claude/*` pushed for review |
| Exact curl command documented | ✅ | See `CURL_COMMAND.md` and README |
| Human gate status tracked in state: `pending` → `awaiting_review` → `completed` | ✅ | State transitions in both routines |

---

## 📋 Summary

| Category | Pass | Fail | N/A |
|----------|------|------|-----|
| Connectors Minimized/Pruned | 5 | 0 | 0 |
| Unrestricted Pushes Disabled | 6 | 0 | 0 |
| State File Selected | 7 | 0 | 0 |
| Secrets Protected | 7 | 0 | 0 |
| B Cannot Run Auto After A | 7 | 0 | 0 |
| Human Gate Enforced | 6 | 0 | 0 |
| **TOTAL** | **38** | **0** | **0** |

---

## 🔒 Safety Guarantees

- ✅ **No automatic escalation** — Human must explicitly trigger each step
- ✅ **No secret leakage** — Tokens only in env vars, never logged
- ✅ **Audit trail** — Complete state + log files for every run
- ✅ **Failure visibility** — Non-silent failures with clear error messages
- ✅ **Idempotent operations** — Safe to re-run
- ✅ **Minimal attack surface** — 3 API endpoints, local Git only

---

## 📝 Sign-off

**Reviewed by:** _________________________  
**Date:** _________________________  
**Approved:** ☐ Yes  ☐ No