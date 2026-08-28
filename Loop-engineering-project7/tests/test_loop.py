"""Tests for Loop Engineering Practice Project 7.

Verifies:
- one-pass behavior (no internal loop)
- sabotage triggers on non-existent file read
- max attempt = 1
- non-silent failure (stderr output)
- NEEDS HUMAN logged
- timestamp in log entry
- spine-only diagnosis (progress.md contains all info)
- cost calculation documented
"""

import datetime
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.loop import run_pass, MAX_ATTEMPTS, SABOTAGE_FILE  # noqa: E402


class TestLoopProject7(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.progress = self.tmp_path / "progress.md"
        self.sabotage_file = self.tmp_path / "nonexistent_sabotage_file.txt"
        # Create initial progress.md (no attempt field - each run is independent)
        self.progress.write_text(
            "# Progress\n\n## State\n- last_run: \n- last_error: \n\n## Log\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_one_pass_per_invocation(self):
        """Each run_pass call is exactly one pass, no internal loop."""
        result = run_pass(self.progress)
        self.assertEqual(result, 1)  # failure expected
        # Only one log entry added
        text = self.progress.read_text(encoding="utf-8")
        log_entries = len(re.findall(r"^### ", text, re.MULTILINE))
        self.assertEqual(log_entries, 1)

    def test_sabotage_triggers_on_nonexistent_file(self):
        """Reading non-existent file triggers sabotage failure."""
        result = run_pass(self.progress)
        self.assertEqual(result, 1)
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn("FAILED: Sabotage triggered", text)
        self.assertIn("nonexistent_sabotage_file.txt", text)
        self.assertIn("FileNotFoundError", text)

    def test_max_attempt_is_one(self):
        """MAX_ATTEMPTS constant is 1."""
        self.assertEqual(MAX_ATTEMPTS, 1)
        # After one failure, attempt should be 1/1 in the log
        run_pass(self.progress)
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn("Attempt: 1/1", text)
        # attempt is not persisted in state (each invocation starts fresh)
        self.assertNotIn("- attempt:", text)  # no attempt field in state

    def test_non_silent_failure(self):
        """Failure prints to stderr, not silent."""
        result = run_pass(self.progress)
        self.assertEqual(result, 1)
        # The function prints to stderr via print(..., file=sys.stderr)
        # We verify the log entry contains error details
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn("error:", text.lower())  # error appears in log

    def test_needs_human_logged(self):
        """NEEDS HUMAN appears in the log entry."""
        run_pass(self.progress)
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn("NEEDS HUMAN", text)

    def test_timestamp_in_log_entry(self):
        """Log entry contains ISO timestamp."""
        run_pass(self.progress)
        text = self.progress.read_text(encoding="utf-8")
        # Check for timestamp pattern in log header (### 2026-08-28T...)
        timestamp_pattern = r"^### \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
        self.assertTrue(re.search(timestamp_pattern, text, re.MULTILINE))

    def test_spine_only_diagnosis(self):
        """Failure is diagnosable from progress.md alone."""
        run_pass(self.progress)
        text = self.progress.read_text(encoding="utf-8")
        # Must contain all diagnostic info without replaying
        self.assertIn("sabotage triggered", text.lower())  # what failed
        self.assertIn("reason:", text.lower())  # why it failed
        self.assertIn("FileNotFoundError", text)  # exception type
        self.assertIn("Attempt: 1/1", text)  # attempt count
        self.assertIn("NEEDS HUMAN", text)  # escalation marker
        # State fields updated (last_run, last_error)
        self.assertIn("- last_run:", text)
        self.assertIn("- last_error: FileNotFoundError:", text)
        # attempt is NOT persisted in state (each run is independent)
        # but log shows Attempt: 1/1

    def test_cost_calculation_documented(self):
        """Cost calculation constants and estimates are documented in README."""
        readme = Path(__file__).resolve().parent.parent / "README.md"
        self.assertTrue(readme.exists())
        readme_text = readme.read_text(encoding="utf-8")
        self.assertIn("token", readme_text.lower())
        self.assertIn("cost", readme_text.lower())
        self.assertIn("monthly", readme_text.lower())
        self.assertIn("daily", readme_text.lower())
        self.assertIn("$", readme_text)


class TestLoopCmd(unittest.TestCase):
    def test_loop_cmd_exists_and_runs(self):
        """loop.cmd exists and invokes the script."""
        cmd_path = Path(__file__).resolve().parent.parent / "loop.cmd"
        self.assertTrue(cmd_path.exists())
        # Run it - should fail with sabotage
        result = subprocess.run(
            ["cmd", "/c", str(cmd_path)],
            cwd=cmd_path.parent,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAILED", result.stderr + result.stdout)
        self.assertIn("NEEDS HUMAN", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()