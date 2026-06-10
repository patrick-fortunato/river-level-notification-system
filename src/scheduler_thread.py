"""Background scheduler thread for the River Level Notification System."""

import logging
import threading

from src.config import Config
from src.scheduler import Scheduler

logger = logging.getLogger(__name__)


class SchedulerThread:
    """Runs the scheduler polling loop in a background daemon thread."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._scheduler = Scheduler(config)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._pipeline_running = False
        self._pipeline_lock = threading.Lock()

    def start(self) -> None:
        """Start the scheduler polling loop in a daemon thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._scheduler.schedule_daily()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Stop the scheduler polling loop."""
        if not self._running:
            return
        self._stop_event.set()
        self._scheduler.clear()
        self._running = False

    def is_running(self) -> bool:
        """Return whether the scheduler is currently running."""
        return self._running

    def is_pipeline_running(self) -> bool:
        """Return whether a pipeline execution is in progress."""
        return self._pipeline_running

    def get_next_run_time(self) -> str | None:
        """Return the next scheduled run time as a formatted string."""
        return self._scheduler.next_run_time()

    def run_now(self) -> None:
        """Execute the pipeline immediately in a new daemon thread."""
        with self._pipeline_lock:
            if self._pipeline_running:
                return
            self._pipeline_running = True

        thread = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        thread.start()

    def _run_pipeline_thread(self) -> None:
        """Run the pipeline and reset the in-progress flag."""
        try:
            self._scheduler.run_now()
        except Exception as exc:
            logger.error("Pipeline execution failed: %s", exc)
        finally:
            self._pipeline_running = False

    def _loop(self) -> None:
        """Polling loop that runs in the daemon thread."""
        while not self._stop_event.is_set():
            self._scheduler.run_pending()
            self._stop_event.wait(timeout=30)
