import contextlib
import copy
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from PIL import Image

from cli import main
from db_locks import exclusive_file_lock
from db_prune import plan_prune, apply_prune, prune_status, strings
from library import Library


class DBPruneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        Image.new('RGB', (8, 8), 'red').save(self.source / 'photo.jpg')
        self.db = self.root / 'db'
        self.library = Library(self.db, self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'protocol': 'file', 'root': str(self.source)}]})
        self.library.scan('photos')
        self.library.merge()
        self.item = self.library.items()[0]
        self.folder = 'media/prune_test'
        self.old = self.write('old.json', self.item)
        self.plan = self.root / 'prune.sqlite'

    def write(self, name, item):
        path = self.db / self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'items': [item]}), encoding='utf-8')
        return path

    def prepare(self, **kwargs):
        return plan_prune(self.db, self.plan, stopped=True, under=self.folder, **kwargs)

    def apply(self, report=None, **kwargs):
        return apply_prune(self.db, self.plan, (report or prune_status(self.plan))['plan_id'], stopped=True, **kwargs)

    def test_verified_deletion_only_removes_old_json_and_prints_commands(self):
        original = (self.source / 'photo.jpg').read_bytes()
        managed = Path(self.item['locations'][-1]['path'])
        before = managed.read_bytes()
        index = (self.db / 'index.json').read_bytes()
        report = self.prepare()
        self.assertTrue(self.old.exists())
        self.assertEqual(report['counts']['pending']['files'], 1)
        self.assertIn('--confirm', report['apply_command_posix'])
        self.assertIn(report['plan_id'], report['apply_command_powershell'])
        result = self.apply(report)
        self.assertEqual(result['counts']['deleted']['files'], 1)
        self.assertFalse(self.old.exists())
        self.assertEqual(managed.read_bytes(), before)
        self.assertEqual((self.source / 'photo.jpg').read_bytes(), original)
        self.assertEqual((self.db / 'index.json').read_bytes(), index)
        self.assertEqual(self.apply()['counts']['deleted']['files'], 1)

    def test_current_and_recovery_referenced_files_are_kept(self):
        current = json.loads((self.db / 'index.json').read_bytes())['chunks'][0]['path']
        recovery = self.db / 'category_merges' / 'recovery.json'
        recovery.parent.mkdir(exist_ok=True)
        recovery.write_text(json.dumps({'before_chunk': self.old.relative_to(self.db).as_posix()}))
        report = plan_prune(self.db, self.plan, stopped=True)
        self.assertGreaterEqual(report['reasons']['protected_reference'], 2)
        self.apply(report)
        self.assertTrue(self.old.exists())
        self.assertTrue((self.db / current).exists())
        self.assertTrue(recovery.exists())

    def test_unique_historical_metadata_missing_id_and_remote_are_not_eligible(self):
        old = copy.deepcopy(self.item)
        old['classification']['tags'] = ['only-in-history']
        self.write('unique.json', old)
        old = copy.deepcopy(self.item)
        old['media_id'] = 'lost-item'
        self.write('missing.json', old)
        report = self.prepare()
        self.assertEqual(report['reasons']['historical_metadata_not_covered'], 1)
        self.assertEqual(report['reasons']['missing_current_item'], 1)
        self.apply(report)
        self.assertTrue((self.old.parent / 'unique.json').exists())
        self.assertTrue((self.old.parent / 'missing.json').exists())

    def test_missing_or_changed_photos_never_allow_deletion(self):
        report = self.prepare()
        path = Path(self.item['locations'][-1]['path'])
        content = path.read_bytes()
        path.write_bytes(b'x' * len(content))
        result = self.apply(report)
        self.assertEqual(result['counts']['kept_after_change']['files'], 1)
        self.assertTrue(self.old.exists())
        self.assertIn('managed_not_verified', result['reasons'])

    def test_source_is_required_even_when_managed_is_valid(self):
        (self.source / 'photo.jpg').unlink()
        result = self.prepare()
        self.assertEqual(result['reasons']['source_not_verified'], 1)
        self.apply(result)
        self.assertTrue(self.old.exists())

    def test_remote_sources_are_kept_without_network_access(self):
        current = copy.deepcopy(self.item)
        current['locations'][0].update(protocol='http', uri='https://example.invalid/photo.jpg')
        current['locations'][0].pop('path')
        self.library.commit([current])
        self.write('old.json', current)
        result = self.prepare()
        self.assertEqual(result['reasons']['source_not_verified'], 1)

    def test_crash_after_unlink_is_reconciled_without_repeating_deletes(self):
        report = self.prepare()
        unlink = Path.unlink
        def interrupted(path, *args, **kwargs):
            result = unlink(path, *args, **kwargs)
            if path == self.old:
                raise KeyboardInterrupt
            return result
        with patch.object(Path, 'unlink', interrupted):
            result = self.apply(report)
        self.assertEqual(result['status'], 'partial_apply')
        self.assertEqual(result['counts']['deleting']['files'], 1)
        result = self.apply()
        self.assertEqual(result['counts']['recovered_deleted']['files'], 1)

    def test_changed_index_or_plan_confirmation_blocks_apply(self):
        report = self.prepare()
        with self.assertRaises(ValueError):
            apply_prune(self.db, self.plan, 'wrong', stopped=True)
        current = json.loads((self.db / 'index.json').read_bytes())
        current['changed'] = True
        (self.db / 'index.json').write_text(json.dumps(current))
        with self.assertRaisesRegex(ValueError, '변경'):
            self.apply(report)
        self.assertTrue(self.old.exists())

    def test_ack_locks_pending_jobs_and_dangerous_paths(self):
        with self.assertRaises(ValueError): plan_prune(self.db, self.plan)
        with exclusive_file_lock(self.db / '.server.lock'):
            with self.assertRaises(ValueError): self.prepare()
        with self.library.writing():
            with self.assertRaises(ValueError): self.prepare()
        jobs = self.db / 'jobs'
        jobs.mkdir(exist_ok=True)
        (jobs / 'running.json').write_text('{"status":"running"}')
        with self.assertRaisesRegex(ValueError, '작업 기록'): self.prepare()
        (jobs / 'running.json').unlink()
        for plan, under in ((self.db / 'bad.sqlite', self.folder), (self.plan, '../source'),
                            (self.root / 'managed' / 'bad.sqlite', self.folder)):
            with self.assertRaises(ValueError): plan_prune(self.db, plan, stopped=True, under=under)

    def test_partial_plan_resume_and_interrupted_apply_resume(self):
        self.write('second.json', self.item)
        report = self.prepare(max_files=1)
        self.assertEqual(report['status'], 'partial')
        report = self.prepare(resume=True)
        self.assertEqual(report['counts']['pending']['files'], 2)
        def interrupt(phase, count, path):
            if phase == 'delete': raise KeyboardInterrupt
        result = self.apply(report, progress=interrupt)
        self.assertEqual(result['status'], 'partial_apply')
        self.assertEqual(result['counts']['deleted']['files'], 1)
        result = self.apply()
        self.assertEqual(result['counts']['deleted']['files'], 2)

    def test_string_scanner_unicode_and_chunk_boundary(self):
        path = self.root / 'strings.json'
        values = {'prefix': 'x' * (1024 * 1024 - 14), 'reference': 'media/with space/old.json', 'unicode': '가족', 'escaped': 'x\\"y'}
        path.write_text(json.dumps(values, ensure_ascii=True), encoding='utf-8')
        result = list(strings(path, 2 * 1024 * 1024))
        self.assertIn('media/with space/old.json', result)
        self.assertIn('가족', result)
        self.assertIn('x\\"y', result)
        with self.assertRaises(ValueError): list(strings(path, 10))

    def test_recovery_reference_with_spaces_and_escaped_unicode_is_preserved(self):
        old = self.write('한 글.json', self.item)
        recovery = self.db / 'reports' / 'reference.jsonl'
        recovery.parent.mkdir(exist_ok=True)
        recovery.write_text(json.dumps({'path': str(old)}, ensure_ascii=True) + '\n')
        report = self.prepare()
        self.assertEqual(report['reasons']['protected_reference'], 1)
        self.apply(report)
        self.assertTrue(old.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows case-insensitive path protection')
    def test_current_reference_with_different_filename_case_is_protected(self):
        index = json.loads((self.db / 'index.json').read_bytes())
        current = index['chunks'][0]['path']
        index['chunks'][0]['path'] = current.upper()
        (self.db / 'index.json').write_text(json.dumps(index))
        report = plan_prune(self.db, self.plan, stopped=True)
        self.apply(report)
        self.assertTrue((self.db / current).exists())

    def test_symlink_json_and_malformed_json_are_not_deleted(self):
        (self.old.parent / 'broken.json').write_text('{broken')
        try:
            (self.old.parent / 'linked.json').symlink_to(self.old)
        except OSError:
            pass
        report = self.prepare()
        self.assertEqual(report['reasons']['unreadable_or_invalid_json'], 1)
        self.apply(report)
        self.assertTrue((self.old.parent / 'broken.json').exists())

    def test_cli_plan_status_apply(self):
        def run(args):
            out, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(error):
                code = main(['--db', str(self.db), *args])
            self.assertEqual(code, 0, error.getvalue())
            return json.loads(out.getvalue())
        report = run(['db-prune-plan', '--plan', str(self.plan), '--server-stopped', '--under', self.folder])
        self.assertEqual(run(['db-prune-status', '--plan', str(self.plan)])['plan_id'], report['plan_id'])
        run(['db-prune-apply', '--plan', str(self.plan), '--server-stopped', '--confirm', report['plan_id']])
        self.assertFalse(self.old.exists())

    def test_cli_over_1000_files_automatically_persists_bounded_progress(self):
        for i in range(1000):
            self.write(f'extra-{i}.json', self.item)
        out, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(error):
            code = main(['--db', str(self.db), 'db-prune-plan', '--plan', str(self.plan),
                         '--server-stopped', '--under', self.folder, '--max-files', '1000', '--progress-log-files', '1'])
        self.assertEqual(code, 2, error.getvalue())
        report = json.loads(out.getvalue())
        log = Path(report['progress_log'])
        data = json.loads(log.read_text(encoding='utf-8'))
        self.assertEqual(data['total'], 1000)
        self.assertEqual(data['processed'], 1000)
        self.assertEqual(data['progress_percent'], 100)
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(report['counts']['pending']['files'], 1000)
        self.assertTrue(self.old.exists())
        self.assertFalse(any(Path(f'{log}.{i}').exists() for i in range(1, 5)))


if __name__ == '__main__':
    unittest.main()
