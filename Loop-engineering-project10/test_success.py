import os
import subprocess
import sys


def test_success_with_env_var():
    """Test that the script succeeds when DUMMY_SECRET_TOKEN is set via environment variable."""
    env = os.environ.copy()
    env["DUMMY_SECRET_TOKEN"] = "dummy-token-abc123xyz"
    
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should succeed with exit code 0
    assert result.returncode == 0
    
    # Should print success message with token length (not the token itself)
    assert "Token retrieved successfully" in result.stdout
    assert "length: 21" in result.stdout
    
    # Should not print the actual token value anywhere
    assert "dummy-token-abc123xyz" not in result.stdout
    assert "dummy-token-abc123xyz" not in result.stderr
    assert "abc123" not in result.stdout
    assert "abc123" not in result.stderr


def test_success_with_different_token():
    """Test that the script works with a different token value."""
    env = os.environ.copy()
    env["DUMMY_SECRET_TOKEN"] = "another-secret-token-456"
    
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0
    assert "Token retrieved successfully" in result.stdout
    assert "length: 24" in result.stdout
    assert "another-secret-token-456" not in result.stdout
    assert "another-secret-token-456" not in result.stderr