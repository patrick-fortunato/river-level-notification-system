"""Google Sheet reader for subscriber preferences."""

import gspread
from google.oauth2.service_account import Credentials

from src.config import Config
from src.models import Subscriber


# Expected header labels (case-insensitive comparison)
EXPECTED_HEADER_COL_A = "email"
EXPECTED_HEADER_COL_B = "include gauges"

# Google Sheets API scopes required for read-only access
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetReader:
    """Reads subscriber emails and inclusion lists from a Google Sheet."""

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

    def get_subscribers(self) -> list[Subscriber]:
        """
        Read subscriber rows (row 2+) and return parsed Subscriber objects.

        Each subscriber has an email (col A) and an optional comma-separated
        inclusion list of gauge numbers (col B). Rows with empty/blank email
        in column A are skipped. An empty inclusion list means receive all gauges.
        """
        worksheet = self._get_worksheet()
        all_values = worksheet.get_all_values()

        subscribers: list[Subscriber] = []

        # Skip header row (index 0), process data rows (index 1+)
        for row in all_values[1:]:
            email = row[0].strip() if len(row) > 0 else ""

            # Skip rows with empty/blank email
            if not email:
                continue

            # Parse inclusion list from column B
            inclusion_raw = row[1].strip() if len(row) > 1 else ""
            included_gauges = _parse_gauge_list(inclusion_raw)

            subscribers.append(
                Subscriber(email=email, included_gauges=included_gauges)
            )

        return subscribers

    def validate_structure(self) -> bool:
        """
        Validate that the sheet is accessible and has the expected header row.

        Returns True if structure is valid, raises an exception otherwise.
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


def _parse_gauge_list(raw_value: str) -> list[str]:
    """
    Parse a comma-separated string of gauge numbers into a list.

    Empty/blank input returns an empty list (meaning receive all gauges).
    Whitespace around each gauge number is stripped. Empty entries from
    consecutive commas are ignored.
    """
    if not raw_value:
        return []

    return [
        gauge.strip()
        for gauge in raw_value.split(",")
        if gauge.strip()
    ]
