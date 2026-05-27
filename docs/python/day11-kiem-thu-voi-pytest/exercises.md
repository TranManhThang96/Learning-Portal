# Ngày 11: Bài Tập Testing

**Scope 2 giờ:** hoàn thành Bài 1 trước. Bài 2 chỉ cần 3-5 test đại diện nếu còn thời gian. Bài 3 là optional/deep dive cho async DB và mocking external services.

## Bài 1 (Cơ bản): Test Suite cho Calculator Class

**Mục tiêu:** Viết test suite đầy đủ cho một Calculator class với pytest, bao gồm fixtures, parametrize và kiểm tra exceptions.

**Yêu cầu:**

Tạo file `src/calculator.py` với class sau:

```python
# src/calculator.py
from typing import Union

Number = Union[int, float]


class Calculator:
    """Simple calculator with history tracking."""

    def __init__(self) -> None:
        self.history: list[dict] = []

    def add(self, a: Number, b: Number) -> Number:
        result = a + b
        self._record("add", a, b, result)
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        result = a - b
        self._record("subtract", a, b, result)
        return result

    def multiply(self, a: Number, b: Number) -> Number:
        result = a * b
        self._record("multiply", a, b, result)
        return result

    def divide(self, a: Number, b: Number) -> float:
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        result = a / b
        self._record("divide", a, b, result)
        return result

    def power(self, base: Number, exp: Number) -> Number:
        if exp < 0:
            raise ValueError("Negative exponent not supported")
        result = base ** exp
        self._record("power", base, exp, result)
        return result

    def sqrt(self, n: Number) -> float:
        if n < 0:
            raise ValueError("Cannot take square root of negative number")
        result = n ** 0.5
        self._record("sqrt", n, None, result)
        return result

    def get_history(self) -> list[dict]:
        return self.history.copy()

    def clear_history(self) -> None:
        self.history.clear()

    def _record(self, op: str, a: Number, b: Number | None, result: Number) -> None:
        self.history.append({
            "operation": op,
            "a": a,
            "b": b,
            "result": result,
        })
```

**Viết tests trong `tests/test_calculator.py`:**

**Phần A - Basic tests:**

```python
# Gợi ý cấu trúc
import pytest
from src.calculator import Calculator


@pytest.fixture
def calc() -> Calculator:
    """Fresh Calculator instance cho mỗi test."""
    return Calculator()


class TestAdd:
    def test_add_two_positives(self, calc): ...
    def test_add_positive_negative(self, calc): ...
    def test_add_floats(self, calc): ...
    def test_add_records_history(self, calc): ...
```

**Phần B - Parametrize:**

```python
@pytest.mark.parametrize("a, b, expected", [
    (2, 3, 5),
    (-1, 1, 0),
    (0, 0, 0),
    (1.5, 2.5, 4.0),
    (-5, -3, -8),
])
def test_add_parametrized(calc, a, b, expected):
    assert calc.add(a, b) == pytest.approx(expected)
```

**Phần C - Exception testing:**

```python
def test_divide_by_zero_raises(calc):
    with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
        calc.divide(10, 0)

# Tương tự cho power với exp < 0 và sqrt với n < 0
```

**Phần D - History tracking:**

```python
def test_history_records_operations(calc):
    calc.add(2, 3)
    calc.multiply(4, 5)
    history = calc.get_history()
    assert len(history) == 2
    assert history[0]["operation"] == "add"
    assert history[0]["result"] == 5

def test_clear_history(calc):
    calc.add(1, 2)
    calc.clear_history()
    assert calc.get_history() == []

def test_history_is_copy(calc):
    # Đảm bảo get_history() trả về copy, không phải reference
    history = calc.get_history()
    history.append({"fake": True})
    assert len(calc.get_history()) == 0
```

**Tiêu chí hoàn thành:**
- [ ] Tối thiểu 20 test cases
- [ ] Tất cả operations được test (add, subtract, multiply, divide, power, sqrt)
- [ ] Coverage cho src/calculator.py >= 95%
- [ ] Dùng parametrize cho ít nhất 2 operations
- [ ] Test tất cả exception cases
- [ ] Test history tracking

**Chạy để kiểm tra:**

```bash
uv run pytest tests/test_calculator.py -v --cov=src/calculator --cov-report=term-missing
```

---

## Bài 2 (Trung bình): Test FastAPI Endpoint với TestClient và Mocking

**Mục tiêu:** Viết tests cho FastAPI endpoints, mock database dependencies, test validation errors và authentication.

**Setup:**

```bash
uv add fastapi httpx pytest pytest-mock sqlalchemy aiosqlite
```

**Code cần test - `src/main.py`:**

```python
# src/main.py
from fastapi import FastAPI, HTTPException, Depends, status, Header
from pydantic import BaseModel, Field, EmailStr
from typing import Annotated
import hashlib


app = FastAPI(title="User API")


# --- Models ---
class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool = True


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    is_active: bool | None = None


# --- In-memory "database" ---
_users_db: dict[int, dict] = {}
_next_id = 1


# --- Dependencies ---
def get_db() -> dict:
    return _users_db


def get_current_user(
    authorization: Annotated[str | None, Header()] = None
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = authorization.removeprefix("Bearer ")
    # Simplified: token = user_id
    user_id = int(token) if token.isdigit() else None
    if user_id is None or user_id not in _users_db:
        raise HTTPException(status_code=401, detail="Invalid token")
    return _users_db[user_id]


# --- Routes ---
@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: dict = Depends(get_db)):
    global _next_id
    # Check duplicate email
    for existing in db.values():
        if existing["email"] == user.email:
            raise HTTPException(status_code=409, detail="Email already exists")

    new_user = {
        "id": _next_id,
        "name": user.name,
        "email": user.email,
        "password_hash": hashlib.sha256(user.password.encode()).hexdigest(),
        "is_active": True,
    }
    db[_next_id] = new_user
    _next_id += 1
    return new_user


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: dict = Depends(get_db)):
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    return db[user_id]


@app.get("/users", response_model=list[UserResponse])
def list_users(db: dict = Depends(get_db)):
    return list(db.values())


@app.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: dict = Depends(get_db),
):
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Cannot update other users")

    user = db[user_id]
    if update.name is not None:
        user["name"] = update.name
    if update.is_active is not None:
        user["is_active"] = update.is_active
    return user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: dict = Depends(get_db),
):
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Cannot delete other users")
    del db[user_id]
```

**Nhiệm vụ - viết `tests/test_main.py`:**

**Phần A - Setup và fixtures:**

```python
import pytest
from fastapi.testclient import TestClient
from src.main import app, _users_db, get_db


@pytest.fixture(autouse=True)
def clear_db():
    """Reset database và counter trước mỗi test."""
    import src.main as main_module
    main_module._users_db.clear()
    main_module._next_id = 1
    yield
    main_module._users_db.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_user(client):
    """Tạo một user mẫu và trả về response data."""
    response = client.post("/users", json={
        "name": "Alice",
        "email": "alice@example.com",
        "password": "password123",
    })
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(sample_user):
    """Header với token của sample_user."""
    return {"Authorization": f"Bearer {sample_user['id']}"}
```

**Phần B - Tests cần viết:**

```python
class TestCreateUser:
    def test_create_valid_user(self, client): ...
    def test_create_returns_201(self, client): ...
    def test_response_excludes_password(self, client): ...
    def test_duplicate_email_returns_409(self, client, sample_user): ...
    def test_invalid_email_returns_422(self, client): ...
    def test_short_name_returns_422(self, client): ...
    def test_short_password_returns_422(self, client): ...

class TestGetUser:
    def test_get_existing_user(self, client, sample_user): ...
    def test_get_nonexistent_returns_404(self, client): ...
    def test_list_users_empty(self, client): ...
    def test_list_users_after_creation(self, client, sample_user): ...

class TestUpdateUser:
    def test_update_own_name(self, client, sample_user, auth_headers): ...
    def test_update_without_auth_returns_401(self, client, sample_user): ...
    def test_update_other_user_returns_403(self, client, sample_user): ...
    def test_partial_update(self, client, sample_user, auth_headers): ...

class TestDeleteUser:
    def test_delete_own_account(self, client, sample_user, auth_headers): ...
    def test_delete_returns_204(self, client, sample_user, auth_headers): ...
    def test_delete_without_auth_returns_401(self, client, sample_user): ...
    def test_deleted_user_not_found(self, client, sample_user, auth_headers): ...
```

**Phần C - Mock dependency:**

```python
def test_with_mocked_db(client, mocker):
    """Test khi mock toàn bộ DB dependency."""
    mock_db = {
        1: {"id": 1, "name": "Mocked User", "email": "mock@test.com", "is_active": True}
    }
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/users/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Mocked User"

    app.dependency_overrides.clear()
```

**Tiêu chí hoàn thành:**
- [ ] Tất cả routes được test (CRUD + auth)
- [ ] Test cả happy path và error cases
- [ ] Test validation errors (422)
- [ ] Test authentication (401, 403)
- [ ] Có ít nhất 1 test dùng dependency override
- [ ] Coverage >= 90%

---

## Bài 3 (Optional/Nâng cao): Async Test Suite với pytest-asyncio

> Chỉ làm bài này sau khi đã chắc fixtures, parametrize, `pytest.raises`, và mock cơ bản. Đây là preview cho Day 12/15, không phải yêu cầu bắt buộc trong 2 giờ.

**Mục tiêu:** Viết async test suite đầy đủ cho một UserService sử dụng SQLAlchemy async, fixtures cho async DB session, và mock external services.

**Setup:**

```bash
uv add pytest pytest-asyncio sqlalchemy aiosqlite pytest-mock
```

**Code cần test:**

```python
# src/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", lazy="selectin")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author: Mapped["User"] = relationship("User", back_populates="posts")
```

```python
# src/user_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.models import User, Post
from typing import Optional
import httpx


class UserNotFoundError(Exception):
    pass


class EmailAlreadyExistsError(Exception):
    pass


class UserService:
    def __init__(self, session: AsyncSession, http_client: httpx.AsyncClient | None = None):
        self.session = session
        self.http_client = http_client or httpx.AsyncClient()

    async def create_user(self, name: str, email: str) -> User:
        # Check duplicate
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise EmailAlreadyExistsError(f"Email {email} already exists")

        user = User(name=name, email=email)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_user(self, user_id: int) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        return user

    async def get_all_users(self, active_only: bool = False) -> list[User]:
        stmt = select(User)
        if active_only:
            stmt = stmt.where(User.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_user(self, user_id: int) -> User:
        user = await self.get_user(user_id)
        user.is_active = False
        await self.session.flush()
        return user

    async def get_user_avatar_url(self, user_id: int) -> str:
        """Gọi external service để lấy avatar URL."""
        user = await self.get_user(user_id)
        response = await self.http_client.get(
            f"https://avatar.service/api/{user.email}"
        )
        data = response.json()
        return data["url"]

    async def notify_user(self, user_id: int, message: str) -> bool:
        """Gửi notification qua external service."""
        user = await self.get_user(user_id)
        response = await self.http_client.post(
            "https://notification.service/send",
            json={"email": user.email, "message": message},
        )
        return response.status_code == 200
```

**Nhiệm vụ - viết `tests/conftest.py` và `tests/test_user_service.py`:**

**conftest.py với async fixtures:**

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from src.models import Base


# Dùng SQLite in-memory cho tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Tạo engine một lần cho toàn session.
    StaticPool: dùng một connection duy nhất (cần thiết cho SQLite in-memory).
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Fresh session với auto-rollback sau mỗi test."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def user_service(db_session):
    """UserService với test session."""
    import httpx
    from src.user_service import UserService
    # Dùng mock HTTP client
    async with httpx.AsyncClient() as client:
        yield UserService(session=db_session, http_client=client)


@pytest_asyncio.fixture
async def sample_user(db_session):
    """Tạo user mẫu cho tests."""
    from src.models import User
    user = User(name="Alice Test", email="alice@test.com", is_active=True)
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user
```

**test_user_service.py - các tests cần viết:**

```python
# tests/test_user_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
from src.user_service import UserService, UserNotFoundError, EmailAlreadyExistsError

pytestmark = pytest.mark.asyncio


class TestCreateUser:
    async def test_create_user_success(self, db_session):
        """Test tạo user thành công."""
        service = UserService(db_session)
        user = await service.create_user("Bob", "bob@test.com")

        assert user.id is not None
        assert user.name == "Bob"
        assert user.email == "bob@test.com"
        assert user.is_active is True

    async def test_create_user_duplicate_email(self, db_session, sample_user):
        """Test tạo user với email đã tồn tại."""
        service = UserService(db_session)

        with pytest.raises(EmailAlreadyExistsError, match="alice@test.com"):
            await service.create_user("Alice2", sample_user.email)

    async def test_create_multiple_users(self, db_session):
        """Test tạo nhiều users với emails khác nhau."""
        service = UserService(db_session)
        users = []
        for i in range(5):
            user = await service.create_user(f"User{i}", f"user{i}@test.com")
            users.append(user)

        assert len(users) == 5
        assert len(set(u.id for u in users)) == 5  # IDs unique


class TestGetUser:
    async def test_get_existing_user(self, db_session, sample_user):
        service = UserService(db_session)
        fetched = await service.get_user(sample_user.id)
        assert fetched.email == sample_user.email

    async def test_get_nonexistent_user(self, db_session):
        service = UserService(db_session)
        with pytest.raises(UserNotFoundError, match="99999"):
            await service.get_user(99999)

    async def test_get_all_users_active_filter(self, db_session):
        """Test lọc chỉ active users."""
        service = UserService(db_session)
        # Tạo active và inactive users
        u1 = await service.create_user("Active", "active@test.com")
        u2 = await service.create_user("Inactive", "inactive@test.com")
        await service.deactivate_user(u2.id)

        all_users = await service.get_all_users(active_only=False)
        active_users = await service.get_all_users(active_only=True)

        assert len(all_users) >= 2
        assert all(u.is_active for u in active_users)
        assert any(not u.is_active for u in all_users)


class TestExternalServices:
    async def test_get_avatar_url_success(self, db_session, sample_user):
        """Test gọi external avatar service - mock HTTP client."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = {"url": "https://cdn.example.com/avatar.jpg"}
        mock_client.get.return_value = mock_response

        service = UserService(db_session, http_client=mock_client)
        url = await service.get_user_avatar_url(sample_user.id)

        assert url == "https://cdn.example.com/avatar.jpg"
        mock_client.get.assert_awaited_once_with(
            f"https://avatar.service/api/{sample_user.email}"
        )

    async def test_notify_user_success(self, db_session, sample_user):
        """Test gửi notification thành công."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(status_code=200)
        mock_client.post.return_value = mock_response

        service = UserService(db_session, http_client=mock_client)
        result = await service.notify_user(sample_user.id, "Hello!")

        assert result is True
        mock_client.post.assert_awaited_once_with(
            "https://notification.service/send",
            json={"email": sample_user.email, "message": "Hello!"},
        )

    async def test_notify_user_service_down(self, db_session, sample_user):
        """Test khi notification service trả về lỗi."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(status_code=503)
        mock_client.post.return_value = mock_response

        service = UserService(db_session, http_client=mock_client)
        result = await service.notify_user(sample_user.id, "Hello!")

        assert result is False

    async def test_get_avatar_url_user_not_found(self, db_session):
        """Test get avatar khi user không tồn tại."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        service = UserService(db_session, http_client=mock_client)

        with pytest.raises(UserNotFoundError):
            await service.get_user_avatar_url(99999)

        # HTTP client không được gọi vì user không tồn tại
        mock_client.get.assert_not_awaited()


# Parametrized async test
@pytest.mark.parametrize("name, email", [
    ("Alice", "alice2@test.com"),
    ("Nguyen Van B", "nguyenvanb@example.vn"),
    ("User With Spaces", "spaces@test.com"),
])
async def test_create_various_users(db_session, name: str, email: str):
    service = UserService(db_session)
    user = await service.create_user(name, email)
    assert user.name == name
    assert user.email == email
```

**pyproject.toml configuration:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
testpaths = ["tests"]
```

Với `strict` mode, async tests cần `@pytest.mark.asyncio`; async fixtures dùng `@pytest_asyncio.fixture`. Nếu chuyển sang `asyncio_mode = "auto"`, hãy ghi rõ trong repo và pin `pytest-asyncio` trong lockfile để tránh lệch behavior giữa máy học viên và CI.

**Tiêu chí hoàn thành:**
- [ ] Tất cả test classes có đầy đủ implementations
- [ ] Async fixtures hoạt động đúng (session scope engine, function scope session)
- [ ] Mỗi test được isolate (không leak data giữa tests)
- [ ] External HTTP calls đều được mock
- [ ] Test cả success và failure paths cho external services
- [ ] Parametrized test cho create user
- [ ] Coverage >= 90%

**Chạy để kiểm tra:**

```bash
uv run pytest tests/test_user_service.py -v --cov=src/user_service --cov-report=term-missing
```
