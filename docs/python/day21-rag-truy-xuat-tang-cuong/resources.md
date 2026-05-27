# Tài Liệu Tham Khảo — Ngày 21: RAG — Retrieval Augmented Generation

## 📚 Official Docs

- **LangChain RAG Tutorial** — https://python.langchain.com/docs/tutorials/rag/ — End-to-end tutorial chính thức, điểm khởi đầu tốt nhất
- **LangChain Document Loaders** — https://python.langchain.com/docs/integrations/document_loaders/ — Danh sách tất cả loaders: PDF, Web, CSV, Notion, Confluence, etc.
- **LangChain Text Splitters** — https://python.langchain.com/docs/concepts/text_splitters — So sánh các splitter, khi nào dùng cái nào
- **LangChain Vector Stores** — https://python.langchain.com/docs/integrations/vectorstores/ — Danh sách tất cả supported vector stores
- **Chroma Docs** — https://docs.trychroma.com/docs/overview/introduction — Full Chroma documentation
- **Qdrant Docs** — https://qdrant.tech/documentation/ — Production vector database
- **pgvector README** — https://github.com/pgvector/pgvector — Setup và usage cho PostgreSQL
- **Pinecone Docs** — https://docs.pinecone.io/ — Managed/serverless vector database, hybrid/rerank options
- **Weaviate Docs** — https://docs.weaviate.io/ — Open-source/cloud vector database với hybrid và multi-modal patterns
- **LangChain Retrievers** — https://python.langchain.com/docs/concepts/retrievers — MultiQuery, Ensemble, Compression retrievers
- **OpenAI Embeddings Guide** — https://platform.openai.com/docs/guides/embeddings — text-embedding-3 models, pricing, best practices
- **RAGAS Docs** — https://docs.ragas.io/en/latest/ — RAG evaluation framework

## 🎥 Video / Courses

- **RAG From Scratch (Official LangChain)** — https://www.youtube.com/playlist?list=PLfaIDFEXuae2LXbO1_PKyVJiQ23ZztA0x — 14-part series, cực kỳ detailed, bắt đầu từ đây
- **Advanced RAG Techniques** — https://www.youtube.com/watch?v=sVcwVQRHIc8 — Multi-query, reranking, hybrid search
- **Qdrant + LangChain Tutorial** — https://www.youtube.com/watch?v=4aD0M6l3p3A — Production setup
- **pgvector Full Tutorial** — https://www.youtube.com/watch?v=FDBnyJu_Ndg — PostgreSQL vector extension
- **RAGAS Evaluation Tutorial** — https://www.youtube.com/watch?v=YH_9SqhJwaw — Evaluate RAG quality

## 📝 Articles / Blog Posts

- **RAG Paper (Original)** — https://arxiv.org/abs/2005.11401 — "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" — Đọc abstract và Figure 1
- **Advanced RAG Techniques** — https://blog.langchain.dev/applying-openai-rag/ — LangChain blog về RAG improvements
- **Choosing the Right Chunk Size** — https://www.pinecone.io/learn/chunking-strategies/ — Pinecone guide về chunking strategies
- **HNSW Algorithm Explained** — https://www.pinecone.io/learn/series/faiss/hnsw/ — Hiểu tại sao vector search nhanh
- **Hybrid Search in RAG** — https://python.langchain.com/docs/how_to/hybrid/ — BM25 + Vector ensemble
- **RAG vs Fine-tuning Decision** — https://www.anyscale.com/blog/a-comprehensive-guide-for-building-rag-based-llm-applications-part-1 — Khi nào dùng gì
- **pgvector vs Dedicated Vector DB** — https://supabase.com/blog/pgvector-vs-pinecone — Trade-offs cho Postgres users
- **Embeddings Explained Visually** — https://jalammar.github.io/illustrated-word2vec/ — Jay Alammar's excellent visual explanation
- **Production RAG Challenges** — https://jxnl.co/writing/2024/05/22/systematically-improving-your-rag/ — Jason Liu's practical guide

## 🔧 Tools / Libraries

### Core RAG Stack:
- **langchain-chroma** — `uv add langchain-chroma` — Chroma integration
- **chromadb** — `uv add chromadb` — Chroma vector database
- **langchain-qdrant** — `uv add langchain-qdrant` — Qdrant integration
- **qdrant-client** — `uv add qdrant-client` — Qdrant Python client
- **langchain-postgres** — `uv add langchain-postgres` — pgvector integration
- **pinecone** — `uv add pinecone` — Pinecone Python SDK
- **weaviate-client** — `uv add weaviate-client` — Weaviate Python client
- **psycopg2-binary** — `uv add psycopg2-binary` — PostgreSQL driver

### Document Loaders:
- **pypdf** — `uv add pypdf` — PDF loading
- **docx2txt** — `uv add docx2txt` — Word documents
- **beautifulsoup4** — `uv add beautifulsoup4` — HTML/web scraping
- **unstructured** — `uv add unstructured` — Universal document loader (PDF, PPTX, XLSX, etc.)

### Embeddings:
- **langchain-openai** — `uv add langchain-openai` — OpenAI embeddings
- **langchain-huggingface** — `uv add langchain-huggingface` — Local HuggingFace models
- **sentence-transformers** — `uv add sentence-transformers` — Local embedding models

### Import smoke test cho LangChain integrations:
```python
from langchain_chroma import Chroma
from langchain_qdrant import QdrantVectorStore
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

Nếu course hoặc blog cũ dùng `langchain_community.vectorstores.*`, hãy coi đó là legacy/compat path và kiểm tra lại theo version đang pin. Với vector stores persisted, luôn ghi lại embedding model + dimension trong collection metadata hoặc README của index.

### Advanced RAG:
- **rank_bm25** — `uv add rank_bm25` — BM25 retrieval cho hybrid search
- **ragas** — `uv add ragas` — RAG evaluation framework
- **datasets** — `uv add datasets` — HuggingFace datasets (required by RAGAS)
- **flashrank** — `uv add flashrank` — Fast reranking models (local)

### Setup Docker cho Vector DBs:
```bash
# Qdrant
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# PostgreSQL + pgvector
docker run -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=ragdb \
  pgvector/pgvector:pg16

# Verify pgvector
# psql -h localhost -U postgres -d ragdb -c "CREATE EXTENSION vector;"
```

## 💡 Ghi chú thêm

### RAG Quality Improvement Checklist

Khi RAG trả lời không đúng, debug theo thứ tự:

**1. Retrieval Issues (80% of cases):**
```python
# Debug: xem retrieved docs cho query
docs = retriever.invoke("your query")
for doc in docs:
    print(doc.page_content[:200])
    print(doc.metadata)
# Nếu retrieved docs không relevant → fix retrieval trước
```

**2. Common Retrieval Fixes:**
- Chunk size quá lớn/nhỏ → Experiment: 200, 500, 1000, 2000
- Query embedding khác với doc embedding format → Thêm "query:" prefix cho queries (embedding model specific)
- Missing relevant doc → Tăng k hoặc thêm multi-query
- Too many irrelevant docs → Thêm metadata filter hoặc dùng MMR

**3. Generation Issues (20% of cases):**
- LLM ignore context → Strengthen system prompt: "ONLY use information from the provided context"
- Hallucination khi context thiếu → Thêm explicit instruction: "If context is insufficient, say 'I don't have enough information'"

### Embedding Model Comparison cho Tiếng Việt

```python
models_to_test = [
    "text-embedding-3-small",                    # OpenAI — decent Vietnamese
    "intfloat/multilingual-e5-small",            # Best free multilingual
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # Good alternative
    "VoVanPhuc/sup-SimCSE-VietNamese-phobert-base",  # Vietnamese-specific
]
```

Recommendation cho tiếng Việt: `intfloat/multilingual-e5-small` (free) hoặc OpenAI `text-embedding-3-small` (paid nhưng tốt hơn).
Khi đổi embedding model, tạo collection/table mới hoặc re-index toàn bộ để tránh mismatch dimension và score không thể so sánh.

### pgvector SQL Examples — Power of SQL + Vectors:

```sql
-- Tạo table với vector column
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding VECTOR(1536)  -- OpenAI text-embedding-3-small dimensions
);

-- Create HNSW index cho fast search
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);

-- Semantic search với SQL filters
SELECT id, content, metadata,
       1 - (embedding <=> query_embedding) AS similarity
FROM documents
WHERE metadata->>'category' = 'python'    -- Filter by metadata
  AND metadata->>'date' >= '2024-01-01'   -- Date filter
ORDER BY embedding <=> query_embedding    -- Sort by similarity
LIMIT 5;

-- Hybrid: vector search + full-text search
SELECT id, content,
       ts_rank(to_tsvector('english', content), query) AS text_rank,
       1 - (embedding <=> query_vec) AS vec_score,
       (ts_rank(...) + (1 - (embedding <=> query_vec))) / 2 AS hybrid_score
FROM documents, plainto_tsquery('english', 'asyncio python') query
WHERE to_tsvector('english', content) @@ query  -- Full-text match required
ORDER BY hybrid_score DESC;
```

### Cost Optimization cho RAG:

| Component | Action | Savings |
|---|---|---|
| Embeddings | Dùng local model (MiniLM) | 100% embedding cost |
| Embeddings | Cache với `CacheBackedEmbeddings` | 80-90% khi re-index |
| Retrieval | Giảm k (4 thay vì 10) | Ít LLM input tokens |
| Generation | Dùng gpt-4o-mini thay vì gpt-4o | 10x cheaper |
| Chunking | Tối ưu chunk size | Ít tokens hơn |

Estimate cho indexing 1000 pages PDF:
- OpenAI embeddings: ≈ $0.50 (one-time)
- Local embeddings: $0 (one-time, cần RAM)
- Queries per day: 100 queries × 4 chunks × 500 tokens = 200K tokens ≈ $0.03/day

### Production Architecture Checklist:

```
[ ] Vector store persisted (không in-memory)
[ ] Embedding cache enabled
[ ] Metadata enriched khi indexing
[ ] Incremental indexing (không rebuild mỗi ngày)
[ ] Retrieval monitoring (log queries + retrieved docs)
[ ] LangSmith tracing enabled
[ ] RAGAS evaluation scheduled (weekly/monthly)
[ ] Fallback khi LLM hoặc vector store down
[ ] Rate limiting cho API endpoint
[ ] Authentication cho query endpoint
```
