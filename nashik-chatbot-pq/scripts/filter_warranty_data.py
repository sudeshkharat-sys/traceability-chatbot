#!/usr/bin/env python3
"""
SCRIPT 2: WARRANTY DATA FILTERING TOOL
=======================================

This script filters warranty and warranty analysis CSV files based on
user-specified manufacturing months to keep.

Usage:
    python filter_warranty_data.py

Interactive Mode:
    - Script will ask which months to keep
    - Enter months in format: Dec-2024,Mar-2025,May-2025
    - Creates filtered CSV files with '_filtered' suffix

Command Line Mode:
    python filter_warranty_data.py --keep "Dec-2024,Mar-2025,May-2025"
"""

import pandas as pd
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# CSV file paths
CSV_DIR = Path(__file__).parent.parent.parent / "thar_csv"

WARRANTY_FILE = CSV_DIR / "2. THAR ROXX Warranty_Sheet1.csv"
WARRANTY_ANALYSIS_FILE = CSV_DIR / "3. THAR ROXX Warranty Analysis_Sheet1.csv"

# Output files (will be created)
WARRANTY_OUTPUT = CSV_DIR / "2. THAR ROXX Warranty_Sheet1_FILTERED.csv"
WARRANTY_ANALYSIS_OUTPUT = CSV_DIR / "3. THAR ROXX Warranty Analysis_Sheet1_FILTERED.csv"

# Backup directory
BACKUP_DIR = CSV_DIR / "backups"

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def create_backup(file_path):
    """Create backup of original file before filtering."""
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
    backup_path = BACKUP_DIR / backup_name

    import shutil
    shutil.copy2(file_path, backup_path)

    print(f"   ✓ Backup created: {backup_path.name}")
    return backup_path

def parse_month_input(month_str):
    """
    Parse month string to validate format.

    Expected format: 'Dec-2024' or 'Mar-2025'
    Returns: (year, month_num, original_string) or None
    """
    try:
        month_str = month_str.strip()
        if '-' in month_str:
            month_part, year_part = month_str.split('-')
            year = int(year_part)

            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month_num = month_map.get(month_part.lower()[:3])

            if month_num:
                return (year, month_num, month_str)
    except:
        pass
    return None

def get_months_to_keep_interactive():
    """Interactively ask user which months to keep."""
    print("\n" + "="*80)
    print("MONTH SELECTION")
    print("="*80)

    # Check if analysis results exist
    analysis_file = Path(__file__).parent / "monthly_analysis_results.txt"
    if analysis_file.exists():
        print("\n📋 Reading recommendations from previous analysis...\n")
        with open(analysis_file, 'r') as f:
            content = f.read()
            if "COMPLETE MONTHS (to keep):" in content:
                complete_section = content.split("COMPLETE MONTHS (to keep):")[1]
                if "INCOMPLETE MONTHS" in complete_section:
                    complete_section = complete_section.split("INCOMPLETE MONTHS")[0]

                print("✓ RECOMMENDED MONTHS TO KEEP (from analysis):")
                print(complete_section.strip())
            else:
                print("⚠️  No recommendations found. Run analyze_monthly_matching.py first.")
    else:
        print("⚠️  No analysis results found. Run analyze_monthly_matching.py first.")

    print("\n" + "="*80)
    print("Enter the months you want to KEEP in the filtered data.")
    print("Format: Dec-2024,Mar-2025,May-2025,Jul-2025")
    print("(comma-separated, no spaces)")
    print("="*80)

    while True:
        months_input = input("\nMonths to keep: ").strip()

        if not months_input:
            print("✗ Error: Please enter at least one month")
            continue

        # Parse months
        month_list = [m.strip() for m in months_input.split(',')]
        parsed_months = []
        invalid_months = []

        for month_str in month_list:
            parsed = parse_month_input(month_str)
            if parsed:
                parsed_months.append(parsed)
            else:
                invalid_months.append(month_str)

        if invalid_months:
            print(f"\n✗ Error: Invalid month format: {', '.join(invalid_months)}")
            print("   Use format: Dec-2024, Mar-2025, etc.")
            continue

        if not parsed_months:
            print("✗ Error: No valid months entered")
            continue

        # Confirm with user
        print(f"\n✓ You selected {len(parsed_months)} month(s) to KEEP:")
        for _, _, month_str in sorted(parsed_months):
            print(f"   • {month_str}")

        confirm = input("\nProceed with filtering? (yes/no): ").strip().lower()
        if confirm in ['yes', 'y']:
            return [m[2] for m in parsed_months]  # Return original month strings
        else:
            print("\nLet's try again...")

def filter_warranty_data(warranty_df, months_to_keep):
    """Filter warranty dataframe to keep only specified months."""
    print("\n" + "="*80)
    print("FILTERING WARRANTY DATA")
    print("="*80)

    original_count = len(warranty_df)

    # Create filter mask
    mask = warranty_df['Manufac_Yr_Mon'].isin(months_to_keep)
    filtered_df = warranty_df[mask].copy()

    filtered_count = len(filtered_df)
    removed_count = original_count - filtered_count

    print(f"\n✓ Original records: {original_count:,}")
    print(f"✓ Filtered records: {filtered_count:,} ({filtered_count/original_count*100:.1f}%)")
    print(f"✗ Removed records: {removed_count:,} ({removed_count/original_count*100:.1f}%)")

    return filtered_df

def filter_warranty_analysis(warranty_analysis_df, kept_vins):
    """Filter warranty analysis to keep only VINs that exist in filtered warranty data."""
    print("\n" + "="*80)
    print("FILTERING WARRANTY ANALYSIS DATA")
    print("="*80)

    original_count = len(warranty_analysis_df)

    # Filter by Serial Number (VIN)
    mask = warranty_analysis_df['Serial Number'].isin(kept_vins)
    filtered_df = warranty_analysis_df[mask].copy()

    filtered_count = len(filtered_df)
    removed_count = original_count - filtered_count

    print(f"\n✓ Original records: {original_count:,}")
    print(f"✓ Filtered records: {filtered_count:,} ({filtered_count/original_count*100:.1f}%)")
    print(f"✗ Removed records: {removed_count:,} ({removed_count/original_count*100:.1f}%)")

    return filtered_df

def save_filtered_data(df, output_path, description):
    """Save filtered dataframe to CSV."""
    try:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ Saved: {output_path.name} ({len(df):,} records)")
        return True
    except Exception as e:
        print(f"✗ Error saving {description}: {e}")
        return False

def print_summary(months_kept, warranty_filtered_df, warranty_analysis_filtered_df):
    """Print final summary."""
    print("\n" + "="*80)
    print("FILTERING COMPLETE!")
    print("="*80)

    print(f"\n✓ Kept {len(months_kept)} month(s):")
    for month in sorted(months_kept):
        print(f"   • {month}")

    print(f"\n✓ Filtered Files Created:")
    print(f"   • {WARRANTY_OUTPUT.name} ({len(warranty_filtered_df):,} records)")
    print(f"   • {WARRANTY_ANALYSIS_OUTPUT.name} ({len(warranty_analysis_filtered_df):,} records)")

    print(f"\n✓ Backups saved in: {BACKUP_DIR}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Review the filtered CSV files")
    print("2. If satisfied, replace original files with filtered versions:")
    print(f"   mv '{WARRANTY_OUTPUT}' '{WARRANTY_FILE}'")
    print(f"   mv '{WARRANTY_ANALYSIS_OUTPUT}' '{WARRANTY_ANALYSIS_FILE}'")
    print("\n3. Run data_loading.py to reload data into Neo4j")
    print("\n4. Test your traceability chatbot!")
    print("\n⚠️  Note: PPCM and ESQA files are NOT filtered (keep all data)")
    print("="*80 + "\n")

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main execution function."""
    print("\n" + "="*80)
    print("WARRANTY DATA FILTERING TOOL")
    print("="*80)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Filter warranty data by manufacturing month')
    parser.add_argument('--keep', type=str, help='Comma-separated months to keep (e.g., Dec-2024,Mar-2025)')
    args = parser.parse_args()

    # Get months to keep
    if args.keep:
        month_list = [m.strip() for m in args.keep.split(',')]
        parsed_months = []
        for month_str in month_list:
            parsed = parse_month_input(month_str)
            if parsed:
                parsed_months.append(parsed[2])
            else:
                print(f"✗ Error: Invalid month format '{month_str}'")
                sys.exit(1)
        months_to_keep = parsed_months
        print(f"\n✓ Keeping {len(months_to_keep)} month(s): {', '.join(months_to_keep)}")
    else:
        months_to_keep = get_months_to_keep_interactive()

    # Check if files exist
    if not WARRANTY_FILE.exists():
        print(f"\n✗ Error: Warranty file not found at {WARRANTY_FILE}")
        sys.exit(1)

    if not WARRANTY_ANALYSIS_FILE.exists():
        print(f"\n✗ Error: Warranty Analysis file not found at {WARRANTY_ANALYSIS_FILE}")
        sys.exit(1)

    # Create backups
    print("\n" + "="*80)
    print("CREATING BACKUPS")
    print("="*80)
    print("\n✓ Creating backups of original files...")

    create_backup(WARRANTY_FILE)
    create_backup(WARRANTY_ANALYSIS_FILE)

    # Load data
    print("\n" + "="*80)
    print("LOADING DATA")
    print("="*80)

    try:
        print("\n✓ Loading warranty data...")
        warranty_df = pd.read_csv(WARRANTY_FILE, encoding='utf-8-sig', low_memory=False)
        print(f"   Loaded {len(warranty_df):,} records")

        print("\n✓ Loading warranty analysis data...")
        warranty_analysis_df = pd.read_csv(WARRANTY_ANALYSIS_FILE, encoding='utf-8-sig', low_memory=False)
        print(f"   Loaded {len(warranty_analysis_df):,} records")
    except Exception as e:
        print(f"\n✗ Error loading files: {e}")
        sys.exit(1)

    # Filter warranty data
    warranty_filtered = filter_warranty_data(warranty_df, months_to_keep)

    # Get VINs from filtered warranty data
    kept_vins = set(warranty_filtered['Serial No'].dropna().astype(str))

    # Filter warranty analysis
    warranty_analysis_filtered = filter_warranty_analysis(warranty_analysis_df, kept_vins)

    # Save filtered data
    print("\n" + "="*80)
    print("SAVING FILTERED DATA")
    print("="*80)
    print()

    success = True
    success &= save_filtered_data(warranty_filtered, WARRANTY_OUTPUT, "Warranty")
    success &= save_filtered_data(warranty_analysis_filtered, WARRANTY_ANALYSIS_OUTPUT, "Warranty Analysis")

    if not success:
        print("\n✗ Error: Some files could not be saved")
        sys.exit(1)

    # Print summary
    print_summary(months_to_keep, warranty_filtered, warranty_analysis_filtered)

if __name__ == "__main__":
    main()
