import os
import re
import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import numpy as np
import base64
import datetime
import math
import matplotlib  # Required for pandas Styler background_gradient
from country_codes import COUNTRY_CODES
# Azure SQL / SQLite database connection module
from azure_db import query_data, get_connection_mode
from discipline_knowledge import (
    DISCIPLINE_KNOWLEDGE, TOKYO_2025_STANDARDS, LA_2028_STANDARDS,
    EVENT_QUOTAS as DISCIPLINE_QUOTAS, get_event_standard, get_event_quota, get_event_knowledge
)
# Coach View module for simplified coaching interface
from coach_view import render_coach_view
# Performance caching utilities
from performance_cache import optimize_dataframe, get_cache_stats, timed
# Projection engine for form projections and advancement probability
from projection_engine import (
    project_performance, calculate_advancement_probability,
    detect_trend, calculate_form_score, calculate_gap, format_gap,
    METHODOLOGY_NOTES
)
# Chart components for consistent visualizations
from chart_components import (
    COLORS, season_progression_chart, gap_analysis_chart,
    probability_gauge, form_trend_chart
)
# Historical benchmarks for championship performance standards
from historical_benchmarks import (
    get_default_benchmarks, format_benchmark_for_display,
    calculate_round_benchmarks, BENCHMARK_METHODOLOGY
)
# Athlete deduplication for data quality
from athlete_dedup import clean_athlete_data, normalize_athlete_id

# Increase the maximum number of cells allowed by Pandas Styler.
pd.set_option("styler.render.max_elements", 1000000)

##########################################################
# 0) Our dictionary of Competition_ID-based filter
##########################################################
MAJOR_COMPETITIONS_CID = {
    "Olympics": {
        "2024": {"CID": "13079218", "Season": "2024"},  # Paris
        "2021": {"CID": "12992925", "Season": "2021"},  # Tokyo
        "2016": {"CID": "12877460", "Season": "2016"},  # Rio
        "2012": {"CID": "12825110", "Season": "2012"},  # London
        "2008": {"CID": "12042259", "Season": "2008"},  # Beijing
        "2004": {"CID": "8232064",  "Season": "2004"},  # Athens
        "2000": {"CID": "8257021",  "Season": "2000"},  # Sydney
        "1996": {"CID": "12828534", "Season": "1996"},  # Atlanta
        "1992": {"CID": "12828528", "Season": "1992"},  # Barcelona
        "1988": {"CID": "12828533", "Season": "1988"},  # Seoul
        "1984": {"CID": "12828557", "Season": "1984"}   # Los Angeles
    },
    "World Championships": {
        "2025": {"CID": "13112510", "Season": "2025"},  # Tokyo
        "2023": {"CID": "13046619", "Season": "2023"},  # Budapest
        "2022": {"CID": "13002354", "Season": "2022"},  # Oregon
        "2019": {"CID": "12935526", "Season": "2019"},  # Doha
        "2017": {"CID": "12898707", "Season": "2017"},  # London
        "2013": {"CID": "12844203", "Season": "2013"},  # Moscow
        "2011": {"CID": "12814135", "Season": "2011"},  # Daegu
        "2009": {"CID": "12789100", "Season": "2009"},  # Berlin
        "2007": {"CID": "10626603", "Season": "2007"},  # Osaka
        "2005": {"CID": "8906660",  "Season": "2005"},  # Helsinki
        "2003": {"CID": "7993620",  "Season": "2003"},  # Paris
        "2001": {"CID": "8257083",  "Season": "2001"},  # Edmonton
        "1999": {"CID": "8256922",  "Season": "1999"},  # Seville
        "1997": {"CID": "12996366", "Season": "1997"},  # Athens
        "1995": {"CID": "12828581", "Season": "1995"},  # Gothenburg
        "1993": {"CID": "12828580", "Season": "1993"},  # Stuttgart
        "1991": {"CID": "12996365", "Season": "1991"},  # Tokyo
        "1987": {"CID": "12996362", "Season": "1987"},  # Rome
        "1983": {"CID": "8255184",  "Season": "1983"}   # Helsinki
    },
    "World U20 Championships": {
        "2024": {"CID": "13080252", "Season": "2024"},  # Lima
        "2022": {"CID": "13002364", "Season": "2022"},  # Cali
        "2021": {"CID": "12993802", "Season": "2021"},  # Nairobi
        "2018": {"CID": "12910467", "Season": "2018"},  # Tampere
        "2016": {"CID": "12876812", "Season": "2016"},  # Bydgoszcz
        "2014": {"CID": "12853328", "Season": "2014"},  # Eugene
        "2012": {"CID": "12824526", "Season": "2012"},  # Barcelona
        "2008": {"CID": "11909738", "Season": "2008"},  # Bydgoszcz
        "2006": {"CID": "9238748",  "Season": "2006"},  # Beijing
        "2004": {"CID": "8196283",  "Season": "2004"},  # Grosseto
        "2000": {"CID": "8256856",  "Season": "2000"}   # Santiago
    },
    "World Athletics Indoor Championships": {
        "2025": {"CID": "13092360", "Season": "2025"},  # Nanjing
        "2024": {"CID": "13056938", "Season": "2024"},  # Glasgow
        "2022": {"CID": "13002200", "Season": "2022"},  # Belgrade
        "2018": {"CID": "12904540", "Season": "2018"},  # Birmingham
        "2016": {"CID": "12871065", "Season": "2016"},  # Portland
        "2014": {"CID": "12848482", "Season": "2014"},  # Sopot
        "2012": {"CID": "12821019", "Season": "2012"},  # Istanbul
        "2010": {"CID": "12794620", "Season": "2010"},  # Doha
        "2008": {"CID": "11465020", "Season": "2008"},  # Valencia
        "2006": {"CID": "9050779",  "Season": "2006"}   # Moscow
    },
    "Asian Games": {
        "2023": {"CID": "13048549", "Season": "2023"},  # Hangzhou
        "2018": {"CID": "12911586", "Season": "2018"},  # Jakarta
        "2014": {"CID": "12854365", "Season": "2014"}   # Incheon
    },
    "Asian Athletics Championships": {
        "2025": {"CID": "13105634", "Season": "2025"},  # Gumi
        "2023": {"CID": "13045167", "Season": "2023"},  # Bangkok
        "2019": {"CID": "12927085", "Season": "2019"},  # Doha
        "2017": {"CID": "12897142", "Season": "2017"},  # Bhubaneswar
        "2015": {"CID": "12861120", "Season": "2015"},  # Wuhan
        "2013": {"CID": "12843333", "Season": "2013"},  # Pune
        "2011": {"CID": "12812847", "Season": "2011"},  # Kobe
        "2007": {"CID": "10571413", "Season": "2007"},  # Amman
        "2005": {"CID": "8923929",  "Season": "2005"},  # Incheon
        "2003": {"CID": "7999347",  "Season": "2003"}   # Manila
    },
    "Asian Indoor Championships": {
        "2025": {"CID": "13092359", "Season": "2025"},  # Hangzhou
        "2023": {"CID": "13048100", "Season": "2023"},  # Astana
        "2018": {"CID": "12908028", "Season": "2018"},  # Tehran
        "2016": {"CID": "12869866", "Season": "2016"},  # Doha
        "2014": {"CID": "12847848", "Season": "2014"},  # Hangzhou
        "2012": {"CID": "12822308", "Season": "2012"},  # Hangzhou
        "2008": {"CID": "11466050", "Season": "2008"}   # Doha
    },
    "Youth Olympics": {
        "2018": {"CID": "12912645", "Season": "2018"},  # Buenos Aires
        "2014": {"CID": "12853759", "Season": "2014"},  # Nanjing
        "2010": {"CID": "12800536", "Season": "2010"}   # Singapore
    }
}

###################################
# 1) Streamlit Setup
###################################
st.set_page_config(
    page_title="Saudi Athletics - Performance Analysis",
    page_icon="Tilasoptija/Saudilogo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

###################################
# 2) Dark Background
###################################
def set_saudi_theme():
    """Apply Saudi Arabia branded theme with green accents."""
    css = """
    <style>
    /* Saudi Green Theme */
    .stApp {
        background-color: #0E1117;
    }
    .block-container {
        background-color: rgba(14, 17, 23, 0.95);
        padding: 2rem;
        border-radius: 12px;
        color: white;
    }
    /* Saudi Green headings */
    h1, h2, h3, h4 {
        color: #006C35 !important;
    }
    /* Accent color for links and highlights */
    a {
        color: #00A651 !important;
    }
    /* Saudi styled metrics */
    [data-testid="stMetricValue"] {
        color: #00A651 !important;
    }
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1F25;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        color: white;
    }
    .stTabs [aria-selected="true"] {
        background-color: #006C35 !important;
    }
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1A1F25;
        border-right: 2px solid #006C35;
    }
    /* Button styling */
    .stButton > button {
        background-color: #006C35;
        color: white;
        border: none;
    }
    .stButton > button:hover {
        background-color: #00A651;
        color: white;
    }
    /* Select boxes */
    .stSelectbox [data-baseweb="select"] {
        background-color: #1A1F25;
    }
    /* Expander headers */
    .streamlit-expanderHeader {
        background-color: #1A1F25;
        border-radius: 8px;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# Apply Saudi theme
set_saudi_theme()




###################################
# 3) DataFrame / Chart Helpers
###################################
def ensure_json_safe(df):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].apply(lambda x: float(x) if pd.notnull(x) else None)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d').fillna("")
        else:
            df[col] = df[col].astype(str).replace("None", "")
    return df

def style_dark_df(df):
    return df.style.set_properties(
        **{'background-color': '#222', 'color': 'white', 'border-color': 'gray'}
    ).hide(axis='index')

###################################
# 4) Basic Data Cleaning + Parsing
###################################
def clean_date(date_str):
    if isinstance(date_str, str):
        parts = date_str.split('_')
        return parts[0]
    return date_str

def clean_columns(df):
    str_cols = [
        "Athlete_ID", "Athlete_Name", "Athlete_Country", "Gender",
        "Round", "Position", "Personal_Best", "Competition", "City", "Stadium"
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": None}).str.strip()
    for dc in ["Start_Date", "End_Date", "Date_of_Birth"]:
        if dc in df.columns:
            df[dc] = df[dc].apply(clean_date)
            df[dc] = pd.to_datetime(df[dc], errors="coerce")
    return df

SAUDI_COLUMNS_DTYPE = {
    "Position": "numeric",
    "Result_numeric": "numeric",
    "Start_Date": "date",
    "End_Date": "date",
    "Date_of_Birth": "date"
}
MAJOR_COLUMNS_DTYPE = {
    "Position": "numeric",
    "Result_numeric": "numeric",
    "Start_Date": "date",
    "End_Date": "date",
    "Date_of_Birth": "date"
}

def coerce_dtypes(df, dtype_map):
    for col, ctype in dtype_map.items():
        if col not in df.columns:
            continue
        if ctype == "numeric":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif ctype == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

###################################
# 4) Basic Data Cleaning + Parsing (Event Results)
###################################


def get_event_list():
    return sorted(event_type_map.keys())

# 1. Event type map - determines sorting direction (time=ascending, distance/points=descending)
# As an athletics coach, this is critical for proper ranking:
# - Track events: Lower time = Better (ascending sort)
# - Field events (jumps/throws): Higher distance = Better (descending sort)
# - Combined events: Higher points = Better (descending sort)
event_type_map = {
    # === TRACK EVENTS (lower is better) ===
    # Sprints
    '50m': 'time', '55m': 'time', '60m': 'time', '100m': 'time', '150m': 'time',
    '200m': 'time', '300m': 'time', '400m': 'time',

    # Middle Distance
    '500m': 'time', '600m': 'time', '800m': 'time', '1000m': 'time',
    '1200m': 'time', '1500m': 'time', '1600m': 'time', 'Mile': 'time',
    '2000m': 'time', '3000m': 'time', '5000m': 'time',
    '10000m': 'time', '10,000m': 'time',

    # Long Distance / Road
    'Marathon': 'time', 'Half Marathon': 'time',
    '5km Road': 'time', '10km Road': 'time', '15km Road': 'time',
    '20km Road': 'time', '25km Road': 'time', '30km Road': 'time',
    '10 Miles, Road': 'time', '100km': 'time',

    # Hurdles - Men
    '50m Hurdles': 'time', '55m Hurdles': 'time', '60m Hurdles': 'time',
    '60m Hurdles (Men)': 'time', '60m Hurdles (Women)': 'time',
    '80m Hurdles': 'time',
    '100m Hurdles': 'time', '100m Hurdles (Youth)': 'time',
    '100m Hurdles (76.2cm)': 'time', '100m Hurdles (76.2cm, 7.5m)': 'time',
    '100m Hurdles (76.2cm, 8.25m)': 'time', '100m Hurdles (76.2cm, 8m)': 'time',
    '100m Hurdles (84cm)': 'time', '100m Hurdles (84cm, 8.25m)': 'time',
    '100m Hurdles (91.4cm)': 'time',
    '110m Hurdles': 'time', '110m Hurdles (Youth)': 'time',
    '110m Hurdles (84cm, 8.25m)': 'time',
    '110m Hurdles (91.4cm)': 'time', '110m Hurdles (91.4cm, 8.5m)': 'time',
    '110m Hurdles (91.4cm, 8.8m)': 'time', '110m Hurdles (91.4cm, 8.90m)': 'time',
    '110m Hurdles (99.1cm)': 'time', '110m Hurdles (99cm, 8.8m)': 'time',
    '110m Hurdles (106.7cm)': 'time',
    '200m Hurdles': 'time', '300m Hurdles': 'time',
    '300m Hurdles (76.2cm)': 'time', '300m Hurdles (84cm)': 'time',
    '400m Hurdles': 'time', '400m Hurdles (Youth)': 'time',
    '400m Hurdles (84cm)': 'time',

    # Steeplechase
    '1500m Steeplechase': 'time', '1500m Steeplechase, 76.2cm': 'time',
    '2000m Steeplechase': 'time', '2000m Steeplechase (84cm)': 'time',
    '3000m Steeplechase': 'time',

    # Relays
    '4x100m Relay': 'time', '4 x 100m': 'time', '4x100m': 'time',
    '4x200m Relay': 'time', '4 x 200m': 'time',
    '4x400m Relay': 'time', '4 x 400m': 'time', '4x400m': 'time',
    '4x400m Mixed Relay': 'time', '4 x 400m Mixed relay': 'time', 'Mixed 4 x 400m': 'time',
    '4x800m Relay': 'time', '4 x 800m': 'time',
    '4x1500m Relay': 'time', '4 x 1500m': 'time',
    'Shuttle Hurdles Relay': 'time', 'Swedish Relay': 'time', 'Medley Relay': 'time',

    # Race Walking
    '3000m Race Walk': 'time', '5000m Race Walk': 'time',
    '10000m Race Walk': 'time', '10,000m Race Walk': 'time', '10km Race Walk': 'time',
    '15km Race Walk': 'time',
    '20000m Race Walk': 'time', '20,000m Race Walk': 'time', '20km Race Walk': 'time',
    '30km Race Walk': 'time', '35km Race Walk': 'time', '50km Race Walk': 'time',

    # === FIELD EVENTS - JUMPS (higher is better) ===
    'High Jump': 'distance', 'High Jump Indoor': 'distance',
    'Pole Vault': 'distance', 'Pole Vault Indoor': 'distance',
    'Long Jump': 'distance', 'Long Jump Indoor': 'distance',
    'Triple Jump': 'distance', 'Triple Jump Indoor': 'distance',

    # === FIELD EVENTS - THROWS (higher/further is better) ===
    # Shot Put - various implements
    'Shot Put': 'distance', 'Shot Put Indoor': 'distance',
    'Shot Put (Youth)': 'distance',
    'Shot Put (3kg)': 'distance', 'Shot Put (4kg)': 'distance',
    'Shot Put (5kg)': 'distance', 'Shot Put (6kg)': 'distance',

    # Discus - various implements
    'Discus Throw': 'distance', 'Discus Throw (Youth)': 'distance',
    'Discus Throw (1kg)': 'distance', 'Discus Throw (1.5kg)': 'distance',
    'Discus Throw (1.75kg)': 'distance', 'Discus Throw (2kg)': 'distance',

    # Hammer - various implements
    'Hammer Throw': 'distance', 'Hammer Throw (Youth)': 'distance',
    'Hammer Throw (3kg)': 'distance', 'Hammer Throw (4kg)': 'distance',
    'Hammer Throw (5kg)': 'distance', 'Hammer Throw (6kg)': 'distance',

    # Javelin - various implements
    'Javelin Throw': 'distance', 'Javelin Throw (Youth)': 'distance',
    'Javelin Throw (Old)': 'distance', 'Javelin Throw (Old Model)': 'distance',
    'Javelin Throw (500g)': 'distance', 'Javelin Throw (600g)': 'distance',
    'Javelin Throw (700g)': 'distance', 'Javelin Throw (800g)': 'distance',

    # === COMBINED EVENTS (higher points is better) ===
    'Decathlon': 'points', 'Decathlon U18': 'points', 'Decathlon U20': 'points',
    'Heptathlon': 'points', 'Heptathlon U18': 'points', 'Heptathlon Indoor': 'points',
    'Pentathlon': 'points', 'Pentathlon Indoor': 'points',
    'Octathlon': 'points', 'Triathlon': 'points',
}

# Indoor-only events (never run outdoors at major championships)
INDOOR_ONLY_EVENTS = {
    '60m', '60m Hurdles', '60m Hurdles Women', '60m Hurdles Men',
    'Pentathlon Indoor', 'Heptathlon Indoor',
    'High Jump Indoor', 'Pole Vault Indoor', 'Long Jump Indoor', 'Triple Jump Indoor',
    'Shot Put Indoor', '3000m Indoor', '1500m Indoor', '800m Indoor', '400m Indoor',
}

# Outdoor-only events (never run indoors at major championships)
OUTDOOR_ONLY_EVENTS = {
    '100m', '200m',  # 200m sometimes run indoors but not common
    '100m Hurdles', '110m Hurdles',
    '400m Hurdles', '3000m Steeplechase', '2000m Steeplechase', '1500m Steeplechase',
    'Discus Throw', 'Hammer Throw', 'Javelin Throw',
    'Decathlon', 'Heptathlon',
    '10000m', '10,000m',
    'Marathon', 'Half Marathon',
    '20km Race Walk', '35km Race Walk', '50km Race Walk',
    '4x100m Relay', '4x400m Relay', '4x400m Mixed Relay',
}

def is_indoor_event(event_name):
    """Check if event is indoor-only."""
    if pd.isna(event_name):
        return False
    event = str(event_name).strip()
    return event in INDOOR_ONLY_EVENTS or 'Indoor' in event

def is_outdoor_event(event_name):
    """Check if event is outdoor-only (not run indoors)."""
    if pd.isna(event_name):
        return False
    event = str(event_name).strip()
    # If it has Indoor suffix, it's not outdoor-only
    if 'Indoor' in event:
        return False
    return event in OUTDOOR_ONLY_EVENTS

def filter_events_for_context(events, include_indoor=False, indoor_only=False):
    """
    Filter events based on indoor/outdoor context.
    - include_indoor=True: Include both indoor and outdoor events
    - indoor_only=True: Only show indoor events
    - Default: Only show outdoor events
    """
    if indoor_only:
        return [e for e in events if is_indoor_event(e)]
    elif include_indoor:
        # Include all events
        return events
    else:
        # Outdoor only - exclude indoor-specific events
        return [e for e in events if not is_indoor_event(e)]

def get_event_type(event_name):
    """
    Determine event type for proper sorting.
    Returns: 'time' (lower=better), 'distance' (higher=better), or 'points' (higher=better)
    """
    if pd.isna(event_name):
        return 'time'

    event_clean = str(event_name).strip()

    # Check direct mapping
    if event_clean in event_type_map:
        return event_type_map[event_clean]

    # Check without Indoor suffix
    event_base = event_clean.replace(' Indoor', '').strip()
    if event_base in event_type_map:
        return event_type_map[event_base]

    # Pattern matching for events not in map
    event_lower = event_clean.lower()

    # Throws (distance - higher is better)
    if any(t in event_lower for t in ['throw', 'put', 'discus', 'hammer', 'javelin', 'shot']):
        return 'distance'

    # Jumps (distance - higher is better)
    if any(j in event_lower for j in ['jump', 'vault']):
        return 'distance'

    # Combined events (points - higher is better)
    if any(c in event_lower for c in ['decathlon', 'heptathlon', 'pentathlon', 'octathlon', 'triathlon']):
        return 'points'

    # Default to time (lower is better) for track events
    return 'time'


def is_better_result(result1, result2, event_type):
    """
    Compare two results to determine if result1 is better than result2.
    For time events: lower is better
    For distance/points events: higher is better
    """
    if pd.isna(result1) or pd.isna(result2):
        return False

    if event_type == 'time':
        return result1 < result2
    else:  # distance or points
        return result1 > result2

# 2. Modified parse_result to handle relay-specific formatting
def parse_result(value, event):
    relay_events = {'4x100m Relay', '4x400m Relay', '4x400m Mixed Relay'}
    original_value = value

    try:
        if not isinstance(value, str) or not value.strip():
            return None

        value = value.strip().upper()

        # Clean known relay formatting issues
        if event in relay_events:
            match = re.search(r'(\d{1,2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?)', value)
            value = match.group(1) if match else re.sub(r'[^\d:.]', '', value)
        else:
            value = re.sub(r"^[^\d:-]+", "", value)

        # Strip suffixes like 'A', 'H'
        value = value.replace('A', '').replace('H', '').strip()

        # Exclude invalid result types
        if value in {'DNF', 'DNS', 'DQ', 'NM', ''}:
            return None

        # Handle None event
        if event is None:
            event = ''
        event_clean = event.strip().replace("Indoor", "").strip()
        e_type = event_type_map.get(event, event_type_map.get(event_clean, 'other'))

        # Time parsing
        if e_type == 'time':
            parts = value.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            return float(value)

        # Distance / Points parsing
        elif e_type in {'distance', 'points'}:
            return float(value)

    except Exception as e:
        # Avoid emoji to prevent encoding issues on Windows
        pass  # Silently skip parse errors
        return None

    return None


def normalize_relay_events(df):
    if 'Event' not in df.columns:
        return df

    # Strip whitespace but preserve original case
    df['Event'] = df['Event'].astype(str).str.strip()

    relay_map = {
        r'4\s*[x×*]\s*100': '4x100m Relay',
        r'4\s*[x×*]\s*400\s*mixed': '4x400m Mixed Relay',
        r'4\s*[x×*]\s*400': '4x400m Relay',
    }

    # Only replace matching relay events (case-insensitive match)
    for pattern, standard in relay_map.items():
        mask = df['Event'].str.lower().str.contains(pattern, regex=True, na=False)
        df.loc[mask, 'Event'] = standard

    return df


# Olympic & World Championship Qualification Standards (2024/2025/2028)
# Format: {event: {'olympic': value, 'world': value, 'tokyo_2025': value}} - seconds for time, meters for field
# Tokyo 2025 WC standards: https://citiusmag.com/articles/qualifying-standards-world-athletics-championships-tokyo-2025
QUALIFICATION_STANDARDS = {
    # Men's Track (times in seconds)
    '100m': {'olympic': 10.00, 'world': 10.00, 'tokyo_2025': 10.00, 'la_2028': 10.00, 'gender': 'Men'},
    '200m': {'olympic': 20.16, 'world': 20.24, 'tokyo_2025': 20.16, 'la_2028': 20.16, 'gender': 'Men'},
    '400m': {'olympic': 44.90, 'world': 45.00, 'tokyo_2025': 44.85, 'la_2028': 44.90, 'gender': 'Men'},
    '800m': {'olympic': 103.50, 'world': 103.80, 'tokyo_2025': 104.50, 'la_2028': 103.50, 'gender': 'Men'},  # 1:43.50 / 1:44.50
    '1500m': {'olympic': 213.00, 'world': 214.00, 'tokyo_2025': 213.00, 'la_2028': 213.00, 'gender': 'Men'},  # 3:33.00
    '5000m': {'olympic': 780.00, 'world': 786.00, 'tokyo_2025': 781.00, 'la_2028': 780.00, 'gender': 'Men'},  # 13:01.00
    '10000m': {'olympic': 1620.00, 'world': 1635.00, 'tokyo_2025': 1620.00, 'la_2028': 1620.00, 'gender': 'Men'},  # 27:00.00
    '110m Hurdles': {'olympic': 13.27, 'world': 13.30, 'tokyo_2025': 13.27, 'la_2028': 13.27, 'gender': 'Men'},
    '400m Hurdles': {'olympic': 48.70, 'world': 49.00, 'tokyo_2025': 48.50, 'la_2028': 48.70, 'gender': 'Men'},
    '3000m Steeplechase': {'olympic': 503.00, 'world': 505.00, 'tokyo_2025': 495.00, 'la_2028': 503.00, 'gender': 'Men'},  # 8:15.00 Tokyo
    'Marathon': {'olympic': 7590.00, 'world': 7590.00, 'tokyo_2025': 7590.00, 'la_2028': 7590.00, 'gender': 'Men'},  # 2:06:30
    '20km Race Walk': {'olympic': 4740.00, 'world': 4760.00, 'tokyo_2025': 4760.00, 'la_2028': 4740.00, 'gender': 'Men'},  # 1:19:20
    '35km Race Walk': {'olympic': 8880.00, 'world': 8880.00, 'tokyo_2025': 8880.00, 'la_2028': 8880.00, 'gender': 'Men'},  # 2:28:00

    # Men's Field (distances in meters)
    'High Jump': {'olympic': 2.33, 'world': 2.30, 'tokyo_2025': 2.33, 'la_2028': 2.33, 'gender': 'Men'},
    'Pole Vault': {'olympic': 5.82, 'world': 5.75, 'tokyo_2025': 5.82, 'la_2028': 5.82, 'gender': 'Men'},
    'Long Jump': {'olympic': 8.27, 'world': 8.15, 'tokyo_2025': 8.27, 'la_2028': 8.27, 'gender': 'Men'},
    'Triple Jump': {'olympic': 17.22, 'world': 17.00, 'tokyo_2025': 17.22, 'la_2028': 17.22, 'gender': 'Men'},
    'Shot Put': {'olympic': 21.35, 'world': 21.00, 'tokyo_2025': 21.50, 'la_2028': 21.35, 'gender': 'Men'},
    'Discus Throw': {'olympic': 67.20, 'world': 66.00, 'tokyo_2025': 67.50, 'la_2028': 67.20, 'gender': 'Men'},
    'Hammer Throw': {'olympic': 78.00, 'world': 77.00, 'tokyo_2025': 78.20, 'la_2028': 78.00, 'gender': 'Men'},
    'Javelin Throw': {'olympic': 85.50, 'world': 84.00, 'tokyo_2025': 85.50, 'la_2028': 85.50, 'gender': 'Men'},
    'Decathlon': {'olympic': 8460, 'world': 8300, 'tokyo_2025': 8550, 'la_2028': 8460, 'gender': 'Men'},

    # Women's Track
    '100m_W': {'olympic': 11.07, 'world': 11.15, 'tokyo_2025': 11.07, 'la_2028': 11.07, 'gender': 'Women'},
    '200m_W': {'olympic': 22.57, 'world': 22.80, 'tokyo_2025': 22.57, 'la_2028': 22.57, 'gender': 'Women'},
    '400m_W': {'olympic': 50.40, 'world': 51.00, 'tokyo_2025': 50.75, 'la_2028': 50.40, 'gender': 'Women'},
    '800m_W': {'olympic': 118.00, 'world': 119.00, 'tokyo_2025': 119.00, 'la_2028': 118.00, 'gender': 'Women'},  # 1:59.00 Tokyo
    '1500m_W': {'olympic': 240.00, 'world': 242.00, 'tokyo_2025': 241.50, 'la_2028': 240.00, 'gender': 'Women'},  # 4:01.50 Tokyo
    '5000m_W': {'olympic': 882.00, 'world': 888.00, 'tokyo_2025': 890.00, 'la_2028': 882.00, 'gender': 'Women'},  # 14:50.00 Tokyo
    '10000m_W': {'olympic': 1800.00, 'world': 1820.00, 'tokyo_2025': 1820.00, 'la_2028': 1800.00, 'gender': 'Women'},  # 30:20.00
    '100m Hurdles': {'olympic': 12.77, 'world': 12.90, 'tokyo_2025': 12.73, 'la_2028': 12.77, 'gender': 'Women'},
    '400m Hurdles_W': {'olympic': 54.85, 'world': 55.50, 'tokyo_2025': 54.65, 'la_2028': 54.85, 'gender': 'Women'},
    '3000m Steeplechase_W': {'olympic': 555.00, 'world': 558.00, 'tokyo_2025': 558.00, 'la_2028': 555.00, 'gender': 'Women'},  # 9:18.00
    'Marathon_W': {'olympic': 8460.00, 'world': 8610.00, 'tokyo_2025': 8610.00, 'la_2028': 8460.00, 'gender': 'Women'},  # 2:23:30
    '20km Race Walk_W': {'olympic': 5280.00, 'world': 5340.00, 'tokyo_2025': 5340.00, 'la_2028': 5280.00, 'gender': 'Women'},  # 1:29:00
    '35km Race Walk_W': {'olympic': 10080.00, 'world': 10080.00, 'tokyo_2025': 10080.00, 'la_2028': 10080.00, 'gender': 'Women'},  # 2:48:00

    # Women's Field
    'High Jump_W': {'olympic': 1.97, 'world': 1.93, 'tokyo_2025': 1.97, 'la_2028': 1.97, 'gender': 'Women'},
    'Pole Vault_W': {'olympic': 4.73, 'world': 4.60, 'tokyo_2025': 4.73, 'la_2028': 4.73, 'gender': 'Women'},
    'Long Jump_W': {'olympic': 6.86, 'world': 6.75, 'tokyo_2025': 6.86, 'la_2028': 6.86, 'gender': 'Women'},
    'Triple Jump_W': {'olympic': 14.55, 'world': 14.30, 'tokyo_2025': 14.55, 'la_2028': 14.55, 'gender': 'Women'},
    'Shot Put_W': {'olympic': 18.80, 'world': 18.50, 'tokyo_2025': 18.80, 'la_2028': 18.80, 'gender': 'Women'},
    'Discus Throw_W': {'olympic': 64.50, 'world': 63.00, 'tokyo_2025': 64.50, 'la_2028': 64.50, 'gender': 'Women'},
    'Hammer Throw_W': {'olympic': 74.00, 'world': 72.00, 'tokyo_2025': 74.00, 'la_2028': 74.00, 'gender': 'Women'},
    'Javelin Throw_W': {'olympic': 64.00, 'world': 62.00, 'tokyo_2025': 64.00, 'la_2028': 64.00, 'gender': 'Women'},
    'Heptathlon': {'olympic': 6480, 'world': 6300, 'tokyo_2025': 6500, 'la_2028': 6480, 'gender': 'Women'},
}

# Target field sizes for ranking qualification (50% of total field)
EVENT_QUOTAS = {
    '100m': 24, '200m': 24, '400m': 24, '800m': 24, '1500m': 22, '5000m': 21,
    '10000m': 14, '110m Hurdles': 20, '100m Hurdles': 20, '400m Hurdles': 20,
    '3000m Steeplechase': 22, 'Marathon': 40, '20km Race Walk': 30, '35km Race Walk': 25,
    'High Jump': 16, 'Pole Vault': 16, 'Long Jump': 16, 'Triple Jump': 16,
    'Shot Put': 16, 'Discus Throw': 16, 'Hammer Throw': 16, 'Javelin Throw': 16,
    'Decathlon': 12, 'Heptathlon': 12,
}

def get_qualification_standard(event_name, gender='Men'):
    """Get Olympic and World Championship qualification standards for an event."""
    # Try direct match first
    if event_name in QUALIFICATION_STANDARDS:
        std = QUALIFICATION_STANDARDS[event_name]
        if std.get('gender') == gender or gender == 'Men':
            return std

    # Try with gender suffix for women
    if gender == 'Women':
        key = f"{event_name}_W"
        if key in QUALIFICATION_STANDARDS:
            return QUALIFICATION_STANDARDS[key]

    # Clean event name and try again
    event_clean = event_name.replace(' Indoor', '').strip()
    if event_clean in QUALIFICATION_STANDARDS:
        return QUALIFICATION_STANDARDS[event_clean]

    return None


###################################
# 5) Data Loader (CSV or SQLite)
###################################

# Configuration: Set data source
# Options: "csv", "sqlite", "major_champs", "combined", or "deploy" (optimized for hosting)
DATA_SOURCE = "deploy"  # Use optimized deployment databases
CSV_FILE = "Tilastoptja_Data/ksa_only.csv"  # KSA-filtered data (8,591 rows)
SQLITE_FILE = "SQL/ksa_athletics.db"  # SQLite version of KSA data
MAJOR_CHAMPS_FILE = "SQL/major_championships.db"  # Full major championships data (88k rows)
DEPLOY_DB_FILE = "SQL/athletics_deploy.db"  # Major champs + KSA (47MB) - for Road to dashboards
COMPETITOR_DB_FILE = "SQL/athletics_competitor.db"  # 2024-today data (456MB) - for Competitor Analysis

@st.cache_data
def load_csv_data(csv_filename: str):
    """Load data from new Tilastopaja CSV format."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, csv_filename)

    if not os.path.exists(csv_path):
        st.warning(f"CSV file not found: {csv_filename}")
        return pd.DataFrame()

    # Read CSV with semicolon delimiter
    df = pd.read_csv(csv_path, delimiter=';', low_memory=False)

    # Create Athlete_Name from firstname + lastname
    df['Athlete_Name'] = (
        df['firstname'].fillna('').astype(str) + ' ' +
        df['lastname'].fillna('').astype(str)
    ).str.strip()

    # Map gender M/F to Men/Women
    df['Gender'] = df['gender'].map({'M': 'Men', 'F': 'Women'})

    # Rename columns to match existing app expectations
    df = df.rename(columns={
        'auto': 'Row_id',
        'competitionid': 'Competition_ID',
        'competitionname': 'Competition',
        'competitionvenue': 'Venue',
        'athleteid': 'Athlete_ID',
        'nationality': 'Athlete_CountryCode',
        'DOB': 'Date_of_Birth',
        'eventname': 'Event',
        'performance': 'Result',
        'competitiondate': 'Start_Date',
        'competitioncountry': 'Venue_CountryCode',
        'round': 'Round',
        'position': 'Position',
    })

    # Ensure Round column is string type and map to readable names
    if 'Round' in df.columns:
        df['Round'] = df['Round'].astype(str).replace('nan', 'Final')
        # Map round codes to readable names
        round_mapping = {
            '': 'Final',
            'nan': 'Final',
            'h1': 'Heat 1', 'h2': 'Heat 2', 'h3': 'Heat 3', 'h4': 'Heat 4',
            'h5': 'Heat 5', 'h6': 'Heat 6', 'h7': 'Heat 7', 'h8': 'Heat 8',
            'H1': 'Heat 1', 'H2': 'Heat 2', 'H3': 'Heat 3', 'H4': 'Heat 4',
            's1': 'Semi 1', 's2': 'Semi 2', 's3': 'Semi 3',
            'S1': 'Semi 1', 'S2': 'Semi 2', 'S3': 'Semi 3',
            'q': 'Qualification', 'Q': 'Qualification',
            'r1': 'Round 1', 'r2': 'Round 2', 'r3': 'Round 3',
            'rB': 'Race B', 'rC': 'Race C', 'rD': 'Race D',
            'f': 'Final', 'F': 'Final',
            '-19': 'U19', '-17': 'U17', '-15': 'U15',
            '-18': 'U18', '-20': 'U20', '-22': 'U22', '-35': 'M35', '-40': 'M40',
        }
        df['Round'] = df['Round'].replace(round_mapping)
        # Handle combined codes like 'h1-19' -> 'Heat 1 U19'
        df['Round'] = df['Round'].str.replace(r'^h(\d)-(\d+)$', r'Heat \1 U\2', regex=True)
        df['Round'] = df['Round'].str.replace(r'^s(\d)-(\d+)$', r'Semi \1 U\2', regex=True)
        df['Round'] = df['Round'].str.replace(r'^q-(\d+)$', r'Qual U\1', regex=True)

    # Keep wapoints, wind, SB columns with their original names
    # Rename PB to Personal_Best
    if 'PB' in df.columns:
        df = df.rename(columns={'PB': 'Personal_Best'})

    # Create Athlete_Country from lookup (full country name)
    df['Athlete_Country'] = df['Athlete_CountryCode'].map(COUNTRY_CODES).fillna(df['Athlete_CountryCode'])

    # Create Venue_Country from lookup
    if 'Venue_CountryCode' in df.columns:
        df['Venue_Country'] = df['Venue_CountryCode'].map(COUNTRY_CODES).fillna(df['Venue_CountryCode'])

    # Set End_Date = Start_Date (not in new format)
    df['End_Date'] = df['Start_Date']

    # Copy venue to stadium
    df['Stadium'] = df['Venue']

    # Apply existing transformations
    df = clean_columns(df)
    df = normalize_relay_events(df)

    # Filter out rows where Event is missing
    if "Event" in df.columns:
        df = df[df["Event"].notnull()]

    # Parse results to numeric
    if 'Result' in df.columns and 'Event' in df.columns:
        df['Result_numeric'] = df.apply(lambda row: parse_result(row['Result'], row['Event']), axis=1)

    # Apply type coercion
    df = coerce_dtypes(df, SAUDI_COLUMNS_DTYPE)

    # Calculate Year from Start_Date
    if 'Year' not in df.columns and 'Start_Date' in df.columns:
        df['Year'] = df['Start_Date'].dt.year

    # Handle wind-assisted flag
    if 'windlegal' in df.columns:
        df['Is_Wind_Assisted'] = df['windlegal'].str.contains('Wind Assisted', case=False, na=False)

    # Ensure wapoints is numeric
    if 'wapoints' in df.columns:
        df['wapoints'] = pd.to_numeric(df['wapoints'], errors='coerce')

    return df


@st.cache_data
def load_sqlite_data(db_filename: str):
    """Load data from database (Azure SQL or local SQLite).

    Automatically detects environment:
    - Streamlit Cloud: Uses Azure SQL if AZURE_SQL_CONN secret is set
    - Local: Uses SQLite files
    """
    # Try Azure SQL / SQLite via azure_db module (auto-detects which to use)
    db_name = db_filename.replace('SQL/', '').replace('.db', '').replace('athletics_', '')

    try:
        df = query_data("SELECT * FROM athletics_data", db_name=db_name)
        if df.empty:
            st.warning(f"No data returned from database. Connection mode: {get_connection_mode()}")
            return pd.DataFrame()
    except Exception as e:
        # If Azure/query_data fails, fall back to direct SQLite
        if get_connection_mode() == 'azure':
            st.error(f"Azure SQL connection failed: {str(e)}. Attempting local SQLite fallback...")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_filename)

        if not os.path.exists(db_path):
            st.error(f"Database not found: {db_filename}. Connection mode: {get_connection_mode()}")
            return pd.DataFrame()

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT * FROM athletics_data", conn)
            conn.close()
        except Exception as e2:
            st.error(f"SQLite fallback also failed: {str(e2)}")
            return pd.DataFrame()

    # Apply same transformations as CSV loader
    # Create Athlete_Name from firstname + lastname if needed
    if 'firstname' in df.columns:
        df['Athlete_Name'] = (
            df['firstname'].fillna('').astype(str) + ' ' +
            df['lastname'].fillna('').astype(str)
        ).str.strip()
        df['Gender'] = df['gender'].map({'M': 'Men', 'F': 'Women'})
        df = df.rename(columns={
            'auto': 'Row_id',
            'competitionid': 'Competition_ID',
            'competitionname': 'Competition',
            'competitionvenue': 'Venue',
            'athleteid': 'Athlete_ID',
            'nationality': 'Athlete_CountryCode',
            'DOB': 'Date_of_Birth',
            'eventname': 'Event',
            'performance': 'Result',
            'competitiondate': 'Start_Date',
            'competitioncountry': 'Venue_CountryCode',
            'round': 'Round',
            'position': 'Position',
            # Pre-computed columns from rebuild_all_data.py (Phase 2 optimization)
            'result_numeric': 'Result_numeric',
            'year': 'Year',
            'round_normalized': 'Round_normalized',
        })
        # Use pre-computed Round_normalized if available, otherwise compute
        if 'Round_normalized' not in df.columns and 'Round' in df.columns:
            df['Round'] = df['Round'].astype(str).replace('nan', 'Final')
            # Map round codes to readable names
            round_mapping = {
                '': 'Final',
                'nan': 'Final',
                'h1': 'Heat 1', 'h2': 'Heat 2', 'h3': 'Heat 3', 'h4': 'Heat 4',
                'h5': 'Heat 5', 'h6': 'Heat 6', 'h7': 'Heat 7', 'h8': 'Heat 8',
                'H1': 'Heat 1', 'H2': 'Heat 2', 'H3': 'Heat 3', 'H4': 'Heat 4',
                's1': 'Semi 1', 's2': 'Semi 2', 's3': 'Semi 3',
                'S1': 'Semi 1', 'S2': 'Semi 2', 'S3': 'Semi 3',
                'q': 'Qualification', 'Q': 'Qualification',
                'r1': 'Round 1', 'r2': 'Round 2', 'r3': 'Round 3',
                'rB': 'Race B', 'rC': 'Race C', 'rD': 'Race D',
                'f': 'Final', 'F': 'Final',
                '-19': 'U19', '-17': 'U17', '-15': 'U15',
                '-18': 'U18', '-20': 'U20', '-22': 'U22', '-35': 'M35', '-40': 'M40',
            }
            df['Round'] = df['Round'].replace(round_mapping)
            df['Round'] = df['Round'].str.replace(r'^h(\d)-(\d+)$', r'Heat \1 U\2', regex=True)
            df['Round'] = df['Round'].str.replace(r'^s(\d)-(\d+)$', r'Semi \1 U\2', regex=True)
            df['Round'] = df['Round'].str.replace(r'^q-(\d+)$', r'Qual U\1', regex=True)
        if 'PB' in df.columns:
            df = df.rename(columns={'PB': 'Personal_Best'})
        df['Athlete_Country'] = df['Athlete_CountryCode'].map(COUNTRY_CODES).fillna(df['Athlete_CountryCode'])
        if 'Venue_CountryCode' in df.columns:
            df['Venue_Country'] = df['Venue_CountryCode'].map(COUNTRY_CODES).fillna(df['Venue_CountryCode'])
        df['End_Date'] = df['Start_Date']
        df['Stadium'] = df['Venue']
    else:
        # For deploy database format (already has Athlete_Name, processed columns)
        # Still need to normalize Round values
        if 'Round' in df.columns:
            df['Round'] = df['Round'].astype(str).replace('nan', 'Final')
            # Map known round values to standardized names
            round_mapping = {
                '': 'Final', 'nan': 'Final', 'None': 'Final',
                'Heats': 'Heats', 'Semifinals': 'Semifinals',
                'Qualification': 'Qualification', 'Final': 'Final'
            }
            df['Round'] = df['Round'].replace(round_mapping)

    df = clean_columns(df)
    df = normalize_relay_events(df)

    if "Event" in df.columns:
        df = df[df["Event"].notnull()]

    df = coerce_dtypes(df, SAUDI_COLUMNS_DTYPE)

    # Parse Result_numeric (ALWAYS do this regardless of database format)
    if 'Result' in df.columns and 'Event' in df.columns and 'Result_numeric' not in df.columns:
        df['Result_numeric'] = df.apply(lambda row: parse_result(row['Result'], row['Event']), axis=1)

    if 'Year' not in df.columns and 'Start_Date' in df.columns:
        df['Year'] = df['Start_Date'].dt.year

    if 'windlegal' in df.columns:
        df['Is_Wind_Assisted'] = df['windlegal'].str.contains('Wind Assisted', case=False, na=False)

    # Ensure wapoints is numeric
    if 'wapoints' in df.columns:
        df['wapoints'] = pd.to_numeric(df['wapoints'], errors='coerce')

    # Optimize DataFrame memory usage for faster operations
    df = optimize_dataframe(df)

    return df


@st.cache_data
def load_major_champs_data(db_filename: str):
    """Load data from major championships database (Azure SQL or local SQLite)."""
    try:
        # Try Azure SQL / SQLite via azure_db module (always use 'major' for major champs)
        df = query_data("SELECT * FROM athletics_data", db_name='major')
        if df.empty:
            st.warning(f"No data returned from major championships database. Connection mode: {get_connection_mode()}")
            return pd.DataFrame()
    except Exception as e:
        # Fallback to direct SQLite connection
        if get_connection_mode() == 'azure':
            st.error(f"Azure SQL connection failed: {str(e)}. Attempting local SQLite fallback...")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_filename)

        if not os.path.exists(db_path):
            st.error(f"Major championships database not found: {db_filename}")
            return pd.DataFrame()

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT * FROM athletics_data", conn)
            conn.close()
        except Exception as e2:
            st.error(f"SQLite fallback also failed: {str(e2)}")
            return pd.DataFrame()

    # Transform new Tilastopaja column format to dashboard format
    if 'firstname' in df.columns:
        # Create Athlete_Name from firstname + lastname
        df['Athlete_Name'] = (
            df['firstname'].fillna('').astype(str) + ' ' +
            df['lastname'].fillna('').astype(str)
        ).str.strip()

        # Map gender
        df['Gender'] = df['gender'].map({'M': 'Men', 'F': 'Women'})

        # Rename columns to dashboard format
        df = df.rename(columns={
            'auto': 'Row_id',
            'competitionid': 'Competition_ID',
            'competitionname': 'Competition',
            'competitionvenue': 'Venue',
            'athleteid': 'Athlete_ID',
            'nationality': 'Athlete_CountryCode',
            'DOB': 'Date_of_Birth',
            'eventname': 'Event',
            'performance': 'Result',
            'competitiondate': 'Start_Date',
            'competitioncountry': 'Venue_CountryCode',
            'round': 'Round',
            'position': 'Position',
            # Pre-computed columns from rebuild_all_data.py (Phase 2 optimization)
            'result_numeric': 'Result_numeric',
            'year': 'Year',
            'round_normalized': 'Round_normalized',
        })

        # Map country codes to full names
        df['Athlete_Country'] = df['Athlete_CountryCode'].map(COUNTRY_CODES).fillna(df['Athlete_CountryCode'])
        if 'Venue_CountryCode' in df.columns:
            df['Venue_Country'] = df['Venue_CountryCode'].map(COUNTRY_CODES).fillna(df['Venue_CountryCode'])

        # Set stadium/venue
        df['Stadium'] = df.get('Venue', '')
        df['End_Date'] = df['Start_Date']

        # Rename PB column
        if 'PB' in df.columns:
            df = df.rename(columns={'PB': 'Personal_Best'})

    # Format Round values (only if pre-computed Round_normalized not available)
    if 'Round_normalized' not in df.columns and 'Round' in df.columns:
        df['Round'] = df['Round'].astype(str).replace('nan', 'Final').str.strip()
        # Map round codes to readable names
        round_mapping = {
            '': 'Final', 'nan': 'Final', 'None': 'Final',
            'h1': 'Heat 1', 'h2': 'Heat 2', 'h3': 'Heat 3', 'h4': 'Heat 4',
            'h5': 'Heat 5', 'h6': 'Heat 6', 'h7': 'Heat 7', 'h8': 'Heat 8',
            'H1': 'Heat 1', 'H2': 'Heat 2', 'H3': 'Heat 3', 'H4': 'Heat 4',
            's1': 'Semi 1', 's2': 'Semi 2', 's3': 'Semi 3',
            'S1': 'Semi 1', 'S2': 'Semi 2', 'S3': 'Semi 3',
            'sf': 'Semi-Final', 'SF': 'Semi-Final',
            'q': 'Qualification', 'Q': 'Qualification',
            'r1': 'Round 1', 'r2': 'Round 2', 'r3': 'Round 3',
            'f': 'Final', 'F': 'Final',
        }
        df['Round'] = df['Round'].replace(round_mapping)
        # Handle patterns like h1-20 (Heat 1 U20)
        df['Round'] = df['Round'].str.replace(r'^h(\d)-(\d+)$', r'Heat \1 U\2', regex=True)
        df['Round'] = df['Round'].str.replace(r'^s(\d)-(\d+)$', r'Semi \1 U\2', regex=True)

    # Clean and process data
    df = clean_columns(df)
    df = normalize_relay_events(df)

    if "Event" in df.columns:
        df = df[df["Event"].notnull()]

    # Only compute Result_numeric if not pre-computed
    if 'Result_numeric' not in df.columns and 'Result' in df.columns and 'Event' in df.columns:
        df['Result_numeric'] = df.apply(lambda row: parse_result(row['Result'], row['Event']), axis=1)

    df = coerce_dtypes(df, MAJOR_COLUMNS_DTYPE)

    # Calculate Year from Start_Date
    if 'Year' not in df.columns and 'Start_Date' in df.columns:
        df['Year'] = df['Start_Date'].dt.year

    # Handle wind-assisted flag
    if 'windlegal' in df.columns:
        df['Is_Wind_Assisted'] = df['windlegal'].str.contains('Wind Assisted', case=False, na=False)

    # Ensure wapoints is numeric
    if 'wapoints' in df.columns:
        df['wapoints'] = pd.to_numeric(df['wapoints'], errors='coerce')

    return df


@st.cache_data(ttl=3600)  # Cache for 1 hour, refresh on restart
def load_data(_cache_version="v8"):  # Change version to force cache refresh
    """Load data from configured source (CSV, SQLite, major_champs, combined, or deploy)."""
    if DATA_SOURCE == "csv":
        df = load_csv_data(CSV_FILE)
    elif DATA_SOURCE == "major_champs":
        df = load_major_champs_data(MAJOR_CHAMPS_FILE)
    elif DATA_SOURCE == "deploy":
        # Optimized deployment database - all major championships + KSA data
        df = load_sqlite_data(DEPLOY_DB_FILE)
    elif DATA_SOURCE == "combined":
        # Load both KSA data and major championships, merge them
        df_ksa = load_sqlite_data(SQLITE_FILE)
        df_major = load_major_champs_data(MAJOR_CHAMPS_FILE)

        # Combine both datasets, removing duplicates
        # KSA data has all Saudi athlete results; major_champs has all athletes at major events
        df = pd.concat([df_ksa, df_major], ignore_index=True)

        # Remove duplicates based on key columns (same athlete, event, date, result)
        dup_cols = ['Athlete_Name', 'Event', 'Start_Date', 'Result', 'Competition_ID']
        available_cols = [c for c in dup_cols if c in df.columns]
        if available_cols:
            df = df.drop_duplicates(subset=available_cols, keep='first')
    else:
        df = load_sqlite_data(SQLITE_FILE)

    # Clean athlete data (deduplicate IDs, normalize names)
    if not df.empty:
        df = clean_athlete_data(df)

    return df


@st.cache_data
def load_competitor_data():
    """Load competitor analysis data (2024-today) from database (Azure SQL or local SQLite)."""
    try:
        # Try Azure SQL / SQLite via azure_db module
        df = query_data("SELECT * FROM athletics_data", db_name='competitor')
        if df.empty:
            st.warning(f"No data returned from competitor database. Connection mode: {get_connection_mode()}")
            return load_data()  # Fall back to main database
    except Exception as e:
        # Fallback to direct SQLite connection or main database
        if get_connection_mode() == 'azure':
            st.error(f"Azure SQL connection failed: {str(e)}. Attempting local SQLite fallback...")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, COMPETITOR_DB_FILE)

        if not os.path.exists(db_path):
            # Fall back to main deploy database if competitor DB doesn't exist
            return load_data()

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql("SELECT * FROM athletics_data", conn)
            conn.close()
        except Exception as e2:
            st.error(f"SQLite fallback also failed: {str(e2)}. Using main database...")
            return load_data()

    # Clean athlete data (deduplicate IDs, normalize names)
    if not df.empty:
        df = clean_athlete_data(df)

    # Parse Result_numeric (need to pass event for proper parsing)
    if 'Result' in df.columns and 'Result_numeric' not in df.columns:
        if 'Event' in df.columns:
            df['Result_numeric'] = df.apply(lambda row: parse_result(row['Result'], row['Event']), axis=1)
        else:
            # Fallback - parse without event context
            df['Result_numeric'] = df['Result'].apply(lambda x: parse_result(x, '100m'))

    # Add Year column
    if 'Start_Date' in df.columns and 'Year' not in df.columns:
        df['Year'] = pd.to_datetime(df['Start_Date'], errors='coerce').dt.year

    return df


# Load data at startup
df_major = load_data()

# Assign country as Athlete_Name fallback for relays
if not df_major.empty and 'Athlete_Name' in df_major.columns:
    df_major['Athlete_Name'] = df_major.apply(
        lambda row: row['Athlete_Name'] if pd.notna(row['Athlete_Name']) and str(row['Athlete_Name']).strip() != '' else row.get('Athlete_Country', 'Team'),
        axis=1
    )







###################################
# 6) Athlete Expansions
###################################
def show_single_athlete_profile(profile, db_label):
    name = profile['Athlete_Name'].iloc[0] if 'Athlete_Name' in profile.columns else "Unknown"
    country = profile['Athlete_Country'].iloc[0] if 'Athlete_Country' in profile.columns else "N/A"
    dob = profile['Date_of_Birth'].iloc[0] if 'Date_of_Birth' in profile.columns else None
    def position_medal(pos):
        if pd.isna(pos):
            return ""
        try:
            p_ = int(pos)
            if p_ == 1:
                return "🥇"
            elif p_ == 2:
                return "🥈"
            elif p_ == 3:
                return "🥉"
        except:
            return ""
        return ""
    grouped = profile.copy()
    cur_year = datetime.datetime.now().year

    if 'Start_Date' in grouped.columns:
        grouped['Year'] = grouped['Start_Date'].dt.year.astype('Int64')
    if pd.notna(dob) and 'Start_Date' in grouped.columns:
        grouped['Age'] = ((grouped['Start_Date'] - dob).dt.days / 365.25).astype(int)
    else:
        grouped['Age'] = np.nan
    if 'Round' in grouped.columns:
        grouped['Round'] = grouped['Round'].astype(str).replace({'nan': 'Final', '': 'Final', 'None': 'Final'})

    # Filter to last 3 years for profile focus
    if 'Year' in grouped.columns:
        last_3_years = grouped[grouped['Year'] >= cur_year - 3].copy()
    else:
        last_3_years = grouped.copy()

    events_ = ", ".join(last_3_years['Event'].dropna().unique()) if 'Event' in last_3_years.columns else "N/A"
    total_results = len(last_3_years)

    with st.expander(f"{name} ({country})", expanded=False):
        st.subheader("Athlete Profile Summary (Last 3 Years)")

        # === BASIC INFO ===
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Name:** {name}")
            st.markdown(f"**Country:** {country}")
            if pd.notna(dob):
                age = (datetime.datetime.now() - dob).days // 365
                st.markdown(f"**DOB:** {dob.strftime('%Y-%m-%d')} (Age {age})")
            else:
                st.markdown("**DOB:** N/A")
        with col2:
            st.markdown(f"**Events:** {events_}")
            st.markdown(f"**Results (3yr):** {total_results}")
            if 'Competition' in last_3_years.columns:
                comp_count = last_3_years['Competition'].nunique()
                st.markdown(f"**Competitions:** {comp_count}")
        with col3:
            # Personal Bests (last 3 years)
            if 'Result_numeric' in last_3_years.columns and not last_3_years['Result_numeric'].isna().all():
                st.markdown("**Personal Best(s):**")
                for event_name in last_3_years['Event'].dropna().unique()[:3]:  # Top 3 events
                    event_data = last_3_years[last_3_years['Event'] == event_name]
                    if event_data['Result_numeric'].isna().all():
                        continue
                    ev_type = get_event_type(event_name)
                    if ev_type == 'time':
                        best_idx = event_data['Result_numeric'].idxmin()
                    else:
                        best_idx = event_data['Result_numeric'].idxmax()
                    best_row = last_3_years.loc[best_idx]
                    st.markdown(f"• {event_name}: **{best_row.get('Result','N/A')}**")

        # === WA POINTS SECTION ===
        st.markdown("---")
        st.markdown("### World Athletics Points")

        if 'wapoints' in last_3_years.columns:
            wapoints_numeric = pd.to_numeric(last_3_years['wapoints'], errors='coerce')
            valid_wapoints = wapoints_numeric.dropna()

            if len(valid_wapoints) > 0:
                col_wa1, col_wa2, col_wa3, col_wa4 = st.columns(4)

                with col_wa1:
                    current_wapoints = valid_wapoints.iloc[-1] if len(valid_wapoints) > 0 else 0
                    st.metric("Current WA Points", f"{current_wapoints:.0f}")

                with col_wa2:
                    avg_wapoints = valid_wapoints.mean()
                    st.metric("Average (3yr)", f"{avg_wapoints:.0f}")

                with col_wa3:
                    max_wapoints = valid_wapoints.max()
                    st.metric("Best WA Points", f"{max_wapoints:.0f}")

                with col_wa4:
                    # Trend (compare first half to second half)
                    if len(valid_wapoints) >= 4:
                        first_half = valid_wapoints.iloc[:len(valid_wapoints)//2].mean()
                        second_half = valid_wapoints.iloc[len(valid_wapoints)//2:].mean()
                        trend = second_half - first_half
                        trend_str = f"+{trend:.0f}" if trend > 0 else f"{trend:.0f}"
                        st.metric("Trend", trend_str, delta=trend_str)
                    else:
                        st.metric("Trend", "N/A")

                # WA Points by Event
                if 'Event' in last_3_years.columns:
                    st.markdown("**WA Points by Event:**")
                    wa_by_event = last_3_years.groupby('Event').agg({
                        'wapoints': ['mean', 'max', 'count']
                    }).round(0)
                    wa_by_event.columns = ['Avg Points', 'Best Points', 'Count']
                    wa_by_event = wa_by_event.sort_values('Best Points', ascending=False)
                    st.dataframe(style_dark_df(ensure_json_safe(wa_by_event.reset_index())), height=150)
            else:
                st.info("No WA Points data available for this athlete.")
        else:
            st.info("WA Points column not available in dataset.")

        st.markdown("---")
        st.markdown("### Notable Performances (Last 3 Years)")
        recent = last_3_years.copy()
        if 'Result_numeric' in recent.columns and 'Event' in recent.columns:
            # Sort by best performance per event type
            def get_sort_key(row):
                ev_type = get_event_type(row['Event'])
                # For time events, lower is better; for distance/points, higher is better
                # We'll return a value where lower is always better for sorting
                if ev_type == 'time':
                    return row['Result_numeric'] if pd.notna(row['Result_numeric']) else float('inf')
                else:
                    return -row['Result_numeric'] if pd.notna(row['Result_numeric']) else float('inf')
            recent['_sort_key'] = recent.apply(get_sort_key, axis=1)
            recent = recent.sort_values('_sort_key')
            recent = recent.drop(columns=['_sort_key'])
            # Mark best per event
            recent['Highlight'] = ''
            for ev in recent['Event'].dropna().unique():
                ev_mask = recent['Event'] == ev
                ev_type = get_event_type(ev)
                if ev_type == 'time':
                    best_val = recent.loc[ev_mask, 'Result_numeric'].min()
                else:
                    best_val = recent.loc[ev_mask, 'Result_numeric'].max()
                best_mask = ev_mask & (recent['Result_numeric'] == best_val)
                recent.loc[best_mask, 'Highlight'] = '🏅'
        if 'Position' in recent.columns:
            recent['Medal'] = recent['Position'].apply(position_medal)
        # Include wapoints and wind in display
        show_cols = ['Result', 'Event', 'Competition', 'Competition_ID', 'Stadium', 'Start_Date', 'Round', 'Position', 'Medal', 'Age', 'wapoints', 'wind', 'Highlight']
        st.dataframe(style_dark_df(ensure_json_safe(recent[[c for c in show_cols if c in recent.columns]].head(5))))
        st.markdown("### Performance Progression Chart (with Qualification Standards)")

        # Get athlete gender for qualification standards
        athlete_gender = last_3_years['Gender'].iloc[0] if 'Gender' in last_3_years.columns and not last_3_years.empty else 'Men'

        if 'Result_numeric' in last_3_years.columns and 'Event' in last_3_years.columns:
            for ev_ in last_3_years['Event'].dropna().unique():
                sub_ev = last_3_years[(last_3_years['Event'] == ev_) & last_3_years['Result_numeric'].notna()].copy()
                if sub_ev.empty:
                    continue
                # Ensure Round is string type for tooltip
                if 'Round' in sub_ev.columns:
                    sub_ev['Round'] = sub_ev['Round'].astype(str).replace('nan', '')

                # Remove outliers
                q1 = sub_ev['Result_numeric'].quantile(0.25)
                q3 = sub_ev['Result_numeric'].quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                sub_ev_filtered = sub_ev[(sub_ev['Result_numeric'] >= lower) & (sub_ev['Result_numeric'] <= upper)].copy()
                if sub_ev_filtered.empty:
                    continue

                if 'Round' in sub_ev_filtered.columns:
                    sub_ev_filtered['Round'] = sub_ev_filtered['Round'].astype(str).replace('nan', '')

                y_min = sub_ev_filtered['Result_numeric'].min()
                y_max = sub_ev_filtered['Result_numeric'].max()

                # Get qualification standards for this event
                qual_std = get_qualification_standard(ev_, athlete_gender)
                benchmark_lines = []

                if qual_std:
                    olympic_std = qual_std.get('olympic')
                    world_std = qual_std.get('world')

                    # Adjust y-axis range to include standards if they're close
                    if olympic_std:
                        y_min = min(y_min, olympic_std * 0.98)
                        y_max = max(y_max, olympic_std * 1.02)
                    if world_std:
                        y_min = min(y_min, world_std * 0.98)
                        y_max = max(y_max, world_std * 1.02)

                y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1
                y_axis = alt.Y('Result_numeric:Q', title='Performance', scale=alt.Scale(domain=[y_min - y_pad, y_max + y_pad]))

                # Build tooltip list
                tooltip_cols = ['Start_Date:T', 'Event:N', 'Result:N', 'Competition:N']
                if 'Round' in sub_ev_filtered.columns and sub_ev_filtered['Round'].str.strip().str.len().gt(0).any():
                    tooltip_cols.append('Round:N')
                if 'wapoints' in sub_ev_filtered.columns:
                    tooltip_cols.append('wapoints:Q')

                # Create main performance line
                perf_line = alt.Chart(sub_ev_filtered).mark_line(
                    interpolate='monotone',
                    point=alt.OverlayMarkDef(filled=True, size=60)
                ).encode(
                    x=alt.X('Start_Date:T', title='Date'),
                    y=y_axis,
                    tooltip=tooltip_cols,
                    color=alt.value('#00FF7F')
                )

                # Create benchmark lines
                layers = [perf_line]

                if qual_std:
                    olympic_std = qual_std.get('olympic')
                    world_std = qual_std.get('world')

                    # Olympic standard line (gold)
                    if olympic_std:
                        olympic_line = alt.Chart(pd.DataFrame({'y': [olympic_std]})).mark_rule(
                            color='gold',
                            strokeWidth=2,
                            strokeDash=[5, 5]
                        ).encode(y='y:Q')
                        layers.append(olympic_line)

                        # Label for Olympic standard
                        olympic_label = alt.Chart(pd.DataFrame({
                            'y': [olympic_std],
                            'text': [f'Olympic: {olympic_std}']
                        })).mark_text(
                            align='right',
                            dx=-5,
                            dy=-5,
                            color='gold',
                            fontSize=10
                        ).encode(
                            y='y:Q',
                            text='text:N'
                        )
                        layers.append(olympic_label)

                    # World Championship standard line (silver)
                    if world_std and world_std != olympic_std:
                        world_line = alt.Chart(pd.DataFrame({'y': [world_std]})).mark_rule(
                            color='silver',
                            strokeWidth=2,
                            strokeDash=[3, 3]
                        ).encode(y='y:Q')
                        layers.append(world_line)

                        world_label = alt.Chart(pd.DataFrame({
                            'y': [world_std],
                            'text': [f'World: {world_std}']
                        })).mark_text(
                            align='right',
                            dx=-5,
                            dy=-5,
                            color='silver',
                            fontSize=10
                        ).encode(
                            y='y:Q',
                            text='text:N'
                        )
                        layers.append(world_label)

                # Combine all layers
                chart = alt.layer(*layers).properties(
                    title=f"{ev_} Progression vs Qualification Standards",
                    width=800,
                    height=350
                ).configure_axis(
                    labelColor='white',
                    titleColor='white',
                    labelFontSize=12,
                    titleFontSize=14,
                    gridColor='gray',
                    domainColor='white'
                ).configure_view(
                    strokeWidth=0,
                    fill='black'
                ).configure_title(
                    color='white',
                    fontSize=16
                )
                st.altair_chart(chart, width='stretch')

                # Show distance to qualification
                if qual_std:
                    best_result = sub_ev_filtered['Result_numeric'].min() if get_event_type(ev_) == 'time' else sub_ev_filtered['Result_numeric'].max()
                    ev_type = get_event_type(ev_)

                    col_q1, col_q2 = st.columns(2)
                    with col_q1:
                        if qual_std.get('olympic'):
                            if ev_type == 'time':
                                diff = best_result - qual_std['olympic']
                                status = "QUALIFIED" if diff <= 0 else f"{diff:.2f}s to go"
                            else:
                                diff = qual_std['olympic'] - best_result
                                status = "QUALIFIED" if diff <= 0 else f"{abs(diff):.2f}m to go"
                            color = "green" if "QUALIFIED" in status else "orange"
                            st.markdown(f"**Olympic Standard:** {status}")
                    with col_q2:
                        if qual_std.get('world'):
                            if ev_type == 'time':
                                diff = best_result - qual_std['world']
                                status = "QUALIFIED" if diff <= 0 else f"{diff:.2f}s to go"
                            else:
                                diff = qual_std['world'] - best_result
                                status = "QUALIFIED" if diff <= 0 else f"{abs(diff):.2f}m to go"
                            st.markdown(f"**World Champs Standard:** {status}")
        st.markdown("### 🗕️ Current Season Results")
        if 'Year' in grouped.columns:
            cyr = datetime.datetime.now().year
            cseason = grouped[grouped['Year'] == cyr].sort_values('Start_Date', ascending=False)
            if cseason.empty:
                st.warning("No results found for the current season.")
            else:
                # Mark season best per event (considering event type)
                cseason['Season_Best'] = ''
                for ev in cseason['Event'].dropna().unique():
                    ev_mask = cseason['Event'] == ev
                    ev_type = get_event_type(ev)
                    if ev_type == 'time':
                        best_val = cseason.loc[ev_mask, 'Result_numeric'].min()
                    else:
                        best_val = cseason.loc[ev_mask, 'Result_numeric'].max()
                    best_mask = ev_mask & (cseason['Result_numeric'] == best_val)
                    cseason.loc[best_mask, 'Season_Best'] = '🌟'
                show_cols2 = ['Start_Date', 'Event', 'Result', 'Season_Best', 'Competition', 'Round', 'Position']
                st.dataframe(style_dark_df(ensure_json_safe(cseason[[c for c in show_cols2 if c in cseason.columns]])))
        def recent_avg(dfx, year_):
            sub_df = dfx[dfx['Year'] == year_].sort_values('Start_Date', ascending=False)
            avg_ = sub_df['Result_numeric'].mean()
            # Mark season best per event (considering event type)
            sub_df['Season_Best'] = ''
            for ev in sub_df['Event'].dropna().unique():
                ev_mask = sub_df['Event'] == ev
                ev_type = get_event_type(ev)
                if ev_type == 'time':
                    best_val = sub_df.loc[ev_mask, 'Result_numeric'].min()
                else:
                    best_val = sub_df.loc[ev_mask, 'Result_numeric'].max()
                best_mask = ev_mask & (sub_df['Result_numeric'] == best_val)
                sub_df.loc[best_mask, 'Season_Best'] = '🌟'
            return sub_df, avg_
        st.markdown("### Seasonal Averages (Last 3 Results)")
        if 'Year' in grouped.columns:
            cyr = datetime.datetime.now().year
            this_season_df, this_avg = recent_avg(grouped, cyr)
            last_season_df, last_avg = recent_avg(grouped, cyr - 1)
            if len(this_season_df) < 3:
                st.info("🔄 Early season: fewer than 3 results.")
            if not this_season_df.empty:
                valid_cnt = this_season_df['Result_numeric'].notna().sum()
                if valid_cnt == 0:
                    st.warning("📬 This season has results, but none numeric for averaging.")
                elif np.isnan(this_avg):
                    st.markdown("**This Season Avg:** Not available (missing numeric results)")
                else:
                    st.markdown(f"**This Season Avg (Last 3):** {this_avg:.2f}")
            else:
                st.markdown("No data for this season")
            st.dataframe(style_dark_df(ensure_json_safe(
                this_season_df[[c for c in ['Start_Date', 'Event', 'Result', 'Season_Best', 'Competition'] if c in this_season_df.columns]]
            )))
            if not np.isnan(last_avg):
                st.markdown(f"**Last Season Avg (Last 3):** {last_avg:.2f}")
            else:
                st.markdown("No data for last season")
            st.dataframe(style_dark_df(ensure_json_safe(
                last_season_df[[c for c in ['Start_Date', 'Event', 'Result', 'Season_Best', 'Competition'] if c in last_season_df.columns]]
            )))
        st.markdown("### Top Results")
        if 'Result_numeric' in grouped.columns and 'Event' in grouped.columns:
            # Get top 10 results per event, considering event type
            top_results = []
            for ev in grouped['Event'].dropna().unique():
                ev_data = grouped[grouped['Event'] == ev].dropna(subset=['Result_numeric']).copy()
                ev_type = get_event_type(ev)
                ascending = (ev_type == 'time')
                ev_top = ev_data.sort_values('Result_numeric', ascending=ascending).head(10)
                # Mark PB per event
                if not ev_top.empty:
                    if ev_type == 'time':
                        best_val = ev_top['Result_numeric'].min()
                    else:
                        best_val = ev_top['Result_numeric'].max()
                    ev_top['PB'] = (ev_top['Result_numeric'] == best_val).apply(lambda x: '🏅' if x else '')
                top_results.append(ev_top)
            if top_results:
                top10 = pd.concat(top_results, ignore_index=True)
            else:
                top10 = grouped.dropna(subset=['Result_numeric']).head(10)
                top10['PB'] = ''
            if 'Position' in top10.columns:
                top10['Medal'] = top10['Position'].apply(position_medal)
            # Include wapoints, wind, and wind-assisted flag
            cshow = ['Result', 'wapoints', 'wind', 'Is_Wind_Assisted', 'Is_Hand_Timed', 'Is_Altitude', 'PB', 'Competition', 'Competition_ID', 'Stadium', 'Round', 'Position', 'Medal', 'Age', 'Start_Date']
            st.dataframe(style_dark_df(ensure_json_safe(
                top10[[c for c in cshow if c in top10.columns]]
            )))

###################################
# 7) Athlete Profiles Container
###################################
def show_athlete_profiles(filtered_df, db_label):
    st.subheader(f"{db_label}: Athlete Profiles")
    if 'Athlete_Name' not in filtered_df.columns:
        st.warning("No 'Athlete_Name' column in data.")
        return
    names_ = [n.strip() for n in filtered_df['Athlete_Name'].dropna().unique()]
    default_name = ["Abdulaziz Abdou Atafi"] if "Abdulaziz Abdou Atafi" in names_ else names_[:1]
    chosen_names = st.multiselect(
    f"{db_label} Athlete(s)",
    names_,
    default=default_name,
    key=f"{db_label}_athlete"
)

    for athlete_name in chosen_names:
        profile = filtered_df[filtered_df['Athlete_Name'] == athlete_name]
        if profile.empty:
            continue
        show_single_athlete_profile(profile, db_label)

###################################
# 8) Qualification Stage
###################################
def get_flag(country_code):
    if not isinstance(country_code, str) or len(country_code) != 3:
        return ""
    offset = 127397
    try:
        return ''.join([chr(ord(c.upper()) + offset) for c in country_code[:2]])
    except:
        return ""

def show_qualification_stage(df):
    st.subheader("Qualification Stage")

    # Ensure Round column exists and is properly formatted
    if 'Round' not in df.columns:
        st.info("No Round column available for qualification analysis.")
        return

    # Convert Round to string and clean up
    df = df.copy()
    df['Round'] = df['Round'].astype(str).replace('nan', 'Final').str.strip()
    df = df[~df['Round'].isin(["None", "", "nan", "NaN", "null"])]

    if df.empty:
        st.info("No round data available after filtering.")
        return

    round_clean_map = {
        "Preliminary round": "Prelims",
        "Preliminary": "Prelims",
        "Qualification": "Heats",
        "Qualifying": "Heats",
        "Heats": "Heats",
        "Heat 1": "Heats", "Heat 2": "Heats", "Heat 3": "Heats", "Heat 4": "Heats",
        "Heat 5": "Heats", "Heat 6": "Heats", "Heat 7": "Heats", "Heat 8": "Heats",
        "Semi 1": "SF", "Semi 2": "SF", "Semi 3": "SF",
        "Quarterfinals": "QF",
        "Semifinals": "SF",
        "Final": "Final",
        "F": "Final",
        "f": "Final"
    }
    df['Round'] = df['Round'].replace(round_clean_map)

    # Relay fallback for missing names
    if 'Athlete_Name' in df.columns and 'Athlete_Country' in df.columns:
        df['Athlete_Name'] = df.apply(
            lambda row: row['Athlete_Name'] if pd.notna(row['Athlete_Name']) and row['Athlete_Name'].strip() != '' else row.get('Athlete_Country', 'Team'),
            axis=1
        )

    if 'Athlete_Country' in df.columns:
        df['Country_Flag'] = df['Athlete_Country'].apply(get_flag)
        df['Athlete_Country'] = df['Country_Flag'] + ' ' + df['Athlete_Country']

    def remove_outliers(df_inner, field='Result_numeric'):
        q1 = df_inner[field].quantile(0.25)
        q3 = df_inner[field].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return df_inner[(df_inner[field] >= lower) & (df_inner[field] <= upper)]

    if {'Round', 'Result_numeric', 'Year'}.issubset(df.columns):
        df_valid = df[df['Result_numeric'].notna()].copy()
        if df_valid.empty:
            st.info("No valid numeric qualification data available.")
            return

        df_filtered = remove_outliers(df_valid)
        if df_filtered.empty:
            st.info("Outlier removal removed all rows; using all valid data instead.")
            df_filtered = df_valid

        round_year_stats = df_filtered.groupby(['Round', 'Year'], as_index=False).agg({
            'Result_numeric': ['mean', 'min', 'max']
        })
        round_year_stats.columns = ['Round', 'Year', 'Avg', 'Min', 'Max']

        is_relay = False
        if 'Event' in df_filtered.columns and not df_filtered.empty:
            is_relay = df_filtered['Event'].str.lower().str.contains('relay').any()

        if not is_relay:
            def get_qualifier_stats(subdf):
                sorted_ = subdf.sort_values('Result_numeric').dropna(subset=['Result_numeric'])
                fastest_q = sorted_['Result_numeric'].iloc[1] if len(sorted_) > 1 else np.nan
                slowest_q = sorted_['Result_numeric'].iloc[7] if len(sorted_) > 7 else np.nan
                return pd.Series({'Fastest_Q': fastest_q, 'Slowest_Q': slowest_q})
            qualifier_stats = df_filtered.groupby(['Round', 'Year'], as_index=False).apply(get_qualifier_stats, include_groups=False).reset_index(drop=True)
            full_stats = pd.merge(round_year_stats, qualifier_stats, on=['Round', 'Year'], how='outer')
        else:
            st.info("Relay event detected; skipping qualifier stats aggregation.")
            full_stats = round_year_stats.copy()

        st.markdown("**Min / Avg / Max / Fastest Q / Slowest Q by Round & Year**")
        st.dataframe(style_dark_df(ensure_json_safe(full_stats)))

        melted = full_stats.melt(id_vars=['Round', 'Year'], var_name='Metric', value_name='Value')
        custom_order = ["Prelims", "Heats", "QF", "SF", "Final"]
        melted['Round'] = pd.Categorical(melted['Round'], categories=custom_order, ordered=True)

        qualifier_lines = ['Fastest_Q', 'Slowest_Q']
        y_min = melted['Value'].min(skipna=True)
        y_max = melted['Value'].max(skipna=True)

        if math.isnan(y_min) or math.isnan(y_max):
            st.info("Insufficient numeric data available for charting qualification performance.")
        else:
            y_padding = (y_max - y_min) * 0.1 if y_max > y_min else 1
            y_axis = alt.Y('Value:Q', title='Performance', scale=alt.Scale(domain=[y_min - y_padding, y_max + y_padding]))

            chart = alt.Chart(melted).mark_line(
                interpolate='monotone',
                point=alt.OverlayMarkDef(filled=True, size=60)
            ).encode(
                x=alt.X('Year:O', title='Year'),
                y=y_axis,
                color=alt.Color('Round:N', sort=custom_order, scale=alt.Scale(scheme='dark2')),
                strokeDash=alt.condition(
                    alt.FieldOneOfPredicate(field='Metric', oneOf=qualifier_lines),
                    alt.value([4, 4]),
                    alt.value([1])
                ),
                tooltip=['Year:O', 'Round:N', 'Metric:N', 'Value:Q']
            ).properties(
                width=220,
                height=250
            ).facet(
                facet='Metric:N',
                columns=3
            ).resolve_scale(y='shared').configure_axis(
                labelColor='white',
                titleColor='white',
                labelFontSize=11,
                titleFontSize=13,
                gridColor='gray'
            ).configure_view(
                strokeWidth=0,
                fill='black'
            ).configure_title(
                color='white',
                fontSize=16
            )
            st.markdown("### Rounds Over Years (Min/Avg/Max + Qualifier Lines)")
            st.altair_chart(chart, width='stretch')
    else:
        st.info("Need 'Round', 'Result_numeric', 'Year' columns for progression chart.")
        st.dataframe(style_dark_df(ensure_json_safe(df.head(10))))
        return

    st.markdown("### Inferred Qualification Flags (Top 2 from Heats)")
    if {'Heat', 'Event', 'Result_numeric', 'Round'}.issubset(df.columns):
        q_df = df[df['Round'].isin(['Heats', 'SF'])].copy()
        is_relay_event = q_df['Event'].str.contains('Relay', na=False)

        if q_df.empty or is_relay_event.all() or 'Heat' not in q_df.columns:
            st.info("Skipping top 2 qualification logic for relays or incomplete data.")
            return

        q_df['Qual'] = ""
        def mark_top_2(grp):
            ev = grp['Event'].iloc[0]
            ev_clean = ev.strip().replace("Indoor", "").strip()
            ev_type = event_type_map.get(ev, event_type_map.get(ev_clean, 'time'))
            ascending = ev_type == 'time'
            sorted_grp = grp.sort_values('Result_numeric', ascending=ascending)
            sorted_grp['Qual'] = ['Q' if i < 2 else '' for i in range(len(sorted_grp))]
            return sorted_grp

        # Note: include_groups=True needed here since mark_top_2 uses 'Event' column
        top_2 = q_df.groupby(['Event', 'Round', 'Heat'], group_keys=False).apply(mark_top_2).reset_index(drop=True)
        top2_mask = top_2['Qual'] == 'Q'
        rest = top_2[~top2_mask]
        lanes_needed = 8
        fill_count = lanes_needed - top2_mask.sum()
        fastest_fill = rest.sort_values('Result_numeric', ascending=True).head(fill_count)
        top_2.loc[fastest_fill.index, 'Qual'] = 'q'

        show_cols = ['Qual', 'Athlete_Name', 'Athlete_Country', 'Event', 'Round', 'Heat', 'Result', 'Result_numeric', 'Competition']
        st.dataframe(style_dark_df(ensure_json_safe(top_2[[c for c in show_cols if c in top_2.columns]])))
    else:
        st.info("Insufficient columns to display inferred qualification flags.")


###################################
# 9) Final Performances
###################################
def show_final_performances(df):
    st.subheader("Final Performances")
    df = df.copy()
    if 'Round' in df.columns:
        df['Round'] = df['Round'].astype(str).replace({'nan': 'Final', 'F': 'Final', 'f': 'Final', 'None': 'Final', '': 'Final'}).str.strip()
        df = df[df['Round'] == "Final"]
    if 'Position' not in df.columns or 'Result_numeric' not in df.columns:
        st.info("Need 'Position' & 'Result_numeric' for final performances.")
        st.dataframe(style_dark_df(ensure_json_safe(df.head(10))))
        return
    def medal_emoji(pos):
        if pd.isna(pos):
            return ""
        try:
            pos = int(pos)
            if pos == 1:
                return "🥇"
            elif pos == 2:
                return "🥈"
            elif pos == 3:
                return "🥉"
        except:
            return ""
        return ""
    df = df.copy()
    df['Medal'] = df['Position'].apply(medal_emoji)
    if 'Athlete_Country' in df.columns:
        df['Country_Flag'] = df['Athlete_Country'].apply(get_flag)
        df['Athlete_Country'] = df['Country_Flag'] + ' ' + df['Athlete_Country']
    final_12 = df[df['Position'].between(1, 12, inclusive='both')].copy()
    st.write("Final round preview (before year conversion):", 
             final_12[['Event', 'Start_Date', 'Result', 'Result_numeric']].head(10))
    if final_12.empty:
        st.info("No final round results in positions 1–12.")
        return
    relay_events = ['4x100m Relay', '4x400m Relay', '4x400m Mixed Relay']
    current_event = final_12['Event'].iloc[0] if 'Event' in final_12.columns else None
    if current_event in relay_events:
        st.info("Relay event detected. Displaying results without outlier removal.")
        top8_filtered = final_12[final_12['Result_numeric'].notna()].copy()
    else:
        def remove_outliers(df_inner, field='Result_numeric'):
            q1 = df_inner[field].quantile(0.25)
            q3 = df_inner[field].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            return df_inner[(df_inner[field] >= lower) & (df_inner[field] <= upper)]
        top8 = final_12[final_12['Position'] <= 8]
        top8_filtered = top8[top8['Result_numeric'].notna()].copy()
        top8_filtered = remove_outliers(top8_filtered)
        removed_outliers = top8[~top8.index.isin(top8_filtered.index)]
        if not removed_outliers.empty:
            with st.expander("📛 Removed Outliers (IQR method)", expanded=False):
                st.dataframe(style_dark_df(ensure_json_safe(
                    removed_outliers[['Event', 'Year', 'Result', 'Result_numeric']]
                )))
    import math
    if 'Year' not in top8_filtered.columns:
        if 'Start_Date' in top8_filtered.columns:
            top8_filtered['Year'] = pd.to_datetime(top8_filtered['Start_Date'], errors='coerce').dt.year
        else:
            st.info("No 'Year' or 'Start_Date' column available; cannot chart Final round top 8.")
            return
    if top8_filtered['Year'].isnull().all():
        st.info("Final round top 8 data do not contain valid year information. Attempting fallback extraction from 'Competition'.")
        def fallback_year(row):
            competition = row['Competition'] if 'Competition' in row and pd.notnull(row['Competition']) else ''
            match = re.search(r'(\d{4})', competition)
            if match:
                return int(match.group(1))
            return None
        top8_filtered = top8_filtered.reset_index(drop=True)
        fallback_series = top8_filtered.apply(lambda row: fallback_year(row), axis=1)
        top8_filtered['Year'] = fallback_series
        st.write("After fallback extraction, final round preview:", 
                 top8_filtered[['Event', 'Start_Date', 'Year', 'Result_numeric']].head(10))
        if top8_filtered['Year'].isnull().all():
            st.info("Fallback extraction did not yield any valid year values. Setting default year of 2021.")
            top8_filtered['Year'] = 2021
    st.write("Final round top 8 data preview:", top8_filtered[['Event', 'Start_Date', 'Year', 'Result_numeric']].head(10))
    if 'Year' in top8_filtered.columns and not top8_filtered.empty:
        y_min = top8_filtered['Result_numeric'].min()
        y_max = top8_filtered['Result_numeric'].max()
        if math.isnan(y_min) or math.isnan(y_max):
            st.info("Insufficient numeric data available for charting performance.")
        else:
            y_padding = (y_max - y_min) * 0.1 if y_max > y_min else 1
            y_axis = alt.Y(
                'Result_numeric:Q',
                title='Performance',
                scale=alt.Scale(domain=[y_min - y_padding, y_max + y_padding])
            )
            chart = alt.Chart(top8_filtered).mark_line(
                interpolate='monotone',
                point=alt.OverlayMarkDef(filled=True, size=60)
            ).encode(
                x=alt.X('Year:O', title='Year'),
                y=y_axis,
                color=alt.Color('Position:N', scale=alt.Scale(scheme='tableau10')),
                tooltip=['Year', 'Position', 'Medal', 'Athlete_Name', 'Athlete_Country', 'Event', 'Result', 'Competition']
            ).properties(
                title="Top 8 Finalists Over Years",
                width=800,
                height=400
            ).configure_axis(
                labelColor='white',
                titleColor='white',
                labelFontSize=12,
                titleFontSize=14,
                gridColor='gray',
                domainColor='white'
            ).configure_view(
                strokeWidth=0,
                fill='black'
            ).configure_title(
                color='white',
                fontSize=18
            )
            st.altair_chart(chart, width='stretch')
    else:
        st.info("No 'Year' column or data available for charting Final round top 8.")
###################################
# 9) Relay Chart
###################################

def show_relay_charts(df):
    st.subheader("Relay Event Analysis")

    # Normalize relay names
    df = normalize_relay_events(df)

    # Filter for relay events only
    relay_df = df[df['Event'].str.contains('relay', case=False, na=False)].copy()
    if relay_df.empty:
        st.info("No relay event data found.")
        return

    # Normalize event column for filtering
    relay_df['Event_clean'] = relay_df['Event'].str.strip().str.lower()

    # Build clean master list
    relay_events_master = [e for e in event_type_map if 'relay' in e.lower()]
    relay_events_master_normalized = [e.lower() for e in relay_events_master]
    event_display_map = {e.lower(): e for e in relay_events_master}

    # Optional filters
    col1, col2, col3 = st.columns(3)
    with col1:
        gender_opts = sorted(relay_df['Gender'].dropna().unique())
        chosen_gender = st.selectbox("Gender", ["All"] + gender_opts, index=0, key="relay_gender")
        if chosen_gender != "All":
            relay_df = relay_df[relay_df['Gender'] == chosen_gender]

    with col2:
        chosen_events = st.multiselect(
            "Relay Events",
            relay_events_master,
            default=relay_events_master,
            key="relay_event_filter"
        )
        chosen_events_normalized = [e.lower() for e in chosen_events]
        relay_df = relay_df[relay_df['Event_clean'].isin(chosen_events_normalized)]

    with col3:
        year_opts = sorted(relay_df['Year'].dropna().unique())
        chosen_years = st.multiselect("Years", year_opts, default=year_opts, key="relay_year_filter")
        if chosen_years:
            relay_df = relay_df[relay_df['Year'].isin(chosen_years)]

    if relay_df.empty:
        st.warning("No data after applying filters.")
        return

    # Re-map event names to display-friendly format
    relay_df['Event'] = relay_df['Event_clean'].map(event_display_map).fillna(relay_df['Event'])

    # Drop missing or outlier results
    relay_df = relay_df[relay_df['Result_numeric'].notna()]
    q1 = relay_df['Result_numeric'].quantile(0.25)
    q3 = relay_df['Result_numeric'].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    relay_df = relay_df[(relay_df['Result_numeric'] >= lower) & (relay_df['Result_numeric'] <= upper)]

    # Relay progression faceted by country
    st.markdown("### 📈 Relay Progression by Country")
    base_chart = alt.Chart(relay_df).mark_line(
        interpolate='monotone',
        point=alt.OverlayMarkDef(filled=True, size=50)
    ).encode(
        x=alt.X('Year:O', title='Year'),
        y=alt.Y('Result_numeric:Q', title='Time (s)'),
        color=alt.Color('Event:N', title='Event'),
        tooltip=['Year', 'Event', 'Result', 'Athlete_Country', 'Competition']
    ).properties(
        width=250,
        height=200
    )

    line_chart = base_chart.facet(
        facet=alt.Facet('Athlete_Country:N', title='Country'),
        columns=3
    ).configure_axis(
        labelColor='white',
        titleColor='white',
        gridColor='gray'
    ).configure_view(
        strokeWidth=0,
        fill='black'
    ).configure_title(
        color='white'
    )

    st.altair_chart(line_chart, width='stretch')

    # Best results table
    st.markdown("### 🏅 Best Relay Performances per Country & Event")
    best_results = (
        relay_df.sort_values('Result_numeric')
        .groupby(['Athlete_Country', 'Event'], as_index=False)
        .first()
    )
    show_cols = ['Athlete_Country', 'Event', 'Result', 'Year', 'Competition']
    st.dataframe(style_dark_df(ensure_json_safe(best_results[show_cols])))


###################################
# 10) Text Report Generator
###################################
def generate_text_report(df, title="Athletics Rankings Report"):
    """Generate a formatted text report similar to Islamic_Arab_Athletics example."""
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append(title.upper())
    report_lines.append("=" * 70)
    report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Dataset entries for analysis: {len(df):,}")
    report_lines.append("")

    if df.empty:
        report_lines.append("No data available for the selected filters.")
        return "\n".join(report_lines)

    # Group by Gender
    for gender in ['Men', 'Women']:
        gender_df = df[df['Gender'] == gender] if 'Gender' in df.columns else df
        if gender_df.empty:
            continue

        report_lines.append("")
        report_lines.append("=" * 70)
        report_lines.append(f"                          {gender.upper()}'S EVENTS")
        report_lines.append("=" * 70)
        report_lines.append("")

        # Get unique events
        if 'Event' not in gender_df.columns:
            continue

        events = sorted(gender_df['Event'].dropna().unique())

        for event in events:
            event_df = gender_df[gender_df['Event'] == event].copy()
            if event_df.empty or 'Result_numeric' not in event_df.columns:
                continue

            # Remove invalid results
            event_df = event_df[event_df['Result_numeric'].notna()]
            if event_df.empty:
                continue

            # Determine sort order (ascending for time events, descending for distance/points)
            e_type = get_event_type(event)
            ascending = e_type == 'time'

            # Get top 20 by best performance
            top_performers = (
                event_df.sort_values('Result_numeric', ascending=ascending)
                .drop_duplicates(subset=['Athlete_Name'])  # One entry per athlete
                .head(20)
            )

            if top_performers.empty:
                continue

            report_lines.append(f"=== TOP 20 PERFORMERS: {gender}'s {event} ===")
            report_lines.append(f"{'Rank':<6}{'Athlete':<35}{'Nation':<8}{'Performance':<13}{'Date':<12}")
            report_lines.append("-" * 75)

            for rank, (_, row) in enumerate(top_performers.iterrows(), 1):
                athlete = str(row.get('Athlete_Name', 'Unknown'))[:33]
                nation = str(row.get('Athlete_CountryCode', row.get('Athlete_Country', 'N/A')))[:6]
                result = str(row.get('Result', 'N/A'))[:11]
                date = ""
                if pd.notna(row.get('Start_Date')):
                    try:
                        date = row['Start_Date'].strftime('%Y-%m-%d') if hasattr(row['Start_Date'], 'strftime') else str(row['Start_Date'])[:10]
                    except:
                        date = str(row.get('Start_Date', ''))[:10]

                report_lines.append(f"{rank:<6}{athlete:<35}{nation:<8}{result:<13}{date:<12}")

            report_lines.append("")
            report_lines.append("")

    return "\n".join(report_lines)


def show_text_report_page(df_all):
    """Show the text report generation page."""
    st.title("Text Report Generator")
    st.markdown("Generate formatted text rankings reports similar to competition analysis reports.")

    df = df_all.copy()

    st.header("Report Filters")

    col1, col2 = st.columns(2)

    with col1:
        # Date range selector
        st.subheader("Date Range")
        if 'Start_Date' in df.columns and df['Start_Date'].notna().any():
            min_date = df['Start_Date'].min()
            max_date = df['Start_Date'].max()
            if pd.notna(min_date) and pd.notna(max_date):
                date_range = st.date_input(
                    "Select Date Range",
                    value=(min_date.date(), max_date.date()),
                    min_value=min_date.date(),
                    max_value=max_date.date(),
                    key="report_date_range"
                )
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    df = df[(df['Start_Date'].dt.date >= start_date) & (df['Start_Date'].dt.date <= end_date)]

    with col2:
        # Gender filter
        if 'Gender' in df.columns:
            gender_options = ["All"] + sorted(df['Gender'].dropna().unique().tolist())
            chosen_gender = st.selectbox("Gender", gender_options, key="report_gender")
            if chosen_gender != "All":
                df = df[df['Gender'] == chosen_gender]

    # Competition selector
    st.subheader("Competition Filter")
    comp_filter_type = st.radio("Filter by:", ["All Competitions", "Major Championships", "Specific Competition"], horizontal=True, key="report_comp_type")

    if comp_filter_type == "Major Championships":
        comp_names = sorted(MAJOR_COMPETITIONS_CID.keys())
        chosen_comp = st.selectbox("Championship", comp_names, key="report_champ_name")
        if chosen_comp:
            edition_years = sorted(MAJOR_COMPETITIONS_CID[chosen_comp].keys(), reverse=True)
            chosen_editions = st.multiselect("Edition Year(s)", ["All"] + edition_years, default=["All"], key="report_champ_years")
            if "All" not in chosen_editions and chosen_editions:
                cids = [MAJOR_COMPETITIONS_CID[chosen_comp][y]["CID"] for y in chosen_editions]
                if "Competition_ID" in df.columns:
                    df['Competition_ID'] = df['Competition_ID'].astype(str)
                    df = df[df["Competition_ID"].isin(cids)]
            elif "All" in chosen_editions:
                cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[chosen_comp].values()]
                if "Competition_ID" in df.columns:
                    df['Competition_ID'] = df['Competition_ID'].astype(str)
                    df = df[df["Competition_ID"].isin(cids)]

    elif comp_filter_type == "Specific Competition":
        if 'Competition' in df.columns:
            comp_options = sorted(df['Competition'].dropna().unique().tolist())
            chosen_comps = st.multiselect("Select Competition(s)", comp_options, key="report_specific_comp")
            if chosen_comps:
                df = df[df['Competition'].isin(chosen_comps)]

    # Event filter
    st.subheader("Event Filter")
    if 'Event' in df.columns:
        event_options = sorted(df['Event'].dropna().unique().tolist())
        chosen_events = st.multiselect("Select Events (leave empty for all)", event_options, key="report_events")
        if chosen_events:
            df = df[df['Event'].isin(chosen_events)]

    # Country filter
    st.subheader("Country Filter")
    if 'Athlete_Country' in df.columns:
        country_options = sorted(df['Athlete_Country'].dropna().unique().tolist())
        chosen_countries = st.multiselect("Select Countries (leave empty for all)", country_options, key="report_countries")
        if chosen_countries:
            df = df[df['Athlete_Country'].isin(chosen_countries)]

    st.markdown("---")

    # Report title
    report_title = st.text_input("Report Title", value="Athletics Rankings Report", key="report_title")

    # Generate button
    if st.button("Generate Report", type="primary", key="generate_report"):
        with st.spinner("Generating report..."):
            report_text = generate_text_report(df, title=report_title)

        st.subheader("Generated Report")
        st.text_area("Report Preview", report_text, height=500, key="report_preview")

        # Download button
        st.download_button(
            label="Download Report (TXT)",
            data=report_text,
            file_name=f"{report_title.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            key="download_report"
        )

    # Show data summary
    st.markdown("---")
    st.subheader("Filtered Data Summary")
    st.markdown(f"**Records after filtering:** {len(df):,}")
    if 'Event' in df.columns:
        st.markdown(f"**Events:** {df['Event'].nunique()}")
    if 'Athlete_Name' in df.columns:
        st.markdown(f"**Athletes:** {df['Athlete_Name'].nunique()}")


###################################
# 11) Road to Championship - Championship Preparation Tab
###################################

# Upcoming major championships for Road To tabs
UPCOMING_CHAMPIONSHIPS = {
    "Asian Games": {
        "2026": {"name": "21st Asian Games", "city": "Nagoya", "country": "Japan", "dates": "Sep 2026"},
    },
    "Olympics": {
        "2028": {"name": "XXXIV Olympic Games", "city": "Los Angeles", "country": "USA", "dates": "Jul-Aug 2028"},
    },
    "World Championships": {
        "2025": {"name": "20th World Athletics Championships", "city": "Tokyo", "country": "Japan", "dates": "Sep 2025"},
    },
    "Asian Athletics Championships": {
        "2025": {"name": "26th Asian Athletics Championships", "city": "Gumi", "country": "South Korea", "dates": "May 2025"},
    }
}


def filter_fat_times_only(df):
    """
    Filter dataframe to only include FAT (Fully Automatic Timing) results.
    Hand times are not valid for predictions as they're ~0.24s slower.

    Optimized: Builds filter mask first, applies in single operation (no unnecessary copy).
    """
    # Build combined mask for FAT times
    mask = pd.Series(True, index=df.index)

    # Filter out hand-timed results if the column exists
    if 'Is_Hand_Timed' in df.columns:
        hand_timed_values = [True, 1, '1', 'Y', 'Yes', 'y', 'yes', 'TRUE', 'True', 'true', 'H', 'h']
        mask = mask & (~df['Is_Hand_Timed'].isin(hand_timed_values))

    # Also filter by result format - hand times often end without hundredths
    # Results with 'h' suffix are hand-timed
    if 'Result' in df.columns:
        mask = mask & (~df['Result'].astype(str).str.lower().str.endswith('h'))

    return df[mask]


@st.cache_data(ttl=3600, show_spinner=False)
def get_final_performance_by_place(_df, championship_type, gender, event, age_group="Senior", include_indoor=False, top_n=20):
    """
    Get historical final performances by finishing place (1st-N) across championships.
    Returns summary stats like Image 1 in Power BI - Final Summary by Place.
    Only uses FAT (Fully Automatic Timing) results - hand times excluded.

    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame (underscore prefix tells Streamlit not to hash it)
        top_n: Number of positions to include (default 20 for more comprehensive analysis)
    """
    # Get all competition IDs for this championship type
    if championship_type not in MAJOR_COMPETITIONS_CID:
        return pd.DataFrame()

    cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[championship_type].values()]

    # Include Indoor Championships if requested (for Olympic qualification)
    if include_indoor and "World Athletics Indoor Championships" in MAJOR_COMPETITIONS_CID:
        indoor_cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID["World Athletics Indoor Championships"].values()]
        cids = cids + indoor_cids

    # Filter data - use column filtering instead of full copy
    df_filtered = _df[_df['Competition_ID'].astype(str).isin(cids)].copy() if 'Competition_ID' in _df.columns else _df.copy()

    # IMPORTANT: Exclude hand-timed results for accurate predictions
    df_filtered = filter_fat_times_only(df_filtered)

    if 'Gender' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Gender'] == gender]

    if 'Event' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Event'] == event]

    # Filter for finals only
    if 'Round' in df_filtered.columns:
        final_terms = ['final', 'f', 'a final', 'final a', '', 'none']
        df_filtered = df_filtered[
            df_filtered['Round'].isna() |
            df_filtered['Round'].str.lower().str.strip().isin(final_terms)
        ]

    if df_filtered.empty:
        return pd.DataFrame()

    # Convert position to numeric
    df_filtered['Position_num'] = pd.to_numeric(df_filtered['Position'], errors='coerce')
    df_filtered = df_filtered[df_filtered['Position_num'].between(1, top_n)]

    # Check Result_numeric
    valid_results = df_filtered['Result_numeric'].notna().sum()
    if df_filtered.empty or valid_results == 0:
        return pd.DataFrame()

    # Group by position (rank) and calculate stats
    event_type = get_event_type(event)

    summary = df_filtered.groupby('Position_num').agg({
        'Result_numeric': ['mean', 'min', 'max', 'count']
    }).round(2)

    summary.columns = ['Average', 'Fastest' if event_type == 'time' else 'Best',
                       'Slowest' if event_type == 'time' else 'Worst', 'Count']
    summary = summary.reset_index()
    summary = summary.rename(columns={'Position_num': 'Rank'})

    return summary


@st.cache_data(ttl=3600, show_spinner=False)
def get_qualification_by_round(_df, championship_type, gender, event, include_indoor=False):
    """
    Get qualification performance by stage (Heats, Semi Finals, etc).
    Returns data like Image 2 - Qualification Type by Stage.
    Only uses FAT (Fully Automatic Timing) results - hand times excluded.

    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame (underscore prefix tells Streamlit not to hash it)
    """
    if championship_type not in MAJOR_COMPETITIONS_CID:
        return pd.DataFrame()

    cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[championship_type].values()]

    # Include Indoor Championships if requested (for Olympic qualification)
    if include_indoor and "World Athletics Indoor Championships" in MAJOR_COMPETITIONS_CID:
        indoor_cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID["World Athletics Indoor Championships"].values()]
        cids = cids + indoor_cids

    # Filter data - use column filtering instead of full copy
    df_filtered = _df[_df['Competition_ID'].astype(str).isin(cids)].copy() if 'Competition_ID' in _df.columns else _df.copy()

    # IMPORTANT: Exclude hand-timed results for accurate predictions
    df_filtered = filter_fat_times_only(df_filtered)

    if 'Gender' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Gender'] == gender]

    if 'Event' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Event'] == event]

    if df_filtered.empty or 'Round' not in df_filtered.columns:
        return pd.DataFrame()

    # Standardize round names using vectorized approach
    # Convert to string first to handle Categorical columns, then fillna
    round_lower = df_filtered['Round'].astype(str).replace('nan', '').str.lower().str.strip()

    # Direct mappings
    direct_map = {
        'heats': 'Heats', 'heat': 'Heats', 'h': 'Heats',
        'semi': 'Semi Finals', 'semi final': 'Semi Finals', 'sf': 'Semi Finals', 'semi-final': 'Semi Finals',
        'final': 'Final', 'f': 'Final', 'a final': 'Final', 'final a': 'Final',
        'qualification': 'Qualification', 'qual': 'Qualification', 'q': 'Qualification',
        '': 'Final', 'none': 'Final'
    }

    # Apply direct mappings first
    df_filtered['Round_std'] = round_lower.map(direct_map)

    # Apply pattern-based mappings for unmapped values
    unmapped_mask = df_filtered['Round_std'].isna()
    if unmapped_mask.any():
        unmapped_rounds = round_lower[unmapped_mask]
        # Heats pattern (h1, h2, h-1, etc.)
        heats_mask = unmapped_rounds.str.match(r'^h[\d\-]')
        # Semi Finals pattern (s1, s2, s-1, etc.)
        semi_mask = unmapped_rounds.str.match(r'^s[\d\-]')
        # Qualification pattern (q*)
        qual_mask = unmapped_rounds.str.startswith('q')
        # Repechage pattern (r* with 2+ chars)
        repechage_mask = unmapped_rounds.str.match(r'^r.+')

        df_filtered.loc[unmapped_mask & heats_mask.reindex(unmapped_mask.index, fill_value=False), 'Round_std'] = 'Heats'
        df_filtered.loc[unmapped_mask & semi_mask.reindex(unmapped_mask.index, fill_value=False), 'Round_std'] = 'Semi Finals'
        df_filtered.loc[unmapped_mask & qual_mask.reindex(unmapped_mask.index, fill_value=False), 'Round_std'] = 'Qualification'
        df_filtered.loc[unmapped_mask & repechage_mask.reindex(unmapped_mask.index, fill_value=False), 'Round_std'] = 'Repechage'

        # Fill remaining with title case
        still_unmapped = df_filtered['Round_std'].isna()
        df_filtered.loc[still_unmapped, 'Round_std'] = round_lower[still_unmapped].str.title()

    # Keep Heats, Semi Finals, and Qualification for analysis
    qual_rounds = ['Heats', 'Semi Finals', 'Qualification', 'Repechage']
    df_qual = df_filtered[df_filtered['Round_std'].isin(qual_rounds)]

    if df_qual.empty:
        return pd.DataFrame()

    summary = df_qual.groupby('Round_std').agg({
        'Result_numeric': ['mean', 'min', 'max', 'count']
    }).round(2)

    summary.columns = ['Average', 'Fastest', 'Slowest', 'Count']
    summary = summary.reset_index()
    summary = summary.rename(columns={'Round_std': 'Round'})

    return summary


@st.cache_data(ttl=3600, show_spinner=False)
def get_ksa_athletes_for_event(_df, gender, event, years_back=3):
    """
    Get KSA athletes competing in a specific event with their best results.
    Only uses FAT (Fully Automatic Timing) results - hand times excluded.

    CACHED: Results cached for 1 hour to improve performance.

    Optimized: Builds combined filter mask before any DataFrame operations.

    Args:
        _df: DataFrame (underscore prefix tells Streamlit not to hash it)
        years_back: Only include athletes active in the last N years (default 3)
                   Set to None for all-time results
    """
    df = _df  # Use local alias for cleaner code

    # Build combined filter mask (no copy until final result)
    mask = pd.Series(True, index=df.index)

    # Gender filter
    if 'Gender' in df.columns:
        mask = mask & (df['Gender'] == gender)

    # Event filter
    if 'Event' in df.columns:
        mask = mask & (df['Event'] == event)

    # KSA filter - check multiple possible column names
    ksa_mask = pd.Series(False, index=df.index)
    if 'Athlete_CountryCode' in df.columns:
        ksa_mask = ksa_mask | (df['Athlete_CountryCode'].astype(str).str.upper() == 'KSA')
    if 'Athlete_Country' in df.columns:
        ksa_mask = ksa_mask | (df['Athlete_Country'].astype(str).str.upper().isin(['KSA', 'SAUDI ARABIA']))
    if 'nationality' in df.columns:
        ksa_mask = ksa_mask | (df['nationality'].astype(str).str.upper() == 'KSA')
    mask = mask & ksa_mask

    # Date filter for recent years
    if years_back is not None and 'Start_Date' in df.columns:
        cutoff_date = pd.Timestamp.now() - pd.DateOffset(years=years_back)
        mask = mask & (df['Start_Date'] >= cutoff_date)

    # Apply filter and FAT times filter
    df_filtered = filter_fat_times_only(df[mask])

    if df_filtered.empty:
        return pd.DataFrame()

    # Filter out rows with missing Result_numeric or Athlete_Name
    df_filtered = df_filtered.dropna(subset=['Result_numeric', 'Athlete_Name'])

    if df_filtered.empty:
        return pd.DataFrame()

    event_type = get_event_type(event)
    ascending = (event_type == 'time')

    # Get best result per athlete using transform (copy here is necessary for modification)
    df_filtered = df_filtered.copy()
    if ascending:
        df_filtered['is_best'] = df_filtered.groupby('Athlete_Name')['Result_numeric'].transform('min') == df_filtered['Result_numeric']
    else:
        df_filtered['is_best'] = df_filtered.groupby('Athlete_Name')['Result_numeric'].transform('max') == df_filtered['Result_numeric']

    best_results = df_filtered[df_filtered['is_best']].drop_duplicates(subset=['Athlete_Name'])
    best_results = best_results.sort_values('Result_numeric', ascending=ascending)

    return best_results


def get_athlete_recent_form(df, athlete_name, event, num_races=3):
    """
    Get athlete's recent form: last N races, average, personal best, season best.
    Returns dict with form data.
    """
    df_filtered = df.copy()

    # Filter for this athlete and event
    if 'Athlete_Name' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Athlete_Name'] == athlete_name]

    if 'Event' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Event'] == event]

    if df_filtered.empty:
        return {
            'last_races': [],
            'average': None,
            'personal_best': None,
            'season_best': None,
            'race_count': 0,
            'trend': 'Unknown'
        }

    # Exclude hand times for accurate analysis
    df_filtered = filter_fat_times_only(df_filtered)

    # Sort by date (most recent first)
    if 'Competition_Date' in df_filtered.columns:
        df_filtered = df_filtered.sort_values('Competition_Date', ascending=False)
    elif 'Date' in df_filtered.columns:
        df_filtered = df_filtered.sort_values('Date', ascending=False)

    # Get recent races with valid results
    valid_results = df_filtered[df_filtered['Result_numeric'].notna()]
    recent_races = valid_results.head(num_races)

    # Extract results
    last_races = []
    for _, row in recent_races.iterrows():
        race_info = {
            'result': row.get('Result', 'N/A'),
            'result_numeric': row.get('Result_numeric'),
            'date': row.get('Competition_Date', row.get('Date', 'N/A')),
            'competition': row.get('Competition_Name', row.get('competition_name', 'N/A'))
        }
        last_races.append(race_info)

    # Calculate stats
    all_results = valid_results['Result_numeric'].tolist()
    event_type = get_event_type(event)

    if all_results:
        average = sum(all_results[:num_races]) / min(len(all_results), num_races) if all_results else None
        if event_type == 'time':
            personal_best = min(all_results)
        else:
            personal_best = max(all_results)
    else:
        average = None
        personal_best = None

    # Season best (current year)
    current_year = datetime.datetime.now().year
    if 'Competition_Date' in valid_results.columns or 'Date' in valid_results.columns:
        date_col = 'Competition_Date' if 'Competition_Date' in valid_results.columns else 'Date'
        try:
            valid_results_season = valid_results[pd.to_datetime(valid_results[date_col]).dt.year == current_year]
            if not valid_results_season.empty:
                season_results = valid_results_season['Result_numeric'].tolist()
                if event_type == 'time':
                    season_best = min(season_results)
                else:
                    season_best = max(season_results)
            else:
                season_best = None
        except:
            season_best = None
    else:
        season_best = None

    # Determine trend from last 3 races
    trend = 'Unknown'
    if len(last_races) >= 2:
        recent_results = [r['result_numeric'] for r in last_races if r['result_numeric'] is not None]
        if len(recent_results) >= 2:
            if event_type == 'time':
                # For time events, lower is better
                if recent_results[0] < recent_results[-1]:
                    trend = '📈 Improving'
                elif recent_results[0] > recent_results[-1]:
                    trend = '📉 Declining'
                else:
                    trend = '➡️ Stable'
            else:
                # For distance/points, higher is better
                if recent_results[0] > recent_results[-1]:
                    trend = '📈 Improving'
                elif recent_results[0] < recent_results[-1]:
                    trend = '📉 Declining'
                else:
                    trend = '➡️ Stable'

    return {
        'last_races': last_races,
        'average': average,
        'personal_best': personal_best,
        'season_best': season_best,
        'race_count': len(all_results),
        'trend': trend
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_batch_athlete_projections(_df, athlete_names, event, event_type):
    """
    Get projections for multiple athletes in a single pass.
    Much faster than calling project_performance in a loop.

    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame (underscore prefix tells Streamlit not to hash it)
        athlete_names: List of athlete names to project
        event: Event name
        event_type: 'time', 'distance', or 'points'

    Returns:
        Dict mapping athlete_name -> {projected, trend_symbol, form_score, performances}
    """
    df = _df

    # Pre-filter for event and FAT times once
    event_mask = df['Event'] == event if 'Event' in df.columns else pd.Series(True, index=df.index)
    df_event = filter_fat_times_only(df[event_mask])

    if df_event.empty or 'Athlete_Name' not in df_event.columns:
        return {name: {'projected': None, 'trend_symbol': '?', 'form_score': None, 'performances': []}
                for name in athlete_names}

    # Sort once by date
    if 'Start_Date' in df_event.columns:
        df_event = df_event.sort_values('Start_Date', ascending=False)

    results = {}
    for athlete_name in athlete_names:
        athlete_df = df_event[df_event['Athlete_Name'] == athlete_name]
        performances = athlete_df.head(5)['Result_numeric'].dropna().tolist() if not athlete_df.empty else []

        if len(performances) >= 2:
            try:
                proj = project_performance(performances, event_type=event_type, is_major_championship=True)
                results[athlete_name] = {
                    'projected': proj['projected'],
                    'trend_symbol': proj['trend_symbol'],
                    'form_score': proj['form_score'],
                    'performances': performances
                }
            except Exception:
                results[athlete_name] = {
                    'projected': performances[0] if performances else None,
                    'trend_symbol': '?',
                    'form_score': None,
                    'performances': performances
                }
        else:
            results[athlete_name] = {
                'projected': performances[0] if performances else None,
                'trend_symbol': '?',
                'form_score': None,
                'performances': performances
            }

    return results


def predict_placement(athlete_result, final_summary, event_type):
    """
    Predict likely placement based on athlete's result vs historical final data.
    Returns predicted place range and probability assessment.
    Now supports up to top 20 for more granular predictions.
    """
    if final_summary.empty or pd.isna(athlete_result):
        return {"predicted_place": "N/A", "assessment": "Insufficient data"}

    # For time events, lower is better
    ascending = (event_type == 'time')

    predictions = []
    for _, row in final_summary.iterrows():
        rank = int(row['Rank'])
        avg = row['Average']
        best = row.get('Fastest', row.get('Best', avg))
        worst = row.get('Slowest', row.get('Worst', avg))

        # Determine assessment based on rank
        def get_assessment(r):
            if r <= 3:
                return "Medal contender"
            elif r <= 8:
                return "Finalist"
            elif r <= 12:
                return "Semi-finalist"
            elif r <= 20:
                return "Heat qualifier"
            else:
                return "Development"

        if ascending:  # Time events
            if athlete_result <= best:
                predictions.append((rank, get_assessment(rank)))
            elif athlete_result <= avg:
                predictions.append((rank, "Competitive"))
            elif athlete_result <= worst:
                predictions.append((rank, "Possible"))
        else:  # Distance/points events
            if athlete_result >= best:
                predictions.append((rank, get_assessment(rank)))
            elif athlete_result >= avg:
                predictions.append((rank, "Competitive"))
            elif athlete_result >= worst:
                predictions.append((rank, "Possible"))

    if not predictions:
        # Check if within top 20 range
        max_rank = final_summary['Rank'].max() if 'Rank' in final_summary.columns else 8
        return {"predicted_place": f"Outside Top {int(max_rank)}", "assessment": "Below historical standards"}

    best_prediction = min(predictions, key=lambda x: x[0])
    return {"predicted_place": f"{best_prediction[0]}", "assessment": best_prediction[1]}


###################################
# WA Points Qualification Analysis Functions
###################################

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_all_events_quota_data(_df_hash, events, gender, date_start_str, date_end_str):
    """
    Batch process quota data for multiple events at once.
    Much faster than calling individual functions in a loop.

    Args:
        _df_hash: Hash of the dataframe for caching
        events: List of event names
        gender: 'Men' or 'Women'
        date_start_str: Start date as string
        date_end_str: End date as string

    Returns:
        dict with quota_data, ksa_best5, ksa_avg, and medians for each event
    """
    # Get the actual dataframe from session state
    df = st.session_state.get('_cached_df_all')
    if df is None:
        return {'quota_data': [], 'ksa_best5': [], 'ksa_avg': [], 'medians': []}

    date_start = pd.to_datetime(date_start_str) if date_start_str else None
    date_end = pd.to_datetime(date_end_str) if date_end_str else None

    quota_data_list = []
    ksa_best5_list = []
    ksa_avg_list = []
    median_data = []

    for event in events:
        quota_info = get_event_quota(event)
        ranking_quota = quota_info.get('ranking_quota', 24)

        # Get quota distribution
        quota_df = get_qualification_quota_distribution(
            df, event, gender, ranking_quota, date_start, date_end
        )
        if not quota_df.empty:
            quota_df = quota_df.copy()
            quota_df['Event'] = event
            quota_data_list.append(quota_df)
            median_data.append({
                'Event': event,
                'median': quota_df['wapoints'].median()
            })

        # Get KSA best 5
        ksa_top5 = get_ksa_athlete_best5_wapoints(df, event, gender, date_start, date_end)
        if not ksa_top5.empty:
            ksa_top5 = ksa_top5.copy()
            ksa_top5['Event'] = event
            ksa_best5_list.append(ksa_top5)

        # Get KSA average
        ksa_avg = calculate_ksa_ranking_score(df, event, gender, date_start, date_end)
        if ksa_avg:
            ksa_avg_list.append({
                'Event': event,
                'avg_wapoints': ksa_avg['avg_wapoints'],
                'Athlete_Name': ksa_avg['Athlete_Name'],
                'count': ksa_avg['count']
            })

    return {
        'quota_data': quota_data_list,
        'ksa_best5': ksa_best5_list,
        'ksa_avg': ksa_avg_list,
        'medians': median_data
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_qualification_quota_distribution(_df, event, gender, quota_size=24, date_start=None, date_end=None):
    """
    Get WA Points distribution for top N athletes (qualification quota).
    This represents athletes who would qualify via ranking.
    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame with wapoints column (underscore prefix for Streamlit)
        event: Event name
        gender: 'Men' or 'Women'
        quota_size: Number of athletes in ranking quota (default 24)
        date_start: Start date for filtering (optional)
        date_end: End date for filtering (optional)

    Returns:
        DataFrame with top athletes by WA Points
    """
    df = _df  # Work with original reference
    if 'wapoints' not in df.columns:
        return pd.DataFrame()

    # Filter by event and gender
    filtered = df.copy()
    if 'Event' in filtered.columns:
        filtered = filtered[filtered['Event'] == event]
    if 'Gender' in filtered.columns:
        filtered = filtered[filtered['Gender'] == gender]

    # Apply date filter if provided
    if date_start and date_end and 'Start_Date' in filtered.columns:
        filtered['Start_Date'] = pd.to_datetime(filtered['Start_Date'], errors='coerce')
        filtered = filtered[
            (filtered['Start_Date'] >= pd.to_datetime(date_start)) &
            (filtered['Start_Date'] <= pd.to_datetime(date_end))
        ]

    # Get best WA Points per athlete
    if 'Athlete_ID' in filtered.columns:
        athlete_best = filtered.groupby('Athlete_ID').agg({
            'wapoints': 'max',
            'Athlete_Name': 'first',
            'Athlete_Country': 'first' if 'Athlete_Country' in filtered.columns else 'first',
            'Result': 'first'
        }).reset_index()
    elif 'Athlete_Name' in filtered.columns:
        athlete_best = filtered.groupby('Athlete_Name').agg({
            'wapoints': 'max',
            'Athlete_Country': 'first' if 'Athlete_Country' in filtered.columns else 'first',
            'Result': 'first'
        }).reset_index()
    else:
        return pd.DataFrame()

    # Filter valid wapoints and sort
    athlete_best = athlete_best[athlete_best['wapoints'].notna()]
    athlete_best = athlete_best.sort_values('wapoints', ascending=False)

    # Return top quota_size athletes
    return athlete_best.head(quota_size)


@st.cache_data(ttl=3600, show_spinner=False)
def get_ksa_athlete_best5_wapoints(_df, event, gender, date_start=None, date_end=None):
    """
    Get KSA athlete's best 5 WA Points performances in an event.
    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame with wapoints column (underscore prefix for Streamlit)
        event: Event name
        gender: 'Men' or 'Women'
        date_start: Start date for filtering
        date_end: End date for filtering

    Returns:
        DataFrame with KSA athletes' top 5 WA Points performances
    """
    df = _df
    if 'wapoints' not in df.columns:
        return pd.DataFrame()

    # Filter for KSA athletes
    filtered = df.copy()
    ksa_mask = (
        (filtered.get('Athlete_CountryCode', pd.Series()) == 'KSA') |
        (filtered.get('Athlete_Country', pd.Series()) == 'Saudi Arabia') |
        (filtered.get('nationality', pd.Series()) == 'KSA')
    )
    filtered = filtered[ksa_mask]

    # Filter by event and gender
    if 'Event' in filtered.columns:
        filtered = filtered[filtered['Event'] == event]
    if 'Gender' in filtered.columns:
        filtered = filtered[filtered['Gender'] == gender]

    # Apply date filter if provided
    if date_start and date_end and 'Start_Date' in filtered.columns:
        filtered['Start_Date'] = pd.to_datetime(filtered['Start_Date'], errors='coerce')
        filtered = filtered[
            (filtered['Start_Date'] >= pd.to_datetime(date_start)) &
            (filtered['Start_Date'] <= pd.to_datetime(date_end))
        ]

    # Filter valid wapoints
    filtered = filtered[filtered['wapoints'].notna()]

    # Get best 5 performances
    result = filtered.nlargest(5, 'wapoints')

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def calculate_ksa_ranking_score(_df, event, gender, date_start=None, date_end=None):
    """
    Calculate average of KSA athlete's best 5 WA Points = ranking score.
    CACHED: Results cached for 1 hour to improve performance.

    Args:
        _df: DataFrame with wapoints column (underscore prefix for Streamlit)
        event: Event name
        gender: 'Men' or 'Women'
        date_start: Start date for filtering
        date_end: End date for filtering

    Returns:
        dict with athlete info and average score, or None if no data
    """
    best5 = get_ksa_athlete_best5_wapoints(_df, event, gender, date_start, date_end)

    if best5.empty:
        return None

    avg_points = best5['wapoints'].mean()
    athlete_name = best5['Athlete_Name'].iloc[0] if 'Athlete_Name' in best5.columns else 'KSA Athlete'

    return {
        'Athlete_Name': athlete_name,
        'avg_wapoints': avg_points,
        'count': len(best5),
        'best_points': best5['wapoints'].max(),
        'performances': best5
    }


def create_qualification_boxplot(df, event, gender, championship='tokyo_2025',
                                  date_start=None, date_end=None, show_previous=False):
    """
    Create a box plot showing WA Points distribution with KSA athlete overlay.

    Args:
        df: DataFrame with wapoints column
        event: Event name
        gender: 'Men' or 'Women'
        championship: 'tokyo_2025' or 'la_2028'
        date_start: Start date for filtering
        date_end: End date for filtering
        show_previous: Whether to show previous cycle overlay

    Returns:
        Altair chart object
    """
    # Get quota size for this event
    quota_info = get_event_quota(event)
    quota_size = quota_info.get('ranking_quota', 24)

    # Get distribution data
    quota_df = get_qualification_quota_distribution(df, event, gender, quota_size, date_start, date_end)

    if quota_df.empty:
        return None

    # Add event column for box plot
    quota_df['Event'] = event

    # Create box plot of qualification quota
    boxplot = alt.Chart(quota_df).mark_boxplot(
        color='#4169E1',
        opacity=0.7,
        size=40
    ).encode(
        x=alt.X('wapoints:Q', title='WA Points', scale=alt.Scale(zero=False)),
        y=alt.Y('Event:N', title=''),
        tooltip=['Event:N']
    )

    # Get KSA athlete's best 5
    ksa_top5 = get_ksa_athlete_best5_wapoints(df, event, gender, date_start, date_end)

    layers = [boxplot]

    if not ksa_top5.empty:
        ksa_top5['Event'] = event

        # KSA individual points (green circles)
        ksa_points = alt.Chart(ksa_top5).mark_circle(
            size=150,
            color='#00FF7F',
            opacity=0.9
        ).encode(
            x=alt.X('wapoints:Q'),
            y=alt.Y('Event:N'),
            tooltip=[
                alt.Tooltip('Athlete_Name:N', title='Athlete'),
                alt.Tooltip('wapoints:Q', title='WA Points', format='.0f'),
                alt.Tooltip('Result:N', title='Result'),
            ]
        )
        layers.append(ksa_points)

        # KSA average (gold square)
        ksa_avg = calculate_ksa_ranking_score(df, event, gender, date_start, date_end)
        if ksa_avg:
            avg_df = pd.DataFrame([{
                'Event': event,
                'avg_wapoints': ksa_avg['avg_wapoints'],
                'Athlete_Name': ksa_avg['Athlete_Name'],
                'count': ksa_avg['count']
            }])

            ksa_avg_marker = alt.Chart(avg_df).mark_square(
                size=250,
                color='#FFD700',
                stroke='black',
                strokeWidth=2
            ).encode(
                x=alt.X('avg_wapoints:Q'),
                y=alt.Y('Event:N'),
                tooltip=[
                    alt.Tooltip('Athlete_Name:N', title='Athlete'),
                    alt.Tooltip('avg_wapoints:Q', title='Avg Best 5', format='.0f'),
                    alt.Tooltip('count:Q', title='Performances')
                ]
            )
            layers.append(ksa_avg_marker)

    # Add median reference line
    median_points = quota_df['wapoints'].median()
    median_df = pd.DataFrame([{'median': median_points, 'Event': event}])
    median_line = alt.Chart(median_df).mark_rule(
        strokeDash=[5, 5],
        color='#FF6B6B',
        strokeWidth=2
    ).encode(
        x=alt.X('median:Q')
    )
    layers.append(median_line)

    # Combine all layers
    chart = alt.layer(*layers).properties(
        height=120,
        title=alt.TitleParams(
            text=f'WA Points Qualification Distribution - {gender}\'s {event}',
            subtitle=f'Top {quota_size} athletes by ranking | Green dots = KSA best 5 | Gold square = KSA average',
            color='white',
            subtitleColor='#888'
        )
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        labelColor='white',
        titleColor='white',
        gridColor='#333'
    ).configure_legend(
        labelColor='white',
        titleColor='white'
    )

    return chart


def show_qualification_points_analysis(df, event, gender, championship_type='World Championships'):
    """
    Display the qualification points analysis section with box plot and controls.
    """
    st.subheader("📊 WA Points Qualification Analysis")

    st.markdown("""
    **How to read this chart:**
    - **Box plot** shows the distribution of WA Points for athletes in the qualification quota
    - **Green dots** are your athlete's best 5 WA Points performances
    - **Gold square** is the average of best 5 (your ranking score)
    - **If the gold square is at or above the median (red dashed line), qualification is likely**
    """)

    # Controls
    col1, col2 = st.columns(2)

    with col1:
        # Date range slider
        date_range = st.date_input(
            "Performance Date Range",
            value=(datetime.date(2024, 8, 1), datetime.date(2025, 8, 24)),
            min_value=datetime.date(2023, 1, 1),
            max_value=datetime.date(2026, 12, 31),
            key=f"qual_date_range_{event}_{gender}"
        )

    with col2:
        # Championship selector
        champ_options = ["Tokyo 2025 WC", "LA 2028 Olympics"]
        selected_champ = st.radio(
            "Qualification Target",
            champ_options,
            horizontal=True,
            key=f"qual_champ_{event}_{gender}"
        )

    # View toggle
    view_mode = st.radio(
        "View Mode",
        ["Points (Ranking)", "Automatic (Entry Standard)"],
        horizontal=True,
        key=f"view_mode_{event}_{gender}"
    )

    show_previous = st.checkbox("Overlay previous cycle (2023-2024)", key=f"prev_cycle_{event}_{gender}")

    # Parse date range
    if len(date_range) == 2:
        date_start, date_end = date_range
    else:
        date_start = datetime.date(2024, 8, 1)
        date_end = datetime.date(2025, 8, 24)

    championship = 'tokyo_2025' if 'Tokyo' in selected_champ else 'la_2028'

    if view_mode == "Points (Ranking)":
        # Show box plot
        chart = create_qualification_boxplot(
            df, event, gender, championship,
            date_start, date_end, show_previous
        )

        if chart:
            st.altair_chart(chart, use_container_width=True)

            # Show metrics
            ksa_data = calculate_ksa_ranking_score(df, event, gender, date_start, date_end)
            quota_df = get_qualification_quota_distribution(
                df, event, gender,
                get_event_quota(event).get('ranking_quota', 24),
                date_start, date_end
            )

            if not quota_df.empty and ksa_data:
                median_points = quota_df['wapoints'].median()
                min_points = quota_df['wapoints'].min()

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("KSA Average Best 5", f"{ksa_data['avg_wapoints']:.0f}")
                with col2:
                    st.metric("Quota Median", f"{median_points:.0f}")
                with col3:
                    gap = ksa_data['avg_wapoints'] - median_points
                    st.metric("Gap to Median", f"{gap:+.0f}",
                             delta_color="normal" if gap >= 0 else "inverse")
                with col4:
                    status = "✅ Likely" if ksa_data['avg_wapoints'] >= median_points else "⚠️ At Risk"
                    st.metric("Qualification Status", status)
        else:
            st.info("No WA Points data available for this event.")

    else:
        # Show automatic qualification view
        entry_std = get_event_standard(event, championship, gender.lower())
        if entry_std:
            st.metric(f"Entry Standard ({selected_champ})",
                     f"{entry_std:.2f}" if entry_std < 100 else f"{entry_std:.0f}")

            # Get KSA athletes and compare to standard
            ksa_data = get_ksa_athlete_best5_wapoints(df, event, gender, date_start, date_end)
            if not ksa_data.empty and 'Result_numeric' in df.columns:
                # Would need to parse results - simplified for now
                st.info("Showing athletes' performances vs entry standard")
        else:
            st.info(f"No entry standard defined for {event} ({gender})")


def show_road_to_championship(df_all, championship_type, target_year, target_city):
    """
    Main Road to Championship tab - comprehensive pre-competition analysis.
    Recreates Power BI visualizations.
    """
    st.title(f"🏆 Road to {target_city} {target_year}")

    # Championship info header
    champ_info = UPCOMING_CHAMPIONSHIPS.get(championship_type, {}).get(target_year, {})
    if champ_info:
        st.markdown(f"""
        **{champ_info.get('name', championship_type)}**
        📍 {champ_info.get('city', target_city)}, {champ_info.get('country', '')}
        📅 {champ_info.get('dates', target_year)}
        """)

    st.markdown("---")

    # === FILTERS ===
    st.header("Analysis Filters")
    st.caption(f"Analyzing historical {championship_type} data to predict requirements for {target_city} {target_year}")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        # Lock benchmark to match target competition type
        if championship_type == "Asian Games":
            selected_champ = "Asian Games"
            st.text_input("Historical Data Source", value="Asian Games (2014-2023)", disabled=True, key=f"road_{championship_type}_champ_display")
        elif championship_type == "Olympics":
            selected_champ = "Olympics"
            st.text_input("Historical Data Source", value="Olympics (1984-2024)", disabled=True, key=f"road_{championship_type}_champ_display")
        elif championship_type == "World Championships":
            selected_champ = "World Championships"
            st.text_input("Historical Data Source", value="World Champs (1983-2025)", disabled=True, key=f"road_{championship_type}_champ_display")

    with col_f2:
        gender_opts = ['Men', 'Women']
        if 'Gender' in df_all.columns:
            gender_opts = sorted(df_all['Gender'].dropna().unique().tolist())
        selected_gender = st.selectbox("Gender", gender_opts, key=f"road_{championship_type}_gender")

    with col_f3:
        age_group_opts = ['Senior', 'U20', 'U18']
        selected_age = st.selectbox("Age Group", age_group_opts, key=f"road_{championship_type}_age")

    with col_f4:
        # Include Indoor option for Olympics qualification
        if championship_type == "Olympics":
            include_indoor = st.checkbox("Include Indoor Results", value=True, key=f"road_{championship_type}_indoor",
                                        help="Indoor results count for Olympic qualification")
        else:
            include_indoor = False

    # Event selector with category filter
    col_ev1, col_ev2 = st.columns([1, 2])
    with col_ev1:
        event_categories = ['All Events', 'Track', 'Field', 'Combined', 'Road/Walk']
        selected_category = st.selectbox("Event Category", event_categories, key=f"road_{championship_type}_cat")

    with col_ev2:
        if 'Event' in df_all.columns:
            all_events = sorted(df_all['Event'].dropna().unique().tolist())

            # First filter by indoor/outdoor context
            # By default exclude indoor-only events unless include_indoor is checked
            all_events = filter_events_for_context(all_events, include_indoor=include_indoor)

            # Filter events by category
            if selected_category == 'Track':
                event_opts = [e for e in all_events if any(x in e for x in ['m', 'Hurdles', 'Steeplechase'])
                             and 'x' not in e.lower() and 'Walk' not in e and 'Road' not in e
                             and 'Jump' not in e and 'Throw' not in e and 'Put' not in e
                             and 'Vault' not in e and 'athlon' not in e]
            elif selected_category == 'Field':
                event_opts = [e for e in all_events if any(x in e for x in ['Jump', 'Throw', 'Put', 'Vault', 'Javelin', 'Discus', 'Hammer', 'Shot'])]
            elif selected_category == 'Combined':
                event_opts = [e for e in all_events if any(x in e for x in ['athlon', 'Heptathlon', 'Decathlon', 'Pentathlon'])]
            elif selected_category == 'Road/Walk':
                event_opts = [e for e in all_events if any(x in e for x in ['Walk', 'Road', 'Marathon', 'km,'])]
            else:
                event_opts = all_events

            if not event_opts:
                st.warning(f"No events found for category '{selected_category}'. Showing all events.")
                event_opts = all_events

            # Reset event selection when category changes - use session state to track
            event_key = f"road_{championship_type}_event"
            cat_key = f"road_{championship_type}_cat_prev"
            indoor_key = f"road_{championship_type}_indoor_prev"

            # Check if category or indoor setting changed - if so, reset the event selection
            category_changed = cat_key in st.session_state and st.session_state[cat_key] != selected_category
            indoor_changed = indoor_key in st.session_state and st.session_state[indoor_key] != include_indoor

            if category_changed or indoor_changed:
                # Clear the event selection from session state
                if event_key in st.session_state:
                    del st.session_state[event_key]
                # Store new values and rerun to refresh dropdown
                st.session_state[cat_key] = selected_category
                st.session_state[indoor_key] = include_indoor
                st.rerun()

            # Store current values for next comparison
            st.session_state[cat_key] = selected_category
            st.session_state[indoor_key] = include_indoor

            # Set sensible default based on category
            if selected_category == 'Field':
                default_event = "Long Jump" if "Long Jump" in event_opts else event_opts[0] if event_opts else ""
            elif selected_category == 'Combined':
                default_event = event_opts[0] if event_opts else ""
            elif selected_category == 'Road/Walk':
                default_event = "Marathon" if "Marathon" in event_opts else event_opts[0] if event_opts else ""
            else:
                default_event = "100m" if "100m" in event_opts else event_opts[0] if event_opts else ""

            # Verify selected event is valid for current category
            current_selection = st.session_state.get(event_key, default_event)
            if current_selection not in event_opts:
                # Force to default if current selection not valid
                current_selection = default_event

            selected_event = st.selectbox("Event", event_opts,
                                          index=event_opts.index(current_selection) if current_selection in event_opts else 0,
                                          key=event_key)
        else:
            st.error("No Event column in data")
            return

    st.markdown("---")

    # === SUB-TABS FOR DIFFERENT ANALYSES ===
    # Show Qualification Points tab for Olympics and World Championships (WA Points system)
    # Asian Games uses area-based quotas, not WA Points
    if championship_type in ["Olympics", "World Championships"]:
        road_tabs = st.tabs([
            "🎯 Medal Standards",
            "📊 Round Progression",
            f"🇸🇦 KSA for {target_city}",
            "📈 Predict Placement",
            "🏆 WA Points/Ranking",
            "📋 One-Pager"
        ])
        qual_points_tab_idx = 4
        one_pager_tab_idx = 5
    else:
        road_tabs = st.tabs([
            "🎯 Medal Standards",
            "📊 Round Progression",
            f"🇸🇦 KSA for {target_city}",
            "📈 Predict Placement",
            "📋 One-Pager"
        ])
        qual_points_tab_idx = None
        one_pager_tab_idx = 4

    # --- Tab 1: Final Performance Standards (like Power BI Image 1) ---
    with road_tabs[0]:
        st.subheader(f"What It Takes to Medal at {target_city} {target_year}")
        st.markdown(f"**{selected_gender}'s {selected_event}** - Based on historical {selected_champ} final performances")

        final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age, include_indoor)

        if final_summary.empty:
            st.info(f"No final performance data available for {selected_gender}'s {selected_event} in {selected_champ}")
        else:
            # Display summary table (like Power BI Image 1 left panel)
            col_t1, col_t2 = st.columns([1, 2])

            with col_t1:
                st.markdown("#### Final Summary by Place (Top 12)")

                # Style the dataframe with green gradient
                def style_final_summary(df):
                    try:
                        return df.style.background_gradient(
                            cmap='Greens', subset=['Average']
                        ).format({
                            'Average': '{:.2f}',
                            'Fastest': '{:.2f}' if 'Fastest' in df.columns else '{:.2f}',
                            'Best': '{:.2f}' if 'Best' in df.columns else '{:.2f}',
                            'Slowest': '{:.2f}' if 'Slowest' in df.columns else '{:.2f}',
                            'Worst': '{:.2f}' if 'Worst' in df.columns else '{:.2f}'
                        })
                    except ImportError:
                        # Fallback if matplotlib not available for background_gradient
                        return df.style.format({
                            'Average': '{:.2f}',
                            'Fastest': '{:.2f}' if 'Fastest' in df.columns else '{:.2f}',
                            'Best': '{:.2f}' if 'Best' in df.columns else '{:.2f}',
                            'Slowest': '{:.2f}' if 'Slowest' in df.columns else '{:.2f}',
                            'Worst': '{:.2f}' if 'Worst' in df.columns else '{:.2f}'
                        })

                st.dataframe(style_final_summary(final_summary), hide_index=True, use_container_width=True)

            with col_t2:
                st.markdown("#### Performance Trends by Finishing Position")

                # Get detailed data for chart
                cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[selected_champ].values()]
                # Include Indoor Championships if requested
                if include_indoor and "World Athletics Indoor Championships" in MAJOR_COMPETITIONS_CID:
                    indoor_cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID["World Athletics Indoor Championships"].values()]
                    cids = cids + indoor_cids
                df_chart = df_all.copy()

                # IMPORTANT: Exclude hand-timed results
                df_chart = filter_fat_times_only(df_chart)

                if 'Competition_ID' in df_chart.columns:
                    df_chart['Competition_ID'] = df_chart['Competition_ID'].astype(str)
                    df_chart = df_chart[df_chart['Competition_ID'].isin(cids)]

                if 'Gender' in df_chart.columns:
                    df_chart = df_chart[df_chart['Gender'] == selected_gender]
                if 'Event' in df_chart.columns:
                    df_chart = df_chart[df_chart['Event'] == selected_event]

                # Filter for finals (Round values transformed: None -> 'Final')
                if 'Round' in df_chart.columns:
                    final_terms = ['final', 'f', 'a final', 'final a', '', 'none']
                    df_chart = df_chart[
                        df_chart['Round'].isna() |
                        df_chart['Round'].str.lower().str.strip().isin(final_terms)
                    ]

                if not df_chart.empty and 'Year' in df_chart.columns:
                    df_chart['Position_num'] = pd.to_numeric(df_chart['Position'], errors='coerce')
                    df_chart = df_chart[df_chart['Position_num'].between(1, 8)]

                    # Map positions to medal/place labels for better readability
                    place_labels = {1: '🥇 1st', 2: '🥈 2nd', 3: '🥉 3rd',
                                   4: '4th', 5: '5th', 6: '6th', 7: '7th', 8: '8th'}
                    df_chart['Place'] = df_chart['Position_num'].map(place_labels)

                    # Custom color scale for places (gold, silver, bronze, then greens)
                    place_colors = ['#FFD700', '#C0C0C0', '#CD7F32',
                                   '#228B22', '#32CD32', '#90EE90', '#98FB98', '#F0FFF0']

                    # Create line chart with improved styling
                    base = alt.Chart(df_chart).encode(
                        x=alt.X('Year:O', title='Championship Year', axis=alt.Axis(labelAngle=0)),
                        y=alt.Y('Result_numeric:Q', title='Performance (FAT)',
                               scale=alt.Scale(zero=False)),
                        color=alt.Color('Place:N',
                                       title='Finish',
                                       scale=alt.Scale(domain=list(place_labels.values()),
                                                      range=place_colors),
                                       sort=list(place_labels.values()),
                                       legend=alt.Legend(orient='right', columns=2)),
                        tooltip=[
                            alt.Tooltip('Year:O', title='Year'),
                            alt.Tooltip('Athlete_Name:N', title='Athlete'),
                            alt.Tooltip('Result:N', title='Time/Distance'),
                            alt.Tooltip('Place:N', title='Position')
                        ]
                    )

                    line = base.mark_line(strokeWidth=2)
                    points = base.mark_circle(size=80)

                    chart = (line + points).properties(
                        height=380,
                        title=alt.TitleParams(
                            text=f'{selected_champ} Finals - {selected_gender}\'s {selected_event}',
                            subtitle='FAT times only | Lower = Faster for track events',
                            color='white',
                            subtitleColor='#888'
                        )
                    ).configure_axis(
                        labelColor='white',
                        titleColor='white',
                        gridColor='#333',
                        labelFontSize=11,
                        titleFontSize=12
                    ).configure_view(
                        strokeWidth=0,
                        fill='#0e1117'
                    ).configure_legend(
                        labelColor='white',
                        titleColor='white',
                        labelFontSize=10
                    )

                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("Insufficient data for trend chart")

            # Key insights - improved presentation
            st.markdown("---")
            st.markdown("### 🎯 Performance Benchmarks")
            event_type = get_event_type(selected_event)

            if not final_summary.empty:
                gold_avg = final_summary[final_summary['Rank'] == 1]['Average'].values
                bronze_avg = final_summary[final_summary['Rank'] == 3]['Average'].values
                eighth_avg = final_summary[final_summary['Rank'] == 8]['Average'].values
                gold_best = final_summary[final_summary['Rank'] == 1]['Fastest' if event_type == 'time' else 'Best'].values if 'Fastest' in final_summary.columns or 'Best' in final_summary.columns else []

                # Display as metric cards
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                unit = "s" if event_type == 'time' else "m" if event_type == 'distance' else "pts"

                with col_m1:
                    if len(gold_avg) > 0:
                        st.metric("🥇 Gold Average", f"{gold_avg[0]:.2f}{unit}",
                                 help="Historical average winning performance")

                with col_m2:
                    if len(gold_best) > 0:
                        st.metric("⚡ Championship Record", f"{gold_best[0]:.2f}{unit}",
                                 help="Best winning performance in this championship")

                with col_m3:
                    if len(bronze_avg) > 0:
                        st.metric("🥉 Medal Line", f"{bronze_avg[0]:.2f}{unit}",
                                 help="Average bronze medal performance")

                with col_m4:
                    if len(eighth_avg) > 0:
                        st.metric("🎯 Finalist Line", f"{eighth_avg[0]:.2f}{unit}",
                                 help="Average 8th place - minimum for finals")

                # Performance gaps - key insight
                if len(gold_avg) > 0 and len(eighth_avg) > 0:
                    gap = abs(eighth_avg[0] - gold_avg[0])
                    st.info(f"📊 **Finals Spread:** {gap:.2f}{unit} separates 1st from 8th place historically")

            # === ENTRY STANDARDS COMPARISON ===
            st.markdown("---")
            st.markdown("### 🎫 Entry Standards vs Championship Performance")

            # Get entry standards
            tokyo_std = get_event_standard(selected_event, 'tokyo_2025', selected_gender.lower())
            la_std = get_event_standard(selected_event, 'la_2028', selected_gender.lower())

            col_std1, col_std2, col_std3, col_std4 = st.columns(4)

            with col_std1:
                if tokyo_std:
                    st.metric("Tokyo 2025 Entry",
                             format_benchmark_for_display(tokyo_std, event_type),
                             help="World Championships Tokyo 2025 entry standard")
                else:
                    st.metric("Tokyo 2025 Entry", "TBD")

            with col_std2:
                if la_std:
                    st.metric("LA 2028 Entry (Est.)",
                             format_benchmark_for_display(la_std, event_type),
                             help="Olympics LA 2028 estimated entry standard")
                else:
                    st.metric("LA 2028 Entry", "TBD")

            with col_std3:
                if gold_avg is not None and len(gold_avg) > 0:
                    st.metric("Gold Average",
                             f"{gold_avg[0]:.2f}{unit}",
                             help="Historical gold medal average")

            with col_std4:
                if eighth_avg is not None and len(eighth_avg) > 0:
                    st.metric("Finalist Average",
                             f"{eighth_avg[0]:.2f}{unit}",
                             help="Historical 8th place average")

            # Dual pathway explanation
            quota_info = get_event_quota(selected_event)
            if quota_info:
                st.markdown("#### 📋 Qualification Pathways")
                col_path1, col_path2 = st.columns(2)

                with col_path1:
                    st.markdown(f"""
**Entry Standard Path (50%)**
- Achieve the entry standard to auto-qualify
- Maximum 3 athletes per country
- Valid from qualification window start
                    """)

                with col_path2:
                    st.markdown(f"""
**WA Rankings Path (50%)**
- Total field: **{quota_info.get('total_field', 'N/A')}** athletes
- Ranking quota: **{quota_info.get('ranking_quota', 'N/A')}** athletes
- Based on average of top WA Points performances
                    """)

            # === PROGRESSION CHART - What It Takes to Win Over Time ===
            st.markdown("---")
            st.markdown("### 📈 Finals Performance Progression (1st-8th)")
            st.markdown("How final performances have evolved across championships for all 8 finalists")

            # Get year-by-year performances for all 8 finalists
            cids_dict = MAJOR_COMPETITIONS_CID.get(selected_champ, {})
            # Include indoor CIDs if requested
            if include_indoor and "World Athletics Indoor Championships" in MAJOR_COMPETITIONS_CID:
                indoor_dict = MAJOR_COMPETITIONS_CID["World Athletics Indoor Championships"]
                cids_dict = {**cids_dict, **indoor_dict}

            progression_data = []

            for year, info in cids_dict.items():
                cid = info.get('CID')
                df_year = df_all.copy()
                df_year = filter_fat_times_only(df_year)

                if 'Competition_ID' in df_year.columns:
                    df_year['Competition_ID'] = df_year['Competition_ID'].astype(str)
                    df_year = df_year[df_year['Competition_ID'] == cid]

                if 'Gender' in df_year.columns:
                    df_year = df_year[df_year['Gender'] == selected_gender]
                if 'Event' in df_year.columns:
                    df_year = df_year[df_year['Event'] == selected_event]

                # Get top 8 finishers (all finalists)
                if not df_year.empty and 'Result_numeric' in df_year.columns:
                    df_year = df_year.dropna(subset=['Result_numeric'])
                    if not df_year.empty:
                        ascending = (event_type == 'time')
                        df_sorted = df_year.sort_values('Result_numeric', ascending=ascending)

                        # Place labels for 1-8
                        place_labels = {1: '🥇 1st', 2: '🥈 2nd', 3: '🥉 3rd',
                                       4: '4th', 5: '5th', 6: '6th', 7: '7th', 8: '8th'}

                        for rank, (_, row) in enumerate(df_sorted.head(8).iterrows(), 1):
                            progression_data.append({
                                'Year': int(year),
                                'Result': row['Result_numeric'],
                                'Rank': rank,
                                'Place': place_labels.get(rank, f'{rank}th')
                            })

            if progression_data:
                prog_df = pd.DataFrame(progression_data)

                # Color scale for 1-8 places (medals + gradient for 4-8)
                place_domain = ['🥇 1st', '🥈 2nd', '🥉 3rd', '4th', '5th', '6th', '7th', '8th']
                place_colors = ['#FFD700', '#C0C0C0', '#CD7F32', '#4CAF50', '#2196F3', '#9C27B0', '#FF5722', '#607D8B']

                # Create progression chart for all 8 places
                progression_chart = alt.Chart(prog_df).mark_line(point=True, strokeWidth=2).encode(
                    x=alt.X('Year:O', title='Championship Year', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Result:Q', title=f'Performance ({unit})',
                           scale=alt.Scale(zero=False,
                                          reverse=(event_type == 'time'))),
                    color=alt.Color('Place:N',
                                   scale=alt.Scale(domain=place_domain, range=place_colors),
                                   legend=alt.Legend(title='Finishing Position')),
                    tooltip=['Year', alt.Tooltip('Result:Q', format='.2f'), 'Place']
                ).properties(
                    height=350,
                    title=f'{selected_event} Final Performances Over Time (1st-8th)'
                ).configure_axis(
                    labelColor='white', titleColor='white', gridColor='#333'
                ).configure_view(
                    strokeWidth=0, fill='#0e1117'
                ).configure_legend(
                    labelColor='white', titleColor='white'
                ).configure_title(
                    color='white'
                )

                st.altair_chart(progression_chart, use_container_width=True)

                # Key insight: trend analysis
                gold_results = prog_df[prog_df['Rank'] == 1].sort_values('Year')
                eighth_results = prog_df[prog_df['Rank'] == 8].sort_values('Year')

                if len(gold_results) >= 2:
                    first_gold = gold_results.iloc[0]['Result']
                    last_gold = gold_results.iloc[-1]['Result']
                    first_year = gold_results.iloc[0]['Year']
                    last_year = gold_results.iloc[-1]['Year']

                    if event_type == 'time':
                        improvement = first_gold - last_gold
                        direction = "faster" if improvement > 0 else "slower"
                    else:
                        improvement = last_gold - first_gold
                        direction = "further/higher" if improvement > 0 else "shorter/lower"

                    st.markdown(f"**📊 Gold Trend:** Performance has gone from "
                               f"**{first_gold:.2f}** ({first_year}) to **{last_gold:.2f}** ({last_year}) — "
                               f"**{abs(improvement):.2f}{unit} {direction}**")

                # Finals spread trend
                if len(eighth_results) >= 2 and len(gold_results) >= 2:
                    recent_gold = gold_results.iloc[-1]['Result']
                    recent_eighth = eighth_results.iloc[-1]['Result'] if len(eighth_results) > 0 else None
                    if recent_eighth:
                        spread = abs(recent_eighth - recent_gold)
                        st.markdown(f"**🎯 Recent Finals Spread:** {spread:.2f}{unit} separated 1st from 8th in {gold_results.iloc[-1]['Year']}")
            else:
                st.info("No progression data available for this event")

    # --- Tab 2: Qualification Standards (like Power BI Image 2) ---
    with road_tabs[1]:
        st.subheader(f"How to Progress Through Rounds at {target_city} {target_year}")
        st.markdown(f"**{selected_gender}'s {selected_event}** - Based on historical {selected_champ} qualification rounds")

        qual_summary = get_qualification_by_round(df_all, selected_champ, selected_gender, selected_event, include_indoor)

        if qual_summary.empty:
            st.warning(f"⚠️ No qualification stage data (Heats/Semi Finals) available for {selected_gender}'s {selected_event}")
            st.markdown("""
            **Why this happens:**
            - Round-by-round data (Heats, Semi Finals) may not be available for this championship
            - Some events go directly to finals without preliminary rounds
            """)
        else:
            col_q1, col_q2 = st.columns([1, 2])

            with col_q1:
                st.markdown("#### Qualification Type by Stage")
                st.dataframe(qual_summary, hide_index=True, use_container_width=True)

                # Show what it takes to qualify
                st.markdown("#### 🎯 To Advance:")
                for _, row in qual_summary.iterrows():
                    round_name = row['Round']
                    avg = row['Average']
                    fastest = row['Fastest']
                    st.markdown(f"**{round_name}:** Average qualifier: {avg:.2f} | Auto qualifier: ~{fastest:.2f}")

            with col_q2:
                st.markdown("#### Qualification Performance Trends")

                # Get detailed qualification data
                cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[selected_champ].values()]
                # Include Indoor Championships if requested
                if include_indoor and "World Athletics Indoor Championships" in MAJOR_COMPETITIONS_CID:
                    indoor_cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID["World Athletics Indoor Championships"].values()]
                    cids = cids + indoor_cids
                df_qual_chart = df_all.copy()
                if 'Competition_ID' in df_qual_chart.columns:
                    df_qual_chart['Competition_ID'] = df_qual_chart['Competition_ID'].astype(str)
                    df_qual_chart = df_qual_chart[df_qual_chart['Competition_ID'].isin(cids)]

                if 'Gender' in df_qual_chart.columns:
                    df_qual_chart = df_qual_chart[df_qual_chart['Gender'] == selected_gender]
                if 'Event' in df_qual_chart.columns:
                    df_qual_chart = df_qual_chart[df_qual_chart['Event'] == selected_event]

                if 'Round' in df_qual_chart.columns:
                    qual_terms = ['heats', 'heat', 'h', 'semi', 'semi final', 'sf', 'semi-final']
                    df_qual_chart = df_qual_chart[df_qual_chart['Round'].str.lower().str.strip().isin(qual_terms)]

                if not df_qual_chart.empty and 'Year' in df_qual_chart.columns:
                    # Standardize round names
                    round_map = {'heats': 'Heats', 'heat': 'Heats', 'h': 'Heats',
                                'semi': 'Semi Finals', 'semi final': 'Semi Finals', 'sf': 'Semi Finals'}
                    df_qual_chart['Round_std'] = df_qual_chart['Round'].str.lower().str.strip().map(
                        lambda x: round_map.get(x, x.title())
                    )

                    # Group by year and round to get averages
                    qual_trend = df_qual_chart.groupby(['Year', 'Round_std']).agg({
                        'Result_numeric': ['mean', 'min', 'max']
                    }).reset_index()
                    qual_trend.columns = ['Year', 'Round', 'Average', 'Best', 'Worst']

                    chart = alt.Chart(qual_trend).mark_line(point=True).encode(
                        x=alt.X('Year:O', title='Competition Year'),
                        y=alt.Y('Average:Q', title='Average Qualifying Time'),
                        color=alt.Color('Round:N', title='Round'),
                        tooltip=['Year', 'Round', 'Average', 'Best', 'Worst']
                    ).properties(height=300).configure_axis(
                        labelColor='white', titleColor='white', gridColor='gray'
                    ).configure_view(strokeWidth=0, fill='#1a1a1a'
                    ).configure_legend(labelColor='white', titleColor='white')

                    st.altair_chart(chart, use_container_width=True)

            # === ADVANCEMENT PROBABILITY CALCULATOR ===
            st.markdown("---")
            st.markdown("### 🧮 Advancement Probability Calculator")
            st.caption("Enter a target performance to see probability of advancing through each round")

            # Get benchmarks for probability calculation
            adv_benchmarks = get_default_benchmarks(selected_event, selected_gender)

            col_calc1, col_calc2 = st.columns([1, 2])

            with col_calc1:
                if event_type == 'time':
                    calc_target = st.text_input(
                        "Target Performance (e.g., 10.05 or 1:45.00)",
                        value="10.00",
                        key=f"adv_calc_{championship_type}_{selected_event}"
                    )
                    try:
                        if ':' in calc_target:
                            parts = calc_target.split(':')
                            if len(parts) == 2:
                                calc_numeric = float(parts[0]) * 60 + float(parts[1])
                            else:
                                calc_numeric = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                        else:
                            calc_numeric = float(calc_target)
                    except:
                        calc_numeric = None
                        st.error("Invalid time format")
                else:
                    calc_numeric = st.number_input(
                        "Target Performance (meters/points)",
                        value=8.00,
                        step=0.01,
                        key=f"adv_calc_{championship_type}_{selected_event}"
                    )

            with col_calc2:
                if calc_numeric and adv_benchmarks:
                    historical_cutoffs = {
                        'heat': adv_benchmarks.get('heat', {}).get('cutoff') or adv_benchmarks.get('heat', {}).get('average'),
                        'semi': adv_benchmarks.get('semi', {}).get('cutoff') or adv_benchmarks.get('semi', {}).get('average'),
                        'final': adv_benchmarks.get('final', {}).get('cutoff') or adv_benchmarks.get('final', {}).get('average'),
                        'medal': adv_benchmarks.get('medal', {}).get('average')
                    }
                    historical_cutoffs = {k: v for k, v in historical_cutoffs.items() if v is not None}

                    if historical_cutoffs:
                        adv_probs = calculate_advancement_probability(calc_numeric, historical_cutoffs, event_type)
                        adv_chart = probability_gauge(adv_probs, title='Probability of Advancing Each Round')
                        st.altair_chart(adv_chart, use_container_width=True)

                        # Show benchmark values
                        st.markdown("**Historical Round Cutoffs:**")
                        cutoff_text = " | ".join([
                            f"Heat: {format_benchmark_for_display(historical_cutoffs.get('heat'), event_type)}" if 'heat' in historical_cutoffs else "",
                            f"Semi: {format_benchmark_for_display(historical_cutoffs.get('semi'), event_type)}" if 'semi' in historical_cutoffs else "",
                            f"Final: {format_benchmark_for_display(historical_cutoffs.get('final'), event_type)}" if 'final' in historical_cutoffs else "",
                            f"Medal: {format_benchmark_for_display(historical_cutoffs.get('medal'), event_type)}" if 'medal' in historical_cutoffs else ""
                        ])
                        st.caption(cutoff_text.strip(" | "))

    # --- Tab 3: KSA Athletes Assessment - DEEP DIVE ---
    with road_tabs[2]:
        st.subheader(f"🇸🇦 KSA Athletes for {target_city} {target_year}")
        st.markdown(f"**{selected_gender}'s {selected_event}** - Assessing readiness against {selected_champ} standards")

        ksa_athletes = get_ksa_athletes_for_event(df_all, selected_gender, selected_event)

        if ksa_athletes.empty:
            st.info(f"No KSA athletes found for {selected_gender}'s {selected_event}")
        else:
            # Get historical standards for comparison
            final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age, include_indoor)
            qual_summary = get_qualification_by_round(df_all, selected_champ, selected_gender, selected_event, include_indoor)
            event_type = get_event_type(selected_event)
            unit = "s" if event_type == 'time' else "m" if event_type == 'distance' else "pts"

            # === OVERVIEW SECTION ===
            st.markdown("### 📊 KSA Squad Overview")
            st.markdown(f"**{len(ksa_athletes)} athlete(s)** currently active in {selected_gender}'s {selected_event}")

            # Squad summary metrics
            col_ov1, col_ov2, col_ov3, col_ov4 = st.columns(4)

            if event_type == 'time':
                best_ksa = ksa_athletes['Result_numeric'].min()
                avg_ksa = ksa_athletes['Result_numeric'].mean()
            else:
                best_ksa = ksa_athletes['Result_numeric'].max()
                avg_ksa = ksa_athletes['Result_numeric'].mean()

            with col_ov1:
                st.metric("Best KSA Performance", f"{best_ksa:.2f}{unit}")

            with col_ov2:
                st.metric("Squad Average", f"{avg_ksa:.2f}{unit}")

            with col_ov3:
                # How many could make finals?
                if not final_summary.empty:
                    eighth_std = final_summary[final_summary['Rank'] == 8]['Average'].values
                    if len(eighth_std) > 0:
                        if event_type == 'time':
                            finalists = len(ksa_athletes[ksa_athletes['Result_numeric'] <= eighth_std[0]])
                        else:
                            finalists = len(ksa_athletes[ksa_athletes['Result_numeric'] >= eighth_std[0]])
                        st.metric("Potential Finalists", f"{finalists}/{len(ksa_athletes)}")
                    else:
                        st.metric("Potential Finalists", "N/A")
                else:
                    st.metric("Potential Finalists", "N/A")

            with col_ov4:
                # Medal contenders
                if not final_summary.empty:
                    bronze_std = final_summary[final_summary['Rank'] == 3]['Average'].values
                    if len(bronze_std) > 0:
                        if event_type == 'time':
                            medalists = len(ksa_athletes[ksa_athletes['Result_numeric'] <= bronze_std[0]])
                        else:
                            medalists = len(ksa_athletes[ksa_athletes['Result_numeric'] >= bronze_std[0]])
                        st.metric("Medal Contenders", f"{medalists}/{len(ksa_athletes)}")
                    else:
                        st.metric("Medal Contenders", "N/A")
                else:
                    st.metric("Medal Contenders", "N/A")

            # === FORM PROJECTIONS SECTION ===
            st.markdown("---")
            st.markdown("### 🔮 Form Projections for Championship")
            st.caption("Statistical projections based on recent performances with confidence intervals")

            # Get historical benchmarks for probability calculations
            hist_benchmarks = get_default_benchmarks(selected_event, selected_gender)

            # Sort athletes by performance (best first)
            if event_type == 'time':
                sorted_athletes_proj = ksa_athletes.sort_values('Result_numeric', ascending=True)
            else:
                sorted_athletes_proj = ksa_athletes.sort_values('Result_numeric', ascending=False)

            for idx, (_, athlete) in enumerate(sorted_athletes_proj.iterrows()):
                athlete_name = athlete['Athlete_Name']

                # Get last 5 performances for this athlete
                athlete_recent = df_all[
                    (df_all['Athlete_Name'] == athlete_name) &
                    (df_all['Event'] == selected_event)
                ].copy()
                athlete_recent = filter_fat_times_only(athlete_recent)

                performances = []
                if not athlete_recent.empty and 'Start_Date' in athlete_recent.columns:
                    athlete_recent = athlete_recent.sort_values('Start_Date', ascending=False)
                    performances = athlete_recent.head(5)['Result_numeric'].dropna().tolist()

                if len(performances) >= 2:
                    # Use projection_engine
                    projection = project_performance(
                        performances=performances,
                        event_type=event_type,
                        is_major_championship=True,
                        include_trend=True
                    )

                    with st.expander(f"📊 {athlete_name} - Form Projection", expanded=(idx==0)):
                        col_proj1, col_proj2, col_proj3, col_proj4 = st.columns(4)

                        with col_proj1:
                            st.metric(
                                "Projected Performance",
                                f"{projection['projected']:.2f}{unit}",
                                help="Weighted average with championship adjustment"
                            )
                        with col_proj2:
                            st.metric(
                                "68% Confidence Range",
                                f"{projection['range_low']:.2f} - {projection['range_high']:.2f}",
                                help="68% probability performance falls in this range"
                            )
                        with col_proj3:
                            trend_delta = "normal" if projection['trend'] == 'improving' else ("inverse" if projection['trend'] == 'declining' else "off")
                            st.metric(
                                f"Form Trend {projection['trend_symbol']}",
                                projection['trend'].title(),
                                delta=projection['trend_symbol'] if projection['trend'] != 'stable' else None,
                                delta_color=trend_delta
                            )
                        with col_proj4:
                            form_color = "normal" if projection['form_score'] >= 70 else ("inverse" if projection['form_score'] < 50 else "off")
                            st.metric(
                                "Form Score",
                                f"{projection['form_score']:.0f}/100",
                                help="100 = at personal best, 0 = at worst"
                            )

                        # Calculate advancement probabilities if benchmarks available
                        if hist_benchmarks:
                            historical_cutoffs = {
                                'heat': hist_benchmarks.get('heat', {}).get('cutoff') or hist_benchmarks.get('heat', {}).get('average'),
                                'semi': hist_benchmarks.get('semi', {}).get('cutoff') or hist_benchmarks.get('semi', {}).get('average'),
                                'final': hist_benchmarks.get('final', {}).get('cutoff') or hist_benchmarks.get('final', {}).get('average'),
                                'medal': hist_benchmarks.get('medal', {}).get('average')
                            }
                            # Remove None values
                            historical_cutoffs = {k: v for k, v in historical_cutoffs.items() if v is not None}

                            if historical_cutoffs:
                                probs = calculate_advancement_probability(
                                    projection['projected'],
                                    historical_cutoffs,
                                    event_type
                                )

                                # Display probability gauge
                                prob_chart = probability_gauge(probs, title='Championship Advancement Probability')
                                st.altair_chart(prob_chart, use_container_width=True)

                        # Methodology disclosure
                        with st.expander("📖 Methodology"):
                            st.markdown(projection['methodology'])
                else:
                    with st.expander(f"📊 {athlete_name} - Insufficient Data", expanded=False):
                        st.info(f"Need at least 2 recent performances for projection. Found: {len(performances)}")

            # === COMPARISON CHART ===
            st.markdown("---")
            st.markdown("### 📈 KSA vs Championship Standards")

            # Create comparison visualization with improved bullet/lollipop chart
            if not final_summary.empty and len(ksa_athletes) > 0:
                # Get championship standards
                gold_std = final_summary[final_summary['Rank'] == 1]['Average'].values
                bronze_std = final_summary[final_summary['Rank'] == 3]['Average'].values
                eighth_std = final_summary[final_summary['Rank'] == 8]['Average'].values

                gold_val = gold_std[0] if len(gold_std) > 0 else None
                bronze_val = bronze_std[0] if len(bronze_std) > 0 else None
                eighth_val = eighth_std[0] if len(eighth_std) > 0 else None

                # Sort athletes by performance (best first)
                if event_type == 'time':
                    sorted_athletes = ksa_athletes.sort_values('Result_numeric', ascending=True)
                else:
                    sorted_athletes = ksa_athletes.sort_values('Result_numeric', ascending=False)

                # Calculate X-axis range
                all_values = sorted_athletes['Result_numeric'].dropna().tolist()
                if gold_val: all_values.append(gold_val)
                if bronze_val: all_values.append(bronze_val)
                if eighth_val: all_values.append(eighth_val)

                if all_values:
                    x_min = min(all_values) * 0.95 if event_type == 'time' else min(all_values) * 0.9
                    x_max = max(all_values) * 1.05 if event_type == 'time' else max(all_values) * 1.1
                else:
                    x_min, x_max = 0, 100

                # Standards legend with colored boxes
                st.markdown("**Championship Standards (dashed lines):**")
                legend_cols = st.columns(4)
                with legend_cols[0]:
                    st.markdown(f"<span style='color:#FFD700;font-weight:bold'>━━</span> **Gold:** {gold_val:.2f}{unit}" if gold_val else "", unsafe_allow_html=True)
                with legend_cols[1]:
                    st.markdown(f"<span style='color:#C0C0C0;font-weight:bold'>━━</span> **Silver:** {final_summary[final_summary['Rank'] == 2]['Average'].values[0]:.2f}{unit}" if len(final_summary[final_summary['Rank'] == 2]['Average'].values) > 0 else "", unsafe_allow_html=True)
                with legend_cols[2]:
                    st.markdown(f"<span style='color:#CD7F32;font-weight:bold'>━━</span> **Medal:** {bronze_val:.2f}{unit}" if bronze_val else "", unsafe_allow_html=True)
                with legend_cols[3]:
                    st.markdown(f"<span style='color:#4169E1;font-weight:bold'>━━</span> **Finalist:** {eighth_val:.2f}{unit}" if eighth_val else "", unsafe_allow_html=True)

                # Prepare data for horizontal bullet chart
                chart_data = []
                for idx, (_, athlete) in enumerate(sorted_athletes.iterrows()):
                    perf = athlete['Result_numeric']

                    # Determine status based on performance
                    if event_type == 'time':
                        if gold_val and perf <= gold_val:
                            status = 'Gold Contender'
                            status_emoji = '🥇'
                        elif bronze_val and perf <= bronze_val:
                            status = 'Medal Contender'
                            status_emoji = '🥉'
                        elif eighth_val and perf <= eighth_val:
                            status = 'Finalist'
                            status_emoji = '🎯'
                        else:
                            status = 'Development'
                            status_emoji = '📈'
                        gap_to_gold = perf - gold_val if gold_val else 0
                    else:
                        if gold_val and perf >= gold_val:
                            status = 'Gold Contender'
                            status_emoji = '🥇'
                        elif bronze_val and perf >= bronze_val:
                            status = 'Medal Contender'
                            status_emoji = '🥉'
                        elif eighth_val and perf >= eighth_val:
                            status = 'Finalist'
                            status_emoji = '🎯'
                        else:
                            status = 'Development'
                            status_emoji = '📈'
                        gap_to_gold = gold_val - perf if gold_val else 0

                    chart_data.append({
                        'Athlete': f"{idx+1}. {athlete['Athlete_Name']}",
                        'Athlete_Name': athlete['Athlete_Name'],
                        'Performance': perf,
                        'Status': status,
                        'Status_Emoji': status_emoji,
                        'Gap_to_Gold': gap_to_gold,
                        'Order': idx
                    })

                chart_df = pd.DataFrame(chart_data)

                # Status color scale (Development = Medium Purple, distinct from gold)
                status_colors = alt.Scale(
                    domain=['Gold Contender', 'Medal Contender', 'Finalist', 'Development'],
                    range=['#FFD700', '#CD7F32', '#4169E1', '#9370DB']
                )

                # Calculate appropriate label limit based on longest name
                max_name_len = max(len(athlete['Athlete_Name']) for _, athlete in sorted_athletes.iterrows())
                label_limit = min(300, max(150, max_name_len * 8))

                # Create horizontal bullet chart with lollipop markers
                base_chart = alt.Chart(chart_df).encode(
                    y=alt.Y('Athlete:N', title=None, sort=alt.SortField('Order', order='ascending'),
                           axis=alt.Axis(
                               labelFontSize=11,
                               labelColor='white',
                               labelLimit=label_limit,
                               labelPadding=10
                           ))
                )

                # Lollipop stem (line from x_min to performance)
                stem = base_chart.mark_rule(strokeWidth=4, opacity=0.7).encode(
                    x=alt.X('Performance:Q', title=f'Performance ({unit})',
                           scale=alt.Scale(domain=[x_min, x_max], reverse=(event_type == 'time')),
                           axis=alt.Axis(
                               labelFontSize=11,
                               labelColor='white',
                               titleFontSize=12,
                               titleColor='white',
                               gridColor='#444',
                               tickCount=8
                           )),
                    color=alt.Color('Status:N', scale=status_colors, legend=alt.Legend(title='Status', orient='bottom'))
                )

                # Lollipop head (circle at performance)
                head = base_chart.mark_circle(size=250, opacity=1).encode(
                    x=alt.X('Performance:Q'),
                    color=alt.Color('Status:N', scale=status_colors, legend=None),
                    tooltip=[
                        alt.Tooltip('Athlete_Name:N', title='Athlete'),
                        alt.Tooltip('Performance:Q', format='.2f', title='PB'),
                        alt.Tooltip('Status:N', title='Status'),
                        alt.Tooltip('Gap_to_Gold:Q', format='.2f', title='Gap to Gold')
                    ]
                )

                # Performance label - positioned based on event type
                if event_type == 'time':
                    # For time events (reversed axis), label on the left of point
                    perf_text = base_chart.mark_text(align='right', dx=-12, fontSize=10, fontWeight='bold', color='white').encode(
                        x=alt.X('Performance:Q'),
                        text=alt.Text('Performance:Q', format='.2f')
                    )
                else:
                    # For distance events, label on the right of point
                    perf_text = base_chart.mark_text(align='left', dx=12, fontSize=10, fontWeight='bold', color='white').encode(
                        x=alt.X('Performance:Q'),
                        text=alt.Text('Performance:Q', format='.2f')
                    )

                # Reference lines for standards with labels
                rule_data = []
                if gold_val:
                    rule_data.append({'Standard': '🥇 Gold', 'Value': gold_val})
                if bronze_val:
                    rule_data.append({'Standard': '🥉 Medal', 'Value': bronze_val})
                if eighth_val:
                    rule_data.append({'Standard': '🎯 Finalist', 'Value': eighth_val})

                rules_df = pd.DataFrame(rule_data)

                rules = alt.Chart(rules_df).mark_rule(strokeDash=[6, 4], strokeWidth=2.5).encode(
                    x=alt.X('Value:Q'),
                    color=alt.Color('Standard:N',
                                  scale=alt.Scale(domain=['🥇 Gold', '🥉 Medal', '🎯 Finalist'],
                                                 range=['#FFD700', '#CD7F32', '#4169E1']),
                                  legend=None),
                    tooltip=[alt.Tooltip('Standard:N'), alt.Tooltip('Value:Q', format='.2f')]
                )

                # Add standard labels at top of chart
                rule_labels = alt.Chart(rules_df).mark_text(
                    align='center', dy=-10, fontSize=10, fontWeight='bold'
                ).encode(
                    x=alt.X('Value:Q'),
                    text=alt.Text('Value:Q', format='.2f'),
                    color=alt.Color('Standard:N',
                                  scale=alt.Scale(domain=['🥇 Gold', '🥉 Medal', '🎯 Finalist'],
                                                 range=['#FFD700', '#CD7F32', '#4169E1']),
                                  legend=None)
                )

                # Combine all layers
                chart = alt.layer(rules, rule_labels, stem, head, perf_text).properties(
                    height=max(350, len(chart_df) * 40),
                    title=alt.TitleParams(
                        text=f'KSA Athletes vs {selected_champ} Standards - {selected_event}',
                        color='white', fontSize=14
                    )
                ).configure_axis(
                    labelColor='white', titleColor='white', gridColor='#333', domainColor='#555'
                ).configure_view(
                    strokeWidth=0, fill='#0e1117'
                ).configure_legend(
                    labelColor='white', titleColor='white', orient='bottom', columns=4
                ).configure_title(
                    color='white'
                )

                st.altair_chart(chart, use_container_width=True)

                # Summary stats below chart
                st.markdown("---")
                summary_cols = st.columns(4)
                gold_count = len(chart_df[chart_df['Status'] == 'Gold Contender'])
                medal_count = len(chart_df[chart_df['Status'] == 'Medal Contender'])
                finalist_count = len(chart_df[chart_df['Status'] == 'Finalist'])
                dev_count = len(chart_df[chart_df['Status'] == 'Development'])

                with summary_cols[0]:
                    st.metric("🥇 Gold Contenders", gold_count)
                with summary_cols[1]:
                    st.metric("🥉 Medal Contenders", medal_count)
                with summary_cols[2]:
                    st.metric("🎯 Finalists", finalist_count)
                with summary_cols[3]:
                    st.metric("📈 Development", dev_count)
            else:
                st.info("No data available for comparison chart.")

            # === WA POINTS ANALYSIS ===
            st.markdown("---")
            st.markdown("### 🏆 World Athletics Points Analysis")

            # Check if WA Points data is available
            if 'wapoints' in ksa_athletes.columns:
                athletes_with_points = ksa_athletes[ksa_athletes['wapoints'].notna()]

                if not athletes_with_points.empty:
                    st.markdown(f"WA Points distribution for **{len(athletes_with_points)}** athlete(s) with ranking points")

                    # Create WA Points bar chart
                    points_data = athletes_with_points[['Athlete_Name', 'wapoints']].copy()
                    points_data = points_data.sort_values('wapoints', ascending=False)
                    points_data.columns = ['Athlete', 'WA Points']

                    # Add ranking tier colors
                    def get_ranking_tier(points):
                        if points >= 1200:
                            return 'Elite (1200+)'
                        elif points >= 1100:
                            return 'Top 50 (1100+)'
                        elif points >= 1000:
                            return 'Top 100 (1000+)'
                        elif points >= 900:
                            return 'Competitive (900+)'
                        else:
                            return 'Development (<900)'

                    points_data['Tier'] = points_data['WA Points'].apply(get_ranking_tier)

                    tier_colors = alt.Scale(
                        domain=['Elite (1200+)', 'Top 50 (1100+)', 'Top 100 (1000+)', 'Competitive (900+)', 'Development (<900)'],
                        range=['#FFD700', '#C0C0C0', '#CD7F32', '#4169E1', '#808080']
                    )

                    # Create horizontal bar chart for WA Points
                    points_chart = alt.Chart(points_data).mark_bar().encode(
                        y=alt.Y('Athlete:N', title=None, sort='-x',
                               axis=alt.Axis(labelFontSize=11)),
                        x=alt.X('WA Points:Q', title='World Athletics Points',
                               scale=alt.Scale(domain=[0, max(points_data['WA Points'].max() * 1.1, 1300)])),
                        color=alt.Color('Tier:N', scale=tier_colors,
                                       legend=alt.Legend(title='Ranking Tier')),
                        tooltip=['Athlete', alt.Tooltip('WA Points:Q', format='.0f'), 'Tier']
                    ).properties(
                        height=max(200, len(points_data) * 30),
                        title='KSA Athletes by WA Ranking Points'
                    )

                    # Add reference lines for key thresholds
                    threshold_data = pd.DataFrame([
                        {'Threshold': 'Olympic Entry', 'Points': 1150},
                        {'Threshold': 'Top 100', 'Points': 1000}
                    ])

                    threshold_lines = alt.Chart(threshold_data).mark_rule(strokeDash=[5, 5], strokeWidth=2).encode(
                        x=alt.X('Points:Q'),
                        color=alt.value('#FF4444'),
                        tooltip=['Threshold', 'Points']
                    )

                    combined_chart = (points_chart + threshold_lines).configure_axis(
                        labelColor='white', titleColor='white', gridColor='#333'
                    ).configure_view(
                        strokeWidth=0, fill='#0e1117'
                    ).configure_legend(
                        labelColor='white', titleColor='white'
                    ).configure_title(
                        color='white'
                    )

                    st.altair_chart(combined_chart, use_container_width=True)

                    # Summary metrics
                    col_pt1, col_pt2, col_pt3, col_pt4 = st.columns(4)
                    with col_pt1:
                        st.metric("Highest Points", f"{points_data['WA Points'].max():.0f}")
                    with col_pt2:
                        st.metric("Average Points", f"{points_data['WA Points'].mean():.0f}")
                    with col_pt3:
                        elite_count = len(points_data[points_data['WA Points'] >= 1100])
                        st.metric("Top 50 Level", f"{elite_count} athletes")
                    with col_pt4:
                        olympic_ready = len(points_data[points_data['WA Points'] >= 1150])
                        st.metric("Olympic Entry Level", f"{olympic_ready} athletes")

                else:
                    st.info("No WA Points data available for KSA athletes in this event")
            else:
                st.info("WA Points column not available in dataset")

            # === QUALIFICATION STATUS ===
            st.markdown("---")
            st.markdown("### 🎫 Qualification Status")
            st.caption("Entry Standard and WA Rankings pathway assessment")

            # Get entry standard based on championship type
            if championship_type == "Olympics":
                entry_std = get_event_standard(selected_event, 'la_2028', selected_gender.lower())
                std_name = "LA 2028"
            elif championship_type == "World Championships":
                entry_std = get_event_standard(selected_event, 'tokyo_2025', selected_gender.lower())
                std_name = "Tokyo 2025"
            else:
                entry_std = None
                std_name = None

            if entry_std:
                st.markdown(f"**Entry Standard ({std_name}):** {format_benchmark_for_display(entry_std, event_type)}")

                # Table of qualification status
                qual_data = []
                for _, athlete in ksa_athletes.iterrows():
                    athlete_name = athlete['Athlete_Name']
                    perf = athlete['Result_numeric']
                    wa_points = athlete.get('wapoints', 0) if 'wapoints' in athlete and pd.notna(athlete.get('wapoints')) else 0

                    # Check entry standard
                    if event_type == 'time':
                        met_standard = perf <= entry_std
                        gap = perf - entry_std
                    else:
                        met_standard = perf >= entry_std
                        gap = entry_std - perf

                    # Determine WA Points status
                    if wa_points >= 1150:
                        points_status = "Likely"
                        points_icon = "🟢"
                    elif wa_points >= 1050:
                        points_status = "Possible"
                        points_icon = "🟡"
                    elif wa_points > 0:
                        points_status = "At Risk"
                        points_icon = "🔴"
                    else:
                        points_status = "N/A"
                        points_icon = "⚪"

                    # Overall status
                    if met_standard:
                        overall = "QUALIFIED"
                        overall_icon = "✅"
                    elif wa_points >= 1150:
                        overall = "LIKELY (Rankings)"
                        overall_icon = "🟢"
                    elif wa_points >= 1050:
                        overall = "POSSIBLE"
                        overall_icon = "🟡"
                    else:
                        overall = "NEEDS WORK"
                        overall_icon = "🔴"

                    qual_data.append({
                        'Athlete': athlete_name,
                        f'PB ({unit})': f"{perf:.2f}",
                        'Entry Standard': "MET" if met_standard else f"{format_gap(gap, event_type)} needed",
                        f'WA Points': f"{wa_points:.0f}" if wa_points > 0 else "N/A",
                        'Ranking Path': f"{points_icon} {points_status}",
                        'Overall': f"{overall_icon} {overall}"
                    })

                qual_df = pd.DataFrame(qual_data)
                st.dataframe(qual_df, hide_index=True, use_container_width=True)

                # Summary
                qualified_count = len([q for q in qual_data if "QUALIFIED" in q['Overall'] or "LIKELY" in q['Overall']])
                st.info(f"**{qualified_count}/{len(qual_data)}** athlete(s) with likely qualification path")

            else:
                st.info(f"Entry standards not available for {selected_event} ({championship_type})")

            # === DETAILED ATHLETE PROFILES ===
            st.markdown("---")
            st.markdown("### 👤 Individual Athlete Analysis")

            # Display each athlete with comprehensive analysis
            for idx, (_, athlete) in enumerate(ksa_athletes.iterrows()):
                athlete_name = athlete['Athlete_Name']

                with st.expander(f"{'🌟' if idx == 0 else '🏃'} {athlete_name}", expanded=(idx == 0)):
                    # Row 1: Key Metrics
                    col_a1, col_a2, col_a3, col_a4 = st.columns(4)

                    with col_a1:
                        st.metric("Personal Best", f"{athlete.get('Result', 'N/A')}")

                    with col_a2:
                        if 'wapoints' in athlete and pd.notna(athlete['wapoints']):
                            st.metric("WA Points", f"{athlete['wapoints']:.0f}")
                        else:
                            st.metric("WA Points", "N/A")

                    with col_a3:
                        # Prediction
                        prediction = predict_placement(athlete['Result_numeric'], final_summary, event_type)
                        st.metric("Predicted Finish", prediction['predicted_place'])

                    with col_a4:
                        # Assessment badge
                        assessment = prediction['assessment']
                        if "Medal" in assessment:
                            st.success(f"🏅 {assessment}")
                        elif "Finalist" in assessment:
                            st.info(f"✅ {assessment}")
                        elif "Competitive" in assessment:
                            st.warning(f"⚠️ {assessment}")
                        else:
                            st.error(f"📈 {assessment}")

                    # Row 2: Gap Analysis with progress bars AND last 5 performances
                    st.markdown("#### 📏 Gap to Championship Standards")

                    # Get last 5 performances for this athlete in this event
                    athlete_recent = df_all[
                        (df_all['Athlete_Name'] == athlete_name) &
                        (df_all['Event'] == selected_event)
                    ].copy()
                    athlete_recent = filter_fat_times_only(athlete_recent)

                    last_5_perfs = []
                    if not athlete_recent.empty and 'Start_Date' in athlete_recent.columns:
                        athlete_recent = athlete_recent.sort_values('Start_Date', ascending=False)
                        last_5 = athlete_recent.head(5)
                        last_5_perfs = last_5['Result_numeric'].dropna().tolist()

                    if not final_summary.empty:
                        gold_std = final_summary[final_summary['Rank'] == 1]['Average'].values
                        bronze_std = final_summary[final_summary['Rank'] == 3]['Average'].values
                        eighth_std = final_summary[final_summary['Rank'] == 8]['Average'].values

                        # Main gap analysis columns
                        col_g1, col_g2, col_g3, col_g4 = st.columns([1, 1, 1, 1.5])

                        with col_g1:
                            if len(gold_std) > 0:
                                if event_type == 'time':
                                    gap = athlete['Result_numeric'] - gold_std[0]
                                    progress = max(0, min(100, (1 - gap/gold_std[0]) * 100)) if gold_std[0] != 0 else 0
                                else:
                                    gap = gold_std[0] - athlete['Result_numeric']
                                    progress = max(0, min(100, (athlete['Result_numeric']/gold_std[0]) * 100)) if gold_std[0] != 0 else 0

                                direction = "behind" if gap > 0 else "ahead"
                                st.markdown(f"**🥇 Gold Standard:** {gold_std[0]:.2f}{unit}")
                                st.progress(int(progress))
                                color = "red" if gap > 0 else "green"
                                st.markdown(f":{color}[{abs(gap):.2f}{unit} {direction}]")

                        with col_g2:
                            if len(bronze_std) > 0:
                                if event_type == 'time':
                                    gap = athlete['Result_numeric'] - bronze_std[0]
                                    progress = max(0, min(100, (1 - gap/bronze_std[0]) * 100)) if bronze_std[0] != 0 else 0
                                else:
                                    gap = bronze_std[0] - athlete['Result_numeric']
                                    progress = max(0, min(100, (athlete['Result_numeric']/bronze_std[0]) * 100)) if bronze_std[0] != 0 else 0

                                direction = "behind" if gap > 0 else "ahead"
                                st.markdown(f"**🥉 Medal Line:** {bronze_std[0]:.2f}{unit}")
                                st.progress(int(progress))
                                color = "red" if gap > 0 else "green"
                                st.markdown(f":{color}[{abs(gap):.2f}{unit} {direction}]")

                        with col_g3:
                            if len(eighth_std) > 0:
                                if event_type == 'time':
                                    gap = athlete['Result_numeric'] - eighth_std[0]
                                    progress = max(0, min(100, (1 - gap/eighth_std[0]) * 100)) if eighth_std[0] != 0 else 0
                                else:
                                    gap = eighth_std[0] - athlete['Result_numeric']
                                    progress = max(0, min(100, (athlete['Result_numeric']/eighth_std[0]) * 100)) if eighth_std[0] != 0 else 0

                                direction = "behind" if gap > 0 else "ahead"
                                st.markdown(f"**🎯 Finalist Line:** {eighth_std[0]:.2f}{unit}")
                                st.progress(int(progress))
                                color = "red" if gap > 0 else "green"
                                st.markdown(f":{color}[{abs(gap):.2f}{unit} {direction}]")

                        with col_g4:
                            # Last 5 Performances mini-chart
                            st.markdown("**📊 Last 5 Performances:**")
                            if last_5_perfs:
                                # Create mini sparkline data
                                sparkline_data = pd.DataFrame({
                                    'Index': range(len(last_5_perfs)),
                                    'Performance': last_5_perfs,
                                    'Label': [f"#{i+1}: {p:.2f}" for i, p in enumerate(last_5_perfs)]
                                })

                                # Add standard lines for context
                                gold_v = gold_std[0] if len(gold_std) > 0 else None
                                eighth_v = eighth_std[0] if len(eighth_std) > 0 else None

                                # Mini sparkline chart
                                sparkline = alt.Chart(sparkline_data).mark_line(
                                    point=alt.OverlayMarkDef(filled=True, size=80),
                                    strokeWidth=2,
                                    color='#00CED1'
                                ).encode(
                                    x=alt.X('Index:O', axis=None),
                                    y=alt.Y('Performance:Q', scale=alt.Scale(zero=False, reverse=(event_type == 'time')), axis=None),
                                    tooltip=['Label']
                                )

                                # Add gold standard line if available
                                if gold_v:
                                    gold_line = alt.Chart(pd.DataFrame({'y': [gold_v]})).mark_rule(
                                        color='#FFD700', strokeDash=[4, 2], strokeWidth=1.5
                                    ).encode(y='y:Q')
                                    sparkline = sparkline + gold_line

                                if eighth_v:
                                    finalist_line = alt.Chart(pd.DataFrame({'y': [eighth_v]})).mark_rule(
                                        color='#4169E1', strokeDash=[4, 2], strokeWidth=1.5
                                    ).encode(y='y:Q')
                                    sparkline = sparkline + finalist_line

                                sparkline = sparkline.properties(height=80, width=150).configure_view(
                                    strokeWidth=0, fill='#1a1a1a'
                                )
                                st.altair_chart(sparkline, use_container_width=True)

                                # Show performance values
                                perf_str = " → ".join([f"{p:.2f}" for p in last_5_perfs])
                                st.caption(f"Recent: {perf_str}")

                                # Trend indicator
                                if len(last_5_perfs) >= 2:
                                    if event_type == 'time':
                                        trend = last_5_perfs[-1] - last_5_perfs[0]  # older - newer for time
                                        trend_dir = "improving ↗" if trend > 0 else "declining ↘" if trend < 0 else "stable →"
                                    else:
                                        trend = last_5_perfs[0] - last_5_perfs[-1]  # newer - older for distance
                                        trend_dir = "improving ↗" if trend > 0 else "declining ↘" if trend < 0 else "stable →"
                                    trend_color = "green" if "improving" in trend_dir else "red" if "declining" in trend_dir else "gray"
                                    st.markdown(f":{trend_color}[Trend: {trend_dir}]")
                            else:
                                st.caption("No recent performances found")

                    # Row 3: Athlete's performance history
                    st.markdown("#### 📊 Recent Performance History")

                    # Get all results for this athlete in this event
                    athlete_history = df_all[
                        (df_all['Athlete_Name'] == athlete_name) &
                        (df_all['Event'] == selected_event)
                    ].copy()

                    # Apply FAT filter
                    athlete_history = filter_fat_times_only(athlete_history)

                    if not athlete_history.empty and 'Start_Date' in athlete_history.columns:
                        athlete_history = athlete_history.sort_values('Start_Date', ascending=False)

                        # Last 3 years
                        three_years_ago = pd.Timestamp.now() - pd.DateOffset(years=3)
                        recent_history = athlete_history[athlete_history['Start_Date'] >= three_years_ago]

                        if not recent_history.empty:
                            col_h1, col_h2 = st.columns([2, 1])

                            with col_h1:
                                # Performance trend chart
                                if 'Result_numeric' in recent_history.columns:
                                    trend_chart = alt.Chart(recent_history).mark_line(
                                        point=alt.OverlayMarkDef(filled=True, size=60)
                                    ).encode(
                                        x=alt.X('Start_Date:T', title='Date'),
                                        y=alt.Y('Result_numeric:Q', title='Performance', scale=alt.Scale(zero=False)),
                                        tooltip=['Start_Date:T', 'Result:N', 'Competition:N']
                                    ).properties(
                                        height=200,
                                        title=f'{athlete_name} - Last 3 Years'
                                    ).configure_axis(
                                        labelColor='white', titleColor='white', gridColor='#333'
                                    ).configure_view(
                                        strokeWidth=0, fill='#0e1117'
                                    ).configure_title(
                                        color='white'
                                    )

                                    st.altair_chart(trend_chart, use_container_width=True)

                            with col_h2:
                                # Summary stats
                                st.markdown("**Last 3 Years Summary:**")
                                if event_type == 'time':
                                    st.markdown(f"- Best: {recent_history['Result_numeric'].min():.2f}{unit}")
                                    st.markdown(f"- Average: {recent_history['Result_numeric'].mean():.2f}{unit}")
                                    st.markdown(f"- Competitions: {len(recent_history)}")
                                else:
                                    st.markdown(f"- Best: {recent_history['Result_numeric'].max():.2f}{unit}")
                                    st.markdown(f"- Average: {recent_history['Result_numeric'].mean():.2f}{unit}")
                                    st.markdown(f"- Competitions: {len(recent_history)}")

                                # Trend indicator
                                if len(recent_history) >= 3:
                                    first_half = recent_history.iloc[len(recent_history)//2:]['Result_numeric'].mean()
                                    second_half = recent_history.iloc[:len(recent_history)//2]['Result_numeric'].mean()

                                    if event_type == 'time':
                                        improving = second_half < first_half
                                    else:
                                        improving = second_half > first_half

                                    if improving:
                                        st.success("📈 Improving trend")
                                    else:
                                        st.warning("📉 Declining trend")

                    # Row 4: Qualification pathway assessment
                    if not qual_summary.empty:
                        st.markdown("#### 🎯 Qualification Pathway")
                        col_q1, col_q2 = st.columns(2)

                        for round_idx, (_, round_data) in enumerate(qual_summary.iterrows()):
                            round_name = round_data['Round']
                            avg_qual = round_data['Average']
                            auto_qual = round_data['Fastest']

                            with col_q1 if round_idx == 0 else col_q2:
                                st.markdown(f"**{round_name}:**")
                                if event_type == 'time':
                                    auto_pass = athlete['Result_numeric'] <= auto_qual
                                    time_pass = athlete['Result_numeric'] <= avg_qual
                                else:
                                    auto_pass = athlete['Result_numeric'] >= auto_qual
                                    time_pass = athlete['Result_numeric'] >= avg_qual

                                if auto_pass:
                                    st.success(f"✅ Auto qualifier (Q) - PB beats {auto_qual:.2f}")
                                elif time_pass:
                                    st.info(f"⏱️ Time qualifier (q) potential - PB beats avg {avg_qual:.2f}")
                                else:
                                    gap = abs(athlete['Result_numeric'] - avg_qual)
                                    st.warning(f"⚠️ Needs {gap:.2f}{unit} improvement to avg qualifier")

            # === METHODOLOGY NOTES ===
            st.markdown("---")
            with st.expander("📖 Methodology Notes", expanded=False):
                st.markdown(METHODOLOGY_NOTES)
                st.markdown("---")
                st.markdown(BENCHMARK_METHODOLOGY)

    # --- Tab 4: Performance Prediction (like Power BI Image 4) ---
    with road_tabs[3]:
        st.subheader(f"📈 Predict Your Placement at {target_city} {target_year}")
        st.markdown(f"**{selected_gender}'s {selected_event}** - Enter a target performance to see predicted placement based on {selected_champ} history")

        event_type = get_event_type(selected_event)

        # Target performance input
        col_p1, col_p2 = st.columns(2)

        with col_p1:
            if event_type == 'time':
                target_input = st.text_input("Target Performance (e.g., 10.05 or 1:45.00)",
                                            value="10.00", key=f"target_{championship_type}")
                # Parse the input
                try:
                    if ':' in target_input:
                        parts = target_input.split(':')
                        if len(parts) == 2:
                            target_numeric = float(parts[0]) * 60 + float(parts[1])
                        else:
                            target_numeric = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    else:
                        target_numeric = float(target_input)
                except:
                    target_numeric = None
                    st.error("Invalid time format")
            else:
                target_numeric = st.number_input("Target Performance (meters/points)",
                                                value=8.00, step=0.01, key=f"target_{championship_type}")

        with col_p2:
            st.markdown("**Target Analysis**")
            if target_numeric:
                final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age, include_indoor)
                prediction = predict_placement(target_numeric, final_summary, event_type)

                st.metric("Predicted Place", prediction['predicted_place'])
                st.markdown(f"**Assessment:** {prediction['assessment']}")

        # Add Probability Gauge for target performance
        if target_numeric:
            st.markdown("---")
            st.markdown("#### 🎯 Advancement Probability for Target Performance")

            # Get historical benchmarks
            target_benchmarks = get_default_benchmarks(selected_event, selected_gender)
            if target_benchmarks:
                historical_cutoffs = {
                    'heat': target_benchmarks.get('heat', {}).get('cutoff') or target_benchmarks.get('heat', {}).get('average'),
                    'semi': target_benchmarks.get('semi', {}).get('cutoff') or target_benchmarks.get('semi', {}).get('average'),
                    'final': target_benchmarks.get('final', {}).get('cutoff') or target_benchmarks.get('final', {}).get('average'),
                    'medal': target_benchmarks.get('medal', {}).get('average')
                }
                historical_cutoffs = {k: v for k, v in historical_cutoffs.items() if v is not None}

                if historical_cutoffs:
                    target_probs = calculate_advancement_probability(target_numeric, historical_cutoffs, event_type)
                    prob_chart = probability_gauge(target_probs, title='Probability of Advancing Each Round')
                    st.altair_chart(prob_chart, use_container_width=True)

        # Historical placement probability table (like Power BI Image 4)
        st.markdown("---")
        st.markdown("#### Target Performance in Final by Rank")

        final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age, include_indoor)

        if not final_summary.empty and target_numeric:
            # Calculate probability of beating each rank
            probability_data = []
            for _, row in final_summary.iterrows():
                rank = int(row['Rank'])
                avg = row['Average']
                count = row['Count']

                # Simple probability: what % of historical results at this rank would the target beat?
                if event_type == 'time':
                    better_than_avg = target_numeric < avg
                else:
                    better_than_avg = target_numeric > avg

                probability_data.append({
                    'Rank': rank,
                    'Historical Avg': f"{avg:.2f}",
                    'Sample Size': count,
                    'Target Better': "✅ Yes" if better_than_avg else "❌ No",
                    'Gap': f"{abs(target_numeric - avg):.2f}"
                })

            prob_df = pd.DataFrame(probability_data)
            st.dataframe(prob_df, hide_index=True, use_container_width=True)

        # === KSA ATHLETES PREDICTION TABLE (Power BI Style) ===
        st.markdown("---")
        st.markdown("### 🇸🇦 KSA Athletes Result Prediction")

        ksa_athletes = get_ksa_athletes_for_event(df_all, selected_gender, selected_event)
        unit = "s" if event_type == 'time' else "m" if event_type == 'distance' else "pts"

        if not ksa_athletes.empty and not final_summary.empty:
            # Get standards for gap calculation (once, not in loop)
            gold_std = final_summary[final_summary['Rank'] == 1]['Average'].values
            bronze_std = final_summary[final_summary['Rank'] == 3]['Average'].values
            eighth_std = final_summary[final_summary['Rank'] == 8]['Average'].values

            # Get all projections in one cached batch call
            athlete_names = ksa_athletes['Athlete_Name'].tolist()
            projections = get_batch_athlete_projections(df_all, tuple(athlete_names), selected_event, event_type)

            # Build prediction table for all KSA athletes WITH PROJECTIONS
            prediction_rows = []
            for _, athlete in ksa_athletes.iterrows():
                athlete_name = athlete['Athlete_Name']
                result = athlete['Result_numeric']

                # Get projection from batch results
                proj_data = projections.get(athlete_name, {})
                projected = proj_data.get('projected') or result
                trend_symbol = proj_data.get('trend_symbol', '?')
                form_score = proj_data.get('form_score')

                # Calculate gaps based on PROJECTED performance
                gold_gap = (projected - gold_std[0]) if len(gold_std) > 0 and event_type == 'time' else (gold_std[0] - projected) if len(gold_std) > 0 else None
                medal_gap = (projected - bronze_std[0]) if len(bronze_std) > 0 and event_type == 'time' else (bronze_std[0] - projected) if len(bronze_std) > 0 else None

                # Get prediction once
                proj_prediction = predict_placement(projected, final_summary, event_type)

                prediction_rows.append({
                    'Athlete': athlete_name,
                    f'PB ({unit})': f"{result:.2f}",
                    f'Projected ({unit})': f"{projected:.2f}",
                    'Trend': trend_symbol,
                    'Form Score': f"{form_score:.0f}/100" if form_score else 'N/A',
                    'Predicted Finish': proj_prediction['predicted_place'],
                    'Assessment': proj_prediction['assessment'],
                    f'Gap to Gold': format_gap(gold_gap, event_type) if gold_gap else 'N/A',
                    f'Gap to Medal': format_gap(medal_gap, event_type) if medal_gap else 'N/A'
                })

            pred_df = pd.DataFrame(prediction_rows)

            # Style the dataframe
            st.dataframe(pred_df, hide_index=True, use_container_width=True)

            # Prediction visualization chart (like Power BI)
            st.markdown("---")
            st.markdown("### 📊 Visual Prediction")

            # Create data for visualization
            chart_data = []
            for _, athlete in ksa_athletes.iterrows():
                chart_data.append({
                    'Athlete': athlete['Athlete_Name'],
                    'Performance': athlete['Result_numeric'],
                    'Type': 'KSA Athlete'
                })

            # Add championship standards
            if len(gold_std) > 0:
                chart_data.append({'Athlete': '🥇 Gold Standard', 'Performance': gold_std[0], 'Type': 'Gold'})
            if len(bronze_std) > 0:
                chart_data.append({'Athlete': '🥉 Medal Line', 'Performance': bronze_std[0], 'Type': 'Medal'})
            if len(eighth_std) > 0:
                chart_data.append({'Athlete': '🎯 Finalist Line', 'Performance': eighth_std[0], 'Type': 'Finalist'})

            chart_df = pd.DataFrame(chart_data)

            # Create lollipop/dot chart
            base = alt.Chart(chart_df).encode(
                y=alt.Y('Athlete:N', title=None, sort=None,
                       axis=alt.Axis(labelFontSize=11)),
                x=alt.X('Performance:Q', title=f'Performance ({unit})',
                       scale=alt.Scale(zero=False)),
                color=alt.Color('Type:N',
                               scale=alt.Scale(domain=['KSA Athlete', 'Gold', 'Medal', 'Finalist'],
                                              range=['#00FF7F', '#FFD700', '#CD7F32', '#4169E1']),
                               legend=alt.Legend(title='Category'))
            )

            points = base.mark_circle(size=150)
            line_to_zero = base.mark_rule(size=3)

            chart = (points + line_to_zero).properties(
                height=max(200, len(chart_data) * 30),
                title='KSA Athletes vs Championship Standards'
            ).configure_axis(
                labelColor='white', titleColor='white', gridColor='#333'
            ).configure_view(
                strokeWidth=0, fill='#0e1117'
            ).configure_legend(
                labelColor='white', titleColor='white'
            ).configure_title(
                color='white'
            )

            st.altair_chart(chart, use_container_width=True)

        else:
            st.info("No KSA athletes or championship data available for prediction")

    # --- Tab 5: Qualification Points Distribution (Olympics & World Championships only) ---
    if qual_points_tab_idx is not None:
      with road_tabs[qual_points_tab_idx]:
        st.subheader(f"{target_city} {target_year} Qualification Points Analysis")

        # === QUALIFICATION SYSTEM EXPLANATION ===
        with st.expander("World Athletics Qualification System - How It Works", expanded=False):
            st.markdown("""
            ### Dual Pathway Qualification System

            The World Athletics Olympic qualification system uses a **dual pathway** approach:

            **1. Entry Standards (Performance-Based) - ~50% of quota**
            - Athletes can qualify by achieving specific entry standards (times/distances)
            - Standards must be achieved within the qualifying window
            - Maximum 3 athletes per NOC can qualify via entry standards per event

            **2. World Rankings (Points-Based) - Remaining ~50%**
            - Athletes ranked highest by World Athletics Rankings fill remaining spots
            - Rankings based on average of best performances in 12-18 month period
            - Points = Result Score + Placing Score (varies by competition level)

            ### How WA Points Are Calculated
            - **Result Score:** Based on World Athletics Scoring Tables (performance converted to points)
            - **Placing Score:** Bonus points for finishing position (up to 350 pts for winning Olympics/World Champs)
            - **Final Score:** Average of best performances within ranking period

            ### Key Thresholds (Typical Olympic Level)
            | Tier | Points Range | Description |
            |------|-------------|-------------|
            | **Elite** | 1200+ | Strong medal contender |
            | **Qualified** | 1100-1199 | Likely to qualify via rankings |
            | **Competitive** | 1000-1099 | May qualify depending on field depth |
            | **Developing** | <1000 | Needs significant improvement |

            *Note: LA 2028 specific entry standards not yet published. Expected 2026-2027.*
            """)

        st.markdown("---")

        # === DATE PERIOD SLIDER ===
        st.markdown("### Select Analysis Period")
        col_date1, col_date2 = st.columns([2, 1])

        with col_date1:
            # Get available date range from data
            if 'Start_Date' in df_all.columns:
                df_dates = df_all[df_all['Start_Date'].notna()].copy()
                if not df_dates.empty:
                    min_date = df_dates['Start_Date'].min()
                    max_date = df_dates['Start_Date'].max()

                    # Convert to datetime if needed
                    if isinstance(min_date, str):
                        min_date = pd.to_datetime(min_date)
                    if isinstance(max_date, str):
                        max_date = pd.to_datetime(max_date)

                    # Default to last 12 months
                    default_start = max(min_date, max_date - pd.DateOffset(months=12))

                    date_range = st.slider(
                        "Analysis Date Range",
                        min_value=min_date.to_pydatetime() if hasattr(min_date, 'to_pydatetime') else min_date,
                        max_value=max_date.to_pydatetime() if hasattr(max_date, 'to_pydatetime') else max_date,
                        value=(default_start.to_pydatetime() if hasattr(default_start, 'to_pydatetime') else default_start,
                               max_date.to_pydatetime() if hasattr(max_date, 'to_pydatetime') else max_date),
                        format="YYYY-MM-DD",
                        key=f"qual_date_range_{championship_type}"
                    )
                else:
                    date_range = None
                    st.warning("No date data available")
            else:
                date_range = None

        with col_date2:
            st.info(f"**Period:** {date_range[0].strftime('%b %Y') if date_range else 'N/A'} - {date_range[1].strftime('%b %Y') if date_range else 'N/A'}")

        # Get data for selected period
        df_qual_points = df_all.copy()

        # Filter by gender
        if 'Gender' in df_qual_points.columns:
            df_qual_points = df_qual_points[df_qual_points['Gender'] == selected_gender]

        # Filter by date range
        if date_range and 'Start_Date' in df_qual_points.columns:
            df_qual_points['Start_Date'] = pd.to_datetime(df_qual_points['Start_Date'], errors='coerce')
            df_qual_points = df_qual_points[
                (df_qual_points['Start_Date'] >= pd.Timestamp(date_range[0])) &
                (df_qual_points['Start_Date'] <= pd.Timestamp(date_range[1]))
            ]

        # Check for WA_Points column
        wa_points_col = None
        for col in ['WA_Points', 'wapoints', 'WaPoints', 'Points']:
            if col in df_qual_points.columns:
                wa_points_col = col
                break

        if wa_points_col is None:
            st.warning("No WA Points data available. Ensure database includes 'wapoints' column.")
        else:
            # =====================================================
            # SINGLE EVENT QUOTA-BASED ANALYSIS (User's preferred view)
            # =====================================================
            st.markdown("### KSA Qualification Positioning")
            st.markdown(f"**Current Event: {selected_event}** ({selected_gender})")

            # View mode toggle
            view_mode_col1, view_mode_col2 = st.columns([2, 1])
            with view_mode_col1:
                view_mode = st.radio(
                    "Qualification View",
                    ["Points (Ranking)", "Automatic (Entry Standard)"],
                    horizontal=True,
                    key=f"qual_view_mode_{championship_type}_{selected_event}"
                )
            with view_mode_col2:
                show_previous_cycle = st.checkbox(
                    "Overlay previous cycle",
                    key=f"prev_cycle_{championship_type}_{selected_event}",
                    help="Show 2023-2024 cycle for comparison"
                )

            # Get quota info for this event
            quota_info = get_event_quota(selected_event)
            ranking_quota = quota_info.get('ranking_quota', 24)

            if view_mode == "Points (Ranking)":
                st.markdown(f"""
                **How to read this chart:**
                - Box plot shows WA Points distribution for top **{ranking_quota} athletes** (ranking quota)
                - **Green dots** = KSA athlete's best 5 WA Points performances
                - **Gold square** = Average of best 5 (ranking score)
                - **Red dashed line** = Median - if gold square is at/above median, qualification likely
                """)

                # Create the quota-based box plot with spinner
                with st.spinner(f"Analyzing {selected_event} qualification data..."):
                    chart = create_qualification_boxplot(
                        df_all, selected_event, selected_gender,
                        championship='tokyo_2025' if 'Tokyo' in target_city else 'la_2028',
                        date_start=date_range[0] if date_range else None,
                        date_end=date_range[1] if date_range else None,
                        show_previous=show_previous_cycle
                    )

                if chart:
                    st.altair_chart(chart, use_container_width=True)

                    # Show metrics
                    ksa_data = calculate_ksa_ranking_score(
                        df_all, selected_event, selected_gender,
                        date_range[0] if date_range else None,
                        date_range[1] if date_range else None
                    )
                    quota_df = get_qualification_quota_distribution(
                        df_all, selected_event, selected_gender, ranking_quota,
                        date_range[0] if date_range else None,
                        date_range[1] if date_range else None
                    )

                    if not quota_df.empty and ksa_data:
                        median_points = quota_df['wapoints'].median()
                        min_points = quota_df['wapoints'].min()

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("KSA Avg Best 5", f"{ksa_data['avg_wapoints']:.0f} pts")
                        with col2:
                            st.metric("Quota Median", f"{median_points:.0f} pts")
                        with col3:
                            gap = ksa_data['avg_wapoints'] - median_points
                            st.metric("Gap to Median", f"{gap:+.0f} pts",
                                     delta_color="normal" if gap >= 0 else "inverse")
                        with col4:
                            status = "Likely" if ksa_data['avg_wapoints'] >= median_points else "At Risk"
                            emoji = "✅" if gap >= 0 else "⚠️"
                            st.metric("Status", f"{emoji} {status}")
                    elif not quota_df.empty:
                        st.info(f"No KSA athletes found competing in {selected_event} during this period.")
                else:
                    st.info(f"No WA Points data available for {selected_event}.")

            else:
                # Automatic (Entry Standard) view
                entry_std = get_event_standard(
                    selected_event,
                    'tokyo_2025' if 'Tokyo' in target_city else 'la_2028',
                    selected_gender.lower()
                )

                if entry_std:
                    event_type = get_event_type(selected_event)
                    unit = "s" if event_type == 'time' else "m" if event_type == 'distance' else "pts"

                    st.markdown(f"""
                    **Entry Standard:** {entry_std:.2f}{unit} for {target_city} {target_year}

                    Athletes who achieve this mark automatically qualify (subject to NOC allocation).
                    """)

                    # Get KSA athletes' best results for this event
                    ksa_event_df = df_qual_points[
                        (df_qual_points['Event'] == selected_event) &
                        (df_qual_points['Athlete_Country'].str.upper().str.contains('KSA|SAU|SAUDI', na=False) if 'Athlete_Country' in df_qual_points.columns else pd.Series([False] * len(df_qual_points)))
                    ]

                    if not ksa_event_df.empty and 'Result_numeric' in ksa_event_df.columns:
                        best_result = ksa_event_df['Result_numeric'].min() if event_type == 'time' else ksa_event_df['Result_numeric'].max()
                        best_athlete = ksa_event_df.loc[
                            ksa_event_df['Result_numeric'].idxmin() if event_type == 'time' else ksa_event_df['Result_numeric'].idxmax()
                        ]

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Entry Standard", f"{entry_std:.2f}{unit}")
                        with col2:
                            st.metric("KSA Best", f"{best_result:.2f}{unit}",
                                     help=f"By {best_athlete.get('Athlete_Name', 'Unknown')}")
                        with col3:
                            gap = entry_std - best_result if event_type == 'time' else best_result - entry_std
                            qualified = gap <= 0 if event_type == 'time' else gap >= 0
                            st.metric("Gap to Standard",
                                     f"{abs(gap):.2f}{unit} {'ahead' if qualified else 'needed'}",
                                     delta_color="normal" if qualified else "inverse")

                        if qualified:
                            st.success(f"✅ {best_athlete.get('Athlete_Name', 'Unknown')} has achieved the entry standard!")
                        else:
                            st.warning(f"⚠️ KSA athletes need to improve by {abs(gap):.2f}{unit} to achieve entry standard.")
                    else:
                        st.info(f"No KSA athletes with results found for {selected_event}.")
                else:
                    st.info(f"No entry standard defined for {selected_event}.")

            st.markdown("---")

            # =====================================================
            # MULTI-EVENT COMPARISON (Existing functionality)
            # =====================================================
            st.markdown("### Multi-Event WA Points Comparison")

            # Get events with sufficient WA Points data
            events_with_points = df_qual_points.groupby('Event')[wa_points_col].count()
            events_with_points = events_with_points[events_with_points >= 5].index.tolist()

            # Event filter for this analysis
            default_events = ['100m', '200m', '400m', 'Pole Vault', 'Triple Jump', 'Shot Put']
            default_events = [e for e in default_events if e in events_with_points]

            if not events_with_points:
                st.warning("No events with sufficient WA Points data found in selected period.")
            else:
                selected_events_qa = st.multiselect(
                    "Events to Compare",
                    events_with_points,
                    default=default_events[:6] if default_events else events_with_points[:6],
                    key=f"qual_points_events_{championship_type}"
                )

                if selected_events_qa:
                    # Filter to selected events
                    df_events = df_qual_points[df_qual_points['Event'].isin(selected_events_qa)].copy()

                    # Convert WA Points to numeric
                    df_events[wa_points_col] = pd.to_numeric(df_events[wa_points_col], errors='coerce')
                    df_events = df_events.dropna(subset=[wa_points_col])

                    if df_events.empty:
                        st.warning("No valid WA Points data for selected events.")
                    else:
                        # Identify KSA athletes
                        if 'Athlete_Country' in df_events.columns:
                            ksa_mask = df_events['Athlete_Country'].str.upper().str.contains('KSA|SAU|SAUDI', na=False)
                        elif 'Athlete_CountryCode' in df_events.columns:
                            ksa_mask = df_events['Athlete_CountryCode'].str.upper() == 'KSA'
                        else:
                            ksa_mask = pd.Series([False] * len(df_events))

                        df_ksa = df_events[ksa_mask].copy()
                        df_others = df_events[~ksa_mask].copy()

                        # === TOP QUALIFICATION POINTS BY EVENT ===
                        st.markdown("### Top Qualification Points by Event")
                        st.markdown("*Shows the highest WA Points achieved by any athlete in each event during the selected period, with KSA athletes' best points for comparison.*")

                        # Calculate top points per event
                        top_points_data = []
                        for event in selected_events_qa:
                            event_data = df_events[df_events['Event'] == event]
                            if not event_data.empty:
                                # Get top performer
                                top_idx = event_data[wa_points_col].idxmax()
                                top_row = event_data.loc[top_idx]

                                # Get KSA best for this event
                                ksa_event = df_ksa[df_ksa['Event'] == event]
                                if not ksa_event.empty:
                                    ksa_best_idx = ksa_event[wa_points_col].idxmax()
                                    ksa_best_row = ksa_event.loc[ksa_best_idx]
                                    ksa_best_points = ksa_best_row[wa_points_col]
                                    ksa_best_name = ksa_best_row.get('Athlete_Name', 'Unknown')
                                else:
                                    ksa_best_points = None
                                    ksa_best_name = '-'

                                top_points_data.append({
                                    'Event': event,
                                    'Top Points': round(top_row[wa_points_col], 0),
                                    'Top Athlete': top_row.get('Athlete_Name', 'Unknown'),
                                    'Top Country': top_row.get('Athlete_Country', top_row.get('Athlete_CountryCode', 'N/A')),
                                    'KSA Best Points': round(ksa_best_points, 0) if ksa_best_points else '-',
                                    'KSA Athlete': ksa_best_name,
                                    'Gap to Top': round(top_row[wa_points_col] - ksa_best_points, 0) if ksa_best_points else '-',
                                    'Athletes Count': len(event_data),
                                    'Avg Points': round(event_data[wa_points_col].mean(), 1)
                                })

                        if top_points_data:
                            top_df = pd.DataFrame(top_points_data)
                            st.dataframe(top_df, hide_index=True, use_container_width=True)

                        # === QUOTA-BASED BOX PLOT WITH KSA OVERLAY ===
                        st.markdown("---")
                        st.markdown("### Qualification Quota Distribution by Event")
                        st.markdown("""
                        *Box plot shows WA Points distribution for athletes within the **ranking quota** (top 24 or event-specific).*
                        - **Green dots** = KSA athlete's best 5 performances
                        - **Gold squares** = KSA average of best 5 (ranking score)
                        - **Red dashed line** = Median (if KSA average is at/above = likely to qualify)
                        """)

                        # Use cached batch function for better performance
                        with st.spinner("Loading quota analysis..."):
                            # Store df_all in session state for the cached function
                            st.session_state['_cached_df_all'] = df_all

                            # Create a hash of the dataframe shape for caching
                            df_hash = f"{len(df_all)}_{hash(tuple(selected_events_qa))}"
                            date_start_str = str(date_range[0]) if date_range else None
                            date_end_str = str(date_range[1]) if date_range else None

                            # Get all quota data at once (cached)
                            batch_data = get_all_events_quota_data(
                                df_hash, tuple(selected_events_qa), selected_gender,
                                date_start_str, date_end_str
                            )

                            quota_data_list = batch_data['quota_data']
                            ksa_best5_list = batch_data['ksa_best5']
                            ksa_avg_list = batch_data['ksa_avg']
                            median_data = batch_data['medians']

                        if quota_data_list:
                            # Combine all quota data
                            all_quota_df = pd.concat(quota_data_list, ignore_index=True)

                            # Create box plot of quota distribution
                            box = alt.Chart(all_quota_df).mark_boxplot(
                                extent='min-max',
                                size=30,
                                color='#4169E1',
                                opacity=0.7
                            ).encode(
                                x=alt.X('Event:N', title='Event', axis=alt.Axis(labelAngle=-45)),
                                y=alt.Y('wapoints:Q', title='WA Points', scale=alt.Scale(zero=False))
                            )

                            layers = [box]

                            # Add median reference lines
                            if median_data:
                                median_df = pd.DataFrame(median_data)
                                median_marks = alt.Chart(median_df).mark_tick(
                                    color='#FF6B6B',
                                    thickness=3,
                                    size=25
                                ).encode(
                                    x=alt.X('Event:N'),
                                    y=alt.Y('median:Q')
                                )
                                layers.append(median_marks)

                            # Add KSA best 5 dots (green)
                            if ksa_best5_list:
                                all_ksa_best5 = pd.concat(ksa_best5_list, ignore_index=True)
                                ksa_dots = alt.Chart(all_ksa_best5).mark_circle(
                                    size=120,
                                    color='#00FF7F',
                                    opacity=0.9
                                ).encode(
                                    x=alt.X('Event:N'),
                                    y=alt.Y('wapoints:Q'),
                                    tooltip=[
                                        alt.Tooltip('Athlete_Name:N', title='Athlete'),
                                        alt.Tooltip('Event:N', title='Event'),
                                        alt.Tooltip('wapoints:Q', title='WA Points', format='.0f'),
                                        alt.Tooltip('Result:N', title='Result')
                                    ]
                                )
                                layers.append(ksa_dots)

                            # Add KSA average squares (gold)
                            if ksa_avg_list:
                                ksa_avg_df = pd.DataFrame(ksa_avg_list)
                                ksa_squares = alt.Chart(ksa_avg_df).mark_square(
                                    size=200,
                                    color='#FFD700',
                                    stroke='black',
                                    strokeWidth=2
                                ).encode(
                                    x=alt.X('Event:N'),
                                    y=alt.Y('avg_wapoints:Q'),
                                    tooltip=[
                                        alt.Tooltip('Athlete_Name:N', title='Athlete'),
                                        alt.Tooltip('Event:N', title='Event'),
                                        alt.Tooltip('avg_wapoints:Q', title='Avg Best 5', format='.0f'),
                                        alt.Tooltip('count:Q', title='Performances')
                                    ]
                                )
                                layers.append(ksa_squares)

                            chart = alt.layer(*layers).properties(
                                height=450,
                                title=alt.TitleParams(
                                    text=f'{target_city} {target_year} - Qualification Quota Distribution',
                                    subtitle=f'{selected_gender} | Green=Best 5 | Gold=Average | Red=Median',
                                    color='white',
                                    subtitleColor='#888',
                                    fontSize=16
                                )
                            ).configure_axis(
                                labelColor='white',
                                titleColor='white',
                                gridColor='#333',
                                labelFontSize=11,
                                titleFontSize=12
                            ).configure_view(
                                strokeWidth=0
                            ).configure_legend(
                                labelColor='white',
                                titleColor='white',
                                labelFontSize=10
                            )

                            st.altair_chart(chart, use_container_width=True)

                            # Show qualification status summary
                            if ksa_avg_list and median_data:
                                st.markdown("#### KSA Qualification Status by Event")
                                status_data = []
                                median_dict = {m['Event']: m['median'] for m in median_data}
                                for avg in ksa_avg_list:
                                    event = avg['Event']
                                    if event in median_dict:
                                        gap = avg['avg_wapoints'] - median_dict[event]
                                        status = "Likely" if gap >= 0 else "At Risk"
                                        status_data.append({
                                            'Event': event,
                                            'Athlete': avg['Athlete_Name'],
                                            'Avg Best 5': round(avg['avg_wapoints'], 0),
                                            'Quota Median': round(median_dict[event], 0),
                                            'Gap': round(gap, 0),
                                            'Status': f"{'✅' if gap >= 0 else '⚠️'} {status}"
                                        })
                                if status_data:
                                    status_df = pd.DataFrame(status_data)
                                    st.dataframe(status_df, hide_index=True, use_container_width=True)
                        else:
                            st.info("No quota data available for selected events.")

                        # === SUMMARY STATISTICS TABLE ===
                        st.markdown("---")
                        st.markdown("### Event Summary Statistics")

                        summary_stats = []
                        for event in selected_events_qa:
                            event_data = df_events[df_events['Event'] == event][wa_points_col]
                            if len(event_data) > 0:
                                summary_stats.append({
                                    'Event': event,
                                    'Athletes Count': len(event_data),
                                    'Average Points': round(event_data.mean(), 2),
                                    'Max Points': round(event_data.max(), 1),
                                    'Min Points': round(event_data.min(), 1)
                                })

                        if summary_stats:
                            stats_df = pd.DataFrame(summary_stats)
                            st.dataframe(stats_df, hide_index=True, use_container_width=True)

                        # === KSA ATHLETES DETAILED BREAKDOWN ===
                        if not df_ksa.empty:
                            st.markdown("---")
                            st.markdown("### KSA Athletes Points Breakdown")

                            ksa_summary = df_ksa.groupby(['Athlete_Name', 'Event']).agg({
                                wa_points_col: ['max', 'mean', 'count']
                            }).round(1)
                            ksa_summary.columns = ['Best Points', 'Avg Points', 'Performances']
                            ksa_summary = ksa_summary.reset_index()
                            ksa_summary = ksa_summary.sort_values('Best Points', ascending=False)

                            st.dataframe(ksa_summary, hide_index=True, use_container_width=True)

                            # Qualification assessment
                            st.markdown("### Qualification Assessment")
                            for _, row in ksa_summary.iterrows():
                                points = row['Best Points']
                                athlete = row['Athlete_Name']
                                event = row['Event']

                                if points >= 1200:
                                    status = "Elite - Strong medal contender"
                                    color = "green"
                                elif points >= 1100:
                                    status = "Qualified - Likely to qualify via rankings"
                                    color = "blue"
                                elif points >= 1000:
                                    status = "Competitive - May qualify depending on field"
                                    color = "orange"
                                else:
                                    status = "Developing - Needs improvement"
                                    color = "red"

                                st.markdown(f"**{athlete}** ({event}): {points:.0f} pts - :{color}[{status}]")
                        else:
                            st.info("No KSA athletes found in selected events during this period.")
                else:
                    st.info("Select at least one event to view the analysis.")

    # --- Tab: One-Pager Report ---
    with road_tabs[one_pager_tab_idx]:
        st.subheader(f"📋 {selected_event} One-Pager - Road to {target_city}")

        # Generate comprehensive one-pager
        final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age, include_indoor)
        qual_summary = get_qualification_by_round(df_all, selected_champ, selected_gender, selected_event, include_indoor)
        ksa_athletes = get_ksa_athletes_for_event(df_all, selected_gender, selected_event)
        event_type = get_event_type(selected_event)

        # Create exportable report
        report_text = f"""
{'='*60}
{selected_gender.upper()}'S {selected_event.upper()} - ROAD TO {target_city.upper()} {target_year}
{'='*60}

CHAMPIONSHIP: {championship_type}
BENCHMARK DATA: Historical {selected_champ} performances

{'='*60}
WHAT IT TAKES TO WIN
{'='*60}
"""

        if not final_summary.empty:
            gold = final_summary[final_summary['Rank'] == 1]
            silver = final_summary[final_summary['Rank'] == 2]
            bronze = final_summary[final_summary['Rank'] == 3]
            eighth = final_summary[final_summary['Rank'] == 8]

            if not gold.empty:
                report_text += f"🥇 GOLD: {gold['Average'].values[0]:.2f} (avg) | Best: {gold.iloc[0].get('Fastest', gold.iloc[0].get('Best', 'N/A'))}\n"
            if not silver.empty:
                report_text += f"🥈 SILVER: {silver['Average'].values[0]:.2f} (avg)\n"
            if not bronze.empty:
                report_text += f"🥉 BRONZE: {bronze['Average'].values[0]:.2f} (avg)\n"
            if not eighth.empty:
                report_text += f"📍 FINAL (8th): {eighth['Average'].values[0]:.2f} (avg)\n"

        report_text += f"""
{'='*60}
KSA ATHLETES - DETAILED FORM ANALYSIS
{'='*60}
"""
        if not ksa_athletes.empty:
            for _, athlete in ksa_athletes.iterrows():
                athlete_name = athlete['Athlete_Name']
                form = get_athlete_recent_form(df_all, athlete_name, selected_event, num_races=3)

                report_text += f"\n━━━ {athlete_name.upper()} ━━━\n"
                report_text += f"📊 CURRENT STATUS:\n"
                pb_str = f"{form['personal_best']:.2f}" if form['personal_best'] else 'N/A'
                sb_str = f"{form['season_best']:.2f}" if form['season_best'] else 'N/A'
                avg_str = f"{form['average']:.2f}" if form['average'] else 'N/A'
                report_text += f"   Personal Best: {pb_str}\n"
                report_text += f"   Season Best: {sb_str}\n"
                report_text += f"   Last 3 Average: {avg_str}\n"
                report_text += f"   Form Trend: {form['trend']}\n"

                # Last 3 races
                report_text += f"\n📅 LAST 3 RACES:\n"
                if form['last_races']:
                    for i, race in enumerate(form['last_races'], 1):
                        date_str = str(race['date'])[:10] if race['date'] != 'N/A' else 'N/A'
                        report_text += f"   {i}. {race['result']} ({date_str})\n"
                else:
                    report_text += "   No recent race data available\n"

                # WA Points if available
                if 'wapoints' in athlete and pd.notna(athlete['wapoints']):
                    report_text += f"\n🏆 WA POINTS: {athlete['wapoints']:.0f}\n"

                # Prediction
                prediction = predict_placement(athlete['Result_numeric'], final_summary, event_type)
                report_text += f"\n🎯 CHAMPIONSHIP PREDICTION:\n"
                report_text += f"   Predicted Finish: {prediction['predicted_place']}\n"
                report_text += f"   Assessment: {prediction['assessment']}\n"
        else:
            report_text += "No KSA athletes currently competing in this event.\n"

        report_text += f"""
{'='*60}
QUALIFICATION PATHWAY
{'='*60}
"""
        if not qual_summary.empty:
            for _, row in qual_summary.iterrows():
                report_text += f"• {row['Round']}: Avg {row['Average']:.2f} | Range: {row['Fastest']:.2f} - {row['Slowest']:.2f}\n"

        report_text += f"""

Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        st.text_area("One-Pager Preview", report_text, height=400)

        st.download_button(
            label="📥 Download One-Pager",
            data=report_text,
            file_name=f"Road_to_{target_city}_{selected_event.replace(' ', '_')}_{selected_gender}.txt",
            mime="text/plain"
        )


###################################
# 12) Event Analysis - What It Takes to Win
###################################
def show_event_analysis(df_all):
    """
    Comprehensive event analysis - what it takes to win each event.
    One-pager summaries for pre-competition reports.
    """
    st.title("📊 Event Analysis - What It Takes to Win")
    st.markdown("Deep analysis of each athletics event with historical performance standards")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        gender_opts = ['Men', 'Women']
        if 'Gender' in df_all.columns:
            gender_opts = sorted(df_all['Gender'].dropna().unique().tolist())
        selected_gender = st.selectbox("Gender", gender_opts, key="event_analysis_gender")

    with col2:
        champ_opts = list(MAJOR_COMPETITIONS_CID.keys())
        selected_champ = st.selectbox("Championship Level", champ_opts, key="event_analysis_champ")

    with col3:
        age_opts = ['Senior', 'U20', 'U18']
        selected_age = st.selectbox("Age Group", age_opts, key="event_analysis_age")

    # Event selector
    if 'Event' in df_all.columns:
        event_opts = sorted(df_all['Event'].dropna().unique().tolist())
        selected_event = st.selectbox("Select Event", event_opts, key="event_analysis_event")
    else:
        st.error("No Event column in data")
        return

    st.markdown("---")

    # Event type determination
    event_type = get_event_type(selected_event)
    unit = "seconds" if event_type == 'time' else "meters" if event_type == 'distance' else "points"

    # Header with event info
    st.header(f"{selected_gender}'s {selected_event}")

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(f"**Event Type:** {'Track' if event_type == 'time' else 'Field'}")
    with col_info2:
        st.markdown(f"**Scoring:** {'Lower is better' if event_type == 'time' else 'Higher is better'}")
    with col_info3:
        st.markdown(f"**Unit:** {unit}")

    # Get data
    final_summary = get_final_performance_by_place(df_all, selected_champ, selected_gender, selected_event, selected_age)
    qual_summary = get_qualification_by_round(df_all, selected_champ, selected_gender, selected_event)

    # Get qualification standards
    qual_std = get_qualification_standard(selected_event, selected_gender)

    # === WHAT IT TAKES TO WIN ===
    st.markdown("---")
    st.subheader("🏆 Performance Standards")

    if not final_summary.empty:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)

        gold = final_summary[final_summary['Rank'] == 1]
        bronze = final_summary[final_summary['Rank'] == 3]
        eighth = final_summary[final_summary['Rank'] == 8]

        with col_s1:
            if not gold.empty:
                st.metric("🥇 Gold Standard", f"{gold['Average'].values[0]:.2f}")

        with col_s2:
            if not bronze.empty:
                st.metric("🥉 Medal Standard", f"{bronze['Average'].values[0]:.2f}")

        with col_s3:
            if not eighth.empty:
                st.metric("🎯 Finalist Standard", f"{eighth['Average'].values[0]:.2f}")

        with col_s4:
            if qual_std:
                olympic_std = qual_std.get('olympic', 'N/A')
                st.metric("📋 Entry Standard", f"{olympic_std}")

    # === DETAILED TABLE ===
    st.markdown("---")
    st.subheader("📊 Final Performance Breakdown")

    col_table, col_chart = st.columns([1, 1])

    with col_table:
        if not final_summary.empty:
            st.dataframe(final_summary, hide_index=True, use_container_width=True)
        else:
            st.info("No final performance data available")

    with col_chart:
        if not final_summary.empty:
            # Bar chart of averages by place
            chart = alt.Chart(final_summary).mark_bar().encode(
                x=alt.X('Rank:O', title='Finishing Place'),
                y=alt.Y('Average:Q', title='Average Performance'),
                color=alt.condition(
                    alt.datum.Rank <= 3,
                    alt.value('#FFD700'),  # Gold for medalists
                    alt.value('#00FF7F')   # Green for others
                ),
                tooltip=['Rank', 'Average', 'Fastest' if 'Fastest' in final_summary.columns else 'Best']
            ).properties(height=250).configure_axis(
                labelColor='white', titleColor='white', gridColor='gray'
            ).configure_view(strokeWidth=0, fill='#1a1a1a')

            st.altair_chart(chart, use_container_width=True)

    # === QUALIFICATION PATHWAY ===
    st.markdown("---")
    st.subheader("🎯 Qualification Pathway")

    if not qual_summary.empty:
        col_q1, col_q2 = st.columns(2)

        with col_q1:
            st.dataframe(qual_summary, hide_index=True, use_container_width=True)

        with col_q2:
            st.markdown("**How to Qualify:**")
            for _, row in qual_summary.iterrows():
                st.markdown(f"""
                **{row['Round']}:**
                - Auto Qualifier (Q): ~{row['Fastest']:.2f}
                - Time Qualifier (q): ~{row['Average']:.2f}
                """)
    else:
        st.info("No qualification stage data available")

    # === COACHING NOTES ===
    st.markdown("---")
    st.subheader("📝 Coaching Notes")

    coaching_notes = get_event_coaching_notes(selected_event, event_type)
    st.markdown(coaching_notes)


def get_event_coaching_notes(event, event_type):
    """Get coaching terminology and tactical notes for each event."""

    notes = {
        '100m': """
**Race Phases:**
- **Reaction Time:** Elite athletes: <0.150s, Good: 0.150-0.180s
- **Drive Phase:** First 30m, body angle ~45°, powerful pushing
- **Transition:** 30-60m, gradual rise to upright
- **Maximum Velocity:** 60-80m, peak speed zone
- **Maintenance:** 80-100m, minimizing deceleration

**Key Factors:**
- Block start technique critical
- First 10m often determines race
- Wind assistance: +2.0 m/s legal limit
- Reaction time <0.100s = false start
        """,
        '200m': """
**Race Phases:**
- **Curve Running:** First 100m, lean into curve, outside arm action
- **Transition:** Coming off curve at ~100m
- **Home Straight:** Final 100m, maintain form under fatigue

**Key Factors:**
- Lane draw matters (bend)
- Speed endurance critical
- Stagger creates perception challenges
        """,
        '400m': """
**Race Model:**
- **First 200m:** Controlled aggression, ~0.5s slower than 200m PB
- **200-300m:** Maintain rhythm, relaxed running
- **Final 100m:** Oxygen debt management, form maintenance

**Pacing Strategy:**
- Even splits or slight negative split optimal
- First 200m typically 0.5-1.0s slower than best 200m
- Lactate management crucial in final 150m
        """,
        'Long Jump': """
**Technical Phases:**
- **Approach:** 16-22 steps, progressive acceleration
- **Takeoff:** Penultimate step lowering, aggressive drive
- **Flight:** Hitch-kick or hang technique
- **Landing:** Feet forward, hip rotation

**Key Factors:**
- Approach consistency critical
- Legal wind: +2.0 m/s
- Board accuracy determines attempts
        """,
        'Shot Put': """
**Technique Styles:**
- **Glide:** Linear movement, Parry O'Brien style
- **Spin:** Rotational, more power potential

**Key Factors:**
- Release angle: 37-42°
- Implement: Men 7.26kg, Women 4kg
- Circle diameter: 2.135m
        """,
    }

    default_note = f"""
**General {event_type.title()} Event Guidelines:**
- {'Lower times indicate better performance' if event_type == 'time' else 'Higher distances/points indicate better performance'}
- Championship experience valuable
- Tactical awareness in rounds important
- Recovery between rounds critical
    """

    return notes.get(event, default_note)


###################################
# 13) Competitor Analysis
###################################
def show_competitor_analysis(df_all):
    """Championship Competitor Analysis - Focus on a single athlete vs competitors."""

    # Load competitor-specific data (2024-today) for better performance
    df_competitor = load_competitor_data()

    # Custom CSS for maroon/burgundy theme matching screenshot
    st.markdown("""
    <style>
    .competitor-header {
        background: linear-gradient(135deg, #722F37 0%, #4A1C24 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .competitor-header h1 {
        color: white;
        margin: 0;
        font-size: 28px;
    }
    .competitor-header h2 {
        color: #FFD700;
        margin: 5px 0 0 0;
        font-size: 20px;
    }
    .athlete-card {
        background: linear-gradient(135deg, #722F37 0%, #5A252D 100%);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid #8B3A42;
    }
    .athlete-info-label {
        color: #CCCCCC;
        font-size: 12px;
        margin-bottom: 2px;
    }
    .athlete-info-value {
        color: white;
        font-size: 16px;
        font-weight: bold;
    }
    .section-title {
        background: #722F37;
        color: #FFD700;
        padding: 8px 15px;
        border-radius: 5px;
        margin-bottom: 10px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    # Use competitor data (2024-today) instead of main data
    df = df_competitor.copy() if not df_competitor.empty else df_all.copy()

    # --- FILTERS ---
    st.sidebar.markdown("### 🎯 Competitor Analysis Filters")

    # Championship selection
    champ_names = sorted(MAJOR_COMPETITIONS_CID.keys())
    chosen_champ = st.sidebar.selectbox("Championship", champ_names,
                                        index=champ_names.index("Asian Indoor Championships") if "Asian Indoor Championships" in champ_names else 0,
                                        key="comp_champ_select")

    # Year selection
    year_opts = sorted(MAJOR_COMPETITIONS_CID[chosen_champ].keys(), reverse=True)
    chosen_year = st.sidebar.selectbox("Edition", year_opts, key="comp_year_select")

    # Gender filter
    if 'Gender' in df.columns:
        gender_opts = sorted(df['Gender'].dropna().unique())
        chosen_gender = st.sidebar.selectbox("Gender", gender_opts, key="comp_gender_select")
        df = df[df['Gender'] == chosen_gender]
    else:
        chosen_gender = "Men"

    # Event filter
    if 'Event' in df.columns:
        event_opts = sorted(df['Event'].dropna().unique())
        default_event = "60m" if "60m" in event_opts else ("100m" if "100m" in event_opts else event_opts[0] if event_opts else None)
        chosen_event = st.sidebar.selectbox("Event", event_opts,
                                            index=event_opts.index(default_event) if default_event in event_opts else 0,
                                            key="comp_event_select")
        df = df[df['Event'] == chosen_event]
    else:
        st.warning("No Event column found")
        return

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Get event type for sorting
    event_type = get_event_type(chosen_event)
    ascending_sort = (event_type == 'time')
    unit = "s" if event_type == 'time' else ("m" if event_type == 'distance' else "pts")

    # Get current year from selection
    current_year = int(chosen_year) if chosen_year.isdigit() else datetime.datetime.now().year

    # Note: Data already filtered to 2024-today via athletics_competitor.db
    st.sidebar.info(f"Using 2024-{current_year} competitor data")

    # --- HEADER ---
    st.markdown(f"""
    <div class="competitor-header">
        <h1>{chosen_champ} {chosen_year} Competitor Analysis</h1>
    </div>
    """, unsafe_allow_html=True)

    # Get athletes for this event, ranked by Season Best
    df_current = df.copy()

    # Calculate Season Best (SB) for current year
    if 'Year' in df_current.columns:
        df_year = df_current[df_current['Year'] == current_year]
    else:
        df_year = df_current

    # Calculate stats for each athlete
    def get_athlete_stats(athlete_df, athlete_name, event_type):
        """Calculate comprehensive stats for an athlete."""
        stats = {'Athlete': athlete_name}

        if athlete_df.empty:
            return stats

        # Country
        stats['Nat'] = athlete_df['Athlete_Country'].iloc[0] if 'Athlete_Country' in athlete_df.columns else '-'
        stats['CountryCode'] = athlete_df['Athlete_CountryCode'].iloc[0] if 'Athlete_CountryCode' in athlete_df.columns else stats['Nat']

        # Season Best (current year)
        year_data = athlete_df[athlete_df['Year'] == current_year] if 'Year' in athlete_df.columns else athlete_df
        if not year_data.empty:
            if event_type == 'time':
                sb_idx = year_data['Result_numeric'].idxmin()
                stats['SB'] = year_data.loc[sb_idx, 'Result'] if pd.notna(sb_idx) else '-'
                stats['SB_numeric'] = year_data['Result_numeric'].min()
            else:
                sb_idx = year_data['Result_numeric'].idxmax()
                stats['SB'] = year_data.loc[sb_idx, 'Result'] if pd.notna(sb_idx) else '-'
                stats['SB_numeric'] = year_data['Result_numeric'].max()
        else:
            stats['SB'] = '-'
            stats['SB_numeric'] = None

        # Performance count in current year
        stats['# Perf in Year'] = len(year_data) if not year_data.empty else 0

        # Last 3 performances average
        recent = athlete_df.sort_values('Start_Date', ascending=False).head(3)
        if not recent.empty:
            stats['Last 3 Avg'] = round(recent['Result_numeric'].mean(), 2)
        else:
            stats['Last 3 Avg'] = '-'

        # Last performance with date
        if 'Start_Date' in athlete_df.columns:
            last_row = athlete_df.sort_values('Start_Date', ascending=False).iloc[0]
            last_date = pd.to_datetime(last_row['Start_Date'])
            stats['Last Perf'] = last_row['Result']
            stats['Last Date'] = last_date.strftime('%d/%m') if pd.notna(last_date) else '-'
            stats['Last Perf (Date)'] = f"{last_row['Result']} ({stats['Last Date']})"
        else:
            stats['Last Perf (Date)'] = '-'

        return stats

    # Get unique athletes
    athletes_list = df['Athlete_Name'].unique().tolist()

    # Build stats for all athletes
    all_stats = []
    for athlete in athletes_list:
        athlete_df = df[df['Athlete_Name'] == athlete]
        stats = get_athlete_stats(athlete_df, athlete, event_type)
        all_stats.append(stats)

    stats_df = pd.DataFrame(all_stats)

    # Sort by SB (best performance first)
    if 'SB_numeric' in stats_df.columns:
        stats_df = stats_df.sort_values('SB_numeric', ascending=ascending_sort, na_position='last')

    # --- PRIMARY ATHLETE SELECTION ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Select Focus Athlete")

    # Default to first KSA athlete or first in list
    ksa_athletes = stats_df[stats_df['CountryCode'].isin(['KSA', 'SAU'])]
    if not ksa_athletes.empty:
        default_athlete = ksa_athletes['Athlete'].iloc[0]
    else:
        default_athlete = stats_df['Athlete'].iloc[0] if not stats_df.empty else None

    athlete_options = stats_df['Athlete'].tolist()
    selected_athlete = st.sidebar.selectbox(
        "Focus Athlete",
        athlete_options,
        index=athlete_options.index(default_athlete) if default_athlete in athlete_options else 0,
        key="comp_focus_athlete"
    )

    # Get selected athlete's stats
    athlete_stats = stats_df[stats_df['Athlete'] == selected_athlete].iloc[0] if selected_athlete else None

    # Update header with athlete name
    st.markdown(f"""
    <div class="competitor-header">
        <h2>{selected_athlete} ({chosen_event})</h2>
    </div>
    """, unsafe_allow_html=True)

    # --- LAYOUT: Athlete Info + Competitors Table ---
    col_left, col_right = st.columns([1, 2])

    with col_left:
        # Athlete Information Card
        st.markdown('<div class="section-title">Athlete Information</div>', unsafe_allow_html=True)

        if athlete_stats is not None:
            # Info grid
            info_col1, info_col2 = st.columns(2)

            with info_col1:
                st.markdown(f"**SB**")
                st.markdown(f"<span style='font-size:20px; color:#00FF7F;'>{athlete_stats.get('SB', '-')}</span>", unsafe_allow_html=True)

                st.markdown(f"**Asia Rank**")
                st.markdown(f"<span style='font-size:18px;'>-</span>", unsafe_allow_html=True)

                st.markdown(f"**Last 3 Avg.**")
                st.markdown(f"<span style='font-size:18px;'>{athlete_stats.get('Last 3 Avg', '-')}</span>", unsafe_allow_html=True)

            with info_col2:
                st.markdown(f"**Last Perf. (Date)**")
                st.markdown(f"<span style='font-size:18px;'>{athlete_stats.get('Last Perf (Date)', '-')}</span>", unsafe_allow_html=True)

                st.markdown(f"**World Rank**")
                st.markdown(f"<span style='font-size:18px;'>-</span>", unsafe_allow_html=True)

                st.markdown(f"**# Perf. in '{str(current_year)[-2:]}**")
                st.markdown(f"<span style='font-size:18px;'>{athlete_stats.get('# Perf in Year', '-')}</span>", unsafe_allow_html=True)

        # Athlete Results History
        st.markdown("---")
        st.markdown(f'<div class="section-title">{selected_athlete} Results</div>', unsafe_allow_html=True)

        athlete_results = df[df['Athlete_Name'] == selected_athlete].copy()
        if not athlete_results.empty:
            athlete_results = athlete_results.sort_values('Start_Date', ascending=False)

            # Format display table
            display_cols = []
            if 'Result' in athlete_results.columns:
                display_cols.append('Result')
            if 'Venue' in athlete_results.columns:
                display_cols.append('Venue')
            elif 'Competition' in athlete_results.columns:
                athlete_results['City'] = athlete_results['Competition'].str.split(' - ').str[0]
                display_cols.append('City')
            if 'Start_Date' in athlete_results.columns:
                athlete_results['Date'] = pd.to_datetime(athlete_results['Start_Date']).dt.strftime('%d/%m/%Y')
                display_cols.append('Date')

            if display_cols:
                results_display = athlete_results[display_cols].rename(columns={
                    'Result': 'Perf.',
                    'Venue': 'City',
                    'Start_Date': 'Date'
                })
                st.dataframe(results_display.head(10), hide_index=True, use_container_width=True)
        else:
            st.info("No results found for this athlete")

    with col_right:
        # Competitors Table
        st.markdown('<div class="section-title">Competitors</div>', unsafe_allow_html=True)

        # Build competitors table (exclude selected athlete)
        competitors_df = stats_df[stats_df['Athlete'] != selected_athlete].copy()

        # Calculate "vs Focus Ath." column (difference from selected athlete's SB)
        focus_sb = athlete_stats.get('SB_numeric') if athlete_stats is not None else None

        if focus_sb is not None and 'SB_numeric' in competitors_df.columns:
            def calc_vs_focus(row):
                if pd.isna(row['SB_numeric']) or pd.isna(focus_sb):
                    return '-'
                diff = row['SB_numeric'] - focus_sb
                if event_type == 'time':
                    # For time: positive means competitor is slower (behind)
                    return f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"
                else:
                    # For distance/points: negative means competitor is behind
                    return f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"

            competitors_df['vs Focus Ath.'] = competitors_df.apply(calc_vs_focus, axis=1)
        else:
            competitors_df['vs Focus Ath.'] = '-'

        # Select columns for display
        display_columns = ['Athlete', 'Nat', 'SB', 'vs Focus Ath.', '# Perf in Year', 'Last 3 Avg', 'Last Perf (Date)']
        available_cols = [c for c in display_columns if c in competitors_df.columns]

        # Rename columns for display
        rename_map = {
            '# Perf in Year': f"# Perf in '{str(current_year)[-2:]}",
            'Last 3 Avg': 'Last 3 Avg. Perf.',
            'vs Focus Ath.': f'vs {selected_athlete.split()[-1] if selected_athlete else "Focus"}'
        }

        competitors_display = competitors_df[available_cols].copy()
        competitors_display = competitors_display.rename(columns=rename_map)

        # Style the dataframe
        def style_competitors(df):
            return df.style.set_properties(**{
                'background-color': '#1E1E1E',
                'color': 'white',
                'border-color': '#333'
            })

        st.dataframe(competitors_display.head(15), hide_index=True, use_container_width=True, height=400)

        # Footnotes for special marks
        st.markdown("""
        <small style='color: #888;'>
        * Indoor performance | ** Outdoor performance | h = hand-timed
        </small>
        """, unsafe_allow_html=True)

    # --- PERFORMANCE COMPARISON CHART ---
    st.markdown("---")
    st.markdown("### 📈 Performance Progression Comparison")

    # Select competitors to compare
    top_competitors = competitors_df.head(5)['Athlete'].tolist()
    compare_athletes = [selected_athlete] + top_competitors

    chart_df = df[df['Athlete_Name'].isin(compare_athletes)].copy()

    if not chart_df.empty and 'Start_Date' in chart_df.columns:
        # Remove outliers
        q1 = chart_df['Result_numeric'].quantile(0.1)
        q3 = chart_df['Result_numeric'].quantile(0.9)
        chart_df = chart_df[(chart_df['Result_numeric'] >= q1) & (chart_df['Result_numeric'] <= q3)]

        if not chart_df.empty:
            # Create color scale - highlight focus athlete
            athlete_colors = ['#FFD700']  # Gold for focus athlete
            athlete_colors.extend(['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'][:len(top_competitors)])

            y_title = 'Time (seconds)' if event_type == 'time' else ('Distance (m)' if event_type == 'distance' else 'Points')

            chart = alt.Chart(chart_df).mark_line(
                interpolate='monotone',
                point=alt.OverlayMarkDef(filled=True, size=60)
            ).encode(
                x=alt.X('Start_Date:T', title='Date'),
                y=alt.Y('Result_numeric:Q', title=y_title, scale=alt.Scale(zero=False)),
                color=alt.Color('Athlete_Name:N', title='Athlete',
                               scale=alt.Scale(domain=compare_athletes, range=athlete_colors)),
                strokeWidth=alt.condition(
                    alt.datum.Athlete_Name == selected_athlete,
                    alt.value(3),
                    alt.value(1.5)
                ),
                tooltip=['Athlete_Name:N', 'Start_Date:T', 'Result:N', 'Competition:N']
            ).properties(
                height=350
            ).configure_axis(
                labelColor='white',
                titleColor='white',
                gridColor='#333'
            ).configure_view(
                strokeWidth=0,
                fill='#0e1117'
            ).configure_legend(
                labelColor='white',
                titleColor='white'
            )

            st.altair_chart(chart, use_container_width=True)

    # --- HEAD-TO-HEAD ANALYSIS ---
    st.markdown("---")
    st.markdown("### ⚔️ Head-to-Head Record")

    if 'Competition_ID' in df.columns:
        # Find competitions where focus athlete competed
        focus_comps = df[df['Athlete_Name'] == selected_athlete]['Competition_ID'].unique()

        # Find shared competitions with other athletes
        h2h_data = []
        for comp_id in focus_comps:
            comp_df = df[df['Competition_ID'] == comp_id]
            focus_row = comp_df[comp_df['Athlete_Name'] == selected_athlete]

            if focus_row.empty:
                continue

            focus_result = focus_row['Result_numeric'].iloc[0]
            focus_pos = focus_row['Position'].iloc[0] if 'Position' in focus_row.columns else None
            comp_name = focus_row['Competition'].iloc[0] if 'Competition' in focus_row.columns else comp_id
            comp_date = focus_row['Start_Date'].iloc[0] if 'Start_Date' in focus_row.columns else None

            # Check other athletes
            others = comp_df[comp_df['Athlete_Name'] != selected_athlete]
            for _, other_row in others.iterrows():
                other_result = other_row['Result_numeric']
                other_pos = other_row['Position'] if 'Position' in other_row else None

                # Determine winner
                if event_type == 'time':
                    winner = selected_athlete if focus_result <= other_result else other_row['Athlete_Name']
                else:
                    winner = selected_athlete if focus_result >= other_result else other_row['Athlete_Name']

                h2h_data.append({
                    'Competition': comp_name,
                    'Date': comp_date,
                    'Opponent': other_row['Athlete_Name'],
                    f'{selected_athlete}': focus_row['Result'].iloc[0],
                    'Opponent Result': other_row['Result'],
                    'Winner': '✓' if winner == selected_athlete else ''
                })

        if h2h_data:
            h2h_df = pd.DataFrame(h2h_data)

            # Summary: wins vs each opponent
            win_summary = h2h_df.groupby('Opponent').agg({
                'Winner': lambda x: (x == '✓').sum(),
                'Competition': 'count'
            }).reset_index()
            win_summary.columns = ['Opponent', 'Wins', 'Total Meetings']
            win_summary['Losses'] = win_summary['Total Meetings'] - win_summary['Wins']
            win_summary['Win %'] = (win_summary['Wins'] / win_summary['Total Meetings'] * 100).round(0).astype(int).astype(str) + '%'

            col_h1, col_h2 = st.columns([1, 2])

            with col_h1:
                st.markdown("**Win/Loss Summary**")
                st.dataframe(win_summary[['Opponent', 'Wins', 'Losses', 'Win %']], hide_index=True, use_container_width=True)

            with col_h2:
                st.markdown("**Recent Head-to-Head Results**")
                h2h_display = h2h_df[['Competition', 'Date', 'Opponent', f'{selected_athlete}', 'Opponent Result', 'Winner']].head(10)
                h2h_display['Date'] = pd.to_datetime(h2h_display['Date']).dt.strftime('%d/%m/%Y')
                st.dataframe(h2h_display, hide_index=True, use_container_width=True)
        else:
            st.info("No head-to-head data available for this athlete.")


###################################
# 12) Detailed Athlete Report
###################################
def show_detailed_report(df_all):
    """Show detailed athlete report with filters, charts, and exportable summary."""
    st.title("Detailed Athlete Report")
    st.markdown("Generate comprehensive performance reports for selected athletes with progression charts and season analysis.")

    df = df_all.copy()

    # Ensure required columns
    if 'Athlete_Name' not in df.columns:
        st.error("No athlete data available.")
        return

    # ============ FILTERS SECTION ============
    st.header("Report Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Country filter first (to narrow down athlete list)
        if 'Athlete_Country' in df.columns:
            country_options = sorted(df['Athlete_Country'].dropna().unique().tolist())
            chosen_countries = st.multiselect(
                "Filter by Country",
                country_options,
                default=["KSA"] if "KSA" in country_options else [],
                key="detailed_report_countries"
            )
            if chosen_countries:
                df = df[df['Athlete_Country'].isin(chosen_countries)]

    with col2:
        # Gender filter
        if 'Gender' in df.columns:
            gender_options = ["All"] + sorted(df['Gender'].dropna().unique().tolist())
            chosen_gender = st.selectbox("Gender", gender_options, key="detailed_report_gender")
            if chosen_gender != "All":
                df = df[df['Gender'] == chosen_gender]

    with col3:
        # Year filter
        if 'Year' in df.columns:
            year_options = sorted([int(y) for y in df['Year'].dropna().unique() if pd.notna(y)], reverse=True)
            if year_options:
                chosen_years = st.multiselect(
                    "Select Years",
                    year_options,
                    default=year_options[:3] if len(year_options) >= 3 else year_options,
                    key="detailed_report_years"
                )
                if chosen_years:
                    df = df[df['Year'].isin(chosen_years)]

    # Athlete selection (main filter)
    st.subheader("Select Athletes")
    athlete_names = sorted(df['Athlete_Name'].dropna().unique().tolist())

    if not athlete_names:
        st.warning("No athletes found with the selected filters.")
        return

    # Default to first KSA athlete if available
    default_athletes = athlete_names[:1] if athlete_names else []
    chosen_athletes = st.multiselect(
        "Select Athlete(s) for Report",
        athlete_names,
        default=default_athletes,
        key="detailed_report_athletes"
    )

    if not chosen_athletes:
        st.info("Select at least one athlete to generate a report.")
        return

    # Filter to selected athletes
    df = df[df['Athlete_Name'].isin(chosen_athletes)]

    # Event filter
    st.subheader("Event Filter")
    if 'Event' in df.columns:
        event_options = sorted(df['Event'].dropna().unique().tolist())
        chosen_events = st.multiselect(
            "Select Events (leave empty for all)",
            event_options,
            key="detailed_report_events"
        )
        if chosen_events:
            df = df[df['Event'].isin(chosen_events)]

    st.markdown("---")

    # ============ REPORT GENERATION ============
    if st.button("Generate Detailed Report", type="primary", key="gen_detailed_report"):
        if df.empty:
            st.warning("No data available for the selected filters.")
            return

        # Generate report for each athlete
        for athlete in chosen_athletes:
            athlete_df = df[df['Athlete_Name'] == athlete].copy()

            if athlete_df.empty:
                continue

            st.markdown(f"## {athlete}")
            st.markdown("---")

            # ---- ATHLETE OVERVIEW ----
            col_info, col_stats = st.columns([1, 2])

            with col_info:
                st.markdown("### Athlete Info")
                country = athlete_df['Athlete_Country'].iloc[0] if 'Athlete_Country' in athlete_df.columns else "N/A"
                flag = get_flag(country) if country != "N/A" else ""

                # Calculate stats
                total_performances = len(athlete_df)
                events_competed = athlete_df['Event'].nunique() if 'Event' in athlete_df.columns else 0
                competitions = athlete_df['Competition'].nunique() if 'Competition' in athlete_df.columns else 0

                # Date range
                if 'Start_Date' in athlete_df.columns:
                    min_date = athlete_df['Start_Date'].min()
                    max_date = athlete_df['Start_Date'].max()
                    date_range_str = f"{min_date.strftime('%d/%m/%Y')} - {max_date.strftime('%d/%m/%Y')}"
                else:
                    date_range_str = "N/A"

                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                            padding: 20px; border-radius: 10px; border-left: 4px solid #e94560;'>
                    <h3 style='color: #e94560; margin: 0;'>{flag} {country}</h3>
                    <p style='color: #aaa; margin: 5px 0;'><b>Performances:</b> {total_performances}</p>
                    <p style='color: #aaa; margin: 5px 0;'><b>Events:</b> {events_competed}</p>
                    <p style='color: #aaa; margin: 5px 0;'><b>Competitions:</b> {competitions}</p>
                    <p style='color: #aaa; margin: 5px 0;'><b>Period:</b> {date_range_str}</p>
                </div>
                """, unsafe_allow_html=True)

            with col_stats:
                st.markdown("### Personal Bests by Event")
                if 'Event' in athlete_df.columns and 'Result_numeric' in athlete_df.columns:
                    pb_data = []
                    for event in athlete_df['Event'].unique():
                        event_df = athlete_df[athlete_df['Event'] == event]
                        event_clean = event.strip().replace("Indoor", "").strip()
                        ev_type = event_type_map.get(event, event_type_map.get(event_clean, 'time'))

                        if ev_type == 'time':
                            best_idx = event_df['Result_numeric'].idxmin()
                        else:
                            best_idx = event_df['Result_numeric'].idxmax()

                        if pd.notna(best_idx):
                            best_row = event_df.loc[best_idx]
                            pb_data.append({
                                'Event': event,
                                'PB': best_row.get('Result', str(best_row['Result_numeric'])),
                                'Date': best_row.get('Start_Date', pd.NaT),
                                'Competition': best_row.get('Competition', 'N/A'),
                                'WA Points': best_row.get('WA_Points', 'N/A')
                            })

                    if pb_data:
                        pb_df = pd.DataFrame(pb_data)
                        if 'Date' in pb_df.columns:
                            pb_df['Date'] = pd.to_datetime(pb_df['Date']).dt.strftime('%d/%m/%Y')
                        st.dataframe(pb_df, hide_index=True, use_container_width=True)

            # ---- PERFORMANCE PROGRESSION CHARTS ----
            st.markdown("### Performance Progression")

            if 'Event' in athlete_df.columns and 'Result_numeric' in athlete_df.columns:
                events_list = athlete_df['Event'].unique()

                for event in events_list:
                    event_df = athlete_df[athlete_df['Event'] == event].copy()

                    if len(event_df) < 2:
                        continue

                    # Determine event type
                    event_clean = event.strip().replace("Indoor", "").strip()
                    ev_type = event_type_map.get(event, event_type_map.get(event_clean, 'time'))

                    st.markdown(f"#### {event}")

                    # Sort by date
                    if 'Start_Date' in event_df.columns:
                        event_df = event_df.sort_values('Start_Date')
                        event_df['Date_Str'] = event_df['Start_Date'].dt.strftime('%d/%m/%Y')

                    # Create progression chart
                    if 'Start_Date' in event_df.columns:
                        y_title = 'Time (seconds)' if ev_type == 'time' else 'Distance/Points'

                        # For time events, lower is better, so reverse scale
                        y_scale = alt.Scale(reverse=(ev_type == 'time'))

                        chart = alt.Chart(event_df).mark_line(
                            point=alt.OverlayMarkDef(filled=True, size=80),
                            color='#e94560'
                        ).encode(
                            x=alt.X('Start_Date:T', title='Date'),
                            y=alt.Y('Result_numeric:Q', title=y_title, scale=y_scale),
                            tooltip=[
                                alt.Tooltip('Start_Date:T', title='Date', format='%d/%m/%Y'),
                                alt.Tooltip('Result:N', title='Result'),
                                alt.Tooltip('Competition:N', title='Competition'),
                                alt.Tooltip('Result_numeric:Q', title='Numeric', format='.2f')
                            ]
                        ).properties(
                            width=700,
                            height=300
                        ).configure_axis(
                            labelColor='white',
                            titleColor='white',
                            gridColor='#333'
                        ).configure_view(
                            strokeWidth=0,
                            fill='#0e1117'
                        )

                        st.altair_chart(chart, use_container_width=True)

                    # Season statistics
                    if 'Year' in event_df.columns:
                        st.markdown("**Season Statistics**")
                        season_stats = event_df.groupby('Year').agg({
                            'Result_numeric': ['count', 'mean', 'min', 'max', 'std']
                        }).round(3)
                        season_stats.columns = ['Performances', 'Average', 'Best', 'Worst', 'Std Dev']
                        season_stats = season_stats.reset_index()
                        season_stats['Year'] = season_stats['Year'].astype(int)

                        if ev_type == 'time':
                            # For time events, min is best
                            season_stats = season_stats.rename(columns={'Best': 'Season Best', 'Worst': 'Slowest'})
                        else:
                            # For distance/points, max is best
                            season_stats = season_stats.rename(columns={'Best': 'Worst', 'Worst': 'Season Best'})
                            season_stats['Season Best'], season_stats['Worst'] = season_stats['Worst'], season_stats['Season Best']

                        st.dataframe(season_stats, hide_index=True, use_container_width=True)

            # ---- COMPETITION BREAKDOWN ----
            st.markdown("### Competition Breakdown")
            if 'Competition' in athlete_df.columns:
                comp_stats = athlete_df.groupby('Competition').agg({
                    'Result_numeric': 'count',
                    'Event': lambda x: ', '.join(x.unique())
                }).reset_index()
                comp_stats.columns = ['Competition', 'Performances', 'Events']
                st.dataframe(comp_stats.head(20), hide_index=True, use_container_width=True)

            # ---- RECENT RESULTS ----
            st.markdown("### Recent Results")
            recent_cols = ['Start_Date', 'Event', 'Result', 'Competition', 'Position']
            recent_cols = [c for c in recent_cols if c in athlete_df.columns]

            if 'Start_Date' in athlete_df.columns:
                recent_df = athlete_df.sort_values('Start_Date', ascending=False)[recent_cols].head(15)
                recent_df['Start_Date'] = pd.to_datetime(recent_df['Start_Date']).dt.strftime('%d/%m/%Y')
                recent_df = recent_df.rename(columns={'Start_Date': 'Date'})
                st.dataframe(recent_df, hide_index=True, use_container_width=True)

            st.markdown("---")

        # ============ EXPORT SECTION ============
        st.markdown("## Export Report")

        # Generate text report
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("DETAILED ATHLETE PERFORMANCE REPORT")
        report_lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 60)
        report_lines.append("")

        for athlete in chosen_athletes:
            athlete_df = df[df['Athlete_Name'] == athlete]
            if athlete_df.empty:
                continue

            report_lines.append(f"\n{'='*50}")
            report_lines.append(f"ATHLETE: {athlete}")
            report_lines.append(f"{'='*50}")

            country = athlete_df['Athlete_Country'].iloc[0] if 'Athlete_Country' in athlete_df.columns else "N/A"
            report_lines.append(f"Country: {country}")
            report_lines.append(f"Total Performances: {len(athlete_df)}")

            if 'Event' in athlete_df.columns:
                report_lines.append(f"Events: {', '.join(athlete_df['Event'].unique())}")

            report_lines.append("\nPERSONAL BESTS:")
            report_lines.append("-" * 40)

            if 'Event' in athlete_df.columns and 'Result_numeric' in athlete_df.columns:
                for event in athlete_df['Event'].unique():
                    event_df = athlete_df[athlete_df['Event'] == event]
                    event_clean = event.strip().replace("Indoor", "").strip()
                    ev_type = event_type_map.get(event, event_type_map.get(event_clean, 'time'))

                    if ev_type == 'time':
                        best_val = event_df['Result_numeric'].min()
                    else:
                        best_val = event_df['Result_numeric'].max()

                    best_row = event_df[event_df['Result_numeric'] == best_val].iloc[0]
                    result_str = best_row.get('Result', str(best_val))
                    report_lines.append(f"  {event}: {result_str}")

            report_lines.append("\nSEASON SUMMARY:")
            report_lines.append("-" * 40)

            if 'Year' in athlete_df.columns:
                for year in sorted(athlete_df['Year'].unique(), reverse=True):
                    year_df = athlete_df[athlete_df['Year'] == year]
                    report_lines.append(f"  {int(year)}: {len(year_df)} performances")

            report_lines.append("")

        report_text = "\n".join(report_lines)

        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            st.download_button(
                label="Download Report (TXT)",
                data=report_text,
                file_name=f"Athlete_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="download_detailed_report_txt"
            )

        with col_dl2:
            # CSV export of filtered data
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="Download Data (CSV)",
                data=csv_data,
                file_name=f"Athlete_Data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_detailed_report_csv"
            )


###################################
# 13) Main
###################################
def main():
    # Load data once at the start with progress indicator
    with st.spinner("Loading athletics data..."):
        # Show connection diagnostics
        conn_mode = get_connection_mode()
        st.info(f"Database connection mode: **{conn_mode}**")

        # Check if secrets are configured (Streamlit Cloud)
        if conn_mode == 'sqlite':
            try:
                if hasattr(st, 'secrets'):
                    available_secrets = list(st.secrets.keys()) if st.secrets else []
                    if 'AZURE_SQL_CONN' not in available_secrets:
                        st.warning(f"⚠️ AZURE_SQL_CONN secret not found. Available secrets: {available_secrets}")
                        st.info("💡 Add AZURE_SQL_CONN in Streamlit Cloud Settings > Secrets")
            except:
                pass

        df_all = load_data()

    if df_all.empty:
        st.error("❌ No data loaded. Please check the data source configuration.")
        st.info(f"Current connection mode: **{get_connection_mode()}**")
        return

    # Sidebar with Saudi branding and view mode toggle
    with st.sidebar:
        # Saudi Logo and Title
        st.image("Tilasoptija/Saudilogo.png", width=120)
        st.markdown("## Saudi Athletics")
        st.markdown("*Performance Analysis Platform*")
        st.markdown("---")

        st.markdown("### View Mode")
        view_mode = st.radio(
            "Select View",
            ["Coach View", "Analyst View"],
            index=0,
            key="view_mode_toggle",
            help="Coach View: Simplified interface for pre-competition briefings\nAnalyst View: Full analysis capabilities"
        )

        st.markdown("---")
        st.markdown("### Data Info")
        st.caption(f"Records: {len(df_all):,}")
        st.caption(f"Result_numeric: {'Yes' if 'Result_numeric' in df_all.columns else 'No'}")
        if 'Result_numeric' in df_all.columns:
            st.caption(f"Valid results: {df_all['Result_numeric'].notna().sum():,}")

    # Render based on view mode
    if view_mode == "Coach View":
        render_coach_view(df_all)
        return  # Exit after Coach View

    # Analyst View (original tabs)
    tab_names = [
        "🏟️ Road to Asian Games",
        "🏅 Road to LA 2028",
        "🌍 Road to Tokyo 2025",
        "📊 Event Analysis",
        "👤 Athlete Profiles",
        "🎯 Qualification vs Final",
        "⚔️ Competitor Analysis",
        "🏃 Relay Analytics",
        "📝 Text Report",
        "📋 Detailed Report"
    ]

    # Use selectbox for tab selection (more efficient than st.tabs for heavy content)
    selected_tab = st.selectbox("Select Analysis Tab", tab_names, key="analyst_tab_select", label_visibility="collapsed")

    st.markdown("---")

    # Only render the selected tab (lazy loading - much faster than st.tabs)
    if selected_tab == "🏟️ Road to Asian Games":
        show_road_to_championship(df_all, "Asian Games", "2026", "Nagoya")

    elif selected_tab == "🏅 Road to LA 2028":
        show_road_to_championship(df_all, "Olympics", "2028", "Los Angeles")

    elif selected_tab == "🌍 Road to Tokyo 2025":
        show_road_to_championship(df_all, "World Championships", "2025", "Tokyo")

    elif selected_tab == "📊 Event Analysis":
        show_event_analysis(df_all)

    elif selected_tab == "👤 Athlete Profiles":
        st.title("Athlete Profiles")
        st.header("Filters")
        filtered_df = df_all.copy()

        col1, col2 = st.columns(2)
        with col1:
            if 'Gender' in filtered_df.columns:
                gender_options = sorted(filtered_df['Gender'].dropna().unique())
                chosen_gender = st.selectbox("Gender", ["All"] + list(gender_options), key="profile_gender")
                if chosen_gender != "All":
                    filtered_df = filtered_df[filtered_df['Gender'] == chosen_gender]

        with col2:
            if 'Athlete_Country' in filtered_df.columns:
                country_options = sorted(filtered_df['Athlete_Country'].dropna().unique())
                chosen_country = st.selectbox("Country", ["All"] + list(country_options), key="profile_country")
                if chosen_country != "All":
                    filtered_df = filtered_df[filtered_df['Athlete_Country'] == chosen_country]

        if 'Event' in filtered_df.columns:
            event_options = sorted(filtered_df['Event'].dropna().unique())
            default_event = ["100m"] if "100m" in event_options else list(event_options[:1]) if len(event_options) > 0 else []
            chosen_events = st.multiselect("Events", event_options, default=default_event, key="profile_events")
            if chosen_events:
                filtered_df = filtered_df[filtered_df['Event'].isin(chosen_events)]

        if 'Year' in filtered_df.columns:
            year_options = sorted([y for y in filtered_df['Year'].dropna().unique() if pd.notna(y)])
            if year_options:
                chosen_years = st.multiselect("Years", year_options, default=year_options, key="profile_years")
                if chosen_years:
                    filtered_df = filtered_df[filtered_df['Year'].isin(chosen_years)]

        st.markdown("#### Filter by Championship")
        comp_names = ["All"] + sorted(MAJOR_COMPETITIONS_CID.keys())
        chosen_comp = st.selectbox("Championship", comp_names, key="profile_comp_name")
        if chosen_comp != "All":
            edition_years = list(MAJOR_COMPETITIONS_CID[chosen_comp].keys())
            chosen_edition_year = st.selectbox("Edition Year", ["All"] + sorted(edition_years, reverse=True), key="profile_comp_year")
            if chosen_edition_year != "All":
                cid = MAJOR_COMPETITIONS_CID[chosen_comp][chosen_edition_year]["CID"]
                if "Competition_ID" in filtered_df.columns:
                    filtered_df['Competition_ID'] = filtered_df['Competition_ID'].astype(str)
                    filtered_df = filtered_df[filtered_df["Competition_ID"] == cid]

        show_athlete_profiles(filtered_df, "Athletics")

    elif selected_tab == "🎯 Qualification vs Final":
        st.title("Qualification vs Final Analysis")
        df_qual = df_all.copy()

        if df_qual.empty:
            st.warning("No data available")
        else:
            if 'Competition_ID' in df_qual.columns:
                df_qual['Competition_ID'] = df_qual['Competition_ID'].astype(str)

            st.header("Filters")
            col1, col2 = st.columns(2)

            with col1:
                if 'Gender' in df_qual.columns:
                    g_opts = sorted(df_qual['Gender'].dropna().unique())
                    if g_opts:
                        default_gender = "Men" if "Men" in g_opts else g_opts[0]
                        chosen_g = st.selectbox("Gender", g_opts, index=g_opts.index(default_gender), key="qualfinal_gender")
                        df_qual = df_qual[df_qual['Gender'] == chosen_g]

            with col2:
                if 'Event' in df_qual.columns:
                    e_opts = sorted(df_qual['Event'].dropna().unique())
                    default_event = [e for e in ['100m'] if e in e_opts] or list(e_opts[:1]) if len(e_opts) > 0 else []
                    chosen_e = st.multiselect("Event", e_opts, default=default_event, key="qualfinal_events")
                    if chosen_e:
                        df_qual = df_qual[df_qual['Event'].isin(chosen_e)]

            st.markdown("#### Filter by Championship")
            comp_names = sorted(MAJOR_COMPETITIONS_CID.keys())
            chosen_comp = st.selectbox("Championship", ["All"] + comp_names, index=0, key="qualfinal_champ_name")
            if chosen_comp != "All":
                cids = [v["CID"] for v in MAJOR_COMPETITIONS_CID[chosen_comp].values()]
                if "Competition_ID" in df_qual.columns:
                    df_qual = df_qual[df_qual["Competition_ID"].isin(cids)]

            if df_qual.empty:
                st.info("No data after filters.")
            else:
                sub_tabs = st.tabs(["Qualification Stage", "Final Performances"])
                with sub_tabs[0]:
                    show_qualification_stage(df_qual)
                with sub_tabs[1]:
                    show_final_performances(df_qual)

    elif selected_tab == "⚔️ Competitor Analysis":
        show_competitor_analysis(df_all)

    elif selected_tab == "🏃 Relay Analytics":
        st.title("Relay Event Analytics")
        df_relay = df_all.copy()
        if df_relay.empty:
            st.warning("No data available")
        else:
            show_relay_charts(df_relay)

    elif selected_tab == "📝 Text Report":
        show_text_report_page(df_all)

    elif selected_tab == "📋 Detailed Report":
        show_detailed_report(df_all)

if __name__ == "__main__":
    main()

# Footer
st.markdown("""
    <hr style='margin-top: 30px; border: 1px solid #444;'>
    <div style='text-align: center; color: #888; font-size: 0.9em;'>
        Athletics Analysis Dashboard — Created by <strong>Luke Gallagher</strong>
    </div>
    """, unsafe_allow_html=True)
