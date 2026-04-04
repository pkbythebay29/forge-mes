import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class AnchorResult:
    backend: str
    tx_id: str
    payload: dict


def generate_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_record(data: dict, stored_hash: str) -> bool:
    return generate_hash(data) == stored_hash


class BaseBlockchainAnchor:
    backend = "base"

    def anchor(self, hash_value: str) -> AnchorResult:
        raise NotImplementedError


class MockBlockchainAnchor:
    backend = "mock"

    def anchor(self, hash_value: str) -> AnchorResult:
        stamp = datetime.now(timezone.utc).isoformat()
        tx_id = f"tx_{hash_value[:10]}"
        return AnchorResult(
            backend=self.backend,
            tx_id=tx_id,
            payload={"anchored_at": stamp, "ledger_entry": f"mock-ledger:{tx_id}"},
        )


def get_anchor_service() -> BaseBlockchainAnchor:
    backend = os.getenv("BLOCKCHAIN_BACKEND", "mock").lower()
    if backend == "mock":
        return MockBlockchainAnchor()
    return MockBlockchainAnchor()
