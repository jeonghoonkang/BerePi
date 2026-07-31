#!/usr/bin/env python3
"""Save PDF pages that contain meaningful pictures, using a remote vision LLM."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import requests


APP_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = APP_DIR / "input"
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "server_config.json"
DEFAULT_SERVER_URL = "http://llm-server.example:4004"
DEFAULT_MODEL = "gemma4:31b"
SUPPORTED_SUFFIXES = {".pdf"}

LOGGER = logging.getLogger("read_mach")

CLASSIFICATION_PROMPT = """
이 문서 페이지 이미지를 분석하세요.

다음 중 하나라도 페이지에 있으면 has_picture=true 입니다.
- 사진, 삽화, 지도, 스크린샷
- 차트, 그래프, 다이어그램, 순서도
- 표가 아닌 시각적 도형이나 기술 도면

다음만 있으면 has_picture=false 입니다.
- 일반 본문 텍스트와 제목
- 단순 표, 페이지 번호, 머리말/꼬리말
- 작은 로고, 아이콘, 서명, 도장, 장식선, 배경 워터마크

반드시 설명이나 마크다운 없이 아래 JSON 한 줄만 응답하세요.
{"has_picture": true, "reason": "짧은 판정 이유"}
""".strip()


@dataclass(frozen=True)
class PageDecision:
    has_picture: bool
    reason: str
    raw_response: str


def load_server_config(config_path: Path) -> dict[str, Any]:
    path = config_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"서버 설정 파일이 없습니다: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"서버 설정 파일을 읽을 수 없습니다: {path} | {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"서버 설정은 JSON 객체여야 합니다: {path}")
    return data


def parse_args() -> argparse.Namespace:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    config_args, _ = config_parser.parse_known_args()
    config = load_server_config(config_args.config)
    password_env = str(config.get("password_env") or "READ_MACH_PASSWORD")

    parser = argparse.ArgumentParser(
        description="input의 PDF를 페이지별로 판독하여 그림이 있는 페이지를 PNG로 저장합니다."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_args.config,
        help=f"서버 JSON 설정 파일 (기본값: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--input-file",
        type=Path,
        help=(
            "input 디렉토리에서 처리할 PDF 한 개. 파일명 또는 input 내부 경로를 지정합니다. "
            "생략하면 input 디렉토리의 모든 PDF를 처리합니다."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--server-url",
        default=os.getenv("READ_MACH_SERVER_URL") or config.get("server_url") or DEFAULT_SERVER_URL,
        help=f"LLM Routing 서버 주소 (기본값: {DEFAULT_SERVER_URL})",
    )
    parser.add_argument(
        "--password",
        default=os.getenv(password_env),
        help=f"접근 비밀번호. 생략 시 {password_env} 환경변수를 사용합니다.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("READ_MACH_MODEL") or config.get("model") or DEFAULT_MODEL,
        help=f"요청할 모델명 (기본값: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--target-id",
        default=os.getenv("READ_MACH_TARGET_ID") or config.get("target_id") or None,
        help="LLM Routing target ID. 생략하면 이미지 전달이 가능한 Ollama 대상을 자동 선택합니다.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=144,
        help="페이지 렌더링 해상도 (기본값: 144 DPI)",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=82,
        help="모델 전송용 JPEG 품질 (기본값: 82)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(config.get("timeout_seconds") or 240),
        help="페이지당 모델 요청 제한 시간, 초 (기본값: 240)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="처리를 시작할 1 기준 페이지 번호",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="처리를 끝낼 1 기준 페이지 번호 (생략 시 마지막 페이지)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="이미 존재하는 결과 PNG도 다시 판정하고 덮어씁니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="모델 판정은 수행하되 결과 PNG는 저장하지 않습니다.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def auth_headers(password: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {password}",
        "X-LLM-Routing-Password": password,
        "X-API-Key": password,
    }


def response_text(data: dict[str, Any]) -> str:
    text = data.get("response") or data.get("output_text") or data.get("text")
    if text:
        return str(text)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        return str(choice.get("text") or message.get("content") or "")
    nested = data.get("data")
    if isinstance(nested, dict):
        return response_text(nested)
    return ""


def parse_decision(text: str) -> PageDecision:
    cleaned = text.strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    match = re.search(r"\{[\s\S]*\}", fenced)
    if not match:
        raise ValueError(f"모델 응답에서 JSON을 찾을 수 없습니다: {cleaned[:300]}")

    data = json.loads(match.group(0))
    value = data.get("has_picture")
    if not isinstance(value, bool):
        raise ValueError(f"has_picture가 boolean이 아닙니다: {cleaned[:300]}")
    return PageDecision(value, str(data.get("reason") or ""), cleaned)


def classify_page(
    session: requests.Session,
    *,
    server_url: str,
    password: str,
    model: str,
    target_id: str,
    api_type: str,
    jpeg_bytes: bytes,
    timeout: int,
) -> PageDecision:
    encoded_image = base64.b64encode(jpeg_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "client_id": "read-mach-picture-page-extractor",
        "model": model,
        "prompt": CLASSIFICATION_PROMPT,
        "stream": False,
        "temperature": 0,
        "timeout": timeout,
        "target_id": target_id,
    }
    if api_type == "vllm":
        payload["messages"] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CLASSIFICATION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                    },
                ],
            }
        ]
    else:
        payload["images"] = [encoded_image]
    response = session.post(
        f"{server_url.rstrip('/')}/api/generate",
        headers=auth_headers(password),
        json=payload,
        timeout=timeout + 30,
    )
    if not response.ok:
        detail = response.text.strip().replace("\n", " ")[:500]
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {detail or '응답 본문 없음'}",
            response=response,
        )
    text = response_text(response.json())
    if not text:
        raise ValueError("모델 응답에 판정 문자열이 없습니다.")
    return parse_decision(text)


def select_ollama_target(
    session: requests.Session,
    *,
    server_url: str,
    password: str,
    requested_model: str,
    explicit_target_id: str | None,
    excluded_target_ids: set[str] | None = None,
    timeout: int = 15,
) -> tuple[str, str, str]:
    response = session.get(
        f"{server_url.rstrip('/')}/api/status",
        headers=auth_headers(password),
        timeout=timeout,
    )
    response.raise_for_status()
    targets = response.json().get("targets")
    if not isinstance(targets, list):
        raise ValueError("서버 상태 응답에 targets 목록이 없습니다.")

    excluded = excluded_target_ids or set()

    def is_dispatch_eligible(target: dict[str, Any]) -> bool:
        try:
            available = int(target.get("available_targets"))
        except (TypeError, ValueError):
            return False
        return bool(target.get("dispatch_eligible")) and available > 0

    if explicit_target_id:
        matches = [target for target in targets if str(target.get("id")) == explicit_target_id]
        if not matches:
            raise ValueError(f"서버에서 target ID를 찾을 수 없습니다: {explicit_target_id}")
        target = matches[0]
        api_type = str(target.get("api_type") or "").strip().lower()
        if api_type not in {"ollama", "vllm"}:
            raise ValueError(
                f"선택한 target은 지원하지 않는 {target.get('api_type')} 형식입니다."
            )
        if not is_dispatch_eligible(target):
            raise ValueError(
                f"선택한 target을 현재 사용할 수 없습니다: {explicit_target_id} "
                f"(available_targets={target.get('available_targets')})"
            )
        return explicit_target_id, str(target.get("model") or requested_model), api_type

    vision_targets = [
        target
        for target in targets
        if str(target.get("api_type") or "").strip().lower() in {"ollama", "vllm"}
        and target.get("id")
        and str(target.get("id")) not in excluded
        and is_dispatch_eligible(target)
    ]
    if not vision_targets:
        raise ValueError("이미지 입력을 전달할 수 있는 가용 Ollama/vLLM target이 없습니다.")

    exact = [
        target
        for target in vision_targets
        if str(target.get("model") or "").strip() == requested_model
    ]
    target = (exact or vision_targets)[0]
    return (
        str(target["id"]),
        str(target.get("model") or requested_model),
        str(target.get("api_type") or "ollama").strip().lower(),
    )


def is_target_unavailable_error(exc: requests.RequestException) -> bool:
    response = getattr(exc, "response", None)
    body = str(getattr(response, "text", "") or "").casefold()
    return bool(
        response is not None
        and getattr(response, "status_code", 0) in {400, 409, 503}
        and "target" in body
        and ("not available" in body or "no eligible fallback" in body)
    )


def safe_stem(path: Path) -> str:
    # Windows에서 사용할 수 없는 문자만 치환하고 한글과 공백은 보존합니다.
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", path.stem).strip(" .")
    return stem or "document"


def render_page(page: fitz.Page, dpi: int, *, alpha: bool = False) -> fitz.Pixmap:
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    return page.get_pixmap(matrix=matrix, alpha=alpha, colorspace=fitz.csRGB)


def iter_pdf_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def select_pdf_files(input_dir: Path, input_file: Path | None) -> list[Path]:
    """Select one PDF inside input_dir, or all PDFs when no file is specified."""
    resolved_input_dir = input_dir.expanduser().resolve()
    if input_file is None:
        return iter_pdf_files(resolved_input_dir)

    requested = input_file.expanduser()
    if requested.is_absolute():
        selected = requested.resolve()
    else:
        direct_path = requested.resolve()
        selected = direct_path if direct_path.exists() else (resolved_input_dir / requested).resolve()

    try:
        selected.relative_to(resolved_input_dir)
    except ValueError as exc:
        raise ValueError(f"--input-file은 input 디렉토리 내부 파일이어야 합니다: {selected}") from exc
    if not selected.is_file():
        raise FileNotFoundError(f"선택한 입력 파일이 없습니다: {selected}")
    if selected.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"--input-file은 PDF 파일이어야 합니다: {selected}")
    return [selected]


def process_pdf(
    pdf_path: Path,
    *,
    output_dir: Path,
    session: requests.Session,
    args: argparse.Namespace,
) -> tuple[int, int, int]:
    saved = 0
    examined = 0
    failed_pages = 0
    with fitz.open(pdf_path) as document:
        first = max(1, args.start_page)
        last = min(document.page_count, args.end_page or document.page_count)
        if first > last:
            LOGGER.warning("%s: 처리할 페이지 범위가 없습니다.", pdf_path.name)
            return 0, 0, 0

        width = max(4, len(str(document.page_count)))
        LOGGER.info("%s: 총 %d페이지, %d~%d페이지 처리", pdf_path.name, document.page_count, first, last)

        for page_number in range(first, last + 1):
            output_path = output_dir / f"{safe_stem(pdf_path)}_page_{page_number:0{width}d}.png"
            if output_path.exists() and not args.overwrite:
                LOGGER.info("[%s %d/%d] 결과가 이미 있어 건너뜀", pdf_path.name, page_number, last)
                continue

            page = document.load_page(page_number - 1)
            pixmap = render_page(page, args.dpi)
            jpeg_bytes = pixmap.tobytes("jpeg", jpg_quality=args.jpeg_quality)
            examined += 1

            try:
                decision = classify_page(
                    session,
                    server_url=args.server_url,
                    password=args.password,
                    model=args.model,
                    target_id=args.target_id,
                    api_type=args.api_type,
                    jpeg_bytes=jpeg_bytes,
                    timeout=args.timeout,
                )
            except requests.RequestException as exc:
                if not is_target_unavailable_error(exc):
                    failed_pages += 1
                    LOGGER.error("[%s %d/%d] 모델 판정 실패: %s", pdf_path.name, page_number, last, exc)
                    continue
                failed_target_id = str(args.target_id)
                LOGGER.warning(
                    "[%s %d/%d] target %s 사용 불가; /api/status를 다시 확인합니다.",
                    pdf_path.name,
                    page_number,
                    last,
                    failed_target_id,
                )
                try:
                    args.target_id, args.model, args.api_type = select_ollama_target(
                        session,
                        server_url=args.server_url,
                        password=args.password,
                        requested_model=args.model,
                        explicit_target_id=None,
                        excluded_target_ids={failed_target_id},
                    )
                    LOGGER.info(
                        "[%s %d/%d] 다른 target으로 전환: %s (model=%s, api_type=%s)",
                        pdf_path.name,
                        page_number,
                        last,
                        args.target_id,
                        args.model,
                        args.api_type,
                    )
                    decision = classify_page(
                        session,
                        server_url=args.server_url,
                        password=args.password,
                        model=args.model,
                        target_id=args.target_id,
                        api_type=args.api_type,
                        jpeg_bytes=jpeg_bytes,
                        timeout=args.timeout,
                    )
                except (requests.RequestException, ValueError) as retry_exc:
                    failed_pages += 1
                    LOGGER.error(
                        "[%s %d/%d] 다른 가용 target 전환 실패: %s",
                        pdf_path.name,
                        page_number,
                        last,
                        retry_exc,
                    )
                    continue
            except ValueError as exc:
                failed_pages += 1
                LOGGER.error("[%s %d/%d] 모델 판정 실패: %s", pdf_path.name, page_number, last, exc)
                continue
            LOGGER.info(
                "[%s %d/%d] 그림=%s (%s)",
                pdf_path.name,
                page_number,
                last,
                decision.has_picture,
                decision.reason,
            )

            if decision.has_picture:
                saved += 1
                if not args.dry_run:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    # 판정용 JPEG가 아니라 무손실 PNG 페이지를 저장합니다.
                    output_path.write_bytes(pixmap.tobytes("png"))

    return examined, saved, failed_pages


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.password:
        LOGGER.error(
            "접근 비밀번호가 없습니다. READ_MACH_PASSWORD 환경변수 또는 --password를 지정하세요."
        )
        return 2
    if args.dpi < 72 or args.dpi > 600:
        LOGGER.error("--dpi는 72~600 범위여야 합니다.")
        return 2
    if not args.input_dir.is_dir():
        LOGGER.error("입력 디렉토리가 없습니다: %s", args.input_dir)
        return 2

    try:
        pdf_files = select_pdf_files(args.input_dir, args.input_file)
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("입력 PDF 선택 실패: %s", exc)
        return 2
    if not pdf_files:
        LOGGER.warning("입력 PDF가 없습니다: %s", args.input_dir)
        return 0

    LOGGER.info("입력 PDF %d개 발견", len(pdf_files))
    total_examined = 0
    total_saved = 0
    failures = 0

    with requests.Session() as session:
        try:
            args.target_id, selected_model, args.api_type = select_ollama_target(
                session,
                server_url=args.server_url,
                password=args.password,
                requested_model=args.model,
                explicit_target_id=args.target_id,
            )
            args.model = selected_model
            LOGGER.info(
                "모델 target 선택: %s (model=%s, api_type=%s)",
                args.target_id,
                args.model,
                args.api_type,
            )
        except (requests.RequestException, ValueError) as exc:
            LOGGER.error("이미지 처리 target 선택 실패: %s", exc)
            return 2

        for pdf_path in pdf_files:
            try:
                examined, saved, page_failures = process_pdf(
                    pdf_path,
                    output_dir=args.output_dir,
                    session=session,
                    args=args,
                )
                total_examined += examined
                total_saved += saved
                failures += page_failures
            except (fitz.FileDataError, requests.RequestException, ValueError) as exc:
                failures += 1
                LOGGER.error("%s 처리 실패: %s", pdf_path, exc)

    LOGGER.info(
        "완료: 판정 %d페이지, 그림 페이지 %d개, 실패 문서 %d개, 출력=%s",
        total_examined,
        total_saved,
        failures,
        args.output_dir,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
