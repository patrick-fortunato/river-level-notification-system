"""Integration tests for the reach-first pipeline.

Tests the reach cache write/read cycle with real filesystem operations and
the full pipeline run with mocked AW API returning reach data.

Requirements: 2.1, 6.1
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.models import GaugeEntry, ReachSubscriber, ResolvedReach
from src.reach_cache import ReachCache


class TestReachCacheWriteAndReadCycle:
    """Integration test using real filesystem for per-reach cache persistence.

    Validates: Requirements 6.1
    """

    def test_cache_put_and_get_cycle(self):
        """Cache put_reach and get_reach cycle produces identical data via real filesystem.

        1. Create a ReachCache with a temp directory cache file
        2. Put a ResolvedReach into the cache
        3. Create a new ReachCache instance pointing to the same file
        4. Get the reach back (should read from cache)
        5. Verify both are equivalent
        6. Verify the cache file exists on disk
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = str(Path(tmp_dir) / "aw_reach_cache.json")

            config = Config(
                aw_reach_cache_file=cache_file,
                aw_cache_ttl_seconds=604800,
            )

            # First instance: write to cache
            cache1 = ReachCache(config)
            reach1 = ResolvedReach(
                reach_id=1234,
                reach_name="North Santiam - Upper",
                gauge_id="14181500",
            )
            reach2 = ResolvedReach(
                reach_id=5678,
                reach_name="Rogue River",
                gauge_id=None,
            )

            cache1.put_reach(1234, reach1)
            cache1.put_reach(5678, reach2)

            # Verify the cache file exists on disk
            assert Path(cache_file).exists()

            # Verify the cache file contains valid JSON with expected structure
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            assert "reaches" in cache_data
            assert "1234" in cache_data["reaches"]
            assert "5678" in cache_data["reaches"]

            # Second instance: read from cache
            cache2 = ReachCache(config)

            result1 = cache2.get_reach(1234)
            result2 = cache2.get_reach(5678)

            # Both results should be equivalent
            assert result1 is not None
            assert result1.reach_id == 1234
            assert result1.reach_name == "North Santiam - Upper"
            assert result1.gauge_id == "14181500"

            assert result2 is not None
            assert result2.reach_id == 5678
            assert result2.reach_name == "Rogue River"
            assert result2.gauge_id is None

    def test_cache_stale_fallback(self):
        """Stale cache entries are returned by get_stale_reach even when expired."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = str(Path(tmp_dir) / "aw_reach_cache.json")

            # Write a cache file with an old timestamp (expired)
            cache_data = {
                "reaches": {
                    "1234": {
                        "reach_name": "Old Cached Reach",
                        "gauge_id": "14321000",
                        "cached_at": "2020-01-01T00:00:00+00:00",
                    }
                }
            }
            Path(cache_file).write_text(json.dumps(cache_data), encoding="utf-8")

            config = Config(
                aw_reach_cache_file=cache_file,
                aw_cache_ttl_seconds=604800,  # 7 days
            )
            cache = ReachCache(config)

            # get_reach should return None (expired)
            result = cache.get_reach(1234)
            assert result is None

            # get_stale_reach should return the entry regardless of TTL
            stale = cache.get_stale_reach(1234)
            assert stale is not None
            assert stale.reach_id == 1234
            assert stale.reach_name == "Old Cached Reach"
            assert stale.gauge_id == "14321000"

    def test_cache_handles_corrupt_file(self):
        """Cache returns None when file is corrupt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = str(Path(tmp_dir) / "aw_reach_cache.json")
            Path(cache_file).write_text("NOT VALID JSON {{{{", encoding="utf-8")

            config = Config(aw_reach_cache_file=cache_file)
            cache = ReachCache(config)

            result = cache.get_reach(1234)
            assert result is None
