"""
Rebuild Azure SQL Table from SQLite Schema
Drops the existing table and creates a new one matching SQLite structure
"""

import os
import sys
import sqlite3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

AZURE_SQL_CONN = os.getenv('AZURE_SQL_CONN')

try:
    import pyodbc
except ImportError:
    print("ERROR: pyodbc not installed")
    sys.exit(1)

def get_azure_connection():
    """Get Azure SQL connection."""
    conn_str = AZURE_SQL_CONN
    available_drivers = pyodbc.drivers()

    if 'ODBC Driver 18 for SQL Server' in available_drivers:
        return pyodbc.connect(conn_str)
    if 'ODBC Driver 17 for SQL Server' in available_drivers:
        conn_str = conn_str.replace('SQL Server', 'ODBC Driver 17 for SQL Server')
        return pyodbc.connect(conn_str, timeout=60)
    if 'SQL Server' in available_drivers:
        conn_str = conn_str.replace('ODBC Driver 17 for SQL Server', 'SQL Server')
        return pyodbc.connect(conn_str, timeout=60)

    raise ValueError(f"No compatible ODBC driver found")

# SQLite to SQL Server type mapping
TYPE_MAP = {
    'TEXT': 'NVARCHAR(500)',
    'REAL': 'FLOAT',
    'INTEGER': 'INT',
    'BLOB': 'VARBINARY(MAX)',
}

def main():
    print("=" * 70)
    print("REBUILD AZURE SQL TABLE FROM SQLITE SCHEMA")
    print("=" * 70)

    sqlite_path = 'SQL/athletics_deploy.db'

    # Step 1: Get SQLite schema
    print("\n[1/5] Reading SQLite schema...")
    sqlite_conn = sqlite3.connect(sqlite_path)
    cursor = sqlite_conn.cursor()
    cursor.execute("PRAGMA table_info(athletics_data)")
    columns = []
    for row in cursor.fetchall():
        col_name = row[1]
        col_type = row[2] or 'TEXT'
        sql_type = TYPE_MAP.get(col_type.upper(), 'NVARCHAR(500)')
        columns.append((col_name, sql_type))
        print(f"   {col_name}: {col_type} -> {sql_type}")

    # Get row count
    row_count = pd.read_sql("SELECT COUNT(*) as cnt FROM athletics_data", sqlite_conn)['cnt'].iloc[0]
    print(f"\n   Total rows to migrate: {row_count:,}")

    # Step 2: Connect to Azure
    print("\n[2/5] Connecting to Azure SQL...")
    azure_conn = get_azure_connection()
    azure_cursor = azure_conn.cursor()
    print("   OK: Connected")

    # Step 3: Drop existing table
    print("\n[3/5] Dropping existing table...")
    try:
        azure_cursor.execute("DROP TABLE IF EXISTS athletics_data")
        azure_conn.commit()
        print("   OK: Table dropped")
    except Exception as e:
        print(f"   Note: {e}")

    # Step 4: Create new table
    print("\n[4/5] Creating new table with SQLite schema...")
    col_defs = ', '.join([f"[{name}] {dtype}" for name, dtype in columns])
    create_sql = f"CREATE TABLE athletics_data ({col_defs})"

    print(f"\n   SQL: {create_sql[:100]}...")

    azure_cursor.execute(create_sql)
    azure_conn.commit()
    print("   OK: Table created")

    # Step 5: Migrate data in batches
    print("\n[5/5] Migrating data...")

    BATCH_SIZE = 5000
    offset = 0
    total_migrated = 0
    col_names = [c[0] for c in columns]

    while True:
        batch_df = pd.read_sql(
            f"SELECT * FROM athletics_data LIMIT {BATCH_SIZE} OFFSET {offset}",
            sqlite_conn
        )

        if batch_df.empty:
            break

        # Insert batch using fast_executemany
        placeholders = ', '.join(['?' for _ in col_names])
        col_str = ', '.join([f"[{c}]" for c in col_names])
        insert_sql = f"INSERT INTO athletics_data ({col_str}) VALUES ({placeholders})"

        # Convert to list of tuples, handling NaN values
        import numpy as np
        batch_df = batch_df.replace({np.nan: None})
        data = [tuple(None if pd.isna(x) else x for x in row) for row in batch_df.values]

        azure_cursor.fast_executemany = True
        azure_cursor.executemany(insert_sql, data)
        azure_conn.commit()

        total_migrated += len(batch_df)
        offset += BATCH_SIZE

        pct = 100 * total_migrated / row_count
        print(f"   Progress: {total_migrated:,} / {row_count:,} ({pct:.1f}%)")

    # Final verification
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)

    azure_cursor.execute("SELECT COUNT(*) FROM athletics_data")
    final_count = azure_cursor.fetchone()[0]

    print(f"\n   Azure SQL now has: {final_count:,} rows")

    if final_count == row_count:
        print(f"   SUCCESS: All {row_count:,} rows migrated!")
    else:
        print(f"   WARNING: Expected {row_count:,}, got {final_count:,}")

    # Create indexes
    print("\n   Creating indexes...")
    indexes = [
        ("idx_eventname", "eventname"),
        ("idx_nationality", "nationality"),
        ("idx_competitionid", "competitionid"),
        ("idx_gender", "gender"),
    ]
    for idx_name, col_name in indexes:
        try:
            azure_cursor.execute(f"CREATE INDEX {idx_name} ON athletics_data ([{col_name}])")
            azure_conn.commit()
            print(f"   OK: Created {idx_name}")
        except Exception as e:
            print(f"   Note: {idx_name} - {e}")

    sqlite_conn.close()
    azure_conn.close()
    print("\n   Done!")

if __name__ == "__main__":
    main()
