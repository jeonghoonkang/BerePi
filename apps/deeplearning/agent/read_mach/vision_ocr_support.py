#!/usr/bin/env python3
"""Shared input validation and vision-model OCR support for read_mach."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = APP_DIR / "input"
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "server_config.json"


def select_input_file(input_file: Path, suffix: str) -> Path:
    """Resolve one file below input/, rejecting traversal and wrong suffixes."""
    input_dir = DEFAULT_INPUT_DIR.resolve()
    requested = input_file.expanduser()
    direct = requested.resolve()
    selected = direct if direct.exists() else (input_dir / requested).resolve()
    try:
        selected.relative_to(input_dir)
    except ValueError as exc:
        raise ValueError(f"--input-file은 input 디렉토리 내부 파일이어야 합니다: {selected}") from exc
    if not selected.is_file():
        raise FileNotFoundError(f"선택한 입력 파일이 없습니다: {selected}")
    if selected.suffix.casefold() != suffix.casefold():
        raise ValueError(f"--input-file은 {suffix} 파일이어야 합니다: {selected}")
    return selected


def image_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def image_mime_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise ValueError("지원되는 PNG/JPEG 이미지 데이터가 아닙니다.")


def call_vision_ocr(
    images: list[bytes],
    prompt: str,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    password: str | None = None,
    client_id: str = "read-mach-image-text-extractor",
) -> tuple[str, dict[str, Any]]:
    """Send one or more encoded images to the configured routing server."""
    import requests

    from extract_picture_pages import (
        auth_headers,
        load_server_config,
        response_text,
        select_ollama_target,
    )

    config = load_server_config(config_path)
    password_env = str(config.get("password_env") or "READ_MACH_PASSWORD")
    secret = password or os.getenv(password_env)
    if not secret:
        raise ValueError(f"서버 비밀번호가 없습니다. {password_env} 환경변수를 입력하세요.")
    server_url = str(config.get("server_url") or "").rstrip("/")
    if not server_url:
        raise ValueError("설정 파일의 server_url이 비어 있습니다.")
    timeout = int(config.get("timeout_seconds") or 240)
    requested_model = str(config.get("model") or "")
    explicit_target = str(config.get("target_id") or "") or None
    encoded = [(image_to_base64(image), image_mime_type(image)) for image in images]

    with requests.Session() as session:
        target_id, model, api_type = select_ollama_target(
            session,
            server_url=server_url,
            password=secret,
            requested_model=requested_model,
            explicit_target_id=explicit_target,
        )
        payload: dict[str, Any] = {
            "client_id": client_id,
            "model": model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0,
            "timeout": timeout,
            "target_id": target_id,
        }
        if api_type == "vllm":
            payload["messages"] = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *[
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{item}"}}
                        for item, mime in encoded
                    ],
                ],
            }]
        else:
            payload["images"] = [item for item, _mime in encoded]
        response = session.post(
            f"{server_url}/api/generate",
            headers=auth_headers(secret),
            json=payload,
            timeout=timeout + 30,
        )
        if not response.ok:
            detail = response.text.strip().replace("\n", " ")[:500]
            raise requests.HTTPError(
                f"OCR 요청 실패: {response.status_code} {response.reason}: {detail}", response=response
            )
        text = response_text(response.json()).strip()
        if not text:
            raise ValueError("모델 OCR 응답이 비어 있습니다.")
        return text, {"ocr_engine": "vision-model", "ocr_model": model, "target_id": target_id}


OCR_PROMPT = """너는 기술문서 OCR 전사기다. 첨부 이미지를 읽고 보이는 문자를 정확히 전사해라.
- 한국어와 영문 기술 용어를 원문 그대로 보존한다.
- 제목, 본문, 표, 목록, 코드, 수식의 읽기 순서를 유지한다.
- 표는 가능한 경우 Markdown 표로 변환한다.
- 보이지 않는 내용은 추측하거나 설명하지 않는다.
- 안내 문구와 코드 펜스 없이 추출된 본문만 출력한다.
"""
