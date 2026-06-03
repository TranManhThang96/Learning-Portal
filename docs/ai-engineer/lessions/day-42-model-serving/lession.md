# Day 42: Model Serving Với FastAPI, SSE Và Production Boundary

## 1. Mục tiêu bài học

Sau Day 42, bạn cần build được một serving layer cho model hoặc RAG pipeline có các đặc điểm sau:

- Có API contract rõ ràng, không chỉ là một hàm `predict()` trả string.
- Có request validation, response schema, error schema và `trace_id`.
- Có `/health` cho process health và `/ready` cho model/runtime readiness.
- Có endpoint non-streaming cho automation và endpoint streaming SSE cho chat UI.
- Có timeout, input limit, output limit, rate limit và concurrency limit.
- Biết khi nào FastAPI là đủ, khi nào nên đặt FastAPI trước vLLM, TGI, Triton hoặc service chuyên dụng khác.
- Trả lời được: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

Trong bài này, "model" có thể là:

- Classical ML model: classifier, ranker, regressor.
- Deep learning model: PyTorch/TensorFlow/ONNX.
- LLM local hoặc managed provider.
- RAG pipeline từ Day 40: retrieve, rerank, build context, generate, validate citation.

## 2. Mental model: training artifact khác serving contract

Training tạo artifact:

```text
dataset + code + params -> model artifact + metrics + registry version
```

Serving biến artifact thành product boundary:

```text
client
  -> API gateway
  -> auth/rate limit
  -> request validation
  -> timeout/concurrency control
  -> model runtime hoặc RAG pipeline
  -> response/stream
  -> structured logs + metrics + trace
```

Một model có accuracy tốt vẫn có thể fail production nếu serving layer thiếu boundary:

| Vấn đề | Hậu quả |
|---|---|
| Không validate input | Prompt quá dài, payload sai schema, request gây OOM hoặc chi phí tăng |
| Không timeout | Request treo, worker bị giữ, queue tăng và toàn service chậm |
| Không concurrency limit | GPU hết memory do quá nhiều request đồng thời |
| Không rate limit | Một tenant hoặc một client ăn hết quota |
| Không trace id | Không debug được request lỗi |
| Không version response | Không biết câu trả lời đến từ model/pipeline nào |
| Không streaming | Chat UI có time-to-first-token kém, user tưởng service chết |

## 3. Serving contract tối thiểu

Endpoint đề xuất cho model hoặc RAG pipeline:

| Endpoint | Mục đích | Ghi chú production |
|---|---|---|
| `GET /health` | Process còn sống không | Không gọi dependency nặng, dùng cho liveness probe |
| `GET /ready` | Service sẵn sàng nhận traffic không | Kiểm tra model loaded, vector DB/model server reachable |
| `GET /models/current` | Trả model/runtime/pipeline version | Bắt buộc để debug rollback và A/B test |
| `POST /query` | Non-streaming inference | Dùng cho batch job, automation, test, eval |
| `GET /query/stream` hoặc `POST /query/stream` | Streaming token/event | Dùng cho chat UI, SSE một chiều server-to-client |

Request contract nên giới hạn rõ:

```json
{
  "question": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?",
  "tenant_id": "demo",
  "top_k": 6,
  "max_output_tokens": 512,
  "include_trace": false
}
```

Response contract nên trả đủ dữ liệu để user dùng được và engineer debug được:

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
  "trace_id": "tr_20260510_001",
  "latency_ms": {
    "retrieval": 42,
    "rerank": 126,
    "generation": 870,
    "total": 1041
  },
  "model_version": "rag-api-v1",
  "finish_reason": "stop"
}
```

Error contract không trả stack trace ra client:

```json
{
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "Model runtime timed out. Please retry.",
    "trace_id": "tr_20260510_001",
    "retryable": true
  }
}
```

## 4. FastAPI service gần production

Ví dụ dưới đây dùng fake runtime để bài học chạy được local. Khi đưa vào project thật, thay `RagRuntime` bằng adapter gọi RAG pipeline, vLLM/TGI OpenAI-compatible endpoint, Triton gRPC/HTTP, BentoML service hoặc managed LLM API.

Điểm production-style trong code:

- Load runtime một lần trong `lifespan`, không load model trong từng request.
- Pydantic schema dùng `extra="forbid"` để reject field lạ.
- Mọi response có `trace_id`, `model_version`, `finish_reason`.
- Có timeout cho non-streaming và streaming.
- Có rate limit và concurrency limit ở gateway.
- SSE event có `token`, `done`, `error`.
- Streaming generator kiểm tra client disconnect.
- Log có latency, tenant, input length và error code.

```python
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger("model-serving")
logging.basicConfig(level=logging.INFO)


@dataclass(frozen=True)
class Settings:
    service_name: str = "day-42-model-serving"
    model_version: str = "rag-api-v1"
    request_timeout_s: float = 20.0
    stream_timeout_s: float = 60.0
    queue_timeout_s: float = 0.2
    max_concurrent_requests: int = 8
    rate_limit_window_s: int = 60
    rate_limit_requests: int = 60


settings = Settings()


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


class ErrorBody(BaseModel):
    code: str
    message: str
    trace_id: str
    retryable: bool


class ErrorResponse(BaseModel):
    error: ErrorBody


class InMemoryRateLimiter:
    """Process-local limiter for local lab. Use Redis/API Gateway for production."""

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


class RagRuntime:
    def __init__(self, model_version: str) -> None:
        self.model_version = model_version
        self.loaded = False

    async def startup(self) -> None:
        # Replace this with model load, warmup request, DB connection, or client init.
        await asyncio.sleep(0.05)
        self.loaded = True

    async def shutdown(self) -> None:
        self.loaded = False

    async def query(self, payload: QueryRequest, trace_id: str) -> QueryResponse:
        started = time.perf_counter()
        await asyncio.sleep(0.08)
        answer = (
            "Đây là câu trả lời mẫu từ runtime. "
            "Trong project thật, thay phần này bằng RAG hoặc model server [S1]."
        )
        generation_ms = int((time.perf_counter() - started) * 1000)
        return QueryResponse(
            answer=answer,
            citations=[
                Citation(
                    source_id="S1",
                    document_id="demo-doc",
                    chunk_id="demo-doc:v1:00001",
                    title="Demo Document",
                )
            ],
            trace_id=trace_id,
            latency_ms={"generation": generation_ms},
            model_version=self.model_version,
            finish_reason="stop",
        )

    async def stream(self, payload: QueryRequest, trace_id: str) -> AsyncIterator[str]:
        tokens = [
            "Đây ",
            "là ",
            "streaming ",
            "response ",
            "mẫu ",
            "qua ",
            "SSE.",
        ]
        for token in tokens[: payload.max_output_tokens]:
            await asyncio.sleep(0.05)
            yield token


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def client_key(request: Request, tenant_id: str) -> str:
    api_key = request.headers.get("x-api-key")
    forwarded_for = request.headers.get("x-forwarded-for")
    host = forwarded_for or (request.client.host if request.client else "unknown")
    identity = api_key or host
    return f"{tenant_id}:{identity}"


def error_detail(code: str, message: str, trace_id: str, retryable: bool) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
            "retryable": retryable,
        }
    }


async def acquire_slot(app: FastAPI, trace_id: str) -> None:
    try:
        await asyncio.wait_for(app.state.semaphore.acquire(), timeout=settings.queue_timeout_s)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail(
                code="CONCURRENCY_LIMIT",
                message="Too many concurrent requests. Please retry later.",
                trace_id=trace_id,
                retryable=True,
            ),
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = RagRuntime(settings.model_version)
    await runtime.startup()
    app.state.runtime = runtime
    app.state.semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
    app.state.rate_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_requests,
        window_s=settings.rate_limit_window_s,
    )
    yield
    await runtime.shutdown()


app = FastAPI(title=settings.service_name, version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    request.state.trace_id = request.headers.get("x-trace-id", f"tr_{uuid.uuid4().hex}")
    response = await call_next(request)
    response.headers["x-trace-id"] = request.state.trace_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", f"tr_{uuid.uuid4().hex}")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = error_detail(
            code="HTTP_ERROR",
            message=str(exc.detail),
            trace_id=trace_id,
            retryable=False,
        )
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", f"tr_{uuid.uuid4().hex}")
    logger.exception("unhandled_error", extra={"trace_id": trace_id})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_detail(
            code="INTERNAL_ERROR",
            message="Unexpected model serving error.",
            trace_id=trace_id,
            retryable=False,
        ),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    runtime: RagRuntime = request.app.state.runtime
    if not runtime.loaded:
        raise HTTPException(status_code=503, detail="runtime is not ready")
    return {"status": "ready", "model_version": runtime.model_version}


@app.get("/models/current")
async def current_model(request: Request) -> dict[str, str]:
    runtime: RagRuntime = request.app.state.runtime
    return {"model_version": runtime.model_version, "runtime": "RagRuntime"}


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    trace_id = request.state.trace_id
    rate_key = client_key(request, payload.tenant_id)
    if not await request.app.state.rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail(
                code="RATE_LIMITED",
                message="Rate limit exceeded. Please retry later.",
                trace_id=trace_id,
                retryable=True,
            ),
        )

    await acquire_slot(request.app, trace_id)
    started = time.perf_counter()
    try:
        async with asyncio.timeout(settings.request_timeout_s):
            response = await request.app.state.runtime.query(payload, trace_id)
            response.latency_ms["total"] = int((time.perf_counter() - started) * 1000)
            logger.info(
                "query_ok",
                extra={
                    "trace_id": trace_id,
                    "tenant_id": payload.tenant_id,
                    "input_chars": len(payload.question),
                    "latency_ms": response.latency_ms["total"],
                    "model_version": response.model_version,
                },
            )
            return response
    except asyncio.TimeoutError as exc:
        logger.warning("query_timeout", extra={"trace_id": trace_id, "tenant_id": payload.tenant_id})
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_detail(
                code="MODEL_TIMEOUT",
                message="Model runtime timed out. Please retry.",
                trace_id=trace_id,
                retryable=True,
            ),
        ) from exc
    finally:
        request.app.state.semaphore.release()


@app.get("/query/stream")
async def query_stream(
    request: Request,
    question: str = Query(..., min_length=1, max_length=2000),
    tenant_id: str = Query("demo", min_length=1, max_length=64),
    top_k: int = Query(6, ge=1, le=20),
    max_output_tokens: int = Query(512, ge=16, le=2048),
) -> StreamingResponse:
    trace_id = request.state.trace_id
    payload = QueryRequest(
        question=question,
        tenant_id=tenant_id,
        top_k=top_k,
        max_output_tokens=max_output_tokens,
    )
    rate_key = client_key(request, payload.tenant_id)
    if not await request.app.state.rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail(
                code="RATE_LIMITED",
                message="Rate limit exceeded. Please retry later.",
                trace_id=trace_id,
                retryable=True,
            ),
        )

    async def events() -> AsyncIterator[str]:
        slot_acquired = False
        started = time.perf_counter()
        try:
            await acquire_slot(request.app, trace_id)
            slot_acquired = True
            yield sse("meta", {"trace_id": trace_id, "model_version": settings.model_version})

            async with asyncio.timeout(settings.stream_timeout_s):
                async for token in request.app.state.runtime.stream(payload, trace_id):
                    if await request.is_disconnected():
                        logger.info("stream_client_disconnected", extra={"trace_id": trace_id})
                        return
                    yield sse("token", {"text": token})

            total_ms = int((time.perf_counter() - started) * 1000)
            yield sse(
                "done",
                {
                    "trace_id": trace_id,
                    "finish_reason": "stop",
                    "latency_ms": {"total": total_ms},
                },
            )
        except HTTPException as exc:
            body = exc.detail if isinstance(exc.detail, dict) else error_detail(
                "STREAM_ERROR",
                str(exc.detail),
                trace_id,
                retryable=True,
            )
            yield sse("error", body["error"])
        except asyncio.TimeoutError:
            yield sse(
                "error",
                error_detail(
                    "STREAM_TIMEOUT",
                    "Streaming response timed out.",
                    trace_id,
                    retryable=True,
                )["error"],
            )
        except Exception:
            logger.exception("stream_failed", extra={"trace_id": trace_id})
            yield sse(
                "error",
                error_detail(
                    "INTERNAL_ERROR",
                    "Unexpected model serving error.",
                    trace_id,
                    retryable=False,
                )["error"],
            )
        finally:
            if slot_acquired:
                request.app.state.semaphore.release()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

Ghi chú quan trọng:

- `GET /query/stream` dễ dùng với browser `EventSource`, nhưng query nằm trên URL. Với dữ liệu nhạy cảm, dùng `POST /query/stream` và stream bằng `fetch()`.
- In-memory rate limiter chỉ đúng cho local hoặc một process. Production nên dùng Redis, API Gateway, Envoy, Kong, NGINX, Cloudflare hoặc service quota tập trung.
- Nếu dùng nhiều Uvicorn workers, mỗi worker có limiter và semaphore riêng. Với GPU local, nhiều worker có thể load nhiều bản model và gây OOM.
- `asyncio.timeout()` cần Python 3.11+. Nếu project dùng Python cũ hơn, thay bằng `asyncio.wait_for()`.
- Nếu model runtime là sync CPU-bound, không gọi trực tiếp trong async endpoint. Đưa vào worker thread/process hoặc tách thành model server riêng.

## 5. Streaming SSE contract

SSE phù hợp khi server chỉ cần đẩy token/event xuống client:

```text
client sends query
server yields token events
client renders partial answer
server yields done or error event
```

Event contract đề xuất:

```text
event: meta
data: {"trace_id":"tr_123","model_version":"rag-api-v1"}

event: token
data: {"text":"Nhân viên "}

event: citation
data: {"source_id":"S1","document_id":"doc_hr_2026","chunk_id":"..."}

event: done
data: {"trace_id":"tr_123","finish_reason":"stop","latency_ms":{"total":1420}}

event: error
data: {"code":"STREAM_TIMEOUT","message":"Streaming response timed out.","trace_id":"tr_123","retryable":true}
```

SSE trade-off:

| Lựa chọn | Nên dùng khi | Không nên dùng khi |
|---|---|---|
| SSE | Chat completion, token stream, progress event một chiều | Cần client và server gửi event hai chiều liên tục |
| WebSocket | Collaboration, voice, realtime bidirectional, tool session stateful | Chỉ stream token một chiều |
| Non-streaming HTTP | Batch job, eval runner, automation, output ngắn | Chat UI cần phản hồi sớm |

Best default cho RAG chat: `POST /query` cho automation/eval và SSE endpoint cho UI.

## 6. Timeout, rate limit và concurrency limit

Các limit nên được thiết kế theo nhiều lớp:

| Layer | Control | Ví dụ |
|---|---|---|
| Input | `question.max_length`, max file size, max context docs | Reject trước khi gọi model |
| Output | `max_output_tokens`, stop sequence | Giảm latency và cost |
| Queue | `queue_timeout_s` | Không để request đợi vô hạn khi service bận |
| Runtime | `request_timeout_s`, upstream HTTP timeout | Fail clean thay vì treo worker |
| Tenant | requests/minute, tokens/minute | Bảo vệ quota và budget |
| GPU | `max_concurrent_requests`, KV cache budget | Tránh OOM |
| Network | reverse proxy timeout, idle timeout | Tránh stream bị cắt bất ngờ |

Rate limit trả `429 RATE_LIMITED`. Concurrency limit thường trả `503 CONCURRENCY_LIMIT` nếu request không lấy được slot trong queue timeout. Model timeout trả `504 MODEL_TIMEOUT`.

Production nên tách rõ:

- Rate limit theo tenant, user, API key và token budget, không chỉ theo IP.
- Concurrency limit theo model/pool/GPU, không chỉ toàn service.
- Timeout theo stage: retrieval timeout, rerank timeout, generation timeout, total timeout.

## 7. Batching trade-off

Batching gom nhiều request để dùng GPU hiệu quả hơn. Với LLM, các runtime như vLLM/TGI thường dùng continuous batching để thêm request mới vào batch đang chạy.

| Lợi ích | Chi phí |
|---|---|
| Tăng tokens/second và GPU utilization | Tăng queue delay nếu `max_wait_ms` quá cao |
| Giảm overhead mỗi request | p95/p99 latency có thể xấu hơn |
| Hữu ích cho batch/eval/offline workload | Time-to-first-token của chat có thể chậm |
| Tận dụng tốt GPU cho model lớn | Cần tuning tránh OOM do batch quá lớn |

Metric cần đo trước khi bật batching mạnh:

- p50/p95/p99 latency.
- Time-to-first-token với streaming.
- Tokens/second tổng và tokens/second mỗi request.
- GPU utilization, memory usage, KV cache usage.
- Error rate, timeout rate, OOM rate.

Best rule:

```text
Interactive chat: ưu tiên p95 latency và time-to-first-token.
Batch/offline inference: ưu tiên throughput và cost/request.
```

Nếu workload là RAG chat nhiều user, nên dùng FastAPI làm gateway và để vLLM/TGI xử lý continuous batching phía model server.

## 8. So sánh serving tools

| Tool | Phù hợp nhất | Điểm mạnh | Trade-off | Khi chọn |
|---|---|---|---|---|
| FastAPI | API gateway, RAG orchestration, business logic, model nhỏ | Python-native, schema rõ, dễ debug, dễ tích hợp auth/logging | Không tự giải quyết GPU scheduling, continuous batching hoặc model optimization | Default cho capstone, RAG app, wrapper trước model server |
| BentoML | Đóng gói Python model service, batchable inference, model registry đơn giản | Developer experience tốt cho Python ML, build image/service nhanh | Với LLM throughput cao vẫn cần runtime chuyên dụng phía sau | Classical ML, embedding/reranker service, team muốn packaging chuẩn |
| TorchServe | Serve PyTorch model bằng handler | Hợp nếu org đã chuẩn hóa TorchServe và model là PyTorch | Ít linh hoạt cho LLM/RAG custom, cần viết handler và ops riêng | PyTorch classifier/detector/ranker đã ổn định |
| Triton Inference Server | GPU inference throughput cao, multi-framework, dynamic batching | Mạnh cho TensorRT/ONNX/PyTorch backend, gRPC/HTTP, model repository | Ops phức tạp, cần hiểu GPU profiling và model format | High-throughput CV/NLP model, multi-model GPU serving |
| vLLM | LLM serving throughput cao | OpenAI-compatible API, continuous batching, memory-efficient KV cache | Phụ thuộc model architecture được hỗ trợ, cần GPU memory planning | Self-host LLM chat/completion, cần throughput tốt |
| TGI | Hugging Face text generation serving | Streaming, tensor parallel, hợp HF ecosystem | Tuning vẫn cần GPU/ops skill, API khác nhau theo phiên bản | Self-host HF model, muốn runtime chuyên cho generation |

Best solution theo context:

| Context | Giải pháp nên chọn |
|---|---|
| Mini-project hoặc RAG product mới | FastAPI gateway + RAG services rõ boundary |
| LLM self-host có traffic thật | FastAPI gateway + vLLM hoặc TGI phía sau |
| Model CV/NLP cần GPU throughput | FastAPI gateway + Triton |
| Classical ML hoặc embedding service Python-first | BentoML hoặc FastAPI tùy team |
| Org đã có PyTorch serving platform | TorchServe nếu vận hành đã mature |
| Cần ship nhanh, data không quá nhạy | FastAPI gateway + managed model API |

## 9. Best practices

1. Load model/runtime một lần ở startup, warm up trước khi `/ready` trả `ready`.
2. Tách `/health` và `/ready`. Liveness không nên fail vì vector DB chậm tạm thời.
3. Dùng Pydantic để validate request và response. Reject field lạ nếu contract cần chặt.
4. Luôn trả `trace_id`, `model_version` hoặc `pipeline_version`.
5. Log structured JSON với stage latency, input length, output tokens, tenant và error code.
6. Không log raw prompt/response nếu có PII, hoặc phải redact trước khi lưu.
7. Đặt timeout ở gateway và upstream client. Không chỉ dựa vào proxy timeout.
8. Có concurrency limit để bảo vệ GPU/KV cache/provider quota.
9. Streaming phải handle client disconnect và vẫn release resource.
10. Với RAG, response phải có citation và citation validator trước khi trả client.
11. Với self-host LLM, dùng runtime chuyên dụng cho batching thay vì tự batch trong FastAPI.
12. Với multi-tenant, rate limit theo tenant/user/API key và có token budget.

## 10. Dùng được trong production không?

Câu trả lời thực tế: pattern trong bài dùng được trong production, nhưng sample code chỉ là baseline học tập. Có thể đưa vào production khi thỏa các điều kiện sau:

- Runtime thật đã được tách rõ: model/RAG pipeline có version, health check, warmup và rollback plan.
- Rate limit chuyển từ in-memory sang Redis/API Gateway hoặc quota service tập trung.
- Có auth thật, tenant isolation và policy không log PII.
- Timeout được đặt ở gateway, upstream client, reverse proxy và model server.
- Concurrency limit được sizing bằng load test trên CPU/GPU thật.
- Với LLM self-host, FastAPI chỉ làm gateway, còn batching và KV cache do vLLM/TGI/Triton hoặc runtime chuyên dụng xử lý.
- Có metrics cho request count, error rate, timeout rate, p50/p95/p99 latency, tokens/sec, cost và GPU memory.
- Có CI test cho schema, error contract, streaming event format và regression test cho RAG output.
- Có deployment strategy: canary, rollback, model version pinning và dashboard.

Không nên gọi là production-ready nếu:

- Model load trong mỗi request.
- Không có timeout/concurrency limit.
- Không có trace id hoặc model version trong response.
- Dùng in-memory limiter với nhiều replicas nhưng tưởng là global quota.
- SSE stream không release resource khi client disconnect.
- Chưa load test p95 latency và OOM behavior.

## 11. Kết luận

FastAPI là lựa chọn tốt cho serving contract, orchestration và product boundary. Nhưng với GPU throughput hoặc LLM traffic nghiêm túc, FastAPI nên đứng trước model server chuyên dụng. Production serving không chỉ là "API chạy được", mà là một hệ thống có contract, limit, observability, versioning và rollback.
