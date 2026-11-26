"""
Miniature reproduction of the AI Advisor tool-calling flow.

Source analyzed:
- agent/pipeline.py
- agent/engine/orchestrator.py
- agent/engine/tool_registry/registry.py
- agent/engine/tool_registry/registry.json

Overall flow:

    User
      |
      v
    Open WebUI Pipeline.pipe()
      |
      |-- inject SYSTEM_PROMPT
      |-- check whether model supports tools
      |-- create Orchestrator(llm_call, fallback_response, tool_creator)
      v
    Orchestrator.handle()
      |
      |-- simple greeting ---------------------> direct LLM answer
      |-- explicit tool creation request ------> creation_pipeline
      |-- model without tool support ----------> fallback context injection
      `-- model with tool support -------------> tool_loop
                                                  |
                                                  |-- registry.get_specs()
                                                  |-- append request_new_tool meta tool
                                                  |-- LLM returns tool_calls
                                                  |-- registry.execute(name, args)
                                                  |-- append role=tool message
                                                  `-- call LLM again for final answer

Run:
    python test.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


MAX_TOOL_CALLS = 8
MAX_TOOL_CREATIONS_PER_QUERY = 2


META_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "request_new_tool",
        "description": (
            "Create and register a new analysis tool when existing tools "
            "cannot answer a data/statistics/aggregation request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Concrete input/output description for the needed tool.",
                },
            },
            "required": ["description"],
        },
    },
}


SIMPLE_PATTERNS = [
    r"^hello\b",
    r"^hi[\s,!.?]",
    r"^thanks?\b",
    r"^안녕",
    r"^하이",
]

TOOL_CREATION_KEYWORDS = [
    "create tool",
    "make a new tool",
    "build a tool",
    "tool 만들어",
    "도구 만들어",
    "도구 생성",
]


def is_simple_query(query: str) -> bool:
    q = query.strip().lower()
    if len(q) > 30:
        return False
    return any(re.match(pattern, q) for pattern in SIMPLE_PATTERNS)


def is_tool_creation_request(query: str) -> bool:
    q = query.lower()
    return any(keyword.lower() in q for keyword in TOOL_CREATION_KEYWORDS)


class ToolRegistry:
    """Small in-memory stand-in for engine.tool_registry.registry."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[dict[str, Any], Callable[..., dict[str, Any]]]] = {}
        self.register(
            name="fetch_normal_stats",
            description="Return normal pressure ranges for a mold.",
            parameters={
                "type": "object",
                "properties": {"mold_model": {"type": "string"}},
                "required": ["mold_model"],
            },
            run=self._fetch_normal_stats,
        )
        self.register(
            name="rag_search",
            description="Search process knowledge documents.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            run=self._rag_search,
        )

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        run: Callable[..., dict[str, Any]],
    ) -> None:
        spec = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        self._tools[name] = (spec, run)

    def get_specs(self) -> list[dict[str, Any]]:
        return [spec for spec, _ in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"error": f"unknown tool: {name}"}
        _, run = self._tools[name]
        try:
            return run(**(args or {}))
        except TypeError as exc:
            return {"error": f"{name} argument error: {exc}"}
        except Exception as exc:
            return {"error": f"{name} execution error: {exc}"}

    @staticmethod
    def _fetch_normal_stats(mold_model: str) -> dict[str, Any]:
        return {
            "data": {
                "mold_model": mold_model,
                "pressure_ranges": {
                    "P1": "21.0~24.5 bar",
                    "P2": "20.5~23.8 bar",
                    "P3": "19.8~22.1 bar",
                },
            }
        }

    @staticmethod
    def _rag_search(query: str) -> dict[str, Any]:
        return {"data": f"Knowledge hit for query: {query}"}


@dataclass
class CreationResult:
    success: bool
    tool_name: str = ""
    spec: dict[str, Any] | None = None
    error: str = ""


def create_tool(description: str, registry: ToolRegistry) -> CreationResult:
    """Stand-in for creation_pipeline.create_tool."""
    tool_name = "calculate_fill_sec_average_tool"

    def run(mold_model: str) -> dict[str, Any]:
        return {"data": {"mold_model": mold_model, "fill_sec_average": "2.43 sec"}}

    registry.register(
        name=tool_name,
        description=description,
        parameters={
            "type": "object",
            "properties": {"mold_model": {"type": "string"}},
            "required": ["mold_model"],
        },
        run=run,
    )
    spec = registry._tools[tool_name][0]
    return CreationResult(success=True, tool_name=tool_name, spec=spec)


class MockLLM:
    """Deterministic model that emits Ollama/OpenAI-style tool_calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls += 1
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        tool_names = {t["function"]["name"] for t in tools}
        called_tools = [m.get("name") for m in messages if m.get("role") == "tool"]

        if not tools:
            return {"message": {"role": "assistant", "content": "Direct answer without tools."}}

        if (
            "request_new_tool" in called_tools
            and "calculate_fill_sec_average_tool" in tool_names
            and "calculate_fill_sec_average_tool" not in called_tools
        ):
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fill_after_create",
                            "function": {
                                "name": "calculate_fill_sec_average_tool",
                                "arguments": {"mold_model": "MCK71758701"},
                            },
                        }
                    ],
                }
            }

        if called_tools:
            return {
                "message": {
                    "role": "assistant",
                    "content": "Final answer composed from the tool result.",
                }
            }

        if "fill_sec" in last_user and "calculate_fill_sec_average_tool" in tool_names:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fill",
                            "function": {
                                "name": "calculate_fill_sec_average_tool",
                                "arguments": {"mold_model": "MCK71758701"},
                            },
                        }
                    ],
                }
            }

        if "fill_sec" in last_user and "request_new_tool" in tool_names:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_create",
                            "function": {
                                "name": "request_new_tool",
                                "arguments": {
                                    "description": (
                                        "Calculate average fill_sec for a given mold_model."
                                    )
                                },
                            },
                        }
                    ],
                }
            }

        return {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_stats",
                        "function": {
                            "name": "fetch_normal_stats",
                            "arguments": {"mold_model": "MCK71758701"},
                        },
                    }
                ],
            }
        }


class Orchestrator:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        llm_call: Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any] | None],
        fallback_response: Callable[[list[dict[str, Any]], str], str],
        tool_creator: Callable[[str], CreationResult] | None = None,
    ) -> None:
        self.registry = registry
        self._llm_call = llm_call
        self._fallback = fallback_response
        self._tool_creator = tool_creator

    def handle(self, user_message: str, messages: list[dict[str, Any]], tool_supported: bool) -> str:
        if is_simple_query(user_message):
            return self._direct_answer(messages)

        if self._tool_creator is not None and is_tool_creation_request(user_message):
            return self._creation_pipeline(user_message)

        if not tool_supported:
            return self._fallback(messages, user_message)

        return self._tool_loop(messages)

    def _direct_answer(self, messages: list[dict[str, Any]]) -> str:
        resp = self._llm_call(messages, [])
        if resp is None:
            return "LLM connection error."
        return resp.get("message", {}).get("content", "")

    def _creation_pipeline(self, user_request: str) -> str:
        if self._tool_creator is None:
            return "No tool creator is configured."
        result = self._tool_creator(user_request)
        if not result.success:
            return f"Tool creation failed: {result.error}"
        return f"Created and registered: {result.tool_name}"

    def _tool_loop(self, messages: list[dict[str, Any]]) -> str:
        tool_call_count = 0
        creation_count = 0
        trace: list[str] = []

        while tool_call_count < MAX_TOOL_CALLS:
            tools = list(self.registry.get_specs())
            if self._tool_creator is not None and creation_count < MAX_TOOL_CREATIONS_PER_QUERY:
                tools.append(META_TOOL_SPEC)

            resp = self._llm_call(messages, tools)
            if resp is None:
                return "LLM connection error."

            assistant_msg = resp.get("message", {})
            tool_calls = assistant_msg.get("tool_calls", [])

            if not tool_calls:
                trace.append(f"assistant_final: {assistant_msg.get('content', '')}")
                return "\n".join(trace)

            messages.append(assistant_msg)

            for tool_call in tool_calls:
                fn = tool_call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)

                if name == "request_new_tool" and self._tool_creator is not None:
                    creation_count += 1
                    creation = self._tool_creator(args.get("description", ""))
                    result = {
                        "data": (
                            f"new tool registered: {creation.tool_name}; "
                            "call it in the next model step"
                        )
                    }
                else:
                    result = self.registry.execute(name, args)

                messages.append(
                    {
                        "role": "tool",
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                        "tool_call_id": tool_call.get("id", ""),
                    }
                )
                trace.append(f"tool_done: {name} -> {result}")

            tool_call_count += 1

        messages.append(
            {
                "role": "user",
                "content": "Summarize the collected tool results.",
            }
        )
        resp = self._llm_call(messages, [])
        return resp.get("message", {}).get("content", "final answer failed")


def fallback_response(messages: list[dict[str, Any]], user_query: str) -> str:
    return f"Fallback path: inject manually fetched context for '{user_query}'."


def run_case(title: str, query: str, tool_supported: bool = True) -> None:
    registry = ToolRegistry()
    llm = MockLLM()
    orch = Orchestrator(
        registry=registry,
        llm_call=llm,
        fallback_response=fallback_response,
        tool_creator=lambda request: create_tool(request, registry),
    )
    messages = [
        {"role": "system", "content": "You are a manufacturing process advisor."},
        {"role": "user", "content": query},
    ]
    print(f"\n== {title} ==")
    print(orch.handle(query, messages, tool_supported))


def main() -> None:
    run_case("direct answer", "hello")
    run_case("normal tool call", "MCK71758701 normal pressure range?")
    run_case("auto-create then final answer", "MCK71758701 fill_sec average?")
    run_case("fallback for model without tools", "MCK71758701 anomaly analysis?", tool_supported=False)
    run_case("explicit creation request", "create tool for average fill_sec by mold_model")


if __name__ == "__main__":
    main()
