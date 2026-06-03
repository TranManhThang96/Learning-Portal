# Day 44: Observability Cho LLM App

Day 44 tập trung vào cách nhìn thấy và debug một LLM/RAG app trong production: request chậm ở đâu, token tốn vì stage nào, retrieval có trả đúng context không, citation có hợp lệ không, feedback của user gắn với trace nào và cost/request đang tăng vì model, prompt hay index version nào.

## Nội dung

1. [Lession: Observability cho LLM/RAG app](./day-44-observability-cho-llm-app/lession.md)
   - Logs, metrics, traces và cách map sang RAG pipeline.
   - Trace schema cho query, retrieval, rerank, context builder, generation, citation validation và feedback.
   - Token usage, cost/request, TTFT, latency theo stage và error taxonomy.
   - Code gần production với FastAPI, structured JSON logs, OpenTelemetry spans và Prometheus metrics.
   - Trade-off, best solution theo context/performance và câu trả lời production readiness.

2. [Document: Schema, checklist, dashboard và runbook](./day-44-observability-cho-llm-app/document.md)
   - Event catalog, trace schema, feedback schema và metric naming.
   - So sánh Langfuse, LangSmith, OpenTelemetry, Prometheus/Grafana và ELK/OpenSearch.
   - Privacy, redaction, sampling, retention, access control và audit.
   - Dashboard panels, alert rules, incident runbook và release checklist.

3. [Exercise: Instrument RAG pipeline](./day-44-observability-cho-llm-app/exercise.md)
   - Thêm `trace_id`, stage timing, token/cost logging và feedback endpoint.
   - Chạy golden set, tạo report top slowest/highest-cost queries và phân loại lỗi.
   - Thiết kế sampling/redaction policy và 3 alert production đầu tiên.
   - Trả lời: dùng được trong production không, nếu có thì cần điều kiện gì.

## Mục Tiêu Sau Bài Học

- Phân biệt rõ logs, metrics và traces trong LLM app.
- Thiết kế được trace schema đủ sâu cho RAG production.
- Đo được latency tổng, latency theo stage, TTFT, throughput, error rate, token usage và cost/request.
- Gắn feedback của user với trace, prompt version, model version, index version và retrieved chunks.
- Chọn tooling observability phù hợp theo team, data policy, performance budget và chi phí vận hành.
- Biết đặt privacy, redaction, sampling và retention policy trước khi log prompt/context/output.
