# Exercise: Triển Khai Model Serving API Với FastAPI Và SSE

## Mục tiêu

Bạn sẽ triển khai một API serving cho model hoặc RAG pipeline với:

- `GET /health`
- `GET /ready`
- `GET /models/current`
- `POST /query`
- `GET /query/stream` dùng Server-Sent Events
- Pydantic request/response validation
- Timeout, rate limit và concurrency limit
- Structured logs có `trace_id`
- Test script cho non-streaming và streaming
- README trả lời production readiness

Thời lượng đề xuất:

- Bản tối thiểu: 60-90 phút.
- Bản tốt cho portfolio: 0.5-1 ngày.
- Bản gần production: 2-3 ngày, thêm auth, Redis limiter, Docker, metrics và CI.

## 0. Acceptance criteria

Hoàn thành bài tập khi bạn có:

- [ ] `POST /query` reject request sai schema bằng `422 VALIDATION_ERROR` theo cùng error contract.
- [ ] `POST /query` trả `answer`, `citations`, `trace_id`, `latency_ms`, `model_version`, `finish_reason`.
- [ ] `GET /query/stream` trả event `meta`, nhiều event `token`, và event `done`.
- [ ] Timeout trả error contract có code `MODEL_TIMEOUT` hoặc `STREAM_TIMEOUT`.
- [ ] Rate limit trả `429 RATE_LIMITED`.
- [ ] Concurrency limit trả `503 CONCURRENCY_LIMIT` hoặc SSE `error`.
- [ ] Log có `trace_id`, `tenant_id`, `input_chars`, `latency_ms`, `model_version`.
- [ ] Có script test streaming bằng Python hoặc `curl -N`.
- [ ] README trả lời: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## 1. Chọn runtime

Chọn một trong ba mức:

| Mức | Runtime | Khi nào dùng |
|---|---|---|
| Local fake runtime | Hàm async giả lập model | Học API boundary nhanh |
| RAG runtime từ Day 40 | Gọi retrieval + generation pipeline | Muốn nối với mini-project RAG |
| LLM runtime thật | Gọi vLLM/TGI/managed LLM qua HTTP | Muốn demo self-host hoặc provider thật |

Khuyến nghị cho lần đầu: dùng fake runtime trước. Sau khi contract ổn, thay runtime bằng RAG hoặc LLM thật.

## 2. Scaffold project

Tạo folder:

```text
day-42-serving-lab/
  app/
    main.py
    schemas.py
    runtime.py
    limits.py
  scripts/
    smoke_test.py
    stream_client.py
  pyproject.toml
  README.md
```

Dependencies tối thiểu:

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "httpx",
  "pydantic",
  "pydantic-settings",
]
```

`pydantic-settings` dùng để đọc và validate config từ environment variables.

Chạy local:

```bash
uvicorn app.main:app --reload --port 8000
```

## 3. Implement schema

Tạo `app/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    source_id: str
    document_id: str
    chunk_id: str
    title: str
    page_start: int | None = None
    page_end: int | None = None


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=2000)
    tenant_id: str = Field("demo", min_length=1, max_length=64)
    top_k: int = Field(6, ge=1, le=20)
    max_output_tokens: int = Field(512, ge=16, le=2048)
    include_trace: bool = False


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
    latency_ms: dict[str, int]
    model_version: str
    finish_reason: Literal["stop", "timeout", "error"]
```

Test nhanh validation:

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'content-type: application/json' \
  -d '{"question":"","unknown_field":true}' | jq
```

Kỳ vọng: FastAPI trả `422`.

## 4. Implement fake runtime

Tạo `app/runtime.py`:

```python
import asyncio
import time
from collections.abc import AsyncIterator

from app.schemas import Citation, QueryRequest, QueryResponse


class Runtime:
    def __init__(self, model_version: str) -> None:
        self.model_version = model_version
        self.loaded = False

    async def startup(self) -> None:
        await asyncio.sleep(0.05)
        self.loaded = True

    async def shutdown(self) -> None:
        self.loaded = False

    async def query(self, payload: QueryRequest, trace_id: str) -> QueryResponse:
        started = time.perf_counter()
        await asyncio.sleep(0.15)
        return QueryResponse(
            answer="Câu trả lời mẫu có citation [S1].",
            citations=[
                Citation(
                    source_id="S1",
                    document_id="demo-doc",
                    chunk_id="demo-doc:v1:00001",
                    title="Demo Document",
                )
            ],
            trace_id=trace_id,
            latency_ms={"generation": int((time.perf_counter() - started) * 1000)},
            model_version=self.model_version,
            finish_reason="stop",
        )

    async def stream(self, payload: QueryRequest, trace_id: str) -> AsyncIterator[str]:
        tokens = ["Câu ", "trả ", "lời ", "đang ", "được ", "stream ", "qua ", "SSE."]
        for token in tokens:
            await asyncio.sleep(0.08)
            yield token
```

Nâng cấp sau:

- Với RAG Day 40: `query()` gọi retrieval, rerank, generator và citation validator.
- Với vLLM/TGI: `query()` gọi HTTP endpoint, `stream()` parse upstream stream rồi map về SSE event contract của bạn.
- Với Triton: `query()` gọi gRPC/HTTP client và map tensor output về response schema.

## 5. Implement rate/concurrency limit

Tạo `app/limits.py`:

```python
import asyncio
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_s: int) -> None:
        self.max_requests = max_requests
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window_s:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True
```

Ghi rõ trong README:

```text
In-memory limiter chỉ dùng cho local. Production cần Redis/API Gateway/quota service
để limit có hiệu lực trên nhiều process và nhiều replicas.
```

## 6. Implement FastAPI app

Tạo `app/main.py`. Bạn có thể dùng code trong `lession.md` làm baseline, hoặc tự implement với các yêu cầu:

- `lifespan` load runtime một lần.
- Middleware tạo `trace_id` và trả header `x-trace-id`.
- Exception handler trả error contract.
- Override `RequestValidationError` để lỗi `422` cũng trả `code`, `message`, `trace_id`, `retryable`.
- `/health` không gọi dependency nặng.
- `/ready` kiểm tra runtime loaded.
- `/query` bọc runtime call bằng timeout.
- `/query/stream` trả `StreamingResponse` với `text/event-stream`.
- Streaming generator release semaphore trong `finally`.
- SSE client coi `done` hoặc `error` là terminal event; không chỉ dựa vào HTTP status.

Checklist code:

- [ ] Không gọi `Runtime()` trong từng request.
- [ ] Không dùng bare `except` rồi nuốt lỗi.
- [ ] Không trả stack trace ra client.
- [ ] Không để request chờ semaphore vô hạn.
- [ ] Không log raw prompt nếu data có thể chứa PII.

## 7. Test bằng curl

Health:

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq
curl -s http://localhost:8000/models/current | jq
```

Non-streaming:

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-key' \
  -d '{
    "question": "Day 42 học gì?",
    "tenant_id": "demo",
    "top_k": 6,
    "max_output_tokens": 256
  }' | jq
```

Streaming:

```bash
curl -N 'http://localhost:8000/query/stream?tenant_id=demo&question=Day%2042%20h%E1%BB%8Dc%20g%C3%AC%3F&max_output_tokens=128'
```

Kỳ vọng:

```text
event: meta
data: {"trace_id":"...","model_version":"..."}

event: token
data: {"text":"Câu "}

event: done
data: {"trace_id":"...","finish_reason":"stop","latency_ms":{"total":...}}
```

## 8. Viết smoke test

Tạo `scripts/smoke_test.py`:

```python
import asyncio

import httpx


BASE_URL = "http://localhost:8000"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        health = await client.get(f"{BASE_URL}/health")
        health.raise_for_status()

        response = await client.post(
            f"{BASE_URL}/query",
            json={
                "question": "Day 42 học gì?",
                "tenant_id": "demo",
                "top_k": 6,
                "max_output_tokens": 128,
            },
        )
        response.raise_for_status()
        body = response.json()
        assert body["trace_id"]
        assert body["model_version"]
        assert body["finish_reason"] == "stop"
        assert "total" in body["latency_ms"]
        print("smoke test ok", body["trace_id"])


if __name__ == "__main__":
    asyncio.run(main())
```

Chạy:

```bash
python scripts/smoke_test.py
```

## 9. Viết streaming client test

Tạo `scripts/stream_client.py`:

```python
import asyncio

import httpx


BASE_URL = "http://localhost:8000"


async def main() -> None:
    params = {
        "question": "Day 42 học gì?",
        "tenant_id": "demo",
        "max_output_tokens": 128,
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", f"{BASE_URL}/query/stream", params=params) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    print(line)


if __name__ == "__main__":
    asyncio.run(main())
```

Chạy:

```bash
python scripts/stream_client.py
```

Acceptance:

- [ ] Nhìn thấy `event: meta`.
- [ ] Nhìn thấy nhiều `event: token`.
- [ ] Nhìn thấy `event: done`.
- [ ] Nếu giảm timeout rất thấp, nhìn thấy `event: error`.
- [ ] Client fail test nếu stream kết thúc mà không có `done` hoặc `error`.

## 10. Test timeout

Sửa fake runtime tạm thời:

```python
async def query(self, payload, trace_id):
    await asyncio.sleep(999)
    return QueryResponse(
        answer="timeout simulation",
        citations=[],
        trace_id=trace_id,
        latency_ms={"total": 999000},
        model_version="fake-rag-v1",
        finish_reason="timeout",
    )
```

Giảm config:

```python
request_timeout_s = 1.0
stream_timeout_s = 1.0
```

Gọi:

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'content-type: application/json' \
  -d '{"question":"timeout test","tenant_id":"demo"}' | jq
```

Kỳ vọng:

```json
{
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "Model runtime timed out. Please retry.",
    "trace_id": "...",
    "retryable": true
  }
}
```

Sau test, revert phần sleep giả lập trong lab code của bạn.

## 11. Test rate limit

Đặt `rate_limit_requests = 2`, `rate_limit_window_s = 60`.

Gọi 3 lần liên tiếp:

```bash
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/query \
    -H 'content-type: application/json' \
    -d '{"question":"rate test","tenant_id":"demo"}'
done
```

Kỳ vọng:

```text
200
200
429
```

Trong lab chưa có auth, limiter fallback theo client IP. Production phải dùng principal/tenant đã được auth middleware hoặc gateway xác thực; không dùng `tenant_id` trong body hay API key chưa validate làm identity.

## 12. Test concurrency limit

Đặt:

```python
max_concurrent_requests = 1
queue_timeout_s = 0.05
```

Tạo nhiều request song song:

```python
import asyncio

import httpx


async def call(i: int) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "http://localhost:8000/query",
            json={"question": f"concurrency test {i}", "tenant_id": "demo"},
        )
        print(i, response.status_code, response.text[:120])


async def main() -> None:
    await asyncio.gather(*(call(i) for i in range(10)))


asyncio.run(main())
```

Kỳ vọng: một số request thành công, một số request trả `503 CONCURRENCY_LIMIT`.

## 13. Benchmark batching trade-off

Nếu bạn dùng vLLM/TGI/Triton hoặc runtime có batching, chạy ít nhất 3 cấu hình:

| Config | Mục tiêu |
|---|---|
| Batch nhỏ, wait thấp | Baseline latency |
| Batch vừa | Cân bằng latency/throughput |
| Batch lớn, wait cao | Throughput tối đa |

Ghi lại:

| Metric | Batch nhỏ | Batch vừa | Batch lớn |
|---|---:|---:|---:|
| request/sec | | | |
| tokens/sec | | | |
| p50 latency | | | |
| p95 latency | | | |
| p99 latency | | | |
| time-to-first-token | | | |
| timeout rate | | | |
| GPU memory peak | | | |

Viết kết luận:

```text
Với interactive chat, chọn config ... vì p95 và time-to-first-token tốt hơn.
Với offline batch, chọn config ... vì throughput cao hơn và SLA latency không chặt.
```

## 14. Thay fake runtime bằng runtime thật

### Option A: RAG pipeline từ Day 40

Map flow:

```text
QueryRequest
  -> normalize question
  -> retrieve with tenant/ACL filter
  -> rerank
  -> build context
  -> generate answer
  -> validate citation
  -> QueryResponse
```

Yêu cầu:

- `tenant_id` phải đi vào retriever filter.
- `top_k` phải có upper bound.
- Response phải có citation thật.
- Trace latency phải tách retrieval, rerank, generation.

### Option B: vLLM/TGI hoặc managed LLM

Map flow:

```text
QueryRequest
  -> prompt builder
  -> HTTP client with timeout
  -> parse completion or stream chunks
  -> QueryResponse/SSE events
```

Yêu cầu:

- HTTP client có timeout.
- Không retry vô hạn.
- Map upstream timeout thành `MODEL_TIMEOUT`.
- Map upstream rate limit thành `UPSTREAM_RATE_LIMITED` hoặc `RATE_LIMITED`.
- Không leak API key/provider error raw ra client.

### Option C: Triton/BentoML/TorchServe

Map flow:

```text
QueryRequest
  -> preprocess
  -> model server request
  -> postprocess
  -> QueryResponse
```

Yêu cầu:

- Version model rõ.
- Preprocess/postprocess có test.
- Timeout và batch behavior được đo.

## 15. README production readiness

README phải có một section:

```markdown
## Production Readiness

### Dùng được trong production không?

Pattern API này có thể dùng trong production, nhưng bản lab hiện tại chưa đủ
production-ready.

### Điều kiện cần để production-ready

- Thay in-memory rate limiter bằng Redis/API Gateway/quota service.
- Thêm authentication và tenant authorization thật.
- Không log raw prompt/response hoặc phải redact PII.
- Chạy load test để sizing timeout, concurrency và batching.
- Thêm metrics, dashboard và alert cho latency, timeout, error rate, queue depth.
- Nếu self-host LLM, đặt FastAPI trước vLLM/TGI/Triton thay vì tự batch trong FastAPI.
- Thêm canary deploy, rollback model version và contract test trong CI.
```

## 16. Câu hỏi review

Trả lời các câu sau sau khi hoàn thành lab:

1. Contract của `/query` có field nào giúp debug production?
2. Vì sao `/health` và `/ready` không nên giống nhau?
3. Vì sao in-memory rate limiter sai khi chạy nhiều replicas?
4. Concurrency limit bảo vệ điều gì trong LLM serving?
5. Batching cải thiện metric nào và có thể làm xấu metric nào?
6. Khi nào nên chọn FastAPI-only?
7. Khi nào nên chọn FastAPI + vLLM/TGI?
8. Khi nào Triton hợp lý hơn FastAPI-only?
9. SSE có lợi gì so với non-streaming HTTP cho chat UI?
10. Bản lab của bạn còn thiếu gì để production-ready?

## 17. Rubric tự chấm

| Mức | Tiêu chí |
|---|---|
| Đạt | Có `/query`, `/query/stream`, validation, timeout và README production readiness |
| Khá | Có rate/concurrency limit, structured logs, smoke test và stream client |
| Tốt | Có runtime thật, trace latency theo stage, benchmark p95/TTFT và error contract đầy đủ |
| Gần production | Có auth, Redis/API Gateway limiter, metrics/dashboard, Docker, CI contract test và rollout/rollback plan |
