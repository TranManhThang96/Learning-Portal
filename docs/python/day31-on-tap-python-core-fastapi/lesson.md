# Ngày 31: Ôn tập Python Core + FastAPI

## 🎯 Mục tiêu học tập
- Consolidate toàn bộ kiến thức Python core từ ngày 1-15
- Nhận diện và sửa các anti-patterns phổ biến trong Python/FastAPI code
- Profiling và tối ưu performance với cProfile, py-spy, memory_profiler
- Refactor một FastAPI app "bad code" → production-ready step by step
- Xây dựng code review checklist chuẩn cho Python projects

## 🔄 So sánh với NodeJS

| Concept | NodeJS/TypeScript | Python |
|---------|-------------------|--------|
| **Profiling** | `clinic.js`, `0x`, Chrome DevTools | `cProfile`, `py-spy`, `memory_profiler` |
| **Memory leaks** | `heapdump`, `node --inspect` | `tracemalloc`, `objgraph`, `memory_profiler` |
| **Hot reload** | `nodemon`, `ts-node-dev` | `uvicorn --reload` |
| **Linting** | ESLint + Prettier | Ruff (thay cả hai) |
| **Type checking** | `tsc --noEmit` | `mypy --strict` |
| **Code review** | Manual + ESLint rules | Manual + Ruff + mypy |

**Key insight**: Python profiling tools đa dạng hơn vì Python có GIL — cần phân biệt CPU-bound vs I/O-bound bottlenecks. NodeJS chỉ có một thread nên profiling đơn giản hơn.

## 📖 Lý thuyết

### 1. Review Async Python — Những Điều Hay Bị Nhầm

**WHY**: Sau 30 ngày học, đây là nguồn bug #1 trong Python backend code.

```python
# ❌ WRONG: Blocking call trong async function — giết chết performance
import time
import asyncio

async def bad_handler():
    time.sleep(2)  # Block toàn bộ event loop!
    return {"result": "done"}

# ✅ CORRECT: Non-blocking
async def good_handler():
    await asyncio.sleep(2)  # Nhường control cho event loop
    return {"result": "done"}

# ❌ WRONG: Không dùng gather khi có thể parallel
async def fetch_all_serial(ids: list[int]):
    results = []
    for id in ids:
        result = await fetch_one(id)  # Serial — chậm N lần
        results.append(result)
    return results

# ✅ CORRECT: Parallel execution
async def fetch_all_parallel(ids: list[int]):
    tasks = [fetch_one(id) for id in ids]
    return await asyncio.gather(*tasks)  # Tất cả chạy đồng thời

# Demo: so sánh thời gian
async def demo():
    import time

    # Serial: ~3 seconds
    start = time.perf_counter()
    await fetch_all_serial([1, 2, 3])
    print(f"Serial: {time.perf_counter() - start:.2f}s")

    # Parallel: ~1 second
    start = time.perf_counter()
    await fetch_all_parallel([1, 2, 3])
    print(f"Parallel: {time.perf_counter() - start:.2f}s")
```

**asyncio.gather vs asyncio.TaskGroup (Python 3.11+)**:

```python
import asyncio

# asyncio.gather — cách cũ, vẫn phổ biến
async def with_gather():
    results = await asyncio.gather(
        task1(),
        task2(),
        return_exceptions=True,  # Không raise, trả về exception như result
    )
    for r in results:
        if isinstance(r, Exception):
            print(f"Task failed: {r}")

# asyncio.TaskGroup — Python 3.11+, cancel-safe hơn
async def with_task_group():
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(task1())
        t2 = tg.create_task(task2())
    # Tất cả tasks xong hoặc tất cả bị cancel khi có exception
    return t1.result(), t2.result()
```

### 2. Advanced Type Hints Review

**WHY**: Type hints giúp IDE và mypy catch bugs trước runtime — đặc biệt quan trọng trong Python vì không có compiler.

```python
from typing import TypeVar, Generic, Protocol, runtime_checkable
from collections.abc import Callable, Awaitable

# TypeVar với bounds
T = TypeVar("T")
NumericT = TypeVar("NumericT", int, float)

def first(items: list[T]) -> T | None:
    return items[0] if items else None

# Protocol — duck typing với type safety (tương đương interface trong TS)
@runtime_checkable
class Cacheable(Protocol):
    def cache_key(self) -> str: ...
    def cache_ttl(self) -> int: ...

# Generic class — tương đương Generic<T> trong TypeScript
class Repository(Generic[T]):
    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def save(self, key: str, value: T) -> None:
        self._store[key] = value

    def get(self, key: str) -> T | None:
        return self._store.get(key)

# TypeAlias (Python 3.12+)
type UserId = str
type UserDict = dict[str, "User"]

# ParamSpec — type hints cho decorators nhận function arguments
from typing import ParamSpec
P = ParamSpec("P")

def logged(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"Calling {func.__name__}")
        result = await func(*args, **kwargs)
        print(f"Done {func.__name__}")
        return result
    return wrapper

@logged
async def my_handler(user_id: str, data: dict) -> dict:
    return {"user_id": user_id}
```

### 3. Decorators — Production Patterns

```python
import functools
import time
import asyncio
from typing import TypeVar, Callable
from collections.abc import Awaitable

T = TypeVar("T")

# Retry decorator với exponential backoff
def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Exception | None = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception  # type: ignore

        return wrapper
    return decorator

# Sử dụng
@retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError, TimeoutError))
async def call_external_api(url: str) -> dict:
    # ...
    pass

# Cache decorator với TTL
from functools import lru_cache
import time

class TTLCache:
    """Thread-safe cache với TTL support."""

    def __init__(self, ttl: int = 60) -> None:
        self._cache: dict = {}
        self._timestamps: dict = {}
        self.ttl = ttl

    def get(self, key):
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            # Expired
            del self._cache[key]
            del self._timestamps[key]
        return None

    def set(self, key, value) -> None:
        self._cache[key] = value
        self._timestamps[key] = time.time()


def cached(ttl: int = 60):
    cache = TTLCache(ttl=ttl)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            cache.set(key, result)
            return result
        return wrapper
    return decorator
```

### 4. Pydantic v2 — Review Các Pattern Quan Trọng

```python
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Annotated
import re

# Custom types với Annotated
PositiveInt = Annotated[int, Field(gt=0)]
NonEmptyStr = Annotated[str, Field(min_length=1, max_length=255)]

class UserCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,  # Tự động strip whitespace
        validate_assignment=True,    # Validate khi assign field
    )

    email: str
    password: str = Field(min_length=8)
    age: PositiveInt
    name: NonEmptyStr

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @model_validator(mode="after")
    def validate_password_not_contains_name(self) -> "UserCreate":
        if self.name.lower() in self.password.lower():
            raise ValueError("Password should not contain your name")
        return self

# Nested models
class Address(BaseModel):
    street: str
    city: str
    country: str = "VN"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Cho phép từ ORM objects

    id: str
    email: str
    address: Address | None = None

# Serialization
user = UserResponse(id="123", email="user@test.com")
print(user.model_dump())             # dict
print(user.model_dump_json())        # JSON string
print(user.model_dump(exclude={"email"}))  # Exclude fields
```

### 5. Code Review Checklist

| Category | Checklist Item | Bad Example | Good Example |
|----------|---------------|-------------|--------------|
| **Async** | Không blocking call trong async function | `time.sleep(1)` | `await asyncio.sleep(1)` |
| **Async** | Dùng gather cho parallel tasks | Serial await trong loop | `asyncio.gather(*tasks)` |
| **Types** | Tất cả functions có type hints | `def get(id):` | `def get(id: str) -> User:` |
| **Types** | Không dùng `Any` trừ khi bắt buộc | `data: Any` | `data: dict[str, str]` |
| **Pydantic** | Response model cho tất cả endpoints | Trả về raw dict | `response_model=UserResponse` |
| **DB** | Không N+1 queries | Lazy load trong loop | `selectinload()` hoặc `joinedload()` |
| **DB** | Đóng session đúng cách | Manual session management | `async with AsyncSession()` |
| **Error** | Custom exceptions, không raise generic | `raise Exception("error")` | `raise UserNotFoundError(user_id)` |
| **Security** | Hash password trước khi lưu | `user.password = raw_password` | `user.hashed_password = hash_password(pw)` |
| **Security** | Validate input đầy đủ | Không validate | Pydantic validators |
| **Logging** | Structured logging | `print("error:", e)` | `logger.error("event", error=str(e))` |
| **Config** | Không hardcode secrets | `API_KEY = "sk-..."` | `settings.api_key` từ env |
| **Tests** | Coverage > 80% | Không có tests | pytest với fixtures |
| **Deps** | Pin versions | `fastapi` | `fastapi>=0.115,<0.116` |

**Checklist này phải map được vào lỗi thật của Day 33/34, không chỉ là khẩu hiệu:**

| Checklist Item | Lỗi đã thấy trong scaffold | Cách review/fix |
|----------------|----------------------------|-----------------|
| Resource lifecycle | Day 33 `documents.py` từng tạo `RAGPipeline()` mỗi upload | Init singleton trong FastAPI lifespan/app state, cleanup Qdrant client khi shutdown |
| Migration ownership | Day 33 README nói có Alembic nhưng thiếu revision | Có `alembic/versions/0001_initial_schema.py`; app startup không gọi `create_all()` |
| Config/secrets | Day 33/34 dùng `sk-placeholder` như default nguy hiểm | `.env.example` để key rỗng; code fail-fast trừ khi `MOCK_AI=true` |
| Dependency drift | Day 32/33 dùng import LangChain cũ/mới lẫn lộn | Dùng packages tách riêng (`langchain-qdrant`, `langchain-text-splitters`) và smoke import test |
| Streaming lifecycle | Day 33 chat giữ DB dependency dù stream không dùng DB | Không inject DB session vào streaming endpoint nếu chỉ cần auth + RAG |
| Checkpointer lifecycle | Day 34 từng tạo Postgres checkpointer/compile graph mỗi request | Mở `AsyncPostgresSaver` trong lifespan, compile graph một lần vào `app.state` |
| Human-in-the-loop | Day 34 approval từng update state thủ công thay vì resume interrupt | Dùng `interrupt()` trong graph và `Command(resume=...)` với cùng `thread_id` |

### 6. Performance Profiling

**WHY**: "Premature optimization is the root of all evil" — Donald Knuth. Nhưng sau khi code chạy được, phải đo trước khi optimize.

#### cProfile — CPU Profiling

```python
import cProfile
import pstats
import asyncio
from io import StringIO

# Profiling sync code
def profile_sync():
    profiler = cProfile.Profile()
    profiler.enable()

    # Code cần profile
    result = compute_heavy_task()

    profiler.disable()
    stats = pstats.Stats(profiler, stream=StringIO())
    stats.sort_stats("cumulative")
    stats.print_stats(20)  # Top 20 functions
    return result

# Profiling async code với asyncio
async def profile_async_main():
    profiler = cProfile.Profile()
    profiler.enable()

    # Chạy async code
    await asyncio.gather(task1(), task2(), task3())

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("tottime")  # Sắp xếp theo total time (không tính sub-calls)
    stats.print_stats(20)

# Save profile để visualize với snakeviz
profiler = cProfile.Profile()
profiler.run("main()")
profiler.dump_stats("profile_output.prof")
# Sau đó: uv add snakeviz && snakeviz profile_output.prof
```

#### py-spy — Production Profiling (Không cần restart process)

```bash
# Install
uv add py-spy

# Attach vào running process (không cần modify code)
py-spy top --pid 12345

# Tạo flame graph
py-spy record -o profile.svg --pid 12345 --duration 30

# Profile từ đầu
py-spy record -o profile.svg -- python -m uvicorn app.main:app

# Kết quả: SVG flame graph mở trong browser
```

#### memory_profiler — Memory Profiling

```python
# uv add memory-profiler
from memory_profiler import profile, memory_usage

# Decorator để profile từng line
@profile
def memory_heavy_function():
    # Mỗi dòng sẽ hiển thị memory usage
    data = [i for i in range(1_000_000)]  # ~8MB
    processed = {x: x**2 for x in data}   # ~50MB
    return processed

# Profile memory over time
def measure_memory():
    mem_usage = memory_usage(
        (memory_heavy_function, [], {}),
        interval=0.1,  # Đo mỗi 100ms
    )
    print(f"Peak memory: {max(mem_usage):.2f} MiB")
    print(f"Min memory: {min(mem_usage):.2f} MiB")

# tracemalloc — built-in, tìm memory leaks
import tracemalloc

tracemalloc.start()

# Code bạn muốn check
result = create_lots_of_objects()

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")
print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)
```

### 7. Refactoring: Bad Code → Production-Ready

**BEFORE (bad code):**

```python
# ❌ BAD: app_bad.py — nhiều vấn đề
from fastapi import FastAPI
import psycopg2  # Sync driver trong async app!
import json

app = FastAPI()

# Global connection — không thread-safe, không có pool
conn = psycopg2.connect("postgresql://localhost/mydb")

@app.get("/users/{id}")
def get_user(id):  # Không type hints, không async
    cursor = conn.cursor()
    # SQL injection vulnerability!
    cursor.execute(f"SELECT * FROM users WHERE id = {id}")
    user = cursor.fetchone()
    if not user:
        return {"error": "not found"}  # Sai HTTP status code
    # Trả về raw tuple, không có schema
    return {"id": user[0], "email": user[1], "password": user[2]}  # Leak password!

@app.post("/users")
def create_user(data: dict):  # dict là quá rộng, không validate
    cursor = conn.cursor()
    # SQL injection!
    cursor.execute(f"INSERT INTO users VALUES ('{data['email']}', '{data['password']}')")
    conn.commit()
    print(f"Created user: {data}")  # Log sensitive data!
    return {"message": "ok"}
```

**AFTER (production-ready):**

```python
# ✅ GOOD: app_good.py
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_db

logger = structlog.get_logger()
router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr  # Validate email format
    password: str = Field(min_length=8, description="Minimum 8 characters")


class UserResponse(BaseModel):
    """Response schema — KHÔNG include password."""
    model_config = {"from_attributes": True}

    id: str
    email: str
    is_active: bool


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Lấy thông tin user theo ID."""
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return UserResponse.model_validate(user)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Tạo user mới với hashed password."""
    # Check duplicate email
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),  # Hash, không lưu plaintext
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Log không bao gồm sensitive data
    logger.info("user_created", user_id=str(user.id), email=user.email)

    return UserResponse.model_validate(user)
```

**So sánh Before vs After:**

| Vấn đề | Bad Code | Good Code |
|--------|----------|-----------|
| SQL Injection | f-string trong SQL | SQLAlchemy ORM (parameterized) |
| Password leak | Trả về raw password | Response schema exclude password |
| Password storage | Plaintext | bcrypt hash |
| Sensitive logging | Log raw data | Log chỉ metadata |
| HTTP status | Luôn 200 | 404, 409, 201 đúng chuẩn |
| Type safety | Không type hints | Full type hints + Pydantic |
| DB connection | Global sync | Dependency injection async |
| Input validation | Không validate | Pydantic với validators |

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| `from module import *` | Namespace pollution, khó debug | Import explicit: `from module import SpecificClass` |
| Mutable default argument `def f(items=[])` | Shared state giữa các calls | `def f(items=None): items = items or []` |
| Không await coroutine | Không chạy gì cả, trả về coroutine object | Luôn `await` khi gọi `async def` |
| Catch `Exception` quá rộng | Ẩn bugs, khó debug | Catch exception cụ thể |
| `isinstance(x, list)` thay vì Protocol | Coupling chặt | Dùng Protocol cho duck typing |
| `datetime.now()` không có timezone | Bug khi so sánh với timezone-aware | `datetime.now(timezone.utc)` |
| `assert` cho validation | Assert bị disable với `-O` flag | Raise explicit exceptions |
| Không set timeout cho HTTP calls | Hang indefinitely | `httpx.AsyncClient(timeout=30.0)` |

## ✅ Best Practices

- **Luôn dùng `async def` cho FastAPI route handlers** — dù handler không có await, FastAPI xử lý tốt hơn với async
- **`response_model` cho tất cả endpoints** — tự động validate và document response schema
- **Dependency Injection cho DB, Redis, external services** — dễ test, dễ mock
- **Structured logging với `structlog`** — không `print()` trong production code
- **`model_config = ConfigDict(from_attributes=True)`** — cho phép tạo Pydantic model từ ORM objects
- **Pin dependency versions** trong `pyproject.toml` — tránh breaking changes
- **`expire_on_commit=False`** trong SQLAlchemy async sessionmaker — tránh lazy loading errors
- **Validate inputs tại API boundary** — không validate ở tầng business logic

## ⚖️ Trade-offs

### Sync vs Async FastAPI handlers
- **Async**: Tốt cho I/O-bound (DB, Redis, HTTP calls) — **dùng trong 95% cases**
- **Sync**: FastAPI chạy trong threadpool — phù hợp cho CPU-bound tasks, nhưng tốt hơn là dùng `run_in_executor`

### Pydantic strict mode vs permissive
- **Strict**: `model_config = ConfigDict(strict=True)` — `"1"` không coerce thành `1`, an toàn hơn
- **Permissive** (default): Tự động coerce types — tiện nhưng có thể che giấu bugs

### cProfile vs py-spy
- **cProfile**: Đo chính xác, nhưng cần modify code và restart. Dùng cho dev/testing
- **py-spy**: Không cần modify code, attach vào process đang chạy. Dùng cho production debugging

## 🚀 Performance Notes

- **Connection pooling**: `db_pool_size = (CPU_cores * 2) + effective_spindle_count` — PostgreSQL công thức
- **`asyncio.gather` với semaphore** để tránh quá nhiều concurrent requests:
  ```python
  sem = asyncio.Semaphore(10)
  async def limited_task(url):
      async with sem:
          return await fetch(url)
  ```
- **`lru_cache` cho sync functions, `asyncio-lru` cho async functions** — không dùng `lru_cache` với async
- **Pydantic model compilation**: Dùng `model_rebuild()` sau khi define circular references

## 📝 Tóm tắt

- Async đúng cách = không blocking calls + dùng gather cho parallel tasks
- Type hints + Pydantic = catch bugs tại compile time thay vì runtime
- Decorators production patterns: retry, cache, logging — reusable và composable
- Code review checklist: Security, Performance, Type Safety, Error Handling
- Profiling workflow: đo trước (cProfile/py-spy) → identify bottleneck → fix → đo lại
- Refactoring bad → good: SQL injection, password leak, missing types, wrong HTTP status
- Structured logging > print(), Dependency Injection > global state
