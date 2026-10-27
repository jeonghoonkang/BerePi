import threading
import unittest
from unittest.mock import Mock

from model_health import ModelHealthMonitor


class ModelHealthTests(unittest.TestCase):
    def test_exact_response_and_failure_isolation(self):
        request = Mock(side_effect=[
            {"models": [{"name": n} for n in ["a", "b", "c", "d", "e", "a"]]},
            {"response": " ok\n", "done": True},
            {"response": "OK", "done": True},
            TimeoutError("timeout"),
            {"response": "ok", "done": False},
            {"response": "ok extra", "done": True},
        ])
        monitor = ModelHealthMonitor(request)
        monitor.check_once()
        state = monitor.snapshot()
        self.assertEqual((state["working_count"], state["active_count"]), (1, 5))
        self.assertEqual(state["status"], "complete")
        self.assertGreater(state["next_check_at"], state["checked_at"])
        for call in request.call_args_list[1:]:
            self.assertEqual(call.kwargs["payload"]["prompt"], "다른 문자 없이 ok만 회신")
            self.assertEqual(call.kwargs["timeout"], 60)
        state["results"].clear()
        self.assertEqual(len(monitor.snapshot()["results"]), 5)

    def test_empty_and_unavailable_are_distinct(self):
        request = Mock(side_effect=[{"models": []}, RuntimeError("offline"), {}])
        monitor = ModelHealthMonitor(request)
        monitor.check_once()
        self.assertEqual(monitor.snapshot()["status"], "complete")
        self.assertEqual(monitor.snapshot()["active_count"], 0)
        monitor.check_once()
        self.assertEqual(monitor.snapshot()["status"], "error")
        self.assertEqual(monitor.snapshot()["error"], "offline")
        monitor.check_once()
        self.assertEqual(monitor.snapshot()["status"], "error")

    def test_active_population_replaced_each_cycle(self):
        request = Mock(side_effect=[{"models": [{"name": "old"}]},
                                   {"response": "ok", "done": True}, {"models": []}])
        monitor = ModelHealthMonitor(request)
        monitor.check_once()
        monitor.check_once()
        self.assertEqual(monitor.snapshot()["results"], [])
        self.assertEqual(monitor.snapshot()["working_count"], 0)

    def test_background_repeats_and_never_overlaps(self):
        entered = threading.Event()
        release = threading.Event()
        repeated = threading.Event()
        calls = []

        def request(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                entered.set()
                release.wait(2)
            else:
                repeated.set()
            return {"models": []}

        monitor = ModelHealthMonitor(request, interval=0.02)
        try:
            monitor.start()
            self.assertTrue(entered.wait(2))
            monitor.start()
            monitor.check_once()
            self.assertEqual(len(calls), 1)
            release.set()
            self.assertTrue(repeated.wait(2))
        finally:
            release.set()
            monitor.stop()
        self.assertFalse(monitor._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
