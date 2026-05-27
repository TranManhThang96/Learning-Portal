# Bài Tập — Ngày 31: Ôn tập Python Core + FastAPI

## Bài 1 — Profile một FastAPI App (Cơ bản)

**Mô tả:** Tìm và đo performance bottleneck trong một FastAPI endpoint đơn giản.

**Yêu cầu:**
1. Tạo FastAPI app với endpoint `/compute` thực hiện Fibonacci(35) (CPU-bound)
2. Tạo endpoint `/fetch` thực hiện 5 HTTP calls đến `httpbin.org/delay/1` (I/O-bound)
3. Dùng `cProfile` để profile endpoint `/compute`
4. Dùng `time.perf_counter()` để đo latency của cả hai endpoints
5. So sánh kết quả và giải thích tại sao chúng khác nhau

**Expected output:**
```
/compute endpoint: ~3.5 seconds (CPU-bound, không benefit từ async)
/fetch serial: ~5 seconds
/fetch parallel (asyncio.gather): ~1 second

cProfile output:
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  ...fibonacci function appears at top...
```

**Hint:**
- Dùng `httpx.AsyncClient` cho async HTTP calls
- `asyncio.gather(*[fetch() for _ in range(5)])` cho parallel
- CPU-bound tasks trong FastAPI: consider `run_in_executor` hoặc separate worker

---

## Bài 2 — Code Review & Fix (Trung bình)

**Mô tả:** Review và fix một FastAPI app với nhiều vấn đề.

**Code cần fix:**
```python
# bad_app.py — Có ít nhất 8 vấn đề, tìm và fix tất cả
from fastapi import FastAPI
import sqlite3
import hashlib

app = FastAPI()
db = sqlite3.connect("users.db")  # Vấn đề 1

@app.post("/login")
def login(email: str, password: str):  # Vấn đề 2, 3
    cursor = db.cursor()
    # Vấn đề 4
    cursor.execute(f"SELECT * FROM users WHERE email='{email}' AND password='{password}'")
    user = cursor.fetchone()
    if not user:
        return {"error": "wrong credentials"}  # Vấn đề 5
    print(f"User logged in: {email}, password: {password}")  # Vấn đề 6
    return {"user": user, "token": "abc123"}  # Vấn đề 7, 8

@app.get("/users")
def get_all_users():  # Vấn đề 9
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()  # Vấn đề 10
```

**Yêu cầu:**
1. Liệt kê ít nhất 8 vấn đề với giải thích
2. Viết lại app với FastAPI best practices:
   - Async handlers
   - Proper authentication (JWT)
   - SQL injection prevention
   - Proper HTTP status codes
   - Response schemas (không expose password)
   - Structured logging
   - Proper error handling

**Expected output:**
- File `good_app.py` với tất cả vấn đề đã được fix
- File `code_review_notes.md` liệt kê tất cả vấn đề và giải pháp

---

## Bài 3 — Build Production FastAPI Module (Nâng cao / Challenge)

**Mô tả:** Xây dựng một `ProductService` production-ready với full type hints, async, caching, và tests.

**Yêu cầu:**
1. Implement `Product` SQLAlchemy model với các fields: `id`, `name`, `price`, `stock`, `created_at`
2. Implement `ProductRepository` với các methods:
   - `async def get_by_id(id: UUID) -> Product | None`
   - `async def list(page: int, per_page: int) -> tuple[list[Product], int]`
   - `async def create(data: ProductCreate) -> Product`
   - `async def update_stock(id: UUID, delta: int) -> Product`
3. Implement FastAPI router với endpoints:
   - `GET /products` — với pagination
   - `GET /products/{id}`
   - `POST /products`
   - `PATCH /products/{id}/stock`
4. Thêm Redis caching cho `GET /products/{id}` với TTL 60s
5. Viết pytest tests cho tất cả endpoints với `httpx.AsyncClient`

**Expected output:**
```bash
pytest tests/ -v
# ✅ test_create_product PASSED
# ✅ test_get_product PASSED
# ✅ test_get_product_cached PASSED  (second call hits cache)
# ✅ test_list_products_pagination PASSED
# ✅ test_update_stock PASSED
# ✅ test_update_stock_insufficient PASSED
```

**Hint:**
- Dùng `pytest-asyncio` với `asyncio_mode = "auto"`
- Mock Redis với `fakeredis.aioredis.FakeRedis()`
- `httpx.AsyncClient(app=app, base_url="http://test")` để test FastAPI

## 🔍 Gợi ý kiểm tra kết quả

### Kiểm tra type hints
```bash
mypy --strict your_module.py
# Expect: Success: no issues found
```

### Kiểm tra code style
```bash
ruff check your_module.py
ruff format --check your_module.py
```

### Benchmark endpoint
```bash
# Install: uv add httpie
# Test 100 concurrent requests
python -c "
import asyncio
import httpx
import time

async def bench():
    async with httpx.AsyncClient() as client:
        start = time.perf_counter()
        tasks = [client.get('http://localhost:8000/products') for _ in range(100)]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        print(f'100 requests in {elapsed:.2f}s = {100/elapsed:.0f} req/s')
        print(f'Status codes: {set(r.status_code for r in results)}')

asyncio.run(bench())
"
```
