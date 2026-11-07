import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('nominatim') / 'setup_local.py'
spec = importlib.util.spec_from_file_location('photo_nominatim_setup', SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class FakeSetup(setup.Setup):
    """Exercise orchestration and files without apt, sudo, network or PostgreSQL."""
    def __init__(self, args, user='tinyos', db_present=False, fail_import=False):
        super().__init__(args, user)
        self.commands = []
        self.db_present, self.fail_import = db_present, fail_import

    def check_space(self, path):
        pass

    def run(self, command, capture=False):
        command = [str(item) for item in command]
        self.commands.append(command)
        if 'psql' in command:
            sql = command[-1]
            if 'pg_database' in sql:
                return '1' if self.db_present else ''
            if 'pg_roles' in sql:
                return 't'
            if 'data_directory' in sql:
                return str(self.project)
        if command[:4] == ['sudo', '-u', 'postgres', 'python3']:
            return str(1024 ** 4)
        if command[:3] == ['python3', '-m', 'venv']:
            self.venv.mkdir(parents=True)
            (self.venv / 'pyvenv.cfg').write_text('test venv')
        if command[0] == 'curl':
            Path(command[command.index('--output') + 1]).write_bytes(b'OSM fixture')
        if 'import' in command:
            self.db_present = True
            if self.fail_import:
                raise OSError('import interrupted')
        return ''


class NominatimSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'

    def args(self, *extra):
        return setup.parser().parse_args(['--project-dir', str(self.project), *extra])

    def execute(self, instance):
        with contextlib.redirect_stdout(io.StringIO()):
            instance.execute()

    def test_install_import_validate_and_generate_launcher_then_idempotent_rerun(self):
        first = FakeSetup(self.args())
        self.execute(first)
        commands = first.commands
        self.assertIn(['sudo', 'systemctl', 'start', 'postgresql'], commands)
        importer = next(command for command in commands if 'import' in command)
        self.assertIn('--reverse-only', importer)
        self.assertEqual(importer[0], str(first.tool))  # Official importer, not the local serve-only wrapper.
        self.assertTrue(any('--check-database' in command for command in commands))
        self.assertEqual(json.loads(first.state_file.read_text())['status'], 'complete')
        self.assertIn('NOMINATIM_IMPORT_STYLE=admin', first.env_file.read_text())
        self.assertIn('exec ', (self.project / 'start-nominatim.sh').read_text())
        second = FakeSetup(self.args(), db_present=True)
        self.execute(second)
        self.assertFalse(any('import' in command or command[0] == 'curl' for command in second.commands))
        self.assertTrue(any('--check-database' in command for command in second.commands))

    def test_existing_unmanaged_db_is_never_imported_or_dropped(self):
        existing = FakeSetup(self.args(), db_present=True)
        with self.assertRaisesRegex(ValueError, 'DB가 이미'), contextlib.redirect_stdout(io.StringIO()):
            existing.execute()
        self.assertFalse(any('import' in command for command in existing.commands))
        self.assertFalse(existing.env_file.exists())
        self.assertFalse(any('drop' in ' '.join(command).lower() for command in existing.commands))

    def test_interrupted_import_does_not_mark_complete_or_overwrite_partial_db(self):
        interrupted = FakeSetup(self.args(), fail_import=True)
        with self.assertRaisesRegex(OSError, 'interrupted'), contextlib.redirect_stdout(io.StringIO()):
            interrupted.execute()
        self.assertEqual(json.loads(interrupted.state_file.read_text())['status'], 'in_progress')
        retry = FakeSetup(self.args(), db_present=True)
        with self.assertRaisesRegex(ValueError, '자동 삭제'), contextlib.redirect_stdout(io.StringIO()):
            retry.execute()
        self.assertFalse(any('import' in command for command in retry.commands))

    def test_existing_config_and_changed_setup_are_preserved(self):
        self.project.mkdir()
        original = 'NOMINATIM_DATABASE_DSN=existing\n'
        (self.project / '.env').write_text(original)
        with self.assertRaisesRegex(ValueError, '덮어쓰지'):
            self.execute(FakeSetup(self.args()))
        self.assertEqual((self.project / '.env').read_text(), original)
        (self.project / '.env').unlink()
        self.execute(FakeSetup(self.args()))
        with self.assertRaisesRegex(ValueError, '구축 설정과 다릅니다'):
            self.execute(FakeSetup(self.args('--db-name', 'other_database')))

    def test_local_map_and_checksum_reject_bad_data_before_import(self):
        osm = self.root / 'map.osm.pbf'
        osm.write_bytes(b'OSM fixture')
        instance = FakeSetup(self.args('--osm-file', str(osm), '--osm-sha256', '0' * 64))
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            self.execute(instance)
        self.assertFalse(any('import' in command or command[0] == 'curl' for command in instance.commands))

    def test_dry_run_performs_no_commands_or_filesystem_mutations(self):
        output = io.StringIO()
        with patch.object(setup.subprocess, 'run') as run, contextlib.redirect_stdout(output):
            self.assertEqual(setup.main(['--project-dir', str(self.project), '--dry-run']), 0)
        run.assert_not_called()
        self.assertFalse(self.project.exists())
        self.assertIn('nominatim-db==5.3.3', output.getvalue())
        self.assertIn('south-korea-latest.osm.pbf', output.getvalue())

    def test_invalid_database_name_rejected_before_external_commands(self):
        instance = FakeSetup(self.args('--db-name', "bad'; DROP DATABASE other; --"))
        with self.assertRaises(ValueError):
            self.execute(instance)
        self.assertEqual(instance.commands, [])


if __name__ == '__main__':
    unittest.main()
