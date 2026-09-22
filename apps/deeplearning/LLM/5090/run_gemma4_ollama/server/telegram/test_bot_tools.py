import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bot


class TelegramWritingToolCommandTests(unittest.TestCase):
    def test_parse_boost_command(self):
        self.assertEqual(bot.parse_boost_command(""), {"dry_run": False})
        self.assertEqual(
            bot.parse_boost_command('--dry-run "주간 회의록.md"'),
            {"dry_run": True, "file": "주간 회의록.md"},
        )
        with self.assertRaisesRegex(ValueError, "지원하지 않는"):
            bot.parse_boost_command("--unknown")

    def test_parse_findm_command(self):
        self.assertEqual(
            bot.parse_findm_command('--page-size 7 --author 7 --room=-1001 --topic 42 "서버 연동"'),
            {"query": "서버 연동", "page_size": 7, "author": "7", "room": "-1001", "topic": "42"},
        )
        with self.assertRaisesRegex(ValueError, "검색어"):
            bot.parse_findm_command("--page-size 7")
        with self.assertRaisesRegex(ValueError, "--author"):
            bot.parse_findm_command("--author")

    def test_allom_identity_uses_current_room_topic_and_author(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=-1001234567890),
            effective_message=SimpleNamespace(message_thread_id=42),
            effective_user=SimpleNamespace(id=7, username="alice", first_name="Alice", last_name=""),
        )

        self.assertEqual(
            bot.telegram_allom_identity(update),
            {
                "room": "-1001234567890",
                "topic": "42",
                "author": "7",
                "author_name": "@alice",
            },
        )

    def test_tool_payload_keeps_credentials_outside_arguments(self):
        with (
            patch.object(bot, "GEMMA4_USER_ID", "operator"),
            patch.object(bot, "GEMMA4_PASSWORD", "secret"),
        ):
            payload = bot.writing_tool_payload("allom", content="메모")

        self.assertEqual(payload["tool"], "allom")
        self.assertEqual(payload["arguments"], {"content": "메모"})
        self.assertEqual(payload["user_id"], "operator")
        self.assertEqual(payload["password"], "secret")

    def test_tool_result_text_contains_command_output(self):
        text = bot.writing_tool_result_text(
            {"tool": "list", "elapsed_seconds": 0.25, "stdout": "파일 목록", "stderr": ""}
        )
        self.assertIn("[list 완료] 0.25초", text)
        self.assertIn("파일 목록", text)

    def test_prompt_reply_includes_safe_telegram_room_summary(self):
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(
                id=-1001234567890,
                type=bot.ChatType.SUPERGROUP,
                title="LLM\n운영방",
            ),
            effective_message=SimpleNamespace(message_thread_id=42),
        )
        context = SimpleNamespace(bot=SimpleNamespace(username="berepi_gemma_bot"))

        text = bot.append_telegram_response_summary("답변", update, context)

        self.assertIn("답변", text)
        self.assertIn("[Telegram]", text)
        self.assertIn("Chat: 슈퍼그룹 (LLM 운영방)", text)
        self.assertIn("Room ID: -1001234567890:42", text)
        self.assertIn("Bot: @berepi_gemma_bot", text)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", text)
        self.assertNotIn("password", text)


if __name__ == "__main__":
    unittest.main()
