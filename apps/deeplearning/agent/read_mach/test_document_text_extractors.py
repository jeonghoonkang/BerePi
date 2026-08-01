from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from docx_text_extractor import extract_docx_package
from hwpx_text_extractor import extract_hwpx_package
from vision_ocr_support import image_mime_type


class DocumentTextExtractorTests(unittest.TestCase):
    def test_extracts_docx_text_and_raster_images(self) -> None:
        document = b'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>DOCX test</w:t></w:r></w:p></w:body>
</w:document>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", document)
                archive.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\ncontent")
                archive.writestr("word/media/vector1.emf", b"ignored")
            text, images = extract_docx_package(path)
        self.assertEqual(text, "DOCX test")
        self.assertEqual([name for name, _ in images], ["word/media/image1.png"])

    def test_extracts_hwpx_sections_in_numeric_order(self) -> None:
        section_one = b'<hp:section xmlns:hp="urn:hancom"><hp:p><hp:t>first</hp:t></hp:p></hp:section>'
        section_two = b'<hp:section xmlns:hp="urn:hancom"><hp:p><hp:t>second</hp:t></hp:p></hp:section>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hwpx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Contents/section10.xml", section_two)
                archive.writestr("Contents/section2.xml", section_one)
                archive.writestr("BinData/image1.jpg", b"\xff\xd8\xffcontent")
            text, images = extract_hwpx_package(path)
        self.assertEqual(text, "first\nsecond")
        self.assertEqual([name for name, _ in images], ["BinData/image1.jpg"])

    def test_detects_supported_image_mime_types(self) -> None:
        self.assertEqual(image_mime_type(b"\x89PNG\r\n\x1a\n"), "image/png")
        self.assertEqual(image_mime_type(b"\xff\xd8\xff"), "image/jpeg")
        with self.assertRaises(ValueError):
            image_mime_type(b"not an image")


if __name__ == "__main__":
    unittest.main()
