from __future__ import annotations

import unittest

from pdf_text_extractor import merge_page_text, model_ocr_prompt, normalize_extracted_text


class PdfTextExtractorTests(unittest.TestCase):
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
