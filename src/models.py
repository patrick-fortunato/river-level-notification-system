"""Data models for the River Level Notification System."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GaugeEntry:
    """A single river gauge reading from USGS."""

    gauge_number: str
    gauge_name: str
    usgs_page_url: str
    reading_datetime: str
    flow_level: str


@dataclass
class Subscriber:
    """A subscriber with their gauge inclusion preferences."""

    email: str
    included_gauges: list[str] = field(default_factory=list)
    state_code: str = ""  # Empty = use global default from config


@dataclass
class StatePreference:
    """Gauge preferences for a single state within a grouped subscriber."""

    state_code: str
    included_gauges: list[str] = field(default_factory=list)  # Empty = all gauges


@dataclass
class GroupedSubscriber:
    """A subscriber with consolidated preferences from all their sheet rows."""

    email: str
    state_preferences: list[StatePreference] = field(default_factory=list)


@dataclass
class RunSummary:
    """Summary of a pipeline execution run."""

    total_subscribers: int
    emails_sent: int
    emails_failed: int
    subscribers_skipped: int
    skip_reasons: list[str]
    start_time: datetime
    end_time: datetime
