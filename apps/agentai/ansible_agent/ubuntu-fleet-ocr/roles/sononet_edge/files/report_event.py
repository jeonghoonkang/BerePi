#!/usr/bin/env python3
"""Send one best-effort operational event to the fleet API."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} EVENT SEVERITY MESSAGE", file=sys.stderr)
        return 2
    event, severity, message = sys.argv[1:]
    revision_path = Path("/var/lib/sononet/config-revision")
    payload = {
        "device_id": os.environ["SONONET_DEVICE_ID"],
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": event,
        "severity": severity,
        "message": message[:1000],
        "config_revision": (
            revision_path.read_text().strip() if revision_path.exists() else "unknown"
        ),
    }
    request = urllib.request.Request(
        f"{os.environ['FLEET_API_URL'].rstrip('/')}/v1/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['DEVICE_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
