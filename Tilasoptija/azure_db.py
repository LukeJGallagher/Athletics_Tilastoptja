"""
Azure SQL Database Connection Module
=====================================

This module provides a unified interface for database operations that works with:
- Local SQLite (for development)
- Azure SQL (for production/cloud deployment)

The connection type is determined by the AZURE_SQL_CONN environment variable.
If set, uses Azure SQL. Otherwise, falls back to local SQLite.

Setup Instructions:
1. Create Azure SQL Database in Azure Portal
2. Get connection string from: Azure Portal > SQL Database > Connection Strings > ODBC
3. Add to GitHub Secrets as SQL_CONNECTION_STRING
4. Enable Azure firewall: SQL Server > Networking > "Allow Azure services"

Author: Team Saudi Athletics
"""

import os
import sqlite3
import pandas as pd
from typing import Optional, Union
from contextlib import contextmanager

# Try to import pyodbc for Azure SQL
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    print("Warning: pyodbc not installed. Azure SQL features disabled.")

# Try to import SQLAlchemy for better ORM support
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

# Database paths for local SQLite
LOCAL_DB_PATHS = {
    'deploy': 'SQL/athletics_deploy.db',
    'competitor': 'SQL/athletics_competitor.db',
    'major': 'SQL/major_championships.db',
    'ksa': 'SQL/ksa_athletics.db',
}

# Azure SQL connection string (lazy-loaded)
_AZURE_SQL_CONN = None

def _get_azure_conn_string():
    """Get Azure SQL connection string from env or Streamlit secrets (lazy-loaded)."""
    global _AZURE_SQL_CONN

    if _AZURE_SQL_CONN is not None:
        return _AZURE_SQL_CONN

    # Try environment variable first
    _AZURE_SQL_CONN = os.getenv('AZURE_SQL_CONN')

    # Try Streamlit secrets if not in environment
    if not _AZURE_SQL_CONN:
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'AZURE_SQL_CONN' in st.secrets:
                _AZURE_SQL_CONN = st.secrets['AZURE_SQL_CONN']
        except (ImportError, FileNotFoundError, KeyError, AttributeError):
            pass  # Streamlit not available or secrets not configured

    return _AZURE_SQL_CONN

# Legacy compatibility
AZURE_SQL_CONN = _get_azure_conn_string()

# Determine which mode we're in (re-evaluated each time)
def _use_azure():
    """Check if Azure SQL should be used."""
    return bool(_get_azure_conn_string()) and PYODBC_AVAILABLE

USE_AZURE = _use_azure()


# =============================================================================
# Connection Functions
# =============================================================================

def get_connection_mode() -> str:
    """Return current connection mode: 'azure' or 'sqlite'"""
    return 'azure' if _use_azure() else 'sqlite'


@contextmanager
def get_azure_connection():
    """
    Context manager for Azure SQL connections.

    Usage:
        with get_azure_connection() as conn:
            df = pd.read_sql("SELECT * FROM athletics_data", conn)
    """
    if not PYODBC_AVAILABLE:
        raise ImportError("pyodbc is required for Azure SQL connections. Install with: pip install pyodbc")

    conn_str = _get_azure_conn_string()
    if not conn_str:
        raise ValueError("AZURE_SQL_CONN not found in environment or Streamlit secrets")

    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_sqlite_connection(db_name: str = 'deploy'):
    """
    Context manager for SQLite connections.

    Args:
        db_name: One of 'deploy', 'competitor', 'major', 'ksa'

    Usage:
        with get_sqlite_connection('deploy') as conn:
            df = pd.read_sql("SELECT * FROM athletics_data", conn)
    """
    if db_name not in LOCAL_DB_PATHS:
        raise ValueError(f"Unknown database: {db_name}. Choose from: {list(LOCAL_DB_PATHS.keys())}")

    db_path = LOCAL_DB_PATHS[db_name]
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_connection(db_name: str = 'deploy'):
    """
    Universal connection context manager.
    Automatically uses Azure SQL if configured, otherwise SQLite.

    Args:
        db_name: Database name (only used for SQLite mode)

    Usage:
        with get_connection() as conn:
            df = pd.read_sql("SELECT * FROM athletics_data", conn)
    """
    if _use_azure():
        with get_azure_connection() as conn:
            yield conn
    else:
        with get_sqlite_connection(db_name) as conn:
            yield conn


def get_sqlalchemy_engine(db_name: str = 'deploy') -> Optional['Engine']:
    """
    Get SQLAlchemy engine for advanced ORM operations.

    Returns SQLAlchemy engine or None if not available.
    """
    if not SQLALCHEMY_AVAILABLE:
        return None

    if _use_azure():
        # Azure SQL connection string for SQLAlchemy
        # Format: mssql+pyodbc:///?odbc_connect=<connection_string>
        from urllib.parse import quote_plus
        conn_str = _get_azure_conn_string()
        if conn_str:
            conn_str_encoded = quote_plus(conn_str)
            return create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str_encoded}")
        return None
    else:
        # SQLite connection
        db_path = LOCAL_DB_PATHS.get(db_name, LOCAL_DB_PATHS['deploy'])
        return create_engine(f"sqlite:///{db_path}")


# =============================================================================
# Data Operations
# =============================================================================

def query_data(sql: str, db_name: str = 'deploy', params: tuple = None) -> pd.DataFrame:
    """
    Execute a SQL query and return results as DataFrame.

    Args:
        sql: SQL query string
        db_name: Database name (only used for SQLite mode)
        params: Optional query parameters

    Returns:
        pandas DataFrame with query results
    """
    with get_connection(db_name) as conn:
        if params:
            return pd.read_sql(sql, conn, params=params)
        return pd.read_sql(sql, conn)


def execute_sql(sql: str, db_name: str = 'deploy', params: tuple = None) -> int:
    """
    Execute a SQL statement (INSERT, UPDATE, DELETE).

    Args:
        sql: SQL statement
        db_name: Database name (only used for SQLite mode)
        params: Optional query parameters

    Returns:
        Number of rows affected
    """
    with get_connection(db_name) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        return cursor.rowcount


def insert_dataframe(df: pd.DataFrame, table_name: str, db_name: str = 'deploy',
                     if_exists: str = 'append') -> int:
    """
    Insert a DataFrame into a database table.

    Args:
        df: DataFrame to insert
        table_name: Target table name
        db_name: Database name (only used for SQLite mode)
        if_exists: 'append', 'replace', or 'fail'

    Returns:
        Number of rows inserted
    """
    with get_connection(db_name) as conn:
        rows_before = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table_name}", conn)['cnt'].iloc[0]
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        rows_after = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table_name}", conn)['cnt'].iloc[0]
        return rows_after - rows_before


# =============================================================================
# Azure SQL Specific Operations
# =============================================================================

def create_azure_table_from_sqlite(sqlite_db: str = 'deploy', table_name: str = 'athletics_data'):
    """
    Create Azure SQL table with same schema as SQLite table.
    Run this once during initial setup.
    """
    if not _use_azure():
        print("Azure SQL not configured. Set AZURE_SQL_CONN environment variable.")
        return

    # Read SQLite schema
    with get_sqlite_connection(sqlite_db) as sqlite_conn:
        # Get column info
        cursor = sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

    # Map SQLite types to SQL Server types
    type_map = {
        'TEXT': 'NVARCHAR(500)',
        'INTEGER': 'INT',
        'REAL': 'FLOAT',
        'BLOB': 'VARBINARY(MAX)',
        '': 'NVARCHAR(500)',  # Default
    }

    # Build CREATE TABLE statement
    col_defs = []
    for col in columns:
        col_name = col[1]
        col_type = col[2].upper() if col[2] else ''
        sql_type = type_map.get(col_type, 'NVARCHAR(500)')
        col_defs.append(f"[{col_name}] {sql_type}")

    create_sql = f"CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n)"

    print(f"Creating Azure SQL table with schema:\n{create_sql}")

    with get_azure_connection() as azure_conn:
        cursor = azure_conn.cursor()
        # Drop if exists
        cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}")
        cursor.execute(create_sql)
        azure_conn.commit()

    print(f"Table {table_name} created successfully in Azure SQL!")


def migrate_sqlite_to_azure(sqlite_db: str = 'deploy', table_name: str = 'athletics_data',
                            batch_size: int = 10000):
    """
    Migrate data from SQLite to Azure SQL in batches.

    Args:
        sqlite_db: Source SQLite database name
        table_name: Table to migrate
        batch_size: Number of rows per batch (for memory efficiency)
    """
    if not _use_azure():
        print("Azure SQL not configured. Set AZURE_SQL_CONN environment variable.")
        return

    print(f"Migrating {table_name} from {sqlite_db} to Azure SQL...")

    # Count total rows
    with get_sqlite_connection(sqlite_db) as conn:
        total_rows = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table_name}", conn)['cnt'].iloc[0]

    print(f"Total rows to migrate: {total_rows:,}")

    # Migrate in batches
    offset = 0
    migrated = 0

    while offset < total_rows:
        with get_sqlite_connection(sqlite_db) as sqlite_conn:
            batch_df = pd.read_sql(
                f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}",
                sqlite_conn
            )

        if batch_df.empty:
            break

        with get_azure_connection() as azure_conn:
            batch_df.to_sql(table_name, azure_conn, if_exists='append', index=False)

        migrated += len(batch_df)
        offset += batch_size
        print(f"  Migrated {migrated:,} / {total_rows:,} rows ({100*migrated/total_rows:.1f}%)")

    print(f"Migration complete! {migrated:,} rows transferred to Azure SQL.")


def sync_new_records_to_azure(new_records: pd.DataFrame, table_name: str = 'athletics_data'):
    """
    Sync new records from daily scrape to Azure SQL.
    Called by daily_sync.py after fetching new data.

    Args:
        new_records: DataFrame with new records to insert
        table_name: Target table name

    Returns:
        Number of rows inserted
    """
    if not _use_azure():
        print("Azure SQL not configured. Skipping sync.")
        return 0

    if new_records.empty:
        print("No new records to sync.")
        return 0

    with get_azure_connection() as conn:
        new_records.to_sql(table_name, conn, if_exists='append', index=False)
        print(f"Synced {len(new_records)} new records to Azure SQL.")
        return len(new_records)


# =============================================================================
# Testing & Diagnostics
# =============================================================================

def test_connection() -> dict:
    """
    Test database connectivity and return diagnostic info.

    Returns:
        Dict with connection status and info
    """
    result = {
        'mode': get_connection_mode(),
        'azure_configured': bool(_get_azure_conn_string()),
        'pyodbc_available': PYODBC_AVAILABLE,
        'sqlalchemy_available': SQLALCHEMY_AVAILABLE,
        'connection_test': 'not_run',
        'row_count': None,
        'error': None
    }

    try:
        with get_connection() as conn:
            df = pd.read_sql("SELECT COUNT(*) as cnt FROM athletics_data", conn)
            result['connection_test'] = 'success'
            result['row_count'] = int(df['cnt'].iloc[0])
    except Exception as e:
        result['connection_test'] = 'failed'
        result['error'] = str(e)

    return result


# =============================================================================
# Main (for testing)
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Azure SQL Database Connection Module - Test")
    print("=" * 60)

    # Run connection test
    test_result = test_connection()

    print(f"\nConnection Mode: {test_result['mode']}")
    print(f"Azure Configured: {test_result['azure_configured']}")
    print(f"pyodbc Available: {test_result['pyodbc_available']}")
    print(f"SQLAlchemy Available: {test_result['sqlalchemy_available']}")
    print(f"Connection Test: {test_result['connection_test']}")

    if test_result['row_count']:
        print(f"Row Count: {test_result['row_count']:,}")

    if test_result['error']:
        print(f"Error: {test_result['error']}")

    print("\n" + "=" * 60)
