import unittest
from unittest.mock import patch

import pulsedav
from test_uptime_display import UptimeDisplayTests


class MacAddressTests(unittest.TestCase):
    def test_linux_default_interface(self):
        with patch.object(pulsedav.platform, 'system', return_value='Linux'), \
             patch.object(pulsedav, 'run_command', side_effect=[
                 'default via 192.168.1.1 dev eth0 proto dhcp\n',
                 '2: eth0: <UP>\n    link/ether AA:BB:CC:DD:EE:FF brd ff:ff:ff:ff:ff:ff',
             ]) as run:
            self.assertEqual(pulsedav.get_mac_address(), 'aa:bb:cc:dd:ee:ff')
            self.assertEqual(run.call_args.args[0], ['ip', 'link', 'show', 'dev', 'eth0'])

    def test_macos_default_interface(self):
        with patch.object(pulsedav.platform, 'system', return_value='Darwin'), \
             patch.object(pulsedav, 'run_command', side_effect=[
                 '   gateway: 192.168.1.1\n interface: en0\n',
                 '\tether 12:34:56:78:9a:bc\n',
             ]) as run:
            self.assertEqual(pulsedav.get_mac_address(), '12:34:56:78:9a:bc')
            self.assertEqual(run.call_args.args[0], ['ifconfig', 'en0'])

    def test_missing_route_or_mac(self):
        for system in ['Linux', 'Darwin']:
            with self.subTest(system=system), \
                 patch.object(pulsedav.platform, 'system', return_value=system), \
                 patch.object(pulsedav, 'run_command', return_value=''):
                self.assertEqual(pulsedav.get_mac_address(), '확인 실패')
        with patch.object(pulsedav.platform, 'system', return_value='Linux'), \
             patch.object(pulsedav, 'run_command', side_effect=[
                 'default dev tun0', 'link/none']):
            self.assertEqual(pulsedav.get_mac_address(), '확인 실패')

    def test_report_includes_mac(self):
        original = pulsedav.format_markdown

        def render(settings, snapshot, *args):
            snapshot['network']['mac_address'] = 'aa:bb:cc:dd:ee:ff'
            return original(settings, snapshot, *args)

        with patch.object(pulsedav, 'format_markdown', side_effect=render):
            report = UptimeDisplayTests().report(60)
        self.assertIn('- MAC 주소: aa:bb:cc:dd:ee:ff', report)


if __name__ == '__main__':
    unittest.main()
