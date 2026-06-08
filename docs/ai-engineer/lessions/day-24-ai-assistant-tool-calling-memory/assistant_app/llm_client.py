from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


class FakeLLMClient:
    """Deterministic local LLM substitute for tests and offline learning."""

    def __init__(self, scripted_outputs: Iterable[str] | None = None) -> None:
        self._scripted_outputs = list(scripted_outputs or [])

    def complete(self, prompt: str) -> str:
        if self._scripted_outputs:
            return self._scripted_outputs.pop(0)

        payload = json.loads(prompt)
        message = payload["current_user_message"].lower()
        tool_result = payload.get("tool_result")
        confirmed_actions = set(payload.get("trusted_context", {}).get("confirmed_actions", []))

        if tool_result is not None:
            return json.dumps(
                {
                    "action": "answer",
                    "final_answer": _answer_from_tool_result(tool_result),
                    "memory_updates": {},
                },
                ensure_ascii=False,
            )

        if "api key" in message or "token" in message or "password" in message:
            return json.dumps(
                {
                    "action": "answer",
                    "final_answer": "Mình không thể ghi nhớ hoặc xử lý secret. Hãy xoá secret khỏi tin nhắn.",
                    "memory_updates": {"preferred_language": "sk-demo-secret"},
                },
                ensure_ascii=False,
            )

        if "tiếng việt" in message or "tieng viet" in message:
            return json.dumps(
                {
                    "action": "answer",
                    "final_answer": "Mình sẽ ưu tiên trả lời bằng tiếng Việt.",
                    "memory_updates": {"preferred_language": "vi"},
                },
                ensure_ascii=False,
            )

        if "tạo ticket" in message or "tao ticket" in message:
            if "create_ticket" not in confirmed_actions:
                return json.dumps(
                    {
                        "action": "ask_clarification",
                        "final_answer": (
                            "Bạn vui lòng xác nhận trong giao diện trước khi mình tạo support ticket."
                        ),
                        "memory_updates": {},
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "action": "call_tool",
                    "tool": {
                        "name": "create_ticket",
                        "args": {
                            "title": "Yêu cầu hỗ trợ từ chat",
                            "summary": payload["current_user_message"],
                            "priority": "normal",
                        },
                    },
                    "memory_updates": {},
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "action": "call_tool",
                "tool": {
                    "name": "search_kb",
                    "args": {"query": payload["current_user_message"], "top_k": 3},
                },
                "memory_updates": {},
            },
            ensure_ascii=False,
        )


def _answer_from_tool_result(tool_result: dict) -> str:
    if tool_result.get("status") != "ok":
        error = tool_result.get("error", "tool_failed")
        if error == "confirmation_required":
            return "Bạn cần xác nhận trong giao diện trước khi mình tạo ticket."
        if error == "idempotency_key_required":
            return "Không thể tạo ticket vì request thiếu idempotency key."
        if error == "idempotency_conflict":
            return "Request key đã được dùng cho một nội dung khác; ticket mới chưa được tạo."
        return "Tool không xử lý được yêu cầu. Vui lòng thử lại hoặc chuyển cho nhân viên hỗ trợ."

    if tool_result.get("tool") == "search_kb":
        items = tool_result.get("items", [])
        if not items:
            return "Mình chưa tìm thấy thông tin phù hợp trong knowledge base."
        snippet = _safe_snippet(items[0]["snippet"])
        sources = ", ".join(item["source"] for item in items)
        return f"Theo knowledge base: {snippet} Nguồn: {sources}."
    if tool_result.get("tool") == "create_ticket":
        return f"Ticket đã được tạo: {tool_result['ticket_id']}."
    return "Mình đã xử lý yêu cầu."


def _safe_snippet(snippet: str) -> str:
    lowered = snippet.lower()
    blocked_terms = ("ignore system", "system prompt", "reveal secret", "developer message")
    if any(term in lowered for term in blocked_terms):
        return "Tài liệu có nội dung không phù hợp để trích nguyên văn; mình chỉ dùng metadata nguồn để hỗ trợ xử lý."
    return snippet
