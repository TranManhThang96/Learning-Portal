# Ngày 13: Tài Liệu Tham Khảo - FastAPI Cơ Bản

## Tài liệu chính thức

### FastAPI
- **Official Docs**: https://fastapi.tiangolo.com/
- **Tutorial**: https://fastapi.tiangolo.com/tutorial/
- **Advanced User Guide**: https://fastapi.tiangolo.com/advanced/
- **Path Parameters**: https://fastapi.tiangolo.com/tutorial/path-params/
- **Query Parameters**: https://fastapi.tiangolo.com/tutorial/query-params/
- **Request Body**: https://fastapi.tiangolo.com/tutorial/body/
- **Body - Fields**: https://fastapi.tiangolo.com/tutorial/body-fields/
- **Dependencies**: https://fastapi.tiangolo.com/tutorial/dependencies/
- **Security**: https://fastapi.tiangolo.com/tutorial/security/
- **Middleware**: https://fastapi.tiangolo.com/tutorial/middleware/
- **Background Tasks**: https://fastapi.tiangolo.com/tutorial/background-tasks/
- **Testing**: https://fastapi.tiangolo.com/tutorial/testing/

### Pydantic v2
- **Official Docs**: https://docs.pydantic.dev/latest/
- **Models**: https://docs.pydantic.dev/latest/concepts/models/
- **Fields**: https://docs.pydantic.dev/latest/concepts/fields/
- **Validators**: https://docs.pydantic.dev/latest/concepts/validators/
- **Config**: https://docs.pydantic.dev/latest/concepts/config/
- **Serialization**: https://docs.pydantic.dev/latest/concepts/serialization/

### Starlette (FastAPI base framework)
- **Docs**: https://www.starlette.io/
- **Middleware**: https://www.starlette.io/middleware/
- **Responses**: https://www.starlette.io/responses/
- **Routing**: https://www.starlette.io/routing/

### Uvicorn
- **Docs**: https://www.uvicorn.org/
- **Deployment**: https://www.uvicorn.org/deployment/

---

## Quick Reference

### FastAPI App Setup

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="API Name",
    description="API Description",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
```

### Route Decorators

```python
@app.get("/path")        # GET
@app.post("/path")       # POST
@app.put("/path")        # PUT
@app.patch("/path")      # PATCH
@app.delete("/path")     # DELETE
@app.options("/path")    # OPTIONS
@app.head("/path")       # HEAD
```

### Parameter Types

```python
from fastapi import Path, Query, Header, Cookie, Form, File, UploadFile
from typing import Annotated

# Path parameter
user_id: Annotated[int, Path(gt=0, description="User ID")]

# Query parameter
skip: Annotated[int, Query(ge=0, default=0)]

# Header
token: Annotated[str | None, Header()] = None

# Cookie
session: Annotated[str | None, Cookie()] = None

# Form data (cần python-multipart)
username: Annotated[str, Form()]

# File upload
file: Annotated[UploadFile, File()]
```

### Pydantic Field Validators

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated


class MyModel(BaseModel):
    # Field constraints
    name: Annotated[str, Field(min_length=2, max_length=100)]
    age: Annotated[int, Field(ge=0, lt=150)]
    email: Annotated[str, Field(pattern=r"^[^@]+@[^@]+$")]
    tags: list[str] = Field(default_factory=list, max_length=10)

    # Field-level validator
    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.lower()

    # Model-level validator (cross-field)
    @model_validator(mode="after")
    def validate_all(self) -> "MyModel":
        if self.some_condition:
            raise ValueError("Invalid combination")
        return self

    # From ORM objects
    model_config = {"from_attributes": True}
```

### Dependency Injection Patterns

```python
from dataclasses import dataclass
from fastapi import Depends, Header
from typing import Annotated

# Simple dependency
@dataclass(frozen=True)
class Settings:
    app_name: str = "Learning API"

def get_settings() -> Settings:
    return Settings()

# Type alias
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Dependency with dependencies
async def get_current_user_id(
    x_demo_user_id: Annotated[int | None, Header()] = None,
) -> int | None:
    return x_demo_user_id

CurrentUserId = Annotated[int | None, Depends(get_current_user_id)]

# Class-based dependency
class Pagination:
    def __init__(self, skip: int = 0, limit: int = 20):
        self.skip = skip
        self.limit = limit

PaginationDep = Annotated[Pagination, Depends()]

# Usage
@app.get("/items")
async def list_items(
    settings: SettingsDep,
    user_id: CurrentUserId,
    p: PaginationDep,
): ...
```

### HTTP Status Codes

```python
from fastapi import status

status.HTTP_200_OK           # 200
status.HTTP_201_CREATED      # 201
status.HTTP_204_NO_CONTENT   # 204
status.HTTP_400_BAD_REQUEST  # 400
status.HTTP_401_UNAUTHORIZED # 401
status.HTTP_403_FORBIDDEN    # 403
status.HTTP_404_NOT_FOUND    # 404
status.HTTP_409_CONFLICT     # 409
status.HTTP_422_UNPROCESSABLE_ENTITY  # 422 (validation)
status.HTTP_500_INTERNAL_SERVER_ERROR # 500
```

### Common Response Patterns

```python
from fastapi.responses import JSONResponse, Response, FileResponse, StreamingResponse

# Thêm custom header
@app.get("/items")
async def list_items(response: Response):
    response.headers["X-Total-Count"] = "100"
    return items

# JSONResponse với custom status
return JSONResponse(status_code=200, content={"key": "value"})

# No content
return Response(status_code=204)

# File download
return FileResponse("file.pdf", media_type="application/pdf")
```

---

## Testing FastAPI

```python
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

# Sync test client
client = TestClient(app)
response = client.get("/users/1")
assert response.status_code == 200
assert response.json()["id"] == 1

# Async test client
@pytest.mark.asyncio
async def test_async():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/users/1")
    assert response.status_code == 200

# Override dependency cho testing
def override_settings():
    return Settings(app_name="Test API")

app.dependency_overrides[get_settings] = override_settings
# Cleanup sau test
app.dependency_overrides.clear()
```

---

## Công cụ test HTTP

### HTTPie (uv add httpie)

```bash
# GET
http GET localhost:8000/users
http localhost:8000/users/1  # GET là default

# POST với JSON body
http POST localhost:8000/users name="Alice" email="alice@test.com"

# POST với JSON body explicit
http POST localhost:8000/users Content-Type:application/json \
  <<< '{"name": "Alice", "email": "alice@test.com"}'

# Với Authorization header
http GET localhost:8000/protected "Authorization: Bearer <token>"

# Query params
http GET "localhost:8000/users?skip=0&limit=10"

# PATCH
http PATCH localhost:8000/users/1 name="Alice Updated"

# DELETE
http DELETE localhost:8000/users/1
```

### curl

```bash
# GET
curl localhost:8000/users

# POST JSON
curl -X POST localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@test.com"}'

# Với Bearer token
curl localhost:8000/protected \
  -H "Authorization: Bearer <token>"

# PATCH
curl -X PATCH localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Updated"}'

# Verbose output
curl -v localhost:8000/users/1
```

---

## Packages dùng trong Day 13

> Day 13 chỉ cần FastAPI/Pydantic/httpx cơ bản. Auth/JWT/hash/SQLAlchemy/Redis nằm ở Day 14-15 để tránh overlap.

| Package | Mục đích | Install |
|---|---|---|
| `python-multipart` | Form data + file upload | `uv add python-multipart` |
| `httpx` | HTTP client + async testing | `uv add httpx` |
| `aiofiles` | Async file I/O | `uv add aiofiles` |
| `python-dotenv` | Load .env files | `uv add python-dotenv` |

---

## So sánh NestJS patterns với FastAPI

| NestJS | FastAPI |
|---|---|
| `@Controller('/users')` | `router = APIRouter(prefix="/users")` |
| `@Injectable()` service | Regular class, injected via `Depends()` |
| `@UseGuards(AuthGuard)` | `user: Annotated[User, Depends(get_current_user)]` |
| `@UsePipes(ValidationPipe)` | Tự động với Pydantic |
| `@UseInterceptors(...)` | Middleware hoặc custom `Depends()` |
| `@Roles('admin')` | `Depends(require_role("admin"))` |
| `dto.toPlainObject()` | `schema.model_dump()` |
| `plainToInstance(Dto, obj)` | `DtoClass.model_validate(obj)` |
| `@ApiProperty()` | `Field(description="...")` |
| `@ApiResponse({status: 200})` | `@app.get(..., responses={200: {...}})` |
| Module system | `app.include_router(...)` |

---

## Bài đọc thêm

- **FastAPI Best Practices**: https://github.com/zhanymkanov/fastapi-best-practices
- **Full Stack FastAPI PostgreSQL Template**: https://github.com/tiangolo/full-stack-fastapi-postgresql
- **Real World FastAPI**: https://github.com/nsidnev/fastapi-realworld-example-app
- **Pydantic v2 Migration Guide**: https://docs.pydantic.dev/latest/migration/
