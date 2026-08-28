import unittest
import urllib.error
from unittest.mock import patch

import server


class OllamaCompatibilityTests(unittest.TestCase):
    def test_index_contains_clipboard_and_upload_ocr_tabs(self) -> None:
        html = server.INDEX_HTML

        for element_id in (
            "ocrClipboardTab",
            "ocrUploadTab",
            "ocrClipboardPanel",
            "ocrUploadPanel",
            "ocrPasteZone",
            "runOcrClipboard",
            "runOcrUpload",
        ):
            self.assertIn(f'id="{element_id}"', html)

        self.assertIn('ocrPasteZone.addEventListener("paste"', html)
        self.assertIn('fetch("/api/generate"', html)

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

    def test_request_json_wraps_connection_refused(self) -> None:
        error = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

        with (
            patch.object(server.urllib.request, "urlopen", side_effect=error),
            self.assertRaisesRegex(
                RuntimeError,
                r"Ollama /api/tags connection failed:.*Connection refused",
            ),
        ):
            server.request_json("/api/tags", timeout=1)

    def test_status_payload_reports_backend_connection_failure(self) -> None:
        error = RuntimeError(
            "Ollama /api/tags connection failed: [Errno 111] Connection refused"
        )

        with patch.object(server, "list_ollama_models", side_effect=error):
            status = server.status_payload()

        self.assertFalse(status["ollama_reachable"])
        self.assertFalse(status["model_available"])
        self.assertEqual(status["models"], [])
        self.assertIn("Connection refused", status["ollama_error"])


if __name__ == "__main__":
    unittest.main()
