import copy
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app import create_app
from backup import create_backup, restore_backup
from library import digest, read_json


class CategoryMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.managed = self.root / 'managed'
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        self.store = self.app.extensions['category_merger']
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}
        sources = []
        for category, color in [('family_a', 'red'), ('family_b', 'blue')]:
            folder = self.root / category
            folder.mkdir()
            exif = Image.Exif()
            exif[36867] = '2024:03:05 12:30:00'
            Image.new('RGB', (8, 8), color).save(folder / 'photo.jpg', exif=exif)
            sources.append({'source_id': category, 'root': str(folder), 'protocol': 'file', 'category': category, 'owner_id': 'alice'})
        self.library.save_config({'managed_root': str(self.managed), 'sources': sources, 'scan_min_free_mb': 32})
        for source in sources:
            self.library.scan(source['source_id'])
        self.library.merge()
        self.before = self.library.items()
        self.originals = {i['media_id']: Path(i['locations'][-1]['path']) for i in self.before}

    def tearDown(self):
        self.temp.cleanup()

    def preview(self):
        return self.store.preview(['family_a', 'family_b'], 'family')

    def test_managed_only_roundtrip_preserves_metadata_and_original_times(self):
        for item in self.before:
            Path(item['locations'][0]['path']).unlink()
        times = {key: path.stat().st_mtime_ns for key, path in self.originals.items()}
        plan = self.preview()
        self.assertEqual(plan['copy_files'], 2)
        result = self.store.execute(plan['operation_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual({i['classification']['category_id'] for i in self.library.items()}, {'family'})
        self.assertEqual({Path(i['locations'][-1]['path']).name for i in self.library.items()}, {'photo.jpg', 'photo_중복.jpg'})
        by_id = {i['media_id']: i for i in self.before}
        for item in self.library.items():
            old = by_id[item['media_id']]
            self.assertEqual(item['capture'], old['capture'])
            self.assertEqual(item['classification']['owner_id'], 'alice')
            self.assertEqual(item['classification']['tags'], old['classification']['tags'])
            path = Path(item['locations'][-1]['path'])
            self.assertEqual(digest(path), old['sha256'])
            self.assertEqual(path.stat().st_mtime_ns, times[item['media_id']])
            self.assertFalse(self.originals[item['media_id']].exists())
        self.assertEqual(len(result['moves']), 2)
        self.assertTrue(all(Path(m['saved']).is_file() for m in result['moves']))
        result = self.store.undo(plan['operation_id'])
        self.assertEqual(result['status'], 'undone')
        self.assertEqual(self.library.items(), self.before)
        self.assertTrue(all(p.is_file() for p in self.originals.values()))
        self.assertTrue(all(p.stat().st_mtime_ns == times[key] for key, p in self.originals.items()))

    def test_existing_identical_target_is_reused_and_not_removed_by_undo(self):
        item = copy.deepcopy(self.before[0])
        item['classification']['category_id'] = 'family'
        target = self.library.merge_target(self.managed, item)
        target.parent.mkdir(parents=True)
        shutil.copy2(self.originals[item['media_id']], target)
        plan = self.preview()
        self.assertEqual(plan['copy_files'], 1)
        self.store.execute(plan['operation_id'])
        self.store.undo(plan['operation_id'])
        self.assertTrue(target.is_file())
        self.assertEqual(digest(target), item['sha256'])

    def test_shared_and_source_referenced_files_are_retained(self):
        shared = copy.deepcopy(self.before[0])
        shared['media_id'] = 'shared'
        shared['classification']['category_id'] = 'other'
        # The second path is itself recorded as a physical original.
        self.before[1]['locations'][0]['path'] = str(self.originals[self.before[1]['media_id']])
        self.library.commit(self.before + [shared])
        result = self.store.execute(self.preview()['operation_id'])
        self.assertEqual(result['moves'], [])
        self.assertTrue(all(path.exists() for path in self.originals.values()))
        self.assertEqual(next(i for i in self.library.items() if i['media_id'] == 'shared')['classification']['category_id'], 'other')

    def test_missing_managed_and_stale_preview_or_undo_are_rejected(self):
        plan = self.preview()
        self.library.edit([self.before[0]['media_id']], {'tags': ['new']})
        with self.assertRaisesRegex(ValueError, '변경'):
            self.store.execute(plan['operation_id'])
        plan = self.preview()
        self.store.execute(plan['operation_id'])
        self.library.edit([self.before[0]['media_id']], {'tags': ['later']})
        with self.assertRaisesRegex(ValueError, '변경'):
            self.store.undo(plan['operation_id'])
        self.assertEqual(next(i for i in self.library.items() if i['media_id'] == self.before[0]['media_id'])['classification']['tags'], ['later'])

    def test_preview_without_managed_never_reads_source(self):
        for path in self.originals.values():
            path.unlink()
        with self.assertRaisesRegex(ValueError, 'managed'):
            self.preview()
        self.assertEqual(self.library.items(), self.before)

    def test_stop_before_commit_resume_and_undo_partial_copy(self):
        plan = self.preview()
        stop = [False]
        def progress(value):
            if value['phase'] == 'category_copying':
                stop[0] = True
        result = self.store.execute(plan['operation_id'], progress, lambda: stop[0])
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(self.library.items(), self.before)
        self.assertTrue(all(path.exists() for path in self.originals.values()))
        self.assertEqual(self.store.execute(plan['operation_id'])['status'], 'completed')
        self.assertEqual(self.store.undo(plan['operation_id'])['status'], 'undone')
        plan = self.preview()
        stop[0] = False
        self.store.execute(plan['operation_id'], progress, lambda: stop[0])
        self.assertEqual(self.store.undo(plan['operation_id'])['status'], 'undone')
        self.assertEqual(self.library.items(), self.before)

    def test_archive_failure_after_db_commit_can_resume(self):
        plan = self.preview()
        with patch.object(self.store, 'move_checked', side_effect=OSError('archive unavailable')):
            with self.assertRaises(OSError):
                self.store.execute(plan['operation_id'])
        self.assertEqual({i['classification']['category_id'] for i in self.library.items()}, {'family'})
        self.assertTrue(all(Path(i['locations'][-1]['path']).exists() for i in self.library.items()))
        self.assertEqual(self.store.execute(plan['operation_id'])['status'], 'completed')
        self.assertEqual(self.store.undo(plan['operation_id'])['status'], 'undone')

    def test_copy_disk_failure_preserves_db_and_originals(self):
        plan = self.preview()
        with patch('category_merge.shutil.disk_usage', return_value=SimpleNamespace(free=0)), self.assertRaisesRegex(ValueError, '공간'):
            self.store.execute(plan['operation_id'])
        self.assertEqual(self.library.items(), self.before)
        self.assertTrue(all(path.exists() for path in self.originals.values()))
        self.assertEqual(list(self.managed.rglob('*.part')), [])

    def test_post_commit_failure_checks_replacement_before_archiving(self):
        plan = self.preview()
        commit = self.library.commit
        def interrupted(items):
            commit(items)
            raise OSError('interrupted after index publication')
        with patch.object(self.library, 'commit', side_effect=interrupted), self.assertRaises(OSError):
            self.store.execute(plan['operation_id'])
        item = self.library.items()[0]
        target = Path(item['locations'][-1]['path'])
        original = self.originals[item['media_id']]
        target.write_bytes(b'changed after crash')
        with self.assertRaisesRegex(ValueError, '변경'):
            self.store.execute(plan['operation_id'])
        self.assertTrue(all(p.exists() for p in self.originals.values()))
        shutil.copy2(original, target)
        self.assertEqual(self.store.execute(plan['operation_id'])['status'], 'completed')

    def test_torn_journal_is_repaired_on_resume(self):
        plan = self.preview()
        stop = [False]
        def progress(value):
            if value['phase'] == 'category_copying':
                stop[0] = True
        self.store.execute(plan['operation_id'], progress, lambda: stop[0])
        journal = self.store.record_path(plan['operation_id']).with_suffix('.jsonl')
        with journal.open('ab') as stream:
            stream.write(b'{"row_index":')
        self.assertEqual(self.store.execute(plan['operation_id'])['status'], 'completed')
        self.assertEqual(self.store.undo(plan['operation_id'])['status'], 'undone')

    def test_backup_restore_includes_archive_and_allows_undo(self):
        from category_merge import CategoryMerger
        from library import Library
        plan = self.preview()
        self.store.execute(plan['operation_id'])
        bundle = self.root / 'backup.zip'
        create_backup(self.library, bundle)
        result = restore_backup(bundle, self.root / 'restored')
        restored = Library(result['db'], result['root'])
        self.assertEqual(CategoryMerger(restored).undo(plan['operation_id'])['status'], 'undone')
        self.assertEqual({i['classification']['category_id'] for i in restored.items()}, {'family_a', 'family_b'})
        self.assertTrue(all(Path(i['locations'][-1]['path']).is_relative_to(Path(result['managed_root'])) for i in restored.items()))

    def test_api_auth_validation_and_background_execution(self):
        url = '/api/category-merges/preview'
        body = {'categories': ['family_a', 'family_b'], 'target_category': 'family'}
        self.assertEqual(self.client.post(url, json=body).status_code, 403)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'secret'}):
            self.assertEqual(self.client.get('/api/category-merges').status_code, 401)
        def wait(response):
            self.assertEqual(response.status_code, 202)
            for _ in range(500):
                value = self.client.get('/api/jobs/' + response.json['job_id']).json
                if value['status'] not in {'queued', 'running', 'stopping'}:
                    return value
                time.sleep(0.01)
            self.fail('Job timeout')
        status = wait(self.client.post(url, json=body, headers=self.headers))
        self.assertEqual(status['status'], 'preview', status)
        token = status['result']['operation_id']
        self.assertEqual(wait(self.client.post(f'/api/category-merges/{token}/run', json={}, headers=self.headers))['status'], 'completed')
        self.assertEqual(wait(self.client.post(f'/api/category-merges/{token}/undo', json={}, headers=self.headers))['status'], 'undone')
        self.assertEqual(len(self.client.get('/api/category-merges').json['items']), 1)


if __name__ == '__main__':
    unittest.main()
