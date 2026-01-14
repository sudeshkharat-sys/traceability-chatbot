#!/usr/bin/env python3
"""
SCRIPT 1: MONTHLY MATCHING RATE ANALYSIS
=========================================

This script analyzes all CSV files and provides month-wise matching rates
between Warranty data and Traceability data.

Usage:
    python analyze_monthly_matching.py

Output:
    - Detailed month-by-month analysis
    - Matching rates for each manufacturing month
    - Recommendations on which months to keep/remove
"""

import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# CSV file paths (relative to script location)
CSV_DIR = Path(__file__).parent.parent.parent / "csv_output"

WARRANTY_FILE = CSV_DIR / "2. THAR ROXX Warranty_Sheet1_backup_20260112_140107.csv"
WARRANTY_ANALYSIS_FILE = CSV_DIR / "3. THAR ROXX Warranty Analysis_Sheet1_backup_20260112_140107.csv"
PPCM_FILE = CSV_DIR / "1. THAR ROXX PPCM_Sheet1.csv"
ESQA_FILE = CSV_DIR / "4. THAR ROXX e-SQA_Sheet1.csv"

TRACEABILITY_FILES = [
    CSV_DIR / "6. Traceability Report - Dec24 to Feb25_Dec 2024.csv",
    CSV_DIR / "6. Traceability Report - Dec24 to Feb25_Jan 2025.csv",
    CSV_DIR / "6. Traceability Report - Dec24 to Feb25_Feb 2025.csv",
    CSV_DIR / "6. Traceability Report - Mar25 to Apr25_Mar 2025.csv",
    CSV_DIR / "6. Traceability Report - Mar25 to Apr25_Apr 2025.csv",
    CSV_DIR / "6. Traceability Report - May25 to Jun25_May 2025.csv",
    CSV_DIR / "6. Traceability Report - May25 to Jun25_june 2025.csv",
    CSV_DIR / "6. Traceability Report - Jul25 to Aug25_July 2025.csv",
    CSV_DIR / "6. Traceability Report - Jul25 to Aug25_Aug 2025.csv",
    CSV_DIR / "6. Traceability Report - Sep25 to Oct25_Sept 2025.csv",
    CSV_DIR / "6. Traceability Report - Sep25 to Oct25_Oct 2025.csv",
    CSV_DIR / "7.Thar_Roxx_NOV_and_Desc_Nov_2025_page1.csv",
    CSV_DIR / "7.Thar_Roxx_NOV_and_Desc_Nov_2025_page2.csv",
    CSV_DIR / "7.Thar_Roxx_NOV_and_Desc_Dec_2025.csv",
]


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def parse_mfg_date(date_str):
    """
    Parse manufacturing date from format 'MMM-YYYY' to (year, month_num, month_str).

    Example: 'Dec-2024' -> (2024, 12, 'Dec-2024')
    """
    try:
        date_str = str(date_str).strip()
        if '-' in date_str:
            month_str, year_str = date_str.split('-')
            year = int(year_str)

            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month_num = month_map.get(month_str.lower()[:3], 0)

            return (year, month_num, date_str)
    except Exception as e:
        pass
    return None

def load_traceability_vins():
    """Load all VINs from traceability files."""
    print("\n" + "="*80)
    print("LOADING TRACEABILITY DATA")
    print("="*80)

    all_vins = set()

    for trace_file in TRACEABILITY_FILES:
        if not trace_file.exists():
            print(f"⚠️  Warning: {trace_file.name} not found")
            continue

        try:
            df = pd.read_csv(trace_file, encoding='utf-8-sig', low_memory=False)

            # Extract last 8 characters from VIN
            if 'VINNumber' in df.columns:
                vins = df['VINNumber'].dropna().astype(str)
                vins_short = vins.str[-8:]
                all_vins.update(vins_short.unique())

                print(f"✓ {trace_file.name}: {len(vins_short):,} VINs")
        except Exception as e:
            print(f"✗ Error loading {trace_file.name}: {e}")

    print(f"\nTotal unique traceability VINs: {len(all_vins):,}")
    return all_vins

def analyze_warranty_by_month(warranty_df, traceability_vins):
    """Analyze warranty data month by month."""
    print("\n" + "="*80)
    print("ANALYZING WARRANTY DATA BY MANUFACTURING MONTH")
    print("="*80)

    months_data = {}

    # Group by manufacturing month
    for idx, row in warranty_df.iterrows():
        mfg_date = row.get('Manufac_Yr_Mon', '')
        vin = str(row.get('Serial No', '')).strip()

        parsed = parse_mfg_date(mfg_date)
        if parsed and vin:
            year, month_num, month_str = parsed

            if month_str not in months_data:
                months_data[month_str] = {
                    'year': year,
                    'month': month_num,
                    'total_records': 0,
                    'vins': [],
                    'matched_vins': set(),
                    'unmatched_vins': set()
                }

            months_data[month_str]['total_records'] += 1
            months_data[month_str]['vins'].append(vin)

    # Calculate matches
    for month_str in months_data:
        vins = set(months_data[month_str]['vins'])
        matched = vins.intersection(traceability_vins)
        unmatched = vins - traceability_vins

        months_data[month_str]['matched_vins'] = matched
        months_data[month_str]['unmatched_vins'] = unmatched
        months_data[month_str]['unique_vins'] = len(vins)
        months_data[month_str]['matched_count'] = len(matched)
        months_data[month_str]['unmatched_count'] = len(unmatched)
        months_data[month_str]['match_rate'] = (len(matched) / len(vins) * 100) if vins else 0

    return months_data

def print_analysis_report(months_data):
    """Print detailed analysis report."""
    print("\n" + "="*80)
    print("MONTH-BY-MONTH MATCHING ANALYSIS")
    print("="*80)

    # Table header
    print(f"\n{'Month':<15} {'Records':<10} {'Unique VINs':<12} {'Matched':<10} "
          f"{'Unmatched':<12} {'Match %':<10} {'Status':<15}")
    print("-" * 95)

    # Sort by year-month
    sorted_months = sorted(months_data.items(),
                          key=lambda x: (x[1]['year'], x[1]['month']))

    complete_months = []
    incomplete_months = []

    for month_str, data in sorted_months:
        status = "✓ COMPLETE" if data['match_rate'] >= 95 else "✗ INCOMPLETE"
        status_symbol = "✓" if data['match_rate'] >= 95 else "✗"

        print(f"{month_str:<15} {data['total_records']:<10} {data['unique_vins']:<12} "
              f"{data['matched_count']:<10} {data['unmatched_count']:<12} "
              f"{data['match_rate']:>8.1f}% {status:<15}")

        if data['match_rate'] >= 95:
            complete_months.append((month_str, data))
        else:
            incomplete_months.append((month_str, data))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_records = sum(d['total_records'] for d in months_data.values())
    total_vins = sum(d['unique_vins'] for d in months_data.values())

    complete_records = sum(d['total_records'] for _, d in complete_months)
    complete_vins = sum(d['unique_vins'] for _, d in complete_months)

    incomplete_records = sum(d['total_records'] for _, d in incomplete_months)
    incomplete_vins = sum(d['unique_vins'] for _, d in incomplete_months)

    print(f"\nORIGINAL WARRANTY DATA:")
    print(f"   Total records: {total_records:,}")
    print(f"   Total unique VINs: {total_vins:,}")
    print(f"   Months covered: {len(months_data)}")

    print(f"\n✓ COMPLETE MONTHS (≥95% match): {len(complete_months)}")
    for month_str, data in complete_months:
        print(f"   {month_str:<15} {data['total_records']:>5} records, "
              f"{data['unique_vins']:>5} VINs, {data['match_rate']:>5.1f}% match")
    print(f"   Subtotal: {complete_records:,} records ({complete_records/total_records*100:.1f}%)")

    print(f"\n✗ INCOMPLETE MONTHS (<95% match): {len(incomplete_months)}")
    for month_str, data in incomplete_months:
        print(f"   {month_str:<15} {data['total_records']:>5} records, "
              f"{data['unique_vins']:>5} VINs, {data['match_rate']:>5.1f}% match")
    print(f"   Subtotal: {incomplete_records:,} records ({incomplete_records/total_records*100:.1f}%)")

    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if len(complete_months) >= len(incomplete_months):
        print(f"\n✓ GOOD NEWS: {len(complete_months)} out of {len(months_data)} months have complete traceability")
        print(f"\nTo achieve 100% matching, you can:")
        print(f"   Option 1: Keep only complete months ({complete_records:,} records, {complete_records/total_records*100:.1f}%)")
        print(f"   Option 2: Request missing traceability data for {len(incomplete_months)} months")
    else:
        print(f"\n⚠️  WARNING: Only {len(complete_months)} out of {len(months_data)} months have complete traceability")
        print(f"\nTo improve matching:")
        print(f"   Option 1: Keep only complete months ({complete_records:,} records, {complete_records/total_records*100:.1f}%)")
        print(f"           ⚠️  This removes {incomplete_records:,} records ({incomplete_records/total_records*100:.1f}%)")
        print(f"   Option 2: Request missing traceability data for these months:")
        for month_str, data in incomplete_months:
            print(f"           - {month_str}")

    # Save recommendations to file
    print(f"\n" + "="*80)
    print("SAVING RECOMMENDATIONS")
    print("="*80)

    output_file = Path(__file__).parent / "monthly_analysis_results.txt"
    with open(output_file, 'w') as f:
        f.write("MONTHLY MATCHING ANALYSIS RESULTS\n")
        f.write("="*80 + "\n\n")
        f.write("COMPLETE MONTHS (to keep):\n")
        for month_str, data in complete_months:
            f.write(f"{month_str}\n")

        f.write("\nINCOMPLETE MONTHS (to remove or request data):\n")
        for month_str, data in incomplete_months:
            f.write(f"{month_str}\n")

    print(f"✓ Results saved to: {output_file}")

    return complete_months, incomplete_months

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main execution function."""
    print("\n" + "="*80)
    print("TRACEABILITY MONTHLY MATCHING ANALYSIS")
    print("="*80)
    print("\nThis script analyzes warranty data and traceability matching rates")
    print("by manufacturing month.\n")

    # Check if files exist
    if not WARRANTY_FILE.exists():
        print(f"✗ Error: Warranty file not found at {WARRANTY_FILE}")
        sys.exit(1)

    # Load traceability VINs
    traceability_vins = load_traceability_vins()

    if not traceability_vins:
        print("\n✗ Error: No traceability VINs found. Check file paths.")
        sys.exit(1)

    # Load warranty data
    print("\n" + "="*80)
    print("LOADING WARRANTY DATA")
    print("="*80)

    try:
        warranty_df = pd.read_csv(WARRANTY_FILE, encoding='utf-8-sig', low_memory=False)
        print(f"✓ Loaded {len(warranty_df):,} warranty records")
    except Exception as e:
        print(f"✗ Error loading warranty file: {e}")
        sys.exit(1)

    # Analyze by month
    months_data = analyze_warranty_by_month(warranty_df, traceability_vins)

    # Print report
    complete_months, incomplete_months = print_analysis_report(months_data)

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nNext Steps:")
    print("   1. Review the analysis above")
    print("   2. Decide which months to keep/remove")
    print("   3. Run 'filter_warranty_data.py' to filter the data")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
