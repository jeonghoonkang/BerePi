import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from telegram_manager import TelegramManager, FIELDS


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manager = TelegramManager(self.root, self.root / "logs", 2500)
        self.manager.legacy = dict.fromkeys(FIELDS, "")
        self.manager.legacy["LLM_API_URL"] = "http://127.0.0.1:2500/api/generate"
        self.addCleanup(self.manager.stop)

    def test_settings_keep_secrets_and_reject_commands(self):
        result = self.manager.save({"TELEGRAM_BOT_TOKEN": "123:test-token", "GEMMA4_PASSWORD": "private"})
        self.assertNotIn("test-token", json.dumps(result))
        self.assertNotIn("private", json.dumps(result))
        self.manager.save({"TELEGRAM_BOT_TOKEN": "", "GEMMA4_PASSWORD": "", "GEMMA4_USER_ID": "operator"})
        self.assertEqual(self.manager.config()["GEMMA4_PASSWORD"], "private")
        self.assertTrue(result["secrets_set"]["TELEGRAM_BOT_TOKEN"])
        for changes in ({"command": "sh evil"}, {"LLM_API_URL": "file:///etc/passwd"}, {"ALLOWED_TELEGRAM_USER_IDS": "abc"}):
            with self.assertRaises(ValueError):
                self.manager.save(changes)
        reloaded = TelegramManager(self.root, self.root / "logs", 2500)
        reloaded.legacy = dict(self.manager.legacy)
        self.assertEqual(reloaded.config()["GEMMA4_USER_ID"], "operator")

    def test_lifecycle_lock_and_restart(self):
        self.manager.save({"TELEGRAM_BOT_TOKEN": "123:test-token"})
        (self.manager.bot_dir / "bot.py").write_text("import time\ntime.sleep(120)\n")
        with patch.dict(os.environ, {"TELEGRAM_PYTHON": sys.executable}):
            first = self.manager.start()
            self.assertTrue(first["running"])
            self.assertEqual(first["pid"], self.manager.start()["pid"])
            other = TelegramManager(self.root, self.root / "logs", 2500)
            other.legacy = dict(self.manager.legacy)
            self.assertTrue(other.status()["external_running"])
            with self.assertRaises(ValueError):
                other.start()
            self.manager.save({"GEMMA4_USER_ID": "new-user"})
            self.assertTrue(self.manager.status()["restart_required"])
            restarted = self.manager.restart()
            self.assertTrue(restarted["running"])
            self.assertNotEqual(first["pid"], restarted["pid"])
            self.assertFalse(restarted["restart_required"])
            self.manager.stop()
            self.assertFalse(self.manager.status()["running"])
            (self.manager.bot_dir / "bot.py").write_text("raise SystemExit(7)\n")
            self.assertFalse(self.manager.start()["running"])
            self.assertIn("7", self.manager.status()["message"])

    def test_authenticated_api_and_origin_validation(self):
        httpd = server.Gemma4ThreadingHTTPServer(("127.0.0.1", 0), server.Gemma4Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        def request(method, body=None, headers=None):
            conn = http.client.HTTPConnection(*httpd.server_address)
            conn.request(method, "/api/telegram", json.dumps(body) if body is not None else None, headers or {})
            response = conn.getresponse()
            data = json.loads(response.read())
            conn.close()
            return response.status, data
        with patch.object(server, "TELEGRAM_MANAGER", self.manager), patch.object(server.Gemma4Handler, "remember_access"):
            self.assertEqual(request("GET")[0], 401)
            self.assertEqual(request("POST", {"action": "start"})[0], 401)
            with patch.object(server, "authenticated_session_user", return_value="admin"):
                self.assertEqual(request("GET")[0], 200)
                status, _ = request("POST", {"action": "save", "config": {"TELEGRAM_BOT_TOKEN": "123:test-token"}}, {"Content-Type": "application/json"})
                self.assertEqual(status, 200)
                self.assertNotIn("test-token", json.dumps(request("GET")[1]))
                self.assertEqual(request("POST", {"action": "stop"}, {"Content-Type": "application/json", "Origin": "https://evil.example"})[0], 403)
                self.assertEqual(request("POST", {"action": "exec"}, {"Content-Type": "application/json"})[0], 400)


if __name__ == "__main__":
    unittest.main()
