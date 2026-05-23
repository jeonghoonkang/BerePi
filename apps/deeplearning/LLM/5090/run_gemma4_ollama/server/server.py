#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.getenv("GEMMA4_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("GEMMA4_SERVER_PORT", "8082"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")
OLLAMA_BIN = os.getenv("OLLAMA_BIN", "/usr/local/bin/ollama")
OLLAMA_PID_FILE = Path(os.getenv("OLLAMA_PID_FILE", Path(__file__).resolve().with_name("ollama.pid")))
GPU_SELECTION_FILE = Path(os.getenv("GPU_SELECTION_FILE", Path(__file__).resolve().with_name("gpu-selection")))
MODEL_SELECTION_FILE = Path(os.getenv("MODEL_SELECTION_FILE", Path(__file__).resolve().with_name("model-selection")))
LOG_DIR = Path(__file__).resolve().with_name("logs")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMMA4_REQUEST_TIMEOUT", "120"))
STARTED_AT = time.time()
PUBLIC_IP_URL = os.getenv("PUBLIC_IP_URL", "https://api.ipify.org")
PUBLIC_IP_CACHE_TTL_SECONDS = int(os.getenv("PUBLIC_IP_CACHE_TTL_SECONDS", "300"))
PUBLIC_IP_CACHE: dict[str, Any] = {"value": "", "checked_at": 0.0}


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemma4 Ollama Server</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #5d6b75;
      --line: #d9e0e5;
      --panel: #f6f8f9;
      --accent: #137c5b;
      --warn: #9b5a00;
      --bad: #a62f2f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }
    main {
      width: min(1040px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 42px;
    }
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    p { margin: 0; color: var(--muted); }
    button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      min-height: 38px;
      padding: 0 14px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
    }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    button.danger {
      color: #fff;
      background: var(--bad);
      border-color: var(--bad);
    }
    select {
      min-height: 38px;
      min-width: min(420px, 100%);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    section {
      margin-top: 24px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 86px;
      background: var(--panel);
    }
    .label {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }
    .value {
      font-size: 16px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .ok { color: var(--accent); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    textarea {
      width: 100%;
      min-height: 120px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: inherit;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #101820;
      color: #edf7f2;
      border-radius: 8px;
      padding: 14px;
      min-height: 96px;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    @media (max-width: 760px) {
      header { display: block; }
      header button { margin-top: 14px; }
      .grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 460px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Gemma4 Ollama Server</h1>
        <p>Port 8082 service page for checking Ollama and sending a quick Gemma4 prompt.</p>
      </div>
      <button id="refresh">Refresh</button>
    </header>

    <section class="grid" id="metrics"></section>

    <section>
      <h2>Service Controls</h2>
      <div class="row">
        <button class="primary" id="startOllama">Start Ollama Server</button>
        <button id="unload">Stop Model</button>
        <button class="danger" id="stopOllama">Stop Ollama Server</button>
        <span id="controlStatus"></span>
      </div>
    </section>

    <section>
      <h2>GPU Selection</h2>
      <div class="row">
        <select id="gpuSelect"></select>
        <button id="saveGpu">Save GPU Selection</button>
        <span id="gpuStatus"></span>
      </div>
    </section>

    <section>
      <h2>Model Selection</h2>
      <div class="row">
        <select id="modelSelect"></select>
        <button id="saveModel">Save Model Selection</button>
        <span id="modelStatus"></span>
      </div>
    </section>

    <section>
      <h2>Prompt Test</h2>
      <textarea id="prompt">Reply with one short sentence that the Gemma4 Ollama service is running.</textarea>
      <div class="row">
        <button class="primary" id="send">Send to Gemma4</button>
        <span id="busy"></span>
      </div>
      <pre id="answer">Waiting for a prompt.</pre>
    </section>

    <section>
      <h2>Python Client Code</h2>
      <pre id="pythonCode"></pre>
    </section>
  </main>

  <script>
    const metrics = document.getElementById("metrics");
    const answer = document.getElementById("answer");
    const busy = document.getElementById("busy");
    const controlStatus = document.getElementById("controlStatus");
    const gpuSelect = document.getElementById("gpuSelect");
    const gpuStatus = document.getElementById("gpuStatus");
    const modelSelect = document.getElementById("modelSelect");
    const modelStatus = document.getElementById("modelStatus");
    const pythonCode = document.getElementById("pythonCode");

    function metric(label, value, cls = "") {
      return `<div class="metric"><div class="label">${label}</div><div class="value ${cls}">${value}</div></div>`;
    }

    function gpuLabel(gpu) {
      const memory = gpu.memory_total_mb ? `, ${gpu.memory_total_mb} MB` : "";
      const bus = gpu.bus_address ? `, ${gpu.bus_address}` : "";
      const source = gpu.source === "lspci" ? "detected by lspci" : "CUDA";
      return `${gpu.index}: ${gpu.name}${memory}${bus} (${source})`;
    }

    function renderGpuOptions(data) {
      const selected = data.selected_gpu || "auto";
      const options = [
        {value: "auto", label: "Auto (all available GPUs)"},
        {value: "cpu", label: "CPU only"}
      ];
      for (const gpu of data.gpus || []) {
        if (gpu.selectable) options.push({value: String(gpu.index), label: gpuLabel(gpu)});
      }
      gpuSelect.innerHTML = options
        .map((option) => `<option value="${option.value}">${option.label}</option>`)
        .join("");
      gpuSelect.value = options.some((option) => option.value === selected) ? selected : "auto";
      gpuStatus.textContent = data.gpu_detection_error ? `GPU detection warning: ${data.gpu_detection_error}` : "";
    }

    function renderModelOptions(data) {
      const selected = data.model || "gemma4";
      const models = data.models && data.models.length ? data.models : [selected];
      modelSelect.innerHTML = models
        .map((model) => `<option value="${model}">${model}</option>`)
        .join("");
      if (!models.includes(selected)) {
        modelSelect.insertAdjacentHTML("afterbegin", `<option value="${selected}">${selected} (missing)</option>`);
      }
      modelSelect.value = selected;
      modelStatus.textContent = data.model_available ? "" : "Selected model is not installed.";
    }

    function renderPythonCode() {
      const serverUrl = window.location.origin;
      pythonCode.textContent = `#!/usr/bin/env python3
import json
import urllib.request
from time import perf_counter


SERVER_URL = "${serverUrl}"
PROMPT = "Reply with one short sentence that the Gemma4 Ollama service is running."


def send_prompt(prompt: str) -> tuple[str, float]:
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    request = urllib.request.Request(
        f"{SERVER_URL}/api/generate",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started_at = perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    elapsed_seconds = perf_counter() - started_at
    return data.get("response", json.dumps(data, ensure_ascii=False, indent=2)), elapsed_seconds


if __name__ == "__main__":
    response_text, elapsed_seconds = send_prompt(PROMPT)
    print(response_text)
    print(f"Elapsed time: {elapsed_seconds:.2f}s")
`;
    }

    async function refreshStatus() {
      metrics.innerHTML = metric("Status", "Loading...");
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const modelClass = data.model_available ? "ok" : "warn";
        const ollamaClass = data.ollama_reachable ? "ok" : "bad";
        metrics.innerHTML = [
          metric("Web Server", `${data.host}:${data.port}<br>Public IP: ${data.public_ip || "Unknown"}`, "ok"),
          metric("Ollama", data.ollama_reachable ? "Reachable" : "Unavailable", ollamaClass),
          metric("Model", `${data.model} (${data.model_available ? "available" : "missing"})`, modelClass),
          metric("Uptime", data.uptime_seconds + "s"),
          metric("Ollama URL", data.ollama_base_url),
          metric("Selected GPU", data.selected_gpu_label),
          metric("Known Models", data.models.length ? data.models.join(", ") : "None")
        ].join("");
        renderGpuOptions(data);
        renderModelOptions(data);
      } catch (err) {
        metrics.innerHTML = metric("Status", String(err), "bad");
      }
    }

    async function sendPrompt() {
      const startedAt = performance.now();
      busy.textContent = "Running...";
      answer.textContent = "";
      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompt: document.getElementById("prompt").value})
        });
        const data = await res.json();
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        if (!res.ok) throw new Error(data.error || "Request failed");
        const responseText = data.response || JSON.stringify(data, null, 2);
        answer.textContent = `${responseText}\n\nElapsed time: ${elapsedSeconds.toFixed(2)}s`;
        busy.textContent = `Done in ${elapsedSeconds.toFixed(2)}s`;
      } catch (err) {
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        answer.textContent = String(err);
        busy.textContent = `Failed after ${elapsedSeconds.toFixed(2)}s`;
        return;
      } finally {
        refreshStatus();
      }
    }

    async function postControl(path, label) {
      controlStatus.textContent = `${label}...`;
      try {
        const res = await fetch(path, {method: "POST"});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        controlStatus.textContent = data.message || `${label} done`;
      } catch (err) {
        controlStatus.textContent = String(err);
      } finally {
        refreshStatus();
      }
    }

    async function saveGpuSelection() {
      gpuStatus.textContent = "Saving...";
      try {
        const res = await fetch("/api/select-gpu", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({gpu: gpuSelect.value})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        gpuStatus.textContent = data.message || "GPU selection saved";
      } catch (err) {
        gpuStatus.textContent = String(err);
      } finally {
        refreshStatus();
      }
    }

    async function saveModelSelection() {
      modelStatus.textContent = "Saving...";
      try {
        const res = await fetch("/api/select-model", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({model: modelSelect.value})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        modelStatus.textContent = data.message || "Model selection saved";
      } catch (err) {
        modelStatus.textContent = String(err);
      } finally {
        refreshStatus();
      }
    }

    document.getElementById("refresh").addEventListener("click", refreshStatus);
    document.getElementById("send").addEventListener("click", sendPrompt);
    document.getElementById("startOllama").addEventListener("click", () => postControl("/api/start-ollama", "Starting Ollama"));
    document.getElementById("unload").addEventListener("click", () => postControl("/api/unload-model", "Stopping model"));
    document.getElementById("stopOllama").addEventListener("click", () => postControl("/api/stop-ollama", "Stopping Ollama"));
    document.getElementById("saveGpu").addEventListener("click", saveGpuSelection);
    document.getElementById("saveModel").addEventListener("click", saveModelSelection);
    renderPythonCode();
    refreshStatus();
  </script>
</body>
</html>
"""


def request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{OLLAMA_BASE_URL}{path}", data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_ollama_models() -> list[str]:
    data = request_json("/api/tags", timeout=5)
    return sorted(model.get("name", "") for model in data.get("models", []) if model.get("name"))


def normalize_model_selection(value: str) -> str:
    value = value.strip()
    if not value:
        return OLLAMA_MODEL
    return value


def read_selected_model() -> str:
    if "GEMMA4_SELECTED_MODEL" in os.environ:
        return normalize_model_selection(os.environ["GEMMA4_SELECTED_MODEL"])
    try:
        return normalize_model_selection(MODEL_SELECTION_FILE.read_text(encoding="utf-8").strip())
    except OSError:
        return normalize_model_selection(OLLAMA_MODEL)


def write_selected_model(value: str) -> str:
    selected = normalize_model_selection(value)
    MODEL_SELECTION_FILE.write_text(f"{selected}\n", encoding="utf-8")
    return selected


def list_gpus() -> tuple[list[dict[str, Any]], str]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,uuid",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        fallback_gpus = list_pci_gpus()
        error = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            error = exc.output.strip() or error
        return fallback_gpus, error

    gpus: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",", 3)]
        if len(parts) < 4:
            continue
        index, name, memory_total_mb, uuid = parts
        try:
            memory_value = int(memory_total_mb)
        except ValueError:
            memory_value = 0
        gpus.append(
            {
                "index": index,
                "name": name,
                "memory_total_mb": memory_value,
                "uuid": uuid,
                "source": "nvidia-smi",
                "selectable": True,
            }
        )
    return gpus, ""


def list_pci_gpus() -> list[dict[str, Any]]:
    try:
        output = subprocess.check_output(["lspci", "-D"], stderr=subprocess.DEVNULL, text=True, timeout=5)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []

    gpus: list[dict[str, Any]] = []
    for line in output.splitlines():
        lower = line.lower()
        if not any(marker in lower for marker in ("vga", "3d controller", "display controller")):
            continue
        address, _, description = line.partition(" ")
        gpus.append(
            {
                "index": str(len(gpus)),
                "name": description.strip(),
                "bus_address": address,
                "memory_total_mb": 0,
                "uuid": "",
                "source": "lspci",
                "selectable": "nvidia" in lower,
            }
        )
    return gpus


def read_selected_gpu() -> str:
    if "GEMMA4_SELECTED_GPU" in os.environ:
        return normalize_gpu_selection(os.environ["GEMMA4_SELECTED_GPU"])
    try:
        return normalize_gpu_selection(GPU_SELECTION_FILE.read_text(encoding="utf-8").strip())
    except OSError:
        return "auto"


def normalize_gpu_selection(value: str) -> str:
    value = value.strip().lower()
    if value in {"", "auto", "all"}:
        return "auto"
    if value in {"cpu", "none"}:
        return "cpu"
    if value.isdigit():
        return value
    return "auto"


def write_selected_gpu(value: str) -> str:
    selected = normalize_gpu_selection(value)
    GPU_SELECTION_FILE.write_text(f"{selected}\n", encoding="utf-8")
    return selected


def selected_gpu_label(selected: str, gpus: list[dict[str, Any]]) -> str:
    if selected == "auto":
        return "Auto (all available GPUs)"
    if selected == "cpu":
        return "CPU only"
    for gpu in gpus:
        if gpu.get("selectable") and str(gpu.get("index")) == selected:
            return f"GPU {selected}: {gpu.get('name')}"
    return f"GPU {selected}"


def ollama_environment() -> dict[str, str]:
    env = os.environ.copy()
    selected = read_selected_gpu()
    if selected == "auto":
        env.pop("CUDA_VISIBLE_DEVICES", None)
    elif selected == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = "-1"
    else:
        env["CUDA_VISIBLE_DEVICES"] = selected
    return env


def public_ip() -> str:
    now = time.time()
    cached_ip = str(PUBLIC_IP_CACHE.get("value") or "")
    checked_at = float(PUBLIC_IP_CACHE.get("checked_at") or 0)
    if cached_ip and now - checked_at < PUBLIC_IP_CACHE_TTL_SECONDS:
        return cached_ip

    try:
        with urllib.request.urlopen(PUBLIC_IP_URL, timeout=3) as response:
            ip = response.read().decode("utf-8").strip()
    except (OSError, urllib.error.URLError, TimeoutError):
        ip = ""

    PUBLIC_IP_CACHE["value"] = ip
    PUBLIC_IP_CACHE["checked_at"] = now
    return ip


def model_matches(name: str, target: str) -> bool:
    return name == target or name == f"{target}:latest"


def status_payload() -> dict[str, Any]:
    models: list[str] = []
    ollama_reachable = False
    error = ""
    gpus, gpu_detection_error = list_gpus()
    selected_gpu = read_selected_gpu()
    selected_model = read_selected_model()
    try:
        models = list_ollama_models()
        ollama_reachable = True
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        error = str(exc)

    return {
        "host": HOST,
        "port": PORT,
        "hostname": socket.gethostname(),
        "public_ip": public_ip(),
        "gpus": gpus,
        "gpu_detection_error": gpu_detection_error,
        "selected_gpu": selected_gpu,
        "selected_gpu_label": selected_gpu_label(selected_gpu, gpus),
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_reachable": ollama_reachable,
        "ollama_error": error,
        "model": selected_model,
        "default_model": OLLAMA_MODEL,
        "model_available": any(model_matches(name, selected_model) for name in models),
        "models": models,
        "uptime_seconds": int(time.time() - STARTED_AT),
    }


def unload_model() -> dict[str, Any]:
    return request_json("/api/generate", payload={"model": read_selected_model(), "keep_alive": 0, "stream": False}, timeout=30)


def ollama_is_reachable() -> bool:
    try:
        list_ollama_models()
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return True


def start_ollama_server() -> dict[str, Any]:
    if ollama_is_reachable():
        return {"ok": True, "message": "Ollama server is already running", "already_running": True}

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = (LOG_DIR / "ollama.log").open("ab")
    process = subprocess.Popen(
        [OLLAMA_BIN, "serve"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=ollama_environment(),
        start_new_session=True,
    )
    OLLAMA_PID_FILE.write_text(str(process.pid), encoding="utf-8")

    for _ in range(30):
        if ollama_is_reachable():
            return {"ok": True, "message": "Ollama server started", "pid": process.pid}
        time.sleep(1)

    return {"ok": False, "message": "Ollama server start timed out", "pid": process.pid}


def child_ollama_pids() -> list[int]:
    try:
        output = subprocess.check_output(["pgrep", "-P", str(os.getpid()), "-f", "ollama"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    pids: list[int] = []
    for line in output.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def known_ollama_pids() -> list[int]:
    pids: list[int] = []
    if OLLAMA_PID_FILE.exists():
        try:
            pids.append(int(OLLAMA_PID_FILE.read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            pass
    for pid in child_ollama_pids():
        if pid not in pids:
            pids.append(pid)
    return pids


def stop_ollama_server() -> dict[str, Any]:
    stopped: list[int] = []
    missing: list[int] = []
    for pid in known_ollama_pids():
        try:
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except ProcessLookupError:
            missing.append(pid)
        except PermissionError as exc:
            return {"ok": False, "message": f"Permission denied stopping Ollama PID {pid}", "error": str(exc)}
    try:
        OLLAMA_PID_FILE.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return {"ok": True, "stopped_pids": stopped, "missing_pids": missing}


class Gemma4Handler(BaseHTTPRequestHandler):
    server_version = "Gemma4OllamaServer/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            body = INDEX_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/health":
            self.send_json({"ok": True, **status_payload()})
            return
        if self.path == "/api/status":
            self.send_json(status_payload())
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/api/start-ollama":
            try:
                result = start_ollama_server()
            except OSError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_GATEWAY
            self.send_json(result, status)
            return

        if self.path == "/api/unload-model":
            try:
                result = unload_model()
            except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return
            self.send_json({"message": f"Model {read_selected_model()} stopped", "ollama": result})
            return

        if self.path == "/api/stop-ollama":
            try:
                try:
                    unload_model()
                except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                    pass
                result = stop_ollama_server()
            except OSError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return
            if not result.get("stopped_pids") and not result.get("missing_pids"):
                self.send_json({"message": "No Ollama PID found for this service", **result})
                return
            self.send_json({"message": "Ollama server stopped", **result})
            return

        if self.path == "/api/select-gpu":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                selected = write_selected_gpu(str(incoming.get("gpu", "auto")))
            except (OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(
                {
                    "message": "GPU selection saved. Restart Ollama to apply it.",
                    "selected_gpu": selected,
                }
            )
            return

        if self.path == "/api/select-model":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                selected = write_selected_model(str(incoming.get("model", OLLAMA_MODEL)))
            except (OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(
                {
                    "message": f"Model selection saved: {selected}",
                    "selected_model": selected,
                }
            )
            return

        if self.path != "/api/generate":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            prompt = str(incoming.get("prompt", "")).strip()
            if not prompt:
                self.send_json({"error": "prompt is required"}, HTTPStatus.BAD_REQUEST)
                return
            payload = {
                "model": str(incoming.get("model") or read_selected_model()),
                "prompt": prompt,
                "stream": False,
            }
            started_at = time.perf_counter()
            result = request_json("/api/generate", payload=payload)
            result["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
            self.send_json(result)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), Gemma4Handler)
    print(f"Gemma4 service page: http://{HOST}:{PORT}")
    print(f"Ollama backend: {OLLAMA_BASE_URL}, model={OLLAMA_MODEL}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
