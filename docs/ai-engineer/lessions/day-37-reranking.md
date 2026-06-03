# Day 37: Reranking

Reranking là tầng xếp hạng lại candidate sau bước retrieval để tăng chất lượng context cuối cùng cho RAG. Bài học này được tách thành các phần riêng để dễ học, dễ thực hành và dễ dùng lại khi nâng cấp pipeline Day 36.

## Nội dung

1. [Lession: Reranking cho Production RAG](./day-37-reranking/lession.md)
   - Bi-encoder vs cross-encoder.
   - Reranker là gì và vì sao retrieve top-k chưa đủ.
   - BGE reranker, Cohere Rerank và lựa chọn managed/self-host.
   - Two-stage retrieval: retrieve top 50/100 rồi rerank top 5/10.
   - Latency, cost, privacy và fallback trade-off.
   - Code Python gần production cho reranker layer và evaluation.

2. [Document: Cheat sheet và production runbook](./day-37-reranking/document.md)
   - Decision matrix chọn reranker.
   - Cấu hình khuyến nghị cho candidate pool, timeout và cache.
   - Metrics cần theo dõi: Recall@k, MRR, nDCG, context precision, p95 latency.
   - Checklist production readiness và runbook rollout.

3. [Exercise: Thêm reranker vào pipeline Day 36](./day-37-reranking/exercise.md)
   - Dùng BM25 + vector + RRF từ Day 36.
   - Rerank top 50 bằng BGE hoặc Cohere.
   - Đo before/after Recall@5, MRR@10 và latency.
   - Phân tích query improved/regressed và viết quyết định production.

## Mục tiêu sau bài học

- Giải thích được reranker khác retriever ở đâu.
- Phân biệt được bi-encoder, cross-encoder, late-interaction và LLM reranking.
- Thiết kế được two-stage retrieval pipeline có ACL filter, dedupe, rerank và context builder.
- Biết khi nào retrieve top 50, top 100 hoặc ít hơn dựa trên recall, latency và cost.
- Đánh giá được cải thiện bằng Recall@k, MRR@k, nDCG@k và latency percentile.
- Trả lời được: dùng reranker trong production được không, và cần điều kiện gì.
