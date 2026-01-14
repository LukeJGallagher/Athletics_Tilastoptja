# Complete Azure SQL Database Rebuild Workflow

**Issue:** Azure SQL database contains para-athletics data and is missing historical 100m results.

**Root Cause:** Database was populated from incremental API endpoints instead of the full historical CSV file.

**Solution:** Download full historical data, rebuild local SQLite, then migrate to Azure SQL.

---

## Prerequisites

1. **Azure SQL database online** - Check in Azure Portal
2. **Firewall configured** - Must allow your IP and Streamlit Cloud (0.0.0.0-255.255.255.255)
3. **Local disk space** - Need ~500MB for CSV + SQLite files

---

## Complete Workflow (3 Steps)

### Step 1: Download Full Historical Data

Download the complete Tilastopaja dataset (~13 million rows):

```bash
python download_full_tilastopaja_data.py
```

**What this does:**
- Downloads from: `https://www.tilastopaja.com/json/ksa/ksaoutput_full.csv`
- Saves to: `Tilastoptja_Data/ksaoutput_full.csv`
- Verifies: Row count, format, columns
- Expected result: ~13 million rows, semicolon-delimited CSV

**Time:** 5-10 minutes depending on internet speed

---

### Step 2: Rebuild Local SQLite Database

Build a clean SQLite database from the CSV file:

```bash
python rebuild_all_data.py --deploy
```

**What this does:**
- Reads: `Tilastoptja_Data/ksaoutput_full.csv`
- Filters: Major championships + KSA athletes
- Pre-computes: `result_numeric`, `year`, `round_normalized`
- Creates: `SQL/athletics_deploy.db` (~43 MB)
- **Excludes:** Para-athletics events (if filter added)

**Time:** 10-15 minutes for full dataset

**Expected result:**
- File: `SQL/athletics_deploy.db`
- Rows: ~500k-1M (major champs + KSA)
- Events: Regular athletics only (100m, 200m, etc.)

---

### Step 3: Migrate to Azure SQL

Upload the clean SQLite data to Azure SQL:

```bash
python rebuild_azure_from_sqlite.py
```

**What this does:**
- Connects to: Azure SQL database
- Deletes: ALL existing Azure SQL data
- Migrates: All rows from `SQL/athletics_deploy.db`
- Verifies: Row count matches
- Batch size: 5,000 rows per batch

**Time:** 15-20 minutes for ~500k rows

**Expected result:**
- Azure SQL has same row count as local SQLite
- No para-athletics events
- Historical 100m data present

---

## Verification

After completing all 3 steps, verify the deployment:

### 1. Check Streamlit Cloud App

Visit your app and check:
- ✓ 100m data shows in Event Analysis tab
- ✓ Historical results from multiple years
- ✓ No para-athletics events (T11, T12, F20, etc.)

### 2. Check Row Count

Run diagnostic:
```bash
python test_azure_connection.py
```

Should show:
- Connection mode: azure
- Row count: ~500k-1M rows

---

## API Sync Configuration

After the initial full rebuild, daily updates can use the API endpoints:

**API Endpoints** (updated daily at 00:15 GMT+2):
- New results: `https://www.tilastopaja.com/json/ksa/list`
- Changed results: `https://www.tilastopaja.com/json/ksa/changes`
- Deleted results: `https://www.tilastopaja.com/json/ksa/deleted`
- New athletes: `https://www.tilastopaja.com/json/ksa/athletesnew`
- Changed athletes: `https://www.tilastopaja.com/json/ksa/athleteschanges`
- Deleted athletes: `https://www.tilastopaja.com/json/ksa/athletesdeleted`

**Current sync script:** `azure_sync.py` (runs weekly via GitHub Actions)

---

## Adding Para-Athletics Filter (Optional)

If you want to permanently exclude para-athletics from the build process:

Edit `rebuild_all_data.py` and add this function:

```python
def is_para_athletics(event_name):
    """Filter out para-athletics events."""
    import re
    # Pattern: T or F followed by 2 digits (classification codes)
    para_pattern = r'\b[TF]\d{2}\b'
    return bool(re.search(para_pattern, str(event_name)))

# Then in the processing loop, add:
df = df[~df['eventname'].apply(is_para_athletics)]
```

This ensures para-athletics is filtered during the SQLite build step.

---

## Troubleshooting

### Issue: Download fails or times out

**Solution:**
- Check internet connection
- Try again (downloads resume from where they stopped)
- Download manually from browser and place in `Tilastoptja_Data/`

### Issue: SQLite build fails

**Solution:**
- Check CSV file exists: `Tilastoptja_Data/ksaoutput_full.csv`
- Verify CSV format (semicolon-delimited)
- Check disk space (need ~500MB)

### Issue: Azure SQL migration fails

**Solution:**
- Check database is online in Azure Portal
- Verify firewall allows your IP
- Test connection: `python test_azure_connection.py`
- Check password in `.env` file

### Issue: Para-athletics still showing

**Solution:**
- Add para-athletics filter to `rebuild_all_data.py` (see above)
- Re-run Step 2 and Step 3
- Or manually delete from Azure: `DELETE FROM athletics_data WHERE eventname LIKE '%T[0-9][0-9]%'`

---

## Summary

**Full rebuild takes ~30-45 minutes total:**
1. Download CSV: 5-10 min
2. Build SQLite: 10-15 min
3. Migrate to Azure: 15-20 min

**After completion:**
- ✓ Clean database with regular athletics only
- ✓ Historical data from all major championships
- ✓ Ready for daily API sync updates

---

## File Locations

```
your-project/
├── Tilastoptja_Data/
│   └── ksaoutput_full.csv          # Full historical data (~13M rows)
├── SQL/
│   └── athletics_deploy.db          # Clean SQLite (~500k rows)
├── Azure SQL Database
│   └── athletics_data table         # Cloud copy (same as SQLite)
└── Scripts:
    ├── download_full_tilastopaja_data.py
    ├── rebuild_all_data.py
    └── rebuild_azure_from_sqlite.py
```

---

**Last Updated:** 2026-01-14
**Status:** Ready to execute
