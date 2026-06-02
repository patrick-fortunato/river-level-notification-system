"""Property tests for the ReportBuilder.

Feature: reach-first-subscriptions

Tests the ReportBuilder's build_report method for correct HTML rendering
of AW links, flow data, USGS links, and subscriber reach ordering.

Validates: Requirements 4.1, 4.2, 4.3, 4.5
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models import GaugeEntry, ReachSubscriber, ResolvedReach
from src.report_builder import ReportBuilder


# --- Strategies ---

# Reach IDs: positive integers in a realistic range
reach_id_strategy = st.integers(min_value=1, max_value=99999)

# Reach names: non-empty printable text
reach_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z"),
        blacklist_characters="<>&\"'\n\r\x00",
    ),
    min_size=1,
    max_size=50,
).map(str.strip).filter(lambda s: len(s) > 0)

# Gauge numbers: numeric strings like USGS gauge IDs
gauge_number_strategy = st.from_regex(r"[0-9]{5,10}", fullmatch=True)

# Flow level: numeric string representing cfs
flow_level_strategy = st.from_regex(r"[1-9][0-9]{0,4}", fullmatch=True)

# Reading datetime: ISO 8601 format
reading_datetime_strategy = st.from_regex(
    r"2025-0[1-9]-[012][1-9]T[01][0-9]:[0-5][0-9]:00\.000-0[5-8]:00",
    fullmatch=True,
)

# Email strategy
email_strategy = st.from_regex(r"[a-z]{3,10}@[a-z]{3,8}\.com", fullmatch=True)


def resolved_reach_with_gauge_strategy():
    """Generate a ResolvedReach with a gauge_id."""
    return st.builds(
        ResolvedReach,
        reach_id=reach_id_strategy,
        reach_name=reach_name_strategy,
        gauge_id=gauge_number_strategy,
    )


def resolved_reach_without_gauge_strategy():
    """Generate a ResolvedReach without a gauge_id."""
    return st.builds(
        ResolvedReach,
        reach_id=reach_id_strategy,
        reach_name=reach_name_strategy,
        gauge_id=st.none(),
    )


def gauge_entry_strategy(gauge_number):
    """Generate a GaugeEntry for a specific gauge number."""
    return st.builds(
        GaugeEntry,
        gauge_number=st.just(gauge_number),
        gauge_name=reach_name_strategy,
        usgs_page_url=st.just(
            f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/"
        ),
        reading_datetime=reading_datetime_strategy,
        flow_level=flow_level_strategy,
    )


# --- Property 7: Report contains AW link for every reach ---


@settings(max_examples=100)
@given(
    reach_ids=st.lists(reach_id_strategy, min_size=1, max_size=5, unique=True),
    email=email_strategy,
    data=st.data(),
)
def test_property_7_report_contains_aw_link_for_every_reach(
    reach_ids: list[int], email: str, data
):
    """Feature: reach-first-subscriptions, Property 7: Report contains AW link for every reach

    For any resolved reach with a non-empty name, the rendered HTML for that
    reach entry contains an anchor tag linking to the correct AW URL
    (river-detail/{reach_id}/main).

    Validates: Requirements 4.1
    """
    subscriber = ReachSubscriber(email=email, reach_ids=reach_ids)

    # Build resolved reaches for all reach IDs
    resolved_reaches: dict[int, ResolvedReach] = {}
    for rid in reach_ids:
        name = data.draw(reach_name_strategy, label=f"name_{rid}")
        resolved_reaches[rid] = ResolvedReach(
            reach_id=rid, reach_name=name, gauge_id=None
        )

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # Verify each reach has its AW URL in the HTML
    for rid in reach_ids:
        expected_url_fragment = f"river-detail/{rid}/main"
        assert expected_url_fragment in html, (
            f"Expected AW URL fragment 'river-detail/{rid}/main' not found in HTML"
        )


# --- Property 8: Report contains flow data when gauge data present ---


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    gauge_number=gauge_number_strategy,
    flow_level=flow_level_strategy,
    reading_datetime=reading_datetime_strategy,
    email=email_strategy,
)
def test_property_8_report_contains_flow_data_when_gauge_present(
    reach_id: int,
    reach_name: str,
    gauge_number: str,
    flow_level: str,
    reading_datetime: str,
    email: str,
):
    """Feature: reach-first-subscriptions, Property 8: Report contains flow data when gauge data present

    For any reach entry where gauge data is available, the rendered HTML
    contains both the flow level value (in cfs) and some form of the timestamp.

    Validates: Requirements 4.2
    """
    subscriber = ReachSubscriber(email=email, reach_ids=[reach_id])
    resolved_reaches = {
        reach_id: ResolvedReach(
            reach_id=reach_id, reach_name=reach_name, gauge_id=gauge_number
        )
    }
    gauge_data = {
        gauge_number: GaugeEntry(
            gauge_number=gauge_number,
            gauge_name=f"Gauge {gauge_number}",
            usgs_page_url=f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/",
            reading_datetime=reading_datetime,
            flow_level=flow_level,
        )
    }

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data)

    assert html is not None

    # HTML must contain the flow level value
    assert flow_level in html, (
        f"Expected flow level '{flow_level}' not found in HTML"
    )

    # HTML must contain "cfs" unit indicator
    assert "cfs" in html, "Expected 'cfs' unit not found in HTML"


# --- Property 9: Report contains USGS link when gauge present ---


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    gauge_number=gauge_number_strategy,
    flow_level=flow_level_strategy,
    reading_datetime=reading_datetime_strategy,
    email=email_strategy,
)
def test_property_9_report_contains_usgs_link_when_gauge_present(
    reach_id: int,
    reach_name: str,
    gauge_number: str,
    flow_level: str,
    reading_datetime: str,
    email: str,
):
    """Feature: reach-first-subscriptions, Property 9: Report contains USGS link when gauge present

    For any reach entry where a USGS gauge is associated, the rendered HTML
    contains an anchor tag linking to the USGS monitoring page for that gauge number.

    Validates: Requirements 4.3
    """
    subscriber = ReachSubscriber(email=email, reach_ids=[reach_id])
    resolved_reaches = {
        reach_id: ResolvedReach(
            reach_id=reach_id, reach_name=reach_name, gauge_id=gauge_number
        )
    }
    gauge_data = {
        gauge_number: GaugeEntry(
            gauge_number=gauge_number,
            gauge_name=f"Gauge {gauge_number}",
            usgs_page_url=f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/",
            reading_datetime=reading_datetime,
            flow_level=flow_level,
        )
    }

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data)

    assert html is not None

    # HTML must contain the USGS monitoring page URL with the gauge number
    expected_usgs_url = f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/"
    assert expected_usgs_url in html, (
        f"Expected USGS URL '{expected_usgs_url}' not found in HTML"
    )

    # Verify it's rendered as a clickable link
    assert f'href="{expected_usgs_url}"' in html, (
        f"Expected USGS URL to be in an href attribute"
    )


# --- Property 10: Report preserves subscriber reach order ---


@settings(max_examples=100)
@given(
    reach_ids=st.lists(reach_id_strategy, min_size=2, max_size=8, unique=True),
    email=email_strategy,
    data=st.data(),
)
def test_property_10_report_preserves_subscriber_reach_order(
    reach_ids: list[int], email: str, data
):
    """Feature: reach-first-subscriptions, Property 10: Report preserves subscriber reach order

    For any subscriber with an ordered list of reach IDs, the rendered report
    contains reach entries in the same order as the subscriber's reach_ids list.

    Validates: Requirements 4.5
    """
    subscriber = ReachSubscriber(email=email, reach_ids=reach_ids)

    # Build resolved reaches for all reach IDs
    resolved_reaches: dict[int, ResolvedReach] = {}
    for rid in reach_ids:
        name = data.draw(reach_name_strategy, label=f"name_{rid}")
        resolved_reaches[rid] = ResolvedReach(
            reach_id=rid, reach_name=name, gauge_id=None
        )

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # Verify reach entries appear in the same order by checking positions
    # of AW URL fragments in the HTML
    positions = []
    for rid in reach_ids:
        url_fragment = f"river-detail/{rid}/main"
        pos = html.find(url_fragment)
        assert pos != -1, f"AW URL for reach {rid} not found in HTML"
        positions.append(pos)

    # Positions must be strictly increasing (preserving order)
    for i in range(len(positions) - 1):
        assert positions[i] < positions[i + 1], (
            f"Reach {reach_ids[i]} (pos {positions[i]}) appears after "
            f"reach {reach_ids[i + 1]} (pos {positions[i + 1]}) in HTML, "
            f"violating subscriber order"
        )


# --- Strategies for state-grouped-email tests ---

from src.config import STATE_NAMES

# Known state abbreviations from STATE_NAMES
known_state_codes = list(STATE_NAMES.keys())

# Strategy for state values
state_code_strategy = st.sampled_from(known_state_codes)

# Strategy for unknown state abbreviations (not in STATE_NAMES)
unknown_state_strategy = st.from_regex(r"[A-Z]{2}", fullmatch=True).filter(
    lambda s: s not in STATE_NAMES
)


# --- Property 3: State groups ordered alphabetically with "Other" last ---


@settings(max_examples=100)
@given(
    email=email_strategy,
    data=st.data(),
)
def test_property_3_state_groups_ordered_alphabetically_other_last(
    email: str, data
):
    """Feature: state-grouped-email, Property 3: State groups ordered alphabetically with "Other" last

    For any subscriber report containing reaches from multiple states, the state
    group headings SHALL appear in alphabetical order by full state name, with
    reaches having no state grouped under "Other" appearing after all named state
    groups.

    **Validates: Requirements 4.1, 4.4, 4.5**
    """
    # Generate at least 2 distinct states to assign to reaches
    distinct_states = data.draw(
        st.lists(
            st.one_of(st.none(), state_code_strategy),
            min_size=2,
            max_size=5,
            unique_by=lambda x: str(x),
        ),
        label="distinct_states",
    )

    # Generate reach_ids with at least as many as distinct states
    num_reaches = data.draw(
        st.integers(min_value=len(distinct_states), max_value=8),
        label="num_reaches",
    )
    reach_ids = data.draw(
        st.lists(reach_id_strategy, min_size=num_reaches, max_size=num_reaches, unique=True),
        label="reach_ids",
    )

    subscriber = ReachSubscriber(email=email, reach_ids=reach_ids)

    # Assign states ensuring each distinct state is used at least once
    resolved_reaches: dict[int, ResolvedReach] = {}
    for i, rid in enumerate(reach_ids):
        if i < len(distinct_states):
            state = distinct_states[i]
        else:
            state = distinct_states[i % len(distinct_states)]
        name = data.draw(reach_name_strategy, label=f"name_{rid}")
        resolved_reaches[rid] = ResolvedReach(
            reach_id=rid, reach_name=name, gauge_id=None, state=state
        )

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # Extract state heading positions from the HTML
    import re
    heading_pattern = re.compile(r'<h2 class="state-heading">([^<]+)</h2>')
    headings = heading_pattern.findall(html)

    assert len(headings) >= 2, f"Expected at least 2 headings, got {headings}"

    # Separate "Other" from named headings
    named_headings = [h for h in headings if h != "Other"]
    has_other = "Other" in headings

    # Named headings must be in alphabetical order
    assert named_headings == sorted(named_headings), (
        f"Named headings not alphabetically ordered: {named_headings}"
    )

    # If "Other" is present, it must be the last heading
    if has_other:
        assert headings[-1] == "Other", (
            f"'Other' is not the last heading. Headings: {headings}"
        )


# --- Property 4: State headings display full state name ---


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    state_code=state_code_strategy,
    email=email_strategy,
)
def test_property_4_state_headings_display_full_state_name(
    reach_id: int, reach_name: str, state_code: str, email: str
):
    """Feature: state-grouped-email, Property 4: State headings display full state name

    For any reach with a state abbreviation present in STATE_NAMES, the report
    SHALL display the corresponding full state name as the group heading. For any
    abbreviation not in STATE_NAMES, the raw abbreviation SHALL be used as the heading.

    **Validates: Requirements 4.2, 6.1, 6.2**
    """
    subscriber = ReachSubscriber(email=email, reach_ids=[reach_id])
    resolved_reaches = {
        reach_id: ResolvedReach(
            reach_id=reach_id, reach_name=reach_name, gauge_id=None, state=state_code
        )
    }

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # The heading should be the full state name
    expected_heading = STATE_NAMES[state_code]
    import re
    heading_pattern = re.compile(r'<h2 class="state-heading">([^<]+)</h2>')
    headings = heading_pattern.findall(html)

    assert expected_heading in headings, (
        f"Expected heading '{expected_heading}' for state '{state_code}' "
        f"not found in headings: {headings}"
    )


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    unknown_state=unknown_state_strategy,
    email=email_strategy,
)
def test_property_4_unknown_state_uses_raw_abbreviation(
    reach_id: int, reach_name: str, unknown_state: str, email: str
):
    """Feature: state-grouped-email, Property 4: State headings display full state name (unknown codes)

    For any abbreviation not in STATE_NAMES, the raw abbreviation SHALL be used
    as the heading.

    **Validates: Requirements 4.2, 6.1, 6.2**
    """
    subscriber = ReachSubscriber(email=email, reach_ids=[reach_id])
    resolved_reaches = {
        reach_id: ResolvedReach(
            reach_id=reach_id, reach_name=reach_name, gauge_id=None, state=unknown_state
        )
    }

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # The heading should be the raw abbreviation since it's not in STATE_NAMES
    import re
    heading_pattern = re.compile(r'<h2 class="state-heading">([^<]+)</h2>')
    headings = heading_pattern.findall(html)

    assert unknown_state in headings, (
        f"Expected raw abbreviation '{unknown_state}' as heading, "
        f"got headings: {headings}"
    )


# --- Property 5: Intra-group subscriber order preserved ---


@settings(max_examples=100)
@given(
    reach_ids=st.lists(reach_id_strategy, min_size=2, max_size=6, unique=True),
    state_code=state_code_strategy,
    email=email_strategy,
    data=st.data(),
)
def test_property_5_intra_group_subscriber_order_preserved(
    reach_ids: list[int], state_code: str, email: str, data
):
    """Feature: state-grouped-email, Property 5: Intra-group subscriber order preserved

    For any subscriber with multiple reaches in the same state, those reaches
    SHALL appear within their state group in the same relative order as in the
    subscriber's reach_ids list.

    **Validates: Requirements 4.3**
    """
    subscriber = ReachSubscriber(email=email, reach_ids=reach_ids)

    # All reaches in the same state
    resolved_reaches: dict[int, ResolvedReach] = {}
    for rid in reach_ids:
        name = data.draw(reach_name_strategy, label=f"name_{rid}")
        resolved_reaches[rid] = ResolvedReach(
            reach_id=rid, reach_name=name, gauge_id=None, state=state_code
        )

    builder = ReportBuilder()
    html = builder.build_report(subscriber, resolved_reaches, gauge_data={})

    assert html is not None

    # Verify reach entries appear in subscriber order by checking positions
    # of AW URL fragments in the HTML
    positions = []
    for rid in reach_ids:
        url_fragment = f"river-detail/{rid}/main"
        pos = html.find(url_fragment)
        assert pos != -1, f"AW URL for reach {rid} not found in HTML"
        positions.append(pos)

    # Positions must be strictly increasing (preserving intra-group order)
    for i in range(len(positions) - 1):
        assert positions[i] < positions[i + 1], (
            f"Reach {reach_ids[i]} (pos {positions[i]}) appears after "
            f"reach {reach_ids[i + 1]} (pos {positions[i + 1]}) in HTML, "
            f"violating intra-group subscriber order"
        )


# --- Property 3 (aw-flow-fallback): Bug Condition — Report renders AW flow data ---

from src.models import AWFlowData

# Strategy for AW flow reading values
aw_reading_strategy = st.floats(min_value=0.1, max_value=100000.0, allow_nan=False, allow_infinity=False)

# Strategy for AW unit strings
aw_unit_strategy = st.sampled_from(["cfs", "ft", "m3/s", "cms"])

# Strategy for AW gauge name
aw_gauge_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), blacklist_characters="<>&\"'\n\r\x00"),
    min_size=1,
    max_size=30,
).map(str.strip).filter(lambda s: len(s) > 0)

# Strategy for updated timestamps
aw_updated_strategy = st.one_of(
    st.none(),
    st.floats(min_value=1.0, max_value=99999999.0, allow_nan=False, allow_infinity=False),
)


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    reading=aw_reading_strategy,
    unit=aw_unit_strategy,
    gauge_name=aw_gauge_name_strategy,
    updated=aw_updated_strategy,
)
def test_property_aw_flow_fallback_3_report_renders_aw_flow_data(
    reach_id: int,
    reach_name: str,
    reading: float,
    unit: str,
    gauge_name: str,
    updated,
):
    """Feature: aw-flow-fallback, Property 3: Bug Condition — Report renders AW flow data

    For any resolved reach with aw_flow_data populated (non-None) and gauge_id=None,
    the fixed ReportBuilder._render_reach_entry SHALL produce HTML that contains the
    flow reading value and does NOT contain "No gauge data available".

    **Validates: Requirements 2.3**
    """
    aw_flow_data = AWFlowData(
        reading=reading,
        unit=unit,
        gauge_name=gauge_name,
        updated=updated,
    )

    resolved = ResolvedReach(
        reach_id=reach_id,
        reach_name=reach_name,
        gauge_id=None,
        aw_flow_data=aw_flow_data,
    )

    builder = ReportBuilder()
    html = builder._render_reach_entry(resolved, gauge_entry=None)

    # Should contain the reading value
    assert str(reading) in html, (
        f"Expected reading '{reading}' in HTML output, got: {html}"
    )

    # Should contain the unit
    assert unit in html, (
        f"Expected unit '{unit}' in HTML output, got: {html}"
    )

    # Should NOT contain the empty-state message
    assert "No gauge data available" not in html, (
        f"HTML should not contain 'No gauge data available' when aw_flow_data is set"
    )

    # Should contain the gauge name (AW attribution)
    assert gauge_name in html, (
        f"Expected gauge_name '{gauge_name}' in HTML output for AW attribution"
    )


# --- Property 4 (aw-flow-fallback): Preservation — USGS report rendering unchanged ---


@settings(max_examples=100)
@given(
    reach_id=reach_id_strategy,
    reach_name=reach_name_strategy,
    gauge_number=gauge_number_strategy,
    flow_level=flow_level_strategy,
    reading_datetime=reading_datetime_strategy,
)
def test_property_aw_flow_fallback_4_usgs_report_rendering_unchanged(
    reach_id: int,
    reach_name: str,
    gauge_number: str,
    flow_level: str,
    reading_datetime: str,
):
    """Feature: aw-flow-fallback, Property 4: Preservation — USGS report rendering unchanged

    For any resolved reach with a valid gauge_id and a corresponding GaugeEntry,
    the fixed ReportBuilder._render_reach_entry SHALL produce HTML that contains
    the flow level in cfs, a USGS gauge link, and does NOT reference AW attribution.

    **Validates: Requirements 3.4**
    """
    resolved = ResolvedReach(
        reach_id=reach_id,
        reach_name=reach_name,
        gauge_id=gauge_number,
    )

    gauge_entry = GaugeEntry(
        gauge_number=gauge_number,
        gauge_name=f"Gauge {gauge_number}",
        usgs_page_url=f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/",
        reading_datetime=reading_datetime,
        flow_level=flow_level,
    )

    builder = ReportBuilder()
    html = builder._render_reach_entry(resolved, gauge_entry)

    # Should contain the flow level
    assert flow_level in html, (
        f"Expected flow level '{flow_level}' in USGS HTML output"
    )

    # Should contain "cfs" unit
    assert "cfs" in html, (
        "Expected 'cfs' in USGS HTML output"
    )

    # Should contain the USGS gauge link
    expected_usgs_url = f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/"
    assert expected_usgs_url in html, (
        f"Expected USGS URL in HTML output"
    )

    # Should contain the gauge number reference
    assert gauge_number in html, (
        f"Expected gauge number '{gauge_number}' in HTML output"
    )

    # Should NOT contain "No gauge data available"
    assert "No gauge data available" not in html, (
        "USGS reach should not show 'No gauge data available'"
    )

    # Should NOT contain AW attribution markers
    assert "(via AW)" not in html, (
        "USGS reach should not contain AW attribution '(via AW)'"
    )
