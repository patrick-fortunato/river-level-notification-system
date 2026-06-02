"""Unit tests for AW flow fallback functionality.

Feature: aw-flow-fallback

Tests the resolver, cache, and report builder behavior for AW flow data
fallback when no USGS gauge is available for a reach.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config
from src.models import AWFlowData, GaugeEntry, ResolvedReach
from src.reach_cache import ReachCache
from src.reach_resolver import ReachResolver
from src.report_builder import ReportBuilder


def _make_resolver() -> ReachResolver:
    """Create a ReachResolver with mocked dependencies."""
    mock_config = MagicMock()
    mock_config.aw_graphql_url = "https://www.americanwhitewater.org/graphql"
    mock_config.aw_request_timeout = 30
    mock_http = MagicMock()
    mock_cache = MagicMock()
    return ReachResolver(config=mock_config, http_client=mock_http, cache=mock_cache)


# --- 6.1: _query_reach with virtual gauge only → aw_flow_data populated ---


def test_query_reach_virtual_gauge_populates_aw_flow_data():
    """Test _query_reach with mocked API response containing only virtual gauge
    with reading → aw_flow_data populated."""
    resolver = _make_resolver()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "reach": {
                "river": "South Fork Payette",
                "section": "Canyon Section",
                "altname": None,
                "states": [{"shortkey": "ID"}],
            },
            "getGaugeInformationForReachID": {
                "gauges": [
                    {
                        "gauge": {
                            "source": "virtual",
                            "source_id": "49596",
                            "name": "S. Fork Payette Virtual Gauge",
                        },
                        "gauge_reading": 2461.0,
                        "reading": 2461.0,
                        "updated": 30578618.0,
                        "metric": {"unit": "cfs"},
                    }
                ]
            },
        }
    }

    resolver._http_client.post.return_value = mock_response

    result = resolver._query_reach(4121)

    assert result.reach_id == 4121
    assert result.gauge_id is None
    assert result.aw_flow_data is not None
    assert result.aw_flow_data.reading == 2461.0
    assert result.aw_flow_data.unit == "cfs"
    assert result.aw_flow_data.gauge_name == "S. Fork Payette Virtual Gauge"
    assert result.aw_flow_data.updated == 30578618.0


# --- 6.2: _query_reach with USGS gauge → gauge_id set, aw_flow_data is None ---


def test_query_reach_usgs_gauge_sets_gauge_id_no_aw_flow_data():
    """Test _query_reach with mocked API response containing USGS gauge →
    gauge_id set, aw_flow_data is None."""
    resolver = _make_resolver()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "reach": {
                "river": "Clackamas River",
                "section": "Three Lynx to North Fork Reservoir",
                "altname": None,
                "states": [{"shortkey": "OR"}],
            },
            "getGaugeInformationForReachID": {
                "gauges": [
                    {
                        "gauge": {
                            "source": "usgs",
                            "source_id": "14209500",
                            "name": "CLACKAMAS RIVER AT THREE LYNX",
                        },
                        "gauge_reading": 1200.0,
                        "reading": 1200.0,
                        "updated": 12345.0,
                        "metric": {"unit": "cfs"},
                    }
                ]
            },
        }
    }

    resolver._http_client.post.return_value = mock_response

    result = resolver._query_reach(1493)

    assert result.reach_id == 1493
    assert result.gauge_id == "14209500"
    assert result.aw_flow_data is None


# --- 6.3: _query_reach with empty gauges list → gauge_id None, aw_flow_data None ---


def test_query_reach_empty_gauges_list():
    """Test _query_reach with empty gauges list → gauge_id None, aw_flow_data None."""
    resolver = _make_resolver()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "reach": {
                "river": "Unknown Creek",
                "section": "Upper",
                "altname": None,
                "states": [{"shortkey": "CA"}],
            },
            "getGaugeInformationForReachID": {
                "gauges": []
            },
        }
    }

    resolver._http_client.post.return_value = mock_response

    result = resolver._query_reach(9999)

    assert result.reach_id == 9999
    assert result.gauge_id is None
    assert result.aw_flow_data is None


# --- 6.4: ReachCache round-trip with aw_flow_data populated ---


def test_reach_cache_round_trip_with_aw_flow_data():
    """Test ReachCache round-trip: put/get reach with aw_flow_data populated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "test_cache.json"
        config = Config(
            aw_reach_cache_file=str(cache_file),
            aw_cache_ttl_seconds=604800,
        )
        cache = ReachCache(config)

        resolved = ResolvedReach(
            reach_id=4121,
            reach_name="South Fork Payette - Canyon Section",
            gauge_id=None,
            state="ID",
            aw_flow_data=AWFlowData(
                reading=2461.0,
                unit="cfs",
                gauge_name="S. Fork Payette Virtual Gauge",
                updated=30578618.0,
            ),
        )

        cache.put_reach(4121, resolved)
        result = cache.get_reach(4121)

        assert result is not None
        assert result.reach_id == 4121
        assert result.reach_name == "South Fork Payette - Canyon Section"
        assert result.gauge_id is None
        assert result.state == "ID"
        assert result.aw_flow_data is not None
        assert result.aw_flow_data.reading == 2461.0
        assert result.aw_flow_data.unit == "cfs"
        assert result.aw_flow_data.gauge_name == "S. Fork Payette Virtual Gauge"
        assert result.aw_flow_data.updated == 30578618.0


# --- 6.5: ReachCache backward compatibility: no aw_flow_data key ---


def test_reach_cache_backward_compatibility_no_aw_flow_data_key():
    """Test ReachCache backward compatibility: get reach from cache entry
    without aw_flow_data key."""
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "test_cache.json"

        # Manually write a cache entry without the aw_flow_data key
        # (simulating an old cache format) — use current time so TTL is valid
        now_iso = datetime.now(timezone.utc).isoformat()
        cache_data = {
            "reaches": {
                "1493": {
                    "reach_name": "Clackamas River - Three Lynx to North Fork Reservoir",
                    "gauge_id": "14209500",
                    "state": "OR",
                    "cached_at": now_iso,
                }
            }
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        config = Config(
            aw_reach_cache_file=str(cache_file),
            aw_cache_ttl_seconds=604800,
        )
        cache = ReachCache(config)

        result = cache.get_reach(1493)

        assert result is not None
        assert result.reach_id == 1493
        assert result.reach_name == "Clackamas River - Three Lynx to North Fork Reservoir"
        assert result.gauge_id == "14209500"
        assert result.state == "OR"
        assert result.aw_flow_data is None


# --- 6.6: _render_reach_entry with aw_flow_data present, gauge_entry None ---


def test_render_reach_entry_with_aw_flow_data():
    """Test _render_reach_entry with aw_flow_data present, gauge_entry None →
    renders flow with AW attribution."""
    resolved = ResolvedReach(
        reach_id=4121,
        reach_name="South Fork Payette - Canyon Section",
        gauge_id=None,
        aw_flow_data=AWFlowData(
            reading=2461.0,
            unit="cfs",
            gauge_name="S. Fork Payette Virtual Gauge",
            updated=30578618.0,
        ),
    )

    builder = ReportBuilder()
    html = builder._render_reach_entry(resolved, gauge_entry=None)

    # Should contain the reading value
    assert "2461.0" in html

    # Should contain the unit
    assert "cfs" in html

    # Should contain the gauge name (AW attribution)
    assert "S. Fork Payette Virtual Gauge" in html

    # Should indicate AW source
    assert "(via AW)" in html

    # Should NOT contain "No gauge data available"
    assert "No gauge data available" not in html

    # Should contain reach name linked to AW
    assert "South Fork Payette - Canyon Section" in html
    assert "river-detail/4121/main" in html


# --- 6.7: _render_reach_entry with both None → shows "No gauge data available" ---


def test_render_reach_entry_both_none_shows_no_gauge_data():
    """Test _render_reach_entry with both gauge_entry and aw_flow_data None →
    shows 'No gauge data available'."""
    resolved = ResolvedReach(
        reach_id=9999,
        reach_name="Unknown Creek - Upper",
        gauge_id=None,
        aw_flow_data=None,
    )

    builder = ReportBuilder()
    html = builder._render_reach_entry(resolved, gauge_entry=None)

    # Should contain "No gauge data available"
    assert "No gauge data available" in html

    # Should contain reach name linked to AW
    assert "Unknown Creek - Upper" in html
    assert "river-detail/9999/main" in html

    # Should NOT contain flow data or AW attribution
    assert "(via AW)" not in html
