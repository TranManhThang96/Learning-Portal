# Document: Model Serving Template, Checklist Và Decision Matrix

## 1. Serving architecture template

Template kiến trúc cho model hoặc RAG pipeline:

```text
Client/UI/Batch Job
  -> API Gateway or FastAPI
      -> Authentication
      -> Tenant/User context
      -> Request validation
      -> Rate limit
      -> Concurrency limit
      -> Timeout wrapper
      -> Model/RAG runtime adapter
      -> Response contract or SSE stream
      -> Structured logs, metrics, traces

Runtime adapter
  -> Local model, BentoML, TorchServe, Triton, vLLM, TGI, or managed provider
```

Boundary quan trọng:

| Boundary | Trách nhiệm |
|---|---|
| API contract | Input/output schema, error schema, event schema |
| Gateway | Auth, validation, limit, timeout, trace id, response mapping |
| Runtime adapter | Gọi model server/provider, retry có kiểm soát, mapping lỗi |
| Model server | Load model, optimize inference, batching, GPU memory |
| Observability | Logs, metrics, traces, alert, dashboard |

## 2. Project structure mẫu

```text
model-serving-api/
  app/
    main.py
    api/
      health.py
      query.py
      streaming.py
      models.py
    core/
      config.py
      errors.py
      logging.py
      limits.py
      security.py
    schemas/
      query.py
      errors.py
      events.py
    services/
      runtime.py
      rag_runtime.py
      llm_client.py
      metrics.py
    tests/
      test_contract.py
      test_validation.py
      test_streaming.py
      test_limits.py
  scripts/
    smoke_test.py
    stream_client.py
    load_test.py
  pyproject.toml
  Dockerfile
  .env.example
  README.md
```

Với project nhỏ, có thể gom file lại. Nhưng vẫn nên giữ rõ 4 nhóm: `api`, `schemas`, `services`, `core`.

## 3. API contract template

### `GET /health`

Mục đích: liveness. Không gọi dependency nặng.

Response:

```json
{
  "status": "ok",
  "service": "model-serving-api",
  "version": "1.0.0"
}
```

### `GET /ready`

Mục đích: readiness. Có thể kiểm tra model loaded, runtime client, vector DB hoặc model server.

Response:

```json
{
  "status": "ready",
  "model_version": "rag-api-v1",
  "dependencies": {
    "runtime": "ok",
    "vector_db": "ok"
  }
}
```

Nếu chưa sẵn sàng:

```json
{
  "error": {
    "code": "NOT_READY",
    "message": "Runtime is not ready.",
    "trace_id": "tr_123",
    "retryable": true
  }
}
```

### `POST /query`

Request:

```json
{
  "question": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?",
  "tenant_id": "demo",
  "top_k": 6,
  "max_output_tokens": 512,
  "include_trace": false
}
```

Validation rules:

| Field | Rule | Lý do |
|---|---|---|
| `question` | Required, `1..2000` chars | Chặn prompt rỗng hoặc quá dài |
| `tenant_id` | Required/default, `1..64` chars | Rate limit và data isolation |
| `top_k` | `1..20` | Chặn context quá lớn |
| `max_output_tokens` | `16..2048` | Kiểm soát latency và cost |
| `include_trace` | Boolean | Trace chi tiết chỉ nên bật khi cần |

Response:

```json
{
  "answer": "Nhân viên full-time có 12 ngày nghỉ phép năm [S1].",
  "citations": [
    {
      "source_id": "S1",
      "document_id": "doc_hr_2026",
      "chunk_id": "demo:doc_hr_2026:v1:00003",
      "title": "HR Policy 2026",
      "page_start": 3,
      "page_end": 3
    }
  ],
  "trace_id": "tr_123",
  "latency_ms": {
    "retrieval": 40,
    "rerank": 130,
    "generation": 900,
    "total": 1070
  },
  "model_version": "rag-api-v1",
  "finish_reason": "stop"
}
```

### `GET /query/stream`

Query params:

```text
question=Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?
tenant_id=demo
top_k=6
max_output_tokens=512
```

Headers:

```text
Accept: text/event-stream
Cache-Control: no-cache
```

Event format:

```text
event: meta
data: {"trace_id":"tr_123","model_version":"rag-api-v1"}

event: token
data: {"text":"Nhân viên "}

event: citation
data: {"source_id":"S1","document_id":"doc_hr_2026","chunk_id":"demo:doc_hr_2026:v1:00003"}

event: done
data: {"trace_id":"tr_123","finish_reason":"stop","latency_ms":{"total":1070}}

event: error
data: {"code":"STREAM_TIMEOUT","message":"Streaming response timed out.","trace_id":"tr_123","retryable":true}
```

Production note:

- Dùng `GET` nếu cần browser `EventSource` đơn giản.
- Dùng `POST` streaming với `fetch()` nếu query nhạy cảm hoặc payload lớn.
- Disable buffering ở reverse proxy cho SSE, ví dụ `X-Accel-Buffering: no` với NGINX.
- Kiểm tra idle timeout của load balancer, CDN và ingress.

### `GET /models/current`

Response:

```json
{
  "model_version": "rag-api-v1",
  "runtime": "vLLM",
  "model_name": "meta-llama/Llama-3.1-8B-Instruct",
  "prompt_version": "answer-prompt-v3",
  "deployed_at": "2026-05-10T10:00:00Z"
}
```

## 4. Error code catalog

| HTTP | Code | Retryable | Khi nào |
|---|---|---|---|
| 400 | `BAD_REQUEST` | No | Payload sai logic nhưng qua schema |
| 401 | `UNAUTHORIZED` | No | Thiếu hoặc sai auth |
| 403 | `FORBIDDEN` | No | User không có quyền tenant/model |
| 422 | `VALIDATION_ERROR` | No | FastAPI/Pydantic reject schema |
| 429 | `RATE_LIMITED` | Yes | Vượt request/token quota |
| 503 | `NOT_READY` | Yes | Runtime chưa load xong |
| 503 | `CONCURRENCY_LIMIT` | Yes | Hết slot inference |
| 504 | `MODEL_TIMEOUT` | Yes | Runtime hoặc upstream quá timeout |
| 500 | `INTERNAL_ERROR` | Maybe | Lỗi bất ngờ, cần trace |

Rule:

- Client chỉ thấy message an toàn.
- Server log giữ exception type, stack trace và upstream error.
- Mọi error phải có `trace_id`.

## 5. Config template

`.env.example`:

```dotenv
APP_ENV=local
SERVICE_NAME=model-serving-api
MODEL_VERSION=rag-api-v1

REQUEST_TIMEOUT_S=20
STREAM_TIMEOUT_S=60
QUEUE_TIMEOUT_S=0.2
MAX_CONCURRENT_REQUESTS=8

RATE_LIMIT_WINDOW_S=60
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_TOKENS=120000

RUNTIME_KIND=fake
RUNTIME_BASE_URL=http://vllm:8000/v1
RUNTIME_API_KEY=change-me

LOG_LEVEL=INFO
REDACT_PROMPTS=true
```

Timeout sizing gợi ý:

| Workload | Request timeout | Stream timeout | Queue timeout |
|---|---:|---:|---:|
| Classifier CPU nhỏ | 1-3s | N/A | 50-100ms |
| Embedding batch nhỏ | 5-15s | N/A | 100-300ms |
| RAG non-streaming | 15-30s | N/A | 100-500ms |
| LLM chat streaming | 10-30s first response, 60-180s total | 60-180s | 100-500ms |

Không copy số này vào production một cách máy móc. Phải đo trên model, GPU, context length và traffic thật.

## 6. Structured log fields

Log một request thành công:

```json
{
  "event": "query_ok",
  "trace_id": "tr_123",
  "tenant_id": "demo",
  "user_id": "u_456",
  "route": "/query",
  "input_chars": 68,
  "prompt_tokens": 2100,
  "completion_tokens": 180,
  "latency_ms": {
    "retrieval": 40,
    "rerank": 130,
    "generation": 900,
    "total": 1070
  },
  "model_version": "rag-api-v1",
  "finish_reason": "stop"
}
```

Log một request lỗi:

```json
{
  "event": "query_failed",
  "trace_id": "tr_123",
  "tenant_id": "demo",
  "route": "/query",
  "error_code": "MODEL_TIMEOUT",
  "retryable": true,
  "latency_ms": {
    "total": 20010
  },
  "model_version": "rag-api-v1"
}
```

Không nên log raw prompt/response mặc định. Nếu cần debug, bật sampling thấp, redact PII và giới hạn retention.

## 7. Tool decision matrix

| Context | Best default | Vì sao | Alternative |
|---|---|---|---|
| RAG app hoặc product API | FastAPI gateway | Cần business logic, auth, schema, trace, citation | BentoML nếu muốn package pipeline như model service |
| LLM self-host nhiều traffic | FastAPI + vLLM/TGI | Gateway giữ product contract, runtime giữ batching/KV cache | Managed LLM API nếu muốn giảm ops |
| CV/NLP model cần throughput GPU | FastAPI + Triton | Triton mạnh về dynamic batching và model repository | BentoML nếu throughput vừa phải |
| Classical ML model Python | FastAPI hoặc BentoML | Dễ vận hành, dễ test | TorchServe nếu org chuẩn PyTorch |
| PyTorch model đã có handler chuẩn | TorchServe | Hợp nếu platform đã có sẵn | Triton hoặc BentoML |
| Offline/batch inference | BentoML/Triton/job runner | Throughput quan trọng hơn p95 user latency | FastAPI nếu vẫn cần online API |

Short rule:

```text
FastAPI = product/API boundary.
vLLM/TGI/Triton = high-throughput runtime boundary.
BentoML = Python model packaging boundary.
TorchServe = PyTorch serving boundary khi org đã chuẩn hóa.
```

## 8. Batching checklist

Trước khi bật batching:

- [ ] Biết workload là interactive, batch, hay mixed.
- [ ] Có baseline p50/p95/p99 latency khi batch off hoặc batch nhỏ.
- [ ] Có metric time-to-first-token cho streaming.
- [ ] Có metric tokens/sec và GPU utilization.
- [ ] Có limit cho `max_batch_size`, `max_wait_ms`, `max_num_batched_tokens`.
- [ ] Có timeout nếu request đứng trong queue quá lâu.
- [ ] Có test với prompt dài và output dài.
- [ ] Có alert cho OOM, timeout rate và queue depth.

Decision:

| Nếu mục tiêu là | Tối ưu |
|---|---|
| Chat UI phản hồi nhanh | `max_wait_ms` thấp, concurrency vừa phải, stream sớm |
| Batch eval qua đêm | Batch lớn hơn, queue lâu hơn được |
| Cost thấp | Throughput/GPU utilization cao, chấp nhận latency |
| SLA p95 chặt | Batch nhỏ hơn, scale replicas hoặc dùng model nhỏ hơn |

## 9. Security checklist

- [ ] Auth bắt buộc cho endpoint inference.
- [ ] Tenant/user context không lấy hoàn toàn từ body nếu client có thể giả mạo.
- [ ] Rate limit theo tenant/user/API key.
- [ ] Token budget theo tenant để tránh cost spike.
- [ ] Không trả stack trace, provider error raw hoặc prompt nội bộ ra client.
- [ ] Redact prompt/response trong logs.
- [ ] Nếu RAG multi-tenant, filter ACL ở retriever, không giao cho prompt.
- [ ] Validate content type và payload size.
- [ ] Có allowlist model nếu client được chọn model.
- [ ] Có audit log cho model version, prompt version và deployment.

## 10. Production readiness checklist

### Contract

- [ ] OpenAPI schema rõ cho request/response/error.
- [ ] Có `trace_id` trong header và response body.
- [ ] Có `model_version` hoặc `pipeline_version`.
- [ ] Có `finish_reason`.
- [ ] SSE event có `meta`, `token`, `done`, `error`.

### Reliability

- [ ] `/health` và `/ready` tách riêng.
- [ ] Startup load/warmup model một lần.
- [ ] Timeout ở gateway, upstream client và proxy.
- [ ] Concurrency limit đã sizing bằng load test.
- [ ] Rate limit global, không chỉ process-local.
- [ ] Graceful shutdown không cắt request đang xử lý quá thô.

### Performance

- [ ] Đo p50/p95/p99 latency.
- [ ] Đo time-to-first-token.
- [ ] Đo tokens/sec và request/sec.
- [ ] Đo CPU/GPU memory.
- [ ] Đã test prompt dài, output dài và burst traffic.
- [ ] Batching được tuning theo SLA.

### Observability

- [ ] Structured logs có trace id, tenant, route, latency, model version.
- [ ] Metrics có request count, error rate, timeout rate, latency histogram.
- [ ] Dashboard có queue depth/concurrency/GPU memory nếu self-host.
- [ ] Alert cho timeout spike, OOM, readiness fail và error rate.

### Release

- [ ] Canary hoặc blue/green deploy.
- [ ] Rollback model/prompt/runtime version.
- [ ] Smoke test sau deploy.
- [ ] Contract test trong CI.
- [ ] Eval regression cho RAG/model quality.

## 11. Incident runbook

### Timeout tăng mạnh

1. Kiểm tra p95/p99 latency theo stage: retrieval, rerank, generation, upstream.
2. Kiểm tra queue depth và concurrency.
3. Kiểm tra prompt length và output tokens có tăng không.
4. Tạm giảm `max_output_tokens` hoặc `top_k` nếu cần bảo vệ service.
5. Scale runtime hoặc rollback model nếu latency tăng sau deploy.

### GPU OOM

1. Dừng rollout hoặc giảm traffic.
2. Giảm `max_concurrent_requests`, batch size hoặc max context/output tokens.
3. Kiểm tra model replicas có bị nhân đôi do nhiều worker không.
4. Kiểm tra KV cache usage và prompt length distribution.
5. Chạy lại load test trước khi mở traffic.

### SSE stream bị cắt

1. Kiểm tra reverse proxy/CDN/ingress idle timeout.
2. Kiểm tra buffering có bị bật không.
3. Kiểm tra server có gửi heartbeat hoặc token đều không.
4. Kiểm tra client disconnect rate.
5. Log `finish_reason` để phân biệt `done`, `timeout`, `client_disconnected`.

### Model version mismatch

1. So sánh `/models/current` với deployment manifest.
2. Kiểm tra registry version và image tag.
3. Kiểm tra cache hoặc replica cũ chưa drain.
4. Rollback hoặc restart replica lệch version.
5. Gắn test vào CI/CD để chặn mismatch lần sau.

## 12. Câu trả lời production readiness mẫu

```text
Pattern này dùng được trong production nếu FastAPI chỉ giữ API/product boundary,
runtime được load/warmup đúng cách, limit được quản lý global, timeout được đặt ở
mọi layer, và hệ thống có observability + rollback.

Sample local chưa production-ready vì rate limiter là in-memory, fake runtime,
chưa có auth thật, chưa có Redis/API Gateway quota, chưa có dashboard/alert,
và chưa được load test trên traffic + GPU thật.
```
