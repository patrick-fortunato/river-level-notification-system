"""Report builder for the River Level Notification System.

Builds personalized HTML email reports by including gauges based on
the subscriber's inclusion list (empty = all gauges).
"""

from datetime import datetime

from src.__version__ import __version__
from src.config import STATE_NAMES
from src.models import GaugeEntry, GroupedSubscriber, Subscriber


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
        self, subscriber: Subscriber, gauge_data: dict[str, GaugeEntry]
    ) -> str | None:
        """Build an HTML report for a subscriber.

        Includes gauges from gauge_data based on the subscriber's included_gauges
        list. If the list is empty, all gauges are included.

        Args:
            subscriber: The subscriber with inclusion preferences.
            gauge_data: Dict mapping gauge_number -> GaugeEntry for all gauges.

        Returns:
            HTML string of the report, or None if no gauges match
            or no data is available.
        """
        if not gauge_data:
            return None

        # Filter to included gauges (empty list = include all)
        if subscriber.included_gauges:
            included_gauges = {
                number: entry
                for number, entry in gauge_data.items()
                if number in subscriber.included_gauges
            }
        else:
            included_gauges = dict(gauge_data)

        if not included_gauges:
            return None

        # Build the HTML report
        gauge_entries_html = "\n".join(
            self._render_gauge_entry(number, entry)
            for number, entry in included_gauges.items()
        )

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
            "    .gauge-entry { border-bottom: 1px solid #e0e0e0; padding: 12px 0; }\n"
            "    .gauge-entry:last-child { border-bottom: none; }\n"
            "    .gauge-name { font-size: 16px; font-weight: bold; margin-bottom: 4px; }\n"
            "    .gauge-name a { color: #1a73e8; text-decoration: none; }\n"
            "    .gauge-name a:hover { text-decoration: underline; }\n"
            "    .gauge-details { font-size: 14px; color: #555555; }\n"
            "    .footer { margin-top: 20px; padding-top: 12px; "
            "border-top: 1px solid #e0e0e0; font-size: 12px; color: #999999; "
            "text-align: center; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            '  <div class="container">\n'
            f"{gauge_entries_html}\n"
            f"{footer_html}\n"
            "  </div>\n"
            "</body>\n"
            "</html>"
        )

        return html

    def build_consolidated_report(
        self,
        grouped_subscriber: GroupedSubscriber,
        state_gauge_data: dict[str, dict[str, GaugeEntry]],
    ) -> str | None:
        """Build a consolidated HTML report with state sections.

        Produces one state section per unique state that has matching gauge data.
        Each state section starts with a visible heading (full state name).
        State sections are ordered alphabetically by full state name.
        Skips states with no matching gauges (no empty sections).
        Returns None if all states produce no content.

        Args:
            grouped_subscriber: The grouped subscriber with state preferences.
            state_gauge_data: Dict mapping state_code -> {gauge_number -> GaugeEntry}.

        Returns:
            HTML string with state sections, or None if no content for any state.
        """
        # Build state sections, collecting (full_state_name, html) pairs
        state_sections: list[tuple[str, str]] = []

        for pref in grouped_subscriber.state_preferences:
            gauges_for_state = state_gauge_data.get(pref.state_code)
            if not gauges_for_state:
                continue

            # Apply gauge inclusion filtering
            if pref.included_gauges:
                filtered_gauges = {
                    number: entry
                    for number, entry in gauges_for_state.items()
                    if number in pref.included_gauges
                }
            else:
                filtered_gauges = dict(gauges_for_state)

            if not filtered_gauges:
                continue

            # Resolve full state name
            full_state_name = STATE_NAMES.get(
                pref.state_code, pref.state_code
            )

            # Render gauge entries for this state
            gauge_entries_html = "\n".join(
                self._render_gauge_entry(number, entry)
                for number, entry in filtered_gauges.items()
            )

            section_html = (
                f'    <div class="state-section">\n'
                f'      <h2 class="state-heading">{full_state_name}</h2>\n'
                f"{gauge_entries_html}\n"
                f"    </div>"
            )

            state_sections.append((full_state_name, section_html))

        if not state_sections:
            return None

        # Sort alphabetically by full state name
        state_sections.sort(key=lambda x: x[0])

        sections_html = "\n".join(html for _, html in state_sections)
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
            "    .state-section { margin-bottom: 20px; }\n"
            "    .state-heading { font-size: 20px; color: #333333; "
            "border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }\n"
            "    .gauge-entry { border-bottom: 1px solid #e0e0e0; padding: 12px 0; }\n"
            "    .gauge-entry:last-child { border-bottom: none; }\n"
            "    .gauge-name { font-size: 16px; font-weight: bold; margin-bottom: 4px; }\n"
            "    .gauge-name a { color: #1a73e8; text-decoration: none; }\n"
            "    .gauge-name a:hover { text-decoration: underline; }\n"
            "    .gauge-details { font-size: 14px; color: #555555; }\n"
            "    .footer { margin-top: 20px; padding-top: 12px; "
            "border-top: 1px solid #e0e0e0; font-size: 12px; color: #999999; "
            "text-align: center; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            '  <div class="container">\n'
            f"{sections_html}\n"
            f"{footer_html}\n"
            "  </div>\n"
            "</body>\n"
            "</html>"
        )

        return html

    def _render_gauge_entry(self, gauge_number: str, entry: GaugeEntry) -> str:
        """Render a single gauge entry as HTML.

        Args:
            gauge_number: The USGS gauge number.
            entry: The GaugeEntry with gauge data.

        Returns:
            HTML string for the gauge entry.
        """
        formatted_datetime = _format_reading_datetime(entry.reading_datetime)
        return (
            '    <div class="gauge-entry">\n'
            f'      <div class="gauge-name">'
            f'<a href="{entry.usgs_page_url}">{entry.gauge_name}</a></div>\n'
            f'      <div class="gauge-details">'
            f"<b>Gauge:</b> {gauge_number} | "
            f"<b>Reading:</b> {formatted_datetime} | "
            f"<b>Flow:</b> {entry.flow_level} cfs</div>\n"
            "    </div>"
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
