import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pulsedav as dav


class DiskAlertTests(unittest.TestCase):
    def test_slots_and_retries(self):
        settings = {'telegram': {'enabled': True}}
        snapshot = {'hostname': 'test', 'disk_alerts': ['- /: 96%']}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(dav, 'DISK_ALERT_STATE_PATH', Path(directory) / 'alert.json'), \
             patch.object(dav, 'send_telegram_report', return_value={'status': 'sent'}) as send, \
             patch.object(dav, 'datetime') as clock:
            for day, hour, expected in [(12, 8, 'sent'), (12, 9, 'already_sent'),
                                        (12, 12, 'sent'), (12, 23, 'already_sent'),
                                        (13, 0, 'sent')]:
                clock.now.return_value = datetime(2026, 10, day, hour, tzinfo=dav.SEOUL)
                self.assertEqual(dav.send_disk_alert(settings, snapshot)['status'], expected)
            self.assertEqual(send.call_count, 3)
            self.assertEqual(dav.send_disk_alert(settings, {'disk_alerts': []})['status'], 'not_needed')
            self.assertEqual(dav.send_disk_alert({}, snapshot)['status'], 'disabled')
            clock.now.return_value = datetime(2026, 10, 13, 12, tzinfo=dav.SEOUL)
            send.return_value = {'status': 'failed'}
            self.assertEqual(dav.send_disk_alert(settings, snapshot)['status'], 'failed')
            send.return_value = {'status': 'sent'}
            self.assertEqual(dav.send_disk_alert(settings, snapshot)['status'], 'sent')


if __name__ == '__main__':
    unittest.main()
