import contextlib
import http.cookiejar
import io
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

from werkzeug.serving import make_server

from app import create_app, main
from library import read_json
from server_tls import tls_context


class TLSConfigurationTests(unittest.TestCase):
    def test_http_only_when_not_requesting_https(self):
        self.assertIsNone(tls_context())
        for certificate, key, required in [(None, None, True), ('cert.pem', None, False), (None, 'key.pem', False)]:
            with self.assertRaises(ValueError):
                tls_context(certificate, key, required)

    def test_bad_tls_settings_never_start_http_server(self):
        for args in [['--https'], ['--certfile', 'missing.pem', '--keyfile', 'missing.key']]:
            with patch('app.Flask.run') as run, patch('app.faulthandler.enable'), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main(args)
                self.assertEqual(result.exception.code, 2)
                run.assert_not_called()


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL is needed to create a temporary test certificate')
class HTTPSIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name).resolve()
        cls.cert, cls.key = cls.folder / 'cert.pem', cls.folder / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-keyout', str(cls.key), '-out', str(cls.cert), '-subj', '/CN=localhost',
                        '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=20)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_cert_chain_loads_and_cli_enables_secure_cookie_automatically(self):
        context = tls_context(self.cert, self.key)
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        with tempfile.TemporaryDirectory() as folder, patch('app.Flask.run', autospec=True) as run, contextlib.redirect_stdout(io.StringIO()):
            main(['--root', folder, '--directory', folder, '--db', str(Path(folder) / 'db'),
                  '--https', '--certfile', str(self.cert), '--keyfile', str(self.key)])
        app = run.call_args.args[0]
        self.assertTrue(app.config['SESSION_COOKIE_SECURE'])
        self.assertIsInstance(run.call_args.kwargs['ssl_context'], ssl.SSLContext)
        self.assertFalse(run.call_args.kwargs['debug'])
        self.assertFalse(run.call_args.kwargs['use_reloader'])

    def test_invalid_certificate_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.pem'
            path.write_text('not a certificate')
            with self.assertRaises(ssl.SSLError):
                tls_context(path, self.key)

    def test_verified_https_initial_setup_login_and_protected_api(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': ''}):
            root = Path(folder).resolve()
            app = create_app(root, root, root / 'db')
            app.config['SESSION_COOKIE_SECURE'] = True
            server = make_server('127.0.0.1', 0, app, threaded=True, ssl_context=tls_context(self.cert, self.key))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                jar = http.cookiejar.CookieJar()
                client = build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=str(self.cert))), HTTPCookieProcessor(jar))
                url = f'https://127.0.0.1:{server.server_port}'
                with client.open(url + '/', timeout=5) as response:
                    page = response.read().decode()
                self.assertIn('auth-login', page)
                self.assertNotIn(str(root), page)
                with self.assertRaises(HTTPError) as denied:
                    client.open(url + '/api/config', timeout=5)
                self.assertEqual(denied.exception.code, 401)
                denied.exception.close()
                body = {'setup_token': read_json(root / 'db' / 'auth.json')['setup_token'],
                        'password': 'tls-fixture-password', 'confirm_password': 'tls-fixture-password'}
                request = Request(url + '/api/auth/setup', data=json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json', 'X-Photo-Browser': '1', 'Origin': url})
                with client.open(request, timeout=5) as response:
                    self.assertTrue(json.load(response)['ok'])
                    self.assertIn('Secure', response.headers['Set-Cookie'])
                self.assertTrue(all(cookie.secure for cookie in jar))
                with client.open(url + '/api/config', timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                worker.join(5)
                server.server_close()


if __name__ == '__main__':
    unittest.main()
