"""American Whitewater API client for the River Level Notification System."""

import logging
import time

import requests

from src.config import Config
from src.models import Reach

logger = logging.getLogger(__name__)


# Mapping from 2-letter US state codes to AW GMI codes used by the GraphQL API.
# AW uses a "USA-XXX" format where XXX is a 3-letter abbreviation.
STATE_CODE_TO_GMI: dict[str, str] = {
    "AL": "USA-ALA", "AK": "USA-ALK", "AZ": "USA-ARZ", "AR": "USA-ARK",
    "CA": "USA-CAL", "CO": "USA-COL", "CT": "USA-CON", "DE": "USA-DEL",
    "FL": "USA-FLO", "GA": "USA-GEO", "HI": "USA-HAW", "ID": "USA-IDA",
    "IL": "USA-ILL", "IN": "USA-IND", "IA": "USA-IOW", "KS": "USA-KAN",
    "KY": "USA-KEN", "LA": "USA-LOU", "ME": "USA-MAI", "MD": "USA-MAR",
    "MA": "USA-MAS", "MI": "USA-MIC", "MN": "USA-MIN", "MS": "USA-MIS",
    "MO": "USA-MSO", "MT": "USA-MON", "NE": "USA-NEB", "NV": "USA-NEV",
    "NH": "USA-NHA", "NJ": "USA-NJE", "NM": "USA-NME", "NY": "USA-NYO",
    "NC": "USA-NCA", "ND": "USA-NDA", "OH": "USA-OHI", "OK": "USA-OKL",
    "OR": "USA-ORE", "PA": "USA-PEN", "RI": "USA-RHI", "SC": "USA-SCA",
    "SD": "USA-SDA", "TN": "USA-TNN", "TX": "USA-TEX", "UT": "USA-UTA",
    "VT": "USA-VER", "VA": "USA-VIR", "WA": "USA-WSH", "WV": "USA-WVI",
    "WI": "USA-WIS", "WY": "USA-WYM", "DC": "USA-DIS",
}


class AWClientError(Exception):
    """Raised when AW API communication fails."""


class AWClient:
    """Fetches gauge-to-reach associations from the AW GraphQL API.

    Queries AW's GraphQL API to discover all reaches for given states,
    then queries gauge associations for each reach. The result is an
    inverted mapping from USGS gauge numbers to AW reaches.
    """

    def __init__(self, config: Config, http_client: requests.Session) -> None:
        """Initialize the client with configuration and an HTTP session.

        Args:
            config: Application configuration containing AW API settings.
            http_client: A requests.Session instance for making HTTP calls.
        """
        self._config = config
        self._http_client = http_client

    def fetch_reach_mapping(self, state_codes: list[str]) -> dict[str, list[Reach]]:
        """Fetch the complete gauge-to-reach mapping for the given states.

        Orchestrates the full fetch flow: gets reach IDs for each state,
        queries gauge associations for each reach, filters to USGS gauges,
        and inverts the mapping.

        Args:
            state_codes: List of US state codes (e.g., ["OR", "WA"]).

        Returns:
            Dict mapping USGS gauge number (str) to list of Reach objects.

        Raises:
            AWClientError: If the API is unreachable or returns errors.
        """
        reach_gauge_pairs: list[tuple[int, str, str, str]] = []

        for state_code in state_codes:
            reaches = self._fetch_reaches_for_state(state_code)
            logger.info(
                "Found %d reaches for state %s", len(reaches), state_code
            )

            for reach_id, reach_name in reaches:
                time.sleep(self._config.aw_request_delay)
                gauges = self._fetch_gauges_for_reach(reach_id)

                for gauge in gauges:
                    source = gauge.get("source", "")
                    source_id = gauge.get("source_id", "")
                    reach_gauge_pairs.append(
                        (reach_id, reach_name, source, source_id)
                    )

        return self._build_inverted_mapping(reach_gauge_pairs)

    def _fetch_reaches_for_state(
        self, state_code: str
    ) -> list[tuple[int, str]]:
        """Get all reach IDs and names for a state from AW's GraphQL API.

        Queries the AW GraphQL `reaches` endpoint with the state's GMI code,
        paginating through all results.

        Args:
            state_code: Two-letter US state code (e.g., "OR").

        Returns:
            List of (reach_id, reach_name) tuples for the given state.

        Raises:
            AWClientError: If the request fails or response is malformed.
        """
        gmi_code = STATE_CODE_TO_GMI.get(state_code.upper())
        if not gmi_code:
            logger.warning(
                "No AW GMI code mapping for state '%s', skipping", state_code
            )
            return []

        reaches: list[tuple[int, str]] = []
        page = 1
        page_size = 100

        while True:
            query = (
                '{ reaches(states: ["%s"], first: %d, page: %d) '
                "{ data { id river section altname } "
                "paginatorInfo { lastPage currentPage } } }"
                % (gmi_code, page_size, page)
            )

            try:
                response = self._http_client.post(
                    self._config.aw_graphql_url,
                    json={"query": query},
                    timeout=self._config.aw_request_timeout,
                )
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                raise AWClientError(
                    f"Network error fetching reaches for state "
                    f"{state_code}: {exc}"
                ) from exc

            if response.status_code >= 400:
                raise AWClientError(
                    f"HTTP {response.status_code} fetching reaches for state "
                    f"{state_code}: {response.text[:200]}"
                )

            try:
                json_data = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError) as exc:
                raise AWClientError(
                    f"Malformed JSON response fetching reaches for state "
                    f"{state_code}: {exc}"
                ) from exc

            if "errors" in json_data:
                error_msg = json_data["errors"][0].get(
                    "message", "Unknown error"
                )
                raise AWClientError(
                    f"GraphQL error fetching reaches for state "
                    f"{state_code}: {error_msg}"
                )

            try:
                reaches_data = json_data["data"]["reaches"]
                data_list = reaches_data["data"]
                paginator = reaches_data["paginatorInfo"]
            except (KeyError, TypeError) as exc:
                raise AWClientError(
                    f"Malformed response structure for state "
                    f"{state_code}: {exc}"
                ) from exc

            for item in data_list:
                reach_id = item.get("id")
                river = item.get("river", "")
                section = item.get("section", "")
                altname = item.get("altname", "")

                if not reach_id:
                    continue

                # Build reach name: "River - Section (Altname)" matching AW display
                name_parts = []
                if river:
                    name_parts.append(river)
                if section:
                    name_parts.append(section)
                reach_name = " - ".join(name_parts)
                if altname:
                    reach_name += f" ({altname})"

                if reach_name:
                    reaches.append((int(reach_id), reach_name))

            # Check if there are more pages
            current_page = paginator.get("currentPage", 1)
            last_page = paginator.get("lastPage", 1)
            if current_page >= last_page:
                break
            page += 1
            time.sleep(self._config.aw_request_delay)

        return reaches

    def _fetch_gauges_for_reach(self, reach_id: int) -> list[dict]:
        """Query AW GraphQL for gauge associations of a single reach.

        Args:
            reach_id: The AW reach ID to query.

        Returns:
            List of gauge dicts with 'source' and 'source_id' fields.

        Raises:
            AWClientError: If the request fails or response is malformed.
        """
        query = (
            "{ getGaugeInformationForReachID(id: %d) "
            "{ gauges { gauge { source source_id } } } }" % reach_id
        )

        try:
            response = self._http_client.post(
                self._config.aw_graphql_url,
                json={"query": query},
                timeout=self._config.aw_request_timeout,
            )
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as exc:
            raise AWClientError(
                f"Network error fetching gauges for reach {reach_id}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise AWClientError(
                f"HTTP {response.status_code} fetching gauges for reach "
                f"{reach_id}: {response.text[:200]}"
            )

        try:
            json_data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise AWClientError(
                f"Malformed JSON response for reach {reach_id}: {exc}"
            ) from exc

        # Check for GraphQL errors
        if "errors" in json_data:
            error_msg = json_data["errors"][0].get("message", "Unknown error")
            raise AWClientError(
                f"GraphQL error for reach {reach_id}: {error_msg}"
            )

        # Extract gauge data from the response
        try:
            gauge_info = json_data["data"]["getGaugeInformationForReachID"]
            if gauge_info is None:
                return []
            gauges_list = gauge_info.get("gauges") or []
            result = []
            for item in gauges_list:
                gauge = item.get("gauge")
                if gauge and "source" in gauge and "source_id" in gauge:
                    result.append(gauge)
            return result
        except (KeyError, TypeError, IndexError) as exc:
            raise AWClientError(
                f"Malformed response structure for reach {reach_id}: {exc}"
            ) from exc

    def _build_inverted_mapping(
        self, reach_gauge_pairs: list[tuple[int, str, str, str]]
    ) -> dict[str, list[Reach]]:
        """Invert reach→gauge pairs into gauge→reaches mapping.

        Filters to only include gauges where source is "usgs".

        Args:
            reach_gauge_pairs: List of (reach_id, reach_name, gauge_source,
                gauge_source_id) tuples.

        Returns:
            Dict mapping USGS gauge number to list of Reach objects.
        """
        mapping: dict[str, list[Reach]] = {}

        for reach_id, reach_name, gauge_source, gauge_source_id in reach_gauge_pairs:
            if gauge_source.lower() != "usgs":
                continue

            if gauge_source_id not in mapping:
                mapping[gauge_source_id] = []

            # Avoid duplicates: don't add the same reach twice for the same gauge
            reach = Reach(reach_id=reach_id, reach_name=reach_name)
            if not any(
                r.reach_id == reach_id for r in mapping[gauge_source_id]
            ):
                mapping[gauge_source_id].append(reach)

        return mapping
