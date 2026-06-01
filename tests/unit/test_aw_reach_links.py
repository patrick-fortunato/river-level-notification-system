"""Unit tests for AW reach links feature error handling.

Tests that AWClientError propagates correctly through the full
fetch_reach_mapping flow when underlying requests fail.

Requirements: 1.5
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.aw_client import AWClient, AWClientError
from src.config import Config


class TestAWClientErrorHandling:
    """Tests for AWClientError raised through fetch_reach_mapping end-to-end."""

    @patch("src.aw_client.time.sleep")
    def test_raises_awclient_error_on_network_failure(self, mock_sleep):
        """AWClientError is raised when a network connection error occurs.

        Simulates a ConnectionError on the GraphQL POST request,
        verifying the error propagates through fetch_reach_mapping.
        """
        config = Config(aw_request_delay=0.0)
        session = MagicMock()
        session.post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Network error"):
            client.fetch_reach_mapping(["OR"])

    @patch("src.aw_client.time.sleep")
    def test_raises_awclient_error_on_http_error_response(self, mock_sleep):
        """AWClientError is raised when the AW API returns HTTP 4xx/5xx.

        Simulates a 500 Internal Server Error on the reaches GraphQL request,
        verifying the error propagates through fetch_reach_mapping.
        """
        config = Config(aw_request_delay=0.0)
        session = MagicMock()

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        session.post.return_value = error_response

        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="HTTP 500"):
            client.fetch_reach_mapping(["OR"])

    @patch("src.aw_client.time.sleep")
    def test_raises_awclient_error_on_malformed_json_response(self, mock_sleep):
        """AWClientError is raised when the GraphQL response is not valid JSON.

        Simulates a successful reaches query (returning one reach), then a
        gauge info response that fails JSON parsing, verifying the error
        propagates through fetch_reach_mapping.
        """
        config = Config(aw_request_delay=0.0)
        session = MagicMock()

        # First POST: reaches query returns valid data with one reach
        reaches_response = MagicMock()
        reaches_response.status_code = 200
        reaches_response.json.return_value = {
            "data": {
                "reaches": {
                    "data": [{"id": 1234, "river": "Test", "section": "River", "altname": ""}],
                    "paginatorInfo": {"currentPage": 1, "lastPage": 1},
                }
            }
        }

        # Second POST: gauge info response fails JSON parsing
        graphql_response = MagicMock()
        graphql_response.status_code = 200
        graphql_response.json.side_effect = ValueError("No JSON object could be decoded")

        session.post.side_effect = [reaches_response, graphql_response]

        client = AWClient(config, session)

        with pytest.raises(AWClientError, match="Malformed JSON"):
            client.fetch_reach_mapping(["OR"])
