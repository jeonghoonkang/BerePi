"""Network-local curl integration and status aggregation tests (stdlib only)."""

import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from format_models_gpus import summarize


def fixture():
    targets = []
    for name, gpu, eligible in [("one", "0", True), ("two", "0", True),
                                ("auto", "auto", True), ("off", "1", False)]:
        targets.append({"id": name, "host": "server", "model": "gemma4:31b",
                        "port": 8082, "selected_gpu": gpu, "dispatch_eligible": eligible,
                        "password": "must-not-print", "access_id": "private-user"})
    return {"targets": targets, "uptime": "1h"}


class StatusReportTests(unittest.TestCase):
    def test_deduplicates_models_and_gpus(self):
        report = summarize(fixture())
        self.assertEqual(report["dispatchable_targets"], 3)
        self.assertEqual(report["available_unique_models"], 1)
        self.assertEqual(report["known_selected_gpu_count"], 1)
        self.assertEqual(report["unresolved_gpu_targets"], ["auto"])
        self.assertNotIn("must-not-print", json.dumps(report))
        self.assertNotIn("private-user", json.dumps(report))

    def test_unknown_disabled_cpu_and_multiple_gpus(self):
        data = {"targets": [
            {"id": "unknown"},
            {"id": "disabled", "enabled": False, "dispatch_eligible": True},
            {"id": "cpu", "host": "a", "selected_gpu": "cpu", "dispatch_eligible": True},
            {"id": "multi", "host": "a", "selected_gpu": "0,1", "dispatch_eligible": True},
        ]}
        report = summarize(data)
        self.assertEqual(report["unknown_availability_targets"], 1)
        self.assertEqual(report["dispatchable_targets"], 2)
        self.assertEqual(report["known_selected_gpu_count"], 2)

    def test_authenticated_metrics_take_precedence(self):
        data = fixture()
        data["metrics"] = {"one": {"dispatch_eligible": False, "pending_queue": 3}}
        report = summarize(data)
        self.assertTrue(report["detail_available"])
        self.assertEqual(report["dispatchable_targets"], 2)
        self.assertEqual(report["targets"][0]["metrics"]["pending_queue"], 3)

    def test_curl_script_with_password_and_http_errors(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get("X-LLM-Routing-Password")))
                self.send_response(200 if len(seen) == 1 else 503)
                self.end_headers()
                self.wfile.write(json.dumps(fixture()).encode())

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            env = dict(os.environ, LLM_ROUTING_PASSWORD='test"\\secret')
            command = ["bash", str(Path(__file__).with_name("list_models_gpus.sh")),
                       "http://127.0.0.1:{}".format(server.server_port), "--json"]
            result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads(result.stdout)["dispatchable_targets"], 3)
            self.assertEqual(seen[0], ("/api/status", env["LLM_ROUTING_PASSWORD"]))
            self.assertNotEqual(subprocess.run(command, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE).returncode, 0)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
