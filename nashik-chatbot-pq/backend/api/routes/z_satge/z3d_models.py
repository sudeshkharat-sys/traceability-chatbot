import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import Z3DModelQueries

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/3d-models", tags=["z3d_models"])

ALLOWED_EXT = {"glb", "gltf", "obj", "stl"}


def _upload_dir() -> Path:
    base = Path(os.environ.get("UPLOADS_DIRECTORY", "uploads"))
    if not base.is_absolute():
        base = Path.cwd() / base
    d = base / "z3d_models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _row(row) -> dict:
    return dict(row._mapping)


# ── Schemas ────────────────────────────────────────────────────────────────────

class TransformUpdate(BaseModel):
    px: float = 0; py: float = 0; pz: float = 0
    rx: float = 0; ry: float = 0; rz: float = 0
    sx: float = 1; sy: float = 1; sz: float = 1


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/layout/{layout_id}")
def list_models(layout_id: int, connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(Z3DModelQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})
    return [_row(r) for r in rows]


@router.post("/upload", status_code=201)
async def upload_model(
    file: UploadFile = File(...),
    layout_id: int = Form(...),
    user_id: Optional[int] = Form(None),
    name: str = Form(...),
    line_group_id: Optional[str] = Form(None),
    station_id: Optional[str] = Form(None),
    is_group_leader: bool = Form(True),
    px: float = Form(0), py: float = Form(0), pz: float = Form(0),
    rx: float = Form(0), ry: float = Form(0), rz: float = Form(0),
    sx: float = Form(1), sy: float = Form(1), sz: float = Form(1),
    connector: StateDBConnector = Depends(get_connector),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Only the group leader (first clone) uploads the actual file; clones reuse file_path=None
    file_path = None
    file_size = 0
    if is_group_leader:
        upload_dir = _upload_dir()
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in (file.filename or "model.glb"))
        dest = upload_dir / f"layout{layout_id}_{safe_name}"
        counter = 1
        stem, sfx = dest.stem, dest.suffix
        while dest.exists():
            dest = upload_dir / f"{stem}_{counter}{sfx}"
            counter += 1
        data = await file.read()
        dest.write_bytes(data)
        file_path = str(dest)
        file_size = len(data)
    else:
        await file.read()  # consume to avoid connection issues

    row = connector.execute_query(Z3DModelQueries.CREATE, {
        "layout_id": layout_id, "user_id": user_id,
        "name": name, "ext": ext,
        "file_path": file_path, "file_size": file_size,
        "line_group_id": line_group_id, "station_id": station_id,
        "px": px, "py": py, "pz": pz,
        "rx": rx, "ry": ry, "rz": rz,
        "sx": sx, "sy": sy, "sz": sz,
    })
    if not row:
        raise HTTPException(status_code=500, detail="Failed to save model record")
    return _row(row[0])


@router.get("/{model_id}/download")
def download_model(model_id: int, connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(Z3DModelQueries.GET_BY_ID, {"model_id": model_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Model not found")
    rec = _row(rows[0])

    # Walk the group to find the leader's file_path if this clone has none
    fp = rec.get("file_path")
    if not fp and rec.get("line_group_id"):
        group_rows = connector.execute_query(Z3DModelQueries.LIST_GROUP, {
            "line_group_id": rec["line_group_id"], "layout_id": rec["layout_id"]
        })
        for gr in group_rows:
            gd = _row(gr)
            if gd.get("file_path"):
                fp = gd["file_path"]
                break

    if not fp or not Path(fp).exists():
        raise HTTPException(status_code=404, detail="File not found on server")

    ext = rec.get("ext", "glb")
    mime = {"glb": "model/gltf-binary", "gltf": "model/gltf+json",
            "obj": "text/plain", "stl": "application/octet-stream"}.get(ext, "application/octet-stream")
    return FileResponse(path=fp, filename=f"{rec['name']}.{ext}", media_type=mime)


@router.put("/{model_id}/transform", status_code=200)
def update_transform(
    model_id: int,
    body: TransformUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    rows = connector.execute_query(Z3DModelQueries.CHECK_EXISTS, {"model_id": model_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Model not found")
    connector.execute_update(Z3DModelQueries.UPDATE_TRANSFORM, {
        "model_id": model_id,
        "px": body.px, "py": body.py, "pz": body.pz,
        "rx": body.rx, "ry": body.ry, "rz": body.rz,
        "sx": body.sx, "sy": body.sy, "sz": body.sz,
    })
    return {"ok": True}


@router.delete("/{model_id}", status_code=204)
def delete_model(model_id: int, connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(Z3DModelQueries.GET_BY_ID, {"model_id": model_id})
    if not rows:
        return  # already gone
    rec = _row(rows[0])
    fp = rec.get("file_path")
    if fp and Path(fp).exists():
        try:
            Path(fp).unlink()
        except Exception as e:
            logger.warning(f"Could not delete 3D model file {fp}: {e}")
    connector.execute_update(Z3DModelQueries.DELETE, {"model_id": model_id})
