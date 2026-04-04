from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.blockchain import generate_hash, get_anchor_service, verify_record
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
    session.commit()
    session.refresh(event)
    return event


def canonical_recipe_record(recipe: Recipe, version: RecipeVersion) -> dict[str, Any]:
    return {
        "entity_type": "recipe_version",
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "recipe_description": recipe.description,
        "recipe_version_id": version.id,
        "version": version.version,
        "status": version.status,
        "instructions": version.instructions,
        "parameters": version.parameters,
        "approved_at": version.approved_at.isoformat() if version.approved_at else None,
        "approved_by": version.approved_by,
        "created_by": version.created_by,
        "created_at": version.created_at.isoformat(),
    }


def canonical_batch_record(session: Session, batch: Batch) -> dict[str, Any]:
    recipe = get_recipe_or_404(session, batch.recipe_id)
    version = session.get(RecipeVersion, batch.recipe_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Recipe version not found")
    materials = session.exec(select(MaterialLot).where(MaterialLot.batch_id == batch.id).order_by(MaterialLot.id)).all()
    events = session.exec(select(BatchEvent).where(BatchEvent.batch_id == batch.id).order_by(BatchEvent.id)).all()
    return {
        "entity_type": "batch_record",
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "status": batch.status,
        "product_name": batch.product_name,
        "planned_quantity": batch.planned_quantity,
        "actual_quantity": batch.actual_quantity,
        "current_step": batch.current_step,
        "recipe": canonical_recipe_record(recipe, version),
        "materials": [
            {
                "id": material.id,
                "material_code": material.material_code,
                "lot_number": material.lot_number,
                "quantity": material.quantity,
                "unit": material.unit,
                "status": material.status,
                "parent_lot_id": material.parent_lot_id,
            }
            for material in materials
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "action": event.action,
                "payload": event.payload,
                "electronic_signature": event.electronic_signature,
                "comment": event.comment,
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
        "started_at": batch.started_at.isoformat() if batch.started_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat(),
    }


def upsert_anchor(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    record_data: dict[str, Any],
) -> BlockchainAnchor:
    hash_value = generate_hash(record_data)
    anchor_service = get_anchor_service()
    result = anchor_service.anchor(hash_value)
    existing = session.exec(
        select(BlockchainAnchor)
        .where(BlockchainAnchor.entity_type == entity_type)
        .where(BlockchainAnchor.entity_id == entity_id)
    ).first()
    if existing:
        existing.hash_value = hash_value
        existing.backend = result.backend
        existing.tx_id = result.tx_id
        existing.anchored_at = utcnow()
        existing.payload = {**result.payload, "record_preview": record_data.get("entity_type")}
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    anchor = BlockchainAnchor(
        entity_type=entity_type,
        entity_id=entity_id,
        hash_value=hash_value,
        backend=result.backend,
        tx_id=result.tx_id,
        payload={**result.payload, "record_preview": record_data.get("entity_type")},
    )
    session.add(anchor)
    session.commit()
    session.refresh(anchor)
    return anchor


def anchor_recipe_version(session: Session, recipe: Recipe, version: RecipeVersion) -> BlockchainAnchor:
    return upsert_anchor(
        session,
        entity_type="recipe_version",
        entity_id=version.id,
        record_data=canonical_recipe_record(recipe, version),
    )


def anchor_batch_record(session: Session, batch: Batch) -> BlockchainAnchor:
    return upsert_anchor(
        session,
        entity_type="batch",
        entity_id=batch.id,
        record_data=canonical_batch_record(session, batch),
    )


def verify_anchor(session: Session, anchor: BlockchainAnchor) -> dict[str, Any]:
    if anchor.entity_type == "batch":
        batch = get_batch_or_404(session, anchor.entity_id)
        record_data = canonical_batch_record(session, batch)
    elif anchor.entity_type == "recipe_version":
        version = session.get(RecipeVersion, anchor.entity_id)
        if not version:
            raise HTTPException(status_code=404, detail="Recipe version not found")
        recipe = get_recipe_or_404(session, version.recipe_id)
        record_data = canonical_recipe_record(recipe, version)
    else:
        raise HTTPException(status_code=404, detail="Unsupported anchored entity")

    recalculated_hash = generate_hash(record_data)
    return {
        "entity_type": anchor.entity_type,
        "entity_id": anchor.entity_id,
        "stored_hash": anchor.hash_value,
        "recalculated_hash": recalculated_hash,
        "verified": verify_record(record_data, anchor.hash_value),
        "tx_id": anchor.tx_id,
        "backend": anchor.backend,
        "payload": anchor.payload,
    }


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
