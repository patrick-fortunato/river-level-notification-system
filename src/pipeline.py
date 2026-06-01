"""Pipeline orchestrator for the River Level Notification System.

Coordinates the full execution flow: validate configuration, read subscribers,
resolve reaches via AW API, fetch targeted USGS gauge data, build and send
personalized reach-first reports, and output a run summary.
"""

from datetime import datetime, timezone

import requests

from src.__version__ import __version__
from src.config import Config
from src.email_sender import EmailSender, TokenRefreshError
from src.logger import PipelineLogger
from src.models import ReachSubscriber, ResolvedReach, RunSummary
from src.reach_cache import ReachCache
from src.reach_resolver import ReachResolver
from src.report_builder import ReportBuilder
from src.sheet_reader import SheetReader
from src.usgs_fetcher import USGSFetcher
from src.validator import ConfigValidator


class Pipeline:
    """Orchestrates the full river level notification pipeline.

    Executes the following steps in order:
    1. Validate configuration (halt on failure)
    2. Read subscribers from Google Sheet (halt on failure)
    3. Resolve reaches via AW API (with caching)
    4. Fetch USGS gauge data for resolved gauges
    5. Build and send personalized reports (continue on individual failures)
    6. Output run summary
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = PipelineLogger()

    def run(self) -> RunSummary:
        """Execute the full pipeline.

        Flow: validate → read subscribers → resolve reaches →
        fetch USGS → build reports → send emails → summary.

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

        # Step 2: Read subscribers from Google Sheet
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

        if total_subscribers == 0:
            self._logger.log("WARNING", "No subscribers found in spreadsheet")
            end_time = datetime.now(timezone.utc)
            self._logger.output_summary(0)
            return RunSummary(
                total_subscribers=0,
                emails_sent=0,
                emails_failed=0,
                subscribers_skipped=0,
                skip_reasons=[],
                start_time=start_time,
                end_time=end_time,
            )

        self._logger.log("INFO", f"Processing {total_subscribers} subscribers")

        # Step 3: Collect all unique reach IDs and resolve via AW API
        all_reach_ids: list[int] = []
        seen_reach_ids: set[int] = set()
        for sub in subscribers:
            for rid in sub.reach_ids:
                if rid not in seen_reach_ids:
                    seen_reach_ids.add(rid)
                    all_reach_ids.append(rid)

        self._logger.log(
            "INFO", f"Resolving {len(all_reach_ids)} unique reach IDs"
        )

        session = requests.Session()
        cache = ReachCache(self._config)
        resolver = ReachResolver(self._config, session, cache)
        resolved_reaches = resolver.resolve_reaches(all_reach_ids)

        self._logger.log(
            "INFO",
            f"Resolved {len(resolved_reaches)} of {len(all_reach_ids)} reaches",
        )

        # Step 4: Collect unique gauge IDs from resolved reaches and fetch USGS data
        gauge_ids: list[str] = []
        seen_gauge_ids: set[str] = set()
        for resolved in resolved_reaches.values():
            if resolved.gauge_id is not None and resolved.gauge_id not in seen_gauge_ids:
                seen_gauge_ids.add(resolved.gauge_id)
                gauge_ids.append(resolved.gauge_id)

        self._logger.log(
            "INFO", f"Fetching USGS data for {len(gauge_ids)} unique gauges"
        )

        fetcher = USGSFetcher(self._config, session)
        gauge_data = fetcher.fetch_gauges_by_ids(gauge_ids)

        self._logger.log(
            "INFO", f"Retrieved {len(gauge_data)} gauge readings"
        )

        # Step 5: Authenticate email sender
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

        # Step 6: Build and send reports per subscriber
        report_builder = ReportBuilder()

        for sub in subscribers:
            # Check if any of this subscriber's reaches were resolved
            sub_resolved = {
                rid: resolved_reaches[rid]
                for rid in sub.reach_ids
                if rid in resolved_reaches
            }

            if not sub_resolved:
                self._logger.record_skip(
                    sub.email, "All reach resolutions failed"
                )
                continue

            # Build report
            report = report_builder.build_report(sub, sub_resolved, gauge_data)

            if report is None:
                self._logger.record_skip(
                    sub.email, "No matching gauges or no data available"
                )
                continue

            # Send email with subject from config
            success = email_sender.send_email(
                sub.email, report, subject=self._config.email_subject
            )
            if success:
                self._logger.record_send_success(sub.email)
            else:
                self._logger.record_send_failure(
                    sub.email, "Send failed after retries"
                )

        # Step 7: Output summary
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

    def _read_subscribers(self) -> list[ReachSubscriber] | None:
        """Read subscribers from the Google Sheet.

        Returns:
            A list of ReachSubscriber objects, or None on failure.
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
