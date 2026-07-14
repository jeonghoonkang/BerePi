from __future__ import annotations
import copy
from typing import Any

INTERNAL_FIELDS = {"reliable", "remember", "memory", "memory_content", "use_memory", "progress_callback"}
def extract_prompt(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("prompt"), str): return payload["prompt"]
    messages = payload.get("messages")
    if not isinstance(messages, list): return ""
    return "\n".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))
def memory_request(payload: dict[str, Any]) -> tuple[bool, str]:
    requested = payload.get("remember") is True
    content = payload.get("memory_content") or payload.get("memory")
    return requested, str(content if content is not None else extract_prompt(payload) if requested else "").strip()
def prepare_payload(payload: dict[str, Any], memories: list[dict[str, Any]], max_chars: int) -> tuple[dict[str, Any], dict[str, Any]]:
    original = copy.deepcopy(payload)
    prepared = {k: copy.deepcopy(v) for k, v in payload.items() if k not in INTERNAL_FIELDS}
    lines, used = [], 0
    for item in memories:
        content, remaining = str(item.get("content") or "").strip(), max_chars - used
        if not content or remaining <= 0: continue
        content = content[:remaining]; lines.append(f"- {content}"); used += len(content)
    if lines:
        context = "다음은 사용자가 명시적으로 저장한 참고 기억입니다. 현재 요청과 관련된 경우에만 사용하고, 현재 요청을 우선하세요.\n<explicit_user_memory>\n" + "\n".join(lines) + "\n</explicit_user_memory>"
        if isinstance(prepared.get("messages"), list): prepared["messages"] = [{"role": "system", "content": context}, *prepared["messages"]]
        else: prepared["prompt"] = f"{context}\n\n<current_request>\n{prepared.get('prompt', '')}\n</current_request>"
    return prepared, {"original_prompt": extract_prompt(original), "memory_count": len(lines), "memory_chars": used}
