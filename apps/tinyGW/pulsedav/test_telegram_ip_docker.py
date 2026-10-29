import unittest
from unittest.mock import patch

import telegram_ip_docker as script


class TelegramIpDockerTests(unittest.TestCase):
    def test_report_includes_network_and_docker_failure(self):
        with patch.object(script, 'get_ip_route_default', return_value=('10.0.0.2', '10.0.0.1')), \
             patch.object(script, 'get_public_ip', return_value='203.0.113.1'), \
             patch.object(script, 'hostname', return_value='gateway'), \
             patch.object(script, 'get_docker_status', return_value='Docker 상태 확인 불가'):
            report = script.build_report()
        for value in ['10.0.0.2', '10.0.0.1', '203.0.113.1', 'gateway', 'Docker 상태 확인 불가']:
            self.assertIn(value, report)

    def test_dry_run_never_sends(self):
        with patch.object(script, 'build_report', return_value='preview'), \
             patch.object(script, 'send_telegram_report') as send, patch('builtins.print'):
            self.assertEqual(script.main(['--dry-run']), 0)
            send.assert_not_called()

    def test_long_report_chunks_and_config(self):
        with patch.object(script, 'build_report', return_value='x' * 4000), \
             patch.object(script, 'send_telegram_report', return_value={'status': 'sent'}) as send:
            self.assertEqual(script.main(['--telegram-config', '/tmp/bot.conf']), 0)
            self.assertEqual(send.call_count, 3)
            self.assertEqual(''.join(c.args[1] for c in send.call_args_list), 'x' * 4000)
            self.assertEqual(send.call_args.args[0]['telegram']['config_path'], '/tmp/bot.conf')

    def test_send_failure_returns_nonzero(self):
        with patch.object(script, 'build_report', return_value='status'), \
             patch.object(script, 'send_telegram_report', return_value={'status': 'failed'}):
            self.assertEqual(script.main([]), 1)
