import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import Z3DLibraryQueries, Z3DPlacementQueries

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
    # True when px/pz are an offset from the placement's station center
    # (survives refresh and follows the station); False = legacy absolute
    # coords, which the renderer ignores for station-bound rows.
    pos_is_offset: bool = False


class DefaultsUpdate(BaseModel):
    px: float = 0; py: float = 0; pz: float = 0
    rx: float = 0; ry: float = 0; rz: float = 0
    sx: float = 1; sy: float = 1; sz: float = 1


# ── Library endpoints ──────────────────────────────────────────────────────────

@router.get("/library")
def list_library(connector: StateDBConnector = Depends(get_connector)):
    """List all models in the global library."""
    rows = connector.execute_query(Z3DLibraryQueries.LIST_ALL, {})
    return [_row(r) for r in rows]


@router.get("/library/{name}")
def get_library_model(name: str, connector: StateDBConnector = Depends(get_connector)):
    """Check if a model exists in the library by name."""
    rows = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": name})
    if not rows:
        raise HTTPException(status_code=404, detail="Model not in library")
    return _row(rows[0])


@router.post("/library/upload", status_code=201)
async def upload_to_library(
    file: UploadFile = File(...),
    name: str = Form(...),
    default_sx: float = Form(1), default_sy: float = Form(1), default_sz: float = Form(1),
    default_rx: float = Form(0), default_ry: float = Form(0), default_rz: float = Form(0),
    connector: StateDBConnector = Depends(get_connector),
):
    """Upload a GLB to the global library (or update defaults if name already exists)."""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Check if model already exists — reuse existing file if so
    existing = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": name})
    file_path = None
    file_size = 0

    data = await file.read()
    if data:  # new file provided
        upload_dir = _upload_dir()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (file.filename or f"{name}.glb"))
        dest = upload_dir / safe
        counter = 1
        stem, sfx = dest.stem, dest.suffix
        while dest.exists() and not (existing and _row(existing[0]).get("file_path") == str(dest)):
            dest = upload_dir / f"{stem}_{counter}{sfx}"
            counter += 1
        dest.write_bytes(data)
        file_path = str(dest)
        file_size = len(data)
    elif existing:
        rec = _row(existing[0])
        file_path = rec.get("file_path")
        file_size = rec.get("file_size", 0)

    rows = connector.execute_query(Z3DLibraryQueries.UPSERT, {
        "name": name, "ext": ext,
        "file_path": file_path, "file_size": file_size,
        "default_sx": default_sx, "default_sy": default_sy, "default_sz": default_sz,
        "default_rx": default_rx, "default_ry": default_ry, "default_rz": default_rz,
    })
    return _row(rows[0])


@router.put("/library/{name}/defaults")
def update_defaults(
    name: str,
    body: DefaultsUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    """Save default position/scale/rotation for a model name — this doubles as the
    reusable "preset" transform applied whenever the model is mapped onto a line."""
    rows = connector.execute_query(Z3DLibraryQueries.UPDATE_DEFAULTS, {
        "name": name,
        "px": body.px, "py": body.py, "pz": body.pz,
        "sx": body.sx, "sy": body.sy, "sz": body.sz,
        "rx": body.rx, "ry": body.ry, "rz": body.rz,
    })
    if not rows:
        raise HTTPException(status_code=404, detail="Model not in library")
    return _row(rows[0])


@router.get("/library/{name}/download")
def download_library_model(name: str, connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": name})
    if not rows:
        raise HTTPException(status_code=404, detail="Model not in library")
    rec = _row(rows[0])
    fp = rec.get("file_path")
    if not fp or not Path(fp).exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    ext = rec.get("ext", "glb")
    mime = {"glb": "model/gltf-binary", "gltf": "model/gltf+json",
            "obj": "text/plain", "stl": "application/octet-stream"}.get(ext, "application/octet-stream")
    # A model's download URL is keyed by NAME, not by file version — replacing
    # the file (re-upload under the same name) does not change the URL. With
    # max-age, the browser wouldn't even ask the server again for up to a day,
    # so a replaced/compressed model could sit invisible for that whole window.
    # no-cache forces a conditional GET (If-None-Match/If-Modified-Since) on
    # every request instead: still cheap (a 304 with no body if unchanged,
    # using the ETag/Last-Modified FileResponse already sets from the file's
    # mtime) but always correct — a replacement is picked up on the very next
    # request, not up to 24h later.
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return FileResponse(path=fp, filename=f"{rec['name']}.{ext}", media_type=mime, headers=headers)


@router.delete("/library/{name}", status_code=204)
def delete_library_model(name: str, connector: StateDBConnector = Depends(get_connector)):
    """Remove a model from the library entirely — deletes its file, any
    line->car-model mappings using it (FK CASCADE), and any placements
    across every layout that were showing it."""
    rows = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": name})
    if not rows:
        raise HTTPException(status_code=404, detail="Model not in library")
    rec = _row(rows[0])

    connector.execute_update(Z3DPlacementQueries.DELETE_BY_MODEL_NAME, {"model_name": name})
    connector.execute_update(Z3DLibraryQueries.DELETE_BY_NAME, {"name": name})

    fp = rec.get("file_path")
    if fp and Path(fp).exists():
        try:
            Path(fp).unlink()
        except OSError:
            logger.warning(f"Failed to delete file on disk for model '{name}': {fp}")


# ── Placement endpoints ────────────────────────────────────────────────────────

@router.get("/placements/layout/{layout_id}")
def list_placements(layout_id: int, connector: StateDBConnector = Depends(get_connector)):
    """List all placed models for a layout."""
    rows = connector.execute_query(Z3DPlacementQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})
    return [_row(r) for r in rows]


@router.post("/placements", status_code=201)
def create_placement(
    layout_id: int = Form(...),
    model_name: str = Form(...),
    line_group_id: Optional[str] = Form(None),
    station_id: Optional[str] = Form(None),
    px: float = Form(0), py: float = Form(0), pz: float = Form(0),
    rx: float = Form(0), ry: float = Form(0), rz: float = Form(0),
    sx: float = Form(1), sy: float = Form(1), sz: float = Form(1),
    pos_is_offset: bool = Form(False),
    connector: StateDBConnector = Depends(get_connector),
):
    rows = connector.execute_query(Z3DPlacementQueries.CREATE, {
        "layout_id": layout_id, "model_name": model_name,
        "line_group_id": line_group_id, "station_id": station_id,
        "px": px, "py": py, "pz": pz,
        "rx": rx, "ry": ry, "rz": rz,
        "sx": sx, "sy": sy, "sz": sz,
        "pos_is_offset": pos_is_offset,
    })
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to create placement")
    return _row(rows[0])


@router.put("/placements/{placement_id}/transform")
def update_placement_transform(
    placement_id: int,
    body: TransformUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    connector.execute_update(Z3DPlacementQueries.UPDATE_TRANSFORM, {
        "placement_id": placement_id,
        "px": body.px, "py": body.py, "pz": body.pz,
        "rx": body.rx, "ry": body.ry, "rz": body.rz,
        "sx": body.sx, "sy": body.sy, "sz": body.sz,
        "pos_is_offset": body.pos_is_offset,
    })
    return {"ok": True}


@router.delete("/placements/{placement_id}", status_code=204)
def delete_placement(placement_id: int, connector: StateDBConnector = Depends(get_connector)):
    connector.execute_update(Z3DPlacementQueries.DELETE, {"placement_id": placement_id})


@router.get("/placements/by-model-name/{model_name}")
def get_placements_by_model_name(
    model_name: str,
    connector: StateDBConnector = Depends(get_connector),
):
    """Fallback: return latest placements for a model name across all layouts."""
    rows = connector.execute_query(
        Z3DPlacementQueries.LIST_LATEST_BY_MODEL_NAME,
        {"model_name": model_name},
    )
    return [_row(r) for r in rows]


@router.get("/placements/line-groups")
def list_all_line_groups(connector: StateDBConnector = Depends(get_connector)):
    """Return all distinct line_group_ids that have saved placements."""
    rows = connector.execute_query(Z3DPlacementQueries.LIST_ALL_LINE_GROUPS, {})
    return [r._mapping["line_group_id"] for r in rows]


@router.get("/placements/by-line-group/{line_group_id}")
def get_placements_by_line_group(
    line_group_id: str,
    connector: StateDBConnector = Depends(get_connector),
):
    """Return the latest saved transforms for a line group across all layouts."""
    rows = connector.execute_query(
        Z3DPlacementQueries.LIST_LATEST_BY_LINE_GROUP,
        {"line_group_id": line_group_id},
    )
    return [_row(r) for r in rows]


@router.delete("/placements/group/{layout_id}/{line_group_id}", status_code=204)
def delete_placement_group(
    layout_id: int, line_group_id: str,
    connector: StateDBConnector = Depends(get_connector),
):
    connector.execute_update(Z3DPlacementQueries.DELETE_BY_GROUP,
                             {"line_group_id": line_group_id, "layout_id": layout_id})
