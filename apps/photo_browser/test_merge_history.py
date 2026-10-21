import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app import create_app
from library import atomic_json, read_json
from merge_history import directory_snapshot, list_reports, render_html


class MergeHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.managed = self.root / 'managed'
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']
        self.library.save_config({'managed_root': str(self.managed), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'family_photos', 'root': str(self.source), 'protocol': 'file', 'category': 'family', 'owner_id': 'alice'}]})

    def tearDown(self):
        self.temp.cleanup()

    def photo(self, name='photo.jpg', color='red'):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        exif = Image.Exif()
        exif[36867] = '2024:03:05 12:30:00'
        Image.new('RGB', (8, 8), color).save(path, exif=exif)
        return path

    def report(self, result):
        return read_json(Path(result['history_report']['files']['json']))

    def test_report_has_times_sources_duplicates_renames_and_before_after(self):
        original = self.photo()
        same = self.source / 'same/photo.jpg'
        same.parent.mkdir()
        same.write_bytes(original.read_bytes())
        self.photo('different/photo.jpg', 'blue')
        self.managed.mkdir()
        (self.managed / 'keep.bin').write_bytes(b'keep')
        (self.managed / 'empty').mkdir()
        (self.managed / '.trash').mkdir()
        (self.managed / '.trash/ignored.jpg').write_bytes(b'excluded')
        self.library.scan('family_photos')
        result = self.library.merge()
        report = self.report(result)
        self.assertEqual(report['status'], 'completed')
        self.assertLessEqual(datetime.fromisoformat(report['started_at']), datetime.fromisoformat(report['finished_at']))
        self.assertGreaterEqual(report['duration_seconds'], 0)
        self.assertEqual(report['summary']['target_count'], 3)
        self.assertEqual(report['summary']['copied_count'], 2)
        self.assertEqual(report['summary']['reused_count'], 1)
        self.assertEqual(report['summary']['identical_content_duplicate_count'], 1)
        self.assertEqual(report['summary']['renamed_copied_count'], 1)
        self.assertEqual(len(report['renamed_files']), 1)
        renamed = report['renamed_files'][0]
        self.assertIn('_중복', renamed['destination'])
        self.assertEqual(Path(renamed['destination']).read_bytes(), Path(renamed['source_locations'][0]['path']).read_bytes())
        self.assertEqual(report['sources'][0]['source_id'], 'family_photos')
        self.assertEqual(report['sources'][0]['owner_id'], 'alice')
        self.assertEqual(report['sources'][0]['category_id'], 'family')
        self.assertEqual(report['sources'][0]['root'], str(self.source))
        self.assertEqual(report['before']['file_count'], 1)
        self.assertEqual(report['before']['total_bytes'], 4)
        self.assertEqual(report['after']['file_count'], 3)
        self.assertEqual(report['delta']['added_count'], 2)
        self.assertEqual(report['delta']['removed_count'], 0)
        self.assertEqual(report['delta']['total_bytes_change'], report['summary']['copied_bytes'])
        self.assertNotIn('.trash', [d['path'] for d in report['after']['directories']])
        by_directory = {d['path']: d for d in report['after']['directories']}
        self.assertEqual(by_directory['family']['file_count'], 2)
        self.assertEqual(by_directory['empty']['file_count'], 0)
        html = Path(result['history_report']['files']['html']).read_text(encoding='utf-8')
        for text in ['KST', '병합 전 디렉토리 구성', '병합 후 디렉토리 구성', '실제로 추가된 파일', 'family_photos']:
            self.assertIn(text, html)
        self.assertEqual(list_reports(self.library)[0]['report_id'], report['report_id'])

    def test_repeated_merge_reports_reuse_and_zero_added_bytes(self):
        self.photo()
        self.library.scan('family_photos')
        first = self.library.merge()
        second = self.library.merge()
        self.assertNotEqual(first['history_report']['report_id'], second['history_report']['report_id'])
        report = self.report(second)
        self.assertEqual(report['summary']['reused_count'], 1)
        self.assertEqual(report['summary']['copied_count'], 0)
        self.assertEqual(report['delta']['added_count'], 0)
        self.assertEqual(report['delta']['total_bytes_change'], 0)

    def test_stop_and_resume_create_separate_linked_run_reports(self):
        for index in range(3):
            self.photo(f'{index}.jpg')
        self.library.scan('family_photos')
        stop = [False]
        def progress(value):
            if value.get('processed', 0) >= 1:
                stop[0] = True
        first = self.library.merge(progress=progress, stopped=lambda: stop[0])
        second = self.library.merge(resume=first['merge_id'])
        first_report, second_report = self.report(first), self.report(second)
        self.assertEqual(first_report['status'], 'stopped')
        self.assertEqual(first_report['summary']['copied_count'], 1)
        self.assertEqual(second_report['merge_id'], first_report['merge_id'])
        self.assertEqual(second['merge_started_at'], first['merge_started_at'])
        self.assertEqual(second_report['merge_started_at'], first['merge_started_at'])
        self.assertLessEqual(datetime.fromisoformat(first['merge_started_at']), datetime.fromisoformat(second['run_started_at']))
        self.assertNotEqual(first_report['report_id'], second_report['report_id'])
        self.assertEqual(second_report['summary']['previous_processed_count'], 1)
        self.assertEqual(second_report['summary']['target_count'], 2)
        self.assertEqual(second_report['summary']['processed_count'], 2)
        self.assertEqual(second_report['delta']['added_count'], 2)
        self.assertEqual(len(second_report['operations']), 2)
        state = read_json(self.library.db / 'merges' / (first['merge_id'] + '.json'))
        self.assertEqual(state['history_report_ids'], [first_report['report_id'], second_report['report_id']])
        self.assertEqual(state['merge_started_at'], first['merge_started_at'])

    def test_low_space_and_file_errors_are_reported_without_claiming_copies(self):
        original = self.photo()
        self.library.scan('family_photos')
        with patch('library.shutil.disk_usage', return_value=SimpleNamespace(free=0)):
            blocked = self.library.merge()
        report = self.report(blocked)
        self.assertEqual(report['status'], 'blocked_low_space')
        self.assertEqual(report['summary']['target_count'], 1)
        self.assertEqual(report['summary']['processed_count'], 0)
        self.assertEqual(report['delta']['added_count'], 0)
        original.unlink()
        failed = self.report(self.library.merge())
        self.assertEqual(failed['summary']['error_count'], 1)
        self.assertEqual(failed['summary']['copied_count'], 0)
        self.assertIn('error', failed['operations'][0])

    def test_preview_does_not_create_execution_history(self):
        self.photo()
        self.library.scan('family_photos')
        result = self.library.merge(preview=True)
        self.assertNotIn('history_report', result)
        self.assertFalse((self.library.db / 'reports').exists())

    def test_unexpected_merge_failure_leaves_failed_history(self):
        self.photo()
        self.library.scan('family_photos')
        with patch.object(self.library, 'commit', side_effect=OSError('DB write failed')):
            with self.assertRaisesRegex(OSError, 'DB write failed'):
                self.library.merge()
        summary = list_reports(self.library)[0]
        self.assertEqual(summary['status'], 'failed')
        self.assertEqual(summary['summary']['copied_count'], 0)
        report = read_json(Path(summary['files']['json']))
        self.assertIn('DB write failed', report['warning'])

    def test_report_finish_failure_does_not_hide_successful_copies(self):
        self.photo()
        self.library.scan('family_photos')
        with patch('merge_history.MergeHistory.finish', side_effect=OSError('report disk error')):
            result = self.library.merge()
        self.assertEqual(result['operations'][0]['status'], 'copied')
        self.assertTrue(Path(result['operations'][0]['destination']).exists())
        self.assertEqual(result['history_report_error'], 'report disk error')
        self.assertIn('보고서 저장 실패', result['warning'])

    def test_snapshots_capture_non_media_files_and_partial_errors(self):
        self.managed.mkdir()
        (self.managed / 'notes.txt').write_bytes(b'notes')
        (self.managed / '.temporary.part').write_bytes(b'staging')
        before = directory_snapshot(self.managed)
        self.assertEqual(before['file_count'], 1)
        self.assertEqual(before['total_bytes'], 5)
        def unreadable(root, **kwargs):
            kwargs['onerror'](PermissionError('permission denied'))
            return iter(())
        with patch('merge_history.os.walk', side_effect=unreadable):
            incomplete = directory_snapshot(self.managed)
        self.assertFalse(incomplete['complete'])
        self.assertIn('permission denied', incomplete['errors'][0])

    def test_html_escapes_paths_and_names(self):
        self.photo()
        self.library.scan('family_photos')
        report = self.report(self.library.merge())
        report['operations'][0]['name'] = '<script>alert("x")</script>'
        rendered = render_html(report)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_reports_api_pagination_download_and_auth(self):
        self.photo()
        self.library.scan('family_photos')
        result = self.library.merge()
        report_id = result['history_report']['report_id']
        listing = self.client.get('/api/merge-reports?limit=1').json
        self.assertEqual(listing['total'], 1)
        self.assertEqual(listing['items'][0]['report_id'], report_id)
        self.assertEqual(self.client.get('/api/merge-reports?offset=1').json['items'], [])
        for format in ['json', 'html']:
            response = self.client.get(f'/api/merge-reports/{report_id}/{format}?download=1')
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            response.close()
        self.assertEqual(self.client.get('/api/merge-reports/unknown/json').status_code, 404)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-password'}):
            self.assertEqual(self.client.get('/api/merge-reports').status_code, 401)
            self.assertEqual(self.client.get(f'/api/merge-reports/{report_id}/html').status_code, 401)

    def test_legacy_jobs_recover_first_start_time_for_resumed_merge(self):
        for job_id, stamp in [('first', '2026-10-20T00:00:00+00:00'), ('resume', '2026-10-21T00:00:00+00:00')]:
            atomic_json(self.library.db / 'jobs' / (job_id + '.json'),
                        {'job_id': job_id, 'kind': 'merge', 'created_at': stamp,
                         'finished_at': stamp, 'status': 'completed', 'result': {'merge_id': 'legacy_merge'}})
        client = create_app(self.root, self.root, self.root / 'db').test_client()
        result = client.get('/api/jobs/resume').json
        self.assertEqual(result['merge_started_at'], '2026-10-20T00:00:00+00:00')
        self.assertIn('server_time', result)
        listing = client.get('/api/jobs').json
        self.assertTrue(all(job['merge_started_at'] == result['merge_started_at'] for job in listing['items']))


if __name__ == '__main__':
    unittest.main()
