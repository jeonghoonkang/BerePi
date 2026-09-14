import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import server


class OllamaCompatibilityTests(unittest.TestCase):
    def test_index_contains_conversation_history_controls_and_tab(self) -> None:
        html = server.INDEX_HTML

        self.assertIn('id="rememberHistory" type="checkbox"', html)
        self.assertIn('data-tab="historyPanel"', html)
        self.assertIn('id="conversationHistoryPaths"', html)
        self.assertIn('id="conversationHistoryItems"', html)
        self.assertIn("remember_history: Boolean(rememberHistory.checked)", html)
        self.assertIn("/api/conversation-history/items?page=", html)

    def test_conversation_history_rollover_total_cap_and_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "conversation.json"
            backup_path = Path(temp_dir) / "conversation_backup.txt"
            current = [
                {"role": "user", "content": f"current-{index}"}
                for index in range(server.CONVERSATION_HISTORY_LIMIT)
            ]
            backup = [
                {"role": "assistant", "content": f"backup-{index}"}
                for index in range(server.CONVERSATION_HISTORY_BACKUP_LIMIT)
            ]
            with (
                patch.object(server, "CONVERSATION_HISTORY_FILE", current_path),
                patch.object(server, "CONVERSATION_HISTORY_BACKUP_FILE", backup_path),
            ):
                server.save_conversation_history(current)
                server.save_conversation_history_backup(backup)
                result = server.append_conversation_history(
                    [
                        {"role": "user", "content": "new-user"},
                        {"role": "assistant", "content": "new-assistant"},
                    ]
                )
                first_page = server.conversation_history_page_payload(1)
                last_page = server.conversation_history_page_payload(400)

                self.assertEqual(result["current_count"], 1000)
                self.assertEqual(result["backup_count"], 9000)
                self.assertEqual(result["total_count"], 10000)
                self.assertEqual(result["current_path"], str(current_path))
                self.assertEqual(result["backup_path"], str(backup_path))
                self.assertEqual(len(first_page["items"]), 25)
                self.assertEqual(first_page["items"][0]["content"], "new-assistant")
                self.assertEqual(first_page["page_size"], 25)
                self.assertEqual(last_page["page"], 400)
                self.assertEqual(len(last_page["items"]), 25)
                self.assertEqual(
                    len(backup_path.read_text(encoding="utf-8").splitlines()),
                    9000,
                )

    def test_conversation_prompt_is_model_independent_role_transcript(self) -> None:
        prompt = server.conversation_prompt(
            [
                {"role": "user", "content": "My name is Bere."},
                {"role": "assistant", "content": "Understood."},
            ],
            "What is my name?",
        )

        self.assertEqual(
            prompt,
            "user: My name is Bere.\nassistant: Understood.\nuser: What is my name?",
        )

    def test_history_is_attached_when_the_queued_prompt_executes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "conversation.json"
            backup_path = Path(temp_dir) / "conversation_backup.txt"
            with (
                patch.object(server, "CONVERSATION_HISTORY_FILE", current_path),
                patch.object(server, "CONVERSATION_HISTORY_BACKUP_FILE", backup_path),
            ):
                server.save_conversation_history(
                    [{"role": "assistant", "content": "latest answer"}]
                )
                payload = server.prompt_payload_for_execution(
                    {
                        "model": "model-a",
                        "prompt": "next question",
                        "_remember_history": True,
                        "_history_user_prompt": "next question",
                    }
                )

        self.assertEqual(
            payload["prompt"],
            "assistant: latest answer\nuser: next question",
        )

    def test_ollama_generate_does_not_forward_history_metadata(self) -> None:
        with (
            patch.object(server, "request_json", return_value={"response": "ok"}) as request,
            patch.object(server, "read_selected_gpu", return_value="auto"),
            patch.object(server, "list_gpus", return_value=([], "")),
            patch.object(server, "server_ip", return_value="127.0.0.1"),
        ):
            server.run_ollama_generate(
                {
                    "model": "gemma4:31b",
                    "prompt": "hello",
                    "stream": False,
                    "_remember_history": True,
                    "_history_user_prompt": "hello",
                }
            )

        backend_payload = request.call_args.kwargs["payload"]
        self.assertNotIn("_remember_history", backend_payload)
        self.assertNotIn("_history_user_prompt", backend_payload)

    def test_successful_result_appends_user_and_assistant_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "conversation.json"
            backup_path = Path(temp_dir) / "conversation_backup.txt"
            result = {
                "model": "model-b",
                "response": "raw response",
                "visible_response": "visible response",
            }
            with (
                patch.object(server, "CONVERSATION_HISTORY_FILE", current_path),
                patch.object(server, "CONVERSATION_HISTORY_BACKUP_FILE", backup_path),
            ):
                server.remember_conversation_result(
                    {
                        "_remember_history": True,
                        "_history_user_prompt": "hello",
                        "_history_user_id": "tester",
                    },
                    result,
                )
                messages = server.read_conversation_history()

        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "hello")
        self.assertEqual(messages[1]["content"], "visible response")
        self.assertEqual(messages[1]["model"], "model-b")

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
