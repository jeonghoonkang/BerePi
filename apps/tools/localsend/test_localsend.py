import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import localsend


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b'\x00\xffbinary' * 200000
        (self.root / '한글.bin').write_bytes(self.payload)
        (self.root / 'empty.txt').write_bytes(b'')
        self.files = localsend.collect_files([str(self.root)])
        self.uploads = {}
        self.cancelled = False
        self.reject = False
        self.fail_upload = False
        self.partial = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                url = urlparse(self.path)
                query = parse_qs(url.query)
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                status, result = 200, None
                if url.path.endswith('/prepare-upload'):
                    owner.assertEqual(query['pin'], ['123456'])
                    data = json.loads(body)
                    owner.assertEqual(data['info']['version'], '2.0')
                    owner.assertEqual(set(data['files']), set(owner.files))
                    owner.assertEqual(data['info']['protocol'], 'http')
                    if owner.reject:
                        status = 403
                    else:
                        ids = list(data['files'])[:1] if owner.partial else data['files']
                        result = dict(sessionId='session & 1', files={k: 'token &?' for k in ids})
                elif url.path.endswith('/upload'):
                    owner.assertEqual(query['sessionId'], ['session & 1'])
                    owner.assertEqual(query['token'], ['token &?'])
                    owner.uploads[query['fileId'][0]] = body
                    if owner.fail_upload:
                        status = 500
                elif url.path.endswith('/cancel'):
                    owner.cancelled = True
                else:
                    status = 404
                encoded = json.dumps(result).encode() if result is not None else b''
                self.send_response(status)
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def send(self):
        return localsend.send('127.0.0.1', self.server.server_port, 'http',
                              localsend.sender_info('Test'), self.files, '123456', 3)

    def test_binary_and_empty_file(self):
        self.assertEqual(self.send(), 2)
        for file_id, (path, _) in self.files.items():
            self.assertEqual(self.uploads[file_id], path.read_bytes())

    def test_partial_acceptance(self):
        self.partial = True
        self.assertEqual(self.send(), 1)
        self.assertEqual(len(self.uploads), 1)

    def test_rejection(self):
        self.reject = True
        with self.assertRaisesRegex(localsend.LocalSendError, '403'):
            self.send()
        self.assertFalse(self.uploads)

    def test_failed_upload_cancels_session(self):
        self.fail_upload = True
        with self.assertRaises(localsend.LocalSendError):
            self.send()
        self.assertTrue(self.cancelled)

    def test_duplicate_destination(self):
        with self.assertRaisesRegex(localsend.LocalSendError, 'Duplicate'):
            localsend.collect_files([str(self.root / 'empty.txt')] * 2)

    def test_missing_input(self):
        with self.assertRaises(localsend.LocalSendError):
            localsend.collect_files([str(self.root / 'missing')])


class DiscoveryTests(unittest.TestCase):
    def test_http_registration_callback(self):
        real_server = ThreadingHTTPServer
        servers = []

        def capture(*args, **kwargs):
            server = real_server(*args, **kwargs)
            servers.append(server)
            return server

        errors = []

        def register():
            import time
            deadline = time.monotonic() + 2
            while not servers and time.monotonic() < deadline:
                time.sleep(.01)
            try:
                localsend.request('127.0.0.1', servers[0].server_port, 'http',
                                  'register', dict(alias='Mac', fingerprint='peer',
                                                   port=53317, protocol='https'), 2)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=register)
        with patch.object(localsend, 'ThreadingHTTPServer', side_effect=capture):
            thread.start()
            peers = localsend.discover(localsend.sender_info('Test'), seconds=.5,
                                       interface='127.0.0.1', port=55319)
            thread.join()
        self.assertFalse(errors)
        self.assertEqual(peers[0]['alias'], 'Mac')
        self.assertEqual(peers[0]['protocol'], 'https')


if __name__ == '__main__':
    unittest.main()
