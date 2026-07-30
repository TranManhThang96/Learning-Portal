# Day 48 Document: Backend/API Reference

## 1. API Endpoint Checklist

| Endpoint | Request validation | Response contract | Trace? | Notes |
|---|---|---|---|---|
| `GET /health` | None | `{"status":"ok"}` | No | Process alive |
| `GET /ready` | None | dependency statuses | Optional | Check vector DB/index/provider |
| `POST /documents/upload` | file type/size | upload status | Yes | No raw secret in logs |
| `POST /documents/ingest` | `doc_id`, tenant, options | job/status | Yes | Prefer async for large docs |
| `GET /documents` | tenant/role | document statuses | Yes | Filter by tenant |
| `POST /query` | question/tenant/user/roles | answer/citations/trace | Yes | Main RAG API |
| `POST /feedback` | trace/rating/reason | accepted | Yes | Tie feedback to trace |
| `GET /traces/{trace_id}` | auth/tenant | redacted trace | Yes | Debug view |
| `POST /eval/run` | eval set/version | run ID | Yes | Restrict access |

## 2. Schema Snippets

### Document Status

```json
{
  "doc_id": "hr_policy_001",
  "title": "Chính sách nhân sự",
  "tenant_id": "demo",
  "status": "indexed",
  "document_version": "v1",
  "chunk_count": 128,
  "index_version": "enterprise_docs_v1",
  "created_at": "2026-05-10T10:00:00Z",
  "updated_at": "2026-05-10T10:05:00Z"
}
```

### Trace

```json
{
  "trace_id": "trace_20260510_001",
  "tenant_id": "demo",
  "prompt_version": "rag_prompt_v3",
  "model": "gpt-4.1-mini",
  "embedding_model": "embedding-v1",
  "index_version": "enterprise_docs_v1",
  "retrieval": {
    "bm25_top_k": 50,
    "vector_top_k": 50,
    "rerank_top_k": 20,
    "context_top_k": 6,
    "retrieved_chunk_ids": [
      "hr_policy_001:v1:0007",
      "hr_policy_001:v1:0012"
    ]
  },
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
  },
  "guardrails": {
    "pii_detected": false,
    "citation_valid": true,
    "policy_action": "allow",
    "prompt_injection_blocked": null,
    "acl_leak": false
  }
}
```

`retrieved_chunk_ids` phục vụ eval/debug và chỉ được trả qua trace endpoint có
authorization. End-user query response không cần lộ danh sách retrieval đầy đủ hoặc
raw context.

## 3. `.env.example` Template

```bash
APP_ENV=local
API_PORT=8000

VECTOR_DB_URL=http://localhost:6333
VECTOR_COLLECTION=enterprise_docs

LLM_PROVIDER=openai-compatible
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=change-this-in-local-env

EMBEDDING_MODEL=text-embedding-model
RERANKER_MODEL=cross-encoder-model

CHUNK_SIZE=800
CHUNK_OVERLAP=120
BM25_TOP_K=50
VECTOR_TOP_K=50
RERANK_TOP_K=20
CONTEXT_TOP_K=6
MAX_CONTEXT_TOKENS=6000

PROMPT_VERSION=rag_prompt_v1
INDEX_VERSION=enterprise_docs_v1
```

## 4. Architecture Review Questions

- Ingestion có idempotent không?
- Chunk metadata có đủ `tenant_id`, `acl_roles`, `doc_id`, `page`, `section`, `document_version` không?
- Permission filter chạy trước hay sau retrieval?
- Nếu vector DB down, `/ready` trả gì?
- Nếu reranker timeout, query pipeline fallback thế nào?
- Citation validator kiểm tra bằng `chunk_id` hay chỉ text?
- Trace có đủ prompt/model/index version không?
- Eval runner gọi API hay pipeline trực tiếp?
- Có đường rollback prompt/model/index không?

## 5. Common Architecture Mistakes

- API route chứa toàn bộ RAG logic.
- Retrieval không filter tenant/role.
- Không version index/chunking/prompt.
- Không phân biệt ingestion path và query path.
- Không có `/ready`, chỉ có `/health`.
- Không có trace ID trong response.
- Không validate citation.
- Hard-code model/top-k/token budget.
- Không có no-answer fallback.
- Demo dùng secret thật trong `.env` hoặc video.

## 6. Definition Of Done Cho Day 48

- Có folder/documentation rõ cho capstone backend.
- Có API contract đủ để frontend Day 49 dùng.
- Có config boundary và `.env.example`.
- Có architecture diagram hoặc text diagram.
- Có ingestion/query/eval paths.
- Có readiness checklist trước UI.
- Có limitations và production conditions.

## 7. API Invariants Giữa Day 46-49

| Invariant | Lý do |
|---|---|
| `policy_action` là enum | Eval không đoán refusal từ wording |
| `citations[*].chunk_id` thuộc allowed context | Không cite source ngoài trust boundary |
| `trace.guardrails.acl_leak` có `true/false/null` | Phân biệt fail, pass và case không áp dụng |
| `latency_ms.total` luôn có | UI/report không tự cộng field thiếu |
| `usage` dùng số không âm | Cost/token report có contract |
| Citation có `document_version` | Audit stale source |

## 8. Nguồn Kỹ Thuật Đã Xác Minh

Truy cập ngày `2026-06-08`:

- [FastAPI request files](https://fastapi.tiangolo.com/tutorial/request-files/):
  `UploadFile`, spooled file, async methods và `multipart/form-data`.
- [FastAPI forms and files](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/):
  cần cài `python-multipart` để nhận form/file.
- [FastAPI response model](https://fastapi.tiangolo.com/tutorial/response-model/):
  validate/filter output theo response contract.
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/):
  `TestClient`; async test có thể dùng HTTPX ASGI transport.
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) và
  [fields](https://docs.pydantic.dev/latest/concepts/fields/):
  `BaseModel`, `Field`, `model_validate_json`, constraints và strictness.
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/):
  `BaseSettings`, `SettingsConfigDict`, env sources và `.env`.

Context7 đã xác minh FastAPI `0.128.0`, Pydantic v2 và settings syntax dùng trong
bài. Không pin version trong prose thay cho dependency lock của capstone.
