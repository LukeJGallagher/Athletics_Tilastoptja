# Streamlit + Azure SQL Deployment Guide

**Complete guide for deploying Streamlit apps with Azure SQL backend to Streamlit Cloud**

## Overview

This guide walks you through deploying a Streamlit application that uses Azure SQL Database for cloud storage while maintaining local SQLite for development. Based on real-world troubleshooting of the Athletics Dashboard project.

## Architecture

```
Local Development          →    Streamlit Cloud Deployment
─────────────────                ──────────────────────────
SQLite databases                 Azure SQL Database
(.db files in SQL/)              (Cloud-hosted)

.env file                        Streamlit Secrets
(AZURE_SQL_CONN)                 (secrets.toml)
```

---

## Prerequisites

### 1. Azure Account
- Free tier available: https://azure.microsoft.com/free/
- You'll get $200 credit + 12 months free services

### 2. GitHub Account
- Repository must be public (for free Streamlit Cloud) or private (with Streamlit paid plan)

### 3. Streamlit Cloud Account
- Free account: https://share.streamlit.io/
- Link with your GitHub account

### 4. Local Development Environment
- Python 3.8+
- pip or conda

---

## Part 1: Azure SQL Database Setup

### Step 1: Create Azure SQL Database

1. **Go to Azure Portal**: https://portal.azure.com
2. **Search for "SQL databases"** in the top search bar
3. **Click "+ Create"**

**Fill in the form:**

| Field | Value | Notes |
|-------|-------|-------|
| **Resource group** | Create new: `your-project-rg` | Groups related resources |
| **Database name** | `your_database_name` | Use underscores, lowercase |
| **Server** | Create new | See server settings below |
| **Compute + storage** | Click "Configure database" | See compute settings below |
| **Backup storage** | Locally-redundant | Cheapest option |

**Server Settings (if creating new):**

| Field | Value |
|-------|-------|
| **Server name** | `your-server-name` (globally unique) |
| **Location** | Choose closest region |
| **Authentication** | SQL authentication |
| **Server admin login** | `your_admin_username` |
| **Password** | Strong password (save this!) |

**Compute Settings:**

1. Click "Configure database"
2. Select **Service tier**: Serverless
3. Select **Compute tier**: Select the **Free** option (if available)
   - 32GB storage
   - 100k vCore seconds/month
   - Auto-pauses after 1 hour idle
4. Click "Apply"

4. **Click "Review + Create"** → **Create**
5. **Wait 2-5 minutes** for deployment

### Step 2: Configure Firewall

**CRITICAL: Without this, Streamlit Cloud cannot connect**

1. Go to your SQL Server (not database) in Azure Portal
2. Left menu: Click **"Networking"**
3. Under **"Firewall rules"**:
   - ✅ Check **"Allow Azure services and resources to access this server"**
   - Click **"+ Add your client IPv4 address"** (for local testing)
   - For Streamlit Cloud, add rule:
     - **Name**: `Streamlit-Cloud-Wide`
     - **Start IP**: `0.0.0.0`
     - **End IP**: `255.255.255.255`
4. **Click "Save"**

⚠️ **Security Note**: The 0.0.0.0-255.255.255.255 rule allows all IPs. This is acceptable for non-sensitive data or initial testing. For production, narrow this after identifying Streamlit Cloud's actual IPs in Azure's connection logs.

### Step 3: Get Connection String

1. **Go to your database** (not server) in Azure Portal
2. Left menu: Click **"Connection strings"**
3. Click **"ODBC"** tab
4. **Copy the connection string** (looks like this):

```
Driver={ODBC Driver 18 for SQL Server};Server=tcp:your-server.database.windows.net,1433;Database=your_database;Uid=your_admin;Pwd={your_password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

5. **Replace `{your_password}` with your actual password**

⚠️ **IMPORTANT**: Change **Driver 18** to **Driver 17** for Streamlit Cloud:

```
Driver={ODBC Driver 17 for SQL Server};Server=tcp:your-server.database.windows.net,1433;Database=your_database;Uid=your_admin;Pwd=YourActualPassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

### Step 4: Create Database Schema

1. In Azure Portal, go to your database
2. Left menu: Click **"Query editor (preview)"**
3. Login with your admin credentials
4. **Run your CREATE TABLE statements**

Example:
```sql
CREATE TABLE your_table_name (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(500),
    value FLOAT,
    date DATE,
    -- Add your columns here
);
```

5. Verify with: `SELECT COUNT(*) FROM your_table_name;`

---

## Part 2: Python Application Setup

### Step 1: Install Dependencies

Add to `requirements.txt`:

```txt
# Core
streamlit>=1.30.0
pandas>=2.0.0
numpy>=1.24.0

# Database
pyodbc>=5.0.0
sqlalchemy>=2.0.0

# Environment variables
python-dotenv>=1.0.0
```

Install locally:
```bash
pip install -r requirements.txt
```

### Step 2: Create Database Connection Module

Create `azure_db.py`:

```python
"""
Azure SQL Database Connection Module
Supports both local SQLite (development) and Azure SQL (production)
"""

import os
import sqlite3
import pandas as pd
from typing import Optional
from contextlib import contextmanager

# Try to import pyodbc for Azure SQL
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    print("Warning: pyodbc not installed. Azure SQL features disabled.")

# Database paths for local SQLite
LOCAL_DB_PATHS = {
    'main': 'database/main.db',
    # Add your database files here
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
            pass

    return _AZURE_SQL_CONN

def _use_azure():
    """Check if Azure SQL should be used."""
    return bool(_get_azure_conn_string()) and PYODBC_AVAILABLE

def get_connection_mode() -> str:
    """Return current connection mode: 'azure' or 'sqlite'"""
    return 'azure' if _use_azure() else 'sqlite'

@contextmanager
def get_azure_connection():
    """Context manager for Azure SQL connections."""
    if not PYODBC_AVAILABLE:
        raise ImportError("pyodbc is required for Azure SQL connections")

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
def get_sqlite_connection(db_name: str = 'main'):
    """Context manager for SQLite connections."""
    if db_name not in LOCAL_DB_PATHS:
        raise ValueError(f"Unknown database: {db_name}")

    db_path = LOCAL_DB_PATHS[db_name]
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    finally:
        if conn:
            conn.close()

@contextmanager
def get_connection(db_name: str = 'main'):
    """
    Universal connection context manager.
    Automatically uses Azure SQL if configured, otherwise SQLite.
    """
    if _use_azure():
        with get_azure_connection() as conn:
            yield conn
    else:
        with get_sqlite_connection(db_name) as conn:
            yield conn

def query_data(sql: str, db_name: str = 'main', params: tuple = None) -> pd.DataFrame:
    """
    Execute a SQL query and return results as DataFrame.
    Works with both Azure SQL and SQLite.
    """
    with get_connection(db_name) as conn:
        if params:
            return pd.read_sql(sql, conn, params=params)
        return pd.read_sql(sql, conn)

def test_connection() -> dict:
    """Test database connectivity and return diagnostic info."""
    result = {
        'mode': get_connection_mode(),
        'azure_configured': bool(_get_azure_conn_string()),
        'pyodbc_available': PYODBC_AVAILABLE,
        'connection_test': 'not_run',
        'error': None
    }

    try:
        with get_connection() as conn:
            # Test with a simple query (adjust table name as needed)
            df = pd.read_sql("SELECT COUNT(*) as cnt FROM your_table_name", conn)
            result['connection_test'] = 'success'
            result['row_count'] = int(df['cnt'].iloc[0])
    except Exception as e:
        result['connection_test'] = 'failed'
        result['error'] = str(e)

    return result
```

### Step 3: Update Your Streamlit App

In your `app.py` or main application file:

```python
import streamlit as st
from azure_db import query_data, get_connection_mode

# Show connection mode (optional - for debugging)
st.sidebar.info(f"Database: {get_connection_mode()}")

# Load data using the unified function
@st.cache_data(ttl=3600)
def load_data():
    """Load data from database (Azure SQL or SQLite)."""
    try:
        df = query_data("SELECT * FROM your_table_name")
        return df
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return pd.DataFrame()

# Use the data
df = load_data()
st.dataframe(df)
```

### Step 4: Configure Local Environment

Create `.env` file (local development only):

```bash
# Azure SQL Connection (for local testing)
AZURE_SQL_CONN=Driver={ODBC Driver 17 for SQL Server};Server=tcp:your-server.database.windows.net,1433;Database=your_database;Uid=your_admin;Pwd=YourPassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

Update your app to load `.env`:

```python
from dotenv import load_dotenv
load_dotenv()  # Add at the top of your main app file
```

**⚠️ IMPORTANT**: Add `.env` to `.gitignore`:

```bash
# .gitignore
.env
*.db
database/
SQL/
```

### Step 5: Create Streamlit Secrets Template

Create `.streamlit/secrets.toml.example`:

```toml
# Streamlit Cloud Secrets Template
# On Streamlit Cloud: Settings > Secrets

# Azure SQL Database (REQUIRED for Streamlit Cloud)
# Use ODBC Driver 17 for compatibility
AZURE_SQL_CONN = "Driver={ODBC Driver 17 for SQL Server};Server=tcp:your-server.database.windows.net,1433;Database=your_database;Uid=your_admin;Pwd=YOUR_PASSWORD;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```

**Add to `.gitignore`**:
```bash
.streamlit/secrets.toml
```

---

## Part 3: Populate Azure SQL Database

### Option 1: Migrate from Local SQLite

If you have local SQLite databases with data:

```python
# migrate_to_azure.py
from azure_db import get_azure_connection, get_sqlite_connection
import pandas as pd

def migrate_data(sqlite_db_name='main', table_name='your_table_name'):
    """Migrate data from SQLite to Azure SQL."""

    # Read from SQLite
    with get_sqlite_connection(sqlite_db_name) as sqlite_conn:
        df = pd.read_sql(f"SELECT * FROM {table_name}", sqlite_conn)

    print(f"Read {len(df):,} rows from SQLite")

    # Write to Azure SQL
    with get_azure_connection() as azure_conn:
        df.to_sql(table_name, azure_conn, if_exists='append', index=False)

    print(f"Migrated {len(df):,} rows to Azure SQL")

if __name__ == "__main__":
    migrate_data()
```

Run locally:
```bash
python migrate_to_azure.py
```

### Option 2: Direct Data Upload

Use Azure Portal Query Editor to insert data, or use a Python script:

```python
import pandas as pd
from azure_db import get_azure_connection

df = pd.read_csv('your_data.csv')

with get_azure_connection() as conn:
    df.to_sql('your_table_name', conn, if_exists='append', index=False)
```

---

## Part 4: GitHub Repository Setup

### Step 1: Prepare Repository

**Files to commit**:
```
your-project/
├── .gitignore              # Exclude secrets and local databases
├── requirements.txt        # Python dependencies
├── azure_db.py            # Database connection module
├── app.py                 # Your Streamlit app
├── .streamlit/
│   └── secrets.toml.example  # Template (NOT actual secrets)
└── README.md              # Project documentation
```

**Files to EXCLUDE** (add to `.gitignore`):
```bash
# Environment
.env

# Databases (too large, contains data)
*.db
database/
SQL/

# Secrets (NEVER commit)
.streamlit/secrets.toml

# Python
__pycache__/
*.pyc
.pytest_cache/

# IDE
.vscode/
.idea/
```

### Step 2: Commit and Push

```bash
git add .
git commit -m "Initial commit for Streamlit + Azure SQL deployment"
git push origin main
```

### Step 3: Verify on GitHub

Go to your GitHub repository and confirm:
- ✅ `azure_db.py` exists
- ✅ `requirements.txt` exists
- ✅ `.streamlit/secrets.toml.example` exists
- ❌ `.env` does NOT exist (should be gitignored)
- ❌ `.db` files do NOT exist (should be gitignored)
- ❌ `.streamlit/secrets.toml` does NOT exist (should be gitignored)

---

## Part 5: Streamlit Cloud Deployment

### Step 1: Create Streamlit Cloud App

1. Go to https://share.streamlit.io/
2. Click **"New app"**
3. Connect your GitHub account (if not already)
4. Select:
   - **Repository**: Your GitHub repo
   - **Branch**: `main` (or your default branch)
   - **Main file path**: `app.py` (or your main app file)
5. Click **"Deploy"** (will fail initially - this is expected)

### Step 2: Add Secrets

1. In Streamlit Cloud, go to your app
2. Click the **"⋮"** menu → **"Settings"**
3. Go to **"Secrets"** section
4. Paste your connection string in TOML format:

```toml
AZURE_SQL_CONN = "Driver={ODBC Driver 17 for SQL Server};Server=tcp:your-server.database.windows.net,1433;Database=your_database;Uid=your_admin;Pwd=YourActualPassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```

5. Click **"Save"**
6. App will automatically redeploy (2-3 minutes)

### Step 3: Monitor Deployment

1. Watch the deployment logs in real-time
2. Look for:
   - ✅ Dependencies installing successfully
   - ✅ App starting without errors
   - ✅ Database connection mode: "azure"

---

## Troubleshooting Common Issues

### Issue 1: ModuleNotFoundError

**Error**: `ModuleNotFoundError: No module named 'your_module'`

**Cause**: File exists locally but not in GitHub

**Fix**:
```bash
git add your_module.py
git commit -m "Add missing module"
git push origin main
```

### Issue 2: ODBC Driver Not Found

**Error**: `Can't open lib 'ODBC Driver 18 for SQL Server'`

**Cause**: Streamlit Cloud has Driver 17, not Driver 18

**Fix**: Update connection string to use **Driver 17**:
```
Driver={ODBC Driver 17 for SQL Server};...
```

Update in:
- `.env` (local)
- `.streamlit/secrets.toml.example` (template)
- Streamlit Cloud secrets (actual deployment)

### Issue 3: Secrets Not Detected

**Error**: `Available secrets: []` or `KeyError: 'AZURE_SQL_CONN'`

**Cause**: Trying to load secrets at module import time (too early)

**Fix**: Use lazy-loading pattern (shown in `azure_db.py` above)

Key concept:
```python
# ❌ BAD - loads at import time
import streamlit as st
AZURE_SQL_CONN = st.secrets['AZURE_SQL_CONN']  # Fails!

# ✅ GOOD - loads at runtime
def get_conn_string():
    import streamlit as st
    return st.secrets['AZURE_SQL_CONN']  # Works!
```

### Issue 4: Login Timeout

**Error**: `Login timeout expired (0) (SQLDriverConnect)`

**Cause**: Azure SQL firewall blocking Streamlit Cloud IPs

**Fix**:
1. Go to Azure Portal → SQL Server → Networking
2. Add firewall rule:
   - Name: `Streamlit-Cloud`
   - Start IP: `0.0.0.0`
   - End IP: `255.255.255.255`
3. Click "Save"
4. Wait 1-2 minutes, then reboot Streamlit app

### Issue 5: Database Not Available

**Error**: `Database 'your_db' on server 'your_server' is not currently available`

**Cause**: Serverless database paused (auto-pauses after 1 hour idle)

**Fix**:
1. Go to Azure Portal → Your database
2. Check status - if "Paused", click **"Resume"**
3. Wait 30-60 seconds for database to resume
4. Retry connection

**Prevention**:
- Set auto-pause delay to longer period (e.g., 7 days)
- Or disable auto-pause (uses more of free tier quota)

### Issue 6: Image/File Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'image.png'`

**Cause**: Image file exists locally but not in GitHub

**Fix**:
```bash
git add image.png
git commit -m "Add missing image asset"
git push origin main
```

### Issue 7: Data Not Loading

**Error**: App runs but shows empty/no data

**Cause**: Azure SQL database is empty (no data migrated)

**Fix**: Run migration script locally:
```bash
python migrate_to_azure.py
```

Or manually populate via Azure Portal Query Editor.

---

## Best Practices

### 1. **Never Commit Secrets**
- Always use `.gitignore` for `.env` and `secrets.toml`
- Use environment variables or Streamlit secrets
- Rotate passwords if accidentally committed

### 2. **Separate Dev and Prod**
- Local development: Use SQLite (fast, no cost)
- Cloud deployment: Use Azure SQL (scalable, accessible)
- Same code works for both via `azure_db.py`

### 3. **Use Lazy-Loading for Secrets**
- Don't access `st.secrets` at module import time
- Load secrets inside functions that run at runtime
- Handle missing secrets gracefully

### 4. **Monitor Costs**
- Azure SQL free tier: 32GB storage, 100k vCore seconds/month
- Serverless auto-pause saves costs
- Monitor usage in Azure Portal → Cost Management

### 5. **Optimize Performance**
- Use `@st.cache_data` for expensive queries
- Set TTL (time-to-live) to balance freshness and speed
- Pre-compute expensive columns in database

### 6. **Secure Your Database**
- Start with wide firewall (0.0.0.0-255.255.255.255) for testing
- Narrow to specific IPs after confirming connectivity
- Use strong passwords (12+ chars, mixed case, numbers, symbols)
- Enable Azure AD authentication for production

### 7. **Version Control**
- Commit code, not data
- Tag releases: `git tag v1.0.0`
- Document changes in commit messages

---

## Quick Checklist

Before deploying, verify:

- [ ] Azure SQL database created and online
- [ ] Firewall rule allows Streamlit Cloud (0.0.0.0-255.255.255.255)
- [ ] Connection string uses **ODBC Driver 17**
- [ ] Database schema created (tables exist)
- [ ] Database populated with data
- [ ] `azure_db.py` implements lazy-loading for secrets
- [ ] `requirements.txt` includes `pyodbc` and `sqlalchemy`
- [ ] `.gitignore` excludes `.env`, `*.db`, `secrets.toml`
- [ ] All Python modules committed to GitHub
- [ ] All image/asset files committed to GitHub
- [ ] Streamlit Cloud secret added (AZURE_SQL_CONN)
- [ ] App successfully deployed and loading data

---

## Example Project Structure

```
my-streamlit-app/
│
├── .gitignore                 # Exclude secrets and databases
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation
│
├── .env                       # Local secrets (NOT in git)
├── .streamlit/
│   ├── config.toml           # Streamlit configuration
│   ├── secrets.toml          # Local secrets (NOT in git)
│   └── secrets.toml.example  # Template (IN git)
│
├── azure_db.py               # Database connection module
├── app.py                    # Main Streamlit app
├── migrate_to_azure.py       # Data migration script (optional)
│
├── database/                 # Local SQLite (NOT in git)
│   └── main.db
│
└── utils/                    # Helper modules
    ├── __init__.py
    └── data_processing.py
```

---

## Additional Resources

- **Streamlit Docs**: https://docs.streamlit.io/
- **Azure SQL Docs**: https://learn.microsoft.com/azure/azure-sql/
- **pyodbc Docs**: https://github.com/mkleehammer/pyodbc/wiki
- **Streamlit Community**: https://discuss.streamlit.io/

---

## Changelog

- **2026-01-14**: Initial guide created based on Athletics Dashboard deployment
  - Resolved ODBC Driver 17 vs 18 compatibility
  - Implemented lazy-loading for Streamlit secrets
  - Fixed Azure SQL firewall configuration
  - Added comprehensive troubleshooting section

---

## Credits

Based on real-world deployment experience with the Athletics Dashboard project. All issues documented here were encountered and resolved during actual deployment.

---

**Need help?** Open an issue in your repository or post on the Streamlit Community forum.
