# AI Analytics Tab - Design Document

**Date:** 2026-02-10
**Status:** Approved
**Author:** Performance Analysis Team
**Module:** `ai_analytics.py`

---

## 1. Executive Summary

Add a conversational AI Analytics tab to the Athletics Dashboard that allows coaches and analysts to ask natural language questions about athlete performance data. The system translates questions into DuckDB SQL queries against the existing Parquet data, executes them, and returns results with AI-generated explanations and Plotly visualizations.

**Approach:** Hybrid -- Natural Language to SQL generation with conversational AI follow-up.

**Key decisions:**
- Single new module (`ai_analytics.py`) imported by the main app
- OpenRouter API with free-tier LLMs (no cost to operate)
- DuckDB queries on existing Parquet files (no new infrastructure)
- AI-chosen Plotly charts with automatic table fallback
- Domain context loaded from `docs/ai_athletics_context.md` (~48 KB)

---

## 2. Architecture Overview

### 2.1 System Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ATHLETICS DASHBOARD                              │
│  Sidebar: [Coach View | Analyst View]                                │
│                                                                      │
│  Analyst View Tabs:                                                  │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────────┐       │
│  │ Road to  │ Event    │ Athlete  │ Relay    │ AI Analytics  │ ...   │
│  │ Asian Gm │ Analysis │ Profiles │ Analyti. │ (NEW)         │       │
│  └──────────┴──────────┴──────────┴──────────┴───────────────┘       │
│                                                                      │
│  AI Analytics Tab:                                                   │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  [Chat Interface - st.chat_message]                          │    │
│  │  ┌─────────────────────────────────────────────────────────┐ │    │
│  │  │ User: "Who are the top 5 KSA sprinters in 2024?"       │ │    │
│  │  ├─────────────────────────────────────────────────────────┤ │    │
│  │  │ AI: Explanation text                                    │ │    │
│  │  │     [Plotly Bar Chart]                                  │ │    │
│  │  │     [Expandable Data Table]                             │ │    │
│  │  │     Suggested: [Follow-up 1] [Follow-up 2]             │ │    │
│  │  └─────────────────────────────────────────────────────────┘ │    │
│  │  [st.chat_input: "Ask about athletics data..."]              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Sidebar (when AI tab active):                                       │
│  ┌──────────────┐                                                    │
│  │ Model: [...]  │  ← Model selector dropdown                       │
│  │ Data: [...]   │  ← Master (96K) / Full (13M) toggle              │
│  │ [Clear Chat]  │  ← Reset conversation                            │
│  └──────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
User types question in st.chat_input
  │
  ▼
Append to st.session_state['ai_chat_history']
  │
  ▼
Build messages array:
  ├── System prompt (schema + domain knowledge from ai_athletics_context.md)
  ├── Response format instructions (JSON schema)
  └── Chat history (last 10 message pairs)
  │
  ▼
Call OpenRouter API
  ├── Model: meta-llama/llama-4-maverick-17b-128e-instruct:free (default)
  ├── Headers: Authorization, HTTP-Referer, X-Title
  └── max_tokens: 2000
  │
  ▼
Parse JSON response
  ├── explanation: string
  ├── sql: string (DuckDB SQL)
  ├── chart_type: bar|line|scatter|box|table|none
  ├── chart_code: string (Plotly Python code)
  └── follow_ups: string[]
  │
  ▼
Validate & Execute SQL
  ├── Reject non-SELECT statements
  ├── Run via DuckDB on athletics_master.parquet or athletics_full.parquet
  └── Return DataFrame (or error message)
  │
  ▼
Render Response
  ├── Explanation text (st.markdown)
  ├── Plotly chart (exec chart_code → fallback to auto-chart → fallback to table)
  ├── Data table (st.dataframe in expander)
  └── Follow-up suggestions (st.button for each)
  │
  ▼
Store assistant response in st.session_state['ai_chat_history']
```

---

## 3. Module Design: `ai_analytics.py`

### 3.1 Public API

```python
def render_ai_analytics(df: pd.DataFrame) -> None:
    """Main entry point. Called from athletics_app_Deploy.py when AI Analytics tab is selected."""
```

This is the only function the main app needs to call. All other functions are internal to the module.

### 3.2 Internal Functions

| Function | Purpose | Inputs | Outputs |
|----------|---------|--------|---------|
| `build_system_prompt()` | Loads `docs/ai_athletics_context.md`, assembles system prompt with schema, domain knowledge, event classification, and JSON response format | None | `str` (system prompt) |
| `call_openrouter(messages, model)` | Makes API call to OpenRouter chat completions endpoint | `List[Dict]`, `str` | `Dict` (parsed JSON response) or error dict |
| `validate_sql(sql)` | Checks SQL is SELECT-only, no dangerous statements | `str` | `bool` |
| `execute_query(sql, data_source)` | Runs DuckDB SQL against Parquet file, returns DataFrame | `str`, `str` | `pd.DataFrame` or `None` |
| `render_chart(chart_spec, df)` | Executes Plotly code string from AI, with fallback chain | `Dict`, `pd.DataFrame` | `plotly.graph_objects.Figure` or `None` |
| `auto_chart(chart_type, df)` | Generates a default Plotly chart based on chart_type and DataFrame shape | `str`, `pd.DataFrame` | `plotly.graph_objects.Figure` |
| `render_response(response, query_result)` | Displays explanation, chart, table, and follow-up suggestions | `Dict`, `pd.DataFrame` | `None` |

### 3.3 Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `ai_chat_history` | `List[Dict]` | Full conversation history (role + content pairs) |
| `ai_model` | `str` | Currently selected model ID |
| `ai_data_source` | `str` | `"master"` or `"full"` |
| `ai_query_cache` | `Dict[str, pd.DataFrame]` | Cached SQL query results (keyed by SQL string) |

---

## 4. System Prompt Design

### 4.1 Structure

The system prompt is assembled from three parts:

1. **Role and instructions** -- Defines the AI as an athletics data analyst, instructs it to return JSON
2. **Schema and domain knowledge** -- Full contents of `docs/ai_athletics_context.md` (1,365 lines, ~48 KB), which includes:
   - Complete database schema (40 columns with types and examples)
   - Event classification (time/distance/points with elite ranges)
   - Major championship competition IDs (Olympics, World Championships, Asian Games, etc.)
   - Country codes and nationality mappings
   - Round normalization rules
   - Query guidelines and common patterns
3. **Response format specification** -- JSON schema the AI must follow

### 4.2 Response JSON Format

The AI must return valid JSON in this structure:

```json
{
  "explanation": "Plain English explanation of the results. 2-4 sentences summarizing what the data shows.",
  "sql": "SELECT firstname, lastname, nationality, performance, wapoints FROM athletics_data WHERE nationality = 'KSA' AND eventname = '100m' AND gender = 'M' ORDER BY result_numeric ASC LIMIT 10",
  "chart_type": "bar",
  "chart_code": "import plotly.express as px\nfig = px.bar(df, x='lastname', y='wapoints', color='nationality', title='Top KSA Sprinters by WA Points')\nfig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font=dict(family='Inter, sans-serif', color='#333'))",
  "follow_ups": [
    "How do these athletes compare to the Asian Games medal standard?",
    "Show their performance trend over the last 3 years"
  ]
}
```

**Field rules:**
- `explanation` -- Always present. Plain English, no jargon. Reference specific numbers when available.
- `sql` -- Always present. Must be a SELECT statement. Table name is always `athletics_data`. Use column names from the schema exactly.
- `chart_type` -- One of: `bar`, `line`, `scatter`, `box`, `table`, `none`. The AI chooses the most appropriate visualization.
- `chart_code` -- Plotly Python code as a string. Uses `df` as the variable name for the query result DataFrame. Must produce a `fig` variable. May be `null` if `chart_type` is `table` or `none`.
- `follow_ups` -- Array of 2-3 suggested follow-up questions. Always present.

### 4.3 Key Prompt Instructions

The system prompt includes these critical instructions for the LLM:

- **Table name:** Always `athletics_data` (this is the DuckDB view name over the Parquet file)
- **Time events:** Lower `result_numeric` is better (100m, 400m, Marathon, Hurdles, Steeplechase, Relays, Race Walk)
- **Distance events:** Higher `result_numeric` is better (Long Jump, High Jump, Shot Put, Discus, Javelin, Hammer)
- **Points events:** Higher `result_numeric` is better (Decathlon, Heptathlon)
- **KSA focus:** When nationality is not specified, default to KSA (Saudi Arabia) for athlete queries
- **Gender column:** Uses `M` or `F` (not Men/Women)
- **Date format:** `competitiondate` is `YYYY-MM-DD` string; `year` is pre-computed INTEGER
- **Round values:** Use `round_normalized` for display (Final, Semi Finals, Heats) or raw `round` column (f, sf, h1, h2)
- **Result sorting:** Always use `result_numeric` for numeric comparisons, not `performance` (which is a string)
- **Chart styling:** Use Team Saudi branding -- primary teal `#007167`, gold accent `#a08e66`, white background, Inter font

---

## 5. OpenRouter Integration

### 5.1 API Configuration

```python
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # Already in .env

# Request headers
headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://athletics-dashboard.streamlit.app",
    "X-Title": "Athletics Dashboard - AI Analytics"
}
```

### 5.2 Available Models (Free Tier)

| Model | ID | Strengths | Context Window |
|-------|----|-----------|---------------|
| Llama 4 Maverick (recommended) | `meta-llama/llama-4-maverick-17b-128e-instruct:free` | Fast, good at SQL generation, strong JSON output | 128K |
| Gemma 3 27B | `google/gemma-3-27b-it:free` | Strong reasoning, good explanations | 96K |
| Mistral Small 3.1 | `mistralai/mistral-small-3.1-24b-instruct:free` | Reliable JSON format, concise | 96K |

The default model is **Llama 4 Maverick** due to its large context window (accommodates the ~48 KB context document plus conversation history) and strong SQL generation capability.

### 5.3 Relationship to Existing `openrouter_client.py`

The project already has `openrouter_client.py` which provides `OpenRouterClient` for generating narrative insights (form analysis, competitor assessment, championship readiness). The AI Analytics module will **not** reuse this client directly because:

- The existing client is designed for single-shot insight generation with fixed prompts
- AI Analytics needs conversational multi-turn chat with JSON-structured responses
- AI Analytics requires a different system prompt, higher max_tokens, and lower temperature
- The API calling pattern is different (chat history vs. single message)

However, `ai_analytics.py` will share the same `OPENROUTER_API_KEY` environment variable and the same OpenRouter API endpoint. If the `openrouter_client.py` module is later refactored to support generic chat, the AI Analytics module could adopt it.

### 5.4 API Call Parameters

```python
payload = {
    "model": selected_model,
    "messages": messages,          # system + chat history
    "max_tokens": 2000,            # Enough for SQL + explanation + chart code
    "temperature": 0.3,            # Low temperature for deterministic SQL
    "response_format": {"type": "json_object"}  # Request JSON output
}
```

---

## 6. Query Execution

### 6.1 DuckDB on Parquet

Queries run via DuckDB directly on Parquet files stored in Azure Blob Storage (or local fallback). This reuses the existing `blob_storage.py` infrastructure.

```python
import duckdb

def execute_query(sql: str, data_source: str = "master") -> pd.DataFrame:
    """Execute SQL query against Parquet data via DuckDB."""

    # Select data file
    parquet_file = "athletics_master.parquet" if data_source == "master" else "athletics_full.parquet"

    # Load Parquet into DuckDB
    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW athletics_data AS SELECT * FROM '{parquet_file}'")

    result = conn.execute(sql).fetchdf()
    conn.close()

    return result
```

### 6.2 Data Source Toggle

| Source | File | Rows | Use Case |
|--------|------|------|----------|
| Master (default) | `athletics_master.parquet` | ~96,000 | Major championships + KSA athletes. Fast queries, focused data. |
| Full | `athletics_full.parquet` | ~13,000,000 | All competition data worldwide. Slower but comprehensive. |

Users toggle between sources in the sidebar. The system prompt is updated to reflect which dataset is active so the AI can set appropriate expectations about result coverage.

### 6.3 SQL Validation

Before execution, all SQL is validated:

```python
def validate_sql(sql: str) -> bool:
    """Ensure SQL is read-only SELECT statement."""

    sql_upper = sql.strip().upper()

    # Must start with SELECT or WITH (for CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Reject dangerous keywords
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
                  "EXEC", "EXECUTE", "GRANT", "REVOKE", "MERGE"]
    for keyword in dangerous:
        # Check for keyword as a whole word (not part of column name)
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False

    return True
```

---

## 7. Visualization

### 7.1 Chart Rendering Pipeline

The chart rendering follows a three-level fallback chain:

```
Level 1: Execute AI-generated chart_code
  │
  ├── Success → Display Plotly figure
  │
  └── Failure (syntax error, missing columns, etc.)
      │
      ▼
Level 2: Auto-chart based on chart_type + DataFrame shape
  │
  ├── Success → Display auto-generated Plotly figure
  │
  └── Failure (incompatible data shape)
      │
      ▼
Level 3: Display as st.dataframe (table fallback)
```

### 7.2 Auto-Chart Logic

When AI-generated chart code fails, `auto_chart()` produces a reasonable default:

| chart_type | Auto-chart behavior |
|-----------|---------------------|
| `bar` | First string column as x-axis, first numeric column as y-axis |
| `line` | Date/year column as x-axis, first numeric column as y-axis |
| `scatter` | First numeric column as x-axis, second numeric column as y-axis |
| `box` | First string column as x-axis (category), first numeric column as y-axis |
| `table` | Skip chart, show table directly |
| `none` | Skip chart (explanation-only response) |

### 7.3 Team Saudi Branding

All charts (both AI-generated and auto-generated) receive Team Saudi styling:

```python
# Applied to all figures before display
fig.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family='Inter, sans-serif', color='#333'),
    margin=dict(l=10, r=10, t=40, b=30)
)
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
```

The system prompt instructs the AI to use teal (`#007167`) as the primary color and gold (`#a08e66`) as the accent color in its chart code.

---

## 8. UI Layout

### 8.1 Tab Header

```python
st.markdown("""
<div style="background: linear-gradient(135deg, #007167 0%, #005a51 100%);
     padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #a08e66;">
    <h2 style="color: white; margin: 0;">AI Analytics</h2>
    <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">
        Ask questions about athletics data in natural language
    </p>
</div>
""", unsafe_allow_html=True)
```

### 8.2 Chat Interface

The tab uses Streamlit's native chat components:

```python
# Display chat history
for message in st.session_state.get('ai_chat_history', []):
    with st.chat_message(message['role']):
        if message['role'] == 'user':
            st.markdown(message['content'])
        else:
            render_response(message['response'], message.get('query_result'))

# Input at bottom
if prompt := st.chat_input("Ask about athletics data..."):
    # Process question...
```

### 8.3 Response Layout

Each AI response renders in this order:

1. **Explanation text** -- `st.markdown(response['explanation'])`
2. **Plotly chart** -- `st.plotly_chart(fig, use_container_width=True)` (if chart generated)
3. **Data table** -- Inside `st.expander("View data")` showing the query result DataFrame
4. **SQL query** -- Inside `st.expander("View SQL")` showing the executed query (for transparency)
5. **Follow-up suggestions** -- Row of `st.button` elements, clicking one submits it as the next question

### 8.4 Sidebar Controls (When AI Tab Active)

```python
with st.sidebar:
    st.markdown("### AI Settings")

    # Model selector
    model = st.selectbox("Model", [
        "meta-llama/llama-4-maverick-17b-128e-instruct:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free"
    ], key="ai_model")

    # Data source toggle
    data_source = st.radio("Data Source", [
        "Master (~96K rows - Major championships + KSA)",
        "Full (~13M rows - All competitions)"
    ], key="ai_data_source")

    # Clear chat
    if st.button("Clear Chat", key="ai_clear_chat"):
        st.session_state['ai_chat_history'] = []
        st.rerun()
```

---

## 9. Error Handling

### 9.1 Error Categories and Responses

| Error | Detection | User-Facing Response | Recovery |
|-------|-----------|---------------------|----------|
| Bad SQL syntax | DuckDB raises exception | "Query failed: {error}. Try rephrasing your question." | Show the attempted SQL in an expander for debugging |
| Non-SELECT SQL | `validate_sql()` returns False | "For security, only data retrieval queries are allowed. Please ask a question about the data." | Log the attempted query |
| Empty results | DataFrame has 0 rows | "No data found matching your query. The SQL tried was: ..." | Suggest broadening the search (remove filters, expand date range) |
| Bad chart code | `exec()` raises exception | Fall back to auto-chart, then to table. No error shown to user. | Log the chart code error for debugging |
| API timeout | `requests.Timeout` after 30s | "The AI service is taking too long. Please try again." | Show retry button |
| API error (429, 500, etc.) | Non-200 status code | "AI service temporarily unavailable. Error: {status_code}" | Show retry button, suggest trying a different model |
| No API key | `OPENROUTER_API_KEY` is None | "AI Analytics requires an OpenRouter API key. Add OPENROUTER_API_KEY to your .env file." | Show setup instructions |
| Invalid JSON response | `json.loads()` fails | Attempt to extract SQL from raw text; if that fails, show "Could not parse AI response. Please try again." | Retry with rephrased prompt |
| Context document missing | `ai_athletics_context.md` not found | Fall back to minimal schema-only prompt | Log warning, continue with reduced context |

### 9.2 Retry Mechanism

```python
if api_error:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Retry", key=f"retry_{len(chat_history)}"):
            # Re-send last message
            ...
    with col2:
        if st.button("Try different model", key=f"switch_{len(chat_history)}"):
            # Cycle to next model
            ...
```

---

## 10. Performance Considerations

### 10.1 Token Management

| Component | Approximate Size | Strategy |
|-----------|-----------------|----------|
| System prompt (fixed) | ~48 KB (~12,000 tokens) | Sent once per conversation, loaded from file |
| Chat history | Variable | Trimmed to last 10 message pairs (user + assistant) |
| AI response | ~500-1500 tokens | `max_tokens: 2000` cap |
| Total per request | ~15,000-20,000 tokens | Well within 128K context window |

### 10.2 Caching

- **Context document:** Loaded once via `@st.cache_data` and reused across all requests
- **Query results:** Stored in `st.session_state['ai_query_cache']` keyed by SQL string. If the same SQL is generated twice, the cached DataFrame is returned without re-executing.
- **Parquet data:** DuckDB reads Parquet efficiently with columnar scanning; only referenced columns are loaded from disk.

### 10.3 Data Source Defaults

- **Default: Master** (~96K rows) -- Fast queries (sub-second), contains major championships and all KSA results
- **Optional: Full** (~13M rows) -- Slower queries (1-5 seconds), used when analyzing non-KSA athletes at non-major competitions
- The sidebar clearly labels the active data source so users understand result scope

### 10.4 Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| Build system prompt | < 50ms | Cached after first load |
| OpenRouter API call | 2-8 seconds | Depends on model, free tier may queue |
| SQL execution (master) | < 500ms | DuckDB on 96K rows |
| SQL execution (full) | 1-5 seconds | DuckDB on 13M rows |
| Chart rendering | < 200ms | Plotly in-browser |
| **Total** | **3-14 seconds** | Acceptable for conversational AI |

---

## 11. Security

### 11.1 SQL Injection Prevention

- All SQL is validated by `validate_sql()` before execution
- Only `SELECT` and `WITH` (CTE) statements are permitted
- Dangerous keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `EXECUTE`, `GRANT`, `REVOKE`, `MERGE`) are rejected
- DuckDB runs in-memory against a read-only Parquet file; there is no writable database to corrupt

### 11.2 API Key Protection

- `OPENROUTER_API_KEY` loaded from `.env` (local) or Streamlit Secrets (cloud)
- Never exposed in frontend HTML, chat messages, or error messages
- `.env` is in `.gitignore` and never committed to GitHub

### 11.3 Chart Code Execution

AI-generated chart code is executed via `exec()` in a restricted namespace:

```python
# Restricted execution environment
allowed_globals = {
    'pd': pd,
    'px': plotly.express,
    'go': plotly.graph_objects,
    'df': query_result,
    'np': numpy,
    '__builtins__': {}  # No builtins - prevents os, sys, etc.
}

try:
    exec(chart_code, allowed_globals)
    fig = allowed_globals.get('fig')
except Exception:
    fig = None  # Fall back to auto-chart
```

This prevents the AI-generated code from accessing the filesystem, network, or any modules beyond pandas, plotly, and numpy.

---

## 12. Integration with Main App

### 12.1 Import

In `athletics_app_Deploy.py`, add the import alongside existing module imports:

```python
from ai_analytics import render_ai_analytics
```

### 12.2 Tab Registration

Add to the `tab_names` list in the Analyst View section (~line 6735):

```python
tab_names = [
    "...",          # existing tabs
    "🤖 AI Analytics"  # new tab
]
```

### 12.3 Tab Rendering

Add the conditional rendering block (~line 6754):

```python
elif selected_tab == "🤖 AI Analytics":
    render_ai_analytics(df_all)
```

### 12.4 Dependencies

Add to `requirements.txt`:

```
plotly>=5.18.0
```

Note: `requests`, `duckdb`, `python-dotenv`, and `pandas` are already in the requirements. No new external dependencies are needed beyond `plotly` (which may already be installed but is not currently listed).

---

## 13. Example Conversations

### 13.1 Simple Query

**User:** "Who are the fastest KSA 100m runners in 2024?"

**AI Response:**
```json
{
  "explanation": "Here are the fastest Saudi Arabian male 100m sprinters from 2024, ranked by their best time. The top performer achieved 10.15s with 1042 WA Points.",
  "sql": "SELECT firstname, lastname, MIN(result_numeric) as best_time, MAX(wapoints) as best_points, COUNT(*) as races FROM athletics_data WHERE nationality = 'KSA' AND eventname = '100m' AND gender = 'M' AND year = 2024 AND result_numeric IS NOT NULL GROUP BY firstname, lastname ORDER BY best_time ASC LIMIT 10",
  "chart_type": "bar",
  "chart_code": "import plotly.express as px\nfig = px.bar(df, x='lastname', y='best_time', color_discrete_sequence=['#007167'], title='Fastest KSA 100m Runners (2024)')\nfig.update_layout(plot_bgcolor='white', yaxis_title='Time (seconds)', xaxis_title='Athlete')",
  "follow_ups": [
    "How do they compare to the Asian Games qualifying standard?",
    "Show their season progression over 2024",
    "Who are the top female KSA sprinters?"
  ]
}
```

### 13.2 Championship Analysis

**User:** "What time was needed to make the 400m final at the last 3 Olympics?"

**AI Response:**
```json
{
  "explanation": "Looking at the men's 400m finals at the last three Olympic Games (Paris 2024, Tokyo 2020, Rio 2016), the slowest qualifier into the final ran approximately 44.5-45.0 seconds. The winning time ranged from 43.03s (Paris 2024) to 43.85s (Rio 2016).",
  "sql": "SELECT competitionname, firstname || ' ' || lastname as athlete, nationality, performance, result_numeric, position FROM athletics_data WHERE eventname = '400m' AND gender = 'M' AND round_normalized = 'Final' AND competitionid IN ('13079218', '12992925', '12877460') ORDER BY competitionid DESC, result_numeric ASC",
  "chart_type": "bar",
  "chart_code": "import plotly.express as px\nfig = px.bar(df, x='athlete', y='result_numeric', color='competitionname', barmode='group', title='400m Olympic Finals - Last 3 Games', color_discrete_sequence=['#007167', '#a08e66', '#005a51'])\nfig.update_layout(plot_bgcolor='white', yaxis_title='Time (seconds)')",
  "follow_ups": [
    "What about the women's 400m?",
    "What WA Points were needed to qualify for these finals?",
    "How do current KSA 400m athletes compare to these standards?"
  ]
}
```

### 13.3 Trend Analysis

**User:** "Show me the progression of the men's Shot Put world record holders' performances at World Championships"

**AI Response:**
```json
{
  "explanation": "Here are the winning performances in the men's Shot Put at World Championships from 1983 to 2025. The event has seen a general upward trend, with the winning distance increasing from around 21m in the early championships to over 22-23m in recent editions.",
  "sql": "SELECT year, competitionname, competitionvenue, firstname || ' ' || lastname as winner, nationality, performance, result_numeric FROM athletics_data WHERE eventname = 'Shot Put' AND gender = 'M' AND round_normalized = 'Final' AND position = '1' AND competitionid IN ('13112510','13046619','13002354','12935526','12898707','12844203','12814135','12789100','10626603','8906660','7993620','8257083','8256922','12996366','12828581','12828580','12996365','12996362','8255184') ORDER BY year ASC",
  "chart_type": "line",
  "chart_code": "import plotly.express as px\nfig = px.line(df, x='year', y='result_numeric', text='winner', markers=True, title='Men\\'s Shot Put - World Championship Winners', color_discrete_sequence=['#007167'])\nfig.update_layout(plot_bgcolor='white', yaxis_title='Distance (m)', xaxis_title='Year')\nfig.update_traces(textposition='top center', textfont_size=9)",
  "follow_ups": [
    "Which countries have won the most Shot Put medals at Worlds?",
    "Compare Shot Put winning distances at Olympics vs World Championships",
    "Who are the current top 10 Shot Putters by WA Points?"
  ]
}
```

---

## 14. Testing Strategy

### 14.1 Unit Tests

| Test | What it validates |
|------|-------------------|
| `test_validate_sql_select` | SELECT statements pass validation |
| `test_validate_sql_with_cte` | WITH (CTE) statements pass validation |
| `test_validate_sql_rejects_insert` | INSERT/UPDATE/DELETE/DROP are rejected |
| `test_validate_sql_rejects_mixed` | `SELECT ... ; DROP TABLE` is rejected |
| `test_build_system_prompt` | System prompt includes schema, event types, and JSON format |
| `test_build_system_prompt_no_context` | Gracefully handles missing context file |
| `test_parse_json_response` | Valid JSON is parsed correctly |
| `test_parse_malformed_json` | Malformed JSON triggers fallback extraction |
| `test_auto_chart_bar` | Auto-chart produces valid bar chart |
| `test_auto_chart_line` | Auto-chart produces valid line chart |
| `test_render_chart_fallback` | Bad chart code falls through to auto-chart |

### 14.2 Integration Tests

| Test | What it validates |
|------|-------------------|
| `test_execute_query_master` | DuckDB query runs on master Parquet |
| `test_execute_query_empty` | Empty result returns empty DataFrame (not error) |
| `test_openrouter_api_call` | API returns valid response (requires API key, skip in CI) |
| `test_full_pipeline` | Question -> SQL -> Execute -> Chart -> Render (end-to-end) |

### 14.3 Manual QA Checklist

- [ ] Ask 5 different question types (athlete lookup, event comparison, championship analysis, trend, statistics)
- [ ] Toggle between Master and Full data sources
- [ ] Switch between all 3 models
- [ ] Verify charts render with Team Saudi branding
- [ ] Test follow-up suggestions (clicking should submit the question)
- [ ] Test error states (bad SQL, empty results, API timeout)
- [ ] Clear chat and verify state resets
- [ ] Verify no API key exposure in UI

---

## 15. Implementation Phases

### Phase 1: Core Pipeline (MVP)
- `ai_analytics.py` with `render_ai_analytics()`, `build_system_prompt()`, `call_openrouter()`, `execute_query()`, `validate_sql()`
- Chat interface with `st.chat_message` and `st.chat_input`
- JSON response parsing and table display
- Integration into main app as new tab
- Error handling for all failure modes

### Phase 2: Visualization
- `render_chart()` with AI-generated Plotly code execution
- `auto_chart()` fallback for failed chart code
- Team Saudi branding applied to all charts
- Expandable data tables

### Phase 3: Polish
- Follow-up suggestion buttons
- Sidebar model selector and data source toggle
- Chat history trimming (10 message pairs)
- Query result caching in session state
- Restricted `exec()` namespace for chart code security

### Phase 4: Testing and Documentation
- Unit tests for SQL validation, prompt building, JSON parsing
- Integration tests for query execution
- Update CLAUDE.md with AI Analytics module documentation
- Update requirements.txt if needed

---

## 16. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| LLM generates incorrect SQL | Wrong results shown to user | Medium | Show SQL in expander for transparency; always show data table for manual verification |
| Free-tier rate limiting | Temporary service unavailability | Medium | Multiple model options; retry button; graceful error message |
| LLM hallucinated column names | Query execution fails | Low | System prompt includes full schema; DuckDB error caught and reported |
| Large result sets slow the UI | Poor user experience | Low | Default LIMIT 100 in system prompt instructions; master dataset is small |
| Context document changes | System prompt becomes stale | Low | Context document is loaded fresh on each app start |
| exec() security vulnerability | Code injection | Very Low | Restricted namespace with no builtins; only pd, px, go, np, df available |

---

## 17. Future Enhancements

These are out of scope for the initial implementation but noted for future consideration:

1. **Saved queries** -- Allow users to bookmark useful queries for quick re-use
2. **Export chat** -- Download conversation as PDF or HTML report
3. **Multi-dataset joins** -- Query across master and full datasets simultaneously
4. **Streaming responses** -- Show AI response as it generates (requires SSE support)
5. **Prompt templates** -- Pre-built question templates for common analyses (e.g., "Championship readiness for [athlete]")
6. **Usage analytics** -- Track which questions are asked most frequently to improve the system prompt
7. **Fine-tuned models** -- If free-tier quality is insufficient, consider fine-tuning on athletics SQL examples
8. **Voice input** -- Browser microphone input for hands-free querying during coaching sessions
