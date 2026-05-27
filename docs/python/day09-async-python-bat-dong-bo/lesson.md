# Ngày 09: Async Python

## 🎯 Mục tiêu học tập

- Hiểu event loop, coroutines, và async/await (so sánh sâu với NodeJS)
- Thành thạo asyncio: tasks, gather, timeout, queue
- Biết khi nào dùng `asyncio.TaskGroup` và cách cleanup khi task bị cancel
- Sử dụng async context managers và async generators
- Dùng httpx cho async HTTP requests
- Biết khi nào cần dùng `run_in_executor()` để gọi blocking code (chi tiết → Ngày 10)

## 🔄 So sánh với NodeJS — PHẦN QUAN TRỌNG NHẤT

| Khái niệm | NodeJS | Python asyncio |
|-----------|--------|----------------|
| Event loop | V8 + libuv, luôn chạy | asyncio.EventLoop, phải start |
| Coroutine | `async function` | `async def` + coroutine object |
| Start event loop | Tự động khi run Node | `asyncio.run(main())` |
| Await | `await promise` | `await coroutine` |
| Promise | `new Promise(resolve, reject)` | `asyncio.Future` |
| Promise.all() | `Promise.all([...])` | `asyncio.gather(...)` |
| Promise.race() | `Promise.race([...])` | `asyncio.wait(return_when=FIRST_COMPLETED)` |
| setTimeout | `setTimeout(fn, ms)` | `asyncio.sleep(seconds)` |
| async generator | `async function*` | `async def` + `yield` |
| Worker threads | `worker_threads` module | `threading` / `multiprocessing` |
| I/O concurrency | Tự động (all I/O async) | Phải `await` explicitly |

**Sự khác biệt quan trọng NHẤT:**
```
NodeJS:
- Single-threaded event loop luôn chạy
- Mọi I/O đều non-blocking by default
- Không có GIL concept
- Code viết sync trông giống blocking nhưng không block (callback-based underneath)

Python:
- Có GIL (Global Interpreter Lock)
- asyncio event loop phải được explicitly started
- Sync code VÀ async code tồn tại song song
- Blocking I/O trong async function = block toàn bộ event loop!
- CPU-bound code không benefit từ asyncio (cần multiprocessing)
```

## 📖 Lý thuyết

### 1. async/await Cơ Bản

```python
import asyncio

# Coroutine — async def trả về coroutine object, KHÔNG execute ngay
async def greet(name: str) -> str:
    await asyncio.sleep(1)  # non-blocking sleep
    return f"Hello, {name}!"

# asyncio.run() — tạo event loop và run main coroutine
async def main() -> None:
    result = await greet("Alice")
    print(result)

asyncio.run(main())  # entry point duy nhất

# Sequential vs Concurrent
async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(1)  # simulate DB query (1 second)
    return {"id": user_id, "name": f"User {user_id}"}

async def sequential() -> None:
    # Sequential: 3 giây tổng
    u1 = await fetch_user(1)  # chờ 1s
    u2 = await fetch_user(2)  # chờ 1s
    u3 = await fetch_user(3)  # chờ 1s
    print(f"Got: {[u1, u2, u3]}")

async def concurrent() -> None:
    # Concurrent: ~1 giây tổng (giống Promise.all)
    u1, u2, u3 = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3),
    )
    print(f"Got: {[u1, u2, u3]}")
```

### 2. asyncio Tasks

```python
import asyncio
from collections.abc import Coroutine
from asyncio import Task
from typing import Any

async def background_job(name: str, n: int) -> list[int]:
    results = []
    for i in range(n):
        await asyncio.sleep(0.1)  # simulate work
        results.append(i)
        print(f"[{name}] processed item {i}")
    return results

async def main() -> None:
    # create_task — bắt đầu chạy NGAY (không cần await)
    task1: Task[list[int]] = asyncio.create_task(
        background_job("worker1", 5),
        name="worker1",
    )
    task2: Task[list[int]] = asyncio.create_task(
        background_job("worker2", 3),
        name="worker2",
    )

    print("Tasks started, doing other work...")
    await asyncio.sleep(0.2)  # other work while tasks run

    # Chờ và lấy kết quả
    results = await asyncio.gather(task1, task2)
    print(f"Results: {results}")

    # Cancel task
    long_task = asyncio.create_task(background_job("long", 100))
    await asyncio.sleep(0.3)
    long_task.cancel()
    try:
        await long_task
    except asyncio.CancelledError:
        print("Task was cancelled")

# Timeout
async def slow_operation() -> str:
    await asyncio.sleep(5)
    return "done"

async def with_timeout() -> None:
    # Python 3.11+ syntax
    try:
        async with asyncio.timeout(2.0):
            result = await slow_operation()
    except TimeoutError:
        print("Operation timed out!")

    # asyncio.wait_for (backward compatible)
    try:
        result = await asyncio.wait_for(slow_operation(), timeout=2.0)
    except asyncio.TimeoutError:
        print("Timed out!")

# gather với error handling
async def may_fail(n: int) -> int:
    if n == 2:
        raise ValueError(f"Task {n} failed!")
    await asyncio.sleep(0.1)
    return n

async def gather_with_errors() -> None:
    # return_exceptions=True: không raise, trả về exceptions như values
    results = await asyncio.gather(
        may_fail(1), may_fail(2), may_fail(3),
        return_exceptions=True,
    )
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Task {i} failed: {result}")
        else:
            print(f"Task {i} succeeded: {result}")

# create_task lifecycle — "fire-and-forget" vẫn phải có owner
_background_tasks: set[asyncio.Task[None]] = set()

def spawn_background(coro: Coroutine[Any, Any, None]) -> None:
    """
    Dùng ở app/service layer khi thật sự cần task nền.
    Giữ reference để task không bị mất dấu và consume exception ở callback.
    """
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    def report_failure(done: asyncio.Task[None]) -> None:
        try:
            done.result()
        except asyncio.CancelledError:
            pass  # shutdown path bình thường
        except Exception as exc:
            print(f"Background task failed: {exc!r}")  # production: logger.exception(...)

    task.add_done_callback(report_failure)

# TaskGroup — Python 3.11+, structured concurrency
async def taskgroup_example() -> None:
    # Nếu một task raise exception, TaskGroup cancel các task còn lại
    # và raise ExceptionGroup khi exit context.
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(may_fail(i)) for i in [1, 3, 4]]

    results = [task.result() for task in tasks]
    print(results)

# Cancellation cleanup — luôn re-raise CancelledError sau cleanup
async def cancellable_worker() -> None:
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("Cleanup before cancellation")
        raise
```

### 3. asyncio Queue

```python
import asyncio
from asyncio import Queue

async def producer(queue: Queue[int], n: int, delay: float = 0.1) -> None:
    for i in range(n):
        await queue.put(i)
        print(f"Produced: {i}")
        await asyncio.sleep(delay)
    # Signal consumers to stop
    for _ in range(3):  # 3 consumers
        await queue.put(-1)  # sentinel

async def consumer(queue: Queue[int], name: str) -> list[int]:
    results = []
    while True:
        item = await queue.get()
        if item == -1:
            queue.task_done()
            break
        print(f"[{name}] Processing: {item}")
        await asyncio.sleep(0.2)  # simulate processing
        results.append(item)
        queue.task_done()
    return results

async def main() -> None:
    queue: Queue[int] = Queue(maxsize=5)  # bounded queue

    producer_task = asyncio.create_task(producer(queue, 10))
    consumer_tasks = [
        asyncio.create_task(consumer(queue, f"consumer_{i}"))
        for i in range(3)
    ]

    await asyncio.gather(producer_task, *consumer_tasks)
```

### 4. Async Context Managers và Generators

```python
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Class-based async context manager
class AsyncDBSession:
    async def __aenter__(self) -> "AsyncDBSession":
        print("Opening DB session")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        print("Closing DB session")
        return False

    async def execute(self, query: str) -> list[dict]:
        await asyncio.sleep(0.1)
        return [{"result": "data"}]

async def main():
    async with AsyncDBSession() as session:
        results = await session.execute("SELECT 1")

# @asynccontextmanager — simpler
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncDBSession, None]:
    session = AsyncDBSession()
    try:
        await session.__aenter__()
        yield session
    finally:
        await session.__aexit__(None, None, None)

# Async generator
async def stream_events(n: int) -> AsyncGenerator[dict, None]:
    for i in range(n):
        await asyncio.sleep(0.1)  # simulate network delay
        yield {"event": f"event_{i}", "data": i}

async def consume_stream() -> None:
    async for event in stream_events(5):
        print(f"Received: {event}")

    # Async comprehension
    events = [event async for event in stream_events(3)]
    print(events)
```

### 5. run_in_executor() — Gọi Blocking Code từ Async

```python
import asyncio
import time

# Vấn đề thường gặp: có blocking sync function cần gọi từ async context
def legacy_sync_call(n: int) -> int:
    """Blocking function từ thư viện cũ — không có async version."""
    time.sleep(0.5)  # simulate blocking I/O
    return n * 2

# WRONG: gọi trực tiếp → block toàn bộ event loop!
async def wrong_way() -> int:
    result = legacy_sync_call(5)  # BUG: blocks event loop!
    return result

# CORRECT: chạy trong thread pool
async def correct_way() -> int:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, legacy_sync_call, 5)
    return result

# asyncio.to_thread() — syntax mới hơn (Python 3.9+), tương đương
async def with_to_thread() -> int:
    result = await asyncio.to_thread(legacy_sync_call, 5)
    return result

# Chạy nhiều blocking calls concurrently
async def main() -> None:
    results = await asyncio.gather(
        asyncio.to_thread(legacy_sync_call, 1),
        asyncio.to_thread(legacy_sync_call, 2),
        asyncio.to_thread(legacy_sync_call, 3),
    )
    print(f"Results: {results}")  # [2, 4, 6] — chạy ~0.5s, không phải 1.5s
```

> **Xem Ngày 10** để hiểu sâu về GIL, threading, multiprocessing, ProcessPoolExecutor,
> và khi nào dùng từng approach cho I/O-bound vs CPU-bound tasks.

### 6. httpx — Async HTTP Client

```python
import asyncio
import httpx

async def fetch_user(client: httpx.AsyncClient, user_id: int) -> dict:
    response = await client.get(f"/users/{user_id}")
    response.raise_for_status()
    return response.json()

async def main() -> None:
    async with httpx.AsyncClient(
        base_url="https://jsonplaceholder.typicode.com",
        timeout=30.0,
        headers={"User-Agent": "MyApp/1.0"},
    ) as client:
        # Single request
        user = await fetch_user(client, 1)
        print(f"User: {user['name']}")

        # Concurrent requests (như Promise.all)
        users = await asyncio.gather(*[
            fetch_user(client, i) for i in range(1, 6)
        ])
        print(f"Fetched {len(users)} users")

        # POST request
        new_post = await client.post(
            "/posts",
            json={"title": "Test", "body": "Content", "userId": 1},
        )
        print(f"Created: {new_post.json()}")

# Streaming download
async def download_file(url: str, output: str) -> None:
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Blocking I/O trong async function | Block toàn bộ event loop | Dùng async library hoặc `run_in_executor` |
| `time.sleep()` trong async | Block event loop | `await asyncio.sleep()` |
| `asyncio.run()` trong async context | RuntimeError: event loop already running | Dùng `await` trực tiếp |
| Coroutine mà không await | Coroutine never executes + RuntimeWarning | Luôn `await` coroutines |
| CPU-bound trong asyncio | Không faster, block event loop | Dùng `ProcessPoolExecutor` |
| `create_task` nhưng không await | Task có thể chạy sau scope kết thúc | Lưu reference, await, hoặc dùng `TaskGroup` |
| Nuốt `CancelledError` | Timeout/shutdown không propagate đúng | Cleanup rồi `raise` lại |

## ✅ Best Practices

- **`asyncio.gather()`** cho concurrent operations (như Promise.all)
- **`asyncio.TaskGroup`** (3.11+) cho nhóm task cùng lifecycle; lỗi ở một task sẽ cancel các task còn lại
- **`asyncio.create_task()`** chỉ dùng cho background tasks có lifecycle rõ ràng (lưu reference, await/cancel khi shutdown)
- **`run_in_executor()`** khi phải gọi blocking sync code từ async context
- **Dùng async libraries**: httpx thay requests, aiofiles thay open(), asyncpg thay psycopg2
- **`asyncio.timeout()`** (3.11+) thay `wait_for()` — cleaner syntax
- **Không mix** sync và async code tùy tiện — design async từ đầu

## ⚖️ Trade-offs

| Approach | Use case | Pros | Cons |
|----------|----------|------|------|
| asyncio | Concurrent I/O | Single thread, low memory | Không giúp CPU-bound |
| asyncio.to_thread() | Blocking sync libs | Wrap dễ dàng, không block event loop | Thread pool overhead |
| threading/multiprocessing | CPU-bound & I/O-bound | True parallelism (process) | Xem chi tiết Ngày 10 |

## 🚀 Performance Notes

- **asyncio có thể handle hàng nghìn concurrent connections** với 1 thread (như Node.js)
- **`asyncio.gather()`** chạy coroutines concurrently, không parallel — vẫn single-threaded
- **GIL released** khi I/O, so threads CAN benefit for I/O-bound (không phải CPU-bound)
- **`ProcessPoolExecutor`** tốn ~50ms overhead per task cho process creation
- **httpx AsyncClient** nên được reused (connection pooling) thay vì tạo mới mỗi request

## 📝 Tóm tắt

- `async def` tạo coroutine — phải `await` mới execute
- `asyncio.run(main())` là entry point — tạo event loop
- `await asyncio.gather(a, b, c)` = `Promise.all([a, b, c])` trong JS
- `asyncio.TaskGroup` = structured concurrency cho nhóm tasks cùng lifecycle
- `asyncio.create_task()` = background task, nhưng phải được quản lý/await/cancel rõ ràng
- Blocking I/O trong async function = CRIME — block toàn bộ event loop
- `asyncio.to_thread()` / `run_in_executor()` để gọi blocking sync code từ async context
- httpx AsyncClient cho HTTP requests, reuse với `async with`
- **Ngày 10**: GIL deep dive, threading, multiprocessing, ProcessPoolExecutor
