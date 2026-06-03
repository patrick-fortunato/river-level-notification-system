"""Unit tests for the scheduler module.

Tests the Scheduler class and configuration defaults.

Requirements: 6.1, 6.2
"""

from unittest.mock import patch, MagicMock

import schedule

from src.config import Config
from src.scheduler import Scheduler


class TestSchedulerConfig:
    """Tests for scheduler configuration defaults."""

    def test_default_schedule_time_is_0600(self):
        """Verify the default schedule time is 06:00."""
        config = Config()
        assert config.schedule_time == "06:00"

    def test_custom_schedule_time_is_respected(self):
        """Verify a custom schedule time is stored correctly."""
        config = Config(schedule_time="08:30")
        assert config.schedule_time == "08:30"

    def test_schedule_time_accepts_various_formats(self):
        """Verify schedule time accepts valid HH:MM formats."""
        for time_str in ["00:00", "12:00", "23:59", "06:00", "18:45"]:
            config = Config(schedule_time=time_str)
            assert config.schedule_time == time_str


class TestSchedulerClass:
    """Tests for the Scheduler class methods."""

    def setup_method(self):
        """Clear all scheduled jobs before each test."""
        schedule.clear()

    def teardown_method(self):
        """Clear all scheduled jobs after each test."""
        schedule.clear()

    def test_schedule_daily_registers_a_job(self):
        """Verify schedule_daily() registers exactly one job."""
        config = Config(schedule_time="06:00")
        scheduler = Scheduler(config)
        scheduler.schedule_daily()

        jobs = schedule.get_jobs()
        assert len(jobs) == 1

    def test_clear_removes_all_jobs(self):
        """Verify clear() removes all scheduled jobs."""
        config = Config(schedule_time="06:00")
        scheduler = Scheduler(config)
        scheduler.schedule_daily()
        assert len(schedule.get_jobs()) == 1

        scheduler.clear()
        assert len(schedule.get_jobs()) == 0

    @patch("src.scheduler.Pipeline")
    def test_run_now_calls_pipeline_run(self, mock_pipeline_cls):
        """Verify run_now() creates a Pipeline and calls run()."""
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        config = Config()
        scheduler = Scheduler(config)
        scheduler.run_now()

        mock_pipeline_cls.assert_called_once_with(config)
        mock_pipeline.run.assert_called_once()

    def test_next_run_time_returns_formatted_time_when_job_exists(self):
        """Verify next_run_time() returns a formatted string when a job is scheduled."""
        config = Config(schedule_time="06:00")
        scheduler = Scheduler(config)
        scheduler.schedule_daily()

        result = scheduler.next_run_time()
        assert result is not None
        # Should be a time like "6:00 AM"
        assert "AM" in result or "PM" in result

    def test_next_run_time_returns_none_when_no_jobs(self):
        """Verify next_run_time() returns None when no jobs are scheduled."""
        config = Config()
        scheduler = Scheduler(config)

        result = scheduler.next_run_time()
        assert result is None
