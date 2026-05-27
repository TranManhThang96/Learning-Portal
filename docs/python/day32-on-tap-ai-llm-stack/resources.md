# Tài Liệu Tham Khảo — Ngày 32

## 📚 Official Docs

- **LangChain Python docs** — https://docs.langchain.com/oss/python/langchain/overview — Current LangChain agents, models, tools, streaming
- **LangChain RAG tutorials** — https://docs.langchain.com/oss/python/langchain/retrieval — Retrieval/RAG patterns
- **LangGraph Python docs** — https://docs.langchain.com/oss/python/langgraph/overview — State machine agents, persistence, interrupts
- **LangSmith** — https://smith.langchain.com/docs — LLM observability platform
- **RAGAS** — https://docs.ragas.io — RAG evaluation framework
- **Chroma** — https://docs.trychroma.com — Vector store documentation

## 🎥 Video / Courses

- **RAG from Scratch** — LangChain YouTube — Playlist 14 videos, build RAG step by step
- **LangGraph Tutorial** — LangChain YouTube — Agents với state machines
- **Advanced RAG Techniques** — Pinecone YouTube — Chunking, reranking, hybrid search

## 📝 Articles / Blog Posts

- **RAG vs Fine-tuning** — https://www.anyscale.com/blog/a-comprehensive-guide-for-building-rag-based-llm-applications — Khi nào dùng gì
- **Advanced RAG Techniques** — https://towardsdatascience.com/advanced-rag-techniques — Hybrid search, reranking
- **LLM Hallucination** — https://arxiv.org/abs/2311.05232 — Research paper về hallucination

## 🔧 Tools / Libraries

- **ragas** — `uv add ragas` — RAG evaluation với Faithfulness, Answer Relevancy metrics
- **deepeval** — `uv add deepeval` — LLM evaluation framework
- **langsmith** — `uv add langsmith` — Tracing và debugging
- **tenacity** — `uv add tenacity` — Retry logic với backoff
- **sentence-transformers** — `uv add sentence-transformers` — Local embedding models
- **chromadb** — `uv add chromadb` — Local vector store
- **qdrant-client** — `uv add qdrant-client` — Production vector store

## 💡 Ghi chú thêm

**RAG Evaluation Metrics (RAGAS):**
- **Faithfulness**: Response có dựa trên retrieved context không? (0-1)
- **Answer Relevancy**: Response có liên quan đến câu hỏi không? (0-1)
- **Context Recall**: Retrieved context có đủ để trả lời không? (0-1)
- **Context Precision**: Retrieved context có chính xác không? (0-1)

**Chunking strategy cheat sheet:**
- Markdown/code: `MarkdownTextSplitter` hoặc `CodeTextSplitter`
- General text: `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)`
- Tables/structured: giữ nguyên, không split
- Large documents (books): Hierarchical chunking — chapter → section → paragraph

**LangSmith free tier**: 5000 traces/tháng — đủ cho development và small projects.
