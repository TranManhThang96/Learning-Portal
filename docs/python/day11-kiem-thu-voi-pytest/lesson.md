# Ngày 11: Testing trong Python với pytest

## 🎯 Mục tiêu học tập

Sau bài học này, bạn sẽ:
- Hiểu cách viết test với pytest và so sánh với Jest/Vitest
- Sử dụng fixtures để setup/teardown test data
- Parametrize tests để test nhiều cases
- Mock dependencies với `unittest.mock` và `pytest-mock`
- Viết async tests với `pytest-asyncio`
- Đo code coverage với `pytest-cov`

**Phạm vi 2 giờ:** core path là pytest basics, fixtures, parametrize, `pytest.raises`, và mock cơ bản. Async DB fixtures, FastAPI TestClient/httpx, coverage threshold, `xdist`, và test performance là phần nâng cao/đọc thêm; chỉ làm khi đã hoàn tất core tests.

---

## 🔄 So sánh với Jest/Vitest

| Khái niệm | Jest/Vitest (TypeScript) | pytest (Python) |
|---|---|---|
| **Test file naming** | `*.test.ts`, `*.spec.ts` | `test_*.py`, `*_test.py` |
| **Test function** | `test('name', () => {})` | `def test_name():` |
| **describe block** | `describe('Suite', () => {})` | `class TestSuite:` hoặc không cần |
| **beforeEach** | `beforeEach(() => {})` | `@pytest.fixture` (function scope) |
| **afterEach/cleanup** | `afterEach(() => {})` | `yield` trong fixture |
| **beforeAll** | `beforeAll(() => {})` | `@pytest.fixture(scope="module")` |
| **expect/assert** | `expect(val).toBe(x)` | `assert val == x` |
| **toThrow** | `expect(fn).toThrow(Error)` | `with pytest.raises(Error):` |
| **parametrize** | `test.each([...])` | `@pytest.mark.parametrize(...)` |
| **mock module** | `jest.mock('./module')` | `@patch('module.func')` hoặc `mocker.patch(...)` |
| **spyOn** | `jest.spyOn(obj, 'method')` | `mocker.spy(obj, 'method')` |
| **async testing** | `async () => { await ... }` | `@pytest.mark.asyncio` + `async def test_():` |
| **snapshot** | `expect(val).toMatchSnapshot()` | Không built-in, dùng `syrupy` |
| **coverage** | `jest --coverage` | `pytest --cov=src --cov-report=html` |

---

## 📖 Lý thuyết

### Section 1: pytest Basics

Cài đặt:

```bash
uv add pytest pytest-cov pytest-mock pytest-asyncio
```

Cấu trúc thư mục:

```
project/
├── src/
│   └── calculator.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_calculator.py
└── pyproject.toml
```

Bài học đầu tiên - viết test đơn giản:

```python
# tests/test_calculator.py
import pytest


def add(a: int, b: int) -> int:
    return a + b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


# Mỗi function bắt đầu bằng test_ là một test case
def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -2) == -3


def test_add_zero():
    assert add(0, 0) == 0


# Test exception: tương đương Jest expect(fn).toThrow()
def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError) as exc_info:
        divide(10, 0)
    # Kiểm tra message của exception
    assert "Cannot divide by zero" in str(exc_info.value)


def test_divide_by_zero_type():
    # Chỉ kiểm tra loại exception, không cần message
    with pytest.raises(ZeroDivisionError):
        divide(5, 0)


# Nhóm test bằng class - tương đương describe() trong Jest
class TestDivide:
    def test_integer(self):
        assert divide(10, 2) == 5.0

    def test_float_result(self):
        # pytest.approx: so sánh float với tolerance
        # Tương đương Jest: expect(val).toBeCloseTo(0.333, 3)
        assert divide(1, 3) == pytest.approx(0.333, rel=1e-3)

    def test_negative(self):
        assert divide(-10, 2) == -5.0

    def test_both_negative(self):
        assert divide(-10, -2) == 5.0
```

Chạy tests:

```bash
# Chạy tất cả tests
uv run pytest

# Chạy với verbose output
uv run pytest -v

# Chạy một file cụ thể
uv run pytest tests/test_calculator.py

# Chạy một test cụ thể
uv run pytest tests/test_calculator.py::test_add_positive

# Chạy một class
uv run pytest tests/test_calculator.py::TestDivide

# Chạy một method trong class
uv run pytest tests/test_calculator.py::TestDivide::test_integer

# Chạy theo keyword
uv run pytest -k "divide"  # Chạy tất cả tests có chứa "divide"
uv run pytest -k "not slow"  # Chạy tất cả tests không có mark "slow"

# Dừng ngay khi fail đầu tiên (như Jest --bail)
uv run pytest -x

# Show print output (như Jest --verbose)
uv run pytest -s

# Hiển thị 10 test chậm nhất
uv run pytest --durations=10
```

Marks - đánh nhãn test:

```python
import pytest


@pytest.mark.slow
def test_heavy_computation():
    # Test tốn nhiều thời gian
    ...


@pytest.mark.skip(reason="Chưa implement")
def test_feature_not_ready():
    ...


@pytest.mark.skipif(
    condition=True,
    reason="Skip trên CI"
)
def test_local_only():
    ...


@pytest.mark.xfail(reason="Bug đã biết, chưa fix")
def test_known_bug():
    assert 1 == 2  # Sẽ fail nhưng không tính là failure
```

Đăng ký marks trong `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

---

### Section 2: Fixtures

Fixtures là cơ chế setup/teardown của pytest. Tương đương `beforeEach`/`afterEach`/`beforeAll`/`afterAll` trong Jest nhưng mạnh hơn nhiều.

**Fixture cơ bản:**

```python
# tests/test_fixtures_basic.py
import pytest


# Định nghĩa fixture bằng decorator
@pytest.fixture
def sample_user():
    # Phần này chạy trước mỗi test (như beforeEach)
    return {
        "id": 1,
        "name": "Nguyen Van A",
        "email": "nguyenvana@example.com",
    }


def test_user_name(sample_user):
    # pytest tự inject fixture qua tên parameter
    assert sample_user["name"] == "Nguyen Van A"


def test_user_email(sample_user):
    assert "@" in sample_user["email"]
```

**Fixture với cleanup - dùng `yield`:**

```python
import pytest
import tempfile
import os


@pytest.fixture
def temp_file():
    # Setup: tạo file tạm
    fd, path = tempfile.mkstemp()
    os.close(fd)
    print(f"\nCreated temp file: {path}")

    yield path  # <-- Test code chạy ở đây

    # Teardown: xóa file sau test (như afterEach)
    os.unlink(path)
    print(f"\nDeleted temp file: {path}")


def test_write_to_file(temp_file):
    with open(temp_file, "w") as f:
        f.write("Hello, pytest!")

    with open(temp_file, "r") as f:
        content = f.read()

    assert content == "Hello, pytest!"
```

**Fixture scope - kiểm soát vòng đời:**

```python
import pytest


# scope="function" (mặc định): tạo mới cho mỗi test
@pytest.fixture(scope="function")
def db_session():
    session = create_session()
    yield session
    session.rollback()
    session.close()


# scope="class": dùng chung trong một class
@pytest.fixture(scope="class")
def class_db(request):
    db = create_database()
    request.cls.db = db  # Gán vào class attribute
    yield db
    db.drop_all()


# scope="module": dùng chung trong một file
@pytest.fixture(scope="module")
def module_client():
    # Khởi tạo một lần cho cả file
    client = create_test_client()
    yield client
    client.close()


# scope="session": dùng chung cho toàn bộ test session
@pytest.fixture(scope="session")
def database():
    # Tạo database một lần cho toàn bộ test suite
    db = create_test_database()
    yield db
    db.cleanup()
```

**conftest.py - chia sẻ fixtures giữa các files:**

```python
# tests/conftest.py
# File đặc biệt: pytest tự động load, không cần import
import pytest
from typing import Generator


@pytest.fixture(scope="session")
def app():
    """Khởi tạo FastAPI app một lần cho toàn session."""
    from main import create_app
    return create_app(testing=True)


@pytest.fixture(scope="module")
def client(app):
    """TestClient dùng chung trong một module."""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(app) -> Generator:
    """Fresh DB session cho mỗi test, tự động rollback."""
    from app.database import AsyncSessionLocal
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_user_data():
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "secret123",
    }
```

**autouse - tự động áp dụng fixture:**

```python
import pytest


@pytest.fixture(autouse=True)
def reset_database():
    """Tự động reset database trước mỗi test, không cần khai báo."""
    setup_test_database()
    yield
    teardown_test_database()


# Test này KHÔNG cần khai báo reset_database nhưng vẫn được reset
def test_create_user():
    user = User.create(name="Alice")
    assert user.id is not None
```

**Factory fixtures - tạo data linh hoạt:**

```python
import pytest
from typing import Callable


@pytest.fixture
def make_user() -> Callable:
    """Factory fixture: trả về function để tạo user với custom data."""
    created_users = []

    def _make_user(name: str = "Default", email: str = "default@test.com", **kwargs):
        user = User(name=name, email=email, **kwargs)
        db.session.add(user)
        db.session.flush()
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup: xóa tất cả users đã tạo
    for user in created_users:
        db.session.delete(user)
    db.session.commit()


# Sử dụng factory fixture
def test_user_comparison(make_user):
    user1 = make_user(name="Alice", email="alice@test.com")
    user2 = make_user(name="Bob", email="bob@test.com")
    assert user1.id != user2.id
    assert user1.name != user2.name
```

---

### Section 3: Parametrize

`@pytest.mark.parametrize` tương đương `test.each` trong Jest.

**Parametrize cơ bản:**

```python
import pytest


def is_palindrome(s: str) -> bool:
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]


# Tham số đơn
@pytest.mark.parametrize("text", ["racecar", "level", "madam"])
def test_palindrome_true(text):
    assert is_palindrome(text) is True


@pytest.mark.parametrize("text", ["hello", "python", "pytest"])
def test_palindrome_false(text):
    assert is_palindrome(text) is False


# Nhiều tham số: (input, expected)
@pytest.mark.parametrize("text, expected", [
    ("racecar", True),
    ("hello", False),
    ("A man a plan a canal Panama", True),
    ("", True),
    ("a", True),
])
def test_palindrome(text: str, expected: bool):
    assert is_palindrome(text) == expected
```

**Parametrize với ids - đặt tên cho từng case:**

```python
import pytest


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 1, 2),
        (-1, 1, 0),
        (0, 0, 0),
        (100, -100, 0),
    ],
    ids=[
        "positive numbers",
        "negative + positive",
        "zeros",
        "large numbers cancel out",
    ],
)
def test_add(a: int, b: int, expected: int):
    assert add(a, b) == expected
```

**Parametrize + pytest.raises:**

```python
import pytest


def parse_age(value: str) -> int:
    age = int(value)
    if age < 0:
        raise ValueError("Age cannot be negative")
    if age > 150:
        raise ValueError("Age is unreasonably large")
    return age


@pytest.mark.parametrize("value, exc_type, exc_message", [
    ("abc", ValueError, "invalid literal"),  # int("abc") raises ValueError
    ("-5", ValueError, "Age cannot be negative"),
    ("200", ValueError, "Age is unreasonably large"),
])
def test_parse_age_errors(value: str, exc_type: type, exc_message: str):
    with pytest.raises(exc_type, match=exc_message):
        parse_age(value)


@pytest.mark.parametrize("value, expected", [
    ("0", 0),
    ("25", 25),
    ("150", 150),
])
def test_parse_age_valid(value: str, expected: int):
    assert parse_age(value) == expected
```

**Nested parametrize - kết hợp nhiều parametrize:**

```python
import pytest


@pytest.mark.parametrize("x", [1, 2, 3])
@pytest.mark.parametrize("y", [10, 20])
def test_multiply(x: int, y: int):
    # Sẽ tạo ra 6 test cases: (1,10), (1,20), (2,10), (2,20), (3,10), (3,20)
    assert multiply(x, y) == x * y
```

---

### Section 4: Mocking

#### unittest.mock (built-in)

```python
# tests/test_mocking.py
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
import pytest


# --- Mock cơ bản ---
def test_mock_basic():
    mock_service = Mock()

    # Mock return value
    mock_service.get_user.return_value = {"id": 1, "name": "Alice"}

    result = mock_service.get_user(1)
    assert result == {"id": 1, "name": "Alice"}

    # Verify được gọi
    mock_service.get_user.assert_called_once_with(1)
    mock_service.get_user.assert_called_with(1)

    # Kiểm tra call count
    assert mock_service.get_user.call_count == 1


def test_mock_side_effect():
    mock_db = Mock()

    # side_effect: raise exception
    mock_db.query.side_effect = ConnectionError("DB is down")

    with pytest.raises(ConnectionError, match="DB is down"):
        mock_db.query("SELECT 1")


def test_mock_side_effect_sequence():
    mock_api = Mock()

    # side_effect với list: lần 1 trả về X, lần 2 trả về Y...
    mock_api.fetch.side_effect = [
        {"data": "first"},
        {"data": "second"},
        ConnectionError("Rate limited"),
    ]

    assert mock_api.fetch() == {"data": "first"}
    assert mock_api.fetch() == {"data": "second"}
    with pytest.raises(ConnectionError):
        mock_api.fetch()


def test_magicmock():
    # MagicMock: hỗ trợ magic methods (__len__, __iter__, __enter__, __exit__)
    mock_file = MagicMock()
    mock_file.__enter__.return_value = mock_file
    mock_file.read.return_value = "file content"

    with mock_file as f:
        content = f.read()

    assert content == "file content"
```

**patch decorator - mock object trong module:**

```python
# src/email_service.py
import smtplib


def send_welcome_email(email: str, name: str) -> bool:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.sendmail("noreply@app.com", email, f"Welcome {name}!")
    return True


# tests/test_email_service.py
from unittest.mock import patch, MagicMock
import pytest
from src.email_service import send_welcome_email


# @patch mock object tại đường dẫn nơi nó được DÙNG, không phải nơi định nghĩa
@patch("src.email_service.smtplib.SMTP")
def test_send_welcome_email(mock_smtp_class):
    # mock_smtp_class là Mock của class smtplib.SMTP
    mock_smtp_instance = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance

    result = send_welcome_email("user@test.com", "Alice")

    assert result is True
    mock_smtp_instance.sendmail.assert_called_once_with(
        "noreply@app.com",
        "user@test.com",
        "Welcome Alice!",
    )


# patch như context manager
def test_send_email_failure():
    with patch("src.email_service.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.side_effect = ConnectionError("SMTP failed")

        with pytest.raises(ConnectionError):
            send_welcome_email("user@test.com", "Bob")


# patch nhiều objects
@patch("src.email_service.smtplib.SMTP")
@patch("src.email_service.logging")
def test_with_multiple_patches(mock_logging, mock_smtp):
    # Thứ tự parameter: patch gần test function nhất = parameter đầu tiên
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

    send_welcome_email("user@test.com", "Charlie")

    # Verify logging được gọi
    mock_logging.info.assert_called()
```

#### pytest-mock (cách viết sạch hơn)

```python
# pytest-mock cung cấp mocker fixture
# Không cần decorator, mock tự động cleanup sau mỗi test

def test_send_email_with_mocker(mocker):
    # mocker.patch: tương đương @patch
    mock_smtp = mocker.patch("src.email_service.smtplib.SMTP")
    mock_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_instance

    result = send_welcome_email("user@test.com", "Dave")

    assert result is True
    mock_instance.sendmail.assert_called_once()


def test_spy_on_method(mocker):
    # mocker.spy: gọi method thật NHƯNG track được calls
    # Tương đương Jest jest.spyOn(obj, 'method')
    calculator = Calculator()

    spy = mocker.spy(calculator, "add")

    result = calculator.add(2, 3)

    assert result == 5  # Vẫn gọi method thật
    spy.assert_called_once_with(2, 3)
    assert spy.call_count == 1


def test_mock_return_value(mocker):
    # mocker.patch.object: mock một method của object cụ thể
    service = UserService()
    mocker.patch.object(service, "get_user", return_value={"id": 1})

    result = service.get_user(1)
    assert result["id"] == 1


def test_mock_property(mocker):
    # Mock property
    mocker.patch.object(
        type(some_object),
        "property_name",
        new_callable=mocker.PropertyMock,
        return_value="mocked value"
    )
```

**AsyncMock - mock async functions:**

```python
from unittest.mock import AsyncMock, patch
import pytest


# src/user_service.py
class UserService:
    async def fetch_from_api(self, user_id: int) -> dict:
        # Gọi external API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.example.com/users/{user_id}")
            return response.json()

    async def get_user_with_posts(self, user_id: int) -> dict:
        user = await self.fetch_from_api(user_id)
        return {**user, "posts": []}


# tests/test_user_service.py
@pytest.mark.asyncio
async def test_get_user_with_posts(mocker):
    service = UserService()

    # Mock async method
    mock_fetch = mocker.patch.object(
        service,
        "fetch_from_api",
        new_callable=AsyncMock,
        return_value={"id": 1, "name": "Alice"},
    )

    result = await service.get_user_with_posts(1)

    assert result["name"] == "Alice"
    assert "posts" in result
    mock_fetch.assert_awaited_once_with(1)
```

---

### Section 5: pytest-asyncio - Async Testing

> **Scope nâng cao:** học cách chạy một async test và một async fixture là đủ cho ngày này. Async DB session, FastAPI async client, và event loop scope chi tiết nên để sang Day 12-15 hoặc đọc thêm.

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "strict"  # Mặc định hiện hành: async tests/fixtures phải khai báo rõ
```

```python
# tests/test_async.py
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock


# Cách khuyến nghị cho course: explicit mark + strict mode
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected_value


# Nếu team đổi pyproject sang asyncio_mode = "auto", decorator có thể bỏ:
# async def test_auto_async():
#     result = await some_async_function()
#     assert result is not None
# Nhưng auto mode nên được ghi rõ và pin pytest-asyncio trong lockfile.


# Async fixture
@pytest_asyncio.fixture
async def async_db():
    """Async fixture với yield."""
    async with create_async_engine(TEST_DATABASE_URL) as engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(async_db):
    async with AsyncSession(async_db) as session:
        yield session
        await session.rollback()


# Test với async fixtures
@pytest.mark.asyncio
async def test_create_user(db_session):
    repo = UserRepository(db_session)
    user = await repo.create(name="Alice", email="alice@test.com")

    assert user.id is not None
    assert user.name == "Alice"


# Test async exception
@pytest.mark.asyncio
async def test_async_raises():
    with pytest.raises(ValueError, match="not found"):
        await get_user_by_id(-1)


# Test concurrent operations
@pytest.mark.asyncio
async def test_concurrent_requests():
    results = await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3),
    )
    assert len(results) == 3
    assert all(r is not None for r in results)


# Async parametrize
@pytest.mark.asyncio
@pytest.mark.parametrize("user_id, expected_name", [
    (1, "Alice"),
    (2, "Bob"),
])
async def test_get_user_parametrized(db_session, user_id: int, expected_name: str):
    user = await get_user(db_session, user_id)
    assert user.name == expected_name
```

**Test FastAPI với TestClient:**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from main import app


# Synchronous TestClient (chạy async app trong sync context)
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_user(client):
    response = client.post(
        "/users",
        json={"name": "Alice", "email": "alice@test.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert "id" in data


def test_get_user_not_found(client):
    response = client.get("/users/99999")
    assert response.status_code == 404


# Async TestClient với httpx
@pytest.mark.asyncio
async def test_async_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200


# Mock dependency trong FastAPI
def test_with_mock_dependency(client, mocker):
    from app.dependencies import get_current_user
    from main import app

    # Override dependency
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "admin"}

    response = client.get("/protected")
    assert response.status_code == 200

    # Cleanup
    app.dependency_overrides.clear()
```

---

### Section 6: Coverage Configuration

> **Scope nâng cao:** coverage config là tốt cho CI, nhưng trong 2 giờ chỉ cần biết chạy `pytest -q` và đọc failure. Thêm coverage threshold sau khi test suite đã ổn định.

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "strict"
addopts = [
    "--strict-markers",
    "--tb=short",
    "-ra",  # Show summary of all non-passed tests
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__init__.py",
]
branch = true  # Đo branch coverage (không chỉ line coverage)

[tool.coverage.report]
show_missing = true
skip_covered = false
fail_under = 80  # Fail nếu coverage < 80%
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

[tool.coverage.html]
directory = "htmlcov"
```

Chạy coverage:

```bash
# Chạy tests với coverage
uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# Chỉ xem summary
uv run pytest --cov=src --cov-report=term

# Fail nếu coverage < 80%
uv run pytest --cov=src --cov-fail-under=80

# Coverage cho một module cụ thể
uv run pytest tests/test_user_service.py --cov=src/user_service --cov-report=term-missing
```

---

## ⚠️ Common Mistakes

| Mistake | Vấn đề | Cách sửa |
|---|---|---|
| **Import sai trong @patch** | `@patch("smtplib.SMTP")` không hoạt động khi module đã import | Phải patch nơi dùng: `@patch("mymodule.smtplib.SMTP")` |
| **Không dùng `pytest.approx`** | `assert 0.1 + 0.2 == 0.3` → FAIL vì floating point | Dùng `assert 0.1 + 0.2 == pytest.approx(0.3)` |
| **Fixture scope sai** | Dùng `scope="session"` cho DB session dẫn đến data leak giữa tests | Session-scoped fixture chỉ cho read-only data; dùng `scope="function"` cho mutable state |
| **Async fixture khai báo sai mode** | `@pytest.fixture` cho async fixture có thể không chạy như mong đợi trong `strict` mode | Dùng `asyncio_mode = "strict"` + `@pytest.mark.asyncio` + `@pytest_asyncio.fixture`; nếu dùng `auto`, pin `pytest-asyncio` |
| **Mock không đúng path** | Mock không có tác dụng vì mock sai target | Mock phải trỏ đến nơi object được IMPORT vào, không phải nơi định nghĩa |
| **Test phụ thuộc thứ tự** | Test A tạo data, Test B dùng data đó → fail khi chạy riêng lẻ | Mỗi test phải độc lập, dùng fixtures để setup data riêng |

---

## ✅ Best Practices

**1. Đặt tên test rõ ràng - theo pattern `test_<what>_<when>_<expected>`:**

```python
# Không tốt
def test_user():
    ...

# Tốt
def test_create_user_with_valid_data_returns_user_with_id():
    ...

def test_create_user_with_duplicate_email_raises_conflict():
    ...
```

**2. Arrange-Act-Assert (AAA) pattern:**

```python
def test_create_order(make_user, make_product):
    # Arrange
    user = make_user(name="Alice")
    product = make_product(price=100, stock=5)

    # Act
    order = create_order(user_id=user.id, product_id=product.id, quantity=2)

    # Assert
    assert order.id is not None
    assert order.total == 200
    assert order.status == "pending"
```

**3. Một assert logic per test (khi có thể):**

```python
# Không tốt - test làm quá nhiều thứ
def test_user_creation():
    user = create_user("Alice", "alice@test.com")
    assert user.id is not None
    assert user.name == "Alice"
    assert user.email == "alice@test.com"
    assert user.created_at is not None
    assert user.is_active is True
    # Nếu assertion đầu fail, không biết những cái sau có đúng không

# Tốt - dùng dataclass hoặc named tuple để assert tổng thể
def test_user_creation():
    user = create_user("Alice", "alice@test.com")
    assert user == User(name="Alice", email="alice@test.com", is_active=True)
```

**4. Dùng conftest.py để chia sẻ fixtures:**

```
tests/
├── conftest.py          # Fixtures dùng chung toàn bộ
├── unit/
│   ├── conftest.py      # Fixtures cho unit tests
│   └── test_*.py
└── integration/
    ├── conftest.py      # Fixtures cho integration tests
    └── test_*.py
```

**5. Mark slow tests và skip trên CI thông thường:**

```python
@pytest.mark.slow
@pytest.mark.integration
async def test_full_user_flow():
    # Test toàn bộ flow: create user -> login -> create post -> ...
    ...
```

---

## ⚖️ Trade-offs

| | pytest | unittest (built-in) |
|---|---|---|
| **Syntax** | Đơn giản, dùng `assert` thường | Verbose: `self.assertEqual`, `self.assertRaises` |
| **Fixtures** | Linh hoạt, inject qua parameter | `setUp`/`tearDown` cứng nhắc hơn |
| **Discovery** | Tự động, convention-based | Cần extend `unittest.TestCase` |
| **Ecosystem** | Phong phú (pytest-mock, pytest-asyncio...) | Built-in, không cần cài thêm |
| **Compatibility** | Có thể chạy unittest test cases | Không chạy được pytest fixtures |

**Khi nào dùng gì:**
- **pytest**: Dự án mới, muốn test đơn giản và flexible
- **unittest**: Dự án cũ hoặc cần built-in only, không muốn thêm dependency

---

## 🚀 Performance Notes

**1. Chạy tests song song với `pytest-xdist`:**

```bash
uv add pytest-xdist

# Chạy với 4 workers
uv run pytest -n 4

# Tự động detect số CPU
uv run pytest -n auto
```

**2. Profiling tests chậm:**

```bash
# Hiển thị 10 tests chậm nhất
uv run pytest --durations=10

# Chỉ hiển thị tests chậm hơn 1 giây
uv run pytest --durations=10 --durations-min=1.0
```

**3. Tối ưu fixture scope:**

```python
# Thay vì tạo DB connection cho mỗi test (chậm)
@pytest.fixture(scope="function")  # Không tốt cho DB connection
def db():
    return create_connection()

# Dùng session scope cho connection, function scope cho transaction
@pytest.fixture(scope="session")
def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    engine.sync_engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()
```

**4. Dùng `--lf` để chạy lại chỉ tests vừa fail:**

```bash
# Chạy lại tests fail lần trước
uv run pytest --lf

# Chạy tests fail trước, sau đó mới chạy phần còn lại
uv run pytest --ff
```

---

## 📝 Tóm tắt

| Tính năng | Cú pháp |
|---|---|
| **Test function** | `def test_name():` |
| **Test class** | `class TestName:` + `def test_method(self):` |
| **Assert** | `assert value == expected` |
| **Assert exception** | `with pytest.raises(ExcType, match="msg"):` |
| **Assert float** | `assert val == pytest.approx(0.333, rel=1e-3)` |
| **Fixture** | `@pytest.fixture` + parameter injection |
| **Fixture cleanup** | `yield` trong fixture body |
| **Fixture scope** | `@pytest.fixture(scope="session/module/class/function")` |
| **Parametrize** | `@pytest.mark.parametrize("a,b", [(1,2), (3,4)])` |
| **Skip** | `@pytest.mark.skip(reason="...")` |
| **Mock** | `mocker.patch("module.func")` hoặc `@patch("module.func")` |
| **Async test** | `@pytest.mark.asyncio` + `async def test_():` |
| **Coverage** | `pytest --cov=src --cov-report=html` |

**Workflow khuyến nghị:**
1. Viết test trước khi viết code (TDD) hoặc viết cùng lúc
2. Chạy `pytest -x --tb=short` trong quá trình dev
3. Chạy `pytest --cov=src` trước khi commit
4. Dùng `pytest -n auto` trên CI để tăng tốc
