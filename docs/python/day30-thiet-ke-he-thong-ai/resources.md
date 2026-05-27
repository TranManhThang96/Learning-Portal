# Tài Liệu Tham Khảo — Ngày 30

## 📚 Official Docs

- **ChromaDB Docs** — https://docs.trychroma.com — Vector DB local, quickstart rất dễ
- **Qdrant Docs** — https://qdrant.tech/documentation — Production vector DB, filtering mạnh
- **ARQ Docs** — https://arq-docs.helpmanual.io — Async job queue với Redis
- **Celery Docs** — https://docs.celeryq.dev — Mature job queue, nhiều tính năng
- **FastAPI Streaming** — https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse — Official docs
- **LangChain Text Splitters** — https://python.langchain.com/docs/how_to/text_splitters — Nhiều chunking strategies
- **pytest-asyncio** — https://pytest-asyncio.readthedocs.io — Async testing với pytest
- **DeepEval** — https://docs.confident-ai.com — Testing framework cho LLM outputs

## 🎥 Video / Courses

- **Building Production RAG (Anthropic)** — https://www.youtube.com/watch?v=T5CNBMRi8Nc — Deep dive RAG architecture
- **FastAPI Streaming Tutorial** — https://www.youtube.com/watch?v=xtKis1HnVWw — End-to-end streaming
- **Vector Databases Explained** — https://www.youtube.com/watch?v=klTvEwg3oJ4 — Comparison các vector DBs
- **LLM Testing Strategies** — https://www.deeplearning.ai/short-courses/evaluating-debugging-generative-ai/ — DeepLearning.AI course
- **RAG from Scratch** — https://www.youtube.com/playlist?list=PLfaIDFEXuae2LXbO1_PKyVJiQ23ZztA0x — LangChain 13-part series

## 📝 Articles / Blog Posts

- **Chunking Strategies for RAG** — https://www.pinecone.io/learn/chunking-strategies — Comprehensive comparison
- **Advanced RAG Techniques** — https://towardsdatascience.com/advanced-rag-techniques-an-illustrated-overview-04d193d8fec6 — Illustrated overview
- **Streaming in FastAPI** — https://medium.com/thedeephub/building-a-streaming-api-with-fastapi-and-llms — Tutorial
- **Testing LLMs** — https://eugeneyan.com/writing/llm-testing — Practical guide
- **RAG vs Fine-tuning: A Synthesis** — https://arxiv.org/abs/2312.05934 — Khi nào dùng cái nào

## 🔧 Tools / Libraries

**RAG:**
- **chromadb** — `uv add chromadb` — Vector DB local, tốt cho development
- **qdrant-client** — `uv add qdrant-client` — Production vector DB
- **pinecone-client** — `uv add pinecone-client` — Cloud-only, managed
- **langchain-text-splitters** — `uv add langchain-text-splitters` — Chunking utilities
- **pypdf** — `uv add pypdf` — PDF parsing
- **unstructured** — `uv add unstructured` — Parse nhiều file formats (PDF, DOCX, HTML...)
- **tiktoken** — `uv add tiktoken` — OpenAI tokenizer (count tokens chính xác)

**Job Queue:**
- **arq** — `uv add arq` — Async Redis job queue
- **celery** — `uv add celery[redis]` — Mature job queue
- **rq** — `uv add rq` — Simple Redis queue

**Streaming:**
- **sse-starlette** — `uv add sse-starlette` — SSE cho FastAPI/Starlette
- **httpx** — `uv add httpx` — Async HTTP client, hỗ trợ streaming

**Testing:**
- **pytest** — `uv add pytest pytest-asyncio` — Testing framework
- **deepeval** — `uv add deepeval` — LLM-specific assertions
- **ragas** — `uv add ragas` — RAG evaluation metrics

## 💡 Ghi chú thêm

**Setup đầy đủ cho ngày 30:**
```bash
# Core
uv add fastapi uvicorn chromadb sentence-transformers

# Document processing
uv add pypdf tiktoken langchain-text-splitters

# Job queue
uv add arq  # hoặc celery[redis]

# Testing
uv add pytest pytest-asyncio deepeval

# Utilities
uv add httpx sse-starlette
```

**`.env.example` cho lab:**
```bash
# Default local mode, không cần key
LLM_MODE=mock

# Chỉ set khi chạy integration test thật
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENAI_MODEL=
CLAUDE_FAST_MODEL=
CLAUDE_REPORT_MODEL=
GEMINI_MODEL=
RUN_LIVE_LLM_TESTS=0
```

**Mock/live provider rule:**
| Context | Provider | Key required |
|---------|----------|--------------|
| Unit tests | `MockProvider` | Không |
| Local demo | `MockProvider` mặc định | Không |
| Manual integration | OpenAI/Anthropic/Gemini provider | Có |
| CI mặc định | `MockProvider` | Không |

**ADR file gợi ý:** `docs/adr/0001-rag-architecture.md` theo template trong `lesson.md`. Tạo một ADR cho mỗi quyết định lớn: vector DB, chunking, provider, cache policy, retention/privacy.

**Chạy Redis local:**
```bash
# Docker
docker run -d -p 6379:6379 redis:alpine

# Hoặc cài thẳng
brew install redis && redis-server  # macOS
sudo apt install redis-server && redis-server  # Ubuntu
```

**Chạy ARQ worker:**
```bash
# File: worker.py với class WorkerSettings
arq worker.WorkerSettings
```

**Vector DB comparison quick:**
```python
# ChromaDB — local first
import chromadb
db = chromadb.Client()  # in-memory
db = chromadb.PersistentClient("./db")  # persist to disk

# Qdrant — production
from qdrant_client import QdrantClient
client = QdrantClient(":memory:")  # in-memory
client = QdrantClient("localhost", port=6333)  # local Docker
client = QdrantClient(url="https://xxx.qdrant.io", api_key="...")  # cloud
```

**RAG evaluation metrics:**
| Metric | Đo gì | Cách tính |
|--------|--------|-----------|
| Faithfulness | Answer có grounded trong context không | % claims có trong retrieved docs |
| Answer Relevance | Answer có trả lời question không | Cosine sim(answer, question) |
| Context Precision | Retrieved docs có liên quan không | % docs được dùng trong answer |
| Context Recall | Có retrieve đủ docs cần thiết không | % cần thiết được retrieve |

**Tổng kết 30 ngày Python:**
Bạn đã đi từ `print("Hello World")` đến thiết kế production AI systems trong 30 ngày.
Các kỹ năng đã có:
- Python fundamentals (syntax, OOP, async)
- Web APIs với FastAPI
- Data processing với pandas/numpy
- Database với SQLAlchemy
- ML với PyTorch/HuggingFace
- AI APIs (Claude, Gemini, OpenAI)
- Production patterns (caching, circuit breaker, observability)
- AI System Design (RAG, streaming, job queue, testing)

Tiếp theo nên học:
- Deep Learning với PyTorch (nếu muốn research)
- MLOps: MLflow, DVC, Kubeflow
- Kubernetes cho deployment
- Advanced RAG: multi-hop, self-querying, hypothetical documents
