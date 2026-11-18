import copy
from unittest.mock import patch
import unittest

from duplicate_cleanup import DuplicateCleanup
from source_comparison import SourceComparison
import test_source_comparison


class DuplicateCleanupTests(unittest.TestCase):
    tearDown = test_source_comparison.SourceComparisonTests.tearDown

    def item(self, items, source, name='0.jpg'):
        return test_source_comparison.SourceComparisonTests.item(
            self, [item for item in items if item['classification']['category_id'] == 'photo_box'], source, name)

    def setUp(self):
        test_source_comparison.SourceComparisonTests.setUp(self)
        self.cleanup = DuplicateCleanup(self.library)
        items = self.library.items()
        family = copy.deepcopy(self.item(items, 'a'))
        family['media_id'] = 'family-only'
        family['classification']['category_id'] = 'family'
        family['classification']['tags'] = ['family-tag']
        self.item(items, 'a')['classification']['events'] = ['original-event']
        self.library.commit(items + [family])
        self.before = self.library.items()

    def files(self):
        return {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                for folder in ('a', 'b', 'managed') for path in (self.root / folder).rglob('*') if path.is_file()}

    def test_preview_execute_undo_preserves_family_keep_annotations_and_all_files(self):
        files = self.files()
        result = self.cleanup.preview(self.left, self.right)
        self.assertEqual(result['archive_count'], 2)
        self.assertEqual(result['preserved_categories'], [{'category': 'family', 'count': 1}])
        self.assertEqual(self.library.items(), self.before)
        page = self.cleanup.page(result['operation_id'])
        self.assertEqual(len(page['rows']), 2)
        done = self.cleanup.execute(result['operation_id'])
        self.assertEqual(done['status'], 'completed')
        current = {item['media_id']: item for item in self.library.items()}
        for item in self.before:
            after = current[item['media_id']]
            if item['classification']['category_id'] == 'photo_box' and item['locations'][0]['source_id'] == 'a':
                self.assertEqual(after['lifecycle']['status'], 'duplicate_archived')
                self.assertEqual(after['locations'], item['locations'])
                self.assertEqual(after['classification'], item['classification'])
            else:
                self.assertEqual(after, item)
        self.assertEqual(self.files(), files)
        self.assertEqual(self.cleanup.execute(result['operation_id'])['status'], 'completed')
        self.cleanup.undo(result['operation_id'])
        self.assertEqual(self.library.items(), self.before)
        self.assertEqual(self.files(), files)
        self.assertEqual(self.cleanup.undo(result['operation_id'])['status'], 'undone')

    def test_unique_unknown_and_shared_source_items_are_never_archived(self):
        items = self.library.items()
        self.item(items, 'a')['sha256'] = '1' * 64  # No matching keeper.
        self.item(items, 'a', '1.jpg')['sha256'] = None
        shared = copy.deepcopy(self.item(items, 'b'))
        shared['media_id'] = 'shared'
        shared['locations'].append({**shared['locations'][0], 'source_id': 'a'})
        self.library.commit(items + [shared])
        result = self.cleanup.preview(self.left, self.right)
        self.assertEqual(result['archive_count'], 0)
        self.assertEqual(result['skipped'], {'no_duplicate': 1, 'unknown_hash': 1, 'shared_item': 1})
        with self.assertRaises(ValueError):
            self.cleanup.execute(result['operation_id'])
        shared['classification']['category_id'] = 'photo_box'
        shared['locations'][0]['source_id'] = 'third'
        self.library.commit(items + [shared])
        result = self.cleanup.preview(self.left, self.right)
        self.assertEqual(result['skipped']['shared_source'], 1)

    def test_preview_and_undo_refuse_stale_targets_without_touching_files(self):
        plan = self.cleanup.preview(self.left, self.right)
        items = self.library.items()
        self.item(items, 'b')['classification']['tags'].append('keeper-edited')
        self.library.commit(items)
        with self.assertRaisesRegex(ValueError, '새 미리보기'):
            self.cleanup.execute(plan['operation_id'])
        plan = self.cleanup.preview(self.left, self.right)
        self.cleanup.execute(plan['operation_id'])
        items = self.library.items()
        self.item(items, 'a')['classification']['tags'].append('edited-later')
        self.library.commit(items)
        with self.assertRaisesRegex(ValueError, '대상 DB 항목이 변경'):
            self.cleanup.undo(plan['operation_id'])

    def test_unrelated_family_edit_survives_execute_and_undo(self):
        plan = self.cleanup.preview(self.left, self.right)
        items = self.library.items()
        family = next(item for item in items if item['media_id'] == 'family-only')
        family['classification']['tags'].append('new-family-tag')
        self.library.commit(items)
        self.cleanup.execute(plan['operation_id'])
        self.cleanup.undo(plan['operation_id'])
        self.assertEqual(next(item for item in self.library.items() if item['media_id'] == 'family-only'), family)

    def test_commit_complete_record_interruption_can_resume_and_undo(self):
        plan = self.cleanup.preview(self.left, self.right)
        save = self.cleanup.save
        def interrupted_save(record):
            if record['status'] == 'completed':
                raise OSError('simulated interruption after DB commit')
            save(record)
        with patch.object(self.cleanup, 'save', side_effect=interrupted_save):
            with self.assertRaises(OSError):
                self.cleanup.execute(plan['operation_id'])
        self.assertEqual(self.cleanup.load(plan['operation_id'])['status'], 'applying')
        self.cleanup.execute(plan['operation_id'])
        def interrupted_undo(record):
            if record['status'] == 'undone':
                raise OSError('simulated interruption after undo commit')
            save(record)
        with patch.object(self.cleanup, 'save', side_effect=interrupted_undo):
            with self.assertRaises(OSError):
                self.cleanup.undo(plan['operation_id'])
        self.assertEqual(self.cleanup.load(plan['operation_id'])['status'], 'undoing')
        self.cleanup.undo(plan['operation_id'])
        self.assertEqual(self.library.items(), self.before)

    def test_scope_validation_and_options_include_db_only_sources_and_categories(self):
        for invalid in (None, {}, {'source_id': 'a'}, {'source_id': '../a', 'category': 'photo_box'}):
            with self.assertRaises(ValueError):
                self.cleanup.preview(invalid, self.right)
        with self.assertRaises(ValueError):
            self.cleanup.preview(self.left, self.left)
        with self.assertRaises(ValueError):
            self.cleanup.load('../bad')
        config = self.library.config()
        config['sources'] = [source for source in config['sources'] if source['source_id'] != 'a']
        self.library.save_config(config)
        options = SourceComparison(self.library).options()
        source = next(source for source in options['sources'] if source['source_id'] == 'a')
        self.assertFalse(source['registered'])
        self.assertEqual(source['categories'], ['family', 'photo_box'])

    def test_api_auth_preview_execute_undo(self):
        import time
        url = '/api/duplicate-db-cleanups'
        self.assertEqual(self.client.post(url + '/preview', json={'remove': self.left, 'keep': self.right}).status_code, 403)
        def wait(response):
            self.assertEqual(response.status_code, 202, response.json)
            for _ in range(500):
                state = self.client.get('/api/jobs/' + response.json['job_id']).json
                if state['status'] not in {'running', 'queued', 'stopping'}:
                    self.assertEqual(state['status'], 'completed', state)
                    return state['result']
                time.sleep(0.01)
            self.fail('Job timeout')
        self.assertEqual(self.client.get('/api/source-comparisons/options').status_code, 200)
        plan = wait(self.client.post(url + '/preview', json={'remove': self.left, 'keep': self.right}, headers=self.headers))
        token = plan['operation_id']
        self.assertEqual(len(self.client.get(f'{url}/{token}?offset=1').json['rows']), 1)
        wait(self.client.post(f'{url}/{token}/run', json={}, headers=self.headers))
        wait(self.client.post(f'{url}/{token}/undo', json={}, headers=self.headers))
        self.assertEqual(self.client.get(url).json['items'][0]['status'], 'undone')
        self.assertEqual(self.library.items(), self.before)

    def test_other_jobs_are_rejected_while_db_cleanup_preview_is_active(self):
        import threading
        import time
        entered, release = threading.Event(), threading.Event()
        original = DuplicateCleanup.preview
        def blocked(store, remove, keep):
            entered.set()
            release.wait(5)
            return original(store, remove, keep)
        with patch.object(DuplicateCleanup, 'preview', autospec=True, side_effect=blocked):
            started = self.client.post('/api/duplicate-db-cleanups/preview',
                                       json={'remove': self.left, 'keep': self.right}, headers=self.headers)
            try:
                self.assertEqual(started.status_code, 202)
                self.assertTrue(entered.wait(2))
                rejected = self.client.post('/api/merge', json={'preview': False}, headers=self.headers)
                self.assertEqual(rejected.status_code, 400)
                self.assertIn('실행 중인 작업', rejected.json['error'])
            finally:
                release.set()
            for _ in range(500):
                state = self.client.get('/api/jobs/' + started.json['job_id']).json
                if state['status'] not in {'running', 'queued', 'stopping'}:
                    break
                time.sleep(0.01)
            self.assertEqual(state['status'], 'completed', state)

    def test_later_scan_does_not_reactivate_archived_duplicates(self):
        plan = self.cleanup.preview(self.left, self.right)
        self.cleanup.execute(plan['operation_id'])
        self.library.scan('a')
        archived = [item for item in self.library.items() if item['lifecycle']['status'] == 'duplicate_archived']
        self.assertEqual(len(archived), 2)

    def test_legacy_metadata_is_not_normalized_in_unrelated_or_restored_items(self):
        items = self.library.items()
        for item in items:
            item['classification'].pop('location_tags', None)
        self.library.commit(items, normalize_metadata=False)
        before = self.library.items()
        plan = self.cleanup.preview(self.left, self.right)
        self.cleanup.execute(plan['operation_id'])
        family = next(item for item in self.library.items() if item['media_id'] == 'family-only')
        self.assertNotIn('location_tags', family['classification'])
        self.cleanup.undo(plan['operation_id'])
        self.assertEqual(self.library.items(), before)


if __name__ == '__main__':
    unittest.main()
