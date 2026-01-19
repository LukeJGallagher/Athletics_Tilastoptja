"""
Migration Script: SQLite to Azure Blob Storage (Parquet)

This script migrates the Athletics data from local SQLite database
to Azure Blob Storage as compressed Parquet files.

Usage:
    python migrate_to_blob_storage.py

Before running:
1. Create Azure Storage Account (see AZURE_BLOB_STORAGE_GUIDE.md)
2. Create container named 'athletics-data'
3. Add connection string to .env:
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Local imports
try:
    from blob_storage import (
        upload_parquet, create_backup, get_storage_usage,
        _use_azure, get_container_client, MASTER_FILE
    )
    BLOB_AVAILABLE = True
except ImportError as e:
    print(f"Error importing blob_storage: {e}")
    BLOB_AVAILABLE = False

# SQLite database paths
SQLITE_PATHS = {
    'deploy': 'SQL/athletics_deploy.db',
    'competitor': 'SQL/athletics_competitor.db',
    'major': 'SQL/major_championships.db',
    'ksa': 'SQL/ksa_athletics.db',
}


def load_sqlite_data(db_name: str = 'deploy') -> pd.DataFrame:
    """Load data from SQLite database."""
    db_path = SQLITE_PATHS.get(db_name)
    if not db_path:
        print(f"Unknown database: {db_name}")
        return pd.DataFrame()

    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return pd.DataFrame()

    print(f"Loading from SQLite: {db_path}")
    conn = sqlite3.connect(db_path)

    # Get table name
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    if not tables:
        print("No tables found in database")
        return pd.DataFrame()

    # Use first table (usually 'athletics_data')
    table_name = tables[0][0]
    print(f"Reading table: {table_name}")

    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()

    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def analyze_data(df: pd.DataFrame):
    """Analyze data before migration."""
    print("\n" + "=" * 60)
    print("DATA ANALYSIS")
    print("=" * 60)

    print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"\nColumns: {list(df.columns)}")

    # Check for key columns
    key_columns = ['eventname', 'nationality', 'firstname', 'lastname', 'competitionid', 'wapoints']
    print("\nKey column presence:")
    for col in key_columns:
        status = "OK" if col in df.columns else "MISSING"
        print(f"  {col}: {status}")

    # Unique counts
    if 'nationality' in df.columns:
        print(f"\nUnique countries: {df['nationality'].nunique()}")
    if 'eventname' in df.columns:
        print(f"Unique events: {df['eventname'].nunique()}")
    if 'competitionid' in df.columns:
        print(f"Unique competitions: {df['competitionid'].nunique()}")

    # Memory usage
    memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
    print(f"\nMemory usage: {memory_mb:.1f} MB")

    # Estimate Parquet size (typically 5-10x smaller)
    estimated_parquet_mb = memory_mb / 8
    print(f"Estimated Parquet size: {estimated_parquet_mb:.1f} MB")


def migrate_to_blob(db_name: str = 'deploy', force: bool = False):
    """Migrate SQLite database to Azure Blob Storage."""
    print("=" * 60)
    print("MIGRATE SQLITE TO AZURE BLOB STORAGE")
    print("=" * 60)

    if not BLOB_AVAILABLE:
        print("ERROR: blob_storage module not available")
        return False

    if not _use_azure():
        print("\nERROR: Azure Blob Storage not configured")
        print("Set AZURE_STORAGE_CONNECTION_STRING in .env file")
        print("\nExample:")
        print("AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=athleticsksa;AccountKey=...;EndpointSuffix=core.windows.net")
        return False

    # Load SQLite data
    df = load_sqlite_data(db_name)
    if df.empty:
        print("No data to migrate")
        return False

    # Analyze
    analyze_data(df)

    # Confirm
    if not force:
        print("\n" + "-" * 60)
        response = input("Proceed with migration? (y/n): ")
        if response.lower() != 'y':
            print("Migration cancelled")
            return False

    # Check existing data and create backup
    print("\nChecking Azure Blob Storage...")
    usage = get_storage_usage()
    if 'error' not in usage:
        print(f"Current storage usage: {usage['total_mb']:.2f} MB")
        if usage['files']:
            print("Creating backup of existing data...")
            create_backup()

    # Upload
    print(f"\nUploading to Azure Blob Storage...")
    success = upload_parquet(df, MASTER_FILE)

    if success:
        # Verify
        print("\nVerifying upload...")
        new_usage = get_storage_usage()
        if 'error' not in new_usage:
            print(f"New storage usage: {new_usage['total_mb']:.2f} MB")
            for f in new_usage['files']:
                print(f"  - {f['name']}: {f['size_mb']} MB")

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"\nData is now available at:")
        print(f"  Container: athletics-data")
        print(f"  File: {MASTER_FILE}")
        print(f"\nTo use in app:")
        print("  from blob_storage import load_data, query")
        print("  df = load_data()")
        print('  results = query("SELECT * FROM athletics_data WHERE nationality = \'KSA\'")')
    else:
        print("\nMigration FAILED")

    return success


def migrate_all_databases():
    """Migrate all SQLite databases to separate Parquet files."""
    print("=" * 60)
    print("MIGRATE ALL DATABASES TO AZURE BLOB STORAGE")
    print("=" * 60)

    if not BLOB_AVAILABLE or not _use_azure():
        print("Azure Blob Storage not configured")
        return

    results = {}

    for db_name, db_path in SQLITE_PATHS.items():
        if os.path.exists(db_path):
            print(f"\n{'=' * 40}")
            print(f"Migrating: {db_name}")
            print(f"{'=' * 40}")

            df = load_sqlite_data(db_name)
            if not df.empty:
                blob_path = f"{db_name}.parquet"
                success = upload_parquet(df, blob_path)
                results[db_name] = {'success': success, 'rows': len(df)}
            else:
                results[db_name] = {'success': False, 'rows': 0}
        else:
            print(f"\nSkipping {db_name}: {db_path} not found")
            results[db_name] = {'success': False, 'rows': 0, 'error': 'not found'}

    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    for db_name, result in results.items():
        status = "OK" if result.get('success') else "FAILED"
        rows = result.get('rows', 0)
        print(f"  {db_name}: {status} ({rows:,} rows)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Migrate SQLite to Azure Blob Storage')
    parser.add_argument('--db', type=str, default='deploy',
                        choices=['deploy', 'competitor', 'major', 'ksa', 'all'],
                        help='Database to migrate (default: deploy)')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Skip confirmation prompt')
    parser.add_argument('--test', '-t', action='store_true',
                        help='Test connection only')

    args = parser.parse_args()

    if args.test:
        print("Testing Azure Blob Storage connection...")
        if _use_azure():
            usage = get_storage_usage()
            if 'error' not in usage:
                print(f"Connection: SUCCESS")
                print(f"Storage: {usage['total_mb']:.2f} MB used")
            else:
                print(f"Connection: FAILED - {usage['error']}")
        else:
            print("Azure not configured")
    elif args.db == 'all':
        migrate_all_databases()
    else:
        migrate_to_blob(args.db, args.force)
