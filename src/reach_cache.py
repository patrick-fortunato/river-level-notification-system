"""Per-reach cache for the River Level Notification System.

Manages local JSON caching of resolved reach data (reach name + gauge ID)
with TTL-based expiration to avoid redundant AW API calls on every pipeline run.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import Config
from src.models import ResolvedReach

logger = logging.getLogger(__name__)


class ReachCache:
    """Manages local JSON caching of resolved reach data with TTL expiration.

    Cache file format:
    {
        "reaches": {
            "1493": {
                "reach_name": "Clackamas River - Three Lynx to North Fork Reservoir",
                "gauge_id": "14209500",
                "cached_at": "2025-01-15T08:00:00+00:00"
            }
        }
    }
    """

    def __init__(self, config: Config) -> None:
        """Initialize the cache with application configuration.

        Args:
            config: Application configuration containing cache file path and TTL.
        """
        self._config = config
        self._cache_path = Path(config.aw_reach_cache_file)
        self._data: dict[str, dict] | None = None  # Lazy-loaded reaches dict

    def get_reach(self, reach_id: int) -> ResolvedReach | None:
        """Get cached reach data if within TTL.

        Args:
            reach_id: The AW reach ID to look up.

        Returns:
            ResolvedReach if cached and within TTL, None on miss or expiry.
        """
        reaches = self._load_cache()
        entry = reaches.get(str(reach_id))
        if entry is None:
            return None

        if not self._is_entry_valid(entry):
            return None

        return self._entry_to_resolved_reach(reach_id, entry)

    def put_reach(self, reach_id: int, resolved: ResolvedReach) -> None:
        """Store a resolved reach entry with current timestamp.

        Updates the in-memory cache and writes to disk.

        Args:
            reach_id: The AW reach ID.
            resolved: The resolved reach data to cache.
        """
        reaches = self._load_cache()
        reaches[str(reach_id)] = {
            "reach_name": resolved.reach_name,
            "gauge_id": resolved.gauge_id,
            "state": resolved.state,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        self._data = reaches
        self._write_cache(reaches)

    def get_stale_reach(self, reach_id: int) -> ResolvedReach | None:
        """Get cached reach data regardless of TTL (for fallback).

        Args:
            reach_id: The AW reach ID to look up.

        Returns:
            ResolvedReach if present in cache (even if expired), None if not found.
        """
        reaches = self._load_cache()
        entry = reaches.get(str(reach_id))
        if entry is None:
            return None

        return self._entry_to_resolved_reach(reach_id, entry)

    def _load_cache(self) -> dict[str, dict]:
        """Load cache data from disk on first access (lazy loading).

        Returns:
            The reaches dict from the cache file, or empty dict on failure.
        """
        if self._data is not None:
            return self._data

        if not self._cache_path.exists():
            self._data = {}
            return self._data

        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Cache file %s is corrupt or unreadable, treating as empty: %s",
                self._cache_path,
                exc,
            )
            self._data = {}
            return self._data

        if not isinstance(data, dict):
            logger.warning(
                "Cache file %s has invalid format, treating as empty",
                self._cache_path,
            )
            self._data = {}
            return self._data

        reaches = data.get("reaches")
        if not isinstance(reaches, dict):
            logger.warning(
                "Cache file %s missing 'reaches' key or invalid type, treating as empty",
                self._cache_path,
            )
            self._data = {}
            return self._data

        self._data = reaches
        return self._data

    def _write_cache(self, reaches: dict[str, dict]) -> None:
        """Write the reaches dict to the cache file.

        Args:
            reaches: The reaches dictionary to persist.
        """
        data = {"reaches": reaches}
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning(
                "Failed to write reach cache to %s: %s", self._cache_path, exc
            )

    def _is_entry_valid(self, entry: dict) -> bool:
        """Check if a cache entry is within TTL.

        Args:
            entry: A single reach cache entry dict.

        Returns:
            True if the entry's cached_at timestamp plus TTL is in the future.
        """
        cached_at_str = entry.get("cached_at")
        if not cached_at_str:
            return False

        try:
            cached_at = datetime.fromisoformat(cached_at_str)
        except (ValueError, TypeError):
            return False

        now = datetime.now(timezone.utc)
        elapsed = (now - cached_at).total_seconds()
        return elapsed < self._config.aw_cache_ttl_seconds

    def _entry_to_resolved_reach(
        self, reach_id: int, entry: dict
    ) -> ResolvedReach | None:
        """Convert a cache entry dict to a ResolvedReach object.

        Args:
            reach_id: The reach ID for this entry.
            entry: The cache entry dict.

        Returns:
            ResolvedReach if the entry has valid data, None otherwise.
        """
        reach_name = entry.get("reach_name")
        if not isinstance(reach_name, str):
            return None

        gauge_id = entry.get("gauge_id")
        # gauge_id can be None or a string
        if gauge_id is not None and not isinstance(gauge_id, str):
            return None

        state = entry.get("state")

        return ResolvedReach(
            reach_id=reach_id,
            reach_name=reach_name,
            gauge_id=gauge_id,
            state=state,
        )
