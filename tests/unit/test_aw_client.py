"""Unit tests for the AWClient.

Tests core functionality: mapping inversion, USGS filtering, and error handling.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.aw_client import AWClient, AWClientError
from src.config import Config
from src.models import Reach


class TestBuildInvertedMapping:
    """Tests for _build_inverted_mapping."""

    def test_empty_pairs_returns_empty_mapping(self):
        config = Config()
        client = AWClient(config, requests.Session())
        result = client._build_inverted_mapping([])
        assert result == {}

    def test_single_usgs_pair(self):
        config = Config()
        client = AWClient(config, requests.Session())
        pairs = [(1234, "North Santiam", "usgs", "14181500")]
        result = client._build_inverted_mapping(pairs)
        assert "14181500" in result
        assert len(result["14181500"]) == 1
        assert result["14181500"][0].reach_id == 1234
        assert result["14181500"][0].reach_name == "North Santiam"

    def test_filters_non_usgs_sources(self):
        config = Config()
        client = AWClient(config, requests.Session())
        pairs = [
            (1234, "North Santiam", "usgs", "14181500"),
            (2345, "Some River", "canada", "08NM116"),
            (3456, "Virtual River", "virtual", "V001"),
        ]
        result = client._build_inverted_mapping(pairs)
        assert "14181500" in result
        assert "08NM116" not in result
        assert "V001" not in result

    def test_multiple_reaches_for_same_gauge(self):
        config = Config()
        client = AWClient(config, requests.Session())
        pairs = [
            (1234, "North Santiam - Upper", "usgs", "14181500"),
            (1235, "North Santiam - Lower", "usgs", "14181500"),
        ]
        result = client._build_inverted_mapping(pairs)
        assert len(result["14181500"]) == 2

    def test_no_duplicate_reaches(self):
        config = Config()
        client = AWClient(config, requests.Session())
        pairs = [
            (1234, "North Santiam", "usgs", "14181500"),
            (1234, "North Santiam", "usgs", "14181500"),
        ]
        result = client._build_inverted_mapping(pairs)
        assert len(result["14181500"]) == 1

    def test_case_insensitive_usgs_filter(self):
        config = Config()
        client = AWClient(config, requests.Session())
        pairs = [
            (1234, "River A", "USGS", "14181500"),
            (2345, "River B", "Usgs", "14211720"),
        ]
        result = client._build_inverted_mapping(pairs)
        assert "14181500" in result
        assert "14211720" in result


class TestFetchGaugesForReach:
    """Tests for _fetch_gauges_for_reach error handling."""

    def test_raises_on_connection_error(self):
        config = Config()
        session = MagicMock()
        session.post.side_effect = requests.exceptions.ConnectionError("fail")
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Network error"):
            client._fetch_gauges_for_reach(1234)

    def test_raises_on_timeout(self):
        config = Config()
        session = MagicMock()
        session.post.side_effect = requests.exceptions.Timeout("timeout")
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Network error"):
            client._fetch_gauges_for_reach(1234)

    def test_raises_on_http_error(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        session.post.return_value = response
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="HTTP 500"):
            client._fetch_gauges_for_reach(1234)

    def test_raises_on_malformed_json(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("bad json")
        session.post.return_value = response
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Malformed JSON"):
            client._fetch_gauges_for_reach(1234)

    def test_raises_on_graphql_errors(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "errors": [{"message": "Reach not found"}]
        }
        session.post.return_value = response
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="GraphQL error"):
            client._fetch_gauges_for_reach(1234)

    def test_returns_gauges_on_success(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {
                "getGaugeInformationForReachID": {
                    "gauges": [
                        {"gauge": {"source": "usgs", "source_id": "14181500"}},
                        {"gauge": {"source": "canada", "source_id": "08NM116"}},
                    ]
                }
            }
        }
        session.post.return_value = response
        client = AWClient(config, session)

        result = client._fetch_gauges_for_reach(1234)
        assert len(result) == 2
        assert result[0]["source"] == "usgs"
        assert result[1]["source"] == "canada"

    def test_returns_empty_list_when_null_response(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"getGaugeInformationForReachID": None}
        }
        session.post.return_value = response
        client = AWClient(config, session)

        result = client._fetch_gauges_for_reach(1234)
        assert result == []


class TestFetchReachesForState:
    """Tests for _fetch_reaches_for_state via GraphQL API."""

    def test_raises_on_connection_error(self):
        config = Config()
        session = MagicMock()
        session.post.side_effect = requests.exceptions.ConnectionError("fail")
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Network error"):
            client._fetch_reaches_for_state("OR")

    def test_raises_on_http_error(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        session.post.return_value = response
        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="HTTP 500"):
            client._fetch_reaches_for_state("OR")

    def test_parses_reaches_from_graphql_response(self):
        config = Config()
        session = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [
                        {"id": 1234, "river": "North Santiam", "section": "Upper", "altname": ""},
                        {"id": 5678, "river": "Clackamas", "section": "Lower", "altname": "Three Lynx"},
                    ],
                    "paginatorInfo": {"currentPage": 1, "lastPage": 1},
                }
            }
        }
        session.post.return_value = response
        client = AWClient(config, session)

        result = client._fetch_reaches_for_state("OR")
        assert len(result) == 2
        assert result[0] == (1234, "North Santiam - Upper")
        assert result[1] == (5678, "Clackamas - Lower (Three Lynx)")

    def test_returns_empty_list_for_unknown_state_code(self):
        config = Config()
        session = MagicMock()
        client = AWClient(config, session)

        result = client._fetch_reaches_for_state("XX")
        assert result == []
        # Should not make any API calls for unknown state
        session.post.assert_not_called()

    @patch("src.aw_client.time.sleep")
    def test_paginates_through_multiple_pages(self, mock_sleep):
        config = Config(aw_request_delay=0.1)
        session = MagicMock()

        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [{"id": 100, "river": "River A", "section": "Sec 1", "altname": ""}],
                    "paginatorInfo": {"currentPage": 1, "lastPage": 2},
                }
            }
        }

        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [{"id": 200, "river": "River B", "section": "Sec 2", "altname": ""}],
                    "paginatorInfo": {"currentPage": 2, "lastPage": 2},
                }
            }
        }

        session.post.side_effect = [page1_response, page2_response]
        client = AWClient(config, session)

        result = client._fetch_reaches_for_state("OR")
        assert len(result) == 2
        assert result[0] == (100, "River A - Sec 1")
        assert result[1] == (200, "River B - Sec 2")
        assert session.post.call_count == 2
        mock_sleep.assert_called_with(0.1)


class TestFetchReachMapping:
    """Tests for the full fetch_reach_mapping orchestration."""

    @patch("src.aw_client.time.sleep")
    def test_orchestrates_full_flow(self, mock_sleep):
        config = Config(aw_request_delay=0.1)
        session = MagicMock()

        # First call: reaches query for state
        reaches_response = MagicMock()
        reaches_response.status_code = 200
        reaches_response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [{"id": 1234, "river": "North Santiam", "section": "Upper", "altname": ""}],
                    "paginatorInfo": {"currentPage": 1, "lastPage": 1},
                }
            }
        }

        # Second call: gauge info for reach
        gauge_response = MagicMock()
        gauge_response.status_code = 200
        gauge_response.json.return_value = {
            "data": {
                "getGaugeInformationForReachID": {
                    "gauges": [
                        {"gauge": {"source": "usgs", "source_id": "14181500"}}
                    ]
                }
            }
        }

        session.post.side_effect = [reaches_response, gauge_response]

        client = AWClient(config, session)
        result = client.fetch_reach_mapping(["OR"])

        assert "14181500" in result
        assert result["14181500"][0].reach_id == 1234
        assert result["14181500"][0].reach_name == "North Santiam - Upper"
        mock_sleep.assert_called_with(0.1)

    @patch("src.aw_client.time.sleep")
    def test_handles_multiple_states(self, mock_sleep):
        config = Config(aw_request_delay=0.0)
        session = MagicMock()

        # Reaches response (same for both states in this test)
        reaches_response = MagicMock()
        reaches_response.status_code = 200
        reaches_response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [{"id": 100, "river": "River A", "section": "Sec", "altname": ""}],
                    "paginatorInfo": {"currentPage": 1, "lastPage": 1},
                }
            }
        }

        # Gauge response
        gauge_response = MagicMock()
        gauge_response.status_code = 200
        gauge_response.json.return_value = {
            "data": {
                "getGaugeInformationForReachID": {
                    "gauges": [
                        {"gauge": {"source": "usgs", "source_id": "11111111"}}
                    ]
                }
            }
        }

        # Two states: OR reaches, OR gauge, WA reaches, WA gauge
        session.post.side_effect = [
            reaches_response, gauge_response,
            reaches_response, gauge_response,
        ]

        client = AWClient(config, session)
        result = client.fetch_reach_mapping(["OR", "WA"])

        assert "11111111" in result
        # 4 POST calls: reaches(OR), gauge(reach 100), reaches(WA), gauge(reach 100)
        assert session.post.call_count == 4
