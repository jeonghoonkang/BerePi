const DEFAULT_ROOT_URL = "";
const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"];
const SPOTIFY_TYPES = new Set(["track", "album", "playlist", "artist", "episode", "show"]);
const QUEUE_STORAGE_KEY = "tesla_direct_streaming_queue";
const QUEUE_URL_STORAGE_KEY = "tesla_direct_streaming_queue_url";

const state = {
  rootUrl: "",
  port: "",
  username: "",
  password: "",
  queueUrl: "",
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
  queueUrlInput: document.querySelector("#queueUrlInput"),
  currentPathInput: document.querySelector("#currentPathInput"),
  loadButton: document.querySelector("#loadButton"),
  upButton: document.querySelector("#upButton"),
  selectVisibleButton: document.querySelector("#selectVisibleButton"),
  clearSelectionButton: document.querySelector("#clearSelectionButton"),
  filterInput: document.querySelector("#filterInput"),
  browserList: document.querySelector("#browserList"),
  breadcrumb: document.querySelector("#breadcrumb"),
  directoryCount: document.querySelector("#directoryCount"),
  fileCount: document.querySelector("#fileCount"),
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
  itemTemplate: document.querySelector("#browserItemTemplate"),
  queueItemTemplate: document.querySelector("#queueItemTemplate"),
};

function init() {
  const url = new URL(window.location.href);
  const requestedRoot = url.searchParams.get("root") || DEFAULT_ROOT_URL;
  const requestedPort = url.searchParams.get("port") || "";
  const requestedUsername = url.searchParams.get("username") || "";
  const requestedQueueUrl = url.searchParams.get("queue_url") || loadStoredQueueUrl();
  const requestedPath = url.searchParams.get("path") || "/";

  state.rootUrl = normalizeRootUrl(requestedRoot);
  state.port = normalizePort(requestedPort);
  state.username = requestedUsername;
  state.queueUrl = requestedQueueUrl;
  state.currentPath = normalizeDirectoryPath(requestedPath);

  elements.rootUrlInput.value = state.rootUrl;
  elements.portInput.value = state.port;
  elements.usernameInput.value = state.username;
  elements.passwordInput.value = "";
  elements.queueUrlInput.value = state.queueUrl;
  elements.currentPathInput.value = state.currentPath;
  restoreQueueFromStorage();

  bindEvents();

  if (state.rootUrl) {
    loadDirectory();
  } else {
    renderBrowser([]);
    setStatus("Root URL 입력 필요");
  }
}

function bindEvents() {
  elements.loadButton.addEventListener("click", () => {
    state.rootUrl = normalizeRootUrl(elements.rootUrlInput.value);
    state.port = normalizePort(elements.portInput.value);
    state.username = elements.usernameInput.value.trim();
    state.password = elements.passwordInput.value;
    state.queueUrl = elements.queueUrlInput.value.trim();
    state.currentPath = normalizeDirectoryPath(elements.currentPathInput.value);
    loadDirectory();
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
    state.queueUrl = elements.queueUrlInput.value.trim();
    loadQueueFromRemote(false);
  });

  elements.appendQueueUrlButton.addEventListener("click", () => {
    state.queueUrl = elements.queueUrlInput.value.trim();
    loadQueueFromRemote(true);
  });

  elements.saveQueueUrlButton.addEventListener("click", () => {
    state.queueUrl = elements.queueUrlInput.value.trim();
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
  if (!elements.queueUrlInput.value.trim()) {
    setStatus("Queue TXT URL 입력 필요");
    return;
  }

  state.queueUrl = elements.queueUrlInput.value.trim();
  syncLocation();
  persistQueueUrl();
  setStatus("Queue TXT 불러오는 중");

  try {
    const response = await fetch(state.queueUrl, buildFetchOptions());
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
  if (!elements.queueUrlInput.value.trim()) {
    setStatus("Queue TXT URL 입력 필요");
    return;
  }

  if (state.queue.length === 0) {
    setStatus("저장할 Queue가 비어 있음");
    return;
  }

  state.queueUrl = elements.queueUrlInput.value.trim();
  syncLocation();
  persistQueueUrl();
  setStatus("Queue TXT 저장 중");

  try {
    const fetchOptions = buildFetchOptions();
    const response = await fetch(state.queueUrl, {
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
      };
    })
    .filter(Boolean);
}

function renderBrowser(entries) {
  elements.browserList.innerHTML = "";
  const directories = entries.filter((entry) => entry.type === "directory").length;
  const files = entries.filter((entry) => entry.type === "file").length;
  elements.directoryCount.textContent = `${directories} folders`;
  elements.fileCount.textContent = `${files} files`;
  elements.recursiveFileCount.textContent = "counting total files...";

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
    elements.recursiveFileCount.textContent = `${totalFiles} total files`;
  } catch (error) {
    elements.recursiveFileCount.textContent = "total count unavailable";
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

init();
