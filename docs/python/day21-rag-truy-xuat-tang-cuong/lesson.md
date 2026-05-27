# Ngày 21: RAG — Retrieval Augmented Generation

## 🎯 Mục tiêu học tập
- Hiểu tại sao RAG tồn tại và problem nó giải quyết
- Build pipeline RAG hoàn chỉnh từ document loading đến generation
- Sử dụng thành thạo Document Loaders và Text Splitters
- Hiểu Embedding models — cách text biến thành vectors
- Tích hợp Vector Stores: Chroma, Qdrant, pgvector, Pinecone, Weaviate
- Optimize RAG pipeline cho accuracy và performance

---

> **Version/import note:** LangChain ecosystem tách nhiều integration ra package riêng. Trong bài này ưu tiên imports hiện hành như `from langchain_chroma import Chroma`, `from langchain_qdrant import QdrantVectorStore`, `from langchain_postgres import PGVector`, `from langchain_openai import OpenAIEmbeddings`, và `from langchain_text_splitters import ...`. Nếu gặp snippet cũ dùng `langchain_community.vectorstores.Chroma` hoặc `langchain.vectorstores.*`, hãy check target LangChain version và smoke-test imports trước khi dùng trong lab.

## 🔄 So sánh với NodeJS

| Khái niệm NodeJS/TypeScript | Tương đương RAG | Ghi chú |
|---|---|---|
| Full-text search (Elasticsearch) | Vector similarity search | Semantic search vs keyword search |
| `fs.readFile()` | Document Loaders | Hỗ trợ nhiều format: PDF, Word, HTML, etc. |
| String splitting / chunking | Text Splitters | Smart split theo semantic boundaries |
| Hash/fingerprint của document | Embedding vector | Text → N-dimensional float array; N phụ thuộc model |
| Elasticsearch index | Vector Store | Lưu và query vectors efficiently |
| `SELECT ... WHERE ... LIKE '%query%'` | `vectorstore.similarity_search(query)` | Ngữ nghĩa thay vì keyword |
| Redis cache cho search results | Vector cache | Cache embeddings để tránh re-compute |
| Microservice với specialized knowledge | RAG system | LLM + external knowledge base |

**Vấn đề cốt lõi RAG giải quyết:**
- NodeJS app: bạn có thể query database, search Elasticsearch — nhưng LLM không thể
- RAG: bridge giữa LLM (generation) và external knowledge (retrieval)
- Giống cho LLM quyền "search" trong knowledge base của bạn

---

## 📖 Lý thuyết

### Section 1: RAG Architecture — Tại Sao Cần RAG?

**WHY — Vấn đề của LLM thuần:**

LLM có ba limitation lớn:
1. **Knowledge cutoff** — Model chỉ biết thông tin đến training date (2024). Company docs, new releases, internal data → LLM không biết
2. **Hallucination** — Khi không biết, LLM fabricate thông tin trông có vẻ đúng
3. **Context window limit** — Không thể nhét toàn bộ knowledge base vào prompt (và rất tốn tiền)

**RAG Pattern giải quyết:**
```
User Question
     ↓
[Retriever] — search trong vector store
     ↓
Top-K relevant documents
     ↓
[Generator] — LLM generates answer dựa trên retrieved docs
     ↓
Answer (với citations từ real documents)
```

**So sánh với alternatives:**

| Approach | Pros | Cons |
|---|---|---|
| Fine-tuning | Model "learns" knowledge | Expensive, slow, hard to update |
| Stuffing context | Simple | Context window limit, expensive |
| RAG | Scalable, updateable, accurate | More complex pipeline |
| RAG + Fine-tuning | Best accuracy | Most complex, most expensive |

**Real-world use cases của RAG:**
- Customer support bot biết toàn bộ product documentation
- Internal knowledge base search (Confluence, Notion)
- Legal/medical document Q&A
- Codebase Q&A (search trong code + explain)
- News/research article Q&A với citations

```
RAG Full Architecture:

INDEXING PHASE (one-time):
Documents → Load → Split → Embed → Store in Vector DB

QUERY PHASE (real-time):
Question → Embed → Search Vector DB → Retrieve Docs → LLM → Answer
```

---

### Section 2: Document Loaders

**WHY — Tại sao cần Document Loaders thay vì đọc file thủ công?**

Raw file reading:
```python
with open("doc.pdf", "rb") as f:
    content = f.read()  # Binary — không đọc được text
```

Mỗi format cần library riêng: PDF (pypdf), Word (python-docx), HTML (beautifulsoup4), etc. Document Loaders chuẩn hóa tất cả thành `List[Document]` với metadata.

```python
# uv add langchain langchain-community pypdf docx2txt beautifulsoup4 unstructured

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    WebBaseLoader,
    DirectoryLoader,
    CSVLoader,
    JSONLoader,
)
from langchain_core.documents import Document

# --- TextLoader — đơn giản nhất ---
loader = TextLoader("readme.txt", encoding="utf-8")
docs = loader.load()
print(f"Loaded: {len(docs)} document(s)")
print(f"Content preview: {docs[0].page_content[:200]}")
print(f"Metadata: {docs[0].metadata}")
# Metadata: {'source': 'readme.txt'}

# --- PyPDFLoader — PDF (mỗi page = 1 Document) ---
loader = PyPDFLoader("document.pdf")
docs = loader.load()
print(f"PDF pages: {len(docs)}")
for i, doc in enumerate(docs[:3]):
    print(f"Page {i+1}: {doc.page_content[:100]}...")
    print(f"Metadata: {doc.metadata}")
    # Metadata: {'source': 'document.pdf', 'page': 0}

# --- WebBaseLoader — scrape web page ---
import bs4

loader = WebBaseLoader(
    web_paths=["https://python.langchain.com/docs/introduction/"],
    bs_kwargs={
        "parse_only": bs4.SoupStrainer(
            class_=("article", "main-content")  # Chỉ lấy main content
        )
    },
)
docs = loader.load()
print(f"Web content length: {len(docs[0].page_content)} chars")

# --- DirectoryLoader — load toàn bộ thư mục ---
loader = DirectoryLoader(
    path="./docs/",           # Thư mục cần load
    glob="**/*.md",           # Pattern — chỉ .md files
    loader_cls=TextLoader,    # Loader để dùng cho mỗi file
    show_progress=True,       # Progress bar (hữu ích khi load nhiều file)
    use_multithreading=True,  # Parallel loading
)
docs = loader.load()
print(f"Loaded {len(docs)} markdown files")
```

```python
# --- CSVLoader — load CSV với custom column mapping ---
loader = CSVLoader(
    file_path="products.csv",
    source_column="product_id",   # Column dùng làm source metadata
    csv_args={"delimiter": ","},
)
docs = loader.load()
# Mỗi row = 1 Document, tất cả columns đều trong page_content
print(docs[0].page_content)
# Output: "product_id: P001\nname: Widget\nprice: 9.99\ncategory: Electronics"

# --- JSONLoader — load JSON với jq parsing ---
loader = JSONLoader(
    file_path="data.json",
    jq_schema=".items[]",           # jq query để extract records
    content_key="description",      # Field nào là main content
    metadata_func=lambda record, metadata: {
        **metadata,
        "id": record.get("id"),
        "category": record.get("category"),
    }
)
docs = loader.load()
```

```python
# --- Custom Loader — khi không có built-in loader ---
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from typing import Iterator
import requests

class APIDocumentLoader(BaseLoader):
    """
    Custom loader: load documents từ REST API.
    Giống viết custom data source connector.
    """

    def __init__(self, api_url: str, api_key: str, endpoint: str):
        self.api_url = api_url
        self.api_key = api_key
        self.endpoint = endpoint

    def lazy_load(self) -> Iterator[Document]:
        """
        lazy_load() dùng Generator — memory-efficient cho large datasets.
        Giống Node.js Readable Stream với backpressure.
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        page = 1

        while True:
            response = requests.get(
                f"{self.api_url}/{self.endpoint}",
                headers=headers,
                params={"page": page, "per_page": 50},
            )
            data = response.json()

            if not data.get("items"):
                break  # No more data

            for item in data["items"]:
                yield Document(
                    page_content=item["content"],
                    metadata={
                        "source": f"{self.api_url}/{self.endpoint}/{item['id']}",
                        "id": item["id"],
                        "created_at": item["created_at"],
                        "author": item.get("author", "unknown"),
                        "tags": item.get("tags", []),
                    }
                )

            page += 1

    def load(self) -> list:
        """load() = collect tất cả từ lazy_load()"""
        return list(self.lazy_load())

# Usage
# loader = APIDocumentLoader("https://api.company.com", "sk-...", "knowledge-base")
# docs = loader.load()
```

---

### Section 3: Text Splitters

**WHY — Tại sao cần Text Splitters?**

Documents thường rất dài (hàng nghìn, hàng trăm nghìn tokens). Nếu nhét nguyên vào vector store:
1. **Context window**: LLM không thể process document quá dài
2. **Search precision**: Khi search, muốn tìm đúng đoạn relevant, không phải cả document dài
3. **Cost**: Embedding một document 100K tokens vs 1000 chunks of 200 tokens — cost khác nhau

**Challenge của text splitting:**
- Split quá nhỏ: mất context, không đủ thông tin
- Split quá lớn: search không precise, LLM context overflow
- Split giữa câu: mất ngữ nghĩa

```python
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    MarkdownTextSplitter,
    PythonCodeTextSplitter,
    TokenTextSplitter,
)
from langchain_core.documents import Document

# --- RecursiveCharacterTextSplitter — best default choice ---
# WHY "Recursive": thử split bằng "\n\n" trước, nếu chunk vẫn quá lớn thì split "\n", rồi " ", rồi ""
# Giữ ngữ nghĩa tốt hơn simple character split

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,       # Max characters per chunk
    chunk_overlap=200,     # Overlap giữa chunks — preserve context
    length_function=len,   # Dùng character count (default)
    separators=["\n\n", "\n", ". ", " ", ""],  # Thứ tự ưu tiên
)

long_text = """
Python là ngôn ngữ lập trình bậc cao, tổng quát, được tạo bởi Guido van Rossum.

Python có triết lý thiết kế nhấn mạnh vào code readability, sử dụng indentation đáng kể.

Ngôn ngữ này hỗ trợ nhiều paradigm lập trình: procedural, object-oriented, và functional.

Python được dùng rộng rãi trong: web development, data science, AI/ML, automation, scripting.
""" * 20  # Nhân để tạo text dài

chunks = splitter.split_text(long_text)
print(f"Original length: {len(long_text)} chars")
print(f"Number of chunks: {len(chunks)}")
print(f"First chunk ({len(chunks[0])} chars):\n{chunks[0][:200]}...")
print(f"\nChunk overlap: chunks[0][-100:] ≈ chunks[1][:100]")

# Split Documents (preserve metadata)
doc = Document(page_content=long_text, metadata={"source": "python_intro.txt"})
split_docs = splitter.split_documents([doc])
print(f"\nSplit into {len(split_docs)} documents")
print(f"Each doc has metadata: {split_docs[0].metadata}")
# Metadata được copy sang mỗi chunk: {'source': 'python_intro.txt'}
```

```python
# --- TokenTextSplitter — split theo tokens không phải characters ---
# Chính xác hơn khi cần fit trong context window

splitter = TokenTextSplitter(
    chunk_size=256,      # Max tokens per chunk
    chunk_overlap=50,    # Overlap in tokens
    encoding_name="cl100k_base",  # OpenAI's tokenizer
)

# Lưu ý: "hello world" = 2 tokens, "supercalifragilistic" = nhiều tokens hơn
chunks = splitter.split_text("Your long document text here...")
```

```python
# --- MarkdownTextSplitter — split theo Markdown structure ---
# Giữ headers, sections intact

markdown_text = """
# Introduction

Python là ngôn ngữ lập trình phổ biến.

## Features

- Easy to learn
- Large ecosystem

### Performance

Python không phải ngôn ngữ nhanh nhất, nhưng đủ fast cho hầu hết use cases.

## Installation

```bash
python --version
```
"""

md_splitter = MarkdownTextSplitter(chunk_size=200, chunk_overlap=50)
chunks = md_splitter.split_text(markdown_text)
for i, chunk in enumerate(chunks):
    print(f"\n--- Chunk {i+1} ---")
    print(chunk[:150])
```

```python
# --- PythonCodeTextSplitter — split code theo functions/classes ---
# Giữ function/class boundaries intact

python_code = '''
import os
import sys

class DataProcessor:
    """Process data files."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> list:
        """Load data from file."""
        with open(self.path) as f:
            return f.readlines()

    def process(self, data: list) -> list:
        """Process loaded data."""
        return [line.strip() for line in data if line.strip()]

def main():
    """Main entry point."""
    processor = DataProcessor("data.txt")
    data = processor.load()
    result = processor.process(data)
    print(f"Processed {len(result)} items")

if __name__ == "__main__":
    main()
'''

code_splitter = PythonCodeTextSplitter(chunk_size=300, chunk_overlap=50)
chunks = code_splitter.split_text(python_code)
print(f"Code split into {len(chunks)} chunks")
for i, chunk in enumerate(chunks):
    print(f"\n--- Chunk {i+1} ---\n{chunk}")
```

```python
# --- Metadata Enrichment — thêm metadata hữu ích vào chunks ---
# Metadata giúp filter khi search (VD: chỉ search trong docs của năm 2024)

def enrich_metadata(docs: list, extra_metadata: dict = None) -> list:
    """Thêm metadata vào tất cả documents"""
    from datetime import datetime

    enriched = []
    for i, doc in enumerate(docs):
        new_metadata = {
            **doc.metadata,
            "chunk_index": i,
            "chunk_total": len(docs),
            "indexed_at": datetime.now().isoformat(),
            "content_length": len(doc.page_content),
        }
        if extra_metadata:
            new_metadata.update(extra_metadata)

        enriched.append(Document(
            page_content=doc.page_content,
            metadata=new_metadata,
        ))

    return enriched

# Usage
docs = splitter.split_documents(loaded_docs)
enriched_docs = enrich_metadata(
    docs,
    extra_metadata={"department": "engineering", "version": "2024-Q1"}
)
```

---

### Section 4: Embedding Models

**WHY — Tại sao cần Embeddings?**

Máy tính không hiểu text. Embedding chuyển text thành vector (array of floats) nơi:
- Các texts có nghĩa tương tự → vectors gần nhau trong không gian
- Cho phép tính "semantic similarity" bằng cosine similarity

Ví dụ direct:
- "Python programming language" → `[0.234, -0.891, 0.123, ...]` (dimension phụ thuộc embedding model)
- "Python snake reptile" → `[0.891, 0.123, -0.456, ...]` (rất khác!)
- "JavaScript programming" → `[0.201, -0.867, 0.145, ...]` (gần với Python programming)

```python
# --- OpenAI Embeddings — chất lượng cao, có cost ---
from langchain_openai import OpenAIEmbeddings

embeddings_model = OpenAIEmbeddings(
    model="text-embedding-3-small",  # Rẻ hơn, 1536 dims
    # model="text-embedding-3-large",  # Chất lượng cao hơn, 3072 dims
)

# Embed một string
single_embedding = embeddings_model.embed_query("Python programming")
print(f"Embedding dimensions: {len(single_embedding)}")
print(f"First 5 values: {single_embedding[:5]}")
# [0.00234, -0.00891, 0.00123, ...]

# Embed nhiều documents (batch — hiệu quả hơn)
texts = [
    "Python programming language",
    "Python snake reptile",
    "JavaScript web development",
    "Machine learning with Python",
]
doc_embeddings = embeddings_model.embed_documents(texts)
print(f"Embedded {len(doc_embeddings)} texts")
print(f"Each embedding: {len(doc_embeddings[0])} dimensions")
```

> **Dimension caveat:** Query embedding và document embedding phải cùng model/cùng dimension. Một collection/index trong Chroma, Qdrant, pgvector thường được tạo với vector size cố định; đổi từ `text-embedding-3-small` sang model khác có thể cần tạo collection mới và re-index toàn bộ documents.

```python
# --- Tính Cosine Similarity để verify embeddings ---
import numpy as np
from langchain_openai import OpenAIEmbeddings

def cosine_similarity(v1: list, v2: list) -> float:
    """Đo độ tương tự giữa hai vectors. Range: -1 (opposite) to 1 (identical)"""
    v1, v2 = np.array(v1), np.array(v2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

texts = [
    "Python programming language created by Guido",     # Ref
    "Python is a popular general-purpose language",     # Similar
    "JavaScript is used for web development",           # Related (programming)
    "The python snake lives in tropical forests",       # Different meaning
    "Data science with Python and pandas",              # Related to programming
]

reference = embeddings_model.embed_query(texts[0])
others = embeddings_model.embed_documents(texts[1:])

print(f"Reference: '{texts[0]}'")
print()
for text, embedding in zip(texts[1:], others):
    similarity = cosine_similarity(reference, embedding)
    bar = "█" * int(similarity * 20)
    print(f"Similarity: {similarity:.3f} {bar}")
    print(f"  → '{text}'")

# Expected output:
# Similarity: 0.891 ████████████████████  → 'Python is a popular...'
# Similarity: 0.612 ████████████          → 'JavaScript is used...'
# Similarity: 0.234 ████                  → 'The python snake...'
# Similarity: 0.756 ███████████████       → 'Data science with Python...'
```

```python
# --- Local Embeddings với sentence-transformers ---
# uv add sentence-transformers
# Ưu điểm: free, privacy (data không rời khỏi machine), offline
# Nhược điểm: cần RAM/GPU, setup phức tạp hơn

from langchain_huggingface import HuggingFaceEmbeddings  # uv add langchain-huggingface

# Nhiều model options:
# - all-MiniLM-L6-v2: nhỏ, nhanh, good quality (22M params)
# - all-mpnet-base-v2: tốt hơn, chậm hơn (109M params)
# - multilingual-e5-large: hỗ trợ tiếng Việt và nhiều ngôn ngữ

embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},  # Dùng "cuda" nếu có GPU
    encode_kwargs={"normalize_embeddings": True},  # Chuẩn hóa cho cosine similarity
)

# API giống OpenAI embeddings
embedding = embeddings_model.embed_query("Hello world")
print(f"Local embedding dims: {len(embedding)}")  # 384 dimensions

# Cho tiếng Việt
multilingual = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-small",
)
viet_embedding = multilingual.embed_query("Xin chào thế giới")
print(f"Vietnamese embedding dims: {len(viet_embedding)}")
```

```python
# --- Embedding cost calculator ---
def estimate_embedding_cost(texts: list, model: str = "text-embedding-3-small") -> dict:
    """
    Ước tính chi phí embedding.
    OpenAI: text-embedding-3-small = $0.02/1M tokens
    """
    pricing = {
        "text-embedding-3-small": 0.02 / 1_000_000,   # per token
        "text-embedding-3-large": 0.13 / 1_000_000,
        "text-embedding-ada-002": 0.10 / 1_000_000,    # old model
    }

    # Estimate tokens: ~4 chars per token (rough estimate)
    total_chars = sum(len(t) for t in texts)
    estimated_tokens = total_chars / 4
    cost = estimated_tokens * pricing.get(model, 0.02 / 1_000_000)

    return {
        "num_texts": len(texts),
        "total_chars": total_chars,
        "estimated_tokens": int(estimated_tokens),
        "estimated_cost_usd": round(cost, 6),
        "model": model,
    }

# Trước khi embed large dataset, estimate cost trước
docs = ["..." * 500 for _ in range(10000)]  # 10K documents
estimate = estimate_embedding_cost(docs)
print(f"Embedding {estimate['num_texts']} docs sẽ tốn ≈ ${estimate['estimated_cost_usd']:.4f}")
```

---

### Section 5: Vector Stores

**WHY — Tại sao cần Vector Store chuyên biệt?**

Naive approach: lưu embeddings trong list, loop để tính similarity → O(n) với n = số documents.

Vector Store dùng algorithms như HNSW (Hierarchical Navigable Small World) để approximate nearest-neighbor search nhanh hơn scan toàn bộ. Latency thực tế phụ thuộc số vector, dimension, index params, filter metadata, hardware, và recall target; đừng assume mọi database đều O(log n) hoặc "millisecond" ở mọi workload.

Giống: Elasticsearch cho text search, nhưng Vector Store cho semantic search.

```python
# --- Chroma — Local Vector Store, best for development ---
# uv add chromadb langchain-chroma

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Tạo documents
documents = [
    Document(page_content="Python là ngôn ngữ lập trình interpreted, dynamically typed", metadata={"topic": "python", "level": "basic"}),
    Document(page_content="asyncio là module Python cho asynchronous programming với event loop", metadata={"topic": "asyncio", "level": "intermediate"}),
    Document(page_content="FastAPI là modern web framework cho Python, hỗ trợ async natively", metadata={"topic": "fastapi", "level": "intermediate"}),
    Document(page_content="SQLAlchemy là ORM phổ biến nhất cho Python, hỗ trợ nhiều databases", metadata={"topic": "database", "level": "intermediate"}),
    Document(page_content="pytest là testing framework tiêu chuẩn cho Python projects", metadata={"topic": "testing", "level": "basic"}),
    Document(page_content="Docker container hóa Python applications, giúp deployment consistent", metadata={"topic": "devops", "level": "basic"}),
    Document(page_content="Redis là in-memory data store, dùng làm cache hoặc message broker", metadata={"topic": "infrastructure", "level": "basic"}),
    Document(page_content="Pydantic là library Python cho data validation với type hints", metadata={"topic": "python", "level": "intermediate"}),
]

# In-memory Chroma (không persist — tốt cho testing)
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
)

# Persistent Chroma (lưu vào disk)
vectorstore_persistent = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    persist_directory="./chroma_db",  # Lưu vào thư mục này
    collection_name="python_knowledge",
)

# Load existing persistent store
vectorstore_loaded = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings,
    collection_name="python_knowledge",
)
```

```python
# --- Similarity Search ---
# Basic search — trả về top-k documents

results = vectorstore.similarity_search(
    query="làm thế nào để code async trong Python?",
    k=3,  # Top 3 results
)
for doc in results:
    print(f"Content: {doc.page_content}")
    print(f"Metadata: {doc.metadata}")
    print()

# Search với score — xem similarity score
results_with_score = vectorstore.similarity_search_with_score(
    query="async programming Python",
    k=3,
)
for doc, score in results_with_score:
    print(f"Score: {score:.4f} | {doc.page_content[:80]}...")
    # Score nhỏ hơn = similar hơn (distance, not similarity!)

# Filtered search — chỉ search trong subset
results_filtered = vectorstore.similarity_search(
    query="Python libraries",
    k=3,
    filter={"level": "intermediate"},  # Chroma filter syntax
)
```

```python
# --- Incremental updates — thêm documents vào existing store ---

new_docs = [
    Document(
        page_content="Celery là distributed task queue, dùng với Redis hoặc RabbitMQ",
        metadata={"topic": "infrastructure", "level": "advanced"}
    ),
    Document(
        page_content="Alembic là database migration tool cho SQLAlchemy",
        metadata={"topic": "database", "level": "advanced"}
    ),
]

# Thêm documents mà không cần rebuild toàn bộ index
vectorstore.add_documents(new_docs)

# Delete documents
ids_to_delete = ["doc_id_1", "doc_id_2"]
# vectorstore.delete(ids=ids_to_delete)

# Get collection info
print(f"Total documents: {vectorstore._collection.count()}")
```

```python
# --- Qdrant — Production Vector Store ---
# uv add qdrant-client langchain-qdrant

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Option 1: In-memory Qdrant (development/testing)
client = QdrantClient(":memory:")

# Option 2: Local Qdrant server
# client = QdrantClient("http://localhost:6333")
# docker run -p 6333:6333 qdrant/qdrant

# Option 3: Qdrant Cloud (production)
# client = QdrantClient(
#     url="https://YOUR-CLUSTER.qdrant.io",
#     api_key="your-api-key",
# )

COLLECTION_NAME = "python_knowledge"
VECTOR_SIZE = 1536  # text-embedding-3-small dimensions

# Tạo collection nếu chưa có
# VECTOR_SIZE phải match embedding model. Nếu đổi model/dimension,
# tạo collection mới hoặc re-index; không mix vectors khác dimension.
if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,  # Cosine similarity
        ),
    )

# Tạo vectorstore từ existing collection
vectorstore = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

# Thêm documents
documents = [
    Document(
        page_content="FastAPI automatic generates OpenAPI documentation",
        metadata={"source": "fastapi_docs", "version": "0.100"}
    ),
]

vectorstore.add_documents(documents)

# Search với filter (Qdrant có powerful filter system)
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = vectorstore.similarity_search(
    query="web API Python",
    k=3,
    filter=Filter(
        must=[FieldCondition(key="metadata.source", match=MatchValue(value="fastapi_docs"))]
    ),
)
```

```python
# --- pgvector — PostgreSQL Vector Extension ---
# Tốt nhất khi bạn đã dùng PostgreSQL
# uv add psycopg2-binary pgvector langchain-postgres

from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings

# Connection string
CONNECTION_STRING = "postgresql+psycopg2://user:password@localhost:5432/mydb"

# Hoặc từ environment
# CONNECTION_STRING = os.getenv("DATABASE_URL")

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Tạo vectorstore — tự động tạo table nếu chưa có
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name="python_knowledge",
    connection=CONNECTION_STRING,
    use_jsonb=True,  # Metadata stored as JSONB (queryable)
)

# Từ documents
vectorstore = PGVector.from_documents(
    documents=documents,
    embedding=embeddings,
    collection_name="python_knowledge",
    connection=CONNECTION_STRING,
)

# Search (same API như Chroma và Qdrant!)
results = vectorstore.similarity_search("Python async", k=3)

# Điểm đặc biệt của pgvector: có thể dùng SQL trực tiếp
# SELECT content, metadata, embedding <=> query_vector AS distance
# FROM langchain_pg_embedding
# WHERE metadata->>'topic' = 'asyncio'
# ORDER BY distance
# LIMIT 3;
```

---

### Section 6: RAG Pipeline Hoàn Chỉnh

**Kết hợp tất cả components thành production-ready RAG:**

```python
# --- Simple RAG Pipeline ---
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_rag_pipeline(docs_path: str):
    """
    Build RAG pipeline từ đầu.
    Giống Express app với search middleware.
    """
    # Step 1: Load documents
    loader = DirectoryLoader(docs_path, glob="**/*.md", loader_cls=TextLoader)
    raw_docs = loader.load()
    print(f"Loaded {len(raw_docs)} documents")

    # Step 2: Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"Split into {len(chunks)} chunks")

    # Step 3: Create embeddings and store
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db",
    )
    print(f"Indexed {vectorstore._collection.count()} vectors")

    # Step 4: Create retriever
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},  # Retrieve top 4 chunks
    )

    # Step 5: RAG prompt
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", """Bạn là assistant thông minh. Trả lời câu hỏi DỰA TRÊN context được cung cấp.
Nếu context không đủ thông tin, hãy nói rõ và không được bịa đặt.
Luôn cite nguồn từ context (nêu tên file/section).

Context:
{context}
"""),
        ("human", "{question}"),
    ])

    # Step 6: LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Step 7: Format retrieved docs
    def format_docs(docs):
        formatted = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            formatted.append(f"[Source: {source}]\n{doc.page_content}")
        return "\n\n---\n\n".join(formatted)

    # Step 8: RAG Chain
    # Đây là LCEL chain: input → retrieve → format → prompt → LLM → output
    rag_chain = (
        {
            "context": retriever | format_docs,  # Retrieve và format docs
            "question": RunnablePassthrough(),   # Pass question through unchanged
        }
        | rag_prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain

# Usage
chain = build_rag_pipeline("./my_docs/")
answer = chain.invoke("How does Python asyncio work?")
print(answer)
```

```python
# --- Advanced RAG với Multi-Query Retrieval ---
# WHY: Một query có thể miss relevant docs
# Multi-Query: generate multiple query variants → retrieve cho tất cả → merge results

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
# MultiQueryRetriever là API classic/version-sensitive; smoke-test theo version pin.
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Multi-query retriever: tự động generate 3 query variants
multi_query_retriever = MultiQueryRetriever.from_llm(
    retriever=retriever,
    llm=llm,
)

# Original query: "Python async?"
# Generated queries:
# 1. "How does Python handle asynchronous programming?"
# 2. "What is asyncio in Python and how to use it?"
# 3. "Python coroutines and event loop explanation"
# → Retrieve cho cả 3, dedup, merge

docs = multi_query_retriever.invoke("Python async?")
print(f"Retrieved {len(docs)} unique documents")
```

```python
# --- RAG với Reranking ---
# WHY: Vector similarity không phải lúc nào cũng = relevant nhất
# Reranker là separate model đánh giá relevance sau khi retrieve

# Compression retriever/document compressor là API classic/version-sensitive.
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Compressor: dùng LLM để extract chỉ relevant portions
compressor = LLMChainExtractor.from_llm(llm)

# Compression retriever: retrieve rộng (k=10), compress xuống relevant content
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 10}),
)

compressed_docs = compression_retriever.invoke("Python OOP patterns")
for doc in compressed_docs:
    print(f"Compressed content: {doc.page_content[:200]}")
```

```python
# --- RAG với Citations ---
# Production feature: trả về answer kèm sources

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field
from typing import List
from langchain_core.output_parsers import PydanticOutputParser

class AnswerWithSources(BaseModel):
    answer: str = Field(description="Câu trả lời đầy đủ")
    sources: List[str] = Field(description="List của sources được dùng để trả lời")
    confidence: float = Field(description="Mức độ tự tin 0.0-1.0 dựa trên context")
    has_sufficient_context: bool = Field(description="Context có đủ thông tin không")

def build_cited_rag(vectorstore):
    """RAG chain trả về answer với citations"""
    parser = PydanticOutputParser(pydantic_object=AnswerWithSources)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Trả lời câu hỏi dựa trên context.
Context:
{context}

{format_instructions}

Nếu context không đủ thông tin, set has_sufficient_context=false và confidence thấp."""),
        ("human", "{question}"),
    ])

    def format_docs_with_sources(docs):
        formatted = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            formatted.append(f"[{source}]: {doc.page_content}")
        return "\n\n".join(formatted)

    def extract_sources(docs):
        return [doc.metadata.get("source", "unknown") for doc in docs]

    chain = (
        {
            "context": retriever | format_docs_with_sources,
            "question": RunnablePassthrough(),
            "format_instructions": lambda _: parser.get_format_instructions(),
        }
        | prompt
        | llm
        | parser
    )

    return chain

# Usage
chain = build_cited_rag(vectorstore)
result = chain.invoke("What are Python best practices for async code?")
print(f"Answer: {result.answer}")
print(f"Sources: {result.sources}")
print(f"Confidence: {result.confidence:.1%}")
print(f"Sufficient context: {result.has_sufficient_context}")
```

```python
# --- Production RAG: Conversational với Memory ---
# Kết hợp RAG + Chat History

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import HumanMessage, AIMessage

def build_conversational_rag(vectorstore):
    """
    Conversational RAG:
    - Nhớ conversation history
    - Reformulate câu hỏi dựa trên context của conversation
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # Prompt để reformulate question based on history
    # VD: User hỏi "Tại sao?" sau câu hỏi về asyncio → reformulate thành "Tại sao asyncio quan trọng?"
    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", """Dựa vào conversation history và câu hỏi mới nhất của user,
tạo lại câu hỏi standalone có thể hiểu được mà không cần history.
Nếu câu hỏi đã standalone, giữ nguyên. Không trả lời câu hỏi, chỉ reformulate nếu cần."""),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # History-aware retriever: reformulate query trước khi search
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_prompt
    )

    # QA prompt
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", """Bạn là Python mentor. Trả lời dựa trên context sau:
{context}

Nếu không đủ thông tin, thừa nhận thẳng thắn."""),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # Combine docs chain
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    # Full RAG chain với history
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    return rag_chain

# Test conversational RAG
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=OpenAIEmbeddings())
rag_chain = build_conversational_rag(vectorstore)

chat_history = []

def chat(question: str) -> str:
    result = rag_chain.invoke({
        "input": question,
        "chat_history": chat_history,
    })
    chat_history.append(HumanMessage(content=question))
    chat_history.append(AIMessage(content=result["answer"]))
    return result["answer"]

print(chat("Asyncio trong Python là gì?"))
print(chat("So sánh với NodeJS event loop?"))
print(chat("Cho tôi ví dụ thực tế?"))
# Lần 3: agent biết "thực tế" liên quan đến asyncio từ context trước
```

---

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Chunk size quá nhỏ (< 100 chars) | Thiếu context, retrieval kém | 500-1000 chars cho most use cases |
| Chunk size quá lớn (> 2000 chars) | LLM nhận quá nhiều noise, kém focus | Test với 500, 1000, 1500 và measure quality |
| Chunk overlap = 0 | Thông tin bị cắt đứt ở boundaries | Dùng 10-20% of chunk size làm overlap |
| Embed query khác format với docs | Similarity kém | Dùng cùng embedding model cho indexing và querying |
| Không filter by metadata | Retrieve off-topic docs | Thêm metadata và filter khi search |
| Rebuild vector store mỗi lần | Chậm, tốn tiền | Persist và chỉ add new docs |
| Đổi embedding model trong cùng collection | Dimension mismatch hoặc kết quả retrieval sai | Tạo collection mới, migration/re-index rõ ràng |
| k quá nhỏ (k=1) | Miss relevant context | Bắt đầu với k=4, adjust based on testing |
| k quá lớn (k=20) | Context window overflow, nhiễu | Dùng reranking để reduce sau khi retrieve rộng |
| Không xử lý "out of context" | LLM hallucinate | Prompt explicitly: "nếu không có trong context, nói không biết" |
| Prompt không có format instructions | Inconsistent citations | Luôn instruct cách cite sources |

---

## ✅ Best Practices

- **Chunk size experimentation**: Không có one-size-fits-all. Test 500, 1000, 1500 với sample queries
- **Metadata từ đầu**: Khi load docs, enrich metadata (date, category, version). Khó thêm sau
- **Hybrid search**: Kết hợp vector search với keyword search có thể improve recall, nhưng cần eval trên query set thật
- **Evaluate RAG**: Dùng RAGAS framework để đo Faithfulness, Relevance, Context Recall
- **Monitor embedding costs**: Track tokens khi embed large corpora. Local models nếu cost là issue
- **Incremental indexing**: Detect và chỉ embed documents mới thay vì rebuild toàn bộ
- **Context window management**: `create_stuff_documents_chain` có thể overflow — test với worst case
- **Prompt engineering**: "Chỉ dùng thông tin trong context" quan trọng để prevent hallucination
- **Sources/Citations**: Always return sources — users cần verify important information
- **Test với adversarial queries**: Hỏi về things không có trong context — system phải từ chối đúng cách

---

## ⚖️ Trade-offs

### Vector Store Comparison

| | Chroma | Qdrant | pgvector | Pinecone | Weaviate |
|---|---|---|---|---|---|
| Setup | Trivial local/server | Docker/cloud | PostgreSQL extension | Managed API | Docker/cloud |
| Scale | Dev/prototype, Chroma Cloud cho managed path; benchmark trước khi lớn | Service riêng, tốt khi cần scale/filter nâng cao | Phụ thuộc PostgreSQL sizing/indexing | Managed/serverless, ít ops | Service riêng/cloud, production-ready |
| Filter | Metadata filter và document contains filter | Advanced payload filters | SQL mạnh nếu metadata nằm trong Postgres | Metadata filters | Filters + schema/class model |
| Hybrid | Không phải hybrid ranking đầy đủ; thường cần BM25/layer ngoài hoặc filter text | Dense + sparse/RRF khi cấu hình đúng | SQL full-text + vector, tự viết fusion/ranking | Dense/sparse/hybrid tùy index/API | Hybrid search built-in |
| Integration | `langchain-chroma`, `chromadb` | `langchain-qdrant`, `qdrant-client` | `langchain-postgres`, SQLAlchemy/psycopg | `pinecone`, LangChain integration | `weaviate-client`, LangChain integration |
| Cost | Local free; Cloud paid | Self-host infra hoặc Cloud | Postgres infra/managed DB | Paid managed | Self-host infra hoặc Cloud |
| Best for | Prototype/dev và dataset vừa | Khi cần vector service riêng | Team đã vận hành PostgreSQL tốt | Managed SLA, ít vận hành | Hybrid/multi-modal/schema-rich search |

### Embedding Models

| | OpenAI ada-002 | OpenAI text-3-small | Local MiniLM |
|---|---|---|---|
| Quality | Good | Better | Good enough |
| Cost | $0.10/1M tokens | $0.02/1M tokens | Free |
| Privacy | Data to OpenAI | Data to OpenAI | Local |
| Multilingual | OK | Better | Needs multilingual model |
| Setup | API key | API key | uv add |

### Chunk Strategies

| | Fixed size | Semantic | Hierarchical |
|---|---|---|---|
| Implementation | Simple | Complex | Complex |
| Quality | OK | Better | Best |
| Cost | Low | Medium | High |
| Use case | General | Long documents | Nested content |

---

## 🚀 Performance Notes

- **Batch embedding**: `embed_documents(texts)` thay vì loop `embed_query()` — 10x faster
- **Async embedding**: `await embeddings.aembed_documents(texts)` trong async context
- **Cache embeddings**: Dùng `CacheBackedEmbeddings` để tránh re-embed unchanged docs
- **HNSW tuning**: Qdrant và pgvector có HNSW parameters — tune `ef_construct` và `m` cho accuracy/speed tradeoff
- **Local models on GPU**: sentence-transformers với CUDA = 10x faster than CPU
- **Retrieval k vs accuracy**: Larger k = better recall but more noise. Sweet spot: k=4-8

```python
# Cache-backed embeddings — tránh re-embed unchanged documents
from langchain.embeddings.cache import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_openai import OpenAIEmbeddings

underlying_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Cache trong local file store
store = LocalFileStore("./embedding_cache/")
cached_embeddings = CacheBackedEmbeddings.from_bytes_store(
    underlying_embeddings,
    store,
    namespace=underlying_embeddings.model,
)

# Lần đầu: gọi API (chậm, có cost)
# Lần sau với cùng text: từ cache (instant, free!)
vectorstore = Chroma.from_documents(documents, embedding=cached_embeddings)
```

---

## 🗄️ So sánh Vector Databases

| Tiêu chí | Chroma | Qdrant | pgvector | Pinecone | Weaviate |
|----------|--------|--------|----------|----------|----------|
| Self-hosted | ✅ | ✅ | ✅ (PostgreSQL ext) | ❌ managed only | ✅ |
| Managed cloud | ✅ (Chroma Cloud) | ✅ | ✅ (Supabase, Neon, managed Postgres) | ✅ | ✅ |
| Scaling | Local đơn giản; Cloud cho managed path, vẫn cần benchmark workload | Tốt nếu vận hành service riêng hoặc dùng Cloud | Phụ thuộc PostgreSQL sizing/indexing | Managed/serverless scale | Tốt, nhất là khi cần schema/hybrid |
| Hybrid search | Metadata + document text filters; hybrid ranking thường cần layer ngoài | Dense+sparse/RRF khi cấu hình đúng | SQL full-text + vector, tự thiết kế fusion | Dense/sparse/hybrid tùy index/API | Hybrid search built-in |
| Use case chính | Prototype, dev, small/medium RAG | Service vector riêng cho Python apps | Đã có PostgreSQL và cần join/transaction/filter SQL | Managed enterprise/SLA, ít ops | Hybrid/multi-modal/schema-rich search |
| Cài đặt | `uv add chromadb` | Docker/cloud | PostgreSQL extension | API only | Docker/cloud |
| Python SDK | ✅ | ✅ | SQLAlchemy + pgvector | ✅ | ✅ |

**Decision tree cho team:**

```
Bạn đang ở giai đoạn nào?
├── Prototype / dev → Chroma (zero setup, in-memory/local)
├── Production và đã có PostgreSQL → cân nhắc pgvector nếu workload/filter phù hợp
├── Production, cần vector service riêng → cân nhắc Qdrant/Pinecone/Weaviate theo ops/SLA
├── Enterprise, cần managed SLA → cân nhắc Pinecone/Qdrant Cloud/Weaviate Cloud/Chroma Cloud
└── Multi-modal hoặc hybrid search nặng → cân nhắc Weaviate/Qdrant/Pinecone hoặc backend có multi-vector/sparse support
```

```python
# Chroma → Qdrant migration — minimal code changes
# Chroma:
from langchain_chroma import Chroma
vectorstore = Chroma.from_documents(docs, embedding=embeddings)

# Qdrant:
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
vectorstore = QdrantVectorStore.from_documents(
    docs,
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="my_collection",
)

# pgvector (PostgreSQL):
from langchain_postgres import PGVector
vectorstore = PGVector.from_documents(
    docs,
    embedding=embeddings,
    connection="postgresql+psycopg://user:pass@localhost:5432/mydb",
    collection_name="my_collection",
)

# Interface là giống nhau sau khi setup:
results = vectorstore.similarity_search("query", k=5)
# → cùng interface bất kể backend
```

> **Khuyến nghị thực tế**: Bắt đầu với Chroma khi dev, rồi chọn Qdrant/pgvector/Pinecone/Weaviate/Chroma Cloud theo dữ liệu, filter, ops, SLA, privacy, và chi phí. Không có lựa chọn "best" tuyệt đối: hybrid support, managed option, và benchmark đều phụ thuộc version, index config, corpus, ngôn ngữ, metadata filters, và latency target. LangChain giúp giữ interface retrieval tương đối giống nhau, nhưng migration production vẫn cần re-index, mapping metadata/filter syntax, kiểm tra embedding dimension, và chạy eval lại.

## 📝 Tóm tắt

- **RAG** giải quyết ba limitation của LLM: knowledge cutoff, hallucination, context window limit
- **Document Loaders** chuẩn hóa nhiều file formats thành `List[Document]` với metadata
- **Text Splitters** chia documents thành chunks — `RecursiveCharacterTextSplitter` là best default
- **Embeddings** chuyển text thành vectors — OpenAI text-3-small (cloud) hoặc MiniLM (local)
- **Vector Stores**: Chroma/Qdrant/pgvector/Pinecone/Weaviate là trade-off; chọn bằng benchmark và eval thay vì theo matrix tuyệt đối
- **RAG Chain** = Retrieve → Format → Prompt → Generate — dùng LCEL để compose
- **Conversational RAG** kết hợp chat history với retrieval — reformulate query trước khi search
- **Production RAG** cần: metadata filtering, caching, citations, evaluation metrics, và monitoring
