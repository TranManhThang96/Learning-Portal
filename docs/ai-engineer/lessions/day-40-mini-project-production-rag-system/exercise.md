# Exercise: Triển Khai Mini-project Production RAG System

## Mục tiêu

Bạn sẽ triển khai một RAG mini-project có upload/ingest, parse, chunk, embed, vector DB, hybrid search, rerank, generation, citation, trace logging, eval report, backend API, simple UI và Docker Compose.

Thời lượng đề xuất:

- Bản tối thiểu: 1 ngày tập trung.
- Bản portfolio tốt: 2-3 ngày.
- Bản gần production hơn: 1 tuần, thêm auth thật, CI, monitoring và deployment.

## 0. Acceptance criteria

Hoàn thành bài tập khi bạn có:

- [ ] `docker compose up --build` chạy backend, UI, Postgres và Qdrant.
- [ ] Upload hoặc ingest được ít nhất 20 tài liệu mẫu.
- [ ] Chunk có metadata: document, page/heading, tenant, ACL, index version.
- [ ] Query trả answer có citation.
- [ ] Dense search và lexical search đều chạy, hybrid merge bằng RRF.
- [ ] Reranker có thể bật/tắt để so sánh.
- [ ] Trace hiển thị latency/token/cost theo stage.
- [ ] Eval runner chạy ít nhất 30 câu golden set.
- [ ] Eval report so sánh vector-only, hybrid, hybrid-rerank.
- [ ] README trả lời production readiness.

## 1. Chuẩn bị dữ liệu

Tạo folder:

```text
data/
  sample_docs/
    hr_policy.md
    remote_work.md
    expense_policy.md
    it_security.md
    onboarding.md
  golden_set.jsonl
```

Yêu cầu corpus:

- Ít nhất 20 documents hoặc 20 sections đủ dài.
- Có tài liệu dễ nhầm nhau, ví dụ policy cho employee và manager.
- Có keyword exact, ví dụ mã chính sách `EXP-2026`, `WFH`, `VPN`.
- Có câu hỏi no-answer, ví dụ hỏi về chính sách không nằm trong tài liệu.
- Có ACL khác nhau: `employee`, `hr`, `finance`, `admin`.

Ví dụ `golden_set.jsonl`:

```jsonl
{"id":"q001","question":"Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?","expected_answer":"12 ngày nghỉ phép năm.","expected_chunk_ids":["demo:hr_policy:v1:00003"],"tags":["hr","leave"],"difficulty":"easy"}
{"id":"q002","question":"Mã EXP-2026 áp dụng cho khoản chi nào?","expected_answer":"Chính sách hoàn tiền công tác.","expected_chunk_ids":["demo:expense_policy:v1:00002"],"tags":["finance","keyword"],"difficulty":"medium"}
{"id":"q003","question":"Công ty có chính sách mua xe cá nhân cho nhân viên không?","expected_answer":"Không đủ thông tin trong tài liệu được cung cấp.","expected_chunk_ids":[],"tags":["no_answer"],"difficulty":"easy"}
```

## 2. Scaffold project

Tạo cấu trúc:

```text
production-rag-system/
  backend/
  frontend/
  data/
  reports/
  docker-compose.yml
  .env.example
  README.md
```

Backend dependencies gợi ý:

```toml
[project]
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "pydantic-settings",
  "sqlalchemy[asyncio]",
  "asyncpg",
  "qdrant-client",
  "python-multipart",
  "tiktoken",
  "httpx",
  "tenacity",
  "structlog",
]
```

Nếu chưa có provider embedding/LLM thật, tạo interface và một fake provider để test pipeline. Nhưng README phải ghi rõ fake provider không đủ production.

## 3. Implement config và healthcheck

Tạo `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "rag_chunks"
    active_index_version: str = "rag-v1"
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100
    dense_top_k: int = 50
    sparse_top_k: int = 50
    rerank_top_n: int = 30
    context_top_k: int = 6
    max_context_tokens: int = 3500
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    class Config:
        env_file = ".env"

settings = Settings()
```

Tạo `GET /health` trả:

```json
{
  "status": "ok",
  "index_version": "rag-v1",
  "dependencies": {
    "postgres": "ok",
    "qdrant": "ok"
  }
}
```

## 4. Implement parser

Yêu cầu:

- `.txt`: đọc text.
- `.md`: giữ heading.
- `.pdf`: nếu chưa kịp làm parser tốt, dùng parser đơn giản nhưng ghi limitation.

Output parser:

```python
class ParsedBlock(BaseModel):
    text: str
    page: int | None = None
    heading: str | None = None
    block_type: str = "paragraph"

class ParsedDocument(BaseModel):
    title: str
    blocks: list[ParsedBlock]
```

Test:

- Markdown heading phải được gắn vào block sau nó.
- File rỗng bị reject.
- File quá lớn bị reject.

## 5. Implement chunker

Yêu cầu:

- Chunk theo heading nếu có.
- Chunk size khoảng 700 tokens, overlap 100 tokens.
- Lưu `page_start`, `page_end`, `heading`.
- Tạo deterministic `chunk_id`.

Pseudo-code:

```python
def chunk_document(parsed: ParsedDocument, document: DocumentMeta, settings: Settings) -> list[Chunk]:
    text_units = merge_blocks_by_heading(parsed.blocks)
    chunks = []
    for unit in text_units:
        windows = sliding_token_windows(
            unit.text,
            size=settings.chunk_size_tokens,
            overlap=settings.chunk_overlap_tokens,
        )
        for window in windows:
            chunks.append(make_chunk(document=document, unit=unit, text=window))
    return chunks
```

Acceptance:

- Không chunk nào rỗng.
- Mỗi chunk có `tenant_id`, `acl_roles`, `document_id`, `index_version`.
- Re-run cùng input tạo cùng `chunk_id`.

## 6. Implement ingestion service

Endpoint:

```text
POST /documents/upload
GET /documents
DELETE /documents/{document_id}
```

Flow:

```text
save raw file
create document row status=processing
parse
chunk
embed batch
upsert Qdrant
update sparse index
insert chunks metadata
mark indexed
```

Failure handling:

- Nếu parse fail: document status `failed`, lưu error ngắn.
- Nếu embedding fail: retry có backoff, sau đó `failed`.
- Nếu upsert vector fail: không mark indexed.
- Nếu delete: set document/chunks `deleted=true`, update sparse index, xóa hoặc filter vector records.

Acceptance:

- Upload file hợp lệ tạo document status `indexed`.
- Upload duplicate content không tạo index duplicate hoặc phải version rõ.
- Delete document xong query không retrieve chunk đó.

## 7. Implement vector store

Tạo Qdrant collection với dimension đúng embedding model.

Payload indexes nên có:

- `tenant_id`
- `acl_roles`
- `document_id`
- `index_version`
- `deleted`

Search function phải nhận `AuthContext`:

```python
class AuthContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: list[str]

async def dense_search(query_vector: list[float], auth: AuthContext, top_k: int) -> list[SearchHit]:
    filter_ = build_acl_filter(
        tenant_id=auth.tenant_id,
        roles=auth.roles,
        index_version=settings.active_index_version,
    )
    return await vector_store.search(query_vector=query_vector, filter_=filter_, top_k=top_k)
```

Không cho client truyền `tenant_id` để search.

## 8. Implement lexical search

Chọn một trong 3 mức:

| Mức | Cách làm | Ghi chú |
|---|---|---|
| Cơ bản | `rank-bm25` in-memory | Dễ học, không production cho multi-instance |
| Tốt cho mini-project | Tantivy persisted index | BM25 thật, nhẹ hơn OpenSearch |
| Production phổ biến | OpenSearch/Elasticsearch | Ops nặng hơn, search feature mạnh |

Acceptance:

- Lexical search cũng enforce tenant/ACL/deleted/index_version.
- Query chứa acronym hoặc mã policy phải tìm được chunk đúng.
- Trace hiển thị dense hits và sparse hits riêng.

## 9. Implement hybrid merge

Implement RRF và dedupe:

```python
def hybrid_merge(dense_hits: list[SearchHit], sparse_hits: list[SearchHit]) -> list[SearchHit]:
    return reciprocal_rank_fusion([dense_hits, sparse_hits], k=60)
```

Test:

- Nếu cùng chunk xuất hiện ở dense và sparse, output chỉ có một chunk.
- Chunk đứng cao ở cả hai list phải lên top.
- Không mất metadata citation.

## 10. Implement reranker

Tạo interface:

```python
class Reranker(Protocol):
    async def rerank(self, query: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]:
        ...
```

Bạn có thể dùng:

- Managed rerank API.
- Local cross-encoder.
- Fake reranker để test wiring, nhưng eval report phải ghi rõ.

Acceptance:

- Có config bật/tắt reranker.
- Nếu reranker timeout, fallback về hybrid hits.
- Trace ghi `rerank_ms`, `reranker_model`, `fallback`.

## 11. Implement generator và citation validator

Context format:

```text
[S1] HR Policy 2026, page 3
Nhân viên full-time có 12 ngày nghỉ phép năm.

[S2] Leave Procedure, page 5
Đơn xin nghỉ cần quản lý trực tiếp phê duyệt.
```

Generator behavior:

- Chỉ trả lời từ context.
- Không đủ context thì trả no-answer.
- Mọi fact cụ thể phải có citation.

Validator:

- Extract `[S\d+]`.
- Check cited source nằm trong context.
- Map citation về `chunk_id`.
- Nếu invalid, retry một lần hoặc trả status `citation_invalid`.

Acceptance:

- Answer có citation hợp lệ.
- LLM cite `[S99]` bị reject.
- Query ngoài tài liệu trả "Không đủ thông tin trong tài liệu được cung cấp."

## 12. Implement query service

Flow trong một function orchestration:

```python
async def answer(request: QueryRequest, user: AuthContext) -> QueryResponse:
    trace = PipelineTrace()

    with trace.span("embed_query"):
        query_vector = await embeddings.embed_query(request.question)

    with trace.span("dense_search"):
        dense_hits = await dense_search(query_vector, user, settings.dense_top_k)

    with trace.span("sparse_search"):
        sparse_hits = await sparse_search(request.question, user, settings.sparse_top_k)

    with trace.span("rrf"):
        hybrid_hits = reciprocal_rank_fusion([dense_hits, sparse_hits])

    with trace.span("rerank"):
        reranked_hits = await reranker.rerank(request.question, hybrid_hits[:50], settings.rerank_top_n)

    context_hits = reranked_hits[: settings.context_top_k]
    if not context_hits:
        return no_context_response(trace)

    with trace.span("generation"):
        answer, usage = await generator.generate(request.question, context_hits)

    with trace.span("citation_validation"):
        citations = validate_and_map_citations(answer, context_hits)

    return build_response(answer, citations, trace, usage)
```

Acceptance:

- Query response có `trace_id`.
- Trace lưu đủ dense/sparse/reranked/context IDs.
- Latency total bằng tổng stage tương đối hợp lý.

## 13. Implement simple UI

UI tối thiểu gồm 4 vùng:

- Upload/Documents.
- Chat.
- Citations/Retrieved chunks.
- Trace/Eval.

Acceptance:

- Upload file từ UI.
- Hỏi câu hỏi và thấy answer.
- Click citation thấy chunk preview.
- Xem latency/token/cost.
- Chạy eval hoặc xem eval run gần nhất.

Không cần landing page. Màn hình đầu tiên nên là tool dùng được.

## 14. Implement eval runner

Endpoint:

```text
POST /eval/run
GET /eval/runs/{run_id}
```

Eval runner:

```text
load golden_set.jsonl
for each question:
  call query pipeline with eval mode
  record retrieved top_k
  compare expected_chunk_ids
  check citations
  track latency/token/cost
write report markdown/json
```

Metrics:

- Hit@5.
- Recall@5.
- MRR@10.
- Citation correctness.
- No-answer accuracy.
- p50/p95 latency.
- Average token/cost.

Acceptance:

- Có report trong `reports/eval-report.md`.
- So sánh 3 config: vector-only, hybrid, hybrid-rerank.
- Có ít nhất 10 failure cases hoặc toàn bộ failures nếu ít hơn.

## 15. Security tests

Tạo test cases:

```text
test_employee_cannot_read_finance_chunk
test_tenant_a_cannot_read_tenant_b_chunk
test_deleted_document_is_not_retrieved
test_client_cannot_override_tenant_id
test_invalid_citation_is_rejected
test_no_context_returns_no_answer
```

Acceptance:

- Tests chạy trong CI hoặc ít nhất bằng `pytest`.
- README ghi cách chạy test.

## 16. Docker và local run

Tạo `.env.example`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.

Lệnh README phải chạy được:

```bash
cp .env.example .env
docker compose up --build
```

Sau đó:

```bash
curl http://localhost:8000/health
open http://localhost:3000
```

Acceptance:

- Clean checkout chạy được nếu có API key hợp lệ.
- Nếu thiếu API key, app báo lỗi cấu hình rõ ràng.
- Logs có `trace_id`.

## 17. README cuối cùng

README phải trả lời:

- App giải quyết bài toán gì?
- Kiến trúc thế nào?
- Cách chạy local?
- Cách ingest data?
- Cách query?
- Cách chạy eval?
- Kết quả eval hiện tại?
- Trade-off chính là gì?
- Security/ACL xử lý ra sao?
- Observability có gì?
- Dùng production được không? Điều kiện gì?

## 18. Rubric tự chấm

| Hạng mục | Điểm tối đa | Tiêu chí |
|---|---:|---|
| Ingestion | 15 | Parse/chunk/embed/index có metadata và error handling |
| Retrieval | 20 | Dense + lexical + RRF + rerank + ACL |
| Generation/citation | 15 | Prompt tốt, citation validator, no-answer |
| Observability | 10 | Trace latency/token/cost theo stage |
| Eval | 15 | Golden set, metrics, config comparison, error analysis |
| API/UI | 10 | API rõ, UI dùng được |
| Docker/README | 10 | Chạy được, document đầy đủ |
| Production readiness | 5 | Trả lời điều kiện production cụ thể |

Tổng: 100 điểm.

## 19. Câu hỏi bắt buộc sau khi làm

Trả lời ngắn trong README hoặc report:

1. Config nào tốt nhất: vector-only, hybrid hay hybrid-rerank? Vì sao?
2. Failure lớn nhất hiện tại đến từ parser, chunking, retrieval, rerank hay generation?
3. Nếu traffic tăng 10 lần, bottleneck đầu tiên là gì?
4. Nếu dữ liệu có PII, cần thay đổi logging thế nào?
5. Nếu đổi embedding model, bạn reindex và rollback ra sao?
6. Nếu user báo citation sai, bạn debug bằng trace như thế nào?
7. Dùng được trong production không? Nếu có thì trong phạm vi và điều kiện nào?

## 20. Stretch goals

Làm thêm nếu còn thời gian:

- Streaming response.
- Query rewrite hoặc multi-query retrieval.
- Prompt injection detector đơn giản cho retrieved chunks.
- Admin screen để switch active index version.
- Blue/green reindex.
- OpenTelemetry trace export.
- Langfuse/LangSmith tracing.
- CI eval smoke test chạy trên 5-10 câu golden set.
- Deployment lên một VM hoặc Kubernetes namespace nhỏ.
