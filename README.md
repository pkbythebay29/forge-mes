# Forge MES

Forge MES is a minimal, agent-ready Manufacturing Execution System built with FastAPI, PostgreSQL, and a lightweight operator UI.

It demonstrates:

- Batch management with status tracking
- Recipe authoring with versioning and approval
- Electronic batch records with immutable event logging
- Material genealogy and traceability
- Equipment monitoring with simple OEE metrics
- REST and WebSocket interfaces
- MCP-compatible agent endpoints
- AI-style operator copilot responses grounded in MES context
- OPC UA and MQTT driver scaffolding for plant connectivity
- Mock PLC simulation
- Docker-first deployment

## Quick Start

Try the full demonstrator in a few minutes:

### Option 1: Docker

```bash
docker compose up --build
```

### Option 2: Local Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Optional: run the mock PLC simulator in a second terminal

```bash
python scripts/plc_simulator.py
```

Open:

- Operator UI: <http://localhost:8000/>
- API docs: <http://localhost:8000/docs>
- Technical guide: <http://localhost:8000/guide>
- Tag mapping guide: <http://localhost:8000/tag-mapping>

Default users:

- `operator` / `operator123`
- `qa` / `qa123`
- `agent` / `agent123`

Suggested demo flow:

1. Create a batch from the approved `Demo Blend` recipe.
2. Start the batch and log all 5 recipe steps.
3. Record a material lot and review the genealogy context.
4. Complete the batch and click `Verify Anchor`.
5. Run `Tamper Demo` and verify again to see the hash mismatch.

## Run

```bash
docker compose up --build
```

Open:

- API docs: <http://localhost:8000/docs>
- Operator UI: <http://localhost:8000/>

Default users:

- `operator` / `operator123`
- `qa` / `qa123`
- `agent` / `agent123`

## Architecture

MES Core -> Immutable Event Log -> Hashing Layer -> Blockchain Anchor Service -> Verification Context

Guiding rules:

- All write actions are logged
- Audit events are append-only and hash chained
- Electronic signatures require password confirmation
- Blockchain anchoring is cryptographic proof, not primary storage

## Components

- `app/main.py`: FastAPI app, REST routes, WebSockets, MCP endpoints
- `app/models.py`: SQLModel domain entities
- `app/services.py`: audit logging, OEE math, entity helpers
- `app/agent.py`: deterministic agent-assist layer for next actions and integrity guidance
- `app/drivers.py`: lightweight OPC UA and MQTT driver registry
- `static/`: minimal operator UI
- `scripts/plc_simulator.py`: mock PLC telemetry loop
- `docker-compose.yml`: API, PostgreSQL, and simulator

## Blockchain Layer

The MES uses blockchain anchoring as a verification layer for ALCOA++-style integrity:

- Full MES records stay in the database
- Only SHA-256 hashes of critical records are anchored
- Approved recipe versions are anchored
- Completed batch records are anchored
- Verification recomputes the current record hash and compares it to the stored blockchain anchor

Anchors store:

- `entity_type`
- `entity_id`
- `hash_value`
- `tx_id`
- `anchored_at`
- backend metadata

Default backend:

- Mock blockchain adapter returning deterministic `tx_<hash-prefix>` identifiers

## Verification and Tamper Demo

Verification endpoints:

- `GET /anchors`
- `GET /anchors/{entity_type}/{entity_id}`
- `POST /anchors/{entity_type}/{entity_id}/verify`

Tamper demo:

1. Create and complete a batch
2. Verify the batch anchor
3. Call `POST /demo/tamper/batches/{id}`
4. Verify again and observe `verified: false`

This demonstrates that the MES can be independently verified instead of blindly trusted.

## AI-Native UX

The operator UI now emphasizes:

- an AI copilot panel for next-best actions
- visible blockchain verification status
- industrial driver connection state

The agent layer does not invent hidden state. It responds from live MES context: batch status, event trail, anchor verification, equipment state, and driver connectivity.

## Industrial Drivers

Driver endpoints:

- `GET /drivers`
- `POST /drivers/opcua/connect`
- `POST /drivers/mqtt/connect`
- `POST /drivers/{driver_type}/publish`

These drivers are intentionally lightweight and pluggable. They are designed to show where plant connectivity fits in the architecture without forcing the MES to depend on a single vendor stack.

## SQLite fallback

If PostgreSQL is not available, the app falls back to local SQLite with `sqlite:///./forge_mes.db`.

## Mock PLC simulator

The simulator posts simple telemetry into `/equipment/{id}/telemetry` every 5 seconds. In Docker Compose it starts automatically.

## MCP-compatible interface

- `GET /mcp/tools`
- `POST /mcp/execute`

Available tools:

- `create_batch`
- `start_batch`
- `verify_anchor`
- `log_event`
- `record_material`
- `list_recipes`
- `get_batch`
