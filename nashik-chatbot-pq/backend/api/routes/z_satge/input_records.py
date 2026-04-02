import io
import json
import logging
import re
from typing import List, Optional

import openpyxl
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import InputRecordQueries
import backend.models.schemas.z_stage_schemas as schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/input", tags=["input"])

# Month keys expected in the Excel (Jan 2024 → Mar 2026)
MONTHLY_KEYS = [
    "2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06",
    "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03",
]


def _row_to_dict(row) -> dict:
    return dict(row._mapping)


def _clean_text(s: str) -> str:
    """Remove characters that cannot be stored in WIN1252 (e.g. zero-width spaces)."""
    s = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]', '', s)
    s = s.encode('cp1252', errors='replace').decode('cp1252')
    return s


def _safe_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.startswith("="):
        return None
    s = _clean_text(s)
    return s or None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_date(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if s.startswith("=") or not s or s == "00:00:00":
        return None
    return s


def _parse_excel(file_bytes: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(
        io.BytesIO(file_bytes), data_only=True, read_only=True
    )
    ws = wb.active

    records = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if row_idx == 1:
            continue  # skip header

        if not any(v is not None for v in row):
            continue  # skip empty rows

        # Monthly data: columns 19-45 (0-indexed 18-44)
        monthly = {}
        for i, key in enumerate(MONTHLY_KEYS):
            val = row[18 + i] if len(row) > 18 + i else None
            if val is not None:
                try:
                    monthly[key] = int(val)
                except (ValueError, TypeError):
                    pass

        # Compute total from parsed monthly values if Excel formula was used
        total_raw = row[17] if len(row) > 17 else None
        total = _safe_int(total_raw) if not (
            total_raw and str(total_raw).startswith("=")
        ) else sum(monthly.values())

        records.append({
            "sr_no":                    _safe_int(row[0] if len(row) > 0 else None),
            "concern_id":               _safe_str(row[1] if len(row) > 1 else None),
            "concern":                  _safe_str(row[2] if len(row) > 2 else None),
            "type":                     _safe_str(row[3] if len(row) > 3 else None),
            "root_cause":               _safe_str(row[4] if len(row) > 4 else None),
            "action_plan":              _safe_str(row[5] if len(row) > 5 else None),
            "target_date":              _safe_date(row[6] if len(row) > 6 else None),
            "closure_date":             _safe_date(row[7] if len(row) > 7 else None),
            "ryg":                      _safe_str(row[8] if len(row) > 8 else None),
            "attri":                    _safe_str(row[9] if len(row) > 9 else None),
            "comm":                     _safe_str(row[10] if len(row) > 10 else None),
            "line":                     _safe_str(row[11] if len(row) > 11 else None),
            "stage_no":                 _safe_str(row[12] if len(row) > 12 else None),
            "z_e":                      _safe_str(row[13] if len(row) > 13 else None),
            "attribution":              _safe_str(row[14] if len(row) > 14 else None),
            "part":                     _safe_str(row[15] if len(row) > 15 else None),
            "phenomena":                _safe_str(row[16] if len(row) > 16 else None),
            "total_incidences":         total,
            "monthly_data":             json.dumps(monthly) if monthly else None,
            "field_defect_after_cutoff": _safe_int(row[45] if len(row) > 45 else None),
            "status_3m":                _safe_str(row[46] if len(row) > 46 else None),
        })

    return records


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=schemas.UploadResponse, status_code=201)
async def upload_excel(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None),
    layout_id: Optional[int] = Form(None),
    connector: StateDBConnector = Depends(get_connector),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx / .xls files are accepted")

    file_bytes = await file.read()
    try:
        records = _parse_excel(file_bytes)
    except Exception as exc:
        logger.error(f"Excel parse error: {exc}")
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel: {exc}")

    if not records:
        raise HTTPException(status_code=422, detail="No data rows found in the uploaded file")

    # Full replace for this user+layout scope, then insert fresh ones
    connector.execute_update(
        InputRecordQueries.DELETE_ALL,
        {"user_id": user_id, "layout_id": layout_id},
    )

    for rec in records:
        rec["user_id"] = user_id
        rec["layout_id"] = layout_id
        connector.execute_query(InputRecordQueries.CREATE, rec)

    return {"message": "Upload successful", "rows_imported": len(records)}


@router.get("/records", response_model=List[schemas.InputRecordOut])
def list_records(
    user_id: Optional[int] = Query(None),
    layout_id: Optional[int] = Query(None),
    connector: StateDBConnector = Depends(get_connector),
):
    rows = connector.execute_query(
        InputRecordQueries.LIST_ALL,
        {"user_id": user_id, "layout_id": layout_id},
    )
    return [_row_to_dict(r) for r in rows]


@router.put("/records/{record_id}", response_model=schemas.InputRecordOut)
def update_record(
    record_id: int,
    payload: schemas.InputRecordUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(
        InputRecordQueries.CHECK_EXISTS, {"record_id": record_id}
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Record not found")

    data = payload.model_dump()
    data["record_id"] = record_id

    rows = connector.execute_query(InputRecordQueries.UPDATE, data)
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to update record")
    return _row_to_dict(rows[0])
