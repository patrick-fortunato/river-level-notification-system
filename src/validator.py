"""Configuration validator for startup checks.

Validates that all required credential files exist and are readable,
and that the Google Sheet is accessible with the expected structure.
"""

import os

import gspread
from google.oauth2.service_account import Credentials

from src.config import Config
from src.sheet_reader import EXPECTED_HEADER_COL_A, EXPECTED_HEADER_COL_B


# Google Sheets API scopes required for validation (read-only)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class ConfigValidator:
    """Validates all configuration at startup before pipeline execution.

    Checks that credential files exist and are readable, and that the
    Google Sheet is accessible with the expected header row structure.
    """

    def __init__(self, config: Config):
        self._config = config

    def validate_all(self) -> list[str]:
        """Validate all configuration.

        Returns:
            A list of error messages. An empty list means all checks passed.
        """
        errors: list[str] = []

        # Check required credential files
        file_checks = [
            (self._config.service_account_file, "Service account credentials"),
            (self._config.gmail_token_file, "Gmail OAuth token"),
            (self._config.gmail_client_secrets_file, "Gmail client secrets"),
        ]

        for path, description in file_checks:
            error = self._check_file_exists(path, description)
            if error:
                errors.append(error)

        # Only check sheet accessibility if the service account file exists
        # (we need it to authenticate)
        if not any(
            e.startswith("Service account credentials")
            for e in errors
        ):
            error = self._check_sheet_accessible()
            if error:
                errors.append(error)

        return errors

    def _check_file_exists(self, path: str, description: str) -> str | None:
        """Check that a file exists and is readable.

        Args:
            path: File path to check.
            description: Human-readable description of the file's purpose.

        Returns:
            An error message string if the check fails, or None if it passes.
        """
        if not os.path.exists(path):
            return f"{description} file not found: {path}"

        if not os.path.isfile(path):
            return f"{description} path is not a file: {path}"

        if not os.access(path, os.R_OK):
            return f"{description} file is not readable: {path}"

        return None

    def _check_sheet_accessible(self) -> str | None:
        """Verify the Google Sheet is reachable and has the expected structure.

        Checks that the sheet can be opened and that the header row has
        'Email' in column A and 'Include Gauges' in column B.

        Returns:
            An error message string if the check fails, or None if it passes.
        """
        try:
            credentials = Credentials.from_service_account_file(
                self._config.service_account_file, scopes=SCOPES
            )
            client = gspread.authorize(credentials)
            spreadsheet = client.open_by_key(self._config.spreadsheet_id)
            worksheet = spreadsheet.sheet1
            header_row = worksheet.row_values(1)
        except FileNotFoundError:
            return (
                f"Service account file not found when accessing sheet: "
                f"{self._config.service_account_file}"
            )
        except Exception as e:
            return f"Google Sheet is not accessible: {e}"

        # Validate header structure
        if len(header_row) < 2:
            return (
                f"Google Sheet header row must have at least 2 columns, "
                f"found {len(header_row)}"
            )

        col_a = header_row[0].strip().lower()
        col_b = header_row[1].strip().lower()

        if col_a != EXPECTED_HEADER_COL_A:
            return (
                f"Google Sheet column A header must be "
                f"'{EXPECTED_HEADER_COL_A}', found '{header_row[0].strip()}'"
            )

        if col_b != EXPECTED_HEADER_COL_B:
            return (
                f"Google Sheet column B header must be "
                f"'{EXPECTED_HEADER_COL_B}', found '{header_row[1].strip()}'"
            )

        return None
