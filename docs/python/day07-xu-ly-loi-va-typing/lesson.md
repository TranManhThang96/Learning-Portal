# Ngày 07: Error Handling & Typing

## 🎯 Mục tiêu học tập

- Nắm vững `try/except/else/finally` và sự khác biệt với JS `try/catch`
- Xây dựng exception hierarchy cho production applications
- Exception chaining với `raise X from Y`
- Advanced type hints: `TypeVar`, `Generic[T]`, `Protocol`, `Literal`, `overload`
- Cấu hình và sử dụng `mypy` strict mode

## 🔄 So sánh JavaScript vs Python

| Khái niệm | JavaScript/TypeScript | Python |
|-----------|----------------------|--------|
| Try/catch | `try { } catch (e) { } finally { }` | `try: except: else: finally:` |
| Throw | `throw new Error("msg")` | `raise ValueError("msg")` |
| Catch specific | `catch (e: SpecificError)` (không native) | `except ValueError as e:` |
| Catch multiple | `catch (e) { if (e instanceof X) ... }` | `except (TypeError, ValueError) as e:` |
| Re-throw | `throw e` | `raise` (không có args = re-raise) |
| Exception chaining | Không có native | `raise NewError() from original_error` |
| `else` clause | Không có | `else:` (chạy khi try KHÔNG raise) |
| Custom error | `class MyError extends Error {}` | `class MyError(Exception): pass` |
| Error hierarchy | Flat (tất cả extends Error) | Tree (built-in hierarchy sâu) |
| Unhandled exception | Process crash với stack trace | Same, nhưng có `sys.excepthook` |
| Type narrowing | TypeScript narrowing | `isinstance()` + type checkers |
| Generic | `class Stack<T> {}` | `class Stack(Generic[T]): pass` |
| Union type | `string \| number` | `str \| int` hoặc `Union[str, int]` |
| Optional | `string \| undefined` | `str \| None` hoặc `Optional[str]` |

**Điểm khác biệt quan trọng:**
- Python `else` clause trong try/except: chạy khi KHÔNG có exception — rất useful nhưng ít biết
- Python `raise` không có args = re-raise exception hiện tại (giữ nguyên traceback)
- Python exception chaining (`from e`) rất quan trọng để preserve context
- Python built-in exception hierarchy rộng hơn JS (`ValueError`, `TypeError`, `KeyError`, etc.)
- `except Exception` chỉ bắt "normal exceptions" trong nhánh `Exception`; nó KHÔNG bắt `SystemExit`, `KeyboardInterrupt`, `GeneratorExit`
- Python không có `try/catch` cho async — `try/except` dùng được cả sync và async

---

## 📖 Lý thuyết

### 1. Exception Hierarchy & try/except/else/finally

**Python built-in exception hierarchy:**

```
BaseException
├── SystemExit              # sys.exit()
├── KeyboardInterrupt       # Ctrl+C
├── GeneratorExit           # generator.close()
└── Exception               # Tất cả "normal" exceptions
    ├── StopIteration
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   ├── OverflowError
    │   └── FloatingPointError
    ├── LookupError
    │   ├── IndexError      # list[999]
    │   └── KeyError        # dict["missing"]
    ├── ValueError          # int("abc")
    ├── TypeError           # 1 + "2"
    ├── AttributeError      # obj.missing_attr
    ├── NameError           # undefined_var
    ├── OSError             # File I/O errors
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   └── ConnectionError
    ├── RuntimeError
    ├── NotImplementedError
    └── ImportError
        └── ModuleNotFoundError
```

**Bare `except` và `BaseException`:**

`except:` tương đương gần như `except BaseException:` nên nó bắt cả `SystemExit`, `KeyboardInterrupt`, và `GeneratorExit`. Đây là lý do production code gần như luôn dùng `except Exception as e:` hoặc exception cụ thể hơn. Chỉ catch `BaseException` khi bạn đang viết framework/runtime boundary cần cleanup rồi re-raise.

**try/except/else/finally đầy đủ:**

```python
import json
from pathlib import Path


def load_config(filepath: str) -> dict:
    """
    Load JSON config file với full error handling.

    Cấu trúc try/except/else/finally:
    - try: code có thể raise exception
    - except: handle specific exceptions
    - else: chạy khi try KHÔNG raise exception (thường return ở đây)
    - finally: LUÔN chạy, dùng để cleanup
    """
    file = None
    try:
        file = open(filepath, encoding="utf-8")
        content = file.read()
        data = json.loads(content)  # Có thể raise json.JSONDecodeError

    except FileNotFoundError:
        # Specific exception — không cần `as e` nếu không dùng
        print(f"Config file not found: {filepath}")
        return {}  # Return default

    except json.JSONDecodeError as e:
        # Có thể access exception details
        print(f"Invalid JSON in {filepath}: {e.msg} at line {e.lineno}")
        return {}

    except PermissionError as e:
        # Re-raise với context thêm
        raise RuntimeError(f"Cannot read config file: {filepath}") from e

    except (ValueError, TypeError) as e:
        # Catch nhiều exception types cùng lúc
        print(f"Unexpected data error: {e}")
        return {}

    except Exception as e:
        # Catch-all — dùng cẩn thận, nên log và re-raise
        print(f"Unexpected error loading config: {type(e).__name__}: {e}")
        raise  # Re-raise giữ nguyên traceback

    else:
        # Chạy khi try block THÀNH CÔNG (không có exception nào)
        # Đây là nơi tốt để put code phụ thuộc vào success của try
        print(f"Config loaded successfully: {len(data)} keys")
        return data

    finally:
        # LUÔN LUÔN chạy, dù có exception hay không
        # Dùng để cleanup resources
        if file is not None:
            file.close()
            print("File closed in finally")
        # NOTE: Không return từ finally! Sẽ suppress exception.


# Test
config = load_config("config.json")
config = load_config("nonexistent.json")    # FileNotFoundError → {}
config = load_config("/etc/shadow")          # PermissionError → RuntimeError
```

**EAFP vs LBYL:**

```python
# Python pattern: EAFP vs LBYL
# EAFP = Easier to Ask Forgiveness than Permission (Python style)
# LBYL = Look Before You Leap (C/Java style)

# LBYL (NodeJS style):
import os
if os.path.exists(filepath) and os.access(filepath, os.R_OK):
    with open(filepath) as f:
        data = json.load(f)
else:
    data = {}

# EAFP (Python style) — PREFERRED:
try:
    with open(filepath) as f:
        data = json.load(f)
except (FileNotFoundError, PermissionError, json.JSONDecodeError):
    data = {}


# Sử dụng else để tránh bare except
def safe_divide(a: float, b: float) -> float | None:
    try:
        result = a / b
    except ZeroDivisionError:
        return None
    else:
        return result


# Context manager cho exception handling
from contextlib import suppress

# Thay vì:
try:
    os.remove("temp.txt")
except FileNotFoundError:
    pass

# Dùng suppress:
with suppress(FileNotFoundError):
    os.remove("temp.txt")
```

**Optional note — Python 3.11+ `ExceptionGroup` và `except*`:**

`asyncio.TaskGroup` có thể gom nhiều lỗi thành `ExceptionGroup`. Khi cần xử lý từng nhóm lỗi theo type, dùng `except*`; nếu chưa học async, chỉ cần nhớ đây là advanced tool cho structured concurrency.

```python
try:
    raise ExceptionGroup("batch failed", [ValueError("bad input"), TimeoutError("slow")])
except* ValueError as group:
    print(f"Validation errors: {len(group.exceptions)}")
except* TimeoutError as group:
    print(f"Timeout errors: {len(group.exceptions)}")
```

---

### 2. Custom Exceptions

**Exception hierarchy cho production app:**

```python
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """
    Base exception cho toàn bộ application.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code (e.g., "USER_NOT_FOUND")
        details: Additional context information
        http_status: HTTP status code (nếu relevant)
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        """Serialize cho API response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(AppError):
    """Raised khi input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        details: dict[str, Any] = {}
        if field:
            details["field"] = field
        if value is not None:
            details["invalid_value"] = str(value)

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            http_status=422,
        )
        self.field = field
        self.value = value


class NotFoundError(AppError):
    """Raised khi resource không tồn tại."""

    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)},
            http_status=404,
        )
        self.resource = resource
        self.identifier = identifier


class ConflictError(AppError):
    """Raised khi có conflict (e.g., duplicate)."""

    def __init__(self, message: str, conflicting_field: str | None = None) -> None:
        details: dict[str, Any] = {}
        if conflicting_field:
            details["field"] = conflicting_field
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
            http_status=409,
        )


class AuthenticationError(AppError):
    """Raised khi authentication fails."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            http_status=401,
        )


class AuthorizationError(AppError):
    """Raised khi không có quyền."""

    def __init__(self, action: str, resource: str) -> None:
        super().__init__(
            message=f"Not authorized to {action} {resource}",
            code="AUTHORIZATION_ERROR",
            details={"action": action, "resource": resource},
            http_status=403,
        )


class ExternalServiceError(AppError):
    """Raised khi external service (API, DB) fail."""

    def __init__(
        self,
        service: str,
        operation: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"External service error [{service}]: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "operation": operation},
            http_status=502,
        )
        self.service = service
        self.operation = operation
        self.original_error = original_error
```

**Exception chaining:**

```python
def fetch_user_from_db(user_id: int) -> dict:
    """Simulate DB call với proper exception chaining."""
    try:
        raise ConnectionError("Connection refused to database:5432")
    except ConnectionError as e:
        # "from e" = explicit exception chaining
        # __cause__ attribute sẽ được set
        raise ExternalServiceError(
            service="PostgreSQL",
            operation="fetch_user",
            message=f"Failed to fetch user {user_id}",
            original_error=e,
        ) from e


try:
    fetch_user_from_db(123)
except ExternalServiceError as e:
    print(f"Caught: {e}")
    print(f"Cause: {e.__cause__}")      # ConnectionError
    # Traceback hiển thị: "The above exception was the direct cause..."


# Suppress chaining với "from None"
def parse_integer(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        raise ValidationError(
            f"'{s}' is not a valid integer",
            field="value",
            value=s,
        ) from None  # Không muốn expose internal ValueError
```

---

### 3. Advanced Type Hints

**TypeVar và Generic:**

```python
from typing import TypeVar, Generic, Iterator
from dataclasses import dataclass


T = TypeVar("T")


class Stack(Generic[T]):
    """
    Type-safe generic stack.

    TypeScript equivalent:
    class Stack<T> {
        private items: T[] = [];
        push(item: T): void { ... }
        pop(): T | undefined { ... }
    }
    """

    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("pop from empty stack")
        return self._items.pop()

    def peek(self) -> T:
        if not self._items:
            raise IndexError("peek at empty stack")
        return self._items[-1]

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(reversed(self._items))

    def __repr__(self) -> str:
        return f"Stack({self._items!r})"


# Usage với type inference
int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
value: int = int_stack.pop()  # mypy biết value là int

# Bounded TypeVar
from typing import Protocol

class Comparable(Protocol):
    def __lt__(self, other: "Comparable") -> bool: ...

ComparableT = TypeVar("ComparableT", bound=Comparable)

def find_max(items: list[ComparableT]) -> ComparableT:
    """Works với int, float, str, datetime..."""
    if not items:
        raise ValueError("Cannot find max of empty list")
    return max(items)

max_int = find_max([1, 3, 2])       # Type: int
max_str = find_max(["a", "c", "b"]) # Type: str
```

**Protocol với @runtime_checkable:**

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> "Serializable": ...


@runtime_checkable
class Cacheable(Protocol):
    def cache_key(self) -> str: ...
    def ttl(self) -> int: ...


@dataclass
class User:
    id: int
    name: str
    email: str

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email}

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(id=data["id"], name=data["name"], email=data["email"])

    def cache_key(self) -> str:
        return f"user:{self.id}"

    def ttl(self) -> int:
        return 3600


user = User(1, "Alice", "alice@example.com")
print(isinstance(user, Serializable))  # True
print(isinstance(user, Cacheable))     # True
```

**Literal types:**

```python
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


def set_log_level(level: LogLevel) -> None:
    import logging
    logging.getLogger().setLevel(level)


set_log_level("INFO")     # OK
# set_log_level("VERBOSE")  # mypy ERROR: Expected Literal["DEBUG", ...]
```

**`@overload` — function overloading:**

```python
from typing import overload, Any


@overload
def process(x: str) -> str: ...
@overload
def process(x: int) -> int: ...
@overload
def process(x: list[str]) -> list[str]: ...


def process(x: str | int | list[str]) -> str | int | list[str]:
    if isinstance(x, str):
        return x.upper()
    elif isinstance(x, int):
        return x * 2
    else:
        return [item.upper() for item in x]


# mypy infers correct return types:
result1: str = process("hello")         # OK: str
result2: int = process(5)               # OK: int
result3: list[str] = process(["a", "b"]) # OK: list[str]
```

**`TYPE_CHECKING` — avoid circular imports:**

```python
from __future__ import annotations  # Cho phép string forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myapp.models.user import User
    from myapp.services.order_service import OrderService


class UserRepository:
    async def get_user_with_orders(self, user_id: int) -> "User":
        # "User" trong quotes = forward reference
        ...
```

---

### 4. mypy Strict Mode

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
show_column_numbers = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[[tool.mypy.overrides]]
module = ["alembic.*", "some_untyped_lib.*"]
ignore_missing_imports = true
```

**Common mypy errors và cách fix:**

```python
# ERROR: Function is missing a return type annotation  [no-untyped-def]
def greet(name: str) -> str:  # Phải có cả input và return type
    return f"Hello, {name}"


# ERROR: Item "None" has no attribute "name"  [union-attr]
def process(user: "User | None") -> str:
    if user is None:
        return "unknown"
    return user.name  # GOOD: narrowed to User after None check


# Type narrowing với isinstance
def process(value: int | str) -> str:
    if isinstance(value, int):
        return str(value * 2)   # mypy biết value là int
    else:
        return value.upper()    # mypy biết value là str


# cast — khi bạn biết rõ hơn mypy
from typing import cast, Any

raw_value: Any = get_from_database()
user_id: int = cast(int, raw_value)
# WARNING: cast không có runtime effect!


# # type: ignore — escape hatch (dùng cẩn thận)
result = some_dynamic_value  # type: ignore[assignment]
```

---

## ⚠️ Common Mistakes

| Mistake | Sai | Đúng |
|---------|-----|------|
| Bare `except` | `except:` → catch kể cả SystemExit | `except Exception as e:` |
| Swallow exception | `except Exception: pass` | Log và/hoặc re-raise |
| Không dùng `from e` | `raise NewError()` — mất cause | `raise NewError() from e` |
| Return từ `finally` | `finally: return value` → suppress exception | Không return trong finally |
| Quá broad exception | `except Exception as e:` cho mọi thứ | Catch specific exceptions |
| Mutable default annotation | `def f(x: list = []):` | `def f(x: list \| None = None):` |
| Quên `__future__` annotations | Forward ref error | `from __future__ import annotations` |
| `cast` thay vì check | `cast(int, value)` khi value có thể None | `isinstance(value, int)` |

---

## ✅ Best Practices

**Exception handling:**
- Catch exceptions càng specific càng tốt
- Luôn log exception trước khi re-raise hoặc handle
- Dùng exception chaining (`from e`) để preserve cause
- `else` clause dùng khi muốn code chỉ chạy khi không có exception
- `finally` chỉ dùng cho cleanup, không return từ đây

**Type hints:**
- Bắt đầu với `from __future__ import annotations` trong mọi file
- Dùng `X | Y` thay vì `Union[X, Y]` (Python 3.10+)
- Dùng `X | None` thay vì `Optional[X]` (Python 3.10+)
- `Protocol` ưu tiên hơn `ABC` cho structural typing
- Không overuse `Any` — là "escape hatch", không phải solution

---

## ⚖️ Trade-offs

| Pattern | Pros | Cons | Khi dùng |
|---------|------|------|-----------|
| Specific exceptions | Clear intent, easy to handle | More classes | Domain modeling |
| Exception hierarchy | Organized, filterable | Maintenance overhead | Large applications |
| `raise X from Y` | Full context, better debugging | Verbose | Service boundaries |
| Generic `T` | Type-safe, reusable | Complex | Data structures, utilities |
| `Protocol` | Loose coupling | No shared code | Interface definitions |
| `@overload` | Precise type inference | Verbose | Public APIs |
| `mypy strict` | Catch bugs early | False positives, slower CI | Production codebases |

---

## 📝 Tóm tắt

| Concept | Key Point | JS/TS Analogy |
|---------|-----------|---------------|
| `try/except/else/finally` | `else` = success path, `finally` = cleanup | `try/catch/finally` (no `else`) |
| `raise` (no args) | Re-raise current exception với original traceback | `throw` (giữ nguyên) |
| `raise X from Y` | Exception chaining, preserve cause | Không có native |
| `raise X from None` | Suppress chaining | Không có |
| Exception hierarchy | Custom exceptions kế thừa `AppError` | `class MyError extends Error` |
| `Generic[T]` | Type-safe generic class | `class Foo<T>` |
| `Protocol` | Structural typing | `interface` (structural) |
| `Literal` | Constrained string/int values | Literal types `"GET" \| "POST"` |
| `@overload` | Multiple type signatures | Function overloads |
| `TYPE_CHECKING` | Import chỉ cho type checker | `import type` trong TS |
| `mypy strict` | Catch type errors trước runtime | `tsc --strict` |
- Xây dựng custom exception hierarchy cho production apps
- Sử dụng type hints nâng cao: TypeVar, Generic, Literal, Protocol
- Hiểu và áp dụng mypy strict mode
