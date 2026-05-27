# Ngày 13: Bài Tập FastAPI Cơ Bản

**Scope 2 giờ:** Bài 1 là primary lab. Bài 2 luyện validation/custom errors/dependency ở mức in-memory. Bài 3 là optional test flow cho FastAPI basic. JWT/OAuth2, database thật, Redis cache và pagination nâng cao chuyển sang Day 14-15.

## Bài 1 (Cơ bản): Todo CRUD API với In-Memory Storage

**Mục tiêu:** Xây dựng Todo CRUD API hoàn chỉnh với FastAPI, hiểu cách định nghĩa routes, Pydantic validation, và HTTP status codes.

**Setup:**

```bash
uv add fastapi uvicorn
```

**Yêu cầu - Tạo file `todo_api.py`:**

**Phần A - Pydantic Schemas:**

```python
# todo_api.py
from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from typing import Annotated
from datetime import datetime
from enum import Enum


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class TodoCreate(BaseModel):
    """Schema để tạo todo mới."""
    title: Annotated[str, Field(
        min_length=1,
        max_length=200,
        description="Tiêu đề của todo",
        examples=["Buy groceries", "Write documentation"],
    )]
    description: Annotated[str | None, Field(
        None,
        max_length=1000,
        description="Mô tả chi tiết",
    )] = None
    priority: Priority = Priority.medium
    due_date: datetime | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)


class TodoUpdate(BaseModel):
    """Schema để update todo - tất cả fields optional."""
    title: Annotated[str | None, Field(None, min_length=1, max_length=200)] = None
    description: str | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    tags: list[str] | None = None
    is_completed: bool | None = None


class TodoResponse(BaseModel):
    """Schema cho response."""
    id: int
    title: str
    description: str | None
    priority: Priority
    due_date: datetime | None
    tags: list[str]
    is_completed: bool
    created_at: datetime
    updated_at: datetime


class TodoListResponse(BaseModel):
    """Paginated list response."""
    items: list[TodoResponse]
    total: int
    skip: int
    limit: int
```

**Phần B - In-memory storage:**

```python
from threading import Lock

# In-memory "database"
_todos: dict[int, dict] = {}
_next_id: int = 1
_lock = Lock()  # Thread safety cho sync operations


def _get_next_id() -> int:
    global _next_id
    with _lock:
        current = _next_id
        _next_id += 1
        return current
```

**Phần C - App và Routes (cần implement):**

```python
app = FastAPI(
    title="Todo API",
    description="Simple Todo List API built with FastAPI",
    version="1.0.0",
)


@app.post("/todos", response_model=TodoResponse, status_code=201)
def create_todo(todo: TodoCreate):
    """
    TODO: Implement
    1. Tạo todo dict với id, title, description, priority, due_date, tags
    2. is_completed = False
    3. created_at = updated_at = datetime.now()
    4. Lưu vào _todos dict
    5. Return todo
    """
    raise NotImplementedError


@app.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(
    todo_id: Annotated[int, Path(gt=0, description="Todo ID")]
):
    """
    TODO: Implement
    1. Tìm todo trong _todos
    2. Raise HTTPException 404 nếu không tìm thấy
    3. Return todo
    """
    raise NotImplementedError


@app.get("/todos", response_model=TodoListResponse)
def list_todos(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    is_completed: bool | None = None,
    priority: Priority | None = None,
    search: Annotated[str | None, Query(min_length=1)] = None,
):
    """
    TODO: Implement với filtering và pagination
    1. Lấy tất cả todos từ _todos.values()
    2. Filter theo is_completed nếu được truyền vào
    3. Filter theo priority nếu được truyền vào
    4. Filter theo search (case-insensitive trong title và description) nếu được truyền vào
    5. Sort theo created_at descending
    6. Apply pagination (skip/limit)
    7. Return TodoListResponse với total = số items SAU khi filter, TRƯỚC khi paginate
    """
    raise NotImplementedError


@app.patch("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(
    todo_id: Annotated[int, Path(gt=0)],
    update: TodoUpdate,
):
    """
    TODO: Implement PATCH - partial update
    1. Tìm todo, raise 404 nếu không tìm thấy
    2. Dùng update.model_dump(exclude_unset=True) để chỉ update fields được truyền vào
    3. Set updated_at = datetime.now()
    4. Return updated todo
    """
    raise NotImplementedError


@app.put("/todos/{todo_id}/complete", response_model=TodoResponse)
def mark_complete(
    todo_id: Annotated[int, Path(gt=0)]
):
    """
    TODO: Implement - đánh dấu todo là hoàn thành
    Raise 404 nếu không tìm thấy
    Raise 409 nếu todo đã completed rồi
    """
    raise NotImplementedError


@app.put("/todos/{todo_id}/reopen", response_model=TodoResponse)
def reopen_todo(
    todo_id: Annotated[int, Path(gt=0)]
):
    """
    TODO: Implement - mở lại todo đã hoàn thành
    Raise 404 nếu không tìm thấy
    Raise 409 nếu todo chưa completed
    """
    raise NotImplementedError


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(
    todo_id: Annotated[int, Path(gt=0)]
):
    """
    TODO: Implement
    Raise 404 nếu không tìm thấy
    Return None (204 No Content)
    """
    raise NotImplementedError


@app.delete("/todos", status_code=204)
def clear_completed():
    """
    TODO: Implement - xóa tất cả todos đã hoàn thành
    """
    raise NotImplementedError


# Stats endpoint (bonus)
@app.get("/todos/stats/summary")
def get_stats():
    """
    TODO: Implement - trả về thống kê
    {
        "total": int,
        "completed": int,
        "pending": int,
        "by_priority": {"low": int, "medium": int, "high": int, "urgent": int},
        "overdue": int  # Số todos quá hạn (due_date < now và chưa completed)
    }
    """
    raise NotImplementedError
```

**Chạy và test:**

```bash
# Chạy server
uvicorn todo_api:app --reload

# Test với httpie (uv add httpie)
http POST localhost:8000/todos title="Buy milk" priority=high
http GET localhost:8000/todos
http GET "localhost:8000/todos?priority=high&is_completed=false"
http PATCH localhost:8000/todos/1 title="Buy milk and eggs"
http PUT localhost:8000/todos/1/complete
http GET localhost:8000/todos/stats/summary
http DELETE localhost:8000/todos/1

# Hoặc dùng curl
curl -X POST localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "priority": "high"}'
```

**Mở Swagger UI để test interactive:** http://localhost:8000/docs

**Tiêu chí hoàn thành:**
- [ ] Tất cả endpoints hoạt động đúng
- [ ] Validation trả về 422 với clear error messages
- [ ] Filtering và pagination hoạt động
- [ ] 404 khi không tìm thấy todo
- [ ] 409 khi mark complete todo đã complete
- [ ] 204 No Content cho DELETE
- [ ] Stats endpoint trả về đúng numbers

---

## Bài 2 (Trung bình): User API In-Memory với Validation và Dependency

**Mục tiêu:** Luyện Pydantic v2 request/response models, custom errors, `Depends()` và header dependency đơn giản. Không dùng JWT, SQLAlchemy, Alembic hoặc Redis trong Day 13.

**Setup:**

```bash
uv add fastapi uvicorn httpx pytest
```

**Yêu cầu:**
- Tạo `user_api.py` với `FastAPI(title="User API")`.
- Tạo `UserCreate`, `UserUpdate`, `UserResponse`, `UserListResponse`.
- Dùng `Field`, `field_validator`, `model_validator` để validate:
  - `email` lowercase và có format hợp lệ.
  - `username` chỉ gồm chữ, số, `_`, độ dài 3-30.
  - `UserUpdate` phải có ít nhất một field.
- Dùng in-memory dict làm storage.
- Tạo dependency `get_current_user_id` đọc header `x-demo-user-id`.
- Endpoint cần có:
  - `POST /users` tạo user, trả 201, không trả password.
  - `GET /users` có `skip`, `limit`, `search`.
  - `GET /users/{user_id}` trả 404 nếu không có.
  - `PATCH /users/{user_id}` chỉ cho update chính user demo, trả 403 nếu khác user.

**Expected output:**

```bash
uvicorn user_api:app --reload --port 8000

curl -X POST localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"ALICE@example.com","password":"secret123"}'
# {"id":1,"username":"alice","email":"alice@example.com","is_active":true}

curl localhost:8000/users/1
# {"id":1,"username":"alice","email":"alice@example.com","is_active":true}

curl -X PATCH localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -H "x-demo-user-id: 1" \
  -d '{"username":"alice_new"}'
# {"id":1,"username":"alice_new","email":"alice@example.com","is_active":true}
```

**Hint:**

```python
from typing import Annotated
from fastapi import Header, HTTPException, status


async def get_current_user_id(
    x_demo_user_id: Annotated[int | None, Header()] = None,
) -> int:
    if x_demo_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing x-demo-user-id")
    return x_demo_user_id
```

**Chạy kiểm tra:**

```bash
uvicorn user_api:app --reload --port 8000
pytest -q
```

---

## Bài 3 (Nâng cao / Optional): Test FastAPI Basic Flow

**Mục tiêu:** Viết test cho API ở Bài 2 bằng `TestClient`, kiểm tra validation, status codes và dependency override. Đây vẫn là FastAPI basic, không chuyển sang auth thật hoặc database.

**Yêu cầu:**
- Tạo `test_user_api.py`.
- Test các case:
  - Create user thành công trả 201 và response không có `password`.
  - Email invalid trả 422.
  - Duplicate email trả 409.
  - `GET /users/{id}` không tồn tại trả 404.
  - `PATCH /users/{id}` thiếu `x-demo-user-id` trả 401.
  - `PATCH /users/{id}` với user khác trả 403.
  - `PATCH /users/{id}` đúng user trả 200.
- Dùng fixture để reset in-memory storage trước mỗi test.

**Expected output:**

```bash
pytest -q test_user_api.py
# 7 passed
```

**Hint:**

```python
import pytest
from fastapi.testclient import TestClient
from user_api import app, users_db


@pytest.fixture(autouse=True)
def clear_users():
    users_db.clear()
    yield
    users_db.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
```

## 🔍 Gợi ý kiểm tra kết quả

```bash
uvicorn todo_api:app --reload --port 8000
curl localhost:8000/docs

uvicorn user_api:app --reload --port 8001
pytest -q
```

Nếu Bài 1 chạy được và Bài 2 có đủ validation/status code, Day 13 đạt mục tiêu. JWT/OAuth2, SQLAlchemy session, Redis cache, WebSocket và BackgroundTasks chuyển sang Day 14-15.
