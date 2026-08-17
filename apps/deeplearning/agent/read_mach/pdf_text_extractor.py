#!/usr/bin/env python3
"""Extract text from PDF text layers and use a vision model for sparse pages."""

from __future__ import annotations

import base64
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

ModelCall = Callable[..., str]
ProgressCallback = Callable[[str, str, str], None]
RendererLoader = Callable[[], Any]


def normalize_extracted_text(text: str) -> str:
    cleaned = str(text or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def merge_page_text(text_layer: str, ocr_text: str) -> str:
    if not text_layer:
        return ocr_text
    if not ocr_text:
        return text_layer
    merged_lines = [line for line in text_layer.splitlines() if line.strip()]
    known = {re.sub(r"\W+", "", line).casefold() for line in merged_lines}
    for line in ocr_text.splitlines():
        normalized = re.sub(r"\W+", "", line).casefold()
        if normalized and normalized not in known:
            merged_lines.append(line)
            known.add(normalized)
    return normalize_extracted_text("\n".join(merged_lines))


def load_pdf_renderer() -> Any:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PDF page image rendering requires pymupdf. "
            "Install Python dependencies with: py -3 -m pip install -r requirements.txt"
        ) from exc
    return fitz


def model_ocr_prompt(page_number: int, text_layer: str) -> str:
    existing = text_layer or "(텍스트 레이어 없음)"
    return f"""너는 기술문서 OCR 전사기다.
첨부된 PDF {page_number}페이지 이미지를 읽고 보이는 문자를 정확히 전사해라.

규칙:
- 한국어와 영문 기술 용어를 원문 그대로 보존한다.
- 제목, 본문, 표, 목록, 코드, 수식의 읽기 순서를 유지한다.
- 표는 가능한 경우 Markdown 표로 변환한다.
- 보이지 않는 내용은 추측하거나 설명하지 않는다.
- 안내 문구와 코드 펜스 없이 추출된 본문만 출력한다.
- 아래 기존 텍스트 레이어는 참고하되, 이미지에서 확인되는 누락 내용을 보완한다.

[기존 텍스트 레이어]
{existing}
"""


def extract_pdf_content(
    pdf_path: Path,
    *,
    config: dict[str, Any] | None = None,
    model_call: ModelCall | None = None,
    progress: ProgressCallback | None = None,
    renderer_loader: RendererLoader = load_pdf_renderer,
    ocr_dpi: int = 300,
    minimum_text_characters: int = 100,
    start_page: int = 1,
    end_page: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return page-labelled PDF text and extraction metadata.

    Pages with a sparse text layer are rendered as PNG and sent to ``model_call``.
    The callback boundary keeps this reader independent from any specific LLM router.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF text extraction requires pypdf. Install dependencies with: "
            "py -3 -m pip install -r requirements.txt"
        ) from exc

    source = Path(pdf_path).expanduser().resolve()
    reader = PdfReader(str(source))
    total_pdf_pages = len(reader.pages)
    first_page = max(1, int(start_page))
    last_page = min(total_pdf_pages, int(end_page) if end_page is not None else total_pdf_pages)
    if first_page > last_page:
        raise ValueError(
            f"처리할 페이지 범위가 없습니다: start={first_page}, end={last_page}, total={total_pdf_pages}"
        )
    selected_page_numbers = range(first_page, last_page + 1)
    page_texts: list[str] = []
    page_details: list[dict[str, Any]] = []
    ocr_page_indexes: list[int] = []
    selectable_text: dict[int, str] = {}
    extraction_warnings: list[str] = []

    selected_page_count = last_page - first_page + 1
    for current_page, page_number in enumerate(selected_page_numbers, 1):
        if progress:
            percentage = current_page * 100 / selected_page_count
            progress(
                "pdf-page-progress",
                f"[PDF 추출] 전체 {selected_page_count}페이지 | "
                f"현재 {current_page}/{selected_page_count}페이지 "
                f"(원본 {page_number}페이지) | 진행률 {percentage:.1f}%",
                "cyan",
            )
        page = reader.pages[page_number - 1]
        try:
            text = normalize_extracted_text(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            text = ""
            extraction_warnings.append(f"page {page_number}: text extraction failed: {exc}")
        selectable_text[page_number] = text
        if len(text) < minimum_text_characters:
            ocr_page_indexes.append(page_number - 1)

    ocr_results: dict[int, str] = {}
    ocr_warnings: list[str] = []
    if ocr_page_indexes:
        if config is None or model_call is None:
            raise RuntimeError(
                "PDF pages require model OCR, but no model configuration/callback was supplied."
            )
        fitz = renderer_loader()
        try:
            document = fitz.open(str(source))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Could not render PDF for OCR: {source} | {exc}") from exc
        try:
            scale = max(72, int(ocr_dpi)) / 72
            for page_index in ocr_page_indexes:
                page_number = page_index + 1
                if progress:
                    progress(
                        "tech-report-ocr",
                        f"sending page image to model for OCR page={page_number}/{len(reader.pages)} dpi={ocr_dpi}",
                        "cyan",
                    )
                page = document.load_page(page_index)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image_base64 = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                ocr_text = model_call(
                    config,
                    model_ocr_prompt(page_number, selectable_text.get(page_number, "")),
                    label=f"tech-report-ocr-page-{page_number}",
                    images=[image_base64],
                )
                normalized_ocr = normalize_extracted_text(ocr_text)
                if not normalized_ocr:
                    warning = f"page {page_number}: model OCR returned no text"
                    ocr_warnings.append(warning)
                    if progress:
                        progress("tech-report-ocr", warning, "yellow")
                ocr_results[page_number] = normalized_ocr
        finally:
            document.close()

    for page_number in selected_page_numbers:
        text_layer = selectable_text.get(page_number, "")
        ocr_text = ocr_results.get(page_number, "")
        if ocr_text and text_layer:
            text, method = merge_page_text(text_layer, ocr_text), "text+ocr"
        elif ocr_text:
            text, method = ocr_text, "ocr"
        else:
            text, method = text_layer, "text"
        if text:
            page_texts.append(f"[PDF page {page_number} | extraction={method}]\n{text}")
        page_details.append(
            {
                "page": page_number,
                "method": method if text else "empty",
                "characters": len(text),
                "text_layer_characters": len(text_layer),
                "ocr_characters": len(ocr_text),
            }
        )

    extracted = "\n\n".join(page_texts).strip()
    if not extracted:
        raise ValueError(f"No readable text was found in {source}. OCR also returned no text.")
    metadata = {
        "source_pdf": str(source),
        "page_count": len(page_details),
        "total_pdf_pages": total_pdf_pages,
        "start_page": first_page,
        "end_page": last_page,
        "total_characters": len(extracted),
        "text_pages": sum(1 for item in page_details if item["method"] in {"text", "text+ocr"}),
        "ocr_pages": sum(1 for item in page_details if item["method"] in {"ocr", "text+ocr"}),
        "empty_pages": sum(1 for item in page_details if item["method"] == "empty"),
        "ocr_engine": "vision-model",
        "ocr_model": str((config or {}).get("model") or "server-default"),
        "ocr_dpi": int(ocr_dpi),
        "ocr_warnings": ocr_warnings,
        "extraction_warnings": extraction_warnings,
        "pages": page_details,
    }
    return extracted, metadata


def parse_cli_args() -> argparse.Namespace:
    from extract_picture_pages import DEFAULT_CONFIG_PATH

    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    pre_args, _ = pre_parser.parse_known_args()

    parser = argparse.ArgumentParser(
        description="PDF의 선택 페이지에서 문자와 문장을 추출하여 텍스트로 저장합니다."
    )
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=pre_args.config)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--ocr-dpi", type=int, default=300)
    parser.add_argument("--minimum-text-characters", type=int, default=100)
    parser.add_argument("--password", default=None)
    parser.add_argument(
        "--cloud-fast-track", action="store_true",
        help="server_url 대신 Cloud Fast Track 주소를 사용합니다.",
    )
    parser.add_argument("--cloud-fast-track-url")
    return parser.parse_args()


def cli_main() -> int:
    import requests

    from extract_picture_pages import (
        auth_headers,
        is_target_unavailable_error,
        load_server_config,
        response_text,
        select_ollama_target,
        select_pdf_files,
    )
    from vision_ocr_support import (
        model_generate_url,
        resolve_model_server_url,
        verify_cloud_fast_track,
    )

    args = parse_cli_args()
    try:
        server_config = load_server_config(args.config)
        password_env = str(server_config.get("password_env") or "READ_MACH_PASSWORD")
        password = args.password or os.getenv(password_env)
        if not password:
            raise ValueError(f"서버 비밀번호가 없습니다. {password_env} 환경변수를 입력하세요.")
        input_dir = Path(__file__).resolve().parent / "input"
        pdf_path = select_pdf_files(input_dir, args.input_file)[0]
        server_url, route = resolve_model_server_url(
            server_config,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
        )
        print(f"모델 호출 경로: {route} ({server_url})", flush=True)
        requested_model = str(server_config.get("model") or "")
        explicit_target = str(server_config.get("target_id") or "") or None
        timeout = int(server_config.get("timeout_seconds") or 240)

        with requests.Session() as session:
            if args.cloud_fast_track:
                verify_cloud_fast_track(
                    session, server_url, password=password, timeout=timeout
                )
                target_id = None
                model = requested_model or "cloud-fast-track-default"
                api_type = "cloud-fast-track"
                print(f"Cloud Fast Track 직접 호출: {server_url}", flush=True)
            else:
                target_id, model, api_type = select_ollama_target(
                    session,
                    server_url=server_url,
                    password=password,
                    requested_model=requested_model,
                    explicit_target_id=explicit_target,
                )
                print(f"모델 target 선택: {target_id} (model={model}, api_type={api_type})")

            def call_vision_model(
                _config: dict[str, Any],
                prompt: str,
                *,
                label: str,
                images: list[str],
            ) -> str:
                nonlocal target_id, model, api_type

                def send_request() -> Any:
                    response = session.post(
                        model_generate_url(
                            server_url, cloud_fast_track=args.cloud_fast_track
                        ),
                        headers=auth_headers(password),
                        json=payload,
                        timeout=timeout + 30,
                    )
                    if not response.ok:
                        detail = response.text.strip().replace("\n", " ")[:500]
                        raise requests.HTTPError(
                            f"{label}: {response.status_code} {response.reason}: {detail}",
                            response=response,
                        )
                    return response

                payload: dict[str, Any] = {
                    "client_id": "read-mach-pdf-text-extractor",
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0,
                    "timeout": timeout,
                }
                if target_id:
                    payload["target_id"] = target_id
                if api_type == "vllm":
                    payload["messages"] = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                *[
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{image}"},
                                    }
                                    for image in images
                                ],
                            ],
                        }
                    ]
                else:
                    payload["images"] = images
                try:
                    response = send_request()
                except requests.RequestException as exc:
                    if args.cloud_fast_track or not is_target_unavailable_error(exc):
                        raise
                    failed_target = target_id
                    target_id, model, api_type = select_ollama_target(
                        session,
                        server_url=server_url,
                        password=password,
                        requested_model=model,
                        explicit_target_id=None,
                        excluded_target_ids={failed_target},
                    )
                    print(
                        f"target 전환: {failed_target} -> {target_id} "
                        f"(model={model}, api_type={api_type})",
                        flush=True,
                    )
                    payload["target_id"] = target_id
                    payload["model"] = model
                    if api_type == "vllm" and "messages" not in payload:
                        payload.pop("images", None)
                        payload["messages"] = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    *[
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}}
                                        for image in images
                                    ],
                                ],
                            }
                        ]
                    elif api_type == "ollama" and "images" not in payload:
                        payload.pop("messages", None)
                        payload["images"] = images
                    response = send_request()
                text = response_text(response.json()).strip()
                if not text:
                    raise ValueError(f"{label}: 모델 OCR 응답이 비어 있습니다.")
                return text

            def progress(_label: str, message: str, _color: str) -> None:
                print(message, flush=True)

            extraction_config = {
                "model": model, "target_id": target_id, "api_type": api_type,
                "route": route, "server_url": server_url,
            }
            text, metadata = extract_pdf_content(
                pdf_path,
                config=extraction_config,
                model_call=call_vision_model,
                progress=progress,
                ocr_dpi=args.ocr_dpi,
                minimum_text_characters=args.minimum_text_characters,
                start_page=args.start_page,
                end_page=args.end_page,
            )

        args.output_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"pages_{metadata['start_page']}-{metadata['end_page']}"
        text_path = args.output_dir / f"{pdf_path.stem}_{suffix}_extracted.txt"
        metadata_path = args.output_dir / f"{pdf_path.stem}_{suffix}_extraction.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"PDF 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
