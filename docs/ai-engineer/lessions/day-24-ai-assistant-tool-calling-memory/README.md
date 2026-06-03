# Support AI Assistant

Mini-project Day 24: AI assistant API backend có tool calling, memory đơn giản, structured output, logging, retry schema và idempotency.

## Architecture

```text
FastAPI /chat
  -> ConversationService
     -> MemoryStore
     -> PromptBuilder
     -> LLMClient
     -> AssistantAction schema validation
     -> ToolExecutor
     -> final answer generation
     -> structured logging
```

Boundary quan trọng:

- LLM chỉ sinh `AssistantAction`, không gọi tool trực tiếp.
- Tool executor enforce allowlist, args schema, confirmation và idempotency.
- Memory chỉ ghi key trong allowlist.
- Retry chỉ sửa structured output sai schema, không retry side effect mù quáng.
- Mỗi request có `trace_id` để nối API log, LLM step và tool step.

## Tools

- `search_kb`: read-only, tìm knowledge base nội bộ, `top_k <= 5`.
- `create_ticket`: side effect, cần `user_confirmed=true` và `idempotency_key`.

## Memory

Memory demo gồm:

- Session history theo `(user_id, session_id)`.
- User profile allowlist: `preferred_language`, `product_area`, `role`, `timezone`.

Production cần thay in-memory store bằng Postgres/Redis có TTL, tenant isolation, backup, delete/export path và audit trail.

## How to run

```bash
cd lessions/day-24-ai-assistant-tool-calling-memory
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn assistant_app.app:app --reload
```

Request mẫu:

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{
    "user_id": "u1",
    "session_id": "s1",
    "message": "Gói Pro có SLA không?",
    "idempotency_key": "req-001"
  }'
```

Chạy tests:

```bash
pytest -q
```

## Production notes

Bản này chưa nên đưa thẳng vào production. Để production-ready cần:

- AuthN/AuthZ và rate limit.
- Provider LLM thật có timeout, retry, circuit breaker, token budget.
- Durable memory/idempotency store.
- Redacted logs và PII policy.
- Golden tests trước khi đổi prompt/model/tool schema.
- Observability: p50/p95 latency, schema retry rate, tool error rate, ticket duplicate rate.
