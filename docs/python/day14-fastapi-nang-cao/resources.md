# Ngày 14: Tài Liệu Tham Khảo

## Thư viện chính

### python-jose — JWT cho Python

- **Tài liệu chính thức:** https://python-jose.readthedocs.io/
- **GitHub:** https://github.com/mpdavis/python-jose
- **PyPI:** https://pypi.org/project/python-jose/

**Cài đặt:**
```bash
uv add "python-jose[cryptography]"
# [cryptography] backend cần thiết cho HS256, RS256
```

**Lý do chọn python-jose:**
- Supports HS256, RS256, ES256 (đủ cho hầu hết use cases)
- API đơn giản: `jwt.encode()`, `jwt.decode()`
- Throw `JWTError` khi token invalid hoặc expired

**Thay thế:** `PyJWT` — phổ biến hơn, API tương tự, cũng tốt

```python
# python-jose
from jose import jwt, JWTError
token = jwt.encode({"sub": "user1"}, "secret", algorithm="HS256")
payload = jwt.decode(token, "secret", algorithms=["HS256"])

# PyJWT (alternative)
import jwt
token = jwt.encode({"sub": "user1"}, "secret", algorithm="HS256")
payload = jwt.decode(token, "secret", algorithms=["HS256"])
```

---

### pwdlib / passlib — Password Hashing

**Khuyến nghị cho app mới:** `pwdlib[argon2]`, cùng hướng với FastAPI security tutorial hiện hành.

```bash
uv add "pwdlib[argon2]"
```

```python
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
hashed = password_hash.hash("my_password")
is_valid = password_hash.verify("my_password", hashed)
```

**Legacy/compatibility option:** `passlib[bcrypt]` vẫn rất phổ biến khi hệ thống đã có bcrypt hashes.

- **Tài liệu chính thức:** https://passlib.readthedocs.io/
- **GitHub:** https://github.com/efficks/passlib
- **PyPI:** https://pypi.org/project/passlib/

**Caveat:** pin hashing backend trong lockfile và chạy test hash/verify trên CI. Với hệ thống mới, ưu tiên Argon2id nếu policy/security team không yêu cầu bcrypt; với hệ thống cũ, giữ bcrypt và migrate có kế hoạch.

**Cài đặt:**
```bash
uv add "passlib[bcrypt]"
```

**Lý do dùng passlib thay vì bcrypt trực tiếp:**
- `CryptContext` quản lý multiple schemes và auto-upgrade
- `deprecated="auto"`: nếu user có hash cũ (MD5), passlib tự nhận biết và báo cần re-hash
- API thống nhất dù đổi algorithm

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash
hashed = pwd_context.hash("my_password")

# Verify (trả về True/False, không throw exception)
is_valid = pwd_context.verify("my_password", hashed)

# Kiểm tra xem hash có cần upgrade không (khi migrate algorithm)
needs_update = pwd_context.needs_update(hashed)
```

**bcrypt cost factor:**
- Default rounds = 12 (2^12 = 4096 iterations)
- Mỗi tăng 1 = chậm gấp đôi
- rounds=12: ~0.3s/hash — đủ an toàn, đủ nhanh
- Không tăng quá rounds=14 trừ khi có yêu cầu security đặc biệt

---

### slowapi — Rate Limiting với Redis

- **Tài liệu chính thức:** https://slowapi.readthedocs.io/
- **GitHub:** https://github.com/laurentS/slowapi
- **PyPI:** https://pypi.org/project/slowapi/

**Cài đặt:**
```bash
uv add slowapi redis
```

**Ví dụ đầy đủ:**
```python
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# key_func: hàm lấy identifier từ request (IP, user_id, API key)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",  # Shared state qua Redis
    default_limits=["100/minute"],
)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# Per-route limit (override default)
@app.get("/search")
@limiter.limit("10/minute")  # Search endpoint giới hạn chặt hơn
async def search(request: Request, q: str):
    ...


# Rate limit theo user_id thay vì IP (sau khi auth)
def get_user_id(request: Request) -> str:
    user = getattr(request.state, "user", None)
    return str(user.id) if user else get_remote_address(request)


user_limiter = Limiter(key_func=get_user_id, storage_uri="redis://localhost:6379")

@app.post("/api/expensive-operation")
@user_limiter.limit("5/hour")
async def expensive_operation(request: Request):
    ...
```

---

## FastAPI Security Documentation

- **FastAPI Security Overview:** https://fastapi.tiangolo.com/tutorial/security/
- **OAuth2 with Password:** https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- **HTTP Basic Auth:** https://fastapi.tiangolo.com/tutorial/security/http-basic-auth/
- **Dependencies in path operations:** https://fastapi.tiangolo.com/tutorial/dependencies/

**Đọc theo thứ tự:**
1. https://fastapi.tiangolo.com/tutorial/security/first-steps/ — hiểu OAuth2PasswordBearer
2. https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ — JWT implementation
3. https://fastapi.tiangolo.com/advanced/security/ — Advanced patterns

---

## Middleware

- **FastAPI Middleware docs:** https://fastapi.tiangolo.com/tutorial/middleware/
- **Starlette BaseHTTPMiddleware:** https://www.starlette.io/middleware/
- **CORS Middleware:** https://fastapi.tiangolo.com/tutorial/cors/

**Các built-in middleware hay dùng:**
```python
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["myapp.com", "*.myapp.com"])
```

---

## Background Tasks

- **FastAPI Background Tasks:** https://fastapi.tiangolo.com/tutorial/background-tasks/
- **ARQ (async task queue):** https://arq-docs.helpmanual.io/
- **Celery với FastAPI:** https://docs.celeryq.dev/en/stable/getting-started/

**Khi nào dùng gì:**

| Use case | Tool |
|---|---|
| Simple async side effects (< 1s) | `BackgroundTasks` |
| Email sending, webhooks | `BackgroundTasks` nếu có thể mất/retry thủ công; ARQ/Celery nếu cần durability |
| Long-running jobs (video encoding) | Celery hoặc ARQ |
| Cron jobs | APScheduler hoặc Celery Beat |
| Task monitoring cần thiết | Celery + Flower |

`BackgroundTasks` chạy trong cùng process, không có persistent queue, retry, dead-letter queue, hoặc monitoring. Không dùng thay thế durable queue cho nghiệp vụ quan trọng.

---

## structlog — Structured Logging

- **Tài liệu chính thức:** https://www.structlog.org/
- **GitHub:** https://github.com/hynek/structlog
- **PyPI:** https://pypi.org/project/structlog/

**Cài đặt:**
```bash
uv add structlog
```

**Setup cơ bản:**
```python
# logging_config.py
import logging
import structlog

def setup_logging(log_level: str = "INFO", json_logs: bool = False):
    """
    Cấu hình structlog.
    - Development: console renderer (màu sắc, dễ đọc)
    - Production: JSON renderer (dễ parse bởi Datadog, Loki, CloudWatch)
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

---

## Lifespan Events

- **FastAPI Lifespan:** https://fastapi.tiangolo.com/advanced/events/
- **Starlette Lifespan:** https://www.starlette.io/lifespan/

**Migration từ on_event (deprecated):**
```python
# CŨ (deprecated)
@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

# MỚI (khuyến nghị)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()    # startup
    yield
    await db.disconnect() # shutdown

app = FastAPI(lifespan=lifespan)
```

---

## Công cụ hữu ích

### httpie — test API từ terminal
```bash
uv add httpie

# Login
http POST localhost:8000/auth/token username=alice password=secret

# Request với Bearer token
http GET localhost:8000/users/me "Authorization: Bearer <token>"
```

### pytest + httpx — test FastAPI
```bash
uv add pytest httpx pytest-asyncio

# test_auth.py
from httpx import AsyncClient, ASGITransport
import pytest
from myapp.main import app

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/token", data={"username": "alice", "password": "secret"})
        assert r.status_code == 200
        assert "access_token" in r.json()
```

### JWT decode online
- https://jwt.io — paste token để xem payload (chỉ decode, không verify)
