#!/usr/bin/env python3
"""Shared input validation and vision-model OCR support for read_mach."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = APP_DIR / "input"
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "server_config.json"
_VERIFIED_CLOUD_FAST_TRACK_URLS: set[str] = set()


@dataclass(frozen=True)
class LocalParallelPlan:
    """Available local OCR capacity calculated from the routing status endpoint."""

    available_gpu_count: int
    available_model_count: int
    available_count: int
    max_workers: int
    target_ids: tuple[str, ...]


def resolve_model_server_url(
    config: dict[str, Any], *, cloud_fast_track: bool = False,
    cloud_fast_track_url: str | None = None,
) -> tuple[str, str]:
    """Resolve the selected routing URL and return it with its source label."""
    if cloud_fast_track:
        server_url = str(cloud_fast_track_url or config.get("cloud_fast_track_url") or "").strip()
        if not server_url:
            raise ValueError(
                "Cloud Fast Track 주소가 비어 있습니다. 설정 파일의 "
                "cloud_fast_track_url 또는 --cloud-fast-track-url을 입력하세요."
            )
        return server_url.rstrip("/"), "cloud-fast-track"

    server_url = str(config.get("server_url") or "").strip()
    if not server_url:
        raise ValueError("설정 파일의 server_url이 비어 있습니다.")
    return server_url.rstrip("/"), "server"


def model_generate_url(server_url: str, *, cloud_fast_track: bool = False) -> str:
    """Return the generate URL for the selected routing mode."""
    url = server_url.rstrip("/")
    endpoint = "/api/gcp/generate" if cloud_fast_track else "/api/generate"
    return f"{url}{endpoint}"


def model_status_url(server_url: str, *, cloud_fast_track: bool = False) -> str:
    """Return the status URL for the selected routing mode."""
    url = server_url.rstrip("/")
    endpoint = "/api/gcp/status" if cloud_fast_track else "/api/status"
    return f"{url}{endpoint}"


def verify_cloud_fast_track(
    session: Any, server_url: str, *, password: str, timeout: int = 15,
) -> dict[str, Any]:
    """Verify the dedicated GCP endpoint once per base URL in this process."""
    url = server_url.rstrip("/")
    if url in _VERIFIED_CLOUD_FAST_TRACK_URLS:
        return {"ok": True, "cached": True}
    headers = {
        "Authorization": f"Bearer {password}",
        "X-LLM-Routing-Password": password,
        "X-API-Key": password,
    }
    response = session.get(
        model_status_url(url, cloud_fast_track=True),
        headers=headers,
        timeout=max(1, min(int(timeout), 30)),
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Cloud Fast Track 상태 응답이 JSON 객체가 아닙니다.")
    if data.get("configured") is False or data.get("ok") is False:
        raise ValueError(f"Cloud Fast Track을 사용할 수 없습니다: {data.get('error') or data}")
    _VERIFIED_CLOUD_FAST_TRACK_URLS.add(url)
    return data


def local_parallel_plan(
    *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None,
) -> LocalParallelPlan:
    """Calculate local OCR parallelism as 50 percent of available GPUs."""
    import requests

    from extract_picture_pages import (
        auth_headers,
        is_target_dispatch_eligible,
        load_server_config,
        target_available_count,
        target_status_metric,
    )

    config = load_server_config(config_path)
    password_env = str(config.get("password_env") or "READ_MACH_PASSWORD")
    secret = password or os.getenv(password_env)
    if not secret:
        raise ValueError(f"서버 비밀번호가 없습니다. {password_env} 환경변수를 입력하세요.")
    server_url, _route = resolve_model_server_url(config)
    timeout = max(1, min(int(config.get("timeout_seconds") or 240), 30))
    with requests.Session() as session:
        response = session.get(
            model_status_url(server_url),
            headers=auth_headers(secret),
            timeout=timeout,
        )
        response.raise_for_status()
        status = response.json()
    if not isinstance(status, dict):
        raise ValueError("서버 상태 응답이 JSON 객체가 아닙니다.")
    targets = status.get("targets")
    if not isinstance(targets, list):
        raise ValueError("서버 상태 응답에 targets 목록이 없습니다.")

    requested_model = str(config.get("model") or "").strip()
    explicit_target_id = str(config.get("target_id") or "").strip()
    eligible = [
        target
        for target in targets
        if isinstance(target, dict)
        and target.get("id")
        and str(target.get("api_type") or "").strip().lower() in {"ollama", "vllm"}
        and is_target_dispatch_eligible(status, target)
        and (not explicit_target_id or str(target.get("id")) == explicit_target_id)
    ]
    exact = [
        target for target in eligible
        if requested_model and str(target.get("model") or "").strip() == requested_model
    ]
    model_targets = exact or eligible
    if not model_targets:
        raise ValueError("이미지 입력을 전달할 수 있는 가용 Ollama/vLLM target이 없습니다.")

    gpu_targets: dict[str, dict[str, Any]] = {}
    for target in model_targets:
        metric = target_status_metric(status, target)
        host = str(target.get("host") or target.get("base_url") or "").strip()
        port = str(target.get("port") or "").strip()
        selected_gpu = str(
            target.get("selected_gpu")
            or target.get("selected_gpu_label")
            or metric.get("selected_gpu_device")
            or ""
        ).strip()
        endpoint = ":".join(part for part in (host, port) if part)
        gpu_key = f"{endpoint}|{selected_gpu}" if endpoint else str(target.get("id"))
        gpu_targets.setdefault(gpu_key, target)

    available_gpu_count = len(gpu_targets)
    available_model_count = sum(
        max(0, target_available_count(status, target) or 0)
        for target in model_targets
    )
    available_count = available_gpu_count
    max_workers = max(1, available_gpu_count // 2)
    return LocalParallelPlan(
        available_gpu_count=available_gpu_count,
        available_model_count=available_model_count,
        available_count=available_count,
        max_workers=max_workers,
        target_ids=tuple(str(target["id"]) for target in gpu_targets.values()),
    )


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
    cloud_fast_track: bool = False,
    cloud_fast_track_url: str | None = None,
    local_target_id: str | None = None,
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
    server_url, route = resolve_model_server_url(
        config,
        cloud_fast_track=cloud_fast_track,
        cloud_fast_track_url=cloud_fast_track_url,
    )
    timeout = int(config.get("timeout_seconds") or 240)
    requested_model = str(config.get("model") or "")
    explicit_target = local_target_id or str(config.get("target_id") or "") or None
    encoded = [(image_to_base64(image), image_mime_type(image)) for image in images]

    with requests.Session() as session:
        if cloud_fast_track:
            verify_cloud_fast_track(session, server_url, password=secret, timeout=timeout)
            target_id = None
            model = requested_model or "cloud-fast-track-default"
            api_type = "cloud-fast-track"
        else:
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
        }
        if target_id:
            payload["target_id"] = target_id
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
            model_generate_url(server_url, cloud_fast_track=cloud_fast_track),
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
        return text, {
            "ocr_engine": "vision-model", "ocr_model": model, "target_id": target_id,
            "route": route, "server_url": server_url,
        }


OCR_PROMPT = """너는 기술문서 OCR 전사기다. 첨부 이미지를 읽고 보이는 문자를 정확히 전사해라.
- 한국어와 영문 기술 용어를 원문 그대로 보존한다.
- 제목, 본문, 표, 목록, 코드, 수식의 읽기 순서를 유지한다.
- 표는 가능한 경우 Markdown 표로 변환한다.
- 보이지 않는 내용은 추측하거나 설명하지 않는다.
- 안내 문구와 코드 펜스 없이 추출된 본문만 출력한다.
"""
