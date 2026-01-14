# Azure SQL Database Setup Guide

## Current Issue

Azure SQL database connection is failing with error:
```
Database 'athletics_data' on server 'athletics-server-ksa.database.windows.net' is not currently available
```

This means either:
- Database was never created
- Database is paused (free tier auto-pauses after 7 days)
- Database was deleted

## Solution: Setup Azure SQL from Scratch

### Step 1: Create Azure SQL Database

1. Go to [Azure Portal](https://portal.azure.com)
2. Search for "SQL databases" in top search bar
3. Click **+ Create**

**Fill in details:**
- **Resource group:** `athletics-rg` (create new if doesn't exist)
- **Database name:** `athletics_data`
- **Server:** Select existing `athletics-server-ksa` OR create new:
  - Server name: `athletics-server-ksa`
  - Location: `UAE North` (or your preferred region)
  - Authentication: SQL authentication
  - Server admin: `athletics_admin`
  - Password: `Asiangames@2026!`
- **Compute + Storage:** Click "Configure database"
  - Select **Serverless**
  - Select **Free** tier (5 GB, 100k vCore seconds/month)
- **Backup storage redundancy:** Locally-redundant
- Click **Review + Create** > **Create**

### Step 2: Configure Firewall Rules

Once database is created:

1. Go to your database > **Networking** (left menu)
2. Under "Firewall rules":
   - ✅ Check **"Allow Azure services and resources to access this server"**
   - Click **+ Add your client IPv4 address** (so you can connect locally)
3. Click **Save**

### Step 3: Create Table Schema

1. In Azure Portal, go to your database
2. Click **Query editor (preview)** in left menu
3. Login with:
   - Username: `athletics_admin`
   - Password: `Asiangames@2026!`
4. Copy and paste the entire content from `database/azure_schema.sql`
5. Click **Run**

You should see: "Table created successfully" and "RowCount: 0"

### Step 4: Populate Database with Data

**Option A: From Local SQLite (Recommended)**

Run this command from your project directory:

```bash
# Test connection first
python azure_sync.py --test

# If connection succeeds, populate with data
python -c "from azure_db import migrate_sqlite_to_azure; migrate_sqlite_to_azure('deploy')"
```

This will upload all data from `SQL/athletics_deploy.db` (43 MB) to Azure SQL in batches.

**Option B: From Tilastopaja API (Slower)**

```bash
python azure_sync.py --full
```

This fetches data directly from Tilastopaja API and inserts to Azure. Takes longer but ensures fresh data.

### Step 5: Verify Data Loaded

```bash
python azure_sync.py --test
```

Should show row count (e.g., "Row Count: 500,000+")

### Step 6: Configure Streamlit Cloud

1. Go to [Streamlit Cloud](https://share.streamlit.io/)
2. Find your app: `athleticstilastoptja-crb7vwf234j8p5rppkn7mq`
3. Click **Settings** > **Secrets**
4. Add:

```toml
AZURE_SQL_CONN = "Driver={ODBC Driver 18 for SQL Server};Server=tcp:athletics-server-ksa.database.windows.net,1433;Database=athletics_data;Uid=athletics_admin;Pwd=Asiangames@2026!;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
```

5. Click **Save**
6. Streamlit will auto-redeploy (2-3 minutes)

### Step 7: Monitor Weekly Sync

The GitHub Actions workflow will run every Sunday at 03:00 UTC to sync new data:
- Location: `.github/workflows/weekly_azure_sync.yml`
- View runs: [GitHub Actions](https://github.com/LukeJGallagher/Athletics_Tilastoptja/actions)

## Troubleshooting

### "Database not available" error
- Check if database is paused in Azure Portal
- Click **Resume** if paused
- Serverless tier auto-pauses after 1 hour of inactivity

### "Cannot connect" error
- Verify firewall rules allow your IP
- Verify password is correct in connection string
- Check database server is in correct region

### "No data" in app
- Verify Azure SQL has data: `python azure_sync.py --test`
- Check Streamlit Cloud secrets are configured correctly
- View Streamlit Cloud logs for detailed errors

## Connection String Format

```
Driver={ODBC Driver 18 for SQL Server};
Server=tcp:athletics-server-ksa.database.windows.net,1433;
Database=athletics_data;
Uid=athletics_admin;
Pwd=YOUR_PASSWORD;
Encrypt=yes;
TrustServerCertificate=no;
Connection Timeout=30;
```

## Cost Management

**Azure SQL Serverless Free Tier:**
- ✅ 5 GB storage
- ✅ 100k vCore seconds/month
- ✅ Auto-pause after 1 hour idle
- ✅ Auto-resume on first query

**Monthly cost:** $0 (within free tier limits)

## Data Size Estimates

| Database | Rows | Size |
|----------|------|------|
| Deploy | ~500k | 43 MB |
| Competitor | ~1.8M | 936 MB |
| Major Champs | ~200k | 26 MB |
| KSA Only | ~5k | 2.5 MB |

Deploy database recommended for Streamlit Cloud (best balance of size and coverage).
