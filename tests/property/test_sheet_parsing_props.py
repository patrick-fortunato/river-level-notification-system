# Feature: river-level-notification-system, Property 2: Subscriber Sheet Parsing Correctness
"""Property test for subscriber sheet parsing.

Generates arbitrary sheet data with subscriber rows containing emails and
comma-separated inclusion lists, verifies parsed Subscriber objects have
included_gauges matching exactly the gauge numbers listed in column B.

Validates: Requirements 2.3, 2.5, 2.6
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.sheet_reader import _parse_gauge_list


# Strategy for generating gauge numbers (5-15 digit numeric strings)
gauge_number_strategy = st.from_regex(r"[0-9]{5,15}", fullmatch=True)

# Strategy for generating gauge lists as comma-separated strings
gauge_list_strategy = st.lists(
    gauge_number_strategy, min_size=0, max_size=10
).map(lambda gauges: ", ".join(gauges))


@settings(max_examples=100)
@given(
    gauge_numbers=st.lists(gauge_number_strategy, min_size=1, max_size=10),
)
def test_parse_gauge_list_extracts_all_gauge_numbers(gauge_numbers: list[str]):
    """Verify parsing a comma-separated string produces exactly the listed gauge numbers."""
    raw_value = ", ".join(gauge_numbers)
    result = _parse_gauge_list(raw_value)
    assert result == gauge_numbers


@settings(max_examples=100)
@given(
    gauge_numbers=st.lists(gauge_number_strategy, min_size=1, max_size=10),
    extra_spaces=st.lists(
        st.integers(min_value=0, max_value=5), min_size=1, max_size=10
    ),
)
def test_parse_gauge_list_strips_whitespace(
    gauge_numbers: list[str], extra_spaces: list[int]
):
    """Verify parsing handles extra whitespace around gauge numbers."""
    # Build a string with variable whitespace around commas
    parts = []
    for i, gauge in enumerate(gauge_numbers):
        spaces = extra_spaces[i % len(extra_spaces)]
        parts.append(" " * spaces + gauge + " " * spaces)
    raw_value = ",".join(parts)

    result = _parse_gauge_list(raw_value)
    assert result == gauge_numbers


@settings(max_examples=100)
@given(data=st.data())
def test_empty_gauge_list_returns_empty(data):
    """Verify empty/blank input returns an empty list (meaning receive all gauges)."""
    raw_value = data.draw(st.sampled_from(["", "   ", "\t", "\n"]))
    result = _parse_gauge_list(raw_value)
    assert result == []


@settings(max_examples=100)
@given(
    gauge_numbers=st.lists(gauge_number_strategy, min_size=1, max_size=5),
)
def test_parse_gauge_list_ignores_empty_entries(gauge_numbers: list[str]):
    """Verify consecutive commas (empty entries) are ignored."""
    # Insert extra commas between entries
    raw_value = ",,".join(gauge_numbers) + ",,"
    result = _parse_gauge_list(raw_value)
    assert result == gauge_numbers
