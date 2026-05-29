# Feature: river-level-notification-system, Property 3: Report Contains Only Included Gauges
# Feature: river-level-notification-system, Property 4: HTML Rendering Contains All Required Gauge Information
# Feature: river-level-notification-system, Property 7: Empty Report Suppression
"""Property tests for the report builder.

Property 3: Verify the report includes exactly those gauges present in gauge_data
AND in the subscriber's included_gauges list (or all if the list is empty).
Validates: Requirements 3.1, 3.4

Property 4: Verify rendered HTML contains the USGS page URL, gauge name,
reading datetime, and flow level.
Validates: Requirements 3.2

Property 7: Verify build_report returns None when no gauges match
or no gauge data is available.
Validates: Requirements 10.1
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.models import GaugeEntry, Subscriber
from src.report_builder import ReportBuilder, _format_reading_datetime


# Strategy for generating gauge numbers
gauge_number_strategy = st.from_regex(r"[0-9]{5,10}", fullmatch=True)

# Strategy for generating gauge entries
gauge_entry_strategy = st.builds(
    GaugeEntry,
    gauge_number=gauge_number_strategy,
    gauge_name=st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=5,
        max_size=40,
    ),
    usgs_page_url=gauge_number_strategy.map(
        lambda n: f"https://waterdata.usgs.gov/nwis/uv?site_no={n}"
    ),
    reading_datetime=st.from_regex(
        r"2025-0[1-9]-[012][1-9]T[01][0-9]:[0-5][0-9]:00",
        fullmatch=True,
    ),
    flow_level=st.from_regex(r"[1-9][0-9]{0,4}", fullmatch=True),
)


def gauge_data_strategy(min_size=1, max_size=10):
    """Generate a dict of gauge_number -> GaugeEntry."""
    return st.lists(
        gauge_entry_strategy, min_size=min_size, max_size=max_size
    ).map(lambda entries: {e.gauge_number: e for e in entries})


# --- Property 3: Report Contains Only Included Gauges ---


@settings(max_examples=100)
@given(
    gauge_data=gauge_data_strategy(min_size=2, max_size=10),
    data=st.data(),
)
def test_report_includes_only_specified_gauges(gauge_data: dict, data):
    """Verify report includes only gauges in the inclusion list."""
    gauge_numbers = list(gauge_data.keys())
    # Include a random non-empty subset
    included = data.draw(
        st.lists(
            st.sampled_from(gauge_numbers),
            min_size=1,
            max_size=len(gauge_numbers),
            unique=True,
        )
    )

    subscriber = Subscriber(email="test@example.com", included_gauges=included)
    builder = ReportBuilder()
    report = builder.build_report(subscriber, gauge_data)

    assert report is not None

    # Check that included gauges appear in the report
    for gauge_num in included:
        assert f"<b>Gauge:</b> {gauge_num}" in report

    # Check that non-included gauges do NOT appear in the report
    not_included = set(gauge_numbers) - set(included)
    for gauge_num in not_included:
        assert f"<b>Gauge:</b> {gauge_num}" not in report


@settings(max_examples=100)
@given(gauge_data=gauge_data_strategy(min_size=1, max_size=10))
def test_report_with_empty_inclusion_list_includes_all_gauges(gauge_data: dict):
    """Verify report with empty inclusion list includes all gauges."""
    subscriber = Subscriber(email="test@example.com", included_gauges=[])
    builder = ReportBuilder()
    report = builder.build_report(subscriber, gauge_data)

    assert report is not None
    for gauge_num, entry in gauge_data.items():
        assert entry.gauge_name in report


@settings(max_examples=100)
@given(
    gauge_data=gauge_data_strategy(min_size=1, max_size=5),
)
def test_report_silently_ignores_nonexistent_included_gauges(gauge_data: dict):
    """Verify inclusion of non-existent gauge numbers doesn't cause errors."""
    # Include gauge numbers that don't exist in the data plus one that does
    real_gauge = list(gauge_data.keys())[0]
    subscriber = Subscriber(
        email="test@example.com",
        included_gauges=[real_gauge, "99999999", "00000000"],
    )
    builder = ReportBuilder()
    report = builder.build_report(subscriber, gauge_data)

    # Only the real gauge should appear
    assert report is not None
    assert f"<b>Gauge:</b> {real_gauge}" in report


# --- Property 4: HTML Rendering Contains All Required Gauge Information ---


@settings(max_examples=100)
@given(gauge_entry=gauge_entry_strategy)
def test_html_contains_all_required_gauge_information(gauge_entry: GaugeEntry):
    """Verify rendered HTML contains URL, gauge name, formatted datetime, and flow level."""
    builder = ReportBuilder()
    html = builder._render_gauge_entry(gauge_entry.gauge_number, gauge_entry)

    assert gauge_entry.usgs_page_url in html
    assert gauge_entry.gauge_name in html
    assert _format_reading_datetime(gauge_entry.reading_datetime) in html
    assert gauge_entry.flow_level in html


@settings(max_examples=100)
@given(gauge_entry=gauge_entry_strategy)
def test_html_contains_clickable_link(gauge_entry: GaugeEntry):
    """Verify the USGS page URL is rendered as a clickable link."""
    builder = ReportBuilder()
    html = builder._render_gauge_entry(gauge_entry.gauge_number, gauge_entry)

    assert f'href="{gauge_entry.usgs_page_url}"' in html


# --- Property 7: Empty Report Suppression ---


@settings(max_examples=100)
@given(gauge_data=gauge_data_strategy(min_size=1, max_size=10))
def test_no_matching_included_gauges_returns_none(gauge_data: dict):
    """Verify build_report returns None when included gauges don't match any data."""
    subscriber = Subscriber(
        email="test@example.com",
        included_gauges=["99999999", "00000000"],
    )
    builder = ReportBuilder()
    result = builder.build_report(subscriber, gauge_data)
    assert result is None


@settings(max_examples=100)
@given(included=st.lists(gauge_number_strategy, min_size=0, max_size=5))
def test_empty_gauge_data_returns_none(included: list[str]):
    """Verify build_report returns None when gauge data is empty."""
    subscriber = Subscriber(email="test@example.com", included_gauges=included)
    builder = ReportBuilder()
    result = builder.build_report(subscriber, {})
    assert result is None
