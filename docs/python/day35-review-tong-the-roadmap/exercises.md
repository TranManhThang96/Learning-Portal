# Bài Tập — Ngày 35: Review Tổng Thể & Roadmap

## Bài 1 — Self-Assessment Hoàn Chỉnh (Cơ bản)

**Mô tả:** Đánh giá trung thực kiến thức của bạn sau 35 ngày học.

**Yêu cầu:**
1. Copy bảng Self-Assessment Checklist từ lesson.md
2. Đánh dấu mỗi skill: ❌ / 🟡 / ✅
3. Với mỗi skill ❌ hoặc 🟡: viết một đoạn code nhỏ để test kiến thức
4. Tổng kết:
   - Bao nhiêu ✅? (Target: > 70%)
   - Top 3 strongest areas?
   - Top 3 weakest areas cần cải thiện?
5. Lập plan cụ thể để nâng các skill ❌ lên 🟡 trong 2 tuần tới

**Expected output:**
```
Self-Assessment Summary:
- Total skills: 60
- ✅ Strong (comfortable): 42 (70%)
- 🟡 Learning (some practice): 13 (22%)
- ❌ Weak (not yet): 5 (8%)

Strongest areas:
1. FastAPI & Web (90% proficiency)
2. Database (85%)
3. Python Core (80%)

Weakest areas:
1. LlamaIndex (need more practice)
2. Fine-tuning (theoretical only)
3. Advanced typing (TypeVar, Generic)

2-week improvement plan:
- Week 1: Build a LlamaIndex project, practice TypeVar
- Week 2: Fine-tune a small model with LoRA
```

---

## Bài 2 — Code Review & Improve Projects (Trung bình)

**Mô tả:** Review code từ day33 và day34, tìm và fix ít nhất 5 vấn đề mỗi project.

**Yêu cầu:**

**Part A — Day 33 (AI Backend Service):**
1. Review `app/api/documents.py`:
   - Verify: RAGPipeline singleton trong FastAPI lifespan/app state
   - Fix: Document ingestion nên là background task
   - Add: Pagination cho `GET /documents`
2. Review `app/rag/pipeline.py`:
   - Verify: import paths dùng `langchain-qdrant`, `langchain-text-splitters`
   - Verify: `OPENAI_API_KEY` placeholder fail-fast, `MOCK_AI=true` chạy smoke được
   - Add: Retry logic cho OpenAI API calls
   - Add: Cost tracking (log input/output tokens)
3. Add: Integration test cho upload → chat flow ở mock mode trước, real mode sau

**Part B — Day 34 (Agentic System):**
1. Verify: Checkpointer lifespan + compiled graph singleton trong app state
2. Add: Token budget per user (100K tokens/day)
3. Add: Audit logging cho tất cả tool calls
4. Improve: Code executor sandboxing (whitelist imports cụ thể hơn)
5. Verify: approval dùng `interrupt()` + `Command(resume=...)`, không dùng `aupdate_state()` để skip interrupt
6. Add: `GET /agent/runs` — list all runs for current user

**Expected output:**
- Các files đã được cải thiện
- File `CHANGELOG.md` liệt kê tất cả thay đổi và lý do
- Tests cho các improvements quan trọng nhất
- Smoke commands trong README chạy được với mock mode không cần OpenAI key

---

## Bài 3 — Mock Senior Interview (Nâng cao / Challenge)

**Mô tả:** Tự trả lời các câu hỏi interview Senior Python Engineer.

**Phần 1 — Viết câu trả lời (30 phút):**
Trả lời đầy đủ 5 câu sau trong file `interview_answers.md`:

1. **Explain Python's GIL and how it affects your design decisions in an async FastAPI application.**

2. **You have a RAG system that's giving hallucinated answers 20% of the time. Walk me through your debugging process and potential solutions.**

3. **Design a rate limiting system that works across multiple FastAPI instances (horizontal scaling). What data structures and infrastructure would you use?**

4. **Explain the difference between `selectinload` and `joinedload` in SQLAlchemy. When would you use each?**

5. **You need to process 1 million documents for a RAG system. How would you design the ingestion pipeline?**

**Phần 2 — Live Coding (30 phút):**
Implement từ đầu (không nhìn code cũ):

```python
# Task: Implement một async Redis-based distributed lock
# Requirements:
# - Lock có TTL (tự động expire)
# - Lock có thể extend TTL khi cần
# - Lock phải atomic (set nếu không có, fail nếu đã có)
# - Unlock chỉ được thực hiện bởi owner
# - Phải work với async Redis

import redis.asyncio as aioredis
from contextlib import asynccontextmanager
import uuid

class DistributedLock:
    def __init__(self, redis_client: aioredis.Redis, key: str, ttl: int = 30):
        # TODO: implement
        pass

    async def acquire(self) -> bool:
        # TODO: implement - return True nếu acquired, False nếu không
        pass

    async def release(self) -> bool:
        # TODO: implement - return True nếu released, False nếu không phải owner
        pass

    async def extend(self, ttl: int) -> bool:
        # TODO: implement - extend TTL
        pass

@asynccontextmanager
async def distributed_lock(redis_client, key: str, ttl: int = 30):
    # TODO: implement context manager
    pass

# Test:
async def test():
    redis = aioredis.from_url("redis://localhost:6379")

    async with distributed_lock(redis, "my_resource") as acquired:
        if acquired:
            print("Got lock, doing work...")
            await asyncio.sleep(1)
        else:
            print("Could not acquire lock")

    # Verify: try to acquire the same lock from two coroutines
    # Only one should succeed
```

**Phần 3 — Self-Evaluation:**
Sau khi hoàn thành, tự chấm điểm:
- Phần 1: Câu trả lời có đầy đủ và chính xác không? /5
- Phần 2: Code có chạy được không? Có edge cases được handle không? /5
- Điểm trung bình < 3: Cần review lại ngày 9, 11, 14
- Điểm trung bình 3-4: Ready cho Junior-Mid Python roles
- Điểm trung bình > 4: Ready cho Senior Python roles

## 🔍 Gợi ý kiểm tra kết quả

### Verify kiến thức Python Core
```bash
# Chạy comprehensive Python quiz
python -c "
# Test 1: Generator
def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

gen = fib()
result = [next(gen) for _ in range(10)]
assert result == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34], 'Generator failed'
print('✅ Generators: OK')

# Test 2: Decorator
def memoize(func):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper

@memoize
def expensive(n):
    return n * n

assert expensive(5) == 25
print('✅ Decorators: OK')

# Test 3: Type hints
from typing import TypeVar, Generic
T = TypeVar('T')
class Stack(Generic[T]):
    def __init__(self): self._items: list[T] = []
    def push(self, item: T) -> None: self._items.append(item)
    def pop(self) -> T: return self._items.pop()

s: Stack[int] = Stack()
s.push(1)
assert s.pop() == 1
print('✅ Generics: OK')

print('All tests passed!')
"
```

### Verify FastAPI knowledge
```bash
# Nếu có FastAPI app running:
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@test.com","password":"securepass"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@test.com","password":"securepass"}'
```

### Distributed Lock Solution (sau khi tự làm)
```python
# Reference implementation
class DistributedLock:
    def __init__(self, redis_client, key: str, ttl: int = 30):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.owner_id = str(uuid.uuid4())

    async def acquire(self) -> bool:
        # SET key value NX EX ttl — atomic operation
        result = await self.redis.set(
            self.key, self.owner_id, nx=True, ex=self.ttl
        )
        return result is True

    async def release(self) -> bool:
        # Lua script để atomic check-and-delete
        lua_script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(lua_script, 1, self.key, self.owner_id)
        return result == 1

    async def extend(self, additional_ttl: int) -> bool:
        lua_script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('expire', KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await self.redis.eval(
            lua_script, 1, self.key, self.owner_id, additional_ttl
        )
        return result == 1

@asynccontextmanager
async def distributed_lock(redis_client, key: str, ttl: int = 30):
    lock = DistributedLock(redis_client, key, ttl)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
```
