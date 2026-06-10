# Tasks: System Tray Scheduler

## Task 1: Refactor src/scheduler.py to expose a Scheduler class

- [x] 1.1 Create a `Scheduler` class with `__init__(self, config: Config)` that stores config and creates a `Pipeline` instance
- [x] 1.2 Implement `schedule_daily()` method that registers the daily job using the `schedule` library
- [x] 1.3 Implement `run_pending()` method that calls `schedule.run_pending()`
- [x] 1.4 Implement `clear()` method that calls `schedule.clear()`
- [x] 1.5 Implement `run_now()` method that calls `Pipeline(config).run()` directly
- [x] 1.6 Implement `next_run_time()` that returns the next scheduled run as a formatted string or None
- [x] 1.7 Refactor existing `start_scheduler()` function to use the new `Scheduler` class internally
- [x] 1.8 Write unit tests for the `Scheduler` class methods

## Task 2: Create the TrayApp class in src/tray_app.py

- [x] 2.1 Create `src/tray_app.py` with `TrayApp` class and `__init__(self, config: Config)` constructor
- [x] 2.2 Implement `_create_icon_image(self, running: bool) -> Image.Image` using Pillow (green/gray circle, 64x64)
- [x] 2.3 Implement `_build_menu()` returning a pystray.Menu with Run Now, Start Scheduler, Stop Scheduler, separator, Quit
- [x] 2.4 Implement `_get_tooltip_text()` returning status-aware tooltip string
- [x] 2.5 Implement `run()` method that creates the pystray.Icon and starts the event loop
- [x] 2.6 Write unit tests for `_create_icon_image` (verify image dimensions and pixel colors)
- [x] 2.7 Write unit tests for `_get_tooltip_text` (verify text for RUNNING and STOPPED states)

## Task 3: Implement SchedulerThread in src/scheduler_thread.py

- [x] 3.1 Create `src/scheduler_thread.py` with `SchedulerThread` class
- [x] 3.2 Implement `__init__` with a `threading.Event` for stop signaling and `daemon=True` thread
- [x] 3.3 Implement `start()` method that begins the polling loop in the daemon thread
- [x] 3.4 Implement `stop()` method that sets the stop event to halt the loop
- [x] 3.5 Implement `is_running()` method returning current state
- [x] 3.6 Implement `get_next_run_time()` delegating to `Scheduler.next_run_time()`
- [x] 3.7 Implement `run_now()` that executes the pipeline in a new daemon thread with concurrency guard
- [x] 3.8 Write unit tests for SchedulerThread start/stop lifecycle (mocking schedule and pipeline)

## Task 4: Implement TrayApp menu action handlers

- [x] 4.1 Implement `on_run_now()` — delegates to SchedulerThread.run_now(), disables if in progress
- [x] 4.2 Implement `on_stop()` — stops SchedulerThread, updates icon to gray, updates tooltip
- [x] 4.3 Implement `on_start()` — starts SchedulerThread, updates icon to green, updates tooltip
- [x] 4.4 Implement `on_quit()` — stops SchedulerThread, calls icon.stop()
- [x] 4.5 Implement menu item enabled/disabled logic (Start disabled when running, Stop disabled when stopped, Run Now disabled when pipeline in progress)
- [x] 4.6 Write unit tests for action handlers (mock pystray, verify state transitions)

## Task 5: Create the tray entry point file

- [x] 5.1 Create `river_notify_tray.pyw` that imports Config and TrayApp, then calls `TrayApp(Config()).run()`
- [x] 5.2 Verify the file has no `print()` statements or console I/O
- [x] 5.3 Add a brief module docstring explaining this is the windowless tray entry point

## Task 6: Update dependencies

- [x] 6.1 Add `pystray` to `requirements.txt`
- [x] 6.2 Add `Pillow` to `requirements.txt`

## Task 7: Verify backward compatibility

- [x] 7.1 Verify `river_notify.py --version` still prints version and exits
- [x] 7.2 Verify `river_notify.py --run-now` still runs the pipeline once and exits
- [x] 7.3 Verify `river_notify.py` (no flags) still starts the blocking scheduler loop
- [x] 7.4 Verify `start_scheduler()` function still exists and works as before
