const promptSlots = [1, 2, 3, 4, 5, 6];

const state = {
  config: null,
  history: [],
  promptMemories: {},
  lastResult: null,
};

const elements = {
  configStatus: document.getElementById("configStatus"),
  authStatus: document.getElementById("authStatus"),
  runStatus: document.getElementById("runStatus"),
  historyStatus: document.getElementById("historyStatus"),
  headerRuntimeStatus: document.getElementById("headerRuntimeStatus"),
  promptGrid: document.getElementById("promptGrid"),
  historyList: document.getElementById("historyList"),
  historyTarget: document.getElementById("historyTarget"),
  resultSummary: document.getElementById("resultSummary"),
  resultSteps: document.getElementById("resultSteps"),
  thinkingSummary: document.getElementById("thinkingSummary"),
  thinkingSteps: document.getElementById("thinkingSteps"),
  copyResultStatus: document.getElementById("copyResultStatus"),
  copyThinkingStatus: document.getElementById("copyThinkingStatus"),
  resultTabButton: document.getElementById("resultTabButton"),
  thinkingTabButton: document.getElementById("thinkingTabButton"),
  resultTabPanel: document.getElementById("resultTabPanel"),
  thinkingTabPanel: document.getElementById("thinkingTabPanel"),
  configFileInput: document.getElementById("configFileInput"),
};

const fieldMap = {
  server_base_url: document.getElementById("serverBaseUrl"),
  generate_path: document.getElementById("generatePath"),
  status_path: document.getElementById("statusPath"),
  request_timeout_seconds: document.getElementById("requestTimeout"),
  user_id: document.getElementById("userId"),
  password: document.getElementById("password"),
  model: document.getElementById("model"),
  keep_alive: document.getElementById("keepAlive"),
  num_ctx: document.getElementById("numCtx"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function promptCardMarkup(slot) {
  return `
    <article class="prompt-card" data-slot="${slot}">
      <div class="prompt-head">
        <div>
          <h3>Prompt ${slot}</h3>
          <p>선택 여부와 그룹을 개별 지정합니다.</p>
        </div>
        <label class="toggle-row">
          <input type="checkbox" data-role="enabled" checked>
          <span>선택</span>
        </label>
      </div>
      <div class="group-buttons" data-role="group-buttons">
        <button type="button" class="group-button active" data-group="1">Group 1</button>
        <button type="button" class="group-button" data-group="2">Group 2</button>
        <button type="button" class="group-button" data-group="3">Group 3</button>
      </div>
      <textarea data-role="text" placeholder="프롬프트 입력해주세요"></textarea>
      <div class="prompt-memory-bar">
        <button type="button" class="secondary prompt-save" data-role="save-memory">저장</button>
        <select data-role="memory-select">
          <option value="">저장된 프롬프트 없음</option>
        </select>
        <button type="button" class="secondary prompt-load" data-role="load-memory">불러오기</button>
        <button type="button" class="danger prompt-delete" data-role="delete-memory">삭제</button>
      </div>
      <div class="prompt-memory-status" data-role="memory-status">저장 대기</div>
    </article>
  `;
}

function buildPromptGrid() {
  elements.promptGrid.innerHTML = promptSlots.map(promptCardMarkup).join("");
  promptSlots.forEach((slot) => {
    const card = getPromptCard(slot);
    card.querySelectorAll(".group-button").forEach((button) => {
      button.addEventListener("click", () => {
        card.querySelectorAll(".group-button").forEach((candidate) => candidate.classList.remove("active"));
        button.classList.add("active");
      });
    });
    card.querySelector('[data-role="save-memory"]').addEventListener("click", () => savePromptMemory(slot));
    card.querySelector('[data-role="load-memory"]').addEventListener("click", () => loadPromptMemory(slot));
    card.querySelector('[data-role="delete-memory"]').addEventListener("click", () => deletePromptMemory(slot));
  });
}

function buildHistoryTargetOptions() {
  elements.historyTarget.innerHTML = promptSlots
    .map((slot) => `<option value="${slot}">Prompt ${slot}</option>`)
    .join("");
}

function getPromptCard(slot) {
  return elements.promptGrid.querySelector(`[data-slot="${slot}"]`);
}

function setPromptMemoryStatus(slot, message) {
  getPromptCard(slot).querySelector('[data-role="memory-status"]').textContent = message;
}

function renderPromptMemoryOptions(slot) {
  const card = getPromptCard(slot);
  const select = card.querySelector('[data-role="memory-select"]');
  const entries = state.promptMemories[String(slot)] || [];
  if (!entries.length) {
    select.innerHTML = `<option value="">저장된 프롬프트 없음</option>`;
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = entries.map((entry, index) => {
    const preview = entry.replace(/\s+/g, " ").trim();
    const label = preview.length > 50 ? `${preview.slice(0, 50)}...` : preview;
    return `<option value="${index}">${escapeHtml(label)}</option>`;
  }).join("");
}

function readPromptState() {
  return promptSlots.map((slot) => {
    const card = getPromptCard(slot);
    return {
      slot,
      enabled: card.querySelector('[data-role="enabled"]').checked,
      group: Number(card.querySelector(".group-button.active").dataset.group),
      text: card.querySelector('[data-role="text"]').value,
    };
  });
}

function applyPromptState(prompts) {
  const bySlot = new Map((prompts || []).map((prompt) => [Number(prompt.slot), prompt]));
  promptSlots.forEach((slot) => {
    const value = bySlot.get(slot);
    const card = getPromptCard(slot);
    const enabled = card.querySelector('[data-role="enabled"]');
    const text = card.querySelector('[data-role="text"]');
    if (!value) return;
    enabled.checked = Boolean(value.enabled);
    text.value = value.text || "";
    card.querySelectorAll(".group-button").forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.group) === Number(value.group || 1));
    });
  });
}

function readConfigFromForm() {
  return {
    server_base_url: fieldMap.server_base_url.value.trim(),
    generate_path: fieldMap.generate_path.value.trim(),
    status_path: fieldMap.status_path.value.trim(),
    request_timeout_seconds: Number(fieldMap.request_timeout_seconds.value || 120),
    user_id: fieldMap.user_id.value.trim(),
    password: fieldMap.password.value,
    model: fieldMap.model.value.trim(),
    keep_alive: fieldMap.keep_alive.value.trim(),
    num_ctx: Number(fieldMap.num_ctx.value || 0),
  };
}

function activeServerBaseUrl() {
  return fieldMap.server_base_url.value.trim() || state.config?.server_base_url || "";
}

function setHeaderRuntimeStatus({runState, connectionState, detail = ""}) {
  const base = `상태: ${runState} | 연결 상태: ${connectionState}`;
  elements.headerRuntimeStatus.textContent = detail ? `${base} | ${detail}` : base;
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

async function copyPanelText(kind) {
  const isResult = kind === "result";
  const summary = isResult ? elements.resultSummary.innerText.trim() : elements.thinkingSummary.innerText.trim();
  const details = isResult ? elements.resultSteps.innerText.trim() : elements.thinkingSteps.innerText.trim();
  const value = [summary, details].filter(Boolean).join("\n\n");
  const statusNode = isResult ? elements.copyResultStatus : elements.copyThinkingStatus;
  if (!value) {
    statusNode.textContent = "복사할 내용이 없습니다.";
    return;
  }
  try {
    await copyText(value);
    statusNode.textContent = "복사했습니다.";
  } catch (error) {
    statusNode.textContent = `복사 실패: ${error}`;
  }
}

function applyConfigToForm(config) {
  Object.entries(fieldMap).forEach(([key, element]) => {
    const value = config?.[key];
    element.value = value === null || value === undefined ? "" : String(value);
  });
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function loadInitialState() {
  const data = await requestJson("/api/state");
  state.config = data.config;
  state.history = data.history;
  state.promptMemories = data.prompt_memories || {};
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  promptSlots.forEach(renderPromptMemoryOptions);
  renderHistory();
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "확인 전", detail: activeServerBaseUrl() || "Server Base URL 미입력"});
}

async function saveConfig(config) {
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: {...config, prompts: readPromptState()}}),
  });
  state.config = data.config;
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  elements.configStatus.textContent = "설정을 저장했습니다.";
}

async function saveAllPrompts() {
  elements.runStatus.textContent = "프롬프트 전체를 저장하는 중입니다.";
  const nextConfig = {
    ...(state.config || {}),
    ...readConfigFromForm(),
    prompts: readPromptState(),
  };
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: nextConfig}),
  });
  state.config = data.config;
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  elements.runStatus.textContent = "프롬프트 전체를 저장했습니다.";
}

async function saveAuthOnly() {
  elements.authStatus.textContent = "인증 정보를 저장하는 중입니다.";
  const nextConfig = {
    ...(state.config || {}),
    ...readConfigFromForm(),
    prompts: readPromptState(),
  };
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: nextConfig}),
  });
  state.config = data.config;
  applyConfigToForm(state.config);
  elements.authStatus.textContent = "User ID / Password를 저장했습니다.";
}

async function testConnection() {
  elements.configStatus.textContent = "원격 연결을 확인하는 중입니다.";
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "확인 중", detail: activeServerBaseUrl()});
  const config = {...readConfigFromForm(), prompts: readPromptState()};
  const data = await requestJson("/api/test-connection", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config}),
  });
  elements.configStatus.textContent = `연결 정상: ${data.status.server_base_url} | ${data.status.status_url} | ${data.status.model} | ${data.status.host}:${data.status.port} | Ollama ${data.status.ollama_reachable ? "reachable" : "unreachable"}`;
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결됨", detail: data.status.status_url});
}

function renderHistory() {
  if (!state.history.length) {
    elements.historyList.innerHTML = `<div class="history-item"><div class="history-preview">저장된 프롬프트가 없습니다.</div></div>`;
    elements.historyStatus.textContent = "히스토리 비어 있음";
    return;
  }
  elements.historyList.innerHTML = state.history.map((entry) => `
    <article class="history-item">
      <header>
        <div class="history-item-title">
          <input type="checkbox" data-history-id="${escapeHtml(entry.id)}">
          <strong>Prompt ${entry.slot}</strong>
        </div>
        <div class="history-meta">Group ${entry.group} | ${escapeHtml(entry.updated_at)}</div>
      </header>
      <div class="history-preview">${escapeHtml(entry.text)}</div>
    </article>
  `).join("");
  elements.historyStatus.textContent = `${state.history.length}개 프롬프트 저장됨`;
}

function selectedHistoryIds() {
  return [...elements.historyList.querySelectorAll("input[data-history-id]:checked")].map((input) => input.dataset.historyId);
}

function firstSelectedHistoryEntry() {
  const selectedId = selectedHistoryIds()[0];
  return state.history.find((entry) => entry.id === selectedId);
}

async function refreshHistory() {
  const data = await requestJson("/api/history");
  state.history = data.history;
  renderHistory();
}

async function refreshPromptMemories() {
  const data = await requestJson("/api/prompt-memories");
  state.promptMemories = data.prompt_memories || {};
  promptSlots.forEach(renderPromptMemoryOptions);
}

async function savePromptMemory(slot) {
  const card = getPromptCard(slot);
  const text = card.querySelector('[data-role="text"]').value.trim();
  if (!text) {
    setPromptMemoryStatus(slot, "저장할 프롬프트를 먼저 입력하세요.");
    return;
  }
  const data = await requestJson("/api/prompt-memory/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({slot, text}),
  });
  state.promptMemories[String(slot)] = data.entries || [];
  renderPromptMemoryOptions(slot);
  setPromptMemoryStatus(slot, `${data.entries.length}개 저장됨 (.txt, 최대 100개)`);
}

function loadPromptMemory(slot) {
  const card = getPromptCard(slot);
  const select = card.querySelector('[data-role="memory-select"]');
  const entries = state.promptMemories[String(slot)] || [];
  const entry = entries[Number(select.value)];
  if (!entry) {
    setPromptMemoryStatus(slot, "불러올 저장 프롬프트를 선택하세요.");
    return;
  }
  card.querySelector('[data-role="text"]').value = entry;
  setPromptMemoryStatus(slot, "저장된 프롬프트를 불러왔습니다.");
}

async function deletePromptMemory(slot) {
  const card = getPromptCard(slot);
  const select = card.querySelector('[data-role="memory-select"]');
  const entries = state.promptMemories[String(slot)] || [];
  const entry = entries[Number(select.value)];
  if (!entry) {
    setPromptMemoryStatus(slot, "삭제할 저장 프롬프트를 선택하세요.");
    return;
  }
  const data = await requestJson("/api/prompt-memory/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({slot, text: entry}),
  });
  state.promptMemories[String(slot)] = data.entries || [];
  renderPromptMemoryOptions(slot);
  setPromptMemoryStatus(slot, "저장 프롬프트를 삭제했습니다.");
}

async function deleteHistory() {
  const ids = selectedHistoryIds();
  if (!ids.length) {
    elements.historyStatus.textContent = "삭제할 프롬프트를 먼저 선택하세요.";
    return;
  }
  const data = await requestJson("/api/history/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ids}),
  });
  state.history = data.history;
  renderHistory();
  elements.historyStatus.textContent = `${ids.length}개 프롬프트를 삭제했습니다.`;
}

function loadHistoryToPrompt() {
  const entry = firstSelectedHistoryEntry();
  if (!entry) {
    elements.historyStatus.textContent = "불러올 프롬프트를 먼저 선택하세요.";
    return;
  }
  const slot = Number(elements.historyTarget.value);
  const card = getPromptCard(slot);
  card.querySelector('[data-role="text"]').value = entry.text;
  card.querySelector('[data-role="enabled"]').checked = true;
  card.querySelectorAll(".group-button").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.group) === Number(entry.group || 1));
  });
  elements.historyStatus.textContent = `Prompt ${slot}에 히스토리 항목을 불러왔습니다.`;
}

function summarizeResult(data) {
  const lines = [
    `사용 서버: ${data.server_base_url || "-"}`,
    `Generate URL: ${data.generate_url || "-"}`,
    `최종 모델: ${data.final_model || "-"}`,
    `최종 응답 길이: ${(data.final_response || "").length} chars`,
    `실행 그룹 수: ${data.steps.length}`,
    `총 소요 시간: ${data.elapsed_seconds.toFixed(2)}s`,
    `응답 전 저장 완료: ${data.saved_before_response ? "yes" : "no"}`,
    `Result 저장 파일: ${data.result_log_path || "-"} (${Number(data.result_log_size_bytes || 0).toLocaleString()} bytes)`,
    `Result 누적 저장 용량: ${Number(data.result_log_total_size_bytes || 0).toLocaleString()} bytes`,
    `Thinking 저장 파일: ${data.thinking_log_path || "-"} (${Number(data.thinking_log_size_bytes || 0).toLocaleString()} bytes)`,
    `Thinking 누적 저장 용량: ${Number(data.thinking_log_total_size_bytes || 0).toLocaleString()} bytes`,
    `전체 로그 누적 저장 용량: ${Number(data.all_logs_total_size_bytes || 0).toLocaleString()} bytes`,
  ];
  elements.resultSummary.innerHTML = lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

function extractThinkingBlocks(text) {
  const value = String(text || "");
  const matches = [...value.matchAll(/<think>([\s\S]*?)<\/think>/gi)];
  if (!matches.length) {
    return {thinking: "", cleaned: value};
  }
  const thinking = matches.map((match) => String(match[1] || "").trim()).filter(Boolean).join("\n\n");
  const cleaned = value.replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
  return {thinking, cleaned};
}

function summarizeThinking(data) {
  const thoughtCount = data.steps.filter((step) => extractThinkingBlocks(step.response).thinking).length;
  const lines = [
    `Thinking 포함 단계 수: ${thoughtCount}`,
    `전체 체인 단계 수: ${data.steps.length}`,
    `최종 서버: ${data.server_base_url || "-"}`,
    `Thinking 저장 파일: ${data.thinking_log_path || "-"} (${Number(data.thinking_log_size_bytes || 0).toLocaleString()} bytes)`,
    `Thinking 누적 저장 용량: ${Number(data.thinking_log_total_size_bytes || 0).toLocaleString()} bytes`,
    `전체 로그 누적 저장 용량: ${Number(data.all_logs_total_size_bytes || 0).toLocaleString()} bytes`,
  ];
  elements.thinkingSummary.innerHTML = lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

function renderSteps(steps) {
  if (!steps.length) {
    elements.resultSteps.innerHTML = "";
    return;
  }
  elements.resultSteps.innerHTML = steps.map((step) => `
    <article class="step-card">
      <div class="step-title">
        <h3>Group ${step.group}</h3>
        <div class="step-meta">${escapeHtml(step.elapsed_line || `${step.elapsed_seconds.toFixed(2)}s`)}</div>
      </div>
      <div class="step-block">
        <h4>사용된 Prompt Slots</h4>
        <pre>${escapeHtml(step.slot_labels.join(", "))}</pre>
      </div>
      <div class="step-block">
        <h4>요청 프롬프트</h4>
        <pre>${escapeHtml(step.request_prompt)}</pre>
      </div>
      <div class="step-block">
        <h4>응답</h4>
        <pre>${escapeHtml(step.response)}</pre>
      </div>
    </article>
  `).join("");
}

function renderThinkingSteps(steps) {
  if (!steps.length) {
    elements.thinkingSteps.innerHTML = "";
    return;
  }
  elements.thinkingSteps.innerHTML = steps.map((step) => {
    const parsed = extractThinkingBlocks(step.response);
    const thinkingText = parsed.thinking || "응답 안에 별도 thinking 블록이 없습니다. 아래는 이 단계의 전체 과정입니다.";
    const visibleResponse = parsed.cleaned || step.response || "(empty)";
    return `
      <article class="thinking-card">
        <h3>Group ${step.group} Thinking</h3>
        <div class="step-block">
          <h4>요청 과정</h4>
          <pre>${escapeHtml(step.request_prompt)}</pre>
        </div>
        <div class="step-block">
          <h4>Thinking</h4>
          <pre>${escapeHtml(thinkingText)}</pre>
        </div>
        <div class="step-block">
          <h4>최종 응답</h4>
          <pre>${escapeHtml(visibleResponse)}</pre>
        </div>
      </article>
    `;
  }).join("");
}

function activateTab(name) {
  const resultActive = name === "result";
  elements.resultTabButton.classList.toggle("active", resultActive);
  elements.thinkingTabButton.classList.toggle("active", !resultActive);
  elements.resultTabPanel.classList.toggle("active", resultActive);
  elements.thinkingTabPanel.classList.toggle("active", !resultActive);
}

async function runChain() {
  elements.runStatus.textContent = "그룹 체인 실행 중입니다.";
  setHeaderRuntimeStatus({runState: "실행 중", connectionState: "연결 시도 중", detail: activeServerBaseUrl()});
  const config = {...readConfigFromForm(), prompts: readPromptState()};
  const data = await requestJson("/api/run-chain", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config}),
  });
  state.lastResult = data;
  summarizeResult(data);
  renderSteps(data.steps);
  summarizeThinking(data);
  renderThinkingSteps(data.steps);
  elements.runStatus.textContent = `실행 완료: ${data.elapsed_seconds.toFixed(2)}s, 그룹 ${data.steps.length}개`;
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결됨", detail: data.generate_url || data.server_base_url || activeServerBaseUrl()});
  await refreshHistory();
}

function clearResults() {
  state.lastResult = null;
  elements.resultSummary.textContent = "아직 실행 기록이 없습니다.";
  elements.resultSteps.innerHTML = "";
  elements.thinkingSummary.textContent = "아직 thinking 기록이 없습니다.";
  elements.thinkingSteps.innerHTML = "";
  elements.runStatus.textContent = "실행 대기 중";
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "확인 전", detail: activeServerBaseUrl() || "Server Base URL 미입력"});
}

function exportConfig() {
  const config = {...readConfigFromForm(), prompts: readPromptState()};
  const blob = new Blob([JSON.stringify(config, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "client_config.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

async function importConfigFromFile(file) {
  const text = await file.text();
  const config = JSON.parse(text);
  applyConfigToForm(config);
  applyPromptState(config.prompts || []);
  elements.configStatus.textContent = "설정 파일을 불러왔습니다. 저장 버튼으로 반영하세요.";
}

document.getElementById("saveConfig").addEventListener("click", async () => {
  try {
    await saveConfig(readConfigFromForm());
  } catch (error) {
    elements.configStatus.textContent = String(error);
  }
});

document.getElementById("saveAllPrompts").addEventListener("click", async () => {
  try {
    await saveAllPrompts();
  } catch (error) {
    elements.runStatus.textContent = String(error);
  }
});

document.getElementById("saveAuth").addEventListener("click", async () => {
  try {
    await saveAuthOnly();
  } catch (error) {
    elements.authStatus.textContent = String(error);
  }
});

document.getElementById("testConnection").addEventListener("click", async () => {
  try {
    await testConnection();
  } catch (error) {
    elements.configStatus.textContent = `연결 실패: ${activeServerBaseUrl()} | ${error}`;
    setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결 실패", detail: activeServerBaseUrl()});
  }
});

document.getElementById("runChain").addEventListener("click", async () => {
  try {
    await runChain();
  } catch (error) {
    elements.runStatus.textContent = `실행 실패: ${activeServerBaseUrl()} | ${error}`;
    setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결 실패", detail: activeServerBaseUrl()});
  }
});

document.getElementById("clearResults").addEventListener("click", clearResults);
elements.resultTabButton.addEventListener("click", () => activateTab("result"));
elements.thinkingTabButton.addEventListener("click", () => activateTab("thinking"));
document.getElementById("copyResultText").addEventListener("click", () => copyPanelText("result"));
document.getElementById("copyThinkingText").addEventListener("click", () => copyPanelText("thinking"));
document.getElementById("deleteHistory").addEventListener("click", async () => {
  try {
    await deleteHistory();
  } catch (error) {
    elements.historyStatus.textContent = String(error);
  }
});
document.getElementById("loadHistoryToPrompt").addEventListener("click", loadHistoryToPrompt);
document.getElementById("exportConfig").addEventListener("click", exportConfig);
document.getElementById("importConfig").addEventListener("click", () => elements.configFileInput.click());
elements.configFileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  if (!file) return;
  try {
    await importConfigFromFile(file);
  } catch (error) {
    elements.configStatus.textContent = `설정 파일 오류: ${error}`;
  } finally {
    event.target.value = "";
  }
});

buildPromptGrid();
buildHistoryTargetOptions();

loadInitialState().then(() => {
  elements.configStatus.textContent = "설정을 불러왔습니다.";
}).catch((error) => {
  elements.configStatus.textContent = String(error);
});
