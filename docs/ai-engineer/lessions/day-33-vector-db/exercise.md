# Exercise: Xây Dựng Mini Vector DB Benchmark

## Mục tiêu

Sau bài tập này bạn sẽ có một mini retrieval service dùng Qdrant local, có schema gần production, metadata filtering, tenant/ACL test và benchmark đơn giản.

Thời lượng đề xuất: 90-150 phút.

## 1. Chuẩn bị

Yêu cầu:

- Docker.
- Python 3.10+.
- `pip install qdrant-client numpy pytest`.

Tạo `docker-compose.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

Chạy:

```bash
docker compose up -d
```

## 2. Dataset mẫu

Tạo 12 chunk giả lập. Trong dự án thật, embedding phải đến từ embedding model. Trong bài tập này dùng vector nhỏ 4 chiều để tập trung vào Vector DB behavior.

```python
CHUNKS = [
    {
        "id": "a:hr:leave:001",
        "text": "Nhân viên công ty A có 12 ngày nghỉ phép năm.",
        "vector": [0.90, 0.10, 0.00, 0.00],
        "metadata": {
            "tenant_id": "company_a",
            "document_id": "hr_leave",
            "chunk_id": "001",
            "acl_roles": ["employee", "hr"],
            "source_uri": "s3://company-a/hr/leave.pdf",
            "page_start": 1,
            "page_end": 1,
            "index_version": "dev-index-v1",
            "deleted": False,
        },
    },
    {
        "id": "a:finance:salary:001",
        "text": "Bảng lương chi tiết chỉ dành cho phòng finance.",
        "vector": [0.85, 0.15, 0.00, 0.05],
        "metadata": {
            "tenant_id": "company_a",
            "document_id": "finance_salary",
            "chunk_id": "001",
            "acl_roles": ["finance"],
            "source_uri": "s3://company-a/finance/salary.pdf",
            "page_start": 2,
            "page_end": 2,
            "index_version": "dev-index-v1",
            "deleted": False,
        },
    },
    {
        "id": "b:hr:leave:001",
        "text": "Nhân viên công ty B có 15 ngày nghỉ phép năm.",
        "vector": [0.91, 0.09, 0.00, 0.00],
        "metadata": {
            "tenant_id": "company_b",
            "document_id": "hr_leave",
            "chunk_id": "001",
            "acl_roles": ["employee", "hr"],
            "source_uri": "s3://company-b/hr/leave.pdf",
            "page_start": 1,
            "page_end": 1,
            "index_version": "dev-index-v1",
            "deleted": False,
        },
    },
]
```

Hãy tự thêm ít nhất 9 chunk nữa, gồm:

- 3 chunk cho `company_a`, role `employee`.
- 3 chunk cho `company_a`, role `admin` hoặc `finance`.
- 3 chunk cho `company_b`.

Đừng bỏ qua bước này: ba record mẫu ở trên chỉ là seed để dễ đọc. Benchmark và ACL test chỉ có ý nghĩa khi corpus có đủ dữ liệu gây nhiễu giữa tenant, role và document category.

Thêm validation trước khi upsert để lỗi hiện ra sớm:

```python
def validate_dataset(chunks: list[dict]) -> None:
    if len(chunks) < 12:
        raise ValueError("Cần ít nhất 12 chunks để benchmark không quá toy.")

    tenants = {item["metadata"]["tenant_id"] for item in chunks}
    if {"company_a", "company_b"} - tenants:
        raise ValueError("Dataset phải có cả company_a và company_b.")

    company_a_roles = {
        role
        for item in chunks
        if item["metadata"]["tenant_id"] == "company_a"
        for role in item["metadata"]["acl_roles"]
    }
    if "employee" not in company_a_roles or not ({"finance", "admin"} & company_a_roles):
        raise ValueError("company_a cần có ít nhất role employee và finance/admin.")
```

Gọi `validate_dataset(CHUNKS)` trước `upsert_chunks(CHUNKS)`.

## 3. Tạo collection

```python
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
from uuid import UUID, uuid5

COLLECTION = "day33_chunks"
INDEX_VERSION = "dev-index-v1"
POINT_ID_NAMESPACE = UUID("b9fd7a5f-ec35-4cb5-90ff-1f204c001cf0")

client = QdrantClient(url="http://localhost:6333")


def point_id_for_chunk(chunk_id: str) -> str:
    return str(uuid5(POINT_ID_NAMESPACE, chunk_id))

if COLLECTION not in {c.name for c in client.get_collections().collections}:
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
        on_disk_payload=True,
    )

for field in ["tenant_id", "acl_roles", "document_id", "index_version"]:
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name=field,
        field_schema=PayloadSchemaType.KEYWORD,
    )
client.create_payload_index(
    collection_name=COLLECTION,
    field_name="deleted",
    field_schema=PayloadSchemaType.BOOL,
)
```

Qdrant point ID chỉ nhận unsigned integer hoặc UUID. Hàm trên tạo UUID ổn định để upsert idempotent; business ID dễ đọc như `a:hr:leave:001` vẫn được giữ trong payload `chunk_id`.

## 4. Upsert dữ liệu

```python
def upsert_chunks(chunks: list[dict]) -> None:
    points = [
        PointStruct(
            id=point_id_for_chunk(item["id"]),
            vector=item["vector"],
            payload={
                **item["metadata"],
                "chunk_id": item["id"],
                "text": item["text"],
            },
        )
        for item in chunks
    ]
    client.upsert(collection_name=COLLECTION, points=points, wait=True)
```

Chạy `upsert_chunks(CHUNKS)`.

## 5. Search có tenant và ACL

```python
def search(query_vector: list[float], tenant_id: str, roles: list[str], limit: int = 5):
    query_filter = Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="index_version", match=MatchValue(value=INDEX_VERSION)),
            FieldCondition(key="deleted", match=MatchValue(value=False)),
            FieldCondition(key="acl_roles", match=MatchAny(any=roles)),
        ]
    )

    response = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=[
            "chunk_id",
            "text",
            "tenant_id",
            "document_id",
            "acl_roles",
            "source_uri",
        ],
        with_vectors=False,
    )
    return response.points
```

Test thủ công:

```python
results = search([0.90, 0.10, 0.00, 0.00], tenant_id="company_a", roles=["employee"])
for point in results:
    print(point.payload["chunk_id"], point.score, point.payload)
```

Kỳ vọng:

- Không có record `company_b`.
- Không có record chỉ dành cho `finance` nếu roles chỉ là `employee`.
- Result có `source_uri` để phục vụ citation.

## 6. Test chống leak tenant/ACL

Viết test bằng `pytest`:

```python
def test_company_a_employee_cannot_see_company_b():
    results = search([0.90, 0.10, 0.00, 0.00], "company_a", ["employee"], limit=20)
    assert results
    assert all(point.payload["tenant_id"] == "company_a" for point in results)


def test_employee_cannot_see_finance_only_document():
    results = search([0.85, 0.15, 0.00, 0.05], "company_a", ["employee"], limit=20)
    document_ids = {point.payload["document_id"] for point in results}
    assert "finance_salary" not in document_ids


def test_finance_can_see_finance_document():
    results = search([0.85, 0.15, 0.00, 0.05], "company_a", ["finance"], limit=20)
    document_ids = {point.payload["document_id"] for point in results}
    assert "finance_salary" in document_ids
```

## 7. Benchmark latency

```python
import statistics
import time


QUERIES = [
    ([0.90, 0.10, 0.00, 0.00], "company_a", ["employee"]),
    ([0.85, 0.15, 0.00, 0.05], "company_a", ["finance"]),
    ([0.91, 0.09, 0.00, 0.00], "company_b", ["employee"]),
]


def percentile(values: list[float], p: int) -> float:
    values = sorted(values)
    index = int((len(values) - 1) * p / 100)
    return values[index]


latencies_ms = []
for _ in range(100):
    for query_vector, tenant_id, roles in QUERIES:
        started = time.perf_counter()
        search(query_vector, tenant_id, roles)
        latencies_ms.append((time.perf_counter() - started) * 1000)

print("p50_ms", statistics.median(latencies_ms))
print("p95_ms", percentile(latencies_ms, 95))
```

Trong production, latency cần tính cả:

- Query embedding.
- Vector search.
- Hybrid/BM25 nếu có.
- Reranking.
- Context building.
- LLM generation.

## 8. Đánh giá Hit@K đơn giản

Tạo qrels:

```python
QRELS = [
    {
        "query_vector": [0.90, 0.10, 0.00, 0.00],
        "tenant_id": "company_a",
        "roles": ["employee"],
        "expected_document_id": "hr_leave",
    },
    {
        "query_vector": [0.91, 0.09, 0.00, 0.00],
        "tenant_id": "company_b",
        "roles": ["employee"],
        "expected_document_id": "hr_leave",
    },
]


def hit_at_k(k: int = 5) -> float:
    hits = 0
    for item in QRELS:
        results = search(item["query_vector"], item["tenant_id"], item["roles"], limit=k)
        document_ids = [point.payload["document_id"] for point in results]
        if item["expected_document_id"] in document_ids:
            hits += 1
    return hits / len(QRELS)


print("Hit@5", hit_at_k(5))
```

Mở rộng:

- Tạo ít nhất 20 query tiếng Việt thật.
- Mỗi query có expected document/chunk.
- So sánh `limit=5`, `limit=10`, `limit=20`.
- Nếu có reranker, đo trước và sau rerank.

## 9. Thử delete path

Mark document finance là deleted:

```python
client.set_payload(
    collection_name=COLLECTION,
    payload={"deleted": True},
    points=[point_id_for_chunk("a:finance:salary:001")],
    wait=True,
)
```

Chạy lại:

```python
results = search([0.85, 0.15, 0.00, 0.05], "company_a", ["finance"], limit=20)
assert "finance_salary" not in {point.payload["document_id"] for point in results}
```

Trong hệ thống thật, bạn nên delete theo `document_id` bằng filter hoặc duy trì danh sách point ids từ ingestion manifest.

## 10. Báo cáo cần nộp

Tạo một file báo cáo ngắn gồm:

```markdown
# Day 33 Vector DB Benchmark Report

## Decision

- Chọn Vector DB:
- Lý do:
- Khi nào cần đổi lựa chọn:

## Schema

- Vector dimension:
- Metric:
- Metadata bắt buộc:
- Tenant/ACL strategy:

## Benchmark

| Config | Hit@5 | p50 ms | p95 ms | Notes |
|---|---:|---:|---:|---|
| qdrant hnsw default | | | | |

## Security Tests

- company_a không thấy company_b:
- employee không thấy finance:
- deleted document không được retrieve:

## Production Readiness

- Backup plan:
- Reindex plan:
- Delete/update plan:
- Monitoring:
- Rủi ro còn lại:
```

## 11. Câu hỏi ôn tập

1. Vì sao score của Vector DB không phải confidence score?
2. Khi nào pgvector tốt hơn Qdrant?
3. HNSW `ef_search` tăng thì được gì và mất gì?
4. Vì sao metadata filter phải nằm trước hoặc trong retrieval?
5. Khi đổi embedding model, vì sao nên tạo index version mới?
6. Sharding và replication giải quyết hai vấn đề khác nhau như thế nào?
7. Điều kiện tối thiểu để Vector DB được dùng trong production là gì?
