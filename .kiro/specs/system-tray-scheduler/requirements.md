# Requirements: System Tray Scheduler

## Requirement 1: System Tray Presence

### User Story
As a user, I want the scheduler to run as a system tray icon so that it operates silently without a visible command prompt window.

### Acceptance Criteria

1. When the tray app is launched, an icon appears in the Windows notification area within 2 seconds.
2. No console window or command prompt is visible at any point during the app's lifecycle.
3. The entry point file uses `.pyw` extension to invoke `pythonw.exe` automatically.
4. The app runs without requiring administrator privileges.

---

## Requirement 2: Context Menu Controls

### User Story
As a user, I want to right-click the tray icon to access Start, Stop, Run Now, and Quit controls so that I can manage the scheduler without a command-line interface.

### Acceptance Criteria

1. Right-clicking the tray icon displays a context menu with these items in order: "Run Now", "Start Scheduler", "Stop Scheduler", a separator, "Quit".
2. "Start Scheduler" is disabled (grayed out) when the scheduler is already running.
3. "Stop Scheduler" is disabled (grayed out) when the scheduler is already stopped.
4. "Run Now" is disabled when a pipeline execution is already in progress.
5. Menu items respond within 1 second of being clicked.

---

## Requirement 3: Run Now Functionality

### User Story
As a user, I want to trigger an immediate pipeline run from the tray menu so that I can check river levels on demand without waiting for the scheduled time.

### Acceptance Criteria

1. Clicking "Run Now" executes the pipeline immediately, regardless of whether the scheduler is running or stopped.
2. The pipeline runs in a background thread so the tray UI remains responsive.
3. Concurrent pipeline runs are prevented — if a run is already in progress, "Run Now" does nothing (or is disabled).
4. After completion, the tray state reflects the updated last-run time.

---

## Requirement 4: Scheduler Start/Stop

### User Story
As a user, I want to start and stop the daily scheduler from the tray menu so that I can pause notifications without closing the app.

### Acceptance Criteria

1. Clicking "Stop Scheduler" halts the scheduling loop — no future scheduled runs occur until "Start" is invoked.
2. Clicking "Start Scheduler" resumes the scheduling loop with the correct next-run time based on the configured schedule.
3. Stopping the scheduler does not interrupt a currently running pipeline execution.
4. The scheduler starts automatically in the RUNNING state when the app launches.
5. Starting and stopping can be repeated any number of times without resource leaks or errors.

---

## Requirement 5: Visual Status Indicators

### User Story
As a user, I want the tray icon and tooltip to reflect the scheduler's current status so that I can tell at a glance whether it's running.

### Acceptance Criteria

1. When the scheduler is running, the tray icon displays a green circle.
2. When the scheduler is stopped, the tray icon displays a gray circle.
3. The tooltip shows "River Notify - Next run: {time}" when the scheduler is running.
4. The tooltip shows "River Notify - Stopped" when the scheduler is stopped.
5. Icon and tooltip update immediately when state changes (within 1 second).

---

## Requirement 6: Clean Application Shutdown

### User Story
As a user, I want the app to exit cleanly when I choose Quit so that no orphan processes or threads remain.

### Acceptance Criteria

1. Clicking "Quit" removes the icon from the system tray.
2. The scheduler thread stops gracefully (does not forcefully terminate mid-pipeline).
3. The process exits with code 0 after all cleanup is complete.
4. Daemon threads terminate automatically when the main thread exits.

---

## Requirement 7: Background Thread Architecture

### User Story
As a developer, I want the scheduler to run in a daemon thread so that the main thread is free for the pystray event loop and the app exits cleanly.

### Acceptance Criteria

1. The scheduler polling loop runs in a thread with `daemon=True`.
2. The pystray event loop runs on the main thread (required on Windows).
3. Pipeline executions triggered by "Run Now" run in separate daemon threads.
4. The scheduler thread uses `threading.Event.wait(timeout=30)` for responsive shutdown (not `time.sleep`).

---

## Requirement 8: Backward Compatibility

### User Story
As a user, I want the existing CLI (`river_notify.py`) to continue working unchanged so that I can still use `--run-now` and `--version` from the command line.

### Acceptance Criteria

1. `python river_notify.py --version` prints the version string and exits.
2. `python river_notify.py --run-now` executes the pipeline once and exits.
3. `python river_notify.py` (no flags) starts the legacy blocking scheduler as before.
4. The existing `start_scheduler()` function in `src/scheduler.py` remains available and functional.

---

## Requirement 9: Scheduler Class Refactoring

### User Story
As a developer, I want the scheduling logic encapsulated in a `Scheduler` class so that both the tray app and the CLI can reuse it.

### Acceptance Criteria

1. A `Scheduler` class exists in `src/scheduler.py` with methods: `schedule_daily()`, `run_pending()`, `clear()`, `run_now()`, `next_run_time()`.
2. The existing `start_scheduler()` function uses the new `Scheduler` class internally.
3. `Scheduler.run_now()` executes `Pipeline.run()` exactly once.
4. `Scheduler.next_run_time()` returns the next scheduled time as a human-readable string, or None if no jobs are scheduled.
5. `Scheduler.clear()` removes all scheduled jobs.

---

## Requirement 10: Dependencies and Installation

### User Story
As a user, I want the new dependencies clearly documented so that I can install them and run the tray app.

### Acceptance Criteria

1. `pystray` is added to `requirements.txt`.
2. `Pillow` is added to `requirements.txt`.
3. The tray app works with Python 3.10+ on Windows.
4. No compilation or build steps are required beyond `pip install -r requirements.txt`.
