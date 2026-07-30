# Day 30 Document: Production Reference

## 1. Decision Framework

Quyết định quantization nên đi theo thứ tự này:

```text
1. Xác định task và SLA
2. Chọn baseline model FP16/BF16 hoặc hosted model mạnh
3. Tạo golden set và metric
4. Chọn runtime theo hardware
5. Thử quantization theo memory target
6. Benchmark latency + throughput + memory
7. Eval quality regression
8. Quyết định production/canary/rollback
```

Nếu bỏ qua bước 2 và 3, bạn chỉ đang tối ưu chi phí mà không biết mình mất gì.

## 2. Runtime Và Quantization Matrix

| Runtime | Format phổ biến | Mạnh ở đâu | Production concern |
|---|---|---|---|
| Ollama | GGUF | Dev local, internal service nhỏ, API đơn giản | Kiểm soát batching/throughput hạn chế hơn vLLM |
| llama.cpp server | GGUF | CPU, Apple Silicon, edge, GPU offload | Cần tự build API/ops nhiều hơn |
| vLLM | FP16/BF16, AWQ/GPTQ tùy version/model | Throughput GPU, continuous batching | Cần GPU, setup và capacity planning |
| TGI | FP16/BF16, quantized tùy backend | HuggingFace ecosystem | Ops phức tạp hơn demo local |
| TensorRT-LLM | FP16/BF16/INT8/INT4 tùy pipeline | Tối ưu NVIDIA production | Build/deploy phức tạp |

Best solution không cố định:

- Laptop/offline: GGUF + llama.cpp/Ollama.
- GPU production throughput: vLLM hoặc TGI.
- NVIDIA optimization sâu: TensorRT-LLM.
- Quality-sensitive: bắt đầu bằng FP16/BF16, quantize sau khi có eval.

## 3. VRAM Estimation Cheat Sheet

### Weights

```text
weights_gb ~= params_billion * bytes_per_param
```

| Precision | Bytes/param | 7B rough | 13B rough |
|---|---:|---:|---:|
| FP32 | 4 | 28GB | 52GB |
| FP16/BF16 | 2 | 14GB | 26GB |
| INT8 | 1 | 7GB | 13GB |
| INT4 | 0.5 + overhead | 4-5.5GB | 7.5-10GB |

### KV Cache

```text
kv_cache_bytes ~= layers * 2 * kv_heads * head_dim * seq_len * concurrent_sequences * bytes
```

Ví dụ cách nghĩ:

```text
Nếu tăng max context từ 4k lên 16k,
KV cache tăng xấp xỉ 4 lần.

Nếu tăng concurrency từ 2 lên 8,
KV cache tăng xấp xỉ 4 lần.
```

### Safety Margin

Thêm margin vì:

- CUDA graph/cache/runtime allocation.
- Tokenizer và HTTP process memory.
- Fragmentation.
- Batch scheduler.
- Log/metrics buffer.
- Framework overhead.

Rule thực dụng: nếu estimate là 7.5GB trên GPU 8GB, xem như không đủ. Hãy giảm context, giảm concurrency, đổi quantization hoặc chọn model nhỏ hơn.

## 4. FastAPI Gateway Template

Template này dùng OpenAI-compatible endpoint, phù hợp với Ollama `/v1`, llama.cpp server OpenAI-compatible, vLLM OpenAI server hoặc TGI-compatible adapter nếu có.

Preflight trước khi mở gateway cho product:

```bash
curl "$LOCAL_LLM_BASE_URL/models" \
  -H "Authorization: Bearer $LOCAL_LLM_API_KEY"

curl "$LOCAL_LLM_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $LOCAL_LLM_API_KEY" \
  -H "content-type: application/json" \
  -d '{
    "model": "'"$LOCAL_LLM_MODEL"'",
    "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
    "temperature": 0,
    "max_tokens": 8
  }'
```

Nếu runtime là vLLM và bạn chạy `--served-model-name local-chat`, gateway phải gửi `LOCAL_LLM_MODEL=local-chat`. Nếu model name không khớp, lỗi thường xuất hiện ở runtime, không phải ở FastAPI validation.

### Install

```bash
pip install -U fastapi uvicorn httpx pydantic psutil
```

### Run

```bash
export LOCAL_LLM_BASE_URL=http://localhost:11434/v1
export LOCAL_LLM_API_KEY=local
export LOCAL_LLM_MODEL=llama3.2
export LOCAL_LLM_RUNTIME=ollama
export REQUEST_TIMEOUT_S=60
export QUEUE_TIMEOUT_S=2
export MAX_CONCURRENCY=4

uvicorn app:app --host 0.0.0.0 --port 9000
```

### `app.py`

```python
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("local_model_api")


class Settings(BaseModel):
    runtime_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    api_key: str = os.getenv("LOCAL_LLM_API_KEY", "local")
    model: str = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
    runtime: str = os.getenv("LOCAL_LLM_RUNTIME", "ollama")
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "60"))
    queue_timeout_s: float = float(os.getenv("QUEUE_TIMEOUT_S", "2"))
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "4"))
    max_input_chars: int = int(os.getenv("MAX_INPUT_CHARS", "8000"))
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))


settings = Settings()
semaphore = asyncio.Semaphore(settings.max_concurrency)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    system: str = Field(default="You are a concise internal assistant.", max_length=2000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    max_tokens: int = Field(default=512, ge=1)


class ChatResponse(BaseModel):
    answer: str
    model: str
    runtime: str
    latency_ms: float
    memory_rss_mb: float
    trace_id: str


class ErrorDetail(BaseModel):
    trace_id: str
    error: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


def validate_limits(req: ChatRequest) -> None:
    if len(req.message) > settings.max_input_chars:
        raise HTTPException(status_code=413, detail="message too large")
    if req.max_tokens > settings.max_output_tokens:
        raise HTTPException(status_code=422, detail="max_tokens exceeds server limit")


async def call_model(client: httpx.AsyncClient, req: ChatRequest) -> str:
    headers = {"Authorization": f"Bearer {settings.api_key}"}
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": req.system},
            {"role": "user", "content": req.message},
        ],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }

    response = await client.post(
        f"{settings.runtime_base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("runtime response does not match chat completion contract") from exc
    if not isinstance(content, str):
        raise ValueError("runtime response content must be a string")
    return content


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_s),
        limits=httpx.Limits(
            max_connections=settings.max_concurrency,
            max_keepalive_connections=settings.max_concurrency,
        ),
    )
    app.state.http_client = client
    try:
        response = await client.get(
            f"{settings.runtime_base_url.rstrip('/')}/models",
            timeout=5,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning(json.dumps({"event": "model_runtime_not_ready", "error": str(exc)}))

    yield

    await client.aclose()


app = FastAPI(
    title="Local Model API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> dict[str, Any]:
    try:
        response = await request.app.state.http_client.get(
            f"{settings.runtime_base_url.rstrip('/')}/models",
            timeout=5,
        )
        response.raise_for_status()
        model_ids = {
            item.get("id")
            for item in response.json().get("data", [])
            if isinstance(item, dict)
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"trace_id": "readiness", "error": type(exc).__name__},
        ) from exc
    if model_ids and settings.model not in model_ids:
        raise HTTPException(
            status_code=503,
            detail={"trace_id": "readiness", "error": "configured model is not served"},
        )
    return {
        "status": "ready",
        "model": settings.model,
        "runtime": settings.runtime,
        "max_concurrency": settings.max_concurrency,
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    validate_limits(req)

    trace_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()

    acquired = False
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=settings.queue_timeout_s)
        acquired = True
        answer = await asyncio.wait_for(
            call_model(request.app.state.http_client, req),
            timeout=settings.request_timeout_s + 1,
        )
    except asyncio.TimeoutError as exc:
        error = "model timeout" if acquired else "queue timeout"
        status_code = 504 if acquired else 503
        raise HTTPException(
            status_code=status_code,
            detail={"trace_id": trace_id, "error": error},
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail={"trace_id": trace_id, "error": f"runtime returned {exc.response.status_code}"},
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail={"trace_id": trace_id, "error": "invalid runtime response"},
        ) from exc
    except Exception as exc:
        logger.exception(json.dumps({"event": "chat_failed", "trace_id": trace_id}))
        raise HTTPException(
            status_code=500,
            detail={"trace_id": trace_id, "error": type(exc).__name__},
        ) from exc
    finally:
        if acquired:
            semaphore.release()

    latency_ms = (time.perf_counter() - start) * 1000
    memory_rss_mb = psutil.Process().memory_info().rss / 1024 / 1024

    logger.info(
        json.dumps(
            {
                "event": "chat_completed",
                "trace_id": trace_id,
                "model": settings.model,
                "runtime": settings.runtime,
                "latency_ms": round(latency_ms, 2),
                "input_chars": len(req.message),
                "output_chars": len(answer),
                "max_tokens": req.max_tokens,
                "memory_rss_mb": round(memory_rss_mb, 2),
            },
            ensure_ascii=False,
        )
    )

    return ChatResponse(
        answer=answer,
        model=settings.model,
        runtime=settings.runtime,
        latency_ms=round(latency_ms, 2),
        memory_rss_mb=round(memory_rss_mb, 2),
        trace_id=trace_id,
    )
```

`memory_rss_mb` trong response là RSS của FastAPI gateway process. Nó hữu ích để phát hiện gateway leak memory, nhưng không đo VRAM/RAM của process model server. Memory thật của model phải lấy từ runtime metrics, `nvidia-smi`, `ollama ps`, `ps/top` theo PID model server hoặc dashboard/container metrics.

Các chi tiết quan trọng trong template:

- `httpx.AsyncClient` được tạo một lần trong FastAPI lifespan để tái sử dụng connection pool và đóng đúng lúc shutdown.
- `/ready` kiểm tra runtime tại thời điểm probe, không dùng một boolean chỉ set lúc startup.
- Semaphore có queue timeout. Nếu service đã đầy, trả `503` thay vì để request chờ vô hạn.
- Error model phản ánh đúng envelope mặc định của `HTTPException`: `{"detail": {...}}`.

## 5. Benchmark Script

### `benchmark_local_api.py`

```python
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass

import httpx
import psutil


PROMPTS = [
    "Tóm tắt local LLM trong 3 bullet.",
    "So sánh INT8 và INT4 cho production serving.",
    "Trả lời JSON với keys: risks, metrics, rollback.",
    "Giải thích vì sao KV cache tăng theo context length.",
]


@dataclass
class Result:
    latency_ms: float
    ok: bool
    output_chars: int
    error: str | None = None


async def one_request(client: httpx.AsyncClient, url: str, prompt: str, max_tokens: int) -> Result:
    start = time.perf_counter()
    try:
        response = await client.post(
            url,
            json={"message": prompt, "max_tokens": max_tokens},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        data = response.json()
        return Result(latency_ms=elapsed_ms, ok=True, output_chars=len(data.get("answer", "")))
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return Result(latency_ms=elapsed_ms, ok=False, output_chars=0, error=type(exc).__name__)


async def run(
    url: str,
    concurrency: int,
    repeat: int,
    timeout_s: float,
    max_tokens: int,
) -> list[Result]:
    prompts = (PROMPTS * repeat)[: len(PROMPTS) * repeat]
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    results: list[Result] = []

    async with httpx.AsyncClient(timeout=timeout_s, limits=limits) as client:
        pending = []
        for prompt in prompts:
            pending.append(one_request(client, url, prompt, max_tokens))
            if len(pending) == concurrency:
                yield_results = await asyncio.gather(*pending)
                for item in yield_results:
                    results.append(item)
                pending = []
        if pending:
            for item in await asyncio.gather(*pending):
                results.append(item)
    return results


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * pct) - 1))
    return ordered[index]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:9000/chat")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--timeout-s", type=float, default=90)
    parser.add_argument("--max-tokens", type=int, default=300)
    args = parser.parse_args()

    process = psutil.Process()
    rss_before_mb = process.memory_info().rss / 1024 / 1024
    started = time.perf_counter()

    results = asyncio.run(
        run(args.url, args.concurrency, args.repeat, args.timeout_s, args.max_tokens)
    )

    total_s = time.perf_counter() - started
    rss_after_mb = process.memory_info().rss / 1024 / 1024
    ok_latencies = [r.latency_ms for r in results if r.ok]
    errors = [r.error for r in results if not r.ok]

    print(
        {
            "count": len(results),
            "ok": len(ok_latencies),
            "error_count": len(errors),
            "error_types": sorted(set(e for e in errors if e)),
            "total_s": round(total_s, 2),
            "attempted_requests_per_s": round(len(results) / total_s, 2) if total_s else 0,
            "successful_requests_per_s": round(len(ok_latencies) / total_s, 2) if total_s else 0,
            "p50_ms": round(statistics.median(ok_latencies), 2) if ok_latencies else 0,
            "p95_ms": round(percentile(ok_latencies, 0.95), 2),
            "p99_ms": round(percentile(ok_latencies, 0.99), 2),
            "avg_ms": round(statistics.mean(ok_latencies), 2) if ok_latencies else 0,
            "avg_output_chars": round(statistics.mean([r.output_chars for r in results if r.ok]), 2)
            if ok_latencies
            else 0,
            "client_rss_before_mb": round(rss_before_mb, 2),
            "client_rss_after_mb": round(rss_after_mb, 2),
        }
    )
```

Lưu ý: script này đo memory của benchmark client, không đo VRAM của model server. Với GPU, ghi thêm `nvidia-smi` hoặc metric từ runtime.

## 6. Memory Measurement

### CPU/RAM

```bash
ps -o pid,rss,comm -p <PID>
top -p <PID>
```

### NVIDIA GPU

```bash
nvidia-smi --query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu --format=csv -l 1
```

### Ollama

```bash
ollama ps
```

Ghi memory ở ba thời điểm:

1. Trước khi gọi request.
2. Sau warmup.
3. Trong benchmark concurrency cao nhất.

## 7. Quality Evaluation Checklist

Golden set nên có:

- Prompt tiếng Việt thực tế.
- Prompt dài gần giới hạn context.
- Structured output JSON.
- Câu hỏi cần citation nếu dùng RAG.
- Case từ chối trả lời nếu policy yêu cầu.
- Case dễ hallucinate.
- Case domain-specific.

Metric:

- Exact/schema validity cho JSON.
- Task accuracy cho classification/extraction.
- Human rating cho long-form answer.
- Citation correctness nếu RAG.
- Regression count giữa FP16/BF16 và quantized.

Decision rule ví dụ:

```text
Chấp nhận INT4 nếu:
- p95 latency giảm hoặc memory fit rõ ràng,
- format accuracy giảm không quá 1%,
- task accuracy giảm không quá 2%,
- không tăng critical hallucination,
- error rate < 0.5% dưới benchmark target.
```

Ngưỡng thật phải theo domain. Với medical/legal/finance, ngưỡng regression phải nghiêm hơn nhiều và thường cần human review.

## 8. Production Checklist

- [ ] Model id, revision, quantization format được pin.
- [ ] License base model và quantized checkpoint được review.
- [ ] Có golden eval trước/sau quantization.
- [ ] Có latency benchmark với prompt ngắn/dài và output ngắn/dài.
- [ ] Có concurrency test đến mức traffic target.
- [ ] Có memory peak sau warmup và khi tải cao.
- [ ] Có API schema và response model.
- [ ] Có timeout ở gateway và runtime.
- [ ] Có max input length, max output tokens, max concurrency.
- [ ] Có `/health` cho process sống.
- [ ] Có `/ready` cho runtime/model sẵn sàng.
- [ ] Có structured logs với `trace_id`.
- [ ] Không log raw prompt chứa PII/secrets.
- [ ] Có metrics p50/p95/p99, error rate, tokens/sec.
- [ ] Có fallback hoặc graceful degradation.
- [ ] Có canary và rollback.

## 9. Câu Trả Lời Production

Dùng được trong production không? Có, nếu local model API được vận hành như một service production thật: contract rõ, benchmark rõ, quality eval rõ, capacity rõ, timeout rõ, monitoring rõ, license rõ và rollback rõ.

Không dùng được trong production nếu chỉ có một model quantized chạy được trên máy cá nhân. "Chạy được" khác với "chịu được traffic thật, lỗi có kiểm soát, chất lượng đo được và rollback được".

## 10. Nguồn đã đối chiếu

Đối chiếu ngày 2026-06-08 qua Context7 và tài liệu chính thức:

- FastAPI lifespan để quản lý shared resources: https://fastapi.tiangolo.com/advanced/events/
- FastAPI Pydantic request body/validation: https://fastapi.tiangolo.com/tutorial/body/
- FastAPI response model và additional responses: https://fastapi.tiangolo.com/tutorial/response-model/ và https://fastapi.tiangolo.com/advanced/additional-responses/
- FastAPI `HTTPException`: https://fastapi.tiangolo.com/tutorial/handling-errors/
- vLLM OpenAI-compatible server và model aliases: https://github.com/vllm-project/vllm/blob/v0.14.0rc2/docs/serving/openai_compatible_server.md
- llama.cpp server/GGUF runtime: https://github.com/ggml-org/llama.cpp/tree/master/tools/server
