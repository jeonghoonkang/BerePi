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
            (root / "c.pptx").touch()
            (root / "ignored.txt").touch()
            files = text_extract.discover_input_files(root)
        self.assertEqual([path.name for path in files], ["a.docx", "B.PNG", "c.pptx"])

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

    def test_can_skip_pptx_embedded_image_ocr(self) -> None:
        command = text_extract.extractor_command(
            Path("sample.pptx"),
            config_path=Path("config.json"),
            output_dir=Path("output"),
            start_page=1,
            end_page=None,
            ocr_dpi=300,
            minimum_text_characters=100,
            skip_embedded_image_ocr=True,
        )
        self.assertIn("--skip-embedded-image-ocr", command)

    def test_forwards_cloud_fast_track_selection(self) -> None:
        command = text_extract.extractor_command(
            Path("sample.pptx"),
            config_path=Path("config.json"),
            output_dir=Path("output"),
            start_page=1,
            end_page=None,
            ocr_dpi=300,
            minimum_text_characters=100,
            cloud_fast_track=True,
            cloud_fast_track_url="https://fast.example/routing",
        )
        self.assertIn("--cloud-fast-track", command)
        self.assertEqual(
            command[command.index("--cloud-fast-track-url") + 1],
            "https://fast.example/routing",
        )

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

    @patch.object(text_extract.sys, "executable", "python")
    def test_builds_local_bizcard_command(self) -> None:
        command = text_extract.bizcard_extractor_command(
            [Path("input/card.jpg"), Path("input/card.png")],
            config_path=Path("config.json"), output_dir=Path("output"),
            use_webdav=False, webdav_url="https://dav.example/cards",
            webdav_username=None, webdav_password=None, webdav_timeout=30, force=False,
        )
        self.assertEqual(Path(command[1]).name, "bizcard_text_extractor.py")
        self.assertEqual(command.count("--input-file"), 2)
        self.assertNotIn("--webdav", command)

    @patch.object(text_extract.sys, "executable", "python")
    def test_builds_webdav_bizcard_command(self) -> None:
        command = text_extract.bizcard_extractor_command(
            [], config_path=Path("config.json"), output_dir=Path("output"),
            use_webdav=True, webdav_url="https://dav.example/cards",
            webdav_username="user", webdav_password="secret", webdav_timeout=40, force=True,
            webdav_save_dir=Path("input/webdav"),
        )
        self.assertIn("--webdav", command)
        self.assertIn("--force", command)
        self.assertEqual(command[command.index("--webdav-url") + 1], "https://dav.example/cards")
        self.assertEqual(command[command.index("--webdav-save-dir") + 1], "input\\webdav")

    @patch("text_extract.subprocess.run")
    @patch("text_extract.parse_args")
    def test_processes_multiple_urls_without_scanning_files(self, parse_args, run) -> None:
        parse_args.return_value = type("Args", (), {
            "input_file": [], "url": ["https://example.com/a", "https://example.com/b"],
            "bizcard": False,
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
