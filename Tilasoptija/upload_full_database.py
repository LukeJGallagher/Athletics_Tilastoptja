"""
Upload Full Athletics Database to Azure Blob Storage

Converts the full CSV (8.8M rows) to Parquet and uploads to Azure.
This database is used for Competitor Analysis only.

Usage:
    python upload_full_database.py
"""

import os
import pandas as pd
from datetime import datetime

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from blob_storage import upload_parquet, FULL_FILE, _use_azure, get_container_client

# Source CSV
CSV_PATH = 'Tilastoptja_Data/ksaoutput_full_new.csv'


def _upload_parquet_file(file_path: str, blob_name: str) -> bool:
    """Upload a Parquet file directly to Azure (avoids DataFrame memory copy)."""
    container = get_container_client()
    if not container:
        print("ERROR: Could not get Azure container client")
        return False

    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"Uploading {file_size_mb:.1f} MB file...")

        blob_client = container.get_blob_client(blob_name)

        with open(file_path, 'rb') as f:
            blob_client.upload_blob(
                f,
                overwrite=True,
                max_concurrency=4,
                timeout=600
            )

        print(f"Upload complete: {blob_name}")
        return True
    except Exception as e:
        print(f"Upload error: {e}")
        return False

# Pre-compute columns for faster loading
def parse_result(value, event):
    """Parse athletic result to numeric value."""
    import re
    EVENT_TYPE_MAP = {
        '100m': 'time', '200m': 'time', '400m': 'time', '800m': 'time',
        '1500m': 'time', '5000m': 'time', '10000m': 'time', 'Marathon': 'time',
        '100m Hurdles': 'time', '110m Hurdles': 'time', '400m Hurdles': 'time',
        '3000m Steeplechase': 'time',
        '4x100m Relay': 'time', '4x400m Relay': 'time',
        '20km Race Walk': 'time', '50km Race Walk': 'time',
        'High Jump': 'distance', 'Pole Vault': 'distance',
        'Long Jump': 'distance', 'Triple Jump': 'distance',
        'Shot Put': 'distance', 'Discus Throw': 'distance',
        'Hammer Throw': 'distance', 'Javelin Throw': 'distance',
        'Decathlon': 'points', 'Heptathlon': 'points',
    }
    try:
        if not isinstance(value, str) or not value.strip():
            return None
        value = value.strip().upper()
        value = re.sub(r"^[^\d:-]+", "", value)
        value = value.replace('A', '').replace('H', '').strip()
        if value in {'DNF', 'DNS', 'DQ', 'NM', ''}:
            return None

        event_clean = (event or '').strip().replace("Indoor", "").strip()
        e_type = EVENT_TYPE_MAP.get(event, EVENT_TYPE_MAP.get(event_clean, 'time'))

        if e_type == 'time':
            parts = value.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            return float(value)
        elif e_type in {'distance', 'points'}:
            return float(value)
    except:
        return None
    return None


def main():
    print("=" * 60)
    print("UPLOADING FULL DATABASE TO AZURE BLOB STORAGE")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not _use_azure():
        print("\nERROR: Azure not configured. Set AZURE_STORAGE_CONNECTION_STRING.")
        return False

    if not os.path.exists(CSV_PATH):
        print(f"\nERROR: CSV file not found: {CSV_PATH}")
        return False

    # Get file size
    size_gb = os.path.getsize(CSV_PATH) / (1024**3)
    print(f"\nSource: {CSV_PATH}")
    print(f"Size: {size_gb:.2f} GB")

    # Load CSV in chunks to manage memory
    print("\nLoading CSV in chunks...")
    chunks = []
    total_rows = 0

    try:
        for i, chunk in enumerate(pd.read_csv(CSV_PATH, delimiter=';', chunksize=500000,
                                               low_memory=False, on_bad_lines='skip')):
            total_rows += len(chunk)
            chunks.append(chunk)
            print(f"  Loaded chunk {i+1}: {len(chunk):,} rows (total: {total_rows:,})")
    except Exception as e:
        print(f"  Warning: CSV parsing stopped early: {e}")
        print(f"  Continuing with {total_rows:,} rows loaded...")

    print(f"\nCombining {len(chunks)} chunks...")
    df = pd.concat(chunks, ignore_index=True)
    print(f"Total rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    # Pre-compute derived columns for faster app loading
    print("\nPre-computing derived columns...")

    # Fix mixed-type columns (object columns with mixed int/str) that cause Parquet errors
    # Must fillna BEFORE astype(str) to avoid PyArrow errors
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('').astype(str)
            # Replace 'nan' strings that may have been created
            df[col] = df[col].replace('nan', '')
    print(f"  Converted all object columns to string (fixes Parquet conversion)")

    # Clean competition ID
    if 'competitionid' in df.columns:
        df['competitionid'] = df['competitionid'].astype(str).str.replace('.0', '', regex=False)
        print(f"  Cleaned competitionid column")

    # Year from date
    if 'competitiondate' in df.columns:
        df['year'] = pd.to_datetime(df['competitiondate'], errors='coerce').dt.year
        print(f"  Added 'year' column")

    # WA Points to numeric
    if 'wapoints' in df.columns:
        df['wapoints'] = pd.to_numeric(df['wapoints'], errors='coerce')
        print(f"  Converted wapoints to numeric")

    # Note: result_numeric computation skipped - takes too long for 8.8M rows
    # The app will compute it on-demand when needed
    print(f"  Skipping result_numeric (computed on-demand in app)")

    # Convert to Parquet
    print(f"\nConverting to Parquet...")
    parquet_path = 'temp_full_upload.parquet'
    total_rows = len(df)  # Store count before deleting
    df.to_parquet(parquet_path, index=False, compression='snappy')

    parquet_size_mb = os.path.getsize(parquet_path) / (1024**2)
    print(f"Parquet size: {parquet_size_mb:.1f} MB")
    print(f"Compression ratio: {size_gb*1024/parquet_size_mb:.1f}x")

    # Free memory before upload
    del df
    import gc
    gc.collect()
    print("Memory freed for upload.")

    # Upload to Azure - directly from file to avoid memory issues
    print(f"\nUploading to Azure Blob Storage...")
    print(f"Target: {FULL_FILE}")

    # Direct upload from file (avoids DataFrame copy in upload_parquet)
    success = _upload_parquet_file(parquet_path, FULL_FILE)

    # Cleanup
    if os.path.exists(parquet_path):
        os.remove(parquet_path)

    if success:
        print("\n" + "=" * 60)
        print("UPLOAD COMPLETE!")
        print("=" * 60)
        print(f"File: {FULL_FILE}")
        print(f"Rows: {total_rows:,}")
        print(f"Size: {parquet_size_mb:.1f} MB")
        return True
    else:
        print("\nERROR: Upload failed!")
        return False


if __name__ == "__main__":
    main()
