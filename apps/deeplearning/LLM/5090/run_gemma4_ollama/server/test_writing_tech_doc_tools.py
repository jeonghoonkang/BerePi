import json
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

import server as gemma_server
from writing_tech_doc_tools import ToolValidationError, WritingTechDocToolRunner


class WritingTechDocToolRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.cli_path = root / "webdav_enhance.py"
        self.config_path = root / "this_config.conf"
        self.cli_path.write_text("# test CLI\n", encoding="utf-8")
        self.config_path.write_text("[webdav]\n", encoding="utf-8")
        self.runner = WritingTechDocToolRunner(
            self.cli_path,
            self.config_path,
            python_executable="python-test",
            timeout_seconds=30,
            max_output_chars=1000,
        )
        self.base = [
            "python-test",
            str(self.runner.cli_path),
            "--config",
            str(self.runner.config_path),
        ]

    def test_catalog_exposes_requested_function_tools(self):
        names = [item["function"]["name"] for item in self.runner.catalog()]
        self.assertEqual(names, ["boost", "list", "allom", "findm"])

    def test_prepare_builds_shell_free_boost_and_list_invocations(self):
        boost = self.runner.prepare({"tool": "boost", "dry_run": True, "file": "회의록.md"})
        self.assertEqual(boost.argv, [*self.base, "boost", "--dry-run", "--file", "회의록.md"])
        listing = self.runner.prepare({"tool": "ls"})
        self.assertEqual(listing.name, "list")
        self.assertEqual(listing.argv, [*self.base, "list"])

    def test_prepare_sends_allom_content_and_telegram_identity(self):
        invocation = self.runner.prepare({
            "tool": "allom",
            "content": "첫 줄\n둘째 줄",
            "room": "-1001",
            "topic": "42",
            "author": "7",
            "author_name": "alice",
        })
        self.assertEqual(
            invocation.argv,
            [
                *self.base, "allom", "--room=-1001", "--topic=42",
                "--author=7", "--author-name=alice",
            ],
        )
        self.assertEqual(invocation.stdin_text, "첫 줄\n둘째 줄")

    def test_prepare_makes_findm_noninteractive_and_validates_page_size(self):
        invocation = self.runner.prepare({"tool": "findm", "query": "서버 연동", "page_size": 7})
        self.assertEqual(
            invocation.argv,
            [*self.base, "findm", "--no-pager", "--page-size", "7", "--", "서버 연동"],
        )
        filtered = self.runner.prepare({
            "tool": "findm", "query": "서버 연동", "author": "7", "room": "-1001", "topic": "42",
        })
        self.assertEqual(
            filtered.argv,
            [
                *self.base, "findm", "--no-pager", "--author=7", "--room=-1001",
                "--topic=42", "--", "서버 연동",
            ],
        )
        with self.assertRaisesRegex(ToolValidationError, "between 1 and 1000"):
            self.runner.prepare({"tool": "findm", "query": "서버", "page_size": 0})

    def test_prepare_rejects_unknown_tool_fields(self):
        with self.assertRaisesRegex(ToolValidationError, "unsupported fields"):
            self.runner.prepare({"tool": "list", "command": "rm -rf"})
        with self.assertRaisesRegex(ToolValidationError, "one of"):
            self.runner.prepare({"tool": "unknown"})

    def test_run_returns_captured_result(self):
        completed = subprocess.CompletedProcess([], 0, stdout="목록 출력\n", stderr="")
        with patch("writing_tech_doc_tools.subprocess.run", return_value=completed) as run:
            result = self.runner.run({"tool": "list"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "목록 출력\n")
        run.assert_called_once_with(
            [*self.base, "list"],
            cwd=str(self.runner.cli_path.parent),
            input=None,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )


class WritingTechDocToolApiTests(unittest.TestCase):
    def setUp(self):
        class QuietHandler(gemma_server.Gemma4Handler):
            def log_message(self, format, *args):
                del format, args

            def remember_access(self):
                return

        self.runner = Mock()
        self.runner.status.return_value = {"enabled": True, "available": True}
        self.runner.catalog.return_value = WritingTechDocToolRunner.catalog()
        self.runner.run.return_value = {
            "ok": True,
            "tool": "list",
            "returncode": 0,
            "stdout": "파일 목록",
            "stderr": "",
            "output_truncated": False,
            "elapsed_seconds": 0.1,
        }
        self.runner_patch = patch.object(gemma_server, "WRITING_TECH_DOC_TOOL_RUNNER", self.runner)
        self.auth_patch = patch.object(gemma_server, "is_authorized_user", return_value=True)
        self.runner_patch.start()
        self.auth_patch.start()
        self.addCleanup(self.runner_patch.stop)
        self.addCleanup(self.auth_patch.stop)
        self.httpd = gemma_server.Gemma4ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def test_catalog_endpoint_returns_function_schemas(self):
        with urllib.request.urlopen(f"{self.base_url}/api/tools/writing-tech-doc", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertEqual(data["name"], "writing-tech-doc")
        self.assertEqual([item["function"]["name"] for item in data["tools"]],
                         ["boost", "list", "allom", "findm"])

    def test_execute_endpoint_dispatches_nested_arguments(self):
        request = urllib.request.Request(
            f"{self.base_url}/api/tools/writing-tech-doc",
            data=json.dumps({"tool": "list", "arguments": {}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 200)
        self.assertEqual(data["stdout"], "파일 목록")
        self.runner.run.assert_called_once_with({"tool": "list"})

    def test_tool_endpoint_requires_server_authentication(self):
        with (
            patch.object(gemma_server, "is_authorized_user", return_value=False),
            self.assertRaises(urllib.error.HTTPError) as raised,
        ):
            urllib.request.urlopen(f"{self.base_url}/api/tools/writing-tech-doc", timeout=3)

        self.assertEqual(raised.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
