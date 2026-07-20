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
DEFAULT_SERVER_URL = "http://keties.iptime.org:4004"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="input의 PDF를 페이지별로 판독하여 그림이 있는 페이지를 PNG로 저장합니다."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--server-url",
        default=os.getenv("READ_MACH_SERVER_URL", DEFAULT_SERVER_URL),
        help=f"LLM Routing 서버 주소 (기본값: {DEFAULT_SERVER_URL})",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("READ_MACH_PASSWORD"),
        help="접근 비밀번호. 생략 시 READ_MACH_PASSWORD 환경변수를 사용합니다.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("READ_MACH_MODEL", DEFAULT_MODEL),
        help=f"요청할 모델명 (기본값: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--target-id",
        default=os.getenv("READ_MACH_TARGET_ID"),
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
        default=240,
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
    jpeg_bytes: bytes,
    timeout: int,
) -> PageDecision:
    payload = {
        "client_id": "read-mach-picture-page-extractor",
        "model": model,
        "prompt": CLASSIFICATION_PROMPT,
        "images": [base64.b64encode(jpeg_bytes).decode("ascii")],
        "stream": False,
        "temperature": 0,
        "timeout": timeout,
        "target_id": target_id,
    }
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
    timeout: int = 15,
) -> tuple[str, str]:
    response = session.get(
        f"{server_url.rstrip('/')}/api/status",
        headers=auth_headers(password),
        timeout=timeout,
    )
    response.raise_for_status()
    targets = response.json().get("targets")
    if not isinstance(targets, list):
        raise ValueError("서버 상태 응답에 targets 목록이 없습니다.")

    if explicit_target_id:
        matches = [target for target in targets if str(target.get("id")) == explicit_target_id]
        if not matches:
            raise ValueError(f"서버에서 target ID를 찾을 수 없습니다: {explicit_target_id}")
        target = matches[0]
        if str(target.get("api_type") or "").lower() != "ollama":
            raise ValueError(
                f"선택한 target은 이미지 배열을 전달하지 않는 {target.get('api_type')} 형식입니다."
            )
        return explicit_target_id, str(target.get("model") or requested_model)

    ollama_targets = [
        target
        for target in targets
        if str(target.get("api_type") or "").strip().lower() == "ollama"
        and target.get("id")
    ]
    if not ollama_targets:
        raise ValueError("이미지 입력을 전달할 수 있는 Ollama target이 없습니다.")

    exact = [
        target
        for target in ollama_targets
        if str(target.get("model") or "").strip() == requested_model
    ]
    target = (exact or ollama_targets)[0]
    return str(target["id"]), str(target.get("model") or requested_model)


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
                    jpeg_bytes=jpeg_bytes,
                    timeout=args.timeout,
                )
            except (requests.RequestException, ValueError) as exc:
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

    pdf_files = iter_pdf_files(args.input_dir)
    if not pdf_files:
        LOGGER.warning("입력 PDF가 없습니다: %s", args.input_dir)
        return 0

    LOGGER.info("입력 PDF %d개 발견", len(pdf_files))
    total_examined = 0
    total_saved = 0
    failures = 0

    with requests.Session() as session:
        try:
            args.target_id, selected_model = select_ollama_target(
                session,
                server_url=args.server_url,
                password=args.password,
                requested_model=args.model,
                explicit_target_id=args.target_id,
            )
            args.model = selected_model
            LOGGER.info("Ollama target 선택: %s (model=%s)", args.target_id, args.model)
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
