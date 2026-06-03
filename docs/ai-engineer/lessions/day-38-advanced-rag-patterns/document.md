# Document: Advanced RAG Cheat Sheet Và Runbook

## 1. Mental model nhanh

Advanced RAG là lớp tối ưu sau baseline, không phải baseline.

```text
Baseline:
query -> hybrid search -> RRF -> rerank -> context -> answer + citation

Advanced:
query understanding
  -> better retrieval queries
  -> better indexed chunks
  -> optional multi-step retrieval
  -> quality check
  -> answer with trace
```

Nguyên tắc mặc định:

1. Sửa chunking, metadata, ACL và hybrid search trước.
2. Thêm query rewriting nếu query của user thiếu rõ ràng.
3. Thêm contextual retrieval nếu chunk mất context.
4. Thêm multi-query nếu synonym/acronym làm Recall thấp.
5. Thêm decomposition hoặc agentic flow chỉ cho query cần nhiều bước.

## 2. Decision matrix

| Pattern | Giải quyết tốt | Không nên dùng khi | Production default |
|---|---|---|---|
| Query rewriting | Query ngắn, typo, không dấu, chat history | Exact ID, exact quote, legal wording | Nên thử sớm |
| Multi-query retrieval | Synonym, acronym, wording đa dạng | SLA chặt, corpus nhỏ, query exact | Có điều kiện |
| HyDE | Query quá ngắn, style user khác corpus | High-risk exact answer | Không mặc định |
| Step-back prompting | Cần context khái niệm chung | Lookup mã/SKU/order | Có điều kiện |
| Query decomposition | So sánh, nhiều điều kiện | FAQ đơn giản | Route riêng |
| Multi-hop RAG | Cần evidence từ nhiều tài liệu | Câu hỏi một bước | Route riêng |
| Contextual retrieval | Chunk mất title/section/table context | Corpus đã sạch, chunk đủ nghĩa | Nên thử sớm |
| Corrective RAG | Context thường yếu hoặc thiếu | Latency rất chặt | Có điều kiện |
| Agentic RAG | Tool choice/multi-step phức tạp | Q&A đơn giản | Không mặc định |
| GraphRAG | Entity relation/global summary | FAQ/policy lookup | Chỉ khi có nhu cầu rõ |

## 3. Query routing cheat sheet

| Query tag | Ví dụ | Route gợi ý |
|---|---|---|
| `exact_lookup` | "ERR-1042 nghĩa là gì?" | Original query + BM25 + rerank |
| `short` | "429 là sao?" | Original + rewrite |
| `synonym` | "nghỉ phép có lương" | Rewrite + hybrid |
| `acronym` | "PTO policy" | Rewrite với glossary + hybrid |
| `conversation` | "nó áp dụng cho Enterprise không?" | Conversational rewrite |
| `comparison` | "Pro khác Enterprise thế nào?" | Decomposition 2 subqueries |
| `multi_hop` | "Ai approve policy ảnh hưởng incident X?" | Multi-hop hoặc agentic route |
| `global` | "Các theme chính của corpus là gì?" | GraphRAG hoặc offline summary |
| `security_sensitive` | "Lương của team finance?" | Strict ACL, no broad rewrite |

## 4. Prompt contract: query rewriting

```text
System:
You rewrite user questions for retrieval over an internal knowledge base.
Do not answer the question.
Preserve intent, constraints, names, IDs, dates and plan names.
If the query is exact lookup, keep it unchanged.
Return JSON only.

Input:
- User query: {query}
- Chat summary: {chat_summary}
- Domain glossary: {glossary}

Output schema:
{
  "rewritten_query": "string",
  "should_search_original": true,
  "reason": "string",
  "risk_flags": ["none" | "ambiguous" | "exact_lookup" | "prompt_injection"]
}
```

Validation:

- Reject output nếu không parse được JSON.
- Reject nếu rewritten query dài hơn giới hạn, ví dụ 300 ký tự.
- Reject nếu mất mã định danh quan trọng từ original query.
- Nếu `risk_flags` chứa `prompt_injection`, chỉ search original hoặc hỏi lại user.

## 5. Prompt contract: multi-query

```text
System:
Generate retrieval query variants with the same intent.
Do not introduce new facts.
Keep IDs, dates, product names and constraints unchanged.
Return JSON only.

Output schema:
{
  "variants": [
    {"query": "string", "purpose": "synonym|acronym|domain_term|vietnamese_english_mix"}
  ]
}
```

Guardrails:

- Tối đa 3 variants.
- Dedupe normalized text.
- Bỏ variant không giữ constraints.
- Rerank sau khi RRF merge.

## 6. Prompt contract: HyDE

```text
System:
Write a hypothetical internal documentation paragraph that could answer the query.
This paragraph is used only to improve retrieval embedding.
Do not include citations.
Do not invent product names, dates or legal clauses.
Return plain text, maximum 120 words.
```

Runbook:

- Embed HyDE text để retrieve.
- Không hiển thị HyDE text cho user.
- Không dùng HyDE text làm citation.
- Nếu domain high-risk, tắt HyDE hoặc route qua review.

## 7. Prompt contract: step-back

```text
System:
Create one broader conceptual retrieval query.
Preserve the domain and main constraint.
Do not remove product names, jurisdiction, dates or policy version if present.
Return JSON only.

Output:
{"step_back_query": "string", "reason": "string"}
```

Rule:

- Retrieve both original and step-back query.
- Khi final answer cần số cụ thể, ưu tiên evidence từ original query.

## 8. Prompt contract: decomposition

```text
System:
Decompose the user question into minimal retrieval subqueries.
Use decomposition only if the answer requires comparing or combining multiple facts.
Return JSON only.

Output:
{
  "requires_decomposition": true,
  "subqueries": [
    {"id": "q1", "query": "string", "expected_evidence": "string"}
  ],
  "synthesis_instruction": "string"
}
```

Validation:

- Tối đa 5 subqueries.
- Mỗi subquery phải bám sát original query.
- Nếu câu hỏi có hai entity A/B, subqueries phải giữ A/B rõ ràng.
- Final answer phải có evidence map theo subquery.

## 9. Grader cho corrective RAG

Rule-based signals:

- `retrieved_count == 0`
- `top_rerank_score < threshold`
- Top chunks đến từ source cũ hơn active version.
- Citation thiếu `source_uri` hoặc `page`.
- Query hỏi "so sánh" nhưng chỉ có evidence cho một bên.
- Query chứa tenant/user-sensitive terms nhưng result thiếu ACL metadata.

LLM grader chỉ nên trả schema:

```json
{
  "answerable": true,
  "missing_evidence": [],
  "conflicting_sources": false,
  "recommended_action": "answer|rewrite_and_retry|ask_clarification|refuse"
}
```

## 10. Observability fields

Log structured trace cho mỗi request:

| Field | Mục đích |
|---|---|
| `request_id` | Trace end-to-end |
| `tenant_id` | Multi-tenancy debug, cần redaction policy |
| `user_role_hash` | Không log raw role nhạy cảm nếu không cần |
| `original_query` | Debug intent |
| `rewritten_query` | Debug rewrite |
| `query_variants` | Debug multi-query |
| `retriever_top_k` | Reproduce retrieval |
| `retrieved_chunk_ids` | Reproduce context |
| `reranked_chunk_ids` | Debug reranker |
| `citations` | Kiểm tra answer grounding |
| `index_version` | Debug stale index |
| `prompt_versions` | Debug behavior drift |
| `latency_breakdown_ms` | Performance |
| `llm_calls` | Cost |
| `fallback_used` | Reliability |
| `eval_tags` | Report theo category |

Không log raw confidential document text nếu chưa có redaction và retention policy.

## 11. Performance budget mẫu

| Stage | Budget p95 gợi ý | Ghi chú |
|---|---:|---|
| Query rewrite | 200-600 ms | Cache nếu query phổ biến |
| Dense retrieval | 50-250 ms | Phụ thuộc Vector DB và filters |
| BM25/sparse retrieval | 30-200 ms | Có thể chạy song song với dense |
| RRF merge | < 20 ms | CPU local |
| Rerank top 50 | 200-900 ms | Cross-encoder có thể đắt |
| Context build | < 50 ms | Dedupe, trim, citation |
| Corrective retry | +300-1500 ms | Chỉ khi cần |
| Generation | 500-3000 ms | Phụ thuộc model và output length |

Nếu p95 target là 2 giây, retrieval path không nên có nhiều hơn 1 online LLM call trước generation, trừ khi chạy async hoặc dùng model rất nhanh.

## 12. Cost estimation nhanh

```text
cost_per_query =
  rewrite_llm_cost
  + multi_query_generation_cost
  + retrieval_calls * retrieval_unit_cost
  + rerank_cost
  + generation_cost
```

Ví dụ route:

| Route | LLM calls trước answer | Retrieval calls | Khi dùng |
|---|---:|---:|---|
| Baseline | 0 | 2, dense + sparse | Default |
| Rewrite | 1 | 4, original/rewrite x dense/sparse | Query ngắn/mơ hồ |
| Multi-query 3 variants | 1 | 8, 4 queries x 2 retrievers | Synonym nặng |
| Decomposition 3 subqueries | 1+ | 6+, mỗi subquery dense/sparse | Comparison/multi-hop |
| Corrective retry | 1-2+ | x2 worst case | Context yếu |

Cost tăng tuyến tính theo số variants/subqueries nếu không có cache và routing.

## 13. Security notes

- Prompt không phải security boundary. ACL phải ở retriever/database layer.
- Query rewrite không được thêm tenant, role hoặc permission từ user input.
- Cache key phải chứa `tenant_id`, `acl_hash`, `index_version` và normalized query.
- Không cache kết quả retrieval cross-tenant.
- Generated query, HyDE text và graph summary đều là derived artifacts, không phải source truth.
- Với right-to-delete, phải xóa hoặc invalidate contextual chunks, graph nodes và summaries liên quan.
- Agentic tools phải có allowlist và kiểm tra quyền riêng ở từng tool.

## 14. Decision report template

```markdown
# Advanced RAG Decision Report

## Change
- Pattern:
- Prompt/index version:
- Target query category:
- Rollout flag:

## Baseline problem
- Failing examples:
- Root cause:
- Current metrics:

## Before/after metrics
| Segment | Pipeline | Recall@5 | MRR@10 | Context precision | Citation accuracy | p95 latency | Cost/query |
|---|---|---:|---:|---:|---:|---:|---:|
| short | baseline | | | | | | |
| short | proposed | | | | | | |

## Risks
- Intent drift:
- Context pollution:
- Security/ACL:
- Cost/latency:
- Ops complexity:

## Decision
- Keep / rollback / limited rollout:
- Reason:
- Monitoring:
- Owner:
```

## 15. Rollout plan

1. Offline eval trên golden set.
2. Shadow mode: log proposed retrieval nhưng không dùng để answer.
3. Compare traces với baseline.
4. Internal canary 5-10% traffic.
5. Monitor no-answer rate, feedback, p95 latency, cost/query, citation error.
6. Rollout theo feature flag.
7. Có rollback một config, không cần redeploy.

## 16. Debug runbook

Khi answer sai, hỏi theo thứ tự:

1. Query có bị rewrite sai intent không?
2. Original query có được search không?
3. Retriever có filter đúng tenant/ACL/index_version không?
4. Dense hay BM25 tìm được expected document?
5. RRF merge có đẩy expected document xuống quá thấp không?
6. Reranker có loại nhầm expected chunk không?
7. Context builder có cắt mất evidence không?
8. Generator có bỏ qua citation hoặc hallucinate không?
9. Pattern mới có làm regression ở query tag khác không?

## 17. Production readiness checklist

- [ ] Có baseline hybrid + rerank được đo bằng golden set.
- [ ] Có query tags để biết pattern giải quyết lỗi nào.
- [ ] Có feature flag cho từng advanced pattern.
- [ ] Có prompt version và config version.
- [ ] Có index version cho contextual retrieval.
- [ ] Có trace structured cho query variants và retrieved chunks.
- [ ] Có tenant/ACL filters bắt buộc.
- [ ] Có cache key an toàn theo tenant/ACL/index_version.
- [ ] Có timeout và fallback về baseline.
- [ ] Có report latency và cost.
- [ ] Có citation kiểm tra source thật.
- [ ] Có rollback plan.
- [ ] Có monitoring sau rollout.

## 18. Câu trả lời production readiness ngắn

Dùng được trong production nếu pattern được chọn dựa trên lỗi đo được, có eval before/after, có trace, có fallback, giữ citation từ source thật và không phá vỡ tenant/ACL. Không nên productionize advanced RAG bằng cách bật đồng loạt query rewrite, multi-query, HyDE, agentic loop và GraphRAG khi chưa có evidence chúng cải thiện chất lượng hơn phần cost/latency/risk tăng thêm.
