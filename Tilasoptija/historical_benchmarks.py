"""
Historical Benchmarks for Athletics Championships

Calculates what it takes to:
- Win a medal (top 3)
- Make the final (top 8)
- Advance from semi-finals
- Survive heats

Based on historical championship data from Olympics, World Championships,
Asian Games, and other major events.

Used by Coach View for setting realistic performance targets.
"""

import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import statistics


# Championship competition IDs for benchmark calculations
BENCHMARK_CHAMPIONSHIPS = {
    'Olympics': ['13079218', '12992925', '12877460', '12825110', '12042259'],  # 2024-2008
    'World Championships': ['13046619', '13002354', '12935526', '12898707', '12844203'],  # 2023-2013
    'Asian Games': ['13048549', '12911586', '12854365'],  # 2023-2014
}

# Round name mappings for normalization
ROUND_MAPPINGS = {
    'final': ['Final', 'final', 'f', 'F'],
    'semi': ['Semi-Final', 'semi-final', 'sf', 'SF', 's', 'Semi'],
    'heat': ['Heat', 'heat', 'h', 'H', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8',
             'Heat 1', 'Heat 2', 'Heat 3', 'Heat 4', 'Heat 5', 'Heat 6', 'Heat 7', 'Heat 8'],
    'qualification': ['Qualification', 'qualification', 'q', 'Q', 'qual']
}


def normalize_round(round_name: str) -> str:
    """Normalize round name to standard format."""
    if not round_name:
        return 'unknown'

    round_lower = str(round_name).lower().strip()

    for standard, variants in ROUND_MAPPINGS.items():
        if round_name in variants or round_lower in [v.lower() for v in variants]:
            return standard

    return 'unknown'


def get_event_type(event_name: str) -> str:
    """
    Determine if event is time-based, distance-based, or points-based.

    Returns:
        'time' - lower is better (track events)
        'distance' - higher is better (jumps, throws)
        'points' - higher is better (combined events)
    """
    event_lower = event_name.lower()

    # Points events
    if any(x in event_lower for x in ['decathlon', 'heptathlon', 'pentathlon']):
        return 'points'

    # Distance events (field)
    distance_events = ['jump', 'vault', 'put', 'throw', 'discus', 'hammer', 'javelin']
    if any(x in event_lower for x in distance_events):
        return 'distance'

    # Default to time (track events)
    return 'time'


def calculate_round_benchmarks(
    df: pd.DataFrame,
    event: str,
    gender: str,
    championships: List[str] = None
) -> Dict[str, Dict]:
    """
    Calculate historical benchmarks for each round of competition.

    Args:
        df: DataFrame with competition results
        event: Event name (e.g., '100m', '400m')
        gender: 'Men' or 'Women'
        championships: List of competition IDs to include

    Returns:
        Dict with benchmarks for each round:
        {
            'medal': {'average': 43.95, 'range': (43.45, 44.32), 'editions': 5},
            'final': {'average': 44.45, 'range': (44.02, 44.89), 'editions': 5},
            'semi': {'average': 45.05, 'range': (44.65, 45.42), 'editions': 5},
            'heat': {'average': 45.55, 'range': (45.12, 45.98), 'editions': 5}
        }
    """
    event_type = get_event_type(event)

    # Filter data
    filtered = df[
        (df['Event'] == event) &
        (df['Gender'] == gender)
    ].copy()

    if championships:
        filtered = filtered[filtered['Competition_ID'].astype(str).isin(championships)]

    if filtered.empty:
        return get_default_benchmarks(event, gender)

    # Normalize round names
    filtered['Round_Normalized'] = filtered['Round'].apply(normalize_round)

    benchmarks = {}

    # Medal line: Top 3 finishers in finals
    finals = filtered[filtered['Round_Normalized'] == 'final'].copy()
    if not finals.empty:
        finals['Position'] = pd.to_numeric(finals['Position'], errors='coerce')
        medalists = finals[finals['Position'] <= 3]

        if not medalists.empty:
            medal_perfs = medalists['Result_numeric'].dropna().tolist()
            if medal_perfs:
                benchmarks['medal'] = {
                    'average': round(statistics.mean(medal_perfs), 2),
                    'range': (round(min(medal_perfs), 2), round(max(medal_perfs), 2)),
                    'best': round(min(medal_perfs) if event_type == 'time' else max(medal_perfs), 2),
                    'editions': len(set(medalists['Competition_ID'].tolist())),
                    'description': 'Top 3 finishers in finals (last 3-5 championships)'
                }

    # Final line: All finalists (typically top 8)
    if not finals.empty:
        final_perfs = finals['Result_numeric'].dropna().tolist()
        if final_perfs:
            benchmarks['final'] = {
                'average': round(statistics.mean(final_perfs), 2),
                'range': (round(min(final_perfs), 2), round(max(final_perfs), 2)),
                'cutoff': round(max(final_perfs) if event_type == 'time' else min(final_perfs), 2),
                'editions': len(set(finals['Competition_ID'].tolist())),
                'description': 'All finalists (top 8) - average performance'
            }

    # Semi-final line: Qualifiers from semis
    semis = filtered[filtered['Round_Normalized'] == 'semi'].copy()
    if not semis.empty:
        # Get qualifiers (typically positions that advanced, or use time-based qualifier marks)
        semi_perfs = semis['Result_numeric'].dropna().tolist()
        if semi_perfs:
            # Estimate qualifying mark (top 60% typically advance)
            semi_perfs_sorted = sorted(semi_perfs, reverse=(event_type != 'time'))
            cutoff_idx = int(len(semi_perfs_sorted) * 0.4)  # Bottom 40% don't advance
            qualifying_perfs = semi_perfs_sorted[:max(1, len(semi_perfs_sorted) - cutoff_idx)]

            benchmarks['semi'] = {
                'average': round(statistics.mean(qualifying_perfs), 2),
                'range': (round(min(semi_perfs), 2), round(max(semi_perfs), 2)),
                'cutoff': round(qualifying_perfs[-1] if qualifying_perfs else semi_perfs_sorted[-1], 2),
                'editions': len(set(semis['Competition_ID'].tolist())),
                'description': 'Semi-final qualifiers - typical advancing performance'
            }

    # Heat survival line: Slowest/lowest heat qualifiers
    heats = filtered[filtered['Round_Normalized'] == 'heat'].copy()
    if not heats.empty:
        heat_perfs = heats['Result_numeric'].dropna().tolist()
        if heat_perfs:
            # Estimate heat qualifying (typically top 3 + fastest losers)
            heat_perfs_sorted = sorted(heat_perfs, reverse=(event_type != 'time'))
            cutoff_idx = int(len(heat_perfs_sorted) * 0.5)  # ~50% advance from heats
            qualifying_perfs = heat_perfs_sorted[:max(1, cutoff_idx)]

            benchmarks['heat'] = {
                'average': round(statistics.mean(qualifying_perfs), 2),
                'range': (round(min(heat_perfs), 2), round(max(heat_perfs), 2)),
                'cutoff': round(qualifying_perfs[-1] if qualifying_perfs else heat_perfs_sorted[cutoff_idx], 2),
                'editions': len(set(heats['Competition_ID'].tolist())),
                'description': 'Heat qualifiers - minimum performance to advance'
            }

    # Fill in missing benchmarks with defaults
    default_benchmarks = get_default_benchmarks(event, gender)
    for round_name in ['medal', 'final', 'semi', 'heat']:
        if round_name not in benchmarks:
            benchmarks[round_name] = default_benchmarks.get(round_name, {})

    return benchmarks


def get_default_benchmarks(event: str, gender: str) -> Dict[str, Dict]:
    """
    Get default benchmarks for events without sufficient historical data.

    Based on typical World Championship performance levels.
    """
    # Default benchmarks for common events
    defaults = {
        'Men': {
            '100m': {'medal': 9.85, 'final': 10.02, 'semi': 10.12, 'heat': 10.25},
            '200m': {'medal': 19.85, 'final': 20.15, 'semi': 20.35, 'heat': 20.55},
            '400m': {'medal': 44.20, 'final': 44.60, 'semi': 45.10, 'heat': 45.50},
            '800m': {'medal': 103.50, 'final': 104.50, 'semi': 106.00, 'heat': 107.50},
            '1500m': {'medal': 212.00, 'final': 215.00, 'semi': 218.00, 'heat': 222.00},
            '5000m': {'medal': 780.00, 'final': 795.00, 'semi': None, 'heat': 810.00},
            '10000m': {'medal': 1620.00, 'final': 1650.00, 'semi': None, 'heat': None},
            '110m Hurdles': {'medal': 13.05, 'final': 13.25, 'semi': 13.45, 'heat': 13.65},
            '400m Hurdles': {'medal': 47.50, 'final': 48.20, 'semi': 49.00, 'heat': 49.80},
            '3000m Steeplechase': {'medal': 495.00, 'final': 505.00, 'semi': None, 'heat': 515.00},
            'High Jump': {'medal': 2.35, 'final': 2.28, 'semi': None, 'heat': 2.25},
            'Pole Vault': {'medal': 5.90, 'final': 5.75, 'semi': None, 'heat': 5.65},
            'Long Jump': {'medal': 8.35, 'final': 8.10, 'semi': None, 'heat': 8.00},
            'Triple Jump': {'medal': 17.50, 'final': 17.10, 'semi': None, 'heat': 16.90},
            'Shot Put': {'medal': 22.50, 'final': 21.50, 'semi': None, 'heat': 20.80},
            'Discus Throw': {'medal': 68.50, 'final': 66.00, 'semi': None, 'heat': 64.50},
            'Hammer Throw': {'medal': 80.00, 'final': 77.50, 'semi': None, 'heat': 75.00},
            'Javelin Throw': {'medal': 88.00, 'final': 84.00, 'semi': None, 'heat': 82.00},
            'Decathlon': {'medal': 8700, 'final': 8400, 'semi': None, 'heat': None},
        },
        'Women': {
            '100m': {'medal': 10.85, 'final': 11.02, 'semi': 11.15, 'heat': 11.30},
            '200m': {'medal': 22.00, 'final': 22.35, 'semi': 22.60, 'heat': 22.90},
            '400m': {'medal': 49.50, 'final': 50.20, 'semi': 51.00, 'heat': 51.80},
            '800m': {'medal': 117.00, 'final': 119.00, 'semi': 121.00, 'heat': 123.00},
            '1500m': {'medal': 238.00, 'final': 242.00, 'semi': 246.00, 'heat': 250.00},
            '5000m': {'medal': 870.00, 'final': 890.00, 'semi': None, 'heat': 910.00},
            '10000m': {'medal': 1800.00, 'final': 1850.00, 'semi': None, 'heat': None},
            '100m Hurdles': {'medal': 12.45, 'final': 12.65, 'semi': 12.85, 'heat': 13.05},
            '400m Hurdles': {'medal': 53.00, 'final': 54.00, 'semi': 55.00, 'heat': 56.00},
            '3000m Steeplechase': {'medal': 555.00, 'final': 570.00, 'semi': None, 'heat': 585.00},
            'High Jump': {'medal': 2.00, 'final': 1.94, 'semi': None, 'heat': 1.90},
            'Pole Vault': {'medal': 4.85, 'final': 4.65, 'semi': None, 'heat': 4.55},
            'Long Jump': {'medal': 7.00, 'final': 6.75, 'semi': None, 'heat': 6.60},
            'Triple Jump': {'medal': 14.80, 'final': 14.40, 'semi': None, 'heat': 14.20},
            'Shot Put': {'medal': 20.00, 'final': 19.00, 'semi': None, 'heat': 18.20},
            'Discus Throw': {'medal': 68.00, 'final': 65.00, 'semi': None, 'heat': 62.00},
            'Hammer Throw': {'medal': 77.00, 'final': 74.00, 'semi': None, 'heat': 71.00},
            'Javelin Throw': {'medal': 66.00, 'final': 63.00, 'semi': None, 'heat': 60.00},
            'Heptathlon': {'medal': 6700, 'final': 6400, 'semi': None, 'heat': None},
        }
    }

    event_defaults = defaults.get(gender, {}).get(event, {})

    result = {}
    for round_name in ['medal', 'final', 'semi', 'heat']:
        value = event_defaults.get(round_name)
        if value is not None:
            result[round_name] = {
                'average': value,
                'range': (value * 0.98, value * 1.02),
                'cutoff': value,
                'editions': 0,
                'description': f'Default benchmark (typical World Championship level)'
            }

    return result


def load_benchmarks_from_db(
    db_path: str,
    event: str,
    gender: str,
    championship_type: str = 'World Championships'
) -> Dict[str, Dict]:
    """
    Load and calculate benchmarks from SQLite database.

    Args:
        db_path: Path to SQLite database
        event: Event name
        gender: 'Men' or 'Women'
        championship_type: 'Olympics', 'World Championships', 'Asian Games'

    Returns:
        Benchmark dictionary
    """
    try:
        conn = sqlite3.connect(db_path)

        # Get championship IDs
        championship_ids = BENCHMARK_CHAMPIONSHIPS.get(championship_type, [])

        if not championship_ids:
            conn.close()
            return get_default_benchmarks(event, gender)

        # Build query
        placeholders = ','.join(['?' for _ in championship_ids])
        query = f"""
            SELECT Event, Gender, Round, Position, Result_numeric, Competition_ID
            FROM results
            WHERE Event = ?
            AND Gender = ?
            AND Competition_ID IN ({placeholders})
            AND Result_numeric IS NOT NULL
        """

        params = [event, gender] + championship_ids
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            return get_default_benchmarks(event, gender)

        return calculate_round_benchmarks(df, event, gender, championship_ids)

    except Exception as e:
        print(f"Error loading benchmarks: {e}")
        return get_default_benchmarks(event, gender)


def get_benchmark_summary(benchmarks: Dict[str, Dict], event_type: str = 'time') -> str:
    """
    Generate human-readable summary of benchmarks.

    Args:
        benchmarks: Benchmark dictionary from calculate_round_benchmarks
        event_type: 'time', 'distance', or 'points'

    Returns:
        Formatted string summary
    """
    lines = []

    round_order = ['medal', 'final', 'semi', 'heat']
    round_names = {
        'medal': 'Medal Zone (Top 3)',
        'final': 'Final Zone (Top 8)',
        'semi': 'Semi-Final Qualifier',
        'heat': 'Heat Survival'
    }

    for round_key in round_order:
        if round_key in benchmarks:
            data = benchmarks[round_key]
            avg = data.get('average', 'N/A')
            range_val = data.get('range', (None, None))

            if event_type == 'time' and isinstance(avg, (int, float)):
                if avg >= 60:
                    mins = int(avg // 60)
                    secs = avg % 60
                    avg_str = f"{mins}:{secs:05.2f}"
                else:
                    avg_str = f"{avg:.2f}"
            elif isinstance(avg, (int, float)):
                avg_str = f"{avg:.2f}" if event_type == 'distance' else f"{int(avg)}"
            else:
                avg_str = str(avg)

            lines.append(f"{round_names.get(round_key, round_key)}: {avg_str}")

    return '\n'.join(lines)


def format_benchmark_for_display(value: float, event_type: str = 'time') -> str:
    """Format benchmark value for display."""
    if value is None:
        return 'N/A'

    if event_type == 'time':
        if value >= 3600:  # Hours
            hours = int(value // 3600)
            mins = int((value % 3600) // 60)
            secs = value % 60
            return f"{hours}:{mins:02d}:{secs:05.2f}"
        elif value >= 60:  # Minutes
            mins = int(value // 60)
            secs = value % 60
            return f"{mins}:{secs:05.2f}"
        else:
            return f"{value:.2f}"
    elif event_type == 'points':
        return f"{int(value)}"
    else:
        return f"{value:.2f}m"


# Methodology documentation
BENCHMARK_METHODOLOGY = """
## Championship Benchmark Methodology

### Data Sources
Benchmarks are calculated from the last 3-5 editions of each championship:
- Olympics: 2024, 2021, 2016, 2012, 2008
- World Championships: 2023, 2022, 2019, 2017, 2013
- Asian Games: 2023, 2018, 2014

### Medal Line
Average performance of gold, silver, and bronze medalists.
This represents the typical performance needed to win a medal.

### Final Line
Average performance of all finalists (typically top 8).
Athletes performing at this level are competitive for finals.

### Semi-Final Line
Estimated from qualifying performances in semi-finals.
Based on the slowest/lowest automatic qualifiers plus time qualifiers.

### Heat Survival
Minimum performance typically needed to advance from heats.
Based on historical heat qualifying times/marks.

### Limitations
- Benchmarks represent historical averages, not guarantees
- Championship conditions vary (altitude, weather, depth of field)
- Tactical racing can produce slower winning times
- Field events may have different qualifying standards each year
"""
