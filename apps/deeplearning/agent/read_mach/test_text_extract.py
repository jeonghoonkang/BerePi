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

    @patch.object(text_extract.sys, "executable", "python")
    def test_builds_url_extractor_command(self) -> None:
        command = text_extract.url_extractor_command(
            "https://example.com/article",
            config_path=Path("config.json"),
            output_dir=Path("output"),
            timeout=45,
        )
        self.assertEqual(Path(command[1]).name, "url_text_extractor.py")
        self.assertEqual(command[command.index("--url") + 1], "https://example.com/article")
        self.assertEqual(command[command.index("--timeout") + 1], "45")

    @patch("text_extract.subprocess.run")
    @patch("text_extract.parse_args")
    def test_processes_multiple_urls_without_scanning_files(self, parse_args, run) -> None:
        parse_args.return_value = type("Args", (), {
            "input_file": [], "url": ["https://example.com/a", "https://example.com/b"],
            "config": Path("config.json"), "output_dir": Path("output"),
            "start_page": 1, "end_page": None, "ocr_dpi": 300,
            "minimum_text_characters": 100, "url_timeout": 30, "fail_fast": False,
        })()
        run.return_value.returncode = 0
        with patch.object(Path, "mkdir"):
            result = text_extract.main()
        self.assertEqual(result, 0)
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
