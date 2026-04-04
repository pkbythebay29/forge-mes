import json
import os
import random
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("FORGE_MES_URL", "http://localhost:8000")
EQUIPMENT_ID = int(os.getenv("FORGE_MES_EQUIPMENT_ID", "1"))


def post_telemetry() -> None:
    status = random.choice(["running", "idle", "running", "running", "stopped"])
    runtime = 1.0 if status == "running" else 0.0
    downtime = 1.0 if status in {"idle", "stopped"} else 0.0
    total = random.randint(2, 6) if status == "running" else 0
    reject = random.randint(0, 1) if total else 0
    payload = {
        "actor": "plc-simulator",
        "status": status,
        "runtime_minutes": runtime,
        "downtime_minutes": downtime,
        "total_count": total,
        "good_count": max(total - reject, 0),
        "reject_count": reject,
        "metadata_json": {"temperature_c": round(random.uniform(20.0, 24.0), 2)},
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/equipment/{EQUIPMENT_ID}/telemetry",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    while True:
        try:
            post_telemetry()
        except urllib.error.URLError as exc:
            print(f"Simulator retrying after error: {exc}")
        time.sleep(5)
