#!/usr/bin/env python3
"""Send a small, secret-free device heartbeat to the fleet API."""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


def atomic_write(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".identity-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_instance_id(path: Path) -> str:
    # Independent of the user-entered device ID, IP address, and hostname.
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            value = path.read_text().strip()
            if not re.fullmatch(r"[a-f0-9]{32}", value):
                raise ValueError("Invalid local instance-id; restore this installation's backup")
            return value
        value = uuid.uuid4().hex
        atomic_write(path, value + "\n")
        return value


def record_id_check(response: dict[str, Any], device_id: str, instance_id: str,
                    status_path: Path) -> None:
    check = response.get("id_check")
    if not isinstance(check, dict) or check.get("status") not in ("clear", "conflict", "unverified"):
        check = {"status": "unverified", "checked_at": None}
    result = {**check, "device_id": device_id, "instance_id": instance_id}
    atomic_write(status_path, json.dumps(result) + "\n")
    if check["status"] == "conflict":
        print(json.dumps({"event": "device_id_conflict", **result}), file=sys.stderr)
    elif check["status"] == "unverified":
        print(json.dumps({"event": "device_id_check_unverified", **result}), file=sys.stderr)


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
    api_url = os.environ.get("FLEET_API_URL", "").rstrip("/")
    token = os.environ.get("DEVICE_TOKEN", "")
    state_root = Path("/var/lib/sononet")
    instance_id = get_instance_id(state_root / "instance-id")
    if not api_url or not token:
        record_id_check({}, device_id, instance_id, state_root / "id-conflict.json")
        print(json.dumps({"event": "heartbeat_skipped", "device_id": device_id,
                          "reason": "Set FLEET_API_URL and DEVICE_TOKEN to enable reporting and ID conflict checks"}))
        return 0
    sync_root = Path(os.environ.get("NEXTCLOUD_LOCAL_DIR", "/var/lib/sononet/sync"))
    usage = shutil.disk_usage(sync_root)
    revision_path = Path("/var/lib/sononet/config-revision")
    payload = {
        "device_id": device_id,
        "instance_id": instance_id,
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
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Invalid heartbeat response")
    except (urllib.error.URLError, OSError, ValueError):
        record_id_check({}, device_id, instance_id, state_root / "id-conflict.json")
        print(json.dumps({"event": "heartbeat_failed", "device_id": device_id}), file=sys.stderr)
        return 1
    record_id_check(body, device_id, instance_id, state_root / "id-conflict.json")
    print(json.dumps({"event": "heartbeat_sent", "device_id": device_id, "response": body}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
