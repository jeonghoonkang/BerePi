import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cli import main
from db_audit import DBAudit, inspect_json, table


class DBAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'db'
        self.db.mkdir()
        self.chunk = 'media/family/alice/2024/01/media_old-but-still-current.json'
        self.put(self.chunk, {'items': [self.item('one'), self.item('two', 'duplicate_archived')]})
        self.put('media/family/alice/2024/01/media_unused.json', {'items': [self.item('old')]})
        self.put('duplicates/current.json', {'exact': []})
        self.put('duplicates/old.json', {'exact': []})
        self.put('duplicates/latest.json', {'generation_file': 'duplicates/current.json'})
        self.put('index.json', {'chunks': [{'path': self.chunk}], 'duplicates': 'duplicates/current.json', 'count': 2})
        self.put('config.json', {'sources': []})
        self.put('auth.json', {'password_hash': 'do-not-show', 'sessions': {'abc': 'private'}})
        for folder in ('scans', 'merges', 'reports/merges', 'category_merges', 'duplicate_cleanups', 'source-path-health', 'ai'):
            self.put(folder + '/record.json', {'test': True})
        self.put('scans/log.jsonl', b'{"n":1}\n{"n":2}\n{"n":3}\n')
        self.put('cache/photo.jpg', b'x' * 5000)
        self.put('downloads/archive.zip', b'x' * 9000)
        self.put('unknown/test.bin', b'other')

    def item(self, mid, state='active'):
        return {'media_id': mid, 'media_type': 'image', 'lifecycle': {'status': state},
                'classification': {'category_id': 'family'}, 'locations': [{'role': 'source', 'source_id': 'photos'}]}

    def put(self, relative, value):
        path = self.db / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return path

    def call(self, *args):
        out, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
            code = main(['--db', str(self.db), *args])
        return code, out.getvalue(), errors.getvalue()

    def test_classes_totals_manifest_references_and_contents(self):
        before = {str(path): path.read_bytes() for path in self.db.rglob('*') if path.is_file()}
        report = DBAudit(self.db).scan(top=2)
        self.assertTrue(report['complete'], report)
        self.assertEqual(report['totals']['file_count'], len(before))
        self.assertEqual(report['totals']['logical_bytes'], sum(map(len, before.values())))
        self.assertEqual(sum(row['logical_bytes'] for row in report['classes']), report['totals']['logical_bytes'])
        groups = {row['class']: row for row in report['classes']}
        self.assertEqual(groups['current_media']['file_count'], 1)
        self.assertEqual(groups['unreferenced_media']['file_count'], 1)
        self.assertEqual(groups['current_duplicates']['file_count'], 1)
        self.assertEqual(groups['old_duplicates']['file_count'], 1)
        self.assertEqual(report['contents']['active_items'], 1)
        self.assertEqual(report['contents']['inactive_items'], 1)
        self.assertEqual(report['contents']['sources'], {'photos': 1})
        self.assertEqual(report['largest_files'][0]['path'], 'downloads/archive.zip')
        self.assertEqual({str(path): path.read_bytes() for path in self.db.rglob('*') if path.is_file()}, before)
        self.assertIn('현재 사용 미디어 JSON', table(report))

    def test_sizes_only_never_reads_old_or_current_media_contents(self):
        self.put('media/broken.json', b'not valid JSON')
        audit = DBAudit(self.db)
        with patch.object(audit, 'contents', side_effect=AssertionError('No content reads')):
            report = audit.scan(with_contents=False)
        self.assertTrue(report['complete'])
        self.assertIsNone(report['contents'])

    def test_invalid_index_does_not_claim_old_files_are_unreferenced(self):
        self.put('index.json', b'{broken')
        report = DBAudit(self.db).scan()
        self.assertFalse(report['complete'])
        self.assertFalse(report['index_valid'])
        self.assertNotIn('unreferenced_media', {row['class'] for row in report['classes']})
        self.assertIn('unknown_media', {row['class'] for row in report['classes']})

    def test_changed_index_missing_reference_and_partial_limits(self):
        audit = DBAudit(self.db)
        self.put('index.json', {'chunks': []})
        report = audit.scan()
        self.assertTrue(report['index_changed_during_audit'])
        self.assertFalse(report['complete'])
        self.put('index.json', {'chunks': [{'path': 'media/missing.json'}]})
        report = DBAudit(self.db).scan(with_contents=False)
        self.assertEqual(report['missing_current_chunk_count'], 1)
        self.assertFalse(report['complete'])
        report = DBAudit(self.db).scan(with_contents=False, max_files=3)
        self.assertEqual(report['totals']['file_count'], 3)
        self.assertFalse(report['walk_complete'])

    def test_interruption_returns_partial_accounting(self):
        def interrupt(phase, count, value):
            if phase == 'files' and count >= 2:
                raise KeyboardInterrupt
        report = DBAudit(self.db).scan(with_contents=False, progress=interrupt)
        self.assertTrue(report['interrupted'])
        self.assertEqual(report['totals']['file_count'], 2)

    def test_json_and_jsonl_preview_limits_and_secret_redaction(self):
        result = inspect_json(self.db, self.chunk, limit=1)
        self.assertEqual(len(result['preview']['items']), 1)
        self.assertEqual(result['truncated_arrays'][0]['total'], 2)
        self.assertEqual(inspect_json(self.db, 'auth.json')['preview']['password_hash'], '[REDACTED]')
        self.assertEqual(inspect_json(self.db, 'auth.json')['preview']['sessions'], '[REDACTED]')
        self.put('url.json', {'root': 'https://user:password@example.invalid/photos?token=private-query'})
        self.assertNotIn('password', inspect_json(self.db, 'url.json')['preview']['root'])
        self.assertNotIn('private-query', inspect_json(self.db, 'url.json')['preview']['root'])
        result = inspect_json(self.db, 'scans/log.jsonl', limit=2)
        self.assertEqual(len(result['preview']), 2)
        self.assertTrue(result['more_jsonl_records'])
        with self.assertRaises(ValueError):
            inspect_json(self.db, self.chunk, max_bytes=5)
        for path in ('../outside.json', '/etc/passwd', 'C:/outside.json', 'cache/photo.jpg'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                inspect_json(self.db, path)

    def test_symlinks_are_not_followed(self):
        target = self.root / 'outside.json'
        target.write_text('{"outside":true}')
        try:
            (self.db / 'linked.json').symlink_to(target)
        except OSError:
            self.skipTest('Symlinks unavailable')
        report = DBAudit(self.db).scan()
        self.assertEqual(report['skipped_links'], 1)
        with self.assertRaises(ValueError):
            inspect_json(self.db, 'linked.json')

    def test_cli_bypasses_library_storage_and_writes_only_stdout(self):
        with patch('cli.Library', side_effect=AssertionError('Must not construct Library')), \
             patch('storage_usage.StorageUsage', side_effect=AssertionError('Must not start storage worker')):
            code, out, errors = self.call('db-audit', '--format', 'json')
        self.assertEqual(code, 0, errors)
        self.assertTrue(json.loads(out)['complete'])
        self.assertEqual(self.call('db-audit', '--sizes-only', '--max-files', '2')[0], 2)
        self.assertEqual(self.call('db-show', '--file', self.chunk, '--limit', '1')[0], 0)
        self.assertEqual(self.call('db-show', '--file', '../outside.json')[0], 1)
        self.assertEqual(self.call('db-audit', '--format', 'table')[0], 0)

    def test_missing_db_is_not_created_and_invalid_limits_rejected(self):
        missing = self.root / 'absent'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--db', str(missing), 'db-audit']), 1)
            with self.assertRaises(SystemExit):
                main(['--db', str(self.db), 'db-audit', '--top', '-1'])
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
