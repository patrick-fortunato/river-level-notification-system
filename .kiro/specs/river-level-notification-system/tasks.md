# Implementation Plan: River Level Notification System

## Overview

Build a Python application that fetches real-time river gauge data from the USGS Water Services REST API for all gauges in a configured US state, reads subscriber emails and exclusion preferences from a Google Sheet, and sends personalized HTML email reports via the Gmail API. Subscribers receive all gauges by default and can optionally exclude specific gauges. The implementation follows an incremental approach: core data models and utilities first, then individual components, then integration and orchestration.

## Tasks

- [ ] 0. Prerequisites — Google Cloud setup and subscriber sheet creation
  - [x] 0.1 Set up Google Cloud project and credentials
    - Create a Google Cloud project and enable the Gmail API and Google Sheets API
    - Create a service account and download the JSON key file (`service_account.json`)
    - Create OAuth2 Desktop client credentials and download the JSON file (`gmail_credentials.json`)
    - Configure the OAuth consent screen and add your Gmail address as a test user
    - See `google-credentials-setup.md` in this spec folder for detailed steps
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 0.2 Create the subscriber Google Sheet
    - Create a new Google Sheet
    - Row 1 (Header Row): Column A = "Email", Column B = "Exclude Gauges"
    - Row 2+ (Subscriber Rows): Column A = subscriber email address; Column B = optional comma-separated list of gauge numbers to exclude (leave blank to receive all gauges)
    - Note the Spreadsheet ID from the URL (the long string between `/d/` and `/edit`)
    - _Requirements: 2.2, 2.3, 2.5, 2.6_

  - [x] 0.3 Share the Google Sheet with the service account
    - Open the Google Sheet and click Share
    - Add the service account email (e.g., `your-name@your-project.iam.gserviceaccount.com`) with Viewer access
    - _Requirements: 2.1_

  - [x] 0.4 Generate the Gmail OAuth token
    - Run `python src/create_token.py` after Task 10.2 is complete (or use the existing `Create_Token_JSON-for_Gmail.py` script)
    - Approve the consent screen in your browser
    - Verify `token.json` is created in the project directory
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 0.5 Add credential files to `.gitignore`
    - Add `service_account.json`, `gmail_credentials.json`, and `token.json` to `.gitignore`
    - _Requirements: 7.4_

- [x] 1. Set up project structure, dependencies, and core data models
  - [x] 1.1 Create project directory structure and install dependencies
    - Create `src/` directory with `__init__.py`
    - Create `tests/property/`, `tests/unit/`, `tests/integration/` directories
    - Create `requirements.txt` with: `requests`, `gspread`, `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `schedule`, `hypothesis`, `pytest`, `responses`
    - _Requirements: 7.4_

  - [x] 1.2 Implement data models (`src/models.py`)
    - Define `GaugeEntry` dataclass with fields: gauge_number, gauge_name, usgs_page_url, reading_datetime, flow_level
    - Define `Subscriber` dataclass with fields: email, excluded_gauges (list of gauge number strings to exclude; empty = receive all)
    - Define `RunSummary` dataclass with fields: total_subscribers, emails_sent, emails_failed, subscribers_skipped, skip_reasons, start_time, end_time
    - _Requirements: 1.4, 2.3, 2.6, 11.2_

  - [x] 1.3 Implement Configuration module (`src/config.py`)
    - Define `Config` dataclass with all configurable fields: file paths, spreadsheet_id, sender_email, email_subject with `{state_name}` placeholder support, schedule_time (default "06:00"), max_retries (default 3), initial_backoff_seconds (default 1.0), backoff_multiplier (default 2.0), email_delay_seconds (default 1.0), usgs_base_url, usgs_format, usgs_parameter_code, usgs_state_code (default "OR")
    - Include a `state_name` property that maps state codes to full names (e.g., "OR" → "Oregon")
    - _Requirements: 1.3, 6.2, 9.3, 13.2_

- [x] 2. Implement Retry Utility and Logger
  - [x] 2.1 Implement retry with exponential backoff (`src/retry.py`)
    - Implement `retry_with_backoff(operation, max_retries, initial_backoff, multiplier, retryable_exceptions)` function
    - First attempt is immediate; subsequent attempts wait with exponential backoff
    - Raise the last exception if all retries exhausted
    - Support jitter to avoid thundering herd
    - _Requirements: 9.1, 9.2, 9.3_

  - [x]* 2.2 Write property test for retry mechanism
    - **Property 6: Retry With Exponential Backoff**
    - Verify that for any operation failing N times (N ≤ max_retries), the mechanism attempts exactly min(failure_count + 1, max_retries + 1) times with each delay at least multiplier times the previous
    - **Validates: Requirements 9.1, 9.2**

  - [x] 2.3 Implement structured logger (`src/logger.py`)
    - Implement `PipelineLogger` class with counters: emails_sent, emails_failed, subscribers_skipped, skip_reasons
    - Implement `log(level, message)` method outputting structured entries with timestamps and severity
    - Implement `record_send_success(recipient)`, `record_send_failure(recipient, error)`, `record_skip(recipient, reason)` methods
    - Implement `output_summary(total_subscribers)` method printing run summary
    - _Requirements: 11.1, 11.2, 11.3_

  - [x]* 2.4 Write property test for run summary accuracy
    - **Property 8: Run Summary Accuracy**
    - Verify that for any sequence of recorded successes, failures, and skips, the summary counters exactly equal the actual counts
    - **Validates: Requirements 11.2**

- [x] 3. Implement USGS Data Fetcher
  - [x] 3.1 Implement USGS fetcher (`src/usgs_fetcher.py`)
    - Implement `USGSFetcher` class with `__init__(config, http_client)` accepting a requests.Session
    - Implement `_build_request_url()` constructing the USGS API URL with stateCd, parameterCd, and format parameters (no specific site numbers needed)
    - Implement `_parse_response(json_data)` extracting GaugeEntry objects from USGS JSON structure
    - Implement `fetch_all_state_gauges()` that calls the API with retry logic, returns dict mapping gauge_number → GaugeEntry for ALL gauges in the configured state
    - Raise `USGSFetchError` on unrecoverable failure after retries exhausted
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.1_

  - [x]* 3.2 Write property test for USGS JSON parsing
    - **Property 1: USGS JSON Parsing Extracts All Required Fields**
    - Generate arbitrary valid USGS JSON responses and verify each time series produces a GaugeEntry with non-empty gauge_number, gauge_name, usgs_page_url, reading_datetime, and flow_level
    - **Validates: Requirements 1.4**

  - [x]* 3.3 Write unit tests for USGS fetcher
    - Test URL construction with state code (no specific gauge numbers)
    - Test parsing with edge cases: empty timeSeries, missing fields, multiple gauges
    - Test error handling for 4xx and 5xx responses
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 4. Implement Sheet Reader
  - [x] 4.1 Implement Google Sheet reader (`src/sheet_reader.py`)
    - Implement `SheetReader` class with `__init__(config)`
    - Implement `authenticate()` using gspread with service account credentials
    - Implement `get_subscribers()` reading rows 2+ to build Subscriber objects (email from col A, comma-separated exclusion list from col B)
    - Parse column B as a comma-separated list of gauge numbers to exclude; treat empty/blank as no exclusions (receive all gauges)
    - Skip rows with empty/blank email in column A
    - Implement `validate_structure()` checking sheet accessibility and header row has expected column labels
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 4.2 Write property test for subscriber sheet parsing
    - **Property 2: Subscriber Sheet Parsing Correctness**
    - Generate arbitrary sheet data with subscriber rows containing emails and comma-separated exclusion lists, verify parsed Subscriber objects have excluded_gauges matching exactly the gauge numbers listed in column B
    - **Validates: Requirements 2.3, 2.5, 2.6**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Report Builder
  - [x] 6.1 Implement report builder (`src/report_builder.py`)
    - Implement `ReportBuilder` class
    - Implement `build_report(subscriber, gauge_data)` that includes ALL gauges from gauge_data EXCEPT those in subscriber's excluded_gauges list, returns HTML string or None if all gauges are excluded or no data available
    - Implement `_render_gauge_entry(gauge_number, entry)` rendering a single gauge as HTML with clickable USGS link, gauge name, reading datetime, and flow level
    - Implement `_render_footer(version)` rendering the email footer with the application version number
    - Format complete report as HTML with all included gauge entries and version footer
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.1_

  - [x]* 6.2 Write property test for report filtering
    - **Property 3: Report Contains All Gauges Except Excluded Ones**
    - Generate arbitrary subscribers with exclusion lists and gauge data dicts, verify the report includes exactly those gauges present in gauge_data AND NOT in the subscriber's excluded_gauges list
    - **Validates: Requirements 3.1, 3.4**

  - [x]* 6.3 Write property test for HTML rendering completeness
    - **Property 4: HTML Rendering Contains All Required Gauge Information**
    - Generate arbitrary GaugeEntry objects with non-empty fields, verify rendered HTML contains the USGS page URL, gauge name, reading datetime, and flow level
    - **Validates: Requirements 3.2**

  - [x]* 6.4 Write property test for empty report suppression
    - **Property 7: Empty Report Suppression**
    - Generate subscribers whose excluded_gauges list contains all gauge numbers in the gauge data dict (or gauge data is empty), verify build_report returns None
    - **Validates: Requirements 10.1**

- [x] 7. Implement Email Sender
  - [x] 7.1 Implement email sender (`src/email_sender.py`)
    - Implement `EmailSender` class with `__init__(config)`
    - Implement `authenticate()` loading OAuth2 token, refreshing if expired, building Gmail service
    - Implement `_refresh_token_if_needed(creds)` that refreshes expired tokens and persists updated token to file
    - Implement `_apply_rate_limit()` enforcing configurable delay between sends
    - Implement `send_email(recipient, html_body)` that constructs MIME message, sends via Gmail API with retry logic, handles HTTP 429 with Retry-After header
    - Return True on success, False on permanent failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3, 9.2, 13.1, 13.2, 13.3_

  - [x]* 7.2 Write property test for independent email delivery
    - **Property 5: Independent Email Delivery**
    - Simulate lists of subscribers with mixed success/failure outcomes, verify the system attempts to send to every subscriber regardless of prior failures
    - **Validates: Requirements 4.4, 4.5**

  - [x]* 7.3 Write property test for rate limiting enforcement
    - **Property 10: Rate Limiting Enforcement**
    - For any sequence of N email sends (N ≥ 2), verify elapsed time between consecutive send starts is at least email_delay_seconds
    - **Validates: Requirements 13.1**

  - [x]* 7.4 Write unit tests for token refresh
    - Test successful token refresh persists new token
    - Test failed refresh logs error and halts
    - Test non-expired token is used as-is
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 8. Implement Config Validator
  - [x] 8.1 Implement configuration validator (`src/validator.py`)
    - Implement `ConfigValidator` class with `__init__(config)`
    - Implement `validate_all()` returning list of error messages (empty = all passed)
    - Implement `_check_file_exists(path, description)` checking service_account_file, gmail_token_file, gmail_client_secrets_file
    - Implement `_check_sheet_accessible()` verifying Google Sheet is reachable and has expected header row structure (Email in col A, Exclude Gauges in col B)
    - _Requirements: 12.1, 12.2, 12.3_

  - [x]* 8.2 Write property test for validation failure halts pipeline
    - **Property 9: Validation Failure Halts Pipeline**
    - Generate configurations with at least one missing/invalid file, verify validate_all returns non-empty error list and pipeline does not proceed to data retrieval or email
    - **Validates: Requirements 12.3**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Pipeline Orchestrator and Token Generator
  - [x] 10.1 Implement pipeline orchestrator (`src/pipeline.py`)
    - Implement `Pipeline` class with `__init__(config)`
    - Implement `run()` method executing full flow: validate config → fetch ALL USGS data for configured state → read subscribers (emails + exclusion lists) → build and send reports (excluding each subscriber's excluded gauges, with rate limiting) → output run summary
    - On validation failure: log errors and exit without further processing
    - On USGS fetch failure: log error and halt
    - On individual email failure: log and continue to next subscriber
    - Track all outcomes in PipelineLogger and output summary at end
    - _Requirements: 1.5, 4.4, 4.5, 10.1, 10.2, 11.2, 12.3_

  - [x] 10.2 Implement token generator utility (`src/create_token.py`)
    - Implement `generate_token(client_secrets_path, token_output_path)` function
    - Run OAuth2 consent flow using InstalledAppFlow with gmail.send scope
    - Save resulting credentials to token_output_path
    - Add `__main__` block for CLI execution
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 11. Implement Scheduler and Entry Point
  - [x] 11.1 Implement scheduler (`src/scheduler.py`)
    - Implement `start_scheduler(config)` using the `schedule` library
    - Schedule pipeline.run() daily at config.schedule_time (default "06:00")
    - Run blocking loop with schedule.run_pending()
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 11.2 Create main entry point (`river_notify.py`)
    - Import Config, Pipeline, and start_scheduler
    - Instantiate Config with appropriate values
    - Handle `--version` flag: print version and exit
    - Handle `--run-now` flag: execute pipeline once immediately and exit
    - Default (no flag): call start_scheduler to begin the daily loop
    - _Requirements: 6.1, 6.3, 6.4_

  - [x]* 11.3 Write unit tests for scheduler
    - Test default schedule time is "06:00"
    - Test custom schedule time is respected
    - _Requirements: 6.1, 6.2_

- [x] 12. Integration tests and final wiring
  - [x]* 12.1 Write integration tests for full pipeline
    - Mock USGS API responses, Google Sheets data, and Gmail API
    - Verify pipeline calls components in correct order
    - Verify run summary reflects actual outcomes
    - Test empty report suppression end-to-end
    - _Requirements: 1.1, 2.1, 4.1, 10.1, 11.2_

  - [x] 12.2 Implement semantic versioning (`src/__version__.py`)
    - Create `src/__version__.py` with initial version `0.1.0`
    - Add `--version` flag to the main entry point that prints the version and exits
    - Include version in startup log output and run summary
    - Add `python-semantic-release` to dev dependencies in `requirements.txt`
    - Configure semantic-release in `pyproject.toml` (or setup.cfg) to read commit messages and auto-bump version
    - Document commit message conventions: `fix:` → PATCH, `feat:` → MINOR, `BREAKING CHANGE:` → MAJOR
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 12.3 Wire all components and verify end-to-end flow
    - Ensure all imports resolve correctly between modules
    - Verify Config is passed consistently to all components
    - Confirm email_subject uses `{state_name}` placeholder correctly with configured state
    - Confirm `--version` flag works on entry point
    - Run full test suite to confirm no regressions
    - _Requirements: 1.3, 4.2, 6.3, 7.1, 7.2, 7.3, 14.2_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All external service interactions should be mocked in tests
- The `schedule` library is used for in-process scheduling; cron is an alternative for production
