import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as music


class PlayerTests(unittest.TestCase):
    def setUp(self):
        music.app.config.update(TESTING=True)
        music.TOKENS.clear()
        self.client = music.app.test_client()

    def signed_in(self, expires=None):
        with self.client.session_transaction() as s:
            s['sid'] = 'test'
            s['csrf'] = 'csrf'
        music.TOKENS['test'] = dict(access_token='access', refresh_token='refresh',
            expires=expires or time.time()+3600, session_expires=time.time()+86400)

    def test_http_ui_available_without_spotify(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HTTP 음악 파일', response.text)
        self.assertEqual(self.client.get('/token').status_code, 401)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_callback_rejects_forged_and_expired_state(self):
        with patch.object(music, 'token_request') as token:
            self.assertEqual(self.client.get('/callback?state=bad&code=x').status_code, 400)
            with self.client.session_transaction() as s:
                s['oauth_state'] = 'state'; s['oauth_started'] = time.time()-601
            self.assertEqual(self.client.get('/callback?state=state&code=x').status_code, 400)
            token.assert_not_called()

    def test_callback_keeps_refresh_token_out_of_cookie(self):
        with self.client.session_transaction() as s:
            s['oauth_state'] = 'state'; s['oauth_started'] = time.time()
        with patch.object(music, 'token_request', return_value=dict(access_token='a', refresh_token='SECRET_REFRESH', expires_in=3600)):
            self.assertEqual(self.client.get('/callback?state=state&code=x').status_code, 302)
        with self.client.session_transaction() as s:
            self.assertNotIn('refresh_token', s)
            self.assertEqual(music.TOKENS[s['sid']]['refresh_token'], 'SECRET_REFRESH')

    def test_refresh(self):
        self.signed_in(time.time()-1)
        with patch.object(music, 'token_request', return_value=dict(access_token='renewed', expires_in=3600)):
            self.assertEqual(self.client.get('/token').json, {'access_token':'renewed'})
            self.assertEqual(music.TOKENS['test']['refresh_token'], 'refresh')

    def test_api_restriction_csrf_and_pagination(self):
        self.signed_in()
        with patch.object(music.requests, 'request') as upstream:
            self.assertEqual(self.client.get('/api/arbitrary').status_code, 404)
            self.assertEqual(self.client.put('/api/me/player/play', json={}).status_code, 403)
            upstream.assert_not_called()
            upstream.return_value = Mock(status_code=200, headers={}, json=lambda:{'items':[], 'next':None})
            self.assertEqual(self.client.get('/api/playlists/abc123/items?limit=20&offset=20').status_code, 200)
            self.assertEqual(upstream.call_args.kwargs['params']['offset'], '20')
            upstream.return_value = Mock(status_code=204)
            self.assertEqual(self.client.put('/api/me/player/play?device_id=browser', json={'uris':['spotify:track:test']}, headers={'X-CSRF-Token':'csrf'}).status_code, 204)

    def test_logout_revokes_local_session(self):
        self.signed_in()
        self.assertEqual(self.client.post('/logout').status_code, 403)
        self.assertEqual(self.client.post('/logout', headers={'X-CSRF-Token':'csrf'}).status_code, 200)
        self.assertFalse(music.TOKENS)
        self.assertEqual(self.client.get('/token').status_code, 401)


if __name__ == '__main__':
    unittest.main()
