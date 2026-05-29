# River Level Notification System

Automated daily river level reports delivered to your inbox. The system fetches real-time gauge data from the USGS Water Services API, reads subscriber preferences from a Google Sheet, and sends personalized HTML emails via Gmail.

## Features

- **USGS REST API integration** — structured JSON data, no browser or scraping required
- **Configurable state** — works with any US state (default: Oregon)
- **Google Sheet subscriber management** — add/remove subscribers without code changes
- **Personalized reports** — each subscriber only sees the gauges they opted into
- **Gmail API delivery** — OAuth2 with automatic token refresh
- **Resilient** — retry with exponential backoff, rate limiting, empty report suppression
- **Observable** — structured logging with run summaries
- **Scheduled** — runs daily at a configurable time (default 6:00 AM)
- **Versioned** — semantic versioning with auto-increment

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

| Row | Col A (Email) | Col B (Include Gauges) |
|-----|---------------|------------------------|
| 1 (Header) | Email | Include Gauges |
| 2+ (Subscribers) | user@email.com | 12484500, 12488500 |
| 2+ (Subscribers) | user2@email.com | *(empty = receive all gauges)* |

- **Column A**: Subscriber email address
- **Column B**: Optional comma-separated list of USGS gauge numbers to include
  - If empty, the subscriber receives ALL gauges for the configured state
  - If populated, the subscriber receives ONLY those gauges listed

## Configuration

Key settings in `src/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `usgs_state_code` | `"OR"` | Two-letter US state abbreviation |
| `schedule_time` | `"06:00"` | Daily run time (HH:MM, local) |
| `max_retries` | `3` | Retry attempts for transient failures |
| `email_delay_seconds` | `1.0` | Delay between email sends |
| `email_subject` | `"Current {state_name} River Levels"` | Subject line template |

## Project Structure

```
├── river_notify.py          # Main entry point
├── src/
│   ├── __init__.py
│   ├── __version__.py       # Semantic version (single source of truth)
│   ├── config.py            # Configuration dataclass
│   ├── usgs_fetcher.py      # USGS API integration
│   ├── sheet_reader.py      # Google Sheets reader
│   ├── report_builder.py    # HTML email report builder
│   ├── email_sender.py      # Gmail API sender
│   ├── retry.py             # Retry with exponential backoff
│   ├── validator.py         # Startup configuration validator
│   ├── logger.py            # Structured logging
│   ├── pipeline.py          # Pipeline orchestrator
│   ├── scheduler.py         # Daily scheduler
│   └── create_token.py      # One-time OAuth token generator
├── tests/
│   ├── property/            # Property-based tests (Hypothesis)
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests (mocked services)
├── requirements.txt
├── pyproject.toml
└── .gitignore
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

## Who This Is For

Whitewater kayakers, rafters, anglers, hydrology enthusiasts, and anyone who wants automated river level notifications based on their personal list of favorite gauges.

## License

MIT
