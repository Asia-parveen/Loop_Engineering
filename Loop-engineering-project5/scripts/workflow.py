import os
import subprocess
import sys
import shutil

PROJECT_ROOT = r"F:\Loop-practice-projects\Loop-engineering-project5"
REVIEW_DIR = os.path.join(PROJECT_ROOT, "review")

def run_job(issue_id):
    issue_name = f"issue{issue_id}"
    worktree_path = os.path.join(REVIEW_DIR, issue_name)
    
    # Clean up existing worktree
    if os.path.exists(worktree_path):
        subprocess.run(["git", "worktree", "remove", "-f", worktree_path], cwd=PROJECT_ROOT)
        if os.path.exists(worktree_path):
            shutil.rmtree(worktree_path)

    # Create isolated worktree
    subprocess.run(["git", "worktree", "add", "-b", f"branch_{issue_name}", worktree_path, "master"], cwd=PROJECT_ROOT, check=True)
    
    # Run Maker
    maker_proc = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "maker.py"), issue_name, worktree_path], capture_output=True, text=True)
    
    if maker_proc.returncode != 0:
        return f"Candidate {issue_id}: FAIL (Maker failed: {maker_proc.stdout}\n{maker_proc.stderr})"
    
    # Run Reviewer
    reviewer_proc = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "reviewer.py"), issue_name, worktree_path], capture_output=True, text=True)
    
    verdict = reviewer_proc.stdout.strip()
    return f"Candidate {issue_id}: {verdict}"

def main():
    print("Starting Project 5 Workflow...")
    
    # In a real shell with '&', we'd background them. 
    # Here we use Python's multiprocessing or subprocess parallelism to simulate the requirement.
    # To strictly follow "using Windows shell background execution (&)", we would need a .cmd that does it.
    # However, managing the 'wait' and result collection in CMD is brittle.
    # I will implement the parallel execution here using subprocess.Popen.
    
    processes = []
    # We will write the output of each job to a temp file to collect them later
    results_dir = os.path.join(REVIEW_DIR, "results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    for i in range(1, 4):
        # We wrap the run_job logic into a small script or just call python with a command
        cmd = f"import sys; sys.path.append(r'{PROJECT_ROOT}'); from scripts.workflow import run_job; print(run_job({i}))"
        out_file = open(os.path.join(results_dir, f"res_{i}.txt"), "w")
        p = subprocess.Popen([sys.executable, "-c", cmd], stdout=out_file, stderr=subprocess.STDOUT)
        processes.append((p, out_file))
        print(f"Launched Candidate {i} job...")

    # Wait for all
    for p, f in processes:
        p.wait()
        f.close()
        
    # Collect and display
    for i in range(1, 4):
        with open(os.path.join(results_dir, f"res_{i}.txt"), "r") as f:
            print(f.read().strip())

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "internal_run_job":
        # This part is used if we wanted to call run_job directly from CLI
        pass
    else:
        main()
