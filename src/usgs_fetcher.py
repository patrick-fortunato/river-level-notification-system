"""USGS Water Services data fetcher for the River Level Notification System."""

import logging
import requests

from src.config import Config
from src.models import GaugeEntry
from src.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class USGSFetchError(Exception):
    """Raised when USGS data retrieval fails after all retries are exhausted."""


class USGSFetcher:
    """Fetches real-time river gauge data from the USGS Instantaneous Values API.

    Retrieves all gauge readings for a configured US state using the USGS
    Water Services REST API in JSON format.
    """

    def __init__(self, config: Config, http_client: requests.Session) -> None:
        """Initialize the fetcher with configuration and an HTTP client.

        Args:
            config: Application configuration containing USGS API settings.
            http_client: A requests.Session instance for making HTTP calls.
        """
        self._config = config
        self._http_client = http_client

    def _build_request_url(self) -> str:
        """Construct the USGS API URL with stateCd, parameterCd, and format parameters.

        Returns:
            The fully-formed USGS Instantaneous Values API URL.
        """
        params = (
            f"?stateCd={self._config.usgs_state_code}"
            f"&parameterCd={self._config.usgs_parameter_code}"
            f"&format={self._config.usgs_format}"
        )
        return f"{self._config.usgs_base_url}{params}"

    def _parse_response(self, json_data: dict) -> dict[str, GaugeEntry]:
        """Parse the USGS JSON response into GaugeEntry objects.

        Extracts gauge information from each time series entry in the response.
        Skips entries that are missing required fields rather than failing the
        entire parse.

        Args:
            json_data: The parsed JSON response from the USGS API.

        Returns:
            A dict mapping gauge_number to GaugeEntry for all successfully
            parsed time series entries.
        """
        gauge_data: dict[str, GaugeEntry] = {}

        time_series = json_data.get("value", {}).get("timeSeries", [])

        for series in time_series:
            try:
                source_info = series.get("sourceInfo", {})
                site_codes = source_info.get("siteCode", [])
                if not site_codes:
                    continue

                gauge_number = site_codes[0].get("value", "")
                if not gauge_number:
                    continue

                gauge_name = source_info.get("siteName", "")
                if not gauge_name:
                    continue

                usgs_page_url = (
                    f"https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_number}/"
                    f"#period=P7D&dataTypeId=continuous-00060-0&showMedian=true&showFieldMeasurements=true"
                )

                # Get the most recent reading from the values array
                values_list = series.get("values", [])
                if not values_list:
                    continue

                value_entries = values_list[0].get("value", [])
                if not value_entries:
                    continue

                # Use the last (most recent) value entry
                latest = value_entries[-1]
                reading_datetime = latest.get("dateTime", "")
                flow_level = latest.get("value", "")

                if not reading_datetime or not flow_level:
                    continue

                gauge_data[gauge_number] = GaugeEntry(
                    gauge_number=gauge_number,
                    gauge_name=gauge_name,
                    usgs_page_url=usgs_page_url,
                    reading_datetime=reading_datetime,
                    flow_level=flow_level,
                )
            except (IndexError, KeyError, TypeError):
                # Skip malformed entries
                continue

        return gauge_data

    def fetch_all_state_gauges(self) -> dict[str, GaugeEntry]:
        """Fetch current readings for all gauges in the configured state.

        Makes an HTTP GET request to the USGS API with retry logic for
        transient failures (timeouts, 5xx responses). Returns all gauge
        data for the configured state.

        Returns:
            A dict mapping gauge_number to GaugeEntry for all gauges in
            the configured state.

        Raises:
            USGSFetchError: If the request fails after all retries are
                exhausted or a permanent (4xx) error is encountered.
        """
        url = self._build_request_url()

        def _make_request() -> dict[str, GaugeEntry]:
            response = self._http_client.get(url, timeout=30)

            # Permanent client errors should not be retried
            if 400 <= response.status_code < 500:
                raise USGSFetchError(
                    f"USGS API returned client error {response.status_code}: "
                    f"{response.text[:200]}"
                )

            # Server errors are retryable — raise to trigger retry
            response.raise_for_status()

            json_data = response.json()
            return self._parse_response(json_data)

        try:
            return retry_with_backoff(
                operation=_make_request,
                max_retries=self._config.max_retries,
                initial_backoff=self._config.initial_backoff_seconds,
                multiplier=self._config.backoff_multiplier,
                retryable_exceptions=(
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError,
                ),
            )
        except USGSFetchError:
            # Re-raise permanent errors without wrapping
            raise
        except Exception as exc:
            raise USGSFetchError(
                f"Failed to fetch USGS data after {self._config.max_retries} "
                f"retries: {exc}"
            ) from exc

    def fetch_gauges_by_ids(self, gauge_ids: list[str]) -> dict[str, GaugeEntry]:
        """Fetch current readings for specific gauge IDs.

        Uses USGS API with sites= parameter instead of stateCd=.
        Returns mapping of gauge_number -> GaugeEntry.
        Skips gauges that return errors (does not halt pipeline).

        Args:
            gauge_ids: List of USGS gauge number strings to fetch.

        Returns:
            A dict mapping gauge_number -> GaugeEntry for all successfully
            fetched gauges.
        """
        if not gauge_ids:
            return {}

        sites_param = ",".join(gauge_ids)
        url = (
            f"{self._config.usgs_base_url}"
            f"?sites={sites_param}"
            f"&parameterCd={self._config.usgs_parameter_code}"
            f"&format={self._config.usgs_format}"
        )

        def _make_request() -> dict[str, GaugeEntry]:
            response = self._http_client.get(url, timeout=30)

            # Permanent client errors should not be retried
            if 400 <= response.status_code < 500:
                raise USGSFetchError(
                    f"USGS API returned client error {response.status_code}: "
                    f"{response.text[:200]}"
                )

            # Server errors are retryable — raise to trigger retry
            response.raise_for_status()

            json_data = response.json()
            return self._parse_response(json_data)

        try:
            return retry_with_backoff(
                operation=_make_request,
                max_retries=self._config.max_retries,
                initial_backoff=self._config.initial_backoff_seconds,
                multiplier=self._config.backoff_multiplier,
                retryable_exceptions=(
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError,
                ),
            )
        except USGSFetchError:
            # Log and return empty — do not halt pipeline
            logger.error(
                "USGS API returned a permanent error for gauges %s", sites_param
            )
            return {}
        except Exception as exc:
            logger.error(
                "Failed to fetch USGS data for gauges %s after %d retries: %s",
                sites_param,
                self._config.max_retries,
                exc,
            )
            return {}
