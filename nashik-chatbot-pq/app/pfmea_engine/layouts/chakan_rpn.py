"""Chakan plant PFMEA sheet layout (older compact RPN-style form).

Identified by its header band ("Operation No", "Potential Failure Mode",
"Severity", "Occurrence", "Detection", "RPN" ...) - see _detect_context().
Structure: one flat header band (~5 rows, short labels sometimes stacked one
letter per row, e.g. "C L A S S"), data right below it, NO merged data cells
- a blank Failure Mode means "same mode as the row above", and every row
carries its own Cause.

Mapped onto the same canonical (group, field) names the Nashik AIAG-VDA
reader produces, so every downstream step (scoring, prompts, write-back) is
shared. Layout-specific knowledge lives ONLY in this file.
"""

import re

from app.pfmea_engine.step2_normalize import (
    FAILURE_CAUSE_FIELD,
    FAILURE_MODE_FIELD,
    build_merge_lookup,
    resolve,
)

LAYOUT_ID = "chakan_rpn"
LABEL = "Chakan (RPN format)"

_EFFECT_FIELD = "1. Failure Effects (FE) to the Next Higher Level Element and/or End User"
_STEP_FIELD = "2. Process Step Station No. and Name of\nFocus Element"
_STEP_FUNCTION_FIELD = "2. Function of the Process Step and Product Characteristic\n(Quantitative value is optional)"
_SEVERITY_RAW = "Severity (S) of FE\n"
_PREVENTION_FIELD = "Current Prevention Control (PC) of FC"
_OCCURRENCE_RAW = "Occurrence (O) of FC"
_DETECTION_CTRL_FIELD = "Current Detection Controls (DC) of FC or FM"
_DETECTION_RAW = "Detection (D) of FC/FM"
_SPECIAL_FIELD = "Special Characteristics"
# Downstream (step3c/step4) reads these keys directly; this layout has no
# such column, so they are emitted as always-blank rather than KeyError-ing.
_BLANK_FIELDS = [
    "1. Process Item System, Subsystem,\nPart Element or\nName of Process",
    "3. Process Work Element ",
    "1. Function of the Process Item Function of System, Subsystem,\nPart Element or Process",
    "3. Function of the Process Work Element and Process\nCharacteristic",
]

_LEGACY_HEADER_SCAN_ROWS = 25


def _compact(text):
    return re.sub(r"[^A-Z0-9]", "", str(text).upper()) if text is not None else ""


def _detect_context(ws):
    """Return (header_row, band_end, {role: column_index}) if this sheet is
    the Chakan compact PFMEA layout, else None. The header band's per-column text is
    the concatenation of every cell in that column across the band, with
    non-alphanumerics dropped, so both stacked single letters ("C","L","A",
    "S","S" -> CLASS) and split words ("POTENTIAL"/"FAILURE"/"MODE") match."""
    merge_lookup = build_merge_lookup(ws)
    for header_row in range(1, min(ws.max_row, _LEGACY_HEADER_SCAN_ROWS) + 1):
        if _compact(resolve(ws, merge_lookup, header_row, 1)) != "OPERATIONNO":
            continue
        band_end = header_row + 4
        for merged_range in ws.merged_cells.ranges:
            if merged_range.min_row == header_row and merged_range.min_col == 1:
                band_end = merged_range.max_row
        cols = {}
        for col in range(1, ws.max_column + 1):
            text = "".join(_compact(ws.cell(row=r, column=col).value) for r in range(header_row, band_end + 1))
            role = None
            if text == "OPERATIONNO":
                role = "op_no"
            elif text.startswith("PROCESSSTEP"):
                role = "step"
            elif text.startswith("REQUIREMENTS"):
                role = "requirements"
            elif "FAILUREMODE" in text and text.startswith("POTENTIAL"):
                role = "mode"
            elif text.startswith("POTENTIALEFFECT"):
                role = "effect"
            elif text == "SEVERITY":
                role = "severity"
            elif text == "CLASS":
                role = "special"
            elif text.startswith("POTENTIALCAUSE"):
                role = "cause"
            elif text.startswith("CURRENT") and "PREVENTION" in text:
                role = "prevention"
            elif text == "OCCURRENCE":
                role = "occurrence"
            elif text.startswith("CURRENT") and "DETECTION" in text:
                role = "detection_ctrl"
            elif text == "DETECTION":
                role = "detection"
            # first match wins: the sheet may repeat "Operation No" etc. in a
            # trailing tracking block far to the right
            if role and role not in cols:
                cols[role] = col
        if {"mode", "cause", "severity", "occurrence", "detection"} <= cols.keys():
            return header_row, band_end, cols
    return None


def normalize(ws, layout=None):
    if layout is None:
        layout = _detect_context(ws)
        if layout is None:
            return [], []
    header_row, band_end, cols = layout
    merge_lookup = build_merge_lookup(ws)

    def cell(row, role):
        col = cols.get(role)
        if col is None:
            return None
        value = resolve(ws, merge_lookup, row, col)
        if isinstance(value, str) and not value.strip():
            return None
        return value

    role_fields = [
        ("step", "Structure Analysis (Step2)", _STEP_FIELD, "other"),
        ("requirements", "Function Analysis (Step3)", _STEP_FUNCTION_FIELD, "other"),
        ("effect", "Failure Analysis (Step4)", _EFFECT_FIELD, "other"),
        ("mode", "Failure Analysis (Step4)", FAILURE_MODE_FIELD, "other"),
        ("severity", "Failure Analysis (Step4)", _SEVERITY_RAW, "risk_score"),
        ("cause", "Failure Analysis (Step4)", FAILURE_CAUSE_FIELD, "work_element"),
        ("prevention", "Risk Analysis (Step5)", _PREVENTION_FIELD, "risk_score"),
        ("occurrence", "Risk Analysis (Step5)", _OCCURRENCE_RAW, "risk_score"),
        ("detection_ctrl", "Risk Analysis (Step5)", _DETECTION_CTRL_FIELD, "risk_score"),
        ("detection", "Risk Analysis (Step5)", _DETECTION_RAW, "risk_score"),
        ("special", "Risk Analysis (Step5)", _SPECIAL_FIELD, "other"),
    ]
    columns = [(g, f, cols[role], t) for role, g, f, t in role_fields if role in cols]

    rows = []
    carry = {"step": None, "requirements": None, "effect": None, "mode": None, "severity": None, "special": None}
    for row in range(band_end + 1, ws.max_row + 1):
        if cell(row, "step") is not None:
            carry["step"] = cell(row, "step")
        mode, cause = cell(row, "mode"), cell(row, "cause")
        if mode is not None:
            # A new Failure Mode row owns its own requirement/effect/severity/
            # class (even if blank); a blank-mode row is another Cause of the
            # mode above and inherits them.
            carry.update(
                mode=mode,
                requirements=cell(row, "requirements"),
                effect=cell(row, "effect"),
                severity=cell(row, "severity"),
                special=cell(row, "special"),
            )
        if mode is None and cause is None:
            continue
        if carry["mode"] is None:
            continue
        severity = cell(row, "severity")
        record = {"_source_rows": [row], "_is_cause_merge_end": True}
        values = {
            "step": carry["step"],
            "requirements": carry["requirements"],
            "effect": carry["effect"],
            "mode": carry["mode"],
            "severity": severity if severity is not None else carry["severity"],
            "cause": cause,
            "prevention": cell(row, "prevention"),
            "occurrence": cell(row, "occurrence"),
            "detection_ctrl": cell(row, "detection_ctrl"),
            "detection": cell(row, "detection"),
            "special": cell(row, "special") if cell(row, "special") is not None else carry["special"],
        }
        for role, group, field, _t in role_fields:
            record[(group, field)] = values[role]
        record["_raw_effect"] = values["effect"]  # for the convert preview (before/after)
        record[("Failure Analysis (Step4)", _EFFECT_FIELD)] = translate_effect(values["effect"])
        for field in _BLANK_FIELDS:
            record[("Structure Analysis (Step2)", field)] = None
        rows.append(record)
    return columns, rows


def detect(ws):
    return _detect_context(ws) is not None


def header_row(ws):
    ctx = _detect_context(ws)
    return ctx[0] if ctx else None


# --- Failure Effect translation ------------------------------------------
# Chakan writes the effect cell as "[optional leading product effect]\nIC :
# <internal customer consequence>\nEC : <external customer consequence>".
# The scoring prompt (step5) judges Severity from the "End User" audience and
# treats "Your Plant" as context, using the Nashik sub-headers. Without this
# translation none of those headers would be found and the model would get
# one undifferentiated blob (where an in-plant "Offline Rework" line can
# drag the score). IC -> Your Plant; EC and any unlabeled leading text
# (the product-level effect, e.g. "Rattle noise") -> End User. The plant's
# own cell is never rewritten - this only changes what the LLM reads.
_IC_RE = re.compile(r"^\s*IC\s*[:\-]\s*(.*)$", re.IGNORECASE)
_EC_RE = re.compile(r"^\s*EC\s*[:\-]\s*(.*)$", re.IGNORECASE)


def translate_effect(text):
    if text is None:
        return None
    plant, end_user, current = [], [], None
    for line in str(text).splitlines():
        ic, ec = _IC_RE.match(line), _EC_RE.match(line)
        if ic:
            current = plant
            line = ic.group(1)
        elif ec:
            current = end_user
            line = ec.group(1)
        elif current is None:
            current = end_user  # leading unlabeled text = product-level effect
        if line.strip():
            current.append(line.strip())
    if not plant and not end_user:
        return text
    return "Your Plant:\n" + "\n".join(plant) + "\nEnd User:\n" + "\n".join(end_user)
