# Day 48: Capstone Architecture Review + Backend/API

## Mục Tiêu

Sau bài này, bạn cần có một backend/API capstone đủ rõ để reviewer hiểu và chạy được:

- Chốt scope capstone: Vietnamese Enterprise Knowledge Assistant.
- Review architecture từ ingestion, retrieval, generation, citation, permission, observability đến evaluation.
- Chuẩn hóa repo structure để project nhìn như production-style system.
- Thiết kế API contract cho document upload, ingestion, query/chat, traces, feedback và eval.
- Tách configuration boundary, không hard-code model/index/token budget.
- Biết readiness gate trước khi chuyển sang UI/monitoring ở Day 49.
- Trả lời được: backend này dùng production được chưa, cần điều kiện gì.

## TL;DR

Day 48 là ngày chuyển các bài học rời rạc thành capstone có architecture rõ. Mục tiêu không phải thêm feature vô hạn, mà là đóng scope, làm backend/API có boundary tốt, có ingestion path, query path, citation, permission filter, config, tracing và eval hook. Một portfolio tốt chứng minh engineering decision, không chỉ demo chatbot trả lời vài câu.

## 1. Scope Capstone

Tên gợi ý:

```text
Vietnamese Enterprise Knowledge Assistant
```

Problem statement:

> Tài liệu nội bộ doanh nghiệp thường phân tán ở PDF, Markdown, wiki, policy file. Keyword search yếu với tiếng Việt và raw LLM dễ hallucinate hoặc leak dữ liệu. Hệ thống cần hỏi đáp tài liệu tiếng Việt có citation, permission-aware retrieval, evaluation và monitoring.

Core features:

- Upload/ingest document PDF/Markdown/Text.
- Parse document và normalize text.
- Chunk theo page/section/heading.
- Embedding tiếng Việt/multilingual.
- Vector DB: Qdrant hoặc pgvector.
- Sparse retrieval: BM25.
- Hybrid search + RRF merge.
- Reranking.
- Chat/query API.
- Citation theo source/page/section/chunk.
- Permission-aware retrieval.
- Trace latency/token/cost.
- Evaluation bằng golden dataset.
- Docker Compose deploy local.

Non-goals cho capstone:

- Full enterprise SSO.
- Multi-agent phức tạp.
- Perfect UI.
- Distributed Kubernetes production.
- Fine-tune model mới.
- Full document lifecycle/legal retention.

Scope tốt là scope có thể demo trong 3-5 phút và defend trong interview.

## 2. Architecture Tổng Thể

```text
Frontend
  -> Backend API
      -> Auth/Tenant Context
      -> Document Service
      -> Ingestion Pipeline
          -> File Validator
          -> Parser
          -> Normalizer
          -> Chunker
          -> Metadata Enricher
          -> Embedding Client
          -> Vector DB / BM25 Index
      -> RAG Orchestrator
          -> Request Validator
          -> Query Normalizer
          -> Dense Retriever
          -> Sparse Retriever
          -> RRF Merger
          -> Reranker
          -> Context Builder
          -> LLM Gateway
          -> Citation Validator
          -> Guardrails
      -> Trace Store
      -> Feedback Store
      -> Eval Runner
```

Tách 3 path:

| Path | Mục đích | Failure mode chính |
|---|---|---|
| Indexing path | Parse, chunk, embed, index | Duplicate chunks, stale index, bad metadata |
| Query path | Retrieve, rerank, generate, cite | Hallucination, invalid citation, timeout |
| Eval path | Replay golden set, report metrics | Non-reproducible run, missing trace |

## 3. Repo Structure

Gợi ý production-style nhưng vẫn vừa sức capstone:

```text
enterprise-rag-assistant/
  apps/
    api/
      app/
        main.py
        config.py
        schemas.py
        routes/
        services/
      tests/
    web/
  packages/
    rag/
      chunking.py
      retrieval.py
      reranking.py
      context.py
      citations.py
    llm/
      gateway.py
      prompts/
    eval/
      runner.py
      metrics.py
    observability/
      tracing.py
  data/
    raw/
    processed/
    eval/
  scripts/
    ingest.py
    evaluate.py
  docker-compose.yml
  .env.example
  README.md
```

Boundary quan trọng:

- API chỉ nhận request, validate, gọi service.
- RAG core không phụ thuộc framework web.
- LLM gateway che provider cụ thể.
- Eval runner có thể gọi API hoặc pipeline trực tiếp.
- Observability không trộn vào business logic quá sâu.

## 4. Backend/API Contract

Endpoint tối thiểu:

| Method | Path | Mục đích |
|---|---|---|
| `GET` | `/health` | Process alive |
| `GET` | `/ready` | Dependency/model/index ready |
| `POST` | `/documents/upload` | Upload file |
| `POST` | `/documents/ingest` | Parse/chunk/embed/index |
| `GET` | `/documents` | List documents/status |
| `POST` | `/query` | Ask RAG |
| `POST` | `/feedback` | User feedback gắn trace |
| `GET` | `/traces/{trace_id}` | Debug trace |
| `POST` | `/eval/run` | Chạy eval |
| `GET` | `/eval/runs/{run_id}` | Lấy eval result |

Query request:

```json
{
  "question": "Nhân viên được nghỉ phép năm bao nhiêu ngày?",
  "tenant_id": "demo",
  "user_id": "reviewer",
  "roles": ["employee"],
  "conversation_id": "demo-session-001"
}
```

Query response:

```json
{
  "answer": "Nhân viên full-time được nghỉ 12 ngày phép năm theo chính sách HR. [S1]",
  "citations": [
    {
      "source_id": "S1",
      "doc_id": "hr_policy_001",
      "title": "Chính sách nhân sự",
      "chunk_id": "hr_policy_001:v1:0007",
      "page": 4,
      "section": "Nghỉ phép năm"
    }
  ],
  "trace_id": "trace_20260510_001",
  "latency_ms": {
    "retrieve": 52,
    "rerank": 176,
    "generate": 1240,
    "total": 1530
  },
  "usage": {
    "input_tokens": 1180,
    "output_tokens": 96,
    "estimated_cost_usd": 0.0021
  }
}
```

## 5. FastAPI Skeleton Gần Production

Ví dụ ngắn dùng `FastAPI` request/response models và `Pydantic` validation:

```python
from typing import Annotated
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

app = FastAPI(title="Vietnamese Enterprise Knowledge Assistant")


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=128)
    roles: list[str] = Field(default_factory=list, max_length=20)
    conversation_id: str | None = Field(default=None, max_length=128)


class Citation(BaseModel):
    source_id: str
    doc_id: str
    title: str | None = None
    chunk_id: str
    page: int | None = None
    section: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
    latency_ms: dict[str, int]
    usage: dict[str, int | float]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    # Check vector DB, embedding provider, index metadata and config.
    return {"status": "ready"}


@app.post("/documents/upload")
async def upload_document(file: Annotated[UploadFile, File()]) -> dict[str, str]:
    if file.content_type not in {"application/pdf", "text/plain", "text/markdown"}:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    return {"filename": file.filename or "unknown", "status": "accepted"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    # In production, call RAG service and return validated response.
    return QueryResponse(
        answer="Không đủ thông tin trong tài liệu hiện có.",
        citations=[],
        trace_id="trace_demo",
        latency_ms={"retrieve": 0, "rerank": 0, "generate": 0, "total": 0},
        usage={"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0},
    )
```

Điểm production cần thêm:

- Dependency injection cho service clients.
- Timeout/retry rõ cho provider.
- Structured logging đã redact PII.
- Request ID/trace ID middleware.
- Rate limiting.
- Auth thật.
- Error format nhất quán.

## 6. Configuration Boundary

Không hard-code:

- Model provider/model name.
- Embedding model.
- Reranker model.
- Vector DB connection.
- Chunk size/overlap.
- Retrieval top-k.
- Rerank top-k.
- Context top-k.
- Prompt version.
- Index version.
- Eval threshold.
- Token budget.
- Guardrail thresholds.

Pydantic settings mẫu:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    vector_db_url: str = "http://localhost:6333"
    llm_provider: str = "openai-compatible"
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-model"
    chunk_size: int = Field(default=800, ge=200, le=3000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    vector_top_k: int = Field(default=50, ge=1, le=200)
    bm25_top_k: int = Field(default=50, ge=1, le=200)
    rerank_top_k: int = Field(default=20, ge=1, le=100)
    context_top_k: int = Field(default=6, ge=1, le=20)
    max_context_tokens: int = Field(default=6000, ge=500, le=32000)
```

`.env.example` nên có default an toàn và không chứa secret thật.

## 7. Ingestion Pipeline

```text
upload document
  -> validate file type/size
  -> store raw file
  -> parse
  -> normalize text
  -> chunk
  -> attach metadata
  -> embed
  -> upsert vector DB
  -> update BM25 index
  -> mark document status indexed
```

Metadata tối thiểu:

```json
{
  "tenant_id": "demo",
  "doc_id": "policy_001",
  "source_uri": "data/raw/policy.pdf",
  "title": "Chính sách nhân sự",
  "page": 3,
  "section": "Nghỉ phép năm",
  "acl_roles": ["employee"],
  "document_version": "v1",
  "index_version": "rag-index-v1",
  "content_hash": "sha256:..."
}
```

Production concern:

- Ingestion phải idempotent.
- Re-run không tạo duplicate chunks.
- Có document status: `uploaded`, `parsing`, `indexed`, `failed`.
- Store error reason để debug.
- Không index document vượt size/type policy.
- Metadata ACL phải đi cùng chunk.

## 8. Query Pipeline

```text
question
  -> validate request
  -> tenant/ACL context
  -> normalize query
  -> BM25 top 50
  -> vector top 50
  -> RRF merge
  -> rerank top 20-50
  -> permission/context filter
  -> context top 5-8
  -> generate answer
  -> validate schema
  -> validate citation
  -> log trace
  -> return answer + citations + trace_id
```

Fallback:

- Empty retrieval: trả "không đủ thông tin".
- Reranker timeout: dùng hybrid rank.
- Citation invalid: retry một lần hoặc refuse safe.
- Provider timeout: trả retryable error có trace ID.
- Eval mode: lưu full trace đã redact.

## 9. Trade-Offs Và Best Solution

| Quyết định | Option A | Option B | Best solution theo context |
|---|---|---|---|
| Vector DB | Qdrant | pgvector | Qdrant nhanh cho demo vector-first; pgvector hợp stack Postgres |
| Retrieval | Dense only | Hybrid | Hybrid cho tài liệu tiếng Việt + thuật ngữ nội bộ |
| Rerank | Không rerank | Cross-encoder rerank | Rerank top 20-50 nếu latency budget cho phép |
| API | Sync đơn giản | Async/background jobs | Upload sync, ingestion async nếu file lớn |
| Auth | Demo roles | Real SSO/JWT | Capstone dùng roles rõ; production cần auth thật |
| Eval | API-level | Pipeline-level | Có cả hai: pipeline debug nhanh, API e2e trước release |
| Observability | Logs | Traces + metrics | Trace theo request để debug RAG layers |

## 10. Performance Và Capacity

Cần đo theo stage:

- Upload/parse time.
- Chunk count per document.
- Embedding throughput.
- Vector upsert latency.
- BM25 retrieval latency.
- Vector retrieval latency.
- Rerank latency.
- LLM generation latency.
- Total p50/p95 latency.
- Token/cost per request.

Budget demo hợp lý:

| Stage | Target |
|---|---:|
| `/health` | < 50 ms |
| `/ready` | < 500 ms |
| Retrieval | < 300 ms |
| Rerank | < 1000 ms |
| Generate | < 5000 ms |
| Total query p95 | < 7000 ms |

Nếu latency quá cao:

- Giảm `rerank_top_k`.
- Giảm `context_top_k`.
- Cache embedding query phổ biến.
- Dùng cheaper/faster model cho low-risk query.
- Tách ingestion ra background queue.

## 11. Readiness Gate Trước Day 49

- [ ] Có architecture diagram hoặc text diagram.
- [ ] Có API docs/contract.
- [ ] Có endpoint health/ready/query/document.
- [ ] Có citation response contract.
- [ ] Có config file hoặc `.env.example`.
- [ ] Có ingestion pipeline design.
- [ ] Có query pipeline design.
- [ ] Có trace fields cho latency/token/cost.
- [ ] Có eval hook hoặc endpoint.
- [ ] Có known limitations.

## 12. Dùng Được Trong Production Không?

Có thể dùng làm nền production, nhưng bản capstone chưa nên được gọi là production hoàn chỉnh nếu thiếu auth, security review và vận hành thật.

Điều kiện để production:

- Auth/tenant/ACL thật, enforce trước retrieval.
- Ingestion async, idempotent, có retry và status.
- Vector DB/index có backup, migration/versioning.
- Secret management qua vault/env, không commit key.
- API có rate limit, timeout, structured error và observability.
- Guardrails từ Day 46 được tích hợp.
- Eval gate từ Day 47 chạy trước release.
- Monitoring từ Day 49 có alert.
- Có rollback cho prompt/model/index.

Với portfolio, mục tiêu hợp lý là "production-style": architecture và code thể hiện đúng boundary, có demo local, có metrics/eval/guardrails, và limitations được nói thẳng.
