import os
import subprocess
import sys
import pytest


def test_failure_without_env_var():
    """Test that the script fails when DUMMY_SECRET_TOKEN is not set."""
    # Ensure the env var is not set
    env = os.environ.copy()
    env.pop("DUMMY_SECRET_TOKEN", None)
    
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should fail with exit code 1
    assert result.returncode == 1
    
    # Should print error to stderr
    assert "ERROR:" in result.stderr
    assert "Secret token not found" in result.stderr
    assert "DUMMY_SECRET_TOKEN" in result.stderr
    assert "Do not look for a .env file" in result.stderr
    
    # Should not print the actual token value anywhere
    assert "dummy-token-abc123xyz" not in result.stdout
    assert "dummy-token-abc123xyz" not in result.stderr


def test_failure_explicit_empty_env_var():
    """Test that the script fails when DUMMY_SECRET_TOKEN is explicitly set to empty."""
    env = os.environ.copy()
    env["DUMMY_SECRET_TOKEN"] = ""
    
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert "Secret token not found" in result.stderr