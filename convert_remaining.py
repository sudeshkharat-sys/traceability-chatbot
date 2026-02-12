import pandas as pd
from pathlib import Path
import re

INPUT_DIR = Path(r"C:\Users\50014665\GraphRag\Traceability\excel")
OUTPUT_DIR = Path(r"C:\Users\50014665\GraphRag\Traceability\csv_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Only these two files
files_to_convert = [
    "6. Traceability Report - Sep25 to Oct25.xlsx",
    "7.Thar_Roxx_NOV_and_Desc.xlsx"
]

def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9_.\-\s]+', '_', name).strip()

def convert_file(filename):
    file_path = INPUT_DIR / filename
    if not file_path.exists():
        print(f"File not found: {filename}")
        return

    print(f"\nProcessing: {filename}")
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        
        for sheet_name in xls.sheet_names:
            print(f"  Converting sheet: '{sheet_name}'...")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if df.empty:
                continue
                
            safe_name = sanitize_filename(f"{file_path.stem}_{sheet_name}.csv")
            out_path = OUTPUT_DIR / safe_name
            
            df = df.fillna("")
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"    ✅ Saved: {out_path.name} ({len(df)} rows)")
    except Exception as e:
        print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    for f in files_to_convert:
        convert_file(f)
    print("\nDone!")