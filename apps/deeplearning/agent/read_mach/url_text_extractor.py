#!/usr/bin/env python3
"""Download a web page and save its readable article text."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup, Tag

APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "server_config.json"
REMOVED_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "nav",
    "header",
    "footer",
    "aside",
}


def validate_url(url: str) -> str:
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--url은 http:// 또는 https:// 웹 주소여야 합니다.")
    return value


def output_stem_for_url(url: str) -> str:
    parsed = urlparse(url)
    path_name = unquote(parsed.path.rstrip("/").split("/")[-1]) or "index"
    safe_name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", path_name).strip("._-")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    return f"url_{safe_name[:80] or 'page'}_{digest}"


def _clean_line(text: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", text).strip()


def _table_text(table: Tag) -> list[str]:
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [_clean_line(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(row) + " |" for row in padded]
    if table.find("th"):
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
    return lines


def extract_article_text(html: str, source_url: str) -> tuple[str, dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(REMOVED_TAGS):
        tag.decompose()

    title = _clean_line(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if not title:
        social_title = soup.find("meta", attrs={"property": "og:title"})
        if isinstance(social_title, Tag):
            title = _clean_line(str(social_title.get("content") or ""))
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical_url = str(canonical_tag.get("href") or "") if isinstance(canonical_tag, Tag) else ""
    root = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body
    if root is None:
        raise ValueError("웹페이지에서 읽을 수 있는 본문 영역을 찾지 못했습니다.")
    if not title:
        first_heading = root.find("h1") or root.find("h2")
        if isinstance(first_heading, Tag):
            title = _clean_line(first_heading.get_text(" ", strip=True))

    lines: list[str] = []
    if title:
        lines.extend([f"# {title}", ""])
    lines.extend([f"Source: {canonical_url or source_url}", ""])

    for element in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "table"]):
        if element.find_parent(["table", "pre"]) and element.name not in {"table", "pre"}:
            continue
        if element.name == "table":
            block = _table_text(element)
        else:
            value = _clean_line(element.get_text(" ", strip=True))
            if not value:
                continue
            if element.name and element.name.startswith("h"):
                block = [f"{'#' * int(element.name[1])} {value}"]
            elif element.name == "li":
                block = [f"- {value}"]
            elif element.name == "blockquote":
                block = [f"> {value}"]
            else:
                block = [value]
        if block and (not lines or lines[-1] != block[0]):
            lines.extend(block)
            lines.append("")

    text = "\n".join(lines).strip()
    if len(text) < 40:
        fallback = _clean_line(root.get_text(" ", strip=True))
        text = f"# {title}\n\nSource: {canonical_url or source_url}\n\n{fallback}".strip()
    if len(text) < 40:
        raise ValueError("웹페이지 본문에서 저장할 문자를 충분히 추출하지 못했습니다.")
    return text, {"title": title, "canonical_url": canonical_url or source_url}


def fetch_url_text(url: str, timeout: int = 30) -> tuple[str, dict[str, object]]:
    source_url = validate_url(url)
    response = requests.get(
        source_url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BerePi-read_mach/1.0; +https://github.com/jeonghoonkang/BerePi)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.casefold():
        raise ValueError(f"HTML 웹페이지가 아닙니다: Content-Type={content_type or 'unknown'}")
    text, page = extract_article_text(response.text, source_url)
    metadata: dict[str, object] = {
        "source_url": source_url,
        "final_url": response.url,
        "canonical_url": page["canonical_url"],
        "title": page["title"],
        "characters": len(text),
        "content_type": content_type,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return text, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="URL 웹페이지의 본문 문자를 output에 저장합니다.")
    parser.add_argument("--url", required=True, help="읽을 http/https 웹페이지 주소")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="read_mach 서버 설정 파일 경로. URL 추출에서는 비밀번호를 사용하지 않습니다.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not args.config.is_file():
            raise ValueError(f"설정 파일이 없습니다: {args.config}")
        text, metadata = fetch_url_text(args.url, timeout=max(1, args.timeout))
        metadata["config_path"] = str(args.config.expanduser().resolve())
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = output_stem_for_url(args.url)
        text_path = args.output_dir / f"{stem}.txt"
        metadata_path = args.output_dir / f"{stem}.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"URL 문자 저장: {text_path}")
        print(f"URL 정보 저장: {metadata_path}")
        return 0
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"URL 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
