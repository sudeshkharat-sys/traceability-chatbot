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
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl" if file_path.suffix != ".xls" else "xlrd")
    except Exception as e:
        print(f"Failed to read {file_path.name}: {e}")
        return

    for sheet_name in xls.sheet_names:
        safe_name = sanitize_filename(f"{file_path.stem}_{sheet_name}.csv")
        out_path = OUTPUT_DIR / safe_name

        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = df.fillna("")  # Clean NaNs
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"Saved: {out_path.name} ({len(df)} rows, {len(df.columns)} cols)")
        except Exception as e:
            print(f"Could not convert sheet '{sheet_name}' in {file_path.name}: {e}")

def main():
    excel_files = [p for p in Path(INPUT_DIR).iterdir() if p.suffix.lower() in EXCEL_EXTS]
    if not excel_files:
        print(f"No Excel files found in: {INPUT_DIR}")
        return

    for file_path in excel_files:
        convert_excel_to_csv(file_path)

    print(f"\nConversion complete! All CSVs are in: {OUTPUT_DIR.resolve()}")

if __name__ == "__main__":
    main()