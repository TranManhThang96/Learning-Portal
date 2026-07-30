from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from threading import RLock
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
    tickets_by_idempotency_key: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

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
            return {
                "tool": "search_kb",
                "status": "error",
                "error": _safe_validation_errors(exc),
            }

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
            return {
                "tool": "create_ticket",
                "status": "error",
                "error": _safe_validation_errors(exc),
            }

        if "create_ticket" not in context.confirmed_actions:
            return {"tool": "create_ticket", "status": "error", "error": "confirmation_required"}
        if not context.idempotency_key:
            return {"tool": "create_ticket", "status": "error", "error": "idempotency_key_required"}

        key = (context.user_id, context.idempotency_key)
        fingerprint = sha256(
            json.dumps(parsed.model_dump(), sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        with self._lock:
            existing = self.tickets_by_idempotency_key.get(key)
            if existing:
                if existing["_request_fingerprint"] != fingerprint:
                    return {
                        "tool": "create_ticket",
                        "status": "error",
                        "error": "idempotency_conflict",
                    }
                return {
                    "tool": "create_ticket",
                    "status": "ok",
                    **_public_ticket(existing),
                    "idempotent_replay": True,
                }

            ticket = {
                "ticket_id": f"tick_{uuid4().hex[:10]}",
                "ticket_status": "created",
                "user_id": context.user_id,
                "title": parsed.title,
                "summary": parsed.summary,
                "priority": parsed.priority,
                "_request_fingerprint": fingerprint,
            }
            self.tickets_by_idempotency_key[key] = ticket
            return {
                "tool": "create_ticket",
                "status": "ok",
                **_public_ticket(ticket),
                "idempotent_replay": False,
            }


def _public_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in ticket.items() if not key.startswith("_")}


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {"loc": list(error["loc"]), "type": error["type"]}
        for error in exc.errors(include_input=False, include_url=False)
    ]
