from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import (
    LineModelMappingQueries, Z3DPresetQueries, CarModelQueries,
    LayoutQueries, StationBoxQueries, Z3DPlacementQueries,
)

router = APIRouter(prefix="/line-model-mappings", tags=["line_model_mappings"])


def _row(row) -> dict:
    return dict(row._mapping)


class MappingCreate(BaseModel):
    layout_id: int
    line_group_id: str
    car_model_id: Optional[int] = None
    preset_id: int


def _apply_mapping_to_placements(connector: StateDBConnector, layout_id: int, line_group_id: str, preset: dict):
    """Fan the preset's model+transform out to every station on the matching line."""
    boxes = connector.execute_query(
        StationBoxQueries.LIST_BY_LAYOUT, {"layout_id": layout_id}
    )
    matching_boxes = [_row(b) for b in boxes if _row(b).get("name") == line_group_id]

    station_ids = []
    for box in matching_boxes:
        station_ids.extend(
            s.strip() for s in (box.get("station_ids") or "").split(",") if s.strip()
        )

    for station_id in station_ids:
        existing = connector.execute_query(
            Z3DPlacementQueries.GET_BY_LAYOUT_STATION,
            {"layout_id": layout_id, "station_id": station_id},
        )
        transform = {
            "model_name": preset["model_name"], "line_group_id": line_group_id,
            "px": preset["px"], "py": preset["py"], "pz": preset["pz"],
            "rx": preset["rx"], "ry": preset["ry"], "rz": preset["rz"],
            "sx": preset["sx"], "sy": preset["sy"], "sz": preset["sz"],
        }
        if existing:
            transform["placement_id"] = _row(existing[0])["id"]
            connector.execute_query(Z3DPlacementQueries.UPDATE_MODEL_AND_TRANSFORM, transform)
        else:
            transform["layout_id"] = layout_id
            transform["station_id"] = station_id
            connector.execute_query(Z3DPlacementQueries.CREATE, transform)


@router.get("/layout/{layout_id}")
def list_mappings(layout_id: int, connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(LineModelMappingQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})
    return [_row(r) for r in rows]


@router.post("", status_code=201)
def create_mapping(
    payload: MappingCreate,
    connector: StateDBConnector = Depends(get_connector),
):
    if not connector.execute_query(LayoutQueries.CHECK_EXISTS, {"layout_id": payload.layout_id}):
        raise HTTPException(status_code=404, detail="Layout not found")

    preset_rows = connector.execute_query(Z3DPresetQueries.GET_BY_ID, {"preset_id": payload.preset_id})
    if not preset_rows:
        raise HTTPException(status_code=404, detail="Preset not found")
    preset = _row(preset_rows[0])

    if payload.car_model_id is not None:
        if not connector.execute_query(CarModelQueries.CHECK_EXISTS, {"car_model_id": payload.car_model_id}):
            raise HTTPException(status_code=404, detail="Car model not found")
        rows = connector.execute_query(LineModelMappingQueries.UPSERT_WITH_CAR_MODEL, {
            "layout_id": payload.layout_id, "line_group_id": payload.line_group_id,
            "car_model_id": payload.car_model_id, "preset_id": payload.preset_id,
        })
    else:
        rows = connector.execute_query(LineModelMappingQueries.UPSERT_NO_CAR_MODEL, {
            "layout_id": payload.layout_id, "line_group_id": payload.line_group_id,
            "preset_id": payload.preset_id,
        })
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to save mapping")

    _apply_mapping_to_placements(connector, payload.layout_id, payload.line_group_id, preset)

    return _row(rows[0])


@router.delete("/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: int, connector: StateDBConnector = Depends(get_connector)):
    exists = connector.execute_query(LineModelMappingQueries.CHECK_EXISTS, {"mapping_id": mapping_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Mapping not found")
    connector.execute_update(LineModelMappingQueries.DELETE, {"mapping_id": mapping_id})


@router.get("/by-line-group/{line_group_id}")
def get_latest_by_line_group(line_group_id: str, connector: StateDBConnector = Depends(get_connector)):
    """Latest mapping(s) for a line name across all layouts — used for cross-layout auto-seed."""
    rows = connector.execute_query(
        LineModelMappingQueries.LIST_LATEST_BY_LINE_GROUP, {"line_group_id": line_group_id}
    )
    return [_row(r) for r in rows]
