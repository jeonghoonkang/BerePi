#!/usr/bin/env python3
"""Extract text and OCR embedded raster images from an HWPX document."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pdf_text_extractor import normalize_extracted_text
from extracted_image_output import output_extracted_images
from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    OCR_PROMPT,
    call_vision_ocr,
    select_input_file,
)

RASTER_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _section_number(name: str) -> tuple[int, str]:
    match = re.search(r"section(\d+)\.xml$", name, flags=re.IGNORECASE)
    return (int(match.group(1)) if match else 10**9, name)


def extract_hwpx_package(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    """Read HWPX section text and raster BinData entries using the standard library."""
    try:
        with zipfile.ZipFile(path) as archive:
            section_names = sorted(
                (name for name in archive.namelist() if re.search(r"(^|/)section\d+\.xml$", name, re.I)),
                key=_section_number,
            )
            if not section_names:
                raise ValueError("Contents/section*.xml 항목이 없습니다.")
            blocks: list[str] = []
            for section_name in section_names:
                root = ET.fromstring(archive.read(section_name))
                for node in root.iter():
                    if node.tag.rsplit("}", 1)[-1] == "t" and node.text:
                        value = node.text.strip()
                        if value:
                            blocks.append(value)
            images = [
                (name, archive.read(name))
                for name in archive.namelist()
                if name.casefold().startswith("bindata/") and Path(name).suffix.casefold() in RASTER_SUFFIXES
            ]
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"올바른 HWPX 문서가 아닙니다: {path} | {exc}") from exc
    return normalize_extracted_text("\n".join(blocks)), images


def extract_hwpx_content(
    path: Path, *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None,
    cloud_fast_track: bool = False, cloud_fast_track_url: str | None = None,
    output_dir: Path | None = None, rm_image: bool = False,
) -> tuple[str, dict[str, object]]:
    text, images = extract_hwpx_package(path)
    image_output_metadata: dict[str, object] = {}
    if output_dir is not None:
        image_output_metadata = output_extracted_images(
            images, source_path=path, output_dir=output_dir, rm_image=rm_image
        ).metadata()
    ocr_blocks: list[str] = []
    model_metadata: dict[str, object] = {"ocr_engine": "not-used", "ocr_model": None}
    for index, (name, data) in enumerate(images, 1):
        result, model_metadata = call_vision_ocr(
            [data], f"{OCR_PROMPT}\nHWPX 포함 그림 {index}({name})를 전사한다.",
            config_path=config_path, password=password, client_id="read-mach-hwpx-text-extractor",
            cloud_fast_track=cloud_fast_track, cloud_fast_track_url=cloud_fast_track_url,
        )
        if result.strip():
            ocr_blocks.append(f"[HWPX embedded image {index}: {name}]\n{result.strip()}")
    combined = "\n\n".join(part for part in [text, *ocr_blocks] if part).strip()
    if not combined:
        raise ValueError(f"HWPX에서 읽을 수 있는 문자나 지원되는 그림을 찾지 못했습니다: {path}")
    metadata: dict[str, object] = {
        "source_hwpx": str(path.resolve()), "format": "hwpx", "characters": len(combined),
        "document_text_characters": len(text), "embedded_images": len(images),
        "ocr_images": len(ocr_blocks), **model_metadata, **image_output_metadata,
    }
    return combined, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="HWPX 문서의 본문과 포함 그림 문자를 추출합니다.")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password")
    parser.add_argument(
        "--rm-image", action="store_true",
        help="추출 이미지를 OCR에 사용한 뒤 output/extract_image에 남기지 않습니다.",
    )
    parser.add_argument("--cloud-fast-track", action="store_true")
    parser.add_argument("--cloud-fast-track-url")
    args = parser.parse_args()
    try:
        source = select_input_file(args.input_file, ".hwpx")
        text, metadata = extract_hwpx_content(
            source, config_path=args.config, password=args.password,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
            output_dir=args.output_dir, rm_image=args.rm_image,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        text_path = args.output_dir / f"{source.stem}_hwpx_extracted.txt"
        metadata_path = args.output_dir / f"{source.stem}_hwpx_extraction.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if metadata.get("extracted_images_removed"):
            print(f"추출 그림 삭제: {metadata['extracted_image_directory']}")
        elif metadata.get("extracted_image_file_count"):
            print(f"추출 그림 저장: {metadata['extracted_image_directory']}")
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"HWPX 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
