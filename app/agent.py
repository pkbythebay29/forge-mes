from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any


def summarize_batch_risk(batch: dict, events: list[dict], anchor: dict | None) -> str:
    if anchor and not anchor.get("verified", True):
        return "Integrity alert: the blockchain anchor no longer matches the batch record."
    if batch.get("status") == "created":
        return "Batch is ready to start once the operator confirms the electronic signature."
    if batch.get("status") == "in_progress":
        return "Batch is active. Verify the next instruction, capture actual values, and keep telemetry stable."
    if batch.get("status") == "completed":
        return "Batch is complete. Review genealogy, verify the anchor, and package the electronic batch record."
    if not events:
        return "No execution events yet. Start by logging operator actions and material consumption."
    return "Batch context looks stable."


def suggest_actions(batch: dict | None, anchor: dict | None, equipment: list[dict], drivers: list[dict]) -> list[str]:
    actions: list[str] = []
    if batch:
        if batch.get("status") == "created":
            actions.append("Start the batch with an electronic signature.")
        if batch.get("status") == "in_progress":
            actions.append("Log the next recipe step and confirm the observed value.")
        if batch.get("status") == "completed":
            actions.append("Run anchor verification and export the eBR summary.")
    if anchor and not anchor.get("verified", True):
        actions.append("Escalate tamper detection and quarantine downstream release actions.")
    if any(item.get("status") in {"stopped", "idle"} for item in equipment):
        actions.append("Check equipment state before dispatching the next production instruction.")
    if any(driver.get("status") != "connected" for driver in drivers):
        actions.append("Connect OPC UA and MQTT drivers to stream plant data into the MES.")
    return actions[:4]


def generate_agent_response(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    batch = context.get("batch")
    anchor = context.get("anchor")
    events = context.get("events", [])
    equipment = context.get("equipment", [])
    drivers = context.get("drivers", [])
    response = {
        "message": summarize_batch_risk(batch or {}, events, anchor),
        "actions": suggest_actions(batch, anchor, equipment, drivers),
        "reasoning": [
            "The assistant prefers verifiable MES actions over opaque automation.",
            "Recommendations favor traceability, electronic signatures, and anchor verification.",
            f"Prompt received: {prompt.strip() or 'No extra prompt supplied.'}",
        ],
        "provider": "builtin",
    }
    return response


def generate_ollama_response(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    body = {
        "model": model,
        "stream": False,
        "prompt": (
            "You are an MES copilot. Be concise, actionable, and grounded in the supplied JSON context.\n"
            f"Context:\n{json.dumps(context, indent=2, default=_json_default)}\n\n"
            f"User prompt:\n{prompt or 'What should I do next?'}"
        ),
    }
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "message": payload.get("response", "").strip() or "Ollama returned an empty response.",
            "actions": suggest_actions(context.get("batch"), context.get("anchor"), context.get("equipment", []), context.get("drivers", [])),
            "reasoning": [
                f"Served by local Ollama model {model}.",
                "Fallback deterministic actions are still included below for MES safety.",
            ],
            "provider": "ollama",
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        fallback = generate_agent_response(prompt, context)
        fallback["reasoning"].insert(0, f"Ollama unavailable, using builtin agent. Error: {exc}")
        return fallback


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
