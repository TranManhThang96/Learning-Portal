# Ngày 13: FastAPI Cơ Bản

## 🎯 Mục tiêu học tập

Sau bài học này, bạn sẽ:
- Setup FastAPI app với lifespan event handling
- Định nghĩa routes với Path, Query, Body parameters và validation
- Hiểu Dependency Injection system của FastAPI (tương đương NestJS DI)
- Xử lý responses: response models, status codes, custom errors
- So sánh Express/NestJS patterns với FastAPI equivalents

**Phạm vi 2 giờ:** Day 13 chỉ cần routing, validation, response model, error handling cơ bản, và dependency basics với `Annotated[..., Depends(...)]`. Auth/JWT, refresh token, role guard, SQLAlchemy integration, và Alembic chỉ là preview; phần triển khai đầy đủ thuộc Day 14-15.

---

## 🔄 So sánh Express/NestJS vs FastAPI

| Tính năng | Express/NestJS (TypeScript) | FastAPI (Python) |
|---|---|---|
| **Basic route** | `@Get('/users')` / `app.get('/users', handler)` | `@app.get("/users")` |
| **Path params** | `@Param('id') id: string` / `req.params.id` | `user_id: int = Path(gt=0)` |
| **Query params** | `@Query('skip') skip: number` / `req.query.skip` | `skip: int = Query(ge=0, default=0)` |
| **Request body** | `@Body() dto: CreateUserDto` / `req.body` | `user: UserCreate` (Pydantic model) |
| **Validation** | `class-validator` decorators | Pydantic validators, `Field(...)` |
| **Middleware** | `app.use(middleware)` | `app.add_middleware(MiddlewareClass)` |
| **DI (injectable)** | `@Injectable()` + constructor injection | `Depends(dependency_function)` |
| **Response type** | `Promise<UserDto>` + `@SerializeGroup` | `response_model=UserResponse` |
| **API Docs** | Swagger với `@nestjs/swagger` | Built-in Swagger (/docs) + ReDoc (/redoc) |
| **Startup/Shutdown** | `onModuleInit()` / `onModuleDestroy()` | `lifespan` context manager |
| **Error handling** | `ExceptionFilter` / Express error middleware | `HTTPException` + `exception_handler` |
| **Status code** | `@HttpCode(201)` | `status_code=status.HTTP_201_CREATED` |
| **Performance** | ~50k req/s (raw) | ~100k req/s (raw, async) |
| **Type checking** | TypeScript compiler | Pydantic runtime + mypy |

---

## 📖 Lý thuyết

### Section 1: Basic FastAPI App với Lifespan

**Cài đặt:**

```bash
uv add fastapi uvicorn[standard] pydantic
```

**Chạy server:**

```bash
# Development (auto-reload)
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**App cơ bản với lifespan:**

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager thay thế @app.on_event("startup") và @app.on_event("shutdown")
    cho startup/shutdown logic.

    Tương đương NestJS:
    async onModuleInit() { ... }     <- Code trước yield
    async onModuleDestroy() { ... }  <- Code sau yield
    """
    # === STARTUP ===
    logger.info("Application starting up...")
    # Day 13 chỉ setup app-level state nhẹ.
    # Database/Redis lifecycle sẽ được triển khai ở Day 15.
    app.state.version = "1.0.0"

    yield  # <-- App chạy ở đây

    # === SHUTDOWN ===
    logger.info("Application shutting down...")
    # Close shared clients/resources tại đây khi app có DB/Redis ở Day 15.


# Khởi tạo app
app = FastAPI(
    title="My Blog API",
    description="Blog API built with FastAPI",
    version="1.0.0",
    lifespan=lifespan,
    # Docs URLs (có thể disable trong production)
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc
    openapi_url="/openapi.json",
)

# CORS middleware - tương đương cors package trong Express
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://myapp.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": app.version,
    }


# Include routers
from src.routers import users, posts
app.include_router(users.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
```

**Router module:**

```python
# src/routers/users.py
from fastapi import APIRouter

router = APIRouter(
    prefix="/users",
    tags=["Users"],  # Nhóm trong Swagger UI
    responses={404: {"description": "User not found"}},  # Common responses
)

@router.get("/")
async def list_users(): ...

@router.get("/{user_id}")
async def get_user(user_id: int): ...
```

---

### Section 2: Routing - Parameters và Validation

**Pydantic Models cho request/response:**

```python
# src/schemas.py
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
from typing import Annotated
from datetime import datetime


# Request schemas (input)
class UserCreate(BaseModel):
    name: Annotated[str, Field(
        min_length=2,
        max_length=100,
        description="Tên người dùng",
        examples=["Nguyen Van A"],
    )]
    email: Annotated[str, Field(
        pattern=r"^[^@]+@[^@]+\.[^@]+$",
        description="Email address",
    )]
    age: Annotated[int, Field(ge=0, le=150, description="Tuổi")] = 0
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        """Tự động chuyển email thành lowercase."""
        return v.lower()

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        """Loại bỏ khoảng trắng thừa."""
        return v.strip()


class UserUpdate(BaseModel):
    name: Annotated[str | None, Field(None, min_length=2, max_length=100)] = None
    age: Annotated[int | None, Field(None, ge=0, le=150)] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        """Phải có ít nhất 1 field để update."""
        if self.name is None and self.age is None:
            raise ValueError("At least one field must be provided for update")
        return self


# Response schemas (output)
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int
    is_active: bool
    created_at: datetime

    # from_attributes=True: cho phép tạo từ SQLAlchemy model objects
    # Tương đương plainToInstance(UserDto, entity) trong NestJS class-transformer
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    skip: int
    limit: int
```

**Route definitions đầy đủ:**

```python
# src/routers/users.py
from fastapi import APIRouter, Path, Query, HTTPException, status, Body
from pydantic import BaseModel, Field
from typing import Annotated
from src.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse

router = APIRouter(prefix="/users", tags=["Users"])

# Tái sử dụng type aliases
UserIdPath = Annotated[int, Path(
    gt=0,
    description="User ID phải là số nguyên dương",
    examples=[1, 42, 100],
)]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Lấy thông tin user",
    description="Lấy thông tin chi tiết của một user theo ID.",
)
async def get_user(user_id: UserIdPath):
    """
    Tương đương Express:
    app.get('/users/:userId', async (req, res) => {
        const user = await findUser(req.params.userId);
        if (!user) return res.status(404).json({ message: 'Not found' });
        res.json(user);
    });
    """
    user = await find_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return user


@router.get(
    "",
    response_model=UserListResponse,
    summary="Lấy danh sách users với pagination",
)
async def list_users(
    skip: Annotated[int, Query(ge=0, description="Số records bỏ qua")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Số records trả về")] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_active: Annotated[bool | None, Query()] = None,
):
    """
    Tương đương Express:
    app.get('/users', async (req, res) => {
        const { skip = 0, limit = 20, search, is_active } = req.query;
        ...
    });
    """
    users = await search_users(skip=skip, limit=limit, query=search, active=is_active)
    total = await count_users(query=search, active=is_active)
    return {"items": users, "total": total, "skip": skip, "limit": limit}


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo user mới",
)
async def create_user(
    user: UserCreate,
    # Body() với embed=True khi muốn { "user": {...} } thay vì {...}
    # user: Annotated[UserCreate, Body(embed=True)],
):
    """
    Request body được validate tự động bởi Pydantic.
    Trả về 422 nếu validation fail (tương đương class-validator trong NestJS).
    """
    existing = await get_user_by_email(user.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Email already exists", "field": "email"},
        )
    new_user = await create_user_in_db(user)
    return new_user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Cập nhật toàn bộ user",
)
async def update_user(
    user_id: UserIdPath,
    user: UserCreate,
    notify: Annotated[bool, Query(description="Gửi email thông báo")] = False,
):
    """PUT: update toàn bộ resource (replace)."""
    existing = await find_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    updated = await update_user_in_db(user_id, user.model_dump())
    if notify:
        await send_notification_email(existing.email, "Your profile was updated")
    return updated


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Cập nhật một phần user",
)
async def partial_update_user(user_id: UserIdPath, update: UserUpdate):
    """PATCH: update một phần resource (partial update)."""
    existing = await find_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # model_dump(exclude_unset=True): chỉ lấy fields được truyền vào
    # Tương đương: {...existingUser, ...updateDto} trong TypeScript
    update_data = update.model_dump(exclude_unset=True)
    return await update_user_in_db(user_id, update_data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa user",
)
async def delete_user(user_id: UserIdPath):
    """204 No Content: không trả về body."""
    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user_from_db(user_id)
    # Không return gì - FastAPI tự trả về 204
```

**Multiple response types:**

```python
from fastapi.responses import JSONResponse, Response
from typing import Union


@router.get(
    "/{user_id}/export",
    responses={
        200: {"content": {"application/json": {}, "text/csv": {}}},
        404: {"model": ErrorResponse},
    },
)
async def export_user(
    user_id: int,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
):
    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")

    if format == "csv":
        csv_data = f"id,name,email\n{user.id},{user.name},{user.email}"
        return Response(content=csv_data, media_type="text/csv")

    return user  # FastAPI tự serialize
```

---

### Section 3: Dependency Injection System

FastAPI DI system tương đương NestJS `@Injectable()` nhưng function-based và flexible hơn.

> **Must Learn:** dependency là function nhận input và trả output. Day 13 chỉ dùng dependency cho settings, pagination, fake current user, và service in-memory. Auth/JWT, database session, repository injection, role guard sẽ học ở Day 14-15.

**Dependency cơ bản cho settings và pagination:**

```python
# src/dependencies.py
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status


@dataclass(frozen=True)
class Settings:
    app_name: str = "Learning API"
    debug: bool = True


def get_settings() -> Settings:
    # Trong app thật có thể dùng pydantic-settings, nhưng Day 13 giữ đơn giản.
    return Settings()


class Pagination:
    """
    Class-based dependency cho query params.
    FastAPI tự đọc skip/limit từ query string.
    """
    def __init__(
        self,
        skip: Annotated[int, Query(ge=0, description="Số records bỏ qua")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="Số records trả về")] = 20,
    ) -> None:
        self.skip = skip
        self.limit = limit


PaginationDep = Annotated[Pagination, Depends()]
SettingsDep = Annotated[Settings, Depends(get_settings)]
```

**Dependency lồng nhau và fake auth để hiểu cú pháp:**

```python
async def get_current_user_id(
    x_demo_user_id: Annotated[int | None, Header()] = None,
) -> int:
    """
    Demo dependency cho Day 13.
    Đây KHÔNG phải JWT auth. Header x-demo-user-id chỉ giúp học Depends().
    """
    if x_demo_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-demo-user-id header",
        )
    return x_demo_user_id


CurrentUserId = Annotated[int, Depends(get_current_user_id)]
```

**Sử dụng dependencies trong routes:**

```python
# src/routers/todos.py
from typing import Annotated

from fastapi import APIRouter, Depends

from src.dependencies import CurrentUserId, PaginationDep, SettingsDep
from src.schemas import TodoCreate, TodoResponse, TodoListResponse
from src.services import TodoService, get_todo_service

router = APIRouter(prefix="/todos", tags=["Todos"])
TodoServiceDep = Annotated[TodoService, Depends(get_todo_service)]


@router.get("", response_model=TodoListResponse)
async def list_todos(
    pagination: PaginationDep,
    settings: SettingsDep,
    service: TodoServiceDep,
):
    return await service.list(skip=pagination.skip, limit=pagination.limit)


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(
    payload: TodoCreate,
    current_user_id: CurrentUserId,
    service: TodoServiceDep,
):
    return await service.create(owner_id=current_user_id, payload=payload)
```

**Ghi nhớ:** `Depends()` không phải DI container như NestJS. Nó là dependency graph per-request: FastAPI gọi function, cache kết quả trong request, rồi truyền kết quả vào route handler.

---

### Section 4: Response Handling và Error Responses

**Custom exception handlers:**

```python
# src/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


class AppException(Exception):
    """Base exception cho application."""
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ResourceNotFoundError(AppException):
    def __init__(self, resource: str, id: int | str):
        super().__init__(
            message=f"{resource} with id '{id}' not found",
            code="RESOURCE_NOT_FOUND",
            status_code=404,
        )


class DuplicateResourceError(AppException):
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            message=f"{resource} with {field}='{value}' already exists",
            code="DUPLICATE_RESOURCE",
            status_code=409,
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register tất cả exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """
        Custom format cho Pydantic validation errors.
        Default FastAPI trả về 422 với format Pydantic.
        Ta format lại cho đẹp hơn.
        """
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"] if loc != "body"),
                "message": error["msg"],
                "type": error["type"],
            })
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler - tránh leak internal errors."""
        import logging
        logging.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
```

**Response model options:**

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class UserWithPassword(BaseModel):
    id: int
    name: str
    email: str
    password_hash: str  # Không muốn return field này


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    bio: str | None = None
    model_config = {"from_attributes": True}


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    # response_model_exclude_unset=True: chỉ trả về fields được set
    # response_model_exclude_none=True: loại bỏ fields có giá trị None
    response_model_exclude_none=True,
)
async def get_user(user_id: int):
    user = await find_user(user_id)
    # Dù UserWithPassword có password_hash,
    # response_model=UserResponse sẽ filter nó ra
    return user


# Response với headers tùy chỉnh
from fastapi import Response


@router.get("/users", response_model=list[UserResponse])
async def list_users(response: Response, skip: int = 0, limit: int = 20):
    users = await get_users(skip=skip, limit=limit)
    total = await count_users()

    # Thêm custom header
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Size"] = str(limit)

    return users


# JSONResponse khi cần control hoàn toàn
from fastapi.responses import JSONResponse


@router.post("/webhook", status_code=200)
async def webhook(payload: dict):
    # Process webhook...
    return JSONResponse(
        status_code=200,
        content={"received": True},
        headers={"X-Webhook-Received": "true"},
    )
```


---

## ⚠️ Common Mistakes

### 1. Quên `async` với I/O calls

```python
import httpx

# SAI
@app.get("/users/{id}")
def get_user(id: int):
    data = httpx.get(f"https://api.example.com/users/{id}")  # Block event loop worker
    return data.json()

# ĐÚNG
@app.get("/users/{id}")
async def get_user(id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{id}")
    return response.json()
```

### 2. Trả raw dict có sensitive field thay vì response model

```python
# SAI: Không có response_model nên password_hash có thể leak
@app.get("/users/{id}")
async def get_user(id: int):
    return {
        "id": id,
        "email": "alice@example.com",
        "password_hash": "$2b$12$...",
    }

# ĐÚNG: Dùng response_model để filter output
class UserResponse(BaseModel):
    id: int
    email: str

@app.get("/users/{id}", response_model=UserResponse)
async def get_user(id: int):
    return {
        "id": id,
        "email": "alice@example.com",
        "password_hash": "$2b$12$...",
    }
```

### 3. Nhầm lẫn Path vs Query parameter

```python
# Path parameter: /users/123
@app.get("/users/{user_id}")
async def get_user(user_id: int): ...  # user_id từ URL path

# Query parameter: /users?skip=10&limit=20
@app.get("/users")
async def list_users(skip: int = 0, limit: int = 20): ...  # từ query string

# Body parameter: cần Pydantic model hoặc Body()
@app.post("/users")
async def create_user(user: UserCreate): ...  # từ request body
```

### 4. Không dùng `response_model_exclude_none` dẫn đến leak sensitive data

```python
user = {
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com",
    "password_hash": "$2b$12$...",
}

# SAI: Không có response_model
@app.get("/users/{id}")
async def get_user(id: int):
    return user  # Trả về cả password_hash!

# ĐÚNG: response_model filter fields
class UserResponse(BaseModel):
    id: int
    name: str
    email: str

@app.get("/users/{id}", response_model=UserResponse)
async def get_user(id: int):
    return user  # password_hash bị filter bởi response_model
```

### 5. Blocking code trong async endpoint

```python
import time

# SAI: time.sleep block event loop
@app.get("/slow")
async def slow_endpoint():
    time.sleep(5)  # Block toàn bộ event loop!
    return {"done": True}

# ĐÚNG: asyncio.sleep
import asyncio

@app.get("/slow")
async def slow_endpoint():
    await asyncio.sleep(5)  # Yield control, không block
    return {"done": True}

# ĐÚNG: Chạy blocking code trong thread pool
import asyncio
from fastapi.concurrency import run_in_threadpool

@app.get("/compute")
async def compute():
    result = await run_in_threadpool(expensive_cpu_bound_function)
    return {"result": result}
```

### 6. Không validate Path parameters

```python
# SAI: user_id có thể là 0 hoặc âm
@app.get("/users/{user_id}")
async def get_user(user_id: int): ...

# ĐÚNG: Thêm validation
@app.get("/users/{user_id}")
async def get_user(
    user_id: Annotated[int, Path(gt=0, description="Must be positive")]
): ...
```

---

## ✅ Best Practices

**1. Organize bằng APIRouter - tránh flat file:**

```python
# src/routers/__init__.py
from src.routers.users import router as users_router
from src.routers.posts import router as posts_router
from src.routers.auth import router as auth_router

# main.py
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(posts_router, prefix="/api/v1/posts", tags=["Posts"])
```

**2. Tách request/response schemas:**

```python
# Tốt: Separate schemas cho input/output/DB
class UserCreate(BaseModel): ...        # Input (password included)
class UserUpdate(BaseModel): ...        # Partial input
class UserInDB(UserCreate): ...         # DB representation
class UserResponse(BaseModel): ...      # Output (no password)
class UserWithPostsResponse(UserResponse): ...  # Extended output
```

**3. Dùng `Annotated` cho reusable parameters:**

```python
# Định nghĩa một lần, dùng nhiều nơi
from typing import Annotated
from fastapi import Path, Query

PositiveIntPath = Annotated[int, Path(gt=0)]
PaginationSkip = Annotated[int, Query(ge=0, description="Records to skip")]
PaginationLimit = Annotated[int, Query(ge=1, le=100, description="Max records")]
```

**4. Versioning với prefix:**

```python
# v1 và v2 có thể chạy song song
app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
```

**5. Sử dụng `model_dump(exclude_unset=True)` cho PATCH:**

```python
@router.patch("/{id}", response_model=UserResponse)
async def partial_update(id: int, update: UserUpdate):
    user = await find_user(id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Chỉ update fields được truyền vào, không overwrite với None
    for field, value in update.model_dump(exclude_unset=True).items():
        user[field] = value
    return user
```

---

## ⚖️ Trade-offs

### FastAPI vs Flask

| | FastAPI | Flask |
|---|---|---|
| **Async** | Native | Cần flask-async hoặc Quart |
| **Validation** | Pydantic built-in | Cần marshmallow/wtforms |
| **API Docs** | Built-in Swagger + ReDoc | Cần flasgger |
| **Learning curve** | Trung bình | Thấp |
| **Performance** | Cao (ASGI) | Trung bình (WSGI) |
| **Flexibility** | Trung bình | Cao |
| **Ecosystem** | Đang phát triển | Rất lớn |

### FastAPI vs Django REST Framework

| | FastAPI | Django REST Framework |
|---|---|---|
| **ORM** | Tự chọn (SQLAlchemy, Tortoise) | Django ORM (tích hợp) |
| **Admin** | Không có | Django Admin |
| **Auth** | Tự implement hoặc authlib | Built-in sessions + drf-simplejwt |
| **Async** | Native | Django 4.1+ async views |
| **Performance** | Cao hơn | Thấp hơn |
| **Full-stack** | Không | Có (templates, static files) |

---

## 🚀 Performance Notes

**1. Async everywhere:**

```bash
# Dùng uvicorn với uvloop (tốt hơn asyncio mặc định)
uv add uvicorn[standard]  # Bao gồm uvloop + httptools

# Production: gunicorn với uvicorn workers
uv add gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

**2. Response model caching:**

```python
# Pydantic v2 tự động cache model validators
# Định nghĩa models ở module level, không trong function
# SAI: tạo model mới mỗi request
@app.get("/users/{id}")
async def get_user(id: int):
    class TempResponse(BaseModel):  # Tạo mới mỗi lần gọi - chậm!
        id: int
        name: str
    ...

# ĐÚNG: Model ở module level
class UserResponse(BaseModel):  # Tạo 1 lần
    id: int
    name: str

@app.get("/users/{id}", response_model=UserResponse)
async def get_user(id: int): ...
```

**3. Reuse HTTP clients for outbound calls:**

```python
# Day 13 concept: lifespan giữ shared clients.
# Day 15 sẽ áp dụng cùng ý tưởng cho DB engine và Redis client.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=5.0)
    yield
    await app.state.http.aclose()
```

---

## 📝 Tóm tắt

| Tính năng | FastAPI |
|---|---|
| **GET route** | `@app.get("/path", response_model=Schema)` |
| **POST route** | `@app.post("/path", status_code=201)` |
| **Path param** | `id: Annotated[int, Path(gt=0)]` |
| **Query param** | `skip: int = Query(ge=0, default=0)` |
| **Body param** | `user: UserCreate` (Pydantic BaseModel) |
| **Header param** | `token: Annotated[str, Header()]` |
| **Dependency** | `settings: Annotated[Settings, Depends(get_settings)]` |
| **Demo header dependency** | `user_id: Annotated[int, Depends(get_current_user_id)]` |
| **HTTPException** | `raise HTTPException(status_code=404, detail="Not found")` |
| **Router** | `router = APIRouter(prefix="/users", tags=["Users"])` |
| **Include router** | `app.include_router(router, prefix="/api/v1")` |
| **Lifespan** | `@asynccontextmanager async def lifespan(app): ... yield ...` |
| **Validation model** | `class Schema(BaseModel): field: Annotated[type, Field(...)]` |
