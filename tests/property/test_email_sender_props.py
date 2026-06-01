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
from src.models import GaugeEntry, ReachSubscriber, ResolvedReach
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

    # Create subscribers (one per outcome) — each subscribes to reach 1001
    subscribers = [
        ReachSubscriber(email=f"user{i}@example.com", reach_ids=[1001])
        for i in range(len(outcomes))
    ]

    # Resolved reaches so reports are non-empty
    resolved_reaches = {
        1001: ResolvedReach(reach_id=1001, reach_name="Test River", gauge_id="12345")
    }

    # Create gauge data so reports are non-empty
    gauge_data = {
        "12345": GaugeEntry(
            gauge_number="12345",
            gauge_name="Test River",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00",
            flow_level="500",
        )
    }

    send_attempts: list[str] = []

    def mock_send_email(recipient, html_body, subject=None):
        send_attempts.append(recipient)
        idx = len(send_attempts) - 1
        return outcomes[idx] if idx < len(outcomes) else True

    # Mock the pipeline components
    with patch("src.pipeline.ConfigValidator") as mock_validator, \
         patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
         patch("src.pipeline.SheetReader") as mock_reader_cls, \
         patch("src.pipeline.EmailSender") as mock_sender_cls, \
         patch("src.pipeline.ReachResolver") as mock_resolver_cls, \
         patch("src.pipeline.ReachCache"):

        # Validator passes
        mock_validator.return_value.validate_all.return_value = []

        # Sheet reader returns subscribers
        mock_reader_cls.return_value.get_subscribers.return_value = subscribers

        # ReachResolver returns resolved reaches
        mock_resolver_cls.return_value.resolve_reaches.return_value = resolved_reaches

        # USGS fetcher returns gauge data
        mock_fetcher_cls.return_value.fetch_gauges_by_ids.return_value = gauge_data

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
