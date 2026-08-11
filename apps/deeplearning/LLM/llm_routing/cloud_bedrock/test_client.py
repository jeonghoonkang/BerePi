import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cloud_bedrock.client import BedrockClient


class BedrockClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.config = Path(self.tempdir.name) / "settings.json"
        self.config.write_text(json.dumps({
            "region": "us-east-1",
            "model_id": "amazon.nova-micro-v1:0",
            "inference_config": {"maxTokens": 64},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_converse_forwards_messages_and_normalizes_text(self) -> None:
        runtime = MagicMock()
        runtime.converse.return_value = {
            "output": {"message": {"content": [{"text": "cloud reply"}]}},
            "usage": {"inputTokens": 2, "outputTokens": 2},
        }
        client = BedrockClient(self.config)
        with patch.object(client, "_client", return_value=runtime):
            result = client.converse({"prompt": "hello"}, 10)

        self.assertEqual(result["response"], "cloud reply")
        runtime.converse.assert_called_once_with(
            modelId="amazon.nova-micro-v1:0",
            messages=[{"role": "user", "content": [{"text": "hello"}]}],
            inferenceConfig={"maxTokens": 64},
        )

    def test_system_message_uses_bedrock_system_field(self) -> None:
        messages, system = BedrockClient._messages({"messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "hello"},
        ]})
        self.assertEqual(system, [{"text": "Be concise"}])
        self.assertEqual(messages[0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
