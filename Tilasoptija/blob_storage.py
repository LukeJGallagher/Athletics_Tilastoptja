"""
Azure Blob Storage Module for Athletics Dashboard
Supports Parquet files with DuckDB queries

Replaces Azure SQL with simpler Blob Storage + Parquet approach:
- No ODBC driver issues
- No serverless wake-up delays
- Faster queries with DuckDB
- 5 GB free tier
"""

import os
import pandas as pd
from datetime import datetime
from typing import Optional
from io import BytesIO

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Azure imports
try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("Warning: azure-storage-blob not installed. Run: pip install azure-storage-blob")

# DuckDB import
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    print("Warning: duckdb not installed. Run: pip install duckdb")


# =============================================================================
# CONFIGURATION - ATHLETICS PROJECT
# =============================================================================

CONTAINER_NAME = "athletics-data"
MASTER_FILE = "athletics_master.parquet"
STORAGE_ACCOUNT_URL = "https://tilastoptija.blob.core.windows.net/"

# Local SQLite paths (for migration)
LOCAL_SQLITE_PATHS = {
    'deploy': 'SQL/athletics_deploy.db',
    'competitor': 'SQL/athletics_competitor.db',
    'major': 'SQL/major_championships.db',
    'ksa': 'SQL/ksa_athletics.db',
}

# =============================================================================


# Connection string (lazy-loaded)
_CONN_STRING = None


def _get_connection_string() -> Optional[str]:
    """Get Azure Storage connection string from env or Streamlit secrets."""
    global _CONN_STRING

    if _CONN_STRING is not None:
        return _CONN_STRING

    # Try environment variable
    _CONN_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')

    # Try Streamlit secrets
    if not _CONN_STRING:
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'AZURE_STORAGE_CONNECTION_STRING' in st.secrets:
                _CONN_STRING = st.secrets['AZURE_STORAGE_CONNECTION_STRING']
        except:
            pass

    return _CONN_STRING


def _use_azure() -> bool:
    """Check if Azure should be used."""
    if os.getenv('FORCE_LOCAL_DATA', '').lower() in ('true', '1', 'yes'):
        return False
    return bool(_get_connection_string()) and AZURE_AVAILABLE


def get_storage_mode() -> str:
    """Return current storage mode: 'azure' or 'local'"""
    return 'azure' if _use_azure() else 'local'


def get_blob_service() -> Optional['BlobServiceClient']:
    """Get Azure Blob Service client."""
    if not AZURE_AVAILABLE:
        return None

    conn_str = _get_connection_string()
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)

    return None


def get_container_client(create_if_missing: bool = True):
    """Get container client."""
    blob_service = get_blob_service()
    if not blob_service:
        return None

    container = blob_service.get_container_client(CONTAINER_NAME)

    if create_if_missing:
        try:
            if not container.exists():
                container.create_container()
                print(f"Created container: {CONTAINER_NAME}")
        except Exception as e:
            print(f"Container check error: {e}")

    return container


def download_parquet(blob_path: str) -> Optional[pd.DataFrame]:
    """Download a parquet file from Azure."""
    container = get_container_client()
    if not container:
        return None

    try:
        blob_client = container.get_blob_client(blob_path)
        if not blob_client.exists():
            print(f"Blob not found: {blob_path}")
            return None
        data = blob_client.download_blob().readall()
        return pd.read_parquet(BytesIO(data))
    except Exception as e:
        print(f"Error downloading {blob_path}: {e}")
        return None


def _clean_dataframe_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame for Parquet compatibility."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('').astype(str)
            df[col] = df[col].replace('nan', '')
    return df


def upload_parquet(df: pd.DataFrame, blob_path: str, overwrite: bool = True) -> bool:
    """Upload DataFrame as parquet to Azure."""
    container = get_container_client()
    if not container:
        return False

    try:
        # Clean data
        df = _clean_dataframe_for_parquet(df)

        buffer = BytesIO()
        df.to_parquet(buffer, index=False, compression='gzip')
        buffer.seek(0)

        file_size_mb = buffer.getbuffer().nbytes / (1024 * 1024)
        print(f"Uploading {len(df):,} rows ({file_size_mb:.1f} MB)...")

        blob_client = container.get_blob_client(blob_path)
        blob_client.upload_blob(
            buffer,
            overwrite=overwrite,
            max_concurrency=4,
            timeout=600
        )
        print(f"Uploaded to {blob_path}")
        return True
    except Exception as e:
        print(f"Error uploading: {e}")
        return False


def create_backup() -> Optional[str]:
    """Create backup of master file."""
    container = get_container_client()
    if not container:
        return None

    try:
        blob_client = container.get_blob_client(MASTER_FILE)
        if not blob_client.exists():
            print("No master file to backup")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/backup_{timestamp}.parquet"

        backup_client = container.get_blob_client(backup_path)
        backup_client.start_copy_from_url(blob_client.url)

        print(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Backup error: {e}")
        return None


def load_data() -> pd.DataFrame:
    """Load athletics data from Azure (or local SQLite fallback)."""
    if _use_azure():
        print("Loading from Azure Blob Storage...")
        df = download_parquet(MASTER_FILE)
        if df is not None and not df.empty:
            print(f"Loaded {len(df):,} rows from Azure")
            return df
        print("Azure empty or unavailable, falling back to local...")

    return _load_local_sqlite()


def _load_local_sqlite(db_name: str = 'deploy') -> pd.DataFrame:
    """Load from local SQLite database (fallback)."""
    import sqlite3

    db_path = LOCAL_SQLITE_PATHS.get(db_name, LOCAL_SQLITE_PATHS['deploy'])

    if not os.path.exists(db_path):
        print(f"Local database not found: {db_path}")
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM athletics_data", conn)
        conn.close()
        print(f"Loaded {len(df):,} rows from local SQLite: {db_path}")
        return df
    except Exception as e:
        print(f"Error loading SQLite: {e}")
        return pd.DataFrame()


def save_data(df: pd.DataFrame, append: bool = False) -> bool:
    """Save data to Azure."""
    if not _use_azure():
        print("Azure not configured, saving locally")
        df.to_parquet('data.parquet', index=False)
        return True

    if append:
        existing = download_parquet(MASTER_FILE)
        if existing is not None and not existing.empty:
            df = pd.concat([existing, df], ignore_index=True)

    return upload_parquet(df, MASTER_FILE)


def migrate_sqlite_to_azure(db_name: str = 'deploy') -> bool:
    """Migrate local SQLite database to Azure Blob Storage as Parquet."""
    print("=" * 60)
    print("MIGRATING SQLITE TO AZURE BLOB STORAGE (PARQUET)")
    print("=" * 60)

    df = _load_local_sqlite(db_name)
    if df.empty:
        print("No data to migrate")
        return False

    print(f"\nData summary:")
    print(f"  Rows: {len(df):,}")
    print(f"  Columns: {len(df.columns)}")

    # Create backup first
    create_backup()

    # Upload
    success = upload_parquet(df, MASTER_FILE)

    if success:
        print(f"\nMigration complete: {len(df):,} rows uploaded as Parquet")

    return success


def get_storage_usage() -> dict:
    """Get storage usage statistics."""
    container = get_container_client(create_if_missing=False)
    if not container:
        return {'error': 'Not connected'}

    try:
        total_size = 0
        files = []

        for blob in container.list_blobs():
            size_mb = blob.size / (1024 * 1024)
            total_size += blob.size
            files.append({'name': blob.name, 'size_mb': round(size_mb, 2)})

        return {
            'total_mb': round(total_size / (1024 * 1024), 2),
            'total_gb': round(total_size / (1024 * 1024 * 1024), 3),
            'free_tier_limit_gb': 5,
            'percent_used': round((total_size / (5 * 1024 * 1024 * 1024)) * 100, 1),
            'files': files
        }
    except Exception as e:
        return {'error': str(e)}


# =============================================================================
# DUCKDB QUERY SUPPORT
# =============================================================================

_duckdb_conn = None
_duckdb_ready = False


def get_duckdb_connection():
    """Get DuckDB connection with data loaded."""
    global _duckdb_conn, _duckdb_ready

    if not DUCKDB_AVAILABLE:
        print("DuckDB not available")
        return None

    if _duckdb_conn is not None and _duckdb_ready:
        return _duckdb_conn

    try:
        _duckdb_conn = duckdb.connect(':memory:')

        print("Loading data into DuckDB...")
        df = load_data()

        if df.empty:
            print("No data available")
            return None

        _duckdb_conn.register('athletics_data', df)
        _duckdb_ready = True

        print(f"DuckDB ready with {len(df):,} rows in 'athletics_data' table")
        return _duckdb_conn

    except Exception as e:
        print(f"DuckDB error: {e}")
        return None


def query(sql: str) -> Optional[pd.DataFrame]:
    """Execute SQL query against athletics data.

    The data is available as the 'athletics_data' table.

    Examples:
        query("SELECT * FROM athletics_data LIMIT 10")
        query("SELECT eventname, COUNT(*) FROM athletics_data GROUP BY eventname")
        query("SELECT * FROM athletics_data WHERE nationality = 'KSA'")
    """
    conn = get_duckdb_connection()
    if conn is None:
        return None

    try:
        return conn.execute(sql).fetchdf()
    except Exception as e:
        print(f"Query error: {e}")
        return None


def refresh_data():
    """Reload data from Azure into DuckDB."""
    global _duckdb_conn, _duckdb_ready

    if _duckdb_conn is not None:
        _duckdb_conn.close()
    _duckdb_conn = None
    _duckdb_ready = False

    return get_duckdb_connection()


# =============================================================================
# TEST CONNECTION
# =============================================================================

def test_connection() -> dict:
    """Test Azure Blob Storage connectivity."""
    result = {
        'mode': get_storage_mode(),
        'azure_configured': bool(_get_connection_string()),
        'azure_available': AZURE_AVAILABLE,
        'duckdb_available': DUCKDB_AVAILABLE,
        'connection_test': 'not_run',
        'error': None
    }

    if _use_azure():
        try:
            usage = get_storage_usage()
            if 'error' not in usage:
                result['connection_test'] = 'success'
                result['storage_usage'] = usage
            else:
                result['connection_test'] = 'failed'
                result['error'] = usage['error']
        except Exception as e:
            result['connection_test'] = 'failed'
            result['error'] = str(e)
    else:
        result['connection_test'] = 'skipped (local mode)'

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("AZURE BLOB STORAGE CONNECTION TEST")
    print("=" * 60)

    result = test_connection()
    print(f"\nStorage Mode: {result['mode']}")
    print(f"Azure Configured: {result['azure_configured']}")
    print(f"Azure SDK Available: {result['azure_available']}")
    print(f"DuckDB Available: {result['duckdb_available']}")
    print(f"Connection Test: {result['connection_test']}")

    if result.get('error'):
        print(f"Error: {result['error']}")

    if result.get('storage_usage'):
        usage = result['storage_usage']
        print(f"\nStorage Usage: {usage['total_mb']:.2f} MB ({usage['percent_used']:.1f}% of 5 GB free tier)")
        if usage.get('files'):
            print("\nFiles:")
            for f in usage['files']:
                print(f"  - {f['name']}: {f['size_mb']} MB")

    print("\n" + "=" * 60)
