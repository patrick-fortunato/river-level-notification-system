"""Property tests for ReachResolver helper methods.

Feature: reach-first-subscriptions

Tests the _extract_reach_name and _extract_usgs_gauge methods for correct
formatting and extraction behavior across all valid inputs.

Validates: Requirements 2.2, 2.3, 2.4, 2.5
"""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.reach_resolver import ReachResolver


# --- Helper to create a ReachResolver instance with mocked dependencies ---


def _make_resolver() -> ReachResolver:
    """Create a ReachResolver with mocked dependencies for testing helpers."""
    mock_config = MagicMock()
    mock_http = MagicMock()
    mock_cache = MagicMock()
    return ReachResolver(config=mock_config, http_client=mock_http, cache=mock_cache)


# --- Strategies ---

# Non-empty text for river/section names (printable, no newlines)
name_text_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z"),
                           blacklist_characters="\n\r\x00"),
    min_size=1,
    max_size=50,
).map(str.strip).filter(lambda s: len(s) > 0)

# Possibly empty text for optional fields
optional_text_strategy = st.one_of(
    st.just(""),
    st.just(None),
    name_text_strategy,
)

# Source names for gauge dicts
source_strategy = st.one_of(
    st.just("usgs"),
    st.just("USGS"),
    st.just("Usgs"),
    st.just("virtual"),
    st.just("calculated"),
    st.just("other"),
    st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=1,
        max_size=10,
    ).filter(lambda s: s.lower() != "usgs"),
)

# Source IDs (numeric strings like USGS gauge numbers)
source_id_strategy = st.from_regex(r"[0-9]{5,15}", fullmatch=True)


# --- Property 4: Reach name formatting ---


@settings(max_examples=100)
@given(
    river=name_text_strategy,
    section=optional_text_strategy,
    altname=optional_text_strategy,
)
def test_property_4_reach_name_formatting_river_present(
    river: str, section, altname
):
    """Feature: reach-first-subscriptions, Property 4: Reach name formatting

    For any combination of river, section, and altname strings (where river
    is non-empty), the reach name formatter produces the correct joined string
    matching the expected format.

    Validates: Requirements 2.2
    """
    resolver = _make_resolver()
    reach_data = {
        "river": river,
        "section": section,
        "altname": altname,
    }

    result = resolver._extract_reach_name(reach_data)

    river_stripped = river.strip()
    section_stripped = (section or "").strip()
    altname_stripped = (altname or "").strip()

    # Compute expected output using the same logic as the formatter
    parts = []
    if river_stripped:
        parts.append(river_stripped)
    if section_stripped:
        parts.append(section_stripped)
    expected = " - ".join(parts)
    if altname_stripped:
        expected += f" ({altname_stripped})"

    assert result == expected


@settings(max_examples=100)
@given(
    section=name_text_strategy,
    altname=optional_text_strategy,
)
def test_property_4_reach_name_formatting_section_only(
    section: str, altname
):
    """Feature: reach-first-subscriptions, Property 4: Reach name formatting

    When only section is non-empty (river is empty), the formatter produces
    the correct string with section and optional altname in parentheses.

    Validates: Requirements 2.2
    """
    resolver = _make_resolver()
    reach_data = {
        "river": "",
        "section": section,
        "altname": altname,
    }

    result = resolver._extract_reach_name(reach_data)

    section_stripped = section.strip()
    altname_stripped = (altname or "").strip()

    # Compute expected output
    expected = section_stripped
    if altname_stripped:
        expected += f" ({altname_stripped})"

    assert result == expected


@settings(max_examples=100)
@given(
    river=name_text_strategy,
    section=name_text_strategy,
    altname=name_text_strategy,
)
def test_property_4_reach_name_formatting_all_fields(
    river: str, section: str, altname: str
):
    """Feature: reach-first-subscriptions, Property 4: Reach name formatting

    When all fields are present, the format is exactly "River - Section (Altname)".

    Validates: Requirements 2.2
    """
    resolver = _make_resolver()
    reach_data = {
        "river": river,
        "section": section,
        "altname": altname,
    }

    result = resolver._extract_reach_name(reach_data)

    expected = f"{river.strip()} - {section.strip()} ({altname.strip()})"
    assert result == expected


# --- Property 5: First USGS gauge extraction ---


@settings(max_examples=100)
@given(
    non_usgs_gauges=st.lists(
        st.fixed_dictionaries({
            "source": source_strategy.filter(lambda s: s.lower() != "usgs"),
            "source_id": source_id_strategy,
        }),
        min_size=0,
        max_size=5,
    ),
    usgs_source_id=source_id_strategy,
    usgs_case=st.sampled_from(["usgs", "USGS", "Usgs", "UsGs"]),
    trailing_gauges=st.lists(
        st.fixed_dictionaries({
            "source": source_strategy,
            "source_id": source_id_strategy,
        }),
        min_size=0,
        max_size=3,
    ),
)
def test_property_5_first_usgs_gauge_extraction(
    non_usgs_gauges: list[dict],
    usgs_source_id: str,
    usgs_case: str,
    trailing_gauges: list[dict],
):
    """Feature: reach-first-subscriptions, Property 5: First USGS gauge extraction

    Returns source_id of first dict with source="usgs" (case-insensitive),
    regardless of other gauges before or after it.

    Validates: Requirements 2.3, 2.4, 2.5
    """
    resolver = _make_resolver()

    # Build gauge list: non-usgs gauges, then the first usgs gauge, then trailing
    usgs_gauge = {"source": usgs_case, "source_id": usgs_source_id}
    gauges = non_usgs_gauges + [usgs_gauge] + trailing_gauges

    result = resolver._extract_usgs_gauge(gauges)

    # Should return the source_id of the first USGS gauge
    assert result == usgs_source_id


@settings(max_examples=100)
@given(
    gauges=st.lists(
        st.fixed_dictionaries({
            "source": source_strategy.filter(lambda s: s.lower() != "usgs"),
            "source_id": source_id_strategy,
        }),
        min_size=0,
        max_size=10,
    ),
)
def test_property_5_no_usgs_gauge_returns_none(
    gauges: list[dict],
):
    """Feature: reach-first-subscriptions, Property 5: First USGS gauge extraction

    Returns None when no gauge has source="usgs".

    Validates: Requirements 2.3, 2.4, 2.5
    """
    resolver = _make_resolver()

    result = resolver._extract_usgs_gauge(gauges)

    assert result is None


# --- Property 1: Resolver extracts state from API response ---


# Strategy for state values: valid 2-letter codes, None, or empty string
state_value_strategy = st.one_of(
    st.none(),
    st.just(""),
    st.sampled_from(["OR", "WA", "CA", "CO", "ID", "MT", "UT", "AK"]),
    st.from_regex(r"[A-Z]{2}", fullmatch=True),
)


@settings(max_examples=100)
@given(
    reach_id=st.integers(min_value=1, max_value=99999),
    river=name_text_strategy,
    section=name_text_strategy,
    state_value=state_value_strategy,
    gauge_source_id=source_id_strategy,
)
def test_property_1_resolver_extracts_state_from_api_response(
    reach_id: int,
    river: str,
    section: str,
    state_value,
    gauge_source_id: str,
):
    """Feature: state-grouped-email, Property 1: Resolver extracts state from API response

    For any valid AW API response containing a state field (including null and
    non-null values), the ReachResolver SHALL produce a ResolvedReach whose
    state field matches the API response value (with null/empty mapped to None).

    **Validates: Requirements 1.2, 1.3**
    """
    resolver = _make_resolver()

    # Mock the HTTP response with the new states array format
    mock_response = MagicMock()
    mock_response.status_code = 200

    # Build the states array based on state_value
    if state_value:
        states_array = [{"shortkey": state_value}]
    elif state_value is None:
        states_array = []
    else:
        # Empty string case
        states_array = [{"shortkey": ""}]

    mock_response.json.return_value = {
        "data": {
            "reach": {
                "river": river,
                "section": section,
                "altname": None,
                "states": states_array,
            },
            "getGaugeInformationForReachID": {
                "gauges": [
                    {"gauge": {"source": "usgs", "source_id": gauge_source_id}}
                ]
            },
        }
    }

    resolver._http_client.post.return_value = mock_response

    result = resolver._query_reach(reach_id)

    # Null/empty state should map to None
    expected_state = state_value if state_value else None

    assert result.state == expected_state, (
        f"Expected state={expected_state!r}, got state={result.state!r} "
        f"for API state value={state_value!r}"
    )
    assert result.reach_id == reach_id
