# Exercise: Thiết Kế Cost Plan Cho RAG App Day 40

## Mục tiêu

Bạn sẽ thiết kế một cost plan gần production cho RAG app Day 40. Bài tập không yêu cầu gọi provider thật, nhưng phải có số liệu giả định rõ, công thức rõ, trade-off rõ và production readiness answer rõ.

Thời lượng đề xuất:

- Bản tối thiểu: 60-90 phút.
- Bản tốt cho portfolio: 3-4 giờ.
- Bản gần production: 1 ngày, có script đọc trace logs và report.

## 0. Acceptance criteria

Hoàn thành bài tập khi bạn có:

- [ ] Bảng estimate cho 1k, 10k và 100k requests/day.
- [ ] Cost model có input tokens, cached input tokens, output tokens, embedding, rerank, retry, infra và observability.
- [ ] Token budget cho `/query`, `/eval/run`, `/documents/ingest`.
- [ ] Thiết kế prompt caching và semantic caching với Redis.
- [ ] Ít nhất 3 model routing rules.
- [ ] Thiết kế context compression/chunk pruning.
- [ ] Kế hoạch dùng Batch API cho offline workload.
- [ ] Distillation overview: khi nào đáng làm, khi nào không.
- [ ] Budget/quota/degrade mode.
- [ ] Pseudo-code hoặc script tính cost từ trace logs.
- [ ] PR note có before/after estimate, risk, rollout và rollback.
- [ ] Trả lời: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## 1. Setup giả định

Giả định traffic ban đầu:

```text
1,000 requests/day
70% simple FAQ
25% normal RAG
5% complex RAG
30 eval questions/day
```

Request profile:

| Request type | Prompt tokens | Cached prompt tokens | Output tokens | Embedding tokens | Rerank units | Cache hit rate | Retry rate | Model |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| simple_faq | 1,800 | 900 | 220 | 24 | 8 | 35% | 1% | llm-small |
| normal_rag | 4,200 | 1,800 | 520 | 32 | 24 | 5% | 2% | llm-medium |
| complex_rag | 7,800 | 2,500 | 900 | 48 | 36 | 0% | 3% | llm-strong |
| eval | 3,800 | 1,600 | 350 | 32 | 24 | 0% | 0% | llm-medium |

Placeholder pricing để làm bài:

```text
llm-small:  input 0.15 / 1M, cached input 0.015 / 1M, output 0.60 / 1M
llm-medium: input 0.50 / 1M, cached input 0.050 / 1M, output 2.00 / 1M
llm-strong: input 2.00 / 1M, cached input 0.200 / 1M, output 8.00 / 1M
embedding-small: 0.02 / 1M tokens
reranker-base: 0.08 / 1000 units
fixed infra: 15 USD/day at 10k requests/day baseline
```

Các số trên là giả định học tập. Khi làm production thật, thay bằng pricing hiện tại của provider.

## 2. Bài 1: Tính baseline cost

Tạo bảng:

```csv
scenario,request_type,requests_per_day,prompt_tokens,cached_prompt_tokens,output_tokens,embedding_tokens,rerank_units,semantic_cache_hit_rate,retry_rate,model,cost_per_request,cost_per_day
1k,simple_faq,700,1800,900,220,24,8,0.35,0.01,llm-small,,
1k,normal_rag,250,4200,1800,520,32,24,0.05,0.02,llm-medium,,
1k,complex_rag,50,7800,2500,900,48,36,0.00,0.03,llm-strong,,
1k,eval,30,3800,1600,350,32,24,0.00,0.00,llm-medium,,
```

Công thức cho non-cache request:

```text
non_cached_input_tokens = prompt_tokens - cached_prompt_tokens

llm_cost =
  non_cached_input_tokens / 1_000_000 * input_price
+ cached_prompt_tokens / 1_000_000 * cached_input_price
+ output_tokens / 1_000_000 * output_price

embedding_cost = embedding_tokens / 1_000_000 * embedding_price
rerank_cost = rerank_units / 1000 * reranker_price
infra_cost = fixed_infra_daily / expected_requests_per_day

raw_cost_per_request = llm_cost + embedding_cost + rerank_cost + infra_cost
effective_cost_per_request =
  raw_cost_per_request * (1 - semantic_cache_hit_rate)
+ cache_lookup_cost_estimate
+ raw_cost_per_request * retry_rate
```

Dòng retry ở trên là approximation cho capacity planning, giả định mỗi retry tốn gần một request đầy đủ. Với trace/billing thật, phải cộng usage của từng attempt; không nhân lại nếu `usage` đã là tổng mọi attempt.

Yêu cầu:

- Tính `cost_per_request` và `cost_per_day` cho scenario 1k.
- Nhân traffic để có scenario 10k và 100k.
- Tách eval/offline cost khỏi realtime cost.
- Ghi rõ assumption cho cache lookup cost. Nếu bỏ qua, ghi `0` và giải thích.

## 3. Bài 2: Phân tích cost driver

Từ bảng baseline, trả lời:

```text
1. Request type nào tốn nhiều nhất mỗi ngày?
2. Stage nào tốn nhiều nhất: input, output, rerank, infra, retry?
3. Nếu traffic tăng 10 lần, cost có tăng tuyến tính không? Vì sao?
4. Cache hit rate cần đạt bao nhiêu để giảm 20% cost simple FAQ?
5. Retry rate tăng từ 2% lên 8% ảnh hưởng cost/month thế nào?
```

Deliverable: 1 bảng top cost drivers và 3 nhận xét ngắn.

## 4. Bài 3: Thiết kế token budget

Thiết kế budget cho:

- `/query` simple FAQ.
- `/query` normal RAG.
- `/query` complex RAG.
- `/eval/run`.
- `/documents/ingest`.

Template:

```yaml
policies:
  simple_faq:
    max_query_tokens:
    max_context_chunks:
    max_context_tokens:
    max_output_tokens:
    max_retries:
    allowed_models:

  normal_rag:
    max_query_tokens:
    max_context_chunks:
    max_context_tokens:
    max_output_tokens:
    max_retries:
    allowed_models:

  documents_ingest:
    max_document_tokens_per_file:
    max_files_per_job:
    max_embedding_batch_tokens:
    max_retries:
    force_batch_when_tokens_over:
```

Yêu cầu:

- Ghi rõ policy nào dành cho free/paid/enterprise tier.
- Mô tả backend enforce budget ở stage nào.
- Mô tả UX khi request bị reject vì vượt budget.

## 5. Bài 4: Prompt caching plan

Thiết kế prompt để tăng cache hit:

```text
Static prefix:
- system instruction
- developer instruction
- response schema
- citation rules
- stable examples

Dynamic suffix:
- tenant-specific context
- retrieved chunks
- user question
- current timestamp nếu thật sự cần
```

Yêu cầu:

- Xác định phần nào của prompt có thể cache.
- Xác định field cần log: `prompt_tokens`, `cached_prompt_tokens`, `cache_key`, `prompt_version`.
- Nêu 3 lý do prompt cache hit thấp.
- Nêu cách rollback nếu prompt caching làm latency/cost không như kỳ vọng.

Trade-off cần trả lời:

```text
Prompt caching có giảm output token cost không?
Nếu prompt version đổi mỗi deploy thì chuyện gì xảy ra?
Với dữ liệu multi-tenant, phần nào không nên xem là cache prefix dùng chung?
```

## 6. Bài 5: Semantic caching với Redis

Thiết kế semantic cache cho simple FAQ.

Key format bắt buộc có:

- `tenant_id`
- `permission_hash`
- `corpus_version`
- `prompt_version`
- `schema_version`
- `embedding_model`
- `cache_hash`

Template:

```text
sc:{tenant_id}:{permission_hash}:{corpus_version}:{prompt_version}:{schema_version}:{embedding_model}:{cache_hash}
```

Yêu cầu:

- Chọn similarity threshold, ví dụ `0.92`, và giải thích.
- Chọn TTL, ví dụ 7 ngày, và giải thích.
- Thiết kế invalidation khi tài liệu thay đổi.
- Thiết kế metric false hit.
- Nêu loại câu hỏi không được cache.

Pseudo-code cần viết:

```python
def should_use_semantic_cache(question, auth, request_type, risk_level):
    if request_type not in {"simple_faq", "normal_rag"}:
        return False
    if risk_level in {"legal", "finance", "medical", "personal_data"}:
        return False
    if auth.permission_hash is None:
        return False
    if len(question) > 500:
        return False
    return True

def build_cache_scope(auth, versions, embedding_model):
    return {
        "tenant_id": auth.tenant_id,
        "permission_hash": auth.permission_hash,
        "corpus_version": versions.corpus,
        "prompt_version": versions.prompt,
        "schema_version": versions.answer_schema,
        "embedding_model": embedding_model,
    }

def lookup_semantic_cache(question, scope):
    normalized = normalize_question(question)
    embedding = embed_query(normalized, model=scope["embedding_model"])
    hits = redis_vector_search(embedding, scope=scope, top_k=3)
    best = hits[0] if hits else None
    if best and best.score >= 0.92:
        return best.payload
    return None

def store_semantic_cache(question, answer, citations, scope):
    if not citations:
        return
    payload = {
        "question": normalize_question(question),
        "answer": answer,
        "citations": citations,
        "scope": scope,
        "ttl_seconds": 7 * 24 * 60 * 60,
    }
    redis_store_answer(payload)
```

## 7. Bài 6: Model routing rules

Thiết kế ít nhất 3 rules:

Ví dụ:

```yaml
routes:
  - name: simple_faq_small_model
    condition: request_type == "simple_faq" and risk_level == "low"
    model: llm-small

  - name: complex_policy_strong_model
    condition: request_type == "complex_rag" and user_tier in ["paid", "enterprise"]
    model: llm-strong

  - name: budget_conserve_mode
    condition: tenant_budget_state in ["conserve", "degraded"]
    model: llm-small
```

Yêu cầu:

- Mỗi route có `route_reason`.
- Mỗi route có metric kiểm chứng.
- Mỗi route có fallback.
- Nêu risk nếu route nhầm sang model nhỏ.

Metrics gợi ý:

- Answer acceptance rate.
- Citation correctness.
- No-answer accuracy.
- Schema success rate.
- Cost/request.
- p95 latency.

## 8. Bài 7: Context compression và chunk pruning

Thiết kế pipeline giảm context:

```text
retrieve dense 50 + sparse 50
  -> merge RRF
  -> rerank top 24
  -> dedupe document/heading
  -> extract relevant spans
  -> enforce context budget
  -> build prompt
```

Yêu cầu:

- Chọn `context_top_k` cho simple, normal và complex.
- Chọn max tokens/span.
- Nêu khi nào dùng compression bằng small model.
- Nêu cách giữ citation correctness sau compression.
- Nêu metric regression cần chạy.

Trade-off cần trả lời:

```text
Giảm top_k từ 8 xuống 4 có thể làm cost giảm nhưng rủi ro gì?
Compression có thể làm citation sai như thế nào?
Với HR/legal/policy assistant, nên ưu tiên raw evidence span hay summary?
```

## 9. Bài 8: Batch API và offline workload

Liệt kê workload nào nên chuyển sang batch:

- Nightly eval.
- Re-embedding tài liệu.
- Synthetic question generation.
- Backfill classification.
- Large summarization offline.

Thiết kế queue:

```text
realtime_queue
  - user-facing query
  - strict latency SLO
  - small retry budget

offline_batch_queue
  - eval/reindex/synthetic
  - separate quota
  - resumable
  - lower priority
```

Yêu cầu:

- Ước lượng cost eval nếu chạy sync mỗi ngày.
- Ước lượng cost eval nếu chạy batch với multiplier giả định.
- Nêu vì sao batch không dùng cho chat realtime.
- Nêu cách tránh offline job ăn hết quota realtime.

## 10. Bài 9: Distillation overview

Viết một đoạn thiết kế distillation cho một task nhỏ trong RAG app:

Gợi ý chọn một trong các task:

- Intent classification.
- Query complexity classifier.
- No-answer detector.
- JSON extraction.
- Query rewrite.

Template:

```text
Task:
Teacher model:
Student model:
Training data source:
Label quality control:
Eval metrics:
Rollout plan:
Rollback plan:
Expected cost saving:
Risks:
```

Yêu cầu:

- Nêu vì sao chưa nên distill toàn bộ answer generator nếu citation correctness là critical.
- Nêu điều kiện traffic/eval để distillation đáng làm.

## 11. Bài 10: Budget/quota/degrade mode

Thiết kế budget policy:

```yaml
tenant_budget:
  monthly_usd: 500
  states:
    normal:
      until_percent: 70
    watch:
      until_percent: 85
      actions: ["alert_owner"]
    conserve:
      until_percent: 95
      actions: ["concise_mode", "reduce_context_top_k"]
    degraded:
      until_percent: 100
      actions: ["small_model_for_simple_tasks", "pause_offline_jobs"]
    hard_stop:
      actions: ["reject_non_critical_requests", "admin_override_required"]
```

Yêu cầu:

- Tách monthly budget, daily budget và per-request budget.
- Tách quota cho realtime và offline.
- Nêu thứ tự degrade.
- Nêu hành vi user thấy khi bị degrade.
- Nêu hành vi admin thấy trong dashboard.

Không được degrade bằng cách:

- Bỏ ACL filter.
- Bỏ citation validation ở domain cần citation.
- Trả answer không có context.
- Chạy model chưa qua eval.

## 12. Bài 11: Script tính cost từ trace logs

Tạo hoặc phác thảo script đọc JSONL:

```bash
python scripts/calc_cost_from_traces.py \
  --traces data/traces/day44-query-traces.jsonl \
  --pricing config/pricing.config.json \
  --out reports/cost-summary.csv
```

Input trace tối thiểu:

```json
{"trace_id":"tr_001","tenant_id":"tenant_a","feature":"rag_query","request_type":"normal_rag","pricing_version":"provider-pricing-2026-05-10","usage_includes_retries":true,"models":{"generator":"llm-medium","embedding":"embedding-small","reranker":"reranker-base"},"usage":{"prompt_tokens":4200,"cached_prompt_tokens":1800,"completion_tokens":520,"embedding_tokens":32,"rerank_units":24},"cache":{"semantic_cache_hit":false},"retry":{"count":0}}
```

Output CSV tối thiểu:

```csv
tenant_id,feature,request_type,generator_model,requests,cost_total_usd,cost_per_request_usd,avg_prompt_tokens,cached_token_ratio,semantic_cache_hit_rate,retry_rate
tenant_a,rag_query,normal_rag,llm-medium,250,0.82,0.00328,4200,0.428,0.05,0.02
```

Yêu cầu script:

- Không double-count cached prompt tokens.
- Tính semantic cache hit cost khác non-cache request.
- Fail nếu `retry.count > 0` nhưng trace không xác nhận usage đã cộng dồn mọi attempt.
- Group by tenant/feature/request_type/model.
- Fail nếu thiếu pricing cho model.
- Có test case cho retry và batch multiplier.

## 13. Bài 12: Viết optimization plan

Chọn 3 optimization và viết before/after estimate.

Gợi ý:

1. Semantic cache cho simple FAQ.
2. Giảm context normal RAG từ 8 chunks xuống 5 chunks sau rerank.
3. Model routing query rewrite/FAQ sang small model.
4. Chạy eval bằng Batch API.
5. Giảm max output tokens và thêm UX detailed mode.

Template:

```markdown
## Optimization 1

### Change

### Expected cost saving

### Quality risk

### Metrics to monitor

### Rollback
```

Yêu cầu:

- Mỗi optimization có trade-off.
- Mỗi optimization có metric.
- Mỗi optimization có rollback.
- Không chọn optimization phá security boundary.

## 14. Bài 13: Production readiness answer

Viết câu trả lời cuối trong README/PR:

```text
Dùng được trong production không?

Có, nếu:
- trace log đã có token/model/cache/retry/cost theo request;
- token budget được enforce ở backend;
- cache scoped theo tenant, ACL, corpus version và prompt version;
- model routing có eval per route;
- context pruning có regression eval cho citation/no-answer;
- offline batch có quota riêng;
- budget alert, degrade mode và rollback flag đã sẵn sàng.

Chưa nên production nếu:
- chỉ có estimate thủ công mà không có trace thật;
- semantic cache chưa có permission boundary;
- chưa có quality gate sau khi giảm context/model;
- không có hard stop khi retry hoặc batch job gây cost spike.
```

## 15. Nộp bài

Deliverables:

- `reports/cost-estimate.md` hoặc spreadsheet export.
- `config/pricing.config.json`.
- `config/token-budget.policy.yaml`.
- `config/model-routing.policy.yaml`.
- `docs/semantic-cache-design.md`.
- `scripts/calc_cost_from_traces.py` hoặc pseudo-code tương đương.
- `reports/cost-optimization-pr-note.md`.

Checklist tự review:

- [ ] Có số liệu cho 1k/10k/100k requests/day.
- [ ] Có cost/request và cost/month.
- [ ] Có ít nhất 3 cách giảm cost.
- [ ] Có trade-off quality/latency/security cho từng cách.
- [ ] Có best solution theo context.
- [ ] Có production readiness answer rõ.
