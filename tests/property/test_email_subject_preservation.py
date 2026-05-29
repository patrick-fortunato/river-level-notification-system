# Feature: hardcoded-state-in-email-subject, Property 2: Preservation
"""Property test for preservation: default state subscribers unchanged.

For any subscriber with empty state_code or state_code matching the global default,
the email subject must continue to use the global default state name.

On UNFIXED code, this test PASSES because send_email() always uses the global
Config.state_name — which is exactly the behavior we want to preserve for
default-state subscribers.

**Validates: Requirements 3.1, 3.2, 3.3**
"""

import base64
from email import message_from_bytes
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config, STATE_NAMES
from src.email_sender import EmailSender
from src.logger import PipelineLogger


# All valid state codes that can serve as the global default
ALL_STATE_CODES = list(STATE_NAMES.keys())


@settings(max_examples=50)
@given(
    global_state_code=st.sampled_from(ALL_STATE_CODES),
)
def test_default_state_subscriber_gets_global_state_in_subject(global_state_code: str):
    """For any valid global state code, when send_email() is called without a
    state override (simulating a subscriber with empty state_code or state_code
    matching the global default), the subject contains the global state name.

    This confirms the baseline behavior to preserve: the email subject uses
    STATE_NAMES[global_state_code] formatted via Config.email_subject.

    Preservation: subscribers with empty state_code or state_code matching
    global default get subject with global default state name.
    """
    config = Config(
        gmail_token_file="fake_token.json",
        sender_email="sender@example.com",
        email_delay_seconds=0,
        usgs_state_code=global_state_code,
    )

    logger = PipelineLogger()
    email_sender = EmailSender(config, logger)

    # Mock the Gmail API service to capture the sent message
    mock_service = MagicMock()
    mock_send = MagicMock()
    mock_send.execute.return_value = {"id": "msg123"}
    mock_service.users.return_value.messages.return_value.send.return_value = mock_send
    email_sender._service = mock_service

    # Call send_email on UNFIXED code (no state_code parameter exists yet)
    # This simulates a subscriber with empty state_code or matching global default
    recipient = "user@example.com"
    html_body = "<html><body>River levels report</body></html>"
    result = email_sender.send_email(recipient, html_body)

    assert result is True, "send_email should return True on success"

    # Extract the raw message that was sent to the Gmail API
    call_args = mock_service.users.return_value.messages.return_value.send.call_args
    raw_message_b64 = call_args[1]["body"]["raw"] if "body" in call_args[1] else call_args[0][0]["raw"]

    # Decode the MIME message to inspect the subject
    raw_bytes = base64.urlsafe_b64decode(raw_message_b64)
    mime_message = message_from_bytes(raw_bytes)
    subject = mime_message["Subject"]

    # The expected subject for a default-state subscriber
    expected_state_name = STATE_NAMES[global_state_code]
    expected_subject = config.email_subject.format(state_name=expected_state_name)

    # Assert: the subject must equal the expected formatted subject
    # On UNFIXED code, this PASSES because send_email() always uses
    # self._config.state_name which resolves from usgs_state_code
    assert subject == expected_subject, (
        f"Preservation violated: with global state_code='{global_state_code}', "
        f"expected subject '{expected_subject}', but got '{subject}'. "
        f"Default-state subscribers must continue to get the global state name."
    )
