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


class DriverRegistry:
    def __init__(self) -> None:
        self._drivers: dict[str, DriverState] = {
            "opcua": DriverState(
                driver_type="opcua",
                name="OPC UA Edge Driver",
                endpoint="opc.tcp://localhost:4840",
                protocol="OPC UA",
                capabilities=["browse", "read", "write", "subscribe", "simulate"],
                metadata={"library_available": find_spec("asyncua") is not None},
            ),
            "mqtt": DriverState(
                driver_type="mqtt",
                name="MQTT Plant Driver",
                endpoint="mqtt://localhost:1883/forge-mes",
                protocol="MQTT",
                capabilities=["publish", "subscribe", "retain", "simulate"],
                metadata={"library_available": find_spec("paho.mqtt") is not None},
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
