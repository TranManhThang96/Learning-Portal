# Bài Tập — Ngày 23: LlamaIndex

> **Version note:** Trước khi làm bài, pin và smoke-test LlamaIndex imports (`llama_index.core`, `Settings`, `KnowledgeGraphIndex`). Nếu target version khác docs hiện hành, ưu tiên sửa import/API theo version đã pin thay vì mix snippets từ nhiều phiên bản.

## Bài 1 — Multi-Index Document System (Cơ bản)

**Mô tả:** Xây dựng một hệ thống Q&A sử dụng cả VectorStoreIndex và SummaryIndex, so sánh kết quả từ hai index.

**Yêu cầu:**
1. Load ít nhất 3 documents về các chủ đề kỹ thuật khác nhau (có thể tạo thủ công hoặc dùng Wikipedia loader)
2. Build cả hai: `VectorStoreIndex` và `SummaryIndex` từ cùng documents
3. Persist cả hai index xuống disk
4. Implement function `smart_query(question: str)` tự động chọn index phù hợp:
   - Nếu question chứa từ khóa ["tóm tắt", "so sánh", "overview", "tổng quan"] → dùng SummaryIndex
   - Còn lại → dùng VectorStoreIndex
5. Test với ít nhất 5 queries, in ra cả response lẫn thời gian trả lời

**Expected output:**
```
Building indexes...
VectorStoreIndex: 24 nodes
SummaryIndex: 24 nodes
Indexes saved to ./storage/

Query 1: "Tóm tắt nội dung chính của tất cả documents"
→ Using: SummaryIndex (matched keyword: "tóm tắt")
→ Time: 2.34s
→ Answer: [summary response...]

Query 2: "FastAPI có gì khác với Flask?"
→ Using: VectorStoreIndex (specific question)
→ Time: 0.87s
→ Answer: [specific response...]

Performance comparison:
  VectorStoreIndex avg time: 0.91s
  SummaryIndex avg time: 2.18s
  Smart router avg time: 1.23s
```

**Hint:**
- Check `os.path.exists(persist_dir)` trước khi build mới
- `StorageContext.from_defaults(persist_dir=...)` để load
- `time.perf_counter()` để đo thời gian
- Summary queries thường bắt đầu bằng "Tóm tắt", "So sánh", "Liệt kê tất cả"

---

## Bài 2 — Custom Ingestion Pipeline với Metadata (Trung bình)

**Mô tả:** Xây dựng ingestion pipeline có custom transformations để process một tập documents kỹ thuật, extract metadata phong phú và build queryable index.

**Yêu cầu:**

**Phần A — Data Preparation:**
Tạo ít nhất 5 documents giả lập technical documentation với metadata:
```python
docs = [
    Document(text="...", metadata={"product": "Redis", "version": "7.0", "type": "tutorial"}),
    Document(text="...", metadata={"product": "PostgreSQL", "version": "16", "type": "reference"}),
    # ... thêm documents
]
```

**Phần B — Custom Transformations:**
Implement 2 custom `TransformComponent`:
1. `CodeBlockExtractor`: Extract code blocks từ text (markdown format ` ```code``` `), thêm metadata `has_code: bool` và `code_languages: List[str]`
2. `ReadabilityScorer`: Tính điểm readability đơn giản dựa trên average sentence length, thêm metadata `readability_score: float` (0-1, 1 = dễ đọc nhất)

**Phần C — Pipeline và Querying:**
1. Build pipeline: SentenceSplitter → CodeBlockExtractor → ReadabilityScorer → Embed
2. Build index và save
3. Query với metadata filters:
   - Tìm documents có code examples (`has_code = True`)
   - Tìm documents về một product cụ thể
   - Tìm documents có readability score cao (> 0.7)

**Expected output:**
```
Pipeline transformations: 4 steps
Processing 5 documents...
  CodeBlockExtractor: Found code in 3/5 documents
  ReadabilityScorer: Avg score = 0.68

Nodes created: 18
  - With code: 7 nodes
  - Without code: 11 nodes
  - High readability (>0.7): 12 nodes

Filter query: "Redis caching" (product=Redis only)
  → 3 results from Redis docs
  → 0 results from PostgreSQL docs ✓

Filter query: "code example" (has_code=True only)
  → Results all contain code blocks ✓
```

**Hint:**
- `re.findall(r'```(\w+)?\n(.*?)```', text, re.DOTALL)` để extract code blocks
- Readability: `avg_sentence_length = total_words / num_sentences`, score = `1 / (1 + avg_sentence_length/20)`
- `MetadataFilters` với `FilterOperator.EQ` cho string match
- Custom TransformComponent cần implement `__call__(self, nodes, **kwargs) -> List[BaseNode]`

---

## Bài 3 — Router Query Engine với Knowledge Graph (Nâng cao / Challenge)

**Mô tả:** Xây dựng một intelligent query system kết hợp VectorStoreIndex, SummaryIndex, và KnowledgeGraphIndex với auto-routing, cùng với evaluation system để đo chất lượng từng route.

**Scope caveat:** `KnowledgeGraphIndex` là phần nhạy version. Nếu version bạn pin khuyến nghị PropertyGraph/graph store API mới hơn, dùng API mới nhưng vẫn giữ mục tiêu bài: route relationship questions sang graph-based retriever và ghi lại API version trong README.

**Yêu cầu:**

**Phần A — Build All Three Indexes:**
```
Dataset: Technical docs về ít nhất 3 technologies (Python, NodeJS, Go hoặc similar)
- VectorStoreIndex: cho specific Q&A
- SummaryIndex: cho overviews và comparisons
- KnowledgeGraphIndex: cho relationship queries ("X được tạo bởi ai?", "Y có quan hệ gì với Z?")
```

**Phần B — RouterQueryEngine với Custom Routing Logic:**
Implement `CustomRouterEngine` với logic routing thông minh hơn LLM selector:
```python
class CustomRouterEngine:
    def query(self, question: str) -> str:
        # Rule 1: Questions về relationships → KG index
        # Rule 2: Questions bắt đầu với comparison words → Summary index
        # Rule 3: Specific technical questions → Vector index
        # Rule 4: Fallback: dùng LLM selector
        ...
```

**Phần C — Evaluation:**
1. Tạo test set: 15 questions với expected index type
   ```python
   test_cases = [
       {"q": "Ai tạo ra Python?", "expected_index": "knowledge_graph"},
       {"q": "So sánh Python và NodeJS", "expected_index": "summary"},
       {"q": "Cú pháp list comprehension trong Python?", "expected_index": "vector"},
       # ... 12 more
   ]
   ```
2. Measure routing accuracy (% queries routed đúng index)
3. Compare response quality giữa đúng index và sai index

**Phần D — Adaptive Learning (Bonus):**
Implement simple feedback mechanism:
- Nếu user rate response < 3/5 → log query + wrong index → adjust routing rules
- Sau 5 failed queries với same pattern → auto-add rule mới

**Expected output:**
```
=== Router Query Engine Evaluation ===

Indexes built:
  VectorStoreIndex: 45 nodes
  SummaryIndex: 45 nodes
  KnowledgeGraphIndex: 23 triplets extracted

Routing Accuracy:
  Rule-based router:  73.3% (11/15 correct)
  LLM-based router:   86.7% (13/15 correct)
  Hybrid router:      93.3% (14/15 correct)  ← Best

Per-index accuracy:
  VectorStore route:  90% (9/10 correct)
  Summary route:      100% (3/3 correct)
  KG route:           50% (1/2 correct) ← Needs improvement

Quality comparison (wrong routing vs right routing):
  When routed to WRONG index: faithfulness = 0.52
  When routed to RIGHT index: faithfulness = 0.84
  → Routing accuracy matters! +61.5% quality improvement

Routing failures analysis:
  Failed: "What is the relationship between asyncio and event loop?"
  → Routed to: VectorStore
  → Should be: KnowledgeGraph (relationship question)
  → Suggested rule: add "relationship between" pattern → KG route
```

**Hint:**
- KnowledgeGraphIndex cần nhiều text để extract triplets — dùng documents ít nhất 300 words
- `kg_index.get_networkx_graph()` để xem graph được built
- Routing rules: check `question.lower()` với regex patterns
- `verbose=True` cho RouterQueryEngine để debug routing decisions
- Faithfulness check: "Does the answer only contain information from the context?"

---

## 🔍 Gợi ý kiểm tra kết quả

### Checklist Bài 1:
- [ ] Index được persist và load thành công (không rebuild nếu đã có)
- [ ] smart_query() routing logic hoạt động (test với ít nhất 2 keywords)
- [ ] Response từ SummaryIndex dài hơn / comprehensive hơn VectorStoreIndex cho summary questions
- [ ] Thời gian SummaryIndex chậm hơn VectorStoreIndex (đây là expected behavior)

### Checklist Bài 2:
- [ ] Custom TransformComponent implement đúng `__call__` signature
- [ ] CodeBlockExtractor detect đúng code blocks (test với markdown có ``` blocks)
- [ ] ReadabilityScorer cho score 0-1 (không ngoài range này)
- [ ] Metadata filters trả về đúng subset của documents

### Checklist Bài 3:
- [ ] Cả 3 indexes được build thành công
- [ ] KnowledgeGraphIndex extract ít nhất 10 triplets (cần text đủ dài)
- [ ] Routing accuracy đo được (cần test cases với expected labels)
- [ ] Quality so sánh giữa đúng vs sai index routing

### Debug Snippets:
```python
# Debug KnowledgeGraph — xem triplets được extracted
import networkx as nx
kg_graph = kg_index.get_networkx_graph()
print(f"Nodes: {kg_graph.number_of_nodes()}")
print(f"Edges: {kg_graph.number_of_edges()}")
for u, v, data in list(kg_graph.edges(data=True))[:10]:
    print(f"  ({u}) --[{data.get('label', '?')}]--> ({v})")

# Debug index contents
print(f"VectorStore nodes: {len(vector_index.docstore.docs)}")
for node_id, node in list(vector_index.docstore.docs.items())[:3]:
    print(f"  {node_id}: {node.get_content()[:80]}")

# Debug retrieval
from llama_index.core import get_response_synthesizer
retriever = vector_index.as_retriever(similarity_top_k=3, verbose=True)
nodes = retriever.retrieve("your test query")
for node in nodes:
    print(f"Score: {node.score:.3f} | {node.text[:80]}")
```
