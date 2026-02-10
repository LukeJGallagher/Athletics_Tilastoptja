# AI Analytics Tab - Reusable Pattern Guide

How to add a natural language "Ask your data" AI tab to any Streamlit dashboard.

---

## Architecture Overview

```
User Question (Natural Language)
        │
        ▼
┌─────────────────────┐
│  System Prompt       │ ← Domain knowledge context document
│  + Chat History      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  OpenRouter API      │ ← Free LLM models (no cost)
│  (LLM generates      │
│   JSON response)     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  JSON Response:      │
│  - explanation       │ → Shown as markdown text
│  - sql               │ → Executed via DuckDB
│  - chart_code        │ → Executed as Plotly code
│  - follow_ups        │ → Suggested next questions
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  DuckDB SQL Engine   │ ← Runs SQL against DataFrame in memory
│  (Read-only, safe)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Streamlit UI        │
│  - Chat messages     │
│  - Plotly charts     │
│  - Data tables       │
│  - SQL viewer        │
└─────────────────────┘
```

## Files You Need (3 files)

### 1. `ai_analytics.py` - The Module (~520 lines)

Copy and adapt. Key sections:

| Section | What It Does | What to Change |
|---------|-------------|----------------|
| `AVAILABLE_MODELS` | Free OpenRouter model list | Update if models change |
| `CONTEXT_DOC_PATH` | Path to domain knowledge doc | Point to your doc |
| `build_system_prompt()` | Builds LLM system prompt | Update table name, column rules |
| `call_openrouter()` | API call + JSON parsing | Usually no changes needed |
| `validate_sql()` | Blocks dangerous SQL | Usually no changes needed |
| `execute_query()` | DuckDB query execution | Change table registration name |
| `render_chart()` | Plotly chart rendering | Update brand colors |
| `render_ai_analytics()` | Main Streamlit UI | Update header text, examples |
| `_process_question()` | Orchestrates the flow | Usually no changes needed |
| `_render_assistant_message()` | Renders AI response | Usually no changes needed |

### 2. `docs/ai_context.md` - Domain Knowledge Document

This is the **most important file** for quality results. The LLM uses this as its reference.

**Must include:**
- Complete column schema with exact names, types, and examples
- Column name mapping (what the LLM should use vs what NOT to use)
- Domain-specific rules (e.g., "lower time = better" for track events)
- Example SQL queries covering common question patterns
- Any lookup values (country codes, competition IDs, event categories)

**Template structure:**
```markdown
## 1. Database Schema
### Column Reference (USE THESE EXACT NAMES)
| Column | Type | Description | Example |
...

### CRITICAL Column Name Rules
- Filtering by X: Use `Column_A` (NOT column_b)
...

## 2. Domain Knowledge
(Sport/business-specific rules, categories, standards)

## 3. SQL Query Guidelines
(Important patterns, gotchas, how to handle NULLs)

## 4. Example Queries
(10-15 example Q&A pairs with correct SQL)
```

### 3. Integration in Main App (~3 lines)

```python
# At top of main app
from ai_analytics import render_ai_analytics

# In tab/page routing
elif selected_tab == "🤖 AI Analytics":
    render_ai_analytics(df_all)
```

## Setup Steps for a New Project

### Step 1: Dependencies

Add to `requirements.txt`:
```
plotly>=5.18.0
duckdb>=0.9.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### Step 2: API Key

Get a free OpenRouter API key from https://openrouter.ai/

Add to `.env` (local):
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Add to Streamlit Cloud secrets (deployed):
```toml
OPENROUTER_API_KEY = "sk-or-v1-your-key-here"
```

### Step 3: Write the Context Document

This is the key to good results. Follow this process:

1. **Get your actual column names** - Run this after your data loading:
   ```python
   print(sorted(df.columns.tolist()))
   for col in sorted(df.columns):
       print(f'{col}: {df[col].dtype} (sample: {df[col].dropna().iloc[0]})')
   ```

2. **Document every column** with exact name, type, description, example value

3. **Document any column renaming** - If your app renames columns from raw data, the AI MUST use the renamed versions (this was our biggest bug)

4. **Add domain rules** - What does "better" mean? What are the categories? What are common filter values?

5. **Write 10-15 example queries** - Cover the most common questions users will ask. These are few-shot examples for the LLM.

### Step 4: Copy and Adapt `ai_analytics.py`

Key things to change:

```python
# 1. Table name in system prompt (line ~96)
"Write DuckDB-compatible SQL queries against the table `your_table_name`."

# 2. Table registration in execute_query() (line ~229)
conn.register('your_table_name', df_source)

# 3. Column names in system prompt rules
"7. Country codes: use `Your_Country_Column` ..."
"8. Gender: use `Your_Gender_Column` with values 'Male' or 'Female'."

# 4. Brand colors in render_chart() (line ~282)
color_discrete_sequence=['#007167']  # Your brand color

# 5. Header text in render_ai_analytics() (line ~313)
"<h2>Your Dashboard AI Assistant</h2>"

# 6. Example questions (line ~389)
examples = [
    "Your common question 1",
    "Your common question 2",
]

# 7. Data source options if you have multiple datasets
```

### Step 5: Test Locally

```bash
streamlit run your_app.py
```

Navigate to the AI tab, try the example questions first. If SQL errors occur, it's almost always wrong column names in the context document.

## Common Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `Referenced column "X" not found` | Context doc has wrong column names | Match column names to actual DataFrame |
| `404 model not found` | OpenRouter model IDs change | Check https://openrouter.ai/models/?q=free |
| `API key not found` on Cloud | `.env` doesn't work on Streamlit Cloud | Add key to `st.secrets` |
| JSON parse error | LLM returned malformed JSON | `call_openrouter()` has fallback parsing |
| Chart doesn't render | AI-generated Plotly code failed | Auto-chart fallback kicks in |
| Slow responses | Large context document | Trim unnecessary sections from context doc |

## Cost

**$0** - Uses OpenRouter free tier models. The `openrouter/free` router automatically selects the best available free model. No credit card required.

## Security

- SQL is validated as read-only (SELECT/WITH only)
- Dangerous keywords (INSERT, UPDATE, DELETE, DROP) are blocked
- DuckDB runs in-memory with no persistent storage
- Chart code execution uses restricted `__builtins__`
- API keys are never sent to the frontend

## Adapting for Other Sports/Domains

The pattern works for any tabular data:

- **Swimming**: Change event types, "lower time = better" stays, add stroke types
- **Weightlifting**: "higher weight = better", add weight categories
- **Team sports**: Add match/game structure, player positions
- **Business data**: Sales metrics, customer segments, KPIs

The only things that change are:
1. The context document (domain knowledge)
2. Column names in system prompt
3. Example queries
4. Brand colors
