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


class TestBuildRequestUrl:
    """Tests for URL construction."""

    def test_url_contains_state_code(self):
        config = Config(usgs_state_code="WA")
        fetcher = USGSFetcher(config, requests.Session())
        url = fetcher._build_request_url()
        assert "stateCd=WA" in url

    def test_url_contains_parameter_code(self):
        config = Config(usgs_parameter_code="00060")
        fetcher = USGSFetcher(config, requests.Session())
        url = fetcher._build_request_url()
        assert "parameterCd=00060" in url

    def test_url_contains_json_format(self):
        config = Config(usgs_format="json")
        fetcher = USGSFetcher(config, requests.Session())
        url = fetcher._build_request_url()
        assert "format=json" in url

    def test_url_uses_configured_base_url(self):
        config = Config(usgs_base_url="https://example.com/api/")
        fetcher = USGSFetcher(config, requests.Session())
        url = fetcher._build_request_url()
        assert url.startswith("https://example.com/api/")

    def test_default_state_is_oregon(self):
        config = Config()
        fetcher = USGSFetcher(config, requests.Session())
        url = fetcher._build_request_url()
        assert "stateCd=OR" in url


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


class TestFetchAllStateGauges:
    """Tests for the full fetch flow with error handling."""

    @responses.activate
    def test_4xx_raises_usgs_fetch_error(self):
        config = Config(usgs_state_code="XX")
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        responses.add(
            responses.GET,
            config.usgs_base_url,
            status=400,
            body="Bad Request",
        )

        with pytest.raises(USGSFetchError, match="client error 400"):
            fetcher.fetch_all_state_gauges()

    @responses.activate
    def test_5xx_retries_and_raises_on_exhaustion(self):
        config = Config(
            usgs_state_code="OR",
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
            with pytest.raises(USGSFetchError, match="Failed to fetch"):
                fetcher.fetch_all_state_gauges()

    @responses.activate
    def test_successful_fetch_returns_gauge_data(self):
        config = Config(usgs_state_code="OR")
        session = requests.Session()
        fetcher = USGSFetcher(config, session)

        json_response = {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {
                            "siteName": "WILLAMETTE RIVER AT PORTLAND, OR",
                            "siteCode": [{"value": "14211720"}],
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "12500", "dateTime": "2025-01-15T08:00:00.000-08:00"}
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

        result = fetcher.fetch_all_state_gauges()
        assert "14211720" in result
        assert result["14211720"].gauge_name == "WILLAMETTE RIVER AT PORTLAND, OR"
        assert result["14211720"].flow_level == "12500"
