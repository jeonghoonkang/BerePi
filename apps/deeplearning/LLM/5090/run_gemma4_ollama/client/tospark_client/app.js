const elements = {
  endpoint: document.getElementById("endpoint"),
  model: document.getElementById("model"),
  temperature: document.getElementById("temperature"),
  timeoutSeconds: document.getElementById("timeoutSeconds"),
  useProxy: document.getElementById("useProxy"),
  streamResponse: document.getElementById("streamResponse"),
  message: document.getElementById("message"),
  refreshGpu: document.getElementById("refreshGpu"),
  gpuStatus: document.getElementById("gpuStatus"),
  gpuRaw: document.getElementById("gpuRaw"),
  payloadPreview: document.getElementById("payloadPreview"),
  sendRequest: document.getElementById("sendRequest"),
  stopRequest: document.getElementById("stopRequest"),
  clearResponse: document.getElementById("clearResponse"),
  copyCurl: document.getElementById("copyCurl"),
  statusText: document.getElementById("statusText"),
  elapsedText: document.getElementById("elapsedText"),
  answer: document.getElementById("answer"),
  rawJson: document.getElementById("rawJson"),
};

let activeRequestController = null;
let activeStopRequested = false;

function payload() {
  return {
    model: elements.model.value.trim(),
    messages: [
      {
        role: "user",
        content: elements.message.value,
      },
    ],
    temperature: Number(elements.temperature.value || 0),
    stream: elements.streamResponse.checked,
  };
}

function setStatus(text, className = "") {
  elements.statusText.textContent = text;
  elements.statusText.className = `status ${className}`.trim();
}

function updatePreview() {
  elements.payloadPreview.value = JSON.stringify(payload(), null, 2);
}

function endpointOrigin(value) {
  try {
    const url = new URL(value);
    return url.origin;
  } catch {
    return "";
  }
}

function renderGpuStatus(data) {
  const lines = [data.summary || "GPU status unavailable"];
  if (Array.isArray(data.gpu_metric_lines) && data.gpu_metric_lines.length) {
    lines.push("");
    lines.push("Relevant metrics:");
    lines.push(...data.gpu_metric_lines.slice(0, 12));
  }
  elements.gpuStatus.textContent = lines.join("\n");
  elements.gpuRaw.textContent = JSON.stringify(data, null, 2);
}

async function refreshGpuStatus() {
  const endpoint = elements.endpoint.value.trim();
  if (!endpointOrigin(endpoint)) {
    elements.gpuStatus.textContent = "Endpoint must include scheme and host.";
    elements.gpuRaw.textContent = "{}";
    return;
  }
  if (!window.location.protocol.startsWith("http")) {
    elements.gpuStatus.textContent = "Run serve.py and open http://127.0.0.1:8091 to inspect GPU status.";
    elements.gpuRaw.textContent = "{}";
    return;
  }

  elements.refreshGpu.disabled = true;
  elements.gpuStatus.textContent = "Checking GPU/server status...";
  try {
    const response = await fetch("/api/gpu-status", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({endpoint}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    renderGpuStatus(data);
  } catch (error) {
    elements.gpuStatus.textContent = `GPU status check failed: ${error}`;
    elements.gpuRaw.textContent = JSON.stringify({error: String(error)}, null, 2);
  } finally {
    elements.refreshGpu.disabled = false;
  }
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\"'\"'")}'`;
}

function curlCommand() {
  return [
    "curl",
    shellQuote(elements.endpoint.value.trim()),
    "-H",
    shellQuote("Content-Type: application/json"),
    "-d",
    shellQuote(JSON.stringify(payload(), null, 2)),
  ].join(" ");
}

function extractAnswer(data) {
  const choice = Array.isArray(data.choices) ? data.choices[0] : null;
  const message = choice && choice.message ? choice.message : null;
  if (message && typeof message.content === "string") {
    return message.content;
  }
  if (typeof data.response === "string") {
    return data.response;
  }
  if (typeof data.content === "string") {
    return data.content;
  }
  return JSON.stringify(data, null, 2);
}

function deltaContent(data) {
  const choice = Array.isArray(data.choices) ? data.choices[0] : null;
  const delta = choice && choice.delta ? choice.delta : null;
  if (delta && typeof delta.content === "string") {
    return delta.content;
  }
  const message = choice && choice.message ? choice.message : null;
  if (message && typeof message.content === "string") {
    return message.content;
  }
  if (typeof data.response === "string") {
    return data.response;
  }
  if (typeof data.content === "string") {
    return data.content;
  }
  return "";
}

async function readStreamingResponse(response, onChunkReceived) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answerText = "";
  const events = [];

  elements.answer.textContent = "";

  function appendEvent(data) {
    const content = deltaContent(data);
    if (content) {
      answerText += content;
      elements.answer.textContent = answerText;
    }
  }

  function processLine(line) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(":")) {
      return;
    }

    const payloadText = trimmed.startsWith("data:")
      ? trimmed.slice(5).trim()
      : trimmed;
    if (!payloadText || payloadText === "[DONE]") {
      return;
    }

    try {
      const data = JSON.parse(payloadText);
      events.push(data);
      appendEvent(data);
    } catch {
      events.push({raw: payloadText});
      answerText += payloadText;
      elements.answer.textContent = answerText;
    }
  }

  while (true) {
    const {done, value} = await reader.read();
    if (done) {
      break;
    }

    onChunkReceived();
    buffer += decoder.decode(value, {stream: true});
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    lines.forEach(processLine);
    elements.rawJson.textContent = JSON.stringify(events, null, 2);
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    processLine(buffer);
  }

  elements.rawJson.textContent = JSON.stringify(events, null, 2);
  if (!answerText) {
    elements.answer.textContent = "Streaming response completed with no content.";
  }
}

async function sendRequest() {
  const endpoint = elements.endpoint.value.trim();
  if (!endpoint) {
    setStatus("Endpoint is required", "error");
    return;
  }

  const controller = new AbortController();
  activeRequestController = controller;
  activeStopRequested = false;
  const timeoutMs = Math.max(1, Number(elements.timeoutSeconds.value || 120)) * 1000;
  let timeoutId = 0;
  function resetRequestTimeout() {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  }
  resetRequestTimeout();
  const startedAt = performance.now();
  const elapsedTimer = window.setInterval(() => {
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    elements.elapsedText.textContent = `${elapsedSeconds.toFixed(1)}s`;
  }, 100);

  elements.sendRequest.disabled = true;
  elements.stopRequest.disabled = false;
  elements.answer.textContent = "Waiting for response...";
  elements.rawJson.textContent = "{}";
  elements.elapsedText.textContent = "0.0s";
  setStatus("Sending...");

  try {
    const currentPayload = payload();
    const shouldUseProxy = elements.useProxy.checked && window.location.protocol.startsWith("http");
    const requestUrl = shouldUseProxy ? "/api/chat" : endpoint;
    const requestBody = shouldUseProxy ? {endpoint, payload: currentPayload} : currentPayload;
    const response = await fetch(requestUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    if (currentPayload.stream && response.body) {
      await readStreamingResponse(response, resetRequestTimeout);
      const elapsedSeconds = (performance.now() - startedAt) / 1000;
      elements.elapsedText.textContent = `${elapsedSeconds.toFixed(2)}s`;
      setStatus(response.ok ? "Done" : `HTTP ${response.status}`, response.ok ? "ok" : "error");
      return;
    }

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = {raw_response: text};
    }

    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    elements.elapsedText.textContent = `${elapsedSeconds.toFixed(2)}s`;
    elements.rawJson.textContent = JSON.stringify(data, null, 2);
    elements.answer.textContent = extractAnswer(data);

    if (!response.ok) {
      setStatus(`HTTP ${response.status}`, "error");
      return;
    }
    setStatus("Done", "ok");
  } catch (error) {
    const message = error.name === "AbortError"
      ? (activeStopRequested ? "Request stopped" : "Request timed out")
      : `${error}`;
    setStatus(message, "error");
  } finally {
    window.clearTimeout(timeoutId);
    window.clearInterval(elapsedTimer);
    elements.sendRequest.disabled = false;
    elements.stopRequest.disabled = true;
    activeRequestController = null;
    activeStopRequested = false;
  }
}

function stopRequest() {
  if (!activeRequestController) {
    return;
  }
  activeStopRequested = true;
  activeRequestController.abort();
  setStatus("Stopping...", "error");
}

function clearResponse() {
  elements.answer.textContent = "";
  elements.rawJson.textContent = "{}";
  elements.elapsedText.textContent = "-";
}

async function copyCurl() {
  const command = curlCommand();
  try {
    await navigator.clipboard.writeText(command);
    setStatus("curl copied", "ok");
  } catch {
    elements.payloadPreview.value = command;
    setStatus("Clipboard unavailable; curl placed in JSON box", "error");
  }
}

[
  elements.endpoint,
  elements.model,
  elements.temperature,
  elements.timeoutSeconds,
  elements.streamResponse,
  elements.message,
].forEach((element) => element.addEventListener("input", updatePreview));

let gpuRefreshTimer = 0;
elements.endpoint.addEventListener("input", () => {
  window.clearTimeout(gpuRefreshTimer);
  gpuRefreshTimer = window.setTimeout(refreshGpuStatus, 600);
});
elements.refreshGpu.addEventListener("click", refreshGpuStatus);
elements.sendRequest.addEventListener("click", sendRequest);
elements.stopRequest.addEventListener("click", stopRequest);
elements.clearResponse.addEventListener("click", clearResponse);
elements.copyCurl.addEventListener("click", copyCurl);
updatePreview();
refreshGpuStatus();
