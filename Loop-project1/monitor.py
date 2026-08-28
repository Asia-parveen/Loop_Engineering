import sys
import time
from pathlib import Path

FINISHED_FILE = Path(__file__).parent / "task-finished.txt"
CHECK_INTERVAL_SECONDS = 60  # 1 minute


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else CHECK_INTERVAL_SECONDS
    print(f"Monitoring for {FINISHED_FILE}... checking every {interval} seconds.")
    while not FINISHED_FILE.exists():
        time.sleep(interval)
    print("Task finished!")


if __name__ == "__main__":
    main()
