import unittest
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
            bot.parse_findm_command('--page-size 7 "서버 연동"'),
            {"query": "서버 연동", "page_size": 7},
        )
        with self.assertRaisesRegex(ValueError, "검색어"):
            bot.parse_findm_command("--page-size 7")

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


if __name__ == "__main__":
    unittest.main()
