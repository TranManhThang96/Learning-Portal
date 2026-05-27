# Bài Tập — Ngày 22: RAG Nâng Cao & Optimization

## Bài 1 — Chunking Comparison (Cơ bản)

**Mô tả:** Implement và so sánh 3 chunking strategies khác nhau trên cùng một document, đo lường và visualize sự khác biệt.

**Yêu cầu:**
1. Tải một document dài (ít nhất 5000 từ) — có thể dùng Wikipedia article hoặc một blog post kỹ thuật
2. Apply 3 strategies: Fixed-size (CharacterTextSplitter), Recursive (RecursiveCharacterTextSplitter), Token-based (TokenTextSplitter)
3. Với mỗi strategy, tính toán và in ra:
   - Số lượng chunks
   - Average chunk size (characters và tokens)
   - Min/Max chunk size
   - Số chunks có overlap với chunk kế tiếp
4. Tạo một function `chunk_quality_report(chunks)` để print report đẹp

**Expected output:**
```
=== Chunking Comparison Report ===

Strategy: CharacterTextSplitter (chunk_size=1000, overlap=200)
  Total chunks:     42
  Avg chunk size:   856 chars / 214 tokens
  Min chunk size:   201 chars
  Max chunk size:   1000 chars
  Chunks with overlap: 41/42

Strategy: RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
  Total chunks:     38
  Avg chunk size:   923 chars / 231 tokens
  Min chunk size:   312 chars
  Max chunk size:   1000 chars
  Chunks with overlap: 37/38

Strategy: TokenTextSplitter (chunk_size=256, overlap=32)
  Total chunks:     47
  Avg chunk size:   245 tokens / 981 chars
  Min chunk size:   32 tokens
  Max chunk size:   256 tokens
  Chunks with overlap: 46/47
```

**Hint:**
- Dùng `tiktoken.encoding_for_model("gpt-4")` để đếm tokens chính xác
- Detect overlap bằng cách check xem `chunk[i][-overlap_size:]` có trong `chunk[i+1][:overlap_size*2]` không
- `langchain_text_splitters` là package cần install

---

## Bài 2 — Hybrid Search Implementation (Trung bình)

**Mô tả:** Build một hybrid search system hoàn chỉnh, so sánh performance của dense-only, sparse-only, và hybrid search trên một test dataset.

**Yêu cầu:**
1. Tạo một corpus gồm ít nhất 20 documents về một chủ đề kỹ thuật (Python, NodeJS, databases...)
2. Implement 3 searchers:
   - `DenseSearcher`: chỉ dùng vector similarity (Chroma)
   - `SparseSearcher`: chỉ dùng BM25
   - `HybridSearcher`: kết hợp cả hai với configurable alpha
3. Tạo một test set gồm 5 queries với ground truth relevant documents
4. Đo `Precision@5` và `Recall@5` cho mỗi searcher
5. Thử 3 giá trị alpha khác nhau (0.3, 0.5, 0.7) và tìm giá trị tốt nhất
6. Ghi lại trường hợp hybrid không thắng dense-only hoặc sparse-only, nếu có, và giải thích dựa trên query/corpus

**Expected output:**
```
=== Search Performance Comparison ===

Corpus: 20 documents
Test queries: 5

Searcher          | Precision@5 | Recall@5 | Avg Latency
------------------|-------------|----------|------------
Dense (vector)    |    0.72     |   0.68   |   145ms
Sparse (BM25)     |    0.65     |   0.71   |    12ms
Hybrid (α=0.3)    |    0.74     |   0.73   |   158ms
Hybrid (α=0.5)    |    0.81     |   0.79   |   162ms  ← Best
Hybrid (α=0.7)    |    0.78     |   0.75   |   159ms

Best alpha: 0.5
Hybrid improvement over Dense: +12.5% Precision, +16.2% Recall
```

Kết quả trên là ví dụ. Với corpus nhỏ hoặc query quá thiên về keyword/semantic, hybrid có thể không thắng; mục tiêu bài này là đo và giải thích, không ép một kỹ thuật thắng mọi dataset.

**Hint:**
- `rank_bm25` package cho BM25: `BM25Okapi(tokenized_corpus)`
- Precision@k = (relevant docs in top-k) / k
- Recall@k = (relevant docs in top-k) / (total relevant docs)
- Dùng `time.perf_counter()` để đo latency
- Ground truth có thể manually label hoặc dùng exact keyword matching

---

## Bài 3 — End-to-End RAG Evaluation Pipeline (Nâng cao / Challenge)

**Mô tả:** Xây dựng một RAG pipeline hoàn chỉnh với evaluation loop tự động, tìm ra configuration tốt nhất thông qua systematic testing.

**Yêu cầu:**

**Phần A — RAG Pipeline Builder:**
```python
class RAGPipelineConfig:
    chunk_size: int          # 256, 512, 1024
    chunk_overlap: float     # 0.1, 0.2 (% của chunk_size)
    chunking_strategy: str   # "fixed", "recursive", "semantic"
    search_type: str         # "dense", "sparse", "hybrid"
    hybrid_alpha: float      # 0.3 - 0.7
    use_reranker: bool       # True/False
    top_k_retrieval: int     # 5, 10, 20
    top_k_final: int         # 3, 5
```

**Phần B — Systematic Evaluation:**
1. Load một document corpus (ít nhất 10 documents)
2. Generate test questions tự động dùng LLM (5 questions từ mỗi document)
3. Build RAG pipeline với 4 configs khác nhau
4. Evaluate mỗi config với RAGAS metrics (hoặc custom evaluator nếu không có API key)
5. Tạo comparison report

**Phần C — Failure Analysis:**
1. Tìm questions mà pipeline trả lời sai (faithfulness < 0.7)
2. Phân tích nguyên nhân:
   - Retrieval failure? (relevant context không được retrieved)
   - Generation failure? (context đúng nhưng LLM trả lời sai)
3. Suggest fixes dựa trên failure analysis

**Expected output:**
```
=== RAG Pipeline Evaluation Report ===
Date: 2024-01-15
Corpus: 10 documents, 1,234 chunks
Test set: 50 questions

Config Comparison:
Config | Chunk | Strategy  | Search  | Rerank | Faithful | Relevancy | Precision | Recall
-------|-------|-----------|---------|--------|----------|-----------|-----------|-------
  A    |  256  | recursive | dense   |   No   |  0.721   |   0.832   |   0.698   | 0.671
  B    |  512  | recursive | hybrid  |   No   |  0.789   |   0.856   |   0.743   | 0.712
  C    |  512  | recursive | hybrid  |  Yes   |  0.834   |   0.891   |   0.812   | 0.798  ← Best
  D    | 1024  | semantic  | hybrid  |  Yes   |  0.801   |   0.867   |   0.789   | 0.823

Winner: Config C

Failure Analysis (Config C):
Total failures (faithfulness < 0.7): 8/50 (16%)

Failure types:
  - Retrieval failure: 5 cases (62.5%)
    Common cause: question uses different vocabulary than documents
    Suggested fix: Add query expansion or synonym handling

  - Generation failure: 3 cases (37.5%)
    Common cause: LLM ignores specific numbers/dates in context
    Suggested fix: Add explicit instruction to preserve exact values

Top 3 problematic questions:
  1. "What is the exact version number of..." → Retrieval miss
  2. "How many days does it take to..." → Generation hallucination
  3. "Compare X and Y in terms of..." → Context insufficient
```

**Hint:**
- Dùng `itertools.product()` để generate tất cả config combinations
- Tạo test questions với prompt: "Generate 3 factual questions about this text that can be answered from the text alone"
- Faithfulness check đơn giản: "Does the answer contain any information NOT in the context? Answer yes/no"
- Lưu kết quả vào CSV để dễ compare

---

## 🔍 Gợi ý kiểm tra kết quả

### Checklist Bài 1:
- [ ] Cả 3 strategies chạy không lỗi
- [ ] Report hiển thị đúng stats (verify thủ công với document ngắn)
- [ ] Overlap detection hoạt động (chunk cuối không có overlap)
- [ ] Token counting dùng tiktoken, không phải `len(text.split())`

### Checklist Bài 2:
- [ ] BM25 index được tạo từ tokenized corpus
- [ ] Score normalization (min-max) áp dụng trước khi combine
- [ ] Latency đo từ search request, không tính index time
- [ ] Precision và Recall tính đúng công thức
- [ ] Kết quả hybrid được so sánh công bằng với dense-only và sparse-only; nếu không tốt hơn, có failure analysis

### Checklist Bài 3:
- [ ] Test questions được generate tự động (không viết tay)
- [ ] Ít nhất 4 configs khác nhau được test
- [ ] Failure analysis phân biệt retrieval vs generation failure
- [ ] Report có thể reproduce (fix random seed nếu có)
- [ ] Suggestions dựa trên actual failure patterns, không generic

### Debug Tips:
```python
# Debug retrieval quality — in ra documents được retrieved
def debug_retrieval(query: str, retriever, expected_doc_id: str):
    results = retriever.invoke(query)
    print(f"Query: {query}")
    print(f"Expected doc ID: {expected_doc_id}")
    retrieved_ids = [doc.metadata.get("id") for doc in results]
    print(f"Retrieved IDs: {retrieved_ids}")
    print(f"Hit: {expected_doc_id in retrieved_ids}")

# Debug embedding similarity
from langchain_openai import OpenAIEmbeddings
import numpy as np

def debug_similarity(text1: str, text2: str):
    embeddings = OpenAIEmbeddings()
    emb1 = embeddings.embed_query(text1)
    emb2 = embeddings.embed_query(text2)
    similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    print(f"Cosine similarity: {similarity:.4f}")
    return similarity
```
