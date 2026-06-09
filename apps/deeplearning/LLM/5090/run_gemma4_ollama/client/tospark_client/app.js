const elements = {
  endpoint: document.getElementById("endpoint"),
  model: document.getElementById("model"),
  temperature: document.getElementById("temperature"),
  timeoutSeconds: document.getElementById("timeoutSeconds"),
  useProxy: document.getElementById("useProxy"),
  message: document.getElementById("message"),
  payloadPreview: document.getElementById("payloadPreview"),
  sendRequest: document.getElementById("sendRequest"),
  copyCurl: document.getElementById("copyCurl"),
  statusText: document.getElementById("statusText"),
  elapsedText: document.getElementById("elapsedText"),
  answer: document.getElementById("answer"),
  rawJson: document.getElementById("rawJson"),
};

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
  };
}

function setStatus(text, className = "") {
  elements.statusText.textContent = text;
  elements.statusText.className = `status ${className}`.trim();
}

function updatePreview() {
  elements.payloadPreview.value = JSON.stringify(payload(), null, 2);
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

async function sendRequest() {
  const endpoint = elements.endpoint.value.trim();
  if (!endpoint) {
    setStatus("Endpoint is required", "error");
    return;
  }

  const controller = new AbortController();
  const timeoutMs = Math.max(1, Number(elements.timeoutSeconds.value || 120)) * 1000;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const startedAt = performance.now();
  const elapsedTimer = window.setInterval(() => {
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    elements.elapsedText.textContent = `${elapsedSeconds.toFixed(1)}s`;
  }, 100);

  elements.sendRequest.disabled = true;
  elements.answer.textContent = "Waiting for response...";
  elements.rawJson.textContent = "{}";
  elements.elapsedText.textContent = "0.0s";
  setStatus("Sending...");

  try {
    const shouldUseProxy = elements.useProxy.checked && window.location.protocol.startsWith("http");
    const requestUrl = shouldUseProxy ? "/api/chat" : endpoint;
    const requestBody = shouldUseProxy ? {endpoint, payload: payload()} : payload();
    const response = await fetch(requestUrl, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
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
      ? "Request timed out"
      : `${error}`;
    elements.answer.textContent = message;
    elements.rawJson.textContent = JSON.stringify({error: message}, null, 2);
    setStatus(message, "error");
  } finally {
    window.clearTimeout(timeoutId);
    window.clearInterval(elapsedTimer);
    elements.sendRequest.disabled = false;
  }
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
  elements.message,
].forEach((element) => element.addEventListener("input", updatePreview));

elements.sendRequest.addEventListener("click", sendRequest);
elements.copyCurl.addEventListener("click", copyCurl);
updatePreview();
