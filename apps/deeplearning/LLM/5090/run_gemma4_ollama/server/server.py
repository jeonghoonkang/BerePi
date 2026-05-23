#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HOST = os.getenv("GEMMA4_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("GEMMA4_SERVER_PORT", "8082"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMMA4_REQUEST_TIMEOUT", "120"))
STARTED_AT = time.time()


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
      <h2>Prompt Test</h2>
      <textarea id="prompt">Reply with one short sentence that the Gemma4 Ollama service is running.</textarea>
      <div class="row">
        <button class="primary" id="send">Send to Gemma4</button>
        <span id="busy"></span>
      </div>
      <pre id="answer">Waiting for a prompt.</pre>
    </section>
  </main>

  <script>
    const metrics = document.getElementById("metrics");
    const answer = document.getElementById("answer");
    const busy = document.getElementById("busy");

    function metric(label, value, cls = "") {
      return `<div class="metric"><div class="label">${label}</div><div class="value ${cls}">${value}</div></div>`;
    }

    async function refreshStatus() {
      metrics.innerHTML = metric("Status", "Loading...");
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const modelClass = data.model_available ? "ok" : "warn";
        const ollamaClass = data.ollama_reachable ? "ok" : "bad";
        metrics.innerHTML = [
          metric("Web Server", `${data.host}:${data.port}`, "ok"),
          metric("Ollama", data.ollama_reachable ? "Reachable" : "Unavailable", ollamaClass),
          metric("Model", `${data.model} (${data.model_available ? "available" : "missing"})`, modelClass),
          metric("Uptime", data.uptime_seconds + "s"),
          metric("Ollama URL", data.ollama_base_url),
          metric("Known Models", data.models.length ? data.models.join(", ") : "None")
        ].join("");
      } catch (err) {
        metrics.innerHTML = metric("Status", String(err), "bad");
      }
    }

    async function sendPrompt() {
      busy.textContent = "Running...";
      answer.textContent = "";
      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompt: document.getElementById("prompt").value})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        answer.textContent = data.response || JSON.stringify(data, null, 2);
      } catch (err) {
        answer.textContent = String(err);
      } finally {
        busy.textContent = "";
        refreshStatus();
      }
    }

    document.getElementById("refresh").addEventListener("click", refreshStatus);
    document.getElementById("send").addEventListener("click", sendPrompt);
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


def model_matches(name: str, target: str) -> bool:
    return name == target or name == f"{target}:latest"


def status_payload() -> dict[str, Any]:
    models: list[str] = []
    ollama_reachable = False
    error = ""
    try:
        models = list_ollama_models()
        ollama_reachable = True
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        error = str(exc)

    return {
        "host": HOST,
        "port": PORT,
        "hostname": socket.gethostname(),
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_reachable": ollama_reachable,
        "ollama_error": error,
        "model": OLLAMA_MODEL,
        "model_available": any(model_matches(name, OLLAMA_MODEL) for name in models),
        "models": models,
        "uptime_seconds": int(time.time() - STARTED_AT),
    }


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
                "model": str(incoming.get("model") or OLLAMA_MODEL),
                "prompt": prompt,
                "stream": False,
            }
            result = request_json("/api/generate", payload=payload)
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
