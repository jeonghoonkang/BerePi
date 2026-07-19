import unittest
from io import BytesIO
from unittest.mock import patch

import server_routing


class DispatchInfoTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
