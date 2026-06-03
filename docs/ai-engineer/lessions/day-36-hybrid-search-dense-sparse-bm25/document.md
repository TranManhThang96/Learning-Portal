# Document: Hybrid Search Cheat Sheet, Code Reference Và Runbook

## 1. Cheat sheet nhanh

Hybrid search là chiến lược retrieval kết hợp sparse search và dense search, thường merge bằng RRF rồi đưa candidates sang reranker hoặc context builder.

```text
query + auth context
  -> safe normalization
  -> mandatory filters
  -> BM25 top_n    \
                   -> RRF -> dedupe -> optional rerank -> context
  -> dense top_n   /
```

Ba lỗi production phổ biến:

1. Chỉ filter ACL ở vector path, quên filter ở BM25 path.
2. Normalize query làm mất mã lỗi, acronym, SKU hoặc số điều khoản.
3. Tối ưu theo average metric, không nhìn category như `exact_code` hoặc `no_diacritic`.

## 2. Decision matrix

| Context | Lựa chọn hợp lý | Vì sao |
|---|---|---|
| Corpus nhỏ, prototype nhanh | BM25-only hoặc dense-only | Đơn giản để có baseline |
| FAQ nhiều synonym, ít mã lỗi/tên riêng | Dense-first, vẫn benchmark BM25 | Semantic intent quan trọng |
| Enterprise docs, policy, support, developer docs | Hybrid BM25 + dense + RRF | Vừa có exact term vừa có semantic |
| Query có nhiều code/acronym/SKU | BM25 top_k cao hơn trong hybrid | Exact token quyết định relevance |
| Query dài, mô tả tự nhiên | Dense top_k cao hơn trong hybrid | Semantic signal nhiều hơn |
| Citation quality rất quan trọng | Hybrid + reranker | RRF tạo candidates, reranker xếp lại |
| BM25 miss nhiều vì synonym nhưng muốn sparse index | Cân nhắc SPLADE | Chỉ sau khi có eval và ops readiness |
| QPS cao, latency rất chặt | Hybrid không rerank hoặc rerank nhỏ | Cần parallel search và cache |

## 3. Retrieval config mẫu

```yaml
retrieval:
  active_index_version: "rag-index-2026-05-10-bge-m3-v2"
  bm25:
    enabled: true
    top_k: 50
    analyzer: "vi_en_code_safe_v1"
  dense:
    enabled: true
    top_k: 50
    embedding_model: "BAAI/bge-m3"
    metric: "cosine"
  fusion:
    strategy: "rrf"
    rrf_k: 60
    final_top_k: 20
    max_chunks_per_document: 2
  reranker:
    enabled: false
    top_k: 30
  security:
    require_tenant_filter: true
    require_acl_filter: true
  cache:
    enabled: true
    ttl_seconds: 300
```

Config phải được version hóa. Khi đổi `top_k`, `rrf_k`, analyzer, embedding model hoặc chunking strategy, nên ghi `retrieval_config_version` vào log và benchmark.

## 4. Python reference gần production

Ví dụ dưới đây dùng in-memory BM25 và in-memory dense matrix để dễ chạy trong bài học, nhưng cấu trúc code mô phỏng service thật:

- Có `AuthContext` và filter bắt buộc.
- Có `Chunk` chứa metadata cần cho citation/debug.
- Có normalizer an toàn, không xóa code/acronym.
- BM25 và dense retrieval tách thành retriever riêng.
- Hybrid service chạy hai path, RRF, dedupe và giới hạn diversity.
- Có metrics Hit@K, Recall@K, MRR@K.

Trong production, bạn thay `InMemoryBM25Retriever` bằng Elasticsearch/OpenSearch/Postgres full-text và thay `InMemoryDenseRetriever` bằng Vector DB như pgvector, Qdrant, Milvus, Weaviate hoặc Pinecone. Interface và contract không nên đổi.

### 4.1 Cài đặt cho local demo

```bash
pip install rank-bm25 sentence-transformers numpy
```

`sentence-transformers` hỗ trợ `SentenceTransformer(...).encode(...)` để encode documents và query. Nếu model hỗ trợ cosine search, dùng `normalize_embeddings=True` hoặc tự normalize trước khi dot product.

### 4.2 Code reference

```python
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, Sequence

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    roles: frozenset[str]
    permission_hash: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    tenant_id: str
    acl_roles: frozenset[str]
    source_uri: str
    page: int | None
    index_version: str
    deleted: bool = False


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float
    rank: int
    source: str


@dataclass(frozen=True)
class HybridHit:
    chunk: Chunk
    rrf_score: float
    final_rank: int
    bm25_rank: int | None
    dense_rank: int | None


@dataclass(frozen=True)
class RetrievalConfig:
    active_index_version: str
    bm25_top_k: int = 50
    dense_top_k: int = 50
    final_top_k: int = 10
    rrf_k: int = 60
    max_chunks_per_document: int = 2


class Retriever(Protocol):
    def search(self, query: str, auth: AuthContext, limit: int) -> list[SearchHit]:
        ...


CODE_SAFE_TOKEN_PATTERN = re.compile(
    r"[A-Za-z]+[+#]{1,2}|[A-Za-z0-9]+(?:[._:/-][A-Za-z0-9]+)+|\w+",
    re.UNICODE,
)


def normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def fold_vietnamese_accents(token: str) -> str:
    token = token.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", token)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize_code_safe(text: str) -> list[str]:
    text = normalize_query(text).lower()
    tokens = CODE_SAFE_TOKEN_PATTERN.findall(text)
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        folded = fold_vietnamese_accents(token)
        if folded != token:
            expanded.append(folded)
    return expanded


def is_visible(chunk: Chunk, auth: AuthContext, active_index_version: str) -> bool:
    return (
        chunk.tenant_id == auth.tenant_id
        and chunk.index_version == active_index_version
        and not chunk.deleted
        and bool(chunk.acl_roles.intersection(auth.roles))
    )


class InMemoryBM25Retriever:
    def __init__(self, chunks: Sequence[Chunk], active_index_version: str) -> None:
        self._chunks = list(chunks)
        self._active_index_version = active_index_version
        tokenized_corpus = [tokenize_code_safe(chunk.text) for chunk in self._chunks]
        self._bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, auth: AuthContext, limit: int) -> list[SearchHit]:
        tokens = tokenize_code_safe(query)
        if not tokens:
            return []

        scores = np.asarray(self._bm25.get_scores(tokens), dtype=np.float32)
        order = np.argsort(-scores)
        hits: list[SearchHit] = []

        for idx in order:
            chunk = self._chunks[int(idx)]
            if scores[idx] <= 0:
                continue
            if not is_visible(chunk, auth, self._active_index_version):
                continue
            hits.append(
                SearchHit(
                    chunk=chunk,
                    score=float(scores[idx]),
                    rank=len(hits) + 1,
                    source="bm25",
                )
            )
            if len(hits) >= limit:
                break

        return hits


class InMemoryDenseRetriever:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        model_name: str,
        active_index_version: str,
    ) -> None:
        self._chunks = list(chunks)
        self._model = SentenceTransformer(model_name)
        self._active_index_version = active_index_version
        self._doc_embeddings = self._model.encode(
            [chunk.text for chunk in self._chunks],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def search(self, query: str, auth: AuthContext, limit: int) -> list[SearchHit]:
        query_embedding = self._model.encode(
            [normalize_query(query)],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        scores = np.asarray(self._doc_embeddings @ query_embedding, dtype=np.float32)
        order = np.argsort(-scores)
        hits: list[SearchHit] = []

        for idx in order:
            chunk = self._chunks[int(idx)]
            if not is_visible(chunk, auth, self._active_index_version):
                continue
            hits.append(
                SearchHit(
                    chunk=chunk,
                    score=float(scores[idx]),
                    rank=len(hits) + 1,
                    source="dense",
                )
            )
            if len(hits) >= limit:
                break

        return hits


def rrf_fuse(rankings: Sequence[Sequence[SearchHit]], rrf_k: int) -> list[HybridHit]:
    by_chunk: dict[str, Chunk] = {}
    rrf_scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}

    for ranking in rankings:
        for hit in ranking:
            chunk_id = hit.chunk.chunk_id
            by_chunk[chunk_id] = hit.chunk
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + hit.rank)
            ranks.setdefault(chunk_id, {})[hit.source] = hit.rank

    ordered = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    return [
        HybridHit(
            chunk=by_chunk[chunk_id],
            rrf_score=score,
            final_rank=i + 1,
            bm25_rank=ranks.get(chunk_id, {}).get("bm25"),
            dense_rank=ranks.get(chunk_id, {}).get("dense"),
        )
        for i, (chunk_id, score) in enumerate(ordered)
    ]


def limit_document_diversity(
    hits: Iterable[HybridHit],
    final_top_k: int,
    max_chunks_per_document: int,
) -> list[HybridHit]:
    per_document_count: dict[str, int] = {}
    selected: list[HybridHit] = []

    for hit in hits:
        count = per_document_count.get(hit.chunk.document_id, 0)
        if count >= max_chunks_per_document:
            continue
        per_document_count[hit.chunk.document_id] = count + 1
        selected.append(
            HybridHit(
                chunk=hit.chunk,
                rrf_score=hit.rrf_score,
                final_rank=len(selected) + 1,
                bm25_rank=hit.bm25_rank,
                dense_rank=hit.dense_rank,
            )
        )
        if len(selected) >= final_top_k:
            break

    return selected


class HybridSearchService:
    def __init__(
        self,
        bm25: Retriever,
        dense: Retriever,
        config: RetrievalConfig,
    ) -> None:
        self._bm25 = bm25
        self._dense = dense
        self._config = config

    def search(self, query: str, auth: AuthContext) -> tuple[list[HybridHit], Mapping[str, float]]:
        normalized_query = normalize_query(query)

        started = time.perf_counter()
        bm25_hits = self._bm25.search(normalized_query, auth, self._config.bm25_top_k)
        bm25_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        dense_hits = self._dense.search(normalized_query, auth, self._config.dense_top_k)
        dense_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        fused = rrf_fuse([bm25_hits, dense_hits], self._config.rrf_k)
        final_hits = limit_document_diversity(
            fused,
            final_top_k=self._config.final_top_k,
            max_chunks_per_document=self._config.max_chunks_per_document,
        )
        merge_ms = (time.perf_counter() - started) * 1000

        metrics = {
            "bm25_ms": bm25_ms,
            "dense_ms": dense_ms,
            "merge_ms": merge_ms,
            "bm25_candidates": float(len(bm25_hits)),
            "dense_candidates": float(len(dense_hits)),
            "final_hits": float(len(final_hits)),
        }
        return final_hits, metrics
```

Trong online service thật, BM25 và dense nên chạy song song bằng async IO hoặc thread pool vì hai calls độc lập. Demo trên chạy tuần tự để dễ đọc.

### 4.3 Dataset mẫu

```python
CHUNKS = [
    Chunk(
        chunk_id="a:refund:001",
        document_id="refund_policy",
        text="Khách hàng có thể yêu cầu hoàn tiền trong 7 ngày cho gói Pro.",
        tenant_id="company_a",
        acl_roles=frozenset({"employee", "support"}),
        source_uri="s3://company-a/policy/refund.pdf",
        page=1,
        index_version="dev-index-v1",
    ),
    Chunk(
        chunk_id="a:invoice:001",
        document_id="invoice_vat",
        text="Để xuất hóa đơn VAT, cần cung cấp tên công ty và mã số thuế.",
        tenant_id="company_a",
        acl_roles=frozenset({"employee", "finance"}),
        source_uri="s3://company-a/finance/vat.pdf",
        page=2,
        index_version="dev-index-v1",
    ),
    Chunk(
        chunk_id="a:sla:001",
        document_id="sla_enterprise",
        text="Gói Enterprise có SLA uptime 99.9% và hỗ trợ P1 trong 2 giờ.",
        tenant_id="company_a",
        acl_roles=frozenset({"support"}),
        source_uri="s3://company-a/support/sla.pdf",
        page=4,
        index_version="dev-index-v1",
    ),
    Chunk(
        chunk_id="a:security:001",
        document_id="security_2fa",
        text="Tài khoản admin bắt buộc bật xác thực hai lớp 2FA.",
        tenant_id="company_a",
        acl_roles=frozenset({"admin"}),
        source_uri="s3://company-a/security/2fa.pdf",
        page=3,
        index_version="dev-index-v1",
    ),
    Chunk(
        chunk_id="a:api:001",
        document_id="api_rate_limit",
        text="API giới hạn 600 request mỗi phút. Vượt giới hạn trả về HTTP 429.",
        tenant_id="company_a",
        acl_roles=frozenset({"developer", "support"}),
        source_uri="s3://company-a/dev/api-rate-limit.md",
        page=None,
        index_version="dev-index-v1",
    ),
    Chunk(
        chunk_id="b:refund:001",
        document_id="refund_policy",
        text="Khách hàng công ty B có thể hoàn tiền trong 14 ngày.",
        tenant_id="company_b",
        acl_roles=frozenset({"employee", "support"}),
        source_uri="s3://company-b/policy/refund.pdf",
        page=1,
        index_version="dev-index-v1",
    ),
]

config = RetrievalConfig(active_index_version="dev-index-v1", final_top_k=5)
auth = AuthContext(
    tenant_id="company_a",
    roles=frozenset({"employee", "support", "developer"}),
    permission_hash="demo-permission-hash",
)

bm25 = InMemoryBM25Retriever(CHUNKS, active_index_version=config.active_index_version)
dense = InMemoryDenseRetriever(
    CHUNKS,
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    active_index_version=config.active_index_version,
)
service = HybridSearchService(bm25=bm25, dense=dense, config=config)

for query in ["tôi muốn lấy lại tiền", "HTTP 429", "SLA enterprise P1", "xuat VAT"]:
    hits, metrics = service.search(query, auth)
    print(query, metrics)
    for hit in hits:
        print(
            hit.final_rank,
            hit.chunk.document_id,
            hit.rrf_score,
            {"bm25_rank": hit.bm25_rank, "dense_rank": hit.dense_rank},
        )
```

## 5. Metrics helper

```python
def hit_at_k(results: Sequence[str], relevant: set[str], k: int) -> float:
    return float(any(doc_id in relevant for doc_id in results[:k]))


def recall_at_k(results: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(results[:k]).intersection(relevant)) / len(relevant)


def mrr_at_k(results: Sequence[str], relevant: set[str], k: int) -> float:
    for idx, doc_id in enumerate(results[:k], start=1):
        if doc_id in relevant:
            return 1.0 / idx
    return 0.0


def evaluate(
    predictions: Mapping[str, Sequence[str]],
    qrels: Mapping[str, set[str]],
    k: int,
) -> dict[str, float]:
    query_ids = list(qrels)
    return {
        f"hit@{k}": sum(hit_at_k(predictions[qid], qrels[qid], k) for qid in query_ids) / len(query_ids),
        f"recall@{k}": sum(recall_at_k(predictions[qid], qrels[qid], k) for qid in query_ids) / len(query_ids),
        f"mrr@{k}": sum(mrr_at_k(predictions[qid], qrels[qid], k) for qid in query_ids) / len(query_ids),
    }
```

## 6. Benchmark report template

```markdown
## Retrieval Benchmark

Corpus:
- Chunks:
- Documents:
- Languages:
- Index version:
- Embedding model:
- BM25 analyzer:

Query set:
- Total queries:
- semantic:
- keyword:
- mixed:
- exact_code:
- no_diacritic:
- english_mix:

| Config | Hit@5 | Recall@10 | MRR@10 | p95 ms | p99 ms | Notes |
|---|---:|---:|---:|---:|---:|---|
| BM25-only | | | | | | |
| Dense-only | | | | | | |
| Hybrid RRF | | | | | | |
| Hybrid RRF + reranker | | | | | | |

Findings:
1.
2.
3.

Decision:
- Roll out:
- Need more eval:
- Config:
- Risks:
```

## 7. Logging checklist

Log các field này ở retrieval layer:

- `request_id`, `tenant_id`, `permission_hash`.
- `query_hash`, không bắt buộc log raw query.
- `index_version`, `retrieval_config_version`.
- `bm25_top_k`, `dense_top_k`, `rrf_k`, `final_top_k`.
- `bm25_latency_ms`, `dense_latency_ms`, `merge_latency_ms`, `rerank_latency_ms`.
- `bm25_candidate_count`, `dense_candidate_count`, `final_hit_count`.
- Top chunk ids, document ids, source ids.
- Rank từ từng path: `bm25_rank`, `dense_rank`, `final_rank`.
- Filter summary: tenant, ACL mode, deleted filter, document version.
- Error và timeout theo từng backend.

Không log:

- Raw chunk text chứa PII.
- Raw user query nếu chưa có policy redaction.
- ACL list đầy đủ nếu có thể lộ cấu trúc quyền nhạy cảm.

## 8. Runbook: thay đổi analyzer

Thay analyzer là thay behavior của BM25 index. Không coi đây là config nhỏ.

1. Tạo analyzer version mới, ví dụ `vi_en_code_safe_v2`.
2. Reindex BM25 vào index mới hoặc shadow index.
3. Chạy benchmark theo query category.
4. So sánh đặc biệt nhóm `no_diacritic`, `exact_code`, `english_mix`.
5. Chạy regression tests cho `C++`, `C#`, `S3`, `HTTP 429`, `VAT`, `P1`.
6. Shadow traffic nếu hệ thống quan trọng.
7. Switch active index bằng feature flag/config.
8. Giữ index cũ trong retention window để rollback.

## 9. Runbook: đổi embedding model

1. Tạo `new_index_version`.
2. Embed lại toàn bộ chunks bằng model mới.
3. Build vector index mới với dimension/metric đúng.
4. Đảm bảo BM25 index và vector index cùng active version hoặc có mapping version rõ ràng.
5. Chạy benchmark dense-only và hybrid.
6. Chạy load test vì dimension/model mới có thể đổi latency.
7. Chạy ACL regression tests.
8. Switch bằng feature flag.
9. Monitor zero-result rate, answer citation quality và user feedback.

## 10. Debug playbook

Khi user báo "RAG trả lời sai", kiểm tra theo thứ tự:

1. Query có vào đúng tenant/index version không?
2. Chunk đúng có tồn tại trong corpus không?
3. Chunk đúng có bị `deleted` hoặc ACL filter loại không?
4. BM25 rank của chunk đúng là bao nhiêu?
5. Dense rank của chunk đúng là bao nhiêu?
6. RRF có merge chunk đúng vào final candidates không?
7. Dedupe/diversity policy có loại chunk đúng không?
8. Reranker có đẩy chunk đúng xuống thấp không?
9. Context builder có cắt mất đoạn chứa answer không?
10. LLM có dùng citation đúng nhưng tổng hợp sai không?

Nếu chunk đúng không nằm trong BM25 lẫn dense top 100, lỗi nằm ở ingestion/chunking/analyzer/embedding. Nếu chunk đúng có trong candidates nhưng không vào context, lỗi nằm ở fusion/rerank/context builder.

## 11. Production readiness checklist

- [ ] Có BM25 baseline, dense baseline và hybrid benchmark.
- [ ] Có query set tagged theo category.
- [ ] Có qrels cho top business workflows.
- [ ] Có analyzer phù hợp tiếng Việt, English mix và code token.
- [ ] Có vector index versioned theo embedding model/chunking strategy.
- [ ] Có mandatory tenant/ACL/deleted/index filters trong cả hai path.
- [ ] Có regression tests chống cross-tenant leak.
- [ ] Có RRF config versioned.
- [ ] Có logging rank/latency/candidate count đủ debug.
- [ ] Có p95/p99 latency SLO và load test.
- [ ] Có cache key chứa tenant, permission hash, index version và config version.
- [ ] Có runbook reindex/rollback.
- [ ] Có owner theo dõi quality metric sau release.

## 12. Quiz ngắn

1. Tại sao RRF ổn định hơn weighted score fusion khi mới bắt đầu?
2. Nếu query `HTTP 429` không ra đúng document, bạn kiểm tra analyzer hay embedding trước?
3. Vì sao cần benchmark theo category `no_diacritic`?
4. Khi nào SPLADE đáng để thử?
5. Vì sao cache key phải chứa `permission_hash`?
