#!/usr/bin/env python3
"""
excel_to_csv.py
---------------
Safely convert Excel files (.xls, .xlsx, .xlsm) to CSV format (Windows-compatible).

Each sheet in a workbook will be saved as a separate CSV file in `<INPUT_DIR>\csv_output`.
File names are sanitized to avoid illegal characters.

Dependencies:
    pip install pandas openpyxl xlrd

Usage:
    python excel_to_csv.py
"""

import os
import pandas as pd
from pathlib import Path
import re

# 🔹 CHANGE THIS to your Excel folder path
INPUT_DIR = Path(r"C:\Users\50014665\GraphRag\thar_remain")   # Windows path (raw string)
OUTPUT_DIR = Path(r"C:\Users\50014665\GraphRag\thar_csv_new")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_EXTS = {".xls", ".xlsx", ".xlsm"}

def sanitize_filename(name: str) -> str:
    """Make a safe filename for saving CSVs."""
    return re.sub(r'[^A-Za-z0-9_.\-\s]+', '_', name).strip()

def convert_excel_to_csv(file_path: Path):
    """Convert all sheets in an Excel file to CSV files."""
    print(f"\nProcessing: {file_path.name}")

    # Determine the correct engine based on file extension
    try:
        if file_path.suffix.lower() == ".xls":
            engine = "xlrd"
        else:
            engine = "openpyxl"

        xls = pd.ExcelFile(file_path, engine=engine)
        sheet_count = len(xls.sheet_names)
        print(f"Found {sheet_count} sheet(s): {', '.join(xls.sheet_names)}")

    except Exception as e:
        print(f"❌ Failed to read {file_path.name}: {e}")
        return

    success_count = 0
    fail_count = 0

    for idx, sheet_name in enumerate(xls.sheet_names, 1):
        print(f"  [{idx}/{sheet_count}] Converting sheet: '{sheet_name}'...")
        safe_name = sanitize_filename(f"{file_path.stem}_{sheet_name}.csv")
        out_path = OUTPUT_DIR / safe_name

        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)

            # Check if sheet is empty
            if df.empty or df.shape[0] == 0:
                print(f"    ⚠️  Warning: Sheet '{sheet_name}' is empty, skipping...")
                continue

            df = df.fillna("")  # Clean NaNs
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"    ✅ Saved: {out_path.name} ({len(df)} rows, {len(df.columns)} cols)")
            success_count += 1

        except Exception as e:
            print(f"    ❌ Could not convert sheet '{sheet_name}': {e}")
            fail_count += 1

    print(f"Summary: {success_count} sheets converted, {fail_count} failed")

def main():
    print("=" * 60)
    print("Excel to CSV Converter (Multi-Sheet Support)")
    print("=" * 60)
    print(f"Input Directory:  {INPUT_DIR.resolve()}")
    print(f"Output Directory: {OUTPUT_DIR.resolve()}")
    print("=" * 60)

    excel_files = [p for p in Path(INPUT_DIR).iterdir() if p.suffix.lower() in EXCEL_EXTS]
    if not excel_files:
        print(f"❌ No Excel files found in: {INPUT_DIR}")
        return

    print(f"\nFound {len(excel_files)} Excel file(s) to process:\n")
    for idx, file_path in enumerate(excel_files, 1):
        print(f"{idx}. {file_path.name}")

    print("\n" + "=" * 60)

    for file_path in excel_files:
        convert_excel_to_csv(file_path)

    print("\n" + "=" * 60)
    print(f"✅ Conversion complete! All CSVs are in: {OUTPUT_DIR.resolve()}")
    print("=" * 60)

if __name__ == "__main__":
    main()