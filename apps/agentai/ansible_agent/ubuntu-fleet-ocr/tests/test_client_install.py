"""Exercise installer sequencing with system paths redirected and host commands mocked.

These tests do not install packages, contact servers, or run systemd on the host.
An Ubuntu deployment with real credentials remains an integration check.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).parents[1] / "client" / "install.sh"


class ClientInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / "commands.log"
        self.config = self.root / "input.env"
        self.config.write_text(
            "SONONET_DEVICE_ID=TEST-001\n"
            "NEXTCLOUD_URL=https://cloud.test\nNEXTCLOUD_USER=test-device\n"
            "NEXTCLOUD_APP_PASSWORD='test password'\n"
            "OCR_API_BASE_URL=https://ocr.test\nOCR_API_KEY=test-key\n"
            "FLEET_API_URL=https://fleet.test\nDEVICE_TOKEN=test-token\n"
        )
        (self.root / "os-release").write_text("ID=ubuntu\n")
        (self.root / "systemd").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Only redirect host paths and the root check in this disposable copy.
        script = INSTALLER.read_text().replace("${EUID} -ne 0", "0 -ne 0")
        for original, replacement in {
            "/etc/os-release": str(self.root / "os-release"),
            "/run/systemd/system": str(self.root / "systemd"),
            "/run/lock/sononet-ansible-pull.lock": str(self.root / "pull.lock"),
            "/etc/sononet": str(self.root / "etc"),
            "/var/lib/sononet/ansible": str(self.root / "checkout"),
        }.items():
            script = script.replace(original, replacement)
        self.script = self.root / "install.sh"
        self.script.write_text(script)
        # Mock the registration transport; real API/HTTP-adapter tests live in test_registration.
        (self.root / "register_device.py").write_text(
            "import os, sys\n"
            "from pathlib import Path\n"
            "if os.environ.get('TEST_FAIL_REGISTRATION'): sys.exit(19)\n"
            "Path(sys.argv[1]).write_text('test-registration-state')\n"
            "print('SONONET_DEVICE_ID=' + (os.environ.get('SONONET_DEVICE_ID') or 'SN-000042'))\n"
            "print('DEVICE_TOKEN=' + 'x' * 43)\n"
        )
        mock_command = '''#!/usr/bin/env bash
set -eu
name=${0##*/}
printf '%s' "$name" >> "$TEST_LOG"
printf ' <%s>' "$@" >> "$TEST_LOG"
printf '\\n' >> "$TEST_LOG"
if [[ "$name" == "${TEST_FAIL_COMMAND:-}" ]]; then exit 17; fi
if [[ "$name" == install ]]; then
  args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -o|-g) shift 2 ;;
      *) args+=("$1"); shift ;;
    esac
  done
  "$TEST_REAL_INSTALL" "${args[@]}"
fi
'''
        for command in ("apt-get", "ansible-pull", "systemctl", "flock", "install"):
            target = self.bin / command
            target.write_text(mock_command)
            target.chmod(0o755)
        self.env = {
            "PATH": str(self.bin) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            "TEST_LOG": str(self.log),
            "TEST_REAL_INSTALL": shutil.which("install") or "/usr/bin/install",
        }

    def auto_configuration(self):
        text = self.config.read_text().replace("SONONET_DEVICE_ID=TEST-001", "SONONET_DEVICE_ID=")
        text = text.replace("DEVICE_TOKEN=test-token", "DEVICE_TOKEN=")
        self.config.write_text(text + "SONONET_ID_MODE=auto\nFLEET_ENROLLMENT_TOKEN=" + "e" * 40 + "\n")

    def test_automatic_identity_is_persisted_before_download(self) -> None:
        self.auto_configuration()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.root / "etc/device.env").read_text()
        self.assertIn("SONONET_DEVICE_ID=SN-000042", installed)
        self.assertIn("DEVICE_TOKEN=" + "x" * 43, installed)
        self.assertIn("NEXTCLOUD_REMOTE_PATH=/Fleet/SN-000042", installed)
        self.assertNotIn("x" * 43, result.stdout)
        self.assertNotIn("e" * 40, result.stdout)
        self.assertIn("ansible-pull <", self.log.read_text())

    def test_failed_registration_preserves_config_and_stops_installation(self) -> None:
        self.auto_configuration()
        installed = self.root / "etc/device.env"
        installed.parent.mkdir()
        installed.write_text("previous valid configuration\n")
        self.env["TEST_FAIL_REGISTRATION"] = "1"
        result = self.run_install()
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertEqual(installed.read_text(), "previous valid configuration\n")
        self.assertNotIn("ansible-pull <", self.log.read_text())
        self.assertNotIn("systemctl", self.log.read_text())

    def test_missing_enrollment_secret_fails_before_installation(self) -> None:
        self.auto_configuration()
        self.config.write_text(self.config.read_text() + "unset FLEET_ENROLLMENT_TOKEN\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(self.log.exists())

    def test_cli_forces_manual_id_and_persists_override(self) -> None:
        with self.config.open("a") as config:
            config.write("FLEET_ENROLLMENT_TOKEN=" + "e" * 40 + "\n")
        result = subprocess.run(["bash", str(self.script), str(self.config),
                                 "--device-id", "LAB-042"],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.root / "etc/device.env").read_text()
        self.assertIn("SONONET_ID_MODE=manual", installed)
        self.assertIn("SONONET_DEVICE_ID=LAB-042", installed)
        self.assertIn("NEXTCLOUD_REMOTE_PATH=/Fleet/LAB-042", installed)
        self.assertNotIn("DEVICE_TOKEN=" + "x" * 43, installed)
        self.assertFalse((self.root / "etc/registration.json").exists())
        self.assertNotIn("Requesting a unique device number", result.stdout)

    def test_default_saves_local_id_without_server_settings_or_helper(self) -> None:
        self.config.write_text(self.config.read_text().replace("DEVICE_TOKEN=test-token", "DEVICE_TOKEN=")
                               .replace("FLEET_API_URL=https://fleet.test", ""))
        (self.root / "register_device.py").unlink()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.root / "etc/device.env").read_text()
        self.assertIn("SONONET_ID_MODE=manual", installed)
        self.assertIn("SONONET_DEVICE_ID=TEST-001", installed)
        self.assertIn("SONONET_FETCH_DEVICE_TOKEN=0", installed)
        self.assertIn("서버에서 ID를 할당받을 수도 있습니다", result.stdout)
        self.assertIn("--server-id", result.stdout)
        self.assertIn("충돌 확인", result.stdout)
        self.assertFalse((self.root / "etc/registration.json").exists())

    def test_default_missing_id_does_not_fall_back_to_server(self) -> None:
        self.config.write_text(self.config.read_text().replace("SONONET_DEVICE_ID=TEST-001", "SONONET_DEVICE_ID=")
                               + "FLEET_ENROLLMENT_TOKEN=" + "e" * 40 + "\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("--server-id", result.stdout)
        self.assertFalse(self.log.exists())

    def test_server_id_flag_explicitly_requests_allocation(self) -> None:
        with self.config.open("a") as config:
            config.write("FLEET_ENROLLMENT_TOKEN=" + "e" * 40 + "\n")
        result = subprocess.run(["bash", str(self.script), str(self.config), "--server-id"],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.root / "etc/device.env").read_text()
        self.assertIn("SONONET_ID_MODE=auto", installed)
        self.assertIn("SONONET_DEVICE_ID=SN-000042", installed)
        self.assertIn("DEVICE_TOKEN=" + "x" * 43, installed)

    def test_manual_token_fetch_requires_explicit_opt_in(self) -> None:
        self.config.write_text(self.config.read_text().replace("DEVICE_TOKEN=test-token", "DEVICE_TOKEN=")
                               + "SONONET_FETCH_DEVICE_TOKEN=1\nFLEET_ENROLLMENT_TOKEN=" + "e" * 40 + "\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.root / "etc/device.env").read_text()
        self.assertIn("SONONET_DEVICE_ID=TEST-001", installed)
        self.assertIn("DEVICE_TOKEN=" + "x" * 43, installed)

    def test_conflicting_id_flags_are_rejected(self) -> None:
        result = subprocess.run(["bash", str(self.script), str(self.config), "--server-id",
                                 "--device-id", "LOCAL-1"], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.log.exists())

    def test_id_server_settings_persist_independently_of_heartbeat_server(self) -> None:
        with self.config.open("a") as config:
            config.write("FLEET_ID_API_URL=https://id.test:8443/fleet\n"
                         "FLEET_ID_REGISTER_PATH=/custom/issue\nFLEET_ID_MANUAL_PATH=/custom/auth\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.root / "etc/device.env"
        for setting in ("FLEET_API_URL=https://fleet.test", "FLEET_ID_API_URL=https://id.test:8443/fleet",
                        "FLEET_ID_REGISTER_PATH=/custom/issue", "FLEET_ID_MANUAL_PATH=/custom/auth"):
            self.assertIn(setting, installed.read_text())
        result = self.run_install(installed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FLEET_ID_API_URL=https://id.test:8443/fleet", installed.read_text())

    def test_manual_id_with_existing_token_does_not_request_registration(self) -> None:
        with self.config.open("a") as config:
            config.write("SONONET_ID_MODE=manual\n")
        self.env["TEST_FAIL_REGISTRATION"] = "1"
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "etc/registration.json").exists())

    def test_manual_id_rejects_missing_or_unsafe_input_without_auto_allocation(self) -> None:
        original = self.config.read_text()
        for device_id in ("", "../outside", "..", "ID;bad"):
            with self.subTest(device_id=device_id):
                self.config.write_text(original + "SONONET_ID_MODE=manual\n"
                                       + "SONONET_DEVICE_ID='" + device_id + "'\n")
                result = self.run_install()
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse(self.log.exists())

    def run_install(self, config: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.script), str(config or self.config)],
            env=self.env, text=True, capture_output=True,
        )

    def test_download_start_and_reuse_installed_configuration(self) -> None:
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text()
        self.assertIn("<https://github.com/jeonghoonkang/BerePi.git>", commands)
        self.assertIn("<-C> <master>", commands)
        self.assertIn("<apps/agentai/ansible_agent/ubuntu-fleet-ocr/local.yml>", commands)
        self.assertLess(commands.index("ansible-pull <"), commands.index("systemctl <start>"))
        self.assertIn("systemctl <start> <sononet-pipeline.service>", commands)
        self.assertIn("systemctl <start> <sononet-heartbeat.service>", commands)
        installed = self.root / "etc" / "device.env"
        self.assertEqual(installed.stat().st_mode & 0o777, 0o600)
        self.assertIn("SONONET_REPO_BRANCH=master", installed.read_text())
        self.assertIn("SONONET_PLAYBOOK_PATH=apps/agentai/", installed.read_text())
        result = self.run_install(installed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NEXTCLOUD_APP_PASSWORD='test password'", installed.read_text())

    def test_custom_repository_and_commit_verification(self) -> None:
        with self.config.open("a") as config:
            config.write("SONONET_REPO_URL=https://git.test/fleet.git\n"
                         "SONONET_REPO_BRANCH=stable\nSONONET_PLAYBOOK_PATH=local.yml\n"
                         "SONONET_VERIFY_COMMIT=1\n")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text()
        self.assertIn("<--verify-commit>", commands)
        self.assertIn("<https://git.test/fleet.git>", commands)
        self.assertIn("<-C> <stable>", commands)
        self.assertIn("<local.yml>", commands)

    def test_download_failure_does_not_start_services(self) -> None:
        self.env["TEST_FAIL_COMMAND"] = "ansible-pull"
        result = self.run_install()
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("systemctl", self.log.read_text())
        self.assertNotIn("first run completed", result.stdout)

    def test_first_run_failure_is_reported(self) -> None:
        self.env["TEST_FAIL_COMMAND"] = "systemctl"
        result = self.run_install()
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("first run completed", result.stdout)

    def test_placeholder_and_unsafe_path_fail_before_installation(self) -> None:
        original = self.config.read_text()
        for setting in ("DEVICE_TOKEN=CHANGE_ME", "OCR_API_KEY=CHANGE_ME",
                        "SONONET_PLAYBOOK_PATH=../local.yml"):
            with self.subTest(setting=setting):
                self.config.write_text(original + setting + "\n")
                result = self.run_install()
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse(self.log.exists())
                self.assertFalse((self.root / "etc").exists())

    def test_updater_preserves_relative_playbook_setting(self) -> None:
        wrapper = (INSTALLER.parents[1] / "roles/sononet_edge/templates/"
                   "sononet-ansible-pull.sh.j2").read_text()
        wrapper = wrapper.replace("source {{ sononet_config_dir }}/device.env",
                                  'source "' + str(self.config) + '"')
        wrapper = wrapper.replace("{{ sononet_repo_branch }}", "stable")
        wrapper = wrapper.replace("{{ sononet_home }}", str(self.root))
        wrapper = wrapper.replace("/usr/bin/ansible-pull", "ansible-pull")
        # Skip the event reporter, which is not installed in this test environment.
        wrapper = wrapper.replace("/usr/bin/python3", "true")
        script = self.root / "updater.sh"
        script.write_text(wrapper)
        with self.config.open("a") as config:
            config.write("SONONET_REPO_URL=https://git.test/fleet.git\n"
                         "SONONET_REPO_BRANCH=master\n"
                         "SONONET_PLAYBOOK_PATH=apps/agentai/ansible_agent/ubuntu-fleet-ocr/local.yml\n")
        result = subprocess.run(["bash", str(script)], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<apps/agentai/ansible_agent/ubuntu-fleet-ocr/local.yml>",
                      self.log.read_text())


if __name__ == "__main__":
    unittest.main()
