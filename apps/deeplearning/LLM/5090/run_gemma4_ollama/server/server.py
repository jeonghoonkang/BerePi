#!/usr/bin/env python3
from __future__ import annotations

import json
import base64
import binascii
import hmac
import os
import re
import secrets
import signal
import socket
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.getenv("GEMMA4_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("GEMMA4_SERVER_PORT", "8082"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b")
OLLAMA_CONTEXT_LENGTH = os.getenv("OLLAMA_CONTEXT_LENGTH", "8192")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "60m")
OLLAMA_BIN = os.getenv("OLLAMA_BIN", "/usr/local/bin/ollama")
OLLAMA_PID_FILE = Path(os.getenv("OLLAMA_PID_FILE", Path(__file__).resolve().with_name("ollama.pid")))
GPU_SELECTION_FILE = Path(os.getenv("GPU_SELECTION_FILE", Path(__file__).resolve().with_name("gpu-selection")))
MODEL_SELECTION_FILE = Path(os.getenv("MODEL_SELECTION_FILE", Path(__file__).resolve().with_name("model-selection")))
PROMPT_HISTORY_FILE = Path(os.getenv("PROMPT_HISTORY_FILE", Path(__file__).resolve().with_name("prompt_history.txt")))
USER_PROMPT_HISTORY_FILE = Path(
  os.getenv("USER_PROMPT_HISTORY_FILE", Path(__file__).resolve().with_name("history_user_prompt.txt"))
)
API_KEY_CONF_FILE = Path(os.getenv("API_KEY_CONF_FILE", Path(__file__).resolve().with_name("api_key.conf")))
LOG_DIR = Path(__file__).resolve().with_name("logs")
WORKSPACE_DIR = Path(os.getenv("GEMMA4_SERVER_WORKSPACE_DIR", Path(__file__).resolve().with_name("workspace")))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMMA4_REQUEST_TIMEOUT", "120"))
STARTED_AT = time.time()
PUBLIC_IP_URL = os.getenv("PUBLIC_IP_URL", "https://api.ipify.org")
PUBLIC_IP_CACHE_TTL_SECONDS = int(os.getenv("PUBLIC_IP_CACHE_TTL_SECONDS", "300"))
PUBLIC_IP_CACHE: dict[str, Any] = {"value": "", "checked_at": 0.0}
PROMPT_HISTORY_LIMIT = 100
PROMPT_HISTORY_LOCK = threading.RLock()
USER_PROMPT_HISTORY_LIMIT = 2000
USER_PROMPT_HISTORY_LOCK = threading.RLock()
PROMPT_QUEUE_MAX_SIZE = int(os.getenv("PROMPT_QUEUE_MAX_SIZE", "10"))
PROMPT_QUEUE_CONDITION = threading.Condition()
PROMPT_QUEUE: list["PromptJob"] = []
PROMPT_QUEUE_ACTIVE = False
PROMPT_QUEUE_NEXT_ID = 1
SESSION_COOKIE_NAME = "gemma4_session"
SESSION_TTL_SECONDS = int(os.getenv("GEMMA4_SESSION_TTL_SECONDS", "28800"))
SESSION_LOCK = threading.RLock()
AUTH_SESSIONS: dict[str, dict[str, Any]] = {}


@dataclass
class PromptJob:
    id: int
    payload: dict[str, Any]
    enqueued_at: float = field(default_factory=time.time)
    cancelled: bool = False


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ollama Service - run_gemma4_ollama/server</title>
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
    .title-path {
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
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
    input {
      min-height: 38px;
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
    .prompt-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .prompt-box label {
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
      font-weight: 700;
    }
    .auth-box {
      display: grid;
      grid-template-columns: minmax(160px, 220px) minmax(160px, 220px);
      gap: 12px;
      align-items: end;
    }
    .auth-box label {
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
      font-weight: 700;
    }
    .auth-box input {
      width: 100%;
    }
    .session-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin: 12px 0;
    }
    .admin-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .check-label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }
    .check-label input {
      min-height: auto;
      width: 18px;
      height: 18px;
      margin: 0;
    }
    .prompt-box textarea {
      min-height: 150px;
    }
    .history-select {
      min-width: 0;
      width: 100%;
    }
    .history-row {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) max-content max-content;
      gap: 10px;
      align-items: center;
      margin-top: 10px;
    }
    .answer-box {
      white-space: normal;
      overflow-wrap: anywhere;
      background: #f1f3f5;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 96px;
      line-height: 1.5;
    }
    .answer-box p,
    .vision-output p {
      color: var(--ink);
      margin: 0 0 12px;
    }
    .answer-box p:last-child,
    .vision-output p:last-child {
      margin-bottom: 0;
    }
    .answer-box table,
    .vision-output table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 14px;
      background: #fff;
      table-layout: auto;
    }
    .answer-box th,
    .answer-box td,
    .vision-output th,
    .vision-output td {
      border: 1px solid #cfd6dc;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    .answer-box th,
    .vision-output th {
      background: #e5e9ed;
      font-weight: 700;
    }
    .answer-box code,
    .vision-output code {
      background: #e2e6ea;
      border-radius: 4px;
      padding: 1px 4px;
    }
    .answer-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 10px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    #pythonCode {
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
    .page-tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 18px;
      border-bottom: 1px solid var(--line);
    }
    .page-tab {
      border-bottom-left-radius: 0;
      border-bottom-right-radius: 0;
      border-bottom-color: transparent;
      min-width: 120px;
    }
    .page-tab.active {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .tab-panel {
      display: none;
    }
    .tab-panel.active {
      display: block;
    }
    .vision-grid {
      display: grid;
      grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
      gap: 14px;
      align-items: start;
    }
    .vision-preview {
      width: 100%;
      min-height: 240px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: var(--panel);
      display: grid;
      place-items: center;
      overflow: hidden;
    }
    .vision-preview img {
      width: 100%;
      height: auto;
      display: block;
    }
    .vision-output {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f1f3f5;
      border: 1px solid var(--line);
      border-radius: 8px;
      min-height: 180px;
      padding: 14px;
      line-height: 1.5;
    }
    .detection-plot {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      min-height: 260px;
      display: grid;
      place-items: center;
      overflow: hidden;
      position: relative;
    }
    .detection-plot canvas {
      width: 100%;
      height: auto;
      display: block;
    }
    @media (max-width: 760px) {
      header { display: block; }
      header button { margin-top: 14px; }
      .grid { grid-template-columns: 1fr 1fr; }
      .prompt-grid { grid-template-columns: 1fr; }
      .auth-box { grid-template-columns: 1fr; }
      .history-row { grid-template-columns: 1fr; }
      .vision-grid { grid-template-columns: 1fr; }
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
        <h1>Ollama Service by Local Download Model <span class="title-path">run_gemma4_ollama/server</span></h1>
        <p>Port 8082 service page for checking Ollama and sending a quick Gemma4 prompt.</p>
      </div>
      <button id="refresh">Refresh</button>
    </header>

    <nav class="page-tabs" aria-label="Service feature tabs">
      <button class="page-tab active" data-tab="serverPanel" type="button">Server</button>
      <button class="page-tab" data-tab="ocrPanel" type="button">OCR</button>
      <button class="page-tab" data-tab="yoloPanel" type="button">YOLO Detection</button>
    </nav>

    <div class="tab-panel active" id="serverPanel">
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
      <div class="auth-box">
        <div>
          <label for="userId">User ID</label>
          <input id="userId" autocomplete="username">
        </div>
        <div>
          <label for="password">Password</label>
          <input id="password" type="password" autocomplete="current-password">
        </div>
      </div>
      <div class="prompt-grid">
        <div class="prompt-box">
          <label for="prompt1">Prompt 1</label>
          <textarea id="prompt1">Reply with one short sentence that the Gemma4 Ollama service is running.</textarea>
        </div>
        <div class="prompt-box">
          <label for="prompt2">Prompt 2</label>
          <textarea id="prompt2"></textarea>
        </div>
      </div>
      <div class="row">
        <button class="primary" id="send">Send Prompt</button>
        <button id="cancelPendingPrompts">Cancel Pending Prompts</button>
        <span id="busy"></span>
      </div>
      <div class="history-row">
        <select class="history-select" id="promptHistory"></select>
        <button id="loadHistoryPrompt1">Load to Prompt 1</button>
        <button id="loadHistoryPrompt2">Load to Prompt 2</button>
      </div>
      <div class="answer-actions">
        <button id="copyAnswer">Copy Result</button>
        <span id="copyStatus"></span>
      </div>
      <div class="answer-box" id="answer">Waiting for a prompt.</div>
    </section>

    <section>
      <h2>User Account Management</h2>
      <p>Start a login session with an existing account. Saving a new User ID and Password is allowed only for that authenticated session.</p>
      <div class="session-row">
        <button id="loginSession">Login Session</button>
        <button id="logoutSession">Logout Session</button>
        <span id="sessionStatus">Session not started.</span>
      </div>
      <div class="admin-grid">
        <div>
          <label for="newUserId">New User ID</label>
          <input id="newUserId" autocomplete="off">
        </div>
        <div>
          <label for="newUserPassword">New Password</label>
          <input id="newUserPassword" type="password" autocomplete="new-password">
        </div>
      </div>
      <div class="row">
        <label class="check-label" for="newUserEnabled">
          <input id="newUserEnabled" type="checkbox" checked>
          Enabled
        </label>
        <button class="primary" id="saveUser">Save User ID / Password</button>
        <span id="saveUserStatus"></span>
      </div>
    </section>

    <section>
      <h2>Python Client Code</h2>
      <pre id="pythonCode"></pre>
    </section>
    </div>

    <section class="tab-panel" id="ocrPanel">
      <h2>OCR</h2>
      <p>../client OCR workflow: upload an image and extract readable text through the current Gemma4 vision model.</p>
      <div class="vision-grid">
        <div>
          <input id="ocrImage" type="file" accept="image/*">
          <div class="vision-preview" id="ocrPreview">No image selected.</div>
          <div class="row">
            <button class="primary" id="runOcr">Run OCR</button>
            <span id="ocrStatus"></span>
          </div>
        </div>
        <div>
          <textarea id="ocrPrompt">Extract all readable text from this image. Preserve line breaks where useful. If the image contains Korean text, return Korean text as accurately as possible.</textarea>
          <div class="answer-actions">
            <button id="copyOcr">Copy OCR Result</button>
            <span id="copyOcrStatus"></span>
          </div>
          <div class="vision-output" id="ocrOutput">Waiting for OCR.</div>
        </div>
      </div>
    </section>

    <section class="tab-panel" id="yoloPanel">
      <h2>YOLO Detection</h2>
      <p>../client YOLO detection workflow: upload an image and ask the current model for object-detection style results.</p>
      <div class="vision-grid">
        <div>
          <input id="yoloImage" type="file" accept="image/*">
          <div class="vision-preview" id="yoloPreview">No image selected.</div>
          <div class="row">
            <button class="primary" id="runYolo">Run Detection</button>
            <span id="yoloStatus"></span>
          </div>
        </div>
        <div>
          <textarea id="yoloPrompt">Analyze this image like an object detector. Return only concise JSON. Use this schema: {"objects":[{"label":"object name","count":1,"confidence":0.0,"bbox":{"x":0.0,"y":0.0,"width":0.0,"height":0.0},"location":"short phrase"}],"summary":"short summary"}. bbox values must be normalized 0.0 to 1.0 relative to image width and height.</textarea>
          <div class="answer-actions">
            <button id="copyYolo">Copy Detection Result</button>
            <span id="copyYoloStatus"></span>
          </div>
          <div class="vision-output" id="yoloOutput">Waiting for detection.</div>
          <div class="detection-plot" id="yoloPlot">Detection box plot will appear here.</div>
        </div>
      </div>
    </section>
  </main>

  <script>
    const metrics = document.getElementById("metrics");
    const answer = document.getElementById("answer");
    const busy = document.getElementById("busy");
    const copyStatus = document.getElementById("copyStatus");
    const sendButton = document.getElementById("send");
    const copyAnswerButton = document.getElementById("copyAnswer");
    const controlStatus = document.getElementById("controlStatus");
    const gpuSelect = document.getElementById("gpuSelect");
    const gpuStatus = document.getElementById("gpuStatus");
    const modelSelect = document.getElementById("modelSelect");
    const modelStatus = document.getElementById("modelStatus");
    const pythonCode = document.getElementById("pythonCode");
    const userId = document.getElementById("userId");
    const password = document.getElementById("password");
    const prompt1 = document.getElementById("prompt1");
    const prompt2 = document.getElementById("prompt2");
    const promptHistory = document.getElementById("promptHistory");
    const loginSessionButton = document.getElementById("loginSession");
    const logoutSessionButton = document.getElementById("logoutSession");
    const sessionStatus = document.getElementById("sessionStatus");
    const newUserId = document.getElementById("newUserId");
    const newUserPassword = document.getElementById("newUserPassword");
    const newUserEnabled = document.getElementById("newUserEnabled");
    const saveUserButton = document.getElementById("saveUser");
    const saveUserStatus = document.getElementById("saveUserStatus");
    const pageTabs = Array.from(document.querySelectorAll(".page-tab"));
    const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
    const ocrImage = document.getElementById("ocrImage");
    const ocrPreview = document.getElementById("ocrPreview");
    const ocrPrompt = document.getElementById("ocrPrompt");
    const ocrOutput = document.getElementById("ocrOutput");
    const ocrStatus = document.getElementById("ocrStatus");
    const copyOcrStatus = document.getElementById("copyOcrStatus");
    const yoloImage = document.getElementById("yoloImage");
    const yoloPreview = document.getElementById("yoloPreview");
    const yoloPrompt = document.getElementById("yoloPrompt");
    const yoloOutput = document.getElementById("yoloOutput");
    const yoloStatus = document.getElementById("yoloStatus");
    const copyYoloStatus = document.getElementById("copyYoloStatus");
    const yoloPlot = document.getElementById("yoloPlot");

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
      const selected = data.model || "gemma4:31b";
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
import base64
from time import perf_counter


SERVER_URL = "${serverUrl}"
USER_ID = "admin"
PASSWORD = "change-me-now"
PROMPT = "Reply with one short sentence that the Gemma4 Ollama service is running."


def send_prompt(prompt: str) -> tuple[dict, float]:
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    token = base64.b64encode(f"{USER_ID}:{PASSWORD}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{SERVER_URL}/api/generate",
        data=payload,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started_at = perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    elapsed_seconds = perf_counter() - started_at
    return data, elapsed_seconds


if __name__ == "__main__":
    data, elapsed_seconds = send_prompt(PROMPT)
    print(data.get("response", json.dumps(data, ensure_ascii=False, indent=2)))
    print(
        f"Elapsed time: {elapsed_seconds:.2f}s | "
        f"Model: {data.get('model', 'unknown')} | "
        f"IP: {data.get('server_ip', 'unknown')} | "
        f"Port: {data.get('server_port', 'unknown')}"
    )
`;
    }

    function promptPreview(prompt) {
      const singleLine = prompt.replace(/\\s+/g, " ").trim();
      return singleLine.length > 90 ? `${singleLine.slice(0, 90)}...` : singleLine;
    }

    function escapeHtml(value) {
      return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function renderInlineMarkdown(value) {
      return escapeHtml(value)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
    }

    function splitMarkdownTableRow(line) {
      let value = line.trim();
      if (value.startsWith("|")) value = value.slice(1);
      if (value.endsWith("|")) value = value.slice(0, -1);
      return value.split("|").map((cell) => cell.trim());
    }

    function isMarkdownTableSeparator(line) {
      const cells = splitMarkdownTableRow(line);
      return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
    }

    function renderMarkdownTable(lines, startIndex) {
      if (startIndex + 1 >= lines.length || !isMarkdownTableSeparator(lines[startIndex + 1])) {
        return null;
      }

      const headers = splitMarkdownTableRow(lines[startIndex]);
      const rows = [];
      let index = startIndex + 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        rows.push(splitMarkdownTableRow(lines[index]));
        index += 1;
      }

      const thead = `<thead><tr>${headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>`;
      const tbody = rows.length
        ? `<tbody>${rows.map((row) => `<tr>${headers.map((_, cellIndex) => `<td>${renderInlineMarkdown(row[cellIndex] || "")}</td>`).join("")}</tr>`).join("")}</tbody>`
        : "";
      return {html: `<table>${thead}${tbody}</table>`, nextIndex: index};
    }

    function renderMarkdown(value) {
      const lines = value.split(/\\r?\\n/);
      const blocks = [];
      let paragraph = [];

      function flushParagraph() {
        if (!paragraph.length) return;
        blocks.push(`<p>${paragraph.map(renderInlineMarkdown).join("<br>")}</p>`);
        paragraph = [];
      }

      for (let index = 0; index < lines.length;) {
        const line = lines[index];
        const table = renderMarkdownTable(lines, index);
        if (table) {
          flushParagraph();
          blocks.push(table.html);
          index = table.nextIndex;
          continue;
        }

        if (!line.trim()) {
          flushParagraph();
          index += 1;
          continue;
        }

        paragraph.push(line);
        index += 1;
      }

      flushParagraph();
      return blocks.join("");
    }

    function setAnswerMarkdown(value) {
      answer.innerHTML = renderMarkdown(value);
    }

    function setPanelMarkdown(panel, value) {
      panel.innerHTML = renderMarkdown(value);
    }

    async function copyText(value) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }

    async function copyAnswer() {
      const value = answer.innerText.trim();
      if (!value || value === "Waiting for a prompt.") {
        copyStatus.textContent = "No result to copy.";
        return;
      }
      try {
        await copyText(value);
        copyStatus.textContent = "Copied.";
      } catch (err) {
        copyStatus.textContent = `Copy failed: ${err}`;
      }
    }

    function showTab(panelId) {
      for (const tab of pageTabs) {
        tab.classList.toggle("active", tab.dataset.tab === panelId);
      }
      for (const panel of tabPanels) {
        panel.classList.toggle("active", panel.id === panelId);
      }
    }

    function imagePayloadFromFile(file) {
      return new Promise((resolve, reject) => {
        if (!file) {
          reject(new Error("Image file is required."));
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = String(reader.result || "");
          const base64Image = dataUrl.includes(",") ? dataUrl.split(",", 2)[1] : dataUrl;
          resolve({dataUrl, base64Image});
        };
        reader.onerror = () => reject(reader.error || new Error("Image read failed."));
        reader.readAsDataURL(file);
      });
    }

    async function previewImage(input, preview) {
      try {
        const file = input.files && input.files[0];
        if (!file) {
          preview.textContent = "No image selected.";
          return;
        }
        const {dataUrl} = await imagePayloadFromFile(file);
        preview.innerHTML = `<img src="${dataUrl}" alt="${escapeHtml(file.name)}">`;
      } catch (err) {
        preview.textContent = String(err);
      }
    }

    function extractJsonObject(value) {
      const text = String(value || "").trim();
      if (!text) return null;
      const fenced = text.match(/```(?:json)?\\s*([\\s\\S]*?)```/i);
      const candidate = fenced ? fenced[1].trim() : text;
      try {
        return JSON.parse(candidate);
      } catch (_) {
        const start = candidate.indexOf("{");
        const end = candidate.lastIndexOf("}");
        if (start >= 0 && end > start) {
          try {
            return JSON.parse(candidate.slice(start, end + 1));
          } catch (_) {
            return null;
          }
        }
      }
      return null;
    }

    function normalizedBox(box) {
      if (!box || typeof box !== "object") return null;
      const x = Number(box.x);
      const y = Number(box.y);
      const width = Number(box.width ?? box.w);
      const height = Number(box.height ?? box.h);
      if (![x, y, width, height].every(Number.isFinite)) return null;
      return {
        x: Math.max(0, Math.min(1, x)),
        y: Math.max(0, Math.min(1, y)),
        width: Math.max(0, Math.min(1, width)),
        height: Math.max(0, Math.min(1, height))
      };
    }

    function collectDetectionObjects(data) {
      const rawObjects = Array.isArray(data?.objects) ? data.objects : [];
      return rawObjects
        .map((item) => ({...item, bbox: normalizedBox(item.bbox || item.box)}))
        .filter((item) => item.bbox);
    }

    async function drawDetectionPlot(file, responseText) {
      const parsed = extractJsonObject(responseText);
      const objects = collectDetectionObjects(parsed);
      if (!file) {
        yoloPlot.textContent = "Select an image before drawing detection boxes.";
        return;
      }
      if (!objects.length) {
        yoloPlot.textContent = "No normalized bbox values were found in the JSON response.";
        return;
      }

      const {dataUrl} = await imagePayloadFromFile(file);
      const image = new Image();
      image.onload = () => {
        const maxWidth = 1000;
        const scale = Math.min(1, maxWidth / image.naturalWidth);
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        context.drawImage(image, 0, 0, width, height);
        context.lineWidth = Math.max(2, Math.round(width / 320));
        context.font = `${Math.max(13, Math.round(width / 52))}px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif`;
        context.textBaseline = "top";

        objects.forEach((object, index) => {
          const color = ["#137c5b", "#a62f2f", "#255f99", "#9b5a00", "#6d4ca3"][index % 5];
          const box = object.bbox;
          const x = box.x * width;
          const y = box.y * height;
          const boxWidth = box.width * width;
          const boxHeight = box.height * height;
          const label = `${object.label || "object"}${object.confidence ? ` ${Number(object.confidence).toFixed(2)}` : ""}`;
          const textWidth = context.measureText(label).width + 10;
          const textHeight = Math.max(20, Math.round(width / 36));

          context.strokeStyle = color;
          context.fillStyle = color;
          context.strokeRect(x, y, boxWidth, boxHeight);
          context.fillRect(x, Math.max(0, y - textHeight), Math.min(textWidth, width - x), textHeight);
          context.fillStyle = "#fff";
          context.fillText(label, x + 5, Math.max(0, y - textHeight + 3));
        });

        yoloPlot.innerHTML = "";
        yoloPlot.appendChild(canvas);
      };
      image.onerror = () => {
        yoloPlot.textContent = "Image preview failed; cannot draw boxes.";
      };
      image.src = dataUrl;
    }

    async function runVisionTask({input, promptInput, output, status, label, afterResult}) {
      const startedAt = performance.now();
      status.textContent = `${label} running...`;
      output.textContent = `${label} running...`;
      try {
        const auth = authPayload();
        if (!auth.user_id || !auth.password) {
          throw new Error("User ID and password are required in the Server tab.");
        }
        const file = input.files && input.files[0];
        const {base64Image} = await imagePayloadFromFile(file);
        const prompt = promptInput.value.trim();
        if (!prompt) {
          throw new Error("Prompt is required.");
        }
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            prompt,
            images: [base64Image],
            model: modelSelect.value,
            ...auth
          })
        });
        const data = await res.json();
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        if (!res.ok) throw new Error(data.error || "Request failed");
        const responseText = data.response || JSON.stringify(data, null, 2);
        setPanelMarkdown(output, `${responseText}\n\n${resultLine(data, elapsedSeconds)}`);
        status.textContent = `Done in ${elapsedSeconds.toFixed(2)}s`;
        if (afterResult) {
          await afterResult(file, responseText);
        }
      } catch (err) {
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        setPanelMarkdown(output, String(err));
        status.textContent = `Failed after ${elapsedSeconds.toFixed(2)}s`;
      } finally {
        refreshStatus();
      }
    }

    async function copyPanelText(output, status) {
      const value = output.innerText.trim();
      if (!value || value.startsWith("Waiting for")) {
        status.textContent = "No result to copy.";
        return;
      }
      try {
        await copyText(value);
        status.textContent = "Copied.";
      } catch (err) {
        status.textContent = `Copy failed: ${err}`;
      }
    }

    function authPayload() {
      return {
        user_id: userId.value.trim(),
        password: password.value
      };
    }

    function resultLine(data, elapsedSeconds) {
      const model = data.model || modelSelect.value || "unknown";
      const ip = data.server_ip || window.location.hostname || "unknown";
      const port = data.server_port || window.location.port || "unknown";
      return `Elapsed time: ${elapsedSeconds.toFixed(2)}s | Model: ${model} | IP: ${ip} | Port: ${port}`;
    }

    function formatRunStartedAt(date) {
      return date.toLocaleTimeString([], {hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit"});
    }

    async function refreshPromptHistory() {
      try {
        const res = await fetch("/api/prompt-history");
        const data = await res.json();
        const history = data.history || [];
        promptHistory.innerHTML = history.length
          ? history.map((prompt, index) => `<option value="${index}">${escapeHtml(promptPreview(prompt))}</option>`).join("")
          : `<option value="">No prompt history</option>`;
        promptHistory.dataset.history = JSON.stringify(history);
        promptHistory.disabled = history.length === 0;
      } catch (err) {
        promptHistory.innerHTML = `<option value="">Prompt history unavailable</option>`;
        promptHistory.dataset.history = "[]";
        promptHistory.disabled = true;
      }
    }

    function loadHistory(target) {
      const history = JSON.parse(promptHistory.dataset.history || "[]");
      const index = Number(promptHistory.value);
      if (!history[index]) return;
      target.value = history[index];
      target.focus();
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
          metric("Keep Alive", data.keep_alive || "default"),
          metric("Context", data.context_length || "default"),
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
      const startedDate = new Date();
      const sendButtonLabel = sendButton.textContent;
      let busyTimer = null;
      function updateBusy() {
        const elapsedSeconds = Math.floor((performance.now() - startedAt) / 1000);
        const message = `Running... started ${formatRunStartedAt(startedDate)} | elapsed ${elapsedSeconds}s`;
        busy.textContent = message;
        sendButton.textContent = "Running...";
        answer.textContent = message;
      }
      const prompts = [prompt1.value, prompt2.value].map((value) => value.trim()).filter(Boolean);
      sendButton.disabled = true;
      copyStatus.textContent = "";
      updateBusy();
      busyTimer = window.setInterval(updateBusy, 1000);
      try {
        const auth = authPayload();
        if (!auth.user_id || !auth.password) {
          throw new Error("User ID and password are required.");
        }
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompts, ...auth})
        });
        const data = await res.json();
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        if (!res.ok) throw new Error(data.error || "Request failed");
        const responseText = data.response || JSON.stringify(data, null, 2);
        setAnswerMarkdown(`${responseText}\n\n${resultLine(data, elapsedSeconds)}`);
        busy.textContent = `Done in ${elapsedSeconds.toFixed(2)}s`;
      } catch (err) {
        const elapsedSeconds = (performance.now() - startedAt) / 1000;
        setAnswerMarkdown(String(err));
        busy.textContent = `Failed after ${elapsedSeconds.toFixed(2)}s`;
        return;
      } finally {
        if (busyTimer) window.clearInterval(busyTimer);
        sendButton.disabled = false;
        sendButton.textContent = sendButtonLabel;
        refreshPromptHistory();
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

    async function cancelPendingPrompts() {
      busy.textContent = "Cancelling pending prompts...";
      try {
        const auth = authPayload();
        if (!auth.user_id || !auth.password) {
          throw new Error("User ID and password are required.");
        }
        const res = await fetch("/api/cancel-pending-prompts", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(auth)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        busy.textContent = data.message || "Pending prompts cancelled";
      } catch (err) {
        busy.textContent = String(err);
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

    function setSessionState(data) {
      const loggedIn = Boolean(data && data.logged_in);
      saveUserButton.disabled = !loggedIn;
      logoutSessionButton.disabled = !loggedIn;
      loginSessionButton.disabled = false;
      sessionStatus.textContent = loggedIn
        ? `Logged in as ${data.user_id || "unknown"}`
        : "Session not started.";
    }

    async function refreshSessionStatus() {
      try {
        const res = await fetch("/api/session-status");
        const data = await res.json();
        setSessionState(data);
      } catch (err) {
        saveUserButton.disabled = true;
        logoutSessionButton.disabled = true;
        sessionStatus.textContent = `Session status unavailable: ${err}`;
      }
    }

    async function loginSession() {
      sessionStatus.textContent = "Starting session...";
      try {
        const auth = authPayload();
        if (!auth.user_id || !auth.password) {
          throw new Error("User ID and password are required.");
        }
        const res = await fetch("/api/session-login", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(auth)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Login failed");
        setSessionState(data);
      } catch (err) {
        saveUserButton.disabled = true;
        logoutSessionButton.disabled = true;
        sessionStatus.textContent = String(err);
      }
    }

    async function logoutSession() {
      sessionStatus.textContent = "Ending session...";
      try {
        const res = await fetch("/api/session-logout", {method: "POST"});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Logout failed");
      } catch (err) {
        sessionStatus.textContent = String(err);
        return;
      }
      newUserPassword.value = "";
      saveUserStatus.textContent = "";
      refreshSessionStatus();
    }

    async function saveUser() {
      saveUserStatus.textContent = "Saving...";
      try {
        const nextUserId = newUserId.value.trim();
        const nextPassword = newUserPassword.value;
        if (!nextUserId || !nextPassword) {
          throw new Error("New User ID and Password are required.");
        }
        const res = await fetch("/api/save-user", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            new_user_id: nextUserId,
            new_password: nextPassword,
            enabled: Boolean(newUserEnabled.checked)
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Save failed");
        saveUserStatus.textContent = data.message || "User saved";
        newUserPassword.value = "";
      } catch (err) {
        saveUserStatus.textContent = String(err);
      }
    }

    document.getElementById("refresh").addEventListener("click", refreshStatus);
    pageTabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
    sendButton.addEventListener("click", sendPrompt);
    copyAnswerButton.addEventListener("click", copyAnswer);
    ocrImage.addEventListener("change", () => previewImage(ocrImage, ocrPreview));
    yoloImage.addEventListener("change", () => previewImage(yoloImage, yoloPreview));
    document.getElementById("runOcr").addEventListener("click", () => runVisionTask({
      input: ocrImage,
      promptInput: ocrPrompt,
      output: ocrOutput,
      status: ocrStatus,
      label: "OCR"
    }));
    document.getElementById("runYolo").addEventListener("click", () => runVisionTask({
      input: yoloImage,
      promptInput: yoloPrompt,
      output: yoloOutput,
      status: yoloStatus,
      label: "Detection",
      afterResult: drawDetectionPlot
    }));
    document.getElementById("copyOcr").addEventListener("click", () => copyPanelText(ocrOutput, copyOcrStatus));
    document.getElementById("copyYolo").addEventListener("click", () => copyPanelText(yoloOutput, copyYoloStatus));
    document.getElementById("loadHistoryPrompt1").addEventListener("click", () => loadHistory(prompt1));
    document.getElementById("loadHistoryPrompt2").addEventListener("click", () => loadHistory(prompt2));
    document.getElementById("startOllama").addEventListener("click", () => postControl("/api/start-ollama", "Starting Ollama"));
    document.getElementById("unload").addEventListener("click", () => postControl("/api/unload-model", "Stopping model"));
    document.getElementById("stopOllama").addEventListener("click", () => postControl("/api/stop-ollama", "Stopping Ollama"));
    document.getElementById("cancelPendingPrompts").addEventListener("click", cancelPendingPrompts);
    document.getElementById("saveGpu").addEventListener("click", saveGpuSelection);
    document.getElementById("saveModel").addEventListener("click", saveModelSelection);
    loginSessionButton.addEventListener("click", loginSession);
    logoutSessionButton.addEventListener("click", logoutSession);
    saveUserButton.addEventListener("click", saveUser);
    renderPythonCode();
    refreshPromptHistory();
    refreshStatus();
    refreshSessionStatus();
  </script>
</body>
</html>
"""


DEFAULT_API_KEY_CONF = {
    "enabled": True,
    "allow_only_user": "",
    "users": [
        {"id": "admin", "password": "change-me-now", "enabled": True},
        {"id": "operator", "password": "change-me-too", "enabled": True},
    ],
}


def ensure_api_key_conf() -> None:
    if API_KEY_CONF_FILE.exists():
        return
    API_KEY_CONF_FILE.write_text(
        json.dumps(DEFAULT_API_KEY_CONF, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        API_KEY_CONF_FILE.chmod(0o600)
    except OSError:
        pass


def read_api_key_conf() -> dict[str, Any]:
    ensure_api_key_conf()
    try:
        data = json.loads(API_KEY_CONF_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": True, "allow_only_user": "__invalid_config__", "users": []}
    return data if isinstance(data, dict) else {"enabled": True, "users": []}


def write_api_key_conf(conf: dict[str, Any]) -> None:
  API_KEY_CONF_FILE.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  try:
    API_KEY_CONF_FILE.chmod(0o600)
  except OSError:
    pass


def valid_user_records(conf: dict[str, Any]) -> list[dict[str, Any]]:
    users = conf.get("users")
    return [user for user in users if isinstance(user, dict)] if isinstance(users, list) else []


def matched_authorized_user_id(user_id: str, password: str) -> str:
    conf = read_api_key_conf()
    allow_only_user = str(conf.get("allow_only_user") or "").strip()
    for user in valid_user_records(conf):
        configured_id = str(user.get("id") or "")
        configured_password = str(user.get("password") or "")
        if not user.get("enabled", True):
            continue
        if allow_only_user and configured_id != allow_only_user:
            continue
        if hmac.compare_digest(configured_id, user_id) and hmac.compare_digest(configured_password, password):
            return configured_id
    return ""


def is_authorized_user(user_id: str, password: str) -> bool:
  conf = read_api_key_conf()
  if conf.get("enabled") is False:
    return True
  return bool(matched_authorized_user_id(user_id, password))


def parse_basic_auth(header_value: str) -> tuple[str, str]:
    prefix = "Basic "
    if not header_value.startswith(prefix):
        return "", ""
    try:
        decoded = base64.b64decode(header_value[len(prefix) :], validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return "", ""
    user_id, separator, password = decoded.partition(":")
    if not separator:
        return "", ""
    return user_id, password


def credentials_from_request(headers: Any, incoming: dict[str, Any]) -> tuple[str, str]:
    user_id, password = parse_basic_auth(str(headers.get("Authorization", "")))
    if user_id or password:
        return user_id, password
    return str(incoming.get("user_id") or incoming.get("username") or ""), str(incoming.get("password") or "")


def sanitize_user_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._@-]+", "", str(value or "").strip())[:64]


def sanitize_password(value: str) -> str:
    return str(value or "").strip()[:256]


def upsert_api_user(user_id: str, password: str, enabled: bool = True) -> dict[str, Any]:
    normalized_user_id = sanitize_user_id(user_id)
    normalized_password = sanitize_password(password)
    if not normalized_user_id:
        raise ValueError("new_user_id is required")
    if not normalized_password:
        raise ValueError("new_password is required")

    conf = read_api_key_conf()
    users = valid_user_records(conf)
    updated = False
    next_users: list[dict[str, Any]] = []
    for user in users:
        configured_id = str(user.get("id") or "")
        if configured_id == normalized_user_id:
            next_users.append({"id": normalized_user_id, "password": normalized_password, "enabled": enabled})
            updated = True
            continue
        next_users.append(
            {
                "id": configured_id,
                "password": str(user.get("password") or ""),
                "enabled": bool(user.get("enabled", True)),
            }
        )

    if not updated:
        next_users.append({"id": normalized_user_id, "password": normalized_password, "enabled": enabled})

    conf["users"] = next_users
    write_api_key_conf(conf)
    return {"id": normalized_user_id, "enabled": enabled, "updated": updated}


def cleanup_expired_sessions() -> None:
    now = time.time()
    expired = [token for token, session in AUTH_SESSIONS.items() if float(session.get("expires_at") or 0) <= now]
    for token in expired:
        AUTH_SESSIONS.pop(token, None)


def create_auth_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with SESSION_LOCK:
        cleanup_expired_sessions()
        AUTH_SESSIONS[token] = {
            "user_id": user_id,
            "expires_at": time.time() + SESSION_TTL_SECONDS,
        }
    return token


def parse_cookie_header(header_value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in str(header_value or "").split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name:
            cookies[name] = value
    return cookies


def session_cookie_value(token: str, *, expired: bool = False) -> str:
    if expired:
        return f"{SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
    return f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}"


def authenticated_session_user(headers: Any) -> str:
    cookies = parse_cookie_header(str(headers.get("Cookie", "")))
    token = cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        return ""
    with SESSION_LOCK:
        cleanup_expired_sessions()
        session = AUTH_SESSIONS.get(token)
        if not session:
            return ""
        session["expires_at"] = time.time() + SESSION_TTL_SECONDS
        return str(session.get("user_id") or "")


def clear_auth_session(headers: Any) -> None:
    cookies = parse_cookie_header(str(headers.get("Cookie", "")))
    token = cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        return
    with SESSION_LOCK:
        AUTH_SESSIONS.pop(token, None)


def read_prompt_history() -> list[str]:
    with PROMPT_HISTORY_LOCK:
        try:
            lines = PROMPT_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            PROMPT_HISTORY_FILE.touch()
            return []
        except OSError:
            return []

    prompts: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = line
        if isinstance(value, str) and value.strip():
            prompts.append(value.strip())
    return prompts[:PROMPT_HISTORY_LIMIT]


def save_prompt_history(prompts: list[str]) -> None:
    unique_prompts: list[str] = []
    seen: set[str] = set()
    for prompt in prompts:
        prompt = prompt.strip()
        if not prompt or prompt in seen:
            continue
        unique_prompts.append(prompt)
        seen.add(prompt)
        if len(unique_prompts) >= PROMPT_HISTORY_LIMIT:
            break

    body = "".join(f"{json.dumps(prompt, ensure_ascii=False)}\n" for prompt in unique_prompts)
    with PROMPT_HISTORY_LOCK:
        PROMPT_HISTORY_FILE.write_text(body, encoding="utf-8")


def remember_prompts(prompts: list[str]) -> None:
    cleaned = [prompt.strip() for prompt in prompts if prompt.strip()]
    if not cleaned:
        return

    with PROMPT_HISTORY_LOCK:
        existing = read_prompt_history()
        save_prompt_history(cleaned + existing)


def read_user_prompt_history() -> list[dict[str, str]]:
  with USER_PROMPT_HISTORY_LOCK:
    try:
      lines = USER_PROMPT_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
      USER_PROMPT_HISTORY_FILE.touch()
      return []
    except OSError:
      return []

  entries: list[dict[str, str]] = []
  for line in lines:
    line = line.strip()
    if not line:
      continue
    try:
      value = json.loads(line)
    except json.JSONDecodeError:
      continue
    if not isinstance(value, dict):
      continue
    requested_at = str(value.get("requested_at") or "").strip()
    user_id = str(value.get("user_id") or "").strip()
    prompt = str(value.get("prompt") or "").strip()
    if not requested_at or not user_id or not prompt:
      continue
    entries.append(
      {
        "requested_at": requested_at,
        "user_id": user_id,
        "prompt": prompt,
      }
    )
  return entries[-USER_PROMPT_HISTORY_LIMIT:]


def save_user_prompt_history(entries: list[dict[str, str]]) -> None:
  trimmed = entries[-USER_PROMPT_HISTORY_LIMIT:]
  body = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in trimmed)
  with USER_PROMPT_HISTORY_LOCK:
    USER_PROMPT_HISTORY_FILE.write_text(body, encoding="utf-8")


def remember_user_prompt(user_id: str, prompt: str, requested_at: float | None = None) -> None:
  cleaned_user_id = str(user_id or "").strip()
  cleaned_prompt = str(prompt or "").strip()
  if not cleaned_user_id or not cleaned_prompt:
    return

  timestamp = time.time() if requested_at is None else requested_at
  entry = {
    "requested_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
    "user_id": cleaned_user_id,
    "prompt": cleaned_prompt,
  }
  with USER_PROMPT_HISTORY_LOCK:
    existing = read_user_prompt_history()
    save_user_prompt_history(existing + [entry])


def ensure_workspace_dir() -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR


def sanitize_workspace_filename(name: str) -> str:
    raw = unicodedata.normalize("NFC", Path(str(name or "")).name)
    value = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]+', "_", raw).strip()
    value = value.strip(". ")
    return value[:180] if value else ""


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
        stat = path.stat()
        saved.append(
            {
                "name": path.name,
                "path": f"workspace/{path.name}",
                "absolute_path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            }
        )
    return saved


def combined_prompt_from_request(incoming: dict[str, Any]) -> tuple[str, list[str]]:
    raw_prompts = incoming.get("prompts")
    prompts: list[str] = []
    if isinstance(raw_prompts, list):
        prompts = [str(prompt).strip() for prompt in raw_prompts if str(prompt).strip()]
    else:
        prompt = str(incoming.get("prompt", "")).strip()
        if prompt:
            prompts = [prompt]

    return "\n\n".join(prompts), prompts


def images_from_request(incoming: dict[str, Any]) -> list[str]:
    raw_images = incoming.get("images")
    if raw_images is None:
        return []
    if not isinstance(raw_images, list):
        raise ValueError("images must be a list of base64-encoded image strings")

    images: list[str] = []
    for index, raw_image in enumerate(raw_images, start=1):
        image = str(raw_image or "").strip()
        if not image:
            continue
        try:
            base64.b64decode(image, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"images[{index}] is not valid base64: {exc}") from exc
        images.append(image)
    return images


def request_options(incoming: dict[str, Any]) -> dict[str, Any]:
    raw_options = incoming.get("options")
    options = dict(raw_options) if isinstance(raw_options, dict) else {}
    try:
        options.setdefault("num_ctx", int(OLLAMA_CONTEXT_LENGTH))
    except ValueError:
        pass
    return options


def request_keep_alive(incoming: dict[str, Any]) -> str | int:
    keep_alive = incoming.get("keep_alive", OLLAMA_KEEP_ALIVE)
    if isinstance(keep_alive, int):
        return keep_alive
    return str(keep_alive)


def request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{OLLAMA_BASE_URL}{path}", data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def prompt_queue_status() -> dict[str, Any]:
    with PROMPT_QUEUE_CONDITION:
        return {
            "active": PROMPT_QUEUE_ACTIVE,
            "pending_count": len(PROMPT_QUEUE),
            "max_pending_count": PROMPT_QUEUE_MAX_SIZE,
            "pending_prompt_ids": [job.id for job in PROMPT_QUEUE],
        }


def cancel_pending_prompts() -> dict[str, Any]:
    with PROMPT_QUEUE_CONDITION:
        cancelled_prompt_ids = [job.id for job in PROMPT_QUEUE]
        for job in PROMPT_QUEUE:
            job.cancelled = True
        PROMPT_QUEUE.clear()
        PROMPT_QUEUE_CONDITION.notify_all()

    cancelled_count = len(cancelled_prompt_ids)
    return {
        "message": f"Cancelled {cancelled_count} pending prompt(s).",
        "cancelled_count": cancelled_count,
        "cancelled_prompt_ids": cancelled_prompt_ids,
        "queue": prompt_queue_status(),
    }


def queue_full_response() -> dict[str, Any]:
    return {
        "response": (
            f"대기 중인 프롬프트가 {PROMPT_QUEUE_MAX_SIZE}개라 더 이상 처리하기 어렵습니다. "
            "잠시 기다린 뒤 다시 요청해 주세요."
        ),
        "queue_full": True,
        "queue": prompt_queue_status(),
    }


def cancelled_prompt_response(job: PromptJob) -> dict[str, Any]:
    return {
        "response": "대기 중이던 프롬프트가 취소되었습니다.",
        "cancelled": True,
        "prompt_queue_id": job.id,
        "queue": prompt_queue_status(),
    }


def run_ollama_generate(payload: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    result = request_json("/api/generate", payload=payload)
    result["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
    result["model"] = payload["model"]
    result["server_ip"] = server_ip()
    result["server_port"] = PORT
    result["elapsed_line"] = (
        f"Elapsed time: {result['elapsed_seconds']:.2f}s | "
        f"Model: {result['model']} | IP: {result['server_ip']} | Port: {result['server_port']}"
    )
    return result


def run_queued_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    global PROMPT_QUEUE_ACTIVE, PROMPT_QUEUE_NEXT_ID

    with PROMPT_QUEUE_CONDITION:
        if len(PROMPT_QUEUE) >= PROMPT_QUEUE_MAX_SIZE:
            return queue_full_response()

        job = PromptJob(id=PROMPT_QUEUE_NEXT_ID, payload=payload)
        PROMPT_QUEUE_NEXT_ID += 1
        PROMPT_QUEUE.append(job)
        PROMPT_QUEUE_CONDITION.notify_all()

        while True:
            if job.cancelled:
                return cancelled_prompt_response(job)
            if PROMPT_QUEUE and PROMPT_QUEUE[0] is job and not PROMPT_QUEUE_ACTIVE:
                PROMPT_QUEUE_ACTIVE = True
                PROMPT_QUEUE.pop(0)
                PROMPT_QUEUE_CONDITION.notify_all()
                break
            PROMPT_QUEUE_CONDITION.wait()

    try:
        result = run_ollama_generate(payload)
        result["prompt_queue_id"] = job.id
        result["queue_wait_seconds"] = round(time.time() - job.enqueued_at - result["elapsed_seconds"], 3)
        result["queue"] = prompt_queue_status()
        return result
    finally:
        with PROMPT_QUEUE_CONDITION:
            PROMPT_QUEUE_ACTIVE = False
            PROMPT_QUEUE_CONDITION.notify_all()


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


def cuda_device_for_gpu_selection(selected: str) -> str:
    gpus, _ = list_gpus()
    for gpu in gpus:
        if str(gpu.get("index")) == selected and gpu.get("uuid"):
            return str(gpu["uuid"])
    return selected


def ollama_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OLLAMA_CONTEXT_LENGTH", OLLAMA_CONTEXT_LENGTH)
    env.setdefault("OLLAMA_KEEP_ALIVE", OLLAMA_KEEP_ALIVE)
    selected = read_selected_gpu()
    if selected == "auto":
        env.pop("CUDA_VISIBLE_DEVICES", None)
    elif selected == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = "-1"
    else:
        env["CUDA_VISIBLE_DEVICES"] = cuda_device_for_gpu_selection(selected)
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


def server_ip() -> str:
    public = public_ip()
    if public:
        return public
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return HOST


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
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "context_length": OLLAMA_CONTEXT_LENGTH,
        "model_available": any(model_matches(name, selected_model) for name in models),
        "models": models,
        "prompt_queue": prompt_queue_status(),
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

    def send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_auth_error(self, message: str = "unauthorized") -> None:
        body = json.dumps({"error": message}, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", 'Basic realm="Gemma4 Prompt"')
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
        if self.path == "/api/prompt-history":
            self.send_json({"history": read_prompt_history()})
            return
        if self.path == "/api/session-status":
          user_id = authenticated_session_user(self.headers)
          self.send_json({"logged_in": bool(user_id), "user_id": user_id})
          return
        if self.path == "/api/workspace/files":
            self.send_json({"workspace_dir": str(ensure_workspace_dir()), "files": list_workspace_files()})
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

        if self.path == "/api/session-login":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                user_id, password = credentials_from_request(self.headers, incoming)
                matched_user_id = matched_authorized_user_id(user_id, password)
                if not matched_user_id:
                    self.send_auth_error("invalid user id or password")
                    return
                token = create_auth_session(matched_user_id)
                self.send_json(
                    {
                        "logged_in": True,
                        "user_id": matched_user_id,
                        "message": f"Session started for {matched_user_id}",
                    },
                    extra_headers={"Set-Cookie": session_cookie_value(token)},
                )
            except json.JSONDecodeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/session-logout":
            clear_auth_session(self.headers)
            self.send_json(
                {"logged_in": False, "message": "Session ended"},
                extra_headers={"Set-Cookie": session_cookie_value("", expired=True)},
            )
            return

        if self.path == "/api/save-user":
            try:
                session_user = authenticated_session_user(self.headers)
                if not session_user:
                    self.send_auth_error("authenticated session required")
                    return
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                saved = upsert_api_user(
                    str(incoming.get("new_user_id") or incoming.get("user_id") or ""),
                    str(incoming.get("new_password") or incoming.get("password") or ""),
                    bool(incoming.get("enabled", True)),
                )
                action = "updated" if saved.get("updated") else "created"
                self.send_json(
                    {
                        "message": f"User {saved['id']} {action} by {session_user}",
                        "saved_user": {"id": saved["id"], "enabled": saved["enabled"]},
                        "saved_by": session_user,
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/cancel-pending-prompts":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                user_id, password = credentials_from_request(self.headers, incoming)
                if not is_authorized_user(user_id, password):
                    self.send_auth_error("invalid user id or password")
                    return
                self.send_json(cancel_pending_prompts())
            except json.JSONDecodeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/workspace/upload":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                user_id, password = credentials_from_request(self.headers, incoming)
                if not is_authorized_user(user_id, password):
                    self.send_auth_error("invalid user id or password")
                    return
                saved = upload_workspace_files(incoming.get("files") or [])
                self.send_json(
                    {
                        "workspace_dir": str(ensure_workspace_dir()),
                        "saved": saved,
                        "files": list_workspace_files(),
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/test-image-transfer":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                user_id, password = credentials_from_request(self.headers, incoming)
                if not is_authorized_user(user_id, password):
                    self.send_auth_error("invalid user id or password")
                    return
                images = images_from_request(incoming)
                self.send_json(
                    {
                        "ok": True,
                        "message": f"Received {len(images)} image(s).",
                        "image_count": len(images),
                        "model": str(incoming.get("model") or read_selected_model()),
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if self.path != "/api/generate":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            user_id, password = credentials_from_request(self.headers, incoming)
            if not is_authorized_user(user_id, password):
                self.send_auth_error("invalid user id or password")
                return
            prompt, prompts = combined_prompt_from_request(incoming)
            if not prompt:
                self.send_json({"error": "prompt is required"}, HTTPStatus.BAD_REQUEST)
                return
            remember_prompts(prompts)
            remember_user_prompt(user_id, prompt)
            payload = {
                "model": str(incoming.get("model") or read_selected_model()),
                "prompt": prompt,
                "options": request_options(incoming),
                "keep_alive": request_keep_alive(incoming),
                "stream": False,
            }
            images = images_from_request(incoming)
            if images:
                payload["images"] = images
            result = run_queued_prompt(payload)
            if images:
                result["image_count"] = len(images)
            self.send_json(result)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    PROMPT_HISTORY_FILE.touch(exist_ok=True)
    ensure_api_key_conf()
    httpd = ThreadingHTTPServer((HOST, PORT), Gemma4Handler)
    print(f"Gemma4 service page: http://{HOST}:{PORT}")
    print(f"Ollama backend: {OLLAMA_BASE_URL}, model={OLLAMA_MODEL}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
