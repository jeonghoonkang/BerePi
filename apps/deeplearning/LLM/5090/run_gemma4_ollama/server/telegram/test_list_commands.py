import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot
from telegram.error import RetryAfter


class ListCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_modes_are_forwarded_and_invalid_input_is_rejected(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
        context = object()
        for text, mode in (("", "recent"), ("all", "all"), ("full", "full")):
            with patch.object(bot, "command_argument_text", return_value=text), patch.object(bot, "execute_writing_tool", new_callable=AsyncMock) as execute:
                await bot.list_command(update, context)
                execute.assert_awaited_once_with(update, context, "list", {"mode": mode})
        with patch.object(bot, "command_argument_text", return_value="bad value"), patch.object(bot, "execute_writing_tool", new_callable=AsyncMock) as execute:
            await bot.list_command(update, context)
            execute.assert_not_awaited()

    async def test_full_reply_preserves_all_chunks_and_retries_rate_limit(self):
        progress = SimpleNamespace(edit_text=AsyncMock(side_effect=[RetryAfter(1), None]))
        message = SimpleNamespace(reply_text=AsyncMock(return_value=progress))
        update = SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=1))
        context = SimpleNamespace(bot=SimpleNamespace(send_chat_action=AsyncMock()))
        result = {"tool": "list", "stdout": "entry\n" * 2000}
        expected = bot.split_message(bot.writing_tool_result_text(result))
        with patch.object(bot, "is_allowed_user", return_value=True), patch.object(bot, "call_writing_tool", return_value=result), patch.object(bot.asyncio, "sleep", new_callable=AsyncMock):
            await bot.execute_writing_tool(update, context, "list", {"mode": "full"})
        self.assertEqual(progress.edit_text.await_count, 2)
        self.assertEqual(progress.edit_text.await_args.args[0], expected[0])
        self.assertEqual([call.args[0] for call in message.reply_text.await_args_list[1:]], expected[1:])
