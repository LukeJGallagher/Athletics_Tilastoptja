"""
AI Athletics Analytics - Natural Language Data Analysis

Hybrid approach: Natural Language → SQL + Conversational AI follow-up.
Uses OpenRouter API with athletics domain knowledge context.

Usage:
    from ai_analytics import render_ai_analytics
    render_ai_analytics(df)
"""

import os
import json
import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# DuckDB for SQL queries
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

# ============================================================
# Configuration
# ============================================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Check .env first, then Streamlit secrets (for Cloud deployment)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    try:
        OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        pass

# Free models available on OpenRouter (updated Feb 2026)
AVAILABLE_MODELS = {
    "Free Router (Recommended)": "openrouter/free",
    "StepFun Step 3.5 Flash": "stepfun/step-3.5-flash:free",
    "NVIDIA Nemotron 30B": "nvidia/nemotron-3-nano-30b-a3b:free",
    "Trinity Mini 26B": "arcee-ai/trinity-mini:free",
}

DEFAULT_MODEL = "openrouter/free"

# Max chat history to send (keep low - free models have small context windows)
MAX_HISTORY = 4

# Context document path
CONTEXT_DOC_PATH = os.path.join(os.path.dirname(__file__), "docs", "ai_athletics_context.md")


# ============================================================
# System Prompt Builder
# ============================================================

def _load_context_document() -> str:
    """Load the athletics context document (truncated to essential sections for speed)."""
    try:
        with open(CONTEXT_DOC_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        # Truncate to first ~800 lines (schema, rules, key examples)
        # Full doc is 1600+ lines - too many tokens for free models
        lines = content.split('\n')
        if len(lines) > 800:
            content = '\n'.join(lines[:800])
        return content
    except FileNotFoundError:
        return "Athletics database with columns: nationality, eventname, performance, competitiondate, wapoints, gender, firstname, lastname, competitionname, round, position."


def _get_data_summary(df: pd.DataFrame) -> str:
    """Build a compact data summary from the actual DataFrame for the AI.
    Cached in session state to avoid recomputing on every question."""
    # Return cached version if available
    if 'ai_data_summary' in st.session_state:
        return st.session_state['ai_data_summary']

    if 'Athlete_CountryCode' not in df.columns:
        return ""

    parts = []

    # KSA athlete names with their events (most important for name matching)
    if 'Athlete_Name' in df.columns and 'Event' in df.columns:
        ksa = df[df['Athlete_CountryCode'] == 'KSA']
        if not ksa.empty:
            athlete_events = ksa.groupby('Athlete_Name')['Event'].apply(
                lambda x: ', '.join(sorted(x.unique())[:3])
            )
            lines = [f"- {name}: {evts}" for name, evts in athlete_events.items()]
            parts.append("KSA ATHLETES (use LIKE '%LastName%' to search):\n" + "\n".join(lines[:60]))

    # All unique events in the database
    if 'Event' in df.columns:
        events = sorted(df['Event'].dropna().unique())
        parts.append("EVENTS IN DATABASE (use exact names in SQL):\n" + ", ".join(events))

    # Top country codes by result count
    top_countries = df['Athlete_CountryCode'].value_counts().head(40).index.tolist()
    parts.append("TOP COUNTRY CODES: " + ", ".join(top_countries))

    summary = "\n\n".join(parts)
    st.session_state['ai_data_summary'] = summary
    return summary


def build_system_prompt(data_source: str = "master") -> str:
    """Build the system prompt with schema + domain knowledge."""
    context = _load_context_document()

    db_note = ""
    if data_source == "full":
        db_note = "You are querying the FULL database (~13M rows, all athletes worldwide). "
    else:
        db_note = "You are querying the filtered database (~96K rows, major championships + KSA athletes). "

    return f"""You are an expert athletics data analyst and coaching assistant for Team Saudi Arabia.
You help coaches analyze athletics performance data using SQL queries and visualizations.

{db_note}

IMPORTANT RULES:
1. Always respond with valid JSON in the exact format specified below.
2. Write DuckDB-compatible SQL queries against the table `athletics_data`.
3. SQL must be READ-ONLY (SELECT only). Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
4. For time events (running, hurdles, relays, race walks): LOWER performance values are BETTER.
5. For field events (jumps, throws) and combined events: HIGHER values are BETTER.
6. The `Result` column is TEXT (e.g., "10.23", "1:45.67", "8.15"). Use `result_numeric` (REAL) for numeric comparisons and sorting.
7. Country codes: use `Athlete_CountryCode` (e.g., 'KSA' for Saudi Arabia, 'USA', 'JPN'). NOT nationality.
8. Gender: use `Gender` column with values 'Men' or 'Women'. NOT 'M'/'F'.
9. When asked about Saudi/KSA athletes, filter by `Athlete_CountryCode = 'KSA'`.
10. Event names: use `Event` column (e.g., '100m', 'Long Jump'). NOT eventname.
11. Competition name: use `Competition`. Date: use `Start_Date`. Athlete name: use `Athlete_Name`.
12. ALWAYS use LIKE with wildcards for athlete name searches: `WHERE Athlete_Name LIKE '%Atafi%'` NOT `= 'Atafi'`. Names may have middle names (e.g., "Abdulaziz Abdou Atafi"). Search by last name or partial name.
13. For event searches, use LIKE when the user is vague: `WHERE Event LIKE '%200%'` matches '200m'. For exact events use `= '200m'`.
14. Always include an explanation in plain English that a coach would understand.
15. Suggest 2-3 relevant follow-up questions.
16. For chart_code, write valid Python using plotly.express (px) or plotly.graph_objects (go). The query result DataFrame is available as variable `df`. Use color_discrete_sequence=['#007167','#a08e66','#005a51','#009688'] (Team Saudi teal/gold). Do NOT set template - styling is applied automatically.

COACHING-SPECIFIC RULES:
17. When asked "how far from standard" or "gap to qualification": Calculate the GAP between the athlete's PB and the entry standard. For time events: PB minus standard (negative = qualified). For field events: standard minus PB (negative = qualified). Reference Tokyo 2025 and LA 2028 standards from the context doc.
18. When asked about "rivals" or "competitors": Show athletes from Asian countries with similar performance levels. Key Asian rivals: JPN, CHN, IND, QAT, BRN, IRI, KOR, TPE, THA, KAZ, UZB. Include PB, recent form (2024-2025), and WA points.
19. When asked about Asian Games: Use CIDs 13048549 (Hangzhou 2023), 12911586 (Jakarta 2018), 12854365 (Incheon 2014). Next target: Nagoya 2026 Asian Games.
20. When asked about World Championships: Use CIDs 13112510 (Tokyo 2025), 13046619 (Budapest 2023), 13002354 (Oregon 2022), 12935526 (Doha 2019). Standards in context doc.
21. When asked about "medal chances" or "can KSA medal": Compare KSA athlete's best to historical medal performances at that championship. Include the gap to the medal line.
22. Always filter recent form with `year >= 2024` unless the user asks for historical data.
23. Include WA Points (wapoints) in results when comparing athletes - it allows cross-event comparison.
24. When showing KSA vs rivals, always include the athlete's country code so the coach can see who they're competing against.
25. NEVER include SQL code or SQL examples in the "explanation" field. The explanation must be plain English only. All SQL goes in the "sql" field. Do not suggest SQL queries the user can run - the system handles that automatically.
26. Keep explanations concise and coaching-focused. Focus on what the DATA SHOWS, not how to query it. A coach does not need to see SQL.
27. CRITICAL SQL RULE: DuckDB requires EVERY non-aggregated column in SELECT to appear in GROUP BY. If you SELECT `year, Competition, MIN(result_numeric)`, you MUST have `GROUP BY year, Competition`. Missing a column causes a Binder Error.

RESPONSE FORMAT - You MUST return valid JSON with exactly these fields:
```json
{{
  "explanation": "Plain English explanation of what the data shows and coaching insights",
  "sql": "SELECT ... FROM athletics_data WHERE ...",
  "chart_type": "bar|line|scatter|box|table|none",
  "chart_code": "fig = px.bar(df, x='column', y='column', title='Title', template='plotly_dark')",
  "follow_ups": ["Follow-up question 1", "Follow-up question 2", "Follow-up question 3"]
}}
```

If the user asks a general question that doesn't need data (e.g., "what are WA points?"), set sql to "" and chart_type to "none".

ATHLETICS DOMAIN KNOWLEDGE:
{context}
"""


# ============================================================
# OpenRouter API
# ============================================================

def call_openrouter(messages: list, model: str = DEFAULT_MODEL) -> dict:
    """Call OpenRouter API and return parsed response."""
    if not OPENROUTER_API_KEY:
        return {"error": "OpenRouter API key not configured. Add OPENROUTER_API_KEY to .env"}

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://athletics-dashboard.streamlit.app",
        "X-Title": "Saudi Athletics AI Analytics",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON from response (handle markdown code blocks)
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to extract JSON object from the response
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            # Return raw text as explanation if JSON parsing fails
            return {
                "explanation": content,
                "sql": "",
                "chart_type": "none",
                "chart_code": "",
                "follow_ups": ["Try asking a more specific question"]
            }

    except requests.exceptions.Timeout:
        return {"error": "API request timed out. Try again."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"API error: {e.response.status_code} - {e.response.text[:200]}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}


# ============================================================
# SQL Execution
# ============================================================

def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL is read-only and safe."""
    if not sql or not sql.strip():
        return True, ""  # Empty SQL is valid (informational response)

    sql_upper = sql.upper().strip()

    # Block dangerous statements
    blocked = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE']
    for keyword in blocked:
        # Check for keyword as a standalone word
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Blocked: {keyword} statements are not allowed"

    # Must start with SELECT or WITH (for CTEs)
    if not sql_upper.startswith(('SELECT', 'WITH')):
        return False, "Only SELECT queries are allowed"

    return True, ""


def execute_query(sql: str, df_source: pd.DataFrame = None) -> tuple[pd.DataFrame, str]:
    """Execute SQL query via DuckDB. Returns (result_df, error_message)."""
    if not sql or not sql.strip():
        return pd.DataFrame(), ""

    is_valid, error = validate_sql(sql)
    if not is_valid:
        return pd.DataFrame(), error

    if not DUCKDB_AVAILABLE:
        return pd.DataFrame(), "DuckDB not available"

    try:
        conn = duckdb.connect(':memory:')
        if df_source is not None and not df_source.empty:
            conn.register('athletics_data', df_source)
        else:
            return pd.DataFrame(), "No data loaded"

        result = conn.execute(sql).fetchdf()
        conn.close()
        return result, ""
    except Exception as e:
        return pd.DataFrame(), f"SQL Error: {str(e)}"


def _suggest_names(query_text: str, df: pd.DataFrame, max_suggestions: int = 5) -> list[str]:
    """Find similar athlete names when a search returns no results."""
    if 'Athlete_Name' not in df.columns:
        return []

    # Extract potential name keywords from the user query (skip common words)
    skip_words = {'show', 'me', 'the', 'all', 'results', 'for', 'of', 'in', 'at',
                  'performance', 'summary', 'compare', 'how', 'what', 'who', 'is',
                  'are', 'was', 'were', 'did', 'does', 'can', 'could', 'would',
                  '100m', '200m', '400m', '800m', '1500m', 'metres', 'meters',
                  'long', 'jump', 'high', 'shot', 'put', 'discus', 'javelin',
                  'hammer', 'throw', 'hurdles', 'relay', 'marathon', 'walk',
                  'men', 'women', 'ksa', 'saudi', 'arabia', 'best', 'fastest',
                  'top', 'recent', 'season', 'year', '2024', '2025', '2026'}

    words = [w for w in re.split(r'[\s,.\-\']+', query_text.lower()) if len(w) > 2 and w not in skip_words]
    if not words:
        return []

    # Search for names containing any of these keywords
    names = df['Athlete_Name'].dropna().unique()
    matches = []
    for name in names:
        name_lower = name.lower()
        for word in words:
            if word in name_lower:
                matches.append(name)
                break

    # Deduplicate and limit
    return list(dict.fromkeys(matches))[:max_suggestions]


# ============================================================
# Chart Rendering
# ============================================================

def render_chart(chart_code: str, chart_type: str, df: pd.DataFrame) -> go.Figure:
    """Execute Plotly chart code from AI response."""
    if chart_type == "none" or chart_type == "table" or df.empty:
        return None

    # Try AI-generated chart code first
    if chart_code and chart_code.strip():
        try:
            local_vars = {"df": df, "px": px, "go": go, "pd": pd}
            exec(chart_code, {"__builtins__": {}}, local_vars)
            fig = local_vars.get("fig")
            if fig is not None:
                _apply_team_saudi_style(fig)
                return fig
        except Exception as e:
            pass  # Fall through to auto-chart

    # Auto-chart fallback based on chart_type
    try:
        if len(df.columns) < 2:
            return None

        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        string_cols = df.select_dtypes(include='object').columns.tolist()

        if not numeric_cols:
            return None

        x_col = string_cols[0] if string_cols else df.columns[0]
        y_col = numeric_cols[0]

        if chart_type == "bar":
            fig = px.bar(df.head(30), x=x_col, y=y_col,
                        color_discrete_sequence=_TS_COLOR_SEQUENCE)
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col,
                         color_discrete_sequence=_TS_COLOR_SEQUENCE)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col,
                            color_discrete_sequence=_TS_COLOR_SEQUENCE)
        elif chart_type == "box":
            fig = px.box(df, x=x_col, y=y_col,
                        color_discrete_sequence=_TS_COLOR_SEQUENCE)
        else:
            fig = px.bar(df.head(30), x=x_col, y=y_col,
                        color_discrete_sequence=_TS_COLOR_SEQUENCE)

        _apply_team_saudi_style(fig)
        return fig
    except Exception:
        return None


# ============================================================
# Main UI
# ============================================================

def render_ai_analytics(df_all: pd.DataFrame):
    """Render the AI Analytics tab with sub-tabs for navigation."""

    # Header
    st.markdown("""
    <div style="background: linear-gradient(135deg, #007167 0%, #005a51 100%);
         padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #a08e66;">
        <h2 style="color: white; margin: 0;">AI Athletics Analyst</h2>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0;">
            Ask questions about athletics data in plain English. Get SQL queries, charts, and coaching insights.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Check API key
    if not OPENROUTER_API_KEY:
        st.error("OpenRouter API key not found. Add `OPENROUTER_API_KEY` to your `.env` file.")
        return

    # Sidebar controls
    st.sidebar.markdown("### AI Analytics Settings")

    model_name = st.sidebar.selectbox(
        "AI Model",
        list(AVAILABLE_MODELS.keys()),
        index=0,
        key="ai_model_select"
    )
    selected_model = AVAILABLE_MODELS[model_name]

    if st.sidebar.button("Clear Chat", key="ai_clear_chat"):
        st.session_state['ai_chat_history'] = []
        st.session_state['ai_messages'] = []
        st.session_state.pop('ai_data_summary', None)
        st.rerun()

    # Use the pre-loaded master data (96K rows - major champs + KSA)
    df_query = df_all

    # Show data info
    st.sidebar.markdown(f"**Rows:** {len(df_query):,}")
    if 'Athlete_CountryCode' in df_query.columns:
        n_countries = df_query['Athlete_CountryCode'].nunique()
        st.sidebar.markdown(f"**Countries:** {n_countries}")
    if 'Event' in df_query.columns:
        n_events = df_query['Event'].nunique()
        st.sidebar.markdown(f"**Events:** {n_events}")

    # Initialize chat history
    if 'ai_messages' not in st.session_state:
        st.session_state['ai_messages'] = []

    # --- Sub-tabs for navigation ---
    tab_chat, tab_standards, tab_rivals, tab_champs = st.tabs([
        "💬 AI Chat",
        "📏 Standards Gap",
        "⚔️ Rival Watch",
        "🏆 Championship History",
    ])

    # --- TAB 1: AI Chat (main chat interface) ---
    with tab_chat:
        _render_chat_tab(df_query, selected_model)

    # --- TAB 2: Standards Gap ---
    with tab_standards:
        _render_standards_gap_tab(df_query, selected_model)

    # --- TAB 3: Rival Watch ---
    with tab_rivals:
        _render_rival_watch_tab(df_query, selected_model)

    # --- TAB 4: Championship History ---
    with tab_champs:
        _render_championship_history_tab(df_query, selected_model)


def _render_chat_tab(df_query: pd.DataFrame, selected_model: str):
    """Render the main AI chat interface."""
    # Display chat history
    for idx, msg in enumerate(st.session_state['ai_messages']):
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                _render_assistant_message(msg, idx, df_query, selected_model)
            else:
                st.markdown(msg["content"])

    # Example queries (only show when chat is empty)
    if not st.session_state['ai_messages']:
        st.markdown("**Try asking:**")
        example_cols = st.columns(2)
        examples = [
            "Show me the top 10 KSA athletes by WA points",
            "Who are the fastest 100m runners in 2024?",
            "Compare KSA vs Japan in 400m hurdles",
            "How far are KSA sprinters from World Championship standards?",
        ]
        for i, example in enumerate(examples):
            with example_cols[i % 2]:
                if st.button(example, key=f"example_{i}", use_container_width=True):
                    _process_question(example, df_query, selected_model)
                    st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about athletics data..."):
        _process_question(prompt, df_query, selected_model)
        st.rerun()


def _render_standards_gap_tab(df_query: pd.DataFrame, selected_model: str):
    """Pre-built view: KSA athletes vs qualification standards. Direct SQL for speed."""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #005a51 0%, #007167 100%);
         padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
        <h3 style="color: white; margin: 0;">KSA Standards Gap Analysis</h3>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">
            How far are Saudi athletes from Tokyo 2025 WC and LA 2028 Olympic standards?
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'standards_active_query' not in st.session_state:
        st.session_state['standards_active_query'] = None

    cols = st.columns(4)
    with cols[0]:
        if st.button("KSA PBs & WA Points", key="std_0", use_container_width=True):
            st.session_state['standards_active_query'] = 'pbs'
    with cols[1]:
        if st.button("Top KSA by Event", key="std_1", use_container_width=True):
            st.session_state['standards_active_query'] = 'by_event'
    with cols[2]:
        if st.button("Recent Form 2024-25", key="std_2", use_container_width=True):
            st.session_state['standards_active_query'] = 'recent_form'
    with cols[3]:
        if st.button("Improving Athletes", key="std_3", use_container_width=True):
            st.session_state['standards_active_query'] = 'improving'

    active = st.session_state.get('standards_active_query')

    if active == 'pbs':
        sql = """SELECT Athlete_Name, Event, Gender,
               MIN(CASE WHEN Event IN ('High Jump','Pole Vault','Long Jump','Triple Jump',
                   'Shot Put','Discus Throw','Hammer Throw','Javelin Throw','Decathlon','Heptathlon')
                   THEN NULL ELSE result_numeric END) AS best_time,
               MAX(CASE WHEN Event IN ('High Jump','Pole Vault','Long Jump','Triple Jump',
                   'Shot Put','Discus Throw','Hammer Throw','Javelin Throw','Decathlon','Heptathlon')
                   THEN result_numeric ELSE NULL END) AS best_distance,
               MAX(wapoints) AS best_wapoints,
               COUNT(*) AS total_results
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND year >= 2023
        GROUP BY Athlete_ID, Athlete_Name, Event, Gender
        ORDER BY best_wapoints DESC
        LIMIT 30"""
        _run_direct_query(sql, df_query, "KSA Athletes - Personal Bests & WA Points",
                          chart_type="bar", x_col="Athlete_Name", y_col="best_wapoints")

    elif active == 'by_event':
        sql = """SELECT Event, Gender, Athlete_Name,
               MIN(result_numeric) AS best_result,
               MAX(wapoints) AS best_wapoints,
               COUNT(*) AS races
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND year >= 2023
        GROUP BY Event, Gender, Athlete_ID, Athlete_Name
        ORDER BY Event, Gender, best_wapoints DESC"""
        _run_direct_query(sql, df_query, "KSA Best Athletes by Event",
                          chart_type="bar", x_col="Event", y_col="best_wapoints", color_col="Athlete_Name")

    elif active == 'recent_form':
        sql = """SELECT Athlete_Name, Event,
               MIN(CASE WHEN year = 2025 THEN result_numeric END) AS sb_2025,
               MIN(CASE WHEN year = 2024 THEN result_numeric END) AS sb_2024,
               MAX(CASE WHEN year = 2025 THEN wapoints END) AS wapts_2025,
               MAX(CASE WHEN year = 2024 THEN wapoints END) AS wapts_2024,
               COUNT(CASE WHEN year >= 2024 THEN 1 END) AS races_recent
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND year >= 2024
        GROUP BY Athlete_ID, Athlete_Name, Event
        HAVING COUNT(CASE WHEN year >= 2024 THEN 1 END) >= 2
        ORDER BY MAX(wapoints) DESC
        LIMIT 25"""
        _run_direct_query(sql, df_query, "KSA Recent Form (2024-2025)",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapts_2025")

    elif active == 'improving':
        sql = """SELECT Athlete_Name, Event,
               COUNT(CASE WHEN PB = 'PB' AND year >= 2024 THEN 1 END) AS recent_pbs,
               COUNT(CASE WHEN SB = 'SB' AND year = 2025 THEN 1 END) AS season_bests_2025,
               MAX(wapoints) AS peak_wapoints,
               COUNT(*) AS total_results
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND year >= 2023
        GROUP BY Athlete_ID, Athlete_Name, Event
        HAVING COUNT(*) >= 3
        ORDER BY recent_pbs DESC, peak_wapoints DESC
        LIMIT 20"""
        _run_direct_query(sql, df_query, "KSA Athletes with Improving Form",
                          chart_type="bar", x_col="Athlete_Name", y_col="recent_pbs")

    else:
        st.info("Select a query above to see results instantly.")


def _render_rival_watch_tab(df_query: pd.DataFrame, selected_model: str):
    """Pre-built view: KSA vs Asian rivals by event. Uses direct SQL for speed."""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #005a51 0%, #007167 100%);
         padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
        <h3 style="color: white; margin: 0;">Rival Watch</h3>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">
            Monitor KSA athletes vs key Asian and regional competitors
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Determine if event is time-based (lower=better) or distance-based (higher=better)
    TIME_EVENTS = {'100m', '200m', '400m', '800m', '1500m', '5000m', '10000m',
                   '110m Hurdles', '100m Hurdles', '400m Hurdles', '3000m Steeplechase',
                   'Marathon', '20km Race Walk', '35km Race Walk'}

    # Event selector for rival comparison
    col1, col2 = st.columns(2)
    with col1:
        event_choice = st.selectbox(
            "Select Event",
            ["100m", "200m", "400m", "800m", "1500m", "110m Hurdles", "400m Hurdles",
             "High Jump", "Long Jump", "Triple Jump", "Shot Put", "Discus Throw",
             "Javelin Throw", "Hammer Throw"],
            key="rival_event_select"
        )
    with col2:
        gender_choice = st.selectbox("Gender", ["Men", "Women"], key="rival_gender_select")

    is_time = event_choice in TIME_EVENTS
    sort_col = "best_time" if is_time else "best_distance"
    sort_dir = "ASC" if is_time else "DESC"
    agg_fn = "MIN" if is_time else "MAX"
    asian_countries = "'KSA','JPN','CHN','IND','QAT','BRN','IRI','KOR','TPE','THA','KAZ','UZB','PHI','SRI','HKG','MAS','SIN','BAN','PAK'"

    # Initialize session state for which query to show
    if 'rival_active_query' not in st.session_state:
        st.session_state['rival_active_query'] = None

    cols = st.columns(4)
    with cols[0]:
        if st.button("KSA vs Rivals", key="rival_0", use_container_width=True):
            st.session_state['rival_active_query'] = 'ksa_vs_rivals'
    with cols[1]:
        if st.button("Top 20 Asia", key="rival_1", use_container_width=True):
            st.session_state['rival_active_query'] = 'top_20'
    with cols[2]:
        if st.button("Asian Games 2023", key="rival_2", use_container_width=True):
            st.session_state['rival_active_query'] = 'asian_games'
    with cols[3]:
        if st.button("Form Trend", key="rival_3", use_container_width=True):
            st.session_state['rival_active_query'] = 'form_trend'

    active = st.session_state.get('rival_active_query')

    if active == 'ksa_vs_rivals':
        sql = f"""SELECT Athlete_Name, Athlete_CountryCode AS Country,
               {agg_fn}(result_numeric) AS {sort_col},
               MAX(wapoints) AS best_wapoints,
               COUNT(*) AS races
        FROM athletics_data
        WHERE Event = '{event_choice}' AND Gender = '{gender_choice}'
          AND Athlete_CountryCode IN ({asian_countries})
          AND result_numeric IS NOT NULL AND year >= 2024
        GROUP BY Athlete_ID, Athlete_Name, Athlete_CountryCode
        ORDER BY {sort_col} {sort_dir}
        LIMIT 30"""
        _run_direct_query(sql, df_query, f"KSA vs Asian Rivals - {gender_choice}'s {event_choice}",
                          chart_type="bar", x_col="Athlete_Name", y_col=sort_col, color_col="Country")

    elif active == 'top_20':
        sql = f"""SELECT Athlete_Name, Athlete_CountryCode AS Country,
               {agg_fn}(result_numeric) AS {sort_col},
               MAX(wapoints) AS best_wapoints
        FROM athletics_data
        WHERE Event = '{event_choice}' AND Gender = '{gender_choice}'
          AND Athlete_CountryCode IN ({asian_countries})
          AND result_numeric IS NOT NULL AND year >= 2024
        GROUP BY Athlete_ID, Athlete_Name, Athlete_CountryCode
        ORDER BY {sort_col} {sort_dir}
        LIMIT 20"""
        _run_direct_query(sql, df_query, f"Top 20 Asian {gender_choice}'s {event_choice} (2024-25)",
                          chart_type="bar", x_col="Athlete_Name", y_col=sort_col, color_col="Country",
                          hover_cols=["best_wapoints"])

    elif active == 'asian_games':
        sql = f"""SELECT Athlete_Name, Athlete_CountryCode AS Country,
               Result, result_numeric, CAST(Position AS INTEGER) AS Place,
               round_normalized AS Round, wapoints
        FROM athletics_data
        WHERE Event = '{event_choice}' AND Gender = '{gender_choice}'
          AND Competition_ID = '13048549'
          AND result_numeric IS NOT NULL
        ORDER BY round_normalized DESC, result_numeric {sort_dir}"""
        _run_direct_query(sql, df_query, f"Asian Games 2023 - {gender_choice}'s {event_choice}",
                          chart_type="bar", x_col="Athlete_Name", y_col="result_numeric", color_col="Country")

    elif active == 'form_trend':
        sql = f"""WITH ksa_best AS (
            SELECT Athlete_Name, Athlete_ID, {agg_fn}(result_numeric) AS pb
            FROM athletics_data
            WHERE Event = '{event_choice}' AND Gender = '{gender_choice}'
              AND Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND year >= 2023
            GROUP BY Athlete_ID, Athlete_Name
            ORDER BY pb {sort_dir} LIMIT 1
        ),
        rival_best AS (
            SELECT Athlete_Name, Athlete_ID, {agg_fn}(result_numeric) AS pb
            FROM athletics_data
            WHERE Event = '{event_choice}' AND Gender = '{gender_choice}'
              AND Athlete_CountryCode != 'KSA'
              AND Athlete_CountryCode IN ({asian_countries})
              AND result_numeric IS NOT NULL AND year >= 2023
            GROUP BY Athlete_ID, Athlete_Name
            ORDER BY pb {sort_dir} LIMIT 1
        )
        SELECT a.Start_Date, a.Athlete_Name, a.Result, a.result_numeric, a.wapoints, a.Competition
        FROM athletics_data a
        WHERE a.Event = '{event_choice}' AND a.Gender = '{gender_choice}'
          AND a.result_numeric IS NOT NULL AND a.year >= 2023
          AND (a.Athlete_ID IN (SELECT Athlete_ID FROM ksa_best)
               OR a.Athlete_ID IN (SELECT Athlete_ID FROM rival_best))
        ORDER BY a.Start_Date ASC"""
        _run_direct_query(sql, df_query, f"Form Trend - {gender_choice}'s {event_choice}",
                          chart_type="line", x_col="Start_Date", y_col="result_numeric", color_col="Athlete_Name")

    else:
        st.info("Select a query above to see results instantly.")


def _render_championship_history_tab(df_query: pd.DataFrame, selected_model: str):
    """Pre-built view: KSA results at major championships. Direct SQL for speed."""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #005a51 0%, #007167 100%);
         padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
        <h3 style="color: white; margin: 0;">Championship History</h3>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">
            KSA performance at Olympics, World Championships, and Asian Games
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'champ_active_query' not in st.session_state:
        st.session_state['champ_active_query'] = None

    cols = st.columns(3)
    with cols[0]:
        if st.button("Asian Games 2023", key="champ_0", use_container_width=True):
            st.session_state['champ_active_query'] = 'ag2023'
    with cols[1]:
        if st.button("World Champs", key="champ_1", use_container_width=True):
            st.session_state['champ_active_query'] = 'wc'
    with cols[2]:
        if st.button("Olympics", key="champ_2", use_container_width=True):
            st.session_state['champ_active_query'] = 'olympics'

    cols2 = st.columns(3)
    with cols2[0]:
        if st.button("Best KSA Performances", key="champ_3", use_container_width=True):
            st.session_state['champ_active_query'] = 'best'
    with cols2[1]:
        if st.button("Medal/Final Appearances", key="champ_4", use_container_width=True):
            st.session_state['champ_active_query'] = 'medals'
    with cols2[2]:
        if st.button("Asian Championships", key="champ_5", use_container_width=True):
            st.session_state['champ_active_query'] = 'asian_champs'

    active = st.session_state.get('champ_active_query')

    if active == 'ag2023':
        sql = """SELECT Event, Athlete_Name, Result, result_numeric,
               CAST(Position AS INTEGER) AS Place, round_normalized AS Round, wapoints
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND Competition_ID = '13048549'
          AND result_numeric IS NOT NULL
        ORDER BY Event, CASE round_normalized WHEN 'Final' THEN 1 WHEN 'Semi Finals' THEN 2 ELSE 3 END,
          CAST(Position AS INTEGER)"""
        _run_direct_query(sql, df_query, "KSA at Asian Games 2023 (Hangzhou)",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints")

    elif active == 'wc':
        sql = """SELECT Competition, year, Event, Athlete_Name, Result, result_numeric,
               CAST(Position AS INTEGER) AS Place, round_normalized AS Round, wapoints
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA'
          AND Competition_ID IN ('13112510','13046619','13002354','12935526')
          AND result_numeric IS NOT NULL
        ORDER BY year DESC, Event, CASE round_normalized WHEN 'Final' THEN 1 WHEN 'Semi Finals' THEN 2 ELSE 3 END"""
        _run_direct_query(sql, df_query, "KSA at World Championships",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints", color_col="Competition")

    elif active == 'olympics':
        sql = """SELECT Competition, year, Event, Athlete_Name, Result, result_numeric,
               CAST(Position AS INTEGER) AS Place, round_normalized AS Round, wapoints
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA'
          AND Competition_ID IN ('13079218','12992925','12877460','12758073','12643829','12487530','12354259',
                                 '12234260','12115891','12011695','11907911')
          AND result_numeric IS NOT NULL
        ORDER BY year DESC, Event"""
        _run_direct_query(sql, df_query, "KSA Olympic History",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints", color_col="Competition")

    elif active == 'best':
        sql = """SELECT Competition, year, Event, Athlete_Name, Result, result_numeric,
               CAST(Position AS INTEGER) AS Place, wapoints
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL AND wapoints IS NOT NULL
        ORDER BY wapoints DESC
        LIMIT 20"""
        _run_direct_query(sql, df_query, "Top 20 KSA Championship Performances by WA Points",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints", color_col="Event")

    elif active == 'medals':
        sql = """SELECT Competition, year, Event, Athlete_Name, Result,
               CAST(Position AS INTEGER) AS Place, round_normalized AS Round, wapoints,
               CASE
                 WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 1 THEN 'GOLD'
                 WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 2 THEN 'SILVER'
                 WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 3 THEN 'BRONZE'
                 WHEN round_normalized = 'Final' THEN 'Finalist'
                 ELSE 'Semi/Heat'
               END AS Achievement
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA' AND result_numeric IS NOT NULL
          AND (round_normalized = 'Final' OR round_normalized = 'Semi Finals')
        ORDER BY year DESC, CASE round_normalized WHEN 'Final' THEN 1 ELSE 2 END,
          CAST(Position AS INTEGER)"""
        _run_direct_query(sql, df_query, "KSA Medal & Final Appearances",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints", color_col="Achievement")

    elif active == 'asian_champs':
        sql = """SELECT Competition, year, Event, Athlete_Name, Result, result_numeric,
               CAST(Position AS INTEGER) AS Place, round_normalized AS Round, wapoints
        FROM athletics_data
        WHERE Athlete_CountryCode = 'KSA'
          AND Competition_ID IN ('13105634','13045167','12927085','12897142','12847574',
                                 '12805200','12757025','12714455','12672791','12637539','12596668')
          AND result_numeric IS NOT NULL
        ORDER BY year DESC, Event, CAST(Position AS INTEGER)"""
        _run_direct_query(sql, df_query, "KSA at Asian Athletics Championships",
                          chart_type="bar", x_col="Athlete_Name", y_col="wapoints", color_col="Competition")

    else:
        st.info("Select a query above to see results instantly.")


# Team Saudi brand colors for charts
_TS_TEAL = '#007167'
_TS_GOLD = '#a08e66'
_TS_DARK_TEAL = '#005a51'
_TS_LIGHT_TEAL = '#009688'
_TS_COLOR_SEQUENCE = ['#007167', '#a08e66', '#005a51', '#009688', '#78909C',
                      '#0077B6', '#FFB800', '#dc3545', '#6c757d', '#2E86AB']


def _apply_team_saudi_style(fig: go.Figure) -> go.Figure:
    """Apply Team Saudi branding to a Plotly figure."""
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Inter, sans-serif', color='#333'),
        showlegend=True,
        margin=dict(l=10, r=10, t=40, b=30),
        colorway=_TS_COLOR_SEQUENCE,
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    return fig


def _run_direct_query(sql: str, df_source: pd.DataFrame, title: str = "",
                      chart_type: str = "bar", x_col: str = None, y_col: str = None,
                      color_col: str = None, hover_cols: list = None) -> None:
    """Execute SQL directly and render results without AI roundtrip. Instant."""
    result, error = execute_query(sql, df_source)
    if error:
        st.error(f"Query error: {error}")
        with st.expander("View SQL", expanded=False):
            st.code(sql, language="sql")
        return
    if result.empty:
        st.warning("No results found for this query.")
        with st.expander("View SQL", expanded=False):
            st.code(sql, language="sql")
        return

    # Show data table
    st.dataframe(result, use_container_width=True, hide_index=True)

    # Auto-generate chart if we have enough data
    if len(result) >= 2 and chart_type != "none":
        try:
            numeric_cols = result.select_dtypes(include='number').columns.tolist()
            string_cols = result.select_dtypes(include='object').columns.tolist()
            _x = x_col or (string_cols[0] if string_cols else result.columns[0])
            _y = y_col or (numeric_cols[0] if numeric_cols else result.columns[1])
            _color = color_col if color_col and color_col in result.columns else None
            _hover = hover_cols if hover_cols else None

            if chart_type == "bar":
                fig = px.bar(result, x=_x, y=_y, color=_color, title=title,
                             hover_data=_hover,
                             color_discrete_sequence=_TS_COLOR_SEQUENCE)
            elif chart_type == "line":
                fig = px.line(result, x=_x, y=_y, color=_color, title=title,
                              hover_data=_hover,
                              color_discrete_sequence=_TS_COLOR_SEQUENCE)
            elif chart_type == "scatter":
                fig = px.scatter(result, x=_x, y=_y, color=_color, title=title,
                                 hover_data=_hover,
                                 color_discrete_sequence=_TS_COLOR_SEQUENCE)
            else:
                fig = None

            if fig:
                _apply_team_saudi_style(fig)
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass  # Skip chart on error

    with st.expander("View SQL", expanded=False):
        st.code(sql, language="sql")


def _show_last_relevant_result(pattern: str):
    """Show the most recent AI result that matches a keyword pattern."""
    if not st.session_state.get('ai_messages'):
        st.info("Click a button above to run a query, or ask your own question in the AI Chat tab.")
        return

    # Show the latest assistant message (results carry across tabs)
    for msg in reversed(st.session_state['ai_messages']):
        if msg["role"] == "assistant" and not msg.get("error"):
            _render_assistant_message(msg)
            break


def _detect_name_words(question: str) -> list[str]:
    """Detect likely athlete name words in a question."""
    skip = {'show', 'me', 'the', 'all', 'results', 'for', 'of', 'in', 'at', 'and',
            'performance', 'summary', 'compare', 'how', 'what', 'who', 'is', 'his', 'her',
            'are', 'was', 'were', 'did', 'does', 'can', 'could', 'would', 'chances',
            '100m', '200m', '400m', '800m', '1500m', '5000m', '10000m', 'metres', 'meters',
            'long', 'jump', 'high', 'shot', 'put', 'discus', 'javelin', 'hammer', 'throw',
            'hurdles', 'relay', 'marathon', 'walk', 'steeplechase', 'triple', 'pole', 'vault',
            'men', 'women', 'ksa', 'saudi', 'arabia', 'best', 'fastest', 'slowest',
            'top', 'recent', 'season', 'year', 'from', 'standard', 'gap', 'rivals',
            'medal', 'final', 'asian', 'games', 'world', 'championship', 'olympic',
            'what', 'about', 'their', 'form', 'trend', 'improving', 'compared', 'with', 'vs'}
    words = [w for w in re.split(r'[\s,.\-\']+', question) if len(w) > 2 and w.lower() not in skip]
    # Capitalized words are likely names
    return [w for w in words if w[0].isupper() or w.isupper()]


def _process_question(question: str, df_query: pd.DataFrame, model: str):
    """Process a user question and generate AI response."""
    # Add user message
    st.session_state['ai_messages'].append({"role": "user", "content": question})

    # Build message history for API
    data_source = "full" if len(df_query) > 500000 else "master"
    system_prompt = build_system_prompt(data_source)

    messages = [{"role": "system", "content": system_prompt}]

    # Inject compact data reference (real names, events, countries from the database)
    data_summary = _get_data_summary(df_query)
    if data_summary:
        messages.append({
            "role": "system",
            "content": f"DATA REFERENCE (actual values in the database - use these exact names/events in SQL):\n{data_summary}"
        })

    # Add recent chat history (very condensed to save tokens for free models)
    history = st.session_state['ai_messages'][-MAX_HISTORY:]
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and "explanation" in msg:
            # Send minimal summary - free models have small context windows
            explanation = msg.get("explanation", "")
            # Truncate long explanations to first 200 chars
            short_explanation = explanation[:200] + "..." if len(explanation) > 200 else explanation
            messages.append({
                "role": "assistant",
                "content": short_explanation
            })

    # Inject critical SQL reminders into the user message to prevent rule-forgetting
    # on multi-turn conversations (free models have small context windows)
    name_words = _detect_name_words(question)

    # Try to match name words to actual KSA athletes for better hints
    name_hint = ""
    if name_words and 'Athlete_Name' in df_query.columns:
        ksa_df = df_query[df_query.get('Athlete_CountryCode', pd.Series()) == 'KSA'] if 'Athlete_CountryCode' in df_query.columns else df_query
        for nw in name_words:
            matches = ksa_df[ksa_df['Athlete_Name'].str.contains(nw, case=False, na=False)]['Athlete_Name'].unique()
            if len(matches) > 0:
                name_hint = f" Full name in database: '{matches[0]}'."
                break

    enhanced_question = question
    if name_words:
        like_hint = " AND ".join(f"Athlete_Name LIKE '%{w}%'" for w in name_words[-2:])
        enhanced_question += f"\n[IMPORTANT: Use LIKE wildcards for names: WHERE {like_hint}.{name_hint} Gender uses 'Men'/'Women'. All non-aggregated columns must be in GROUP BY.]"
    else:
        enhanced_question += "\n[IMPORTANT: Use LIKE for name searches. Gender uses 'Men'/'Women'. All non-aggregated columns must be in GROUP BY.]"

    # Replace the last user message with the enhanced version for the API only
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] = enhanced_question

    # Call API
    response = call_openrouter(messages, model)

    if "error" in response:
        st.session_state['ai_messages'].append({
            "role": "assistant",
            "content": response["error"],
            "explanation": response["error"],
            "sql": "",
            "chart_type": "none",
            "chart_code": "",
            "follow_ups": [],
            "query_result": None,
            "error": True,
        })
        return

    # Execute SQL if provided
    sql = response.get("sql", "")
    query_result = pd.DataFrame()
    query_error = ""

    if sql:
        query_result, query_error = execute_query(sql, df_query)

        # Auto-retry on common SQL errors (ask LLM to fix its own SQL)
        if query_error and ("Binder Error" in query_error or "not found" in query_error):
            fix_messages = messages + [
                {"role": "assistant", "content": json.dumps({"sql": sql})},
                {"role": "user", "content": f"Your SQL had an error: {query_error}\nFix the SQL and return the corrected JSON response. Remember: all non-aggregated SELECT columns must be in GROUP BY."}
            ]
            retry_response = call_openrouter(fix_messages, model)
            if "error" not in retry_response:
                retry_sql = retry_response.get("sql", "")
                if retry_sql and retry_sql != sql:
                    sql = retry_sql
                    query_result, query_error = execute_query(sql, df_query)
                    if not query_error:
                        response = retry_response  # Use the fixed response

    # Auto-retry on empty results when names were detected (model may have used = instead of LIKE)
    if sql and query_result.empty and not query_error and name_words:
        # Check if the SQL used = instead of LIKE for names
        if "= '" in sql and "Athlete_Name" in sql:
            fix_messages = messages + [
                {"role": "assistant", "content": json.dumps({"sql": sql})},
                {"role": "user", "content": f"Your SQL returned no results because you used exact match (=) for athlete names. Use LIKE with wildcards instead. For example: WHERE Athlete_Name LIKE '%{name_words[-1]}%'. Fix and return corrected JSON."}
            ]
            retry_response = call_openrouter(fix_messages, model)
            if "error" not in retry_response:
                retry_sql = retry_response.get("sql", "")
                if retry_sql and retry_sql != sql:
                    sql = retry_sql
                    query_result, query_error = execute_query(sql, df_query)
                    if not query_error and not query_result.empty:
                        response = retry_response

    # If still no results, suggest similar names
    name_suggestions = []
    if sql and query_result.empty and not query_error:
        name_suggestions = _suggest_names(question, df_query)

    # Build chart
    chart_fig = None
    if not query_result.empty:
        chart_fig = render_chart(
            response.get("chart_code", ""),
            response.get("chart_type", "table"),
            query_result,
        )

    # Store assistant response
    st.session_state['ai_messages'].append({
        "role": "assistant",
        "content": response.get("explanation", ""),
        "explanation": response.get("explanation", ""),
        "sql": sql,
        "chart_type": response.get("chart_type", "none"),
        "chart_code": response.get("chart_code", ""),
        "follow_ups": response.get("follow_ups", []),
        "query_result": query_result if not query_result.empty else None,
        "query_error": query_error,
        "chart_fig": chart_fig,
        "name_suggestions": name_suggestions,
    })


def _render_assistant_message(msg: dict, msg_idx: int = 0, df_query: pd.DataFrame = None, selected_model: str = DEFAULT_MODEL):
    """Render an assistant message with explanation, chart, table, and clickable follow-ups."""
    # Error state
    if msg.get("error"):
        st.error(msg.get("explanation", "An error occurred"))
        return

    # Explanation
    explanation = msg.get("explanation", "")
    if explanation:
        st.markdown(explanation)

    # Query error
    if msg.get("query_error"):
        st.warning(f"Query issue: {msg['query_error']}")

    # Chart
    chart_fig = msg.get("chart_fig")
    if chart_fig is not None:
        st.plotly_chart(chart_fig, use_container_width=True)

    # Data table - show directly (not hidden in expander)
    query_result = msg.get("query_result")
    sql = msg.get("sql", "")
    if query_result is not None and not query_result.empty:
        st.markdown(f"**Results: {len(query_result):,} rows**")
        st.dataframe(query_result, use_container_width=True, hide_index=True)
    elif sql and not msg.get("query_error"):
        st.info("Query returned no results. Try broadening your search.")
        # Show name suggestions if available
        suggestions = msg.get("name_suggestions", [])
        if suggestions:
            suggestion_text = ", ".join(f"**{name}**" for name in suggestions)
            st.markdown(f"Did you mean: {suggestion_text}?")
            st.caption("Try re-asking with the full athlete name above.")

    # SQL (collapsible)
    if sql:
        with st.expander("View SQL Query", expanded=False):
            st.code(sql, language="sql")

    # Follow-up suggestions as clickable buttons
    follow_ups = msg.get("follow_ups", [])
    if follow_ups and df_query is not None:
        st.markdown("**Follow-up questions:**")
        fu_cols = st.columns(min(len(follow_ups[:3]), 3))
        for i, fq in enumerate(follow_ups[:3]):
            with fu_cols[i]:
                if st.button(fq, key=f"followup_{msg_idx}_{i}", use_container_width=True):
                    _process_question(fq, df_query, selected_model)
                    st.rerun()
    elif follow_ups:
        # Fallback if no df_query (e.g. rendered from non-chat tab)
        st.markdown("**Follow-up questions:**")
        for fq in follow_ups[:3]:
            st.markdown(f"- {fq}")
