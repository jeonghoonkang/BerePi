#!/usr/bin/env python3
"""Small, authenticated Raspberry Pi gateway to a dedicated Ollama daemon."""
import hmac
import base64
import binascii
import io
import ipaddress
import json
import os
import platform
import shutil
import secrets
import time
import socket
import subprocess
import sys
import threading
import warnings
import urllib.error
import urllib.request
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_OCR_BODY = ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 65536
RESTART_EXIT_CODE = 75
OCR_PROMPT = ("이미지에서 읽을 수 있는 모든 글자를 추출해 주세요. "
              "원문의 언어와 줄바꿈을 유지하고, 설명이나 추측 없이 인식한 텍스트만 반환하세요.")


class Config:
    def __init__(self):
        self.host = os.getenv("GEMMA4_SERVER_HOST", "0.0.0.0")
        self.port = int(os.getenv("GEMMA4_SERVER_PORT", "8082"))
        self.backend = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
        self.key = os.getenv("GEMMA4_API_KEY", "")
        self.user = os.getenv("GEMMA4_LOGIN_USER", "admin")
        self.password = os.getenv("GEMMA4_LOGIN_PASSWORD") or self.key
        self.context = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "2048"))
        self.threads = int(os.getenv("GEMMA4_NUM_THREAD", "4"))
        self.tokens = int(os.getenv("GEMMA4_MAX_TOKENS", "512"))
        self.ocr_tokens = int(os.getenv("GEMMA4_OCR_MAX_TOKENS", "2048"))
        self.timeout = int(os.getenv("GEMMA4_REQUEST_TIMEOUT", "1800"))
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
        if len(self.key) < 24:
            raise ValueError("GEMMA4_API_KEY must contain at least 24 characters; run install.sh")
        if min(self.context, self.threads, self.tokens, self.ocr_tokens, self.timeout) <= 0:
            raise ValueError("Context, threads, tokens and timeout must be positive")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config):
        self.config = config
        self.started = time.monotonic()
        self.instance_id = secrets.token_hex(16)
        self.restart_requested = threading.Event()
        self.sessions = {}
        self.session_lock = threading.Lock()
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


def machine_info():
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                memory[key] = int(value.split()[0]) * 1024
    except (OSError, ValueError):
        pass
    try:
        temperature = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        temperature = None
    return {"hostname": socket.gethostname(), "os": platform.platform(),
            "architecture": platform.machine(), "cpu_count": os.cpu_count(),
            "load_average": list(os.getloadavg()), "memory": memory,
            "temperature_c": temperature}


def local_ipv4_addresses():
    """Return this server's LAN addresses, with 192.168.* addresses first."""
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=3, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    addresses = set()
    for value in result.stdout.split():
        try:
            address = ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            continue
        if address in ipaddress.IPv4Network("192.168.0.0/16") or address in ipaddress.IPv4Network("10.0.0.0/8"):
            addresses.add(address)
    return [str(address) for address in sorted(addresses, key=lambda ip: (not str(ip).startswith("192.168."), int(ip)))]


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


def ocr_payload(data, config):
    if not isinstance(data, dict) or set(data) - {"image", "prompt", "instructions", "engine"}:
        raise ValueError("OCR requires image and optional engine, prompt or instructions")
    if data.get("engine", "gemma") not in ("tesseract", "gemma"):
        raise ValueError("OCR engine must be tesseract or gemma")
    if "prompt" in data and "instructions" in data:
        raise ValueError("Use either prompt or instructions, not both")
    instructions = data.get("instructions", "")
    if not isinstance(instructions, str) or len(instructions) > 4000:
        raise ValueError("OCR instructions must be at most 4000 characters")
    encoded = data.get("image")
    if not isinstance(encoded, str) or not encoded or len(encoded) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise ValueError("JPG/PNG image must be at most 10 MiB")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 image") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("JPG/PNG image must be at most 10 MiB")
    # Lazy import keeps text-only use available before upgrading dependencies.
    from PIL import Image, UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise ValueError("Only JPG and PNG images are supported")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image must be at most 20 megapixels")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, SyntaxError) as exc:
        raise ValueError("Invalid or oversized JPG/PNG image") from exc
    prompt = data.get("prompt", OCR_PROMPT + ("\n" + instructions.strip() if instructions.strip() else ""))
    if not isinstance(prompt, str) or not prompt.strip() or ("prompt" in data and len(prompt) > 4000):
        raise ValueError("OCR prompt must contain 1 to 4000 characters")
    payload = generation_payload({"messages": [{"role": "user", "content": prompt}]}, "/api/chat", config)
    payload["messages"][0]["images"] = [encoded]
    payload["options"]["num_predict"] = config.ocr_tokens
    return payload

def tesseract_ocr(encoded):
    runtime = Path(__file__).with_name('.ocr-runtime')
    binary = shutil.which('tesseract')
    env = os.environ.copy()
    env['OMP_THREAD_LIMIT'] = '1'
    if not binary and (runtime / 'usr/bin/tesseract').exists():
        binary = str(runtime / 'usr/bin/tesseract')
        libraries = [str(path) for path in (runtime / 'usr/lib').glob('*-linux-gnu')]
        env['LD_LIBRARY_PATH'] = ':'.join(libraries + [env.get('LD_LIBRARY_PATH', '')])
        env['TESSDATA_PREFIX'] = str(runtime / 'usr/share/tesseract-ocr/5/tessdata')
    if not binary:
        raise RuntimeError('Tesseract가 없습니다. 서버에서 bash install_ocr.sh를 실행하세요.')
    result = subprocess.run([binary, 'stdin', 'stdout', '-l', 'kor+eng', '--psm', '3'],
                            input=base64.b64decode(encoded), capture_output=True,
                            env=env, timeout=90)
    if result.returncode:
        raise RuntimeError('Tesseract OCR 실패: 이미지와 kor/eng 언어 데이터 설치를 확인하세요.')
    return {'response': result.stdout.decode('utf-8').strip(),
            'model': 'Tesseract (kor+eng)', 'done': True, 'done_reason': 'stop'}


class Handler(BaseHTTPRequestHandler):
    server_version = "Gemma4Pi/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send_bytes(self, status, body, content_type="application/json; charset=utf-8", cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def reply(self, status, data, cookie=None):
        self.send_bytes(status, json.dumps(data, ensure_ascii=False).encode(), cookie=cookie)

    def session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return cookie["gemma_pi_session"].value if "gemma_pi_session" in cookie else ""
        except CookieError:
            return ""

    def session_user(self):
        with self.server.session_lock:
            record = self.server.sessions.get(self.session_token())
            if record and record[1] > time.monotonic():
                return record[0]
        return None

    def same_origin(self):
        origin = self.headers.get("Origin")
        try:
            foreign_origin = bool(origin and urlsplit(origin).netloc != self.headers.get("Host"))
        except ValueError:
            foreign_origin = True
        if foreign_origin or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.reply(403, {"error": "Cross-origin requests are not allowed"})
            return False
        return True

    def read_json(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are not supported")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 65536:
            raise ValueError("JSON body must be 1 to 65536 bytes")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def status_data(self):
        config = self.server.config
        result = {"server": machine_info(), "uptime_seconds": round(time.monotonic() - self.server.started),
                  "host": config.host, "port": config.port, "backend_url": config.backend,
                  "local_urls": [f"http://{address}:{config.port}" for address in local_ipv4_addresses()],
                  "instance_id": self.server.instance_id,
                  "restarting": self.server.restart_requested.is_set(),
                  "model": config.model, "busy": self.server.inference.locked(),
                  "inference": {"device": "CPU", "threads": config.threads,
                                "context": config.context, "max_tokens": config.tokens,
                                "timeout_seconds": config.timeout, "keep_alive": config.keep_alive},
                  "ollama_online": False, "model_installed": False, "loaded_models": []}
        try:
            models = self.server.backend_json("/api/tags").get("models", [])
            result["ollama_online"] = True
            result["model_details"] = next((m for m in models if m.get("name") == config.model), None)
            result["model_installed"] = result["model_details"] is not None
        except (OSError, ValueError):
            result["backend_error"] = "Ollama에 연결할 수 없습니다."
        try:
            result["loaded_models"] = self.server.backend_json("/api/ps").get("models", [])
        except (OSError, ValueError):
            result["loaded_models_error"] = "로드 상태를 조회할 수 없습니다."
        return result

    def authenticated(self):
        if self.session_user():
            return True
        expected = ("Bearer " + self.server.config.key).encode()
        supplied = self.headers.get("Authorization", "").encode()
        if hmac.compare_digest(supplied, expected):
            return True
        self.reply(401, {"error": "Valid Bearer token required"})
        return False

    def do_GET(self):
        if self.path == "/":
            self.send_bytes(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path in {"/api", "/api/"}:
            self.reply(200, {"service": "Gemma4 Raspberry Pi", "endpoints": {
                "GET": ["/api/ocr/example", "/api/health", "/api/ready", "/api/session", "/api/status", "/api/model-info"],
                "POST": ["/api/session-login", "/api/session-logout", "/api/generate", "/api/chat", "/api/ocr", "/api/restart"],
            }})
        elif self.path in {"/health", "/api/health"}:
            self.reply(200, {"status": "ok", "instance_id": self.server.instance_id,
                             "restarting": self.server.restart_requested.is_set()})
        elif self.path == "/api/session":
            user = self.session_user()
            self.reply(200, {"logged_in": bool(user), "user_id": user})
        elif self.path == "/api/status":
            if self.authenticated():
                self.reply(200, self.status_data())
        elif self.path == "/api/ocr/example":
            if self.authenticated():
                self.send_bytes(200, (Path(__file__).parent / "assets" / "neural-network.png").read_bytes(), "image/png")
        elif self.path == "/api/model-info":
            if not self.authenticated():
                return
            try:
                result = self.server.backend_json("/api/show", {"model": self.server.config.model})
                self.reply(200, result)
            except (OSError, ValueError):
                self.reply(502, {"error": "모델 상세 정보를 조회할 수 없습니다."})
        elif self.path in {"/ready", "/api/ready"}:
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
        if not self.same_origin():
            return
        if self.path == "/api/restart":
            if not self.authenticated():
                return
            try:
                if self.read_json() != {}:
                    raise ValueError("Restart expects an empty JSON object")
            except (ValueError, UnicodeError, OSError) as exc:
                self.reply(400, {"error": str(exc)})
                return
            # The same lock prevents a new inference from starting after acceptance.
            if not self.server.inference.acquire(blocking=False):
                self.reply(409, {"error": "추론 또는 재시작이 진행 중입니다. 완료 후 다시 시도하세요."})
                return
            self.server.restart_requested.set()
            try:
                self.reply(202, {"restarting": True, "instance_id": self.server.instance_id})
                self.wfile.flush()
            finally:
                # shutdown must run outside serve_forever's main thread.
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path == "/api/session-login":
            try:
                data = self.read_json()
                user, password = data.get("user_id", ""), data.get("password", "")
                config = self.server.config
                if not isinstance(user, str) or not isinstance(password, str):
                    raise ValueError("User ID and password must be strings")
                if not (hmac.compare_digest(user.encode(), config.user.encode()) and
                        hmac.compare_digest(password.encode(), config.password.encode())):
                    self.reply(401, {"error": "아이디 또는 암호가 올바르지 않습니다."})
                    return
                token = secrets.token_urlsafe(32)
                with self.server.session_lock:
                    now = time.monotonic()
                    self.server.sessions = {k: v for k, v in self.server.sessions.items() if v[1] > now}
                    if len(self.server.sessions) >= 128:
                        self.server.sessions.pop(next(iter(self.server.sessions)))
                    self.server.sessions.pop(self.session_token(), None)
                    self.server.sessions[token] = (user, now + 28800)
                self.reply(200, {"logged_in": True, "user_id": user},
                           cookie=f"gemma_pi_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
            except (ValueError, UnicodeError, TimeoutError) as exc:
                self.reply(400, {"error": str(exc)})
            return
        if self.path == "/api/session-logout":
            with self.server.session_lock:
                self.server.sessions.pop(self.session_token(), None)
            self.reply(200, {"logged_in": False},
                       cookie="gemma_pi_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
            return
        if self.path not in {"/api/generate", "/api/chat", "/api/ocr"}:
            self.reply(404, {"error": "Not found"})
            return
        if not self.authenticated():
            return
        if not self.server.inference.acquire(blocking=False):
            self.reply(429, {"error": "Inference busy; retry after the current request completes"})
            return
        try:
            self.run_inference()
        finally:
            self.server.inference.release()

    def run_inference(self):
        request_started = time.monotonic()
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported")
            length = int(self.headers.get("Content-Length", "0"))
            limit = MAX_OCR_BODY if self.path == "/api/ocr" else 65536
            if not 0 < length <= limit:
                self.reply(413, {"error": f"JSON body must be 1 to {limit} bytes"})
                return
            receive_started = time.monotonic()
            body = self.rfile.read(length)
            received = time.monotonic()
            data = json.loads(body)
            del body
            payload = (ocr_payload(data, self.server.config) if self.path == "/api/ocr"
                       else generation_payload(data, self.path, self.server.config))
            prepared = time.monotonic()
        except ImportError:
            self.reply(503, {"error": "OCR 이미지 검증 모듈이 없습니다. sudo apt-get install python3-pil 실행 후 재시도하세요."})
            return
        except (ValueError, UnicodeError, OSError) as exc:
            self.reply(400, {"error": str(exc)})
            return
        try:
            started = time.monotonic()
            backend_path = "/api/chat" if self.path == "/api/ocr" else self.path
            engine = data.get("engine", "gemma") if self.path == "/api/ocr" else None
            if engine == "tesseract":
                execution_started = time.monotonic()
                result = tesseract_ocr(data["image"])
                execution_seconds = time.monotonic() - execution_started
                result["text"] = result["response"]
            else:
                if engine == "gemma":
                    info = self.server.backend_json("/api/show", {"model": self.server.config.model})
                    if not isinstance(info, dict):
                        raise ValueError("Invalid model information")
                    if "vision" not in info.get("capabilities", []):
                        self.reply(422, {"error": "선택 모델은 이미지 OCR을 지원하지 않습니다."})
                        return
                execution_started = time.monotonic()
                result = self.server.backend_json(backend_path, payload, self.server.config.timeout)
                execution_seconds = time.monotonic() - execution_started
            if not isinstance(result, dict):
                raise ValueError("Invalid backend response")
            if engine == "gemma" and "error" not in result:
                message = result.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                    raise ValueError("Missing OCR text in backend response")
                result["text"] = message["content"]
                result["response"] = message["content"]
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            result["requested_model"] = result["model"] if engine == "tesseract" else self.server.config.model
            if engine:
                result["engine"] = engine
                # Backend request wall time includes local HTTP/JSON overhead;
                # only Ollama's total_duration measures its own execution.
                duration = result.get("total_duration")
                llm_seconds = (round(duration / 1e9, 3)
                               if engine == "gemma" and type(duration) in (int, float)
                               and 0 <= duration < float("inf") else None)
                result["timings"] = {
                    "image_receive_seconds": round(received - receive_started, 3),
                    "image_prepare_seconds": round(prepared - received, 3),
                    "backend_request_seconds": round(execution_seconds, 3) if engine == "gemma" else None,
                    "llm_execution_seconds": llm_seconds,
                    "tesseract_execution_seconds": round(execution_seconds, 3) if engine == "tesseract" else None,
                    "server_total_seconds": round(time.monotonic() - request_started, 3),
                }
            self.reply(502 if "error" in result else 200, result)
        except urllib.error.HTTPError as exc:
            self.reply(502, {"error": ("Gemma 이미지 OCR 실패: 서버의 메모리와 Ollama 로그를 확인해 주세요."
                                       if self.path == "/api/ocr" else "Ollama inference failed"), "backend_status": exc.code,
                             "hint": "Check Ollama logs for model/version or insufficient memory errors"})
        except RuntimeError as exc:
            self.reply(503, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            self.reply(504, {"error": "Tesseract OCR timed out"})
        except (TimeoutError, socket.timeout):
            self.reply(504, {"error": "Ollama inference timed out"})
        except (OSError, ValueError):
            self.reply(502, {"error": "Ollama unavailable or invalid response"})


def print_startup_addresses(config):
    print(f"Gemma4 Pi: http://{config.host}:{config.port} model={config.model}", flush=True)
    addresses = local_ipv4_addresses()
    for address in addresses:
        print(f"LAN IP: http://{address}:{config.port}", flush=True)
    if not addresses:
        print("LAN IP: 192.168.* 또는 10.* 내부 주소가 없습니다.", flush=True)
    elif config.host != "0.0.0.0":
        print(
            f"현재 바인딩 주소: {config.host}. 모든 내부 IP로 접속하려면 "
            "config.env의 GEMMA4_SERVER_HOST=0.0.0.0 설정 후 재시작하세요.",
            flush=True,
        )


def main():
    config = Config()
    with Server((config.host, config.port), config) as server:
        print_startup_addresses(config)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    if server.restart_requested.is_set():
        if os.getenv("GEMMA4_MANAGED_LAUNCHER") == "1":
            return RESTART_EXIT_CODE
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
