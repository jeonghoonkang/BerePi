"""Regression tests for urllib authentication against a named DAV realm."""
import base64
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import HTTPBasicAuthHandler

from pulsedav import SimpleRequestException, SimpleSession, WebDAVConfig, ensure_remote_directories


class WebDAVAuthTests(unittest.TestCase):
    def test_default_credentials_match_nextcloud_realm(self):
        session = SimpleSession(WebDAVConfig('http://example.test:22080', '/dav', 'user', 'test-password'))
        handler = next(h for h in session.opener.handlers if isinstance(h, HTTPBasicAuthHandler))
        self.assertEqual(handler.passwd.find_user_password('Nextcloud', 'http://example.test:22080/dav/user'),
                         ('user', 'test-password'))
        self.assertEqual(handler.passwd.find_user_password('Nextcloud', 'http://other.test:22080/dav/user'),
                         (None, None))

    def test_propfind_retries_named_realm_and_rejects_bad_password(self):
        received = []
        expected = 'Basic ' + base64.b64encode(b'user:test-password').decode('ascii')

        class Handler(BaseHTTPRequestHandler):
            def do_PROPFIND(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                received.append((self.headers.get('Authorization'), body))
                if self.headers.get('Authorization') != expected:
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="Nextcloud", charset="UTF-8"')
                    self.end_headers()
                    return
                self.send_response(207)
                self.end_headers()
                self.wfile.write(b'<d:multistatus xmlns:d="DAV:"/>')

            def do_MKCOL(self):
                self.send_response(405)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            session = SimpleSession(WebDAVConfig(base, '/dav', 'user', 'test-password'))
            result = session.request('PROPFIND', base + '/dav/user', headers={'Depth': '0'}, data='<propfind/>', timeout=5)
            self.assertEqual(result.status_code, 207)
            self.assertEqual(received, [(None, b'<propfind/>'), (expected, b'<propfind/>')])
            bad = SimpleSession(WebDAVConfig(base, '/dav', 'user', 'wrong-password'))
            rejected = bad.request('PROPFIND', base + '/dav/user', timeout=5)
            self.assertEqual(rejected.status_code, 401)
            with self.assertRaises(SimpleRequestException):
                rejected.raise_for_status()
            ensure_remote_directories(session, WebDAVConfig(base, '/dav', 'user', 'test-password'), 'tinyGW/site/host')
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
