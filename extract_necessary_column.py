#!/usr/bin/env python3
"""
extract_bev_columns_named.py

Extracts specific Excel columns (by letter position) for BEV dataset files,
and saves clean outputs with names like "1. BEV PPCM.xlsx", "2. BEV Warranty.xlsx", etc.
"""

import os
import glob
from pathlib import Path
import pandas as pd

# ---------- Helper functions ----------
def col_letter_to_index(letter: str) -> int:
    """Convert Excel column letter (A, B, AA, etc.) to 0-based index."""
    letter = letter.strip().upper()
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1

def expand_letter_range(start: str, end: str):
    """Expand Excel range, e.g. V to AH."""
    def idx_to_letter(i):
        s = ""
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    start_i = col_letter_to_index(start) + 1
    end_i = col_letter_to_index(end) + 1
    return [idx_to_letter(i) for i in range(start_i, end_i + 1)]

def select_columns_by_letters(df, letters):
    """Select columns from DataFrame using Excel column letters."""
    selected = []
    for l in letters:
        try:
            i = col_letter_to_index(l)
            if i < len(df.columns):
                selected.append(df.columns[i])
        except Exception:
            continue
    if not selected:
        return df
    return df[selected].copy()

def find_file(patterns, search_dirs):
    for d in search_dirs:
        for p in patterns:
            files = glob.glob(str(d / p))
            if files:
                return Path(files[0])
    return None

# ---------- Config: Dataset definitions ----------
DATASETS = [
    {
        "no": "1",
        "name": "THAR ROXX PPCM",
        "patterns": ["*PPCM*.xls*", "*BEV PPCM*.xls*"],
        "columns": ["A","B","C","D","G","H","L","Q","R"]
    },
    {
        "no": "2",
        "name": "THAR ROXX Warranty",
        "patterns": ["*Warranty*.xls*", "*BEV Warranty*.xls*"],
        "columns": None  # All columns
    },
    {
        "no": "3",
        "name": "THAR ROXX Warranty Analysis",
        "patterns": ["*Warranty analysis*.xls*", "*Warranty Analysis*.xls*"],
        "columns": ["H","E","F","L","D"]
    },
    {
        "no": "4",
        "name": "THAR ROXX e-SQA",
        "patterns": ["*e-SQA*.xls*", "*SQA*.xls*", "*SQA rejection*.xls*"],
        "columns": ["B","E","H","I","J","O","R","U"] + expand_letter_range("V","AH")
    },
    {
    "no": "6",
    "name": "Traceability Report - Dec24 to Feb25",
    "patterns": ["*Dec24*Feb25*.xls*"],
    "columns": ["J","M","I","S"] 
    },
    {
        "no": "7",
        "name": "Traceability Report - Jul25 to Aug25",
        "patterns": ["*Jul25*Aug25*.xls*"],
        "columns": ["J","M","I","S"]  
    },
    {
        "no": "8",
        "name": "Traceability Report - Mar25 to Apr25",
        "patterns": ["*Mar25*Apr25*.xls*"],
        "columns": ["J","M","I","S"]  
    },
    {
        "no": "9",
        "name": "Traceability Report - May25 to Jun25",
        "patterns": ["*May25*Jun25*.xls*"],
        "columns": ["J","M","I","S"]  
    },
    {
        "no": "10",
        "name": "Traceability Report - Sep25 to Oct25",
        "patterns": ["*Sep25*Oct25*.xls*"],
        "columns": ["J","M","I","S"]  
    },
]

SEARCH_DIRS = [Path.cwd(), Path("data")]
print(f"[INFO] Searching in directories: {[str(d) for d in SEARCH_DIRS]}")
OUTPUT_DIR = Path("thar_data_sorted")
print(f"[INFO] Output directory: {OUTPUT_DIR}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Main ----------
for ds in DATASETS:
    ds_no = ds["no"]
    ds_name = ds["name"]
    print(f"\n[INFO] Processing {ds_no}. {ds_name}")

    file_path = find_file(ds["patterns"], SEARCH_DIRS)
    if not file_path:
        print(f"  [WARN] File not found for {ds_name}")
        continue

    try:
        df = pd.read_excel(file_path, header=0, engine="openpyxl")
    except Exception as e:
        print(f"  [ERROR] Could not read {file_path}: {e}")
        continue

    cols = ds["columns"]
    if cols is None:
        df_out = df.copy()  # all columns
        note = "ALL columns"
    elif len(cols) == 0:
        df_out = df.iloc[:, :min(30, df.shape[1])].copy()
        note = "First 30 columns (fallback)"
    else:
        df_out = select_columns_by_letters(df, cols)
        note = f"Columns {','.join(cols)}"

    out_path = OUTPUT_DIR / f"{ds_no}. {ds_name}.xlsx"
    try:
        df_out.to_excel(out_path, index=False)
        print(f"  [OK] Saved -> {out_path}  ({df_out.shape[1]} cols)  [{note}]")
    except Exception as e:
        print(f"  [ERROR] Saving failed: {e}")

print("\n[INFO] Extraction completed. Check the 'output/' folder.")