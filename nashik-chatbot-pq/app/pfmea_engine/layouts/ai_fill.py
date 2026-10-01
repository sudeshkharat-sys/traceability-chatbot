"""AI gap-fill for the Nashik converter.

The older plant forms (e.g. Chakan RPN) have no Process Item, Process Work
Element (6M) or the three Function columns that the Nashik AIAG-VDA form
requires, so a straight column mapping leaves them blank. This module asks
the LLM to propose those values *from the sheet's own text* (step, step
function, failure modes, causes, controls), so the converted sheet is
complete instead of half empty.

Only descriptive text columns are generated. Scores (S/O/D), controls and
Action Priority are never invented. Every generated cell is flagged so the
writer can colour it and the reviewer can see what is AI-proposed.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Nashik column numbers the AI may fill (only when the plant left them blank).
COL_PROCESS_ITEM = 1
COL_WORK_ELEMENT = 5
COL_FN_ITEM = 7
COL_FN_STEP = 9
COL_FN_WORK_ELEMENT = 11

_STEP_KEY = "2. Process Step Station No. and Name of\nFocus Element"
_FN_STEP_KEY = "2. Function of the Process Step and Product Characteristic\n(Quantitative value is optional)"
_MODE_KEY = "2. Failure Mode (FM) of the\nFocus Element"
_CAUSE_KEY = "3. Failure Cause (FC) of the Work Element"
_PREVENTION_KEY = "Current Prevention Control (PC) of FC"
_DETECTION_KEY = "Current Detection Controls (DC) of FC or FM"

_CHUNK = 20      # causes per LLM call
_WORKERS = 4

_SYSTEM = (
    "You are an automotive process-FMEA engineer (AIAG-VDA). You complete blank "
    "columns of a PFMEA that is being migrated from an older plant format. "
    "Use ONLY what the supplied rows imply; be concise and concrete (one short "
    "sentence or phrase per cell, no marketing language). Never invent part "
    "numbers, values or standards. Reply with a single JSON object and nothing else."
)


def _get(record, key):
    for k, v in record.items():
        if isinstance(k, tuple) and k[1] == key:
            return v
    return None


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _clean(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _json_call(llm, prompt):
    from app.pfmea_engine.step5_severity_llm import call_llm
    return call_llm(llm, prompt)


def _sheet_prompt(info, steps):
    lines = "\n".join(f"- {s['step']}" + (f" -> {s['fn']}" if s["fn"] else "") for s in steps[:40])
    known = info.get("aggregatepartdescrptn") or info.get("subject") or info.get("partnameprocess") or ""
    return (
        f"{_SYSTEM}\n\nProcess steps of this PFMEA (step -> its function, if given):\n{lines}\n"
        f"Part / process hint from the sheet header: {known or 'none'}\n\n"
        "Return JSON: {\"process_item\": <name of the system / subsystem / process this PFMEA covers, "
        "short>, \"function_of_process_item\": <what that process item must achieve overall, one sentence>}"
    )


def _step_prompt(step, fn, process_item, rows):
    body = "\n".join(
        f"{r['i']}. mode: {r['mode']} | cause: {r['cause']}"
        + (f" | prevention: {r['prev']}" if r["prev"] else "")
        + (f" | detection: {r['det']}" if r["det"] else "")
        for r in rows
    )
    return (
        f"{_SYSTEM}\n\nProcess item: {process_item or 'n/a'}\nProcess step: {step}\n"
        f"Function of the step: {fn or '(blank - please propose)'}\n\nFailure causes:\n{body}\n\n"
        "For each cause give the Process Work Element in 6M form \"<Category>: <specific element>\" where "
        "Category is one of Man, Machine, Method, Material, Measurement, Environment (e.g. "
        "\"Machine: Barcode scanner\", \"Man: Operator\"), and the function of that work element incl. the "
        "process characteristic it controls (one short sentence).\n"
        "Return JSON: {\"function_of_step\": <one sentence>, \"causes\": [{\"i\": <number>, "
        "\"work_element\": <str>, \"function\": <str>}, ...]}"
    )


def fill_blanks(records, info, llm, log=print):
    """Fill blank Process Item / Work Element / Function cells on `records` in
    place (record["_ai"] = {nashik_col: text}). Returns
    {"filled": <cells>, "failed": <calls>, "error": <first error or None>}."""
    status = {"filled": 0, "failed": 0, "error": None}
    if not records:
        return status
    info = info or {}

    def note_failure(exc):
        status["failed"] += 1
        status["error"] = status["error"] or str(exc)
        logger.warning("AI gap-fill call failed: %s", exc)

    # Group rows by step, preserving order.
    groups = {}
    for idx, rec in enumerate(records):
        groups.setdefault(_clean(_get(rec, _STEP_KEY)) or "", []).append(idx)

    steps = [{"step": s, "fn": _clean(_get(records[ix[0]], _FN_STEP_KEY))} for s, ix in groups.items() if s]

    # 1) sheet level: Process Item + its function
    process_item = _clean(info.get("aggregatepartdescrptn"))
    fn_item = None
    try:
        data = _json_call(llm, _sheet_prompt(info, steps))
        process_item = process_item or _clean(data.get("process_item"))
        fn_item = _clean(data.get("function_of_process_item"))
    except Exception as exc:  # noqa: BLE001 - never fail the whole conversion on AI
        note_failure(exc)

    for rec in records:
        ai = rec.setdefault("_ai", {})
        if process_item and not info.get("aggregatepartdescrptn"):
            ai[COL_PROCESS_ITEM] = process_item
        if fn_item:
            ai[COL_FN_ITEM] = fn_item

    # 2) per step (chunked): Work Element, its function, step function
    jobs = []
    for step, idxs in groups.items():
        for n in range(0, len(idxs), _CHUNK):
            jobs.append((step, idxs[n:n + _CHUNK]))

    def run(job):
        step, idxs = job
        fn = _clean(_get(records[idxs[0]], _FN_STEP_KEY))
        rows = [{
            "i": n, "mode": _clean(_get(records[ix], _MODE_KEY)) or "", "cause": _clean(_get(records[ix], _CAUSE_KEY)) or "",
            "prev": _clean(_get(records[ix], _PREVENTION_KEY)), "det": _clean(_get(records[ix], _DETECTION_KEY)),
        } for n, ix in enumerate(idxs)]
        return job, _json_call(llm, _step_prompt(step, fn, process_item, rows))

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = [pool.submit(run, j) for j in jobs]
        for fut in futures:
            try:
                (step, idxs), data = fut.result()
            except Exception as exc:  # noqa: BLE001
                note_failure(exc)
                continue
            fn_step = _clean(data.get("function_of_step"))
            for item in data.get("causes") or []:
                try:
                    ix = idxs[int(item["i"])]
                except (KeyError, ValueError, TypeError, IndexError):
                    continue
                ai = records[ix].setdefault("_ai", {})
                if _clean(item.get("work_element")):
                    ai[COL_WORK_ELEMENT] = _clean(item["work_element"])
                if _clean(item.get("function")):
                    ai[COL_FN_WORK_ELEMENT] = _clean(item["function"])
            if fn_step:
                for ix in idxs:
                    if _blank(_get(records[ix], _FN_STEP_KEY)):
                        records[ix].setdefault("_ai", {})[COL_FN_STEP] = fn_step

    status["filled"] = sum(len(r.get("_ai", {})) for r in records)
    log(f"AI gap-fill: {status['filled']} blank cells proposed"
        + (f" ({status['failed']} call(s) failed: {status['error']})" if status["failed"] else ""))
    return status
