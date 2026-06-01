"""Pipeline orchestrator for the River Level Notification System.

Coordinates the full execution flow: validate configuration, fetch USGS data
per unique state across subscribers, read subscribers, build and send
personalized reports, and output a run summary.
"""

from datetime import datetime, timezone

import requests

from src.__version__ import __version__
from src.config import Config, STATE_NAMES
from src.email_grouper import EmailGrouper
from src.email_sender import EmailSender, TokenRefreshError
from src.logger import PipelineLogger
from src.models import GroupedSubscriber, RunSummary, Subscriber
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

        # Step 2: Read subscribers and group by email
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

        # Group subscriber rows by email address
        # Normalize empty state_code to the global default before grouping
        for sub in subscribers:
            if not sub.state_code:
                sub.state_code = self._config.usgs_state_code

        grouper = EmailGrouper()
        grouped_subscribers = grouper.group_subscribers(subscribers)

        total_subscribers = len(grouped_subscribers)
        self._logger.log("INFO", f"Processing {total_subscribers} subscribers")

        # Step 3: Determine unique states and fetch USGS data for each
        state_gauge_data = self._fetch_gauge_data_for_grouped_subscribers(
            grouped_subscribers
        )
        if state_gauge_data is None:
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

        # Step 4: Build and send reports
        email_sender = self._authenticate_email_sender()
        if email_sender is None:
            # Token auth failed — skip all subscribers
            for gs in grouped_subscribers:
                self._logger.record_skip(gs.email, "Email authentication failed")
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

        for grouped_sub in grouped_subscribers:
            report = report_builder.build_consolidated_report(
                grouped_sub, state_gauge_data
            )

            if report is None:
                self._logger.record_skip(
                    grouped_sub.email,
                    "No matching gauges or no data available",
                )
                continue

            # Determine subject line based on number of states
            subject = self._determine_subject(grouped_sub)

            success = email_sender.send_email(
                grouped_sub.email, report, subject=subject
            )
            if success:
                self._logger.record_send_success(grouped_sub.email)
            else:
                self._logger.record_send_failure(
                    grouped_sub.email, "Send failed after retries"
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

    def _determine_subject(self, grouped_sub: GroupedSubscriber) -> str:
        """Determine the email subject line for a grouped subscriber.

        Uses the state-specific subject format for single-state subscribers,
        and the consolidated subject for multi-state subscribers.

        Args:
            grouped_sub: The grouped subscriber to determine subject for.

        Returns:
            The formatted subject line string.
        """
        if len(grouped_sub.state_preferences) == 1:
            # Single-state: use state-specific subject
            state_code = grouped_sub.state_preferences[0].state_code
            state_name = STATE_NAMES.get(state_code, state_code)
            return self._config.email_subject.format(state_name=state_name)
        else:
            # Multi-state: use consolidated subject
            return self._config.consolidated_email_subject

    def _fetch_gauge_data_for_grouped_subscribers(
        self, grouped_subscribers: list[GroupedSubscriber]
    ) -> dict[str, dict] | None:
        """Fetch USGS gauge data for all unique states across grouped subscribers.

        Collects all unique state codes from grouped subscriber preferences,
        then fetches data once per unique state.

        Args:
            grouped_subscribers: List of grouped subscribers to determine required states.

        Returns:
            A dict mapping state_code -> {gauge_number -> GaugeEntry},
            or None if fetching fails for any state.
        """
        # Determine unique states needed
        unique_states: set[str] = set()
        for gs in grouped_subscribers:
            for pref in gs.state_preferences:
                unique_states.add(pref.state_code)

        self._logger.log(
            "INFO",
            f"Fetching USGS data for {len(unique_states)} state(s): "
            f"{', '.join(sorted(unique_states))}",
        )

        state_gauge_data: dict[str, dict] = {}
        session = requests.Session()

        for state_code in sorted(unique_states):
            self._logger.log("INFO", f"Fetching USGS data for state: {state_code}")
            try:
                # Create a temporary config with this state code for the fetcher
                state_config = Config(
                    usgs_base_url=self._config.usgs_base_url,
                    usgs_format=self._config.usgs_format,
                    usgs_parameter_code=self._config.usgs_parameter_code,
                    usgs_state_code=state_code,
                    max_retries=self._config.max_retries,
                    initial_backoff_seconds=self._config.initial_backoff_seconds,
                    backoff_multiplier=self._config.backoff_multiplier,
                )
                fetcher = USGSFetcher(state_config, session)
                gauge_data = fetcher.fetch_all_state_gauges()
                self._logger.log(
                    "INFO",
                    f"Retrieved {len(gauge_data)} gauge readings for {state_code}",
                )
                state_gauge_data[state_code] = gauge_data
            except USGSFetchError as exc:
                self._logger.log(
                    "ERROR", f"USGS data fetch failed for {state_code}: {exc}"
                )
                self._logger.log(
                    "ERROR", "Halting pipeline due to USGS failure."
                )
                return None

        return state_gauge_data

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
