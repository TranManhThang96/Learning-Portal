# Exercise: Xây Dựng Hybrid Retrieval BM25 + Dense + RRF

## Mục tiêu

Sau bài tập này bạn sẽ tự build một mini hybrid retriever có:

- BM25 search top-k.
- Dense vector search top-k.
- Merge bằng Reciprocal Rank Fusion.
- Query normalization an toàn cho tiếng Việt, acronym và code.
- Evaluation bằng Hit@K, Recall@K và MRR@K.
- Báo cáo so sánh BM25-only, dense-only và hybrid.

Thời lượng đề xuất: 120-180 phút.

## 1. Chuẩn bị

Yêu cầu:

- Python 3.10+.
- Máy có thể tải model từ Hugging Face nếu dùng `sentence-transformers`.

Cài đặt:

```bash
python -m venv .venv
source .venv/bin/activate
pip install rank-bm25 sentence-transformers numpy pandas pytest
```

Nếu máy yếu hoặc không muốn tải model, bạn vẫn có thể hoàn thành phần BM25, RRF và metrics trước. Dense path có thể thay bằng vector giả lập để hiểu pipeline.

## 2. Dataset mẫu

Tạo file `day36_hybrid_demo.py` và bắt đầu với dataset sau:

```python
DOCS = [
    {
        "id": "refund_policy",
        "tenant_id": "company_a",
        "roles": ["employee", "support"],
        "text": "Khách hàng có thể yêu cầu hoàn tiền trong 7 ngày cho gói Pro.",
    },
    {
        "id": "invoice_vat",
        "tenant_id": "company_a",
        "roles": ["employee", "finance"],
        "text": "Để xuất hóa đơn VAT, cần cung cấp tên công ty và mã số thuế.",
    },
    {
        "id": "sla_enterprise",
        "tenant_id": "company_a",
        "roles": ["support"],
        "text": "Gói Enterprise có SLA uptime 99.9% và hỗ trợ P1 trong 2 giờ.",
    },
    {
        "id": "password_reset",
        "tenant_id": "company_a",
        "roles": ["employee", "support"],
        "text": "Người dùng có thể reset mật khẩu bằng email đăng ký.",
    },
    {
        "id": "security_2fa",
        "tenant_id": "company_a",
        "roles": ["admin"],
        "text": "Tài khoản admin bắt buộc bật xác thực hai lớp 2FA.",
    },
    {
        "id": "api_rate_limit",
        "tenant_id": "company_a",
        "roles": ["developer", "support"],
        "text": "API giới hạn 600 request mỗi phút. Vượt giới hạn trả về HTTP 429.",
    },
    {
        "id": "refund_policy_b",
        "tenant_id": "company_b",
        "roles": ["employee", "support"],
        "text": "Khách hàng công ty B có thể yêu cầu hoàn tiền trong 14 ngày.",
    },
]

QUERIES = [
    {
        "id": "q_semantic_refund",
        "query": "tôi muốn lấy lại tiền gói Pro",
        "category": "semantic",
        "relevant": {"refund_policy"},
    },
    {
        "id": "q_keyword_vat",
        "query": "xuat VAT cho cong ty",
        "category": "keyword_no_diacritic",
        "relevant": {"invoice_vat"},
    },
    {
        "id": "q_keyword_sla",
        "query": "SLA enterprise P1",
        "category": "keyword",
        "relevant": {"sla_enterprise"},
    },
    {
        "id": "q_code_429",
        "query": "lỗi 429 là gì",
        "category": "exact_code",
        "relevant": {"api_rate_limit"},
    },
    {
        "id": "q_semantic_password",
        "query": "quên password thì làm sao vào lại tài khoản",
        "category": "mixed",
        "relevant": {"password_reset"},
    },
]
```

## 3. Implement tokenizer và normalizer

Yêu cầu:

- Không xóa số.
- Không làm hỏng `HTTP 429`, `2FA`, `C++`, `node.js`.
- Có lowercase cho token text thường.
- Có thể xử lý query không dấu ở mức cơ bản bằng accent-folding có kiểm soát.

Gợi ý:

```python
import re
import unicodedata


TOKEN_PATTERN = re.compile(
    r"[A-Za-z]+[+#]{1,2}|[A-Za-z0-9]+(?:[._:/-][A-Za-z0-9]+)+|\w+",
    re.UNICODE,
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fold_vietnamese_accents(token: str) -> str:
    token = token.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", token)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(normalize_text(text).lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        folded = fold_vietnamese_accents(token)
        if folded != token:
            expanded.append(folded)
    return expanded
```

Thử nhanh:

```python
assert "429" in tokenize("HTTP 429")
assert "2fa" in tokenize("Bật 2FA")
assert "bat" in tokenize("Bật 2FA")
assert tokenize("C++") != ["c"]
```

## 4. Implement BM25 search

```python
import numpy as np
from rank_bm25 import BM25Okapi


class BM25Search:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.index = BM25Okapi([tokenize(doc["text"]) for doc in docs])

    def search(self, query: str, tenant_id: str, roles: set[str], k: int) -> list[tuple[str, float]]:
        scores = np.asarray(self.index.get_scores(tokenize(query)), dtype=np.float32)
        order = np.argsort(-scores)
        results: list[tuple[str, float]] = []

        for idx in order:
            doc = self.docs[int(idx)]
            if scores[idx] <= 0:
                continue
            if doc["tenant_id"] != tenant_id:
                continue
            if not roles.intersection(doc["roles"]):
                continue
            results.append((doc["id"], float(scores[idx])))
            if len(results) >= k:
                break

        return results
```

## 5. Implement dense search

```python
from sentence_transformers import SentenceTransformer


class DenseSearch:
    def __init__(self, docs: list[dict], model_name: str) -> None:
        self.docs = docs
        self.model = SentenceTransformer(model_name)
        self.doc_embeddings = self.model.encode(
            [doc["text"] for doc in docs],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def search(self, query: str, tenant_id: str, roles: set[str], k: int) -> list[tuple[str, float]]:
        query_embedding = self.model.encode(
            [normalize_text(query)],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        scores = np.asarray(self.doc_embeddings @ query_embedding, dtype=np.float32)
        order = np.argsort(-scores)
        results: list[tuple[str, float]] = []

        for idx in order:
            doc = self.docs[int(idx)]
            if doc["tenant_id"] != tenant_id:
                continue
            if not roles.intersection(doc["roles"]):
                continue
            results.append((doc["id"], float(scores[idx])))
            if len(results) >= k:
                break

        return results
```

Model gợi ý để chạy local:

```python
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

Với hệ thống thật, chọn model bằng benchmark domain, không chọn chỉ vì model nổi tiếng.

## 6. Implement RRF

```python
def rrf_merge(rankings: list[list[tuple[str, float]]], rrf_k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _) in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
```

Không dùng:

```python
final_score = bm25_score + cosine_score
```

Lý do: BM25 score và cosine score không cùng scale.

## 7. Implement metrics

```python
def hit_at_k(results: list[str], relevant: set[str], k: int) -> float:
    return float(any(doc_id in relevant for doc_id in results[:k]))


def recall_at_k(results: list[str], relevant: set[str], k: int) -> float:
    return len(set(results[:k]).intersection(relevant)) / len(relevant)


def mrr_at_k(results: list[str], relevant: set[str], k: int) -> float:
    for rank, doc_id in enumerate(results[:k], start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0
```

Chạy benchmark:

```python
def evaluate_system(name: str, predictions: dict[str, list[str]], k: int = 5) -> dict[str, float]:
    by_id = {item["id"]: item for item in QUERIES}
    hit = []
    recall = []
    mrr = []
    for query_id, ranked_doc_ids in predictions.items():
        relevant = by_id[query_id]["relevant"]
        hit.append(hit_at_k(ranked_doc_ids, relevant, k))
        recall.append(recall_at_k(ranked_doc_ids, relevant, k))
        mrr.append(mrr_at_k(ranked_doc_ids, relevant, k))
    return {
        "system": name,
        f"hit@{k}": sum(hit) / len(hit),
        f"recall@{k}": sum(recall) / len(recall),
        f"mrr@{k}": sum(mrr) / len(mrr),
    }
```

## 8. Chạy so sánh ba hệ thống

```python
bm25 = BM25Search(DOCS)
dense = DenseSearch(DOCS, MODEL_NAME)

tenant_id = "company_a"
roles = {"employee", "support", "developer"}

bm25_predictions: dict[str, list[str]] = {}
dense_predictions: dict[str, list[str]] = {}
hybrid_predictions: dict[str, list[str]] = {}

for item in QUERIES:
    bm25_hits = bm25.search(item["query"], tenant_id, roles, k=5)
    dense_hits = dense.search(item["query"], tenant_id, roles, k=5)
    hybrid_hits = rrf_merge([bm25_hits, dense_hits], rrf_k=60)[:5]

    bm25_predictions[item["id"]] = [doc_id for doc_id, _ in bm25_hits]
    dense_predictions[item["id"]] = [doc_id for doc_id, _ in dense_hits]
    hybrid_predictions[item["id"]] = [doc_id for doc_id, _ in hybrid_hits]

    print("\\nQUERY:", item["query"], "|", item["category"])
    print("expected:", item["relevant"])
    print("bm25:", bm25_predictions[item["id"]])
    print("dense:", dense_predictions[item["id"]])
    print("hybrid:", hybrid_predictions[item["id"]])

print(evaluate_system("bm25", bm25_predictions, k=5))
print(evaluate_system("dense", dense_predictions, k=5))
print(evaluate_system("hybrid", hybrid_predictions, k=5))
```

## 9. Bài tập bắt buộc

1. Thêm ít nhất 15 documents nữa.
2. Thêm ít nhất 20 queries, chia đều cho các category:
   - `semantic`
   - `keyword`
   - `mixed`
   - `exact_code`
   - `no_diacritic`
   - `english_mix`
3. Báo cáo BM25-only vs dense-only vs hybrid.
4. Ghi ra 3 query BM25 thắng dense.
5. Ghi ra 3 query dense thắng BM25.
6. Ghi ra 3 query hybrid tốt hơn từng path riêng lẻ.
7. Thử `bm25_top_k` và `dense_top_k` lần lượt là 3, 5, 10, 20.
8. Thử `rrf_k` là 10, 30, 60, 100.
9. Kiểm tra tenant/ACL: user `company_a` không được thấy document `company_b`.
10. Viết kết luận production readiness.

## 10. Test bằng pytest

Tạo file `test_day36_hybrid.py`.

```python
def test_company_a_cannot_see_company_b():
    bm25 = BM25Search(DOCS)
    hits = bm25.search("hoàn tiền", tenant_id="company_a", roles={"employee"}, k=20)
    assert hits
    assert "refund_policy_b" not in [doc_id for doc_id, _ in hits]


def test_employee_cannot_see_admin_2fa_doc():
    bm25 = BM25Search(DOCS)
    hits = bm25.search("2FA admin", tenant_id="company_a", roles={"employee"}, k=20)
    assert "security_2fa" not in [doc_id for doc_id, _ in hits]


def test_rrf_keeps_dense_only_candidate():
    bm25_hits = [("doc_a", 10.0)]
    dense_hits = [("doc_b", 0.9)]
    fused = [doc_id for doc_id, _ in rrf_merge([bm25_hits, dense_hits])]
    assert "doc_a" in fused
    assert "doc_b" in fused
```

## 11. Mẫu báo cáo cần nộp

```markdown
# Day 36 Hybrid Retrieval Report

## Dataset

- Documents:
- Queries:
- Query categories:
- Embedding model:
- Analyzer/tokenizer:

## Metrics

| System | Hit@5 | Recall@5 | MRR@5 | Notes |
|---|---:|---:|---:|---|
| BM25-only | | | | |
| Dense-only | | | | |
| Hybrid RRF | | | | |

## Findings

1. BM25 mạnh ở:
2. Dense mạnh ở:
3. Hybrid cải thiện ở:
4. Query normalization làm sai ở:
5. ACL/filter test:

## Production Readiness

Hybrid search dùng được trong production không?

Trả lời:

Điều kiện còn thiếu trước production:

- Golden set tối thiểu 30-50 query có tag `keyword`, `semantic`, `no-diacritic`, `code-heavy` và `permission`.
- Tenant/ACL/deleted/index filters được enforce giống nhau ở BM25 path và dense path.
- Có p95/p99 latency, query timeout, fallback khi một retriever lỗi và regression test cho analyzer/embedding/index version.
```

## 12. Câu hỏi tự luận

1. Nếu query `HTTP 429` không retrieve được `api_rate_limit`, bạn debug theo thứ tự nào?
2. Nếu query "tôi muốn lấy lại tiền" BM25 miss nhưng dense đúng, bạn có nên thêm synonym dictionary không?
3. Vì sao query không dấu cần được đánh giá riêng ở corpus tiếng Việt?
4. Nếu hybrid tăng Hit@5 nhưng p95 latency vượt SLA, bạn tối ưu gì trước?
5. Khi nào bạn thêm reranker vào sau RRF?
6. Khi nào bạn cân nhắc SPLADE thay vì BM25?

## 13. Tiêu chí hoàn thành

- [ ] Code chạy được end-to-end.
- [ ] BM25, dense và hybrid đều có output riêng.
- [ ] RRF không dùng raw score fusion.
- [ ] Metrics được tính tự động.
- [ ] Có ít nhất 20 queries có qrels.
- [ ] Có category analysis.
- [ ] Có test tenant/ACL.
- [ ] Có kết luận production readiness rõ ràng.
