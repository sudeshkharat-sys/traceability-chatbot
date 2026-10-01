"""Gap-fill for the Nashik converter: Process Item, Work Element (6M), Function
of Process Item and Function of Work Element.

The older plant forms (e.g. Chakan RPN) have none of these, so a straight
column mapping leaves them blank. In a real Nashik sheet they are NOT per-row
values:
  * Process Item           - one short name for the whole station
  * Work Element (6M)      - one block per step: "Man :\\n1.Operator\\nMachine :\\n1.Scanner ..."
  * Function of Work Elem. - one block per step, same 6M layout
  * Function of Proc. Item - one block: "Your Plant- ... / End user- ..."
so that is what gets generated here, per step.

Division of labour (so nothing is invented):
  * CODE classifies every failure cause into a 6M category from keywords in
    the plant's own cause text, and builds the blocks.
  * The LLM is only asked to NAME the elements / functions for those
    categories, may answer null, and every answer is dropped unless its words
    (and numbers) appear in that step's own text.
Scores (S/O/D), controls and Action Priority are never touched. Every
generated cell is flagged (record["_ai"]) so the writer can colour it.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

COL_PROCESS_ITEM = 1
COL_WORK_ELEMENT = 5
COL_FN_ITEM = 7
COL_FN_WORK_ELEMENT = 11

_STEP_KEY = "2. Process Step Station No. and Name of\nFocus Element"
_FN_STEP_KEY = "2. Function of the Process Step and Product Characteristic\n(Quantitative value is optional)"
_MODE_KEY = "2. Failure Mode (FM) of the\nFocus Element"
_CAUSE_KEY = "3. Failure Cause (FC) of the Work Element"
_PREVENTION_KEY = "Current Prevention Control (PC) of FC"
_DETECTION_KEY = "Current Detection Controls (DC) of FC or FM"
_EFFECT_KEY = "1. Failure Effects (FE) to the Next Higher Level Element and/or End User"

_WORKERS = 4
_MAX_CAUSES_PER_CALL = 60

# Nashik order and labels (Material is written "Material (Indirect)" on the form).
CATEGORIES = ["Man", "Machine", "Method", "Material (Indirect)", "Measurement", "Environment"]
_CAT_KEYWORDS = [
    # checked in this order against the CAUSE text only
    ("Man", ("operator", "human", "associate", "worker", "fatigue", "negligen", "forget", "forgot",
             "mistake", "careless", "skill", "not followed", "training")),
    ("Measurement", ("gauge", "gage", "measur", "instrument", "inspection tool")),
    ("Machine", ("machine", "tool", "nutrunner", "wrench", "scanner", "printer", "cartri", "equipment",
                 "fixture", "jig", "socket", "bit ", "calibrat", "sensor", "hoist", "conveyor",
                 "pokayoke", "poka-yoke", "program", "software", "device")),
    ("Material (Indirect)", ("part", "biw", "material", "component", "supplier", "incoming", "sticker",
                              "label", "bolt", "screw", "fastener", "defect", "damage")),
    ("Method", ("method", "procedure", "sequence", "sop", "instruction", "setting", "process",
                "standard", "layout", "drawing")),
    ("Environment", ("dust", "temperature", "humid", "lighting", "noise", "weather", "environment", "vibration")),
]

_SYSTEM = (
    "You are an automotive process-FMEA engineer (AIAG-VDA) completing blank columns of a PFMEA migrated from "
    "an older plant format. STRICT RULES: use ONLY what the supplied text clearly states. If unsure, return null "
    "- an empty cell is far better than a guess. Never invent part names, numbers, tools, standards or "
    "specifications; reuse the plant's own wording. Keep every item to a short phrase. "
    "Reply with a single JSON object and nothing else."
)

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _get(record, key):
    for k, v in record.items():
        if isinstance(k, tuple) and k[1] == key:
            return v
    return None


def _clean(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def classify_6m(cause_text):
    """6M category for a failure cause from its own words, or None when no
    keyword matches (then the LLM may classify it, or it stays unplaced)."""
    low = f" {str(cause_text or '').lower()} "
    for category, words in _CAT_KEYWORDS:
        if any(w in low for w in words):
            return category
    return None


def _stem(word):
    return word[:5]


def grounded(text, source):
    """True only if every number and every meaningful word of `text` occurs in
    `source` (word match on the first 5 letters, so plurals/typos still pass)."""
    if not text:
        return False
    src = str(source or "").lower()
    src_stems = {_stem(w) for w in _WORD_RE.findall(src)}
    if any(n not in set(_NUM_RE.findall(src)) for n in _NUM_RE.findall(text)):
        return False
    meaningful = [w for w in _WORD_RE.findall(text.lower()) if not w.isdigit() and len(w) > 3]
    return bool(meaningful) and all(_stem(w) in src_stems for w in meaningful)


def _json_call(llm, prompt):
    from app.pfmea_engine.step5_severity_llm import call_llm
    return call_llm(llm, prompt)


def _as_list(value):
    if isinstance(value, str):
        value = [value]
    return [c for c in (_clean(v) for v in (value or [])) if c]


def build_block(by_category):
    """{category: [items]} -> Nashik block text, in form order; empty
    categories are omitted."""
    parts = []
    for cat in CATEGORIES:
        items = by_category.get(cat) or []
        if items:
            parts.append(f"{cat} :\n" + "\n".join(f"{i}.{t}" for i, t in enumerate(items, 1)))
    return "\n\n".join(parts) or None


def _step_prompt(step, fn, process_item, items):
    body = "\n".join(
        f"{n}. cause: {it['cause']}" + (f" | category: {it['cat']}" if it["cat"] else " | category: ?")
        + (f" | prevention: {it['prev']}" if it["prev"] else "")
        + (f" | detection: {it['det']}" if it["det"] else "")
        for n, it in enumerate(items)
    )
    return (
        f"{_SYSTEM}\n\nProcess item: {process_item or 'n/a'}\nProcess step: {step}\n"
        f"Function of the step: {fn or 'n/a'}\n\nFailure causes (6M category already assigned by rules; '?' = unknown):\n{body}\n\n"
        "Task: list the physical work elements this step uses, per 6M category, ONLY those named or clearly "
        "implied by the causes/controls above (e.g. cause 'Wrong tool used' + control 'Nutrunner...' -> Machine: "
        "'Nutrunner'). For each category also give the function of that group in one short phrase taken from the "
        "step function/causes. Categories: Man, Machine, Method, Material (Indirect), Measurement, Environment. "
        "Omit a category if nothing in the text supports it.\n"
        "Return JSON: {\"elements\": {\"<Category>\": [\"<name>\", ...]}, \"functions\": {\"<Category>\": "
        "[\"<function>\", ...]}}"
    )


def _sheet_prompt(hint, steps):
    lines = "\n".join(f"- {s['step']}" + (f" -> {s['fn']}" if s["fn"] else "") for s in steps[:40])
    return (
        f"{_SYSTEM}\n\nHeader details from the sheet: {hint or 'none'}\nProcess steps (step -> function):\n{lines}\n\n"
        "Return JSON: {\"process_item\": <short name of the station/process this PFMEA covers, using the header "
        "or step names, or null>, \"your_plant\": <what the process item must achieve in the plant, one sentence "
        "taken from the step functions, or null>, \"end_user\": <what it must achieve for the end user, one "
        "sentence, ONLY if stated or obvious from the text, else null>}"
    )


def fill_blanks(records, info, llm, log=print):
    """Fill record["_ai"] = {nashik_col: text} in place. `llm=None` runs the
    rule-based part only. Returns {"filled", "failed", "error"}."""
    status = {"filled": 0, "failed": 0, "error": None}
    if not records:
        return status
    info = info or {}

    def note_failure(exc):
        status["failed"] += 1
        status["error"] = status["error"] or str(exc)
        logger.warning("AI gap-fill call failed: %s", exc)

    groups = {}
    for idx, rec in enumerate(records):
        groups.setdefault(_clean(_get(rec, _STEP_KEY)) or "", []).append(idx)
    step_fn = {s: _clean(_get(records[ix[0]], _FN_STEP_KEY)) for s, ix in groups.items()}
    steps = [{"step": s, "fn": step_fn[s]} for s in groups if s]

    # ---- sheet level: Process Item + Function of Process Item ----------
    process_item = _clean(info.get("aggregatepartdescrptn"))
    fn_item = None
    hint = " ".join(str(v) for v in info.values() if v)
    sheet_src = hint + " " + " ".join(f"{s['step']} {s['fn'] or ''}" for s in steps)
    if llm is not None:
        try:
            data = _json_call(llm, _sheet_prompt(hint, steps))
            if not process_item:
                cand = _clean(data.get("process_item"))
                process_item = cand if grounded(cand, sheet_src) else None
            plant, user = _clean(data.get("your_plant")), _clean(data.get("end_user"))
            plant = plant if grounded(plant, sheet_src) else None
            user = user if grounded(user, sheet_src) else None
            if plant or user:
                fn_item = "\n\n".join(x for x in (f"Your Plant- {plant}" if plant else None,
                                                  f"End user- {user}" if user else None) if x)
        except Exception as exc:  # noqa: BLE001 - AI must never fail the conversion
            note_failure(exc)

    # ---- per step: 6M classification (code) + element/function names (AI) ----
    def work(step):
        idxs = groups[step]
        items = []
        for ix in idxs:
            rec = records[ix]
            cause = _clean(_get(rec, _CAUSE_KEY))
            if cause:
                items.append({"ix": ix, "cause": cause, "cat": classify_6m(cause),
                              "prev": _clean(_get(rec, _PREVENTION_KEY)), "det": _clean(_get(rec, _DETECTION_KEY))})
        items = items[:_MAX_CAUSES_PER_CALL]
        src = " ".join([step, step_fn[step] or ""] + [
            f"{i['cause']} {i['prev'] or ''} {i['det'] or ''}" for i in items])
        elements = {c: [] for c in CATEGORIES}
        functions = {c: [] for c in CATEGORIES}
        # deterministic: Man -> Operator, only if the text itself says so
        if any(i["cat"] == "Man" for i in items) and re.search(r"operator|associate", src.lower()):
            elements["Man"].append("Operator")
        if llm is not None and items:
            data = _json_call(llm, _step_prompt(step, step_fn[step], process_item, items))
            for cat, names in (data.get("elements") or {}).items():
                if cat in elements:
                    for n in _as_list(names):
                        if grounded(n, src) and n not in elements[cat]:
                            elements[cat].append(n)
            for cat, fns in (data.get("functions") or {}).items():
                if cat in functions:
                    functions[cat] += [f for f in _as_list(fns) if grounded(f, src)]
        # Function block only for categories that actually have elements
        functions = {c: f for c, f in functions.items() if elements.get(c)}
        return idxs, build_block(elements), build_block(functions)

    steps_with_ids = [s for s in groups if s]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {s: pool.submit(work, s) for s in steps_with_ids}
    results = {}
    for s, fut in futures.items():
        try:
            results[s] = fut.result()
        except Exception as exc:  # noqa: BLE001
            note_failure(exc)

    for step, idxs in groups.items():
        we_block = fn_block = None
        if step in results:
            _i, we_block, fn_block = results[step]
        for ix in idxs:
            ai = records[ix].setdefault("_ai", {})
            if process_item and not info.get("aggregatepartdescrptn"):
                ai[COL_PROCESS_ITEM] = process_item
            if fn_item:
                ai[COL_FN_ITEM] = fn_item
            if we_block:
                ai[COL_WORK_ELEMENT] = we_block
            if fn_block:
                ai[COL_FN_WORK_ELEMENT] = fn_block

    status["filled"] = sum(len(r.get("_ai", {})) for r in records)
    log(f"AI gap-fill: {status['filled']} cells proposed"
        + (f" ({status['failed']} call(s) failed: {status['error']})" if status["failed"] else ""))
    return status
