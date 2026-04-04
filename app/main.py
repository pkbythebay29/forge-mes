from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.db import get_session, init_db, session_scope
from app.models import Batch, BatchEvent, BlockchainAnchor, Equipment, MaterialLot, Recipe, RecipeVersion, User
from app.schemas import (
    BatchCreate,
    BatchOut,
    BatchTransition,
    EquipmentOut,
    EquipmentTelemetry,
    EventCreate,
    EventOut,
    MCPToolCall,
    MaterialCreate,
    MaterialOut,
    RecipeApprove,
    RecipeCreate,
    RecipeOut,
    RecipeVersionOut,
    VerificationOut,
)
from app.security import hash_password, verify_signature
from app.services import (
    anchor_batch_record,
    anchor_recipe_version,
    ensure_batch_status,
    equipment_metrics,
    get_batch_or_404,
    get_equipment_or_404,
    get_latest_recipe_version,
    get_material_or_404,
    get_recipe_or_404,
    record_event,
    verify_anchor,
)
from app.websocket_manager import manager


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def seed_data() -> None:
    with session_scope() as session:
        recipe_to_anchor = None
        version_to_anchor = None
        if not session.exec(select(User)).first():
            for username, full_name, password, role in [
                ("operator", "Primary Operator", "operator123", "operator"),
                ("qa", "Quality Reviewer", "qa123", "qa"),
                ("agent", "Automation Agent", "agent123", "agent"),
            ]:
                session.add(
                    User(
                        username=username,
                        full_name=full_name,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )

        if not session.exec(select(Equipment)).first():
            session.add(
                Equipment(
                    equipment_code="MIX-001",
                    name="Mixer 001",
                    status="idle",
                    ideal_rate_per_minute=4.0,
                    metadata_json={"line": "A", "simulated": True},
                )
            )

        if not session.exec(select(Recipe)).first():
            recipe = Recipe(name="Demo Blend", description="Simple two-step blend recipe", created_by="qa")
            session.add(recipe)
            session.flush()
            version = RecipeVersion(
                recipe_id=recipe.id,
                version=1,
                instructions=[
                    {"step": 1, "title": "Charge Vessel", "instruction": "Add material lots to mixer", "target_value": 100},
                    {"step": 2, "title": "Mix", "instruction": "Mix for 15 minutes at standard speed", "target_value": 15},
                ],
                parameters={"temperature_c": 22, "speed_rpm": 120},
                status="approved",
                approved_by="qa",
                approved_at=datetime.now(timezone.utc),
                created_by="qa",
            )
            session.add(version)
            session.flush()
            recipe_to_anchor = recipe
            version_to_anchor = version
        session.commit()
        if recipe_to_anchor and version_to_anchor:
            anchor_recipe_version(session, recipe_to_anchor, version_to_anchor)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_data()
    yield


app = FastAPI(title="Forge MES", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def recipe_version_out(version: RecipeVersion) -> RecipeVersionOut:
    return RecipeVersionOut(
        id=version.id,
        recipe_id=version.recipe_id,
        version=version.version,
        instructions=version.instructions,
        parameters=version.parameters,
        status=version.status,
        approved_at=version.approved_at,
        approved_by=version.approved_by,
    )


@app.get("/")
def operator_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/recipes", response_model=RecipeVersionOut)
def create_recipe(payload: RecipeCreate, session: Session = Depends(get_session)) -> RecipeVersionOut:
    recipe = session.exec(select(Recipe).where(Recipe.name == payload.name)).first()
    if recipe:
        latest = get_latest_recipe_version(session, recipe.id)
        version_number = latest.version + 1
    else:
        recipe = Recipe(name=payload.name, description=payload.description, created_by=payload.actor)
        session.add(recipe)
        session.flush()
        version_number = 1

    version = RecipeVersion(
        recipe_id=recipe.id,
        version=version_number,
        instructions=payload.instructions,
        parameters=payload.parameters,
        status="draft",
        created_by=payload.actor,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    record_event(
        session,
        batch_id=None,
        event_type="recipe",
        actor=payload.actor,
        action="recipe_version_created",
        payload={"recipe_id": recipe.id, "recipe_version_id": version.id, "version": version.version},
    )
    return recipe_version_out(version)


@app.get("/recipes")
def list_recipes(session: Session = Depends(get_session)) -> list[dict]:
    recipes = session.exec(select(Recipe)).all()
    return [
        {
            "recipe": RecipeOut.model_validate(recipe).model_dump(),
            "latest_version": recipe_version_out(get_latest_recipe_version(session, recipe.id)).model_dump(),
        }
        for recipe in recipes
    ]


@app.post("/recipes/{recipe_id}/approve", response_model=RecipeVersionOut)
def approve_recipe(recipe_id: int, payload: RecipeApprove, session: Session = Depends(get_session)) -> RecipeVersionOut:
    verify_signature(session, payload.signature.username, payload.signature.password)
    recipe = get_recipe_or_404(session, recipe_id)
    version = get_latest_recipe_version(session, recipe.id)
    version.status = "approved"
    version.approved_by = payload.actor
    version.approved_at = datetime.now(timezone.utc)
    session.add(version)
    session.commit()
    session.refresh(version)
    record_event(
        session,
        batch_id=None,
        event_type="recipe",
        actor=payload.actor,
        action="recipe_approved",
        payload={"recipe_id": recipe.id, "recipe_version_id": version.id, "version": version.version},
        electronic_signature=True,
    )
    anchor_recipe_version(session, recipe, version)
    return recipe_version_out(version)


@app.post("/batches", response_model=BatchOut)
def create_batch(payload: BatchCreate, session: Session = Depends(get_session)) -> BatchOut:
    recipe = get_recipe_or_404(session, payload.recipe_id)
    recipe_version = session.get(RecipeVersion, payload.recipe_version_id) if payload.recipe_version_id else get_latest_recipe_version(session, recipe.id)
    if not recipe_version or recipe_version.status != "approved":
        raise HTTPException(status_code=409, detail="Batch must use an approved recipe version")
    batch = Batch(
        batch_number=payload.batch_number,
        recipe_id=recipe.id,
        recipe_version_id=recipe_version.id,
        product_name=payload.product_name,
        planned_quantity=payload.planned_quantity,
        created_by=payload.actor,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    record_event(
        session,
        batch_id=batch.id,
        event_type="batch",
        actor=payload.actor,
        action="batch_created",
        payload={"batch_number": batch.batch_number, "recipe_version_id": batch.recipe_version_id},
    )
    return BatchOut.model_validate(batch)


@app.get("/batches")
def list_batches(session: Session = Depends(get_session)) -> list[BatchOut]:
    return [BatchOut.model_validate(batch) for batch in session.exec(select(Batch).order_by(Batch.id.desc())).all()]


@app.get("/batches/{batch_id}")
def get_batch(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = get_batch_or_404(session, batch_id)
    recipe_version = session.get(RecipeVersion, batch.recipe_version_id)
    materials = session.exec(select(MaterialLot).where(MaterialLot.batch_id == batch.id)).all()
    events = session.exec(select(BatchEvent).where(BatchEvent.batch_id == batch.id).order_by(BatchEvent.id)).all()
    return {
        "batch": BatchOut.model_validate(batch).model_dump(),
        "recipe_version": recipe_version_out(recipe_version).model_dump(),
        "materials": [MaterialOut.model_validate(material).model_dump() for material in materials],
        "events": [EventOut.model_validate(event).model_dump() for event in events],
    }


@app.post("/batches/{batch_id}/start", response_model=BatchOut)
async def start_batch(batch_id: int, payload: BatchTransition, session: Session = Depends(get_session)) -> BatchOut:
    verify_signature(session, payload.signature.username, payload.signature.password)
    batch = get_batch_or_404(session, batch_id)
    ensure_batch_status(batch, {"created"}, "in_progress")
    batch.status = "in_progress"
    batch.started_at = datetime.now(timezone.utc)
    batch.current_step = 1
    session.add(batch)
    session.commit()
    session.refresh(batch)
    event = record_event(
        session,
        batch_id=batch.id,
        event_type="batch",
        actor=payload.actor,
        action="batch_started",
        payload={"batch_id": batch.id, "current_step": batch.current_step},
        electronic_signature=True,
        comment=payload.comment,
    )
    await manager.broadcast("events", {"kind": "batch_started", "batch_id": batch.id, "event": EventOut.model_validate(event).model_dump()})
    return BatchOut.model_validate(batch)


@app.post("/batches/{batch_id}/complete", response_model=BatchOut)
async def complete_batch(batch_id: int, payload: BatchTransition, session: Session = Depends(get_session)) -> BatchOut:
    verify_signature(session, payload.signature.username, payload.signature.password)
    batch = get_batch_or_404(session, batch_id)
    ensure_batch_status(batch, {"in_progress"}, "completed")
    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    event = record_event(
        session,
        batch_id=batch.id,
        event_type="batch",
        actor=payload.actor,
        action="batch_completed",
        payload={"batch_id": batch.id, "actual_quantity": batch.actual_quantity},
        electronic_signature=True,
        comment=payload.comment,
    )
    anchor_batch_record(session, batch)
    await manager.broadcast("events", {"kind": "batch_completed", "batch_id": batch.id, "event": EventOut.model_validate(event).model_dump()})
    return BatchOut.model_validate(batch)


@app.post("/events", response_model=EventOut)
async def create_event(payload: EventCreate, session: Session = Depends(get_session)) -> EventOut:
    signed = False
    if payload.signature:
        verify_signature(session, payload.signature.username, payload.signature.password)
        signed = True

    batch = get_batch_or_404(session, payload.batch_id) if payload.batch_id else None
    if batch and payload.action == "step_completed":
        batch.current_step += 1
        if "actual_quantity" in payload.payload:
            batch.actual_quantity = payload.payload["actual_quantity"]
        session.add(batch)
        session.commit()
        session.refresh(batch)

    event = record_event(
        session,
        batch_id=payload.batch_id,
        event_type=payload.event_type,
        actor=payload.actor,
        action=payload.action,
        payload=payload.payload,
        electronic_signature=signed,
        comment=payload.comment,
    )
    event_out = EventOut.model_validate(event)
    await manager.broadcast("events", {"kind": "event_created", "batch_id": payload.batch_id, "event": event_out.model_dump()})
    return event_out


@app.get("/batches/{batch_id}/events", response_model=list[EventOut])
def get_batch_events(batch_id: int, session: Session = Depends(get_session)) -> list[EventOut]:
    get_batch_or_404(session, batch_id)
    events = session.exec(select(BatchEvent).where(BatchEvent.batch_id == batch_id).order_by(BatchEvent.id)).all()
    return [EventOut.model_validate(event) for event in events]


@app.post("/materials", response_model=MaterialOut)
async def create_material(payload: MaterialCreate, session: Session = Depends(get_session)) -> MaterialOut:
    material = MaterialLot(
        material_code=payload.material_code,
        lot_number=payload.lot_number,
        quantity=payload.quantity,
        unit=payload.unit,
        status=payload.status,
        parent_lot_id=payload.parent_lot_id,
        batch_id=payload.batch_id,
        created_by=payload.actor,
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    event = record_event(
        session,
        batch_id=payload.batch_id,
        event_type="material",
        actor=payload.actor,
        action="material_recorded",
        payload={"material_id": material.id, "lot_number": material.lot_number, "parent_lot_id": material.parent_lot_id},
    )
    await manager.broadcast("events", {"kind": "material_recorded", "batch_id": payload.batch_id, "event": EventOut.model_validate(event).model_dump()})
    return MaterialOut.model_validate(material)


@app.get("/materials/{material_id}")
def get_material(material_id: int, session: Session = Depends(get_session)) -> dict:
    material = get_material_or_404(session, material_id)
    parent = session.get(MaterialLot, material.parent_lot_id) if material.parent_lot_id else None
    children = session.exec(select(MaterialLot).where(MaterialLot.parent_lot_id == material.id)).all()
    return {
        "material": MaterialOut.model_validate(material).model_dump(),
        "parent": MaterialOut.model_validate(parent).model_dump() if parent else None,
        "children": [MaterialOut.model_validate(child).model_dump() for child in children],
    }


@app.get("/anchors")
def list_anchors(session: Session = Depends(get_session)) -> list[dict]:
    anchors = session.exec(select(BlockchainAnchor).order_by(BlockchainAnchor.anchored_at.desc())).all()
    return [
        {
            "id": anchor.id,
            "entity_type": anchor.entity_type,
            "entity_id": anchor.entity_id,
            "hash_value": anchor.hash_value,
            "tx_id": anchor.tx_id,
            "backend": anchor.backend,
            "anchored_at": anchor.anchored_at,
            "payload": anchor.payload,
        }
        for anchor in anchors
    ]


@app.get("/anchors/{entity_type}/{entity_id}", response_model=VerificationOut)
def verify_anchored_record(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> VerificationOut:
    anchor = session.exec(
        select(BlockchainAnchor)
        .where(BlockchainAnchor.entity_type == entity_type)
        .where(BlockchainAnchor.entity_id == entity_id)
    ).first()
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor not found")
    return VerificationOut(**verify_anchor(session, anchor))


@app.post("/anchors/{entity_type}/{entity_id}/verify", response_model=VerificationOut)
def verify_anchored_record_post(entity_type: str, entity_id: int, session: Session = Depends(get_session)) -> VerificationOut:
    return verify_anchored_record(entity_type, entity_id, session)


@app.post("/demo/tamper/batches/{batch_id}")
def tamper_batch_record(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = get_batch_or_404(session, batch_id)
    batch.product_name = f"{batch.product_name} (tampered)"
    session.add(batch)
    session.commit()
    session.refresh(batch)
    anchor = session.exec(
        select(BlockchainAnchor)
        .where(BlockchainAnchor.entity_type == "batch")
        .where(BlockchainAnchor.entity_id == batch.id)
    ).first()
    verification = verify_anchor(session, anchor) if anchor else None
    return {
        "message": "Batch record modified for tamper-detection demo",
        "batch": BatchOut.model_validate(batch).model_dump(),
        "verification": verification,
    }


@app.get("/equipment", response_model=list[EquipmentOut])
def list_equipment(session: Session = Depends(get_session)) -> list[EquipmentOut]:
    result = []
    for equipment in session.exec(select(Equipment)).all():
        result.append(EquipmentOut.model_validate({**equipment.model_dump(), **equipment_metrics(equipment)}))
    return result


@app.post("/equipment/{equipment_id}/telemetry", response_model=EquipmentOut)
async def post_equipment_telemetry(equipment_id: int, payload: EquipmentTelemetry, session: Session = Depends(get_session)) -> EquipmentOut:
    equipment = get_equipment_or_404(session, equipment_id)
    equipment.status = payload.status
    equipment.runtime_minutes += payload.runtime_minutes
    equipment.downtime_minutes += payload.downtime_minutes
    equipment.total_count += payload.total_count
    equipment.good_count += payload.good_count
    equipment.reject_count += payload.reject_count
    equipment.last_seen_at = datetime.now(timezone.utc)
    equipment.metadata_json = {**equipment.metadata_json, **payload.metadata_json}
    session.add(equipment)
    session.commit()
    session.refresh(equipment)
    event = record_event(
        session,
        batch_id=None,
        event_type="equipment",
        actor=payload.actor,
        action="equipment_telemetry_received",
        payload={"equipment_id": equipment.id, "status": equipment.status, "total_count": equipment.total_count},
    )
    await manager.broadcast("equipment", {"kind": "equipment_update", "equipment_id": equipment.id, "event": EventOut.model_validate(event).model_dump()})
    return EquipmentOut.model_validate({**equipment.model_dump(), **equipment_metrics(equipment)})


@app.get("/mcp/tools")
def mcp_tools() -> dict:
    return {
        "name": "forge-mes-mcp",
        "tools": [
            {"name": "create_batch", "description": "Create a new manufacturing batch"},
            {"name": "start_batch", "description": "Start an existing batch with electronic signature"},
            {"name": "verify_anchor", "description": "Verify an anchored record against its blockchain hash"},
            {"name": "log_event", "description": "Append an immutable MES event"},
            {"name": "record_material", "description": "Create a material lot or genealogy record"},
            {"name": "list_recipes", "description": "List recipe masters and latest versions"},
            {"name": "get_batch", "description": "Retrieve a batch with recipe and event context"},
        ],
    }


@app.post("/mcp/execute")
async def mcp_execute(tool_call: MCPToolCall, session: Session = Depends(get_session)) -> dict:
    args = tool_call.arguments
    if tool_call.tool == "create_batch":
        return {"ok": True, "result": create_batch(BatchCreate(**args), session).model_dump()}
    if tool_call.tool == "start_batch":
        return {"ok": True, "result": (await start_batch(args["batch_id"], BatchTransition(**args["payload"]), session)).model_dump()}
    if tool_call.tool == "verify_anchor":
        return {"ok": True, "result": verify_anchored_record(args["entity_type"], args["entity_id"], session).model_dump()}
    if tool_call.tool == "log_event":
        return {"ok": True, "result": (await create_event(EventCreate(**args), session)).model_dump()}
    if tool_call.tool == "record_material":
        return {"ok": True, "result": (await create_material(MaterialCreate(**args), session)).model_dump()}
    if tool_call.tool == "list_recipes":
        return {"ok": True, "result": list_recipes(session)}
    if tool_call.tool == "get_batch":
        return {"ok": True, "result": get_batch(args["batch_id"], session)}
    raise HTTPException(status_code=404, detail="Unknown MCP tool")


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await manager.connect("events", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("events", websocket)


@app.websocket("/ws/equipment")
async def ws_equipment(websocket: WebSocket) -> None:
    await manager.connect("equipment", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("equipment", websocket)
