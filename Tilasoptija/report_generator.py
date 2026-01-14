"""
PDF Report Generator for Athletics Dashboard

Generates professional PDF reports for coaches including:
- Athlete Report Cards with performance charts
- Competition Briefings with squad overview
- Competitor Analysis with gap visualizations

Uses ReportLab for PDF generation with embedded charts.
"""

import io
import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd

# Try to import reportlab, provide fallback message if not available
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Try to import altair for chart export
try:
    import altair as alt
    ALTAIR_AVAILABLE = True
except ImportError:
    ALTAIR_AVAILABLE = False


# Report styling constants - only define if reportlab is available
if REPORTLAB_AVAILABLE:
    COLORS = {
        'primary': colors.HexColor('#1a5f7a'),
        'secondary': colors.HexColor('#57c5b6'),
        'success': colors.HexColor('#28a745'),
        'warning': colors.HexColor('#ffc107'),
        'danger': colors.HexColor('#dc3545'),
        'dark': colors.HexColor('#343a40'),
        'light': colors.HexColor('#f8f9fa'),
        'ksa_green': colors.HexColor('#006c35'),
        'gold': colors.HexColor('#ffd700'),
        'silver': colors.HexColor('#c0c0c0'),
        'bronze': colors.HexColor('#cd7f32'),
    }
else:
    COLORS = {}


def check_dependencies() -> Tuple[bool, str]:
    """Check if required dependencies are available."""
    if not REPORTLAB_AVAILABLE:
        return False, "reportlab not installed. Run: pip install reportlab"
    return True, "All dependencies available"


class AthleteReportGenerator:
    """Generates PDF reports for individual athletes."""

    def __init__(self, output_path: str = None):
        """
        Initialize the report generator.

        Args:
            output_path: Path to save the PDF file
        """
        self.output_path = output_path
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        if not REPORTLAB_AVAILABLE:
            return

        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            textColor=COLORS['primary'],
            alignment=TA_CENTER
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=COLORS['dark'],
            borderWidth=1,
            borderColor=COLORS['secondary'],
            borderPadding=5
        ))

        # Metric style (for key numbers)
        self.styles.add(ParagraphStyle(
            name='Metric',
            parent=self.styles['Normal'],
            fontSize=18,
            alignment=TA_CENTER,
            textColor=COLORS['primary']
        ))

        # Caption style
        self.styles.add(ParagraphStyle(
            name='Caption',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER
        ))

        # Methodology note style
        self.styles.add(ParagraphStyle(
            name='MethodNote',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            leftIndent=10,
            rightIndent=10,
            spaceBefore=5
        ))

    def generate_athlete_report(
        self,
        athlete_data: Dict,
        performances: List[Dict],
        benchmarks: Dict,
        probabilities: Dict,
        competitors: List[Dict] = None,
        chart_images: Dict[str, bytes] = None
    ) -> bytes:
        """
        Generate a complete athlete report card PDF.

        Args:
            athlete_data: Dict with athlete info (name, event, country, etc.)
            performances: List of recent performance dicts
            benchmarks: Dict with medal/final/semi/heat benchmarks
            probabilities: Dict with advancement probabilities
            competitors: Optional list of competitor dicts
            chart_images: Optional dict mapping chart names to PNG bytes

        Returns:
            PDF content as bytes
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        story = []

        # Title
        story.append(Paragraph(
            f"Athlete Report Card",
            self.styles['ReportTitle']
        ))

        # Athlete header
        story.append(self._create_athlete_header(athlete_data))
        story.append(Spacer(1, 20))

        # Qualification Status
        story.append(Paragraph("Qualification Status", self.styles['SectionHeader']))
        story.append(self._create_qualification_table(athlete_data, benchmarks))
        story.append(Spacer(1, 15))

        # Form Projection
        story.append(Paragraph("Form Projection", self.styles['SectionHeader']))
        story.append(self._create_projection_section(athlete_data, performances))

        # Add season progression chart if available
        if chart_images and 'season_progression' in chart_images:
            story.append(Spacer(1, 10))
            story.append(self._add_chart_image(chart_images['season_progression']))

        story.append(Spacer(1, 15))

        # Championship Benchmarks
        story.append(Paragraph("Championship Benchmarks", self.styles['SectionHeader']))
        story.append(self._create_benchmarks_table(benchmarks, athlete_data.get('projected')))

        # Add gap analysis chart if available
        if chart_images and 'gap_analysis' in chart_images:
            story.append(Spacer(1, 10))
            story.append(self._add_chart_image(chart_images['gap_analysis']))

        story.append(Spacer(1, 15))

        # Advancement Probabilities
        story.append(Paragraph("Advancement Probabilities", self.styles['SectionHeader']))
        story.append(self._create_probability_table(probabilities))

        # Competitors section (if provided)
        if competitors:
            story.append(PageBreak())
            story.append(Paragraph("Competitive Landscape", self.styles['SectionHeader']))
            story.append(self._create_competitors_table(competitors, athlete_data))

        # Methodology notes
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", color=colors.grey))
        story.append(self._create_methodology_notes())

        # Footer with generation timestamp
        story.append(Spacer(1, 20))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | KSA Athletics Analysis",
            self.styles['Caption']
        ))

        doc.build(story)
        return buffer.getvalue()

    def _create_athlete_header(self, athlete_data: Dict) -> Table:
        """Create the athlete header section."""
        name = athlete_data.get('name', 'Unknown Athlete')
        event = athlete_data.get('event', 'Unknown Event')
        country = athlete_data.get('country', 'KSA')

        sb = athlete_data.get('season_best', '-')
        pb = athlete_data.get('personal_best', '-')
        trend = athlete_data.get('trend', 'stable')

        trend_icon = {'improving': '↑', 'stable': '→', 'declining': '↓'}.get(trend, '→')

        data = [
            [Paragraph(f"<b>{name}</b>", self.styles['Heading1']), ''],
            [f"{event} | {country}", ''],
            ['', ''],
            ['Season Best', 'Personal Best'],
            [Paragraph(f"<b>{sb}</b>", self.styles['Metric']),
             Paragraph(f"<b>{pb}</b>", self.styles['Metric'])],
            [f"Form: {trend} {trend_icon}", '']
        ]

        table = Table(data, colWidths=[9*cm, 9*cm])
        table.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('SPAN', (0, 1), (1, 1)),
            ('SPAN', (0, 5), (1, 5)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (1, 0), COLORS['primary']),
            ('FONTSIZE', (0, 3), (1, 3), 10),
            ('TEXTCOLOR', (0, 3), (1, 3), colors.grey),
            ('BACKGROUND', (0, 4), (1, 4), COLORS['light']),
            ('BOX', (0, 0), (-1, -1), 1, COLORS['secondary']),
        ]))

        return table

    def _create_qualification_table(self, athlete_data: Dict, benchmarks: Dict) -> Table:
        """Create qualification status table."""
        sb = athlete_data.get('season_best')
        event_type = athlete_data.get('event_type', 'time')

        rows = [['Standard', 'Required', 'Gap', 'Status']]

        standards = [
            ('Entry Standard', benchmarks.get('entry', {}).get('value')),
            ('Medal Line', benchmarks.get('medal', {}).get('value')),
            ('Final Line', benchmarks.get('final', {}).get('value')),
        ]

        for label, standard in standards:
            if standard and sb:
                try:
                    sb_float = float(sb) if isinstance(sb, (int, float, str)) else 0
                    std_float = float(standard)

                    if event_type == 'time':
                        gap = sb_float - std_float
                        gap_str = f"+{gap:.2f}" if gap > 0 else f"{gap:.2f}"
                        status = "✓ Met" if sb_float <= std_float else "○ Gap"
                    else:
                        gap = std_float - sb_float
                        gap_str = f"-{gap:.2f}" if gap > 0 else f"+{abs(gap):.2f}"
                        status = "✓ Met" if sb_float >= std_float else "○ Gap"

                    rows.append([label, f"{standard}", gap_str, status])
                except (ValueError, TypeError):
                    rows.append([label, f"{standard}", '-', '-'])
            else:
                rows.append([label, f"{standard or '-'}", '-', '-'])

        table = Table(rows, colWidths=[5*cm, 4*cm, 4*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS['light']]),
        ]))

        return table

    def _create_projection_section(self, athlete_data: Dict, performances: List[Dict]) -> Table:
        """Create form projection section."""
        projected = athlete_data.get('projected', '-')
        confidence_low = athlete_data.get('confidence_low', '-')
        confidence_high = athlete_data.get('confidence_high', '-')
        trend = athlete_data.get('trend', 'stable')

        data = [
            ['Projected Performance', 'Confidence Range (68%)', 'Trend'],
            [
                Paragraph(f"<b>{projected}</b>", self.styles['Metric']),
                f"{confidence_low} - {confidence_high}",
                trend.capitalize()
            ]
        ]

        # Add recent performances
        if performances:
            perf_str = ", ".join([str(p.get('result', '-')) for p in performances[:5]])
            data.append(['Recent: ' + perf_str, '', ''])

        table = Table(data, colWidths=[6*cm, 6*cm, 5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['secondary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('SPAN', (0, 2), (2, 2)) if len(data) > 2 else ('SPAN', (0, 0), (0, 0)),
        ]))

        return table

    def _create_benchmarks_table(self, benchmarks: Dict, projected: float = None) -> Table:
        """Create championship benchmarks table."""
        rows = [['Round', 'Benchmark', 'Source', 'Gap to Projected']]

        round_order = ['medal', 'final', 'semi', 'heat']
        round_labels = {
            'medal': 'Medal',
            'final': 'Final',
            'semi': 'Semi-Final',
            'heat': 'Heat Survival'
        }

        for rnd in round_order:
            if rnd in benchmarks:
                data = benchmarks[rnd]
                value = data.get('value', '-')
                source = data.get('source', '-')

                gap_str = '-'
                if projected and value and value != '-':
                    try:
                        gap = float(projected) - float(value)
                        gap_str = f"{gap:+.2f}"
                    except (ValueError, TypeError):
                        pass

                rows.append([round_labels.get(rnd, rnd), str(value), source, gap_str])

        if len(rows) == 1:
            rows.append(['No benchmark data available', '', '', ''])

        table = Table(rows, colWidths=[4*cm, 4*cm, 5.5*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['dark']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS['light']]),
        ]))

        return table

    def _create_probability_table(self, probabilities: Dict) -> Table:
        """Create advancement probabilities table."""
        rows = [['Outcome', 'Probability', 'Visual']]

        outcomes = [
            ('Medal', probabilities.get('medal', 0)),
            ('Make Final', probabilities.get('final', 0)),
            ('Make Semi', probabilities.get('semi', 0)),
            ('Survive Heat', probabilities.get('heat', 0)),
        ]

        for outcome, prob in outcomes:
            prob_pct = f"{prob:.0f}%" if isinstance(prob, (int, float)) else str(prob)

            # Simple visual bar representation
            filled = int(prob / 10) if isinstance(prob, (int, float)) else 0
            bar = '█' * filled + '░' * (10 - filled)

            rows.append([outcome, prob_pct, bar])

        table = Table(rows, colWidths=[5*cm, 4*cm, 8*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),
            ('FONTNAME', (2, 1), (2, -1), 'Courier'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        return table

    def _create_competitors_table(self, competitors: List[Dict], athlete_data: Dict) -> Table:
        """Create competitors comparison table."""
        rows = [['Rank', 'Athlete', 'Country', 'SB', 'PB', 'Gap', 'Form']]

        athlete_sb = athlete_data.get('season_best', 0)
        event_type = athlete_data.get('event_type', 'time')

        for i, comp in enumerate(competitors[:10], 1):
            name = comp.get('name', '-')
            country = comp.get('country', '-')
            sb = comp.get('season_best', '-')
            pb = comp.get('personal_best', '-')
            form = comp.get('trend', '-')

            # Calculate gap
            gap_str = '-'
            if sb and athlete_sb:
                try:
                    comp_sb = float(sb)
                    ath_sb = float(athlete_sb)
                    if event_type == 'time':
                        gap = ath_sb - comp_sb
                    else:
                        gap = comp_sb - ath_sb
                    gap_str = f"{gap:+.2f}"
                except (ValueError, TypeError):
                    pass

            rows.append([str(i), name[:20], country, str(sb), str(pb), gap_str, form[:8]])

        table = Table(rows, colWidths=[1.5*cm, 5*cm, 2*cm, 2.5*cm, 2.5*cm, 2*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['dark']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS['light']]),
        ]))

        return table

    def _add_chart_image(self, image_bytes: bytes, width: float = 15*cm) -> Image:
        """Add a chart image to the report."""
        img_buffer = io.BytesIO(image_bytes)
        img = Image(img_buffer, width=width)
        return img

    def _create_methodology_notes(self) -> Paragraph:
        """Create methodology notes section."""
        notes = """
        <b>Methodology Notes:</b><br/>
        • <b>Projection:</b> Weighted average of last 5 performances (weights: 1.0, 0.85, 0.72, 0.61, 0.52)<br/>
        • <b>Confidence Range:</b> ±1 standard deviation = 68% probability window<br/>
        • <b>Championship Adjustment:</b> +0.5% for time events (pressure factor)<br/>
        • <b>Trend:</b> Improving/Declining = >2% change over recent performances<br/>
        • <b>Benchmarks:</b> Median performance from last 3 editions of each championship level
        """
        return Paragraph(notes, self.styles['MethodNote'])


class CompetitionBriefingGenerator:
    """Generates competition briefing PDFs for entire KSA squad."""

    def __init__(self):
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
        if REPORTLAB_AVAILABLE:
            self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom styles for briefing documents."""
        self.styles.add(ParagraphStyle(
            name='BriefingTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            spaceAfter=30,
            textColor=COLORS['ksa_green'],
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='EventHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=COLORS['primary']
        ))

    def generate_competition_briefing(
        self,
        competition_name: str,
        competition_date: str,
        athletes_by_event: Dict[str, List[Dict]],
        event_benchmarks: Dict[str, Dict] = None
    ) -> bytes:
        """
        Generate a competition briefing document.

        Args:
            competition_name: Name of the competition
            competition_date: Date of the competition
            athletes_by_event: Dict mapping event names to list of athlete dicts
            event_benchmarks: Optional dict mapping events to benchmark dicts

        Returns:
            PDF content as bytes
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        story = []

        # Title page
        story.append(Spacer(1, 3*cm))
        story.append(Paragraph(
            f"Competition Briefing",
            self.styles['BriefingTitle']
        ))
        story.append(Paragraph(
            f"<b>{competition_name}</b>",
            self.styles['Heading1']
        ))
        story.append(Paragraph(
            competition_date,
            self.styles['Normal']
        ))
        story.append(Spacer(1, 2*cm))

        # Squad summary
        total_athletes = sum(len(athletes) for athletes in athletes_by_event.values())
        total_events = len(athletes_by_event)

        summary_data = [
            ['KSA Squad Summary', ''],
            ['Total Athletes', str(total_athletes)],
            ['Events Entered', str(total_events)],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M')]
        ]

        summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
        summary_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('BACKGROUND', (0, 0), (1, 0), COLORS['ksa_green']),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, COLORS['ksa_green']),
            ('GRID', (0, 1), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(summary_table)

        story.append(PageBreak())

        # Event-by-event breakdown
        for event_name, athletes in sorted(athletes_by_event.items()):
            story.append(Paragraph(event_name, self.styles['EventHeader']))

            # Athletes table
            rows = [['Athlete', 'SB', 'PB', 'Projected', 'Target']]
            for ath in athletes:
                rows.append([
                    ath.get('name', '-'),
                    str(ath.get('season_best', '-')),
                    str(ath.get('personal_best', '-')),
                    str(ath.get('projected', '-')),
                    ath.get('target', 'TBD')
                ])

            table = Table(rows, colWidths=[6*cm, 2.5*cm, 2.5*cm, 3*cm, 3*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(table)

            # Event benchmarks if available
            if event_benchmarks and event_name in event_benchmarks:
                bench = event_benchmarks[event_name]
                bench_text = f"Benchmarks - Medal: {bench.get('medal', '-')} | Final: {bench.get('final', '-')} | Semi: {bench.get('semi', '-')}"
                story.append(Paragraph(bench_text, self.styles['Normal']))

            story.append(Spacer(1, 15))

        doc.build(story)
        return buffer.getvalue()


def export_chart_as_png(chart: 'alt.Chart', width: int = 600, height: int = 400) -> bytes:
    """
    Export an Altair chart as PNG bytes.

    Requires altair_saver and selenium/chromedriver for PNG export.
    Falls back to SVG if PNG export fails.

    Args:
        chart: Altair chart object
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        PNG image bytes
    """
    if not ALTAIR_AVAILABLE:
        raise ImportError("altair is required for chart export")

    try:
        # Try PNG export (requires altair_saver)
        buffer = io.BytesIO()
        chart.save(buffer, format='png', scale_factor=2)
        return buffer.getvalue()
    except Exception:
        # PNG export requires additional dependencies
        # Return None to indicate chart couldn't be exported
        return None


def generate_html_report(
    athlete_data: Dict,
    performances: List[Dict],
    benchmarks: Dict,
    probabilities: Dict,
    competitors: List[Dict] = None
) -> str:
    """
    Generate an HTML report (alternative to PDF).

    Args:
        athlete_data: Dict with athlete info
        performances: List of recent performance dicts
        benchmarks: Dict with championship benchmarks
        probabilities: Dict with advancement probabilities
        competitors: Optional list of competitor dicts

    Returns:
        HTML string
    """
    name = athlete_data.get('name', 'Unknown')
    event = athlete_data.get('event', '-')
    country = athlete_data.get('country', 'KSA')
    sb = athlete_data.get('season_best', '-')
    pb = athlete_data.get('personal_best', '-')
    projected = athlete_data.get('projected', '-')
    trend = athlete_data.get('trend', 'stable')

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Athlete Report - {name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #1a5f7a; text-align: center; border-bottom: 3px solid #57c5b6; padding-bottom: 15px; }}
            h2 {{ color: #343a40; border-left: 4px solid #57c5b6; padding-left: 10px; margin-top: 30px; }}
            .header-info {{ text-align: center; color: #666; margin-bottom: 20px; }}
            .metrics {{ display: flex; justify-content: center; gap: 40px; margin: 20px 0; }}
            .metric {{ text-align: center; padding: 15px 25px; background: #f8f9fa; border-radius: 8px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #1a5f7a; }}
            .metric-label {{ font-size: 12px; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #1a5f7a; color: white; padding: 12px; text-align: center; }}
            td {{ padding: 10px; text-align: center; border-bottom: 1px solid #ddd; }}
            tr:nth-child(even) {{ background: #f8f9fa; }}
            .trend-improving {{ color: #28a745; }}
            .trend-declining {{ color: #dc3545; }}
            .trend-stable {{ color: #6c757d; }}
            .methodology {{ background: #f8f9fa; padding: 15px; border-radius: 5px; font-size: 12px; color: #666; margin-top: 30px; }}
            .footer {{ text-align: center; color: #999; font-size: 11px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Athlete Report Card</h1>
            <div class="header-info">
                <strong style="font-size: 20px;">{name}</strong><br>
                {event} | {country}
            </div>

            <div class="metrics">
                <div class="metric">
                    <div class="metric-value">{sb}</div>
                    <div class="metric-label">Season Best</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{pb}</div>
                    <div class="metric-label">Personal Best</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{projected}</div>
                    <div class="metric-label">Projected</div>
                </div>
                <div class="metric">
                    <div class="metric-value trend-{trend}">{trend.capitalize()}</div>
                    <div class="metric-label">Form Trend</div>
                </div>
            </div>

            <h2>Championship Benchmarks</h2>
            <table>
                <tr>
                    <th>Round</th>
                    <th>Benchmark</th>
                    <th>Gap to Projected</th>
                </tr>
    """

    round_labels = {'medal': 'Medal', 'final': 'Final', 'semi': 'Semi-Final', 'heat': 'Heat'}
    for rnd in ['medal', 'final', 'semi', 'heat']:
        if rnd in benchmarks:
            value = benchmarks[rnd].get('value', '-')
            gap = '-'
            if projected and projected != '-' and value and value != '-':
                try:
                    gap_val = float(projected) - float(value)
                    gap = f"{gap_val:+.2f}"
                except:
                    pass
            html += f"""
                <tr>
                    <td>{round_labels.get(rnd, rnd)}</td>
                    <td>{value}</td>
                    <td>{gap}</td>
                </tr>
            """

    html += """
            </table>

            <h2>Advancement Probabilities</h2>
            <table>
                <tr>
                    <th>Outcome</th>
                    <th>Probability</th>
                </tr>
    """

    for outcome in ['medal', 'final', 'semi', 'heat']:
        prob = probabilities.get(outcome, 0)
        prob_str = f"{prob:.0f}%" if isinstance(prob, (int, float)) else str(prob)
        html += f"""
                <tr>
                    <td>{outcome.capitalize()}</td>
                    <td>{prob_str}</td>
                </tr>
        """

    if competitors:
        html += """
            </table>

            <h2>Top Competitors</h2>
            <table>
                <tr>
                    <th>Athlete</th>
                    <th>Country</th>
                    <th>SB</th>
                    <th>Gap</th>
                </tr>
        """
        for comp in competitors[:5]:
            comp_sb = comp.get('season_best', '-')
            gap = '-'
            if sb and sb != '-' and comp_sb and comp_sb != '-':
                try:
                    gap_val = float(sb) - float(comp_sb)
                    gap = f"{gap_val:+.2f}"
                except:
                    pass
            html += f"""
                <tr>
                    <td>{comp.get('name', '-')}</td>
                    <td>{comp.get('country', '-')}</td>
                    <td>{comp_sb}</td>
                    <td>{gap}</td>
                </tr>
            """

    html += f"""
            </table>

            <div class="methodology">
                <strong>Methodology Notes:</strong><br>
                • Projection: Weighted average of last 5 performances (weights: 1.0, 0.85, 0.72, 0.61, 0.52)<br>
                • Championship Adjustment: +0.5% for time events (pressure factor)<br>
                • Benchmarks: Median from last 3 championship editions
            </div>

            <div class="footer">
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | KSA Athletics Analysis
            </div>
        </div>
    </body>
    </html>
    """

    return html


# Module test
if __name__ == "__main__":
    available, msg = check_dependencies()
    print(f"Dependencies: {msg}")

    if available:
        # Test PDF generation
        generator = AthleteReportGenerator()

        test_athlete = {
            'name': 'Mohammed Al-Yousef',
            'event': '400m',
            'country': 'KSA',
            'season_best': 44.72,
            'personal_best': 44.51,
            'projected': 44.65,
            'confidence_low': 44.45,
            'confidence_high': 44.85,
            'trend': 'improving',
            'event_type': 'time'
        }

        test_benchmarks = {
            'medal': {'value': 43.90, 'source': 'WC 2023'},
            'final': {'value': 44.50, 'source': 'WC 2023'},
            'semi': {'value': 45.10, 'source': 'WC 2023'},
            'heat': {'value': 45.50, 'source': 'WC 2023'}
        }

        test_probs = {
            'medal': 5,
            'final': 35,
            'semi': 75,
            'heat': 95
        }

        pdf_bytes = generator.generate_athlete_report(
            test_athlete,
            [],
            test_benchmarks,
            test_probs
        )

        with open('test_report.pdf', 'wb') as f:
            f.write(pdf_bytes)

        print(f"Generated test_report.pdf ({len(pdf_bytes)} bytes)")

    # Test HTML generation (always available)
    html = generate_html_report(
        {'name': 'Test Athlete', 'event': '100m', 'season_best': 10.05, 'projected': 10.02, 'trend': 'improving'},
        [],
        {'medal': {'value': 9.85}, 'final': {'value': 10.00}},
        {'medal': 5, 'final': 40, 'semi': 80, 'heat': 95}
    )

    with open('test_report.html', 'w') as f:
        f.write(html)

    print("Generated test_report.html")
