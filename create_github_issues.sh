#!/bin/bash
# Create GitHub Issues for River Level Notification System
# Prerequisites: Install GitHub CLI (https://cli.github.com/) and run `gh auth login`

REPO="patrick-fortunato/river-level-notification-system"

gh issue create --repo "$REPO" \
  --title "Task 0: Prerequisites — Google Cloud setup and subscriber sheet creation" \
  --body "## Sub-tasks

- [ ] 0.1 Set up Google Cloud project and credentials
  - Create a Google Cloud project and enable the Gmail API and Google Sheets API
  - Create a service account and download the JSON key file (\`service_account.json\`)
  - Create OAuth2 Desktop client credentials and download the JSON file (\`gmail_credentials.json\`)
  - Configure the OAuth consent screen and add your Gmail address as a test user
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 0.2 Create the subscriber Google Sheet
  - Row 1: Optional title/description (ignored by the system)
  - Row 2 (Header Row): Leave columns A–C empty; starting from column D, enter USGS gauge numbers
  - Row 3+ (Subscriber Rows): Column C = subscriber email; Columns D+ = TRUE or FALSE
  - Note the Spreadsheet ID from the URL
  - _Requirements: 2.2, 2.3, 2.5_

- [ ] 0.3 Share the Google Sheet with the service account
  - Add the service account email with Viewer access
  - _Requirements: 2.1_

- [ ] 0.4 Generate the Gmail OAuth token
  - Run \`python src/create_token.py\` (after Task 10.2) or use existing script
  - Approve the consent screen and verify \`token.json\` is created
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 0.5 Add credential files to \`.gitignore\`
  - Add \`service_account.json\`, \`gmail_credentials.json\`, and \`token.json\`
  - _Requirements: 7.4_
"

gh issue create --repo "$REPO" \
  --title "Task 1: Set up project structure, dependencies, and core data models" \
  --body "## Sub-tasks

- [ ] 1.1 Create project directory structure and install dependencies
  - Create \`src/\` directory with \`__init__.py\`
  - Create \`tests/property/\`, \`tests/unit/\`, \`tests/integration/\` directories
  - Create \`requirements.txt\` with: requests, gspread, google-auth, google-auth-oauthlib, google-api-python-client, schedule, hypothesis, pytest, responses
  - _Requirements: 7.4_

- [ ] 1.2 Implement data models (\`src/models.py\`)
  - Define \`GaugeEntry\` dataclass: gauge_number, gauge_name, usgs_page_url, reading_datetime, flow_level
  - Define \`Subscriber\` dataclass: email, subscribed_gauges (list of gauge number strings)
  - Define \`RunSummary\` dataclass: total_subscribers, emails_sent, emails_failed, subscribers_skipped, skip_reasons, start_time, end_time
  - _Requirements: 1.4, 2.3, 11.2_

- [ ] 1.3 Implement Configuration module (\`src/config.py\`)
  - Define \`Config\` dataclass with all configurable fields
  - Include a \`state_name\` property that maps state codes to full names
  - _Requirements: 1.3, 6.2, 9.3, 13.2_
"

gh issue create --repo "$REPO" \
  --title "Task 2: Implement Retry Utility and Logger" \
  --body "## Sub-tasks

- [ ] 2.1 Implement retry with exponential backoff (\`src/retry.py\`)
  - Implement \`retry_with_backoff(operation, max_retries, initial_backoff, multiplier, retryable_exceptions)\`
  - First attempt immediate; subsequent attempts wait with exponential backoff
  - Raise last exception if all retries exhausted; support jitter
  - _Requirements: 9.1, 9.2, 9.3_

- [ ] 2.2 _(Optional)_ Write property test for retry mechanism
  - **Property 6: Retry With Exponential Backoff**
  - _Validates: Requirements 9.1, 9.2_

- [ ] 2.3 Implement structured logger (\`src/logger.py\`)
  - \`PipelineLogger\` class with counters: emails_sent, emails_failed, subscribers_skipped, skip_reasons
  - Methods: \`log()\`, \`record_send_success()\`, \`record_send_failure()\`, \`record_skip()\`, \`output_summary()\`
  - _Requirements: 11.1, 11.2, 11.3_

- [ ] 2.4 _(Optional)_ Write property test for run summary accuracy
  - **Property 8: Run Summary Accuracy**
  - _Validates: Requirements 11.2_
"

gh issue create --repo "$REPO" \
  --title "Task 3: Implement USGS Data Fetcher" \
  --body "## Sub-tasks

- [ ] 3.1 Implement USGS fetcher (\`src/usgs_fetcher.py\`)
  - \`USGSFetcher\` class with \`__init__(config, http_client)\`
  - Methods: \`_build_request_url()\`, \`_parse_response()\`, \`fetch_gauge_data()\`
  - Raise \`USGSFetchError\` on unrecoverable failure after retries exhausted
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.1_

- [ ] 3.2 _(Optional)_ Write property test for USGS JSON parsing
  - **Property 1: USGS JSON Parsing Extracts All Required Fields**
  - _Validates: Requirements 1.4_

- [ ] 3.3 _(Optional)_ Write unit tests for USGS fetcher
  - Test URL construction, parsing edge cases, error handling
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
"

gh issue create --repo "$REPO" \
  --title "Task 4: Implement Sheet Reader" \
  --body "## Sub-tasks

- [ ] 4.1 Implement Google Sheet reader (\`src/sheet_reader.py\`)
  - \`SheetReader\` class with \`__init__(config)\`
  - Methods: \`authenticate()\`, \`get_gauge_numbers()\`, \`get_subscribers()\`, \`validate_structure()\`
  - Skip rows with empty/blank email in column C
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 4.2 _(Optional)_ Write property test for subscriber sheet parsing
  - **Property 2: Subscriber Sheet Parsing Correctness**
  - _Validates: Requirements 2.2, 2.3, 2.5_
"

gh issue create --repo "$REPO" \
  --title "Task 5: Checkpoint — Ensure all tests pass" \
  --body "Run the full test suite and verify all tests pass before proceeding to the next phase.

**Blocked by:** Tasks 1–4
"

gh issue create --repo "$REPO" \
  --title "Task 6: Implement Report Builder" \
  --body "## Sub-tasks

- [ ] 6.1 Implement report builder (\`src/report_builder.py\`)
  - \`ReportBuilder\` class
  - Methods: \`build_report(subscriber, gauge_data)\`, \`_render_gauge_entry()\`, \`_render_footer()\`
  - Returns HTML string or None if no matching gauges have data
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.1_

- [ ] 6.2 _(Optional)_ Write property test for report filtering
  - **Property 3: Report Contains Only Subscribed Gauges With Data**
  - _Validates: Requirements 3.1, 3.4_

- [ ] 6.3 _(Optional)_ Write property test for HTML rendering completeness
  - **Property 4: HTML Rendering Contains All Required Gauge Information**
  - _Validates: Requirements 3.2_

- [ ] 6.4 _(Optional)_ Write property test for empty report suppression
  - **Property 7: Empty Report Suppression**
  - _Validates: Requirements 10.1_
"

gh issue create --repo "$REPO" \
  --title "Task 7: Implement Email Sender" \
  --body "## Sub-tasks

- [ ] 7.1 Implement email sender (\`src/email_sender.py\`)
  - \`EmailSender\` class with \`__init__(config)\`
  - Methods: \`authenticate()\`, \`_refresh_token_if_needed()\`, \`_apply_rate_limit()\`, \`send_email()\`
  - Handle HTTP 429 with Retry-After header; return True/False
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3, 9.2, 13.1, 13.2, 13.3_

- [ ] 7.2 _(Optional)_ Write property test for independent email delivery
  - **Property 5: Independent Email Delivery**
  - _Validates: Requirements 4.4, 4.5_

- [ ] 7.3 _(Optional)_ Write property test for rate limiting enforcement
  - **Property 10: Rate Limiting Enforcement**
  - _Validates: Requirements 13.1_

- [ ] 7.4 _(Optional)_ Write unit tests for token refresh
  - _Requirements: 8.1, 8.2, 8.3_
"

gh issue create --repo "$REPO" \
  --title "Task 8: Implement Config Validator" \
  --body "## Sub-tasks

- [ ] 8.1 Implement configuration validator (\`src/validator.py\`)
  - \`ConfigValidator\` class with \`__init__(config)\`
  - Methods: \`validate_all()\`, \`_check_file_exists()\`, \`_check_sheet_accessible()\`
  - Returns list of error messages (empty = all passed)
  - _Requirements: 12.1, 12.2, 12.3_

- [ ] 8.2 _(Optional)_ Write property test for validation failure halts pipeline
  - **Property 9: Validation Failure Halts Pipeline**
  - _Validates: Requirements 12.3_
"

gh issue create --repo "$REPO" \
  --title "Task 9: Checkpoint — Ensure all tests pass" \
  --body "Run the full test suite and verify all tests pass before proceeding to the final phase.

**Blocked by:** Tasks 6–8
"

gh issue create --repo "$REPO" \
  --title "Task 10: Implement Pipeline Orchestrator and Token Generator" \
  --body "## Sub-tasks

- [ ] 10.1 Implement pipeline orchestrator (\`src/pipeline.py\`)
  - \`Pipeline\` class with \`__init__(config)\`
  - \`run()\` method: validate config → read gauges → fetch USGS data → read subscribers → build/send reports → output summary
  - On validation failure: log and exit. On USGS failure: log and halt. On email failure: log and continue.
  - _Requirements: 1.5, 4.4, 4.5, 10.1, 10.2, 11.2, 12.3_

- [ ] 10.2 Implement token generator utility (\`src/create_token.py\`)
  - \`generate_token(client_secrets_path, token_output_path)\` function
  - OAuth2 consent flow with gmail.send scope
  - \`__main__\` block for CLI execution
  - _Requirements: 5.1, 5.2, 5.3_
"

gh issue create --repo "$REPO" \
  --title "Task 11: Implement Scheduler and Entry Point" \
  --body "## Sub-tasks

- [ ] 11.1 Implement scheduler (\`src/scheduler.py\`)
  - \`start_scheduler(config)\` using the \`schedule\` library
  - Schedule \`pipeline.run()\` daily at \`config.schedule_time\` (default \"06:00\")
  - Run blocking loop with \`schedule.run_pending()\`
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 11.2 Create main entry point (\`river_notify.py\`)
  - Import Config and start_scheduler
  - Instantiate Config and call start_scheduler
  - _Requirements: 6.1, 6.3_

- [ ] 11.3 _(Optional)_ Write unit tests for scheduler
  - Test default and custom schedule times
  - _Requirements: 6.1, 6.2_
"

gh issue create --repo "$REPO" \
  --title "Task 12: Integration tests and final wiring" \
  --body "## Sub-tasks

- [ ] 12.1 _(Optional)_ Write integration tests for full pipeline
  - Mock USGS API, Google Sheets, and Gmail API
  - Verify pipeline order, run summary, and empty report suppression
  - _Requirements: 1.1, 2.1, 4.1, 10.1, 11.2_

- [ ] 12.2 Implement semantic versioning (\`src/__version__.py\`)
  - Initial version \`0.1.0\`
  - Add \`--version\` flag to entry point
  - Configure \`python-semantic-release\` in \`pyproject.toml\`
  - Document commit conventions: \`fix:\` → PATCH, \`feat:\` → MINOR, \`BREAKING CHANGE:\` → MAJOR
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 12.3 Wire all components and verify end-to-end flow
  - Verify imports, Config passing, email_subject placeholder, --version flag
  - Run full test suite
  - _Requirements: 1.3, 4.2, 6.3, 7.1, 7.2, 7.3, 14.2_
"

gh issue create --repo "$REPO" \
  --title "Task 13: Final checkpoint — Ensure all tests pass" \
  --body "Run the complete test suite one final time and verify everything passes.

**Blocked by:** Tasks 10–12
"

echo ""
echo "Done! All 14 issues created."
