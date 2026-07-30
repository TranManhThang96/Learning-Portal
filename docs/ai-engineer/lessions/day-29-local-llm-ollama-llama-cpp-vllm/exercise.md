# Day 29 Exercise: Chạy Và Đánh Giá Local LLM

Thời lượng gợi ý: 60-120 phút.

Mục tiêu: chạy ít nhất một local model, gọi bằng OpenAI-compatible client, đo latency cơ bản, ghi decision note và trả lời có dùng production được không.

## Phần 1: Setup Runtime

Chọn một trong hai hướng.

### Option A: Ollama

```bash
ollama pull llama3.2
ollama run llama3.2
```

Kiểm tra API:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2",
  "messages": [
    {"role": "user", "content": "Trả lời một câu: local LLM là gì?"}
  ],
  "stream": false
}'
```

### Option B: vLLM

Chỉ chọn nếu có GPU và môi trường phù hợp.

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name local-chat
```

Kiểm tra OpenAI-compatible endpoint:

```bash
curl http://localhost:8000/v1/models
```

Nếu `/v1/models` chạy nhưng `/v1/chat/completions` lỗi về chat template, chọn instruct/chat model có template phù hợp hoặc cấu hình `--chat-template` theo docs vLLM; không tự ghép prompt role trong business code.

## Phần 2: Gọi Bằng OpenAI-compatible Client

Cài dependency:

```bash
pip install -U openai
```

Lệnh `-U` chỉ phù hợp lab tạm. Khi lưu bài hoặc đưa vào CI, ghi version đã chạy (`python -m pip freeze`) và pin dependency trong lockfile/requirements để benchmark có thể lặp lại.

Tạo file `local_llm_probe.py` trong workspace tạm hoặc thư mục thực hành của bạn:

```python
from __future__ import annotations

import os
import time

from openai import OpenAI

base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
api_key = os.getenv("LOCAL_LLM_API_KEY", "local")
model = os.getenv("LOCAL_LLM_MODEL", "llama3.2")

client = OpenAI(
    base_url=base_url,
    api_key=api_key,
    timeout=30.0,
    max_retries=2,
)

prompts = [
    "Tóm tắt local LLM trong 3 bullet.",
    "Trả lời JSON với keys: runtime, strengths, risks.",
    "Giải thích KV cache cho senior software engineer.",
]

for prompt in prompts:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    text = response.choices[0].message.content or ""
    print({"model": model, "latency_ms": round(latency_ms, 2), "chars": len(text)})
    print(text[:500])
```

Chạy:

```bash
LOCAL_LLM_BASE_URL=http://localhost:11434/v1 \
LOCAL_LLM_MODEL=llama3.2 \
python local_llm_probe.py
```

Với vLLM:

```bash
LOCAL_LLM_BASE_URL=http://localhost:8000/v1 \
LOCAL_LLM_MODEL=local-chat \
python local_llm_probe.py
```

## Phần 3: Benchmark Nhỏ

Chạy mỗi prompt ít nhất 5 lần và ghi lại:

| Prompt | p50 latency | p95 latency | Output có đúng không | Ghi chú |
|---|---:|---:|---|---|
| Short summary |  |  |  |  |
| JSON output |  |  |  |  |
| KV cache explanation |  |  |  |  |
| Long context |  |  |  |  |

Thêm một prompt dài:

```text
Bạn là AI engineer. Hãy đọc context sau và trả lời ngắn gọn...
```

Sau đó lặp lại cùng nội dung 30-50 lần để mô phỏng RAG context dài. So sánh latency với prompt ngắn.

## Phần 4: So Sánh Runtime Theo Context

Điền bảng sau:

| Context | Runtime chọn | Vì sao | Rủi ro |
|---|---|---|---|
| Dev laptop offline |  |  |  |
| Internal assistant 20 user |  |  |  |
| Batch summarize 100k docs/ngày |  |  |  |
| Edge device không internet |  |  |  |
| Chatbot public traffic cao |  |  |  |

Gợi ý:

- Dev laptop thường bắt đầu bằng Ollama hoặc LM Studio.
- Edge thường cân nhắc llama.cpp + GGUF.
- Throughput GPU cao thường cân nhắc vLLM hoặc TGI.
- Public traffic cần auth, rate limit, monitoring, fallback và security review.

## Phần 5: Production Readiness Checklist

- [ ] Đã ghi model id, revision/digest và quantization.
- [ ] Đã đọc license/model card.
- [ ] Đã đo prompt ngắn và prompt dài.
- [ ] Đã đo p50/p95, không chỉ một lần chạy.
- [ ] Đã ghi RAM/VRAM observed.
- [ ] Đã thử concurrency tối thiểu 2-4 request song song.
- [ ] Đã giới hạn `max_tokens`.
- [ ] Đã có timeout.
- [ ] Đã có retry có kiểm soát.
- [ ] Đã không log full prompt nhạy cảm.
- [ ] Đã có health/readiness check.
- [ ] Đã smoke test capability app thật sự dùng: model alias, system role, streaming/usage/JSON/tool calling nếu có.
- [ ] Đã có fallback plan.
- [ ] Đã có golden eval hoặc ít nhất sample set cho chất lượng.
- [ ] Đã trả lời được: production được không, điều kiện gì.

## Phần 6: Quiz

1. Local LLM có đảm bảo dữ liệu không leak không? Vì sao?
2. Vì sao cùng một model nhưng runtime khác nhau có latency khác nhau?
3. Quantization giảm VRAM bằng cách nào và rủi ro chính là gì?
4. Tại sao prompt dài ảnh hưởng prefill nhiều hơn decode?
5. KV cache tăng theo những yếu tố nào?
6. Khi nào Ollama đủ dùng, khi nào nên chuyển sang vLLM?
7. Khi nào llama.cpp là lựa chọn tốt hơn GPU serving?
8. Vì sao OpenAI-compatible API không đủ để production nếu thiếu gateway?
9. Những metric nào cần xem trước khi mở traffic thật?
10. Nếu p95 latency vượt SLO, bạn sẽ thử 5 hướng tối ưu nào?

## Phần 7: Bài Tập Thiết Kế

Thiết kế một local LLM service cho internal policy Q&A:

- 200 nhân viên.
- Tài liệu nội bộ không được gửi ra cloud.
- 80% request là hỏi đáp ngắn.
- 20% request có RAG context dài.
- SLO: p95 dưới 5 giây cho câu hỏi ngắn, dưới 12 giây cho câu hỏi dài.
- Cần audit log nhưng không được lưu PII thô.

Bạn cần nộp:

- Runtime chọn cho dev.
- Runtime chọn cho production.
- Model candidate.
- API contract.
- Logging fields.
- Benchmark plan.
- Fallback plan.
- Rủi ro còn lại.

## Phần 8: Decision Note

```markdown
# Day 29 Local LLM Decision Note

## Use case
- Task:
- Data sensitivity:
- Users/concurrency:
- Latency SLO:

## Runtime candidates
- Ollama:
- llama.cpp:
- vLLM:
- TGI:
- LM Studio:

## Model
- model_id:
- revision/digest:
- license:
- quantization:
- context window:

## Benchmark result
- short prompt p50/p95:
- long prompt p50/p95:
- concurrency:
- RAM/VRAM:
- quality notes:

## Production decision
- Dùng được trong production không:
- Điều kiện bắt buộc:
- Runtime chọn:
- Fallback:
- Rollback:
- Rủi ro còn lại:
```
