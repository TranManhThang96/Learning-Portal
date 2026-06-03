# Day 29 Document: Local LLM Serving Gần Production

Tài liệu này đưa phần lý thuyết Day 29 thành một skeleton thực tế: config, OpenAI-compatible client abstraction, FastAPI proxy, health check, logging, timeout/retry và benchmark.

Các ví dụ dùng OpenAI Python client với `base_url`, `timeout` và `max_retries` theo API hiện hành, phù hợp khi runtime local expose OpenAI-compatible endpoint như Ollama hoặc vLLM.

## 1. Cấu Hình Runtime

### Ollama

```bash
ollama pull llama3.2
ollama serve
```

Endpoint tham khảo:

```text
Native: http://localhost:11434/api/chat
OpenAI-compatible: http://localhost:11434/v1
```

### vLLM

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name local-chat
```

Endpoint tham khảo:

```text
OpenAI-compatible: http://localhost:8000/v1
```

### llama.cpp

```bash
./build/bin/llama-server \
  -m ./models/model-q4_k_m.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 4096 \
  -ngl 99
```

Tùy version/build, API có thể khác nhau. Trước khi viết adapter production, luôn kiểm tra endpoint `/health`, `/v1/models`, `/v1/chat/completions` hoặc endpoint native mà runtime cung cấp.

## 2. Environment Config

Ví dụ `.env`:

```bash
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_API_KEY=local
LOCAL_LLM_MODEL=llama3.2
LOCAL_LLM_RUNTIME=ollama
LOCAL_LLM_TIMEOUT_S=30
LOCAL_LLM_MAX_RETRIES=2
LOCAL_LLM_MAX_TOKENS=512
LOCAL_LLM_TEMPERATURE=0.2
LOG_LEVEL=INFO
```

Production nên pin thêm:

```bash
MODEL_ID=llama3.2
MODEL_REVISION=exact-revision-or-digest
MODEL_LICENSE=check-model-card
RUNTIME_VERSION=ollama-or-vllm-version
QUANTIZATION=q4_k_m-or-fp16
MAX_CONTEXT_TOKENS=4096
```

## 3. OpenAI-compatible Client Abstraction

File ví dụ `local_llm_client.py`:

```python
from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError, APIStatusError

logger = logging.getLogger("local_llm")


@dataclass(frozen=True)
class LocalLLMConfig:
    base_url: str
    api_key: str
    model: str
    runtime: str
    timeout_s: float = 30.0
    max_retries: int = 2
    temperature: float = 0.2
    max_tokens: int = 512

    @classmethod
    def from_env(cls) -> "LocalLLMConfig":
        return cls(
            base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("LOCAL_LLM_API_KEY", "local"),
            model=os.getenv("LOCAL_LLM_MODEL", "llama3.2"),
            runtime=os.getenv("LOCAL_LLM_RUNTIME", "ollama"),
            timeout_s=float(os.getenv("LOCAL_LLM_TIMEOUT_S", "30")),
            max_retries=int(os.getenv("LOCAL_LLM_MAX_RETRIES", "2")),
            temperature=float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("LOCAL_LLM_MAX_TOKENS", "512")),
        )


class LocalLLMClient:
    def __init__(self, config: LocalLLMConfig) -> None:
        self.config = config
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout_s,
            max_retries=config.max_retries,
        )

    def chat(self, messages: list[dict[str, str]], trace_id: str | None = None) -> dict[str, Any]:
        trace_id = trace_id or str(uuid.uuid4())
        start = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            text = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)

            logger.info(
                "llm_request_success",
                extra={
                    "trace_id": trace_id,
                    "runtime": self.config.runtime,
                    "model": self.config.model,
                    "latency_ms": round(latency_ms, 2),
                    "input_tokens": getattr(usage, "prompt_tokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None),
                },
            )

            return {
                "trace_id": trace_id,
                "runtime": self.config.runtime,
                "model": self.config.model,
                "text": text,
                "latency_ms": latency_ms,
                "input_tokens": getattr(usage, "prompt_tokens", None),
                "output_tokens": getattr(usage, "completion_tokens", None),
            }

        except (APITimeoutError, APIConnectionError, RateLimitError, APIStatusError) as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "llm_request_failed",
                extra={
                    "trace_id": trace_id,
                    "runtime": self.config.runtime,
                    "model": self.config.model,
                    "latency_ms": round(latency_ms, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise
```

Điểm production quan trọng:

- `base_url` giúp trỏ cùng client tới Ollama, vLLM, llama.cpp hoặc cloud-compatible endpoint.
- `timeout` tránh request treo vô hạn.
- `max_retries` xử lý lỗi tạm thời, nhưng không nên retry quá nhiều với request sinh text dài.
- Log có `trace_id`, runtime, model và latency; không log full prompt nếu có dữ liệu nhạy cảm.

## 4. FastAPI Proxy/Gateway

File ví dụ `app.py`:

```python
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from openai import APIConnectionError, APITimeoutError, RateLimitError, APIStatusError
from pydantic import BaseModel, Field

from local_llm_client import LocalLLMClient, LocalLLMConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_gateway")

config = LocalLLMConfig.from_env()
llm = LocalLLMClient(config)
app = FastAPI(title="Local LLM Gateway", version="0.1.0")


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    model_policy: str = "default"


class ChatResponse(BaseModel):
    trace_id: str
    runtime: str
    model: str
    text: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "runtime": config.runtime,
        "model": config.model,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> dict[str, object]:
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    start = time.perf_counter()

    try:
        messages = [message.model_dump() for message in payload.messages]
        result = llm.chat(messages=messages, trace_id=trace_id)
        return result
    except APITimeoutError as exc:
        raise HTTPException(status_code=504, detail="LLM timeout") from exc
    except (APIConnectionError, RateLimitError) as exc:
        raise HTTPException(status_code=503, detail="LLM unavailable") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM upstream error: {exc.status_code}") from exc
    finally:
        logger.info(
            "gateway_request_finished",
            extra={
                "trace_id": trace_id,
                "path": str(request.url.path),
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
```

Chạy local:

```bash
pip install -U fastapi uvicorn openai
uvicorn app:app --host 0.0.0.0 --port 9000
```

Gọi thử:

```bash
curl http://localhost:9000/chat \
  -H 'content-type: application/json' \
  -H 'x-trace-id: demo-001' \
  -d '{
    "messages": [
      {"role": "user", "content": "Tóm tắt local LLM trong 3 bullet."}
    ]
  }'
```

Production cần thêm:

- AuthN/AuthZ.
- Rate limit theo user/tenant.
- Request body size limit.
- Prompt redaction trước logging.
- Streaming endpoint nếu UX cần.
- Fallback policy.
- Circuit breaker nếu runtime lỗi liên tục.
- Metrics endpoint Prometheus hoặc OpenTelemetry.

## 5. Health Check Thật Hơn

`/health` chỉ kiểm tra process gateway sống. Với LLM serving, nên có thêm `/ready` hoặc scheduled probe:

```python
@app.get("/ready")
def ready() -> dict[str, object]:
    started = time.perf_counter()
    try:
        result = llm.chat(
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            trace_id="readiness-probe",
        )
        return {
            "status": "ready",
            "runtime": config.runtime,
            "model": config.model,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "sample_ok": "ok" in result["text"].lower(),
        }
    except Exception:
        logger.exception("llm_readiness_failed")
        raise HTTPException(status_code=503, detail="LLM not ready")
```

Không nên gọi generation nặng trong health check quá thường xuyên. Với Kubernetes, tách:

- Liveness: process còn sống.
- Readiness: model đã load và endpoint nhận request.
- Synthetic probe: chạy định kỳ ngoài request path để kiểm tra chất lượng/latency.

## 6. Benchmark Script

File ví dụ `benchmark_local_llm.py`:

```python
from __future__ import annotations

import concurrent.futures
import os
import statistics
import time
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class Sample:
    name: str
    prompt: str


samples = [
    Sample("short", "Tóm tắt local LLM trong 3 bullet."),
    Sample("json", "Trả lời JSON với keys: runtime, strengths, risks."),
    Sample("long_context", "Giải thích KV cache cho senior software engineer. " * 80),
]

client = OpenAI(
    base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("LOCAL_LLM_API_KEY", "local"),
    timeout=float(os.getenv("LOCAL_LLM_TIMEOUT_S", "60")),
    max_retries=int(os.getenv("LOCAL_LLM_MAX_RETRIES", "1")),
)
model = os.getenv("LOCAL_LLM_MODEL", "llama3.2")


def run_once(sample: Sample) -> dict[str, object]:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": sample.prompt}],
        temperature=0.2,
        max_tokens=256,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    return {
        "sample": sample.name,
        "latency_ms": latency_ms,
        "chars": len(text),
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, int(round((pct / 100) * (len(values) - 1))))
    return values[index]


def main() -> None:
    iterations = int(os.getenv("BENCH_ITERATIONS", "10"))
    concurrency = int(os.getenv("BENCH_CONCURRENCY", "1"))
    jobs = [sample for sample in samples for _ in range(iterations)]

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(run_once, jobs))
    total_s = time.perf_counter() - started

    latencies = [float(item["latency_ms"]) for item in results]
    print(
        {
            "model": model,
            "requests": len(results),
            "concurrency": concurrency,
            "total_s": round(total_s, 2),
            "rps": round(len(results) / total_s, 2),
            "latency_avg_ms": round(statistics.mean(latencies), 2),
            "latency_p50_ms": round(percentile(latencies, 50), 2),
            "latency_p95_ms": round(percentile(latencies, 95), 2),
            "latency_p99_ms": round(percentile(latencies, 99), 2),
        }
    )


if __name__ == "__main__":
    main()
```

Chạy:

```bash
BENCH_ITERATIONS=5 BENCH_CONCURRENCY=1 python benchmark_local_llm.py
BENCH_ITERATIONS=10 BENCH_CONCURRENCY=4 python benchmark_local_llm.py
```

Khi benchmark production candidate, ghi thêm bằng tool hệ thống:

```bash
nvidia-smi
docker stats
top
```

## 7. Decision Record Template

```markdown
# Local LLM Decision Record

## Use case
- Task:
- User:
- Data sensitivity:
- Expected traffic:
- Latency SLO:

## Runtime tested
- Ollama:
- llama.cpp:
- vLLM:
- TGI:
- Cloud baseline:

## Model
- model_id:
- revision/digest:
- license:
- quantization:
- context window:
- runtime version:

## Benchmark
- prompt short p50/p95:
- prompt long p50/p95:
- concurrency tested:
- RAM/VRAM observed:
- error rate:
- quality score:

## Decision
- Dev runtime:
- Production candidate:
- Fallback:
- Rollout plan:
- Rollback plan:

## Risks
- Quality:
- Latency:
- Security/privacy:
- License:
- Ops:
```

## 8. Common Pitfalls

- Chọn model theo leaderboard nhưng không chạy golden eval của use case.
- Benchmark prompt ngắn rồi production lại dùng RAG context dài.
- Quên kiểm tra license model.
- Log full prompt chứa PII.
- Không giới hạn `max_tokens`, dẫn tới latency và cost compute khó kiểm soát.
- Retry request generation dài quá nhiều lần, làm tải tăng khi runtime đang lỗi.
- Không tách gateway khỏi runtime, khiến đổi Ollama sang vLLM phải sửa business code.
- Không có fallback khi GPU OOM hoặc runtime restart.
- Nhầm average latency với user experience; p95/p99 mới phản ánh sự khó chịu của user.
