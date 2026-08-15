# Loop Practice Project 1: In-Session Loop Monitor

A learning exercise for **Concept 4: in-session loop**. A monitor loop watches for a long-running task to finish and reports exactly when it does.

## Files

- `long_task.py` — simulates a long task. Defaults to sleeping 3 minutes, then creates `task-finished.txt`.
- `monitor.py` — in-session loop that checks for `task-finished.txt` every 1 minute and prints `Task finished!` once when it appears, then stops.

## How to run (full 3-minute demo)

Terminal 1 — start the task:

```
python long_task.py
```

Terminal 2 — start the monitor:

```
python monitor.py
```

After 3 minutes `long_task.py` writes `task-finished.txt`. Within the next 1-minute check, the monitor prints `Task finished!` and exits cleanly. You do not need to watch the terminal; the monitor stops by itself.

## How to test quickly

Both scripts accept an optional number of seconds to shorten the wait.

Terminal 1 — start a short task:

```
python long_task.py 5
```

Terminal 2 — check every 1 second:

```
python monitor.py 1
```

The task finishes after 5 seconds and the monitor prints `Task finished!` and stops.

## Notes

- No third-party dependencies; only the Python standard library.
- Delete `task-finished.txt` before re-running so the monitor waits for a fresh run.
