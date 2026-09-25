"""
PFMEA Assistant Service
Wraps app.pfmea_engine.run_pipeline (the AI Severity/Detection review
pipeline, ported in from the standalone pfmea_ai/ prototype - that folder
is kept as-is for CLI-only testing, this is the real integration used by
the PFMEA Assistant card) for use behind a request/response API: takes an
uploaded workbook's bytes in, returns per-row card data plus the
annotated workbook's bytes back out, with no file paths the caller has to
manage themselves.
"""

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from app.pfmea_engine.run_pipeline import run_pipeline

logger = logging.getLogger(__name__)

# In-memory store of the most recently generated output workbook per
# analysis run, keyed by a random token handed back to the frontend so it
# can fetch the formatted .xlsx separately from the JSON card data (the
# JSON response would otherwise have to carry the whole binary workbook
# inline). Fine for the current single-process testing/demo phase; a real
# multi-worker deployment would need this moved to shared storage (disk/S3)
# instead of a process-local dict.
_download_cache: dict[str, bytes] = {}


def list_sheet_names(file_bytes: bytes) -> list[str]:
    """Sheet names in the uploaded workbook, so the frontend can offer a
    sheet picker before running the (LLM-cost-incurring) analysis."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        wb = load_workbook(tmp.name, read_only=True)
        return wb.sheetnames


def analyze_workbook(
    file_bytes: bytes,
    sheet_names: Optional[list[str]] = None,
    repeat: int = 3,
    merge_mode: bool = True,
) -> dict:
    """Run the PFMEA AI review pipeline on an uploaded workbook.

    Returns {"sheets": {sheet_name: [row, ...]}, "download_token": str} -
    "sheets" is what the PFMEA Assistant screen renders as review cards,
    one per Failure Mode row (each row dict has failure_mode,
    plant_recorded_severity, ai_suggested_severity, ai_reasoning,
    ai_suggested_detection, ai_recommended_action, etc. - see
    step5_severity_llm.py's score_entries() for the full per-row shape).
    "download_token" is passed to get_download() to retrieve the same
    annotated workbook as a downloadable .xlsx.

    merge_mode=True matches the reviewed/tested BLANK-TEST output shape
    (A/B sub-mode values folded directly into Severity/Detection/
    Prevention) - the alternative (merge_mode=False) keeps a separate
    worst-case row-level value plus a Sub-modes column instead."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = Path(tmp_dir) / "input.xlsx"
        source_path.write_bytes(file_bytes)
        output_path = Path(tmp_dir) / "output.xlsx"

        all_rows: dict[str, list] = {}
        run_pipeline(
            source_path,
            sheet_names=sheet_names,
            repeat=repeat,
            output_path=output_path,
            merge_mode=merge_mode,
            log=logger.info,
            all_rows_out=all_rows,
        )

        output_bytes = output_path.read_bytes()

    token = uuid.uuid4().hex
    _download_cache[token] = output_bytes

    return {"sheets": all_rows, "download_token": token}


def get_download(token: str) -> Optional[bytes]:
    """The annotated workbook produced by a previous analyze_workbook()
    call, or None if the token is unknown/expired (process restarted,
    or was never issued)."""
    return _download_cache.get(token)
