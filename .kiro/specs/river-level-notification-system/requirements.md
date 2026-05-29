# Requirements Document

## Introduction

The River Level Notification System retrieves real-time river gauge data from the USGS water monitoring service for a configured US state, reads subscriber preferences from a Google Sheet, and sends personalized HTML email reports to each subscriber via the Gmail API. The system runs on a configurable daily schedule and includes a separate utility for Gmail OAuth token generation.

## Glossary

- **Notification_System**: The main application that orchestrates data retrieval, subscriber processing, and email delivery.
- **USGS_Data_Service**: The United States Geological Survey water monitoring service that provides real-time river gauge readings for US states.
- **Subscriber_Sheet**: A Google Sheet that stores subscriber email addresses and their gauge subscription preferences.
- **Gauge_Number**: A unique numeric identifier assigned by USGS to each river monitoring station.
- **Gauge_Entry**: A data record for a single river gauge containing: gauge name, USGS page link, date/time of reading, and flow level.
- **Subscriber_Row**: A row in the Subscriber_Sheet (row 3 onward) containing a recipient email address in column C and TRUE/FALSE subscription flags in columns D onward.
- **Header_Row**: Row 2 of the Subscriber_Sheet containing gauge numbers as column headers starting from column D.
- **Email_Report**: A personalized HTML email containing gauge entries for gauges a subscriber has opted into.
- **Token_Generator**: A standalone utility that performs the Gmail OAuth2 consent flow and persists the resulting token locally.
- **Scheduler**: The component responsible for triggering the Notification_System at a configured daily time.
- **Gmail_Service**: The Gmail API used to send emails via OAuth2 authentication.

## Requirements

### Requirement 1: Retrieve River Gauge Data

**User Story:** As a subscriber, I want the system to fetch current river gauge data from USGS, so that I receive up-to-date river level information.

#### Acceptance Criteria

1. WHEN the Notification_System executes its data retrieval step, THE Notification_System SHALL query the USGS_Data_Service via its structured REST API (not screen scraping) to obtain real-time river gauge data for the requested gauge numbers in the configured state.
2. THE Notification_System SHALL request data in a structured format (e.g., JSON) from the USGS Water Services API.
3. THE Notification_System SHALL support a configurable US state code (two-letter abbreviation) for filtering USGS data, defaulting to Oregon (OR) when no state is configured.
4. FOR EACH gauge returned by the USGS_Data_Service, THE Notification_System SHALL extract the gauge name, the USGS page link, the latest date/time of reading, and the current flow level.
5. IF the USGS_Data_Service is unreachable or returns an error, THEN THE Notification_System SHALL log the error and halt the current execution run.

### Requirement 2: Read Subscriber Preferences

**User Story:** As a system operator, I want subscriber preferences managed in a Google Sheet, so that subscriptions can be updated without code changes.

#### Acceptance Criteria

1. WHEN the Notification_System executes its subscriber reading step, THE Notification_System SHALL authenticate with the Google Sheets API using a service account credential file.
2. THE Notification_System SHALL read the Header_Row (row 2) to identify gauge numbers starting from column D.
3. THE Notification_System SHALL read each Subscriber_Row (row 3 onward) to obtain the recipient email address from column C and subscription flags from columns D onward.
4. WHEN a Subscriber_Row has an empty or blank email address in column C, THE Notification_System SHALL skip that row without error.
5. WHEN a Subscriber_Row contains a TRUE value in a gauge column, THE Notification_System SHALL include that gauge in the subscriber's personalized report.

### Requirement 3: Build Personalized Email Reports

**User Story:** As a subscriber, I want to receive an email containing only the river gauges I selected, so that I see relevant information without clutter.

#### Acceptance Criteria

1. FOR EACH subscriber with a valid email address, THE Notification_System SHALL build an Email_Report containing only the gauges marked TRUE in that subscriber's row.
2. FOR EACH gauge included in an Email_Report, THE Notification_System SHALL display: a clickable link to the USGS gauge page, the gauge name, the date/time of the reading, and the flow level.
3. THE Notification_System SHALL format the Email_Report as HTML.
4. WHEN a gauge number from the Header_Row is not found in the retrieved USGS data, THE Notification_System SHALL silently omit that gauge from the Email_Report without generating an error.
5. THE Notification_System SHALL include the application version number in the footer of each Email_Report.

### Requirement 4: Send Emails via Gmail API

**User Story:** As a subscriber, I want to receive my river level report by email, so that I can check conditions without visiting a website.

#### Acceptance Criteria

1. THE Notification_System SHALL authenticate with the Gmail_Service using a persisted OAuth2 token.
2. FOR EACH subscriber with a non-empty Email_Report, THE Notification_System SHALL send the Email_Report to the subscriber's email address.
3. WHEN an email is sent successfully, THE Notification_System SHALL print a success message including the recipient's email address.
4. IF sending an email to a subscriber fails, THEN THE Notification_System SHALL print a failure message including the recipient's email address and error details, and continue processing remaining subscribers.
5. THE Notification_System SHALL send each subscriber's email independently so that a failure for one subscriber does not prevent delivery to other subscribers.

### Requirement 5: Gmail Token Generation Utility

**User Story:** As a system operator, I want a one-time utility to generate the Gmail OAuth token, so that I can set up authentication without modifying the main system.

#### Acceptance Criteria

1. WHEN the Token_Generator is executed, THE Token_Generator SHALL initiate the Gmail OAuth2 consent flow using a client secrets file.
2. WHEN the OAuth2 consent flow completes successfully, THE Token_Generator SHALL save the resulting token to a local file for future use by the Notification_System.
3. THE Token_Generator SHALL request the Gmail send scope during the OAuth2 consent flow.

### Requirement 6: Scheduled Daily Execution

**User Story:** As a system operator, I want the system to run automatically once per day, so that subscribers receive reports without manual intervention.

#### Acceptance Criteria

1. THE Scheduler SHALL execute the Notification_System once per day at a configurable time.
2. THE Scheduler SHALL default to 06:00 AM local time when no custom time is configured.
3. WHEN the scheduled time is reached, THE Scheduler SHALL trigger the full pipeline: retrieve gauge data, read subscriber preferences, and send emails.

### Requirement 7: Secure Credential Management

**User Story:** As a system operator, I want credentials stored externally, so that secrets are never exposed in source code.

#### Acceptance Criteria

1. THE Notification_System SHALL load the Google Sheets service account credentials from an external configuration file.
2. THE Notification_System SHALL load the Gmail OAuth2 token from an external file.
3. THE Notification_System SHALL load the Gmail client secrets from an external configuration file.
4. THE Notification_System SHALL NOT contain hardcoded credentials, API keys, or secrets in source code.

### Requirement 8: Automatic Token Refresh

**User Story:** As a system operator, I want expired OAuth tokens to be refreshed automatically, so that the system continues running without manual re-authentication.

#### Acceptance Criteria

1. WHEN the Notification_System loads a Gmail OAuth2 token that has expired, THE Notification_System SHALL attempt to refresh the token using the stored refresh token.
2. WHEN the token refresh succeeds, THE Notification_System SHALL persist the updated token to the token file and proceed with email delivery.
3. IF the token refresh fails (e.g., refresh token revoked), THEN THE Notification_System SHALL log an error indicating that manual re-authentication via the Token_Generator is required, and halt the current execution run.

### Requirement 9: Retry Logic for Transient Failures

**User Story:** As a system operator, I want the system to retry failed operations, so that temporary network issues don't cause missed reports.

#### Acceptance Criteria

1. WHEN the USGS_Data_Service request fails due to a transient error (e.g., timeout, 5xx response), THE Notification_System SHALL retry the request up to a configurable number of attempts with exponential backoff.
2. WHEN an email send fails due to a transient error (e.g., rate limit, temporary Gmail unavailability), THE Notification_System SHALL retry the send up to a configurable number of attempts with exponential backoff before logging the failure and moving to the next subscriber.
3. THE Notification_System SHALL default to 3 retry attempts if no custom retry count is configured.

### Requirement 10: Empty Report Suppression

**User Story:** As a subscriber, I don't want to receive an empty email when none of my selected gauges have data available.

#### Acceptance Criteria

1. WHEN a subscriber has gauges marked TRUE but none of those gauges returned data from the USGS_Data_Service, THE Notification_System SHALL NOT send an email to that subscriber for the current run.
2. WHEN an email is suppressed due to an empty report, THE Notification_System SHALL log that the subscriber was skipped along with the reason.

### Requirement 11: Structured Logging and Run Summary

**User Story:** As a system operator, I want structured logs with a run summary, so that I can monitor system health and diagnose issues.

#### Acceptance Criteria

1. THE Notification_System SHALL output log entries with timestamps for all significant events (startup, data retrieval, email sends, errors, completion).
2. WHEN a run completes, THE Notification_System SHALL output a summary including: total subscribers processed, emails sent successfully, emails failed, and subscribers skipped (with reasons).
3. THE Notification_System SHALL use structured log formatting (e.g., consistent prefix, severity level) to support log parsing and monitoring tools.

### Requirement 12: Configuration Validation on Startup

**User Story:** As a system operator, I want the system to validate all configuration at startup, so that I'm alerted to problems before any work begins.

#### Acceptance Criteria

1. WHEN the Notification_System starts, THE Notification_System SHALL validate that all required configuration files exist and are readable (service account file, Gmail token file, Gmail client secrets file).
2. WHEN the Notification_System starts, THE Notification_System SHALL validate that the Google Sheet is accessible and contains the expected structure (Header_Row with at least one gauge number).
3. IF any configuration validation check fails, THEN THE Notification_System SHALL log a descriptive error message identifying the specific problem and exit before performing any data retrieval or email operations.

### Requirement 13: Email Rate Limiting

**User Story:** As a system operator, I want email sends to be rate-limited, so that the system doesn't exceed Gmail API quotas as the subscriber list grows.

#### Acceptance Criteria

1. THE Notification_System SHALL enforce a configurable delay between consecutive email sends to avoid exceeding Gmail API rate limits.
2. THE Notification_System SHALL default to a 1-second delay between sends if no custom delay is configured.
3. IF the Gmail API returns a rate-limit error (HTTP 429), THE Notification_System SHALL pause for the duration indicated by the API response (or a default backoff period) before retrying.

### Requirement 14: Semantic Versioning

**User Story:** As a system operator, I want the application to use semantic versioning that auto-increments on changes, so that I can track which version is deployed and what changed.

#### Acceptance Criteria

1. THE Notification_System SHALL maintain a version number following Semantic Versioning (MAJOR.MINOR.PATCH) as defined by semver.org.
2. THE Notification_System SHALL expose its current version in startup logs and when queried via a `--version` command-line flag.
3. THE version SHALL be stored in a single source-of-truth location within the project (e.g., `src/__version__.py` or `pyproject.toml`).
4. THE version SHALL auto-increment on each commit or release using a versioning tool or git hook:
   - PATCH increments for bug fixes and minor changes
   - MINOR increments for new features or non-breaking enhancements
   - MAJOR increments for breaking changes
5. THE Notification_System SHALL include the version in the run summary log output.
