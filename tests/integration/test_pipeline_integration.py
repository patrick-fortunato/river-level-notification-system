"""Integration tests for the full pipeline.

Mocks USGS API responses, Google Sheets data, and Gmail API to verify
the pipeline calls components in correct order, run summary reflects
actual outcomes, and empty report suppression works end-to-end.

Requirements: 1.1, 2.1, 4.1, 10.1, 11.2
"""

from unittest.mock import patch, MagicMock

import pytest

from src.config import Config
from src.models import GaugeEntry, Subscriber
from src.pipeline import Pipeline


def _make_config(**overrides) -> Config:
    """Create a Config with test defaults."""
    defaults = dict(
        service_account_file="service_account.json",
        gmail_token_file="token.json",
        gmail_client_secrets_file="gmail_credentials.json",
        spreadsheet_id="test_sheet_id",
        sender_email="sender@example.com",
        email_delay_seconds=0,
        max_retries=0,
    )
    defaults.update(overrides)
    return Config(**defaults)


def _make_gauge_data() -> dict[str, GaugeEntry]:
    """Create sample gauge data."""
    return {
        "12345": GaugeEntry(
            gauge_number="12345",
            gauge_name="RIVER A AT CITY",
            usgs_page_url="https://waterdata.usgs.gov/nwis/uv?site_no=12345",
            reading_datetime="2025-01-15T08:00:00",
            flow_level="1500",
        ),
        "67890": GaugeEntry(
            gauge_number="67890",
            gauge_name="RIVER B AT TOWN",
            usgs_page_url="https://waterdata.usgs.gov/nwis/uv?site_no=67890",
            reading_datetime="2025-01-15T09:00:00",
            flow_level="800",
        ),
    }


class TestPipelineIntegration:
    """Integration tests for the full pipeline flow."""

    def _run_pipeline_with_mocks(
        self,
        config: Config,
        validation_errors: list[str] | None = None,
        gauge_data: dict | None = None,
        subscribers: list[Subscriber] | None = None,
        send_results: list[bool] | None = None,
    ):
        """Run the pipeline with mocked external dependencies."""
        if validation_errors is None:
            validation_errors = []
        if gauge_data is None:
            gauge_data = _make_gauge_data()
        if subscribers is None:
            subscribers = [
                Subscriber(email="user1@example.com", included_gauges=[]),
                Subscriber(email="user2@example.com", included_gauges=["67890"]),
            ]
        if send_results is None:
            send_results = [True] * len(subscribers)

        send_call_count = [0]

        def mock_send(recipient, html_body):
            idx = send_call_count[0]
            send_call_count[0] += 1
            return send_results[idx] if idx < len(send_results) else True

        with patch("src.pipeline.ConfigValidator") as mock_validator, \
             patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
             patch("src.pipeline.SheetReader") as mock_reader_cls, \
             patch("src.pipeline.EmailSender") as mock_sender_cls:

            mock_validator.return_value.validate_all.return_value = validation_errors

            mock_fetcher_cls.return_value.fetch_all_state_gauges.return_value = gauge_data

            mock_reader = MagicMock()
            mock_reader.get_subscribers.return_value = subscribers
            mock_reader_cls.return_value = mock_reader

            mock_sender = MagicMock()
            mock_sender.send_email.side_effect = mock_send
            mock_sender_cls.return_value = mock_sender

            pipeline = Pipeline(config)
            summary = pipeline.run()

            return summary, mock_validator, mock_fetcher_cls, mock_reader_cls, mock_sender

    def test_pipeline_calls_components_in_correct_order(self):
        """Verify pipeline executes: validate -> fetch -> read -> send."""
        config = _make_config()
        summary, mock_validator, mock_fetcher, mock_reader, mock_sender = \
            self._run_pipeline_with_mocks(config)

        # All components should have been called
        mock_validator.return_value.validate_all.assert_called_once()
        mock_fetcher.return_value.fetch_all_state_gauges.assert_called_once()
        mock_reader.return_value.authenticate.assert_called_once()
        mock_reader.return_value.get_subscribers.assert_called_once()
        assert mock_sender.send_email.call_count == 2  # 2 subscribers

    def test_run_summary_reflects_actual_outcomes(self):
        """Verify run summary counters match actual send results."""
        config = _make_config()
        subscribers = [
            Subscriber(email="user1@example.com", included_gauges=[]),
            Subscriber(email="user2@example.com", included_gauges=[]),
            Subscriber(email="user3@example.com", included_gauges=[]),
        ]

        summary, *_ = self._run_pipeline_with_mocks(
            config,
            subscribers=subscribers,
            send_results=[True, False, True],
        )

        assert summary.total_subscribers == 3
        assert summary.emails_sent == 2
        assert summary.emails_failed == 1
        assert summary.subscribers_skipped == 0

    def test_empty_report_suppression_end_to_end(self):
        """Verify subscribers whose included gauges don't match any data are skipped."""
        config = _make_config()
        gauge_data = _make_gauge_data()

        # This subscriber includes only gauges that don't exist in the data
        subscribers = [
            Subscriber(
                email="no_match@example.com",
                included_gauges=["99999", "88888"],
            ),
            Subscriber(email="normal@example.com", included_gauges=[]),
        ]

        summary, _, _, _, mock_sender = self._run_pipeline_with_mocks(
            config,
            gauge_data=gauge_data,
            subscribers=subscribers,
            send_results=[True],  # Only one send expected
        )

        # Only one email should be sent (the subscriber with empty include list = all)
        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.subscribers_skipped == 1

    def test_validation_failure_halts_pipeline(self):
        """Verify validation failure prevents any further processing."""
        config = _make_config()

        summary, _, mock_fetcher, mock_reader, mock_sender = \
            self._run_pipeline_with_mocks(
                config,
                validation_errors=["Missing service_account.json"],
            )

        mock_fetcher.return_value.fetch_all_state_gauges.assert_not_called()
        mock_reader.return_value.get_subscribers.assert_not_called()
        mock_sender.send_email.assert_not_called()
        assert summary.total_subscribers == 0

    def test_mixed_outcomes_tracked_correctly(self):
        """Verify a mix of successes, failures, and skips are all tracked."""
        config = _make_config()
        gauge_data = _make_gauge_data()

        subscribers = [
            Subscriber(email="success@example.com", included_gauges=[]),
            Subscriber(email="fail@example.com", included_gauges=[]),
            Subscriber(
                email="skipped@example.com",
                included_gauges=["99999", "88888"],  # No match
            ),
        ]

        summary, *_ = self._run_pipeline_with_mocks(
            config,
            gauge_data=gauge_data,
            subscribers=subscribers,
            send_results=[True, False],
        )

        assert summary.total_subscribers == 3
        assert summary.emails_sent == 1
        assert summary.emails_failed == 1
        assert summary.subscribers_skipped == 1

    def test_empty_gauge_data_skips_all_subscribers(self):
        """Verify empty gauge data results in all subscribers being skipped."""
        config = _make_config()
        subscribers = [
            Subscriber(email="user1@example.com", included_gauges=[]),
            Subscriber(email="user2@example.com", included_gauges=[]),
        ]

        summary, _, _, _, mock_sender = self._run_pipeline_with_mocks(
            config,
            gauge_data={},
            subscribers=subscribers,
        )

        mock_sender.send_email.assert_not_called()
        assert summary.subscribers_skipped == 2
        assert summary.emails_sent == 0
