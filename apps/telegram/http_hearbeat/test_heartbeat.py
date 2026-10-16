import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest

import heartbeat as h


def status():
    return {"targets": [{"id": "a", "name": "GPU A", "enabled": True,
                         "model": "model-a", "host": "backend", "port": 8000}],
            "metrics": {"a": {"status": "ok", "available_targets": 1,
                               "last_health_probe_at": time.time()}}}


class StatusTests(unittest.TestCase):
    def test_healthy_authenticated_response_has_no_top_level_ok(self):
        self.assertEqual(h.inspect_status(status(), time.time(), 300), {})

    def test_public_response_is_not_healthy(self):
        self.assertIn("routing:auth", h.inspect_status({"ok": True, "status": "ready", "targets": []}, time.time(), 300))

    def test_bad_and_stale_target_identified(self):
        data = status()
        data["metrics"]["a"].update(status="error", available_targets=0, last_health_probe_at=1)
        issues = h.inspect_status(data, time.time(), 300)
        self.assertIn("model-a", issues["target:a"])
        self.assertIn("backend:8000", issues["target:a"])

    def test_disabled_target_and_empty_configuration(self):
        data = status()
        data["targets"][0]["enabled"] = False
        self.assertEqual(set(h.inspect_status(data, time.time(), 300)), {"routing:empty"})

    def test_unknown_capacity_does_not_mean_failure(self):
        data = status()
        data["metrics"]["a"]["available_targets"] = None
        self.assertEqual(h.inspect_status(data, time.time(), 300), {})


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.config = {"name": "test", "failure_threshold": 2, "reminder_seconds": 100}
        self.state = {}
        self.messages = []

    def cycle(self, issues, now):
        h.update_state(self.state, issues, self.config, now, self.messages.append)

    def test_threshold_suppression_reminder_recovery(self):
        self.cycle({"target:a": "bad"}, 1)
        self.assertEqual(self.messages, [])
        self.cycle({"target:a": "bad"}, 2)
        self.cycle({"target:a": "bad"}, 3)
        self.assertEqual(len(self.messages), 1)
        self.cycle({"target:a": "bad"}, 102)
        self.assertEqual(len(self.messages), 2)
        self.cycle({}, 103)
        self.assertIn("복구", self.messages[-1])
        self.cycle({}, 104)
        self.assertEqual(len(self.messages), 3)

    def test_router_outage_does_not_recover_backend(self):
        self.cycle({"target:a": "bad"}, 1)
        self.cycle({"target:a": "bad"}, 2)
        self.cycle({"routing:connection": "offline"}, 3)
        self.cycle({"routing:connection": "offline"}, 4)
        self.assertIn("target:a", self.state["active"])
        self.assertNotIn("복구", self.messages[-1])

    def test_failed_delivery_is_not_acknowledged(self):
        self.cycle({"target:a": "bad"}, 1)
        def fail(message):
            raise h.CheckError("network")
        with self.assertRaises(h.CheckError):
            h.update_state(self.state, {"target:a": "bad"}, self.config, 2, fail)
        self.assertNotIn("active", self.state)
        self.cycle({"target:a": "bad"}, 3)
        self.assertEqual(len(self.messages), 1)

    def test_restart_preserves_notification_state(self):
        self.cycle({}, 1)
        self.state = json.loads(json.dumps(self.state))
        self.cycle({}, 2)
        self.assertEqual(len(self.messages), 1)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/health")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                if self.path == "/html":
                    self.wfile.write(b"<html>login</html>")
                    return
                data = {"ok": True}
                if self.path == "/api/status":
                    data = status() if self.headers.get("Authorization") == "Bearer secret" else {"ok": True, "targets": []}
                self.wfile.write(json.dumps(data).encode())
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_collect_with_auth_and_invalid_password(self):
        config = {"url": self.url, "password": "secret", "timeout_seconds": 2, "max_status_age_seconds": 300}
        self.assertEqual(h.collect(config), {})
        config["password"] = "wrong"
        self.assertIn("routing:auth", h.collect(config))

    def test_html_and_redirect_rejected(self):
        for path in ("/html", "/redirect"):
            with self.subTest(path=path), self.assertRaises(h.CheckError):
                h.request_json(self.url + path, 2, "secret")

    def test_connection_failure(self):
        with self.assertRaises(h.CheckError):
            h.request_json("http://127.0.0.1:0/health", 0.1)


if __name__ == "__main__":
    unittest.main()
