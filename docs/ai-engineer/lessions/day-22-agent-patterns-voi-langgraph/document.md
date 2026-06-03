# Day 22 Document: Production Reference Cho Agent Patterns Với LangGraph

## 1. Decision Guide

Chọn pattern theo context, không theo độ "ngầu":

| Tình huống | Pattern | Best solution |
|---|---|---|
| Người dùng hỏi ngắn, đôi khi cần lookup | ReAct | `MessagesState` + `ToolNode` + `tools_condition`, tool read-only |
| Câu hỏi rơi vào một trong vài domain rõ | Router | Structured classifier trước, mỗi route có tool set riêng |
| Task có nhiều bước phụ thuộc nhau | Planner-executor | Planner sinh plan có schema, executor chạy có budget |
| Nhiều nhóm capability tách biệt | Supervisor | Supervisor route tới specialist, không share tool quá rộng |
| Action có side effect/rủi ro | Human-in-the-loop | `interrupt` + persistent checkpointer + approval UI |

Rule thực tế: bắt đầu bằng router + ReAct nhỏ. Chỉ nâng lên planner-executor/supervisor khi complexity thật sự xuất hiện qua requirement hoặc production incident.

## 2. State Design

State tốt phải đủ thông tin để resume nhưng không biến thành data lake.

Nên có:

- `messages`: lịch sử message cần cho model.
- `tenant_id` hoặc reference tới tenant trong config metadata, không để model tự điền.
- `route`: route đã chọn.
- `budget`: max steps/tool calls/tokens.
- `pending_action`: action cần approval nếu có.
- `audit_refs`: id của ticket/refund/log, không nhét raw sensitive payload.

Không nên có:

- Raw API client, DB connection, file handle.
- Secret, access token, API key.
- Toàn bộ document dài nếu chỉ cần summary/reference id.
- Permission do model tạo.

Ví dụ state cho support workflow:

```python
from typing import Literal, TypedDict

from langgraph.graph import MessagesState


class SupportState(MessagesState):
    route: Literal["billing", "policy", "technical", "fallback"] | None
    step_count: int
    pending_action_id: str | None
    final_ticket_id: str | None
```

## 3. Tool Design Checklist

Tool tốt cho agent cần giống một internal API endpoint có contract rõ:

- Tên tool là động từ cụ thể: `get_order_status`, `search_policy`, `create_ticket_draft`.
- Docstring nói rõ tool làm gì, khi nào dùng, output là gì.
- Input schema chặt: enum, min/max length, format, limit.
- Tool không nhận `tenant_id`, `user_id`, `role` từ model nếu đó là auth context.
- Backend inject auth context từ request/session.
- Có timeout ngắn hơn timeout tổng của request.
- Có idempotency key cho write tool.
- Có audit event cho write và high-risk read.
- Trả output ngắn, có cấu trúc, tránh dump dữ liệu lớn vào message history.

## 4. Permission Model

Một permission matrix tối thiểu:

| Capability | Auto-call | Cần approval | Ghi chú |
|---|---:|---:|---|
| Search public policy | Có | Không | Rate limit và cache |
| Read order của tenant hiện tại | Có | Không | Authz server-side |
| Create draft ticket | Có thể | Tùy org | Idempotent, audit |
| Send email to customer | Không | Có | Preview trước khi gửi |
| Refund/payment | Không | Có | Payment service enforce permission |
| Delete/update record | Không | Có | Require reason + audit |
| Execute shell/SQL | Không | Có | Sandbox + allowlist |

Prompt có thể mô tả policy, nhưng enforcement phải nằm trong code.

## 5. Recursion Limit Và Budget

`recursion_limit` giới hạn số bước graph được thực thi. Với ReAct agent, mỗi vòng thường gồm:

```text
agent node -> tools node -> agent node
```

Nếu đặt quá thấp, agent chưa kịp hoàn thành. Nếu đặt quá cao, incident cost/latency sẽ nặng hơn.

Gợi ý ban đầu:

| Workflow | `recursion_limit` | Max tool calls |
|---|---:|---:|
| Read-only Q&A đơn giản | 6-8 | 2-3 |
| Support lookup nhiều nguồn | 8-12 | 4-6 |
| Planner-executor | Theo số step + margin | Theo plan budget |
| HITL | Tính cả node approval/resume | Theo action policy |

Ngoài `recursion_limit`, vẫn cần budget riêng:

- Max tokens per model call.
- Max total tokens per request.
- Max wall-clock time.
- Max tool latency.
- Max retry count.
- Max cost per tenant/request.

## 6. Checkpoint, Interrupt, Resume

Checklist để human-in-the-loop chạy đúng:

- Compile graph với checkpointer.
- Mỗi invocation có `configurable.thread_id` ổn định.
- Node cần chờ người dùng gọi `interrupt(value)`.
- Client lưu interrupt id/value và hiển thị approval UI.
- Resume bằng `Command(resume=...)` với cùng config/thread.
- Node có `interrupt` phải idempotent vì khi resume node có thể chạy lại từ đầu.
- Side effect không đặt trước `interrupt` trong cùng node nếu có thể bị chạy lại.

Anti-pattern:

```text
call_payment_service()
interrupt("Approve refund?")
```

Cách đúng:

```text
interrupt("Approve refund?")
call_payment_service_with_idempotency_key()
```

## 7. Observability Schema Gợi Ý

Event log nên đủ để trả lời "agent đã làm gì và vì sao request này tốn tiền/chậm/sai".

```json
{
  "event": "agent.tool_call",
  "request_id": "req_123",
  "thread_id": "thread_abc",
  "tenant_id": "tenant_001",
  "workflow": "support_agent_v1",
  "node": "tools",
  "tool": "get_order_status",
  "args_redacted": {"order_id": "ORD-1001"},
  "status": "success",
  "latency_ms": 142,
  "message_count": 6,
  "checkpoint_id": "ckpt_456"
}
```

Metrics cần alert:

- P95/P99 latency theo workflow.
- Error rate theo node/tool.
- Tool timeout rate.
- Recursion limit hit rate.
- Interrupt pending quá lâu.
- Token/cost theo tenant.
- Route fallback rate.
- Approval rejection rate.

## 8. Testing Strategy

Test agent không chỉ test final answer.

| Test | Mục tiêu |
|---|---|
| Unit test tool | Validate schema, authz, timeout, error mapping |
| Unit test router | Query vào đúng route, fallback khi mơ hồ |
| Graph test | Node/edge chạy đúng, không loop quá limit |
| Golden test | Bộ câu hỏi cố định cho tool selection/final answer |
| Injection test | Tool output/user input không override policy |
| HITL test | Interrupt, resume, reject/approve đều đúng |
| Idempotency test | Retry không tạo duplicate side effect |
| Load test | P95 latency/cost trong budget |

Ví dụ scenario golden test:

```text
Input: "Đơn ORD-1001 bị tính phí hai lần"
Expected route: billing
Expected tool: get_order_status, search_policy
Forbidden tool: refund_payment
Expected final: hướng dẫn escalation hoặc tạo ticket, không hứa refund trực tiếp
```

## 9. Failure Playbook

| Incident | Chẩn đoán nhanh | Fix ngắn hạn | Fix dài hạn |
|---|---|---|---|
| Agent gọi tool lặp | Xem trace node/tool, recursion hit | Giảm limit, block loop pattern | Eval + prompt/tool output redesign |
| Cost tăng đột biến | Xem token/tool count theo tenant | Hạ budget, rate limit | Router, cache, model routing |
| Gọi nhầm write tool | Xem permission/audit | Disable tool, require approval | Tách read/write registry |
| Trả lời theo tool injection | Xem raw tool output | Sanitize output, system patch | Tool result parser + eval injection |
| Duplicate ticket/refund | Xem idempotency/audit | Deduplicate thủ công | Idempotency key ở service boundary |
| Resume HITL lỗi | Xem thread_id/checkpoint | Retry với đúng config | Persistent checkpointer + integration test |

## 10. Production Readiness Checklist

- [ ] Có owner cho workflow và tool registry.
- [ ] Có state schema version.
- [ ] Có `recursion_limit` và budget.
- [ ] Có timeout/retry/fallback rõ.
- [ ] Có persistent checkpointer nếu workflow cần resume.
- [ ] Có HITL cho high-risk side effect.
- [ ] Có idempotency key cho write tool.
- [ ] Có audit log không sửa được cho action quan trọng.
- [ ] Có trace theo request/thread/node/tool/model.
- [ ] Có eval trước deploy và canary sau deploy.
- [ ] Có kill switch để disable tool/workflow.
- [ ] Có data retention policy cho checkpoints và traces.

## 11. Tài Liệu Tham Khảo

- LangGraph Python reference: `StateGraph`, `MessagesState`, `ToolNode`, `tools_condition`, checkpointer, `interrupt`, `Command`.
- ReAct paper: reasoning and acting pattern.
- OWASP Top 10 for LLM Applications: prompt injection, tool abuse, sensitive data leakage.
- Day 19 trong khóa học: structured output và function calling.
- Day 20 trong khóa học: production architecture, observability, quota, audit.
- Day 23 trong khóa học: security basics cho LLM app.
