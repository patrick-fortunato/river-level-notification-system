# River Level Notification System

Automated daily river level reports delivered to your inbox. Subscribers enter [American Whitewater](https://www.americanwhitewater.org/) reach IDs in a Google Sheet, and the system resolves each reach to its name and associated gauge via the AW API, fetches real-time flow data, and sends personalized HTML emails organized by state and reach — with color-coded runnability indicators showing whether each reach is currently paddleable.

## Features

- **Reach-first subscriptions** — subscribe by AW reach ID; the system resolves gauge associations automatically
- **Runnability indicators** — color-coded status (🟢 Runnable / 🔴 Too Low / 🔴 Too High) based on AW flow ranges
- **State-grouped emails** — reaches organized under state headings (alphabetical) for easy scanning
- **AW flow data fallback** — reaches without USGS gauges still show flow data from AW virtual/calculated gauges
- **American Whitewater integration** — reach names, AW page links, state info, and gauge lookups via the AW GraphQL API
- **USGS REST API integration** — structured JSON flow data, no browser or scraping required
- **Google Sheet subscriber management** — add/remove subscribers without code changes
- **Gmail API delivery** — OAuth2 with automatic token refresh
- **Resilient** — retry with exponential backoff, rate limiting, per-reach error isolation
- **Observable** — structured logging with run summaries
- **Scheduled** — runs daily at a configurable time (default 6:00 AM)
- **Cached** — reach data cached locally with 7-day TTL to minimize AW API calls; versioned cache auto-invalidates on schema changes

## Quick Start

### Prerequisites

1. Python 3.10+
2. A Google Cloud project with Gmail API and Google Sheets API enabled
3. Service account credentials (for Sheets) and OAuth2 client credentials (for Gmail)

See [Google Credentials Setup Guide](.kiro/specs/river-level-notification-system/google-credentials-setup.md) for detailed instructions.

### Installation

```bash
pip install -r requirements.txt
```

### Setup

1. Place your `service_account.json` and `gmail_credentials.json` in the project root
2. Create your subscriber Google Sheet ([structure details below](#google-sheet-structure))
3. Share the sheet with your service account email
4. Generate your Gmail token:

```bash
python src/create_token.py
```

5. Update configuration in `src/config.py` with your spreadsheet ID and sender email

### Run

```bash
# Run once immediately
python river_notify.py --run-now

# Start the daily scheduler
python river_notify.py

# Check version
python river_notify.py --version
```

## Google Sheet Structure

| Col A (Email) | Col B (Reach IDs) |
|---------------|-------------------|
| Email | Reach IDs |
| user@email.com | 1493, 2001, 4521 |
| user2@email.com | 305, 1493 |

- **Column A**: Subscriber email address
- **Column B**: Comma-separated list of American Whitewater reach IDs
  - Find reach IDs on the [AW website](https://www.americanwhitewater.org/) (the number in the river detail URL)
  - Duplicates are automatically removed (first occurrence kept)
  - Non-integer values are skipped with a logged warning

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `schedule_time` | `"06:00"` | Daily run time (HH:MM, local) |
| `max_retries` | `3` | Retry attempts for transient failures |
| `email_delay_seconds` | `1.0` | Delay between email sends |
| `email_subject` | `"Current River Levels"` | Email subject line |
| `aw_graphql_url` | `"https://www.americanwhitewater.org/graphql"` | AW GraphQL API endpoint |
| `aw_reach_cache_file` | `"aw_reach_cache.json"` | Local cache file for reach-to-gauge mappings |
| `aw_cache_ttl_seconds` | `604800` | Cache TTL in seconds (7 days) |

## Project Structure

```
├── river_notify.py          # Main entry point
├── src/
│   ├── __init__.py
│   ├── __version__.py       # Semantic version (1.0.0)
│   ├── config.py            # Configuration dataclass
│   ├── models.py            # Data models (ReachSubscriber, ResolvedReach, etc.)
│   ├── usgs_fetcher.py      # USGS API integration
│   ├── sheet_reader.py      # Google Sheets reader (Email + Reach IDs)
│   ├── reach_resolver.py    # AW API reach resolution (reach ID → name + gauge)
│   ├── reach_cache.py       # Per-reach versioned cache with TTL (JSON file)
│   ├── report_builder.py    # HTML email report builder (reach-first layout)
│   ├── email_sender.py      # Gmail API sender
│   ├── pipeline.py          # Pipeline orchestrator
│   ├── retry.py             # Retry with exponential backoff
│   ├── validator.py         # Startup configuration validator
│   ├── logger.py            # Structured logging
│   ├── aw_client.py         # American Whitewater API client
│   ├── scheduler.py         # Daily scheduler
│   └── create_token.py      # One-time OAuth token generator
├── tests/
│   ├── property/            # Property-based tests (Hypothesis)
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests (mocked services)
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── android/                 # Native Android companion app (Kotlin, planned)
    └── app/
```

## Commit Message Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic version bumping:

- `fix: description` → PATCH bump (0.1.0 → 0.1.1)
- `feat: description` → MINOR bump (0.1.0 → 0.2.0)
- `BREAKING CHANGE: description` → MAJOR bump (0.1.0 → 1.0.0)

## Security

- **Never commit** `service_account.json`, `gmail_credentials.json`, or `token.json`
- All three are listed in `.gitignore`
- Credentials are loaded from external files at runtime
- `aw_reach_cache.json` is auto-generated and contains no secrets (listed in `.gitignore`)

## Android App (Planned)

A native Android companion app is in development under the `android/` directory. It provides the same river flow and runnability data directly on your phone — no email required.

- **Home screen widget** — shows river names + runnability status at a glance
- **Browse & add reaches** — browse AW reaches by state, search by name
- **Daily notifications** — lists runnable rivers after each scheduled fetch
- **Offline support** — cached data available without network
- **WorkManager scheduling** — battery-efficient daily updates at a user-chosen time

The Android app is a standalone Kotlin implementation sharing the same business logic (AW API queries, runnability classification) but running independently from the Windows/Python app.

## Who This Is For

Whitewater kayakers, rafters, and paddlers who want automated river level notifications for their favorite reaches. Enter your American Whitewater reach IDs in the spreadsheet and get daily flow reports with at-a-glance runnability status — no need to check the AW website, look up USGS gauge numbers, or configure state codes.

## License

MIT
