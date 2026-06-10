"""Scheduler module for the River Level Notification System.

Runs the pipeline on a configurable daily schedule using the `schedule` library.
"""

import time

import schedule

from src.config import Config
from src.pipeline import Pipeline


class Scheduler:
    """Controllable scheduler that wraps the schedule library."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def schedule_daily(self) -> None:
        """Register the daily job using the schedule library."""
        schedule.every().day.at(self._config.schedule_time).do(self._run_pipeline)

    def run_pending(self) -> None:
        """Check and run any pending scheduled jobs."""
        schedule.run_pending()

    def clear(self) -> None:
        """Clear all scheduled jobs."""
        schedule.clear()

    def run_now(self) -> None:
        """Execute the pipeline immediately."""
        Pipeline(self._config).run()

    def next_run_time(self) -> str | None:
        """Return the next scheduled run time as a formatted string, or None if no jobs."""
        jobs = schedule.get_jobs()
        if not jobs:
            return None
        next_run = jobs[0].next_run
        if next_run is None:
            return None
        return next_run.strftime("%I:%M %p").lstrip("0")

    def _run_pipeline(self) -> None:
        """Internal method that creates and runs the Pipeline."""
        Pipeline(self._config).run()


def start_scheduler(config: Config) -> None:
    """Start the scheduling loop.

    Schedules the pipeline to run daily at the configured time and blocks
    indefinitely, checking for pending jobs every 30 seconds.

    Args:
        config: Application configuration containing schedule_time (HH:MM format).
    """
    scheduler = Scheduler(config)
    scheduler.schedule_daily()

    print(
        f"[Scheduler] River Level Notification System started. "
        f"Pipeline scheduled daily at {config.schedule_time}."
    )

    while True:
        scheduler.run_pending()
        time.sleep(30)
