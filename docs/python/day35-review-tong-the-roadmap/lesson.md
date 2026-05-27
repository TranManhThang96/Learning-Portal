# Ngày 35: Review Tổng Thể & Roadmap Tiếp Theo

## 🎯 Mục tiêu học tập
- Self-assessment toàn diện kiến thức Python sau 35 ngày
- Code review projects từ ngày 33-34 với góc nhìn senior
- Chuẩn bị cho Python senior interviews
- Lập kế hoạch 6 tháng tiếp theo để master Python AI Engineering
- Biết roadmap để tiếp tục phát triển sau khóa học

## 🔄 So sánh với NodeJS — Tổng Kết Cuối Khóa

| Khía cạnh | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| **Typing** | Structural typing (TypeScript) | Gradual typing (mypy) |
| **Async** | Single-threaded event loop | asyncio + GIL (multi-threaded cho I/O) |
| **Package manager** | npm/yarn/pnpm | pip/Poetry/uv |
| **Framework** | Express/NestJS/Fastify | FastAPI/Django/Flask |
| **ORM** | Prisma/TypeORM/Drizzle | SQLAlchemy 2.0 |
| **Testing** | Jest/Vitest | pytest |
| **AI/ML** | LangChain.js (limited) | Python ecosystem (dominant) |
| **Performance** | V8 JIT (fast for I/O) | CPython (slower, PyPy/Cython cho perf) |
| **Community** | Large, frontend-leaning | Huge, science/AI-leaning |
| **Job market** | Strong (web/startup) | Very strong (AI/data/backend) |

**Khi nào dùng Python thay vì NodeJS:**
- AI/ML applications → Python
- Data processing → Python
- Scientific computing → Python
- Khi team có Python expertise → Python
- Khi dùng LangGraph, HuggingFace, PyTorch → bắt buộc Python

**Khi nào vẫn dùng NodeJS:**
- Real-time apps (WebSocket-heavy) → NodeJS tốt hơn
- Frontend BFF (Backend for Frontend) → NodeJS
- Team chỉ biết JS → NodeJS
- Microservices nhỏ không cần AI → cả hai đều OK

## 📖 Nội dung

### 1. Self-Assessment Checklist: Python Junior → Senior

Đánh giá bản thân theo thang điểm:
- ❌ Chưa biết
- 🟡 Hiểu lý thuyết, chưa thực hành nhiều
- ✅ Thoải mái áp dụng vào production

#### Python Core

| Skill | Self-Assessment |
|-------|----------------|
| Variables, types, type hints | |
| String formatting (f-strings) | |
| Control flow (if/match/for/while) | |
| List/dict/set comprehensions | |
| Functions: args, kwargs, lambda | |
| Closures và scope | |
| Decorators (tạo và dùng) | |
| Generator functions (yield) | |
| Class, inheritance, MRO | |
| Dunder methods (`__str__`, `__eq__`, ...) | |
| @property, @classmethod, @staticmethod | |
| Abstract classes (ABC) | |
| Type hints nâng cao (TypeVar, Generic, Protocol) | |
| Exception hierarchy, custom exceptions | |
| Context managers (`with`, `__enter__`/`__exit__`) | |
| Async/await, event loop | |
| asyncio.gather, TaskGroup | |
| GIL — khi nào cần threading vs multiprocessing | |
| Pathlib, file I/O | |
| functools: lru_cache, partial, reduce | |

#### FastAPI & Web

| Skill | Self-Assessment |
|-------|----------------|
| Routing, path/query params | |
| Request body với Pydantic | |
| Dependency Injection | |
| Middleware | |
| Background tasks | |
| Lifespan events (startup/shutdown) | |
| StreamingResponse (SSE) | |
| JWT Authentication | |
| Exception handlers | |
| Response models | |
| OpenAPI docs | |
| Testing FastAPI với httpx | |

#### Database & Caching

| Skill | Self-Assessment |
|-------|----------------|
| SQLAlchemy 2.0: mapped_column, Mapped | |
| Async SQLAlchemy + asyncpg | |
| Relationships: one-to-many, many-to-many | |
| Alembic migrations | |
| N+1 problem và fix (selectinload/joinedload) | |
| Connection pooling | |
| Redis: get/set/expire | |
| Redis Sorted Sets (rate limiting) | |
| Repository pattern | |

#### AI/ML Stack

| Skill | Self-Assessment |
|-------|----------------|
| OpenAI Responses API và SDK env-key setup | |
| Chat Completions legacy/compatibility path | |
| Streaming responses | |
| Structured outputs với Pydantic | |
| Prompt engineering (system/few-shot/CoT) | |
| RAG architecture | |
| Text splitting strategies | |
| Embedding models | |
| Vector stores (Chroma, Qdrant) | |
| LangChain LCEL chains | |
| LangChain agents | |
| LangGraph state machines | |
| Human-in-the-loop | |
| LangGraph persistence: checkpointer lifespan + `thread_id` | |
| LangGraph interrupt/resume với `Command(resume=...)` | |
| LlamaIndex | |
| Local LLMs (Ollama) | |
| RAG evaluation (RAGAS) | |
| LLM observability (LangSmith) | |
| Cost optimization | |
| Guardrails | |

#### Production Skills

| Skill | Self-Assessment |
|-------|----------------|
| Docker: Dockerfile multi-stage | |
| Docker Compose | |
| Environment config (pydantic-settings) | |
| `.env.example` không chứa secret thật hoặc placeholder nguy hiểm | |
| Structured logging (structlog) | |
| Health checks | |
| Graceful shutdown | |
| App-level singleton resource lifecycle | |
| cProfile, py-spy profiling | |
| pytest: fixtures, parametrize, markers | |
| Async testing (pytest-asyncio) | |
| Mocking (pytest-mock) | |
| CI/CD basics | |
| Pre-commit hooks | |

### 2. Code Review — Project AI Backend (Ngày 33)

**Những điểm mạnh cần giữ:**
- Async throughout — không có blocking calls
- Pydantic v2 cho request/response validation
- Dependency injection cho DB, Redis
- Structured logging với structlog
- Multi-stage Dockerfile với non-root user
- Docker Compose với health checks

**Những fixes đã được đưa vào scaffold và phải giữ khi refactor:**

```python
# ✅ RAGPipeline singleton trong app state
from fastapi import Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag_pipeline = RAGPipeline()
    yield
    app.state.rag_pipeline.close()

@router.post("/upload")
async def upload(request: Request, ...):
    pipeline = request.app.state.rag_pipeline

# ✅ Migration story rõ ràng
# app startup không gọi Base.metadata.create_all()
# schema nằm ở alembic/versions/0001_initial_schema.py
# chạy: uv run alembic upgrade head

# ✅ Config fail-fast nhưng vẫn smoke-test được
# OPENAI_API_KEY="" + MOCK_AI=false -> raise trước khi tạo OpenAI client
# MOCK_AI=true -> dùng deterministic local embeddings/context dump

# ⚠️ Portfolio improvement: thêm pagination cho list documents
@router.get("/")
async def list_documents(...):
    result = await db.execute(select(Document)...)  # Fetch ALL

# ✅ Fix: Cursor-based pagination
@router.get("/")
async def list_documents(
    limit: int = Query(default=20, le=100),
    cursor: str | None = None,
    ...
):
    query = select(Document).where(Document.owner_id == current_user.user_id)
    if cursor:
        query = query.where(Document.id > uuid.UUID(cursor))
    query = query.order_by(Document.id).limit(limit + 1)
    result = await db.execute(query)
    docs = result.scalars().all()
    has_more = len(docs) > limit
    return {
        "items": docs[:limit],
        "next_cursor": str(docs[-2].id) if has_more else None,
    }
```

**Cần kiểm tra thêm khi hoàn thiện portfolio:**
- Background ingestion/worker queue nếu upload file lớn hoặc nhiều concurrent uploads.
- Pagination cho `GET /documents`.
- Integration test upload TXT → Qdrant ingest → chat stream ở `MOCK_AI=true`, sau đó smoke real mode với key thật.
- Qdrant filter phải dùng metadata path đúng (`metadata.user_id`) theo integration package đang pin.

### 3. Code Review — Project Agentic System (Ngày 34)

**Những fixes đã được đưa vào scaffold và phải giữ khi refactor:**

```python
# ✅ Checkpointer + compiled graph sống theo app lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with checkpointer_lifespan() as checkpointer:
        app.state.agent_graph = build_graph().compile(checkpointer=checkpointer)
        yield

# ✅ Human approval resume đúng interrupt point
from langgraph.types import Command

result = await graph.ainvoke(
    Command(resume={"approved": approved}),
    config={"configurable": {"thread_id": thread_id}},
)

# ❌ Vấn đề 2: Code executor dùng exec() — cần better sandboxing
def execute_python_code(code: str) -> str:
    exec(code, restricted_globals)  # Vẫn có thể bị bypass

# ✅ Fix production: Dùng E2B hoặc Docker container
# uv add e2b
from e2b_code_interpreter import Sandbox

async def execute_code_e2b(code: str) -> str:
    async with Sandbox() as sandbox:
        execution = await sandbox.notebook.exec_cell(code)
        return execution.text

# ❌ Vấn đề 3: Không có rate limiting cho agent runs
# Agent run có thể tốn nhiều tokens → cần budget control

# ✅ Fix: Token budget per user per day
async def check_token_budget(user_id: str, redis_client: Redis) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"token_budget:{user_id}:{today}"
    used = int(await redis_client.get(key) or 0)
    if used > 100_000:  # 100K tokens/day limit
        raise HTTPException(429, "Daily token budget exceeded")
```

**Cần kiểm tra thêm khi hoàn thiện portfolio:**
- Không tạo `AsyncPostgresSaver` hoặc compile graph trong route handler.
- `/agent/run` phải trả `awaiting_approval` khi result có `__interrupt__`.
- `/agent/approve` phải dùng cùng `thread_id`; nếu đổi thread_id thì resume sẽ không tìm thấy checkpoint.
- Có smoke mode `MOCK_AI=true` + `CHECKPOINT_BACKEND=memory` và real mode với PostgreSQL.

### 4. Senior Python Interview Questions

### Portfolio Deliverables Sau Fix Day 33/34

Để coi hai project cuối khóa là portfolio-ready, deliverables tối thiểu là:

| Artifact | Acceptance criteria |
|----------|---------------------|
| Day 33 `.env.example` | Không chứa secret thật; placeholder key fail-fast; có `MOCK_AI=true` smoke path |
| Day 33 migrations | `uv run alembic upgrade head` tạo schema từ `0001_initial_schema.py`; app không auto `create_all()` |
| Day 33 RAG flow | RAG pipeline là singleton lifecycle-managed; Qdrant metadata filter theo user; import dùng `langchain-qdrant` |
| Day 33 smoke | Test config/mock embeddings chạy không cần OpenAI; real-mode docs nói rõ cần key thật |
| Day 34 checkpointer | `AsyncPostgresSaver` mở trong lifespan; graph compile một lần; route handler không tạo pool mới |
| Day 34 interrupt | Approval flow dùng `interrupt()` và `Command(resume=...)` với cùng `thread_id` |
| Day 34 smoke | `MOCK_AI=true` + `CHECKPOINT_BACKEND=memory` chạy được không cần OpenAI/Postgres |
| Final docs | README, lesson, exercises không còn hướng dẫn copy pattern cũ |

#### Python Internals

**Q1: GIL là gì và ảnh hưởng đến performance như thế nào?**

> GIL (Global Interpreter Lock) là mutex trong CPython ngăn multiple threads chạy Python bytecode đồng thời. Điều này có nghĩa là Python threads không thể tận dụng multiple CPU cores cho CPU-bound tasks.
>
> **Ảnh hưởng:**
> - CPU-bound: Threads không giúp ích, dùng `multiprocessing` hoặc `ProcessPoolExecutor`
> - I/O-bound: Threads hoạt động tốt vì GIL được release khi chờ I/O
> - `asyncio`: Không bị ảnh hưởng vì single-threaded, dùng cooperative multitasking
>
> **Fix**: `multiprocessing` cho CPU-bound, `asyncio` cho I/O-bound.

**Q2: Sự khác biệt giữa `__new__` và `__init__`?**

> - `__new__`: Class method, tạo instance mới (allocate memory), return instance
> - `__init__`: Instance method, initialize instance sau khi tạo, return None
> - Thứ tự: `__new__` → `__init__`
> - Dùng `__new__` khi: implement Singleton, immutable types, metaclasses

**Q3: Python memory management hoạt động thế nào?**

> - **Reference counting**: Mỗi object có `ob_refcnt`, khi = 0 → deallocate
> - **Garbage collector**: Xử lý circular references mà reference counting không catch được
> - **Memory pools**: CPython dùng pymalloc cho small objects (< 512 bytes)
> - **Weak references**: `weakref.ref()` — không tăng refcount

#### Async Programming

**Q4: `asyncio.gather` vs `asyncio.TaskGroup` — khi nào dùng cái nào?**

> ```python
> # gather: Python 3.7+, nếu một task fail có thể tiếp tục các task khác
> results = await asyncio.gather(task1(), task2(), return_exceptions=True)
>
> # TaskGroup: Python 3.11+, structured concurrency
> # Nếu một task fail → cancel tất cả tasks còn lại → exception propagates
> async with asyncio.TaskGroup() as tg:
>     t1 = tg.create_task(task1())
>     t2 = tg.create_task(task2())
> ```
> Prefer `TaskGroup` cho Python 3.11+ — safer, clearer cancellation semantics.

**Q5: Giải thích `async context manager` và implement một cái.**

> ```python
> class DatabaseConnection:
>     async def __aenter__(self):
>         self.conn = await create_connection()
>         return self.conn
>
>     async def __aexit__(self, exc_type, exc_val, exc_tb):
>         await self.conn.close()
>         return False  # Don't suppress exceptions
>
> # Dùng với contextlib
> from contextlib import asynccontextmanager
>
> @asynccontextmanager
> async def get_connection():
>     conn = await create_connection()
>     try:
>         yield conn
>     finally:
>         await conn.close()
> ```

#### FastAPI & System Design

**Q6: Giải thích FastAPI Dependency Injection và tại sao nó quan trọng.**

> FastAPI DI cho phép:
> 1. **Reusability**: `get_db()` dùng ở mọi route
> 2. **Testability**: Mock dễ dàng với `app.dependency_overrides`
> 3. **Resource management**: DB sessions auto-close sau request
> 4. **Chaining**: Dependencies có thể depend on other dependencies
>
> ```python
> # Testing with override:
> app.dependency_overrides[get_db] = lambda: mock_db_session
> ```

**Q7: Làm thế nào để tránh N+1 query problem trong SQLAlchemy?**

> ```python
> # N+1 problem:
> users = await db.execute(select(User))
> for user in users.scalars():
>     # Mỗi loop tạo thêm 1 query!
>     print(user.posts)  # Lazy load
>
> # Fix với selectinload (IN query):
> from sqlalchemy.orm import selectinload
> users = await db.execute(
>     select(User).options(selectinload(User.posts))
> )
> # 2 queries total: 1 for users, 1 for all posts
>
> # Fix với joinedload (JOIN):
> from sqlalchemy.orm import joinedload
> users = await db.execute(
>     select(User).options(joinedload(User.posts))
> )
> # 1 query với JOIN (cẩn thận với many-to-many → data duplication)
> ```

**Q8: Design một rate limiter production-ready.**

> ```python
> # Sliding window với Redis Sorted Sets:
> async def check_rate_limit(redis: Redis, key: str, limit: int, window: int):
>     now = time.time()
>     async with redis.pipeline() as pipe:
>         pipe.zremrangebyscore(key, 0, now - window)
>         pipe.zcard(key)
>         pipe.zadd(key, {str(now): now})
>         pipe.expire(key, window)
>         _, count, _, _ = await pipe.execute()
>     if count >= limit:
>         raise RateLimitExceeded()
> ```

#### AI System Design

**Q9: Design một RAG system có thể handle 1 triệu documents.**

> Architecture:
> - **Ingestion**: Kafka queue → workers → batch embedding → Qdrant
> - **Vector store**: Qdrant với sharding, không Chroma (không scale)
> - **Caching**: Semantic cache với Redis + embedding similarity
> - **Retrieval**: Hybrid search (dense + sparse), reranking
> - **Observability**: LangSmith/Langfuse cho tracing
> - **Cost**: Cache embeddings, batch requests, use small embedding models

**Q10: Khi nào RAG vs Fine-tuning vs Prompt Engineering?**

> | Approach | Dùng khi |
> |----------|---------|
> | Prompt Engineering | Thay đổi behavior, không cần domain knowledge mới |
> | RAG | Cần up-to-date info, private data, source citations |
> | Fine-tuning | Cần specific style/format, RAG không đủ, có labeled data |
>
> **Thứ tự thử**: Prompt Engineering → RAG → Fine-tuning (theo độ phức tạp và chi phí)

### 5. Roadmap 6 Tháng Tiếp Theo

#### Tháng 1-2: Consolidation
- Build 2 personal projects từ đầu (không nhìn tutorial)
- Contribute fixes/docs cho 1 OSS Python project
- Target: `mypy --strict` pass trên tất cả code bạn viết
- Daily: Read 1 Python PEP hoặc blog post

#### Tháng 3-4: Specialization
- Chọn 1 trong 2 paths:
  - **Path A (AI Engineering)**: LangGraph advanced, multi-agent systems, MLflow, eval frameworks
  - **Path B (Backend Engineering)**: Celery/ARQ, gRPC, Kafka với Python, advanced SQLAlchemy
- Build một production-scale project (real traffic, real database)
- Study: "Fluent Python" by Luciano Ramalho (bắt buộc)

#### Tháng 5-6: Advanced Topics
- CPython internals: đọc source code, hiểu memory model
- Performance: Cython, C extensions, Numba cho CPU-bound
- Advanced testing: property-based testing với Hypothesis
- Open source: contribute feature, không chỉ bug fixes
- Interview prep: LeetCode Python, system design

### 6. Tài Nguyên Nâng Cao

#### Sách bắt buộc
1. **Fluent Python** (Luciano Ramalho) — Python "Bible", phải đọc
2. **Python Cookbook** (David Beazley) — Advanced recipes, patterns
3. **Architecture Patterns with Python** (Harry Percival) — DDD, Clean Architecture
4. **Designing Data-Intensive Applications** (Martin Kleppmann) — System design

#### Khóa học nâng cao
- **FastAPI Advanced** — full course từ official docs
- **LangChain/LangGraph** — official tutorials + cookbook
- **Deep Learning Specialization** (Coursera, Andrew Ng) — nền tảng ML

#### OSS Projects để contribute
- **FastAPI** — github.com/fastapi/fastapi — Start với bug fixes
- **LangChain** — github.com/langchain-ai/langchain — Documentation improvements
- **SQLAlchemy** — Advanced, nhưng học được nhiều
- **Pydantic** — High impact, Python-heavy

## ⚠️ Common Mistakes — Final Summary

| Sai lầm phổ biến nhất | Cách nhớ |
|----------------------|---------|
| Blocking call trong async context | "async = non-blocking, luôn luôn" |
| Global mutable state | "State trong app, không trong module" |
| Missing type hints | "Type hints = documentation chạy được" |
| Bare `except:` hoặc catch `BaseException` | "Chỉ catch exception bạn xử lý được" |
| `except Exception` quá rộng ở boundary không log/raise lại | "Catch specific, log structured, preserve cause" |
| String formatting với + | "f-string only" |
| `datetime.now()` without timezone | "Always UTC: `datetime.now(timezone.utc)`" |
| Mutable default args | "Default None, assign inside" |
| Not closing DB sessions | "Context manager or DI, always" |

## ✅ Top 20 Best Practices — Toàn Khóa

1. **Type hints everywhere** — mypy strict mode
2. **Pydantic cho tất cả data validation** — không validate manually
3. **async/await cho mọi I/O** — không blocking calls
4. **asyncio.gather cho parallel tasks** — không serial await trong loop
5. **Dependency Injection** — không global state
6. **Structured logging** — không print()
7. **Custom exceptions** — không raise bare Exception
8. **Context managers cho resources** — không manual open/close
9. **f-strings** — không string concatenation
10. **Comprehensions** — không append trong loop khi có thể
11. **lru_cache cho expensive pure functions** — không redundant computation
12. **expire_on_commit=False** với async SQLAlchemy — tránh lazy load errors
13. **response_model cho tất cả FastAPI endpoints** — không raw dict
14. **Parameterized SQL** (SQLAlchemy ORM) — không f-string SQL
15. **Hash passwords** với bcrypt — không plaintext
16. **Environment config** với pydantic-settings — không hardcode secrets
17. **Multi-stage Dockerfile** với non-root user — bảo mật production
18. **pytest fixtures** — không copy-paste test setup
19. **Temperature thấp** cho factual LLM tasks — ổn định hơn nhưng không tuyệt đối deterministic
20. **Explicit retry logic** cho external APIs — không assume success

## 📝 Tóm tắt Toàn Khóa 35 Ngày

**Giai đoạn 1 (Ngày 1-15):** Từ zero đến production Python developer
- Tools: pyenv, uv, ruff, mypy, pre-commit
- Core: types, OOP, async, decorators, generators
- FastAPI: routing, DI, auth, DB, caching
- Testing, Docker, deployment

**Giai đoạn 2 (Ngày 16-30):** AI Engineering với Python
- OpenAI API, prompt engineering
- RAG pipeline: splitting, embedding, vector stores
- LangChain, LlamaIndex, LangGraph
- Agents, tools, human-in-the-loop
- Production AI: observability, caching, guardrails

**Giai đoạn 3 (Ngày 31-35):** Consolidation và thực chiến
- Code review và refactoring
- Performance profiling
- Two production projects: AI Backend + Agentic System
- Interview prep và roadmap

**Bạn đã đi được một hành trình dài từ một Senior NodeJS Developer chưa biết Python, đến một Python engineer có thể build production AI applications. Đây chỉ là bước đầu — hãy tiếp tục build, learn, và contribute!**
