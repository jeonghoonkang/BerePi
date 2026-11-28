import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prune_memory import AdaptiveMemory, MIB, MemoryBudgetError, cgroup_limits, object_bytes, system_memory


class AdaptiveMemoryTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.state = dict(total_bytes=8 * 1024 * MIB, effective_limit_bytes=8 * 1024 * MIB,
                          available_bytes=4 * 1024 * MIB, rss_bytes=100 * MIB,
                          pressure_some_avg10=0, pressure_full_avg10=0)

    def manager(self, ceiling=None):
        return AdaptiveMemory(ceiling, provider=lambda: dict(self.state), clock=lambda: self.now)

    def test_user_ceiling_clamped_and_never_preallocated(self):
        manager = self.manager(100000)
        state = manager.snapshot()
        self.assertLess(state['cache_budget_bytes'], 1024 * MIB)
        self.assertEqual(state['cache_used_bytes'], 0)
        self.assertEqual(self.manager(2).snapshot()['cache_budget_bytes'], 2 * MIB)
        with self.assertRaises(ValueError): self.manager(0)

    def test_shared_lru_counts_bytes_and_false_results(self):
        manager = self.manager(2)
        manager.put(('physical', 'false'), False)
        self.assertIs(manager.get(('physical', 'false')), False)
        for i in range(8): manager.put(('item', i), str(i) * (250 * 1024))
        state = manager.snapshot()
        self.assertLessEqual(state['cache_used_bytes'] + state['sqlite_cache_limit_bytes'], state['cache_budget_bytes'])
        self.assertGreater(state['cache_evictions'], 0)
        self.assertIsNone(manager.get(('item', 0)))
        self.assertIsNotNone(manager.get(('item', 7)))
        manager.put(('chunk', 'too-big'), 'x' * (4 * MIB))
        self.assertIsNone(manager.get(('chunk', 'too-big')))

    def test_pressure_shrinks_immediately_and_growth_waits_for_cooldown(self):
        manager = self.manager()
        budget = manager.snapshot()['cache_budget_bytes']
        manager.put(('item', 'large'), 'x' * (budget // 2))
        self.state['pressure_full_avg10'] = 2
        self.now = 2
        shrunk = manager.snapshot()
        self.assertEqual(shrunk['cache_budget_bytes'], budget // 2)
        self.assertEqual(shrunk['adjustment'], 'pressure_shrink')
        self.assertEqual(shrunk['cache_used_bytes'], 0)
        self.state['pressure_full_avg10'] = 0
        self.now = 20
        self.assertEqual(manager.snapshot()['cache_budget_bytes'], budget // 2)
        self.now = 32
        self.assertEqual(manager.snapshot()['cache_budget_bytes'], budget // 2 + 32 * MIB)

    def test_hysteresis_ignores_small_headroom_fluctuations(self):
        manager = self.manager()
        budget = manager.snapshot()['cache_budget_bytes']
        self.state['available_bytes'] -= 100 * MIB
        self.now = 2
        self.assertEqual(manager.snapshot()['cache_budget_bytes'], budget)

    def test_low_memory_evicts_and_stops_and_large_json_is_not_admitted(self):
        manager = self.manager()
        manager.put(('item', 1), 'data')
        self.state['available_bytes'] = 4 * MIB
        self.now = 2
        with self.assertRaises(MemoryBudgetError): manager.check()
        self.assertEqual(manager.snapshot()['cache_entries'], 0)
        self.state['available_bytes'] = 40 * MIB
        self.now = 4
        with self.assertRaises(MemoryBudgetError): manager.require_json(2 * MIB)

    def test_unknown_metrics_do_not_grow_and_count_shared_references_once(self):
        self.state = {}
        manager = self.manager()
        initial = manager.snapshot()['cache_budget_bytes']
        self.now = 60
        self.assertEqual(manager.snapshot()['cache_budget_bytes'], initial)
        self.assertLessEqual(initial, 32 * MIB)
        value = ['shared' * 1000]
        self.assertLess(object_bytes([value, value]), object_bytes(value) * 2)

    def test_cgroup_parents_high_limit_mount_root_and_v1(self):
        files = {
            '/proc/self/cgroup': '0::/tenant/job\n',
            '/proc/self/mountinfo': '42 25 0:30 /tenant /cg rw - cgroup2 cgroup rw\n',
            '/cg/job/memory.max': 'max', '/cg/job/memory.current': '100', '/cg/job/memory.high': 'max',
            '/cg/memory.max': '1000', '/cg/memory.current': '800', '/cg/memory.high': '900',
        }
        def reader(path):
            if str(path) not in files: raise FileNotFoundError(path)
            return files[str(path)]
        self.assertEqual(cgroup_limits(reader=reader), [(1000, 200), (900, 100)])
        files['/proc/self/cgroup'] = '0::/\n'
        self.assertEqual(cgroup_limits(reader=reader), [(1000, 200), (900, 100)])
        files.update({'/proc/self/cgroup': '5:memory:/worker\n',
                      '/proc/self/mountinfo': '42 25 0:30 / /cg rw - cgroup cgroup rw,memory\n',
                      '/cg/worker/memory.limit_in_bytes': '2000', '/cg/worker/memory.usage_in_bytes': '500'})
        self.assertEqual(cgroup_limits(reader=reader), [(2000, 1500)])

    def test_linux_combines_host_and_cgroup_and_address_space_limits(self):
        files = {'/proc/meminfo': 'MemTotal: 10000 kB\nMemAvailable: 5000 kB\n',
                 '/proc/self/status': 'VmRSS: 100 kB\nVmSize: 1000 kB\n',
                 '/proc/pressure/memory': 'some avg10=2.0 avg60=1 avg300=0 total=3\nfull avg10=0.5 avg60=0 avg300=0 total=1\n'}
        with patch('prune_memory.sys.platform', 'linux'), patch('prune_memory._read', side_effect=lambda path: files[str(path)]), \
             patch('prune_memory.cgroup_limits', return_value=[(4000 * 1024, 2000 * 1024)]), \
             patch('resource.getrlimit', return_value=(2500 * 1024, 2500 * 1024)):
            sample = system_memory()
        self.assertEqual(sample['available_bytes'], 1500 * 1024)
        self.assertEqual(sample['effective_limit_bytes'], 2500 * 1024)
        self.assertEqual(sample['rss_bytes'], 100 * 1024)
        self.assertEqual(sample['pressure_full_avg10'], .5)


if __name__ == '__main__': unittest.main()
