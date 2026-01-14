"""
Rebuild Azure SQL Database from Clean SQLite
Drops all data in Azure SQL and repopulates from local athletics_deploy.db
"""

from dotenv import load_dotenv
load_dotenv()

from azure_db import get_azure_connection, get_sqlite_connection
import pandas as pd
import sys

def main():
    print("=" * 70)
    print("REBUILD AZURE SQL FROM CLEAN SQLITE")
    print("=" * 70)

    # Step 1: Verify local SQLite
    print("\n[1/5] Verifying local SQLite database...")
    with get_sqlite_connection('deploy') as sqlite_conn:
        count_df = pd.read_sql("SELECT COUNT(*) as cnt FROM athletics_data", sqlite_conn)
        sqlite_rows = int(count_df['cnt'].iloc[0])
        print(f"   ✓ Local SQLite has {sqlite_rows:,} rows")

        # Sample check
        sample_df = pd.read_sql("SELECT DISTINCT eventname FROM athletics_data LIMIT 5", sqlite_conn)
        print(f"   ✓ Sample events: {', '.join(sample_df['eventname'].tolist())}")

    # Step 2: Connect to Azure
    print("\n[2/5] Connecting to Azure SQL...")
    try:
        with get_azure_connection() as azure_conn:
            cursor = azure_conn.cursor()
            print("   ✓ Azure SQL connection successful")

            # Check current Azure data
            cursor.execute("SELECT COUNT(*) as cnt FROM athletics_data")
            azure_rows_before = cursor.fetchone()[0]
            print(f"   ⚠  Azure SQL currently has {azure_rows_before:,} rows (will be replaced)")
    except Exception as e:
        print(f"   ✗ Azure SQL connection failed: {e}")
        print("\nERROR: Cannot connect to Azure SQL. Check:")
        print("  1. Database is online (not paused)")
        print("  2. Firewall allows your IP")
        print("  3. Connection string in .env is correct")
        sys.exit(1)

    # Step 3: Confirm deletion
    print("\n[3/5] Preparing to delete existing Azure SQL data...")
    confirm = input(f"\n⚠️  This will DELETE all {azure_rows_before:,} rows in Azure SQL.\n   Type 'YES' to confirm: ")

    if confirm != 'YES':
        print("\nAborted. No changes made.")
        sys.exit(0)

    # Step 4: Delete existing data
    print("\n[4/5] Deleting existing Azure SQL data...")
    with get_azure_connection() as azure_conn:
        cursor = azure_conn.cursor()
        cursor.execute("DELETE FROM athletics_data")
        azure_conn.commit()
        print(f"   ✓ Deleted {azure_rows_before:,} rows from Azure SQL")

    # Step 5: Migrate data in batches
    print("\n[5/5] Migrating data from SQLite to Azure SQL...")

    BATCH_SIZE = 5000
    offset = 0
    migrated_total = 0

    with get_sqlite_connection('deploy') as sqlite_conn:
        while True:
            # Read batch from SQLite
            batch_df = pd.read_sql(
                f"SELECT * FROM athletics_data LIMIT {BATCH_SIZE} OFFSET {offset}",
                sqlite_conn
            )

            if batch_df.empty:
                break

            # Write batch to Azure SQL
            with get_azure_connection() as azure_conn:
                batch_df.to_sql('athletics_data', azure_conn, if_exists='append', index=False)

            migrated_total += len(batch_df)
            offset += BATCH_SIZE

            print(f"   Progress: {migrated_total:,} / {sqlite_rows:,} rows ({100*migrated_total/sqlite_rows:.1f}%)")

            if migrated_total >= sqlite_rows:
                break

    # Final verification
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)

    with get_azure_connection() as azure_conn:
        cursor = azure_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM athletics_data")
        final_count = cursor.fetchone()[0]

        print(f"\n✓ Azure SQL now has {final_count:,} rows")

        # Verify events
        cursor.execute("SELECT DISTINCT eventname FROM athletics_data ORDER BY eventname")
        events = [row[0] for row in cursor.fetchall()[:10]]
        print(f"✓ Sample events: {', '.join(events[:5])}...")

        if final_count == sqlite_rows:
            print(f"\n✓ SUCCESS: All {sqlite_rows:,} rows migrated successfully!")
        else:
            print(f"\n⚠  WARNING: Expected {sqlite_rows:,} rows but got {final_count:,}")

if __name__ == "__main__":
    main()
