from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import text_extract


class TextExtractDispatcherTests(unittest.TestCase):
    def test_discovers_supported_files_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "B.PNG").touch()
            (root / "a.docx").touch()
            (root / "ignored.txt").touch()
            files = text_extract.discover_input_files(root)
        self.assertEqual([path.name for path in files], ["a.docx", "B.PNG"])

    def test_maps_each_extension_to_its_extractor(self) -> None:
        for suffix, script_name in text_extract.EXTRACTORS.items():
            with self.subTest(suffix=suffix), patch.object(text_extract.sys, "executable", "python"):
                command = text_extract.extractor_command(
                    Path(f"sample{suffix}"),
                    config_path=Path("config.json"),
                    output_dir=Path("output"),
                    start_page=1,
                    end_page=None,
                    ocr_dpi=300,
                    minimum_text_characters=100,
                )
            self.assertEqual(Path(command[1]).name, script_name)

    def test_rejects_unsupported_explicit_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "notes.txt"
            unsupported.touch()
            with self.assertRaisesRegex(ValueError, "지원하지 않는"):
                text_extract.resolve_requested_files(root, [unsupported])


if __name__ == "__main__":
    unittest.main()
