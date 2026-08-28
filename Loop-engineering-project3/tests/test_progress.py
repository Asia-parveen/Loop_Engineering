"""Tests for Loop Engineering Practice Project 3.

Verifies the deduplication logic: the second run must only report commits
newer than last_seen_commit and must never repeat already-recorded ones.
Uses a real throwaway git repository (stdlib + git only).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.loop import run_pass  # noqa: E402


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


class TestLoopDedup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Loop Test")
        self.progress = Path(self._tmp.name) / "progress.md"

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, message):
        git(self.repo, "commit", "--allow-empty", "-m", message)
        return git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def test_first_run_records_all_commits(self):
        c1 = self._commit("first commit")
        cursor, summary = run_pass(self.progress, self.repo)
        self.assertIsNone(cursor)
        self.assertIn("First run", summary)
        self.assertIn(c1[:7], summary)
        self.assertIn("- last_seen_commit:", self.progress.read_text(encoding="utf-8"))

    def test_second_run_does_not_repeat_first(self):
        c1 = self._commit("first commit")
        run_pass(self.progress, self.repo)

        c2 = self._commit("second commit")
        c2_short = git(self.repo, "rev-parse", "--short", "HEAD").stdout.strip()
        cursor2, summary2 = run_pass(self.progress, self.repo)
        self.assertEqual(cursor2, c1[:7])  # cursor used in this run
        self.assertIn(c2_short, summary2)  # only the new commit is reported
        self.assertNotIn(f"{c1[:7]} ", summary2)  # first commit not repeated

        # the spine advanced to the newest commit
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn(f"- last_seen_commit: {c2_short}", text)

    def test_run_with_no_new_commits(self):
        c1 = self._commit("first commit")
        run_pass(self.progress, self.repo)

        cursor2, summary2 = run_pass(self.progress, self.repo)
        self.assertEqual(cursor2, c1[:7])  # cursor unchanged
        self.assertIn(f"No new commits since {c1[:7]}", summary2)


if __name__ == "__main__":
    unittest.main()
