import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class HistoryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name in ('CONVERSATION_HISTORY_FILE', 'CONVERSATION_HISTORY_BACKUP_FILE', 'USER_PROMPT_HISTORY_FILE'):
            patcher = patch.object(server, name, Path(self.temp.name) / name)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.identity = server.request_history_identity(
            {'room_id': 'room-a', 'source': 'telegram', 'sender_id': '123'}, 'account', '192.0.2.1'
        )

    def test_identity_survives_result_rollover_and_prompt_log_rewrite(self):
        with patch.object(server, 'CONVERSATION_HISTORY_LIMIT', 1):
            server.remember_conversation_result(
                {'_remember_history': True, '_history_user_prompt': 'question', '_history_identity': self.identity},
                {'response': 'answer', 'model': 'test-model'},
            )
            for message in server.read_conversation_history_backup() + server.read_conversation_history():
                for key, value in self.identity.items():
                    self.assertEqual(message[key], value)
        server.remember_user_prompt('account', 'first', identity=self.identity)
        server.remember_user_prompt('account', 'second')
        first = server.read_user_prompt_history()[0]
        for key, value in self.identity.items():
            self.assertEqual(first[key], value)
        raw = json.loads(server.USER_PROMPT_HISTORY_FILE.read_text().splitlines()[0])
        self.assertEqual(raw['room_id'], 'room-a')

    def test_context_excludes_each_other_identity_and_legacy_records(self):
        messages = [{'role': 'assistant', 'content': 'same conversation', **self.identity}]
        for key in server.HISTORY_IDENTITY_FIELDS:
            messages.append({'role': 'assistant', 'content': 'must not leak', **self.identity, key: 'different'})
        messages.append({'role': 'assistant', 'content': 'legacy must not leak'})
        server.save_conversation_history(messages)
        result = server.prompt_payload_for_execution({
            '_remember_history': True, '_history_identity': self.identity, '_history_user_prompt': 'next'
        })
        self.assertEqual(result['prompt'], 'assistant: same conversation\nuser: next')

    def test_filters_apply_before_pagination_include_backup_and_legacy(self):
        server.save_conversation_history_backup([
            {'role': 'user', 'content': str(index), **self.identity} for index in range(30)
        ])
        server.save_conversation_history([
            {'role': 'assistant', 'content': 'other', **self.identity, 'user_id': 'other'},
            {'role': 'user', 'content': 'legacy'},
        ])
        result = server.conversation_history_page_payload(2, {'room_id': 'room-a', 'user_id': 'account'})
        self.assertEqual(result['total_count'], 30)
        self.assertEqual(result['backup_count'], 30)
        self.assertEqual(result['current_count'], 0)
        self.assertEqual(len(result['items']), 5)
        self.assertIn('other', result['filter_options']['user_id'])
        legacy = server.conversation_history_page_payload(1, {'room_id': ''})
        self.assertEqual([item['content'] for item in legacy['items']], ['legacy'])
        empty = server.conversation_history_page_payload(999, {'client_ip': 'missing'})
        self.assertEqual(empty['page'], 1)
        self.assertEqual(empty['items'], [])

    def test_ip_and_authenticated_account_are_server_supplied(self):
        identity = server.request_history_identity(
            {'client_ip': 'spoofed', 'user_id': 'spoofed', 'room_id': ' '}, 'real-user', '192.0.2.2'
        )
        self.assertEqual(identity['client_ip'], '192.0.2.2')
        self.assertEqual(identity['user_id'], 'real-user')
        self.assertEqual(identity['room_id'], 'default')


if __name__ == '__main__':
    unittest.main()
