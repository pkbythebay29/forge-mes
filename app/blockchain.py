import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class AnchorResult:
    backend: str
    reference: str
    payload: dict


class MockBlockchainAnchor:
    backend = "mock"

    def anchor(self, event_hash: str) -> AnchorResult:
        stamp = datetime.now(timezone.utc).isoformat()
        reference = hashlib.sha256(f"{event_hash}:{stamp}".encode("utf-8")).hexdigest()
        return AnchorResult(
            backend=self.backend,
            reference=f"mock://anchor/{reference}",
            payload={"anchored_at": stamp},
        )


def get_anchor_service() -> MockBlockchainAnchor:
    backend = os.getenv("BLOCKCHAIN_BACKEND", "mock").lower()
    if backend == "mock":
        return MockBlockchainAnchor()
    return MockBlockchainAnchor()
