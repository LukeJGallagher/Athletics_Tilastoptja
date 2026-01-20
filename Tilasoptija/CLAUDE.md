# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Athletics performance analysis platform built with Python and Streamlit. Focuses on Saudi Arabian athletes and Islamic/Arab nations' athletic achievements using World Athletics competition data from Tilastopaja.

## Running the Application

```bash
streamlit run athletics_app_Deploy.py
```

The app uses dark theme configured in `.streamlit/config.toml`.

## Data Storage Policy

**GitHub contains CODE ONLY** - No data files are committed to GitHub. All data lives in Azure Blob Storage (Parquet format).

**Local Data Source:** `Tilastoptja_Data/ksaoutput_full.csv`
- Used for local development and initial database builds
- Contains ~13 million rows with all competition data
- Includes `wapoints` (WA Points) column for rankings
- Semicolon-delimited (`;`)
- **NOT committed to GitHub** (blocked by `.gitignore`)

## Building Databases

**Rebuild ALL databases from ksaoutput_full.csv:**
```bash
python rebuild_all_data.py
```

This builds:
- `SQL/athletics_deploy.db` - Main dashboard (major champs + KSA data)
- `SQL/athletics_competitor.db` - Recent data (for competitor analysis)
- `SQL/major_championships.db` - Major championships only
- `SQL/ksa_athletics.db` - KSA athletes only

**Build specific databases:**
```bash
python rebuild_all_data.py --deploy      # Main deploy database only
python rebuild_all_data.py --competitor  # Competitor analysis only
python rebuild_all_data.py --major       # Major championships only
python rebuild_all_data.py --ksa         # KSA athletes only
python rebuild_all_data.py --discover    # Discover new championship IDs
```

**Pre-computed columns (for performance):** The build script pre-computes `result_numeric`, `year`, and `round_normalized` to avoid recalculation at runtime.

## Architecture

### Main Application: `athletics_app_Deploy.py`

**Data Source Toggle (line ~553):**
```python
DATA_SOURCE = "deploy"  # Use optimized deployment databases (RECOMMENDED)
```

**Dashboard Tabs:**
1. Road to Asian Games - KSA athlete preparation for 2026 Nagoya
2. Road to LA 2028 - Olympic qualification tracking
3. Event Analysis - Performance requirements to medal
4. Athlete Profiles - Individual athlete deep dives with WA Points
5. Qualification vs Final - Round progression analysis
6. Competitor Analysis - Compare athletes across nations
7. Relay Analytics - Team event analysis
8. Text/Detailed Reports - Exportable summaries

**Key Functions:**
- `load_data()` / `load_sqlite_data()` - Unified data loaders
- `parse_result()` - Converts times/distances to numeric values
- `get_event_type()` - Returns 'time', 'distance', or 'points' for sorting direction
- `normalize_relay_events()` - Standardizes relay event names
- `MAJOR_COMPETITIONS_CID` - Dictionary of competition IDs (Olympics, WC, Asian Games, etc.)

### Database Build Script: `rebuild_all_data.py`

- `KNOWN_CHAMPIONSHIP_IDS` - Verified competition IDs for major championships
- `KEEP_COLUMNS` - Columns retained in built databases (includes `wapoints`)
- `EVENT_TYPE_MAP` - Maps event names to 'time', 'distance', or 'points'
- Processes CSV in 500k row chunks for memory efficiency

### Coach View Module: `coach_view.py`

Simplified coach-focused interface imported by main app via `render_coach_view()`:
- `show_competition_prep_hub()` - Championship selection, KSA squad overview, countdown
- `show_athlete_report_cards()` - Qualification status, form projections, benchmarks
- `show_competitor_watch()` - Rival monitoring, gaps, custom race builder
- `show_export_center()` - PDF/HTML report generation

Navigation uses `st.session_state['coach_view_tab']` for programmatic tab switching.

### Support Modules

| Module | Purpose |
|--------|---------|
| `projection_engine.py` | Weighted performance projections, confidence intervals, trend detection |
| `historical_benchmarks.py` | Medal/final/semi/heat benchmark calculations from championship history |
| `chart_components.py` | Reusable Altair charts (dark theme, export-ready) |
| `country_codes.py` | `COUNTRY_CODES` dict mapping 3-letter codes to full names |
| `discipline_knowledge.py` | Qualification standards (Tokyo 2025, LA 2028), event quotas |
| `athlete_dedup.py` | Handle duplicate athlete entries (ID normalization, Arabic name prefixes) |
| `report_generator.py` | PDF/HTML report generation with embedded charts |
| `azure_db.py` | Database connection (SQLite local, Azure SQL cloud with auto-wake retry) |
| `blob_storage.py` | Azure Blob Storage with Parquet files, DuckDB queries, fallback to SQLite |

## Qualification Standards

`discipline_knowledge.py` exports:
- `TOKYO_2025_STANDARDS` - World Championships entry standards
- `LA_2028_STANDARDS` - Olympic entry standards (estimated)
- `EVENT_QUOTAS` - Field sizes and ranking quotas per event (50% entry standard, 50% WA Rankings)

## Data Format

**CSV Column Mapping (Tilastopaja -> Dashboard):**
| CSV Column | Dashboard Column |
|------------|------------------|
| firstname + lastname | Athlete_Name |
| gender (M/F) | Gender (Men/Women) |
| nationality | Athlete_CountryCode |
| eventname | Event |
| performance | Result |
| competitionid | Competition_ID |
| competitiondate | Start_Date |
| wapoints | wapoints (WA Points) |
| round | Round (mapped to readable: h1->Heat 1, etc.) |

**Event Type Classification:**
- `time` events (lower is better): 100m, 400m, Marathon, Hurdles, Steeplechase, Relays, Race Walk
- `distance` events (higher is better): Long Jump, High Jump, Shot Put, Discus, Javelin, Hammer
- `points` events (higher is better): Decathlon, Heptathlon

## WA Points Integration

Displayed throughout dashboard:
- **Athlete Profiles:** Current, Average, and Best WA Points
- **Event Analysis:** WA Points by event for athletes
- **Results Tables:** WA Points column in all competition results

All databases include `wapoints` column with index for fast queries.

## Key Dependencies

pandas, sqlite3, streamlit, altair, numpy, requests, beautifulsoup4, python-dotenv

**Azure Blob Storage:** azure-storage-blob, azure-identity, pyarrow, duckdb

**Legacy Azure SQL:** pyodbc, sqlalchemy

Optional: weasyprint, jinja2, playwright (for PDF/testing)

## Database File Sizes

| Database | Size | Purpose |
|----------|------|---------|
| `athletics_deploy.db` | 43 MB | Main dashboard (major champs + KSA) |
| `athletics_competitor.db` | 936 MB | Recent 2024+ data for competitor analysis |
| `major_championships.db` | 26 MB | Major championships only |
| `ksa_athletics.db` | 2.5 MB | KSA athletes only |

## API Keys (.env)

The `.env` file contains API keys for external services:
- `OPENROUTER_API_KEY` - For AI-powered insights (free models)
- `BRAVE_API_KEY` - Web search capabilities
- `FIRECRAWL_API_KEY` - Web scraping
- `BRIGHTDATA_API_KEY` - Data collection

**Note:** Never commit `.env` to version control.

## Extended Competition Coverage

**Olympics (11 editions):** 1984-2024
- Paris 2024: CID 13079218
- Tokyo 2020: CID 12992925
- Rio 2016: CID 12877460

**World Championships (19 editions):** 1983-2025
- Tokyo 2025: CID 13112510
- Budapest 2023: CID 13046619
- Oregon 2022: CID 13002354

**Asian Games (3 editions):** 2014-2023
- Hangzhou 2023: CID 13048549
- Jakarta 2018: CID 12911586

**Asian Athletics Championships (11 editions):** 2003-2025
- Gumi 2025: CID 13105634
- Bangkok 2023: CID 13045167

**Also tracked:** World U20, World Indoor, Asian Indoor, Youth Olympics, Diamond League

## Coach Dashboard Design (v2.0)

See `docs/plans/2026-01-06-world-class-coaching-dashboard-design.md` for full specification.

**Dual-Mode Views:**
- **Coach View** - Simplified, action-focused for pre-competition briefings
- **Analyst View** - Current detailed analysis capabilities

**Coach View Tabs:**
1. Competition Prep Hub - Select championship, view KSA squad, countdown
2. Athlete Report Cards - Qualification status, form projections, benchmarks
3. Competitor Watch - Rival monitoring, gaps, form trends
4. Export Center - PDF/HTML report generation

**Key Features:**
- Statistical form projections with confidence intervals
- Historical championship benchmarks (medal/final/semi/heat lines)
- Enhanced competitor analysis (gaps, PB dates, form trends)
- Exportable reports with embedded charts
- Methodology notes visible for transparency

## Rollback Points

During implementation, use git tags for safe rollback:
```bash
git tag rollback-phase-X-start    # Before starting phase
git tag checkpoint-phase-X-complete  # After completing phase
git reset --hard <tag-name>       # Emergency rollback
```

## Testing

```bash
# Run Playwright e2e tests
pytest tests/e2e/ -v

# Run performance benchmarks
pytest tests/performance/ -v

# Generate HTML report
pytest tests/ --html=test_report.html
```

**Performance Targets:**
- Initial load: < 3 seconds
- Tab switch: < 500ms
- Report generation: < 5 seconds
- PDF export: < 10 seconds

## Azure Blob Storage Deployment (Recommended)

### Why Blob Storage over SQL?
- No ODBC driver issues on Streamlit Cloud
- No serverless wake-up delays (40613 errors)
- Parquet is ~10x smaller than CSV
- DuckDB provides fast SQL queries in-memory
- 5 GB free tier (enough for 50+ sport projects)

### Architecture
```
GitHub Code  →  GitHub Actions  →  Azure Blob Storage
  Your repo      Weekly sync        Parquet files
                                         ↓
                                    DuckDB queries
```

### Deployment Files
- `blob_storage.py` - Blob Storage module with DuckDB support
- `migrate_to_blob_storage.py` - Migration script from SQLite
- `.github/workflows/daily_sync.yml` - GitHub Actions (runs Sunday 02:00 UTC)

### Azure Blob Storage Details
- **Storage Account:** tilastoptija
- **Container:** athletics-data
- **Master File:** athletics_master.parquet
- **Region:** UAE North
- **Data Size:** ~2 MB (95,781 rows compressed)

### Environment Variables
- `AZURE_STORAGE_CONNECTION_STRING` - Blob Storage connection string
- Set in GitHub Secrets and Streamlit Cloud Secrets

### Quick Setup
```bash
# 1. Test connection
python blob_storage.py

# 2. Migrate SQLite to Blob Storage
python migrate_to_blob_storage.py --db deploy

# 3. Verify
python -c "from blob_storage import load_data; print(len(load_data()))"
```

### Usage in App
```python
from blob_storage import load_data, query

# Load all data
df = load_data()

# SQL queries with DuckDB
results = query("SELECT * FROM athletics_data WHERE nationality = 'KSA'")
```

See `AZURE_BLOB_STORAGE_GUIDE.md` for complete setup instructions.

---

## Azure SQL Deployment (Legacy)

**Note:** Azure SQL is kept for compatibility but Blob Storage is recommended.

### Architecture (The "Sandwich")
```
GitHub Code (Brain)  →  GitHub Actions (Motor)  →  Azure SQL (Memory)
     Your repo              Runs weekly              Cloud database
```

### Azure SQL Database Details
- **Server:** athletics-server-ksa.database.windows.net
- **Database:** athletics_data
- **Admin:** athletics_admin
- **Region:** UAE North
- **Tier:** Free (100k vCore seconds/month)

### Environment Variables for Azure SQL
- `AZURE_SQL_CONN` - Azure SQL ODBC connection string (set in GitHub Secrets as `SQL_CONNECTION_STRING`)
- Also stored in `.env` for local testing

### Azure Serverless Auto-Wake

The Azure SQL database uses serverless tier which auto-pauses after inactivity. `azure_db.py` includes retry logic:
- Detects error code 40613 ("database not currently available")
- Retries with exponential backoff (10s, 20s, 40s)
- Maximum 3 retry attempts before failing

### Complete Setup Process

#### Step 1: Create Azure SQL Database
1. Go to [portal.azure.com](https://portal.azure.com)
2. Search "SQL Database" > Create
3. Fill in:
   - Resource group: `athletics-rg` (create new)
   - Database name: `athletics_data`
   - Server: Create new > `athletics-server-ksa`
   - Admin: `athletics_admin` + password
   - Region: UAE North
4. Compute + storage > Select **Free tier**
5. Networking > **Public endpoint** > Allow Azure services: **Yes**
6. Review + Create

#### Step 2: Get Connection String
1. Azure Portal > Your SQL Database > **Connection strings**
2. Copy **ODBC** tab
3. Replace `{your_password}` with actual password
4. Add to `.env` file:
   ```
   AZURE_SQL_CONN=Driver={ODBC Driver 18 for SQL Server};Server=tcp:athletics-server-ksa.database.windows.net,1433;Database=athletics_data;Uid=athletics_admin;Pwd=YOUR_PASSWORD;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
   ```

#### Step 3: GitHub Repository
Repository: `https://github.com/LukeJGallagher/Athletics_Tilastoptja`

**IMPORTANT: No data files in GitHub** - Only code goes to GitHub. All data (CSV, DB, parquet, xlsx) is stored in Azure SQL only. See `.gitignore` for blocked file types.

#### Step 4: Add GitHub Secret
1. GitHub repo > **Settings** > **Secrets and variables** > **Actions**
2. Click **New repository secret**
3. Name: `SQL_CONNECTION_STRING`
4. Value: Same ODBC connection string from `.env`

#### Step 5: Test & Run
- **Local test:** `python azure_sync.py --test`
- **Manual trigger:** GitHub > Actions > Weekly Azure SQL Sync > Run workflow
- **Automatic:** Runs every Sunday 03:00 UTC

### Files Committed for Azure Deployment
```
.github/workflows/weekly_azure_sync.yml  # GitHub Actions workflow
azure_db.py                               # Database connection module
azure_sync.py                             # Sync script
requirements.txt                          # Dependencies (pyodbc, sqlalchemy)
.gitignore                                # Excludes .env, large files
```

See `DEPLOYMENT.md` for additional deployment options.

## Athlete Deduplication

The `athlete_dedup.py` module handles duplicate athlete entries:
- `normalize_athlete_id()` - Handles float/int ID variations (147939 vs 147939.0)
- `normalize_name()` - Standardizes Arabic prefixes (Al-, al, Al Jadani → al jadani)
- `MANUAL_ID_MAPPINGS` - Manual overrides for known duplicates
- Integrated into `load_data()` via `clean_athlete_data()`

## Performance Optimizations

Key cached functions (1-hour TTL):
- `get_final_performance_by_place()` - Historical championship results
- `get_ksa_athletes_for_event()` - KSA athlete filtering
- `get_batch_athlete_projections()` - Batch athlete form projections
- `get_qualification_by_round()` - Round-by-round qualification data

Use `@st.cache_data(ttl=3600)` decorator with `_df` prefix for DataFrame arguments.

## Common Issues and Fixes

### Streamlit Cloud Deployment
- **Image paths**: Use `Tilasoptija/Saudilogo.png` not `Saudilogo.png` (working directory is repo root)
- **ODBC Driver**: Streamlit Cloud has Driver 17, not 18 - connection string auto-detects

### Pandas Categorical Type Errors
When concatenating columns that might be Categorical (e.g., country flags):
```python
# Wrong - causes TypeError
df['col'] = df['Category_Col'] + ' ' + df['String_Col']

# Correct - convert to string first
df['col'] = df['Category_Col'].astype(str) + ' ' + df['String_Col'].astype(str)
```

### IndexError on Best Performance Lookup
When finding best performance, handle NaN values:
```python
# Wrong - fails if no valid results
best_val = event_df['Result_numeric'].min()
best_row = event_df[event_df['Result_numeric'] == best_val].iloc[0]

# Correct - filter NaN first, use idxmin
event_df_valid = event_df[event_df['Result_numeric'].notna()]
if not event_df_valid.empty:
    best_idx = event_df_valid['Result_numeric'].idxmin()
    best_row = event_df_valid.loc[best_idx]
```
