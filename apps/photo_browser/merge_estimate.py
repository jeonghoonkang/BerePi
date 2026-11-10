"""Estimate remaining file work from up to 100 recent completed operations."""
import time
from collections import deque
from datetime import datetime, timedelta, timezone

ETA_FIELDS = ('eta_ready', 'eta_sample_files', 'eta_sample_target', 'eta_sample_seconds',
              'eta_sample_kind', 'merge_processing_elapsed_seconds',
              'estimated_remaining_seconds', 'estimated_finish_at')


class MergeEstimate:
    def __init__(self, total, fast_total=0, clock=None, wall_clock=None):
        self.clock = clock or time.monotonic
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.total = total
        self.slow_total = max(0, total - fast_total)
        self.slow, self.fast = deque(maxlen=100), deque(maxlen=100)
        self.slow_done = self.fast_done = 0
        self.last_fast = False
        self.started = self.last = self.clock()

    def completed(self, fast=False):
        current = self.clock()
        (self.fast if fast else self.slow).append(max(0, current - self.last))
        if fast:
            self.fast_done += 1
        else:
            self.slow_done += 1
            self.slow_total = max(self.slow_total, self.slow_done)
        self.last = current
        self.last_fast = fast

    def checkpoint_finished(self):
        current = self.clock()
        samples = self.fast if self.last_fast else self.slow
        if samples:
            samples[-1] += max(0, current - self.last)
        self.last = current

    def snapshot(self):
        current = self.clock()
        remaining = max(0, self.total - self.slow_done - self.fast_done)
        samples = self.slow if self.slow_total else self.fast
        target = min(100, self.slow_total or self.total)
        ready = len(samples) >= target
        seconds = finish = None
        if ready:
            slow_rate = sum(self.slow) / len(self.slow) if self.slow else 0
            fast_rate = sum(self.fast) / len(self.fast) if self.fast else slow_rate
            slow_left = min(remaining, max(0, self.slow_total - self.slow_done))
            estimate = slow_left * slow_rate + (remaining - slow_left) * fast_rate
            seconds = max(1, estimate - max(0, current - self.last)) if remaining else 0
            finish = (self.wall_clock() + timedelta(seconds=seconds)).isoformat()
        return {'eta_ready': ready, 'eta_sample_files': len(samples), 'eta_sample_target': target,
                'eta_sample_seconds': round(sum(samples), 2),
                'eta_sample_kind': 'copy_verify' if self.slow_total else 'fast_skip',
                'merge_processing_elapsed_seconds': round(max(0, current - self.started), 2),
                'estimated_remaining_seconds': round(seconds, 2) if seconds is not None else None,
                'estimated_finish_at': finish}
