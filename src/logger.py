"""Structured logging and run summary tracking for the pipeline."""

from datetime import datetime, timezone

from src.__version__ import __version__


class PipelineLogger:
    """Structured logger with counters for pipeline run tracking.

    Provides structured log output with timestamps and severity levels,
    and tracks email delivery outcomes for the run summary.
    """

    def __init__(self) -> None:
        self.emails_sent: int = 0
        self.emails_failed: int = 0
        self.subscribers_skipped: int = 0
        self.skip_reasons: list[str] = []

    def log(self, level: str, message: str) -> None:
        """Output a structured log entry with timestamp and severity.

        Args:
            level: Severity level (e.g., INFO, WARNING, ERROR).
            message: The log message.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")
        print(f"[{timestamp}] [{level.upper()}] {message}")

    def record_send_success(self, recipient: str) -> None:
        """Record a successful email send.

        Args:
            recipient: The email address that received the message.
        """
        self.emails_sent += 1
        self.log("INFO", f"Email sent successfully to {recipient}")

    def record_send_failure(self, recipient: str, error: str) -> None:
        """Record a failed email send.

        Args:
            recipient: The email address that failed.
            error: Description of the error.
        """
        self.emails_failed += 1
        self.log("ERROR", f"Email send failed for {recipient}: {error}")

    def record_skip(self, recipient: str, reason: str) -> None:
        """Record a skipped subscriber.

        Args:
            recipient: The email address that was skipped.
            reason: Why the subscriber was skipped.
        """
        self.subscribers_skipped += 1
        self.skip_reasons.append(f"{recipient}: {reason}")
        self.log("INFO", f"Skipped {recipient}: {reason}")

    def output_summary(self, total_subscribers: int) -> None:
        """Output the run summary with all counters.

        Args:
            total_subscribers: Total number of subscribers processed.
        """
        self.log("INFO", "--- Run Summary ---")
        self.log("INFO", f"Version: {__version__}")
        self.log("INFO", f"Total subscribers: {total_subscribers}")
        self.log("INFO", f"Emails sent: {self.emails_sent}")
        self.log("INFO", f"Emails failed: {self.emails_failed}")
        self.log("INFO", f"Subscribers skipped: {self.subscribers_skipped}")
        if self.skip_reasons:
            self.log("INFO", "Skip reasons:")
            for reason in self.skip_reasons:
                self.log("INFO", f"  - {reason}")
        self.log("INFO", "--- End Summary ---")
