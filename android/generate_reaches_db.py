"""Generate a pre-populated SQLite database with all US reaches from AW API.

Run this script to create the bundled database file for the Android app.
Output: android/app/src/main/assets/databases/river_flow.db
"""

import json
import sqlite3
import time
import sys
import os

import requests

# AW GMI codes for all US states
STATE_CODES = [
    "USA-ALA", "USA-ALK", "USA-ARZ", "USA-ARK", "USA-CAL", "USA-COL",
    "USA-CON", "USA-DEL", "USA-FLO", "USA-GEO", "USA-HAW", "USA-IDA",
    "USA-ILL", "USA-IND", "USA-IOW", "USA-KAN", "USA-KEN", "USA-LOU",
    "USA-MAI", "USA-MAR", "USA-MAS", "USA-MIC", "USA-MIN", "USA-MIS",
    "USA-MSO", "USA-MON", "USA-NEB", "USA-NEV", "USA-NHA", "USA-NJE",
    "USA-NME", "USA-NYO", "USA-NCA", "USA-NDA", "USA-OHI", "USA-OKL",
    "USA-ORE", "USA-PEN", "USA-RHI", "USA-SCA", "USA-SDA", "USA-TNN",
    "USA-TEX", "USA-UTA", "USA-VER", "USA-VIR", "USA-WSH", "USA-WVI",
    "USA-WIS", "USA-WYM", "USA-DIS",
]

AW_GRAPHQL_URL = "https://www.americanwhitewater.org/graphql"
PAGE_SIZE = 100
DELAY_BETWEEN_REQUESTS = 0.5


def format_reach_name(river, section, altname):
    """Format reach name: 'River - Section (Altname)'"""
    parts = []
    if river and river.strip():
        parts.append(river.strip())
    if section and section.strip():
        parts.append(section.strip())
    name = " - ".join(parts)
    if altname and altname.strip():
        name += f" ({altname.strip()})"
    return name


def fetch_reaches_for_state(state_code):
    """Fetch all reaches for a state from AW API."""
    reaches = []
    page = 1

    while True:
        query = (
            f'{{ reaches(states: ["{state_code}"], first: {PAGE_SIZE}, page: {page}) '
            f'{{ data {{ id river section altname }} '
            f'paginatorInfo {{ currentPage lastPage }} }} }}'
        )

        try:
            response = requests.post(
                AW_GRAPHQL_URL,
                json={"query": query},
                timeout=30,
            )
            data = response.json()
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

        if "errors" in data:
            print(f"  GraphQL error on page {page}: {data['errors'][0].get('message')}")
            break

        reaches_data = data.get("data", {}).get("reaches", {})
        items = reaches_data.get("data", [])
        paginator = reaches_data.get("paginatorInfo", {})

        for item in items:
            reach_id = item.get("id")
            if not reach_id:
                continue
            name = format_reach_name(
                item.get("river", ""),
                item.get("section", ""),
                item.get("altname", ""),
            )
            if name:
                reaches.append((int(reach_id), name, state_code))

        current_page = paginator.get("currentPage", 1)
        last_page = paginator.get("lastPage", 1)

        if current_page >= last_page:
            break

        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return reaches


def create_database(output_path, all_reaches):
    """Create the SQLite database with the available_reaches table."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    # Create only the available_reaches table (Room will handle the others)
    # But Room expects ALL tables to exist in a pre-packaged DB, so we need
    # to create all tables matching the Room schema exactly.
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS available_reaches (
            reach_id INTEGER NOT NULL PRIMARY KEY,
            reach_name TEXT NOT NULL,
            state TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tracked_reaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            reach_id INTEGER NOT NULL,
            reach_name TEXT NOT NULL,
            state TEXT,
            gauge_id TEXT,
            rmin REAL,
            rmax REAL,
            added_at INTEGER NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS index_tracked_reaches_reach_id ON tracked_reaches (reach_id);

        CREATE TABLE IF NOT EXISTS cached_flow_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            reach_id INTEGER NOT NULL,
            flow_reading REAL,
            unit TEXT,
            gauge_name TEXT,
            updated_at REAL,
            fetched_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS index_cached_flow_data_reach_id ON cached_flow_data (reach_id);

        CREATE TABLE IF NOT EXISTS user_preferences (
            `key` TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS room_master_table (
            id INTEGER PRIMARY KEY,
            identity_hash TEXT
        );
    """)

    # Insert the identity hash that Room expects
    # This must match the hash Room generates for our schema
    # We'll use a fallback strategy instead — see below
    cursor.execute("INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
                   ("",))  # Empty hash — we'll use fallbackToDestructiveMigration

    # Insert all reaches
    cursor.executemany(
        "INSERT OR REPLACE INTO available_reaches (reach_id, reach_name, state) VALUES (?, ?, ?)",
        all_reaches,
    )

    conn.commit()
    conn.close()


def main():
    output_path = "app/src/main/assets/databases/river_flow.db"
    print(f"Generating pre-populated database: {output_path}")
    print(f"Fetching reaches for {len(STATE_CODES)} states...\n")

    all_reaches = []
    for i, state_code in enumerate(STATE_CODES):
        print(f"[{i+1}/{len(STATE_CODES)}] Fetching {state_code}...", end=" ")
        reaches = fetch_reaches_for_state(state_code)
        all_reaches.extend(reaches)
        print(f"{len(reaches)} reaches")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\nTotal: {len(all_reaches)} reaches across {len(STATE_CODES)} states")
    print(f"Creating database...")

    create_database(output_path, all_reaches)
    print(f"Done! Database saved to: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
