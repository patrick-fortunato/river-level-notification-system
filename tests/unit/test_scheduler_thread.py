"""Unit tests for the SchedulerThread class.

Tests start/stop lifecycle and concurrency guard without real scheduling.
"""

import time
import threading
from unittest.mock import patch, MagicMock

from src.config import Config


class TestSchedulerThreadLifecycle:
    """Tests for SchedulerThread start/stop behavior."""

    @patch("src.scheduler_thread.Scheduler")
    def test_start_sets_is_running_true(self, mock_scheduler_cls):
        """Verify start() sets is_running to True."""
        mock_scheduler_cls.return_value = MagicMock()

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        assert st.is_running() is False
        st.start()
        assert st.is_running() is True
        st.stop()  # cleanup

    @patch("src.scheduler_thread.Scheduler")
    def test_stop_sets_is_running_false(self, mock_scheduler_cls):
        """Verify stop() sets is_running to False."""
        mock_scheduler_cls.return_value = MagicMock()

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        st.start()
        assert st.is_running() is True
        st.stop()
        assert st.is_running() is False

    @patch("src.scheduler_thread.Scheduler")
    def test_start_when_already_running_is_noop(self, mock_scheduler_cls):
        """Verify calling start() when already running does nothing."""
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        st.start()
        st.start()  # should be a no-op

        # schedule_daily should only be called once
        assert mock_scheduler.schedule_daily.call_count == 1
        st.stop()

    @patch("src.scheduler_thread.Scheduler")
    def test_stop_when_not_running_is_noop(self, mock_scheduler_cls):
        """Verify calling stop() when not running does nothing."""
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        st.stop()  # should be a no-op
        assert mock_scheduler.clear.call_count == 0


class TestSchedulerThreadRunNow:
    """Tests for SchedulerThread.run_now() concurrency guard."""

    @patch("src.scheduler_thread.Scheduler")
    def test_run_now_calls_pipeline(self, mock_scheduler_cls):
        """Verify run_now() delegates to Scheduler.run_now()."""
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        st.run_now()
        # Give the daemon thread time to execute
        time.sleep(0.1)

        mock_scheduler.run_now.assert_called_once()

    @patch("src.scheduler_thread.Scheduler")
    def test_run_now_prevents_concurrent_runs(self, mock_scheduler_cls):
        """Verify run_now() prevents a second concurrent pipeline execution."""
        call_count = 0
        run_event = threading.Event()

        def slow_run():
            nonlocal call_count
            call_count += 1
            run_event.wait(timeout=2)

        mock_scheduler = MagicMock()
        mock_scheduler.run_now.side_effect = slow_run
        mock_scheduler_cls.return_value = mock_scheduler

        from src.scheduler_thread import SchedulerThread
        st = SchedulerThread(Config())

        st.run_now()
        time.sleep(0.05)  # let first run start
        st.run_now()  # should be rejected
        time.sleep(0.05)

        # Only one call should have happened
        assert call_count == 1

        # Clean up
        run_event.set()
        time.sleep(0.1)
