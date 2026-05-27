# Tài Liệu Tham Khảo — Ngày 22: RAG Nâng Cao & Optimization

## 📚 Official Docs

- **LangChain Text Splitters** — https://python.langchain.com/docs/how_to/#text-splitters — Tất cả các splitter built-in, với examples
- **RAGAS Documentation** — https://docs.ragas.io/en/latest/ — Framework đánh giá RAG, metrics explanation
- **Sentence Transformers Cross-Encoders** — https://www.sbert.net/docs/pretrained_cross-encoders.html — Danh sách pre-trained cross-encoder models
- **rank_bm25 PyPI** — https://pypi.org/project/rank-bm25/ — BM25 implementation cho Python
- **LangChain EnsembleRetriever** — https://python.langchain.com/docs/how_to/ensemble_retriever/ — Hybrid search với Reciprocal Rank Fusion
- **Cohere Rerank API** — https://docs.cohere.com/docs/rerank-2 — API-based re-ranking, multilingual

## 🎥 Video / Courses

- **Advanced RAG Techniques** (DeepLearning.AI) — https://www.deeplearning.ai/short-courses/building-evaluating-advanced-rag/ — Course ngắn, thực hành, miễn phí
- **RAG from scratch** (LangChain YouTube) — https://www.youtube.com/playlist?list=PLfaIDFEXuae2LXbO1_PKyVJiQ23ZztA0x — Series 20 videos, cover từ basic đến advanced
- **Chunking Strategies Explained** — https://www.youtube.com/watch?v=8OJC21T2SL4 — Video so sánh trực quan các strategies
- **Hybrid Search Deep Dive** — https://www.youtube.com/watch?v=lYxGYXjfrNI — Giải thích BM25 + dense search + RRF

## 📝 Articles / Blog Posts

- **Chunking Strategies for LLM Applications** — https://www.pinecone.io/learn/chunking-strategies/ — Pinecone's comprehensive guide, có benchmark
- **Advanced RAG: Small-to-Big Retrieval** — https://towardsdatascience.com/advanced-rag-01-small-to-big-retrieval-172181b396d4 — Parent-child chunking deep dive
- **Evaluating RAG with RAGAS** — https://blog.langchain.dev/evaluating-rag-pipelines-with-ragas-langsmith/ — Official LangChain blog
- **RAG Failure Modes and How to Fix Them** — https://www.anyscale.com/blog/a-comprehensive-guide-for-building-rag-based-llm-applications-part-1 — Rất đầy đủ, có code
- **BM25 Explained** — https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables — Elasticsearch explain BM25, visual diagrams
- **Lost in the Middle: How Language Models Use Long Contexts** — https://arxiv.org/abs/2307.03172 — Paper gốc về attention pattern của LLM
- **RAGAS: Automated Evaluation of Retrieval Augmented Generation** — https://arxiv.org/abs/2309.15217 — Paper gốc của RAGAS

## 🔧 Tools / Libraries

- **rank_bm25** — `uv add rank-bm25` — BM25 implementation thuần Python, dễ dùng
- **RAGAS** — `uv add ragas` — Evaluation framework, hỗ trợ nhiều metrics
- **sentence-transformers** — `uv add sentence-transformers` — Cross-encoder models, bi-encoders
- **tiktoken** — `uv add tiktoken` — OpenAI's tokenizer, đếm tokens chính xác
- **langchain-text-splitters** — `uv add langchain-text-splitters` — All splitting strategies
- **langchain-community** — `uv add langchain-community` — BM25Retriever, EnsembleRetriever
- **langchain-experimental** — `uv add langchain-experimental` — SemanticChunker
- **langchain-chroma + chromadb** — `uv add langchain-chroma chromadb` — Local vector store, persistent
- **FAISS** — `uv add faiss-cpu` — Fast vector search cho large datasets
- **Weaviate** — `uv add weaviate-client` — Production vector DB với hybrid search built-in

## 💡 Ghi chú thêm

### Import smoke test:
```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever

# Các retriever/compressor core có thể đổi path theo LangChain minor version.
# Smoke-test trong môi trường course:
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
```

### Về RAGAS và OpenAI costs:
RAGAS dùng LLM để evaluate (GPT-4o-mini ổn, không cần GPT-4). Một lần evaluate 50 questions tốn khoảng $0.10-0.30. Có thể dùng local LLM (Ollama) để free:

```python
from langchain_ollama import ChatOllama
llm = ChatOllama(model="llama3.1:8b")
evaluator_llm = LangchainLLMWrapper(llm)
result = evaluate(dataset=dataset, metrics=[Faithfulness(llm=evaluator_llm)])
```

### Về Cross-Encoder models miễn phí:
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — 22MB, chạy được trên CPU, tiếng Anh
- `BAAI/bge-reranker-base` — 278MB, tiếng Anh + Trung
- `BAAI/bge-reranker-v2-m3` — Multilingual kể cả tiếng Việt, cần GPU

### Thứ tự ưu tiên khi optimize RAG:
1. **Đầu tiên:** Cải thiện chunking và metadata (dễ nhất, rẻ nhất)
2. **Tiếp theo:** Tạo eval set nhỏ với expected sources/answers
3. **Sau đó:** Thử hybrid search và re-ranking, chỉ giữ nếu Precision/Recall/faithfulness tốt hơn trong eval
4. **Cuối cùng:** Đổi embedding model hoặc thêm model API đắt hơn khi bottleneck đã rõ

### Benchmark tham khảo (BEIR dataset, không copy trực tiếp cho production):
- Dense-only search: ~0.45 NDCG@10
- BM25-only: ~0.43 NDCG@10
- Hybrid (RRF): ~0.52 NDCG@10 (+15-20% so với từng phương pháp riêng lẻ)
- Hybrid + Re-ranking: ~0.58 NDCG@10

Các số này chỉ minh họa xu hướng trên benchmark public. Với corpus tiếng Việt, tài liệu nội bộ, code, hoặc domain có nhiều mã định danh, ranking có thể khác đáng kể; validate bằng eval set của chính app.
