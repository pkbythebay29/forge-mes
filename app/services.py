from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.blockchain import get_anchor_service
from app.models import Batch, BatchEvent, BlockchainAnchor, Equipment, MaterialLot, Recipe, RecipeVersion


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_event_hash(previous_hash: str | None, batch_id: int | None, event_type: str, actor: str, action: str, payload: dict[str, Any], created_at: datetime) -> str:
    canonical = json.dumps(
        {
            "previous_hash": previous_hash,
            "batch_id": batch_id,
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "payload": payload,
            "created_at": created_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_event(
    session: Session,
    *,
    batch_id: int | None,
    event_type: str,
    actor: str,
    action: str,
    payload: dict[str, Any],
    electronic_signature: bool = False,
    comment: str | None = None,
) -> BatchEvent:
    previous_event = session.exec(select(BatchEvent).order_by(BatchEvent.id.desc())).first()
    previous_hash = previous_event.event_hash if previous_event else None
    created_at = utcnow()
    event_hash = compute_event_hash(previous_hash, batch_id, event_type, actor, action, payload, created_at)
    event = BatchEvent(
        batch_id=batch_id,
        event_type=event_type,
        actor=actor,
        action=action,
        payload=payload,
        electronic_signature=electronic_signature,
        comment=comment,
        previous_hash=previous_hash,
        event_hash=event_hash,
        created_at=created_at,
    )
    session.add(event)
    session.flush()

    anchor_service = get_anchor_service()
    anchor = anchor_service.anchor(event_hash)
    session.add(
        BlockchainAnchor(
            event_hash=event_hash,
            backend=anchor.backend,
            reference=anchor.reference,
            payload=anchor.payload,
        )
    )
    event.anchored_ref = anchor.reference
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_latest_recipe_version(session: Session, recipe_id: int) -> RecipeVersion:
    version = session.exec(
        select(RecipeVersion).where(RecipeVersion.recipe_id == recipe_id).order_by(RecipeVersion.version.desc())
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Recipe version not found")
    return version


def get_batch_or_404(session: Session, batch_id: int) -> Batch:
    batch = session.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


def get_recipe_or_404(session: Session, recipe_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def get_material_or_404(session: Session, material_id: int) -> MaterialLot:
    material = session.get(MaterialLot, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material lot not found")
    return material


def get_equipment_or_404(session: Session, equipment_id: int) -> Equipment:
    equipment = session.get(Equipment, equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return equipment


def ensure_batch_status(batch: Batch, allowed: set[str], target: str) -> None:
    if batch.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move batch from {batch.status} to {target}",
        )


def equipment_metrics(equipment: Equipment) -> dict[str, float]:
    total_time = equipment.runtime_minutes + equipment.downtime_minutes
    availability = equipment.runtime_minutes / total_time if total_time else 0.0
    performance = (
        min(equipment.total_count / max(equipment.runtime_minutes * equipment.ideal_rate_per_minute, 1e-9), 1.0)
        if equipment.runtime_minutes > 0
        else 0.0
    )
    quality = equipment.good_count / equipment.total_count if equipment.total_count else 0.0
    return {
        "availability": round(availability, 4),
        "performance": round(performance, 4),
        "quality": round(quality, 4),
        "oee": round(availability * performance * quality, 4),
    }
