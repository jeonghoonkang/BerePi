import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from library import Library, atomic_json
from scan_engine import scan_sessions
from workflow import WorkflowStatus


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'incoming'
        self.source.mkdir()
        for index in range(2):
            Image.new('RGB', (8, 8), (index * 80, 10, 20)).save(self.source / f'{index}.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.workflow = WorkflowStatus(self.library)
        self.config = {'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                       'sources': [{'source_id': 'photos', 'protocol': 'file', 'root': str(self.source),
                                    'category': 'family', 'owner_id': 'alice'}]}

    def statuses(self, jobs=()):
        result = self.workflow.snapshot(jobs)
        return [s['status'] for s in result['steps']]

    def save_session(self, state):
        atomic_json(self.library.db / 'scans' / 'sessions' / state['scan_id'] / 'state.json', state)

    def test_empty_settings_scan_publication_and_complete_merge(self):
        self.assertEqual(self.statuses(), ['pending'] * 4)
        self.library.save_config(self.config)
        self.assertEqual(self.statuses(), ['completed', 'pending', 'pending', 'pending'])
        self.library.scan('photos')
        self.assertEqual(self.statuses(), ['completed', 'completed', 'completed', 'pending'])
        self.library.merge()
        result = self.workflow.snapshot()
        self.assertEqual([s['status'] for s in result['steps']], ['completed'] * 4)
        self.assertEqual(result['percent'], 100)
        self.assertEqual(result['completed_steps'], 4)
        self.assertEqual(WorkflowStatus(self.library).snapshot()['percent'], 100)

    def test_live_listing_and_publication_have_indeterminate_bars(self):
        self.library.save_config(self.config)
        state = self.library.scan('photos')
        for phase in ('listing', 'publishing'):
            progress = {**state, 'phase': phase, 'status': 'running', 'published': False,
                        'inventory_complete': phase != 'listing', 'processed': 0 if phase == 'listing' else 2}
            job = {'job_id': 'job1', 'kind': 'scan', 'source_id': 'photos', 'status': 'running',
                   'created_at': state['created_at'], 'progress': progress}
            result = self.workflow.snapshot([job])
            active = result['steps'][1 if phase == 'listing' else 2]
            self.assertEqual(active['status'], 'running')
            self.assertIsNone(active['percent'])
            if phase == 'publishing':
                self.assertEqual(result['steps'][1]['status'], 'completed')
            self.assertLess(result['percent'], 100)

    def test_partial_stopped_and_file_errors_never_complete(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        state = scan_sessions(self.library)[0]
        state.update(status='stopped', processed=1, published=True)
        self.save_session(state)
        result = self.workflow.snapshot()
        self.assertEqual(result['steps'][1]['status'], 'warning')
        self.assertEqual(result['steps'][2]['status'], 'warning')
        self.assertLess(result['percent'], 100)
        state.update(status='completed', processed=2, errors=[{'error': 'unreadable'}])
        self.save_session(state)
        self.assertEqual(self.statuses()[1:3], ['warning', 'warning'])

    def test_source_added_or_changed_requires_new_scan(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        self.library.merge()
        config = self.library.config()
        config['sources'][0]['owner_id'] = 'bob'
        self.library.save_config(config)
        self.assertEqual(self.statuses()[1], 'warning')
        self.assertNotEqual(self.statuses()[3], 'completed')
        self.library.scan('photos')
        other = self.root / 'second'
        other.mkdir()
        config['sources'].append({'source_id': 'second', 'protocol': 'file', 'root': str(other)})
        self.library.save_config(config)
        self.assertNotEqual(self.statuses()[1], 'completed')
        self.assertNotEqual(self.statuses()[2], 'completed')
        self.assertEqual(self.workflow.snapshot()['steps'][1]['percent'], 50)

    def test_partial_copy_and_classification_change_invalidate_merge_completion(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        items = self.library.items()
        self.library.merge([items[0]['media_id']])
        result = self.workflow.snapshot()
        self.assertEqual(result['steps'][3]['percent'], 50)
        self.assertEqual(result['steps'][3]['status'], 'warning')
        self.library.merge()
        self.assertEqual(self.statuses()[3], 'completed')
        self.library.edit([items[0]['media_id']], {'category_id': 'work'})
        result = self.workflow.snapshot()
        self.assertEqual(result['steps'][3]['percent'], 50)
        self.assertNotEqual(result['steps'][3]['status'], 'completed')

    def test_blocked_failed_and_running_merge_jobs_override_old_success(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        self.library.merge()
        for status, expected in [('blocked_low_space', 'warning'), ('stopped', 'warning'), ('failed', 'failed'), ('running', 'running')]:
            result = self.workflow.snapshot([{'job_id': status, 'kind': 'merge', 'status': status,
                                             'created_at': '9999', 'progress': {'processed': 1, 'total': 2, 'percent': 50}}])
            self.assertEqual(result['steps'][3]['status'], expected)
            self.assertLess(result['percent'], 100)

    def test_completed_job_with_operation_errors_is_not_green(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        self.library.merge()
        job = {'job_id': 'failed-files', 'kind': 'merge', 'status': 'completed', 'created_at': '9999',
               'result': {'status': 'completed', 'operations': [{'status': 'error'}]}}
        self.assertEqual(self.workflow.snapshot([job])['steps'][3]['status'], 'warning')

    def test_restart_failed_scan_overlays_persisted_running_state(self):
        self.library.save_config(self.config)
        state = self.library.scan('photos')
        state.update(status='running', phase='processing', processed=1, published=False)
        self.save_session(state)
        job = {'job_id': 'old', 'kind': 'scan', 'source_id': 'photos', 'created_at': state['created_at'],
               'status': 'interrupted', 'progress': {'scan_id': state['scan_id']}}
        self.assertEqual(self.statuses([job])[1], 'warning')
        self.assertNotEqual(self.statuses([job])[2], 'completed')

    def test_catalog_counts_cached_until_immutable_generation_changes(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        self.workflow.snapshot()
        from workflow import read_json
        read_chunks = []
        def reading(path, *args, **kwargs):
            if '/media/' in str(path):
                read_chunks.append(path)
            return read_json(path, *args, **kwargs)
        with patch('workflow.read_json', side_effect=reading):
            self.workflow.snapshot()
            self.workflow.snapshot()
        self.assertEqual(read_chunks, [])
        self.library.merge()
        self.assertEqual(self.statuses()[3], 'completed')

    def test_api_restores_cli_progress_and_has_no_cache(self):
        self.library.save_config(self.config)
        self.library.scan('photos')
        self.library.merge()
        client = create_app(self.root, self.root, self.library.db).test_client()
        result = client.get('/api/workflow')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(result.json['percent'], 100)
        page = client.get('/').get_data(as_text=True)
        self.assertIn('id="workflow-steps"', page)
        self.assertIn('workflow.js', page)

    def test_empty_scan_has_no_copy_work_and_does_not_claim_100_percent(self):
        for path in self.source.iterdir():
            path.unlink()
        self.library.save_config(self.config)
        self.library.scan('photos')
        result = self.workflow.snapshot()
        self.assertEqual([s['status'] for s in result['steps'][:3]], ['completed'] * 3)
        self.assertEqual(result['steps'][3]['percent'], 0)
        self.assertLess(result['percent'], 100)


if __name__ == '__main__':
    unittest.main()
