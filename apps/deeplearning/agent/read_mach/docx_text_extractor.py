#!/usr/bin/env python3
"""Extract text and OCR embedded raster images from a DOCX document."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pdf_text_extractor import normalize_extracted_text
from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    OCR_PROMPT,
    call_vision_ocr,
    select_input_file,
)

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png"}


def extract_docx_package(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    """Read visible document.xml text and supported images without Microsoft Word."""
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            blocks: list[str] = []
            for paragraph in root.iter(f"{{{WORD_NS}}}p"):
                value = "".join(node.text or "" for node in paragraph.iter(f"{{{WORD_NS}}}t")).strip()
                if value:
                    blocks.append(value)
            images = [
                (name, archive.read(name))
                for name in archive.namelist()
                if name.startswith("word/media/") and Path(name).suffix.casefold() in RASTER_SUFFIXES
            ]
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"올바른 DOCX 문서가 아닙니다: {path} | {exc}") from exc
    return normalize_extracted_text("\n\n".join(blocks)), images


def extract_docx_content(
    path: Path, *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None,
    cloud_fast_track: bool = False, cloud_fast_track_url: str | None = None,
) -> tuple[str, dict[str, object]]:
    text, images = extract_docx_package(path)
    ocr_blocks: list[str] = []
    model_metadata: dict[str, object] = {"ocr_engine": "not-used", "ocr_model": None}
    for index, (name, data) in enumerate(images, 1):
        result, model_metadata = call_vision_ocr(
            [data], f"{OCR_PROMPT}\nDOCX 포함 그림 {index}({name})를 전사한다.",
            config_path=config_path, password=password, client_id="read-mach-docx-text-extractor",
            cloud_fast_track=cloud_fast_track, cloud_fast_track_url=cloud_fast_track_url,
        )
        if result.strip():
            ocr_blocks.append(f"[DOCX embedded image {index}: {name}]\n{result.strip()}")
    combined = "\n\n".join(part for part in [text, *ocr_blocks] if part).strip()
    if not combined:
        raise ValueError(f"DOCX에서 읽을 수 있는 문자나 지원되는 그림을 찾지 못했습니다: {path}")
    metadata: dict[str, object] = {
        "source_docx": str(path.resolve()), "format": "docx", "characters": len(combined),
        "document_text_characters": len(text), "embedded_images": len(images),
        "ocr_images": len(ocr_blocks), **model_metadata,
    }
    return combined, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="DOCX 문서의 본문과 포함 그림 문자를 추출합니다.")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password")
    parser.add_argument("--cloud-fast-track", action="store_true")
    parser.add_argument("--cloud-fast-track-url")
    args = parser.parse_args()
    try:
        source = select_input_file(args.input_file, ".docx")
        text, metadata = extract_docx_content(
            source, config_path=args.config, password=args.password,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        text_path = args.output_dir / f"{source.stem}_docx_extracted.txt"
        metadata_path = args.output_dir / f"{source.stem}_docx_extraction.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"DOCX 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
