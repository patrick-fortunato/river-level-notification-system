"""Main entry point for the River Level Notification System.

Starts the daily scheduler that runs the river level notification pipeline
at the configured time.
"""

import sys

from src.__version__ import __version__
from src.config import Config
from src.pipeline import Pipeline
from src.scheduler import start_scheduler


def main() -> None:
    """Initialize configuration and start the scheduler."""
    # Handle --version flag
    if "--version" in sys.argv:
        print(f"River Level Notification System v{__version__}")
        sys.exit(0)

    print(f"[INFO] River Level Notification System v{__version__} starting...")

    config = Config()

    # Handle --run-now flag: execute pipeline once immediately and exit
    if "--run-now" in sys.argv:
        pipeline = Pipeline(config)
        pipeline.run()
        sys.exit(0)

    start_scheduler(config)


if __name__ == "__main__":
    main()
