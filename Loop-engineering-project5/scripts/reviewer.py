import sys
import os
import subprocess

def review_issue(issue_name, worktree_path):
    project_subdir = "Loop-engineering-project5"
    test_file = os.path.join(worktree_path, project_subdir, "tests", f"test_{issue_name}.py")
    
    # 1. Inspect diff
    diff_proc = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=worktree_path, capture_output=True, text=True)
    changed_files = diff_proc.stdout.splitlines()
    
    # Check if tests were modified
    if any("tests/" in f for f in changed_files):
        print("FAIL: Tests were modified")
        sys.exit(1)
        
    # 2. Run tests (change cwd so import resolves worktree src)
    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", test_file],
        cwd=os.path.join(worktree_path, project_subdir),
        capture_output=True
    )
    
    if test_result.returncode == 0:
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL: Tests failed")
        sys.exit(1)

if __name__ == "__main__":
    review_issue(sys.argv[1], sys.argv[2])
