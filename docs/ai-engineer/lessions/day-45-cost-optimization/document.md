# Document: Cost Optimization Templates, Runbook Và Pseudo-code

## 1. Mental model nhanh

Một cost plan đáng tin phải trả lời được 5 câu:

```text
1. Mỗi request tốn bao nhiêu tiền?
2. Cost đến từ stage nào?
3. Giới hạn token/quota nằm ở đâu và enforce như thế nào?
4. Khi vượt budget, hệ thống degrade ra sao?
5. Quality có còn đạt release gate sau tối ưu không?
```

Không hardcode bảng giá vào business logic. Giá model, discount, cached token price và Batch API behavior thay đổi theo provider. Production nên dùng `pricing_config` có version, effective date và dashboard đối chiếu billing thật.

## 2. Pricing config template

Ví dụ `pricing.config.json`:

```json
{
  "pricing_version": "provider-pricing-2026-05-10",
  "currency": "USD",
  "token_unit": 1000000,
  "batch_multiplier": "0.5",
  "llm_models": {
    "llm-small": {
      "input_per_1m": "0.1500",
      "cached_input_per_1m": "0.0150",
      "output_per_1m": "0.6000",
      "reasoning_per_1m": "0.6000"
    },
    "llm-medium": {
      "input_per_1m": "0.5000",
      "cached_input_per_1m": "0.0500",
      "output_per_1m": "2.0000",
      "reasoning_per_1m": "2.0000"
    },
    "llm-strong": {
      "input_per_1m": "2.0000",
      "cached_input_per_1m": "0.2000",
      "output_per_1m": "8.0000",
      "reasoning_per_1m": "8.0000"
    }
  },
  "embedding_models": {
    "embedding-small": {
      "input_per_1m": "0.0200"
    }
  },
  "rerankers": {
    "reranker-base": {
      "per_1000_units": "0.0800"
    }
  },
  "tool_calls": {
    "web_search": {
      "per_call": "0.0100"
    }
  },
  "infra_allocation": {
    "fixed_daily_usd": "15.0000",
    "expected_requests_per_day": 10000
  }
}
```

Ghi chú:

- Các số trên là placeholder để làm bài, không phải giá thật.
- `cached_input_per_1m` phải tách riêng với non-cached input.
- Nếu provider không có reasoning tokens hoặc cached input price, để `0` hoặc bằng input price theo contract của provider.
- Nếu dùng Batch API, có thể thêm `batch_multiplier`, ví dụ `"batch_multiplier": "0.5"`, nhưng phải lấy từ provider pricing hiện tại.

## 3. Trace log schema

Trace log nên là JSONL, mỗi dòng là một request hoặc một job item:

```json
{
  "trace_id": "tr_001",
  "timestamp": "2026-05-10T10:30:00Z",
  "tenant_id": "tenant_a",
  "user_id_hash": "sha256:...",
  "feature": "rag_query",
  "request_type": "normal_rag",
  "pipeline_version": "rag-cost-v2",
  "pricing_version": "provider-pricing-2026-05-10",
  "prompt_version": "rag-answer.v4",
  "corpus_version": "policy-2026-05",
  "is_batch": false,
  "usage_includes_retries": true,
  "models": {
    "generator": "llm-medium",
    "embedding": "embedding-small",
    "reranker": "reranker-base"
  },
  "usage": {
    "prompt_tokens": 4200,
    "cached_prompt_tokens": 1800,
    "completion_tokens": 520,
    "reasoning_tokens": 0,
    "embedding_tokens": 32,
    "rerank_units": 24,
    "tool_calls": {
      "web_search": 0
    }
  },
  "cache": {
    "semantic_cache_hit": false,
    "prompt_cache_hit_tokens": 1800
  },
  "retry": {
    "count": 0,
    "reason": null
  },
  "latency_ms": {
    "total": 1810
  },
  "quality_signals": {
    "answer_status": "answered",
    "citation_valid": true
  }
}
```

Validation rules:

- `cached_prompt_tokens <= prompt_tokens`.
- `pricing_version` trong trace phải match config hoặc được map bằng compatibility table.
- `models.generator` bắt buộc nếu không phải semantic cache hit.
- Nếu `semantic_cache_hit=true`, generation tokens nên bằng `0` hoặc trace phải giải thích vì sao vẫn gọi LLM.
- Retry phải được log như cost thật. Nếu một trace đại diện logical request, `usage` phải cộng dồn mọi attempt và `usage_includes_retries=true`; lựa chọn tốt hơn là lưu thêm mảng attempt để audit.

## 4. Cost estimate table

CSV template:

```csv
request_type,requests_per_day,prompt_tokens,cached_prompt_tokens,completion_tokens,embedding_tokens,rerank_units,semantic_cache_hit_rate,retry_rate,model,cost_per_request_usd,cost_per_day_usd
simple_faq,700,1800,900,220,24,8,0.35,0.01,llm-small,,
normal_rag,250,4200,1800,520,32,24,0.05,0.02,llm-medium,,
complex_rag,50,7800,2500,900,48,36,0.00,0.03,llm-strong,,
eval,30,3800,1600,350,32,24,0.00,0.00,llm-medium,,
```

Nên tạo 3 sheet hoặc 3 scenario:

- 1k requests/day.
- 10k requests/day.
- 100k requests/day.

Mỗi scenario cần ghi rõ:

- Traffic mix.
- Cache hit rate giả định.
- Retry rate giả định.
- Model route ratio.
- Batch/offline jobs.
- Fixed infra allocation.
- Quality risk.

## 5. Token budget policy template

Ví dụ `token-budget.policy.yaml`:

```yaml
version: rag-token-budget-v2
defaults:
  max_retries: 1
  reject_when_question_tokens_over: true
  log_budget_decision: true

policies:
  simple_faq:
    max_query_tokens: 120
    max_context_chunks: 3
    max_context_tokens: 1800
    max_output_tokens: 250
    max_rerank_candidates: 12
    allowed_models: ["llm-small", "llm-medium"]

  normal_rag:
    max_query_tokens: 250
    max_context_chunks: 5
    max_context_tokens: 3500
    max_output_tokens: 600
    max_rerank_candidates: 24
    allowed_models: ["llm-medium", "llm-strong"]

  complex_rag:
    max_query_tokens: 500
    max_context_chunks: 8
    max_context_tokens: 7000
    max_output_tokens: 900
    max_rerank_candidates: 36
    allowed_models: ["llm-strong"]
    required_tiers: ["paid", "enterprise"]

  eval_run:
    max_query_tokens: 250
    max_context_chunks: 5
    max_context_tokens: 3500
    max_output_tokens: 400
    max_rerank_candidates: 24
    max_retries: 0
    force_batch_when_items_over: 100
```

Budget decision log:

```json
{
  "trace_id": "tr_001",
  "budget_policy": "normal_rag",
  "budget_version": "rag-token-budget-v2",
  "query_tokens": 84,
  "context_tokens_before_pruning": 6900,
  "context_tokens_after_pruning": 3380,
  "context_chunks_before": 12,
  "context_chunks_after": 5,
  "max_output_tokens": 600,
  "decision": "allowed"
}
```

## 6. Redis semantic cache template

Key format:

```text
sc:{tenant_id}:{permission_hash}:{corpus_version}:{prompt_version}:{schema_version}:{embedding_model}:{cache_hash}
```

Payload:

```json
{
  "cache_id": "sc:tenant_a:roles_employee:policy_2026_05:rag_v4:v1:embedding_small:abc123",
  "normalized_question": "ngay nghi phep nam full time",
  "answer": "Nhân viên full-time có 12 ngày nghỉ phép năm [S1].",
  "citations": [
    {
      "document_id": "doc_hr",
      "chunk_id": "tenant_a:doc_hr:v3:004",
      "source_id": "S1"
    }
  ],
  "source_chunk_hashes": ["sha256:..."],
  "quality": {
    "citation_valid": true,
    "answer_status": "answered"
  },
  "created_at": "2026-05-10T10:30:00Z",
  "ttl_seconds": 604800
}
```

Invalidation triggers:

- Document/corpus version thay đổi.
- Prompt/schema version thay đổi.
- ACL/role mapping thay đổi.
- Embedding model thay đổi.
- Citation validator phát hiện cached answer sai.
- User feedback negative có severity cao.

Metrics:

- `semantic_cache_hit_rate`.
- `semantic_cache_false_hit_rate`.
- `semantic_cache_saved_cost_usd`.
- `semantic_cache_p95_latency_ms`.
- `semantic_cache_entries_by_tenant`.

## 7. Model routing policy template

```yaml
version: rag-routing-v2

routes:
  - name: semantic_cache_hit
    when:
      semantic_cache_hit: true
    action:
      mode: cache_hit
      model: null

  - name: simple_faq_low_risk
    when:
      request_type: simple_faq
      risk_level: low
    action:
      mode: normal
      model: llm-small
      max_output_tokens: 250

  - name: high_risk_paid
    when:
      risk_level_in: ["legal", "finance", "policy"]
      user_tier_in: ["paid", "enterprise"]
      query_complexity_in: ["medium", "complex"]
    action:
      mode: normal
      model: llm-strong
      max_output_tokens: 900

  - name: conserve_budget
    when:
      tenant_budget_state_in: ["conserve", "degraded"]
    action:
      mode: degraded
      model: llm-small
      max_output_tokens: 350
      context_top_k_delta: -2

default:
  mode: normal
  model: llm-medium
  max_output_tokens: 600
```

Mỗi route cần:

- Eval set riêng hoặc tag riêng trong golden set.
- Alert nếu route ratio thay đổi bất thường.
- Rollback bằng config, không cần deploy code.
- `route_reason` trong trace.

## 8. Pseudo-code gần production: tính cost từ trace logs

Script dưới đây đọc trace JSONL, pricing config JSON và xuất summary CSV. Đây là pseudo-code gần production: dùng `Decimal`, validate field quan trọng, không double-count cached input tokens và gom nhóm theo tenant/feature/model/request type.

```python
#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


MILLION = Decimal("1000000")
THOUSAND = Decimal("1000")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def d(value, default="0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


@dataclass(frozen=True)
class CostBreakdown:
    llm_input: Decimal = Decimal("0")
    llm_cached_input: Decimal = Decimal("0")
    llm_output: Decimal = Decimal("0")
    llm_reasoning: Decimal = Decimal("0")
    embedding: Decimal = Decimal("0")
    rerank: Decimal = Decimal("0")
    tool: Decimal = Decimal("0")
    infra: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return (
            self.llm_input
            + self.llm_cached_input
            + self.llm_output
            + self.llm_reasoning
            + self.embedding
            + self.rerank
            + self.tool
            + self.infra
        )


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_no}: {exc}") from exc


def require(trace: dict, field: str):
    current = trace
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Missing required field {field} in trace {trace.get('trace_id')}")
        current = current[part]
    return current


def per_token_cost(tokens: Decimal, price_per_1m: Decimal, multiplier: Decimal) -> Decimal:
    return (tokens / MILLION) * price_per_1m * multiplier


def calculate_trace_cost(trace: dict, pricing: dict) -> CostBreakdown:
    usage = trace.get("usage", {})
    models = trace.get("models", {})

    trace_pricing_version = require(trace, "pricing_version")
    if trace_pricing_version != pricing.get("pricing_version"):
        raise ValueError(
            f"Pricing version mismatch in trace {trace.get('trace_id')}: "
            f"{trace_pricing_version} != {pricing.get('pricing_version')}"
        )

    retry_count = int(trace.get("retry", {}).get("count", 0) or 0)
    if retry_count > 0 and not trace.get("usage_includes_retries", False):
        raise ValueError(
            f"Trace {trace.get('trace_id')} has retries but usage does not include all attempts"
        )

    semantic_cache_hit = bool(trace.get("cache", {}).get("semantic_cache_hit", False))
    batch_multiplier = Decimal("1")
    if trace.get("is_batch"):
        batch_multiplier = d(pricing.get("batch_multiplier", "1"))

    infra = pricing.get("infra_allocation", {})
    expected_requests = d(infra.get("expected_requests_per_day", "0"))
    fixed_daily = d(infra.get("fixed_daily_usd", "0"))
    infra_per_request = Decimal("0") if expected_requests <= 0 else fixed_daily / expected_requests

    llm_input = Decimal("0")
    llm_cached_input = Decimal("0")
    llm_output = Decimal("0")
    llm_reasoning = Decimal("0")

    if not semantic_cache_hit:
        generator = require(trace, "models.generator")
        model_price = pricing["llm_models"][generator]

        prompt_tokens = d(usage.get("prompt_tokens"))
        cached_tokens = d(usage.get("cached_prompt_tokens"))
        if cached_tokens > prompt_tokens:
            raise ValueError(f"cached_prompt_tokens > prompt_tokens in trace {trace.get('trace_id')}")

        non_cached_tokens = prompt_tokens - cached_tokens
        completion_tokens = d(usage.get("completion_tokens"))
        reasoning_tokens = d(usage.get("reasoning_tokens"))

        llm_input = per_token_cost(
            non_cached_tokens,
            d(model_price.get("input_per_1m")),
            batch_multiplier,
        )
        llm_cached_input = per_token_cost(
            cached_tokens,
            d(model_price.get("cached_input_per_1m", model_price.get("input_per_1m"))),
            batch_multiplier,
        )
        llm_output = per_token_cost(
            completion_tokens,
            d(model_price.get("output_per_1m")),
            batch_multiplier,
        )
        llm_reasoning = per_token_cost(
            reasoning_tokens,
            d(model_price.get("reasoning_per_1m", model_price.get("output_per_1m"))),
            batch_multiplier,
        )

    embedding_cost = Decimal("0")
    embedding_model = models.get("embedding")
    if embedding_model and d(usage.get("embedding_tokens")) > 0:
        embedding_price = pricing["embedding_models"][embedding_model]
        embedding_cost = per_token_cost(
            d(usage.get("embedding_tokens")),
            d(embedding_price.get("input_per_1m")),
            batch_multiplier,
        )

    rerank_cost = Decimal("0")
    reranker = models.get("reranker")
    if reranker and d(usage.get("rerank_units")) > 0:
        reranker_price = pricing["rerankers"][reranker]
        rerank_cost = (d(usage.get("rerank_units")) / THOUSAND) * d(reranker_price.get("per_1000_units"))

    tool_cost = Decimal("0")
    for tool_name, count in usage.get("tool_calls", {}).items():
        tool_price = pricing.get("tool_calls", {}).get(tool_name)
        if not tool_price:
            raise ValueError(f"Missing pricing for tool call {tool_name}")
        tool_cost += d(count) * d(tool_price.get("per_call"))

    return CostBreakdown(
        llm_input=money(llm_input),
        llm_cached_input=money(llm_cached_input),
        llm_output=money(llm_output),
        llm_reasoning=money(llm_reasoning),
        embedding=money(embedding_cost),
        rerank=money(rerank_cost),
        tool=money(tool_cost),
        infra=money(infra_per_request),
    )


def group_key(trace: dict) -> tuple[str, str, str, str, str]:
    models = trace.get("models", {})
    return (
        trace.get("tenant_id", "unknown"),
        trace.get("feature", "unknown"),
        trace.get("request_type", "unknown"),
        models.get("generator", "cache_or_unknown"),
        trace.get("pricing_version", "unknown"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", required=True, type=Path)
    parser.add_argument("--pricing", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    pricing = load_json(args.pricing)
    summary = defaultdict(lambda: {
        "requests": 0,
        "prompt_tokens": Decimal("0"),
        "cached_prompt_tokens": Decimal("0"),
        "completion_tokens": Decimal("0"),
        "cost_total": Decimal("0"),
        "cost_llm_input": Decimal("0"),
        "cost_llm_cached_input": Decimal("0"),
        "cost_llm_output": Decimal("0"),
        "cost_embedding": Decimal("0"),
        "cost_rerank": Decimal("0"),
        "cost_tool": Decimal("0"),
        "cost_infra": Decimal("0"),
        "semantic_cache_hits": 0,
        "retries": 0,
    })

    for _, trace in iter_jsonl(args.traces):
        cost = calculate_trace_cost(trace, pricing)
        key = group_key(trace)
        row = summary[key]
        usage = trace.get("usage", {})

        row["requests"] += 1
        row["prompt_tokens"] += d(usage.get("prompt_tokens"))
        row["cached_prompt_tokens"] += d(usage.get("cached_prompt_tokens"))
        row["completion_tokens"] += d(usage.get("completion_tokens"))
        row["cost_total"] += cost.total
        row["cost_llm_input"] += cost.llm_input
        row["cost_llm_cached_input"] += cost.llm_cached_input
        row["cost_llm_output"] += cost.llm_output + cost.llm_reasoning
        row["cost_embedding"] += cost.embedding
        row["cost_rerank"] += cost.rerank
        row["cost_tool"] += cost.tool
        row["cost_infra"] += cost.infra
        row["semantic_cache_hits"] += int(bool(trace.get("cache", {}).get("semantic_cache_hit")))
        row["retries"] += int(trace.get("retry", {}).get("count", 0) or 0)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "tenant_id",
            "feature",
            "request_type",
            "generator_model",
            "pricing_version",
            "requests",
            "avg_prompt_tokens",
            "cached_token_ratio",
            "avg_completion_tokens",
            "semantic_cache_hit_rate",
            "retry_rate",
            "cost_total_usd",
            "cost_per_request_usd",
            "cost_llm_input_usd",
            "cost_llm_cached_input_usd",
            "cost_llm_output_usd",
            "cost_embedding_usd",
            "cost_rerank_usd",
            "cost_tool_usd",
            "cost_infra_usd",
        ])

        for key, row in sorted(summary.items()):
            requests = Decimal(row["requests"])
            prompt_tokens = row["prompt_tokens"]
            cached_tokens = row["cached_prompt_tokens"]
            completion_tokens = row["completion_tokens"]
            cost_total = money(row["cost_total"])

            cached_ratio = Decimal("0") if prompt_tokens == 0 else cached_tokens / prompt_tokens
            writer.writerow([
                *key,
                row["requests"],
                money(prompt_tokens / requests),
                money(cached_ratio),
                money(completion_tokens / requests),
                money(Decimal(row["semantic_cache_hits"]) / requests),
                money(Decimal(row["retries"]) / requests),
                cost_total,
                money(cost_total / requests),
                money(row["cost_llm_input"]),
                money(row["cost_llm_cached_input"]),
                money(row["cost_llm_output"]),
                money(row["cost_embedding"]),
                money(row["cost_rerank"]),
                money(row["cost_tool"]),
                money(row["cost_infra"]),
            ])


if __name__ == "__main__":
    main()
```

Chạy script nếu lưu thành `scripts/calc_cost_from_traces.py`:

```bash
python scripts/calc_cost_from_traces.py \
  --traces data/traces/day44-query-traces.jsonl \
  --pricing config/pricing.config.json \
  --out reports/cost-summary.csv
```

Production hardening cần thêm:

- Map `pricing_version` cũ sang bảng giá lịch sử.
- Đối chiếu billing provider mỗi ngày.
- Alert nếu trace thiếu usage hoặc token bất thường.
- Unit test cho cached token, semantic cache hit, batch multiplier và retry.
- Không để script silently bỏ qua trace lỗi.

## 9. Cost dashboard

Dashboard tối thiểu:

| Chart | Group by | Mục đích |
|---|---|---|
| Cost/day | tenant, feature | phát hiện tenant/feature đốt tiền |
| Cost/request p50/p95 | request_type | biết tail cost |
| Token/request p50/p95 | model, prompt_version | phát hiện prompt/context phình |
| Cache hit rate | tenant, cache type | đánh giá prompt/semantic cache |
| Retry rate | endpoint, model | phát hiện schema/prompt/provider lỗi |
| Route ratio | route_name, model | phát hiện router đổi hành vi |
| Eval cost | eval suite, model | kiểm soát offline workload |

Alert gợi ý:

- Daily cost vượt forecast 20%.
- p95 prompt tokens tăng 30% sau deploy.
- Semantic cache false hit > 0.5% với domain policy.
- Retry rate > 3%.
- Eval/batch job dùng quá 20% daily budget.
- Tenant vượt 85% monthly budget.

## 10. Runbook: cost spike

Khi cost tăng bất thường:

```text
1. Xác nhận spike
   So sánh billing provider, internal cost summary và request volume.

2. Xác định phạm vi
   Group by tenant, feature, endpoint, model, prompt_version, route_name.

3. Kiểm tra nguyên nhân phổ biến
   - Traffic tăng thật.
   - Retry loop.
   - Prompt/context dài hơn sau deploy.
   - Cache hit giảm.
   - Router route nhiều request sang model mạnh.
   - Eval/batch job chạy nhầm realtime quota.

4. Bật mitigation
   - Disable job/offline workload.
   - Bật concise mode.
   - Giảm max output tokens.
   - Giảm context_top_k.
   - Route simple task sang small model.
   - Rate limit tenant/user gây spike.

5. Verify quality
   Chạy smoke eval cho citation/no-answer trước khi giữ mitigation lâu dài.

6. Postmortem
   Cập nhật budget policy, alert threshold, test và dashboard.
```

Rollback levers nên là config/feature flag:

- `semantic_cache_enabled=false`
- `model_router_version=previous`
- `context_budget_version=previous`
- `eval_jobs_paused=true`
- `complex_mode_enabled=false`

## 11. PR note template

```markdown
## Cost Optimization PR

### Problem
- Current cost/request:
- Current cost/day:
- Main driver:

### Change
- Technique:
- Affected endpoint/tenant:
- Config changed:

### Before/After estimate
| Metric | Before | After | Expected delta |
|---|---:|---:|---:|
| Cost/request | | | |
| p95 latency | | | |
| Prompt tokens/request | | | |
| Output tokens/request | | | |
| Cache hit rate | | | |

### Quality guardrail
- Golden set:
- Retrieval recall:
- Citation correctness:
- No-answer accuracy:
- Schema success:

### Risk
- Quality risk:
- Security/privacy risk:
- Operational risk:

### Rollout
- Canary scope:
- Monitoring window:
- Alert:

### Rollback
- Config flag:
- Owner:
- Time to rollback:

### Production readiness answer
Có/không dùng được trong production? Điều kiện còn thiếu là gì?
```

## 12. Tài liệu tham khảo provider-specific

- OpenAI Prompt Caching docs: https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI Batch API docs: https://developers.openai.com/api/docs/guides/batch

Các link trên dùng để kiểm tra behavior hiện tại của OpenAI. Khi triển khai thật, vẫn cần đối chiếu provider đang dùng, model cụ thể, data retention policy và pricing page tại thời điểm release.
