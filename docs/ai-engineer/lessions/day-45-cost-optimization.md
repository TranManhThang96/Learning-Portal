# Day 45: Cost Optimization

Day 45 tập trung vào cách kiểm soát chi phí cho LLM/RAG app gần production. Bài học này được tách thành các phần riêng để dễ học, dễ áp dụng vào mini-project Day 40 và dễ dùng làm tài liệu review kiến trúc.

## Nội dung

1. [Lession: Cost Optimization cho LLM/RAG production](./day-45-cost-optimization/lession.md)
   - Cost model cho toàn pipeline: retrieval, embedding, rerank, context, generation, retry, eval, observability và infra.
   - Token budget, prompt caching, semantic caching với Redis, model routing, context compression và chunk pruning.
   - Batch API, distillation overview, budget/quota/degrade mode và best solution theo context/performance.
   - Trả lời rõ: dùng được trong production không, và cần điều kiện gì.

2. [Document: Template, runbook và pseudo-code](./day-45-cost-optimization/document.md)
   - Pricing config, trace log schema, bảng estimate cost, token budget policy và cache key template.
   - Pseudo-code gần production để tính cost từ trace logs.
   - Runbook kiểm soát cost spike, budget alert, rollout và rollback.

3. [Exercise: Lab thiết kế cost plan cho RAG app Day 40](./day-45-cost-optimization/exercise.md)
   - Estimate cost cho 1k, 10k và 100k requests/day.
   - Thiết kế token budget cho `/query`, `/eval/run`, `/documents/ingest`.
   - Thiết kế Redis semantic cache, model routing rules, degrade mode và PR note.

## Mục tiêu sau bài học

- Ước lượng được `cost/request`, `cost/day`, `cost/month` từ traffic, token usage, cache hit rate và retry rate.
- Biết thiết kế token budget như một backend contract thay vì chỉ là lời nhắc trong prompt.
- Biết chọn kỹ thuật giảm cost theo context: prompt caching, semantic caching, model routing, context pruning, Batch API hoặc distillation.
- Biết trade-off giữa quality, latency, reliability, security và cost.
- Có thể viết production readiness answer cho một cost optimization plan.
