"""Scheduler module for the River Level Notification System.

Runs the pipeline on a configurable daily schedule using the `schedule` library.
"""

import time

import schedule

from src.config import Config
from src.pipeline import Pipeline


def start_scheduler(config: Config) -> None:
    """Start the scheduling loop.

    Schedules the pipeline to run daily at the configured time and blocks
    indefinitely, checking for pending jobs every 30 seconds.

    Args:
        config: Application configuration containing schedule_time (HH:MM format).
    """
    pipeline = Pipeline(config)

    schedule.every().day.at(config.schedule_time).do(pipeline.run)

    print(
        f"[Scheduler] River Level Notification System started. "
        f"Pipeline scheduled daily at {config.schedule_time}."
    )

    while True:
        schedule.run_pending()
        time.sleep(30)
