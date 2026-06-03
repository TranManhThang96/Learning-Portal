# Day 21 Document: Decision Guide Và Production Checklist

## 1. One-Page Decision Guide

Khi chọn framework cho LLM app, hãy đi theo thứ tự câu hỏi này.

### Bước 1: Bài Toán Có Cần LLM Framework Không?

Nếu chỉ cần một call để phân loại, trích xuất JSON hoặc tóm tắt ngắn, hãy bắt đầu bằng Raw SDK bọc trong `LLMClient`.

Chỉ thêm framework khi có một trong các nhu cầu thật:

- Nhiều bước compose thành chain.
- Nhiều integration model/retriever/tool.
- RAG ingestion/retrieval là phần phức tạp.
- Workflow có state, loop, checkpoint, approval.
- Cần tối ưu prompt/pipeline bằng evaluation.

### Bước 2: Vấn Đề Chính Là Gì?

| Vấn đề chính | Lựa chọn nên thử trước |
|---|---|
| Control, latency, cost, request shape | Raw SDK |
| Compose prompt/model/parser/tool nhanh | LangChain LCEL |
| Ingestion, chunking, indexing, retrieval | LlamaIndex |
| Stateful agent, loop, HITL, checkpoint | LangGraph |
| Prompt/program optimization theo metric | DSPy |

### Bước 3: Production Constraint Nào Quan Trọng Nhất?

| Constraint | Gợi ý |
|---|---|
| p95 latency thấp | Raw SDK, cache, model nhỏ, ít calls |
| Audit/compliance | Explicit service layer, trace, prompt/schema version |
| Multi-tenant RAG | LlamaIndex hoặc custom retrieval với metadata filter bắt buộc |
| Human approval | LangGraph hoặc workflow engine có checkpoint |
| Fast iteration | LangChain LCEL, nhưng pin version và test |
| Quality optimization | Golden set + eval + DSPy hoặc prompt eval pipeline |

## 2. ADR Mẫu

```markdown
# ADR: Chọn Abstraction Cho Support Ticket Triage

## Status

Accepted

## Context

Team cần build service phân loại support ticket thành structured output:
category, priority, needs_human, confidence, reasons và draft_reply.
SLA p95 dưới 2 giây, volume 50k tickets/ngày, dữ liệu có PII,
cần audit prompt/model/schema version. Hiện tại workflow chỉ có một LLM call,
chưa cần retrieval hoặc tool execution.

## Decision

Bắt đầu với Raw SDK thông qua internal `LLMClient`.
Không dùng LangChain ở phase đầu vì chain chưa phức tạp.
Không dùng LlamaIndex vì chưa có document-heavy RAG.
Không dùng LangGraph vì chưa có stateful workflow hoặc HITL.
Chuẩn bị interface để có thể thêm LangChain/LangGraph sau.

## Consequences

Ưu điểm:
- Kiểm soát timeout, retry, logging, schema và cost rõ.
- Ít dependency và ít version churn.
- Dễ tối ưu latency.

Nhược điểm:
- Team phải tự viết wrapper, tests và observability.
- Nếu workflow tăng lên nhiều bước, code có thể trở nên dài.

## Production Conditions

- Pydantic schema strict.
- Prompt versioned.
- Model routed qua config.
- Structured logs có trace_id, model, token, latency, retry_count.
- Redaction trước khi log raw ticket.
- Golden test set tối thiểu 100 tickets.
- Dashboard p50/p95 latency, schema error rate, escalation rate, cost/day.

## Revisit

Revisit nếu:
- Workflow có nhiều bước/tool.
- Cần retrieval từ knowledge base.
- Cần human approval cho refund.
- Có hơn 3 provider/model cần support cùng lúc.
```

## 3. Framework Evaluation Matrix

Chấm mỗi tiêu chí từ 1 đến 5 theo context của team.

| Tiêu chí | Raw SDK | LangChain LCEL | LlamaIndex | LangGraph | DSPy |
|---|---:|---:|---:|---:|---:|
| Control request/response | 5 | 3 | 3 | 3 | 2 |
| Tốc độ prototype chain | 2 | 5 | 3 | 3 | 3 |
| RAG data abstraction | 1 | 3 | 5 | 2 | 3 |
| Stateful workflow | 1 | 2 | 2 | 5 | 2 |
| Evaluation-driven optimization | 2 | 2 | 2 | 2 | 5 |
| Debug dễ nếu trace tốt | 5 | 3 | 3 | 4 | 3 |
| Dependency/version risk thấp | 4 | 2 | 2 | 2 | 2 |
| Performance tuning sâu | 5 | 3 | 3 | 3 | 2 |

Không cộng điểm máy móc. Matrix chỉ giúp thảo luận rõ trade-off.

## 4. Observability Checklist

### Trace Fields Bắt Buộc

| Field | Lý do |
|---|---|
| `trace_id` | Join log giữa API, LLM, retriever, tool |
| `tenant_id` | Debug quota, cache, data isolation |
| `workflow_name` | Biết flow nào đang lỗi |
| `workflow_version` | Rollback và so sánh version |
| `prompt_id` | Biết prompt nào được dùng |
| `prompt_version` | Debug prompt regression |
| `schema_version` | Debug output contract |
| `provider` | Debug provider outage/rate limit |
| `model` | Debug quality/cost/latency thay đổi |
| `input_tokens` | Cost và prompt bloat |
| `output_tokens` | Cost và output length |
| `latency_ms` | SLA |
| `retry_count` | Cost spike và reliability |
| `error_type` | Phân loại lỗi |
| `validation_status` | Structured output health |

### Metrics Nên Có

- Request count theo workflow/model/tenant.
- p50/p95/p99 latency.
- Token trung bình/request.
- Cost/ngày và cost/tenant.
- Schema validation error rate.
- Rate limit error rate.
- Timeout rate.
- Retry count distribution.
- Cache hit rate.
- Human escalation rate.
- Auto-send vs manual-review rate.
- Retrieval hit quality nếu có RAG.
- Tool error rate nếu có tool.

### Logs Không Nên Lưu Raw

- API key, session token, OAuth token.
- Password, secret, private key.
- Full credit card, government id.
- Raw customer PII nếu chưa có policy retention.
- Tool args chứa credentials.
- Full document content nhạy cảm.

## 5. Structured Output Flow: Ticket Triage

### Output Schema

```json
{
  "category": "billing | bug | howto | account | other",
  "priority": "low | medium | high | urgent",
  "needs_human": true,
  "confidence": 0.87,
  "reasons": ["billing dispute", "refund requested"],
  "draft_reply": "..."
}
```

### Business Rules Gợi Ý

| Tình huống | Priority | needs_human |
|---|---|---|
| Câu hỏi how-to đơn giản | low/medium | false |
| Bug ảnh hưởng một user, có workaround | medium | false hoặc true nếu enterprise |
| Billing dispute/refund | high | true |
| Security, data leak, account takeover | urgent | true |
| Enterprise customer down | urgent | true |
| Confidence thấp | medium/high | true |

### Quality Metrics

- Exact schema valid rate >= 99%.
- Category macro-F1 theo golden set.
- Priority macro-F1 theo golden set.
- False negative rate của `needs_human` thấp nhất có thể, vì bỏ sót escalation nguy hiểm hơn review thừa.
- Draft reply policy violation rate.

## 6. Abstraction Risk Register

| Risk | Dấu hiệu | Mitigation |
|---|---|---|
| Hidden retry | Cost/request tăng bất thường | Chọn một layer retry, log retry_count |
| Prompt không version | Output đổi nhưng không biết vì sao | Prompt Registry, prompt_id/version |
| Schema drift | Client parse lỗi | Version schema, validate bằng Pydantic |
| Provider behavior drift | Fallback trả khác quality | Golden tests theo provider/model |
| Tool side effect duplicate | Refund/ticket update bị chạy 2 lần | Idempotency key, approval, audit |
| Tenant data leak | Retrieval/cache trả data tenant khác | Metadata filter bắt buộc, cache key có tenant |
| Callback leak PII | Trace chứa raw ticket | Redaction, allowlist logging |
| Agent infinite loop | Latency/cost spike | Max iterations, timeout, stop condition |
| Over-abstraction | Debug phải đọc framework internals | Trace từng step, giữ service boundary |

## 7. Khi Kết Hợp Nhiều Framework

Kết hợp framework là bình thường, nhưng phải rõ ownership:

```text
FastAPI service
  -> domain service: TicketWorkflow
      -> Raw SDK: strict classification call
      -> LlamaIndex: retrieve policy docs
      -> LangGraph: approval workflow nếu cần refund
      -> LangChain LCEL: compose prompt + structured output cho draft reply
```

Nguyên tắc:

- Domain service sở hữu business policy.
- Framework chỉ là implementation detail.
- Tool permission không nằm trong prompt.
- Output từ framework luôn đi qua validation.
- Trace xuyên suốt, không mất `trace_id` giữa các layer.

## 8. Production Readiness Checklist

- [ ] Có owner cho workflow.
- [ ] Có ADR chọn abstraction.
- [ ] Có prompt_id và prompt_version.
- [ ] Có schema_version.
- [ ] Có model routing config.
- [ ] Có timeout và retry policy rõ.
- [ ] Có structured logging.
- [ ] Có dashboard latency/cost/error.
- [ ] Có redaction policy.
- [ ] Có golden test set.
- [ ] Có rollback plan cho prompt/model/package.
- [ ] Có tenant isolation nếu multi-tenant.
- [ ] Có human approval cho action nhạy cảm.
- [ ] Có runbook khi provider 429/outage.

## 9. Câu Trả Lời Phỏng Vấn Ngắn

Nếu được hỏi "nên dùng LangChain hay gọi Raw SDK?", câu trả lời tốt không phải là chọn ngay một bên.

Một câu trả lời production-oriented:

> Nếu flow chỉ là một call structured output có SLA chặt, tôi bắt đầu bằng Raw SDK bọc trong internal LLMClient để kiểm soát timeout, retry, schema validation, token/cost và trace. Nếu workflow bắt đầu có nhiều chain, tool integration hoặc cần prototype nhiều provider, tôi cân nhắc LangChain LCEL nhưng sẽ pin version, thêm golden tests và trace từng step. Nếu vấn đề chính là RAG document ingestion/retrieval, tôi đánh giá LlamaIndex. Nếu agent có state, loop, checkpoint hoặc human approval, tôi dùng LangGraph. Quyết định cuối cùng phải dựa trên eval, SLA, observability và năng lực vận hành của team.
