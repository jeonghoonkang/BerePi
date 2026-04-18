const DEFAULT_ROOT_URL = "";
const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"];

const state = {
  rootUrl: "",
  currentPath: "/",
  entries: [],
  filteredEntries: [],
  selectedFiles: new Map(),
  queue: [],
  currentQueueIndex: -1,
};

const elements = {
  rootUrlInput: document.querySelector("#rootUrlInput"),
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
  addSelectedButton: document.querySelector("#addSelectedButton"),
  playQueueButton: document.querySelector("#playQueueButton"),
  clearQueueButton: document.querySelector("#clearQueueButton"),
  queueList: document.querySelector("#queueList"),
  audioPlayer: document.querySelector("#audioPlayer"),
  playerTitle: document.querySelector("#playerTitle"),
  playPauseButton: document.querySelector("#playPauseButton"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  statusText: document.querySelector("#statusText"),
  nowPlaying: document.querySelector("#nowPlaying"),
  itemTemplate: document.querySelector("#browserItemTemplate"),
};

function init() {
  const url = new URL(window.location.href);
  const requestedRoot = url.searchParams.get("root") || DEFAULT_ROOT_URL;
  const requestedPath = url.searchParams.get("path") || "/";

  state.rootUrl = normalizeRootUrl(requestedRoot);
  state.currentPath = normalizeDirectoryPath(requestedPath);

  elements.rootUrlInput.value = state.rootUrl;
  elements.currentPathInput.value = state.currentPath;

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
    setStatus(`${uniqueSelected.length}곡 큐에 추가`);
  });

  elements.clearQueueButton.addEventListener("click", () => {
    state.queue = [];
    state.currentQueueIndex = -1;
    renderQueue();
    elements.audioPlayer.pause();
    elements.audioPlayer.removeAttribute("src");
    elements.audioPlayer.load();
    updateNowPlaying();
    setStatus("큐 비움");
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

  const targetUrl = joinUrl(state.rootUrl, state.currentPath);
  setStatus("목록 불러오는 중");
  elements.currentPathInput.value = state.currentPath;
  syncLocation();

  try {
    const response = await fetch(targetUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const html = await response.text();
    state.entries = parseApacheDirectoryListing(html, targetUrl);
    applyFilter(elements.filterInput.value);
    renderBreadcrumb();
    setStatus(`목록 준비 완료 (${state.entries.length}개 항목)`);
  } catch (error) {
    renderBrowser([]);
    setStatus(`로드 실패: ${error.message}`);
  }
}

function parseApacheDirectoryListing(html, baseUrl) {
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
        url: url.href,
        path: pathname,
        type: isDirectory ? "directory" : "file",
      };
    })
    .filter(Boolean)
    .filter((entry) => entry.type === "directory" || isAudioFile(entry.name))
    .sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "directory" ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
}

function renderBrowser(entries) {
  elements.browserList.innerHTML = "";
  const directories = entries.filter((entry) => entry.type === "directory").length;
  const files = entries.filter((entry) => entry.type === "file").length;
  elements.directoryCount.textContent = `${directories} folders`;
  elements.fileCount.textContent = `${files} files`;

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
    subtitle.textContent = entry.type === "directory" ? "폴더 열기" : entry.url;

    if (entry.type === "directory") {
      link.addEventListener("click", () => {
        state.currentPath = relativePathFromRoot(entry.url);
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
    const item = document.createElement("li");
    item.className = index === state.currentQueueIndex ? "active" : "";
    item.textContent = `${index + 1}. ${entry.name}`;
    item.addEventListener("click", () => playTrackAtIndex(index));
    elements.queueList.appendChild(item);
  });

  updateNowPlaying();
}

function playTrackAtIndex(index) {
  if (index < 0 || index >= state.queue.length) {
    return;
  }

  state.currentQueueIndex = index;
  const entry = state.queue[index];
  elements.audioPlayer.src = entry.url;
  elements.playerTitle.textContent = entry.name;
  updateNowPlaying();
  renderQueue();

  elements.audioPlayer.play().catch(() => {
    setStatus("브라우저 재생 차단. 화면 터치 후 다시 시도");
  });
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

function joinUrl(rootUrl, currentPath) {
  const trimmedPath = currentPath.replace(/^\/+/, "");
  return new URL(trimmedPath, rootUrl).href;
}

function relativePathFromRoot(targetUrl) {
  const root = new URL(state.rootUrl);
  const target = new URL(targetUrl);
  const relative = target.pathname.replace(root.pathname, "");
  return normalizeDirectoryPath(relative);
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
  url.searchParams.set("path", state.currentPath);
  window.history.replaceState({}, "", url);
}

init();
