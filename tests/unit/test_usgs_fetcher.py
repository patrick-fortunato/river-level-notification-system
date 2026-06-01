"""Unit tests for the USGS data fetcher.

Tests URL construction, parsing edge cases, and error handling.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

from unittest.mock import patch, MagicMock

import pytest
import requests
import responses

from src.config import Config
from src.usgs_fetcher import USGSFetcher, USGSFetchError


class TestParseResponse:
    """Tests for USGS JSON response parsing."""

    def test_empty_time_series_returns_empty_dict(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {"value": {"timeSeries": []}}
        result = fetcher._parse_response(json_data)
        assert result == {}

    def test_missing_value_key_returns_empty_dict(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {}
        result = fetcher._parse_response(json_data)
        assert result == {}

    def test_missing_site_code_skips_entry(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {"siteName": "Test River", "siteCode": []},
                        "values": [{"value": [{"value": "100", "dateTime": "2025-01-15T08:00:00"}]}],
                    }
                ]
            }
        }
        result = fetcher._parse_response(json_data)
        assert result == {}

    def test_missing_site_name_skips_entry(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {"siteName": "", "siteCode": [{"value": "12345"}]},
                        "values": [{"value": [{"value": "100", "dateTime": "2025-01-15T08:00:00"}]}],
                    }
                ]
            }
        }
        result = fetcher._parse_response(json_data)
        assert result == {}

    def test_missing_values_skips_entry(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {"siteName": "Test River", "siteCode": [{"value": "12345"}]},
                        "values": [],
                    }
                ]
            }
        }
        result = fetcher._parse_response(json_data)
        assert result == {}

    def test_multiple_gauges_parsed_correctly(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {"siteName": "River A", "siteCode": [{"value": "11111"}]},
                        "values": [{"value": [{"value": "500", "dateTime": "2025-01-15T08:00:00"}]}],
                    },
                    {
                        "sourceInfo": {"siteName": "River B", "siteCode": [{"value": "22222"}]},
                        "values": [{"value": [{"value": "750", "dateTime": "2025-01-15T09:00:00"}]}],
                    },
                ]
            }
        }
        result = fetcher._parse_response(json_data)
        assert len(result) == 2
        assert "11111" in result
        assert "22222" in result
        assert result["11111"].gauge_name == "River A"
        assert result["22222"].gauge_name == "River B"
        assert result["11111"].flow_level == "500"
        assert result["22222"].flow_level == "750"

    def test_uses_last_value_entry_as_most_recent(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        json_data = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {"siteName": "River A", "siteCode": [{"value": "11111"}]},
                        "values": [
                            {
                                "value": [
                                    {"value": "100", "dateTime": "2025-01-15T06:00:00"},
                                    {"value": "200", "dateTime": "2025-01-15T07:00:00"},
                                    {"value": "300", "dateTime": "2025-01-15T08:00:00"},
                                ]
                            }
                        ],
                    }
                ]
            }
        }
        result = fetcher._parse_response(json_data)
        assert result["11111"].flow_level == "300"
        assert result["11111"].reading_datetime == "2025-01-15T08:00:00"


class TestFetchGaugesByIds:
    """Tests for the fetch_gauges_by_ids method."""

    def test_empty_list_returns_empty_dict(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        result = fetcher.fetch_gauges_by_ids([])
        assert result == {}

    @responses.activate
    def test_builds_url_with_sites_parameter(self):
        config = Config()
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        json_response = {"value": {"timeSeries": []}}

        responses.add(
            responses.GET,
            config.usgs_base_url,
            json=json_response,
            status=200,
        )

        fetcher.fetch_gauges_by_ids(["14209500", "14211720"])

        # Verify the request URL contains sites= parameter
        assert len(responses.calls) == 1
        request_url = responses.calls[0].request.url
        assert "sites=14209500%2C14211720" in request_url or "sites=14209500,14211720" in request_url
        assert "parameterCd=00060" in request_url
        assert "format=json" in request_url
        # Should NOT contain stateCd
        assert "stateCd" not in request_url

    @responses.activate
    def test_successful_fetch_returns_gauge_data(self):
        config = Config()
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        json_response = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {
                            "siteName": "CLACKAMAS RIVER AT ESTACADA, OR",
                            "siteCode": [{"value": "14209500"}],
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "1500", "dateTime": "2025-01-15T08:00:00.000-08:00"}
                                ]
                            }
                        ],
                    },
                    {
                        "sourceInfo": {
                            "siteName": "WILLAMETTE RIVER AT PORTLAND, OR",
                            "siteCode": [{"value": "14211720"}],
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "12500", "dateTime": "2025-01-15T09:00:00.000-08:00"}
                                ]
                            }
                        ],
                    },
                ]
            }
        }

        responses.add(
            responses.GET,
            config.usgs_base_url,
            json=json_response,
            status=200,
        )

        result = fetcher.fetch_gauges_by_ids(["14209500", "14211720"])
        assert len(result) == 2
        assert "14209500" in result
        assert "14211720" in result
        assert result["14209500"].gauge_name == "CLACKAMAS RIVER AT ESTACADA, OR"
        assert result["14209500"].flow_level == "1500"
        assert result["14211720"].gauge_name == "WILLAMETTE RIVER AT PORTLAND, OR"
        assert result["14211720"].flow_level == "12500"

    @responses.activate
    def test_4xx_error_returns_empty_dict_does_not_raise(self):
        config = Config()
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        responses.add(
            responses.GET,
            config.usgs_base_url,
            status=400,
            body="Bad Request",
        )

        # Should NOT raise — returns empty dict gracefully
        result = fetcher.fetch_gauges_by_ids(["99999999"])
        assert result == {}

    @responses.activate
    def test_5xx_retries_and_returns_empty_on_exhaustion(self):
        config = Config(
            max_retries=2,
            initial_backoff_seconds=0.001,
            backoff_multiplier=1.5,
        )
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        # Add 3 responses (initial + 2 retries) all returning 500
        for _ in range(3):
            responses.add(
                responses.GET,
                config.usgs_base_url,
                status=500,
                body="Internal Server Error",
            )

        with patch("src.retry.time.sleep"):
            # Should NOT raise — returns empty dict gracefully
            result = fetcher.fetch_gauges_by_ids(["14209500"])
            assert result == {}

    @responses.activate
    def test_single_gauge_id(self):
        config = Config()
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        json_response = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {
                            "siteName": "TEST RIVER",
                            "siteCode": [{"value": "12345678"}],
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "800", "dateTime": "2025-01-15T10:00:00.000-08:00"}
                                ]
                            }
                        ],
                    }
                ]
            }
        }

        responses.add(
            responses.GET,
            config.usgs_base_url,
            json=json_response,
            status=200,
        )

        result = fetcher.fetch_gauges_by_ids(["12345678"])
        assert len(result) == 1
        assert result["12345678"].flow_level == "800"

    @responses.activate
    def test_connection_error_returns_empty_dict(self):
        config = Config(
            max_retries=1,
            initial_backoff_seconds=0.001,
        )
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        responses.add(
            responses.GET,
            config.usgs_base_url,
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            config.usgs_base_url,
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        with patch("src.retry.time.sleep"):
            result = fetcher.fetch_gauges_by_ids(["14209500"])
            assert result == {}
