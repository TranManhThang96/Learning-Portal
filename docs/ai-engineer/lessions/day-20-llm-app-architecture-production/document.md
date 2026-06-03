# Day 20 Document: Production Reference

## 1. Architecture Decision Template

Dùng template này khi thiết kế hoặc review một LLM feature trước khi đưa vào production.

```markdown
# LLM Architecture Decision

## Context

- Feature:
- Owner:
- Users:
- Tenant tiers:
- Data sensitivity:
- Expected traffic:
- p95 latency target:
- Monthly cost budget:

## Task profile

- Task type: chat / extraction / classification / reasoning / RAG / agent
- Input size:
- Output size:
- Requires tool calling:
- Requires structured output:
- Realtime or async:

## Prompt and schema

- Prompt ID:
- Prompt version:
- Schema version:
- Golden set:
- Eval metric:
- Rollback prompt version:

## Model routing

- Primary model:
- Fallback model:
- Local or hosted:
- Routing signals:
- Tenant restrictions:
- Data policy:

## Reliability

- API deadline:
- Provider timeout:
- Max retry attempts:
- Backoff:
- Fallback condition:
- Circuit breaker:
- Queue/deadline:

## Multi-tenancy

- Tenant source:
- Cache namespace:
- Quota policy:
- Tool permission:
- Audit partition:

## Cost controls

- Max input tokens:
- Max output tokens:
- Budget per tenant:
- Alert threshold:
- Degrade behavior:

## Observability

- Metrics:
- Logs:
- Traces:
- Dashboard:
- Alerts:

## Production decision

- Can be used in production:
- Required conditions:
- Known risks:
- Rollback plan:
- Final decision:
```

## 2. Component Responsibility Matrix

| Component | Must do | Must not do |
|---|---|---|
| API Gateway | Auth, request size, tenant resolution, coarse rate limit | Build prompt hoặc gọi provider trực tiếp nếu business policy phức tạp |
| Orchestrator | Enforce prompt/model/cache/quota/retry/fallback policy | Bỏ qua tenant context hoặc log raw PII mặc định |
| Prompt Registry | Version, owner, changelog, eval metadata | Lưu prompt vô danh không rollback được |
| Model Router | Chọn model theo task, tier, SLO, cost, policy | Chọn model hardcode trong từng endpoint |
| Provider Adapter | Chuẩn hóa SDK, error, timeout, usage | Expose provider-specific detail ra business layer |
| Cache | Namespace theo tenant, version, permission | Cache response sensitive mà thiếu ACL |
| Audit Log | Ghi metadata truy vết và policy decision | Dùng thay thế metrics hoặc trace |
| Observability | Đo latency, token, cost, retry, fallback, cache hit | Chỉ log text response và coi là đủ |

## 3. Prompt Registry Checklist

- Có `prompt_id` ổn định.
- Có `version` theo semantic hoặc incremental version.
- Có owner/team.
- Có expected input variables.
- Có output schema version nếu dùng structured output.
- Có compatible models.
- Có eval score trên golden set.
- Có changelog ngắn.
- Có rollout status.
- Có rollback version.
- Cache key và trace log có prompt metadata.

## 4. Model Router Policy Example

```yaml
models:
  fast_extractor:
    provider: mock_a
    model_id: fast-extract-v1
    max_output_tokens: 512
    cost_per_1k_tokens_usd: 0.0002
  strong_reasoner:
    provider: mock_b
    model_id: strong-reason-v1
    max_output_tokens: 2048
    cost_per_1k_tokens_usd: 0.0030
  fallback_balanced:
    provider: mock_c
    model_id: fallback-balanced-v1
    max_output_tokens: 1024
    cost_per_1k_tokens_usd: 0.0010

routing:
  extract:
    primary: fast_extractor
    fallback: fallback_balanced
  reasoning:
    primary: strong_reasoner
    fallback: fallback_balanced
  chat:
    primary: fallback_balanced
    fallback: fast_extractor

tenant_tiers:
  free:
    allowed_models: [fast_extractor]
    daily_budget_usd: 1
  pro:
    allowed_models: [fast_extractor, fallback_balanced]
    daily_budget_usd: 20
  enterprise:
    allowed_models: [fast_extractor, fallback_balanced, strong_reasoner]
    daily_budget_usd: 500
```

Trong production thật, policy này thường nằm trong config service hoặc database có audit trail, không hardcode tùy tiện.

## 5. Reliability Defaults

| Setting | Default gợi ý | Lý do |
|---|---:|---|
| API deadline realtime | 5-10s | Tránh request treo quá lâu |
| Provider timeout | 2-6s | Nhỏ hơn API deadline để còn fallback |
| Retry attempts | 1-2 | Retry nhiều làm tăng p95 và cost |
| Backoff | 100-500ms + jitter | Giảm thundering herd |
| Max output tokens | Theo task | Chặn cost spike và latency spike |
| Queue deadline | Theo business SLA | Job quá deadline nên fail/degrade |
| Circuit open threshold | 5-10 lỗi liên tiếp | Tránh gọi provider đang lỗi liên tục |

Retry nên áp dụng cho transient errors. Không retry blindly với validation error, policy block hoặc tool side effect thiếu idempotency.

## 6. Cache Key Reference

Exact prompt cache key nên có đủ context:

```text
sha256(
  tenant_id
  + user_permission_hash
  + prompt_id
  + prompt_version
  + schema_version
  + model_id
  + task
  + normalized_input
)
```

Không nên dùng:

```text
sha256(user_message)
```

Vì key đó có thể leak giữa tenant, sai prompt version, sai model hoặc sai permission.

## 7. Audit Event Schema

```json
{
  "event_type": "llm_request_completed",
  "trace_id": "uuid",
  "tenant_id": "tenant_pro",
  "user_id_hash": "sha256-prefix",
  "task": "extract",
  "prompt_id": "support_triage",
  "prompt_version": "v1",
  "schema_version": "ticket_triage.v1",
  "provider": "mock-fast",
  "model": "fast-extract-v1",
  "cache_hit": false,
  "retry_count": 1,
  "fallback_used": false,
  "input_tokens": 128,
  "output_tokens": 64,
  "estimated_cost_usd": 0.00004,
  "latency_ms": 421.7,
  "policy_decision": "allow",
  "error_code": null
}
```

Audit log nên append-only. Nếu cần xóa dữ liệu theo policy privacy, nên thiết kế retention và redaction rõ từ đầu.

## 8. Metrics Checklist

- `llm_requests_total{tenant_tier, task, provider, model, status}`.
- `llm_latency_ms{task, provider, model}`.
- `llm_provider_errors_total{provider, error_type}`.
- `llm_retries_total{provider, task}`.
- `llm_fallbacks_total{task, from_model, to_model}`.
- `llm_cache_hits_total{task, cache_type}`.
- `llm_input_tokens_total{tenant_id, task, model}`.
- `llm_output_tokens_total{tenant_id, task, model}`.
- `llm_estimated_cost_usd_total{tenant_id, task, model}`.
- `llm_quota_rejections_total{tenant_id, reason}`.

Nếu dùng OpenTelemetry, nên tạo span riêng cho `prompt.build`, `cache.lookup`, `provider.generate`, `tool.call`, `output.validate` và `audit.write`.

## 9. Security Checklist

- Secrets nằm trong secret manager hoặc environment, không hardcode.
- API key provider có scope và rotation plan.
- Không log raw prompt/response mặc định.
- Có PII redaction hoặc data classification.
- Prompt injection được xử lý ở policy/tool layer, không chỉ bằng prompt.
- Tool allowlist rõ ràng.
- Tool write operation có idempotency key.
- Tool service check tenant permission.
- Cache namespace theo tenant.
- Audit log có access control và retention.
- Provider data retention policy được review.

## 10. Production Readiness Rubric

| Mức | Mô tả | Dùng production? |
|---|---|---|
| Level 0 | Endpoint gọi SDK provider trực tiếp, không timeout/quota/audit | Không |
| Level 1 | Có timeout, schema validation, basic logging | Chỉ internal low-risk |
| Level 2 | Có orchestrator, prompt version, quota, cache an toàn, retry/fallback | Có thể production nhỏ |
| Level 3 | Có observability đầy đủ, golden set, canary, rollback, cost dashboard | Production tốt |
| Level 4 | Multi-provider/local fallback, circuit breaker, tenant budgets, incident runbook | Production enterprise |

## 11. Review Findings Cho Bản Day 20 Cũ

- Nội dung tiếng Việt không dấu, chưa đạt yêu cầu readability của khóa học.
- File còn phẳng, chưa tách `lession.md`, `document.md`, `exercise.md`.
- Có skeleton FastAPI nhưng chỉ nằm trong markdown, chưa có script chạy trực tiếp.
- Chưa giải thích đủ khác biệt giữa orchestrator và gateway.
- Chưa đủ checklist production readiness, cost controls, tenant quota và observability metrics.
- Chưa có exercise step-by-step để người học tự kiểm chứng retry, timeout, fallback, cache hit, audit log và quota.
- Chưa trả lời đủ rõ điều kiện "dùng được trong production không".
