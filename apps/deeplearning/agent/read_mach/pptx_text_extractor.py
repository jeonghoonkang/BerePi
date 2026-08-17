#!/usr/bin/env python3
"""Extract visible slide text and OCR embedded raster images from a PPTX file."""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
import zipfile
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

from pdf_text_extractor import normalize_extracted_text
from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    OCR_PROMPT,
    call_vision_ocr,
    select_input_file,
)

DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png"}
ProgressCallback = Callable[[str, str, str], None]


def _slide_names(archive: zipfile.ZipFile) -> list[str]:
    """Return slide part names in the order defined by presentation.xml."""
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {
        relationship.attrib["Id"]: relationship.attrib.get("Target", "")
        for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    }

    names: list[str] = []
    slide_list = presentation.find(f"{{{PRESENTATION_NS}}}sldIdLst")
    if slide_list is None:
        return names
    for slide_id in slide_list.findall(f"{{{PRESENTATION_NS}}}sldId"):
        relationship_id = slide_id.attrib.get(f"{{{OFFICE_REL_NS}}}id")
        target = targets.get(relationship_id or "")
        if target:
            names.append(posixpath.normpath(posixpath.join("ppt", target)))
    return names


def _extract_pptx_package(
    path: Path, *, progress: ProgressCallback | None = None,
    image_ocr_planned: bool = False,
) -> tuple[str, list[tuple[str, bytes]], int]:
    """Read visible slide text and raster media using only the standard library."""
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = _slide_names(archive)
            if not slide_names:
                raise ValueError("슬라이드 항목이 없습니다.")

            images = [
                (name, archive.read(name))
                for name in archive.namelist()
                if name.casefold().startswith("ppt/media/")
                and Path(name).suffix.casefold() in RASTER_SUFFIXES
            ]
            slides: list[str] = []
            total_pages = len(slide_names)
            total_work = total_pages + (len(images) if image_ocr_planned else 0)
            for current_page, slide_name in enumerate(slide_names, 1):
                root = ET.fromstring(archive.read(slide_name))
                paragraphs: list[str] = []
                for paragraph in root.iter(f"{{{DRAWING_NS}}}p"):
                    value = "".join(
                        node.text or "" for node in paragraph.iter(f"{{{DRAWING_NS}}}t")
                    ).strip()
                    if value:
                        paragraphs.append(value)
                if paragraphs:
                    slides.append("\n".join(paragraphs))
                if progress:
                    stage_percentage = current_page * 100 / total_pages
                    overall_percentage = current_page * 100 / total_work
                    stage_label = (
                        "PPTX 1/2: 슬라이드 문자"
                        if image_ocr_planned
                        else "PPTX 슬라이드 문자"
                    )
                    progress(
                        "pptx-page-progress",
                        f"[{stage_label}] 전체 {total_pages}페이지 | "
                        f"현재 {current_page}/{total_pages}페이지 | "
                        f"단계 {stage_percentage:.1f}% | 전체 {overall_percentage:.1f}%",
                        "cyan",
                    )

    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"올바른 PPTX 문서가 아닙니다: {path} | {exc}") from exc
    return normalize_extracted_text("\n\n".join(slides)), images, total_pages


def extract_pptx_package(
    path: Path, *, progress: ProgressCallback | None = None
) -> tuple[str, list[tuple[str, bytes]]]:
    """Read a PPTX package while preserving the existing two-value public API."""
    text, images, _page_count = _extract_pptx_package(path, progress=progress)
    return text, images


def extract_pptx_content(
    path: Path, *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None,
    progress: ProgressCallback | None = None, ocr_embedded_images: bool = True,
    cloud_fast_track: bool = False, cloud_fast_track_url: str | None = None,
) -> tuple[str, dict[str, object]]:
    text, images, page_count = _extract_pptx_package(
        path, progress=progress, image_ocr_planned=ocr_embedded_images
    )
    ocr_blocks: list[str] = []
    model_metadata: dict[str, object] = {"ocr_engine": "not-used", "ocr_model": None}
    ocr_images = images if ocr_embedded_images else []
    total_work = page_count + len(ocr_images)
    for index, (name, data) in enumerate(ocr_images, 1):
        if progress:
            completed_images = index - 1
            stage_percentage = completed_images * 100 / len(ocr_images)
            overall_percentage = (page_count + completed_images) * 100 / total_work
            progress(
                "pptx-image-ocr-progress",
                f"[PPTX 2/2: 이미지 OCR] 전체 {len(ocr_images)}개 | "
                f"현재 {index}/{len(ocr_images)}개 ({name}) | "
                f"완료 {stage_percentage:.1f}% | 전체 {overall_percentage:.1f}%",
                "cyan",
            )
        result, model_metadata = call_vision_ocr(
            [data], f"{OCR_PROMPT}\nPPTX 포함 그림 {index}({name})를 전사한다.",
            config_path=config_path, password=password,
            client_id="read-mach-pptx-text-extractor",
            cloud_fast_track=cloud_fast_track,
            cloud_fast_track_url=cloud_fast_track_url,
        )
        if result.strip():
            ocr_blocks.append(f"[PPTX embedded image {index}: {name}]\n{result.strip()}")

    if progress:
        progress(
            "pptx-complete",
            f"[PPTX 추출 완료] 슬라이드 {page_count}페이지 | "
            f"이미지 OCR {len(ocr_images)}개 | 전체 100.0%",
            "green",
        )

    combined = "\n\n".join(part for part in [text, *ocr_blocks] if part).strip()
    if not combined:
        raise ValueError(f"PPTX에서 읽을 수 있는 문자나 지원되는 그림을 찾지 못했습니다: {path}")
    metadata: dict[str, object] = {
        "source_pptx": str(path.resolve()), "format": "pptx", "characters": len(combined),
        "page_count": page_count, "document_text_characters": len(text),
        "embedded_images": len(images), "embedded_image_ocr_skipped": not ocr_embedded_images,
        "ocr_images": len(ocr_blocks), **model_metadata,
    }
    return combined, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="PPTX 슬라이드와 포함 그림의 문자를 추출합니다.")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password")
    parser.add_argument(
        "--cloud-fast-track", action="store_true",
        help="server_url 대신 Cloud Fast Track 주소를 사용합니다.",
    )
    parser.add_argument(
        "--cloud-fast-track-url",
        help="설정 파일의 cloud_fast_track_url을 이번 실행에서 덮어씁니다.",
    )
    parser.add_argument(
        "--skip-embedded-image-ocr",
        action="store_true",
        help="슬라이드 XML 문자만 추출하고 포함 이미지 OCR은 건너뜁니다.",
    )
    args = parser.parse_args()
    try:
        source = select_input_file(args.input_file, ".pptx")

        def print_progress(_label: str, message: str, _color: str) -> None:
            print(message, flush=True)

        text, metadata = extract_pptx_content(
            source, config_path=args.config, password=args.password, progress=print_progress,
            ocr_embedded_images=not args.skip_embedded_image_ocr,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        text_path = args.output_dir / f"{source.stem}_pptx_extracted.txt"
        metadata_path = args.output_dir / f"{source.stem}_pptx_extraction.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"PPTX 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
