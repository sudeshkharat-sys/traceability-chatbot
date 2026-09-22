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
  Detection (D)  - AI suggested Detection score (1-10, AIAG-VDA table),
                   scored from the CURRENT Detection Controls (DC) text
                   as actually described - not from Severity, and not
                   from the recommendation below
  Detection Note - AI suggested detection method (sensor/gauge/vision
                   check/functional test/inspection gate) specific to
                   catching THIS Failure Mode, distinct from Prevention
  Prevention     - AI suggested prevention/poka-yoke action
  Sub-modes      - when the Failure Mode cell was flagged as containing
                   2+ distinct modes merged into one cell, one compact
                   "A = <name> (S<x>/D<y>)" line per detected sub-mode
                   (up to 2; a rare 3rd+ still only shows in Remark).
                   Blank when the row's Mode wasn't a merged cell.
                   Deliberately NOT physical row-splitting: this sheet has
                   fields (Function of Step, Effect, Severity, Detection
                   Control, ...) merged ACROSS two different failure
                   entries at once, and openpyxl does not correctly
                   shrink/shift those merges when rows are inserted
                   mid-span (confirmed by testing - it leaves a stale,
                   overlapping merged range instead), so physically
                   splitting rows risks silently corrupting the sheet.
  Sub-mode Prevention / Sub-mode Detection - one "A = ...\nB = ..." line
                   per sub-mode's own Prevention action / Detection
                   action, matching the labels used in the Sub-modes
                   column above.
  Remark         - cause/mode mismatch, ambiguity breakdown, plant-vs-AI
                   disagreement, AND a cross-row check: flags when the
                   exact same Failure Cause text is reused verbatim
                   across two DIFFERENT Failure Modes elsewhere in the
                   sheet - e.g. a copy-pasted Cause that doesn't actually
                   belong to this row (see the "wrong part/mix-up" Cause
                   shared between "Scratch/Damage" and "Fitment/Wrong
                   Selection" in the Head lamp sheet). Deliberately does
                   NOT repeat the per-sub-mode Severity/Detection/action
                   detail already shown in the Sub-modes columns above -
                   just a short pointer to look there, so this cell
                   stays short instead of duplicating that data as text.

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
from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, PatternFill, Side

NEW_COLUMN_HEADERS = [
    # First column in the Suggestion block on purpose - the sheet's own
    # Failure Mode column is far to the left (e.g. column P), so a reader
    # who has scrolled all the way over to the Suggestion block at the
    # right edge would otherwise have no idea which failure mode a row's
    # Severity/Detection/Prevention values are even about, especially once
    # split into "A = .../B = ...". Repeating the mode name(s) right here
    # means the Suggestion section is readable entirely on its own.
    "Failure Mode",
    "Severity (S)",
    "Severity Note",
    "Occurrence (O)",
    "Detection (D)",
    "Detection Note",
    "Prevention",
    "Sub-modes",
    "Sub-mode Prevention",
    "Sub-mode Detection",
    "Remark",
]

# merge_mode folds each sub-mode's Prevention/Detection action straight into
# the Prevention/Detection Note columns as "A = ...\nB = ..." (same as
# Severity/Detection above), so the separate Sub-mode Prevention/Sub-mode
# Detection columns would just repeat that same text a second time - drop
# them instead of shipping a duplicate column. Sub-modes itself is also
# dropped: the plant's own Failure Mode column (already the first column
# on the sheet) already holds the raw merged text with both sub-modes in
# it, so re-stating "A = <name> / B = <name>" in a second column next to
# it is redundant - the A/B labels only need to live where the actual
# per-mode values are (Severity/Detection/Prevention Note above).
MERGE_MODE_COLUMN_HEADERS = [h for h in NEW_COLUMN_HEADERS if h not in ("Sub-modes", "Sub-mode Prevention", "Sub-mode Detection")]

# Distinct purple fill for the new Suggestion block, matching the plant's
# own screenshot of this block, so it visually reads as a clearly-new,
# AI-suggested area rather than blending into the existing green/blue
# section headers.
SUGGESTION_FILL_RGB = "FF7030A0"

# One uniform thin border applied to every cell in the new block, instead
# of copying whatever border the sheet's own template cells happen to use
# (which vary - some are "medium", some "thin" - copying them made the new
# block's grid look inconsistent, dark in some spots and light in others).
UNIFORM_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def find_merge_containing(ws, row, col):
    for merged_range in ws.merged_cells.ranges:
        if merged_range.min_row <= row <= merged_range.max_row and merged_range.min_col <= col <= merged_range.max_col:
            return merged_range
    return None


def find_sub_header_rows(ws, header_row):
    """The sheet's own sub-headers (e.g. 'Severity (S)' at O15) are each
    merged vertically across a 3-row band starting at header_row (O15:O17).
    Find that band - and a real reference cell to copy styling from - from
    an existing sub-header instead of hardcoding header_row+2, so this
    survives a template row-height change. Returns (row_start, row_end,
    reference_cell)."""
    for col in range(1, ws.max_column + 1):
        merged_range = find_merge_containing(ws, header_row, col)
        if merged_range and merged_range.min_row == header_row and merged_range.max_row > header_row:
            return merged_range.min_row, merged_range.max_row, ws.cell(row=merged_range.min_row, column=merged_range.min_col)
    ref = ws.cell(row=header_row, column=1)
    return header_row, header_row, ref


def find_section_header_rows(ws, header_row):
    """The sheet's own top-level section headers (e.g. 'Optimization
    (Step6)') sit merged across 2 rows immediately above the sub-header
    band (rows header_row-2 : header_row-1). Found from an existing
    section header's own merge instead of hardcoding, for the same reason
    as find_sub_header_rows. Returns (row_start, row_end, reference_cell)."""
    candidate_row = header_row - 2
    for col in range(1, ws.max_column + 1):
        merged_range = find_merge_containing(ws, candidate_row, col)
        if merged_range and merged_range.min_row == candidate_row and merged_range.max_row == header_row - 1:
            return merged_range.min_row, merged_range.max_row, ws.cell(row=merged_range.min_row, column=merged_range.min_col)
    ref = ws.cell(row=candidate_row, column=1)
    return candidate_row, header_row - 1, ref


def style_like(target_cell, reference_cell, fill_rgb=None, center=False):
    """Copy font from an existing header cell so the new Suggestion header
    reads as part of the same sheet, not a bolted-on afterthought. Border
    is NOT copied from the reference - the sheet's own template cells use
    inconsistent border weights ("medium" on some headers, "thin" on data
    cells), and copying them made the new block's grid look uneven, dark
    in some spots and light in others; every new cell gets the same
    UNIFORM_BORDER instead, guaranteeing a consistent look regardless of
    what the rest of the template does. Optionally override the fill color
    (e.g. to the Suggestion block's own distinct purple), and/or force
    centered horizontal+vertical alignment with wrap text - reads better
    for a wide merged header or a data cell than inheriting the
    reference's plain left alignment."""
    target_cell.font = copy(reference_cell.font)
    target_cell.border = UNIFORM_BORDER
    if center:
        target_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    else:
        target_cell.alignment = copy(reference_cell.alignment)
    if fill_rgb:
        target_cell.fill = PatternFill(fill_type="solid", fgColor=fill_rgb)
    else:
        target_cell.fill = copy(reference_cell.fill)


def style_merged_range(ws, min_row, max_row, min_col, max_col, reference_cell, fill_rgb=None, center=False):
    """Apply style_like to EVERY physical cell inside a merged range, not
    just its top-left anchor. A merged cell only DISPLAYS the anchor's
    value, but Excel/other viewers can still show each interior cell's own
    border/fill at the seams if they're left at their default (unstyled)
    state - this is what caused some borders to look dark/thin and others
    to look missing/inconsistent. Styling every cell in the range makes
    the whole merged block's border look uniform."""
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            style_like(ws.cell(row=r, column=c), reference_cell, fill_rgb=fill_rgb, center=center)


def set_row_height_for_wrapped_text(ws, row_start, row_end, values, column_widths, points_per_line=15):
    """Excel only auto-fits row height for UNMERGED cells - a merged range
    (which every Suggestion-block cell is, when it spans a multi-row plant
    entry) keeps whatever height the template's original rows had, so a
    long wrapped/bulleted value like Remark gets visually clipped at the
    bottom unless we size the row ourselves.

    Estimates each cell's line count (explicit '\\n' breaks, plus wrapping
    within the column's character width) and sets the merge's total height
    to fit the tallest cell, split evenly across its rows."""
    max_lines = 1
    for col, value in values.items():
        if not value:
            continue
        width_chars = max(column_widths.get(col, 20), 1)
        # Sum of wrapped-line counts across this cell's explicit '\n'
        # breaks - e.g. a 3-bullet Remark where each bullet itself wraps
        # to 2 lines needs 6 lines of height, not 3.
        total_lines = sum(max(1, (len(line) // width_chars) + 1) for line in str(value).split("\n"))
        max_lines = max(max_lines, total_lines)

    row_count = row_end - row_start + 1
    height_per_row = max((max_lines * points_per_line) / row_count, points_per_line)
    for r in range(row_start, row_end + 1):
        current = ws.row_dimensions[r].height
        if current is None or height_per_row > current:
            ws.row_dimensions[r].height = height_per_row


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


def build_remark(row, cause_to_modes, this_cause, merge_mode=False):
    """Short, single-cell Remark text: notes merged failure modes, any
    cause/mode mismatch or ambiguity flag, plant-vs-AI disagreement, and
    (new) whether this row's Cause is duplicated on a different Mode
    elsewhere in the sheet."""
    parts = []

    merged = row.get("ai_merged_modes_detected")
    if merged:
        if merge_mode:
            # merge_mode has no Sub-modes column - the A/B breakdown lives
            # directly in Severity/Detection/Prevention above, matched
            # against the plant's own (still-merged) Failure Mode cell.
            parts.append(f"Merged failure mode ({len(merged)} distinct modes detected) - see the A/B breakdown in Severity/Detection/Prevention above, matched against the Failure Mode text.")
        else:
            # The per-sub-mode Severity/Detection/Prevention/Detection-action
            # detail lives in the dedicated Sub-modes/Sub-mode Prevention/
            # Sub-mode Detection columns now - keep this a short pointer
            # instead of duplicating all of that as one long paragraph.
            parts.append(f"Merged failure mode ({len(merged)} distinct modes detected) - see Sub-modes columns for per-mode Severity/Detection/actions. Row-level Severity/Detection above are the worst case; consider splitting this row in the plant sheet.")

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

    return "\n".join(f"- {p}" for p in parts) if parts else "Single failure mode, no flags."


def apply_suggestions_to_sheet(ws, rows, cause_to_modes=None, cause_by_mode=None, log=print, merge_mode=False):
    """Core of step6: given an already-open worksheet and this sheet's list
    of suggestion rows (step5's per-sheet output shape), append the
    Suggestion column block and write every row's values into it. Mutates
    ws in place; does not save the workbook (caller decides when/where).

    cause_to_modes/cause_by_mode are optional - when omitted, the
    duplicate-Cause-across-Modes check in Remark is skipped for this sheet
    (e.g. if no severity_input data was available). Returns the number of
    rows written, or None if the sheet's header row couldn't be found (an
    error is logged instead of raising, so a multi-sheet caller can skip
    just this one sheet and continue with the rest).

    merge_mode=True changes how a merged (2+ sub-modes) row's Severity/
    Severity Note/Detection/Detection Note cells are written: instead of
    the single row-level worst-case value, each cell gets one "A = ...\\nB
    = ..." line per detected sub-mode - the same A/B labels as the
    Sub-modes column, so a reviewer never has to go hunting in Sub-modes
    for the actual number. The Sub-modes column itself then only needs to
    say what A and B ARE (the failure-mode names), not repeat their
    scores. A row with no detected sub-modes is unaffected either way."""
    cause_to_modes = cause_to_modes or {}
    cause_by_mode = cause_by_mode or {}

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
        log(f"ERROR: could not find the header row (no cell containing 'Failure Mode (FM)') in sheet '{ws.title}'.")
        return None

    # Always append a brand new column block - never write into an existing
    # column, even an empty one, so it's unambiguous which cells are
    # AI-suggested vs. the plant's own data. Mirrors the sheet's own
    # convention: a merged top-level section header (like "Optimization
    # (Step6)" at row 13-14) spanning the whole block, plus each
    # sub-column's header merged vertically across the same 3-row band as
    # its siblings (e.g. "Severity (S)" at row 15-17) - found by inspecting
    # an existing sub-header's own merged range rather than hardcoding row
    # numbers, so this keeps working if the template's row layout shifts.
    headers = MERGE_MODE_COLUMN_HEADERS if merge_mode else NEW_COLUMN_HEADERS
    start_col = ws.max_column + 1
    end_col = start_col + len(headers) - 1

    section_header_row_start, section_header_row_end, section_ref_cell = find_section_header_rows(ws, header_row)
    sub_header_row_start, sub_header_row_end, sub_ref_cell = find_sub_header_rows(ws, header_row)

    ws.merge_cells(start_row=section_header_row_start, start_column=start_col, end_row=section_header_row_end, end_column=end_col)
    ws.cell(row=section_header_row_start, column=start_col, value="Suggestion")
    # Top-level section header stays plain (no fill) like its siblings
    # ("Risk Analysis (Step5)", "Optimization (Step6)") - only the
    # sub-column headers below get the distinct purple fill. Centered
    # (not inheriting the sibling's left-alignment) since a 6-column-wide
    # merged label reads oddly pinned to one edge - every cell in the
    # merge is styled, not just the anchor, so the block's border/fill
    # looks uniform instead of showing stray unstyled interior cells.
    style_merged_range(ws, section_header_row_start, section_header_row_end, start_col, end_col, section_ref_cell, center=True)

    for i, header in enumerate(headers):
        col = start_col + i
        ws.merge_cells(start_row=sub_header_row_start, start_column=col, end_row=sub_header_row_end, end_column=col)
        ws.cell(row=sub_header_row_start, column=col, value=header)
        style_merged_range(ws, sub_header_row_start, sub_header_row_end, col, col, sub_ref_cell, fill_rgb=SUGGESTION_FILL_RGB, center=True)

    col_by_header = {header: start_col + i for i, header in enumerate(headers)}
    failure_mode_col = col_by_header["Failure Mode"]
    severity_col = col_by_header["Severity (S)"]
    severity_note_col = col_by_header["Severity Note"]
    occurrence_col = col_by_header["Occurrence (O)"]
    detection_col = col_by_header["Detection (D)"]
    detection_note_col = col_by_header["Detection Note"]
    prevention_col = col_by_header["Prevention"]
    submodes_col = col_by_header.get("Sub-modes")
    submode_prevention_col = col_by_header.get("Sub-mode Prevention")
    submode_detection_col = col_by_header.get("Sub-mode Detection")
    remark_col = col_by_header["Remark"]

    # Widen the new columns so wrapped text is actually readable instead of
    # squeezing into the sheet's default column width - Severity/Occurrence/
    # Detection hold only a short number so they stay narrow (one normal
    # cell width); the Note and other text-heavy columns get roughly double
    # that so a sentence of reasoning doesn't look cramped/odd in a
    # single-number-width column.
    column_widths = {
        failure_mode_col: 35,
        severity_col: 8,
        severity_note_col: 45,
        occurrence_col: 8,
        detection_col: 8,
        detection_note_col: 40,
        prevention_col: 45,
        submodes_col: 35,
        submode_prevention_col: 45,
        submode_detection_col: 45,
        remark_col: 50,
    }
    for col, width in column_widths.items():
        if col is None:
            continue
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    log(f"  [{ws.title}] header row: {header_row}, Suggestion block: {ws.cell(row=header_row, column=start_col).coordinate.rstrip('0123456789')}-{ws.cell(row=header_row, column=end_col).coordinate.rstrip('0123456789')}")
    if not cause_by_mode:
        log(f"  [{ws.title}] NOTE: no Cause data given - the duplicate-Cause-across-Modes check in Remark is skipped for this sheet.")

    # Reference an existing DATA cell (not a header) for border/alignment/
    # font, so the new Suggestion cells look like the rest of the row
    # instead of bare/unformatted - found from the first data row under
    # the sub-header band.
    data_ref_cell = ws.cell(row=sub_header_row_end + 1, column=1)
    for r in range(sub_header_row_end + 1, ws.max_row + 1):
        candidate = ws.cell(row=r, column=start_col - 1)
        if candidate.border.top.style or candidate.border.left.style:
            data_ref_cell = candidate
            break

    written = 0
    for row in rows:
        this_cause = cause_by_mode.get(row["failure_mode"].strip())
        excel_rows = row["source_excel_rows"]
        # The plant's Failure Mode cell is merged across all rows in
        # source_excel_rows (e.g. [18, 19]) - merge these new Suggestion
        # cells across the SAME row span for each column, so this record's
        # row height/borders match the rest of the row instead of leaving
        # a bare, unmerged single-height cell next to a merged 2-row block.
        row_start, row_end = min(excel_rows), max(excel_rows)

        splits = (row.get("ai_split_suggestions") or [])[:2]
        labels = ["A", "B"]

        # Repeated at the start of the Suggestion block regardless of
        # merge_mode, so the block reads on its own without scrolling back
        # to the sheet's own Failure Mode column - single mode name normally,
        # or "A = .../B = ..." when this row's cell was a merged/split mode.
        failure_mode_value = (
            "\n".join(f"{labels[i]} = {s['failure_mode']}" for i, s in enumerate(splits))
            if splits else row["failure_mode"]
        )

        def sev_text(s):
            sev = s.get("suggested_severity")
            return str(sev) if sev is not None else "?"

        def det_text(s):
            det = s.get("suggested_detection")
            return str(det) if det is not None else "(not scored - re-run needed)"

        if merge_mode and splits:
            # A/B split values move INTO the actual Severity/Detection/
            # Prevention columns (this is the point of merge_mode) - no
            # single row-level worst-case value sitting next to them, and
            # no separate Sub-mode Prevention/Detection columns repeating
            # the same text a second time. Sub-modes then only needs to
            # say what A/B name each is.
            severity_value = "\n".join(f"{labels[i]} = {sev_text(s)}" for i, s in enumerate(splits))
            severity_note_value = "\n".join(f"{labels[i]} = {s.get('reasoning') or ''}" for i, s in enumerate(splits))
            detection_value = "\n".join(f"{labels[i]} = {det_text(s)}" for i, s in enumerate(splits))
            detection_note_value = "\n".join(f"{labels[i]} = {s.get('detection_recommendation') or 'n/a'}" for i, s in enumerate(splits))
            prevention_value = "\n".join(f"{labels[i]} = {s.get('recommended_action') or 'n/a'}" for i, s in enumerate(splits))
            # No Sub-modes column in merge_mode (see MERGE_MODE_COLUMN_HEADERS) -
            # the plant's own Failure Mode column already shows the raw
            # merged text, and the A/B labels above are enough to match it.
            submodes_value = None
        else:
            severity_value = row["ai_suggested_severity"]
            severity_note_value = row.get("ai_reasoning") or ""
            detection_value = row.get("ai_suggested_detection")
            detection_note_value = row.get("ai_detection_recommendation") or ""
            prevention_value = row.get("ai_recommended_action") or ""
            # Non-merge_mode keeps the original "A = name (Sx/Dy)" combined
            # line in Sub-modes, unchanged from before merge_mode existed.
            submodes_value = "\n".join(
                f"{labels[i]} = {s['failure_mode']} (S{sev_text(s)}/D{det_text(s)})" for i, s in enumerate(splits)
            )

        values = {
            failure_mode_col: failure_mode_value,
            severity_col: severity_value,
            severity_note_col: severity_note_value,
            # Occurrence intentionally left blank - requires real plant data.
            detection_col: detection_value,
            detection_note_col: detection_note_value,
            prevention_col: prevention_value,
            remark_col: build_remark(row, cause_to_modes, this_cause, merge_mode=merge_mode),
        }
        if submodes_col is not None:
            values[submodes_col] = submodes_value
        # Non-merge_mode only: dedicated Sub-mode Prevention/Detection
        # columns with the same "A = ...\nB = ..." breakdown - in
        # merge_mode this same text already lives in Prevention/Detection
        # Note above, so these columns don't exist there (see
        # MERGE_MODE_COLUMN_HEADERS).
        if submode_prevention_col is not None:
            values[submode_prevention_col] = "\n".join(
                f"{labels[i]} = {s.get('recommended_action') or 'n/a'}" for i, s in enumerate(splits)
            )
        if submode_detection_col is not None:
            values[submode_detection_col] = "\n".join(
                f"{labels[i]} = {s.get('detection_recommendation') or 'n/a'}" for i, s in enumerate(splits)
            )
        for col, value in values.items():
            if row_end > row_start:
                ws.merge_cells(start_row=row_start, start_column=col, end_row=row_end, end_column=col)
            ws.cell(row=row_start, column=col, value=value)
            # Style every cell in the merge, not just the anchor, and force
            # centered+wrapped alignment - this is what keeps the border
            # look consistent (no stray unstyled interior cells) and text
            # vertically centered for readability.
            style_merged_range(ws, row_start, row_end, col, col, data_ref_cell, center=True)
        # Excel never auto-fits row height across a MERGED cell (only
        # unmerged ones), so a wrapped multi-line value - the bulleted
        # Remark especially - gets visually clipped at the bottom of the
        # merge unless we set an explicit height ourselves.
        set_row_height_for_wrapped_text(ws, row_start, row_end, values, column_widths)
        written += 1

    return written


def main():
    args = sys.argv[1:]
    # --merge-mode: A/B split values go into the Severity/Detection columns
    # themselves instead of the row-level worst-case value (see
    # apply_suggestions_to_sheet's docstring). Writes to a separate
    # "__merge_mode.xlsx" file by default - never overwrites the plain
    # "__with_suggestions.xlsx" output, so both formats stay available side
    # by side for review.
    merge_mode = "--merge-mode" in args
    if merge_mode:
        args.remove("--merge-mode")

    if len(args) < 3:
        print("Usage: python step6_write_suggestions_to_excel.py <source.xlsx> <sheet_name> <suggestions.json> [severity_input.json] [output.xlsx] [--merge-mode]")
        sys.exit(1)

    source_path = Path(args[0])
    sheet_name = args[1]
    suggestions_path = Path(args[2])

    # 4th/5th args are both optional and positionally ambiguous (severity_input
    # json vs. output xlsx) - disambiguate by file extension.
    severity_input_path = None
    output_path = None
    for extra in args[3:]:
        if extra.lower().endswith(".json"):
            severity_input_path = Path(extra)
        else:
            output_path = Path(extra)
    if output_path is None:
        suffix = "__merge_mode.xlsx" if merge_mode else "__with_suggestions.xlsx"
        output_path = source_path.with_name(f"{source_path.stem}{suffix}")

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

    written = apply_suggestions_to_sheet(ws, rows, cause_to_modes=cause_to_modes, cause_by_mode=cause_by_mode, merge_mode=merge_mode)
    if written is None:
        sys.exit(1)

    wb.save(output_path)
    print(f"\nWrote {written} row(s) of suggestions to {output_path}")


if __name__ == "__main__":
    main()
