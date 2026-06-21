#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import errno
import getpass
import hashlib
import hmac
import html
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.getenv("WRITING_MACH_HOST", "127.0.0.1")
PORT = int(os.getenv("WRITING_MACH_PORT", "8786"))
WEB_AUTH_USER = os.getenv("WRITING_MACH_WEB_USER", "")
WEB_AUTH_PASSWORD = os.getenv("WRITING_MACH_WEB_PASSWORD", "")
PROMPT_SENT = False
PROMPT_SENT_LOCK = threading.Lock()
SERVICE_LOG_PATH: Path | None = None
SERVICE_LOG_LOCK = threading.Lock()
RUNTIME_CONFIG_OVERRIDES: dict[str, Any] = {}
LLM_TRACE_DIR: Path | None = None
LLM_TRACE_LOCK = threading.Lock()
LLM_TRACE_COUNTER = 0
CHECKPOINT_LOCK = threading.Lock()
CHECKPOINT_PATH: Path | None = None
CHECKPOINT_STATE: dict[str, Any] | None = None

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_PATH = DATA_DIR / "client_config.json"
SAMPLE_CONFIG_PATH = BASE_DIR / "config" / "client_config.sample.json"
BACKBONE_PATH = BASE_DIR / "story_backbone.md"
USE_COLOR = os.getenv("NO_COLOR", "").strip() == "" and os.getenv("WRITING_MACH_NO_COLOR", "").strip() == ""

COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "red": "\033[31m",
    "bold": "\033[1m",
}

DEFAULT_CONFIG = {
    "server_base_url": "http://127.0.0.1:8082",
    "generate_path": "/api/generate",
    "status_path": "/api/status",
    "request_timeout_seconds": 600,
    "user_id": "",
    "password": "",
    "model": "",
    "keep_alive": "6m",
    "num_ctx": 8192,
    "target_words_per_chapter": 1800,
    "language": "ko",
    "chapter_parallelism": 1,
    "chapter_retry": 2,
    "model_retry_wait_seconds": 30,
    "model_retry_prompt_after_failures": 10,
    "model_retry_status_timeout_seconds": 10,
    "model_retry_max_timeout_multiplier": 3,
    "pipeline_agents": ["outline", "writer", "reviewer", "finalizer"],
    "agent_workers": [],
    "global_review_enabled": True,
    "global_review_mode": "strict",
    "global_review_focus": [
        "전체 논지 일관성",
        "챕터 간 반복 제거",
        "용어 통일",
        "시대 흐름 점검",
        "도입부와 결론의 연결",
    ],
    "allow_global_rewrite": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Writing Mach client service.")
    parser.add_argument(
        "--host",
        default=HOST,
        help=f"Server bind address. Defaults to WRITING_MACH_HOST or {HOST}.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help=f"Server bind port. Defaults to WRITING_MACH_PORT or {PORT}.",
    )
    parser.add_argument(
        "--backbone",
        default=str(BACKBONE_PATH),
        help=f"Story backbone markdown file. Defaults to {BACKBONE_PATH}.",
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help=f"Client config JSON file. Defaults to {CONFIG_PATH}.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test LLM status and generation using the selected config, then exit without starting the web service.",
    )
    parser.add_argument(
        "--run-on-start",
        action="store_true",
        help="Start book generation immediately after the service starts, without waiting for the web button.",
    )
    parser.add_argument(
        "--exit-after-run",
        action="store_true",
        help="Exit the service after --run-on-start completes.",
    )
    parser.add_argument(
        "--model-check-timeout",
        type=int,
        default=int(os.getenv("WRITING_MACH_MODEL_CHECK_TIMEOUT", "5")),
        help="Seconds to wait for startup LLM status checks. Defaults to WRITING_MACH_MODEL_CHECK_TIMEOUT or 5.",
    )
    parser.add_argument(
        "--web-user",
        default=os.getenv("WRITING_MACH_WEB_USER"),
        help="Web login user. If omitted, prompts during startup.",
    )
    parser.add_argument(
        "--web-password",
        default=os.getenv("WRITING_MACH_WEB_PASSWORD"),
        help="Web login password. If omitted, prompts during startup. Use an empty value to disable web auth.",
    )
    parser.add_argument(
        "--llm-user",
        default=os.getenv("WRITING_MACH_LLM_USER"),
        help="LLM API user_id override. Does not write to the config file.",
    )
    parser.add_argument(
        "--llm-password",
        default=os.getenv("WRITING_MACH_LLM_PASSWORD"),
        help="LLM API password override. Does not write to the config file.",
    )
    parser.add_argument(
        "--prompt-warning-seconds",
        type=int,
        default=int(os.getenv("WRITING_MACH_PROMPT_WARNING_SECONDS", "10")),
        help="Seconds to wait after service startup before warning that no LLM prompt was sent.",
    )
    parser.add_argument(
        "--model-retry-wait-seconds",
        type=int,
        default=None,
        help="Seconds to wait before retrying a failed chapter while the model server is still alive.",
    )
    parser.add_argument(
        "--model-retry-prompt-after-failures",
        type=int,
        default=None,
        help="Ask whether to stop after this many total model failures. Defaults to 10.",
    )
    parser.add_argument(
        "--log-file",
        default=os.getenv("WRITING_MACH_LOG_FILE", ""),
        help="Service progress log file. Defaults to output/service_YYYYMMDD_HHMMSS.log.",
    )
    return parser.parse_args()


def color_text(text: str, color: str) -> str:
    if not USE_COLOR:
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def progress_log(stage: str, message: str, color: str = "cyan", started: float | None = None) -> None:
    elapsed = ""
    plain_elapsed = ""
    if started is not None:
        plain_elapsed = f" +{time.perf_counter() - started:.1f}s"
        elapsed = color_text(plain_elapsed, "dim")
    stamp = time.strftime("%H:%M:%S")
    prefix = color_text(f"[{stamp}] [{stage}]", color)
    print(f"{prefix}{elapsed} {message}", flush=True)
    if SERVICE_LOG_PATH is not None:
        line = f"[{stamp}] [{stage}]{plain_elapsed} {message}\n"
        with SERVICE_LOG_LOCK:
            try:
                SERVICE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with SERVICE_LOG_PATH.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            except OSError:
                pass


class ChapterPipelineError(Exception):
    def __init__(
        self,
        message: str,
        *,
        failed_agent: str = "",
        partial_result: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_agent = failed_agent
        self.partial_result = partial_result or {}


AGENT_OUTPUT_KEYS = {
    "outline": "outline",
    "writer": "draft",
    "reviewer": "review",
    "finalizer": "final",
}


AGENT_REQUIRED_KEYS = {
    "outline": [],
    "writer": ["outline"],
    "reviewer": ["outline", "draft"],
    "finalizer": ["review"],
}


def first_runnable_agent_index(pipeline_agents: list[str], outputs: dict[str, str], requested_agent: str = "") -> int:
    start_index = pipeline_agents.index(requested_agent) if requested_agent in pipeline_agents else 0
    for index, agent in enumerate(pipeline_agents[: start_index + 1]):
        output_key = AGENT_OUTPUT_KEYS.get(agent, "")
        if output_key and outputs.get(output_key):
            continue
        return index
    return start_index


def init_service_log(log_file: str = "") -> Path:
    global SERVICE_LOG_PATH

    if log_file.strip():
        SERVICE_LOG_PATH = Path(log_file).expanduser().resolve()
    else:
        SERVICE_LOG_PATH = OUTPUT_DIR / f"service_{time.strftime('%Y%m%d_%H%M%S')}.log"
    SERVICE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERVICE_LOG_PATH.write_text("", encoding="utf-8")
    return SERVICE_LOG_PATH


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def preview_text(text: str, limit: int = 700) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def init_llm_trace_dir() -> Path:
    global LLM_TRACE_DIR, LLM_TRACE_COUNTER

    trace_dir = OUTPUT_DIR / f"llm_trace_{time.strftime('%Y%m%d_%H%M%S')}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    with LLM_TRACE_LOCK:
        LLM_TRACE_DIR = trace_dir
        LLM_TRACE_COUNTER = 0
    return trace_dir


def safe_trace_name(value: str) -> str:
    name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value or "").strip("_")
    return (name or "model")[:80]


def save_llm_trace(
    *,
    url: str,
    config: dict[str, Any],
    prompt: str,
    started_at: str,
    elapsed_seconds: float,
    label: str = "",
    response: str = "",
    error: str = "",
    raw_response: dict[str, Any] | None = None,
) -> str:
    trace_dir = LLM_TRACE_DIR
    if trace_dir is None:
        return ""

    with LLM_TRACE_LOCK:
        global LLM_TRACE_COUNTER
        LLM_TRACE_COUNTER += 1
        trace_number = LLM_TRACE_COUNTER

    worker_name = safe_trace_name(str(config.get("name") or config.get("model") or "model"))
    path = trace_dir / f"{trace_number:04d}_{worker_name}.json"
    payload = {
        "sequence": trace_number,
        "created_at": started_at,
        "elapsed_seconds": elapsed_seconds,
        "label": label,
        "url": url,
        "worker": config.get("name", ""),
        "model": config.get("model", ""),
        "prompt_word_count": word_count(prompt),
        "response_word_count": word_count(response),
        "prompt": prompt,
        "response": response,
        "error": error,
        "raw_response": raw_response or {},
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        progress_log("warning", f"failed to write LLM trace {path}: {exc}", "yellow")
        return ""
    return str(path)


def mark_prompt_sent() -> None:
    global PROMPT_SENT

    with PROMPT_SENT_LOCK:
        first_prompt = not PROMPT_SENT
        PROMPT_SENT = True
    if first_prompt:
        progress_log("model-request", "first LLM prompt is being sent", "green")


def schedule_prompt_wait_warning(seconds: int, url: str) -> None:
    wait_seconds = max(1, int(seconds))

    def warn_if_no_prompt() -> None:
        with PROMPT_SENT_LOCK:
            prompt_sent = PROMPT_SENT
        if prompt_sent:
            return
        progress_log(
            "service",
            (
                f"No LLM prompt has been sent after {wait_seconds}s. "
                f"Open {url}, log in, then start book generation. "
                "If you already clicked run, check the browser error and LLM status."
            ),
            "yellow",
        )

    timer = threading.Timer(wait_seconds, warn_if_no_prompt)
    timer.daemon = True
    timer.start()


def bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def backbone_bool_value(value: str) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
        "enable",
        "enabled",
        "parallel",
        "사용",
        "사용함",
        "켜기",
        "활성",
        "활성화",
        "병렬",
        "병렬실행",
    }


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = {key: value for key, value in config.items() if not key.startswith("_")}
    redacted.pop("password", None)
    redacted["agent_workers"] = [
        {key: value for key, value in worker.items() if key not in {"password", "agent_workers"}}
        for worker in config.get("agent_workers", [])
    ]
    return redacted


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "checkpoints").mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        sample = DEFAULT_CONFIG
        if SAMPLE_CONFIG_PATH.exists():
            try:
                sample = normalize_config(json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                sample = DEFAULT_CONFIG
        CONFIG_PATH.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checkpoint_key(backbone: str) -> str:
    return hashlib.sha256(backbone.encode("utf-8")).hexdigest()[:16]


def checkpoint_file_for(backbone: str) -> Path:
    return OUTPUT_DIR / "checkpoints" / f"checkpoint_{checkpoint_key(backbone)}.json"


def empty_chapter_checkpoint(chapter: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "chapter": chapter,
        "status": "pending",
        "failed_agent": "",
        "worker": "",
        "updated_at": "",
        "completed_agents": [],
        "outline": "",
        "draft": "",
        "review": "",
        "final": "",
    }


def init_checkpoint(backbone: str, config: dict[str, Any], chapters: list[dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
    global CHECKPOINT_PATH, CHECKPOINT_STATE

    path = checkpoint_file_for(backbone)
    loaded: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}

    if loaded.get("status") == "completed":
        loaded = {}

    chapter_map = loaded.get("chapters") if isinstance(loaded.get("chapters"), dict) else {}
    if not chapter_map:
        chapter_map = {}
    for index, chapter in enumerate(chapters, start=1):
        key = str(chapter["number"])
        existing = chapter_map.get(key) if isinstance(chapter_map.get(key), dict) else {}
        base = empty_chapter_checkpoint(chapter, index)
        base.update(existing)
        base["chapter"] = chapter
        base["index"] = index
        chapter_map[key] = base

    state = {
        "version": 1,
        "checkpoint_key": checkpoint_key(backbone),
        "status": "running",
        "created_at": loaded.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "title": title_from_backbone(backbone),
        "backbone_hash": checkpoint_key(backbone),
        "config": public_config(config),
        "chapters": chapter_map,
        "coordinator_notes": loaded.get("coordinator_notes", ""),
        "revised_opening": loaded.get("revised_opening", ""),
        "events": loaded.get("events", [])[-300:] if isinstance(loaded.get("events"), list) else [],
    }
    with CHECKPOINT_LOCK:
        CHECKPOINT_PATH = path
        CHECKPOINT_STATE = state
        save_checkpoint_locked()
    return path, state


def save_checkpoint_locked() -> None:
    if CHECKPOINT_PATH is None or CHECKPOINT_STATE is None:
        return
    CHECKPOINT_STATE["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(CHECKPOINT_STATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checkpoint_event(stage: str, message: str) -> None:
    with CHECKPOINT_LOCK:
        if CHECKPOINT_STATE is None:
            return
        events = CHECKPOINT_STATE.setdefault("events", [])
        events.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage": stage, "message": message})
        del events[:-500]
        save_checkpoint_locked()


def checkpoint_update_chapter(
    chapter: dict[str, Any],
    *,
    index: int,
    worker: str,
    status: str,
    outputs: dict[str, str],
    completed_agent: str = "",
    failed_agent: str = "",
) -> None:
    with CHECKPOINT_LOCK:
        if CHECKPOINT_STATE is None:
            return
        key = str(chapter["number"])
        chapters = CHECKPOINT_STATE.setdefault("chapters", {})
        entry = chapters.get(key) if isinstance(chapters.get(key), dict) else empty_chapter_checkpoint(chapter, index)
        entry["index"] = index
        entry["chapter"] = chapter
        entry["worker"] = worker
        entry["status"] = status
        entry["failed_agent"] = failed_agent
        entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        for output_key in ("outline", "draft", "review", "final"):
            if outputs.get(output_key):
                entry[output_key] = outputs[output_key]
        if completed_agent:
            completed = entry.setdefault("completed_agents", [])
            if completed_agent not in completed:
                completed.append(completed_agent)
            events = CHECKPOINT_STATE.setdefault("events", [])
            events.append(
                {
                    "time": entry["updated_at"],
                    "stage": f"{chapter['title']}:{completed_agent}",
                    "message": "agent stage completed and output saved",
                }
            )
            del events[:-500]
        if failed_agent:
            events = CHECKPOINT_STATE.setdefault("events", [])
            events.append(
                {
                    "time": entry["updated_at"],
                    "stage": f"{chapter['title']}:{failed_agent}",
                    "message": "agent stage failed; partial outputs saved for resume",
                }
            )
            del events[:-500]
        if status == "completed":
            events = CHECKPOINT_STATE.setdefault("events", [])
            events.append(
                {
                    "time": entry["updated_at"],
                    "stage": chapter["title"],
                    "message": "chapter completed and final output saved",
                }
            )
            del events[:-500]
        chapters[key] = entry
        save_checkpoint_locked()


def checkpoint_chapter_entry(chapter: dict[str, Any]) -> dict[str, Any]:
    with CHECKPOINT_LOCK:
        if CHECKPOINT_STATE is None:
            return {}
        entry = CHECKPOINT_STATE.get("chapters", {}).get(str(chapter["number"]), {})
        return dict(entry) if isinstance(entry, dict) else {}


def checkpoint_set_field(key: str, value: Any) -> None:
    with CHECKPOINT_LOCK:
        if CHECKPOINT_STATE is None:
            return
        CHECKPOINT_STATE[key] = value
        save_checkpoint_locked()


def checkpoint_mark_status(status: str) -> None:
    with CHECKPOINT_LOCK:
        if CHECKPOINT_STATE is None:
            return
        CHECKPOINT_STATE["status"] = status
        save_checkpoint_locked()


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    timeout = int(incoming.get("request_timeout_seconds") or DEFAULT_CONFIG["request_timeout_seconds"])
    num_ctx = int(incoming.get("num_ctx") or DEFAULT_CONFIG["num_ctx"])
    target_words = int(incoming.get("target_words_per_chapter") or DEFAULT_CONFIG["target_words_per_chapter"])
    chapter_parallelism = int(incoming.get("chapter_parallelism") or DEFAULT_CONFIG["chapter_parallelism"])
    chapter_retry = int(incoming.get("chapter_retry") or DEFAULT_CONFIG["chapter_retry"])
    retry_wait = int(incoming.get("model_retry_wait_seconds") or DEFAULT_CONFIG["model_retry_wait_seconds"])
    retry_prompt_after = int(
        incoming.get("model_retry_prompt_after_failures") or DEFAULT_CONFIG["model_retry_prompt_after_failures"]
    )
    retry_status_timeout = int(
        incoming.get("model_retry_status_timeout_seconds") or DEFAULT_CONFIG["model_retry_status_timeout_seconds"]
    )
    retry_max_timeout_multiplier = int(
        incoming.get("model_retry_max_timeout_multiplier")
        or DEFAULT_CONFIG["model_retry_max_timeout_multiplier"]
    )
    pipeline_agents = incoming.get("pipeline_agents") or DEFAULT_CONFIG["pipeline_agents"]
    if isinstance(pipeline_agents, str):
        pipeline_agents = [item.strip() for item in pipeline_agents.split(",") if item.strip()]
    pipeline_agents = [agent for agent in pipeline_agents if agent in {"outline", "writer", "reviewer", "finalizer"}]
    focus = incoming.get("global_review_focus") or DEFAULT_CONFIG["global_review_focus"]
    if isinstance(focus, str):
        focus = [item.strip() for item in re.split(r"[,;\n]", focus) if item.strip()]

    normalized = {
        "server_base_url": str(incoming.get("server_base_url") or DEFAULT_CONFIG["server_base_url"]).rstrip("/"),
        "generate_path": str(incoming.get("generate_path") or DEFAULT_CONFIG["generate_path"]),
        "status_path": str(incoming.get("status_path") or DEFAULT_CONFIG["status_path"]),
        "request_timeout_seconds": max(5, timeout),
        "user_id": str(incoming.get("user_id") or ""),
        "password": str(incoming.get("password") or ""),
        "model": str(incoming.get("model") or ""),
        "keep_alive": str(incoming.get("keep_alive") or DEFAULT_CONFIG["keep_alive"]),
        "num_ctx": max(0, num_ctx),
        "target_words_per_chapter": max(300, target_words),
        "language": str(incoming.get("language") or DEFAULT_CONFIG["language"]),
        "chapter_parallelism": max(1, chapter_parallelism),
        "chapter_retry": max(1, chapter_retry),
        "model_retry_wait_seconds": max(1, retry_wait),
        "model_retry_prompt_after_failures": max(1, retry_prompt_after),
        "model_retry_status_timeout_seconds": max(1, retry_status_timeout),
        "model_retry_max_timeout_multiplier": max(1, retry_max_timeout_multiplier),
        "pipeline_agents": pipeline_agents or list(DEFAULT_CONFIG["pipeline_agents"]),
        "agent_workers": incoming.get("agent_workers") if isinstance(incoming.get("agent_workers"), list) else [],
        "global_review_enabled": bool_value(
            incoming.get("global_review_enabled"),
            bool(DEFAULT_CONFIG["global_review_enabled"]),
        ),
        "global_review_mode": str(incoming.get("global_review_mode") or DEFAULT_CONFIG["global_review_mode"]),
        "global_review_focus": focus if isinstance(focus, list) else list(DEFAULT_CONFIG["global_review_focus"]),
        "allow_global_rewrite": bool_value(
            incoming.get("allow_global_rewrite"),
            bool(DEFAULT_CONFIG["allow_global_rewrite"]),
        ),
    }
    normalized["agent_workers"] = normalize_agent_workers(normalized)
    return normalized


def normalize_agent_workers(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_workers = config.get("agent_workers") or []
    workers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_workers):
        if not isinstance(raw, dict):
            continue
        server_base_url = str(raw.get("server_base_url") or "").strip().rstrip("/")
        if not server_base_url:
            continue
        worker = {
            "name": str(raw.get("name") or f"worker-{index + 1}"),
            "server_base_url": server_base_url,
            "generate_path": str(raw.get("generate_path") or config["generate_path"]),
            "status_path": str(raw.get("status_path") or config["status_path"]),
            "request_timeout_seconds": int(raw.get("request_timeout_seconds") or config["request_timeout_seconds"]),
            "user_id": str(raw.get("user_id") if raw.get("user_id") is not None else config["user_id"]),
            "password": str(raw.get("password") if raw.get("password") is not None else config["password"]),
            "model": str(raw.get("model") if raw.get("model") is not None else config["model"]),
            "keep_alive": str(raw.get("keep_alive") or config["keep_alive"]),
            "num_ctx": int(raw.get("num_ctx") or config["num_ctx"]),
            "max_parallel": max(1, int(raw.get("max_parallel") or 1)),
        }
        workers.append(worker)

    if workers:
        return workers

    return [
        {
            "name": "default",
            "server_base_url": config["server_base_url"],
            "generate_path": config["generate_path"],
            "status_path": config["status_path"],
            "request_timeout_seconds": config["request_timeout_seconds"],
            "user_id": config["user_id"],
            "password": config["password"],
            "model": config["model"],
            "keep_alive": config["keep_alive"],
            "num_ctx": config["num_ctx"],
            "max_parallel": max(1, int(config.get("chapter_parallelism") or 1)),
        }
    ]


def read_config() -> dict[str, Any]:
    ensure_dirs()
    try:
        return normalize_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return normalize_config(DEFAULT_CONFIG)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    normalized = normalize_config(config)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def runtime_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = read_config()
    for key, value in dict(override or {}).items():
        if key in DEFAULT_CONFIG:
            if key in {"user_id", "password"} and value == "" and merged.get(key):
                continue
            merged[key] = value
    merged.update(RUNTIME_CONFIG_OVERRIDES)
    return normalize_config(merged)


def read_story_backbone() -> str:
    if not BACKBONE_PATH.exists():
        raise ValueError(f"story_backbone.md not found: {BACKBONE_PATH}")
    return BACKBONE_PATH.read_text(encoding="utf-8").strip()


def parse_chapters(backbone: str) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in backbone.splitlines():
        match = re.match(r"\s*-\s*(\d+)\s*챕터\s*$", line)
        if match:
            current = {"number": int(match.group(1)), "title": f"{match.group(1)} 챕터", "bullets": []}
            chapters.append(current)
            continue
        if current and re.match(r"\s*-\s+", line):
            bullet = re.sub(r"^\s*-\s*", "", line).strip()
            if bullet and not re.search(r"챕터|작성방법|main writer|agent", bullet, re.IGNORECASE):
                current["bullets"].append(bullet)
    if not chapters:
        chapters = [{"number": 1, "title": "1 챕터", "bullets": [backbone]}]
    return chapters


def split_backbone_option_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value or "") if item.strip()]


def parse_backbone_key_values(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in split_backbone_option_items(value):
        if "=" in item:
            key, raw_value = item.split("=", 1)
        elif ":" in item and not re.match(r"^https?://", item.strip(), re.IGNORECASE):
            key, raw_value = item.split(":", 1)
        else:
            continue
        parsed[key.strip().lower().replace("-", "_")] = raw_value.strip()
    return parsed


def normalize_backbone_worker(value: str, index: int, base_config: dict[str, Any]) -> dict[str, Any] | None:
    values = parse_backbone_key_values(value)
    if not values and re.search(r"https?://", value, re.IGNORECASE):
        parts = value.split()
        values = {"server_base_url": parts[0]}
        if len(parts) > 1:
            values["name"] = parts[1]

    url = values.get("url") or values.get("server") or values.get("server_base_url") or values.get("base_url")
    if not url:
        return None

    worker = {
        "name": values.get("name") or values.get("이름") or f"backbone-worker-{index}",
        "server_base_url": url.rstrip("/"),
        "generate_path": values.get("generate_path") or values.get("path") or base_config["generate_path"],
        "status_path": values.get("status_path") or base_config["status_path"],
        "request_timeout_seconds": int(values.get("timeout") or values.get("request_timeout_seconds") or base_config["request_timeout_seconds"]),
        "user_id": values.get("user_id") or values.get("id") or base_config["user_id"],
        "password": values.get("password") or values.get("pass") or base_config["password"],
        "model": values.get("model") or values.get("모델") or base_config["model"],
        "keep_alive": values.get("keep_alive") or base_config["keep_alive"],
        "num_ctx": int(values.get("num_ctx") or base_config["num_ctx"]),
        "max_parallel": max(1, int(values.get("max_parallel") or values.get("parallel") or values.get("병렬") or 1)),
    }
    return worker


def parse_backbone_runtime_options(backbone: str, base_config: dict[str, Any], chapter_count: int) -> tuple[dict[str, Any], list[str]]:
    options: dict[str, Any] = {}
    alerts: list[str] = []
    workers: list[dict[str, Any]] = []
    parallel_requested = False
    parallelism_explicit = False

    for raw_line in backbone.splitlines():
        line = re.sub(r"^\s*[-*]\s*", "", raw_line).strip()
        if not line:
            continue

        match = re.match(r"^(?:병렬\s*실행|parallel(?:_run|_enabled)?|parallel)\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if match:
            parallel_requested = backbone_bool_value(match.group(1))
            alerts.append(f"story_backbone.md 병렬실행={parallel_requested}")
            continue

        match = re.match(r"^(?:병렬\s*챕터|동시\s*챕터|parallel\s*chapters|chapter_parallelism|parallelism)\s*[:=]\s*(\d+)", line, re.IGNORECASE)
        if match:
            options["chapter_parallelism"] = max(1, int(match.group(1)))
            parallel_requested = True
            parallelism_explicit = True
            alerts.append(f"story_backbone.md chapter_parallelism={options['chapter_parallelism']}")
            continue

        match = re.match(r"^(?:모델\s*worker|모델\s*워커|agent\s*worker|worker)\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if match:
            worker = normalize_backbone_worker(match.group(1), len(workers) + 1, base_config)
            if worker:
                workers.append(worker)
                parallel_requested = True
                alerts.append(f"story_backbone.md worker={worker['name']} {worker['server_base_url']} model={worker.get('model') or 'default'}")
            continue

    if workers:
        options["agent_workers"] = workers
    if parallel_requested:
        slot_count = sum(max(1, int(worker.get("max_parallel") or 1)) for worker in (workers or base_config.get("agent_workers") or []))
        default_parallelism = max(1, min(chapter_count, slot_count or int(base_config.get("chapter_parallelism") or 1)))
        if not parallelism_explicit:
            options["chapter_parallelism"] = max(int(base_config.get("chapter_parallelism") or 1), default_parallelism)
        options["_backbone_parallel_enabled"] = True
        options["_backbone_parallel_alerts"] = alerts
    return options, alerts


def apply_backbone_runtime_options(config: dict[str, Any], backbone: str, chapter_count: int) -> dict[str, Any]:
    options, _ = parse_backbone_runtime_options(backbone, config, chapter_count)
    if not options:
        return config
    merged = dict(config)
    private_alerts = options.pop("_backbone_parallel_alerts", [])
    parallel_enabled = bool(options.pop("_backbone_parallel_enabled", False))
    merged.update(options)
    normalized = normalize_config(merged)
    normalized["_backbone_parallel_enabled"] = parallel_enabled
    normalized["_backbone_parallel_alerts"] = private_alerts
    return normalized


def join_url(base_url: str, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def request_json(url: str, payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError(f"Timed out waiting for {url} after {timeout} seconds.") from exc
    if not raw.strip():
        raise ValueError(f"Empty response from {url}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw.strip().replace("\n", " ")[:240]
        raise ValueError(f"Expected JSON from {url}; preview={preview!r}") from exc


def build_generate_payload(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "keep_alive": config["keep_alive"],
        "stream": False,
        "options": {"num_ctx": int(config["num_ctx"])},
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def extract_response_text(data: dict[str, Any]) -> str:
    for key in ("response", "text", "output", "content"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            if isinstance(first.get("text"), str):
                return first["text"]
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    return json.dumps(data, ensure_ascii=False, indent=2)


def call_model(config: dict[str, Any], prompt: str, label: str = "", timeout_multiplier: int = 1) -> str:
    generate_url = join_url(config["server_base_url"], config["generate_path"])
    started = time.perf_counter()
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = build_generate_payload(config, prompt)
    label_text = f" [{label}]" if label else ""
    base_timeout_seconds = int(config["request_timeout_seconds"])
    timeout_scale = max(1, int(timeout_multiplier or 1))
    timeout_seconds = base_timeout_seconds * timeout_scale
    prompt_words = word_count(prompt)
    progress_log(
        "model",
        (
            f"request{label_text} -> {generate_url} prompt_words={prompt_words} "
            f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x base_timeout={base_timeout_seconds}s"
        ),
        "blue",
    )
    progress_log(
        "model-request",
        (
            f"user={payload.get('user_id') or '-'} "
            f"model={payload.get('model') or config.get('model') or 'server-default'} "
            f"keep_alive={payload.get('keep_alive')} "
            f"num_ctx={payload.get('options', {}).get('num_ctx')}"
        ),
        "cyan",
    )
    progress_log("model-request", f"prompt preview: {preview_text(prompt)}", "dim")
    failure_count = 0
    while True:
        send_started = time.perf_counter()
        attempt_number = failure_count + 1
        try:
            mark_prompt_sent()
            progress_log(
                "model-request",
                (
                    f"{label or 'model'} sending prompt attempt={attempt_number} "
                    f"prompt_words={prompt_words} timeout={timeout_seconds}s timeout_scale={timeout_scale}x"
                ),
                "cyan",
            )
            data = request_json(generate_url, payload, timeout_seconds)
            send_elapsed = time.perf_counter() - send_started
            progress_log(
                "model-response",
                (
                    f"{label or 'model'} received response attempt={attempt_number} "
                    f"send_elapsed={send_elapsed:.1f}s total_elapsed={time.perf_counter() - started:.1f}s "
                    f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x"
                ),
                "green",
            )
            break
        except urllib.error.HTTPError as exc:
            send_elapsed = time.perf_counter() - send_started
            error = f"Model endpoint returned HTTP {exc.code}: {generate_url} | {exc.reason}"
            trace_path = save_llm_trace(
                url=generate_url,
                config=config,
                prompt=prompt,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                label=label,
                error=f"HTTP {exc.code}: {exc.reason}",
            )
            progress_log(
                "model-response",
                (
                    f"{label or 'model'} failed attempt={attempt_number} "
                    f"send_elapsed={send_elapsed:.1f}s total_elapsed={time.perf_counter() - started:.1f}s "
                    f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x error=HTTP {exc.code} {exc.reason}"
                ),
                "red",
            )
            if trace_path:
                progress_log("model-trace", f"saved failed request trace -> {trace_path}", "yellow")
            if exc.code == HTTPStatus.UNAUTHORIZED:
                raise ValueError("Model endpoint rejected authentication. Check User ID/Password.") from exc
        except urllib.error.URLError as exc:
            send_elapsed = time.perf_counter() - send_started
            error = f"Could not connect to model endpoint: {generate_url} | {exc}"
            trace_path = save_llm_trace(
                url=generate_url,
                config=config,
                prompt=prompt,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                label=label,
                error=f"URL error: {exc}",
            )
            progress_log(
                "model-response",
                (
                    f"{label or 'model'} failed attempt={attempt_number} "
                    f"send_elapsed={send_elapsed:.1f}s total_elapsed={time.perf_counter() - started:.1f}s "
                    f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x error={exc}"
                ),
                "red",
            )
            if trace_path:
                progress_log("model-trace", f"saved failed request trace -> {trace_path}", "yellow")
        except TimeoutError as exc:
            send_elapsed = time.perf_counter() - send_started
            error = str(exc)
            trace_path = save_llm_trace(
                url=generate_url,
                config=config,
                prompt=prompt,
                started_at=started_at,
                elapsed_seconds=time.perf_counter() - started,
                label=label,
                error=error,
            )
            progress_log(
                "model-response",
                (
                    f"{label or 'model'} timed out attempt={attempt_number} "
                    f"send_elapsed={send_elapsed:.1f}s total_elapsed={time.perf_counter() - started:.1f}s "
                    f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x error={error}"
                ),
                "red",
            )
            if trace_path:
                progress_log("model-trace", f"saved failed request trace -> {trace_path}", "yellow")

        failure_count += 1
        if not retryable_model_error(error):
            raise ValueError(error)
        progress_log(
            "model-retry",
            f"{label or 'model'} request failed without response ({failure_count}): {error}",
            "yellow",
        )
        try:
            wait_for_model_queue_slot(config, label, failure_count, error)
        except Exception as retry_exc:
            raise ValueError(f"{error} | retry_status_failed={retry_exc}") from retry_exc
        progress_log(
            "model-retry",
            f"{label or 'model'} resending prompt after queue check",
            "cyan",
        )
    text = extract_response_text(data).strip()
    progress_log(
        "model",
        (
            f"response{label_text} <- response_words={word_count(text)} "
            f"prompt_words={prompt_words} total_elapsed={time.perf_counter() - started:.1f}s "
            f"timeout={timeout_seconds}s timeout_scale={timeout_scale}x"
        ),
        "green",
        started,
    )
    progress_log("model-response", f"response preview: {preview_text(text, 1200)}", "dim")
    trace_path = save_llm_trace(
        url=generate_url,
        config=config,
        prompt=prompt,
        started_at=started_at,
        elapsed_seconds=time.perf_counter() - started,
        label=label,
        response=text,
        raw_response=data,
    )
    if trace_path:
        progress_log("model-trace", f"saved prompt/response trace -> {trace_path}", "cyan")
    return text


def fetch_remote_status(config: dict[str, Any]) -> dict[str, Any]:
    url = join_url(config["server_base_url"], config["status_path"])
    try:
        data = request_json(url, None, int(config["request_timeout_seconds"]))
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to model status endpoint: {url} | {exc}") from exc
    return {
        "server_base_url": config["server_base_url"],
        "status_url": url,
        "model": data.get("model", ""),
        "host": data.get("host", ""),
        "port": data.get("port", ""),
        "raw": data,
    }


def retryable_model_error(error: str) -> bool:
    lowered = (error or "").lower()
    return any(
        marker in lowered
        for marker in (
            "http 502",
            "bad gateway",
            "timed out",
            "timeout",
            "could not connect",
            "connection refused",
            "temporarily unavailable",
            "service unavailable",
            "http 503",
            "http 504",
        )
    )


def split_gpu_tokens(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if re.fullmatch(r"[0-9,\s]+", text):
        return [item for item in re.split(r"[,\s]+", text) if item]
    match = re.search(r"(?:cuda|gpu|device)[^0-9]*([0-9](?:\s*,\s*[0-9])*)", text, re.IGNORECASE)
    if match:
        return [item for item in re.split(r"\s*,\s*", match.group(1)) if item]
    return [text]


def model_server_retry_status(config: dict[str, Any]) -> dict[str, Any]:
    check_config = dict(config)
    check_config["request_timeout_seconds"] = int(config.get("model_retry_status_timeout_seconds") or 10)
    status = fetch_remote_status(check_config)
    raw = status.get("raw") if isinstance(status.get("raw"), dict) else {}

    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    targets = raw.get("targets") if isinstance(raw.get("targets"), list) else []
    active = 0
    pending = 0
    available_targets = 0
    idle_targets = 0
    gpu_tokens: set[str] = set()
    requested_target_id = str(config.get("target_id") or "").strip()

    for target in targets:
        if not isinstance(target, dict) or not target.get("enabled", True):
            continue
        if requested_target_id and str(target.get("id") or "") != requested_target_id:
            continue
        metric = metrics.get(str(target.get("id"))) if isinstance(metrics, dict) else {}
        if not isinstance(metric, dict):
            metric = {}
        if metric.get("status") in {"ok", "ready", None, ""}:
            available_targets += 1
        target_active = int(metric.get("active_requests") or 0)
        target_pending = int(metric.get("pending_queue") or 0)
        active += target_active
        pending += target_pending
        if target_active == 0 and target_pending == 0 and metric.get("status") in {"ok", "ready", None, ""}:
            idle_targets += 1
        for key in ("selected_gpu_device", "selected_gpu_label", "selected_gpu", "gpu_type"):
            for token in split_gpu_tokens(str(metric.get(key) or target.get(key) or "")):
                gpu_tokens.add(token)

    gpus = raw.get("gpus") if isinstance(raw.get("gpus"), list) else []
    for gpu in gpus:
        if isinstance(gpu, dict):
            token = str(gpu.get("id") or gpu.get("index") or gpu.get("uuid") or gpu.get("name") or "").strip()
            if token:
                gpu_tokens.add(token)

    queue = raw.get("prompt_queue") if isinstance(raw.get("prompt_queue"), dict) else {}
    pending += int(queue.get("pending_count") or 0)
    if not targets and pending == 0 and active == 0:
        idle_targets = 1

    service_status = str(raw.get("status") or status.get("model") or "ok")
    return {
        "live": True,
        "status": service_status,
        "model": status.get("model") or "",
        "gpu_count": len(gpu_tokens) if gpu_tokens else None,
        "available_targets": available_targets if targets else None,
        "idle_targets": idle_targets,
        "queue_empty": idle_targets > 0,
        "active_requests": active,
        "pending_prompts": pending,
        "status_url": status.get("status_url") or "",
    }


def retry_status_text(status: dict[str, Any]) -> str:
    gpu_count = status.get("gpu_count")
    gpu_text = str(gpu_count) if gpu_count is not None else "unknown"
    target_count = status.get("available_targets")
    target_text = str(target_count) if target_count is not None else "unknown"
    return (
        f"status={status.get('status') or 'ok'} "
        f"model={status.get('model') or '-'} "
        f"available_gpus={gpu_text} "
        f"available_targets={target_text} "
        f"idle_targets={status.get('idle_targets', 0)} "
        f"active={status.get('active_requests', 0)} "
        f"pending={status.get('pending_prompts', 0)}"
    )


def ask_continue_after_failures(chapter_title: str, failures: int) -> bool:
    try:
        answer = input(
            f"{chapter_title} has failed {failures} model request attempts. Continue retrying? [y/N]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        progress_log("retry", "no interactive answer available; stopping retries", "red")
        return False
    return answer in {"y", "yes", "c", "continue", "계속", "예", "네"}


def wait_for_model_queue_slot(config: dict[str, Any], label: str, failure_count: int, last_error: str) -> None:
    wait_seconds = int(config.get("model_retry_wait_seconds") or DEFAULT_CONFIG["model_retry_wait_seconds"])
    prompt_after = int(
        config.get("model_retry_prompt_after_failures")
        or DEFAULT_CONFIG["model_retry_prompt_after_failures"]
    )
    title = label or str(config.get("name") or "model")
    asked_at_failure = False

    while True:
        if failure_count > prompt_after and not asked_at_failure:
            asked_at_failure = True
            if not ask_continue_after_failures(title, failure_count):
                raise ValueError(f"{title} stopped by user after {failure_count} failed model requests: {last_error}")

        status = model_server_retry_status(config)
        if status.get("queue_empty"):
            progress_log(
                "model-retry",
                (
                    f"{title} model queue has an empty target; resending prompt now. "
                    f"{retry_status_text(status)}"
                ),
                "green",
            )
            return

        progress_log(
            "model-retry",
            (
                f"{title} all model queues are busy; waiting {wait_seconds}s before checking again. "
                f"{retry_status_text(status)}"
            ),
            "yellow",
        )
        time.sleep(wait_seconds)


def deferred_timeout_multiplier_for_attempt(config: dict[str, Any], attempt: int) -> int:
    max_multiplier = int(
        config.get("model_retry_max_timeout_multiplier")
        or DEFAULT_CONFIG["model_retry_max_timeout_multiplier"]
    )
    return max(1, min(max_multiplier, attempt + 1))


def wait_for_deferred_queue_slot(worker: dict[str, Any], config: dict[str, Any], chapter_title: str, attempt: int) -> int:
    wait_seconds = int(config.get("model_retry_wait_seconds") or DEFAULT_CONFIG["model_retry_wait_seconds"])
    while True:
        status = model_server_retry_status(worker)
        if status.get("queue_empty"):
            multiplier = deferred_timeout_multiplier_for_attempt(config, attempt)
            progress_log(
                "deferred",
                (
                    f"{chapter_title} model queue is idle enough for deferred prompt; "
                    f"timeout_scale={multiplier}x. {retry_status_text(status)}"
                ),
                "green",
            )
            return multiplier

        progress_log(
            "deferred",
            (
                f"{chapter_title} deferred prompt is waiting because all model queues are busy; "
                f"checking again in {wait_seconds}s. {retry_status_text(status)}"
            ),
            "yellow",
        )
        time.sleep(wait_seconds)


def explain_request_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == HTTPStatus.UNAUTHORIZED:
            return "HTTP 401 Unauthorized. User ID/Password is likely wrong."
        if exc.code == HTTPStatus.NOT_FOUND:
            return "HTTP 404 Not Found. Check generate_path/status_path in config."
        return f"HTTP {exc.code} {exc.reason}."
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        return f"Connection failed: {reason}. Check server_base_url and whether the LLM server is running."
    if isinstance(exc, TimeoutError):
        return str(exc)
    if isinstance(exc, ValueError):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def run_model_diagnostics(timeout_seconds: int) -> bool:
    config = runtime_config()
    targets = startup_model_status_targets(config)
    timeout = max(1, int(timeout_seconds))
    all_ok = True

    progress_log("test", f"Config: {CONFIG_PATH}", "cyan")
    progress_log("test", f"Testing {len(targets)} LLM endpoint(s), timeout={timeout}s", "cyan")

    for target in targets:
        test_config = dict(target)
        test_config["request_timeout_seconds"] = timeout
        name = str(test_config.get("name") or "primary")
        status_url = join_url(str(test_config.get("server_base_url", "")), str(test_config.get("status_path", "")))
        generate_url = join_url(str(test_config.get("server_base_url", "")), str(test_config.get("generate_path", "")))

        progress_log("test", f"[{name}] status GET {status_url}", "blue")
        try:
            status = fetch_remote_status(test_config)
            progress_log(
                "test",
                f"[{name}] status OK model={status.get('model') or test_config.get('model') or 'unknown'}",
                "green",
            )
        except Exception as exc:
            all_ok = False
            progress_log("test", f"[{name}] status FAILED: {explain_request_error(exc)}", "red")

        progress_log("test", f"[{name}] generate POST {generate_url}", "blue")
        try:
            prompt = "Reply with exactly: OK"
            payload = build_generate_payload(test_config, prompt)
            progress_log(
                "test",
                (
                    f"[{name}] payload user={payload.get('user_id') or '-'} "
                    f"model={payload.get('model') or test_config.get('model') or 'server-default'} "
                    f"num_ctx={payload.get('options', {}).get('num_ctx')}"
                ),
                "cyan",
            )
            data = request_json(generate_url, payload, timeout)
            text = extract_response_text(data).strip()
            if not text:
                raise ValueError(f"Generate response JSON did not contain text. Keys={list(data.keys())}")
            progress_log("test", f"[{name}] generate OK response preview: {preview_text(text, 300)}", "green")
        except Exception as exc:
            all_ok = False
            progress_log("test", f"[{name}] generate FAILED: {explain_request_error(exc)}", "red")

    if all_ok:
        progress_log("test", "LLM diagnostic passed.", "green")
    else:
        progress_log("test", "LLM diagnostic failed. Fix the errors above and run --test again.", "red")
    return all_ok


def startup_model_status_targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    targets = [{"name": "primary", **config}]
    targets.extend(config.get("agent_workers", []))

    unique_targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for target in targets:
        status_url = join_url(str(target.get("server_base_url", "")), str(target.get("status_path", "")))
        if not status_url or status_url in seen:
            continue
        seen.add(status_url)
        unique_targets.append(target)
    return unique_targets


def check_startup_model_status(timeout_seconds: int) -> bool:
    config = runtime_config()
    targets = startup_model_status_targets(config)
    timeout = max(1, int(timeout_seconds))
    progress_log("model-check", f"checking {len(targets)} LLM status endpoint(s), timeout={timeout}s", "cyan")

    ok_count = 0
    for target in targets:
        check_config = dict(target)
        check_config["request_timeout_seconds"] = timeout
        name = str(check_config.get("name") or "primary")
        try:
            status = fetch_remote_status(check_config)
        except Exception as exc:
            progress_log(
                "model-check",
                f"{name} unavailable: {check_config.get('server_base_url')} ({exc})",
                "red",
            )
            continue

        ok_count += 1
        model = status.get("model") or check_config.get("model") or "unknown"
        remote = ""
        if status.get("host") or status.get("port"):
            remote = f" remote={status.get('host', '')}:{status.get('port', '')}"
        progress_log(
            "model-check",
            f"{name} OK: {status['status_url']} model={model}{remote}",
            "green",
        )

    if ok_count == 0:
        progress_log(
            "model-check",
            f"LLM is not responding. Start the model server or update {CONFIG_PATH} before running agents.",
            "red",
        )
        return False
    if ok_count < len(targets):
        progress_log(
            "model-check",
            f"LLM check partially available: {ok_count}/{len(targets)} endpoint(s) responded.",
            "yellow",
        )
    return True


def create_http_server(host: str, port: int) -> tuple[ThreadingHTTPServer, str]:
    try:
        return ThreadingHTTPServer((host, port), WritingMachHandler), host
    except OSError as exc:
        if exc.errno != errno.EADDRNOTAVAIL:
            raise
        fallback_host = "0.0.0.0"
        progress_log(
            "service",
            f"cannot bind to {host}:{port}; retrying on {fallback_host}:{port}",
            "yellow",
        )
        return ThreadingHTTPServer((fallback_host, port), WritingMachHandler), fallback_host


def valid_web_auth(header: str | None) -> bool:
    if WEB_AUTH_PASSWORD == "":
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    user, separator, password = decoded.partition(":")
    if not separator:
        return False
    return hmac.compare_digest(user, WEB_AUTH_USER) and hmac.compare_digest(password, WEB_AUTH_PASSWORD)


def resolve_web_auth(user: str | None, password: str | None) -> tuple[str, str]:
    resolved_user = user
    resolved_password = password

    if resolved_user is None:
        resolved_user = input("Web login user: ").strip()
    if resolved_password is None:
        resolved_password = getpass.getpass("Web login password (empty disables web auth): ")

    if resolved_password and not resolved_user:
        raise ValueError("Web login user is required when web password is set.")
    return resolved_user or "", resolved_password or ""


def title_from_backbone(backbone: str) -> str:
    match = re.search(r"제목은\s*(.+)", backbone)
    if match:
        return match.group(1).strip()
    match = re.search(r"^#\s+(.+)$", backbone, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "untitled-book"


def book_brief(backbone: str) -> str:
    chapters = parse_chapters(backbone)
    chapter_lines = "\n".join(f"- {item['title']}" for item in chapters)
    return f"""제목: {title_from_backbone(backbone)}
챕터 구성:
{chapter_lines}"""


def chapter_source_section(backbone: str, chapter: dict[str, Any]) -> str:
    number = int(chapter["number"])
    lines = backbone.splitlines()
    section: list[str] = []
    in_section = False
    marker_pattern = re.compile(r"\s*-\s*(\d+)\s*챕터\s*$")

    for line in lines:
        marker = marker_pattern.match(line)
        if marker:
            marker_number = int(marker.group(1))
            if marker_number == number:
                in_section = True
                section.append(line)
                continue
            if in_section:
                break
        if in_section:
            section.append(line)

    text = "\n".join(section).strip()
    if text:
        return text

    bullets = "\n".join(f"- {item}" for item in chapter["bullets"])
    return f"{chapter['title']}\n{bullets}".strip()


def chapter_context(backbone: str, chapter: dict[str, Any], config: dict[str, Any]) -> str:
    return f"""책 전체 개요:
{book_brief(backbone)}

담당 챕터 상세 기획:
{chapter_source_section(backbone, chapter)}

공통 작성 지침:
- 한국어로 작성합니다.
- 목표 분량은 약 {config['target_words_per_chapter']} 단어입니다.
- 사실 설명, 시대적 맥락, 핵심 사례/기관/산업 항목, 해설을 균형 있게 넣습니다.
- 책 전체의 일부가 되도록 독립된 챕터 제목과 절 구성을 포함합니다.
- 메타 설명 없이 원고 또는 편집 산출물만 출력합니다.
"""


def outline_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any]) -> str:
    return f"""당신은 책 챕터의 구조를 설계하는 outline agent입니다.

{chapter_context(backbone, chapter, config)}

작업:
1. 챕터 도입부의 hook을 제안합니다.
2. 3~6개의 주요 절을 설계합니다.
3. 각 절의 핵심 논점, 사례, 연결 문장을 bullet로 정리합니다.
4. 전체 책의 다른 챕터와 연결될 전환 메모를 포함합니다.

출력 형식:
# {chapter['title']} Outline
## 도입
...
## 절 구성
...
## 전환 메모
...
"""


def writer_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any], chapter_outline: str) -> str:
    return f"""당신은 책의 한 챕터를 담당하는 writer agent입니다.

{chapter_context(backbone, chapter, config)}

outline agent 산출물:
{chapter_outline}

작업:
- outline의 구조를 따라 완성도 있는 챕터 초안을 작성합니다.
- bullet 위주가 아니라 출판 원고에 가까운 문단 중심 산문으로 작성합니다.
- 제목은 Markdown heading으로 시작합니다.
- 아직 reviewer와 finalizer가 보기 전의 초안이므로, 내용 누락 없이 충분히 씁니다.
"""


def reviewer_prompt(
    backbone: str,
    chapter: dict[str, Any],
    config: dict[str, Any],
    chapter_outline: str,
    chapter_draft: str,
) -> str:
    return f"""당신은 전문 편집자 reviewer agent입니다.

{chapter_context(backbone, chapter, config)}

outline:
{chapter_outline}

writer agent 초안:
{chapter_draft}

작업:
1. 명확성, 흐름, 완성도, 용어 일관성, 흥미도를 기준으로 초안을 개선합니다.
2. outline에서 빠진 내용을 보강합니다.
3. 사실관계가 어색하거나 과장된 부분은 보수적으로 정리합니다.

출력:
- 리뷰 코멘트가 아니라 개선이 반영된 챕터 전체 원고만 출력합니다.
"""


def finalizer_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any], chapter_review: str) -> str:
    return f"""당신은 최종 원고를 정리하는 finalizer agent입니다.

{chapter_context(backbone, chapter, config)}

reviewer agent 개선 원고:
{chapter_review}

작업:
- Markdown heading 계층을 정리합니다.
- 반복, TODO, 메타 코멘트, 불필요한 안내문을 제거합니다.
- 문단 사이 전환을 부드럽게 다듬습니다.
- 챕터 제목으로 시작하는 최종 원고만 출력합니다.
"""


def coordinator_prompt(backbone: str, chapter_drafts: list[dict[str, Any]], config: dict[str, Any]) -> str:
    draft_text = "\n\n".join(
        f"## {item['chapter']['title']} 최종안\n{item.get('final', item.get('draft', ''))}" for item in chapter_drafts
    )
    focus = "\n".join(f"- {item}" for item in config.get("global_review_focus", []))
    rewrite_policy = "필요한 챕터의 재작성 지시까지 작성합니다." if config.get("allow_global_rewrite") else "원고를 직접 재작성하지 말고 수정 지시만 작성합니다."
    return f"""당신은 전체 책을 조율하는 main writer agent입니다.

책 전체 기획:
{backbone}

리뷰 모드: {config.get('global_review_mode', 'strict')}
리뷰 초점:
{focus}

아래는 각 챕터 파이프라인의 최종 출력입니다.
{draft_text}

작업:
1. 전체 책의 논지, 시대 흐름, 용어, 반복/누락을 점검합니다.
2. 1챕터 초반부와 책의 도입부가 뒤 챕터의 방향과 어긋나는 부분을 찾아 수정 방향을 제시합니다.
3. 최종 원고에서 초반부가 어떤 관점을 깔아야 하는지 구체적인 편집 지시를 작성합니다.
4. {rewrite_policy}

출력 형식:
## 전체 편집 방향
...

## 챕터별 수정 지시
...

## 초반부 수정 지시
...
"""


def revise_opening_prompt(backbone: str, chapter_drafts: list[dict[str, Any]], coordinator_notes: str) -> str:
    first_chapter = chapter_drafts[0].get("final", chapter_drafts[0].get("draft", "")) if chapter_drafts else ""
    other_summaries = "\n\n".join(
        f"## {item['chapter']['title']}\n{item.get('final', item.get('draft', ''))[:2500]}" for item in chapter_drafts[1:]
    )
    return f"""당신은 최종 원고를 다듬는 lead writer입니다.

책 전체 기획:
{backbone}

main writer agent의 조율 메모:
{coordinator_notes}

1챕터 기존 초안:
{first_chapter}

뒤 챕터 참고 내용:
{other_summaries}

작업:
- 책의 도입부와 1챕터 초반부를 다시 작성합니다.
- 뒤 챕터에서 다루는 주제와 자연스럽게 이어지도록 관점, 문제의식, 시대 흐름을 조정합니다.
- 출력은 수정된 도입부와 1챕터 전체 원고로 작성합니다.
"""


def compile_book(title: str, revised_opening: str, chapter_drafts: list[dict[str, Any]], coordinator_notes: str) -> str:
    remaining = "\n\n".join(item.get("final", item.get("draft", "")) for item in chapter_drafts[1:])
    return f"""# {title}

> generated by writing_mach on {time.strftime('%Y-%m-%d %H:%M:%S')}

## Main Writer Notes

{coordinator_notes}

---

{revised_opening}

---

{remaining}
"""


def inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def markdown_table_to_html(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2:
        return ""
    headers = rows[0]
    body_rows = rows[2:] if len(rows) > 2 else []
    header_html = "".join(f"<th>{inline_markdown_to_html(cell)}</th>" for cell in headers)
    body_html = "\n".join(
        "<tr>" + "".join(f"<td>{inline_markdown_to_html(cell)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def markdown_to_html_document(markdown: str, title: str = "") -> str:
    body: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            body.append(f"<p>{inline_markdown_to_html(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            body.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    def flush_table() -> None:
        if table_lines:
            table_html = markdown_table_to_html(table_lines)
            if table_html:
                body.append(table_html)
            else:
                body.extend(f"<p>{inline_markdown_to_html(line)}</p>" for line in table_lines)
            table_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if table_lines and not (stripped.startswith("|") and stripped.endswith("|")):
            flush_table()
        if not stripped:
            flush_table()
            flush_list()
            flush_paragraph()
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(stripped)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_table()
            flush_list()
            flush_paragraph()
            level = min(6, len(heading.group(1)))
            body.append(f"<h{level}>{inline_markdown_to_html(heading.group(2))}</h{level}>")
            continue
        if stripped in {"---", "***", "___"}:
            flush_table()
            flush_list()
            flush_paragraph()
            body.append("<hr>")
            continue
        if stripped.startswith(">"):
            flush_table()
            flush_list()
            flush_paragraph()
            body.append(f"<blockquote>{inline_markdown_to_html(stripped.lstrip('> ').strip())}</blockquote>")
            continue
        list_match = re.match(r"^(?:[-*+]|\d+[.)])\s+(.+)$", stripped)
        if list_match:
            flush_table()
            flush_paragraph()
            list_items.append(inline_markdown_to_html(list_match.group(1)))
            continue
        flush_table()
        flush_list()
        paragraph.append(stripped)

    flush_table()
    flush_list()
    flush_paragraph()
    document_title = html.escape(title or "Writing Mach")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{document_title}</title>
  <style>
    @page {{ margin: 18mm 16mm; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans CJK KR", "Malgun Gothic", sans-serif;
      font-size: 11pt;
      line-height: 1.72;
      color: #202124;
    }}
    h1 {{ font-size: 24pt; margin: 0 0 18pt; page-break-after: avoid; }}
    h2 {{ font-size: 17pt; margin: 22pt 0 10pt; border-bottom: 1px solid #d7dce2; padding-bottom: 4pt; page-break-after: avoid; }}
    h3 {{ font-size: 14pt; margin: 18pt 0 8pt; page-break-after: avoid; }}
    h4, h5, h6 {{ font-size: 12pt; margin: 14pt 0 6pt; page-break-after: avoid; }}
    p {{ margin: 0 0 9pt; }}
    blockquote {{ margin: 0 0 14pt; padding: 8pt 12pt; border-left: 4pt solid #8aa0b8; background: #f3f6f8; color: #4b5563; }}
    ul {{ margin: 0 0 10pt 18pt; padding: 0; }}
    li {{ margin: 3pt 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12pt 0 16pt; font-size: 9.5pt; page-break-inside: avoid; }}
    th, td {{ border: 1px solid #c8d0d9; padding: 5pt 6pt; vertical-align: top; }}
    th {{ background: #eef2f6; font-weight: 700; }}
    hr {{ border: 0; border-top: 1px solid #d7dce2; margin: 18pt 0; }}
    code {{ font-family: Menlo, Consolas, monospace; font-size: 9.5pt; background: #f1f3f4; padding: 1pt 3pt; }}
  </style>
</head>
<body>
{chr(10).join(body)}
</body>
</html>
"""


def write_book_pdf(markdown_path: Path, pdf_path: Path) -> tuple[bool, str]:
    errors: list[str] = []
    if pdf_path.exists():
        pdf_path.unlink()
    html_path = markdown_path.with_suffix(".pdf_source.html")
    try:
        markdown = markdown_path.read_text(encoding="utf-8")
        html_path.write_text(
            markdown_to_html_document(markdown, title=title_from_backbone(markdown)),
            encoding="utf-8",
        )
    except OSError as exc:
        return False, f"failed to prepare HTML for PDF: {exc}"

    pandoc = shutil.which("pandoc")
    if pandoc:
        try:
            completed = subprocess.run(
                [pandoc, str(markdown_path), "-s", "-o", str(pdf_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                errors.append((completed.stderr or completed.stdout or "pandoc failed").strip())
            elif pdf_path.exists() and pdf_path.stat().st_size > 0:
                return True, str(pdf_path)
            else:
                errors.append("pandoc produced an empty PDF file.")
        except OSError as exc:
            errors.append(str(exc))

    try:
        from weasyprint import HTML  # type: ignore[import-not-found]

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return True, str(pdf_path)
        errors.append("weasyprint produced an empty PDF file.")
    except ImportError:
        errors.append("weasyprint is not installed.")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"weasyprint failed: {exc}")

    cupsfilter = shutil.which("cupsfilter")
    if cupsfilter:
        try:
            completed = subprocess.run(
                [cupsfilter, "-m", "application/pdf", str(html_path)],
                check=False,
                capture_output=True,
            )
            if completed.returncode != 0:
                error = completed.stderr.decode("utf-8", errors="replace").strip()
                errors.append(error or "cupsfilter failed")
            else:
                pdf_path.write_bytes(completed.stdout)
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    return True, str(pdf_path)
                errors.append("cupsfilter produced an empty PDF file.")
        except OSError as exc:
            errors.append(str(exc))
    elif not pandoc:
        errors.append("cupsfilter not found.")

    if not errors:
        errors.append("PDF converter produced an empty file.")
    errors.append(f"HTML preview was saved to {html_path}. Install pandoc or weasyprint for rendered PDF output.")
    return False, " | ".join(error for error in errors if error)


def worker_slots(config: dict[str, Any]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for worker in config["agent_workers"]:
        slots.extend([worker] * max(1, int(worker.get("max_parallel") or 1)))
    return slots or config["agent_workers"]


def run_chapter_pipeline(
    config: dict[str, Any],
    worker: dict[str, Any],
    backbone: str,
    chapter: dict[str, Any],
    index: int,
    total: int,
    resume_outputs: dict[str, str] | None = None,
    resume_agent: str = "",
    timeout_multiplier: int = 1,
) -> dict[str, Any]:
    started = time.perf_counter()
    worker_name = worker.get("name", "worker")
    pipeline_agents = config.get("pipeline_agents") or DEFAULT_CONFIG["pipeline_agents"]
    outputs: dict[str, str] = dict(resume_outputs or {})
    start_index = first_runnable_agent_index(pipeline_agents, outputs, resume_agent)
    skipped_agents = pipeline_agents[:start_index]
    progress_log(
        "chapter",
        f"{index}/{total} {chapter['title']} pipeline started on {worker_name} ({','.join(pipeline_agents)})",
        "yellow",
    )
    if skipped_agents:
        progress_log(
            "chapter",
            f"{chapter['title']} resuming at {pipeline_agents[start_index]}; skipping completed stages: {','.join(skipped_agents)}",
            "cyan",
            started,
        )
    if timeout_multiplier > 1:
        progress_log(
            "chapter",
            f"{chapter['title']} using deferred timeout_scale={timeout_multiplier}x for resumed prompt(s)",
            "yellow",
            started,
        )

    current_text = (
        outputs.get("final")
        or outputs.get("review")
        or outputs.get("draft")
        or outputs.get("outline")
        or ""
    )
    for agent in pipeline_agents[start_index:]:
        missing = [key for key in AGENT_REQUIRED_KEYS.get(agent, []) if not outputs.get(key)]
        if missing:
            raise ChapterPipelineError(
                f"{chapter['title']} cannot run {agent}; missing prerequisite output(s): {', '.join(missing)}",
                failed_agent=agent,
                partial_result={
                    "chapter": chapter,
                    "worker": worker_name,
                    "elapsed_seconds": time.perf_counter() - started,
                    "failed_agent": agent,
                    "outline": outputs.get("outline", ""),
                    "draft": outputs.get("draft", ""),
                    "review": outputs.get("review", ""),
                    "final": outputs.get("final", ""),
                },
            )
        agent_started = time.perf_counter()
        progress_log("agent", f"{chapter['title']}:{agent} -> {worker_name}", "blue")
        label = f"{chapter['title']}:{agent}"
        try:
            if agent == "outline":
                current_text = call_model(
                    worker,
                    outline_prompt(backbone, chapter, config),
                    label=label,
                    timeout_multiplier=timeout_multiplier,
                )
                outputs["outline"] = current_text
            elif agent == "writer":
                current_text = call_model(
                    worker,
                    writer_prompt(backbone, chapter, config, outputs.get("outline", "")),
                    label=label,
                    timeout_multiplier=timeout_multiplier,
                )
                outputs["draft"] = current_text
            elif agent == "reviewer":
                current_text = call_model(
                    worker,
                    reviewer_prompt(
                        backbone,
                        chapter,
                        config,
                        outputs.get("outline", ""),
                        outputs.get("draft", current_text),
                    ),
                    label=label,
                    timeout_multiplier=timeout_multiplier,
                )
                outputs["review"] = current_text
            elif agent == "finalizer":
                current_text = call_model(
                    worker,
                    finalizer_prompt(backbone, chapter, config, outputs.get("review", current_text)),
                    label=label,
                    timeout_multiplier=timeout_multiplier,
                )
                outputs["final"] = current_text
        except Exception as exc:
            checkpoint_update_chapter(
                chapter,
                index=index,
                worker=worker_name,
                status="failed",
                outputs=outputs,
                failed_agent=agent,
            )
            raise ChapterPipelineError(
                f"{chapter['title']}:{agent} failed: {exc}",
                failed_agent=agent,
                partial_result={
                    "chapter": chapter,
                    "worker": worker_name,
                    "elapsed_seconds": time.perf_counter() - started,
                    "failed_agent": agent,
                    "outline": outputs.get("outline", ""),
                    "draft": outputs.get("draft", ""),
                    "review": outputs.get("review", ""),
                    "final": outputs.get("final", ""),
                },
            ) from exc
        progress_log(
            "agent",
            f"{chapter['title']}:{agent} done ({word_count(current_text)} words)",
            "green",
            agent_started,
        )
        checkpoint_update_chapter(
            chapter,
            index=index,
            worker=worker_name,
            status="running",
            outputs=outputs,
            completed_agent=agent,
        )

    final_text = outputs.get("final") or outputs.get("review") or outputs.get("draft") or outputs.get("outline") or current_text
    checkpoint_update_chapter(
        chapter,
        index=index,
        worker=worker_name,
        status="completed",
        outputs={**outputs, "final": final_text},
    )
    progress_log(
        "chapter",
        f"{index}/{total} {chapter['title']} pipeline done on {worker_name} ({word_count(final_text)} words)",
        "green",
        started,
    )
    return {
        "chapter": chapter,
        "worker": worker_name,
        "elapsed_seconds": time.perf_counter() - started,
        "outline": outputs.get("outline", ""),
        "draft": outputs.get("draft", ""),
        "review": outputs.get("review", ""),
        "final": final_text,
    }


def run_chapter_with_retry(
    config: dict[str, Any],
    worker: dict[str, Any],
    backbone: str,
    chapter: dict[str, Any],
    index: int,
    total: int,
    phase: str = "normal",
    total_attempt_offset: int = 0,
    continuous_on_live_model: bool = False,
    resume_outputs: dict[str, str] | None = None,
    resume_agent: str = "",
) -> dict[str, Any]:
    last_error = ""
    partial_result: dict[str, Any] = {}
    current_resume_outputs: dict[str, str] = dict(resume_outputs or {})
    current_resume_agent = resume_agent
    attempt = 1
    retry_limit = int(config["chapter_retry"])
    while True:
        total_attempt = total_attempt_offset + attempt
        limit_text = str(retry_limit) if attempt <= retry_limit else "continuous"
        try:
            if attempt > 1 or phase != "normal":
                progress_log(
                    "retry",
                    (
                        f"{chapter['title']} {phase} attempt {attempt}/{limit_text} "
                        f"(total attempt {total_attempt})"
                    ),
                    "yellow",
                )
            timeout_multiplier = 1
            if phase == "deferred":
                timeout_multiplier = wait_for_deferred_queue_slot(worker, config, chapter["title"], attempt)
            return run_chapter_pipeline(
                config,
                worker,
                backbone,
                chapter,
                index,
                total,
                resume_outputs=current_resume_outputs,
                resume_agent=current_resume_agent,
                timeout_multiplier=timeout_multiplier,
            )
        except ChapterPipelineError as exc:
            last_error = str(exc)
            partial_result = exc.partial_result
            current_resume_agent = exc.failed_agent
            current_resume_outputs = {
                "outline": str(partial_result.get("outline") or ""),
                "draft": str(partial_result.get("draft") or ""),
                "review": str(partial_result.get("review") or ""),
                "final": str(partial_result.get("final") or ""),
            }
            progress_log(
                "retry",
                (
                    f"{chapter['title']} {phase} failed attempt {attempt}/{limit_text} "
                    f"(total attempt {total_attempt}, failed_agent={current_resume_agent or '-'}): {last_error}"
                ),
                "red",
            )
        except Exception as exc:
            last_error = str(exc)
            progress_log(
                "retry",
                (
                    f"{chapter['title']} {phase} failed attempt {attempt}/{limit_text} "
                    f"(total attempt {total_attempt}): {last_error}"
                ),
                "red",
            )

        if attempt < retry_limit:
            attempt += 1
            continue

        if not continuous_on_live_model or not retryable_model_error(last_error):
            raise ChapterPipelineError(
                f"{chapter['title']} failed after {attempt} {phase} attempts: {last_error}",
                failed_agent=current_resume_agent,
                partial_result=partial_result,
            )

        try:
            status = model_server_retry_status(worker)
        except Exception as status_exc:
            raise ChapterPipelineError(
                f"{chapter['title']} failed after {attempt} {phase} attempts and model status is unavailable: "
                f"{status_exc} | last_error={last_error}",
                failed_agent=current_resume_agent,
                partial_result=partial_result,
            ) from status_exc

        wait_seconds = int(config.get("model_retry_wait_seconds") or DEFAULT_CONFIG["model_retry_wait_seconds"])
        prompt_after = int(
            config.get("model_retry_prompt_after_failures")
            or DEFAULT_CONFIG["model_retry_prompt_after_failures"]
        )
        if total_attempt > prompt_after and not ask_continue_after_failures(chapter["title"], total_attempt):
            raise ChapterPipelineError(
                f"{chapter['title']} stopped by user after {total_attempt} failed attempts: {last_error}",
                failed_agent=current_resume_agent,
                partial_result=partial_result,
            )

        progress_log(
            "warning",
            (
                f"{chapter['title']} model server is still responding; waiting {wait_seconds}s before retry. "
                f"{retry_status_text(status)}"
            ),
            "yellow",
        )
        time.sleep(wait_seconds)
        attempt += 1


def chapter_queue_key(chapter: dict[str, Any]) -> str:
    return str(chapter["number"])


def make_chapter_queue_state(
    chapter: dict[str, Any],
    index: int,
    worker: dict[str, Any] | None = None,
    status: str = "pending",
    detail: str = "",
) -> dict[str, Any]:
    return {
        "index": index,
        "number": chapter["number"],
        "title": chapter["title"],
        "worker": (worker or {}).get("name", ""),
        "status": status,
        "detail": detail,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def update_chapter_queue_state(
    states: dict[str, dict[str, Any]],
    chapter: dict[str, Any],
    *,
    index: int,
    worker: dict[str, Any] | None = None,
    status: str,
    detail: str = "",
) -> None:
    key = chapter_queue_key(chapter)
    state = states.get(key) or make_chapter_queue_state(chapter, index, worker)
    state["index"] = index
    state["number"] = chapter["number"]
    state["title"] = chapter["title"]
    if worker is not None:
        state["worker"] = worker.get("name", "")
    state["status"] = status
    state["detail"] = detail
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    states[key] = state


def sorted_chapter_queue_states(states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(item) for item in states.values()), key=lambda item: int(item.get("index") or 0))


def chapter_queue_counts(states: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for state in states.values():
        status = str(state.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def format_chapter_queue_counts(counts: dict[str, int]) -> str:
    order = ["pending", "queued", "running", "finishing", "completed", "deferred", "skipped", "failed"]
    parts = [f"{key}={counts[key]}" for key in order if counts.get(key)]
    for key in sorted(counts):
        if key not in order:
            parts.append(f"{key}={counts[key]}")
    return " ".join(parts) if parts else "empty"


def format_chapter_queue_lines(states: dict[str, dict[str, Any]]) -> str:
    parts = []
    for state in sorted_chapter_queue_states(states):
        worker = state.get("worker") or "-"
        detail = f" {state.get('detail')}" if state.get("detail") else ""
        parts.append(f"{state.get('title')}={state.get('status')}@{worker}{detail}")
    return " | ".join(parts) if parts else "no chapters"


def log_chapter_queue_snapshot(
    states: dict[str, dict[str, Any]],
    history: list[dict[str, Any]],
    *,
    reason: str,
    started: float,
) -> None:
    counts = chapter_queue_counts(states)
    snapshot = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason,
        "counts": counts,
        "chapters": sorted_chapter_queue_states(states),
    }
    history.append(snapshot)
    del history[:-300]
    checkpoint_set_field("chapter_queue", snapshot["chapters"])
    checkpoint_set_field("chapter_queue_history", history)
    progress_log(
        "chapter-queue",
        f"{reason}: {format_chapter_queue_counts(counts)} | {format_chapter_queue_lines(states)}",
        "cyan",
        started,
    )


def run_book_agents(config: dict[str, Any], backbone: str | None = None) -> dict[str, Any]:
    ensure_dirs()
    backbone_text = (backbone or read_story_backbone()).strip()
    chapters = parse_chapters(backbone_text)
    config = apply_backbone_runtime_options(config, backbone_text, len(chapters))
    started = time.perf_counter()
    llm_trace_dir = init_llm_trace_dir()
    checkpoint_path, checkpoint_state = init_checkpoint(backbone_text, config, chapters)
    checkpoint_set_field("llm_trace_dir", str(llm_trace_dir))
    progress_log("start", f"book agent run started: {len(chapters)} chapters", "bold", started)
    progress_log("backbone", f"title='{title_from_backbone(backbone_text)}'", "cyan", started)
    progress_log("model-trace", f"saving full prompts/responses -> {llm_trace_dir}", "cyan", started)
    progress_log("checkpoint", f"saving/resuming checkpoint -> {checkpoint_path}", "cyan", started)
    checkpoint_event("start", f"book run started with {len(chapters)} chapters")
    if config.get("_backbone_parallel_enabled"):
        for alert in config.get("_backbone_parallel_alerts", []):
            progress_log("parallel-alert", alert, "magenta", started)
        progress_log(
            "parallel-alert",
            "story_backbone.md requested parallel chapter execution",
            "magenta",
            started,
        )

    slots = worker_slots(config)
    max_workers = min(len(chapters), int(config["chapter_parallelism"]), len(slots))
    progress_log(
        "dispatch",
        f"chapter parallelism={max_workers}, worker slots={len(slots)}, pipeline={','.join(config['pipeline_agents'])}",
        "cyan",
        started,
    )

    chapter_drafts: list[dict[str, Any]] = []
    deferred_retries: list[dict[str, Any]] = []
    chapter_queue_states: dict[str, dict[str, Any]] = {
        chapter_queue_key(chapter): make_chapter_queue_state(
            chapter,
            index,
            slots[(index - 1) % len(slots)] if slots else None,
            "pending",
        )
        for index, chapter in enumerate(chapters, start=1)
    }
    chapter_queue_history: list[dict[str, Any]] = []
    log_chapter_queue_snapshot(chapter_queue_states, chapter_queue_history, reason="initialized", started=started)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for index, chapter in enumerate(chapters, start=1):
            worker = slots[(index - 1) % len(slots)]
            saved = checkpoint_chapter_entry(chapter)
            saved_outputs = {
                "outline": str(saved.get("outline") or ""),
                "draft": str(saved.get("draft") or ""),
                "review": str(saved.get("review") or ""),
                "final": str(saved.get("final") or ""),
            }
            if saved.get("status") == "completed" and saved_outputs["final"]:
                update_chapter_queue_state(
                    chapter_queue_states,
                    chapter,
                    index=index,
                    worker=worker,
                    status="skipped",
                    detail="completed checkpoint",
                )
                progress_log(
                    "checkpoint",
                    f"{chapter['title']} already completed in checkpoint; skipping chapter pipeline",
                    "green",
                    started,
                )
                chapter_drafts.append(
                    {
                        "chapter": chapter,
                        "worker": saved.get("worker") or worker.get("name", "worker"),
                        "elapsed_seconds": 0.0,
                        "outline": saved_outputs["outline"],
                        "draft": saved_outputs["draft"],
                        "review": saved_outputs["review"],
                        "final": saved_outputs["final"],
                        "resumed_from_checkpoint": True,
                    }
                )
                continue
            resume_agent = str(saved.get("failed_agent") or "")
            if any(saved_outputs.values()):
                update_chapter_queue_state(
                    chapter_queue_states,
                    chapter,
                    index=index,
                    worker=worker,
                    status="queued",
                    detail=f"resume={resume_agent or 'auto'}",
                )
                progress_log(
                    "checkpoint",
                    (
                        f"{chapter['title']} resuming from checkpoint "
                        f"(failed_agent={resume_agent or 'auto'})"
                    ),
                    "yellow",
                    started,
                )
            else:
                update_chapter_queue_state(
                    chapter_queue_states,
                    chapter,
                    index=index,
                    worker=worker,
                    status="queued",
                    detail="waiting for worker",
                )
            future = executor.submit(
                run_chapter_with_retry,
                config,
                worker,
                backbone_text,
                chapter,
                index,
                len(chapters),
                "normal",
                0,
                False,
                saved_outputs,
                resume_agent,
            )
            futures[future] = {
                "chapter": chapter,
                "index": index,
                "worker": worker,
            }

        log_chapter_queue_snapshot(chapter_queue_states, chapter_queue_history, reason="submitted", started=started)
        pending_futures = set(futures)
        total_futures = len(futures)
        for future in pending_futures:
            item = futures[future]
            if future.done():
                future_status = "finishing"
                future_detail = "awaiting result collection"
            elif future.running():
                future_status = "running"
                future_detail = "worker active"
            else:
                future_status = "queued"
                future_detail = "waiting for worker"
            update_chapter_queue_state(
                chapter_queue_states,
                item["chapter"],
                index=int(item["index"]),
                worker=item["worker"],
                status=future_status,
                detail=future_detail,
            )
        progress_log(
            "parallel",
            f"running {sum(1 for future in pending_futures if future.running())}/{max_workers} chapter worker(s)",
            "cyan",
            started,
        )
        log_chapter_queue_snapshot(chapter_queue_states, chapter_queue_history, reason="parallel tick", started=started)
        while pending_futures:
            done, pending_futures = wait(pending_futures, timeout=30, return_when=FIRST_COMPLETED)
            for future in pending_futures:
                item = futures[future]
                update_chapter_queue_state(
                    chapter_queue_states,
                    item["chapter"],
                    index=int(item["index"]),
                    worker=item["worker"],
                    status="running" if future.running() else "queued",
                    detail="worker active" if future.running() else "waiting for worker",
                )
            for future in done:
                item = futures[future]
                update_chapter_queue_state(
                    chapter_queue_states,
                    item["chapter"],
                    index=int(item["index"]),
                    worker=item["worker"],
                    status="finishing",
                    detail="awaiting result collection",
                )
            running_count = sum(1 for future in pending_futures if future.running())
            completed_total = total_futures - len(pending_futures)
            progress_log(
                "parallel",
                (
                    f"running {running_count}/{max_workers} chapter worker(s), "
                    f"pending futures={len(pending_futures)}, completed this tick={len(done)}, "
                    f"completed total={completed_total}/{total_futures}"
                ),
                "cyan",
                started,
            )
            log_chapter_queue_snapshot(chapter_queue_states, chapter_queue_history, reason="parallel tick", started=started)
            if not done:
                continue
            for future in done:
                item = futures[future]
                chapter = item["chapter"]
                try:
                    chapter_drafts.append(future.result())
                    update_chapter_queue_state(
                        chapter_queue_states,
                        chapter,
                        index=int(item["index"]),
                        worker=item["worker"],
                        status="completed",
                        detail="chapter pipeline done",
                    )
                    log_chapter_queue_snapshot(
                        chapter_queue_states,
                        chapter_queue_history,
                        reason=f"{chapter['title']} completed",
                        started=started,
                    )
                except ChapterPipelineError as exc:
                    error = str(exc)
                    deferred_retries.append(
                        {
                            **item,
                            "error": error,
                            "failed_agent": exc.failed_agent,
                            "partial_result": exc.partial_result,
                        }
                    )
                    update_chapter_queue_state(
                        chapter_queue_states,
                        chapter,
                        index=int(item["index"]),
                        worker=item["worker"],
                        status="deferred",
                        detail=f"failed_agent={exc.failed_agent or 'unknown'}",
                    )
                    log_chapter_queue_snapshot(
                        chapter_queue_states,
                        chapter_queue_history,
                        reason=f"{chapter['title']} deferred",
                        started=started,
                    )
                    progress_log(
                        "warning",
                        (
                            f"{chapter['title']} failed after normal retries at {exc.failed_agent or 'unknown'}; "
                            "will resume from the appropriate stage after current chapter batch completes. "
                            f"error={error}"
                        ),
                        "yellow",
                        started,
                    )
                except Exception as exc:
                    error = str(exc)
                    deferred_retries.append({**item, "error": error})
                    update_chapter_queue_state(
                        chapter_queue_states,
                        chapter,
                        index=int(item["index"]),
                        worker=item["worker"],
                        status="deferred",
                        detail="unexpected failure",
                    )
                    log_chapter_queue_snapshot(
                        chapter_queue_states,
                        chapter_queue_history,
                        reason=f"{chapter['title']} deferred",
                        started=started,
                    )
                    progress_log(
                        "warning",
                        (
                            f"{chapter['title']} failed after normal retries while other chapters may still be running; "
                            "will retry after current chapter batch completes. "
                            f"error={error}"
                        ),
                        "yellow",
                        started,
                    )

    if deferred_retries:
        progress_log(
            "warning",
            f"{len(deferred_retries)} chapter(s) queued for deferred retry after parallel batch completion",
            "yellow",
            started,
        )
        for item in deferred_retries:
            chapter = item["chapter"]
            index = int(item["index"])
            worker = item["worker"]
            partial_result = item.get("partial_result") if isinstance(item.get("partial_result"), dict) else {}
            resume_outputs = {
                "outline": str(partial_result.get("outline") or ""),
                "draft": str(partial_result.get("draft") or ""),
                "review": str(partial_result.get("review") or ""),
                "final": str(partial_result.get("final") or ""),
            }
            resume_agent = str(item.get("failed_agent") or partial_result.get("failed_agent") or "")
            update_chapter_queue_state(
                chapter_queue_states,
                chapter,
                index=index,
                worker=worker,
                status="running",
                detail=f"deferred retry resume={resume_agent or 'auto'}",
            )
            log_chapter_queue_snapshot(
                chapter_queue_states,
                chapter_queue_history,
                reason=f"{chapter['title']} deferred retry started",
                started=started,
            )
            progress_log(
                "retry",
                (
                    f"{chapter['title']} deferred retry started after other chapters completed "
                    f"(resume_agent={resume_agent or 'auto'})"
                ),
                "yellow",
                started,
            )
            try:
                result = run_chapter_with_retry(
                    config,
                    worker,
                    backbone_text,
                    chapter,
                    index,
                    len(chapters),
                    "deferred",
                    int(config["chapter_retry"]),
                    True,
                    resume_outputs,
                    resume_agent,
                )
                result["deferred_retry"] = {
                    "used": True,
                    "initial_error": item["error"],
                    "resume_agent": resume_agent,
                }
                chapter_drafts.append(result)
                update_chapter_queue_state(
                    chapter_queue_states,
                    chapter,
                    index=index,
                    worker=worker,
                    status="completed",
                    detail="deferred retry succeeded",
                )
                log_chapter_queue_snapshot(
                    chapter_queue_states,
                    chapter_queue_history,
                    reason=f"{chapter['title']} deferred retry completed",
                    started=started,
                )
                progress_log(
                    "retry",
                    f"{chapter['title']} deferred retry succeeded",
                    "green",
                    started,
                )
            except Exception as exc:
                update_chapter_queue_state(
                    chapter_queue_states,
                    chapter,
                    index=index,
                    worker=worker,
                    status="failed",
                    detail="deferred retry failed",
                )
                log_chapter_queue_snapshot(
                    chapter_queue_states,
                    chapter_queue_history,
                    reason=f"{chapter['title']} failed",
                    started=started,
                )
                checkpoint_mark_status("failed")
                progress_log(
                    "warning",
                    f"{chapter['title']} deferred retry failed: {exc}",
                    "red",
                    started,
                )
                raise

    chapter_drafts.sort(key=lambda item: int(item["chapter"]["number"]))

    if config.get("global_review_enabled"):
        if checkpoint_state.get("coordinator_notes"):
            coordinator_notes = str(checkpoint_state.get("coordinator_notes") or "")
            progress_log("checkpoint", "main-writer notes restored from checkpoint", "green", started)
        else:
            coordinator_started = time.perf_counter()
            progress_log("main-writer", "reviewing finalized chapter outputs and preparing direction notes", "magenta", started)
            try:
                coordinator_notes = call_model(
                    config,
                    coordinator_prompt(backbone_text, chapter_drafts, config),
                    label="main-writer:coordinator",
                )
                checkpoint_set_field("coordinator_notes", coordinator_notes)
                checkpoint_event("main-writer", "coordinator notes completed")
            except Exception:
                checkpoint_mark_status("failed")
                raise
            progress_log(
                "main-writer",
                f"direction notes done ({word_count(coordinator_notes)} words)",
                "green",
                coordinator_started,
            )
    else:
        coordinator_notes = "Global review disabled by config."
        checkpoint_set_field("coordinator_notes", coordinator_notes)

    revise_started = time.perf_counter()
    if checkpoint_state.get("revised_opening"):
        revised_opening = str(checkpoint_state.get("revised_opening") or "")
        progress_log("checkpoint", "lead-writer revised opening restored from checkpoint", "green", started)
    else:
        progress_log("lead-writer", "rewriting opening and early chapter from chapter-agent outputs", "cyan", started)
        try:
            revised_opening = call_model(
                config,
                revise_opening_prompt(backbone_text, chapter_drafts, coordinator_notes),
                label="lead-writer:revise-opening",
            )
            checkpoint_set_field("revised_opening", revised_opening)
            checkpoint_event("lead-writer", "revised opening completed")
        except Exception:
            checkpoint_mark_status("failed")
            raise
        progress_log("lead-writer", f"opening revision done ({word_count(revised_opening)} words)", "green", revise_started)

    title = title_from_backbone(backbone_text)
    progress_log("compile", "compiling final manuscript", "blue", started)
    book = compile_book(title, revised_opening, chapter_drafts, coordinator_notes)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    elapsed_minutes = max(1, int(round((time.perf_counter() - started) / 60.0)))
    elapsed_suffix = f"{elapsed_minutes}min"
    output_path = OUTPUT_DIR / f"book_{timestamp}_{elapsed_suffix}.md"
    pdf_path = OUTPUT_DIR / f"book_{timestamp}_{elapsed_suffix}.pdf"
    log_path = OUTPUT_DIR / f"run_{timestamp}_{elapsed_suffix}.json"
    checkpoint_set_field("output_path", str(output_path))
    checkpoint_set_field("pdf_path", str(pdf_path))
    checkpoint_set_field("log_path", str(log_path))
    progress_log("save", f"writing book markdown -> {output_path}", "blue", started)
    output_path.write_text(book + "\n", encoding="utf-8")
    progress_log("save", f"writing book PDF -> {pdf_path}", "blue", started)
    pdf_ok, pdf_message = write_book_pdf(output_path, pdf_path)
    if pdf_ok:
        progress_log("save", f"book PDF written -> {pdf_path}", "green", started)
    else:
        progress_log("save", f"book PDF skipped: {pdf_message}", "yellow", started)
    progress_log("save", f"writing run log -> {log_path}", "blue", started)
    log_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "config": public_config(config),
                "backbone_parallel_enabled": bool(config.get("_backbone_parallel_enabled")),
                "backbone_parallel_alerts": config.get("_backbone_parallel_alerts", []),
                "deferred_retries": [
                    {
                        "chapter": item["chapter"],
                        "index": item["index"],
                        "worker": public_config(item["worker"]),
                        "initial_error": item["error"],
                        "failed_agent": item.get("failed_agent", ""),
                        "partial_outputs": {
                            "outline": bool((item.get("partial_result") or {}).get("outline")),
                            "draft": bool((item.get("partial_result") or {}).get("draft")),
                            "review": bool((item.get("partial_result") or {}).get("review")),
                            "final": bool((item.get("partial_result") or {}).get("final")),
                        },
                    }
                    for item in deferred_retries
                ],
                "backbone": backbone_text,
                "chapters": chapter_drafts,
                "chapter_queue": sorted_chapter_queue_states(chapter_queue_states),
                "chapter_queue_history": chapter_queue_history,
                "coordinator_notes": coordinator_notes,
                "revised_opening": revised_opening,
                "output_path": str(output_path),
                "pdf_path": str(pdf_path) if pdf_ok else "",
                "pdf_error": "" if pdf_ok else pdf_message,
                "service_log_path": str(SERVICE_LOG_PATH) if SERVICE_LOG_PATH else "",
                "llm_trace_dir": str(llm_trace_dir),
                "checkpoint_path": str(checkpoint_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    progress_log("done", f"agent run finished ({word_count(book)} words total)", "green", started)
    checkpoint_mark_status("completed")
    return {
        "ok": True,
        "elapsed_seconds": time.perf_counter() - started,
        "title": title,
        "chapter_count": len(chapters),
        "backbone_parallel_enabled": bool(config.get("_backbone_parallel_enabled")),
        "backbone_parallel_alerts": config.get("_backbone_parallel_alerts", []),
        "deferred_retries": [
            {
                "chapter": item["chapter"],
                "index": item["index"],
                "worker": public_config(item["worker"]),
                "initial_error": item["error"],
                "failed_agent": item.get("failed_agent", ""),
                "partial_outputs": {
                    "outline": bool((item.get("partial_result") or {}).get("outline")),
                    "draft": bool((item.get("partial_result") or {}).get("draft")),
                    "review": bool((item.get("partial_result") or {}).get("review")),
                    "final": bool((item.get("partial_result") or {}).get("final")),
                },
            }
            for item in deferred_retries
        ],
        "chapters": chapter_drafts,
        "chapter_queue": sorted_chapter_queue_states(chapter_queue_states),
        "chapter_queue_history": chapter_queue_history,
        "coordinator_notes": coordinator_notes,
        "revised_opening": revised_opening,
        "book": book,
        "output_path": str(output_path),
        "pdf_path": str(pdf_path) if pdf_ok else "",
        "pdf_error": "" if pdf_ok else pdf_message,
        "service_log_path": str(SERVICE_LOG_PATH) if SERVICE_LOG_PATH else "",
        "llm_trace_dir": str(llm_trace_dir),
        "checkpoint_path": str(checkpoint_path),
        "log_path": str(log_path),
    }


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


class WritingMachHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def require_auth(self) -> bool:
        if valid_web_auth(self.headers.get("Authorization")):
            return True
        body = json.dumps({"error": "authentication required"}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Writing Mach"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.require_auth():
            return
        if self.path in {"/", "/index.html"}:
            self.serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/styles.css":
            self.serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/app.js":
            self.serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/state":
            self.send_json({"config": read_config(), "backbone": read_story_backbone()})
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.require_auth():
            return
        try:
            incoming = parse_json_body(self)
            request_path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            progress_log("api", f"POST {request_path}", "cyan")
            if request_path == "/api/config":
                self.send_json({"config": write_config(incoming.get("config") or {})})
                return
            if request_path == "/api/test-connection":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": fetch_remote_status(config)})
                return
            if request_path == "/api/write-book":
                config = runtime_config(incoming.get("config"))
                self.send_json({"result": run_book_agents(config, str(incoming.get("backbone") or ""))})
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            progress_log("api-error", f"{self.path}: {exc}", "red")
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (json.JSONDecodeError, OSError, TimeoutError, urllib.error.URLError) as exc:
            progress_log("api-error", f"{self.path}: {exc}", "red")
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def start_run_on_start(exit_after_run: bool, httpd: ThreadingHTTPServer) -> None:
    def auto_run() -> None:
        try:
            progress_log("auto-run", "starting book generation from CLI --run-on-start", "magenta")
            result = run_book_agents(runtime_config())
            progress_log(
                "auto-run",
                f"finished: output={result.get('output_path')} pdf={result.get('pdf_path') or '-'}",
                "green",
            )
        except Exception as exc:  # noqa: BLE001
            progress_log("auto-run", f"failed: {exc}", "red")
        finally:
            if exit_after_run:
                progress_log("auto-run", "exit-after-run requested; shutting down service", "yellow")
                httpd.shutdown()

    thread = threading.Thread(target=auto_run, daemon=True, name="writing-mach-auto-run")
    thread.start()


def main() -> int:
    global BACKBONE_PATH, CONFIG_PATH, WEB_AUTH_USER, WEB_AUTH_PASSWORD, RUNTIME_CONFIG_OVERRIDES

    args = parse_args()
    BACKBONE_PATH = Path(args.backbone).expanduser().resolve()
    CONFIG_PATH = Path(args.config).expanduser().resolve()
    RUNTIME_CONFIG_OVERRIDES = {
        key: value
        for key, value in {
            "user_id": args.llm_user,
            "password": args.llm_password,
            "model_retry_wait_seconds": args.model_retry_wait_seconds,
            "model_retry_prompt_after_failures": args.model_retry_prompt_after_failures,
        }.items()
        if value is not None
    }
    ensure_dirs()
    log_path = init_service_log(args.log_file)
    progress_log("service", f"Client config: {CONFIG_PATH}", "cyan")
    if args.test:
        return 0 if run_model_diagnostics(args.model_check_timeout) else 2
    check_startup_model_status(args.model_check_timeout)
    WEB_AUTH_USER, WEB_AUTH_PASSWORD = resolve_web_auth(args.web_user, args.web_password)
    httpd, bind_host = create_http_server(args.host, args.port)
    progress_log("service", f"Writing Mach service: http://{bind_host}:{args.port}", "green")
    service_url = f"http://{bind_host}:{args.port}"
    if bind_host != args.host:
        service_url = f"http://{args.host}:{args.port}"
        progress_log("service", f"Public URL: {service_url}", "cyan")
    if WEB_AUTH_PASSWORD:
        progress_log("service", f"Web auth enabled: user={WEB_AUTH_USER}", "cyan")
    else:
        progress_log("service", "Web auth disabled", "yellow")
    progress_log("service", f"Story backbone: {BACKBONE_PATH}", "cyan")
    progress_log("service", f"Service log: {log_path}", "cyan")
    schedule_prompt_wait_warning(args.prompt_warning_seconds, service_url)
    if args.run_on_start:
        start_run_on_start(args.exit_after_run, httpd)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
