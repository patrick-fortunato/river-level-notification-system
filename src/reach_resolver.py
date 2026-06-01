"""Reach resolver for the River Level Notification System.

Resolves AW reach IDs to reach names and associated USGS gauge IDs
by querying the American Whitewater GraphQL API. Uses ReachCache for
TTL-based caching and stale fallback when the API is unreachable.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Protocol

import requests

from src.config import Config
from src.models import ResolvedReach

if TYPE_CHECKING:
    from src.reach_cache import ReachCache

logger = logging.getLogger(__name__)


class ReachCacheProtocol(Protocol):
    """Protocol for reach cache interface."""

    def get_reach(self, reach_id: int) -> ResolvedReach | None: ...
    def put_reach(self, reach_id: int, resolved: ResolvedReach) -> None: ...
    def get_stale_reach(self, reach_id: int) -> ResolvedReach | None: ...


class ReachResolver:
    """Resolves reach IDs to names and USGS gauge associations via AW API."""

    def __init__(
        self, config: Config, http_client: requests.Session, cache: ReachCacheProtocol
    ) -> None:
        """Initialize the resolver.

        Args:
            config: Application configuration with AW API settings.
            http_client: A requests.Session for making HTTP calls.
            cache: ReachCache instance for per-reach caching.
        """
        self._config = config
        self._http_client = http_client
        self._cache = cache

    def resolve_reaches(self, reach_ids: list[int]) -> dict[int, ResolvedReach]:
        """Resolve a list of reach IDs to ResolvedReach objects.

        Checks cache first for each reach ID. Queries the AW API for cache
        misses. Updates cache with fresh results. Marks unreachable reaches
        as unresolvable (logs error, does not halt).

        Args:
            reach_ids: List of AW reach IDs to resolve.

        Returns:
            Mapping of reach_id -> ResolvedReach for successfully resolved reaches.
        """
        results: dict[int, ResolvedReach] = {}

        for reach_id in reach_ids:
            # Check cache first
            cached = self._cache.get_reach(reach_id)
            if cached is not None:
                results[reach_id] = cached
                continue

            # Cache miss — query AW API
            try:
                resolved = self._query_reach(reach_id)
                self._cache.put_reach(reach_id, resolved)
                results[reach_id] = resolved
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException,
            ) as exc:
                logger.error(
                    "AW API unreachable for reach %d: %s", reach_id, exc
                )
                # Attempt stale cache fallback
                stale = self._cache.get_stale_reach(reach_id)
                if stale is not None:
                    logger.warning(
                        "Using stale cache for reach %d", reach_id
                    )
                    results[reach_id] = stale
                else:
                    logger.error(
                        "Reach %d unresolvable: no cache fallback available",
                        reach_id,
                    )
            except ReachResolverError as exc:
                logger.error("Failed to resolve reach %d: %s", reach_id, exc)
                # Attempt stale cache fallback
                stale = self._cache.get_stale_reach(reach_id)
                if stale is not None:
                    logger.warning(
                        "Using stale cache for reach %d", reach_id
                    )
                    results[reach_id] = stale
                else:
                    logger.error(
                        "Reach %d unresolvable: no cache fallback available",
                        reach_id,
                    )

            # Rate-limit between API calls
            time.sleep(self._config.aw_request_delay)

        return results

    def _query_reach(self, reach_id: int) -> ResolvedReach:
        """Query AW API for a single reach's name and gauge associations.

        Uses two GraphQL queries combined in a single request:
        - `reach(id: N)` for river, section, altname fields
        - `getGaugeInformationForReachID(id: N)` for gauge associations

        Args:
            reach_id: The AW reach ID to query.

        Returns:
            A ResolvedReach with the reach name and optional USGS gauge ID.

        Raises:
            ReachResolverError: If the API returns an error or malformed data.
            requests.exceptions.ConnectionError: If the API is unreachable.
            requests.exceptions.Timeout: If the request times out.
        """
        query = (
            "{ reach(id: %d) { river section altname states { shortkey } } "
            "getGaugeInformationForReachID(id: %d) "
            "{ gauges { gauge { source source_id } } } }"
            % (reach_id, reach_id)
        )

        response = self._http_client.post(
            self._config.aw_graphql_url,
            json={"query": query},
            timeout=self._config.aw_request_timeout,
        )

        if response.status_code >= 400:
            raise ReachResolverError(
                f"HTTP {response.status_code} for reach {reach_id}: "
                f"{response.text[:200]}"
            )

        try:
            json_data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise ReachResolverError(
                f"Malformed JSON for reach {reach_id}: {exc}"
            ) from exc

        if "errors" in json_data:
            error_msg = json_data["errors"][0].get("message", "Unknown error")
            raise ReachResolverError(
                f"GraphQL error for reach {reach_id}: {error_msg}"
            )

        try:
            reach_data = json_data["data"]["reach"]
            if reach_data is None:
                raise ReachResolverError(
                    f"Reach {reach_id} not found in AW API"
                )
        except (KeyError, TypeError) as exc:
            raise ReachResolverError(
                f"Malformed response for reach {reach_id}: {exc}"
            ) from exc

        reach_name = self._extract_reach_name(reach_data)

        # Extract state from states array (first entry's shortkey)
        states_list = reach_data.get("states") or []
        if states_list and isinstance(states_list, list):
            first_state = states_list[0].get("shortkey") if isinstance(states_list[0], dict) else None
            state = first_state if first_state else None
        else:
            state = None

        # Extract gauge information
        gauge_info = json_data.get("data", {}).get("getGaugeInformationForReachID")
        gauges_list = (gauge_info.get("gauges") or []) if gauge_info else []
        gauges = []
        for item in gauges_list:
            gauge = item.get("gauge")
            if gauge and "source" in gauge and "source_id" in gauge:
                gauges.append(gauge)

        gauge_id = self._extract_usgs_gauge(gauges)

        return ResolvedReach(
            reach_id=reach_id,
            reach_name=reach_name,
            gauge_id=gauge_id,
            state=state,
        )

    def _extract_reach_name(self, reach_data: dict) -> str:
        """Combine river, section, altname into display name.

        Format: "River - Section (Altname)"
        - Joins river and section with " - "
        - Appends " (altname)" if altname is present

        Args:
            reach_data: Dict with river, section, altname fields.

        Returns:
            The formatted reach name string.
        """
        river = (reach_data.get("river") or "").strip()
        section = (reach_data.get("section") or "").strip()
        altname = (reach_data.get("altname") or "").strip()

        name_parts = []
        if river:
            name_parts.append(river)
        if section:
            name_parts.append(section)

        reach_name = " - ".join(name_parts)
        if altname:
            reach_name += f" ({altname})"

        return reach_name

    def _extract_usgs_gauge(self, gauges: list[dict]) -> str | None:
        """Return source_id of first gauge with source='usgs', or None.

        Args:
            gauges: List of gauge dicts with 'source' and 'source_id' fields.

        Returns:
            The source_id string of the first USGS gauge, or None if none found.
        """
        for gauge in gauges:
            source = gauge.get("source", "")
            if source.lower() == "usgs":
                return gauge.get("source_id")
        return None


class ReachResolverError(Exception):
    """Raised when reach resolution fails due to API or data issues."""
