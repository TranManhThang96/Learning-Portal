# Day 48 Exercise: Chuẩn Hóa Backend/API Capstone

## Mục Tiêu

Bạn sẽ biến capstone từ ý tưởng thành backend/API contract có thể build và review.

Deliverables:

- Architecture diagram dạng text hoặc hình.
- Repo structure.
- `.env.example`.
- FastAPI skeleton hoặc backend tương đương.
- API contract cho ingestion/query/trace/eval.
- Readiness checklist.

## Bài Tập 1: Chốt Scope

Viết `docs/scope.md`:

```markdown
# Scope

## Problem

## Users

## Core Features

## Non-Goals

## Demo Flow

## Risks

## Success Criteria
```

Success criteria phải đo được, ví dụ:

- Query demo trả answer có citation.
- No-answer case không hallucinate.
- Eval set 30 cases chạy được.
- Trace hiển thị latency/token/cost.

## Bài Tập 2: Vẽ Architecture

Tạo `docs/architecture.md` với:

```text
Frontend
  -> Backend API
      -> Auth/Tenant Context
      -> Ingestion Pipeline
      -> RAG Orchestrator
      -> Trace Store
      -> Eval Runner
```

Sau diagram, giải thích 3 path:

- Indexing path.
- Query path.
- Eval path.

## Bài Tập 3: Tạo API Schemas

Tạo `apps/api/app/schemas.py`:

```python
from pydantic import BaseModel, Field


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
```

## Bài Tập 4: Tạo Backend Skeleton

Tạo `apps/api/app/main.py`:

```python
from fastapi import FastAPI, HTTPException
from .schemas import QueryRequest, QueryResponse

app = FastAPI(title="Vietnamese Enterprise Knowledge Assistant")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if not request.roles:
        raise HTTPException(status_code=403, detail="Missing roles")
    return QueryResponse(
        answer="Không đủ thông tin trong tài liệu hiện có.",
        citations=[],
        trace_id="trace_demo",
        latency_ms={"retrieve": 0, "rerank": 0, "generate": 0, "total": 0},
        usage={"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0},
    )
```

Chạy local:

```bash
uvicorn apps.api.app.main:app --reload --port 8000
```

## Bài Tập 5: Viết `.env.example`

Bắt buộc có:

- `VECTOR_DB_URL`.
- `LLM_PROVIDER`.
- `LLM_MODEL`.
- `LLM_API_KEY`.
- `EMBEDDING_MODEL`.
- `RERANKER_MODEL`.
- `CHUNK_SIZE`.
- `CHUNK_OVERLAP`.
- `BM25_TOP_K`.
- `VECTOR_TOP_K`.
- `RERANK_TOP_K`.
- `CONTEXT_TOP_K`.
- `MAX_CONTEXT_TOKENS`.
- `PROMPT_VERSION`.
- `INDEX_VERSION`.

Không commit `.env` thật.

## Bài Tập 6: Viết Readiness Gate

Tạo `docs/day48_readiness.md`:

```markdown
# Day 48 Readiness

- [ ] Architecture diagram exists.
- [ ] API contract documented.
- [ ] `/health` works.
- [ ] `/ready` checks dependencies.
- [ ] `/query` returns answer/citations/trace_id.
- [ ] Ingestion design documented.
- [ ] Config boundary documented.
- [ ] Trace schema documented.
- [ ] Known limitations documented.
```

## Checklist Nộp Bài

- [ ] Có `docs/scope.md`.
- [ ] Có `docs/architecture.md`.
- [ ] Có schemas cho query/citation/trace.
- [ ] Có backend skeleton chạy được.
- [ ] Có `.env.example`.
- [ ] Có API contract cho Day 49 UI.
- [ ] Có readiness checklist và limitations.
