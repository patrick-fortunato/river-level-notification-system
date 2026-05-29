# Feature: river-level-notification-system, Property 5: Independent Email Delivery
"""Property test for independent email delivery.

Simulates lists of subscribers with mixed success/failure outcomes, verifies
the system attempts to send to every subscriber regardless of prior failures.

Validates: Requirements 4.4, 4.5
"""

from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.logger import PipelineLogger
from src.models import GaugeEntry, Subscriber
from src.pipeline import Pipeline


@settings(max_examples=100)
@given(
    outcomes=st.lists(
        st.booleans(),  # True = success, False = failure
        min_size=2,
        max_size=15,
    ),
)
def test_all_subscribers_attempted_regardless_of_failures(outcomes: list[bool]):
    """Verify the system attempts to send to every subscriber regardless of prior failures."""
    config = Config(
        service_account_file="fake_sa.json",
        gmail_token_file="fake_token.json",
        gmail_client_secrets_file="fake_client.json",
        spreadsheet_id="fake_id",
        sender_email="sender@example.com",
        email_delay_seconds=0,
    )

    # Create subscribers (one per outcome)
    subscribers = [
        Subscriber(email=f"user{i}@example.com", included_gauges=[])
        for i in range(len(outcomes))
    ]

    # Create gauge data so reports are non-empty
    gauge_data = {
        "12345": GaugeEntry(
            gauge_number="12345",
            gauge_name="Test River",
            usgs_page_url="https://waterdata.usgs.gov/nwis/uv?site_no=12345",
            reading_datetime="2025-01-15T08:00:00",
            flow_level="500",
        )
    }

    send_attempts: list[str] = []

    def mock_send_email(recipient, html_body, state_code=None):
        send_attempts.append(recipient)
        idx = len(send_attempts) - 1
        return outcomes[idx] if idx < len(outcomes) else True

    # Mock the pipeline components
    with patch("src.pipeline.ConfigValidator") as mock_validator, \
         patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
         patch("src.pipeline.SheetReader") as mock_reader_cls, \
         patch("src.pipeline.EmailSender") as mock_sender_cls:

        # Validator passes
        mock_validator.return_value.validate_all.return_value = []

        # USGS returns gauge data
        mock_fetcher_cls.return_value.fetch_all_state_gauges.return_value = gauge_data

        # Sheet reader returns subscribers
        mock_reader_cls.return_value.get_subscribers.return_value = subscribers

        # Email sender
        mock_sender = MagicMock()
        mock_sender.send_email.side_effect = mock_send_email
        mock_sender_cls.return_value = mock_sender

        pipeline = Pipeline(config)
        pipeline.run()

    # Verify every subscriber was attempted
    assert len(send_attempts) == len(subscribers)
    for i, sub in enumerate(subscribers):
        assert send_attempts[i] == sub.email
