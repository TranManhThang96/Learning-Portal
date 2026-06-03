from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .schemas import CreateTicketArgs, SearchKbArgs, ToolContext


KNOWLEDGE_BASE = [
    {
        "title": "Pro SLA",
        "snippet": "Gói Pro có SLA 99.9% và kênh hỗ trợ ưu tiên.",
        "source": "kb://plans/pro-sla",
    },
    {
        "title": "Refund policy",
        "snippet": "Yêu cầu refund cần được tạo ticket và kiểm tra theo điều khoản thanh toán.",
        "source": "kb://billing/refund-policy",
    },
    {
        "title": "Security support",
        "snippet": "Không gửi password, token hoặc API key qua chat support.",
        "source": "kb://security/support-safe-data",
    },
]


@dataclass
class ToolExecutor:
    tickets_by_idempotency_key: dict[str, dict[str, Any]] = field(default_factory=dict)
    max_tool_calls: int = 3

    def run(self, name: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        if name == "search_kb":
            return self._search_kb(args)
        if name == "create_ticket":
            return self._create_ticket(args, context)
        return {"tool": name, "status": "error", "error": "tool_not_allowed"}

    def _search_kb(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = SearchKbArgs.model_validate(args)
        except ValidationError as exc:
            return {"tool": "search_kb", "status": "error", "error": exc.errors()}

        query_terms = set(parsed.query.lower().split())
        scored = []
        for item in KNOWLEDGE_BASE:
            haystack = f"{item['title']} {item['snippet']}".lower()
            score = sum(1 for term in query_terms if term in haystack)
            if score:
                scored.append((score, item))

        items = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]
        return {"tool": "search_kb", "status": "ok", "items": items[: parsed.top_k]}

    def _create_ticket(self, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        try:
            parsed = CreateTicketArgs.model_validate(args)
        except ValidationError as exc:
            return {"tool": "create_ticket", "status": "error", "error": exc.errors()}

        if not parsed.user_confirmed:
            return {"tool": "create_ticket", "status": "error", "error": "confirmation_required"}
        if not context.idempotency_key:
            return {"tool": "create_ticket", "status": "error", "error": "idempotency_key_required"}

        existing = self.tickets_by_idempotency_key.get(context.idempotency_key)
        if existing:
            return {"tool": "create_ticket", "status": "ok", **existing, "idempotent_replay": True}

        ticket = {
            "ticket_id": f"tick_{uuid4().hex[:10]}",
            "ticket_status": "created",
            "user_id": context.user_id,
            "title": parsed.title,
            "summary": parsed.summary,
            "priority": parsed.priority,
        }
        self.tickets_by_idempotency_key[context.idempotency_key] = ticket
        return {"tool": "create_ticket", "status": "ok", **ticket, "idempotent_replay": False}
