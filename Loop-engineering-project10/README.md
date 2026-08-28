# Loop Engineering Project 10: Environment Variables vs .env Files

## Overview

This project demonstrates the critical difference between storing secrets in `.env` files versus environment variables, and why the latter is the correct approach for production/cloud environments.

## The Scenario

A small routine (`main.py`) requires a dummy secret token (`DUMMY_SECRET_TOKEN`) to run successfully.

## Run 1: Failure (`.env` only, no environment variable)

**Setup:**
- The dummy token is stored **only** in a gitignored `.env` file
- The script runs in a fresh/cloud-like environment where `.env` is unavailable (not loaded)

**Result:** **FAILURE**

The script exits with code 1 and prints:
```
ERROR: Secret token not found. Expected environment variable DUMMY_SECRET_TOKEN to be set. Do not look for a .env file.
```

**Why it failed (A4 - Secrets Management):**
- `.env` files are **local development conveniences**, not runtime mechanisms
- They are intentionally **gitignored** and **not deployed** to production/cloud environments
- The runtime (Python) does **not automatically load** `.env` files — you need a library like `python-dotenv` to do that
- In a fresh/cloud environment, the `.env` file simply doesn't exist or isn't read
- **A4 Principle:** Secrets must be injected into the runtime environment, not baked into files that may not be present

## Run 2: Success (Environment variable provided)

**Setup:**
- The same dummy token is provided via the `DUMMY_SECRET_TOKEN` environment variable
- The prompt instruction is followed: *"credentials are available as environment variables; do not look for a .env file."*
- No `.env` file is used or loaded

**Result:** **SUCCESS**

The script exits with code 0 and prints:
```
Token retrieved successfully (length: 21)
```

**Why it succeeded (A2 - Environment Configuration):**
- Environment variables are the **standard, universal mechanism** for configuring applications across all environments (local, CI, staging, production)
- They are **injected by the platform** (Docker, Kubernetes, cloud providers, CI/CD systems)
- They work **identically** everywhere — no special libraries needed
- **A2 Principle:** Configuration (including secrets) comes from the environment, making the application portable and environment-agnostic

## Key Takeaways

| Aspect | `.env` File | Environment Variable |
|--------|-------------|---------------------|
| **Portability** | ❌ Local only | ✅ Universal |
| **Deployment** | ❌ Not deployed | ✅ Injected by platform |
| **Security** | ⚠️ Risk of commit | ✅ Never in code/repo |
| **Runtime loading** | ❌ Requires library | ✅ Native OS support |
| **A2 Compliance** | ❌ No | ✅ Yes |
| **A4 Compliance** | ❌ No (file-based) | ✅ Yes (injected) |

## Running the Tests

```bash
# Run failure test (simulates fresh environment without .env)
python -m pytest test_failure.py -v

# Run success test (simulates env var injection)
python -m pytest test_success.py -v

# Run all tests
python -m pytest -v
```

## Test Results

Both tests verify:
1. The script **fails** when the environment variable is not set (even if `.env` exists locally)
2. The script **succeeds** when the environment variable is properly set
3. The **actual secret value is never printed** in logs/output (only its length)