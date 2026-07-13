from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.database import get_connector
from app.queries import CarModelQueries

router = APIRouter(prefix="/car-models", tags=["car_models"])


def _row(row) -> dict:
    return dict(row._mapping)


class CarModelCreate(BaseModel):
    name: str
    code: Optional[str] = None


class CarModelUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


@router.get("")
def list_car_models(connector: StateDBConnector = Depends(get_connector)):
    rows = connector.execute_query(CarModelQueries.LIST_ALL, {})
    return [_row(r) for r in rows]


@router.post("", status_code=201)
def create_car_model(
    payload: CarModelCreate,
    connector: StateDBConnector = Depends(get_connector),
):
    rows = connector.execute_query(
        CarModelQueries.CREATE, {"name": payload.name, "code": payload.code}
    )
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to create car model")
    return _row(rows[0])


@router.put("/{car_model_id}")
def update_car_model(
    car_model_id: int,
    payload: CarModelUpdate,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(CarModelQueries.CHECK_EXISTS, {"car_model_id": car_model_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Car model not found")

    rows = connector.execute_query(
        CarModelQueries.UPDATE,
        {"car_model_id": car_model_id, "name": payload.name, "code": payload.code},
    )
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to update car model")
    return _row(rows[0])


@router.delete("/{car_model_id}", status_code=204)
def delete_car_model(
    car_model_id: int,
    connector: StateDBConnector = Depends(get_connector),
):
    exists = connector.execute_query(CarModelQueries.CHECK_EXISTS, {"car_model_id": car_model_id})
    if not exists:
        raise HTTPException(status_code=404, detail="Car model not found")

    connector.execute_update(CarModelQueries.DELETE, {"car_model_id": car_model_id})
