from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from check_routing import RoutingCheckError, check_routing


class FakeRoutingHandler(BaseHTTPRequestHandler):
    password = "test-secret"

    def log_message(self, format: str, *args: object) -> None:
        return

    def write_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self.write_json(
                {
                    "ok": True,
                    "status": "ready",
                    "model": "fake-model",
                    "target_count": 1,
                    "targets": [{"id": "fake-target"}],
                }
            )
            return
        self.write_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self.write_json({"error": "not found"}, 404)
            return
        if self.headers.get("Authorization") != f"Bearer {self.password}":
            self.write_json({"ok": False, "error": "invalid api password"}, 401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.write_json(
            {
                "ok": True,
                "target_name": "fake-target",
                "model": "fake-model",
                "response": "OK" if payload.get("prompt") else "",
            }
        )


class RoutingSmokeCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRoutingHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_status_and_generation_pass(self) -> None:
        result = check_routing(self.base_url, password="test-secret", timeout=5)
        self.assertTrue(result.ok)
        self.assertEqual(result.response, "OK")
        self.assertEqual(result.target_name, "fake-target")

    def test_invalid_password_fails(self) -> None:
        with self.assertRaisesRegex(RoutingCheckError, "HTTP 401"):
            check_routing(self.base_url, password="wrong", timeout=5)

    def test_missing_password_fails_before_generation(self) -> None:
        with self.assertRaisesRegex(RoutingCheckError, "needs a password"):
            check_routing(self.base_url, password="", timeout=5)


if __name__ == "__main__":
    unittest.main()
