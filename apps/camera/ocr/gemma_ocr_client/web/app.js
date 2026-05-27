const state = {
  config: null,
  images: [],
  history: [],
  webdavHistory: [],
  resultWebdavHistory: [],
  webdavFiles: [],
  activeWebdavSlot: 1,
  ocrTimerId: null,
  ocrStartedAt: 0,
  ocrRunning: false,
};

const elements = {
  connectionStatus: document.getElementById("connectionStatus"),
  serverBaseUrl: document.getElementById("serverBaseUrl"),
  generatePath: document.getElementById("generatePath"),
  statusPath: document.getElementById("statusPath"),
  requestTimeout: document.getElementById("requestTimeout"),
  userId: document.getElementById("userId"),
  password: document.getElementById("password"),
  model: document.getElementById("model"),
  keepAlive: document.getElementById("keepAlive"),
  numCtx: document.getElementById("numCtx"),
  ocrPrompt: document.getElementById("ocrPrompt"),
  webdavStatus: document.getElementById("webdavStatus"),
  webdavTabs: [...document.querySelectorAll("[data-webdav-tab]")],
  webdavPanels: [...document.querySelectorAll("[data-webdav-panel]")],
  webdavUrl: {
    1: document.getElementById("webdavUrl1"),
    2: document.getElementById("webdavUrl2"),
  },
  webdavUser: {
    1: document.getElementById("webdavUser1"),
    2: document.getElementById("webdavUser2"),
  },
  webdavPassword: {
    1: document.getElementById("webdavPassword1"),
    2: document.getElementById("webdavPassword2"),
  },
  webdavHistory: document.getElementById("webdavHistory"),
  testWebdavImage: document.getElementById("testWebdavImage"),
  loadWebdavImage: document.getElementById("loadWebdavImage"),
  saveWebdavConfig: document.getElementById("saveWebdavConfig"),
  loadWebdavHistory: document.getElementById("loadWebdavHistory"),
  deleteWebdavHistory: document.getElementById("deleteWebdavHistory"),
  resultWebdavStatus: document.getElementById("resultWebdavStatus"),
  resultWebdavUrl: document.getElementById("resultWebdavUrl"),
  resultWebdavSubPath: document.getElementById("resultWebdavSubPath"),
  resultWebdavUser: document.getElementById("resultWebdavUser"),
  resultWebdavPassword: document.getElementById("resultWebdavPassword"),
  resultWebdavHistory: document.getElementById("resultWebdavHistory"),
  saveResultWebdavConfig: document.getElementById("saveResultWebdavConfig"),
  loadResultWebdavHistory: document.getElementById("loadResultWebdavHistory"),
  deleteResultWebdavHistory: document.getElementById("deleteResultWebdavHistory"),
  webdavFileStatus: document.getElementById("webdavFileStatus"),
  webdavFileList: document.getElementById("webdavFileList"),
  addSelectedWebdavFiles: document.getElementById("addSelectedWebdavFiles"),
  dropZone: document.getElementById("dropZone"),
  fileInput: document.getElementById("fileInput"),
  imageStatus: document.getElementById("imageStatus"),
  imageList: document.getElementById("imageList"),
  runStatus: document.getElementById("runStatus"),
  runOcr: document.getElementById("runOcr"),
  testImageTransfer: document.getElementById("testImageTransfer"),
  saveResultWebdav: document.getElementById("saveResultWebdav"),
  resultText: document.getElementById("resultText"),
  historyList: document.getElementById("historyList"),
};

const configFields = {
  server_base_url: elements.serverBaseUrl,
  generate_path: elements.generatePath,
  status_path: elements.statusPath,
  request_timeout_seconds: elements.requestTimeout,
  user_id: elements.userId,
  password: elements.password,
  model: elements.model,
  keep_alive: elements.keepAlive,
  num_ctx: elements.numCtx,
  ocr_prompt: elements.ocrPrompt,
  result_webdav_url: elements.resultWebdavUrl,
  result_webdav_sub_path: elements.resultWebdavSubPath,
  result_webdav_user: elements.resultWebdavUser,
  result_webdav_password: elements.resultWebdavPassword,
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function humanSize(sizeBytes) {
  const value = Number(sizeBytes || 0);
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(2)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} bytes`;
}

function applyConfigToForm(config) {
  Object.entries(configFields).forEach(([key, element]) => {
    const value = config?.[key];
    element.value = value === null || value === undefined ? "" : String(value);
  });
  applyWebdavSlotsToForm(config);
}

function readConfigFromForm() {
  return {
    server_base_url: elements.serverBaseUrl.value.trim(),
    generate_path: elements.generatePath.value.trim(),
    status_path: elements.statusPath.value.trim(),
    request_timeout_seconds: Number(elements.requestTimeout.value || 600),
    user_id: elements.userId.value.trim(),
    password: elements.password.value,
    model: elements.model.value.trim(),
    keep_alive: elements.keepAlive.value.trim(),
    num_ctx: Number(elements.numCtx.value || 0),
    ocr_prompt: elements.ocrPrompt.value,
    webdav_url: elements.webdavUrl[1].value.trim(),
    webdav_user: elements.webdavUser[1].value.trim(),
    webdav_password: elements.webdavPassword[1].value,
    webdav_slots: [readWebdavSlot(1), readWebdavSlot(2)],
    result_webdav_url: elements.resultWebdavUrl.value.trim(),
    result_webdav_sub_path: elements.resultWebdavSubPath.value.trim(),
    result_webdav_user: elements.resultWebdavUser.value.trim(),
    result_webdav_password: elements.resultWebdavPassword.value,
  };
}

function readWebdavSlot(slot) {
  return {
    slot,
    url: elements.webdavUrl[slot].value.trim(),
    username: elements.webdavUser[slot].value.trim(),
    password: elements.webdavPassword[slot].value,
  };
}

function applyWebdavSlotsToForm(config) {
  const slots = Array.isArray(config?.webdav_slots) ? config.webdav_slots : [];
  [1, 2].forEach((slot) => {
    const value = slots.find((entry) => Number(entry.slot) === slot) || {};
    elements.webdavUrl[slot].value = value.url || (slot === 1 ? config?.webdav_url || "" : "");
    elements.webdavUser[slot].value = value.username || (slot === 1 ? config?.webdav_user || "" : "");
    elements.webdavPassword[slot].value = value.password || (slot === 1 ? config?.webdav_password || "" : "");
  });
}

function activateWebdavTab(slot) {
  state.activeWebdavSlot = Number(slot) === 2 ? 2 : 1;
  elements.webdavTabs.forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.webdavTab) === state.activeWebdavSlot);
  });
  elements.webdavPanels.forEach((panel) => {
    panel.classList.toggle("active", Number(panel.dataset.webdavPanel) === state.activeWebdavSlot);
  });
}

function formatElapsedSeconds(startedAt) {
  const elapsedMs = Math.max(0, Date.now() - startedAt);
  return Math.floor(elapsedMs / 1000);
}

function updateOcrTimerStatus() {
  if (!state.ocrStartedAt) return;
  elements.runStatus.textContent = `OCR 실행 중: ${formatElapsedSeconds(state.ocrStartedAt)}초 경과`;
}

function startOcrTimer() {
  stopOcrTimer();
  state.ocrRunning = true;
  state.ocrStartedAt = Date.now();
  elements.runOcr.disabled = true;
  updateOcrTimerStatus();
  state.ocrTimerId = window.setInterval(updateOcrTimerStatus, 250);
}

function stopOcrTimer() {
  if (state.ocrTimerId) {
    window.clearInterval(state.ocrTimerId);
  }
  state.ocrTimerId = null;
  state.ocrStartedAt = 0;
  state.ocrRunning = false;
  elements.runOcr.disabled = false;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      const marker = "base64,";
      const offset = value.indexOf(marker);
      resolve(offset >= 0 ? value.slice(offset + marker.length) : value);
    };
    reader.onerror = () => reject(reader.error || new Error(`파일 읽기 실패: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function fileToImageItem(file, source = "file") {
  if (!file.type.startsWith("image/")) {
    throw new Error(`이미지만 지원합니다: ${file.name || file.type || "unknown"}`);
  }
  const contentBase64 = await fileToBase64(file);
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: file.name || `${source}-${new Date().toISOString().replaceAll(":", "-")}.png`,
    mime_type: file.type || "image/png",
    size: file.size || 0,
    source,
    selected: true,
    previewUrl: URL.createObjectURL(file),
    content_base64: contentBase64,
  };
}

async function addFiles(fileList, source = "file") {
  const files = [...(fileList || [])];
  if (!files.length) return;
  const added = [];
  for (const file of files) {
    added.push(await fileToImageItem(file, source));
  }
  state.images.push(...added);
  renderImages();
}

function addRemoteImageItem(image) {
  const mimeType = image.mime_type || "image/png";
  state.images.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: image.name || "webdav-image",
    mime_type: mimeType,
    size: image.size || 0,
    source: image.source || "webdav",
    url: image.url || "",
    selected: true,
    previewUrl: `data:${mimeType};base64,${image.content_base64}`,
    content_base64: image.content_base64,
  });
  renderImages();
}

function renderWebdavFiles() {
  if (!state.webdavFiles.length) {
    elements.webdavFileList.innerHTML = "";
    elements.addSelectedWebdavFiles.disabled = true;
    return;
  }
  const selectedCount = state.webdavFiles.filter((file) => file.selected).length;
  elements.addSelectedWebdavFiles.disabled = selectedCount === 0;
  elements.webdavFileStatus.textContent = `원격 이미지 ${state.webdavFiles.length}개 발견 · ${selectedCount}개 선택됨`;
  elements.webdavFileList.innerHTML = state.webdavFiles.map((file) => `
    <label class="remote-file-item">
      <input type="checkbox" data-webdav-file="${escapeHtml(file.id)}" ${file.selected ? "checked" : ""}>
      <span>
        <strong>${escapeHtml(file.name || "image")}</strong>
        <small>${escapeHtml(file.content_type || "image")} · ${file.content_length === null || file.content_length === undefined ? "크기 확인 불가" : humanSize(file.content_length)}</small>
        <small>${escapeHtml(file.url || file.href || "")}</small>
      </span>
    </label>
  `).join("");
  elements.webdavFileList.querySelectorAll("[data-webdav-file]").forEach((input) => {
    input.addEventListener("change", () => {
      const file = state.webdavFiles.find((candidate) => candidate.id === input.dataset.webdavFile);
      if (file) {
        file.selected = input.checked;
        renderWebdavFiles();
      }
    });
  });
}

function applyWebdavSearchStatus(status) {
  const files = Array.isArray(status.matched_images) ? status.matched_images : [];
  state.webdavFiles = files.map((file, index) => ({
    id: file.id || `webdav-file-${Date.now()}-${index}`,
    slot: Number(file.slot || status.slot || state.activeWebdavSlot),
    name: file.name || file.href || `webdav-image-${index + 1}`,
    url: file.url || file.href || status.url || "",
    href: file.href || file.url || "",
    content_type: file.content_type || status.content_type || "image",
    content_length: file.content_length === undefined ? null : file.content_length,
    selected: true,
  }));
  renderWebdavFiles();
}

function renderImages() {
  const selectedCount = state.images.filter((image) => image.selected).length;
  elements.imageStatus.textContent = state.images.length
    ? `${state.images.length}개 이미지 준비됨 · ${selectedCount}개 전송 선택됨`
    : "선택된 이미지 없음";

  if (!state.images.length) {
    elements.imageList.innerHTML = "";
    return;
  }

  elements.imageList.innerHTML = state.images.map((image) => `
    <article class="image-card">
      <img src="${image.previewUrl}" alt="${escapeHtml(image.name)}">
      <div>
        <label class="image-select-row">
          <input type="checkbox" data-select-image="${image.id}" ${image.selected ? "checked" : ""}>
          <span>프롬프트 전송에 포함</span>
        </label>
        <strong>${escapeHtml(image.name)}</strong>
        <span>${escapeHtml(image.mime_type)} · ${humanSize(image.size)} · ${escapeHtml(image.source)}</span>
      </div>
      <button class="secondary icon-button" type="button" data-remove-image="${image.id}" title="삭제">×</button>
    </article>
  `).join("");

  elements.imageList.querySelectorAll("[data-select-image]").forEach((input) => {
    input.addEventListener("change", () => {
      const image = state.images.find((candidate) => candidate.id === input.dataset.selectImage);
      if (image) {
        image.selected = input.checked;
        renderImages();
      }
    });
  });

  elements.imageList.querySelectorAll("[data-remove-image]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = state.images.findIndex((image) => image.id === button.dataset.removeImage);
      if (index >= 0) {
        URL.revokeObjectURL(state.images[index].previewUrl);
        state.images.splice(index, 1);
        renderImages();
      }
    });
  });
}

function renderHistory() {
  if (!state.history.length) {
    elements.historyList.innerHTML = `<div class="empty-note">저장된 결과 없음</div>`;
    return;
  }
  elements.historyList.innerHTML = state.history.map((entry) => {
    const preview = String(entry.text || "").trim() || "(empty)";
    return `
      <button class="history-item" type="button" data-history-id="${escapeHtml(entry.id)}">
        <span>${escapeHtml(entry.created_at || "")}</span>
        <strong>${escapeHtml((entry.image_names || []).join(", ") || "image")}</strong>
        <small>${escapeHtml(preview.length > 150 ? `${preview.slice(0, 150)}...` : preview)}</small>
      </button>
    `;
  }).join("");
  elements.historyList.querySelectorAll("[data-history-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const entry = state.history.find((candidate) => candidate.id === button.dataset.historyId);
      if (!entry) return;
      elements.resultText.textContent = formatOcrResultSection(entry, 0);
      elements.runStatus.textContent = `불러옴: ${entry.created_at || entry.id}`;
    });
  });
}

function imageMetaFromResult(result) {
  const images = Array.isArray(result.images) ? result.images : [];
  const webdavUrls = Array.isArray(result.webdav_urls) ? result.webdav_urls : [];
  const names = Array.isArray(result.image_names) ? result.image_names : [];
  return {
    names: names.length ? names : images.map((image) => image.name).filter(Boolean),
    urls: [
      ...images.map((image) => image.url).filter(Boolean),
      ...webdavUrls.filter(Boolean),
    ].filter((url, index, list) => list.indexOf(url) === index),
  };
}

function formatOcrResultSection(result, index) {
  const meta = imageMetaFromResult(result || {});
  const names = meta.names.length ? meta.names.join(", ") : `image ${index + 1}`;
  const lines = [`## ${index + 1}. ${names}`, `File: ${names}`];
  if (meta.urls.length) {
    lines.push(`WebDAV: ${meta.urls.join(", ")}`);
  }
  lines.push("", String(result?.text || ""));
  return lines.join("\n");
}

function renderWebdavHistory() {
  if (!state.webdavHistory.length) {
    elements.webdavHistory.innerHTML = `<option value="">저장된 설정 없음</option>`;
    elements.webdavHistory.disabled = true;
    elements.loadWebdavHistory.disabled = true;
    elements.deleteWebdavHistory.disabled = true;
    return;
  }
  elements.webdavHistory.disabled = false;
  elements.loadWebdavHistory.disabled = false;
  elements.deleteWebdavHistory.disabled = false;
  elements.webdavHistory.innerHTML = state.webdavHistory.map((entry) => `
    <option value="${escapeHtml(entry.id)}">${escapeHtml(entry.label || entry.url || entry.id)}</option>
  `).join("");
}

function selectedWebdavHistoryEntry() {
  const id = elements.webdavHistory.value;
  return state.webdavHistory.find((entry) => entry.id === id);
}

function applyWebdavHistoryEntry(entry) {
  if (!entry) {
    elements.webdavStatus.textContent = "불러올 WebDAV 설정을 선택해 주세요.";
    return;
  }
  const slot = Number(entry.slot) === 2 ? 2 : state.activeWebdavSlot;
  activateWebdavTab(slot);
  elements.webdavUrl[slot].value = entry.url || "";
  elements.webdavUser[slot].value = entry.username || "";
  elements.webdavPassword[slot].value = entry.password || "";
  elements.webdavStatus.textContent = `설정 불러옴: ${entry.label || entry.url || entry.id}`;
}

function renderResultWebdavHistory() {
  if (!state.resultWebdavHistory.length) {
    elements.resultWebdavHistory.innerHTML = `<option value="">저장된 결과 경로 없음</option>`;
    elements.resultWebdavHistory.disabled = true;
    elements.loadResultWebdavHistory.disabled = true;
    elements.deleteResultWebdavHistory.disabled = true;
    return;
  }
  elements.resultWebdavHistory.disabled = false;
  elements.loadResultWebdavHistory.disabled = false;
  elements.deleteResultWebdavHistory.disabled = false;
  elements.resultWebdavHistory.innerHTML = state.resultWebdavHistory.map((entry) => `
    <option value="${escapeHtml(entry.id)}">${escapeHtml(entry.label || entry.url || entry.id)}</option>
  `).join("");
}

function selectedResultWebdavHistoryEntry() {
  const id = elements.resultWebdavHistory.value;
  return state.resultWebdavHistory.find((entry) => entry.id === id);
}

function applyResultWebdavHistoryEntry(entry) {
  if (!entry) {
    elements.resultWebdavStatus.textContent = "불러올 결과 저장 경로를 선택해 주세요.";
    return;
  }
  elements.resultWebdavUrl.value = entry.url || "";
  elements.resultWebdavSubPath.value = entry.sub_path || "";
  elements.resultWebdavUser.value = entry.username || "";
  elements.resultWebdavPassword.value = entry.password || "";
  elements.resultWebdavStatus.textContent = `경로 불러옴: ${entry.label || entry.url || entry.id}`;
}

async function loadInitialState() {
  const data = await requestJson("/api/state");
  state.config = data.config;
  state.history = data.history || [];
  state.webdavHistory = data.webdav_history || [];
  state.resultWebdavHistory = data.result_webdav_history || [];
  applyConfigToForm(state.config);
  renderHistory();
  renderWebdavHistory();
  renderResultWebdavHistory();
  elements.connectionStatus.textContent = state.config?.server_base_url || "설정 대기";
}

async function saveConfig() {
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: readConfigFromForm()}),
  });
  state.config = data.config;
  state.webdavHistory = data.webdav_history || state.webdavHistory;
  state.resultWebdavHistory = data.result_webdav_history || state.resultWebdavHistory;
  applyConfigToForm(state.config);
  renderWebdavHistory();
  renderResultWebdavHistory();
  elements.connectionStatus.textContent = "설정 저장됨";
}

async function testConnection() {
  elements.connectionStatus.textContent = "연결 확인 중";
  const data = await requestJson("/api/test-connection", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: readConfigFromForm()}),
  });
  const status = data.status || {};
  elements.connectionStatus.textContent = `연결됨 ${status.model || status.status_url || ""}`.trim();
}

async function pasteClipboardImage() {
  if (!navigator.clipboard?.read) {
    elements.imageStatus.textContent = "이 브라우저는 클립보드 이미지 읽기를 지원하지 않습니다.";
    return;
  }
  const items = await navigator.clipboard.read();
  const files = [];
  for (const item of items) {
    const imageType = item.types.find((type) => type.startsWith("image/"));
    if (!imageType) continue;
    const blob = await item.getType(imageType);
    files.push(new File([blob], `clipboard-${Date.now()}.png`, {type: imageType}));
  }
  if (!files.length) {
    elements.imageStatus.textContent = "클립보드에서 이미지를 찾지 못했습니다.";
    return;
  }
  await addFiles(files, "clipboard");
}

async function loadWebdavImage() {
  elements.loadWebdavImage.disabled = true;
  elements.webdavStatus.textContent = "WebDAV 경로 검색 중";
  elements.webdavFileStatus.textContent = "원격 파일 검색 중";
  try {
    const slot = state.activeWebdavSlot;
    const data = await requestJson("/api/webdav-image/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        slot,
        url: elements.webdavUrl[slot].value.trim(),
        username: elements.webdavUser[slot].value.trim(),
        password: elements.webdavPassword[slot].value,
      }),
    });
    const status = data.status || {};
    state.webdavHistory = data.webdav_history || state.webdavHistory;
    renderWebdavHistory();
    applyWebdavSearchStatus(status);
    elements.webdavStatus.textContent = `주소 ${slot} 검색됨: 원격 이미지 ${Number(status.matched_image_count || state.webdavFiles.length)}개`;
  } catch (error) {
    elements.webdavStatus.textContent = `실패: ${error}`;
    elements.webdavFileStatus.textContent = "원격 파일 검색 실패";
    state.webdavFiles = [];
    renderWebdavFiles();
  } finally {
    elements.loadWebdavImage.disabled = false;
  }
}

async function testWebdavImage() {
  elements.testWebdavImage.disabled = true;
  elements.webdavStatus.textContent = "이미지 경로 확인 중";
  try {
    const slot = state.activeWebdavSlot;
    const data = await requestJson("/api/webdav-image/test", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        slot,
        url: elements.webdavUrl[slot].value.trim(),
        username: elements.webdavUser[slot].value.trim(),
        password: elements.webdavPassword[slot].value,
      }),
    });
    const status = data.status || {};
    state.webdavHistory = data.webdav_history || state.webdavHistory;
    renderWebdavHistory();
    applyWebdavSearchStatus(status);
    if (Array.isArray(status.matched_images) && status.matched_images.length) {
      const firstImage = status.matched_images[0];
      const count = Number(status.matched_image_count || status.matched_images.length);
      elements.webdavStatus.textContent = `주소 ${slot}에서 이미지 ${count}개 발견: ${firstImage.name || firstImage.href || "image"}`;
      return;
    }
    const sizeText = status.content_length === undefined || status.content_length === null
      ? "크기 확인 불가"
      : humanSize(status.content_length);
    elements.webdavStatus.textContent = `주소 ${slot} 확인됨: ${status.name || "image"} · ${status.content_type || "image"} · ${sizeText}`;
  } catch (error) {
    elements.webdavStatus.textContent = `경로 확인 실패: ${error}`;
    elements.webdavFileStatus.textContent = "원격 파일 확인 실패";
    state.webdavFiles = [];
    renderWebdavFiles();
  } finally {
    elements.testWebdavImage.disabled = false;
  }
}

async function saveWebdavConfig() {
  elements.saveWebdavConfig.disabled = true;
  elements.webdavStatus.textContent = "WebDAV 설정 저장 중";
  try {
    const slot = state.activeWebdavSlot;
    const data = await requestJson("/api/webdav-config/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        slot,
        url: elements.webdavUrl[slot].value.trim(),
        username: elements.webdavUser[slot].value.trim(),
        password: elements.webdavPassword[slot].value,
      }),
    });
    state.config = data.config || state.config;
    state.webdavHistory = data.webdav_history || state.webdavHistory;
    renderWebdavHistory();
    elements.webdavStatus.textContent = "WebDAV 설정 저장됨";
  } catch (error) {
    elements.webdavStatus.textContent = `설정 저장 실패: ${error}`;
  } finally {
    elements.saveWebdavConfig.disabled = false;
  }
}

async function addSelectedWebdavFiles() {
  const selectedFiles = state.webdavFiles.filter((file) => file.selected);
  if (!selectedFiles.length) {
    elements.webdavFileStatus.textContent = "추가할 WebDAV 파일을 선택해 주세요.";
    return;
  }
  elements.addSelectedWebdavFiles.disabled = true;
  elements.webdavFileStatus.textContent = "선택한 WebDAV 파일 불러오는 중";
  let addedCount = 0;
  try {
    for (const file of selectedFiles) {
      const slot = Number(file.slot || state.activeWebdavSlot) === 2 ? 2 : 1;
      const data = await requestJson("/api/webdav-image", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          config: readConfigFromForm(),
          slot,
          url: file.url,
          username: elements.webdavUser[slot].value.trim(),
          password: elements.webdavPassword[slot].value,
        }),
      });
      addRemoteImageItem(data.image || {});
      state.webdavHistory = data.webdav_history || state.webdavHistory;
      file.selected = false;
      addedCount += 1;
    }
    renderWebdavHistory();
    elements.webdavFileStatus.textContent = `WebDAV 파일 ${addedCount}개를 이미지 목록에 추가했습니다.`;
  } catch (error) {
    elements.webdavFileStatus.textContent = `WebDAV 파일 추가 실패: ${error}`;
  } finally {
    renderWebdavFiles();
  }
}

async function downloadSelectedWebdavFilesForOcr() {
  const selectedFiles = state.webdavFiles.filter((file) => file.selected);
  if (!selectedFiles.length) {
    return 0;
  }
  elements.webdavFileStatus.textContent = "OCR 전송을 위해 선택한 WebDAV 파일 불러오는 중";
  let addedCount = 0;
  for (const file of selectedFiles) {
    const slot = Number(file.slot || state.activeWebdavSlot) === 2 ? 2 : 1;
    const data = await requestJson("/api/webdav-image", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        slot,
        url: file.url,
        username: elements.webdavUser[slot].value.trim(),
        password: elements.webdavPassword[slot].value,
      }),
    });
    addRemoteImageItem(data.image || {});
    state.webdavHistory = data.webdav_history || state.webdavHistory;
    file.selected = false;
    addedCount += 1;
  }
  renderWebdavHistory();
  renderWebdavFiles();
  elements.webdavFileStatus.textContent = `WebDAV 파일 ${addedCount}개를 OCR 이미지 목록에 추가했습니다.`;
  return addedCount;
}

async function deleteSelectedWebdavHistory() {
  const entry = selectedWebdavHistoryEntry();
  if (!entry) {
    elements.webdavStatus.textContent = "삭제할 WebDAV 설정을 선택해 주세요.";
    return;
  }
  const data = await requestJson("/api/webdav-history/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({id: entry.id}),
  });
  state.webdavHistory = data.webdav_history || [];
  renderWebdavHistory();
  elements.webdavStatus.textContent = "WebDAV 설정을 삭제했습니다.";
}

async function saveResultWebdavConfig() {
  elements.saveResultWebdavConfig.disabled = true;
  elements.resultWebdavStatus.textContent = "결과 저장 경로 저장 중";
  try {
    const data = await requestJson("/api/result-webdav-config/save", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        url: elements.resultWebdavUrl.value.trim(),
        sub_path: elements.resultWebdavSubPath.value.trim(),
        username: elements.resultWebdavUser.value.trim(),
        password: elements.resultWebdavPassword.value,
      }),
    });
    state.config = data.config || state.config;
    state.resultWebdavHistory = data.result_webdav_history || state.resultWebdavHistory;
    applyConfigToForm(state.config);
    renderResultWebdavHistory();
    elements.resultWebdavStatus.textContent = "결과 저장 경로 저장됨";
  } catch (error) {
    elements.resultWebdavStatus.textContent = `결과 저장 경로 저장 실패: ${error}`;
  } finally {
    elements.saveResultWebdavConfig.disabled = false;
  }
}

async function deleteSelectedResultWebdavHistory() {
  const entry = selectedResultWebdavHistoryEntry();
  if (!entry) {
    elements.resultWebdavStatus.textContent = "삭제할 결과 저장 경로를 선택해 주세요.";
    return;
  }
  const data = await requestJson("/api/result-webdav-history/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({id: entry.id}),
  });
  state.resultWebdavHistory = data.result_webdav_history || [];
  renderResultWebdavHistory();
  elements.resultWebdavStatus.textContent = "결과 저장 경로를 삭제했습니다.";
}

async function saveResultToWebdav() {
  const content = elements.resultText.textContent || "";
  if (!content.trim() || content.includes("OCR 寃곌낵媛") || content.includes("아직 OCR 결과")) {
    elements.resultWebdavStatus.textContent = "저장할 OCR 결과가 없습니다.";
    return;
  }
  elements.saveResultWebdav.disabled = true;
  elements.resultWebdavStatus.textContent = "OCR 결과 WebDAV 저장 중";
  try {
    const data = await requestJson("/api/ocr-result/save-webdav", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        content,
        url: elements.resultWebdavUrl.value.trim(),
        sub_path: elements.resultWebdavSubPath.value.trim(),
        username: elements.resultWebdavUser.value.trim(),
        password: elements.resultWebdavPassword.value,
      }),
    });
    const status = data.status || {};
    state.resultWebdavHistory = status.history || state.resultWebdavHistory;
    renderResultWebdavHistory();
    elements.resultWebdavStatus.textContent = `저장 완료: ${status.file_name || ""}`;
    elements.runStatus.textContent = `OCR 결과 저장 완료: ${status.url || ""}`;
  } catch (error) {
    elements.resultWebdavStatus.textContent = `OCR 결과 저장 실패: ${error}`;
  } finally {
    elements.saveResultWebdav.disabled = false;
  }
}

async function runOcr() {
  if (state.ocrRunning) {
    return;
  }
  const selectedRemoteCount = state.webdavFiles.filter((file) => file.selected).length;
  if (!state.images.length) {
    if (!selectedRemoteCount) {
      elements.runStatus.textContent = "이미지를 먼저 추가하거나 WebDAV 원격 파일을 선택해 주세요.";
      return;
    }
  }
  let selectedImages = state.images.filter((image) => image.selected);
  if (!selectedImages.length) {
    if (!selectedRemoteCount) {
      elements.runStatus.textContent = "프롬프트 전송에 포함할 이미지를 선택해 주세요.";
      return;
    }
  }
  startOcrTimer();
  try {
    const addedRemoteCount = await downloadSelectedWebdavFilesForOcr();
    selectedImages = state.images.filter((image) => image.selected);
    if (!selectedImages.length) {
      elements.runStatus.textContent = "OCR로 전송할 이미지가 없습니다.";
      return;
    }
    const results = [];
    let lastHistory = state.history;
    let failedCount = 0;
    for (let index = 0; index < selectedImages.length; index += 1) {
      const image = selectedImages[index];
      elements.runStatus.textContent = `OCR 실행 중: ${index + 1}/${selectedImages.length} · ${image.name || "image"} · ${formatElapsedSeconds(state.ocrStartedAt)}초 경과`;
      const payloadImage = {
        name: image.name,
        mime_type: image.mime_type,
        source: image.source,
        url: image.url,
        content_base64: image.content_base64,
      };
      try {
        const data = await requestJson("/api/ocr", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            config: readConfigFromForm(),
            prompt: elements.ocrPrompt.value,
            images: [payloadImage],
          }),
        });
        const result = data.result || {};
        results.push(result);
        lastHistory = data.history || lastHistory;
      } catch (error) {
        failedCount += 1;
        results.push({
          image_names: [image.name || `image ${index + 1}`],
          images: [{
            name: image.name || `image ${index + 1}`,
            mime_type: image.mime_type || "",
            source: image.source || "",
            url: image.url || "",
          }],
          webdav_urls: image.url ? [image.url] : [],
          text: `[OCR 실패]\n${String(error)}`,
          elapsed_seconds: 0,
          image_count: 1,
          server_image_count: 0,
          error: true,
        });
      }
      elements.resultText.textContent = results
        .map((item, resultIndex) => formatOcrResultSection(item, resultIndex))
        .join("\n\n");
    }
    state.history = lastHistory;
    const totalElapsed = results.reduce((sum, item) => sum + Number(item.elapsed_seconds || 0), 0);
    const totalServerCount = results.reduce((sum, item) => sum + Number(item.server_image_count || item.image_count || 0), 0);
    const imageCount = `${selectedImages.length}개`;
    const serverImageCount = totalServerCount ? `${totalServerCount}개` : "확인 불가";
    const remoteText = addedRemoteCount ? ` · WebDAV ${addedRemoteCount}개 포함` : "";
    const failText = failedCount ? ` · 실패 ${failedCount}개` : "";
    elements.runStatus.textContent = `완료: ${totalElapsed.toFixed(2)}초 · 이미지 ${imageCount} 순차 전송 · 서버 수신 ${serverImageCount}${remoteText}${failText}`;
    renderHistory();
  } catch (error) {
    elements.runStatus.textContent = `OCR 실패: ${error}`;
  } finally {
    stopOcrTimer();
  }
}

function selectedImagePayloads() {
  return state.images
    .filter((image) => image.selected)
    .map(({name, mime_type, source, url, content_base64}) => ({name, mime_type, source, url, content_base64}));
}

async function testImageTransfer() {
  elements.testImageTransfer.disabled = true;
  elements.runStatus.textContent = "이미지 전송 테스트 중";
  try {
    const payloadImages = selectedImagePayloads();
    const data = await requestJson("/api/test-image-transfer", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfigFromForm(),
        images: payloadImages,
      }),
    });
    const status = data.status || {};
    const clientCount = status.client_image_count === undefined || status.client_image_count === null
      ? "확인 불가"
      : `${Number(status.client_image_count || 0)}개`;
    const serverCount = status.server_image_count === undefined || status.server_image_count === null
      ? "확인 불가"
      : `${Number(status.server_image_count || 0)}개`;
    const sourceLabel = payloadImages.length ? "선택 이미지" : "내장 테스트 이미지";
    elements.runStatus.textContent = `이미지 전송 테스트 완료: ${sourceLabel} ${clientCount} 전송 · 서버 수신 ${serverCount} · ${(Number(status.elapsed_seconds || 0)).toFixed(2)}초`;
  } catch (error) {
    elements.runStatus.textContent = `이미지 전송 테스트 실패: ${error}`;
  } finally {
    elements.testImageTransfer.disabled = false;
  }
}

async function copyResult() {
  const text = elements.resultText.textContent || "";
  if (!text.trim()) {
    elements.runStatus.textContent = "복사할 결과가 없습니다.";
    return;
  }
  await navigator.clipboard.writeText(text);
  elements.runStatus.textContent = "결과를 클립보드에 복사했습니다.";
}

function clearResult() {
  elements.resultText.textContent = "아직 OCR 결과가 없습니다.";
  elements.runStatus.textContent = "실행 대기";
}

document.getElementById("saveConfig").addEventListener("click", () => saveConfig().catch((error) => {
  elements.connectionStatus.textContent = String(error);
}));
document.getElementById("testConnection").addEventListener("click", () => testConnection().catch((error) => {
  elements.connectionStatus.textContent = `연결 실패: ${error}`;
}));
document.getElementById("pasteClipboard").addEventListener("click", () => pasteClipboardImage().catch((error) => {
  elements.imageStatus.textContent = `클립보드 읽기 실패: ${error}`;
}));
document.getElementById("loadWebdavImage").addEventListener("click", () => loadWebdavImage().catch((error) => {
  elements.webdavStatus.textContent = `실패: ${error}`;
  elements.loadWebdavImage.disabled = false;
}));
document.getElementById("saveWebdavConfig").addEventListener("click", () => saveWebdavConfig().catch((error) => {
  elements.webdavStatus.textContent = `설정 저장 실패: ${error}`;
  elements.saveWebdavConfig.disabled = false;
}));
document.getElementById("testWebdavImage").addEventListener("click", () => testWebdavImage().catch((error) => {
  elements.webdavStatus.textContent = `경로 확인 실패: ${error}`;
  elements.testWebdavImage.disabled = false;
}));
document.getElementById("addSelectedWebdavFiles").addEventListener("click", () => addSelectedWebdavFiles().catch((error) => {
  elements.webdavFileStatus.textContent = `WebDAV 파일 추가 실패: ${error}`;
  renderWebdavFiles();
}));
document.getElementById("loadWebdavHistory").addEventListener("click", () => applyWebdavHistoryEntry(selectedWebdavHistoryEntry()));
document.getElementById("deleteWebdavHistory").addEventListener("click", () => deleteSelectedWebdavHistory().catch((error) => {
  elements.webdavStatus.textContent = `삭제 실패: ${error}`;
}));
document.getElementById("saveResultWebdavConfig").addEventListener("click", () => saveResultWebdavConfig().catch((error) => {
  elements.resultWebdavStatus.textContent = `결과 저장 경로 저장 실패: ${error}`;
  elements.saveResultWebdavConfig.disabled = false;
}));
document.getElementById("loadResultWebdavHistory").addEventListener("click", () => applyResultWebdavHistoryEntry(selectedResultWebdavHistoryEntry()));
document.getElementById("deleteResultWebdavHistory").addEventListener("click", () => deleteSelectedResultWebdavHistory().catch((error) => {
  elements.resultWebdavStatus.textContent = `경로 삭제 실패: ${error}`;
}));
elements.webdavTabs.forEach((button) => {
  button.addEventListener("click", () => activateWebdavTab(Number(button.dataset.webdavTab)));
});
document.getElementById("runOcr").addEventListener("click", () => runOcr().catch((error) => {
  elements.runStatus.textContent = `OCR 실패: ${error}`;
}));
document.getElementById("testImageTransfer").addEventListener("click", () => testImageTransfer().catch((error) => {
  elements.runStatus.textContent = `이미지 전송 테스트 실패: ${error}`;
  elements.testImageTransfer.disabled = false;
}));
document.getElementById("copyResult").addEventListener("click", () => copyResult().catch((error) => {
  elements.runStatus.textContent = `복사 실패: ${error}`;
}));
document.getElementById("saveResultWebdav").addEventListener("click", () => saveResultToWebdav().catch((error) => {
  elements.resultWebdavStatus.textContent = `OCR 결과 저장 실패: ${error}`;
  elements.saveResultWebdav.disabled = false;
}));
document.getElementById("clearResult").addEventListener("click", clearResult);
document.getElementById("clearHistory").addEventListener("click", async () => {
  const data = await requestJson("/api/history/clear", {method: "POST"});
  state.history = data.history || [];
  renderHistory();
});

elements.dropZone.addEventListener("click", () => elements.fileInput.click());
elements.fileInput.addEventListener("change", async (event) => {
  try {
    await addFiles(event.target.files || [], "file");
  } catch (error) {
    elements.imageStatus.textContent = String(error);
  } finally {
    event.target.value = "";
  }
});
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
elements.dropZone.addEventListener("drop", async (event) => {
  event.preventDefault();
  elements.dropZone.classList.remove("dragover");
  try {
    await addFiles(event.dataTransfer?.files || [], "drop");
  } catch (error) {
    elements.imageStatus.textContent = String(error);
  }
});
window.addEventListener("paste", async (event) => {
  const files = [...(event.clipboardData?.files || [])].filter((file) => file.type.startsWith("image/"));
  if (files.length) {
    await addFiles(files, "paste");
  }
});

loadInitialState().catch((error) => {
  elements.connectionStatus.textContent = String(error);
});
