# Ngày 10: Concurrency & Parallelism trong Python

## 🎯 Mục tiêu học tập

- Hiểu sâu về GIL (Global Interpreter Lock) — tại sao tồn tại và ảnh hưởng thực tế
- Phân biệt rõ threading vs multiprocessing vs asyncio — khi nào dùng cái nào
- Thành thạo `concurrent.futures` (ThreadPoolExecutor, ProcessPoolExecutor)
- Kết hợp asyncio + multiprocessing cho CPU-bound + I/O-bound tasks
- Dùng `asyncio.to_thread()` để chạy blocking code trong async context

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS | Python |
|-----------|--------|--------|
| GIL | Không có (V8 single-threaded) | Có — giới hạn CPU parallelism trong 1 process |
| True CPU parallelism | Worker Threads / `child_process` | `multiprocessing` / `ProcessPoolExecutor` |
| Thread pool | `worker_threads` + libuv thread pool | `ThreadPoolExecutor` |
| Process pool | `child_process.fork()` | `ProcessPoolExecutor` |
| Run blocking in async | `setImmediate`, `worker_threads` | `asyncio.to_thread()`, `run_in_executor()` |
| Shared memory | `SharedArrayBuffer` | `multiprocessing.shared_memory`, `Value`, `Array` |
| IPC | `postMessage()` | `Queue`, `Pipe`, `Manager` |
| CPU cores | Node cluster module | `multiprocessing` — mỗi process = 1 GIL riêng |

**Điểm khác biệt cốt lõi:**
```
NodeJS:
- Single-threaded event loop cho JavaScript chính; libuv thread pool xử lý một số blocking I/O/native work
- Worker Threads chạy CPU-bound JavaScript song song thật nhưng dùng V8 isolate riêng
- Không có GIL concept — mỗi V8 instance độc lập
- CPU-bound: Worker Threads hoặc child processes, đổi lại phải quản lý message passing/lifecycle

Python:
- GIL = chỉ 1 thread Python chạy bytecode tại 1 thời điểm
- Threading OK cho I/O (GIL released khi wait I/O)
- Multiprocessing = nhiều process, mỗi process có GIL riêng → true CPU parallelism
- asyncio = cooperative multitasking, single thread, best cho concurrent I/O
```

## 📖 Lý thuyết

### 1. GIL (Global Interpreter Lock) Deep Dive

**WHY — Tại sao GIL tồn tại?**

CPython (Python reference implementation) quản lý memory bằng **reference counting**:

```python
import sys

# Mỗi object có reference count
x = [1, 2, 3]
print(sys.getrefcount(x))  # 2 (x + argument của getrefcount)

y = x  # tăng refcount
print(sys.getrefcount(x))  # 3

del y  # giảm refcount
# Khi refcount = 0 → garbage collected
```

Nếu nhiều threads đồng thời modify refcount của cùng 1 object → **race condition** → memory corruption. GIL là giải pháp đơn giản: chỉ 1 thread được chạy Python bytecode tại 1 thời điểm.

**GIL ảnh hưởng thực tế:**

```python
import threading
import time

# CPU-bound task — BỊ GIL LIMIT
def count(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
    return total

# Test: 1 thread vs 2 threads — CPU-bound
N = 50_000_000

# Sequential: ~2.5s
start = time.perf_counter()
count(N)
count(N)
elapsed_seq = time.perf_counter() - start

# 2 threads: ~2.5s (KHÔNG nhanh hơn vì GIL!)
start = time.perf_counter()
t1 = threading.Thread(target=count, args=(N,))
t2 = threading.Thread(target=count, args=(N,))
t1.start(); t2.start()
t1.join(); t2.join()
elapsed_thread = time.perf_counter() - start

print(f"Sequential: {elapsed_seq:.2f}s")
print(f"2 Threads:  {elapsed_thread:.2f}s")
# Kết quả: cả hai ~2.5s — threading KHÔNG giúp ích cho CPU-bound!
# Đôi khi 2 threads còn chậm hơn vì GIL switching overhead!
```

**GIL được RELEASE trong trường hợp nào:**

```python
import threading
import time
import urllib.request

# I/O operations RELEASE GIL — threading CÓ hiệu quả!
def fetch(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as response:
        # GIL released trong khi chờ I/O
        return len(response.read())

urls = ["https://example.com"] * 5

# Sequential: ~5 * 1s = 5s
# Threading: ~1s (vì GIL released khi I/O, các threads thực sự chạy song song)
threads = [threading.Thread(target=fetch, args=(url,)) for url in urls]
for t in threads: t.start()
for t in threads: t.join()

# GIL cũng released khi:
# - Một số C extension functions (numpy, scipy) khi chạy native code
# - time.sleep()
# - File I/O
# - Network I/O
# - Các C-level blocking calls
```

**Khi nào GIL KHÔNG phải vấn đề:**
- I/O-bound code (threading vẫn hiệu quả)
- Numpy/Scipy/PyTorch: nhiều operations chạy ở C/native backend và release GIL, nhưng không phải mọi operation
- asyncio (single-threaded, không cần GIL release)

### 2. Threading

```python
import threading
import time
import queue
from typing import Callable

# Thread cơ bản
def worker(name: str, delay: float) -> None:
    print(f"[{name}] Started")
    time.sleep(delay)  # simulate I/O — GIL released
    print(f"[{name}] Done after {delay}s")

# Tạo và chạy threads
threads = [
    threading.Thread(target=worker, args=(f"thread-{i}", 1.0), daemon=True)
    for i in range(5)
]
start = time.perf_counter()
for t in threads: t.start()
for t in threads: t.join()
print(f"Total: {time.perf_counter() - start:.2f}s")  # ~1s, không phải 5s

# Thread với return value — dùng queue
def fetch_data(result_queue: queue.Queue, url: str) -> None:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            result_queue.put({"url": url, "size": len(r.read()), "error": None})
    except Exception as e:
        result_queue.put({"url": url, "size": 0, "error": str(e)})

result_queue: queue.Queue = queue.Queue()
urls = ["https://httpbin.org/get", "https://httpbin.org/ip"]
threads = [threading.Thread(target=fetch_data, args=(result_queue, url)) for url in urls]
for t in threads: t.start()
for t in threads: t.join()

results = []
while not result_queue.empty():
    results.append(result_queue.get())
print(results)

# Thread-safe operations với Lock
class ThreadSafeCounter:
    def __init__(self) -> None:
        self._count = 0
        self._lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:  # acquire lock — giống mutex trong C
            self._count += 1

    @property
    def value(self) -> int:
        with self._lock:
            return self._count

counter = ThreadSafeCounter()
threads = [threading.Thread(target=lambda: [counter.increment() for _ in range(10_000)]) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
print(counter.value)  # Luôn là 100_000 (thread-safe)
```

### 3. concurrent.futures — Interface Thống Nhất

```python
import concurrent.futures
import time
import math
from typing import Callable

# ThreadPoolExecutor — I/O-bound tasks
def io_task(n: int) -> str:
    time.sleep(0.5)  # simulate network/DB
    return f"I/O result {n}"

# ProcessPoolExecutor — CPU-bound tasks
def cpu_task(n: int) -> int:
    """Tính số nguyên tố — CPU intensive."""
    return sum(1 for i in range(2, n) if all(n % j != 0 for j in range(2, int(math.sqrt(n)) + 1)))

# ThreadPoolExecutor — giống BullMQ workers cho I/O tasks
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    # map: giống Promise.all(items.map(fn))
    results = list(executor.map(io_task, range(8)))
    print(f"ThreadPool results: {len(results)} items")

    # submit: fine-grained control, trả về Future
    futures = [executor.submit(io_task, i) for i in range(8)]
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        print(f"Completed: {result}")

# ProcessPoolExecutor — true CPU parallelism
# Lưu ý: function phải pickle-able (không dùng lambda, nested function)
# Lưu ý portability: tạo ProcessPool trong if __name__ == "__main__"
# để chạy đúng trên Windows/macOS hoặc khi start method là "spawn".
def is_prime(n: int) -> bool:
    if n < 2: return False
    return all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1))

def run_process_pool_demo() -> None:
    numbers = list(range(10_000, 10_100))

    start = time.perf_counter()
    # Sequential
    sequential_primes = [n for n in numbers if is_prime(n)]
    print(f"Sequential: {time.perf_counter() - start:.3f}s, found {len(sequential_primes)} primes")

    start = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(is_prime, numbers))
    parallel_primes = [n for n, is_p in zip(numbers, results) if is_p]
    print(f"Parallel:   {time.perf_counter() - start:.3f}s, found {len(parallel_primes)} primes")

if __name__ == "__main__":
    run_process_pool_demo()

# as_completed — process kết quả khi ready (không chờ tất cả)
def slow_task(n: int) -> dict:
    time.sleep(n * 0.1)  # task 3 mất 0.3s, task 1 mất 0.1s
    return {"n": n, "result": n ** 2}

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    future_to_n = {executor.submit(slow_task, n): n for n in [3, 1, 4, 1, 5]}

    for future in concurrent.futures.as_completed(future_to_n):
        n = future_to_n[future]
        try:
            result = future.result()
            print(f"Task {n} done: {result}")  # In theo thứ tự hoàn thành
        except Exception as e:
            print(f"Task {n} failed: {e}")
```

### 4. asyncio.to_thread() — Chạy Blocking Code trong Async

```python
import asyncio
import time
import concurrent.futures

# Vấn đề: blocking function trong async context
def slow_sync_function(n: int) -> int:
    """Blocking — không thể await, không thể dùng trong asyncio."""
    time.sleep(1)  # Block toàn bộ event loop nếu gọi trực tiếp!
    return n * 2

# Giải pháp 1: asyncio.to_thread() (Python 3.9+) — đơn giản nhất
async def main_with_to_thread() -> None:
    start = time.perf_counter()

    # Chạy 3 blocking calls concurrently mà không block event loop
    results = await asyncio.gather(
        asyncio.to_thread(slow_sync_function, 1),
        asyncio.to_thread(slow_sync_function, 2),
        asyncio.to_thread(slow_sync_function, 3),
    )
    print(f"Results: {results}")  # [2, 4, 6]
    print(f"Time: {time.perf_counter() - start:.2f}s")  # ~1s, không phải 3s

asyncio.run(main_with_to_thread())

# Giải pháp 2: run_in_executor() (compatible với Python < 3.9)
async def main_with_executor() -> None:
    loop = asyncio.get_event_loop()

    # Dùng default thread pool
    result = await loop.run_in_executor(None, slow_sync_function, 1)

    # Dùng custom thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = await asyncio.gather(
            loop.run_in_executor(pool, slow_sync_function, 1),
            loop.run_in_executor(pool, slow_sync_function, 2),
        )
    print(results)

# Real-world: gọi blocking library từ async FastAPI endpoint
import requests  # blocking library

async def fetch_external_api(url: str) -> dict:
    """Gọi requests (blocking) từ async context."""
    # WRONG: response = requests.get(url)  # Block event loop!
    # CORRECT:
    response = await asyncio.to_thread(requests.get, url)
    return response.json()
```

### 5. asyncio + multiprocessing — CPU + I/O Hybrid

```python
import asyncio
import concurrent.futures
import time
import math

def cpu_intensive(n: int) -> int:
    """CPU-bound: tính tổng các số nguyên tố < n."""
    return sum(i for i in range(2, n) if all(i % j != 0 for j in range(2, int(math.sqrt(i)) + 1)))

async def process_with_multiprocessing(numbers: list[int]) -> list[int]:
    """Combine asyncio event loop với process pool cho CPU work."""
    loop = asyncio.get_event_loop()

    with concurrent.futures.ProcessPoolExecutor() as process_pool:
        # Chạy CPU tasks trong process pool, không block event loop
        futures = [
            loop.run_in_executor(process_pool, cpu_intensive, n)
            for n in numbers
        ]
        results = await asyncio.gather(*futures)
    return list(results)

async def main() -> None:
    numbers = [10_000, 20_000, 30_000, 40_000]

    start = time.perf_counter()
    results = await process_with_multiprocessing(numbers)
    print(f"Results: {results}")
    print(f"Time with ProcessPool: {time.perf_counter() - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

**Multiprocessing caveats quan trọng:**

- Trên Windows/macOS và mọi môi trường dùng start method `"spawn"`, child process import lại main module. Vì vậy mọi code tạo `Process`, `Pool`, hoặc `ProcessPoolExecutor` phải nằm sau `if __name__ == "__main__":`.
- Function chạy trong process phải ở module level và pickle-able; tránh lambda, nested function, open DB connection, file handle, logger context làm argument.
- Tạo process pool có overhead lớn. Với web service, tạo pool ở app lifecycle/startup và shutdown rõ ràng; không tạo pool mới cho từng request.
- Linux default `"fork"` đôi khi che lỗi thiếu guard, nhưng vẫn nên viết portable như trên.

### 6. Decision Matrix — Khi Nào Dùng Gì

```python
"""
Decision matrix — giống như chọn giữa Redis queue, Worker Threads, cluster trong Node.js

┌─────────────────────────────────────────────────────────────────────┐
│                    PYTHON CONCURRENCY DECISION TREE                  │
├─────────────────────┬───────────────────────────────────────────────┤
│ Task type           │ Recommended approach                          │
├─────────────────────┼───────────────────────────────────────────────┤
│ Concurrent I/O      │ asyncio + await                               │
│ (network, DB, files)│ → 1000s of concurrent I/O ops, single thread  │
├─────────────────────┼───────────────────────────────────────────────┤
│ Blocking I/O        │ asyncio.to_thread() / ThreadPoolExecutor      │
│ (legacy sync libs)  │ → Wrap blocking call, don't block event loop  │
├─────────────────────┼───────────────────────────────────────────────┤
│ CPU-bound           │ ProcessPoolExecutor / multiprocessing         │
│ (compute, ML, math) │ → Each process has own GIL, true parallelism  │
├─────────────────────┼───────────────────────────────────────────────┤
│ Mixed: async API +  │ asyncio + run_in_executor(ProcessPoolExecutor)│
│ CPU-bound backend   │ → Best of both worlds                         │
├─────────────────────┼───────────────────────────────────────────────┤
│ Simple parallel I/O │ ThreadPoolExecutor (simpler than asyncio)     │
│ (script, batch job) │ → Good when async refactor is too expensive   │
├─────────────────────┼───────────────────────────────────────────────┤
│ Sequential script   │ Sync code                                     │
│ (no concurrency)    │ → Don't over-engineer                         │
└─────────────────────┴───────────────────────────────────────────────┘
"""

# Ví dụ thực tế: AI service xử lý requests
# - Nhận nhiều HTTP requests đồng thời → asyncio (FastAPI)
# - Mỗi request cần call OpenAI API → await httpx (I/O-bound)
# - Một số requests cần tokenize text (CPU) → run_in_executor(ProcessPool)
# - Background jobs (email, cleanup) → asyncio.to_thread hoặc Celery

# Numpy/PyTorch: nhiều phép toán native release GIL, nhưng đo benchmark theo operation/backend cụ thể.
import numpy as np

def numpy_task(size: int) -> float:
    """Nhiều numpy operations run at C level — thường release GIL."""
    arr = np.random.random(size)
    return float(np.sum(arr))  # GIL released trong numpy ops

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(numpy_task, [1_000_000] * 4))
    # Thực sự chạy song song vì numpy releases GIL
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix |
|---------|---------|---------|
| Threading cho CPU-bound Python code | Không nhanh hơn (GIL), có thể chậm hơn | Dùng ProcessPoolExecutor |
| Gọi blocking sync code trong async | Block toàn bộ event loop | `asyncio.to_thread()` hoặc `run_in_executor()` |
| Lambda/nested function trong ProcessPool | PicklingError | Dùng module-level functions |
| Quá nhiều processes | High memory, context switch overhead | max_workers = cpu_count() |
| Shared mutable state giữa threads | Race conditions, data corruption | Lock, Queue, hoặc dùng asyncio thay |
| Tạo ProcessPool ở top-level module | RuntimeError/fork bomb trên spawn platforms | Tạo pool trong `if __name__ == "__main__"` hoặc app lifecycle |
| Truyền object không pickle-able vào ProcessPool | PicklingError hoặc hang khó debug | Truyền data đơn giản; mở resource trong child nếu cần |

## ✅ Best Practices

- **asyncio** cho concurrent I/O trong web services (FastAPI, aiohttp)
- **ThreadPoolExecutor** cho blocking legacy libraries (boto3, requests, psycopg2 sync)
- **ProcessPoolExecutor** cho CPU-bound: image processing, ML inference, data transformation
- **Numpy/PyTorch**: benchmark theo operation/backend; nhiều native ops release GIL nhưng không phải tất cả
- **`asyncio.to_thread()`** là cách đơn giản nhất để wrap blocking call
- **`if __name__ == "__main__"`**: bắt buộc cho multiprocessing portable, nhất là Windows/macOS/spawn
- **Giới hạn số workers**: cpu_count() cho CPU-bound, 2-4x cpu_count() cho I/O-bound

## ⚖️ Trade-offs

| Approach | Memory | Startup | Communication | Use case |
|----------|--------|---------|---------------|---------|
| asyncio | Thấp nhất | Instant | Shared memory | Concurrent I/O |
| threading | Thấp | Fast | Shared memory (cần Lock) | I/O với blocking libs |
| multiprocessing | Cao (mỗi process fork) | Slow (~50ms) | IPC (pickle overhead) | CPU-bound tasks |
| concurrent.futures | Depends | - | Unified API trên cả hai | Scripting, batch |

## 🚀 Performance Notes

- **Thread switching** xảy ra sau ~100 bytecodes (GIL sys.getswitchinterval = 0.005s)
- **Process pool overhead**: ~50-100ms để fork process — không phù hợp với tasks < 50ms
- **asyncio** có thể handle 10,000+ concurrent I/O connections với 1 thread
- **Numpy với threading**: hiệu quả vì GIL released trong C code
- **`multiprocessing.Pool.map()`** vs `ProcessPoolExecutor.map()`: tương đương, prefer `concurrent.futures` vì API đẹp hơn

## 📝 Tóm tắt

- **GIL**: chỉ 1 Python thread chạy tại 1 thời điểm → threading không giúp CPU-bound
- **GIL released**: khi I/O, khi gọi C extensions (numpy, requests) → threading OK cho I/O
- **asyncio**: tốt nhất cho concurrent I/O, single-threaded, không cần worry về GIL
- **ThreadPoolExecutor**: wrap blocking sync code để dùng từ async context
- **ProcessPoolExecutor**: true CPU parallelism — mỗi process có GIL riêng
- **asyncio.to_thread()**: cách đơn giản nhất để run sync blocking code
- **Rule**: I/O → asyncio, CPU → multiprocessing, blocking libs → to_thread/run_in_executor
