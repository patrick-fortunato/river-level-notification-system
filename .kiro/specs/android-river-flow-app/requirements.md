# Requirements Document

## Introduction

A native Android companion app for the River Level Notification System. The app displays river flow data and runnability status for whitewater reaches using the American Whitewater (AW) GraphQL API. It provides a home screen widget for at-a-glance runnability, a full detail view with flow readings and links, daily scheduled data fetches via WorkManager, on-demand refresh, and notifications listing runnable rivers. Reach IDs are entered directly in the app and stored locally — no email, no Google Sheet, completely standalone from the existing Python/Windows application.

## Glossary

- **App**: The native Android application built with Kotlin and Jetpack Compose
- **Widget**: A Jetpack Glance home screen widget displaying river runnability status
- **Reach**: A paddleable river section identified by an AW reach ID (integer)
- **Reach_ID**: An integer identifier for a reach on the American Whitewater website
- **AW_API**: The American Whitewater GraphQL API at https://www.americanwhitewater.org/graphql
- **Runnability_Classifier**: The component that classifies flow against the runnable range (rmin/rmax)
- **RunnabilityStatus**: One of: Runnable, Too Low, Too High, Unknown
- **Flow_Reading**: A numeric flow measurement (typically in cfs) from a gauge associated with a reach
- **rmin**: The minimum flow value for a reach to be considered runnable
- **rmax**: The maximum flow value for a reach to be considered runnable
- **Scheduler**: The WorkManager-based component that triggers daily data fetches
- **Data_Repository**: The component managing local storage (Room database) and API data fetching
- **Notification_Manager**: The component responsible for posting Android notifications after data updates

## Requirements

### Requirement 1: Reach Management

**User Story:** As a paddler, I want to browse available reaches by state and add them to my tracked list, so that I can easily find and track rivers without needing to look up reach IDs manually.

#### Acceptance Criteria

1. WHEN the user opens the reach management screen, THE App SHALL fetch the list of available reaches from the AW_API grouped by state
2. THE App SHALL display US states alphabetically, allowing the user to select a state to view its reaches
3. WHEN a user selects a state, THE App SHALL display all reaches for that state sorted alphabetically by river name
4. WHEN a user selects a reach from the state list, THE App SHALL add it to the tracked reaches in the local Room database
5. WHEN a user removes a reach from their tracked list, THE App SHALL delete the reach and its cached data from the local Room database
6. THE App SHALL persist all tracked reach IDs across app restarts using the Room database
7. IF a user selects a reach that is already in their tracked list, THEN THE App SHALL display a message indicating the reach is already tracked and not create a duplicate
8. THE App SHALL provide a search function that filters reaches by name using a contains match (case-insensitive) across all states
9. WHEN the user types a search term, THE App SHALL display matching reaches from all states with their state indicated, sorted alphabetically
10. THE App SHALL cache the available reaches list locally so that the browse-by-state view works offline after the first fetch

### Requirement 2: AW API Data Fetching

**User Story:** As a paddler, I want the app to fetch reach data from the AW API, so that I have current river names, flow readings, and runnability ranges.

#### Acceptance Criteria

1. WHEN a data fetch is triggered, THE Data_Repository SHALL query the AW_API GraphQL endpoint for each tracked reach ID
2. THE Data_Repository SHALL extract reach name (river + section + altname), state, gauge associations, rmin, rmax, and gauge_reading from the AW_API response
3. WHEN the AW_API returns a valid response, THE Data_Repository SHALL store the fetched data in the local Room database with a timestamp
4. IF the AW_API is unreachable or returns an error, THEN THE Data_Repository SHALL retain the previously cached data and log the failure
5. THE Data_Repository SHALL use Retrofit with OkHttp to perform network requests to the AW_API
6. THE Data_Repository SHALL NOT make direct calls to the USGS API; all flow data is obtained from the AW_API gauge_reading field

### Requirement 3: Runnability Classification

**User Story:** As a paddler, I want to see whether each river is runnable, too low, or too high, so that I can quickly decide which rivers to paddle.

#### Acceptance Criteria

1. WHEN flow_reading, rmin, and rmax are all available for a reach, THE Runnability_Classifier SHALL return Runnable if rmin <= flow_reading <= rmax
2. WHEN flow_reading is below rmin, THE Runnability_Classifier SHALL return Too_Low
3. WHEN flow_reading is above rmax, THE Runnability_Classifier SHALL return Too_High
4. IF flow_reading, rmin, or rmax is missing for a reach, THEN THE Runnability_Classifier SHALL return Unknown
5. FOR ALL valid combinations of flow_reading, rmin, and rmax where rmin <= rmax, THE Runnability_Classifier SHALL produce a deterministic and consistent classification (invariant property)

### Requirement 4: Daily Scheduled Data Fetch

**User Story:** As a paddler, I want the app to automatically fetch river data once daily at a time I choose, so that I have fresh data each morning without manual intervention.

#### Acceptance Criteria

1. THE Scheduler SHALL use Android WorkManager to schedule a daily background data fetch
2. WHEN the user sets a daily update time in settings, THE Scheduler SHALL schedule the next fetch to occur at that time
3. WHEN the scheduled time arrives, THE Scheduler SHALL trigger a full data fetch for all tracked reach IDs
4. IF the device is offline at the scheduled time, THEN THE Scheduler SHALL retry the fetch when network connectivity is restored (using WorkManager network constraint)
5. THE Scheduler SHALL persist the schedule across device reboots using WorkManager's persistent work

### Requirement 5: On-Demand Refresh

**User Story:** As a paddler, I want to manually refresh all river data at any time, so that I can get the latest readings before heading to the river.

#### Acceptance Criteria

1. WHEN the user taps the Refresh Now button, THE App SHALL trigger a data fetch for all tracked reach IDs
2. WHILE a refresh is in progress, THE App SHALL display a loading indicator
3. WHEN the refresh completes successfully, THE App SHALL update all displayed data and the last-update timestamp
4. IF the refresh fails due to network error, THEN THE App SHALL display an error message and retain the previously cached data

### Requirement 6: Home Screen Widget

**User Story:** As a paddler, I want a home screen widget showing my rivers and their runnability status, so that I can check conditions at a glance without opening the app.

#### Acceptance Criteria

1. THE Widget SHALL display a list of tracked river names with a runnability indicator (🟢 for Runnable, 🔴 for Too Low or Too High, ⚪ for Unknown)
2. THE Widget SHALL use Jetpack Glance for implementation
3. WHEN the user taps on a river entry in the Widget, THE Widget SHALL open the App to the detail view for that reach
4. WHEN new data is fetched (scheduled or on-demand), THE Widget SHALL update to reflect the latest runnability status
5. THE Widget SHALL display the last-update timestamp at the bottom

### Requirement 7: Full Detail View

**User Story:** As a paddler, I want a detailed view for each river showing flow readings, runnability, and links to AW and USGS pages, so that I can get full information before deciding to paddle.

#### Acceptance Criteria

1. THE App SHALL display a detail screen for each tracked reach showing: reach name, state, current flow reading with units, runnability status, rmin, and rmax
2. THE App SHALL display a link to the AW reach page (https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main)
3. WHEN a USGS gauge is associated with the reach, THE App SHALL display a link to the USGS gauge page (https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_id}/#period=P7D&dataTypeId=continuous-00060-0&showMedian=true&showFieldMeasurements=true)
4. THE App SHALL display the timestamp of the last data fetch for each reach
5. THE App SHALL display the runnability status with color coding (green for Runnable, red for Too Low or Too High, gray for Unknown)

### Requirement 8: Last Update Timestamp

**User Story:** As a paddler, I want to see when data was last fetched, so that I know how fresh the displayed information is.

#### Acceptance Criteria

1. WHEN a data fetch completes successfully, THE App SHALL record the completion timestamp in the local database
2. THE App SHALL display the last-update timestamp on the main reach list screen
3. THE Widget SHALL display the last-update timestamp
4. THE App SHALL format the timestamp in a human-readable format (e.g., "Today 6:00 AM" or "Yesterday 6:00 AM")

### Requirement 9: Notifications

**User Story:** As a paddler, I want a notification after the daily update listing which rivers are runnable, so that I know immediately if conditions are good without opening the app.

#### Acceptance Criteria

1. WHEN the daily scheduled fetch completes, THE Notification_Manager SHALL post an Android notification
2. WHEN one or more reaches are classified as Runnable, THE Notification_Manager SHALL list the runnable river names in the notification body
3. WHEN no reaches are classified as Runnable, THE Notification_Manager SHALL display "No rivers in range today" in the notification body
4. WHEN the user taps the notification, THE App SHALL open to the main reach list screen
5. THE Notification_Manager SHALL use a dedicated notification channel so the user can control notification preferences via Android system settings

### Requirement 10: Settings Screen

**User Story:** As a paddler, I want a settings screen to manage my reach list and daily update time, so that I can configure the app to my preferences.

#### Acceptance Criteria

1. THE App SHALL provide a settings screen accessible from the main screen
2. THE App SHALL allow the user to add new reach IDs from the settings screen
3. THE App SHALL allow the user to remove existing reach IDs from the settings screen
4. THE App SHALL allow the user to set the daily update time using a time picker
5. THE App SHALL persist the daily update time preference in the local database
6. WHEN the user changes the daily update time, THE Scheduler SHALL reschedule the next daily fetch to the new time

### Requirement 11: Local Storage

**User Story:** As a paddler, I want all my data stored locally on the device, so that the app works offline with cached data and requires no external accounts.

#### Acceptance Criteria

1. THE App SHALL use a Room database to store reach IDs, cached reach data, flow readings, and user preferences
2. THE App SHALL function offline by displaying previously cached data when no network is available
3. WHEN the app starts with no network and cached data exists, THE App SHALL display the cached data with the last-update timestamp
4. THE App SHALL NOT require any user account, login, or external service beyond the AW_API for data

### Requirement 12: Main Reach List Screen

**User Story:** As a paddler, I want a main screen showing all my tracked rivers with their current status, so that I can quickly scan conditions for all my rivers.

#### Acceptance Criteria

1. THE App SHALL display a scrollable list of all tracked reaches on the main screen
2. THE App SHALL display each reach entry with: river name, state abbreviation, current flow reading, and runnability indicator (🟢/🔴/⚪)
3. WHEN the user taps a reach entry, THE App SHALL navigate to the detail view for that reach
4. THE App SHALL display the last-update timestamp at the top of the list
5. WHEN no reaches are tracked, THE App SHALL display an empty state with instructions to add reach IDs

### Requirement 13: App Architecture and Tech Stack

**User Story:** As a developer, I want the app built with modern Android architecture and libraries, so that it is maintainable, testable, and follows current best practices.

#### Acceptance Criteria

1. THE App SHALL be implemented in Kotlin using Jetpack Compose for all UI
2. THE App SHALL use Material 3 design components and theming
3. THE App SHALL use Hilt for dependency injection
4. THE App SHALL use Retrofit with OkHttp for network requests
5. THE App SHALL use Room for local database persistence
6. THE App SHALL use WorkManager for background scheduling
7. THE App SHALL use Jetpack Glance for the home screen widget
8. THE App SHALL reside in the android/ directory within the existing repository
