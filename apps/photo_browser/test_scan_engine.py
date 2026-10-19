import json
import errno
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app import create_app
from library import Library, read_json
from scan_engine import MIB, ScanEngine, scan_sessions


class ScanControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'incoming'
        self.source.mkdir()
        for index in range(5):
            Image.new('RGB', (8, 8), (index * 30, 40, 80)).save(self.source / f'{index}.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.config = {'managed_root': str(self.root / 'organized'), 'scan_min_free_mb': 32, 'sources': [{'source_id': 'photos', 'root': str(self.source), 'protocol': 'file', 'category': 'family', 'owner_id': 'alice'}]}
        self.library.save_config(self.config)

    def tearDown(self):
        self.temp.cleanup()

    def stop_after(self, count, listing=False):
        stop = threading.Event()
        def progress(state):
            if listing:
                if not state['inventory_complete'] and state['total'] >= count:
                    stop.set()
            elif state['processed'] >= count:
                stop.set()
        return self.library.scan('photos', progress=progress, stopped=stop.is_set)

    def test_stop_resume_after_new_library_instance_preserves_edits(self):
        report = self.stop_after(2)
        self.assertEqual((report['status'], report['total'], report['processed']), ('stopped', 5, 2))
        self.assertEqual(len(self.library.items()), 2)
        item = self.library.items()[0]
        self.library.edit([item['media_id']], {'events': ['휴가']})
        restarted = Library(self.root / 'db', self.root)
        with patch.object(ScanEngine, 'process', autospec=True, side_effect=ScanEngine.process) as process:
            complete = restarted.scan('photos', mode='resume')
        self.assertEqual(process.call_count, 3)
        self.assertEqual(complete['status'], 'completed')
        self.assertEqual(complete['processed'], 5)
        self.assertEqual(len(restarted.items()), 5)
        self.assertEqual(next(i for i in restarted.items() if i['media_id'] == item['media_id'])['classification']['events'], ['휴가'])
        with self.assertRaises(ValueError):
            restarted.scan('photos', mode='resume')

    def test_restart_recounts_and_reanalyzes_every_file(self):
        first = self.stop_after(2)
        with patch.object(ScanEngine, 'process', autospec=True, side_effect=ScanEngine.process) as process:
            report = self.library.scan('photos', mode='restart')
        self.assertNotEqual(report['scan_id'], first['scan_id'])
        self.assertEqual(process.call_count, 5)
        self.assertTrue(report['full'])
        self.assertEqual(len(self.library.items()), 5)

    def test_stop_while_counting_resumes_without_duplicate_inventory(self):
        report = self.stop_after(2, listing=True)
        self.assertEqual(report['status'], 'stopped')
        self.assertFalse(report['inventory_complete'])
        self.assertEqual(report['processed'], 0)
        self.assertIsNone(report['percent'])
        complete = self.library.scan('photos', mode='resume')
        self.assertEqual((complete['total'], complete['processed']), (5, 5))
        self.assertEqual(len(self.library.items()), 5)

    def test_disk_shortage_checkpoints_then_resumes(self):
        low = [False]
        def progress(state):
            if state['processed'] >= 2:
                low[0] = True
        def disk(path):
            return SimpleNamespace(free=(16 if low[0] else 4096) * MIB)
        with patch('scan_engine.shutil.disk_usage', side_effect=disk):
            paused = self.library.scan('photos', progress=progress)
        self.assertEqual(paused['status'], 'paused_low_space')
        self.assertEqual(paused['processed'], 2)
        self.assertIn('공간', paused['warning'])
        complete = self.library.scan('photos', mode='resume')
        self.assertEqual(complete['processed'], 5)
        self.assertEqual(complete['status'], 'completed')

    def test_low_disk_before_processing_and_configuration_validation(self):
        with patch('scan_engine.shutil.disk_usage', return_value=SimpleNamespace(free=16 * MIB)):
            report = self.library.scan('photos')
        self.assertEqual(report['status'], 'paused_low_space')
        self.assertEqual(report['processed'], 0)
        self.assertFalse(report['inventory_complete'])
        self.assertEqual(self.library.scan('photos', mode='resume')['processed'], 5)
        for value in [0, -1, True, '32']:
            with self.assertRaises(ValueError):
                self.library.save_config({**self.config, 'scan_min_free_mb': value})

    def test_final_publication_space_check_is_resumable(self):
        original_publish = ScanEngine.publish
        def unavailable(engine, records):
            if engine.state['status'] == 'completed':
                return False
            return original_publish(engine, records)
        with patch.object(ScanEngine, 'publish', unavailable):
            report = self.library.scan('photos')
        self.assertEqual(report['status'], 'paused_low_space')
        self.assertEqual(report['processed'], 5)
        with patch.object(ScanEngine, 'process', side_effect=AssertionError('must not reprocess')):
            complete = self.library.scan('photos', mode='resume')
        self.assertEqual(complete['status'], 'completed')
        self.assertEqual(len(self.library.items()), 5)

    def test_stop_publication_failure_keeps_resumable_journal(self):
        with patch.object(self.library, 'commit', side_effect=OSError(errno.ENOSPC, 'disk full')):
            report = self.stop_after(2)
        self.assertEqual(report['status'], 'paused_low_space')
        self.assertEqual(report['processed'], 2)
        self.assertFalse(report['published'])
        self.assertEqual(self.library.scan('photos', mode='resume')['status'], 'completed')
        self.assertEqual(len(self.library.items()), 5)

    def test_resuming_rejects_changed_source_and_handles_torn_journal(self):
        report = self.stop_after(2)
        folder = self.root / 'db/scans/sessions' / report['scan_id']
        with (folder / 'results.jsonl').open('ab') as stream:
            stream.write(b'{"ordinal": 2')
        changed = {**self.config, 'sources': [{**self.config['sources'][0], 'category': 'work'}]}
        self.library.save_config(changed)
        with self.assertRaises(ValueError):
            self.library.scan('photos', mode='resume')
        self.library.save_config(self.config)
        self.assertEqual(self.library.scan('photos', mode='resume')['processed'], 5)

    def test_partial_scan_never_marks_unvisited_existing_files_missing(self):
        self.library.scan('photos')
        (self.source / '4.jpg').unlink()
        report = self.stop_after(2)
        self.assertEqual(report['status'], 'stopped')
        self.assertTrue(all(i['locations'][0]['status'] == 'available' for i in self.library.items()))
        self.library.scan('photos', mode='resume')
        item = next(i for i in self.library.items() if i['name'] == '4.jpg')
        self.assertEqual(item['locations'][0]['status'], 'missing')

    def test_remote_transfer_checks_temp_disk_and_is_interruptible(self):
        # Exercise the streaming callback without a real remote server.
        import io
        location = {'source_id': 'remote', 'protocol': 'http', 'uri': 'http://localhost/photos/a.jpg'}
        source = {'source_id': 'remote', 'root': 'http://localhost/photos/', 'protocol': 'http'}
        self.library.save_config({**self.config, 'sources': self.config['sources'] + [source]})
        response = io.BytesIO(b'x' * (3 * MIB))
        response.headers = {'Content-Length': str(3 * MIB)}
        calls = []
        def transfer(total, downloaded):
            calls.append((total, downloaded))
            if downloaded >= MIB:
                from scan_engine import ScanPause
                raise ScanPause('stopped', 'stop download')
        with patch.object(self.library, 'remote_open', return_value=response):
            from scan_engine import ScanPause
            with self.assertRaises(ScanPause):
                with self.library.materialize(location, transfer=transfer):
                    self.fail('download should stop before yielding')
        self.assertTrue(any(downloaded >= MIB for _, downloaded in calls))

    def test_api_stop_progress_job_reload_and_resume(self):
        app = create_app(self.root, self.root, self.root / 'db')
        client = app.test_client()
        headers = {'X-Photo-Browser': '1'}
        entered, release = threading.Event(), threading.Event()
        original = ScanEngine.process
        def slow(engine, *args):
            entered.set()
            release.wait(5)
            return original(engine, *args)
        with patch.object(ScanEngine, 'process', slow):
            started = client.post('/api/scan', json={'source_id': 'photos'}, headers=headers)
            job_id = started.json['job_id']
            self.assertTrue(entered.wait(5))
            response = client.get('/api/jobs/' + job_id)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            status = response.json
            self.assertTrue(status['progress']['inventory_complete'])
            self.assertEqual(status['progress']['total'], 5)
            duplicate = client.post('/api/scan', json={'source_id': 'photos'}, headers=headers)
            self.assertEqual(duplicate.status_code, 400)
            self.assertEqual(client.post('/api/jobs/' + job_id + '/stop', json={}, headers=headers).status_code, 200)
            release.set()
            for _ in range(300):
                status = client.get('/api/jobs/' + job_id).json
                if status['status'] not in {'queued', 'running', 'stopping'}:
                    break
                time.sleep(0.01)
        self.assertEqual(status['status'], 'stopped')
        reloaded = create_app(self.root, self.root, self.root / 'db').test_client()
        self.assertEqual(reloaded.get('/api/jobs/' + job_id).json['status'], 'stopped')
        self.assertEqual(reloaded.get('/api/scans').json['items'][0]['status'], 'stopped')
        started = reloaded.post('/api/scan', json={'source_id': 'photos', 'mode': 'resume'}, headers=headers)
        self.assertEqual(started.status_code, 202)
        for _ in range(300):
            result = reloaded.get('/api/jobs/' + started.json['job_id']).json
            if result['status'] not in {'queued', 'running', 'stopping'}:
                break
            time.sleep(0.01)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['result']['processed'], 5)

    def test_process_crash_releases_lock_and_replays_durable_results(self):
        script = '''
import os, sys, time
from pathlib import Path
from library import Library
from scan_engine import ScanEngine
root = Path(sys.argv[1])
original = ScanEngine.process
def slow(engine, *args):
    time.sleep(1.05)
    return original(engine, *args)
ScanEngine.process = slow
def progress(state):
    if state['processed'] >= 3:
        os._exit(77)
Library(root / 'db', root).scan('photos', progress=progress)
'''
        crashed = subprocess.run([sys.executable, '-c', script, str(self.root)], cwd=Path(__file__).parent, timeout=20)
        self.assertEqual(crashed.returncode, 77)
        checkpoint = scan_sessions(self.library)[0]
        self.assertEqual(checkpoint['processed'], 2)
        self.assertEqual(checkpoint['status'], 'running')
        with patch.object(ScanEngine, 'process', autospec=True, side_effect=ScanEngine.process) as process:
            report = self.library.scan('photos', mode='resume')
        self.assertEqual(process.call_count, 3)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(len(self.library.items()), 5)

    def test_temporary_download_volume_is_checked_separately(self):
        engine = ScanEngine(self.library, 'photos')
        engine.reserve = 32 * MIB
        engine.state = {'total': 5, 'processed': 0}
        def disk(path):
            return SimpleNamespace(free=(4096 if Path(path) == self.library.db else 16) * MIB)
        from scan_engine import ScanPause
        with patch('scan_engine.shutil.disk_usage', side_effect=disk):
            with self.assertRaises(ScanPause) as paused:
                engine.check(extra=2 * MIB, temporary=True, force=True)
        self.assertEqual(paused.exception.status, 'paused_low_space')
        self.assertIn('임시 디스크', paused.exception.warning)


if __name__ == '__main__':
    unittest.main()
