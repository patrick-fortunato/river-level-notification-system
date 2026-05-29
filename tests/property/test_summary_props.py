# Feature: river-level-notification-system, Property 8: Run Summary Accuracy
"""Property test for run summary accuracy.

Verifies that for any sequence of recorded successes, failures, and skips,
the summary counters exactly equal the actual counts.

Validates: Requirements 11.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.logger import PipelineLogger


@settings(max_examples=100)
@given(
    successes=st.lists(st.emails(), min_size=0, max_size=20),
    failures=st.lists(
        st.tuples(st.emails(), st.text(min_size=1, max_size=50)),
        min_size=0,
        max_size=20,
    ),
    skips=st.lists(
        st.tuples(st.emails(), st.text(min_size=1, max_size=50)),
        min_size=0,
        max_size=20,
    ),
)
def test_summary_counters_match_actual_counts(
    successes: list[str],
    failures: list[tuple[str, str]],
    skips: list[tuple[str, str]],
):
    """Verify summary counters exactly equal the actual counts of each outcome."""
    logger = PipelineLogger()

    for recipient in successes:
        logger.record_send_success(recipient)

    for recipient, error in failures:
        logger.record_send_failure(recipient, error)

    for recipient, reason in skips:
        logger.record_skip(recipient, reason)

    assert logger.emails_sent == len(successes)
    assert logger.emails_failed == len(failures)
    assert logger.subscribers_skipped == len(skips)
    assert len(logger.skip_reasons) == len(skips)


@settings(max_examples=100)
@given(
    operations=st.lists(
        st.sampled_from(["success", "failure", "skip"]),
        min_size=1,
        max_size=50,
    ),
)
def test_summary_counters_sum_to_total_operations(operations: list[str]):
    """Verify that the sum of all counters equals the total number of operations."""
    logger = PipelineLogger()

    for op in operations:
        if op == "success":
            logger.record_send_success("test@example.com")
        elif op == "failure":
            logger.record_send_failure("test@example.com", "error")
        else:
            logger.record_skip("test@example.com", "reason")

    total = logger.emails_sent + logger.emails_failed + logger.subscribers_skipped
    assert total == len(operations)
