import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pulsedav
from test_uptime_display import UptimeDisplayTests


class MacAddressTests(unittest.TestCase):
    def test_physical_wired_ports_exclude_virtual_wifi_and_invalid_macs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, physical, wireless, kind, mac in (
                ('eth0', True, False, '1', 'AA:BB:CC:DD:EE:FF'),
                ('enp2s0', True, False, '1', '12:34:56:78:9a:bc'),
                ('docker0', False, False, '1', '12:34:56:78:9a:bc'),
                ('veth123', False, False, '1', '12:34:56:78:9a:bc'),
                ('wlan0', True, True, '1', '12:34:56:78:9a:bc'),
                ('lo', False, False, '772', '00:00:00:00:00:00'),
                ('bad0', True, False, '1', 'invalid'),
            ):
                device = root / name
                device.mkdir()
                if physical:
                    (device / 'device').mkdir()
                if wireless:
                    (device / 'wireless').mkdir()
                (device / 'type').write_text(kind)
                (device / 'address').write_text(mac)
            with patch.object(pulsedav.platform, 'system', return_value='Linux'), \
                 patch.object(pulsedav, 'Path', return_value=root):
                self.assertEqual(pulsedav.get_physical_nic_macs(), [
                    {'interface': 'enp2s0', 'mac_address': '12:34:56:78:9a:bc'},
                    {'interface': 'eth0', 'mac_address': 'aa:bb:cc:dd:ee:ff'},
                ])

    def test_macos_physical_ethernet_ports(self):
        output = ('Hardware Port: Ethernet\nDevice: en1\nEthernet Address: AA:BB:CC:DD:EE:FF\n\n'
                  'Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: 12:34:56:78:9a:bc\n\n'
                  'Hardware Port: Bluetooth PAN\nDevice: en2\nEthernet Address: 12:34:56:78:9a:bc\n')
        with patch.object(pulsedav.platform, 'system', return_value='Darwin'), \
             patch.object(pulsedav, 'run_command', return_value=output):
            self.assertEqual(pulsedav.get_physical_nic_macs(), [
                {'interface': 'en1', 'mac_address': 'aa:bb:cc:dd:ee:ff'}])

    def test_report_includes_physical_ports(self):
        original = pulsedav.format_markdown

        def render(settings, snapshot, *args):
            settings['include']['network'] = True
            snapshot['network']['detail'] = 'network details'
            snapshot['network']['physical_nics'] = [
                {'interface': 'eth0', 'mac_address': 'aa:bb:cc:dd:ee:ff'},
                {'interface': 'enp2s0', 'mac_address': '12:34:56:78:9a:bc'},
            ]
            return original(settings, snapshot, *args)

        with patch.object(pulsedav, 'format_markdown', side_effect=render):
            report = UptimeDisplayTests().report(60)
        self.assertIn('- eth0: aa:bb:cc:dd:ee:ff', report)
        self.assertIn('- enp2s0: 12:34:56:78:9a:bc', report)

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
