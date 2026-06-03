# Day 36: Hybrid Search - Dense + Sparse + BM25

Hybrid search là baseline rất mạnh cho RAG production vì kết hợp semantic retrieval với keyword retrieval. Bài học này được tách thành các phần riêng để dễ học, dễ thực hành và dễ dùng lại khi thiết kế hệ thống thật.

## Nội dung

1. [Lession: Hybrid Search production](./day-36-hybrid-search-dense-sparse-bm25/lession.md)
   - Dense retrieval, sparse retrieval và BM25.
   - SPLADE overview và vị trí của neural sparse retrieval.
   - Hybrid search bằng Reciprocal Rank Fusion.
   - Query normalization cho tiếng Việt, English mix, mã lỗi, acronym và SKU.
   - Keyword-heavy query vs semantic query.
   - Trade-off quality, latency, cost, index size, analyzer và reranker.

2. [Document: Cheat sheet, code reference và runbook](./day-36-hybrid-search-dense-sparse-bm25/document.md)
   - Decision matrix chọn BM25-only, dense-only, hybrid, SPLADE hoặc reranker.
   - Reference pipeline gần production bằng Python.
   - Checklist logging, metrics, cache, ACL, reindex và incident debugging.
   - Mẫu báo cáo benchmark BM25 vs dense vs hybrid.

3. [Exercise: Hands-on hybrid retrieval](./day-36-hybrid-search-dense-sparse-bm25/exercise.md)
   - Build BM25 top-k.
   - Build dense vector top-k.
   - Merge bằng RRF.
   - Đo Hit@K, Recall@K, MRR@K.
   - Phân tích query keyword-heavy, semantic, no-diacritic và code-heavy.

## Mục tiêu sau bài học

- Giải thích được vì sao embedding không thay thế BM25 trong RAG production.
- Phân biệt được dense retrieval, sparse retrieval, BM25 và SPLADE.
- Thiết kế được hybrid retrieval pipeline có normalize, filter, parallel search, RRF merge, dedupe, optional rerank và context builder.
- Biết query nào nên kỳ vọng BM25 thắng, query nào dense thắng, query nào cần hybrid.
- Biết cách benchmark bằng query set có qrels thay vì cảm giác.
- Trả lời được: dùng hybrid search trong production được không, và cần điều kiện gì.
