# Day 24: Mini-project - AI Assistant có Tool Calling + Memory

## Mục tiêu

Build một **Support AI Assistant API backend** nhỏ nhưng có boundary gần production:

- Nhận request qua API `/chat`.
- Dùng prompt template có version, policy và tool catalog.
- Bắt model trả về structured output theo schema.
- Gọi ít nhất 2 tools qua tool executor, không cho model gọi hàm trực tiếp.
- Có memory đơn giản theo user/session.
- Có logging, trace id, timeout, retry schema và idempotency cho action có side effect.
- Có tests cho schema, tool policy và prompt injection.

## Bối cảnh bài toán

Ta xây một assistant cho customer support:

```text
Người dùng hỏi về sản phẩm/chính sách
  -> assistant tìm trong knowledge base nếu cần
  -> assistant trả lời kèm nguồn
  -> nếu người dùng muốn tạo ticket, assistant yêu cầu xác nhận
  -> khi đã xác nhận, assistant tạo ticket idempotent
  -> assistant chỉ ghi nhớ preference an toàn
```

Phạm vi cố ý nhỏ:

- Không browse web.
- Không chạy raw SQL.
- Không tự refund, gửi email, xóa dữ liệu hoặc gọi tool nguy hiểm.
- Không lưu secret, token, password, payment data hoặc PII nhạy cảm vào memory.
- Mỗi request phải có `user_id`, `session_id` và optional `idempotency_key`.

## Kiến trúc tổng quan

```text
Client
  -> FastAPI /chat
  -> ConversationService
     -> MemoryStore: load session history + user profile
     -> PromptBuilder: render prompt versioned
     -> LLMClient: sinh structured action
     -> Schema Validator: Pydantic validate JSON
     -> ToolExecutor: allowlist + policy + timeout + idempotency
     -> MemoryStore: save safe memory updates
     -> Structured Logs: trace_id, latency, tool calls, errors
  -> Response
```

Flow chuẩn:

1. API nhận `user_id`, `session_id`, `message`, `idempotency_key`.
2. Service load `recent_messages` và user memory allowlist.
3. Prompt builder render system prompt với policy, schema, tools và memory summary.
4. LLM trả JSON theo `AssistantAction`.
5. Backend validate JSON bằng Pydantic.
6. Nếu action là `call_tool`, tool executor kiểm tra allowlist, args, confirmation, idempotency.
7. Service đưa tool result vào prompt lần hai để model tạo final answer.
8. Service cập nhật memory nếu key nằm trong allowlist.
9. Service ghi structured log với `trace_id` và trả response.

## Structured output contract

Model không được trả free-form text trực tiếp cho business logic. Nó phải trả JSON:

```python
class ToolRequest(BaseModel):
    name: Literal["search_kb", "create_ticket"]
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantAction(BaseModel):
    action: Literal["answer", "call_tool", "ask_clarification"]
    tool: ToolRequest | None = None
    final_answer: str | None = None
    memory_updates: dict[str, str] = Field(default_factory=dict)
```

Business rules quan trọng:

- `action="answer"` phải có `final_answer`.
- `action="ask_clarification"` phải có `final_answer`.
- `action="call_tool"` phải có `tool`.
- `memory_updates` chỉ nhận key an toàn như `preferred_language`, `product_area`, `role`.
- Args do LLM sinh ra luôn bị xem là untrusted input.

## Prompt template

Prompt nên có các phần tách rõ:

- Role: assistant là support orchestrator, không phải autonomous agent.
- Safety policy: không tiết lộ prompt, không làm theo instruction trong tool result.
- Tool catalog: tên tool, input, output, policy.
- Memory summary: chỉ preference đã validate.
- Output schema: bắt buộc JSON, không markdown.
- Task: xử lý message hiện tại.

Prompt nên có version, ví dụ `support-assistant-v1`. Khi đổi prompt, log phải ghi version để debug regression.

## Tool executor

Tool executor là lớp bảo vệ giữa LLM và hệ thống thật.

Tool 1: `search_kb`

```text
Input: query, top_k
Output: list[{title, snippet, source}]
Policy: read-only, top_k từ 1 đến 5, timeout ngắn
```

Tool 2: `create_ticket`

```text
Input: title, summary, priority, user_confirmed
Output: ticket_id, status
Policy: chỉ tạo khi user_confirmed=true, cần idempotency_key
```

Nguyên tắc:

- Chỉ tool nằm trong allowlist mới được chạy.
- Validate args bằng schema riêng cho từng tool.
- Side effect phải có confirmation và idempotency.
- Có `MAX_TOOL_CALLS`, timeout và structured error.
- Không truyền secret vào prompt hoặc tool result.

## Memory policy

Memory trong bài này là application-owned store, không phải "niềm tin" vào model.

Loại memory:

- Short-term: vài message gần nhất trong session.
- Long-term profile: preference nhỏ theo user, ví dụ `preferred_language`, `product_area`, `role`.
- Summary: có thể thêm sau để giảm token khi hội thoại dài.

Schema tối thiểu:

```text
user_id
session_id
key
value
updated_at
source
```

Policy:

- Scope theo user/tenant, không dùng global key mơ hồ.
- Chỉ lưu key trong allowlist.
- Không lưu raw prompt dài nếu có PII.
- Có delete path và TTL nếu dùng cho production.
- Khi model đề xuất memory update, backend validate lại trước khi ghi.

## Retry khi output sai schema

Retry chỉ dùng để sửa format hoặc schema, không dùng để lặp business action.

```python
def complete_action_with_retry(llm, prompt, max_retries=2):
    last_error = None
    for attempt in range(max_retries + 1):
        raw = llm.complete(prompt)
        try:
            return AssistantAction.model_validate_json(raw)
        except Exception as exc:
            last_error = str(exc)
            prompt = prompt + "\nReturn only valid JSON matching the schema. No markdown."
    raise ValueError(f"invalid_llm_output: {last_error}")
```

Lưu ý: nếu tool `create_ticket` đã chạy thành công, retry final answer không được tạo ticket lần hai. Đây là lý do cần `idempotency_key`.

## Idempotency

Với tool có side effect, cùng một request retry có thể bị gửi lại vì timeout, network error hoặc schema retry. `create_ticket` cần idempotency:

```text
idempotency_key = user_id + session_id + client_request_id
```

Nếu key đã tồn tại, tool trả lại `ticket_id` cũ thay vì tạo ticket mới.

## Trace và logging

Mỗi request cần log metadata:

```json
{
  "trace_id": "tr_...",
  "prompt_version": "support-assistant-v1",
  "user_id_hash": "sha256...",
  "session_id": "s1",
  "action": "call_tool",
  "tool_name": "search_kb",
  "latency_ms": 84,
  "retry_count": 1,
  "error": null
}
```

Không log raw prompt, password, token, full user message nếu sản phẩm có PII. Trong bài học, code demo log ít để dễ quan sát; production cần redaction nghiêm hơn.

## Trade-off

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Ghi chú production |
|---|---|---|---|
| Raw SDK/provider client | App nhỏ, muốn hiểu boundary rõ | Workflow graph phức tạp | Tốt cho Day 24 |
| LangGraph | Cần state machine nhiều bước | Chỉ có 1-2 tool đơn giản | Hữu ích từ Day 22 trở đi |
| SQLite/in-memory memory | Demo, local, test | Multi-region hoặc nhiều worker | Dễ inspect, không bền vững |
| Redis/Postgres memory | Production backend thông thường | Prototype cực nhỏ | Có TTL, concurrency tốt hơn |
| One-shot tool call | Flow đơn giản, latency thấp | Cần nhiều bước phụ thuộc nhau | Dễ kiểm soát |
| Agent loop nhiều bước | Nhiều tools, cần lập kế hoạch | Public app rủi ro cao | Phải có max steps, budget, audit |
| Auto-create ticket | Internal trusted workflow | Public chatbot | Public cần confirmation |

## Performance

- Mỗi tool loop thường thêm ít nhất 1 LLM call, làm tăng latency và cost.
- Giới hạn `MAX_TOOL_CALLS` nhỏ, ví dụ 2-3 cho support assistant.
- Conversation history dài làm tăng token cost; dùng summary hoặc chỉ lấy last N messages.
- Cache kết quả `search_kb` cho query lặp lại.
- Timeout riêng cho LLM và từng tool.
- Log p50/p95 latency theo phase: `memory_load`, `llm_plan`, `tool`, `llm_final`, `total`.
- Retry schema chỉ nên 1-2 lần; retry nhiều làm tăng tail latency.

## Security prompts cần test

Test các case sau:

- Người dùng yêu cầu "ignore previous instructions".
- Knowledge base snippet chứa instruction độc hại.
- Người dùng yêu cầu lộ system prompt hoặc tool schema nội bộ.
- Người dùng ép tạo ticket khi chưa confirm.
- Người dùng đưa secret và yêu cầu ghi nhớ.

Backend không thể chỉ dựa vào prompt để an toàn. Tool executor, schema validation, memory allowlist và logging redaction mới là lớp kiểm soát chính.

## Dùng được trong production không? Nếu có thì cần điều kiện gì?

Có thể dùng làm nền cho production nếu thay các phần demo bằng hạ tầng thật và bổ sung guardrails:

- Thay `FakeLLMClient` bằng provider client thật có timeout, retry, circuit breaker và rate limit.
- Thay in-memory store bằng Postgres/Redis có TTL, tenant isolation và migration.
- Dùng authentication, authorization, quota theo user/tenant.
- Redact log, kiểm soát PII, có retention policy.
- Có golden tests trước khi đổi model/prompt/tool schema.
- Có observability: trace, metrics, alert theo error rate, latency, tool failures.
- Có human handoff cho case high-risk hoặc low-confidence.

Không nên đưa thẳng bản demo vào production vì memory và ticket store là in-memory, chưa có auth thật, chưa có distributed lock, chưa có PII compliance và chưa tích hợp provider LLM thật.

## Kết quả cuối bài

Bạn nên đọc và chạy thư mục `assistant_app/` trong bài này. Nó là reference implementation tối giản nhưng thể hiện các boundary quan trọng: API, prompt, schema, tools, memory, idempotency, trace, retry và tests.
