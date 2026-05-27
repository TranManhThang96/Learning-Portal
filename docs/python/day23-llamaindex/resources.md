# Tài Liệu Tham Khảo — Ngày 23: LlamaIndex

## 📚 Official Docs

- **LlamaIndex Documentation** — https://docs.llamaindex.ai/ — Official docs, rất đầy đủ với examples
- **LlamaIndex Core Concepts** — https://docs.llamaindex.ai/en/stable/getting_started/concepts/ — Hiểu Document, Node, Index, Engine
- **Index Types Guide** — https://docs.llamaindex.ai/en/stable/module_guides/indexing/ — Tất cả index types với khi nào dùng
- **Query Engines** — https://docs.llamaindex.ai/en/stable/module_guides/deploying/query_engine/ — RouterQueryEngine, SubQuestion, etc.
- **Ingestion Pipeline** — https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/ — Pipeline với transformations
- **Node Parsers** — https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/ — Tất cả splitter/parser types
- **Metadata Extractors** — https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/?h=extractor#metadata-extractors — TitleExtractor, KeywordExtractor, etc.
- **LlamaHub** — https://llamahub.ai/ — 300+ data loaders và integrations

## 🎥 Video / Courses

- **LlamaIndex Full Course** (LlamaIndex YouTube) — https://www.youtube.com/watch?v=Zyd2ZMywkOY — 2 giờ, từ basics đến advanced
- **Building RAG with LlamaIndex** (DeepLearning.AI) — https://www.deeplearning.ai/short-courses/building-agentic-rag-with-llamaindex/ — Free course, 5 lessons
- **LlamaIndex vs LangChain: Which one to choose?** — https://www.youtube.com/watch?v=Mhpzjm2RQSQ — So sánh trực tiếp, có code demo
- **Advanced RAG with LlamaIndex** — https://www.youtube.com/watch?v=TRjq7t2Ms5I — Hierarchical retrievers, routers

## 📝 Articles / Blog Posts

- **LlamaIndex vs LangChain: A Comprehensive Comparison** — https://www.datacamp.com/blog/llamaindex-vs-langchain — Bảng so sánh chi tiết với use cases
- **Advanced Query Strategies in LlamaIndex** — https://betterprogramming.pub/advanced-rag-llamaindex-1-understanding-query-engines-6527cdeeb430 — Deep dive query engines
- **Building Production RAG with LlamaIndex** — https://towardsdatascience.com/advanced-rag-02-welcome-to-llamaindex-d8eef5c9fa64 — Production patterns
- **KnowledgeGraphIndex Explained** — https://medium.com/llamaindex-blog/towards-property-graph-based-rag-17c5c5b62b28 — Property graph RAG
- **LlamaIndex Ingestion Pipeline** — https://blog.llamaindex.ai/introducing-the-data-ingestion-pipeline-af2a9d7e70b6 — Official blog post về pipeline

## 🔧 Tools / Libraries

- **llama-index** — `uv add llama-index` — Core package
- **llama-index-llms-openai** — `uv add llama-index-llms-openai` — OpenAI LLM integration
- **llama-index-embeddings-openai** — `uv add llama-index-embeddings-openai` — OpenAI embeddings
- **llama-index-vector-stores-chroma** — `uv add llama-index-vector-stores-chroma` — Chroma integration
- **llama-index-readers-file** — `uv add llama-index-readers-file` — File loaders (PDF, Word, etc.)
- **llama-index-graph-stores-neo4j** — `uv add llama-index-graph-stores-neo4j` — Neo4j cho production KG
- **llama-parse** — `uv add llama-parse` — Advanced PDF parsing (tables, images)
- **LlamaHub CLI** — `llamaindex-cli download-llamadataset` — Download sample datasets

## 💡 Ghi chú thêm

### Về LlamaIndex versioning:
LlamaIndex thay đổi API khá nhiều giữa các versions. Bài này target docs hiện hành với `llama_index.core` và package integrations tách riêng. Pin minor version trong `pyproject.toml`/lockfile và luôn check version trong docs:
```python
from importlib.metadata import version

print(version("llama-index-core"))  # Ví dụ: 0.14.x theo docs hiện hành
print(version("llama-index-llms-openai"))
print(version("llama-index-embeddings-openai"))
```

Smoke test imports trước lab:
```python
from llama_index.core import VectorStoreIndex, SummaryIndex, KnowledgeGraphIndex, Settings
from llama_index.core.graph_stores import SimpleGraphStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.ingestion import IngestionPipeline
```

Các integrations như OpenAI, Ollama, Chroma, Qdrant thường nằm trong package riêng (`llama-index-llms-*`, `llama-index-embeddings-*`, `llama-index-vector-stores-*`). Nếu `uv add llama-index` không kéo đủ dependency cho snippet, cài package integration explicit thay vì đổi import ngẫu nhiên.

### Sử dụng LlamaIndex với LangChain:
```python
# LlamaIndex/LangChain bridge APIs đổi khá nhanh; smoke-test theo version pin.
from llama_index.core.langchain_helpers.agents.tools import IndexToolConfig, LlamaIndexTool

# Hoặc trực tiếp:
from llama_index.core import VectorStoreIndex
llama_index_retriever = index.as_retriever()

# Wrap thành LangChain retriever
from langchain_core.retrievers import BaseRetriever
# Wrapper helper/path có thể đổi theo LlamaIndex + LangChain version; smoke-test import.
```

### Dùng Ollama với LlamaIndex (local, free):
```python
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.1:8b", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
```

### KnowledgeGraphIndex tips:
- Cần documents có nhiều named entities và clear relationships
- Hỗ trợ Neo4j cho production (in-memory graph chỉ cho prototyping)
- `KnowledgeGraphIndex`/graph store APIs là phần dễ đổi giữa versions; nếu import hoặc params khác docs, kiểm tra target version thay vì sửa mò
- `max_triplets_per_chunk=5` là baseline hợp lý — tăng lên nếu documents rich về relationships và eval cho thấy recall thiếu
- Visualize graph với: `nx.draw(kg_index.get_networkx_graph())`
