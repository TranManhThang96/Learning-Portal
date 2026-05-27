# Tài Liệu Tham Khảo — Ngày 07: Error Handling & Typing

## 📚 Official Docs

- **Python Exceptions**: https://docs.python.org/3/library/exceptions.html
- **typing module**: https://docs.python.org/3/library/typing.html
- **mypy documentation**: https://mypy.readthedocs.io/
- **mypy Cheat Sheet**: https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
- **PEP 544 — Protocols**: https://peps.python.org/pep-0544/
- **PEP 695 — Type Parameter Syntax (3.12)**: https://peps.python.org/pep-0695/
- **PEP 3134 — Exception Chaining**: https://peps.python.org/pep-3134/
- **contextlib**: https://docs.python.org/3/library/contextlib.html

## 📝 Articles / Blog Posts

- **Real Python — Exception Handling**: https://realpython.com/python-exceptions/
- **Real Python — Python Protocols**: https://realpython.com/python-protocol/
- **Real Python — Python Type Checking**: https://realpython.com/python-type-checking/
- **mypy Getting Started**: https://mypy.readthedocs.io/en/stable/getting_started.html
- **Fluent Python (Chapter 24: Class Metaprogramming)** — Luciano Ramalho
- **Python Cookbook (Chapter 14: Testing, Debugging, Exceptions)**

## 🎥 Video / Courses

- **mCoding — Python Exceptions Deep Dive**: https://www.youtube.com/watch?v=ZsvftkbbrR0
- **ArjanCodes — Python Protocols Explained**: https://www.youtube.com/watch?v=xvb5hGLoK0A
- **ArjanCodes — Result Type in Python**: https://www.youtube.com/watch?v=J-HWmoTKhC8
- **mCoding — mypy Tutorial**: https://www.youtube.com/watch?v=yccn01qgHu4

## 🔧 Tools / Libraries

- **mypy**: https://mypy.readthedocs.io/ — Static type checker
- **pyright**: https://github.com/microsoft/pyright — Microsoft's type checker (Pylance)
- **beartype**: https://github.com/beartype/beartype — Runtime type checking `@beartype`
- **returns**: https://github.com/dry-python/returns — Railway-oriented programming, `Result`, `Maybe`, `IO`
- **neverthrow** (TypeScript): https://github.com/supermacro/neverthrow — Inspiration cho Result type

## 💡 Ghi chú thêm

- `except Exception` là catch-all hợp lý cho application errors nhưng vẫn nên log rồi re-raise nếu không biết cách recover.
- Bare `except:` chỉ phù hợp ở boundary rất thấp để cleanup rồi `raise` lại; đừng dùng trong business logic.
- `mypy --strict` nên bật theo từng package nếu codebase cũ quá nhiều lỗi type cùng lúc.

## Exception Cheat Sheet

```python
# Avoid bare except: it behaves like catching BaseException and can swallow
# KeyboardInterrupt/SystemExit. Use specific exceptions or Exception.

# try/except/else/finally
try:
    result = risky()
except SpecificError as e:
    handle(e)
except (TypeError, ValueError) as e:
    handle_multiple(e)
except Exception as e:
    logger.error("unexpected", error=e)
    raise  # re-raise preserves traceback
else:
    process(result)  # only if no exception
finally:
    cleanup()  # always runs

# Exception chaining
try:
    db_call()
except ConnectionError as e:
    raise ServiceError("DB unavailable") from e  # explicit chain
    # raise ServiceError("...") from None  # suppress chain

# Custom exception
class AppError(Exception):
    def __init__(self, message: str, code: str, http_status: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status

# Suppress
from contextlib import suppress
with suppress(FileNotFoundError):
    os.remove("temp.txt")
```

## Type Hints Cheat Sheet

```python
from __future__ import annotations
from typing import TypeVar, Generic, Protocol, runtime_checkable
from typing import Literal, overload, TYPE_CHECKING

# Union (Python 3.10+)
x: str | int | None = "hello"

# TypeVar
T = TypeVar("T")
def first(items: list[T]) -> T | None:
    return items[0] if items else None

# Python 3.12 new syntax (shorter)
def first[T](items: list[T]) -> T | None: ...

# Generic class
class Stack(Generic[T]):
    def push(self, item: T) -> None: ...
    def pop(self) -> T: ...

# Protocol (structural)
@runtime_checkable
class Drawable(Protocol):
    def draw(self, canvas: str) -> None: ...

# Literal
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Overload
@overload
def process(x: str) -> str: ...
@overload
def process(x: int) -> int: ...
def process(x):
    ...

# TYPE_CHECKING guard
if TYPE_CHECKING:
    from myapp.models import HeavyModel
```

## NodeJS → Python Error Handling

| NodeJS/TypeScript | Python |
|-------------------|--------|
| `try/catch/finally` | `try/except/finally` |
| `catch (e: Error)` | `except Exception as e:` |
| `instanceof` check in catch | `except SpecificError as e:` |
| Re-throw: `throw e` | Re-raise: `raise` |
| `Error.cause` | `e.__cause__` (via `from e`) |
| `new CustomError()` | `raise CustomError(...)` |
| Không có `else` | `else:` — runs if no exception |
| `string \| number` | `str \| int` |
| `T extends U` | `TypeVar("T", bound=U)` |
| `class Foo<T>` | `class Foo(Generic[T])` |
| `interface Foo` | `class Foo(Protocol)` |
| `import type` | `if TYPE_CHECKING:` |
| `neverthrow Result<T,E>` | Custom `Result(Generic[T, E])` hoặc `returns` library |
