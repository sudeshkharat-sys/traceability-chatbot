"""Step 6: write step5's severity suggestions back into a copy of the source Excel.

Never modifies the original workbook - always saves to a new file
(default: "<original-stem>__with_suggestions.xlsx"). Existing data,
formatting, and columns are left untouched; this ALWAYS appends a brand
new "Suggestion" column block after the last existing column, rather
than writing into any pre-existing column (even an empty one like
"Action Priority") - the plant asked for a genuinely new, dedicated block
so it's unambiguous which cells are AI-suggested vs. the plant's own data.

New columns added, in order:
  Severity (S)   - AI suggested severity (1-10)
  Severity Note  - short reason for that severity
  Occurrence (O) - left BLANK: requires real plant defect-frequency data,
                   never AI-generated
  Detection (D)  - left BLANK for now: step5 does not yet generate a
                   distinct Detection suggestion (see step5's
                   recommended_action, which is Prevention-only)
  Prevention     - AI suggested prevention/poka-yoke action
  Remark         - merged-mode info, cause/mode mismatch, ambiguity
                   breakdown, plant-vs-AI disagreement, AND (new) a
                   cross-row check: flags when the exact same Failure
                   Cause text is reused verbatim across two DIFFERENT
                   Failure Modes elsewhere in the sheet - e.g. a
                   copy-pasted Cause that doesn't actually belong to
                   this row (see the "wrong part/mix-up" Cause shared
                   between "Scratch/Damage" and "Fitment/Wrong
                   Selection" in the Head lamp sheet).

The duplicate-Cause check needs the original Failure Cause text, which
is not in step5's suggestions JSON (only Failure Mode is) - it's read
from the severity_input JSON produced by step4_severity_input.py
(pass its path as the 4th argument; the check is skipped gracefully if
not provided).

Usage:
    python step6_write_suggestions_to_excel.py <source.xlsx> <sheet_name> <suggestions.json> [severity_input.json] [output.xlsx]
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

NEW_COLUMN_HEADERS = [
    "Severity (S)",
    "Severity Note",
    "Occurrence (O)",
    "Detection (D)",
    "Prevention",
    "Remark",
]


def normalize_header(text):
    """Collapse whitespace/newlines so header text matches regardless of
    Excel's wrapped-cell line breaks (e.g. 'Detectio\nn (D)' -> 'detection (d)')."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def normalize_cause_text(text):
    """Normalize a Failure Cause cell for exact-duplicate comparison -
    collapse whitespace/case so trivial formatting differences don't
    hide a real copy-paste duplicate."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def find_data_row_for_excel_row(ws, target_excel_row, search_col):
    """Given one of the plant's original row numbers (from
    source_excel_rows), find the actual row to write into - accounting for
    vertically merged cells (a Failure Mode cell merged across rows 18-19
    is one logical entry; writing into its top-left row is what actually
    shows up)."""
    for merged_range in ws.merged_cells.ranges:
        if merged_range.min_col <= search_col <= merged_range.max_col:
            if merged_range.min_row <= target_excel_row <= merged_range.max_row:
                return merged_range.min_row
    return target_excel_row


def build_duplicate_cause_map(severity_input_path):
    """Return {normalized_cause_text: [failure_mode, ...]} across every
    mode in every group of the given severity_input JSON, so a Remark can
    flag when this row's Cause is also used, verbatim, by a DIFFERENT
    Failure Mode elsewhere in the same sheet."""
    if not severity_input_path:
        return {}
    with open(severity_input_path, encoding="utf-8") as fh:
        groups = json.load(fh)
    cause_to_modes = defaultdict(list)
    for group in groups:
        for mode_entry in group.get("modes_covered", []):
            cause = normalize_cause_text(mode_entry.get("failure_cause"))
            mode = mode_entry.get("failure_mode")
            if cause and mode:
                cause_to_modes[cause].append(mode)
    return cause_to_modes


def build_remark(row, cause_to_modes, this_cause):
    """Short, single-cell Remark text: notes merged failure modes, any
    cause/mode mismatch or ambiguity flag, plant-vs-AI disagreement, and
    (new) whether this row's Cause is duplicated on a different Mode
    elsewhere in the sheet."""
    parts = []

    merged = row.get("ai_merged_modes_detected")
    if merged:
        numbered = "; ".join(f"{i + 1}. {m}" for i, m in enumerate(merged))
        parts.append(f"Merged failure mode: {numbered}.")

    if row.get("ai_cause_mode_mismatch"):
        note = row.get("ai_cause_mode_mismatch_note") or "Stated Cause does not logically produce the stated Mode."
        parts.append(f"Cause/Mode mismatch: {note}")

    possible = row.get("ai_possible_severities")
    if possible:
        options = "; ".join(f"S{p['severity']} ({p['effect_used']})" for p in possible)
        parts.append(f"Ambiguous - plausible severities: {options}. Suggested value is the worst case; review before finalizing.")

    if not row.get("agree"):
        parts.append(f"AI severity ({row['ai_suggested_severity']}) differs from plant-recorded ({row['plant_recorded_severity']}) - review recommended.")

    if this_cause:
        normalized = normalize_cause_text(this_cause)
        other_modes = sorted({m for m in cause_to_modes.get(normalized, []) if m.strip() != row["failure_mode"].strip()})
        if other_modes:
            listed = "; ".join(other_modes)
            parts.append(f"Same Failure Cause text is also used, verbatim, on a different Failure Mode: {listed}. Verify this Cause actually belongs to this row and wasn't copy-pasted.")

    return " ".join(parts) if parts else "Single failure mode, no flags."


def main():
    if len(sys.argv) < 4:
        print("Usage: python step6_write_suggestions_to_excel.py <source.xlsx> <sheet_name> <suggestions.json> [severity_input.json] [output.xlsx]")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    sheet_name = sys.argv[2]
    suggestions_path = Path(sys.argv[3])

    # 4th/5th args are both optional and positionally ambiguous (severity_input
    # json vs. output xlsx) - disambiguate by file extension.
    severity_input_path = None
    output_path = None
    for extra in sys.argv[4:]:
        if extra.lower().endswith(".json"):
            severity_input_path = Path(extra)
        else:
            output_path = Path(extra)
    if output_path is None:
        output_path = source_path.with_name(f"{source_path.stem}__with_suggestions.xlsx")

    with open(suggestions_path, encoding="utf-8") as fh:
        suggestions = json.load(fh)

    if sheet_name not in suggestions:
        print(f"ERROR: '{sheet_name}' not found in {suggestions_path}. Available: {list(suggestions.keys())}")
        sys.exit(1)

    rows = suggestions[sheet_name]
    cause_to_modes = build_duplicate_cause_map(severity_input_path)

    # Cause text per Failure Mode, for the duplicate-Cause check - only
    # available if severity_input_path was given.
    cause_by_mode = {}
    if severity_input_path:
        with open(severity_input_path, encoding="utf-8") as fh:
            groups = json.load(fh)
        for group in groups:
            for mode_entry in group.get("modes_covered", []):
                cause_by_mode[mode_entry["failure_mode"].strip()] = mode_entry.get("failure_cause")

    wb = load_workbook(source_path)
    if sheet_name not in wb.sheetnames:
        print(f"ERROR: sheet '{sheet_name}' not found in {source_path}. Available: {wb.sheetnames}")
        sys.exit(1)
    ws = wb[sheet_name]

    # Header row is wherever "Failure Mode (FM)" appears - detected instead
    # of hardcoded row 15 so this survives minor template edits. Matched on
    # the specific "(fm)" abbreviation, not the bare phrase, since the
    # sheet's own title also contains "Failure Mode" and would otherwise
    # false-match on row 1.
    header_row = None
    for r in range(1, ws.max_row + 1):
        if any("failure mode (fm)" in normalize_header(ws.cell(row=r, column=c).value) for c in range(1, ws.max_column + 1)):
            header_row = r
            break
    if header_row is None:
        print("ERROR: could not find the header row (no cell containing 'Failure Mode (FM)').")
        sys.exit(1)

    # Always append a brand new column block - never write into an existing
    # column, even an empty one, so it's unambiguous which cells are
    # AI-suggested vs. the plant's own data.
    start_col = ws.max_column + 1
    for i, header in enumerate(NEW_COLUMN_HEADERS):
        ws.cell(row=header_row, column=start_col + i, value=header)

    severity_col, severity_note_col, occurrence_col, detection_col, prevention_col, remark_col = range(start_col, start_col + 6)

    print(f"Detected header row: {header_row}")
    print(f"Appended new Suggestion columns at: {ws.cell(row=header_row, column=start_col).coordinate} - {ws.cell(row=header_row, column=start_col + 5).coordinate}")
    if not severity_input_path:
        print("NOTE: no severity_input.json given - the duplicate-Cause-across-Modes check in Remark is skipped.")

    written = 0
    for row in rows:
        this_cause = cause_by_mode.get(row["failure_mode"].strip())
        for excel_row in row["source_excel_rows"]:
            target_row = find_data_row_for_excel_row(ws, excel_row, severity_col)
            ws.cell(row=target_row, column=severity_col, value=row["ai_suggested_severity"])
            ws.cell(row=target_row, column=severity_note_col, value=row.get("ai_reasoning") or "")
            # Occurrence intentionally left blank - requires real plant data.
            # Detection intentionally left blank - step5 does not yet generate
            # a real, distinct Detection suggestion (only Prevention).
            ws.cell(row=target_row, column=prevention_col, value=row.get("ai_recommended_action") or "")
            ws.cell(row=target_row, column=remark_col, value=build_remark(row, cause_to_modes, this_cause))
            written += 1
            break  # one write per logical row group is enough - merged cells share the same target_row anyway

    wb.save(output_path)
    print(f"\nWrote {written} row(s) of suggestions to {output_path}")


if __name__ == "__main__":
    main()
