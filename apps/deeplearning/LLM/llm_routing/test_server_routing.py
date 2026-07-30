import unittest
from io import BytesIO
from unittest.mock import patch

import server_routing


class DispatchInfoTests(unittest.TestCase):
    def setUp(self) -> None:
        server_routing.TARGET_RUNTIME.clear()
        server_routing.TARGET_QUEUES.clear()
        server_routing.TARGET_WORKERS.clear()
        server_routing.TARGET_CURSOR = 0

    def test_prompt_input_has_default_smoke_test_text(self) -> None:
        self.assertIn(
            '<textarea id="test_prompt" placeholder="전송할 prompt">'
            "다른 내용 없이 ok 만 회신</textarea>",
            server_routing.INDEX_HTML,
        )

    def test_sse_event_format(self) -> None:
        encoded = server_routing.sse_event_bytes("dispatch_info", {"value": "한글"})

        self.assertEqual(
            encoded.decode("utf-8"),
            'event: dispatch_info\ndata: {"value":"한글"}\n\n',
        )

    def test_stream_sends_dispatch_info_before_response(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Test LLM",
            host="127.0.0.1",
            port=11434,
            model="test-model",
        )
        handler = server_routing.RoutingHandler.__new__(server_routing.RoutingHandler)
        handler.wfile = BytesIO()

        with (
            patch.object(handler, "start_sse"),
            patch.object(server_routing, "choose_target", return_value=target),
            patch.object(server_routing, "load_targets", return_value=[target]),
            patch.object(
                server_routing,
                "route_prompt",
                return_value={"ok": True, "response": "hello"},
            ) as route,
        ):
            handler.write_prompt_sse({"prompt": "hello"})

        events = handler.wfile.getvalue().decode("utf-8")
        self.assertLess(events.index("event: dispatch_info"), events.index("event: response"))
        self.assertLess(events.index("event: response"), events.index("event: done"))
        route.assert_called_once_with(handler, {"prompt": "hello"}, selected_target=target)

    def test_dispatch_info_contains_selected_target(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Test LLM",
            host="127.0.0.1",
            port=11434,
            model="test-model",
        )

        with patch.object(server_routing, "load_targets", return_value=[target]):
            fields = server_routing.dispatch_info_fields(target)

        self.assertEqual(fields["dispatch_info"]["status"], "selected")
        self.assertEqual(fields["dispatch_info"]["model_number"], 1)
        self.assertEqual(fields["dispatch_info"]["target"]["target_id"], "target-1")
        self.assertEqual(fields["dispatch_info"]["target"]["model"], "test-model")

    def test_dispatch_info_reports_no_selection(self) -> None:
        self.assertEqual(
            server_routing.dispatch_info_fields(None),
            {
                "dispatch_info": {
                    "status": "not_selected",
                    "model_number": None,
                    "target": None,
                }
            },
        )

    def test_openai_response_keeps_dispatch_info(self) -> None:
        dispatch_info = {
            "status": "selected",
            "model_number": 2,
            "target": {"target_id": "target-2"},
        }

        response = server_routing.openai_chat_response(
            {
                "model": "test-model",
                "response": "hello",
                "dispatch_info": dispatch_info,
            }
        )

        self.assertEqual(response["dispatch_info"], dispatch_info)
        self.assertEqual(response["routing"]["dispatch_info"], dispatch_info)

    def test_three_errors_fail_over_to_a_different_model(self) -> None:
        failed = server_routing.LLMTarget(
            id="failed-target",
            name="Failed",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        same_model = server_routing.LLMTarget(
            id="same-model-target",
            name="Same model",
            host="127.0.0.2",
            port=11434,
            model="model-a",
        )
        fallback = server_routing.LLMTarget(
            id="fallback-target",
            name="Fallback",
            host="127.0.0.3",
            port=11434,
            model="model-b",
        )
        metric = server_routing.metric_for(failed.id)
        metric.consecutive_errors = 3
        server_routing.store_metric(failed.id, metric)

        with (
            patch.object(
                server_routing,
                "load_targets",
                return_value=[failed, same_model, fallback],
            ),
            patch.object(server_routing, "ensure_target_queues"),
        ):
            selected = server_routing.choose_target({"prompt": "same data"})
            explicitly_selected = server_routing.choose_target(
                {"prompt": "same data", "target_id": failed.id}
            )

        self.assertEqual(selected.id, fallback.id)
        self.assertEqual(explicitly_selected.id, fallback.id)
        self.assertNotEqual(selected.model, failed.model)

    def test_success_resets_consecutive_error_count(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Target",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        metric = server_routing.metric_for(target.id)
        metric.consecutive_errors = 2
        server_routing.store_metric(target.id, metric)

        with (
            patch.object(
                server_routing,
                "request_json",
                return_value={"response": "ok"},
            ),
            patch.object(server_routing, "record_access"),
            patch.object(server_routing, "update_client_stats"),
            patch.object(server_routing, "dispatch_target_fields", return_value={}),
        ):
            result = server_routing.execute_prompt(
                target,
                {"prompt": "same data", "timeout": 1},
                "test-client",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            server_routing.metric_for(target.id).consecutive_errors,
            0,
        )

    def test_backend_error_increments_consecutive_error_count(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Target",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        with (
            patch.object(
                server_routing,
                "request_json",
                side_effect=TimeoutError("backend timeout"),
            ),
            patch.object(server_routing, "record_access"),
        ):
            for expected in range(1, 4):
                with self.assertRaises(TimeoutError):
                    server_routing.execute_prompt(
                        target,
                        {"prompt": "same data", "timeout": 1},
                        "test-client",
                    )
                self.assertEqual(
                    server_routing.metric_for(target.id).consecutive_errors,
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
