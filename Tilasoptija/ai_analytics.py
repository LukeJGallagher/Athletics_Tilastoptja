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

# Max chat history to send (manage token usage)
MAX_HISTORY = 10

# Context document path
CONTEXT_DOC_PATH = os.path.join(os.path.dirname(__file__), "docs", "ai_athletics_context.md")


# ============================================================
# System Prompt Builder
# ============================================================

def _load_context_document() -> str:
    """Load the athletics context document."""
    try:
        with open(CONTEXT_DOC_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Athletics database with columns: nationality, eventname, performance, competitiondate, wapoints, gender, firstname, lastname, competitionname, round, position."


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
16. For chart_code, write valid Python using plotly.express (px) or plotly.graph_objects (go). The query result DataFrame is available as variable `df`. Always set template='plotly_dark'.

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
                # Apply Team Saudi styling
                fig.update_layout(
                    template='plotly_dark',
                    font=dict(family='Inter, sans-serif'),
                    margin=dict(l=10, r=10, t=40, b=30),
                )
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
            fig = px.bar(df.head(30), x=x_col, y=y_col, template='plotly_dark',
                        color_discrete_sequence=['#007167'])
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, template='plotly_dark',
                         color_discrete_sequence=['#007167'])
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, template='plotly_dark',
                            color_discrete_sequence=['#007167'])
        elif chart_type == "box":
            fig = px.box(df, x=x_col, y=y_col, template='plotly_dark',
                        color_discrete_sequence=['#007167'])
        else:
            fig = px.bar(df.head(30), x=x_col, y=y_col, template='plotly_dark',
                        color_discrete_sequence=['#007167'])

        fig.update_layout(
            font=dict(family='Inter, sans-serif'),
            margin=dict(l=10, r=10, t=40, b=30),
        )
        return fig
    except Exception:
        return None


# ============================================================
# Main UI
# ============================================================

def render_ai_analytics(df_all: pd.DataFrame):
    """Render the AI Analytics tab."""

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
        st.rerun()

    # Use the pre-loaded master data (96K rows - major champs + KSA)
    # Full 13M row database is too large for Streamlit Cloud memory
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

    # Display chat history
    for msg in st.session_state['ai_messages']:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                _render_assistant_message(msg)
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
            "What events does Saudi Arabia compete in?",
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


def _process_question(question: str, df_query: pd.DataFrame, model: str):
    """Process a user question and generate AI response."""
    # Add user message
    st.session_state['ai_messages'].append({"role": "user", "content": question})

    # Build message history for API
    data_source = "full" if len(df_query) > 500000 else "master"
    system_prompt = build_system_prompt(data_source)

    messages = [{"role": "system", "content": system_prompt}]

    # Add recent chat history (trimmed)
    history = st.session_state['ai_messages'][-MAX_HISTORY:]
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and "explanation" in msg:
            # Send condensed version of assistant response
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "explanation": msg.get("explanation", ""),
                    "sql": msg.get("sql", ""),
                })
            })

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

    # If query returned no results and there's no error, suggest similar names
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


def _render_assistant_message(msg: dict):
    """Render an assistant message with explanation, chart, table, and follow-ups."""
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

    # Follow-up suggestions
    follow_ups = msg.get("follow_ups", [])
    if follow_ups:
        st.markdown("**Follow-up questions:**")
        for i, fq in enumerate(follow_ups[:3]):
            st.markdown(f"- {fq}")
