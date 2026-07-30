from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConfirmedAction = Literal["create_ticket"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=256)
    confirmed_actions: set[ConfirmedAction] = Field(default_factory=set)


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["search_kb", "create_ticket"]
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["answer", "call_tool", "ask_clarification"]
    tool: ToolRequest | None = None
    final_answer: str | None = None
    memory_updates: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_contract(self) -> "AssistantAction":
        if self.action in {"answer", "ask_clarification"}:
            if not self.final_answer:
                raise ValueError("final_answer is required for answer or ask_clarification")
            if self.tool is not None:
                raise ValueError("tool must be absent for answer or ask_clarification")
        if self.action == "call_tool":
            if self.tool is None:
                raise ValueError("tool is required for call_tool")
            if self.final_answer is not None:
                raise ValueError("final_answer must be absent for call_tool")
        return self


class ToolCallLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["ok", "error"]
    error: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    answer: str
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    memory_updates: dict[str, str] = Field(default_factory=dict)


class SearchKbArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=5)


class CreateTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=5, max_length=2000)
    priority: Literal["low", "normal", "high"] = "normal"


class ToolContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    user_id: str
    session_id: str
    trace_id: str
    idempotency_key: str | None = None
    confirmed_actions: frozenset[ConfirmedAction] = Field(default_factory=frozenset)
