# Document: Observability Schema, Dashboard Và Runbook

Tài liệu này là phần reference cho Day 44. Dùng nó khi cần thiết kế schema, dashboard, alert, privacy policy hoặc review production readiness cho một LLM/RAG app.

## 1. Architecture Tham Khảo

```text
Client
  -> API Gateway
  -> RAG API
       -> Trace Context
       -> Query Rewrite
       -> Hybrid Retrieval
       -> Reranker
       -> Context Builder
       -> LLM Gateway
       -> Citation Validator
       -> Feedback API
  -> Observability Outputs
       -> Metrics: Prometheus -> Grafana
       -> Logs: JSON -> ELK/OpenSearch
       -> Traces: OpenTelemetry -> Tempo/Jaeger/Datadog/etc.
       -> LLM Trace Store: Langfuse/LangSmith/custom table
```

Nguyên tắc: app không phụ thuộc vào một tool duy nhất. App phát ra telemetry theo contract ổn định, còn backend lưu trữ có thể thay đổi.

## 2. Trace Schema Contract

### 2.1 Required Fields

| Field | Type | Bắt buộc | Ghi chú |
|---|---:|---:|---|
| `trace_id` | string | Có | Sinh ở đầu request, trả về client |
| `tenant_id` | string | Có | Không dùng làm Prometheus label nếu quá nhiều tenant |
| `user_id_hash` | string/null | Có | Hash có salt, không log raw user id |
| `route` | string | Có | Ví dụ `/query` |
| `environment` | string | Có | `dev`, `staging`, `prod` |
| `query.raw_hash` | string | Có | Dùng join/debug không cần raw text |
| `query.raw_redacted` | string/null | Tùy policy | Chỉ có khi raw logging được phép |
| `retrieval.index_version` | string | Có | Bắt buộc để rollback/debug |
| `retrieval.candidates` | array | Có | Có thể chỉ lưu top N |
| `rerank.reranker_model` | string/null | Có | Null nếu không rerank |
| `context.chunk_ids` | array | Có | Danh sách chunk đưa vào prompt |
| `context.context_tokens` | number | Có | Token budget control |
| `generation.model` | string | Có | Model thực tế đã gọi |
| `generation.prompt_version` | string | Có | Prompt template version |
| `generation.input_tokens` | number | Có | Từ provider hoặc tokenizer estimate |
| `generation.output_tokens` | number | Có | Từ provider hoặc tokenizer estimate |
| `generation.ttft_ms` | number/null | Có | Null nếu không streaming và không đo được |
| `generation.latency_ms` | number | Có | Model call latency |
| `generation.estimated_cost_usd` | number | Có | Cost estimate theo pricing table version |
| `generation.pricing_table_version` | string | Có | Version/effective date của bảng giá dùng để estimate |
| `validation.citation_valid` | boolean | Có | Quality signal |
| `result.status` | string | Có | `success`, `error`, `timeout`, `blocked` |
| `result.total_latency_ms` | number | Có | End-to-end latency |

### 2.2 Candidate Chunk Fields

| Field | Type | Ghi chú |
|---|---:|---|
| `rank` | number | Rank trước hoặc sau rerank, ghi rõ context |
| `chunk_id` | string | Stable id, không chứa raw content |
| `document_id` | string | Document id hoặc hash |
| `source_uri_hash` | string | Hash nếu source URI nhạy cảm |
| `score_dense` | number/null | Dense similarity |
| `score_sparse` | number/null | BM25/sparse score |
| `score_rrf` | number/null | Hybrid merge score |
| `rerank_score` | number/null | Cross-encoder score |
| `acl_matched` | boolean | Permission filter |
| `metadata` | object | Chỉ metadata an toàn |

Không nên lưu toàn bộ chunk text trong candidate list mặc định. Nếu cần debug, lưu bản redacted hoặc lưu reference để người có quyền mở document gốc.

## 3. Event Catalog

| Event | Level | Payload tối thiểu |
|---|---|---|
| `query_received` | INFO | trace_id, tenant_id, user_id_hash, query_hash, query_length_chars |
| `query_rewritten` | INFO | trace_id, rewrite_enabled, rewritten_query_hash, latency_ms |
| `retrieval_started` | DEBUG/INFO | trace_id, strategy, top_k, index_version |
| `retrieval_completed` | INFO | trace_id, candidate_count, empty_retrieval, latency_ms |
| `rerank_completed` | INFO | trace_id, candidate_count, selected_count, latency_ms, top_score |
| `context_built` | INFO | trace_id, chunk_count, context_tokens, truncated |
| `generation_started` | INFO | trace_id, provider, model, prompt_version |
| `first_token_received` | INFO | trace_id, model, ttft_ms |
| `generation_completed` | INFO | trace_id, input_tokens, output_tokens, latency_ms, cost |
| `citation_validated` | INFO/WARN | trace_id, valid, failure_reason |
| `guardrail_blocked` | WARN | trace_id, policy, action, stage |
| `feedback_received` | INFO | trace_id, rating, reason, user_id_hash |
| `request_failed` | ERROR | trace_id, stage, error_type, retryable |

Quy ước payload:

- Dùng snake_case.
- Timestamp UTC.
- `trace_id` luôn có.
- Error có `error_type`, `stage`, `retryable`.
- Không log bearer token, API key, cookie, connection string.

## 4. Metrics Naming

### 4.1 Service Metrics

| Metric | Type | Labels | Ý nghĩa |
|---|---|---|---|
| `rag_request_total` | Counter | `route`, `status` | Tổng request |
| `rag_requests_in_flight` | Gauge | `route` | Request đang xử lý |
| `rag_stage_latency_seconds` | Histogram | `stage` | Latency theo stage |
| `rag_request_latency_seconds` | Histogram | `route` | End-to-end latency |
| `rag_error_total` | Counter | `stage`, `error_type` | Lỗi theo stage |

### 4.2 LLM Metrics

| Metric | Type | Labels | Ý nghĩa |
|---|---|---|---|
| `llm_ttft_seconds` | Histogram | `model` | Time to first token |
| `llm_request_total` | Counter | `model`, `status` | Model calls |
| `llm_token_total` | Counter | `model`, `type` | Input/output tokens |
| `llm_cost_usd_total` | Counter | `model` | Estimated cost |
| `llm_retry_total` | Counter | `model`, `reason` | Retry count |
| `llm_rate_limit_total` | Counter | `provider`, `model` | Provider rate limit |

### 4.3 RAG Quality Metrics

| Metric | Type | Labels | Ý nghĩa |
|---|---|---|---|
| `rag_empty_retrieval_total` | Counter | `index_version` | Retrieval trả 0 chunk |
| `rag_context_truncated_total` | Counter | `prompt_version` | Context bị cắt |
| `rag_citation_invalid_total` | Counter | `reason` | Citation sai |
| `rag_feedback_total` | Counter | `rating`, `reason` | User feedback |
| `rag_no_answer_total` | Counter | `reason` | App từ chối hoặc không đủ context |

### 4.4 Label Cardinality Rules

Không dùng các field sau làm metric label:

- `trace_id`.
- `user_id` hoặc `user_id_hash`.
- Raw `query`.
- `chunk_id`.
- `document_id` nếu số lượng lớn.
- `session_id`.
- Error message tự do.

Các field này nên nằm trong logs/traces, không nằm trong Prometheus labels.

## 5. Dashboard Panels

Dashboard tối thiểu cho Day 44:

| Panel | Query/nguồn | Mục tiêu |
|---|---|---|
| Request rate | `rate(rag_request_total[5m])` | Traffic |
| Error rate | `sum(rate(rag_request_total{status!="success"}[5m])) / sum(rate(rag_request_total[5m]))` | Reliability |
| p95 total latency | histogram quantile trên `rag_request_latency_seconds` | SLA |
| p95 stage latency | histogram quantile theo `rag_stage_latency_seconds` | Bottleneck |
| p95 TTFT | histogram quantile trên `llm_ttft_seconds` | UX streaming |
| Input/output tokens per minute | `rate(llm_token_total[5m])` | Token budget |
| Cost per hour | `increase(llm_cost_usd_total[1h])` | Budget |
| Empty retrieval rate | `rate(rag_empty_retrieval_total[5m]) / rate(rag_request_total[5m])` | Retrieval health |
| Citation failure rate | `rate(rag_citation_invalid_total[5m]) / rate(rag_request_total[5m])` | Answer trust |
| Feedback down rate | `rate(rag_feedback_total{rating="down"}[1h]) / rate(rag_feedback_total[1h])` | Quality trend |

Dashboard tốt phải có filter theo environment, route, model, prompt version và index version. Với tenant nhiều, chỉ filter tenant trên trace/log backend hoặc metric backend đã được thiết kế để chịu cardinality đó.

## 6. Alert Rules Gợi Ý

Ví dụ PromQL ở mức tham khảo:

```yaml
groups:
  - name: rag-observability
    rules:
      - alert: RAGHighErrorRate
        expr: |
          sum(rate(rag_request_total{status!="success"}[5m]))
          /
          sum(rate(rag_request_total[5m])) > 0.03
        for: 10m
        labels:
          severity: page
        annotations:
          summary: "RAG error rate > 3%"

      - alert: RAGHighP95Latency
        expr: |
          histogram_quantile(
            0.95,
            sum(rate(rag_request_latency_seconds_bucket[5m])) by (le)
          ) > 8
        for: 10m
        labels:
          severity: ticket
        annotations:
          summary: "RAG p95 latency > 8s"

      - alert: LLMHighTTFT
        expr: |
          histogram_quantile(
            0.95,
            sum(rate(llm_ttft_seconds_bucket[5m])) by (le, model)
          ) > 3
        for: 10m
        labels:
          severity: ticket
        annotations:
          summary: "LLM p95 TTFT > 3s"

      - alert: RAGCostSpike
        expr: |
          sum(increase(llm_cost_usd_total[1h]))
          >
          2 * (sum(increase(llm_cost_usd_total[24h])) / 24)
        for: 15m
        labels:
          severity: ticket
        annotations:
          summary: "LLM hourly cost is above normal baseline"

      - alert: RAGCitationFailureSpike
        expr: |
          sum(rate(rag_citation_invalid_total[15m]))
          /
          sum(rate(rag_request_total[15m])) > 0.05
        for: 15m
        labels:
          severity: ticket
        annotations:
          summary: "Citation failure rate > 5%"
```

Điều chỉnh threshold theo baseline thật. Alert không có owner và runbook thì chỉ tạo noise.

## 7. Storage Schema Tham Khảo

### 7.1 Trace Table

```sql
CREATE TABLE rag_traces (
    trace_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id_hash TEXT,
    session_id_hash TEXT,
    route TEXT NOT NULL,
    environment TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    query_redacted TEXT,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding_model TEXT,
    reranker_model TEXT,
    index_version TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    pricing_table_version TEXT NOT NULL,
    ttft_ms INTEGER,
    total_latency_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_type TEXT,
    citation_valid BOOLEAN,
    raw_trace JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_traces_created_at ON rag_traces (created_at DESC);
CREATE INDEX idx_rag_traces_tenant_created ON rag_traces (tenant_id, created_at DESC);
CREATE INDEX idx_rag_traces_versions ON rag_traces (prompt_version, model, index_version);
CREATE INDEX idx_rag_traces_status ON rag_traces (status, error_type);
```

### 7.2 Feedback Table

```sql
CREATE TABLE rag_feedback (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES rag_traces(trace_id),
    tenant_id TEXT NOT NULL,
    user_id_hash TEXT,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    reason TEXT NOT NULL,
    comment_hash TEXT,
    comment_redacted TEXT,
    triage_status TEXT NOT NULL DEFAULT 'new',
    triage_owner TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_feedback_trace ON rag_feedback (trace_id);
CREATE INDEX idx_rag_feedback_rating_created ON rag_feedback (rating, created_at DESC);
```

Nếu dùng data warehouse, có thể flatten một số field thường query và giữ `raw_trace` làm JSON.

## 8. Tooling Decision Matrix

| Context | Tooling khuyến nghị | Lý do |
|---|---|---|
| Capstone cá nhân | JSON logs + SQLite/Postgres trace table + report script | Dễ demo, ít vận hành |
| MVP nội bộ | Prometheus/Grafana + OpenTelemetry + structured logs | Đủ SLO và debug |
| RAG app cần prompt/feedback UI nhanh | Langfuse + Prometheus/Grafana | LLM-specific trace và cost workflow |
| LangChain/LangGraph app | LangSmith + Prometheus/Grafana | Trace chain/agent tốt |
| Enterprise platform | OpenTelemetry + Prometheus/Grafana + ELK/OpenSearch + optional LLM trace store | Hợp chuẩn platform |
| Regulated data | Self-host hoặc custom trace store, metadata-only default | Kiểm soát data residency |

Best default cho đa số team: OpenTelemetry cho traces, Prometheus/Grafana cho metrics, structured JSON logs cho ELK/OpenSearch, và LLM-specific trace store chỉ dùng khi đã qua security review.

## 9. Privacy Policy Template

### 9.1 Data Classification

| Data | Classification | Default action |
|---|---|---|
| Trace id, latency, status | Operational metadata | Log 100% |
| Model, prompt version, index version | Operational metadata | Log 100% |
| Token usage, cost | Billing metadata | Log 100% |
| User id | Personal data | Hash with salt |
| Query text | Potential PII | Hash, redact, sample raw only when allowed |
| Retrieved context | Potential confidential data | Store chunk ids, not raw text |
| Answer text | Potential PII/confidential | Redact and sample |
| Feedback comment | Potential PII | Hash, redact, length limit |
| API keys/tokens | Secret | Never log |

### 9.2 Redaction Requirements

- Redact trước khi ghi log, export trace hoặc gửi sang SaaS.
- Redaction phải chạy trên prompt, context, output, tool args và feedback comment.
- Secret scanning rule phải bắt bearer token, API key, cookie, password, connection string.
- Không dựa vào UI masking làm lớp bảo vệ duy nhất.
- Có test cho redaction với email, phone, ID number và secret format của công ty.

### 9.3 Sampling Requirements

- Metadata trace: 100%.
- Error/timeout/blocked: 100%.
- Negative feedback: 100%.
- Success raw content: 0-5% tùy data policy.
- Regulated tenant: raw content 0% mặc định.
- Eval/golden set: 100% nếu dữ liệu đã được approved.

### 9.4 Access Control

- Developer xem được metadata và redacted trace.
- Support chỉ xem trace của tenant được phân quyền.
- Security/admin xem audit log truy cập trace.
- Raw content nếu có phải cần quyền riêng và có expiry.
- Mọi truy cập trace production nên có audit event.

## 10. Runbook Incident

### 10.1 Latency Spike

1. Kiểm tra p95 total latency và stage latency.
2. Nếu `generation` tăng: kiểm tra provider status, model, token/request, retry/rate limit.
3. Nếu `retrieval` tăng: kiểm tra vector DB latency, DB connection pool, index size, filter.
4. Nếu `rerank` tăng: kiểm tra candidate count, reranker model, CPU/GPU queue.
5. Nếu `context_build` tăng: kiểm tra chunk count, tokenizer, document metadata.
6. Rollback prompt/model/index nếu spike gắn với version mới.

### 10.2 Cost Spike

1. So sánh token/request theo prompt version và route.
2. Kiểm tra context truncation và selected chunk count.
3. Kiểm tra model router có chọn model đắt bất thường không.
4. Kiểm tra retry storm hoặc timeout retry.
5. Kiểm tra traffic theo tenant/feature.
6. Tạm bật budget guardrail hoặc model fallback nếu cần.

### 10.3 Citation Failure Spike

1. Lọc trace có `citation_valid=false`.
2. Kiểm tra selected chunk ids có chứa source được cite không.
3. Kiểm tra prompt version có thay đổi citation format không.
4. Kiểm tra parser citation có regression không.
5. Kiểm tra index version và metadata `source_id/chunk_id`.
6. Thêm case vào golden set trước khi fix.

### 10.4 Negative Feedback Spike

1. Join feedback với trace theo `trace_id`.
2. Phân loại reason: wrong answer, wrong source, missing context, too slow, unsafe.
3. Với wrong source: xem retrieval/rerank/citation.
4. Với missing context: xem ingestion/index/ACL/chunking.
5. Với too slow: xem TTFT và stage latency.
6. Tạo regression set từ các trace đã triage.

## 11. Release Checklist

- [ ] Có dashboard staging và production.
- [ ] Alert có owner và runbook.
- [ ] Prompt/model/index version xuất hiện trong trace.
- [ ] Redaction tests pass.
- [ ] Không có Prometheus high-cardinality labels.
- [ ] Feedback endpoint hoạt động và join được với trace.
- [ ] Golden set chạy trước release.
- [ ] Release note có thay đổi prompt/model/index.
- [ ] Có rollback plan cho prompt/model/index.
- [ ] Cost budget và rate limit đã cấu hình.

## 12. Nguồn Chính Thức Nên Đọc

- OpenTelemetry documentation: https://opentelemetry.io/docs/
- OpenTelemetry Python: https://opentelemetry-python.readthedocs.io/
- Prometheus Python client: https://github.com/prometheus/client_python
- Prometheus documentation: https://prometheus.io/docs/
- Grafana documentation: https://grafana.com/docs/
- Langfuse documentation: https://langfuse.com/docs
- LangSmith documentation: https://docs.smith.langchain.com/
- Elastic Observability: https://www.elastic.co/observability
- OpenSearch Observability: https://opensearch.org/docs/latest/observing-your-data/
