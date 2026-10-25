import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot


class OcrConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = []
        self.context = SimpleNamespace(user_data={}, application=SimpleNamespace(create_task=self.create_task))
        remote = SimpleNamespace(file_path="/scan.pdf", download_as_bytearray=AsyncMock(return_value=b"%PDF-1.4\n"))
        self.document = SimpleNamespace(file_size=9, file_name="scan.pdf", mime_type="application/pdf", get_file=AsyncMock(return_value=remote))
        self.update = self.make_update(self.document)
        self.allowed = patch.object(bot, "is_allowed_user", return_value=True)
        self.prompt = patch.object(bot, "prompt_from_update", return_value="original request")
        self.allowed.start()
        self.prompt.start()

    def create_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    def make_update(self, document=None, room=1):
        return SimpleNamespace(
            effective_chat=SimpleNamespace(id=room, type="private"),
            effective_user=SimpleNamespace(id=7),
            message=SimpleNamespace(document=document, photo=[], reply_to_message=None,
                                    message_thread_id=None, reply_text=AsyncMock()))

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.prompt.stop()
        self.allowed.stop()

    async def test_file_waits_then_unmentioned_reply_uses_original_prompt(self):
        with patch.object(bot, "process_prompt", new_callable=AsyncMock) as process:
            await bot.handle_prompt(self.update, self.context)
            process.assert_not_awaited()
            self.assertIn("pdf", self.update.message.reply_text.call_args.args[0])
            reply = self.make_update()
            # Group confirmations do not need to mention the bot a second time.
            with (patch.object(bot, "prompt_from_update", return_value=""),
                  patch.object(bot, "message_text", return_value="OCR 실행"),
                  patch.object(bot, "bot_usernames", return_value=set())):
                await bot.handle_prompt(reply, self.context)
            args = process.call_args.args
            self.assertEqual(args[2], "original request")
            self.assertEqual(args[3]["ocr_reply"], "OCR 실행")
            self.assertEqual(args[3]["files"][0]["name"], "scan.pdf")
            self.assertFalse(self.context.user_data["ocr_pending"])

    async def test_no_and_timeout_send_without_opt_in(self):
        with patch.object(bot, "process_prompt", new_callable=AsyncMock) as process:
            await bot.handle_prompt(self.update, self.context)
            with (patch.object(bot, "message_text", return_value="아니요"),
                  patch.object(bot, "bot_usernames", return_value=set())):
                await bot.handle_prompt(self.make_update(), self.context)
            self.assertEqual(process.call_args.args[3]["ocr_reply"], "아니요")
            with patch.object(bot.asyncio, "sleep", new_callable=AsyncMock):
                await bot.handle_prompt(self.update, self.context)
                await self.tasks[-1]
            self.assertEqual(process.call_args.args[3]["ocr_reply"], "")
            self.assertEqual(process.await_count, 2)

    async def test_initial_ocr_request_sends_file_immediately(self):
        with (patch.object(bot, "process_prompt", new_callable=AsyncMock) as process,
              patch.object(bot, "prompt_from_update", return_value="첨부 파일 OCR 해주세요")):
            await bot.handle_prompt(self.update, self.context)
            process.assert_awaited_once()
            self.assertTrue(process.call_args.args[3]["ocr_reply"])
            self.assertEqual(process.call_args.args[2], "첨부 파일 OCR 해주세요")
            self.assertEqual(process.call_args.args[3]["files"][0]["name"], "scan.pdf")
            self.update.message.reply_text.assert_not_awaited()
            self.assertFalse(self.tasks)
            self.assertFalse(self.context.user_data["ocr_pending"])

    async def test_other_room_does_not_consume_pending_file(self):
        with patch.object(bot, "process_prompt", new_callable=AsyncMock):
            await bot.handle_prompt(self.update, self.context)
            await bot.handle_prompt(self.make_update(room=2), self.context)
            self.assertIn("1:0", self.context.user_data["ocr_pending"])


if __name__ == "__main__":
    unittest.main()
