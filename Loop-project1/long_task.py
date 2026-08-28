import sys
import time
from pathlib import Path

SLEEP_SECONDS = 180  # 3 minutes
FINISHED_FILE = Path(__file__).parent / "task-finished.txt"


def main():
    sleep_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else SLEEP_SECONDS
    print(f"Starting long task. Sleeping for {sleep_seconds} seconds...")
    time.sleep(sleep_seconds)
    FINISHED_FILE.write_text("done", encoding="utf-8")
    print("Long task complete. Created task-finished.txt")


if __name__ == "__main__":
    main()
