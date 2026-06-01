"""Unit tests for pipeline consolidation behavior.

Tests subject line formatting, one-email-per-subscriber delivery,
and backward compatibility for single-row subscribers.

Requirements: 3.1, 3.2, 4.1, 4.2
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.models import GaugeEntry, GroupedSubscriber, StatePreference, Subscriber
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


def _make_gauge_data(state_code: str = "OR") -> dict[str, GaugeEntry]:
    """Create sample gauge data for a given state."""
    return {
        "12345": GaugeEntry(
            gauge_number="12345",
            gauge_name=f"RIVER A AT CITY ({state_code})",
            usgs_page_url=f"https://waterdata.usgs.gov/monitoring-location/USGS-12345/#period=P7D&dataTypeId=continuous-00060-0&showMedian=true&showFieldMeasurements=true",
            reading_datetime="2025-01-15T08:00:00",
            flow_level="1500",
        ),
    }


class TestSubjectLineFormatting:
    """Tests for subject line determination based on subscriber state count."""

    def test_multi_state_subscriber_uses_generic_subject(self):
        """Multi-state subscribers get the consolidated subject without state name.

        Validates: Requirement 3.2
        """
        config = _make_config()
        pipeline = Pipeline(config)

        grouped_sub = GroupedSubscriber(
            email="multi@example.com",
            state_preferences=[
                StatePreference(state_code="OR", included_gauges=[]),
                StatePreference(state_code="WA", included_gauges=[]),
            ],
        )

        subject = pipeline._determine_subject(grouped_sub)
        assert subject == "Current River Levels"

    def test_single_state_subscriber_uses_state_specific_subject(self):
        """Single-state subscribers get the state-specific subject format.

        Validates: Requirement 4.1
        """
        config = _make_config()
        pipeline = Pipeline(config)

        grouped_sub = GroupedSubscriber(
            email="single@example.com",
            state_preferences=[
                StatePreference(state_code="OR", included_gauges=[]),
            ],
        )

        subject = pipeline._determine_subject(grouped_sub)
        assert subject == "Current Oregon River Levels"

    def test_single_state_wa_subscriber_uses_washington_subject(self):
        """Single-state WA subscriber gets 'Washington' in subject.

        Validates: Requirement 4.1
        """
        config = _make_config()
        pipeline = Pipeline(config)

        grouped_sub = GroupedSubscriber(
            email="wa_user@example.com",
            state_preferences=[
                StatePreference(state_code="WA", included_gauges=[]),
            ],
        )

        subject = pipeline._determine_subject(grouped_sub)
        assert subject == "Current Washington River Levels"

    def test_three_state_subscriber_uses_generic_subject(self):
        """Subscriber with three states still gets the generic subject.

        Validates: Requirement 3.2
        """
        config = _make_config()
        pipeline = Pipeline(config)

        grouped_sub = GroupedSubscriber(
            email="many@example.com",
            state_preferences=[
                StatePreference(state_code="OR", included_gauges=[]),
                StatePreference(state_code="WA", included_gauges=[]),
                StatePreference(state_code="CA", included_gauges=[]),
            ],
        )

        subject = pipeline._determine_subject(grouped_sub)
        assert subject == "Current River Levels"


class TestPipelineSendsOneEmailPerGroupedSubscriber:
    """Tests that the pipeline sends exactly one email per grouped subscriber.

    Validates: Requirement 3.1, 4.1
    """

    def _run_pipeline_with_subscribers(
        self, config: Config, subscribers: list[Subscriber]
    ):
        """Run the pipeline with mocked dependencies and return the mock sender."""
        # Build state gauge data for all states referenced
        state_codes = set()
        for sub in subscribers:
            state_codes.add(sub.state_code if sub.state_code else config.usgs_state_code)

        state_gauge_data = {}
        for sc in state_codes:
            state_gauge_data[sc] = _make_gauge_data(sc)

        fetch_calls = iter(sorted(state_codes))

        def mock_fetch():
            sc = next(fetch_calls)
            return state_gauge_data[sc]

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
            mock_sender.send_email.return_value = True
            mock_sender_cls.return_value = mock_sender

            pipeline = Pipeline(config)
            summary = pipeline.run()

            return summary, mock_sender

    def test_two_rows_same_email_sends_one_email(self):
        """Two subscriber rows with the same email produce exactly one send call.

        Validates: Requirement 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="user@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = self._run_pipeline_with_subscribers(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.total_subscribers == 1

    def test_three_rows_two_unique_emails_sends_two_emails(self):
        """Three rows with two unique emails produce exactly two send calls.

        Validates: Requirement 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="alice@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="alice@example.com", included_gauges=[], state_code="WA"),
            Subscriber(email="bob@example.com", included_gauges=[], state_code="OR"),
        ]

        summary, mock_sender = self._run_pipeline_with_subscribers(config, subscribers)

        assert mock_sender.send_email.call_count == 2
        assert summary.emails_sent == 2
        assert summary.total_subscribers == 2

    def test_case_insensitive_grouping_sends_one_email(self):
        """Rows with same email in different cases produce one send call.

        Validates: Requirements 1.1, 3.1
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="User@Example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = self._run_pipeline_with_subscribers(config, subscribers)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1

    def test_multi_state_email_uses_consolidated_subject(self):
        """Multi-state subscriber email is sent with the consolidated subject.

        Validates: Requirement 3.2
        """
        config = _make_config()
        subscribers = [
            Subscriber(email="user@example.com", included_gauges=[], state_code="OR"),
            Subscriber(email="user@example.com", included_gauges=[], state_code="WA"),
        ]

        summary, mock_sender = self._run_pipeline_with_subscribers(config, subscribers)

        # Verify the subject passed to send_email
        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current River Levels"


class TestSingleRowBackwardCompatibility:
    """Tests that single-row subscribers behave the same as before consolidation.

    Validates: Requirement 4.2
    """

    def _run_pipeline_single_subscriber(self, config: Config, subscriber: Subscriber):
        """Run the pipeline with a single subscriber and return mock sender."""
        state_code = subscriber.state_code if subscriber.state_code else config.usgs_state_code
        gauge_data = _make_gauge_data(state_code)

        with patch("src.pipeline.ConfigValidator") as mock_validator, \
             patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
             patch("src.pipeline.SheetReader") as mock_reader_cls, \
             patch("src.pipeline.EmailSender") as mock_sender_cls:

            mock_validator.return_value.validate_all.return_value = []
            mock_fetcher_cls.return_value.fetch_all_state_gauges.return_value = gauge_data

            mock_reader = MagicMock()
            mock_reader.get_subscribers.return_value = [subscriber]
            mock_reader_cls.return_value = mock_reader

            mock_sender = MagicMock()
            mock_sender.send_email.return_value = True
            mock_sender_cls.return_value = mock_sender

            pipeline = Pipeline(config)
            summary = pipeline.run()

            return summary, mock_sender

    def test_single_row_subscriber_sends_one_email(self):
        """A single-row subscriber still receives exactly one email.

        Validates: Requirement 4.2
        """
        config = _make_config()
        subscriber = Subscriber(
            email="solo@example.com", included_gauges=[], state_code="OR"
        )

        summary, mock_sender = self._run_pipeline_single_subscriber(config, subscriber)

        assert mock_sender.send_email.call_count == 1
        assert summary.emails_sent == 1
        assert summary.total_subscribers == 1

    def test_single_row_subscriber_uses_state_specific_subject(self):
        """A single-row subscriber gets the state-specific subject line.

        Validates: Requirements 4.1, 4.2
        """
        config = _make_config()
        subscriber = Subscriber(
            email="solo@example.com", included_gauges=[], state_code="OR"
        )

        summary, mock_sender = self._run_pipeline_single_subscriber(config, subscriber)

        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current Oregon River Levels"

    def test_single_row_subscriber_email_sent_to_correct_recipient(self):
        """A single-row subscriber's email is sent to the correct address.

        Validates: Requirement 4.2
        """
        config = _make_config()
        subscriber = Subscriber(
            email="solo@example.com", included_gauges=[], state_code="OR"
        )

        summary, mock_sender = self._run_pipeline_single_subscriber(config, subscriber)

        call_args = mock_sender.send_email.call_args
        assert call_args[0][0] == "solo@example.com"

    def test_single_row_subscriber_with_default_state(self):
        """A single-row subscriber with empty state_code uses the config default.

        Validates: Requirement 4.2
        """
        config = _make_config(usgs_state_code="OR")
        subscriber = Subscriber(
            email="default@example.com", included_gauges=[], state_code=""
        )

        summary, mock_sender = self._run_pipeline_single_subscriber(config, subscriber)

        assert mock_sender.send_email.call_count == 1
        call_kwargs = mock_sender.send_email.call_args
        assert call_kwargs[1]["subject"] == "Current Oregon River Levels"
