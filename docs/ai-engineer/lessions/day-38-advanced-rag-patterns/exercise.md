# Exercise: Advanced RAG Evaluation Lab

## Mục tiêu

Sau bài tập này bạn sẽ có một mini report chứng minh pattern nào đáng giữ cho RAG pipeline. Trọng tâm là 3 pattern gần production nhất:

1. Query rewriting.
2. Multi-query retrieval có RRF merge.
3. Contextual retrieval.

HyDE, step-back, decomposition, corrective RAG và GraphRAG là phần mở rộng tùy thời gian.

Thời lượng đề xuất: 120-180 phút.

## 1. Điều kiện chuẩn bị

Bạn cần một baseline từ Day 36/37:

```text
user query
  -> dense retrieval top_k
  -> BM25 retrieval top_k
  -> RRF merge
  -> rerank top_n
  -> final contexts
```

Nếu chưa có code đầy đủ, có thể làm bài tập ở mức notebook/script với corpus nhỏ và scoring thủ công.

Yêu cầu tối thiểu:

- Python 3.10+.
- Một embedding model hoặc mock embedding ổn định.
- Một BM25 implementation, ví dụ `rank-bm25`, hoặc sparse search tự viết đơn giản.
- Một reranker, hoặc mock reranker dựa trên expected keyword nếu bạn chỉ tập trung vào orchestration.

## 2. Tạo mini corpus

Tạo 12-20 chunks mô phỏng enterprise knowledge base. Mỗi chunk cần metadata:

```python
CORPUS = [
    {
        "chunk_id": "refund_pro_001",
        "document_id": "refund_policy_2026",
        "title": "Refund Policy 2026",
        "section_path": ["Plans", "Pro"],
        "text": "Khách hàng gói Pro được hoàn tiền trong vòng 7 ngày kể từ ngày mua nếu chưa vượt quá 100 API calls.",
        "metadata": {
            "tenant_id": "company_a",
            "acl_roles": ["support", "sales"],
            "source_uri": "kb://refund_policy_2026#pro",
            "index_version": "day38-v1",
        },
    },
    {
        "chunk_id": "refund_enterprise_001",
        "document_id": "refund_policy_2026",
        "title": "Refund Policy 2026",
        "section_path": ["Plans", "Enterprise"],
        "text": "Gói Enterprise không áp dụng hoàn tiền tự động. Mọi yêu cầu refund cần được account manager phê duyệt.",
        "metadata": {
            "tenant_id": "company_a",
            "acl_roles": ["support", "sales"],
            "source_uri": "kb://refund_policy_2026#enterprise",
            "index_version": "day38-v1",
        },
    },
    {
        "chunk_id": "rate_limit_429_001",
        "document_id": "api_error_guide",
        "title": "API Error Guide",
        "section_path": ["HTTP errors", "429"],
        "text": "HTTP 429 Too Many Requests xảy ra khi client vượt quá rate limit theo phút hoặc theo ngày.",
        "metadata": {
            "tenant_id": "company_a",
            "acl_roles": ["developer", "support"],
            "source_uri": "kb://api_error_guide#429",
            "index_version": "day38-v1",
        },
    },
]
```

Thêm ít nhất:

- 3 chunks về billing/payment với synonym như "invoice", "hóa đơn", "thanh toán".
- 3 chunks về leave/PTO để test acronym.
- 3 chunks gần giống nhưng khác plan/version để test rerank.
- 2 chunks của tenant khác để test filter không leak.
- 2 chunks có text ngắn thiếu context, ví dụ "Thời hạn là 7 ngày", để test contextual retrieval.

## 3. Tạo golden set

Tạo file hoặc list Python:

```python
GOLDEN_SET = [
    {
        "query": "429 là sao?",
        "tags": ["short", "acronym"],
        "expected_chunk_ids": ["rate_limit_429_001"],
    },
    {
        "query": "gói Pro refund khác Enterprise thế nào?",
        "tags": ["comparison", "multi_hop"],
        "expected_chunk_ids": ["refund_pro_001", "refund_enterprise_001"],
    },
    {
        "query": "PTO của nhân viên full-time là gì?",
        "tags": ["acronym", "synonym"],
        "expected_chunk_ids": ["leave_policy_001"],
    },
]
```

Bạn cần tối thiểu 20 queries:

- 5 query ngắn.
- 5 query synonym/acronym.
- 4 query comparison.
- 3 query exact lookup.
- 3 query chunk thiếu context.

## 4. Implement metrics

```python
def recall_at_k(results: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 0.0
    return len(set(results[:k]) & expected) / len(expected)


def reciprocal_rank(results: list[str], expected: set[str]) -> float:
    for index, chunk_id in enumerate(results, start=1):
        if chunk_id in expected:
            return 1.0 / index
    return 0.0


def evaluate(run_results: list[dict], k: int = 5) -> dict:
    recalls = []
    mrrs = []
    for row in run_results:
        result_ids = row["result_chunk_ids"]
        expected = set(row["expected_chunk_ids"])
        recalls.append(recall_at_k(result_ids, expected, k))
        mrrs.append(reciprocal_rank(result_ids, expected))
    return {
        f"recall@{k}": sum(recalls) / len(recalls),
        "mrr": sum(mrrs) / len(mrrs),
    }
```

Mở rộng nếu có thời gian:

- Report theo tag.
- Thêm p50/p95 latency.
- Thêm estimated cost/query.
- Thêm context precision: tỷ lệ chunks trong final context thuộc expected set.

## 5. Baseline run

Chạy pipeline:

```text
baseline = hybrid search + RRF + rerank
```

Ghi bảng:

```markdown
| Query | Tags | Expected | Retrieved top 5 | Recall@5 | RR | Note |
|---|---|---|---|---:|---:|---|
```

Phân tích 5 lỗi lớn nhất. Với mỗi lỗi, ghi root cause:

- Query quá ngắn.
- Sai synonym/acronym.
- Chunk thiếu context.
- Reranker fail.
- Expected document bị ACL/index filter loại.
- Corpus thiếu dữ liệu.

## 6. Thêm query rewriting

Implement một rewriter đơn giản trước. Có thể dùng rule hoặc LLM.

Rule-based starter:

```python
GLOSSARY = {
    "pto": "paid time off nghỉ phép có lương",
    "429": "HTTP 429 Too Many Requests rate limit",
    "refund": "hoàn tiền refund",
}


def rewrite_query(query: str) -> str | None:
    lowered = query.lower()
    expansions = [value for key, value in GLOSSARY.items() if key in lowered]
    if not expansions:
        return None
    return f"{query} {' '.join(expansions)}"
```

Retrieval rule:

```python
queries = [original_query]
rewritten = rewrite_query(original_query)
if rewritten:
    queries.append(rewritten)
```

Chạy lại eval:

- Query rewriting có tăng Recall@5 ở nhóm `short`, `acronym`, `synonym` không?
- Có làm giảm nhóm `exact_lookup` không?
- Latency/cost tăng bao nhiêu nếu dùng LLM rewrite?

## 7. Thêm multi-query retrieval

Tạo variants:

```python
def generate_query_variants(query: str) -> list[str]:
    variants = [query]
    rewritten = rewrite_query(query)
    if rewritten:
        variants.append(rewritten)
    if "refund" in query.lower():
        variants.append(query.replace("refund", "hoàn tiền"))
    return list(dict.fromkeys(variants))[:3]
```

Mỗi variant chạy dense + BM25, sau đó RRF merge và rerank.

Yêu cầu report:

- Số retrieval calls/query.
- Recall@5 theo tag.
- Context precision.
- Ví dụ query cải thiện.
- Ví dụ query bị noise.

## 8. Thêm contextual retrieval

Tạo field `contextual_text`:

```python
def contextual_text(chunk: dict) -> str:
    section = " > ".join(chunk["section_path"])
    return "\n".join(
        [
            f"Document: {chunk['title']}",
            f"Section: {section}",
            f"Text: {chunk['text']}",
        ]
    )
```

Index/embed bằng `contextual_text`, nhưng context gửi vào LLM vẫn nên dùng:

```text
Title, section, source_uri, original text
```

So sánh:

- Baseline embed `text`.
- Contextual embed `contextual_text`.

Câu hỏi cần trả lời:

- Nhóm query nào cải thiện?
- Index size/token embedding tăng bao nhiêu?
- Có chunk nào bị context sai làm retrieval lệch không?
- Có cần reindex version mới không?

## 9. Optional: HyDE

Tạo hypothetical document ngắn cho query:

```python
def mock_hyde(query: str) -> str:
    return f"Tài liệu nội bộ giải thích về {query}, bao gồm điều kiện áp dụng, giới hạn, ngoại lệ và ví dụ."
```

Embed HyDE text và retrieve. Report:

- HyDE cải thiện query ngắn không?
- Có làm retrieval lệch do text quá generic không?
- Có đảm bảo HyDE không được dùng làm citation không?

## 10. Optional: step-back

Tạo step-back query:

```python
def step_back(query: str) -> str | None:
    if "refund" in query.lower() or "hoàn tiền" in query.lower():
        return "refund policy điều kiện hoàn tiền thời hạn ngoại lệ theo gói"
    if "429" in query:
        return "API rate limit HTTP error troubleshooting"
    return None
```

Retrieve original + step-back. Report case nào step-back giúp tìm background nhưng vẫn cần original để có detail.

## 11. Optional: decomposition

Với comparison query, tách thủ công:

```python
def decompose(query: str) -> list[str]:
    lowered = query.lower()
    if "pro" in lowered and "enterprise" in lowered and "refund" in lowered:
        return ["Pro plan refund policy", "Enterprise plan refund policy"]
    return [query]
```

Yêu cầu:

- Trace result theo subquery.
- Final answer có citation cho từng bên so sánh.
- Nếu thiếu evidence cho một bên, answer phải nói thiếu thông tin thay vì đoán.

## 12. Optional: corrective RAG

Thêm rule:

```python
def should_retry(top_results: list[dict], expected_min_score: float = 0.2) -> bool:
    if not top_results:
        return True
    return top_results[0].get("rerank_score", 0.0) < expected_min_score
```

Nếu retry:

1. Dùng rewritten query nếu chưa dùng.
2. Tăng top_k.
3. Nếu vẫn yếu, trả về "không đủ thông tin trong tài liệu" hoặc hỏi clarification.

## 13. Final decision report

Nộp báo cáo:

```markdown
# Day 38 Advanced RAG Report

## Corpus and golden set
- Number of chunks:
- Number of queries:
- Tags:

## Results
| Pipeline | Recall@5 | MRR | Context precision | p95 latency | Estimated cost/query |
|---|---:|---:|---:|---:|---:|
| baseline hybrid + rerank | | | | | |
| + query rewriting | | | | | |
| + multi-query | | | | | |
| + contextual retrieval | | | | | |

## Decision
- Keep:
- Do not keep:
- Rollout condition:
- Risks:
- Monitoring:
```

Quy tắc quyết định:

- Giữ query rewriting nếu nhóm `short/synonym/acronym` cải thiện rõ và exact lookup không regression.
- Giữ contextual retrieval nếu chunk thiếu context cải thiện mà index cost chấp nhận được.
- Chỉ giữ multi-query nếu tăng Recall đáng kể hơn phần latency/cost/noise tăng thêm.
- Không giữ HyDE/agentic/decomposition nếu chưa có query category cần chúng.

## 14. Quiz tự kiểm tra

1. Vì sao query rewrite không nên thay thế hoàn toàn original query?
2. RRF giải quyết vấn đề gì khi multi-query tạo nhiều result lists?
3. Contextual retrieval nên cite `contextual_text` hay source text gốc?
4. Khi nào bạn chọn decomposition thay vì multi-query?
5. Corrective RAG cần giới hạn gì để tránh cost spike?
6. GraphRAG phù hợp với loại câu hỏi nào trong corpus của bạn?

## 15. Tiêu chí hoàn thành

- [ ] Có baseline metrics.
- [ ] Có ít nhất 20 queries trong golden set.
- [ ] Có eval theo tag.
- [ ] Có query rewriting và so sánh before/after.
- [ ] Có contextual retrieval và so sánh before/after.
- [ ] Có phân tích trade-off latency/cost.
- [ ] Có decision report cuối cùng.
- [ ] Có câu trả lời production readiness cho pipeline bạn chọn.
