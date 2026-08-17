from __future__ import annotations

import unittest

from error_handling.gpu_failover import (
    GPUFailoverExhaustedError,
    execute_with_gpu_failover,
)


class FakeHTTPError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


class GPUFailoverTests(unittest.TestCase):
    def test_resends_same_work_to_another_gpu_after_failure(self) -> None:
        payload = object()
        calls: list[tuple[str, object]] = []
        transitions: list[tuple[str, str]] = []

        def operation(target_id: str) -> str:
            calls.append((target_id, payload))
            if target_id == "gpu-a":
                raise RuntimeError("GPU worker stopped")
            return "received"

        result = execute_with_gpu_failover(
            ["gpu-a", "gpu-b", "gpu-c"],
            operation,
            initial_target_id="gpu-a",
            on_failover=lambda attempt, next_id: transitions.append(
                (attempt.target_id, next_id)
            ),
        )

        self.assertEqual(result, "received")
        self.assertEqual([target_id for target_id, _payload in calls], ["gpu-a", "gpu-b"])
        self.assertIs(calls[0][1], calls[1][1])
        self.assertEqual(transitions, [("gpu-a", "gpu-b")])

    def test_does_not_retry_nonrecoverable_client_error(self) -> None:
        calls: list[str] = []

        def operation(target_id: str) -> str:
            calls.append(target_id)
            raise FakeHTTPError(401)

        with self.assertRaises(FakeHTTPError):
            execute_with_gpu_failover(["gpu-a", "gpu-b"], operation)

        self.assertEqual(calls, ["gpu-a"])

    def test_reports_all_attempts_when_every_gpu_fails(self) -> None:
        with self.assertRaises(GPUFailoverExhaustedError) as context:
            execute_with_gpu_failover(
                ["gpu-a", "gpu-b"],
                lambda target_id: (_ for _ in ()).throw(RuntimeError(target_id)),
            )

        self.assertEqual(
            [attempt.target_id for attempt in context.exception.attempts],
            ["gpu-a", "gpu-b"],
        )


if __name__ == "__main__":
    unittest.main()
