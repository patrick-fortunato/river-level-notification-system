# Requirements Document

## Introduction

This feature enhances the River Level Notification System's email reports by grouping reaches under US state headings instead of rendering them as a flat list. The state information is sourced from the American Whitewater (AW) GraphQL API during reach resolution, requiring no changes to the subscriber spreadsheet schema. Within each state group, reaches maintain the subscriber's specified order.

## Glossary

- **ReachResolver**: The component that queries the AW GraphQL API to resolve reach IDs into reach names, gauge associations, and state information.
- **ResolvedReach**: The data model representing a reach after resolution, containing reach ID, name, gauge ID, and state.
- **ReportBuilder**: The component that constructs personalized HTML email reports for each subscriber.
- **ReachCache**: The component that caches resolved reach data locally with TTL-based expiration.
- **AW_API**: The American Whitewater GraphQL API at `https://www.americanwhitewater.org/graphql`.
- **Subscriber_Spreadsheet**: The Google Sheet containing two columns (Email, Reach IDs) that defines subscriber reach subscriptions.
- **State_Heading**: An HTML heading element in the email report that labels a group of reaches belonging to the same US state.
- **Subscriber_Order**: The order in which a subscriber listed their reach IDs in the spreadsheet.

## Requirements

### Requirement 1: Fetch State from AW API

**User Story:** As a system operator, I want the ReachResolver to capture state information from the AW API during reach resolution, so that reaches can be grouped by state in email reports.

#### Acceptance Criteria

1. WHEN the ReachResolver queries the AW_API for a reach, THE ReachResolver SHALL include the `state` field in the GraphQL query for the `reach(id: N)` resource.
2. WHEN the AW_API returns a valid response containing a `state` field, THE ReachResolver SHALL store the state value in the ResolvedReach model.
3. IF the AW_API returns a null or empty `state` field for a reach, THEN THE ReachResolver SHALL set the state to None on the ResolvedReach model.

### Requirement 2: Extend ResolvedReach Model with State

**User Story:** As a developer, I want the ResolvedReach data model to include a state field, so that downstream components can access state information for grouping.

#### Acceptance Criteria

1. THE ResolvedReach model SHALL contain a `state` field of type optional string representing the US state abbreviation.
2. WHEN a ResolvedReach is constructed without a state value, THE ResolvedReach model SHALL default the `state` field to None.

### Requirement 3: Cache State Information

**User Story:** As a system operator, I want the ReachCache to persist state information alongside other reach data, so that cached reaches retain their state for grouping without re-querying the API.

#### Acceptance Criteria

1. WHEN the ReachCache stores a ResolvedReach entry, THE ReachCache SHALL include the `state` value in the cached JSON data.
2. WHEN the ReachCache loads a cached entry, THE ReachCache SHALL reconstruct the ResolvedReach with the stored `state` value.
3. WHEN the ReachCache loads a cached entry that has no `state` key (legacy cache entry), THE ReachCache SHALL set the `state` field to None on the reconstructed ResolvedReach.

### Requirement 4: Group Reaches by State in Email Report

**User Story:** As a subscriber, I want my email report to show reaches grouped under state headings, so that I can quickly find reaches by geographic region.

#### Acceptance Criteria

1. WHEN the ReportBuilder constructs an email report, THE ReportBuilder SHALL group reaches by their state value.
2. WHEN the ReportBuilder renders a state group, THE ReportBuilder SHALL display a State_Heading containing the full US state name before the group's reach entries.
3. WHILE rendering reaches within a single state group, THE ReportBuilder SHALL maintain the Subscriber_Order of those reaches.
4. WHEN the ReportBuilder encounters reaches with a None state value, THE ReportBuilder SHALL group those reaches under a heading labeled "Other".
5. THE ReportBuilder SHALL order state groups alphabetically by full state name, with the "Other" group appearing last.

### Requirement 5: Preserve Spreadsheet Schema

**User Story:** As a system operator, I want the subscriber spreadsheet to remain unchanged at two columns (Email, Reach IDs), so that no manual data entry changes are required from subscribers.

#### Acceptance Criteria

1. THE Subscriber_Spreadsheet SHALL remain a two-column format containing Email and Reach IDs.
2. THE Pipeline SHALL derive state information exclusively from the AW_API, not from the Subscriber_Spreadsheet.

### Requirement 6: State Code to Full Name Mapping

**User Story:** As a subscriber, I want state headings to display full state names rather than abbreviations, so that the report is easy to read.

#### Acceptance Criteria

1. WHEN the ReportBuilder renders a State_Heading, THE ReportBuilder SHALL convert the state abbreviation to the full US state name using the STATE_NAMES mapping in the configuration module.
2. IF the ReportBuilder encounters a state abbreviation not present in the STATE_NAMES mapping, THEN THE ReportBuilder SHALL use the raw abbreviation as the State_Heading text.
