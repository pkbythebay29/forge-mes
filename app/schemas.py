from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SignaturePayload(BaseModel):
    username: str
    password: str


class RecipeCreate(BaseModel):
    name: str
    description: str = ""
    instructions: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    actor: str


class RecipeApprove(BaseModel):
    actor: str
    signature: SignaturePayload


class BatchCreate(BaseModel):
    batch_number: str
    recipe_id: int
    recipe_version_id: Optional[int] = None
    product_name: str
    planned_quantity: float = 0.0
    actor: str


class BatchTransition(BaseModel):
    actor: str
    signature: SignaturePayload
    comment: Optional[str] = None


class EventCreate(BaseModel):
    batch_id: Optional[int] = None
    event_type: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str
    signature: Optional[SignaturePayload] = None
    comment: Optional[str] = None


class MaterialCreate(BaseModel):
    material_code: str
    lot_number: str
    quantity: float
    unit: str = "kg"
    status: str = "available"
    parent_lot_id: Optional[int] = None
    batch_id: Optional[int] = None
    actor: str


class EquipmentTelemetry(BaseModel):
    actor: str = "plc-simulator"
    status: str
    runtime_minutes: float = 0.0
    downtime_minutes: float = 0.0
    total_count: int = 0
    good_count: int = 0
    reject_count: int = 0
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MCPToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    created_by: str
    created_at: datetime


class RecipeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipe_id: int
    version: int
    instructions: list[dict[str, Any]]
    parameters: dict[str, Any]
    status: str
    approved_at: Optional[datetime]
    approved_by: Optional[str]


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_number: str
    recipe_id: int
    recipe_version_id: int
    status: str
    product_name: str
    planned_quantity: float
    actual_quantity: float
    current_step: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_id: Optional[int]
    event_type: str
    actor: str
    action: str
    payload: dict[str, Any]
    electronic_signature: bool
    comment: Optional[str]
    previous_hash: Optional[str]
    event_hash: str
    anchored_ref: Optional[str]
    created_at: datetime


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    material_code: str
    lot_number: str
    quantity: float
    unit: str
    status: str
    parent_lot_id: Optional[int]
    batch_id: Optional[int]
    created_by: str
    created_at: datetime


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_code: str
    name: str
    status: str
    runtime_minutes: float
    downtime_minutes: float
    ideal_rate_per_minute: float
    total_count: int
    good_count: int
    reject_count: int
    last_seen_at: Optional[datetime]
    metadata_json: dict[str, Any]
    availability: float
    performance: float
    quality: float
    oee: float
