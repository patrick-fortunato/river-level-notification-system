# Tasks: Android River Flow App (v2 - Clean Rebuild)

## Phase 1: Project Setup + Data Layer

- [ ] 1.1 Create Gradle project structure (settings.gradle.kts, build.gradle.kts, libs.versions.toml, gradle wrapper)
- [ ] 1.2 Create app/build.gradle.kts with dependencies (Compose, Room, Retrofit, Hilt, WorkManager, Glance)
- [ ] 1.3 Create AndroidManifest.xml (INTERNET, POST_NOTIFICATIONS, widget receiver)
- [ ] 1.4 Create Room entities (TrackedReach, CachedFlowData, AvailableReach, UserPreference)
- [ ] 1.5 Create Room DAOs (all suspend functions, no Flow returns)
- [ ] 1.6 Create RiverFlowDatabase class
- [ ] 1.7 Create Retrofit AWGraphQLApi interface and DTO classes
- [ ] 1.8 Create domain models (ReachWithFlow, RunnabilityStatus, RunnabilityClassifier, ReachNameFormatter, UrlBuilder)
- [ ] 1.9 Create ReachRepository with all methods
- [ ] 1.10 Create Hilt modules (NetworkModule, DatabaseModule)
- [ ] 1.11 Create HiltAndroidApp class with notification channel + WorkManager config
- [ ] 1.12 Copy reaches.json to assets/databases/
- [ ] 1.13 Verify build succeeds

## Phase 2: Core UI + ViewModel

- [ ] 2.1 Create Material 3 theme (light/dark)
- [ ] 2.2 Create Navigation (routes: main, detail, addReach, settings)
- [ ] 2.3 Create MainActivity with @AndroidEntryPoint + notification permission request
- [ ] 2.4 Create MainViewModel (explicit StateFlow, loadData + refresh methods)
- [ ] 2.5 Create MainScreen (reach list with runnability indicators, refresh button, last update, empty state)
- [ ] 2.6 Create DetailViewModel + DetailScreen (flow, links, runnability)
- [ ] 2.7 Create AddReachViewModel + AddReachScreen (state browser, search, add button, "already tracked" indicator)
- [ ] 2.8 Verify build succeeds

## Phase 3: Settings + Scheduling

- [ ] 3.1 Create SettingsViewModel + SettingsScreen (time picker, tracked reach list with remove, refresh reach list button)
- [ ] 3.2 Create WorkScheduler (scheduleDaily, uses PeriodicWorkRequest)
- [ ] 3.3 Create DataFetchWorker (@HiltWorker, calls repo + notification + widget update)
- [ ] 3.4 Schedule daily work on app startup in Application.onCreate
- [ ] 3.5 Verify build succeeds

## Phase 4: Widget + Notifications

- [ ] 4.1 Create RiverFlowWidget (Glance, reads from Room directly, shows reaches + indicators)
- [ ] 4.2 Create RiverFlowWidgetReceiver
- [ ] 4.3 Create WidgetUpdater utility
- [ ] 4.4 Create NotificationHelper (channel, daily update notification)
- [ ] 4.5 Create widget XML metadata and initial layout
- [ ] 4.6 Add clickable action to open app from widget
- [ ] 4.7 Verify build succeeds

## Phase 5: Emulator Testing

- [ ] 5.1 Run on emulator — verify app opens to empty state
- [ ] 5.2 Browse states, select Oregon, verify reaches load instantly from bundled JSON
- [ ] 5.3 Add a reach, verify it appears on main screen
- [ ] 5.4 Tap refresh, verify flow data populates and runnability shows green/red
- [ ] 5.5 Open detail screen, verify links work
- [ ] 5.6 Open settings, set time, verify no crash
- [ ] 5.7 Remove a reach from settings, verify it disappears from main
- [ ] 5.8 Add widget to home screen, verify it shows data
- [ ] 5.9 Trigger WorkManager manually, verify notification appears

## Notes

- All ViewModels use explicit StateFlow (no Room Flow observation)
- Repository methods are all suspend — ViewModel calls them and updates state explicitly
- DAOs have NO Flow return types — only suspend functions
- Bundled JSON loaded on first launch into Room (no createFromAsset, no callbacks)
- Widget creates its own Room instance (read-only, no Hilt)
- WorkManager scheduled on app startup with saved time preference
- Notifications require runtime permission grant (Android 13+)
