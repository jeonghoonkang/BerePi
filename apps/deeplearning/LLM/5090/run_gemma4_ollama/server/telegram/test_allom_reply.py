import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import bot


class AllomReplyTests(unittest.IsolatedAsyncioTestCase):
    def update(self, text, original=None):
        message = NS(text=text, reply_to_message=original, message_thread_id=42,
                     reply_text=AsyncMock())
        return NS(message=message, effective_message=message,
                  effective_chat=NS(id=-1001),
                  effective_user=NS(id=7, username='saver'))

    def original(self, **changes):
        values = dict(text='첫째 줄\n둘째 줄\n\n마지막 문단', caption=None,
                      chat=NS(id=-1001), message_id=99,
                      from_user=NS(id=8, username='writer', full_name='Writer'), sender_chat=None)
        return NS(**dict(values, **changes))

    async def test_reply_preserves_original_and_saver_identity(self):
        original = self.original()
        update = self.update('/allom', original)
        with patch.object(bot, 'execute_writing_tool', new_callable=AsyncMock) as execute:
            await bot.allom_command(update, None)
        args = execute.await_args.args[3]
        self.assertEqual(args['author'], '7')
        self.assertEqual(args['room'], '-1001')
        self.assertEqual(args['topic'], '42')
        self.assertIn(original.text, args['content'])
        self.assertIn('"author_id": 8', args['content'])
        self.assertIn('"message_id": 99', args['content'])
        self.assertNotIn('## 추가 메모', args['content'])
        self.assertEqual(args['content'], bot.allom_message_content(update))

    async def test_reply_with_note_and_caption(self):
        update = self.update('/allom@mybot 추가\n메모', self.original(text=None, caption='사진 설명\n두 줄'))
        result = bot.allom_message_content(update)
        self.assertIn('## 원본 메시지\n\n사진 설명\n두 줄', result)
        self.assertIn('## 추가 메모\n\n추가\n메모', result)

    async def test_plain_allom_unchanged(self):
        update = self.update('/allom 일반\n\n메모')
        self.assertEqual(bot.allom_message_content(update), '일반\n\n메모')

    async def test_empty_reply_and_empty_command_do_not_save(self):
        updates = [self.update('/allom'),
                   self.update('/allom', self.original(text=None)),
                   self.update('/allom 추가', self.original(text=None))]
        for update in updates:
            with patch.object(bot, 'execute_writing_tool', new_callable=AsyncMock) as execute:
                await bot.allom_command(update, None)
                execute.assert_not_awaited()
            update.message.reply_text.assert_awaited_once()

    async def test_channel_sender_and_missing_author(self):
        channel = self.original(sender_chat=NS(id=-1002, title='Channel', username='channel'))
        content = bot.allom_message_content(self.update('/allom', channel))
        self.assertIn('"author_id": -1002', content)
        self.assertIn('"author_name": "Channel"', content)
        unknown = self.original(from_user=None)
        self.assertIn('"author_id": null', bot.allom_message_content(self.update('/allom', unknown)))

    async def test_unauthorized_user_cannot_save_reply(self):
        update = self.update('/allom', self.original())
        with patch.object(bot, 'is_allowed_user', return_value=False), patch.object(bot, 'call_writing_tool') as call:
            await bot.allom_command(update, None)
            call.assert_not_called()
        update.message.reply_text.assert_not_awaited()
