from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import Z3DPresetQueries, Z3DLibraryQueries

router = APIRouter(prefix="/3d-models/presets", tags=["z3d_presets"])


def _row(row) -> dict:
    return dict(row._mapping)


class PresetCreate(BaseModel):
    name: str
    model_name: str
    px: float = 0; py: float = 0; pz: float = 0
    rx: float = 0; ry: float = 0; rz: float = 0
    sx: float = 1; sy: float = 1; sz: float = 1


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    model_name: Optional[str] = None
    px: float = 0; py: float = 0; pz: float = 0
    rx: float = 0; ry: float = 0; rz: float = 0
    sx: float = 1; sy: float = 1; sz: float = 1


@router.get("")
def list_presets(connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(Z3DPresetQueries.LIST_ALL, {})
    return [_row(r) for r in rows]


@router.post("", status_code=201)
def create_preset(
    payload: PresetCreate,
    connector: StateDBConnector = Depends(get_connector),
):
    lib = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": payload.model_name})
    if not lib:
        raise HTTPException(status_code=404, detail=f"Model '{payload.model_name}' not in library")

    rows = connector.execute_query(Z3DPresetQueries.CREATE, {
        "name": payload.name, "model_name": payload.model_name,
        "px": payload.px, "py": payload.py, "pz": payload.pz,
        "rx": payload.rx, "ry": payload.ry, "rz": payload.rz,
        "sx": payload.sx, "sy": payload.sy, "sz": payload.sz,
    })
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to create preset")
    return _row(rows[0])


@router.put("/{preset_id}")
def update_preset(
    preset_id: int,
    payload: PresetUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(Z3DPresetQueries.CHECK_EXISTS, {"preset_id": preset_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Preset not found")

    if payload.model_name:
        lib = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": payload.model_name})
        if not lib:
            raise HTTPException(status_code=404, detail=f"Model '{payload.model_name}' not in library")

    rows = connector.execute_query(Z3DPresetQueries.UPDATE, {
        "preset_id": preset_id, "name": payload.name, "model_name": payload.model_name,
        "px": payload.px, "py": payload.py, "pz": payload.pz,
        "rx": payload.rx, "ry": payload.ry, "rz": payload.rz,
        "sx": payload.sx, "sy": payload.sy, "sz": payload.sz,
    })
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to update preset")
    return _row(rows[0])


@router.delete("/{preset_id}", status_code=204)
def delete_preset(
    preset_id: int,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(Z3DPresetQueries.CHECK_EXISTS, {"preset_id": preset_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Preset not found")

    connector.execute_update(Z3DPresetQueries.DELETE, {"preset_id": preset_id})
