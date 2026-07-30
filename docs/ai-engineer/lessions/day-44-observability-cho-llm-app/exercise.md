# Exercise: Instrument RAG Pipeline

Mục tiêu bài tập: biến một RAG API đang chạy được thành một service có observability đủ để debug latency, quality, token usage, cost/request và feedback.

Bạn có thể dùng mini-project Day 40 hoặc RAG app riêng. Không cần đổi model/provider nếu app hiện tại đã chạy được.

## 1. Yêu Cầu Đầu Ra

Sau lab, repository của bạn cần có:

- `trace_id` được sinh ở đầu request và trả về trong response.
- Structured JSON logs cho từng stage.
- Metrics endpoint `/metrics` theo Prometheus format.
- Trace record có retrieval, rerank, context, generation, citation validation và feedback.
- Token usage, cost/request và TTFT nếu app dùng streaming.
- Feedback endpoint `POST /feedback`.
- Report cho ít nhất 30 câu hỏi golden set.
- Production readiness answer: dùng được trong production không, nếu có thì cần điều kiện gì.

## 2. Bước 1: Thêm Trace ID

Trong endpoint `/query`, tạo `trace_id` ngay khi nhận request:

```python
import uuid


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex}"
```

Response nên có:

```json
{
  "trace_id": "tr_abc123",
  "answer": "...",
  "citations": [],
  "usage": {
    "input": 1200,
    "output": 180
  },
  "estimated_cost_usd": "0.000768"
}
```

Checklist:

- [ ] `trace_id` xuất hiện trong mọi log event.
- [ ] `trace_id` trả về client.
- [ ] Feedback dùng lại `trace_id`.
- [ ] Error response cũng trả `trace_id`.

## 3. Bước 2: Structured JSON Logs

Thêm helper:

```python
import json
import logging
import time
from typing import Any

logger = logging.getLogger("rag")


def log_event(event: str, **fields: Any) -> None:
    logger.info(
        json.dumps(
            {
                "event": event,
                "timestamp_ms": int(time.time() * 1000),
                **fields,
            },
            ensure_ascii=False,
            default=str,
        )
    )
```

Log tối thiểu:

```python
log_event("query_received", trace_id=trace_id, query_hash=query_hash, top_k=top_k)
log_event("retrieval_completed", trace_id=trace_id, candidate_count=len(chunks), latency_ms=...)
log_event("rerank_completed", trace_id=trace_id, selected_count=len(selected), latency_ms=...)
log_event("context_built", trace_id=trace_id, context_tokens=context_tokens, truncated=truncated)
log_event("generation_completed", trace_id=trace_id, input_tokens=..., output_tokens=..., cost=...)
log_event("citation_validated", trace_id=trace_id, valid=True, failure_reason=None)
```

Không log raw query/context nếu chưa có redaction.

## 4. Bước 3: Đo Latency Theo Stage

Thêm context manager:

```python
from contextlib import contextmanager
import time


@contextmanager
def timed(stage: str, latency_ms: dict[str, int]):
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms[stage] = round((time.perf_counter() - start) * 1000)
```

Dùng trong pipeline:

```python
latency_ms = {}
request_started = time.perf_counter()

with timed("retrieval", latency_ms):
    chunks = retrieve(query)

with timed("rerank", latency_ms):
    selected = rerank(query, chunks)

with timed("context_build", latency_ms):
    context = build_context(selected)

with timed("generation", latency_ms):
    answer = generate(context, query)
```

Report cuối request:

```python
log_event(
    "query_completed",
    trace_id=trace_id,
    total_latency_ms=round((time.perf_counter() - request_started) * 1000),
    stage_latency_ms=latency_ms,
)
```

Nếu có code async, context manager vẫn dùng được nếu block bên trong `await` không yêu cầu `asynccontextmanager`.

## 5. Bước 4: Prometheus Metrics

Cài dependency:

```bash
pip install prometheus-client
```

Thêm metrics:

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

REQUESTS = Counter("rag_request_total", "Total RAG requests", ["route", "status"])
STAGE_LATENCY = Histogram("rag_stage_latency_seconds", "Latency by stage", ["stage"])
REQUEST_LATENCY = Histogram("rag_request_latency_seconds", "End-to-end latency", ["route"])
TOKENS = Counter("llm_token_total", "LLM token usage", ["model", "type"])
COST = Counter("llm_cost_usd_total", "LLM cost in USD", ["model"])
IN_FLIGHT = Gauge("rag_requests_in_flight", "Requests in flight", ["route"])


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

Ghi metrics:

```python
REQUESTS.labels(route="/query", status="success").inc()
STAGE_LATENCY.labels(stage="retrieval").observe(latency_ms["retrieval"] / 1000)
REQUEST_LATENCY.labels(route="/query").observe(total_latency_ms / 1000)
TOKENS.labels(model=model, type="input").inc(input_tokens)
TOKENS.labels(model=model, type="output").inc(output_tokens)
COST.labels(model=model).inc(float(cost_usd))
```

Kiểm tra:

```bash
curl http://localhost:8000/metrics | grep rag_
```

## 6. Bước 5: Token Usage Và Cost/Request

Tạo pricing table versioned:

```python
from decimal import Decimal

MODEL_PRICE_USD_PER_1M = {
    "gpt-4.1-mini": {"input": Decimal("0.40"), "output": Decimal("1.60")},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    price = MODEL_PRICE_USD_PER_1M[model]
    return (
        Decimal(input_tokens) * price["input"] / Decimal(1_000_000)
        + Decimal(output_tokens) * price["output"] / Decimal(1_000_000)
    ).quantize(Decimal("0.000001"))
```

Yêu cầu:

- [ ] Lưu `input_tokens`.
- [ ] Lưu `output_tokens`.
- [ ] Lưu `estimated_cost_usd`.
- [ ] Lưu `pricing_table_version` nếu pricing có thể đổi.
- [ ] Nếu provider không trả usage, ghi rõ `usage_source="estimated"`.

Các con số trong snippet là fixture để học cách tính, không phải cam kết giá hiện hành. Production phải đọc pricing từ config có `pricing_table_version` và `effective_at`, rồi đối soát với billing provider.

## 7. Bước 6: Đo TTFT

Nếu endpoint stream token, đo time to first token:

```python
import time


async def stream_answer(prompt: str, model: str, trace_id: str):
    started = time.perf_counter()
    first_token_seen = False

    async for token in llm_client.stream(prompt=prompt, model=model):
        if not first_token_seen:
            ttft_ms = round((time.perf_counter() - started) * 1000)
            log_event("first_token_received", trace_id=trace_id, model=model, ttft_ms=ttft_ms)
            first_token_seen = True
        yield token.text
```

Nếu app không streaming, ghi `ttft_ms=null` và đo `generation.latency_ms`. Không bịa TTFT từ total latency.

## 8. Bước 7: Trace Record

Tạo một object trace và lưu cuối request:

```python
trace_record = {
    "trace_id": trace_id,
    "tenant_id": tenant_id,
    "user_id_hash": user_id_hash,
    "query": {
        "raw_hash": query_hash,
        "raw_redacted": query_redacted,
        "length_chars": len(query),
    },
    "retrieval": {
        "strategy": "hybrid",
        "index_version": index_version,
        "top_k": top_k,
        "latency_ms": latency_ms["retrieval"],
        "candidates": candidate_summaries,
    },
    "rerank": {
        "enabled": True,
        "reranker_model": reranker_model,
        "latency_ms": latency_ms["rerank"],
        "selected_count": len(selected),
    },
    "context": {
        "chunk_ids": [chunk["chunk_id"] for chunk in selected],
        "context_tokens": context_tokens,
        "truncated": truncated,
    },
    "generation": {
        "model": model,
        "prompt_version": prompt_version,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "ttft_ms": ttft_ms,
        "latency_ms": latency_ms["generation"],
        "estimated_cost_usd": str(cost_usd),
        "pricing_table_version": pricing_table_version,
    },
    "validation": {
        "citation_valid": citation_valid,
        "citation_failure_reason": citation_failure_reason,
    },
    "result": {
        "status": "success",
        "total_latency_ms": total_latency_ms,
    },
}
```

Lưu vào Postgres, SQLite, JSONL hoặc Langfuse/LangSmith tùy stack. Với capstone, JSONL hoặc SQLite là đủ nếu report đọc được.

## 9. Bước 8: Feedback Endpoint

Contract:

```text
POST /feedback
{
  "trace_id": "tr_abc123",
  "rating": "down",
  "reason": "wrong_source",
  "comment": "Answer cited policy 2024, but the question asked 2026"
}
```

Pydantic model:

```python
from typing import Literal
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: Literal["up", "down"]
    reason: Literal[
        "helpful",
        "wrong_answer",
        "wrong_source",
        "missing_context",
        "too_slow",
        "unsafe",
        "other",
    ]
    comment: str | None = Field(default=None, max_length=2000)
```

Checklist:

- [ ] Validate `trace_id` tồn tại.
- [ ] Redact/hash comment.
- [ ] Lưu `rating`, `reason`, `triage_status`.
- [ ] Log event `feedback_received`.
- [ ] Có report feedback theo reason.

## 10. Bước 9: Privacy, Redaction, Sampling

Implement tối thiểu:

```python
import hashlib
import os
import re

SALT = os.environ["OBSERVABILITY_HASH_SALT"]


def hash_value(value: str) -> str:
    return "sha256:" + hashlib.sha256(f"{SALT}:{value}".encode()).hexdigest()


def redact_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)
    text = re.sub(r"\b(?:\+?84|0)(?:\d[\s.-]?){8,10}\b", "[PHONE]", text)
    text = re.sub(r"\b\d{9,12}\b", "[ID_NUMBER]", text)
    return text
```

Sampling policy cần nộp:

| Request type | Metadata trace | Raw content |
|---|---:|---:|
| Success | 100% | 0-5% |
| Error/timeout | 100% | 100% redacted hoặc theo allowlist |
| Thumbs down | 100% | 100% redacted hoặc theo allowlist |
| Sensitive tenant | 100% | 0% |

## 11. Bước 10: Chạy Golden Set

Chuẩn bị `golden_questions.jsonl` với ít nhất 30 câu:

```jsonl
{"id":"q001","query":"Chính sách nghỉ phép năm 2026 là gì?","expected_source":"policy_2026"}
{"id":"q002","query":"Nhân viên thử việc có được nghỉ phép không?","expected_source":"policy_hr"}
```

Runner đơn giản:

```python
import json
import requests

with open("golden_questions.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        response = requests.post(
            "http://localhost:8000/query",
            json={"query": item["query"], "top_k": 20},
            timeout=30,
        )
        print(json.dumps({"id": item["id"], **response.json()}, ensure_ascii=False))
```

Chạy:

```bash
python run_golden_set.py > traces/golden_run_day44.jsonl
```

Nếu bạn không tạo file runner riêng trong repo, có thể chạy bằng notebook hoặc script tạm, nhưng report phải có số liệu.

## 12. Bước 11: Report Bắt Buộc

Tạo bảng:

| Metric | Giá trị |
|---|---:|
| Total queries | 30 |
| Success rate | |
| p50 total latency | |
| p95 total latency | |
| p95 retrieval latency | |
| p95 rerank latency | |
| p95 generation latency | |
| p95 TTFT | |
| Average input tokens | |
| Average output tokens | |
| Average cost/request | |
| Empty retrieval rate | |
| Citation failure rate | |
| Thumbs down rate | |

Top slowest:

| Rank | Trace ID | Query ID | Total latency | Bottleneck stage |
|---:|---|---|---:|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

Top highest-cost:

| Rank | Trace ID | Query ID | Input tokens | Output tokens | Cost |
|---:|---|---|---:|---:|---:|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

Error classification:

| Error class | Count | Ví dụ trace | Fix đề xuất |
|---|---:|---|---|
| Retrieval | | | |
| Rerank | | | |
| Context builder | | | |
| Generation | | | |
| Citation | | | |
| Timeout | | | |
| Guardrail | | | |

## 13. Bước 12: Viết Production Readiness Answer

Trả lời theo format sau:

```text
Dùng được trong production không?

Có, nhưng chỉ ở mức internal beta nếu thỏa:
- Observability: mọi request có trace_id, stage latency, token usage, cost/request và error type.
- Privacy: raw query/context/output được redact trước khi log; raw trace chỉ lưu theo sampling policy.
- Cost control: dashboard có cost/request, cost/day, token/request và alert cost spike.
- Alert/runbook: p95 latency, error rate, timeout rate, citation failure và empty retrieval đều có owner.
- Eval/feedback loop: feedback gắn trace_id và golden set chạy trước khi đổi prompt/model/index.
- Performance overhead: instrumentation overhead dưới 5% p95 latency so với baseline.

Chưa được public production nếu còn thiếu:
- Chưa có access control cho trace store, chưa có retention policy, chưa có redaction test tự động,
  hoặc chưa có load test chứng minh overhead của observability.
```

Ví dụ câu trả lời tốt:

```text
Có thể dùng cho internal beta. Hệ thống đã có trace_id, JSON logs, Prometheus metrics,
token/cost accounting, feedback endpoint và dashboard p95 latency/cost/citation failure.
Để lên public production cần thêm redaction test tự động, retention policy, access control
cho trace store, alert có owner, load test chứng minh overhead dưới 5%, và golden set chạy
trước mỗi lần đổi prompt/model/index.
```

## 14. Rubric Chấm Điểm

| Hạng mục | Điểm |
|---|---:|
| Trace schema đủ retrieval/rerank/context/generation/validation | 20 |
| Logs JSON có event taxonomy và `trace_id` | 15 |
| Metrics có latency, error, token, cost, TTFT | 15 |
| Feedback loop gắn trace và triage reason | 10 |
| Privacy/redaction/sampling policy | 15 |
| Report golden set với slowest/highest-cost/error classification | 15 |
| Production readiness answer rõ điều kiện | 10 |

Tổng: 100 điểm.

## 15. Lỗi Thường Gặp

- Chỉ log final answer, không log metadata của retrieved chunks. Cách đúng là log `chunk_id`, `document_id`, score, version, hash/length và redaction status; không log raw chunk content nếu chưa có policy rõ.
- Không có prompt/model/index version trong trace.
- Lưu raw query/context/output mà không redact.
- Dùng `trace_id` làm Prometheus label.
- Chỉ đo total latency, không đo stage latency.
- Không đo token usage và cost/request.
- Feedback không join được với trace.
- Không phân biệt empty retrieval, invalid citation, timeout và provider error.
- Alert quá nhiều nhưng không có owner hoặc runbook.
- Báo "production ready" chỉ vì endpoint chạy được.

## 16. Deliverable Cuối Cùng

Nộp các phần sau:

1. Link hoặc screenshot `/metrics`.
2. 3-5 log events mẫu đã redact.
3. 1 trace JSON hoàn chỉnh nhưng đã redact hoặc chỉ chứa hash/metadata cho nội dung nhạy cảm.
4. Report 30 golden queries.
5. Top 5 slowest queries.
6. Top 5 highest-cost queries.
7. Bảng phân loại lỗi.
8. Sampling/redaction policy.
9. 3 alert production đầu tiên.
10. Production readiness answer.
