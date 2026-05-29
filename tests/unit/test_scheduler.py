"""Unit tests for the scheduler module.

Tests default and custom schedule times.

Requirements: 6.1, 6.2
"""

from src.config import Config


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
