"""
Diagnose Azure SQL Database Content
Check for para-athletics contamination and data completeness
"""

from dotenv import load_dotenv
load_dotenv()

from azure_db import query_data, get_connection_mode
import pandas as pd
import re

def is_para_athletics_event(event_name):
    """
    Detect if an event is para-athletics based on classification codes.

    Para-athletics events have codes like:
    - T11-T13, T20, T31-T38, T40-T47, T51-T54 (Track)
    - F11-F13, F20, F31-F38, F40-F46, F51-F57 (Field)
    """
    if not event_name:
        return False

    # Pattern: T or F followed by 2 digits (11-99)
    para_pattern = r'\b[TF]\d{2}\b'
    return bool(re.search(para_pattern, str(event_name)))

def main():
    print("=" * 70)
    print("Azure SQL Database Diagnostic Report")
    print("=" * 70)

    mode = get_connection_mode()
    print(f"\nConnection Mode: {mode}")

    if mode != 'azure':
        print("ERROR: Not connected to Azure SQL. Check your .env file.")
        return

    print("\n" + "-" * 70)
    print("1. TOTAL ROW COUNT")
    print("-" * 70)

    total_df = query_data("SELECT COUNT(*) as total FROM athletics_data")
    total_rows = int(total_df['total'].iloc[0])
    print(f"Total rows: {total_rows:,}")

    print("\n" + "-" * 70)
    print("2. SAMPLE EVENTS (First 20 unique events)")
    print("-" * 70)

    events_df = query_data("""
        SELECT DISTINCT Event
        FROM athletics_data
        ORDER BY Event
    """)

    print(f"\nTotal unique events: {len(events_df)}")
    print("\nFirst 20 events:")
    for idx, event in enumerate(events_df['Event'].head(20), 1):
        is_para = is_para_athletics_event(event)
        marker = "⚠️ PARA" if is_para else "✓ Regular"
        print(f"  {idx:2d}. {event:40s} [{marker}]")

    print("\n" + "-" * 70)
    print("3. PARA-ATHLETICS DETECTION")
    print("-" * 70)

    # Get all events and check for para-athletics
    all_events = query_data("SELECT Event, COUNT(*) as count FROM athletics_data GROUP BY Event")
    all_events['is_para'] = all_events['Event'].apply(is_para_athletics_event)

    para_events = all_events[all_events['is_para'] == True]
    regular_events = all_events[all_events['is_para'] == False]

    para_count = para_events['count'].sum()
    regular_count = regular_events['count'].sum()

    print(f"\nRegular Athletics:")
    print(f"  Events: {len(regular_events):,}")
    print(f"  Records: {regular_count:,} ({100*regular_count/total_rows:.1f}%)")

    print(f"\nPara-Athletics:")
    print(f"  Events: {len(para_events):,}")
    print(f"  Records: {para_count:,} ({100*para_count/total_rows:.1f}%)")

    if para_count > 0:
        print(f"\n⚠️ WARNING: Database contains {para_count:,} para-athletics records!")
        print("\nSample para-athletics events:")
        for idx, row in para_events.head(10).iterrows():
            print(f"  - {row['Event']:40s} ({row['count']:,} records)")

    print("\n" + "-" * 70)
    print("4. 100M DATA CHECK")
    print("-" * 70)

    # Check for 100m data (both regular and para)
    m100_df = query_data("""
        SELECT Event, Gender, COUNT(*) as count, MIN(Start_Date) as earliest, MAX(Start_Date) as latest
        FROM athletics_data
        WHERE Event LIKE '%100%'
        GROUP BY Event, Gender
        ORDER BY Event, Gender
    """)

    print(f"\nFound {len(m100_df)} 100m event variations:")
    for idx, row in m100_df.iterrows():
        is_para = is_para_athletics_event(row['Event'])
        marker = "⚠️ PARA" if is_para else "✓"
        print(f"  {marker} {row['Event']:40s} {row['Gender']:5s} - {row['count']:,} records ({row['earliest']} to {row['latest']})")

    # Check specifically for regular Men's 100m
    regular_100m = query_data("""
        SELECT COUNT(*) as count, MIN(Start_Date) as earliest, MAX(Start_Date) as latest
        FROM athletics_data
        WHERE Event = '100 Metres' AND Gender = 'Men'
    """)

    if len(regular_100m) > 0 and regular_100m['count'].iloc[0] > 0:
        print(f"\n✓ Regular Men's 100m: {regular_100m['count'].iloc[0]:,} records")
        print(f"  Date range: {regular_100m['earliest'].iloc[0]} to {regular_100m['latest'].iloc[0]}")
    else:
        print(f"\n❌ ERROR: No regular Men's 100m data found!")

    print("\n" + "-" * 70)
    print("5. COMPETITION COVERAGE")
    print("-" * 70)

    comps_df = query_data("""
        SELECT Competition, COUNT(*) as count, MIN(Start_Date) as earliest, MAX(Start_Date) as latest
        FROM athletics_data
        GROUP BY Competition
        ORDER BY count DESC
        LIMIT 15
    """)

    print(f"\nTop 15 competitions by record count:")
    for idx, row in comps_df.iterrows():
        print(f"  {row['Competition']:50s} - {row['count']:,} records ({row['earliest']} to {row['latest']})")

    print("\n" + "=" * 70)
    print("DIAGNOSIS COMPLETE")
    print("=" * 70)

    # Summary and recommendations
    if para_count > regular_count:
        print("\n❌ CRITICAL: Database is MAJORITY para-athletics!")
        print("   Recommendation: REBUILD database with para-athletics filter")
    elif para_count > 0:
        print(f"\n⚠️  WARNING: Database contains {para_count:,} para-athletics records")
        print("   Recommendation: Clean database to remove para-athletics")
    else:
        print("\n✓ Database contains only regular athletics")

    if len(m100_df[m100_df['Event'] == '100 Metres']) == 0:
        print("\n❌ CRITICAL: Missing regular 100m data")
        print("   Recommendation: Check data source and rebuild")

if __name__ == "__main__":
    main()
