from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import (
    LineModelMappingQueries, Z3DLibraryQueries, CarModelQueries,
    StationBoxQueries, Z3DPlacementQueries,
)

router = APIRouter(prefix="/line-model-mappings", tags=["line_model_mappings"])


def _row(row) -> dict:
    return dict(row._mapping)


class MappingCreate(BaseModel):
    line_group_id: str
    car_model_id: Optional[int] = None
    model_name: str


def _apply_mapping_to_all_layouts(connector: StateDBConnector, line_group_id: str, library_model: dict):
    """Fan the library model + its saved default transform out to every station,
    on every layout, whose station box name matches this line — global, like the
    old 'one model for the line, everywhere' behaviour."""
    boxes = connector.execute_query(
        StationBoxQueries.LIST_BY_NAME_ALL_LAYOUTS, {"name": line_group_id}
    )

    for box in (_row(b) for b in boxes):
        layout_id = box["layout_id"]
        station_ids = [s.strip() for s in (box.get("station_ids") or "").split(",") if s.strip()]

        for station_id in station_ids:
            existing = connector.execute_query(
                Z3DPlacementQueries.GET_BY_LAYOUT_STATION,
                {"layout_id": layout_id, "station_id": station_id},
            )
            transform = {
                "model_name": library_model["name"], "line_group_id": line_group_id,
                "px": library_model["default_px"], "py": library_model["default_py"], "pz": library_model["default_pz"],
                "rx": library_model["default_rx"], "ry": library_model["default_ry"], "rz": library_model["default_rz"],
                "sx": library_model["default_sx"], "sy": library_model["default_sy"], "sz": library_model["default_sz"],
            }
            if existing:
                transform["placement_id"] = _row(existing[0])["id"]
                connector.execute_query(Z3DPlacementQueries.UPDATE_MODEL_AND_TRANSFORM, transform)
            else:
                transform["layout_id"] = layout_id
                transform["station_id"] = station_id
                connector.execute_query(Z3DPlacementQueries.CREATE, transform)


@router.get("")
def list_mappings(connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(LineModelMappingQueries.LIST_ALL, {})
    return [_row(r) for r in rows]


@router.post("", status_code=201)
def create_mapping(
    payload: MappingCreate,
    connector: StateDBConnector = Depends(get_connector),
):
    lib_rows = connector.execute_query(Z3DLibraryQueries.GET_BY_NAME, {"name": payload.model_name})
    if not lib_rows:
        raise HTTPException(status_code=404, detail=f"Model '{payload.model_name}' not in library")
    library_model = _row(lib_rows[0])

    if payload.car_model_id is not None:
        if not connector.execute_query(CarModelQueries.CHECK_EXISTS, {"car_model_id": payload.car_model_id}):
            raise HTTPException(status_code=404, detail="Car model not found")
        rows = connector.execute_query(LineModelMappingQueries.UPSERT_WITH_CAR_MODEL, {
            "line_group_id": payload.line_group_id,
            "car_model_id": payload.car_model_id, "model_name": library_model["name"],
        })
    else:
        rows = connector.execute_query(LineModelMappingQueries.UPSERT_NO_CAR_MODEL, {
            "line_group_id": payload.line_group_id, "model_name": library_model["name"],
        })
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to save mapping")

    _apply_mapping_to_all_layouts(connector, payload.line_group_id, library_model)

    return _row(rows[0])


@router.delete("/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: int, connector: StateDBConnector = Depends(get_connector)):
    exists = connector.execute_query(LineModelMappingQueries.CHECK_EXISTS, {"mapping_id": mapping_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Mapping not found")
    connector.execute_update(LineModelMappingQueries.DELETE, {"mapping_id": mapping_id})
