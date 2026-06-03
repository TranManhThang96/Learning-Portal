# Day 24: Mini-project - AI Assistant có Tool Calling + Memory

Day 24 đã được tách thành thư mục riêng để dễ học, chạy thử và mở rộng thành mini-project production-style.

## Nội dung

- [Bài học chính](./day-24-ai-assistant-tool-calling-memory/lession.md)
- [Tài liệu thiết kế và kiến trúc](./day-24-ai-assistant-tool-calling-memory/document.md)
- [Bài tập thực hành](./day-24-ai-assistant-tool-calling-memory/exercise.md)
- [README architecture của mini-project](./day-24-ai-assistant-tool-calling-memory/README.md)

## Deliverable

Sau bài này, bạn có một AI assistant API backend có:

- FastAPI endpoint `/chat`.
- Prompt template có version.
- Structured output bằng Pydantic schema.
- Ít nhất 2 tools: `search_kb`, `create_ticket`.
- Memory đơn giản theo `user_id` và `session_id`.
- Logging có `trace_id`.
- Retry khi output của model sai schema.
- Tool executor có allowlist, policy, idempotency và giới hạn số tool calls.
- Tests cho schema, tool policy và security prompts.
