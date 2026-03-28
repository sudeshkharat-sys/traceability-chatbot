from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.connectors.state_db_connector import StateDBConnector
from app.queries import LayoutQueries, BypassIconQueries
from app.connectors.database import get_connector
import backend.models.schemas.z_stage_schemas as schemas

router = APIRouter(tags=["bypass_icons"])


def _row_to_dict(row) -> dict:
    return dict(row._mapping)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/layouts/{layout_id}/bypass-icons",
    response_model=List[schemas.BypassIconOut],
)
def list_bypass_icons(
    layout_id: int,
    connector:  StateDBConnector = Depends(get_connector),
):
    layout_exists = connector.execute_query(
        LayoutQueries.CHECK_EXISTS, {"layout_id": layout_id}
    )
    if not layout_exists:
        raise HTTPException(status_code=404, detail="Layout not found")

    rows = connector.execute_query(
        BypassIconQueries.LIST_BY_LAYOUT, {"layout_id": layout_id}
    )
    return [_row_to_dict(r) for r in rows]


@router.post(
    "/layouts/{layout_id}/bypass-icons",
    response_model=schemas.BypassIconOut,
    status_code=201,
)
def create_bypass_icon(
    layout_id: int,
    payload: schemas.BypassIconCreate,
    connector: StateDBConnector = Depends(get_connector),
):
    layout_exists = connector.execute_query(
        LayoutQueries.CHECK_EXISTS, {"layout_id": layout_id}
    )
    if not layout_exists:
        raise HTTPException(status_code=404, detail="Layout not found")

    rows = connector.execute_query(
        BypassIconQueries.CREATE_ICON,
        {
            "layout_id": layout_id,
            "position_x": payload.position_x,
            "position_y": payload.position_y,
        },
    )
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to create bypass icon")
    return _row_to_dict(rows[0])


@router.put("/bypass-icons/{icon_id}", response_model=schemas.BypassIconOut)
def update_bypass_icon(
    icon_id: int,
    payload: schemas.BypassIconUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(
        BypassIconQueries.CHECK_EXISTS, {"icon_id": icon_id}
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Bypass icon not found")

    data = payload.model_dump()
    rows = connector.execute_query(
        BypassIconQueries.UPDATE_ICON,
        {
            "icon_id": icon_id,
            "position_x": data.get("position_x"),
            "position_y": data.get("position_y"),
        },
    )
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to update bypass icon")
    return _row_to_dict(rows[0])


@router.delete("/bypass-icons/{icon_id}", status_code=204)
def delete_bypass_icon(
    icon_id: int,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(
        BypassIconQueries.CHECK_EXISTS, {"icon_id": icon_id}
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Bypass icon not found")

    connector.execute_update(BypassIconQueries.DELETE_ICON, {"icon_id": icon_id})
