from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=256)


class ToolRequest(BaseModel):
    name: Literal["search_kb", "create_ticket"]
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantAction(BaseModel):
    action: Literal["answer", "call_tool", "ask_clarification"]
    tool: ToolRequest | None = None
    final_answer: str | None = None
    memory_updates: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_contract(self) -> "AssistantAction":
        if self.action in {"answer", "ask_clarification"} and not self.final_answer:
            raise ValueError("final_answer is required for answer or ask_clarification")
        if self.action == "call_tool" and self.tool is None:
            raise ValueError("tool is required for call_tool")
        return self


class ToolCallLog(BaseModel):
    name: str
    status: Literal["ok", "error"]
    error: str | None = None


class ChatResponse(BaseModel):
    trace_id: str
    answer: str
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    memory_updates: dict[str, str] = Field(default_factory=dict)


class SearchKbArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=5)


class CreateTicketArgs(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=5, max_length=2000)
    priority: Literal["low", "normal", "high"] = "normal"
    user_confirmed: bool = False


class ToolContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str
    session_id: str
    trace_id: str
    idempotency_key: str | None = None
