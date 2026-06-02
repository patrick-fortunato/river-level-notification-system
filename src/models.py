"""Data models for the River Level Notification System."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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
    rmin: float | None = None  # Minimum runnable flow
    rmax: float | None = None  # Maximum runnable flow

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


class RunnabilityStatus(str, Enum):
    """Runnability classification based on flow vs runnable range."""

    RUNNABLE = "Runnable"
    TOO_LOW = "Too Low"
    TOO_HIGH = "Too High"
    UNKNOWN = "Unknown"


def classify_runnability(
    flow: float | None,
    rmin: float | None,
    rmax: float | None,
) -> RunnabilityStatus:
    """Classify flow against runnable range.

    Returns UNKNOWN if any input is None.
    Returns RUNNABLE if rmin <= flow <= rmax.
    Returns TOO_LOW if flow < rmin.
    Returns TOO_HIGH if flow > rmax.
    """
    if flow is None or rmin is None or rmax is None:
        return RunnabilityStatus.UNKNOWN
    if flow < rmin:
        return RunnabilityStatus.TOO_LOW
    if flow > rmax:
        return RunnabilityStatus.TOO_HIGH
    return RunnabilityStatus.RUNNABLE
