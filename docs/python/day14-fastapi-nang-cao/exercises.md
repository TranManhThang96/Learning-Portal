# Ngày 14: Bài Tập Thực Hành

## Bài 1 (Cơ bản): Rate Limiting Middleware với Counter In-Memory

### Mục tiêu

Xây dựng `RateLimitMiddleware` với sliding window counter in-memory, sau đó test bằng cách gọi nhiều request liên tiếp.

### Yêu cầu

1. Implement `SlidingWindowRateLimiter` class với:
   - `max_requests: int` — số request tối đa trong window
   - `window_seconds: int` — kích thước window (giây)
   - Method `is_allowed(client_id: str) -> tuple[bool, int]` — trả về `(allowed, retry_after_seconds)`

2. Wrap vào `RateLimitMiddleware(BaseHTTPMiddleware)`:
   - Lấy client IP từ `X-Forwarded-For` hoặc `request.client.host`
   - Trả về `429 Too Many Requests` với header `Retry-After` khi vượt limit
   - Thêm header `X-RateLimit-Remaining` vào mọi response

3. Tạo FastAPI app với endpoint `GET /ping` để test

4. Viết test script gửi 15 requests liên tiếp với limit 10/minute

### Khung code

```python
# exercise1/main.py
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Kiểm tra xem client có được phép request không.

        Returns:
            (True, 0) nếu được phép
            (False, retry_after_seconds) nếu bị rate limit
        """
        now = time.time()
        window_start = now - self.window_seconds
        requests = self._windows[client_id]

        # TODO: Xóa timestamps cũ ngoài window

        # TODO: Kiểm tra số lượng requests trong window

        # TODO: Nếu được phép, thêm timestamp hiện tại

        pass  # Xóa dòng này khi implement

    def get_remaining(self, client_id: str) -> int:
        """Trả về số requests còn lại trong window hiện tại."""
        # TODO: Implement
        pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(max_requests, window_seconds)

    async def dispatch(self, request: Request, call_next):
        # TODO: Lấy client IP

        # TODO: Kiểm tra rate limit

        # TODO: Thêm X-RateLimit-Remaining header vào response

        pass  # Xóa dòng này khi implement


app = FastAPI()
app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)


@app.get("/ping")
async def ping():
    return {"message": "pong"}


# Test script — chạy riêng: python test_rate_limit.py
# import httpx
# for i in range(15):
#     r = httpx.get("http://localhost:8000/ping")
#     print(f"Request {i+1}: {r.status_code} | Remaining: {r.headers.get('X-RateLimit-Remaining')}")
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
# exercise1/solution.py
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds
        requests = self._windows[client_id]

        # Xóa timestamps cũ ngoài sliding window
        while requests and requests[0] < window_start:
            requests.popleft()

        if len(requests) >= self.max_requests:
            # retry_after = thời gian đến khi request cũ nhất expire
            retry_after = int(requests[0] + self.window_seconds - now) + 1
            return False, retry_after

        requests.append(now)
        return True, 0

    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        requests = self._windows[client_id]
        # Count requests trong window mà không mutate
        count = sum(1 for ts in requests if ts >= window_start)
        return max(0, self.max_requests - count)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(max_requests, window_seconds)

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        allowed, retry_after = self.limiter.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        remaining = self.limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


app = FastAPI()
app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)


@app.get("/ping")
async def ping():
    return {"message": "pong"}
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Tại sao `defaultdict(deque)` phù hợp hơn `dict` thông thường ở đây?
2. `get_remaining()` không mutate `_windows` — tại sao điều này quan trọng?
3. Nếu deploy 4 Gunicorn workers, rate limiter này có hoạt động đúng không? Tại sao?

---

## Bài 2 (Trung bình): JWT Auth Flow Hoàn Chỉnh

### Mục tiêu

Implement đầy đủ flow: register → login → dùng access token → refresh token → /me endpoint.

### Yêu cầu

1. **Models (in-memory, không cần DB)**:
   - `User` dataclass: `id`, `username`, `email`, `hashed_password`, `is_active`
   - `fake_users_db: dict[int, User]` làm database giả

2. **Schemas (Pydantic)**:
   - `UserCreate(username, email, password)`
   - `UserResponse(id, username, email)` — không expose password
   - `Token(access_token, refresh_token, token_type="bearer")`
   - `LoginRequest(username, password)` — JSON body (không dùng form)

3. **Auth endpoints**:
   - `POST /auth/register` → tạo user, trả về `UserResponse`
   - `POST /auth/login` → verify password, trả về `Token`
   - `POST /auth/refresh` → verify refresh token, trả về `Token` mới
   - `GET /auth/me` → require Bearer token, trả về `UserResponse`

4. **Requirements**:
   - Access token expire sau 15 phút
   - Refresh token expire sau 7 ngày
   - Dùng `pwdlib[argon2]` cho app mới hoặc `passlib[bcrypt]` nếu muốn luyện legacy bcrypt stack
   - Dùng `python-jose[cryptography]` cho JWT
   - Validate trong `get_current_user` dependency: token type phải là "access"
   - Pin hashing/JWT dependencies trong lockfile; đo bcrypt cost trên máy thật và không commit secret key demo

### Setup

```bash
uv add fastapi uvicorn "python-jose[cryptography]" "passlib[bcrypt]"
# App mới có thể đổi phần hash sang pwdlib/Argon2:
# uv add "pwdlib[argon2]"
```

### Khung code

```python
# exercise2/main.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# ===================== Config =====================
SECRET_KEY = "dev-secret-key-change-in-production-must-be-long-enough"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ===================== Password hashing =====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ===================== OAuth2 scheme =====================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ===================== In-memory DB =====================
@dataclass
class User:
    id: int
    username: str
    email: str
    hashed_password: str
    is_active: bool = True


fake_users_db: dict[int, User] = {}
_next_id = 1

# ===================== Schemas =====================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ===================== JWT helpers =====================
def create_access_token(user_id: int) -> str:
    # TODO: Implement
    pass


def create_refresh_token(user_id: int) -> str:
    # TODO: Implement
    pass


# ===================== Dependencies =====================
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    # TODO: Decode token, verify type == "access", lấy user từ fake_db
    pass


# ===================== App + Routers =====================
app = FastAPI(title="JWT Auth Demo")


@app.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(user_data: UserCreate):
    # TODO: Kiểm tra username đã tồn tại chưa, hash password, lưu vào fake_db
    pass


@app.post("/auth/login", response_model=Token)
async def login(credentials: LoginRequest):
    # TODO: Tìm user theo username, verify password, tạo tokens
    pass


@app.post("/auth/refresh", response_model=Token)
async def refresh(body: RefreshRequest):
    # TODO: Verify refresh token, tạo tokens mới
    pass


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    # TODO: Trả về current user
    pass
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
# exercise2/solution.py
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

SECRET_KEY = "dev-secret-key-change-in-production-must-be-long-enough-32chars"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class User:
    id: int
    username: str
    email: str
    hashed_password: str
    is_active: bool = True


fake_users_db: dict[int, User] = {}
_next_id: int = 1


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _create_token(user_id: int, token_type: str, expire: datetime) -> str:
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(user_id, "access", expire)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(user_id, "refresh", expire)


def _find_user_by_username(username: str) -> User | None:
    return next((u for u in fake_users_db.values() if u.username == username), None)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc

    user = fake_users_db.get(user_id)
    if not user or not user.is_active:
        raise exc
    return user


app = FastAPI(title="JWT Auth Demo")


@app.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(user_data: UserCreate):
    global _next_id
    if _find_user_by_username(user_data.username):
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        id=_next_id,
        username=user_data.username,
        email=user_data.email,
        hashed_password=pwd_context.hash(user_data.password),
    )
    fake_users_db[_next_id] = user
    _next_id += 1
    return UserResponse(id=user.id, username=user.username, email=user.email)


@app.post("/auth/login", response_model=Token)
async def login(credentials: LoginRequest):
    user = _find_user_by_username(credentials.username)
    if not user or not pwd_context.verify(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@app.post("/auth/refresh", response_model=Token)
async def refresh(body: RefreshRequest):
    exc = HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc

    user = fake_users_db.get(user_id)
    if not user or not user.is_active:
        raise exc

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
    )
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Tại sao `OAuth2PasswordBearer(tokenUrl="/auth/login")` không tự động gọi `/auth/login`?
2. Điều gì xảy ra nếu bạn dùng access token để gọi endpoint `/auth/refresh`?
3. Nếu muốn implement "logout" (revoke refresh token), bạn cần thay đổi gì trong kiến trúc?

---

## Bài 3 (Nâng cao): Structuring a Blog API với Multiple Routers

### Mục tiêu

Xây dựng Blog API với cấu trúc thư mục rõ ràng, shared dependencies, và demonstrate cách các routers tương tác với nhau.

### Cấu trúc thư mục yêu cầu

```
exercise3/
├── main.py
├── config.py
├── database.py          # SQLite in-memory với SQLAlchemy async
├── dependencies.py      # Shared: get_db, get_current_user
├── exceptions.py        # NotFoundError, ConflictError, setup_exception_handlers
├── routers/
│   ├── __init__.py
│   ├── auth.py          # POST /auth/register, POST /auth/login
│   ├── users.py         # GET /users, GET /users/{id}, PATCH /users/{id}/me
│   └── posts.py         # CRUD /posts, GET /users/{user_id}/posts
└── models/
    ├── __init__.py
    ├── user.py          # SQLAlchemy User model
    └── post.py          # SQLAlchemy Post model
```

### Yêu cầu chi tiết

**routers/auth.py:**
- `POST /auth/register` — public, tạo user mới, trả `UserResponse`
- `POST /auth/login` — public, trả `Token`

**routers/users.py:**
- `GET /users` — public, danh sách users với pagination (`skip`, `limit`)
- `GET /users/{user_id}` — public, chi tiết user
- `PATCH /users/me` — require auth, update current user's profile

**routers/posts.py:**
- `GET /posts` — public, danh sách posts với pagination
- `POST /posts` — require auth, tạo post mới
- `GET /posts/{post_id}` — public, chi tiết post
- `DELETE /posts/{post_id}` — require auth, chỉ author mới được xóa
- `GET /users/{user_id}/posts` — public, posts của một user cụ thể

**Shared dependency pattern:**

```python
# dependencies.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# get_db và get_current_user được dùng ở nhiều routers
# Định nghĩa một lần, import ở nhiều nơi

DBDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]  # Không require auth
```

**Exception handling pattern:**

```python
# exceptions.py
# Khi router raise NotFoundError("Post", post_id)
# → Global handler bắt và trả về {"error": {"code": "NOT_FOUND", "message": "..."}}
```

**Test flow:**

```python
# test_flow.py - chạy với: python test_flow.py
import httpx

BASE = "http://localhost:8000/api/v1"

# 1. Register
r = httpx.post(f"{BASE}/auth/register", json={"username": "alice", "email": "alice@example.com", "password": "secret123"})
assert r.status_code == 201

# 2. Login
r = httpx.post(f"{BASE}/auth/login", json={"username": "alice", "password": "secret123"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Create post
r = httpx.post(f"{BASE}/posts", json={"title": "Hello World", "content": "My first post"}, headers=headers)
assert r.status_code == 201
post_id = r.json()["id"]

# 4. Delete own post
r = httpx.delete(f"{BASE}/posts/{post_id}", headers=headers)
assert r.status_code == 204

# 5. Try delete non-existent post
r = httpx.delete(f"{BASE}/posts/999", headers=headers)
assert r.status_code == 404
assert r.json()["error"]["code"] == "NOT_FOUND"

print("All tests passed!")
```

### Điểm học được

- Cách tổ chức code khi project lớn dần
- Import circular dependency cần tránh (ví dụ: `users.py` không import từ `posts.py`)
- Shared `DBDep`, `CurrentUserDep` type aliases giảm lặp code
- Authorization logic (chỉ author mới được xóa post) thuộc về service layer, không phải router
- `GET /users/{user_id}/posts` — nested resource, định nghĩa ở `posts.py` nhưng prefix dưới `/users`

### Gợi ý cấu trúc main.py

```python
# exercise3/main.py
from fastapi import FastAPI
from .routers import auth, users, posts
from .exceptions import setup_exception_handlers

def create_app() -> FastAPI:
    app = FastAPI(title="Blog API", version="1.0.0")
    setup_exception_handlers(app)

    # Tất cả routes đều có prefix /api/v1
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(posts.router, prefix="/api/v1")

    return app

app = create_app()
```
