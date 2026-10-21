import io
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from server_network import ServerNetwork, local_addresses, public_address


class ServerNetworkTests(unittest.TestCase):
    def test_local_addresses_exclude_loopback_and_include_default_route(self):
        entries = [(2, 2, 17, '', (ip, 0)) for ip in ['127.0.0.1', '192.168.1.10', '169.254.1.2', '0.0.0.0']]
        with patch('server_network.socket.getaddrinfo', return_value=entries), patch('server_network.socket.socket') as socket:
            socket.return_value.__enter__.return_value.getsockname.return_value = ('10.0.0.5', 1234)
            self.assertEqual(local_addresses(), ['10.0.0.5', '192.168.1.10'])
        with patch('server_network.socket.getaddrinfo', side_effect=OSError), patch('server_network.socket.socket', side_effect=OSError):
            self.assertEqual(local_addresses(), [])

    def test_public_lookup_validates_service_response(self):
        with patch('server_network.urlopen', return_value=io.BytesIO(b'8.8.8.8\n')) as lookup:
            self.assertEqual(public_address(), '8.8.8.8')
            self.assertEqual(lookup.call_args.kwargs['timeout'], 4)
        for value in [b'192.168.1.10', b'<html>error</html>', b'']:
            with patch('server_network.urlopen', return_value=io.BytesIO(value)), self.assertRaises(ValueError):
                public_address()

    def test_nonblocking_single_lookup_and_cached_result(self):
        service = ServerNetwork()
        entered, release = threading.Event(), threading.Event()
        def lookup():
            entered.set()
            release.wait(3)
            return '8.8.8.8'
        with patch('server_network.local_addresses', return_value=['192.168.1.10']), patch('server_network.public_address', side_effect=lookup) as public:
            first = service.get()
            self.assertTrue(first['refreshing'])
            self.assertTrue(entered.wait(2))
            for _ in range(10):
                self.assertTrue(service.get()['refreshing'])
            release.set()
            # Synchronize with the background thread without sleep-based timing assertions.
            for thread in threading.enumerate():
                if thread.name == 'photo-server-ip':
                    thread.join(3)
            result = service.get()
            self.assertEqual(result['external_ip'], '8.8.8.8')
            self.assertEqual(result['internal_ips'], ['192.168.1.10'])
            self.assertEqual(result['status'], 'ok')
            self.assertFalse(result['refreshing'])
            self.assertEqual(public.call_count, 1)

    def test_failure_keeps_internal_ip_and_retries_after_expiry(self):
        service = ServerNetwork()
        with patch('server_network.local_addresses', return_value=['10.0.0.5']), patch('server_network.public_address', side_effect=OSError):
            service.refresh()
        result = service.get()
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['internal_ips'], ['10.0.0.5'])
        self.assertIsNone(result['external_ip'])
        with patch('server_network.local_addresses', return_value=['10.0.0.6']), patch('server_network.public_address', return_value='8.8.4.4'):
            service.expires = 0
            service.get()
            for thread in threading.enumerate():
                if thread.name == 'photo-server-ip':
                    thread.join(3)
            self.assertEqual(service.get()['external_ip'], '8.8.4.4')

    def test_page_endpoint_and_auth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(root, root, root / 'db')
            client = app.test_client()
            for page in ['/', '/jobs']:
                response = client.get(page)
                self.assertIn('내부 IP'.encode(), response.data)
                self.assertIn(b'server_network.js', response.data)
            with patch.object(app.extensions['server_network'], 'get', return_value={'internal_ips': ['10.0.0.5'], 'external_ip': '8.8.8.8', 'status': 'ok', 'refreshing': False}):
                response = client.get('/api/server-network')
                self.assertEqual(response.json['internal_ips'], ['10.0.0.5'])
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-password'}):
                    self.assertEqual(client.get('/api/server-network').status_code, 401)


if __name__ == '__main__':
    unittest.main()
