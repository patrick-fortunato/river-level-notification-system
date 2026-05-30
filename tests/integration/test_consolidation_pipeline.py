"""Integration tests for the consolidated email pipeline.

End-to-end pipeline runs with mocked Sheet/USGS/Gmail verifying
consolidated output, email count matching unique subscriber count,
backward compatibility for single-row subscribers, case-insensitive
email grouping, and subject line determination.

Requirements: 1.1, 3.1, 4.1, 4.2
"""

from unittest.mock import MagicMock, patch

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
        usgs_state_code="OR",
        email_subject="Current {state_name} River Levels",
        consolidated_email_subject="Current River Levels",
    )
    defaults.update(overrides)
    return Config(**defaults)


def _make_gauge_data_for_state(state_code: str) -> dict[str, GaugeEntry]:
    """Create sample gauge data for a given state code."""
    gauge_number = {"OR": "11111", "WA": "22222", "CA": "33333"}.get(
        state_code, "99999"
    )
    return {
        gauge_number: GaugeEntry(
            gauge_number=gauge_number,
            gauge_name=f"RIVER AT CITY ({state_code})",
            usgs_page_url=f"https://waterdata.usgs.gov/nwis/uv?site_no={gauge_number}",
            reading_datetime="2025-01-15T08:00:00",
            flow_level="1500",
        ),
    }


def _run_pipeline(config, subscribers, send_results=None):
    """Run the pipeline with fully mocked external dependencies.

    Mocks ConfigValidator, USGSFetcher, SheetReader, and EmailSender.
    The USGSFetcher is set up to return appropriate gauge data per state.

    Returns:
        Tuple of (RunSummary, mock_sender) for assertions.
    """
    # Determine unique states (after normalization)
    normalized_subscribers = []
    for sub in subscribers:
        sc = sub.state_code if sub.state_code else config.usgs_state_code
        normalized_subscribers.append(sc)

    unique_states = sorted(set(normalized_subscribers))

    # Build state gauge data
    state_gauge_data = {sc: _make_gauge_data_for_state(sc) for sc in unique_states}

    # USGSFetcher is called once per unique state in sorted order
    fetch_iter = iter(unique_states)

    def mock_fetch():
        sc = next(fetch_iter)
        return state_gauge_data[sc]

    if send_results is None:
        send_results_iter = iter([True] * 100)
    else:
        send_results_iter = iter(send_results)

    def mock_send(recipient, html_body, state_code=None, subject=None):
        return next(send_results_iter)

    with patch("src.pipeline.ConfigValidator") as mock_validator, \
         patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
         patch("src.pipeline.SheetReader") as mock_reader_cls, \
         patch("src.pipeline.EmailSender") as mock_sender_cls:

        mock_validator.return_value.validate_all.return_value = []
        mock_fetcher_cls.return_value.fetch_all_state_gauges.side_effect = mock_fetch

        mock_reader = MagicMock()
        mock_reader.get_subscribers.return_value = subscribers
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.send_email.side_effect = mock_send
        mock_sender_cls.return_value = mock_sender

        pipeline = Pipeline(config)
        summary = pipeline.run()

        return summary, mock_sender


class TestConsolidatedPipelineIntegration:
    """Integration tests for the full consolidated email pipeline."""

    def test_multiple_rows_same_email_sends_one_email(self):
        """Multiple rows for the same email produce exactly one email sent.

        Validates: Requirements 1.1, 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="user@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.total_subscribers == 1

    def test_multiple_unique_emails_sends_one_per_email(self):
        """Multiple unique emails each get exactly one email.

        Validates: Requirements 1.1, 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="alice@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="bob@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="carol@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 3
        assert summary.emails_sent == 3
        assert summary.total_subscribers == 3

    def test_email_count_matches_unique_subscriber_count(self):
        """Email count equals the number of unique (case-insensitive) emails.

        Validates: Requirements 1.1, 3.1
        """
        config = _make_config()
        # 5 rows, but only 2 unique emails
        subscribers = [
            Subscriber(email="user1@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user1@example.com", included_gauges=[], state_code="WA"),
            Subscriber(email="user1@example.com", included_gauges=[], state_code="CA"),
            Subscriber(email="user2@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user2@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 2
        assert summary.emails_sent == 2
        assert summary.total_subscribers == 2

    def test_single_row_subscriber_backward_compatibility(self):
        """Single-row subscriber gets one email with state-specific subject.

        Validates: Requirements 4.1, 4.2
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="solo@example.com", included_gauges=[], state_code="OR"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.total_subscribers == 1

        # Verify state-specific subject
        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current Oregon River Levels"

    def test_case_insensitive_email_grouping_end_to_end(self):
        """Emails differing only in case are grouped into one send.

        Validates: Requirements 1.1, 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="User@Example.COM", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
            Subscriber(email="USER@EXAMPLE.COM", included_gauges=[], state_code="CA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.total_subscribers == 1

    def test_multi_state_subscriber_gets_generic_subject(self):
        """Multi-state subscriber receives email with generic subject line.

        Validates: Requirements 3.1, 4.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="multi@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="multi@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current River Levels"

    def test_single_state_subscriber_gets_state_specific_subject(self):
        """Single-state subscriber receives email with state-specific subject.

        Validates: Requirements 4.1, 4.2
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="single@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current Washington River Levels"

    def test_consolidated_email_contains_state_section_headings(self):
        """Multi-state subscriber's email HTML contains state section headings.

        Validates: Requirements 1.1, 3.1, 4.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="user@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        # Get the HTML body passed to send_email
        call_args = mock_sender.send_email.call_args
        html_body = call_args[0][1]

        # Verify state section headings are present
        assert "Oregon" in html_body
        assert "Washington" in html_body

    def test_empty_state_code_normalized_to_config_default(self):
        """Subscriber with empty state_code uses the config default before grouping.

        Validates: Requirements 4.1, 4.2
        """
        config = _make_config(usgs_state_code="OR")
        subscribers = [
            Subscriber(email="user@example.com", included_gauges=[], state_code=""),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        # Should use state-specific subject since it's a single-state subscriber
        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current Oregon River Levels"

    def test_mixed_single_and_multi_state_subscribers(self):
        """Pipeline handles a mix of single-state and multi-state subscribers.

        Validates: Requirements 1.1, 3.1, 4.1, 4.2
        """
        config = _make_config()
        subscribers = [
            # Multi-state subscriber
            Subscriber(email="multi@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="multi@example.com", included_gauges=[], state_code="WA"),
            # Single-state subscriber
            Subscriber(email="single@example.com", included_gauges=[], state_code="OR"),
        ]

        summary, mock_sender = _run_pipeline(config, subscribers)

        assert mock_sender.send_email.call_count == 2
        assert summary.emails_sent == 2
        assert summary.total_subscribers == 2

        # Verify subjects: find which call is for which subscriber
        calls = mock_sender.send_email.call_args_list
        subjects = [call[1]["subject"] for call in calls]
        recipients = [call[0][0] for call in calls]

        for recipient, subject in zip(recipients, subjects):
            if recipient == "multi@example.com":
                assert subject == "Current River Levels"
            elif recipient == "single@example.com":
                assert subject == "Current Oregon River Levels"

    def test_send_failure_tracked_in_summary(self):
        """Send failures are correctly tracked in the run summary.

        Validates: Requirements 3.1, 4.2
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="success@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="fail@example.com", included_gauges=[], state_code="OR"),
        ]

        summary, mock_sender = _run_pipeline(
            config, subscribers, send_results=[True, False]
        )

        assert summary.total_subscribers == 2
        assert summary.emails_sent == 1
        assert summary.emails_failed == 1
