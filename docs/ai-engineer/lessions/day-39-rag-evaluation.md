# Day 39: RAG Evaluation

RAG Evaluation là phần biến một RAG pipeline từ demo thành hệ thống có thể release có kiểm soát. Bài học này được tách thành các phần riêng để dễ học, dễ thực hành và dễ dùng lại khi làm capstone Production RAG.

## Nội dung

1. [Lession: RAG Evaluation production](./day-39-rag-evaluation/lession.md)
   - Tư duy evaluation cho RAG.
   - Golden dataset, qrels và versioning.
   - Recall@k, Precision@k, MRR, NDCG.
   - Context precision/recall, faithfulness, answer relevance, hallucination detection.
   - RAGAS, TruLens, LangSmith concepts.
   - CI, regression, release gate và production readiness.

2. [Document: Golden set, report template và runbook](./day-39-rag-evaluation/document.md)
   - Mẫu schema cho golden dataset.
   - Bộ 41 câu hỏi golden set mẫu.
   - Eval report template.
   - Rubric cho LLM-as-judge.
   - Checklist release và incident runbook.

3. [Exercise: Xây dựng RAG eval runner](./day-39-rag-evaluation/exercise.md)
   - Chuẩn bị input/output contract cho RAG pipeline.
   - Viết Python eval runner gần production.
   - Tính retrieval metrics, citation metrics, report theo tag.
   - Thiết kế CI smoke eval, nightly full eval và regression gate.

## Mục tiêu sau bài học

- Tạo được golden dataset 30-50 câu hỏi có expected answer, expected source chunk, difficulty và tags.
- Đo được retrieval quality bằng Hit@k, Recall@k, Precision@k, MRR và NDCG.
- Đo được generation quality bằng faithfulness, answer relevance, answer correctness, citation correctness và hallucination rate.
- Phân biệt lỗi do parser, chunking, embedding, BM25, hybrid merge, reranker, context builder, generator, citation hay ACL.
- Viết được eval report có breakdown theo tag, regression summary và release gate.
- Trả lời được: RAG Evaluation dùng được trong production không, và cần điều kiện gì.
