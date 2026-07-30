# Document: Vector DB Cheat Sheet Và Runbook

## 1. Mental model nhanh

Vector DB trong RAG tương đương một search service có index lifecycle, không phải chỉ là bảng lưu array float.

```text
Documents
  -> parse
  -> chunk
  -> embed
  -> upsert vector + metadata
  -> query vector + mandatory filters
  -> rerank
  -> answer with citations
```

Ba lỗi production phổ biến:

1. Search không filter theo tenant/ACL.
2. Đổi embedding model nhưng vẫn dùng chung collection cũ.
3. Không có delete/reindex path nên câu trả lời dùng dữ liệu stale.

## 2. Decision matrix

| Context | Lựa chọn hợp lý | Lý do |
|---|---|---|
| MVP, đã có Postgres, dưới vài triệu chunk | pgvector | Ít service, backup quen thuộc, đủ tốt cho scale vừa |
| RAG self-host nghiêm túc, cần filter mạnh | Qdrant | API rõ, HNSW tốt, payload filtering tốt |
| Workload vector rất lớn, đội infra mạnh | Milvus | Scale-out tốt, phù hợp corpus lớn |
| Cần managed service và ship nhanh | Pinecone | Giảm ops, có namespace/managed capacity |
| Cần schema/search platform giàu tính năng | Weaviate | Nhiều feature search/schema |
| Notebook, demo, local prototype | Chroma | Dễ bắt đầu, không nên là mặc định production |

## 3. Sizing nhanh

Raw vector storage:

```text
raw_vector_bytes = number_of_chunks * dimension * bytes_per_float
```

Với float32, `bytes_per_float = 4`.

| Chunks | Dimension | Raw vector |
|---:|---:|---:|
| 100K | 768 | ~307 MB |
| 1M | 768 | ~3.1 GB |
| 1M | 1024 | ~4.1 GB |
| 1M | 1536 | ~6.1 GB |
| 10M | 1024 | ~41 GB |

Thực tế cần cộng thêm HNSW/IVF overhead, payload, WAL, snapshots, replicas, cache và dung lượng tạm khi reindex.

## 4. ANN tuning cheat sheet

| Kỹ thuật | Tham số | Tăng tham số | Giảm tham số |
|---|---|---|---|
| HNSW | `M` | Recall tốt hơn, RAM/build time tăng | Ít RAM hơn, có thể giảm recall |
| HNSW | `ef_construction` | Index tốt hơn, build chậm hơn | Build nhanh hơn, recall có thể giảm |
| HNSW | `ef_search` | Recall tốt hơn, query chậm hơn | Latency tốt hơn, recall giảm |
| IVF | `lists`/`nlist` | Nhiều cluster hơn | Ít cluster hơn |
| IVF | `probes`/`nprobe` | Recall tốt hơn, query chậm hơn | Query nhanh hơn, recall giảm |
| PQ | code size/quantization | Tiết kiệm memory/disk | Có thể giảm ranking quality |

Nguyên tắc: tune bằng bảng benchmark, không tune bằng cảm giác.

```markdown
| Config | Recall@5 | MRR@10 | p95 search ms | RAM/storage | Ghi chú |
|---|---:|---:|---:|---:|---|
| exact baseline | | | | | |
| hnsw default | | | | | |
| hnsw ef_search=100 | | | | | |
| hnsw ef_search=200 | | | | | |
| quantized | | | | | |
```

## 5. Metadata bắt buộc

| Field | Bắt buộc? | Mục đích |
|---|---|---|
| `tenant_id` | Có | Multi-tenancy |
| `acl_roles` hoặc `acl_subjects` | Có | Permission-aware retrieval |
| `document_id` | Có | Delete/update/citation |
| `chunk_id` | Có | Debug và citation |
| `source_uri` | Có | Trace về tài liệu gốc |
| `page_start`, `page_end` | Nên có | Citation chính xác |
| `embedding_model` | Có | Tránh trộn model |
| `dimension` | Có | Validate vector |
| `metric` | Có | Validate similarity |
| `chunking_strategy` | Có | Reproduce/reindex |
| `index_version` | Có | Blue/green và rollback |
| `text_hash` | Nên có | Detect thay đổi |
| `deleted_at` hoặc `deleted` | Có | Delete path |

## 6. Mẫu Docker Compose cho Qdrant local

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: "dev-local-key-change-me"

volumes:
  qdrant_data:
```

Production cần thêm network policy, secret manager, persistent volume class phù hợp, backup/snapshot job, resource requests/limits và monitoring.

## 7. Mẫu pgvector migration

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    acl_roles TEXT[] NOT NULL,
    index_version TEXT NOT NULL,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX rag_chunks_filter_idx
    ON rag_chunks (tenant_id, index_version)
    WHERE deleted_at IS NULL;

CREATE INDEX rag_chunks_acl_idx
    ON rag_chunks USING gin (acl_roles);

CREATE INDEX CONCURRENTLY rag_chunks_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

## 8. Runbook ingestion

1. Nhận document event.
2. Parse document và lưu raw source vào object storage.
3. Chunk theo strategy versioned.
4. Tính `text_hash` cho từng chunk.
5. Embed theo model versioned.
6. Validate dimension và metric.
7. Upsert batch vào Vector DB với `index_version`.
8. Tạo/refresh payload indexes nếu cần.
9. Ghi ingestion manifest: document count, chunk count, failed chunks.
10. Chạy smoke query và ACL test.

Idempotency key nên dựa trên:

```text
tenant_id + document_id + document_version + chunking_strategy + embedding_model + chunk_index
```

## 9. Runbook reindex

Khi cần reindex:

- Đổi embedding model.
- Đổi dimension hoặc metric.
- Đổi chunking strategy.
- Tune index lớn có thể ảnh hưởng ranking.
- Data corruption hoặc restore.

Các bước:

1. Tạo `new_index_version`.
2. Build collection/index mới hoặc partition mới.
3. Ingest toàn bộ corpus vào index mới.
4. Chạy offline eval.
5. Chạy ACL regression tests.
6. Chạy load test p95/p99.
7. Shadow traffic nếu hệ thống quan trọng.
8. Switch active version bằng config/feature flag.
9. Giữ version cũ cho rollback.
10. Cleanup sau retention window.

## 10. Runbook delete/update

Update document nên được xử lý như delete old chunks + insert new chunks trong cùng document version mới.

Delete:

1. Mark `deleted_at` hoặc `deleted=true` ngay.
2. Search filter loại bỏ deleted records.
3. Invalidate cache.
4. Xóa vật lý async nếu policy cho phép.
5. Audit log người/tác nhân đã xóa và số chunk bị ảnh hưởng.

Permission change:

1. Update ACL payload cho chunks liên quan.
2. Invalidate cache theo `document_id`.
3. Chạy test với user mất quyền để chắc chắn không còn retrieval được.

## 11. Runbook backup và restore

Backup schedule nên phụ thuộc RPO:

- Knowledge base ít đổi: daily snapshot có thể đủ.
- SaaS có cập nhật liên tục: snapshot + WAL/binlog/object manifest.
- Managed service: kiểm tra export/snapshot thực sự restore được không.

Restore drill:

1. Restore vào staging.
2. Verify collection config.
3. Verify vector count theo tenant.
4. Verify sample document/chunk.
5. Chạy 20-50 query qrels.
6. Chạy cross-tenant ACL test.
7. Ghi lại RTO/RPO thực tế.

## 12. Security checklist

- [ ] Retriever không nhận `tenant_id` từ client body.
- [ ] Mọi query đều có tenant filter.
- [ ] Mọi query đều có ACL filter.
- [ ] Query cache key chứa `tenant_id`, `acl_hash`, `index_version`.
- [ ] Logs không chứa raw confidential text khi chưa redaction.
- [ ] Có test user A không thấy tenant B.
- [ ] Có test user mất role không thấy tài liệu cũ.
- [ ] Có alert khi query thiếu mandatory filter.

## 13. Production readiness checklist

- [ ] Có owner vận hành.
- [ ] Có schema versioned.
- [ ] Có embedding/index compatibility checks.
- [ ] Có benchmark quality và latency.
- [ ] Có backup restore drill.
- [ ] Có reindex/rollback plan.
- [ ] Có delete/update path.
- [ ] Có multi-tenancy/ACL tests.
- [ ] Có dashboard p95/p99 latency, error rate, vector count.
- [ ] Có cost estimate theo growth 6-12 tháng.

## 14. Nguồn Kỹ Thuật Đã Đối Chiếu

- [Qdrant Python client](https://github.com/qdrant/qdrant-client): `create_collection`, `create_payload_index`, `upsert` và universal query API `query_points`.
- [Qdrant filtering](https://qdrant.tech/documentation/concepts/filtering/): payload conditions, `must`/`should` và array matching.
- [Qdrant points](https://qdrant.tech/documentation/concepts/points/): point ID hợp lệ là unsigned integer hoặc UUID; business `chunk_id` nên nằm trong payload.
- [pgvector](https://github.com/pgvector/pgvector): distance operators, HNSW/IVFFlat, filtered query và iterative index scans.

Các config trong bài là điểm bắt đầu để benchmark, không phải giá trị mặc định cho mọi workload. Hãy pin version image/package đã kiểm thử trong project thật và chạy restore/load test trước production.
