from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime


ALLOWED_MEMORY_KEYS = {"preferred_language", "product_area", "role", "timezone"}
SECRET_MARKERS = ("api_key", "apikey", "password", "token", "secret", "sk-")


@dataclass
class MemoryStore:
    session_messages: dict[tuple[str, str], list[dict[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    user_profile: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))

    def recent_messages(self, user_id: str, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        return self.session_messages[(user_id, session_id)][-limit:]

    def append_message(self, user_id: str, session_id: str, role: str, content: str) -> None:
        self.session_messages[(user_id, session_id)].append(
            {
                "role": role,
                "content": content,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def profile(self, user_id: str) -> dict[str, str]:
        return dict(self.user_profile[user_id])

    def apply_updates(
        self,
        user_id: str,
        updates: dict[str, str],
    ) -> dict[str, str]:
        accepted: dict[str, str] = {}
        for key, value in updates.items():
            normalized = value.strip()
            if key not in ALLOWED_MEMORY_KEYS:
                continue
            if _looks_sensitive(normalized):
                continue
            self.user_profile[user_id][key] = normalized
            accepted[key] = normalized
        return accepted


def _looks_sensitive(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in SECRET_MARKERS)
