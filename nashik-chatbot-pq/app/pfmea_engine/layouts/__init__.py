"""Sheet-layout registry.

Each plant/format gets ONE module in this package exposing:
    LAYOUT_ID, LABEL, detect(ws) -> bool, header_row(ws) -> int|None,
    normalize(ws) -> (columns, records)
where `records` use the canonical (group, field) keys the shared pipeline
(scoring, prompts, write-back) consumes. To support a new sheet type: add a
module here, import it below, append it to LAYOUTS. Nothing else in the
pipeline should need to know which plant a sheet came from.
"""

from app.pfmea_engine.layouts import chakan_rpn, nashik_vda

# Order = detection priority. Layouts must not overlap: the first whose
# detect() matches wins.
LAYOUTS = [chakan_rpn, nashik_vda]
_BY_ID = {m.LAYOUT_ID: m for m in LAYOUTS}
DEFAULT_LAYOUT_ID = nashik_vda.LAYOUT_ID  # fallback: original behavior


class LayoutMismatch(ValueError):
    pass


def available_layouts():
    return [{"id": m.LAYOUT_ID, "label": m.LABEL, "short_label": getattr(m, "SHORT_LABEL", m.LABEL)} for m in LAYOUTS]


def detect_layout(ws):
    """Layout id for this sheet, or None if nothing recognizes it (e.g. a
    process-flow or cover tab)."""
    for m in LAYOUTS:
        if m.detect(ws):
            return m.LAYOUT_ID
    return None


def get_layout(layout_id):
    if layout_id not in _BY_ID:
        raise LayoutMismatch(f"Unknown sheet layout '{layout_id}'. Available: {sorted(_BY_ID)}")
    return _BY_ID[layout_id]


def normalize_with_layout(ws, layout="auto"):
    """layout="auto": detect per sheet, falling back to the Nashik reader when
    nothing matches (unchanged historical behavior). An explicit id forces
    that reader; a sheet it doesn't fit simply yields no records."""
    if layout in (None, "", "auto"):
        module = _BY_ID.get(detect_layout(ws)) or _BY_ID[DEFAULT_LAYOUT_ID]
    else:
        module = get_layout(layout)
    return module.normalize(ws)


def find_header_row(ws):
    """Header row of whichever layout matches (used by the write-back step)."""
    for m in LAYOUTS:
        row = m.header_row(ws)
        if row is not None:
            return row
    return None
