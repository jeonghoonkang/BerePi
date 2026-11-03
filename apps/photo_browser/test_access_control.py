import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from library import read_json


class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}
        self.path = self.root / 'db' / 'auth.json'

    def post(self, endpoint, data, client=None, headers=None):
        return (client or self.client).post('/api/auth/' + endpoint, json=data, headers=headers or self.headers)

    def setup_password(self, password='my-password-123'):
        token = read_json(self.path)['setup_token']
        return self.post('setup', {'setup_token': token, 'password': password, 'confirm_password': password})

    def test_initial_file_and_owner_token_setup(self):
        config = read_json(self.path)
        self.assertIsNone(config['password_hash'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.client.get('/api/auth/status').json['enabled'])
        self.assertEqual(self.post('setup', {'setup_token': 'wrong', 'password': 'my-password-123', 'confirm_password': 'my-password-123'}).status_code, 403)
        self.assertEqual(self.setup_password().status_code, 200)
        stored = self.path.read_text()
        self.assertNotIn('my-password-123', stored)
        self.assertIn('pbkdf2:sha256:', read_json(self.path)['password_hash'])
        self.assertTrue(self.client.get('/api/auth/status').json['authenticated'])
        self.assertEqual(self.client.get('/api/config').status_code, 200)

    def test_logged_out_page_hides_paths_and_apis_and_files_require_login(self):
        self.setup_password()
        other = self.app.test_client()
        page = other.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('auth-login', page.get_data(as_text=True))
        self.assertNotIn(str(self.root), page.get_data(as_text=True))
        self.assertNotIn('server-network', page.get_data(as_text=True))
        self.assertEqual(page.headers['Cache-Control'], 'no-store')
        for path in ['/api/config', '/api/library-summary', '/api/workflow', '/media?path=private.jpg']:
            response = other.get(path)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('WWW-Authenticate', response.headers)
        response = other.get('/static/auth.js')
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_gui_login_logout_and_cookie_flags(self):
        self.setup_password()
        self.post('logout', {})
        self.assertEqual(self.post('login', {'password': 'wrong'}).status_code, 401)
        response = self.post('login', {'password': 'my-password-123'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', response.headers['Set-Cookie'])
        self.assertEqual(self.client.get('/api/config').status_code, 200)
        self.assertEqual(self.post('logout', {}).status_code, 200)
        self.assertEqual(self.client.get('/api/config').status_code, 401)

    def test_change_password_requires_login_and_revokes_other_sessions(self):
        self.setup_password()
        other = self.app.test_client()
        self.assertEqual(self.post('password', {'password': 'new-pass-123', 'confirm_password': 'new-pass-123'}, other).status_code, 401)
        self.post('login', {'password': 'my-password-123'}, other)
        self.assertEqual(self.post('password', {'password': 'new-pass-123', 'confirm_password': 'new-pass-123'}).status_code, 200)
        self.assertEqual(self.client.get('/api/config').status_code, 200)
        self.assertEqual(other.get('/api/config').status_code, 401)
        self.assertEqual(self.post('login', {'password': 'my-password-123'}, other).status_code, 401)
        self.assertEqual(self.post('login', {'password': 'new-pass-123'}, other).status_code, 200)

    def test_settings_persist_across_server_restart_and_old_setup_token_is_not_admin(self):
        self.setup_password()
        second_app = create_app(self.root, self.root, self.root / 'db')
        other = second_app.test_client()
        self.assertTrue(other.get('/api/auth/status').json['enabled'])
        self.assertEqual(self.post('login', {'password': 'my-password-123'}, other).status_code, 200)
        self.assertEqual(self.post('setup', {'setup_token': read_json(self.path)['setup_token'], 'password': 'other-pass', 'confirm_password': 'other-pass'}, other).status_code, 403)

    def test_manual_password_file_import_is_hashed_and_removed(self):
        self.path.write_text(json.dumps({'password': 'manual-password-123'}))
        other_app = create_app(self.root, self.root, self.root / 'db')
        other = other_app.test_client()
        self.assertNotIn('password', read_json(self.path))
        self.assertEqual(self.post('login', {'password': 'manual-password-123'}, other).status_code, 200)

    def test_existing_env_and_basic_auth_work_but_saved_password_takes_priority(self):
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'legacy-secret'}):
            self.assertEqual(self.client.get('/api/config').status_code, 401)
            self.assertEqual(self.client.get('/api/config', auth=('user', 'legacy-secret')).status_code, 200)
            self.assertEqual(self.post('login', {'password': 'legacy-secret'}).status_code, 200)
            self.post('password', {'password': 'stored-password', 'confirm_password': 'stored-password'})
            other = self.app.test_client()
            self.assertEqual(other.get('/api/config', auth=('user', 'legacy-secret')).status_code, 401)
            self.assertEqual(other.get('/api/config', auth=('user', 'stored-password')).status_code, 200)

    def test_post_headers_origin_and_password_confirmation(self):
        token = read_json(self.path)['setup_token']
        data = {'setup_token': token, 'password': 'my-password-123', 'confirm_password': 'my-password-123'}
        self.assertEqual(self.client.post('/api/auth/setup', json=data).status_code, 403)
        self.assertEqual(self.post('setup', data, headers={**self.headers, 'Origin': 'https://evil.invalid'}).status_code, 403)
        self.assertEqual(self.post('setup', {**data, 'confirm_password': 'different'}).status_code, 400)
        self.assertEqual(self.post('setup', {**data, 'password': 'short', 'confirm_password': 'short'}).status_code, 400)
        self.assertFalse(self.client.get('/api/auth/status').json['enabled'])

    def test_failed_login_attempts_are_throttled(self):
        self.setup_password()
        self.post('logout', {})
        for _ in range(5):
            self.assertEqual(self.post('login', {'password': 'wrong'}).status_code, 401)
        response = self.post('login', {'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '60')

    def test_unicode_password_and_no_secret_in_status(self):
        password = '나의안전한암호123'
        self.setup_password(password)
        self.post('logout', {})
        self.assertEqual(self.post('login', {'password': password}).status_code, 200)
        self.assertEqual(set(self.client.get('/api/auth/status').json), {'enabled', 'authenticated'})

    def test_logout_blocks_browser_cached_basic_credentials_until_login(self):
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'legacy-secret'}):
            self.assertEqual(self.client.get('/api/config', auth=('user', 'legacy-secret')).status_code, 200)
            self.post('logout', {})
            self.assertEqual(self.client.get('/api/config', auth=('user', 'legacy-secret')).status_code, 401)
            self.post('login', {'password': 'legacy-secret'})
            self.assertEqual(self.client.get('/api/config').status_code, 200)

    def test_copied_cookie_cannot_be_replayed_after_logout(self):
        self.setup_password()
        cookie = self.client.get_cookie('photo_browser_session').value
        self.post('logout', {})
        replay = self.app.test_client()
        replay.set_cookie('photo_browser_session', cookie)
        self.assertEqual(replay.get('/api/config').status_code, 401)
        self.assertFalse(replay.get('/api/auth/status').json['authenticated'])

    def test_missing_auth_file_fails_closed_including_after_restart(self):
        self.setup_password()
        self.assertTrue((self.root / 'db' / 'auth.required').is_file())
        self.path.unlink()
        self.assertEqual(self.app.test_client().get('/api/config').status_code, 400)
        self.assertFalse(self.path.exists())
        with self.assertRaisesRegex(ValueError, '필수 인증 설정'):
            create_app(self.root, self.root, self.root / 'db')

    def test_clearing_password_or_expired_server_session_does_not_allow_access(self):
        import time
        self.setup_password()
        config = read_json(self.path)
        config['sessions'] = {key: time.time() - 1 for key in config['sessions']}
        self.app.extensions['photo_access'].write(config)
        self.assertEqual(self.client.get('/api/config').status_code, 401)
        config['password_hash'] = None
        self.path.write_text(json.dumps(config))
        self.assertEqual(self.app.test_client().get('/api/config').status_code, 400)

    def test_logging_out_one_session_does_not_logout_other_client(self):
        self.setup_password()
        other = self.app.test_client()
        self.post('login', {'password': 'my-password-123'}, other)
        self.post('logout', {})
        self.assertEqual(other.get('/api/config').status_code, 200)


if __name__ == '__main__':
    unittest.main()
