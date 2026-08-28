# Loop Engineering Practice Project 4

> Implementer-reviewer workflow: worktree (Concept 8), skill (Concept 9),
> maker-checker (Concept 11).

## The project

`src/price.py` computes `final_price(base, discount_percent, tax_percent)`.
It contains a deliberate bug: **tax is applied to the base price instead of
the discounted price**. The tests in `tests/test_price.py` expose it.

## Roles

- **Implementer** — works in its own Git worktree (`impl`, branch
  `impl/fix-price`), follows `SKILL.md`, fixes the bug, commits, pushes.
- **Reviewer** — works in an independent review worktree (`review`, branch
  `review/fix-price`, based on the implementer's branch). It does **not**
  trust the implementer: it inspects the actual diff and runs the tests
  itself, then writes exactly one verdict to `review/result.txt`:
  `PASS: <reasons>` or `FAIL: <reasons>`.
- **Gate** (`gate/open_pr.cmd`) — the maker-checker control point. Only it
  may start the PR step, and only when the reviewer returned `PASS`.

## The gate

- `PASS` → verify reviewer result, push `impl/fix-price`, print the exact
  GitHub compare URL where the PR can be opened manually.
- `FAIL` or missing result → block the PR, exit code 1.
- Automatic `gh pr create` needs the `gh` CLI, which is **not installed**
  here, so this demo stops at the compare/PR URL. It never fakes a PR.
- The gate never modifies the tests to force a pass.

## Worktrees (both outside the repo)

- Implementer: `F:\Loop-engineering-project4-worktrees\impl`  (branch `impl/fix-price`)
- Reviewer:   `F:\Loop-engineering-project4-worktrees\review` (branch `review/fix-price`)

The two worktrees never check out the same branch at the same time (Git
forbids it): the reviewer branches `review/fix-price` off the implementer's
committed `impl/fix-price`.

## Demonstrations

1. **Good fix** → reviewer PASS → gate allows the PR step.
2. **Deliberately bad fix** → reviewer FAIL with concrete reasons → gate blocks.

If the reviewer ever passes the deliberately bad fix, the checker is too
weak and must be tightened before continuing.

## Files

| File                | Purpose                                        |
|---------------------|------------------------------------------------|
| `src/price.py`      | The code with the intentional bug.             |
| `tests/test_price.py` | The spec the fix must satisfy.              |
| `SKILL.md`          | Reusable fix steps for the implementer.        |
| `review/reviewer.cmd` | Independent reviewer -> PASS/FAIL + reasons. |
| `gate/open_pr.cmd`  | PASS/FAIL gate controlling the PR step.        |
| `progress.md`       | Log of the two demo runs.                      |
