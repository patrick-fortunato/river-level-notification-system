# Feature: river-level-notification-system, Property 1: USGS JSON Parsing Extracts All Required Fields
"""Property test for USGS JSON parsing.

Generates arbitrary valid USGS JSON responses and verifies each time series
produces a GaugeEntry with non-empty gauge_number, gauge_name, usgs_page_url,
reading_datetime, and flow_level.

Validates: Requirements 1.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.usgs_fetcher import USGSFetcher

import requests


def usgs_time_series_strategy():
    """Generate a valid USGS time series entry."""
    return st.fixed_dictionaries({
        "sourceInfo": st.fixed_dictionaries({
            "siteName": st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
                min_size=1,
                max_size=50,
            ),
            "siteCode": st.lists(
                st.fixed_dictionaries({
                    "value": st.from_regex(r"[0-9]{5,15}", fullmatch=True),
                }),
                min_size=1,
                max_size=1,
            ),
        }),
        "values": st.lists(
            st.fixed_dictionaries({
                "value": st.lists(
                    st.fixed_dictionaries({
                        "value": st.from_regex(r"[0-9]{1,6}", fullmatch=True),
                        "dateTime": st.from_regex(
                            r"2025-0[1-9]-[012][0-9]T[01][0-9]:[0-5][0-9]:00\.000-0[78]:00",
                            fullmatch=True,
                        ),
                    }),
                    min_size=1,
                    max_size=5,
                ),
            }),
            min_size=1,
            max_size=1,
        ),
    })


def usgs_response_strategy():
    """Generate a valid USGS API JSON response with one or more time series.

    Each time series has a unique gauge number to avoid dict key collisions.
    """
    return st.integers(min_value=1, max_value=10).flatmap(
        lambda n: st.lists(
            usgs_time_series_strategy(),
            min_size=n,
            max_size=n,
        ).filter(
            # Ensure all gauge numbers are unique
            lambda series: len(set(
                s["sourceInfo"]["siteCode"][0]["value"] for s in series
            )) == len(series)
        ).map(lambda ts: {"value": {"timeSeries": ts}})
    )


@settings(max_examples=100)
@given(json_data=usgs_response_strategy())
def test_parsing_extracts_all_required_fields(json_data: dict):
    """Verify each time series produces a GaugeEntry with all non-empty fields."""
    config = Config()
    session = requests.Session()
    fetcher = USGSFetcher(config, session)

    result = fetcher._parse_response(json_data)

    # Every valid time series should produce a GaugeEntry
    expected_count = len(json_data["value"]["timeSeries"])
    assert len(result) == expected_count

    for gauge_number, entry in result.items():
        assert entry.gauge_number != ""
        assert entry.gauge_name != ""
        assert entry.usgs_page_url != ""
        assert entry.reading_datetime != ""
        assert entry.flow_level != ""
        assert gauge_number == entry.gauge_number
        assert f"USGS-{gauge_number}" in entry.usgs_page_url


@settings(max_examples=100)
@given(json_data=usgs_response_strategy())
def test_parsing_produces_correct_url_format(json_data: dict):
    """Verify each GaugeEntry has a properly formatted USGS page URL."""
    config = Config()
    session = requests.Session()
    fetcher = USGSFetcher(config, session)

    result = fetcher._parse_response(json_data)

    for gauge_number, entry in result.items():
        expected_url = (
            f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/"
            f"#period=P7D&dataTypeId=continuous-00060-0&showMedian=true&showFieldMeasurements=true"
        )
        assert entry.usgs_page_url == expected_url
