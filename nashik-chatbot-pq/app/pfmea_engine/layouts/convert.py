"""Convert a non-Nashik PFMEA sheet (e.g. Chakan RPN format) into a real
Nashik AIAG-VDA sheet, so the rest of the pipeline only ever sees Nashik.

The plant's own values are copied as-is (Chakan's IC:/EC: effect text becomes
the Your Plant / End User sections, see chakan_rpn.translate_effect). The
Nashik form has more columns than the old form (work element, functions,
optimization block); those are left blank for the plant to fill. Output is
one unmerged row per failure cause with context repeated on every row, which
the Nashik reader handles the same as merged cells.
"""

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, PatternFill, Side, Font
from openpyxl.utils import get_column_letter

from app.pfmea_engine.layouts import LAYOUTS, get_layout, nashik_vda

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


def _write_nashik_sheet(ws, records):
    """Fill an empty worksheet with the Nashik header (rows 13-17) and one
    data row per record from row 18."""
    ws.cell(row=1, column=1, value="Process Failure Mode and Effects Analysis (Converted to Nashik AIAG-VDA format)")
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=20)
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)

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
        for first, last, _t in _FIELDS:
            for c in range(first, last + 1):
                cell = ws.cell(row=row, column=c)
                cell.border = _BORDER
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            if last > first:
                ws.merge_cells(start_row=row, start_column=first, end_row=row, end_column=last)

    for c in range(1, 39):
        ws.column_dimensions[get_column_letter(c)].width = 14
    for first, _last, text in _FIELDS:
        if first in (13, 18, 20, 23):
            ws.column_dimensions[get_column_letter(first)].width = 40


def convert_workbook_to_nashik(source_path, dest_path, layout="auto", log=print):
    """Save a copy of the workbook at dest_path where every PFMEA sheet that
    is not already Nashik format is rebuilt in Nashik format. Returns the
    list of converted sheet names (empty = nothing to convert; dest_path is
    then not written). The original file is never modified."""
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
            plan.append((ws.title, module.LABEL, records))
    if not plan:
        return []

    out = load_workbook(source_path, rich_text=True)
    for title, label, records in plan:
        index = out.sheetnames.index(title)
        del out[title]
        new_ws = out.create_sheet(title, index)
        _write_nashik_sheet(new_ws, records)
        log(f"Converted '{title}' from {label} to Nashik AIAG-VDA format ({len(records)} rows)")
    out.save(dest_path)
    return [t for t, _l, _r in plan]
