"""
Coach View Module for Athletics Dashboard

Provides simplified, action-focused interface for coaches including:
- Competition Prep Hub - Select championship, view KSA squad
- Athlete Report Cards - Comprehensive athlete briefings
- Competitor Watch - Monitor rivals and gaps
- Export Center - Generate PDF/HTML reports

This module integrates with the main dashboard via view mode toggle.
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics

# Import our custom modules
from projection_engine import (
    project_performance, calculate_gap, format_gap, detect_trend,
    get_trend_symbol, calculate_form_score, compare_to_competitors,
    calculate_advancement_probability, METHODOLOGY_NOTES
)
from historical_benchmarks import (
    get_default_benchmarks, format_benchmark_for_display,
    get_event_type, BENCHMARK_METHODOLOGY
)
from chart_components import (
    season_progression_chart, gap_analysis_chart, probability_gauge,
    competitor_comparison_chart, form_trend_chart, COLORS
)
from discipline_knowledge import (
    TOKYO_2025_STANDARDS, LA_2028_STANDARDS, EVENT_QUOTAS,
    get_event_standard, get_event_quota, DISCIPLINE_KNOWLEDGE
)

# Import report generator (with fallback if not available)
try:
    from report_generator import (
        AthleteReportGenerator, CompetitionBriefingGenerator,
        generate_html_report, check_dependencies
    )
    REPORT_GEN_AVAILABLE = True
except ImportError:
    REPORT_GEN_AVAILABLE = False

# Upcoming championships with dates (Tokyo 2025 WC has completed)
UPCOMING_CHAMPIONSHIPS = {
    "Asian Games 2026": {
        "date": datetime(2026, 9, 19),
        "type": "Asian Games",
        "venue": "Nagoya, Japan",
        "cid": None  # TBD
    },
    "World Championships 2027": {
        "date": datetime(2027, 8, 14),
        "type": "World Championships",
        "venue": "Beijing, China",
        "cid": None
    },
    "LA 2028 Olympics": {
        "date": datetime(2028, 7, 14),
        "type": "Olympics",
        "venue": "Los Angeles, USA",
        "cid": None
    }
}


def get_ksa_athletes(df: pd.DataFrame) -> pd.DataFrame:
    """Get all KSA athletes from data (optimized - no copy unless necessary)."""
    if 'Athlete_CountryCode' in df.columns:
        return df[df['Athlete_CountryCode'] == 'KSA']
    elif 'nationality' in df.columns:
        return df[df['nationality'] == 'KSA']
    return pd.DataFrame()


def filter_fat_times_only(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter dataframe to only include FAT (Fully Automatic Timing) results.
    Hand times are not valid for predictions as they're ~0.24s slower.
    """
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    # Filter out hand-timed results if the column exists
    if 'Is_Hand_Timed' in df.columns:
        hand_timed_values = [True, 1, '1', 'Y', 'Yes', 'y', 'yes', 'TRUE', 'True', 'true', 'H', 'h']
        mask = mask & (~df['Is_Hand_Timed'].isin(hand_timed_values))

    # Also filter by result format - hand times often end with 'h' suffix
    if 'Result' in df.columns:
        mask = mask & (~df['Result'].astype(str).str.lower().str.endswith('h'))

    return df[mask]


@st.cache_data(ttl=300, show_spinner=False)
def _get_athlete_performances_cached(
    _df_hash: str,
    athlete_id: str,
    event: str,
    limit: int,
    athlete_col: str,
    event_col: str,
    date_col: str,
    result_col: str,
    df_json: str
) -> List[Dict]:
    """Cached version of athlete performance lookup."""
    import json
    df = pd.read_json(df_json)

    athlete_data = df[
        (df[athlete_col].astype(str) == str(athlete_id)) &
        (df[event_col] == event)
    ]

    if athlete_data.empty:
        return []

    athlete_data = athlete_data.copy()
    athlete_data[date_col] = pd.to_datetime(athlete_data[date_col], errors='coerce')
    athlete_data = athlete_data.sort_values(date_col, ascending=False).head(limit)

    performances = []
    for _, row in athlete_data.iterrows():
        result = row.get(result_col) or row.get('Result_numeric')
        if pd.notna(result):
            performances.append({
                'date': str(row[date_col]),
                'result': float(result),
                'competition': str(row.get('Competition', row.get('competitionname', 'Unknown')))
            })

    return performances


def get_athlete_recent_performances(df: pd.DataFrame, athlete_id: str, event: str, limit: int = 10) -> List[Dict]:
    """Get athlete's recent performances in an event (optimized)."""
    athlete_col = 'Athlete_ID' if 'Athlete_ID' in df.columns else 'athleteid'
    event_col = 'Event' if 'Event' in df.columns else 'eventname'
    date_col = 'Start_Date' if 'Start_Date' in df.columns else 'competitiondate'
    result_col = 'Result_numeric' if 'Result_numeric' in df.columns else 'result_numeric'

    # Filter data first to reduce size before any operations
    athlete_data = df[
        (df[athlete_col].astype(str) == str(athlete_id)) &
        (df[event_col] == event)
    ]

    if athlete_data.empty:
        return []

    # Only copy and process the filtered subset
    comp_col = 'Competition' if 'Competition' in df.columns else 'competitionname'
    athlete_data = athlete_data[[date_col, result_col, comp_col]].copy()
    athlete_data[date_col] = pd.to_datetime(athlete_data[date_col], errors='coerce')
    athlete_data = athlete_data.dropna(subset=[result_col]).sort_values(date_col, ascending=False).head(limit)

    performances = []
    for _, row in athlete_data.iterrows():
        performances.append({
            'date': row[date_col],
            'result': float(row[result_col]),
            'competition': str(row.get(comp_col, 'Unknown'))
        })

    return performances


def get_athlete_bests(df: pd.DataFrame, athlete_id: str, event: str) -> Dict:
    """Get athlete's season best, personal best, and averages (optimized)."""
    athlete_col = 'Athlete_ID' if 'Athlete_ID' in df.columns else 'athleteid'
    event_col = 'Event' if 'Event' in df.columns else 'eventname'
    date_col = 'Start_Date' if 'Start_Date' in df.columns else 'competitiondate'
    result_col = 'Result_numeric' if 'Result_numeric' in df.columns else 'result_numeric'

    # Filter once and select only needed columns
    mask = (df[athlete_col].astype(str) == str(athlete_id)) & (df[event_col] == event)
    athlete_data = df.loc[mask, [date_col, result_col]].dropna(subset=[result_col])

    if athlete_data.empty:
        return {'sb': None, 'pb': None, 'avg': None, 'pb_date': None}

    event_type = get_event_type(event)
    results = athlete_data[result_col].tolist()

    # Personal Best (all time)
    pb = min(results) if event_type == 'time' else max(results)

    # Season Best (current year) - convert dates only for the filtered subset
    athlete_data = athlete_data.copy()
    athlete_data[date_col] = pd.to_datetime(athlete_data[date_col], errors='coerce')
    current_year = datetime.now().year
    season_mask = athlete_data[date_col].dt.year == current_year
    season_data = athlete_data.loc[season_mask]

    if not season_data.empty:
        season_results = season_data[result_col].tolist()
        sb = min(season_results) if event_type == 'time' else max(season_results)
    else:
        sb = pb  # Use PB if no season results

    # Average of last 5
    recent_results = athlete_data.nlargest(5, date_col)[result_col].tolist()
    avg = statistics.mean(recent_results) if recent_results else None

    # PB date
    pb_mask = athlete_data[result_col] == pb
    pb_date = athlete_data.loc[pb_mask, date_col].iloc[0] if pb_mask.any() else None

    return {'sb': sb, 'pb': pb, 'avg': avg, 'pb_date': pb_date}


def show_competition_prep_hub(df: pd.DataFrame):
    """
    Competition Prep Hub - Central hub for preparing athletes before championships.

    Features:
    - Competition selector with countdown
    - KSA squad overview grouped by event
    - Quick status cards per athlete
    - Bulk selection for report generation
    """
    st.title("Competition Prep Hub")

    # Competition selector
    col1, col2 = st.columns([2, 1])

    with col1:
        selected_champ = st.selectbox(
            "Select Championship",
            list(UPCOMING_CHAMPIONSHIPS.keys()),
            key="coach_competition_select"
        )

    with col2:
        champ_info = UPCOMING_CHAMPIONSHIPS[selected_champ]
        days_until = (champ_info['date'] - datetime.now()).days

        if days_until > 0:
            st.metric("Days Until", f"{days_until}", delta=None)
        else:
            st.metric("Status", "Completed" if days_until < -30 else "In Progress")

    # Championship info bar
    st.info(f"**{selected_champ}** | {champ_info['venue']} | {champ_info['date'].strftime('%B %d, %Y')}")

    st.markdown("---")

    # Get KSA athletes
    ksa_df = get_ksa_athletes(df)

    if ksa_df.empty:
        st.warning("No KSA athlete data found in the database.")
        return

    # Group by event
    event_col = 'Event' if 'Event' in ksa_df.columns else 'eventname'
    gender_col = 'Gender' if 'Gender' in ksa_df.columns else 'gender'
    name_col = 'Athlete_Name' if 'Athlete_Name' in ksa_df.columns else 'firstname'
    date_col = 'Start_Date' if 'Start_Date' in ksa_df.columns else 'competitiondate'

    # Filter to ACTIVE athletes only (competed in last 3 years)
    ksa_df = ksa_df.copy()  # Avoid SettingWithCopyWarning
    ksa_df[date_col] = pd.to_datetime(ksa_df[date_col], errors='coerce')
    cutoff_date = datetime.now() - timedelta(days=365 * 3)  # Last 3 years
    active_ksa_df = ksa_df[ksa_df[date_col] >= cutoff_date]

    if active_ksa_df.empty:
        st.warning("No active KSA athletes found (competed in last 3 years).")
        return

    # Get unique athletes per event - use observed=True to avoid memory issues with categorical columns
    athlete_events = active_ksa_df.groupby([event_col, gender_col, name_col], observed=True).size().reset_index(name='count')

    # Filter options
    st.subheader("Squad Overview")

    col1, col2 = st.columns(2)
    with col1:
        gender_opts = ['All'] + sorted(athlete_events[gender_col].dropna().unique().tolist())
        selected_gender = st.selectbox("Filter by Gender", gender_opts, key="prep_gender")

    with col2:
        if selected_gender != 'All':
            events_for_gender = athlete_events[athlete_events[gender_col] == selected_gender][event_col].unique()
        else:
            events_for_gender = athlete_events[event_col].unique()
        event_opts = ['All Events'] + sorted(events_for_gender.tolist())
        selected_event = st.selectbox("Filter by Event", event_opts, key="prep_event")

    # Filter data
    filtered = athlete_events.copy()
    if selected_gender != 'All':
        filtered = filtered[filtered[gender_col] == selected_gender]
    if selected_event != 'All Events':
        filtered = filtered[filtered[event_col] == selected_event]

    # Display athletes with status cards
    st.markdown("### Athletes")

    if filtered.empty:
        st.info("No athletes found matching filters.")
        return

    # Get standards for comparison
    standards = TOKYO_2025_STANDARDS if '2025' in selected_champ else LA_2028_STANDARDS

    # Selection for bulk export
    selected_athletes = []

    for event in sorted(filtered[event_col].unique()):
        event_athletes = filtered[filtered[event_col] == event]

        with st.expander(f"**{event}** ({len(event_athletes)} athletes)", expanded=True):
            for _, row in event_athletes.iterrows():
                athlete_name = row[name_col]
                gender = row[gender_col]

                # Get athlete's best performances
                athlete_id_col = 'Athlete_ID' if 'Athlete_ID' in ksa_df.columns else 'athleteid'
                athlete_row = ksa_df[ksa_df[name_col] == athlete_name].iloc[0] if not ksa_df[ksa_df[name_col] == athlete_name].empty else None

                if athlete_row is not None:
                    athlete_id = athlete_row[athlete_id_col]
                    bests = get_athlete_bests(ksa_df, athlete_id, event)

                    # Get entry standard
                    gender_key = 'men' if gender == 'Men' or gender == 'M' else 'women'
                    standard = get_event_standard(event, 'tokyo_2025', gender_key)

                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])

                    with col1:
                        # Ensure label is not empty to avoid Streamlit warning
                        label = athlete_name if athlete_name and str(athlete_name).strip() else "Unknown Athlete"
                        selected = st.checkbox(label, key=f"select_{athlete_name}_{event}")
                        if selected:
                            selected_athletes.append({'name': athlete_name, 'event': event, 'id': athlete_id})

                    with col2:
                        if bests['sb']:
                            event_type = get_event_type(event)
                            sb_formatted = format_benchmark_for_display(bests['sb'], event_type)
                            st.caption(f"SB: {sb_formatted}")
                        else:
                            st.caption("SB: N/A")

                    with col3:
                        if standard and bests['sb']:
                            gap = calculate_gap(bests['sb'], standard, get_event_type(event))
                            if gap <= 0:
                                st.success("Qualified")
                            else:
                                st.warning(f"{format_gap(gap, get_event_type(event))} to qualify")
                        else:
                            st.caption("Standard: N/A")

                    with col4:
                        performances = get_athlete_recent_performances(ksa_df, athlete_id, event, 5)
                        if len(performances) >= 3:
                            results = [p['result'] for p in performances]
                            trend = detect_trend(results, get_event_type(event))
                            st.caption(f"Form: {get_trend_symbol(trend)} {trend.title()}")
                        else:
                            st.caption("Form: N/A")

                    with col5:
                        if st.button("View", key=f"report_{athlete_name}_{event}"):
                            st.session_state['selected_athlete_for_report'] = {
                                'name': athlete_name,
                                'id': athlete_id,
                                'event': event
                            }
                            # Auto-switch to Reports tab
                            st.session_state['coach_view_tab'] = "Athlete Reports"
                            st.rerun()

    # Store selected championship in session state for other tabs
    st.session_state['selected_championship'] = selected_champ
    st.session_state['selected_championship_info'] = champ_info

    # Bulk export section
    if selected_athletes:
        st.markdown("---")
        st.subheader(f"Selected Athletes: {len(selected_athletes)}")

        # Auto-store selections for Report Cards tab
        st.session_state['bulk_report_athletes'] = selected_athletes

        col1, col2 = st.columns(2)
        with col1:
            st.success(f"{len(selected_athletes)} athletes ready for Report Cards")
        with col2:
            st.info("Switch to **Athlete Reports** tab to view detailed briefings")


def show_athlete_report_cards(df: pd.DataFrame):
    """
    Athlete Report Cards - Comprehensive pre-competition briefings.

    Uses championship context from Competition Prep Hub to show:
    - Competition-specific qualification standards
    - Championship benchmarks (medal/final lines)
    - Form projection vs championship requirements
    - Top competitors for that championship
    """
    # Get championship context from Comp Prep tab
    selected_champ = st.session_state.get('selected_championship', 'Asian Games 2026')
    champ_info = st.session_state.get('selected_championship_info', UPCOMING_CHAMPIONSHIPS.get(selected_champ, {}))

    # Header with championship context
    st.title("Athlete Report Cards")

    # Show championship context bar
    if champ_info:
        days_until = (champ_info.get('date', datetime.now()) - datetime.now()).days
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"### {selected_champ}")
            st.caption(f"{champ_info.get('venue', 'TBD')} | {champ_info.get('date', datetime.now()).strftime('%B %Y')}")
        with col2:
            if days_until > 0:
                st.metric("Days Until", days_until)
        with col3:
            # Determine which standards to use based on championship
            if 'Olympic' in selected_champ or 'LA 2028' in selected_champ:
                standards_name = "LA 2028 Standards"
                standards_key = 'la_2028'
            else:
                standards_name = "Tokyo 2025 Standards"
                standards_key = 'tokyo_2025'
            st.caption(f"Using: {standards_name}")

        st.markdown("---")
    else:
        standards_key = 'tokyo_2025'

    # Get KSA athletes
    ksa_df = get_ksa_athletes(df)

    if ksa_df.empty:
        st.warning("No KSA athlete data available.")
        return

    # Athlete selector
    name_col = 'Athlete_Name' if 'Athlete_Name' in ksa_df.columns else 'firstname'
    event_col = 'Event' if 'Event' in ksa_df.columns else 'eventname'
    athlete_id_col = 'Athlete_ID' if 'Athlete_ID' in ksa_df.columns else 'athleteid'

    # Check if there are athletes selected from Competition Prep Hub
    bulk_selected = st.session_state.get('bulk_report_athletes', [])
    preselected = st.session_state.get('selected_athlete_for_report', None)

    # If athletes selected in Prep Hub, only show those
    if bulk_selected:
        st.success(f"Showing {len(bulk_selected)} athlete(s) selected from Competition Prep for **{selected_champ}**")
        col_clear, col_space = st.columns([1, 3])
        with col_clear:
            if st.button("Clear Selection", key="clear_bulk_selection"):
                st.session_state['bulk_report_athletes'] = []
                st.session_state['selected_athlete_for_report'] = None
                st.rerun()

        # Build athlete options from bulk selection
        athlete_event_options = [(a['name'], a['event']) for a in bulk_selected]
        athlete_names = list(set([a['name'] for a in bulk_selected]))
    else:
        athlete_event_options = None
        athlete_names = sorted(ksa_df[name_col].dropna().unique().tolist())
        st.info("💡 **Tip:** Select athletes in **Competition Prep** tab first to see competition-specific analysis")

    col1, col2 = st.columns(2)

    with col1:
        default_idx = athlete_names.index(preselected['name']) if preselected and preselected['name'] in athlete_names else 0
        selected_athlete = st.selectbox("Select Athlete", athlete_names, index=default_idx, key="report_athlete")

    # Get athlete's events
    athlete_data = ksa_df[ksa_df[name_col] == selected_athlete]

    with col2:
        # If bulk selection exists, only show events for this athlete from the selection
        if bulk_selected:
            athlete_events = [a['event'] for a in bulk_selected if a['name'] == selected_athlete]
            if not athlete_events:
                # Fallback to all events if no match
                athlete_events = sorted(athlete_data[event_col].dropna().unique().tolist())
        else:
            athlete_events = sorted(athlete_data[event_col].dropna().unique().tolist())

        default_event_idx = athlete_events.index(preselected['event']) if preselected and preselected.get('event') in athlete_events else 0
        selected_event = st.selectbox("Select Event", athlete_events, index=default_event_idx, key="report_event")

    if not selected_athlete or not selected_event:
        st.info("Please select an athlete and event.")
        return

    # Get athlete ID
    athlete_id = athlete_data[athlete_id_col].iloc[0] if not athlete_data.empty else None
    gender_col = 'Gender' if 'Gender' in athlete_data.columns else 'gender'
    gender = athlete_data[gender_col].iloc[0] if gender_col in athlete_data.columns else 'Men'
    gender_key = 'men' if gender in ['Men', 'M'] else 'women'

    st.markdown("---")

    # Report Header
    st.header(f"{selected_athlete} | {selected_event}")
    st.caption(f"Saudi Arabia | {gender}")

    # Pre-filter data for this athlete to speed up all subsequent lookups
    athlete_col = 'Athlete_ID' if 'Athlete_ID' in df.columns else 'athleteid'
    event_col_df = 'Event' if 'Event' in df.columns else 'eventname'
    athlete_event_df = df[
        (df[athlete_col].astype(str) == str(athlete_id)) &
        (df[event_col_df] == selected_event)
    ]

    # === QUALIFICATION STATUS ===
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Qualification Status")

        bests = get_athlete_bests(athlete_event_df, athlete_id, selected_event)
        event_type = get_event_type(selected_event)

        # Entry standard - use championship-specific standards
        standard = get_event_standard(selected_event, standards_key, gender_key)

        metrics_col1, metrics_col2 = st.columns(2)

        with metrics_col1:
            if standard:
                st.metric("Entry Standard", format_benchmark_for_display(standard, event_type))
            else:
                st.metric("Entry Standard", "TBD")

            if bests['sb']:
                st.metric("Season Best", format_benchmark_for_display(bests['sb'], event_type))
            else:
                st.metric("Season Best", "N/A")

        with metrics_col2:
            if bests['pb']:
                pb_date = bests.get('pb_date')
                pb_str = format_benchmark_for_display(bests['pb'], event_type)
                if pb_date and pd.notna(pb_date):
                    pb_str += f" ({pd.to_datetime(pb_date).strftime('%b %Y')})"
                st.metric("Personal Best", pb_str)
            else:
                st.metric("Personal Best", "N/A")

            # WA Ranking (placeholder - would need ranking data)
            st.metric("WA Ranking", "TBD")

        # Qualification status
        if standard and bests['sb']:
            gap = calculate_gap(bests['sb'], standard, event_type)
            if gap <= 0:
                st.success(f"QUALIFIED - {format_gap(abs(gap), event_type)} under standard")
            else:
                st.warning(f"Gap to Standard: {format_gap(gap, event_type)}")

    with col2:
        st.subheader("Form Projection")

        performances = get_athlete_recent_performances(athlete_event_df, athlete_id, selected_event, 10)

        if len(performances) >= 3:
            results = [p['result'] for p in performances]
            projection = project_performance(results, event_type=event_type, is_major_championship=True)

            metrics_col1, metrics_col2 = st.columns(2)

            with metrics_col1:
                st.metric(
                    "Projected Performance",
                    format_benchmark_for_display(projection['projected'], event_type)
                )
                st.metric(
                    "Trend",
                    f"{projection['trend_symbol']} {projection['trend'].title()}"
                )

            with metrics_col2:
                st.metric(
                    "Confidence Range",
                    f"{format_benchmark_for_display(projection['range_low'], event_type)} - {format_benchmark_for_display(projection['range_high'], event_type)}"
                )
                st.metric("Form Score", f"{projection['form_score']}/100",
                         help="0-100 scale. Higher = better recent form")

            # Form Score Methodology
            with st.expander("How is Form Score calculated?"):
                st.markdown("""
                **Form Score (0-100)** measures how well an athlete is performing relative to their own capability:

                **Formula:** `Form Score = Consistency (40%) + Trend (30%) + Recency (30%)`

                **Components:**
                1. **Consistency (40%)** - How tight are recent results?
                   - Low variance in times/distances = High score
                   - Example: 10.05, 10.08, 10.04 = 95 (very consistent)
                   - Example: 10.05, 10.45, 10.15 = 60 (inconsistent)

                2. **Trend (30%)** - Are performances improving?
                   - Recent results better than older ones = High score
                   - Example: 10.20 → 10.10 → 10.05 = 90 (improving)
                   - Example: 10.05 → 10.15 → 10.25 = 40 (declining)

                3. **Recency (30%)** - How recent is their best?
                   - Best performance in last 30 days = High score
                   - Example: PB 2 weeks ago = 95
                   - Example: PB 6 months ago = 50

                **Example Calculation (100m sprinter):**
                - Last 5 results: 10.05, 10.08, 10.12, 10.06, 10.10
                - Consistency: σ=0.03s → Score 85/100
                - Trend: Slight improvement → Score 70/100
                - Recency: Best 3 weeks ago → Score 80/100
                - **Form Score: 0.4(85) + 0.3(70) + 0.3(80) = 79/100**
                """)
        else:
            st.info("Insufficient data for projection (need 3+ performances)")

    # === LAST 5 RACES ===
    st.markdown("---")
    st.subheader("Recent Competition History")

    # Get last 5 performances with full details
    date_col = 'Start_Date' if 'Start_Date' in athlete_event_df.columns else 'competitiondate'
    result_col = 'Result' if 'Result' in athlete_event_df.columns else 'performance'
    result_num_col = 'Result_numeric' if 'Result_numeric' in athlete_event_df.columns else 'result_numeric'
    comp_col = 'Competition' if 'Competition' in athlete_event_df.columns else 'competitionname'

    recent_df = athlete_event_df.sort_values(date_col, ascending=False).head(5)

    if not recent_df.empty:
        # Build race history table
        race_history = []
        valid_results = []

        for _, row in recent_df.iterrows():
            race_date = pd.to_datetime(row[date_col], errors='coerce')
            result_val = row.get(result_num_col)
            result_display = row.get(result_col, 'N/A')
            competition = row.get(comp_col, 'Unknown')

            if pd.notna(result_val):
                valid_results.append(result_val)

            race_history.append({
                'Date': race_date.strftime('%d %b %Y') if pd.notna(race_date) else 'N/A',
                'Competition': str(competition)[:40] if competition else 'N/A',
                'Result': format_benchmark_for_display(result_val, event_type) if pd.notna(result_val) else str(result_display),
                'result_num': result_val
            })

        # Calculate average
        if valid_results:
            avg_result = sum(valid_results) / len(valid_results)
            avg_display = format_benchmark_for_display(avg_result, event_type)
        else:
            avg_result = None
            avg_display = 'N/A'

        # Display metrics
        col_avg1, col_avg2, col_avg3 = st.columns(3)
        with col_avg1:
            st.metric("Last 5 Races Average", avg_display)
        with col_avg2:
            if valid_results:
                if event_type == 'time':
                    best_recent = min(valid_results)
                else:
                    best_recent = max(valid_results)
                st.metric("Best in Last 5", format_benchmark_for_display(best_recent, event_type))
        with col_avg3:
            st.metric("Races Analyzed", len(valid_results))

        # Display race history table
        st.markdown("**Race History**")
        race_df = pd.DataFrame(race_history)[['Date', 'Competition', 'Result']]
        st.dataframe(race_df, hide_index=True, use_container_width=True)

        # Championship projection comparison
        if champ_info and avg_result:
            st.markdown("**Championship Outlook**")
            champ_name = st.session_state.get('selected_championship', 'Championship')
            col_proj1, col_proj2 = st.columns(2)

            with col_proj1:
                st.caption(f"If performing at average ({avg_display}):")
                # Compare to benchmarks
                benchmarks = get_default_benchmarks(selected_event, gender)
                if benchmarks:
                    for round_name, label in [('final', 'Final'), ('semi', 'Semi'), ('heat', 'Heat')]:
                        if round_name in benchmarks and benchmarks[round_name].get('average'):
                            bench_val = benchmarks[round_name]['average']
                            gap = calculate_gap(avg_result, bench_val, event_type)
                            if gap <= 0:
                                st.success(f"✓ {label}: {format_gap(abs(gap), event_type)} inside")
                            else:
                                st.warning(f"✗ {label}: {format_gap(gap, event_type)} outside")

            with col_proj2:
                if bests['pb']:
                    st.caption(f"If performing at PB ({format_benchmark_for_display(bests['pb'], event_type)}):")
                    if benchmarks:
                        for round_name, label in [('final', 'Final'), ('semi', 'Semi'), ('heat', 'Heat')]:
                            if round_name in benchmarks and benchmarks[round_name].get('average'):
                                bench_val = benchmarks[round_name]['average']
                                gap = calculate_gap(bests['pb'], bench_val, event_type)
                                if gap <= 0:
                                    st.success(f"✓ {label}: {format_gap(abs(gap), event_type)} inside")
                                else:
                                    st.warning(f"✗ {label}: {format_gap(gap, event_type)} outside")
    else:
        st.info("No recent competition data available.")

    st.markdown("---")

    # === CHAMPIONSHIP BENCHMARKS ===
    st.subheader("Championship Benchmarks")
    st.caption("What it takes to advance at major championships (based on historical data)")

    benchmarks = get_default_benchmarks(selected_event, gender)

    if benchmarks:
        bench_cols = st.columns(4)

        for i, (round_name, label) in enumerate([
            ('medal', 'Medal Zone'),
            ('final', 'Final'),
            ('semi', 'Semi-Final'),
            ('heat', 'Heat Survival')
        ]):
            with bench_cols[i]:
                if round_name in benchmarks and benchmarks[round_name].get('average'):
                    value = benchmarks[round_name]['average']
                    st.metric(label, format_benchmark_for_display(value, event_type))

                    # Gap from athlete
                    if bests['sb']:
                        gap = calculate_gap(bests['sb'], value, event_type)
                        if gap <= 0:
                            st.caption(f"{format_gap(abs(gap), event_type)} ahead")
                        else:
                            st.caption(f"{format_gap(gap, event_type)} behind")
                else:
                    st.metric(label, "N/A")

    st.markdown("---")

    # === SEASON PROGRESSION CHART ===
    st.subheader("Season Progression")

    if performances:
        # Prepare benchmark lines for chart
        chart_benchmarks = {}
        if benchmarks:
            for key in ['medal', 'final', 'semi', 'heat']:
                if key in benchmarks and benchmarks[key].get('average'):
                    chart_benchmarks[key] = benchmarks[key]['average']

        chart = season_progression_chart(
            performances=performances,
            benchmarks=chart_benchmarks,
            event_type=event_type,
            title=f"Season Progression - {selected_athlete}",
            width=700,
            height=350
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No performance data available for chart.")

    st.markdown("---")

    # === PROBABILITY GAUGE ===
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Advancement Probability")

        if performances and len(performances) >= 3 and benchmarks:
            results = [p['result'] for p in performances]
            projection = project_performance(results, event_type=event_type)

            historical_cutoffs = {}
            for key in ['heat', 'semi', 'final', 'medal']:
                if key in benchmarks and benchmarks[key].get('average'):
                    historical_cutoffs[key] = benchmarks[key]['average']

            if historical_cutoffs:
                probabilities = calculate_advancement_probability(
                    projection['projected'],
                    historical_cutoffs,
                    event_type
                )

                prob_chart = probability_gauge(probabilities)
                st.altair_chart(prob_chart, use_container_width=True)
        else:
            st.info("Insufficient data for probability calculation")

    with col2:
        st.subheader("Gap Analysis")

        if bests['sb'] and benchmarks:
            chart_benchmarks = {}
            for key in ['medal', 'final', 'semi', 'heat']:
                if key in benchmarks and benchmarks[key].get('average'):
                    chart_benchmarks[key] = benchmarks[key]['average']

            if chart_benchmarks:
                gap_chart = gap_analysis_chart(
                    athlete_performance=bests['sb'],
                    benchmarks=chart_benchmarks,
                    event_type=event_type
                )
                st.altair_chart(gap_chart, use_container_width=True)
        else:
            st.info("Insufficient data for gap analysis")

    # === METHODOLOGY NOTES ===
    with st.expander("Methodology Notes"):
        st.markdown(METHODOLOGY_NOTES)
        st.markdown(BENCHMARK_METHODOLOGY)


# Asian region country codes for filtering Asian Games competitors
ASIAN_COUNTRY_CODES = {
    'KSA', 'JPN', 'CHN', 'KOR', 'IND', 'QAT', 'BRN', 'UAE', 'KUW', 'OMA',
    'IRN', 'IRQ', 'SYR', 'JOR', 'LBN', 'PAL', 'YEM', 'THA', 'VIE', 'MAS',
    'SGP', 'INA', 'PHI', 'MYA', 'CAM', 'LAO', 'BRU', 'TLS', 'TPE', 'HKG',
    'MAC', 'MGL', 'PRK', 'PAK', 'AFG', 'BAN', 'NEP', 'SRI', 'MDV', 'BHU',
    'UZB', 'KAZ', 'KGZ', 'TJK', 'TKM', 'AUS', 'NZL'  # Oceania often compete in Asian events
}


def show_competitor_watch(df: pd.DataFrame):
    """
    Competitor Watch - Monitor rivals and competitive landscape by competition.

    Features:
    - Competition-based competitor lists (filtered by region for Asian Games)
    - Gap analysis vs KSA athletes
    - Form trends and PB dates
    - Vulnerable competitor identification
    """
    st.title("Competitor Watch")

    # Column mappings
    event_col = 'Event' if 'Event' in df.columns else 'eventname'
    gender_col = 'Gender' if 'Gender' in df.columns else 'gender'
    comp_id_col = 'Competition_ID' if 'Competition_ID' in df.columns else 'competitionid'
    comp_name_col = 'Competition' if 'Competition' in df.columns else 'competitionname'
    name_col = 'Athlete_Name' if 'Athlete_Name' in df.columns else 'firstname'
    result_col = 'Result_numeric' if 'Result_numeric' in df.columns else 'result_numeric'
    date_col = 'Start_Date' if 'Start_Date' in df.columns else 'competitiondate'
    country_col = 'Athlete_CountryCode' if 'Athlete_CountryCode' in df.columns else 'nationality'
    athlete_id_col = 'Athlete_ID' if 'Athlete_ID' in df.columns else 'athleteid'

    # Get championship context from Comp Prep tab (if set)
    default_champ = st.session_state.get('selected_championship', 'Asian Games 2026')

    # Competition selector
    st.subheader("Select Competition")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Target championship dropdown - default to Comp Prep selection
        championship_options = list(UPCOMING_CHAMPIONSHIPS.keys())
        default_idx = championship_options.index(default_champ) if default_champ in championship_options else 0
        selected_championship = st.selectbox(
            "Target Championship",
            championship_options,
            index=default_idx,
            key="watch_championship"
        )

    with col2:
        gender_opts = sorted(df[gender_col].dropna().unique().tolist())
        selected_gender = st.selectbox("Gender", gender_opts, key="watch_gender")

    with col3:
        gender_filtered = df[df[gender_col] == selected_gender]
        event_opts = sorted(gender_filtered[event_col].dropna().unique().tolist())
        selected_event = st.selectbox("Event", event_opts, key="watch_event")

    if not selected_event:
        st.info("Please select an event.")
        return

    # Championship info
    champ_info = UPCOMING_CHAMPIONSHIPS.get(selected_championship, {})
    champ_date = champ_info.get('date')
    champ_type = champ_info.get('type', 'Championship')

    if champ_date:
        days_to_go = (champ_date - datetime.now()).days
        st.info(f"**{selected_championship}** | {champ_info.get('venue', 'TBD')} | {days_to_go} days to go")

    st.markdown("---")

    # Get ALL KSA athletes for comparison
    ksa_df = get_ksa_athletes(df)
    ksa_in_event = ksa_df[(ksa_df[event_col] == selected_event) & (ksa_df[gender_col] == selected_gender)]

    # Get unique KSA athletes in this event
    ksa_athletes_unique = ksa_in_event.drop_duplicates(subset=[athlete_id_col])

    ksa_bests = {'sb': None, 'pb': None}
    ksa_athlete = None
    ksa_id = None

    if not ksa_athletes_unique.empty:
        event_type = get_event_type(selected_event)

        # If multiple KSA athletes, let user select which one to compare
        ksa_athlete_names = ksa_athletes_unique[name_col].unique().tolist()

        st.subheader(f"🇸🇦 KSA Athletes in {selected_event} ({len(ksa_athlete_names)} athletes)")

        # Check if there's a preselected athlete from Comp Prep
        preselected_report = st.session_state.get('selected_athlete_for_report', None)
        bulk_selected = st.session_state.get('bulk_report_athletes', [])

        # Find default athlete from selections
        default_ksa_idx = 0
        if preselected_report and preselected_report.get('name') in ksa_athlete_names:
            default_ksa_idx = ksa_athlete_names.index(preselected_report['name'])
        elif bulk_selected:
            # Use first bulk selected athlete that matches this event
            for a in bulk_selected:
                if a['name'] in ksa_athlete_names and a.get('event') == selected_event:
                    default_ksa_idx = ksa_athlete_names.index(a['name'])
                    break

        if len(ksa_athlete_names) > 1:
            selected_ksa = st.selectbox("Select KSA Athlete for Comparison", ksa_athlete_names, index=default_ksa_idx, key="ksa_compare_athlete")
            ksa_athlete = selected_ksa
            ksa_row = ksa_athletes_unique[ksa_athletes_unique[name_col] == selected_ksa].iloc[0]
            ksa_id = ksa_row[athlete_id_col]
        else:
            ksa_athlete = ksa_athlete_names[0]
            ksa_id = ksa_athletes_unique[athlete_id_col].iloc[0]

        ksa_event_data = df[(df[athlete_id_col].astype(str) == str(ksa_id)) & (df[event_col] == selected_event)]
        ksa_bests = get_athlete_bests(ksa_event_data, ksa_id, selected_event)

        # Show all KSA athletes summary
        ksa_summary_data = []
        for _, ksa_row in ksa_athletes_unique.iterrows():
            kid = ksa_row[athlete_id_col]
            kname = ksa_row[name_col]
            k_event_data = df[(df[athlete_id_col].astype(str) == str(kid)) & (df[event_col] == selected_event)]
            k_bests = get_athlete_bests(k_event_data, kid, selected_event)
            ksa_summary_data.append({
                'Athlete': kname,
                'SB': format_benchmark_for_display(k_bests['sb'], event_type) if k_bests['sb'] else 'N/A',
                'PB': format_benchmark_for_display(k_bests['pb'], event_type) if k_bests['pb'] else 'N/A',
                'Selected': '✓' if kname == ksa_athlete else ''
            })

        st.dataframe(pd.DataFrame(ksa_summary_data), hide_index=True, use_container_width=True)

        # Highlight selected athlete metrics
        col_ksa1, col_ksa2, col_ksa3 = st.columns(3)
        with col_ksa1:
            st.metric("Comparing", ksa_athlete)
        with col_ksa2:
            if ksa_bests['sb']:
                st.metric("Season Best", format_benchmark_for_display(ksa_bests['sb'], event_type))
        with col_ksa3:
            if ksa_bests['pb']:
                st.metric("Personal Best", format_benchmark_for_display(ksa_bests['pb'], event_type))
    else:
        st.warning("No KSA athlete in this event for comparison.")

    st.markdown("---")

    # Get competitors based on recent major competitions
    st.subheader(f"Top Competitors - {selected_event} ({selected_gender})")
    st.caption(f"Athletes likely to compete at {selected_championship}")

    # Filter to event and gender
    event_data = df[(df[event_col] == selected_event) & (df[gender_col] == selected_gender)].copy()

    # For Asian Games/Asian Championships, filter to Asian countries only
    is_asian_event = 'Asian' in selected_championship
    if is_asian_event:
        event_data = event_data[event_data[country_col].isin(ASIAN_COUNTRY_CODES)]
        st.caption(f"Showing Asian athletes only (eligible for {selected_championship})")

    # Remove hand times - only use FAT (Fully Automatic Timing)
    event_data = filter_fat_times_only(event_data)

    event_data[date_col] = pd.to_datetime(event_data[date_col], errors='coerce')

    # Get last 2 years of data for competitor analysis
    cutoff_date = datetime.now() - timedelta(days=730)
    recent_data = event_data[event_data[date_col] >= cutoff_date]

    if recent_data.empty:
        st.info("No recent competitor data available (FAT times only).")
        return

    event_type = get_event_type(selected_event)

    # Pre-compute ALL athlete bests once for fast search (used by Build Custom Race List)
    event_data_clean = event_data.dropna(subset=[result_col, athlete_id_col])
    if event_type == 'time':
        all_athlete_bests = event_data_clean.groupby(athlete_id_col, observed=True).agg({
            result_col: 'min',
            name_col: 'first',
            country_col: 'first'
        }).reset_index()
    else:
        all_athlete_bests = event_data_clean.groupby(athlete_id_col, observed=True).agg({
            result_col: 'max',
            name_col: 'first',
            country_col: 'first'
        }).reset_index()

    # Get season bests per athlete
    recent_data = recent_data.dropna(subset=[result_col, athlete_id_col])

    if event_type == 'time':
        athlete_bests = recent_data.groupby(athlete_id_col, observed=True).agg({
            result_col: 'min',
            name_col: 'first',
            country_col: 'first'
        }).reset_index()
        athlete_bests = athlete_bests.sort_values(result_col, ascending=True)
    else:
        athlete_bests = recent_data.groupby(athlete_id_col, observed=True).agg({
            result_col: 'max',
            name_col: 'first',
            country_col: 'first'
        }).reset_index()
        athlete_bests = athlete_bests.sort_values(result_col, ascending=False)

    # Build competitor data
    competitors_data = []

    for i, row in athlete_bests.head(30).iterrows():
        athlete_id = row[athlete_id_col]
        athlete_name = row[name_col]
        country = row[country_col]
        sb = row[result_col]

        # Get PB from all-time data
        all_time_data = event_data[event_data[athlete_id_col] == athlete_id]
        if event_type == 'time':
            pb = all_time_data[result_col].min()
        else:
            pb = all_time_data[result_col].max()

        pb_row = all_time_data[all_time_data[result_col] == pb]
        pb_date = pb_row[date_col].iloc[0] if not pb_row.empty else None

        # Get recent form (last 3 competitions)
        recent = all_time_data.sort_values(date_col, ascending=False).head(3)
        recent_form = recent[result_col].tolist()

        # Get last 3 competition names
        comp_col = 'Competition' if 'Competition' in all_time_data.columns else 'competitionname'
        last_3_comps = recent[comp_col].tolist() if comp_col in recent.columns else []
        last_3_comps_str = ", ".join([str(c)[:20] for c in last_3_comps[:3]]) if last_3_comps else "N/A"

        # Calculate average performance
        avg_perf = statistics.mean(recent_form) if recent_form else None

        # Calculate gap from KSA athlete
        gap = None
        gap_formatted = "N/A"
        if ksa_bests['sb'] and pd.notna(sb):
            gap = calculate_gap(ksa_bests['sb'], sb, event_type)
            gap_formatted = format_gap(gap, event_type) if gap else "N/A"

        # Detect trend
        trend = detect_trend(recent_form, event_type) if len(recent_form) >= 3 else 'stable'

        competitors_data.append({
            'Rank': len(competitors_data) + 1,
            'Athlete': athlete_name,
            'Country': country,
            'SB': format_benchmark_for_display(sb, event_type) if pd.notna(sb) else 'N/A',
            'SB_raw': sb,
            'PB': format_benchmark_for_display(pb, event_type) if pd.notna(pb) else 'N/A',
            'PB Date': pb_date.strftime('%b %Y') if pd.notna(pb_date) else 'N/A',
            'Avg': format_benchmark_for_display(avg_perf, event_type) if avg_perf else 'N/A',
            'Last 3 Comps': last_3_comps_str,
            'Gap': gap_formatted,
            'Gap_raw': gap,
            'Trend': f"{get_trend_symbol(trend)} {trend.title()}",
            'Is_KSA': country == 'KSA',
            'Athlete_ID': athlete_id
        })

    if competitors_data:
        comp_df = pd.DataFrame(competitors_data)

        # Style the dataframe - highlight KSA athletes
        def highlight_ksa(row):
            if 'Is_KSA' in row.index and row['Is_KSA']:
                return ['background-color: #1a4d1a'] * len(row)
            elif row['Country'] == 'KSA':
                return ['background-color: #1a4d1a'] * len(row)
            return [''] * len(row)

        display_cols = ['Rank', 'Athlete', 'Country', 'SB', 'Avg', 'PB', 'PB Date', 'Last 3 Comps', 'Gap', 'Trend']
        # Include Is_KSA for styling if it exists
        style_cols = display_cols + (['Is_KSA'] if 'Is_KSA' in comp_df.columns else [])
        styled_df = comp_df[style_cols].style.apply(highlight_ksa, axis=1)
        # Hide the Is_KSA column after styling
        if 'Is_KSA' in style_cols:
            styled_df = styled_df.hide(subset=['Is_KSA'], axis='columns')
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=500
        )

        # Summary insights
        st.markdown("---")
        st.subheader("Insights")

        col1, col2, col3 = st.columns(3)

        with col1:
            peaking = [c for c in competitors_data if 'Improving' in c['Trend']]
            st.metric("Athletes Peaking", len(peaking))

        with col2:
            old_pb = [c for c in competitors_data if c['PB Date'] != 'N/A' and '202' not in c['PB Date']]
            st.metric("PB > 2 years old", len(old_pb))

        with col3:
            if ksa_bests['sb']:
                ahead = [c for c in competitors_data if c['Gap_raw'] and c['Gap_raw'] < 0]
                st.metric("Athletes Ahead", len(ahead))

    # === MANUAL COMPETITOR SELECTION TAB ===
    st.markdown("---")
    st.subheader("Build Custom Race List")
    st.caption(f"Build race simulation for {selected_event} ({selected_gender})")

    # Country filter for quick add
    all_countries = sorted(all_athlete_bests[country_col].dropna().unique().tolist())

    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        country_filter = st.multiselect(
            "Filter by Country",
            options=all_countries,
            default=[],
            key="race_list_country_filter",
            placeholder="All countries"
        )
    with col_filter2:
        top_n = st.slider("Top N Athletes", min_value=10, max_value=100, value=50, key="race_list_top_n")

    # Pre-build list of top competitors for quick selection
    if country_filter:
        filtered_bests = all_athlete_bests[all_athlete_bests[country_col].isin(country_filter)]
    else:
        filtered_bests = all_athlete_bests

    top_competitors_for_select = []
    if event_type == 'time':
        top_sorted = filtered_bests.nsmallest(top_n, result_col)
    else:
        top_sorted = filtered_bests.nlargest(top_n, result_col)

    for _, row in top_sorted.iterrows():
        top_competitors_for_select.append({
            'id': row[athlete_id_col],
            'name': row[name_col],
            'country': row[country_col],
            'best': row[result_col],
            'display': f"{row[name_col]} ({row[country_col]}) - {format_benchmark_for_display(row[result_col], event_type)}"
        })

    # Two methods: Quick select from top competitors OR search
    col_method1, col_method2 = st.columns(2)

    with col_method1:
        st.markdown(f"**Quick Add - Top {top_n} Athletes**")
        if country_filter:
            st.caption(f"Filtered to: {', '.join(country_filter)}")
        quick_select = st.multiselect(
            "Select from top performers",
            options=[a['display'] for a in top_competitors_for_select],
            key="quick_competitor_select",
            label_visibility="collapsed"
        )

        if quick_select:
            if st.button("Add Selected", key="add_quick_select"):
                if 'custom_race_list' not in st.session_state:
                    st.session_state['custom_race_list'] = []
                added = 0
                for sel in quick_select:
                    for a in top_competitors_for_select:
                        if a['display'] == sel:
                            # Check not already in list
                            existing_ids = [x['id'] for x in st.session_state['custom_race_list']]
                            if a['id'] not in existing_ids:
                                st.session_state['custom_race_list'].append(a)
                                added += 1
                if added:
                    st.success(f"Added {added} athlete(s)")
                    st.rerun()

    with col_method2:
        st.markdown("**Search All Athletes**")
        search_term = st.text_input("Type name to search", key="competitor_search", placeholder="e.g. Bolt", label_visibility="collapsed")

        if search_term and len(search_term) >= 2:
            # Search in pre-computed all_athlete_bests
            search_results = all_athlete_bests[
                all_athlete_bests[name_col].str.contains(search_term, case=False, na=False)
            ].head(20)

            if not search_results.empty:
                search_athletes = [
                    {
                        'id': row[athlete_id_col],
                        'name': row[name_col],
                        'country': row[country_col],
                        'best': row[result_col],
                        'display': f"{row[name_col]} ({row[country_col]}) - {format_benchmark_for_display(row[result_col], event_type)}"
                    }
                    for _, row in search_results.iterrows()
                ]

                selected_search = st.multiselect(
                    "Search results",
                    options=[a['display'] for a in search_athletes],
                    key="manual_competitor_select",
                    label_visibility="collapsed"
                )

                if selected_search and st.button("Add from Search", key="add_search_select"):
                    if 'custom_race_list' not in st.session_state:
                        st.session_state['custom_race_list'] = []
                    added = 0
                    for sel in selected_search:
                        for a in search_athletes:
                            if a['display'] == sel:
                                existing_ids = [x['id'] for x in st.session_state['custom_race_list']]
                                if a['id'] not in existing_ids:
                                    st.session_state['custom_race_list'].append(a)
                                    added += 1
                    if added:
                        st.success(f"Added {added} athlete(s)")
                        st.rerun()
            else:
                st.info("No athletes found.")

    # Display current race list
    if 'custom_race_list' in st.session_state and st.session_state['custom_race_list']:
        st.markdown("#### Your Custom Race List")

        race_list_data = []
        for i, athlete in enumerate(st.session_state['custom_race_list']):
            # Calculate gap from KSA
            gap_val = None
            if ksa_bests['sb'] and athlete['best']:
                gap_val = calculate_gap(ksa_bests['sb'], athlete['best'], event_type)

            race_list_data.append({
                'Lane': i + 1,
                'Athlete': athlete['name'],
                'Country': athlete['country'],
                'Best': format_benchmark_for_display(athlete['best'], event_type) if athlete['best'] else 'N/A',
                'Gap to KSA': format_gap(gap_val, event_type) if gap_val else 'N/A'
            })

        race_df = pd.DataFrame(race_list_data)
        st.dataframe(race_df, hide_index=True, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Race List", key="clear_race_list"):
                st.session_state['custom_race_list'] = []
                st.rerun()
        with col2:
            st.download_button(
                "Export Race List",
                data=race_df.to_csv(index=False),
                file_name=f"race_list_{selected_event}_{selected_gender}.csv",
                mime="text/csv",
                key="export_race_list"
            )


def show_export_center(df: pd.DataFrame):
    """
    Export Center - Generate PDF/HTML reports for coaches.

    Features:
    - Individual athlete exports
    - Bulk squad exports
    - Report format selection
    - Print-ready formatting
    """
    st.title("Export Center")

    # Check dependencies
    if REPORT_GEN_AVAILABLE:
        pdf_available, pdf_msg = check_dependencies()
    else:
        pdf_available = False
        pdf_msg = "Report generator module not loaded"

    # Show what will be exportable
    st.subheader("Report Contents")
    st.markdown("""
    Each athlete report includes:

    1. **Header** - Athlete name, event, championship
    2. **Qualification Status** - Entry standard, season best, personal best, WA ranking
    3. **Form Projection** - Projected performance range with confidence interval
    4. **Championship Benchmarks** - What it takes to medal, make finals, advance
    5. **Top Competitors Table** - Rivals with gaps, PB dates, form trends
    6. **Advancement Probability** - Chances of making each round
    7. **Methodology Notes** - How projections are calculated
    """)

    st.markdown("---")

    # Individual Export Section
    st.subheader("Export Individual Report")

    # Get KSA athletes for export
    ksa_data = get_ksa_athletes(df)

    if not ksa_data.empty:
        # Build athlete options
        name_col = 'Athlete_Name' if 'Athlete_Name' in ksa_data.columns else 'firstname'
        event_col = 'Event' if 'Event' in ksa_data.columns else 'eventname'

        athletes_export = ksa_data.groupby([name_col, event_col], observed=True).size().reset_index()
        athlete_options = [f"{row[name_col]} - {row[event_col]}" for _, row in athletes_export.iterrows()]

        selected_export = st.selectbox("Select Athlete", athlete_options, key="export_athlete_select")

        if selected_export:
            athlete_name, event_name = selected_export.rsplit(" - ", 1)

            col1, col2 = st.columns(2)

            with col1:
                export_format = st.radio("Export Format", ["HTML", "PDF"], horizontal=True, key="export_format")

            with col2:
                include_competitors = st.checkbox("Include Competitors", value=True, key="export_include_comp")

            if st.button("Generate Report", type="primary", key="generate_report_btn"):
                with st.spinner("Generating report..."):
                    try:
                        # Get athlete data
                        athlete_id_col = 'Athlete_ID' if 'Athlete_ID' in ksa_data.columns else 'athleteid'
                        athlete_row = ksa_data[ksa_data[name_col] == athlete_name].iloc[0]
                        athlete_id = str(athlete_row.get(athlete_id_col, ''))

                        # Get performances
                        perfs = get_athlete_recent_performances(df, athlete_id, event_name, limit=10)
                        perf_values = [p['result'] for p in perfs if p.get('result')]

                        # Get projection
                        event_type = get_event_type(event_name)
                        projection = project_performance(perf_values, event_type=event_type) if perf_values else {}

                        # Get benchmarks
                        gender = 'Men' if ksa_data[ksa_data[name_col] == athlete_name]['Gender'].iloc[0] in ['M', 'Men'] else 'Women'
                        benchmarks = get_default_benchmarks(event_name, gender)

                        # Format benchmarks for report
                        formatted_benchmarks = {}
                        for level in ['medal', 'final', 'semi', 'heat']:
                            if level in benchmarks:
                                formatted_benchmarks[level] = {
                                    'value': benchmarks[level].get('value', '-'),
                                    'source': f"{benchmarks[level].get('source', 'Historical')} (median last 3)"
                                }

                        # Get probabilities
                        if projection and 'projected' in projection:
                            proj_val = projection['projected']
                            historical_cutoffs = {k: v.get('value') for k, v in benchmarks.items() if v.get('value')}
                            probabilities = calculate_advancement_probability(proj_val, historical_cutoffs, event_type)
                        else:
                            probabilities = {'medal': 0, 'final': 0, 'semi': 0, 'heat': 0}

                        # Build athlete data dict for report
                        sb_col = 'Result_numeric' if 'Result_numeric' in ksa_data.columns else 'result_numeric'
                        athlete_events = ksa_data[(ksa_data[name_col] == athlete_name) & (ksa_data[event_col] == event_name)]
                        season_best = athlete_events[sb_col].min() if event_type == 'time' else athlete_events[sb_col].max()
                        personal_best = athlete_events[sb_col].min() if event_type == 'time' else athlete_events[sb_col].max()

                        athlete_data = {
                            'name': athlete_name,
                            'event': event_name,
                            'country': 'KSA',
                            'season_best': round(season_best, 2) if pd.notna(season_best) else '-',
                            'personal_best': round(personal_best, 2) if pd.notna(personal_best) else '-',
                            'projected': round(projection.get('projected', 0), 2) if projection else '-',
                            'confidence_low': round(projection.get('confidence_low', 0), 2) if projection else '-',
                            'confidence_high': round(projection.get('confidence_high', 0), 2) if projection else '-',
                            'trend': projection.get('trend', 'stable') if projection else 'stable',
                            'event_type': event_type
                        }

                        # Get competitors if requested
                        competitors = []
                        if include_competitors:
                            comp_results = compare_to_competitors(
                                season_best if pd.notna(season_best) else 0,
                                df, event_name, gender, event_type, limit=10
                            )
                            competitors = comp_results.get('top_competitors', [])

                        # Generate report
                        if export_format == "HTML":
                            html_content = generate_html_report(
                                athlete_data, perfs, formatted_benchmarks, probabilities, competitors
                            )
                            st.download_button(
                                label="Download HTML Report",
                                data=html_content,
                                file_name=f"{athlete_name.replace(' ', '_')}_{event_name}_report.html",
                                mime="text/html"
                            )
                            st.success("HTML report generated!")

                            # Preview
                            with st.expander("Preview Report"):
                                st.components.v1.html(html_content, height=600, scrolling=True)

                        elif export_format == "PDF":
                            if pdf_available:
                                generator = AthleteReportGenerator()
                                pdf_bytes = generator.generate_athlete_report(
                                    athlete_data, perfs, formatted_benchmarks, probabilities, competitors
                                )
                                st.download_button(
                                    label="Download PDF Report",
                                    data=pdf_bytes,
                                    file_name=f"{athlete_name.replace(' ', '_')}_{event_name}_report.pdf",
                                    mime="application/pdf"
                                )
                                st.success("PDF report generated!")
                            else:
                                st.error(f"PDF generation requires reportlab. {pdf_msg}")
                                st.info("HTML export is available as an alternative.")

                    except Exception as e:
                        st.error(f"Error generating report: {str(e)}")
    else:
        st.warning("No KSA athlete data available for export.")

    st.markdown("---")

    # Bulk Export Queue
    st.subheader("Bulk Export Queue")

    bulk_athletes = st.session_state.get('bulk_report_athletes', [])

    if bulk_athletes:
        st.success(f"{len(bulk_athletes)} athletes selected for bulk export")
        for athlete in bulk_athletes:
            st.caption(f"- {athlete['name']} ({athlete['event']})")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate All Reports (HTML)", key="bulk_html"):
                with st.spinner(f"Generating {len(bulk_athletes)} reports..."):
                    # Generate each report
                    all_reports = []
                    for ath in bulk_athletes:
                        try:
                            # Simplified data for bulk export
                            ath_data = {
                                'name': ath['name'],
                                'event': ath['event'],
                                'country': 'KSA',
                                'season_best': ath.get('sb', '-'),
                                'personal_best': ath.get('pb', '-'),
                                'projected': ath.get('projected', '-'),
                                'trend': ath.get('trend', 'stable')
                            }
                            html = generate_html_report(ath_data, [], {}, {})
                            all_reports.append({
                                'name': ath['name'],
                                'event': ath['event'],
                                'content': html
                            })
                        except Exception as e:
                            st.warning(f"Failed to generate report for {ath['name']}: {e}")

                    if all_reports:
                        # Combine into ZIP (simplified - just show first)
                        st.success(f"Generated {len(all_reports)} reports")
                        for report in all_reports[:3]:  # Show first 3
                            st.download_button(
                                label=f"Download {report['name']}",
                                data=report['content'],
                                file_name=f"{report['name'].replace(' ', '_')}_{report['event']}_report.html",
                                mime="text/html",
                                key=f"bulk_dl_{report['name']}_{report['event']}"
                            )

        with col2:
            if st.button("Clear Queue", key="clear_queue"):
                st.session_state['bulk_report_athletes'] = []
                st.rerun()
    else:
        st.caption("No athletes selected. Use Competition Prep Hub to select athletes for bulk export.")

    # Methodology section
    st.markdown("---")
    with st.expander("Report Methodology"):
        st.markdown("""
        **Projection Formula:**
        - Weighted average of last 5 performances
        - Weights: 1.0, 0.85, 0.72, 0.61, 0.52 (exponential decay)
        - Championship adjustment: +0.5% for time events

        **Confidence Interval:**
        - ±1 standard deviation = 68% confidence range

        **Benchmarks:**
        - Median performance from last 3 championship editions
        - Sources: Olympics, World Championships, Asian Games
        """)


def render_coach_view(df: pd.DataFrame):
    """
    Main entry point for Coach View.
    Renders all Coach View tabs.
    """
    # Saudi Arabia header
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <div>
            <h1 style="color: #006C35; margin: 0;">Saudi Athletics</h1>
            <p style="color: #888; margin: 0;">Coach Dashboard - Performance Analysis</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Coach View navigation - using selectbox for programmatic control
    tab_names = [
        "Competition Prep",
        "Athlete Reports",
        "Competitor Watch",
        "Export Center"
    ]

    # Check if we should auto-switch tabs (e.g., from "View" button in Competition Prep)
    default_tab = st.session_state.get('coach_view_tab', "Competition Prep")
    if default_tab not in tab_names:
        default_tab = "Competition Prep"

    # Navigation selectbox in sidebar or main area
    selected_tab = st.selectbox(
        "Navigate to",
        tab_names,
        index=tab_names.index(default_tab),
        key="coach_nav_select"
    )

    # Update session state
    st.session_state['coach_view_tab'] = selected_tab

    st.markdown("---")

    # Render selected tab content
    if selected_tab == "Competition Prep":
        show_competition_prep_hub(df)
    elif selected_tab == "Athlete Reports":
        show_athlete_report_cards(df)
    elif selected_tab == "Competitor Watch":
        show_competitor_watch(df)
    elif selected_tab == "Export Center":
        show_export_center(df)
