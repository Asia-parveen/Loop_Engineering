# SKILL: Fix the price calculator tax bug

Short reusable steps for the implementer working in an isolated worktree.

## Goal

Make `tests/test_price.py` pass by fixing `src/price.py`.

## Steps

1. Open `src/price.py` and `tests/test_price.py`.
2. Run the test suite to see the failure:

   ```
   python -m unittest discover -s tests -v
   ```

3. Read the failing test. It asserts that tax is applied to the
   **discounted** price, not the base price:
   `final_price(100, 10, 20) == 108.0`.
4. Edit `src/price.py` so the `tax` line uses `discounted` instead of
   `base_price`.
5. Re-run the test suite until it exits with code 0.
6. Commit the change on your branch (e.g. `impl/fix-price`).
7. Do **not** open a PR yourself. Only `gate/open_pr.cmd` may start the PR
   step, and only after the reviewer returns `PASS`.
