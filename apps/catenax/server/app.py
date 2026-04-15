"""Backend server for collaborative robot telemetry used by Catena-X EDC demos.

Endpoints
- GET /health
- POST /api/v1/cobot/telemetry
- GET /api/v1/cobot/telemetry/latest
- GET /api/v1/cobot/telemetry?limit=20

The server stores each accepted payload as JSON on disk so it can be exposed by
an EDC HttpData asset and replayed into an AAS bridge.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
LATEST_FILE = DATA_DIR / "latest.json"
REQUIRED_FIELDS = {
    "robot_id",
    "line_id",
    "station_id",
    "cycle_time_ms",
    "power_watts",
    "program_name",
    "status",
}

LOGGER = logging.getLogger("catenax.server")
STORE_LOCK = Lock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_telemetry(payload: Dict[str, Any]) -> List[str]:
    missing = sorted(field for field in REQUIRED_FIELDS if field not in payload)
    if missing:
        return [f"Missing required fields: {', '.join(missing)}"]

    errors: List[str] = []
    numeric_fields = ("cycle_time_ms", "power_watts")
    for field in numeric_fields:
        try:
            float(payload[field])
        except (TypeError, ValueError):
            errors.append(f"Field '{field}' must be numeric")

    for field in ("robot_id", "line_id", "station_id", "program_name", "status"):
        if not str(payload.get(field, "")).strip():
            errors.append(f"Field '{field}' must not be empty")

    return errors


def _sanitize_timestamp(value: str) -> str:
    return value.replace(":", "-").replace(".", "-")


def store_telemetry(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_data_dir()
    stored_at = utc_now()
    event = dict(payload)
    event["stored_at"] = stored_at

    day_dir = DATA_DIR / datetime.now(UTC).strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{_sanitize_timestamp(stored_at)}"
        f"_{str(event['robot_id']).replace('/', '_')}.json"
    )
    file_path = day_dir / filename

    with STORE_LOCK:
        file_path.write_text(
            json.dumps(event, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        LATEST_FILE.write_text(
            json.dumps(event, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    LOGGER.info("Stored telemetry robot_id=%s file=%s", event["robot_id"], file_path.name)
    return {
        "status": "stored",
        "stored_at": stored_at,
        "file": str(file_path.relative_to(APP_DIR)),
        "telemetry": event,
    }


def read_latest() -> Dict[str, Any] | None:
    if not LATEST_FILE.exists():
        return None
    return json.loads(LATEST_FILE.read_text(encoding="utf-8"))


def read_recent(limit: int) -> List[Dict[str, Any]]:
    ensure_data_dir()
    files = sorted(DATA_DIR.glob("*/*.json"), reverse=True)
    results: List[Dict[str, Any]] = []
    for path in files[:limit]:
        results.append(json.loads(path.read_text(encoding="utf-8")))
    return results


class TelemetryHandler(BaseHTTPRequestHandler):
    server_version = "CatenaXCobotTelemetry/1.0"

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b""
        if not raw:
            raise ValueError("Request body is empty")
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "catenax-cobot-telemetry",
                    "timestamp": utc_now(),
                },
            )
            return

        if parsed.path == "/api/v1/cobot/telemetry/latest":
            latest = read_latest()
            if latest is None:
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"error": "No telemetry has been stored yet"},
                )
                return
            self._send_json(HTTPStatus.OK, latest)
            return

        if parsed.path == "/api/v1/cobot/telemetry":
            query = parse_qs(parsed.query)
            try:
                limit = max(1, min(int(query.get("limit", ["20"])[0]), 200))
            except ValueError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Query parameter 'limit' must be an integer"},
                )
                return
            items = read_recent(limit)
            self._send_json(
                HTTPStatus.OK,
                {
                    "items": items,
                    "count": len(items),
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/cobot/telemetry":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON: {exc.msg}"})
            return

        errors = validate_telemetry(payload)
        if errors:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Validation failed", "details": errors},
            )
            return

        result = store_telemetry(payload)
        self._send_json(HTTPStatus.CREATED, result)

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def run_server(host: str, port: int) -> None:
    ensure_data_dir()
    httpd = ThreadingHTTPServer((host, port), TelemetryHandler)
    LOGGER.info("Serving on http://%s:%s", host, port)
    httpd.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Cobot telemetry JSON backend")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
