#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import email.utils
import html
import json
import os
import posixpath
import queue
import re
import secrets
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("LLM_ROUTING_CONFIG", APP_DIR / "llm_targets.json"))
LOG_DIR = Path(os.getenv("LLM_ROUTING_LOG_DIR", APP_DIR / "logs"))
ACCESS_LOG_PATH = Path(os.getenv("LLM_ROUTING_ACCESS_LOG", LOG_DIR / "access.jsonl"))
ADMIN_PASSWORD_PATH = Path(os.getenv("LLM_ROUTING_ADMIN_PASSWORD_FILE", APP_DIR / "admin_password.conf"))
WEBDAV_CONFIG_PATH = Path(os.getenv("LLM_ROUTING_WEBDAV_CONFIG", APP_DIR / "webdav_settings.json"))
HOST = os.getenv("LLM_ROUTING_HOST", "0.0.0.0")
PORT = int(os.getenv("LLM_ROUTING_PORT", "4004"))
PROXY_HOST = os.getenv("LLM_ROUTING_PROXY_HOST", HOST)
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("LLM_ROUTING_TIMEOUT", "180"))
PROXY_TIMEOUT_SECONDS = int(os.getenv("LLM_ROUTING_PROXY_TIMEOUT", "180"))
QUEUE_MAX_PER_TARGET = int(os.getenv("LLM_ROUTING_QUEUE_MAX_PER_TARGET", "10"))
STATUS_REFRESH_SECONDS = int(os.getenv("LLM_ROUTING_STATUS_REFRESH_SECONDS", os.getenv("LLM_ROUTING_HEALTH_CHECK_INTERVAL_SECONDS", "10")))
HEALTH_CHECK_INTERVAL_SECONDS = STATUS_REFRESH_SECONDS
WEBDAV_DEFAULT_INTERVAL_MINUTES = int(os.getenv("LLM_ROUTING_WEBDAV_INTERVAL_MINUTES", "30"))
WEBDAV_MAX_INTERVAL_MINUTES = 24 * 60
WEBDAV_RETENTION_DAYS = int(os.getenv("LLM_ROUTING_WEBDAV_RETENTION_DAYS", "90"))
SESSION_COOKIE_NAME = "llm_routing_session"
SESSION_TTL_SECONDS = int(os.getenv("LLM_ROUTING_SESSION_TTL_SECONDS", "28800"))
STARTED_AT = time.time()
STATE_LOCK = threading.RLock()
TARGET_CURSOR = 0
CLIENT_STATS: dict[str, dict[str, Any]] = {}
TARGET_RUNTIME: dict[str, dict[str, Any]] = {}
RECENT_ACCESS: list[dict[str, Any]] = []
AUTH_SESSIONS: dict[str, float] = {}
TARGET_QUEUES: dict[str, queue.Queue["PromptJob"]] = {}
TARGET_WORKERS: dict[str, threading.Thread] = {}
PROXY_SERVERS: dict[str, tuple[ThreadingHTTPServer, threading.Thread, int]] = {}
WEBDAV_REPORT_STATE: dict[str, Any] = {
    "enabled": False,
    "status": "disabled",
    "last_sent_at": "",
    "last_error": "",
    "remote_paths": [],
    "destination_urls": [],
}
MAX_RECENT_ACCESS = 300
OPENAI_COMPATIBLE_API_TYPES = {"openai", "vllm"}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
GPU_METRIC_KEYWORDS = (
    "gpu",
    "cuda",
    "kv_cache",
    "cache_usage",
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
)
TARGET_HISTORY_LIMIT = 100


@dataclass
class LLMTarget:
    id: str
    name: str
    host: str
    port: int
    proxy_port: int = 0
    model: str = ""
    api_type: str = "ollama"
    gpu_info: str = ""
    gpu_type: str = ""
    selected_gpu: str = ""
    selected_gpu_label: str = ""
    access_id: str = ""
    password: str = ""
    enabled: bool = True
    weight: int = 1
    notes: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}".rstrip("/")


@dataclass
class TargetMetrics:
    total_prompts: int = 0
    pending_queue: int = 0
    active_requests: int = 0
    total_response_seconds: float = 0.0
    last_response_seconds: float = 0.0
    last_error: str = ""
    last_seen_at: str = ""
    last_health_at: float = 0.0
    status: str = "unknown"
    uptime: str = ""
    queue_state: str = "idle"
    last_health_probe_at: float = 0.0
    remote_gpu_info: str = ""
    remote_gpu_type: str = ""
    remote_ifconfig_ips: str = ""
    recent_response_seconds: list[float] = field(default_factory=list)

    @property
    def average_response_seconds(self) -> float:
        if self.total_prompts <= 0:
            return 0.0
        return self.total_response_seconds / self.total_prompts


@dataclass
class PromptJob:
    target: LLMTarget
    payload: dict[str, Any]
    client: str
    enqueued_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: Exception | None = None


class QueueFullError(Exception):
    pass


class PromptDispatchError(Exception):
    def __init__(self, message: str, dispatch_count: int = 0, target: LLMTarget | None = None) -> None:
        super().__init__(message)
        self.dispatch_count = max(0, int(dispatch_count))
        self.target = target


def dispatch_count_fields(count: int) -> dict[str, int]:
    normalized = max(0, int(count))
    return {
        "llm_dispatch_count": normalized,
        "prompt_forward_count": normalized,
    }


def dispatch_target_fields(target: LLMTarget | None) -> dict[str, Any]:
    if target is None:
        return {
            "llm_dispatch_model_number": None,
            "llm_dispatch_target": None,
        }
    enabled_targets = [item for item in load_targets() if item.enabled]
    number = next((index + 1 for index, item in enumerate(enabled_targets) if item.id == target.id), None)
    target_info = {
        "number": number,
        "target_id": target.id,
        "target_name": target.name,
        "target_host": target.host,
        "target_port": target.port,
        "target_url": target.base_url,
        "api_type": target.api_type,
        "model": target.model,
        "selected_gpu": target.selected_gpu,
        "selected_gpu_label": target.selected_gpu_label,
        "selected_gpu_device": selected_gpu_device(target),
    }
    return {
        "llm_dispatch_model_number": number,
        "llm_dispatch_target": target_info,
    }


def queue_state_text(active_requests: int, pending_queue: int) -> str:
    if active_requests > 0:
        return "active"
    if pending_queue > 0:
        return "pending"
    return "idle"


def now_text() -> str:
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def seconds_to_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}D {hours}H {minutes}M"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "disabled"}:
            return False
    return bool(value)


def ensure_admin_password() -> None:
    if os.getenv("LLM_ROUTING_ADMIN_PASSWORD"):
        return
    if ADMIN_PASSWORD_PATH.exists():
        return
    ADMIN_PASSWORD_PATH.write_text("change-me-now\n", encoding="utf-8")
    try:
        os.chmod(ADMIN_PASSWORD_PATH, 0o600)
    except OSError:
        pass


def parse_admin_passwords(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def admin_passwords() -> list[str]:
    value = os.getenv("LLM_ROUTING_ADMIN_PASSWORD", "").strip()
    if value:
        return parse_admin_passwords(value)
    ensure_admin_password()
    try:
        passwords = parse_admin_passwords(ADMIN_PASSWORD_PATH.read_text(encoding="utf-8"))
    except OSError:
        passwords = []
    return passwords or ["change-me-now"]


def valid_admin_password(supplied: str) -> bool:
    if not supplied:
        return False
    return any(secrets.compare_digest(supplied, password) for password in admin_passwords())


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with STATE_LOCK:
        AUTH_SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return token


def valid_session(token: str) -> bool:
    if not token:
        return False
    with STATE_LOCK:
        expires_at = AUTH_SESSIONS.get(token, 0)
        if expires_at <= time.time():
            AUTH_SESSIONS.pop(token, None)
            return False
        AUTH_SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
        return True


def prompt_api_password(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> str:
    auth = str(handler.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1].strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded = ""
        if ":" in decoded:
            return decoded.split(":", 1)[1]
    for header_name in ("X-LLM-Routing-Password", "X-API-Key"):
        value = str(handler.headers.get(header_name) or "").strip()
        if value:
            return value
    return str(payload.get("api_password") or payload.get("password") or "").strip()


def prompt_api_authenticated(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> bool:
    if valid_session(getattr(handler, "session_token")()):
        return True
    supplied = prompt_api_password(handler, payload)
    return valid_admin_password(supplied)


def load_targets() -> list[LLMTarget]:
    raw = load_json(CONFIG_PATH, {"targets": []})
    targets: list[LLMTarget] = []
    for item in raw.get("targets", []):
        if not isinstance(item, dict):
            continue
        try:
            targets.append(
                LLMTarget(
                    id=str(item.get("id") or uuid.uuid4().hex),
                    name=str(item.get("name") or item.get("model") or "LLM"),
                    host=str(item.get("host") or "127.0.0.1"),
                    port=int(item.get("port") or 11434),
                    proxy_port=int(item.get("proxy_port") or 0),
                    model=str(item.get("model") or ""),
                    api_type=str(item.get("api_type") or "ollama"),
                    gpu_info=str(item.get("gpu_info") or ""),
                    gpu_type=str(item.get("gpu_type") or ""),
                    selected_gpu=str(item.get("selected_gpu") or ""),
                    selected_gpu_label=str(item.get("selected_gpu_label") or ""),
                    access_id=str(item.get("access_id") or ""),
                    password=str(item.get("password") or ""),
                    enabled=bool_value(item.get("enabled"), True),
                    weight=max(1, int(item.get("weight") or 1)),
                    notes=str(item.get("notes") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return targets


def target_identity_key(target: LLMTarget | dict[str, Any]) -> str:
    if isinstance(target, LLMTarget):
        api_type = target.api_type
        host = target.host
        port = target.port
        model = target.model
        selected_gpu = target.selected_gpu
    else:
        api_type = str(target.get("api_type") or "ollama")
        host = str(target.get("host") or "")
        port = str(target.get("port") or "")
        model = str(target.get("model") or "")
        selected_gpu = str(target.get("selected_gpu") or "")
    return "|".join(
        [
            api_type.strip().lower(),
            host.strip().lower(),
            str(port).strip(),
            model.strip().lower(),
            selected_gpu.strip().lower(),
        ]
    )


def target_history_item(target: LLMTarget) -> dict[str, Any]:
    item = dict(target.__dict__)
    item.pop("id", None)
    item["history_key"] = target_identity_key(target)
    item["saved_at"] = now_text()
    return item


def load_target_history() -> list[dict[str, Any]]:
    raw = load_json(CONFIG_PATH, {"targets": [], "target_history": []})
    history = raw.get("target_history", [])
    if not isinstance(history, list):
        return []
    return [item for item in history if isinstance(item, dict)]


def duplicate_target_ids(targets: list[LLMTarget]) -> set[str]:
    ids_by_key: dict[str, list[str]] = {}
    for target in targets:
        key = target_identity_key(target)
        ids_by_key.setdefault(key, []).append(target.id)
    return {target_id for ids in ids_by_key.values() if len(ids) > 1 for target_id in ids}


def save_targets(targets: list[LLMTarget]) -> None:
    raw = load_json(CONFIG_PATH, {"targets": [], "target_history": []})
    history = raw.get("target_history", [])
    if not isinstance(history, list):
        history = []
    save_json(CONFIG_PATH, {"targets": [target.__dict__ for target in targets], "target_history": history})


def remember_target_history(target: LLMTarget) -> None:
    raw = load_json(CONFIG_PATH, {"targets": [], "target_history": []})
    targets_raw = raw.get("targets", [])
    if not isinstance(targets_raw, list):
        targets_raw = []
    history = raw.get("target_history", [])
    if not isinstance(history, list):
        history = []
    new_item = target_history_item(target)
    history = [
        item
        for item in history
        if isinstance(item, dict) and target_identity_key(item) != new_item["history_key"]
    ]
    history.insert(0, new_item)
    save_json(CONFIG_PATH, {"targets": targets_raw, "target_history": history[:TARGET_HISTORY_LIMIT]})


def ensure_default_config() -> None:
    if CONFIG_PATH.exists():
        return
    save_targets(
        [
            LLMTarget(
                id=uuid.uuid4().hex,
                name="Local Ollama",
                host="127.0.0.1",
                port=11434,
                proxy_port=0,
                model="llama3.1",
                api_type="ollama",
                gpu_info="local GPU",
                gpu_type="auto",
                enabled=False,
                notes="Enable and edit this target from the web UI.",
            )
        ]
    )


def metric_for(target_id: str) -> TargetMetrics:
    raw = TARGET_RUNTIME.setdefault(target_id, TargetMetrics().__dict__)
    metric = TargetMetrics(**{key: raw.get(key, getattr(TargetMetrics(), key)) for key in TargetMetrics().__dict__})
    TARGET_RUNTIME[target_id] = metric.__dict__
    return metric


def store_metric(target_id: str, metric: TargetMetrics) -> None:
    TARGET_RUNTIME[target_id] = metric.__dict__


def target_auth_headers(target: LLMTarget) -> dict[str, str]:
    if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
        token = target.password or target.access_id
        return {"Authorization": f"Bearer {token}"} if token else {}
    if target.access_id:
        token = base64.b64encode(f"{target.access_id}:{target.password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}
    return {}


def request_json(
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    request_headers.update(headers or {})
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers, method="GET" if payload is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:500] if body else exc.reason
        raise RuntimeError(f"HTTP {exc.code} from backend: {detail}") from exc
    if not body.strip():
        return {}
    return json.loads(body)


def request_text(url: str, timeout: int = 5, headers: dict[str, str] | None = None) -> tuple[int, str, str]:
    request_headers = {"Accept": "application/json, text/plain, */*"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, response.headers.get("Content-Type", ""), body


def target_by_id(target_id: str) -> LLMTarget | None:
    for target in load_targets():
        if target.id == target_id:
            return target
    return None


def proxy_request(
    target: LLMTarget,
    method: str,
    path: str,
    body: bytes | None,
    incoming_headers: dict[str, str],
) -> tuple[int, dict[str, str], bytes]:
    url = f"{target.base_url}{path}"
    headers: dict[str, str] = {}
    for key, value in incoming_headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS or lowered in {"host", "content-length"}:
            continue
        headers[key] = value
    headers.update(target_auth_headers(target))
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_SECONDS) as response:
            response_body = response.read()
            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length"
            }
            return response.status, response_headers, response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        response_headers = {
            key: value
            for key, value in exc.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length"
        }
        return exc.code, response_headers, response_body


def proxy_handler_for(target_id: str) -> type[BaseHTTPRequestHandler]:
    class OllamaProxyHandler(BaseHTTPRequestHandler):
        server_version = "LLMRoutingOllamaProxy/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def send_proxy_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, HEAD, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-LLM-Routing-Password, X-API-Key")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def proxy_any(self) -> None:
            target = target_by_id(target_id)
            if target is None or not target.enabled:
                self.send_proxy_response(HTTPStatus.NOT_FOUND, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"target not found"}')
                return
            if target.api_type != "ollama":
                self.send_proxy_response(HTTPStatus.BAD_REQUEST, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"proxy_port is only supported for ollama targets"}')
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else None
            try:
                status, headers, response_body = proxy_request(target, self.command, self.path, body, dict(self.headers.items()))
                record_access(
                    {
                        "client": self.client_address[0] if self.client_address else "unknown",
                        "status": "proxy",
                        "method": self.command,
                        "path": self.path,
                        "proxy_port": target.proxy_port,
                        **access_target_fields(target),
                    }
                )
                self.send_proxy_response(status, headers, response_body)
            except Exception as exc:  # noqa: BLE001
                payload = json.dumps({"ok": False, "error": f"Proxy request failed: {exc}"}, ensure_ascii=False).encode("utf-8")
                self.send_proxy_response(HTTPStatus.BAD_GATEWAY, {"Content-Type": "application/json; charset=utf-8"}, payload)

        def do_GET(self) -> None:
            self.proxy_any()

        def do_POST(self) -> None:
            self.proxy_any()

        def do_PUT(self) -> None:
            self.proxy_any()

        def do_DELETE(self) -> None:
            self.proxy_any()

        def do_HEAD(self) -> None:
            self.proxy_any()

        def do_OPTIONS(self) -> None:
            self.send_proxy_response(HTTPStatus.NO_CONTENT, {}, b"")

    return OllamaProxyHandler


def sync_ollama_proxy_servers() -> None:
    targets = load_targets()
    desired = {
        target.id: target
        for target in targets
        if target.enabled and target.api_type == "ollama" and target.proxy_port > 0
    }
    to_stop: list[ThreadingHTTPServer] = []
    with STATE_LOCK:
        for target_id, (server, thread, port) in list(PROXY_SERVERS.items()):
            target = desired.get(target_id)
            if target is None or target.proxy_port != port or not thread.is_alive():
                to_stop.append(server)
                PROXY_SERVERS.pop(target_id, None)
        for target_id, target in desired.items():
            if target_id in PROXY_SERVERS:
                continue
            try:
                server = ThreadingHTTPServer((PROXY_HOST, target.proxy_port), proxy_handler_for(target_id))
            except OSError as exc:
                print(f"Ollama proxy for {target.name} failed on {PROXY_HOST}:{target.proxy_port}: {exc}", flush=True)
                continue
            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
                name=f"llm-routing-ollama-proxy-{target_id}",
            )
            PROXY_SERVERS[target_id] = (server, thread, target.proxy_port)
            thread.start()
            print(
                f"Ollama proxy for {target.name} listening on http://{PROXY_HOST}:{target.proxy_port} -> {target.base_url}",
                flush=True,
            )
    for server in to_stop:
        server.shutdown()
        server.server_close()


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


def metric_number(metrics_text: str, metric_name: str) -> float | None:
    pattern = re.compile(rf"^{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+([-+]?\d+(?:\.\d+)?)$")
    for line in metrics_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            return float(match.group(1))
    return None


def probe_openai_compatible_target(target: LLMTarget) -> dict[str, Any]:
    probes: dict[str, Any] = {}
    summary: list[str] = [f"Origin: {target.base_url}"]
    headers = target_auth_headers(target)
    metrics_body = ""

    for path in ("/health", "/v1/models", "/metrics"):
        url = f"{target.base_url}{path}"
        try:
            status, content_type, body = request_text(url, timeout=5, headers=headers)
            probes[path] = {
                "ok": 200 <= status < 300,
                "status": status,
                "content_type": content_type,
                "body_preview": body[:4000],
            }
            if path == "/metrics":
                metrics_body = body
        except urllib.error.HTTPError as exc:
            probes[path] = {"ok": False, "status": exc.code, "error": exc.read().decode("utf-8", errors="replace")[:1000]}
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            probes[path] = {"ok": False, "error": str(exc)}

    health = probes.get("/health", {})
    if health.get("ok"):
        summary.append("Health: reachable")
    else:
        summary.append(f"Health: unavailable ({health.get('status') or health.get('error')})")

    model_ids: list[str] = []
    models = probes.get("/v1/models", {})
    if models.get("ok"):
        try:
            model_data = json.loads(str(models.get("body_preview") or "{}"))
            model_ids = [str(item.get("id")) for item in model_data.get("data", []) if isinstance(item, dict) and item.get("id")]
            if model_ids:
                summary.append("Models: " + ", ".join(model_ids[:4]))
            else:
                summary.append("Models: reachable")
        except (TypeError, json.JSONDecodeError):
            summary.append("Models: reachable")

    metric_lines = interesting_metric_lines(metrics_body)
    running = metric_number(metrics_body, "vllm:num_requests_running")
    waiting = metric_number(metrics_body, "vllm:num_requests_waiting")
    if metric_lines:
        summary.append(f"GPU/vLLM metrics: {len(metric_lines)} relevant lines found")
    elif probes.get("/metrics", {}).get("ok"):
        summary.append("GPU/vLLM metrics: /metrics reachable, no GPU-specific lines in preview")
    else:
        metrics = probes.get("/metrics", {})
        summary.append(f"GPU/vLLM metrics: unavailable ({metrics.get('status') or metrics.get('error')})")

    return {
        "ok": bool(health.get("ok") or models.get("ok")),
        "summary": "\n".join(summary),
        "model_ids": model_ids,
        "gpu_metric_lines": metric_lines,
        "num_requests_running": running,
        "num_requests_waiting": waiting,
        "probes": probes,
    }


def target_health(target: LLMTarget) -> dict[str, Any]:
    try:
        if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
            data = probe_openai_compatible_target(target)
            return {"ok": bool(data.get("ok")), "data": data}
        try:
            data = request_json(f"{target.base_url}/api/tags", timeout=5, headers=target_auth_headers(target))
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            data = request_json(f"{target.base_url}/health", timeout=5, headers=target_auth_headers(target))
        return {"ok": True, "data": data}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def parse_model_ids(target: LLMTarget, data: dict[str, Any]) -> list[str]:
    if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
        values = data.get("data", [])
        return sorted({str(item.get("id")) for item in values if isinstance(item, dict) and item.get("id")})
    values = data.get("models", [])
    if values and all(isinstance(item, str) for item in values):
        return sorted({str(item) for item in values if str(item)})
    names = {str(item.get("name")) for item in values if isinstance(item, dict) and item.get("name")}
    names.update(str(item.get("model")) for item in values if isinstance(item, dict) and item.get("model"))
    if data.get("model"):
        names.add(str(data.get("model")))
    if data.get("default_model"):
        names.add(str(data.get("default_model")))
    return sorted(name for name in names if name)


def parse_gpus(data: dict[str, Any]) -> list[dict[str, str]]:
    values = data.get("gpus") if isinstance(data.get("gpus"), list) else []
    gpus: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        index = item.get("index") if item.get("index") is not None else item.get("id")
        value = str(index if index is not None else "").strip()
        name = str(item.get("name") or value or "GPU").strip()
        label = f"GPU {value}: {name}" if value else name
        memory = item.get("memory_total_mb")
        if isinstance(memory, (int, float)) and memory > 0:
            label = f"{label} ({int(memory)} MB)"
        gpus.append({"value": value, "label": label, "name": name})
    return gpus


def gpu_label_matches_selection(label: str, selected_gpu: str) -> bool:
    if not selected_gpu:
        return False
    match = re.match(r"^\s*GPU\s+([^:\s]+)", str(label or ""), flags=re.IGNORECASE)
    return bool(match and match.group(1) == selected_gpu)


def selected_gpu_label_from_health(target: LLMTarget, data: dict[str, Any]) -> str:
    if not target.selected_gpu:
        return ""
    for gpu in parse_gpus(data):
        if gpu.get("value") == target.selected_gpu:
            return str(gpu.get("label") or "")
    return ""


def fetch_target_models(target: LLMTarget) -> list[str]:
    if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
        data = request_json(f"{target.base_url}/v1/models", timeout=8, headers=target_auth_headers(target))
    else:
        try:
            data = request_json(f"{target.base_url}/api/tags", timeout=8, headers=target_auth_headers(target))
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            data = request_json(f"{target.base_url}/health", timeout=8, headers=target_auth_headers(target))
    return parse_model_ids(target, data)


def fetch_target_options(target: LLMTarget) -> dict[str, Any]:
    models = fetch_target_models(target)
    gpus: list[dict[str, str]] = []
    try:
        health = request_json(f"{target.base_url}/health", timeout=8, headers=target_auth_headers(target))
        gpus = parse_gpus(health)
        if not models:
            models = parse_model_ids(target, health)
    except Exception:
        pass
    return {"models": models, "gpus": gpus}


def target_from_lookup_payload(payload: dict[str, Any]) -> LLMTarget:
    host = str(payload.get("host") or "").strip()
    if not host:
        raise ValueError("host is required.")
    port = int(payload.get("port") or 0)
    if port <= 0:
        raise ValueError("port is required.")
    return LLMTarget(
        id=str(payload.get("id") or "lookup"),
        name=str(payload.get("name") or "lookup"),
        host=host,
        port=port,
        proxy_port=int(payload.get("proxy_port") or 0),
        model=str(payload.get("model") or ""),
        api_type=str(payload.get("api_type") or "ollama").strip(),
        selected_gpu=str(payload.get("selected_gpu") or "").strip(),
        selected_gpu_label=str(payload.get("selected_gpu_label") or "").strip(),
        access_id=str(payload.get("access_id") or "").strip(),
        password=str(payload.get("password") or ""),
    )


def prompt_text(payload: dict[str, Any]) -> str:
    prompt = str(payload.get("prompt") or "")
    if prompt.strip():
        return prompt
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    lines: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user")
        content = message.get("content")
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
            if parts:
                lines.append(f"{role}: {' '.join(parts)}")
    return "\n".join(lines)


def build_backend_payload(target: LLMTarget, request_payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    prompt = prompt_text(request_payload)
    model = str(request_payload.get("model") or target.model or "")
    if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
        messages = request_payload.get("messages")
        if not isinstance(messages, list):
            messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        for key in ("temperature", "max_tokens", "top_p"):
            if key in request_payload:
                payload[key] = request_payload[key]
        return f"{target.base_url}/v1/chat/completions", payload

    payload = dict(request_payload)
    payload["prompt"] = prompt
    if model:
        payload["model"] = model
    if target.selected_gpu:
        payload["selected_gpu"] = target.selected_gpu
    payload["stream"] = False
    payload.pop("target_id", None)
    payload.pop("client_id", None)
    payload.pop("user_id", None)
    payload.pop("password", None)
    payload.pop("api_password", None)
    return f"{target.base_url}/api/generate", payload


def normalize_backend_response(target: LLMTarget, data: dict[str, Any]) -> dict[str, Any]:
    if target.api_type in OPENAI_COMPATIBLE_API_TYPES:
        content = ""
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else {}
            if isinstance(message, dict):
                content = str(message.get("content") or "")
        return {"response": content, "raw": data}
    return {"response": str(data.get("response") or data.get("message") or ""), "raw": data}


def selected_gpu_device(target: LLMTarget) -> str:
    if target.selected_gpu_label and (not target.selected_gpu or gpu_label_matches_selection(target.selected_gpu_label, target.selected_gpu)):
        return target.selected_gpu_label
    if target.selected_gpu:
        gpu_names = [part.strip() for part in target.gpu_info.split(",") if part.strip()]
        detail = ""
        if target.selected_gpu.isdigit():
            index = int(target.selected_gpu)
            if 0 <= index < len(gpu_names):
                detail = gpu_names[index]
        if not detail:
            detail = " ".join(part for part in (target.gpu_type, target.gpu_info) if part).strip()
        return f"GPU {target.selected_gpu}: {detail}" if detail else f"GPU {target.selected_gpu}"
    detail = " ".join(part for part in (target.gpu_type, target.gpu_info) if part).strip()
    return detail or "auto"


def sync_queue_metric(target_id: str) -> None:
    with STATE_LOCK:
        q = TARGET_QUEUES.get(target_id)
        metric = metric_for(target_id)
        metric.pending_queue = q.qsize() if q else 0
        metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
        store_metric(target_id, metric)


def target_queue(target_id: str) -> queue.Queue[PromptJob]:
    with STATE_LOCK:
        q = TARGET_QUEUES.get(target_id)
        if q is None:
            q = queue.Queue(maxsize=QUEUE_MAX_PER_TARGET)
            TARGET_QUEUES[target_id] = q
        worker = TARGET_WORKERS.get(target_id)
        if worker is None or not worker.is_alive():
            worker = threading.Thread(target=target_worker, args=(target_id, q), daemon=True, name=f"llm-routing-worker-{target_id}")
            TARGET_WORKERS[target_id] = worker
            worker.start()
        return q


def ensure_target_queues(targets: list[LLMTarget]) -> None:
    for target in targets:
        if target.enabled:
            target_queue(target.id)


def scheduler_load(target: LLMTarget) -> tuple[int, int, float]:
    q = TARGET_QUEUES.get(target.id)
    pending = q.qsize() if q else 0
    metric = metric_for(target.id)
    active = metric.active_requests
    busy = 1 if active or pending else 0
    weighted_load = (pending + active) / max(1, target.weight)
    return busy, pending + active, weighted_load


def choose_target(payload: dict[str, Any]) -> LLMTarget:
    global TARGET_CURSOR
    targets = [target for target in load_targets() if target.enabled]
    if not targets:
        raise ValueError("No enabled LLM targets are configured.")
    ensure_target_queues(targets)
    requested_id = str(payload.get("target_id") or "")
    if requested_id:
        for target in targets:
            if target.id == requested_id:
                return target
        raise ValueError(f"Requested target_id is not enabled or does not exist: {requested_id}")

    with STATE_LOCK:
        candidates: list[tuple[tuple[int, int, float], LLMTarget]] = []
        for target in targets:
            q = TARGET_QUEUES.get(target.id)
            pending = q.qsize() if q else 0
            if pending >= QUEUE_MAX_PER_TARGET:
                continue
            candidates.append((scheduler_load(target), target))
        if not candidates:
            raise QueueFullError(f"All target queues are full. max_per_target={QUEUE_MAX_PER_TARGET}")
        best_score = min(score for score, _ in candidates)
        best = [target for score, target in candidates if score == best_score]
        target = best[TARGET_CURSOR % len(best)]
        TARGET_CURSOR += 1
        return target


def record_access(event: dict[str, Any]) -> None:
    event = {"time": now_text(), **event}
    with STATE_LOCK:
        RECENT_ACCESS.insert(0, event)
        del RECENT_ACCESS[MAX_RECENT_ACCESS:]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with ACCESS_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def client_key(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> str:
    client_id = str(payload.get("client_id") or payload.get("user_id") or "")
    if client_id:
        return client_id
    return handler.client_address[0] if handler.client_address else "unknown"


def update_client_stats(client: str, response_seconds: float) -> None:
    with STATE_LOCK:
        stats = CLIENT_STATS.setdefault(
            client,
            {"client": client, "prompt_count": 0, "first_seen": time.time(), "last_seen": time.time(), "recent_times": []},
        )
        stats["prompt_count"] += 1
        stats["last_seen"] = time.time()
        recent = stats.setdefault("recent_times", [])
        recent.append(time.time())
        del recent[:-120]
        stats["last_response_seconds"] = response_seconds


def access_target_fields(target: LLMTarget) -> dict[str, Any]:
    return {
        "target": target.name,
        "target_id": target.id,
        "target_host": target.host,
        "target_port": target.port,
        "target_url": target.base_url,
        "api_type": target.api_type,
        "model": target.model,
        "gpu_type": target.gpu_type,
        "gpu_info": target.gpu_info,
        "selected_gpu": target.selected_gpu,
        "selected_gpu_label": target.selected_gpu_label,
        "selected_gpu_device": selected_gpu_device(target),
    }


def target_worker(target_id: str, q: queue.Queue[PromptJob]) -> None:
    while True:
        job = q.get()
        job.started_at = time.time()
        sync_queue_metric(target_id)
        try:
            job.result = execute_prompt(job.target, job.payload, job.client)
        except Exception as exc:  # noqa: BLE001
            job.error = exc
        finally:
            job.done.set()
            q.task_done()
            sync_queue_metric(target_id)


def execute_prompt(target: LLMTarget, payload: dict[str, Any], client: str) -> dict[str, Any]:
    with STATE_LOCK:
        metric = metric_for(target.id)
        metric.active_requests += 1
        metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
        store_metric(target.id, metric)

    started = time.time()
    try:
        url, backend_payload = build_backend_payload(target, payload)
        data = request_json(
            url,
            backend_payload,
            int(payload.get("timeout") or DEFAULT_TIMEOUT_SECONDS),
            headers=target_auth_headers(target),
        )
        elapsed = time.time() - started
        normalized = normalize_backend_response(target, data)
        with STATE_LOCK:
            metric = metric_for(target.id)
            metric.total_prompts += 1
            metric.total_response_seconds += elapsed
            metric.last_response_seconds = elapsed
            metric.last_error = ""
            metric.last_seen_at = now_text()
            metric.status = "ok"
            metric.active_requests = max(0, metric.active_requests - 1)
            q = TARGET_QUEUES.get(target.id)
            metric.pending_queue = q.qsize() if q else metric.pending_queue
            metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
            recent = metric.recent_response_seconds
            recent.append(elapsed)
            del recent[:-30]
            store_metric(target.id, metric)
        update_client_stats(client, elapsed)
        record_access(
            {
                "client": client,
                "status": "ok",
                "response_seconds": round(elapsed, 3),
                **access_target_fields(target),
            }
        )
        return {
            "ok": True,
            "target_id": target.id,
            "target_name": target.name,
            "target_host": target.host,
            "target_port": target.port,
            "target_url": target.base_url,
            "api_type": target.api_type,
            "model": target.model,
            "gpu_type": target.gpu_type,
            "gpu_info": target.gpu_info,
            "selected_gpu": target.selected_gpu,
            "selected_gpu_label": target.selected_gpu_label,
            "selected_gpu_device": selected_gpu_device(target),
            **dispatch_count_fields(1),
            **dispatch_target_fields(target),
            "response_seconds": elapsed,
            **normalized,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - started
        with STATE_LOCK:
            metric = metric_for(target.id)
            metric.last_error = str(exc)
            metric.status = "error"
            metric.active_requests = max(0, metric.active_requests - 1)
            q = TARGET_QUEUES.get(target.id)
            metric.pending_queue = q.qsize() if q else max(0, metric.pending_queue)
            metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
            store_metric(target.id, metric)
        record_access(
            {
                "client": client,
                "status": "error",
                "error": str(exc),
                "response_seconds": round(elapsed, 3),
                **access_target_fields(target),
            }
        )
        raise


def route_prompt(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> dict[str, Any]:
    if not prompt_text(payload).strip():
        raise ValueError("prompt or messages is required.")
    target = choose_target(payload)
    # Freeze the routing metadata as soon as the target is selected.  The
    # configured target list may be edited while a long-running LLM request is
    # in flight, but the response must describe the model that was actually
    # selected for this dispatch.
    dispatch_metadata = dispatch_target_fields(target)
    client = client_key(handler, payload)
    q = target_queue(target.id)
    job = PromptJob(target=target, payload=dict(payload), client=client)
    try:
        q.put_nowait(job)
    except queue.Full as exc:
        sync_queue_metric(target.id)
        raise QueueFullError(f"Queue is full for target {target.name}. max_per_target={QUEUE_MAX_PER_TARGET}") from exc

    sync_queue_metric(target.id)
    queued_count = q.qsize()
    backend_timeout = int(payload.get("timeout") or DEFAULT_TIMEOUT_SECONDS)
    wait_timeout = int(payload.get("request_timeout") or (backend_timeout * max(1, queued_count) + 10))
    if not job.done.wait(wait_timeout):
        dispatch_count = 1 if job.started_at else 0
        raise PromptDispatchError(
            f"Queued prompt timed out after {wait_timeout}s for target {target.name}.",
            dispatch_count,
            target,
        )
    if job.error is not None:
        dispatch_count = 1 if job.started_at else 0
        raise PromptDispatchError(f"Backend request failed: {job.error}", dispatch_count, target) from job.error
    result = dict(job.result or {})
    result.update(dispatch_count_fields(int(result.get("llm_dispatch_count") or 1)))
    result.update(dispatch_metadata)
    result["queue_wait_seconds"] = max(0.0, (job.started_at or time.time()) - job.enqueued_at)
    result["queue_max_per_target"] = QUEUE_MAX_PER_TARGET
    return result


def compare_prompt(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> dict[str, Any]:
    if not prompt_text(payload).strip():
        raise ValueError("prompt or messages is required.")
    targets = [target for target in load_targets() if target.enabled]
    if not targets:
        raise ValueError("No enabled LLM targets are configured.")

    started = time.time()
    results: list[dict[str, Any]] = []
    jobs: list[PromptJob] = []
    for target in targets:
        item_payload = dict(payload)
        item_payload["target_id"] = target.id
        item_payload["client_id"] = str(payload.get("client_id") or "web-ui-compare")
        q = target_queue(target.id)
        job = PromptJob(target=target, payload=item_payload, client=item_payload["client_id"])
        try:
            q.put_nowait(job)
            jobs.append(job)
            sync_queue_metric(target.id)
        except queue.Full as exc:
            sync_queue_metric(target.id)
            results.append(
                {
                    "ok": False,
                    "target_id": target.id,
                    "target_name": target.name,
                    "target_host": target.host,
                    "target_port": target.port,
                    "target_url": target.base_url,
                    "api_type": target.api_type,
                    "model": target.model,
                    "gpu_type": target.gpu_type,
                    "gpu_info": target.gpu_info,
                    "selected_gpu": target.selected_gpu,
                    "selected_gpu_label": target.selected_gpu_label,
                    "selected_gpu_device": selected_gpu_device(target),
                    **dispatch_count_fields(0),
                    **dispatch_target_fields(target),
                    "response_seconds": 0.0,
                    "error": f"Queue is full for target {target.name}. max_per_target={QUEUE_MAX_PER_TARGET}",
                }
            )

    backend_timeout = int(payload.get("timeout") or DEFAULT_TIMEOUT_SECONDS)
    wait_timeout = int(payload.get("request_timeout") or (backend_timeout + QUEUE_MAX_PER_TARGET * backend_timeout + 10))
    for job in jobs:
        target = job.target
        if not job.done.wait(wait_timeout):
            dispatch_count = 1 if job.started_at else 0
            results.append(
                {
                    "ok": False,
                    "target_id": target.id,
                    "target_name": target.name,
                    "target_host": target.host,
                    "target_port": target.port,
                    "target_url": target.base_url,
                    "api_type": target.api_type,
                    "model": target.model,
                    "gpu_type": target.gpu_type,
                    "gpu_info": target.gpu_info,
                    "selected_gpu": target.selected_gpu,
                    "selected_gpu_label": target.selected_gpu_label,
                    "selected_gpu_device": selected_gpu_device(target),
                    **dispatch_count_fields(dispatch_count),
                    **dispatch_target_fields(target),
                    "response_seconds": time.time() - job.enqueued_at,
                    "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                    "error": f"Queued comparison prompt timed out after {wait_timeout}s for target {target.name}.",
                }
            )
            continue
        if job.error is not None:
            dispatch_count = 1 if job.started_at else 0
            results.append(
                {
                    "ok": False,
                    "target_id": target.id,
                    "target_name": target.name,
                    "target_host": target.host,
                    "target_port": target.port,
                    "target_url": target.base_url,
                    "api_type": target.api_type,
                    "model": target.model,
                    "gpu_type": target.gpu_type,
                    "gpu_info": target.gpu_info,
                    "selected_gpu": target.selected_gpu,
                    "selected_gpu_label": target.selected_gpu_label,
                    "selected_gpu_device": selected_gpu_device(target),
                    **dispatch_count_fields(dispatch_count),
                    **dispatch_target_fields(target),
                    "response_seconds": time.time() - job.enqueued_at,
                    "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                    "error": str(job.error),
                }
            )
            continue
        data = job.result or {}
        dispatch_count = int(data.get("llm_dispatch_count") or 1)
        results.append(
            {
                "ok": True,
                "target_id": target.id,
                "target_name": target.name,
                "target_host": target.host,
                "target_port": target.port,
                "target_url": target.base_url,
                "api_type": target.api_type,
                "model": target.model,
                "gpu_type": target.gpu_type,
                "gpu_info": target.gpu_info,
                "selected_gpu": target.selected_gpu,
                "selected_gpu_label": target.selected_gpu_label,
                "selected_gpu_device": selected_gpu_device(target),
                **dispatch_count_fields(dispatch_count),
                **dispatch_target_fields(target),
                "response_seconds": data.get("response_seconds", time.time() - job.enqueued_at),
                "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                "response": data.get("response", ""),
                "raw": data.get("raw", {}),
            }
        )

    total_dispatch_count = sum(int(item.get("llm_dispatch_count") or 0) for item in results)
    dispatched_targets = [
        item.get("llm_dispatch_target")
        for item in results
        if int(item.get("llm_dispatch_count") or 0) > 0 and isinstance(item.get("llm_dispatch_target"), dict)
    ]
    return {
        "ok": any(item.get("ok") for item in results),
        "target_count": len(targets),
        **dispatch_count_fields(total_dispatch_count),
        "llm_dispatch_model_numbers": [item.get("number") for item in dispatched_targets],
        "llm_dispatch_targets": dispatched_targets,
        "response_seconds": time.time() - started,
        "results": results,
    }


def openai_chat_response(data: dict[str, Any]) -> dict[str, Any]:
    created = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": data.get("model") or "",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": data.get("response") or ""},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        **dispatch_count_fields(int(data.get("llm_dispatch_count") or 0)),
        "llm_dispatch_model_number": data.get("llm_dispatch_model_number"),
        "llm_dispatch_target": data.get("llm_dispatch_target"),
        "routing": {
            "target_id": data.get("target_id"),
            "target_name": data.get("target_name"),
            "target_host": data.get("target_host"),
            "target_port": data.get("target_port"),
            "target_url": data.get("target_url"),
            "api_type": data.get("api_type"),
            "gpu_type": data.get("gpu_type"),
            "gpu_info": data.get("gpu_info"),
            "selected_gpu": data.get("selected_gpu"),
            "selected_gpu_label": data.get("selected_gpu_label"),
            "selected_gpu_device": data.get("selected_gpu_device"),
            **dispatch_count_fields(int(data.get("llm_dispatch_count") or 0)),
            "llm_dispatch_model_number": data.get("llm_dispatch_model_number"),
            "llm_dispatch_target": data.get("llm_dispatch_target"),
            "response_seconds": data.get("response_seconds"),
        },
    }


def api_status_payload() -> dict[str, Any]:
    targets = [target for target in load_targets() if target.enabled]
    first = targets[0] if targets else None
    network = local_network_info()
    return {
        "ok": True,
        "service": "llm-routing",
        "status": "ready" if targets else "no-enabled-targets",
        "uptime": seconds_to_uptime(time.time() - STARTED_AT),
        "model": first.model if first else "",
        "host": HOST,
        "port": PORT,
        "ip_address": network["primary_ip"],
        "ipv4_addresses": network["ipv4_addresses"],
        "service_url": network["service_url"],
        "network": network,
        "target_count": len(targets),
        "targets": [
            {
                "id": target.id,
                "name": target.name,
                "host": target.host,
                "port": target.port,
                "proxy_port": target.proxy_port,
                "model": target.model,
                "api_type": target.api_type,
                "selected_gpu": target.selected_gpu,
                "selected_gpu_label": target.selected_gpu_label,
            }
            for target in targets
        ],
    }


def read_access_log(limit: int = 200) -> list[dict[str, Any]]:
    if not ACCESS_LOG_PATH.exists():
        return []
    try:
        lines = ACCESS_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    events = []
    for line in reversed(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def run_command(command: list[str], timeout: int = 5) -> str:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return (completed.stdout or completed.stderr or "").strip()


def local_network_info() -> dict[str, Any]:
    hostname = socket.gethostname()
    primary_ip = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            primary_ip = sock.getsockname()[0]
    except OSError:
        primary_ip = ""

    addresses: list[str] = []
    try:
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip_address = str(item[4][0])
            if ip_address and ip_address not in addresses:
                addresses.append(ip_address)
    except OSError:
        pass
    if primary_ip and primary_ip not in addresses:
        addresses.insert(0, primary_ip)

    return {
        "hostname": hostname,
        "primary_ip": primary_ip,
        "ipv4_addresses": addresses,
        "listen_host": HOST,
        "listen_port": PORT,
        "service_url": f"http://{primary_ip or hostname}:{PORT}",
    }


def load_webdav_settings() -> dict[str, Any]:
    return load_json(
        WEBDAV_CONFIG_PATH,
        {
            "enabled": False,
            "schedule": {"interval_minutes": WEBDAV_DEFAULT_INTERVAL_MINUTES},
            "report": {"filename": "llm_routing_status.md"},
            "webdav": {
                "hostname": "",
                "root": "",
                "sub": "",
                "username": "",
                "password": "",
                "verify_ssl": True,
            },
        },
    )


def normalize_webdav_path(value: str) -> str:
    return str(value or "").strip().strip("/")


def normalize_webdav_subs(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    subs: list[str] = []
    for item in values:
        normalized = normalize_webdav_path(str(item or ""))
        if normalized not in subs:
            subs.append(normalized)
    return subs


def webdav_remote_dirs(settings: dict[str, Any]) -> list[str]:
    host_name = normalize_webdav_path(socket.gethostname())
    remote_dirs: list[str] = []
    for sub in normalize_webdav_subs(settings.get("webdav", {}).get("sub", "")):
        if sub:
            remote_dirs.append(posixpath.join("tinyGW", sub, host_name).strip("/"))
        else:
            remote_dirs.append(posixpath.join("tinyGW", host_name).strip("/"))
    return remote_dirs or [posixpath.join("tinyGW", host_name).strip("/")]


def webdav_url(settings: dict[str, Any], remote_path: str = "") -> str:
    webdav = settings.get("webdav", {})
    hostname = str(webdav.get("hostname") or "").rstrip("/")
    root = normalize_webdav_path(str(webdav.get("root") or ""))
    path = posixpath.join(root, normalize_webdav_path(remote_path)).strip("/")
    quoted = "/".join(urllib.parse.quote(part) for part in path.split("/") if part)
    return f"{hostname}/{quoted}" if quoted else hostname


def webdav_request(
    settings: dict[str, Any],
    method: str,
    remote_path: str,
    data: bytes | None = None,
    content_type: str = "text/markdown; charset=utf-8",
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    webdav = settings.get("webdav", {})
    username = str(webdav.get("username") or "")
    password = str(webdav.get("password") or "")
    headers: dict[str, str] = {}
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if data is not None:
        headers["Content-Type"] = content_type
    if extra_headers:
        headers.update(extra_headers)
    context = None
    if not bool(webdav.get("verify_ssl", True)):
        context = ssl._create_unverified_context()  # noqa: SLF001
    req = urllib.request.Request(webdav_url(settings, remote_path), data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=context) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if method == "MKCOL" and exc.code in {405, 409}:
            return b""
        if method == "DELETE" and exc.code == 404:
            return b""
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:300] if body else exc.reason
        raise RuntimeError(f"WebDAV {method} failed: HTTP {exc.code} {detail}") from exc


def ensure_webdav_remote_dirs(settings: dict[str, Any], remote_dir: str) -> None:
    current = ""
    for part in normalize_webdav_path(remote_dir).split("/"):
        if not part:
            continue
        current = posixpath.join(current, part).strip("/")
        webdav_request(settings, "MKCOL", current)


def timestamped_webdav_filename(file_name: str, timestamp: dt.datetime | None = None) -> str:
    normalized = normalize_webdav_path(file_name) or "llm_routing_status.md"
    parent, name = posixpath.split(normalized)
    stem, ext = posixpath.splitext(name)
    if not stem:
        stem = "llm_routing_status"
    if not ext:
        ext = ".md"
    created_at = timestamp or dt.datetime.now().astimezone()
    stamped_name = f"{stem}_{created_at.strftime('%Y%m%d_%H%M%S')}{ext}"
    return posixpath.join(parent, stamped_name).strip("/") if parent else stamped_name


def webdav_report_file_pattern(file_name: str) -> tuple[str, str, str]:
    normalized = normalize_webdav_path(file_name) or "llm_routing_status.md"
    parent, name = posixpath.split(normalized)
    stem, ext = posixpath.splitext(name)
    return parent, stem or "llm_routing_status", ext or ".md"


def webdav_href_to_remote_path(settings: dict[str, Any], href: str) -> str:
    parsed_href = urllib.parse.urlparse(href)
    href_path = urllib.parse.unquote(parsed_href.path or href).strip("/")
    root_url = webdav_url(settings, "")
    root_path = urllib.parse.unquote(urllib.parse.urlparse(root_url).path).strip("/")
    if root_path and href_path.startswith(root_path):
        return href_path[len(root_path) :].strip("/")
    return href_path


def parse_webdav_datetime(value: str) -> dt.datetime | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(cleaned)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def list_webdav_directory(settings: dict[str, Any], remote_dir: str) -> list[dict[str, Any]]:
    body = webdav_request(
        settings,
        "PROPFIND",
        remote_dir,
        data=b"""<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:getlastmodified />
    <d:resourcetype />
  </d:prop>
</d:propfind>
""",
        content_type="application/xml; charset=utf-8",
        extra_headers={"Depth": "1"},
    )
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    entries: list[dict[str, Any]] = []
    for response in root.findall("{DAV:}response"):
        href = response.findtext("{DAV:}href") or ""
        remote_path = webdav_href_to_remote_path(settings, href)
        if not remote_path or normalize_webdav_path(remote_path) == normalize_webdav_path(remote_dir):
            continue
        resource_type = response.find(".//{DAV:}resourcetype")
        is_collection = resource_type is not None and resource_type.find("{DAV:}collection") is not None
        if is_collection:
            continue
        last_modified = response.findtext(".//{DAV:}getlastmodified") or ""
        entries.append(
            {
                "remote_path": normalize_webdav_path(remote_path),
                "name": posixpath.basename(remote_path),
                "last_modified": parse_webdav_datetime(last_modified),
            }
        )
    return entries


def delete_old_webdav_report_files(settings: dict[str, Any], remote_dir: str, file_name: str) -> list[str]:
    file_parent, stem, ext = webdav_report_file_pattern(file_name)
    cleanup_dir = posixpath.join(remote_dir, file_parent).strip("/") if file_parent else remote_dir
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=WEBDAV_RETENTION_DAYS)
    deleted: list[str] = []
    try:
        entries = list_webdav_directory(settings, cleanup_dir)
    except Exception:
        return deleted
    legacy_name = f"{stem}{ext}"
    pattern = re.compile(rf"^{re.escape(stem)}_(\d{{8}}_\d{{6}}){re.escape(ext)}$")
    for entry in entries:
        name = str(entry.get("name") or "")
        match = pattern.match(name)
        file_time = None
        if match:
            try:
                file_time = dt.datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=dt.timezone.utc)
            except ValueError:
                file_time = None
        elif name == legacy_name:
            last_modified = entry.get("last_modified")
            if isinstance(last_modified, dt.datetime):
                file_time = last_modified
        else:
            continue
        if file_time is None or file_time >= cutoff:
            continue
        remote_path = str(entry.get("remote_path") or "")
        if not remote_path:
            continue
        webdav_request(settings, "DELETE", remote_path)
        deleted.append(remote_path)
    return deleted


def webdav_settings_error(settings: dict[str, Any]) -> str:
    if not settings.get("enabled", False):
        return "disabled"
    webdav = settings.get("webdav", {})
    for key in ("hostname", "root", "username", "password"):
        if not str(webdav.get(key) or "").strip():
            return f"webdav.{key} is required"
    return ""


def snapshot_metrics() -> dict[str, dict[str, Any]]:
    with STATE_LOCK:
        return {target_id: dict(values) for target_id, values in TARGET_RUNTIME.items()}


def llm_selection_markdown() -> str:
    targets = load_targets()
    metrics = snapshot_metrics()
    network = local_network_info()
    lines = [
        f"# LLM Routing Status - {socket.gethostname()}",
        "",
        f"- 생성 시각: {now_text()}",
        f"- 호스트명: {network['hostname']}",
        f"- 대표 IP: {network['primary_ip'] or '-'}",
        f"- IPv4 목록: {', '.join(network['ipv4_addresses']) if network['ipv4_addresses'] else '-'}",
        f"- 서비스 URL: {network['service_url']}",
        f"- 서비스 uptime: {seconds_to_uptime(time.time() - STARTED_AT)}",
        f"- 등록 LLM: {len(targets)}",
        f"- 활성 LLM: {sum(1 for target in targets if target.enabled)}",
        "",
        "## 모델/GPU 선택 상태",
        "",
        "| 상태 | 이름 | 주소 | 모델 | 선택 GPU | Queue | 처리 수 | 평균 응답 |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for target in targets:
        metric = metrics.get(target.id, {})
        total = int(metric.get("total_prompts") or 0)
        avg = 0.0
        if total:
            avg = float(metric.get("total_response_seconds") or 0.0) / total
        lines.append(
            "| "
            + " | ".join(
                [
                    "enabled" if target.enabled else "disabled",
                    target.name,
                    f"{target.host}:{target.port}",
                    target.model or "-",
                    selected_gpu_device(target),
                    f"{metric.get('queue_state', 'idle')} active {metric.get('active_requests', 0)} pending {metric.get('pending_queue', 0)}/{QUEUE_MAX_PER_TARGET}",
                    str(total),
                    f"{avg:.2f}s",
                ]
            )
            + " |"
        )
    local_gpu = local_gpu_info()
    lines.extend(
        [
            "",
            "## 로컬 GPU 상태",
            "",
            f"- 요약: {local_gpu['summary']}",
            f"- source: {local_gpu['source']}",
            "",
            "```text",
            str(local_gpu["detail"]),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def command_failed_text(value: str) -> bool:
    lowered = str(value or "").lower()
    return not lowered.strip() or any(
        marker in lowered
        for marker in (
            "no such file",
            "not found",
            "command not found",
            "not recognized",
            "unable to locate",
        )
    )


def summarize_nvidia_smi(value: str) -> str:
    gpus: list[str] = []
    for index, line in enumerate(value.splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if not parts or not parts[0]:
            continue
        name = parts[0]
        util = f"{parts[1]}%" if len(parts) > 1 and parts[1] else "n/a"
        memory = f"{parts[2]}/{parts[3]} MB" if len(parts) > 3 and parts[2] and parts[3] else "n/a"
        temp = f"{parts[4]}C" if len(parts) > 4 and parts[4] else "n/a"
        gpus.append(f"GPU {index}: {name}, util {util}, mem {memory}, temp {temp}")
    return "; ".join(gpus) if gpus else "NVIDIA GPU detected"


def summarize_system_profiler_gpu(value: str) -> str:
    names: list[str] = []
    current_name = ""
    cores = ""
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if line.startswith("Chipset Model:"):
            current_name = line.split(":", 1)[1].strip()
        elif line.startswith("Total Number of Cores:"):
            cores = line.split(":", 1)[1].strip()
        if current_name and (cores or line.startswith("Metal Support:")):
            label = current_name if not cores else f"{current_name} ({cores} cores)"
            if label not in names:
                names.append(label)
            current_name = ""
            cores = ""
    return "; ".join(names) if names else "GPU information available"


def local_gpu_info() -> dict[str, str]:
    nvidia_text = run_command(
        ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
        timeout=4,
    )
    if not command_failed_text(nvidia_text):
        return {
            "source": "nvidia-smi",
            "summary": summarize_nvidia_smi(nvidia_text),
            "detail": nvidia_text[:5000],
        }

    profiler_text = run_command(["system_profiler", "SPDisplaysDataType"], timeout=5)
    if not command_failed_text(profiler_text):
        return {
            "source": "system_profiler",
            "summary": summarize_system_profiler_gpu(profiler_text),
            "detail": profiler_text[:5000],
        }

    return {
        "source": "unavailable",
        "summary": "GPU 정보를 찾을 수 없습니다",
        "detail": f"nvidia-smi: {nvidia_text}\nsystem_profiler: {profiler_text}",
    }


def update_webdav_report_state(**values: Any) -> None:
    with STATE_LOCK:
        WEBDAV_REPORT_STATE.update(values)


def send_webdav_status_once(settings: dict[str, Any]) -> dict[str, Any]:
    error = webdav_settings_error(settings)
    if error:
        raise ValueError(error)
    report = settings.get("report", {}) if isinstance(settings.get("report"), dict) else {}
    base_file_name = normalize_webdav_path(str(report.get("filename") or "llm_routing_status.md")) or "llm_routing_status.md"
    file_name = timestamped_webdav_filename(base_file_name)
    markdown = llm_selection_markdown().encode("utf-8")
    remote_dirs = webdav_remote_dirs(settings)
    remote_paths = [posixpath.join(remote_dir, file_name).strip("/") for remote_dir in remote_dirs]
    deleted_paths: list[str] = []
    for remote_dir, remote_path in zip(remote_dirs, remote_paths):
        deleted_paths.extend(delete_old_webdav_report_files(settings, remote_dir, base_file_name))
        remote_parent = posixpath.dirname(remote_path)
        ensure_webdav_remote_dirs(settings, remote_parent or remote_dir)
        webdav_request(settings, "PUT", remote_path, data=markdown)
    return {
        "remote_paths": remote_paths,
        "destination_urls": [webdav_url(settings, remote_path) for remote_path in remote_paths],
        "deleted_paths": deleted_paths,
    }


def test_webdav_settings() -> dict[str, Any]:
    settings = load_webdav_settings()
    error = webdav_settings_error(settings)
    if error:
        return {
            "ok": False,
            "config_path": str(WEBDAV_CONFIG_PATH),
            "error": error,
            "settings_enabled": bool(settings.get("enabled", False)),
        }

    file_name = f"llm_routing_webdav_test_{int(time.time())}.txt"
    remote_dirs = webdav_remote_dirs(settings)
    remote_paths = [posixpath.join(remote_dir, file_name).strip("/") for remote_dir in remote_dirs]
    network = local_network_info()
    payload = (
        "LLM Routing WebDAV test\n"
        f"host={network['hostname']}\n"
        f"primary_ip={network['primary_ip']}\n"
        f"ipv4_addresses={', '.join(network['ipv4_addresses'])}\n"
        f"service_url={network['service_url']}\n"
        f"time={now_text()}\n"
    ).encode("utf-8")
    uploaded: list[dict[str, str]] = []
    try:
        for remote_dir, remote_path in zip(remote_dirs, remote_paths):
            ensure_webdav_remote_dirs(settings, remote_dir)
            webdav_request(settings, "PUT", remote_path, data=payload, content_type="text/plain; charset=utf-8")
            uploaded.append({"remote_path": remote_path, "destination_url": webdav_url(settings, remote_path)})
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "config_path": str(WEBDAV_CONFIG_PATH),
            "error": str(exc),
            "remote_dirs": remote_dirs,
            "remote_paths": remote_paths,
            "uploaded": uploaded,
        }

    return {
        "ok": True,
        "config_path": str(WEBDAV_CONFIG_PATH),
        "message": "WebDAV settings are valid. Test file uploaded.",
        "remote_dirs": remote_dirs,
        "remote_paths": remote_paths,
        "destination_urls": [item["destination_url"] for item in uploaded],
    }


def webdav_report_loop() -> None:
    settings = load_webdav_settings()
    error = webdav_settings_error(settings)
    if error == "disabled":
        update_webdav_report_state(enabled=False, status="disabled", last_error="")
        return
    if error:
        update_webdav_report_state(enabled=True, status="error", last_error=error)
        return
    interval = int(settings.get("schedule", {}).get("interval_minutes") or WEBDAV_DEFAULT_INTERVAL_MINUTES)
    interval = min(WEBDAV_MAX_INTERVAL_MINUTES, max(1, interval))
    update_webdav_report_state(enabled=True, status="waiting", interval_minutes=interval)
    while True:
        try:
            result = send_webdav_status_once(settings)
            update_webdav_report_state(
                status="ok",
                last_sent_at=now_text(),
                last_error="",
                remote_paths=result["remote_paths"],
                destination_urls=result["destination_urls"],
                deleted_paths=result.get("deleted_paths", []),
            )
        except Exception as exc:  # noqa: BLE001
            update_webdav_report_state(status="error", last_error=str(exc))
        time.sleep(interval * 60)


def start_webdav_reporter() -> None:
    thread = threading.Thread(target=webdav_report_loop, daemon=True, name="llm-routing-webdav-reporter")
    thread.start()


def local_system_stats() -> dict[str, Any]:
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    cpu_count = os.cpu_count() or 0
    gpu = local_gpu_info()
    network = local_network_info()
    with STATE_LOCK:
        webdav_report = dict(WEBDAV_REPORT_STATE)
    return {
        "hostname": socket.gethostname(),
        "primary_ip": network["primary_ip"],
        "ipv4_addresses": network["ipv4_addresses"],
        "listen_host": network["listen_host"],
        "listen_port": network["listen_port"],
        "service_url": network["service_url"],
        "network": network,
        "service_uptime": seconds_to_uptime(time.time() - STARTED_AT),
        "cpu_count": cpu_count,
        "load_average": [round(value, 2) for value in load_avg],
        "gpu_source": gpu["source"],
        "gpu_summary": gpu["summary"],
        "gpu_status": gpu["detail"][:5000],
        "access_log": read_access_log(100),
        "webdav_report": webdav_report,
    }


def status_payload() -> dict[str, Any]:
    targets = load_targets()
    ensure_target_queues(targets)
    health_by_id: dict[str, dict[str, Any]] = {}
    now = time.time()
    for target in targets:
        metric = metric_for(target.id)
        q = TARGET_QUEUES.get(target.id)
        local_pending = q.qsize() if q else 0
        selected_gpu_health_label = ""
        should_probe_health = (
            target.enabled
            and now - metric.last_health_at >= HEALTH_CHECK_INTERVAL_SECONDS
        )
        if should_probe_health:
            metric.last_health_at = now
            health = target_health(target)
            metric.status = "ok" if health["ok"] else "error"
            metric.last_error = "" if health["ok"] else health.get("error", "")
            metric.last_health_probe_at = now
            data = health.get("data") if isinstance(health.get("data"), dict) else {}
            if target.api_type in OPENAI_COMPATIBLE_API_TYPES and isinstance(data, dict):
                running = data.get("num_requests_running")
                waiting = data.get("num_requests_waiting")
                if isinstance(running, (int, float)):
                    metric.active_requests = int(running)
                if isinstance(waiting, (int, float)):
                    metric.pending_queue = int(waiting)
                if data.get("summary"):
                    metric.remote_gpu_info = str(data.get("summary"))
                if data.get("gpu_metric_lines"):
                    metric.remote_gpu_type = target.api_type
                metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
            elif isinstance(data, dict):
                queue = data.get("prompt_queue") if isinstance(data.get("prompt_queue"), dict) else {}
                if isinstance(queue.get("pending_count"), int):
                    metric.pending_queue = int(queue.get("pending_count", 0))
                if isinstance(queue.get("average_prompt_processing_seconds"), (int, float)):
                    metric.last_response_seconds = float(queue.get("average_prompt_processing_seconds", 0.0))
                if data.get("uptime_human"):
                    metric.uptime = str(data.get("uptime_human"))
                ifconfig_values = data.get("ifconfig_ipv4_addresses")
                if isinstance(ifconfig_values, list):
                    labels = []
                    for item in ifconfig_values:
                        if isinstance(item, dict) and item.get("ip"):
                            interface = str(item.get("interface") or "-")
                            labels.append(f"{interface}: {item.get('ip')}")
                        elif isinstance(item, str) and item:
                            labels.append(item)
                    metric.remote_ifconfig_ips = ", ".join(dict.fromkeys(labels))
                elif isinstance(data.get("ifconfig_ips"), list):
                    metric.remote_ifconfig_ips = ", ".join(dict.fromkeys(str(item) for item in data.get("ifconfig_ips", []) if item))
                gpus = data.get("gpus") if isinstance(data.get("gpus"), list) else []
                gpu_names = [str(gpu.get("name")) for gpu in gpus if isinstance(gpu, dict) and gpu.get("name")]
                if gpu_names:
                    metric.remote_gpu_info = ", ".join(gpu_names)
                    selected_gpu_health_label = selected_gpu_label_from_health(target, data)
                    selected = selected_gpu_health_label or str(data.get("selected_gpu_label") or "")
                    metric.remote_gpu_type = selected or gpu_names[0]
                metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
            metric.last_seen_at = now_text()
        metric.pending_queue = max(metric.pending_queue, local_pending)
        metric.queue_state = queue_state_text(metric.active_requests, metric.pending_queue)
        store_metric(target.id, metric)
        health_by_id[target.id] = metric.__dict__ | {
            "average_response_seconds": metric.average_response_seconds,
            "gpu_info": metric.remote_gpu_info or target.gpu_info,
            "gpu_type": metric.remote_gpu_type or target.gpu_type,
            "ifconfig_ips": metric.remote_ifconfig_ips,
            "selected_gpu_device": selected_gpu_health_label or selected_gpu_device(target),
            "queue_max_per_target": QUEUE_MAX_PER_TARGET,
            "activity_state": metric.queue_state,
        }

    clients = []
    for stats in CLIENT_STATS.values():
        recent = [stamp for stamp in stats.get("recent_times", []) if now - stamp <= 60]
        clients.append(
            {
                "client": stats["client"],
                "prompt_count": stats.get("prompt_count", 0),
                "qps": round(len(recent) / 60, 3),
                "last_response_seconds": round(float(stats.get("last_response_seconds", 0.0)), 3),
                "last_seen": seconds_to_uptime(now - float(stats.get("last_seen", now))) + " ago",
            }
        )
    return {
        "started_at": dt.datetime.fromtimestamp(STARTED_AT).astimezone().isoformat(),
        "uptime": seconds_to_uptime(time.time() - STARTED_AT),
        "status_refresh_seconds": STATUS_REFRESH_SECONDS,
        "targets": [target.__dict__ for target in targets],
        "target_history": load_target_history(),
        "duplicate_target_ids": sorted(duplicate_target_ids(targets)),
        "metrics": health_by_id,
        "service": {
            "client_count": len(CLIENT_STATS),
            "clients": sorted(clients, key=lambda item: item["prompt_count"], reverse=True),
            "recent_access": list(RECENT_ACCESS),
        },
        "local": local_system_stats(),
    }


LOGIN_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLM Routing Login</title>
  <style>
    :root { --ink:#182026; --muted:#64717c; --line:#d7dee5; --panel:#f7f9fb; --accent:#0f766e; --bad:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; display:grid; place-items:center; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#fff; }
    main { width:min(420px, calc(100vw - 32px)); border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:24px; }
    h1 { margin:0 0 8px; font-size:24px; letter-spacing:0; }
    p { margin:0 0 18px; color:var(--muted); }
    input { width:100%; min-height:40px; border:1px solid var(--line); border-radius:6px; padding:8px 10px; font:inherit; background:#fff; }
    button { width:100%; min-height:40px; margin-top:10px; border:1px solid var(--accent); border-radius:6px; background:var(--accent); color:#fff; font-weight:700; cursor:pointer; }
    .error { margin-top:10px; color:var(--bad); min-height:20px; font-size:14px; }
  </style>
</head>
<body>
<main>
  <h1>LLM Routing</h1>
  <p>관리 화면에 접속하려면 password를 입력하세요.</p>
  <input id="password" type="password" placeholder="Password" autofocus>
  <button onclick="login()">Login</button>
  <div id="error" class="error"></div>
</main>
<script>
async function login() {
  const password = document.getElementById('password').value;
  document.getElementById('error').textContent = '';
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({password})
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'login failed');
    }
    window.location.href = '/';
  } catch (err) {
    document.getElementById('error').textContent = String(err);
  }
}
document.getElementById('password').addEventListener('keydown', event => {
  if (event.key === 'Enter') login();
});
</script>
</body>
</html>
"""


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLM Routing</title>
  <style>
    :root { --ink:#182026; --muted:#64717c; --line:#d7dee5; --panel:#f7f9fb; --accent:#0f766e; --bad:#b42318; --warn:#996000; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:#fff; }
    main { width:min(1220px, calc(100vw - 32px)); margin:0 auto; padding:26px 0 48px; }
    header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; border-bottom:1px solid var(--line); padding-bottom:18px; }
    h1 { margin:0 0 6px; font-size:28px; letter-spacing:0; }
    p { margin:0; color:var(--muted); }
    nav { display:flex; gap:8px; margin-top:20px; border-bottom:1px solid var(--line); }
    nav button { border:0; border-bottom:3px solid transparent; background:#fff; padding:12px 14px; cursor:pointer; font-weight:700; }
    nav button.active { border-color:var(--accent); color:var(--accent); }
    section { display:none; padding-top:18px; }
    section.active { display:block; }
    .grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .metric, .panel { border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:14px; }
    .metric .label { color:var(--muted); font-size:13px; margin-bottom:6px; }
    .metric .value { font-size:18px; font-weight:800; overflow-wrap:anywhere; }
    .runtime-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:14px; }
    .runtime-card { border:1px solid var(--line); border-radius:8px; background:#fff; padding:14px; }
    .runtime-card h3 { margin:0 0 10px; font-size:15px; line-height:1.25; overflow-wrap:anywhere; }
    .runtime-card dl { display:grid; grid-template-columns:auto minmax(0,1fr); gap:6px 10px; margin:0; font-size:13px; }
    .runtime-card dt { color:var(--muted); }
    .runtime-card dd { margin:0; font-weight:700; overflow-wrap:anywhere; text-align:right; }
    table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    th, td { border-bottom:1px solid var(--line); padding:9px; text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:12px; text-transform:uppercase; }
    input, select, textarea { width:100%; min-height:36px; border:1px solid var(--line); border-radius:6px; padding:8px; font:inherit; background:#fff; }
    input[type="checkbox"] { width:auto; min-height:0; }
    textarea { min-height:76px; resize:vertical; }
    .form-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; align-items:end; }
    .check-row { display:flex; gap:8px; align-items:center; min-height:36px; color:var(--muted); font-weight:700; }
    .model-row { display:grid; grid-template-columns:minmax(0,2fr) minmax(0,2fr) auto; gap:10px; margin-top:10px; align-items:end; }
    .model-status { color:var(--muted); font-size:13px; align-self:center; min-height:20px; }
    .history-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; margin-top:10px; align-items:end; }
    .notice { margin-top:12px; border:1px solid #f2c94c; border-radius:8px; background:#fff8db; color:#7a4f00; padding:10px 12px; font-weight:700; }
    .notice:empty { display:none; }
    .duplicate-row { background:#fff4e5; }
    .duplicate-badge { display:inline-block; margin-top:4px; color:#7a4f00; font-weight:800; }
    .test-toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:10px; }
    .test-metrics { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }
    .test-output { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:12px; margin-top:12px; }
    .response-box { margin:0; min-height:630px; max-height:630px; overflow:auto; background:#f1f3f5; color:#24292f; border:1px solid #d0d7de; border-radius:8px; padding:14px; line-height:1.48; }
    .markdown-view { white-space:normal; overflow-wrap:anywhere; }
    .markdown-view h1, .markdown-view h2, .markdown-view h3 { margin:12px 0 8px; line-height:1.25; }
    .markdown-view p { margin:0 0 10px; color:#24292f; }
    .markdown-view ul, .markdown-view ol { margin:0 0 10px 22px; padding:0; }
    .markdown-view code { background:#e5e7eb; border-radius:4px; padding:1px 4px; }
    .markdown-view pre { max-height:none; background:#e5e7eb; color:#24292f; border:1px solid #d0d7de; }
    .raw-view { white-space:pre-wrap; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:13px; }
    .compare-response { max-width:420px; max-height:120px; overflow:auto; white-space:pre-wrap; }
    button { min-height:36px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; font-weight:700; padding:0 12px; }
    button.primary { color:#fff; background:var(--accent); border-color:var(--accent); }
    button.danger { color:#fff; background:var(--bad); border-color:var(--bad); }
    .ok { color:var(--accent); font-weight:700; } .error { color:var(--bad); font-weight:700; } .warn { color:var(--warn); font-weight:700; }
    pre { margin:0; white-space:pre-wrap; overflow:auto; max-height:420px; background:#101820; color:#ecf3f5; border-radius:8px; padding:12px; }
    @media (max-width:900px) { .grid, .form-grid { grid-template-columns:1fr 1fr; } header { display:block; } }
    @media (max-width:620px) { .grid, .form-grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>LLM Routing</h1>
      <p>외부 prompt를 등록된 LLM 서버로 전달하고 응답을 되돌려주는 라우터</p>
    </div>
    <div>
      <button onclick="refresh()">Refresh</button>
      <button onclick="logout()">Logout</button>
    </div>
  </header>
  <nav>
    <button class="active" data-tab="llms">LLM 리스트</button>
    <button data-tab="service">서비스</button>
    <button data-tab="local">로컬머신</button>
    <button data-tab="test">프롬프트 테스트</button>
  </nav>
  <section id="llms" class="active">
    <div class="grid" id="targetMetrics"></div>
    <div class="runtime-cards" id="runtimeCards"></div>
    <div class="panel" style="margin-top:14px">
      <div class="form-grid">
        <input id="name" placeholder="이름">
        <input id="host" placeholder="IP 주소">
        <input id="port" placeholder="PORT" type="number">
        <input id="proxy_port" placeholder="PROXY PORT" type="number">
        <select id="api_type"><option value="ollama">ollama</option><option value="openai">openai</option><option value="vllm">vllm</option></select>
        <label class="check-row"><input id="enabled" type="checkbox" checked> 사용</label>
        <button class="primary" onclick="saveTarget()">저장</button>
        <input id="gpu_type" placeholder="GPU 종류">
        <input id="gpu_info" placeholder="GPU 정보">
        <select id="selected_gpu"><option value="">GPU 자동 선택</option></select>
        <input id="selected_gpu_label" type="hidden">
        <input id="access_id" placeholder="접근 ID">
        <input id="password" placeholder="PASS" type="password">
        <input id="notes" placeholder="메모">
        <button onclick="clearForm()">신규 입력</button>
      </div>
      <div class="history-row">
        <select id="target_history"><option value="">저장된 입력 히스토리</option></select>
        <button onclick="applyTargetHistory()">히스토리 적용</button>
      </div>
      <div class="model-row">
        <input id="model" placeholder="모델 이름">
        <select id="model_select"><option value="">모델 목록</option></select>
        <button onclick="loadModels()">모델 조회</button>
      </div>
      <div id="model_status" class="model-status"></div>
      <input id="target_id" type="hidden">
    </div>
    <div id="duplicateNotice" class="notice"></div>
    <table><thead><tr><th>상태</th><th>LLM</th><th>주소</th><th>모델</th><th>GPU</th><th>Queue</th><th>처리 수</th><th>동작시간</th><th>응답</th><th>관리</th></tr></thead><tbody id="targetRows"></tbody></table>
  </section>
  <section id="service">
    <div class="grid" id="serviceMetrics"></div>
    <h3>모델 동작 상태</h3>
    <table>
      <thead>
        <tr><th>LLM</th><th>주소</th><th>모델</th><th>동작 상태</th><th>Active</th><th>Pending prompts</th><th>최근 응답</th><th>최근 확인</th></tr>
      </thead>
      <tbody id="serviceTargetRows"></tbody>
    </table>
    <h3>클라이언트 요청 상태</h3>
    <table><thead><tr><th>클라이언트</th><th>요청 prompt 수</th><th>초당 질의</th><th>최근 응답</th><th>최근 접속</th></tr></thead><tbody id="clientRows"></tbody></table>
  </section>
  <section id="local">
    <div class="grid" id="localMetrics"></div>
    <h3>LLM Routing WebDAV 전송</h3>
    <div class="test-toolbar">
      <button onclick="testWebdavSettings()">WebDAV 설정 확인</button>
    </div>
    <pre id="webdavStatus"></pre>
    <h3>GPU 상태</h3><pre id="gpuStatus"></pre>
    <h3>접근 로그</h3><pre id="accessLog"></pre>
  </section>
  <section id="test">
    <div class="panel">
      <select id="test_target"></select>
      <div id="autoTargetSummary" class="model-status"></div>
      <textarea id="test_prompt" placeholder="전송할 prompt"></textarea>
      <div class="test-toolbar">
        <button class="primary" onclick="sendPrompt()">전송</button>
        <button onclick="compareAllPrompts()">전체 모델 비교</button>
        <button onclick="clearPromptTest()">결과 지우기</button>
      </div>
    </div>
    <div class="test-metrics">
      <div class="metric"><div class="label">상태</div><div id="test_status" class="value">대기</div></div>
      <div class="metric"><div class="label">경과 시간</div><div id="test_elapsed" class="value">-</div></div>
      <div class="metric"><div class="label">응답 시간</div><div id="test_response_time" class="value">-</div></div>
      <div class="metric"><div class="label">선택 결과</div><div id="test_selected_target" class="value">-</div></div>
    </div>
    <h3>자동 선택 대상 모델/GPU</h3>
    <table><thead><tr><th>LLM</th><th>주소</th><th>모델</th><th>GPU</th><th>Queue</th></tr></thead><tbody id="autoTargetRows"></tbody></table>
    <div class="test-output">
      <div>
        <h3>회신</h3>
        <div id="test_answer" class="response-box markdown-view"></div>
      </div>
      <div>
        <h3>원본 응답</h3>
        <pre id="test_result" class="response-box raw-view"></pre>
      </div>
    </div>
    <h3>전체 모델 비교</h3>
    <table><thead><tr><th>상태</th><th>LLM</th><th>모델</th><th>GPU</th><th>소요 시간</th><th>수신 내용</th></tr></thead><tbody id="compareRows"></tbody></table>
  </section>
</main>
<script>
let state = {};
let selectedTestTargetId = localStorage.getItem('llmRoutingTestTargetId') || '';
for (const btn of document.querySelectorAll('nav button')) {
  btn.onclick = () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  };
}
function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function inlineMarkdown(text) {
  return esc(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
}
function renderMarkdown(text) {
  const lines = String(text || '').split(/\\r?\\n/);
  const html = [];
  let inCode = false;
  let codeLines = [];
  let inList = false;
  function closeList() {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  }
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) {
        html.push(`<pre><code>${esc(codeLines.join('\\n'))}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,3})\\s+(.+)$/);
    if (heading) {
      closeList();
      html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
      continue;
    }
    const bullet = line.match(/^\\s*[-*]\\s+(.+)$/);
    if (bullet) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    closeList();
    if (!line.trim()) {
      html.push('<br>');
    } else {
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }
  if (inCode) {
    html.push(`<pre><code>${esc(codeLines.join('\\n'))}</code></pre>`);
  }
  closeList();
  return html.join('');
}
function setAnswer(text) {
  document.getElementById('test_answer').innerHTML = renderMarkdown(text);
}
function metric(label, value) { return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`; }
function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds || 0)));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (days) return `${days}D ${hours}H ${minutes}M`;
  if (hours) return `${hours}H ${minutes}M ${secs}S`;
  if (minutes) return `${minutes}M ${secs}S`;
  return `${secs}S`;
}
function formatSeconds(seconds) {
  const value = Number(seconds || 0);
  return value > 0 ? `${value.toFixed(2)}s` : '-';
}
function latestTargetActivity(targets, metrics) {
  return targets
    .map(t => metrics[t.id] || {})
    .filter(m => m.last_seen_at)
    .map(m => m.last_seen_at)
    .sort()
    .pop() || '-';
}
function latestTargetMetric(targets, metrics) {
  return targets
    .map(t => metrics[t.id] || {})
    .filter(m => m.last_seen_at)
    .sort((a,b) => String(a.last_seen_at).localeCompare(String(b.last_seen_at)))
    .pop() || {};
}
function routerRunningSeconds() {
  const startedMs = Date.parse(state.started_at || '');
  return Number.isFinite(startedMs) ? (Date.now() - startedMs) / 1000 : 0;
}
async function api(path, options) {
  const res = await fetch(path, options);
  if (res.status === 401) {
    window.location.href = '/';
    throw new Error('login required');
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
async function logout() {
  await api('/api/logout', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  window.location.href = '/';
}
async function refresh() {
  state = await api('/api/status');
  renderTargets(); renderTargetHistory(); renderService(); renderLocal(); renderTestTargets();
}
function renderTargets() {
  const targets = state.targets || [];
  const metrics = state.metrics || {};
  const local = state.local || {};
  const duplicateIds = new Set(state.duplicate_target_ids || []);
  const duplicateCount = duplicateIds.size;
  const totalProcessingSeconds = targets.reduce((n,t)=>n+Number(metrics[t.id]?.total_response_seconds||0),0);
  const latestResponseSeconds = Number(latestTargetMetric(targets, metrics).last_response_seconds || 0);
  document.getElementById('targetMetrics').innerHTML = [
    metric('등록 LLM', targets.length),
    metric('활성 LLM', targets.filter(t => t.enabled).length),
    metric('로컬 IP', local.primary_ip || '-'),
    metric('라우터 uptime', state.uptime || ''),
    metric('라우터 시작', state.started_at ? new Date(state.started_at).toLocaleString() : '-'),
    metric('중복 항목', duplicateCount),
    metric('전체 pending queue', targets.reduce((n,t)=>n+(metrics[t.id]?.pending_queue||0),0)),
    metric('전체 처리 prompt', targets.reduce((n,t)=>n+(metrics[t.id]?.total_prompts||0),0)),
    metric('누적 LLM 동작시간', formatDuration(totalProcessingSeconds)),
    metric('최근 LLM 동작시간', formatSeconds(latestResponseSeconds)),
    metric('최근 LLM 동작시각', latestTargetActivity(targets, metrics))
  ].join('');
  document.getElementById('runtimeCards').innerHTML = [
    `<div class="runtime-card">
      <h3>LLM Router</h3>
      <dl>
        <dt>uptime</dt><dd>${esc(state.uptime || '-')}</dd>
        <dt>로컬 IP</dt><dd>${esc(local.primary_ip || '-')}</dd>
        <dt>서비스 URL</dt><dd>${esc(local.service_url || '-')}</dd>
        <dt>동작시간</dt><dd>${esc(formatDuration(routerRunningSeconds()))}</dd>
        <dt>시작 시각</dt><dd>${esc(state.started_at ? new Date(state.started_at).toLocaleString() : '-')}</dd>
        <dt>최근 LLM 동작</dt><dd>${esc(latestTargetActivity(targets, metrics))}</dd>
      </dl>
    </div>`,
    ...targets.map(t => {
      const m = metrics[t.id] || {};
      const cls = m.status === 'ok' ? 'ok' : (m.status === 'error' ? 'error' : 'warn');
      return `<div class="runtime-card">
        <h3>${esc(t.name || t.model || t.id)}</h3>
        <dl>
          <dt>상태</dt><dd><span class="${cls}">${esc(m.status || 'unknown')}</span></dd>
          <dt>사용 여부</dt><dd>${esc(t.enabled ? '사용' : '비사용')}</dd>
          <dt>서비스 uptime</dt><dd>${esc(m.uptime || '-')}</dd>
          <dt>누적 동작시간</dt><dd>${esc(formatDuration(m.total_response_seconds || 0))}</dd>
          <dt>최근 동작시간</dt><dd>${esc(formatSeconds(m.last_response_seconds || 0))}</dd>
          <dt>최근 동작시각</dt><dd>${esc(m.last_seen_at || '-')}</dd>
          <dt>Queue</dt><dd>${esc(m.queue_state || 'idle')} ${m.active_requests||0}/${m.pending_queue||0}</dd>
        </dl>
      </div>`;
    })
  ].join('');
  document.getElementById('duplicateNotice').textContent = duplicateCount
    ? `중복된 LLM 서버 항목 ${duplicateCount}개가 있습니다. 같은 API/IP/PORT/모델/GPU 조합은 노란색으로 표시됩니다.`
    : '';
  document.getElementById('targetRows').innerHTML = targets.map(t => {
    const m = metrics[t.id] || {};
    const cls = m.status === 'ok' ? 'ok' : (m.status === 'error' ? 'error' : 'warn');
    const selectedGpuDevice = m.selected_gpu_device || t.selected_gpu_label || m.gpu_info || t.gpu_info || '';
    const ifconfigIps = m.ifconfig_ips ? `<br><small>ifconfig: ${esc(m.ifconfig_ips)}</small>` : '';
    const duplicateBadge = duplicateIds.has(t.id) ? '<br><span class="duplicate-badge">중복</span>' : '';
    return `<tr class="${duplicateIds.has(t.id) ? 'duplicate-row' : ''}">
      <td><span class="${cls}">${esc(m.status || 'unknown')}</span><br>${t.enabled ? 'enabled' : 'disabled'}${duplicateBadge}</td>
      <td>${esc(t.name)}<br><small>${esc(t.id)}</small></td>
      <td>${esc(t.host)}:${esc(t.port)}<br><small>${esc(t.api_type)}${t.proxy_port ? ` / proxy :${esc(t.proxy_port)}` : ''}</small>${ifconfigIps}</td>
      <td>${esc(t.model)}</td>
      <td>${esc(m.gpu_type || t.gpu_type)}<br><small>${esc(selectedGpuDevice)}</small><br><small>selected: ${esc(t.selected_gpu || 'auto')}</small></td>
      <td>${esc(m.queue_state || 'idle')}<br>active ${m.active_requests||0}, pending ${m.pending_queue||0}/${m.queue_max_per_target||10}</td>
      <td>${m.total_prompts||0}</td>
      <td>누적 ${esc(formatDuration(m.total_response_seconds||0))}<br><small>최근 ${esc(formatSeconds(m.last_response_seconds||0))}</small><br><small>${esc(m.last_seen_at||'-')}</small></td>
      <td>평균 ${esc(formatSeconds(m.average_response_seconds||0))}<br><small>${esc(m.last_error||'')}</small></td>
      <td><button onclick='editTarget(${JSON.stringify(t)})'>편집</button> <button onclick="setTargetEnabled('${t.id}', ${t.enabled ? 'false' : 'true'})">${t.enabled ? '사용 안함' : '사용'}</button> <button class="danger" onclick="deleteTarget('${t.id}')">삭제</button></td>
    </tr>`;
  }).join('');
}
function historyLabel(item) {
  const title = item.name || item.model || 'LLM';
  const address = `${item.host || ''}:${item.port || ''}`;
  const model = item.model ? ` / ${item.model}` : '';
  const gpu = item.selected_gpu ? ` / GPU ${item.selected_gpu}` : '';
  return `${title} - ${address}${model}${gpu}`;
}
function renderTargetHistory() {
  const select = document.getElementById('target_history');
  const currentValue = select.value;
  const history = state.target_history || [];
  select.innerHTML = '<option value="">저장된 입력 히스토리</option>' + history.map((item, index) => {
    const savedAt = item.saved_at ? ` (${item.saved_at})` : '';
    return `<option value="${index}">${esc(historyLabel(item) + savedAt)}</option>`;
  }).join('');
  if (currentValue && Number(currentValue) < history.length) {
    select.value = currentValue;
  }
}
function renderService() {
  const service = state.service || {};
  const clients = service.clients || [];
  const targets = state.targets || [];
  const metrics = state.metrics || {};
  const totalPending = targets.reduce((n,t)=>n+(metrics[t.id]?.pending_queue||0),0);
  const totalActive = targets.reduce((n,t)=>n+(metrics[t.id]?.active_requests||0),0);
  document.getElementById('serviceMetrics').innerHTML = [
    metric('접속 prompt 클라이언트', service.client_count || 0),
    metric('전체 클라이언트 요청', clients.reduce((n,c)=>n+(c.prompt_count||0),0)),
    metric('Active 요청', totalActive),
    metric('Pending prompts', totalPending),
    metric('총 QPS', clients.reduce((n,c)=>n+(c.qps||0),0).toFixed(3)),
    metric('상태 갱신 주기', `${state.status_refresh_seconds || 10}s`),
    metric('라우터 uptime', state.uptime || '')
  ].join('');
  document.getElementById('serviceTargetRows').innerHTML = targets.map(t => {
    const m = metrics[t.id] || {};
    const stateText = m.activity_state || m.queue_state || 'idle';
    const cls = m.status === 'ok' ? 'ok' : (m.status === 'error' ? 'error' : 'warn');
    const stateCls = stateText === 'active' ? 'ok' : (stateText === 'pending' ? 'warn' : '');
    const probeText = m.last_health_probe_at ? new Date(Number(m.last_health_probe_at) * 1000).toLocaleTimeString() : '-';
    const ifconfigIps = m.ifconfig_ips ? `<br><small>ifconfig: ${esc(m.ifconfig_ips)}</small>` : '';
    return `<tr>
      <td>${esc(t.name)}<br><small>${esc(t.id)}</small></td>
      <td>${esc(t.host)}:${esc(t.port)}<br><small>${esc(t.api_type)}${t.proxy_port ? ` / proxy :${esc(t.proxy_port)}` : ''}</small>${ifconfigIps}</td>
      <td>${esc(t.model || 'server-default')}</td>
      <td><span class="${cls}">${esc(m.status || 'unknown')}</span><br><span class="${stateCls}">${esc(stateText)}</span></td>
      <td>${m.active_requests || 0}</td>
      <td>${m.pending_queue || 0}/${m.queue_max_per_target || 10}</td>
      <td>${Number(m.last_response_seconds || 0).toFixed(2)}s<br><small>${esc(m.last_error || '')}</small></td>
      <td>${esc(probeText)}<br><small>${esc(m.last_seen_at || '')}</small></td>
    </tr>`;
  }).join('');
  document.getElementById('clientRows').innerHTML = clients.map(c => `<tr><td>${esc(c.client)}</td><td>${c.prompt_count}</td><td>${c.qps}</td><td>${c.last_response_seconds}s</td><td>${esc(c.last_seen)}</td></tr>`).join('');
}
function renderLocal() {
  const local = state.local || {};
  const webdav = local.webdav_report || {};
  document.getElementById('localMetrics').innerHTML = [
    metric('호스트', local.hostname || ''),
    metric('로컬 IP', local.primary_ip || '-'),
    metric('IPv4 주소', (local.ipv4_addresses || []).join(', ') || '-'),
    metric('서비스 URL', local.service_url || '-'),
    metric('CPU cores', local.cpu_count || 0),
    metric('Load avg', (local.load_average || []).join(', ')),
    metric('로컬 GPU', local.gpu_summary || ''),
    metric('GPU source', local.gpu_source || ''),
    metric('서비스 uptime', local.service_uptime || '')
  ].join('');
  document.getElementById('webdavStatus').textContent = JSON.stringify(webdav, null, 2);
  document.getElementById('gpuStatus').textContent = local.gpu_status || '';
  document.getElementById('accessLog').textContent = JSON.stringify(local.access_log || [], null, 2);
}
async function testWebdavSettings() {
  const box = document.getElementById('webdavStatus');
  box.textContent = 'WebDAV 설정을 확인 중입니다...';
  try {
    const data = await api('/api/webdav-test', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    box.textContent = JSON.stringify(data, null, 2);
    await refresh();
  } catch (err) {
    box.textContent = String(err);
  }
}
function renderTestTargets() {
  const select = document.getElementById('test_target');
  const previousValue = select.value || selectedTestTargetId;
  const enabledTargets = (state.targets || []).filter(t=>t.enabled);
  select.innerHTML = '<option value="">자동 선택</option>' + (state.targets || []).filter(t=>t.enabled).map(t => `<option value="${esc(t.id)}">${esc(t.name)} (${esc(t.model)})</option>`).join('');
  if (previousValue && enabledTargets.some(t => t.id === previousValue)) {
    select.value = previousValue;
  } else {
    select.value = '';
    selectedTestTargetId = '';
    localStorage.removeItem('llmRoutingTestTargetId');
  }
  renderAutoTargetRows(enabledTargets);
}
function renderAutoTargetRows(enabledTargets) {
  const metrics = state.metrics || {};
  document.getElementById('autoTargetSummary').textContent = enabledTargets.length
    ? `자동 선택 후보 ${enabledTargets.length}개`
    : '자동 선택 가능한 활성 LLM이 없습니다.';
  document.getElementById('autoTargetRows').innerHTML = enabledTargets.map(t => {
    const m = metrics[t.id] || {};
    const gpuType = m.gpu_type || t.gpu_type || '';
    const gpuInfo = m.selected_gpu_device || t.selected_gpu_label || m.gpu_info || t.gpu_info || '';
    return `<tr>
      <td>${esc(t.name)}<br><small>${esc(t.id)}</small></td>
      <td>${esc(t.host)}:${esc(t.port)}<br><small>${esc(t.api_type)}${t.proxy_port ? ` / proxy :${esc(t.proxy_port)}` : ''}</small></td>
      <td>${esc(t.model || '')}</td>
      <td>${esc(gpuType)}<br><small>${esc(t.selected_gpu_label || gpuInfo)}</small><br><small>selected: ${esc(t.selected_gpu || 'auto')}</small></td>
      <td>${esc(m.queue_state || 'idle')}<br>active ${m.active_requests || 0}, pending ${m.pending_queue || 0}/${m.queue_max_per_target || 10}</td>
    </tr>`;
  }).join('');
}
function setModelOptions(models, selectedModel = '') {
  const select = document.getElementById('model_select');
  const currentModel = selectedModel || document.getElementById('model').value;
  select.innerHTML = '<option value="">모델 목록</option>' + models.map(model => `<option value="${esc(model)}">${esc(model)}</option>`).join('');
  if (currentModel && models.includes(currentModel)) {
    select.value = currentModel;
  }
}
function setGpuOptions(gpus, selectedGpu = '') {
  const select = document.getElementById('selected_gpu');
  const currentGpu = selectedGpu || select.value;
  select.innerHTML = '<option value="">GPU 자동 선택</option>' + gpus.map(gpu => `<option value="${esc(gpu.value)}">${esc(gpu.label || gpu.value)}</option>`).join('');
  if (currentGpu && gpus.some(gpu => gpu.value === currentGpu)) {
    select.value = currentGpu;
  } else if (currentGpu) {
    select.innerHTML += `<option value="${esc(currentGpu)}">GPU ${esc(currentGpu)} (저장됨)</option>`;
    select.value = currentGpu;
  }
}
function editTarget(t) {
  for (const key of ['target_id','name','host','port','proxy_port','model','api_type','gpu_type','gpu_info','selected_gpu','selected_gpu_label','access_id','password','notes']) {
    const id = key === 'target_id' ? 'target_id' : key;
    const value = key === 'target_id' ? t.id : t[key];
    document.getElementById(id).value = value || '';
  }
  document.getElementById('enabled').checked = Boolean(t.enabled);
  setModelOptions([], t.model || '');
  setGpuOptions([], t.selected_gpu || '');
  document.getElementById('model_status').textContent = '';
}
function applyTargetHistory() {
  const select = document.getElementById('target_history');
  const item = (state.target_history || [])[Number(select.value)];
  if (!item) return;
  const keepTargetId = document.getElementById('target_id').value;
  for (const key of ['name','host','port','proxy_port','model','api_type','gpu_type','gpu_info','selected_gpu','selected_gpu_label','access_id','password','notes']) {
    document.getElementById(key).value = item[key] || '';
  }
  document.getElementById('target_id').value = keepTargetId;
  document.getElementById('enabled').checked = item.enabled !== false;
  setModelOptions([], item.model || '');
  setGpuOptions([], item.selected_gpu || '');
  document.getElementById('model_status').textContent = '히스토리 입력값을 적용했습니다.';
}
function clearForm() {
  for (const id of ['target_id','name','host','port','proxy_port','model','gpu_type','gpu_info','selected_gpu_label','access_id','password','notes']) document.getElementById(id).value = '';
  document.getElementById('api_type').value = 'ollama';
  document.getElementById('enabled').checked = true;
  setModelOptions([]);
  setGpuOptions([]);
  document.getElementById('model_status').textContent = '';
}
async function loadModels() {
  const status = document.getElementById('model_status');
  const payload = {};
  for (const id of ['host','port','api_type','access_id','password']) payload[id] = document.getElementById(id).value;
  status.textContent = '모델 목록을 조회 중입니다...';
  try {
    const data = await api('/api/models', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    setModelOptions(data.models || []);
    setGpuOptions(data.gpus || []);
    const gpuText = (data.gpus || []).length ? `, GPU ${(data.gpus || []).length}개` : '';
    status.textContent = `${(data.models || []).length}개 모델${gpuText}를 찾았습니다.`;
  } catch (err) {
    setModelOptions([]);
    setGpuOptions([]);
    status.textContent = String(err);
  }
}
async function saveTarget() {
  const payload = {};
  for (const id of ['target_id','name','host','port','proxy_port','model','api_type','gpu_type','gpu_info','selected_gpu','access_id','password','notes']) payload[id === 'target_id' ? 'id' : id] = document.getElementById(id).value;
  const gpuSelect = document.getElementById('selected_gpu');
  payload.selected_gpu_label = gpuSelect.value ? (gpuSelect.options[gpuSelect.selectedIndex]?.textContent || '') : '';
  const selectedMatch = payload.selected_gpu_label.match(/^\\s*GPU\\s+([^:\\s]+)/i);
  if (payload.selected_gpu && selectedMatch && selectedMatch[1] !== payload.selected_gpu) {
    payload.selected_gpu_label = '';
  }
  payload.enabled = document.getElementById('enabled').checked;
  await api('/api/targets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  clearForm(); await refresh();
}
async function setTargetEnabled(id, enabled) {
  await api('/api/target-enabled', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, enabled})});
  await refresh();
}
async function deleteTarget(id) {
  await api('/api/delete-target', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
  await refresh();
}
async function sendPrompt() {
  const select = document.getElementById('test_target');
  selectedTestTargetId = select.value;
  if (selectedTestTargetId) {
    localStorage.setItem('llmRoutingTestTargetId', selectedTestTargetId);
  } else {
    localStorage.removeItem('llmRoutingTestTargetId');
  }
  const payload = {prompt: document.getElementById('test_prompt').value, target_id: selectedTestTargetId, client_id: 'web-ui'};
  const startedAt = performance.now();
  let elapsedTimer = window.setInterval(() => {
    document.getElementById('test_elapsed').textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
  }, 100);
  document.getElementById('test_status').textContent = '전송 중';
  document.getElementById('test_response_time').textContent = '-';
  setAnswer('');
  document.getElementById('test_result').textContent = 'Running...';
  try {
    const data = await api('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    document.getElementById('test_status').textContent = '완료';
    document.getElementById('test_elapsed').textContent = `${elapsedSeconds.toFixed(2)}s`;
    document.getElementById('test_response_time').textContent = `${Number(data.response_seconds || elapsedSeconds).toFixed(2)}s`;
    document.getElementById('test_selected_target').textContent = selectedTargetLabel(data);
    setAnswer(promptResponseDetails(data));
    document.getElementById('test_result').textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    document.getElementById('test_status').textContent = '오류';
    document.getElementById('test_elapsed').textContent = `${elapsedSeconds.toFixed(2)}s`;
    document.getElementById('test_response_time').textContent = '-';
    document.getElementById('test_selected_target').textContent = '-';
    setAnswer('');
    document.getElementById('test_result').textContent = String(err);
  } finally {
    window.clearInterval(elapsedTimer);
  }
  await refresh();
}
function selectedTargetLabel(data) {
  return `${data.target_name || ''} / ${data.model || ''} / ${data.target_host || ''}:${data.target_port || ''} / GPU ${data.selected_gpu || 'auto'}`;
}
function renderCompareResults(results) {
  document.getElementById('compareRows').innerHTML = results.map(item => {
    const cls = item.ok ? 'ok' : 'error';
    const status = item.ok ? 'ok' : 'error';
    const response = item.ok ? (item.response || '') : (item.error || '');
    const selectedGpu = item.selected_gpu_device || item.selected_gpu_label || item.selected_gpu || 'auto';
    return `<tr>
      <td><span class="${cls}">${esc(status)}</span></td>
      <td>${esc(item.target_name)}<br><small>${esc(item.target_id)}</small></td>
      <td>${esc(item.model || '')}</td>
      <td>${esc(item.gpu_type || '')}<br><small>${esc(selectedGpu)}</small></td>
      <td>${Number(item.response_seconds || 0).toFixed(2)}s</td>
      <td><div class="compare-response">${esc(response)}</div></td>
    </tr>`;
  }).join('');
}
function promptResponseDetails(data) {
  const selectedGpu = data.selected_gpu_device || data.selected_gpu_label || data.selected_gpu || 'auto';
  const lines = [
    `### ${data.target_name || ''}`,
    `- Target: ${data.target_host || ''}:${data.target_port || ''}`,
    `- API: ${data.api_type || ''}`,
    `- Model: ${data.model || ''}`,
    `- GPU: ${`${data.gpu_type || ''} ${data.gpu_info || ''}`.trim()}`,
    `- Selected GPU: ${selectedGpu}`,
    `- Elapsed: ${Number(data.response_seconds || 0).toFixed(2)}s`,
    '',
    data.response || ''
  ];
  return lines.join('\\n');
}
async function compareAllPrompts() {
  const payload = {prompt: document.getElementById('test_prompt').value, client_id: 'web-ui-compare'};
  const startedAt = performance.now();
  let elapsedTimer = window.setInterval(() => {
    document.getElementById('test_elapsed').textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
  }, 100);
  document.getElementById('test_status').textContent = '전체 비교 중';
  document.getElementById('test_response_time').textContent = '-';
  setAnswer('');
  document.getElementById('test_result').textContent = 'Running comparison...';
  document.getElementById('compareRows').innerHTML = '';
  try {
    const data = await api('/api/compare', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    const results = data.results || [];
    const successCount = results.filter(item => item.ok).length;
    document.getElementById('test_status').textContent = `비교 완료 ${successCount}/${results.length}`;
    document.getElementById('test_elapsed').textContent = `${elapsedSeconds.toFixed(2)}s`;
    document.getElementById('test_response_time').textContent = `${Number(data.response_seconds || elapsedSeconds).toFixed(2)}s`;
    document.getElementById('test_selected_target').textContent = `${successCount}/${results.length}개 완료`;
    setAnswer(results.map(item => `### ${item.target_name} / ${item.model || ''}\\n- Target: ${item.target_host || ''}:${item.target_port || ''}\\n- GPU: ${item.selected_gpu_device || item.selected_gpu_label || item.selected_gpu || 'auto'}\\n\\n${item.ok ? (item.response || '') : ('ERROR: ' + (item.error || ''))}`).join('\\n\\n---\\n\\n'));
    document.getElementById('test_result').textContent = JSON.stringify(data, null, 2);
    renderCompareResults(results);
  } catch (err) {
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    document.getElementById('test_status').textContent = '비교 오류';
    document.getElementById('test_elapsed').textContent = `${elapsedSeconds.toFixed(2)}s`;
    document.getElementById('test_response_time').textContent = '-';
    document.getElementById('test_selected_target').textContent = '-';
    setAnswer('');
    document.getElementById('test_result').textContent = String(err);
  } finally {
    window.clearInterval(elapsedTimer);
  }
  await refresh();
}
function clearPromptTest() {
  document.getElementById('test_status').textContent = '대기';
  document.getElementById('test_elapsed').textContent = '-';
  document.getElementById('test_response_time').textContent = '-';
  document.getElementById('test_selected_target').textContent = '-';
  setAnswer('');
  document.getElementById('test_result').textContent = '';
  document.getElementById('compareRows').innerHTML = '';
}
refresh();
setInterval(refresh, 10000);
document.getElementById('test_target').addEventListener('change', (event) => {
  selectedTestTargetId = event.target.value;
  if (selectedTestTargetId) {
    localStorage.setItem('llmRoutingTestTargetId', selectedTestTargetId);
  } else {
    localStorage.removeItem('llmRoutingTestTargetId');
  }
});
document.getElementById('model_select').addEventListener('change', (event) => {
  if (event.target.value) {
    document.getElementById('model').value = event.target.value;
  }
});
for (const id of ['host','port','api_type','access_id','password']) {
  document.getElementById(id).addEventListener('change', () => {
    setModelOptions([]);
    setGpuOptions([]);
    document.getElementById('model_status').textContent = '';
  });
}
</script>
</body>
</html>
"""


class RoutingHandler(BaseHTTPRequestHandler):
    server_version = "LLMRouting/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def session_token(self) -> str:
        cookie_header = self.headers.get("Cookie", "")
        for item in cookie_header.split(";"):
            if "=" not in item:
                continue
            name, value = item.strip().split("=", 1)
            if name == SESSION_COOKIE_NAME:
                return value
        return ""

    def is_authenticated(self) -> bool:
        return valid_session(self.session_token())

    def require_auth(self) -> bool:
        if self.is_authenticated():
            return True
        self.write_json({"ok": False, "error": "login required"}, HTTPStatus.UNAUTHORIZED)
        return False

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}

    def write_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-LLM-Routing-Password, X-API-Key")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_login_cookie(self, token: str) -> None:
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax",
        )

    def clear_login_cookie(self) -> None:
        self.send_header("Set-Cookie", f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")

    def write_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.write_html(INDEX_HTML if self.is_authenticated() else LOGIN_HTML)
            return
        if self.path == "/health":
            self.write_json({"ok": True, "uptime": seconds_to_uptime(time.time() - STARTED_AT)})
            return
        if self.path == "/api/status":
            self.write_json(status_payload() if self.is_authenticated() else api_status_payload())
            return
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-LLM-Routing-Password, X-API-Key")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/login":
                if valid_admin_password(str(payload.get("password") or "")):
                    body = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.write_login_cookie(create_session())
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.write_json({"ok": False, "error": "invalid password"}, HTTPStatus.UNAUTHORIZED)
                return
            if self.path == "/api/logout":
                body = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.clear_login_cookie()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path in {"/api/generate", "/generate", "/api/chat"}:
                if not prompt_api_authenticated(self, payload):
                    self.write_json({"ok": False, "error": "invalid api password"}, HTTPStatus.UNAUTHORIZED)
                    return
                self.write_json(route_prompt(self, payload))
                return
            if self.path == "/v1/chat/completions":
                if not prompt_api_authenticated(self, payload):
                    self.write_json({"ok": False, "error": "invalid api password"}, HTTPStatus.UNAUTHORIZED)
                    return
                self.write_json(openai_chat_response(route_prompt(self, payload)))
                return
            if not self.require_auth():
                return
            if self.path == "/api/compare":
                self.write_json(compare_prompt(self, payload))
                return
            if self.path == "/api/webdav-test":
                self.write_json(test_webdav_settings())
                return
            if self.path == "/api/targets":
                self.write_json({"ok": True, "target": self.upsert_target(payload)})
                return
            if self.path == "/api/target-enabled":
                self.write_json({"ok": True, "target": self.set_target_enabled(payload)})
                return
            if self.path == "/api/delete-target":
                self.write_json({"ok": True, "deleted": self.delete_target(str(payload.get("id") or ""))})
                return
            if self.path == "/api/models":
                target = target_from_lookup_payload(payload)
                self.write_json({"ok": True, **fetch_target_options(target)})
                return
            self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except PromptDispatchError as exc:
            self.write_json(
                {
                    "ok": False,
                    "error": str(exc),
                    **dispatch_count_fields(exc.dispatch_count),
                    **dispatch_target_fields(exc.target),
                },
                HTTPStatus.BAD_GATEWAY,
            )
        except QueueFullError as exc:
            self.write_json({"ok": False, "error": str(exc), **dispatch_count_fields(0)}, HTTPStatus.TOO_MANY_REQUESTS)
        except ValueError as exc:
            self.write_json({"ok": False, "error": str(exc), **dispatch_count_fields(0)}, HTTPStatus.BAD_REQUEST)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            detail = f"Backend HTTP {exc.code}: {exc.reason}"
            if body:
                detail = f"{detail}\n{body[:2000]}"
            self.write_json({"ok": False, "error": detail, **dispatch_count_fields(1)}, HTTPStatus.BAD_GATEWAY)
        except (RuntimeError, urllib.error.URLError, TimeoutError, OSError) as exc:
            self.write_json(
                {"ok": False, "error": f"Backend request failed: {exc}", **dispatch_count_fields(1)},
                HTTPStatus.BAD_GATEWAY,
            )
        except Exception as exc:  # noqa: BLE001
            self.write_json({"ok": False, "error": str(exc), **dispatch_count_fields(0)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def upsert_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        target_id = str(payload.get("id") or uuid.uuid4().hex)
        name = str(payload.get("name") or payload.get("model") or "LLM").strip()
        host = str(payload.get("host") or "").strip()
        if not host:
            raise ValueError("host is required.")
        port = int(payload.get("port") or 0)
        if port <= 0:
            raise ValueError("port is required.")
        new_target = LLMTarget(
            id=target_id,
            name=name,
            host=host,
            port=port,
            proxy_port=int(payload.get("proxy_port") or 0),
            model=str(payload.get("model") or "").strip(),
            api_type=str(payload.get("api_type") or "ollama").strip(),
            gpu_info=str(payload.get("gpu_info") or "").strip(),
            gpu_type=str(payload.get("gpu_type") or "").strip(),
            selected_gpu=str(payload.get("selected_gpu") or "").strip(),
            selected_gpu_label=str(payload.get("selected_gpu_label") or "").strip(),
            access_id=str(payload.get("access_id") or "").strip(),
            password=str(payload.get("password") or ""),
            enabled=bool_value(payload.get("enabled"), True),
            weight=max(1, int(payload.get("weight") or 1)),
            notes=str(payload.get("notes") or "").strip(),
        )
        targets = load_targets()
        replaced = False
        for index, target in enumerate(targets):
            if target.id == target_id:
                targets[index] = new_target
                replaced = True
                break
        if not replaced:
            targets.append(new_target)
        save_targets(targets)
        remember_target_history(new_target)
        sync_ollama_proxy_servers()
        return new_target.__dict__

    def set_target_enabled(self, payload: dict[str, Any]) -> dict[str, Any]:
        target_id = str(payload.get("id") or "").strip()
        if not target_id:
            raise ValueError("id is required.")
        targets = load_targets()
        for target in targets:
            if target.id == target_id:
                target.enabled = bool_value(payload.get("enabled"), target.enabled)
                save_targets(targets)
                if not target.enabled:
                    sync_queue_metric(target.id)
                return target.__dict__
        raise ValueError(f"target not found: {target_id}")

    def delete_target(self, target_id: str) -> bool:
        if not target_id:
            raise ValueError("id is required.")
        targets = load_targets()
        filtered = [target for target in targets if target.id != target_id]
        save_targets(filtered)
        with STATE_LOCK:
            TARGET_RUNTIME.pop(target_id, None)
        sync_ollama_proxy_servers()
        return len(filtered) != len(targets)


def main() -> int:
    global HOST, PORT

    parser = argparse.ArgumentParser(description="Route prompt requests to multiple LLM backends.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    HOST = args.host
    PORT = args.port
    ensure_default_config()
    ensure_admin_password()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    start_webdav_reporter()
    httpd = ThreadingHTTPServer((args.host, args.port), RoutingHandler)
    sync_ollama_proxy_servers()
    print(f"LLM Routing listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping LLM Routing", flush=True)
    finally:
        with STATE_LOCK:
            proxy_servers = [server for server, _, _ in PROXY_SERVERS.values()]
            PROXY_SERVERS.clear()
        for server in proxy_servers:
            server.shutdown()
            server.server_close()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
