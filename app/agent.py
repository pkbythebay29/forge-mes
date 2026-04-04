from __future__ import annotations

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
    }
    return response
