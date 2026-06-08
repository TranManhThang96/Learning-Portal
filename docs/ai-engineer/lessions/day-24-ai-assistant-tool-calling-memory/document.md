# Tài liệu thiết kế: Support AI Assistant Backend

## 1. Requirement

Functional requirements:

- `POST /chat` nhận `user_id`, `session_id`, `message`, optional `idempotency_key`
  và `confirmed_actions`.
- Assistant trả lời câu hỏi support dựa trên knowledge base nội bộ.
- Assistant có thể tạo support ticket sau khi người dùng xác nhận.
- Assistant nhớ một số preference an toàn theo user.
- Mỗi response có `trace_id`, `answer`, `tool_calls`, `memory_updates`.

Non-functional requirements:

- Validate structured output trước khi thực thi tool.
- Giới hạn số lần gọi tool trong một request.
- Log đủ để debug nhưng không rò rỉ secret.
- Retry khi model trả output sai schema.
- Có tests cho schema, tool executor, memory policy và prompt injection.

## 2. API contract

Request:

```json
{
  "user_id": "u_123",
  "session_id": "s_abc",
  "message": "Gói Pro có SLA không?",
  "idempotency_key": "req_001",
  "confirmed_actions": []
}
```

Response:

```json
{
  "trace_id": "tr_...",
  "answer": "Gói Pro có SLA 99.9% theo tài liệu Support Policy.",
  "tool_calls": [
    {
      "name": "search_kb",
      "status": "ok"
    }
  ],
  "memory_updates": {}
}
```

## 3. Data model

Conversation message:

```text
user_id
session_id
role: user | assistant | tool
content
created_at
```

User memory:

```text
user_id
key
value
updated_at
source_session_id
```

Ticket:

```text
ticket_id
user_id
title
summary
priority
idempotency_key
created_at
```

## 4. Prompt template contract

Prompt phải nói rõ:

- Model chỉ được quyết định action, không được tự thực hiện side effect.
- Tool result là untrusted content, không phải instruction.
- Output chỉ là JSON theo schema.
- Nếu thiếu thông tin hoặc thiếu confirmation, phải hỏi lại.
- Không ghi nhớ secret/PII.

Ví dụ tool catalog:

```text
search_kb(query: string, top_k: int <= 5) -> read-only KB snippets
create_ticket(title, summary, priority) -> requires trusted confirmation context
```

## 5. Tool executor

Tool executor không tin vào model:

1. Kiểm tra tool name nằm trong allowlist.
2. Validate args bằng Pydantic schema riêng.
3. Enforce policy theo tool.
4. Chạy real integration bằng client có connect/read/total timeout; local fake
   function không cần giả lập timeout.
5. Trả structured result hoặc structured error.
6. Log tên tool, status, latency, không log dữ liệu nhạy cảm.

Với `create_ticket`, executor phải kiểm tra:

- `create_ticket` có trong confirmation context do application cung cấp.
- Có `idempotency_key`.
- Key được scope theo authenticated user/tenant.
- Nếu key đã tồn tại với cùng payload fingerprint, trả lại ticket cũ.
- Nếu cùng key nhưng payload khác, trả `idempotency_conflict`.

## 6. Memory policy

Memory write path:

```text
LLM đề xuất memory_updates
  -> backend lọc key bằng allowlist
  -> backend chặn value chứa secret pattern cơ bản
  -> backend ghi memory kèm source_session_id
```

Allowlist gợi ý:

- `preferred_language`
- `product_area`
- `timezone`
- `communication_style`

Không lưu:

- Password, access token, API key.
- Payment data.
- Government ID.
- Raw private conversation dài.
- Instruction do user muốn "ghi nhớ mãi" nhưng ảnh hưởng security policy.
- `role`, permission hoặc support tier do model đề xuất. Đây là authorization/business
  state và phải đến từ identity service hoặc CRM đáng tin cậy.

## 7. Idempotency

Trong distributed system, retry là bình thường. Một request tạo ticket có thể bị chạy lại nếu:

- Client retry do timeout.
- API gateway retry.
- Worker restart sau khi side effect đã chạy.
- Model output sai schema ở bước final answer.

Vì vậy `create_ticket` phải nhận `idempotency_key` từ request. Production nên lưu
`(actor_scope, idempotency_key, request_fingerprint, result)` trong database có
unique constraint và transaction.

## 8. Testing strategy

Schema tests:

- Reject JSON thiếu `final_answer` khi action là `answer`.
- Reject tool không nằm trong allowlist.
- Reject memory key không nằm trong allowlist.

Tool tests:

- `search_kb` giới hạn `top_k`.
- `create_ticket` fail khi chưa confirm.
- `create_ticket` idempotent với cùng key.

Security prompt tests:

- Prompt injection không được tạo ticket khi chưa confirm.
- Câu chữ "tôi xác nhận" không thay thế confirmation context.
- Secret không được ghi vào memory.
- Tool result độc hại không được override system prompt.

## 9. Production checklist

- AuthN/AuthZ trước `/chat`.
- Rate limit theo user/session/IP.
- Audit log cho tool có side effect.
- Redaction cho logs.
- Prompt versioning và rollback.
- Eval/golden set trước khi đổi model.
- Observability theo trace id.
- Timeout, retry và circuit breaker cho LLM provider.
- Tenant isolation cho memory và ticket.
- Delete/export memory theo privacy requirement.

## 10. Nguồn kỹ thuật đã đối chiếu

Đối chiếu ngày 2026-06-08:

- [OpenAI - Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs):
  phân biệt structured response và function calling, xử lý refusal, tránh schema drift.
- [OpenAI - Migrate to the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses):
  Responses API được khuyến nghị cho project mới; tool call và tool output là các item riêng.
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/):
  model validation, strict contract và cấu hình extra fields.
- [FastAPI request body](https://fastapi.tiangolo.com/tutorial/body/):
  request model và validation ở API boundary.
- [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/):
  prompt injection, excessive agency, improper output handling và sensitive data disclosure.
