# Exercise: Thêm Reranker Vào Pipeline Day 36

## Mục tiêu

Sau bài tập này bạn sẽ có một pipeline RAG retrieval gần production:

```text
BM25 top 50 + Vector top 50
  -> RRF merge
  -> ACL filter
  -> dedupe
  -> rerank top 50
  -> final top 5/10
  -> evaluate Recall@k / MRR
```

Thời lượng đề xuất: 120-180 phút.

## 1. Chuẩn bị

Yêu cầu:

- Python 3.10+.
- Pipeline Day 36 đã có BM25, vector search và RRF.
- Một corpus nhỏ có `chunk_id`, `document_id`, `tenant_id`, `acl_roles`, `title`, `text`, `source_uri`.
- Một query set có qrels.

Cài thư viện nếu muốn chạy BGE reranker local:

```bash
pip install sentence-transformers numpy
```

Nếu muốn thử Cohere Rerank:

```bash
pip install cohere
export COHERE_API_KEY="..."
```

## 2. Dataset và qrels tối thiểu

Tạo file hoặc object Python tương đương:

```python
QUERIES = [
    {
        "query_id": "q001",
        "query": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm 2026?",
        "tags": ["policy", "version", "vietnamese"],
    },
    {
        "query_id": "q002",
        "query": "VPN error 809 xử lý như thế nào?",
        "tags": ["keyword-heavy", "incident"],
    },
    {
        "query_id": "q003",
        "query": "Can contractor access production database?",
        "tags": ["english", "acl", "security"],
    },
]

QRELS = {
    "q001": {"hr_leave_2026:chunk_003"},
    "q002": {"it_vpn_runbook:chunk_007"},
    "q003": {"security_access_policy:chunk_011"},
}
```

Mở rộng lên ít nhất 30 query nếu muốn kết quả có ý nghĩa hơn. Nên có query tốt, query khó, query tiếng Việt không dấu, acronym, mã lỗi, và query trộn English/Vietnamese.

## 3. Step 1 - Chạy baseline Hybrid Search

Từ Day 36, viết hàm trả về danh sách `chunk_id` sau RRF, chưa rerank.

```python
def run_hybrid_only(query: str, top_k: int = 10) -> list[str]:
    bm25_hits = bm25_search(query, top_k=50)
    vector_hits = vector_search(query, top_k=50)
    merged = reciprocal_rank_fusion([bm25_hits, vector_hits])
    permitted = acl_filter(merged)
    deduped = dedupe(permitted)
    return [hit.chunk_id for hit in deduped[:top_k]]
```

Yêu cầu:

- Không có chunk khác tenant.
- Không có chunk user không có quyền.
- Có log số lượng candidate sau từng bước.

## 4. Step 2 - Thêm BGE reranker

```python
from sentence_transformers import CrossEncoder


class LocalBgeReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, query: str, candidates: list[dict], top_n: int = 10) -> list[dict]:
        pairs = [
            (
                query,
                "Title: {title}\nSection: {section}\nText: {text}".format(
                    title=item.get("title", ""),
                    section=" > ".join(item.get("section_path", [])),
                    text=item["text"][:2500],
                ),
            )
            for item in candidates
        ]
        scores = self.model.predict(pairs)

        ranked = sorted(
            zip(candidates, scores, strict=True),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [
            {
                **candidate,
                "rerank_score": float(score),
                "final_rank": index + 1,
            }
            for index, (candidate, score) in enumerate(ranked[:top_n])
        ]
```

Pipeline:

```python
def run_hybrid_plus_rerank(query: str, reranker: LocalBgeReranker) -> list[str]:
    bm25_hits = bm25_search(query, top_k=50)
    vector_hits = vector_search(query, top_k=50)
    merged = reciprocal_rank_fusion([bm25_hits, vector_hits])
    permitted = acl_filter(merged)
    deduped = dedupe(permitted)

    candidates = [hit.to_dict() for hit in deduped[:50]]
    ranked = reranker.rerank(query, candidates, top_n=10)
    return [item["chunk_id"] for item in ranked]
```

Nếu máy yếu, giảm `rerank_k` xuống 20 trước, sau đó benchmark lại top 50.

## 5. Step 3 - Optional Cohere Rerank

Dùng managed API để so sánh baseline nhanh:

```python
import os

import cohere


class CohereRerankClient:
    def __init__(self, model: str = "rerank-v4.0-pro") -> None:
        self.client = cohere.Client(token=os.environ["COHERE_API_KEY"])
        self.model = model

    def rerank(self, query: str, candidates: list[dict], top_n: int = 10) -> list[dict]:
        documents = [
            "Title: {title}\nText: {text}".format(
                title=item.get("title", ""),
                text=item["text"][:2500],
            )
            for item in candidates
        ]
        response = self.client.v2.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=top_n,
            max_tokens_per_doc=1200,
        )

        ranked = []
        for rank, result in enumerate(response.results, start=1):
            item = dict(candidates[result.index])
            item["rerank_score"] = float(result.relevance_score)
            item["final_rank"] = rank
            ranked.append(item)
        return ranked
```

Chỉ chạy phần này nếu dữ liệu được phép gửi ra ngoài. Nếu corpus có PII hoặc dữ liệu nội bộ nhạy cảm, dùng dữ liệu giả lập hoặc bỏ qua managed API.

## 6. Step 4 - Evaluation

```python
def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def mrr_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def evaluate(run: dict[str, list[str]], qrels: dict[str, set[str]]) -> dict[str, float]:
    recall_5 = []
    mrr_10 = []
    for query_id, relevant_ids in qrels.items():
        ranked_ids = run.get(query_id, [])
        recall_5.append(recall_at_k(ranked_ids, relevant_ids, 5))
        mrr_10.append(mrr_at_k(ranked_ids, relevant_ids, 10))

    total = len(qrels) or 1
    return {
        "Recall@5": sum(recall_5) / total,
        "MRR@10": sum(mrr_10) / total,
    }
```

Chạy:

```python
hybrid_run = {
    item["query_id"]: run_hybrid_only(item["query"], top_k=10)
    for item in QUERIES
}

reranker = LocalBgeReranker()
rerank_run = {
    item["query_id"]: run_hybrid_plus_rerank(item["query"], reranker)
    for item in QUERIES
}

print("Hybrid only:", evaluate(hybrid_run, QRELS))
print("Hybrid + rerank:", evaluate(rerank_run, QRELS))
```

## 7. Step 5 - Benchmark latency

```python
import statistics
import time


def benchmark(fn, queries: list[dict], repeat: int = 3) -> dict[str, float]:
    latencies = []
    for _ in range(repeat):
        for item in queries:
            started = time.perf_counter()
            fn(item["query"])
            latencies.append((time.perf_counter() - started) * 1000)

    latencies = sorted(latencies)
    p95_index = int(0.95 * (len(latencies) - 1))
    return {
        "avg_ms": statistics.mean(latencies),
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[p95_index],
        "max_ms": max(latencies),
    }
```

Đo riêng:

- Hybrid only.
- Hybrid + BGE rerank top 20.
- Hybrid + BGE rerank top 50.
- Optional Hybrid + Cohere rerank top 50.

## 8. Report cần nộp

```markdown
| Pipeline | Recall@5 | MRR@10 | p50 ms | p95 ms | Cost/1K query | Ghi chú |
|---|---:|---:|---:|---:|---:|---|
| Hybrid only | | | | | | |
| Hybrid + BGE top 20 | | | | | | |
| Hybrid + BGE top 50 | | | | | | |
| Hybrid + Cohere top 50 | | | | | | |
```

Thêm phân tích:

- 5 query improved sau rerank.
- 5 query regressed sau rerank.
- Query nào không được cải thiện vì chunk đúng không nằm trong candidate pool?
- `rerank_k=20` hay `rerank_k=50` đáng dùng hơn theo SLA?
- Nếu bật production, bạn dùng BGE self-host hay Cohere managed? Vì sao?

## 9. Quiz

1. Vì sao cần retrieve top 50/100 rồi mới rerank top 5/10?
2. Reranking cải thiện Recall@50 hay Recall@5? Giải thích.
3. Nếu p95 tăng từ 450ms lên 1.600ms sau rerank, bạn xử lý thế nào?
4. Nếu dùng Cohere Rerank cho tài liệu nội bộ, bạn phải kiểm tra những điều kiện gì?
5. Khi nào không nên dùng reranker?

## 10. Acceptance criteria

- [ ] Có pipeline Hybrid only chạy được.
- [ ] Có pipeline Hybrid + rerank chạy được.
- [ ] ACL filter chạy trước rerank.
- [ ] Có số liệu Recall@5 và MRR@10 trước/sau rerank.
- [ ] Có benchmark p50/p95.
- [ ] Có bảng so sánh ít nhất 2 cấu hình `rerank_k`.
- [ ] Có phân tích improved/regressed query.
- [ ] Có câu trả lời production readiness rõ ràng.

## 11. Câu trả lời production readiness mẫu

Ví dụ câu trả lời tốt:

```text
Có thể dùng reranker trong production cho nhóm query policy/support vì Hybrid + BGE top 50 tăng MRR@10 từ 0.61 lên 0.78 và Recall@5 từ 0.70 lên 0.84 trên 120 query eval. p95 retrieval tăng từ 420ms lên 780ms, vẫn dưới SLA 1.200ms. Hệ thống đã filter tenant/ACL trước rerank, có timeout 800ms và fallback về RRF rank. Giai đoạn đầu bật bằng feature flag cho 20% internal traffic, log before/after rank và theo dõi citation correctness.
```

Ví dụ câu trả lời chưa đạt:

```text
Nên dùng reranker vì nó thông minh hơn vector search.
```

Câu trả lời chưa đạt vì không có metric, latency, security condition, fallback và rollout plan.
