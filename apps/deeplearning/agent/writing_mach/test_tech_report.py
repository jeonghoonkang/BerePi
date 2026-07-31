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
    def test_short_report_expansion_requires_explicit_approval(self) -> None:
        with patch("builtins.input", return_value="n"):
            self.assertFalse(client_service.confirm_tech_report_expansion(8, "pdf"))
        with patch("builtins.input", return_value="yes"):
            self.assertTrue(client_service.confirm_tech_report_expansion(8, "pdf"))

    def test_splits_five_report_sections_as_expansion_guides(self) -> None:
        report = """# 기술 보고서

## 1. 개요 (Background & Objectives)
개요 내용
## 2. 핵심 아키텍처 및 데이터 흐름 (Core Architecture & Workflow)
구조 내용
## 3. 주요 모듈 / 기술 사양 (Technical Specifications - 표 형식 활용)
사양 내용
## 4. 기존 기술 대비 차별점 및 제약사항 (Comparison & Limitations)
제약 내용
## 5. 결론 및 적용/고려 사항 (Key Takeaways)
결론 내용
"""
        preamble, sections = client_service.split_tech_report_sections(report)
        self.assertEqual(preamble, "# 기술 보고서")
        self.assertEqual(len(sections), 5)
        self.assertTrue(sections[0].startswith("## 1."))
        self.assertTrue(sections[4].startswith("## 5."))

    def test_page_estimate_is_used_when_pdf_is_unavailable(self) -> None:
        pages, method = client_service.tech_report_page_count(
            "가" * 3601,
            Path("missing.pdf"),
            False,
        )
        self.assertEqual((pages, method), (3, "character-estimate"))

    def test_timeout_grows_ten_percent_and_resets_after_success(self) -> None:
        config = {
            "server_base_url": "http://model.test",
            "generate_path": "/api/generate",
            "status_path": "/api/status",
            "request_timeout_seconds": 100,
            "user_id": "",
            "password": "",
            "model": "model-a",
            "keep_alive": "1m",
            "num_ctx": 8192,
            "cloud_model_enabled": False,
            "agent_workers": [],
        }
        observed_timeouts = []

        def timeout_then_succeed(_config, _url, _payload, timeout):
            observed_timeouts.append(timeout)
            if len(observed_timeouts) <= 2:
                raise TimeoutError("backend timed out")
            return {"response": "ok"}

        with (
            patch.object(client_service, "invoke_model_request", side_effect=timeout_then_succeed),
            patch.object(client_service, "wait_for_model_queue_slot", return_value=None),
        ):
            self.assertEqual(client_service.call_model(config, "write report"), "ok")

        with patch.object(
            client_service,
            "invoke_model_request",
            side_effect=lambda _config, _url, _payload, timeout: (
                observed_timeouts.append(timeout) or {"response": "reset"}
            ),
        ):
            self.assertEqual(client_service.call_model(config, "next prompt"), "reset")

        self.assertEqual(observed_timeouts, [100, 110, 121, 100])
        self.assertEqual(client_service.next_model_timeout(280), 300)
        self.assertEqual(client_service.next_model_timeout(300), 300)

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

    def test_reads_utf8_txt_source_without_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "article.txt"
            source.write_text("Physical AI 데이터센터 기술 구조와 운영 원리", encoding="utf-8")

            text, metadata = client_service.read_tech_report_source(source, config={})

        self.assertIn("Physical AI", text)
        self.assertEqual(metadata["source_type"], "txt")
        self.assertEqual(metadata["ocr_engine"], "not-used")
        self.assertEqual(metadata["total_characters"], len(text))

    def test_accepts_txt_path_and_builds_twenty_page_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            source.write_text("기술 원문", encoding="utf-8")

            selected = client_service.resolve_tech_report_pdf(str(source))
            prompt = client_service.build_tech_report_prompt(selected, "기술 원문")

        self.assertEqual(selected, source.resolve())
        self.assertIn("형식: TXT", prompt)
        self.assertIn("약 20페이지", prompt)
        self.assertIn("기술 원문", prompt)

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

    def test_unknown_target_switches_to_different_model_worker(self) -> None:
        fallback = {
            "name": "fallback",
            "server_base_url": "http://fallback.test",
            "generate_path": "/api/generate",
            "status_path": "/api/status",
            "request_timeout_seconds": 1,
            "user_id": "",
            "password": "",
            "model": "model-b",
            "keep_alive": "6m",
            "num_ctx": 8192,
            "cloud_model_enabled": False,
        }
        config = {
            "name": "primary",
            "server_base_url": "http://primary.test",
            "generate_path": "/api/generate",
            "status_path": "/api/status",
            "request_timeout_seconds": 1,
            "user_id": "",
            "password": "",
            "model": "model-a",
            "keep_alive": "6m",
            "num_ctx": 8192,
            "cloud_model_enabled": False,
            "model_retry_wait_seconds": 1,
            "model_retry_prompt_after_failures": 20,
            "agent_workers": [fallback],
        }
        invoked_models = []

        def invoke(active_config, _url, payload, _timeout):
            invoked_models.append((active_config["model"], payload["model"]))
            if len(invoked_models) == 1:
                raise TimeoutError("primary timeout")
            return {"response": "ok"}

        with (
            patch.object(client_service, "invoke_model_request", side_effect=invoke),
            patch.object(
                client_service,
                "model_server_retry_status",
                side_effect=[
                    {
                        "available_targets": None,
                        "queue_empty": True,
                        "status": "model-a",
                        "model": "model-a",
                        "idle_targets": 1,
                        "active_requests": 0,
                        "pending_prompts": 0,
                    },
                    {
                        "available_targets": 1,
                        "queue_empty": True,
                        "status": "model-b",
                        "model": "model-b",
                        "idle_targets": 1,
                        "active_requests": 0,
                        "pending_prompts": 0,
                    },
                ],
            ),
        ):
            result = client_service.call_model(
                config,
                "read image",
                label="tech-report-ocr-page-1",
                images=["ZmFrZS1wbmc="],
            )

        self.assertEqual(result, "ok")
        self.assertEqual(
            invoked_models,
            [("model-a", "model-a"), ("model-b", "model-b")],
        )

    def test_unknown_target_without_fallback_does_not_resend(self) -> None:
        status = {
            "available_targets": None,
            "queue_empty": True,
            "status": "model-a",
            "model": "model-a",
            "idle_targets": 1,
            "active_requests": 0,
            "pending_prompts": 0,
        }
        with patch.object(
            client_service,
            "model_server_retry_status",
            return_value=status,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "prompt was not resent",
            ):
                client_service.wait_for_model_queue_slot(
                    {"model": "model-a", "server_base_url": "http://primary.test"},
                    "tech-report-ocr-page-1",
                    1,
                    "timeout",
                    fallback_workers=[],
                )

    def test_retry_status_does_not_treat_target_without_availability_as_idle(self) -> None:
        remote_status = {
            "model": "model-a",
            "status_url": "http://router.test/api/status",
            "raw": {
                "targets": [{"id": "target-a", "enabled": True}],
                "metrics": {
                    "target-a": {
                        "status": "ok",
                        "active_requests": 0,
                        "pending_queue": 0,
                    }
                },
            },
        }
        with patch.object(
            client_service,
            "fetch_remote_status",
            return_value=remote_status,
        ):
            status = client_service.model_server_retry_status(
                {"model_retry_status_timeout_seconds": 1}
            )

        self.assertIsNone(status["available_targets"])
        self.assertEqual(status["idle_targets"], 0)
        self.assertFalse(status["queue_empty"])


if __name__ == "__main__":
    unittest.main()
