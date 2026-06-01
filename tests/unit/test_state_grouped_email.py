"""Unit tests for state-grouped email feature.

Feature: state-grouped-email

Tests specific examples and edge cases for the state field across
ResolvedReach, ReachResolver, ReachCache, and ReportBuilder.
"""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config, STATE_NAMES
from src.models import ReachSubscriber, ResolvedReach
from src.reach_cache import ReachCache
from src.reach_resolver import ReachResolver
from src.report_builder import ReportBuilder


class TestResolvedReachStateDefault:
    """6.1: ResolvedReach defaults state to None when not provided."""

    def test_state_defaults_to_none(self):
        """ResolvedReach constructed without state kwarg defaults to None."""
        reach = ResolvedReach(reach_id=1234, reach_name="Test River", gauge_id="14209500")
        assert reach.state is None

    def test_state_can_be_set_explicitly(self):
        """ResolvedReach constructed with state kwarg stores the value."""
        reach = ResolvedReach(
            reach_id=1234, reach_name="Test River", gauge_id="14209500", state="OR"
        )
        assert reach.state == "OR"


class TestGraphQLQueryIncludesState:
    """6.2: GraphQL query string includes 'state' field."""

    def test_query_contains_state_field(self):
        """The GraphQL query in _query_reach includes 'state' in reach fields."""
        mock_config = MagicMock()
        mock_config.aw_graphql_url = "https://example.com/graphql"
        mock_config.aw_request_timeout = 30
        mock_http = MagicMock()
        mock_cache = MagicMock()

        resolver = ReachResolver(
            config=mock_config, http_client=mock_http, cache=mock_cache
        )

        # Mock a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "reach": {
                    "river": "Test River",
                    "section": "Upper",
                    "altname": None,
                    "states": [{"shortkey": "OR"}],
                },
                "getGaugeInformationForReachID": {"gauges": []},
            }
        }
        mock_http.post.return_value = mock_response

        resolver._query_reach(1234)

        # Verify the query sent to the API includes "states"
        call_args = mock_http.post.call_args
        query_payload = call_args[1]["json"]["query"] if "json" in call_args[1] else call_args[0][1]["query"]
        assert "states" in query_payload, (
            f"'states' not found in GraphQL query: {query_payload}"
        )


class TestLegacyCacheEntryWithoutState:
    """6.3: Legacy cache entry without state key loads with state=None."""

    def test_legacy_entry_loads_with_state_none(self):
        """A cache entry missing the 'state' key loads with state=None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = Path(tmp_dir) / "test_cache.json"

            # Write a legacy cache entry (no "state" key)
            legacy_data = {
                "reaches": {
                    "1234": {
                        "reach_name": "Clackamas River - Three Lynx",
                        "gauge_id": "14209500",
                        "cached_at": "2099-01-15T08:00:00+00:00",
                    }
                }
            }
            with open(cache_file, "w") as f:
                json.dump(legacy_data, f)

            config = Config(
                aw_reach_cache_file=str(cache_file),
                aw_cache_ttl_seconds=604800,
            )
            cache = ReachCache(config)

            result = cache.get_reach(1234)

            assert result is not None
            assert result.state is None
            assert result.reach_name == "Clackamas River - Three Lynx"
            assert result.gauge_id == "14209500"


class TestReportSingleStateOneHeading:
    """6.4: Report with single state produces one heading."""

    def test_single_state_one_heading(self):
        """A report where all reaches are in one state produces exactly one heading."""
        subscriber = ReachSubscriber(email="test@example.com", reach_ids=[1, 2, 3])
        resolved_reaches = {
            1: ResolvedReach(reach_id=1, reach_name="River A", gauge_id=None, state="OR"),
            2: ResolvedReach(reach_id=2, reach_name="River B", gauge_id=None, state="OR"),
            3: ResolvedReach(reach_id=3, reach_name="River C", gauge_id=None, state="OR"),
        }

        builder = ReportBuilder()
        html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

        assert html is not None

        heading_pattern = re.compile(r'<h2 class="state-heading">([^<]+)</h2>')
        headings = heading_pattern.findall(html)

        assert len(headings) == 1
        assert headings[0] == "Oregon"


class TestReportAllNoneStatesOnlyOther:
    """6.5: Report with all None states produces only 'Other' heading."""

    def test_all_none_states_only_other_heading(self):
        """When all reaches have state=None, the report has only an 'Other' heading."""
        subscriber = ReachSubscriber(email="test@example.com", reach_ids=[10, 20])
        resolved_reaches = {
            10: ResolvedReach(reach_id=10, reach_name="Unknown River", gauge_id=None, state=None),
            20: ResolvedReach(reach_id=20, reach_name="Mystery Creek", gauge_id=None, state=None),
        }

        builder = ReportBuilder()
        html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

        assert html is not None

        heading_pattern = re.compile(r'<h2 class="state-heading">([^<]+)</h2>')
        headings = heading_pattern.findall(html)

        assert len(headings) == 1
        assert headings[0] == "Other"
