#!/usr/bin/env python3
"""Create structured Markdown documents from local or WebDAV business-card images."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests

from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    call_vision_ocr,
    image_mime_type,
)

DEFAULT_WEBDAV_URL = "http://keties.iptime.org:4001/apps/memories/folders/Photos/memories/biz_card"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
BIZCARD_PROMPT = """너는 명함 OCR 및 연락처 정보 추출기다. 첨부된 명함 이미지 한 장을 읽어라.
보이는 내용만 사용하고 추측하지 말며, 반드시 설명이나 Markdown 코드 펜스 없이 JSON 객체 하나만 응답한다.

JSON 필드:
{
  "name": "성명",
  "name_en": "영문 성명",
  "company": "회사 또는 기관",
  "department": "부서",
  "title": "직책",
  "mobile": ["휴대전화"],
  "phone": ["일반전화"],
  "fax": ["팩스"],
  "email": ["이메일"],
  "website": ["웹사이트"],
  "address": ["주소"],
  "other": ["그 밖의 표시 정보"],
  "raw_text": "명함에서 읽은 전체 문자열"
}

값이 보이지 않는 문자열 필드는 빈 문자열, 목록 필드는 빈 목록으로 기록한다.
전화번호, 이메일, URL의 원문 표기를 보존하고 한국어와 영문을 모두 전사한다.
"""


@dataclass(frozen=True)
class CardImage:
    name: str
    source: str
    data: bytes


def discover_local_cards(paths: Iterable[Path] | None = None) -> list[CardImage]:
    """Read explicit images or all card images below input/."""
    root = DEFAULT_INPUT_DIR.resolve()
    requested = list(paths or [])
    candidates = requested or sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES),
        key=lambda path: str(path).casefold(),
    )
    cards: list[CardImage] = []
    for requested_path in candidates:
        direct = requested_path.expanduser().resolve()
        selected = direct if direct.exists() else (root / requested_path).resolve()
        try:
            selected.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"명함 파일은 input 디렉토리 내부에 있어야 합니다: {selected}") from exc
        if not selected.is_file() or selected.suffix.casefold() not in IMAGE_SUFFIXES:
            raise ValueError(f"지원되는 JPG/PNG 명함 파일이 아닙니다: {selected}")
        data = selected.read_bytes()
        image_mime_type(data)
        cards.append(CardImage(selected.name, str(selected), data))
    return cards


def _webdav_image_urls(xml_data: bytes, base_url: str) -> list[str]:
    root = ET.fromstring(xml_data)
    base_path = unquote(urlparse(base_url).path.rstrip("/"))
    urls: list[str] = []
    for response in root.findall("{DAV:}response"):
        href_node = response.find("{DAV:}href")
        resource_type = response.find(".//{DAV:}resourcetype")
        href = str(href_node.text or "") if href_node is not None else ""
        path = unquote(urlparse(href).path.rstrip("/"))
        is_collection = resource_type is not None and resource_type.find("{DAV:}collection") is not None
        if href and path != base_path and not is_collection and Path(path).suffix.casefold() in IMAGE_SUFFIXES:
            urls.append(urljoin(base_url.rstrip("/") + "/", href))
    return sorted(set(urls), key=str.casefold)


def read_webdav_cards(
    webdav_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
    timeout: int = 30,
    session: requests.Session | None = None,
) -> list[CardImage]:
    """List a WebDAV collection with PROPFIND and download JPG/PNG members."""
    client = session or requests.Session()
    auth = (username, password or "") if username else None
    response = client.request(
        "PROPFIND", webdav_url, headers={"Depth": "1"}, auth=auth, timeout=max(1, timeout)
    )
    response.raise_for_status()
    try:
        urls = _webdav_image_urls(response.content, webdav_url)
    except ET.ParseError as exc:
        raise ValueError(f"WebDAV 목록 XML을 읽을 수 없습니다: {exc}") from exc
    cards: list[CardImage] = []
    for url in urls:
        item = client.get(url, auth=auth, timeout=max(1, timeout))
        item.raise_for_status()
        image_mime_type(item.content)
        name = unquote(Path(urlparse(url).path).name) or "business-card"
        cards.append(CardImage(name, url, item.content))
    return cards


def save_webdav_cards(cards: Iterable[CardImage], directory: Path) -> list[Path]:
    """Save downloaded WebDAV images locally without overwriting duplicate names."""
    destination = directory.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    reserved: set[str] = set()
    for card in cards:
        original_name = Path(card.name).name or "business-card"
        stem = Path(original_name).stem or "business-card"
        suffix = Path(original_name).suffix.casefold()
        if suffix not in IMAGE_SUFFIXES:
            suffix = ".jpg"
        candidate = f"{stem}{suffix}"
        sequence = 2
        while candidate.casefold() in reserved:
            candidate = f"{stem}_{sequence}{suffix}"
            sequence += 1
        reserved.add(candidate.casefold())
        output_path = destination / candidate
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_bytes(card.data)
        temporary.replace(output_path)
        saved.append(output_path)
    return saved


def parse_bizcard_response(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("명함 OCR 응답에서 JSON 객체를 찾지 못했습니다.")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("명함 OCR 결과는 JSON 객체여야 합니다.")
    for field in ("name", "name_en", "company", "department", "title", "raw_text"):
        data[field] = str(data.get(field) or "").strip()
    for field in ("mobile", "phone", "fax", "email", "website", "address", "other"):
        value = data.get(field) or []
        if isinstance(value, str):
            value = [value]
        data[field] = [str(item).strip() for item in value if str(item).strip()]
    return data


def _markdown_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- (없음)"


def bizcard_markdown(card: dict[str, Any], source: str, *, heading_level: int = 1) -> str:
    display_name = card["name"] or card["name_en"] or "이름 미상"
    scalar_rows = [
        ("성명", card["name"]), ("영문 성명", card["name_en"]),
        ("회사/기관", card["company"]), ("부서", card["department"]), ("직책", card["title"]),
    ]
    title_prefix = "#" * max(1, heading_level)
    section_prefix = "#" * (max(1, heading_level) + 1)
    lines = [
        f"{title_prefix} 명함 - {display_name}", "", f"원본: {source}", "",
        f"{section_prefix} 기본 정보", "",
    ]
    lines.extend(f"- {label}: {value or '(없음)'}" for label, value in scalar_rows)
    for label, field in (
        ("휴대전화", "mobile"), ("전화", "phone"), ("팩스", "fax"),
        ("이메일", "email"), ("웹사이트", "website"), ("주소", "address"), ("기타", "other"),
    ):
        lines.extend(["", f"{section_prefix} {label}", "", _markdown_list(card[field])])
    lines.extend(["", f"{section_prefix} OCR 원문", "", card["raw_text"] or "(없음)"])
    return "\n".join(lines).strip()


def load_bizcard_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "records": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError(f"명함 처리 상태 파일 형식이 올바르지 않습니다: {path}")
    return data


def save_bizcard_state(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def render_bizcard_document(records: list[dict[str, Any]]) -> str:
    lines = ["# 명함 문서", "", "## Index", ""]
    for index, record in enumerate(records, 1):
        card = record["card"]
        name = card.get("name") or card.get("name_en") or "이름 미상"
        company = card.get("company") or "소속 미상"
        lines.append(f"- [{name} — {company}](#bizcard-{index})")
    for index, record in enumerate(records, 1):
        lines.extend([
            "", "---", "", f'<a id="bizcard-{index}"></a>', "",
            bizcard_markdown(record["card"], record["source"], heading_level=2),
        ])
    return "\n".join(lines).strip() + "\n"


def process_cards(
    cards: list[CardImage], *, config_path: Path, output_dir: Path,
    model_password: str | None = None, force: bool = False,
    cloud_fast_track: bool = False, cloud_fast_track_url: str | None = None,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / ".bizcard_state.json"
    document_path = output_dir / "bizcards.md"
    state = load_bizcard_state(state_path)
    records: list[dict[str, Any]] = state["records"]
    source_indexes = {str(record.get("source")): index for index, record in enumerate(records)}
    results: list[dict[str, Any]] = []
    for index, image in enumerate(cards, 1):
        previous_index = source_indexes.get(image.source)
        if previous_index is not None and not force:
            print(f"[{index}/{len(cards)}] 이미 처리하여 건너뜀: {image.source}", flush=True)
            continue
        print(f"[{index}/{len(cards)}] 명함 OCR: {image.source}", flush=True)
        response, model = call_vision_ocr(
            [image.data], BIZCARD_PROMPT, config_path=config_path, password=model_password,
            client_id="read-mach-bizcard-extractor",
            cloud_fast_track=cloud_fast_track, cloud_fast_track_url=cloud_fast_track_url,
        )
        card = parse_bizcard_response(response)
        record = {
            "source": image.source, "source_name": image.name, "card": card,
            "processed_at": datetime.now(timezone.utc).isoformat(), **model,
        }
        if previous_index is None:
            source_indexes[image.source] = len(records)
            records.append(record)
        else:
            records[previous_index] = record
        state["records"] = records
        document_path.write_text(render_bizcard_document(records), encoding="utf-8")
        save_bizcard_state(state_path, state)
        results.append(record)
    document_path.write_text(render_bizcard_document(records), encoding="utf-8")
    print(f"통합 명함 문서 저장: {document_path}", flush=True)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="명함 이미지를 OCR하여 Markdown 연락처 문서를 만듭니다.")
    parser.add_argument("--input-file", type=Path, action="append", default=[])
    parser.add_argument("--webdav", action="store_true", help="WebDAV 명함 폴더에서 원본을 읽습니다.")
    parser.add_argument("--webdav-url", default=DEFAULT_WEBDAV_URL)
    parser.add_argument("--webdav-username", default=os.getenv("READ_MACH_WEBDAV_USERNAME"))
    parser.add_argument("--webdav-password", default=os.getenv("READ_MACH_WEBDAV_PASSWORD"))
    parser.add_argument("--webdav-timeout", type=int, default=30)
    parser.add_argument(
        "--webdav-save-dir",
        type=Path,
        help="WebDAV에서 받은 원본 JPG/PNG를 함께 저장할 로컬 디렉토리",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password", help="모델 서버 비밀번호")
    parser.add_argument("--cloud-fast-track", action="store_true")
    parser.add_argument("--cloud-fast-track-url")
    parser.add_argument("--force", action="store_true", help="이미 처리한 동일 경로 명함도 다시 OCR")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        cards = read_webdav_cards(
            args.webdav_url, username=args.webdav_username, password=args.webdav_password,
            timeout=args.webdav_timeout,
        ) if args.webdav else discover_local_cards(args.input_file)
        if not cards:
            raise ValueError("처리할 JPG/PNG 명함 이미지가 없습니다.")
        if args.webdav_save_dir:
            if not args.webdav:
                raise ValueError("--webdav-save-dir은 --webdav와 함께 사용해야 합니다.")
            saved_paths = save_webdav_cards(cards, args.webdav_save_dir)
            print(f"WebDAV 원본 저장 완료: {len(saved_paths)}개 -> {args.webdav_save_dir}")
        results = process_cards(
            cards, config_path=args.config, output_dir=args.output_dir,
            model_password=args.password, force=args.force,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
        )
        print(f"명함 문서 생성 완료: 새로 처리 {len(results)}개, 입력 {len(cards)}개")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        print(f"명함 문서 생성 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
