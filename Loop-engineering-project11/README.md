# Loop Engineering Project 11: Two Routines with Human Approval Gate

## Overview

This project implements a **two-routine workflow with a mandatory human approval gate** between them:

- **Routine A** — Manual/one-off trigger that creates a reviewable draft on a `claude/` branch
- **Routine B** — API-triggered follow-up action that requires explicit human invocation with bearer token authentication

The human gate ensures **Routine B never runs automatically** after Routine A. A human must review the draft and explicitly trigger Routine B via a documented curl command.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HUMAN OPERATOR                                    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
         ┌─────────────────────┐         ┌─────────────────────┐
         │    ROUTINE A        │         │    ROUTINE B        │
         │  (Manual Trigger)   │         │  (API Triggered)    │
         └──────────┬──────────┘         └──────────┬──────────┘
                    │                               │
         ┌──────────┴──────────┐         ┌──────────┴──────────┐
         │  Creates            │         │  Requires           │
         │  claude/* branch    │         │  Bearer Token       │
         │  with summary       │         │  (from env var)     │
         └──────────┬──────────┘         └──────────┬──────────┘
                    │                               │
         ┌──────────┴──────────┐         ┌──────────┴──────────┐
         │  Saves state/log    │         │  Human MUST         │
         │  evidence           │         │  run curl command   │
         └──────────┬──────────┘         └──────────┬──────────┘
                    │                               │
         ┌──────────┴──────────┐         ┌──────────┴──────────┐
         │  Sets human_gate:   │         │  Validates draft    │
         │  "awaiting_review"  │────────▶│  exists, then runs  │
         └─────────────────────┘         └──────────┬──────────┘
                                                    │
                                         ┌──────────┴──────────┐
                                         │  Creates shipping   │
                                         │  record, updates    │
                                         │  state to           │
                                         │  "completed"        │
                                         └─────────────────────┘
```

---

## Routine A: Manual Draft Creation

### Purpose
Create a reviewable draft on a `claude/` branch with a commit summary. Does **not** trigger Routine B.

### Trigger
Manual only — run via command line:
```bash
python routine_a.py [--since YYYY-MM-DD] [--branch-suffix NAME]
```

### What It Does
1. Fetches Git commits (optionally filtered by date)
2. Creates a markdown summary (`COMMIT_SUMMARY.md`)
3. Creates/updates a `claude/<suffix>` branch with the summary
4. Pushes branch to origin (for reviewability)
5. Saves state to `routine_state.json` with `human_gate_status: "awaiting_review"`
6. Writes detailed log to `logs/routine_a_<run_id>.log`

### What It Does NOT Do
- ❌ Does NOT call Routine B
- ❌ Does NOT start any background process
- ❌ Does NOT write trigger files or signals
- ❌ Does NOT auto-merge or auto-publish

### Outputs
- **Branch**: `claude/<suffix>` with `COMMIT_SUMMARY.md`
- **State**: `routine_state.json` updated with draft info
- **Log**: `logs/routine_a_<run_id>.log` with full transcript

### Example Run
```bash
$ python routine_a.py --since 2026-01-01 --branch-suffix my-summary

✅ Routine A completed successfully!
   Run ID: a1b2c3d4
   Branch: claude/my-summary
   Commits: 5
   Summary hash: abc123def456
   Log: logs/routine_a_a1b2c3d4.log
   State: routine_state.json

📋 Next step: Review the draft on branch 'claude/my-summary'
   Then trigger Routine B manually using the documented curl command.
```

---

## Routine B: API-Triggered Follow-up

### Purpose
Execute a follow-up action **only when explicitly triggered by a human** via API call with valid bearer token.

### Trigger
Explicit API call only:
```bash
curl -X POST \
  -H "Authorization: Bearer $ROUTINE_B_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "human"}' \
  http://localhost:8765/trigger
```

### What It Does
1. Validates bearer token from `Authorization` header
2. Checks that a draft from Routine A exists and is `ready_for_review`
3. Executes the follow-up action (creates shipping record)
4. Updates state to `human_gate_status: "completed"`
5. Writes detailed log to `logs/routine_b_<run_id>.log`
6. Creates shipping record in `logs/shipping_record_<run_id>.json`

### What It Does NOT Do
- ❌ Does NOT run automatically
- ❌ Does NOT auto-merge branches
- ❌ Does NOT accept unauthenticated requests
- ❌ Does NOT log or expose the bearer token

### API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | None | Health check |
| `/status` | GET | None | Check draft status |
| `/trigger` | POST | **Bearer token required** | Execute Routine B |

### Starting the Server
```bash
# Set token first (required)
export ROUTINE_B_API_TOKEN="your-secure-random-token"

# Start server
python routine_b.py --port 8765
```

### Example Trigger
```bash
$ curl -X POST \
  -H "Authorization: Bearer your-secure-random-token" \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "human-reviewer"}' \
  http://localhost:8765/trigger

{
  "success": true,
  "run_id": "e5f6g7h8",
  "action_result": {
    "action": "review_and_ship",
    "draft_branch": "claude/my-summary",
    "summary_hash": "abc123def456",
    "executed_at": "2026-08-29T14:30:00.123456",
    "executed_by": "human_api_trigger",
    "details": ["Branch 'claude/my-summary' exists on remote"],
    "shipping_record": "logs/shipping_record_e5f6g7h8.json"
  },
  "log_file": "logs/routine_b_e5f6g7h8.log",
  "state_file": "routine_state.json",
  "message": "Routine B executed successfully. Check shipping record."
}
```

---

## Human Gate Flow

### The Gate
The human gate is enforced by **state machine** in `routine_state.json`:

```
pending → awaiting_review → completed
   │            │               │
   │      Routine A         Routine B
   │       creates          validates
   │       draft            draft exists
   │            │               │
   ▼            ▼               ▼
  (start)   (human reviews)  (human triggers)
```

### Step-by-Step Flow

1. **Human runs Routine A**
   ```bash
   python routine_a.py --branch-suffix feature-xyz
   ```

2. **Human reviews the draft**
   ```bash
   # View the summary locally
   git show claude/feature-xyz:COMMIT_SUMMARY.md
   
   # Or view on GitHub/GitLab after push
   # https://github.com/owner/repo/tree/claude/feature-xyz
   ```

3. **Human starts Routine B server** (if not already running)
   ```bash
   export ROUTINE_B_API_TOKEN="your-secure-token"
   python routine_b.py --port 8765 &
   ```

4. **Human triggers Routine B via curl** (THE GATE)
   ```bash
   curl -X POST \
     -H "Authorization: Bearer $ROUTINE_B_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"approved_by": "your-name"}' \
     http://localhost:8765/trigger
   ```

5. **Verify completion**
   ```bash
   # Check state
   cat routine_state.json | jq '.human_gate_status'
   # Should be "completed"
   
   # Check shipping record
   cat logs/shipping_record_*.json
   ```

---

## A3 / A4 / A6 Concepts

### A3: Connectors Minimized/Pruned
- **Routine A**: Only uses local Git (`git` CLI) — no external APIs
- **Routine B**: Only exposes 3 HTTP endpoints (`/health`, `/status`, `/trigger`) — no database, message queue, or external service connectors
- **No auto-merge/publish connectors** — human must manually merge PR

### A4: Secrets Management
- **Bearer token sourced ONLY from environment variable** (`ROUTINE_B_API_TOKEN`)
- **Never hard-coded** in source code
- **Never printed** to logs, stdout, or stderr
- **Constant-time comparison** prevents timing attacks
- **No `.env` file support** — follows 12-factor app principles

### A6: Safety Checklist
See [A6_SAFETY_CHECKLIST.md](A6_SAFETY_CHECKLIST.md) for the complete 38-item checklist covering:
1. ✅ Connectors minimized/pruned
2. ✅ Unrestricted pushes disabled
3. ✅ State file selected
4. ✅ Secrets protected
5. ✅ Routine B cannot run automatically after Routine A
6. ✅ Human gate enforced

---

## Setup

### Prerequisites
- Python 3.8+
- Git repository (with remote `origin` configured)
- Network access for `git push` (Routine A)

### Installation
```bash
cd Loop-engineering-project11

# No pip install needed — uses only standard library
# Verify Python version
python --version  # 3.8+
```

### Configuration
```bash
# Required for Routine B
export ROUTINE_B_API_TOKEN="$(openssl rand -hex 32)"

# Optional: custom port for Routine B
export ROUTINE_B_PORT=8765
```

### Generate a Secure Token
```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python -c "import secrets; print(secrets.token_hex(32))"

# Option 3: /dev/urandom (Linux/macOS)
head -c 32 /dev/urandom | xxd -p -c 32
```

---

## Testing

### Run All Tests
```bash
python -m pytest test_project11.py -v
```

### Test Categories

| Test | Verifies |
|------|----------|
| `TestRoutineA::test_a_runs_independently` | A runs without B |
| `TestRoutineA::test_a_creates_reviewable_draft` | Creates `claude/` branch |
| `TestRoutineA::test_a_does_not_trigger_b_automatically` | **Critical**: B not auto-triggered |
| `TestRoutineA::test_a_saves_clear_state_and_log_evidence` | State + logs created |
| `TestRoutineB::test_b_requires_explicit_api_trigger` | B only runs via API |
| `TestRoutineB::test_b_requires_bearer_token_authentication` | Auth required |
| `TestRoutineB::test_b_successful_action_is_observable` | Shipping record + logs |
| `TestRoutineB::test_b_rejects_invalid_missing_token` | 401 on bad auth |
| `TestRoutineB::test_b_no_secret_exposed_in_logs` | Token not in logs |
| `TestRoutineB::test_b_fails_without_draft_from_a` | Human gate enforced |
| `TestHumanGateFlow::test_complete_human_gate_flow` | End-to-end flow |
| `TestHumanGateFlow::test_curl_command_documented_works` | Exact curl works |
| `TestSecurityAndSafety::test_no_hardcoded_secrets` | No secrets in code |
| `TestSecurityAndSafety::test_routine_a_no_external_dependencies` | Minimal connectors |

### Expected Test Output
```
============================= test session starts ==============================
test_project11.py::TestRoutineA::test_a_runs_independently PASSED
test_project11.py::TestRoutineA::test_a_creates_reviewable_draft PASSED
test_project11.py::TestRoutineA::test_a_does_not_trigger_b_automatically PASSED
test_project11.py::TestRoutineA::test_a_saves_clear_state_and_log_evidence PASSED
test_project11.py::TestRoutineB::test_b_requires_explicit_api_trigger PASSED
test_project11.py::TestRoutineB::test_b_requires_bearer_token_authentication PASSED
test_project11.py::TestRoutineB::test_b_successful_action_is_observable PASSED
test_project11.py::TestRoutineB::test_b_rejects_invalid_missing_token PASSED
test_project11.py::TestRoutineB::test_b_no_secret_exposed_in_logs PASSED
test_project11.py::TestRoutineB::test_b_fails_without_draft_from_a PASSED
test_project11.py::TestHumanGateFlow::test_complete_human_gate_flow PASSED
test_project11.py::TestHumanGateFlow::test_curl_command_documented_works PASSED
test_project11.py::TestSecurityAndSafety::test_no_hardcoded_secrets PASSED
test_project11.py::TestSecurityAndSafety::test_routine_a_no_external_dependencies PASSED
test_project11.py::TestSecurityAndSafety::test_state_file_not_world_writable PASSED
============================== 15 passed in 2.34s ==============================
```

---

## Safe Usage Guidelines

### Do ✅
- Run Routine A manually when you need a draft
- Review the `claude/*` branch before triggering B
- Use a strong, randomly generated `ROUTINE_B_API_TOKEN`
- Keep the token in environment variables only
- Stop Routine B server when not in use
- Check `routine_state.json` and logs for audit trail

### Don't ❌
- Don't hard-code the token in scripts or config files
- Don't commit `routine_state.json` or `logs/` to Git (add to `.gitignore`)
- Don't expose Routine B server to public networks without additional auth
- Don't run Routine B without a valid draft from Routine A
- Don't auto-trigger Routine B from CI/CD or schedulers

### Security Notes
- The bearer token is validated via SHA-256 hash comparison (timing-safe)
- Token is never logged — only "Bearer token validated" messages appear
- Routine B binds to `localhost` by default (not `0.0.0.0`)
- State file contains no secrets — only metadata and hashes

---

## Files Created

```
Loop-engineering-project11/
├── routine_a.py              # Routine A: Manual draft creation
├── routine_b.py              # Routine B: API server + trigger
├── test_project11.py         # Comprehensive test suite
├── A6_SAFETY_CHECKLIST.md    # 38-item safety checklist
├── README.md                 # This file
├── routine_state.json        # Created at runtime (gitignored)
└── logs/                     # Created at runtime (gitignored)
    ├── routine_a_<run_id>.log
    ├── routine_b_<run_id>.log
    └── shipping_record_<run_id>.json
```

### .gitignore Recommendation
```gitignore
# Project 11 runtime files
routine_state.json
logs/
*.log
```

---

## Troubleshooting

### Routine A: "Not a git repository"
```bash
# Ensure you're in a git repo with origin remote
git status
git remote -v
```

### Routine B: "API token not found"
```bash
# Set the environment variable
export ROUTINE_B_API_TOKEN="your-token"
# Then start server
python routine_b.py
```

### Routine B: "Connection refused" on curl
```bash
# Check server is running
curl http://localhost:8765/health
# Should return {"status": "ok", "service": "routine-b"}
```

### Routine B: "Human gate check failed: No draft found"
```bash
# Run Routine A first
python routine_a.py --branch-suffix my-draft
# Then trigger B
```

### Routine B: 401 Unauthorized
```bash
# Verify token matches exactly
echo $ROUTINE_B_API_TOKEN
# Use same value in curl -H "Authorization: Bearer $ROUTINE_B_API_TOKEN"
```

---

## License

Loop Engineering Practice — Educational/Reference Implementation