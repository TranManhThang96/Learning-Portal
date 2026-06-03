# Day 31: RAG Architecture

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Giải thích RAG là gì, vì sao khác chatbot gọi LLM trực tiếp.
- Thiết kế được hai pipeline chính: indexing pipeline và query pipeline.
- Hiểu vai trò của document loader, parser, chunker, embedding model, Vector DB, retriever, reranker, context builder, generator, citation và feedback loop.
- Biết thiết kế metadata, ACL, document versioning, index versioning và delete/reindex path.
- Đặt được latency budget, cost budget, quality metric và monitoring cho từng stage.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

RAG = Retrieval + Generation. Thay vì nhồi toàn bộ knowledge vào prompt hoặc fine-tune model chỉ để nhớ facts, hệ thống sẽ retrieve các đoạn tài liệu liên quan từ source of truth, đưa chúng vào context, rồi yêu cầu LLM trả lời dựa trên context đó.

Production RAG không phải `embed -> vector search -> ask LLM`. Nó là một data system có ingestion, parsing, chunking, metadata, permission filtering, hybrid retrieval, reranking, citation, evaluation, monitoring, delete/reindex workflow và rollback. Nếu không đo retrieval quality và không validate citation, hệ thống chỉ là chatbot có thêm search, chưa phải production RAG đáng tin.

## 1. Bài Này Nằm Ở Đâu Trong Lộ Trình

Day 25 đã giúp bạn phân biệt khi nào dùng RAG, fine-tune, tool calling hoặc prompt-only. Day 31 mở Phase 5: Production RAG. Từ Day 31 đến Day 40, mục tiêu là build được một RAG system có retrieval tốt, evaluation rõ, citation, monitoring và khả năng mở rộng.

```text
Day 25-30: quyết định RAG/fine-tune/local LLM/deploy model
Day 31: RAG architecture tổng thể
Day 32: embedding models và benchmark tiếng Việt
Day 33: Vector DB
Day 34: chunking strategies
Day 35: metadata, citation, permission-aware RAG
Day 36-39: hybrid search, reranking, advanced RAG, RAG evaluation
Day 40: mini project production RAG system
```

Kỹ năng chính của Day 31 là nhìn RAG như một distributed system có read path, write path, indexing state, query trace và quality regression test.

## 2. RAG Giải Quyết Vấn Đề Gì

LLM giỏi language reasoning nhưng yếu ở các điểm production sau:

- Không biết private data của công ty.
- Không biết facts mới sau thời điểm training.
- Có thể hallucinate khi thiếu evidence.
- Không tự có citation đáng tin.
- Không tự enforce permission, tenant boundary hoặc data retention.
- Không có guarantee rằng câu trả lời đến từ source of truth hiện tại.

RAG đưa knowledge vào runtime:

```text
User question
  -> retrieve relevant chunks from trusted corpus
  -> build grounded context
  -> generate answer from context
  -> return answer + citation + trace
```

Map về tư duy Senior Software Engineer:

| RAG concept | SE analogy | Câu hỏi production |
|---|---|---|
| Document corpus | Source of truth / data lake | Dữ liệu có owner, version, retention không? |
| Chunk | Searchable record | Record này có đủ context và metadata không? |
| Embedding | Semantic index key | Model/version nào tạo ra vector này? |
| Vector DB | Search index | Có backup, replica, filter, metric không? |
| Retriever | Query engine | Có enforce tenant/ACL trước khi trả kết quả không? |
| Reranker | Ranking service | Có đáng latency/cost không? |
| Context builder | Response assembler | Có token budget và dedupe không? |
| Citation | Audit trail | Citation có map về source thật không? |
| Eval set | Regression test suite | Thay chunking/model có làm quality giảm không? |
| Trace | Distributed tracing | Sai ở stage nào: retrieval, rerank hay generation? |

## 3. Architecture Tổng Quan

Một RAG system production nên tách bốn path:

- Indexing path: đưa document vào search index.
- Query path: trả lời người dùng theo quyền truy cập.
- Evaluation path: đo chất lượng offline/online.
- Admin path: reindex, delete, rollback, inspect trace.

Diagram tổng thể:

```text
                         +----------------------+
                         |  Document Sources    |
                         |  PDF/MD/HTML/DB/API  |
                         +----------+-----------+
                                    |
                         Indexing Pipeline
                                    |
        +---------+  +--------+  +---------+  +----------+  +-----------+
        | Loader  -> | Parser -> | Cleaner -> | Chunker  -> | Metadata  |
        +---------+  +--------+  +---------+  +----------+  | Enricher  |
                                                            +-----+-----+
                                                                  |
                                                        +---------v---------+
                                                        | Embedding Service |
                                                        +---------+---------+
                                                                  |
                                                        +---------v---------+
                                                        | Vector DB/Search  |
                                                        | index + metadata  |
                                                        +---------+---------+
                                                                  |
User -> API/Auth -> Query Normalizer -> Retriever -> ACL Filter -> Reranker
                                                                  |
                                                        +---------v---------+
                                                        | Context Builder   |
                                                        +---------+---------+
                                                                  |
                                                        +---------v---------+
                                                        | LLM Generator     |
                                                        +---------+---------+
                                                                  |
                                                        +---------v---------+
                                                        | Citation Validator|
                                                        +---------+---------+
                                                                  |
                                                         Answer + Sources
                                                                  |
                                                       Feedback + Monitoring
```

Nguyên tắc quan trọng: indexing pipeline và query pipeline phải tách nhau. Nếu bạn trộn mọi thứ trong một script, khi câu trả lời sai sẽ rất khó biết lỗi đến từ parser, chunker, embedding, retriever, reranker, prompt hay model.

## 4. Indexing Pipeline Step By Step

Indexing pipeline biến raw document thành searchable chunks.

```text
raw document
  -> load
  -> parse
  -> clean
  -> split into chunks
  -> enrich metadata
  -> embed
  -> upsert into index
  -> publish index version
```

### Step 1: Document Loader

Loader chịu trách nhiệm lấy dữ liệu từ nguồn thật:

- File: Markdown, PDF, HTML, DOCX, CSV.
- SaaS: Google Drive, Notion, Confluence, SharePoint.
- Database: policy table, support article, product catalog.
- API: CMS, ticketing system, internal docs service.

Production loader cần xử lý:

- Incremental sync thay vì full import mọi lần.
- Document bị xóa hoặc revoke permission.
- Retry có backoff khi source API lỗi.
- Idempotency để job chạy lại không tạo duplicate.
- Source checksum hoặc `text_hash` để bỏ qua document không đổi.
- PII/secret scanning nếu dữ liệu nhạy cảm.

### Step 2: Parser Và Cleaner

Parser chuyển file format thành text có structure. Cleaner loại bỏ noise nhưng không làm mất semantic signal.

Ví dụ cần giữ:

- Heading, title, section path.
- Table caption và row/column quan trọng.
- Code block language.
- Page number hoặc clause number cho citation.
- Link gốc và timestamp.

Ví dụ nên loại bỏ:

- Header/footer lặp lại ở mỗi trang PDF.
- Menu/sidebar HTML.
- Tracking text, cookie banner.
- Multiple whitespace không có nghĩa.

Sai lầm phổ biến: convert PDF thành text phẳng rồi chunk theo 800 token. Với policy/legal/technical docs, heading và clause number là bằng chứng quan trọng cho retrieval và citation.

### Step 3: Chunker

Chunk là đơn vị retrieve. Chunk quá nhỏ thì thiếu context; chunk quá lớn thì retrieval nhiễu và tốn token.

Chiến lược bắt đầu thực dụng:

- Markdown/HTML: chunk theo heading, giới hạn 300-800 tokens, overlap 50-120 tokens.
- PDF policy/legal: chunk theo section/clause, giữ page number.
- Code/docs kỹ thuật: chunk theo function/class/heading, giữ path.
- FAQ: mỗi Q&A là một chunk hoặc một group nhỏ.
- Table: convert thành text có header row, không cắt giữa table nếu table ngắn.

Metadata tối thiểu cho mỗi chunk:

```text
chunk_id
document_id
document_title
source_uri
source_type
tenant_id
acl_tags
document_version
index_version
embedding_model
chunking_strategy
chunk_index
section_path
page_number
text_hash
created_at
updated_at
```

### Step 4: Embedding

Embedding model biến chunk text thành vector. Query cũng được embed vào cùng vector space để tìm similarity.

Điều cần version:

- Model name và revision.
- Vector dimension.
- Normalization setting.
- Text preprocessing.
- Chunking strategy.

Khi đổi embedding model, score distribution thay đổi. Không nên upsert vector mới lẫn với vector cũ rồi so sánh như cùng một index. Cách an toàn là tạo index version mới, chạy eval, sau đó switch traffic hoặc canary.

### Step 5: Upsert Vector DB / Search Index

Index cần lưu cả vector và metadata. Với enterprise RAG, metadata filtering quan trọng ngang embedding.

Upsert cần idempotent:

```text
chunk_id = hash(tenant_id, document_id, document_version, chunk_index, text_hash)
```

Khi document bị xóa hoặc user mất quyền, phải có delete/revoke path. Không thể chỉ update prompt để "đừng trả lời tài liệu này".

## 5. Query Pipeline Step By Step

Query pipeline nhận câu hỏi và trả về answer có source.

```text
query
  -> request validation
  -> auth + tenant context
  -> normalize/rewrite optional
  -> retrieve candidates
  -> filter by metadata + ACL
  -> rerank candidates
  -> build context
  -> generate answer
  -> validate citations
  -> log trace + feedback hook
```

### Step 1: Auth Và Tenant Context

Trước retrieval, backend phải biết user thuộc tenant nào, role nào, được đọc source nào. ACL phải được enforce ở retriever/search layer bằng metadata filter hoặc permission join, không giao cho LLM tự quyết.

Ví dụ:

```text
tenant_id = "acme"
allowed_acl_tags = ["employee", "engineering", "vn-office"]
source_types = ["policy", "runbook"]
```

### Step 2: Query Normalizer / Rewriter

Normalizer xử lý typo nhẹ, lowercase nếu phù hợp, chuẩn hóa mã sản phẩm hoặc acronym. Query rewriting có thể biến câu hỏi mơ hồ thành câu hỏi rõ hơn hoặc tạo nhiều biến thể.

Trade-off:

- Query rewrite có thể tăng recall.
- Nhưng thêm latency/cost và có nguy cơ làm lệch ý user.
- Với production, rewrite output nên được log và có timeout riêng.

### Step 3: Retriever

Retriever lấy candidates. Các kiểu retrieval:

- Dense vector search: tốt cho semantic similarity, synonym, natural language.
- BM25/keyword search: tốt cho exact term, mã lỗi, tên sản phẩm, acronym, legal clause.
- Hybrid search: kết hợp dense + sparse, thường là baseline tốt cho enterprise docs.
- Metadata filtering: tenant, permission, product, language, time range.
- Multi-query retrieval: chạy nhiều query variants rồi merge.

Pattern phổ biến:

```text
dense top 50
+ BM25 top 50
-> merge + dedupe
-> ACL filter
-> rerank top 50
-> select top 5-10 for context
```

### Step 4: Reranker

Embedding similarity nhanh nhưng ranking chưa chắc tốt. Reranker nhận `(query, candidate chunk)` và sắp xếp lại. Cross-encoder/reranker thường chính xác hơn vector similarity nhưng chậm hơn.

Nên dùng reranker khi:

- Citation quality quan trọng.
- Corpus nhiều documents giống nhau.
- Query dài hoặc ambiguous.
- Có requirement giảm hallucination.

Có thể bỏ reranker khi:

- Corpus nhỏ, sạch, search đã rất tốt.
- Latency cực chặt.
- Eval chứng minh reranker không cải thiện đáng kể.

### Step 5: Context Builder

Context builder quyết định đưa gì vào prompt. Đây là nơi nhiều RAG system fail vì nhét quá nhiều context nhiễu.

Rule production:

- Có token budget rõ ràng.
- Dedupe chunks gần giống nhau.
- Giữ title, section, source id gần text.
- Ưu tiên chunk score cao, source đáng tin, document mới hơn nếu phù hợp.
- Không cắt giữa sentence/table/code block nếu tránh được.
- Chỉ cho model cite source id đã đưa vào context.

Context format nên machine-check được:

```text
<source id="S1" document_id="policy-123" section="Nghỉ phép" page="4">
Nhân viên cần gửi yêu cầu nghỉ phép trước ít nhất 3 ngày làm việc...
</source>
```

### Step 6: Generator Và Citation

Generator dùng LLM để trả lời từ context. Prompt cần rõ contract:

```text
Bạn là assistant trả lời dựa trên context.
Chỉ dùng thông tin trong context.
Nếu context không đủ, nói rõ "Tôi không có đủ thông tin trong tài liệu được cung cấp".
Mỗi claim quan trọng phải có citation dạng [S1], [S2].
Không tạo citation ngoài danh sách source đã cung cấp.
```

Prompt không đủ. Backend vẫn cần citation validator:

- Citation id trong answer có nằm trong context không?
- Mỗi citation có map về chunk/document thật không?
- Có claim quan trọng nào không citation không?
- Answer có nói quá context không?
- Nếu không có context đủ, model có từ chối đúng không?

## 6. Feedback Loop Và Evaluation

RAG không thể cải thiện nếu không có eval. Có hai lớp:

- Offline evaluation: chạy golden set trước khi deploy thay đổi.
- Online evaluation: thu feedback và production telemetry.

Golden set nên có schema:

```json
{
  "query": "Nhân viên thử việc có được nghỉ phép năm không?",
  "expected_relevant_chunk_ids": ["policy-leave-v3-004"],
  "expected_answer_facts": [
    "Có hoặc không theo policy hiện hành",
    "Điều kiện áp dụng",
    "Nguồn policy"
  ],
  "must_not_include": ["quy định đã hết hiệu lực"],
  "category": "hr_policy",
  "difficulty": "medium"
}
```

Metric retrieval:

- Hit@K: chunk đúng có nằm trong top K không.
- Recall@K: lấy được bao nhiêu relevant chunks.
- MRR@K: relevant chunk đầu tiên đứng cao không.
- nDCG@K: ranking có đúng thứ tự relevance không.

Metric generation:

- Faithfulness: answer có bám context không.
- Citation correctness: citation có đúng source không.
- Answer completeness: trả lời đủ ý cần thiết không.
- Refusal correctness: khi thiếu context có biết nói không đủ thông tin không.

Metric product/ops:

- p50/p95/p99 latency.
- Cost/request và token/request.
- Retrieval empty rate.
- Low confidence rate.
- Citation click-through.
- Thumbs up/down.
- Escalation rate.
- Index freshness lag.

## 7. Trade-off Quan Trọng

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| Vector-only retrieval | Corpus sạch, semantic FAQ, prototype | Nhiều acronym, mã lỗi, legal term | Dễ miss exact term |
| BM25-only | Keyword-heavy, log/code/error search | Câu hỏi tự nhiên, nhiều synonym | Baseline rẻ và dễ debug |
| Hybrid retrieval | Enterprise docs, tiếng Việt + English mix | Prototype rất nhỏ | Thường là default tốt |
| No reranker | Latency rất chặt, corpus nhỏ | Citation/quality quan trọng | Cần eval chứng minh đủ tốt |
| Reranker | Cần top context chính xác | QPS cao, p95 rất chặt | Rerank top 20-100, có timeout |
| Fixed chunk size | Bắt đầu nhanh | Docs có structure phức tạp | Dễ cắt mất context |
| Structure-aware chunking | Markdown/PDF/legal/code docs | Ingestion cần cực đơn giản | Parser phức tạp hơn |
| Sync indexing | Dataset nhỏ, admin manual | Docs update liên tục | Dễ timeout và khó retry |
| Async indexing | Corpus lớn, update thường xuyên | Cần immediate consistency | Cần job status và retry |
| Managed vector DB | Muốn giảm ops | Data residency/self-host bắt buộc | Cost tăng theo scale |
| Self-host vector DB | Privacy/cost control | Team thiếu ops | Cần backup, tuning, monitoring |

## 8. Performance Và Cost

Latency tổng:

```text
auth
+ query rewrite optional
+ query embedding
+ vector/BM25 retrieval
+ reranking
+ context building
+ LLM generation
+ citation validation
```

Budget tham khảo cho v1:

| Stage | Budget p95 |
|---|---:|
| Auth / request validation | 20 ms |
| Query embedding | 50-300 ms |
| Vector + metadata search | 20-150 ms |
| BM25 / hybrid merge | 20-100 ms |
| Rerank top 50 | 100-800 ms |
| Context build | 20 ms |
| LLM first token | 800-2500 ms |
| Total non-streaming | 3-6 s |

Vector storage rough estimate:

```text
raw_vector_storage = num_chunks * dimensions * 4 bytes
```

| Chunks | Dim | Raw vector |
|---:|---:|---:|
| 1M | 768 | ~3.1 GB |
| 1M | 1024 | ~4.1 GB |
| 1M | 1536 | ~6.1 GB |
| 1M | 3072 | ~12.3 GB |

Thực tế cần cộng index overhead, metadata, replicas, backups và write-ahead logs. Với RAG lớn, chunk count và metadata cardinality có thể quan trọng không kém model size.

Tối ưu thường gặp:

- Cache query embedding cho query lặp lại.
- Cache retrieval result ngắn hạn theo tenant + normalized query nếu data không quá realtime.
- Rerank ít candidates hơn sau khi đã tune retrieval.
- Giới hạn context bằng token budget và dedupe.
- Stream answer để giảm perceived latency.
- Dùng smaller/faster generator cho câu hỏi đơn giản.
- Tách online query path khỏi offline indexing jobs.

## 9. Code Example Gần Production

Ví dụ dưới đây không phụ thuộc vendor cụ thể. Nó thể hiện boundary quan trọng: retriever trả candidates, context builder tạo source ids, generator chỉ được cite source ids đó, validator kiểm citation.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import re
import time
import uuid


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str
    allowed_acl_tags: set[str]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Source:
    source_id: str
    chunk_id: str
    document_id: str
    title: str
    text: str
    score: float


class Retriever(Protocol):
    def search(self, query: str, user: UserContext, top_k: int) -> list[RetrievedChunk]:
        ...


class Generator(Protocol):
    def answer(self, question: str, context: str, source_ids: list[str]) -> str:
        ...


def is_allowed(chunk: Chunk, user: UserContext) -> bool:
    metadata = chunk.metadata
    if metadata.get("tenant_id") != user.tenant_id:
        return False
    chunk_acl = set(metadata.get("acl_tags", []))
    return bool(chunk_acl & user.allowed_acl_tags)


def build_context(results: list[RetrievedChunk], max_chars: int = 8000) -> tuple[str, list[Source]]:
    parts: list[str] = []
    sources: list[Source] = []
    used_chars = 0
    seen_chunk_ids: set[str] = set()

    for item in results:
        chunk = item.chunk
        if chunk.chunk_id in seen_chunk_ids:
            continue
        source_id = f"S{len(sources) + 1}"
        section = chunk.metadata.get("section_path", "")
        page = chunk.metadata.get("page_number", "")
        block = (
            f'<source id="{source_id}" document_id="{chunk.document_id}" '
            f'title="{chunk.title}" section="{section}" page="{page}">\n'
            f"{chunk.text.strip()}\n"
            "</source>"
        )
        if used_chars + len(block) > max_chars:
            break
        parts.append(block)
        sources.append(
            Source(
                source_id=source_id,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                text=chunk.text,
                score=item.score,
            )
        )
        seen_chunk_ids.add(chunk.chunk_id)
        used_chars += len(block)

    return "\n\n".join(parts), sources


def validate_citations(answer: str, sources: list[Source]) -> list[str]:
    allowed = {source.source_id for source in sources}
    cited = set(re.findall(r"\[(S\d+)\]", answer))
    invalid = sorted(cited - allowed)
    if invalid:
        return [f"Invalid citations: {', '.join(invalid)}"]
    if sources and not cited:
        return ["Answer has context sources but no citation."]
    return []


def answer_rag(
    question: str,
    user: UserContext,
    retriever: Retriever,
    generator: Generator,
    retrieve_top_k: int = 50,
    context_max_chars: int = 8000,
) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()

    candidates = retriever.search(question, user, top_k=retrieve_top_k)
    allowed_candidates = [item for item in candidates if is_allowed(item.chunk, user)]
    context, sources = build_context(allowed_candidates, max_chars=context_max_chars)

    if not sources:
        return {
            "trace_id": trace_id,
            "answer": "Tôi không có đủ thông tin trong tài liệu được phép truy cập.",
            "sources": [],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    answer = generator.answer(question, context, [source.source_id for source in sources])
    citation_errors = validate_citations(answer, sources)
    if citation_errors:
        answer = "Tôi không thể tạo câu trả lời có citation hợp lệ từ tài liệu được cung cấp."

    return {
        "trace_id": trace_id,
        "answer": answer,
        "sources": [source.__dict__ for source in sources],
        "citation_errors": citation_errors,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }
```

Đây vẫn chưa phải app hoàn chỉnh. Khi đưa vào production, bạn cần thêm request schema, auth thật, timeout, retry, structured logging, rate limit, metrics, tracing, secret handling và test suite.

## 10. Dùng Được Trong Production Không?

Có, RAG là pattern production rất thực tế cho knowledge assistant, support bot, policy Q&A, developer assistant và search có natural language. Nhưng chỉ dùng được khi thỏa các điều kiện tối thiểu sau:

- Retrieval permission-safe: tenant/ACL được enforce trước khi context vào prompt.
- Citation validate được: source id do backend sinh, không tin citation model tự bịa.
- Evaluation rõ: có golden set, retrieval metrics, generation metrics và regression gate trước deploy.
- Observability đủ sâu: trace từng stage, latency, token, cost, retrieval scores, reranker scores, citation errors.
- Index lifecycle đầy đủ: incremental indexing, delete/revoke, reindex, versioning và rollback.
- Security review: chống prompt injection trong retrieved documents, không log PII/secret, có data retention policy.
- Performance budget: p95 latency, cost/request và capacity plan đạt yêu cầu sản phẩm.
- Human fallback: với domain rủi ro cao, câu trả lời phải có escalation hoặc human review.

Nếu thiếu ACL hoặc citation validation, không nên dùng cho dữ liệu nội bộ nhạy cảm. Nếu thiếu eval, chỉ nên coi là prototype. Nếu thiếu monitoring, bạn sẽ không biết hệ thống sai ở đâu khi người dùng báo lỗi.

## 11. Checklist Học Xong

- [ ] Vẽ được indexing pipeline và query pipeline.
- [ ] Liệt kê được component chính của RAG architecture.
- [ ] Thiết kế được chunk schema có metadata, ACL và version.
- [ ] Giải thích được dense retrieval, BM25, hybrid retrieval và reranker.
- [ ] Thiết kế được context builder có token budget và dedupe.
- [ ] Có citation rule và citation validation rule.
- [ ] Có eval set tối thiểu 10 query.
- [ ] Có latency budget và trace schema.
- [ ] Liệt kê được production risks: ACL leak, stale index, prompt injection, hallucination, cost spike.
- [ ] Trả lời được hệ thống này production được không và thiếu điều kiện gì.

