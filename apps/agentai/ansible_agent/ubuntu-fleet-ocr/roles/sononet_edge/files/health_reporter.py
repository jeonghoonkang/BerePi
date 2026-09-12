#!/usr/bin/env python3
"""Send a small, secret-free device heartbeat to the fleet API."""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


def unit_status(unit: str) -> dict[str, str]:
    properties = [
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainStatus",
        "ExecMainExitTimestamp",
    ]
    command = ["systemctl", "show", unit]
    for prop in properties:
        command.extend(["--property", prop])
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    values["query_status"] = str(result.returncode)
    return values


def ocr_summary(database_path: Path) -> dict[str, Any]:
    if not database_path.exists():
        return {"success": 0, "failed": 0, "last_processed_at": None}
    with sqlite3.connect(database_path) as database:
        counts = dict(database.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"))
        last = database.execute("SELECT MAX(processed_at) FROM jobs WHERE status='success'").fetchone()
    return {
        "success": int(counts.get("success", 0)),
        "failed": int(counts.get("failed", 0)),
        "last_processed_at": last[0] if last else None,
    }


def main() -> int:
    device_id = os.environ["SONONET_DEVICE_ID"]
    api_url = os.environ["FLEET_API_URL"].rstrip("/")
    token = os.environ["DEVICE_TOKEN"]
    sync_root = Path(os.environ.get("NEXTCLOUD_LOCAL_DIR", "/var/lib/sononet/sync"))
    usage = shutil.disk_usage(sync_root)
    revision_path = Path("/var/lib/sononet/config-revision")
    payload = {
        "device_id": device_id,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hostname": platform.node(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "config_revision": revision_path.read_text().strip() if revision_path.exists() else "unknown",
        "load_average": list(os.getloadavg()),
        "disk": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        },
        "ocr": ocr_summary(
            Path(os.environ.get("OCR_STATE_DB", "/var/lib/sononet/ocr-state.sqlite3"))
        ),
        "units": {
            name: unit_status(name)
            for name in (
                "sononet-pipeline.service",
                "sononet-ansible-pull.service",
                "sononet-pipeline.timer",
                "sononet-ansible-pull.timer",
            )
        },
    }
    request = urllib.request.Request(
        f"{api_url}/v1/heartbeat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    print(json.dumps({"event": "heartbeat_sent", "device_id": device_id, "response": body}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
