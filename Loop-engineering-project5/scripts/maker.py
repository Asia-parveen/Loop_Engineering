import sys
import os
import subprocess

def fix_issue(issue_name, worktree_path):
    # Adjust for the fact that the repo root is one level up
    project_subdir = "Loop-engineering-project5"
    src_file = os.path.join(worktree_path, project_subdir, "src", f"{issue_name}.py")
    test_file = os.path.join(worktree_path, project_subdir, "tests", f"test_{issue_name}.py")
    
    with open(src_file, "r") as f:
        content = f.read()

    print(f"Maker: Read content of {src_file}: {repr(content)}")

    # Maker logic for specific bugs
    if issue_name == "issue1":
        # Fix price - percent -> price - (price * percent / 100)
        new_content = content.replace("price - percent", "price - (price * percent / 100.0)")
    elif issue_name == "issue2":
        # Fix data[:n-1] -> data[:n]
        new_content = content.replace("data[:n-1]", "data[:n]")
    elif issue_name == "issue3":
        # Fix text.capitalize() -> text.title()
        new_content = content.replace("text.capitalize()", "' '.join(word.capitalize() for word in text.split())")
    else:
        print(f"Unknown issue: {issue_name}")
        sys.exit(1)

    if new_content == content:
        print(f"Maker: WARNING - No replacement made for {issue_name}")
    else:
        print(f"Maker: Applied fix for {issue_name}")

    with open(src_file, "w") as f:
        f.write(new_content)

    # Run test to verify fix (change cwd so import resolves worktree src)
    result = subprocess.run(
        [sys.executable, "-m", "unittest", test_file],
        cwd=os.path.join(worktree_path, project_subdir),
        capture_output=True
    )

    if result.returncode == 0:
        # Commit fix
        subprocess.run(["git", "add", src_file], cwd=worktree_path)
        subprocess.run(["git", "commit", "-m", f"Fix {issue_name}"], cwd=worktree_path)
        print(f"Maker: Fixed and committed {issue_name}")
    else:
        print(f"Maker: Fix failed for {issue_name}")
        print("STDOUT:", result.stdout.decode())
        print("STDERR:", result.stderr.decode())
        sys.exit(1)

if __name__ == "__main__":
    fix_issue(sys.argv[1], sys.argv[2])
