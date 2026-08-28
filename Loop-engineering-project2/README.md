# Loop Engineering Practice Project 2

> Loop until a command says the work is done, not until the agent decides it is done.

## Goal

Practice a conditional loop (Concept 5) with a maker-checker split (Concept 11).
The agent never decides the work is complete. Only the test runner's exit code
can say "done".

## Roles

- **Maker** = the agent. Edits `src/calculator.py` to fix the code.
- **Checker** = the test runner (`run_tests.cmd`). Approves or rejects the work
  with its exit code. It is the source of truth.

## Files

| File                | Purpose                                             |
|---------------------|-----------------------------------------------------|
| `src/calculator.py` | The code the agent fixes. Contains 3 deliberate bugs. |
| `tests/`            | 3 small tests, one per broken function.             |
| `run_tests.cmd`     | The checker command. Thin wrapper around the test runner. |

## The loop

```
attempt = 0
loop:
  1. agent (maker) edits src/calculator.py
  2. run run_tests.cmd (checker)
  3. exit code 0 -> all tests pass -> DONE
  4. exit code non-zero -> read failures, attempt += 1
  5. if attempt == 6 -> STOP: "not done after 6 attempts"
```

## Rules

- **Exit code is the truth.** `0` = passed, non-zero = failed.
- **Maximum 6 attempts.** Reaching the cap means the command never said done.
- **The agent must NOT declare completion.** "I'm done" is not a signal;
  the checker's exit code is the only valid completion signal. An agent can
  *believe* it finished while the command still fails — the command is what counts.

## The checker

```cmd
run_tests.cmd
```
