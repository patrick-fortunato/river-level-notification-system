"""Pipeline orchestrator for the River Level Notification System.

Coordinates the full execution flow: validate configuration, fetch USGS data,
read subscribers, build and send personalized reports, and output a run summary.
"""

from datetime import datetime, timezone

import requests

from src.__version__ import __version__
from src.config import Config
from src.email_sender import EmailSender, TokenRefreshError
from src.logger import PipelineLogger
from src.models import RunSummary
from src.report_builder import ReportBuilder
from src.sheet_reader import SheetReader
from src.usgs_fetcher import USGSFetcher, USGSFetchError
from src.validator import ConfigValidator


class Pipeline:
    """Orchestrates the full river level notification pipeline.

    Executes the following steps in order:
    1. Validate configuration (halt on failure)
    2. Fetch all USGS gauge data for the configured state (halt on failure)
    3. Read subscribers from Google Sheet
    4. Build and send personalized reports (continue on individual failures)
    5. Output run summary
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = PipelineLogger()

    def run(self) -> RunSummary:
        """Execute the full pipeline.

        Returns:
            A RunSummary with outcome counts and timing information.
        """
        start_time = datetime.now(timezone.utc)
        self._logger.log("INFO", f"Pipeline run started (v{__version__})")

        # Step 1: Validate configuration
        if not self._validate():
            end_time = datetime.now(timezone.utc)
            self._logger.output_summary(0)
            return RunSummary(
                total_subscribers=0,
                emails_sent=self._logger.emails_sent,
                emails_failed=self._logger.emails_failed,
                subscribers_skipped=self._logger.subscribers_skipped,
                skip_reasons=list(self._logger.skip_reasons),
                start_time=start_time,
                end_time=end_time,
            )

        # Step 2: Fetch USGS data
        gauge_data = self._fetch_gauge_data()
        if gauge_data is None:
            end_time = datetime.now(timezone.utc)
            self._logger.output_summary(0)
            return RunSummary(
                total_subscribers=0,
                emails_sent=self._logger.emails_sent,
                emails_failed=self._logger.emails_failed,
                subscribers_skipped=self._logger.subscribers_skipped,
                skip_reasons=list(self._logger.skip_reasons),
                start_time=start_time,
                end_time=end_time,
            )

        # Step 3: Read subscribers
        subscribers = self._read_subscribers()
        if subscribers is None:
            end_time = datetime.now(timezone.utc)
            self._logger.output_summary(0)
            return RunSummary(
                total_subscribers=0,
                emails_sent=self._logger.emails_sent,
                emails_failed=self._logger.emails_failed,
                subscribers_skipped=self._logger.subscribers_skipped,
                skip_reasons=list(self._logger.skip_reasons),
                start_time=start_time,
                end_time=end_time,
            )

        total_subscribers = len(subscribers)
        self._logger.log("INFO", f"Processing {total_subscribers} subscribers")

        # Step 4: Build and send reports
        email_sender = self._authenticate_email_sender()
        if email_sender is None:
            # Token auth failed — skip all subscribers
            for sub in subscribers:
                self._logger.record_skip(sub.email, "Email authentication failed")
            end_time = datetime.now(timezone.utc)
            self._logger.output_summary(total_subscribers)
            return RunSummary(
                total_subscribers=total_subscribers,
                emails_sent=self._logger.emails_sent,
                emails_failed=self._logger.emails_failed,
                subscribers_skipped=self._logger.subscribers_skipped,
                skip_reasons=list(self._logger.skip_reasons),
                start_time=start_time,
                end_time=end_time,
            )

        report_builder = ReportBuilder()

        for subscriber in subscribers:
            report = report_builder.build_report(subscriber, gauge_data)

            if report is None:
                self._logger.record_skip(
                    subscriber.email,
                    "No matching gauges or no data available",
                )
                continue

            success = email_sender.send_email(subscriber.email, report)
            if success:
                self._logger.record_send_success(subscriber.email)
            else:
                self._logger.record_send_failure(
                    subscriber.email, "Send failed after retries"
                )

        # Step 5: Output summary
        end_time = datetime.now(timezone.utc)
        self._logger.log("INFO", "Pipeline run completed")
        self._logger.output_summary(total_subscribers)

        return RunSummary(
            total_subscribers=total_subscribers,
            emails_sent=self._logger.emails_sent,
            emails_failed=self._logger.emails_failed,
            subscribers_skipped=self._logger.subscribers_skipped,
            skip_reasons=list(self._logger.skip_reasons),
            start_time=start_time,
            end_time=end_time,
        )

    def _validate(self) -> bool:
        """Validate configuration at startup.

        Returns:
            True if all checks pass, False otherwise.
        """
        self._logger.log("INFO", "Validating configuration...")
        validator = ConfigValidator(self._config)
        errors = validator.validate_all()

        if errors:
            for error in errors:
                self._logger.log("ERROR", f"Validation failed: {error}")
            self._logger.log(
                "ERROR",
                "Configuration validation failed. Halting pipeline.",
            )
            return False

        self._logger.log("INFO", "Configuration validation passed")
        return True

    def _fetch_gauge_data(self) -> dict | None:
        """Fetch all USGS gauge data for the configured state.

        Returns:
            A dict mapping gauge_number -> GaugeEntry, or None on failure.
        """
        self._logger.log(
            "INFO",
            f"Fetching USGS data for state: {self._config.usgs_state_code} "
            f"({self._config.state_name})",
        )

        try:
            session = requests.Session()
            fetcher = USGSFetcher(self._config, session)
            gauge_data = fetcher.fetch_all_state_gauges()
            self._logger.log(
                "INFO", f"Retrieved {len(gauge_data)} gauge readings"
            )
            return gauge_data
        except USGSFetchError as exc:
            self._logger.log("ERROR", f"USGS data fetch failed: {exc}")
            self._logger.log("ERROR", "Halting pipeline due to USGS failure.")
            return None

    def _read_subscribers(self) -> list | None:
        """Read subscribers from the Google Sheet.

        Returns:
            A list of Subscriber objects, or None on failure.
        """
        self._logger.log("INFO", "Reading subscribers from Google Sheet...")

        try:
            reader = SheetReader(self._config)
            reader.authenticate()
            subscribers = reader.get_subscribers()
            self._logger.log(
                "INFO", f"Found {len(subscribers)} subscribers"
            )
            return subscribers
        except Exception as exc:
            self._logger.log(
                "ERROR", f"Failed to read subscribers: {exc}"
            )
            self._logger.log("ERROR", "Halting pipeline due to sheet read failure.")
            return None

    def _authenticate_email_sender(self) -> EmailSender | None:
        """Authenticate the email sender with Gmail API.

        Returns:
            An authenticated EmailSender instance, or None on failure.
        """
        self._logger.log("INFO", "Authenticating with Gmail API...")

        try:
            sender = EmailSender(self._config, self._logger)
            sender.authenticate()
            return sender
        except TokenRefreshError as exc:
            self._logger.log(
                "ERROR",
                f"Gmail authentication failed: {exc}",
            )
            return None
        except Exception as exc:
            self._logger.log(
                "ERROR",
                f"Unexpected error during Gmail authentication: {exc}",
            )
            return None
