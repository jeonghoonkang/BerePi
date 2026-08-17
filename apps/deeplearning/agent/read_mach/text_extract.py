#!/usr/bin/env python3
"""Dispatch supported input files and URLs to their text extractors."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from vision_ocr_support import DEFAULT_CONFIG_PATH, DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR


EXTRACTORS = {
    ".pdf": "pdf_text_extractor.py",
    ".docx": "docx_text_extractor.py",
    ".pptx": "pptx_text_extractor.py",
    ".hwpx": "hwpx_text_extractor.py",
    ".jpg": "jpg_text_extractor.py",
    ".png": "png_text_extractor.py",
}


def format_elapsed(seconds: float) -> str:
    """Format an elapsed duration as HH:MM:SS.s."""
    total_seconds = max(0.0, float(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:04.1f}"


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
    skip_embedded_image_ocr: bool = False,
    rm_image: bool = False,
    cloud_fast_track: bool = False,
    cloud_fast_track_url: str | None = None,
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
    if suffix in {".pdf", ".pptx"}:
        command.extend(["--start-page", str(start_page)])
        if end_page is not None:
            command.extend(["--end-page", str(end_page)])
    if suffix == ".pdf":
        command.extend(["--ocr-dpi", str(ocr_dpi)])
        command.extend(["--minimum-text-characters", str(minimum_text_characters)])
    elif suffix == ".pptx":
        if skip_embedded_image_ocr:
            command.append("--skip-embedded-image-ocr")
    if rm_image and suffix in {".docx", ".pptx", ".hwpx"}:
        command.append("--rm-image")
    if cloud_fast_track:
        command.append("--cloud-fast-track")
        if cloud_fast_track_url:
            command.extend(["--cloud-fast-track-url", cloud_fast_track_url])
    return command


def url_extractor_command(
    url: str, *, config_path: Path, output_dir: Path, timeout: int
) -> list[str]:
    """Build the URL text extractor command for one web address."""
    script = Path(__file__).resolve().parent / "url_text_extractor.py"
    return [
        sys.executable,
        str(script),
        "--url",
        url,
        "--config",
        str(config_path),
        "--output-dir",
        str(output_dir),
        "--timeout",
        str(max(1, timeout)),
    ]


def bizcard_extractor_command(
    input_files: list[Path],
    *,
    config_path: Path,
    output_dir: Path,
    use_webdav: bool,
    webdav_url: str,
    webdav_username: str | None,
    webdav_password: str | None,
    webdav_timeout: int,
    force: bool,
    webdav_save_dir: Path | None = None,
    cloud_fast_track: bool = False,
    cloud_fast_track_url: str | None = None,
) -> list[str]:
    """Build the business-card document extractor command."""
    script = Path(__file__).resolve().parent / "bizcard_text_extractor.py"
    command = [
        sys.executable, str(script), "--config", str(config_path), "--output-dir", str(output_dir)
    ]
    for path in input_files:
        command.extend(["--input-file", str(path)])
    if use_webdav:
        command.extend(["--webdav", "--webdav-url", webdav_url])
        command.extend(["--webdav-timeout", str(max(1, webdav_timeout))])
        if webdav_username:
            command.extend(["--webdav-username", webdav_username])
        if webdav_password:
            command.extend(["--webdav-password", webdav_password])
        if webdav_save_dir is not None:
            command.extend(["--webdav-save-dir", str(webdav_save_dir)])
    if force:
        command.append("--force")
    if cloud_fast_track:
        command.append("--cloud-fast-track")
        if cloud_fast_track_url:
            command.extend(["--cloud-fast-track-url", cloud_fast_track_url])
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
        help=(
            "처리할 input 내부 파일. 여러 번 지정 가능하며, 파일과 URL을 모두 생략하면 "
            "지원 파일 전체를 처리합니다."
        ),
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="본문을 추출할 HTTP/HTTPS URL. 여러 번 지정할 수 있습니다.",
    )
    parser.add_argument("--bizcard", action="store_true", help="JPG/PNG 명함을 OCR하여 문서를 생성")
    parser.add_argument("--bizcard-webdav", action="store_true", help="명함 원본을 WebDAV에서 읽기")
    parser.add_argument("--bizcard-force", action="store_true", help="처리된 동일 경로 명함도 다시 OCR")
    parser.add_argument(
        "--webdav-url",
        default="http://keties.iptime.org:4001/apps/memories/folders/Photos/memories/biz_card",
    )
    parser.add_argument("--webdav-username")
    parser.add_argument("--webdav-password")
    parser.add_argument("--webdav-timeout", type=int, default=30)
    parser.add_argument(
        "--webdav-save-dir",
        type=Path,
        help="WebDAV 명함 원본을 함께 저장할 로컬 디렉토리 (--bizcard 전용)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--cloud-fast-track", action="store_true",
        help="server_url 대신 Cloud Fast Track 주소를 사용",
    )
    parser.add_argument(
        "--cloud-fast-track-url",
        help="설정 파일의 cloud_fast_track_url을 이번 실행에서 덮어쓰기",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-page", type=int, default=1, help="PDF/PPTX에 적용")
    parser.add_argument("--end-page", type=int, help="PDF/PPTX에 적용")
    parser.add_argument("--ocr-dpi", type=int, default=300, help="PDF에만 적용")
    parser.add_argument("--minimum-text-characters", type=int, default=100, help="PDF에만 적용")
    parser.add_argument(
        "--skip-embedded-image-ocr",
        action="store_true",
        help="PPTX 포함 이미지 OCR을 건너뛰고 슬라이드 문자만 추출",
    )
    parser.add_argument(
        "--rm-image",
        action="store_true",
        help="DOCX/PPTX/HWPX에서 추출한 그림을 output/extract_image에 남기지 않음",
    )
    parser.add_argument("--url-timeout", type=int, default=30, help="URL별 요청 제한 시간(초)")
    parser.add_argument("--fail-fast", action="store_true", help="첫 실패에서 처리를 중단")
    return parser.parse_args()


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    if args.bizcard:
        command = bizcard_extractor_command(
            args.input_file,
            config_path=args.config,
            output_dir=args.output_dir,
            use_webdav=args.bizcard_webdav,
            webdav_url=args.webdav_url,
            webdav_username=args.webdav_username,
            webdav_password=args.webdav_password,
            webdav_timeout=args.webdav_timeout,
            force=args.bizcard_force,
            webdav_save_dir=args.webdav_save_dir,
            cloud_fast_track=args.cloud_fast_track,
            cloud_fast_track_url=args.cloud_fast_track_url,
        )
        result = subprocess.run(command, check=False)
        print(f"전체 실행 시간: {format_elapsed(time.perf_counter() - started_at)}", flush=True)
        return result.returncode
    try:
        if args.input_file:
            sources = resolve_requested_files(DEFAULT_INPUT_DIR, args.input_file)
        elif args.url:
            sources = []
        else:
            sources = discover_input_files(DEFAULT_INPUT_DIR)
    except (OSError, ValueError) as exc:
        print(f"입력 파일 선택 실패: {exc}", file=sys.stderr)
        return 2

    if not sources and not args.url:
        print(f"지원되는 입력 파일 또는 URL이 없습니다: {DEFAULT_INPUT_DIR}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[tuple[str, int]] = []
    tasks: list[tuple[str, str, list[str]]] = []
    for source in sources:
        extractor = EXTRACTORS[source.suffix.casefold()]
        command = extractor_command(
            source, config_path=args.config, output_dir=args.output_dir,
            start_page=max(1, args.start_page), end_page=args.end_page,
            ocr_dpi=max(72, args.ocr_dpi),
            minimum_text_characters=max(0, args.minimum_text_characters),
            skip_embedded_image_ocr=getattr(args, "skip_embedded_image_ocr", False),
            rm_image=getattr(args, "rm_image", False),
            cloud_fast_track=getattr(args, "cloud_fast_track", False),
            cloud_fast_track_url=getattr(args, "cloud_fast_track_url", None),
        )
        tasks.append((str(source), extractor, command))
    for url in args.url:
        command = url_extractor_command(
            url, config_path=args.config, output_dir=args.output_dir, timeout=args.url_timeout
        )
        tasks.append((url, "url_text_extractor.py", command))

    total = len(tasks)
    attempted = 0
    successes = 0
    for index, (label, extractor, command) in enumerate(tasks, 1):
        attempted += 1
        task_started_at = time.perf_counter()
        print(f"[{index}/{total}] {label} -> {extractor}", flush=True)
        result = subprocess.run(command, check=False)
        task_elapsed = format_elapsed(time.perf_counter() - task_started_at)
        if result.returncode:
            failures.append((label, result.returncode))
            print(
                f"[{index}/{total}] 실패(exit={result.returncode}, 소요={task_elapsed}): {label}",
                file=sys.stderr,
            )
            if args.fail_fast:
                break
        else:
            successes += 1
            print(f"[{index}/{total}] 완료(소요={task_elapsed}): {label}", flush=True)

    print(f"처리 요약: 성공 {successes}, 실패 {len(failures)}, 시도 {attempted}, 대상 {total}")
    print(f"전체 실행 시간: {format_elapsed(time.perf_counter() - started_at)}", flush=True)
    if failures:
        for label, returncode in failures:
            print(f"- 실패(exit={returncode}): {label}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
