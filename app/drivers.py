from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.util import find_spec
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DriverState:
    driver_type: str
    name: str
    endpoint: str
    status: str = "disconnected"
    protocol: str = ""
    connected_at: str | None = None
    last_error: str | None = None
    last_message: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tag_map: list[dict[str, Any]] = field(default_factory=list)


class DriverRegistry:
    def __init__(self) -> None:
        self._drivers: dict[str, DriverState] = {
            "opcua": DriverState(
                driver_type="opcua",
                name="OPC UA Edge Driver",
                endpoint="opc.tcp://localhost:4840",
                protocol="OPC UA",
                capabilities=["browse", "read", "write", "subscribe", "simulate"],
                metadata={
                    "library_available": find_spec("asyncua") is not None,
                    "server_endpoint": "opc.tcp://localhost:4840",
                    "security_mode": "None",
                    "namespace": "2",
                },
                tag_map=[
                    {"source_tag": "ns=2;s=Batch.Id", "mes_field": "batch.batch_number", "type": "string", "direction": "read"},
                    {"source_tag": "ns=2;s=Batch.Status", "mes_field": "batch.status", "type": "string", "direction": "read"},
                    {"source_tag": "ns=2;s=Batch.StartCommand", "mes_field": "batch.start_command", "type": "boolean", "direction": "write"},
                    {"source_tag": "ns=2;s=Batch.StopCommand", "mes_field": "batch.stop_command", "type": "boolean", "direction": "write"},
                    {"source_tag": "ns=2;s=Batch.RecipeName", "mes_field": "recipe.name", "type": "string", "direction": "read"},
                    {"source_tag": "ns=2;s=Process.ActualQuantity", "mes_field": "batch.actual_quantity", "type": "float", "direction": "read"},
                    {"source_tag": "ns=2;s=Process.StepIndex", "mes_field": "batch.current_step", "type": "integer", "direction": "read"},
                    {"source_tag": "ns=2;s=Equipment.Mixer001.Runtime", "mes_field": "equipment.runtime_minutes", "type": "float", "direction": "read"},
                ],
            ),
            "mqtt": DriverState(
                driver_type="mqtt",
                name="MQTT Plant Driver",
                endpoint="mqtt://localhost:1883/forge-mes",
                protocol="MQTT",
                capabilities=["publish", "subscribe", "retain", "simulate"],
                metadata={"library_available": find_spec("paho.mqtt") is not None},
                tag_map=[
                    {"source_tag": "forge/line1/batch/id", "mes_field": "batch.batch_number", "type": "string", "direction": "subscribe"},
                    {"source_tag": "forge/line1/batch/start", "mes_field": "batch.start_command", "type": "boolean", "direction": "subscribe"},
                    {"source_tag": "forge/line1/batch/complete", "mes_field": "batch.complete_command", "type": "boolean", "direction": "subscribe"},
                    {"source_tag": "forge/line1/batch/step", "mes_field": "batch.current_step", "type": "integer", "direction": "subscribe"},
                    {"source_tag": "forge/line1/equipment/mix001/status", "mes_field": "equipment.status", "type": "string", "direction": "subscribe"},
                    {"source_tag": "forge/line1/equipment/mix001/counts/good", "mes_field": "equipment.good_count", "type": "integer", "direction": "subscribe"},
                ],
            ),
        }

    def list(self) -> list[DriverState]:
        return list(self._drivers.values())

    def get(self, driver_type: str) -> DriverState:
        if driver_type not in self._drivers:
            raise KeyError(driver_type)
        return self._drivers[driver_type]

    def connect(self, driver_type: str, endpoint: str | None = None) -> DriverState:
        driver = self.get(driver_type)
        if endpoint:
            driver.endpoint = endpoint
        driver.status = "connected"
        driver.connected_at = utcnow().isoformat()
        driver.last_error = None
        driver.last_message = {
            "summary": f"{driver.name} connected in lightweight mode",
            "endpoint": driver.endpoint,
            "timestamp": driver.connected_at,
        }
        return driver

    def disconnect(self, driver_type: str) -> DriverState:
        driver = self.get(driver_type)
        driver.status = "disconnected"
        driver.last_message = {
            "summary": f"{driver.name} disconnected",
            "timestamp": utcnow().isoformat(),
        }
        return driver

    def publish(self, driver_type: str, topic: str, payload: dict[str, Any]) -> DriverState:
        driver = self.get(driver_type)
        if driver.status != "connected":
            driver = self.connect(driver_type)
        driver.last_message = {
            "topic": topic,
            "payload": payload,
            "timestamp": utcnow().isoformat(),
        }
        return driver


registry = DriverRegistry()
