# Feature: river-level-notification-system, Property 9: Validation Failure Halts Pipeline
"""Property test for validation failure halting the pipeline.

Generates configurations with at least one missing/invalid file, verifies
validate_all returns non-empty error list and pipeline does not proceed
to data retrieval or email.

Validates: Requirements 12.3
"""

from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import Config
from src.pipeline import Pipeline
from src.validator import ConfigValidator


# Strategy for generating file paths that don't exist
nonexistent_path_strategy = st.from_regex(
    r"/tmp/nonexistent_[a-z]{5,10}_[0-9]{3,6}\.json", fullmatch=True
)


@settings(max_examples=100)
@given(
    sa_path=nonexistent_path_strategy,
    token_path=nonexistent_path_strategy,
    client_path=nonexistent_path_strategy,
)
def test_missing_files_produce_validation_errors(
    sa_path: str, token_path: str, client_path: str
):
    """Verify that missing credential files produce non-empty error list."""
    config = Config(
        service_account_file=sa_path,
        gmail_token_file=token_path,
        gmail_client_secrets_file=client_path,
        spreadsheet_id="fake_id",
    )

    validator = ConfigValidator(config)
    errors = validator.validate_all()

    # At least one error should be reported (all three files are missing)
    assert len(errors) >= 1
    # Should have errors for each missing file
    assert any("not found" in e for e in errors)


@settings(max_examples=50)
@given(
    sa_path=nonexistent_path_strategy,
)
def test_validation_failure_prevents_data_retrieval(sa_path: str):
    """Verify pipeline does not fetch data or send emails when validation fails."""
    config = Config(
        service_account_file=sa_path,
        gmail_token_file="/tmp/also_missing_token.json",
        gmail_client_secrets_file="/tmp/also_missing_client.json",
        spreadsheet_id="fake_id",
    )

    with patch("src.pipeline.USGSFetcher") as mock_fetcher_cls, \
         patch("src.pipeline.SheetReader") as mock_reader_cls, \
         patch("src.pipeline.EmailSender") as mock_sender_cls:

        pipeline = Pipeline(config)
        summary = pipeline.run()

        # USGS fetcher should never be called
        mock_fetcher_cls.return_value.fetch_all_state_gauges.assert_not_called()
        # Sheet reader should never be called
        mock_reader_cls.return_value.get_subscribers.assert_not_called()
        # Email sender should never be called
        mock_sender_cls.return_value.send_email.assert_not_called()

        # Summary should reflect no work done
        assert summary.emails_sent == 0
        assert summary.total_subscribers == 0
