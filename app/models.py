from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str
    password_hash: str
    role: str = Field(default="operator")
    created_at: datetime = Field(default_factory=utcnow)


class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)


class RecipeVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    version: int
    instructions: list[dict[str, Any]] = Field(sa_column=Column(JSON))
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="draft")
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_number: str = Field(index=True, unique=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    recipe_version_id: int = Field(foreign_key="recipeversion.id")
    status: str = Field(default="created", index=True)
    product_name: str
    planned_quantity: float = 0.0
    actual_quantity: float = 0.0
    current_step: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)


class BatchEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: Optional[int] = Field(default=None, foreign_key="batch.id", index=True)
    event_type: str = Field(index=True)
    actor: str = Field(index=True)
    action: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    electronic_signature: bool = False
    comment: Optional[str] = None
    previous_hash: Optional[str] = None
    event_hash: str = Field(index=True)
    anchored_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class MaterialLot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    material_code: str = Field(index=True)
    lot_number: str = Field(index=True, unique=True)
    quantity: float = 0.0
    unit: str = Field(default="kg")
    status: str = Field(default="available")
    parent_lot_id: Optional[int] = Field(default=None, foreign_key="materiallot.id")
    batch_id: Optional[int] = Field(default=None, foreign_key="batch.id", index=True)
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)


class Equipment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    equipment_code: str = Field(index=True, unique=True)
    name: str
    status: str = Field(default="idle")
    runtime_minutes: float = 0.0
    downtime_minutes: float = 0.0
    ideal_rate_per_minute: float = 1.0
    total_count: int = 0
    good_count: int = 0
    reject_count: int = 0
    last_seen_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class BlockchainAnchor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_hash: str = Field(index=True, unique=True)
    backend: str
    reference: str
    anchored_at: datetime = Field(default_factory=utcnow)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
