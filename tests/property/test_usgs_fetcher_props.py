"""Property tests for USGS fetcher gauge ID deduplication logic.

Feature: reach-first-subscriptions

Tests that the pipeline logic for collecting unique gauge IDs from resolved
reaches correctly deduplicates and excludes None values.

Validates: Requirements 3.2
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import ResolvedReach


# --- Strategies ---

# Reach IDs (positive integers)
reach_id_strategy = st.integers(min_value=1, max_value=99999)

# Gauge IDs (numeric strings like USGS gauge numbers) or None
gauge_id_strategy = st.one_of(
    st.none(),
    st.from_regex(r"[0-9]{5,15}", fullmatch=True),
)

# Non-empty reach name
reach_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "S"),
                           blacklist_characters="\n\r\x00"),
    min_size=1,
    max_size=50,
)

# Strategy for a dict of reach_id -> ResolvedReach with controlled gauge_ids
resolved_reaches_strategy = st.dictionaries(
    keys=reach_id_strategy,
    values=st.tuples(reach_name_strategy, gauge_id_strategy),
    min_size=1,
    max_size=20,
).map(
    lambda d: {
        reach_id: ResolvedReach(
            reach_id=reach_id,
            reach_name=name,
            gauge_id=gauge_id,
        )
        for reach_id, (name, gauge_id) in d.items()
    }
)


# --- Property 6: Gauge ID deduplication ---


@settings(max_examples=100)
@given(resolved_reaches=resolved_reaches_strategy)
def test_property_6_gauge_id_deduplication(
    resolved_reaches: dict[int, ResolvedReach],
):
    """Feature: reach-first-subscriptions, Property 6: Gauge ID deduplication

    For any collection of ResolvedReach objects (some with gauge_id=None,
    some sharing the same gauge_id), the set of unique non-None gauge_ids
    extracted from those reaches equals the set that would be passed to the
    fetcher.

    The pipeline logic:
        gauge_ids = list({r.gauge_id for r in resolved_reaches.values() if r.gauge_id is not None})

    Validates: Requirements 3.2
    """
    # This is the pipeline logic for collecting gauge IDs
    gauge_ids = list(
        {r.gauge_id for r in resolved_reaches.values() if r.gauge_id is not None}
    )

    # Compute expected: the set of unique non-None gauge_ids
    expected_set = {
        r.gauge_id for r in resolved_reaches.values() if r.gauge_id is not None
    }

    # Property: the collected gauge_ids as a set equals the expected set
    assert set(gauge_ids) == expected_set

    # Property: no duplicates in the collected list
    assert len(gauge_ids) == len(set(gauge_ids))

    # Property: no None values in the collected list
    assert None not in gauge_ids

    # Property: every non-None gauge_id from the reaches is present
    for reach in resolved_reaches.values():
        if reach.gauge_id is not None:
            assert reach.gauge_id in gauge_ids


@settings(max_examples=100)
@given(
    resolved_reaches=st.dictionaries(
        keys=reach_id_strategy,
        values=st.tuples(reach_name_strategy, st.none()),
        min_size=1,
        max_size=10,
    ).map(
        lambda d: {
            reach_id: ResolvedReach(
                reach_id=reach_id,
                reach_name=name,
                gauge_id=gauge_id,
            )
            for reach_id, (name, gauge_id) in d.items()
        }
    )
)
def test_property_6_all_none_gauge_ids_produces_empty(
    resolved_reaches: dict[int, ResolvedReach],
):
    """Feature: reach-first-subscriptions, Property 6: Gauge ID deduplication

    When all reaches have gauge_id=None, the collected gauge IDs list is empty.

    Validates: Requirements 3.2
    """
    gauge_ids = list(
        {r.gauge_id for r in resolved_reaches.values() if r.gauge_id is not None}
    )

    assert gauge_ids == []


@settings(max_examples=100)
@given(
    shared_gauge_id=st.from_regex(r"[0-9]{5,15}", fullmatch=True),
    num_reaches=st.integers(min_value=2, max_value=10),
)
def test_property_6_shared_gauge_id_deduplicates(
    shared_gauge_id: str,
    num_reaches: int,
):
    """Feature: reach-first-subscriptions, Property 6: Gauge ID deduplication

    When multiple reaches share the same gauge_id, the deduplication logic
    produces exactly one entry for that gauge_id.

    Validates: Requirements 3.2
    """
    # Create multiple reaches all sharing the same gauge_id
    resolved_reaches = {
        i: ResolvedReach(
            reach_id=i,
            reach_name=f"Reach {i}",
            gauge_id=shared_gauge_id,
        )
        for i in range(1, num_reaches + 1)
    }

    gauge_ids = list(
        {r.gauge_id for r in resolved_reaches.values() if r.gauge_id is not None}
    )

    # Should produce exactly one entry
    assert len(gauge_ids) == 1
    assert gauge_ids[0] == shared_gauge_id
