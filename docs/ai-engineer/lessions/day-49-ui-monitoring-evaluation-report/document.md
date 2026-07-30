# Day 49 Document: UI, Monitoring, Evaluation Report Reference

## 1. UI Review Checklist

| Item | Required | Evidence |
|---|---|---|
| Chat input | Yes | Can submit Vietnamese question |
| Answer rendering | Yes | Shows grounded answer |
| Citation cards | Yes | doc/page/section/chunk visible |
| Source excerpt | Recommended | Click citation or side panel |
| Trace ID | Yes | Copyable |
| Latency breakdown | Yes | retrieve/rerank/generate/total |
| Token/cost | Yes | usage block |
| Feedback | Yes | rating + reason + trace_id |
| Error state | Yes | timeout/index not ready/citation invalid |
| ACL behavior | Yes | No source leak in citation panel |

## 2. Feedback Schema

```json
{
  "trace_id": "trace_20260510_001",
  "conversation_id": "demo-session-001",
  "rating": "up|down",
  "reason": "helpful|wrong_answer|wrong_source|missing_citation|incomplete|too_slow|no_answer_wrong|policy_violation",
  "comment": "optional redacted text"
}
```

Validation:

- `trace_id` required.
- `rating` enum.
- `reason` required for `down`.
- `comment` max length, redact PII.

## 3. Monitoring Metrics Catalog

| Metric | Type | Tags |
|---|---|---|
| `rag_requests_total` | counter | status, model, prompt_version |
| `rag_request_duration_seconds` | histogram | stage, model, prompt_version |
| `rag_input_tokens` | histogram | model |
| `rag_output_tokens` | histogram | model |
| `rag_estimated_cost_usd` | histogram | model |
| `rag_empty_retrieval_total` | counter | index_version |
| `rag_citation_invalid_total` | counter | prompt_version |
| `rag_schema_failures_total` | counter | model |
| `rag_guardrail_refusals_total` | counter | reason |
| `rag_feedback_down_total` | counter | reason |

Không dùng `tenant_id`, `user_id`, email, question hoặc `trace_id` làm metric label.
Chúng có cardinality cao và có thể chứa dữ liệu nhạy cảm. Để debug từng request, dùng
trace/log đã kiểm soát quyền.

## 4. Evaluation Report Template

```markdown
# Evaluation Report

Date:
Author:
Git SHA:
Eval set version:
Corpus version:
Index version:
Prompt version:
LLM model:
Embedding model:
Reranker:

## Executive Summary

Decision: PASS / CONDITIONAL PASS / FAIL

## Metrics

| Metric | Current | Previous | Threshold | Status |
|---|---:|---:|---:|---|
| Recall@5 |  |  |  |  |
| MRR@10 |  |  |  |  |
| Citation validity |  |  |  |  |
| Citation correctness |  |  |  |  |
| Faithfulness |  |  |  |  |
| Format pass rate |  |  |  |  |
| No-answer accuracy |  |  |  |  |
| Prompt injection block rate |  |  |  |  |
| ACL leak count |  |  |  |  |
| Missing evidence count |  |  |  |  |
| p95 latency ms |  |  |  |  |
| Avg cost/request |  |  |  |  |

Thêm cột `Applicable cases` trong report thật. `N/A` không phải pass.

## Results By Tag

| Tag | Cases | Pass rate | Main issue |
|---|---:|---:|---|

## Failure Analysis

| Case ID | Layer | Expected | Actual | Fix |
|---|---|---|---|---|

## Release Notes

## Risks And Limitations

## Next Actions
```

## 5. Release Decision Rules

`PASS`:

- No ACL/security critical failure.
- Citation correctness đạt threshold.
- Format pass rate đạt threshold.
- No-answer behavior đạt threshold.
- Latency/cost trong budget.

`CONDITIONAL PASS`:

- Non-critical regression có owner.
- Có canary và rollback.
- Known issue không ảnh hưởng security/data leak.

`FAIL`:

- Any ACL leak.
- Prompt injection critical case pass-through.
- Citation failure cao.
- Format response làm client hỏng.
- p95 latency/cost vượt xa budget mà không có mitigation.

## 6. Demo Flow 3 Phút

1. Hỏi câu normal về HR policy.
2. Click citation, chỉ ra doc/page/section/chunk.
3. Mở trace detail, chỉ latency/token/cost.
4. Submit feedback `down` với reason `wrong_source` hoặc `up`.
5. Hỏi câu ngoài tài liệu để thấy no-answer.
6. Mở evaluation report và release decision.

## 7. Data Privacy Notes

- Không hiển thị raw logs cho end user.
- Không log raw question nếu có PII.
- Hash `user_id` và `question`.
- Redact comment feedback.
- Trace detail cần role admin/support.
- Source excerpt phải qua ACL giống query.

## 8. Nguồn Kỹ Thuật Đã Xác Minh

Truy cập ngày `2026-06-08`:

- [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/):
  phân biệt traces, metrics và logs.
- [OpenTelemetry metrics](https://opentelemetry.io/docs/concepts/signals/metrics/):
  counter, gauge, histogram và aggregation.
- [OpenTelemetry logs](https://opentelemetry.io/docs/concepts/signals/logs/):
  structured log có schema ổn định và correlation bằng trace/span IDs.
- [Prometheus metric and label naming](https://prometheus.io/docs/practices/naming/):
  base units, `_total` cho counter và tránh high-cardinality labels.
- [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/):
  API output contract mà UI Day 49 phải bám theo.

Các nguồn trên là reference; bài học giữ implementation vendor-neutral để capstone
có thể dùng OpenTelemetry/Prometheus hoặc backend observability tương đương.
