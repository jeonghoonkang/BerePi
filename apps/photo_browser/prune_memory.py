"""Dependency-free memory sampling and a shared, byte-budgeted adaptive LRU.

Budgets cover retained caches, not Python's allocator or a single JSON parse.
Unknown OS metrics use a small fixed budget, never an optimistic RAM estimate.
"""
from collections import OrderedDict
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

MIB = 1024 * 1024
SQLITE_CACHE_BYTES = MIB  # Two connections, 512 KiB page cache each.


class MemoryBudgetError(RuntimeError):
    """Stop safely at a checkpoint instead of relying on the OOM killer."""


def _read(path):
    return Path(path).read_text(encoding='utf-8')


def cgroup_limits(proc=Path('/proc'), reader=_read):
    """Return headrooms/limits for all visible cgroup-v2 ancestors and v1 memory."""
    result = []
    try:
        groups = [line.split(':', 2) for line in reader(proc / 'self/cgroup').splitlines()]
        mounts = reader(proc / 'self/mountinfo').splitlines()
        for line in mounts:
            left, right = line.split(' - ', 1)
            fields, fs = left.split(), right.split()
            version = fs[0]
            if version not in {'cgroup2', 'cgroup'}: continue
            if version == 'cgroup' and 'memory' not in fs[2].split(','): continue
            group = next((path for _, controllers, path in groups
                          if (version == 'cgroup2' and controllers == '') or
                          (version == 'cgroup' and 'memory' in controllers.split(','))), None)
            if group is None: continue
            unescape = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
            root, mount = Path(unescape(fields[3])), Path(unescape(fields[4]))
            # A cgroup namespace may expose '/' even when the mount root is deeper.
            try: relative = Path(group).relative_to(root)
            except ValueError:
                if group != '/': continue
                relative = Path('.')
            folder = mount / relative
            while True:
                try:
                    maximum = reader(folder / ('memory.max' if version == 'cgroup2' else 'memory.limit_in_bytes')).strip()
                    current = int(reader(folder / ('memory.current' if version == 'cgroup2' else 'memory.usage_in_bytes')))
                    if maximum != 'max' and 0 < int(maximum) < 1 << 60:
                        result.append((int(maximum), max(0, int(maximum) - current)))
                    if version == 'cgroup2':
                        high = reader(folder / 'memory.high').strip()
                        if high != 'max' and 0 < int(high) < 1 << 60:
                            result.append((int(high), max(0, int(high) - current)))
                except (OSError, ValueError): pass
                if folder == mount: break
                folder = folder.parent
    except (OSError, ValueError, IndexError): pass
    return result


def system_memory():
    sample = dict(total_bytes=None, available_bytes=None, rss_bytes=None,
                  effective_limit_bytes=None, pressure_some_avg10=None, pressure_full_avg10=None,
                  metrics_source='unavailable')
    try:
        if sys.platform.startswith('linux'):
            values = {key: int(value.split()[0]) * 1024 for key, value in
                      (line.split(':', 1) for line in _read('/proc/meminfo').splitlines())}
            sample.update(total_bytes=values['MemTotal'], available_bytes=values.get('MemAvailable'), metrics_source='linux-proc')
            status = {key: value for key, value in (line.split(':', 1) for line in _read('/proc/self/status').splitlines())}
            sample['rss_bytes'] = int(status['VmRSS'].split()[0]) * 1024
            limits = cgroup_limits()
            if limits:
                sample['effective_limit_bytes'] = min(value[0] for value in limits)
                available = sample['available_bytes']
                sample['available_bytes'] = min([value[1] for value in limits] + ([available] if available is not None else []))
            try:
                for line in _read('/proc/pressure/memory').splitlines():
                    parts = line.split()
                    sample['pressure_' + parts[0] + '_avg10'] = float(dict(p.split('=') for p in parts[1:])['avg10'])
            except (OSError, ValueError, KeyError): pass
            # Address-space limits constrain new allocations even when RAM is free.
            try:
                import resource
                soft, _ = resource.getrlimit(resource.RLIMIT_AS)
                if soft > 0:
                    headroom = max(0, soft - int(status['VmSize'].split()[0]) * 1024)
                    sample['available_bytes'] = min(sample['available_bytes'], headroom) if sample['available_bytes'] is not None else headroom
                    sample['effective_limit_bytes'] = min(sample.get('effective_limit_bytes') or soft, soft)
            except (ImportError, OSError, ValueError, KeyError): pass
        elif sys.platform == 'darwin':
            def command(args):
                return subprocess.check_output(args, text=True, timeout=2, stderr=subprocess.DEVNULL)
            sample['total_bytes'] = int(command(['/usr/sbin/sysctl', '-n', 'hw.memsize']))
            vm = command(['/usr/bin/vm_stat'])
            page = int(re.search(r'page size of (\d+) bytes', vm)[1])
            values = {key: int(value.strip().rstrip('.')) for key, value in
                      (line.split(':', 1) for line in vm.splitlines()[1:] if ':' in line)}
            sample['available_bytes'] = page * sum(values.get(key, 0) for key in ('Pages free', 'Pages inactive', 'Pages speculative'))
            sample['rss_bytes'] = int(command(['/bin/ps', '-o', 'rss=', '-p', str(os.getpid())])) * 1024
            sample['metrics_source'] = 'macos-vm-stat'
        elif sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [(name, ctypes.c_ulonglong) for name in
                           ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
            state = MemoryStatus(); state.length = ctypes.sizeof(state)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)): raise OSError('GlobalMemoryStatusEx')
            sample.update(total_bytes=state.total, available_bytes=min(state.available, state.virtual_available), metrics_source='windows-global-memory')
            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
                           ('peak', 'working', 'paged_peak', 'paged', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
            counters = Counters(); counters.cb = ctypes.sizeof(counters)
            kernel = ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            getinfo = ctypes.windll.psapi.GetProcessMemoryInfo
            getinfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if getinfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb): sample['rss_bytes'] = counters.working
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError): pass
    total = sample['total_bytes']
    limit = sample['effective_limit_bytes']
    sample['effective_limit_bytes'] = min(total, limit) if total and limit else total or limit
    return sample


def object_bytes(value):
    """Count retained Python containers/strings, sharing within one entry once."""
    seen, stack, size = set(), [value], 0
    while stack:
        item = stack.pop()
        if id(item) in seen: continue
        seen.add(id(item)); size += sys.getsizeof(item)
        if isinstance(item, dict):
            stack.extend(item.keys()); stack.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            stack.extend(item)
    return size


class AdaptiveMemory:
    def __init__(self, ceiling_mib=None, provider=system_memory, clock=time.monotonic):
        if ceiling_mib is not None and ceiling_mib < 1: raise ValueError('메모리 예산은 1 MiB 이상이어야 합니다.')
        self.provider, self.clock = provider, clock
        self.ceiling = int(ceiling_mib * MIB) if ceiling_mib is not None else 1024 * MIB
        self.lock = threading.RLock()
        self.entries = OrderedDict()
        self.used = self.hits = self.misses = self.evictions = 0
        self.last_sample = self.last_growth = self.last_shrink = float('-inf')
        self.budget = None
        self.reason = 'initializing'
        self.metrics = {}
        self.snapshot()

    def _poll(self):
        now = self.clock()
        if now - self.last_sample < 2: return
        self.last_sample = now
        self.metrics = self.provider()
        available, limit = self.metrics.get('available_bytes'), self.metrics.get('effective_limit_bytes')
        reserve = min(512 * MIB, max(32 * MIB, int((limit or 1024 * MIB) * .05)))
        headroom = max(0, available - reserve) if available is not None else None
        cap = min(self.ceiling, int(limit * .1) if limit else 32 * MIB)
        safe = min(cap, int(headroom * .2)) if headroom is not None else min(cap, 32 * MIB)
        pressure = ((self.metrics.get('pressure_full_avg10') or 0) >= 1 or
                    (self.metrics.get('pressure_some_avg10') or 0) >= 10)
        if self.budget is None:
            self.budget = safe
            self.reason = 'automatic_initial' if available is not None else 'metrics_unavailable_fixed'
            self.last_growth = now
        elif pressure or (available is not None and available < reserve) or safe < self.budget * .8:
            self.budget = min(safe, self.budget // 2)
            self.reason = 'pressure_shrink' if pressure else 'headroom_shrink'
            self.last_shrink = now
            self.last_growth = now
        elif available is not None and now - max(self.last_growth, self.last_shrink) >= 30:
            self.budget = min(safe, self.budget + 32 * MIB)
            self.reason = 'stable_growth'
            self.last_growth = now
        # Unknown metrics must not increase an existing budget.
        self._evict()

    def _evict(self):
        while self.entries and self.used > max(0, self.budget - SQLITE_CACHE_BYTES):
            _, (_, size) = self.entries.popitem(last=False)
            self.used -= size; self.evictions += 1

    def get(self, key):
        with self.lock:
            self._poll()
            entry = self.entries.pop(key, None)
            if entry is None:
                self.misses += 1
                return None
            self.entries[key] = entry
            self.hits += 1
            return entry[0]

    def put(self, key, value):
        with self.lock:
            self._poll()
            previous = self.entries.pop(key, None)
            if previous: self.used -= previous[1]
            size = object_bytes((key, value)) + 256  # OrderedDict/accounting overhead.
            if size <= max(0, self.budget - SQLITE_CACHE_BYTES):
                self.entries[key] = (value, size); self.used += size
            self._evict()

    def require_json(self, size):
        # Conservative admission estimate, not a guarantee of Python heap size.
        with self.lock:
            self._poll()
            available = self.metrics.get('available_bytes')
            if available is not None and size * 8 + 32 * MIB > available:
                self.budget = 0
                self.reason = 'json_admission_shrink'
                self.last_shrink = self.clock()
                self._evict()
                self.last_sample = float('-inf')
                self._poll()
                available = self.metrics.get('available_bytes')
                if available is not None and size * 8 + 32 * MIB > available:
                    raise MemoryBudgetError('JSON 파싱 예상 메모리를 확보할 수 없습니다. 메모리 확보 후 같은 계획으로 다시 실행하세요.')

    def check(self):
        state = self.snapshot()
        if state['critical']:
            raise MemoryBudgetError('가용 메모리가 8 MiB 미만입니다. 안전하게 중단합니다. 메모리 확보 후 같은 계획으로 이어서 실행하세요.')

    def snapshot(self):
        with self.lock:
            self._poll()
            available = self.metrics.get('available_bytes')
            return {**self.metrics, 'cache_budget_bytes': self.budget, 'cache_used_bytes': self.used,
                    'sqlite_cache_limit_bytes': SQLITE_CACHE_BYTES,
                    'cache_entries': len(self.entries), 'cache_hits': self.hits, 'cache_misses': self.misses,
                    'cache_evictions': self.evictions, 'adjustment': self.reason,
                    'user_ceiling_bytes': self.ceiling, 'critical': available is not None and available < 8 * MIB}


def memory_line(state):
    def mib(value): return '?' if value is None else f'{value / MIB:.1f}'
    return (f"RAM RSS {mib(state.get('rss_bytes'))} MiB · 가용 {mib(state.get('available_bytes'))} MiB"
            f" · 캐시 {mib(state.get('cache_used_bytes'))}/{mib(state.get('cache_budget_bytes'))} MiB"
            f" · {state.get('adjustment', 'unknown')}")
