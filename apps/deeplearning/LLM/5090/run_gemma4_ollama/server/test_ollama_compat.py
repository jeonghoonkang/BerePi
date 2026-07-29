import unittest
from unittest.mock import patch

import server


class OllamaCompatibilityTests(unittest.TestCase):
    def test_tags_payload_proxies_local_ollama_response(self) -> None:
        expected = {
            "models": [
                {
                    "name": "gemma4:31b",
                    "model": "gemma4:31b",
                    "size": 123,
                }
            ]
        }

        with patch.object(server, "request_json", return_value=expected) as request:
            result = server.ollama_tags_payload()

        self.assertEqual(result, expected)
        request.assert_called_once_with("/api/tags", timeout=5)

    def test_tags_payload_rejects_invalid_backend_response(self) -> None:
        with (
            patch.object(server, "request_json", return_value={"models": None}),
            self.assertRaisesRegex(RuntimeError, "models list"),
        ):
            server.ollama_tags_payload()


if __name__ == "__main__":
    unittest.main()
