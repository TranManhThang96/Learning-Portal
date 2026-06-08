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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000)
    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=128)
    roles: list[str] = Field(default_factory=list, max_length=20)
    conversation_id: str | None = Field(default=None, max_length=128)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    doc_id: str
    title: str | None = None
    chunk_id: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    document_version: str | None = None
    score: float | None = None


class LatencyBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieve: int = Field(ge=0)
    rerank: int = Field(ge=0)
    generate: int = Field(ge=0)
    total: int = Field(ge=0)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4000)
    citations: list[Citation]
    trace_id: str
    latency_ms: LatencyBreakdown
    usage: Usage
    policy_action: Literal["allow", "refuse", "escalate"]
    needs_escalation: bool = False

    @model_validator(mode="after")
    def enforce_policy_contract(self) -> "QueryResponse":
        if self.policy_action == "allow" and not self.citations:
            raise ValueError("Allowed answer must include citations")
        if self.policy_action == "refuse" and self.citations:
            raise ValueError("Refusal must not include citations")
        if self.policy_action == "escalate" and not self.needs_escalation:
            raise ValueError("Escalation must set needs_escalation=true")
        return self


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=64)


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["accepted"]
```

## Bài Tập 4: Tạo Backend Skeleton

Tạo `apps/api/app/main.py`:

```python
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from .schemas import IngestRequest, IngestResponse, QueryRequest, QueryResponse

app = FastAPI(title="Vietnamese Enterprise Knowledge Assistant")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "text/markdown"}
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, object]:
    checks = {"config": True, "vector_db": False, "index": False}
    if not all(checks.values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}


async def validate_upload(file: UploadFile) -> int:
    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_CONTENT_TYPES or suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
    await file.seek(0)
    return size


@app.post("/documents/upload")
async def upload_document(
    file: Annotated[UploadFile, File()],
) -> dict[str, str | int]:
    size = await validate_upload(file)
    return {
        "filename": Path(file.filename or "unknown").name,
        "size_bytes": size,
        "status": "accepted",
    }


@app.post("/documents/ingest", response_model=IngestResponse, status_code=202)
def ingest_document(request: IngestRequest) -> IngestResponse:
    return IngestResponse(job_id=f"ingest_{request.doc_id}", status="accepted")


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
        policy_action="refuse",
        needs_escalation=False,
    )
```

Chạy local:

```bash
python3 -m pip install fastapi uvicorn python-multipart
python3 -m uvicorn apps.api.app.main:app --reload --port 8000
```

`/ready` phải trả `503` ở skeleton cho đến khi bạn thay check giả bằng check vector
DB/index/config thật. Upload acceptance criteria:

- Reject file vượt 10 MiB.
- Reject suffix/MIME không allowlist.
- Không dùng raw filename làm storage path.
- Ghi rõ production còn cần magic-byte/parser sandbox/malware policy.

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

## Bài Tập 7: API Contract Tests

Tạo `apps/api/tests/test_contract.py` bằng `fastapi.testclient.TestClient` hoặc
`httpx.AsyncClient` + `ASGITransport`. Bắt buộc test:

- `/health` trả `200`.
- `/ready` trả `503` khi dependency chưa sẵn sàng.
- Query thiếu roles trong demo trả `403`.
- Query fallback trả `policy_action="refuse"` và không citation.
- Upload sai type trả `415`; file quá lớn trả `413`.
- `/documents/ingest` trả `202` và `job_id`.

Không cần gọi LLM/vector DB thật trong contract tests; inject fake service để test
route, schema và error behavior deterministic.

## Checklist Nộp Bài

- [ ] Có `docs/scope.md`.
- [ ] Có `docs/architecture.md`.
- [ ] Có schemas cho query/citation/trace.
- [ ] Có backend skeleton chạy được.
- [ ] Có `.env.example`.
- [ ] Có API contract cho Day 49 UI.
- [ ] Có contract tests cho happy path và failure path.
- [ ] Có readiness checklist và limitations.
