"""
PFMEA Assistant API Routes
Upload a PFMEA Excel sheet, get back AI Severity/Detection review cards
plus a downloadable annotated workbook.
"""

import asyncio
import logging
import threading
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
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
        sheet_names = get_service().list_sheet_names(file_bytes)
        return {"sheets": sheet_names}
    except Exception as e:
        logger.exception("PFMEA sheet listing failed")
        raise HTTPException(status_code=400, detail=f"Could not read workbook: {e}")


@router.post("/analyze")
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    sheet_names: Optional[str] = Form(None),
    repeat: int = Form(3),
):
    """Run the AI review pipeline on the uploaded workbook.

    sheet_names is a comma-separated list of sheet names to process (blank
    = every sheet). repeat is how many times each row is independently
    scored by the LLM for stability (see run_pipeline's own docs - keep at
    3, it's cheap insurance against single-call sampling variance).

    The pipeline itself runs in a worker thread (analyze_workbook is
    synchronous and can take minutes on a full sheet) while this coroutine
    polls request.is_disconnected() alongside it - if the frontend's
    Cancel button aborts the request, that's detected here and flipped
    into a threading.Event the pipeline checks between rows/sheets, so an
    abandoned run stops spending LLM calls instead of running to
    completion for a response nobody's waiting for."""
    try:
        file_bytes = await file.read()
        requested_sheets = (
            [s.strip() for s in sheet_names.split(",") if s.strip()]
            if sheet_names
            else None
        )

        cancel_event = threading.Event()

        async def watch_for_disconnect():
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    cancel_event.set()
                    return
                await asyncio.sleep(1)

        pipeline_task = asyncio.create_task(
            asyncio.to_thread(
                get_service().analyze_workbook,
                file_bytes,
                sheet_names=requested_sheets,
                repeat=repeat,
                cancel_check=cancel_event.is_set,
            )
        )
        watcher_task = asyncio.create_task(watch_for_disconnect())

        try:
            done, _ = await asyncio.wait(
                {pipeline_task, watcher_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if pipeline_task not in done:
                # Client gone - let already-in-flight rows wind down (bounded
                # by max_concurrent_rows) instead of abandoning the thread.
                cancel_event.set()
                await pipeline_task
        finally:
            watcher_task.cancel()

        return pipeline_task.result()
    except Exception as e:
        logger.exception("PFMEA analysis failed")
        raise HTTPException(status_code=500, detail=f"PFMEA analysis failed: {e}")


@router.get("/download/{token}")
async def download(token: str):
    """The annotated .xlsx produced by a previous /analyze call."""
    output_bytes = get_service().get_download(token)
    if output_bytes is None:
        raise HTTPException(status_code=404, detail="Download token not found or expired")
    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pfmea_with_suggestions.xlsx"},
    )
