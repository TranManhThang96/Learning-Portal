# Ngày 30: AI System Design

## 🎯 Mục tiêu học tập
- Thiết kế RAG pipeline production-grade với chunking, indexing, retrieval đúng chuẩn
- Implement async job queue với Celery/ARQ cho long-running AI tasks
- Xây dựng streaming responses end-to-end từ FastAPI → LLM → client
- Hiểu cách test AI systems với cả deterministic và non-deterministic outputs

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Job queue | Bull, BullMQ | Celery (Redis), ARQ (Redis), RQ |
| Vector DB client | N/A (ít ecosystem) | Qdrant, Weaviate, Chroma SDK |
| Streaming API | `res.write()`, Server-Sent Events | FastAPI `StreamingResponse`, SSE |
| Document parsing | `pdf-parse`, `mammoth` | `pypdf`, `unstructured` |
| Text chunking | Tự viết | `langchain.text_splitter` |
| Testing AI outputs | Jest + snapshots | pytest + fuzzy matchers |
| Background tasks | Worker threads, cluster | Celery workers, asyncio |

Đây là ngày tổng hợp — bạn sẽ thấy Python ecosystem cho production AI mature hơn NodeJS nhiều, đặc biệt là document processing và vector operations.

## Project Scaffold & API Key Strategy

Trong ngày 30, mọi lab nên chạy được không cần API key. API thật chỉ bật khi learner set env vars rõ ràng.

```text
ai-system-lab/
  app/
    main.py              # FastAPI routes
    providers.py         # LLMProvider, OpenAIProvider, MockProvider
    rag.py               # in-memory retrieval
    streaming.py         # SSE helpers
  tests/
    test_rag.py
    test_providers.py    # mock-only unit tests
  docs/
    adr/
      0001-rag-architecture.md
  .env.example
  pyproject.toml
```

API key policy:
- `.env.example` chỉ chứa tên biến, không chứa key thật: `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, `GEMINI_API_KEY=`.
- Unit tests luôn dùng `MockProvider`; integration tests thật chỉ chạy khi `RUN_LIVE_LLM_TESTS=1`.
- App local default là mock mode để learner test RAG, streaming, cache và guardrails trước khi trả tiền API.
- Nếu muốn scaffold lớn hơn, dùng Day 33 project như bản mở rộng; Day 30 chỉ cần mini scaffold ở trên.

ADR template:

```markdown
# ADR-0001: <Decision title>

## Status
Proposed | Accepted | Superseded

## Context
- Problem:
- Constraints:
- Non-goals:

## Options
| Option | Pros | Cons | Cost/Risk |
|--------|------|------|-----------|
| A | | | |
| B | | | |

## Decision
We will:

## Consequences
- Positive:
- Negative:
- Follow-up metrics:
```

## 📖 Lý thuyết

### 1. RAG Pipeline Production-Grade

**WHY:** RAG (Retrieval Augmented Generation) là pattern phổ biến nhất để build AI apps với custom data. "Production-grade" nghĩa là handle các edge cases: document các loại, chunking thông minh, reranking, hybrid search.

```python
# uv add chromadb sentence-transformers langchain pypdf unstructured
# === COMPLETE RAG PIPELINE ===

import os
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# === 1. DOCUMENT LOADING ===
@dataclass
class Document:
    content: str
    metadata: dict  # source, page, chunk_id, etc.
    doc_id: str

def load_text_file(file_path: str) -> list[Document]:
    """Load plain text file"""
    content = Path(file_path).read_text(encoding="utf-8")
    return [Document(
        content=content,
        metadata={"source": file_path, "type": "text"},
        doc_id=hashlib.md5(content.encode()).hexdigest()[:8]
    )]

def load_pdf(file_path: str) -> list[Document]:
    """Load PDF file, mỗi trang là 1 document"""
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    documents = []

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text.strip():  # bỏ trang trắng
            continue

        documents.append(Document(
            content=text,
            metadata={
                "source": file_path,
                "page": page_num + 1,
                "type": "pdf"
            },
            doc_id=f"pdf_{hashlib.md5(text.encode()).hexdigest()[:8]}"
        ))

    return documents

def load_from_url(url: str) -> list[Document]:
    """Load webpage content"""
    import httpx
    from bs4 import BeautifulSoup

    response = httpx.get(url, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # Bỏ scripts và styles
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    return [Document(
        content=text,
        metadata={"source": url, "type": "web"},
        doc_id=hashlib.md5(url.encode()).hexdigest()[:8]
    )]
```

```python
# === 2. CHUNKING STRATEGIES ===
from typing import Generator

def chunk_by_tokens(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    model_name: str = "cl100k_base"  # OpenAI tokenizer
) -> list[str]:
    """
    Chunk theo số tokens thực sự.
    Tốt hơn chunk theo chars vì model có token limit, không char limit.
    """
    import tiktoken

    encoding = tiktoken.get_encoding(model_name)
    tokens = encoding.encode(text)

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        start += chunk_size - overlap  # overlap để không mất context ở boundary

    return chunks

def chunk_by_semantic(text: str, min_chars: int = 200) -> list[str]:
    """
    Chunk theo cấu trúc ngữ nghĩa: paragraphs > sentences.
    Giữ context tự nhiên hơn, nhưng chunk sizes không đều.
    """
    # Tách theo double newlines (paragraphs)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < min_chars * 3:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def chunk_markdown(text: str) -> list[str]:
    """
    Chunk theo markdown headers.
    Tốt cho documentation, wiki, etc.
    """
    import re

    # Split tại mỗi header (H1, H2, H3)
    sections = re.split(r'\n(?=#{1,3} )', text)

    chunks = []
    for section in sections:
        if not section.strip():
            continue
        # Nếu section quá dài, chunk tiếp theo paragraphs
        if len(section) > 2000:
            sub_chunks = chunk_by_semantic(section, min_chars=300)
            chunks.extend(sub_chunks)
        else:
            chunks.append(section)

    return chunks

# Test chunking
sample_text = """
# Introduction to Python

Python is a high-level programming language created by Guido van Rossum.
It emphasizes code readability through significant whitespace.

## Features

Python supports multiple programming paradigms including procedural, OOP, and functional.
It has a comprehensive standard library often called "batteries included".

### Dynamic Typing

Python uses dynamic typing, meaning variable types are determined at runtime.
This makes development faster but can introduce runtime errors.
"""

chunks = chunk_markdown(sample_text)
print(f"Chunks: {len(chunks)}")
for i, chunk in enumerate(chunks):
    print(f"\n--- Chunk {i+1} ({len(chunk)} chars) ---")
    print(chunk[:100] + "..." if len(chunk) > 100 else chunk)
```

```python
# === 3. VECTOR STORE VỚI CHROMADB ===
import chromadb
from sentence_transformers import SentenceTransformer
import uuid

class RAGVectorStore:
    """
    Vector store wrapper cho RAG pipeline.
    Sử dụng ChromaDB (local) và sentence-transformers (local embedding).
    """

    def __init__(
        self,
        collection_name: str = "rag_documents",
        embedding_model: str = "all-MiniLM-L6-v2",
        persist_directory: str = "./chroma_db"
    ):
        # ChromaDB client với persistence
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Embedding function
        self.encoder = SentenceTransformer(embedding_model)

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # dùng cosine similarity
        )

        print(f"Vector store ready. Existing docs: {self.collection.count()}")

    def add_documents(self, documents: list[Document], batch_size: int = 100):
        """Thêm documents vào vector store"""
        # Batch processing để tránh OOM
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            texts = [doc.content for doc in batch]
            embeddings = self.encoder.encode(texts, show_progress_bar=True).tolist()

            self.collection.add(
                ids=[doc.doc_id for doc in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[doc.metadata for doc in batch]
            )

        print(f"Added {len(documents)} documents. Total: {self.collection.count()}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict = None
    ) -> list[dict]:
        """Semantic search"""
        query_embedding = self.encoder.encode(query).tolist()

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]
        }

        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = self.collection.query(**kwargs)

        # Format results
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            output.append({
                "content": doc,
                "metadata": meta,
                "similarity": 1 - dist  # distance → similarity
            })

        return output

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Hybrid search: kết hợp vector search + BM25 keyword search.
        Tốt hơn pure vector search cho queries với specific keywords.
        """
        # Vector search
        vector_results = self.search(query, top_k=top_k * 2)

        # BM25 keyword search (simplified)
        query_words = set(query.lower().split())
        bm25_scores = []

        for r in vector_results:
            content_words = set(r["content"].lower().split())
            # Simple keyword overlap score
            overlap = len(query_words & content_words) / len(query_words)
            bm25_scores.append(overlap)

        # RRF (Reciprocal Rank Fusion) để kết hợp scores
        k = 60  # RRF constant
        rrf_scores = []
        for rank, (result, bm25) in enumerate(zip(vector_results, bm25_scores)):
            vector_score = 1 / (k + rank + 1)
            bm25_rank = sorted(bm25_scores, reverse=True).index(bm25)
            bm25_rrf = 1 / (k + bm25_rank + 1)
            rrf_scores.append(vector_score + bm25_rrf)

        # Sort by RRF score
        sorted_results = [r for _, r in sorted(
            zip(rrf_scores, vector_results),
            reverse=True
        )]

        return sorted_results[:top_k]
```

```python
# === 4. RERANKING (tùy chọn nhưng cải thiện quality đáng kể) ===
def rerank_results(
    query: str,
    results: list[dict],
    top_k: int = 3
) -> list[dict]:
    """
    Cross-encoder reranking: chính xác hơn bi-encoder nhưng chậm hơn.
    Chỉ dùng cho top-k candidates từ initial retrieval.
    """
    from sentence_transformers import CrossEncoder

    # Model cross-encoder — compute score cho mỗi (query, document) pair
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    # Chuẩn bị pairs
    pairs = [(query, r["content"]) for r in results]

    # Score tất cả pairs cùng lúc
    scores = reranker.predict(pairs)

    # Sắp xếp lại theo score mới
    reranked = sorted(
        zip(scores, results),
        key=lambda x: x[0],
        reverse=True
    )

    return [r for _, r in reranked[:top_k]]
```

```python
# === 5. COMPLETE RAG QUERY PIPELINE ===
import anthropic

class RAGPipeline:
    """
    Production-grade RAG pipeline:
    Query → Retrieve → Rerank → Augment → Generate
    """

    def __init__(self, vector_store: RAGVectorStore):
        self.vector_store = vector_store
        self.llm = anthropic.Anthropic()

    def query(
        self,
        question: str,
        top_k: int = 5,
        use_reranking: bool = True,
        use_hybrid: bool = True
    ) -> dict:
        """
        Full RAG pipeline.
        Returns response + retrieved context + confidence info.
        """
        # 1. Retrieve candidates
        if use_hybrid:
            candidates = self.vector_store.hybrid_search(question, top_k=top_k * 2)
        else:
            candidates = self.vector_store.search(question, top_k=top_k * 2)

        # 2. Rerank (nếu có đủ candidates)
        if use_reranking and len(candidates) > top_k:
            try:
                final_docs = rerank_results(question, candidates, top_k=top_k)
            except ImportError:
                final_docs = candidates[:top_k]  # fallback nếu không có cross-encoder
        else:
            final_docs = candidates[:top_k]

        # 3. Build context string
        context_parts = []
        for i, doc in enumerate(final_docs, 1):
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(f"[Source {i}: {source}]\n{doc['content']}")

        context = "\n\n---\n\n".join(context_parts)

        # 4. Generate response với augmented context
        system_prompt = """Bạn là AI assistant. Trả lời dựa trên context được cung cấp.
Nếu không tìm thấy câu trả lời trong context, nói "Tôi không tìm thấy thông tin này trong tài liệu."
Luôn trích dẫn source khi có thể."""

        prompt = f"""Context:
{context}

Question: {question}

Answer based on the context above:"""

        response = self.llm.messages.create(
            model=os.environ["CLAUDE_FAST_MODEL"],
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.content[0].text

        return {
            "question": question,
            "answer": answer,
            "sources": [
                {"source": d["metadata"].get("source"), "similarity": d.get("similarity", 0)}
                for d in final_docs
            ],
            "context_used": len(final_docs),
            "tokens_used": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens
            }
        }
```

### 2. Async Job Queue với ARQ

**WHY:** AI tasks thường mất 5-60 giây. Không thể để user đợi HTTP response đó lâu. Job queue cho phép return ngay `job_id`, xử lý background, user poll hoặc nhận callback khi xong.

```python
# uv add arq redis
# ARQ là lightweight async job queue, tốt cho Python async apps

import asyncio
from arq import cron
from arq.connections import RedisSettings
import anthropic
import os
import time

# === DEFINE WORKERS ===
async def generate_report(ctx, user_id: str, topic: str) -> dict:
    """
    Long-running task: generate AI report.
    Chạy trong ARQ worker process.
    """
    start = time.time()
    print(f"[Worker] Generating report for user={user_id}, topic={topic}")

    # Giả lập long-running AI task
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=os.environ["CLAUDE_REPORT_MODEL"],
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Generate a comprehensive report about: {topic}
Include:
1. Executive Summary (3 bullet points)
2. Key Findings (5 points)
3. Recommendations (3 actionable items)
Format as structured text."""
        }]
    )

    report = response.content[0].text
    elapsed = time.time() - start

    # Lưu kết quả — thực tế save vào DB
    result = {
        "user_id": user_id,
        "topic": topic,
        "report": report,
        "generated_in_seconds": elapsed,
        "tokens": response.usage.input_tokens + response.usage.output_tokens
    }

    return result

async def process_document(ctx, document_id: str, content: str) -> dict:
    """Chunk và index document vào vector store"""
    chunks = chunk_by_semantic(content, min_chars=200)

    results = {
        "document_id": document_id,
        "chunks_created": len(chunks),
        "total_chars": len(content)
    }

    # Thực tế: thêm vào vector store
    return results

# Worker settings
class WorkerSettings:
    """ARQ Worker configuration"""
    functions = [generate_report, process_document]
    redis_settings = RedisSettings(host="localhost", port=6379)
    max_jobs = 10  # số jobs chạy parallel tối đa
    job_timeout = 300  # 5 phút timeout per job

# === API SIDE: ENQUEUE JOBS ===
async def enqueue_report_generation(user_id: str, topic: str) -> str:
    """Enqueue job và trả về job_id cho client"""
    from arq import create_pool

    redis = await create_pool(RedisSettings(host="localhost", port=6379))

    # Enqueue job — trả về ngay, không chờ
    job = await redis.enqueue_job(
        "generate_report",
        user_id=user_id,
        topic=topic,
        _job_id=f"report_{user_id}_{int(time.time())}",  # custom job ID
        _queue_name="default"
    )

    await redis.close()
    return job.job_id

async def get_job_status(job_id: str) -> dict:
    """Check job status và kết quả nếu done"""
    from arq import create_pool
    from arq.jobs import Job, JobStatus

    redis = await create_pool(RedisSettings(host="localhost", port=6379))

    job = Job(job_id, redis)
    status = await job.status()

    result = {"job_id": job_id, "status": status.value}

    if status == JobStatus.complete:
        result["result"] = await job.result()
    elif status == JobStatus.not_found:
        result["error"] = "Job not found or expired"

    await redis.close()
    return result

# FastAPI endpoint example
# @app.post("/generate-report")
# async def create_report(user_id: str, topic: str):
#     job_id = await enqueue_report_generation(user_id, topic)
#     return {"job_id": job_id, "status": "queued"}
#
# @app.get("/report-status/{job_id}")
# async def check_report(job_id: str):
#     return await get_job_status(job_id)
```

### 3. Streaming Responses End-to-End

**WHY:** Thay vì đợi 5-10 giây rồi nhận toàn bộ response, streaming cho phép show từng token ngay khi LLM generate. Trải nghiệm user tốt hơn đáng kể, perceived latency thấp hơn nhiều.

```python
# uv add fastapi uvicorn anthropic httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import anthropic
import asyncio
import json
import os

app = FastAPI()
claude_client = anthropic.Anthropic()

# === SERVER-SENT EVENTS (SSE) STREAMING ===
async def generate_stream(prompt: str):
    """
    Generator function cho SSE streaming.
    Yield từng chunk theo SSE format.
    """
    # SSE format: "data: {json}\n\n"
    # Event types: token, done, error

    try:
        with claude_client.messages.stream(
            model=os.environ["CLAUDE_FAST_MODEL"],
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                # Yield mỗi token như SSE event
                event = json.dumps({"type": "token", "content": text})
                yield f"data: {event}\n\n"
                # Quan trọng: không có sleep ở đây vì đã có backpressure tự nhiên

            # Gửi usage info khi done
            final = stream.get_final_message()
            done_event = json.dumps({
                "type": "done",
                "usage": {
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens
                }
            })
            yield f"data: {done_event}\n\n"

    except Exception as e:
        error_event = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_event}\n\n"

@app.post("/stream")
async def stream_endpoint(prompt: str):
    """
    FastAPI endpoint trả về streaming SSE response.
    Client nhận từng token ngay khi có.
    """
    return StreamingResponse(
        generate_stream(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tắt nginx buffering
            "Connection": "keep-alive",
        }
    )

# === STREAMING VỚI ASYNC GENERATOR ===
async def async_generate_stream(prompt: str):
    """Async version — cần cho async Claude client"""
    import anthropic

    # Anthropic async client
    async_client = anthropic.AsyncAnthropic()

    async with async_client.messages.stream(
        model=os.environ["CLAUDE_FAST_MODEL"],
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

@app.post("/stream-async")
async def stream_async_endpoint(prompt: str):
    return StreamingResponse(
        async_generate_stream(prompt),
        media_type="text/event-stream"
    )

# === CLIENT SIDE: Consume SSE stream ===
async def consume_stream(url: str, prompt: str):
    """Client code để consume SSE stream"""
    import httpx

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            url,
            params={"prompt": prompt},
            timeout=120
        ) as response:
            full_text = ""
            print("Streaming response: ", end="", flush=True)

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])

                    if data["type"] == "token":
                        print(data["content"], end="", flush=True)
                        full_text += data["content"]

                    elif data["type"] == "done":
                        print()  # newline
                        print(f"\nUsage: {data['usage']}")
                        break

                    elif data["type"] == "error":
                        print(f"\nError: {data['message']}")
                        break

            return full_text
```

```python
# === STREAMING VỚI WEBSOCKET (alternative) ===
from fastapi import WebSocket, WebSocketDisconnect
import anthropic
import os

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint cho bidirectional streaming.
    Tốt hơn SSE khi cần client gửi nhiều messages.
    """
    await websocket.accept()

    async_client = anthropic.AsyncAnthropic()

    try:
        while True:
            # Nhận message từ client
            data = await websocket.receive_json()
            prompt = data.get("message", "")

            if not prompt:
                continue

            # Stream response về client
            full_response = ""

            async with async_client.messages.stream(
                model=os.environ["CLAUDE_FAST_MODEL"],
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                async for text in stream.text_stream:
                    await websocket.send_json({
                        "type": "token",
                        "content": text
                    })
                    full_response += text

            # Gửi done signal
            await websocket.send_json({
                "type": "done",
                "full_response": full_response
            })

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
```

### 4. Testing AI Systems

**WHY:** AI outputs không deterministic — cùng prompt có thể cho output khác nhau mỗi lần. Cần testing strategy khác với traditional unit tests.

```python
# uv add pytest pytest-asyncio deepeval
import pytest
import re
from typing import Callable

# === STRATEGY 1: DETERMINISTIC TESTS (không gọi LLM thật) ===
# Mock LLM responses để test logic, không test AI quality

from unittest.mock import patch, MagicMock

def get_llm_response(prompt: str) -> str:
    """Function cần test"""
    import anthropic
    import os
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=os.environ["CLAUDE_FAST_MODEL"],
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def test_llm_function_logic():
    """Test logic XUNG QUANH LLM call, không phải LLM output"""
    with patch("anthropic.Anthropic") as mock_anthropic:
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Python is a programming language.")],
            usage=MagicMock(input_tokens=10, output_tokens=8)
        )

        # Test
        result = get_llm_response("What is Python?")

        # Assert
        assert result == "Python is a programming language."
        mock_client.messages.create.assert_called_once()

        # Kiểm tra prompt được format đúng
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["messages"][0]["content"] == "What is Python?"

# pytest test_file.py::test_llm_function_logic
```

```python
# === STRATEGY 2: SEMANTIC TESTING (gọi LLM thật) ===
# Test semantic properties của output, không exact match

from sentence_transformers import SentenceTransformer, util

encoder = SentenceTransformer("all-MiniLM-L6-v2")

def assert_semantically_similar(
    actual: str,
    expected: str,
    threshold: float = 0.7,
    message: str = ""
):
    """
    Assert hai texts có cùng nghĩa.
    Thay thế cho `assert actual == expected` với AI outputs.
    """
    actual_emb = encoder.encode(actual, convert_to_tensor=True)
    expected_emb = encoder.encode(expected, convert_to_tensor=True)

    similarity = util.cos_sim(actual_emb, expected_emb).item()

    if similarity < threshold:
        raise AssertionError(
            f"Semantic similarity {similarity:.3f} < threshold {threshold}. "
            f"Message: {message}\n"
            f"Actual:   {actual[:100]}\n"
            f"Expected: {expected[:100]}"
        )

    return similarity

def assert_contains_topics(text: str, required_topics: list[str], threshold: float = 0.6):
    """Assert rằng text đề cập đến các topics yêu cầu"""
    text_emb = encoder.encode(text, convert_to_tensor=True)

    missing_topics = []
    for topic in required_topics:
        topic_emb = encoder.encode(topic, convert_to_tensor=True)
        similarity = util.cos_sim(text_emb, topic_emb).item()
        if similarity < threshold:
            missing_topics.append(f"{topic} (similarity: {similarity:.3f})")

    if missing_topics:
        raise AssertionError(f"Text missing topics: {missing_topics}")

def assert_format_valid(text: str, format_rules: dict):
    """Assert output format đúng với các rules"""
    violations = []

    if "min_length" in format_rules:
        if len(text) < format_rules["min_length"]:
            violations.append(f"Too short: {len(text)} < {format_rules['min_length']}")

    if "max_length" in format_rules:
        if len(text) > format_rules["max_length"]:
            violations.append(f"Too long: {len(text)} > {format_rules['max_length']}")

    if "required_patterns" in format_rules:
        for pattern in format_rules["required_patterns"]:
            if not re.search(pattern, text, re.IGNORECASE):
                violations.append(f"Missing pattern: {pattern}")

    if "forbidden_patterns" in format_rules:
        for pattern in format_rules["forbidden_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"Contains forbidden: {pattern}")

    if violations:
        raise AssertionError(f"Format violations:\n" + "\n".join(f"  - {v}" for v in violations))

# Test examples
@pytest.mark.integration  # đánh dấu test cần gọi API thật
def test_python_explanation_quality():
    """Test chất lượng giải thích Python"""
    response = get_llm_response("Explain Python generators in simple terms")

    # 1. Semantic similarity với expected answer
    assert_semantically_similar(
        response,
        "Generators are a way to create iterators that yield values lazily",
        threshold=0.6,
        message="Should explain generators conceptually"
    )

    # 2. Must mention key concepts
    assert_contains_topics(response, ["yield", "memory", "lazy"], threshold=0.5)

    # 3. Format checks
    assert_format_valid(response, {
        "min_length": 100,
        "max_length": 2000,
        "forbidden_patterns": [r"I don't know", r"I cannot"],
    })
```

```python
# === STRATEGY 3: BEHAVIORAL TESTING ===
# Test invariant properties của AI output

@pytest.mark.parametrize("language", ["English", "Vietnamese", "French"])
def test_language_consistency(language: str):
    """Model phải trả lời bằng ngôn ngữ được yêu cầu"""
    response = get_llm_response(f"Say 'Hello World' in {language}")

    # Map language → expected phrase
    expected = {
        "English": "Hello World",
        "Vietnamese": "Xin chào",
        "French": "Bonjour"
    }

    assert expected[language].lower() in response.lower(), \
        f"Expected {expected[language]} in response but got: {response}"

def test_no_hallucination_on_unknown():
    """Model không nên bịa đặt thông tin khi không biết"""
    response = get_llm_response(
        "What is the GDP of the fictional country Xyzland in 2024?"
    )

    # Model phải indicate rằng không biết hoặc fictional
    uncertainty_phrases = [
        "fictional", "don't exist", "doesn't exist",
        "not aware", "made up", "imaginary", "không tồn tại"
    ]

    has_uncertainty = any(phrase in response.lower() for phrase in uncertainty_phrases)
    assert has_uncertainty, f"Model should indicate uncertainty. Got: {response}"

# === SNAPSHOT TESTING CHO DETERMINISTIC OUTPUTS ===
import json
from pathlib import Path

class SnapshotRegistry:
    """Lưu và compare output snapshots"""

    def __init__(self, snapshot_dir: str = "tests/snapshots"):
        self.dir = Path(snapshot_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def assert_matches_snapshot(self, name: str, actual: str, update: bool = False):
        """
        So sánh output với saved snapshot.
        Dùng update=True để update snapshot khi output thay đổi intentionally.
        """
        snapshot_file = self.dir / f"{name}.txt"

        if update or not snapshot_file.exists():
            snapshot_file.write_text(actual, encoding="utf-8")
            print(f"Snapshot {'updated' if update else 'created'}: {snapshot_file}")
            return

        expected = snapshot_file.read_text(encoding="utf-8")

        if actual != expected:
            # In diff
            import difflib
            diff = difflib.unified_diff(
                expected.splitlines(), actual.splitlines(),
                lineterm="", fromfile="expected", tofile="actual"
            )
            diff_text = "\n".join(diff)
            raise AssertionError(
                f"Snapshot mismatch for '{name}':\n{diff_text}\n\n"
                f"Run with update=True to update snapshot"
            )

# Dùng cho deterministic functions (không phải LLM output trực tiếp)
snapshots = SnapshotRegistry()

def test_prompt_template():
    """Test rằng prompt template format đúng"""
    # Đây là deterministic — không gọi LLM
    template = f"Answer this question: {{question}}\nContext: {{context}}"
    result = template.format(
        question="What is Python?",
        context="Python is a programming language."
    )
    snapshots.assert_matches_snapshot("prompt_template_basic", result)
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Chunk quá nhỏ (<100 tokens) | Mất context, poor retrieval quality | Bắt đầu khoảng 256-512 tokens rồi đo retrieval |
| Chunk quá lớn (>1000 tokens) | Noise trong context, tốn token | Giảm chunk hoặc dùng chunk theo cấu trúc tài liệu |
| Không có overlap giữa chunks | Mất thông tin ở boundary | Overlap 10-20% chunk size |
| Streaming buffer đầy | Tokens bị delay, jerky UX | `yield` ngay, không accumulate |
| Test LLM output với exact match | Tests fragile, fail liên tục | Dùng semantic similarity hoặc contains checks |
| Job queue không có timeout | Jobs treo mãi, queue đầy | Set `_job_timeout` cho mỗi job |
| Không handle vector DB connection failure | App crash khi DB down | Health check + graceful degradation |

## ✅ Best Practices

- **RAG: bắt đầu với chunk 256-512 tokens và overlap vừa phải, sau đó tune bằng eval set.** Không có chunk size đúng cho mọi loại tài liệu.
- **Reranking thường cải thiện retrieval quality** so với first-pass vector search, nhưng latency/cost tăng nên phải đo trên query set thật.
- **Hybrid search (vector + BM25) tốt hơn pure vector** cho queries có specific terms.
- **Streaming ngay từ đầu** — dễ hơn là add sau khi đã build.
- **Test AI logic riêng với AI output:** Mock LLM để test logic, integration test để test quality.
- **Job queue với TTL cho results:** Đặt TTL theo privacy/SLA; tránh để kết quả AI tích lũy vô hạn.
- **Health check endpoint** kiểm tra vector DB, LLM API, Redis trước khi accept requests.

## ⚖️ Trade-offs

**Vector DB options:**
| | ChromaDB | Qdrant | Pinecone |
|--|---------|--------|---------|
| Hosting | Local | Local/Cloud | Cloud only |
| Scale | <1M docs | 100M+ docs | Enterprise |
| Setup | `uv add chromadb` | Docker | API key |
| Cost | Local infra | Local/managed tùy deployment | Managed pricing thay đổi theo plan/usage |

**Job Queue: Celery vs ARQ:**
| | Celery | ARQ |
|--|--------|-----|
| Async | Partial | Native async |
| Dependencies | Redis/RabbitMQ | Redis only |
| Complexity | High | Low |
| Ecosystem | Mature | Growing |

## 🚀 Performance Notes

- **Embedding caching:** Cache embeddings của documents sau khi index, không re-encode khi query.
- **Async vector search:** ChromaDB và Qdrant đều support async queries — dùng `asyncio` để parallel queries.
- **Pre-filtering trước vector search:** Filter by metadata trước để giảm search space.
- **HNSW index:** Đảm bảo dùng HNSW index (mặc định trong hầu hết vector DBs) cho sub-linear search time.
- **Quantized embeddings:** Quantization có thể giảm memory đáng kể, nhưng recall/accuracy phụ thuộc model, corpus và search metric; đo trước khi bật production.

## 📝 Tóm tắt

- RAG pipeline = Load → Chunk → Embed → Index → Retrieve → Rerank → Generate. Mỗi bước đều có trade-offs.
- Chunking strategy phụ thuộc vào content type: markdown theo headers, PDF theo pages với size limit, general text theo semantic paragraphs
- Async job queue (ARQ/Celery) nên dùng cho AI tasks dài, dễ timeout, cần retry hoặc cần chạy ngoài request lifecycle
- Streaming SSE là tiêu chuẩn cho LLM responses, cải thiện UX đáng kể
- Testing AI: mock LLM cho unit tests (deterministic), dùng semantic similarity cho integration tests
- Production AI system cần tất cả layers từ ngày 29 + RAG + streaming + job queue
- Ngày 30 hoàn thiện bức tranh full-stack AI application với Python
