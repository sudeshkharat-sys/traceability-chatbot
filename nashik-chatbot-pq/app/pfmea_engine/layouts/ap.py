"""AIAG-VDA Action Priority (AP) - common table for DFMEA and PFMEA.

Transcribed from "Table AP - Action Priority for DFMEA and PFMEA" (AIAG & VDA
FMEA Handbook, 1st ed. 2019; pp. 116-117 of the handbook copy in pfmea_ai/).
Rows = Severity group, columns = Occurrence group, each cell = H/M/L for the
Detection groups 7-10, 5-6, 2-4, 1.
"""

_D_GROUPS = ((7, 10), (5, 6), (2, 4), (1, 1))

# (s_lo, s_hi): [((o_lo, o_hi), "HHHH"-style string per D group), ...]
_TABLE = [
    ((9, 10), [((8, 10), "HHHH"), ((6, 7), "HHHH"), ((4, 5), "HHHM"), ((2, 3), "HMLL"), ((1, 1), "LLLL")]),
    ((7, 8), [((8, 10), "HHHH"), ((6, 7), "HHHM"), ((4, 5), "HMMM"), ((2, 3), "MMLL"), ((1, 1), "LLLL")]),
    ((4, 6), [((8, 10), "HHMM"), ((6, 7), "MMML"), ((4, 5), "MLLL"), ((2, 3), "LLLL"), ((1, 1), "LLLL")]),
    ((2, 3), [((8, 10), "MMLL"), ((6, 7), "LLLL"), ((4, 5), "LLLL"), ((2, 3), "LLLL"), ((1, 1), "LLLL")]),
    ((1, 1), [((1, 10), "LLLL")]),
]


def _to_rating(value):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 10 else None


def action_priority(severity, occurrence, detection):
    """'H' / 'M' / 'L', or None if any rating is missing / not 1-10."""
    s, o, d = _to_rating(severity), _to_rating(occurrence), _to_rating(detection)
    if None in (s, o, d):
        return None
    for (s_lo, s_hi), o_rows in _TABLE:
        if s_lo <= s <= s_hi:
            for (o_lo, o_hi), cells in o_rows:
                if o_lo <= o <= o_hi:
                    for (d_lo, d_hi), ap in zip(_D_GROUPS, cells):
                        if d_lo <= d <= d_hi:
                            return ap
    return None
