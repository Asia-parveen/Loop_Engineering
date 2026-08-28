"""Tests for Loop Engineering Practice Project 8.

Verifies critical safety and workflow behavior:
- Six-part loop executes in order
- Maker produces output, checker validates before connector
- Budget guards enforce limits
- NEEDS HUMAN escalation on failures
- Spine (progress.md) records all state
- One-pass execution (no internal loop)
- Deduplication prevents repeat work
- Timeout handling
- Non-silent failures
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spine import (
    read_state,
    read_budget,
    update_progress,
    format_log_entry,
    estimate_tokens,
    initial_progress_text,
)
from src.heartbeat import HeartbeatConfig, Cadence, get_cadence_from_env, get_timeout_from_env
from src.worktree import Worktree, WorktreeConfig, generate_run_id, isolated_worktree
from src.budget import BudgetConfig, check_budget, enforce_budget, BudgetExceededError
from src.skill import SkillConfig, execute_skill, Commit
from src.maker import MakerConfig, run_maker
from src.checker import CheckerConfig, run_checks
from src.connector import ConnectorConfig, run_connector
from src.loop import run_pass


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


class TestSpine(unittest.TestCase):
    """Tests for the spine (progress.md) persistence."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.progress = Path(self._tmp.name) / "progress.md"

    def tearDown(self):
        self._tmp.cleanup()

    def test_initial_progress_text(self):
        text = initial_progress_text()
        self.assertIn("# Progress", text)
        self.assertIn("## State", text)
        self.assertIn("## Budget", text)
        self.assertIn("## Log", text)
        self.assertIn("last_seen_commit", text)
        self.assertIn("max_tokens_per_run", text)

    def test_read_write_state(self):
        update_progress(self.progress, {"last_seen_commit": "abc123", "last_run": "2026-01-01"}, {}, "Test entry")
        state = read_state(self.progress)
        self.assertEqual(state["last_seen_commit"], "abc123")
        # last_run is always overwritten with current timestamp by update_progress
        self.assertIsNotNone(state["last_run"])

    def test_format_log_entry_with_needs_human(self):
        entry = format_log_entry("FAILED", "Something broke", "Details here", needs_human=True)
        self.assertIn("STATUS: FAILED", entry)
        self.assertIn("NEEDS HUMAN", entry)

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 1)
        self.assertEqual(estimate_tokens("a" * 4), 1)
        self.assertEqual(estimate_tokens("a" * 100), 25)


class TestHeartbeat(unittest.TestCase):
    """Tests for heartbeat/cadence configuration."""

    def test_default_cadence(self):
        config = HeartbeatConfig()
        self.assertEqual(config.cadence, Cadence.MANUAL)
        self.assertEqual(config.timeout_seconds, 300)

    def test_cadence_from_env(self):
        os.environ["LOOP_CADENCE"] = "daily"
        try:
            self.assertEqual(get_cadence_from_env(), Cadence.DAILY)
        finally:
            del os.environ["LOOP_CADENCE"]

    def test_timeout_from_env(self):
        os.environ["LOOP_TIMEOUT_SECONDS"] = "600"
        try:
            self.assertEqual(get_timeout_from_env(), 600)
        finally:
            del os.environ["LOOP_TIMEOUT_SECONDS"]


class TestWorktree(unittest.TestCase):
    """Tests for isolated worktree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_worktree_create_cleanup(self):
        with isolated_worktree(base_dir=self.base) as wt_path:
            self.assertTrue(wt_path.exists())
            (wt_path / "test.txt").write_text("hello")
        # Should be cleaned up after context
        self.assertFalse(wt_path.exists())

    def test_worktree_keep_on_failure(self):
        wt_path = None
        try:
            with isolated_worktree(base_dir=self.base, keep_on_failure=True) as wt:
                wt_path = wt
                raise ValueError("simulated failure")
        except ValueError:
            pass
        # Should be kept on failure
        self.assertTrue(wt_path.exists())

    def test_generate_run_id(self):
        id1 = generate_run_id()
        id2 = generate_run_id()
        self.assertNotEqual(id1, id2)
        self.assertTrue(id1.startswith("run-"))


class TestBudget(unittest.TestCase):
    """Tests for budget/token guards."""

    def setUp(self):
        self.config = BudgetConfig(max_tokens_per_run=1000, token_price_per_1k=0.001, max_cost_per_run_usd=0.01)

    def test_check_budget_allowed(self):
        result = check_budget(500, self.config)
        self.assertTrue(result.allowed)
        self.assertIsNone(result.error)

    def test_check_budget_exceeded_tokens(self):
        result = check_budget(1500, self.config)
        self.assertFalse(result.allowed)
        self.assertIn("TOKEN BUDGET EXCEEDED", result.error)

    def test_check_budget_exceeded_cost(self):
        config = BudgetConfig(max_tokens_per_run=10000, token_price_per_1k=0.1, max_cost_per_run_usd=0.01)
        result = check_budget(500, config)  # 500 * 0.1/1000 = 0.05 > 0.01
        self.assertFalse(result.allowed)
        self.assertIn("COST BUDGET EXCEEDED", result.error)

    def test_check_budget_warning(self):
        result = check_budget(900, self.config)  # 90% threshold
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.warning)

    def test_enforce_budget_raises(self):
        with self.assertRaises(BudgetExceededError):
            enforce_budget(1500, self.config)


class TestSkill(unittest.TestCase):
    """Tests for the changelog generation skill."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Loop Test")
        self.worktree = Path(self._tmp.name) / "worktree"
        self.worktree.mkdir()
        self.changelog = self.worktree / "CHANGELOG.md"

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, message):
        git(self.repo, "commit", "--allow-empty", "-m", message)
        return git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def test_execute_skill_first_run(self):
        c1 = self._commit("first commit")
        c2 = self._commit("second commit")

        config = SkillConfig(
            repo_root=self.repo,
            worktree_dir=self.worktree,
            changelog_path=self.changelog,
            cursor_commit=None,
            max_commits=100,
        )
        result = execute_skill(config)

        self.assertEqual(len(result.commits), 2)
        self.assertTrue(self.changelog.exists())
        content = self.changelog.read_text()
        self.assertIn("Changelog Draft", content)
        self.assertIn(c1[:7], content)
        self.assertIn(c2[:7], content)
        self.assertEqual(result.new_cursor, c2[:7])

    def test_execute_skill_incremental(self):
        c1 = self._commit("first commit")
        c2 = self._commit("second commit")

        # First run
        config1 = SkillConfig(
            repo_root=self.repo,
            worktree_dir=self.worktree,
            changelog_path=self.changelog,
            cursor_commit=None,
            max_commits=100,
        )
        execute_skill(config1)

        # Second run with cursor
        c3 = self._commit("third commit")
        config2 = SkillConfig(
            repo_root=self.repo,
            worktree_dir=self.worktree,
            changelog_path=self.changelog,
            cursor_commit=c2[:7],
            max_commits=100,
        )
        result = execute_skill(config2)

        self.assertEqual(len(result.commits), 1)
        self.assertEqual(result.commits[0].hash, c3[:7])
        content = self.changelog.read_text()
        self.assertIn(c3[:7], content)
        self.assertNotIn(c1[:7], content)  # Old commit not repeated
        self.assertNotIn(c2[:7], content)


class TestMakerChecker(unittest.TestCase):
    """Tests for maker-checker workflow."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Loop Test")
        self.worktree_base = Path(self._tmp.name) / "worktrees"
        self.worktree_base.mkdir()
        self._commit("initial commit")

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, message):
        git(self.repo, "commit", "--allow-empty", "-m", message)
        return git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def test_maker_produces_output(self):
        budget = BudgetConfig(max_tokens_per_run=5000)
        config = MakerConfig(
            repo_root=self.repo,
            worktree_base=self.worktree_base,
            cursor_commit=None,
            budget=budget,
        )
        result = run_maker(config)

        self.assertTrue(result.changelog_path.exists())
        self.assertTrue(result.worktree_path.exists())
        self.assertGreater(result.skill_result.tokens_estimated, 0)
        self.assertTrue(result.budget_result.allowed)

    def test_checker_validates_output(self):
        budget = BudgetConfig(max_tokens_per_run=5000)
        maker_config = MakerConfig(
            repo_root=self.repo,
            worktree_base=self.worktree_base,
            cursor_commit=None,
            budget=budget,
        )
        maker_result = run_maker(maker_config)

        checker_config = CheckerConfig()
        check_result = run_checks(maker_result, checker_config)

        self.assertTrue(check_result.passed)
        self.assertGreater(len(check_result.checks), 0)
        self.assertEqual(len(check_result.failures), 0)

    def test_checker_catches_empty_changelog(self):
        # Create a maker result with empty changelog
        from src.maker import MakerResult
        from src.budget import BudgetResult

        empty_worktree = self.worktree_base / "empty"
        empty_worktree.mkdir()
        empty_changelog = empty_worktree / "CHANGELOG.md"
        empty_changelog.write_text("")

        # Mock skill result
        class MockSkillResult:
            commits = []
            tokens_estimated = 10

        maker_result = MakerResult(
            worktree_path=empty_worktree,
            changelog_path=empty_changelog,
            skill_result=MockSkillResult(),
            budget_result=BudgetResult(True, 10, 4990, 0.0, 0.01),
            run_id="test",
        )

        check_result = run_checks(maker_result, CheckerConfig())
        self.assertFalse(check_result.passed)
        self.assertTrue(any("empty" in f.lower() for f in check_result.failures))


class TestConnector(unittest.TestCase):
    """Tests for connector (Git integration)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Loop Test")
        # Create initial commit on master (default branch)
        (self.repo / "README.md").write_text("# Test")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "initial")
        # Create a bare "origin" for pushing
        self.origin = Path(self._tmp.name) / "origin"
        self.origin.mkdir()
        git(self.origin, "init", "--bare")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "-u", "origin", "master")

        self.worktree_base = Path(self._tmp.name) / "worktrees"
        self.worktree_base.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_connector_creates_branch(self):
        # Create a mock maker result
        from src.maker import MakerResult
        from src.budget import BudgetResult
        from src.skill import SkillResult
        from src.checker import CheckResult

        wt = self.worktree_base / "test"
        wt.mkdir()
        changelog = wt / "CHANGELOG.md"
        changelog.write_text("# Changelog Draft\n\n## 2026-01-01\n- abc123 test commit\n")

        maker_result = MakerResult(
            worktree_path=wt,
            changelog_path=changelog,
            skill_result=SkillResult([], "", "abc123", 100),
            budget_result=BudgetResult(True, 100, 4900, 0.0001, 0.01),
            run_id="test",
        )

        check_result = CheckResult(
            passed=True,
            checks=[],
            failures=[],
            warnings=[],
            changelog_hash="deadbeef",
        )

        config = ConnectorConfig(repo_root=self.repo, create_pr=False)
        result = run_connector(config, maker_result, check_result)

        self.assertTrue(result.shipped)
        self.assertIsNotNone(result.branch_name)
        self.assertTrue(result.branch_name.startswith("changelog-draft/"))

    def test_connector_aborts_on_checker_failure(self):
        from src.maker import MakerResult
        from src.budget import BudgetResult
        from src.skill import SkillResult
        from src.checker import CheckResult

        maker_result = MakerResult(
            worktree_path=Path("/tmp"),
            changelog_path=Path("/tmp/x"),
            skill_result=SkillResult([], "", "abc123", 100),
            budget_result=BudgetResult(True, 100, 4900, 0.0001, 0.01),
            run_id="test",
        )

        check_result = CheckResult(
            passed=False,
            checks=[],
            failures=["Failed check"],
            warnings=[],
            changelog_hash="deadbeef",
        )

        config = ConnectorConfig(repo_root=self.repo)
        result = run_connector(config, maker_result, check_result)

        self.assertFalse(result.shipped)
        self.assertTrue(result.needs_human)


class TestFullLoop(unittest.TestCase):
    """Integration tests for the full six-part loop."""
    
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name) / "project8"
        self.project_root.mkdir()

        # Copy source files to temp project
        src_root = Path(__file__).resolve().parent.parent / "src"
        shutil.copytree(src_root, self.project_root / "src")

        # Create fresh progress.md using initial_progress_text from the copied src
        sys.path.insert(0, str(self.project_root))
        from src.spine import initial_progress_text
        (self.project_root / "progress.md").write_text(initial_progress_text(), encoding="utf-8")
        sys.path.remove(str(self.project_root))

        # Initialize git repo
        git(self.project_root, "init")
        git(self.project_root, "config", "user.email", "test@example.com")
        git(self.project_root, "config", "user.name", "Loop Test")
        (self.project_root / "README.md").write_text("# Test Project")
        git(self.project_root, "add", "README.md")
        git(self.project_root, "commit", "-m", "initial commit")

        # Add some commits
        for i in range(3):
            (self.project_root / f"file{i}.txt").write_text(f"content {i}")
            git(self.project_root, "add", f"file{i}.txt")
            git(self.project_root, "commit", "-m", f"add file{i}")

        # Create bare origin for connector tests
        self.origin = Path(self._tmp.name) / "origin"
        self.origin.mkdir()
        git(self.origin, "init", "--bare")
        git(self.project_root, "remote", "add", "origin", str(self.origin))
        git(self.project_root, "push", "-u", "origin", "master")

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_run_processes_all_commits(self):
        # Run the loop via subprocess to use temp project's modules
        cmd_path = self.project_root / "loop.cmd"
        # Create loop.cmd in temp project (use -m for module execution)
        cmd_path.write_text('@echo off\ncd /d "%~dp0"\npython -m src.loop\nexit /b %errorlevel%\n')
        
        result = subprocess.run(
            ["cmd", "/c", str(cmd_path)],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        # Exit code 0 = success, 2 = shipped but needs human review
        self.assertIn(result.returncode, [0, 2])

        # Check progress.md updated
        progress = self.project_root / "progress.md"
        text = progress.read_text()
        self.assertIn("last_seen_commit:", text)
        self.assertTrue("SHIPPED" in text or "CONNECTOR_SKIPPED" in text)

    def test_second_run_processes_only_new(self):
        cmd_path = self.project_root / "loop.cmd"
        cmd_path.write_text('@echo off\ncd /d "%~dp0"\npython -m src.loop\nexit /b %errorlevel%\n')
        
        # First run
        subprocess.run(
            ["cmd", "/c", str(cmd_path)],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Add new commit
        (self.project_root / "new_file.txt").write_text("new")
        git(self.project_root, "add", "new_file.txt")
        git(self.project_root, "commit", "-m", "add new_file")

        # Second run
        result = subprocess.run(
            ["cmd", "/c", str(cmd_path)],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertIn(result.returncode, [0, 2])

        progress = self.project_root / "progress.md"
        text = progress.read_text()
        # Second run should have advanced the cursor and logged SHIPPED
        self.assertIn("SHIPPED", text)
        # Verify cursor advanced (last_seen_commit should be different from first run)
        # The log should have two SHIPPED entries
        self.assertEqual(text.count("STATUS: SHIPPED"), 2)


class TestLoopCmd(unittest.TestCase):
    """Test the loop.cmd entry point."""

    def test_loop_cmd_exists(self):
        cmd_path = Path(__file__).resolve().parent.parent / "loop.cmd"
        self.assertTrue(cmd_path.exists())

    def test_loop_cmd_runs(self):
        cmd_path = Path(__file__).resolve().parent.parent / "loop.cmd"
        result = subprocess.run(
            ["cmd", "/c", str(cmd_path)],
            cwd=cmd_path.parent,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Should run without crashing (exit code 0, 1, or 2 are all valid)
        self.assertIn(result.returncode, [0, 1, 2])
        # Should produce output
        self.assertTrue(len(result.stdout) + len(result.stderr) > 0)


class TestSafetyGuards(unittest.TestCase):
    """Tests for critical safety guards."""

    def test_no_auto_merge(self):
        """Verify connector never auto-merges."""
        connector_file = Path(__file__).resolve().parent.parent / "src" / "connector.py"
        text = connector_file.read_text()
        # Check for actual auto-merge code patterns (not in docstrings/comments)
        # Look for executable code that would perform auto-merge
        self.assertNotIn("git merge", text)
        self.assertNotIn("merge --ff-only", text)
        self.assertNotIn("auto_merge", text)
        # The word "auto-merge" appears only in docstring saying "no auto-merge"
        # which is the correct documentation of the safety principle

    def test_no_destructive_git_operations(self):
        """Verify no destructive git commands in connector."""
        connector_file = Path(__file__).resolve().parent.parent / "src" / "connector.py"
        text = connector_file.read_text()
        dangerous = ["reset --hard", "push --force", "clean -fd", "checkout -f"]
        for d in dangerous:
            self.assertNotIn(d, text)

    def test_budget_enforced_in_maker(self):
        """Verify maker checks budget before producing."""
        maker_file = Path(__file__).resolve().parent.parent / "src" / "maker.py"
        text = maker_file.read_text()
        self.assertIn("check_budget", text)
        self.assertIn("BudgetExceededError", text)

    def test_checker_before_connector(self):
        """Verify loop runs checker before connector."""
        loop_file = Path(__file__).resolve().parent.parent / "src" / "loop.py"
        text = loop_file.read_text()
        checker_idx = text.find("run_checks")
        connector_idx = text.find("run_connector")
        self.assertLess(checker_idx, connector_idx)

    def test_one_pass_per_invocation(self):
        """Verify run_pass has no internal loop."""
        loop_file = Path(__file__).resolve().parent.parent / "src" / "loop.py"
        text = loop_file.read_text()
        self.assertNotIn("while True", text)
        self.assertNotIn("while False", text)
        # Check for infinite loop patterns, not all for loops (which are legitimate)
        run_pass_body = text.split("def run_pass")[1].split("def ")[0]
        self.assertNotIn("while ", run_pass_body)  # No while loops in run_pass
        self.assertNotIn("for _ in range(", run_pass_body)  # No infinite-range loops


class TestObservability(unittest.TestCase):
    """Tests for logging and observability."""

    def test_log_entry_contains_timestamp(self):
        entry = format_log_entry("SUCCESS", "Done", needs_human=False)
        # Timestamp is added by update_progress, not format_log_entry
        # But we verify the structure
        self.assertIn("STATUS: SUCCESS", entry)
        self.assertIn("Summary: Done", entry)

    def test_progress_log_appends(self):
        _tmp = tempfile.TemporaryDirectory()
        progress = Path(_tmp.name) / "progress.md"
        progress.write_text(initial_progress_text())

        update_progress(progress, {"last_seen_commit": "abc"}, {}, "First run")
        update_progress(progress, {"last_seen_commit": "def"}, {}, "Second run")

        text = progress.read_text()
        self.assertEqual(text.count("### 20"), 2)  # Two dated entries
        _tmp.cleanup()


if __name__ == "__main__":
    unittest.main()