# Day 17 Exercise: LLM Fundamentals

## Mục tiêu thực hành

Hoàn thành bài này để bạn có dữ liệu thực tế về decoding params, token budget, cost, latency, output stability và model choice. Kết quả cuối bài là một model decision note ngắn cho một LLM feature production-style.

## Yêu cầu môi trường

Chọn một trong hai hướng:

- Local: cài Ollama và pull một model nhỏ, ví dụ `llama3.1:8b`, `qwen2.5:7b` hoặc model tương đương máy bạn chạy được.
- Hosted: dùng provider có API tương thích OpenAI-style. Không commit API key vào repo.

Python packages:

```bash
pip install -U requests pydantic
```

## Exercise 1: Chạy Cùng Prompt Với Nhiều Decoding Params

Tạo file tạm trong máy bạn, ví dụ `day17_decode_experiment.py`:

```python
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError


BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "180"))

PROMPT = """Bạn là AI Engineer đang review một feature LLM.
Hãy trả lời bằng tiếng Việt có dấu.

Task:
Liệt kê 5 rủi ro production khi dùng LLM cho customer support.
Mỗi rủi ro gồm:
- risk: tên rủi ro ngắn
- impact: tác động
- mitigation: cách giảm rủi ro

Chỉ trả về JSON object hợp lệ theo schema:
{
  "risks": [
    {"risk": "...", "impact": "...", "mitigation": "..."}
  ]
}
"""


class Risk(BaseModel):
    risk: str = Field(min_length=3)
    impact: str = Field(min_length=10)
    mitigation: str = Field(min_length=10)


class RiskReport(BaseModel):
    risks: list[Risk] = Field(min_length=5, max_length=5)


@dataclass(frozen=True)
class RunConfig:
    name: str
    temperature: float
    top_p: float
    max_tokens: int


def call_ollama(config: RunConfig) -> dict[str, Any]:
    started = time.perf_counter()
    response = requests.post(
        f"{BASE_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": PROMPT,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_predict": config.max_tokens,
            },
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("response", "")
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    validation_error = None
    parsed = None
    try:
        parsed = RiskReport.model_validate_json(text)
    except ValidationError as exc:
        validation_error = str(exc).splitlines()[0]

    return {
        "config": config.__dict__,
        "latency_ms": latency_ms,
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "finish_reason": data.get("done_reason"),
        "valid_json": parsed is not None,
        "validation_error": validation_error,
        "text_preview": text[:600],
    }


def main() -> None:
    configs = [
        RunConfig("deterministic", temperature=0.0, top_p=1.0, max_tokens=600),
        RunConfig("low_creativity", temperature=0.2, top_p=0.9, max_tokens=600),
        RunConfig("balanced", temperature=0.5, top_p=0.95, max_tokens=600),
        RunConfig("creative", temperature=0.9, top_p=0.95, max_tokens=600),
    ]

    results = []
    for config in configs:
        for attempt in range(1, 4):
            result = call_ollama(config)
            result["attempt"] = attempt
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, indent=2))

    valid_count = sum(1 for item in results if item["valid_json"])
    print(
        json.dumps(
            {
                "total_runs": len(results),
                "valid_json_runs": valid_count,
                "json_validity_rate": round(valid_count / len(results), 4),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
```

Ghi lại bảng:

| Config | Attempt | Latency ms | Prompt tokens | Output tokens | Valid JSON | Nhận xét stability |
|---|---:|---:|---:|---:|---|---|
| deterministic | 1 |  |  |  |  |  |
| deterministic | 2 |  |  |  |  |  |
| deterministic | 3 |  |  |  |  |  |
| creative | 1 |  |  |  |  |  |

Câu hỏi:

- Config nào ổn định nhất?
- Config nào dễ làm hỏng JSON nhất?
- Output token có ảnh hưởng latency thế nào?
- Với extraction/schema, bạn chọn config nào?

## Exercise 2: Token Budget Cho Use Case Customer Support

Giả sử bạn build support assistant:

- System prompt: 700 tokens.
- Developer instruction: 400 tokens.
- Chat history summary: 1,200 tokens.
- User message: 300 tokens.
- Retrieved docs: 6 chunks, mỗi chunk 900 tokens.
- Tool result: 1,000 tokens.
- Model context window: 16,000 tokens.
- Bạn muốn reserve output 1,500 tokens và safety margin 1,000 tokens.

Tính:

```text
total = system + developer + history + user + docs + tool + output + margin
```

Trả lời:

- Có vượt context window không?
- Nếu cần giảm 3,000 tokens, bạn giảm ở đâu trước?
- Vì sao không nên cắt system prompt hoặc user message đầu tiên?
- Khi nào nên dùng reranking?

Gợi ý production answer:

- Giữ system/developer instruction ngắn nhưng không cắt mù.
- Giảm số retrieved chunks sau rerank.
- Summarize chat history.
- Summarize hoặc paginate tool result.
- Reserve output token cố định theo response contract.

## Exercise 3: Cost Estimate

Giả sử provider tính:

- Input: `0.50 USD / 1M tokens`.
- Output: `2.00 USD / 1M tokens`.

Traffic:

- 30,000 requests/day.
- Average input: 1,800 tokens.
- Average output: 350 tokens.
- Retry rate: 4%.

Tính:

```text
daily_input_tokens = requests * avg_input * (1 + retry_rate)
daily_output_tokens = requests * avg_output * (1 + retry_rate)
daily_cost = input_tokens / 1_000_000 * input_price
           + output_tokens / 1_000_000 * output_price
monthly_cost = daily_cost * 30
```

Sau đó trả lời:

- Nếu output tăng từ 350 lên 900 tokens thì monthly cost đổi thế nào?
- Cách giảm cost nào ít ảnh hưởng quality nhất?
- Bạn đặt quota hoặc budget alert ở mức nào?

## Exercise 4: Hosted Vs Local Decision

Điền bảng cho một use case của bạn.

| Tiêu chí | Hosted strong model | Hosted small model | Local/open-weight model |
|---|---|---|---|
| Quality expected |  |  |  |
| p95 latency expected |  |  |  |
| Cost/request |  |  |  |
| Data sensitivity |  |  |  |
| Ops complexity |  |  |  |
| Security/compliance risk |  |  |  |
| Upgrade/rollback |  |  |  |
| Decision |  |  |  |

Kết luận cần có dạng:

```markdown
For production v1, I choose ...

Reason:
- ...

Required conditions:
- Golden set:
- Logging:
- Data policy:
- Fallback:
- Rollback:
```

## Exercise 5: Production Readiness Review

Review đoạn pseudo-design sau:

```text
Frontend gửi toàn bộ chat history và file content lên API.
API nối string vào prompt.
API gọi model mạnh nhất với temperature 0.8 và max_tokens 4000.
Response raw text được hiển thị cho user và lưu nguyên văn vào database.
Không log token usage.
Không validate output.
Không có eval set.
```

Tìm ít nhất 10 vấn đề, phân loại theo:

- Cost.
- Latency.
- Security/privacy.
- Reliability.
- Quality.
- Maintainability.

Đề xuất design sửa lại theo flow:

```text
validate request
-> permission filter
-> summarize/truncate history
-> retrieve/rerank documents
-> build versioned prompt
-> count token budget
-> call model with task-specific decoding
-> validate output
-> log safe metadata
-> fallback or return stable response
```

## Deliverable Cuối Bài

Tạo một note ngắn:

```markdown
# Day 17 Model Choice Notes

## Use case

## Token budget

## Decoding config

## Hosted vs local decision

## Cost estimate

## Latency expectation

## Security policy

## Production readiness

LLM dùng được trong production cho use case này không?
Nếu có, điều kiện bắt buộc là gì?
Nếu chưa, blocker là gì?
```

Checklist hoàn thành:

- [ ] Chạy hoặc mô phỏng decoding experiment.
- [ ] Có bảng latency/token/output validity.
- [ ] Tính được token budget.
- [ ] Tính được cost estimate.
- [ ] Có hosted vs local decision.
- [ ] Có câu trả lời production readiness rõ ràng.
