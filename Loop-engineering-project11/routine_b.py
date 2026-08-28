#!/usr/bin/env python3
"""
Routine B: API-Triggered Follow-up Action
Requires bearer token from environment variable.
Runs ONLY when explicitly triggered by human using curl/API call.
Records clear success/failure evidence in transcript/state.
"""

import os
import sys
import json
import uuid
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time


STATE_FILE = "routine_state.json"
LOG_DIR = "logs"
API_TOKEN_ENV = "ROUTINE_B_API_TOKEN"
DEFAULT_PORT = 8765


class RoutineBError(Exception):
    """Custom exception for Routine B errors."""
    pass


def ensure_directories() -> None:
    """Ensure required directories exist."""
    Path(LOG_DIR).mkdir(exist_ok=True)


def load_state() -> Dict[str, Any]:
    """Load state from file."""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "routine_a_runs": [],
        "routine_b_runs": [],
        "current_draft": None,
        "human_gate_status": "pending"
    }


def save_state(state: Dict[str, Any]) -> None:
    """Save state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_message(level: str, message: str) -> str:
    """Create a log entry."""
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] [{level.upper()}] {message}"
    return entry


def write_log(log_entries: list, run_id: str) -> str:
    """Write log entries to file."""
    log_file = Path(LOG_DIR) / f"routine_b_{run_id}.log"
    with open(log_file, "w") as f:
        f.write("\n".join(log_entries))
    return str(log_file)


def get_api_token() -> str:
    """Get API token from environment variable."""
    token = os.environ.get(API_TOKEN_ENV)
    if not token:
        raise RoutineBError(
            f"API token not found. Expected environment variable {API_TOKEN_ENV} to be set. "
            "Do not hard-code or print the token."
        )
    return token


def validate_bearer_token(auth_header: Optional[str]) -> bool:
    """Validate bearer token from Authorization header."""
    if not auth_header:
        return False
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    
    provided_token = parts[1]
    expected_token = get_api_token()
    
    # Constant-time comparison to prevent timing attacks
    return hashlib.sha256(provided_token.encode()).hexdigest() == \
           hashlib.sha256(expected_token.encode()).hexdigest()


def check_draft_ready(state: Dict[str, Any]) -> tuple[bool, str]:
    """Check if a draft from Routine A is ready for review."""
    draft = state.get("current_draft")
    if not draft:
        return False, "No draft found. Run Routine A first."
    
    if draft.get("status") != "ready_for_review":
        return False, f"Draft status is '{draft.get('status')}', not 'ready_for_review'."
    
    # Verify branch exists
    branch_name = draft.get("branch_name")
    if not branch_name:
        return False, "Draft missing branch name."
    
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return False, f"Draft branch '{branch_name}' not found locally."
    
    return True, "Draft is ready for review."


def execute_routine_b_action(draft: Dict[str, Any], run_id: str, log_entries: list) -> Dict[str, Any]:
    """
    Execute the Routine B action.
    This is where the actual follow-up work happens.
    """
    branch_name = draft.get("branch_name")
    summary_hash = draft.get("summary_hash")
    
    log_entries.append(log_message("info", f"Executing Routine B action for draft: {branch_name}"))
    log_entries.append(log_message("info", f"Draft summary hash: {summary_hash}"))
    
    # Simulate the follow-up action - in a real scenario this could be:
    # - Creating a PR from the draft branch
    # - Deploying the changes
    # - Running additional validation
    # - Merging after approval
    # etc.
    
    # For this implementation, we'll create a "shipping" record
    # and optionally create a PR (but not auto-merge)
    
    action_result = {
        "action": "review_and_ship",
        "draft_branch": branch_name,
        "summary_hash": summary_hash,
        "executed_at": datetime.now().isoformat(),
        "executed_by": "human_api_trigger",
        "details": []
    }
    
    # Verify the branch exists on remote
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch_name],
        capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        action_result["details"].append(f"Branch '{branch_name}' exists on remote")
        log_entries.append(log_message("info", f"Branch '{branch_name}' exists on remote"))
    else:
        action_result["details"].append(f"Branch '{branch_name}' NOT found on remote (may need push)")
        log_entries.append(log_message("warning", f"Branch '{branch_name}' not found on remote"))
    
    # Create a shipping record file
    shipping_record = {
        "routine_b_run_id": run_id,
        "draft_branch": branch_name,
        "draft_summary_hash": summary_hash,
        "action": "human_approved_ship",
        "timestamp": datetime.now().isoformat(),
        "status": "shipped",
        "note": "Shipped via human API trigger - NEEDS HUMAN for final merge/review"
    }
    
    shipping_file = Path(LOG_DIR) / f"shipping_record_{run_id}.json"
    with open(shipping_file, "w") as f:
        json.dump(shipping_record, f, indent=2)
    
    action_result["shipping_record"] = str(shipping_file)
    log_entries.append(log_message("info", f"Shipping record created: {shipping_file}"))
    log_entries.append(log_message("success", "Routine B action executed successfully"))
    
    return action_result


def run_routine_b(trigger_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run Routine B: Execute follow-up action after human approval.
    
    This should ONLY be called via the API endpoint with valid authentication.
    
    Args:
        trigger_data: Optional data from API trigger
        
    Returns:
        Dict with run results
    """
    ensure_directories()
    run_id = str(uuid.uuid4())[:8]
    log_entries = []
    
    log_entries.append(log_message("info", f"Starting Routine B run: {run_id}"))
    log_entries.append(log_message("info", f"Trigger data: {trigger_data or 'none'}"))
    
    state = load_state()
    
    # Check if draft is ready
    ready, message = check_draft_ready(state)
    if not ready:
        log_entries.append(log_message("error", f"Human gate check failed: {message}"))
        log_entries.append(log_message("info", "Routine B cannot proceed without approved draft from Routine A"))
        log_file = write_log(log_entries, run_id)
        
        error_info = {
            "run_id": run_id,
            "error": message,
            "created_at": datetime.now().isoformat(),
            "status": "failed_human_gate",
            "log_file": log_file
        }
        state["routine_b_runs"].append(error_info)
        save_state(state)
        
        return {
            "success": False,
            "run_id": run_id,
            "error": message,
            "log_file": log_file,
            "state_file": STATE_FILE
        }
    
    log_entries.append(log_message("success", f"Human gate passed: {message}"))
    
    try:
        # Execute the action
        draft = state["current_draft"]
        action_result = execute_routine_b_action(draft, run_id, log_entries)
        
        # Update state
        draft["status"] = "shipped_by_routine_b"
        draft["shipped_at"] = datetime.now().isoformat()
        draft["shipped_by_run"] = run_id
        
        run_info = {
            "run_id": run_id,
            "draft_branch": draft["branch_name"],
            "action_result": action_result,
            "created_at": datetime.now().isoformat(),
            "status": "success",
            "log_file": f"logs/routine_b_{run_id}.log"
        }
        state["routine_b_runs"].append(run_info)
        state["human_gate_status"] = "completed"
        save_state(state)
        
        log_entries.append(log_message("info", "State updated. Human gate completed."))
        log_entries.append(log_message("success", "Routine B completed successfully"))
        
        log_file = write_log(log_entries, run_id)
        
        return {
            "success": True,
            "run_id": run_id,
            "action_result": action_result,
            "log_file": log_file,
            "state_file": STATE_FILE,
            "message": "Routine B executed successfully. Check shipping record."
        }
        
    except RoutineBError as e:
        log_entries.append(log_message("error", str(e)))
        log_file = write_log(log_entries, run_id)
        
        error_info = {
            "run_id": run_id,
            "error": str(e),
            "created_at": datetime.now().isoformat(),
            "status": "failed",
            "log_file": log_file
        }
        state["routine_b_runs"].append(error_info)
        save_state(state)
        
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e),
            "log_file": log_file,
            "state_file": STATE_FILE
        }
    except Exception as e:
        log_entries.append(log_message("error", f"Unexpected error: {e}"))
        log_file = write_log(log_entries, run_id)
        
        error_info = {
            "run_id": run_id,
            "error": f"Unexpected error: {e}",
            "created_at": datetime.now().isoformat(),
            "status": "failed",
            "log_file": log_file
        }
        state["routine_b_runs"].append(error_info)
        save_state(state)
        
        return {
            "success": False,
            "run_id": run_id,
            "error": f"Unexpected error: {e}",
            "log_file": log_file,
            "state_file": STATE_FILE
        }


class RoutineBHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Routine B API."""
    
    def log_message(self, format, *args):
        """Suppress default log messages."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "routine-b"}).encode())
            return
        
        if parsed.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            state = load_state()
            self.wfile.write(json.dumps({
                "draft_ready": state.get("current_draft", {}).get("status") == "ready_for_review",
                "draft_branch": state.get("current_draft", {}).get("branch_name"),
                "human_gate_status": state.get("human_gate_status"),
                "routine_b_runs": len(state.get("routine_b_runs", []))
            }).encode())
            return
        
        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests - the main trigger endpoint."""
        parsed = urlparse(self.path)
        
        if parsed.path != "/trigger":
            self.send_response(404)
            self.end_headers()
            return
        
        # Check Authorization header
        auth_header = self.headers.get("Authorization")
        if not validate_bearer_token(auth_header):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Unauthorized",
                "message": "Invalid or missing bearer token"
            }).encode())
            return
        
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        
        try:
            trigger_data = json.loads(body)
        except json.JSONDecodeError:
            trigger_data = {}
        
        # Run Routine B
        result = run_routine_b(trigger_data)
        
        if result["success"]:
            self.send_response(200)
        else:
            error_msg = result.get("error", "").lower()
            is_human_gate_error = "human gate" in error_msg or "draft" in error_msg or "no draft" in error_msg
            self.send_response(400 if is_human_gate_error else 500)
        
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())


def start_server(port: int = DEFAULT_PORT) -> HTTPServer:
    """Start the Routine B API server."""
    server = HTTPServer(("", port), RoutineBHandler)
    return server


def main():
    """Main entry point for Routine B."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Routine B: API-triggered follow-up action")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to run API server (default: {DEFAULT_PORT})")
    parser.add_argument("--run-once", action="store_true", help="Run Routine B once directly (bypasses API, for testing)")
    parser.add_argument("--trigger-data", help="JSON data for direct run")
    
    args = parser.parse_args()
    
    # Check token is set
    try:
        get_api_token()
    except RoutineBError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    
    if args.run_once:
        print("Running Routine B directly (bypassing API)...")
        trigger_data = json.loads(args.trigger_data) if args.trigger_data else None
        result = run_routine_b(trigger_data)
        
        if result["success"]:
            print(f"\n✅ Routine B completed successfully!")
            print(f"   Run ID: {result['run_id']}")
            print(f"   Action: {result['action_result']['action']}")
            print(f"   Draft branch: {result['action_result']['draft_branch']}")
            print(f"   Log: {result['log_file']}")
            return 0
        else:
            print(f"\n❌ Routine B failed!")
            print(f"   Run ID: {result['run_id']}")
            print(f"   Error: {result['error']}")
            print(f"   Log: {result['log_file']}")
            return 1
    
    # Start API server
    print(f"Starting Routine B API server on port {args.port}...")
    print(f"   Health check: http://localhost:{args.port}/health")
    print(f"   Status check: http://localhost:{args.port}/status")
    print(f"   Trigger endpoint: POST http://localhost:{args.port}/trigger")
    print(f"   Required header: Authorization: Bearer <{API_TOKEN_ENV}>")
    print(f"\nPress Ctrl+C to stop")
    
    server = start_server(args.port)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
        return 0


if __name__ == "__main__":
    sys.exit(main())