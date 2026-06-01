"""Google Sheet reader for subscriber reach ID preferences."""

import logging

import gspread
from google.oauth2.service_account import Credentials

from src.config import Config
from src.models import ReachSubscriber

logger = logging.getLogger(__name__)

# Expected header labels (case-insensitive comparison)
EXPECTED_HEADER_COL_A = "email"
EXPECTED_HEADER_COL_B = "reach ids"

# Google Sheets API scopes required for read-only access
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetReader:
    """Reads subscriber emails and reach IDs from a Google Sheet."""

    def __init__(self, config: Config):
        self._config = config
        self._client: gspread.Client | None = None
        self._sheet: gspread.Spreadsheet | None = None

    def authenticate(self) -> None:
        """Authenticate with Google Sheets using service account credentials."""
        credentials = Credentials.from_service_account_file(
            self._config.service_account_file, scopes=SCOPES
        )
        self._client = gspread.authorize(credentials)

    def get_subscribers(self) -> list[ReachSubscriber]:
        """Parse spreadsheet rows into ReachSubscriber objects.

        - Skips rows with blank email
        - Skips rows with empty Reach IDs (logs warning)
        - Parses comma-separated integers from column B
        - Skips non-integer values (logs warning)
        - Deduplicates reach IDs preserving first-occurrence order
        """
        worksheet = self._get_worksheet()
        all_values = worksheet.get_all_values()

        subscribers: list[ReachSubscriber] = []

        # Skip header row (index 0), process data rows (index 1+)
        for row in all_values[1:]:
            email = row[0].strip() if len(row) > 0 else ""

            # Skip rows with blank email (column A)
            if not email:
                continue

            # Get reach IDs raw value from column B
            reach_ids_raw = row[1].strip() if len(row) > 1 else ""

            # Skip rows with empty Reach IDs column (log warning)
            if not reach_ids_raw:
                logger.warning(
                    "Skipping subscriber '%s': empty Reach IDs column", email
                )
                continue

            # Parse comma-separated integers with whitespace trimming
            reach_ids = _parse_reach_ids(reach_ids_raw, email)

            # If no valid reach IDs were parsed, skip the subscriber
            if not reach_ids:
                logger.warning(
                    "Skipping subscriber '%s': no valid reach IDs found", email
                )
                continue

            subscribers.append(
                ReachSubscriber(email=email, reach_ids=reach_ids)
            )

        return subscribers

    def validate_structure(self) -> bool:
        """Validate header row: 'Email' (A), 'Reach IDs' (B).

        Returns True if structure is valid, raises SheetStructureError otherwise.
        """
        worksheet = self._get_worksheet()
        header_row = worksheet.row_values(1)

        if len(header_row) < 2:
            raise SheetStructureError(
                f"Header row must have at least 2 columns, found {len(header_row)}"
            )

        col_a = header_row[0].strip().lower()
        col_b = header_row[1].strip().lower()

        if col_a != EXPECTED_HEADER_COL_A:
            raise SheetStructureError(
                f"Column A header must be '{EXPECTED_HEADER_COL_A}', "
                f"found '{header_row[0].strip()}'"
            )

        if col_b != EXPECTED_HEADER_COL_B:
            raise SheetStructureError(
                f"Column B header must be '{EXPECTED_HEADER_COL_B}', "
                f"found '{header_row[1].strip()}'"
            )

        return True

    def _get_worksheet(self) -> gspread.Worksheet:
        """Get the first worksheet from the configured spreadsheet."""
        if self._client is None:
            raise RuntimeError(
                "SheetReader not authenticated. Call authenticate() first."
            )

        if self._sheet is None:
            self._sheet = self._client.open_by_key(self._config.spreadsheet_id)

        return self._sheet.sheet1


class SheetStructureError(Exception):
    """Raised when the Google Sheet does not have the expected structure."""

    pass


def _parse_reach_ids(raw_value: str, email: str) -> list[int]:
    """Parse a comma-separated string of reach IDs into a deduplicated list.

    - Splits on commas and trims whitespace from each token
    - Skips non-integer values (logs warning with email context)
    - Deduplicates preserving first-occurrence order
    """
    reach_ids: list[int] = []
    seen: set[int] = set()

    for token in raw_value.split(","):
        token = token.strip()
        if not token:
            continue

        try:
            reach_id = int(token)
        except ValueError:
            logger.warning(
                "Skipping invalid reach ID '%s' for subscriber '%s'",
                token,
                email,
            )
            continue

        if reach_id not in seen:
            seen.add(reach_id)
            reach_ids.append(reach_id)

    return reach_ids
