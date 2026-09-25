"""Step 3b: decode the plant's own recorded S/O/D numbers into what they mean.

This answers "when I see Severity=5, what was that actually meant to
represent?" - pure lookup against the AIAG-VDA scoring reference tables
(AIAG_VDA_Scoring_Reference.xlsx, copied from the reference
FMEA_Template.xlsx on the claude/fmea-car-manufacturing-4pthaq branch), no
AI involved. This is about the plant's EXISTING numbers, not a suggestion -
that comes later in Step 6, once we have the AIAG-VDA handbook PDF for RAG
and can generate an independent AI draft to compare against.

Usage:
    python step3b_explain_scores.py <rpn-csv-from-step3> [reference-xlsx]

Writes a sibling CSV with "__explained" appended to the filename, adding
one "<Score> Meaning" column per S/O/D field.
"""

import csv
import sys
from pathlib import Path

from openpyxl import load_workbook

SEVERITY_FIELD = "Failure Analysis (Step4) :: Severity (S) of FE"
OCCURRENCE_FIELD = "Risk Analysis (Step5) :: Occurrence (O) of FC"
DETECTION_FIELD = "Risk Analysis (Step5) :: Detection (D) of FC/FM"

REFERENCE_SHEETS = {
    SEVERITY_FIELD: "Severity Table",
    OCCURRENCE_FIELD: "Occurrence Table",
    DETECTION_FIELD: "Detection Table",
}


def load_reference_lookup(reference_path):
    """score (1-10) -> "<Meaning> - <extra column>" per table."""
    wb = load_workbook(reference_path, data_only=True)
    lookup = {}
    for field, sheet_name in REFERENCE_SHEETS.items():
        ws = wb[sheet_name]
        rows = ws.iter_rows(min_row=2, values_only=True)
        table = {}
        for score, meaning, extra in rows:
            if not isinstance(score, (int, float)):
                continue
            table[int(score)] = f"{meaning.strip()} ({extra.strip()})" if extra else meaning.strip()
        lookup[field] = table
    return lookup


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python step3b_explain_scores.py <rpn-csv-from-step3> [reference-xlsx]")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    reference_path = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).with_name("AIAG_VDA_Scoring_Reference.xlsx")
    )

    lookup = load_reference_lookup(reference_path)

    with open(in_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = list(reader)

    field_columns = {}
    for field in REFERENCE_SHEETS:
        if field not in header:
            print(f"ERROR: expected column {field!r} not found in {in_path}")
            sys.exit(1)
        field_columns[field] = header.index(field)

    legend_row_index = header.index("Source Excel Rows")

    out_header = header + [f"{f.split('::')[-1].strip()} Meaning" for f in REFERENCE_SHEETS]
    out_rows = []
    for row in rows:
        new_row = list(row)
        is_legend_row = row[legend_row_index] == "audit"
        for field, col_index in field_columns.items():
            if is_legend_row:
                new_row.append("meaning_lookup")
                continue
            score = to_int(row[col_index])
            table = lookup[field]
            new_row.append(table.get(score, "Unknown / not in 1-10 range") if score is not None else "Missing score")
        out_rows.append(new_row)

    out_path = in_path.with_name(in_path.stem + "__explained.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(out_header)
        writer.writerows(out_rows)

    print(f"Wrote {out_path}")
    mode_col = header.index("Failure Analysis (Step4) :: 2. Failure Mode (FM) of the Focus Element")
    for row in out_rows:
        if row[legend_row_index] == "audit":
            continue
        mode = row[mode_col][:40].replace("\n", " ")
        sev_meaning = row[-3]
        print(f"  {mode:<42} Severity meaning: {sev_meaning[:70]}")


if __name__ == "__main__":
    main()
