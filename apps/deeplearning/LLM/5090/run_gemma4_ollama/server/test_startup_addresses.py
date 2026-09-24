import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import server


class StartupAddressTests(unittest.TestCase):
    def output(self, host):
        stream = io.StringIO()
        with patch.object(server, "ifconfig_ipv4_addresses", return_value=[
            {"interface": "en0", "ip": "192.168.0.25"},
            {"interface": "en1", "ip": "10.0.0.5"},
        ]), redirect_stdout(stream):
            server.print_service_addresses(host, 8083)
        return stream.getvalue()

    def test_wildcard_lists_network_urls_with_actual_port(self):
        output = self.output("0.0.0.0")
        self.assertIn("http://192.168.0.25:8083", output)
        self.assertIn("http://10.0.0.5:8083", output)
        self.assertIn("http://127.0.0.1:8083", output)
        self.assertNotIn("http://0.0.0.0", output)

    def test_loopback_does_not_advertise_network_access(self):
        output = self.output("127.0.0.1")
        self.assertIn("192.168.0.25", output)
        self.assertNotIn("Network URL:", output)

    def test_specific_bind_only_advertises_matching_interface(self):
        output = self.output("10.0.0.5")
        self.assertIn("http://10.0.0.5:8083", output)
        self.assertNotIn("http://192.168.0.25", output)

    def test_linux_ip_fallback_excludes_loopback(self):
        with patch.object(server.subprocess, "check_output", side_effect=[
            FileNotFoundError(),
            "1: lo    inet 127.0.0.1/8 scope host lo\n"
            "2: eth0    inet 192.168.0.25/24 scope global eth0\n",
        ]):
            self.assertEqual(server.ifconfig_ipv4_addresses(), [
                {"interface": "eth0", "ip": "192.168.0.25"},
            ])

    def test_no_network_interfaces(self):
        with patch.object(server, "ifconfig_ipv4_addresses", return_value=[]), \
                redirect_stdout(io.StringIO()) as output:
            server.print_service_addresses("0.0.0.0", 8082)
        self.assertIn("no non-loopback address detected", output.getvalue())


if __name__ == "__main__":
    unittest.main()
