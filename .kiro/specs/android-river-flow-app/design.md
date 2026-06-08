# Design Document: Android River Flow App (v2 - Clean Rebuild)

## Overview

A native Android app for paddlers to check river flow and runnability. Queries the AW GraphQL API, stores data locally in Room, displays results in Jetpack Compose UI and a Glance home screen widget, and sends notifications after daily WorkManager-scheduled fetches.

This is a clean rebuild focusing on:
- **Explicit state management** — ViewModel exposes a single StateFlow, updated explicitly after operations
- **Verified data flow** — each layer tested independently before wiring
- **Simple scheduling** — WorkManager with periodic work, scheduled on app startup
- **Bundled reach data** — reaches.json loaded into Room on first launch for instant browsing

## Architecture

```
┌─────────────────────────────────────────────────┐
│  UI Layer (Jetpack Compose)                     │
│  - Screens observe ViewModel.uiState            │
│  - User actions call ViewModel methods          │
└───────────────────────┬─────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────┐
│  ViewModel Layer                                │
│  - Holds MutableStateFlow<UiState>              │
│  - Calls Repository suspend functions           │
│  - Explicitly updates state after each call     │
└───────────────────────┬─────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────┐
│  Repository Layer (single class)                │
│  - Mediates between API and Room                │
│  - All methods are suspend functions            │
│  - Returns plain data (no reactive flows)       │
└──────────┬────────────────────────┬─────────────┘
           │                        │
┌──────────┴──────────┐  ┌─────────┴──────────────┐
│  AWGraphQLApi       │  │  Room Database          │
│  (Retrofit)         │  │  - TrackedReach         │
│                     │  │  - CachedFlowData       │
│                     │  │  - AvailableReach       │
│                     │  │  - UserPreference       │
└─────────────────────┘  └────────────────────────┘
```

**Key difference from v1:** ViewModels don't observe Room Flows. Instead, they call `repository.getXxx()` suspend functions and explicitly set their StateFlow. This makes the data flow deterministic and debuggable.

## Components

### 1. Room Database (same schema as v1)

Entities: `TrackedReachEntity`, `CachedFlowDataEntity`, `AvailableReachEntity`, `UserPreferenceEntity`

DAOs return `suspend` functions only (no `Flow` return types). The ViewModel controls when to re-query.

### 2. ReachRepository

All methods are `suspend` — no reactive streams:

```kotlin
class ReachRepository(private val api: AWGraphQLApi, private val db: RiverFlowDatabase) {
    suspend fun getTrackedReachesWithFlow(): List<ReachWithFlow>
    suspend fun fetchFlowDataForAllReaches(): Result<Unit>
    suspend fun getReachesByState(gmiCode: String): List<AvailableReach>
    suspend fun searchReaches(query: String): List<AvailableReach>
    suspend fun addTrackedReach(reachId: Int, name: String, state: String): Result<Unit>
    suspend fun removeTrackedReach(reachId: Int)
    suspend fun loadBundledReachesIfNeeded()
    suspend fun getDailyUpdateTime(): String
    suspend fun setDailyUpdateTime(time: String)
}
```

### 3. ViewModels

Each ViewModel holds a `MutableStateFlow<XUiState>` and updates it explicitly:

```kotlin
class MainViewModel(private val repo: ReachRepository) {
    private val _state = MutableStateFlow(MainUiState())
    val state: StateFlow<MainUiState> = _state

    fun loadData() { viewModelScope.launch { _state.value = ... } }
    fun refresh() { viewModelScope.launch { repo.fetchFlowData(); loadData() } }
}
```

### 4. WorkManager Scheduling

- Single `PeriodicWorkRequest` with 24-hour repeat
- Scheduled on app startup using saved time preference
- `DataFetchWorker` calls `repo.fetchFlowDataForAllReaches()`, then posts notification and updates widget
- `ExistingPeriodicWorkPolicy.KEEP` — doesn't reschedule if already queued

### 5. Widget (Glance)

- Reads directly from Room (creates its own DB instance — read-only, no Hilt)
- Shows up to 8 reaches with emoji indicators
- Tap opens app
- Updated after each WorkManager fetch via `GlanceAppWidget.updateAll()`

### 6. Notifications

- Notification channel created in Application.onCreate()
- POST_NOTIFICATIONS permission requested on first app open
- After daily fetch: builds notification body listing runnable rivers
- If none runnable: "No rivers in range today"

## Data Models (unchanged from v1)

Same Room entities and domain models. Key domain class:

```kotlin
data class ReachWithFlow(
    val reachId: Int, val reachName: String, val state: String?,
    val gaugeId: String?, val rmin: Double?, val rmax: Double?,
    val flowReading: Double?, val unit: String?, val gaugeName: String?,
    val lastUpdated: Long?, val runnability: RunnabilityStatus
)
```

## URL Formats

The app links to external pages for each reach:

- **AW Reach page:** `https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main`
- **USGS Gauge page:** `https://waterdata.usgs.gov/monitoring-location/USGS-{gauge_id}/#period=P7D&dataTypeId=continuous-00060-0&showMedian=true&showFieldMeasurements=true`

The USGS URL includes parameters to show the 7-day discharge (00060 = cubic feet per second) with median and field measurements — matching the Python app's behavior.

## Bundled Data Strategy

- `reaches.json` in assets (4,141 reaches, ~400KB)
- On first launch, Repository checks if `available_reaches` table is empty
- If empty, loads JSON and bulk-inserts into Room
- Subsequent launches read from Room (instant)
- "Refresh Reach List" in Settings re-fetches from AW API

## Testing Strategy

1. **Unit tests** for pure functions (RunnabilityClassifier, ReachNameFormatter, UrlBuilder)
2. **Repository tests** with mocked API + in-memory Room DB
3. **Emulator testing** for full integration (API calls, UI, WorkManager, notifications)

No property-based tests in the Android app — keep it simple with example-based tests.
