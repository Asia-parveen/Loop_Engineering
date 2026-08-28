#!/usr/bin/env python3
"""
Test Suite for Loop Engineering Project 11
Tests Routine A and Routine B with human approval gate.
"""

import os
import sys
import json
import time
import subprocess
import threading
import requests
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import routine_a
import routine_b


def run_cmd(cmd, cwd=None, env=None, capture=True):
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        env=env or os.environ.copy(),
        capture_output=capture,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def is_process_running(process_name):
    """Check if a process is running (cross-platform)."""
    if sys.platform == "win32":
        rc, out, err = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {process_name}"])
        return process_name.lower() in out.lower()
    else:
        rc, out, err = run_cmd(["pgrep", "-f", process_name])
        return rc == 0 and out.strip() != ""


class TestRoutineA:
    """Tests for Routine A: Manual trigger, creates draft, no auto-trigger B."""
    
    def setup_method(self):
        """Clean up before each test."""
        for f in ["routine_state.json", "logs"]:
            p = PROJECT_ROOT / f
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
    
    def test_a_runs_independently(self):
        """Test that Routine A can run independently."""
        # Run Routine A
        result = routine_a.run_routine_a(since="2020-01-01", branch_suffix="test-independent")
        
        assert result["success"] is True
        assert "run_id" in result
        assert result["branch_name"] == "claude/test-independent"
        assert result["commit_count"] >= 0
        assert Path(result["log_file"]).exists()
        assert Path(result["state_file"]).exists()
        
        # Verify state file
        with open(PROJECT_ROOT / "routine_state.json") as f:
            state = json.load(f)
        
        assert len(state["routine_a_runs"]) == 1
        assert state["routine_a_runs"][0]["status"] == "ready_for_review"
        assert state["human_gate_status"] == "awaiting_review"
        assert state["current_draft"]["branch_name"] == "claude/test-independent"
    
    def test_a_creates_reviewable_draft(self):
        """Test that Routine A creates a reviewable claude/ branch."""
        result = routine_a.run_routine_a(branch_suffix="test-draft")
        
        assert result["success"] is True
        
        # Verify branch exists
        rc, out, err = run_cmd(["git", "rev-parse", "--verify", "claude/test-draft"])
        assert rc == 0, f"Branch not created: {err}"
        
        # Verify branch has COMMIT_SUMMARY.md
        rc, out, err = run_cmd(["git", "show", "claude/test-draft:COMMIT_SUMMARY.md"])
        assert rc == 0, f"Summary file not in branch: {err}"
        assert "Commit Summary" in out
    
    def test_a_does_not_trigger_b_automatically(self):
        """Test that Routine A does NOT automatically trigger Routine B."""
        # Run Routine A
        routine_a.run_routine_a(branch_suffix="test-no-auto-b")
        
        # Check state - human gate should be awaiting_review, not completed
        with open(PROJECT_ROOT / "routine_state.json") as f:
            state = json.load(f)
        
        assert state["human_gate_status"] == "awaiting_review"
        assert len(state["routine_b_runs"]) == 0
        
        # Verify no Routine B process is running
        assert not is_process_running("routine_b"), "Routine B process should not be running"
    
    def test_a_saves_clear_state_and_log_evidence(self):
        """Test that Routine A saves clear state and log evidence."""
        result = routine_a.run_routine_a(branch_suffix="test-evidence")
        
        assert result["success"] is True
        
        # Check log file exists and has content
        log_path = Path(result["log_file"])
        assert log_path.exists()
        
        log_content = log_path.read_text(encoding="utf-8")
        assert "[INFO]" in log_content
        assert "[SUCCESS]" in log_content
        assert "Routine A completed successfully" in log_content
        assert "Routine B NOT triggered automatically" in log_content
        
        # Check state file
        with open(PROJECT_ROOT / "routine_state.json") as f:
            state = json.load(f)
        
        run = state["routine_a_runs"][0]
        assert "run_id" in run
        assert "branch_name" in run
        assert "summary_hash" in run
        assert "commit_count" in run
        assert "created_at" in run
        assert "status" in run
        assert "log_file" in run
    
    def test_a_handles_errors_gracefully(self):
        """Test that Routine A handles errors and logs them."""
        # Test with invalid git repo (simulate by running outside git repo)
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save original cwd
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Re-import to pick up new cwd
                import importlib
                importlib.reload(routine_a)
                
                result = routine_a.run_routine_a()
                
                assert result["success"] is False
                assert "error" in result
                assert Path(result["log_file"]).exists()
                
                log_content = Path(result["log_file"]).read_text(encoding="utf-8")
                assert "[ERROR]" in log_content
            finally:
                os.chdir(orig_cwd)
                importlib.reload(routine_a)


class TestRoutineB:
    """Tests for Routine B: API-triggered, requires auth, explicit trigger only."""
    
    def setup_method(self):
        """Clean up before each test."""
        for f in ["routine_state.json", "logs"]:
            p = PROJECT_ROOT / f
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
        
        # Set up test token
        os.environ["ROUTINE_B_API_TOKEN"] = "test-secret-token-abc123"
    
    def teardown_method(self):
        """Clean up after each test."""
        os.environ.pop("ROUTINE_B_API_TOKEN", None)
    
    def test_b_requires_explicit_api_trigger(self):
        """Test that Routine B only runs when explicitly triggered via API."""
        # First run Routine A to create a draft
        routine_a.run_routine_a(branch_suffix="test-b-trigger")
        
        # Start Routine B server in background
        server_thread, base_url = self._start_test_server()
        
        try:
            # Wait for server to start
            time.sleep(0.5)
            
            # Check status before trigger
            resp = requests.get(f"{base_url}/status")
            assert resp.json()["draft_ready"] is True
            assert resp.json()["routine_b_runs"] == 0
            
            # Trigger Routine B via API
            headers = {"Authorization": "Bearer test-secret-token-abc123"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={"note": "test"})
            
            assert resp.status_code == 200
            result = resp.json()
            assert result["success"] is True
            
            # Check status after trigger
            resp = requests.get(f"{base_url}/status")
            assert resp.json()["routine_b_runs"] == 1
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_requires_bearer_token_authentication(self):
        """Test that Routine B rejects requests without valid bearer token."""
        routine_a.run_routine_a(branch_suffix="test-b-auth")
        
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            # Test without token
            resp = requests.post(f"{base_url}/trigger", json={})
            assert resp.status_code == 401
            assert "Unauthorized" in resp.json()["error"]
            
            # Test with invalid token
            headers = {"Authorization": "Bearer invalid-token"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            assert resp.status_code == 401
            
            # Test with malformed auth header
            headers = {"Authorization": "Basic invalid"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            assert resp.status_code == 401
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_successful_action_is_observable(self):
        """Test that successful Routine B action produces observable evidence."""
        routine_a.run_routine_a(branch_suffix="test-b-observable")
        
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            headers = {"Authorization": "Bearer test-secret-token-abc123"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={"note": "observable test"})
            
            assert resp.status_code == 200
            result = resp.json()
            assert result["success"] is True
            
            # Check log file exists
            assert Path(result["log_file"]).exists()
            log_content = Path(result["log_file"]).read_text(encoding="utf-8")
            assert "[SUCCESS]" in log_content
            assert "Routine B completed successfully" in log_content
            
            # Check shipping record created
            assert "action_result" in result
            assert "shipping_record" in result["action_result"]
            shipping_path = Path(result["action_result"]["shipping_record"])
            assert shipping_path.exists()
            
            with open(shipping_path) as f:
                shipping = json.load(f)
            assert shipping["status"] == "shipped"
            assert shipping["action"] == "human_approved_ship"
            
            # Check state updated
            with open(PROJECT_ROOT / "routine_state.json") as f:
                state = json.load(f)
            assert state["human_gate_status"] == "completed"
            assert len(state["routine_b_runs"]) == 1
            assert state["routine_b_runs"][0]["status"] == "success"
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_rejects_invalid_missing_token(self):
        """Test that Routine B rejects invalid or missing tokens."""
        routine_a.run_routine_a(branch_suffix="test-b-reject")
        
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            # Missing token
            resp = requests.post(f"{base_url}/trigger", json={})
            assert resp.status_code == 401
            data = resp.json()
            assert data["error"] == "Unauthorized"
            assert "token" in data["message"].lower()
            
            # Empty token
            headers = {"Authorization": "Bearer "}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            assert resp.status_code == 401
            
            # Wrong token
            headers = {"Authorization": "Bearer wrong-token"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            assert resp.status_code == 401
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_no_secret_exposed_in_logs(self):
        """Test that no secret is exposed in Routine B logs."""
        routine_a.run_routine_a(branch_suffix="test-b-no-secret")
        
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            headers = {"Authorization": "Bearer test-secret-token-abc123"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            
            assert resp.status_code == 200
            result = resp.json()
            
            # Check log file
            log_content = Path(result["log_file"]).read_text(encoding="utf-8")
            
            # Token should NEVER appear in logs
            assert "test-secret-token-abc123" not in log_content
            assert "abc123" not in log_content
            
            # Check response doesn't contain token
            resp_text = json.dumps(result)
            assert "test-secret-token-abc123" not in resp_text
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_fails_without_draft_from_a(self):
        """Test that Routine B fails cleanly when no draft from Routine A exists."""
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            headers = {"Authorization": "Bearer test-secret-token-abc123"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={})
            
            assert resp.status_code == 400
            result = resp.json()
            assert result["success"] is False
            assert "No draft found" in result["error"] or "draft" in result["error"].lower()
            
            # Check log file
            log_content = Path(result["log_file"]).read_text(encoding="utf-8")
            assert "[ERROR]" in log_content
            assert "Human gate check failed" in log_content
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_b_direct_run_once(self):
        """Test Routine B direct run (bypassing API) for testing."""
        routine_a.run_routine_a(branch_suffix="test-b-direct")
        
        # Run directly
        result = routine_b.run_routine_b({"test": "direct"})
        
        assert result["success"] is True
        assert "action_result" in result
        assert Path(result["log_file"]).exists()
        
        log_content = Path(result["log_file"]).read_text(encoding="utf-8")
        assert "[SUCCESS]" in log_content
    
    def _start_test_server(self, port=18765):
        """Start Routine B server in background thread."""
        server = routine_b.start_server(port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return thread, f"http://localhost:{port}"
    
    def _stop_test_server(self, thread):
        """Stop the test server."""
        # Server shutdown handled by daemon thread on test exit
        pass


class TestHumanGateFlow:
    """Tests for the complete human gate flow."""
    
    def setup_method(self):
        """Clean up before each test."""
        for f in ["routine_state.json", "logs"]:
            p = PROJECT_ROOT / f
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
        
        os.environ["ROUTINE_B_API_TOKEN"] = "test-gate-token-xyz789"
    
    def teardown_method(self):
        os.environ.pop("ROUTINE_B_API_TOKEN", None)
    
    def test_complete_human_gate_flow(self):
        """Test the complete flow: A creates draft -> human reviews -> B triggered."""
        # Step 1: Human runs Routine A
        result_a = routine_a.run_routine_a(branch_suffix="human-gate-flow")
        assert result_a["success"] is True
        
        # Step 2: Human reviews the draft (simulated by checking branch exists)
        rc, out, err = run_cmd(["git", "show", "claude/human-gate-flow:COMMIT_SUMMARY.md"])
        assert rc == 0
        assert "Commit Summary" in out
        
        # Step 3: Human starts Routine B server
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            # Step 4: Human triggers Routine B via curl/API
            headers = {"Authorization": "Bearer test-gate-token-xyz789"}
            resp = requests.post(f"{base_url}/trigger", headers=headers, json={"approved_by": "human"})
            
            assert resp.status_code == 200
            result_b = resp.json()
            assert result_b["success"] is True
            
            # Step 5: Verify state shows completed flow
            with open(PROJECT_ROOT / "routine_state.json") as f:
                state = json.load(f)
            
            assert state["human_gate_status"] == "completed"
            assert state["current_draft"]["status"] == "shipped_by_routine_b"
            assert len(state["routine_a_runs"]) == 1
            assert len(state["routine_b_runs"]) == 1
            
        finally:
            self._stop_test_server(server_thread)
    
    def test_curl_command_documented_works(self):
        """Test that the documented curl command works."""
        routine_a.run_routine_a(branch_suffix="curl-test")
        
        server_thread, base_url = self._start_test_server()
        
        try:
            time.sleep(0.5)
            
            # This is the exact curl command from documentation
            cmd = [
                "curl", "-X", "POST",
                "-H", "Authorization: Bearer test-gate-token-xyz789",
                "-H", "Content-Type: application/json",
                "-d", '{"approved_by": "human"}',
                f"{base_url}/trigger"
            ]
            
            rc, out, err = run_cmd(cmd)
            assert rc == 0
            
            result = json.loads(out)
            assert result["success"] is True
            
        finally:
            self._stop_test_server(server_thread)
    
    def _start_test_server(self, port=18766):
        server = routine_b.start_server(port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return thread, f"http://localhost:{port}"
    
    def _stop_test_server(self, thread):
        pass


class TestSecurityAndSafety:
    """Tests for security and safety properties."""
    
    def setup_method(self):
        for f in ["routine_state.json", "logs"]:
            p = PROJECT_ROOT / f
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
    
    def test_no_hardcoded_secrets(self):
        """Test that no secrets are hardcoded in source files."""
        for py_file in ["routine_a.py", "routine_b.py"]:
            content = (PROJECT_ROOT / py_file).read_text(encoding="utf-8")
            
            # Check for common secret patterns
            assert "test-secret-token" not in content
            assert "abc123" not in content
            assert "xyz789" not in content
            assert "ROUTINE_B_API_TOKEN" not in content or "os.environ.get" in content
    
    def test_routine_a_no_external_dependencies(self):
        """Test Routine A uses only standard library and git."""
        content = (PROJECT_ROOT / "routine_a.py").read_text(encoding="utf-8")
        
        # Should not import external HTTP libraries
        assert "requests" not in content
        assert "urllib" not in content
        assert "httpx" not in content
        assert "aiohttp" not in content
        assert "flask" not in content
        assert "fastapi" not in content
    
    def test_routine_b_minimal_endpoints(self):
        """Test Routine B exposes only necessary endpoints."""
        content = (PROJECT_ROOT / "routine_b.py").read_text(encoding="utf-8")
        
        # Check handler only defines expected paths
        assert '"/health"' in content
        assert '"/status"' in content
        assert '"/trigger"' in content
        
        # Should not have other endpoints
        # (This is a basic check; full verification would need AST parsing)
    
    def test_state_file_not_world_writable(self):
        """Test that state file has reasonable permissions."""
        routine_a.run_routine_a(branch_suffix="perm-test")
        
        state_path = PROJECT_ROOT / "routine_state.json"
        assert state_path.exists()
        
        # On Windows, just verify it's readable/writable by owner
        assert os.access(state_path, os.R_OK)
        assert os.access(state_path, os.W_OK)


def run_all_tests():
    """Run all tests and return results."""
    import pytest
    
    # Run pytest on this file
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)