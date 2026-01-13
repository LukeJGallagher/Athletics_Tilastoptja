"""
Azure SQL Weekly Sync Script
=============================

This script syncs the local SQLite database to Azure SQL.
Called by GitHub Actions weekly (.github/workflows/weekly_azure_sync.yml)

The script:
1. Connects to Azure SQL using AZURE_SQL_CONN environment variable
2. Fetches new data from Tilastopaja API (changes since last sync)
3. Inserts new records into Azure SQL
4. Logs sync results

Environment Variables Required:
- AZURE_SQL_CONN: Azure SQL ODBC connection string

Usage:
    python azure_sync.py           # Normal sync
    python azure_sync.py --full    # Full table rebuild (use sparingly)
    python azure_sync.py --test    # Test connection only

Author: Team Saudi Athletics
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
import pandas as pd

# Try to import pyodbc
try:
    import pyodbc
except ImportError:
    print("ERROR: pyodbc not installed. Run: pip install pyodbc")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

# Azure SQL connection from environment
AZURE_SQL_CONN = os.getenv('AZURE_SQL_CONN')

# Tilastopaja API endpoints
API_BASE = "https://www.tilastopaja.com/json/ksa"
API_ENDPOINTS = {
    'list': f"{API_BASE}/list",        # New results
    'changes': f"{API_BASE}/changes",  # Changed results
    'deleted': f"{API_BASE}/deleted",  # Deleted results
}

# Table name in Azure SQL
TABLE_NAME = 'athletics_data'

# Columns to keep (matches SQLite schema)
KEEP_COLUMNS = [
    'Athlete_Name', 'Athlete_CountryCode', 'Gender', 'Event',
    'Result', 'result_numeric', 'Position', 'Round', 'round_normalized',
    'Competition', 'Competition_ID', 'Start_Date', 'year',
    'wapoints', 'Athlete_ID', 'DOB'
]

# Sync log file path
SYNC_LOG_PATH = 'azure_sync_log.json'


# =============================================================================
# Database Functions
# =============================================================================

def get_azure_connection():
    """Get Azure SQL connection."""
    if not AZURE_SQL_CONN:
        raise ValueError("AZURE_SQL_CONN environment variable not set!")
    return pyodbc.connect(AZURE_SQL_CONN)


def test_azure_connection():
    """Test Azure SQL connection and return status."""
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS test")
        result = cursor.fetchone()
        conn.close()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)


def table_exists():
    """Check if athletics_data table exists in Azure SQL."""
    try:
        conn = get_azure_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{TABLE_NAME}'
        """)
        exists = cursor.fetchone()[0] > 0
        conn.close()
        return exists
    except Exception as e:
        print(f"Error checking table: {e}")
        return False


def create_table():
    """Create athletics_data table in Azure SQL."""
    print(f"Creating table {TABLE_NAME}...")

    # SQL Server schema
    create_sql = f"""
    CREATE TABLE {TABLE_NAME} (
        id INT IDENTITY(1,1) PRIMARY KEY,
        Athlete_Name NVARCHAR(200),
        Athlete_CountryCode NVARCHAR(10),
        Gender NVARCHAR(10),
        Event NVARCHAR(100),
        Result NVARCHAR(50),
        result_numeric FLOAT,
        Position NVARCHAR(20),
        Round NVARCHAR(50),
        round_normalized NVARCHAR(50),
        Competition NVARCHAR(300),
        Competition_ID NVARCHAR(20),
        Start_Date DATE,
        year INT,
        wapoints FLOAT,
        Athlete_ID NVARCHAR(20),
        DOB DATE,
        sync_date DATETIME DEFAULT GETDATE()
    );

    -- Create indexes for common queries
    CREATE INDEX idx_athlete_name ON {TABLE_NAME}(Athlete_Name);
    CREATE INDEX idx_country ON {TABLE_NAME}(Athlete_CountryCode);
    CREATE INDEX idx_event ON {TABLE_NAME}(Event);
    CREATE INDEX idx_competition_id ON {TABLE_NAME}(Competition_ID);
    CREATE INDEX idx_year ON {TABLE_NAME}(year);
    """

    conn = get_azure_connection()
    cursor = conn.cursor()

    # Split and execute each statement
    for statement in create_sql.split(';'):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
            except Exception as e:
                print(f"  Warning: {e}")

    conn.commit()
    conn.close()
    print(f"Table {TABLE_NAME} created successfully!")


def get_last_sync_date():
    """Get the last sync date from log file."""
    if os.path.exists(SYNC_LOG_PATH):
        with open(SYNC_LOG_PATH, 'r') as f:
            log = json.load(f)
            return log.get('last_sync')
    return None


def update_sync_log(records_added, records_updated=0, records_deleted=0):
    """Update the sync log file."""
    log = {
        'last_sync': datetime.now().isoformat(),
        'records_added': records_added,
        'records_updated': records_updated,
        'records_deleted': records_deleted
    }
    with open(SYNC_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)
    print(f"Sync log updated: {log}")


# =============================================================================
# Data Fetching Functions
# =============================================================================

def fetch_new_records(since_date=None):
    """
    Fetch new records from Tilastopaja API.

    Args:
        since_date: Only fetch records after this date (ISO format)

    Returns:
        DataFrame with new records
    """
    print(f"Fetching new records from Tilastopaja API...")

    try:
        params = {}
        if since_date:
            params['since'] = since_date

        response = requests.get(API_ENDPOINTS['list'], params=params, timeout=60)
        response.raise_for_status()

        data = response.json()

        if not data or not isinstance(data, list):
            print("No new records found.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        print(f"Fetched {len(df)} records from API")
        return df

    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return pd.DataFrame()
    except json.JSONDecodeError as e:
        print(f"Failed to parse API response: {e}")
        return pd.DataFrame()


def process_records(df):
    """
    Process and clean fetched records.

    Args:
        df: Raw DataFrame from API

    Returns:
        Cleaned DataFrame ready for insertion
    """
    if df.empty:
        return df

    # Rename columns to match schema
    column_map = {
        'firstname': 'first_name',
        'lastname': 'last_name',
        'nationality': 'Athlete_CountryCode',
        'gender': 'Gender',
        'eventname': 'Event',
        'performance': 'Result',
        'competitionid': 'Competition_ID',
        'competitionname': 'Competition',
        'competitiondate': 'Start_Date',
        'round': 'Round',
        'position': 'Position',
        'wapoints': 'wapoints',
        'athleteid': 'Athlete_ID',
        'dob': 'DOB'
    }

    # Rename columns that exist
    for old, new in column_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    # Create Athlete_Name from first/last name
    if 'first_name' in df.columns and 'last_name' in df.columns:
        df['Athlete_Name'] = df['first_name'].fillna('') + ' ' + df['last_name'].fillna('')
        df['Athlete_Name'] = df['Athlete_Name'].str.strip()

    # Map gender
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map({'M': 'Men', 'F': 'Women'}).fillna(df['Gender'])

    # Parse result to numeric
    if 'Result' in df.columns:
        df['result_numeric'] = df['Result'].apply(parse_result)

    # Extract year from date
    if 'Start_Date' in df.columns:
        df['Start_Date'] = pd.to_datetime(df['Start_Date'], errors='coerce')
        df['year'] = df['Start_Date'].dt.year

    # Normalize round names
    if 'Round' in df.columns:
        df['round_normalized'] = df['Round'].apply(normalize_round)

    # Keep only required columns
    available_cols = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df[available_cols]

    return df


def parse_result(result):
    """Convert result string to numeric value."""
    if pd.isna(result):
        return None

    result = str(result).strip()

    # Remove common suffixes
    for suffix in ['h', 'w', 'A', 'a', 'i']:
        result = result.rstrip(suffix)

    try:
        # Handle time format (MM:SS.ss or HH:MM:SS)
        if ':' in result:
            parts = result.split(':')
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return float(result)
    except (ValueError, TypeError):
        return None


def normalize_round(round_name):
    """Normalize round names for consistency."""
    if pd.isna(round_name):
        return 'Final'

    round_name = str(round_name).lower().strip()

    round_map = {
        'f': 'Final', 'final': 'Final', 'a final': 'Final',
        'sf': 'Semi-Final', 'semi': 'Semi-Final', 'semifinal': 'Semi-Final',
        'h': 'Heat', 'heat': 'Heat', 'heats': 'Heat',
        'q': 'Qualification', 'qual': 'Qualification'
    }

    # Check for heat numbers
    for i in range(1, 10):
        if round_name in [f'h{i}', f'heat {i}', f'heat{i}']:
            return f'Heat {i}'

    return round_map.get(round_name, round_name.title())


# =============================================================================
# Sync Functions
# =============================================================================

def sync_to_azure(df):
    """
    Insert DataFrame records into Azure SQL.

    Args:
        df: Processed DataFrame to insert

    Returns:
        Number of rows inserted
    """
    if df.empty:
        return 0

    print(f"Inserting {len(df)} records into Azure SQL...")

    conn = get_azure_connection()

    # Build INSERT statement
    columns = df.columns.tolist()
    placeholders = ', '.join(['?' for _ in columns])
    column_names = ', '.join([f'[{c}]' for c in columns])

    insert_sql = f"INSERT INTO {TABLE_NAME} ({column_names}) VALUES ({placeholders})"

    cursor = conn.cursor()
    rows_inserted = 0

    # Insert in batches
    batch_size = 1000
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        for _, row in batch.iterrows():
            values = [None if pd.isna(v) else v for v in row.values]
            try:
                cursor.execute(insert_sql, values)
                rows_inserted += 1
            except Exception as e:
                print(f"  Error inserting row: {e}")

        conn.commit()
        print(f"  Inserted batch {i//batch_size + 1} ({rows_inserted} total)")

    conn.close()
    return rows_inserted


def run_full_sync():
    """Run a full sync - drops and recreates table with all data."""
    print("=" * 60)
    print("FULL SYNC - This will rebuild the entire Azure SQL table")
    print("=" * 60)

    # Check connection
    success, msg = test_azure_connection()
    if not success:
        print(f"Connection failed: {msg}")
        return

    # Drop existing table
    print("Dropping existing table...")
    conn = get_azure_connection()
    cursor = conn.cursor()
    cursor.execute(f"IF OBJECT_ID('{TABLE_NAME}', 'U') IS NOT NULL DROP TABLE {TABLE_NAME}")
    conn.commit()
    conn.close()

    # Create new table
    create_table()

    # Fetch all data
    df = fetch_new_records()
    if df.empty:
        print("No data to sync.")
        return

    # Process and insert
    df = process_records(df)
    rows = sync_to_azure(df)

    update_sync_log(rows)
    print(f"\nFull sync complete! {rows} records inserted.")


def run_incremental_sync():
    """Run incremental sync - only new/changed records since last sync."""
    print("=" * 60)
    print("INCREMENTAL SYNC")
    print("=" * 60)

    # Check connection
    success, msg = test_azure_connection()
    if not success:
        print(f"Connection failed: {msg}")
        return

    # Create table if needed
    if not table_exists():
        print("Table doesn't exist. Running full sync instead...")
        run_full_sync()
        return

    # Get last sync date
    last_sync = get_last_sync_date()
    if last_sync:
        print(f"Last sync: {last_sync}")
    else:
        # Default to last week if no log
        last_sync = (datetime.now() - timedelta(days=7)).isoformat()
        print(f"No sync log found. Fetching records since {last_sync}")

    # Fetch new records
    df = fetch_new_records(since_date=last_sync)
    if df.empty:
        print("No new records to sync.")
        update_sync_log(0)
        return

    # Process and insert
    df = process_records(df)
    rows = sync_to_azure(df)

    update_sync_log(rows)
    print(f"\nIncremental sync complete! {rows} new records inserted.")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Sync athletics data to Azure SQL')
    parser.add_argument('--full', action='store_true', help='Full table rebuild')
    parser.add_argument('--test', action='store_true', help='Test connection only')
    args = parser.parse_args()

    print("=" * 60)
    print("Azure SQL Sync - Team Saudi Athletics")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Check environment
    if not AZURE_SQL_CONN:
        print("\nERROR: AZURE_SQL_CONN environment variable not set!")
        print("\nTo set up:")
        print("1. Go to Azure Portal > Your SQL Database > Connection Strings")
        print("2. Copy the ODBC connection string")
        print("3. Add to GitHub Secrets as SQL_CONNECTION_STRING")
        print("4. Or set locally: export AZURE_SQL_CONN='your_connection_string'")
        sys.exit(1)

    print(f"\nConnection string configured: {'*' * 20}...{AZURE_SQL_CONN[-20:]}")

    if args.test:
        print("\nTesting connection...")
        success, msg = test_azure_connection()
        if success:
            print(f"SUCCESS: {msg}")

            # Check table
            if table_exists():
                conn = get_azure_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
                count = cursor.fetchone()[0]
                conn.close()
                print(f"Table {TABLE_NAME} exists with {count:,} rows")
            else:
                print(f"Table {TABLE_NAME} does not exist")
        else:
            print(f"FAILED: {msg}")
        return

    if args.full:
        run_full_sync()
    else:
        run_incremental_sync()


if __name__ == "__main__":
    main()
