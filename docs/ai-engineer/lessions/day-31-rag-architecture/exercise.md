# Day 31 Exercise: Thiết Kế Mini Production RAG

Thời lượng gợi ý: 90-150 phút.

Mục tiêu: thiết kế và mô phỏng một RAG system cho "Internal Policy Assistant" có indexing pipeline, query pipeline, citation, eval và production readiness checklist.

## Phần 1: Xác Định Use Case

Chọn một use case:

| Use case | Corpus | Risk chính |
|---|---|---|
| HR Policy Assistant | Handbook, policy PDF, FAQ | Trả lời sai quyền lợi nhân viên |
| Engineering Runbook Assistant | Runbook, incident postmortem, ADR | Hướng dẫn sai khi incident |
| Customer Support Policy Bot | Refund policy, shipping policy, product FAQ | Hallucination ảnh hưởng khách hàng |
| Legal Contract Search | Contract clauses, addendum | Citation sai hoặc thiếu clause |

Viết ngắn:

- User là ai?
- Họ hỏi gì?
- Source of truth là gì?
- Câu trả lời sai gây hậu quả gì?
- Có dữ liệu nhạy cảm hoặc ACL không?

## Phần 2: Vẽ Architecture Diagram

Vẽ diagram text cho hai path.

Indexing path:

```text
Sources
  -> Loader
  -> Parser
  -> Cleaner
  -> Chunker
  -> Metadata Enricher
  -> Embedding Service
  -> Vector DB/Search Index
  -> Index Version
```

Query path:

```text
User
  -> API/Auth
  -> Query Normalize/Rewrite
  -> Permission-aware Hybrid Retriever
  -> Backend Post-filter
  -> Reranker
  -> Context Builder
  -> LLM Generator
  -> Citation Validator
  -> Answer + Sources + Trace
```

Yêu cầu: ghi rõ stage nào sync, stage nào async, stage nào có retry, stage nào có timeout.

## Phần 3: Thiết Kế Chunk Schema

Tạo 5 document giả lập và ít nhất 10 chunks. Mỗi chunk cần metadata:

```json
{
  "chunk_id": "",
  "document_id": "",
  "document_title": "",
  "source_uri": "",
  "tenant_id": "",
  "acl_tags": [],
  "document_version": "",
  "index_version": "",
  "chunk_index": 0,
  "section_path": [],
  "page_number": null,
  "text": ""
}
```

Checklist:

- [ ] Có ít nhất 2 ACL tags khác nhau.
- [ ] Có ít nhất 1 document version cũ và 1 version mới.
- [ ] Có source URI cho citation.
- [ ] Có section path để người dùng kiểm chứng.

## Phần 4: Chọn Retrieval Strategy

Điền bảng:

| Quyết định | Lựa chọn của bạn | Vì sao | Trade-off |
|---|---|---|---|
| Dense-only / BM25-only / Hybrid |  |  |  |
| retrieve top_k |  |  |  |
| rerank top_n |  |  |  |
| context chunks |  |  |  |
| max context tokens |  |  |  |
| citation format |  |  |  |

Gợi ý thực dụng cho enterprise docs:

```text
dense top 50 with tenant/ACL pre-filter
+ BM25 top 50 with tenant/ACL pre-filter
-> RRF merge
-> backend post-filter
-> rerank top 50
-> context top 5-8 chunks
```

## Phần 5: Viết Pseudo-code Query Pipeline

Hoàn thiện pseudo-code sau:

```python
def answer_policy_question(question, user):
    trace = new_trace()
    tenant_id, acl_tags = resolve_permissions(user)

    normalized_query = normalize(question)

    dense_candidates = dense_search(
        normalized_query,
        tenant_id=tenant_id,
        acl_tags=acl_tags,
        top_k=50,
    )
    bm25_candidates = bm25_search(
        normalized_query,
        tenant_id=tenant_id,
        acl_tags=acl_tags,
        top_k=50,
    )

    candidates = merge_and_dedupe(dense_candidates, bm25_candidates)
    # Defense-in-depth: search backends pre-filter; backend checks again
    # before text can reach the reranker, context builder, or LLM.
    candidates = filter_by_acl(candidates, acl_tags)
    reranked = rerank(normalized_query, candidates[:50], timeout_ms=800)
    context, sources = build_context(reranked, max_tokens=2500)

    if not sources:
        return no_answer(trace)

    answer = generate_answer(question, context, sources)
    citation_errors = validate_citations(answer, sources)

    log_trace(trace, question, sources, citation_errors)
    return answer, sources, trace.id
```

Yêu cầu: thêm xử lý timeout/fallback cho reranker và generator.

## Phần 6: Tạo Golden Eval Set

Tạo ít nhất 10 queries:

| Query | Expected chunks | Expected facts | Must not include | Difficulty |
|---|---|---|---|---|
|  |  |  |  | easy/medium/hard |

Phải có:

- 3 câu hỏi dễ có exact keyword.
- 3 câu hỏi semantic/paraphrase.
- 2 câu hỏi cần ACL khác nhau.
- 1 câu hỏi thiếu thông tin, expected answer phải từ chối.
- 1 câu hỏi có document version cũ gây nhiễu.

Metric cần tính:

- Hit@5.
- Recall@10.
- MRR@10.
- Citation correctness.
- Refusal correctness.

## Phần 7: Latency Và Cost Budget

Đặt budget cho hệ thống:

| Stage | Target p95 | Fallback nếu vượt |
|---|---:|---|
| Auth + validation |  |  |
| Query embedding |  |  |
| Hybrid retrieval |  |  |
| Rerank |  |  |
| Context build |  |  |
| Generation first token |  |  |
| Total |  |  |

Trả lời:

1. Nếu p95 vượt 6 giây, bạn tối ưu stage nào trước?
2. Nếu cost/request quá cao, giảm gì trước: top_k, reranker, context tokens hay model?
3. Nếu quality giảm khi giảm context, bạn đo metric nào để quyết định?

## Phần 8: Production Risk Review

Điền bảng:

| Risk | Ví dụ cụ thể | Mitigation |
|---|---|---|
| ACL leak |  |  |
| Stale index |  |  |
| Prompt injection in document |  |  |
| Citation giả |  |  |
| Hallucination |  |  |
| Cost spike |  |  |
| PII trong log |  |  |
| Reindex fail giữa chừng |  |  |

## Phần 9: Quiz

1. RAG khác prompt-only chatbot ở đâu?
2. Vì sao indexing pipeline và query pipeline phải tách nhau?
3. Chunk quá nhỏ và chunk quá lớn gây lỗi gì?
4. Vì sao hybrid retrieval thường tốt cho enterprise docs?
5. Reranker cải thiện gì và đánh đổi gì?
6. ACL nên enforce ở đâu?
7. Citation validator cần check gì?
8. Khi đổi embedding model, vì sao nên tạo index version mới?
9. Metric nào đo retrieval quality?
10. Khi nào RAG nên trả lời "không đủ thông tin"?

## Phần 10: Tiêu Chí Hoàn Thành

- [ ] Có diagram indexing path và query path.
- [ ] Có chunk schema với metadata, ACL và version.
- [ ] Có retrieval strategy kèm trade-off.
- [ ] Có pseudo-code query pipeline.
- [ ] Có 10 golden queries.
- [ ] Có latency/cost budget.
- [ ] Có production risk table.
- [ ] Trả lời rõ: hệ thống này production được không, cần điều kiện gì.

Mẫu câu trả lời production readiness:

```text
Hệ thống này có thể dùng production cho internal beta nếu:
- Chỉ mở cho nhóm user có ACL đã kiểm thử.
- Có citation validator và answer fallback khi context thiếu.
- Có golden set đạt Hit@5 >= 85% và citation correctness >= 95%.
- Có monitoring p95 latency, empty retrieval, citation error và feedback.
- Có delete/reindex path khi policy thay đổi.

Chưa nên mở public hoặc dùng cho quyết định pháp lý/nhân sự tự động nếu chưa có human review,
audit log, security review và regression test ổn định.
```
