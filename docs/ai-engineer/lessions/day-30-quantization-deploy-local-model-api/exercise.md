# Day 30 Exercise: Local Model API Benchmark

## Mục Tiêu

Bạn sẽ tạo một FastAPI gateway cho local model, chạy benchmark latency/memory và viết quyết định production readiness.

Kết quả cần nộp:

- `app.py`: FastAPI gateway.
- `benchmark_local_api.py`: benchmark script.
- `results.md`: bảng kết quả latency, memory, quality note.
- `production_decision.md`: trả lời "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

## Phần 1: Chuẩn Bị Runtime

Chọn một trong các runtime:

### Option A: Ollama

```bash
ollama pull llama3.2
ollama serve
```

Gateway config:

```bash
export LOCAL_LLM_BASE_URL=http://localhost:11434/v1
export LOCAL_LLM_API_KEY=local
export LOCAL_LLM_MODEL=llama3.2
export LOCAL_LLM_RUNTIME=ollama
```

### Option B: llama.cpp server

Ví dụ concept:

```bash
./llama-server -m model.gguf --host 0.0.0.0 --port 8080 --ctx-size 4096
```

Gateway config:

```bash
export LOCAL_LLM_BASE_URL=http://localhost:8080/v1
export LOCAL_LLM_API_KEY=local
export LOCAL_LLM_MODEL=local-gguf
export LOCAL_LLM_RUNTIME=llama.cpp
```

### Option C: vLLM OpenAI server

Ví dụ concept:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model <model-id> \
  --host 0.0.0.0 \
  --port 8000
```

Gateway config:

```bash
export LOCAL_LLM_BASE_URL=http://localhost:8000/v1
export LOCAL_LLM_API_KEY=local
export LOCAL_LLM_MODEL=<model-id>
export LOCAL_LLM_RUNTIME=vllm
```

## Phần 2: Tạo FastAPI Gateway

Cài dependency:

```bash
pip install -U fastapi uvicorn httpx pydantic psutil
```

Tạo `app.py` dựa theo template trong `document.md`.

Yêu cầu bắt buộc:

- `POST /chat` nhận `message`, `system`, `temperature`, `max_tokens`.
- Response có `answer`, `model`, `runtime`, `latency_ms`, `memory_rss_mb`, `trace_id`.
- `GET /health` trả process health.
- `GET /ready` kiểm tra runtime/model readiness.
- Có timeout.
- Có concurrency limit.
- Có max input length và max output tokens.
- Có structured log, không log raw prompt.

Chạy:

```bash
uvicorn app:app --host 0.0.0.0 --port 9000
```

Smoke test:

```bash
curl http://localhost:9000/health
curl http://localhost:9000/ready
curl -X POST http://localhost:9000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Giải thích INT4 trong 3 bullet.","max_tokens":200}'
```

## Phần 3: Benchmark Latency

Tạo `benchmark_local_api.py` theo template trong `document.md`.

Chạy ba cấu hình:

```bash
python benchmark_local_api.py --concurrency 1 --repeat 5 --max-tokens 200
python benchmark_local_api.py --concurrency 4 --repeat 5 --max-tokens 300
python benchmark_local_api.py --concurrency 8 --repeat 5 --max-tokens 300
```

Nếu máy yếu, giảm concurrency xuống `1`, `2`, `4`.

Ghi vào `results.md`:

| Config | p50 ms | p95 ms | p99 ms | req/s | error rate | RAM/VRAM peak | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| concurrency=1 | | | | | | | |
| concurrency=4 | | | | | | | |
| concurrency=8 | | | | | | | |

## Phần 4: Benchmark Memory

Trước benchmark:

```bash
ollama ps
nvidia-smi
```

Trong benchmark:

```bash
nvidia-smi --query-gpu=timestamp,name,memory.used,memory.total,utilization.gpu --format=csv -l 1
```

Nếu không có GPU:

```bash
ps -o pid,rss,comm -p <PID>
top -p <PID>
```

Ghi:

- RAM trước warmup.
- RAM sau warmup.
- RAM/VRAM peak khi concurrency cao nhất.
- Có OOM hoặc timeout không.

## Phần 5: Quality Regression Mini Eval

Tạo 10 prompt thật cho use case của bạn:

1. 3 prompt hỏi đáp tiếng Việt.
2. 2 prompt yêu cầu JSON.
3. 2 prompt dài gần context thực tế.
4. 1 prompt domain-specific.
5. 1 prompt dễ hallucinate.
6. 1 prompt yêu cầu từ chối nếu thiếu dữ kiện.

Nếu có hai model/format, ví dụ FP16 vs INT4 hoặc Q4 vs Q5, chạy cùng 10 prompt và chấm:

| Prompt | Baseline pass/fail | Quantized pass/fail | Lỗi nếu fail |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

Quality note cần trả lời:

- JSON có parse được không?
- Câu trả lời tiếng Việt có tự nhiên không?
- Có hallucination nghiêm trọng không?
- Có sai instruction hoặc vượt policy không?
- Regression có chấp nhận được với use case không?

## Phần 6: Production Decision

Tạo `production_decision.md` theo mẫu:

```markdown
# Production Decision

## Context

- Use case:
- Traffic target:
- SLA:
- Hardware:
- Runtime:
- Model:
- Quantization:

## Benchmark Summary

- p50:
- p95:
- p99:
- req/s:
- RAM/VRAM peak:
- error rate:

## Quality Summary

- Golden set size:
- Pass rate baseline:
- Pass rate quantized:
- Regression:

## Decision

Dùng được trong production không?

## Điều kiện

- Điều kiện 1:
- Điều kiện 2:
- Điều kiện 3:

## Rollback/Fallback

- Khi timeout:
- Khi OOM:
- Khi quality regression:
```

Gợi ý quyết định:

- Nếu p95 không đạt SLA: chưa production, cần model nhỏ hơn, quantization khác, runtime khác hoặc GPU tốt hơn.
- Nếu memory sát giới hạn: chưa production cho traffic thật, cần giảm context/concurrency hoặc tăng hardware.
- Nếu quality regression cao: chưa production, cần model tốt hơn, INT8/Q5/Q6 thay vì INT4, hoặc fallback.
- Nếu chỉ thiếu observability/auth/rate limit: có thể canary nội bộ, chưa public production.

## Checklist Tự Chấm

- [ ] Gateway chạy được và có `/health`.
- [ ] Gateway có `/ready` phản ánh runtime thật.
- [ ] Request/response schema rõ ràng.
- [ ] Timeout hoạt động.
- [ ] Concurrency limit hoạt động.
- [ ] Benchmark có p50/p95/p99.
- [ ] Có ghi RAM/VRAM peak.
- [ ] Có quality mini eval.
- [ ] Có quyết định production rõ ràng.
- [ ] Có rollback/fallback plan.

