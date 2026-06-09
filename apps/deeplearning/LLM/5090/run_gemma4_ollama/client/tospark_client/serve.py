#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = 8091
APP_DIR = Path(__file__).resolve().parent
GPU_METRIC_KEYWORDS = (
    "gpu",
    "cuda",
    "kv_cache",
    "cache_usage",
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
)


def endpoint_origin(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("endpoint must include scheme and host")
    return f"{parsed.scheme}://{parsed.netloc}"


def read_http_text(url: str, timeout: int = 5) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read().decode("utf-8", errors="replace")
        return response.status, content_type, body


def interesting_metric_lines(metrics_text: str) -> list[str]:
    lines: list[str] = []
    for line in metrics_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lowered = stripped.lower()
        if any(keyword in lowered for keyword in GPU_METRIC_KEYWORDS):
            lines.append(stripped)
    return lines[:80]


def gpu_status_payload(endpoint: str) -> dict[str, Any]:
    origin = endpoint_origin(endpoint)
    probes: dict[str, Any] = {}
    summary: list[str] = [f"Origin: {origin}"]

    for path in ("/health", "/v1/models", "/metrics"):
        url = f"{origin}{path}"
        try:
            status, content_type, body = read_http_text(url)
            probes[path] = {
                "ok": 200 <= status < 300,
                "status": status,
                "content_type": content_type,
                "body_preview": body[:2000],
            }
        except urllib.error.HTTPError as exc:
            probes[path] = {"ok": False, "status": exc.code, "error": exc.read().decode("utf-8", errors="replace")[:1000]}
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            probes[path] = {"ok": False, "error": str(exc)}

    health = probes.get("/health", {})
    if health.get("ok"):
        summary.append("Health: reachable")
    else:
        summary.append(f"Health: unavailable ({health.get('status') or health.get('error')})")

    models = probes.get("/v1/models", {})
    if models.get("ok"):
        try:
            model_data = json.loads(str(models.get("body_preview") or "{}"))
            model_ids = [str(item.get("id")) for item in model_data.get("data", []) if isinstance(item, dict)]
            if model_ids:
                summary.append("Models: " + ", ".join(model_ids[:4]))
        except (TypeError, json.JSONDecodeError):
            summary.append("Models: reachable")

    metrics = probes.get("/metrics", {})
    metric_lines: list[str] = []
    if metrics.get("ok"):
        metric_lines = interesting_metric_lines(str(metrics.get("body_preview") or ""))
        if metric_lines:
            summary.append(f"GPU/vLLM metrics: {len(metric_lines)} relevant lines found")
        else:
            summary.append("GPU/vLLM metrics: /metrics reachable, no GPU-specific lines in preview")
    else:
        summary.append(f"GPU/vLLM metrics: unavailable ({metrics.get('status') or metrics.get('error')})")

    return {
        "endpoint": endpoint,
        "origin": origin,
        "summary": "\n".join(summary),
        "gpu_metric_lines": metric_lines,
        "probes": probes,
    }


class ToSparkHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path == "/api/gpu-status":
            self.handle_gpu_status()
            return
        if self.path != "/api/chat":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self.handle_chat()

    def handle_chat(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            endpoint = str(incoming.get("endpoint") or "").strip()
            payload = incoming.get("payload")
            if not endpoint:
                raise ValueError("endpoint is required")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")

            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "text/event-stream, application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                if payload.get("stream"):
                    self.send_response(HTTPStatus(response.status))
                    self.send_header("Content-Type", response.headers.get("Content-Type", "text/event-stream; charset=utf-8"))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    while True:
                        chunk = response.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    return
                body = response.read()
                status = HTTPStatus(response.status)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = HTTPStatus(exc.code)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_gpu_status(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            endpoint = str(incoming.get("endpoint") or "").strip()
            if not endpoint:
                raise ValueError("endpoint is required")
            self.send_json(gpu_status_payload(endpoint))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), ToSparkHandler)
    print(f"To Spark Client: http://{HOST}:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
