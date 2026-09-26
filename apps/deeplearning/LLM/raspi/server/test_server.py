"""HTTP integration tests; no Ollama installation or model download needed."""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from server import Config, Server


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
        if data.get('prompt') == 'block':
            self.server.entered.set()
            self.server.release.wait(5)
        failed = data.get('prompt') == 'fail'
        self.send_response(500 if failed else 200)
        self.end_headers()
        response = {'response': '안녕하세요', 'done': True}
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

    def test_missing_key_prevents_startup(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                Config()


if __name__ == '__main__':
    unittest.main()
