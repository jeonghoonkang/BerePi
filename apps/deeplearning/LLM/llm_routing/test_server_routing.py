import unittest
from io import BytesIO
import urllib.error
from unittest.mock import MagicMock, patch

import server_routing


class DispatchInfoTests(unittest.TestCase):
    def setUp(self) -> None:
        server_routing.TARGET_RUNTIME.clear()
        server_routing.TARGET_QUEUES.clear()
        server_routing.TARGET_WORKERS.clear()
        server_routing.MODEL_DISPATCH_COUNTS.clear()
        server_routing.TARGET_MODEL_LIST_CACHE.clear()
        server_routing.TARGET_CURSOR = 0

    def test_missing_requested_model_uses_an_installed_model(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Target",
            host="127.0.0.1",
            port=11434,
            model="gemma4:31b",
        )
        backend_models: list[str] = []

        def request_json(url, payload=None, *_args, **_kwargs):
            if url.endswith("/api/tags"):
                return {"models": [{"name": "llama3.2-vision:11b"}]}
            backend_models.append(payload["model"])
            return {"response": "ok"}

        with (
            patch.object(server_routing, "request_json", side_effect=request_json),
            patch.object(server_routing, "record_access"),
            patch.object(server_routing, "update_client_stats"),
            patch.object(server_routing, "dispatch_target_fields", return_value={}),
        ):
            result = server_routing.execute_prompt(
                target,
                {"prompt": "same data", "model": "gemma4:31b", "timeout": 1},
                "test-client",
            )

        self.assertEqual(backend_models, ["llama3.2-vision:11b"])
        self.assertEqual(result["model"], "llama3.2-vision:11b")
        self.assertEqual(result["requested_model"], "gemma4:31b")
        self.assertTrue(result["model_fallback_applied"])

    def test_model_fallback_prefers_same_model_family(self) -> None:
        selected = server_routing.choose_supported_model(
            "gemma4:31b",
            "gemma4:31b",
            ["llama3:8b", "gemma4:27b", "qwen3:14b"],
        )

        self.assertEqual(selected, "gemma4:27b")

    def test_api_password_gets_refreshing_status_payload(self) -> None:
        handler = server_routing.RoutingHandler.__new__(server_routing.RoutingHandler)
        handler.path = "/api/status"

        with (
            patch.object(handler, "is_authenticated", return_value=False),
            patch.object(server_routing, "prompt_api_authenticated", return_value=True),
            patch.object(server_routing, "status_payload", return_value={"detail": True}) as detailed,
            patch.object(server_routing, "api_status_payload", return_value={"detail": False}) as public,
            patch.object(handler, "write_json") as write_json,
        ):
            handler.do_GET()

        detailed.assert_called_once_with()
        public.assert_not_called()
        write_json.assert_called_once_with({"detail": True})

    def test_prompt_input_has_default_smoke_test_text(self) -> None:
        self.assertIn(
            '<textarea id="test_prompt" placeholder="전송할 prompt">'
            "다른 내용 없이 ok 만 회신</textarea>",
            server_routing.INDEX_HTML,
        )

    def test_index_html_keeps_javascript_newline_escape(self) -> None:
        self.assertIn(
            "routing_messages || [String(err)]).join('\\n')",
            server_routing.INDEX_HTML,
        )

    def test_gcp_tab_uses_dedicated_endpoint(self) -> None:
        self.assertIn('data-tab="gcp">GCP 테스트</button>', server_routing.INDEX_HTML)
        self.assertIn('id="gcp_test_prompt"', server_routing.INDEX_HTML)
        self.assertIn('id="gcp_base_url"', server_routing.INDEX_HTML)
        self.assertIn("data.base_url || config.base_url", server_routing.INDEX_HTML)
        self.assertIn("api('/api/gcp/generate'", server_routing.INDEX_HTML)
        self.assertIn("자동 LLM 라우팅 대상에는 포함되지 않습니다", server_routing.INDEX_HTML)

    def test_gcp_status_does_not_expose_api_key(self) -> None:
        settings = MagicMock()
        settings.configuration_status.return_value = {
            "configured": True,
            "model_id": "gemma-4-31b-it",
            "api_version": "v1beta",
            "base_url": "https://generativelanguage.googleapis.com",
            "key_source": "environment:GEMINI_API_KEY",
        }
        with patch.object(server_routing, "GoogleAIStudioClient", return_value=settings):
            result = server_routing.gcp_status_payload()

        self.assertTrue(result["ok"])
        self.assertTrue(result["configured"])
        self.assertEqual(result["model_id"], "gemma-4-31b-it")
        self.assertNotIn("api_key", result)

    def test_api_number_selects_exact_gpu_target(self) -> None:
        first = server_routing.LLMTarget(
            id="gpu-1", name="GPU 1", host="127.0.0.1", port=11434, api_number=1
        )
        second = server_routing.LLMTarget(
            id="gpu-2", name="GPU 2", host="127.0.0.2", port=11434, api_number=2
        )
        with (
            patch.object(server_routing, "load_targets", return_value=[first, second]),
            patch.object(server_routing, "ensure_target_queues"),
            patch.object(server_routing, "target_has_known_availability", return_value=True),
            patch.object(server_routing, "target_failover_open", return_value=False),
            patch.object(server_routing, "target_queue", return_value=MagicMock(qsize=lambda: 0)),
        ):
            selected = server_routing.choose_target({"api_number": 2, "prompt": "hello"})

        self.assertEqual(selected.id, "gpu-2")

    def test_gcp_target_id_selects_google_ai_studio(self) -> None:
        settings = MagicMock(
            model_id="gemma-4-31b-it",
            base_url="https://generativelanguage.googleapis.com",
        )
        with patch.object(server_routing, "GoogleAIStudioClient", return_value=settings):
            selected = server_routing.choose_target(
                {"target_id": "google-ai-studio-endpoint", "prompt": "hello"}
            )

        self.assertEqual(selected.id, "google-ai-studio-endpoint")
        self.assertEqual(selected.api_type, "google_ai_studio")
        self.assertEqual(selected.model, "gemma-4-31b-it")

    def test_direct_api_number_disables_cross_gpu_failover(self) -> None:
        target = server_routing.LLMTarget(
            id="gpu-2", name="GPU 2", host="127.0.0.2", port=11434, api_number=2
        )
        handler = MagicMock(headers={}, client_address=("127.0.0.1", 12345))
        with (
            patch.object(server_routing, "choose_target", return_value=target),
            patch.object(server_routing, "prompt_failover_targets") as failover,
            patch.object(
                server_routing,
                "dispatch_prompt_to_target",
                return_value={"ok": True, "llm_dispatch_count": 1},
            ) as dispatch,
        ):
            result = server_routing.route_prompt(
                handler, {"api_number": 2, "prompt": "hello"}
            )

        failover.assert_not_called()
        dispatch.assert_called_once_with(handler, {"api_number": 2, "prompt": "hello"}, target)
        self.assertTrue(result["ok"])

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
        metric.available_targets = 1
        server_routing.store_metric(failed.id, metric)
        for target in (same_model, fallback):
            metric = server_routing.metric_for(target.id)
            metric.available_targets = 1
            server_routing.store_metric(target.id, metric)

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

    def test_backend_unauthorized_is_reported_as_authentication_failure(self) -> None:
        http_error = urllib.error.HTTPError(
            "http://backend/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"error":"bad credentials"}'),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(server_routing.BackendAuthenticationError) as raised:
                server_routing.request_json(
                    "http://backend/v1/chat/completions",
                    {"model": "model-a", "prompt": "hello"},
                )
        http_error.close()

        self.assertEqual(raised.exception.status_code, 401)

    def test_authentication_failure_calls_next_model_once(self) -> None:
        first = server_routing.LLMTarget(
            id="target-1",
            name="First",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        second = server_routing.LLMTarget(
            id="target-2",
            name="Second",
            host="127.0.0.2",
            port=11434,
            model="model-b",
        )
        auth_error = server_routing.PromptDispatchError(
            "Backend request failed: authentication failed",
            1,
            first,
        )
        auth_error.__cause__ = server_routing.BackendAuthenticationError(401)
        handler = MagicMock(headers={}, client_address=("127.0.0.1", 12345))

        with (
            patch.object(server_routing, "load_targets", return_value=[first, second]),
            patch.object(server_routing, "choose_target", return_value=first),
            patch.object(
                server_routing,
                "dispatch_prompt_to_target",
                side_effect=[
                    auth_error,
                    {
                        "ok": True,
                        "model": second.model,
                        "llm_dispatch_count": 1,
                        "failover_from_models": [],
                    },
                ],
            ) as dispatch,
        ):
            result = server_routing.route_prompt(handler, {"prompt": "hello"})

        self.assertEqual([call.args[2].id for call in dispatch.call_args_list], [first.id, second.id])
        self.assertEqual(result["llm_dispatch_count"], 2)
        self.assertTrue(result["failover_applied"])
        self.assertTrue(result["model_failures"][0]["authentication_failed"])
        self.assertIn("암호", result["routing_messages"][0])
        self.assertIn("다음 모델", result["routing_messages"][0])

    def test_all_models_fail_once_and_stop_at_last_model(self) -> None:
        first = server_routing.LLMTarget(
            id="target-1",
            name="First",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        duplicate_model = server_routing.LLMTarget(
            id="target-duplicate",
            name="Duplicate",
            host="127.0.0.2",
            port=11434,
            model="model-a",
        )
        last = server_routing.LLMTarget(
            id="target-2",
            name="Last",
            host="127.0.0.3",
            port=11434,
            model="model-b",
        )
        first_error = server_routing.PromptDispatchError("first failed", 1, first)
        first_error.__cause__ = server_routing.BackendAuthenticationError(401)
        last_error = server_routing.PromptDispatchError("last failed", 1, last)
        handler = MagicMock(headers={}, client_address=("127.0.0.1", 12345))

        with (
            patch.object(
                server_routing,
                "load_targets",
                return_value=[first, duplicate_model, last],
            ),
            patch.object(server_routing, "choose_target", return_value=first),
            patch.object(
                server_routing,
                "dispatch_prompt_to_target",
                side_effect=[first_error, last_error],
            ) as dispatch,
        ):
            with self.assertRaises(server_routing.AllModelsFailedError) as raised:
                server_routing.route_prompt(handler, {"prompt": "hello"})

        error = raised.exception
        self.assertEqual([call.args[2].id for call in dispatch.call_args_list], [first.id, last.id])
        self.assertEqual(error.dispatch_count, 2)
        self.assertEqual(error.target.id, last.id)
        self.assertTrue(error.response_fields["all_models_failed"])
        self.assertTrue(error.response_fields["execution_stopped"])
        self.assertEqual(error.response_fields["last_model"], last.model)
        self.assertIn("반복 호출하지 않고", str(error))
        self.assertIn("실행을 중지", str(error))

    def test_unknown_availability_target_is_skipped(self) -> None:
        unknown = server_routing.LLMTarget(
            id="unknown-target",
            name="Unknown",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        available = server_routing.LLMTarget(
            id="available-target",
            name="Available",
            host="127.0.0.2",
            port=11434,
            model="model-b",
        )
        metric = server_routing.metric_for(available.id)
        metric.available_targets = 1
        server_routing.store_metric(available.id, metric)

        with (
            patch.object(server_routing, "load_targets", return_value=[unknown, available]),
            patch.object(server_routing, "ensure_target_queues"),
            patch.object(
                server_routing,
                "target_health",
                return_value={"ok": True, "data": {}},
            ),
        ):
            selected = server_routing.choose_target({"prompt": "same data"})
            explicit = server_routing.choose_target(
                {"prompt": "same data", "target_id": unknown.id}
            )

        self.assertEqual(selected.id, available.id)
        self.assertEqual(explicit.id, available.id)
        self.assertIsNone(
            server_routing.metric_for(unknown.id).available_targets
        )

    def test_all_unknown_availability_targets_reject_dispatch(self) -> None:
        unknown = server_routing.LLMTarget(
            id="unknown-target",
            name="Unknown",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        with (
            patch.object(server_routing, "load_targets", return_value=[unknown]),
            patch.object(server_routing, "ensure_target_queues"),
            patch.object(
                server_routing,
                "target_health",
                return_value={"ok": True, "data": {}},
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "No LLM targets have known positive availability",
            ):
                server_routing.choose_target({"prompt": "same data"})

    def test_available_targets_is_derived_from_health_models(self) -> None:
        self.assertEqual(
            server_routing.available_targets_from_health(
                {"models": [{"name": "model-a"}, {"name": "model-b"}]}
            ),
            2,
        )
        self.assertEqual(
            server_routing.available_targets_from_health(
                {"available_targets": 0}
            ),
            0,
        )
        self.assertIsNone(
            server_routing.available_targets_from_health({"status": "ok"})
        )

    def test_repeated_model_dispatch_reduces_timeout_to_100_seconds(self) -> None:
        first_target = server_routing.LLMTarget(
            id="target-1",
            name="First",
            host="127.0.0.1",
            port=11434,
            model="shared-model",
        )
        second_target = server_routing.LLMTarget(
            id="target-2",
            name="Second",
            host="127.0.0.2",
            port=11434,
            model="shared-model",
        )
        observed_timeouts = []

        def fake_request(_url, _payload, timeout, headers=None):
            observed_timeouts.append(timeout)
            return {"response": "ok"}

        with (
            patch.object(server_routing, "request_json", side_effect=fake_request),
            patch.object(server_routing, "record_access"),
            patch.object(server_routing, "update_client_stats"),
            patch.object(server_routing, "dispatch_target_fields", return_value={}),
        ):
            first = server_routing.execute_prompt(
                first_target,
                {"prompt": "first", "timeout": 600},
                "test-client",
            )
            second = server_routing.execute_prompt(
                second_target,
                {"prompt": "second", "timeout": 600},
                "test-client",
            )

        self.assertEqual(observed_timeouts, [600, 100])
        self.assertEqual(first["model_dispatch_attempt"], 1)
        self.assertFalse(first["repeated_model_timeout_applied"])
        self.assertEqual(second["model_dispatch_attempt"], 2)
        self.assertTrue(second["repeated_model_timeout_applied"])
        self.assertEqual(second["backend_timeout_seconds"], 100)

    def test_repeated_model_timeout_does_not_raise_shorter_requested_timeout(self) -> None:
        target = server_routing.LLMTarget(
            id="target-1",
            name="Target",
            host="127.0.0.1",
            port=11434,
            model="model-a",
        )
        server_routing.MODEL_DISPATCH_COUNTS["model-a"] = 1

        self.assertEqual(server_routing.repeated_model_timeout(target, 45), 45)
        self.assertEqual(server_routing.repeated_model_timeout(target, 600), 100)

    def test_dedicated_bedrock_route_does_not_use_configured_targets(self) -> None:
        handler = server_routing.RoutingHandler.__new__(server_routing.RoutingHandler)
        settings = MagicMock(region="us-east-1", model_id="amazon.nova-micro-v1:0")
        with (
            patch.object(server_routing, "BedrockClient", return_value=settings),
            patch.object(server_routing, "route_prompt", return_value={"ok": True}) as route,
        ):
            result = server_routing.route_bedrock_prompt(
                handler,
                {"prompt": "hello", "target_id": "local-target"},
            )

        self.assertTrue(result["ok"])
        selected = route.call_args.kwargs["selected_target"]
        forwarded = route.call_args.args[1]
        self.assertEqual(selected.api_type, "bedrock")
        self.assertEqual(selected.model, "amazon.nova-micro-v1:0")
        self.assertNotIn("target_id", forwarded)

    def test_dedicated_gcp_route_does_not_use_configured_targets(self) -> None:
        handler = server_routing.RoutingHandler.__new__(server_routing.RoutingHandler)
        settings = MagicMock(
            model_id="gemma-4-31b-it",
        )
        with (
            patch.object(server_routing, "GoogleAIStudioClient", return_value=settings),
            patch.object(server_routing, "route_prompt", return_value={"ok": True}) as route,
        ):
            result = server_routing.route_gcp_prompt(
                handler,
                {"prompt": "hello", "target_id": "local-target"},
            )

        self.assertTrue(result["ok"])
        selected = route.call_args.kwargs["selected_target"]
        forwarded = route.call_args.args[1]
        self.assertEqual(selected.api_type, "google_ai_studio")
        self.assertEqual(selected.model, "gemma-4-31b-it")
        self.assertNotIn("target_id", forwarded)


if __name__ == "__main__":
    unittest.main()
