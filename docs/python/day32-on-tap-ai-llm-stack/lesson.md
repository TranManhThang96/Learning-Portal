# Ngày 32: Ôn tập AI/LLM Stack

## 🎯 Mục tiêu học tập
- Review và consolidate toàn bộ kiến thức AI/ML từ ngày 16-30
- Xây dựng RAG pipeline hoàn chỉnh từ đầu đến cuối
- Debug LLM applications một cách có hệ thống
- Hiểu các patterns Agent quan trọng và khi nào dùng
- Implement evaluation framework cho AI systems

## 🔄 So sánh với NodeJS

| Khía cạnh | NodeJS/TypeScript | Python AI Stack |
|-----------|-------------------|----------------|
| **LLM SDK** | `openai` npm, `@langchain/openai` | `openai`, `langchain-openai` — mature hơn nhiều |
| **Vector DB** | `@qdrant/js-client-rest` | `qdrant-client` — đầy đủ tính năng hơn |
| **Embeddings** | Gọi API | Gọi API + local models (sentence-transformers) |
| **Agent frameworks** | LangChain.js (ít tính năng) | LangChain + LangGraph — production-ready |
| **Evaluation** | Chưa có framework chuẩn | RAGAS, DeepEval, Promptfoo |
| **Local LLM** | Ollama (gọi REST) | Ollama + HuggingFace transformers |
| **Streaming** | SSE với EventSource | asyncio generators + FastAPI StreamingResponse |

**Tại sao Python AI stack tốt hơn**: Hầu hết research papers publish Python code. HuggingFace, PyTorch, LangChain đều Python-first. JS ports thường lag 3-6 tháng về tính năng.

## 📖 Lý thuyết

### 1. RAG Pipeline — Full Review

**Architecture:**

```
Document Ingestion Pipeline:
  Raw Files → Extract Text → Split Chunks → Embed → Store in VectorDB

Query Pipeline:
  User Question → Embed → Similarity Search → Retrieve Top-K → LLM → Answer
```

**Complete RAG implementation từ scratch:**

```python
# rag_from_scratch.py — Complete RAG system
import asyncio
import uuid
from pathlib import Path
from typing import AsyncIterator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Install/pin explicitly:
# uv add langchain langchain-openai langchain-chroma langchain-text-splitters
# Qdrant projects should use langchain-qdrant.QdrantVectorStore.
# Older imports like langchain.text_splitter or
# langchain_community.vectorstores.Qdrant only belong in pinned legacy examples.

# 1. DOCUMENT LOADING
def load_text_file(path: str) -> str:
    """Load và return text content."""
    return Path(path).read_text(encoding="utf-8")

# 2. TEXT SPLITTING
def split_document(text: str, source: str) -> list[Document]:
    """
    Chia text thành chunks có overlap.

    chunk_size=1000: Đủ context, không quá dài
    chunk_overlap=200: Tránh mất context tại boundary
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_text(text)
    return [
        Document(
            page_content=chunk,
            metadata={"source": source, "chunk_id": str(uuid.uuid4())},
        )
        for chunk in chunks
    ]

# 3. EMBEDDING + STORAGE
class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
        self.persist_dir = persist_dir
        self._store: Chroma | None = None

    def get_store(self) -> Chroma:
        if self._store is None:
            self._store = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embeddings,
            )
        return self._store

    def add_documents(self, documents: list[Document]) -> None:
        store = self.get_store()
        store.add_documents(documents)
        print(f"Added {len(documents)} chunks to vector store")

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        store = self.get_store()
        return store.similarity_search(query, k=k)

# 4. RAG CHAIN
class RAGChain:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            streaming=True,
        )

    def _format_docs(self, docs: list[Document]) -> str:
        return "\n\n---\n\n".join(
            f"Source: {d.metadata.get('source', 'unknown')}\n{d.page_content}"
            for d in docs
        )

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Stream câu trả lời với context từ vector store."""
        # Retrieve relevant docs
        docs = self.vector_store.similarity_search(question, k=5)
        context = self._format_docs(docs)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Trả lời câu hỏi dựa trên context bên dưới.
Nếu không có thông tin, hãy nói rõ điều đó.

Context:
{context}"""),
            ("human", "{question}"),
        ])

        chain = prompt | self.llm | StrOutputParser()

        async for chunk in chain.astream({"context": context, "question": question}):
            yield chunk

# 5. USAGE
async def main():
    # Ingest
    vector_store = VectorStore()
    text = load_text_file("my_document.txt")
    docs = split_document(text, source="my_document.txt")
    vector_store.add_documents(docs)

    # Query
    rag = RAGChain(vector_store)
    question = "Nội dung chính của tài liệu là gì?"

    print(f"\nQ: {question}\nA: ", end="")
    async for chunk in rag.stream_answer(question):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    asyncio.run(main())
```

**Smoke test import + mock mode (không cần API key):**

```python
# smoke_ai_stack.py
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


class MockEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 0.0, 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 0.0, 1.0]


splitter = RecursiveCharacterTextSplitter(chunk_size=80, chunk_overlap=10)
docs = [
    Document(page_content=chunk, metadata={"source": "smoke"})
    for chunk in splitter.split_text("FastAPI supports async Python APIs.")
]
store = Chroma(collection_name="smoke", embedding_function=MockEmbeddings())
store.add_documents(docs)
hits = store.similarity_search("async APIs", k=1)
assert hits
print("LangChain imports and mock retrieval OK")
```

Chạy smoke này trước lab RAG để catch lỗi import/package split sớm. Mock embeddings chỉ chứng minh wiring chạy được; không dùng để đo retrieval quality.

### 2. Agent Patterns Review

**Modern agent path (LangChain current docs):**

```python
# agent_modern.py — current LangChain agent API
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

@tool
def calculator(expression: str) -> str:
    """Tính toán biểu thức toán học. Input: chuỗi biểu thức như '2 + 3 * 4'"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"

@tool
def web_search(query: str) -> str:
    """Tìm kiếm thông tin trên web. Input: câu hỏi hoặc từ khóa tìm kiếm."""
    # Mock implementation
    return f"Search results for '{query}': [Mock result 1, Mock result 2]"

@tool
def get_current_time() -> str:
    """Lấy thời gian hiện tại."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

tools = [calculator, web_search, get_current_time]

model = init_chat_model(
    "gpt-4o-mini",
    model_provider="openai",
    temperature=0,
)
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=(
        "Bạn là trợ lý kỹ thuật. Dùng tool khi cần dữ liệu hoặc tính toán, "
        "không bịa kết quả tool."
    ),
)

result = agent.invoke({
    "messages": [
        {"role": "user", "content": "Bây giờ là mấy giờ? Và 15 * 23 bằng bao nhiêu?"}
    ]
})
print(result["messages"][-1].content)
```

`AgentExecutor` + `create_react_agent` vẫn gặp trong tutorial cũ, nhưng không nên là default cho code mới nếu project đang pin LangChain bản hiện hành. Với workflow có state, approval, resume hoặc checkpoint, chuyển sang LangGraph thay vì cố nhồi logic vào ReAct prompt.

**LangGraph — State Machine Agent:**

```python
# langgraph_agent.py
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

# State definition
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    iteration_count: int

# LLM với tools
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools([calculator, web_search])

def call_llm(state: AgentState) -> AgentState:
    """Node: gọi LLM."""
    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "iteration_count": state["iteration_count"] + 1,
    }

def should_continue(state: AgentState) -> str:
    """Edge: quyết định tiếp tục hay kết thúc."""
    last_message = state["messages"][-1]
    # Nếu LLM muốn dùng tool
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    # Hoặc nếu đã quá nhiều iterations
    if state["iteration_count"] >= 5:
        return "end"
    return "end"

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_llm)
workflow.add_node("tools", ToolNode([calculator, web_search]))

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
workflow.add_edge("tools", "agent")  # Sau khi tools chạy, quay lại agent

graph = workflow.compile()

# Run
result = graph.invoke({
    "messages": [HumanMessage(content="Tính 25 * 48 và tìm kiếm về Python")],
    "iteration_count": 0,
})
print(result["messages"][-1].content)
```

### 3. Debugging LLM Applications

**Vấn đề đặc thù**: LLM là non-deterministic — cùng input có thể cho output khác nhau.

```python
# debugging_llm.py — Strategies for debugging LLM apps

# Strategy 1: Temperature=0 cho reproducible outputs (trong tests)
from langchain_openai import ChatOpenAI

debug_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,  # Deterministic hơn, dùng cho testing
    seed=42,        # Thêm reproducibility (OpenAI specific)
)

# Strategy 2: LangSmith tracing
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-langsmith-key"
os.environ["LANGCHAIN_PROJECT"] = "my-rag-debug"
# Tất cả LangChain calls sẽ tự động được trace

# Strategy 3: Custom callback để log mọi thứ
from langchain_core.callbacks import BaseCallbackHandler

class DebugCallback(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print("\n=== LLM CALL START ===")
        for i, prompt in enumerate(prompts):
            print(f"Prompt {i}: {prompt[:200]}...")  # First 200 chars

    def on_llm_end(self, response, **kwargs):
        print(f"=== LLM CALL END ===")
        print(f"Tokens used: {response.llm_output}")

    def on_retriever_end(self, documents, **kwargs):
        print(f"=== RETRIEVED {len(documents)} DOCS ===")
        for doc in documents:
            print(f"  - {doc.metadata.get('source')}: {doc.page_content[:100]}...")

# Dùng callback
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(callbacks=[DebugCallback()])

# Strategy 4: Inspect retrieved documents
def debug_rag_query(rag_chain, vector_store, question: str):
    """Debug helper: xem documents nào được retrieve."""
    print(f"\nQuestion: {question}")

    # Lấy retrieved docs
    docs = vector_store.similarity_search(question, k=5)
    print(f"\nRetrieved {len(docs)} documents:")
    for i, doc in enumerate(docs):
        score = doc.metadata.get("score", "N/A")
        print(f"\n[{i+1}] Score: {score}")
        print(f"Source: {doc.metadata.get('source')}")
        print(f"Content: {doc.page_content[:200]}...")

    print("\n--- Final Answer ---")
    # Chạy full chain
    answer = rag_chain.invoke(question)
    print(answer)
    return answer

# Strategy 5: Eval với golden dataset
def evaluate_rag(rag_chain, test_cases: list[dict]) -> dict:
    """
    Đánh giá RAG với test cases đã biết expected answer.

    test_cases = [
        {"question": "...", "expected_keywords": ["keyword1", "keyword2"]}
    ]
    """
    results = []
    for case in test_cases:
        answer = rag_chain.invoke(case["question"])
        keywords_found = [
            kw for kw in case["expected_keywords"]
            if kw.lower() in answer.lower()
        ]
        score = len(keywords_found) / len(case["expected_keywords"])
        results.append({
            "question": case["question"],
            "answer": answer,
            "score": score,
            "missing_keywords": [
                kw for kw in case["expected_keywords"]
                if kw.lower() not in answer.lower()
            ],
        })

    avg_score = sum(r["score"] for r in results) / len(results)
    print(f"\nAverage score: {avg_score:.2%}")
    return {"results": results, "avg_score": avg_score}
```

### 4. RAG Failure Modes & Fixes

```python
# rag_failure_modes.py

# ❌ Failure Mode 1: Chunk quá nhỏ — mất context
bad_splitter = RecursiveCharacterTextSplitter(
    chunk_size=100,   # Quá nhỏ!
    chunk_overlap=0,  # Không overlap
)
# Fix: chunk_size=500-1500, chunk_overlap=100-200

# ❌ Failure Mode 2: Retrieve quá ít documents
bad_retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
# Fix: k=4-8, tùy độ phức tạp câu hỏi

# ❌ Failure Mode 3: Không re-rank — noisy results
# Fix: Dùng cross-encoder re-ranking
# Caveat: retriever/compressor import paths move across LangChain minors.
# Pin your LangChain version and add a smoke import test before teaching this.
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
compressor = CrossEncoderReranker(model=model, top_n=3)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever,
)

# ❌ Failure Mode 4: Prompt không rõ ràng về việc nói "tôi không biết"
bad_prompt = "Trả lời câu hỏi: {question}\nContext: {context}"
# Fix: Explicit instruction
good_prompt = """Trả lời câu hỏi dựa NGHIÊM NGẶT vào context được cung cấp.
Nếu context không có thông tin đủ, hãy nói: "Tôi không tìm thấy thông tin này trong tài liệu."
KHÔNG được bịa đặt hoặc dùng kiến thức ngoài context.

Context: {context}
Câu hỏi: {question}"""

# ❌ Failure Mode 5: Hybrid search kém — chỉ dùng dense embeddings
# Fix: Kết hợp BM25 (sparse) + embedding (dense)
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

bm25_retriever = BM25Retriever.from_documents(documents, k=5)
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

hybrid_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.4, 0.6],  # 40% BM25, 60% semantic
)
```

### 5. Production Checklist cho AI Systems

```python
# production_checklist.py

# ✅ 1. Retry logic với exponential backoff
import tenacity
from openai import AsyncOpenAI

openai_client = AsyncOpenAI()

@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type((Exception,)),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
)
async def call_openai_with_retry(prompt: str) -> str:
    response = await openai_client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )
    return response.output_text

# ✅ 2. Cost tracking
class CostTracker:
    # Example only: keep real pricing in config/docs, not hardcoded in code.
    PRICES = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "text-embedding-ada-002": {"input": 0.10, "output": 0},
    }

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        prices = self.PRICES.get(model, {"input": 0, "output": 0})
        return (
            input_tokens * prices["input"] / 1_000_000
            + output_tokens * prices["output"] / 1_000_000
        )

# ✅ 3. Response caching
import hashlib
import json
import redis

async def get_cached_response(
    redis_client: redis.asyncio.Redis,
    prompt: str,
    ttl: int = 3600,
) -> str | None:
    cache_key = f"llm:{hashlib.sha256(prompt.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    return cached

async def cache_response(
    redis_client: redis.asyncio.Redis,
    prompt: str,
    response: str,
    ttl: int = 3600,
) -> None:
    cache_key = f"llm:{hashlib.sha256(prompt.encode()).hexdigest()}"
    await redis_client.setex(cache_key, ttl, response)

# ✅ 4. Input/Output guardrails
class GuardrailsChecker:
    BLOCKED_PATTERNS = [
        r"(?i)ignore (previous|all) instructions",
        r"(?i)you are now",
        r"(?i)jailbreak",
    ]

    def check_input(self, text: str) -> bool:
        """Returns True nếu input safe."""
        import re
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, text):
                return False
        return True

    def check_output_length(self, text: str, max_chars: int = 10000) -> str:
        """Truncate output nếu quá dài."""
        if len(text) > max_chars:
            return text[:max_chars] + "...[truncated]"
        return text
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Chunk size quá nhỏ (<200 chars) | Mất context, câu trả lời thiếu thông tin | chunk_size=500-1500 |
| Không overlap chunks | Mất thông tin tại boundaries | chunk_overlap=10-20% của chunk_size |
| Temperature=1 trong production | Output không nhất quán | temperature=0.0-0.3 cho factual tasks |
| Không retry khi OpenAI rate limit | App crash với 429 error | tenacity với exponential backoff |
| Không track token usage | Bill sốc cuối tháng | Log input/output tokens mỗi request |
| Prompt injection không được xử lý | Security vulnerability | Validate và sanitize user inputs |
| Không có fallback khi LLM down | 100% downtime | Multiple providers: OpenAI → Anthropic |
| Store raw API responses | Tốn tiền khi query lại | Cache responses với Redis |

## ✅ Best Practices

- **Temperature thấp cho factual RAG** (0.0-0.2), cao hơn cho creative tasks (0.7-1.0)
- **Explicit "I don't know" instruction** trong system prompt — giảm hallucination
- **Chunk overlap 10-20%** của chunk size — tránh mất context tại boundaries
- **Hybrid search (dense + sparse)** tốt hơn pure semantic search trong nhiều cases
- **Re-ranking** với cross-encoder — cải thiện precision đáng kể
- **LangSmith** cho production tracing — không thể debug LLM apps mà không có observability
- **Golden dataset** ít nhất 50 Q&A pairs để evaluate RAG quality
- **Budget controls**: set `max_tokens` để tránh runaway costs

## ⚖️ Trade-offs

### LangChain vs LlamaIndex
| | LangChain | LlamaIndex |
|---|---|---|
| **Strengths** | Agents, chains, diverse integrations | RAG, indexing, document Q&A |
| **Learning curve** | Steeper (nhiều abstractions) | Gentler for RAG use cases |
| **Community** | Larger | Smaller but focused |
| **Use when** | Complex agents, multi-step workflows | Pure RAG, document Q&A |

### OpenAI vs Local Models
| | OpenAI API | Local (Ollama/HuggingFace) |
|---|---|---|
| **Cost** | Per-token pricing | Hardware cost |
| **Privacy** | Data sent to OpenAI | Stays on-premise |
| **Quality** | State-of-the-art | Improving, still behind |
| **Latency** | Network + compute | Local compute only |
| **Use when** | Best quality needed | Privacy-sensitive data |

**Caveat thực tế**: "Local" không tự động rẻ hơn hoặc riêng tư hơn nếu phải thuê GPU cloud, log prompt vào vendor observability, hoặc dùng model pull từ registry không kiểm soát. "Cloud" không tự động kém an toàn nếu tổ chức có data processing agreement, retention controls, key management và redaction. Quyết định theo data classification, latency SLO, budget, model quality và compliance.

## 🚀 Performance Notes

- **Batch embeddings**: Embed 100 chunks cùng lúc thay vì từng cái — tiết kiệm 90% API calls
- **Async LLM calls**: `asyncio.gather` cho multiple LLM calls độc lập
- **Semantic caching**: Cache theo embedding similarity, không chỉ exact match
- **Streaming**: Giảm perceived latency — user thấy output ngay lập tức

## 📝 Tóm tắt

- RAG = Ingest (load→split→embed→store) + Query (embed→search→retrieve→generate)
- Agent patterns: ReAct (đơn giản) → LangGraph (complex state machines)
- Debug LLM: temperature=0, LangSmith tracing, custom callbacks, golden dataset eval
- Common RAG failures: chunk size, overlap, retrieval quality, prompt clarity
- Production essentials: retry logic, cost tracking, caching, guardrails, observability
- LangChain cho agents, LlamaIndex cho RAG — biết khi nào dùng cái gì
- Local models cho privacy, OpenAI/Anthropic cho quality
