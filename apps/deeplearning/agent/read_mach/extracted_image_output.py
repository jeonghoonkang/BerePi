"""Persist embedded document images below an extractor output directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ExtractedImageOutput:
    directory: Path
    files: tuple[Path, ...]
    image_count: int
    removed: bool

    def metadata(self) -> dict[str, object]:
        return {
            "extracted_image_directory": str(self.directory),
            "extracted_image_count": self.image_count,
            "extracted_image_files": [str(path) for path in self.files],
            "extracted_image_file_count": len(self.files),
            "extracted_images_removed": self.removed,
        }


def _safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" ._")
    return cleaned or fallback


def _clear_image_directory(image_directory: Path) -> bool:
    existed = image_directory.exists() or image_directory.is_symlink()
    if image_directory.is_symlink():
        raise ValueError(f"추출 이미지 디렉토리가 심볼릭 링크입니다: {image_directory}")
    if image_directory.exists() and not image_directory.is_dir():
        raise ValueError(f"추출 이미지 경로가 디렉토리가 아닙니다: {image_directory}")
    if image_directory.is_dir():
        for existing in sorted(image_directory.rglob("*"), reverse=True):
            if existing.is_file() or existing.is_symlink():
                existing.unlink()
            elif existing.is_dir():
                existing.rmdir()
        image_directory.rmdir()
    return existed


def output_extracted_images(
    images: Sequence[tuple[str, bytes]],
    *,
    source_path: Path,
    output_dir: Path,
    rm_image: bool = False,
) -> ExtractedImageOutput:
    """Write images under extract_image, or leave none behind when rm_image is set."""
    source = Path(source_path)
    document_name = _safe_name(
        f"{source.stem}_{source.suffix.lstrip('.').casefold()}", "document"
    )
    image_directory = Path(output_dir).expanduser().resolve() / "extract_image" / document_name
    if rm_image:
        had_saved_directory = _clear_image_directory(image_directory)
        return ExtractedImageOutput(
            directory=image_directory,
            files=(),
            image_count=len(images),
            removed=bool(images or had_saved_directory),
        )
    if not images:
        return ExtractedImageOutput(
            directory=image_directory,
            files=(),
            image_count=0,
            removed=False,
        )

    _clear_image_directory(image_directory)
    image_directory.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, (archive_name, data) in enumerate(images, 1):
        original_name = _safe_name(Path(archive_name).name, f"image_{index}")
        destination = image_directory / f"{index:04d}_{original_name}"
        destination.write_bytes(data)
        saved.append(destination)
    return ExtractedImageOutput(
        directory=image_directory,
        files=tuple(saved),
        image_count=len(images),
        removed=False,
    )
