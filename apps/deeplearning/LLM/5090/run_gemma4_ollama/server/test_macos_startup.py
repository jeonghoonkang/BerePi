"""Exercise the launcher without network access, models, or live services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class MacOSStartupTests(unittest.TestCase):
    def test_existing_ollama_and_optional_token(self):
        source = Path(__file__).resolve().parent
        for args in ([], ['--ai-server-list-token', 'test token']):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copy(source / 'run_service.sh', root / 'run_service.sh')
                bin_dir = root / 'bin'
                bin_dir.mkdir()
                scripts = {
                    'uname': '#!/bin/sh\necho Darwin\n',
                    'curl': '#!/bin/sh\nexit 0\n',
                    'ollama': '#!/bin/sh\necho "Unexpected Ollama operation: $*" >&2\nexit 99\n',
                    'python3': '''#!/bin/sh
if [ "$1" = "-" ]; then
  exit 1
fi
printf '%s\\n' "$@" > "$CAPTURE_FILE"
''',
                }
                for name, content in scripts.items():
                    path = bin_dir / name
                    path.write_text(content)
                    path.chmod(0o755)
                env = os.environ.copy()
                for name in list(env):
                    if name.startswith(('OLLAMA_', 'GEMMA4_')) or name in (
                        'GPU_SELECTION_FILE', 'MODEL_SELECTION_FILE'
                    ):
                        env.pop(name)
                env.update(PATH=f'{bin_dir}:/usr/bin:/bin', AUTO_PULL='0',
                           CAPTURE_FILE=str(root / 'arguments'))
                result = subprocess.run(
                    ['/bin/bash', str(root / 'run_service.sh'), *args],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('Using existing Ollama', result.stdout)
                self.assertNotIn('Unexpected Ollama operation', result.stderr)
                self.assertEqual((root / 'arguments').read_text().splitlines(),
                                 [str(root / 'server.py'), *args])
                self.assertFalse((root / 'ollama.pid').exists())


if __name__ == '__main__':
    unittest.main()
