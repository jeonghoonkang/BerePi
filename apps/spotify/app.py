"""Personal Spotify SDK + direct HTTP audio player."""
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session

load_dotenv(Path(__file__).with_name('.env'))
app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE') == '1')
# Credentials stay on the server; cookies contain only an opaque session ID.
TOKENS = {}
API = 'https://api.spotify.com/v1'
REDIRECT = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8501/callback')
SCOPES = 'streaming user-read-email user-read-private user-library-read playlist-read-private playlist-read-collaborative user-read-playback-state user-modify-playback-state'


def token_request(data):
    response = requests.post('https://accounts.spotify.com/api/token', data=data,
                             auth=(os.getenv('SPOTIFY_CLIENT_ID', ''),
                                   os.getenv('SPOTIFY_CLIENT_SECRET', '')), timeout=20)
    response.raise_for_status()
    return response.json()


def access_token():
    sid = session.get('sid')
    record = TOKENS.get(sid)
    if not record or record['session_expires'] < time.time():
        TOKENS.pop(sid, None)
        return None
    if record['expires'] <= time.time() + 60:
        refreshed = token_request({'grant_type': 'refresh_token', 'refresh_token': record['refresh_token']})
        record.update(access_token=refreshed['access_token'], expires=time.time() + refreshed['expires_in'],
                      refresh_token=refreshed.get('refresh_token', record['refresh_token']))
    return record['access_token']


@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.errorhandler(requests.RequestException)
def upstream_error(error):
    return jsonify(error='외부 API 연결 또는 인증에 실패했습니다. 다시 로그인하거나 잠시 후 재시도하세요.'), 502


@app.get('/')
def index():
    session.setdefault('csrf', secrets.token_urlsafe(32))
    return render_template('index.html', csrf=session['csrf'], configured=bool(os.getenv('SPOTIFY_CLIENT_ID') and os.getenv('SPOTIFY_CLIENT_SECRET')))


@app.get('/login')
def login():
    if not os.getenv('SPOTIFY_CLIENT_ID') or not os.getenv('SPOTIFY_CLIENT_SECRET'):
        return '서버의 .env에 Spotify Client ID와 Secret을 설정하세요.', 400
    session['oauth_state'] = secrets.token_urlsafe(32)
    session['oauth_started'] = time.time()
    return redirect('https://accounts.spotify.com/authorize?' + urlencode(dict(
        client_id=os.environ['SPOTIFY_CLIENT_ID'], response_type='code', redirect_uri=REDIRECT,
        scope=SCOPES, state=session['oauth_state'])))


@app.get('/callback')
def callback():
    expected = session.pop('oauth_state', None)
    started = session.pop('oauth_started', 0)
    if not expected or not secrets.compare_digest(expected, request.args.get('state', '')) or time.time() - started > 600:
        return '로그인 검증 실패. 처음부터 다시 로그인하세요.', 400
    if request.args.get('error') or not request.args.get('code'):
        return 'Spotify 로그인이 취소되었습니다.', 400
    data = token_request(dict(grant_type='authorization_code', code=request.args['code'], redirect_uri=REDIRECT))
    TOKENS.pop(session.get('sid'), None)
    for sid, record in list(TOKENS.items()):
        if record['session_expires'] < time.time():
            TOKENS.pop(sid, None)
    session['sid'] = secrets.token_urlsafe(32)
    TOKENS[session['sid']] = dict(access_token=data['access_token'], refresh_token=data['refresh_token'],
        expires=time.time() + data['expires_in'], session_expires=time.time() + 86400)
    return redirect('/')


@app.post('/logout')
def logout():
    if request.headers.get('X-CSRF-Token') != session.get('csrf') or not session.get('csrf'):
        return jsonify(error='요청 검증 실패'), 403
    TOKENS.pop(session.get('sid'), None)
    session.clear()
    return jsonify(ok=True)


@app.get('/token')
def token():
    value = access_token()
    return (jsonify(access_token=value) if value else (jsonify(error='Spotify 로그인이 필요합니다.'), 401))


@app.route('/api/<path:path>', methods=['GET', 'PUT'])
def spotify_api(path):
    allowed = path in ('me', 'me/tracks', 'me/playlists') or bool(re.fullmatch(r'playlists/[A-Za-z0-9]+/items', path))
    if request.method == 'PUT':
        allowed = path in ('me/player/play', 'me/player/pause')
        if not session.get('csrf') or request.headers.get('X-CSRF-Token') != session['csrf']:
            return jsonify(error='요청 검증 실패'), 403
    if not allowed:
        return jsonify(error='허용되지 않은 API'), 404
    value = access_token()
    if not value:
        return jsonify(error='Spotify 로그인이 필요합니다.'), 401
    response = requests.request(request.method, f'{API}/{path}', params=request.args,
        json=request.get_json(silent=True) if request.method == 'PUT' else None,
        headers={'Authorization': f'Bearer {value}'}, timeout=20)
    if response.status_code == 204:
        return '', 204
    try:
        payload = response.json()
    except ValueError:
        payload = {'error': 'Spotify가 잘못된 응답을 반환했습니다.'}
    result = jsonify(payload)
    result.status_code = response.status_code
    if 'Retry-After' in response.headers:
        result.headers['Retry-After'] = response.headers['Retry-After']
    return result


if __name__ == '__main__':
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '8501')), debug=False)
