"""
Temporary script: PDF to Excel conversion
Preserves column values exactly as they appear in the PDF tables.
Usage: python3 pdf_to_excel.py input.pdf [output.xlsx]
"""

import sys
import pdfplumber
import pandas as pd
from pathlib import Path


def pdf_to_excel(pdf_path: str, output_path: str = None):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    if output_path is None:
        output_path = pdf_path.with_suffix(".xlsx")
    else:
        output_path = Path(output_path)

    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Processing {len(pdf.pages)} page(s)...")

        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                }
            )

            if not tables:
                # Fallback: try text-based extraction
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                )

            for t_idx, table in enumerate(tables):
                if not table:
                    continue
                # Keep values exactly as extracted (no casting)
                df = pd.DataFrame(table)
                # Use first row as header if it looks like a header row
                if df.iloc[0].notna().all() and df.iloc[0].str.strip().str.len().gt(0).all():
                    df.columns = df.iloc[0]
                    df = df[1:].reset_index(drop=True)
                all_tables.append((f"Page{page_num}_Table{t_idx+1}", df))
                print(f"  Page {page_num}, Table {t_idx+1}: {df.shape[0]} rows x {df.shape[1]} cols")

    if not all_tables:
        print("No tables found. Trying plain text extraction...")
        all_tables = _extract_as_text(pdf_path)

    if not all_tables:
        print("No extractable tables found in the PDF.")
        sys.exit(1)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in all_tables:
            # Truncate sheet name to Excel's 31-char limit
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
            # Auto-fit column widths
            ws = writer.sheets[safe_name]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) if cell.value is not None else 0)
                    for cell in col
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

    print(f"\nDone. Output saved to: {output_path}")
    print(f"Sheets created: {[name for name, _ in all_tables]}")


def _extract_as_text(pdf_path: Path):
    """Fallback: extract all text lines into a single sheet."""
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.splitlines():
                    if line.strip():
                        rows.append([line.strip()])
    if rows:
        df = pd.DataFrame(rows, columns=["Content"])
        return [("Sheet1", df)]
    return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pdf_to_excel.py input.pdf [output.xlsx]")
        sys.exit(1)

    pdf_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else None
    pdf_to_excel(pdf_file, out_file)
