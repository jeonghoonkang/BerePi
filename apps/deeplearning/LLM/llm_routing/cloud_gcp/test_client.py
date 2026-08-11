import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from cloud_gcp.client import GoogleAIStudioClient


class _Response:
    def __init__(self, data):
        self.buffer = BytesIO(json.dumps(data).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.buffer.read()


class GoogleAIStudioClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.config = Path(self.tempdir.name) / "settings.json"
        self.config.write_text(json.dumps({
            "api_key": "test-key",
            "model_id": "gemma-4-31b-it",
            "generation_config": {"maxOutputTokens": 64, "thinkingLevel": "minimal"},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_generate_calls_ai_studio_generate_content(self) -> None:
        client = GoogleAIStudioClient(self.config)
        response = _Response({
            "candidates": [{"content": {"parts": [{"text": "studio reply"}]}}],
            "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 2},
        })
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = client.generate({"prompt": "hello"}, 10)

        self.assertEqual(result["response"], "studio reply")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("/v1beta/models/gemma-4-31b-it:generateContent", request.full_url)
        self.assertEqual(request.headers["X-goog-api-key"], "test-key")
        self.assertEqual(body["contents"], [{"role": "user", "parts": [{"text": "hello"}]}])
        self.assertEqual(body["generationConfig"], {
            "maxOutputTokens": 64,
            "thinkingConfig": {"thinkingLevel": "minimal"},
        })

    def test_system_and_assistant_messages_are_converted(self) -> None:
        contents, system = GoogleAIStudioClient._contents({"messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": "Next question"},
        ]})
        self.assertEqual(system, {"parts": [{"text": "Be concise"}]})
        self.assertEqual(contents[0]["role"], "model")
        self.assertEqual(contents[1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
