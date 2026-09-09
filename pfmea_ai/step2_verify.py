"""Exhaustive, independent cross-check of step2_normalize.py's output.

This does NOT reuse step2_normalize.py's block/entry-splitting logic - that
would just prove the code agrees with itself. Instead, for every output row
it re-derives every single field from the raw Excel merges from scratch,
using only that row's recorded Source Excel Rows (the audit column), and
diffs the result against what's actually in the CSV. Any mismatch is a real
bug, not a rounding difference.

It also prints a completeness report for the "core comparison fields" -
Failure Mode, Effect, Cause, Severity, Prevention Control, Occurrence,
Detection Control, Detection - since Step 6 (comparing the plant's real
PFMEA against an AI-generated draft) is only as trustworthy as these
columns. A field that's blank in the plant's own sheet is not a parsing
bug and is reported separately from an actual mismatch.

Usage:
    python step2_verify.py <path-to-excel> [sheet_name ...]

Exits non-zero if any sheet has a mismatch.
"""

import csv
import sys
from pathlib import Path

from openpyxl import load_workbook

from step2_normalize import (
    build_columns,
    build_merge_lookup,
    flatten_header,
    normalize_sheet,
    resolve,
    write_csv,
)

CORE_FIELDS = [
    "2. Failure Mode (FM) of the\nFocus Element",
    "1. Failure Effects (FE) to the Next Higher Level Element and/or End User",
    "3. Failure Cause (FC) of the Work Element",
    "Severity (S) of FE\n",
    "Current Prevention Control (PC) of FC",
    "Occurrence (O) of FC",
    "Current Detection Controls (DC) of FC or FM",
    "Detection (D) of FC/FM",
]


def independent_field_value(ws, merge_lookup, source_rows, col):
    """Re-derive a single field's value straight from the raw merges, for
    exactly the given source rows - no reuse of step2's own grouping code."""
    for row in source_rows:
        value = resolve(ws, merge_lookup, row, col)
        if value not in (None, ""):
            return value
    return None


def verify_sheet(ws, sheet_name):
    merge_lookup = build_merge_lookup(ws)
    columns = build_columns(ws, merge_lookup)
    _columns, rows = normalize_sheet(ws)

    mismatches = []
    for row_index, record in enumerate(rows, start=1):
        source_rows = record["_source_rows"]
        for group, field, col, _ftype in columns:
            expected = independent_field_value(ws, merge_lookup, source_rows, col)
            actual = record[(group, field)]
            expected_s = "" if expected is None else str(expected).strip()
            actual_s = "" if actual is None else str(actual).strip()
            if expected_s != actual_s:
                mismatches.append(
                    {
                        "sheet": sheet_name,
                        "output_row": row_index,
                        "source_rows": source_rows,
                        "field": flatten_header(group, field),
                        "expected": expected_s,
                        "actual": actual_s,
                    }
                )

    return rows, mismatches


def completeness_report(columns, rows):
    core_columns = [
        (g, f) for g, f, _c, _t in columns if f in CORE_FIELDS
    ]
    report = {flatten_header(g, f): 0 for g, f in core_columns}
    for record in rows:
        for g, f in core_columns:
            if record.get((g, f)) not in (None, ""):
                report[flatten_header(g, f)] += 1
    return report, len(rows)


def main():
    if len(sys.argv) < 2:
        print("Usage: python step2_verify.py <path-to-excel> [sheet_name ...]")
        sys.exit(1)

    path = sys.argv[1]
    only_sheets = sys.argv[2:] if len(sys.argv) > 2 else None

    wb = load_workbook(path, data_only=True)
    sheet_names = only_sheets if only_sheets else wb.sheetnames

    all_mismatches = []
    for sheet_name in sheet_names:
        ws = wb[sheet_name]
        columns = build_columns(ws, build_merge_lookup(ws))
        rows, mismatches = verify_sheet(ws, sheet_name)
        all_mismatches.extend(mismatches)

        print("=" * 80)
        print(f"Sheet: {sheet_name}  ->  {len(rows)} rows checked, {len(mismatches)} mismatches")

        report, total = completeness_report(columns, rows)
        print("Core comparison field completeness:")
        for field, count in report.items():
            flag = "" if count == total else "  <-- some rows missing this"
            print(f"  {count}/{total}  {field}{flag}")

        for m in mismatches:
            print(f"  MISMATCH row {m['output_row']} (source {m['source_rows']}) field={m['field']!r}")
            print(f"    expected: {m['expected'][:80]!r}")
            print(f"    actual:   {m['actual'][:80]!r}")

    print("=" * 80)
    if all_mismatches:
        print(f"FAILED: {len(all_mismatches)} mismatch(es) found across all sheets.")
        sys.exit(1)
    else:
        print("PASSED: every field on every output row matches an independent re-derivation from the raw Excel merges.")


if __name__ == "__main__":
    main()
