#!/usr/bin/env python3
"""Extract visible slide text and OCR embedded raster images from a PPTX file."""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

from pdf_text_extractor import normalize_extracted_text
from error_handling.gpu_failover import GPUFailoverAttempt, execute_with_gpu_failover
from extracted_image_output import output_extracted_images
from vision_ocr_support import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    OCR_PROMPT,
    call_vision_ocr,
    local_parallel_plan,
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


def _selected_slide_images(
    archive: zipfile.ZipFile, slide_names: list[str]
) -> list[tuple[str, bytes]]:
    """Return raster images directly referenced by the selected slides."""
    archive_names = set(archive.namelist())
    image_names: list[str] = []
    seen: set[str] = set()
    for slide_name in slide_names:
        relationship_name = posixpath.join(
            posixpath.dirname(slide_name), "_rels", f"{posixpath.basename(slide_name)}.rels"
        )
        if relationship_name not in archive_names:
            continue
        relationships = ET.fromstring(archive.read(relationship_name))
        for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
            if relationship.attrib.get("TargetMode") == "External":
                continue
            target = relationship.attrib.get("Target", "")
            name = posixpath.normpath(posixpath.join(posixpath.dirname(slide_name), target))
            name = name.lstrip("/")
            if (
                name in archive_names
                and Path(name).suffix.casefold() in RASTER_SUFFIXES
                and name not in seen
            ):
                seen.add(name)
                image_names.append(name)
    return [(name, archive.read(name)) for name in image_names]


def _extract_pptx_package(
    path: Path, *, progress: ProgressCallback | None = None,
    image_ocr_planned: bool = False,
    start_page: int = 1, end_page: int | None = None,
) -> tuple[str, list[tuple[str, bytes]], dict[str, int]]:
    """Read visible slide text and raster media using only the standard library."""
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = _slide_names(archive)
            if not slide_names:
                raise ValueError("슬라이드 항목이 없습니다.")

            total_pptx_pages = len(slide_names)
            first_page = max(1, int(start_page))
            last_page = min(
                total_pptx_pages,
                int(end_page) if end_page is not None else total_pptx_pages,
            )
            if first_page > last_page:
                raise ValueError(
                    f"처리할 슬라이드 범위가 없습니다: start={first_page}, "
                    f"end={last_page}, total={total_pptx_pages}"
                )
            selected_slide_names = slide_names[first_page - 1:last_page]
            images = _selected_slide_images(archive, selected_slide_names)
            slides: list[str] = []
            page_count = len(selected_slide_names)
            total_work = page_count + (len(images) if image_ocr_planned else 0)
            for current_page, slide_name in enumerate(selected_slide_names, 1):
                original_page = first_page + current_page - 1
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
                    stage_percentage = current_page * 100 / page_count
                    overall_percentage = current_page * 100 / total_work
                    stage_label = (
                        "PPTX 1/2: 슬라이드 문자"
                        if image_ocr_planned
                        else "PPTX 슬라이드 문자"
                    )
                    progress(
                        "pptx-page-progress",
                        f"[{stage_label}] 선택 {page_count}페이지 | "
                        f"현재 {current_page}/{page_count}페이지 "
                        f"(원본 {original_page}페이지) | "
                        f"단계 {stage_percentage:.1f}% | 전체 {overall_percentage:.1f}%",
                        "cyan",
                    )

    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"올바른 PPTX 문서가 아닙니다: {path} | {exc}") from exc
    page_metadata = {
        "page_count": page_count,
        "total_pptx_pages": total_pptx_pages,
        "start_page": first_page,
        "end_page": last_page,
    }
    return normalize_extracted_text("\n\n".join(slides)), images, page_metadata


def extract_pptx_package(
    path: Path, *, progress: ProgressCallback | None = None,
    start_page: int = 1, end_page: int | None = None,
) -> tuple[str, list[tuple[str, bytes]]]:
    """Read a PPTX package while preserving the existing two-value public API."""
    text, images, _page_metadata = _extract_pptx_package(
        path, progress=progress, start_page=start_page, end_page=end_page
    )
    return text, images


def extract_pptx_content(
    path: Path, *, config_path: Path = DEFAULT_CONFIG_PATH, password: str | None = None,
    progress: ProgressCallback | None = None, ocr_embedded_images: bool = True,
    cloud_fast_track: bool = False, cloud_fast_track_url: str | None = None,
    start_page: int = 1, end_page: int | None = None,
    output_dir: Path | None = None, rm_image: bool = False,
) -> tuple[str, dict[str, object]]:
    text, images, page_metadata = _extract_pptx_package(
        path, progress=progress, image_ocr_planned=ocr_embedded_images,
        start_page=start_page, end_page=end_page,
    )
    image_output_metadata: dict[str, object] = {}
    if output_dir is not None:
        image_output_metadata = output_extracted_images(
            images, source_path=path, output_dir=output_dir, rm_image=rm_image
        ).metadata()
    page_count = page_metadata["page_count"]
    ocr_blocks: list[str] = []
    model_metadata: dict[str, object] = {"ocr_engine": "not-used", "ocr_model": None}
    ocr_images = images if ocr_embedded_images else []
    total_work = page_count + len(ocr_images)
    parallel_metadata: dict[str, object] = {}
    worker_count = 1
    plan = None
    failover_count = 0
    failover_lock = threading.Lock()
    if ocr_images and not cloud_fast_track:
        plan = local_parallel_plan(config_path=config_path, password=password)
        worker_count = min(len(ocr_images), plan.max_workers)
        parallel_metadata = {
            "available_gpu_count": plan.available_gpu_count,
            "available_model_count": plan.available_model_count,
            "available_local_count": plan.available_count,
            "gpu_parallel_ratio": 0.5,
            "ocr_parallel_workers": worker_count,
            "gpu_failover_enabled": len(plan.target_ids) > 1,
        }
        if progress:
            progress(
                "pptx-local-parallel-plan",
                f"[로컬 LLM 병렬 설정] 가용 GPU {plan.available_gpu_count}개 | "
                f"가용 모델 {plan.available_model_count}개 | "
                f"GPU 50% 기준 병렬 {worker_count}개",
                "cyan",
            )

    def ocr_image(index: int, name: str, data: bytes) -> tuple[str, dict[str, object]]:
        def call_target(target_id: str | None) -> tuple[str, dict[str, object]]:
            return call_vision_ocr(
                [data], f"{OCR_PROMPT}\nPPTX 포함 그림 {index}({name})를 전사한다.",
                config_path=config_path, password=password,
                client_id="read-mach-pptx-text-extractor",
                cloud_fast_track=cloud_fast_track,
                cloud_fast_track_url=cloud_fast_track_url,
                local_target_id=target_id,
            )

        if plan is None:
            return call_target(None)

        initial_target_id = plan.target_ids[(index - 1) % len(plan.target_ids)]

        def report_failover(attempt: GPUFailoverAttempt, next_target_id: str) -> None:
            nonlocal failover_count
            with failover_lock:
                failover_count += 1
            if progress:
                progress(
                    "pptx-gpu-failover",
                    f"[GPU 장애 전환] {name} | target {attempt.target_id} 실패 "
                    f"({attempt.error_type}: {attempt.error_message}) | "
                    f"target {next_target_id}로 동일 데이터 재전송",
                    "yellow",
                )

        return execute_with_gpu_failover(
            plan.target_ids,
            call_target,
            initial_target_id=initial_target_id,
            on_failover=report_failover,
        )

    ocr_results: list[tuple[str, dict[str, object]] | None] = [None] * len(ocr_images)
    if worker_count == 1:
        for result_index, (name, data) in enumerate(ocr_images):
            ocr_results[result_index] = ocr_image(result_index + 1, name, data)
            if progress:
                completed = result_index + 1
                progress(
                    "pptx-image-ocr-progress",
                    f"[PPTX 2/2: 이미지 OCR] 전체 {len(ocr_images)}개 | "
                    f"현재 {completed}/{len(ocr_images)}개 ({name}) | "
                    f"완료 {completed * 100 / len(ocr_images):.1f}% | "
                    f"전체 {(page_count + completed) * 100 / total_work:.1f}%",
                    "cyan",
                )
    elif ocr_images:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(ocr_image, index, name, data): (index, name)
                for index, (name, data) in enumerate(ocr_images, 1)
            }
            for completed, future in enumerate(as_completed(futures), 1):
                index, name = futures[future]
                ocr_results[index - 1] = future.result()
                if progress:
                    progress(
                        "pptx-image-ocr-progress",
                        f"[PPTX 2/2: 이미지 OCR] 전체 {len(ocr_images)}개 | "
                        f"현재 {completed}/{len(ocr_images)}개 ({name}) | "
                        f"완료 {completed * 100 / len(ocr_images):.1f}% | "
                        f"전체 {(page_count + completed) * 100 / total_work:.1f}%",
                        "cyan",
                    )

    for index, ((name, _data), ocr_result) in enumerate(zip(ocr_images, ocr_results), 1):
        if ocr_result is None:
            continue
        result, result_metadata = ocr_result
        model_metadata = result_metadata
        if result.strip():
            ocr_blocks.append(f"[PPTX embedded image {index}: {name}]\n{result.strip()}")
    if parallel_metadata:
        parallel_metadata["gpu_failover_count"] = failover_count

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
        **page_metadata, "document_text_characters": len(text),
        "embedded_images": len(images), "embedded_image_ocr_skipped": not ocr_embedded_images,
        "ocr_images": len(ocr_blocks), **model_metadata, **parallel_metadata,
        **image_output_metadata,
    }
    return combined, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="PPTX 슬라이드와 포함 그림의 문자를 추출합니다.")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--password")
    parser.add_argument(
        "--rm-image", action="store_true",
        help="추출 이미지를 OCR에 사용한 뒤 output/extract_image에 남기지 않습니다.",
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
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
            start_page=args.start_page,
            end_page=args.end_page,
            output_dir=args.output_dir,
            rm_image=args.rm_image,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        range_suffix = (
            f"_pages_{metadata['start_page']}-{metadata['end_page']}"
            if args.start_page != 1 or args.end_page is not None
            else ""
        )
        text_path = args.output_dir / f"{source.stem}{range_suffix}_pptx_extracted.txt"
        metadata_path = args.output_dir / f"{source.stem}{range_suffix}_pptx_extraction.json"
        text_path.write_text(text + "\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if metadata.get("extracted_images_removed"):
            print(f"추출 그림 삭제: {metadata['extracted_image_directory']}")
        elif metadata.get("extracted_image_file_count"):
            print(f"추출 그림 저장: {metadata['extracted_image_directory']}")
        print(f"추출 문자 저장: {text_path}")
        print(f"추출 정보 저장: {metadata_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"PPTX 문자 추출 실패: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
