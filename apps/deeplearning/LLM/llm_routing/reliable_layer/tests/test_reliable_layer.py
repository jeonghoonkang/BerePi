from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from reliable_layer.config import ReliableLayerConfig
from reliable_layer.errors import ReliableAttemptsExhausted
from reliable_layer.memory import ExplicitMemoryStore
from reliable_layer.orchestrator import ReliableOrchestrator

class ReliableLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = ExplicitMemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.layer = ReliableOrchestrator(self.store, ReliableLayerConfig(max_attempts=3, base_backoff_seconds=0, max_backoff_seconds=0), sleep=lambda _: None)
    def tearDown(self) -> None: self.temp.cleanup()
    def test_memory_requires_explicit_flag(self) -> None:
        self.layer.generate({"user_id":"u1","prompt":"secret"}, lambda p:{"response":"ok"})
        self.assertEqual([], self.store.list_for_user("u1"))
        self.layer.generate({"user_id":"u1","prompt":"remember","remember":True}, lambda p:{"response":"ok"})
        self.assertEqual("remember", self.store.list_for_user("u1")[0]["content"])
    def test_retry_and_progress(self) -> None:
        calls, events = [], []
        def route(payload):
            calls.append(payload)
            if len(calls) < 3: raise TimeoutError("slow")
            return {"response":"done"}
        result = self.layer.generate({"client_id":"c1","prompt":"hi"}, route, events.append)
        self.assertEqual(3, result.attempts); self.assertEqual(2, len([e for e in events if e.state == "retrying"]))
    def test_non_retryable_stops(self) -> None:
        calls = []
        def route(payload): calls.append(payload); raise ValueError("invalid")
        with self.assertRaises(ReliableAttemptsExhausted): self.layer.generate({"prompt":"hi"}, route)
        self.assertEqual(1, len(calls))
    def test_memory_context_preserves_original(self) -> None:
        self.store.remember("u1", "한국어 선호"); captured = {}
        result = self.layer.generate({"user_id":"u1","prompt":"current"}, lambda p:(captured.update(p) or {"response":"ok"}))
        self.assertIn("한국어 선호", captured["prompt"]); self.assertEqual("current", result.audit["original_prompt"])

if __name__ == "__main__": unittest.main()
