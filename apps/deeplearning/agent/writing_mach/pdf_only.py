#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from client_service import OUTPUT_DIR, write_book_pdf


def latest_book_markdown() -> Path:
    candidates = sorted(
        OUTPUT_DIR.glob("book_*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No book_*.md files found in {OUTPUT_DIR}")
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a Writing Mach markdown file to PDF only.")
    parser.add_argument(
        "markdown",
        nargs="?",
        help="Markdown file to convert. Defaults to the latest output/book_*.md.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="PDF output path. Defaults to the markdown path with .pdf suffix.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    markdown_path = Path(args.markdown).expanduser().resolve() if args.markdown else latest_book_markdown()
    if not markdown_path.exists():
        print(f"Markdown file not found: {markdown_path}", file=sys.stderr)
        return 2
    if markdown_path.suffix.lower() not in {".md", ".markdown"}:
        print(f"Input is not a markdown file: {markdown_path}", file=sys.stderr)
        return 2

    pdf_path = Path(args.output).expanduser().resolve() if args.output else markdown_path.with_suffix(".pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Markdown: {markdown_path}")
    print(f"PDF:      {pdf_path}")
    ok, message = write_book_pdf(markdown_path, pdf_path)
    if ok:
        print(f"PDF written: {message}")
        return 0

    print(f"PDF generation failed: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
