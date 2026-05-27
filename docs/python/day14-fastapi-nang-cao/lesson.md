# Ngày 14: FastAPI Nâng Cao

## 🎯 Mục tiêu học tập

Sau ngày 13, bạn sẽ có thể:

- Viết Middleware cho logging, rate limiting trong FastAPI
- Implement JWT Authentication với access token và refresh token
- Sử dụng Background Tasks và Lifespan để quản lý startup/shutdown
- Cấu hình Global Exception Handlers thay vì try/catch rải rác
- Cấu trúc project lớn với APIRouter, prefix, tags, và shared dependencies

---

## 🔄 So sánh với NestJS

| Khái niệm NestJS | Tương đương FastAPI | Ghi chú |
|---|---|---|
| `Interceptors` / `Middleware` | `BaseHTTPMiddleware` / `@app.middleware("http")` | FastAPI dùng ASGI middleware |
| `Guards` | `Depends()` dependencies | Guard trong NestJS inject vào route, FastAPI inject dependency |
| `ExceptionFilters` | `@app.exception_handler()` | Decorator đăng ký handler cho từng loại exception |
| `@Module()` + `@Controller()` | `APIRouter` + `include_router()` | Không có class-based, chỉ dùng router instance |
| `@Injectable()` Service | Python class thường, inject qua `Depends()` | Không có DI container, chỉ là function composition |
| `app.useGlobalPipes()` | Pydantic validation tự động | Validation xảy ra tại model level, không cần pipe riêng |
| `ConfigModule` | `pydantic-settings` | Sẽ học kỹ ở Day 15 |

**Tư duy chính:** NestJS có một DI container trung tâm quản lý lifecycle. FastAPI dùng function composition — mọi thứ đều là function, dependency là function trả về giá trị, không có magic.

---

## 📖 Lý thuyết

### Section 1: Middleware

Middleware trong FastAPI chạy trước và sau mỗi request, tương tự NestJS Interceptors. Có hai cách viết middleware:

**Cách 1: `@app.middleware("http")` decorator** — đơn giản nhưng ít linh hoạt.

**Cách 2: `BaseHTTPMiddleware` class** — có thể tái sử dụng, thêm vào nhiều app khác nhau.

#### RequestLoggingMiddleware với structlog và request_id

```python
# src/myapp/middleware/logging.py
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Tạo unique request ID để trace qua logs
        request_id = str(uuid.uuid4())

        # Bind request_id vào structlog context — mọi log trong request này đều có field này
        bound_logger = logger.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Lưu vào request.state để các route handler có thể dùng
        request.state.request_id = request_id
        request.state.logger = bound_logger

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            bound_logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Trả request_id về client để debug
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            bound_logger.error(
                "request_failed",
                error=str(exc),
                duration_ms=round(duration_ms, 2),
            )
            raise
```

#### RateLimitMiddleware (in-memory, dùng cho development)

```python
# src/myapp/middleware/rate_limit.py
import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple sliding window rate limiter dùng in-memory.

    QUAN TRỌNG: Đây chỉ dùng cho development/single instance.
    Production với nhiều worker/pod cần dùng Redis.
    Xem slowapi + Redis: https://github.com/laurentS/slowapi
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        # Dict[client_ip, deque[timestamp]]
        self._requests: dict[str, deque] = defaultdict(deque)

    def _get_client_ip(self, request: Request) -> str:
        # Lấy real IP khi đứng sau proxy (nginx, load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        now = time.time()
        window_start = now - self.window_seconds

        # Xóa các request cũ ngoài window
        client_requests = self._requests[client_ip]
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()

        if len(client_requests) >= self.requests_per_minute:
            # Tính thời gian phải chờ
            retry_after = int(client_requests[0] + self.window_seconds - now) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        client_requests.append(now)
        return await call_next(request)


# NOTE: Production rate limiting với slowapi + Redis:
#
# from slowapi import Limiter
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded
#
# limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379")
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
#
# @router.get("/users")
# @limiter.limit("60/minute")
# async def list_users(request: Request):
#     ...
```

**Đăng ký middleware:**

```python
# src/myapp/main.py
from myapp.middleware.logging import RequestLoggingMiddleware
from myapp.middleware.rate_limit import InMemoryRateLimitMiddleware

app = FastAPI()

# Thứ tự quan trọng! Middleware được thêm sau cùng chạy đầu tiên (LIFO)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware, requests_per_minute=100)
```

---

### Section 2: JWT Authentication

FastAPI không có built-in auth như NestJS Passport. Ta tự xây dùng:
- `python-jose[cryptography]` — tạo và verify JWT
- Password hashing: FastAPI docs hiện dùng `pwdlib[argon2]` cho Argon2; `passlib[bcrypt]` vẫn phổ biến trong codebase cũ. Chọn một stack, pin version trong lockfile, và đo latency login trên hardware thật.

```bash
uv add "python-jose[cryptography]" "pwdlib[argon2]"
# Hoặc nếu cần tương thích bcrypt/passlib:
uv add "python-jose[cryptography]" "passlib[bcrypt]"
```

#### Cấu trúc files

```
src/myapp/
├── auth/
│   ├── __init__.py
│   ├── dependencies.py   # get_current_user, get_current_active_user
│   ├── router.py         # /token, /refresh endpoints
│   ├── schemas.py        # Token, TokenData Pydantic models
│   └── service.py        # create_access_token, verify_password, etc.
```

#### auth/service.py — JWT utilities

```python
# src/myapp/auth/service.py
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash

from myapp.config import get_settings

settings = get_settings()

# Argon2 password hashing theo FastAPI docs hiện hành.
# Nếu team đang dùng bcrypt/passlib, giữ tương thích và migrate có kế hoạch.
password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
) -> str:
    """
    Tạo JWT access token.

    Args:
        subject: Thường là user_id hoặc username (sẽ thành claim "sub")
        expires_delta: Thời gian sống. Mặc định từ settings.
        extra_claims: Claims bổ sung, ví dụ {"roles": ["admin"]}
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(subject: str | Any) -> str:
    """Refresh token sống lâu hơn (7 ngày), chỉ dùng để lấy access token mới."""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """Decode và verify token. Raise JWTError nếu invalid/expired."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
```

#### auth/schemas.py — Pydantic models

```python
# src/myapp/auth/schemas.py
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str
    token_type: str  # "access" hoặc "refresh"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str
```

#### auth/dependencies.py — Dependency injection

```python
# src/myapp/auth/dependencies.py
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from myapp.auth.service import decode_token
from myapp.users.models import User
from myapp.users.repository import UserRepository
from myapp.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

# OAuth2PasswordBearer khai báo URL endpoint để lấy token
# FastAPI dùng URL này để render "Authorize" button trong Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)

        # Kiểm tra đây là access token, không phải refresh token
        if payload.get("type") != "access":
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


# Type alias để tái sử dụng trong route handlers
CurrentUser = Annotated[User, Depends(get_current_active_user)]
```

#### auth/router.py — Login và Refresh endpoints

```python
# src/myapp/auth/router.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.auth.schemas import Token, RefreshRequest
from myapp.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from myapp.database import get_db
from myapp.users.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=Token)
async def login(
    # OAuth2PasswordRequestForm parse application/x-www-form-urlencoded
    # (theo chuẩn OAuth2, KHÔNG phải JSON)
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login bằng username/password, nhận access + refresh token."""
    repo = UserRepository(db)
    user = await repo.get_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dùng refresh token để lấy access token mới mà không cần login lại."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )

    try:
        payload = decode_token(body.refresh_token)

        if payload.get("type") != "refresh":
            raise credentials_exception

        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))

    if not user or not user.is_active:
        raise credentials_exception

    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return Token(access_token=new_access_token, refresh_token=new_refresh_token)


@router.get("/me")
async def get_me(current_user: "CurrentUser"):
    """Lấy thông tin user đang đăng nhập."""
    from myapp.auth.dependencies import CurrentUser
    return current_user
```

---

### Section 3: Background Tasks + Lifespan

#### Lifespan — thay thế `@app.on_event("startup")`

Từ FastAPI 0.93+, dùng `lifespan` context manager thay vì deprecated `on_event`:

```python
# src/myapp/main.py
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from myapp.database import engine, Base
from myapp.cache import redis_client

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # === STARTUP ===
    logger.info("application_starting")

    # Tạo tables (production nên dùng Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Test Redis connection
    await redis_client.ping()
    logger.info("redis_connected")

    logger.info("application_ready")

    yield  # Application chạy ở đây

    # === SHUTDOWN ===
    logger.info("application_shutting_down")

    # Đóng connection pools gracefully
    await engine.dispose()
    await redis_client.aclose()

    logger.info("application_stopped")


app = FastAPI(
    title="My API",
    version="1.0.0",
    lifespan=lifespan,
)
```

#### Background Tasks

`BackgroundTasks` cho phép chạy code sau khi response đã trả về client. Phù hợp cho:
- Gửi email
- Ghi audit log
- Cập nhật analytics
- Gọi webhook

```python
# src/myapp/routers/users.py
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.database import get_db
from myapp.users.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])
logger = structlog.get_logger()


async def send_welcome_email(user_email: str, username: str) -> None:
    """
    Gửi welcome email sau khi user đăng ký.
    Chạy trong background — không block response.
    """
    logger.info("sending_welcome_email", email=user_email, username=username)
    # await email_service.send(to=user_email, template="welcome", ...)
    logger.info("welcome_email_sent", email=user_email)


async def audit_log(
    action: str,
    user_id: int,
    resource: str,
    details: dict | None = None,
) -> None:
    """Ghi audit log vào DB hoặc external service."""
    logger.info(
        "audit_event",
        action=action,
        user_id=user_id,
        resource=resource,
        details=details or {},
    )
    # await audit_service.log(...)


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # ... tạo user trong DB ...
    # user = await user_repo.create(user_data)

    # Thêm tasks vào queue — chạy sau khi response được gửi đi
    background_tasks.add_task(
        send_welcome_email,
        user_email=user_data.email,
        username=user_data.username,
    )
    background_tasks.add_task(
        audit_log,
        action="user_created",
        user_id=1,  # user.id
        resource="users",
        details={"email": user_data.email},
    )

    # Response trả về ngay, email gửi sau
    return {"id": 1, "email": user_data.email, "username": user_data.username}
```

**Lưu ý về BackgroundTasks:**
- Chạy trong cùng process, không phải worker riêng biệt
- Nếu task lâu (> vài giây) hoặc cần retry → dùng Celery hoặc ARQ
- Nếu app crash, task đang chạy có thể bị mất
- Không phải durable queue: không có persistence, retry policy, dead-letter queue, scheduling, hoặc monitoring. Chỉ dùng cho side effect ngắn, idempotent, có thể chạy lại hoặc mất mà không làm hỏng dữ liệu chính.

---

### Section 4: Global Exception Handlers

Thay vì try/catch trong từng route, đăng ký handler toàn cục:

```python
# src/myapp/exceptions.py
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class AppException(Exception):
    """Base exception cho business logic errors."""

    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, id: int | str):
        super().__init__(
            message=f"{resource} with id '{id}' not found",
            code="NOT_FOUND",
            status_code=404,
        )


class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT", status_code=409)


def setup_exception_handlers(app: FastAPI) -> None:
    """Đăng ký tất cả exception handlers lên app instance."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handler cho HTTPException — lỗi do FastAPI raise hoặc code raise trực tiếp."""
        logger.warning(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                }
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handler cho Pydantic validation errors.
        Trả về chi tiết từng field bị lỗi thay vì raw Pydantic format.
        """
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"][1:]),  # bỏ "body" prefix
                "message": error["msg"],
                "type": error["type"],
            })

        logger.info(
            "validation_error",
            path=request.url.path,
            errors=errors,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": errors,
                }
            },
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handler cho custom business logic exceptions."""
        logger.info(
            "app_exception",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all handler — bắt mọi exception chưa được handle.
        KHÔNG expose error details ra ngoài trong production.
        """
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            error=str(exc),
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
            exc_info=True,  # Include traceback trong log
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
```

**Dùng trong route:**

```python
# Không cần try/catch, chỉ raise exception
@router.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise NotFoundError(resource="User", id=user_id)  # Handler tự bắt
    return user
```

---

### Section 5: Router Structure cho Large Apps

#### Folder structure

```
src/myapp/
├── main.py              # App factory, middleware, lifespan
├── config.py            # Settings (pydantic-settings)
├── database.py          # Engine, SessionLocal, get_db
├── exceptions.py        # AppException, setup_exception_handlers
├── middleware/
│   ├── logging.py
│   └── rate_limit.py
├── auth/
│   ├── dependencies.py  # get_current_user, CurrentUser type alias
│   ├── router.py        # /auth/token, /auth/refresh
│   ├── schemas.py       # Token, LoginRequest
│   └── service.py       # JWT utils, password hashing
├── users/
│   ├── models.py        # SQLAlchemy User model
│   ├── repository.py    # UserRepository
│   ├── router.py        # /users CRUD endpoints
│   ├── schemas.py       # UserCreate, UserResponse, UserUpdate
│   └── service.py       # UserService (business logic)
└── posts/
    ├── models.py
    ├── repository.py
    ├── router.py
    └── schemas.py
```

#### APIRouter với prefix, tags, dependencies

```python
# src/myapp/users/router.py
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.auth.dependencies import get_current_active_user, CurrentUser
from myapp.database import get_db
from myapp.users.schemas import UserResponse, UserUpdate

# prefix="/users": mọi route trong router này đều bắt đầu bằng /users
# tags=["Users"]: group trong Swagger UI
# dependencies: áp dụng cho TẤT CẢ routes trong router (require auth)
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(get_current_active_user)],  # Auth required cho toàn router
)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # get_current_active_user đã chạy tự động trước khi vào đây
    ...


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    # CurrentUser = Annotated[User, Depends(get_current_active_user)]
    return current_user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ...
```

#### main.py — App factory với include_router

```python
# src/myapp/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from myapp.middleware.logging import RequestLoggingMiddleware
from myapp.exceptions import setup_exception_handlers
from myapp.auth.router import router as auth_router
from myapp.users.router import router as users_router
from myapp.posts.router import router as posts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup / shutdown (xem Section 3)
    yield


def create_app() -> FastAPI:
    """App factory pattern — dễ test, dễ tạo nhiều instances."""
    app = FastAPI(title="Blog API", version="1.0.0", lifespan=lifespan)

    # Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    setup_exception_handlers(app)

    # Routers — prefix /api/v1 áp dụng cho tất cả
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(posts_router, prefix="/api/v1")

    # Health check không có prefix
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

**Kết quả routes:**
- `POST /api/v1/auth/token`
- `POST /api/v1/auth/refresh`
- `GET  /api/v1/users/`
- `GET  /api/v1/users/me`
- `PATCH /api/v1/users/{user_id}`
- `GET  /health`

---

## ⚠️ Common Mistakes

| Lỗi | Vấn đề | Cách sửa |
|---|---|---|
| Dùng `@app.on_event("startup")` | Deprecated từ FastAPI 0.93, sẽ bị xóa | Dùng `lifespan` context manager |
| Thứ tự middleware sai | Middleware thêm sau cùng chạy đầu tiên (LIFO) | Thêm outer middleware trước (logging trước rate limit) |
| Không kiểm tra `token_type` trong JWT | Refresh token dùng được như access token | Luôn check `payload["type"] == "access"` |
| `BackgroundTasks` cho task lâu | Nếu process restart, task mất | Task > 5 giây → Celery/ARQ/Redis Queue |
| Rate limiter in-memory với nhiều workers | Mỗi worker có counter riêng | Dùng Redis-backed rate limiter (slowapi) |
| Exception handler bắt `Exception` đặt trước | Handler đặt sau đăng ký sau, ưu tiên cao hơn | Đăng ký generic `Exception` handler CUỐI CÙNG |
| Expose stack trace trong production | Leak thông tin nhạy cảm | Generic handler chỉ log, không trả trace ra response |

---

## ✅ Best Practices

1. **Dùng `create_app()` factory** — tách khởi tạo app khỏi global scope, dễ test với `TestClient(create_app())`

2. **Type alias cho dependencies** — `CurrentUser = Annotated[User, Depends(get_current_active_user)]` giảm lặp code

3. **`request_id` trong mọi log** — bind vào structlog context ngay trong middleware, mọi downstream log đều có

4. **Phân tách exception hierarchy** — `AppException` → `NotFoundError`, `ConflictError`, v.v. Mỗi loại có HTTP status riêng

5. **Router-level dependencies** — thay vì thêm `Depends(auth)` vào từng route, thêm vào `APIRouter(dependencies=[...])`

6. **Không lưu refresh token ở client-side only** — production nên lưu refresh token vào DB (whitelist) để có thể revoke

---

## ⚖️ Trade-offs

| Quyết định | Ưu điểm | Nhược điểm |
|---|---|---|
| JWT stateless | Không cần DB lookup khi verify | Không thể revoke token trước khi expire |
| JWT + DB whitelist | Có thể logout/revoke | Mỗi request cần DB lookup |
| In-memory rate limit | Zero infrastructure | Không hoạt động với multiple workers |
| Redis rate limit (slowapi) | Works với multiple workers/pods | Cần Redis infrastructure |
| `BackgroundTasks` | Built-in, không cần setup | Không có retry, mất khi process crash |
| Celery/ARQ | Retry, persistent, monitoring | Cần Redis/RabbitMQ, thêm complexity |

---

## 🔌 WebSocket trong FastAPI

> **Phần mở rộng** — đọc sau khi nắm vững core. Thời gian ước tính: 30 phút.

```python
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    Query,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)

app = FastAPI()

# Connection Manager — quản lý nhiều WebSocket connections
class ConnectionManager:
    def __init__(self) -> None:
        self._active: dict[str, WebSocket] = {}  # user_id → WebSocket
        self._rooms: dict[str, set[str]] = {}    # room_id → set of user_ids

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self._active.pop(user_id, None)
        for members in self._rooms.values():
            members.discard(user_id)

    async def send_personal(self, user_id: str, message: dict) -> None:
        if ws := self._active.get(user_id):
            await ws.send_json(message)

    async def broadcast_to_room(self, room_id: str, message: dict) -> None:
        for uid in self._rooms.get(room_id, set()):
            await self.send_personal(uid, message)

    def join_room(self, user_id: str, room_id: str) -> None:
        self._rooms.setdefault(room_id, set()).add(user_id)

manager = ConnectionManager()

async def get_ws_user(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> str:
    """
    Demo auth cho WebSocket. Nếu thiếu/invalid token, đóng bằng close code 1008
    (policy violation) thay vì raise HTTPException.
    """
    if token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return token  # demo: token chính là user_id


@app.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    user_id: Annotated[str, Depends(get_ws_user)],
) -> None:
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "join_room":
                manager.join_room(user_id, data["room_id"])
            elif data.get("type") == "chat":
                await manager.broadcast_to_room(data["room_id"], {
                    "from": user_id, "text": data["text"],
                })
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# SSE cho AI streaming responses:
from fastapi.responses import StreamingResponse

@app.get("/ai/stream")
async def stream_ai(prompt: str) -> StreamingResponse:
    async def generate():
        for word in f"Response to: {prompt}".split():
            yield f"data: {word}\n\n"  # SSE format
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# WebSocket vs SSE:
# WebSocket: bidirectional — chat, collaborative editing, gaming
# SSE: server→client only — AI streaming, live feeds, notifications
```

**WebSocket auth note:** query token ở ví dụ chỉ để demo dễ chạy. Production nên dùng token ngắn hạn, cookie đã bảo vệ, hoặc subprotocol/header thông qua gateway phù hợp; luôn validate trước `accept()` và dùng close code chuẩn như `1008` cho policy/auth failure.

## 🔒 Security Best Practices

> **Phần mở rộng** — đọc sau khi nắm vững core. Thời gian ước tính: 20 phút.

```python
from pwdlib import PasswordHash
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

# Argon2id password hashing — khuyến nghị mặc định cho app mới
password_hash = PasswordHash.recommended()

def hash_password(plain: str) -> str:
    return password_hash.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)

# secrets module — cryptographically secure random
token = secrets.token_urlsafe(32)    # URL-safe token (API keys, reset links)
hex_token = secrets.token_hex(32)    # Hex token (CSRF)
# Timing-safe comparison — chống timing attacks
is_valid = secrets.compare_digest(provided, stored)

# Secure headers middleware — tương đương helmet.js
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'",
        })
        return response

# Vulnerability scanning:
# uv run pip-audit  →  báo cáo packages có known CVEs
```

**Hashing/scanning caveat:**

- Chọn bcrypt/Argon2id theo policy của team, pin dependency trong lockfile, và đo latency login thực tế trước khi tăng cost factor.
- `passlib` tiện cho migration nhiều scheme, nhưng vẫn cần kiểm tra compatibility với backend `bcrypt`/`argon2` đang dùng trong CI.
- `pip-audit`, `bandit`, secret scanning, và image scanning chỉ là safety net; không thay thế threat modeling, review permission, và kiểm tra cấu hình production.

---

## 🚀 Performance Notes

- **Middleware overhead:** Mỗi middleware thêm latency. Đo với `time.perf_counter()` trước và sau `call_next()`
- **JWT verification:** `jose.decode()` là CPU-bound. Với > 10K req/s, consider caching decoded token (short TTL)
- **bcrypt cost factor:** Mặc định `rounds=12`. Tăng rounds = an toàn hơn nhưng chậm hơn. Login endpoint không nên có rate limit quá cao
- **Background task queue:** Nhiều tasks nhỏ tốt hơn một task lớn — tránh blocking event loop
- **`include_router` order:** Route được định nghĩa trước có priority cao hơn nếu pattern overlap (ít xảy ra với REST API)

---

## 📝 Tóm tắt

Ngày 13 đã đưa FastAPI từ "chạy được" lên "production-ready":

- **Middleware** xử lý cross-cutting concerns (logging, rate limiting) không lặp code trong từng route
- **JWT Auth** với `python-jose` + `pwdlib[argon2]` (hoặc `passlib[bcrypt]` cho legacy), inject qua `Depends()` — tương tự NestJS Guards nhưng explicit hơn
- **Lifespan** quản lý startup/shutdown một cách đúng đắn, thay thế deprecated `on_event`
- **Background Tasks** cho async side effects không block response
- **Global Exception Handlers** thống nhất format lỗi, không có try/catch rải rác
- **APIRouter** + `include_router` tổ chức code scalable, tương tự NestJS Modules
- **WebSocket** với ConnectionManager pattern cho real-time features
- **Security**: Argon2/bcrypt, `secrets` module, secure headers — tương tự helmet.js

**Ngày mai (Day 15):** Tích hợp database + Redis caching vào FastAPI, pagination patterns, và giải quyết N+1 query problem.
