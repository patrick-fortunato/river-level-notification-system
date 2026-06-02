# Requirements Document

## Introduction

Add a color-coded runnability indicator to the email reports, matching the red/green indicator shown on the American Whitewater (AW) website's "Latest Flow" column. The indicator compares the current flow reading against the reach's runnable range (`rmin`/`rmax`) to display whether a reach is currently runnable, too low, or too high. This information is already available from the AW GraphQL API but is not currently captured or displayed.

## Glossary

- **Runnability_Indicator**: A color-coded visual element (dot or text label) in the email report conveying whether the current flow is within the runnable range for a reach
- **Runnability_Status**: An enumeration of flow conditions: "Runnable" (within range), "Too Low" (below rmin), "Too High" (above rmax), or "Unknown" (range data unavailable)
- **Runnable_Range**: The minimum (`rmin`) and maximum (`rmax`) flow values defining acceptable paddling conditions for a reach, as reported by the AW API
- **ReachResolver**: The component that queries the AW GraphQL API to resolve reach IDs into reach metadata (name, gauge ID, state, flow data)
- **ReportBuilder**: The component that renders personalized HTML email reports for subscribers
- **ResolvedReach**: The domain object carrying resolved reach metadata through the pipeline
- **ReachCache**: The JSON-file-based cache storing resolved reach data with TTL expiration
- **GraphQL_Query**: The AW API query issued by ReachResolver to fetch reach and gauge information
- **Email_Client**: Any email rendering application (Gmail, Outlook, Apple Mail) that displays the HTML report to subscribers

## Requirements

### Requirement 1: Capture Runnable Range from AW API

**User Story:** As a pipeline operator, I want the system to capture `rmin` and `rmax` from the AW API during reach resolution, so that runnability status can be determined downstream.

#### Acceptance Criteria

1. WHEN the ReachResolver queries the AW GraphQL API for a reach, THE GraphQL_Query SHALL include the `rmin` and `rmax` fields in the `getGaugeInformationForReachID` selection set.
2. WHEN the AW API returns gauge data containing numeric `rmin` and `rmax` values, THE ReachResolver SHALL extract the `rmin` and `rmax` from the first gauge entry that provides them.
3. WHEN the AW API returns gauge data where `rmin` or `rmax` is null or absent, THE ReachResolver SHALL set the corresponding value to None on the ResolvedReach.
4. THE ResolvedReach SHALL carry optional `rmin` and `rmax` fields (float or None) representing the runnable range for the reach.

### Requirement 2: Persist Runnable Range in Cache

**User Story:** As a pipeline operator, I want the runnable range to be cached alongside other reach data, so that the system avoids redundant API calls while still providing runnability information.

#### Acceptance Criteria

1. WHEN the ReachCache stores a ResolvedReach, THE ReachCache SHALL serialize the `rmin` and `rmax` values into the cache entry.
2. WHEN the ReachCache loads a cached entry containing `rmin` and `rmax` values, THE ReachCache SHALL deserialize them into the ResolvedReach object.
3. WHEN a cache entry lacks `rmin` or `rmax` keys (pre-existing cache data), THE ReachCache SHALL treat the missing values as None without error.

### Requirement 3: Determine Runnability Status

**User Story:** As a subscriber, I want the system to determine whether a reach is currently runnable based on its flow reading and runnable range, so that I receive actionable status information.

#### Acceptance Criteria

1. WHEN a flow reading is available and `rmin` and `rmax` are both non-null, AND the flow reading is greater than or equal to `rmin` and less than or equal to `rmax`, THE Runnability_Indicator logic SHALL classify the Runnability_Status as "Runnable".
2. WHEN a flow reading is available and `rmin` and `rmax` are both non-null, AND the flow reading is less than `rmin`, THE Runnability_Indicator logic SHALL classify the Runnability_Status as "Too Low".
3. WHEN a flow reading is available and `rmin` and `rmax` are both non-null, AND the flow reading is greater than `rmax`, THE Runnability_Indicator logic SHALL classify the Runnability_Status as "Too High".
4. WHEN `rmin` is null OR `rmax` is null OR no flow reading is available, THE Runnability_Indicator logic SHALL classify the Runnability_Status as "Unknown".
5. THE Runnability_Indicator logic SHALL use the USGS flow reading when a USGS gauge is associated with the reach, and the AW flow reading when only AW fallback data is available.

### Requirement 4: Display Runnability Indicator in Email

**User Story:** As a subscriber, I want to see a color-coded indicator next to the flow reading in my email report, so that I can quickly identify which reaches are runnable without visiting the AW website.

#### Acceptance Criteria

1. WHEN the Runnability_Status is "Runnable", THE ReportBuilder SHALL render a green-colored indicator with the text "Runnable" adjacent to the flow reading.
2. WHEN the Runnability_Status is "Too Low", THE ReportBuilder SHALL render a red-colored indicator with the text "Too Low" adjacent to the flow reading.
3. WHEN the Runnability_Status is "Too High", THE ReportBuilder SHALL render a red-colored indicator with the text "Too High" adjacent to the flow reading.
4. WHEN the Runnability_Status is "Unknown", THE ReportBuilder SHALL render no indicator adjacent to the flow reading.
5. THE ReportBuilder SHALL use inline CSS styles for all indicator styling to ensure compatibility across Email_Clients.
6. WHEN no flow reading is available for a reach (displays "No gauge data available"), THE ReportBuilder SHALL not render a Runnability_Indicator.

### Requirement 5: Compatibility with Both Flow Data Sources

**User Story:** As a subscriber monitoring reaches with different gauge types, I want the runnability indicator to work regardless of whether the flow comes from USGS or AW, so that all my tracked reaches show consistent status information.

#### Acceptance Criteria

1. WHEN a reach has a USGS gauge association and USGS flow data is available, THE Runnability_Indicator logic SHALL compare the USGS flow reading against the `rmin` and `rmax` from the AW API to determine Runnability_Status.
2. WHEN a reach has no USGS gauge but has AW fallback flow data, THE Runnability_Indicator logic SHALL compare the AW flow reading against the `rmin` and `rmax` from the AW API to determine Runnability_Status.
3. WHEN a reach has a USGS gauge association but USGS flow data is temporarily unavailable, THE Runnability_Indicator logic SHALL classify the Runnability_Status as "Unknown".
