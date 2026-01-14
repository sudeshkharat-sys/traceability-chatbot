#!/usr/bin/env python3
"""
Quick diagnostic script to check data coverage in warranty vs traceability files
"""
import re
from pathlib import Path

print("="*80)
print("DATA COVERAGE DIAGNOSTIC")
print("="*80)

# Check warranty file
warranty_file = Path("thar_csv/2. THAR ROXX Warranty_Sheet1.csv")
if warranty_file.exists():
    with open(warranty_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        months = re.findall(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-20(24|25)', content)

    month_counts = {}
    for month, year in months:
        key = f"{month}-20{year}"
        month_counts[key] = month_counts.get(key, 0) + 1

    print("\n📄 WARRANTY DATA - Manufacturing Months:")
    print("-" * 80)
    for month in sorted(month_counts.keys(), key=lambda x: (x.split('-')[1], ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].index(x.split('-')[0]))):
        print(f"  {month}: {month_counts[month]:,} records")

    # Highlight missing months
    print("\n⚠️  MISSING WARRANTY DATA FOR:")
    missing = []
    for month in ['Sep', 'Oct', 'Nov', 'Dec']:
        key = f"{month}-2025"
        if month_counts.get(key, 0) < 100:  # Less than 100 records = essentially missing
            missing.append(key)
            print(f"  ❌ {key}: {month_counts.get(key, 0)} records (insufficient)")

else:
    print(f"\n❌ Warranty file not found at {warranty_file}")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
if missing:
    print("\n⚠️  You need to obtain updated WARRANTY data that includes:")
    for m in missing:
        print(f"    - {m}")
    print("\nContact your data source and request the latest warranty export")
    print("that includes vehicles manufactured through December 2025.")
else:
    print("\n✅ All months have sufficient data!")

print("\n" + "="*80)
