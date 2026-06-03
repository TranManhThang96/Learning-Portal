from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from .llm_client import FakeLLMClient
from .memory import MemoryStore
from .prompt import PROMPT_VERSION, build_prompt
from .schemas import AssistantAction, ChatRequest, ChatResponse, ToolCallLog, ToolContext
from .tools import ToolExecutor

logger = logging.getLogger("assistant_app")


class ConversationService:
    def __init__(
        self,
        memory: MemoryStore | None = None,
        tools: ToolExecutor | None = None,
        llm: FakeLLMClient | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.tools = tools or ToolExecutor()
        self.llm = llm or FakeLLMClient()

    def chat(self, request: ChatRequest) -> ChatResponse:
        started = perf_counter()
        trace_id = f"tr_{uuid4().hex[:12]}"
        tool_calls: list[ToolCallLog] = []

        self.memory.append_message(request.user_id, request.session_id, "user", request.message)
        action = self._plan_action(request, trace_id)
        memory_updates = self.memory.apply_updates(request.user_id, action.memory_updates)

        if action.action in {"answer", "ask_clarification"}:
            answer = action.final_answer or "Mình cần thêm thông tin để xử lý yêu cầu."
        else:
            context = ToolContext(
                user_id=request.user_id,
                session_id=request.session_id,
                trace_id=trace_id,
                idempotency_key=request.idempotency_key,
            )
            assert action.tool is not None
            tool_result = self.tools.run(action.tool.name, action.tool.args, context)
            status = "ok" if tool_result.get("status") == "ok" else "error"
            tool_calls.append(
                ToolCallLog(
                    name=action.tool.name,
                    status=status,
                    error=None if status == "ok" else str(tool_result.get("error")),
                )
            )
            answer = self._final_answer(request, trace_id, tool_result)

        self.memory.append_message(request.user_id, request.session_id, "assistant", answer)
        logger.info(
            "chat_completed",
            extra={
                "trace_id": trace_id,
                "prompt_version": PROMPT_VERSION,
                "action": action.action,
                "tool_calls": [call.model_dump() for call in tool_calls],
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return ChatResponse(
            trace_id=trace_id,
            answer=answer,
            tool_calls=tool_calls,
            memory_updates=memory_updates,
        )

    def _plan_action(self, request: ChatRequest, trace_id: str) -> AssistantAction:
        prompt = build_prompt(
            message=request.message,
            memory=self.memory.profile(request.user_id),
            recent_messages=self.memory.recent_messages(request.user_id, request.session_id),
        )
        return self._complete_action_with_retry(prompt, trace_id)

    def _final_answer(self, request: ChatRequest, trace_id: str, tool_result: dict) -> str:
        prompt = build_prompt(
            message=request.message,
            memory=self.memory.profile(request.user_id),
            recent_messages=self.memory.recent_messages(request.user_id, request.session_id),
            tool_result=tool_result,
        )
        return self._complete_action_with_retry(prompt, trace_id).final_answer or "Đã xử lý yêu cầu."

    def _complete_action_with_retry(
        self,
        prompt: str,
        trace_id: str,
        max_retries: int = 2,
    ) -> AssistantAction:
        last_error = ""
        retry_count = 0
        current_prompt = prompt
        for attempt in range(max_retries + 1):
            raw = self.llm.complete(current_prompt)
            try:
                action = AssistantAction.model_validate_json(raw)
                if retry_count:
                    logger.info("schema_retry_succeeded", extra={"trace_id": trace_id, "retry_count": retry_count})
                return action
            except Exception as exc:
                last_error = str(exc)
                retry_count = attempt + 1
                current_prompt = (
                    f"{prompt}\n\nPrevious output was invalid: {last_error}. "
                    "Return only valid JSON matching the schema. No markdown."
                )
        logger.warning("schema_retry_failed", extra={"trace_id": trace_id, "retry_count": retry_count})
        raise ValueError(f"invalid_llm_output: {last_error}")
