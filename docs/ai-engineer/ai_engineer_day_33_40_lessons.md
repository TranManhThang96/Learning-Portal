# 8 Bai Hoc Tiep Theo Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 5 - Production RAG.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 33 | Vector DB | Vector DB decision note + collection schema + benchmark recall/latency |
| Day 34 | Chunking Strategies | Chunking benchmark tren 3 strategies |
| Day 35 | Metadata, Citation, Permission-aware RAG | Metadata schema + ACL filter + citation validator |
| Day 36 | Hybrid Search - Dense + Sparse + BM25 | BM25 + dense retrieval + RRF merge |
| Day 37 | Reranking | Hybrid + reranker before/after report |
| Day 38 | Advanced RAG Patterns | Decision report cho query rewrite, multi-query, contextual retrieval |
| Day 39 | RAG Evaluation | Golden set 30-50 questions + eval report |
| Day 40 | Mini-project - Production RAG System | Backend API + simple UI + Docker Compose + eval result |

## File Chi Tiet

| Ngay | File |
|---:|---|
| Day 33 | [Vector DB](./bai-hoc-day-33-40/day-33-vector-db.md) |
| Day 34 | [Chunking Strategies](./bai-hoc-day-33-40/day-34-chunking-strategies.md) |
| Day 35 | [Metadata, Citation, Permission-aware RAG](./bai-hoc-day-33-40/day-35-metadata-citation-permission-aware-rag.md) |
| Day 36 | [Hybrid Search - Dense + Sparse + BM25](./bai-hoc-day-33-40/day-36-hybrid-search-dense-sparse-bm25.md) |
| Day 37 | [Reranking](./bai-hoc-day-33-40/day-37-reranking.md) |
| Day 38 | [Advanced RAG Patterns](./bai-hoc-day-33-40/day-38-advanced-rag-patterns.md) |
| Day 39 | [RAG Evaluation](./bai-hoc-day-33-40/day-39-rag-evaluation.md) |
| Day 40 | [Mini-project - Production RAG System](./bai-hoc-day-33-40/day-40-mini-project-production-rag-system.md) |

## Tong Quan Learning Path

Day 33-40 hoan tat Phase 5: Production RAG. Neu Day 31-32 da dat nen mong ve architecture va embedding benchmark, nhom bai nay dua RAG len muc production-style: vector index co metadata, chunking co citation, permission-aware retrieval, hybrid search, reranking, advanced retrieval patterns, evaluation va mini-project hoan chinh.

Trong production, RAG khong phai mot flow `embed -> search -> ask LLM`. No la mot data system co ingestion, index lifecycle, permission, citation, eval regression va observability. Muc tieu cua Day 33-40 la lam ro cac boundary do.

## Artifact Nen Co Sau Day 33-40

| Artifact | Den tu ngay | Gia tri production |
|---|---:|---|
| Vector DB decision note | Day 33 | Chon pgvector/Qdrant/Milvus/Pinecone dua tren scale va ops |
| Collection schema co metadata | Day 33 | Quan ly tenant, ACL, index version, delete/reindex |
| Chunking benchmark | Day 34 | Chon strategy dua tren retrieval/citation quality |
| Permission-aware metadata schema | Day 35 | Giam risk cross-tenant leak va citation ao |
| Hybrid search pipeline | Day 36 | Ket hop semantic search va exact keyword search |
| Reranker before/after report | Day 37 | Tang top context precision va citation quality |
| Advanced RAG decision report | Day 38 | Them pattern dua tren eval, khong them complexity cam tinh |
| Golden eval set | Day 39 | Regression suite cho RAG |
| Production RAG mini-project | Day 40 | Portfolio artifact co API, UI, Docker, eval va README |

## Production Gate

Truoc khi dua RAG system vao capstone hoac demo public, can co it nhat:

- Golden eval set co 30-50 queries, qrels va tags.
- Version cho corpus, chunking strategy, embedding model, index, reranker, prompt va eval set.
- Metadata schema co tenant, ACL, source, page/section, document version va index version.
- Citation validator: model khong duoc cite source nam ngoai context.
- Hybrid search baseline: BM25-only, dense-only, hybrid va hybrid + reranker.
- Latency/cost report theo stage: embed, retrieve, rerank, generate.
- Security notes cho prompt injection, ACL leak, PII logging, source URI leak va cache key.
- Delete/reindex plan cho document lifecycle.

## Learning Cadence

| Thoi luong | Viec lam |
|---:|---|
| 10 phut | Doc TL;DR va muc tieu |
| 35 phut | Hoc concept chinh |
| 45 phut | Hands-on/code/design |
| 20 phut | Ghi chu trade-off, performance, production concern |
| 10 phut | Update learning log |
