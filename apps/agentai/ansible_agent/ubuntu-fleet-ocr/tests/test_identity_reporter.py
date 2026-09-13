from concurrent.futures import ThreadPoolExecutor
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "roles/sononet_edge/files/health_reporter.py"
SPEC = importlib.util.spec_from_file_location("identity_reporter", MODULE_PATH)
REPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTER)


class IdentityReporterTest(unittest.TestCase):
    def test_local_only_client_skips_http_and_marks_check_unverified(self):
        for settings in ({"SONONET_DEVICE_ID": "LOCAL-1"},
                         {"SONONET_DEVICE_ID": "LOCAL-1", "FLEET_API_URL": "https://fleet.test"}):
            with self.subTest(settings=settings), mock.patch.dict(REPORTER.os.environ, settings, clear=True), \
                    mock.patch.object(REPORTER, "get_instance_id", return_value="a" * 32), \
                    mock.patch.object(REPORTER, "record_id_check") as record, \
                    mock.patch.object(REPORTER.urllib.request, "urlopen") as urlopen, \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(REPORTER.main(), 0)
                urlopen.assert_not_called()
                record.assert_called_once_with({}, "LOCAL-1", "a" * 32,
                                                Path("/var/lib/sononet/id-conflict.json"))
                self.assertIn("heartbeat_skipped", stdout.getvalue())

    def test_local_only_event_reporting_does_not_send_http(self):
        spec = importlib.util.spec_from_file_location("local_event_reporter", MODULE_PATH.with_name("report_event.py"))
        reporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reporter)
        with mock.patch.dict(reporter.os.environ, {"SONONET_DEVICE_ID": "LOCAL-1"}, clear=True), \
                mock.patch.object(reporter.sys, "argv", ["report_event.py", "started", "info", "test"]), \
                mock.patch.object(reporter.urllib.request, "urlopen") as urlopen:
            self.assertEqual(reporter.main(), 0)
            urlopen.assert_not_called()

    def test_instance_identity_is_persistent_and_independent_per_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with ThreadPoolExecutor(max_workers=8) as pool:
                values = list(pool.map(REPORTER.get_instance_id, [root / "instance-id"] * 16))
            self.assertEqual(len(set(values)), 1)
            self.assertNotEqual(values[0], REPORTER.get_instance_id(root / "other-instance"))
            self.assertEqual((root / "instance-id").stat().st_mode & 0o777, 0o600)
            (root / "instance-id").write_text("corrupt")
            with self.assertRaises(ValueError):
                REPORTER.get_instance_id(root / "instance-id")

    def test_conflict_is_logged_saved_and_replaced_by_clear_result(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "id-conflict.json"
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                REPORTER.record_id_check({"id_check": {"status": "conflict", "instance_count": 2,
                                                       "checked_at": 100}}, "LAB-1", "a" * 32, status)
            self.assertIn("device_id_conflict", stderr.getvalue())
            self.assertEqual(json.loads(status.read_text())["status"], "conflict")
            REPORTER.record_id_check({"id_check": {"status": "clear", "instance_count": 1,
                                                   "checked_at": 200}}, "LAB-1", "a" * 32, status)
            self.assertEqual(json.loads(status.read_text())["status"], "clear")
            self.assertEqual(status.stat().st_mode & 0o777, 0o600)

    def test_old_server_or_failed_check_is_not_reported_as_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "id-conflict.json"
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                REPORTER.record_id_check({}, "LAB-1", "a" * 32, status)
            self.assertEqual(json.loads(status.read_text())["status"], "unverified")
            self.assertIn("device_id_check_unverified", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
