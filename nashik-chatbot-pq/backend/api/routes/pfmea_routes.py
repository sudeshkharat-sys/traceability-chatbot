"""
PFMEA Assistant API Routes
Upload a PFMEA Excel sheet, get back AI Severity/Detection review cards
plus a downloadable annotated workbook.
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
        sheet_names = get_service().list_sheet_names(file_bytes)
        return {"sheets": sheet_names}
    except Exception as e:
        logger.exception("PFMEA sheet listing failed")
        raise HTTPException(status_code=400, detail=f"Could not read workbook: {e}")


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet_names: Optional[str] = Form(None),
    repeat: int = Form(3),
):
    """Run the AI review pipeline on the uploaded workbook.

    sheet_names is a comma-separated list of sheet names to process (blank
    = every sheet). repeat is how many times each row is independently
    scored by the LLM for stability (see run_pipeline's own docs - keep at
    3, it's cheap insurance against single-call sampling variance)."""
    try:
        file_bytes = await file.read()
        requested_sheets = (
            [s.strip() for s in sheet_names.split(",") if s.strip()]
            if sheet_names
            else None
        )
        result = get_service().analyze_workbook(
            file_bytes, sheet_names=requested_sheets, repeat=repeat
        )
        return result
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
