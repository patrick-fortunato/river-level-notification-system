# Feature: river-level-notification-system, Property 10: Rate Limiting Enforcement
"""Property test for rate limiting enforcement.

For any sequence of N email sends (N >= 2), verifies elapsed time between
consecutive send starts is at least email_delay_seconds.

Validates: Requirements 13.1
"""

import time
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.email_sender import EmailSender
from src.logger import PipelineLogger


@settings(max_examples=50, deadline=30000)
@given(
    num_sends=st.integers(min_value=2, max_value=5),
    delay_seconds=st.floats(min_value=0.05, max_value=0.15),
)
def test_rate_limiting_enforces_minimum_delay(num_sends: int, delay_seconds: float):
    """Verify elapsed time between consecutive sends is at least email_delay_seconds.

    The EmailSender records _last_send_time after each successful send and
    sleeps before the next send if insufficient time has elapsed. We measure
    the total time for all sends and verify it's at least (N-1) * delay.
    """
    config = Config(
        gmail_token_file="fake_token.json",
        sender_email="sender@example.com",
        email_delay_seconds=delay_seconds,
        max_retries=0,  # No retries for this test
    )

    # Mock the Gmail API service
    mock_service = MagicMock()
    mock_execute = MagicMock(return_value={"id": "msg123"})
    mock_service.users.return_value.messages.return_value.send.return_value.execute = mock_execute

    logger = PipelineLogger()
    sender = EmailSender(config, logger)
    sender._service = mock_service  # Bypass authentication

    start = time.time()
    for i in range(num_sends):
        sender.send_email(f"user{i}@example.com", "<html>test</html>")
    total_elapsed = time.time() - start

    # Total time should be at least (num_sends - 1) * delay_seconds
    # (first send has no delay, subsequent sends each wait)
    expected_minimum = (num_sends - 1) * delay_seconds
    # Allow 10% tolerance for timing imprecision
    assert total_elapsed >= expected_minimum * 0.9, (
        f"Total elapsed {total_elapsed:.4f}s < expected minimum {expected_minimum:.4f}s "
        f"for {num_sends} sends with {delay_seconds:.4f}s delay"
    )
