# Day 45: Cost Optimization Cho LLM/RAG Production

## 1. Mục tiêu bài học

Sau Day 45, bạn cần nhìn một LLM/RAG app và trả lời được:

```text
Request này tốn bao nhiêu tiền?
Stage nào đang làm cost phình lên?
Token budget của từng endpoint là gì?
Nếu vượt budget, hệ thống degrade như thế nào?
Nếu giảm context/model/output tokens, quality có còn đạt release gate không?
Dùng được trong production không, nếu có thì cần điều kiện gì?
```

Cost optimization không phải là "chọn model rẻ hơn". Với hệ thống thật, cost đến từ toàn pipeline:

- Input tokens và output tokens của LLM.
- Embedding cho query và documents.
- Reranking, query rewrite, classifier, guardrail hoặc citation validation.
- Vector DB, lexical search, Redis, database, queue và object storage.
- Retry, timeout, malformed structured output và fallback.
- Eval, synthetic data, offline batch, observability và log retention.
- GPU/serving utilization nếu self-host model.

Tư duy đúng của Senior SE: **cost là một non-functional requirement**, giống latency, availability và security. Phải đo, budget, enforce, alert và review theo từng release.

## 2. Bối cảnh dùng trong bài

Bài này lấy RAG app Day 40 làm ví dụ:

```text
User question
  -> normalize
  -> optional semantic cache lookup
  -> query embedding
  -> dense search + lexical search
  -> hybrid merge
  -> rerank
  -> context builder
  -> LLM generation
  -> citation validation
  -> trace/cost logger
```

Mục tiêu không phải giảm cost bằng mọi giá. Mục tiêu là tìm điểm tối ưu theo context:

- Với FAQ nội bộ: cost thấp và latency thấp thường quan trọng hơn reasoning mạnh.
- Với HR/legal/policy: citation correctness quan trọng hơn vài phần trăm cost.
- Với eval/offline workload: có thể chấp nhận chậm hơn để dùng Batch API.
- Với tenant trả phí cao: có thể route sang model mạnh hơn và quota lớn hơn.
- Với tenant trial/free: có thể giới hạn output, context và retry.

## 3. Step-by-step cost optimization loop

Không tối ưu khi chưa có số liệu. Quy trình production nên đi theo vòng lặp:

```text
1. Instrument
   Log token, model, cache, retry, latency và stage-level trace.

2. Baseline
   Tính cost/request, cost/day, cost/month theo tenant, feature và model.

3. Budget
   Đặt token budget, request quota, eval budget và retry budget.

4. Optimize
   Áp dụng cache, model routing, context pruning, batch hoặc distillation.

5. Verify
   Chạy regression eval: retrieval, answer quality, citation, no-answer, latency.

6. Roll out
   Canary theo tenant/traffic %, theo dõi cost và quality cùng lúc.

7. Degrade or rollback
   Nếu vượt budget hoặc quality giảm, bật degrade mode hoặc rollback config.
```

Điểm quan trọng: mọi tối ưu cost phải có **before/after estimate** và **quality gate**. Nếu cost giảm 40% nhưng citation sai tăng mạnh, đó không phải optimization tốt cho RAG production.

## 4. Cost model

Công thức tối thiểu cho một request:

```text
cost_per_request =
  llm_input_tokens * input_price_per_token
+ llm_cached_input_tokens * cached_input_price_per_token
+ llm_output_tokens * output_price_per_token
+ reasoning_tokens * reasoning_price_per_token
+ embedding_tokens * embedding_price_per_token
+ reranker_units * reranker_price_per_unit
+ tool_calls * tool_price_per_call
+ retry_count * retry_cost
+ infra_cost_allocated_per_request
+ observability_cost_allocated_per_request
```

Với RAG app, tách theo stage để biết cần tối ưu ở đâu:

| Stage | Cost driver | Metric cần log | Tối ưu thường dùng |
|---|---|---|---|
| Query normalization | CPU hoặc LLM nhỏ | `normalization_ms`, `rewrite_tokens` | rule-based, small model |
| Semantic cache lookup | Redis + embedding | `cache_lookup_ms`, `cache_hit` | TTL, threshold, tenant scope |
| Query embedding | embedding tokens/request | `embedding_tokens`, `embedding_model` | cache query embedding, batch offline |
| Dense search | vector DB CPU/RAM | `dense_top_k`, `dense_ms` | metadata filter, index tuning |
| Lexical search | search infra | `sparse_top_k`, `sparse_ms` | index field đúng, limit candidate |
| Rerank | model/API call | `rerank_candidates`, `rerank_ms` | giảm candidate, dùng reranker nhỏ |
| Context build | input tokens | `context_tokens`, `context_chunks` | chunk pruning, compression |
| Generation | input/output tokens | `prompt_tokens`, `completion_tokens` | token budget, concise mode |
| Citation validation | CPU hoặc retry | `citation_valid`, `retry_count` | schema validation, stricter prompt |
| Eval | nhân số request | `eval_items`, `eval_cost` | Batch API, sampling |
| Observability | storage/log volume | `trace_size_bytes` | retention, sampling, redaction |

### Daily/monthly estimate

```text
cost_per_day =
  sum(cost_per_request_by_type * requests_per_day_by_type)
+ offline_jobs_cost_per_day
+ fixed_infra_cost_per_day

cost_per_month = cost_per_day * 30
```

Nên estimate theo request type, không lấy một average mơ hồ:

| Request type | Traffic share | Cost behavior | Ghi chú |
|---|---:|---|---|
| Simple FAQ | cao | input/output thấp, cache hit cao | ứng viên tốt cho semantic cache |
| Normal RAG | trung bình | context 3-6 chunks | default path |
| Complex RAG | thấp | context dài, model mạnh | quota riêng |
| Eval | theo batch | nhân golden set | chạy offline |
| Admin/debug | thấp | trace đầy đủ, output dài | chỉ cho internal user |

## 5. Trace log là nền tảng của cost optimization

Nếu trace không có token và model, bạn không thể tối ưu nghiêm túc. Mỗi request nên log tối thiểu:

```json
{
  "trace_id": "tr_20260510_001",
  "timestamp": "2026-05-10T10:30:00Z",
  "tenant_id": "tenant_a",
  "user_tier": "paid",
  "feature": "rag_query",
  "request_type": "normal_rag",
  "pipeline_version": "rag-cost-v2",
  "corpus_version": "policy-2026-05",
  "prompt_version": "rag-answer.v4",
  "models": {
    "embedding": "embedding-small",
    "reranker": "reranker-base",
    "generator": "llm-medium"
  },
  "usage": {
    "prompt_tokens": 4200,
    "cached_prompt_tokens": 1800,
    "completion_tokens": 520,
    "reasoning_tokens": 0,
    "embedding_tokens": 32,
    "rerank_units": 24
  },
  "retrieval": {
    "dense_top_k": 50,
    "sparse_top_k": 50,
    "rerank_top_n": 24,
    "context_chunks": 5,
    "context_tokens": 3100
  },
  "cache": {
    "prompt_cache_hit_tokens": 1800,
    "semantic_cache_hit": false,
    "semantic_cache_similarity": null
  },
  "latency_ms": {
    "embedding": 42,
    "dense_search": 38,
    "sparse_search": 21,
    "rerank": 170,
    "generation": 1460,
    "total": 1810
  },
  "retry": {
    "count": 0,
    "reason": null
  },
  "estimated_cost_usd": 0.0031,
  "quality_signals": {
    "answer_status": "answered",
    "citation_valid": true,
    "user_feedback": null
  }
}
```

Production note:

- Log cost estimate ngay trong request path hoặc async worker gần realtime.
- Không log raw PII nếu không cần; dùng redaction và retention policy.
- Lưu `pricing_version` để sau này biết cost được tính theo bảng giá nào.
- Cost dashboard nên drill-down theo tenant, feature, route, model, prompt version và cache hit.

## 6. Token budget

Token budget là contract giữa product, backend và prompt. Nó phải được enforce ở backend, không chỉ ghi trong prompt.

Ví dụ budget cho RAG app:

| Endpoint/request | Max query tokens | Max context chunks | Max context tokens | Max output tokens | Max retries | Ghi chú |
|---|---:|---:|---:|---:|---:|---|
| `/query` simple FAQ | 120 | 3 | 1,800 | 250 | 1 | ưu tiên cache/latency |
| `/query` normal RAG | 250 | 5 | 3,500 | 600 | 1 | default |
| `/query` complex RAG | 500 | 8 | 7,000 | 900 | 1 | cần quota/tier |
| `/eval/run` | 250 | 5 | 3,500 | 400 | 0 | deterministic, offline |
| `/documents/ingest` | n/a | n/a | n/a | n/a | 3 | budget theo document tokens |
| `/admin/debug` | 1,000 | 10 | 12,000 | 1,200 | 0 | internal only |

Backend enforcement nên có các bước:

```text
receive request
  -> classify request_type
  -> load tenant/user budget policy
  -> reject or trim query if too long
  -> cap retrieval top_k and rerank_top_n
  -> build candidate context
  -> prune until context_tokens <= budget
  -> set max_output_tokens on model call
  -> cap retry count
  -> log budget decision
```

Pseudo-code:

```python
def enforce_token_budget(request, retrieved_chunks, policy, tokenizer):
    query_tokens = tokenizer.count(request.question)
    if query_tokens > policy.max_query_tokens:
        raise BudgetError("question_too_long")

    selected = []
    total_context_tokens = 0

    for chunk in retrieved_chunks[: policy.max_context_chunks * 2]:
        chunk_tokens = tokenizer.count(chunk.text)
        if total_context_tokens + chunk_tokens > policy.max_context_tokens:
            continue
        selected.append(chunk)
        total_context_tokens += chunk_tokens
        if len(selected) >= policy.max_context_chunks:
            break

    return GenerationPlan(
        context_chunks=selected,
        max_output_tokens=policy.max_output_tokens,
        max_retries=policy.max_retries,
        budget_name=policy.name,
    )
```

Trade-off:

- Budget quá chặt giảm cost nhưng tăng no-answer hoặc answer thiếu bằng chứng.
- Budget quá rộng làm cost, latency và p95 spike.
- Best default cho RAG Day 40: đặt normal budget vừa đủ 4-5 chunks, chỉ mở complex budget khi classifier thấy câu hỏi cần multi-section reasoning.

## 7. Prompt caching

Prompt caching phù hợp khi phần prefix của prompt lặp lại:

```text
system instruction
+ developer instruction
+ response schema
+ static examples
+ stable tool definitions
+ stable policy block
+ dynamic context
+ user question
```

Nguyên tắc thiết kế:

1. Đặt phần static ở đầu prompt.
2. Đặt user-specific data, query và context biến động ở cuối.
3. Version hóa prompt: `prompt_version`, `schema_version`, `policy_version`.
4. Log `cached_prompt_tokens` hoặc field tương đương của provider.
5. Không trộn dữ liệu permission-sensitive vào cache key dùng chung.

Với provider như OpenAI, prompt caching có thể tự động áp dụng cho prompt đủ dài, usage trả về số cached tokens, và có tham số kiểu `prompt_cache_key`/retention tùy model. Chi tiết này thay đổi theo provider, nên production code không nên hardcode giả định; hãy log usage thực tế và đưa pricing vào config.

Risk:

- Cache key sai có thể làm giảm hit rate hoặc tạo rủi ro dữ liệu multi-tenant.
- Prefix thay đổi liên tục làm cache vô dụng.
- Caching không giảm output token cost; nếu answer quá dài, cost vẫn cao.
- Cached tokens vẫn có thể tính vào rate limit tùy provider.

Best use trong Day 40 RAG:

- Cache phần system prompt, schema, citation rules và static examples.
- Không cache global phần context chứa tài liệu tenant nếu chưa chắc boundary permission.
- Theo dõi `cached_tokens / prompt_tokens`, p95 latency và cost/request trước/sau.

## 8. Semantic caching với Redis

Semantic cache trả lại answer đã có cho query gần nghĩa nhau, không chỉ query giống hệt nhau.

Flow:

```text
question
  -> normalize
  -> classify cache eligibility
  -> embedding(question)
  -> vector search trong cache index
  -> kiểm tra similarity threshold
  -> kiểm tra tenant_id, permission_hash, corpus_version, prompt_version
  -> nếu hit: trả cached answer
  -> nếu miss: chạy full RAG pipeline rồi lưu cache entry
```

Cache entry tối thiểu:

```json
{
  "cache_id": "sc:tenant_a:policy-2026-05:rag-answer.v4:8f31",
  "tenant_id": "tenant_a",
  "permission_hash": "roles:employee",
  "corpus_version": "policy-2026-05",
  "prompt_version": "rag-answer.v4",
  "answer_schema_version": "v1",
  "embedding_model": "embedding-small",
  "generator_model": "llm-medium",
  "normalized_question": "ngay nghi phep nam full time",
  "answer": "Nhân viên full-time có 12 ngày nghỉ phép năm [S1].",
  "citations": ["doc_hr:v3:chunk_004"],
  "source_chunk_hashes": ["sha256:..."],
  "created_at": "2026-05-10T10:30:00Z",
  "expires_at": "2026-05-17T10:30:00Z"
}
```

Redis có thể dùng theo hai lớp:

- Redis key-value để lưu answer payload, TTL, metadata và counters.
- Redis vector search hoặc vector DB riêng để search embedding của normalized question.

Pseudo-code:

```python
def get_semantic_cache(question, auth, versions, embedding):
    if not is_cacheable(question, auth):
        return CacheMiss(reason="not_cacheable")

    normalized = normalize_question(question)
    query_vector = embedding.embed(normalized)
    candidates = cache_index.search(
        vector=query_vector,
        top_k=5,
        filters={
            "tenant_id": auth.tenant_id,
            "permission_hash": auth.permission_hash,
            "corpus_version": versions.corpus,
            "prompt_version": versions.prompt,
        },
    )

    best = candidates[0] if candidates else None
    if best and best.score >= 0.92 and still_valid(best.metadata):
        payload = redis.get(best.cache_id)
        return CacheHit(payload=payload, similarity=best.score)

    return CacheMiss(reason="low_similarity_or_not_found")
```

Không dùng semantic cache cho:

- Câu hỏi chứa PII hoặc dữ liệu cá nhân nhạy cảm.
- Dữ liệu realtime: giá, tồn kho, lịch, trạng thái ticket.
- Câu hỏi yêu cầu tính toán theo thời điểm hiện tại.
- Domain có rủi ro cao nếu trả nhầm: legal advice, medical advice, financial decision.
- Multi-tenant/ACL chưa có permission hash chắc chắn.

Trade-off:

- Hit rate cao giúp giảm mạnh cost và latency.
- Similarity threshold thấp có thể trả nhầm answer.
- Invalidation khó nếu corpus thay đổi thường xuyên.
- Best default: chỉ bật cho FAQ có citation ổn định, threshold cao, TTL ngắn, scoped theo tenant + ACL + corpus version.

## 9. Model routing

Không phải request nào cũng cần model mạnh nhất. Router chọn model theo task, complexity, user tier, quota, latency SLO và risk.

Ví dụ rule table:

| Task | Default model tier | Khi nào nâng cấp | Khi nào hạ cấp |
|---|---|---|---|
| Intent classification | rule/small | intent không chắc | gần hết budget |
| Query rewrite | small | query dài, ambiguous | exact keyword query |
| JSON extraction | small/medium | schema fail nhiều | input đơn giản |
| RAG answer | medium | multi-hop, high-risk, paid tier | simple FAQ, cacheable |
| Citation validation | rule/small | citation conflict | debug off |
| Eval judge | strong | release gate chính | smoke test |

Router input nên rõ:

```json
{
  "request_type": "normal_rag",
  "tenant_tier": "paid",
  "remaining_monthly_budget_usd": 42.5,
  "query_complexity": "medium",
  "risk_level": "policy",
  "latency_slo_ms": 2500,
  "cache_hit": false,
  "provider_health": "ok"
}
```

Pseudo-code:

```python
def route_model(features, budgets, eval_scores):
    if budgets.tenant_monthly_remaining_usd <= 0:
        return Route(model="llm-small", mode="degraded", reason="budget_exhausted")

    if features.cache_hit:
        return Route(model=None, mode="cache_hit", reason="semantic_cache")

    if features.request_type == "simple_faq":
        return Route(model="llm-small", mode="normal", reason="simple_faq")

    if features.risk_level in {"legal", "finance"} and budgets.user_tier == "paid":
        return Route(model="llm-strong", mode="normal", reason="high_risk_paid")

    if features.query_complexity == "complex":
        return Route(model="llm-strong", mode="normal", reason="complex_query")

    return Route(model="llm-medium", mode="normal", reason="default_rag")
```

Production guardrail:

- Mỗi route phải có eval riêng, không dùng một golden score chung.
- Log route reason để debug bill tăng bất thường.
- Có fallback khi provider lỗi, nhưng fallback cũng phải nằm trong budget.
- Model nhỏ phải qua structured output validation nếu dùng cho extraction.

## 10. Context compression và chunk pruning

RAG cost thường phình vì context quá dài. Tối ưu context nên làm trước khi đổi model.

Pipeline đề xuất:

```text
retrieve top 50 dense + top 50 sparse
  -> RRF merge
  -> rerank top 24
  -> remove duplicate document/section
  -> keep top evidence spans
  -> apply max context token budget
  -> optional compression
  -> build prompt with citations
```

Kỹ thuật:

- Giảm `context_top_k` sau rerank, không nhất thiết giảm retrieval candidate ban đầu.
- Dedupe chunk cùng document/heading nếu nội dung trùng ý.
- Prune chunk có score thấp hoặc không chứa entity/query terms quan trọng.
- Trích evidence span trong chunk thay vì đưa cả chunk dài.
- Tách mode `concise` và `detailed`.
- Dùng metadata filter trước retrieval: tenant, ACL, document type, language, version.
- Dùng compression bằng small model cho context dài, nhưng chỉ khi citation vẫn map được về source span.

Ví dụ chunk pruning:

```python
def prune_context(reranked_hits, budget, tokenizer):
    selected = []
    used_sections = set()
    used_tokens = 0

    for hit in reranked_hits:
        section_key = (hit.document_id, hit.heading)
        if section_key in used_sections and hit.score < budget.duplicate_section_score:
            continue

        span = extract_relevant_span(hit.text, hit.query_terms, max_tokens=budget.max_span_tokens)
        span_tokens = tokenizer.count(span)
        if used_tokens + span_tokens > budget.max_context_tokens:
            continue

        selected.append(ContextBlock(source_id=hit.source_id, text=span, metadata=hit.metadata))
        used_sections.add(section_key)
        used_tokens += span_tokens

        if len(selected) >= budget.max_context_chunks:
            break

    return selected
```

Trade-off:

- Pruning mạnh giảm cost nhưng có thể mất evidence.
- Compression có thể tạo paraphrase làm citation khó validate.
- Với policy assistant, ưu tiên giữ nguyên source span ngắn hơn là summary không còn trích dẫn trực tiếp.

Best default cho Day 40:

- Retrieval candidate vẫn rộng: dense 50 + sparse 50.
- Rerank còn 24.
- Context gửi LLM còn 4-5 blocks.
- Mỗi block là source span 250-500 tokens có citation metadata.

## 11. Batch API và offline workload

Batch API phù hợp với workload không cần trả lời realtime:

- Embedding hoặc re-embedding tài liệu.
- Nightly eval trên golden set.
- Synthetic question generation.
- Classification/summarization large dataset.
- Backfill trace analysis.
- Migration prompt/model version.

Không phù hợp với:

- Chat realtime.
- Request cần streaming.
- User-facing SLA tính bằng giây.
- Action cần kết quả ngay để tiếp tục workflow.

Production design:

```text
Realtime path
  -> strict latency SLO
  -> small per-request budget
  -> limited retry
  -> user-facing quota

Offline path
  -> queue/batch
  -> separate quota
  -> lower priority
  -> resumable job
  -> result audit table
```

Nhiều provider có Batch API với pricing/rate-limit khác sync API. Ví dụ tài liệu OpenAI hiện mô tả batch là async, thường có discount và completion window rõ. Tuy nhiên, thông số cụ thể là provider-specific; course code nên đọc từ `pricing_config` và feature flags.

## 12. Distillation overview

Distillation là dùng model mạnh tạo label/output để train hoặc fine-tune model nhỏ hơn.

Flow:

```text
collect stable task traces
  -> filter high-quality examples
  -> generate teacher labels bằng strong model
  -> human review hoặc rule validation
  -> train/fine-tune student model
  -> eval theo task
  -> canary route một phần traffic
  -> monitor quality/cost drift
```

Nên dùng khi:

- Task lặp lại nhiều: classification, extraction, routing, short answer.
- Format output rõ và có schema.
- Traffic đủ lớn để bù chi phí tạo dataset/eval.
- Có golden set đáng tin cậy.
- Requirement ổn định trong vài tháng.

Không nên dùng khi:

- Product requirement thay đổi liên tục.
- Domain cần reasoning mạnh hoặc context dài.
- Chưa có eval framework.
- Data có rủi ro compliance cao mà chưa xử lý governance.

Trade-off:

- Cost inference dài hạn có thể giảm nhiều.
- Chi phí ban đầu tăng: data labeling, training, eval, deployment.
- Model nhỏ dễ drift khi corpus hoặc policy đổi.
- Best use trong RAG Day 40: distill query classifier, intent router, no-answer detector hoặc extraction task; chưa nên distill toàn bộ answer generator nếu citation correctness là release gate chính.

## 13. Budget, quota và degrade mode

Production cần phân biệt:

- **Budget**: số tiền/token dự kiến được dùng trong một khoảng thời gian.
- **Quota**: giới hạn enforce được, ví dụ requests/day hoặc tokens/month.
- **Rate limit**: tốc độ request/token trong một cửa sổ ngắn.
- **Degrade mode**: hành vi khi budget/quota/rate limit sắp hoặc đã vượt.

Ví dụ policy:

| Level | Trigger | Hành động | User impact |
|---|---|---|---|
| Normal | dưới 70% monthly budget | full route | không |
| Watch | 70-85% | alert, tăng sampling logs | không đáng kể |
| Conserve | 85-95% | concise output, giảm context, ưu tiên cache | answer ngắn hơn |
| Degraded | 95-100% | route model nhỏ, tắt complex mode, batch eval | quality có thể giảm |
| Hard stop | vượt 100% hoặc abuse | reject non-critical, admin override | request bị từ chối |

Degrade mode nên có thứ tự:

```text
1. Giảm max output tokens.
2. Bật concise answer mode.
3. Giảm context_top_k nhưng giữ citation validation.
4. Ưu tiên semantic cache cho FAQ.
5. Route simple task sang small model.
6. Tạm dừng eval/synthetic/offline job.
7. Reject complex/debug request không quan trọng.
8. Hard stop tenant hoặc user nếu vượt quota nghiêm trọng.
```

Không nên degrade bằng cách:

- Bỏ ACL filter.
- Tắt citation validation cho domain cần citation.
- Trả answer không có đủ context.
- Retry vô hạn sang provider khác.
- Chuyển sang model chưa qua eval.

## 14. Best solution theo context/performance

Không có một kỹ thuật tốt nhất cho mọi hệ thống. Chọn theo shape của workload.

| Context | Best first move | Vì sao | Cần đo |
|---|---|---|---|
| RAG app mới, traffic thấp | instrument + token budget | chưa có data để tối ưu sâu | cost/request, p95 tokens |
| FAQ traffic cao | semantic cache + small model route | query lặp lại nhiều | cache hit, false hit |
| Prompt/schema dài | prompt caching | giảm prefill cost/latency | cached tokens ratio |
| Context quá dài | chunk pruning + context budget | giảm input tokens trực tiếp | citation correctness |
| Eval/nightly job tốn tiền | Batch API | không cần realtime | job success, total cost |
| Nhiều task đơn giản | model routing | không dùng model mạnh cho mọi thứ | quality per route |
| Stable high-volume task | distillation | giảm cost dài hạn | student vs teacher eval |
| Self-host GPU idle thấp | batching + quantization + autoscaling | cost nằm ở utilization | GPU utilization, throughput |

Best default cho RAG Day 40:

1. Log đầy đủ token/cost theo trace.
2. Enforce token budget cho `/query` và `/eval/run`.
3. Dùng prompt caching cho static prompt/schema.
4. Prune context còn 4-5 source spans sau rerank.
5. Dùng semantic cache chỉ cho FAQ tenant-scoped.
6. Route simple FAQ/query rewrite sang small model.
7. Chạy eval/offline workload bằng batch queue.
8. Chỉ nghiên cứu distillation sau khi traffic và eval đủ ổn định.

## 15. Trade-off tổng hợp

| Kỹ thuật | Giảm cost | Tác động latency | Risk chính | Production condition |
|---|---:|---|---|---|
| Max output tokens | cao | giảm | answer thiếu | có UX "more detail" hoặc detailed mode |
| Prompt caching | trung bình-cao | giảm prefill | cache miss nếu prefix biến động | static prefix, log cached tokens |
| Semantic cache | rất cao với FAQ | giảm mạnh | trả nhầm context | tenant/ACL/corpus scoped, threshold cao |
| Model routing | cao | tùy route | model nhỏ fail case khó | eval per route, fallback rõ |
| Context pruning | cao | giảm | mất evidence | citation regression test |
| Context compression | trung bình | có thể tăng vì thêm call | summary sai/lost citation | map về source span |
| Batch API | cao cho offline | không realtime | job chậm, retry phức tạp | separate queue/quota |
| Distillation | cao dài hạn | giảm | data/eval cost cao | task ổn định, golden set tốt |
| Local model | tùy utilization | tùy infra | ops/GPU phức tạp | tính TCO, monitor utilization |

## 16. Dùng được trong production không?

**Có, dùng được trong production nếu cost optimization được triển khai như một control plane có đo lường, budget, policy và eval, không phải vài mẹo giảm token rời rạc.**

Điều kiện tối thiểu:

- Mọi LLM/embedding/rerank call đều log token usage, model, pricing version và trace id.
- Có dashboard cost theo tenant, feature, endpoint, model và prompt version.
- Token budget được enforce ở backend.
- Cache key có tenant, ACL/permission hash, corpus version, prompt version và schema version.
- Model routing có eval per route và fallback được test.
- Context pruning/compression có regression eval cho retrieval, citation và no-answer.
- Offline jobs dùng quota riêng, không ăn hết quota realtime.
- Có budget alert, degrade mode, hard stop và admin override.
- Có runbook rollback khi cost giảm nhưng quality tụt.
- Không hardcode bảng giá trong business logic; giá nằm trong config/versioned table.

Chưa nên gọi là production-ready nếu:

- Chỉ estimate bằng spreadsheet, không có trace thật.
- Không log cached tokens, retry count hoặc context tokens.
- Semantic cache không scope theo tenant/permission.
- Tất cả request đều dùng cùng một model mạnh.
- Eval không chạy sau khi giảm context hoặc đổi model.
- Không có cách dừng cost spike do retry loop, abuse hoặc batch job lỗi.

## 17. Checklist trước khi merge cost optimization PR

- [ ] Before/after cost estimate có số liệu trace thật hoặc giả định ghi rõ.
- [ ] Có budget policy cho endpoint bị ảnh hưởng.
- [ ] Có metric quality liên quan: retrieval recall, citation correctness, no-answer accuracy, schema success.
- [ ] Có rollout plan: canary tenant hoặc traffic percentage.
- [ ] Có rollback plan: config flag, model route fallback, cache disable.
- [ ] Có alert cho cost spike và cache false hit.
- [ ] Có log `route_reason`, `budget_decision`, `cache_decision`.
- [ ] Không thay đổi ACL/security boundary để giảm cost.
- [ ] Không xóa trace/log cần cho audit nếu chưa có retention policy.
