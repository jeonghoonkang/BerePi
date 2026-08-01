#!/usr/bin/env python3
"""Dispatch supported input files to the format-specific text extractors."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from vision_ocr_support import DEFAULT_CONFIG_PATH, DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR


EXTRACTORS = {
    ".pdf": "pdf_text_extractor.py",
    ".docx": "docx_text_extractor.py",
    ".hwpx": "hwpx_text_extractor.py",
    ".jpg": "jpg_text_extractor.py",
    ".png": "png_text_extractor.py",
}


def discover_input_files(input_dir: Path) -> list[Path]:
    """Return all supported files below input_dir in deterministic path order."""
    root = input_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"입력 디렉토리가 없습니다: {root}")
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in EXTRACTORS),
        key=lambda path: str(path).casefold(),
    )


def resolve_requested_files(input_dir: Path, requested_files: list[Path]) -> list[Path]:
    """Resolve explicit files while keeping all access inside input_dir."""
    root = input_dir.expanduser().resolve()
    files: list[Path] = []
    for requested in requested_files:
        candidate = requested.expanduser().resolve()
        selected = candidate if candidate.exists() else (root / requested).resolve()
        try:
            selected.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"--input-file은 input 디렉토리 내부 파일이어야 합니다: {selected}") from exc
        if not selected.is_file():
            raise FileNotFoundError(f"선택한 입력 파일이 없습니다: {selected}")
        if selected.suffix.casefold() not in EXTRACTORS:
            supported = ", ".join(sorted(EXTRACTORS))
            raise ValueError(f"지원하지 않는 입력 형식입니다: {selected.suffix} (지원: {supported})")
        files.append(selected)
    return files


def extractor_command(
    source: Path,
    *,
    config_path: Path,
    output_dir: Path,
    start_page: int,
    end_page: int | None,
    ocr_dpi: int,
    minimum_text_characters: int,
) -> list[str]:
    """Build the format-specific extractor command for one source file."""
    suffix = source.suffix.casefold()
    script = Path(__file__).resolve().parent / EXTRACTORS[suffix]
    command = [
        sys.executable,
        str(script),
        "--input-file",
        str(source),
        "--config",
        str(config_path),
        "--output-dir",
        str(output_dir),
    ]
    if suffix == ".pdf":
        command.extend(["--start-page", str(start_page), "--ocr-dpi", str(ocr_dpi)])
        command.extend(["--minimum-text-characters", str(minimum_text_characters)])
        if end_page is not None:
            command.extend(["--end-page", str(end_page)])
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="입력 파일 확장자에 맞는 추출기를 선택하여 문자를 순차 추출합니다."
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        action="append",
        default=[],
        help="처리할 input 내부 파일. 여러 번 지정 가능하며, 생략하면 지원 파일 전체를 처리합니다.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-page", type=int, default=1, help="PDF에만 적용")
    parser.add_argument("--end-page", type=int, help="PDF에만 적용")
    parser.add_argument("--ocr-dpi", type=int, default=300, help="PDF에만 적용")
    parser.add_argument("--minimum-text-characters", type=int, default=100, help="PDF에만 적용")
    parser.add_argument("--fail-fast", action="store_true", help="첫 실패에서 처리를 중단")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sources = (
            resolve_requested_files(DEFAULT_INPUT_DIR, args.input_file)
            if args.input_file
            else discover_input_files(DEFAULT_INPUT_DIR)
        )
    except (OSError, ValueError) as exc:
        print(f"입력 파일 선택 실패: {exc}", file=sys.stderr)
        return 2

    if not sources:
        print(f"지원되는 입력 파일이 없습니다: {DEFAULT_INPUT_DIR}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[tuple[Path, int]] = []
    total = len(sources)
    for index, source in enumerate(sources, 1):
        extractor = EXTRACTORS[source.suffix.casefold()]
        print(f"[{index}/{total}] {source.name} -> {extractor}", flush=True)
        command = extractor_command(
            source,
            config_path=args.config,
            output_dir=args.output_dir,
            start_page=max(1, args.start_page),
            end_page=args.end_page,
            ocr_dpi=max(72, args.ocr_dpi),
            minimum_text_characters=max(0, args.minimum_text_characters),
        )
        result = subprocess.run(command, check=False)
        if result.returncode:
            failures.append((source, result.returncode))
            print(f"[{index}/{total}] 실패(exit={result.returncode}): {source}", file=sys.stderr)
            if args.fail_fast:
                break
        else:
            print(f"[{index}/{total}] 완료: {source.name}", flush=True)

    completed = total - len(failures) if not args.fail_fast else index - len(failures)
    print(f"처리 요약: 성공 {completed}, 실패 {len(failures)}, 대상 {total}")
    if failures:
        for source, returncode in failures:
            print(f"- 실패(exit={returncode}): {source}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
