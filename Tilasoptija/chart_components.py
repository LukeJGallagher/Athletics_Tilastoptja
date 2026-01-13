"""
Chart Components for Athletics Dashboard

Reusable Altair chart components for:
- Season progression timelines
- Gap analysis visuals
- Probability gauges
- Competitor comparison bars
- Performance distribution histograms

All charts styled for dark theme and export-ready.
"""

import altair as alt
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# Chart color palette (dark theme compatible)
COLORS = {
    'primary': '#00FF7F',      # Spring green (KSA athlete)
    'secondary': '#4ECDC4',    # Teal
    'warning': '#FFD700',      # Gold
    'danger': '#FF6B6B',       # Coral red
    'success': '#00FF7F',      # Green
    'medal_gold': '#FFD700',
    'medal_silver': '#C0C0C0',
    'medal_bronze': '#CD7F32',
    'final_line': '#4ECDC4',
    'semi_line': '#FFD700',
    'heat_line': '#FF6B6B',
    'background': '#1a1a1a',
    'text': '#ffffff',
    'grid': '#333333',
    'competitor': '#888888'
}

# Base chart configuration for dark theme
def get_base_config():
    """Get base Altair configuration for dark theme."""
    return {
        'background': COLORS['background'],
        'title': {'color': COLORS['text']},
        'axis': {
            'labelColor': COLORS['text'],
            'titleColor': COLORS['text'],
            'gridColor': COLORS['grid'],
            'domainColor': COLORS['grid']
        },
        'legend': {
            'labelColor': COLORS['text'],
            'titleColor': COLORS['text']
        },
        'view': {'stroke': 'transparent'}
    }


def season_progression_chart(
    performances: List[Dict],
    benchmarks: Dict[str, float] = None,
    event_type: str = 'time',
    title: str = 'Season Progression',
    width: int = 600,
    height: int = 300
) -> alt.Chart:
    """
    Create season progression line chart with benchmark overlays.

    Args:
        performances: List of dicts with 'date', 'result', 'competition' keys
        benchmarks: Dict with 'medal', 'final', 'semi', 'heat' lines
        event_type: 'time' (inverted y-axis) or 'distance'/'points'
        title: Chart title
        width: Chart width in pixels
        height: Chart height in pixels

    Returns:
        Altair chart object
    """
    if not performances:
        return alt.Chart().mark_text().encode(
            text=alt.value('No performance data available')
        ).properties(width=width, height=height)

    # Create DataFrame
    df = pd.DataFrame(performances)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')  # Ensure chronological order

    # Filter to recent performances only (last 2 years) for cleaner display
    two_years_ago = pd.Timestamp.now() - pd.Timedelta(days=730)
    df_recent = df[df['date'] >= two_years_ago]
    if df_recent.empty:
        df_recent = df.tail(20)  # Fallback to last 20 if no recent data

    # Calculate y-axis domain based on data + benchmarks
    all_values = df_recent['result'].tolist()
    if benchmarks:
        all_values.extend([v for v in benchmarks.values() if v is not None])

    y_min = min(all_values) * 0.98 if event_type != 'time' else min(all_values) - 0.5
    y_max = max(all_values) * 1.02 if event_type != 'time' else max(all_values) + 0.5

    # For time events: lower is better, so reverse axis
    # y_min should be the BEST (lowest) time, y_max the WORST (highest)
    y_scale = alt.Scale(
        domain=[y_max, y_min] if event_type == 'time' else [y_min, y_max],
        nice=True
    )

    # Calculate date range for appropriate axis formatting
    date_range = (df_recent['date'].max() - df_recent['date'].min()).days

    # Base performance line with cleaner date axis
    base = alt.Chart(df_recent).encode(
        x=alt.X('date:T',
                title='Date',
                axis=alt.Axis(
                    format='%b %y',  # Shorter format: "Jan 24"
                    labelAngle=-45,
                    tickCount=min(len(df_recent), 6)  # Fewer tick marks
                )),
        tooltip=[
            alt.Tooltip('date:T', title='Date', format='%d %b %Y'),
            alt.Tooltip('result:Q', title='Result', format='.2f'),
            alt.Tooltip('competition:N', title='Competition')
        ]
    )

    # Performance points and line - use shared y_scale
    points = base.mark_circle(size=80, color=COLORS['primary']).encode(
        y=alt.Y('result:Q', title='Performance', scale=y_scale)
    )

    line = base.mark_line(color=COLORS['primary'], strokeWidth=2).encode(
        y=alt.Y('result:Q', scale=y_scale)
    )

    chart = line + points

    # Add benchmark lines if provided
    if benchmarks:
        benchmark_data = []
        benchmark_colors = {
            'medal': COLORS['medal_gold'],
            'final': COLORS['final_line'],
            'semi': COLORS['semi_line'],
            'heat': COLORS['heat_line']
        }
        benchmark_labels = {
            'medal': 'Medal Line',
            'final': 'Final Line',
            'semi': 'Semi Line',
            'heat': 'Heat Line'
        }

        for key, value in benchmarks.items():
            if value is not None and key in benchmark_colors:
                benchmark_data.append({
                    'benchmark': benchmark_labels.get(key, key),
                    'value': value,
                    'color': benchmark_colors[key]
                })

        if benchmark_data:
            bench_df = pd.DataFrame(benchmark_data)

            # Use same y_scale for benchmark rules
            rules = alt.Chart(bench_df).mark_rule(strokeDash=[5, 5]).encode(
                y=alt.Y('value:Q', scale=y_scale),
                color=alt.Color('benchmark:N',
                               scale=alt.Scale(
                                   domain=list(benchmark_labels.values()),
                                   range=list(benchmark_colors.values())
                               ),
                               legend=alt.Legend(title='Benchmarks')),
                strokeWidth=alt.value(2)
            )

            # Add labels for benchmark lines - use same y_scale
            labels = alt.Chart(bench_df).mark_text(
                align='right',
                dx=-5,
                dy=-5,
                fontSize=10
            ).encode(
                y=alt.Y('value:Q', scale=y_scale),
                text='benchmark:N',
                color=alt.Color('benchmark:N',
                               scale=alt.Scale(
                                   domain=list(benchmark_labels.values()),
                                   range=list(benchmark_colors.values())
                               ),
                               legend=None)
            )

            chart = chart + rules + labels

    return chart.properties(
        width=width,
        height=height,
        title=title
    ).configure(**get_base_config())


def gap_analysis_chart(
    athlete_performance: float,
    benchmarks: Dict[str, float],
    event_type: str = 'time',
    title: str = 'Gap Analysis',
    width: int = 500,
    height: int = 200
) -> alt.Chart:
    """
    Create horizontal bar chart showing gap to each benchmark.

    Args:
        athlete_performance: Athlete's season best or projected performance
        benchmarks: Dict with benchmark values
        event_type: 'time', 'distance', or 'points'
        title: Chart title
        width: Chart width
        height: Chart height

    Returns:
        Altair chart object
    """
    data = []

    benchmark_order = ['medal', 'final', 'semi', 'heat']
    benchmark_labels = {
        'medal': 'Medal Line',
        'final': 'Final Line',
        'semi': 'Semi Line',
        'heat': 'Heat Line'
    }

    for key in benchmark_order:
        if key in benchmarks and benchmarks[key] is not None:
            target = benchmarks[key]
            if event_type == 'time':
                gap = athlete_performance - target  # Positive = behind
            else:
                gap = target - athlete_performance  # Positive = behind

            data.append({
                'benchmark': benchmark_labels.get(key, key),
                'target': target,
                'gap': gap,
                'status': 'Ahead' if gap < 0 else 'Behind',
                'order': benchmark_order.index(key)
            })

    if not data:
        return alt.Chart().mark_text().encode(
            text=alt.value('No benchmark data available')
        ).properties(width=width, height=height)

    df = pd.DataFrame(data)

    # Create bar chart
    bars = alt.Chart(df).mark_bar().encode(
        y=alt.Y('benchmark:N',
                title=None,
                sort=alt.EncodingSortField(field='order', order='ascending')),
        x=alt.X('gap:Q',
                title='Gap (negative = ahead, positive = behind)',
                scale=alt.Scale(domain=[-max(abs(df['gap'].min()), abs(df['gap'].max())) * 1.2,
                                        max(abs(df['gap'].min()), abs(df['gap'].max())) * 1.2])),
        color=alt.condition(
            alt.datum.gap < 0,
            alt.value(COLORS['success']),
            alt.value(COLORS['danger'])
        ),
        tooltip=['benchmark:N', 'target:Q', 'gap:Q', 'status:N']
    )

    # Add zero line
    zero_line = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(
        color=COLORS['text'],
        strokeWidth=2
    ).encode(x='x:Q')

    # Add gap labels
    labels = alt.Chart(df).mark_text(
        align='left',
        dx=5,
        fontSize=12,
        color=COLORS['text']
    ).encode(
        y=alt.Y('benchmark:N', sort=alt.EncodingSortField(field='order', order='ascending')),
        x=alt.X('gap:Q'),
        text=alt.Text('gap:Q', format='+.2f')
    )

    return (bars + zero_line + labels).properties(
        width=width,
        height=height,
        title=title
    ).configure(**get_base_config())


def probability_gauge(
    probabilities: Dict[str, float],
    title: str = 'Advancement Probability',
    width: int = 400,
    height: int = 150
) -> alt.Chart:
    """
    Create probability gauge bars for each round.

    Args:
        probabilities: Dict with round names and probability percentages
        title: Chart title
        width: Chart width
        height: Chart height

    Returns:
        Altair chart object
    """
    data = []
    round_order = ['heat', 'semi', 'final', 'medal']
    round_labels = {
        'heat': 'Make Heats',
        'semi': 'Make Semis',
        'final': 'Make Finals',
        'medal': 'Win Medal'
    }

    for i, key in enumerate(round_order):
        if key in probabilities:
            prob = probabilities[key]
            data.append({
                'round': round_labels.get(key, key),
                'probability': prob,
                'order': i,
                'prob_text': f"{prob:.0f}%"
            })

    if not data:
        return alt.Chart().mark_text().encode(
            text=alt.value('No probability data')
        ).properties(width=width, height=height)

    df = pd.DataFrame(data)

    # Background bars (100%)
    background = alt.Chart(df).mark_bar(color=COLORS['grid']).encode(
        y=alt.Y('round:N',
                title=None,
                sort=alt.EncodingSortField(field='order', order='descending')),
        x=alt.X('max_val:Q',
                title='Probability %',
                scale=alt.Scale(domain=[0, 100]))
    ).transform_calculate(max_val='100')

    # Probability bars - use transform_calculate for color classification
    bars = alt.Chart(df).transform_calculate(
        color_category="datum.probability >= 70 ? 'high' : (datum.probability >= 40 ? 'medium' : 'low')"
    ).mark_bar().encode(
        y=alt.Y('round:N', sort=alt.EncodingSortField(field='order', order='descending')),
        x=alt.X('probability:Q'),
        color=alt.Color('color_category:N',
                       scale=alt.Scale(
                           domain=['high', 'medium', 'low'],
                           range=[COLORS['success'], COLORS['warning'], COLORS['danger']]
                       ),
                       legend=None),
        tooltip=['round:N', 'probability:Q']
    )

    # Probability labels
    labels = alt.Chart(df).mark_text(
        align='left',
        dx=5,
        fontSize=12,
        fontWeight='bold',
        color=COLORS['text']
    ).encode(
        y=alt.Y('round:N', sort=alt.EncodingSortField(field='order', order='descending')),
        x=alt.X('probability:Q'),
        text='prob_text:N'
    )

    return (background + bars + labels).properties(
        width=width,
        height=height,
        title=title
    ).configure(**get_base_config())


def competitor_comparison_chart(
    athlete_name: str,
    athlete_sb: float,
    competitors: List[Dict],
    event_type: str = 'time',
    title: str = 'Competitor Comparison',
    width: int = 600,
    height: int = 400
) -> alt.Chart:
    """
    Create horizontal bar chart comparing athlete to competitors.

    Args:
        athlete_name: Name of the main athlete
        athlete_sb: Athlete's season best
        competitors: List of competitor dicts with 'name', 'country', 'sb', 'gap'
        event_type: 'time', 'distance', or 'points'
        title: Chart title
        width: Chart width
        height: Chart height

    Returns:
        Altair chart object
    """
    data = []

    # Add main athlete
    data.append({
        'name': athlete_name,
        'sb': athlete_sb,
        'is_athlete': True,
        'label': f"{athlete_name} (YOU)"
    })

    # Add competitors
    for comp in competitors[:15]:  # Limit to top 15
        data.append({
            'name': comp.get('name', 'Unknown'),
            'sb': comp.get('sb', 0),
            'is_athlete': False,
            'label': f"{comp.get('name', '')} ({comp.get('country', '')})"
        })

    df = pd.DataFrame(data)

    # Sort by performance
    df = df.sort_values('sb', ascending=(event_type == 'time'))

    bars = alt.Chart(df).mark_bar().encode(
        y=alt.Y('label:N',
                title=None,
                sort=alt.EncodingSortField(field='sb', order='ascending' if event_type == 'time' else 'descending')),
        x=alt.X('sb:Q',
                title='Season Best',
                scale=alt.Scale(reverse=(event_type != 'time'))),
        color=alt.condition(
            alt.datum.is_athlete,
            alt.value(COLORS['primary']),
            alt.value(COLORS['competitor'])
        ),
        tooltip=['name:N', 'sb:Q']
    )

    # Add value labels
    labels = alt.Chart(df).mark_text(
        align='left',
        dx=5,
        fontSize=10,
        color=COLORS['text']
    ).encode(
        y=alt.Y('label:N', sort=alt.EncodingSortField(field='sb', order='ascending' if event_type == 'time' else 'descending')),
        x=alt.X('sb:Q'),
        text=alt.Text('sb:Q', format='.2f')
    )

    return (bars + labels).properties(
        width=width,
        height=height,
        title=title
    ).configure(**get_base_config())


def form_trend_chart(
    performances: List[Dict],
    event_type: str = 'time',
    title: str = 'Recent Form Trend',
    width: int = 400,
    height: int = 200
) -> alt.Chart:
    """
    Create small form trend sparkline with trend indicator.

    Args:
        performances: List of dicts with 'date', 'result' keys (most recent first)
        event_type: 'time', 'distance', or 'points'
        title: Chart title
        width: Chart width
        height: Chart height

    Returns:
        Altair chart object
    """
    if not performances:
        return alt.Chart().mark_text().encode(
            text=alt.value('No data')
        ).properties(width=width, height=height)

    df = pd.DataFrame(performances)
    df['index'] = range(len(df))

    # Line chart
    line = alt.Chart(df).mark_line(
        color=COLORS['primary'],
        strokeWidth=3
    ).encode(
        x=alt.X('index:O', title='Recent Performances', axis=alt.Axis(labels=False)),
        y=alt.Y('result:Q',
                title='Performance',
                scale=alt.Scale(reverse=(event_type == 'time')))
    )

    # Points
    points = alt.Chart(df).mark_circle(
        size=100,
        color=COLORS['primary']
    ).encode(
        x=alt.X('index:O'),
        y=alt.Y('result:Q'),
        tooltip=['result:Q']
    )

    # Trend line (linear regression)
    trend = alt.Chart(df).transform_regression(
        'index', 'result'
    ).mark_line(
        color=COLORS['warning'],
        strokeDash=[5, 5],
        strokeWidth=2
    ).encode(
        x='index:O',
        y='result:Q'
    )

    return (line + points + trend).properties(
        width=width,
        height=height,
        title=title
    ).configure(**get_base_config())


def create_report_charts(
    athlete_data: Dict,
    performances: List[Dict],
    benchmarks: Dict[str, float],
    competitors: List[Dict],
    probabilities: Dict[str, float],
    event_type: str = 'time'
) -> Dict[str, alt.Chart]:
    """
    Create all charts needed for an athlete report card.

    Args:
        athlete_data: Dict with athlete info
        performances: List of performance dicts
        benchmarks: Dict with benchmark values
        competitors: List of competitor dicts
        probabilities: Dict with round probabilities
        event_type: 'time', 'distance', or 'points'

    Returns:
        Dict of chart name -> Altair chart object
    """
    charts = {}

    # Season progression
    charts['season_progression'] = season_progression_chart(
        performances=performances,
        benchmarks=benchmarks,
        event_type=event_type,
        title=f"Season Progression - {athlete_data.get('name', 'Athlete')}"
    )

    # Gap analysis
    if performances:
        athlete_sb = performances[0].get('result', 0)
        charts['gap_analysis'] = gap_analysis_chart(
            athlete_performance=athlete_sb,
            benchmarks=benchmarks,
            event_type=event_type,
            title='Gap to Championship Benchmarks'
        )

    # Probability gauge
    charts['probability'] = probability_gauge(
        probabilities=probabilities,
        title='Advancement Probability'
    )

    # Competitor comparison
    if performances and competitors:
        charts['competitors'] = competitor_comparison_chart(
            athlete_name=athlete_data.get('name', 'Athlete'),
            athlete_sb=performances[0].get('result', 0),
            competitors=competitors,
            event_type=event_type,
            title='Season Best Comparison'
        )

    # Form trend
    charts['form_trend'] = form_trend_chart(
        performances=performances[:10],  # Last 10
        event_type=event_type,
        title='Recent Form'
    )

    return charts


def chart_to_html(chart: alt.Chart) -> str:
    """Convert Altair chart to HTML string for embedding in reports."""
    return chart.to_html()


def chart_to_png_base64(chart: alt.Chart) -> str:
    """
    Convert Altair chart to base64 PNG for embedding in PDFs.

    Note: Requires altair_saver and selenium/chromedriver.
    Falls back to SVG if PNG generation fails.
    """
    try:
        import io
        import base64
        png_data = chart.save(fp=None, format='png')
        return base64.b64encode(png_data).decode('utf-8')
    except Exception:
        # Fall back to SVG
        try:
            svg_data = chart.save(fp=None, format='svg')
            return base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''
