# Feature: hardcoded-state-in-email-subject, Property 1: Bug Condition
"""Property test for bug condition: hardcoded state in email subject.

For any subscriber with a non-default state_code (different from the global "OR"),
the email subject SHOULD contain the subscriber's state name, not the global default.

On UNFIXED code, this test is EXPECTED TO FAIL because send_email() always uses
the global Config.state_name ("Oregon") regardless of the subscriber's state.

**Validates: Requirements 1.1, 1.2**
"""

from unittest.mock import MagicMock, patch
import base64
from email import message_from_bytes

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config, STATE_NAMES
from src.email_sender import EmailSender
from src.logger import PipelineLogger


# All state codes excluding the global default "OR"
NON_DEFAULT_STATE_CODES = [code for code in STATE_NAMES.keys() if code != "OR"]


@settings(max_examples=50)
@given(
    state_code=st.sampled_from(NON_DEFAULT_STATE_CODES),
)
def test_email_subject_reflects_subscriber_state(state_code: str):
    """For subscribers with a non-default state_code, the email subject must
    contain the subscriber's state name (not the global default 'Oregon').

    Bug condition: effective_state != globalConfig.usgs_state_code
    Expected behavior: subject contains STATE_NAMES[subscriber.state_code]
    """
    config = Config(
        gmail_token_file="fake_token.json",
        sender_email="sender@example.com",
        email_delay_seconds=0,
        usgs_state_code="OR",  # Global default
    )

    logger = PipelineLogger()
    email_sender = EmailSender(config, logger)

    # Mock the Gmail API service to capture the sent message
    mock_service = MagicMock()
    mock_send = MagicMock()
    mock_send.execute.return_value = {"id": "msg123"}
    mock_service.users.return_value.messages.return_value.send.return_value = mock_send
    email_sender._service = mock_service

    # Call send_email with state_code parameter (as the pipeline now does)
    recipient = f"subscriber@example.com"
    html_body = "<html><body>River levels report</body></html>"
    result = email_sender.send_email(recipient, html_body, state_code=state_code)

    assert result is True, "send_email should return True on success"

    # Extract the raw message that was sent to the Gmail API
    call_args = mock_service.users.return_value.messages.return_value.send.call_args
    raw_message_b64 = call_args[1]["body"]["raw"] if "body" in call_args[1] else call_args[0][0]["raw"]

    # Decode the MIME message to inspect the subject
    raw_bytes = base64.urlsafe_b64decode(raw_message_b64)
    mime_message = message_from_bytes(raw_bytes)
    subject = mime_message["Subject"]

    # The expected state name for this subscriber
    expected_state_name = STATE_NAMES[state_code]

    # Assert: the subject should contain the subscriber's state name
    # On UNFIXED code, this will FAIL because subject always contains "Oregon"
    assert expected_state_name in subject, (
        f"Bug confirmed: subscriber with state_code='{state_code}' should get "
        f"subject containing '{expected_state_name}', but got subject: '{subject}'. "
        f"The subject always uses the global default 'Oregon' instead of the "
        f"subscriber's actual state."
    )
