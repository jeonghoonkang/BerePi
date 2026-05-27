#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.getenv("GEMMA_OCR_CLIENT_HOST", "127.0.0.1")
PORT = int(os.getenv("GEMMA_OCR_CLIENT_PORT", "8775"))
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "client_config.json"
HISTORY_PATH = DATA_DIR / "ocr_history.json"
SAMPLE_CONFIG_PATH = BASE_DIR / "config" / "client_config.sample.json"
HISTORY_LIMIT = 100

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
    "ocr_prompt": "Extract all visible text from the image. Preserve line breaks and reading order. Return only the OCR text.",
}

TEST_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        sample = DEFAULT_CONFIG
        if SAMPLE_CONFIG_PATH.exists():
            try:
                sample = normalize_config(json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                sample = DEFAULT_CONFIG
        CONFIG_PATH.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]\n", encoding="utf-8")


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    timeout = int(incoming.get("request_timeout_seconds") or DEFAULT_CONFIG["request_timeout_seconds"])
    num_ctx = int(incoming.get("num_ctx") or DEFAULT_CONFIG["num_ctx"])
    return {
        "server_base_url": str(incoming.get("server_base_url") or DEFAULT_CONFIG["server_base_url"]).rstrip("/"),
        "generate_path": str(incoming.get("generate_path") or DEFAULT_CONFIG["generate_path"]),
        "status_path": str(incoming.get("status_path") or DEFAULT_CONFIG["status_path"]),
        "request_timeout_seconds": max(5, timeout),
        "user_id": str(incoming.get("user_id") or ""),
        "password": str(incoming.get("password") or ""),
        "model": str(incoming.get("model") or ""),
        "keep_alive": str(incoming.get("keep_alive") or DEFAULT_CONFIG["keep_alive"]),
        "num_ctx": max(0, num_ctx),
        "ocr_prompt": str(incoming.get("ocr_prompt") or DEFAULT_CONFIG["ocr_prompt"]),
    }


def read_config() -> dict[str, Any]:
    ensure_data_files()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        data = DEFAULT_CONFIG
    return normalize_config(data)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def runtime_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = read_config()
    for key, value in dict(override or {}).items():
        if key in DEFAULT_CONFIG:
            merged[key] = value
    return normalize_config(merged)


def read_history() -> list[dict[str, Any]]:
    ensure_data_files()
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data[:HISTORY_LIMIT] if isinstance(entry, dict)]


def append_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = [entry] + read_history()
    history = history[:HISTORY_LIMIT]
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history


def clear_history() -> list[dict[str, Any]]:
    HISTORY_PATH.write_text("[]\n", encoding="utf-8")
    return []


def join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def request_json(
    url: str,
    payload: dict[str, Any] | None,
    timeout: int,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        content_type = str(response.headers.get("Content-Type") or "")
        if not raw.strip():
            raise ValueError(f"Empty response from {url}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            preview = raw.strip().replace("\n", " ")[:220]
            raise ValueError(
                f"Expected JSON from {url}, but received Content-Type={content_type or 'unknown'}; "
                f"preview={preview!r}"
            ) from exc


def basic_auth_header(config: dict[str, Any]) -> dict[str, str]:
    if not config.get("user_id") or not config.get("password"):
        return {}
    token = base64.b64encode(f"{config['user_id']}:{config['password']}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


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
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    return json.dumps(data, ensure_ascii=False, indent=2)


def clean_image_item(item: dict[str, Any]) -> dict[str, str]:
    name = str(item.get("name") or "image")
    mime_type = str(item.get("mime_type") or "image/png")
    content_base64 = str(item.get("content_base64") or "")
    if not mime_type.startswith("image/"):
        raise ValueError(f"Only image files are supported: {name}")
    try:
        base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid image payload for {name}: {exc}") from exc
    return {"name": name, "mime_type": mime_type, "content_base64": content_base64}


def build_generate_payload(config: dict[str, Any], prompt: str, images: list[dict[str, str]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "images": [image["content_base64"] for image in images],
        "keep_alive": config["keep_alive"],
        "stream": False,
        "options": {"num_ctx": int(config["num_ctx"])},
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def run_ocr(config: dict[str, Any], images: list[dict[str, Any]], prompt: str) -> dict[str, Any]:
    if not config.get("server_base_url"):
        raise ValueError("Gemma model URL is required.")
    if not images:
        raise ValueError("At least one image is required.")
    clean_images = [clean_image_item(item) for item in images]
    effective_prompt = str(prompt or config["ocr_prompt"]).strip()
    if not effective_prompt:
        raise ValueError("OCR prompt is required.")
    generate_url = join_url(config["server_base_url"], config["generate_path"])
    started = time.perf_counter()
    try:
        data = request_json(
            generate_url,
            build_generate_payload(config, effective_prompt, clean_images),
            int(config["request_timeout_seconds"]),
            basic_auth_header(config),
        )
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to Gemma generate endpoint: {generate_url} | {exc}") from exc
    elapsed = time.perf_counter() - started
    text = extract_response_text(data).strip()
    remote_image_count = data.get("image_count")
    if remote_image_count is not None:
        try:
            remote_image_count = int(remote_image_count)
        except (TypeError, ValueError):
            remote_image_count = None
    entry = {
        "id": f"ocr-{int(time.time() * 1000)}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_base_url": config["server_base_url"],
        "generate_url": generate_url,
        "model": str(data.get("model") or config.get("model") or ""),
        "image_names": [image["name"] for image in clean_images],
        "image_count": len(clean_images),
        "server_image_count": remote_image_count,
        "server_response_keys": sorted(str(key) for key in data.keys()),
        "elapsed_seconds": elapsed,
        "text": text,
    }
    return {"result": entry, "raw": data, "history": append_history(entry)}


def build_image_transfer_test_payload(config: dict[str, Any], images: list[dict[str, Any]]) -> dict[str, Any]:
    clean_images = [clean_image_item(item) for item in images]
    if not clean_images:
        clean_images = [
            {
                "name": "embedded-1x1-test.png",
                "mime_type": "image/png",
                "content_base64": TEST_IMAGE_BASE64,
            }
        ]
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "images": [image["content_base64"] for image in clean_images],
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def test_image_transfer(config: dict[str, Any], images: list[dict[str, Any]]) -> dict[str, Any]:
    if not config.get("server_base_url"):
        raise ValueError("Gemma model URL is required.")
    url = join_url(config["server_base_url"], "/api/test-image-transfer")
    payload = build_image_transfer_test_payload(config, images)
    image_count = len(payload["images"])
    started = time.perf_counter()
    try:
        data = request_json(url, payload, int(config["request_timeout_seconds"]), basic_auth_header(config))
    except urllib.error.HTTPError as exc:
        if exc.code == HTTPStatus.NOT_FOUND:
            raise ValueError(
                f"Image transfer test endpoint not found: {url}. "
                "Restart or update the Gemma server with /api/test-image-transfer support."
            ) from exc
        raise
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to Gemma image-transfer test endpoint: {url} | {exc}") from exc
    elapsed = time.perf_counter() - started
    return {
        "ok": bool(data.get("ok")),
        "test_url": url,
        "client_image_count": image_count,
        "server_image_count": data.get("image_count"),
        "elapsed_seconds": elapsed,
        "message": str(data.get("message") or ""),
        "raw": data,
    }


def fetch_remote_status(config: dict[str, Any]) -> dict[str, Any]:
    url = join_url(config["server_base_url"], config["status_path"])
    try:
        data = request_json(url, None, int(config["request_timeout_seconds"]), basic_auth_header(config))
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to Gemma status endpoint: {url} | {exc}") from exc
    return {
        "server_base_url": config["server_base_url"],
        "status_url": url,
        "host": data.get("host", ""),
        "port": data.get("port", ""),
        "model": data.get("model", ""),
        "ollama_reachable": bool(data.get("ollama_reachable", True)),
        "model_available": bool(data.get("model_available", True)),
        "raw": data,
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
            self.send_json({"config": read_config(), "history": read_history()})
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            incoming = parse_json_body(self)
            if self.path == "/api/config":
                self.send_json({"config": write_config(incoming.get("config") or {})})
                return
            if self.path == "/api/test-connection":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": fetch_remote_status(config)})
                return
            if self.path == "/api/test-image-transfer":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": test_image_transfer(config, incoming.get("images") or [])})
                return
            if self.path == "/api/ocr":
                config = runtime_config(incoming.get("config"))
                self.send_json(run_ocr(config, incoming.get("images") or [], str(incoming.get("prompt") or "")))
                return
            if self.path == "/api/history/clear":
                self.send_json({"history": clear_history()})
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (json.JSONDecodeError, OSError, urllib.error.URLError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    ensure_data_files()
    httpd = ThreadingHTTPServer((HOST, PORT), ClientHandler)
    print(f"Gemma OCR client service: http://{HOST}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
