# Bài Tập — Ngày 18: OpenAI SDK & LLM Basics

## Bài 1 — Responses Client với History Management (Cơ bản)

**Mô tả:**
Xây dựng một interactive client đơn giản bằng **Responses API** với conversation history và basic analytics. Đây là foundation của mọi chatbot application.

**Yêu cầu:**

Implement class `ChatClient` với các tính năng:

```python
import os
from openai import OpenAI
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tokens_used: int = 0

class ChatClient:
    def __init__(
        self,
        system_prompt: str,
        model: str = "gpt-5",
        max_history_messages: int = 10,
        max_output_tokens: int = 500,
    ):
        # TODO: Implement
        pass

    def chat(self, user_message: str) -> str:
        """
        Gửi message và nhận response.
        - Tự động maintain conversation history
        - Implement sliding window khi history vượt quá max_history_messages
        - Track token usage cho mỗi message
        - Return assistant response string
        - Dùng client.responses.create(..., input=[...], max_output_tokens=...)
        """
        # TODO: Implement
        pass

    def get_stats(self) -> dict:
        """
        Return dict với:
        - total_messages: int
        - total_tokens: int
        - estimated_cost_usd: float
        - conversation_duration_seconds: float
        """
        # TODO: Implement
        pass

    def reset(self):
        """Clear conversation history, giữ nguyên system prompt."""
        # TODO: Implement
        pass

    def export_conversation(self) -> list[dict]:
        """Export conversation dưới dạng list of dicts (JSON-serializable)."""
        # TODO: Implement
        pass
```

**Test cases:**

```python
# Test 1: Basic chat
client = ChatClient(
    system_prompt="Bạn là trợ lý Python, trả lời ngắn gọn bằng tiếng Việt.",
    max_history_messages=6
)

r1 = client.chat("Python list comprehension là gì?")
assert isinstance(r1, str) and len(r1) > 10, "Response phải là string không rỗng"

r2 = client.chat("Cho ví dụ với nested list")
assert isinstance(r2, str), "Response phải là string"

# Test 2: Stats
stats = client.get_stats()
assert stats['total_messages'] == 4, "4 messages: 2 user + 2 assistant"
assert stats['total_tokens'] > 0, "Token count phải > 0"
assert 0 <= stats['estimated_cost_usd'] < 0.05, "Cost snapshot estimate phải reasonable cho 2 short calls"

# Test 3: Sliding window
for i in range(10):
    client.chat(f"Message {i}")
# Sau 10 messages, history phải được trim nhưng chat vẫn hoạt động

# Test 4: Export
history = client.export_conversation()
assert all('role' in m and 'content' in m for m in history), "Mỗi message cần role và content"

print("All tests passed!")
client.stats = client.get_stats()
print(f"Total cost: ${stats['estimated_cost_usd']:.6f}")
```

**Expected output:**
```
All tests passed!
Total cost: $0.000XXX

=== Chat Stats ===
Total messages: 4
Total tokens: XXX
Estimated cost: $0.000XXX
Duration: X.Xs
```

**Hint:**
- `datetime.now()` để track start time trong `__init__`
- Sliding window: `self.history[-self.max_history_messages:]` để lấy N messages gần nhất
- Cost: inject pricing config cập nhật theo pricing page hoặc bỏ cost estimate nếu chưa verify. Không hardcode giá như fact lâu dài.
- `response.output_text` để lấy text; `response.usage.input_tokens`, `response.usage.output_tokens`, `response.usage.total_tokens` để lấy usage.

---

## Bài 2 — Structured Data Extraction Pipeline (Trung bình)

**Mô tả:**
Xây dựng pipeline extract thông tin từ job postings (tin tuyển dụng) và lưu vào structured format. Đây là use case phổ biến trong HR tech, data collection.

**Setup:**

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from openai import OpenAI
import json
import os

client = OpenAI()
MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")

# Sample job postings để test
JOB_POSTINGS = [
    """
    Senior Backend Developer - TechCorp Vietnam
    Địa điểm: Hà Nội (hybrid)
    Mức lương: 2000-3500 USD/tháng

    Yêu cầu:
    - 5+ năm kinh nghiệm với NodeJS hoặc Python
    - Thành thạo PostgreSQL, Redis, Docker
    - Kinh nghiệm với microservices architecture
    - Tiếng Anh đọc hiểu tài liệu kỹ thuật
    - Bonus: Kinh nghiệm với Kafka, Kubernetes

    Phúc lợi: 13th month salary, health insurance, 15 days annual leave
    Apply: hr@techcorp.vn hoặc LinkedIn
    """,

    """
    ML Engineer | AI Startup | Remote

    We're looking for a passionate ML Engineer to join our growing team.
    Requirements:
    - Bachelor's or Master's in CS/Math/Statistics
    - 3+ years with Python, TensorFlow/PyTorch
    - Experience with LLMs, RAG, fine-tuning
    - Strong understanding of NLP fundamentals
    - Salary: competitive, equity included
    - Location: Remote (GMT+7 timezone)
    Contact: careers@aistartup.io
    """,

    """
    Tuyển Fullstack Developer (Junior/Mid)
    Công ty: WebSolutions JSC
    Lương: 15-25 triệu VND

    Mô tả công việc:
    - Phát triển web applications với ReactJS và NestJS
    - Làm việc với MySQL, MongoDB
    - 1-3 năm kinh nghiệm
    - Địa điểm: TP.HCM, quận 1
    - Thời gian: 8h-17h, thứ 2-thứ 6
    Email: tuyendung@websolutions.vn
    """,
]
```

**Yêu cầu:**

1. **Định nghĩa Pydantic schema `JobPosting`** với các fields:
   - `job_title`: str
   - `company_name`: str
   - `location`: str
   - `work_type`: Literal["onsite", "remote", "hybrid", "unknown"]
   - `salary_min_usd`: Optional[float] — convert tất cả về USD (1 USD ≈ 25,000 VND)
   - `salary_max_usd`: Optional[float]
   - `experience_years_min`: Optional[int]
   - `experience_years_max`: Optional[int]
   - `required_skills`: list[str]
   - `nice_to_have_skills`: list[str]
   - `contact_email`: Optional[str]
   - `seniority_level`: Literal["junior", "mid", "senior", "lead", "unknown"]

2. **Implement `extract_job_posting(text: str) -> JobPosting`** dùng structured output với `client.responses.parse(..., text_format=JobPosting)`.

3. **Implement `batch_extract(postings: list[str]) -> list[JobPosting]`** xử lý nhiều postings. Dùng `asyncio.gather()` để parallel processing (không dùng loop tuần tự).

4. **Sau khi extract, tạo summary report:**
   - Số lượng jobs theo seniority level
   - Salary range tổng hợp (min/max/avg)
   - Top 10 skills được yêu cầu nhiều nhất
   - Số jobs remote/hybrid/onsite

5. **Export kết quả ra file JSON** với format:
```json
{
  "extraction_timestamp": "2024-01-01T12:00:00",
  "total_jobs": 3,
  "jobs": [...],
  "summary": {
    "by_seniority": {...},
    "salary_stats": {...},
    "top_skills": [...],
    "by_work_type": {...}
  }
}
```

**Expected output:**
```
Extracting 3 job postings in parallel...
Done in X.Xs

=== JOB EXTRACTION REPORT ===
Total jobs processed: 3

By Seniority:
  senior: 1
  mid: 1
  junior: 1

Salary Stats (USD):
  Min: $XXX
  Max: $XXXX
  Average: $XXXX

Top Skills:
  1. python (X jobs)
  2. nodejs (X jobs)
  3. docker (X jobs)
  ...

Work Type:
  hybrid: X
  remote: X
  onsite: X

Results saved to: job_extraction_results.json
```

**Hint:**
- Trong system prompt, hướng dẫn model convert salary về USD
- Dùng `asyncio.gather()` với `AsyncOpenAI` để parallel extraction
- Với async structured output, dùng `await async_client.responses.parse(..., text_format=JobPosting)` nếu SDK version hỗ trợ; nếu không, chạy sync parse trong worker thread hoặc xử lý tuần tự cho bài tập.
- Collect tất cả skills, dùng `Counter` từ `collections` để count
- `json.dumps(result, ensure_ascii=False, indent=2, default=str)` để export

---

## Bài 3 — Production-Grade LLM Service (Nâng cao / Challenge)

**Mô tả:**
Xây dựng một `LLMService` class production-ready với đầy đủ features: retry logic, rate limiting, cost tracking, caching, và comprehensive error handling. Đây là pattern bạn sẽ dùng trong production AI applications.

**Yêu cầu:**

```python
import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, TypeVar, Type
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, BadRequestError
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

T = TypeVar('T', bound=BaseModel)

@dataclass
class RequestMetrics:
    """Metrics cho một API request."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cached: bool = False
    error: Optional[str] = None

class LLMService:
    """
    Production-grade LLM service với:
    - Async-first design
    - Retry với exponential backoff (chỉ transient errors)
    - In-memory caching (pluggable thành Redis)
    - Rate limiting (max concurrent requests)
    - Cost tracking theo model
    - Structured output support
    - Comprehensive metrics
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gpt-5",
        max_concurrent_requests: int = 10,
        cache_ttl_seconds: int = 3600,  # 1 giờ
        monthly_budget_usd: float = 10.0,
    ):
        # TODO: Initialize AsyncOpenAI client, semaphore, cache dict, metrics list, etc.
        pass

    async def complete(
        self,
        input_items: list[dict],
        model: Optional[str] = None,
        max_output_tokens: int = 500,
        temperature: float = 0.7,
        use_cache: bool = True,  # Cache khi input/model/prompt_version ổn định
    ) -> str:
        """
        Gửi Responses API request với:
        - Cache lookup (nếu input/model/prompt_version ổn định và use_cache=True)
        - Rate limiting via semaphore
        - Retry với exponential backoff
        - Metrics tracking
        - Budget check (warn nếu gần vượt budget)

        Raise nếu: AuthenticationError, monthly budget exceeded
        Return None nếu: max retries exceeded
        """
        # TODO: Implement
        pass

    async def parse(
        self,
        input_items: list[dict],
        response_model: Type[T],
        model: Optional[str] = None,
        max_output_tokens: int = 1000,
    ) -> Optional[T]:
        """
        Structured output parsing với Pydantic bằng client.responses.parse(..., text_format=response_model).
        Return None nếu parsing fail sau retries.
        """
        # TODO: Implement
        pass

    async def batch_complete(
        self,
        requests: list[dict],  # List of {"input_items": [...], "max_output_tokens": ..., ...}
        progress_callback: Optional[callable] = None,
    ) -> list[Optional[str]]:
        """
        Process nhiều requests song song với rate limiting.
        Gọi progress_callback(completed, total) sau mỗi request xong.
        Trả về results theo đúng thứ tự input (kể cả None cho failed requests).
        """
        # TODO: Implement
        pass

    def _cache_key(self, input_items: list[dict], model: str) -> str:
        """Tạo cache key từ input items + model."""
        content = json.dumps({"model": model, "input": input_items}, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def get_metrics_report(self) -> dict:
        """
        Return comprehensive metrics:
        - total_requests, cache_hits, cache_hit_rate
        - total_cost_usd, cost_by_model
        - avg_latency_ms, p95_latency_ms, p99_latency_ms
        - error_rate, errors_by_type
        - requests_per_hour (last 24h)
        """
        # TODO: Implement
        pass

    def is_over_budget(self) -> bool:
        """Check nếu đã vượt monthly budget."""
        # TODO: Implement
        pass
```

**Test suite:**

```python
import asyncio

async def test_llm_service():
    service = LLMService(
        default_model="gpt-5",
        max_concurrent_requests=5,
        monthly_budget_usd=1.0,
    )

    print("Test 1: Basic response...")
    result = await service.complete(
        input_items=[{"role": "user", "content": "Say 'hello' in one word"}],
        temperature=0.0,
        max_output_tokens=10,
    )
    assert result is not None and len(result) > 0
    print(f"  ✓ Response: {result}")

    print("\nTest 2: Cache hit...")
    result2 = await service.complete(
        input_items=[{"role": "user", "content": "Say 'hello' in one word"}],
        temperature=0.0,
        max_output_tokens=10,
    )
    # Lần 2 phải từ cache
    metrics = service.get_metrics_report()
    assert metrics['cache_hits'] == 1, f"Expected 1 cache hit, got {metrics['cache_hits']}"
    print(f"  ✓ Cache hit rate: {metrics['cache_hit_rate']:.0%}")

    print("\nTest 3: Structured output...")
    class SimpleAnswer(BaseModel):
        answer: str
        confidence: float

    parsed = await service.parse(
        input_items=[{"role": "user", "content": "What is 2+2? Give confidence 0-1."}],
        response_model=SimpleAnswer,
        temperature=0.0,
    )
    assert parsed is not None
    assert parsed.answer == "4" or "4" in parsed.answer
    assert 0 <= parsed.confidence <= 1
    print(f"  ✓ Parsed: answer={parsed.answer}, confidence={parsed.confidence}")

    print("\nTest 4: Batch responses...")
    prompts = [f"What is {i}*{i}? Reply with just the number." for i in range(1, 6)]
    requests = [{"input_items": [{"role": "user", "content": p}], "max_output_tokens": 10, "temperature": 0.0}
                for p in prompts]

    completed_count = 0
    def progress(done, total):
        nonlocal completed_count
        completed_count = done
        print(f"  Progress: {done}/{total}", end='\r')

    results = await service.batch_complete(requests, progress_callback=progress)
    print()
    assert len(results) == 5, "Phải có đúng 5 results"
    assert all(r is not None for r in results), "Tất cả requests phải thành công"
    print(f"  ✓ Batch results: {results}")

    print("\n=== Final Metrics Report ===")
    report = service.get_metrics_report()
    print(f"Total requests:   {report['total_requests']}")
    print(f"Cache hits:       {report['cache_hits']} ({report['cache_hit_rate']:.0%})")
    print(f"Total cost:       ${report['total_cost_usd']:.6f}")
    print(f"Avg latency:      {report['avg_latency_ms']:.0f}ms")
    print(f"p95 latency:      {report['p95_latency_ms']:.0f}ms")
    print(f"Error rate:       {report['error_rate']:.0%}")
    print(f"Budget used:      {report['total_cost_usd']/1.0:.1%}")

asyncio.run(test_llm_service())
```

**Expected output:**
```
Test 1: Basic response...
  ✓ Response: hello

Test 2: Cache hit...
  ✓ Cache hit rate: 50%

Test 3: Structured output...
  ✓ Parsed: answer=4, confidence=0.99

Test 4: Batch responses...
  Progress: 5/5
  ✓ Batch results: ['1', '4', '9', '16', '25']

=== Final Metrics Report ===
Total requests:   7
Cache hits:       1 (14%)
Total cost:       $0.000XXX
Avg latency:      XXXms
p95 latency:      XXXms
Error rate:       0%
Budget used:      0.0%
```

**Hint:**
- `asyncio.Semaphore(max_concurrent_requests)` cho rate limiting — dùng `async with semaphore:`
- Cache: `dict` với key = `_cache_key()` và value = `(result, timestamp)`. Check `timestamp + ttl > now` để invalidate
- Metrics: lưu list `RequestMetrics` objects, compute stats khi cần báo cáo
- Retry: wrap `_make_request()` private method với `@retry(...)` tenacity decorator
- `numpy.percentile()` cho p95/p99 latency nếu muốn, hoặc dùng `sorted(latencies)[int(0.95 * len(latencies))]`

---

## 🔍 Gợi ý kiểm tra kết quả

**Kiểm tra API key hoạt động:**
```python
import os
from openai import OpenAI

def check_api_key():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
            input=[{"role": "user", "content": "Say OK"}],
            max_output_tokens=5,
        )
        print(f"✓ API key valid, model: {response.model}")
        print(f"  Response: {response.output_text}")
        return True
    except Exception as e:
        print(f"✗ API key error: {e}")
        return False

check_api_key()
```

**Debug token usage:**
```python
import tiktoken

def debug_tokens(input_items: list[dict], model: str = "gpt-5"):
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")
    for msg in input_items:
        tokens = len(enc.encode(msg['content']))
        print(f"  [{msg['role']}] {tokens} tokens: {msg['content'][:50]}...")
    print("  Context limit: kiểm tra model catalog trước khi chạy batch lớn")

debug_tokens([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Tell me about Python programming."},
])
```

**Estimate cost trước khi chạy batch:**
```python
def estimate_batch_cost(
    prompts: list[str],
    system_prompt: str = "",
    expected_output_tokens: int = 100,
    model: str = "gpt-5"
) -> dict:
    import tiktoken
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")

    sys_tokens = len(enc.encode(system_prompt)) if system_prompt else 0
    total_input_tokens = sum(len(enc.encode(p)) + sys_tokens + 10 for p in prompts)
    total_output_tokens = len(prompts) * expected_output_tokens

    return {
        "num_requests": len(prompts),
        "estimated_input_tokens": total_input_tokens,
        "estimated_output_tokens": total_output_tokens,
        "pricing_note": "Nhân token totals với pricing page hiện hành; không hardcode giá trong bài tập.",
    }

result = estimate_batch_cost(["What is Python?"] * 100, expected_output_tokens=200)
print(f"100 requests estimated cost: ${result['estimated_cost_usd']:.4f} (~{result['estimated_cost_vnd']:.0f} VND)")
```
