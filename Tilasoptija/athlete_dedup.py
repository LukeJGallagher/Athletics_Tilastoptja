"""
Athlete Name Deduplication Utility

Handles common data quality issues:
1. Same athlete ID stored as int vs float (147939 vs 147939.0)
2. Name spelling variations (Al-Jadani vs Al Jadani)
3. Different IDs for same person

Usage:
    from athlete_dedup import normalize_athlete_id, normalize_name, deduplicate_athletes
"""

import re
import pandas as pd
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


def normalize_athlete_id(athlete_id) -> str:
    """
    Normalize athlete ID to consistent string format.
    Handles: 147939, 147939.0, '147939', '147939.0' -> '147939'
    """
    if pd.isna(athlete_id):
        return ''

    # Convert to string and remove .0 suffix
    id_str = str(athlete_id).strip()
    if id_str.endswith('.0'):
        id_str = id_str[:-2]

    return id_str


def normalize_name(name: str) -> str:
    """
    Normalize athlete name for comparison.
    - Lowercase
    - Remove extra spaces
    - Normalize Arabic name prefixes (Al-, al, Al )
    - Remove special characters
    """
    if not name or pd.isna(name):
        return ''

    name = str(name).strip().lower()

    # Normalize Arabic prefixes
    # Al-Jadani, Al Jadani, al-jadani, AlJadani -> al jadani
    name = re.sub(r'\bal[\s\-]?', 'al ', name)

    # Remove hyphens and extra spaces
    name = re.sub(r'[\-]', ' ', name)
    name = re.sub(r'\s+', ' ', name)

    # Remove special characters except spaces
    name = re.sub(r'[^\w\s]', '', name)

    return name.strip()


def create_name_key(firstname: str, lastname: str) -> str:
    """Create a normalized key for matching athletes."""
    fn = normalize_name(firstname)
    ln = normalize_name(lastname)
    return f"{fn}|{ln}"


def similarity_score(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0-1)."""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()


def find_duplicate_athletes(df: pd.DataFrame,
                           firstname_col: str = 'firstname',
                           lastname_col: str = 'lastname',
                           id_col: str = 'athleteid',
                           threshold: float = 0.85) -> Dict[str, List[str]]:
    """
    Find potential duplicate athletes in dataframe.

    Returns:
        Dict mapping canonical ID to list of duplicate IDs
    """
    # Get unique athletes
    athletes = df[[id_col, firstname_col, lastname_col]].drop_duplicates()
    athletes[id_col] = athletes[id_col].apply(normalize_athlete_id)
    athletes = athletes[athletes[id_col] != '']

    # Group by normalized name
    athletes['name_key'] = athletes.apply(
        lambda r: create_name_key(r[firstname_col], r[lastname_col]), axis=1
    )

    # Find duplicates by name_key
    duplicates = {}
    name_groups = athletes.groupby('name_key')[id_col].apply(list).to_dict()

    for name_key, ids in name_groups.items():
        unique_ids = list(set(ids))
        if len(unique_ids) > 1:
            # Multiple IDs for same normalized name
            canonical = min(unique_ids, key=lambda x: int(x) if x.isdigit() else float('inf'))
            duplicates[canonical] = [i for i in unique_ids if i != canonical]

    return duplicates


def build_athlete_id_mapping(df: pd.DataFrame,
                            firstname_col: str = 'firstname',
                            lastname_col: str = 'lastname',
                            id_col: str = 'athleteid') -> Dict[str, str]:
    """
    Build mapping from variant IDs to canonical IDs.

    Returns:
        Dict mapping each athlete ID to its canonical ID
    """
    duplicates = find_duplicate_athletes(df, firstname_col, lastname_col, id_col)

    mapping = {}
    for canonical, variants in duplicates.items():
        mapping[canonical] = canonical  # Map canonical to itself
        for variant in variants:
            mapping[variant] = canonical

    return mapping


def deduplicate_athletes(df: pd.DataFrame,
                        firstname_col: str = 'firstname',
                        lastname_col: str = 'lastname',
                        id_col: str = 'athleteid',
                        inplace: bool = False) -> pd.DataFrame:
    """
    Deduplicate athletes in dataframe.

    1. Normalizes athlete IDs (removes .0 suffix)
    2. Maps variant IDs to canonical IDs
    3. Returns cleaned dataframe
    """
    if not inplace:
        df = df.copy()

    # Step 1: Normalize all athlete IDs
    df[id_col] = df[id_col].apply(normalize_athlete_id)

    # Step 2: Build and apply ID mapping
    mapping = build_athlete_id_mapping(df, firstname_col, lastname_col, id_col)

    if mapping:
        df[id_col] = df[id_col].map(lambda x: mapping.get(x, x))

    return df


def get_athlete_display_name(df: pd.DataFrame,
                            athlete_id: str,
                            firstname_col: str = 'firstname',
                            lastname_col: str = 'lastname',
                            id_col: str = 'athleteid') -> str:
    """Get canonical display name for an athlete."""
    norm_id = normalize_athlete_id(athlete_id)

    athlete = df[df[id_col].apply(normalize_athlete_id) == norm_id]

    if athlete.empty:
        return f"Unknown ({athlete_id})"

    # Get most common name variant
    names = athlete[[firstname_col, lastname_col]].value_counts()
    if len(names) > 0:
        firstname, lastname = names.index[0]
        return f"{firstname} {lastname}"

    return f"Unknown ({athlete_id})"


# Known manual mappings for edge cases
# Format: variant_id -> canonical_id
MANUAL_ID_MAPPINGS = {
    # Abdulaziz Rabie Al Jadani variants
    '652065': '147939',  # Al Jadani -> Al-Jadani

    # Add more manual mappings as discovered
    # 'variant_id': 'canonical_id',
}


def apply_manual_mappings(df: pd.DataFrame, id_col: str = 'athleteid') -> pd.DataFrame:
    """Apply known manual ID corrections."""
    df = df.copy()
    df[id_col] = df[id_col].apply(normalize_athlete_id)
    df[id_col] = df[id_col].map(lambda x: MANUAL_ID_MAPPINGS.get(x, x))
    return df


# ============================================================
# Integration with main app
# ============================================================

def clean_athlete_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main function to clean athlete data for the dashboard.
    Call this after loading data.
    """
    # Determine column names
    if 'athleteid' in df.columns:
        id_col = 'athleteid'
        fn_col = 'firstname'
        ln_col = 'lastname'
    elif 'Athlete_ID' in df.columns:
        id_col = 'Athlete_ID'
        fn_col = 'Athlete_Name'  # Combined name
        ln_col = None
    else:
        return df  # Can't clean without ID column

    # Normalize IDs
    df[id_col] = df[id_col].apply(normalize_athlete_id)

    # Apply manual mappings
    df[id_col] = df[id_col].map(lambda x: MANUAL_ID_MAPPINGS.get(x, x))

    # Auto-deduplicate if we have firstname/lastname
    if ln_col and fn_col in df.columns and ln_col in df.columns:
        df = deduplicate_athletes(df, fn_col, ln_col, id_col)

    return df


if __name__ == "__main__":
    # Test the deduplication
    import sqlite3

    conn = sqlite3.connect('SQL/athletics_deploy.db')
    df = pd.read_sql("SELECT * FROM athletics_data WHERE nationality = 'KSA'", conn)
    conn.close()

    print("Before deduplication:")
    print(f"  Unique athlete IDs: {df['athleteid'].nunique()}")

    # Find duplicates
    dupes = find_duplicate_athletes(df)
    print(f"\nFound {len(dupes)} athletes with duplicate IDs:")
    for canonical, variants in list(dupes.items())[:10]:
        print(f"  {canonical} <- {variants}")

    # Clean data
    df_clean = clean_athlete_data(df)
    print(f"\nAfter deduplication:")
    print(f"  Unique athlete IDs: {df_clean['athleteid'].nunique()}")
