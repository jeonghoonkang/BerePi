const DEFAULT_ROOT_URL = "";
const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"];
const SPOTIFY_TYPES = new Set(["track", "album", "playlist", "artist", "episode", "show"]);
const QUEUE_STORAGE_KEY = "tesla_direct_streaming_queue";
const QUEUE_URL_STORAGE_KEY = "tesla_direct_streaming_queue_url";
const QUEUE_SETTINGS_STORAGE_KEY = "tesla_direct_streaming_queue_settings";
const ROOT_MEMORY_STORAGE_KEY = "tesla_direct_streaming_root_memory";
const ROOT_MEMORY_META_STORAGE_KEY = "tesla_direct_streaming_root_memory_meta";

const state = {
  rootUrl: "",
  port: "",
  username: "",
  password: "",
  rootMemoryPassword: "",
  queueUrl: "",
  queuePort: "",
  queueUsername: "",
  queuePassword: "",
  currentPath: "/",
  entries: [],
  filteredEntries: [],
  selectedFiles: new Map(),
  queue: [],
  currentQueueIndex: -1,
};

const elements = {
  rootUrlInput: document.querySelector("#rootUrlInput"),
  portInput: document.querySelector("#portInput"),
  usernameInput: document.querySelector("#usernameInput"),
  passwordInput: document.querySelector("#passwordInput"),
  rootMemoryPasswordInput: document.querySelector("#rootMemoryPasswordInput"),
  queueUrlInput: document.querySelector("#queueUrlInput"),
  queuePortInput: document.querySelector("#queuePortInput"),
  queueUsernameInput: document.querySelector("#queueUsernameInput"),
  queuePasswordInput: document.querySelector("#queuePasswordInput"),
  currentPathInput: document.querySelector("#currentPathInput"),
  loadButton: document.querySelector("#loadButton"),
  saveRootMemoryButton: document.querySelector("#saveRootMemoryButton"),
  restoreRootMemoryButton: document.querySelector("#restoreRootMemoryButton"),
  upButton: document.querySelector("#upButton"),
  selectVisibleButton: document.querySelector("#selectVisibleButton"),
  clearSelectionButton: document.querySelector("#clearSelectionButton"),
  filterInput: document.querySelector("#filterInput"),
  browserList: document.querySelector("#browserList"),
  breadcrumb: document.querySelector("#breadcrumb"),
  visibleSummary: document.querySelector("#visibleSummary"),
  originalSummary: document.querySelector("#originalSummary"),
  recursiveFileCount: document.querySelector("#recursiveFileCount"),
  addSelectedButton: document.querySelector("#addSelectedButton"),
  playQueueButton: document.querySelector("#playQueueButton"),
  clearQueueButton: document.querySelector("#clearQueueButton"),
  loadQueueUrlButton: document.querySelector("#loadQueueUrlButton"),
  appendQueueUrlButton: document.querySelector("#appendQueueUrlButton"),
  saveQueueUrlButton: document.querySelector("#saveQueueUrlButton"),
  restoreQueueButton: document.querySelector("#restoreQueueButton"),
  queueList: document.querySelector("#queueList"),
  audioPlayer: document.querySelector("#audioPlayer"),
  spotifyPlayer: document.querySelector("#spotifyPlayer"),
  playerTitle: document.querySelector("#playerTitle"),
  playerHint: document.querySelector("#playerHint"),
  playPauseButton: document.querySelector("#playPauseButton"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  statusText: document.querySelector("#statusText"),
  nowPlaying: document.querySelector("#nowPlaying"),
  rootMemoryStorageStatus: document.querySelector("#rootMemoryStorageStatus"),
  rootMemorySavedStatus: document.querySelector("#rootMemorySavedStatus"),
  rootMemoryList: document.querySelector("#rootMemoryList"),
  itemTemplate: document.querySelector("#browserItemTemplate"),
  queueItemTemplate: document.querySelector("#queueItemTemplate"),
};

async function init() {
  const url = new URL(window.location.href);
  const storedQueueSettings = loadStoredQueueSettings();
  const requestedRoot = url.searchParams.get("root") || DEFAULT_ROOT_URL;
  const requestedPort = url.searchParams.get("port") || "";
  const requestedUsername = url.searchParams.get("username") || "";
  const requestedQueueUrl = url.searchParams.get("queue_url") || loadStoredQueueUrl();
  const requestedQueuePort = url.searchParams.get("queue_port") || storedQueueSettings.queuePort || "";
  const requestedQueueUsername = url.searchParams.get("queue_username") || storedQueueSettings.queueUsername || "";
  const requestedPath = url.searchParams.get("path") || "/";

  state.rootUrl = normalizeRootUrl(requestedRoot);
  state.port = normalizePort(requestedPort);
  state.username = requestedUsername;
  state.rootMemoryPassword = "";
  state.queueUrl = normalizeQueueUrl(requestedQueueUrl);
  state.queuePort = normalizePort(requestedQueuePort);
  state.queueUsername = requestedQueueUsername;
  state.currentPath = normalizeDirectoryPath(requestedPath);

  elements.rootUrlInput.value = state.rootUrl;
  elements.portInput.value = state.port;
  elements.usernameInput.value = state.username;
  elements.passwordInput.value = "";
  elements.rootMemoryPasswordInput.value = "";
  elements.queueUrlInput.value = state.queueUrl;
  elements.queuePortInput.value = state.queuePort;
  elements.queueUsernameInput.value = state.queueUsername;
  elements.queuePasswordInput.value = "";
  elements.currentPathInput.value = state.currentPath;
  restoreQueueFromStorage();
  updateRootMemoryDiagnostics();

  bindEvents();
  await tryAutoRestoreRootMemory();

  if (state.rootUrl) {
    loadDirectory();
  } else {
    renderBrowser([]);
    setStatus("Root URL 입력 필요");
  }
}

function bindEvents() {
  elements.loadButton.addEventListener("click", () => {
    syncRootStateFromInputs();
    state.queueUrl = normalizeQueueUrl(elements.queueUrlInput.value);
    state.queuePort = normalizePort(elements.queuePortInput.value);
    state.queueUsername = elements.queueUsernameInput.value.trim();
    state.queuePassword = elements.queuePasswordInput.value;
    state.currentPath = normalizeDirectoryPath(elements.currentPathInput.value);
    syncQueueInputs();
    loadDirectory();
  });

  elements.saveRootMemoryButton.addEventListener("click", async () => {
    syncRootStateFromInputs();
    await saveRootMemory();
  });

  elements.restoreRootMemoryButton.addEventListener("click", async () => {
    syncRootStateFromInputs();
    await restoreRootMemory(true);
  });

  elements.rootMemoryPasswordInput.addEventListener("change", async () => {
    syncRootStateFromInputs();
    await restoreRootMemory(false);
  });

  elements.upButton.addEventListener("click", () => {
    state.currentPath = getParentPath(state.currentPath);
    elements.currentPathInput.value = state.currentPath;
    loadDirectory();
  });

  elements.filterInput.addEventListener("input", () => {
    applyFilter(elements.filterInput.value);
  });

  elements.selectVisibleButton.addEventListener("click", () => {
    state.filteredEntries
      .filter((entry) => entry.type === "file")
      .forEach((entry) => {
        state.selectedFiles.set(entry.url, entry);
      });
    renderBrowser(state.filteredEntries);
  });

  elements.clearSelectionButton.addEventListener("click", () => {
    state.selectedFiles.clear();
    renderBrowser(state.filteredEntries);
  });

  elements.addSelectedButton.addEventListener("click", () => {
    const selected = Array.from(state.selectedFiles.values()).sort((a, b) => a.name.localeCompare(b.name));
    if (selected.length === 0) {
      setStatus("선택된 곡 없음");
      return;
    }

    const existingUrls = new Set(state.queue.map((entry) => entry.url));
    const uniqueSelected = selected.filter((entry) => !existingUrls.has(entry.url));
    state.queue = [...state.queue, ...uniqueSelected];
    renderQueue();
    persistQueue();
    setStatus(`${uniqueSelected.length}곡 큐에 추가`);
  });

  elements.clearQueueButton.addEventListener("click", () => {
    state.queue = [];
    state.currentQueueIndex = -1;
    renderQueue();
    clearPlayers();
    updateNowPlaying();
    persistQueue();
    setStatus("큐 비움");
  });

  elements.loadQueueUrlButton.addEventListener("click", () => {
    syncQueueStateFromInputs();
    loadQueueFromRemote(false);
  });

  elements.appendQueueUrlButton.addEventListener("click", () => {
    syncQueueStateFromInputs();
    loadQueueFromRemote(true);
  });

  elements.saveQueueUrlButton.addEventListener("click", () => {
    syncQueueStateFromInputs();
    saveQueueToRemote();
  });

  elements.restoreQueueButton.addEventListener("click", () => {
    restoreQueueFromStorage(true);
  });

  elements.playQueueButton.addEventListener("click", () => {
    if (state.queue.length === 0) {
      setStatus("재생 큐가 비어 있음");
      return;
    }

    if (state.currentQueueIndex < 0) {
      playTrackAtIndex(0);
      return;
    }

    elements.audioPlayer.play().catch(() => {
      setStatus("브라우저 재생 차단. 화면 터치 후 다시 시도");
    });
  });

  elements.playPauseButton.addEventListener("click", () => {
    if (state.queue.length > 0 && state.currentQueueIndex >= 0 && isSpotifyEntry(state.queue[state.currentQueueIndex])) {
      setStatus("Spotify Embed은 내부 컨트롤 또는 다음 곡 버튼 사용");
      return;
    }

    if (!elements.audioPlayer.src && state.queue.length > 0) {
      playTrackAtIndex(Math.max(state.currentQueueIndex, 0));
      return;
    }

    if (elements.audioPlayer.paused) {
      elements.audioPlayer.play().catch(() => {
        setStatus("브라우저 재생 차단. 화면 터치 후 다시 시도");
      });
    } else {
      elements.audioPlayer.pause();
      setStatus("일시정지");
    }
  });

  elements.prevButton.addEventListener("click", () => {
    if (state.currentQueueIndex > 0) {
      playTrackAtIndex(state.currentQueueIndex - 1);
    }
  });

  elements.nextButton.addEventListener("click", () => {
    if (state.currentQueueIndex + 1 < state.queue.length) {
      playTrackAtIndex(state.currentQueueIndex + 1);
    }
  });

  elements.audioPlayer.addEventListener("ended", () => {
    if (state.currentQueueIndex + 1 < state.queue.length) {
      playTrackAtIndex(state.currentQueueIndex + 1);
    } else {
      setStatus("재생 완료");
    }
  });

  elements.audioPlayer.addEventListener("play", () => setStatus("재생 중"));
  elements.audioPlayer.addEventListener("pause", () => {
    if (elements.audioPlayer.currentTime > 0 && !elements.audioPlayer.ended) {
      setStatus("일시정지");
    }
  });
}

async function loadDirectory() {
  if (!state.rootUrl) {
    setStatus("Root URL 입력 필요");
    return;
  }

  const targetUrl = buildDisplayUrl(state.currentPath);
  setStatus("목록 불러오는 중");
  elements.currentPathInput.value = state.currentPath;
  syncLocation();

  try {
    const response = await fetch(targetUrl, buildFetchOptions());
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const html = await response.text();
    state.entries = parseApacheDirectoryListing(html, targetUrl);
    applyFilter(elements.filterInput.value);
    renderBreadcrumb();
    updateRecursiveFileCount(targetUrl, html);
    setStatus(`목록 준비 완료 (${state.entries.length}개 항목)`);
  } catch (error) {
    renderBrowser([]);
    setStatus(`로드 실패: ${error.message}`);
  }
}

async function loadQueueFromRemote(append) {
  if (!state.queueUrl) {
    setStatus("Queue TXT URL 입력 필요");
    return;
  }

  syncLocation();
  persistQueueSettings();
  setStatus("Queue TXT 불러오는 중");

  try {
    const response = await fetch(buildQueueRequestUrl(), buildQueueFetchOptions());
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const text = await response.text();
    const imported = parseQueueText(text);
    if (imported.length === 0) {
      setStatus("Queue TXT에 곡이 없음");
      return;
    }

    const nextQueue = append ? [...state.queue] : [];
    const existingUrls = new Set(nextQueue.map((entry) => entry.url));
    imported.forEach((entry) => {
      if (!existingUrls.has(entry.url)) {
        existingUrls.add(entry.url);
        nextQueue.push(entry);
      }
    });

    state.queue = nextQueue;
    if (state.currentQueueIndex >= state.queue.length) {
      state.currentQueueIndex = state.queue.length - 1;
    }
    renderQueue();
    persistQueue();
    setStatus(`${imported.length}곡 Queue 반영`);
  } catch (error) {
    setStatus(`Queue 로드 실패: ${error.message}`);
  }
}

async function saveQueueToRemote() {
  if (!state.queueUrl) {
    setStatus("Queue TXT URL 입력 필요");
    return;
  }

  if (state.queue.length === 0) {
    setStatus("저장할 Queue가 비어 있음");
    return;
  }

  syncLocation();
  persistQueueSettings();
  setStatus("Queue TXT 저장 중");

  try {
    const fetchOptions = buildQueueFetchOptions();
    const response = await fetch(buildQueueRequestUrl(), {
      ...fetchOptions,
      method: "PUT",
      headers: {
        ...((fetchOptions.headers) || {}),
        "Content-Type": "text/plain; charset=utf-8",
      },
      body: serializeQueueText(),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    setStatus(`${state.queue.length}곡 Queue 저장 완료`);
  } catch (error) {
    setStatus(`Queue 저장 실패: ${error.message}`);
  }
}

function parseApacheDirectoryListing(html, baseUrl) {
  return parseDirectoryListingEntries(html, baseUrl)
    .filter((entry) => entry.type === "directory" || isAudioFile(entry.name))
    .sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "directory" ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
}

function parseDirectoryListingEntries(html, baseUrl) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const links = Array.from(doc.querySelectorAll("a[href]"));

  return links
    .map((anchor) => {
      const href = anchor.getAttribute("href");
      const label = anchor.textContent.trim();
      if (!href || !label || href.startsWith("?") || label === "Parent Directory") {
        return null;
      }

      const url = new URL(href, baseUrl);
      const pathname = decodeURIComponent(url.pathname);
      const isDirectory = href.endsWith("/") || label.endsWith("/");
      const name = label.replace(/\/$/, "");

      if (name === "..") {
        return null;
      }

      return {
        name,
        url: buildDisplayUrl(pathname),
        displayUrl: buildDisplayUrl(pathname),
        path: pathname,
        type: isDirectory ? "directory" : "file",
        sizeBytes: parseSizeBytes(anchor),
      };
    })
    .filter(Boolean);
}

function renderBrowser(entries) {
  elements.browserList.innerHTML = "";
  updateSummary(entries, state.entries);
  elements.recursiveFileCount.textContent = "전체 하위 파일 계산 중...";

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "표시할 폴더나 오디오 파일이 없습니다.";
    elements.browserList.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const fragment = elements.itemTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".browser-item");
    const icon = fragment.querySelector(".item-icon");
    const link = fragment.querySelector(".item-link");
    const subtitle = fragment.querySelector(".item-subtitle");
    const checkbox = fragment.querySelector(".item-checkbox");
    const selector = fragment.querySelector(".item-selector");

    icon.textContent = entry.type === "directory" ? "📁" : "♪";
    link.textContent = entry.name;
    subtitle.textContent = entry.type === "directory" ? "폴더 열기" : entry.displayUrl;

    if (entry.type === "directory") {
      link.addEventListener("click", () => {
        state.currentPath = normalizeDirectoryPath(entry.path);
        elements.currentPathInput.value = state.currentPath;
        loadDirectory();
      });
      checkbox.disabled = true;
      selector.style.visibility = "hidden";
    } else {
      checkbox.checked = state.selectedFiles.has(entry.url);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          state.selectedFiles.set(entry.url, entry);
        } else {
          state.selectedFiles.delete(entry.url);
        }
      });
      link.addEventListener("click", () => {
        if (!state.queue.some((item) => item.url === entry.url)) {
          state.queue.push(entry);
          renderQueue();
        }
        const queueIndex = state.queue.findIndex((item) => item.url === entry.url);
        playTrackAtIndex(queueIndex);
      });
    }

    card.dataset.type = entry.type;
    elements.browserList.appendChild(fragment);
  });
}

function renderBreadcrumb() {
  const segments = state.currentPath.split("/").filter(Boolean);
  const crumbs = ['<button data-path="/">root</button>'];
  let build = "/";

  segments.forEach((segment) => {
    build = `${build}${segment}/`;
    crumbs.push(`<span>/</span><button data-path="${build}">${segment}</button>`);
  });

  elements.breadcrumb.innerHTML = crumbs.join("");
  Array.from(elements.breadcrumb.querySelectorAll("button")).forEach((button) => {
    button.className = "item-link";
    button.addEventListener("click", () => {
      state.currentPath = button.dataset.path;
      elements.currentPathInput.value = state.currentPath;
      loadDirectory();
    });
  });
}

async function updateRecursiveFileCount(baseUrl, rootHtml) {
  try {
    const totalFiles = await countFilesRecursively(baseUrl, rootHtml, new Set());
    elements.recursiveFileCount.textContent = `전체 하위 파일: ${totalFiles} files`;
  } catch (error) {
    elements.recursiveFileCount.textContent = "전체 하위 파일: 계산 불가";
  }
}

async function countFilesRecursively(directoryUrl, html, visited) {
  const normalizedUrl = new URL(directoryUrl).href;
  if (visited.has(normalizedUrl)) {
    return 0;
  }
  visited.add(normalizedUrl);

  const entries = parseDirectoryListingEntries(html, normalizedUrl);
  const fileCount = entries.filter((entry) => entry.type === "file").length;
  const directories = entries.filter((entry) => entry.type === "directory");

  let nestedCount = 0;
  for (const directory of directories) {
    try {
      const response = await fetch(directory.url, buildFetchOptions());
      if (!response.ok) {
        continue;
      }
      const childHtml = await response.text();
      nestedCount += await countFilesRecursively(directory.url, childHtml, visited);
    } catch (error) {
      continue;
    }
  }

  return fileCount + nestedCount;
}

function renderQueue() {
  elements.queueList.innerHTML = "";

  if (state.queue.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "곡을 선택한 뒤 큐에 추가하세요.";
    elements.queueList.appendChild(empty);
    updateNowPlaying();
    return;
  }

  state.queue.forEach((entry, index) => {
    const fragment = elements.queueItemTemplate.content.cloneNode(true);
    const item = fragment.querySelector(".queue-item");
    const trackButton = fragment.querySelector(".queue-track");
    const urlNode = fragment.querySelector(".queue-url");
    const upButton = fragment.querySelector(".queue-move-up");
    const downButton = fragment.querySelector(".queue-move-down");
    const removeButton = fragment.querySelector(".queue-remove");

    item.classList.toggle("active", index === state.currentQueueIndex);
    trackButton.textContent = `${index + 1}. ${entry.name}`;
    urlNode.textContent = entry.displayUrl || entry.url;
    trackButton.addEventListener("click", () => playTrackAtIndex(index));
    upButton.disabled = index === 0;
    downButton.disabled = index === state.queue.length - 1;
    upButton.addEventListener("click", () => moveQueueItem(index, -1));
    downButton.addEventListener("click", () => moveQueueItem(index, 1));
    removeButton.addEventListener("click", () => removeQueueItem(index));
    elements.queueList.appendChild(fragment);
  });

  updateNowPlaying();
}

function playTrackAtIndex(index) {
  if (index < 0 || index >= state.queue.length) {
    return;
  }

  state.currentQueueIndex = index;
  const entry = state.queue[index];
  if (isSpotifyEntry(entry)) {
    showSpotifyPlayer(entry);
  } else {
    showAudioPlayer(entry);
  }
  elements.playerTitle.textContent = entry.name;
  updateNowPlaying();
  renderQueue();
}

function updateNowPlaying() {
  if (state.currentQueueIndex < 0 || state.currentQueueIndex >= state.queue.length) {
    elements.nowPlaying.textContent = "재생 전";
    elements.playerTitle.textContent = "선택된 곡이 없습니다";
    return;
  }

  const entry = state.queue[state.currentQueueIndex];
  elements.nowPlaying.textContent = `${state.currentQueueIndex + 1}/${state.queue.length} · ${entry.name}`;
  elements.playerTitle.textContent = entry.name;
}

function applyFilter(keyword) {
  const normalized = keyword.trim().toLowerCase();
  state.filteredEntries = state.entries.filter((entry) => {
    if (!normalized) {
      return true;
    }
    return entry.name.toLowerCase().includes(normalized);
  });
  renderBrowser(state.filteredEntries);
}

function updateSummary(visibleEntries, allEntries) {
  elements.visibleSummary.textContent = `표시: ${formatDirectoryAndFileSummary(visibleEntries)}`;
  elements.originalSummary.textContent = `원본: ${formatDirectoryAndFileSummary(allEntries)}`;
}

function formatDirectoryAndFileSummary(entries) {
  const directories = entries.filter((entry) => entry.type === "directory").length;
  const files = entries.filter((entry) => entry.type === "file").length;
  const totalSize = entries
    .filter((entry) => entry.type === "file")
    .reduce((sum, entry) => sum + (entry.sizeBytes || 0), 0);
  return `${directories} folders · ${files} files · ${formatBytes(totalSize)}`;
}

function parseSizeBytes(anchor) {
  const rowText = anchor.closest("tr, pre, li")?.textContent || anchor.parentElement?.textContent || "";
  const withoutName = rowText.replace(anchor.textContent || "", " ");
  const sizeMatch = withoutName.match(/(\d+(?:\.\d+)?)\s*(K|M|G|T)?B?\b/i);
  if (!sizeMatch) {
    return 0;
  }

  const value = Number.parseFloat(sizeMatch[1]);
  if (Number.isNaN(value)) {
    return 0;
  }

  const unit = (sizeMatch[2] || "").toUpperCase();
  const multipliers = {
    "": 1,
    K: 1024,
    M: 1024 ** 2,
    G: 1024 ** 3,
    T: 1024 ** 4,
  };
  return Math.round(value * (multipliers[unit] || 1));
}

function formatBytes(bytes) {
  if (!bytes) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const digits = value >= 10 || unitIndex === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

function isAudioFile(filename) {
  const lower = filename.toLowerCase();
  return AUDIO_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

function normalizeRootUrl(value) {
  if (!value) {
    return "";
  }

  const trimmed = value.trim();
  return trimmed.endsWith("/") ? trimmed : `${trimmed}/`;
}

function syncRootStateFromInputs() {
  state.rootUrl = normalizeRootUrl(elements.rootUrlInput.value);
  state.port = normalizePort(elements.portInput.value);
  state.username = elements.usernameInput.value.trim();
  state.password = elements.passwordInput.value;
  state.rootMemoryPassword = elements.rootMemoryPasswordInput.value;
}

function syncRootInputs() {
  elements.rootUrlInput.value = state.rootUrl;
  elements.portInput.value = state.port;
  elements.usernameInput.value = state.username;
}

function normalizeQueueUrl(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) {
    return "";
  }

  try {
    const parsed = new URL(trimmed);
    parsed.username = "";
    parsed.password = "";
    return parsed.href;
  } catch (error) {
    return trimmed;
  }
}

function normalizePort(value) {
  return (value || "").trim().replace(/[^0-9]/g, "");
}

function parseQueueText(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => createQueueEntry(line))
    .filter(Boolean);
}

function serializeQueueText() {
  return state.queue
    .map((entry) => entry.sourceUrl || entry.displayUrl || entry.url)
    .join("\n");
}

function createQueueEntry(rawValue) {
  const spotifyEntry = createSpotifyQueueEntry(rawValue);
  if (spotifyEntry) {
    return spotifyEntry;
  }

  const resolvedUrl = resolveQueueUrl(rawValue);
  if (!resolvedUrl) {
    return null;
  }

  return {
    name: extractFilename(resolvedUrl),
    url: resolvedUrl,
    displayUrl: resolvedUrl,
    sourceUrl: rawValue,
    path: new URL(resolvedUrl).pathname,
    type: "file",
  };
}

function createSpotifyQueueEntry(rawValue) {
  const spotifyMeta = parseSpotifyReference(rawValue);
  if (!spotifyMeta) {
    return null;
  }

  return {
    name: `Spotify ${spotifyMeta.type} ${spotifyMeta.id}`,
    url: spotifyMeta.embedUrl,
    displayUrl: spotifyMeta.shareUrl,
    sourceUrl: rawValue,
    path: spotifyMeta.shareUrl,
    type: "spotify",
    spotifyType: spotifyMeta.type,
    spotifyId: spotifyMeta.id,
  };
}

function parseSpotifyReference(rawValue) {
  try {
    if (rawValue.startsWith("spotify:")) {
      const parts = rawValue.split(":");
      const type = parts[1];
      const id = parts[2];
      if (!SPOTIFY_TYPES.has(type) || !id) {
        return null;
      }
      return {
        type,
        id,
        shareUrl: `https://open.spotify.com/${type}/${id}`,
        embedUrl: `https://open.spotify.com/embed/${type}/${id}`,
      };
    }

    const url = new URL(rawValue);
    if (url.hostname !== "open.spotify.com") {
      return null;
    }
    const segments = url.pathname.split("/").filter(Boolean);
    const embedIndex = segments[0] === "embed" ? 1 : 0;
    const type = segments[embedIndex];
    const id = segments[embedIndex + 1];
    if (!SPOTIFY_TYPES.has(type) || !id) {
      return null;
    }
    return {
      type,
      id,
      shareUrl: `https://open.spotify.com/${type}/${id}`,
      embedUrl: `https://open.spotify.com/embed/${type}/${id}`,
    };
  } catch (error) {
    return null;
  }
}

function resolveQueueUrl(rawValue) {
  try {
    if (/^https?:\/\//i.test(rawValue)) {
      return new URL(rawValue).href;
    }
    return buildDisplayUrl(normalizeDirectoryPath(rawValue));
  } catch (error) {
    return null;
  }
}

function extractFilename(url) {
  const pathname = new URL(url).pathname;
  const parts = pathname.split("/").filter(Boolean);
  return decodeURIComponent(parts[parts.length - 1] || url);
}

function moveQueueItem(index, delta) {
  const nextIndex = index + delta;
  if (nextIndex < 0 || nextIndex >= state.queue.length) {
    return;
  }

  const [item] = state.queue.splice(index, 1);
  state.queue.splice(nextIndex, 0, item);
  if (state.currentQueueIndex === index) {
    state.currentQueueIndex = nextIndex;
  } else if (state.currentQueueIndex === nextIndex) {
    state.currentQueueIndex = index;
  }
  renderQueue();
  persistQueue();
}

function removeQueueItem(index) {
  state.queue.splice(index, 1);
  if (state.currentQueueIndex === index) {
    state.currentQueueIndex = -1;
    clearPlayers();
  } else if (state.currentQueueIndex > index) {
    state.currentQueueIndex -= 1;
  }
  renderQueue();
  persistQueue();
}

function normalizeDirectoryPath(value) {
  if (!value || value === "/") {
    return "/";
  }

  const cleaned = value.trim().replace(/^\/+/, "").replace(/\/+$/, "");
  return cleaned ? `/${cleaned}/` : "/";
}

function getParentPath(path) {
  const segments = path.split("/").filter(Boolean);
  segments.pop();
  return segments.length ? `/${segments.join("/")}/` : "/";
}

function buildBaseUrl() {
  if (!state.rootUrl) {
    return "";
  }

  const base = new URL(state.rootUrl);
  if (state.port) {
    base.port = state.port;
  }
  return base;
}

function buildDisplayUrl(targetPath) {
  const base = buildBaseUrl();
  if (!base) {
    return "";
  }

  const trimmedPath = targetPath.replace(/^\/+/, "");
  return new URL(trimmedPath, base.href).href;
}

function buildFetchOptions() {
  const options = { cache: "no-store" };
  if (!state.username) {
    return options;
  }

  options.headers = {
    Authorization: `Basic ${btoa(`${state.username}:${state.password}`)}`,
  };
  return options;
}

function buildQueueRequestUrl() {
  const parsed = new URL(state.queueUrl);
  if (state.queuePort) {
    parsed.port = state.queuePort;
  }
  parsed.username = "";
  parsed.password = "";
  return parsed.href;
}

function buildQueueFetchOptions() {
  const options = { cache: "no-store" };
  if (!state.queueUsername) {
    return options;
  }

  options.headers = {
    Authorization: `Basic ${btoa(`${state.queueUsername}:${state.queuePassword}`)}`,
  };
  return options;
}

function isSpotifyEntry(entry) {
  return entry && entry.type === "spotify";
}

function showSpotifyPlayer(entry) {
  clearPlayers();
  elements.spotifyPlayer.src = entry.url;
  elements.spotifyPlayer.classList.remove("hidden");
  elements.playerHint.textContent = "Spotify 공유 링크는 Embed Player로 재생됩니다. 다음 곡 이동은 아래 버튼을 사용하세요.";
  setStatus("Spotify Embed 재생 준비");
}

function showAudioPlayer(entry) {
  clearPlayers();
  elements.audioPlayer.src = entry.url;
  elements.audioPlayer.classList.remove("hidden");
  elements.playerHint.textContent = "서버 오디오는 브라우저 audio player로 재생됩니다.";
  elements.audioPlayer.play().catch(() => {
    setStatus("브라우저 재생 차단. 화면 터치 후 다시 시도");
  });
}

function clearPlayers() {
  elements.audioPlayer.pause();
  elements.audioPlayer.removeAttribute("src");
  elements.audioPlayer.load();
  elements.audioPlayer.classList.add("hidden");
  elements.spotifyPlayer.src = "";
  elements.spotifyPlayer.classList.add("hidden");
}

function setStatus(text) {
  elements.statusText.textContent = text;
}

function syncLocation() {
  const url = new URL(window.location.href);
  if (state.rootUrl) {
    url.searchParams.set("root", state.rootUrl);
  } else {
    url.searchParams.delete("root");
  }
  if (state.port) {
    url.searchParams.set("port", state.port);
  } else {
    url.searchParams.delete("port");
  }
  if (state.username) {
    url.searchParams.set("username", state.username);
  } else {
    url.searchParams.delete("username");
  }
  if (state.queueUrl) {
    url.searchParams.set("queue_url", state.queueUrl);
  } else {
    url.searchParams.delete("queue_url");
  }
  if (state.queuePort) {
    url.searchParams.set("queue_port", state.queuePort);
  } else {
    url.searchParams.delete("queue_port");
  }
  if (state.queueUsername) {
    url.searchParams.set("queue_username", state.queueUsername);
  } else {
    url.searchParams.delete("queue_username");
  }
  url.searchParams.set("path", state.currentPath);
  window.history.replaceState({}, "", url);
}

function persistQueue() {
  const payload = {
    queue: state.queue,
    currentQueueIndex: state.currentQueueIndex,
  };
  window.localStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(payload));
  persistQueueUrl();
}

function persistQueueUrl() {
  window.localStorage.setItem(QUEUE_URL_STORAGE_KEY, state.queueUrl || "");
}

function persistQueueSettings() {
  persistQueueUrl();
  const payload = {
    queuePort: state.queuePort || "",
    queueUsername: state.queueUsername || "",
  };
  window.localStorage.setItem(QUEUE_SETTINGS_STORAGE_KEY, JSON.stringify(payload));
}

function restoreQueueFromStorage(showStatus = false) {
  try {
    const raw = window.localStorage.getItem(QUEUE_STORAGE_KEY);
    if (!raw) {
      if (showStatus) {
        setStatus("저장된 Queue 없음");
      }
      renderQueue();
      return;
    }
    const parsed = JSON.parse(raw);
    state.queue = Array.isArray(parsed.queue) ? parsed.queue : [];
    state.currentQueueIndex = Number.isInteger(parsed.currentQueueIndex) ? parsed.currentQueueIndex : -1;
    renderQueue();
    if (showStatus) {
      setStatus(`이전 Queue 복원 (${state.queue.length}곡)`);
    }
  } catch (error) {
    state.queue = [];
    state.currentQueueIndex = -1;
    renderQueue();
    if (showStatus) {
      setStatus("저장된 Queue 복원 실패");
    }
  }
}

function loadStoredQueueUrl() {
  return window.localStorage.getItem(QUEUE_URL_STORAGE_KEY) || "";
}

function loadStoredQueueSettings() {
  try {
    const raw = window.localStorage.getItem(QUEUE_SETTINGS_STORAGE_KEY);
    if (!raw) {
      return { queuePort: "", queueUsername: "" };
    }
    const parsed = JSON.parse(raw);
    return {
      queuePort: parsed.queuePort || "",
      queueUsername: parsed.queueUsername || "",
    };
  } catch (error) {
    return { queuePort: "", queueUsername: "" };
  }
}

function updateRootMemoryDiagnostics() {
  const storageOk = isLocalStorageAvailable();
  elements.rootMemoryStorageStatus.textContent = storageOk
    ? "Storage 상태: 사용 가능"
    : "Storage 상태: 사용 불가";

  const metaRaw = window.localStorage.getItem(ROOT_MEMORY_META_STORAGE_KEY);
  if (!metaRaw) {
    elements.rootMemorySavedStatus.textContent = "저장된 Root 기억 없음";
    elements.rootMemoryList.textContent = "저장된 Root 기억 없음";
    return;
  }

  try {
    const meta = JSON.parse(metaRaw);
    const savedAt = formatStoredTimestamp(meta.savedAt);
    elements.rootMemorySavedStatus.textContent = `마지막 저장: ${savedAt}`;
    elements.rootMemoryList.textContent = [
      `Root URL: ${meta.rootUrl || "-"}`,
      `포트: ${meta.port || "-"}`,
      `ID: ${meta.username || "-"}`,
      `현재 경로: ${meta.currentPath || "/"}`,
      `저장 시각: ${savedAt}`,
    ].join("\n");
  } catch (error) {
    elements.rootMemorySavedStatus.textContent = "저장된 Root 기억 메타데이터 손상";
    elements.rootMemoryList.textContent = "저장된 Root 기억 메타데이터를 읽을 수 없습니다.";
  }
}

function isLocalStorageAvailable() {
  try {
    const probeKey = "__tesla_direct_streaming_probe__";
    window.localStorage.setItem(probeKey, "ok");
    window.localStorage.removeItem(probeKey);
    return true;
  } catch (error) {
    return false;
  }
}

function formatStoredTimestamp(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ko-KR", { hour12: false });
}

async function saveRootMemory() {
  if (!state.rootMemoryPassword) {
    setStatus("기억 암호 입력 필요");
    return;
  }

  const payload = {
    rootUrl: state.rootUrl,
    port: state.port,
    username: state.username,
    password: state.password,
    currentPath: state.currentPath,
  };
  const meta = {
    rootUrl: state.rootUrl,
    port: state.port,
    username: state.username,
    currentPath: state.currentPath,
    savedAt: new Date().toISOString(),
  };

  try {
    const encrypted = await encryptJsonPayload(payload, state.rootMemoryPassword);
    window.localStorage.setItem(ROOT_MEMORY_STORAGE_KEY, JSON.stringify(encrypted));
    window.localStorage.setItem(ROOT_MEMORY_META_STORAGE_KEY, JSON.stringify(meta));
    updateRootMemoryDiagnostics();
    setStatus("Root 기억 저장 완료");
  } catch (error) {
    setStatus("Root 기억 저장 실패");
  }
}

async function restoreRootMemory(showStatus) {
  if (!state.rootMemoryPassword) {
    if (showStatus) {
      setStatus("기억 암호 입력 필요");
    }
    return false;
  }

  const raw = window.localStorage.getItem(ROOT_MEMORY_STORAGE_KEY);
  if (!raw) {
    updateRootMemoryDiagnostics();
    if (showStatus) {
      setStatus("저장된 Root 기억 없음");
    }
    return false;
  }

  try {
    const encrypted = JSON.parse(raw);
    const restored = await decryptJsonPayload(encrypted, state.rootMemoryPassword);
    state.rootUrl = normalizeRootUrl(restored.rootUrl || "");
    state.port = normalizePort(restored.port || "");
    state.username = restored.username || "";
    state.password = restored.password || "";
    state.currentPath = normalizeDirectoryPath(restored.currentPath || "/");
    syncRootInputs();
    elements.passwordInput.value = state.password;
    elements.currentPathInput.value = state.currentPath;
    updateRootMemoryDiagnostics();
    if (showStatus) {
      setStatus("Root 기억 복원 완료");
    }
    return true;
  } catch (error) {
    updateRootMemoryDiagnostics();
    if (showStatus) {
      setStatus("기억 암호 불일치 또는 복원 실패");
    }
    return false;
  }
}

async function tryAutoRestoreRootMemory() {
  if (!elements.rootMemoryPasswordInput.value) {
    return;
  }
  syncRootStateFromInputs();
  await restoreRootMemory(false);
}

async function encryptJsonPayload(payload, password) {
  const encoder = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveAesKey(password, salt);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    encoder.encode(JSON.stringify(payload)),
  );

  return {
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
  };
}

async function decryptJsonPayload(payload, password) {
  const decoder = new TextDecoder();
  const salt = base64ToBytes(payload.salt);
  const iv = base64ToBytes(payload.iv);
  const ciphertext = base64ToBytes(payload.ciphertext);
  const key = await deriveAesKey(password, salt);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    ciphertext,
  );
  return JSON.parse(decoder.decode(plaintext));
}

async function deriveAesKey(password, salt) {
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveKey"],
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

function bytesToBase64(bytes) {
  return btoa(String.fromCharCode(...bytes));
}

function base64ToBytes(value) {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}

function syncQueueStateFromInputs() {
  state.queueUrl = normalizeQueueUrl(elements.queueUrlInput.value);
  state.queuePort = normalizePort(elements.queuePortInput.value);
  state.queueUsername = elements.queueUsernameInput.value.trim();
  state.queuePassword = elements.queuePasswordInput.value;
  syncQueueInputs();
}

function syncQueueInputs() {
  elements.queueUrlInput.value = state.queueUrl;
  elements.queuePortInput.value = state.queuePort;
  elements.queueUsernameInput.value = state.queueUsername;
}

void init();
