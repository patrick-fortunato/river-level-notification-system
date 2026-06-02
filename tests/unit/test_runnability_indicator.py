"""Unit tests for runnability indicator feature.

Tests verify:
- GraphQL query includes rmin and rmax fields
- flow_level string-to-float conversion edge cases
- Indicator HTML uses inline style= attributes (not class-based)
"""

from src.models import (
    GaugeEntry,
    ResolvedReach,
    RunnabilityStatus,
    classify_runnability,
)
from src.reach_resolver import ReachResolver
from src.report_builder import ReportBuilder


class TestGraphQLQueryIncludesRminRmax:
    """6.1: Unit test verifying GraphQL query string includes rmin and rmax fields."""

    def test_query_contains_rmin(self):
        """The GraphQL query string in ReachResolver must include 'rmin'."""
        import inspect

        source = inspect.getsource(ReachResolver._query_reach)
        assert "rmin" in source, (
            "GraphQL query in _query_reach does not include 'rmin'"
        )

    def test_query_contains_rmax(self):
        """The GraphQL query string in ReachResolver must include 'rmax'."""
        import inspect

        source = inspect.getsource(ReachResolver._query_reach)
        assert "rmax" in source, (
            "GraphQL query in _query_reach does not include 'rmax'"
        )

    def test_query_string_has_rmin_rmax_in_gauge_fields(self):
        """The rmin and rmax fields appear in the gauge information query."""
        import inspect

        source = inspect.getsource(ReachResolver._query_reach)
        # Check that rmin and rmax appear in the graphql query literal
        # The query string should contain "rmin rmax" as field selections
        assert "rmin rmax" in source, (
            "Expected 'rmin rmax' as adjacent fields in the GraphQL query string"
        )


class TestFlowLevelConversionEdgeCases:
    """6.2: Unit test for flow_level string-to-float conversion edge cases."""

    def test_non_numeric_flow_produces_unknown(self):
        """When flow_level is a non-numeric string, indicator should be Unknown."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="N/A",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # No indicator should appear for non-numeric flow
        assert "● Runnable" not in html
        assert "● Too Low" not in html
        assert "● Too High" not in html

    def test_empty_string_flow_produces_unknown(self):
        """When flow_level is empty string, no indicator should appear."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        assert "● Runnable" not in html
        assert "● Too Low" not in html
        assert "● Too High" not in html

    def test_text_with_units_flow_produces_unknown(self):
        """When flow_level has text like '100 cfs', float conversion should fail gracefully."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=50.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="100 cfs",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # "100 cfs" is not convertible to float, so no indicator
        assert "● Runnable" not in html
        assert "● Too Low" not in html
        assert "● Too High" not in html

    def test_numeric_flow_produces_indicator(self):
        """When flow_level is a valid numeric string, indicator should appear."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="250",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # Should show Runnable (250 is within [100, 500])
        assert "● Runnable" in html


class TestIndicatorUsesInlineStyles:
    """6.3: Unit test verifying indicator HTML uses inline style= attributes."""

    def test_runnable_indicator_uses_inline_style(self):
        """Runnable indicator must use style= attribute, not CSS classes."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="250",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # Must use inline style
        assert 'style="color: #2e7d32; font-weight: bold;"' in html
        # Must NOT use class-based styling for the indicator
        assert 'class="runnable"' not in html
        assert 'class="indicator"' not in html

    def test_too_low_indicator_uses_inline_style(self):
        """Too Low indicator must use style= attribute, not CSS classes."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=500.0,
            rmax=1000.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="100",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # Must use inline style with red color
        assert 'style="color: #c62828; font-weight: bold;"' in html
        assert "● Too Low" in html

    def test_too_high_indicator_uses_inline_style(self):
        """Too High indicator must use style= attribute, not CSS classes."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="1000",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # Must use inline style with red color
        assert 'style="color: #c62828; font-weight: bold;"' in html
        assert "● Too High" in html

    def test_indicator_rendered_as_span_element(self):
        """The indicator must be rendered as a <span> element with inline style."""
        resolved = ResolvedReach(
            reach_id=1,
            reach_name="Test River",
            gauge_id="12345",
            rmin=100.0,
            rmax=500.0,
        )
        gauge_entry = GaugeEntry(
            gauge_number="12345",
            gauge_name="Test Gauge",
            usgs_page_url="https://waterdata.usgs.gov/monitoring-location/USGS-12345/",
            reading_datetime="2025-01-15T08:00:00.000-08:00",
            flow_level="250",
        )

        builder = ReportBuilder()
        html = builder._render_reach_entry(resolved, gauge_entry)

        # Check it's a span with style
        assert '<span style="color: #2e7d32; font-weight: bold;"> ● Runnable</span>' in html
