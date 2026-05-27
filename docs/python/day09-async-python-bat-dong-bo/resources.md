# Tài Liệu Tham Khảo — Ngày 09: Async Python

## 📚 Official Docs

- **asyncio** — https://docs.python.org/3/library/asyncio.html — Event loop, tasks, primitives
- **asyncio tasks** — https://docs.python.org/3/library/asyncio-task.html — create_task, gather, wait
- **asyncio queues** — https://docs.python.org/3/library/asyncio-queue.html — Queue, PriorityQueue
- **asyncio.timeout** — https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout — Python 3.11+
- **httpx** — https://www.python-httpx.org/ — Async HTTP client docs

## 🎥 Video / Courses

- **"Python asyncio Deep Dive"** - mCoding (YouTube) — Internals, event loop explained
- **"Asyncio vs Threading vs Multiprocessing"** - Arjan Codes (YouTube) — When to use what
- **"Python Concurrency"** - Real Python (YouTube) — Practical comparison

## 📝 Articles / Blog Posts

- **"Async IO in Python: A Complete Walkthrough"** — realpython.com — Comprehensive guide
- **"Python Threading vs asyncio"** — realpython.com — GIL explained
- **"Python's GIL"** — dabeaz.com — Deep dive into GIL

## 🔧 Tools / Libraries

- **httpx** — python-httpx.org — Async + sync HTTP client (thay thế requests)
- **aiofiles** — github.com/Tinche/aiofiles — Async file I/O
- **aioboto3** — github.com/terricain/aioboto3 — Async AWS SDK
- **aioredis** — redis.readthedocs.io — Async Redis client (included in redis-py 4.2+)
- **asyncpg** — github.com/MagicStack/asyncpg — Fastest async PostgreSQL driver

## 💡 Ghi chú thêm

- **`asyncio.TaskGroup`** (Python 3.11+): structured concurrency, thay thế `gather()` với better error handling
  ```python
  async with asyncio.TaskGroup() as tg:
      t1 = tg.create_task(coro1())
      t2 = tg.create_task(coro2())
  ```
- **Cancellation**: nếu catch `asyncio.CancelledError` để cleanup, hãy `raise` lại; nuốt cancellation có thể làm timeout/shutdown behave sai
- **`asyncio.Semaphore`**: rate limiting — giới hạn số concurrent operations
- **`asyncio.Event`**: giống EventEmitter NodeJS cho một-lần signal
- **`asyncio.Lock`**: mutual exclusion cho shared async state
- **Uvloop**: drop-in replacement cho asyncio event loop, nhanh hơn 2-4x (dùng libuv như NodeJS)
  ```bash
  uv add uvloop
  ```
  ```python
  import uvloop
  asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
  ```
- **`trio`** và **`anyio`**: alternative async frameworks với better structured concurrency
