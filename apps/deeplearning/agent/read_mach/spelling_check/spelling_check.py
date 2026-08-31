#!/usr/bin/env python3
"""Report Korean and English spelling issues in a PDF, page by page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol


HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")
ENGLISH_RUN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*")
SENTENCE_RE = re.compile(r"[^\n.!?。！？]+(?:[.!?。！？]+|$)")


class Checker(Protocol):
    def check(self, text: str) -> Iterable[Any]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SpellingIssue:
    page: int
    language: str
    error: str
    correction: str
    message: str
    context: str
    rule_id: str


def normalize_text(text: str) -> str:
    """Normalize PDF text without joining unrelated blocks."""
    text = (text or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=[A-Za-z])-\n(?=[A-Za-z])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def iter_language_segments(text: str) -> Iterable[tuple[str, str]]:
    """Yield sentence-like segments classified as Korean or English."""
    for paragraph in text.splitlines():
        for match in SENTENCE_RE.finditer(paragraph):
            segment = match.group(0).strip()
            if not segment:
                continue
            hangul_count = len(HANGUL_RE.findall(segment))
            latin_count = len(LATIN_RE.findall(segment))
            if hangul_count:
                yield "ko-KR", segment
                # Korean technical documents commonly embed English words. Check
                # those runs separately so an English typo is not overlooked.
                for english_match in ENGLISH_RUN_RE.finditer(segment):
                    yield "en-US", english_match.group(0)
            elif latin_count:
                yield "en-US", segment


def extract_pdf_pages(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf가 필요합니다. requirements.txt를 설치해 주세요.") from exc

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise RuntimeError("암호화된 PDF를 열 수 없습니다.") from exc
    return [normalize_text(page.extract_text() or "") for page in reader.pages]


def _value(match: Any, *names: str, default: Any = "") -> Any:
    for name in names:
        if hasattr(match, name):
            return getattr(match, name)
        if isinstance(match, dict) and name in match:
            return match[name]
    return default


def issue_from_match(page: int, language: str, segment: str, match: Any) -> SpellingIssue:
    offset = int(_value(match, "offset", default=0))
    length = int(_value(match, "error_length", "errorLength", "length", default=0))
    replacements = list(_value(match, "replacements", default=[]) or [])
    context_start = max(0, offset - 35)
    context_end = min(len(segment), offset + max(length, 1) + 35)
    context = segment[context_start:context_end]
    if context_start:
        context = "..." + context
    if context_end < len(segment):
        context += "..."
    return SpellingIssue(
        page=page,
        language=language,
        error=segment[offset : offset + length],
        correction=replacements[0] if replacements else "(수정 제안 없음)",
        message=str(_value(match, "message", default="")),
        context=context,
        rule_id=str(_value(match, "rule_id", "ruleId", default="")),
    )


def check_pages(
    pages: list[str],
    checkers: dict[str, Checker],
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[SpellingIssue], list[int]]:
    issues: list[SpellingIssue] = []
    empty_pages: list[int] = []
    total_pages = len(pages)
    for page_number, text in enumerate(pages, 1):
        if progress:
            progress(page_number, total_pages)
        if not text.strip():
            empty_pages.append(page_number)
            continue
        for language, segment in iter_language_segments(text):
            for match in checkers[language].check(segment):
                issues.append(issue_from_match(page_number, language, segment, match))
    return issues, empty_pages


def create_checkers(
    remote_url: str | None = None,
    *,
    public_api: bool = False,
) -> dict[str, Checker]:
    try:
        import language_tool_python
    except ImportError as exc:
        raise RuntimeError("language-tool-python이 필요합니다. requirements.txt를 설치해 주세요.") from exc

    if public_api:
        return {
            language: language_tool_python.LanguageToolPublicAPI(language)
            for language in ("ko-KR", "en-US")
        }
    kwargs = {"remote_server": remote_url} if remote_url else {}
    try:
        return {
            language: language_tool_python.LanguageTool(language, **kwargs)
            for language in ("ko-KR", "en-US")
        }
    except Exception as exc:
        mode = f"원격 서버({remote_url})" if remote_url else "로컬 서버"
        raise RuntimeError(
            f"LanguageTool {mode}를 시작하지 못했습니다: {exc}. "
            "로컬 모드는 Java가 필요합니다. Java를 설치하거나 --remote-url을 사용해 주세요."
        ) from exc


def print_report(pdf_path: Path, pages: list[str], issues: list[SpellingIssue], empty_pages: list[int]) -> None:
    print(f"PDF: {pdf_path}")
    print(f"페이지: {len(pages)} | 오류 후보: {len(issues)}")
    if empty_pages:
        joined = ", ".join(map(str, empty_pages))
        print(f"경고: 텍스트를 추출하지 못한 페이지: {joined} (스캔 PDF는 OCR 필요)")
    for number, issue in enumerate(issues, 1):
        print(f"\n[{number}] 페이지 {issue.page} | {issue.language}")
        print(f"오류: {issue.error or '(위치만 탐지됨)'}")
        print(f"수정: {issue.correction}")
        print(f"설명: {issue.message}")
        print(f"문맥: {issue.context}")


def print_progress(page_number: int, total_pages: int) -> None:
    """Display the currently checked page immediately."""
    print(
        f"\r맞춤법 검사 중: {page_number}/{total_pages} 페이지",
        end="" if page_number < total_pages else "\n",
        file=sys.stderr,
        flush=True,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF의 한글/영문 맞춤법 오류를 페이지별로 검사합니다.")
    parser.add_argument("input_pdf", type=Path, help="검사할 PDF 파일")
    parser.add_argument("--output", "-o", type=Path, help="JSON 결과 파일 경로")
    server_group = parser.add_mutually_exclusive_group()
    server_group.add_argument("--remote-url", help="기존 LanguageTool 서버 URL")
    server_group.add_argument(
        "--public-api",
        action="store_true",
        help="무료 공개 API 사용 (긴 PDF는 요청 한도 때문에 권장하지 않음)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_path = args.input_pdf.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        print(f"오류: PDF 파일을 찾을 수 없습니다: {pdf_path}", file=sys.stderr)
        return 2

    checkers: dict[str, Checker] = {}
    try:
        pages = extract_pdf_pages(pdf_path)
        print("LanguageTool 검사기를 준비하는 중...", file=sys.stderr, flush=True)
        checkers = create_checkers(args.remote_url, public_api=args.public_api)
        issues, empty_pages = check_pages(pages, checkers, progress=print_progress)
        print_report(pdf_path, pages, issues, empty_pages)
        if args.output:
            output_path = args.output.expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "input_pdf": str(pdf_path),
                "page_count": len(pages),
                "issue_count": len(issues),
                "empty_text_pages": empty_pages,
                "issues": [asdict(issue) for issue in issues],
            }
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nJSON 저장: {output_path}")
        return 1 if issues else 0
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    finally:
        for checker in checkers.values():
            try:
                checker.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
