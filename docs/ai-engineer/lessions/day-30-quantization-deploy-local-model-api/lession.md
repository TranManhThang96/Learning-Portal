# Day 30: Quantization & Deploy Local Model API

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Giải thích FP32, FP16, BF16, INT8, INT4 và tác động của dtype lên memory, latency, throughput, cost.
- Phân biệt GGUF, AWQ, GPTQ ở góc nhìn format, runtime và deployment.
- Ước lượng RAM/VRAM cho model weights, KV cache, runtime overhead và concurrency.
- Chọn quantization theo context thay vì chọn theo cảm tính.
- Expose local model qua FastAPI gateway có request/response schema, health, readiness, timeout, concurrency limit và structured logging.
- Benchmark latency, throughput, tokens/sec, memory usage và quality regression trước/sau quantization.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

Quantization giảm memory footprint bằng cách lưu weights ở precision thấp hơn, ví dụ INT8 hoặc INT4 thay vì FP16/BF16. Nó giúp chạy model lớn hơn trên cùng phần cứng và có thể giảm cost, nhưng không tự động làm model nhanh hơn hoặc tốt hơn. Bottleneck có thể chuyển sang KV cache, prefill, decode kernel, CPU memory bandwidth, GPU occupancy hoặc network/API queue.

Production local model API không nên chỉ là một script gọi model. Bạn cần một gateway có schema rõ, timeout, readiness, concurrency control, logging, benchmark, quality eval, fallback và rollback. Nếu không đo cả latency, memory và quality, bạn chưa thật sự biết quantized model có dùng được không.

## 1. Bài Này Nằm Ở Đâu Trong Lộ Trình

Day 25-28 giúp bạn quyết định khi nào fine-tune, chuẩn bị dataset, chạy LoRA/QLoRA và evaluate model. Day 29 giới thiệu Ollama, llama.cpp, vLLM và local LLM runtime. Day 30 là bước đóng gói local model thành API có thể đưa vào hệ thống thật.

```text
Day 25: quyết định RAG/fine-tune/tool/prompt
Day 26: dataset instruction tuning
Day 27: LoRA/QLoRA hands-on
Day 28: evaluation trước/sau fine-tune
Day 29: local LLM runtime: Ollama, llama.cpp, vLLM
Day 30: quantization + local model API + benchmark
```

Kỹ năng chính của ngày này không phải là biết thật nhiều tên format. Kỹ năng chính là ra quyết định engineering: model nào, quantization nào, runtime nào, trên phần cứng nào, với SLA nào, và regression chấp nhận được là bao nhiêu.

## 2. Mental Model: Precision Là Gì

Model có hàng tỷ tham số. Mỗi tham số là một số. Precision quyết định số đó được lưu bằng bao nhiêu byte và biểu diễn chi tiết tới mức nào.

| Dtype | Bytes/param | Hay dùng khi | Điểm mạnh | Điểm yếu |
|---|---:|---|---|---|
| FP32 | 4 | Training baseline, research, CPU ops cần chính xác | Ổn định, ít lỗi số học | Quá tốn memory cho inference LLM |
| FP16 | 2 | GPU inference/training phổ biến | Nhanh, tiết kiệm 50% so với FP32 | Dynamic range hẹp hơn BF16 |
| BF16 | 2 | GPU mới, training/inference ổn định | Dynamic range gần FP32 hơn FP16 | Không phải phần cứng nào cũng tối ưu |
| INT8 | 1 | Quantized inference | Giảm memory mạnh, quality thường còn tốt | Cần kernel/runtime hỗ trợ tốt |
| INT4 | 0.5 | Local/edge/GPU VRAM hạn chế | Chạy được model lớn hơn nhiều | Quality regression dễ thấy hơn, kernel phụ thuộc runtime |

Rule đơn giản:

```text
weights_memory_gb ~= params_billion * bytes_per_param
```

Ví dụ rough cho weights, chưa tính KV cache và overhead:

| Model size | FP32 | FP16/BF16 | INT8 | INT4 thực tế |
|---|---:|---:|---:|---:|
| 3B | ~12GB | ~6GB | ~3GB | ~1.8-2.5GB |
| 7B | ~28GB | ~14GB | ~7GB | ~4-5.5GB |
| 13B | ~52GB | ~26GB | ~13GB | ~7.5-10GB |
| 70B | ~280GB | ~140GB | ~70GB | ~38-50GB |

INT4 thực tế thường lớn hơn `params * 0.5 byte` vì có scale, metadata, group size, tensor alignment và runtime overhead.

## 3. FP32, FP16, BF16 Step By Step

### FP32

FP32 là baseline dễ hiểu nhất: mỗi số dùng 32 bit. Khi training hoặc debug numerical issue, FP32 an toàn hơn. Với LLM inference, FP32 gần như không kinh tế vì memory và bandwidth quá lớn.

Nên dùng FP32 khi:

- Đang kiểm chứng correctness ở model nhỏ.
- Một operation cụ thể bị unstable ở precision thấp.
- CPU inference cho model nhỏ và latency không quan trọng.

Không nên dùng FP32 cho chat LLM production nếu có lựa chọn FP16/BF16 hoặc quantized.

### FP16

FP16 giảm một nửa memory so với FP32 và được GPU hỗ trợ rất tốt. Nhiều model serving GPU dùng FP16 làm baseline inference.

Nên dùng FP16 khi:

- Có GPU đủ VRAM.
- Cần quality baseline trước khi quantize.
- Runtime/kernel hỗ trợ FP16 tốt.

Rủi ro: một số workload có thể gặp overflow/underflow hoặc quality issue nếu model không phù hợp.

### BF16

BF16 cũng dùng 2 byte như FP16 nhưng có dynamic range tốt hơn. Với GPU hiện đại, BF16 thường là lựa chọn tốt cho training/inference nếu được hỗ trợ.

Nên dùng BF16 khi:

- GPU hỗ trợ BF16 tốt.
- Bạn muốn độ ổn định số học tốt hơn FP16.
- Model checkpoint hoặc runtime khuyến nghị BF16.

Trade-off: nếu phần cứng hoặc kernel không tối ưu BF16, latency có thể không tốt bằng FP16.

## 4. INT8 Và INT4 Step By Step

Quantization chuyển weights từ số thực precision cao sang số nguyên precision thấp cùng scale. Mục tiêu là giảm memory và memory bandwidth.

### INT8

INT8 thường là điểm cân bằng tốt khi bạn muốn giảm memory nhưng chưa muốn chịu regression lớn như INT4.

Phù hợp khi:

- GPU/CPU memory không đủ cho FP16/BF16.
- Task cần quality tương đối ổn định.
- Bạn có golden set để đo regression.

Không nên chọn nếu runtime không có kernel INT8 tốt. Khi đó INT8 có thể tiết kiệm memory nhưng latency không cải thiện đáng kể.

### INT4

INT4 giảm memory mạnh hơn, thường là chìa khóa để chạy model 7B/13B trên laptop hoặc GPU nhỏ. Nhưng INT4 dễ làm giảm chất lượng hơn, đặc biệt ở reasoning, math, code, structured output và tiếng Việt nếu base model yếu.

Phù hợp khi:

- Mục tiêu chính là fit vào RAM/VRAM.
- Traffic thấp hoặc medium.
- Task không quá nhạy với lỗi nhỏ.
- Có fallback hoặc human review.

Không phù hợp khi:

- Output phải tuyệt đối đúng schema hoặc số liệu.
- SLA chặt, traffic cao, context dài.
- Chưa có eval trước/sau quantization.

## 5. GGUF, AWQ, GPTQ

Không có chuyện "INT4 nào cũng như nhau". Bạn phải nói rõ format, runtime, kernel, model và hardware.

| Format | Runtime thường gặp | Mạnh ở đâu | Hạn chế | Context tốt |
|---|---|---|---|---|
| GGUF | llama.cpp, Ollama | Local CPU, Apple Silicon, GPU offload, file portable | Scale production lớn cần tự thiết kế nhiều hơn | Dev local, edge, internal tool nhỏ |
| AWQ | vLLM, TensorRT-LLM, ExLlama tùy model | INT4 GPU inference, thường giữ quality tốt | Cần kernel/runtime hỗ trợ đúng | GPU serving muốn tiết kiệm VRAM |
| GPTQ | ExLlama, AutoGPTQ, một số GPU runtime | Post-training quantization phổ biến | Quality/kernel phụ thuộc checkpoint | Community model, GPU nhỏ |

GGUF thường có các mức như `Q8_0`, `Q6_K`, `Q5_K_M`, `Q4_K_M`. Với local LLM, `Q4_K_M` thường là điểm bắt đầu thực dụng; `Q5_K_M` hoặc `Q6_K` tốt hơn nếu còn memory; `Q8_0` gần INT8 nhưng nặng hơn.

AWQ và GPTQ thường xuất hiện trong GPU serving. Chúng không tự nhiên tốt hơn GGUF; chúng tốt khi runtime của bạn tối ưu cho chúng.

## 6. KV Cache Là Gì Và Vì Sao Nó Quan Trọng

Transformer sinh text theo kiểu autoregressive: mỗi token mới phụ thuộc vào các token trước đó. Để không tính lại toàn bộ context ở mỗi bước, runtime lưu key/value của attention vào KV cache.

Rough formula:

```text
kv_cache_bytes ~= layers * 2 * kv_heads * head_dim * seq_len * concurrent_sequences * bytes_per_kv_element
```

Ý nghĩa:

- `layers`: model càng sâu, KV cache càng lớn.
- `2`: có key và value.
- `kv_heads`: GQA/MQA giảm số KV heads nên tiết kiệm memory.
- `seq_len`: prompt dài và output dài đều làm cache tăng.
- `concurrent_sequences`: concurrency càng cao, cache càng lớn.
- `bytes_per_kv_element`: FP16/BF16 thường 2 bytes; một số runtime hỗ trợ KV cache quantization.

Ví dụ intuition:

```text
Một model 7B INT4 có thể chỉ cần ~5GB weights,
nhưng với context dài và nhiều request song song,
KV cache + overhead có thể làm GPU 8GB OOM.
```

Production implication:

- Đặt `max_context`, `max_prompt_tokens`, `max_tokens` và `max_concurrency`.
- Đừng bật context 32k/128k chỉ vì model hỗ trợ nếu product không cần.
- Đo p95/p99 latency dưới prompt dài, không chỉ prompt ngắn.
- Theo dõi memory peak khi concurrency tăng.

## 7. VRAM Estimation Thực Tế

Ước lượng deployment cần tính đủ bốn phần:

```text
required_memory =
  weights_memory
  + kv_cache_memory
  + runtime_overhead
  + fragmentation_and_safety_margin
```

Checklist estimate:

1. Chọn model size và quantization.
2. Tính weights memory rough.
3. Ước lượng context length và concurrency.
4. Tính KV cache hoặc dùng memory profiling của runtime.
5. Thêm overhead 10-30% tùy runtime.
6. Chạy warmup và benchmark thật.

Ví dụ quyết định:

| Hardware | Model khả thi ban đầu | Gợi ý |
|---|---|---|
| Laptop 16GB RAM, không GPU | 3B/7B GGUF Q4 | Dùng Ollama/llama.cpp, context vừa phải |
| GPU 8GB VRAM | 7B INT4, context thấp-medium | Giới hạn concurrency, đo OOM |
| GPU 16GB VRAM | 7B FP16 hoặc 13B INT4 | Nếu task khó, thử 7B FP16 trước |
| GPU 24GB VRAM | 13B FP16 hoặc 30B+ INT4 tùy runtime | Đo throughput/p95 nghiêm túc |
| Multi-GPU | vLLM/TGI/TensorRT-LLM | Cần ops, batching, monitoring |

## 8. Throughput Vs Quality

Latency là thời gian một request. Throughput là tổng lượng xử lý trên một đơn vị thời gian, ví dụ requests/sec hoặc output tokens/sec. Quality là độ đúng của kết quả.

Ba thứ này thường kéo nhau:

- Model lớn hơn: quality có thể tốt hơn, latency/memory/cost tăng.
- Quantization thấp hơn: memory giảm, quality có thể giảm, speed phụ thuộc kernel.
- Batch lớn hơn: throughput tăng, latency từng request có thể tăng.
- Context dài hơn: answer có thể đủ thông tin hơn, prefill chậm và KV cache tăng.
- Concurrency cao hơn: GPU utilization tốt hơn, p95/p99 có thể xấu hơn.

Metric tối thiểu:

| Metric | Cần vì |
|---|---|
| TTFT | User cảm nhận phản hồi đầu tiên |
| Total latency | Request hoàn tất mất bao lâu |
| Output tokens/sec | Decode speed |
| Requests/sec | API throughput |
| RAM/VRAM peak | Có fit phần cứng không |
| Error rate | Timeout, OOM, 5xx, schema fail |
| Format accuracy | JSON/tool args có còn đúng không |
| Task score | Quality thật trên golden set |

## 9. Deploy Architecture

Không nên để product app gọi thẳng local runtime nếu bạn cần production control.

```text
Client / Product service
  -> FastAPI Local Model Gateway
      -> auth / API key / tenant policy
      -> request validation
      -> prompt template version
      -> timeout and max_tokens
      -> concurrency limiter
      -> structured logging / trace_id
      -> readiness check
      -> LocalLLMClient
          -> Ollama / llama.cpp server / vLLM / TGI
  -> Response
```

FastAPI gateway thêm giá trị:

- API contract ổn định dù runtime bên dưới thay đổi.
- Có thể enforce limit theo tenant.
- Có nơi log metric và redaction.
- Có timeout/fallback chuẩn.
- Có endpoint `/health` và `/ready` cho orchestrator.
- Có thể thêm canary, model routing, A/B test.

Theo docs FastAPI hiện tại, nên dùng Pydantic model cho validation/response filtering, `response_model` cho OpenAPI contract, `HTTPException` cho lỗi có kiểm soát, và lifespan cho startup/shutdown hoặc readiness state.

## 10. FastAPI Template Gần Production

Template đầy đủ hơn nằm trong `document.md`. Đây là skeleton quan trọng:

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

logger = logging.getLogger("local_model_api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class Settings(BaseModel):
    runtime_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    api_key: str = os.getenv("LOCAL_LLM_API_KEY", "local")
    model: str = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
    runtime: str = os.getenv("LOCAL_LLM_RUNTIME", "ollama")
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "60"))
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "4"))


settings = Settings()
semaphore = asyncio.Semaphore(settings.max_concurrency)
ready_state = {"ready": False, "last_error": None}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    system: str = Field(default="You are a concise internal assistant.", max_length=2000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    max_tokens: int = Field(default=512, ge=1, le=2048)


class ChatResponse(BaseModel):
    answer: str
    model: str
    runtime: str
    latency_ms: float
    memory_rss_mb: float
    trace_id: str


async def call_openai_compatible(req: ChatRequest) -> str:
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
    timeout = httpx.Timeout(settings.request_timeout_s)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.runtime_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"] or ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.get(f"{settings.runtime_base_url.rstrip('/')}/models")
        ready_state["ready"] = True
    except Exception as exc:
        ready_state["last_error"] = str(exc)
        logger.warning(json.dumps({"event": "model_runtime_not_ready", "error": str(exc)}))
    yield


app = FastAPI(title="Local Model API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    if not ready_state["ready"]:
        raise HTTPException(status_code=503, detail=ready_state)
    return {"status": "ready", "model": settings.model, "runtime": settings.runtime}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    trace_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()

    try:
        async with semaphore:
            answer = await asyncio.wait_for(
                call_openai_compatible(req),
                timeout=settings.request_timeout_s + 2,
            )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail={"trace_id": trace_id, "error": "timeout"}) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail={"trace_id": trace_id, "error": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"trace_id": trace_id, "error": type(exc).__name__}) from exc

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

Đây vẫn là gateway mẫu, chưa phải toàn bộ platform. Production thật cần thêm auth, rate limit, redaction, metrics exporter, container health policy, canary và deployment manifest.

## 11. Benchmark Latency Và Memory

Benchmark phải tách ít nhất ba nhóm:

1. Prompt ngắn, output ngắn: đo baseline overhead.
2. Prompt dài, output ngắn: đo prefill.
3. Prompt vừa, output dài: đo decode.

Benchmark tối thiểu:

```bash
pip install -U httpx psutil
python benchmark_local_api.py --url http://localhost:9000/chat --concurrency 4 --repeat 5
```

Khi ghi kết quả, luôn ghi kèm:

- Model id và revision.
- Quantization format: ví dụ `GGUF Q4_K_M`, `AWQ INT4`, `GPTQ INT4`, `FP16`.
- Runtime và version.
- Hardware: CPU, RAM, GPU, VRAM.
- Context length, max output tokens, concurrency.
- p50, p95, p99, error rate, output tokens/sec nếu đo được.
- RAM/VRAM peak sau warmup.

## 12. Production Decision: Dùng Được Không

Có, local quantized model API có thể dùng trong production, nhưng chỉ khi đáp ứng các điều kiện sau:

- Quality đạt ngưỡng trên golden set thật của sản phẩm, không chỉ test prompt thủ công.
- Có baseline so sánh với FP16/BF16 hoặc hosted model mạnh hơn.
- Latency p95/p99 đạt SLA dưới traffic và prompt length thực tế.
- Memory không OOM sau warmup, concurrency test và context dài.
- API gateway có validation, timeout, concurrency limit, health/readiness, structured logging và metric.
- Có fallback hoặc degradation path khi local runtime timeout/OOM/crash.
- Có review license của base model và quantized checkpoint.
- Có policy không log PII/secrets/raw prompt nhạy cảm.
- Có rollout plan: canary, rollback, model version pinning.

Không nên gọi là production nếu chỉ chạy được local demo, chưa có eval, chưa có monitoring, chưa có timeout, chưa có memory test và chưa có rollback.

## 13. Trade-off Và Best Solution Theo Context

| Context | Best starting solution | Vì sao | Cần tránh |
|---|---|---|---|
| Dev local, học tập, demo nội bộ | Ollama hoặc llama.cpp + GGUF Q4_K_M/Q5_K_M | Setup nhanh, ít ops | Đừng suy ra production throughput từ laptop demo |
| Internal RAG nhỏ, dữ liệu private | FastAPI gateway + Ollama/llama.cpp + model 7B/8B quantized | Đủ kiểm soát privacy, chi phí thấp | Context quá dài, không có eval citation |
| API production traffic vừa, có GPU | vLLM + AWQ/GPTQ hoặc FP16 + FastAPI gateway | Throughput tốt hơn, batching tốt hơn | Runtime không hỗ trợ quant format |
| Quality-sensitive reasoning/code | FP16/BF16 model tốt hơn, chỉ quantize sau eval | Giảm regression | Chọn INT4 chỉ vì tiết kiệm VRAM |
| Edge/offline | GGUF Q4/Q5, prompt ngắn, task hẹp | Fit phần cứng | Hứa SLA như cloud model lớn |
| Cost optimization cho task hẹp | Distill/fine-tune model nhỏ + INT8/INT4 | Rẻ và nhanh nếu task ổn định | Bỏ qua drift và quality monitoring |

## 14. Checklist

- [ ] Giải thích được FP32, FP16, BF16, INT8, INT4.
- [ ] Phân biệt được GGUF, AWQ, GPTQ theo runtime và deployment.
- [ ] Ước lượng được weights memory cho model 3B/7B/13B.
- [ ] Hiểu KV cache tăng theo context, output length và concurrency.
- [ ] Biết vì sao INT4 không luôn nhanh hơn FP16.
- [ ] Có FastAPI gateway với request/response schema.
- [ ] Có `/health` và `/ready`.
- [ ] Có timeout, concurrency limit và max token limit.
- [ ] Có benchmark p50/p95/p99 latency.
- [ ] Có đo RAM/VRAM peak sau warmup.
- [ ] Có golden set so sánh quality trước/sau quantization.
- [ ] Có câu trả lời production readiness rõ ràng.

## 15. Quiz Nhanh

1. Vì sao model 7B INT4 vẫn có thể OOM trên GPU 8GB khi context dài?
2. FP16 và BF16 cùng 2 bytes, khác nhau ở điểm nào quan trọng?
3. Khi nào nên chọn INT8 thay vì INT4?
4. GGUF phù hợp nhất với runtime nào?
5. Vì sao benchmark phải ghi cả model revision, runtime version và hardware?
6. `/health` và `/ready` khác nhau thế nào?
7. FastAPI gateway thêm giá trị gì nếu Ollama/vLLM đã có API?
8. Quality regression của quantization nên đo bằng gì?
9. Batching giúp throughput nhưng có thể làm xấu metric nào?
10. Điều kiện tối thiểu để local model API được dùng trong production là gì?
