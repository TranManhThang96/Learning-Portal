# Day 34: Chunking Strategies

## 1. TL;DR

Chunking là cách cắt tài liệu dài thành các record nhỏ hơn để đưa vào embedding, vector database, reranker và context của LLM. Trong RAG, chunk không chỉ là đoạn text. Chunk là đơn vị retrieval, citation, permission check, cache, evaluation, deletion và reindex.

Không có `chunk_size=800` nào đúng cho mọi hệ thống. Cách chọn tốt hơn là:

1. Cắt theo cấu trúc tài liệu trước: heading, section, paragraph, table, page, function, class.
2. Sau đó mới áp token budget để tránh chunk quá dài.
3. Luôn giữ metadata đủ để truy vết: source, page, heading, version, tenant, ACL, parser version, chunking strategy.
4. Đánh giá bằng query thật, không chọn theo cảm tính.

Production RAG thường bắt đầu bằng recursive hoặc markdown-aware chunking cho tài liệu sạch, layout-aware PDF chunking cho PDF quan trọng, code-aware chunking cho codebase, và parent-child chunking khi cần precision cao nhưng vẫn cần context rộng.

## 2. Vì sao chunking quyết định chất lượng RAG?

Pipeline RAG đơn giản:

```text
Document -> parse -> clean -> chunk -> embed -> index -> retrieve -> rerank -> build context -> generate answer
```

Nếu chunk sai, các bước phía sau chỉ tối ưu trên đơn vị dữ liệu sai:

- Embedding của một chunk bị cắt ngang ý sẽ không đại diện đúng nội dung.
- Vector search có thể lấy đúng từ khóa nhưng thiếu phần điều kiện ở câu trước hoặc bảng sau.
- Reranker không thể khôi phục context đã bị mất.
- LLM dễ hallucinate vì nhận nửa câu, thiếu heading hoặc thiếu page.
- Citation có thể trỏ sai trang nếu chunk không lưu page metadata.
- Permission-aware RAG có thể rò rỉ dữ liệu nếu child chunk và parent chunk không cùng ACL.

Với Senior SE, hãy xem chunking giống thiết kế schema và index cho database: schema kém thì query planner giỏi cũng không cứu được toàn bộ hệ thống.

## 3. Một chunk tốt cần có gì?

Một chunk tốt nên thỏa các tiêu chí sau:

| Tiêu chí | Ý nghĩa production |
|---|---|
| Đủ nghĩa khi đọc độc lập | Retriever và reranker có đủ context để chọn đúng |
| Boundary tự nhiên | Không cắt giữa câu, bảng, bullet, function hoặc clause |
| Metadata đầy đủ | Có thể cite, audit, filter, delete và reproduce |
| Độ dài phù hợp | Không quá nhỏ gây mất context, không quá lớn gây noise và tốn token |
| Ít duplicate | Giảm chi phí vector DB, reranker và context |
| Stable ID | Reindex và trace không bị mất khả năng đối chiếu |
| Permission rõ ràng | Không trộn nội dung khác tenant, user group hoặc document scope |

Ví dụ metadata tối thiểu:

```json
{
  "chunk_id": "doc-123:v4:recursive:v2:0007:9f1a2c",
  "document_id": "doc-123",
  "document_title": "Chính sách hoàn tiền SaaS",
  "source_uri": "s3://kb/policies/refund-policy-v4.pdf",
  "source_type": "pdf",
  "page_start": 3,
  "page_end": 4,
  "heading_path": ["Chính sách hoàn tiền", "Điều kiện được hoàn tiền"],
  "chunk_index": 7,
  "parent_id": "doc-123:v4:section:refund-conditions",
  "token_count": 312,
  "char_start": 8421,
  "char_end": 10102,
  "document_version": "v4",
  "parser_version": "pdf-layout-parser-2026-05",
  "chunking_strategy": "recursive",
  "chunking_version": "v2",
  "text_hash": "9f1a2c...",
  "tenant_id": "tenant-a",
  "acl_hash": "sales-support-policy-read"
}
```

## 4. Fixed-size chunking

Fixed-size chunking cắt tài liệu theo số ký tự hoặc token cố định.

```text
Document text
  -> chunk 0: token 0-400
  -> chunk 1: token 350-750
  -> chunk 2: token 700-1100
```

Ưu điểm:

- Dễ implement.
- Nhanh, ít dependency.
- Phù hợp prototype hoặc corpus text rất đồng nhất.
- Dễ kiểm soát số token.

Nhược điểm:

- Dễ cắt ngang câu, bảng, heading, list hoặc code.
- Dễ mất điều kiện quan trọng ở boundary.
- Citation yếu vì chunk không hiểu section/page.
- Không tối ưu cho PDF, markdown, legal document hoặc code.

Dùng trong production được không?

Có, nhưng thường chỉ nên dùng làm baseline hoặc fallback cho text đã được normalize tốt. Điều kiện tối thiểu là có sentence-aware boundary, overlap vừa phải, metadata đầy đủ và retrieval eval chứng minh không thua strategy có cấu trúc.

## 5. Recursive chunking

Recursive chunking cắt theo separator từ lớn đến nhỏ. Ví dụ:

```python
separators = ["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
```

Ý tưởng:

1. Thử giữ section hoặc paragraph nếu còn dưới token limit.
2. Nếu quá dài, cắt tiếp theo paragraph.
3. Nếu vẫn quá dài, cắt theo sentence.
4. Chỉ cắt theo word/character khi không còn lựa chọn tốt hơn.

Ưu điểm:

- Baseline tốt cho tài liệu text, docs, wiki, FAQ.
- Giữ boundary tự nhiên tốt hơn fixed-size.
- Dễ debug và reproducible hơn semantic chunking.
- Không cần embedding trong bước chunking.

Nhược điểm:

- Không hiểu layout PDF.
- Không bảo toàn table phức tạp nếu parser đã flatten sai.
- Không hiểu code symbol nếu chỉ dùng separator text.
- Section rất dài vẫn có thể bị cắt ở điểm chưa tối ưu.

Dùng trong production được không?

Có. Đây thường là lựa chọn v1 tốt cho docs nội bộ, knowledge base và markdown đã parse sạch. Cần thêm metadata heading/page/source, dedupe overlap và benchmark theo query thật.

## 6. Semantic chunking

Semantic chunking tìm điểm đổi chủ đề dựa trên embedding hoặc model semantic similarity. Cách phổ biến:

1. Tách tài liệu thành sentence hoặc paragraph nhỏ.
2. Tính embedding cho từng đơn vị.
3. Tính similarity giữa các đoạn liền kề.
4. Nếu similarity giảm mạnh, coi đó là topic boundary.
5. Gom các đoạn gần nhau đến khi đạt min/max token.

Ưu điểm:

- Giữ topic boundary tốt với văn bản dài, ít heading.
- Hữu ích cho transcript, meeting note, long-form article.
- Có thể cải thiện precision khi tài liệu không có cấu trúc rõ.

Nhược điểm:

- Tốn thêm embedding/preprocessing.
- Khó reproducible hơn nếu model hoặc threshold đổi.
- Có thêm hyperparameter: min tokens, max tokens, breakpoint percentile.
- Có thể tạo chunk quá nhỏ nếu tài liệu chuyển ý liên tục.

Dùng trong production được không?

Có, khi corpus có văn bản dài ít cấu trúc và team có eval pipeline rõ. Điều kiện bắt buộc là versioning model/threshold, lưu chunking version, đo chi phí indexing và có regression test trước khi re-chunk toàn bộ corpus.

## 7. Markdown-aware chunking

Markdown có cấu trúc giàu ngữ nghĩa:

```markdown
# API Rate Limit

## Error 429

| Plan | Limit |
|---|---:|
| Pro | 600 rpm |
```

Markdown-aware chunker nên:

- Parse heading hierarchy và lưu `heading_path`.
- Gắn heading path vào text được embed để chunk ngắn vẫn có context.
- Giữ code block nguyên khối nếu có thể.
- Không tách table khỏi caption, heading và note liên quan.
- Loại repeated navigation, footer, "last updated" nếu lặp ở mọi page.
- Giữ anchor/section id để citation link chính xác.

Ví dụ text để embed:

```text
Document: API Rate Limit
Section: Errors > HTTP 429
Content:
When the API key exceeds 600 requests per minute, the API returns HTTP 429...
```

Điểm cần chú ý: text dùng để embed có thể chứa heading/context bổ sung, nhưng text hiển thị cho user nên giữ nội dung gốc sạch để citation không gây nhiễu.

Dùng trong production được không?

Có. Với developer docs, runbook, handbook, wiki và policy markdown, đây thường là best default. Cần parser ổn định, test với table/code/list, và giữ mapping tới source anchor.

## 8. PDF chunking

PDF là nguồn lỗi lớn trong enterprise RAG vì PDF không phải format text logic, mà là layout trình bày. Các lỗi hay gặp:

- Header/footer bị lặp trong mọi chunk.
- Multi-column bị trộn dòng.
- Text extraction sai thứ tự đọc.
- Table bị flatten thành dòng vô nghĩa.
- OCR mất dấu tiếng Việt.
- Caption tách khỏi hình hoặc bảng.
- Page number trong metadata không khớp page hiển thị.

Pipeline nên dùng:

```text
PDF
  -> layout parser
  -> OCR nếu cần
  -> cleanup header/footer
  -> detect block: title, paragraph, table, figure caption, footnote
  -> page-aware chunking
  -> table serialization
  -> metadata validation
  -> embedding/index
```

Với table, đừng chỉ flatten thành text rời rạc. Nên serialize có header:

```text
Table: Gói dịch vụ và giới hạn request
Columns: Plan | Requests per minute | Burst
Row: Pro | 600 | 1200
Row: Enterprise | 5000 | 10000
Source: page 4
```

Rủi ro citation/page/source:

- Nếu chunk trải từ page 3 sang page 5, citation cần `page_start=3`, `page_end=5`, hoặc tốt hơn là giữ page spans chi tiết.
- Nếu parser bỏ header section, answer có thể cite đúng page nhưng thiếu context pháp lý.
- Nếu OCR sai dấu hoặc sai số, retrieval và answer đều sai nhưng trông vẫn hợp lý.

Dùng trong production được không?

Có, nhưng cần coi parser là thành phần production, không phải helper script. Điều kiện gồm layout parser tốt, OCR quality check, page-level metadata, table extraction, visual spot-check, eval riêng cho citation theo page và quy trình reprocess khi parser nâng version.

## 9. Code chunking

Code RAG không nên cắt theo token ngẫu nhiên. Boundary tự nhiên của code là:

- Repository.
- File/module.
- Import block.
- Class/interface/type.
- Function/method.
- Config block.
- Test case.

Metadata code nên có:

```json
{
  "repo": "payment-service",
  "commit": "a1b2c3d",
  "file_path": "src/refund/policy.ts",
  "language": "typescript",
  "symbol_name": "calculateRefundEligibility",
  "symbol_type": "function",
  "start_line": 42,
  "end_line": 118,
  "imports": ["date-fns", "./types"],
  "chunking_strategy": "tree-sitter-symbol-v1"
}
```

Best practice:

- Dùng parser như Tree-sitter thay vì regex nếu có thể.
- Với function quá dài, chia theo block logic nhưng vẫn giữ signature và docstring.
- Với class lớn, tạo parent là class, child là method.
- Kết hợp hybrid search vì code query thường chứa exact symbol, path hoặc error message.
- Citation nên trỏ về file path và line range.

Dùng trong production được không?

Có. Điều kiện là parser theo ngôn ngữ, metadata commit/file/line chính xác, index theo commit hoặc branch rõ ràng, và permission theo repo/team.

## 10. Parent-child chunking

Parent-child chunking tách hai cấp:

```text
Parent: section 900-1800 tokens
  Child 1: 180-350 tokens
  Child 2: 180-350 tokens
  Child 3: 180-350 tokens
```

Search trên child để tăng precision. Khi build context, fetch parent để có context rộng hơn.

Luồng production:

```text
query
  -> retrieve top_k child chunks
  -> apply metadata/ACL filters
  -> rerank child chunks
  -> group by parent_id
  -> fetch parent sections with budget
  -> dedupe and compress context
  -> generate answer with citations
```

Ưu điểm:

- Child nhỏ giúp match query chính xác.
- Parent lớn giúp LLM có đủ context để trả lời.
- Phù hợp policy, legal, specs, design docs.

Nhược điểm:

- Tăng độ phức tạp indexing và retrieval.
- Dễ duplicate parent nếu nhiều child cùng section match.
- Parent quá lớn làm tốn context token.
- ACL phải nhất quán giữa parent và child.
- Citation cần quyết định cite child, parent hay source span.

Dùng trong production được không?

Có. Đây là pattern mạnh cho enterprise RAG, nhưng chỉ nên dùng khi context builder có budget/dedupe tốt, metadata parent-child ổn định và permission check áp dụng ở cả hai cấp.

## 11. Chunk overlap

Overlap là phần nội dung lặp giữa hai chunk liền kề. Mục tiêu là tránh mất thông tin ở boundary.

Trade-off:

| Overlap | Lợi ích | Chi phí |
|---:|---|---|
| 0% | Index nhỏ, ít duplicate | Dễ mất ý ở boundary |
| 5-10% | Cân bằng cho docs sạch | Vẫn có thể miss câu dài |
| 10-20% | Baseline tốt cho text thường | Vector tăng, reranker tốn hơn |
| >25% | Giảm miss boundary | Duplicate cao, context lặp, citation nhiễu |

Overlap nên theo sentence/paragraph, không nên cắt cứng theo character. Với markdown-aware hoặc parent-child chunking tốt, overlap có thể thấp hơn. Với fixed-size, overlap thường cần cao hơn để bù boundary kém.

## 12. Chunk size trade-off

Không chọn chunk size tách khỏi use case.

| Use case | Gợi ý ban đầu | Lý do |
|---|---:|---|
| FAQ/support answer ngắn | 100-300 tokens | Query thường hỏi fact cụ thể |
| Product docs/handbook | 300-800 tokens | Cần đủ heading, rule, exception |
| Policy/legal | Theo clause/section, thường 400-1200 tokens | Không được mất điều kiện pháp lý |
| PDF financial report | Theo page/block/table | Page citation quan trọng |
| Code RAG | Theo function/class, không theo token cứng | Symbol boundary quan trọng |
| Parent-child | child 150-400, parent 800-2000 | Precision + context |

Ảnh hưởng hiệu năng:

- Chunk nhỏ hơn làm số vector tăng, storage tăng, ANN latency có thể tăng.
- Chunk lớn hơn làm context token tăng, LLM latency/cost tăng.
- Overlap 20% có thể làm index tăng hơn 20% vì boundary và small chunks.
- Semantic chunking tốn thêm preprocessing embedding.
- PDF OCR/layout parsing thường là bottleneck ingestion.
- Re-chunking thường đồng nghĩa re-embed và reindex, cần migration plan.

Ví dụ scale:

```text
100,000 documents * 12 chunks/document = 1.2M vectors
100,000 documents * 35 chunks/document = 3.5M vectors
```

Chênh lệch này ảnh hưởng trực tiếp đến RAM/disk vector DB, thời gian index, latency, chi phí rerank và chi phí backup.

## 13. Code gần production: chunking/eval mini pipeline

Ví dụ dưới đây không phụ thuộc vendor cụ thể. Trong production, bạn có thể thay `simple_embed` bằng embedding model thật và thay in-memory search bằng Qdrant, pgvector, Milvus hoặc Pinecone.

```python
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Iterable, Literal


Strategy = Literal["fixed", "recursive", "markdown"]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    strategy: Strategy
    chunk_index: int
    heading_path: tuple[str, ...]
    source_uri: str
    page_start: int | None = None
    page_end: int | None = None
    parent_id: str | None = None
    token_count: int = 0
    text_hash: str = ""


def estimate_tokens(text: str) -> int:
    # Đủ tốt cho sizing tương đối trong demo. Production nên dùng tokenizer của embedding/LLM model.
    return max(1, math.ceil(len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)) * 1.25))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def make_chunk(
    *,
    document_id: str,
    source_uri: str,
    strategy: Strategy,
    chunk_index: int,
    text: str,
    heading_path: tuple[str, ...] = (),
    page_start: int | None = None,
    page_end: int | None = None,
    parent_id: str | None = None,
) -> Chunk:
    normalized = re.sub(r"\s+", " ", text).strip()
    text_hash = stable_hash(normalized)
    chunk_id = f"{document_id}:{strategy}:v1:{chunk_index:04d}:{text_hash}"
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=normalized,
        strategy=strategy,
        chunk_index=chunk_index,
        heading_path=heading_path,
        source_uri=source_uri,
        page_start=page_start,
        page_end=page_end,
        parent_id=parent_id,
        token_count=estimate_tokens(normalized),
        text_hash=text_hash,
    )


def fixed_size_chunks(
    document_id: str,
    source_uri: str,
    text: str,
    max_tokens: int = 160,
    overlap_tokens: int = 30,
) -> list[Chunk]:
    words = re.findall(r"\S+", text)
    chunks: list[Chunk] = []
    start = 0
    index = 0
    step = max(1, max_tokens - overlap_tokens)
    while start < len(words):
        piece = " ".join(words[start : start + max_tokens])
        chunks.append(
            make_chunk(
                document_id=document_id,
                source_uri=source_uri,
                strategy="fixed",
                chunk_index=index,
                text=piece,
            )
        )
        start += step
        index += 1
    return chunks


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def recursive_chunks(
    document_id: str,
    source_uri: str,
    text: str,
    max_tokens: int = 220,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            chunks.append("\n\n".join(current).strip())
            current.clear()

    for paragraph in paragraphs:
        if estimate_tokens(paragraph) > max_tokens:
            flush()
            sentences = split_sentences(paragraph)
            window: list[str] = []
            for sentence in sentences:
                candidate = " ".join([*window, sentence])
                if estimate_tokens(candidate) > max_tokens and window:
                    chunks.append(" ".join(window))
                    window = window[-overlap_sentences:] if overlap_sentences else []
                window.append(sentence)
            if window:
                chunks.append(" ".join(window))
            continue

        candidate = "\n\n".join([*current, paragraph])
        if estimate_tokens(candidate) > max_tokens:
            flush()
        current.append(paragraph)
    flush()

    return [
        make_chunk(
            document_id=document_id,
            source_uri=source_uri,
            strategy="recursive",
            chunk_index=i,
            text=chunk_text,
        )
        for i, chunk_text in enumerate(chunks)
    ]


def markdown_chunks(
    document_id: str,
    source_uri: str,
    markdown: str,
    max_tokens: int = 260,
) -> list[Chunk]:
    lines = markdown.splitlines()
    sections: list[tuple[tuple[str, ...], list[str]]] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_path: tuple[str, ...] = ()

    def flush() -> None:
        if current_lines:
            sections.append((current_path, current_lines.copy()))
            current_lines.clear()

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack[:] = [(l, t) for l, t in heading_stack if l < level]
            heading_stack.append((level, title))
            current_path = tuple(title for _, title in heading_stack)
            current_lines.append(line)
        else:
            current_lines.append(line)
    flush()

    chunks: list[Chunk] = []
    for path, section_lines in sections:
        section_text = "\n".join(section_lines).strip()
        contextual_text = f"Section: {' > '.join(path)}\n\n{section_text}" if path else section_text
        if estimate_tokens(contextual_text) <= max_tokens:
            chunks.append(
                make_chunk(
                    document_id=document_id,
                    source_uri=source_uri,
                    strategy="markdown",
                    chunk_index=len(chunks),
                    text=contextual_text,
                    heading_path=path,
                )
            )
            continue

        for sub in recursive_chunks(document_id, source_uri, section_text, max_tokens=max_tokens):
            chunks.append(
                make_chunk(
                    document_id=document_id,
                    source_uri=source_uri,
                    strategy="markdown",
                    chunk_index=len(chunks),
                    text=f"Section: {' > '.join(path)}\n\n{sub.text}",
                    heading_path=path,
                )
            )
    return chunks


def simple_embed(text: str) -> set[str]:
    stopwords = {"và", "là", "của", "cho", "trong", "khi", "nếu", "the", "a", "to", "of"}
    terms = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
    return {term for term in terms if len(term) > 2 and term not in stopwords}


def jaccard_score(query: str, chunk: Chunk) -> float:
    q = simple_embed(query)
    c = simple_embed(" ".join([*chunk.heading_path, chunk.text]))
    if not q or not c:
        return 0.0
    return len(q & c) / len(q | c)


def retrieve(query: str, chunks: Iterable[Chunk], top_k: int = 5) -> list[tuple[float, Chunk]]:
    scored = [(jaccard_score(query, chunk), chunk) for chunk in chunks]
    return sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]
```

Điểm gần production trong ví dụ:

- Chunk có dataclass rõ ràng, không truyền dict tùy tiện.
- `chunk_id` ổn định theo document, strategy, version, index và text hash.
- Metadata đủ chỗ cho source/page/heading/parent.
- Tách chunking, ID, token estimate và retrieval eval.
- Có thể thay từng phần bằng tokenizer, embedding model và vector DB thật.

Những thứ demo chưa đủ production:

- `estimate_tokens` chỉ là ước lượng.
- `simple_embed` không thay thế embedding model.
- Chưa có PDF parser, ACL, observability, retry, batch indexing, backfill, schema migration.
- Chưa có regression test bằng ground-truth query set.

## 14. Evaluation cho chunking

Không đánh giá chunking bằng cảm giác. Hãy dùng một query set nhỏ nhưng thật:

```json
[
  {
    "query": "Gói Pro bị giới hạn bao nhiêu request mỗi phút?",
    "expected_source": "refund-policy.md#rate-limit",
    "expected_terms": ["Pro", "600", "requests per minute"]
  },
  {
    "query": "Khách hàng có được hoàn tiền sau 30 ngày không?",
    "expected_source": "refund-policy.md#refund-window",
    "expected_terms": ["30 ngày", "không hoàn tiền", "ngoại lệ"]
  }
]
```

Metrics retrieval nên đo:

- `Recall@k`: expected chunk/source có nằm trong top k không.
- `MRR`: kết quả đúng đứng ở vị trí mấy.
- Citation accuracy: page/section/source có đúng không.
- Context token per answer: tốn bao nhiêu token.
- Duplicate rate: top k có bao nhiêu chunk trùng ý.
- No-answer correctness: khi tài liệu không có thông tin, hệ thống có từ chối không.

Checklist khi so sánh strategy:

1. Cùng document source.
2. Cùng embedding model.
3. Cùng vector DB/search config.
4. Cùng reranker nếu có.
5. Cùng `top_k` và context budget.
6. Log đầy đủ chunk id, score, heading, page, token count.
7. Đánh giá cả chất lượng answer và chất lượng citation.

## 15. Best solution theo context

| Context | Strategy nên bắt đầu | Lý do |
|---|---|---|
| Markdown docs, wiki, runbook | Markdown-aware + recursive fallback | Tận dụng heading/table/code block |
| Plain text FAQ | Recursive, chunk nhỏ | Query ngắn, fact cụ thể |
| Legal/policy PDF | Layout-aware PDF + parent-child | Page citation và clause context quan trọng |
| Transcript/meeting note | Semantic hoặc recursive theo paragraph | Topic shift quan trọng hơn heading |
| Codebase assistant | Code-aware symbol chunking + hybrid search | Function/class/path/line là boundary thật |
| Enterprise RAG có permission | Parent-child + strict metadata filter | Precision, context và ACL đều quan trọng |
| Prototype nhanh | Fixed-size hoặc recursive | Tối ưu tốc độ học, nhưng phải eval lại |

## 16. Production readiness

Dùng được trong production không?

Có. Chunking là bắt buộc trong hầu hết production RAG, nhưng không nên xem nó là một tham số đơn lẻ. Production-ready chunking cần các điều kiện sau:

- Có parser phù hợp với từng source type: markdown, HTML, PDF, code, spreadsheet.
- Có schema metadata ổn định cho citation, filtering, permission, audit và deletion.
- Có versioning cho document, parser, chunking strategy và embedding model.
- Có evaluation set trước khi đổi chunk size, overlap hoặc parser.
- Có migration plan vì re-chunk thường kéo theo re-embed và reindex.
- Có dedupe để kiểm soát overlap và repeated boilerplate.
- Có observability: log chunk id, source, score, rerank score, context token, answer citation.
- Có data governance: tenant, ACL, retention, delete propagation.
- Có fallback cho tài liệu parse lỗi và quy trình human review cho source quan trọng.

Decision rule thực tế:

```text
Nếu tài liệu có cấu trúc rõ -> chunk theo cấu trúc.
Nếu tài liệu là PDF quan trọng -> ưu tiên layout/page/table trước token size.
Nếu tài liệu là code -> chunk theo symbol.
Nếu query cần fact nhỏ nhưng answer cần context rộng -> parent-child.
Nếu chưa biết gì -> recursive baseline + eval, không nhảy thẳng vào semantic phức tạp.
```

