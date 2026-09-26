#!/usr/bin/env python3
"""Small, authenticated Raspberry Pi gateway to a dedicated Ollama daemon."""
import hmac
import ipaddress
import json
import os
import socket
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Config:
    def __init__(self):
        self.host = os.getenv("GEMMA4_SERVER_HOST", "127.0.0.1")
        self.port = int(os.getenv("GEMMA4_SERVER_PORT", "8082"))
        self.backend = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
        self.key = os.getenv("GEMMA4_API_KEY", "")
        self.context = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "2048"))
        self.threads = int(os.getenv("GEMMA4_NUM_THREAD", "4"))
        self.tokens = int(os.getenv("GEMMA4_MAX_TOKENS", "512"))
        self.timeout = int(os.getenv("GEMMA4_REQUEST_TIMEOUT", "1800"))
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
        if len(self.key) < 24:
            raise ValueError("GEMMA4_API_KEY must contain at least 24 characters; run install.sh")
        if min(self.context, self.threads, self.tokens, self.timeout) <= 0:
            raise ValueError("Context, threads, tokens and timeout must be positive")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config):
        self.config = config
        self.inference = threading.Lock()
        self.connections = threading.BoundedSemaphore(16)
        # Do not route localhost inference through a machine-wide HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()

    def backend_json(self, path, payload=None, timeout=5):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.config.backend + path, data=data,
            headers={"Content-Type": "application/json"},
        )
        with self.opener.open(request, timeout=timeout) as response:
            return json.load(response)


def generation_payload(data, path, config):
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    if data.get("stream", False) is not False:
        raise ValueError("Only stream:false is supported")
    if data.get("model", config.model) != config.model:
        raise ValueError("Only the configured model is available")
    payload = {
        "model": config.model, "stream": False, "think": False,
        "keep_alive": config.keep_alive,
        "options": {"num_ctx": config.context, "num_thread": config.threads,
                    "num_gpu": 0, "num_predict": config.tokens},
    }
    if path == "/api/generate":
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A non-empty prompt is required")
        payload["prompt"] = prompt
        if "system" in data:
            if not isinstance(data["system"], str):
                raise ValueError("system must be a string")
            payload["system"] = data["system"]
    else:
        messages = data.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 32:
            raise ValueError("messages must contain 1 to 32 text messages")
        for message in messages:
            if (not isinstance(message, dict)
                    or message.get("role") not in ("system", "user", "assistant")
                    or not isinstance(message.get("content"), str)):
                raise ValueError("Each message requires a valid role and string content")
            if set(message) - {"role", "content"}:
                raise ValueError("Only text messages are supported")
        payload["messages"] = messages
    allowed = {"model", "stream", "prompt", "system"} if path == "/api/generate" else {"model", "stream", "messages"}
    if set(data) - allowed:
        raise ValueError("Unsupported fields: " + ", ".join(sorted(set(data) - allowed)))
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "Gemma4Pi/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send_bytes(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def reply(self, status, data):
        self.send_bytes(status, json.dumps(data, ensure_ascii=False).encode())

    def authenticated(self):
        expected = ("Bearer " + self.server.config.key).encode()
        supplied = self.headers.get("Authorization", "").encode()
        if hmac.compare_digest(supplied, expected):
            return True
        self.reply(401, {"error": "Valid Bearer token required"})
        return False

    def do_GET(self):
        if self.path == "/":
            self.send_bytes(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/health":
            self.reply(200, {"status": "ok"})
        elif self.path == "/ready":
            if not self.authenticated():
                return
            try:
                models = self.server.backend_json("/api/tags").get("models", [])
                ready = any(m.get("name") == self.server.config.model for m in models)
                self.reply(200 if ready else 503, {"ready": ready, "model": self.server.config.model})
            except (OSError, ValueError):
                self.reply(503, {"ready": False, "error": "Ollama unavailable"})
        else:
            self.reply(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in {"/api/generate", "/api/chat"}:
            self.reply(404, {"error": "Not found"})
            return
        if not self.authenticated():
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                self.reply(413, {"error": "JSON body must be 1 to 65536 bytes"})
                return
            data = json.loads(self.rfile.read(length))
            payload = generation_payload(data, self.path, self.server.config)
        except (ValueError, UnicodeError, TimeoutError) as exc:
            self.reply(400, {"error": str(exc)})
            return
        if not self.server.inference.acquire(blocking=False):
            self.reply(429, {"error": "Inference busy; retry after the current request completes"})
            return
        try:
            result = self.server.backend_json(self.path, payload, self.server.config.timeout)
            self.reply(502 if "error" in result else 200, result)
        except urllib.error.HTTPError as exc:
            self.reply(502, {"error": "Ollama inference failed", "backend_status": exc.code,
                             "hint": "Check Ollama logs for model/version or insufficient memory errors"})
        except (TimeoutError, socket.timeout):
            self.reply(504, {"error": "Ollama inference timed out"})
        except (OSError, ValueError):
            self.reply(502, {"error": "Ollama unavailable or invalid response"})
        finally:
            self.server.inference.release()


def print_startup_addresses(config):
    print(f"Gemma4 Pi: http://{config.host}:{config.port} model={config.model}", flush=True)
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=3, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        print("LAN IP: 자동 조회 실패 (hostname -I로 확인하세요).", flush=True)
        return
    addresses = set()
    for value in result.stdout.split():
        try:
            address = ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            continue
        if address in ipaddress.IPv4Network("10.0.0.0/8") or address in ipaddress.IPv4Network("192.168.0.0/16"):
            addresses.add(address)
    for address in sorted(addresses):
        print(f"LAN IP: http://{address}:{config.port}", flush=True)
    if not addresses:
        print("LAN IP: 192.168.* 또는 10.* 내부 주소가 없습니다.", flush=True)
    elif config.host != "0.0.0.0":
        print(
            f"현재 바인딩 주소: {config.host}. 모든 내부 IP로 접속하려면 "
            "config.env의 GEMMA4_SERVER_HOST=0.0.0.0 설정 후 재시작하세요.",
            flush=True,
        )


if __name__ == "__main__":
    config = Config()
    with Server((config.host, config.port), config) as server:
        print_startup_addresses(config)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
