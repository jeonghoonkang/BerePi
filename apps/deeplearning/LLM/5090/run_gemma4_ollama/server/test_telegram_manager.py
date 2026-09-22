import http.client
import json
import os
import subprocess
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

    def test_reload_reads_shell_again_and_preserves_web_precedence(self):
        self.manager.bot_dir.mkdir()
        config = self.manager.bot_dir / "this_conf_keys.sh"
        config.write_text('GEMMA4_USER_ID="updated"\n', encoding="utf-8")
        exported = subprocess.CompletedProcess([], 0, b"GEMMA4_USER_ID=updated\0TELEGRAM_BOT_TOKEN=123:test-token\0")
        with patch.dict(os.environ, {}, clear=True), patch("telegram_manager.subprocess.run", return_value=exported) as run:
            self.assertEqual(self.manager.status()["config"]["GEMMA4_USER_ID"], "")
            state = self.manager.reload()
            self.assertEqual(state["config"]["GEMMA4_USER_ID"], "updated")
            self.assertTrue(state["secrets_set"]["TELEGRAM_BOT_TOKEN"])
            self.assertNotIn("test-token", json.dumps(state))
            self.assertEqual(run.call_args.kwargs["cwd"], config.parent)
            self.assertIn("set -a", run.call_args.args[0][2])
            self.manager.save({"GEMMA4_USER_ID": "web-user"})
            self.assertEqual(self.manager.reload()["config"]["GEMMA4_USER_ID"], "web-user")
            self.assertEqual(run.call_count, 2)
            self.assertTrue(self.manager.status()["config_sources"]["web_exists"])

    def test_reload_failure_reports_path_without_shell_secrets(self):
        self.manager.bot_dir.mkdir()
        config = self.manager.bot_dir / "this_conf_keys.sh"
        config.touch()
        previous = dict(self.manager.legacy)
        failure = subprocess.CalledProcessError(1, "bash", stderr=b"private-token")
        with patch.dict(os.environ, {}, clear=True), patch("telegram_manager.subprocess.run", side_effect=failure):
            with self.assertRaises(ValueError) as raised:
                self.manager.reload()
        self.assertIn(str(config.resolve()), str(raised.exception))
        self.assertNotIn("private-token", str(raised.exception))
        self.assertEqual(self.manager.legacy, previous)

    def test_reload_missing_explicit_file(self):
        missing = self.root / "missing.sh"
        with patch.dict(os.environ, {"TELEGRAM_CONFIG_FILE": str(missing)}):
            with self.assertRaisesRegex(ValueError, "missing.sh"):
                self.manager.reload()

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
            self.assertEqual(request("POST", {"action": "reload"})[0], 401)
            with patch.object(server, "authenticated_session_user", return_value="admin"):
                self.assertEqual(request("GET")[0], 200)
                with patch.object(self.manager, "reload", return_value=self.manager.status()) as reload:
                    self.assertEqual(request("POST", {"action": "reload"}, {"Content-Type": "application/json"})[0], 200)
                    reload.assert_called_once_with()
                status, _ = request("POST", {"action": "save", "config": {"TELEGRAM_BOT_TOKEN": "123:test-token"}}, {"Content-Type": "application/json"})
                self.assertEqual(status, 200)
                self.assertNotIn("test-token", json.dumps(request("GET")[1]))
                self.assertEqual(request("POST", {"action": "stop"}, {"Content-Type": "application/json", "Origin": "https://evil.example"})[0], 403)
                self.assertEqual(request("POST", {"action": "exec"}, {"Content-Type": "application/json"})[0], 400)


if __name__ == "__main__":
    unittest.main()
