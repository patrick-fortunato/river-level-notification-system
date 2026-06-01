"""Configuration module for the River Level Notification System."""

from dataclasses import dataclass


# Mapping of US state codes to full state names
STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


@dataclass
class Config:
    """Application configuration with sensible defaults."""

    # File paths
    service_account_file: str = "service_account.json"
    gmail_token_file: str = "token.json"
    gmail_client_secrets_file: str = "gmail_credentials.json"

    # Google Sheet
    spreadsheet_id: str = "162VPJsE3TosjmvDFOrmH8OXZb_xgFYzytXCP4Y6DWgk"

    # Email
    sender_email: str = "fortunatopt@gmail.com"
    email_subject: str = "Current River Levels"

    # Scheduler
    schedule_time: str = "06:00"

    # Retry
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0

    # Rate limiting
    email_delay_seconds: float = 1.0

    # USGS API
    usgs_base_url: str = "https://waterservices.usgs.gov/nwis/iv/"
    usgs_format: str = "json"
    usgs_parameter_code: str = "00060"  # Discharge (cubic feet/sec)
    # AW API
    aw_graphql_url: str = "https://www.americanwhitewater.org/graphql"
    aw_reach_cache_file: str = "aw_reach_cache.json"
    aw_cache_ttl_seconds: int = 604800  # 7 days
    aw_request_timeout: int = 30
    aw_request_delay: float = 0.5


