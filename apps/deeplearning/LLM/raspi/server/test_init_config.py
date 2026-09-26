"""Configuration repair regression tests without apt or model installation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from init_config import ensure_config


class ConfigSetupTests(unittest.TestCase):
    def test_create_and_repair_preserve_settings_and_are_idempotent(self):
        for content in [None, 'GEMMA4_SERVER_PORT=9090\n',
                        'GEMMA4_API_KEY=\n', "export GEMMA4_API_KEY='short'\n"]:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'config.env.sample').write_text('GEMMA4_SERVER_PORT=8082\n')
                config = root / 'config.env'
                if content is not None:
                    config.write_text(content)
                with patch.dict(os.environ, {'GEMMA4_API_KEY': 'inherited-' * 5}):
                    self.assertTrue(ensure_config(root))
                key = subprocess.check_output(
                    ['bash', '-c', 'source "$1"; printf "%s" "$GEMMA4_API_KEY"',
                     'test', str(config)], text=True)
                self.assertEqual(len(key), 64)
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                text = config.read_text()
                if content is not None:
                    self.assertTrue(text.startswith(content))
                self.assertFalse(ensure_config(root))
                self.assertEqual(config.read_text(), text)

    def test_valid_quoted_key_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.env'
            original = "export GEMMA4_API_KEY='a long existing password with spaces'\n"
            config.write_text(original)
            config.chmod(0o644)
            self.assertFalse(ensure_config(root))
            self.assertEqual(config.read_text(), original)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_invalid_shell_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.env'
            config.write_text("GEMMA4_API_KEY='unterminated\n")
            before = config.read_bytes()
            with self.assertRaises(ValueError):
                ensure_config(root)
            self.assertEqual(config.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
