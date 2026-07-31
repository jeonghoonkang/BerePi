from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from extract_picture_pages import classify_page, load_server_config, select_ollama_target, select_pdf_files


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._data


class FakeSession:
    def __init__(self, targets: list[dict]) -> None:
        self.targets = targets

    def get(self, *_args, **_kwargs) -> FakeResponse:
        return FakeResponse({"targets": self.targets})


class FakePostResponse:
    ok = True
    reason = "OK"
    text = ""

    def json(self) -> dict:
        return {"response": '{"has_picture": true, "reason": "chart"}'}


class CapturingSession:
    def __init__(self) -> None:
        self.payload: dict = {}

    def post(self, *_args, **kwargs) -> FakePostResponse:
        self.payload = kwargs["json"]
        return FakePostResponse()


class InputFileSelectionTests(unittest.TestCase):
    def test_target_selection_skips_unavailable_and_excluded_targets(self) -> None:
        session = FakeSession(
            [
                {"id": "down", "api_type": "ollama", "model": "gemma4:31b", "available_targets": 0, "dispatch_eligible": False},
                {"id": "first", "api_type": "ollama", "model": "gemma4:31b", "available_targets": 1, "dispatch_eligible": True},
                {"id": "fallback", "api_type": "ollama", "model": "other-model", "available_targets": 2, "dispatch_eligible": True},
            ]
        )

        selected = select_ollama_target(
            session,
            server_url="http://router.example",
            password="secret",
            requested_model="gemma4:31b",
            explicit_target_id=None,
            excluded_target_ids={"first"},
        )

        self.assertEqual(selected, ("fallback", "other-model", "ollama"))

    def test_vllm_uses_openai_multimodal_image_message(self) -> None:
        session = CapturingSession()

        decision = classify_page(
            session,
            server_url="http://router.example",
            password="secret",
            model="vision-model",
            target_id="vllm-ready",
            api_type="vllm",
            jpeg_bytes=b"jpeg",
            timeout=5,
        )

        content = session.payload["messages"][0]["content"]
        self.assertTrue(decision.has_picture)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("images", session.payload)

    def test_selects_available_vllm_target(self) -> None:
        session = FakeSession(
            [{"id": "vllm-ready", "api_type": "vllm", "model": "vision-model", "available_targets": 1, "dispatch_eligible": True}]
        )

        selected = select_ollama_target(
            session,
            server_url="http://router.example",
            password="secret",
            requested_model="vision-model",
            explicit_target_id=None,
        )

        self.assertEqual(selected, ("vllm-ready", "vision-model", "vllm"))

    def test_explicit_unavailable_target_is_rejected(self) -> None:
        session = FakeSession(
            [{"id": "down", "api_type": "ollama", "model": "gemma4:31b", "available_targets": 0, "dispatch_eligible": False}]
        )

        with self.assertRaisesRegex(ValueError, "현재 사용할 수 없습니다"):
            select_ollama_target(
                session,
                server_url="http://router.example",
                password="secret",
                requested_model="gemma4:31b",
                explicit_target_id="down",
            )

    def test_loads_server_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "server.json"
            config_path.write_text(
                '{"server_url":"http://router.example:4004","password_env":"ROUTER_PASSWORD"}',
                encoding="utf-8",
            )

            config = load_server_config(config_path)

        self.assertEqual(config["server_url"], "http://router.example:4004")
        self.assertEqual(config["password_env"], "ROUTER_PASSWORD")

    def test_selects_one_pdf_by_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            first = input_dir / "first.pdf"
            second = input_dir / "second.pdf"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            selected = select_pdf_files(input_dir, Path("second.pdf"))

        self.assertEqual(selected, [second.resolve()])

    def test_rejects_file_outside_input_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            input_dir.mkdir()
            outside = root / "outside.pdf"
            outside.write_bytes(b"outside")

            with self.assertRaisesRegex(ValueError, "input 디렉토리 내부"):
                select_pdf_files(input_dir, outside)

    def test_without_selection_returns_all_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            first = input_dir / "a.pdf"
            second = input_dir / "b.pdf"
            first.write_bytes(b"a")
            second.write_bytes(b"b")

            selected = select_pdf_files(input_dir, None)

        self.assertEqual(selected, [first.resolve(), second.resolve()])


if __name__ == "__main__":
    unittest.main()
