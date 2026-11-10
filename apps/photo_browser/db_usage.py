"""Cached background accounting of logical bytes in the entire DB tree."""
import os
import stat
import threading
import time
from datetime import datetime, timezone


class DirectoryUsage:
    def __init__(self, root, ttl=30):
        self.root = root
        self.ttl = ttl
        self.lock = threading.Lock()
        self.worker = None
        self.checked = None
        self.value = {'state': 'pending', 'size_bytes': None, 'file_count': None,
                      'skipped': 0, 'errors': [], 'checked_at': None}

    def snapshot(self, force=False):
        with self.lock:
            running = self.worker is not None and self.worker.is_alive()
            if not running and (force or self.checked is None or time.monotonic() - self.checked >= self.ttl):
                self.worker = threading.Thread(target=self.measure, daemon=True, name='photo-db-usage')
                self.worker.start()
                running = True
            return {**self.value, 'running': running, 'refresh_seconds': self.ttl}

    def measure(self):
        size = count = skipped = 0
        errors = []
        folders = [self.root]
        root_failed = False
        while folders:
            folder = folders.pop()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        try:
                            info = entry.stat(follow_symlinks=False)
                            # Do not follow symlinks or Windows junctions into
                            # another storage tree, or count their target bytes.
                            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                                skipped += 1
                            elif stat.S_ISDIR(info.st_mode):
                                folders.append(entry.path)
                            elif stat.S_ISREG(info.st_mode):
                                size += info.st_size
                                count += 1
                            else:
                                skipped += 1
                        except OSError as exc:
                            skipped += 1
                            if len(errors) < 3:
                                errors.append(str(exc))
            except OSError as exc:
                skipped += 1
                if folder == self.root:
                    root_failed = True
                if len(errors) < 3:
                    errors.append(str(exc))
        with self.lock:
            self.checked = time.monotonic()
            if root_failed:
                # Retain a previous measurement instead of reporting a false 0.
                self.value = {**self.value, 'state': 'error', 'errors': errors, 'skipped': skipped}
            else:
                self.value = {'state': 'partial' if skipped else 'ready', 'size_bytes': size,
                              'file_count': count, 'skipped': skipped, 'errors': errors,
                              'checked_at': datetime.now(timezone.utc).isoformat()}
