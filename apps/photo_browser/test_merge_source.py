import contextlib
import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from test_support import create_app
from cli import main
from library import read_json
from merge_status import merge_status


class SourceMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}
        sources = []
        for number in range(1, 4):
            folder = self.root / f'source{number}'
            folder.mkdir()
            for index in range(2):
                Image.new('RGB', (8, 8), (number * 50, index * 60, 10)).save(folder / f'photo{index}.jpg')
            sources.append({'source_id': f'source{number}', 'root': str(folder), 'protocol': 'file',
                            'category': f'category{number}', 'owner_id': 'alice'})
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32, 'sources': sources})
        for source in sources[:2]:
            self.library.scan(source['source_id'])

    def tearDown(self):
        self.temp.cleanup()

    def test_unscanned_third_source_never_falls_back_to_existing_sources(self):
        with patch.object(self.library, 'merge_space', side_effect=AssertionError('Must not process all sources')):
            for preview in (False, True):
                with self.assertRaisesRegex(ValueError, 'source3.*스캔'):
                    self.library.merge(source_id='source3', preview=preview)
        self.assertEqual(len(self.library.items()), 4)
        self.assertFalse(any(i['locations'][-1]['role'] == 'managed' for i in self.library.items()))

    def test_third_source_limits_preflight_preview_copy_and_report(self):
        self.library.scan('source3')
        before = {i['media_id']: i for i in self.library.items() if i['locations'][0]['source_id'] != 'source3'}
        preview = self.library.merge(source_id='source3', preview=True)
        self.assertEqual(preview['total'], 2)
        self.assertEqual(preview['scope_source_id'], 'source3')
        updates = []
        with patch.object(self.library, 'merge_space', wraps=self.library.merge_space) as check:
            result = self.library.merge(source_id='source3', progress=updates.append)
        pending = check.call_args.args[2]
        self.assertEqual(len(pending), 2)
        self.assertTrue(all(i['locations'][0]['source_id'] == 'source3' for i in pending))
        self.assertEqual(result['total'], 2)
        self.assertEqual(len(result['operations']), 2)
        self.assertTrue(all(p.get('scope_source_id') == 'source3' for p in updates))
        for item in self.library.items():
            if item['media_id'] in before:
                self.assertEqual(item, before[item['media_id']])
            else:
                self.assertTrue(Path(item['locations'][-1]['path']).exists())
        report = read_json(Path(result['history_report']['files']['json']))
        self.assertEqual(report['scope_source_id'], 'source3')
        self.assertEqual({s['source_id'] for s in report['sources']}, {'source3'})
        self.assertEqual(merge_status(self.library.db)['items'][0]['scope_source_id'], 'source3')

    def test_resume_keeps_original_scope_and_target_ids(self):
        self.library.scan('source3')
        stop = [False]
        def progress(value):
            if value.get('processed', 0) >= 1 and value.get('phase') == 'merging':
                stop[0] = True
        first = self.library.merge(source_id='source3', progress=progress, stopped=lambda: stop[0])
        self.assertEqual(first['status'], 'stopped')
        self.assertEqual(first['processed'], 1)
        with self.assertRaisesRegex(ValueError, '범위'):
            self.library.merge(resume=first['merge_id'], source_id='source1')
        result = self.library.merge(resume=first['merge_id'])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['scope_source_id'], 'source3')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual({i['locations'][0]['source_id'] for i in self.library.items() if i['locations'][-1]['role'] == 'managed'}, {'source3'})

    def test_empty_ids_does_not_mean_all_and_unscoped_merge_remains_available(self):
        self.assertEqual(self.library.merge(ids=[], preview=True)['total'], 0)
        self.assertEqual(self.library.merge(preview=True)['total'], 4)
        with self.assertRaisesRegex(ValueError, '등록된'):
            self.library.merge(source_id='not_registered')

    def test_background_api_and_cli_accept_scope(self):
        self.library.scan('source3')
        started = self.client.post('/api/merge', json={'source_id': 'source3', 'preview': False}, headers=self.headers)
        self.assertEqual(started.status_code, 202)
        for _ in range(500):
            status = self.client.get('/api/jobs/' + started.json['job_id']).json
            if status['status'] not in {'queued', 'running', 'stopping'}:
                break
            time.sleep(0.01)
        self.assertEqual(status['status'], 'completed', status)
        self.assertEqual(status['source_id'], 'source3')
        self.assertEqual(status['result']['total'], 2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['--db', str(self.library.db), '--root', str(self.root), 'merge', '--source-id', 'source3', '--preview'])
        self.assertEqual(code, 0)
        self.assertIn('"scope_source_id": "source3"', output.getvalue())
