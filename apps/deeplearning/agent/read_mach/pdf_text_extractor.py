#!/usr/bin/env python3
"""Extract text from PDF text layers and use a vision model for sparse pages."""

from __future__ import annotations

import base64
import re
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
    page_texts: list[str] = []
    page_details: list[dict[str, Any]] = []
    ocr_page_indexes: list[int] = []
    selectable_text: dict[int, str] = {}
    extraction_warnings: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
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

    for page_number in range(1, len(reader.pages) + 1):
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
        "page_count": len(reader.pages),
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
