# Day 44: Observability Cho LLM App

## 1. Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Thiết kế observability cho LLM/RAG app theo 3 lớp: logs, metrics và traces.
- Đo được latency tổng, latency theo stage, throughput, error rate, token usage, cost/request và TTFT.
- Tạo trace schema đủ sâu cho RAG: query, retrieved chunks, reranked chunks, context, prompt, generation, citation validation và feedback.
- Gắn user feedback với `trace_id`, prompt version, model version, index version và retrieved chunks để debug regression.
- So sánh được Langfuse, LangSmith, OpenTelemetry, Prometheus/Grafana và ELK/OpenSearch.
- Thiết kế privacy, redaction, sampling, retention và access control trước khi log prompt/context/output.
- Trả lời được: dùng được trong production không, nếu có thì cần điều kiện gì.

## 2. Tư Duy Chính

LLM app không chỉ fail theo kiểu HTTP 500. Nó có thể:

- Trả lời chậm nhưng vẫn `200 OK`.
- Dùng quá nhiều token vì prompt/context phình to.
- Retrieve nhầm document nhưng model vẫn viết câu trả lời nghe hợp lý.
- Reranker đẩy chunk đúng xuống dưới.
- Citation trỏ sai source.
- Output đúng về ngữ pháp nhưng sai policy.
- Cost tăng vì model router chọn model đắt.
- User bấm thumbs down nhưng team không biết prompt, model, index và chunks nào đã tạo ra answer đó.

Vì vậy observability cho LLM app phải trả lời được 6 câu hỏi:

1. Request nào bị lỗi hoặc chậm?
2. Lỗi nằm ở stage nào: retrieval, rerank, context builder, model call, citation validation hay feedback?
3. Version nào liên quan: prompt, model, embedding model, reranker, index, guardrail?
4. Token usage và cost/request là bao nhiêu?
5. Output có đạt quality signal không: citation valid, no-answer đúng, feedback tốt?
6. Có log dữ liệu nhạy cảm quá mức không?

## 3. Map Sang Senior Software Engineering

| LLM/RAG concept | SE concept tương đương | Observability cần có |
|---|---|---|
| Prompt | Config/versioned template | Version, input size, rendered length, owner |
| Model provider | Downstream service | Latency, timeout, retry, error code, rate limit |
| Embedding/index | Search infrastructure | Index version, top-k, score distribution, empty retrieval |
| Reranker | Ranking service | Candidate count, latency, top score, score gap |
| Context builder | Request payload builder | Context token, truncation, selected chunk ids |
| Citation validation | Contract validation | Valid/invalid count, failure reason |
| User feedback | Product quality signal | Rating, reason, trace linkage, triage status |
| Trace store | Debug database | Retention, access control, sampling, redaction |

Điểm khác biệt lớn so với API truyền thống: `success` không chỉ là status code. Một LLM request thành công về mặt HTTP vẫn có thể thất bại về mặt quality.

## 4. Logs, Metrics, Traces

### Logs

Logs là event chi tiết, thường ở dạng structured JSON. Dùng logs để debug một request cụ thể hoặc search theo event.

Ví dụ event:

```json
{
  "timestamp": "2026-05-10T10:15:21.120Z",
  "level": "INFO",
  "event": "retrieval_completed",
  "trace_id": "tr_01hxx",
  "tenant_id": "acme",
  "route": "/query",
  "top_k": 20,
  "candidate_count": 18,
  "empty_retrieval": false,
  "latency_ms": 42,
  "index_version": "policy-index-2026-05-01"
}
```

Log tốt có key ổn định, có `trace_id`, không chứa secret và không dùng message text tự do làm nguồn dữ liệu chính.

### Metrics

Metrics là số liệu aggregate để dashboard và alert.

Ví dụ:

- `rag_request_total{route,status}`.
- `rag_stage_latency_seconds{stage}`.
- `rag_token_total{model,type}` với `type=input|output`.
- `rag_cost_usd_total{model,tenant_tier}`.
- `rag_empty_retrieval_total{index_version}`.
- `rag_citation_invalid_total{reason}`.
- `llm_ttft_seconds{model}`.

Không đưa `trace_id`, `user_id`, `query`, `chunk_id` vào label Prometheus. Các field đó có cardinality cao, làm metric store phình nhanh và dashboard chậm.

### Traces

Trace mô tả đường đi của một request qua nhiều stage. Với RAG, trace quan trọng hơn log text rời rạc vì nó giữ quan hệ cha con:

```text
rag.query
  query.rewrite
  retrieval.hybrid_search
  rerank.cross_encoder
  context.build
  llm.generate
  citation.validate
  feedback.attach
```

Trace giúp trả lời: tổng latency 3.2s là do model call 2.6s, reranker 400ms hay vector DB 180ms.

## 5. Golden Signals Cho LLM App

| Signal | Metric cụ thể | Vì sao quan trọng |
|---|---|---|
| Latency | total latency, stage latency, p50/p95/p99, TTFT | User cảm nhận tốc độ qua first token và tổng thời gian |
| Traffic | requests/minute, tokens/minute, streaming sessions | Dự báo capacity và rate limit |
| Errors | timeout, provider error, schema violation, empty retrieval, invalid citation | Tách lỗi infrastructure khỏi lỗi quality |
| Saturation | queue length, CPU/RAM/GPU, connection pool, provider rate limit | Biết hệ thống đang nghẽn ở đâu |
| Cost | cost/request, cost/day, cost by model/tenant/feature | Kiểm soát ngân sách và pricing |
| Quality | feedback rating, no-answer accuracy, citation failure rate, retrieval hit rate | LLM app cần đo đúng/sai, không chỉ uptime |

TTFT là `time to first token`: thời gian từ lúc nhận request đến token đầu tiên của model stream. Với UI streaming, TTFT thường quyết định cảm giác "app có phản hồi" hơn total latency.

## 6. Trace Schema Cho RAG

Trace schema nên đủ chi tiết để debug nhưng không bắt buộc log raw content ở mọi môi trường.

```json
{
  "trace_id": "tr_01hxx4e6kg9k7r8y0x",
  "request_id": "req_9d2c",
  "session_id_hash": "sha256:7c0f...",
  "tenant_id": "acme",
  "user_id_hash": "sha256:aa31...",
  "route": "/query",
  "environment": "prod",
  "query": {
    "raw_redacted": "Chính sách nghỉ phép năm 2026 là gì?",
    "raw_hash": "sha256:2f67...",
    "language": "vi",
    "length_chars": 38
  },
  "rewrite": {
    "enabled": true,
    "rewritten_query_redacted": "Chính sách nghỉ phép nhân viên năm 2026",
    "latency_ms": 35
  },
  "retrieval": {
    "strategy": "hybrid_dense_bm25_rrf",
    "index_version": "policy-index-2026-05-01",
    "embedding_model": "text-embedding-3-small",
    "top_k": 30,
    "latency_ms": 64,
    "empty": false,
    "candidates": [
      {
        "rank": 1,
        "chunk_id": "policy_2026::chunk_018",
        "document_id": "policy_2026",
        "source_uri_hash": "sha256:c91e...",
        "score_dense": 0.82,
        "score_sparse": 12.7,
        "score_rrf": 0.041,
        "acl_matched": true
      }
    ]
  },
  "rerank": {
    "enabled": true,
    "reranker_model": "bge-reranker-v2-m3",
    "candidate_count": 30,
    "selected_count": 8,
    "latency_ms": 210,
    "top_score": 0.91,
    "score_gap_top2": 0.08
  },
  "context": {
    "chunk_ids": ["policy_2026::chunk_018", "policy_2026::chunk_021"],
    "context_tokens": 1840,
    "truncated": false,
    "max_context_tokens": 6000
  },
  "generation": {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "prompt_version": "rag-answer-v7",
    "temperature": 0.1,
    "input_tokens": 2300,
    "output_tokens": 420,
    "ttft_ms": 780,
    "latency_ms": 2800,
    "finish_reason": "stop",
    "estimated_cost_usd": 0.001592
  },
  "validation": {
    "schema_valid": true,
    "citation_valid": true,
    "citation_failure_reason": null,
    "guardrail_action": "allow"
  },
  "feedback": {
    "rating": null,
    "reason": null,
    "comment_redacted": null
  },
  "result": {
    "status": "success",
    "error_type": null,
    "total_latency_ms": 3140
  }
}
```

Trong production nghiêm ngặt, `raw_redacted` có thể tắt theo tenant. Khi đó vẫn giữ `raw_hash`, length, language, version và metadata để debug aggregate.

## 7. Event Taxonomy

Nên định nghĩa event cố định từ đầu:

| Event | Khi ghi | Field quan trọng |
|---|---|---|
| `query_received` | Nhận request | trace_id, tenant, route, query_hash |
| `query_rewritten` | Rewrite xong | latency, rewrite_enabled, rewritten_hash |
| `retrieval_completed` | Search xong | index_version, top_k, count, empty, latency |
| `rerank_completed` | Rerank xong | reranker_model, candidate_count, selected_count, latency |
| `context_built` | Build context xong | chunk_count, context_tokens, truncated |
| `generation_started` | Bắt đầu gọi model | provider, model, prompt_version |
| `first_token_received` | Có token đầu tiên | ttft_ms, model |
| `generation_completed` | Model trả xong | input_tokens, output_tokens, latency, cost |
| `citation_validated` | Validate citation | valid, failure_reason |
| `feedback_received` | User feedback | trace_id, rating, reason |
| `request_failed` | Request lỗi | error_type, stage, retryable |
| `guardrail_blocked` | Guardrail chặn | policy, action, stage |

Event taxonomy giúp team không phải đoán tên field khi viết dashboard hoặc query log.

## 8. Code Gần Production

Đoạn code dưới đây minh họa instrumentation ở mức service thật: có `trace_id`, redaction, structured JSON logs, OpenTelemetry spans, Prometheus metrics, token/cost accounting và feedback endpoint.

### 8.1 Dependencies

```bash
pip install fastapi uvicorn pydantic prometheus-client opentelemetry-api opentelemetry-sdk
```

Nếu deploy bằng Gunicorn nhiều worker, Prometheus client cần cấu hình multiprocess riêng. Với bài học này, ta giữ ví dụ ở mức một process để tập trung vào observability contract.

### 8.2 OpenTelemetry Startup

Trong service thật, cấu hình tracer provider ở startup. Local development có thể dùng console exporter; production thường thay bằng OTLP exporter hoặc exporter mà platform đang dùng.

```python
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_tracing() -> None:
    resource = Resource.create(
        {
            "service.name": "rag-api",
            "service.version": "1.0.0",
            "deployment.environment": "dev",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
```

Gọi `configure_tracing()` một lần khi app start. Không gọi lại trong từng request.

### 8.3 Shared Observability Module

```python
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from prometheus_client import Counter, Gauge, Histogram

LOGGER = logging.getLogger("rag.observability")
LOGGER.setLevel(logging.INFO)

SALT = os.environ.get("OBSERVABILITY_HASH_SALT", "dev-only-change-me")
RAW_CONTENT_LOGGING = os.environ.get("RAW_CONTENT_LOGGING", "false").lower() == "true"

tracer = trace.get_tracer("rag-api", "1.0.0")

REQUESTS = Counter(
    "rag_request_total",
    "Total RAG requests",
    ["route", "status"],
)
STAGE_LATENCY = Histogram(
    "rag_stage_latency_seconds",
    "Latency by RAG stage",
    ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
TTFT = Histogram(
    "llm_ttft_seconds",
    "Time to first token",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
TOKENS = Counter(
    "llm_token_total",
    "LLM token usage",
    ["model", "type"],
)
COST = Counter(
    "llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["model"],
)
IN_FLIGHT = Gauge(
    "rag_requests_in_flight",
    "RAG requests currently being processed",
    ["route"],
)
EMPTY_RETRIEVAL = Counter(
    "rag_empty_retrieval_total",
    "RAG requests with zero retrieved chunks",
    ["index_version"],
)
CITATION_INVALID = Counter(
    "rag_citation_invalid_total",
    "Invalid citation count",
    ["reason"],
)

MODEL_PRICE_USD_PER_1M = {
    "gpt-4.1-mini": {"input": Decimal("0.40"), "output": Decimal("1.60")},
    "gpt-4.1": {"input": Decimal("2.00"), "output": Decimal("8.00")},
}

PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:\+?84|0)(?:\d[\s.-]?){8,10}\b"), "[PHONE]"),
    (re.compile(r"\b\d{9,12}\b"), "[ID_NUMBER]"),
]


def hash_value(value: str | None) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(f"{SALT}:{value}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def safe_content(text: str | None) -> str | None:
    if text is None:
        return None
    return redact_text(text) if RAW_CONTENT_LOGGING else None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    price = MODEL_PRICE_USD_PER_1M.get(model)
    if not price:
        return Decimal("0")
    input_cost = Decimal(input_tokens) * price["input"] / Decimal(1_000_000)
    output_cost = Decimal(output_tokens) * price["output"] / Decimal(1_000_000)
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp_ms": int(time.time() * 1000),
        **fields,
    }
    LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))


@dataclass
class RagTrace:
    trace_id: str
    route: str
    tenant_id: str
    user_id_hash: str | None
    prompt_version: str
    model: str
    index_version: str
    status: Literal["success", "error"] = "success"
    error_type: str | None = None
    stage_latency_ms: dict[str, int] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    estimated_cost_usd: Decimal = Decimal("0")


@contextmanager
def measured_stage(trace_record: RagTrace, stage: str, **span_attrs: Any):
    start = time.perf_counter()
    with tracer.start_as_current_span(f"rag.{stage}") as span:
        span.set_attributes(
            {
                "rag.trace_id": trace_record.trace_id,
                "rag.tenant_id": trace_record.tenant_id,
                "rag.stage": stage,
                **{k: v for k, v in span_attrs.items() if v is not None},
            }
        )
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            trace_record.status = "error"
            trace_record.error_type = type(exc).__name__
            raise
        finally:
            elapsed_seconds = time.perf_counter() - start
            elapsed_ms = round(elapsed_seconds * 1000)
            trace_record.stage_latency_ms[stage] = elapsed_ms
            STAGE_LATENCY.labels(stage=stage).observe(elapsed_seconds)
```

Điểm production quan trọng trong module này:

- `trace_id` được propagate qua log, metric correlation và span attributes.
- Raw content mặc định không log. Muốn bật phải dùng env flag và vẫn redact.
- Prometheus label chỉ dùng field cardinality thấp như `stage`, `model`, `status`.
- Cost dùng Decimal để tránh lỗi làm tròn khi aggregate.
- Exception được record vào span và vẫn có log event riêng ở API layer.

### 8.4 FastAPI Query Endpoint

```python
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

app = FastAPI(title="RAG API with Observability")


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class QueryResponse(BaseModel):
    trace_id: str
    answer: str
    citations: list[dict[str, str]]
    usage: dict[str, int]
    estimated_cost_usd: str


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")] = "demo",
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> QueryResponse:
    trace_id = f"tr_{uuid.uuid4().hex}"
    route = "/query"
    model = "gpt-4.1-mini"
    prompt_version = "rag-answer-v7"
    index_version = "policy-index-2026-05-01"
    trace_record = RagTrace(
        trace_id=trace_id,
        route=route,
        tenant_id=x_tenant_id,
        user_id_hash=hash_value(x_user_id),
        prompt_version=prompt_version,
        model=model,
        index_version=index_version,
    )

    IN_FLIGHT.labels(route=route).inc()
    start = time.perf_counter()

    with tracer.start_as_current_span("rag.query") as root_span:
        root_span.set_attributes(
            {
                "rag.trace_id": trace_id,
                "rag.tenant_id": x_tenant_id,
                "rag.prompt_version": prompt_version,
                "rag.model": model,
                "rag.index_version": index_version,
            }
        )
        log_event(
            "query_received",
            trace_id=trace_id,
            tenant_id=x_tenant_id,
            user_id_hash=trace_record.user_id_hash,
            query_hash=hash_value(request.query),
            query_redacted=safe_content(request.query),
            query_length_chars=len(request.query),
            top_k=request.top_k,
        )

        try:
            with measured_stage(trace_record, "retrieval", index_version=index_version):
                retrieved = await retrieve_chunks(request.query, top_k=request.top_k)
                if not retrieved:
                    EMPTY_RETRIEVAL.labels(index_version=index_version).inc()

            log_event(
                "retrieval_completed",
                trace_id=trace_id,
                tenant_id=x_tenant_id,
                index_version=index_version,
                top_k=request.top_k,
                candidate_count=len(retrieved),
                empty_retrieval=len(retrieved) == 0,
                latency_ms=trace_record.stage_latency_ms["retrieval"],
                chunk_ids=[chunk["chunk_id"] for chunk in retrieved[:10]],
            )

            with measured_stage(trace_record, "rerank", candidate_count=len(retrieved)):
                reranked = await rerank_chunks(request.query, retrieved)

            with measured_stage(trace_record, "context_build", selected_count=len(reranked[:8])):
                context = build_context(reranked[:8])

            log_event(
                "context_built",
                trace_id=trace_id,
                chunk_count=len(context["chunk_ids"]),
                context_tokens=context["token_count"],
                truncated=context["truncated"],
            )

            with measured_stage(trace_record, "generation", model=model, prompt_version=prompt_version):
                generation = await generate_answer_streaming(
                    query=request.query,
                    context=context["text"],
                    model=model,
                    prompt_version=prompt_version,
                    trace_id=trace_id,
                )

            input_tokens = int(generation["usage"]["input_tokens"])
            output_tokens = int(generation["usage"]["output_tokens"])
            cost = estimate_cost_usd(model, input_tokens, output_tokens)
            trace_record.token_usage = {"input": input_tokens, "output": output_tokens}
            trace_record.estimated_cost_usd = cost

            TOKENS.labels(model=model, type="input").inc(input_tokens)
            TOKENS.labels(model=model, type="output").inc(output_tokens)
            COST.labels(model=model).inc(float(cost))
            TTFT.labels(model=model).observe(generation["ttft_ms"] / 1000)

            with measured_stage(trace_record, "citation_validation"):
                validation = validate_citations(generation["citations"], context["chunk_ids"])
                if not validation["valid"]:
                    CITATION_INVALID.labels(reason=validation["reason"]).inc()

            log_event(
                "generation_completed",
                trace_id=trace_id,
                tenant_id=x_tenant_id,
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                ttft_ms=generation["ttft_ms"],
                latency_ms=trace_record.stage_latency_ms["generation"],
                estimated_cost_usd=str(cost),
                finish_reason=generation["finish_reason"],
            )
            log_event(
                "citation_validated",
                trace_id=trace_id,
                valid=validation["valid"],
                failure_reason=validation["reason"],
            )

            REQUESTS.labels(route=route, status="success").inc()
            total_latency_ms = round((time.perf_counter() - start) * 1000)
            log_event(
                "query_completed",
                trace_id=trace_id,
                status="success",
                total_latency_ms=total_latency_ms,
                stage_latency_ms=trace_record.stage_latency_ms,
                token_usage=trace_record.token_usage,
                estimated_cost_usd=str(trace_record.estimated_cost_usd),
            )

            return QueryResponse(
                trace_id=trace_id,
                answer=generation["answer"],
                citations=generation["citations"],
                usage=trace_record.token_usage,
                estimated_cost_usd=str(trace_record.estimated_cost_usd),
            )

        except TimeoutError as exc:
            REQUESTS.labels(route=route, status="timeout").inc()
            log_event(
                "request_failed",
                trace_id=trace_id,
                status="timeout",
                error_type=type(exc).__name__,
                stage_latency_ms=trace_record.stage_latency_ms,
            )
            raise HTTPException(status_code=504, detail={"trace_id": trace_id, "error": "timeout"}) from exc
        except Exception as exc:
            REQUESTS.labels(route=route, status="error").inc()
            log_event(
                "request_failed",
                trace_id=trace_id,
                status="error",
                error_type=type(exc).__name__,
                stage_latency_ms=trace_record.stage_latency_ms,
            )
            raise HTTPException(status_code=500, detail={"trace_id": trace_id, "error": "internal_error"}) from exc
        finally:
            IN_FLIGHT.labels(route=route).dec()
```

Các hàm `retrieve_chunks`, `rerank_chunks`, `build_context`, `generate_answer_streaming` và `validate_citations` là boundary của app. Bài học không ràng buộc bạn vào provider cụ thể, nhưng observability contract phải ổn định dù implementation đổi từ Qdrant sang pgvector hoặc từ model A sang model B.

### 8.5 Đo TTFT Với Streaming

```python
async def generate_answer_streaming(
    query: str,
    context: str,
    model: str,
    prompt_version: str,
    trace_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_token_ms: int | None = None
    chunks: list[str] = []
    last_event: Any | None = None

    prompt = render_prompt(prompt_version=prompt_version, query=query, context=context)
    input_tokens_estimate = estimate_tokens(prompt)

    log_event(
        "generation_started",
        trace_id=trace_id,
        model=model,
        prompt_version=prompt_version,
        prompt_tokens_estimate=input_tokens_estimate,
    )

    async for token_event in llm_client.stream(model=model, prompt=prompt, temperature=0.1):
        last_event = token_event
        if first_token_ms is None:
            first_token_ms = round((time.perf_counter() - started) * 1000)
            log_event("first_token_received", trace_id=trace_id, model=model, ttft_ms=first_token_ms)
        chunks.append(token_event.text)

    answer = "".join(chunks)
    provider_usage = getattr(last_event, "usage", None)
    finish_reason = getattr(last_event, "finish_reason", None)
    usage = provider_usage if provider_usage else {
        "input_tokens": input_tokens_estimate,
        "output_tokens": estimate_tokens(answer),
    }

    return {
        "answer": answer,
        "citations": extract_citations(answer),
        "usage": usage,
        "ttft_ms": first_token_ms or round((time.perf_counter() - started) * 1000),
        "finish_reason": finish_reason or "unknown",
    }
```

Nếu provider không trả token usage, có thể estimate bằng tokenizer tương thích. Nhưng trong billing production, estimate chỉ dùng cho dashboard gần đúng. Billing thật vẫn cần đối soát với provider invoice.

## 9. Feedback Loop

Feedback phải gắn với `trace_id`. Nếu chỉ lưu `thumbs_down` mà không lưu trace, feedback gần như vô dụng cho debug.

```python
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    trace_id: str = Field(pattern=r"^tr_[a-f0-9]+$")
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


@app.post("/feedback")
async def feedback(
    request: FeedbackRequest,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")] = "demo",
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> dict[str, str]:
    feedback_record = {
        "trace_id": request.trace_id,
        "tenant_id": x_tenant_id,
        "user_id_hash": hash_value(x_user_id),
        "rating": request.rating,
        "reason": request.reason,
        "comment_redacted": safe_content(request.comment),
        "comment_hash": hash_value(request.comment),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "triage_status": "new",
    }
    await feedback_store.insert(feedback_record)
    log_event("feedback_received", **feedback_record)
    return {"status": "accepted", "trace_id": request.trace_id}
```

Feedback loop thực tế:

1. User gửi feedback.
2. Feedback store join với trace store qua `trace_id`.
3. Triage phân loại lỗi: retrieval, rerank, prompt, generation, citation, policy, UX.
4. Lỗi chất lượng được đưa vào golden set hoặc regression set.
5. Release sau phải chứng minh metric cải thiện hoặc không regression.

## 10. Tooling Comparison

| Tool | Mạnh ở đâu | Yếu ở đâu | Khi nên dùng |
|---|---|---|---|
| Langfuse | LLM trace, prompt versioning, cost, score, feedback, dataset/eval workflow | Cần xem xét data policy nếu dùng SaaS; self-host cần vận hành thêm | Capstone, LLM app độc lập, team muốn observability chuyên cho prompt/model |
| LangSmith | Trace/eval tốt trong ecosystem LangChain/LangGraph | Lock-in theo LangChain/LangGraph nhiều hơn; không thay thế metrics infra | App dùng LangChain/LangGraph và cần debug chain/agent |
| OpenTelemetry | Vendor-neutral traces, span context, integration microservice | Không tự hiểu prompt/chunk/feedback nếu bạn không thiết kế attributes | Enterprise, nhiều service, cần gửi trace sang nhiều backend |
| Prometheus/Grafana | Metrics, alert, SLO dashboard, chi phí thấp, phổ biến | Không lưu trace chi tiết; label cardinality phải kiểm soát | Production metrics mặc định cho API/RAG service |
| ELK/OpenSearch | Search structured logs, incident investigation, retention policy | Tốn storage nếu log raw prompt/context; cần index lifecycle | Khi cần search log chi tiết, audit và debug theo event |
| Custom JSON trace store | Kiểm soát schema, rẻ cho capstone nhỏ | Phải tự làm dashboard/report/retention | Learning project, MVP nội bộ, policy không cho gửi data ra SaaS |

Không cần dùng tất cả từ ngày đầu. Vấn đề cần giải quyết trước là schema và policy. Tool chỉ là nơi lưu và hiển thị.

## 11. Trade-off Quan Trọng

| Quyết định | Lợi ích | Chi phí/rủi ro | Khuyến nghị |
|---|---|---|---|
| Log raw prompt/context/output | Debug quality rất tốt | Rủi ro PII/confidential data, storage cost cao | Tắt mặc định, chỉ bật theo tenant/debug window, có redaction và approval |
| Metadata-only trace | An toàn hơn, rẻ hơn | Debug hallucination khó hơn | Default production cho dữ liệu nhạy cảm |
| Full tracing 100% request | Không bỏ sót lỗi hiếm | Storage và export overhead | 100% metadata trace, sample raw content theo policy |
| Sampling | Giảm cost | Có thể bỏ sót incident | Always keep errors, timeouts, thumbs down; sample success |
| Prometheus labels chi tiết | Query dashboard có vẻ tiện | Cardinality explosion | Label chỉ dùng field ít giá trị; chi tiết đưa vào logs/traces |
| SaaS observability | Nhanh, UI tốt | Data residency, cost, vendor dependency | Dùng nếu data policy cho phép và có DPA/security review |
| Self-host | Kiểm soát dữ liệu | Tốn vận hành | Dùng khi compliance yêu cầu hoặc scale đủ lớn |
| Sync logging | Code đơn giản | Tăng latency tail | Với traffic cao, dùng queue/batch exporter |

## 12. Best Solution Theo Context Và Performance

### Capstone hoặc MVP nội bộ

Best solution:

- Structured JSON logs.
- Một trace table hoặc JSONL trace store.
- Prometheus metrics cho latency, errors, token, cost.
- Grafana dashboard đơn giản.
- Feedback endpoint gắn với `trace_id`.
- Raw content logging tắt mặc định, bật tạm khi debug.

Lý do: đủ chứng minh production thinking, ít dependency, dễ chạy local và ít rủi ro data policy.

### App dùng LangChain hoặc LangGraph nhiều

Best solution:

- LangSmith để trace chain/agent/eval.
- Prometheus/Grafana cho service metrics và alert.
- Structured logs hoặc ELK/OpenSearch cho audit event.
- Redaction callback trước khi gửi prompt/tool args ra ngoài.

Lý do: LangSmith nhìn tốt graph/node/tool call, nhưng metrics production vẫn nên ở Prometheus/Grafana.

### Enterprise nhiều microservice

Best solution:

- OpenTelemetry làm chuẩn trace context xuyên API gateway, RAG service, retriever, reranker, LLM gateway.
- Prometheus/Grafana cho metrics và alert.
- ELK/OpenSearch cho logs.
- LLM-specific trace store như Langfuse nếu security review cho phép, hoặc custom trace store nếu không.

Lý do: vendor-neutral, tích hợp được với platform observability hiện có, không ép toàn bộ tổ chức vào một LLM SaaS.

### Dữ liệu nhạy cảm hoặc regulated domain

Best solution:

- Metadata-only trace mặc định.
- Hash user/session/query.
- Redaction trước log/export.
- Sampling raw content rất thấp, theo allowlist tenant và thời gian hữu hạn.
- Access control theo vai trò, audit người xem trace.
- Retention ngắn cho raw content, dài hơn cho aggregate metrics.

Lý do: debug không được đánh đổi bằng việc rò rỉ dữ liệu khách hàng.

### Performance-sensitive app

Best solution:

- Không ghi log đồng bộ nhiều payload lớn trong request path.
- Batch exporter cho traces.
- Async/background logging cho trace detail.
- Metrics dùng label cardinality thấp.
- Sample success traces, giữ toàn bộ error traces.
- Đo overhead của instrumentation trong load test.

Target hợp lý: observability overhead p95 nhỏ hơn 5% total latency, trừ khi đang bật debug mode tạm thời.

## 13. Privacy, Redaction Và Sampling

### Redaction

Các nhóm dữ liệu cần xử lý trước khi log:

- Email, phone, ID number, address.
- API key, bearer token, cookie, connection string.
- Customer name, employee id, salary, contract clause nếu domain nhạy cảm.
- Retrieved context từ document nội bộ.
- Tool arguments chứa dữ liệu hệ thống.

Redaction nên chạy trước khi dữ liệu rời process, không chỉ trước khi hiển thị trên dashboard.

### Sampling

Sampling policy gợi ý:

| Loại request | Metadata | Raw prompt/context/output |
|---|---:|---:|
| Success bình thường | 100% | 1-5% nếu policy cho phép |
| Timeout/error | 100% | 100% redacted hoặc theo allowlist |
| Thumbs down | 100% | 100% redacted hoặc theo allowlist |
| Tenant nhạy cảm | 100% | 0% mặc định |
| Eval/golden set | 100% | 100% vì dùng synthetic hoặc approved data |

Sampling không nên áp dụng mù. Error, timeout và negative feedback phải được giữ nhiều hơn success traffic.

### Retention

Gợi ý retention:

- Raw prompt/context/output: 7-30 ngày tùy policy.
- Redacted trace: 30-90 ngày.
- Metrics aggregate: 6-18 tháng.
- Audit log truy cập trace: theo yêu cầu compliance.
- Eval traces dùng cho regression: versioned lâu hơn, nhưng nên dùng dữ liệu đã được phê duyệt.

## 14. Production Readiness

### Dùng Được Trong Production Không?

Có, observability stack kiểu này dùng được trong production nếu thỏa các điều kiện sau:

- Có `trace_id` xuyên suốt request path và feedback path.
- Có structured logs, metrics và traces cho từng stage quan trọng.
- Có dashboard cho p50/p95/p99 latency, TTFT, token usage, cost/request, error rate, empty retrieval và citation failure.
- Có alert cho latency spike, error spike, cost spike, provider timeout, empty retrieval spike và citation failure spike.
- Có redaction trước khi ghi log/export trace.
- Có sampling policy rõ, đặc biệt với raw prompt/context/output.
- Có retention, access control và audit cho trace store.
- Có versioning cho prompt, model, embedding model, reranker và index.
- Có golden set/eval để biến feedback thành regression test.
- Có performance test chứng minh instrumentation không làm tăng latency quá mức.

### Chưa Đủ Production Nếu

- Chỉ `print()` prompt và answer ra console.
- Log raw PII/context vào third-party tool mà chưa có security review.
- Metrics không có token/cost/TTFT.
- Trace không lưu prompt/model/index version.
- Feedback không gắn với `trace_id`.
- Prometheus label chứa `user_id`, `query`, `trace_id` hoặc `chunk_id`.
- Không có alert và không có owner xử lý alert.
- Không có retention policy nên log storage tăng vô hạn.

## 15. Checklist Cuối Bài

- [ ] Mỗi request có `trace_id`.
- [ ] Mỗi stage có latency riêng.
- [ ] Logs là JSON và có event taxonomy cố định.
- [ ] Metrics có request count, latency, error, TTFT, token, cost, empty retrieval và citation failure.
- [ ] Trace schema lưu prompt/model/index/embedding/reranker version.
- [ ] Feedback endpoint gắn với `trace_id`.
- [ ] Raw content logging có redaction, sampling và retention.
- [ ] Dashboard có p95 latency, p95 TTFT, cost/request, token/request và quality signals.
- [ ] Alert đầu tiên tập trung vào latency, error, cost, empty retrieval và citation failure.
- [ ] Bạn trả lời được production readiness bằng điều kiện cụ thể, không chỉ nói "có logging".
