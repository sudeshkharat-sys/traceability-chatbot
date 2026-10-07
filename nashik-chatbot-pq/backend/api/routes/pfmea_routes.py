"""
PFMEA APEX Advisor API Routes
Upload a PFMEA Excel sheet, get back AI Severity/Detection review cards
plus a downloadable annotated workbook.

/analyze starts the review as a background job and returns a token right
away rather than blocking on the whole run - the frontend polls /progress
for a live row counter, then reads /result once it's done. This is what
lets the UI show real progress and lets Cancel actually stop new rows from
being scored instead of just abandoning an open HTTP request.
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pfmea"])

_service = None


def get_service():
    global _service
    if _service is None:
        from backend.services import pfmea_service
        _service = pfmea_service
    return _service


@router.post("/sheets")
async def list_sheets(file: UploadFile = File(...)):
    """Sheet names in an uploaded workbook, for a sheet picker - run before
    /analyze so the user can choose which sheet(s) to spend LLM calls on."""
    try:
        file_bytes = await file.read()
        # "sheets" stays a plain list of names (existing clients); the
        # per-sheet detected layout and the selectable formats ride along.
        return get_service().inspect_workbook(file_bytes)
    except Exception as e:
        logger.exception("PFMEA sheet listing failed")
        raise HTTPException(status_code=400, detail=f"Could not read workbook: {e}")


@router.post("/convert")
async def convert(file: UploadFile = File(...), layout: str = Form("auto")):
    """Convert non-Nashik sheets to Nashik format (no AI calls) and return a
    before/after preview. Confirm it, then call /analyze with convert_token."""
    try:
        return get_service().convert_to_nashik(await file.read(), layout=layout)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("PFMEA conversion failed")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")


@router.get("/converted/{token}")
async def converted(token: str):
    """The converted Nashik-format .xlsx, to open in Excel and check."""
    data = get_service().get_converted(token)
    if data is None:
        raise HTTPException(status_code=404, detail="Converted file not found or expired")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pfmea_nashik_format.xlsx"},
    )


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet_names: Optional[str] = Form(None),
    repeat: int = Form(3),
    layout: str = Form("auto"),
    convert_token: Optional[str] = Form(None),
):
    """Start the AI review pipeline in the background and return a token.

    sheet_names is a comma-separated list of sheet names to process (blank
    = every sheet). repeat is how many times each row is independently
    scored by the LLM for stability (see run_pipeline's own docs - default
    3 is cheap insurance against single-call sampling variance; the
    frontend offers 1-5 as a cost-vs-confidence tradeoff the reviewer
    picks). Restricted to 1-5 here - not a hard technical limit, just a
    sanity cap so a stray value can't multiply LLM spend unexpectedly.

    Poll GET /pfmea/progress/{token} for live status, then GET
    /pfmea/result/{token} once it reports done/cancelled."""
    if not 1 <= repeat <= 5:
        raise HTTPException(status_code=400, detail="repeat must be between 1 and 5")
    try:
        file_bytes = await file.read()
        if convert_token:
            # Run on the converted workbook the user already reviewed.
            file_bytes = get_service().get_converted(convert_token)
            if file_bytes is None:
                raise HTTPException(status_code=400, detail="Converted file expired - convert again")
            layout = "auto"
        requested_sheets = (
            [s.strip() for s in sheet_names.split(",") if s.strip()]
            if sheet_names
            else None
        )
        token = get_service().start_analysis(
            file_bytes, sheet_names=requested_sheets, repeat=repeat, layout=layout
        )
        return {"token": token}
    except HTTPException:
        raise
    except ValueError as e:
        # LayoutMismatch (unknown format / no PFMEA rows found) is the
        # caller's input problem, not a server fault.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("PFMEA analysis failed to start")
        raise HTTPException(status_code=500, detail=f"PFMEA analysis failed to start: {e}")


@router.get("/progress/{token}")
async def progress(token: str):
    """Live {status, completed_rows, total_rows, current_sheet} for a run
    started with /analyze."""
    state = get_service().get_progress(token)
    if state is None:
        raise HTTPException(status_code=404, detail="Run token not found or expired")
    return state


@router.get("/result/{token}")
async def result(token: str):
    """The finished {sheets, download_token, usage, cancelled} payload -
    404 while still running (poll /progress instead) or if the token is
    unknown."""
    progress_state = get_service().get_progress(token)
    if progress_state is None:
        raise HTTPException(status_code=404, detail="Run token not found or expired")
    if progress_state["status"] == "error":
        raise HTTPException(status_code=500, detail=progress_state["error"] or "PFMEA analysis failed")
    if progress_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Still running - poll /progress until done")
    run_result = get_service().get_result(token)
    if run_result is None:
        raise HTTPException(status_code=404, detail="Result not available")
    return run_result


@router.post("/cancel/{token}")
async def cancel(token: str):
    """Stop an in-progress run from starting any new rows - rows already
    in flight still finish (see run_pipeline's cancel_check docs)."""
    ok = get_service().cancel_run(token)
    if not ok:
        raise HTTPException(status_code=404, detail="Run token not found or expired")
    return {"cancelling": True}


@router.get("/download/{token}")
async def download(token: str):
    """The annotated .xlsx produced by a previous analysis run."""
    output_bytes = get_service().get_download(token)
    if output_bytes is None:
        raise HTTPException(status_code=404, detail="Download token not found or expired")
    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pfmea_with_suggestions.xlsx"},
    )
