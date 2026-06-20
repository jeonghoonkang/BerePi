#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import queue
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
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
HOST = os.getenv("LLM_ROUTING_HOST", "0.0.0.0")
PORT = int(os.getenv("LLM_ROUTING_PORT", "4004"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("LLM_ROUTING_TIMEOUT", "180"))
QUEUE_MAX_PER_TARGET = int(os.getenv("LLM_ROUTING_QUEUE_MAX_PER_TARGET", "10"))
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
MAX_RECENT_ACCESS = 300
OPENAI_COMPATIBLE_API_TYPES = {"openai", "vllm"}
GPU_METRIC_KEYWORDS = (
    "gpu",
    "cuda",
    "kv_cache",
    "cache_usage",
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
)


@dataclass
class LLMTarget:
    id: str
    name: str
    host: str
    port: int
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
    status: str = "unknown"
    uptime: str = ""
    queue_state: str = "idle"
    remote_gpu_info: str = ""
    remote_gpu_type: str = ""
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


def admin_password() -> str:
    value = os.getenv("LLM_ROUTING_ADMIN_PASSWORD", "").strip()
    if value:
        return value
    ensure_admin_password()
    try:
        return ADMIN_PASSWORD_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "change-me-now"


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
                    model=str(item.get("model") or ""),
                    api_type=str(item.get("api_type") or "ollama"),
                    gpu_info=str(item.get("gpu_info") or ""),
                    gpu_type=str(item.get("gpu_type") or ""),
                    selected_gpu=str(item.get("selected_gpu") or ""),
                    selected_gpu_label=str(item.get("selected_gpu_label") or ""),
                    access_id=str(item.get("access_id") or ""),
                    password=str(item.get("password") or ""),
                    enabled=bool(item.get("enabled", True)),
                    weight=max(1, int(item.get("weight") or 1)),
                    notes=str(item.get("notes") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return targets


def save_targets(targets: list[LLMTarget]) -> None:
    save_json(CONFIG_PATH, {"targets": [target.__dict__ for target in targets]})


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
    if target.selected_gpu_label:
        return target.selected_gpu_label
    if target.selected_gpu:
        detail = " ".join(part for part in (target.gpu_type, target.gpu_info) if part).strip()
        return f"GPU {target.selected_gpu}: {detail}" if detail else f"GPU {target.selected_gpu}"
    detail = " ".join(part for part in (target.gpu_type, target.gpu_info) if part).strip()
    return detail or "auto"


def sync_queue_metric(target_id: str) -> None:
    with STATE_LOCK:
        q = TARGET_QUEUES.get(target_id)
        metric = metric_for(target_id)
        metric.pending_queue = q.qsize() if q else 0
        metric.queue_state = "running" if metric.active_requests else ("pending" if metric.pending_queue else "idle")
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
        metric.queue_state = "running"
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
            metric.queue_state = "idle" if metric.active_requests == 0 and metric.pending_queue == 0 else ("running" if metric.active_requests else "pending")
            recent = metric.recent_response_seconds
            recent.append(elapsed)
            del recent[:-30]
            store_metric(target.id, metric)
        update_client_stats(client, elapsed)
        record_access({"client": client, "target": target.name, "target_id": target.id, "status": "ok", "response_seconds": round(elapsed, 3)})
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
            metric.queue_state = "idle" if metric.active_requests == 0 and metric.pending_queue == 0 else ("running" if metric.active_requests else "pending")
            store_metric(target.id, metric)
        record_access({"client": client, "target": target.name, "target_id": target.id, "status": "error", "error": str(exc), "response_seconds": round(elapsed, 3)})
        raise


def route_prompt(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> dict[str, Any]:
    if not prompt_text(payload).strip():
        raise ValueError("prompt or messages is required.")
    target = choose_target(payload)
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
        raise TimeoutError(f"Queued prompt timed out after {wait_timeout}s for target {target.name}.")
    if job.error is not None:
        raise job.error
    result = dict(job.result or {})
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
                    "response_seconds": 0.0,
                    "error": f"Queue is full for target {target.name}. max_per_target={QUEUE_MAX_PER_TARGET}",
                }
            )

    backend_timeout = int(payload.get("timeout") or DEFAULT_TIMEOUT_SECONDS)
    wait_timeout = int(payload.get("request_timeout") or (backend_timeout + QUEUE_MAX_PER_TARGET * backend_timeout + 10))
    for job in jobs:
        target = job.target
        if not job.done.wait(wait_timeout):
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
                    "response_seconds": time.time() - job.enqueued_at,
                    "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                    "error": f"Queued comparison prompt timed out after {wait_timeout}s for target {target.name}.",
                }
            )
            continue
        if job.error is not None:
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
                    "response_seconds": time.time() - job.enqueued_at,
                    "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                    "error": str(job.error),
                }
            )
            continue
        data = job.result or {}
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
                "response_seconds": data.get("response_seconds", time.time() - job.enqueued_at),
                "queue_wait_seconds": max(0.0, (job.started_at or time.time()) - job.enqueued_at),
                "response": data.get("response", ""),
                "raw": data.get("raw", {}),
            }
        )

    return {
        "ok": any(item.get("ok") for item in results),
        "target_count": len(targets),
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
            "response_seconds": data.get("response_seconds"),
        },
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


def local_system_stats() -> dict[str, Any]:
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    cpu_count = os.cpu_count() or 0
    gpu_text = run_command(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], timeout=4)
    if not gpu_text or "No such file" in gpu_text:
        gpu_text = run_command(["system_profiler", "SPDisplaysDataType"], timeout=5)
    return {
        "hostname": socket.gethostname(),
        "service_uptime": seconds_to_uptime(time.time() - STARTED_AT),
        "cpu_count": cpu_count,
        "load_average": [round(value, 2) for value in load_avg],
        "gpu_status": gpu_text[:5000],
        "access_log": read_access_log(100),
    }


def status_payload() -> dict[str, Any]:
    targets = load_targets()
    ensure_target_queues(targets)
    health_by_id: dict[str, dict[str, Any]] = {}
    for target in targets:
        metric = metric_for(target.id)
        q = TARGET_QUEUES.get(target.id)
        local_pending = q.qsize() if q else 0
        if target.enabled and (not metric.last_seen_at or metric.status == "unknown"):
            health = target_health(target)
            metric.status = "ok" if health["ok"] else "error"
            metric.last_error = "" if health["ok"] else health.get("error", "")
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
                metric.queue_state = "running" if metric.active_requests else ("pending" if metric.pending_queue else "idle")
            elif isinstance(data, dict):
                queue = data.get("prompt_queue") if isinstance(data.get("prompt_queue"), dict) else {}
                if isinstance(queue.get("pending_count"), int):
                    metric.pending_queue = int(queue.get("pending_count", 0))
                if isinstance(queue.get("average_prompt_processing_seconds"), (int, float)):
                    metric.last_response_seconds = float(queue.get("average_prompt_processing_seconds", 0.0))
                if data.get("uptime_human"):
                    metric.uptime = str(data.get("uptime_human"))
                gpus = data.get("gpus") if isinstance(data.get("gpus"), list) else []
                gpu_names = [str(gpu.get("name")) for gpu in gpus if isinstance(gpu, dict) and gpu.get("name")]
                if gpu_names:
                    metric.remote_gpu_info = ", ".join(gpu_names)
                    selected = str(data.get("selected_gpu_label") or "")
                    metric.remote_gpu_type = selected or gpu_names[0]
                metric.queue_state = "pending" if metric.pending_queue else "idle"
            metric.last_seen_at = now_text()
        metric.pending_queue = max(metric.pending_queue, local_pending)
        metric.queue_state = "running" if metric.active_requests else ("pending" if metric.pending_queue else "idle")
        store_metric(target.id, metric)
        health_by_id[target.id] = metric.__dict__ | {
            "average_response_seconds": metric.average_response_seconds,
            "gpu_info": metric.remote_gpu_info or target.gpu_info,
            "gpu_type": metric.remote_gpu_type or target.gpu_type,
            "queue_max_per_target": QUEUE_MAX_PER_TARGET,
        }

    now = time.time()
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
        "targets": [target.__dict__ for target in targets],
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
    table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    th, td { border-bottom:1px solid var(--line); padding:9px; text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:12px; text-transform:uppercase; }
    input, select, textarea { width:100%; min-height:36px; border:1px solid var(--line); border-radius:6px; padding:8px; font:inherit; background:#fff; }
    textarea { min-height:76px; resize:vertical; }
    .form-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; align-items:end; }
    .model-row { display:grid; grid-template-columns:minmax(0,2fr) minmax(0,2fr) auto; gap:10px; margin-top:10px; align-items:end; }
    .model-status { color:var(--muted); font-size:13px; align-self:center; min-height:20px; }
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
    <div class="panel" style="margin-top:14px">
      <div class="form-grid">
        <input id="name" placeholder="이름">
        <input id="host" placeholder="IP 주소">
        <input id="port" placeholder="PORT" type="number">
        <select id="api_type"><option value="ollama">ollama</option><option value="openai">openai</option><option value="vllm">vllm</option></select>
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
      <div class="model-row">
        <input id="model" placeholder="모델 이름">
        <select id="model_select"><option value="">모델 목록</option></select>
        <button onclick="loadModels()">모델 조회</button>
      </div>
      <div id="model_status" class="model-status"></div>
      <input id="target_id" type="hidden">
    </div>
    <table><thead><tr><th>상태</th><th>LLM</th><th>주소</th><th>모델</th><th>GPU</th><th>Queue</th><th>처리 수</th><th>평균 응답</th><th>관리</th></tr></thead><tbody id="targetRows"></tbody></table>
  </section>
  <section id="service">
    <div class="grid" id="serviceMetrics"></div>
    <table><thead><tr><th>클라이언트</th><th>요청 prompt 수</th><th>초당 질의</th><th>최근 응답</th><th>최근 접속</th></tr></thead><tbody id="clientRows"></tbody></table>
  </section>
  <section id="local">
    <div class="grid" id="localMetrics"></div>
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
  renderTargets(); renderService(); renderLocal(); renderTestTargets();
}
function renderTargets() {
  const targets = state.targets || [];
  const metrics = state.metrics || {};
  document.getElementById('targetMetrics').innerHTML = [
    metric('등록 LLM', targets.length),
    metric('활성 LLM', targets.filter(t => t.enabled).length),
    metric('전체 pending queue', targets.reduce((n,t)=>n+(metrics[t.id]?.pending_queue||0),0)),
    metric('전체 처리 prompt', targets.reduce((n,t)=>n+(metrics[t.id]?.total_prompts||0),0))
  ].join('');
  document.getElementById('targetRows').innerHTML = targets.map(t => {
    const m = metrics[t.id] || {};
    const cls = m.status === 'ok' ? 'ok' : (m.status === 'error' ? 'error' : 'warn');
    return `<tr>
      <td><span class="${cls}">${esc(m.status || 'unknown')}</span><br>${t.enabled ? 'enabled' : 'disabled'}</td>
      <td>${esc(t.name)}<br><small>${esc(t.id)}</small></td>
      <td>${esc(t.host)}:${esc(t.port)}<br><small>${esc(t.api_type)}</small></td>
      <td>${esc(t.model)}</td>
      <td>${esc(m.gpu_type || t.gpu_type)}<br><small>${esc(t.selected_gpu_label || m.gpu_info || t.gpu_info)}</small><br><small>selected: ${esc(t.selected_gpu || 'auto')}</small></td>
      <td>${esc(m.queue_state || 'idle')}<br>active ${m.active_requests||0}, pending ${m.pending_queue||0}/${m.queue_max_per_target||10}</td>
      <td>${m.total_prompts||0}</td>
      <td>${Number(m.average_response_seconds||0).toFixed(2)}s<br><small>${esc(m.last_error||'')}</small></td>
      <td><button onclick='editTarget(${JSON.stringify(t)})'>편집</button> <button class="danger" onclick="deleteTarget('${t.id}')">삭제</button></td>
    </tr>`;
  }).join('');
}
function renderService() {
  const service = state.service || {};
  const clients = service.clients || [];
  document.getElementById('serviceMetrics').innerHTML = [
    metric('접속 prompt 클라이언트', service.client_count || 0),
    metric('전체 클라이언트 요청', clients.reduce((n,c)=>n+(c.prompt_count||0),0)),
    metric('총 QPS', clients.reduce((n,c)=>n+(c.qps||0),0).toFixed(3)),
    metric('라우터 uptime', state.uptime || '')
  ].join('');
  document.getElementById('clientRows').innerHTML = clients.map(c => `<tr><td>${esc(c.client)}</td><td>${c.prompt_count}</td><td>${c.qps}</td><td>${c.last_response_seconds}s</td><td>${esc(c.last_seen)}</td></tr>`).join('');
}
function renderLocal() {
  const local = state.local || {};
  document.getElementById('localMetrics').innerHTML = [
    metric('호스트', local.hostname || ''),
    metric('CPU cores', local.cpu_count || 0),
    metric('Load avg', (local.load_average || []).join(', ')),
    metric('서비스 uptime', local.service_uptime || '')
  ].join('');
  document.getElementById('gpuStatus').textContent = local.gpu_status || '';
  document.getElementById('accessLog').textContent = JSON.stringify(local.access_log || [], null, 2);
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
    const gpuInfo = m.gpu_info || t.gpu_info || '';
    return `<tr>
      <td>${esc(t.name)}<br><small>${esc(t.id)}</small></td>
      <td>${esc(t.host)}:${esc(t.port)}<br><small>${esc(t.api_type)}</small></td>
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
  for (const key of ['target_id','name','host','port','model','api_type','gpu_type','gpu_info','selected_gpu','selected_gpu_label','access_id','password','notes']) {
    const id = key === 'target_id' ? 'target_id' : key;
    const value = key === 'target_id' ? t.id : t[key];
    document.getElementById(id).value = value || '';
  }
  setModelOptions([], t.model || '');
  setGpuOptions([], t.selected_gpu || '');
  document.getElementById('model_status').textContent = '';
}
function clearForm() {
  for (const id of ['target_id','name','host','port','model','gpu_type','gpu_info','selected_gpu_label','access_id','password','notes']) document.getElementById(id).value = '';
  document.getElementById('api_type').value = 'ollama';
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
  for (const id of ['target_id','name','host','port','model','api_type','gpu_type','gpu_info','selected_gpu','access_id','password','notes']) payload[id === 'target_id' ? 'id' : id] = document.getElementById(id).value;
  const gpuSelect = document.getElementById('selected_gpu');
  payload.selected_gpu_label = gpuSelect.value ? (gpuSelect.options[gpuSelect.selectedIndex]?.textContent || '') : '';
  payload.enabled = true;
  await api('/api/targets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  clearForm(); await refresh();
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
setInterval(refresh, 5000);
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
            if not self.require_auth():
                return
            self.write_json(status_payload())
            return
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/login":
                if secrets.compare_digest(str(payload.get("password") or ""), admin_password()):
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
                self.write_json(route_prompt(self, payload))
                return
            if self.path == "/v1/chat/completions":
                self.write_json(openai_chat_response(route_prompt(self, payload)))
                return
            if not self.require_auth():
                return
            if self.path == "/api/compare":
                self.write_json(compare_prompt(self, payload))
                return
            if self.path == "/api/targets":
                self.write_json({"ok": True, "target": self.upsert_target(payload)})
                return
            if self.path == "/api/delete-target":
                self.write_json({"ok": True, "deleted": self.delete_target(str(payload.get("id") or ""))})
                return
            if self.path == "/api/models":
                target = target_from_lookup_payload(payload)
                self.write_json({"ok": True, **fetch_target_options(target)})
                return
            self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except QueueFullError as exc:
            self.write_json({"ok": False, "error": str(exc)}, HTTPStatus.TOO_MANY_REQUESTS)
        except ValueError as exc:
            self.write_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            detail = f"Backend HTTP {exc.code}: {exc.reason}"
            if body:
                detail = f"{detail}\n{body[:2000]}"
            self.write_json({"ok": False, "error": detail}, HTTPStatus.BAD_GATEWAY)
        except Exception as exc:  # noqa: BLE001
            self.write_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
            model=str(payload.get("model") or "").strip(),
            api_type=str(payload.get("api_type") or "ollama").strip(),
            gpu_info=str(payload.get("gpu_info") or "").strip(),
            gpu_type=str(payload.get("gpu_type") or "").strip(),
            selected_gpu=str(payload.get("selected_gpu") or "").strip(),
            selected_gpu_label=str(payload.get("selected_gpu_label") or "").strip(),
            access_id=str(payload.get("access_id") or "").strip(),
            password=str(payload.get("password") or ""),
            enabled=bool(payload.get("enabled", True)),
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
        return new_target.__dict__

    def delete_target(self, target_id: str) -> bool:
        if not target_id:
            raise ValueError("id is required.")
        targets = load_targets()
        filtered = [target for target in targets if target.id != target_id]
        save_targets(filtered)
        with STATE_LOCK:
            TARGET_RUNTIME.pop(target_id, None)
        return len(filtered) != len(targets)


def main() -> int:
    parser = argparse.ArgumentParser(description="Route prompt requests to multiple LLM backends.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    ensure_default_config()
    ensure_admin_password()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), RoutingHandler)
    print(f"LLM Routing listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping LLM Routing", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
