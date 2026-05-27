# Bài Tập — Ngày 21: RAG — Retrieval Augmented Generation

## Bài 1 — Python Documentation QA Bot (Cơ bản)

**Mô tả:**
Xây dựng QA bot về Python, được index từ một set of markdown documents mô tả các Python concepts. Bot có thể trả lời câu hỏi về Python chính xác dựa trên documents, không hallucinate.

**Yêu cầu:**

**Bước 1 — Tạo knowledge base (tự tạo docs):**
```python
# Tạo ít nhất 10 markdown documents về Python topics
# Lưu vào thư mục: ./python_docs/

docs_content = {
    "list_comprehension.md": """
# List Comprehension trong Python

List comprehension là cú pháp ngắn gọn để tạo list mới từ iterable.

## Syntax cơ bản
[expression for item in iterable if condition]

## So sánh với for loop
```python
# For loop truyền thống
squares = []
for x in range(10):
    squares.append(x**2)

# List comprehension - ngắn hơn, Pythonic hơn
squares = [x**2 for x in range(10)]
```

## Nested list comprehension
```python
matrix = [[1,2,3],[4,5,6],[7,8,9]]
flat = [num for row in matrix for num in row]
```

## Khi nào KHÔNG nên dùng
- Logic phức tạp nhiều điều kiện → dùng for loop để dễ đọc hơn
- Side effects (in ra màn hình, ghi file) → for loop
""",
    "asyncio_basics.md": """
# AsyncIO trong Python

## Tại sao cần AsyncIO
Python single-threaded, nhưng có thể handle concurrent I/O với asyncio.
Khác với NodeJS: Python cần declare async explicitly với async/await keywords.

## Core concepts
- Coroutine: function với async def
- Event loop: scheduler chạy coroutines
- Task: scheduled coroutine
- await: yield control về event loop

## Example cơ bản
```python
import asyncio

async def fetch_data(url: str) -> str:
    await asyncio.sleep(1)  # Simulate I/O
    return f"Data from {url}"

async def main():
    # Sequential: 2 seconds total
    result1 = await fetch_data("url1")
    result2 = await fetch_data("url2")

    # Concurrent: 1 second total
    result1, result2 = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
    )

asyncio.run(main())
```

## asyncio vs threading
asyncio: best for I/O-bound (network, disk)
threading: OK for I/O-bound nhưng GIL limits
multiprocessing: best for CPU-bound
""",
    # Thêm ít nhất 8 files nữa về: decorators, generators, context_managers,
    # type_hints, dataclasses, pydantic, fastapi_basics, testing_pytest
}

import os
os.makedirs("./python_docs", exist_ok=True)
for filename, content in docs_content.items():
    with open(f"./python_docs/{filename}", "w") as f:
        f.write(content)
print(f"Created {len(docs_content)} documentation files")
```

**Bước 2 — Build RAG Pipeline:**
```python
def build_python_qa_bot():
    """
    Pipeline:
    1. Load tất cả .md files từ ./python_docs/
    2. Split với chunk_size=500, overlap=100
    3. Embed với text-embedding-3-small
    4. Store trong Chroma (persist)
    5. Create RAG chain với prompt "chỉ dùng thông tin trong docs"
    """
    ...
    return chain

chain = build_python_qa_bot()
```

**Bước 3 — Test queries:**
```python
test_queries = [
    # In-context queries — phải trả lời được
    "List comprehension trong Python là gì?",
    "asyncio.gather() dùng để làm gì?",
    "Khi nào không nên dùng list comprehension?",
    "asyncio khác threading như thế nào?",

    # Out-of-context queries — phải từ chối / admit không biết
    "Python có framework nào cho blockchain không?",
    "Thời tiết hôm nay ở Hanoi thế nào?",
]

for query in test_queries:
    print(f"\nQ: {query}")
    answer = chain.invoke(query)
    print(f"A: {answer[:300]}...")
```

**Expected output:**
```
Q: List comprehension trong Python là gì?
A: List comprehension là cú pháp ngắn gọn để tạo list mới từ iterable.
   Syntax: [expression for item in iterable if condition]
   [Source: list_comprehension.md]

Q: Thời tiết hôm nay ở Hanoi thế nào?
A: Tôi không có thông tin về thời tiết trong tài liệu Python documentation.
   Tôi chỉ có thể trả lời các câu hỏi liên quan đến Python programming.
```

**Hint:**
```python
# Load markdown files
from langchain_community.document_loaders import DirectoryLoader, TextLoader
loader = DirectoryLoader("./python_docs/", glob="**/*.md", loader_cls=TextLoader)

# Thêm source vào prompt để guide citations
def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in docs
    )
```

**Import/version note:** Dùng vector store imports từ package integration riêng (`from langchain_chroma import Chroma`, `from langchain_openai import OpenAIEmbeddings`). Lưu `embedding_model="text-embedding-3-small"` cùng collection; nếu đổi embedding model hoặc dimension, tạo collection mới và re-index thay vì add vào collection cũ.

---

## Bài 2 — Codebase Q&A System (Trung bình)

**Mô tả:**
Xây dựng RAG system có thể trả lời câu hỏi về một Python codebase — "tìm function X ở đâu", "file Y làm gì", "giải thích pattern Z". Dùng Python code files làm knowledge base.

**Yêu cầu:**

**Bước 1 — Setup sample codebase để index:**
```python
# Tạo sample Python project để RAG index
# Hoặc clone một open-source Python project nhỏ
# Gợi ý: dùng code từ các bài học trước (ngày 1-18)

sample_files = {
    "models.py": """
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    id: int
    username: str = Field(min_length=3, max_length=50)
    email: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True

class Product(BaseModel):
    id: int
    name: str
    price: float = Field(gt=0)
    category: str
    tags: List[str] = []

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: float

class Order(BaseModel):
    id: int
    user_id: int
    items: List[OrderItem]
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def total(self) -> float:
        return sum(item.unit_price * item.quantity for item in self.items)
""",
    "services/user_service.py": """
from typing import Optional, List
from models import User
import hashlib

class UserService:
    def __init__(self, db_connection):
        self.db = db_connection
        self._cache = {}

    async def get_user(self, user_id: int) -> Optional[User]:
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        user = await self.db.fetch_one(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        if user:
            user_obj = User(**user)
            self._cache[user_id] = user_obj
            return user_obj
        return None

    async def create_user(self, username: str, email: str, password: str) -> User:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        user_id = await self.db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3) RETURNING id",
            username, email, hashed_password
        )
        return User(id=user_id, username=username, email=email)

    async def get_active_users(self) -> List[User]:
        users = await self.db.fetch_all("SELECT * FROM users WHERE is_active = true")
        return [User(**u) for u in users]
""",
    # Thêm: order_service.py, product_service.py, api/routes.py, utils/validators.py
}
```

**Bước 2 — Build Code-Aware RAG:**
```python
def build_codebase_rag(code_directory: str):
    """
    Đặc điểm cần implement:
    1. Dùng PythonCodeTextSplitter thay vì RecursiveCharacterTextSplitter
       → Giữ function/class boundaries intact
    2. Enrich metadata: filename, function names, class names
    3. Custom prompt biết mình đang answer về Python code
    4. Retrieve k=6 (code cần nhiều context hơn text)
    """

    # Load Python files
    from langchain_community.document_loaders import DirectoryLoader, TextLoader
    from langchain_text_splitters import PythonCodeTextSplitter
    import ast

    loader = DirectoryLoader(
        code_directory,
        glob="**/*.py",
        loader_cls=TextLoader,
    )
    raw_docs = loader.load()

    # Split theo code structure
    splitter = PythonCodeTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(raw_docs)

    # Enrich metadata với code structure info
    def enrich_code_metadata(doc):
        """Extract function/class names từ code chunk"""
        try:
            tree = ast.parse(doc.page_content)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            doc.metadata["functions"] = functions
            doc.metadata["classes"] = classes
            doc.metadata["has_async"] = "async def" in doc.page_content
        except:
            pass
        return doc

    enriched_chunks = [enrich_code_metadata(chunk) for chunk in chunks]

    # Build vectorstore và chain...
    ...

# Test queries
queries = [
    "UserService.get_user() làm gì và khi nào return None?",
    "Tìm tất cả async functions trong codebase",
    "Order model có property gì để tính total price?",
    "Password được hash như thế nào trong user service?",
    "Tìm tất cả nơi dùng cache",
]
```

**Bước 3 — Implement Semantic Code Search:**
```python
def semantic_code_search(vectorstore, query: str, filter_async: bool = False) -> list:
    """
    Search code với optional filters.
    filter_async: chỉ trả về async functions nếu True
    """
    search_kwargs = {"k": 5}

    if filter_async:
        # Chroma filter: chỉ lấy docs có async
        search_kwargs["filter"] = {"has_async": True}

    docs = vectorstore.similarity_search(query, **search_kwargs)

    # Format results với code highlighting
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        functions = doc.metadata.get("functions", [])
        print(f"File: {source}")
        if functions:
            print(f"Functions: {', '.join(functions)}")
        print(f"Code preview:\n{doc.page_content[:300]}\n")

    return docs

# Test
semantic_code_search(vectorstore, "database query with error handling")
semantic_code_search(vectorstore, "user authentication", filter_async=True)
```

**Expected output:**
```
Q: UserService.get_user() làm gì và khi nào return None?

Retrieved:
  File: services/user_service.py
  Functions: get_user, create_user, get_active_users

Answer: UserService.get_user() nhận user_id và:
1. Kiểm tra trong memory cache trước (_cache dict)
2. Nếu không có trong cache, query database
3. Return None khi không tìm thấy user trong DB
4. Cache user object và return nếu tìm thấy
[Source: services/user_service.py, line ~10-20]
```

**Hint:**
- `PythonCodeTextSplitter` trong `langchain_text_splitters`
- `ast.parse()` để extract structure — wrap trong try/except
- Metadata filter trong Chroma: `filter={"key": "value"}`

---

## Bài 3 — Multi-Source RAG với Evaluation (Nâng cao / Challenge)

**Mô tả:**
Xây dựng RAG system production-grade: load từ nhiều nguồn (web + files + API mock), implement hybrid search, đánh giá chất lượng với RAGAS metrics, và build REST API endpoint để serve queries.

**Yêu cầu:**

**Bước 1 — Multi-Source Ingestion Pipeline:**
```python
class MultiSourceIngestionPipeline:
    """
    Load và index documents từ nhiều sources.
    Giống ETL pipeline nhưng cho vector store.
    """

    def __init__(self, vectorstore, embeddings, splitter):
        self.vectorstore = vectorstore
        self.embeddings = embeddings
        self.splitter = splitter
        self.ingested_sources = set()  # Track ingested sources

    def ingest_directory(self, path: str, glob: str = "**/*.md", source_tag: str = None):
        """Ingest từ local directory"""
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        loader = DirectoryLoader(path, glob=glob, loader_cls=TextLoader)
        docs = loader.load()

        # Tag source
        for doc in docs:
            doc.metadata["ingestion_source"] = source_tag or "local_files"
            doc.metadata["ingested_at"] = datetime.now().isoformat()

        return self._process_and_store(docs, source_tag)

    def ingest_urls(self, urls: list, source_tag: str = "web"):
        """Ingest từ web URLs"""
        from langchain_community.document_loaders import WebBaseLoader
        loader = WebBaseLoader(web_paths=urls)
        docs = loader.load()
        for doc in docs:
            doc.metadata["ingestion_source"] = source_tag
        return self._process_and_store(docs, source_tag)

    def ingest_from_api(self, items: list, content_key: str, source_tag: str = "api"):
        """
        Ingest từ API response (list of dicts).
        Giống ETL bước Extract từ REST API.
        """
        docs = [
            Document(
                page_content=item[content_key],
                metadata={k: v for k, v in item.items() if k != content_key,
                          "ingestion_source": source_tag}
            )
            for item in items
        ]
        return self._process_and_store(docs, source_tag)

    def _process_and_store(self, docs: list, source_tag: str) -> dict:
        """Split, embed, và store documents"""
        chunks = self.splitter.split_documents(docs)

        # Deduplicate by content hash
        seen_hashes = set()
        unique_chunks = []
        for chunk in chunks:
            content_hash = hash(chunk.page_content)
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(chunk)

        self.vectorstore.add_documents(unique_chunks)
        self.ingested_sources.add(source_tag)

        return {
            "source": source_tag,
            "raw_docs": len(docs),
            "chunks": len(unique_chunks),
            "deduped": len(chunks) - len(unique_chunks),
        }

    def get_stats(self) -> dict:
        """Thống kê về ingested data"""
        return {
            "sources": list(self.ingested_sources),
            "total_vectors": self.vectorstore._collection.count(),
        }
```

**Bước 2 — Hybrid Search (Vector + BM25):**
```python
# uv add rank_bm25

from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever  # version-sensitive; smoke-test import

def build_hybrid_retriever(vectorstore, documents: list, weights: tuple = (0.5, 0.5)):
    """
    Hybrid search: kết hợp vector search (semantic) + BM25 (keyword)
    weights: (bm25_weight, vector_weight) — tổng phải = 1.0

    WHY hybrid:
    - Vector search: tốt cho semantic similarity ("Python coroutines" → asyncio)
    - BM25: tốt cho exact keyword match ("asyncio.gather" exact function name)
    - Ensemble: best of both worlds
    """
    # Vector retriever
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # BM25 retriever (keyword-based)
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 5

    # Ensemble: RRF (Reciprocal Rank Fusion) để merge results
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=list(weights),
    )

    return ensemble_retriever
```

**Bước 3 — RAG Evaluation với RAGAS:**
```python
# uv add ragas

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,        # Là answer có faithful với context không?
    AnswerRelevancy,     # Answer có relevant với question không?
    ContextRecall,       # Retrieved context có cover ground truth không?
    ContextPrecision,    # Context có precise (ít noise) không?
)
from datasets import Dataset
from langchain_openai import ChatOpenAI

def evaluate_rag_pipeline(chain, retriever, test_cases: list) -> dict:
    """
    Evaluate RAG quality với RAGAS metrics.

    test_cases: list of dicts với keys:
    - question: câu hỏi
    - ground_truth: expected answer (viết tay)
    """
    # Collect predictions
    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for tc in test_cases:
        question = tc["question"]
        ground_truth = tc["ground_truth"]

        # Get answer
        answer = chain.invoke(question)

        # Get retrieved contexts
        contexts = retriever.invoke(question)
        context_texts = [doc.page_content for doc in contexts]

        eval_data["question"].append(question)
        eval_data["answer"].append(answer)
        eval_data["contexts"].append(context_texts)
        eval_data["ground_truth"].append(ground_truth)

    # Create HuggingFace dataset.
    # Nếu RAGAS version pin dùng schema user_input/response/retrieved_contexts/reference,
    # map question/answer/contexts/ground_truth sang các tên đó.
    dataset = Dataset.from_dict(eval_data)

    # Evaluate
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))
    results = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
            ContextPrecision(llm=evaluator_llm),
        ],
    )

    return results

# Test cases — viết ground truth cho một số representative questions
test_cases = [
    {
        "question": "asyncio.gather() dùng để làm gì?",
        "ground_truth": "asyncio.gather() cho phép chạy nhiều coroutines concurrently và đợi tất cả hoàn thành, tương tự Promise.all() trong JavaScript.",
    },
    {
        "question": "Khi nào không nên dùng list comprehension?",
        "ground_truth": "Không nên dùng list comprehension khi logic phức tạp nhiều điều kiện hoặc khi có side effects như in ra màn hình hay ghi file.",
    },
    # Thêm 5-8 test cases nữa
]
```

**Bước 4 — FastAPI REST Endpoint:**
```python
# uv add fastapi uvicorn

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio

app = FastAPI(title="Python Knowledge RAG API", version="1.0.0")

class QueryRequest(BaseModel):
    question: str
    filter_source: Optional[str] = None  # Filter by ingestion source
    top_k: int = 4

class QueryResponse(BaseModel):
    answer: str
    sources: list
    confidence: float
    retrieved_chunks: int

# Global RAG chain (initialize on startup)
rag_chain = None

@app.on_event("startup")
async def startup():
    global rag_chain
    # Initialize RAG pipeline
    rag_chain = build_rag_pipeline()  # Your function from above
    print("RAG pipeline ready!")

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not rag_chain:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        # Run in thread pool (langchain chain is sync)
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rag_chain.invoke(request.question)
        )

        return QueryResponse(
            answer=result["answer"] if isinstance(result, dict) else result,
            sources=result.get("sources", []) if isinstance(result, dict) else [],
            confidence=0.85,  # Mock — thực tế tính từ similarity scores
            retrieved_chunks=request.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "vectors": vectorstore._collection.count()}

@app.get("/stats")
async def stats():
    return pipeline.get_stats()

# Run: uvicorn main:app --reload
# Test: curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"question": "asyncio là gì?"}'
```

**Bước 5 — Integration Test:**
```python
def full_integration_test():
    """
    Test toàn bộ pipeline end-to-end
    """
    print("1. Initializing components...")
    # Setup vectorstore, embeddings, splitter
    ...

    print("2. Ingesting from multiple sources...")
    pipeline = MultiSourceIngestionPipeline(...)
    r1 = pipeline.ingest_directory("./python_docs/")
    r2 = pipeline.ingest_from_api(mock_api_data, content_key="content")
    print(f"   Ingested: {r1}, {r2}")

    print("3. Building hybrid retriever...")
    retriever = build_hybrid_retriever(vectorstore, all_docs)

    print("4. Testing queries...")
    for query in test_queries:
        answer = chain.invoke(query)
        print(f"   Q: {query[:50]}...")
        print(f"   A: {answer[:100]}...\n")

    print("5. Running RAGAS evaluation...")
    eval_results = evaluate_rag_pipeline(chain, retriever, test_cases)
    print(f"   Faithfulness: {eval_results['faithfulness']:.2f}")
    print(f"   Answer Relevancy: {eval_results['answer_relevancy']:.2f}")

    print("6. Generating improvement recommendations...")
    # Dùng LLM để analyze eval results và suggest improvements
    ...

full_integration_test()
```

**Expected output:**
```
1. Initializing components...
   Chroma vectorstore ready
   Embeddings: text-embedding-3-small

2. Ingesting from multiple sources...
   Source: local_files - 8 docs, 45 chunks
   Source: api - 20 docs, 78 chunks
   Total vectors: 123

3. Building hybrid retriever...
   BM25 + Vector ensemble ready (50/50 weights)

4. Testing queries...
   Q: asyncio.gather() dùng để làm gì?...
   A: asyncio.gather() cho phép chạy nhiều coroutines concurrently...

5. Running RAGAS evaluation...
   Faithfulness:       0.87  ✓ (> 0.8 is good)
   Answer Relevancy:   0.92  ✓
   Context Recall:     0.78  ! (needs improvement)
   Context Precision:  0.83  ✓

6. Improvement Recommendations:
   - Context Recall thấp: tăng k từ 4 lên 6
   - Xem xét chunk size nhỏ hơn (500 → 300) để precise retrieval
   - Thêm documents về các topics còn thiếu
```

**Bonus Challenges:**
- Implement incremental indexing: chỉ re-index documents bị thay đổi (check file mtime)
- Add MMR (Maximal Marginal Relevance) retrieval để avoid duplicate chunks
- Build simple CLI interface: `python rag_cli.py --query "asyncio là gì?"`
- Export RAGAS evaluation report sang HTML

---

## 🔍 Gợi ý kiểm tra kết quả

### Checklist Bài 1:
```python
# Test RAG returns correct info từ docs
chain = build_python_qa_bot()

# Must answer from context
answer = chain.invoke("List comprehension syntax là gì?")
assert "[" in answer or "expression" in answer.lower(), "Phải mention syntax"

# Must refuse out-of-context
answer_oc = chain.invoke("Python có framework blockchain không?")
assert any(phrase in answer_oc.lower() for phrase in [
    "không có", "không tìm thấy", "không đủ thông tin", "ngoài phạm vi"
]), "Phải từ chối out-of-context questions"

print("✓ RAG returns correct answers and refuses out-of-context")
```

### Checklist Bài 2:
```python
# Test code-aware retrieval
vectorstore = build_codebase_rag("./sample_project/")

# Search by function behavior
results = vectorstore.similarity_search("hash password user", k=3)
assert any("hashlib" in doc.page_content for doc in results), \
    "Phải tìm được hashing code"

# Test metadata filter
async_results = vectorstore.similarity_search(
    "async database query",
    k=5,
    filter={"has_async": True}
)
assert all(doc.metadata.get("has_async") for doc in async_results), \
    "Filter phải chỉ trả async code"

print("✓ Code search works with metadata filtering")
```

### Checklist Bài 3:
```python
# Test multi-source ingestion
pipeline = MultiSourceIngestionPipeline(...)
result = pipeline.ingest_directory("./python_docs/")
assert result["chunks"] > 0
assert "local_files" in pipeline.ingested_sources

# Test deduplication
result2 = pipeline.ingest_directory("./python_docs/")  # Re-ingest same files
# Total vectors should not double (dedup working)
# Note: Chroma doesn't auto-dedup — verify your dedup logic

print("✓ Multi-source ingestion working")

# Verify RAGAS scores reasonable
assert eval_results["faithfulness"] > 0.7, "Faithfulness phải > 0.7"
assert eval_results["answer_relevancy"] > 0.7, "Relevancy phải > 0.7"
print("✓ RAG quality metrics acceptable")
```

### Debug RAG Issues:
```python
# Debugging tool: xem retrieved documents cho query
def debug_retrieval(retriever, query: str):
    """Xem RAG đang retrieve gì"""
    docs = retriever.invoke(query)
    print(f"\n=== Retrieval Debug: '{query}' ===")
    print(f"Retrieved {len(docs)} chunks:")
    for i, doc in enumerate(docs):
        print(f"\n[Chunk {i+1}]")
        print(f"Source: {doc.metadata.get('source')}")
        print(f"Content: {doc.page_content[:200]}")
        print(f"Metadata: {doc.metadata}")

# Nếu answer sai, check retrieval trước!
debug_retrieval(retriever, "asyncio gather concurrent")
```
