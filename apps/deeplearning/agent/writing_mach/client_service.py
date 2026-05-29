#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.getenv("WRITING_MACH_HOST", "127.0.0.1")
PORT = int(os.getenv("WRITING_MACH_PORT", "8786"))

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_PATH = DATA_DIR / "client_config.json"
SAMPLE_CONFIG_PATH = BASE_DIR / "config" / "client_config.sample.json"
BACKBONE_PATH = BASE_DIR / "story_backbone.md"
USE_COLOR = os.getenv("NO_COLOR", "").strip() == "" and os.getenv("WRITING_MACH_NO_COLOR", "").strip() == ""

COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "red": "\033[31m",
    "bold": "\033[1m",
}

DEFAULT_CONFIG = {
    "server_base_url": "http://127.0.0.1:8082",
    "generate_path": "/api/generate",
    "status_path": "/api/status",
    "request_timeout_seconds": 600,
    "user_id": "admin",
    "password": "aimodel",
    "model": "",
    "keep_alive": "60m",
    "num_ctx": 8192,
    "target_words_per_chapter": 1800,
    "language": "ko",
}


def color_text(text: str, color: str) -> str:
    if not USE_COLOR:
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def progress_log(stage: str, message: str, color: str = "cyan", started: float | None = None) -> None:
    elapsed = ""
    if started is not None:
        elapsed = color_text(f" +{time.perf_counter() - started:.1f}s", "dim")
    stamp = time.strftime("%H:%M:%S")
    prefix = color_text(f"[{stamp}] [{stage}]", color)
    print(f"{prefix}{elapsed} {message}", flush=True)


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        sample = DEFAULT_CONFIG
        if SAMPLE_CONFIG_PATH.exists():
            try:
                sample = normalize_config(json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                sample = DEFAULT_CONFIG
        CONFIG_PATH.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming = dict(raw or {})
    timeout = int(incoming.get("request_timeout_seconds") or DEFAULT_CONFIG["request_timeout_seconds"])
    num_ctx = int(incoming.get("num_ctx") or DEFAULT_CONFIG["num_ctx"])
    target_words = int(incoming.get("target_words_per_chapter") or DEFAULT_CONFIG["target_words_per_chapter"])
    return {
        "server_base_url": str(incoming.get("server_base_url") or DEFAULT_CONFIG["server_base_url"]).rstrip("/"),
        "generate_path": str(incoming.get("generate_path") or DEFAULT_CONFIG["generate_path"]),
        "status_path": str(incoming.get("status_path") or DEFAULT_CONFIG["status_path"]),
        "request_timeout_seconds": max(5, timeout),
        "user_id": str(incoming.get("user_id") or ""),
        "password": str(incoming.get("password") or ""),
        "model": str(incoming.get("model") or ""),
        "keep_alive": str(incoming.get("keep_alive") or DEFAULT_CONFIG["keep_alive"]),
        "num_ctx": max(0, num_ctx),
        "target_words_per_chapter": max(300, target_words),
        "language": str(incoming.get("language") or DEFAULT_CONFIG["language"]),
    }


def read_config() -> dict[str, Any]:
    ensure_dirs()
    try:
        return normalize_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return normalize_config(DEFAULT_CONFIG)


def write_config(config: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    normalized = normalize_config(config)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def runtime_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = read_config()
    for key, value in dict(override or {}).items():
        if key in DEFAULT_CONFIG:
            if key in {"user_id", "password"} and value == "" and merged.get(key):
                continue
            merged[key] = value
    return normalize_config(merged)


def read_story_backbone() -> str:
    if not BACKBONE_PATH.exists():
        raise ValueError(f"story_backbone.md not found: {BACKBONE_PATH}")
    return BACKBONE_PATH.read_text(encoding="utf-8").strip()


def parse_chapters(backbone: str) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in backbone.splitlines():
        match = re.match(r"\s*-\s*(\d+)\s*챕터\s*$", line)
        if match:
            current = {"number": int(match.group(1)), "title": f"{match.group(1)} 챕터", "bullets": []}
            chapters.append(current)
            continue
        if current and re.match(r"\s*-\s+", line):
            bullet = re.sub(r"^\s*-\s*", "", line).strip()
            if bullet and not re.search(r"챕터|작성방법|main writer|agent", bullet, re.IGNORECASE):
                current["bullets"].append(bullet)
    if not chapters:
        chapters = [{"number": 1, "title": "1 챕터", "bullets": [backbone]}]
    return chapters


def join_url(base_url: str, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def request_json(url: str, payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (TimeoutError, socket.timeout) as exc:
        raise TimeoutError(f"Timed out waiting for {url} after {timeout} seconds.") from exc
    if not raw.strip():
        raise ValueError(f"Empty response from {url}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw.strip().replace("\n", " ")[:240]
        raise ValueError(f"Expected JSON from {url}; preview={preview!r}") from exc


def build_generate_payload(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "keep_alive": config["keep_alive"],
        "stream": False,
        "options": {"num_ctx": int(config["num_ctx"])},
    }
    if config.get("model"):
        payload["model"] = config["model"]
    return payload


def extract_response_text(data: dict[str, Any]) -> str:
    for key in ("response", "text", "output", "content"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            if isinstance(first.get("text"), str):
                return first["text"]
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    return json.dumps(data, ensure_ascii=False, indent=2)


def call_model(config: dict[str, Any], prompt: str) -> str:
    generate_url = join_url(config["server_base_url"], config["generate_path"])
    started = time.perf_counter()
    progress_log("model", f"request -> {generate_url} ({word_count(prompt)} words prompt)", "blue")
    try:
        data = request_json(generate_url, build_generate_payload(config, prompt), int(config["request_timeout_seconds"]))
    except urllib.error.HTTPError as exc:
        if exc.code == HTTPStatus.UNAUTHORIZED:
            raise ValueError("Model endpoint rejected authentication. Check User ID/Password.") from exc
        raise ValueError(f"Model endpoint returned HTTP {exc.code}: {generate_url} | {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to model endpoint: {generate_url} | {exc}") from exc
    except TimeoutError as exc:
        raise ValueError(str(exc)) from exc
    text = extract_response_text(data).strip()
    progress_log("model", f"response <- {word_count(text)} words", "green", started)
    return text


def fetch_remote_status(config: dict[str, Any]) -> dict[str, Any]:
    url = join_url(config["server_base_url"], config["status_path"])
    try:
        data = request_json(url, None, int(config["request_timeout_seconds"]))
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not connect to model status endpoint: {url} | {exc}") from exc
    return {
        "server_base_url": config["server_base_url"],
        "status_url": url,
        "model": data.get("model", ""),
        "host": data.get("host", ""),
        "port": data.get("port", ""),
        "raw": data,
    }


def title_from_backbone(backbone: str) -> str:
    match = re.search(r"제목은\s*(.+)", backbone)
    if match:
        return match.group(1).strip()
    return "untitled-book"


def chapter_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any]) -> str:
    bullets = "\n".join(f"- {item}" for item in chapter["bullets"])
    return f"""당신은 책의 한 챕터를 담당하는 전문 작가 에이전트입니다.

책 전체 기획:
{backbone}

담당 챕터:
{chapter['title']}
{bullets}

작성 지침:
- 한국어로 작성합니다.
- 목표 분량은 약 {config['target_words_per_chapter']} 단어입니다.
- 사실 설명, 시대적 맥락, 핵심 앨범/뮤지션 목록, 해설을 균형 있게 넣습니다.
- 책 전체의 일부가 되도록 독립된 챕터 제목과 절 구성을 포함합니다.
- 아직 다른 챕터와 조율 전인 1차 초안입니다.
"""


def coordinator_prompt(backbone: str, chapter_drafts: list[dict[str, Any]]) -> str:
    draft_text = "\n\n".join(
        f"## {item['chapter']['title']} 초안\n{item['draft']}" for item in chapter_drafts
    )
    return f"""당신은 전체 책을 조율하는 main writer agent입니다.

책 전체 기획:
{backbone}

아래는 각 챕터 에이전트의 1차 출력입니다.
{draft_text}

작업:
1. 전체 책의 논지, 시대 흐름, 용어, 반복/누락을 점검합니다.
2. 1챕터 초반부와 책의 도입부가 뒤 챕터의 방향과 어긋나는 부분을 찾아 수정 방향을 제시합니다.
3. 최종 원고에서 초반부가 어떤 관점을 깔아야 하는지 구체적인 편집 지시를 작성합니다.

출력 형식:
## 전체 편집 방향
...

## 초반부 수정 지시
...
"""


def revise_opening_prompt(backbone: str, chapter_drafts: list[dict[str, Any]], coordinator_notes: str) -> str:
    first_chapter = chapter_drafts[0]["draft"] if chapter_drafts else ""
    other_summaries = "\n\n".join(
        f"## {item['chapter']['title']}\n{item['draft'][:2500]}" for item in chapter_drafts[1:]
    )
    return f"""당신은 최종 원고를 다듬는 lead writer입니다.

책 전체 기획:
{backbone}

main writer agent의 조율 메모:
{coordinator_notes}

1챕터 기존 초안:
{first_chapter}

뒤 챕터 참고 내용:
{other_summaries}

작업:
- 책의 도입부와 1챕터 초반부를 다시 작성합니다.
- 뒤 챕터에서 다루는 주제와 자연스럽게 이어지도록 관점, 문제의식, 시대 흐름을 조정합니다.
- 출력은 수정된 도입부와 1챕터 전체 원고로 작성합니다.
"""


def compile_book(title: str, revised_opening: str, chapter_drafts: list[dict[str, Any]], coordinator_notes: str) -> str:
    remaining = "\n\n".join(item["draft"] for item in chapter_drafts[1:])
    return f"""# {title}

> generated by writing_mach on {time.strftime('%Y-%m-%d %H:%M:%S')}

## Main Writer Notes

{coordinator_notes}

---

{revised_opening}

---

{remaining}
"""


def run_book_agents(config: dict[str, Any], backbone: str | None = None) -> dict[str, Any]:
    backbone_text = (backbone or read_story_backbone()).strip()
    chapters = parse_chapters(backbone_text)
    started = time.perf_counter()
    progress_log("start", f"book agent run started: {len(chapters)} chapters", "bold", started)
    progress_log("backbone", f"title='{title_from_backbone(backbone_text)}'", "cyan", started)

    chapter_drafts: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        chapter_started = time.perf_counter()
        progress_log(
            "chapter",
            f"{index}/{len(chapters)} {chapter['title']} draft started ({len(chapter['bullets'])} bullets)",
            "yellow",
            started,
        )
        draft = call_model(config, chapter_prompt(backbone_text, chapter, config))
        chapter_drafts.append({"chapter": chapter, "draft": draft})
        progress_log(
            "chapter",
            f"{index}/{len(chapters)} {chapter['title']} draft done ({word_count(draft)} words)",
            "green",
            chapter_started,
        )

    coordinator_started = time.perf_counter()
    progress_log("main-writer", "reviewing chapter drafts and preparing direction notes", "magenta", started)
    coordinator_notes = call_model(config, coordinator_prompt(backbone_text, chapter_drafts))
    progress_log("main-writer", f"direction notes done ({word_count(coordinator_notes)} words)", "green", coordinator_started)

    revise_started = time.perf_counter()
    progress_log("lead-writer", "rewriting opening and early chapter from chapter-agent outputs", "cyan", started)
    revised_opening = call_model(config, revise_opening_prompt(backbone_text, chapter_drafts, coordinator_notes))
    progress_log("lead-writer", f"opening revision done ({word_count(revised_opening)} words)", "green", revise_started)

    title = title_from_backbone(backbone_text)
    progress_log("compile", "compiling final manuscript", "blue", started)
    book = compile_book(title, revised_opening, chapter_drafts, coordinator_notes)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"book_{timestamp}.md"
    log_path = OUTPUT_DIR / f"run_{timestamp}.json"
    progress_log("save", f"writing book markdown -> {output_path}", "blue", started)
    output_path.write_text(book + "\n", encoding="utf-8")
    progress_log("save", f"writing run log -> {log_path}", "blue", started)
    log_path.write_text(
        json.dumps(
            {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "config": {key: value for key, value in config.items() if key != "password"},
                "backbone": backbone_text,
                "chapters": chapter_drafts,
                "coordinator_notes": coordinator_notes,
                "revised_opening": revised_opening,
                "output_path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    progress_log("done", f"agent run finished ({word_count(book)} words total)", "green", started)
    return {
        "ok": True,
        "elapsed_seconds": time.perf_counter() - started,
        "title": title,
        "chapter_count": len(chapters),
        "chapters": chapter_drafts,
        "coordinator_notes": coordinator_notes,
        "revised_opening": revised_opening,
        "book": book,
        "output_path": str(output_path),
        "log_path": str(log_path),
    }


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


class WritingMachHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/styles.css":
            self.serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/app.js":
            self.serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/state":
            self.send_json({"config": read_config(), "backbone": read_story_backbone()})
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            incoming = parse_json_body(self)
            request_path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            if request_path == "/api/config":
                self.send_json({"config": write_config(incoming.get("config") or {})})
                return
            if request_path == "/api/test-connection":
                config = runtime_config(incoming.get("config"))
                self.send_json({"status": fetch_remote_status(config)})
                return
            if request_path == "/api/write-book":
                config = runtime_config(incoming.get("config"))
                self.send_json({"result": run_book_agents(config, str(incoming.get("backbone") or ""))})
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (json.JSONDecodeError, OSError, TimeoutError, urllib.error.URLError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def main() -> int:
    ensure_dirs()
    httpd = ThreadingHTTPServer((HOST, PORT), WritingMachHandler)
    progress_log("service", f"Writing Mach service: http://{HOST}:{PORT}", "green")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
