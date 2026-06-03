# Day 40: Mini-project - Production RAG System

Day 40 tổng hợp toàn bộ Phase 5 thành một mini-project RAG gần production. Bài học này được tách thành các phần riêng để dễ học, dễ triển khai và dễ dùng làm portfolio.

## Nội dung

1. [Lession: Xây dựng Production RAG System end-to-end](./day-40-mini-project-production-rag-system/lession.md)
   - Upload/ingest tài liệu, parse, normalize, chunk, embed và index.
   - Query pipeline có permission filter, hybrid search, RRF, rerank, context builder, generation và citation validation.
   - Logging latency/token/cost, trace từng stage, eval report và production readiness.
   - Backend API, simple UI, Docker Compose, README, security/ACL và observability.

2. [Document: Template, checklist và runbook](./day-40-mini-project-production-rag-system/document.md)
   - Architecture template, project structure, API contract, schema, prompt contract.
   - Docker Compose mẫu, `.env.example`, README template, eval report template.
   - Checklist production readiness, security review, observability review và incident runbook.

3. [Exercise: Lab triển khai mini-project](./day-40-mini-project-production-rag-system/exercise.md)
   - Tạo repository mini-project.
   - Implement ingestion pipeline, query pipeline, UI, eval runner và report.
   - Chạy Docker Compose, benchmark latency/cost, kiểm thử ACL/citation/no-answer.
   - Trả lời câu hỏi: dùng được trong production không, và cần điều kiện gì.

## Mục tiêu sau bài học

- Build được một RAG system end-to-end có boundary rõ giữa indexing path, query path và eval path.
- Biết thiết kế schema metadata phục vụ citation, ACL, document lifecycle, reindex và rollback.
- Biết kết hợp dense retrieval, lexical retrieval, hybrid merge và reranking.
- Biết log trace theo từng stage để debug lỗi retrieval, rerank, prompt hoặc generation.
- Biết tạo golden set, chạy eval và viết release decision dựa trên metric.
- Biết trình bày production architecture, trade-off, limitation và điều kiện để đưa RAG vào production.
