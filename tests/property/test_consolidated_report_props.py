# Feature: email-consolidation, Property 3: One state section per unique state
"""Property tests for the ReportBuilder.build_consolidated_report() method.

Property 3: For any grouped subscriber with N unique states that have
available gauge data, the consolidated report SHALL contain exactly N
state section headings.

Validates: Requirements 2.1, 4.1
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import STATE_NAMES
from src.models import GaugeEntry, GroupedSubscriber, StatePreference
from src.report_builder import ReportBuilder


# --- Strategies ---

# Use a subset of real state codes for generating test data
VALID_STATE_CODES = list(STATE_NAMES.keys())

state_code_strategy = st.sampled_from(VALID_STATE_CODES)

# Strategy for generating gauge numbers (USGS-style numeric strings)
gauge_number_strategy = st.from_regex(r"[0-9]{5,10}", fullmatch=True)

# Strategy for generating a GaugeEntry
gauge_entry_strategy = st.builds(
    GaugeEntry,
    gauge_number=gauge_number_strategy,
    gauge_name=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
    usgs_page_url=st.just("https://waterservices.usgs.gov/nwis/iv/"),
    reading_datetime=st.just("2025-01-15T08:00:00.000-08:00"),
    flow_level=st.from_regex(r"[0-9]{1,6}", fullmatch=True),
)


def build_state_gauge_data(state_codes, gauge_numbers_per_state):
    """Build a state_gauge_data dict with matching gauge entries.

    Args:
        state_codes: List of state codes to include data for.
        gauge_numbers_per_state: Dict mapping state_code -> list of gauge numbers.

    Returns:
        Dict mapping state_code -> {gauge_number -> GaugeEntry}.
    """
    result = {}
    for sc in state_codes:
        gauges = gauge_numbers_per_state.get(sc, [])
        if gauges:
            result[sc] = {
                num: GaugeEntry(
                    gauge_number=num,
                    gauge_name=f"Gauge {num}",
                    usgs_page_url="https://waterservices.usgs.gov/nwis/iv/",
                    reading_datetime="2025-01-15T08:00:00.000-08:00",
                    flow_level="1000",
                )
                for num in gauges
            }
    return result


def count_state_headings(html: str) -> int:
    """Count the number of state section headings in the HTML output."""
    return len(re.findall(r'<h2 class="state-heading">', html))


def extract_state_heading_names(html: str) -> list[str]:
    """Extract state names from state section headings in the HTML output."""
    return re.findall(r'<h2 class="state-heading">([^<]+)</h2>', html)


# --- Property 3: One state section per unique state ---


@settings(max_examples=100)
@given(data=st.data())
def test_report_contains_exactly_n_state_sections_for_n_states_with_data(data):
    """**Validates: Requirements 2.1, 4.1**

    For any grouped subscriber with N unique states that have available
    gauge data, the consolidated report SHALL contain exactly N state
    section headings.
    """
    # Generate 1-5 unique state codes for the subscriber
    num_states = data.draw(st.integers(min_value=1, max_value=5))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    # For each state, generate gauge numbers that will be available in data
    gauge_numbers_per_state = {}
    state_preferences = []
    for sc in state_codes:
        # Generate 1-3 gauge numbers for this state
        gauge_nums = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = gauge_nums

        # Use empty included_gauges (meaning "all gauges") to ensure all match
        state_preferences.append(StatePreference(state_code=sc, included_gauges=[]))

    grouped_subscriber = GroupedSubscriber(
        email="test@example.com",
        state_preferences=state_preferences,
    )

    # Build state_gauge_data with data for all states
    state_gauge_data = build_state_gauge_data(state_codes, gauge_numbers_per_state)

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report should not be None since all states have data
    assert report is not None

    # Count state headings — should be exactly N
    heading_count = count_state_headings(report)
    assert heading_count == num_states, (
        f"Expected {num_states} state headings, got {heading_count}"
    )


@settings(max_examples=100)
@given(data=st.data())
def test_single_state_subscriber_has_exactly_one_state_section(data):
    """**Validates: Requirements 2.1, 4.1**

    When a subscriber has only one state, the consolidated report SHALL
    contain exactly one state section heading for that state.
    """
    # Generate a single state code
    state_code = data.draw(state_code_strategy)

    # Generate gauge numbers
    gauge_nums = data.draw(
        st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
    )

    grouped_subscriber = GroupedSubscriber(
        email="single@example.com",
        state_preferences=[StatePreference(state_code=state_code, included_gauges=[])],
    )

    state_gauge_data = build_state_gauge_data(
        [state_code], {state_code: gauge_nums}
    )

    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    assert report is not None

    # Exactly one state heading
    heading_count = count_state_headings(report)
    assert heading_count == 1

    # The heading should contain the full state name
    expected_name = STATE_NAMES[state_code]
    heading_names = extract_state_heading_names(report)
    assert heading_names == [expected_name]


# Feature: email-consolidation, Property 4: State sections ordered alphabetically


@settings(max_examples=100)
@given(data=st.data())
def test_state_sections_ordered_alphabetically(data):
    """**Validates: Requirements 2.3**

    For any consolidated report containing multiple state sections, the state
    name headings SHALL appear in alphabetical order within the HTML output.
    """
    # Generate 2-5 unique state codes to ensure multiple sections
    num_states = data.draw(st.integers(min_value=2, max_value=5))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    # For each state, generate gauge numbers that will be available in data
    gauge_numbers_per_state = {}
    state_preferences = []
    for sc in state_codes:
        gauge_nums = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = gauge_nums
        state_preferences.append(StatePreference(state_code=sc, included_gauges=[]))

    grouped_subscriber = GroupedSubscriber(
        email="alpha@example.com",
        state_preferences=state_preferences,
    )

    # Build state_gauge_data with data for all states
    state_gauge_data = build_state_gauge_data(state_codes, gauge_numbers_per_state)

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report should not be None since all states have data
    assert report is not None

    # Extract state heading names from the HTML
    heading_names = extract_state_heading_names(report)

    # Verify headings are in alphabetical order
    assert heading_names == sorted(heading_names), (
        f"State headings are not in alphabetical order: {heading_names}"
    )

    # Also verify we got the expected number of headings
    assert len(heading_names) == num_states


# Feature: email-consolidation, Property 6: Empty state sections excluded


@settings(max_examples=100)
@given(data=st.data())
def test_empty_state_sections_excluded_no_data_for_state(data):
    """**Validates: Requirements 3.3**

    For any grouped subscriber where some states have no matching gauges
    in the available data (state_gauge_data has no entry for that state code),
    the consolidated report SHALL not contain state section headings for those states.
    """
    # Generate 2-5 unique state codes: split into "with data" and "without data"
    num_states = data.draw(st.integers(min_value=2, max_value=5))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    # At least 1 state has data, at least 1 state has no data
    num_with_data = data.draw(st.integers(min_value=1, max_value=num_states - 1))
    states_with_data = state_codes[:num_with_data]
    states_without_data = state_codes[num_with_data:]

    # Build state preferences for ALL states (subscriber expects all of them)
    state_preferences = [
        StatePreference(state_code=sc, included_gauges=[]) for sc in state_codes
    ]

    grouped_subscriber = GroupedSubscriber(
        email="test@example.com",
        state_preferences=state_preferences,
    )

    # Build state_gauge_data ONLY for states_with_data
    gauge_numbers_per_state = {}
    for sc in states_with_data:
        gauge_nums = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = gauge_nums

    state_gauge_data = build_state_gauge_data(states_with_data, gauge_numbers_per_state)

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report should not be None since at least one state has data
    assert report is not None

    # Extract state heading names from the HTML
    heading_names = extract_state_heading_names(report)

    # States without data should NOT appear in headings
    for sc in states_without_data:
        full_name = STATE_NAMES.get(sc, sc)
        assert full_name not in heading_names, (
            f"State '{full_name}' ({sc}) has no data but appears in report headings"
        )

    # States with data SHOULD appear in headings
    for sc in states_with_data:
        full_name = STATE_NAMES.get(sc, sc)
        assert full_name in heading_names, (
            f"State '{full_name}' ({sc}) has data but is missing from report headings"
        )


@settings(max_examples=100)
@given(data=st.data())
def test_empty_state_sections_excluded_no_matching_gauges(data):
    """**Validates: Requirements 3.3**

    For any grouped subscriber where some states have gauge data available
    but the subscriber's included_gauges for that state don't match any
    gauges in the data, the consolidated report SHALL not contain state
    section headings for those states.
    """
    # Generate 2-4 unique state codes
    num_states = data.draw(st.integers(min_value=2, max_value=4))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    # At least 1 state will have matching gauges, at least 1 will not
    num_matching = data.draw(st.integers(min_value=1, max_value=num_states - 1))
    states_matching = state_codes[:num_matching]
    states_not_matching = state_codes[num_matching:]

    state_preferences = []
    gauge_numbers_per_state = {}

    # For matching states: subscriber's included_gauges overlap with available data
    for sc in states_matching:
        gauge_nums = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = gauge_nums
        # Use empty included_gauges (all gauges) to guarantee a match
        state_preferences.append(StatePreference(state_code=sc, included_gauges=[]))

    # For non-matching states: data exists but subscriber's included_gauges
    # don't overlap with any available gauge numbers
    for sc in states_not_matching:
        # Generate gauge numbers that will be in the data
        available_gauges = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = available_gauges

        # Generate different gauge numbers for the subscriber's filter
        # that definitely don't overlap with available_gauges
        non_overlapping = data.draw(
            st.lists(
                st.from_regex(r"[0-9]{11,15}", fullmatch=True),
                min_size=1,
                max_size=3,
                unique=True,
            )
        )
        state_preferences.append(
            StatePreference(state_code=sc, included_gauges=non_overlapping)
        )

    grouped_subscriber = GroupedSubscriber(
        email="test@example.com",
        state_preferences=state_preferences,
    )

    # Build state_gauge_data for ALL states (both matching and non-matching)
    state_gauge_data = build_state_gauge_data(
        state_codes, gauge_numbers_per_state
    )

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report should not be None since at least one state has matching data
    assert report is not None

    # Extract state heading names from the HTML
    heading_names = extract_state_heading_names(report)

    # States with non-matching gauges should NOT appear in headings
    for sc in states_not_matching:
        full_name = STATE_NAMES.get(sc, sc)
        assert full_name not in heading_names, (
            f"State '{full_name}' ({sc}) has no matching gauges but appears in headings"
        )

    # States with matching gauges SHOULD appear in headings
    for sc in states_matching:
        full_name = STATE_NAMES.get(sc, sc)
        assert full_name in heading_names, (
            f"State '{full_name}' ({sc}) has matching gauges but is missing from headings"
        )


# Feature: email-consolidation, Property 7: All-empty states returns None


@settings(max_examples=100)
@given(data=st.data())
def test_all_empty_states_returns_none_empty_state_gauge_data(data):
    """**Validates: Requirements 3.4**

    For any grouped subscriber where state_gauge_data is an empty dict
    (no gauge data available for any state), the report builder SHALL return None.
    """
    # Generate 1-5 unique state codes for the subscriber
    num_states = data.draw(st.integers(min_value=1, max_value=5))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    # Build state preferences with arbitrary included_gauges
    state_preferences = []
    for sc in state_codes:
        # Mix of empty and non-empty included_gauges
        use_empty = data.draw(st.booleans())
        if use_empty:
            state_preferences.append(StatePreference(state_code=sc, included_gauges=[]))
        else:
            gauge_nums = data.draw(
                st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
            )
            state_preferences.append(
                StatePreference(state_code=sc, included_gauges=gauge_nums)
            )

    grouped_subscriber = GroupedSubscriber(
        email="test@example.com",
        state_preferences=state_preferences,
    )

    # state_gauge_data is empty — no data for any state
    state_gauge_data: dict[str, dict[str, GaugeEntry]] = {}

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report MUST be None since no states have any data
    assert report is None, (
        "Expected None when state_gauge_data is empty, but got a report"
    )


@settings(max_examples=100)
@given(data=st.data())
def test_all_empty_states_returns_none_no_matching_gauges(data):
    """**Validates: Requirements 3.4**

    For any grouped subscriber where state_gauge_data has entries but the
    subscriber's included_gauges for every state don't match any gauges
    in the data, the report builder SHALL return None.
    """
    # Generate 1-5 unique state codes for the subscriber
    num_states = data.draw(st.integers(min_value=1, max_value=5))
    state_codes = data.draw(
        st.lists(
            state_code_strategy,
            min_size=num_states,
            max_size=num_states,
            unique=True,
        )
    )

    state_preferences = []
    gauge_numbers_per_state = {}

    for sc in state_codes:
        # Generate gauge numbers that will be in the data (5-10 digit numbers)
        available_gauges = data.draw(
            st.lists(gauge_number_strategy, min_size=1, max_size=3, unique=True)
        )
        gauge_numbers_per_state[sc] = available_gauges

        # Generate different gauge numbers for the subscriber's filter
        # that definitely don't overlap (use 11-15 digit numbers to avoid collision)
        non_overlapping = data.draw(
            st.lists(
                st.from_regex(r"[0-9]{11,15}", fullmatch=True),
                min_size=1,
                max_size=3,
                unique=True,
            )
        )
        state_preferences.append(
            StatePreference(state_code=sc, included_gauges=non_overlapping)
        )

    grouped_subscriber = GroupedSubscriber(
        email="test@example.com",
        state_preferences=state_preferences,
    )

    # Build state_gauge_data with data for all states
    state_gauge_data = build_state_gauge_data(state_codes, gauge_numbers_per_state)

    # Build the report
    builder = ReportBuilder()
    report = builder.build_consolidated_report(grouped_subscriber, state_gauge_data)

    # Report MUST be None since no state has any matching gauges
    assert report is None, (
        "Expected None when no state has matching gauges, but got a report"
    )
