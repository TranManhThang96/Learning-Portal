# Day 38: Advanced RAG Patterns Production

## 1. Bài này nằm ở đâu trong Production RAG?

Từ Day 31 đến Day 37, bạn đã có các khối nền tảng:

```text
Documents
  -> parse
  -> chunk
  -> embed
  -> vector DB / sparse index

User query
  -> hybrid search
  -> rerank
  -> build context
  -> answer with citations
```

Day 38 trả lời câu hỏi: khi baseline hybrid search + reranking vẫn fail, nên thêm pattern nào, thêm ở đâu, và làm sao chứng minh nó đáng giá?

Điểm quan trọng nhất: advanced RAG là công cụ xử lý lỗi cụ thể, không phải danh sách feature phải bật hết. Pipeline production tốt thường bắt đầu bằng:

```text
query normalization
  -> hybrid search, dense + BM25
  -> RRF merge
  -> reranking
  -> context building with citation
  -> generation
  -> evaluation and trace
```

Sau đó mới thêm có chọn lọc:

1. Query rewriting cho query ngắn, sai chính tả, thiếu context chat, synonym hoặc acronym.
2. Contextual retrieval cho chunk bị mất section/title/table context.
3. Multi-query khi corpus có nhiều cách diễn đạt và Recall@K còn thấp.
4. Decomposition hoặc multi-hop khi câu hỏi thật sự cần nhiều bước.
5. Corrective RAG hoặc agentic RAG khi hệ thống cần tự phát hiện retrieval yếu và thử lại.
6. GraphRAG khi câu hỏi liên quan entity/relation/global summary, không phải FAQ thông thường.

## 2. Taxonomy lỗi trước khi chọn pattern

Không chọn pattern bằng cảm giác. Hãy phân loại lỗi trên golden set:

| Loại lỗi | Dấu hiệu | Pattern phù hợp |
|---|---|---|
| Query quá ngắn | "429 là sao", "policy refund?" | Query rewriting, multi-query |
| Query sai chính tả/không dấu | "nghi phep nam dc bao nhieu ngay" | Query normalization, query rewriting |
| Query dùng synonym/acronym | "SLA", "PTO", "churn", "chargeback" | Query rewriting, hybrid search, glossary |
| Query cần chat history | "nó có áp dụng cho gói Enterprise không?" | Conversational query rewriting |
| Query cần so sánh | "Pro khác Enterprise về refund thế nào?" | Query decomposition, multi-hop RAG |
| Chunk thiếu ngữ cảnh | Chunk chỉ ghi "thời hạn là 7 ngày" | Contextual retrieval, parent-child retrieval |
| Retrieval trả về chunk gần nhưng sai | Top chunks không answerable | Reranking, corrective RAG, better qrels |
| Cần hiểu quan hệ entity | "A liên quan B qua dự án nào?" | GraphRAG hoặc graph-assisted retrieval |
| Cần câu hỏi tổng quan trên corpus lớn | "Các chủ đề chính trong tài liệu này là gì?" | GraphRAG community summary |

Nếu lỗi đang nằm ở ACL, document freshness, citation hoặc chunking quá tệ, advanced prompt thường không cứu được. Sửa dữ liệu, schema và index lifecycle trước.

## 3. Baseline production trước khi advanced

Baseline tối thiểu đáng tin:

```text
1. Normalize query
2. Dense retrieval top 50
3. BM25/sparse retrieval top 50
4. Merge bằng Reciprocal Rank Fusion
5. Apply tenant/ACL/deleted/index_version filters trong retriever
6. Rerank top 50 xuống top 5-10
7. Build context có citation metadata
8. Generate answer chỉ dựa trên retrieved evidence
9. Log trace và metrics
```

Trước khi thêm pattern, cần có:

- Golden set 30-100 câu hỏi có expected documents hoặc expected answer.
- Query tags: `short`, `keyword`, `synonym`, `multi_hop`, `comparison`, `table`, `policy`, `security_sensitive`.
- Metrics: Recall@5, Recall@10, MRR@10, nDCG@10, context precision, citation correctness, p50/p95 latency, token cost.
- Baseline report để so sánh before/after.

Không có baseline thì mọi advanced pattern chỉ là cảm giác.

## 4. Query rewriting

Query rewriting biến câu hỏi của user thành query rõ hơn cho retrieval, nhưng không được thay đổi intent.

Ví dụ:

```text
Original: "429 là sao?"
Rewritten: "HTTP 429 Too Many Requests rate limit API request per minute"

Original: "nó có áp dụng cho enterprise không?"
Chat context: user đang hỏi refund policy
Rewritten: "Refund policy có áp dụng cho gói Enterprise không?"
```

Các dạng rewriting phổ biến:

| Dạng | Mục đích | Ví dụ |
|---|---|---|
| Normalization | Sửa không dấu, typo, casing | "nghi phep" -> "nghỉ phép" |
| Expansion | Thêm synonym/acronym | "PTO" -> "paid time off, nghỉ phép" |
| Conversational rewrite | Bổ sung chat context | "nó" -> "refund policy gói Pro" |
| Domain rewrite | Dùng thuật ngữ corpus | "bị chặn request" -> "rate limit HTTP 429" |

Rule production:

- Luôn search cả original query và rewritten query khi query có rủi ro drift.
- Rewriter chỉ tạo query retrieval, không trả lời user.
- Output phải có schema rõ ràng, ví dụ JSON.
- Có giới hạn độ dài và số lượng terms.
- Log original, rewritten, rewrite reason và risk flags.
- Không đưa instruction độc hại từ user vào system prompt của rewriter.

Prompt contract mẫu:

```text
You rewrite the user question for document retrieval.
Do not answer the question.
Preserve the original intent.
Use Vietnamese with necessary English technical terms.
Return JSON only:
{
  "rewritten_query": "...",
  "reason": "...",
  "risk_flags": ["ambiguous" | "prompt_injection" | "exact_lookup" | "none"]
}
```

Khi không nên rewrite:

- Query là mã lỗi, SKU, order id, invoice id, exact phrase pháp lý.
- User yêu cầu trích nguyên văn một điều khoản.
- Rewriter không đủ context để disambiguate.

Với exact lookup, giữ nguyên query là tín hiệu quan trọng cho BM25.

## 5. Multi-query retrieval

Multi-query tạo nhiều biến thể của cùng intent, retrieve từng biến thể rồi merge kết quả.

```text
User query
  -> q1 original
  -> q2 rewritten
  -> q3 synonym variant
  -> q4 domain terminology variant
  -> retrieve each query
  -> RRF merge
  -> rerank
```

Pattern này hữu ích khi corpus có nhiều cách viết:

- Tài liệu tiếng Việt + English mix.
- Cùng khái niệm có nhiều synonym.
- Tài liệu do nhiều team viết, wording không thống nhất.
- Query của user ngắn nhưng intent vẫn rõ.

Rủi ro:

- Tăng số retrieval calls.
- Tăng noise nếu variants đi xa khỏi intent.
- Tăng latency và context pollution.
- Debug khó nếu không log từng variant.

Reciprocal Rank Fusion, RRF, thường là cách merge đơn giản và ổn:

```python
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    text: str
    source_uri: str
    rank: int
    score: float
    retriever: str
    query_variant: str
    metadata: dict


def rrf_merge(result_lists: list[list[Candidate]], k: int = 60) -> list[Candidate]:
    scores: dict[str, float] = defaultdict(float)
    best: dict[str, Candidate] = {}

    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            scores[item.chunk_id] += 1.0 / (k + rank)
            if item.chunk_id not in best or rank < best[item.chunk_id].rank:
                best[item.chunk_id] = item

    merged = sorted(best.values(), key=lambda item: scores[item.chunk_id], reverse=True)
    return [
        Candidate(
            chunk_id=item.chunk_id,
            text=item.text,
            source_uri=item.source_uri,
            rank=index,
            score=scores[item.chunk_id],
            retriever="rrf",
            query_variant=item.query_variant,
            metadata=item.metadata,
        )
        for index, item in enumerate(merged, start=1)
    ]
```

Production guardrail:

- Giới hạn 2-4 variants.
- Dedupe theo normalized query.
- Nếu query chứa ID/code, không sinh biến thể làm mất ID/code.
- Rerank sau khi merge, không đưa thẳng tất cả chunks vào LLM.

## 6. HyDE

HyDE, viết tắt của Hypothetical Document Embeddings, tạo một đoạn tài liệu giả định có thể trả lời câu hỏi, embed đoạn đó, rồi dùng embedding để retrieve tài liệu thật.

```text
query
  -> generate hypothetical answer/document
  -> embed hypothetical document
  -> vector search
  -> retrieve real chunks
  -> answer using real chunks only
```

HyDE có ích khi:

- Query quá ngắn hoặc không giống style trong corpus.
- Corpus viết theo dạng policy/documentation, user hỏi rất casual.
- Dense embedding của câu hỏi ngắn không đủ tín hiệu.

Nhưng HyDE có rủi ro lớn:

- Hypothetical document có thể hallucinate terms sai.
- Có thể kéo retrieval về vùng kiến thức sai.
- Dễ gây hiểu nhầm nếu team dùng HyDE output như evidence.

Rule bắt buộc: HyDE output không bao giờ là citation, không bao giờ là source of truth. Nó chỉ là query artifact.

Không nên dùng HyDE mặc định cho:

- Legal/compliance exact wording.
- Medical/finance high-risk answer.
- Query cần trích điều khoản cụ thể.
- Corpus nhỏ đã retrieval tốt.

## 7. Step-back prompting

Step-back prompting tạo một câu hỏi tổng quát hơn để tìm context nền, sau đó kết hợp với retrieval trực tiếp.

Ví dụ:

```text
Original: "Có được refund sau 10 ngày không?"
Step-back: "Refund policy điều kiện hoàn tiền và thời hạn áp dụng"
```

Pipeline an toàn:

```text
retrieve(original query)
retrieve(step-back query)
merge
rerank
answer with exact evidence
```

Không bỏ retrieval trực tiếp, vì step-back có thể làm mất detail như plan name, date, jurisdiction hoặc version.

Step-back phù hợp với:

- Policy concept.
- Incident troubleshooting từ triệu chứng sang runbook category.
- Câu hỏi cần background trước khi trả lời detail.

Không phù hợp với:

- Lookup theo mã.
- Câu hỏi cần số liệu cụ thể.
- Câu hỏi có exact quote.

## 8. Query decomposition và multi-hop RAG

Query decomposition tách câu hỏi phức tạp thành nhiều subqueries. Multi-hop RAG retrieve và tổng hợp evidence qua nhiều bước.

Ví dụ:

```text
Question: "Chính sách refund gói Pro khác Enterprise thế nào?"

Subquery 1: "Refund policy for Pro plan"
Subquery 2: "Refund policy for Enterprise plan"
Synthesis: compare conditions, time window, exceptions and citations
```

Điểm khác nhau:

- Decomposition là việc tách câu hỏi.
- Multi-hop RAG là pipeline dùng kết quả hop trước để quyết định hop sau hoặc tổng hợp nhiều hop.

Production requirements:

- Mỗi subquery có trace riêng.
- Mỗi claim trong final answer map về source của subquery tương ứng.
- Có giới hạn số subqueries, thường 2-5.
- Có fallback hỏi lại user nếu decomposition mơ hồ.
- Không dùng multi-hop cho FAQ đơn giản.

Sơ đồ:

```text
user question
  -> classify as multi-hop?
  -> decompose into subqueries
  -> retrieve + rerank per subquery
  -> evidence table
  -> synthesize answer
  -> verify citations cover each claim
```

Với production, nhiều hệ thống chỉ cần decomposition dạng deterministic cho comparison query:

```text
"A khác B về X thế nào?"
  -> retrieve X for A
  -> retrieve X for B
  -> compare
```

Không cần agent loop nếu pattern của câu hỏi ổn định.

## 9. Contextual retrieval

Contextual retrieval thêm ngữ cảnh vào chunk ở indexing time để chunk độc lập hơn khi search.

Vấn đề:

```text
Chunk text: "Thời hạn là 7 ngày kể từ ngày mua."
```

Chunk này không nói 7 ngày cho cái gì. Nếu embed nguyên chunk, retrieval rất yếu.

Contextual chunk:

```text
Document: Refund Policy 2026
Section: Gói Pro > Điều kiện hoàn tiền
Summary: Quy định hoàn tiền cho khách hàng gói Pro.
Text: Thời hạn là 7 ngày kể từ ngày mua.
```

Code indexing gần production:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RawChunk:
    document_id: str
    chunk_id: str
    title: str
    section_path: list[str]
    page_start: int | None
    text: str
    metadata: dict


def build_contextual_text(chunk: RawChunk) -> str:
    section = " > ".join(chunk.section_path) if chunk.section_path else "Unknown section"
    page = f"Page: {chunk.page_start}" if chunk.page_start else "Page: unknown"
    return "\n".join(
        [
            f"Document: {chunk.title}",
            f"Section: {section}",
            page,
            "Purpose: Retrieval context only. Use original source text for citation.",
            f"Text: {chunk.text}",
        ]
    )


def build_vector_record(chunk: RawChunk, embedding: list[float], index_version: str) -> dict:
    return {
        "id": f"{chunk.document_id}:{chunk.chunk_id}:{index_version}",
        "text": chunk.text,
        "contextual_text": build_contextual_text(chunk),
        "embedding": embedding,
        "metadata": {
            **chunk.metadata,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "section_path": chunk.section_path,
            "page_start": chunk.page_start,
            "index_version": index_version,
            "contextual_strategy": "title_section_page_v1",
        },
    }
```

Lưu ý quan trọng:

- Embed `contextual_text`, nhưng khi hiển thị citation nên trỏ về `text` và source document thật.
- Nếu context được LLM generate, phải version prompt và reindex khi đổi prompt.
- Context sai có thể làm retrieval sai hàng loạt.
- Context dài làm tăng embedding cost và index size.

Contextual retrieval thường là pattern đáng thử sớm nhất sau hybrid + rerank vì nó cải thiện chất lượng offline, không thêm LLM call vào online path.

## 10. Corrective RAG

Corrective RAG kiểm tra chất lượng retrieved context trước khi answer. Nếu context yếu, hệ thống rewrite/retrieve lại, mở rộng search hoặc hỏi user.

```text
retrieve
  -> grade context quality
  -> if good: answer
  -> if weak: rewrite + retrieve again
  -> if still weak: ask clarification or answer "không đủ thông tin"
```

Grader có thể là:

- Rule-based: không có chunk đủ score, source không đúng tenant, citation thiếu.
- Model-based: LLM đánh giá context có answerable không.
- Hybrid: rule trước, LLM chỉ dùng cho case khó.

Production controls:

- Max retry thường là 1.
- Timeout tổng cho retrieval path.
- Log reason: `low_recall`, `low_rerank_score`, `conflicting_sources`, `no_citation`.
- Không để corrective loop chạy không giới hạn.

Corrective RAG có ích khi user experience quan trọng hơn latency tuyệt đối, ví dụ internal assistant, customer support hoặc analyst workflow. Với API latency chặt, có thể chỉ dùng rule-based fallback.

## 11. Agentic RAG

Agentic RAG cho LLM quyết định gọi retrieval tools nhiều lần, có thể chọn tool khác nhau như vector search, SQL search, web search nội bộ, graph search hoặc code search.

Nên dùng khi task thật sự cần:

- Multi-step reasoning.
- Chọn tool tùy tình huống.
- Kết hợp nhiều data source.
- Lập kế hoạch và verify từng bước.

Không nên dùng agentic RAG cho FAQ đơn giản vì:

- Latency khó dự đoán.
- Cost có worst case cao.
- Debug phức tạp.
- Dễ loop nếu stop condition kém.
- Security surface lớn hơn.

Checklist bắt buộc:

- Tool allowlist.
- Max steps.
- Timeout.
- Cost budget.
- Trace từng tool call.
- Tenant/ACL filter ở tool layer.
- Eval regression theo scenario.
- Human-readable execution trace cho debugging.

Một lựa chọn thực dụng: thay vì agent tự do, dùng orchestrator có state machine rõ ràng:

```text
classify_query
  -> direct_retrieval | comparison_retrieval | troubleshooting_retrieval
  -> fixed steps
  -> answer
```

State machine dễ test hơn agent loop mở.

## 12. GraphRAG overview

GraphRAG xây graph từ corpus:

```text
documents
  -> extract entities and relations
  -> build graph
  -> community detection / summaries
  -> graph search + vector search
  -> answer
```

GraphRAG phù hợp khi câu hỏi liên quan:

- Entity relationship: "Project A liên quan team B qua incident nào?"
- Global summary: "Các chủ đề chính trong tập tài liệu này là gì?"
- Community-level analysis: "Nhóm rủi ro lớn nhất trong contract corpus là gì?"
- Long corpus có nhiều cross-reference.

Không nên dùng GraphRAG nếu bài toán là:

- FAQ hoặc policy lookup đơn giản.
- Corpus nhỏ.
- Tài liệu thay đổi liên tục nhưng chưa có graph update pipeline.
- Team chưa có evaluation cho entity extraction/relation extraction.

Trade-off:

- Build index đắt hơn.
- Update/delete phức tạp hơn.
- Graph extraction có lỗi riêng.
- Cần eval cả graph quality, không chỉ answer quality.
- Có thể phải lưu thêm community summaries và provenance.

GraphRAG trong Day 38 chỉ là overview. Với project Day 40, chỉ nên thêm GraphRAG nếu golden set có nhiều câu hỏi entity/global mà vector + BM25 + rerank không đủ.

## 13. Thiết kế pipeline gần production

Ví dụ dưới đây minh họa orchestration cho retrieval path. Đây không phải framework hoàn chỉnh, nhưng thể hiện các boundary quan trọng: policy, trace, tenant/ACL, query variants, merge, rerank và fallback.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RetrievalPolicy:
    max_query_variants: int = 3
    dense_top_k: int = 50
    sparse_top_k: int = 50
    final_top_k: int = 8
    enable_rewrite: bool = True
    enable_multi_query: bool = False
    timeout_ms: int = 2500


@dataclass(frozen=True)
class SearchRequest:
    query: str
    tenant_id: str
    acl_roles: tuple[str, ...]
    chat_summary: str | None = None
    index_version: str = "active"


@dataclass
class SearchTrace:
    original_query: str
    rewritten_query: str | None = None
    query_variants: list[str] = field(default_factory=list)
    retrieved_count: int = 0
    reranked_count: int = 0
    fallback_used: str | None = None
    latency_ms: int = 0
    warnings: list[str] = field(default_factory=list)


class QueryRewriter(Protocol):
    def rewrite(self, request: SearchRequest) -> str | None:
        ...


class Retriever(Protocol):
    def search(
        self,
        query: str,
        tenant_id: str,
        acl_roles: tuple[str, ...],
        index_version: str,
        top_k: int,
    ) -> list[Candidate]:
        ...


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Candidate], top_k: int) -> list[Candidate]:
        ...


def dedupe_queries(queries: list[str], max_count: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for query in queries:
        normalized = " ".join(query.strip().lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(query.strip())
        if len(output) >= max_count:
            break
    return output


class AdvancedRagRetriever:
    def __init__(
        self,
        dense: Retriever,
        sparse: Retriever,
        reranker: Reranker,
        rewriter: QueryRewriter | None,
        policy: RetrievalPolicy,
    ) -> None:
        self.dense = dense
        self.sparse = sparse
        self.reranker = reranker
        self.rewriter = rewriter
        self.policy = policy

    def retrieve(self, request: SearchRequest) -> tuple[list[Candidate], SearchTrace]:
        started = time.monotonic()
        trace = SearchTrace(original_query=request.query)

        queries = [request.query]
        if self.policy.enable_rewrite and self.rewriter:
            rewritten = self.rewriter.rewrite(request)
            if rewritten and rewritten.strip() != request.query.strip():
                trace.rewritten_query = rewritten
                queries.append(rewritten)

        query_variants = dedupe_queries(queries, self.policy.max_query_variants)
        trace.query_variants = query_variants

        result_lists: list[list[Candidate]] = []
        for query in query_variants:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if elapsed_ms > self.policy.timeout_ms:
                trace.fallback_used = "timeout_before_all_variants"
                break

            result_lists.append(
                self.dense.search(
                    query=query,
                    tenant_id=request.tenant_id,
                    acl_roles=request.acl_roles,
                    index_version=request.index_version,
                    top_k=self.policy.dense_top_k,
                )
            )
            result_lists.append(
                self.sparse.search(
                    query=query,
                    tenant_id=request.tenant_id,
                    acl_roles=request.acl_roles,
                    index_version=request.index_version,
                    top_k=self.policy.sparse_top_k,
                )
            )

        merged = rrf_merge(result_lists)
        trace.retrieved_count = len(merged)

        if not merged:
            trace.warnings.append("no_retrieval_result")
            trace.latency_ms = int((time.monotonic() - started) * 1000)
            return [], trace

        reranked = self.reranker.rerank(
            query=request.query,
            candidates=merged,
            top_k=self.policy.final_top_k,
        )
        trace.reranked_count = len(reranked)
        trace.latency_ms = int((time.monotonic() - started) * 1000)
        return reranked, trace
```

Trong code thật, bạn cần thêm:

- Circuit breaker cho LLM rewriter.
- Cache theo `tenant_id`, `acl_hash`, `index_version`, normalized query.
- Structured logging và distributed tracing.
- Redaction cho logs chứa query nhạy cảm.
- Eval job chạy trước khi bật feature flag.

## 14. Performance và cost trade-off

| Pattern | Online LLM call? | Tăng latency | Tăng cost | Rủi ro chính | Ghi chú |
|---|---:|---:|---:|---|---|
| Query rewriting | Có | Thấp-vừa | Thấp | Drift intent | Cache được |
| Multi-query | Thường có | Vừa-cao | Vừa | Noise, nhiều retrieval calls | Giới hạn variants |
| HyDE | Có | Vừa-cao | Vừa | Hallucinated retrieval anchor | Không dùng làm evidence |
| Step-back | Có | Vừa | Thấp-vừa | Mất detail | Search direct + step-back |
| Decomposition | Có | Cao | Vừa-cao | Sai subquery | Trace từng subquery |
| Contextual retrieval | Offline hoặc indexing time | Không tăng online nhiều | Tăng index cost | Context sai/stale | Rất đáng thử |
| Corrective RAG | Có thể có | Vừa-cao | Vừa | Retry loop | Max retry |
| Agentic RAG | Có | Khó đoán | Cao | Loop, tool misuse | Chỉ dùng có kiểm soát |
| GraphRAG | Offline + online tùy thiết kế | Vừa-cao | Cao | Graph stale/sai relation | Dùng cho entity/global query |

Rule thực dụng:

1. Nếu p95 latency dưới 2 giây là bắt buộc, tránh nhiều online LLM calls trên retrieval path.
2. Nếu corpus có chunk mất context, ưu tiên contextual retrieval vì chi phí nằm ở indexing time.
3. Nếu query set có nhiều synonym/acronym, dùng rewrite + original search trước khi bật multi-query.
4. Nếu câu hỏi multi-hop ít hơn 5-10% traffic, có thể route riêng thay vì làm mọi query đi qua decomposition.

## 15. Evaluation gate

Mỗi pattern mới phải qua decision gate:

```markdown
| Pipeline | Recall@5 | MRR@10 | Context precision | Citation accuracy | p95 latency | Cost/query | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline hybrid + rerank | | | | | | | |
| + query rewrite | | | | | | | |
| + contextual retrieval | | | | | | | |
| + multi-query | | | | | | | |
```

Không chỉ nhìn aggregate. Hãy report theo tag:

- `short`
- `synonym`
- `acronym`
- `comparison`
- `multi_hop`
- `exact_lookup`
- `policy`
- `table`
- `security_sensitive`

Một pattern được giữ khi:

- Cải thiện rõ trên nhóm lỗi mục tiêu.
- Không làm giảm đáng kể nhóm query đang tốt.
- p95 latency và cost còn trong budget.
- Không làm hỏng citation hoặc permission.
- Có trace đủ để debug.

## 16. Best practices

- Bắt đầu từ hybrid search + reranker.
- Đừng dùng agentic RAG để che lấp retriever yếu.
- Luôn giữ original query trong retrieval set.
- Version prompt cho rewrite, HyDE, decomposition và contextual enrichment.
- Không để generated text trở thành source citation.
- Rerank sau khi merge multi-query.
- Có feature flag để bật/tắt từng pattern.
- Có fallback về baseline khi LLM rewriter timeout.
- Trace mọi variants và retrieved chunks.
- Đánh giá theo category, không chỉ điểm trung bình.

## 17. Dùng được trong production không?

Có, nhưng không phải bằng cách bật mọi pattern.

Production-ready khi có đủ điều kiện:

- Baseline hybrid + rerank đã chạy ổn và có golden set.
- Advanced pattern được gắn với lỗi cụ thể trong golden set.
- Có before/after report về quality, latency và cost.
- Có tenant/ACL filter ở retriever layer.
- Có citation đúng source thật, không cite rewritten query hoặc HyDE text.
- Có timeout, retry limit, cache và fallback.
- Có tracing cho từng bước retrieval.
- Có prompt/version/index version rõ ràng.
- Có monitoring sau khi rollout: no-answer rate, citation error, retrieval latency, cost/query, user feedback.

Không production-ready nếu:

- Chưa có eval.
- Không biết pattern nào đang cải thiện lỗi nào.
- Agent loop không có max steps.
- Query rewrite có thể thay đổi intent mà không được phát hiện.
- Contextual chunk không có version và reindex path.
- GraphRAG index không có update/delete strategy.

## 18. Checklist cuối bài

- [ ] Giải thích được query rewriting, multi-query, HyDE và step-back khác nhau thế nào.
- [ ] Biết query decomposition khác multi-hop RAG ở đâu.
- [ ] Biết contextual retrieval cải thiện chunk mất context bằng cách nào.
- [ ] Biết khi nào không nên dùng HyDE hoặc agentic RAG.
- [ ] Có thể thiết kế trace cho original query, rewritten query, variants, retrieved chunks và reranked chunks.
- [ ] Có decision report trước khi giữ một advanced pattern.
- [ ] Trả lời được điều kiện production readiness.

## 19. Câu hỏi ôn tập

1. Vì sao nên search cả original query và rewritten query?
2. Khi nào multi-query retrieval làm Recall@K tăng nhưng context precision giảm?
3. Vì sao HyDE output không được dùng làm evidence?
4. Step-back prompting khác query rewriting ở điểm nào?
5. Query decomposition cần lưu trace thế nào để final answer có citation đúng?
6. Vì sao contextual retrieval thường đáng thử trước agentic RAG?
7. Khi nào GraphRAG đáng đầu tư?
8. Nếu p95 latency tăng 3 lần nhưng Recall@5 chỉ tăng 1%, bạn quyết định thế nào?
