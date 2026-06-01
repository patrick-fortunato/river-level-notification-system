# Requirements Document

## Introduction

The River Level Notification System sends daily emails with USGS gauge data for rivers in subscribed states. Each gauge entry currently shows the gauge name, flow reading, and a link to the USGS monitoring page. This feature adds links to associated American Whitewater (AW) river run pages for each gauge, giving subscribers direct access to paddling-specific information about river sections tied to the gauges they monitor.

American Whitewater maintains a database that maps USGS gauge numbers to "reaches" (river runs). One USGS gauge can be associated with multiple reaches (e.g., different sections of the same river). The system will query AW's GraphQL API to build a gauge-to-reach mapping, cache it locally, and include AW reach links in the email HTML alongside each gauge entry.

## Glossary

- **AW_Client**: The component responsible for querying the American Whitewater GraphQL API and returning structured reach data.
- **Reach**: A river run segment in the American Whitewater database, identified by a unique numeric reach ID and associated with a human-readable name.
- **Reach_Mapping**: A data structure that maps USGS gauge numbers to a list of associated Reach records (reach ID and reach name).
- **Reach_Cache**: The component responsible for persisting and retrieving the Reach_Mapping to avoid redundant API calls on every pipeline run.
- **Report_Builder**: The component that constructs HTML email content from gauge data and subscriber preferences.
- **Pipeline**: The orchestration component that coordinates data fetching, report building, and email sending for the River Level Notification System.
- **AW_Reach_URL**: A URL in the format `https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main` that links to the main page for a specific reach.

## Requirements

### Requirement 1: Fetch Reach Mapping from American Whitewater API

**User Story:** As a pipeline operator, I want the system to fetch the mapping of USGS gauge numbers to AW reaches from the AW GraphQL API, so that reach links can be included in notification emails.

#### Acceptance Criteria

1. WHEN the Pipeline initiates a reach mapping fetch, THE AW_Client SHALL query the American Whitewater GraphQL API at `https://www.americanwhitewater.org/graphql` to retrieve gauge-to-reach associations.
2. THE AW_Client SHALL extract the USGS gauge source ID and associated reach IDs and reach names from the API response.
3. THE AW_Client SHALL return a Reach_Mapping that maps each USGS gauge number (string) to a list of Reach records containing reach ID (integer) and reach name (string).
4. WHEN a single USGS gauge number is associated with multiple reaches, THE AW_Client SHALL include all associated reaches in the list for that gauge number.
5. IF the AW GraphQL API returns an error or is unreachable, THEN THE AW_Client SHALL raise a descriptive error indicating the failure reason.

### Requirement 2: Cache the Reach Mapping

**User Story:** As a pipeline operator, I want the reach mapping to be cached locally, so that the system does not query the AW API on every pipeline run and respects AW's server resources.

#### Acceptance Criteria

1. WHEN the AW_Client successfully fetches a Reach_Mapping, THE Reach_Cache SHALL persist the mapping to a local JSON file.
2. WHEN the Pipeline needs the Reach_Mapping, THE Reach_Cache SHALL return the cached mapping if the cache file exists and has not exceeded the configured time-to-live (TTL).
3. WHEN the cache file does not exist or has exceeded the configured TTL, THE Reach_Cache SHALL trigger a fresh fetch from the AW_Client and update the cache file.
4. THE Reach_Cache SHALL store a timestamp alongside the cached data to enable TTL-based expiration checks.
5. IF the cache file exists but contains invalid or unparseable data, THEN THE Reach_Cache SHALL treat the cache as expired and trigger a fresh fetch.

### Requirement 3: Include AW Reach Links in Gauge Email Entries

**User Story:** As a subscriber, I want each gauge entry in my email to include links to the associated American Whitewater river run pages, so that I can quickly navigate to paddling-specific information for the rivers I monitor.

#### Acceptance Criteria

1. WHEN the Report_Builder renders a gauge entry and the Reach_Mapping contains one or more reaches for that gauge number, THE Report_Builder SHALL display one AW reach link per associated reach below the gauge details.
2. THE Report_Builder SHALL format each AW reach link as a clickable hyperlink with the reach name as the link text and the AW_Reach_URL as the href.
3. THE Report_Builder SHALL construct the AW_Reach_URL using the pattern `https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main`.
4. WHEN the Reach_Mapping contains no reaches for a gauge number, THE Report_Builder SHALL render the gauge entry without any AW reach links (no empty placeholder or error message).
5. WHEN a gauge has multiple associated reaches, THE Report_Builder SHALL display all reach links for that gauge.

### Requirement 4: Integrate Reach Mapping into Pipeline Execution

**User Story:** As a pipeline operator, I want the reach mapping fetch and caching to be integrated into the pipeline execution flow, so that reach links are available during report building without manual intervention.

#### Acceptance Criteria

1. THE Pipeline SHALL load the Reach_Mapping (from cache or fresh fetch) before building reports.
2. THE Pipeline SHALL pass the Reach_Mapping to the Report_Builder for use during gauge entry rendering.
3. IF the Reach_Mapping fetch fails and no valid cache exists, THEN THE Pipeline SHALL proceed with report building without reach links rather than halting execution.
4. WHEN the Reach_Mapping fetch fails but a valid (non-expired) cache exists, THE Pipeline SHALL use the cached mapping and log a warning about the fetch failure.
5. THE Pipeline SHALL log the number of gauge-to-reach associations loaded from the mapping.

### Requirement 5: Parse and Print Reach Mapping Data

**User Story:** As a developer, I want the reach mapping serialization to be correct and lossless, so that cached data faithfully represents the fetched API data.

#### Acceptance Criteria

1. THE Reach_Cache SHALL serialize the Reach_Mapping to JSON format preserving all gauge numbers, reach IDs, and reach names.
2. THE Reach_Cache SHALL deserialize a JSON cache file back into a Reach_Mapping that is equivalent to the original data structure.
3. FOR ALL valid Reach_Mapping values, serializing then deserializing SHALL produce an equivalent Reach_Mapping (round-trip property).
