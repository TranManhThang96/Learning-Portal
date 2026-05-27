# Bài Tập — Ngày 09: Async Python

## Bài 1 — Concurrent API Calls với Rate Limiting (Cơ bản)

**Mô tả:** Fetch nhiều URLs concurrently với rate limiting.

**Yêu cầu:**
```python
import asyncio
import httpx
from typing import AsyncGenerator

async def fetch_with_semaphore(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Fetch URL, respecting semaphore limit."""
    async with semaphore:  # max N concurrent requests
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return {"url": url, "status": response.status_code, "data": response.json()}
        except Exception as e:
            return {"url": url, "status": -1, "error": str(e)}

async def fetch_all(urls: list[str], max_concurrent: int = 5) -> list[dict]:
    """Fetch all URLs with rate limiting."""
    semaphore = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient() as client:
        tasks = [fetch_with_semaphore(client, url, semaphore) for url in urls]
        return await asyncio.gather(*tasks)
```

**Test với JSONPlaceholder API:**
```python
async def main():
    urls = [
        f"https://jsonplaceholder.typicode.com/posts/{i}"
        for i in range(1, 21)  # 20 posts
    ]
    results = await fetch_all(urls, max_concurrent=5)
    successful = [r for r in results if r["status"] == 200]
    failed = [r for r in results if r["status"] != 200]
    print(f"Successful: {len(successful)}, Failed: {len(failed)}")
```

---

## Bài 2 — Async Job Queue Processor (Trung bình)

**Mô tả:** Multi-worker async job queue.

**Yêu cầu:**
```python
import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable, Any

@dataclass
class Job:
    id: int
    payload: dict
    priority: int = 0

class AsyncJobQueue:
    def __init__(self, num_workers: int = 3) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._num_workers = num_workers
        self._results: dict[int, Any] = {}
        self._running = False

    async def submit(self, job: Job) -> None:
        await self._queue.put((-job.priority, job))

    async def _worker(self, name: str, processor: Callable) -> None:
        while self._running:
            try:
                _, job = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                print(f"[{name}] Processing job {job.id}")
                result = await processor(job)
                self._results[job.id] = result
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue

    async def run(self, processor: Callable, duration: float = 5.0) -> dict:
        self._running = True
        workers = [
            asyncio.create_task(self._worker(f"worker_{i}", processor))
            for i in range(self._num_workers)
        ]
        await asyncio.sleep(duration)
        self._running = False
        await asyncio.gather(*workers, return_exceptions=True)
        return self._results
```

**Test:**
```python
async def process_job(job: Job) -> str:
    await asyncio.sleep(0.2)  # simulate work
    return f"Result for job {job.id}: {job.payload}"

async def main():
    queue = AsyncJobQueue(num_workers=3)
    for i in range(10):
        await queue.submit(Job(id=i, payload={"data": f"item_{i}"}, priority=i % 3))

    results = await queue.run(process_job, duration=3.0)
    print(f"Processed {len(results)} jobs")
```

---

## Bài 3 — Async Web Scraper với Retry và Timeout (Nâng cao)

**Mô tả:** Robust web scraper với retry, timeout, rate limiting.

**Yêu cầu:**
```python
import asyncio
import httpx
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ScraperConfig:
    max_concurrent: int = 5
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_per_second: float = 10.0

@dataclass
class ScrapeResult:
    url: str
    status_code: int
    content: str = ""
    error: str = ""
    attempts: int = 0

class AsyncScraper:
    def __init__(self, config: ScraperConfig = ScraperConfig()) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._rate_limiter = asyncio.Semaphore(int(config.rate_limit_per_second))

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> ScrapeResult:
        for attempt in range(1, self.config.max_retries + 1):
            try:
                async with self._semaphore:
                    async with asyncio.timeout(self.config.timeout):
                        response = await client.get(url)
                        return ScrapeResult(
                            url=url,
                            status_code=response.status_code,
                            content=response.text,
                            attempts=attempt,
                        )
            except (httpx.HTTPError, TimeoutError) as e:
                if attempt == self.config.max_retries:
                    return ScrapeResult(url=url, status_code=-1, error=str(e), attempts=attempt)
                await asyncio.sleep(self.config.retry_delay * (2 ** (attempt - 1)))

        return ScrapeResult(url=url, status_code=-1, error="Max retries exceeded", attempts=self.config.max_retries)

    async def scrape_all(self, urls: list[str]) -> list[ScrapeResult]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tasks = [self._fetch_with_retry(client, url) for url in urls]
            return await asyncio.gather(*tasks)

    async def scrape_stream(self, urls: list[str]):
        """Yield results as they complete (async generator)."""
        async with httpx.AsyncClient() as client:
            tasks = {
                asyncio.create_task(self._fetch_with_retry(client, url)): url
                for url in urls
            }
            pending = set(tasks.keys())
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    yield await task
```

**Test:**
```python
async def main():
    scraper = AsyncScraper(ScraperConfig(max_concurrent=3, max_retries=2))
    urls = [f"https://jsonplaceholder.typicode.com/posts/{i}" for i in range(1, 11)]
    results = await scraper.scrape_all(urls)
    successful = [r for r in results if r.status_code == 200]
    print(f"Scraped {len(successful)}/{len(results)} URLs successfully")

asyncio.run(main())
```

## 🔍 Gợi ý kiểm tra kết quả

```bash
# Test asyncio basic
python -c "
import asyncio

async def test():
    results = await asyncio.gather(
        asyncio.sleep(0.1),
        asyncio.sleep(0.1),
        asyncio.sleep(0.1),
    )
    print('3 concurrent sleeps done')

import time
start = time.perf_counter()
asyncio.run(test())
elapsed = time.perf_counter() - start
assert elapsed < 0.3, f'Should take ~0.1s, took {elapsed:.2f}s'
print(f'Elapsed: {elapsed:.2f}s (expected ~0.1s) ✅')
"

# Install httpx nếu chưa có
uv add httpx
```
