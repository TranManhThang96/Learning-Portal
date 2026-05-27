# Ngày 23: LlamaIndex

## 🎯 Mục tiêu học tập
- Hiểu rõ sự khác biệt giữa LlamaIndex và LangChain, biết khi nào dùng cái nào
- Implement VectorStoreIndex, SummaryIndex, và KnowledgeGraphIndex
- Xây dựng query engines và retrievers linh hoạt
- Tạo ingestion pipelines với transformations
- Kết hợp nhiều index với RouterQueryEngine

> **Target version note:** Bài này hướng tới LlamaIndex Python hiện hành theo docs `llama_index.core`/package integrations (`llama-index-core`, `llama-index-llms-openai`, `llama-index-embeddings-openai`). LlamaIndex đổi API nhanh; nếu project pin khác version docs, hãy chạy import smoke test trước lab. Đặc biệt `Settings` và `KnowledgeGraphIndex` là các surface từng thay đổi nhiều giữa các minor versions.

## 🔄 So sánh với NodeJS

| Khái niệm LlamaIndex | Tương đương NodeJS | Ghi chú |
|---------------------|-------------------|---------|
| `Document` | Raw data object (Buffer, JSON) | Wrapper cho raw content |
| `Node` / `TextNode` | Processed chunk với metadata | Giống message trong queue sau processing |
| `Index` | Database + indexes | Mỗi Index type = different query strategy |
| `QueryEngine` | Service layer | Orchestrates retrieval + generation |
| `Retriever` | Repository pattern | Chỉ fetch, không generate |
| `IngestionPipeline` | ETL pipeline (Bull/BullMQ jobs) | Transform → chunk → embed → store |
| `Settings` | Dependency injection / app config | Configure LLM, embeddings; thay thế nhiều pattern `ServiceContext` cũ |
| `StorageContext` | Database connection config | Persist indexes xuống disk |

**LlamaIndex vs LangChain — Khi nào dùng cái nào:**

| Feature | LlamaIndex | LangChain |
|---------|-----------|-----------|
| **Mục tiêu chính** | Data indexing và querying | General LLM orchestration |
| **Strength** | Complex document Q&A, knowledge graphs | Chains, agents, tool use |
| **Data connectors** | Nhiều connectors/integrations, thường tách package | Ít hơn, cần community |
| **Index abstraction** | Nhiều loại index rõ ràng | Chủ yếu vector store |
| **Learning curve** | Cao hơn | Thấp hơn |
| **Best for** | Document-heavy RAG apps | General agents, chatbots |

**Rule of thumb:** Nếu app của bạn chủ yếu là **"tôi có nhiều documents và cần query chúng thông minh"** → LlamaIndex. Nếu app là **"tôi cần orchestrate nhiều LLM calls, tools, agents"** → LangChain.

## 📖 Lý thuyết

### Section 1: Core Concepts — Documents, Nodes, và Index

**WHY LlamaIndex ra đời?**

LangChain rất mạnh cho orchestration nhưng phức tạp khi làm việc với nhiều loại documents. LlamaIndex được thiết kế từ đầu cho use case: **"Connect your data to LLMs"**. Nó có:
- Nhiều data connectors/integrations (PDF, Notion, Confluence, Google Docs, Slack...), nhiều cái cần cài package riêng
- Nhiều index types cho các query patterns khác nhau
- Advanced query routing

```python
# uv add llama-index llama-index-llms-openai llama-index-embeddings-openai

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Document,
    Settings,
)
from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
import os

# === Global Settings — Dependency Injection ===
# Tương tự như NestJS Module providers
# Settings là global mutable config theo docs hiện hành. Tốt cho notebook/lab,
# nhưng trong service multi-tenant hoặc test suite nên set ở startup rõ ràng
# và tránh mutate giữa requests. Khi API hỗ trợ truyền llm/embed_model trực tiếp,
# ưu tiên explicit dependency để dễ test.
Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
Settings.chunk_size = 512
Settings.chunk_overlap = 64

# === Documents — Raw Data Wrapper ===
# Tạo documents thủ công
doc1 = Document(
    text="""
    LlamaIndex là framework để connect LLMs với external data sources.
    Nó hỗ trợ hơn 160 data connectors khác nhau.
    Core components bao gồm: Data Connectors, Indexes, Engines, Agents.
    """,
    metadata={
        "source": "llama_index_overview.txt",
        "author": "Jerry Liu",
        "date": "2024-01-01",
        "category": "framework",
    },
    # metadata_separator và excluded_* giúp kiểm soát
    # thông tin nào được include trong embedding
    excluded_embed_metadata_keys=["date"],  # Không embed metadata này
    excluded_llm_metadata_keys=["author"],  # LLM không thấy author
)

doc2 = Document(
    text="""
    LangChain là framework để build applications với LLMs.
    Nó mạnh cho chains, agents, và tool use.
    LangChain có LCEL (LangChain Expression Language) để compose chains.
    """,
    metadata={
        "source": "langchain_overview.txt",
        "category": "framework",
    }
)

# Load từ file directory
# reader = SimpleDirectoryReader("./data/")
# documents = reader.load_data()

# === TextNode — Processed Chunks ===
# Document → (parsing + chunking) → Nodes
# Mỗi Node là một chunk với đầy đủ metadata
node = TextNode(
    text="LlamaIndex core concepts: documents, nodes, indexes",
    metadata={"source": "manual"},
    # Relationships giữa các nodes
    relationships={
        NodeRelationship.SOURCE: RelatedNodeInfo(node_id="doc_id_123"),
        NodeRelationship.PREVIOUS: RelatedNodeInfo(node_id="prev_node_id"),
        NodeRelationship.NEXT: RelatedNodeInfo(node_id="next_node_id"),
    }
)

print(f"Node ID: {node.node_id}")
print(f"Node relationships: {node.relationships}")
```

### Section 2: Index Types — Chọn đúng tool cho đúng job

**WHY có nhiều index types?**

Mỗi query pattern cần một structure khác nhau. Giống như trong databases: bạn không dùng B-tree index cho full-text search, và không dùng full-text search index cho range queries.

#### 2.1 VectorStoreIndex — General Purpose RAG

```python
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.core.vector_stores import SimpleVectorStore
import os

# === Build Index từ Documents ===
# Tự động: parse → chunk → embed → store
print("Building VectorStoreIndex...")
index = VectorStoreIndex.from_documents(
    [doc1, doc2],
    show_progress=True,  # Progress bar
)

# === Persist Index xuống disk ===
# Giống như flush data xuống database
PERSIST_DIR = "./storage/vector_index"
index.storage_context.persist(persist_dir=PERSIST_DIR)
print(f"Index saved to {PERSIST_DIR}")

# === Load Index từ disk ===
# Không cần rebuild mỗi lần
from llama_index.core import load_index_from_storage

if os.path.exists(PERSIST_DIR):
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    loaded_index = load_index_from_storage(storage_context)
    print("Loaded index from disk")

# === Query với VectorStoreIndex ===
query_engine = index.as_query_engine(
    similarity_top_k=3,          # Retrieve top 3 chunks
    response_mode="compact",     # Combine chunks vào 1 response
    # response_mode options:
    # "refine" — iteratively refine answer với từng chunk
    # "compact" — combine chunks, then answer (default tốt)
    # "tree_summarize" — build tree của summaries
    # "no_text" — chỉ return retrieved nodes (debug)
    # "accumulate" — generate separate answer cho mỗi node, concatenate
)

response = query_engine.query("LlamaIndex là gì?")
print(f"\nAnswer: {response}")
print(f"\nSource nodes: {len(response.source_nodes)}")
for node in response.source_nodes:
    print(f"  - Score: {node.score:.3f} | {node.text[:60]}...")
```

#### 2.2 SummaryIndex — Summarization Tasks

```python
from llama_index.core import SummaryIndex

# WHY SummaryIndex?
# VectorStoreIndex tốt cho "find relevant chunks".
# SummaryIndex tốt cho "summarize toàn bộ document" hoặc
# "answer questions cần đọc nhiều/tất cả chunks".

# SummaryIndex lưu nodes theo sequential order (không phải vector)
# Khi query, nó iterate qua tất cả nodes và tổng hợp

summary_index = SummaryIndex.from_documents([doc1, doc2])

# Mode: "default" — sử dụng tất cả nodes
summary_engine = summary_index.as_query_engine(
    response_mode="tree_summarize",
    # tree_summarize: Build tree của summaries bottom-up
    # Phù hợp cho documents rất dài
    use_async=True,  # Parallel processing
)

# Query yêu cầu global understanding
response = summary_engine.query(
    "So sánh LlamaIndex và LangChain về features chính"
)
print(f"Summary response: {response}")

# SummaryIndex cũng có retriever mode
summary_retriever = summary_index.as_retriever(
    retriever_mode="llm",
    # "llm" — dùng LLM để chọn nodes relevant nhất
    # "default" — return tất cả nodes
    choice_top_k=5,  # LLM chọn top 5 relevant nodes
)
```

#### 2.3 KnowledgeGraphIndex — Structured Relationships

```python
from llama_index.core import KnowledgeGraphIndex
from llama_index.core.graph_stores import SimpleGraphStore

# WHY Knowledge Graph?
# Khi relationships giữa entities quan trọng hơn content của documents.
# VD: "Ai là founder của LlamaIndex?", "LlamaIndex version nào support X?"

# KG Index extract entities và relationships từ text
# Rồi build graph: Entity → Relationship → Entity
# API note: `KnowledgeGraphIndex` vẫn xuất hiện trong docs/examples, nhưng graph
# APIs trong LlamaIndex thay đổi nhanh. Với production graph RAG, kiểm tra
# docs của version đang pin; `KnowledgeGraphIndex` phù hợp để học concept,
# còn project thật có thể cần PropertyGraph/graph-store API mới hơn.

graph_store = SimpleGraphStore()
storage_context = StorageContext.from_defaults(graph_store=graph_store)

kg_index = KnowledgeGraphIndex.from_documents(
    [doc1, doc2],
    storage_context=storage_context,
    max_triplets_per_chunk=5,  # Max (subject, predicate, object) triplets mỗi chunk
    include_embeddings=True,   # Thêm vector search vào graph
    show_progress=True,
)

# Query graph
kg_query_engine = kg_index.as_query_engine(
    include_text=True,         # Include source text, không chỉ graph
    retriever_mode="keyword",  # Dùng keywords để traverse graph
    # retriever_mode options:
    # "keyword" — extract keywords, traverse graph
    # "embedding" — vector similarity để find starting nodes
    # "hybrid" — kết hợp cả hai
    response_mode="tree_summarize",
)

response = kg_query_engine.query("LlamaIndex được tạo bởi ai?")
print(f"KG Answer: {response}")

# Visualize graph (optional)
# kg_index.get_networkx_graph() → networkx Graph
# Có thể export sang Gephi, Neo4j, etc.
```

#### 2.4 Composite Indexes — Router và Ensemble

```python
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector, PydanticSingleSelector

# WHY Router?
# Có nhiều index types khác nhau — router tự động chọn index phù hợp nhất
# cho từng query. Giống như API Gateway routing requests.

# Build multiple indexes
vector_index = VectorStoreIndex.from_documents([doc1, doc2])
summary_index = SummaryIndex.from_documents([doc1, doc2])

# Wrap thành tools với description
vector_tool = QueryEngineTool.from_defaults(
    query_engine=vector_index.as_query_engine(similarity_top_k=3),
    description=(
        "Phù hợp cho các câu hỏi specific về một framework cụ thể, "
        "features, và technical details."
    ),
)

summary_tool = QueryEngineTool.from_defaults(
    query_engine=summary_index.as_query_engine(response_mode="tree_summarize"),
    description=(
        "Phù hợp cho việc tổng hợp, so sánh nhiều frameworks, "
        "hoặc câu hỏi cần overview toàn diện."
    ),
)

# Router tự động chọn tool phù hợp
router_engine = RouterQueryEngine(
    selector=LLMSingleSelector.from_defaults(),  # LLM chọn tool
    query_engine_tools=[vector_tool, summary_tool],
    verbose=True,  # In ra tool nào được chọn và lý do
)

# Test routing
print("\n=== Query 1: Specific feature question ===")
r1 = router_engine.query("LlamaIndex có bao nhiêu data connectors?")
print(f"Answer: {r1}")

print("\n=== Query 2: Comparison question ===")
r2 = router_engine.query("So sánh tổng quan LlamaIndex và LangChain")
print(f"Answer: {r2}")
```

### Section 3: Query Engines — Advanced Patterns

**WHY cần advanced query engines?**

Basic `index.as_query_engine()` chỉ là simple retrieve + generate. Real-world apps cần: filtering theo metadata, multi-step reasoning, sub-question decomposition.

#### 3.1 Sub-Question Query Engine

```python
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.tools import QueryEngineTool

# WHY Sub-Question?
# Complex questions thường cần nhiều lookups khác nhau.
# "So sánh performance của Python và NodeJS trong web apps" cần:
# 1. Tìm info về Python web performance
# 2. Tìm info về NodeJS web performance
# 3. Synthesize comparison

# Setup tools (mỗi tool là một index hoặc engine)
tools = [
    QueryEngineTool.from_defaults(
        query_engine=vector_index.as_query_engine(),
        name="framework_docs",
        description="Contains documentation about LlamaIndex and LangChain frameworks",
    ),
    # Trong real app, bạn có thể có nhiều tools từ nhiều data sources
]

sub_question_engine = SubQuestionQueryEngine.from_defaults(
    query_engine_tools=tools,
    verbose=True,  # Xem sub-questions được generate
    use_async=True,  # Parallel execution của sub-questions
)

# Engine sẽ:
# 1. Decompose question thành sub-questions
# 2. Execute mỗi sub-question song song
# 3. Synthesize final answer từ tất cả sub-answers
response = sub_question_engine.query(
    "So sánh architecture và use cases của LlamaIndex vs LangChain. "
    "Framework nào phù hợp hơn cho enterprise RAG applications?"
)
print(f"Sub-question answer: {response}")
```

#### 3.2 Retriever với Metadata Filtering

```python
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode

# Tạo index với diverse metadata
nodes_with_metadata = [
    TextNode(
        text="FastAPI là modern Python web framework, nhanh và type-safe",
        metadata={"category": "web_framework", "language": "python", "year": 2018}
    ),
    TextNode(
        text="Express.js là minimal web framework cho Node.js",
        metadata={"category": "web_framework", "language": "javascript", "year": 2010}
    ),
    TextNode(
        text="PostgreSQL là advanced open-source relational database",
        metadata={"category": "database", "language": "sql", "year": 1996}
    ),
    TextNode(
        text="Redis là in-memory data structure store, dùng cho caching",
        metadata={"category": "database", "language": "c", "year": 2009}
    ),
]

filtered_index = VectorStoreIndex(nodes_with_metadata)

# Filter theo metadata trước khi vector search
python_retriever = filtered_index.as_retriever(
    similarity_top_k=5,
    filters=MetadataFilters(
        filters=[
            MetadataFilter(
                key="language",
                value="python",
                operator=FilterOperator.EQ,
            ),
        ]
    )
)

# Chỉ retrieve Python-related documents
results = python_retriever.retrieve("web framework")
print("Python-only results:")
for node in results:
    print(f"  - {node.text[:60]} | lang: {node.metadata['language']}")

# Complex filter — kết hợp nhiều conditions
web_framework_retriever = filtered_index.as_retriever(
    similarity_top_k=5,
    filters=MetadataFilters(
        filters=[
            MetadataFilter(key="category", value="web_framework", operator=FilterOperator.EQ),
            MetadataFilter(key="year", value=2015, operator=FilterOperator.GT),
        ],
        condition="and",  # "and" hoặc "or"
    )
)

results = web_framework_retriever.retrieve("web development")
print("\nWeb frameworks after 2015:")
for node in results:
    print(f"  - {node.text[:60]} | year: {node.metadata['year']}")
```

#### 3.3 Custom Retriever

```python
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from typing import List

class HybridLlamaRetriever(BaseRetriever):
    """
    Custom retriever kết hợp vector search và keyword search.
    Implement BaseRetriever interface của LlamaIndex.

    Giống như implement một Repository class trong NestJS.
    """

    def __init__(
        self,
        vector_retriever,
        keyword_retriever,
        alpha: float = 0.5,
    ):
        self.vector_retriever = vector_retriever
        self.keyword_retriever = keyword_retriever
        self.alpha = alpha
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """
        Implement abstract method của BaseRetriever.
        query_bundle chứa: query_str, embedding, custom_embedding_strs
        """
        # Retrieve từ cả hai sources
        vector_nodes = self.vector_retriever.retrieve(query_bundle)
        keyword_nodes = self.keyword_retriever.retrieve(query_bundle)

        # Merge và deduplicate
        all_nodes = {}

        for node_with_score in vector_nodes:
            node_id = node_with_score.node.node_id
            all_nodes[node_id] = NodeWithScore(
                node=node_with_score.node,
                score=node_with_score.score * self.alpha
            )

        for node_with_score in keyword_nodes:
            node_id = node_with_score.node.node_id
            keyword_score = (node_with_score.score or 0) * (1 - self.alpha)

            if node_id in all_nodes:
                # Node xuất hiện ở cả hai — cộng scores
                all_nodes[node_id] = NodeWithScore(
                    node=node_with_score.node,
                    score=all_nodes[node_id].score + keyword_score,
                )
            else:
                all_nodes[node_id] = NodeWithScore(
                    node=node_with_score.node,
                    score=keyword_score,
                )

        # Sort theo combined score
        sorted_nodes = sorted(
            all_nodes.values(),
            key=lambda x: x.score or 0,
            reverse=True
        )

        return sorted_nodes


# Sử dụng custom retriever
from llama_index.core.retrievers import KeywordTableSimpleRetriever

vector_retriever = vector_index.as_retriever(similarity_top_k=5)
# keyword_retriever = keyword_index.as_retriever()

# hybrid_retriever = HybridLlamaRetriever(
#     vector_retriever=vector_retriever,
#     keyword_retriever=keyword_retriever,
#     alpha=0.6,
# )
```

### Section 4: Ingestion Pipelines

**WHY có IngestionPipeline?**

Khi build production RAG, bạn cần:
1. Parse documents (PDF, HTML, Word...)
2. Extract metadata
3. Clean và normalize text
4. Chunk theo strategy
5. Generate embeddings
6. Store vào vector DB

Nếu làm thủ công, code rất lộn xộn. IngestionPipeline giống như Bull queue với nhiều processors — mỗi step là một transformation.

```python
from llama_index.core.ingestion import IngestionPipeline, IngestionCache
from llama_index.core.node_parser import (
    SentenceSplitter,
    SemanticSplitterNodeParser,
    TokenTextSplitter,
)
from llama_index.core.extractors import (
    TitleExtractor,
    QuestionsAnsweredExtractor,
    SummaryExtractor,
    KeywordExtractor,
)
from llama_index.core.schema import MetadataMode
from llama_index.embeddings.openai import OpenAIEmbedding

# === Transformations (Pipeline Steps) ===

# Step 1: Splitting — tương tự langchain splitters
sentence_splitter = SentenceSplitter(
    chunk_size=512,
    chunk_overlap=64,
    paragraph_separator="\n\n",
)

# Step 2: Metadata Extraction — tự động extract info từ content
title_extractor = TitleExtractor(
    nodes=5,  # Dùng 5 nodes đầu để extract title
    llm=Settings.llm,
)

keyword_extractor = KeywordExtractor(
    keywords=10,  # Extract top 10 keywords
    llm=Settings.llm,
)

questions_extractor = QuestionsAnsweredExtractor(
    questions=3,  # Generate 3 questions mỗi chunk có thể trả lời
    llm=Settings.llm,
    # Có thể hữu ích: index theo câu hỏi thay vì chỉ content.
    # Không mặc định tốt hơn; tốn LLM calls và cần eval recall/precision.
)

# Step 3: Embedding
embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# === Build Pipeline ===
pipeline = IngestionPipeline(
    transformations=[
        sentence_splitter,           # 1. Chunk documents
        title_extractor,             # 2. Extract titles
        keyword_extractor,           # 3. Extract keywords
        questions_extractor,         # 4. Generate Q&A pairs
        embed_model,                 # 5. Generate embeddings
    ],
    # Cache: tránh reprocess documents không thay đổi
    # Tương tự ETL incremental processing
    cache=IngestionCache(),
)

# === Run Pipeline ===
print("Running ingestion pipeline...")
nodes = pipeline.run(
    documents=[doc1, doc2],
    show_progress=True,
    num_workers=4,  # Parallel processing
)

print(f"\nIngestion complete: {len(nodes)} nodes created")
for node in nodes[:2]:
    print(f"\nNode ID: {node.node_id}")
    print(f"Text preview: {node.text[:100]}...")
    print(f"Metadata: {node.metadata}")
```

#### 4.1 Pipeline với Custom Transformation

```python
from llama_index.core.schema import BaseNode, TransformComponent
from typing import Any, List, Optional, Sequence

class LanguageDetector(TransformComponent):
    """
    Custom transformation: detect và tag ngôn ngữ của mỗi node.
    Giống như một middleware trong Express.js pipeline.
    """

    def __call__(
        self,
        nodes: List[BaseNode],
        **kwargs: Any
    ) -> List[BaseNode]:
        """
        Transform method — nhận list nodes, trả về list nodes đã transform.
        """
        for node in nodes:
            text = node.get_content(metadata_mode=MetadataMode.NONE)

            # Detect language (simplified)
            # Trong production: dùng langdetect hoặc fasttext
            has_vietnamese = any(
                char in text for char in "àáạảãâầấậẩẫăằắặẳẵ"
            )

            node.metadata["language"] = "vi" if has_vietnamese else "en"
            node.metadata["word_count"] = len(text.split())
            node.metadata["char_count"] = len(text)

        return nodes


class ContentFilter(TransformComponent):
    """Filter ra các nodes quá ngắn hoặc không có nội dung thực sự"""

    min_words: int = 10  # Class attribute với default

    def __call__(
        self,
        nodes: List[BaseNode],
        **kwargs: Any
    ) -> List[BaseNode]:
        filtered = []
        removed = 0

        for node in nodes:
            text = node.get_content(metadata_mode=MetadataMode.NONE)
            word_count = len(text.split())

            if word_count >= self.min_words:
                filtered.append(node)
            else:
                removed += 1
                print(f"Filtered out short node: '{text[:50]}...' ({word_count} words)")

        print(f"ContentFilter: {len(nodes)} → {len(filtered)} nodes ({removed} removed)")
        return filtered


# Pipeline với custom transformations
custom_pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=64),
        LanguageDetector(),        # Custom: detect language
        ContentFilter(min_words=15),  # Custom: filter short nodes
        embed_model,
    ],
)

custom_nodes = custom_pipeline.run(documents=[doc1, doc2])
print(f"\nCustom pipeline: {len(custom_nodes)} nodes")
for node in custom_nodes[:2]:
    print(f"  Language: {node.metadata.get('language')} | "
          f"Words: {node.metadata.get('word_count')}")
```

#### 4.2 Pipeline với Vector Store Integration

```python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.vector_stores import SimpleVectorStore
from llama_index.core import StorageContext, VectorStoreIndex

# Pipeline có thể trực tiếp feed vào vector store
vector_store = SimpleVectorStore()

pipeline_with_store = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=64),
        embed_model,
    ],
    vector_store=vector_store,  # Auto-insert nodes vào vector store
)

# Run pipeline — nodes được auto-indexed
pipeline_with_store.run(documents=[doc1, doc2])

# Create index từ đã-populated vector store
index_from_pipeline = VectorStoreIndex.from_vector_store(vector_store)
engine = index_from_pipeline.as_query_engine()

# Persist pipeline cache để incremental processing
pipeline_with_store.persist("./pipeline_storage")
# Load: IngestionPipeline.from_persist_dir("./pipeline_storage")
```

### Section 5: So sánh đầy đủ LlamaIndex vs LangChain

```python
# === LANGCHAIN approach ===
# Ưu điểm: Flexible, nhiều integrations, LCEL elegant
# Nhược điểm: Boilerplate nhiều cho document-heavy use cases

# from langchain_community.document_loaders import DirectoryLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain_chroma import Chroma
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.runnables import RunnablePassthrough

# loader = DirectoryLoader("./data/")
# docs = loader.load()
# splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
# chunks = splitter.split_documents(docs)
# vectorstore = Chroma.from_documents(chunks, OpenAIEmbeddings())
# retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
# ... (thêm nhiều steps)

# === LLAMAINDEX approach ===
# Ưu điểm: Document-centric, ít boilerplate, nhiều index types
# Nhược điểm: Less flexible cho non-RAG use cases

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings

# Settings.llm = OpenAI(model="gpt-4o-mini")
# Settings.embed_model = OpenAIEmbedding()

# documents = SimpleDirectoryReader("./data/").load_data()
# index = VectorStoreIndex.from_documents(documents)
# engine = index.as_query_engine()
# response = engine.query("What is in these documents?")
# → Chỉ 5 dòng so với LangChain's 15+ dòng

# === Khi nào dùng LlamaIndex ===
USE_LLAMAINDEX_WHEN = [
    "Build Q&A system trên nhiều documents",
    "Cần nhiều loại index (vector, summary, knowledge graph)",
    "Ingestion pipeline phức tạp với metadata extraction",
    "Multi-document synthesis",
    "Query routing dựa trên content type",
]

# === Khi nào dùng LangChain ===
USE_LANGCHAIN_WHEN = [
    "Build agents với nhiều tools",
    "Complex multi-step chains",
    "Chatbots với conversation history",
    "Custom orchestration logic phức tạp",
    "Cần LCEL cho composable pipelines",
]

# === Khi nào dùng CẢ HAI ===
USE_BOTH_WHEN = [
    "LlamaIndex cho indexing và retrieval",
    "LangChain cho agent orchestration",
    # LlamaIndex indexes implement LangChain BaseRetriever interface
    # → Có thể plug LlamaIndex retriever vào LangChain chain
]
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Không set `Settings.llm` và `Settings.embed_model` | Dùng default model (có thể không phải ý muốn) | Luôn explicitly set ở đầu file |
| Mutate `Settings` giữa requests/tests | Kết quả khó reproduce, tenant này ảnh hưởng tenant khác | Set một lần khi app start hoặc truyền config rõ ràng nơi API hỗ trợ |
| Copy `KnowledgeGraphIndex` snippet từ version khác | Import/param lỗi hoặc graph behavior khác | Pin LlamaIndex minor version và chạy smoke test build/query |
| Rebuild index mỗi lần | Chậm, tốn tiền embedding | Persist index và load nếu tồn tại |
| Dùng VectorStoreIndex cho mọi use case | Kém hiệu quả cho summarization | Chọn index type phù hợp với query pattern |
| Ignore metadata khi index | Không thể filter sau này | Luôn thêm source, date, category metadata |
| Không dùng cache trong IngestionPipeline | Reprocess documents không thay đổi | Thêm `IngestionCache()` vào pipeline |
| response_mode mặc định cho documents dài | "Compact" bỏ sót thông tin quan trọng | Dùng "tree_summarize" cho documents > 10 pages |
| Node splitter chunk_size quá nhỏ | Mất context | Ít nhất 256 tokens, thường 512 |

## ✅ Best Practices

- **Luôn persist index:** Tránh rebuild. Check `os.path.exists(persist_dir)` trước khi build mới.
- **Metadata là first-class citizen:** Source, date, category, author — filter nhanh hơn semantic search nhiều.
- **QuestionsAnsweredExtractor là technique nên thử:** Pre-generate questions có thể tăng recall cho docs dạng FAQ/how-to, nhưng cũng tốn LLM calls và có thể thêm noise nếu câu hỏi synthetic kém.
- **Router Engine cho production:** Đừng dùng một index type cho tất cả — route đến index phù hợp.
- **IngestionCache cho incremental updates:** Chỉ process documents mới/thay đổi, skip documents cũ.
- **Async mode cho large ingestion:** `num_workers` và `use_async=True` có thể tăng tốc, nhưng đo theo loader/vector store/API rate limit.
- **Combine LlamaIndex + LangChain:** LlamaIndex retriever → LangChain agent — best of both worlds.

## ⚖️ Trade-offs

| Index Type | Query Speed | Build Cost | Best For |
|-----------|-------------|------------|----------|
| VectorStoreIndex | Nhanh (kNN) | Medium | General Q&A, specific facts |
| SummaryIndex | Chậm (iterate all) | Thấp | Summarization, global questions |
| KnowledgeGraphIndex | Trung bình | Cao (LLM extraction) | Relationship queries |
| RouterQueryEngine | Overhead nhỏ | Cao (multiple indexes) | Mixed query types |

## 🚀 Performance Notes

- **Embedding batch size:** Batch embeddings khi provider/integration hỗ trợ; tên tham số nằm ở embed model hoặc pipeline tùy version, nên kiểm tra docs của package đang pin.
- **Async ingestion:** `await pipeline.arun(documents=docs)` — parallel document processing.
- **Index/vector compression:** Quantization hoặc compression thường nằm ở vector DB/model layer (Qdrant/Pinecone/FAISS/local embedding), không phải magic flag chung của LlamaIndex; benchmark recall trước khi bật.
- **Lazy loading:** `index.as_retriever()` không load tất cả vào RAM — lazy fetching từ disk.
- **Cache warming:** Pre-populate IngestionCache bằng cách run pipeline trên training set trước.

## 📝 Tóm tắt

- **LlamaIndex vs LangChain:** LlamaIndex cho document-heavy RAG, LangChain cho general orchestration — không phải either/or, có thể kết hợp
- **3 index types chính:** VectorStoreIndex (semantic Q&A), SummaryIndex (global understanding), KnowledgeGraphIndex (relationships)
- **RouterQueryEngine là pattern production:** Tự động route query đến index phù hợp, không hardcode
- **IngestionPipeline = ETL pipeline:** Split → Extract metadata → Filter → Embed → Store, có cache cho incremental updates
- **QuestionsAnsweredExtractor là optional optimization:** Index theo questions thay vì content có thể cải thiện một số corpus, nhưng chỉ giữ nếu eval set chứng minh cải thiện
- **Persist index là bắt buộc:** Không rebuild mỗi lần chạy, tiết kiệm time và money
- **Custom transformations cho domain-specific logic:** LlamaIndex's pipeline extensible như Express middleware
