"""Data models for the River Level Notification System."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AWFlowData:
    """Flow data sourced from AW's gauge response (non-USGS fallback)."""

    reading: float
    unit: str
    gauge_name: str
    updated: float | None = None


@dataclass
class GaugeEntry:
    """A single river gauge reading from USGS."""

    gauge_number: str
    gauge_name: str
    usgs_page_url: str
    reading_datetime: str
    flow_level: str


@dataclass
class ReachSubscriber:
    """A subscriber with their ordered list of reach IDs."""

    email: str
    reach_ids: list[int]  # Ordered, deduplicated


@dataclass
class ResolvedReach:
    """A reach resolved from the AW API."""

    reach_id: int
    reach_name: str
    gauge_id: str | None  # USGS gauge number, or None if no USGS gauge
    state: str | None = None  # US state abbreviation (e.g., "OR", "WA")
    aw_flow_data: AWFlowData | None = None  # AW flow data fallback when no USGS gauge

    @property
    def aw_url(self) -> str:
        return (
            f"https://www.americanwhitewater.org/content/River/view/"
            f"river-detail/{self.reach_id}/main"
        )


@dataclass
class Reach:
    """A reach from the AW API (used by AWClient inverted mapping)."""

    reach_id: int
    reach_name: str


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
