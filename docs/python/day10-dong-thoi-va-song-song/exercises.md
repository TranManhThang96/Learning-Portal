# Bài Tập — Ngày 10: Concurrency & Parallelism

## Bài 1 — Thread-Safe Download Manager (Cơ bản)

**Mô tả:** Xây dựng download manager dùng ThreadPoolExecutor, xử lý concurrent downloads với progress tracking.

**Yêu cầu:**
```python
import concurrent.futures
import time
import threading
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class DownloadTask:
    url: str
    filename: str
    size_bytes: int = 0
    downloaded_bytes: int = 0
    status: str = "pending"  # pending, downloading, done, failed
    error: str = ""

class DownloadManager:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, DownloadTask] = {}
        self._lock = threading.Lock()

    def add_task(self, url: str, filename: str) -> str:
        """Thêm download task, trả về task_id."""
        ...

    def _download(self, task_id: str) -> None:
        """Thực hiện download (simulate bằng time.sleep)."""
        import random
        import time

        with self._lock:
            task = self._tasks[task_id]
            task.status = "downloading"
            task.size_bytes = random.randint(100_000, 5_000_000)

        # Simulate download với progress
        chunk_size = task.size_bytes // 10
        for i in range(10):
            time.sleep(0.1)  # simulate network I/O
            with self._lock:
                self._tasks[task_id].downloaded_bytes += chunk_size

        with self._lock:
            self._tasks[task_id].status = "done"

    def download_all(self, progress_callback: Callable | None = None) -> dict[str, DownloadTask]:
        """Submit tất cả tasks và chờ hoàn thành."""
        ...

    def get_progress(self) -> dict[str, float]:
        """Trả về dict: task_id → progress (0.0 - 1.0)."""
        ...
```

**Test:**
```python
manager = DownloadManager(max_workers=3)
urls = [
    ("https://example.com/file1.zip", "file1.zip"),
    ("https://example.com/file2.zip", "file2.zip"),
    ("https://example.com/file3.zip", "file3.zip"),
    ("https://example.com/file4.zip", "file4.zip"),
    ("https://example.com/file5.zip", "file5.zip"),
]
for url, name in urls:
    manager.add_task(url, name)

import time
start = time.perf_counter()
results = manager.download_all()
elapsed = time.perf_counter() - start

done = [t for t in results.values() if t.status == "done"]
print(f"Downloaded {len(done)}/{len(results)} files in {elapsed:.2f}s")
# Với 5 tasks, 4 workers, 1s per task → ~2s total (không phải 5s)
assert elapsed < 3.0, f"Expected < 3s, got {elapsed:.2f}s"
assert len(done) == 5, "All downloads should succeed"
```

---

## Bài 2 — CPU-Bound Image Processor với ProcessPool (Trung bình)

**Mô tả:** Simulate image processing pipeline dùng ProcessPoolExecutor — convert, resize, apply filters.

**Lưu ý bắt buộc:** mọi code tạo `ProcessPoolExecutor` phải chạy dưới `if __name__ == "__main__":` trong script thật; function chạy trong pool phải là module-level function để pickle được.

**Yêu cầu:**
```python
import concurrent.futures
import time
import math
from dataclasses import dataclass
from typing import Callable

@dataclass
class ImageTask:
    image_id: int
    width: int
    height: int
    data: list[int]  # simulate pixel data

def simulate_grayscale(task: ImageTask) -> ImageTask:
    """CPU-intensive: convert to grayscale (simulate với math)."""
    # Simulate pixel processing
    new_data = [
        int(0.299 * p + 0.587 * p + 0.114 * p)
        for p in task.data
    ]
    return ImageTask(task.image_id, task.width, task.height, new_data)

def simulate_blur(task: ImageTask) -> ImageTask:
    """CPU-intensive: apply blur filter."""
    # Simulate convolution
    result = []
    for i, pixel in enumerate(task.data):
        neighbors = task.data[max(0, i-1):i+2]
        result.append(int(sum(neighbors) / len(neighbors)))
    return ImageTask(task.image_id, task.width, task.height, result)

def process_image_pipeline(task: ImageTask) -> dict:
    """
    Full processing pipeline: grayscale → blur
    Phải là module-level function để pickle được.
    """
    result = simulate_grayscale(task)
    result = simulate_blur(result)
    return {
        "image_id": result.image_id,
        "processed_pixels": len(result.data),
        "checksum": sum(result.data),
    }

# Benchmark: Sequential vs ProcessPool
def run_benchmark(images: list[ImageTask]) -> None:
    # Sequential
    start = time.perf_counter()
    seq_results = [process_image_pipeline(img) for img in images]
    seq_time = time.perf_counter() - start

    # ProcessPoolExecutor
    start = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor() as executor:
        pool_results = list(executor.map(process_image_pipeline, images))
    pool_time = time.perf_counter() - start

    print(f"Sequential:  {seq_time:.3f}s")
    print(f"ProcessPool: {pool_time:.3f}s")
    print(f"Speedup:     {seq_time / pool_time:.1f}x")
    assert len(seq_results) == len(pool_results), "Same number of results"
```

**Test:**
```python
if __name__ == "__main__":
    import random
    images = [
        ImageTask(
            image_id=i,
            width=200,
            height=200,
            data=[random.randint(0, 255) for _ in range(200 * 200)],
        )
        for i in range(8)
    ]
    run_benchmark(images)
```

**Expected output:**
```
Sequential:  2.4s (approximate)
ProcessPool: 0.8s (approximate)
Speedup:     3.0x (depends on CPU cores)
```

---

## Bài 3 — Async + Multiprocessing Hybrid Service (Nâng cao)

**Mô tả:** Xây dựng service xử lý requests với asyncio cho I/O và ProcessPool cho CPU-bound tasks — pattern thực tế trong AI services.

**Lưu ý:** `HybridRequestProcessor` tạo `ProcessPoolExecutor`, nên demo script phải giữ `asyncio.run(main())` dưới `if __name__ == "__main__":`; trong app server thật, tạo pool ở startup/lifespan và shutdown trong cleanup.

**Yêu cầu:**

```python
import asyncio
import concurrent.futures
import time
import math
from dataclasses import dataclass
from typing import Any

@dataclass
class Request:
    request_id: str
    payload: dict
    request_type: str  # "io_task" | "cpu_task"

@dataclass
class Response:
    request_id: str
    result: Any
    processing_time: float
    worker_type: str  # "async", "thread", "process"

# CPU-bound function — phải ở module level để pickle
def heavy_computation(data: dict) -> dict:
    """Simulate ML inference hoặc data transformation (CPU-bound)."""
    n = data.get("n", 10_000)
    # Simulate expensive computation
    result = sum(
        math.sqrt(i) * math.log(i + 1)
        for i in range(1, n)
    )
    return {"computation_result": result, "input_n": n}

class HybridRequestProcessor:
    """
    Service xử lý mixed workload:
    - I/O tasks (DB queries, API calls): asyncio
    - CPU tasks (ML inference, data processing): ProcessPool
    - Blocking legacy calls: ThreadPool
    """
    def __init__(self, max_processes: int = 4, max_threads: int = 10) -> None:
        self._process_pool = concurrent.futures.ProcessPoolExecutor(max_workers=max_processes)
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_threads)
        self._processed_count = 0
        self._lock = asyncio.Lock()

    async def handle_io_task(self, request: Request) -> Response:
        """Async I/O task — simulate DB query hoặc external API call."""
        start = time.perf_counter()
        delay = request.payload.get("delay", 0.1)
        await asyncio.sleep(delay)  # Non-blocking I/O
        result = {"data": f"fetched_{request.request_id}", "delay": delay}
        return Response(
            request_id=request.request_id,
            result=result,
            processing_time=time.perf_counter() - start,
            worker_type="async",
        )

    async def handle_cpu_task(self, request: Request) -> Response:
        """CPU-bound task — chạy trong process pool."""
        start = time.perf_counter()
        loop = asyncio.get_event_loop()
        # Chạy CPU task trong process pool, KHÔNG block event loop
        result = await loop.run_in_executor(
            self._process_pool,
            heavy_computation,
            request.payload,
        )
        return Response(
            request_id=request.request_id,
            result=result,
            processing_time=time.perf_counter() - start,
            worker_type="process",
        )

    async def process_batch(self, requests: list[Request]) -> list[Response]:
        """Xử lý batch requests concurrently."""
        tasks = []
        for req in requests:
            if req.request_type == "io_task":
                tasks.append(self.handle_io_task(req))
            elif req.request_type == "cpu_task":
                tasks.append(self.handle_cpu_task(req))

        responses = await asyncio.gather(*tasks)

        async with self._lock:
            self._processed_count += len(responses)

        return list(responses)

    def shutdown(self) -> None:
        self._process_pool.shutdown(wait=True)
        self._thread_pool.shutdown(wait=True)

async def main() -> None:
    processor = HybridRequestProcessor(max_processes=4, max_threads=8)

    # Tạo batch: mix I/O và CPU tasks
    requests = []
    for i in range(10):
        req_type = "cpu_task" if i % 3 == 0 else "io_task"
        requests.append(Request(
            request_id=f"req-{i:03d}",
            payload={"n": 50_000, "delay": 0.1},
            request_type=req_type,
        ))

    print(f"Processing {len(requests)} requests...")
    print(f"  CPU tasks: {sum(1 for r in requests if r.request_type == 'cpu_task')}")
    print(f"  I/O tasks: {sum(1 for r in requests if r.request_type == 'io_task')}")

    start = time.perf_counter()
    responses = await processor.process_batch(requests)
    total_time = time.perf_counter() - start

    cpu_responses = [r for r in responses if r.worker_type == "process"]
    io_responses = [r for r in responses if r.worker_type == "async"]

    print(f"\nCompleted in {total_time:.2f}s")
    print(f"CPU tasks avg time: {sum(r.processing_time for r in cpu_responses) / len(cpu_responses):.3f}s")
    print(f"I/O tasks avg time: {sum(r.processing_time for r in io_responses) / len(io_responses):.3f}s")

    processor.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**Expected output:**
```
Processing 10 requests...
  CPU tasks: 4
  I/O tasks: 6

Completed in ~0.3s  # CPU và I/O chạy song song
CPU tasks avg time: ~0.15s
I/O tasks avg time: ~0.10s
```

**Bonus:** Thêm rate limiting, retry logic cho CPU tasks bị timeout, metrics collection.
