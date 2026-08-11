import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from cloud_gcp.client import GCPVertexClient


class _Response:
    def __init__(self, data):
        self.buffer = BytesIO(json.dumps(data).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.buffer.read()


class GCPVertexClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.config = Path(self.tempdir.name) / "settings.json"
        self.config.write_text(json.dumps({
            "project_id": "test-project",
            "location": "us-central1",
            "endpoint_id": "123456",
            "model_id": "google/gemma-4-31b-it",
            "inference_config": {"max_tokens": 64},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_generate_calls_vertex_chat_completions(self) -> None:
        client = GCPVertexClient(self.config)
        response = _Response({
            "choices": [{"message": {"content": "gcp reply"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2},
        })
        with (
            patch.object(client, "_access_token", return_value="token"),
            patch("urllib.request.urlopen", return_value=response) as urlopen,
        ):
            result = client.generate({"prompt": "hello"}, 10)

        self.assertEqual(result["response"], "gcp reply")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIn("/endpoints/123456/chat/completions", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bearer token")
        self.assertEqual(body["model"], "google/gemma-4-31b-it")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hello"}])


if __name__ == "__main__":
    unittest.main()
