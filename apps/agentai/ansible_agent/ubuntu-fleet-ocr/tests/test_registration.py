from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient


PROJECT = Path(__file__).parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLIENT = load_module("fleet_registration_client", PROJECT / "client/register_device.py")


class RegistrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.enrollment = "enrollment-" + "e" * 40
        self.admin = "admin-" + "a" * 40
        with mock.patch.dict(os.environ, {
            "FLEET_DB_PATH": str(self.root / "fleet.sqlite3"),
            "FLEET_HMAC_SECRET": "h" * 64,
            "ADMIN_TOKEN": self.admin,
            "FLEET_ENROLLMENT_TOKEN": self.enrollment,
        }):
            self.api = load_module("fleet_registration_api", PROJECT / "central/api/main.py")
        self.http = TestClient(self.api.app)
        self.addCleanup(self.http.close)

    def enroll(self, key):
        response = self.http.post("/v1/devices/register",
                                  json={"registration_key": key},
                                  headers={"Authorization": "Bearer " + self.enrollment})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def report_identity(self, device_id, instance_id):
        response = self.http.post("/v1/heartbeat", json={
            "device_id": device_id, "instance_id": instance_id,
            "observed_at": "2026-09-13T00:00:00Z", "hostname": "same-hostname",
        }, headers={"Authorization": "Bearer " + self.api.expected_device_token(device_id)})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["id_check"]

    def test_manual_id_is_kept_even_when_duplicated_and_allocator_is_not_used(self):
        body = {"device_id": "LAB-042"}
        headers = {"Authorization": "Bearer " + self.enrollment}
        first = self.http.post("/v1/devices/manual", json=body, headers=headers)
        second = self.http.post("/v1/devices/manual", json=body, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["device_id"], "LAB-042")
        with self.api.connect() as database:
            self.assertEqual(database.execute("SELECT next_number FROM device_sequence").fetchone()[0], 1)
        self.assertEqual(self.http.post("/v1/devices/manual", json=body).status_code, 401)
        self.assertEqual(self.http.post("/v1/devices/manual", json={"device_id": "../escape"},
                                       headers=headers).status_code, 422)

    def test_manual_client_requests_auth_without_registration_key_or_allocator(self):
        state = self.root / "registration.json"
        opener = mock.Mock()

        def request_server(request, timeout):
            self.assertTrue(request.full_url.endswith("/v1/devices/manual"))
            self.assertEqual(json.loads(request.data), {"device_id": "LAB-042"})
            response = self.http.post("/v1/devices/manual", content=request.data,
                                      headers=dict(request.header_items()))
            return io.BytesIO(response.content)

        opener.open.side_effect = request_server
        with mock.patch.object(CLIENT, "build_opener", return_value=opener):
            result = CLIENT.register("https://fleet.test", self.enrollment, state, requested_id="LAB-042")
        self.assertEqual(result["device_id"], "LAB-042")
        self.assertFalse(state.exists())

    def test_custom_id_server_port_prefix_and_mode_specific_paths(self):
        for requested_id, path, api_route in (
            (None, "/custom/issue", "/v1/devices/register"),
            ("LAB-042", "/custom/authorize", "/v1/devices/manual"),
        ):
            with self.subTest(requested_id=requested_id):
                opener = mock.Mock()

                def request_server(request, timeout):
                    self.assertEqual(request.full_url, "https://id.test:8443/fleet" + path)
                    response = self.http.post(api_route, content=request.data,
                                              headers=dict(request.header_items()))
                    self.assertEqual(response.status_code, 200)
                    return io.BytesIO(response.content)

                opener.open.side_effect = request_server
                with mock.patch.object(CLIENT, "build_opener", return_value=opener):
                    result = CLIENT.register("https://id.test:8443/fleet/", self.enrollment,
                                             self.root / "registration.json", requested_id=requested_id,
                                             registration_path="/custom/issue", manual_path="/custom/authorize")
                self.assertEqual(result["device_id"], requested_id or "SN-000001")

    def test_main_reads_id_server_settings_and_preserves_legacy_defaults(self):
        common = {"FLEET_API_URL": "https://health.test", "FLEET_ENROLLMENT_TOKEN": self.enrollment,
                  "SONONET_ID_MODE": "manual", "SONONET_DEVICE_ID": "LAB-1"}
        for overrides, expected_base, expected_register, expected_manual in (
            ({}, "https://health.test", "/v1/devices/register", "/v1/devices/manual"),
            ({"FLEET_ID_API_URL": "", "FLEET_ID_REGISTER_PATH": "", "FLEET_ID_MANUAL_PATH": ""},
             "https://health.test", "/v1/devices/register", "/v1/devices/manual"),
            ({"FLEET_ID_API_URL": "https://id.test", "FLEET_ID_REGISTER_PATH": "/issue", "FLEET_ID_MANUAL_PATH": "/auth"},
             "https://id.test", "/issue", "/auth"),
        ):
            with self.subTest(overrides=overrides), mock.patch.dict(os.environ, {**common, **overrides}, clear=True), \
                    mock.patch.object(CLIENT.sys, "argv", ["register_device.py", str(self.root / "state.json")]), \
                    mock.patch.object(CLIENT, "register", return_value={"device_id": "LAB-1", "device_token": "x" * 43}) as register, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(CLIENT.main(), 0)
                register.assert_called_once_with(expected_base, self.enrollment, self.root / "state.json",
                                                  requested_id="LAB-1", registration_path=expected_register,
                                                  manual_path=expected_manual)

    def test_invalid_endpoint_is_rejected_before_state_or_network(self):
        for base, path in (("http://id.test", "/issue"), ("https://user:pass@id.test", "/issue"),
                           ("https://id.test:bad", "/issue"), ("https://id.test", "https://other.test/issue"),
                           ("https://id.test", "//other.test/issue"), ("https://id.test", "/../issue"),
                           ("https://id.test", "/issue?redirect=elsewhere"), ("https://id.test", "issue")):
            with self.subTest(base=base, path=path), mock.patch.object(CLIENT, "build_opener") as opener:
                state = self.root / "device" / "registration.json"
                with self.assertRaises(ValueError):
                    CLIENT.register(base, self.enrollment, state, registration_path=path)
                self.assertFalse(state.parent.exists())
                opener.assert_not_called()

    def test_same_server_path_change_reuses_registration_key(self):
        state = self.root / "registration.json"
        bodies = []
        opener = mock.Mock()

        def request_server(request, timeout):
            bodies.append(json.loads(request.data))
            response = self.http.post("/v1/devices/register", content=request.data,
                                      headers=dict(request.header_items()))
            return io.BytesIO(response.content)

        opener.open.side_effect = request_server
        with mock.patch.object(CLIENT, "build_opener", return_value=opener):
            first = CLIENT.register("https://id.test", self.enrollment, state)
            second = CLIENT.register("https://id.test", self.enrollment, state, registration_path="/new/issue")
        self.assertEqual(first, second)
        self.assertEqual(bodies[0], bodies[1])

    def test_duplicate_ids_warn_both_clients_and_are_visible_to_admin(self):
        self.assertEqual(self.report_identity("LAB-1", "a" * 32)["status"], "clear")
        self.assertEqual(self.report_identity("LAB-1", "a" * 32)["status"], "clear")
        with self.assertLogs("fleet.identity", level="WARNING"):
            second = self.report_identity("LAB-1", "b" * 32)
            first = self.report_identity("LAB-1", "a" * 32)
        self.assertEqual(first["status"], "conflict")
        self.assertEqual(second["instance_count"], 2)
        self.assertEqual(self.http.get("/v1/id-conflicts").status_code, 401)
        conflicts = self.http.get("/v1/id-conflicts",
                                  headers={"Authorization": "Bearer " + self.admin}).json()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["device_id"], "LAB-1")
        self.assertEqual(len(conflicts[0]["instances"]), 2)
        self.assertNotIn("device_token", json.dumps(conflicts))

    def test_changing_manual_id_clears_previous_claim(self):
        self.report_identity("OLD", "a" * 32)
        with self.assertLogs("fleet.identity", level="WARNING"):
            self.report_identity("OLD", "b" * 32)
        self.report_identity("NEW", "b" * 32)
        self.assertEqual(self.report_identity("OLD", "a" * 32)["status"], "clear")
        self.api.initialize_database()
        self.assertEqual(self.report_identity("NEW", "b" * 32)["instance_count"], 1)

    def test_offline_instance_expires_by_server_time_not_client_time(self):
        self.report_identity("LAB-1", "a" * 32)
        with self.api.connect() as database:
            database.execute("UPDATE device_instances SET last_seen=?",
                             (int(self.api.time.time()) - self.api.CONFLICT_WINDOW_SECONDS - 1,))
        self.assertEqual(self.report_identity("LAB-1", "b" * 32)["status"], "clear")
        with self.assertLogs("fleet.identity", level="WARNING"):
            self.assertEqual(self.report_identity("LAB-1", "a" * 32)["status"], "conflict")

    def test_legacy_clients_without_instance_id_are_unverified(self):
        response = self.http.post("/v1/heartbeat", json={"device_id": "LEGACY",
                                  "observed_at": "now", "hostname": "old"},
                                  headers={"Authorization": "Bearer " + self.api.expected_device_token("LEGACY")})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id_check"]["status"], "unverified")

    def test_unauthenticated_claim_cannot_create_conflict(self):
        self.report_identity("LAB-1", "a" * 32)
        response = self.http.post("/v1/heartbeat", json={"device_id": "LAB-1", "instance_id": "b" * 32,
                                  "observed_at": "now", "hostname": "fake"},
                                  headers={"Authorization": "Bearer wrong"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.report_identity("LAB-1", "a" * 32)["status"], "clear")

    def test_concurrent_devices_get_unique_numbers_and_tokens(self):
        keys = [secrets.token_hex(32) for _ in range(24)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(self.enroll, keys))
        self.assertEqual(len({r["device_id"] for r in results}), 24)
        self.assertEqual(len({r["device_token"] for r in results}), 24)
        self.assertEqual({r["device_id"] for r in results},
                         {f"SN-{i:06d}" for i in range(1, 25)})

    def test_concurrent_retries_and_restart_reuse_one_number(self):
        key = secrets.token_hex(32)
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(self.enroll, [key] * 24))
        self.assertTrue(all(result == results[0] for result in results))
        self.api.initialize_database()
        self.assertEqual(self.enroll(key), results[0])
        self.assertEqual(self.enroll(secrets.token_hex(32))["device_id"], "SN-000002")
        with self.api.connect() as database:
            row = database.execute("SELECT registration_hash FROM device_registry "
                                   "WHERE device_id='SN-000001'").fetchone()
        self.assertEqual(row[0], hashlib.sha256(key.encode()).hexdigest())

    def test_credentials_authorize_only_assigned_device(self):
        result = self.enroll(secrets.token_hex(32))
        payload = {"device_id": result["device_id"], "observed_at": "2026-09-13T00:00:00Z",
                   "hostname": "test-client"}
        headers = {"Authorization": "Bearer " + result["device_token"]}
        self.assertEqual(self.http.post("/v1/heartbeat", json=payload, headers=headers).status_code, 202)
        payload["device_id"] = "SN-999999"
        self.assertEqual(self.http.post("/v1/heartbeat", json=payload, headers=headers).status_code, 403)

    def test_existing_manual_ids_and_migration_are_reserved(self):
        self.http.post("/v1/heartbeat", json={"device_id": "SN-000001", "observed_at": "now",
                                            "hostname": "legacy"},
                       headers={"Authorization": "Bearer " + self.api.expected_device_token("SN-000001")})
        # Simulate old data before device_registry existed.
        with self.api.connect() as database:
            database.execute("INSERT INTO events(device_id, observed_at, event, payload) "
                             "VALUES ('SN-000002', 'now', 'boot', '{}')")
        self.api.initialize_database()
        self.assertEqual(self.enroll(secrets.token_hex(32))["device_id"], "SN-000003")

    def test_registration_auth_validation_and_admin_listing(self):
        body = {"registration_key": secrets.token_hex(32)}
        self.assertEqual(self.http.post("/v1/devices/register", json=body).status_code, 401)
        self.assertEqual(self.http.post("/v1/devices/register", json=body,
                                       headers={"Authorization": "Bearer wrong"}).status_code, 403)
        self.assertEqual(self.http.post("/v1/devices/register", json={"registration_key": "bad"},
                                       headers={"Authorization": "Bearer " + self.enrollment}).status_code, 422)
        with mock.patch.object(self.api, "ENROLLMENT_TOKEN", ""):
            self.assertEqual(self.http.post("/v1/devices/register", json=body).status_code, 503)
        result = self.enroll(body["registration_key"])
        self.assertEqual(self.http.get("/v1/registrations").status_code, 401)
        listing = self.http.get("/v1/registrations",
                                headers={"Authorization": "Bearer " + self.admin}).json()
        self.assertEqual(listing[0]["device_id"], result["device_id"])
        self.assertNotIn("registration_hash", listing[0])
        self.assertNotIn("device_token", listing[0])

    def test_client_lost_response_reuses_persisted_key_end_to_end(self):
        state = self.root / "device" / "registration.json"
        requests = []

        def request_server(request, timeout):
            # Bridge the real client's HTTP request to the real FastAPI handler.
            self.assertTrue(state.exists())
            self.assertEqual(state.stat().st_mode & 0o777, 0o600)
            requests.append(json.loads(request.data))
            response = self.http.post("/v1/devices/register", content=request.data,
                                      headers=dict(request.header_items()))
            self.assertEqual(response.status_code, 200, response.text)
            if len(requests) == 1:
                raise URLError("response lost after server commit")
            return io.BytesIO(response.content)

        opener = mock.Mock()
        opener.open.side_effect = request_server
        with mock.patch.object(CLIENT, "build_opener", return_value=opener), \
                mock.patch.object(CLIENT.time, "sleep"):
            first = CLIENT.register("https://fleet.test", self.enrollment, state)
            second = CLIENT.register("https://fleet.test", self.enrollment, state)
        self.assertEqual(first, second)
        self.assertTrue(all(body == requests[0] for body in requests))
        self.assertEqual(first["device_id"], "SN-000001")
        self.assertEqual(self.enroll(secrets.token_hex(32))["device_id"], "SN-000002")

    def test_client_network_failure_preserves_state_for_next_run(self):
        state = self.root / "device" / "registration.json"
        opener = mock.Mock()
        opener.open.side_effect = URLError("offline")
        with mock.patch.object(CLIENT, "build_opener", return_value=opener), \
                mock.patch.object(CLIENT.time, "sleep"):
            with self.assertRaises(RuntimeError):
                CLIENT.register("https://fleet.test", self.enrollment, state)
        self.assertTrue(state.exists())
        self.assertEqual(opener.open.call_count, 3)
        saved = state.read_bytes()
        with self.assertRaises(ValueError):
            CLIENT.register("https://other.test", self.enrollment, state)
        self.assertEqual(state.read_bytes(), saved)

    def test_client_rejects_plain_http_and_untrusted_response(self):
        state = self.root / "registration.json"
        with self.assertRaises(ValueError):
            CLIENT.register("http://fleet.test", self.enrollment, state)
        self.assertFalse(state.exists())
        opener = mock.Mock()
        opener.open.return_value = io.BytesIO(json.dumps({
            "device_id": "SN-000001; touch /tmp/injected", "device_token": "a" * 43,
        }).encode())
        with mock.patch.object(CLIENT, "build_opener", return_value=opener):
            with self.assertRaises(ValueError):
                CLIENT.register("https://fleet.test", self.enrollment, state)

    def test_client_does_not_retry_auth_errors_or_follow_redirects(self):
        state = self.root / "registration.json"
        opener = mock.Mock()
        opener.open.side_effect = HTTPError("https://fleet.test", 403, "Forbidden", {}, None)
        with mock.patch.object(CLIENT, "build_opener", return_value=opener):
            with self.assertRaises(RuntimeError):
                CLIENT.register("https://fleet.test", self.enrollment, state)
        self.assertEqual(opener.open.call_count, 1)
        self.assertIsNone(CLIENT.NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.test"))


if __name__ == "__main__":
    unittest.main()
