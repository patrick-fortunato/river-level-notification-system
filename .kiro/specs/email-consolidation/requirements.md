# Requirements Document

## Introduction

The River Level Notification System currently sends one email per subscriber row in the Google Sheet. When a user has multiple rows (e.g., one for Oregon and one for Washington), they receive multiple separate emails. This feature consolidates all rows for the same email address into a single email, with distinct sections for each state.

## Glossary

- **Pipeline**: The orchestration component that coordinates data fetching, report building, and email sending for the River Level Notification System.
- **Subscriber**: A person identified by an email address who receives river level notifications.
- **Subscriber_Row**: A single row in the Google Sheet containing an email address, optional gauge inclusion list, and optional state code.
- **Consolidated_Email**: A single email message sent to a subscriber that contains river level data from all of their subscriber rows, organized by state.
- **State_Section**: A visually distinct portion of the consolidated email that contains gauge data for one state.
- **Email_Grouper**: The component responsible for grouping subscriber rows by email address.
- **Report_Builder**: The component that constructs HTML email content from gauge data and subscriber preferences.

## Requirements

### Requirement 1: Group Subscriber Rows by Email Address

**User Story:** As a subscriber with multiple rows in the sheet, I want my rows to be grouped together, so that I receive a single consolidated email instead of multiple separate emails.

#### Acceptance Criteria

1. WHEN the Pipeline reads subscriber rows from the Google Sheet, THE Email_Grouper SHALL group all Subscriber_Rows that share the same email address (case-insensitive comparison) into a single logical subscriber.
2. THE Email_Grouper SHALL preserve the gauge inclusion list and state code from each individual Subscriber_Row within the group.
3. WHEN two Subscriber_Rows have email addresses differing only in letter case, THE Email_Grouper SHALL treat them as the same subscriber.

### Requirement 2: Build Consolidated Report with State Sections

**User Story:** As a subscriber with rows for multiple states, I want my email to have a clearly labeled section for each state, so that I can easily find the river levels for each state I care about.

#### Acceptance Criteria

1. WHEN a subscriber has grouped rows spanning multiple states, THE Report_Builder SHALL produce a single HTML report containing one State_Section per unique state.
2. THE Report_Builder SHALL display a visible state name heading at the start of each State_Section.
3. THE Report_Builder SHALL order State_Sections alphabetically by state name.
4. WHEN a subscriber has grouped rows for the same state with different gauge inclusion lists, THE Report_Builder SHALL combine the gauge inclusion lists for that state (union of all specified gauges).
5. WHEN a subscriber has one row with an empty gauge inclusion list for a state, THE Report_Builder SHALL include all gauges for that state in the corresponding State_Section.

### Requirement 3: Send One Email Per Subscriber

**User Story:** As a subscriber, I want to receive exactly one email per pipeline run regardless of how many rows I have in the sheet, so that my inbox is not cluttered with duplicate notifications.

#### Acceptance Criteria

1. THE Pipeline SHALL send exactly one Consolidated_Email per unique subscriber email address per pipeline run.
2. WHEN the Consolidated_Email is sent, THE Pipeline SHALL use a subject line that does not reference a single specific state.
3. IF the Report_Builder produces no content for any of a subscriber's states (no matching gauges or no data available), THEN THE Pipeline SHALL exclude that state's section from the Consolidated_Email rather than sending an empty section.
4. IF the Report_Builder produces no content for all of a subscriber's states, THEN THE Pipeline SHALL skip sending an email to that subscriber.

### Requirement 4: Maintain Single-State Backward Compatibility

**User Story:** As a subscriber with only one row in the sheet, I want my email to look and function the same as before, so that the consolidation feature does not disrupt my existing experience.

#### Acceptance Criteria

1. WHEN a subscriber has only one Subscriber_Row, THE Report_Builder SHALL produce a report that includes a State_Section heading for that single state.
2. WHEN a subscriber has only one Subscriber_Row, THE Pipeline SHALL send the Consolidated_Email using the same delivery mechanism (Gmail API, retry logic, rate limiting) as the current system.
