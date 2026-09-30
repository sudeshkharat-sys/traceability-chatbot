"""
PFMEA Assistant Service
Wraps app.pfmea_engine.run_pipeline (the AI Severity/Detection review
pipeline, ported in from the standalone pfmea_ai/ prototype - that folder
is kept as-is for CLI-only testing, this is the real integration used by
the PFMEA Assistant card) for use behind a request/response API: takes an
uploaded workbook's bytes in, returns per-row card data plus the
annotated workbook's bytes back out, with no file paths the caller has to
manage themselves.

Analysis runs as a background job rather than one long blocking request:
start_analysis() kicks off a worker thread and returns a token immediately;
the frontend polls get_progress(token) for a live row counter, then calls
get_result(token) once it's done. This is what lets the UI show real
progress instead of just a spinner, and lets Cancel actually stop new rows
from starting (cancel_run() flips an Event the pipeline checks between
rows) without needing to hold the HTTP connection open the whole time.
"""

import logging
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from app.pfmea_engine.run_pipeline import run_pipeline
from app.pfmea_engine.layouts.ap import action_priority
from app.pfmea_engine.layouts.convert import convert_workbook_to_nashik
from app.pfmea_engine.layouts import LayoutMismatch, available_layouts, detect_layout, get_layout
from app.pfmea_engine.step2_normalize import normalize_sheet

logger = logging.getLogger(__name__)

# In-memory store of the most recently generated output workbook per
# analysis run, keyed by a random token handed back to the frontend so it
# can fetch the formatted .xlsx separately from the JSON card data (the
# JSON response would otherwise have to carry the whole binary workbook
# inline). Fine for the current single-process testing/demo phase; a real
# multi-worker deployment would need this moved to shared storage (disk/S3)
# instead of a process-local dict.
_download_cache: dict[str, bytes] = {}

# In-memory run state, keyed by the token start_analysis() returns. Same
# "fine for single-process now, move to shared storage for multi-worker"
# caveat as _download_cache above.
_run_state: dict[str, dict] = {}
_run_lock = threading.Lock()

# Same starting-point $/1K rates as the pfmea_ai/ Streamlit prototype's
# "Advanced options" panel - NOT read from Azure (its API reports tokens
# used, never a dollar figure), so treat the resulting cost as an estimate
# to sanity-check spend, not an invoice.
_DEFAULT_PRICE_PER_1K_INPUT = 0.00015
_DEFAULT_PRICE_PER_1K_OUTPUT = 0.0006


def list_sheet_names(file_bytes: bytes) -> list[str]:
    """Sheet names in the uploaded workbook, so the frontend can offer a
    sheet picker before running the (LLM-cost-incurring) analysis.

    Writes to a real TemporaryDirectory rather than NamedTemporaryFile:
    NamedTemporaryFile keeps its own handle open on the file for as long as
    the `with` block runs, and Windows (unlike Linux) refuses to let
    openpyxl open that same path a second time while that handle is still
    held - this is exactly what caused the "[Errno 13] Permission denied"
    crash on a Windows deployment. A TemporaryDirectory only holds the
    directory open, not the file inside it, so openpyxl can open the file
    freely on every OS."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "input.xlsx"
        tmp_path.write_bytes(file_bytes)
        wb = load_workbook(tmp_path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        return sheet_names


def inspect_workbook(file_bytes: bytes) -> dict:
    """Sheet names plus the sheet layout detected for each (Nashik AIAG-VDA,
    Chakan RPN, ... see app.pfmea_engine.layouts), so the UI can show what
    each tab was recognized as and offer a manual override. Needs a normal
    (non read-only) load - detection reads merged cells. `layout` is None for
    tabs nothing recognizes (cover pages, process flow, Control Plans)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "input.xlsx"
        tmp_path.write_bytes(file_bytes)
        wb = load_workbook(tmp_path, data_only=True)
        try:
            sheets = []
            for ws in wb.worksheets:
                layout_id = detect_layout(ws)
                sheets.append({"name": ws.title, "layout": layout_id})
            return {
                "sheets": [s["name"] for s in sheets],
                "sheet_layouts": {s["name"]: s["layout"] for s in sheets},
                "layouts": available_layouts(),
            }
        finally:
            wb.close()


# Converted workbooks waiting for the user's confirm-then-run, by token.
_converted_cache: dict[str, bytes] = {}

_PREVIEW_FIELDS = [
    ("step", "2. Process Step Station No. and Name of\nFocus Element"),
    ("severity", "Severity (S) of FE\n"),
    ("mode", "2. Failure Mode (FM) of the\nFocus Element"),
    ("cause", "3. Failure Cause (FC) of the Work Element"),
    ("prevention", "Current Prevention Control (PC) of FC"),
    ("occurrence", "Occurrence (O) of FC"),
    ("detection_ctrl", "Current Detection Controls (DC) of FC or FM"),
    ("detection", "Detection (D) of FC/FM"),
]
_EFFECT_KEY = "1. Failure Effects (FE) to the Next Higher Level Element and/or End User"


def convert_to_nashik(file_bytes: bytes, layout: str = "auto") -> dict:
    """Convert every non-Nashik PFMEA sheet to Nashik format WITHOUT running
    any AI, and return a before/after preview so the user can confirm it
    looks right before spending LLM calls. The converted workbook is cached
    under convert_token: pass it to /analyze to run on it, or fetch it with
    get_converted() to open in Excel."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        src = Path(tmp_dir) / "input.xlsx"
        dst = Path(tmp_dir) / "converted.xlsx"
        src.write_bytes(file_bytes)
        info: list = []
        if layout not in ("auto", "", None):
            get_layout(layout)
        converted = convert_workbook_to_nashik(src, dst, layout=layout, log=logger.info, info_out=info)
        if not converted:
            return {"converted": False, "sheets": []}
        token = uuid.uuid4().hex
        _converted_cache[token] = dst.read_bytes()
    sheets = []
    for item in info:
        rows = []
        for rec in item["records"]:
            row = {"source_row": (rec.get("_source_rows") or [None])[0],
                   "effect_before": rec.get("_raw_effect")}
            for key, field in _PREVIEW_FIELDS:
                row[key] = next((v for k, v in rec.items() if isinstance(k, tuple) and k[1] == field), None)
            if rec.get("_op_no") is not None and row["step"] is not None:
                row["step"] = f"{rec['_op_no']} - {row['step']}"
            row["action_priority"] = action_priority(row["severity"], row["occurrence"], row["detection"])
            row["effect_after"] = next((v for k, v in rec.items() if isinstance(k, tuple) and k[1] == _EFFECT_KEY), None)
            rows.append(row)
        sheets.append({"name": item["title"], "from_label": item["label"], "rows": rows})
    return {"converted": True, "convert_token": token, "sheets": sheets}


def get_converted(token: str) -> Optional[bytes]:
    return _converted_cache.get(token)


def _count_total_rows(source_path: Path, sheet_names: Optional[list[str]], layout: str = "auto") -> int:
    """How many Failure Mode entries the run will score, across every
    requested sheet - computed with the same normalize_sheet() the real
    pipeline uses (so it's the true count, not raw Excel rows), just
    without any LLM calls, so this is free to run up front for the
    progress bar's denominator.

    Not read_only=True - normalize_sheet() needs ws.merged_cells, which
    openpyxl's read-only worksheet mode doesn't support at all
    (AttributeError, not just slower) - only load_workbook's normal mode
    exposes it."""
    wb = load_workbook(source_path, data_only=True)
    try:
        names = sheet_names if sheet_names else wb.sheetnames
        total = 0
        for name in names:
            if name not in wb.sheetnames:
                continue
            _columns, records = normalize_sheet(wb[name], layout)
            total += len(records)
        return total
    finally:
        wb.close()


def start_analysis(
    file_bytes: bytes,
    sheet_names: Optional[list[str]] = None,
    repeat: int = 3,
    merge_mode: bool = True,
    layout: str = "auto",
) -> str:
    """Kick off the AI review pipeline in a background thread and return a
    token immediately - the caller polls get_progress(token) for live
    status and get_result(token) once it's done, instead of blocking on
    one long request for the whole run."""
    tmp_dir = tempfile.mkdtemp()
    source_path = Path(tmp_dir) / "input.xlsx"
    source_path.write_bytes(file_bytes)
    output_path = Path(tmp_dir) / "output.xlsx"

    if layout not in ("auto", "", None):
        get_layout(layout)  # raises LayoutMismatch for an unknown id
    total_rows = _count_total_rows(source_path, sheet_names, layout)
    if total_rows == 0:
        detected = inspect_workbook(file_bytes)["sheet_layouts"]
        summary = ", ".join(f"'{n}': {l or 'not recognized'}" for n, l in detected.items())
        raise LayoutMismatch(
            "No failure-mode rows were found in the selected sheet(s). "
            f"Selected format: {layout or 'auto'}. Detected per sheet - {summary}. "
            "Check that this is a PFMEA sheet (not a Control Plan / process flow) "
            "and that the plant format matches."
        )

    token = uuid.uuid4().hex
    cancel_event = threading.Event()
    state = {
        "status": "running",  # running | done | cancelled | error
        "completed_rows": 0,
        "total_rows": total_rows,
        "current_sheet": None,
        # Which row is actively being scored right now (set as soon as its
        # LLM call starts, not when it finishes) - completed_rows alone can
        # sit unchanged for the whole duration of a slow/first row, which
        # looked indistinguishable from a hang. See run_pipeline()'s
        # row_started_callback docstring.
        "current_failure_mode": None,
        "result": None,
        "error": None,
        "cancel_event": cancel_event,
    }
    with _run_lock:
        _run_state[token] = state

    def worker():
        # done-so-far per sheet, so a per-sheet callback count can be
        # turned into a running total across every sheet in the run.
        done_per_sheet: dict[str, int] = {}

        def progress_callback(sheet_name, done_in_sheet, _total_in_sheet):
            with _run_lock:
                delta = done_in_sheet - done_per_sheet.get(sheet_name, 0)
                if delta > 0:
                    state["completed_rows"] += delta
                    done_per_sheet[sheet_name] = done_in_sheet
                state["current_sheet"] = sheet_name

        def row_started_callback(sheet_name, failure_mode):
            with _run_lock:
                state["current_sheet"] = sheet_name
                state["current_failure_mode"] = failure_mode

        try:
            all_rows: dict[str, list] = {}
            usage_rows: list[dict] = []
            run_pipeline(
                source_path,
                sheet_names=sheet_names,
                repeat=repeat,
                output_path=output_path,
                merge_mode=merge_mode,
                layout=layout,
                log=logger.info,
                all_rows_out=all_rows,
                usage_rows=usage_rows,
                price_per_1k_input=_DEFAULT_PRICE_PER_1K_INPUT,
                price_per_1k_output=_DEFAULT_PRICE_PER_1K_OUTPUT,
                cancel_check=cancel_event.is_set,
                progress_callback=progress_callback,
                row_started_callback=row_started_callback,
            )

            download_token = uuid.uuid4().hex
            _download_cache[download_token] = output_path.read_bytes()

            usage = {
                "rows": usage_rows,
                "total_input_tokens": sum(r["input_tokens"] for r in usage_rows),
                "total_output_tokens": sum(r["output_tokens"] for r in usage_rows),
                "total_tokens": sum(r["total_tokens"] for r in usage_rows),
                "total_cost_usd": sum(
                    r["cost_usd"] for r in usage_rows if r.get("cost_usd") is not None
                ) if usage_rows else 0.0,
            }

            with _run_lock:
                state["result"] = {
                    "sheets": all_rows,
                    "download_token": download_token,
                    "usage": usage,
                    "cancelled": cancel_event.is_set(),
                }
                state["status"] = "cancelled" if cancel_event.is_set() else "done"
        except Exception as e:
            logger.exception("PFMEA analysis failed")
            with _run_lock:
                state["status"] = "error"
                state["error"] = str(e)

    threading.Thread(target=worker, daemon=True).start()
    return token


def get_progress(token: str) -> Optional[dict]:
    """Live status for a run started with start_analysis() - polled by the
    frontend while it's running. None if the token is unknown/expired."""
    with _run_lock:
        state = _run_state.get(token)
        if state is None:
            return None
        return {
            "status": state["status"],
            "completed_rows": state["completed_rows"],
            "total_rows": state["total_rows"],
            "current_sheet": state["current_sheet"],
            "current_failure_mode": state["current_failure_mode"],
            "error": state["error"],
        }


def get_result(token: str) -> Optional[dict]:
    """The finished {"sheets", "download_token", "usage", "cancelled"}
    payload, once status is "done" or "cancelled" - None while still
    running or if the token is unknown."""
    with _run_lock:
        state = _run_state.get(token)
        return state["result"] if state else None


def cancel_run(token: str) -> bool:
    """Stop new rows from starting on an in-progress run - rows already
    in flight still finish (see run_pipeline's cancel_check docs). Returns
    False if the token is unknown."""
    with _run_lock:
        state = _run_state.get(token)
        if state is None:
            return False
        state["cancel_event"].set()
        return True


def get_download(token: str) -> Optional[bytes]:
    """The annotated workbook produced by a previous analysis run, or None
    if the token is unknown/expired (process restarted, or was never
    issued)."""
    return _download_cache.get(token)
