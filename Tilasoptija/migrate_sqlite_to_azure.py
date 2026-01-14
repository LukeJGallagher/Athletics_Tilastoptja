"""
Migrate SQLite Database to Azure SQL
Uses the same connection method as azure_sync.py
"""

import os
import sys
import sqlite3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Get Azure connection string
AZURE_SQL_CONN = os.getenv('AZURE_SQL_CONN')

# Try to import pyodbc
try:
    import pyodbc
except ImportError:
    print("ERROR: pyodbc not installed. Run: pip install pyodbc")
    sys.exit(1)

def get_azure_connection():
    """Get Azure SQL connection (same as azure_sync.py)."""
    if not AZURE_SQL_CONN:
        raise ValueError("AZURE_SQL_CONN environment variable not set!")

    conn_str = AZURE_SQL_CONN
    available_drivers = pyodbc.drivers()

    # Try ODBC Driver 18 first
    if 'ODBC Driver 18 for SQL Server' in available_drivers:
        return pyodbc.connect(conn_str)

    # Try ODBC Driver 17
    if 'ODBC Driver 17 for SQL Server' in available_drivers:
        conn_str_17 = conn_str.replace('ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server')
        conn_str_17 = conn_str_17.replace('SQL Server', 'ODBC Driver 17 for SQL Server')
        return pyodbc.connect(conn_str_17, timeout=60)

    # Fall back to SQL Server driver (Windows default)
    if 'SQL Server' in available_drivers:
        conn_str_fallback = conn_str.replace('ODBC Driver 18 for SQL Server', 'SQL Server')
        conn_str_fallback = conn_str_fallback.replace('ODBC Driver 17 for SQL Server', 'SQL Server')
        return pyodbc.connect(conn_str_fallback, timeout=60)

    raise ValueError(f"No compatible ODBC driver found. Available: {available_drivers}")

def main():
    print("=" * 70)
    print("MIGRATE SQLITE TO AZURE SQL")
    print("=" * 70)

    sqlite_path = 'SQL/athletics_deploy.db'

    # Step 1: Check local SQLite
    print("\n[1/5] Checking local SQLite database...")
    if not os.path.exists(sqlite_path):
        print(f"   ERROR: {sqlite_path} not found!")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_count = pd.read_sql("SELECT COUNT(*) as cnt FROM athletics_data", sqlite_conn)['cnt'].iloc[0]
    print(f"   OK: Local SQLite has {sqlite_count:,} rows")

    # Get column names
    cursor = sqlite_conn.cursor()
    cursor.execute("PRAGMA table_info(athletics_data)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"   OK: {len(columns)} columns")

    # Step 2: Connect to Azure
    print("\n[2/5] Connecting to Azure SQL...")
    try:
        azure_conn = get_azure_connection()
        azure_cursor = azure_conn.cursor()
        print("   OK: Connected to Azure SQL")

        azure_cursor.execute("SELECT COUNT(*) FROM athletics_data")
        azure_count_before = azure_cursor.fetchone()[0]
        print(f"   Current Azure rows: {azure_count_before:,}")
    except Exception as e:
        print(f"   ERROR: {e}")
        sys.exit(1)

    # Step 3: Confirm deletion
    print("\n[3/5] Ready to migrate...")
    print(f"   This will DELETE all {azure_count_before:,} rows in Azure SQL")
    print(f"   and replace with {sqlite_count:,} rows from local SQLite")
    print("   Proceeding automatically...")

    # Step 4: Delete existing Azure data
    print("\n[4/5] Deleting existing Azure SQL data...")
    azure_cursor.execute("DELETE FROM athletics_data")
    azure_conn.commit()
    print(f"   OK: Deleted {azure_count_before:,} rows")

    # Step 5: Migrate in batches
    print("\n[5/5] Migrating data...")

    BATCH_SIZE = 1000
    offset = 0
    total_migrated = 0

    while True:
        # Read batch from SQLite
        batch_df = pd.read_sql(
            f"SELECT * FROM athletics_data LIMIT {BATCH_SIZE} OFFSET {offset}",
            sqlite_conn
        )

        if batch_df.empty:
            break

        # Insert into Azure SQL
        for _, row in batch_df.iterrows():
            placeholders = ', '.join(['?' for _ in columns])
            col_names = ', '.join(columns)
            values = [row[col] for col in columns]

            try:
                azure_cursor.execute(
                    f"INSERT INTO athletics_data ({col_names}) VALUES ({placeholders})",
                    values
                )
            except Exception as e:
                print(f"   Error inserting row: {e}")
                continue

        azure_conn.commit()
        total_migrated += len(batch_df)
        offset += BATCH_SIZE

        pct = 100 * total_migrated / sqlite_count
        print(f"   Progress: {total_migrated:,} / {sqlite_count:,} ({pct:.1f}%)")

    # Final verification
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)

    azure_cursor.execute("SELECT COUNT(*) FROM athletics_data")
    final_count = azure_cursor.fetchone()[0]

    print(f"\n   Azure SQL now has: {final_count:,} rows")

    if final_count == sqlite_count:
        print(f"   SUCCESS: All {sqlite_count:,} rows migrated!")
    else:
        print(f"   WARNING: Expected {sqlite_count:,}, got {final_count:,}")

    # Cleanup
    sqlite_conn.close()
    azure_conn.close()

if __name__ == "__main__":
    main()
