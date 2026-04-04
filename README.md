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
- Mock PLC simulation
- Docker-first deployment

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
- `static/`: minimal operator UI
- `scripts/plc_simulator.py`: mock PLC telemetry loop
- `docker-compose.yml`: API, PostgreSQL, and simulator

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
- `log_event`
- `record_material`
- `list_recipes`
- `get_batch`
