# Feature: reach-first-subscriptions, Property 11: Cache serialization round-trip
"""Property tests for ReachCache serialization round-trip.

Verifies that for any valid ResolvedReach object, writing it to the cache
via put_reach and reading it back via get_reach produces an equivalent
ResolvedReach with the same reach_id, reach_name, and gauge_id.

**Validates: Requirements 6.1**
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.models import ResolvedReach
from src.reach_cache import ReachCache


# Strategy for generating reach IDs (positive integers)
reach_ids = st.integers(min_value=1, max_value=1_000_000)

# Strategy for generating reach names (non-empty strings)
reach_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip() != "")

# Strategy for generating USGS gauge IDs (numeric strings or None)
gauge_ids = st.one_of(
    st.none(),
    st.text(
        alphabet="0123456789",
        min_size=1,
        max_size=15,
    ),
)

# Strategy for generating a ResolvedReach object
resolved_reach_strategy = st.builds(
    ResolvedReach,
    reach_id=reach_ids,
    reach_name=reach_names,
    gauge_id=gauge_ids,
)


@settings(max_examples=100)
@given(resolved=resolved_reach_strategy)
def test_cache_serialization_round_trip(resolved: ResolvedReach):
    """For any valid ResolvedReach object, writing it to the cache via put_reach
    and reading it back via get_reach SHALL produce an equivalent ResolvedReach
    with the same reach_id, reach_name, and gauge_id.

    Feature: reach-first-subscriptions, Property 11: Cache serialization round-trip

    **Validates: Requirements 6.1**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "test_cache.json"

        # Create a Config with a temp cache file and long TTL so entries don't expire
        config = Config(
            aw_reach_cache_file=str(cache_file),
            aw_cache_ttl_seconds=604800,  # 7 days
        )
        cache = ReachCache(config)

        # Write the resolved reach to cache
        cache.put_reach(resolved.reach_id, resolved)

        # Read it back
        result = cache.get_reach(resolved.reach_id)

        # The round-trip must produce an equivalent object
        assert result is not None, (
            f"get_reach returned None for reach_id={resolved.reach_id}"
        )
        assert result.reach_id == resolved.reach_id, (
            f"reach_id mismatch: expected {resolved.reach_id}, got {result.reach_id}"
        )
        assert result.reach_name == resolved.reach_name, (
            f"reach_name mismatch: expected '{resolved.reach_name}', "
            f"got '{result.reach_name}'"
        )
        assert result.gauge_id == resolved.gauge_id, (
            f"gauge_id mismatch: expected {resolved.gauge_id}, got {result.gauge_id}"
        )


# --- Property 2: Cache round-trip preserves state field ---

# Strategy for state values: valid 2-letter codes or None
state_strategy = st.one_of(
    st.none(),
    st.sampled_from(["OR", "WA", "CA", "CO", "ID", "MT", "UT", "AK"]),
    st.from_regex(r"[A-Z]{2}", fullmatch=True),
)

# Strategy for generating a ResolvedReach with state
resolved_reach_with_state_strategy = st.builds(
    ResolvedReach,
    reach_id=reach_ids,
    reach_name=reach_names,
    gauge_id=gauge_ids,
    state=state_strategy,
)


@settings(max_examples=100)
@given(resolved=resolved_reach_with_state_strategy)
def test_property_2_cache_round_trip_preserves_state(resolved: ResolvedReach):
    """Feature: state-grouped-email, Property 2: Cache round-trip preserves state

    For any valid ResolvedReach with any state value (including None), writing
    it to the cache via put_reach and reading it back via get_reach SHALL
    produce a ResolvedReach with the same state value.

    **Validates: Requirements 3.1, 3.2**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "test_cache.json"

        config = Config(
            aw_reach_cache_file=str(cache_file),
            aw_cache_ttl_seconds=604800,
        )
        cache = ReachCache(config)

        # Write the resolved reach to cache
        cache.put_reach(resolved.reach_id, resolved)

        # Read it back
        result = cache.get_reach(resolved.reach_id)

        # The round-trip must preserve the state field
        assert result is not None, (
            f"get_reach returned None for reach_id={resolved.reach_id}"
        )
        assert result.state == resolved.state, (
            f"state mismatch: expected {resolved.state!r}, got {result.state!r}"
        )
        # Also verify other fields are preserved
        assert result.reach_id == resolved.reach_id
        assert result.reach_name == resolved.reach_name
        assert result.gauge_id == resolved.gauge_id
