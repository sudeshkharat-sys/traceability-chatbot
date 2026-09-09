"""Step 6: write the final output Excel - plant's columns + a Suggestion group.

Per the requested layout: same 2-level header style as the plant's own
sheet (a merged Group row, then a Field row underneath), with the plant's
original fields untouched on the left, plus one new "Suggestion" group on
the right - for now just Severity and Occurrence (Prevention Control and
Detection suggestions are not built yet, so they're left out rather than
faked).

Data rows are the normalized, one-row-per-failure-entry rows from
step2_normalize.py (not the raw merged Excel layout) - that's the only
form where "one row = one failure" actually holds, which is what a
Suggestion column needs to attach to.

Reads step5_severity_llm.py / step5b_occurrence_llm.py's output JSON
(<stem>__severity_suggestions.json / __occurrence_suggestions.json) if
present, matching each output row to its suggestion by source_excel_rows.
If those files don't exist yet (Step 5 hasn't been run against the live
API), the Suggestion cells are filled with a clear placeholder instead of
being silently blank - so it's obvious what's missing versus what's a
real "no suggestion" result.

Usage:
    python step6_write_output.py <path-to-excel> <sheet_name>

Writes <stem>__<sheet>__with_suggestions.xlsx
"""

import json
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from step2_normalize import build_columns, build_merge_lookup, flatten_header, normalize_sheet

SUGGESTION_FILL = PatternFill(start_color="FFF4CC", end_color="FFF4CC", fill_type="solid")
GROUP_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
HEADER_FONT = Font(bold=True)


def load_suggestions(path, kind):
    """kind: 'severity' or 'occurrence'. Returns {tuple(source_excel_rows): result_dict}
    across all sheets in the file, or {} if the file doesn't exist yet."""
    suggestions_path = Path(path).with_name(f"{Path(path).stem}__{kind}_suggestions.json")
    if not suggestions_path.exists():
        return {}, suggestions_path

    with open(suggestions_path, encoding="utf-8") as fh:
        data = json.load(fh)

    lookup = {}
    for sheet_results in data.values():
        for r in sheet_results:
            lookup[tuple(r["source_excel_rows"])] = r
    return lookup, suggestions_path


SCRIPT_BY_FIELD = {"Severity": "step5_severity_llm.py", "Occurrence": "step5b_occurrence_llm.py"}


def format_suggestion(result, field_label, plant_key, ai_key):
    if result is None:
        return f"(AI suggestion pending - run {SCRIPT_BY_FIELD[field_label]} against the live API)"
    plant_val = result[plant_key]
    ai_val = result[ai_key]
    if plant_val == ai_val:
        return f"AI agrees: {ai_val} - matches plant's recorded value"
    return f"AI suggests {ai_val} (vs plant's {plant_val}) - {result['ai_reasoning']}"


def main():
    if len(sys.argv) != 3:
        print("Usage: python step6_write_output.py <path-to-excel> <sheet_name>")
        sys.exit(1)

    path, sheet_name = sys.argv[1], sys.argv[2]

    wb_in = load_workbook(path, data_only=True)
    ws_in = wb_in[sheet_name]
    columns = build_columns(ws_in, build_merge_lookup(ws_in))
    _cols, rows = normalize_sheet(ws_in)

    severity_lookup, severity_path = load_suggestions(path, "severity")
    occurrence_lookup, occurrence_path = load_suggestions(path, "occurrence")

    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = sheet_name[:31]

    # header row 1: group, merged across each group's field span; row 2: field names
    col_index = 1
    prev_group = None
    group_start_col = 1
    for group, field, _src_col, _ftype in columns:
        if group != prev_group:
            if prev_group is not None and col_index - 1 >= group_start_col:
                ws_out.merge_cells(start_row=1, start_column=group_start_col, end_row=1, end_column=col_index - 1)
                cell = ws_out.cell(row=1, column=group_start_col, value=prev_group)
                cell.font = HEADER_FONT
                cell.fill = GROUP_FILL
                cell.alignment = Alignment(horizontal="center")
            group_start_col = col_index
            prev_group = group
        ws_out.cell(row=2, column=col_index, value=flatten_header(None, field)).font = HEADER_FONT
        col_index += 1
    if prev_group is not None and col_index - 1 >= group_start_col:
        ws_out.merge_cells(start_row=1, start_column=group_start_col, end_row=1, end_column=col_index - 1)
        cell = ws_out.cell(row=1, column=group_start_col, value=prev_group)
        cell.font = HEADER_FONT
        cell.fill = GROUP_FILL
        cell.alignment = Alignment(horizontal="center")

    suggestion_start_col = col_index
    ws_out.cell(row=2, column=col_index, value="Severity Suggestion").font = HEADER_FONT
    ws_out.cell(row=2, column=col_index, value="Severity Suggestion").fill = SUGGESTION_FILL
    col_index += 1
    ws_out.cell(row=2, column=col_index, value="Occurrence Suggestion").font = HEADER_FONT
    ws_out.cell(row=2, column=col_index, value="Occurrence Suggestion").fill = SUGGESTION_FILL
    ws_out.merge_cells(start_row=1, start_column=suggestion_start_col, end_row=1, end_column=col_index)
    sug_group_cell = ws_out.cell(row=1, column=suggestion_start_col, value="Suggestion")
    sug_group_cell.font = HEADER_FONT
    sug_group_cell.fill = SUGGESTION_FILL
    sug_group_cell.alignment = Alignment(horizontal="center")

    # data rows
    for r, record in enumerate(rows, start=3):
        c = 1
        for group, field, _src_col, _ftype in columns:
            value = record[(group, field)]
            ws_out.cell(row=r, column=c, value="" if value is None else str(value).strip())
            c += 1

        src_key = tuple(record["_source_rows"])
        sev_result = severity_lookup.get(src_key)
        occ_result = occurrence_lookup.get(src_key)
        ws_out.cell(row=r, column=c, value=format_suggestion(sev_result, "Severity", "plant_recorded_severity", "ai_suggested_severity")).fill = SUGGESTION_FILL
        c += 1
        ws_out.cell(row=r, column=c, value=format_suggestion(occ_result, "Occurrence", "plant_recorded_occurrence", "ai_suggested_occurrence")).fill = SUGGESTION_FILL

    for c in range(1, col_index + 1):
        ws_out.column_dimensions[get_column_letter(c)].width = 28

    out_path = Path(path).with_name(f"{Path(path).stem}__{sheet_name.replace(' ', '_')}__with_suggestions.xlsx")
    wb_out.save(out_path)

    print(f"Wrote {out_path}  ({len(rows)} rows, {col_index} columns)")
    if not severity_lookup:
        print(f"NOTE: {severity_path.name} not found - Severity Suggestion column is a placeholder. Run step5_severity_llm.py against the live API first.")
    if not occurrence_lookup:
        print(f"NOTE: {occurrence_path.name} not found - Occurrence Suggestion column is a placeholder. Run step5b_occurrence_llm.py against the live API first.")


if __name__ == "__main__":
    main()
