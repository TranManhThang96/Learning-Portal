# Day 33: Vector DB

Vector DB là tầng lưu trữ và truy vấn semantic retrieval cho RAG production. Bài học này được tách thành các phần riêng để dễ học, dễ thực hành và dễ dùng lại khi thiết kế hệ thống thật.

## Nội dung

1. [Lession: Vector DB production](./day-33-vector-db/lession.md)
   - ANN search, HNSW, IVF, PQ.
   - Metadata filtering, multi-tenancy, ACL.
   - Schema, index version, delete/reindex/backup.
   - Sharding, replication, monitoring.
   - Cách chọn pgvector, Qdrant, Milvus, Weaviate, Pinecone, Chroma.

2. [Document: Cheat sheet và runbook](./day-33-vector-db/document.md)
   - Bảng decision matrix.
   - Checklist production readiness.
   - Runbook ingestion, reindex, backup, restore, incident.
   - Mẫu schema và cấu hình gần production.

3. [Exercise: Hands-on benchmark](./day-33-vector-db/exercise.md)
   - Chạy Qdrant local.
   - Tạo collection có tenant/ACL/index version.
   - Upsert dữ liệu mẫu.
   - Search có metadata filter.
   - Đo latency, Hit@K/Recall@K và kiểm thử chống leak tenant.

## Mục tiêu sau bài học

- Giải thích được vì sao Vector DB không chỉ là nơi lưu embedding.
- Phân biệt được exact search và ANN search, hiểu trade-off recall/latency/cost.
- Biết khi nào dùng HNSW, IVF, PQ và cần tune tham số nào.
- Thiết kế schema có `tenant_id`, ACL, metadata, `index_version`, `embedding_model`, delete path.
- Chọn được pgvector, Qdrant, Milvus, Weaviate, Pinecone hoặc Chroma theo context.
- Trả lời được: dùng Vector DB trong production được không, và cần điều kiện gì.
