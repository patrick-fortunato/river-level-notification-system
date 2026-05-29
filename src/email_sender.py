"""Email sender module using Gmail API with OAuth2 authentication."""

import base64
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import Config
from src.logger import PipelineLogger
from src.retry import retry_with_backoff


class EmailSendError(Exception):
    """Raised when an email send fails permanently."""


class TokenRefreshError(Exception):
    """Raised when OAuth2 token refresh fails."""


class EmailSender:
    """Sends HTML emails via the Gmail API with rate limiting and retry.

    Handles OAuth2 token loading and refresh, constructs MIME messages,
    enforces configurable rate limiting between sends, and retries on
    transient failures including HTTP 429 rate-limit responses.
    """

    def __init__(self, config: Config, logger: PipelineLogger | None = None) -> None:
        self._config = config
        self._logger = logger or PipelineLogger()
        self._service = None
        self._last_send_time: float | None = None

    def authenticate(self) -> None:
        """Load OAuth2 token, refresh if expired, and build Gmail service.

        Raises:
            TokenRefreshError: If the token cannot be loaded or refreshed.
        """
        try:
            creds = Credentials.from_authorized_user_file(
                self._config.gmail_token_file,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
        except Exception as exc:
            raise TokenRefreshError(
                f"Failed to load token from {self._config.gmail_token_file}: {exc}"
            ) from exc

        creds = self._refresh_token_if_needed(creds)
        self._service = build("gmail", "v1", credentials=creds)
        self._logger.log("INFO", "Gmail API service authenticated successfully")

    def _refresh_token_if_needed(self, creds: Credentials) -> Credentials:
        """Refresh expired token and persist updated token to file.

        Args:
            creds: The current OAuth2 credentials.

        Returns:
            Valid (possibly refreshed) credentials.

        Raises:
            TokenRefreshError: If refresh fails (e.g., refresh token revoked).
        """
        if creds.valid:
            return creds

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Persist the refreshed token
                with open(self._config.gmail_token_file, "w") as token_file:
                    token_file.write(creds.to_json())
                self._logger.log("INFO", "OAuth2 token refreshed and persisted")
                return creds
            except Exception as exc:
                raise TokenRefreshError(
                    "Token refresh failed. Manual re-authentication required "
                    f"via Token Generator: {exc}"
                ) from exc

        raise TokenRefreshError(
            "Token is invalid and cannot be refreshed. "
            "Run the Token Generator to re-authenticate."
        )

    def _apply_rate_limit(self) -> None:
        """Enforce configurable delay between consecutive email sends."""
        if self._last_send_time is not None:
            elapsed = time.time() - self._last_send_time
            remaining = self._config.email_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def send_email(self, recipient: str, html_body: str) -> bool:
        """Send an HTML email to the recipient with retry logic.

        Constructs a MIME message, applies rate limiting, and sends via
        the Gmail API. Retries on transient failures (5xx, 429) with
        exponential backoff. Handles HTTP 429 Retry-After headers.

        Args:
            recipient: The recipient's email address.
            html_body: The HTML content of the email body.

        Returns:
            True on successful send, False on permanent failure.
        """
        if self._service is None:
            self._logger.log("ERROR", "Gmail service not authenticated. Call authenticate() first.")
            return False

        # Build the MIME message
        message = MIMEMultipart("alternative")
        message["To"] = recipient
        message["From"] = self._config.sender_email
        message["Subject"] = self._config.email_subject.format(
            state_name=self._config.state_name
        )
        message.attach(MIMEText(html_body, "html"))

        # Encode for Gmail API
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body = {"raw": raw_message}

        # Apply rate limiting before sending
        self._apply_rate_limit()

        def _do_send():
            """Attempt to send the email, raising on transient errors."""
            try:
                self._service.users().messages().send(  # type: ignore[union-attr]
                    userId="me", body=body
                ).execute()
            except HttpError as exc:
                status_code = exc.resp.status if exc.resp else 0
                if status_code == 429:
                    # Handle rate-limit: use Retry-After header if available
                    retry_after = exc.resp.get("retry-after") if exc.resp else None
                    if retry_after:
                        try:
                            time.sleep(float(retry_after))
                        except (ValueError, TypeError):
                            pass
                    raise  # Let retry mechanism handle it
                elif status_code >= 500:
                    raise  # Transient server error, retry
                else:
                    # 4xx (other than 429) is a permanent failure
                    raise EmailSendError(
                        f"Permanent send failure (HTTP {status_code}): {exc}"
                    ) from exc

        try:
            retry_with_backoff(
                operation=_do_send,
                max_retries=self._config.max_retries,
                initial_backoff=self._config.initial_backoff_seconds,
                multiplier=self._config.backoff_multiplier,
                retryable_exceptions=(HttpError,),
            )
            self._last_send_time = time.time()
            return True
        except EmailSendError as exc:
            self._logger.log(
                "ERROR",
                f"Permanent failure sending to {recipient}: {exc}",
            )
            self._last_send_time = time.time()
            return False
        except HttpError as exc:
            self._logger.log(
                "ERROR",
                f"All retries exhausted sending to {recipient}: {exc}",
            )
            self._last_send_time = time.time()
            return False
        except Exception as exc:
            self._logger.log(
                "ERROR",
                f"Unexpected error sending to {recipient}: {exc}",
            )
            self._last_send_time = time.time()
            return False
