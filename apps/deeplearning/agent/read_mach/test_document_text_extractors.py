from __future__ import annotations

import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from docx_text_extractor import extract_docx_package
from hwpx_text_extractor import extract_hwpx_package
from pptx_text_extractor import extract_pptx_content, extract_pptx_package
from vision_ocr_support import (
    LocalParallelPlan,
    image_mime_type,
    local_parallel_plan,
    model_generate_url,
    model_status_url,
    resolve_model_server_url,
    verify_cloud_fast_track,
)


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

    def test_extracts_pptx_text_in_presentation_order_and_raster_images(self) -> None:
        presentation = b'''<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="1" r:id="rId10"/><p:sldId id="2" r:id="rId2"/></p:sldIdLst>
</p:presentation>'''
        relationships = b'''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2" Target="slides/slide2.xml"/>
  <Relationship Id="rId10" Target="slides/slide10.xml"/>
</Relationships>'''
        slide_template = '''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
 <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
</p:sld>'''
        slide_relationship_template = '''<Relationships
 xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="../media/{}"/>
</Relationships>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pptx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("ppt/presentation.xml", presentation)
                archive.writestr("ppt/_rels/presentation.xml.rels", relationships)
                archive.writestr("ppt/slides/slide2.xml", slide_template.format("second"))
                archive.writestr("ppt/slides/slide10.xml", slide_template.format("first"))
                archive.writestr(
                    "ppt/slides/_rels/slide2.xml.rels",
                    slide_relationship_template.format("image2.jpg"),
                )
                archive.writestr(
                    "ppt/slides/_rels/slide10.xml.rels",
                    slide_relationship_template.format("image1.png"),
                )
                archive.writestr("ppt/media/image1.png", b"\x89PNG\r\n\x1a\ncontent")
                archive.writestr("ppt/media/image2.jpg", b"\xff\xd8\xffcontent")
                archive.writestr("ppt/media/vector1.emf", b"ignored")
            progress_messages: list[str] = []
            text, images = extract_pptx_package(
                path,
                progress=lambda _label, message, _color: progress_messages.append(message),
            )
            ocr_progress_messages: list[str] = []
            plan = LocalParallelPlan(4, 4, 4, 2, ("target-1", "target-2", "target-3", "target-4"))
            concurrent_calls = threading.Barrier(2)

            def fake_ocr(*_args, **_kwargs):
                concurrent_calls.wait(timeout=2)
                return "image text", {"ocr_engine": "vision", "ocr_model": "test"}

            with patch("pptx_text_extractor.local_parallel_plan", return_value=plan), patch(
                "pptx_text_extractor.call_vision_ocr",
                side_effect=fake_ocr,
            ) as ocr_call:
                content, metadata = extract_pptx_content(
                    path,
                    progress=lambda _label, message, _color: ocr_progress_messages.append(message),
                    output_dir=Path(directory) / "output",
                )
            saved_image_data = [
                Path(saved_path).read_bytes()
                for saved_path in metadata["extracted_image_files"]
            ]
            failover_calls: list[tuple[str, list[bytes], str]] = []
            failover_progress: list[str] = []

            def fake_ocr_with_failover(images, prompt, **kwargs):
                target_id = kwargs["local_target_id"]
                failover_calls.append((target_id, images, prompt))
                if target_id == "target-1":
                    raise RuntimeError("GPU failed")
                return "recovered image text", {"ocr_engine": "vision", "ocr_model": "test"}

            with patch("pptx_text_extractor.local_parallel_plan", return_value=plan), patch(
                "pptx_text_extractor.call_vision_ocr", side_effect=fake_ocr_with_failover,
            ):
                _recovered_content, recovered_metadata = extract_pptx_content(
                    path,
                    progress=lambda _label, message, _color: failover_progress.append(message),
                )
            selected_progress: list[str] = []
            selected_text, selected_images = extract_pptx_package(
                path,
                start_page=2,
                end_page=2,
                progress=lambda _label, message, _color: selected_progress.append(message),
            )
        self.assertEqual(text, "first\n\nsecond")
        self.assertEqual(
            [name for name, _ in images],
            ["ppt/media/image1.png", "ppt/media/image2.jpg"],
        )
        self.assertEqual(len(progress_messages), 2)
        self.assertIn("선택 2페이지", progress_messages[0])
        self.assertIn("현재 1/2페이지", progress_messages[0])
        self.assertIn("단계 50.0%", progress_messages[0])
        self.assertIn("현재 2/2페이지", progress_messages[1])
        self.assertIn("단계 100.0%", progress_messages[1])
        self.assertIn("image text", content)
        self.assertEqual(metadata["page_count"], 2)
        self.assertEqual(metadata["available_gpu_count"], 4)
        self.assertEqual(metadata["available_model_count"], 4)
        self.assertEqual(metadata["ocr_parallel_workers"], 2)
        self.assertEqual(metadata["extracted_image_file_count"], 2)
        self.assertEqual(
            saved_image_data,
            [b"\x89PNG\r\n\x1a\ncontent", b"\xff\xd8\xffcontent"],
        )
        self.assertEqual(
            {call.kwargs["local_target_id"] for call in ocr_call.call_args_list},
            {"target-1", "target-2"},
        )
        self.assertTrue(any("병렬 2개" in message for message in ocr_progress_messages))
        self.assertIn("현재 2/2개", ocr_progress_messages[-2])
        self.assertIn("전체 100.0%", ocr_progress_messages[-2])
        self.assertIn("전체 100.0%", ocr_progress_messages[-1])
        retry_calls = [call for call in failover_calls if "그림 1" in call[2]]
        self.assertEqual([call[0] for call in retry_calls], ["target-1", "target-2"])
        self.assertEqual(retry_calls[0][1], retry_calls[1][1])
        self.assertEqual(retry_calls[0][2], retry_calls[1][2])
        self.assertEqual(recovered_metadata["gpu_failover_count"], 1)
        self.assertTrue(any("동일 데이터 재전송" in message for message in failover_progress))
        self.assertEqual(selected_text, "second")
        self.assertEqual(
            [name for name, _ in selected_images], ["ppt/media/image2.jpg"]
        )
        self.assertIn("선택 1페이지", selected_progress[0])
        self.assertIn("원본 2페이지", selected_progress[0])

    def test_detects_supported_image_mime_types(self) -> None:
        self.assertEqual(image_mime_type(b"\x89PNG\r\n\x1a\n"), "image/png")
        self.assertEqual(image_mime_type(b"\xff\xd8\xff"), "image/jpeg")
        with self.assertRaises(ValueError):
            image_mime_type(b"not an image")

    def test_selects_cloud_fast_track_url_only_when_requested(self) -> None:
        config = {
            "server_url": "http://router.example:4004/",
            "cloud_fast_track_url": "https://fast.example/api/",
        }
        self.assertEqual(
            resolve_model_server_url(config),
            ("http://router.example:4004", "server"),
        )
        self.assertEqual(
            resolve_model_server_url(config, cloud_fast_track=True),
            ("https://fast.example/api", "cloud-fast-track"),
        )
        self.assertEqual(
            resolve_model_server_url(
                config, cloud_fast_track=True,
                cloud_fast_track_url="https://override.example/fast/",
            ),
            ("https://override.example/fast", "cloud-fast-track"),
        )

    def test_rejects_missing_cloud_fast_track_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "cloud_fast_track_url"):
            resolve_model_server_url({"server_url": "http://router"}, cloud_fast_track=True)

    def test_cloud_fast_track_appends_dedicated_gcp_paths(self) -> None:
        base_url = "http://router.example:4004"
        self.assertEqual(
            model_generate_url(base_url, cloud_fast_track=True),
            "http://router.example:4004/api/gcp/generate",
        )
        self.assertEqual(
            model_status_url(base_url, cloud_fast_track=True),
            "http://router.example:4004/api/gcp/status",
        )
        self.assertEqual(
            model_generate_url(base_url),
            "http://router.example:4004/api/generate",
        )

    def test_verifies_cloud_fast_track_status_endpoint(self) -> None:
        response = MagicMock()
        response.json.return_value = {
            "ok": True, "configured": True, "model_id": "gemma-4-31b-it"
        }
        session = MagicMock()
        session.get.return_value = response

        result = verify_cloud_fast_track(
            session, "http://unique-router.example:4004", password="secret", timeout=90
        )

        self.assertTrue(result["configured"])
        session.get.assert_called_once()
        self.assertEqual(
            session.get.call_args.args[0],
            "http://unique-router.example:4004/api/gcp/status",
        )
        self.assertEqual(session.get.call_args.kwargs["timeout"], 30)

    def test_local_parallel_plan_uses_half_of_available_gpus(self) -> None:
        targets = [
            {
                "id": f"target-{index}",
                "host": f"worker-{index}.example",
                "port": 11434,
                "selected_gpu": "0",
                "api_type": "ollama",
                "model": "gemma4:31b",
            }
            for index in range(1, 6)
        ]
        response = MagicMock()
        response.json.return_value = {
            "targets": targets,
            "metrics": {
                target["id"]: {
                    "available_targets": 2 if target["id"] == "target-1" else 1,
                    "dispatch_eligible": True,
                }
                for target in targets
            },
        }
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "server.json"
            config_path.write_text(
                '{"server_url":"http://router.example:4004","model":"gemma4:31b"}',
                encoding="utf-8",
            )
            with patch("requests.Session", return_value=session):
                plan = local_parallel_plan(config_path=config_path, password="secret")

        self.assertEqual(plan.available_gpu_count, 5)
        self.assertEqual(plan.available_model_count, 6)
        self.assertEqual(plan.available_count, 5)
        self.assertEqual(plan.max_workers, 2)
        self.assertEqual(plan.target_ids, tuple(target["id"] for target in targets))
        self.assertEqual(session.get.call_args.args[0], "http://router.example:4004/api/status")


if __name__ == "__main__":
    unittest.main()
