"""Step 3: compute RPN + Risk Level from the normalized PFMEA rows.

Pure arithmetic, no AI, no API key. Takes the CSV that step2_normalize.py
writes (one row per failure entry, with Severity / Occurrence / Detection
columns already present) and adds two columns: RPN (S x O x D) and Risk
Level, using the same banding as pfmea_outputs/FMEA_Template.xlsx's
"RPN Guide" sheet from the claude/fmea-car-manufacturing-4pthaq branch:

    RPN Range   Risk Level
    1 - 80      Low
    81 - 150    Medium
    151 - 300   High
    (anything above 300, i.e. near the 10x10x10 max of 1000)  Critical

Usage:
    python step3_rpn.py <normalized-csv-from-step2>

Writes a sibling CSV with "__rpn" appended to the filename.
"""

import csv
import sys
from pathlib import Path

SEVERITY_FIELD = "Failure Analysis (Step4) :: Severity (S) of FE"
OCCURRENCE_FIELD = "Risk Analysis (Step5) :: Occurrence (O) of FC"
DETECTION_FIELD = "Risk Analysis (Step5) :: Detection (D) of FC/FM"


def risk_level(rpn):
    if rpn <= 80:
        return "Low"
    if rpn <= 150:
        return "Medium"
    if rpn <= 300:
        return "High"
    return "Critical"


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def add_rpn(rows):
    for row in rows:
        s = to_int(row.get(SEVERITY_FIELD))
        o = to_int(row.get(OCCURRENCE_FIELD))
        d = to_int(row.get(DETECTION_FIELD))

        if s is None or o is None or d is None:
            row["RPN"] = ""
            row["Risk Level"] = "Missing S/O/D"
            continue

        rpn = s * o * d
        row["RPN"] = rpn
        row["Risk Level"] = risk_level(rpn)

    return rows


def main():
    if len(sys.argv) != 2:
        print("Usage: python step3_rpn.py <normalized-csv-from-step2>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    with open(in_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if SEVERITY_FIELD not in fieldnames or OCCURRENCE_FIELD not in fieldnames or DETECTION_FIELD not in fieldnames:
        print("ERROR: this CSV does not have the expected Severity/Occurrence/Detection column names.")
        print(f"Expected: {SEVERITY_FIELD!r}, {OCCURRENCE_FIELD!r}, {DETECTION_FIELD!r}")
        print(f"Found columns: {fieldnames}")
        sys.exit(1)

    rows = add_rpn(rows)
    out_fieldnames = fieldnames + ["RPN", "Risk Level"]

    out_path = in_path.with_name(in_path.stem + "__rpn.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {out_path}")
    counts = {}
    for row in rows:
        counts[row["Risk Level"]] = counts.get(row["Risk Level"], 0) + 1
    print("Risk Level breakdown:", counts)

    for row in rows:
        mode = row.get("Failure Analysis (Step4) :: 2. Failure Mode (FM) of the Focus Element", "")
        print(f"  RPN={row['RPN']:>4}  {row['Risk Level']:<8}  {mode[:55]}")


if __name__ == "__main__":
    main()
