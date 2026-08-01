#!/usr/bin/env python3
"""Common implementation used by the JPG and PNG command-line extractors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    OCR_PROMPT,
    call_vision_ocr,
    image_mime_type,
    select_input_file,
)


def extract_image_text(
    image_path: Path, *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None
) -> tuple[str, dict[str, object]]:
    data = image_path.read_bytes()
    image_mime_type(data)
    text, model_metadata = call_vision_ocr([data], OCR_PROMPT, config_path=config_path, password=password)
    metadata: dict[str, object] = {
        "source_image": str(image_path.resolve()),
        "format": image_path.suffix.lstrip(".").lower(),
        "bytes": len(data),
        "characters": len(text),
        **model_metadata,
    }
    return text, metadata


def run_image_cli(suffix: str, description: str) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password")
    args = parser.parse_args()
    try:
        source = select_input_file(args.input_file, suffix)
        text, metadata = extract_image_text(source, config_path=args.config, password=args.password)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{source.stem}_{suffix.lstrip('.').lower()}_extracted"
        text_path = args.output_dir / f"{stem}.txt"
        metadata_path = args.output_dir / f"{stem}.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must turn dependency/network errors into a clean exit
        print(f"{suffix.upper()} 문자 추출 실패: {exc}", file=sys.stderr)
        return 2
