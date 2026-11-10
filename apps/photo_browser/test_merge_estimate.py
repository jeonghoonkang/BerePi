import unittest
import copy
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from library import Library
from merge_status import merge_status

from merge_estimate import MergeEstimate


class MergeEstimateTests(unittest.TestCase):
    def estimator(self, total, fast_total=0):
        self.clock = 0
        return MergeEstimate(total, fast_total, clock=lambda: self.clock,
                             wall_clock=lambda: datetime(2026, 11, 10, tzinfo=timezone.utc))

    def complete(self, estimate, seconds, count, fast=False):
        for _ in range(count):
            self.clock += seconds
            estimate.completed(fast)

    def test_first_100_files_enable_estimate(self):
        estimate = self.estimator(1000)
        self.complete(estimate, 2, 99)
        self.assertFalse(estimate.snapshot()['eta_ready'])
        self.assertIsNone(estimate.snapshot()['estimated_finish_at'])
        self.complete(estimate, 2, 1)
        data = estimate.snapshot()
        self.assertTrue(data['eta_ready'])
        self.assertEqual(data['eta_sample_files'], 100)
        self.assertEqual(data['eta_sample_seconds'], 200)
        self.assertEqual(data['estimated_remaining_seconds'], 1800)
        self.assertEqual(data['estimated_finish_at'], '2026-11-10T00:30:00+00:00')

    def test_fast_skips_do_not_shorten_copy_estimate(self):
        estimate = self.estimator(1500, fast_total=1000)
        self.complete(estimate, .001, 1000, fast=True)
        self.assertFalse(estimate.snapshot()['eta_ready'])
        self.complete(estimate, 5, 100)
        self.assertEqual(estimate.snapshot()['estimated_remaining_seconds'], 2000)
        self.assertEqual(estimate.snapshot()['eta_sample_seconds'], 500)

    def test_recent_window_tracks_speed_changes_and_checkpoint_overhead(self):
        estimate = self.estimator(1000)
        self.complete(estimate, 10, 100)
        self.complete(estimate, 1, 100)
        self.clock += 10
        estimate.checkpoint_finished()
        data = estimate.snapshot()
        self.assertEqual(data['eta_sample_files'], 100)
        self.assertEqual(data['eta_sample_seconds'], 110)
        self.assertEqual(data['estimated_remaining_seconds'], 880)

    def test_empty_short_and_all_fast_jobs(self):
        self.assertEqual(self.estimator(0).snapshot()['estimated_remaining_seconds'], 0)
        short = self.estimator(10)
        self.complete(short, 1, 10)
        self.assertEqual(short.snapshot()['estimated_remaining_seconds'], 0)
        fast = self.estimator(1000, fast_total=1000)
        self.complete(fast, .1, 100, fast=True)
        self.assertEqual(fast.snapshot()['eta_sample_kind'], 'fast_skip')
        self.assertEqual(fast.snapshot()['estimated_remaining_seconds'], 90)

    def test_merge_publishes_estimate_after_100_files_and_cli_keeps_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'source'
            source.mkdir()
            Image.new('RGB', (8, 8), 'red').save(source / 'photo.jpg')
            library = Library(root / 'db', root)
            library.save_config({'managed_root': str(root / 'managed'), 'scan_min_free_mb': 32,
                                 'sources': [{'source_id': 'photos', 'protocol': 'file', 'root': str(source),
                                              'category': 'family', 'owner_id': 'alice'}]})
            library.scan('photos')
            original = library.items()[0]
            items = []
            for i in range(105):
                item = copy.deepcopy(original)
                item['media_id'] = f'photo{i:03}'
                items.append(item)
            library.commit(items)
            events = []
            result = library.merge(progress=events.append)
            ready = next(event for event in events if event.get('eta_ready'))
            self.assertEqual(ready['processed'], 100)
            self.assertEqual(ready['eta_sample_files'], 100)
            self.assertGreater(ready['estimated_remaining_seconds'], 0)
            self.assertGreaterEqual(ready['estimated_total_seconds'], ready['merge_elapsed_seconds'])
            self.assertEqual(result['estimated_remaining_seconds'], 0)
            self.assertEqual(merge_status(library.db)['items'][0]['eta_sample_files'], 100)


if __name__ == '__main__':
    unittest.main()
