# User Stories & QA Test Cases

## Overview

User stories derived from the requirements document, organized for agile sprint planning. Each story includes acceptance criteria and QA test cases for validation.

---

## Epic 1: River Gauge Data Retrieval

### Story 1.1: Fetch River Gauge Data from USGS API

**As a** subscriber,
**I want** the system to fetch current river gauge data from the USGS REST API,
**So that** I receive accurate, up-to-date river level information in my email.

**Acceptance Criteria:**
- System queries the USGS Instantaneous Values API using JSON format
- System extracts gauge name, USGS page link, reading date/time, and flow level for each gauge
- System uses the configured state code in the API request
- System defaults to Oregon (OR) when no state is configured

**Story Points:** 5

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-1.1.1 | Successful data fetch | Configure 2 valid gauge numbers, run data retrieval | Both gauges return complete GaugeEntry objects with all fields populated |
| TC-1.1.2 | Default state code | Run system without setting a state code | API request includes `stateCd=OR` |
| TC-1.1.3 | Custom state code | Set state code to "WA", run data retrieval | API request includes `stateCd=WA` |
| TC-1.1.4 | JSON format requested | Inspect outgoing API request | URL includes `format=json` |
| TC-1.1.5 | All fields extracted | Fetch data for a known gauge | GaugeEntry contains non-empty gauge_number, gauge_name, usgs_page_url, reading_datetime, flow_level |

---

### Story 1.2: Handle USGS API Failures

**As a** system operator,
**I want** the system to retry transient USGS failures and halt on permanent errors,
**So that** temporary network issues don't cause missed reports but real problems are surfaced.

**Acceptance Criteria:**
- System retries on 5xx responses and timeouts with exponential backoff
- System defaults to 3 retry attempts
- System halts and logs error after all retries are exhausted
- System halts immediately on 4xx (permanent) errors

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-1.2.1 | Retry on 503 | Mock USGS to return 503 twice, then 200 | System retries and succeeds on 3rd attempt |
| TC-1.2.2 | Retry on timeout | Mock USGS to timeout once, then respond | System retries and succeeds |
| TC-1.2.3 | Exhaust retries | Mock USGS to return 500 for all attempts | System logs error and halts after 3 attempts |
| TC-1.2.4 | No retry on 404 | Mock USGS to return 404 | System logs error and halts immediately (no retry) |
| TC-1.2.5 | Exponential backoff timing | Mock failures, measure delays | Each delay is at least multiplier × previous delay |
| TC-1.2.6 | Custom retry count | Set max_retries=5, mock 4 failures then success | System succeeds on 5th attempt |

---

## Epic 2: Subscriber Management

### Story 2.1: Read Subscriber Preferences from Google Sheet

**As a** system operator,
**I want** subscriber preferences managed in a Google Sheet with a simple structure,
**So that** I can add/remove subscribers and change gauge exclusions without touching code.

**Acceptance Criteria:**
- System authenticates with Google Sheets using a service account
- System reads the header row (row 1) to confirm expected column layout
- System reads subscriber emails from column A, rows 2 onward
- System reads optional comma-separated exclusion lists from column B
- Subscribers with empty exclusion lists receive ALL gauges
- Rows with empty/blank email are skipped without error

**Story Points:** 5

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-2.1.1 | Read header row | Sheet has "Email" in A1, "Exclude Gauges" in B1 | System confirms expected structure |
| TC-2.1.2 | Read subscriber with no exclusions | Row 2 has email, column B is blank | Subscriber object has empty excluded_gauges list (receives all) |
| TC-2.1.3 | Read subscriber with exclusions | Row has email, B has "12484500, 12488500" | Subscriber has those 2 gauges in excluded_gauges |
| TC-2.1.4 | Skip empty email row | Row 3 has blank in column A | Row is skipped, no error logged |
| TC-2.1.5 | Multiple subscribers | 5 rows with valid emails | 5 Subscriber objects returned |
| TC-2.1.6 | Service account auth | Provide valid service account JSON | Authentication succeeds, sheet is readable |
| TC-2.1.7 | Invalid service account | Provide malformed JSON file | System reports authentication error |

---

## Epic 3: Email Report Generation

### Story 3.1: Build Personalized HTML Email Reports

**As a** subscriber,
**I want** to receive an email containing all river gauges in my state except those I've opted out of,
**So that** I see relevant information without clutter.

**Acceptance Criteria:**
- Report includes all gauges from the state EXCEPT those in the subscriber's exclusion list
- Each gauge entry shows: clickable USGS link, gauge name, date/time, flow level
- Report is formatted as HTML
- Exclusion entries not matching any USGS gauge are silently ignored

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-3.1.1 | Subscriber with no exclusions | Subscriber has empty exclusion list, 5 gauges available | Report contains all 5 gauge entries |
| TC-3.1.2 | Subscriber with exclusions | Subscriber excludes 2 of 5 gauges | Report contains exactly 3 gauge entries |
| TC-3.1.3 | HTML format | Build report for a subscriber | Output is valid HTML with proper tags |
| TC-3.1.4 | Clickable USGS link | Check gauge entry in report | Contains `<a href="...">` with correct USGS URL |
| TC-3.1.5 | All fields displayed | Check a gauge entry | Shows gauge name, date/time, and flow level |
| TC-3.1.6 | Invalid exclusion silently ignored | Subscriber excludes gauge "99999999" not in USGS data | No error, report includes all available gauges |
| TC-3.1.7 | Version in email footer | Build any report | Footer contains current app version (e.g., "v0.1.0") |

---

### Story 3.2: Suppress Empty Email Reports

**As a** subscriber,
**I don't want** to receive an empty email when all gauges are excluded or no data is available,
**So that** my inbox isn't cluttered with useless messages.

**Acceptance Criteria:**
- No email is sent if all gauges are in the subscriber's exclusion list or no data is available
- System logs that the subscriber was skipped with reason

**Story Points:** 2

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-3.2.1 | All gauges excluded | Subscriber excludes all gauges returned by USGS | No email sent, log shows "skipped: all gauges excluded" |
| TC-3.2.2 | No USGS data available | USGS returns empty data set | No email sent, log shows "skipped: no gauge data" |
| TC-3.2.3 | Some gauges not excluded | Subscriber excludes 2 of 5 gauges | Email IS sent with the 3 remaining gauges |
| TC-3.2.4 | Skip reason logged | Trigger empty report suppression | Log entry includes subscriber email and skip reason |

---

## Epic 4: Email Delivery

### Story 4.1: Send Emails via Gmail API

**As a** subscriber,
**I want** to receive my river level report by email,
**So that** I can check conditions without visiting a website.

**Acceptance Criteria:**
- System authenticates with Gmail using persisted OAuth2 token
- System sends HTML email to each subscriber with a non-empty report
- Success message printed for each sent email
- Failure for one subscriber doesn't block others

**Story Points:** 5

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-4.1.1 | Successful send | Valid token, valid recipient | Email sent, success message printed with recipient address |
| TC-4.1.2 | Failed send continues | 3 subscribers, 2nd fails | 1st and 3rd still receive emails |
| TC-4.1.3 | Failure message logged | Email send fails | Log shows recipient address and error details |
| TC-4.1.4 | HTML content delivered | Send email, check content type | Email MIME type is text/html |
| TC-4.1.5 | Dynamic subject line | State set to "OR" | Email subject is "Current Oregon River Levels" |
| TC-4.1.6 | Custom subject with state | State set to "WA" | Email subject is "Current Washington River Levels" |

---

### Story 4.2: Rate Limit Email Sends

**As a** system operator,
**I want** email sends rate-limited,
**So that** the system doesn't exceed Gmail API quotas as the subscriber list grows.

**Acceptance Criteria:**
- Configurable delay between consecutive sends (default 1 second)
- System respects HTTP 429 Retry-After header from Gmail
- System retries rate-limited sends with backoff

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-4.2.1 | Default 1-second delay | Send 3 emails, measure timing | At least 1 second between each send |
| TC-4.2.2 | Custom delay | Set delay to 2 seconds, send 2 emails | At least 2 seconds between sends |
| TC-4.2.3 | Handle 429 response | Mock Gmail returning 429 with Retry-After: 5 | System waits 5 seconds then retries |
| TC-4.2.4 | 429 without Retry-After | Mock 429 without header | System uses default backoff period |

---

### Story 4.3: Automatic Token Refresh

**As a** system operator,
**I want** expired OAuth tokens refreshed automatically,
**So that** the system keeps running without manual intervention.

**Acceptance Criteria:**
- System detects expired token and refreshes using refresh token
- Updated token is persisted to file
- If refresh fails (revoked), system logs error and halts

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-4.3.1 | Refresh expired token | Load expired token with valid refresh token | New access token obtained, persisted to file |
| TC-4.3.2 | Use valid token as-is | Load non-expired token | No refresh attempted, token used directly |
| TC-4.3.3 | Revoked refresh token | Load expired token with revoked refresh | Error logged mentioning Token_Generator, system halts |
| TC-4.3.4 | Persisted token works next run | Refresh token, restart system | System loads the refreshed token successfully |

---

## Epic 5: Token Generation Utility

### Story 5.1: Generate Gmail OAuth Token

**As a** system operator,
**I want** a one-time utility to generate the Gmail OAuth token,
**So that** I can set up authentication easily without modifying the main system.

**Acceptance Criteria:**
- Utility initiates OAuth2 consent flow using client secrets file
- Utility requests gmail.send scope
- Token saved to local file on successful consent

**Story Points:** 2

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-5.1.1 | Successful token generation | Run utility, complete consent flow | `token.json` created with valid credentials |
| TC-5.1.2 | Correct scope requested | Inspect OAuth request | Scope includes `https://www.googleapis.com/auth/gmail.send` |
| TC-5.1.3 | Missing client secrets | Run utility without `gmail_credentials.json` | Clear error message about missing file |
| TC-5.1.4 | Token file usable by main system | Generate token, then run main pipeline | Main system authenticates successfully using the token |

---

## Epic 6: Scheduling

### Story 6.1: Run Pipeline on Daily Schedule

**As a** system operator,
**I want** the system to run automatically once per day,
**So that** subscribers receive reports without manual intervention.

**Acceptance Criteria:**
- System executes pipeline daily at configurable time
- Default time is 06:00 AM local time
- Full pipeline triggered: fetch data → read subscribers → send emails
- `--run-now` flag executes pipeline once immediately and exits without starting the scheduler

**Story Points:** 2

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-6.1.1 | Default schedule time | Start scheduler without custom time | Pipeline scheduled for 06:00 |
| TC-6.1.2 | Custom schedule time | Set schedule_time to "08:30" | Pipeline scheduled for 08:30 |
| TC-6.1.3 | Pipeline triggered at time | Advance clock to scheduled time | Full pipeline executes (validate → fetch → read → send → summary) |
| TC-6.1.4 | Runs daily | Let scheduler run past 2 scheduled times | Pipeline executes twice |
| TC-6.1.5 | --run-now flag | Run `python river_notify.py --run-now` | Pipeline executes once immediately and process exits |
| TC-6.1.6 | --run-now does not start scheduler | Run with --run-now, check for scheduler loop | No scheduler loop started, process exits after pipeline completes |

---

## Epic 7: Configuration & Security

### Story 7.1: Secure Credential Management

**As a** system operator,
**I want** credentials stored externally,
**So that** secrets are never exposed in source code or version control.

**Acceptance Criteria:**
- All credentials loaded from external files
- No hardcoded secrets in source code
- Credential files listed in .gitignore

**Story Points:** 1

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-7.1.1 | No hardcoded secrets | Search source code for API keys/passwords | No matches found |
| TC-7.1.2 | Credentials loaded from files | Check system startup | Reads service_account.json, token.json, gmail_credentials.json |
| TC-7.1.3 | .gitignore includes credential files | Check .gitignore contents | All 3 credential files are listed |

---

### Story 7.2: Validate Configuration on Startup

**As a** system operator,
**I want** the system to validate all configuration at startup,
**So that** I'm alerted to problems before any work begins.

**Acceptance Criteria:**
- System checks all credential files exist and are readable
- System checks Google Sheet is accessible with expected structure
- System exits with descriptive error if any check fails
- No data retrieval or email operations occur if validation fails

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-7.2.1 | All config valid | Provide all valid files and accessible sheet | Validation passes, pipeline proceeds |
| TC-7.2.2 | Missing service account file | Remove service_account.json | Error: "service account file not found", system exits |
| TC-7.2.3 | Missing token file | Remove token.json | Error: "Gmail token file not found", system exits |
| TC-7.2.4 | Sheet not accessible | Use invalid spreadsheet ID | Error: "Google Sheet not accessible", system exits |
| TC-7.2.5 | Sheet missing header labels | Sheet has wrong or missing column labels in row 1 | Error: "unexpected sheet structure", system exits |
| TC-7.2.6 | No pipeline work on failure | Fail validation, check logs | No USGS requests made, no emails sent |

---

## Epic 8: Observability

### Story 8.1: Structured Logging with Run Summary

**As a** system operator,
**I want** structured logs with a run summary,
**So that** I can monitor system health and diagnose issues quickly.

**Acceptance Criteria:**
- All log entries include timestamp and severity level
- Run summary shows: total subscribers, emails sent, emails failed, subscribers skipped
- Log format supports parsing by monitoring tools

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-8.1.1 | Timestamp in logs | Trigger any log event | Log entry starts with ISO timestamp |
| TC-8.1.2 | Severity levels | Trigger info, warning, error events | Each shows appropriate level (INFO, WARN, ERROR) |
| TC-8.1.3 | Run summary counts | Process 5 subscribers: 3 sent, 1 failed, 1 skipped | Summary shows: total=5, sent=3, failed=1, skipped=1 |
| TC-8.1.4 | Skip reasons included | Subscriber skipped due to empty report | Summary includes reason "no gauge data available" |
| TC-8.1.5 | Summary at end of run | Complete a full pipeline run | Summary is the last output before exit |

---

## Epic 9: Prerequisites (Manual Setup)

### Story 9.1: Google Cloud Project Setup

**As a** system operator,
**I want** clear instructions for setting up Google Cloud credentials,
**So that** I can get the system running without guessing.

**Acceptance Criteria:**
- Documentation covers creating a Cloud project
- Documentation covers enabling Gmail and Sheets APIs
- Documentation covers creating service account + downloading key
- Documentation covers creating OAuth2 client + downloading credentials
- Documentation covers OAuth consent screen setup

**Story Points:** 1 (documentation only)

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-9.1.1 | Follow setup guide end-to-end | New user follows google-credentials-setup.md | All credential files obtained, system runs successfully |
| TC-9.1.2 | Troubleshooting section | Encounter "access blocked" error | Guide explains adding test user |

---

### Story 9.2: Create and Configure Subscriber Sheet

**As a** system operator,
**I want** to create a properly structured Google Sheet,
**So that** the system can read subscriber preferences correctly.

**Acceptance Criteria:**
- Sheet has header row (row 1) with "Email" in column A and "Exclude Gauges" in column B
- Sheet has subscriber emails in column A, rows 2+
- Sheet has optional comma-separated gauge exclusion lists in column B
- Sheet is shared with the service account email

**Story Points:** 1 (manual setup)

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-9.2.1 | Correct sheet structure | Create sheet per spec, run system | System reads all subscribers and exclusion lists correctly |
| TC-9.2.2 | Sheet shared with service account | Share sheet, run system | No authentication errors |
| TC-9.2.3 | Unshared sheet | Don't share sheet, run system | Validation fails with "sheet not accessible" error |

---

## Epic 10: Versioning

### Story 10.1: Semantic Versioning with Auto-Increment

**As a** system operator,
**I want** the application to use semantic versioning that auto-increments on changes,
**So that** I can track which version is deployed and understand the impact of changes.

**Acceptance Criteria:**
- Version follows MAJOR.MINOR.PATCH format (semver.org)
- Version displayed in startup logs and run summary
- `--version` CLI flag prints version and exits
- Version stored in a single source-of-truth file (`src/__version__.py`)
- Version auto-increments based on commit message conventions:
  - `fix:` → PATCH bump
  - `feat:` → MINOR bump
  - `BREAKING CHANGE:` → MAJOR bump

**Story Points:** 3

#### QA Test Cases

| ID | Test Case | Steps | Expected Result |
|----|-----------|-------|-----------------|
| TC-10.1.1 | Version in startup log | Run the pipeline | Log output includes version number (e.g., "v0.1.0") |
| TC-10.1.2 | --version flag | Run `python river_notify.py --version` | Prints version number and exits without running pipeline |
| TC-10.1.3 | Version in run summary | Complete a pipeline run | Run summary includes the application version |
| TC-10.1.4 | Single source of truth | Check `src/__version__.py` | Contains version string matching what's displayed |
| TC-10.1.5 | Patch bump on fix commit | Commit with message `fix: handle empty gauge list` | Version increments from 0.1.0 to 0.1.1 |
| TC-10.1.6 | Minor bump on feat commit | Commit with message `feat: add email templates` | Version increments from 0.1.1 to 0.2.0 |
| TC-10.1.7 | Major bump on breaking change | Commit with `BREAKING CHANGE:` in body | Version increments from 0.2.0 to 1.0.0 |
| TC-10.1.8 | Valid semver format | Check version string | Matches pattern `X.Y.Z` where X, Y, Z are non-negative integers |

---

## Summary

| Epic | Stories | Total Story Points |
|------|---------|-------------------|
| 1. River Gauge Data Retrieval | 2 | 8 |
| 2. Subscriber Management | 1 | 5 |
| 3. Email Report Generation | 2 | 5 |
| 4. Email Delivery | 3 | 11 |
| 5. Token Generation Utility | 1 | 2 |
| 6. Scheduling | 1 | 2 |
| 7. Configuration & Security | 2 | 4 |
| 8. Observability | 1 | 3 |
| 9. Prerequisites | 2 | 2 |
| 10. Versioning | 1 | 3 |
| **Total** | **16 stories** | **45 points** |

## Sprint Planning Suggestions

**Sprint 1 (Foundation):** Stories 7.1, 9.1, 9.2, 1.1 — Get credentials set up, project structure, and data fetching working
**Sprint 2 (Core Pipeline):** Stories 2.1, 3.1, 3.2 — Read subscribers and build reports
**Sprint 3 (Delivery):** Stories 4.1, 4.3, 5.1 — Email sending with token management
**Sprint 4 (Resilience):** Stories 1.2, 4.2, 7.2 — Retry logic, rate limiting, validation
**Sprint 5 (Operations):** Stories 6.1, 8.1, 10.1 — Scheduling, observability, and versioning
