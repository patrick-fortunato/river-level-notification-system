"""Report builder for the River Level Notification System.

Builds personalized HTML email reports organized by state and reach. Reaches
are grouped under state headings (full state names, alphabetically ordered),
with an "Other" group for reaches lacking state data appearing last. Each
reach entry shows the reach name linked to its AW page, flow data when
available, and a USGS gauge link when a gauge is associated.
"""

from collections import OrderedDict
from datetime import datetime

from src.__version__ import __version__
from src.config import STATE_NAMES
from src.models import (
    GaugeEntry,
    ReachSubscriber,
    ResolvedReach,
    RunnabilityStatus,
    classify_runnability,
)


def _format_reading_datetime(raw_datetime: str) -> str:
    """Format a USGS datetime string into a human-readable format.

    Converts ISO 8601 format (e.g., '2025-01-15T08:00:00.000-08:00')
    into 'Wed, Jan 15 8:00 AM' format.

    Falls back to the raw string if parsing fails.
    """
    try:
        dt = datetime.fromisoformat(raw_datetime)
        # Use %I:%M %p then strip leading zero for cross-platform compatibility
        time_part = dt.strftime("%I:%M %p").lstrip("0")
        date_part = dt.strftime("%a, %b %d")
        return f"{date_part} {time_part}"
    except (ValueError, TypeError):
        return raw_datetime


class ReportBuilder:
    """Builds personalized HTML email reports for subscribers."""

    def build_report(
        self,
        subscriber: ReachSubscriber,
        resolved_reaches: dict[int, ResolvedReach],
        gauge_data: dict[str, GaugeEntry],
    ) -> str | None:
        """Build an HTML report for a subscriber, grouped by state.

        Iterates subscriber's reach_ids in order, groups reaches by state,
        sorts groups alphabetically by full state name (with "Other" last),
        and renders each group with a state heading followed by reach entries.

        Args:
            subscriber: The subscriber with their ordered reach IDs.
            resolved_reaches: Dict mapping reach_id -> ResolvedReach.
            gauge_data: Dict mapping gauge_number -> GaugeEntry.

        Returns:
            HTML string of the report, or None if no reaches could be rendered.
        """
        # Step 1: Collect (state, resolved, gauge_entry) tuples in subscriber order
        reach_tuples: list[tuple[str | None, ResolvedReach, GaugeEntry | None]] = []

        for reach_id in subscriber.reach_ids:
            resolved = resolved_reaches.get(reach_id)
            if resolved is None:
                continue

            gauge_entry = None
            if resolved.gauge_id and resolved.gauge_id in gauge_data:
                gauge_entry = gauge_data[resolved.gauge_id]

            reach_tuples.append((resolved.state, resolved, gauge_entry))

        if not reach_tuples:
            return None

        # Step 2: Group by state, preserving subscriber order within each group
        groups: OrderedDict[str | None, list[tuple[ResolvedReach, GaugeEntry | None]]] = OrderedDict()
        for state, resolved, gauge_entry in reach_tuples:
            if state not in groups:
                groups[state] = []
            groups[state].append((resolved, gauge_entry))

        # Step 3: Sort groups alphabetically by full state name, "Other" last
        def state_sort_key(state: str | None) -> tuple[int, str]:
            if state is None:
                return (1, "")  # "Other" goes last
            full_name = STATE_NAMES.get(state, state)
            return (0, full_name)

        sorted_states = sorted(groups.keys(), key=state_sort_key)

        # Step 4: Render each group with heading + reach entries
        all_html_parts: list[str] = []
        for state in sorted_states:
            # Render state heading
            if state is None:
                heading_text = "Other"
            else:
                heading_text = STATE_NAMES.get(state, state)

            all_html_parts.append(
                f'    <h2 class="state-heading">{heading_text}</h2>'
            )

            # Render reach entries within this group
            for resolved, gauge_entry in groups[state]:
                all_html_parts.append(
                    self._render_reach_entry(resolved, gauge_entry)
                )

        reach_entries_html = "\n".join(all_html_parts)
        footer_html = self._render_footer(__version__)

        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            '  <meta charset="utf-8">\n'
            "  <style>\n"
            "    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; "
            "background-color: #f5f5f5; }\n"
            "    .container { max-width: 700px; margin: 0 auto; "
            "background-color: #ffffff; padding: 20px; border-radius: 5px; }\n"
            "    .state-heading { font-size: 20px; color: #333333; "
            "margin-top: 24px; margin-bottom: 8px; padding-bottom: 4px; "
            "border-bottom: 2px solid #1a73e8; }\n"
            "    .reach-entry { border-bottom: 1px solid #e0e0e0; padding: 12px 0; }\n"
            "    .reach-entry:last-child { border-bottom: none; }\n"
            "    .reach-name { font-size: 16px; font-weight: bold; margin-bottom: 4px; }\n"
            "    .reach-name a { color: #1a73e8; text-decoration: none; }\n"
            "    .reach-name a:hover { text-decoration: underline; }\n"
            "    .reach-details { font-size: 14px; color: #555555; }\n"
            "    .gauge-link { font-size: 13px; margin-top: 4px; }\n"
            "    .gauge-link a { color: #1a73e8; text-decoration: none; }\n"
            "    .gauge-link a:hover { text-decoration: underline; }\n"
            "    .no-gauge { font-size: 14px; color: #999999; font-style: italic; }\n"
            "    .footer { margin-top: 20px; padding-top: 12px; "
            "border-top: 1px solid #e0e0e0; font-size: 12px; color: #999999; "
            "text-align: center; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            '  <div class="container">\n'
            f"{reach_entries_html}\n"
            f"{footer_html}\n"
            "  </div>\n"
            "</body>\n"
            "</html>"
        )

        return html

    def _render_reach_entry(
        self, resolved: ResolvedReach, gauge_entry: GaugeEntry | None
    ) -> str:
        """Render a single reach entry as HTML.

        Args:
            resolved: The resolved reach with name and optional gauge ID.
            gauge_entry: The gauge reading data, or None if unavailable.

        Returns:
            HTML string for the reach entry.
        """
        aw_url = resolved.aw_url

        # Primary heading: reach name linked to AW page
        name_html = (
            f'      <div class="reach-name">'
            f'<a href="{aw_url}">{resolved.reach_name}</a></div>'
        )

        # Flow data and gauge link
        if gauge_entry is not None:
            formatted_datetime = _format_reading_datetime(
                gauge_entry.reading_datetime
            )

            # Determine runnability indicator for USGS reaches
            try:
                flow_value = float(gauge_entry.flow_level)
            except (ValueError, TypeError):
                flow_value = None
            status = classify_runnability(flow_value, resolved.rmin, resolved.rmax)
            indicator_html = self._render_runnability_indicator(status)

            details_html = (
                f'      <div class="reach-details">'
                f"<b>Flow:</b> {gauge_entry.flow_level} cfs | "
                f"<b>Reading:</b> {formatted_datetime}</div>"
            )

            # Runnability indicator on its own line
            indicator_line = ""
            if indicator_html:
                indicator_line = f"\n      <div>{indicator_html}</div>"

            # USGS gauge link
            gauge_link_html = ""
            if resolved.gauge_id:
                usgs_url = gauge_entry.usgs_page_url
                gauge_link_html = (
                    f'\n      <div class="gauge-link">'
                    f'<a href="{usgs_url}">USGS Gauge {resolved.gauge_id}</a></div>'
                )

            return (
                f'    <div class="reach-entry">\n'
                f"{name_html}\n"
                f"{details_html}"
                f"{indicator_line}"
                f"{gauge_link_html}\n"
                f"    </div>"
            )
        elif resolved.aw_flow_data is not None:
            # AW flow data fallback (no USGS gauge, but AW provides flow info)
            aw_data = resolved.aw_flow_data

            # Determine runnability indicator for AW fallback reaches
            status = classify_runnability(aw_data.reading, resolved.rmin, resolved.rmax)
            indicator_html = self._render_runnability_indicator(status)

            details_html = (
                f'      <div class="reach-details">'
                f"<b>Flow:</b> {aw_data.reading} {aw_data.unit} | "
                f"<b>Source:</b> {aw_data.gauge_name} (via AW)</div>"
            )

            # Runnability indicator on its own line
            indicator_line = ""
            if indicator_html:
                indicator_line = f"\n      <div>{indicator_html}</div>"

            return (
                f'    <div class="reach-entry">\n'
                f"{name_html}\n"
                f"{details_html}"
                f"{indicator_line}\n"
                f"    </div>"
            )
        else:
            # No gauge data available at all
            no_gauge_html = (
                f'      <div class="no-gauge">No gauge data available</div>'
            )
            return (
                f'    <div class="reach-entry">\n'
                f"{name_html}\n"
                f"{no_gauge_html}\n"
                f"    </div>"
            )

    def _render_footer(self, version: str) -> str:
        """Render the email footer with the application version number.

        Args:
            version: The application version string.

        Returns:
            HTML string for the footer.
        """
        return (
            f'    <div class="footer">\n'
            f"      River Level Notification System v{version}\n"
            f"    </div>"
        )

    def _render_runnability_indicator(self, status: RunnabilityStatus) -> str:
        """Render a runnability indicator HTML span with inline CSS.

        Args:
            status: The runnability classification status.

        Returns:
            HTML span string for the indicator, or empty string if UNKNOWN.
        """
        if status == RunnabilityStatus.UNKNOWN:
            return ""
        color = "#2e7d32" if status == RunnabilityStatus.RUNNABLE else "#c62828"
        return f'<span style="color: {color}; font-weight: bold;"> ● {status.value}</span>'
