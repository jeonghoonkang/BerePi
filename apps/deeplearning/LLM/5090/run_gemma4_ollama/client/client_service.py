#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.getenv("GEMMA4_CLIENT_HOST", "127.0.0.1")
PORT = int(os.getenv("GEMMA4_CLIENT_PORT", "8765"))
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
RESULT_LOG_DIR = DATA_DIR / "result_logs"
THINKING_LOG_DIR = DATA_DIR / "thinking_logs"
CHAIN_SAVE_DIR = DATA_DIR / "saved_chains"
DEFAULT_WORKSPACE_DIR = Path.home() / "Documents" / "PromptChainWorkspace"
CONFIG_PATH = DATA_DIR / "client_config.json"
HISTORY_PATH = DATA_DIR / "prompt_history.json"
SAMPLE_CONFIG_PATH = BASE_DIR / "config" / "client_config.sample.json"
HISTORY_LIMIT = 300
HISTORY_LOCK = threading.RLock()
PROMPT_MEMORY_LIMIT = 100
LOG_ROTATE_MAX_BYTES = 5 * 1024 * 1024
REMOTE_WORKSPACE_UPLOAD_PATH = "/api/workspace/upload"


DEFAULT_PROMPTS = [
    {"slot": 1, "enabled": True, "group": 1, "text": ""},
    {"slot": 2, "enabled": False, "group": 1, "text": ""},
    {"slot": 3, "enabled": True, "group": 2, "text": ""},
    {"slot": 4, "enabled": False, "group": 2, "text": ""},
    {"slot": 5, "enabled": True, "group": 3, "text": ""},
    {"slot": 6, "enabled": False, "group": 3, "text": ""},
]


DEFAULT_CONFIG = {
    "server_base_url": "http://127.0.0.1:8082",
    "generate_path": "/api/generate",
    "status_path": "/api/status",
    "request_timeout_seconds": 120,
    "user_id": "admin",
    "password": "change-me-now",
    "model": "",
    "keep_alive": "60m",
    "num_ctx": 8192,
    "local_workspace_dir": str(DEFAULT_WORKSPACE_DIR),
    "prompts": DEFAULT_PROMPTS,
}


@dataclass
class PromptEntry:
    slot: int
    enabled: bool
    group: int
    text: str


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    THINKING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    CHAIN_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        sample = DEFAULT_CONFIG
        if SAMPLE_CONFIG_PATH.exists():
            try:
                sample = normalize_config(json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                sample = DEFAULT_CONFIG
        CONFIG_PATH.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]\n", encoding="utf-8")
    for slot in range(1, 7):
        memory_path = prompt_memory_path(slot)
        if not memory_path.exists():
            memory_path.write_text("", encoding="utf-8")


def prompt_memory_path(slot: int) -> Path:
    return DATA_DIR / f"prompt_slot_{int(slot)}.txt"


def normalize_prompt(prompt: dict[str, Any], slot_fallback: int) -> dict[str, Any]:
    return {
        "slot": int(prompt.get("slot", slot_fallback)),
        "enabled": bool(prompt.get("enabled", True)),
        "group": normalize_group(prompt.get("group", 1)),
        "text": str(prompt.get("text", "")),
    }


def normalize_group(value: Any) -> int:
    try:
        group = int(value)
    except (TypeError, ValueError):
        return 1
    return group if group in {1, 2, 3} else 1


def normalize_workspace_dir(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = str(DEFAULT_WORKSPACE_DIR)
    return str(Path(raw).expanduser())


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    prompts = incoming.get("prompts")
    if not isinstance(prompts, list):
        prompts = DEFAULT_PROMPTS
    normalized_prompts = [normalize_prompt(prompt, index + 1) for index, prompt in enumerate(prompts[:6])]
    if len(normalized_prompts) < 6:
        for slot in range(len(normalized_prompts) + 1, 7):
            normalized_prompts.append(normalize_prompt({"slot": slot, "enabled": False, "group": 1, "text": ""}, slot))

    return {
        "server_base_url": str(incoming.get("server_base_url") or DEFAULT_CONFIG["server_base_url"]).rstrip("/"),
        "generate_path": str(incoming.get("generate_path") or DEFAULT_CONFIG["generate_path"]),
        "status_path": str(incoming.get("status_path") or DEFAULT_CONFIG["status_path"]),
        "request_timeout_seconds": max(5, int(incoming.get("request_timeout_seconds") or DEFAULT_CONFIG["request_timeout_seconds"])),
        "user_id": str(incoming.get("user_id") or ""),
        "password": str(incoming.get("password") or ""),
        "model": str(incoming.get("model") or ""),
        "keep_alive": str(incoming.get("keep_alive") or DEFAULT_CONFIG["keep_alive"]),
        "num_ctx": int(incoming.get("num_ctx") or DEFAULT_CONFIG["num_ctx"]),
        "local_workspace_dir": normalize_workspace_dir(incoming.get("local_workspace_dir") or DEFAULT_CONFIG["local_workspace_dir"]),
        "prompts": normalized_prompts,
    }


def runtime_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    base = read_config()
    incoming = dict(override or {})
    merged = dict(base)
    for key in (
        "server_base_url",
        "generate_path",
        "status_path",
        "request_timeout_seconds",
        "user_id",
        "password",
        "model",
        "keep_alive",
        "num_ctx",
        "local_workspace_dir",
        "prompts",
    ):
        if key in incoming:
            merged[key] = incoming[key]
    return normalize_config(merged)


def selected_prompt_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [
        {
            "slot": int(prompt["slot"]),
            "group": normalize_group(prompt["group"]),
            "text": str(prompt["text"]),
        }
        for prompt in config.get("prompts", [])
        if bool(prompt.get("enabled")) and str(prompt.get("text") or "").strip()
    ]
    return sorted(entries, key=lambda item: (item["group"], item["slot"]))


def order_label_for_config(config: dict[str, Any]) -> str:
    entries = selected_prompt_entries(config)
    if not entries:
        return "선택된 프롬프트 없음"
    grouped: dict[int, list[str]] = {}
    for entry in entries:
        grouped.setdefault(entry["group"], []).append(f"Prompt {entry['slot']}")
    return " -> ".join(f"Group {group}: {', '.join(grouped[group])}" for group in (1, 2, 3) if group in grouped)


def sanitize_chain_filename(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "").strip()).strip("._-")
    return value[:120] if value else ""


def sanitize_workspace_filename(name: str) -> str:
    raw = Path(str(name or "")).name
    value = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]+', "_", raw).strip()
    value = value.strip(". ")
    return value[:180] if value else ""


def workspace_root(config: dict[str, Any] | None = None) -> Path:
    effective = config or read_config()
    raw = effective.get("local_workspace_dir") or DEFAULT_CONFIG["local_workspace_dir"]
    return Path(str(raw)).expanduser().resolve(strict=False)


def ensure_workspace_dir(config: dict[str, Any] | None = None) -> Path:
    path = workspace_root(config)
    path.mkdir(parents=True, exist_ok=True)
    return path


def unique_workspace_path(file_name: str) -> Path:
    root = ensure_workspace_dir()
    candidate = root / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_path = root / f"{stem}_{index:02d}{suffix}"
        if not next_path.exists():
            return next_path
        index += 1


def auto_chain_filename() -> str:
    return f"chain_{time.strftime('%Y%m%d_%H%M%S')}.json"


def unique_chain_path(file_name: str) -> Path:
    candidate = CHAIN_SAVE_DIR / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix or ".json"
    index = 2
    while True:
        next_path = CHAIN_SAVE_DIR / f"{stem}_{index:02d}{suffix}"
        if not next_path.exists():
            return next_path
        index += 1


def save_chain_file(config: dict[str, Any], requested_name: str) -> dict[str, Any]:
    normalized = normalize_config(config)
    clean_name = sanitize_chain_filename(requested_name)
    if clean_name:
        if not clean_name.lower().endswith(".json"):
            clean_name = f"{clean_name}.json"
    else:
        clean_name = auto_chain_filename()
    path = unique_chain_path(clean_name)
    payload = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "order_label": order_label_for_config(normalized),
        "config": normalized,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "file_name": path.name,
        "file_path": str(path),
        "order_label": payload["order_label"],
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def list_workspace_files() -> list[dict[str, Any]]:
    root = ensure_workspace_dir()
    files: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "path": f"workspace/{path.name}",
                "absolute_path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            }
        )
    return files


def upload_workspace_files(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        file_name = sanitize_workspace_filename(str(item.get("name") or ""))
        if not file_name:
            continue
        content_base64 = str(item.get("content_base64") or "")
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"Invalid file payload for {file_name}: {exc}") from exc
        path = unique_workspace_path(file_name)
        path.write_bytes(content)
        saved.append(
            {
                "name": path.name,
                "path": f"workspace/{path.name}",
                "absolute_path": str(path),
                "size_bytes": path.stat().st_size,
                "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)),
            }
        )
    return saved


def resolve_workspace_file(name: str) -> Path:
    root = ensure_workspace_dir()
    clean_name = sanitize_workspace_filename(name)
    if not clean_name:
        raise ValueError("Valid workspace file name is required.")
    path = (root / clean_name).resolve()
    if path.parent != root.resolve():
        raise ValueError("Invalid workspace path.")
    if not path.exists() or not path.is_file():
        raise ValueError(f"Workspace file not found: {clean_name}")
    return path


def delete_workspace_file(name: str) -> dict[str, Any]:
    path = resolve_workspace_file(name)
    file_name = path.name
    path.unlink()
    return {"deleted": file_name}


def rename_workspace_file(old_name: str, new_name: str) -> dict[str, Any]:
    source = resolve_workspace_file(old_name)
    root = ensure_workspace_dir()
    target_name = sanitize_workspace_filename(new_name)
    if not target_name:
        raise ValueError("New file name is required.")
    target = root / target_name
    if target.exists() and target.resolve() != source.resolve():
        target = unique_workspace_path(target_name)
    source.rename(target)
    stat = target.stat()
    return {
        "name": target.name,
        "path": f"workspace/{target.name}",
        "size_bytes": stat.st_size,
        "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
    }


def workspace_payload() -> dict[str, Any]:
    root = ensure_workspace_dir()
    return {
        "workspace_dir": str(root),
        "files": list_workspace_files(),
    }


def read_config() -> dict[str, Any]:
    ensure_data_files()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = DEFAULT_CONFIG
    return normalize_config(data)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def read_prompt_memory(slot: int) -> list[str]:
    path = prompt_memory_path(slot)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    entries: list[str] = []
    seen: set[str] = set()
    for line in lines:
        value = line.strip()
        if not value:
            continue
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                value = parsed.strip()
        except json.JSONDecodeError:
            pass
        if not value or value in seen:
            continue
        entries.append(value)
        seen.add(value)
        if len(entries) >= PROMPT_MEMORY_LIMIT:
            break
    return entries


def write_prompt_memory(slot: int, entries: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        value = str(entry).strip()
        if not value or value in seen:
            continue
        unique.append(value)
        seen.add(value)
        if len(unique) >= PROMPT_MEMORY_LIMIT:
            break
    body = "".join(f"{json.dumps(entry, ensure_ascii=False)}\n" for entry in unique)
    prompt_memory_path(slot).write_text(body, encoding="utf-8")
    return unique


def save_prompt_memory(slot: int, text: str) -> list[str]:
    value = str(text).strip()
    if not value:
        raise ValueError("Prompt text is required.")
    existing = read_prompt_memory(slot)
    return write_prompt_memory(slot, [value] + existing)


def delete_prompt_memory(slot: int, text: str) -> list[str]:
    value = str(text).strip()
    return write_prompt_memory(slot, [entry for entry in read_prompt_memory(slot) if entry != value])


def all_prompt_memories() -> dict[str, list[str]]:
    return {str(slot): read_prompt_memory(slot) for slot in range(1, 7)}


def read_history() -> list[dict[str, Any]]:
    ensure_data_files()
    with HISTORY_LOCK:
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for entry in data[:HISTORY_LIMIT]:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        cleaned.append(
            {
                "id": str(entry.get("id") or f"history-{len(cleaned)+1}"),
                "slot": int(entry.get("slot") or 1),
                "group": normalize_group(entry.get("group") or 1),
                "text": text,
                "updated_at": str(entry.get("updated_at") or ""),
            }
        )
    return cleaned


def write_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = read_history_entries(entries)
    with HISTORY_LOCK:
        HISTORY_PATH.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cleaned


def read_history_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for entry in entries:
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        key = (int(entry.get("slot") or 1), normalize_group(entry.get("group") or 1), text)
        if key in seen:
            continue
        unique.append(
            {
                "id": str(entry.get("id") or f"{int(time.time() * 1000)}-{len(unique)+1}"),
                "slot": key[0],
                "group": key[1],
                "text": text,
                "updated_at": str(entry.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
            }
        )
        seen.add(key)
        if len(unique) >= HISTORY_LIMIT:
            break
    return unique


def remember_prompts(prompts: list[PromptEntry]) -> list[dict[str, Any]]:
    if not prompts:
        return read_history()
    existing = read_history()
    fresh = [
        {
            "id": f"{int(time.time() * 1000)}-{index}",
            "slot": prompt.slot,
            "group": prompt.group,
            "text": prompt.text.strip(),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for index, prompt in enumerate(prompts, start=1)
        if prompt.text.strip()
    ]
    return write_history(fresh + existing)


def delete_history_ids(ids: list[str]) -> list[dict[str, Any]]:
    id_set = {str(item) for item in ids}
    remaining = [entry for entry in read_history() if entry["id"] not in id_set]
    return write_history(remaining)


def join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def extract_thinking_blocks(text: str) -> tuple[str, str]:
    value = str(text or "")
    matches = list(re.finditer(r"<think>([\s\S]*?)</think>", value, flags=re.IGNORECASE))
    if not matches:
        return "", value.strip()
    thinking = "\n\n".join(str(match.group(1) or "").strip() for match in matches if str(match.group(1) or "").strip())
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", value, flags=re.IGNORECASE).strip()
    return thinking, cleaned


def extract_structured_thinking(data: dict[str, Any]) -> str:
    direct = data.get("thinking")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    for key in ("thoughts", "reasoning", "reasoning_content", "thinking_text"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    message = data.get("message")
    if isinstance(message, dict):
        for key in ("thinking", "thoughts", "reasoning", "reasoning_content"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def next_log_path(directory: Path, prefix: str) -> Path:
    candidates = sorted(directory.glob(f"{prefix}_*.txt"))
    if not candidates:
        return directory / f"{prefix}_0001.txt"
    latest = candidates[-1]
    try:
        suffix = int(latest.stem.rsplit("_", 1)[-1])
    except ValueError:
        suffix = len(candidates)
    if latest.exists() and latest.stat().st_size < LOG_ROTATE_MAX_BYTES:
        return latest
    return directory / f"{prefix}_{suffix + 1:04d}.txt"


def append_rotating_log(directory: Path, prefix: str, content: str) -> Path:
    encoded = content.encode("utf-8")
    path = next_log_path(directory, prefix)
    if path.exists() and path.stat().st_size + len(encoded) > LOG_ROTATE_MAX_BYTES:
        try:
            suffix = int(path.stem.rsplit("_", 1)[-1]) + 1
        except ValueError:
            suffix = 2
        path = directory / f"{prefix}_{suffix:04d}.txt"
    with path.open("ab") as handle:
        handle.write(encoded)
    return path


def directory_total_size(directory: Path) -> int:
    total = 0
    for path in directory.glob("*.txt"):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def format_result_log(result: dict[str, Any]) -> str:
    lines = [
        "=" * 88,
        f"saved_at={time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"server_base_url={result.get('server_base_url', '')}",
        f"generate_url={result.get('generate_url', '')}",
        f"final_model={result.get('final_model', '')}",
        f"elapsed_seconds={result.get('elapsed_seconds', 0):.3f}",
        "",
    ]
    for step in result.get("steps", []):
        lines.extend(
            [
                f"[Group {step.get('group')}]",
                f"slots={', '.join(step.get('slot_labels', []))}",
                f"elapsed={step.get('elapsed_line', '')}",
                "[Request Prompt]",
                str(step.get("request_prompt", "")),
                "",
                "[Response]",
                str(step.get("response", "")),
                "",
            ]
        )
    lines.extend(["[Final Response]", str(result.get("final_response", "")), "", ""])
    return "\n".join(lines)


def format_thinking_log(result: dict[str, Any]) -> str:
    lines = [
        "=" * 88,
        f"saved_at={time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"server_base_url={result.get('server_base_url', '')}",
        f"generate_url={result.get('generate_url', '')}",
        "",
    ]
    for step in result.get("steps", []):
        thinking = str(step.get("thinking", "") or "").strip()
        visible = str(step.get("visible_response", "") or "").strip()
        if not thinking:
            thinking, visible = extract_thinking_blocks(str(step.get("response", "")))
        lines.extend(
            [
                f"[Group {step.get('group')}]",
                f"slots={', '.join(step.get('slot_labels', []))}",
                "[Request Prompt]",
                str(step.get("request_prompt", "")),
                "",
                "[Thinking]",
                thinking or "(no explicit thinking block found)",
                "",
                "[Visible Response]",
                visible or str(step.get("response", "")),
                "",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def persist_chain_logs(result: dict[str, Any]) -> dict[str, str]:
    result_path = append_rotating_log(RESULT_LOG_DIR, "result", format_result_log(result))
    thinking_path = append_rotating_log(THINKING_LOG_DIR, "thinking", format_thinking_log(result))
    result_total_size = directory_total_size(RESULT_LOG_DIR)
    thinking_total_size = directory_total_size(THINKING_LOG_DIR)
    return {
        "result_log_path": str(result_path),
        "thinking_log_path": str(thinking_path),
        "result_log_size_bytes": result_path.stat().st_size if result_path.exists() else 0,
        "thinking_log_size_bytes": thinking_path.stat().st_size if thinking_path.exists() else 0,
        "result_log_total_size_bytes": result_total_size,
        "thinking_log_total_size_bytes": thinking_total_size,
        "all_logs_total_size_bytes": result_total_size + thinking_total_size,
        "saved_before_response": True,
    }


def request_json(
    url: str,
    payload: dict[str, Any] | None,
    timeout: int,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def remote_workspace_upload(config: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"attempted": False, "ok": True, "saved_count": 0, "saved": []}
    if not config.get("server_base_url"):
        return {"attempted": False, "ok": False, "error": "Server Base URL is required for remote workspace sync."}
    if not config.get("user_id") or not config.get("password"):
        return {"attempted": False, "ok": False, "error": "User ID and Password are required for remote workspace sync."}

    upload_url = join_url(config["server_base_url"], REMOTE_WORKSPACE_UPLOAD_PATH)
    token = base64.b64encode(f"{config['user_id']}:{config['password']}".encode("utf-8")).decode("ascii")
    try:
        data = request_json(
            upload_url,
            {"files": items},
            int(config["request_timeout_seconds"]),
            {"Authorization": f"Basic {token}"},
        )
        return {
            "attempted": True,
            "ok": True,
            "url": upload_url,
            "workspace_dir": str(data.get("workspace_dir") or ""),
            "saved_count": len(data.get("saved") or []),
            "saved": data.get("saved") or [],
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        return {
            "attempted": True,
            "ok": False,
            "url": upload_url,
            "error": str(exc),
        }


def fetch_remote_workspace_files(config: dict[str, Any]) -> dict[str, Any]:
    if not config.get("server_base_url"):
        return {"attempted": False, "ok": False, "error": "Server Base URL is required."}
    if not config.get("user_id") or not config.get("password"):
        return {"attempted": False, "ok": False, "error": "User ID and Password are required."}
    url = join_url(config["server_base_url"], "/api/workspace/files")
    token = base64.b64encode(f"{config['user_id']}:{config['password']}".encode("utf-8")).decode("ascii")
    try:
        data = request_json(
            url,
            None,
            int(config["request_timeout_seconds"]),
            {"Authorization": f"Basic {token}"},
        )
        return {
            "attempted": True,
            "ok": True,
            "url": url,
            "workspace_dir": str(data.get("workspace_dir") or ""),
            "files": data.get("files") or [],
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        return {
            "attempted": True,
            "ok": False,
            "url": url,
            "error": str(exc),
            "files": [],
        }


def collect_selected_prompts(config: dict[str, Any]) -> list[PromptEntry]:
    selected: list[PromptEntry] = []
    for prompt in config["prompts"]:
        entry = PromptEntry(
            slot=int(prompt["slot"]),
            enabled=bool(prompt["enabled"]),
            group=normalize_group(prompt["group"]),
            text=str(prompt["text"]),
        )
        if entry.enabled and entry.text.strip():
            selected.append(entry)
    return selected


def group_prompt_text(prompts: list[PromptEntry]) -> str:
    ordered = sorted(prompts, key=lambda item: item.slot)
    return "\n\n".join(prompt.text.strip() for prompt in ordered if prompt.text.strip())


def build_generate_payload(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "keep_alive": config["keep_alive"],
        "options": {"num_ctx": int(config["num_ctx"])},
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def run_chain(config: dict[str, Any]) -> dict[str, Any]:
    selected = collect_selected_prompts(config)
    if not selected:
        raise ValueError("At least one selected prompt is required.")
    if not config.get("server_base_url"):
        raise ValueError("Server Base URL is required.")
    if not config.get("user_id") or not config.get("password"):
        raise ValueError("User ID and Password are required.")

    timeout = int(config["request_timeout_seconds"])
    generate_url = join_url(config["server_base_url"], config["generate_path"])
    grouped = {group: [prompt for prompt in selected if prompt.group == group] for group in (1, 2, 3)}

    chain_started = time.perf_counter()
    prior_response = ""
    steps: list[dict[str, Any]] = []

    for group in (1, 2, 3):
        prompts = grouped[group]
        if not prompts:
            continue
        addition = group_prompt_text(prompts)
        request_prompt = addition if not prior_response else f"{prior_response}\n\n{addition}"
        started = time.perf_counter()
        response_data = request_json(generate_url, build_generate_payload(config, request_prompt), timeout)
        response_text = str(response_data.get("response") or "")
        structured_thinking = extract_structured_thinking(response_data)
        block_thinking, visible_response = extract_thinking_blocks(response_text)
        final_thinking = structured_thinking or block_thinking
        elapsed_seconds = time.perf_counter() - started
        steps.append(
            {
                "group": group,
                "slot_labels": [f"Prompt {prompt.slot}" for prompt in sorted(prompts, key=lambda item: item.slot)],
                "request_prompt": request_prompt,
                "response": response_text,
                "thinking": final_thinking,
                "visible_response": visible_response or response_text,
                "model": str(response_data.get("model") or config.get("model") or ""),
                "server_ip": str(response_data.get("server_ip") or ""),
                "server_port": str(response_data.get("server_port") or ""),
                "elapsed_seconds": float(response_data.get("elapsed_seconds") or elapsed_seconds),
                "elapsed_line": str(response_data.get("elapsed_line") or f"Elapsed time: {elapsed_seconds:.2f}s"),
            }
        )
        prior_response = response_text

    remember_prompts(selected)
    elapsed = time.perf_counter() - chain_started
    result = {
        "steps": steps,
        "final_response": prior_response,
        "final_model": steps[-1]["model"] if steps else "",
        "elapsed_seconds": elapsed,
        "server_base_url": config["server_base_url"],
        "generate_url": generate_url,
        "order_label": order_label_for_config(config),
    }
    result.update(persist_chain_logs(result))
    return result


def fetch_remote_status(config: dict[str, Any]) -> dict[str, Any]:
    timeout = int(config["request_timeout_seconds"])
    status_url = join_url(config["server_base_url"], config["status_path"])
    data = request_json(status_url, None, timeout)
    return {
        "server_base_url": config["server_base_url"],
        "status_url": status_url,
        "host": data.get("host", ""),
        "port": data.get("port", ""),
        "model": data.get("model", ""),
        "ollama_reachable": bool(data.get("ollama_reachable")),
        "model_available": bool(data.get("model_available")),
    }


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


class ClientHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

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
            self.send_json({
                "config": read_config(),
                "history": read_history(),
                "prompt_memories": all_prompt_memories(),
                "workspace_files": list_workspace_files(),
                "workspace_dir": str(ensure_workspace_dir()),
            })
            return
        if self.path == "/api/history":
            self.send_json({"history": read_history()})
            return
        if self.path == "/api/prompt-memories":
            self.send_json({"prompt_memories": all_prompt_memories()})
            return
        if self.path == "/api/workspace/files":
            self.send_json(workspace_payload())
            return
        if self.path == "/api/workspace/remote-files":
            config = runtime_config()
            self.send_json(fetch_remote_workspace_files(config))
            return
        if self.path.startswith("/api/workspace/download?"):
            try:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                name = str((query.get("name") or [""])[0])
                path = resolve_workspace_file(name)
                body = path.read_bytes()
                quoted_name = urllib.parse.quote(path.name, safe="")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted_name}")
                self.end_headers()
                self.wfile.write(body)
            except (OSError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            incoming = parse_json_body(self)
            if self.path == "/api/config":
                config = write_config(incoming.get("config") or {})
                ensure_workspace_dir(config)
                self.send_json({"config": config})
                return
            if self.path == "/api/test-connection":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": fetch_remote_status(config)})
                return
            if self.path == "/api/run-chain":
                config = runtime_config(incoming.get("config"))
                result = run_chain(config)
                self.send_json(result)
                return
            if self.path == "/api/save-chain-file":
                config = runtime_config((incoming.get("config") or {}) if isinstance(incoming, dict) else {})
                result = save_chain_file(config, str(incoming.get("name") or ""))
                self.send_json(result)
                return
            if self.path == "/api/history/delete":
                history = delete_history_ids(incoming.get("ids") or [])
                self.send_json({"history": history})
                return
            if self.path == "/api/workspace/upload":
                config = runtime_config(incoming.get("config"))
                saved = upload_workspace_files(incoming.get("files") or [])
                remote_sync = remote_workspace_upload(config, incoming.get("files") or [])
                self.send_json({"saved": saved, "remote_sync": remote_sync, **workspace_payload()})
                return
            if self.path == "/api/workspace/delete":
                result = delete_workspace_file(str(incoming.get("name") or ""))
                self.send_json({**result, **workspace_payload()})
                return
            if self.path == "/api/workspace/rename":
                result = rename_workspace_file(str(incoming.get("old_name") or ""), str(incoming.get("new_name") or ""))
                self.send_json({"renamed": result, **workspace_payload()})
                return
            if self.path == "/api/prompt-memory/save":
                slot = int(incoming.get("slot") or 0)
                if slot not in range(1, 7):
                    raise ValueError("Valid prompt slot is required.")
                memories = save_prompt_memory(slot, str(incoming.get("text") or ""))
                self.send_json({"slot": slot, "entries": memories})
                return
            if self.path == "/api/prompt-memory/delete":
                slot = int(incoming.get("slot") or 0)
                if slot not in range(1, 7):
                    raise ValueError("Valid prompt slot is required.")
                memories = delete_prompt_memory(slot, str(incoming.get("text") or ""))
                self.send_json({"slot": slot, "entries": memories})
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (json.JSONDecodeError, OSError, urllib.error.URLError) as exc:
            target_url = ""
            if self.path == "/api/test-connection":
                config = runtime_config(incoming.get("config") if isinstance(incoming, dict) else None)
                target_url = join_url(config["server_base_url"], config["status_path"])
            elif self.path == "/api/run-chain":
                config = runtime_config(incoming.get("config") if isinstance(incoming, dict) else None)
                target_url = join_url(config["server_base_url"], config["generate_path"])
            message = str(exc)
            if target_url:
                message = f"{message} | target={target_url}"
            self.send_json({"error": message}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    ensure_data_files()
    httpd = ThreadingHTTPServer((HOST, PORT), ClientHandler)
    print(f"Gemma4 client service: http://{HOST}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
