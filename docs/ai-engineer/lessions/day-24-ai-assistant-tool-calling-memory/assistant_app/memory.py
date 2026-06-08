from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock


ALLOWED_MEMORY_KEYS = {
    "communication_style",
    "preferred_language",
    "product_area",
    "timezone",
}
SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization:",
    "bearer ",
    "password",
    "private key",
    "secret",
    "sk-",
    "token",
)
INSTRUCTION_MARKERS = (
    "developer message",
    "ignore previous",
    "ignore system",
    "system prompt",
)
EMAIL_PATTERN = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")
CARD_LIKE_PATTERN = re.compile(r"(?:\d[ -]?){13,19}")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
TIMEZONE_PATTERN = re.compile(r"^[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+)+$")
SAFE_TEXT_PATTERN = re.compile(r"^[\w .+\-/]{1,64}$", re.UNICODE)


@dataclass
class MemoryStore:
    session_messages: dict[tuple[str, str], list[dict[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    user_profile: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def recent_messages(self, user_id: str, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        with self._lock:
            return list(self.session_messages[(user_id, session_id)][-limit:])

    def append_message(self, user_id: str, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self.session_messages[(user_id, session_id)].append(
                {
                    "role": role,
                    "content": content,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )

    def profile(self, user_id: str) -> dict[str, str]:
        with self._lock:
            return dict(self.user_profile[user_id])

    def apply_updates(
        self,
        user_id: str,
        updates: dict[str, str],
    ) -> dict[str, str]:
        accepted: dict[str, str] = {}
        with self._lock:
            for key, value in updates.items():
                normalized = value.strip()
                if key not in ALLOWED_MEMORY_KEYS:
                    continue
                if not _is_safe_memory_value(key, normalized):
                    continue
                self.user_profile[user_id][key] = normalized
                accepted[key] = normalized
        return accepted


def _looks_sensitive(value: str) -> bool:
    lower = value.lower()
    if any(marker in lower for marker in SECRET_MARKERS + INSTRUCTION_MARKERS):
        return True
    if EMAIL_PATTERN.search(value) or CARD_LIKE_PATTERN.search(value):
        return True
    return "\n" in value or "\r" in value or len(value) > 64


def _is_safe_memory_value(key: str, value: str) -> bool:
    if not value or _looks_sensitive(value):
        return False
    if key == "preferred_language":
        return LANGUAGE_PATTERN.fullmatch(value) is not None
    if key == "timezone":
        return TIMEZONE_PATTERN.fullmatch(value) is not None
    if key == "communication_style":
        return value in {"concise", "detailed", "formal", "friendly"}
    return SAFE_TEXT_PATTERN.fullmatch(value) is not None
