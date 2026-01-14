"""
Download Full Tilastopaja Historical Data
Downloads the complete ksaoutput_full.csv file with all historical results
"""

import requests
import os
from datetime import datetime

# Tilastopaja full data URL
FULL_DATA_URL = "https://www.tilastopaja.com/json/ksa/ksaoutput_full.csv"
OUTPUT_DIR = "Tilastoptja_Data"
OUTPUT_FILE = "ksaoutput_full.csv"

def download_full_data():
    """Download the complete historical data CSV file."""

    print("=" * 70)
    print("DOWNLOAD TILASTOPAJA FULL HISTORICAL DATA")
    print("=" * 70)

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"\n✓ Created directory: {OUTPUT_DIR}/")

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

    # Check if file already exists
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        mod_time = datetime.fromtimestamp(os.path.getmtime(output_path))
        print(f"\n⚠️  File already exists:")
        print(f"   Path: {output_path}")
        print(f"   Size: {file_size:.1f} MB")
        print(f"   Last modified: {mod_time}")

        overwrite = input("\n   Overwrite? (yes/no): ")
        if overwrite.lower() != 'yes':
            print("\n✓ Using existing file")
            return output_path

    # Download the file
    print(f"\n[1/2] Downloading from: {FULL_DATA_URL}")
    print("   This may take several minutes for ~13 million rows...")

    try:
        response = requests.get(FULL_DATA_URL, stream=True, timeout=300)
        response.raise_for_status()

        # Get total file size if available
        total_size = int(response.headers.get('content-length', 0))

        # Download with progress
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = 100 * downloaded / total_size
                        mb_downloaded = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(f"   Progress: {mb_downloaded:.1f}/{mb_total:.1f} MB ({progress:.1f}%)", end='\r')

        print()  # New line after progress

        # Verify download
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n[2/2] Download complete!")
        print(f"   File: {output_path}")
        print(f"   Size: {final_size:.1f} MB")

        return output_path

    except requests.exceptions.RequestException as e:
        print(f"\n✗ Download failed: {e}")
        return None
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return None

def verify_csv_format(file_path):
    """Quick verification of CSV format and row count."""

    print("\n" + "=" * 70)
    print("VERIFYING CSV FORMAT")
    print("=" * 70)

    try:
        # Read first few lines to check format
        with open(file_path, 'r', encoding='utf-8') as f:
            header = f.readline().strip()
            first_row = f.readline().strip()

        print(f"\n✓ File is readable")
        print(f"✓ Header columns: {len(header.split(';'))} columns")
        print(f"✓ Delimiter: semicolon (;)")

        # Count total lines (approximate row count)
        print(f"\n⏳ Counting rows (this may take a minute)...")

        with open(file_path, 'r', encoding='utf-8') as f:
            row_count = sum(1 for _ in f) - 1  # Subtract header

        print(f"✓ Total rows: {row_count:,}")

        # Show sample columns
        print(f"\nSample column names:")
        columns = header.split(';')[:10]
        for idx, col in enumerate(columns, 1):
            print(f"  {idx:2d}. {col}")

        if row_count < 1000000:
            print(f"\n⚠️  WARNING: Expected ~13 million rows, got {row_count:,}")
            print("   File may be incomplete or corrupted")
        else:
            print(f"\n✓ Row count looks reasonable")

        return True

    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        return False

if __name__ == "__main__":
    # Download the full data
    file_path = download_full_data()

    if file_path:
        # Verify the downloaded file
        if verify_csv_format(file_path):
            print("\n" + "=" * 70)
            print("SUCCESS - Full data downloaded and verified!")
            print("=" * 70)
            print(f"\nNext steps:")
            print(f"1. Run: python rebuild_all_data.py --deploy")
            print(f"   This builds the SQLite database from the CSV")
            print(f"2. Run: python rebuild_azure_from_sqlite.py")
            print(f"   This migrates the clean data to Azure SQL")
        else:
            print("\n⚠️  Download succeeded but verification failed")
            print("   Check the file manually before proceeding")
    else:
        print("\n✗ Download failed - see errors above")
