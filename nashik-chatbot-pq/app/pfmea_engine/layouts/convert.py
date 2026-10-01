"""Convert a non-Nashik PFMEA sheet (e.g. Chakan RPN format) into a real
Nashik AIAG-VDA sheet, so the rest of the pipeline only ever sees Nashik.

The plant's own values are copied as-is (Chakan's IC:/EC: effect text becomes
the Your Plant / End User sections, see chakan_rpn.translate_effect). The
Nashik form has more columns than the old form (work element, functions,
optimization block); the AI gap-fill (ai_fill.py) proposes the descriptive
ones from the sheet's own text, flagged in blue italics. Output is
one unmerged row per failure cause with context repeated on every row, which
the Nashik reader handles the same as merged cells.
"""

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, PatternFill, Side, Font
from openpyxl.utils import get_column_letter

from app.pfmea_engine.layouts import LAYOUTS, get_layout, nashik_vda
from app.pfmea_engine.layouts import ai_fill as ai_fill_mod

_GROUPS = [
    ("Structure Analysis (Step2)", 1, 6),
    ("Function Analysis (Step3)", 7, 12),
    ("Failure Analysis (Step4)", 13, 19),
    ("Risk Analysis (Step5)", 20, 27),
    ("Optimization (Step6)", 28, 38),
]
# (first column, last column, header text) - same spans as the Nashik template.
_FIELDS = [
    (1, 2, "1. Process Item System, Subsystem,\nPart Element or\nName of Process"),
    (3, 4, "2. Process Step Station No. and Name of\nFocus Element"),
    (5, 6, "3. Process Work Element\n(6 M) \nMan, Machine, Method, Material (Indirect), Measurement, Mother earth (Environment)"),
    (7, 8, "1. Function of the Process Item Function of System, Subsystem,\nPart Element or Process"),
    (9, 10, "2. Function of the Process Step and Product Characteristic\n(Quantitative value is optional)"),
    (11, 12, "3. Function of the Process Work Element and Process\nCharacteristic"),
    (13, 14, "1. Failure Effects (FE) to the Next Higher Level Element and/or End User"),
    (15, 15, "Severity (S) of FE\n"),
    (16, 17, "2. Failure Mode (FM) of the\nFocus Element"),
    (18, 19, "3. Failure Cause (FC) of the Work Element"),
    (20, 21, "Current Prevention Control (PC) of FC"),
    (22, 22, "Occurrence (O) of FC"),
    (23, 24, "Current Detection Controls (DC) of FC or FM"),
    (25, 25, "Detection (D) of FC/FM"),
    (26, 26, "Action Priority"),
    (27, 27, "Special \nCharacteristics"),
    (28, 28, "Prevention Action"),
    (29, 29, "Detection Action"),
    (30, 30, "Responsible Persons Name"),
    (31, 31, "Target Completion\nDate"),
    (32, 32, "Status"),
    (33, 33, "Action Taken with Pointer to  Evidence"),
    (34, 34, "Completion Date"),
    (35, 35, "Severity (S)"),
    (36, 36, "Occurrence (O)"),
    (37, 37, "Detection (D)"),
    (38, 38, "Action Priority"),
]
_COL_FOR_FIELD = {text: first for first, _last, text in _FIELDS}
_COL_FOR_FIELD["Special Characteristics"] = 27  # Chakan spelling of the Nashik header

_THIN = Side(style="thin")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_WRAP = Alignment(wrap_text=True, vertical="center", horizontal="center")
_PINK, _GREEN = "FFF769BE", "FF009900"
_GROUP_FILL = "FFFFC000"
_AI_COLOR = "FF1D4ED8"
_AI_FONT = Font(italic=True, color=_AI_COLOR)


# Nashik title block: (label cell, value cell) pairs; A-C / D-F / G-H are merged
# three / three / two wide like the template.
_TITLE_BLOCK = [
    ("A5", "Company Name ", "A6", "company"),
    ("A7", "Manufacturing Location", "A8", "plant"),
    ("A9", "Customer Name ", "A10", None),
    ("A11", "Model Year / Program", "A12", "model"),
    ("D5", "Subject ", "D6", "partnameprocess"),
    ("D7", "PFMEA Start Date", "D8", "fmeadateorig"),
    ("D9", "PFMEA Revision Date", "D10", "revdate"),
    ("D11", "Cross Functional Team", "D12", "team"),
    ("G5", "PFMEA ID Number", "G6", "docno"),
    ("G7", "Process Responsibility", "G8", "responsibility"),
    ("G9", "PFMEA Rev No", "G10", "revno"),
    ("G11", "Confidential Level", "G12", None),
]


def _write_title_block(ws, info):
    """Fill the Nashik title block from whatever the source sheet carried;
    fields the source has no equivalent for stay blank."""
    info = dict(info)
    reviewed, approved = info.get("reviewedby"), info.get("approvedby")
    if reviewed or approved:
        info["responsibility"] = "; ".join(
            x for x in (f"Reviewed by: {reviewed}" if reviewed else None,
                        f"Approved by: {approved}" if approved else None) if x)
    ws.cell(row=3, column=1, value="Planning and Preparation (Step1)")
    ws.merge_cells("A3:H4")
    for label_ref, label, value_ref, key in _TITLE_BLOCK:
        width = 3 if label_ref[0] in "AD" else 2
        for ref, text in ((label_ref, label), (value_ref, info.get(key) if key else None)):
            cell = ws[ref]
            cell.value = text
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = _BORDER
            if text is not None and ref == label_ref:
                cell.font = Font(bold=True)
            end = cell.column + width - 1
            ws.merge_cells(start_row=cell.row, start_column=cell.column, end_row=cell.row, end_column=end)


def _write_history_block(ws, info):
    """Nashik's revision table (I3:T12) from the source's own Rev No / date;
    skipped when the source carries neither."""
    if not (info.get("revno") or info.get("revdate")):
        return
    ws.cell(row=3, column=9, value="History / Change Authorization")
    ws.merge_cells("I3:T4")
    ws["I3"].font = Font(bold=True)
    ws["I3"].alignment = Alignment(wrap_text=True, vertical="center")
    for col, text in ((9, "Rev no"), (10, "Date:"), (11, "Remarks")):
        ws.cell(row=5, column=col, value=text).font = Font(bold=True)
    ws.merge_cells("K5:T5")
    ws.cell(row=6, column=9, value=info.get("revno"))
    ws.cell(row=6, column=10, value=info.get("revdate"))
    ws.merge_cells("K6:T6")
    for r in range(3, 7):
        for c in range(9, 21):
            ws.cell(row=r, column=c).border = _BORDER


def _runs(values):
    """(start, end) index pairs of consecutive equal values."""
    runs, start = [], 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start]:
            runs.append((start, i - 1))
            start = i
    return runs


def _merge_like_nashik(ws, first_row, last_row):
    """Merge repeated context the way the Nashik form does, instead of
    repeating it on every cause row: Process Item / its function over the whole
    sheet, Step and its Function per consecutive run, and Effect + Severity +
    Failure Mode + Special Characteristics once per failure-mode block.
    Everything else (cause, controls, O, D, AP) stays one row each."""
    rows = range(first_row, last_row + 1)

    def col_values(col):
        return [ws.cell(row=r, column=col).value for r in rows]

    mode_block = list(zip(col_values(16), col_values(13), col_values(15)))
    # field first-col -> grouping key per row (None = never merge vertically)
    keys = {
        1: [0] * len(rows), 7: [0] * len(rows),
        3: col_values(3), 9: list(zip(col_values(3), col_values(9))),
        5: col_values(3), 11: col_values(3),  # Work Element blocks are per step, like the Nashik form
        13: mode_block, 15: mode_block, 16: mode_block, 27: mode_block,
    }
    for first, last, _t in _FIELDS:
        key_list = keys.get(first)
        runs = _runs(key_list) if key_list else [(i, i) for i in range(len(rows))]
        for start, end in runs:
            if start == end and last == first:
                continue
            ws.merge_cells(start_row=first_row + start, start_column=first,
                           end_row=first_row + end, end_column=last)


def _fit_row_heights(ws, first_row, last_row):
    """Excel never auto-grows rows that hold merged cells, so wrapped text
    (Failure Effect's "Your Plant: ... End User: ..." etc.) would show only its
    first line. Size each row so every cell's full text fits; a cell merged
    over several rows shares its needed height across them."""
    def width_of(col_first, col_last):
        return sum(ws.column_dimensions[get_column_letter(c)].width or 14 for c in range(col_first, col_last + 1))

    spans = {}
    for merged in ws.merged_cells.ranges:
        if merged.min_row >= first_row:
            spans[(merged.min_row, merged.min_col)] = merged
    height = {r: 15.0 for r in range(first_row, last_row + 1)}
    for r in range(first_row, last_row + 1):
        for c in range(1, 39):
            value = ws.cell(row=r, column=c).value
            if value is None or isinstance(value, (int, float)):
                continue
            merged = spans.get((r, c))
            r_end, c_end = (merged.max_row, merged.max_col) if merged else (r, c)
            chars = max(8, int(width_of(c, c_end) * 1.05))
            lines = sum(max(1, -(-len(part) // chars)) for part in str(value).split("\n"))
            needed = lines * 12.5 + 3
            have = sum(height[x] for x in range(r, r_end + 1))
            if needed > have:
                extra = (needed - have) / (r_end - r + 1)
                for x in range(r, r_end + 1):
                    height[x] += extra
    for r, h in height.items():
        ws.row_dimensions[r].height = min(h, 409)


def _write_nashik_sheet(ws, records, info=None):
    """Fill an empty worksheet with the Nashik header (rows 13-17) and one
    data row per record from row 18."""
    info = info or {}
    ai_cells = []
    ws.cell(row=1, column=1, value="Process Failure Mode and Effects Analysis (Process FMEA)")
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=20)
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)

    _write_title_block(ws, info or {})
    _write_history_block(ws, info or {})

    for name, first, last in _GROUPS:
        ws.merge_cells(start_row=13, start_column=first, end_row=14, end_column=last)
        cell = ws.cell(row=13, column=first, value=name)
        cell.font = Font(bold=True)
        for r in (13, 14):
            for c in range(first, last + 1):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=_GROUP_FILL)
                ws.cell(row=r, column=c).border = _BORDER
        cell.alignment = _WRAP

    for first, last, text in _FIELDS:
        ws.merge_cells(start_row=15, start_column=first, end_row=17, end_column=last)
        cell = ws.cell(row=15, column=first, value=text)
        cell.font = Font(bold=True)
        cell.alignment = _WRAP
        fill = None
        if text.startswith("3. Process Work Element") or text.startswith("3. Function of the Process Work") or text.startswith("3. Failure Cause"):
            fill = _PINK
        elif first in (15, 20, 22, 23, 25, 26, 35, 36, 37, 38):
            fill = _GREEN
        for r in range(15, 18):
            for c in range(first, last + 1):
                ws.cell(row=r, column=c).border = _BORDER
                if fill:
                    ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=fill)
    ws.row_dimensions[15].height = 22.5

    for i, record in enumerate(records):
        row = 18 + i
        for key, value in record.items():
            if not isinstance(key, tuple):
                continue
            col = _COL_FOR_FIELD.get(key[1])
            if col is None or value is None:
                continue
            ws.cell(row=row, column=col, value=value)
        # Process Item comes from the source's own "Aggregate Part Descrptn".
        # Work Element (6M) and the Function columns come from the AI gap-fill below.
        if info.get("aggregatepartdescrptn"):
            ws.cell(row=row, column=1, value=info["aggregatepartdescrptn"])
        # Action Priority is left blank: the source has RPN, not AP, and only
        # data present in the input is filled.
        # The plant's own action tracking, into the matching optimization columns.
        extra = record.get("_extra") or {}
        for role, col in (("recommended", 28), ("responsibility", 30), ("action_taken", 33),
                          ("sev_after", 35), ("occ_after", 36), ("det_after", 37)):
            if extra.get(role) is not None:
                ws.cell(row=row, column=col, value=extra[role])
        # AI-proposed text for columns the old form had no data for; only
        # where the plant left the cell blank, and visibly marked.
        for col, text in (record.get("_ai") or {}).items():
            if ws.cell(row=row, column=col).value in (None, ""):
                ws.cell(row=row, column=col, value=text)
                ai_cells.append((row, col))
        for first, last, _t in _FIELDS:
            for c in range(first, last + 1):
                cell = ws.cell(row=row, column=c)
                cell.border = _BORDER
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for r_, c_ in [x for x in ai_cells if x[0] == row]:
            ws.cell(row=r_, column=c_).font = _AI_FONT

    _merge_like_nashik(ws, 18, 18 + len(records) - 1)

    for c in range(1, 39):
        ws.column_dimensions[get_column_letter(c)].width = 14
    for first, _last, text in _FIELDS:
        if first in (13, 18, 20, 23):
            ws.column_dimensions[get_column_letter(first)].width = 40

    _fit_row_heights(ws, 18, 18 + len(records) - 1)

def _get_llm_or_none(log):
    try:
        import os
        from app.pfmea_engine.step5_severity_llm import get_llm
        # Own setting, independent of the scoring model: GPT-5 (default) is
        # better at leaving a cell empty when unsure; gpt4omini also works.
        return get_llm(profile=os.environ.get("PFMEA_CONVERT_LLM_PROFILE", "gpt5"),
                       reasoning_effort=os.environ.get("PFMEA_CONVERT_REASONING_EFFORT", "low"))
    except Exception as exc:  # noqa: BLE001 - missing credentials etc. must not block conversion
        log(f"AI gap-fill unavailable ({exc}); blank columns left empty.")
        return None


def convert_workbook_to_nashik(source_path, dest_path, layout="auto", log=print, info_out=None,
                               ai_fill=True, llm=None):
    """Save a copy of the workbook at dest_path where every PFMEA sheet that
    is not already Nashik format is rebuilt in Nashik format. Returns the
    list of converted sheet names (empty = nothing to convert; dest_path is
    then not written). If info_out is a list, one {title, label, records}
    dict per converted sheet is appended (for the UI preview). With ai_fill,
    columns the old form has no data for (Process Item, Work Element, the
    Function columns) are proposed by the LLM instead of left blank. The
    original file is never modified."""
    wb = load_workbook(source_path, data_only=True)
    plan = []
    for ws in wb.worksheets:
        if layout in (None, "", "auto"):
            module = next((m for m in LAYOUTS if m.detect(ws)), None)
        else:
            module = get_layout(layout)
        if module is None or module is nashik_vda:
            continue
        _cols, records = module.normalize(ws)
        if records:
            header = getattr(module, "header_info", None)
            plan.append((ws.title, module.LABEL, records, header(ws) if header else {}))
    if not plan:
        return []

    ai_status = {}
    if ai_fill:
        llm = llm or _get_llm_or_none(log)
    for title, _label, records, info in plan:
        if ai_fill:
            # llm=None still runs the rule-based part (6M classification, Operator)
            ai_status[title] = ai_fill_mod.fill_blanks(records, info, llm, log=log)
            if llm is None:
                ai_status[title]["error"] = "AI model not available"
        else:
            ai_status[title] = {"filled": 0, "failed": 0, "error": None}

    out = load_workbook(source_path, rich_text=True)
    for title, label, records, info in plan:
        index = out.sheetnames.index(title)
        del out[title]
        new_ws = out.create_sheet(title, index)
        _write_nashik_sheet(new_ws, records, info)
        log(f"Converted '{title}' from {label} to Nashik AIAG-VDA format ({len(records)} rows)")
    out.save(dest_path)
    if info_out is not None:
        info_out.extend({"title": t, "label": l, "records": r, "ai": ai_status.get(t)} for t, l, r, _i in plan)
    return [t for t, _l, _r, _i in plan]


def sheet_grid(ws, first_row=18):
    """The converted sheet as a plain grid the UI can draw like Excel:
    headers (group band + field names) and rows of cells with rowspan, so the
    merged Nashik blocks look the same in the browser as in the file."""
    merged = {(m.min_row, m.min_col): m for m in ws.merged_cells.ranges if m.min_row >= first_row}
    covered = set()
    for m in merged.values():
        for r in range(m.min_row + 1, m.max_row + 1):
            covered.add((r, m.min_col))
    groups = []
    for name, g_first, g_last in _GROUPS:
        n = sum(1 for first, _l, _t in _FIELDS if g_first <= first <= g_last)
        groups.append({"text": name.split(" (")[0], "span": n})
    headers = [" ".join(text.split()) for _f, _l, text in _FIELDS]
    rows = []
    for r in range(first_row, ws.max_row + 1):
        cells = []
        for first, _last, _t in _FIELDS:
            if (r, first) in covered:
                continue
            cell = ws.cell(row=r, column=first)
            m = merged.get((r, first))
            color = getattr(getattr(cell.font, "color", None), "rgb", None)
            cells.append({"v": cell.value, "rs": (m.max_row - m.min_row + 1) if m else 1,
                          "ai": color == _AI_COLOR and cell.value not in (None, "")})
        rows.append(cells)
    return {"groups": groups, "headers": headers, "rows": rows}
