"""Property tests for Pipeline run summary counts consistency.

Feature: reach-first-subscriptions, Property 14: Run summary counts consistency

Tests that for any pipeline execution, the run summary satisfies:
    emails_sent + emails_failed + subscribers_skipped == total_subscribers

Validates: Requirements 8.4
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.models import GaugeEntry, ReachSubscriber, ResolvedReach, RunSummary
from src.pipeline import Pipeline


# --- Strategies ---

# Reach IDs: positive integers in a realistic range
reach_id_strategy = st.integers(min_value=1, max_value=99999)

# Gauge numbers: numeric strings like USGS gauge IDs
gauge_number_strategy = st.from_regex(r"[0-9]{5,10}", fullmatch=True)

# Email strategy
email_strategy = st.from_regex(r"[a-z]{3,10}@[a-z]{3,8}\.com", fullmatch=True)

# Subscriber strategy: a ReachSubscriber with 1-5 unique reach IDs
subscriber_strategy = st.builds(
    ReachSubscriber,
    email=email_strategy,
    reach_ids=st.lists(reach_id_strategy, min_size=1, max_size=5, unique=True),
)

# Outcome for each subscriber: resolve success or failure, email send success or failure
# "resolve_fail" = all reaches fail to resolve → subscriber skipped
# "report_none" = report builder returns None → subscriber skipped
# "send_success" = email sent successfully
# "send_fail" = email send fails
subscriber_outcome_strategy = st.sampled_from(
    ["resolve_fail", "report_none", "send_success", "send_fail"]
)


@settings(max_examples=100)
@given(
    subscribers=st.lists(subscriber_strategy, min_size=1, max_size=10),
    outcomes=st.data(),
)
def test_property_14_run_summary_counts_consistency(
    subscribers: list[ReachSubscriber], outcomes
):
    """Feature: reach-first-subscriptions, Property 14: Run summary counts consistency

    For any pipeline execution, the run summary satisfies:
        emails_sent + emails_failed + subscribers_skipped == total_subscribers

    Validates: Requirements 8.4
    """
    # Draw an outcome for each subscriber
    subscriber_outcomes = [
        outcomes.draw(subscriber_outcome_strategy, label=f"outcome_{i}")
        for i in range(len(subscribers))
    ]

    # Build the resolved reaches dict based on outcomes
    # For "resolve_fail" subscribers, none of their reaches will be in the dict
    resolved_reaches: dict[int, ResolvedReach] = {}
    gauge_data: dict[str, GaugeEntry] = {}

    for sub, outcome in zip(subscribers, subscriber_outcomes):
        if outcome == "resolve_fail":
            # Don't add any of this subscriber's reaches to resolved_reaches
            continue
        # For other outcomes, resolve all reaches
        for rid in sub.reach_ids:
            if rid not in resolved_reaches:
                gauge_id = f"{rid:08d}"[:8]
                resolved_reaches[rid] = ResolvedReach(
                    reach_id=rid,
                    reach_name=f"Reach {rid}",
                    gauge_id=gauge_id,
                )
                # Add gauge data for the gauge
                if gauge_id not in gauge_data:
                    gauge_data[gauge_id] = GaugeEntry(
                        gauge_number=gauge_id,
                        gauge_name=f"Gauge {gauge_id}",
                        usgs_page_url=f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_id}/",
                        reading_datetime="2025-01-15T08:00:00.000-08:00",
                        flow_level="500",
                    )

    # Determine report_builder behavior per subscriber
    report_none_emails = {
        sub.email
        for sub, outcome in zip(subscribers, subscriber_outcomes)
        if outcome == "report_none"
    }

    # Determine email send behavior per subscriber
    send_fail_emails = {
        sub.email
        for sub, outcome in zip(subscribers, subscriber_outcomes)
        if outcome == "send_fail"
    }

    config = Config()

    pipeline = Pipeline(config)

    # Mock all external dependencies
    with (
        patch("src.pipeline.ConfigValidator") as mock_validator_cls,
        patch("src.pipeline.SheetReader") as mock_reader_cls,
        patch("src.pipeline.ReachCache") as mock_cache_cls,
        patch("src.pipeline.ReachResolver") as mock_resolver_cls,
        patch("src.pipeline.USGSFetcher") as mock_fetcher_cls,
        patch("src.pipeline.EmailSender") as mock_sender_cls,
        patch("src.pipeline.ReportBuilder") as mock_builder_cls,
        patch("src.pipeline.requests") as mock_requests,
    ):
        # requests.Session() returns a mock session
        mock_requests.Session.return_value = MagicMock()

        # ReachCache returns a mock cache
        mock_cache_cls.return_value = MagicMock()

        # ConfigValidator.validate_all() returns no errors
        mock_validator = MagicMock()
        mock_validator.validate_all.return_value = []
        mock_validator_cls.return_value = mock_validator

        # SheetReader.authenticate() is a no-op, get_subscribers() returns our list
        mock_reader = MagicMock()
        mock_reader.get_subscribers.return_value = subscribers
        mock_reader_cls.return_value = mock_reader

        # ReachResolver.resolve_reaches() returns our pre-built dict
        mock_resolver = MagicMock()
        mock_resolver.resolve_reaches.return_value = resolved_reaches
        mock_resolver_cls.return_value = mock_resolver

        # USGSFetcher.fetch_gauges_by_ids() returns our gauge data
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_gauges_by_ids.return_value = gauge_data
        mock_fetcher_cls.return_value = mock_fetcher

        # EmailSender.authenticate() is a no-op
        mock_sender = MagicMock()

        def send_email_side_effect(recipient, html_body, subject=None):
            if recipient in send_fail_emails:
                return False
            return True

        mock_sender.send_email.side_effect = send_email_side_effect
        mock_sender_cls.return_value = mock_sender

        # ReportBuilder.build_report() returns None for report_none subscribers
        mock_builder = MagicMock()

        def build_report_side_effect(sub, sub_resolved, gd):
            if sub.email in report_none_emails:
                return None
            return "<html>report</html>"

        mock_builder.build_report.side_effect = build_report_side_effect
        mock_builder_cls.return_value = mock_builder

        # Run the pipeline
        summary = pipeline.run()

    # THE PROPERTY: counts must be consistent
    assert summary.emails_sent + summary.emails_failed + summary.subscribers_skipped == summary.total_subscribers, (
        f"Counts inconsistency: "
        f"emails_sent({summary.emails_sent}) + "
        f"emails_failed({summary.emails_failed}) + "
        f"subscribers_skipped({summary.subscribers_skipped}) = "
        f"{summary.emails_sent + summary.emails_failed + summary.subscribers_skipped} "
        f"!= total_subscribers({summary.total_subscribers})"
    )

    # Also verify total_subscribers matches input
    assert summary.total_subscribers == len(subscribers)
