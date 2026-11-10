import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_support import create_app
from library import atomic_json


class JobArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'db'
        self.job = {'job_id': 'scanjob', 'kind': 'scan', 'source_id': 'bigsoft', 'status': 'completed',
                    'created_at': '2026-11-01T23:00:00+00:00',
                    'started_at': '2026-11-02T00:00:00+00:00', 'finished_at': '2026-11-02T01:02:03+00:00',
                    'result': {'status': 'completed', 'processed': 36008, 'total': 36008, 'percent': 100,
                               'added': 0, 'updated': 0, 'unchanged': 36008, 'published': True,
                               'current_file': '/photos/인테리어/IMG_2992.JPG', 'errors': []}}
        atomic_json(self.db / 'jobs' / 'scanjob.json', self.job)
        self.app = create_app(self.root, self.root, self.db)
        self.client = self.app.test_client()
        self.headers = {'X-Photo-Browser': '1'}

    def archive(self, job_id='scanjob', headers=None):
        return self.client.post(f'/api/jobs/{job_id}/archive', json={},
                                headers=self.headers if headers is None else headers)

    def test_txt_times_results_path_and_metadata_survive_restart(self):
        self.assertFalse((self.db / 'job-archives').exists())
        response = self.archive()
        self.assertEqual(response.status_code, 200)
        path = Path(response.json['path'])
        self.assertEqual(path, self.db / 'job-archives' / 'scanjob.txt')
        text = path.read_text(encoding='utf-8')
        for expected in ('시작 시각: 2026-11-02 09:00:00 KST',
                         '완료 / 종료 시각: 2026-11-02 10:02:03 KST', '처리 개수: 36008',
                         '변경 없음: 36008', 'DB 반영: True', '/photos/인테리어/IMG_2992.JPG',
                         f'TXT 보관 경로: {path}', '전체 작업 기록 (JSON)'):
            self.assertIn(expected, text)
        self.assertEqual(json.loads(text.split('전체 작업 기록 (JSON)\n')[1])['result'], self.job['result'])
        current = self.client.get('/api/jobs/scanjob').json
        self.assertEqual(current['archive'], response.json)
        restarted = create_app(self.root, self.root, self.db).test_client()
        self.assertEqual(restarted.get('/api/jobs').json['items'][0]['archive'], response.json)
        self.assertEqual(current['started_at'], self.job['started_at'])
        self.assertEqual(current['finished_at'], self.job['finished_at'])

    def test_repeat_archive_and_write_failure_preserve_saved_file(self):
        first = self.archive().json
        path = Path(first['path'])
        original = path.read_bytes()
        with patch('job_archive.atomic_text', side_effect=OSError('disk full')):
            response = self.archive()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.client.get('/api/jobs/scanjob').json['archive'], first)
        self.assertEqual(self.archive().json['path'], str(path))
        self.assertEqual(len(list(path.parent.glob('*.txt'))), 1)

    def test_missing_dates_are_not_invented(self):
        job = {**self.job, 'job_id': 'legacy', 'status': 'failed', 'error': 'old failure'}
        job.pop('started_at'); job.pop('finished_at')
        atomic_json(self.db / 'jobs' / 'legacy.json', job)
        client = create_app(self.root, self.root, self.db).test_client()
        response = client.post('/api/jobs/legacy/archive', json={}, headers=self.headers)
        text = Path(response.json['path']).read_text(encoding='utf-8')
        self.assertIn('시작 시각: 기록 없음', text)
        self.assertIn('완료 / 종료 시각: 기록 없음', text)
        self.assertIn('error: old failure', text)

    def test_archive_requires_auth_headers_and_existing_job(self):
        self.assertEqual(self.archive(headers={}).status_code, 403)
        self.assertEqual(self.archive('missing').status_code, 404)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'secret'}):
            self.assertEqual(self.archive().status_code, 401)
        self.assertFalse((self.db / 'job-archives').exists())

    def test_running_job_cannot_be_archived(self):
        entered, release = threading.Event(), threading.Event()
        library = self.app.extensions['photo_library']
        def running(*args, **kwargs):
            entered.set(); release.wait(5)
            return {'status': 'completed'}
        with patch.object(library, 'scan', side_effect=running):
            started = self.client.post('/api/scan', json={'source_id': 'bigsoft'}, headers=self.headers)
            job_id = started.json['job_id']
            try:
                self.assertTrue(entered.wait(2))
                response = self.archive(job_id)
                self.assertEqual(response.status_code, 400)
                self.assertIn('종료된 뒤', response.json['error'])
                self.assertFalse((self.db / 'job-archives').exists())
            finally:
                release.set()
                for _ in range(200):
                    if self.client.get(f'/api/jobs/{job_id}').json['status'] == 'completed':
                        break
                    time.sleep(.01)


if __name__ == '__main__':
    unittest.main()
