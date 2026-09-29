"""Nashik plant PFMEA sheet layout (AIAG-VDA 6-step form).

The reader itself is normalize_vda_sheet() in step2_normalize.py (kept there
so existing imports/constants are untouched); this module only identifies
the layout.
"""

import re

LAYOUT_ID = "nashik_vda"
LABEL = "Nashik (AIAG-VDA format)"

_SCAN_ROWS = 25


def _norm(value):
    return re.sub(r"\s+", " ", str(value)).strip().lower() if value is not None else ""


def header_row(ws):
    """Row containing the "Failure Mode (FM)" field header, or None. Matched
    on the "(fm)" abbreviation, not the bare phrase, because the sheet title
    also contains "Failure Mode"."""
    for r in range(1, min(ws.max_row, _SCAN_ROWS) + 1):
        for c in range(1, ws.max_column + 1):
            if "failure mode (fm)" in _norm(ws.cell(row=r, column=c).value):
                return r
    return None


def detect(ws):
    return header_row(ws) is not None


def normalize(ws):
    from app.pfmea_engine.step2_normalize import normalize_vda_sheet
    return normalize_vda_sheet(ws)
