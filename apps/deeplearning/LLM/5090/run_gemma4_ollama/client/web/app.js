const promptSlots = [1, 2, 3, 4, 5, 6];

const state = {
  config: null,
  history: [],
  promptMemories: {},
  workspaceFiles: [],
  workspaceDir: "",
  remoteWorkspaceFiles: [],
  remoteWorkspaceDir: "",
  remoteWorkspaceError: "",
  pendingWorkspaceFiles: [],
  lastResult: null,
};

const elements = {
  configStatus: document.getElementById("configStatus"),
  queueStatus: document.getElementById("queueStatus"),
  authStatus: document.getElementById("authStatus"),
  runStatus: document.getElementById("runStatus"),
  chainOrderStatus: document.getElementById("chainOrderStatus"),
  chainSaveStatus: document.getElementById("chainSaveStatus"),
  historyStatus: document.getElementById("historyStatus"),
  headerRuntimeStatus: document.getElementById("headerRuntimeStatus"),
  workspaceStatus: document.getElementById("workspaceStatus"),
  workspaceUploadStatus: document.getElementById("workspaceUploadStatus"),
  workspaceDirStatus: document.getElementById("workspaceDirStatus"),
  remoteWorkspaceDirStatus: document.getElementById("remoteWorkspaceDirStatus"),
  promptGrid: document.getElementById("promptGrid"),
  historyList: document.getElementById("historyList"),
  historyTarget: document.getElementById("historyTarget"),
  workspaceTarget: document.getElementById("workspaceTarget"),
  workspaceFileList: document.getElementById("workspaceFileList"),
  remoteWorkspaceFileList: document.getElementById("remoteWorkspaceFileList"),
  workspacePendingList: document.getElementById("workspacePendingList"),
  workspaceFileInput: document.getElementById("workspaceFileInput"),
  dropZone: document.getElementById("dropZone"),
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
  chainFileName: document.getElementById("chainFileName"),
  ocrImage: document.getElementById("ocrImage"),
  ocrPrompt: document.getElementById("ocrPrompt"),
  ocrStatus: document.getElementById("ocrStatus"),
  ocrOutput: document.getElementById("ocrOutput"),
  yoloImage: document.getElementById("yoloImage"),
  yoloPrompt: document.getElementById("yoloPrompt"),
  yoloStatus: document.getElementById("yoloStatus"),
  yoloOutput: document.getElementById("yoloOutput"),
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
  local_workspace_dir: document.getElementById("localWorkspaceDir"),
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
        updateChainOrderStatus();
      });
    });
    card.querySelector('[data-role="enabled"]').addEventListener("change", updateChainOrderStatus);
    card.querySelector('[data-role="text"]').addEventListener("input", updateChainOrderStatus);
    card.querySelector('[data-role="save-memory"]').addEventListener("click", () => savePromptMemory(slot));
    card.querySelector('[data-role="load-memory"]').addEventListener("click", () => loadPromptMemory(slot));
    card.querySelector('[data-role="delete-memory"]').addEventListener("click", () => deletePromptMemory(slot));
  });
}

function buildHistoryTargetOptions() {
  elements.historyTarget.innerHTML = promptSlots
    .map((slot) => `<option value="${slot}">Prompt ${slot}</option>`)
    .join("");
  elements.workspaceTarget.innerHTML = promptSlots
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

function selectedPromptEntries() {
  return readPromptState()
    .filter((prompt) => prompt.enabled && String(prompt.text || "").trim())
    .sort((left, right) => (left.group - right.group) || (left.slot - right.slot));
}

function formatChainOrder(entries = selectedPromptEntries()) {
  if (!entries.length) {
    return "선택된 프롬프트 없음";
  }
  const grouped = new Map();
  for (const entry of entries) {
    const items = grouped.get(entry.group) || [];
    items.push(`Prompt ${entry.slot}`);
    grouped.set(entry.group, items);
  }
  return [1, 2, 3]
    .filter((group) => grouped.has(group))
    .map((group) => `Group ${group}: ${grouped.get(group).join(", ")}`)
    .join(" -> ");
}

function updateChainOrderStatus() {
  elements.chainOrderStatus.textContent = `현재 체인 순서: ${formatChainOrder()}`;
}

function humanSize(sizeBytes) {
  const value = Number(sizeBytes || 0);
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(2)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} bytes`;
}

function updateWorkspaceDirStatus() {
  const value = fieldMap.local_workspace_dir.value.trim() || state.workspaceDir || state.config?.local_workspace_dir || "";
  elements.workspaceDirStatus.textContent = value ? `클라이언트 workspace 경로: ${value}` : "클라이언트 workspace 경로 미설정";
}

function updateRemoteWorkspaceDirStatus() {
  if (state.remoteWorkspaceError) {
    elements.remoteWorkspaceDirStatus.textContent = `서버 workspace 조회 실패: ${state.remoteWorkspaceError}`;
    return;
  }
  const value = state.remoteWorkspaceDir || "";
  elements.remoteWorkspaceDirStatus.textContent = value ? `서버 workspace 경로: ${value}` : "서버 workspace 경로 확인 전";
}

function renderWorkspacePendingFiles() {
  if (!state.pendingWorkspaceFiles.length) {
    elements.workspacePendingList.innerHTML = `<div class="workspace-item"><div class="workspace-meta">업로드 대기 파일이 없습니다.</div></div>`;
    return;
  }
  elements.workspacePendingList.innerHTML = state.pendingWorkspaceFiles.map((file, index) => `
    <article class="workspace-item">
      <header>
        <div class="workspace-title">${escapeHtml(file.name)}</div>
        <div class="workspace-meta">${humanSize(file.size)}</div>
      </header>
      <div class="workspace-actions">
        <button class="secondary" type="button" data-remove-upload="${index}">목록 제거</button>
      </div>
    </article>
  `).join("");
  elements.workspacePendingList.querySelectorAll("[data-remove-upload]").forEach((button) => {
    button.addEventListener("click", () => {
      state.pendingWorkspaceFiles.splice(Number(button.dataset.removeUpload), 1);
      renderWorkspacePendingFiles();
    });
  });
}

function renderWorkspaceFiles() {
  if (!state.workspaceFiles.length) {
    elements.workspaceFileList.innerHTML = `<div class="workspace-item"><div class="workspace-meta">workspace 파일이 없습니다.</div></div>`;
    elements.workspaceStatus.textContent = "workspace 비어 있음";
    updateWorkspaceDirStatus();
    return;
  }
  elements.workspaceFileList.innerHTML = state.workspaceFiles.map((file) => `
    <article class="workspace-item">
      <header>
        <div class="workspace-title">${escapeHtml(file.name)}</div>
        <div class="workspace-meta">${escapeHtml(file.modified_at || "")} | ${humanSize(file.size_bytes)}</div>
      </header>
      <div class="workspace-path"><strong>로컬 상대 경로</strong><br>${escapeHtml(file.path)}</div>
      <div class="workspace-path"><strong>로컬 절대 경로</strong><br>${escapeHtml(file.absolute_path || file.path || "")}</div>
      <div class="workspace-actions">
        <button class="secondary" type="button" data-insert-workspace="${escapeHtml(file.absolute_path || file.path)}">로컬 경로 입력</button>
        <button class="secondary" type="button" data-download-workspace="${escapeHtml(file.name)}">다운로드</button>
        <button class="secondary" type="button" data-rename-workspace="${escapeHtml(file.name)}">이름변경</button>
        <button class="danger" type="button" data-delete-workspace="${escapeHtml(file.name)}">삭제</button>
      </div>
    </article>
  `).join("");
  elements.workspaceFileList.querySelectorAll("[data-insert-workspace]").forEach((button) => {
    button.addEventListener("click", () => insertWorkspacePath(button.dataset.insertWorkspace));
  });
  elements.workspaceFileList.querySelectorAll("[data-download-workspace]").forEach((button) => {
    button.addEventListener("click", () => downloadWorkspaceFile(button.dataset.downloadWorkspace));
  });
  elements.workspaceFileList.querySelectorAll("[data-rename-workspace]").forEach((button) => {
    button.addEventListener("click", () => renameWorkspaceFile(button.dataset.renameWorkspace));
  });
  elements.workspaceFileList.querySelectorAll("[data-delete-workspace]").forEach((button) => {
    button.addEventListener("click", () => deleteWorkspaceFile(button.dataset.deleteWorkspace));
  });
  elements.workspaceStatus.textContent = `${state.workspaceFiles.length}개 workspace 파일`;
  updateWorkspaceDirStatus();
}

function renderRemoteWorkspaceFiles() {
  if (state.remoteWorkspaceError) {
    elements.remoteWorkspaceFileList.innerHTML = `<div class="workspace-item"><div class="workspace-meta">${escapeHtml(state.remoteWorkspaceError)}</div></div>`;
    updateRemoteWorkspaceDirStatus();
    return;
  }
  if (!state.remoteWorkspaceFiles.length) {
    elements.remoteWorkspaceFileList.innerHTML = `<div class="workspace-item"><div class="workspace-meta">서버 workspace 파일이 없습니다.</div></div>`;
    updateRemoteWorkspaceDirStatus();
    return;
  }
  elements.remoteWorkspaceFileList.innerHTML = state.remoteWorkspaceFiles.map((file) => `
    <article class="workspace-item">
      <header>
        <div class="workspace-title">${escapeHtml(file.name)}</div>
        <div class="workspace-meta">${escapeHtml(file.modified_at || "")} | ${humanSize(file.size_bytes)}</div>
      </header>
      <div class="workspace-path"><strong>서버 상대 경로</strong><br>${escapeHtml(file.path || "")}</div>
      <div class="workspace-path"><strong>서버 절대 경로</strong><br>${escapeHtml(file.absolute_path || file.path || "")}</div>
      <div class="workspace-actions">
        <button class="secondary" type="button" data-insert-remote-workspace="${escapeHtml(file.absolute_path || file.path)}">서버 경로 입력</button>
      </div>
    </article>
  `).join("");
  elements.remoteWorkspaceFileList.querySelectorAll("[data-insert-remote-workspace]").forEach((button) => {
    button.addEventListener("click", () => insertWorkspacePath(button.dataset.insertRemoteWorkspace));
  });
  updateRemoteWorkspaceDirStatus();
}

function insertWorkspacePath(path) {
  const slot = Number(elements.workspaceTarget.value);
  const card = getPromptCard(slot);
  const textarea = card.querySelector('[data-role="text"]');
  const nextValue = textarea.value.trim() ? `${textarea.value}\n${path}` : path;
  textarea.value = nextValue;
  card.querySelector('[data-role="enabled"]').checked = true;
  elements.workspaceStatus.textContent = `Prompt ${slot}에 ${path} 경로를 입력했습니다.`;
  updateChainOrderStatus();
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
  updateChainOrderStatus();
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
    local_workspace_dir: fieldMap.local_workspace_dir.value.trim(),
  };
}

function activeServerBaseUrl() {
  return fieldMap.server_base_url.value.trim() || state.config?.server_base_url || "";
}

function setHeaderRuntimeStatus({runState, connectionState, detail = ""}) {
  const base = `상태: ${runState} | 연결 상태: ${connectionState}`;
  elements.headerRuntimeStatus.textContent = detail ? `${base} | ${detail}` : base;
}

function queueStatusLine(status) {
  const queue = status?.prompt_queue || {};
  const waiting = Number(status?.waiting_job_count ?? queue.waiting_job_count ?? queue.pending_count ?? 0);
  const active = Number(status?.active_job_count ?? queue.active_job_count ?? (queue.active ? 1 : 0));
  const total = Number(status?.total_unfinished_job_count ?? queue.total_unfinished_job_count ?? (waiting + active));
  const waitSeconds = Number(queue.estimated_wait_seconds || 0);
  return `Queue 대기 작업: ${waiting}개 | 처리 중: ${active}개 | 총 미완료: ${total}개${waitSeconds > 0 ? ` | 예상 대기: ${waitSeconds.toFixed(2)}s` : ""}`;
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

function imagePayloadFromFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error("이미지 파일을 먼저 선택하세요."));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    };
    reader.onerror = () => reject(reader.error || new Error("이미지 파일을 읽지 못했습니다."));
    reader.readAsDataURL(file);
  });
}

async function loadInitialState() {
  const data = await requestJson("/api/state");
  state.config = data.config;
  state.history = data.history;
  state.promptMemories = data.prompt_memories || {};
  state.workspaceFiles = data.workspace_files || [];
  state.workspaceDir = data.workspace_dir || data.config?.local_workspace_dir || "";
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  promptSlots.forEach(renderPromptMemoryOptions);
  renderHistory();
  renderWorkspacePendingFiles();
  renderWorkspaceFiles();
  updateWorkspaceDirStatus();
  updateChainOrderStatus();
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "확인 전", detail: activeServerBaseUrl() || "Server Base URL 미입력"});
  await refreshRemoteWorkspaceFiles();
}

async function saveConfig(config) {
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: {...config, prompts: readPromptState()}}),
  });
  state.config = data.config;
  state.workspaceDir = data.config?.local_workspace_dir || state.workspaceDir;
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  await refreshWorkspaceFiles();
  await refreshRemoteWorkspaceFiles();
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
  state.workspaceDir = data.config?.local_workspace_dir || state.workspaceDir;
  applyConfigToForm(state.config);
  applyPromptState(state.config.prompts);
  await refreshWorkspaceFiles();
  await refreshRemoteWorkspaceFiles();
  elements.runStatus.textContent = "프롬프트 전체를 저장했습니다.";
}

async function saveChainFile() {
  elements.chainSaveStatus.textContent = "체인 파일을 저장하는 중입니다.";
  const payload = {
    name: elements.chainFileName.value.trim(),
    config: {
      ...(state.config || {}),
      ...readConfigFromForm(),
      prompts: readPromptState(),
    },
  };
  const data = await requestJson("/api/save-chain-file", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  elements.chainSaveStatus.textContent = `체인 파일 저장 완료: ${data.file_path} (${Number(data.size_bytes || 0).toLocaleString()} bytes) | ${data.order_label}`;
  if (!elements.chainFileName.value.trim()) {
    elements.chainFileName.value = data.file_name || "";
  }
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
  const queueLine = queueStatusLine(data.status);
  elements.configStatus.textContent = `연결 정상: ${data.status.server_base_url} | ${data.status.status_url} | ${data.status.model} | ${data.status.host}:${data.status.port} | Ollama ${data.status.ollama_reachable ? "reachable" : "unreachable"}`;
  elements.queueStatus.textContent = queueLine;
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결됨", detail: `${data.status.status_url} | ${queueLine}`});
}

function renderHistory() {
  if (!state.history.length) {
    elements.historyList.innerHTML = `<div class="history-item"><div class="history-preview">저장된 프롬프트가 없습니다.</div></div>`;
    elements.historyStatus.textContent = "히스토리 비어 있음";
    return;
  }
  const previewText = (value) => {
    const singleLine = String(value || "").replace(/\s+/g, " ").trim();
    if (singleLine.length <= 90) {
      return singleLine;
    }
    return `${singleLine.slice(0, 90)}...`;
  };
  elements.historyList.innerHTML = state.history.map((entry) => `
    <article class="history-item">
      <header>
        <div class="history-item-title">
          <input type="checkbox" data-history-id="${escapeHtml(entry.id)}">
          <strong>Prompt ${entry.slot}</strong>
        </div>
        <div class="history-meta">Group ${entry.group} | ${escapeHtml(entry.updated_at)}</div>
      </header>
      <div class="history-preview">${escapeHtml(previewText(entry.text))}</div>
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

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      const marker = "base64,";
      const offset = value.indexOf(marker);
      if (offset < 0) {
        reject(new Error(`base64 인코딩 실패: ${file.name}`));
        return;
      }
      resolve(value.slice(offset + marker.length));
    };
    reader.onerror = () => reject(reader.error || new Error(`파일 읽기 실패: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function addPendingWorkspaceFiles(fileList) {
  const nextFiles = [...(fileList || [])].filter((file) => file && file.name);
  if (!nextFiles.length) {
    return;
  }
  const existing = new Set(state.pendingWorkspaceFiles.map((file) => `${file.name}:${file.size}:${file.lastModified || 0}`));
  for (const file of nextFiles) {
    const key = `${file.name}:${file.size}:${file.lastModified || 0}`;
    if (!existing.has(key)) {
      state.pendingWorkspaceFiles.push(file);
      existing.add(key);
    }
  }
  renderWorkspacePendingFiles();
  elements.workspaceUploadStatus.textContent = `${state.pendingWorkspaceFiles.length}개 파일 업로드 대기 중`;
}

async function refreshWorkspaceFiles() {
  const data = await requestJson("/api/workspace/files");
  state.workspaceFiles = data.files || [];
  state.workspaceDir = data.workspace_dir || fieldMap.local_workspace_dir.value.trim() || state.workspaceDir;
  renderWorkspaceFiles();
}

async function refreshRemoteWorkspaceFiles() {
  const data = await requestJson("/api/workspace/remote-files");
  state.remoteWorkspaceFiles = data.files || [];
  state.remoteWorkspaceDir = data.workspace_dir || "";
  state.remoteWorkspaceError = data.ok === false ? String(data.error || data.url || "remote workspace unavailable") : "";
  renderRemoteWorkspaceFiles();
}

async function uploadWorkspaceFiles() {
  if (!state.pendingWorkspaceFiles.length) {
    elements.workspaceUploadStatus.textContent = "업로드할 파일을 먼저 추가하세요.";
    return;
  }
  elements.workspaceUploadStatus.textContent = `${state.pendingWorkspaceFiles.length}개 파일을 업로드하는 중입니다.`;
  const files = await Promise.all(state.pendingWorkspaceFiles.map(async (file) => ({
    name: file.name,
    content_base64: await fileToBase64(file),
  })));
  const data = await requestJson("/api/workspace/upload", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({files, config: readConfigFromForm()}),
  });
  const remoteSync = data.remote_sync || {};
  state.workspaceFiles = data.files || [];
  state.workspaceDir = data.workspace_dir || state.workspaceDir;
  state.pendingWorkspaceFiles = [];
  renderWorkspacePendingFiles();
  renderWorkspaceFiles();
  if (remoteSync.ok) {
    await refreshRemoteWorkspaceFiles();
  } else {
    renderRemoteWorkspaceFiles();
  }
  const localSaved = (data.saved || []).length;
  if (remoteSync.attempted && remoteSync.ok) {
    elements.workspaceUploadStatus.textContent = `${localSaved}개 파일을 로컬 workspace와 서버 workspace에 저장했습니다. 서버 저장 ${Number(remoteSync.saved_count || 0)}개`;
    return;
  }
  if (remoteSync.attempted && !remoteSync.ok) {
    elements.workspaceUploadStatus.textContent = `${localSaved}개 파일을 로컬 workspace에 저장했습니다. 서버 workspace 업로드 실패: ${remoteSync.error || remoteSync.url || "unknown error"}`;
    return;
  }
  elements.workspaceUploadStatus.textContent = `${localSaved}개 파일을 로컬 workspace에 저장했습니다.`;
}

async function deleteWorkspaceFile(name) {
  if (!window.confirm(`${name} 파일을 workspace에서 삭제하시겠습니까?`)) {
    return;
  }
  elements.workspaceStatus.textContent = `${name} 삭제 중`;
  const data = await requestJson("/api/workspace/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name}),
  });
  state.workspaceFiles = data.files || [];
  state.workspaceDir = data.workspace_dir || state.workspaceDir;
  renderWorkspaceFiles();
  elements.workspaceStatus.textContent = `${data.deleted} 파일을 삭제했습니다.`;
  await refreshRemoteWorkspaceFiles();
}

async function renameWorkspaceFile(name) {
  const nextName = window.prompt("새 파일 이름을 입력하세요.", name);
  if (nextName === null) {
    return;
  }
  if (!String(nextName).trim()) {
    elements.workspaceStatus.textContent = "새 파일 이름을 입력하세요.";
    return;
  }
  elements.workspaceStatus.textContent = `${name} 이름 변경 중`;
  const data = await requestJson("/api/workspace/rename", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({old_name: name, new_name: String(nextName).trim()}),
  });
  state.workspaceFiles = data.files || [];
  state.workspaceDir = data.workspace_dir || state.workspaceDir;
  renderWorkspaceFiles();
  elements.workspaceStatus.textContent = `${name} -> ${data.renamed.name}`;
  await refreshRemoteWorkspaceFiles();
}

function downloadWorkspaceFile(name) {
  window.location.href = `/api/workspace/download?name=${encodeURIComponent(name)}`;
  elements.workspaceStatus.textContent = `${name} 다운로드를 시작했습니다.`;
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
    `실행 프롬프트 순서: ${data.order_label || "-"}`,
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
  const thoughtCount = data.steps.filter((step) => String(step.thinking || "").trim() || extractThinkingBlocks(step.response).thinking).length;
  const lines = [
    `실행 프롬프트 순서: ${data.order_label || "-"}`,
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
    const thinkingText = String(step.thinking || "").trim() || parsed.thinking || "응답 안에 별도 thinking 블록이 없습니다. 아래는 이 단계의 전체 과정입니다.";
    const visibleResponse = String(step.visible_response || "").trim() || parsed.cleaned || step.response || "(empty)";
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
  elements.chainOrderStatus.textContent = `현재 체인 순서: ${formatChainOrder()}`;
  setHeaderRuntimeStatus({runState: "실행 중", connectionState: "연결 시도 중", detail: activeServerBaseUrl()});
  const config = {...readConfigFromForm(), prompts: readPromptState()};
  try {
    const status = await requestJson("/api/test-connection", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({config}),
    });
    const queueLine = queueStatusLine(status.status);
    elements.queueStatus.textContent = queueLine;
    elements.runStatus.textContent = `그룹 체인 실행 중입니다. ${queueLine}`;
  } catch (error) {
    elements.queueStatus.textContent = `Queue 대기 작업: 확인 실패 (${error})`;
  }
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
  elements.chainOrderStatus.textContent = `현재 체인 순서: ${data.order_label || formatChainOrder()}`;
  setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결됨", detail: data.generate_url || data.server_base_url || activeServerBaseUrl()});
  await refreshHistory();
}

async function runVision(kind) {
  const isOcr = kind === "ocr";
  const input = isOcr ? elements.ocrImage : elements.yoloImage;
  const promptInput = isOcr ? elements.ocrPrompt : elements.yoloPrompt;
  const status = isOcr ? elements.ocrStatus : elements.yoloStatus;
  const output = isOcr ? elements.ocrOutput : elements.yoloOutput;
  const label = isOcr ? "OCR" : "YOLO";
  const config = readConfigFromForm();
  let requestTimer = null;

  status.textContent = `${label} 준비 중`;
  output.textContent = `${label} 요청 준비 중`;

  try {
    const file = input.files && input.files[0];
    const prompt = promptInput.value.trim();
    if (!prompt) {
      throw new Error("프롬프트를 입력하세요.");
    }
    const image = await imagePayloadFromFile(file);
    const requestStartedAt = performance.now();
    function updateTimer() {
      const elapsedSeconds = Math.floor((performance.now() - requestStartedAt) / 1000);
      const message = `${label} 실행 중... 요청 후 ${elapsedSeconds}s`;
      status.textContent = message;
      output.textContent = message;
    }
    updateTimer();
    requestTimer = window.setInterval(updateTimer, 1000);

    const data = await requestJson("/api/run-vision", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({config, prompt, images: [image]}),
    });
    const elapsedSeconds = (performance.now() - requestStartedAt) / 1000;
    const responseText = data.response || JSON.stringify(data, null, 2);
    output.textContent = `${responseText}\n\n${data.elapsed_line || `Elapsed time: ${elapsedSeconds.toFixed(2)}s`}`;
    status.textContent = `${label} 완료: ${elapsedSeconds.toFixed(2)}s`;
    setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결됨", detail: data.generate_url || activeServerBaseUrl()});
  } catch (error) {
    status.textContent = `${label} 실패: ${error}`;
    output.textContent = String(error);
    setHeaderRuntimeStatus({runState: "정지 중", connectionState: "연결 실패", detail: activeServerBaseUrl()});
  } finally {
    if (requestTimer) window.clearInterval(requestTimer);
  }
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
  state.workspaceDir = config.local_workspace_dir || state.workspaceDir;
  updateWorkspaceDirStatus();
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

document.getElementById("saveChainFile").addEventListener("click", async () => {
  try {
    await saveChainFile();
  } catch (error) {
    elements.chainSaveStatus.textContent = String(error);
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
document.getElementById("runOcr").addEventListener("click", () => runVision("ocr"));
document.getElementById("runYolo").addEventListener("click", () => runVision("yolo"));

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
document.getElementById("uploadWorkspaceFiles").addEventListener("click", async () => {
  try {
    await uploadWorkspaceFiles();
  } catch (error) {
    elements.workspaceUploadStatus.textContent = `업로드 실패: ${error}`;
  }
});
document.getElementById("refreshWorkspaceFiles").addEventListener("click", async () => {
  try {
    elements.workspaceStatus.textContent = "workspace 파일 목록을 새로고침하는 중입니다.";
    await refreshWorkspaceFiles();
    await refreshRemoteWorkspaceFiles();
  } catch (error) {
    elements.workspaceStatus.textContent = `목록 갱신 실패: ${error}`;
  }
});
fieldMap.local_workspace_dir.addEventListener("input", updateWorkspaceDirStatus);
elements.workspaceFileInput.addEventListener("change", (event) => {
  addPendingWorkspaceFiles(event.target.files || []);
  event.target.value = "";
});
elements.dropZone.addEventListener("click", () => elements.workspaceFileInput.click());
elements.dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  elements.dropZone.classList.add("dragover");
});
elements.dropZone.addEventListener("dragenter", (event) => {
  event.preventDefault();
  elements.dropZone.classList.add("dragover");
});
elements.dropZone.addEventListener("dragleave", (event) => {
  if (!elements.dropZone.contains(event.relatedTarget)) {
    elements.dropZone.classList.remove("dragover");
  }
});
elements.dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  elements.dropZone.classList.remove("dragover");
  addPendingWorkspaceFiles(event.dataTransfer?.files || []);
});
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
