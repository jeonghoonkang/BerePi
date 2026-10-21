"""Bounded, timestamped directory history independent of long library jobs."""
import json
import os
import shutil
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from library import uid


class DirectoryHistory:
    limit = 1000

    def __init__(self, db):
        self.path = Path(db) / 'history.txt'
        self.lock = threading.Lock()

    def _read(self):
        entries, invalid = deque(maxlen=self.limit), 0
        if self.path.exists():
            with self.path.open(encoding='utf-8') as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if (not isinstance(entry, dict) or not isinstance(entry.get('id'), str)
                                or not isinstance(entry.get('path'), str) or not Path(entry['path']).is_absolute()
                                or not isinstance(entry.get('recursive'), bool)
                                or datetime.fromisoformat(entry['recorded_at']).tzinfo is None):
                            raise ValueError('Invalid history record')
                        entries.append(entry)
                    except (ValueError, KeyError, TypeError):
                        invalid += 1
        return list(entries), invalid

    def entries(self):
        with self.lock:
            entries, invalid = self._read()
            return list(reversed(entries)), invalid

    def add(self, path, recursive=False):
        with self.lock:
            entries, invalid = self._read()
            if invalid:
                shutil.copy2(self.path, self.path.with_name('history.corrupt.' + uid() + '.txt'))
            entry = {'id': uid(), 'recorded_at': datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='microseconds'),
                     'path': str(path), 'recursive': recursive}
            entries.append(entry)
            entries = entries[-self.limit:]
            temporary = self.path.with_name('history.' + uid() + '.tmp')
            try:
                with temporary.open('w', encoding='utf-8') as stream:
                    for item in entries:
                        stream.write(json.dumps(item, ensure_ascii=False) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
            return entry
