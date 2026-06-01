# Requirements Document

## Introduction

This feature replaces the existing gauge-first subscription model with a reach-first approach. Instead of subscribing to USGS gauge numbers and US states, subscribers enter American Whitewater (AW) reach IDs. The system resolves each reach ID to its name and associated USGS gauge, fetches flow data, and delivers emails organized by reach rather than by gauge. This eliminates the state-based USGS fetch, the "Include Gauges" column, and the "State" column from the spreadsheet.

## Glossary

- **Reach_ID**: An integer identifier assigned by American Whitewater to a specific river section (e.g., 1493)
- **Reach_Name**: The display name for a reach, composed of river + section + altname from the AW API
- **AW_API**: The American Whitewater GraphQL API at https://www.americanwhitewater.org/graphql
- **USGS_Gauge**: A USGS streamflow monitoring station identified by a numeric ID (e.g., 14209500)
- **Subscriber**: A person identified by email address who receives river level notifications
- **Sheet_Reader**: The component that reads subscriber data from the Google Sheet
- **Reach_Resolver**: The component that queries the AW API to resolve reach IDs into reach names and associated USGS gauge IDs
- **Report_Builder**: The component that constructs personalized HTML email content
- **Pipeline**: The orchestrator that coordinates the full notification workflow
- **Flow_Reading**: A USGS instantaneous streamflow measurement in cubic feet per second (cfs)
- **Reach_Entry**: A single reach section within an email report, containing reach name, flow data, and links

## Requirements

### Requirement 1: Spreadsheet Schema Change

**User Story:** As a subscriber, I want to enter AW reach IDs in the spreadsheet, so that I receive notifications for specific river sections I care about.

#### Acceptance Criteria

1. THE Sheet_Reader SHALL read subscriber data from a spreadsheet with columns: Email (column A) and Reach IDs (column B)
2. WHEN a subscriber row contains a comma-separated list of integers in column B, THE Sheet_Reader SHALL parse each integer as a Reach_ID
3. WHEN a subscriber row contains whitespace around reach IDs or commas, THE Sheet_Reader SHALL trim whitespace and parse correctly
4. IF a subscriber row has an empty or blank email in column A, THEN THE Sheet_Reader SHALL skip that row
5. IF a subscriber row has an empty Reach IDs column, THEN THE Sheet_Reader SHALL skip that subscriber with a logged warning
6. THE Sheet_Reader SHALL validate that the header row contains "Email" in column A and "Reach IDs" in column B

### Requirement 2: Reach Resolution via AW API

**User Story:** As a system operator, I want the system to automatically resolve reach IDs to reach names and gauge associations, so that subscribers only need to know their reach IDs.

#### Acceptance Criteria

1. WHEN the Pipeline processes a list of Reach_IDs, THE Reach_Resolver SHALL query the AW_API using the `getGaugeInformationForReachID` query for each unique Reach_ID
2. THE Reach_Resolver SHALL extract the reach name by combining the `river`, `section`, and `altname` fields from the AW_API response
3. WHEN the AW_API response contains a gauge with source equal to "usgs", THE Reach_Resolver SHALL extract the source_id as the associated USGS_Gauge number
4. WHEN a reach has multiple USGS gauges associated, THE Reach_Resolver SHALL use the first gauge with source equal to "usgs"
5. WHEN a reach has no gauge with source equal to "usgs", THE Reach_Resolver SHALL mark that reach as having no gauge data available
6. IF the AW_API returns an error or is unreachable for a specific reach, THEN THE Reach_Resolver SHALL log the error and mark that reach as unresolvable

### Requirement 3: USGS Flow Data Fetching

**User Story:** As a subscriber, I want to see current flow readings for my reaches, so that I can decide whether to go paddling.

#### Acceptance Criteria

1. WHEN the Reach_Resolver has identified USGS_Gauge numbers for subscriber reaches, THE Pipeline SHALL fetch instantaneous flow data from the USGS Water Services API for each unique gauge number
2. THE Pipeline SHALL deduplicate gauge fetches when multiple reaches share the same USGS_Gauge
3. IF the USGS API returns an error or no data for a gauge, THEN THE Pipeline SHALL mark the associated reaches as having no current flow data

### Requirement 4: Reach-First Email Layout

**User Story:** As a subscriber, I want each email entry to show the reach name prominently with a link to the AW page, so that I can quickly identify my river sections and access more details.

#### Acceptance Criteria

1. THE Report_Builder SHALL render each Reach_Entry with the Reach_Name as the primary heading, linked to the AW page URL (https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main)
2. WHEN a reach has associated flow data, THE Report_Builder SHALL display the flow reading in cfs and the reading timestamp below the reach name
3. WHEN a reach has an associated USGS_Gauge, THE Report_Builder SHALL display the gauge number as a secondary link to the USGS monitoring page
4. WHEN a reach has no associated USGS_Gauge, THE Report_Builder SHALL display the reach name and AW link with the text "No gauge data available" in place of flow information
5. THE Report_Builder SHALL order reach entries in the same sequence as the subscriber specified them in the spreadsheet
6. THE Report_Builder SHALL format the reading timestamp in a human-readable format (e.g., "Wed, Jan 15 8:00 AM")

### Requirement 5: Removal of Gauge-First Model

**User Story:** As a system maintainer, I want the old gauge-first subscription model removed, so that there is a single clear subscription path and no dead code.

#### Acceptance Criteria

1. THE Pipeline SHALL NOT use state-based USGS fetching (fetching all gauges for a US state)
2. THE Sheet_Reader SHALL NOT read or require a "State" column from the spreadsheet
3. THE Sheet_Reader SHALL NOT read or require an "Include Gauges" column from the spreadsheet
4. THE Pipeline SHALL NOT use the EmailGrouper or GroupedSubscriber model for state-based grouping

### Requirement 6: Reach-to-Gauge Caching

**User Story:** As a system operator, I want reach-to-gauge associations cached locally, so that the system does not make excessive API calls to AW on every run.

#### Acceptance Criteria

1. WHEN the Reach_Resolver resolves a Reach_ID, THE Pipeline SHALL cache the reach name and associated USGS_Gauge number locally
2. WHEN a cached entry exists for a Reach_ID and the cache entry is less than 7 days old, THE Reach_Resolver SHALL use the cached data instead of querying the AW_API
3. WHEN a cached entry is older than 7 days, THE Reach_Resolver SHALL re-query the AW_API and update the cache
4. IF the AW_API is unreachable and a stale cache entry exists, THEN THE Reach_Resolver SHALL use the stale cached data and log a warning
5. THE Pipeline SHALL store the cache as a JSON file at the path configured in the application config

### Requirement 7: Reach ID Parsing and Validation

**User Story:** As a subscriber, I want the system to handle minor formatting issues in my reach ID list, so that small typos do not prevent my report from being generated.

#### Acceptance Criteria

1. WHEN a reach ID value is not a valid positive integer, THE Sheet_Reader SHALL skip that value and log a warning identifying the invalid entry and the subscriber email
2. WHEN a subscriber's reach ID list contains duplicate reach IDs, THE Sheet_Reader SHALL deduplicate them preserving the first occurrence order
3. THE Sheet_Reader SHALL parse reach IDs separated by commas, including entries with extra spaces (e.g., "1493, 1494 , 2001")

### Requirement 8: Pipeline Orchestration

**User Story:** As a system operator, I want the pipeline to coordinate reach resolution, data fetching, and email delivery in a reliable sequence, so that subscribers receive complete reports.

#### Acceptance Criteria

1. THE Pipeline SHALL execute steps in order: read subscribers, resolve reaches, fetch USGS data, build reports, send emails
2. WHEN all reach resolutions fail for a subscriber, THE Pipeline SHALL skip that subscriber and log the reason
3. WHEN email sending fails for a subscriber, THE Pipeline SHALL log the failure and continue processing remaining subscribers
4. THE Pipeline SHALL produce a run summary including: total subscribers, emails sent, emails failed, and subscribers skipped
5. IF no subscribers are found in the spreadsheet, THEN THE Pipeline SHALL log a warning and complete without error

### Requirement 9: Major Version Bump

**User Story:** As a system maintainer, I want the version bumped to 1.0.0, so that the breaking change to the subscription model is clearly communicated via semantic versioning.

#### Acceptance Criteria

1. THE Pipeline SHALL update `__version__` to `"1.0.0"` to reflect the breaking change to the spreadsheet schema and subscription model
2. THE email footer SHALL display the updated version number
