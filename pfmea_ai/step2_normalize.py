"""Step 2: normalize a real plant PFMEA sheet into one clean row per failure entry.

The plant workbook uses the standard AIAG-VDA 6-step PFMEA form, confirmed by
hand against NEW_PFMEA.xlsx:

    Row 13      - top-level group header, merged across a block of columns
                  (Structure Analysis (Step2), Function Analysis (Step3),
                  Failure Analysis (Step4), Risk Analysis (Step5),
                  Optimization (Step6))
    Row 14      - blank filler row, part of the row-13 merge, carries no data
    Row 15-17   - field-level sub-header, merged across 1-2 columns each
                  (e.g. "1. Process Item...", "Severity (S) of FE", ...)
    Row 18+     - data. Cells are heavily merged both across and within a
                  block: e.g. Process Item/Step/Work Element are merged for
                  the whole block, while Failure Cause is merged one row at
                  a time - so different fields in the same block can have
                  different row granularity.

This script:
  1. Builds the true two-level header (group + field) per column, using the
     first column of each header merge as that field's representative
     column (skips merge-continuation columns).
  2. Forward-fills every merged data cell with its merge's top-left value,
     so every row carries full context regardless of which field merges
     span how many rows.
  3. Drops rows that have neither a Failure Mode nor a Failure Cause value
     (pure separator rows) - everything else is kept as one output row.

Usage:
    python step2_normalize.py <path-to-excel> [sheet_name]

Prints the normalized rows and writes one CSV per processed sheet next to
the input file, e.g. NEW_PFMEA__Head_lamp__normalized.csv
"""

import csv
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

GROUP_ROW = 13
FIELD_ROW = 15
DATA_START_ROW = 18

FAILURE_MODE_FIELD = "2. Failure Mode (FM) of the\nFocus Element"
FAILURE_CAUSE_FIELD = "3. Failure Cause (FC) of the Work Element"


def build_merge_lookup(ws):
    """Map every (row, col) inside a merged range to that merge's top-left cell."""
    lookup = {}
    for merged_range in ws.merged_cells.ranges:
        top_left_value = ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for col in range(merged_range.min_col, merged_range.max_col + 1):
                lookup[(row, col)] = top_left_value
    return lookup


def resolve(ws, merge_lookup, row, col):
    if (row, col) in merge_lookup:
        return merge_lookup[(row, col)]
    return ws.cell(row=row, column=col).value


def build_columns(ws, merge_lookup):
    """Return an ordered list of (group, field, column_index), one entry per
    distinct field - merge-continuation columns are skipped."""
    columns = []
    prev_group, prev_field = None, None
    for col in range(1, ws.max_column + 1):
        group = resolve(ws, merge_lookup, GROUP_ROW, col)
        field = resolve(ws, merge_lookup, FIELD_ROW, col)
        if field is None:
            continue
        if group == prev_group and field == prev_field:
            continue
        columns.append((group, field, col))
        prev_group, prev_field = group, field
    return columns


def normalize_sheet(ws):
    merge_lookup = build_merge_lookup(ws)
    columns = build_columns(ws, merge_lookup)

    raw_rows = []
    for row in range(DATA_START_ROW, ws.max_row + 1):
        record = {}
        for group, field, col in columns:
            record[(group, field)] = resolve(ws, merge_lookup, row, col)
        raw_rows.append(record)

    def mode_of(record):
        return next((v for (g, f), v in record.items() if f == FAILURE_MODE_FIELD), None)

    def cause_of(record):
        return next((v for (g, f), v in record.items() if f == FAILURE_CAUSE_FIELD), None)

    # The plant sheet sometimes records a Failure Mode's Severity on one
    # physical row and its matching Failure Cause on the next physical row
    # (Mode's merge is narrower than Severity's merge), which produces one
    # row with the cause blank and a sibling row with the same mode and the
    # real cause. Group consecutive rows that share the same forward-filled
    # Mode value, and within each group drop the blank-cause rows whenever
    # at least one row in that same group actually has a cause - otherwise
    # they are just duplicate shells of the row that really has the cause.
    blocks = []
    for record in raw_rows:
        if blocks and mode_of(blocks[-1][0]) == mode_of(record):
            blocks[-1].append(record)
        else:
            blocks.append([record])

    rows = []
    for block in blocks:
        non_blank_cause_rows = [r for r in block if cause_of(r) not in (None, "")]
        keep = non_blank_cause_rows if non_blank_cause_rows else block
        for record in keep:
            mode_val = mode_of(record)
            cause_val = cause_of(record)
            if mode_val in (None, "") and cause_val in (None, ""):
                continue
            rows.append(record)

    return columns, rows


def flatten_header(group, field):
    field_clean = re.sub(r"\s+", " ", field).strip()
    if group:
        group_clean = re.sub(r"\s+", " ", group).strip()
        return f"{group_clean} :: {field_clean}"
    return field_clean


def write_csv(out_path, columns, rows):
    headers = [flatten_header(g, f) for g, f, _ in columns]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for record in rows:
            writer.writerow(
                "" if record[(g, f)] is None else str(record[(g, f)]).strip()
                for g, f, _ in columns
            )


def main():
    if len(sys.argv) < 2:
        print("Usage: python step2_normalize.py <path-to-excel> [sheet_name]")
        sys.exit(1)

    path = sys.argv[1]
    only_sheet = sys.argv[2] if len(sys.argv) > 2 else None

    wb = load_workbook(path, data_only=True)
    sheet_names = [only_sheet] if only_sheet else wb.sheetnames

    for sheet_name in sheet_names:
        ws = wb[sheet_name]
        columns, rows = normalize_sheet(ws)

        print("=" * 80)
        print(f"Sheet: {sheet_name}  ->  {len(rows)} failure-entry rows, {len(columns)} fields")

        out_path = Path(path).with_name(
            f"{Path(path).stem}__{sheet_name.replace(' ', '_')}__normalized.csv"
        )
        write_csv(out_path, columns, rows)
        print(f"Wrote {out_path}")

        for i, record in enumerate(rows[:3], start=1):
            mode = next((v for (g, f), v in record.items() if f == FAILURE_MODE_FIELD), None)
            cause = next((v for (g, f), v in record.items() if f == FAILURE_CAUSE_FIELD), None)
            print(f"  row {i}: Failure Mode={mode!r:.60}  Failure Cause={cause!r:.60}")


if __name__ == "__main__":
    main()
