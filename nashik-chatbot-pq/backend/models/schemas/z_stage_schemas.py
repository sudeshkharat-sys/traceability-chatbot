from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ── StationBox ───────────────────────────────────────────────────────────────

class StationBoxBase(BaseModel):
    name: str
    prefix: str
    station_count: int
    station_ids: Optional[str] = None
    z_labels: Optional[str] = None
    station_data: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    order_index: int = 0


class StationBoxCreate(StationBoxBase):
    pass


class StationBoxUpdate(BaseModel):
    name: Optional[str] = None
    prefix: Optional[str] = None
    station_count: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    order_index: Optional[int] = None


class StationBoxOut(StationBoxBase):
    id: int
    layout_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── BuyoffIcon ───────────────────────────────────────────────────────────────

class BuyoffIconBase(BaseModel):
    position_x: float = 0.0
    position_y: float = 0.0


class BuyoffIconCreate(BuyoffIconBase):
    pass


class BuyoffIconUpdate(BaseModel):
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class BuyoffIconOut(BuyoffIconBase):
    id: int
    layout_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat aliases (keep old names working during transition)
BypassIconBase   = BuyoffIconBase
BypassIconCreate = BuyoffIconCreate
BypassIconUpdate = BuyoffIconUpdate
BypassIconOut    = BuyoffIconOut


# ── Connection ────────────────────────────────────────────────────────────────

class ConnectionOut(BaseModel):
    id: int
    layout_id: int
    from_box_id: Optional[int] = None
    to_box_id: Optional[int] = None
    from_buyoff_id: Optional[int] = None
    to_buyoff_id: Optional[int] = None
    from_station_id: Optional[str] = None
    to_station_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Layout ────────────────────────────────────────────────────────────────────

class LayoutBase(BaseModel):
    name: str


class LayoutCreate(LayoutBase):
    pass


class LayoutUpdate(BaseModel):
    name: Optional[str] = None
    legend_position_x: Optional[float] = None
    legend_position_y: Optional[float] = None


class LayoutOut(LayoutBase):
    id: int
    user_id: Optional[int] = None
    legend_position_x: Optional[float] = None
    legend_position_y: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    station_boxes: List[StationBoxOut] = []
    buyoff_icons: List[BuyoffIconOut] = []
    connections: List[ConnectionOut] = []

    model_config = {"from_attributes": True}


class LayoutSummary(LayoutBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Snapshot (full layout save) ───────────────────────────────────────────────

class SnapshotBox(BaseModel):
    local_id: str
    name: str
    prefix: str
    station_count: int
    station_ids: Optional[str] = None
    z_labels: Optional[str] = None
    station_data: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    order_index: int = 0


class SnapshotBuyoffIcon(BaseModel):
    local_id: str
    position_x: float = 0.0
    position_y: float = 0.0


# Backward-compat alias
SnapshotBypassIcon = SnapshotBuyoffIcon


class SnapshotConnection(BaseModel):
    from_local_id: str
    to_local_id: str
    from_station_id: Optional[str] = None
    to_station_id: Optional[str] = None


class LayoutSnapshotCreate(BaseModel):
    name: str
    legend_position_x: Optional[float] = None
    legend_position_y: Optional[float] = None
    boxes: List[SnapshotBox] = []
    buyoff_icons: List[SnapshotBuyoffIcon] = []
    connections: List[SnapshotConnection] = []


# ── InputRecord ───────────────────────────────────────────────────────────────

class InputRecordOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    layout_id: Optional[int] = None
    sr_no: Optional[int] = None
    concern_id: Optional[str] = None
    concern: Optional[str] = None
    type: Optional[str] = None
    root_cause: Optional[str] = None
    action_plan: Optional[str] = None
    target_date: Optional[str] = None
    closure_date: Optional[str] = None
    ryg: Optional[str] = None
    attri: Optional[str] = None
    comm: Optional[str] = None
    line: Optional[str] = None
    stage_no: Optional[str] = None
    z_e: Optional[str] = None
    attribution: Optional[str] = None
    part: Optional[str] = None
    phenomena: Optional[str] = None
    total_incidences: Optional[int] = None
    monthly_data: Optional[str] = None
    field_defect_after_cutoff: Optional[int] = None
    status_3m: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InputRecordUpdate(BaseModel):
    layout_id: Optional[int] = None
    sr_no: Optional[int] = None
    concern_id: Optional[str] = None
    concern: Optional[str] = None
    type: Optional[str] = None
    root_cause: Optional[str] = None
    action_plan: Optional[str] = None
    target_date: Optional[str] = None
    closure_date: Optional[str] = None
    ryg: Optional[str] = None
    attri: Optional[str] = None
    comm: Optional[str] = None
    line: Optional[str] = None
    stage_no: Optional[str] = None
    z_e: Optional[str] = None
    attribution: Optional[str] = None
    part: Optional[str] = None
    phenomena: Optional[str] = None
    total_incidences: Optional[int] = None
    monthly_data: Optional[str] = None
    field_defect_after_cutoff: Optional[int] = None
    status_3m: Optional[str] = None


class UploadResponse(BaseModel):
    message: str
    rows_imported: int
