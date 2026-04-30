"""
QLense API Routes
Data availability check and Excel upload for QLense agent.

Logic:
  - GET  /qlense/data-status   → tells the frontend which of the 5 data sources
                                  (warranty / rpt / gnovac / rfi / esqa) are already
                                  loaded for this user (reuses Part Labeler tables).
  - POST /qlense/upload         → upload an Excel/CSV file; returns extracted headers
                                  so the frontend can present a column-mapping UI.
  - POST /qlense/confirm-upload → apply the column mapping and load the file into the
                                  correct table (same service as Part Labeler).

If the user already uploaded data via Part Labeler, data-status will show it as
available and no re-upload is needed.
"""

import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["qlense"])

_service = None


def _get_service():
    global _service
    if _service is None:
        from backend.services.part_labeler_service import PartLabelerService
        _service = PartLabelerService()
    return _service


# ── Request schemas ────────────────────────────────────────────────────────────

class QLenseConfirmUploadRequest(BaseModel):
    tempFilePath: str
    mapping: Dict[str, str]
    userId: int
    dataSource: str  # "warranty" | "rpt" | "gnovac" | "rfi" | "esqa"


# ── Endpoints ──────────────────────────────────────────────────────────────────

# ── PDF ingestion state (in-process, single node) ─────────────────────────────
_ingest_state: Dict = {"running": False, "last_result": None, "error": None}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/data-status")
async def qlense_data_status(userId: int = Query(..., description="User ID")):
    """
    Return which of the 5 data sources have rows in the DB for this user.

    Response shape:
    {
      "warranty": {"uploaded": true,  "row_count": 1234},
      "rpt":      {"uploaded": false, "row_count": 0},
      "gnovac":   {"uploaded": true,  "row_count": 567},
      "rfi":      {"uploaded": false, "row_count": 0},
      "esqa":     {"uploaded": false, "row_count": 0},
      "any_uploaded": true
    }
    """
    try:
        status = _get_service().get_data_status(userId)
        status["any_uploaded"] = any(v["uploaded"] for v in status.values())
        return JSONResponse(content=status)
    except Exception as e:
        logger.error(f"QLense data-status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check data status")


@router.post("/upload")
async def qlense_upload(file: UploadFile = File(...)):
    """
    Upload an Excel or CSV file for QLense.
    Returns the temp file path and extracted column headers so the
    frontend can present a column-mapping step before final ingestion.
    """
    try:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)

        safe_name = f"{os.urandom(4).hex()}_{file.filename}"
        file_path = os.path.join(temp_dir, safe_name)
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        headers = _get_service().extract_excel_headers(file_path)
        return {"tempFilePath": file_path, "headers": headers}
    except Exception as e:
        logger.error(f"QLense upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-pdfs")
async def qlense_ingest_pdfs():
    """
    Trigger ingestion of all PDFs in data_qlense/Problem_Solved/ into OpenSearch.
    Runs in a background thread so the request returns immediately.

    - If already running: returns 409
    - On success the PDFs are searchable by the QLense agent Phase 2
    """
    if _ingest_state["running"]:
        raise HTTPException(status_code=409, detail="Ingestion already running")

    def _run():
        _ingest_state["running"] = True
        _ingest_state["error"] = None
        _ingest_state["last_result"] = None
        try:
            # Resolve Problem_Solved directory relative to this file
            routes_dir = Path(__file__).resolve().parent          # routes/
            project_root = routes_dir.parent.parent.parent.parent  # nashik-chatbot-pq/
            problem_solved_dir = project_root.parent / "data_qlense" / "Problem_Solved"

            from app.connectors.state_db_connector import StateDBConnector
            from app.config.config import get_settings
            from dataloader.scraper.file_system_scraper import FileScraper
            from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

            settings = get_settings()
            index_name = settings.OPENSEARCH_INDEX_NAME

            db = StateDBConnector()
            scraper = FileScraper(db, index_name)
            scrape_stats = scraper.scrape_directory(problem_solved_dir)
            db.close()

            dep = DocumentEmbeddingProcessor()
            embed_stats = dep.run()
            dep.close()

            _ingest_state["last_result"] = {
                "scrape": scrape_stats,
                "embed": embed_stats,
            }
            logger.info(
                f"PDF ingestion complete: "
                f"{embed_stats['documents_completed']}/{embed_stats['documents_processed']} docs, "
                f"{embed_stats['total_chunks_created']} chunks created"
            )
        except Exception as e:
            logger.error(f"PDF ingestion error: {e}", exc_info=True)
            _ingest_state["error"] = str(e)
        finally:
            _ingest_state["running"] = False

    threading.Thread(target=_run, daemon=True, name="qlense-pdf-ingest").start()
    return {"started": True, "message": "PDF ingestion started in background. Poll /qlense/ingest-status for progress."}


@router.get("/ingest-status")
async def qlense_ingest_status():
    """
    Return current state of the background PDF ingestion job.
    """
    return {
        "running": _ingest_state["running"],
        "last_result": _ingest_state["last_result"],
        "error": _ingest_state["error"],
    }


@router.post("/confirm-upload")
async def qlense_confirm_upload(payload: QLenseConfirmUploadRequest):
    """
    Apply the column mapping and load the file into the correct PostgreSQL table.
    Dispatches to the same service method as Part Labeler so the QLense agent
    can immediately query the data after upload.

    dataSource must be one of: warranty, rpt, gnovac, rfi, esqa
    """
    valid_sources = {"warranty", "rpt", "gnovac", "rfi", "esqa"}
    if payload.dataSource not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dataSource '{payload.dataSource}'. Must be one of: {', '.join(valid_sources)}"
        )
    try:
        count = _get_service().process_data_for_source(
            payload.tempFilePath,
            payload.mapping,
            payload.userId,
            payload.dataSource,
        )
        if os.path.exists(payload.tempFilePath):
            os.remove(payload.tempFilePath)
        return {"success": True, "rowsLoaded": count, "dataSource": payload.dataSource}
    except Exception as e:
        logger.error(f"QLense confirm-upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
