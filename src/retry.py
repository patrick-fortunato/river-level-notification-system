"""Retry utility with exponential backoff and jitter."""

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    operation: Callable[[], T],
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    multiplier: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Execute operation with exponential backoff on transient failures.

    The first attempt is immediate. Subsequent attempts wait with exponential
    backoff plus jitter to avoid thundering herd problems.

    Args:
        operation: A callable that takes no arguments and returns a value.
        max_retries: Maximum number of retry attempts after the first failure.
        initial_backoff: Base delay in seconds for the first retry.
        multiplier: Factor by which the delay increases on each subsequent retry.
        retryable_exceptions: Tuple of exception types that trigger a retry.

    Returns:
        The return value of the operation on success.

    Raises:
        The last exception encountered if all retries are exhausted.
    """
    last_exception: Exception | None = None
    total_attempts = max_retries + 1  # first attempt + retries

    for attempt in range(total_attempts):
        try:
            return operation()
        except retryable_exceptions as exc:
            last_exception = exc

            # If this was the last allowed attempt, don't sleep — just raise
            if attempt >= max_retries:
                break

            # Calculate delay with exponential backoff
            delay = initial_backoff * (multiplier ** attempt)

            # Add jitter: random value between 0 and delay to spread out retries
            jitter = random.uniform(0, delay * 0.5)
            time.sleep(delay + jitter)

    # All retries exhausted — raise the last exception
    raise last_exception  # type: ignore[misc]
