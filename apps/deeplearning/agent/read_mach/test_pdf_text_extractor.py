from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_text_extractor import extract_pdf_content, merge_page_text, model_ocr_prompt, normalize_extracted_text


class FakePage:
    def __init__(self, number: int) -> None:
        self.number = number

    def extract_text(self) -> str:
        return f"page {self.number} " + ("content " * 20)


class FakeReader:
    def __init__(self, _path: str) -> None:
        self.pages = [FakePage(number) for number in range(1, 7)]


class PdfTextExtractorTests(unittest.TestCase):
    def test_extracts_only_selected_page_range(self) -> None:
        progress_messages: list[str] = []
        with patch("pypdf.PdfReader", FakeReader):
            text, metadata = extract_pdf_content(
                Path("sample.pdf"),
                start_page=4,
                end_page=6,
                minimum_text_characters=10,
                progress=lambda _label, message, _color: progress_messages.append(message),
            )

        self.assertNotIn("[PDF page 3", text)
        self.assertIn("[PDF page 4", text)
        self.assertIn("[PDF page 6", text)
        self.assertEqual(metadata["page_count"], 3)
        self.assertEqual(metadata["total_pdf_pages"], 6)
        self.assertEqual(len(progress_messages), 3)
        self.assertIn("전체 3페이지", progress_messages[0])
        self.assertIn("현재 1/3페이지", progress_messages[0])
        self.assertIn("원본 4페이지", progress_messages[0])
        self.assertIn("진행률 33.3%", progress_messages[0])
        self.assertIn("현재 3/3페이지", progress_messages[-1])
        self.assertIn("진행률 100.0%", progress_messages[-1])

    def test_normalizes_wrapped_and_repeated_whitespace(self) -> None:
        self.assertEqual(normalize_extracted_text("data-\nflow   module"), "dataflow module")

    def test_merges_ocr_lines_without_repeating_text_layer(self) -> None:
        merged = merge_page_text("Architecture\nGateway", "Gateway\n센서 데이터")
        self.assertEqual(merged, "Architecture\nGateway\n센서 데이터")

    def test_ocr_prompt_contains_page_and_existing_text(self) -> None:
        prompt = model_ocr_prompt(3, "existing layer")
        self.assertIn("3페이지", prompt)
        self.assertIn("existing layer", prompt)


if __name__ == "__main__":
    unittest.main()
