"""Step 6: write step5's severity suggestions back into a copy of the source Excel.

Never modifies the original workbook - always saves to a new file
(default: "<original-stem>__with_suggestions.xlsx"). Existing data,
formatting, and merged cells are left untouched; only the empty
"Suggestion" cells (Severity, Detection, Prevention) get filled in, plus
a new "Remark" column added right after that block. Occurrence is
deliberately left blank - it requires real plant defect-frequency data,
not an AI guess.

The exact column positions are NOT hardcoded - they're located by
searching the header row for the row's LAST occurrence of "Severity (S)"
(the sheet has an earlier "Severity (S) of FE" column too, so this must
match the final/rightmost one, which is the Suggestion block), then
reading the columns to its right by their own header text so this keeps
working even if the plant's column order/naming shifts slightly (e.g.
"Prevention" vs "Action Priority" as the 4th column).

Usage:
    python step6_write_suggestions_to_excel.py <source.xlsx> <sheet_name> <suggestions.json> [output.xlsx]
"""

import json
import re
import sys
from pathlib import Path

from openpyxl import load_workbook


def normalize_header(text):
    """Collapse whitespace/newlines so header text matches regardless of
    Excel's wrapped-cell line breaks (e.g. 'Detectio\nn (D)' -> 'detection (d)')."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def find_suggestion_columns(ws, header_row):
    """Locate the Suggestion block's Severity/Occurrence/Detection/
    Prevention-or-ActionPriority columns by header text.

    Several of these labels (Severity, Occurrence, Detection, Prevention)
    also appear EARLIER in the sheet for unrelated columns (e.g. "Severity
    (S) of FE" under Risk Analysis, "Prevention Action" under Optimization
    Step6). To avoid ever matching one of those by mistake:
    1. Find "severity" using the LAST (rightmost) match in the whole row -
       the Suggestion block is always the final/rightmost occurrence.
    2. Then find occurrence/detection/prevention/action_priority/remark
       using the EARLIEST match strictly AFTER that Severity column only -
       matches before it are a different, unrelated column and must never
       be used here, no matter how the label text reads in isolation.
    """
    headers = {}
    for col in range(1, ws.max_column + 1):
        text = normalize_header(ws.cell(row=header_row, column=col).value)
        if not text:
            continue
        headers[col] = text

    def last_match(*needles):
        matches = [col for col, text in headers.items() if all(n in text for n in needles)]
        return max(matches) if matches else None

    def first_match_after(after_col, *needles):
        if after_col is None:
            return None
        matches = [col for col, text in headers.items() if col > after_col and all(n in text for n in needles)]
        return min(matches) if matches else None

    severity_col = last_match("severity")

    return {
        "severity": severity_col,
        "occurrence": first_match_after(severity_col, "occurrence"),
        "detection": first_match_after(severity_col, "detection"),
        "prevention": first_match_after(severity_col, "prevention"),
        # "priority" is misspelled "Prirorty" in the actual template, so
        # match on "action" alone (this column always immediately follows
        # Detection in the Suggestion block, so it's unambiguous here).
        "action_priority": first_match_after(severity_col, "action"),
        "remark": first_match_after(severity_col, "remark"),
    }


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


def build_remark(row):
    """Short, single-cell Remark text: notes merged failure modes and any
    cause/mode mismatch or ambiguity flag, so a reviewer knows why the
    Severity/Detection/Prevention cells read the way they do without
    opening the full JSON."""
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

    return " ".join(parts) if parts else "Single failure mode, no flags."


def main():
    if len(sys.argv) < 4:
        print("Usage: python step6_write_suggestions_to_excel.py <source.xlsx> <sheet_name> <suggestions.json> [output.xlsx]")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    sheet_name = sys.argv[2]
    suggestions_path = Path(sys.argv[3])
    output_path = Path(sys.argv[4]) if len(sys.argv) > 4 else source_path.with_name(f"{source_path.stem}__with_suggestions.xlsx")

    with open(suggestions_path, encoding="utf-8") as fh:
        suggestions = json.load(fh)

    if sheet_name not in suggestions:
        print(f"ERROR: '{sheet_name}' not found in {suggestions_path}. Available: {list(suggestions.keys())}")
        sys.exit(1)

    rows = suggestions[sheet_name]

    wb = load_workbook(source_path)
    if sheet_name not in wb.sheetnames:
        print(f"ERROR: sheet '{sheet_name}' not found in {source_path}. Available: {wb.sheetnames}")
        sys.exit(1)
    ws = wb[sheet_name]

    # Header row is wherever "Failure Mode" appears (row 15 in the known
    # layout) - detected instead of hardcoded so this survives minor
    # template edits.
    header_row = None
    for r in range(1, ws.max_row + 1):
        if any("failure mode (fm)" in normalize_header(ws.cell(row=r, column=c).value) for c in range(1, ws.max_column + 1)):
            header_row = r
            break
    if header_row is None:
        print("ERROR: could not find the header row (no cell containing 'Failure Mode').")
        sys.exit(1)

    cols = find_suggestion_columns(ws, header_row)
    print(f"Detected header row: {header_row}")
    print(f"Detected Suggestion columns: { {k: (ws.cell(row=header_row, column=v).coordinate if v else None) for k, v in cols.items()} }")

    if not cols["severity"] or not cols["detection"] or (not cols["prevention"] and not cols["action_priority"]):
        print("ERROR: could not locate the Suggestion block's Severity/Detection/Prevention columns by header text.")
        print("Open the file and check the exact header wording, or share it so the search patterns can be adjusted.")
        sys.exit(1)

    prevention_col = cols["prevention"] or cols["action_priority"]

    # Add a "Remark" column right after the last Suggestion column, if one
    # doesn't already exist there.
    last_suggestion_col = max(c for c in (cols["severity"], cols["occurrence"], cols["detection"], prevention_col) if c)
    if cols["remark"]:
        remark_col = cols["remark"]
    else:
        remark_col = last_suggestion_col + 1
        ws.insert_cols(remark_col)
        ws.cell(row=header_row, column=remark_col, value="Remark")
        print(f"Inserted new 'Remark' column at {ws.cell(row=header_row, column=remark_col).coordinate}")

    written = 0
    for row in rows:
        for excel_row in row["source_excel_rows"]:
            target_row = find_data_row_for_excel_row(ws, excel_row, cols["severity"])
            ws.cell(row=target_row, column=cols["severity"], value=row["ai_suggested_severity"])
            # Occurrence intentionally left blank - requires real plant data.
            # Detection intentionally left blank - step5 does not yet generate
            # a real Detection suggestion (only a Prevention-style
            # recommended_action). Do NOT duplicate recommended_action into
            # both columns - that would misrepresent it as two distinct
            # suggestions when it's only one.
            ws.cell(row=target_row, column=prevention_col, value=row.get("ai_recommended_action") or "")
            ws.cell(row=target_row, column=remark_col, value=build_remark(row))
            written += 1
            break  # one write per logical row group is enough - merged cells share the same target_row anyway

    wb.save(output_path)
    print(f"\nWrote {written} row(s) of suggestions to {output_path}")


if __name__ == "__main__":
    main()
