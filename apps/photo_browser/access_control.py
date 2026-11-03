"""Shared-password GUI sessions, compatible with existing Basic API clients."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import OrderedDict
from datetime import timedelta

from flask import abort, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from library import read_json


class AccessControl:
    def __init__(self, app, db):
        self.path = db / 'auth.json'
        self.lock = threading.RLock()
        self.failures = OrderedDict()
        config = self.config()
        os.chmod(self.path, 0o600)
        app.secret_key = config['session_secret']
        app.config.update(SESSION_COOKIE_NAME='photo_browser_session', SESSION_COOKIE_HTTPONLY=True,
                          SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
                          SESSION_COOKIE_SECURE=os.environ.get('PHOTO_BROWSER_COOKIE_SECURE') == '1')
        app.extensions['photo_access'] = self

    def write(self, config):
        temporary = self.path.with_name('.auth-' + secrets.token_hex(12) + '.tmp')
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def config(self):
        with self.lock:
            if self.path.is_symlink():
                raise ValueError('인증 설정은 심볼릭 링크가 아닌 auth.json 파일이어야 합니다.')
            config = read_json(self.path, {})
            if not isinstance(config, dict):
                raise ValueError('auth.json은 JSON 객체여야 합니다.')
            before = dict(config)
            config.setdefault('schema_version', 1)
            config.setdefault('session_secret', secrets.token_hex(32))
            config.setdefault('credential_version', secrets.token_hex(16))
            config.setdefault('setup_token', secrets.token_urlsafe(24))
            config.setdefault('password_hash', None)
            if config['schema_version'] != 1 or not isinstance(config['session_secret'], str) or len(config['session_secret']) < 32:
                raise ValueError('auth.json 버전 또는 세션 키를 확인하세요.')
            if config['password_hash'] is not None and (not isinstance(config['password_hash'], str) or not config['password_hash']):
                raise ValueError('auth.json password_hash 값을 확인하세요.')
            if any(not isinstance(config[key], str) or len(config[key]) < 16 for key in ('credential_version', 'setup_token')):
                raise ValueError('auth.json 초기 설정 키 또는 인증 버전을 확인하세요.')
            if 'password' in config:
                password = config.pop('password')
                self.validate_new(password)
                config.update(password_hash=generate_password_hash(password, method='pbkdf2:sha256:600000'),
                              credential_version=secrets.token_hex(16))
            if config != before:
                self.write(config)
            return config

    @staticmethod
    def validate_new(password):
        if not isinstance(password, str) or not password.strip() or not 8 <= len(password) <= 128:
            raise ValueError('새 비밀번호는 8~128자로 입력하세요.')

    @staticmethod
    def enabled(config):
        return bool(config['password_hash'] or os.environ.get('PHOTO_BROWSER_PASSWORD'))

    @staticmethod
    def matches(config, password):
        if not isinstance(password, str) or len(password) > 1024:
            return False
        if config['password_hash']:
            return check_password_hash(config['password_hash'], password)
        expected = os.environ.get('PHOTO_BROWSER_PASSWORD', '')
        return bool(expected) and hmac.compare_digest(password.encode('utf-8'), expected.encode('utf-8'))

    @staticmethod
    def fingerprint(config):
        credential = config['password_hash'] or os.environ.get('PHOTO_BROWSER_PASSWORD', '')
        return hashlib.sha256((config['credential_version'] + '\0' + credential).encode('utf-8')).hexdigest()

    def authenticated(self, config):
        token = session.get('photo_auth')
        if isinstance(token, str) and hmac.compare_digest(token.encode(), self.fingerprint(config).encode()):
            return True
        if session.get('photo_basic_logged_out'):
            return False
        basic = request.authorization
        if not basic or basic.type != 'basic' or self.limited():
            return False
        valid = self.matches(config, basic.password)
        if not valid:
            self.failed()
        return valid

    def login(self, config):
        session.clear()
        session.permanent = True
        session['photo_auth'] = self.fingerprint(config)
        with self.lock:
            self.failures.pop(request.remote_addr or 'unknown', None)

    def limited(self):
        key, clock = request.remote_addr or 'unknown', time.monotonic()
        with self.lock:
            times = [t for t in self.failures.pop(key, []) if clock - t < 60]
            self.failures[key] = times
            if len(self.failures) > 4096:
                self.failures.popitem(last=False)
            if len(times) >= 5:
                return True
            return False

    def failed(self):
        with self.lock:
            self.failures.setdefault(request.remote_addr or 'unknown', []).append(time.monotonic())

    def protect(self):
        config = self.config()
        public = request.endpoint in {'static', 'auth_status', 'auth_login', 'auth_setup', 'auth_logout'}
        if not public and self.enabled(config) and not self.authenticated(config):
            if request.endpoint == 'index':
                return render_template('login.html')
            return jsonify(error='로그인이 필요합니다.', login_required=True), 401
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            from urllib.parse import urlsplit
            origin = request.headers.get('Origin')
            if request.headers.get('X-Photo-Browser') != '1' or (origin and urlsplit(origin).netloc != request.host):
                abort(403, description='허용되지 않은 변경 요청입니다.')


def register_access(app, db):
    access = AccessControl(app, db)
    app.before_request(access.protect)

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('JSON 객체를 보내세요.')
        return data

    def throttle():
        if access.limited():
            return jsonify(error='로그인 시도가 너무 많습니다. 1분 후 다시 시도하세요.'), 429, {'Retry-After': '60'}

    @app.get('/api/auth/status')
    def auth_status():
        config = access.config()
        return jsonify(enabled=access.enabled(config), authenticated=access.enabled(config) and access.authenticated(config))

    @app.post('/api/auth/login')
    def auth_login():
        blocked = throttle()
        if blocked:
            return blocked
        config = access.config()
        if not access.enabled(config):
            raise ValueError('아직 암호가 설정되지 않았습니다. 초기 암호를 저장하세요.')
        if not access.matches(config, body().get('password')):
            access.failed()
            return jsonify(error='비밀번호가 올바르지 않습니다.'), 401
        access.login(config)
        return jsonify(ok=True)

    @app.post('/api/auth/setup')
    def auth_setup():
        blocked = throttle()
        if blocked:
            return blocked
        with access.lock:
            config, data = access.config(), body()
            if access.enabled(config):
                return jsonify(error='이미 암호가 설정되었습니다. 로그인 후 변경하세요.'), 403
            token = data.get('setup_token')
            if not isinstance(token, str) or not hmac.compare_digest(token.encode(), config['setup_token'].encode()):
                access.failed()
                return jsonify(error='설정 파일의 초기 설정 키를 확인하세요.'), 403
            password = data.get('password')
            access.validate_new(password)
            if password != data.get('confirm_password'):
                raise ValueError('새 비밀번호 확인 값이 다릅니다.')
            config.update(password_hash=generate_password_hash(password, method='pbkdf2:sha256:600000'),
                          credential_version=secrets.token_hex(16), setup_token=secrets.token_urlsafe(24))
            access.write(config)
            access.login(config)
        return jsonify(ok=True)

    @app.post('/api/auth/password')
    def auth_password():
        with access.lock:
            config, data = access.config(), body()
            if not access.enabled(config) or not access.authenticated(config):
                return jsonify(error='로그인 후 비밀번호를 변경하세요.'), 401
            password = data.get('password')
            access.validate_new(password)
            if password != data.get('confirm_password'):
                raise ValueError('새 비밀번호 확인 값이 다릅니다.')
            config.update(password_hash=generate_password_hash(password, method='pbkdf2:sha256:600000'),
                          credential_version=secrets.token_hex(16))
            access.write(config)
            access.login(config)
        return jsonify(ok=True)

    @app.post('/api/auth/logout')
    def auth_logout():
        session.clear()
        # Browsers may retain legacy Basic credentials. An explicit GUI logout
        # must not silently authenticate again from that cached header.
        session['photo_basic_logged_out'] = True
        return jsonify(ok=True)

    @app.after_request
    def auth_cache(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    return access
