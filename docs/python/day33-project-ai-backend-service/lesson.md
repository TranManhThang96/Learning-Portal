# Ngày 33: Project Thực Chiến — AI Backend Service

## 🎯 Mục tiêu học tập
- Xây dựng hoàn chỉnh một AI Backend Service production-ready từ đầu
- Tích hợp FastAPI + PostgreSQL + Redis + Qdrant trong một hệ thống thống nhất
- Implement RAG pipeline với LangChain và vector database Qdrant
- Xây dựng streaming chat endpoint với Server-Sent Events (SSE)
- Implement JWT authentication và Redis-based rate limiting
- Đóng gói toàn bộ với Docker Compose

## 🔄 So sánh với NodeJS

| Khía cạnh | NodeJS/TypeScript | Python/FastAPI |
|-----------|-------------------|----------------|
| Framework | Express/NestJS | FastAPI |
| ORM | Prisma/TypeORM | SQLAlchemy 2.0 async |
| Validation | Zod/class-validator | Pydantic v2 |
| Vector DB client | qdrant-client (JS) | qdrant-client (Python) |
| LLM framework | LangChain.js | LangChain (Python) - mature hơn |
| Streaming | res.write() / SSE | StreamingResponse / SSE |
| Auth | passport.js / jsonwebtoken | python-jose / PyJWT |
| Rate limiting | express-rate-limit + Redis | custom Redis middleware |
| Docker | Dockerfile + compose | Dockerfile + compose (giống hệt) |

**Điểm khác biệt quan trọng nhất**: Python ecosystem cho AI/ML phong phú hơn nhiều — LangChain Python có nhiều tính năng và ổn định hơn LangChain.js.

## 📖 Lý thuyết & Hướng Dẫn Xây Dựng

### 1. Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Backend Service                       │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │  Client  │───▶│  FastAPI │───▶│   Auth Middleware    │  │
│  └──────────┘    │  :8000   │    └──────────────────────┘  │
│                  └────┬─────┘                               │
│                       │                                     │
│          ┌────────────┼────────────┐                        │
│          ▼            ▼            ▼                        │
│  ┌──────────────┐ ┌───────┐ ┌──────────────┐              │
│  │  /auth       │ │/chat  │ │  /documents  │              │
│  │  endpoints   │ │ SSE   │ │  endpoints   │              │
│  └──────────────┘ └───┬───┘ └──────┬───────┘              │
│                       │            │                        │
│              ┌────────▼──┐  ┌──────▼──────┐               │
│              │RAG Pipeline│  │  Embedding  │               │
│              │(LangChain) │  │   Service   │               │
│              └────┬───────┘  └──────┬──────┘               │
│                   │                 │                        │
│     ┌─────────────┼─────────────────┘                      │
│     ▼             ▼                 ▼                       │
│  ┌──────┐   ┌──────────┐    ┌──────────┐                  │
│  │Redis │   │ Qdrant   │    │PostgreSQL│                   │
│  │Cache │   │Vector DB │    │   DB     │                   │
│  └──────┘   └──────────┘    └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 2. Setup Project

**Tại sao dùng cấu trúc này?**
Cấu trúc monorepo với `app/` package giúp tách biệt concerns rõ ràng, dễ test từng component độc lập, và scale tốt khi project lớn.

```bash
# Khởi tạo project
mkdir ai-backend-service && cd ai-backend-service

# Tạo cấu trúc thư mục
mkdir -p app/{api,core,db,rag}
touch app/__init__.py app/api/__init__.py app/core/__init__.py
touch app/db/__init__.py app/rag/__init__.py

# Cài dependencies với uv
uv init
uv add fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic
uv add langchain langchain-openai langchain-qdrant langchain-text-splitters qdrant-client
uv add python-jose[cryptography] passlib[bcrypt] redis pydantic-settings
uv add httpx aiofiles structlog opentelemetry-api
uv add --dev pytest pytest-asyncio httpx coverage ruff mypy
```

LangChain integration packages change fast. Pin the project minor versions and add a smoke import test before the RAG lab. Avoid mixing current split packages with legacy imports such as `langchain.text_splitter` or `langchain_community.vectorstores.Qdrant` unless the project intentionally pins an older stack.

OpenAI guidance for new direct SDK code is Responses API-first. Trong scaffold này, RAG generation đi qua LangChain `ChatOpenAI` vì mục tiêu là luyện LangChain/Qdrant integration. Nếu viết service gọi OpenAI trực tiếp, dùng `client.responses.create(...)`, `response.output_text`, `tools=[...]`, `text={"format": ...}` cho structured outputs; chỉ giữ Chat Completions như compatibility path cho code cũ.

### 3. Configuration với Pydantic Settings

**WHY**: Centralize tất cả config, validate lúc startup, tránh runtime errors vì thiếu env var.

```python
# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "AI Backend Service"
    debug: bool = False
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/db
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_ttl: int = 3600  # 1 hour cache TTL

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"
    embedding_dim: int = 1536  # OpenAI ada-002

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-ada-002"
    mock_ai: bool = False  # true only for local smoke tests without API calls

    # Rate limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60  # seconds

    def require_openai_api_key(self) -> str:
        if self.mock_ai:
            return self.openai_api_key
        if not self.openai_api_key or self.openai_api_key == "sk-placeholder":
            raise ValueError("Set OPENAI_API_KEY or enable MOCK_AI=true for smoke tests")
        return self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4. Database Models với SQLAlchemy 2.0

**WHY**: SQLAlchemy 2.0 dùng mapped_column() thay vì Column() cũ — type-safe hơn, integrate tốt với mypy.

```python
# app/db/models.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="owner")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    chunk_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(50), default="processing")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="documents")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")
```

### 5. Database Session Management

```python
# app/db/session.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# Engine với connection pool được cấu hình đúng
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # Kiểm tra connection còn sống trước khi dùng
    echo=settings.debug,  # Log SQL queries khi debug
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # QUAN TRỌNG: tránh lazy loading sau commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency để inject database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### 6. JWT Authentication

```python
# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    user_id: str
    email: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if not user_id or not email:
            raise ValueError("Invalid token payload")
        return TokenData(user_id=user_id, email=email)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
```

### 7. Redis Rate Limiter

```python
# app/core/rate_limiter.py
import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import get_settings

settings = get_settings()


class RateLimiter:
    """Sliding window rate limiter dùng Redis sorted sets."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.max_requests = settings.rate_limit_requests
        self.window = settings.rate_limit_window

    async def check_rate_limit(self, key: str) -> None:
        now = time.time()
        window_start = now - self.window

        # Sử dụng Redis pipeline để atomic operations
        async with self.redis.pipeline() as pipe:
            # Xóa entries cũ ngoài window
            pipe.zremrangebyscore(key, 0, window_start)
            # Đếm requests trong window hiện tại
            pipe.zcard(key)
            # Thêm request mới
            pipe.zadd(key, {str(now): now})
            # Set TTL
            pipe.expire(key, self.window)
            results = await pipe.execute()

        current_count = results[1]  # zcard result

        if current_count >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window}s",
                headers={"Retry-After": str(self.window)},
            )


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency cho Redis client."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
```

### 8. RAG Pipeline

```python
# app/rag/pipeline.py
import uuid
from collections.abc import AsyncIterator

from langchain_core.documents import Document as LCDocument
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, VectorParams

from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """Bạn là trợ lý AI hữu ích. Trả lời câu hỏi của người dùng \
dựa trên context được cung cấp. Nếu không có thông tin trong context, \
hãy nói rõ điều đó thay vì bịa đặt.

Context:
{context}"""


class RAGPipeline:
    def __init__(self) -> None:
        api_key = settings.require_openai_api_key()
        self.embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=api_key,
        )
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=api_key,
            streaming=True,
            temperature=0.1,
        )
        self.qdrant_client = QdrantClient(url=settings.qdrant_url)
        self._ensure_collection()
        self.vectorstore = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=settings.qdrant_collection,
            embedding=self.embeddings,
        )

    def _ensure_collection(self) -> None:
        """Tạo Qdrant collection nếu chưa tồn tại."""
        collections = self.qdrant_client.get_collections().collections
        names = [c.name for c in collections]
        if settings.qdrant_collection not in names:
            self.qdrant_client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )

    def close(self) -> None:
        close = getattr(self.qdrant_client, "close", None)
        if callable(close):
            close()

    def _user_filter(self, user_id: str) -> Filter:
        return Filter(
            must=[
                FieldCondition(
                    key="metadata.user_id",
                    match=MatchValue(value=user_id),
                )
            ]
        )

    async def ingest_document(
        self, content: str, filename: str, user_id: str
    ) -> int:
        """Ingest document vào vector store. Returns số chunks."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_text(content)

        # Tạo LangChain documents với metadata
        documents = [
            LCDocument(
                page_content=chunk,
                metadata={
                    "source": filename,
                    "user_id": user_id,
                    "chunk_id": str(uuid.uuid4()),
                    "chunk_index": i,
                },
            )
            for i, chunk in enumerate(chunks)
        ]

        await self.vectorstore.aadd_documents(documents)
        return len(chunks)

    async def stream_answer(
        self, question: str, user_id: str
    ) -> AsyncIterator[str]:
        """Stream câu trả lời từ RAG pipeline."""
        user_filter = self._user_filter(user_id)

        # Chỉ retrieve documents của user hiện tại
        # QdrantVectorStore lưu metadata dưới payload `metadata`,
        # nên filter đúng là `metadata.user_id`, không phải `user_id`.
        retriever = self.vectorstore.as_retriever(
            search_kwargs={
                "k": 5,
                "filter": user_filter,
            }
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{question}"),
        ])

        def format_docs(docs: list[LCDocument]) -> str:
            return "\n\n".join(
                f"[{i+1}] {doc.page_content}"
                for i, doc in enumerate(docs)
            )

        chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        async for chunk in chain.astream(question):
            yield chunk
```

### 9. FastAPI App với Lifespan

```python
# app/main.py
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.db.session import engine
from app.rag.pipeline import RAGPipeline

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup và shutdown events."""
    # Startup
    logger.info("Starting up AI Backend Service")

    # Database schema thuộc Alembic, không auto-create ở startup.
    # Chạy: uv run alembic upgrade head
    app.state.rag_pipeline = RAGPipeline()
    logger.info("RAG pipeline ready")
    yield

    # Shutdown
    logger.info("Shutting down...")
    app.state.rag_pipeline.close()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
```

### 10. Streaming Chat Endpoint

```python
# app/api/chat.py
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.security import TokenData, get_current_user
from app.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: UUID | None = None


def get_rag_pipeline(request: Request) -> RAGPipeline:
    return request.app.state.rag_pipeline


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> StreamingResponse:
    """Streaming chat endpoint với SSE format."""

    async def generate():
        # SSE format: data: {...}\n\n
        try:
            async for chunk in pipeline.stream_answer(
                question=request.question,
                user_id=current_user.user_id,
            ):
                data = json.dumps({"chunk": chunk, "done": False})
                yield f"data: {data}\n\n"

            # Signal completion
            yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"

        except Exception as e:
            error_data = json.dumps({"error": str(e), "done": True})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Tắt nginx buffering
        },
    )
```

### 11. Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/aibackend
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: aibackend
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Dùng `expire_on_commit=True` (default) với async | LazyLoadingError khi access relationship sau commit | Set `expire_on_commit=False` trong sessionmaker |
| Tạo RAGPipeline() trong mỗi request | Tốn thời gian khởi tạo, connection leaks | Khởi tạo một lần trong app state hoặc singleton |
| Không set `X-Accel-Buffering: no` | Nginx buffer toàn bộ response, streaming không hoạt động | Luôn thêm header này cho SSE endpoints |
| Embed documents đồng bộ trong request handler | Request timeout với file lớn | Dùng background task hoặc async job queue |
| Không filter theo user_id khi query Qdrant | Một user xem được documents của user khác | Luôn filter metadata theo user_id |
| Pool size quá nhỏ với nhiều concurrent users | Connection exhaustion, timeout | Tính toán: pool_size = (worker_count × 2) + headroom |

## ✅ Best Practices

- **Tách RAG pipeline thành service class** — dễ mock trong tests, dễ swap implementation
- **Dùng background tasks cho document ingestion** — không block request handler
- **Validate file type và size** ở API layer trước khi process
- **Cache embeddings** khi có thể — tốn tiền nhất trong pipeline
- **Implement circuit breaker** cho OpenAI API calls — tránh cascade failures
- **Log structured với structlog** — dễ query trong Elasticsearch/Grafana
- **Dùng Alembic** cho database migrations, không dùng `create_all()` trong production
- **Set timeout cho tất cả external calls** — Qdrant, OpenAI, Redis

## ⚖️ Trade-offs

### Qdrant vs pgvector
| | Qdrant | pgvector |
|---|---|---|
| **Performance** | Tốt hơn cho vector-only queries | Chậm hơn khi data lớn |
| **Infrastructure** | Service riêng biệt | Tích hợp trong PostgreSQL |
| **Filtering** | Payload filtering mạnh | SQL WHERE clause linh hoạt hơn |
| **Khi nào dùng** | Large-scale vector search | Đã có PostgreSQL, data nhỏ-vừa |

### Streaming vs Non-streaming
- **Streaming**: UX tốt hơn (user thấy response ngay), phức tạp hơn để implement
- **Non-streaming**: Đơn giản hơn, dễ cache toàn bộ response, dễ test

## 🚀 Performance Notes

- **Batch embedding**: Embed nhiều chunks cùng lúc thay vì từng cái một (giảm API calls 10x)
- **Async tất cả I/O**: Không dùng requests, dùng httpx; không dùng psycopg2, dùng asyncpg
- **Connection pooling**: PostgreSQL và Qdrant đều cần pool size phù hợp
- **Redis caching**: Cache embeddings của queries phổ biến (semantic similarity cache)
- **Chunk size tuning**: Chunk nhỏ → retrieve chính xác hơn, chunk lớn → context đầy đủ hơn

## 📝 Tóm tắt

- Kiến trúc layered: API → Service → Repository → Database
- FastAPI + Pydantic v2 + SQLAlchemy 2.0 là bộ ba hoàn hảo cho Python backend
- RAG pipeline: Ingest → Embed → Store → Retrieve → Generate
- Streaming response dùng `StreamingResponse` với SSE format
- Docker Compose orchestrate toàn bộ infrastructure (API, DB, Redis, Qdrant)
- Luôn filter theo user context khi query vector store
- Background tasks cho heavy operations, không block request handler
