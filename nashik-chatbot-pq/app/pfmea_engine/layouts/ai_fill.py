"""Gap-fill for the Nashik converter: Process Item, Work Element (6M) and Function
of Work Element and Function of Process Item (Your Plant line only; End User / Ship to Plant stay for the plant).

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

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
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

# Things that are CONTROLS or records, never work elements.
_CONTROL_WORDS = re.compile(
    r"check|audit|training|calibrat|record|buy ?off|inspect|verif|sop\b|instruction|awareness|"
    r"observ|clita|\bpm\b|maintenance|sticker\b.*(torque|daily)|coding|\btest\b|review|approval", re.I)

# Connecting words that never count as "new facts" in the grounding check.
_STOPWORDS = {"with", "that", "this", "from", "into", "onto", "over", "under", "each", "when", "while",
              "which", "their", "there", "than", "then", "also", "only", "used", "using", "ensure",
              "ensures", "proper", "properly", "correct", "correctly", "after", "before", "during",
              "based", "within", "without", "such", "these", "those", "have", "been", "will", "shall"}

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
    meaningful = [w for w in _WORD_RE.findall(text.lower())
                  if not w.isdigit() and len(w) > 3 and w not in _STOPWORDS]
    return bool(meaningful) and all(_stem(w) in src_stems for w in meaningful)


_CACHE_LOCK = threading.Lock()


def _cache_path():
    return Path(os.environ.get("PFMEA_AI_CACHE_FILE") or Path(tempfile.gettempdir()) / "pfmea_ai_fill_cache.json")


def _cache_key(prompt):
    model = os.environ.get("PFMEA_CONVERT_LLM_PROFILE", "gpt5") + os.environ.get("PFMEA_CONVERT_REASONING_EFFORT", "low")
    return hashlib.sha256((model + "\n" + prompt).encode("utf-8")).hexdigest()


def _cache_get(key):
    if os.environ.get("PFMEA_AI_CACHE", "1") == "0":
        return None
    try:
        with _CACHE_LOCK:
            return json.loads(_cache_path().read_text(encoding="utf-8")).get(key)
    except Exception:  # noqa: BLE001 - no/corrupt cache is just a miss
        return None


def _cache_put(key, value):
    if os.environ.get("PFMEA_AI_CACHE", "1") == "0":
        return
    try:
        with _CACHE_LOCK:
            path = _cache_path()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                data = {}
            data[key] = value
            path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:  # noqa: BLE001 - caching must never break a conversion
        pass


def _json_call(llm, prompt, attempts=3):
    """Same prompt (same file, same model settings) -> saved answer, no new AI call.
    Set PFMEA_AI_CACHE=0 to always call the model."""
    key = _cache_key(prompt)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    value = _json_call_uncached(llm, prompt, attempts)
    _cache_put(key, value)
    return value


def _json_call_uncached(llm, prompt, attempts=3):
    """Ask for strict JSON (response_format) and retry when the model's answer
    is not parseable - reasoning models occasionally emit a stray character."""
    from app.pfmea_engine.step5_severity_llm import call_llm
    json_llm = llm
    try:
        json_llm = llm.bind(response_format={"type": "json_object"})
    except Exception:  # noqa: BLE001 - not every client supports binding
        pass
    last = None
    for attempt in range(attempts):
        try:
            return call_llm(json_llm, prompt)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if json_llm is not llm and "json" not in str(exc).lower():
                json_llm = llm  # the endpoint rejected JSON mode: retry plain
    raise last


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


def _step_prompt(step, fns, process_item, items):
    body = "\n".join(
        f"{n}. cause: {it['cause']}" + (f" | category: {it['cat']}" if it["cat"] else " | category: ?")
        + (f" | prevention: {it['prev']}" if it["prev"] else "")
        + (f" | detection: {it['det']}" if it["det"] else "")
        for n, it in enumerate(items)
    )
    return (
        f"{_SYSTEM}\n\nProcess item: {process_item or 'n/a'}\nProcess step: {step}\n"
        f"Requirements / functions of the step: {'; '.join(fns) if fns else 'n/a'}\n\nFailure causes (6M category already assigned by rules; '?' = unknown):\n{body}\n\n"
        "Task: list the work elements this step uses, per 6M category, taken from the CAUSES and the step "
        "(e.g. cause 'Wrong tool used' with control 'Nutrunner...' -> Machine: 'Nutrunner'). Prevention/detection "
        "controls are given only to help you identify equipment: NEVER output a control, check, audit, training, "
        "calibration, record, buy-off or SOP as a work element - those are controls, not work elements. Only "
        "physical equipment/tools (Machine), parts/consumables (Material), the way the work is done (Method), "
        "gauges/instruments (Measurement), conditions (Environment), people (Man). For each category also give "
        "the function of that group in one short phrase from the step function/causes. "
        "Omit a category if nothing in the causes supports it.\n"
        "Also give \"your_plant\": one short sentence saying what this operation achieves in the plant, using "
        "ONLY the step name and its requirements above (no new facts), or null if unclear.\n"
        "Return JSON: {\"elements\": {\"<Category>\": [\"<name>\", ...]}, \"functions\": {\"<Category>\": "
        "[\"<function>\", ...]}, \"your_plant\": <sentence or null>}"
    )


def _sheet_prompt(hint, steps):
    lines = "\n".join(f"- {s['step']}" + (f" -> {s['fn']}" if s["fn"] else "") for s in steps[:40])
    return (
        f"{_SYSTEM}\n\nHeader details from the sheet: {hint or 'none'}\nProcess steps (step -> function):\n{lines}\n\n"
        "Return JSON: {\"process_item\": <short name of the station/process this PFMEA covers, using the header "
        "or step names, or null>}"
    )


def fill_blanks(records, info, llm, log=print):
    """Fill record["_ai"] = {nashik_col: text} in place. `llm=None` runs the
    rule-based part only. Returns {"filled", "failed", "error"}."""
    status = {"filled": 0, "failed": 0, "calls": 0, "error": None, "message": None}
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
    step_reqs = {}
    for s_, ix in groups.items():
        seen = []
        for i_ in ix:
            r_ = _clean(_get(records[i_], _FN_STEP_KEY))
            if r_ and r_ not in seen:
                seen.append(r_)
        step_reqs[s_] = seen
    steps = [{"step": s, "fn": step_fn[s]} for s in groups if s]

    # ---- sheet level: Process Item (Function of Process Item is built per step by the converter, code only) ----
    process_item = _clean(info.get("aggregatepartdescrptn"))
    hint = " ".join(str(v) for v in info.values() if v)
    sheet_src = hint + " " + " ".join(f"{s['step']} {s['fn'] or ''}" for s in steps)
    if llm is not None:
        try:
            data = _json_call(llm, _sheet_prompt(hint, steps))
            if not process_item:
                cand = _clean(data.get("process_item"))
                process_item = cand if grounded(cand, sheet_src) else None
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
        # Names must be grounded in the step and its CAUSES (controls are not a source of work elements).
        src = " ".join([step] + step_reqs[step] + [i["cause"] for i in items])
        src_all = src + " " + " ".join(f"{i['prev'] or ''} {i['det'] or ''}" for i in items)
        found_cats = {i["cat"] for i in items if i["cat"]}
        elements = {c: [] for c in CATEGORIES}
        functions = {c: [] for c in CATEGORIES}
        your_plant = None
        # deterministic: Man -> Operator, only if the text itself says so
        if any(i["cat"] == "Man" for i in items) and re.search(r"operator|associate", src.lower()):
            elements["Man"].append("Operator")
        if llm is not None and items:
            data = _json_call(llm, _step_prompt(step, step_reqs[step], process_item, items))
            for cat, names in (data.get("elements") or {}).items():
                if cat in elements and cat in found_cats:  # category must be evidenced by a cause
                    for n in _as_list(names):
                        if (grounded(n, src_all) and not _CONTROL_WORDS.search(n)
                                and n not in elements[cat]):
                            elements[cat].append(n)
            plant_text = _clean(data.get("your_plant"))
            if plant_text and grounded(plant_text, " ".join([step] + step_reqs[step])):
                your_plant = f"Your Plant:\n{plant_text}"
            for cat, fns in (data.get("functions") or {}).items():
                if cat in functions:
                    functions[cat] += [f for f in _as_list(fns) if grounded(f, src) and f not in functions[cat]]
        # Function block only for categories that actually have elements
        functions = {c: f for c, f in functions.items() if elements.get(c)}
        return idxs, build_block(elements), build_block(functions), your_plant

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
        we_block = fn_block = plant_block = None
        if step in results:
            _i, we_block, fn_block, plant_block = results[step]
        for ix in idxs:
            ai = records[ix].setdefault("_ai", {})
            if process_item and not info.get("aggregatepartdescrptn"):
                ai[COL_PROCESS_ITEM] = process_item
            if we_block:
                ai[COL_WORK_ELEMENT] = we_block
            if fn_block:
                ai[COL_FN_WORK_ELEMENT] = fn_block
            if plant_block:
                ai[COL_FN_ITEM] = plant_block

    status["calls"] = len(steps_with_ids) + (1 if llm is not None else 0)
    if status["failed"]:
        status["message"] = (f"AI could not complete {status['failed']} of {status['calls']} requests "
                             "(unreadable answer); those cells were left empty.")
    status["filled"] = sum(len(r.get("_ai", {})) for r in records)
    log(f"AI gap-fill: {status['filled']} cells proposed"
        + (f" ({status['failed']} call(s) failed: {status['error']})" if status["failed"] else ""))
    return status
