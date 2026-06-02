"""Property tests for runnability classification logic.

Feature: runnability-indicator

Tests the classify_runnability function for correct classification of flow
readings against runnable range boundaries.

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import RunnabilityStatus, classify_runnability


# --- Property 2: Classification correctness for flow vs range ---


@settings(max_examples=100)
@given(
    flow=st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False),
    rmin=st.floats(min_value=0, max_value=50000, allow_nan=False, allow_infinity=False),
    range_width=st.floats(min_value=0.1, max_value=50000, allow_nan=False, allow_infinity=False),
)
def test_property_2_classification_correctness(flow: float, rmin: float, range_width: float):
    """Feature: runnability-indicator, Property 2: Classification correctness

    For any flow reading and valid rmin/rmax range where rmin <= rmax, the
    classify_runnability function SHALL return RUNNABLE when rmin <= flow <= rmax,
    TOO_LOW when flow < rmin, and TOO_HIGH when flow > rmax.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    rmax = rmin + range_width  # ensures rmin <= rmax

    result = classify_runnability(flow, rmin, rmax)

    if flow < rmin:
        assert result == RunnabilityStatus.TOO_LOW, (
            f"Expected TOO_LOW for flow={flow} < rmin={rmin}, got {result}"
        )
    elif flow > rmax:
        assert result == RunnabilityStatus.TOO_HIGH, (
            f"Expected TOO_HIGH for flow={flow} > rmax={rmax}, got {result}"
        )
    else:
        assert result == RunnabilityStatus.RUNNABLE, (
            f"Expected RUNNABLE for rmin={rmin} <= flow={flow} <= rmax={rmax}, got {result}"
        )


# --- Property 3: Missing data produces Unknown classification ---


@settings(max_examples=100)
@given(
    flow=st.one_of(
        st.none(),
        st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False),
    ),
    rmin=st.one_of(
        st.none(),
        st.floats(min_value=0, max_value=50000, allow_nan=False, allow_infinity=False),
    ),
    rmax=st.one_of(
        st.none(),
        st.floats(min_value=0, max_value=100000, allow_nan=False, allow_infinity=False),
    ),
)
def test_property_3_missing_data_produces_unknown(
    flow: float | None, rmin: float | None, rmax: float | None
):
    """Feature: runnability-indicator, Property 3: Missing data produces Unknown

    For any combination of inputs where at least one of (flow, rmin, rmax) is None,
    the classify_runnability function SHALL return UNKNOWN.

    **Validates: Requirements 3.4**
    """
    # Only test cases where at least one input is None
    if flow is not None and rmin is not None and rmax is not None:
        # Skip cases where all are present - those are tested by Property 2
        return

    result = classify_runnability(flow, rmin, rmax)

    assert result == RunnabilityStatus.UNKNOWN, (
        f"Expected UNKNOWN when at least one input is None "
        f"(flow={flow!r}, rmin={rmin!r}, rmax={rmax!r}), got {result}"
    )
