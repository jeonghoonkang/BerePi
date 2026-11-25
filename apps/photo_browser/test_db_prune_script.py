"""Exercise the Bash workflow against an isolated real DB and CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from db_prune import prune_status
import test_db_prune


def find_bash():
    if os.name != 'nt':
        return shutil.which('bash')
    git = shutil.which('git')
    if git:
        # The bundled Git runtime provides Bash under the name sh.exe.
        candidate = Path(git).parent.parent / 'usr/bin/sh.exe'
        if candidate.is_file():
            return str(candidate)
    return None


@unittest.skipUnless(find_bash(), 'Bash runtime required')
class DBPruneScriptTests(unittest.TestCase):
    write = test_db_prune.DBPruneTests.write
    prepare = test_db_prune.DBPruneTests.prepare

    def setUp(self):
        test_db_prune.DBPruneTests.setUp(self)
        self.bash = find_bash()
        self.script = Path(__file__).with_name('db_prune.sh').resolve()
        self.env = dict(os.environ, PYTHON=sys.executable.replace('\\', '/'), PYTHONUTF8='1')
        if os.name == 'nt':
            self.env['PATH'] = str(Path(self.bash).parent) + os.pathsep + self.env['PATH']
            version = subprocess.run([self.bash, '--version'], capture_output=True, text=True).stdout
            if 'cygwin' in version.lower():
                # Cygwin does not translate POSIX arguments for native Python.
                shim = self.root / 'python-shim.sh'
                shim.write_text('#!/usr/bin/sh\n'
                                'if [[ "$1" != -* ]]; then\n'
                                '  shift; set -- "$NATIVE_CLI" "$@"\n'
                                'fi\nexec "$NATIVE_PYTHON" "$@"\n', encoding='utf-8', newline='\n')
                self.env['NATIVE_PYTHON'] = self.env['PYTHON']
                self.env['NATIVE_CLI'] = self.script.with_name('cli.py').as_posix()
                self.env['PYTHON'] = shim.as_posix()

    def run_script(self, *args, input=''):
        result = subprocess.run([self.bash, self.script.as_posix(), *args,
                                 '--db', self.db.as_posix(), '--plan', self.plan.as_posix()],
                                input=input.encode('utf-8'), capture_output=True,
                                env=self.env, cwd=self.root, timeout=30)
        result.stdout = result.stdout.decode('utf-8')
        result.stderr = result.stderr.decode('utf-8')
        return result

    def test_default_run_accepts_partial_plan_and_cancel_preserves_files(self):
        result = self.run_script('--max-files', '1', '--under', self.folder, input='yes\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(prune_status(self.plan)['status'], 'partial')
        self.assertTrue(self.old.exists())
        self.assertIn('삭제를 취소', result.stdout)

    def test_run_reuses_existing_plan_and_deletes_only_old_json_after_confirmation(self):
        report = self.prepare()
        index = (self.db / 'index.json').read_bytes()
        source = self.source / 'photo.jpg'
        managed = Path(self.item['locations'][-1]['path'])
        contents = (source.read_bytes(), managed.read_bytes())
        result = self.run_script(input='yes\n' + report['plan_id'] + '\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('기존 계획을 재사용', result.stdout)
        self.assertFalse(self.old.exists())
        self.assertEqual(prune_status(self.plan)['counts']['deleted']['files'], 1)
        self.assertEqual((source.read_bytes(), managed.read_bytes()), contents)
        self.assertEqual((self.db / 'index.json').read_bytes(), index)

    def test_apply_rejects_wrong_confirmation(self):
        self.prepare()
        result = self.run_script('apply', '--server-stopped', input='wrong-id\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.old.exists())
        self.assertEqual(prune_status(self.plan)['counts']['pending']['files'], 1)

    def test_plan_resume_adds_inspections_without_deletion(self):
        self.write('second.json', self.item)
        first = self.run_script('plan', '--under', self.folder, '--max-files', '1', '--server-stopped')
        self.assertEqual(first.returncode, 2, first.stderr)
        plan_id = prune_status(self.plan)['plan_id']
        second = self.run_script('plan', '--under', self.folder, '--resume', '--all', '--server-stopped')
        self.assertEqual(second.returncode, 0, second.stderr)
        report = prune_status(self.plan)
        self.assertEqual(report['plan_id'], plan_id)
        self.assertEqual(report['counts']['pending']['files'], 2)
        self.assertTrue(self.old.exists())

    def test_status_does_not_require_interactive_input(self):
        self.prepare()
        result = self.run_script('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['counts']['pending']['files'], 1)

    def test_plan_error_does_not_proceed_to_delete(self):
        self.prepare()
        result = self.run_script('plan', '--server-stopped')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('삭제 확인', result.stdout)
        self.assertTrue(self.old.exists())

    def test_declining_server_stop_does_not_create_plan(self):
        result = self.run_script(input='no\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.plan.exists())


if __name__ == '__main__':
    unittest.main()
