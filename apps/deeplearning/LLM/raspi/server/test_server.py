"""HTTP integration tests; no Ollama installation or model download needed."""
import subprocess
import json
import base64
import io
import time
from http.cookiejar import CookieJar
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from server import Config, Server, MAX_OCR_BODY, MAX_IMAGE_BYTES
from PIL import Image


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"models": [{"name": "gemma4:e4b"}]}).encode())

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.received = data
        self.server.received_path = self.path
        if data.get('prompt') == 'block':
            self.server.entered.set()
            self.server.release.wait(5)
        failed = data.get('prompt') == 'fail'
        self.send_response(500 if failed else 200)
        self.end_headers()
        response = {'response': '안녕하세요', 'done': True, 'model': 'gemma4:e4b',
                    'eval_count': 8, 'eval_duration': 2000000000}
        if self.path == '/api/show':
            response = {'capabilities': ['completion', 'vision']}
        if self.path == '/api/chat':
            response = {'message': {'role': 'assistant', 'content': '안녕하세요'}, 'done': True}
        self.wfile.write(json.dumps(response).encode())


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
        cls.backend.entered = threading.Event()
        cls.backend.release = threading.Event()
        cls.backend_thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.backend_thread.start()
        cls.key = 'test-key-' + 'a' * 32
        with patch.dict(os.environ, {'GEMMA4_API_KEY': cls.key}, clear=True):
            config = Config()
        config.backend = f'http://127.0.0.1:{cls.backend.server_port}'
        cls.server = Server(('127.0.0.1', 0), config)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        for server, thread in [(cls.server, cls.thread), (cls.backend, cls.backend_thread)]:
            server.shutdown()
            server.server_close()
            thread.join()

    def request(self, path, data=None, auth=True):
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + self.key
        request = urllib.request.Request(self.base + path, headers=headers,
                                         data=None if data is None else json.dumps(data).encode())
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_health_and_readiness(self):
        self.assertEqual(self.request('/health', auth=False)[0], 200)
        self.assertEqual(self.request('/ready', auth=False)[0], 401)
        self.assertEqual(self.request('/ready')[1]['ready'], True)
        original = self.server.config.model
        try:
            self.server.config.model = 'missing:model'
            self.assertEqual(self.request('/ready')[0], 503)
        finally:
            self.server.config.model = original

    def test_auth_required_before_inference(self):
        self.assertEqual(self.request('/api/generate', {'prompt': 'hello'}, auth=False)[0], 401)

    def test_generate_cpu_limits(self):
        status, result = self.request('/api/generate', {'prompt': '안녕'})
        self.assertEqual(status, 200)
        self.assertEqual(result['response'], '안녕하세요')
        self.assertEqual(self.backend.received['options'],
                         {'num_ctx': 2048, 'num_thread': 4, 'num_gpu': 0, 'num_predict': 512})
        self.assertFalse(self.backend.received['stream'])

    def test_chat(self):
        messages = [{'role': 'user', 'content': '안녕'}]
        status, result = self.request('/api/chat', {'messages': messages})
        self.assertEqual(status, 200)
        self.assertEqual(result['message']['content'], '안녕하세요')
        self.assertEqual(self.backend.received['messages'], messages)

    def test_invalid_and_resource_override_requests(self):
        for payload in [[], {'prompt': ''}, {'prompt': 4}, {'prompt': 'a', 'stream': True},
                        {'prompt': 'a', 'model': 'gemma4:31b'},
                        {'prompt': 'a', 'options': {'num_ctx': 128000}}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.request('/api/generate', payload)[0], 400)
        self.assertEqual(self.request('/api/chat', {'messages': [{'role': 'bogus'}]})[0], 400)
        self.assertEqual(self.request('/api/chat', {'messages': [{'role': [], 'content': 'x'}]})[0], 400)
        self.assertEqual(self.request('/api/generate', {'prompt': 'a' * 65536})[0], 413)

    def test_backend_failure_releases_slot(self):
        self.assertEqual(self.request('/api/generate', {'prompt': 'fail'})[0], 502)
        self.assertEqual(self.request('/api/generate', {'prompt': 'hello'})[0], 200)

    def test_busy_request_is_rejected(self):
        results = []
        worker = threading.Thread(target=lambda: results.append(self.request('/api/generate', {'prompt': 'block'})))
        worker.start()
        try:
            self.assertTrue(self.backend.entered.wait(2))
            self.assertEqual(self.request('/api/generate', {'prompt': 'second'})[0], 429)
            self.assertEqual(self.request('/health')[0], 200)
        finally:
            self.backend.release.set()
            worker.join(5)
        self.assertEqual(results[0][0], 200)

    def test_status_and_model_info_require_auth(self):
        for path in ['/api/status', '/api/model-info']:
            self.assertEqual(self.request(path, auth=False)[0], 401)
            status, data = self.request(path)
            self.assertEqual(status, 200)
            self.assertNotIn(self.key, json.dumps(data))
        status = self.request('/api/status')[1]
        self.assertTrue(status['ollama_online'])
        self.assertTrue(status['model_installed'])
        self.assertEqual(status['inference']['device'], 'CPU')
        self.assertIn('memory', status['server'])

    def test_generation_timings_preserve_backend_model(self):
        status, data = self.request('/api/generate', {'prompt': 'hi'})
        self.assertEqual(status, 200)
        self.assertEqual(data['model'], 'gemma4:e4b')
        self.assertEqual(data['requested_model'], 'gemma4:e4b')
        self.assertGreaterEqual(data['elapsed_seconds'], 0)
        self.assertEqual(data['eval_count'], 8)

    def test_login_session_logout_expiry_and_origin(self):
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                            urllib.request.HTTPCookieProcessor(jar))
        def call(path, data=None, origin=None):
            headers = {'Content-Type': 'application/json'}
            if origin:
                headers['Origin'] = origin
            request = urllib.request.Request(self.base + path, headers=headers,
                data=None if data is None else json.dumps(data).encode())
            try:
                response = opener.open(request, timeout=10)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, json.load(response)
        self.assertFalse(call('/api/session')[1]['logged_in'])
        self.assertEqual(call('/api/session-login', {'user_id': 'admin', 'password': 'bad'})[0], 401)
        self.assertEqual(call('/api/session-login', {'user_id': [], 'password': self.key})[0], 400)
        credentials = {'user_id': 'admin', 'password': self.key}
        self.assertEqual(call('/api/session-login', credentials, 'http://other.example')[0], 403)
        self.assertEqual(call('/api/session-login', credentials)[0], 200)
        cookie = next(iter(jar))
        self.assertIn('HttpOnly', cookie._rest)
        self.assertEqual(cookie._rest['SameSite'], 'Strict')
        self.assertTrue(call('/api/session')[1]['logged_in'])
        self.assertEqual(call('/api/status')[0], 200)
        self.assertEqual(call('/api/chat', {'messages': [{'role': 'user', 'content': 'hi'}]})[0], 200)
        self.assertEqual(call('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 200)
        self.assertEqual(call('/api/session-logout', {}, 'http://other.example')[0], 403)
        self.assertEqual(call('/api/session-logout', {})[0], 200)
        self.assertEqual(call('/api/status')[0], 401)
        self.assertEqual(call('/api/session-login', credentials)[0], 200)
        with self.server.session_lock:
            for token, (user, _) in self.server.sessions.items():
                self.server.sessions[token] = (user, time.monotonic() - 1)
        self.assertEqual(call('/api/status')[0], 401)

    def test_separate_login_password(self):
        with patch.dict(os.environ, {'GEMMA4_API_KEY': self.key,
                                    'GEMMA4_LOGIN_PASSWORD': 'separate-password'}, clear=True):
            config = Config()
        self.assertEqual(config.password, 'separate-password')
        self.assertEqual(config.key, self.key)

    @staticmethod
    def image(format='PNG', size=(32, 16)):
        buffer = io.BytesIO()
        Image.new('RGB', size, 'white').save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode('ascii')

    def test_ocr_png_and_jpeg_forward_images_and_return_text(self):
        for format in ('PNG', 'JPEG'):
            with self.subTest(format=format):
                image = self.image(format)
                status, result = self.request('/api/ocr', {'image': image, 'prompt': '글자만 읽어 주세요', 'engine': 'gemma'})
                self.assertEqual(status, 200)
                self.assertEqual(result['text'], '안녕하세요')
                self.assertEqual(self.backend.received_path, '/api/chat')
                self.assertEqual(self.backend.received['messages'][0],
                                 {'role': 'user', 'content': '글자만 읽어 주세요', 'images': [image]})
                self.assertEqual(self.backend.received['options']['num_predict'], 2048)
                self.assertEqual(self.backend.received['options']['num_gpu'], 0)
                self.assertGreaterEqual(result['elapsed_seconds'], 0)

    def test_ocr_requires_auth(self):
        self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'}, auth=False)[0], 401)

    def test_invalid_ocr_rejected_and_slot_released(self):
        image = self.image()
        for data in [[], {}, {'image': 123}, {'image': ''}, {'image': '%bad-base64%'},
                     {'image': base64.b64encode(b'not an image').decode()},
                     {'image': self.image('GIF')}, {'image': image, 'prompt': ''},
                     {'image': image, 'prompt': 42}, {'image': image, 'prompt': 'a' * 4001},
                     {'image': image, 'options': {}}, {'image': 'data:image/png;base64,' + image},
                     {'image': base64.b64encode(base64.b64decode(image)[:30]).decode()}]:
            with self.subTest(data=str(data)[:70]):
                self.assertEqual(self.request('/api/ocr', data)[0], 400)
                self.assertFalse(self.server.inference.locked())
        self.assertEqual(self.request('/api/ocr', {'image': image, 'engine': 'gemma'})[0], 200)

    def test_ocr_image_and_body_limits(self):
        # Lower limits keep the regression test small while exercising HTTP validation.
        with patch('server.MAX_IMAGE_BYTES', 10):
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 400)
        with patch('server.MAX_IMAGE_PIXELS', 100):
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 400)
        with patch('server.MAX_OCR_BODY', 20):
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 413)
        self.assertGreater(MAX_OCR_BODY, MAX_IMAGE_BYTES)
        self.assertFalse(self.server.inference.locked())

    def test_ocr_accepts_full_10_mib_and_rejects_one_byte_over(self):
        self.assertEqual(MAX_IMAGE_BYTES, 10 * 1024 * 1024)
        # Valid PNG with trailing padding exercises real HTTP/base64 body limits.
        raw = base64.b64decode(self.image())
        raw += b"\0" * (MAX_IMAGE_BYTES - len(raw))
        encoded = base64.b64encode(raw).decode('ascii')
        status, result = self.request('/api/ocr', {'image': encoded})
        self.assertEqual(status, 200)
        self.assertEqual(self.backend.received['messages'][0]['images'], [encoded])
        status, result = self.request('/api/ocr', {'image': base64.b64encode(raw + b'x').decode('ascii')})
        self.assertEqual(status, 400)
        self.assertIn('10 MiB', result['error'])
        self.assertFalse(self.server.inference.locked())

    def test_bundled_ocr_example_requires_auth_and_is_valid_image(self):
        self.assertEqual(self.request('/api/ocr/example', auth=False)[0], 401)
        request = urllib.request.Request(self.base + '/api/ocr/example',
                                        headers={'Authorization': 'Bearer ' + self.key})
        with self.opener.open(request, timeout=10) as response:
            self.assertEqual(response.headers['Content-Type'], 'image/png')
            raw = response.read()
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.size, (1280, 591))
            image.verify()
        self.assertEqual(self.request('/api/ocr', {'image': base64.b64encode(raw).decode('ascii')})[0], 200)

    def test_ocr_shares_inference_slot_with_chat(self):
        with self.server.inference:
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 429)
            self.assertEqual(self.request('/api/health')[0], 200)

    def test_ocr_backend_errors_allow_retry(self):
        for error, status in [(TimeoutError(), 504), (OSError(), 502)]:
            with patch.object(self.server, 'backend_json', side_effect=error):
                self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], status)
            self.assertFalse(self.server.inference.locked())
        for response in ({'error': 'vision unsupported'}, {}, {'message': {}}, []):
            with patch.object(self.server, 'backend_json', side_effect=[{'capabilities': ['vision']}, response]):
                self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 502)
            self.assertFalse(self.server.inference.locked())
        self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 200)

    def test_api_namespace_includes_health_and_readiness(self):
        self.assertEqual(self.request('/api/health', auth=False)[0], 200)
        self.assertEqual(self.request('/api/ready', auth=False)[0], 401)
        self.assertEqual(self.request('/api/ready')[0], 200)
        status, index = self.request('/api', auth=False)
        self.assertEqual(status, 200)
        self.assertIn('/api/ocr', index['endpoints']['POST'])

    def test_public_hostname_same_origin_login_and_ocr(self):
        # Simulate the port-forwarded request while still keeping tests offline.
        headers = {'Host': 'sonno.iptime.org:8082', 'Origin': 'http://sonno.iptime.org:8082',
                   'Content-Type': 'application/json'}
        request = urllib.request.Request(self.base + '/api/session-login', headers=headers,
            data=json.dumps({'user_id': 'admin', 'password': self.key}).encode())
        with self.opener.open(request) as response:
            self.assertEqual(response.status, 200)
            headers['Cookie'] = response.headers['Set-Cookie'].split(';')[0]
        request = urllib.request.Request(self.base + '/api/ocr', headers=headers,
            data=json.dumps({'image': self.image(), 'engine': 'gemma'}).encode())
        with self.opener.open(request) as response:
            self.assertEqual(json.load(response)['text'], '안녕하세요')

    def test_ocr_defaults_to_gemma_with_or_without_instructions(self):
        with patch('server.tesseract_ocr') as tesseract:
            for extra in ({}, {'instructions': 'Keep lines'}, {'prompt': 'Read text'}):
                with self.subTest(extra=extra):
                    status, result = self.request('/api/ocr', {'image': self.image(), **extra})
                    self.assertEqual(status, 200)
                    self.assertEqual(result['engine'], 'gemma')
                    self.assertEqual(result['requested_model'], 'gemma4:e4b')
                    self.assertEqual(result['text'], '안녕하세요')
                    self.assertEqual(self.backend.received_path, '/api/chat')
            tesseract.assert_not_called()

    def test_gemma_default_never_falls_back_to_tesseract(self):
        with patch('server.tesseract_ocr') as tesseract:
            with patch.object(self.server, 'backend_json', side_effect=OSError('unavailable')):
                self.assertEqual(self.request('/api/ocr', {'image': self.image()})[0], 502)
            with patch.object(self.server, 'backend_json', return_value={'capabilities': ['completion']}):
                self.assertEqual(self.request('/api/ocr', {'image': self.image()})[0], 422)
            tesseract.assert_not_called()
        self.assertFalse(self.server.inference.locked())

    def test_tesseract_requires_explicit_engine_and_preserves_response_aliases(self):
        with patch('server.tesseract_ocr', return_value={'response': 'OCR text', 'model': 'Tesseract (kor+eng)'}) as engine:
            status, result = self.request('/api/ocr', {'image': self.image(), 'engine': 'tesseract'})
            self.assertEqual(status, 200)
            self.assertEqual(result['engine'], 'tesseract')
            self.assertEqual(result['text'], result['response'])
            self.assertEqual(result['requested_model'], 'Tesseract (kor+eng)')
            engine.assert_called_once()
        for error, code in [(RuntimeError('missing'), 503), (subprocess.TimeoutExpired('tesseract', 90), 504)]:
            with patch('server.tesseract_ocr', side_effect=error):
                self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'tesseract'})[0], code)
            self.assertFalse(self.server.inference.locked())

    def test_local_ocr_request_compatibility(self):
        status, result = self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma', 'instructions': 'Keep lines'})
        self.assertEqual(status, 200)
        self.assertEqual(result['text'], result['response'])
        self.assertIn('Keep lines', self.backend.received['messages'][0]['content'])
        status, legacy = self.request('/api/ocr', {'image': self.image(), 'prompt': 'Read text'})
        self.assertEqual(status, 200)
        self.assertEqual(legacy['engine'], 'gemma')
        self.assertEqual(legacy['text'], legacy['response'])
        self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma', 'instructions': 'x' * 4000})[0], 200)
        for extra in [{'engine': 'invalid'}, {'instructions': []}, {'instructions': 'x' * 4001},
                      {'prompt': 'x', 'instructions': 'y'}]:
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), **extra})[0], 400)
        with patch.object(self.server, 'backend_json', return_value={'capabilities': ['completion']}):
            self.assertEqual(self.request('/api/ocr', {'image': self.image(), 'engine': 'gemma'})[0], 422)
        self.assertFalse(self.server.inference.locked())

    def test_missing_key_prevents_startup(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                Config()


if __name__ == '__main__':
    unittest.main()
