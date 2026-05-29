# Feature: river-level-notification-system, Property 6: Retry With Exponential Backoff
"""Property test for retry mechanism with exponential backoff.

Verifies that for any operation failing N times (N <= max_retries), the mechanism
attempts exactly min(failure_count + 1, max_retries + 1) times with each delay
at least multiplier times the previous.

Validates: Requirements 9.1, 9.2
"""

import time
from unittest.mock import patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.retry import retry_with_backoff


@settings(max_examples=100)
@given(
    failure_count=st.integers(min_value=0, max_value=5),
    max_retries=st.integers(min_value=1, max_value=5),
    initial_backoff=st.floats(min_value=0.001, max_value=0.05),
    multiplier=st.floats(min_value=1.5, max_value=3.0),
)
def test_retry_attempts_correct_count(
    failure_count: int, max_retries: int, initial_backoff: float, multiplier: float
):
    """Verify the retry mechanism attempts exactly the expected number of times."""
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) <= failure_count:
            raise ValueError(f"Failure #{len(attempts)}")
        return "success"

    expected_attempts = min(failure_count + 1, max_retries + 1)

    if failure_count <= max_retries:
        # Should eventually succeed
        with patch("src.retry.time.sleep"):
            result = retry_with_backoff(
                operation=operation,
                max_retries=max_retries,
                initial_backoff=initial_backoff,
                multiplier=multiplier,
                retryable_exceptions=(ValueError,),
            )
        assert result == "success"
        assert len(attempts) == expected_attempts
    else:
        # Should exhaust retries and raise
        try:
            with patch("src.retry.time.sleep"):
                retry_with_backoff(
                    operation=operation,
                    max_retries=max_retries,
                    initial_backoff=initial_backoff,
                    multiplier=multiplier,
                    retryable_exceptions=(ValueError,),
                )
            assert False, "Should have raised"
        except ValueError:
            assert len(attempts) == expected_attempts


@settings(max_examples=100)
@given(
    max_retries=st.integers(min_value=2, max_value=4),
    initial_backoff=st.floats(min_value=0.001, max_value=0.01),
    multiplier=st.floats(min_value=1.5, max_value=3.0),
)
def test_retry_delays_increase_exponentially(
    max_retries: int, initial_backoff: float, multiplier: float
):
    """Verify that each successive delay is at least multiplier times the previous base delay."""
    sleep_calls: list[float] = []

    def fake_sleep(duration):
        sleep_calls.append(duration)

    attempts = []

    def always_fail():
        attempts.append(1)
        raise ValueError("always fails")

    with patch("src.retry.time.sleep", side_effect=fake_sleep):
        with patch("src.retry.random.uniform", return_value=0):  # Remove jitter for predictable delays
            try:
                retry_with_backoff(
                    operation=always_fail,
                    max_retries=max_retries,
                    initial_backoff=initial_backoff,
                    multiplier=multiplier,
                    retryable_exceptions=(ValueError,),
                )
            except ValueError:
                pass

    # Should have max_retries sleep calls (one between each retry)
    assert len(sleep_calls) == max_retries

    # Each delay should be multiplier times the previous
    for i in range(1, len(sleep_calls)):
        assert sleep_calls[i] >= sleep_calls[i - 1] * multiplier * 0.99  # small float tolerance
