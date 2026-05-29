const state = {
  config: null,
  running: false,
  lastBook: "",
};

const elements = {
  connectionStatus: document.getElementById("connectionStatus"),
  serverBaseUrl: document.getElementById("serverBaseUrl"),
  generatePath: document.getElementById("generatePath"),
  statusPath: document.getElementById("statusPath"),
  userId: document.getElementById("userId"),
  password: document.getElementById("password"),
  model: document.getElementById("model"),
  requestTimeout: document.getElementById("requestTimeout"),
  numCtx: document.getElementById("numCtx"),
  targetWords: document.getElementById("targetWords"),
  keepAlive: document.getElementById("keepAlive"),
  saveConfig: document.getElementById("saveConfig"),
  testConnection: document.getElementById("testConnection"),
  runAgents: document.getElementById("runAgents"),
  backboneText: document.getElementById("backboneText"),
  backboneStatus: document.getElementById("backboneStatus"),
  runStatus: document.getElementById("runStatus"),
  agentLog: document.getElementById("agentLog"),
  bookOutput: document.getElementById("bookOutput"),
  outputPath: document.getElementById("outputPath"),
  copyBook: document.getElementById("copyBook"),
};

function applyConfig(config) {
  elements.serverBaseUrl.value = config?.server_base_url || "";
  elements.generatePath.value = config?.generate_path || "/api/generate";
  elements.statusPath.value = config?.status_path || "/api/status";
  elements.userId.value = config?.user_id || "";
  elements.password.value = config?.password || "";
  elements.model.value = config?.model || "";
  elements.requestTimeout.value = config?.request_timeout_seconds || 600;
  elements.numCtx.value = config?.num_ctx || 8192;
  elements.targetWords.value = config?.target_words_per_chapter || 1800;
  elements.keepAlive.value = config?.keep_alive || "60m";
}

function readConfig() {
  return {
    server_base_url: elements.serverBaseUrl.value.trim(),
    generate_path: elements.generatePath.value.trim(),
    status_path: elements.statusPath.value.trim(),
    user_id: elements.userId.value.trim(),
    password: elements.password.value,
    model: elements.model.value.trim(),
    request_timeout_seconds: Number(elements.requestTimeout.value || 600),
    num_ctx: Number(elements.numCtx.value || 8192),
    target_words_per_chapter: Number(elements.targetWords.value || 1800),
    keep_alive: elements.keepAlive.value.trim(),
  };
}

async function requestJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error(`Writing Mach 서비스에 연결할 수 없습니다: ${url}. client_service.py 실행 여부를 확인해 주세요. (${error})`);
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function setRunning(running) {
  state.running = running;
  elements.runAgents.disabled = running;
  elements.saveConfig.disabled = running;
  elements.testConnection.disabled = running;
}

async function loadState() {
  const data = await requestJson("/api/state");
  state.config = data.config;
  applyConfig(state.config);
  elements.backboneText.value = data.backbone || "";
  elements.connectionStatus.textContent = state.config?.server_base_url || "설정 대기";
  elements.backboneStatus.textContent = "story_backbone.md 로드됨";
}

async function saveConfig() {
  const data = await requestJson("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: readConfig()}),
  });
  state.config = data.config;
  applyConfig(state.config);
  elements.connectionStatus.textContent = "설정 저장됨";
}

async function testConnection() {
  elements.connectionStatus.textContent = "연결 확인 중";
  const data = await requestJson("/api/test-connection", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({config: readConfig()}),
  });
  const status = data.status || {};
  elements.connectionStatus.textContent = `연결 정상: ${status.server_base_url || ""} ${status.model || ""}`.trim();
}

function formatAgentLog(result) {
  const lines = [
    `제목: ${result.title || "-"}`,
    `챕터 수: ${result.chapter_count || 0}`,
    `실행 시간: ${Number(result.elapsed_seconds || 0).toFixed(2)}초`,
    `최종 원고: ${result.output_path || "-"}`,
    `실행 로그: ${result.log_path || "-"}`,
    "",
    "## 메인 작가 조율 메모",
    result.coordinator_notes || "",
    "",
    "## 챕터 에이전트 출력 요약",
  ];
  (result.chapters || []).forEach((item, index) => {
    const title = item.chapter?.title || `${index + 1} 챕터`;
    const preview = String(item.draft || "").slice(0, 1000);
    lines.push(`\n### ${title}\n${preview}${String(item.draft || "").length > 1000 ? "\n..." : ""}`);
  });
  return lines.join("\n");
}

async function runAgents() {
  if (state.running) return;
  setRunning(true);
  elements.runStatus.textContent = "챕터 에이전트와 메인 작가 에이전트 실행 중입니다. 긴 원고는 시간이 걸릴 수 있습니다.";
  elements.agentLog.textContent = "실행 중...";
  try {
    const data = await requestJson("/api/write-book", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        config: readConfig(),
        backbone: elements.backboneText.value,
      }),
    });
    const result = data.result || {};
    state.lastBook = result.book || "";
    elements.agentLog.textContent = formatAgentLog(result);
    elements.bookOutput.textContent = state.lastBook || "최종 원고가 비어 있습니다.";
    elements.outputPath.textContent = result.output_path || "저장 경로 없음";
    elements.runStatus.textContent = `완료: ${Number(result.elapsed_seconds || 0).toFixed(2)}초`;
  } catch (error) {
    elements.runStatus.textContent = `실패: ${error}`;
    elements.agentLog.textContent = String(error);
  } finally {
    setRunning(false);
  }
}

async function copyBook() {
  const text = state.lastBook || elements.bookOutput.textContent || "";
  if (!text.trim()) {
    elements.runStatus.textContent = "복사할 최종 원고가 없습니다.";
    return;
  }
  await navigator.clipboard.writeText(text);
  elements.runStatus.textContent = "최종 원고를 클립보드에 복사했습니다.";
}

elements.saveConfig.addEventListener("click", () => saveConfig().catch((error) => {
  elements.connectionStatus.textContent = `설정 저장 실패: ${error}`;
}));
elements.testConnection.addEventListener("click", () => testConnection().catch((error) => {
  elements.connectionStatus.textContent = `연결 실패: ${error}`;
}));
elements.runAgents.addEventListener("click", () => runAgents());
elements.copyBook.addEventListener("click", () => copyBook().catch((error) => {
  elements.runStatus.textContent = `복사 실패: ${error}`;
}));

loadState().catch((error) => {
  elements.connectionStatus.textContent = String(error);
});
