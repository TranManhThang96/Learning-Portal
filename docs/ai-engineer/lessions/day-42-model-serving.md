# Day 42: Model Serving

Day 42 tập trung biến một model, LLM hoặc RAG pipeline thành một API có contract rõ, có streaming, có timeout, có rate/concurrency limit và có câu trả lời production readiness.

## Nội dung

1. [Lession: Model Serving với FastAPI, SSE và production boundary](./day-42-model-serving/lession.md)
   - Thiết kế serving contract cho `/health`, `/ready`, `/query`, `/query/stream` và `/models/current`.
   - Request validation bằng Pydantic, error contract, trace id, latency logging và model version.
   - Streaming response bằng Server-Sent Events, xử lý timeout và client disconnect.
   - Rate limit, concurrency limit, batching trade-off và cách chọn FastAPI/BentoML/TorchServe/Triton/vLLM/TGI.
   - Trả lời rõ: dùng được trong production không, và cần điều kiện gì.

2. [Document: Template, checklist và decision matrix](./day-42-model-serving/document.md)
   - API contract template, SSE event contract, config template và structured log fields.
   - Tool comparison cho FastAPI, BentoML, TorchServe, Triton, vLLM và TGI.
   - Checklist timeout, rate limit, concurrency, batching, security và observability.
   - Runbook cho timeout, OOM, latency spike, stream bị cắt và model version mismatch.

3. [Exercise: Lab triển khai Model Serving API](./day-42-model-serving/exercise.md)
   - Scaffold một FastAPI service gần production.
   - Implement endpoint non-streaming và streaming SSE.
   - Thêm request validation, timeout, in-memory limiter cho local và note Redis/API Gateway cho production.
   - Viết test script, chạy curl streaming, benchmark latency và đưa ra release decision.

## Mục tiêu sau bài học

- Biết phân biệt model artifact, model runtime, API gateway và product contract.
- Thiết kế được FastAPI serving contract đủ dùng cho model hoặc RAG pipeline.
- Implement được SSE streaming cho LLM/RAG response một chiều server-to-client.
- Biết đặt timeout, input/output limit, rate limit và concurrency limit để bảo vệ GPU/provider quota.
- Hiểu batching giúp tăng throughput nhưng có thể làm xấu p95 latency và time-to-first-token.
- Chọn đúng serving tool theo context thay vì mặc định dùng một framework cho mọi workload.
