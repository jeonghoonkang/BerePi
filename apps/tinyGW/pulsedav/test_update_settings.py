import json
from pathlib import Path
import tempfile
import unittest

from update_settings import rebuild


class UpdateSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.template = Path(self.directory.name) / "settings.json"
        self.target = Path(self.directory.name) / "this_settings.json"

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_update_preserves_connections_and_adds_new_fields(self):
        self.write(self.template, {
            "webdav": {"username": "default", "password": "default", "sub": ""},
            "iptime": {"user_id": "", "user_pw": "", "enabled": False},
            "schedule": {"interval_minutes": 30},
        })
        self.write(self.target, {
            "webdav": {"username": "my-user", "password": "my-secret", "sub": ["office"]},
            "iptime": {"user_id": "router-user", "user_pw": "router-secret"},
            "obsolete": True,
        })
        original = self.target.read_bytes()
        backup = rebuild(self.template, self.target)
        result = json.loads(self.target.read_text())
        self.assertEqual(result["webdav"]["password"], "my-secret")
        self.assertEqual(result["webdav"]["username"], "my-user")
        self.assertEqual(result["webdav"]["sub"], ["office"])
        self.assertEqual(result["iptime"]["user_id"], "router-user")
        self.assertEqual(result["iptime"]["user_pw"], "router-secret")
        self.assertFalse(result["iptime"]["enabled"])
        self.assertEqual(result["schedule"]["interval_minutes"], 30)
        self.assertNotIn("obsolete", result)
        self.assertEqual(backup.read_bytes(), original)
        for path in (backup, self.target):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_first_creation_and_same_path_protection(self):
        self.write(self.template, {"new": True})
        self.assertIsNone(rebuild(self.template, self.target))
        self.assertEqual(json.loads(self.target.read_text()), {"new": True})
        with self.assertRaises(ValueError):
            rebuild(self.template, self.template)

    def test_conflicts_do_not_modify_existing_file(self):
        for template, old in [
            ({"webdav": {}}, {"webdav": {"password": "secret"}}),
            ({"enabled": False}, {"enabled": 1}),
            ({"nested": {}}, {"nested": "old"}),
        ]:
            with self.subTest(template=template):
                self.write(self.template, template)
                self.write(self.target, old)
                original = self.target.read_bytes()
                with self.assertRaises(ValueError):
                    rebuild(self.template, self.target)
                self.assertEqual(self.target.read_bytes(), original)
                self.assertFalse(list(self.target.parent.glob("*.bak.*")))

    def test_invalid_json_does_not_expose_contents_or_overwrite(self):
        self.write(self.template, {})
        self.target.write_text('{"password": "secret" broken}', encoding="utf-8")
        original = self.target.read_bytes()
        with self.assertRaises(ValueError) as caught:
            rebuild(self.template, self.target)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(self.target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
