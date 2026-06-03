# Day 38: Advanced RAG Patterns

Advanced RAG không có nghĩa là nhồi thật nhiều agent hoặc prompt vào pipeline. Đây là bài học về cách xử lý các lỗi retrieval khó hơn sau khi bạn đã có nền tảng từ Day 36 Hybrid Search và Day 37 Reranking: query mơ hồ, query quá ngắn, synonym, acronym, câu hỏi cần nhiều bước, chunk mất ngữ cảnh và corpus có quan hệ entity phức tạp.

Bài này được tách thành các phần riêng để dễ học, dễ tra cứu và dễ thực hành.

## Nội dung

1. [Lession: Advanced RAG Patterns production](./day-38-advanced-rag-patterns/lession.md)
   - Query rewriting, multi-query retrieval, HyDE, step-back prompting.
   - Query decomposition, multi-hop RAG, contextual retrieval.
   - Corrective RAG, agentic RAG, GraphRAG overview.
   - Thiết kế pipeline gần production với trace, fallback, budget và evaluation gate.

2. [Document: Cheat sheet, prompt templates và runbook](./day-38-advanced-rag-patterns/document.md)
   - Decision matrix chọn pattern theo loại lỗi.
   - Prompt contract cho rewrite, multi-query, HyDE, decomposition và grader.
   - Metrics, performance budget, observability fields và decision report template.
   - Checklist production readiness.

3. [Exercise: Advanced RAG evaluation lab](./day-38-advanced-rag-patterns/exercise.md)
   - Chạy baseline hybrid + rerank.
   - Thêm query rewriting, multi-query và contextual retrieval.
   - Đo Recall@K, MRR, context precision, latency và cost.
   - Viết decision report: pattern nào giữ, pattern nào bỏ.

## Mục tiêu sau bài học

- Hiểu từng advanced RAG pattern giải quyết lỗi gì và đổi lại bằng cost/latency/risk nào.
- Biết vì sao production không cần implement tất cả pattern cùng lúc.
- Ưu tiên đúng: baseline hybrid search + reranking, sau đó query rewriting và contextual retrieval.
- Thiết kế được trace để debug từng bước: original query, rewritten query, variants, retrieved chunks, reranked chunks và citations.
- Trả lời được: dùng Advanced RAG trong production được không, và cần điều kiện gì.

## Cách học đề xuất

1. Đọc `lession.md` để nắm mental model và kiến trúc.
2. Dùng `document.md` như cheat sheet khi thiết kế hoặc review một RAG pipeline thật.
3. Làm `exercise.md` trên query set nhỏ trước, sau đó mới cân nhắc áp dụng vào project Day 40.
