import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cli import main
from prune_progress import PruneProgress


class PruneProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'db'
        self.db.mkdir()
        self.plan = self.root / 'plan.sqlite'

    def monitor(self, **kwargs):
        return PruneProgress(self.db, self.plan, 'db-prune-plan', **kwargs)

    def latest(self, path):
        return json.loads(path.read_text(encoding='utf-8').splitlines()[-1])

    def test_independent_heartbeat_runs_during_a_blocked_operation(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            with self.monitor(interval=.02, files=1) as monitor:
                monitor('hash-bytes', 1048576, '/source/slow-photo.jpg')
                threading.Event().wait(.09)  # No further progress callbacks.
                data = self.latest(monitor.path)
                self.assertEqual(data['phase'], 'hash-bytes')
                self.assertEqual(data['path'], '/source/slow-photo.jpg')
                self.assertGreater(data['elapsed_seconds'], .02)
                self.assertIsNone(data['progress_percent'])
        self.assertGreaterEqual(error.getvalue().count('slow-photo.jpg'), 2)
        self.assertEqual(self.latest(monitor.path)['status'], 'completed')
        self.assertIn('finished_at', self.latest(monitor.path))

    def test_rotation_stays_within_five_files_and_single_mode_removes_backups(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.monitor(interval=3600, max_bytes=4096) as monitor:
                for i in range(80):
                    monitor('hash', i, 'x' * 500)
                    monitor.write()
            files = [path for path in [monitor.path, *(Path(f'{monitor.path}.{i}') for i in range(1, 5))] if path.exists()]
            self.assertEqual(len(files), 5)
            self.assertTrue(all(path.stat().st_size <= 4096 for path in files))
            with self.monitor(interval=3600, files=1) as single:
                single('plan-total', 1000, 'media')
            self.assertTrue(single.path.is_file())
            self.assertFalse(any(Path(f'{single.path}.{i}').exists() for i in range(1, 5)))

    def test_percentage_eta_and_stalled_io_are_explicit(self):
        monitor = self.monitor()
        with patch('prune_progress.time.monotonic', return_value=0):
            monitor.started = 0
            monitor('plan-total', 100, 'media')
        for i in range(1, 11):
            with patch('prune_progress.time.monotonic', return_value=i):
                monitor('plan', i, 'media/file.json')
        with patch('prune_progress.time.monotonic', return_value=10):
            data = monitor.snapshot()
        self.assertEqual(data['progress_percent'], 10)
        self.assertEqual(data['estimated_remaining_seconds'], 90)
        self.assertEqual(data['elapsed_minutes'], .17)
        self.assertIsNotNone(data['estimated_finish_at'])
        with patch('prune_progress.time.monotonic', return_value=100):
            data = monitor.snapshot()
        self.assertEqual(data['estimate_status'], 'long_running_step')
        self.assertIsNone(data['estimated_finish_at'])

    def test_final_summary_and_failed_jobs_do_not_keep_a_future_eta(self):
        monitor = self.monitor()
        monitor('delete-total', 1, 'plan')
        monitor('delete', 1, 'media/file.json')
        monitor('summary', 1, 'plan')
        self.assertEqual(monitor.snapshot()['estimate_status'], 'finalizing')
        monitor.finish('completed')
        self.assertEqual(monitor.snapshot()['estimated_remaining_seconds'], 0)
        monitor.finish('failed')
        self.assertIsNone(monitor.snapshot()['estimated_finish_at'])

    def test_cli_always_saves_log_above_1000_files_and_keeps_stdout_json(self):
        def operation(*args, **kwargs):
            progress = args[7]
            progress('plan-total', 1001, 'media')
            for i in range(1001):
                progress('plan', i + 1, f'media/{i}.json')
            return {'status': 'ready'}
        out, err = io.StringIO(), io.StringIO()
        with patch('db_prune.plan_prune', side_effect=operation), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['--db', str(self.db), 'db-prune-plan', '--plan', str(self.plan), '--server-stopped'])
        self.assertEqual(code, 0, err.getvalue())
        path = Path(json.loads(out.getvalue())['progress_log'])
        data = self.latest(path)
        self.assertEqual(data['processed'], 1001)
        self.assertEqual(data['progress_percent'], 100)
        self.assertEqual(data['status'], 'ready')
        self.assertTrue(all(key in data for key in ('started_at', 'current_time', 'estimated_finish_at', 'elapsed_seconds')))

    def test_unsafe_paths_and_unrelated_files_are_not_overwritten(self):
        for path in [self.plan, self.db / 'log', self.root / 'plan.sqlite-wal']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.monitor(log_path=path)
        unrelated = self.root / 'user.log'
        unrelated.write_text('keep this')
        with self.assertRaises(ValueError):
            with self.monitor(log_path=unrelated): pass
        self.assertEqual(unrelated.read_text(), 'keep this')
        # A rotated backup must never alias the SQLite plan, even before creation.
        with self.assertRaises(ValueError):
            PruneProgress(self.db, self.root / 'custom.1', 'plan', log_path=self.root / 'custom')

    def test_same_db_reuses_log_across_plan_names_and_concurrent_writer_is_rejected(self):
        other = PruneProgress(self.db, self.root / 'other.sqlite', 'db-prune-plan')
        self.assertEqual(self.monitor().path, other.path)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.monitor(interval=3600):
                with self.assertRaisesRegex(ValueError, '다른 작업'):
                    with other: pass

    def test_interrupt_and_log_write_failure_are_reported(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            with self.monitor(files=1) as monitor:
                raise KeyboardInterrupt
        self.assertEqual(self.latest(monitor.path)['status'], 'interrupted')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(OSError, '필수 진행 로그'):
            with self.monitor(interval=.01) as monitor:
                with patch.object(monitor, 'write', side_effect=OSError('disk full')):
                    threading.Event().wait(.05)
                    monitor('plan', 1, 'path')


if __name__ == '__main__':
    unittest.main()
