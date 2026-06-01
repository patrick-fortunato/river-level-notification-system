"""Email grouping logic for consolidating subscriber rows by email address."""

from collections import defaultdict

from src.models import GroupedSubscriber, StatePreference, Subscriber


def merge_gauge_lists(gauge_lists: list[list[str]]) -> list[str]:
    """Merge multiple gauge inclusion lists for the same state.

    If any list is empty (meaning 'all gauges'), returns empty.
    Otherwise returns the sorted union of all lists.

    Args:
        gauge_lists: List of gauge inclusion lists to merge.

    Returns:
        Merged gauge list. Empty means include all gauges.
    """
    if any(len(gl) == 0 for gl in gauge_lists):
        return []
    merged: set[str] = set()
    for gl in gauge_lists:
        merged.update(gl)
    return sorted(merged)


class EmailGrouper:
    """Groups subscriber rows by email address for consolidated delivery."""

    def group_subscribers(
        self, subscribers: list[Subscriber]
    ) -> list[GroupedSubscriber]:
        """Group subscriber rows by case-insensitive email.

        Preserves original email casing from the first occurrence.
        Merges gauge lists for same-state rows using merge_gauge_lists.

        Args:
            subscribers: Raw subscriber rows from the sheet reader.

        Returns:
            List of GroupedSubscriber objects, one per unique email.
        """
        # Track email groups: key is lowercased email
        # Value is (original_email, dict of state_code -> list of gauge lists)
        groups: dict[str, tuple[str, dict[str, list[list[str]]]]] = {}

        for sub in subscribers:
            key = sub.email.lower()
            if key not in groups:
                groups[key] = (sub.email, defaultdict(list))
            _, state_gauges = groups[key]
            state_gauges[sub.state_code].append(sub.included_gauges)

        result: list[GroupedSubscriber] = []
        for key, (original_email, state_gauges) in groups.items():
            state_preferences: list[StatePreference] = []
            for state_code, gauge_lists in state_gauges.items():
                merged = merge_gauge_lists(gauge_lists)
                state_preferences.append(
                    StatePreference(state_code=state_code, included_gauges=merged)
                )
            result.append(
                GroupedSubscriber(
                    email=original_email, state_preferences=state_preferences
                )
            )

        return result
