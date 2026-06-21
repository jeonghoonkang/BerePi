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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    "chapter_parallelism": 1,
    "chapter_retry": 2,
    "pipeline_agents": ["outline", "writer", "reviewer", "finalizer"],
    "agent_workers": [],
    "global_review_enabled": True,
    "global_review_mode": "strict",
    "global_review_focus": [
        "전체 논지 일관성",
        "챕터 간 반복 제거",
        "용어 통일",
        "시대 흐름 점검",
        "도입부와 결론의 연결",
    ],
    "allow_global_rewrite": False,
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


def bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def backbone_bool_value(value: str) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
        "enable",
        "enabled",
        "parallel",
        "사용",
        "사용함",
        "켜기",
        "활성",
        "활성화",
        "병렬",
        "병렬실행",
    }


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = {key: value for key, value in config.items() if not key.startswith("_")}
    redacted.pop("password", None)
    redacted["agent_workers"] = [
        {key: value for key, value in worker.items() if key not in {"password", "agent_workers"}}
        for worker in config.get("agent_workers", [])
    ]
    return redacted


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
    chapter_parallelism = int(incoming.get("chapter_parallelism") or DEFAULT_CONFIG["chapter_parallelism"])
    chapter_retry = int(incoming.get("chapter_retry") or DEFAULT_CONFIG["chapter_retry"])
    pipeline_agents = incoming.get("pipeline_agents") or DEFAULT_CONFIG["pipeline_agents"]
    if isinstance(pipeline_agents, str):
        pipeline_agents = [item.strip() for item in pipeline_agents.split(",") if item.strip()]
    pipeline_agents = [agent for agent in pipeline_agents if agent in {"outline", "writer", "reviewer", "finalizer"}]
    focus = incoming.get("global_review_focus") or DEFAULT_CONFIG["global_review_focus"]
    if isinstance(focus, str):
        focus = [item.strip() for item in re.split(r"[,;\n]", focus) if item.strip()]

    normalized = {
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
        "chapter_parallelism": max(1, chapter_parallelism),
        "chapter_retry": max(1, chapter_retry),
        "pipeline_agents": pipeline_agents or list(DEFAULT_CONFIG["pipeline_agents"]),
        "agent_workers": incoming.get("agent_workers") if isinstance(incoming.get("agent_workers"), list) else [],
        "global_review_enabled": bool_value(
            incoming.get("global_review_enabled"),
            bool(DEFAULT_CONFIG["global_review_enabled"]),
        ),
        "global_review_mode": str(incoming.get("global_review_mode") or DEFAULT_CONFIG["global_review_mode"]),
        "global_review_focus": focus if isinstance(focus, list) else list(DEFAULT_CONFIG["global_review_focus"]),
        "allow_global_rewrite": bool_value(
            incoming.get("allow_global_rewrite"),
            bool(DEFAULT_CONFIG["allow_global_rewrite"]),
        ),
    }
    normalized["agent_workers"] = normalize_agent_workers(normalized)
    return normalized


def normalize_agent_workers(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_workers = config.get("agent_workers") or []
    workers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_workers):
        if not isinstance(raw, dict):
            continue
        server_base_url = str(raw.get("server_base_url") or "").strip().rstrip("/")
        if not server_base_url:
            continue
        worker = {
            "name": str(raw.get("name") or f"worker-{index + 1}"),
            "server_base_url": server_base_url,
            "generate_path": str(raw.get("generate_path") or config["generate_path"]),
            "status_path": str(raw.get("status_path") or config["status_path"]),
            "request_timeout_seconds": int(raw.get("request_timeout_seconds") or config["request_timeout_seconds"]),
            "user_id": str(raw.get("user_id") if raw.get("user_id") is not None else config["user_id"]),
            "password": str(raw.get("password") if raw.get("password") is not None else config["password"]),
            "model": str(raw.get("model") if raw.get("model") is not None else config["model"]),
            "keep_alive": str(raw.get("keep_alive") or config["keep_alive"]),
            "num_ctx": int(raw.get("num_ctx") or config["num_ctx"]),
            "max_parallel": max(1, int(raw.get("max_parallel") or 1)),
        }
        workers.append(worker)

    if workers:
        return workers

    return [
        {
            "name": "default",
            "server_base_url": config["server_base_url"],
            "generate_path": config["generate_path"],
            "status_path": config["status_path"],
            "request_timeout_seconds": config["request_timeout_seconds"],
            "user_id": config["user_id"],
            "password": config["password"],
            "model": config["model"],
            "keep_alive": config["keep_alive"],
            "num_ctx": config["num_ctx"],
            "max_parallel": max(1, int(config.get("chapter_parallelism") or 1)),
        }
    ]


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


def split_backbone_option_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value or "") if item.strip()]


def parse_backbone_key_values(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in split_backbone_option_items(value):
        if "=" in item:
            key, raw_value = item.split("=", 1)
        elif ":" in item and not re.match(r"^https?://", item.strip(), re.IGNORECASE):
            key, raw_value = item.split(":", 1)
        else:
            continue
        parsed[key.strip().lower().replace("-", "_")] = raw_value.strip()
    return parsed


def normalize_backbone_worker(value: str, index: int, base_config: dict[str, Any]) -> dict[str, Any] | None:
    values = parse_backbone_key_values(value)
    if not values and re.search(r"https?://", value, re.IGNORECASE):
        parts = value.split()
        values = {"server_base_url": parts[0]}
        if len(parts) > 1:
            values["name"] = parts[1]

    url = values.get("url") or values.get("server") or values.get("server_base_url") or values.get("base_url")
    if not url:
        return None

    worker = {
        "name": values.get("name") or values.get("이름") or f"backbone-worker-{index}",
        "server_base_url": url.rstrip("/"),
        "generate_path": values.get("generate_path") or values.get("path") or base_config["generate_path"],
        "status_path": values.get("status_path") or base_config["status_path"],
        "request_timeout_seconds": int(values.get("timeout") or values.get("request_timeout_seconds") or base_config["request_timeout_seconds"]),
        "user_id": values.get("user_id") or values.get("id") or base_config["user_id"],
        "password": values.get("password") or values.get("pass") or base_config["password"],
        "model": values.get("model") or values.get("모델") or base_config["model"],
        "keep_alive": values.get("keep_alive") or base_config["keep_alive"],
        "num_ctx": int(values.get("num_ctx") or base_config["num_ctx"]),
        "max_parallel": max(1, int(values.get("max_parallel") or values.get("parallel") or values.get("병렬") or 1)),
    }
    return worker


def parse_backbone_runtime_options(backbone: str, base_config: dict[str, Any], chapter_count: int) -> tuple[dict[str, Any], list[str]]:
    options: dict[str, Any] = {}
    alerts: list[str] = []
    workers: list[dict[str, Any]] = []
    parallel_requested = False
    parallelism_explicit = False

    for raw_line in backbone.splitlines():
        line = re.sub(r"^\s*[-*]\s*", "", raw_line).strip()
        if not line:
            continue

        match = re.match(r"^(?:병렬\s*실행|parallel(?:_run|_enabled)?|parallel)\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if match:
            parallel_requested = backbone_bool_value(match.group(1))
            alerts.append(f"story_backbone.md 병렬실행={parallel_requested}")
            continue

        match = re.match(r"^(?:병렬\s*챕터|동시\s*챕터|parallel\s*chapters|chapter_parallelism|parallelism)\s*[:=]\s*(\d+)", line, re.IGNORECASE)
        if match:
            options["chapter_parallelism"] = max(1, int(match.group(1)))
            parallel_requested = True
            parallelism_explicit = True
            alerts.append(f"story_backbone.md chapter_parallelism={options['chapter_parallelism']}")
            continue

        match = re.match(r"^(?:모델\s*worker|모델\s*워커|agent\s*worker|worker)\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if match:
            worker = normalize_backbone_worker(match.group(1), len(workers) + 1, base_config)
            if worker:
                workers.append(worker)
                parallel_requested = True
                alerts.append(f"story_backbone.md worker={worker['name']} {worker['server_base_url']} model={worker.get('model') or 'default'}")
            continue

    if workers:
        options["agent_workers"] = workers
    if parallel_requested:
        slot_count = sum(max(1, int(worker.get("max_parallel") or 1)) for worker in (workers or base_config.get("agent_workers") or []))
        default_parallelism = max(1, min(chapter_count, slot_count or int(base_config.get("chapter_parallelism") or 1)))
        if not parallelism_explicit:
            options["chapter_parallelism"] = max(int(base_config.get("chapter_parallelism") or 1), default_parallelism)
        options["_backbone_parallel_enabled"] = True
        options["_backbone_parallel_alerts"] = alerts
    return options, alerts


def apply_backbone_runtime_options(config: dict[str, Any], backbone: str, chapter_count: int) -> dict[str, Any]:
    options, _ = parse_backbone_runtime_options(backbone, config, chapter_count)
    if not options:
        return config
    merged = dict(config)
    private_alerts = options.pop("_backbone_parallel_alerts", [])
    parallel_enabled = bool(options.pop("_backbone_parallel_enabled", False))
    merged.update(options)
    normalized = normalize_config(merged)
    normalized["_backbone_parallel_enabled"] = parallel_enabled
    normalized["_backbone_parallel_alerts"] = private_alerts
    return normalized


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


def chapter_context(backbone: str, chapter: dict[str, Any], config: dict[str, Any]) -> str:
    bullets = "\n".join(f"- {item}" for item in chapter["bullets"])
    return f"""책 전체 기획:
{backbone}

담당 챕터:
{chapter['title']}
{bullets}

공통 작성 지침:
- 한국어로 작성합니다.
- 목표 분량은 약 {config['target_words_per_chapter']} 단어입니다.
- 사실 설명, 시대적 맥락, 핵심 앨범/뮤지션 목록, 해설을 균형 있게 넣습니다.
- 책 전체의 일부가 되도록 독립된 챕터 제목과 절 구성을 포함합니다.
- 메타 설명 없이 원고 또는 편집 산출물만 출력합니다.
"""


def outline_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any]) -> str:
    return f"""당신은 책 챕터의 구조를 설계하는 outline agent입니다.

{chapter_context(backbone, chapter, config)}

작업:
1. 챕터 도입부의 hook을 제안합니다.
2. 3~6개의 주요 절을 설계합니다.
3. 각 절의 핵심 논점, 사례, 연결 문장을 bullet로 정리합니다.
4. 전체 책의 다른 챕터와 연결될 전환 메모를 포함합니다.

출력 형식:
# {chapter['title']} Outline
## 도입
...
## 절 구성
...
## 전환 메모
...
"""


def writer_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any], chapter_outline: str) -> str:
    return f"""당신은 책의 한 챕터를 담당하는 writer agent입니다.

{chapter_context(backbone, chapter, config)}

outline agent 산출물:
{chapter_outline}

작업:
- outline의 구조를 따라 완성도 있는 챕터 초안을 작성합니다.
- bullet 위주가 아니라 출판 원고에 가까운 문단 중심 산문으로 작성합니다.
- 제목은 Markdown heading으로 시작합니다.
- 아직 reviewer와 finalizer가 보기 전의 초안이므로, 내용 누락 없이 충분히 씁니다.
"""


def reviewer_prompt(
    backbone: str,
    chapter: dict[str, Any],
    config: dict[str, Any],
    chapter_outline: str,
    chapter_draft: str,
) -> str:
    return f"""당신은 전문 편집자 reviewer agent입니다.

{chapter_context(backbone, chapter, config)}

outline:
{chapter_outline}

writer agent 초안:
{chapter_draft}

작업:
1. 명확성, 흐름, 완성도, 용어 일관성, 흥미도를 기준으로 초안을 개선합니다.
2. outline에서 빠진 내용을 보강합니다.
3. 사실관계가 어색하거나 과장된 부분은 보수적으로 정리합니다.

출력:
- 리뷰 코멘트가 아니라 개선이 반영된 챕터 전체 원고만 출력합니다.
"""


def finalizer_prompt(backbone: str, chapter: dict[str, Any], config: dict[str, Any], chapter_review: str) -> str:
    return f"""당신은 최종 원고를 정리하는 finalizer agent입니다.

{chapter_context(backbone, chapter, config)}

reviewer agent 개선 원고:
{chapter_review}

작업:
- Markdown heading 계층을 정리합니다.
- 반복, TODO, 메타 코멘트, 불필요한 안내문을 제거합니다.
- 문단 사이 전환을 부드럽게 다듬습니다.
- 챕터 제목으로 시작하는 최종 원고만 출력합니다.
"""


def coordinator_prompt(backbone: str, chapter_drafts: list[dict[str, Any]], config: dict[str, Any]) -> str:
    draft_text = "\n\n".join(
        f"## {item['chapter']['title']} 최종안\n{item.get('final', item.get('draft', ''))}" for item in chapter_drafts
    )
    focus = "\n".join(f"- {item}" for item in config.get("global_review_focus", []))
    rewrite_policy = "필요한 챕터의 재작성 지시까지 작성합니다." if config.get("allow_global_rewrite") else "원고를 직접 재작성하지 말고 수정 지시만 작성합니다."
    return f"""당신은 전체 책을 조율하는 main writer agent입니다.

책 전체 기획:
{backbone}

리뷰 모드: {config.get('global_review_mode', 'strict')}
리뷰 초점:
{focus}

아래는 각 챕터 파이프라인의 최종 출력입니다.
{draft_text}

작업:
1. 전체 책의 논지, 시대 흐름, 용어, 반복/누락을 점검합니다.
2. 1챕터 초반부와 책의 도입부가 뒤 챕터의 방향과 어긋나는 부분을 찾아 수정 방향을 제시합니다.
3. 최종 원고에서 초반부가 어떤 관점을 깔아야 하는지 구체적인 편집 지시를 작성합니다.
4. {rewrite_policy}

출력 형식:
## 전체 편집 방향
...

## 챕터별 수정 지시
...

## 초반부 수정 지시
...
"""


def revise_opening_prompt(backbone: str, chapter_drafts: list[dict[str, Any]], coordinator_notes: str) -> str:
    first_chapter = chapter_drafts[0].get("final", chapter_drafts[0].get("draft", "")) if chapter_drafts else ""
    other_summaries = "\n\n".join(
        f"## {item['chapter']['title']}\n{item.get('final', item.get('draft', ''))[:2500]}" for item in chapter_drafts[1:]
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
    remaining = "\n\n".join(item.get("final", item.get("draft", "")) for item in chapter_drafts[1:])
    return f"""# {title}

> generated by writing_mach on {time.strftime('%Y-%m-%d %H:%M:%S')}

## Main Writer Notes

{coordinator_notes}

---

{revised_opening}

---

{remaining}
"""


def worker_slots(config: dict[str, Any]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for worker in config["agent_workers"]:
        slots.extend([worker] * max(1, int(worker.get("max_parallel") or 1)))
    return slots or config["agent_workers"]


def run_chapter_pipeline(
    config: dict[str, Any],
    worker: dict[str, Any],
    backbone: str,
    chapter: dict[str, Any],
    index: int,
    total: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    worker_name = worker.get("name", "worker")
    pipeline_agents = config.get("pipeline_agents") or DEFAULT_CONFIG["pipeline_agents"]
    progress_log(
        "chapter",
        f"{index}/{total} {chapter['title']} pipeline started on {worker_name} ({','.join(pipeline_agents)})",
        "yellow",
    )

    outputs: dict[str, str] = {}
    current_text = ""
    for agent in pipeline_agents:
        agent_started = time.perf_counter()
        progress_log("agent", f"{chapter['title']}:{agent} -> {worker_name}", "blue")
        if agent == "outline":
            current_text = call_model(worker, outline_prompt(backbone, chapter, config))
            outputs["outline"] = current_text
        elif agent == "writer":
            current_text = call_model(worker, writer_prompt(backbone, chapter, config, outputs.get("outline", "")))
            outputs["draft"] = current_text
        elif agent == "reviewer":
            current_text = call_model(
                worker,
                reviewer_prompt(
                    backbone,
                    chapter,
                    config,
                    outputs.get("outline", ""),
                    outputs.get("draft", current_text),
                ),
            )
            outputs["review"] = current_text
        elif agent == "finalizer":
            current_text = call_model(worker, finalizer_prompt(backbone, chapter, config, outputs.get("review", current_text)))
            outputs["final"] = current_text
        progress_log(
            "agent",
            f"{chapter['title']}:{agent} done ({word_count(current_text)} words)",
            "green",
            agent_started,
        )

    final_text = outputs.get("final") or outputs.get("review") or outputs.get("draft") or outputs.get("outline") or current_text
    progress_log(
        "chapter",
        f"{index}/{total} {chapter['title']} pipeline done on {worker_name} ({word_count(final_text)} words)",
        "green",
        started,
    )
    return {
        "chapter": chapter,
        "worker": worker_name,
        "elapsed_seconds": time.perf_counter() - started,
        "outline": outputs.get("outline", ""),
        "draft": outputs.get("draft", ""),
        "review": outputs.get("review", ""),
        "final": final_text,
    }


def run_chapter_with_retry(
    config: dict[str, Any],
    worker: dict[str, Any],
    backbone: str,
    chapter: dict[str, Any],
    index: int,
    total: int,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, int(config["chapter_retry"]) + 1):
        try:
            if attempt > 1:
                progress_log("retry", f"{chapter['title']} attempt {attempt}/{config['chapter_retry']}", "yellow")
            return run_chapter_pipeline(config, worker, backbone, chapter, index, total)
        except Exception as exc:
            last_error = str(exc)
            progress_log("retry", f"{chapter['title']} failed attempt {attempt}: {last_error}", "red")
    raise ValueError(f"{chapter['title']} failed after {config['chapter_retry']} attempts: {last_error}")


def run_book_agents(config: dict[str, Any], backbone: str | None = None) -> dict[str, Any]:
    ensure_dirs()
    backbone_text = (backbone or read_story_backbone()).strip()
    chapters = parse_chapters(backbone_text)
    config = apply_backbone_runtime_options(config, backbone_text, len(chapters))
    started = time.perf_counter()
    progress_log("start", f"book agent run started: {len(chapters)} chapters", "bold", started)
    progress_log("backbone", f"title='{title_from_backbone(backbone_text)}'", "cyan", started)
    if config.get("_backbone_parallel_enabled"):
        for alert in config.get("_backbone_parallel_alerts", []):
            progress_log("parallel-alert", alert, "magenta", started)
        progress_log(
            "parallel-alert",
            "story_backbone.md requested parallel chapter execution",
            "magenta",
            started,
        )

    slots = worker_slots(config)
    max_workers = min(len(chapters), int(config["chapter_parallelism"]), len(slots))
    progress_log(
        "dispatch",
        f"chapter parallelism={max_workers}, worker slots={len(slots)}, pipeline={','.join(config['pipeline_agents'])}",
        "cyan",
        started,
    )

    chapter_drafts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for index, chapter in enumerate(chapters, start=1):
            worker = slots[(index - 1) % len(slots)]
            future = executor.submit(run_chapter_with_retry, config, worker, backbone_text, chapter, index, len(chapters))
            futures[future] = chapter

        for future in as_completed(futures):
            chapter_drafts.append(future.result())

    chapter_drafts.sort(key=lambda item: int(item["chapter"]["number"]))

    if config.get("global_review_enabled"):
        coordinator_started = time.perf_counter()
        progress_log("main-writer", "reviewing finalized chapter outputs and preparing direction notes", "magenta", started)
        coordinator_notes = call_model(config, coordinator_prompt(backbone_text, chapter_drafts, config))
        progress_log(
            "main-writer",
            f"direction notes done ({word_count(coordinator_notes)} words)",
            "green",
            coordinator_started,
        )
    else:
        coordinator_notes = "Global review disabled by config."

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
                "config": public_config(config),
                "backbone_parallel_enabled": bool(config.get("_backbone_parallel_enabled")),
                "backbone_parallel_alerts": config.get("_backbone_parallel_alerts", []),
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
        "backbone_parallel_enabled": bool(config.get("_backbone_parallel_enabled")),
        "backbone_parallel_alerts": config.get("_backbone_parallel_alerts", []),
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
