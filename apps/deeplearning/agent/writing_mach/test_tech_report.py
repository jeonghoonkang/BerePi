from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import client_service


class FakePdfPage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, _path: str) -> None:
        self.pages = [
            FakePdfPage("Architecture module sends telemetry through a REST API."),
            FakePdfPage(""),
        ]


class FakePixmap:
    width = 1
    height = 1
    samples = b"\xff\xff\xff"

    def tobytes(self, _format: str) -> bytes:
        return b"fake-png"


class FakeRenderPage:
    def get_pixmap(self, **_kwargs: object) -> FakePixmap:
        return FakePixmap()


class FakeDocument:
    def load_page(self, _index: int) -> FakeRenderPage:
        return FakeRenderPage()

    def close(self) -> None:
        return


class TechReportPdfTests(unittest.TestCase):
    def test_uses_text_layer_and_ocr_for_scanned_page(self) -> None:
        fake_fitz = SimpleNamespace(
            open=lambda _path: FakeDocument(),
            Matrix=lambda *_args: object(),
        )
        with (
            patch("pypdf.PdfReader", FakeReader),
            patch.object(
                client_service,
                "_load_pdf_renderer",
                return_value=fake_fitz,
            ),
            patch.object(
                client_service,
                "call_model",
                return_value="OCR로 추출한 데이터 처리 모듈과 작동 원리 설명입니다.",
            ) as model,
        ):
            text, metadata = client_service.extract_pdf_content(
                Path("input.pdf"),
                config={"model": "vision-model"},
                minimum_text_characters=40,
            )

        self.assertIn("Architecture module", text)
        self.assertIn("OCR로 추출한", text)
        self.assertEqual(metadata["text_pages"], 1)
        self.assertEqual(metadata["ocr_pages"], 1)
        self.assertEqual(metadata["empty_pages"], 0)
        self.assertEqual(metadata["ocr_engine"], "vision-model")
        self.assertEqual(model.call_args.kwargs["images"], ["ZmFrZS1wbmc="])

    def test_default_pdf_is_latest_file_in_input_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            older = input_dir / "older.pdf"
            newer = input_dir / "newer.pdf"
            older.write_bytes(b"old")
            newer.write_bytes(b"new")
            older.touch()
            newer.touch()
            older_mtime = older.stat().st_mtime - 10
            older.chmod(older.stat().st_mode)
            import os

            os.utime(older, (older_mtime, older_mtime))
            with patch.object(client_service, "INPUT_DIR", input_dir):
                selected = client_service.resolve_tech_report_pdf("")

        self.assertEqual(selected.name, "newer.pdf")

    def test_cloud_vision_payload_contains_image_data_url(self) -> None:
        config = {
            "cloud_model_enabled": True,
            "model": "paid-vision-model",
            "cloud_max_tokens": 2048,
            "cloud_temperature": 0.1,
            "cloud_vision_detail": "high",
        }

        payload = client_service.build_generate_payload(
            config,
            "이미지의 문자를 추출하세요.",
            images=["ZmFrZS1wbmc="],
        )

        content = payload["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(
            content[1]["image_url"]["url"],
            "data:image/png;base64,ZmFrZS1wbmc=",
        )
        self.assertEqual(payload["model"], "paid-vision-model")

    def test_cloud_config_reads_api_key_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cloud.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "openai-compatible",
                        "base_url": "https://cloud.example.test",
                        "api_key_env": "TEST_CLOUD_API_KEY",
                        "model": "paid-model",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"TEST_CLOUD_API_KEY": "secret"}, clear=False):
                overrides = client_service.load_cloud_model_overrides(str(path))

        self.assertTrue(overrides["cloud_model_enabled"])
        self.assertEqual(overrides["cloud_api_key"], "secret")
        self.assertEqual(overrides["generate_path"], "/v1/chat/completions")
        self.assertEqual(
            client_service.model_request_headers(overrides),
            {"Authorization": "Bearer secret"},
        )

    def test_google_cloud_config_and_vision_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "google.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "google",
                        "api_key_env": "TEST_GOOGLE_API_KEY",
                        "model": "gemini-test",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"TEST_GOOGLE_API_KEY": "google-secret"}):
                config = client_service.load_cloud_model_overrides(str(path))

        payload = client_service.build_generate_payload(
            config, "read this", images=["ZmFrZS1wbmc="]
        )
        self.assertEqual(config["cloud_provider"], "google")
        self.assertIn("gemini-test:generateContent", config["generate_path"])
        self.assertEqual(
            client_service.model_request_headers(config),
            {"x-goog-api-key": "google-secret"},
        )
        self.assertEqual(
            payload["contents"][0]["parts"][1]["inline_data"]["data"],
            "ZmFrZS1wbmc=",
        )
        self.assertEqual(
            client_service.extract_response_text(
                {"candidates": [{"content": {"parts": [{"text": "google ok"}]}}]}
            ),
            "google ok",
        )

    def test_bedrock_config_and_converse_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bedrock.json"
            path.write_text(
                json.dumps(
                    {
                        "provider": "aws-bedrock",
                        "region": "ap-northeast-2",
                        "profile": "development",
                        "model": "vision-model",
                    }
                ),
                encoding="utf-8",
            )
            config = client_service.load_cloud_model_overrides(str(path))

        payload = client_service.build_generate_payload(
            config, "read this", images=["ZmFrZS1wbmc="]
        )
        self.assertEqual(config["cloud_provider"], "aws-bedrock")
        self.assertEqual(config["cloud_aws_profile"], "development")
        self.assertEqual(payload["modelId"], "vision-model")
        self.assertEqual(
            payload["messages"][0]["content"][1]["image"]["source"]["base64"],
            "ZmFrZS1wbmc=",
        )
        self.assertEqual(
            client_service.extract_response_text(
                {"output": {"message": {"content": [{"text": "bedrock ok"}]}}}
            ),
            "bedrock ok",
        )


if __name__ == "__main__":
    unittest.main()
