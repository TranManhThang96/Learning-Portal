# Day 33: Vector DB Production

## 1. Vector DB giải quyết vấn đề gì?

Trong RAG, câu hỏi của user được biến thành embedding, sau đó hệ thống tìm các đoạn tài liệu có ý nghĩa gần nhất:

```text
user query
  -> normalize + embed query
  -> vector search top_k
  -> metadata/ACL filtering
  -> optional BM25/hybrid search
  -> rerank
  -> build context with citations
  -> LLM answer
```

Nếu corpus chỉ có vài trăm chunk, exact search bằng NumPy hoặc Postgres đơn giản vẫn đủ để học. Khi corpus lên hàng trăm nghìn hoặc hàng triệu chunk, hệ thống cần Vector DB để:

- Tìm nearest neighbors nhanh hơn full scan.
- Lưu vector cùng metadata có thể filter.
- Hỗ trợ upsert/delete khi tài liệu thay đổi.
- Tách collection/namespace/index version khi đổi embedding model hoặc chunking strategy.
- Scale query throughput bằng shard/replica.
- Có backup, restore, monitoring và operational runbook.

Điểm quan trọng: Vector DB là một search engine chuyên cho vector, nhưng production vẫn cần các phẩm chất giống database: durability, access control, migration, rollback, observability và cost control.

## 2. Exact search và ANN search

Exact search so sánh query vector với toàn bộ document vectors:

```text
score_i = similarity(query_vector, document_vector_i)
sort score desc
return top_k
```

Exact search có recall cao nhất vì không bỏ sót vector nào, nhưng chi phí tăng tuyến tính theo số chunk. ANN, viết tắt của Approximate Nearest Neighbor, giảm latency bằng cách tìm gần đúng trong một cấu trúc index.

| Cách search | Ưu điểm | Nhược điểm | Khi nên dùng |
|---|---|---|---|
| Exact search | Dễ hiểu, recall tối đa, debug tốt | Chậm khi corpus lớn | Baseline, corpus nhỏ, eval |
| ANN search | Nhanh, scale tốt | Có thể mất recall | Production retrieval |
| Hybrid search | Kết hợp semantic + keyword | Phức tạp hơn, cần merge/rerank | Tài liệu nhiều mã lỗi, tên riêng, keyword |

ANN không phải phép màu. Mọi thay đổi như `top_k`, `ef_search`, `nprobe`, quantization, filter strategy hoặc embedding model đều phải được đánh giá lại bằng query set thật.

## 3. Similarity metric

Các metric phổ biến:

| Metric | Ý nghĩa | Lưu ý |
|---|---|---|
| Cosine similarity | So góc giữa hai vector | Phổ biến cho sentence embedding |
| Dot product | So tích vô hướng | Tốt khi model được train cho dot product |
| Euclidean/L2 | Khoảng cách hình học | Hay dùng trong một số ANN/index |

Không tự ý đổi metric sau khi đã index. Embedding model thường khuyến nghị metric phù hợp. Nếu dùng sai metric, retrieval có thể giảm chất lượng dù hệ thống vẫn chạy.

Vector score cũng không phải confidence score của câu trả lời. Score chỉ nói chunk gần query trong embedding space, không đảm bảo chunk đúng, mới nhất, đủ quyền truy cập hoặc đủ ngữ cảnh.

## 4. HNSW

HNSW, viết tắt của Hierarchical Navigable Small World, là ANN dạng graph. Mỗi vector là một node, các cạnh nối tới neighbors gần nhau. Khi query, thuật toán đi qua graph để tìm vùng gần query thay vì quét toàn bộ corpus.

Tham số chính:

| Tham số | Ý nghĩa | Tăng lên thì sao? |
|---|---|---|
| `M` | Số cạnh/neighbors mỗi node | Recall tốt hơn, RAM cao hơn |
| `ef_construction` | Độ kỹ khi build index | Index tốt hơn, build chậm hơn |
| `ef_search` | Số candidate khi query | Recall tốt hơn, latency cao hơn |

HNSW thường là lựa chọn mặc định tốt cho RAG v1 vì chất lượng cao, dễ benchmark và được nhiều Vector DB hỗ trợ. Trade-off lớn nhất là RAM và thời gian build index.

Best practice:

- Dùng exact search trên tập nhỏ làm baseline.
- Tune `ef_search` theo p95 latency và Recall@K, không tune bằng cảm giác.
- Benchmark có metadata filter, vì filter có thể làm recall giảm.
- Không trộn nhiều embedding dimension hoặc metric trong cùng một index.

## 5. IVF và PQ

IVF, viết tắt của Inverted File Index, chia vector space thành nhiều cluster. Khi query, hệ thống chỉ search một số cluster gần nhất.

| Tham số | Ý nghĩa | Trade-off |
|---|---|---|
| `nlist` hoặc `lists` | Số cluster khi build index | Nhiều hơn có thể nhanh hơn nhưng cần dữ liệu đủ lớn |
| `nprobe` hoặc `probes` | Số cluster được quét khi query | Cao hơn tăng recall, tăng latency |

PQ, viết tắt của Product Quantization, nén vector để giảm RAM/disk. PQ phù hợp khi corpus rất lớn hoặc chi phí lưu trữ là vấn đề, nhưng có thể làm ranking kém hơn.

Quy tắc production:

- IVF/PQ không nên là tối ưu đầu tiên cho dự án nhỏ.
- Dùng khi đã có benchmark chứng minh HNSW hoặc exact search không đáp ứng cost/latency.
- Sau khi bật PQ/quantization, phải đo lại Recall@5, Recall@10, MRR@10 và lỗi theo từng nhóm query.

## 6. Schema production cho vector record

Một record tốt không chỉ có `text` và `vector`. Nó cần đủ metadata để truy vết, filter, xóa, reindex và debug.

```json
{
  "id": "company_a:policy_001:2026-01:chunk_00012",
  "document_id": "policy_001",
  "chunk_id": "chunk_00012",
  "text": "Nhân viên full-time có 12 ngày nghỉ phép năm...",
  "vector": [0.01, -0.04, 0.21],
  "metadata": {
    "tenant_id": "company_a",
    "acl_roles": ["employee", "hr"],
    "source_uri": "s3://kb/company_a/hr/policy.pdf",
    "source_type": "pdf",
    "document_version": "2026-01",
    "chunk_index": 12,
    "page_start": 3,
    "page_end": 4,
    "section_path": ["HR", "Leave Policy"],
    "language": "vi",
    "embedding_model": "BAAI/bge-m3",
    "dimension": 1024,
    "metric": "cosine",
    "chunking_strategy": "markdown_heading_v2_800_120",
    "index_version": "rag-index-2026-05-10-bge-m3-v2",
    "text_hash": "sha256:...",
    "deleted_at": null,
    "created_at": "2026-05-10T08:00:00Z",
    "updated_at": "2026-05-10T08:00:00Z"
  }
}
```

Các field bắt buộc trong production:

- `tenant_id`: chống leak dữ liệu giữa khách hàng/phòng ban.
- `acl_roles` hoặc `acl_subjects`: kiểm soát quyền truy cập.
- `document_id`, `chunk_id`, `source_uri`, `page_start`, `page_end`: phục vụ citation và debug.
- `embedding_model`, `dimension`, `metric`: tránh trộn vector không tương thích.
- `chunking_strategy`, `index_version`: phục vụ reindex/rollback.
- `text_hash`: phát hiện tài liệu thay đổi.
- `deleted_at`: hỗ trợ soft delete và cleanup async.

## 7. Metadata filtering, tenant và ACL

Filter quyền phải chạy trong retriever hoặc database query, không giao cho prompt.

```text
tenant_id = current_user.tenant_id
AND deleted_at IS NULL
AND acl_roles intersects current_user.roles
AND index_version = active_index_version
```

Nếu LLM nhận chunk không đúng quyền rồi được yêu cầu "đừng trả lời phần này", dữ liệu đã bị leak vào prompt. Đây là lỗi security, không phải lỗi prompt engineering.

Các mô hình multi-tenancy:

| Mô hình | Ưu điểm | Nhược điểm | Khi dùng |
|---|---|---|---|
| Collection per tenant | Isolation rõ, dễ xóa tenant | Nhiều tenant gây khó ops | Ít tenant, yêu cầu bảo mật cao |
| Shared collection + tenant filter | Dễ vận hành, scale nhiều tenant | Sai filter là leak | SaaS nhiều tenant, có test bắt buộc |
| Namespace/partition | Cân bằng isolation và ops | Phụ thuộc DB hỗ trợ | Managed Vector DB hoặc Qdrant/Milvus tùy thiết kế |

Default tốt cho nhiều hệ thống B2B: shared collection hoặc namespace, nhưng mọi retriever function phải bắt buộc nhận `tenant_id` từ auth context, không nhận từ body do client gửi.

## 8. Sharding và replication

Sharding chia dữ liệu ra nhiều phần để tăng capacity. Replication nhân bản dữ liệu để tăng availability hoặc throughput.

| Khái niệm | Giải quyết | Trade-off |
|---|---|---|
| Sharding | Corpus quá lớn, write/read vượt một node | Query fan-out, rebalance, vận hành phức tạp |
| Replication | HA, read throughput | Tăng cost, cần consistency model |
| Partition theo tenant | Giảm blast radius | Có tenant lớn gây hotspot |
| Partition theo index version | Blue/green reindex dễ hơn | Tốn storage trong giai đoạn chuyển đổi |

Với RAG v1, đừng bắt đầu bằng topology quá phức tạp. Hãy có số liệu trước:

- Số chunk hiện tại và 6 tháng tới.
- QPS trung bình và peak.
- p95/p99 latency target.
- Kích thước vector dimension.
- Filter cardinality.
- Tốc độ ingest/update/delete.
- Yêu cầu data residency và backup.

## 9. Chọn Vector DB

| Công cụ | Khi nên dùng | Khi không nên dùng | Ghi chú production |
|---|---|---|---|
| pgvector | Team đã có Postgres, scale vừa, muốn ít service | QPS/vector workload lớn, cần cluster search chuyên dụng | Rất tốt cho MVP và hệ thống vừa |
| Qdrant | Muốn self-host production, API rõ, filter mạnh | Team không muốn vận hành thêm service | Default tốt cho nhiều RAG app |
| Milvus | Corpus rất lớn, workload vector nặng | Team thiếu thời gian ops | Mạnh nhưng vận hành phức tạp hơn |
| Weaviate | Cần schema/search features, hybrid/search module | Muốn stack tối giản | Cần benchmark filter và cost |
| Pinecone | Muốn managed service, ship nhanh, ít ops | Data residency/cost/lock-in nhạy cảm | Kiểm tra SLA, namespace, backup, export |
| Chroma | Local dev, notebook, prototype | Enterprise production mặc định | Tốt để học, không nên là mặc định production |

Decision framework:

1. Nếu đã có Postgres, corpus dưới vài triệu chunk, QPS vừa và team muốn đơn giản: bắt đầu với pgvector.
2. Nếu cần Vector DB riêng, self-host, filter tốt, triển khai nhanh: chọn Qdrant.
3. Nếu workload rất lớn, cần scale-out chuyên sâu: đánh giá Milvus hoặc managed service.
4. Nếu team nhỏ cần ra sản phẩm nhanh và data policy cho phép: Pinecone/managed service có thể hợp lý.
5. Nếu chỉ demo local: Chroma đủ, nhưng phải có kế hoạch migration trước production.

## 10. Code gần production với Qdrant

Ví dụ dưới đây minh họa collection versioned, payload index, upsert idempotent và search có tenant/ACL filter.

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)


COLLECTION = "rag_chunks_bge_m3_v2"
VECTOR_SIZE = 1024
ACTIVE_INDEX_VERSION = "rag-index-2026-05-10-bge-m3-v2"


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    roles: tuple[str, ...]


def get_client() -> QdrantClient:
    return QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ.get("QDRANT_API_KEY"),
        timeout=10,
    )


def ensure_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
            on_disk_payload=True,
        )

    for field in ("tenant_id", "acl_roles", "document_id", "index_version", "deleted"):
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD,
        )


def upsert_chunks(client: QdrantClient, chunks: Sequence[dict]) -> None:
    points = []
    for chunk in chunks:
        payload = {
            **chunk["metadata"],
            "text": chunk["text"],
            "deleted": "false",
            "index_version": ACTIVE_INDEX_VERSION,
        }
        points.append(
            PointStruct(
                id=chunk["id"],
                vector=chunk["embedding"],
                payload=payload,
            )
        )

    client.upsert(collection_name=COLLECTION, points=points, wait=True)


def search_chunks(
    client: QdrantClient,
    query_vector: list[float],
    auth: AuthContext,
    limit: int = 20,
):
    query_filter = Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=auth.tenant_id)),
            FieldCondition(key="deleted", match=MatchValue(value="false")),
            FieldCondition(key="index_version", match=MatchValue(value=ACTIVE_INDEX_VERSION)),
            FieldCondition(key="acl_roles", match=MatchAny(any=list(auth.roles))),
        ]
    )

    return client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=[
            "text",
            "document_id",
            "chunk_id",
            "source_uri",
            "page_start",
            "page_end",
            "section_path",
            "index_version",
        ],
        with_vectors=False,
    ).points
```

Production notes:

- `tenant_id` lấy từ auth/session, không lấy từ request body.
- `limit` cho retrieval có thể lớn hơn context final vì còn rerank.
- Không trả vector về API nếu không cần.
- Cần retry/backoff ở ingestion job, nhưng tránh retry vô hạn khi dữ liệu lỗi.
- `create_payload_index` nên chạy trong migration/init job, không chạy ở mọi request runtime.

## 11. Code gần production với pgvector

pgvector hợp khi bạn đã có Postgres và muốn giảm số service trong hệ thống.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    acl_roles TEXT[] NOT NULL,
    source_uri TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    embedding_model TEXT NOT NULL,
    metric TEXT NOT NULL DEFAULT 'cosine',
    chunking_strategy TEXT NOT NULL,
    index_version TEXT NOT NULL,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rag_chunks_tenant_idx
    ON rag_chunks (tenant_id, index_version)
    WHERE deleted_at IS NULL;

CREATE INDEX rag_chunks_document_idx
    ON rag_chunks (tenant_id, document_id);

CREATE INDEX rag_chunks_acl_roles_idx
    ON rag_chunks USING gin (acl_roles);

CREATE INDEX CONCURRENTLY rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

Query có filter:

```sql
BEGIN;
SET LOCAL hnsw.ef_search = 100;

SELECT
    id,
    document_id,
    chunk_id,
    text,
    source_uri,
    page_start,
    page_end,
    1 - (embedding <=> $1::vector) AS similarity
FROM rag_chunks
WHERE tenant_id = $2
  AND deleted_at IS NULL
  AND index_version = $3
  AND acl_roles && $4::text[]
ORDER BY embedding <=> $1::vector
LIMIT $5;

COMMIT;
```

Lưu ý:

- HNSW trong pgvector không cần training trước như IVFFlat.
- Với IVFFlat, cần chọn `lists` khi tạo index và tune `ivfflat.probes` khi query.
- Filter có thể làm ANN trả ít kết quả tốt hơn kỳ vọng; phải benchmark với filter thật.
- Postgres backup/restore quen thuộc là lợi thế lớn, nhưng vector index vẫn cần theo dõi bloat, vacuum, reindex và query plan.

## 12. Delete, reindex và blue/green index

Tài liệu trong RAG luôn thay đổi. Nếu không thiết kế lifecycle, hệ thống sẽ trả lời bằng dữ liệu cũ.

Delete path nên có:

1. Nhận event `document_deleted` hoặc `permission_changed`.
2. Mark `deleted_at` hoặc payload `deleted=true` ngay để search không lấy nữa.
3. Xóa vật lý async sau khi audit/retention cho phép.
4. Invalidate cache theo `tenant_id`, `document_id`, `acl_hash`, `index_version`.
5. Ghi log số chunk bị ảnh hưởng.

Blue/green reindex:

```text
current index: rag-index-2026-05-01-bge-m3-v1
new index:     rag-index-2026-05-10-bge-m3-v2

1. Build new collection/index ở background.
2. Ingest toàn bộ documents sang index mới.
3. Chạy eval: Recall@K, MRR, citation accuracy, latency, ACL tests.
4. Chạy shadow traffic nếu có.
5. Switch active_index_version.
6. Giữ index cũ đủ lâu để rollback.
7. Xóa index cũ sau retention window.
```

Không reindex đè trực tiếp lên index đang phục vụ production nếu hệ thống cần rollback nhanh.

## 13. Backup, restore và disaster recovery

Backup cần bao gồm:

- Vector data.
- Payload/metadata.
- Mapping document/chunk/source.
- Collection/index config.
- Embedding model name, dimension, metric.
- Ingestion manifest và `index_version`.

Restore test quan trọng hơn backup job. Một backup chưa từng restore thành công chỉ là giả định.

Checklist restore:

- Restore vào môi trường staging.
- Chạy count theo tenant/document.
- Chạy sample queries có qrels.
- Kiểm tra ACL không leak.
- So sánh p95 latency trước/sau restore.
- Ghi lại RTO/RPO thực tế.

## 14. Monitoring

Metric cần theo dõi:

| Nhóm | Metric |
|---|---|
| Retrieval quality | Recall@K offline, MRR@K, citation hit rate, no-answer rate |
| Latency | embedding latency, vector search p50/p95/p99, rerank latency, total RAG latency |
| Traffic | QPS, top_k distribution, filter cardinality, payload size |
| Index health | vector count, deleted count, index build time, shard/replica status |
| Security | cross-tenant denied count, missing ACL filter, unusual access |
| Cost | storage, replicas, managed service spend, embedding spend |

Log mỗi retrieval request nên có:

```json
{
  "request_id": "req_123",
  "tenant_id": "company_a",
  "user_id_hash": "u_hash",
  "index_version": "rag-index-2026-05-10-bge-m3-v2",
  "embedding_model": "BAAI/bge-m3",
  "top_k": 20,
  "filters": ["tenant_id", "acl_roles", "deleted", "index_version"],
  "result_chunk_ids": ["chunk_1", "chunk_2"],
  "scores": [0.82, 0.79],
  "latency_ms": {
    "embed": 45,
    "vector_search": 18,
    "rerank": 70
  }
}
```

Không log raw query hoặc raw chunk nếu dữ liệu nhạy cảm, trừ khi đã có policy redaction/retention rõ ràng.

## 15. Dùng được trong production không?

Có, Vector DB dùng được trong production và là thành phần cốt lõi của nhiều RAG system. Nhưng điều kiện tối thiểu là:

- Có schema rõ ràng cho tenant, ACL, metadata, source, version.
- Filter quyền được enforce ở backend/retriever, không dựa vào LLM.
- Có benchmark retrieval quality với query set thật.
- Có monitoring latency, recall, error rate và index health.
- Có runbook backup/restore, reindex, delete và rollback.
- Không trộn embedding model/dimension/metric trong cùng active index.
- Có test chống cross-tenant leak.
- Có owner vận hành Vector DB hoặc chọn managed service với SLA phù hợp.

Không nên production nếu chỉ có notebook demo, không có ACL test, không có delete/reindex path, không có restore test và không biết Recall@K hiện tại là bao nhiêu.

## 16. Checklist cuối bài

- [ ] Giải thích được exact search và ANN search.
- [ ] Phân biệt HNSW, IVF, PQ và trade-off.
- [ ] Thiết kế schema có tenant, ACL, metadata và version.
- [ ] Chọn được Vector DB theo scale, ops, cost và data policy.
- [ ] Viết được query có metadata filter đúng quyền.
- [ ] Có kế hoạch delete, reindex, backup, restore.
- [ ] Đo được Recall@K, MRR@K và p95 latency.
- [ ] Trả lời được điều kiện production readiness.

