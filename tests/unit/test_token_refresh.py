"""Unit tests for OAuth2 token refresh in the email sender.

Tests successful token refresh, failed refresh, and non-expired token handling.

Requirements: 8.1, 8.2, 8.3
"""

import json
from unittest.mock import patch, MagicMock, mock_open

import pytest

from src.config import Config
from src.email_sender import EmailSender, TokenRefreshError
from src.logger import PipelineLogger


class TestTokenRefresh:
    """Tests for _refresh_token_if_needed behavior."""

    def _make_sender(self) -> EmailSender:
        config = Config(
            gmail_token_file="fake_token.json",
            sender_email="sender@example.com",
        )
        return EmailSender(config, PipelineLogger())

    def test_valid_token_used_as_is(self):
        """Non-expired token should be returned without refresh."""
        sender = self._make_sender()

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        result = sender._refresh_token_if_needed(mock_creds)

        assert result is mock_creds
        mock_creds.refresh.assert_not_called()

    def test_expired_token_refreshed_and_persisted(self):
        """Expired token with refresh_token should be refreshed and saved."""
        sender = self._make_sender()

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_value"
        mock_creds.to_json.return_value = '{"token": "new_token"}'

        m = mock_open()
        with patch("builtins.open", m):
            result = sender._refresh_token_if_needed(mock_creds)

        mock_creds.refresh.assert_called_once()
        m.assert_called_once_with("fake_token.json", "w")
        m().write.assert_called_once_with('{"token": "new_token"}')
        assert result is mock_creds

    def test_refresh_failure_raises_token_refresh_error(self):
        """Failed refresh should raise TokenRefreshError."""
        sender = self._make_sender()

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_value"
        mock_creds.refresh.side_effect = Exception("Refresh token revoked")

        with pytest.raises(TokenRefreshError, match="Token refresh failed"):
            sender._refresh_token_if_needed(mock_creds)

    def test_invalid_token_without_refresh_token_raises_error(self):
        """Invalid token without refresh_token should raise TokenRefreshError."""
        sender = self._make_sender()

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = False
        mock_creds.refresh_token = None

        with pytest.raises(TokenRefreshError, match="cannot be refreshed"):
            sender._refresh_token_if_needed(mock_creds)

    def test_expired_token_without_refresh_token_raises_error(self):
        """Expired token without refresh_token should raise TokenRefreshError."""
        sender = self._make_sender()

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = None

        with pytest.raises(TokenRefreshError, match="cannot be refreshed"):
            sender._refresh_token_if_needed(mock_creds)
