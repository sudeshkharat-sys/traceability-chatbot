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
import re

from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Border, PatternFill, Side, Font
from openpyxl.utils import get_column_letter

from app.pfmea_engine.layouts import LAYOUTS, get_layout, nashik_vda
from app.pfmea_engine.layouts import ai_fill as ai_fill_mod
from app.pfmea_engine.layouts.ai_fill import classify_6m
from app.pfmea_engine.layouts.ap import action_priority

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
_MEDIUM = Side(style="medium")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_DATA_BORDER = Border(left=_MEDIUM, right=_MEDIUM, top=_MEDIUM, bottom=_MEDIUM)
_WRAP = Alignment(wrap_text=True, vertical="center", horizontal="center")
_AI_COLOR = "FF1D4ED8"
_RED = "FFFF0000"

# Colours and fonts taken from the Nashik plant sheet (Arial throughout).
_GREY, _BLUE, _PINK, _GREEN, _PURPLE = "FFD9D9D9", "FF00B0F0", "FFF769BE", "FF009900", "FF7030A0"
_GROUP_FILL_BY_NAME = {  # band over each group of columns; Optimization has no fill
    "Structure Analysis (Step2)": "FFFFC000", "Function Analysis (Step3)": "FFFFC000",
    "Failure Analysis (Step4)": "FFFFC000", "Risk Analysis (Step5)": "FFE2EFDA",
}
_HEADER_FILL = {}
for _c in (1, 7, 13):
    _HEADER_FILL[_c] = _GREY
for _c in (3, 9, 16):
    _HEADER_FILL[_c] = _BLUE
for _c in (5, 11, 18):
    _HEADER_FILL[_c] = _PINK
for _c in (15, 20, 22, 23, 25, 26, 35, 36, 37, 38):
    _HEADER_FILL[_c] = _GREEN
_HEADER_FILL[27] = _PURPLE
# column -> (horizontal, vertical, bold) for data cells, as on the plant sheet
_DATA_STYLE = {1: ("left", "top", True), 3: ("left", "top", True), 5: ("left", "top", False),
               7: ("left", "top", False), 9: ("left", "center", True), 11: ("left", "top", False),
               13: ("center", "center", False), 15: ("center", "center", True), 16: ("center", "center", True),
               18: ("left", "center", True), 20: ("center", "center", True), 22: ("center", "center", True),
               23: ("center", "center", True), 25: ("center", "center", True), 26: ("center", "center", True),
               27: ("center", "center", False)}
for _c in range(28, 35):
    _DATA_STYLE[_c] = ("left", "top", False)
for _c in range(35, 39):
    _DATA_STYLE[_c] = ("center", "center", True)
_AI_FONT = Font(name="Arial", size=10, italic=True, color=_AI_COLOR)


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
    ws.cell(row=3, column=1, value="Planning and Preparation (Step1)").font = Font(name="Arial", size=12, bold=True)
    ws.merge_cells("A3:H4")
    for label_ref, label, value_ref, key in _TITLE_BLOCK:
        width = 3 if label_ref[0] in "AD" else 2
        for ref, text in ((label_ref, label), (value_ref, info.get(key) if key else None)):
            cell = ws[ref]
            cell.value = text
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = _BORDER
            cell.font = Font(name="Arial", size=10, bold=True)
            if text is not None and ref == label_ref:
                cell.font = Font(name="Arial", size=10, bold=True)
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
        1: [0] * len(rows),
        3: col_values(3), 9: list(zip(col_values(3), col_values(9))),
        5: col_values(3), 7: col_values(3), 11: col_values(3),  # per-step blocks, like the Nashik form
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


def _wrapped_lines(paragraph, chars):
    """Lines a paragraph takes when word-wrapped at `chars` characters."""
    lines, current = 1, 0
    for word in paragraph.split(" "):
        need = len(word) + (1 if current else 0)
        if current and current + need > chars:
            lines, current = lines + 1, len(word)
        else:
            current += need
        while current > chars:  # a single very long word breaks across lines
            lines, current = lines + 1, current - chars
    return lines


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
            bold = bool(ws.cell(row=r, column=c).font.b)
            chars = max(6, int(width_of(c, c_end) * (0.88 if bold else 0.93)))
            lines = sum(_wrapped_lines(part, chars) for part in str(value).split("\n"))
            needed = lines * 13.0 + 5
            have = sum(height[x] for x in range(r, r_end + 1))
            if needed > have:
                extra = (needed - have) / (r_end - r + 1)
                for x in range(r, r_end + 1):
                    height[x] += extra
    for r, h in height.items():
        ws.row_dimensions[r].height = min(h, 409)


_AUDIENCE = re.compile(r"^(Your Plant|Ship to Plant|End User)\s*:?\s*(.*)$", re.I)
_SIX_M = re.compile(r"^(Man|Machine|Method|Material(?: \(Indirect\))?|Measurement|Environment)\s*:\s*$")


def _font(bold=False, color=None, italic=False):
    return InlineFont(rFont="Arial", sz=10, b=bold, i=italic, color=color)


def _audience_runs(text, ai):
    """Failure Effect / Function of Process Item the way the plant writes it:
    "Your Plant :", "Ship to Plant :", "End User :" as red bold labels, the
    text under each in black. The Ship to Plant label is always shown (empty
    when the source has nothing), as on the plant sheet."""
    parts, current = {}, None
    for line in str(text).splitlines():
        m = _AUDIENCE.match(line.strip())
        if m:
            current = m.group(1).lower().replace("ship to plant", "ship")
            parts.setdefault(current, [])
            if m.group(2).strip():
                parts[current].append(m.group(2).strip())
        elif current and line.strip():
            parts[current].append(line.strip())
    if not parts:
        return None
    parts.setdefault("end user", [])
    body_color = _AI_COLOR if ai else None
    runs = []
    for key, label in (("your plant", "Your Plant :"), ("ship", "Ship to Plant :"), ("end user", "End User :")):
        if key not in parts and key != "ship":
            continue
        runs.append(TextBlock(_font(True, _RED, ai), label + "\n"))
        content = "\n".join(parts.get(key, []))
        runs.append(TextBlock(_font(False, body_color, ai), content + ("\n\n" if key == "your plant" else "\n" if key == "ship" else "")))
    return CellRichText(*runs)


def _block_runs(text, ai):
    """Work Element / Function of Work Element: 6M headings bold, items plain."""
    color = _AI_COLOR if ai else None
    runs = []
    for line in str(text).splitlines(keepends=True):
        bold = bool(_SIX_M.match(line.strip()))
        runs.append(TextBlock(_font(bold, color, ai), line))
    return CellRichText(*runs)


def _apply_rich_text(ws, first_row, last_row, ai_cells):
    for r in range(first_row, last_row + 1):
        for c in (5, 7, 11, 13):
            value = ws.cell(row=r, column=c).value
            if not isinstance(value, str) or not value:
                continue
            ai = (r, c) in ai_cells
            rich = _block_runs(value, ai) if c in (5, 11) else _audience_runs(value, ai)
            if rich is not None:
                ws.cell(row=r, column=c).value = rich


_STEP_FIELD = "2. Process Step Station No. and Name of\nFocus Element"
_FN_STEP_FIELD = "2. Function of the Process Step and Product Characteristic\n(Quantitative value is optional)"
_SEV_FIELD = "Severity (S) of FE\n"
_OCC_FIELD = "Occurrence (O) of FC"
_DET_FIELD = "Detection (D) of FC/FM"


def _write_nashik_sheet(ws, records, info=None):
    """Fill an empty worksheet with the Nashik header (rows 13-17) and one
    data row per record from row 18."""
    info = info or {}
    ai_cells = []
    ws.cell(row=1, column=1, value="Process Failure Mode and Effects Analysis (Process FMEA)")
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=20)
    ws.cell(row=1, column=1).font = Font(name="Arial", bold=True, size=14)

    _write_title_block(ws, info or {})
    _write_history_block(ws, info or {})

    for name, first, last in _GROUPS:
        ws.merge_cells(start_row=13, start_column=first, end_row=14, end_column=last)
        cell = ws.cell(row=13, column=first, value=name)
        cell.font = Font(name="Arial", size=10, bold=True)
        band = _GROUP_FILL_BY_NAME.get(name)
        for r in (13, 14):
            for c in range(first, last + 1):
                if band:
                    ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=band)
                ws.cell(row=r, column=c).border = _BORDER
        cell.alignment = _WRAP

    for first, last, text in _FIELDS:
        ws.merge_cells(start_row=15, start_column=first, end_row=17, end_column=last)
        cell = ws.cell(row=15, column=first, value=text)
        cell.font = Font(name="Arial", bold=True, size=8 if first < 20 else 9,
                         color="FFFFF2CC" if first == 27 else None)
        cell.alignment = _WRAP
        fill = _HEADER_FILL.get(first)
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
        # Action Priority from the plant's own S / O / D via the AIAG-VDA AP table (code only).
        sod = [next((v for k, v in record.items() if isinstance(k, tuple) and k[1] == f), None)
               for f in (_SEV_FIELD, _OCC_FIELD, _DET_FIELD)]
        ap = action_priority(*sod)
        if ap:
            ws.cell(row=row, column=26, value=ap)
        # Failure Cause: Nashik writes the 6M category in front ("Man- ..."). Added only when
        # a keyword clearly places the cause; the plant's own wording is kept untouched.
        cause = ws.cell(row=row, column=18).value
        category = classify_6m(cause)
        if cause and category and not re.match(rf"^\s*{re.escape(category.split(' ')[0])}\b", str(cause), re.I):
            ws.cell(row=row, column=18, value=f"{category.split(' ')[0]}- {cause}")
        # The plant's own action tracking, into the matching optimization columns.
        extra = record.get("_extra") or {}
        for role, col in (("recommended", 28), ("responsibility", 30), ("action_taken", 33),
                          ("sev_after", 35), ("occ_after", 36), ("det_after", 37)):
            if extra.get(role) is not None:
                ws.cell(row=row, column=col, value=extra[role])
        # Process Step: the form's header is "Station No. and Name of Focus Element", so the
        # plant's own Operation No goes in front of the name on one line ("10 - NAME").
        if record.get("_op_no") not in (None, "") and ws.cell(row=row, column=3).value:
            ws.cell(row=row, column=3, value=f"{record['_op_no']} - {ws.cell(row=row, column=3).value}")
        after = [extra.get(r) for r in ("sev_after", "occ_after", "det_after")]
        ap_after = action_priority(*after)
        if ap_after:
            ws.cell(row=row, column=38, value=ap_after)
        # AI-proposed text for columns the old form had no data for; only
        # where the plant left the cell blank, and visibly marked.
        for col, text in (record.get("_ai") or {}).items():
            if ws.cell(row=row, column=col).value in (None, ""):
                ws.cell(row=row, column=col, value=text)
                ai_cells.append((row, col))
        for first, last, _t in _FIELDS:
            horizontal, vertical, bold = _DATA_STYLE.get(first, ("left", "top", False))
            for c in range(first, last + 1):
                cell = ws.cell(row=row, column=c)
                cell.border = _DATA_BORDER
                cell.alignment = Alignment(wrap_text=True, horizontal=horizontal, vertical=vertical)
                cell.font = Font(name="Arial", size=10, bold=bold)
        for r_, c_ in [x for x in ai_cells if x[0] == row]:
            ws.cell(row=r_, column=c_).font = Font(name="Arial", size=10, italic=True, color=_AI_COLOR,
                                                   bold=_DATA_STYLE.get(c_, ("", "", False))[2])

    _merge_like_nashik(ws, 18, 18 + len(records) - 1)

    for c in range(1, 39):
        ws.column_dimensions[get_column_letter(c)].width = 14
    for first, _last, text in _FIELDS:
        if first in (13, 18, 20, 23):
            ws.column_dimensions[get_column_letter(first)].width = 40

    _apply_rich_text(ws, 18, 18 + len(records) - 1, set(ai_cells))
    _fit_row_heights(ws, 18, 18 + len(records) - 1)  # after rich text: counts the added labels

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
                ai_status[title]["error"] = ai_status[title]["message"] = "AI model is not configured"
        else:
            ai_status[title] = {"filled": 0, "failed": 0, "error": None, "message": None}

    out = load_workbook(source_path, rich_text=True)
    new_tabs = []  # (PFMEA tab title, label, records, ai status)
    for title, label, records, info in plan:
        index = out.sheetnames.index(title)
        del out[title]
        used = set(out.sheetnames)
        suffix = "" if len(plan) == 1 else f" - {title}"
        names = [_unique_title(base + suffix, used) for base in (PFD_TITLE, PAGE1_TITLE, PAGE2_TITLE)]
        used.update(names)
        # A Nashik workbook is three tabs: PFD, PFMEA page 1, PFMEA page 2 (Step 7 results).
        _write_pfd_sheet(out.create_sheet(names[0], index), records)
        page1 = out.create_sheet(names[1], index + 1)
        _write_nashik_sheet(page1, records, info)
        _write_page2_sheet(out.create_sheet(names[2], index + 2), records, info)
        status = dict(ai_status.get(title) or {}, filled=sum(len(r.get("_ai", {})) for r in records))
        new_tabs.append((names[1], label, records, status, names[0], names[2]))
        log(f"Converted '{title}' from {label} to AIAG-VDA format ({len(records)} rows): {', '.join(names)}")
    out.save(dest_path)
    if info_out is not None:
        info_out.extend({"title": t, "label": l, "records": r, "ai": a_, "pfd_title": pf, "page2_title": p2}
                        for t, l, r, a_, pf, p2 in new_tabs)
    return [t[0] for t in new_tabs]


PFD_TITLE = "PFD"
PAGE1_TITLE = "PFMEA- AIAG VDA Page 1"
PAGE2_TITLE = "PFMEA Page 2"
_BAD_TITLE = re.compile(r"[\[\]:*?/\\]")


def _unique_title(name, used):
    """Excel tab name: no []:*?/\\, at most 31 characters, unique in the workbook."""
    base = _BAD_TITLE.sub(" ", " ".join(str(name).split()))[:31].strip() or "Sheet"
    title, n = base, 2
    while title in used:
        suffix = f" ({n})"
        title, n = base[:31 - len(suffix)] + suffix, n + 1
    return title


def _by_operation(records):
    """[(operation no, step name, [unique requirements])] in sheet order."""
    ops, key = [], object()
    for rec in records:
        step = next((v for k, v in rec.items() if isinstance(k, tuple) and k[1] == _STEP_FIELD), None)
        req = next((v for k, v in rec.items() if isinstance(k, tuple) and k[1] == _FN_STEP_FIELD), None)
        this = (rec.get("_op_no"), step)
        if this != key:
            ops.append((rec.get("_op_no"), step, []))
            key = this
        text = " ".join(str(req).split()) if req else None
        if text and text not in ops[-1][2]:
            ops[-1][2].append(text)
    return ops


def _write_pfd_sheet(ws, records):
    """Process Flow Diagram tab: one row per operation from the old form's own
    Operation No, step name and requirements (Product Characteristics). Flow
    symbols and Process Characteristics are not in the old form - left empty."""
    ws.cell(row=1, column=2, value="PROCESS FLOW DIAGRAM").font = Font(name="Calibri", bold=True, size=16)
    ws.merge_cells("B1:F1")
    for col, text in enumerate(("Operation No.", "Operation Description", "Flow", "Product Characteristics",
                                "Process Characteristics"), start=2):
        c = ws.cell(row=2, column=col, value=text)
        c.font = Font(name="Calibri", bold=True, size=11)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = _DATA_BORDER
    for i, (op, step, reqs) in enumerate(_by_operation(records)):
        row = 3 + i
        values = (op, " ".join(str(step).split()) if step else None, None, "\n".join(reqs) or None, None)
        for col, value in enumerate(values, start=2):
            c = ws.cell(row=row, column=col, value=value)
            c.font = Font(name="Arial", size=11)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = _DATA_BORDER
    for letter, width in (("A", 4), ("B", 18.5), ("C", 46.8), ("D", 18.5), ("E", 42.2), ("F", 34.2)):
        ws.column_dimensions[letter].width = width


def _ap_rows(records):
    """[(failure mode, S, O, D, AP, has_action)] per cause row, AP from the plant's S/O/D."""
    rows = []
    for rec in records:
        get = lambda f: next((v for k, v in rec.items() if isinstance(k, tuple) and k[1] == f), None)
        s_, o_, d_ = get(_SEV_FIELD), get(_OCC_FIELD), get(_DET_FIELD)
        extra = rec.get("_extra") or {}
        rows.append((get("2. Failure Mode (FM) of the\nFocus Element"), s_, o_, d_,
                     action_priority(s_, o_, d_), bool(extra.get("recommended"))))
    return rows


def _write_page2_sheet(ws, records, info):
    """PFMEA Page 2 (Step 7 Result Documentation): AP summary, justification list
    for Medium/High without action, team members. Counts come from the converted
    rows in code; justification text and team details the old form lacks stay empty."""
    info = info or {}
    ws.cell(row=1, column=1, value="Process Failure Mode and Effects Analysis (Process FMEA)").font = Font(name="Arial", bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=20)
    _write_title_block(ws, info)
    _write_history_block(ws, info)

    def put(ref, value, bold=True, size=10, merge=None, border=True, wrap=True):
        c = ws[ref]
        c.value = value
        c.font = Font(name="Arial", bold=bold, size=size)
        c.alignment = Alignment(wrap_text=wrap, vertical="center")
        if merge:
            ws.merge_cells(merge)
        if border:
            area = ws[merge or ref]
            cells = [area] if not isinstance(area, tuple) else [x for row in area for x in (row if isinstance(row, tuple) else (row,))]
            for cell in cells:
                cell.border = _BORDER

    put("A13", "Result Documentation (Step7)", size=12, merge="A13:H14", border=False)
    put("I13", "Justification", border=False)
    put("I14", "In case of AP medium or High but team decided no action required", border=False)
    put("A15", "Action Priority summary", size=9, merge="A15:H15")
    put("A16", "Opn no", merge="A16:B16")
    put("C16", "Priority", merge="C16:D16")
    put("E16", "No of Failure modes", merge="E16:F16")
    put("G16", "No of Actions Identified", size=9, merge="G16:H16")
    rows = _ap_rows(records)
    for i, (label, letter) in enumerate((("High", "H"), ("Moderate", "M"), ("Low", "L"))):
        r = 17 + i
        put(f"A{r}", None, merge=f"A{r}:B{r}")
        put(f"C{r}", label)
        put(f"D{r}", letter)
        put(f"E{r}", sum(1 for x in rows if x[4] == letter) or None, merge=f"E{r}:F{r}")
        put(f"G{r}", sum(1 for x in rows if x[4] == letter and x[5]) or None, merge=f"G{r}:H{r}")

    put("A20", "Team Member details", merge="A20:H20")
    for ref, text, merge in (("A21", "S.no", None), ("B21", "Dept", "B21:C21"), ("D21", "Emp Id no", None),
                             ("E21", "Letter Code", None), ("F21", "Employee Name", "F21:H21")):
        put(ref, text, merge=merge)
    team = [n.strip() for n in str(info.get("team") or "").split(",") if n.strip()]
    for i in range(max(len(team), 14)):
        r = 22 + i
        put(f"A{r}", i + 1 if i < len(team) else None)
        put(f"B{r}", None, merge=f"B{r}:C{r}")
        put(f"D{r}", None)
        put(f"E{r}", None)
        put(f"F{r}", team[i] if i < len(team) else None, merge=f"F{r}:H{r}")

    for col, text in (("I", "S.no"), ("J", "Failure Mode (FM) of the\nFocus Element"), ("M", "Severity"),
                      ("N", "Occurrence"), ("O", "Detection"), ("P", "AP"), ("Q", "Justification")):
        put(f"{col}15", text, merge="J15:L15" if col == "J" else None)
    need = [x for x in rows if x[4] in ("H", "M") and not x[5]]
    for i, (fm, s_, o_, d_, ap, _a) in enumerate(need):
        r = 16 + i
        put(f"I{r}", i + 1)
        put(f"J{r}", fm, bold=False, merge=f"J{r}:L{r}")
        for col, v in (("M", s_), ("N", o_), ("O", d_), ("P", ap), ("Q", None)):
            put(f"{col}{r}", v, bold=False)
    for letter, width in (("A", 10.3), ("D", 12.2), ("E", 12.0), ("F", 10.3), ("H", 11.3), ("I", 10.3), ("J", 12.2),
                          ("K", 10.3), ("N", 11.8), ("O", 12.0), ("P", 10.3), ("Q", 30)):
        ws.column_dimensions[letter].width = width


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


def _plain_grid(headers, rows):
    return {"groups": [], "headers": headers,
            "rows": [[{"v": v, "rs": 1, "ai": False} for v in row] for row in rows]}


def pfd_grid(ws):
    rows = [[ws.cell(row=r, column=c).value for c in range(2, 7)] for r in range(3, ws.max_row + 1)]
    return _plain_grid([ws.cell(row=2, column=c).value for c in range(2, 7)], [r for r in rows if any(r)])


def page2_grid(ws):
    """The Step 7 summary (AP counts) plus the justification list, as plain rows."""
    rows = [[ws.cell(row=r, column=c).value for c in (3, 4, 5, 7)] for r in (17, 18, 19)]
    return _plain_grid(["Priority", "AP", "No of Failure modes", "No of Actions Identified"], rows)
