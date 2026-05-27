# Bài Tập — Ngày 06: Modules, Packages & Project Structure

## Bài 1: Tổ Chức Package Calculator

**Mô tả:** Tạo một Python package `calculator` được tổ chức tốt với public API rõ ràng, proper `__init__.py`, và `__all__`. Package sẽ cung cấp các operations toán học với error handling và logging.

**Yêu cầu cấu trúc:**

```
calculator/
├── __init__.py           # Public API: expose Operations, calculate()
├── operations/
│   ├── __init__.py       # Re-export basic và advanced
│   ├── basic.py          # add, subtract, multiply, divide
│   └── advanced.py       # power, sqrt, factorial, fibonacci
├── history.py            # Calculation history với @dataclass
└── exceptions.py         # DivisionByZeroError, NegativeSquareRootError
```

**Yêu cầu:**
- `calculator/__init__.py` phải expose: `calculate()`, `Operations`, `CalculationHistory`
- `__all__` được khai báo đầy đủ ở mỗi `__init__.py`
- Relative imports trong internal modules
- Exception hierarchy kế thừa từ base `CalculatorError`
- `calculate(operation: str, *args) -> float` — dispatch function

**Starter code:**

```python
# calculator/exceptions.py
class CalculatorError(Exception):
    """Base exception cho calculator package."""
    pass


class DivisionByZeroError(CalculatorError):
    """Raised khi chia cho 0."""
    pass


class NegativeSquareRootError(CalculatorError):
    """Raised khi sqrt của số âm."""
    pass


class InvalidOperationError(CalculatorError):
    """Raised khi operation không tồn tại."""
    pass


# calculator/history.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CalculationRecord:
    """Lưu lại một lần tính toán."""
    operation: str
    args: tuple
    result: float
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        args_str = ", ".join(str(a) for a in self.args)
        return f"[{self.timestamp:%H:%M:%S}] {self.operation}({args_str}) = {self.result}"


class CalculationHistory:
    """Manages history of calculations."""

    def __init__(self, max_size: int = 100) -> None:
        self._records: list[CalculationRecord] = []
        self._max_size = max_size

    def add(self, operation: str, args: tuple, result: float) -> None:
        record = CalculationRecord(operation=operation, args=args, result=result)
        self._records.append(record)
        # Giới hạn size
        if len(self._records) > self._max_size:
            self._records.pop(0)

    def get_last(self, n: int = 10) -> list[CalculationRecord]:
        return self._records[-n:]

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)


# calculator/operations/basic.py
# TODO: Implement các functions sau với proper error handling:
# - add(*args: float) -> float  (cộng nhiều số)
# - subtract(a: float, b: float) -> float
# - multiply(*args: float) -> float
# - divide(a: float, b: float) -> float  (raise DivisionByZeroError nếu b == 0)


# calculator/operations/advanced.py
# TODO: Implement:
# - power(base: float, exponent: float) -> float
# - sqrt(n: float) -> float  (raise NegativeSquareRootError nếu n < 0)
# - factorial(n: int) -> int  (raise ValueError nếu n < 0 hoặc không phải int)
# - fibonacci(n: int) -> int  (số fibonacci thứ n, dùng @lru_cache)


# calculator/operations/__init__.py
# TODO: Re-export tất cả operations
# __all__ = [...]


# calculator/__init__.py
# TODO: Define public API và calculate() dispatch function

# Public API
from .operations import add, subtract, multiply, divide, power, sqrt, factorial, fibonacci
from .history import CalculationHistory, CalculationRecord
from .exceptions import CalculatorError, DivisionByZeroError, NegativeSquareRootError

__version__ = "1.0.0"
__all__ = [
    "calculate",
    "CalculationHistory",
    "CalculationRecord",
    "CalculatorError",
    "DivisionByZeroError",
    "NegativeSquareRootError",
    # Operations
    "add", "subtract", "multiply", "divide",
    "power", "sqrt", "factorial", "fibonacci",
]

# Global history instance
_history = CalculationHistory()


def calculate(operation: str, *args: float) -> float:
    """
    Dispatch function — thực hiện phép tính theo tên operation.

    Usage:
        result = calculate("add", 1, 2, 3)        # 6
        result = calculate("divide", 10, 2)        # 5.0
        result = calculate("sqrt", 16)             # 4.0
        result = calculate("factorial", 5)         # 120

    Raises:
        InvalidOperationError: nếu operation không tồn tại
        CalculatorError: nếu có lỗi tính toán
    """
    # TODO: Implement dispatch
    pass


def get_history() -> CalculationHistory:
    """Lấy global calculation history."""
    return _history
```

**Test file — tất cả phải pass:**

```python
# test_calculator.py
import pytest
import math
from calculator import calculate, get_history, CalculationHistory
from calculator import add, subtract, multiply, divide, sqrt, factorial
from calculator.exceptions import (
    CalculatorError, DivisionByZeroError,
    NegativeSquareRootError, InvalidOperationError
)


class TestBasicOperations:
    def test_add(self):
        assert add(1, 2) == 3
        assert add(1, 2, 3, 4) == 10

    def test_subtract(self):
        assert subtract(5, 3) == 2
        assert subtract(0, 5) == -5

    def test_multiply(self):
        assert multiply(2, 3) == 6
        assert multiply(2, 3, 4) == 24

    def test_divide(self):
        assert divide(10, 2) == 5.0
        assert divide(1, 3) == pytest.approx(1/3)

    def test_divide_by_zero(self):
        with pytest.raises(DivisionByZeroError):
            divide(5, 0)


class TestAdvancedOperations:
    def test_sqrt(self):
        assert sqrt(16) == 4.0
        assert sqrt(2) == pytest.approx(math.sqrt(2))

    def test_sqrt_negative(self):
        with pytest.raises(NegativeSquareRootError):
            sqrt(-1)

    def test_factorial(self):
        assert factorial(0) == 1
        assert factorial(5) == 120

    def test_factorial_negative(self):
        with pytest.raises(ValueError):
            factorial(-1)


class TestCalculateDispatch:
    def test_add_dispatch(self):
        assert calculate("add", 1, 2, 3) == 6

    def test_invalid_operation(self):
        with pytest.raises(InvalidOperationError):
            calculate("unknown_op", 1, 2)


class TestHistory:
    def test_history_records(self):
        history = get_history()
        initial_len = len(history)
        calculate("add", 5, 10)
        assert len(history) == initial_len + 1

    def test_history_last(self):
        calculate("multiply", 3, 4)
        last = get_history().get_last(1)[0]
        assert last.operation == "multiply"
        assert last.result == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Bài 2: Structlog với Request ID Context

**Mô tả:** Implement một logging system với `structlog` hỗ trợ automatic request ID injection cho tất cả log messages trong một request context. Mô phỏng FastAPI middleware pattern.

**Yêu cầu:**
- Setup structlog với JSON output cho production, console output cho development
- Middleware function bind `request_id`, `user_id`, `endpoint` vào context
- Tất cả logs trong cùng "request" đều tự động có request context
- Custom processor thêm `app_version` và `environment`
- Async-safe dùng `contextvars`

```python
import asyncio
import uuid
import structlog
import structlog.contextvars
from typing import Callable, Any
from dataclasses import dataclass


# ============================================================
# Setup logging
# ============================================================

def setup_logging(environment: str = "development", app_version: str = "1.0.0") -> None:
    """
    Configure structlog.

    TODO: Implement với:
    - shared_processors bao gồm: merge_contextvars, add_log_level, TimeStamper
    - Custom processor inject app_version và environment vào mọi log
    - JSON renderer cho production, ConsoleRenderer cho development
    """
    pass


# ============================================================
# Custom processor
# ============================================================

def add_app_context(
    logger: Any,
    method_name: str,
    event_dict: dict,
    *,
    app_version: str,
    environment: str,
) -> dict:
    """
    Custom structlog processor.

    TODO: Add app_version và environment vào event_dict.
    Sử dụng functools.partial để bind app_version và environment.
    """
    pass


# ============================================================
# Request simulation
# ============================================================

@dataclass
class MockRequest:
    method: str
    path: str
    user_id: str | None = None


async def handle_request(request: MockRequest) -> dict:
    """
    Simulate xử lý HTTP request với logging.

    TODO: Implement:
    1. Bind request context vào contextvars (request_id, method, path, user_id)
    2. Log "request_started"
    3. Simulate business logic với logging
    4. Log "request_completed" với duration
    5. Clear context sau khi xong
    """
    logger = structlog.get_logger("request_handler")
    request_id = str(uuid.uuid4())[:8]

    # TODO: setup context, log, process, cleanup
    pass


async def get_user(user_id: str) -> dict:
    """
    Simulate service call — logs nên tự động có request context.

    TODO: Log "fetching_user" và "user_fetched" với user_id.
    Context từ contextvars sẽ tự động được inject.
    """
    logger = structlog.get_logger("user_service")
    # TODO: implement
    pass


async def send_notification(user_id: str, message: str) -> None:
    """Simulate notification service."""
    logger = structlog.get_logger("notification_service")
    # TODO: Log notification sent
    pass


# ============================================================
# Concurrent requests demo
# ============================================================

async def run_concurrent_requests():
    """
    Chạy nhiều requests đồng thời — mỗi request có context riêng.
    Đây là điểm mấu chốt: asyncio + contextvars = per-coroutine context.
    """
    requests = [
        MockRequest("GET", "/api/users/1", user_id="user-1"),
        MockRequest("POST", "/api/users", user_id=None),
        MockRequest("GET", "/api/users/2", user_id="user-2"),
        MockRequest("DELETE", "/api/users/3", user_id="admin"),
    ]

    # Chạy concurrent — mỗi request có request_id riêng trong logs
    results = await asyncio.gather(*[handle_request(req) for req in requests])
    return results


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    # Setup
    setup_logging(environment="development", app_version="1.2.3")

    logger = structlog.get_logger("main")
    logger.info("Application starting", service="myapp")

    # Run concurrent requests
    results = asyncio.run(run_concurrent_requests())

    logger.info("All requests completed", count=len(results))

    # Expected: logs cho mỗi request có request_id riêng,
    # nhưng service logs (user_service, notification_service)
    # cũng có cùng request_id của request đang xử lý
```

**Expected output format (JSON):**
```json
{"event": "request_started", "request_id": "a1b2c3d4", "method": "GET", "path": "/api/users/1", "user_id": "user-1", "level": "info", "timestamp": "..."}
{"event": "fetching_user", "request_id": "a1b2c3d4", "user_id": "user-1", "level": "debug", "timestamp": "..."}
{"event": "user_fetched", "request_id": "a1b2c3d4", "user_id": "user-1", "found": true, "level": "info", "timestamp": "..."}
{"event": "request_completed", "request_id": "a1b2c3d4", "status": 200, "duration_ms": 15, "level": "info", "timestamp": "..."}
```

---

## Bài 3: Tạo Project CLI Tool Hoàn Chỉnh

**Mô tả:** Tạo một CLI tool `dataconv` để convert dữ liệu giữa các formats (CSV, JSON, YAML). Tool này là mini-project với project structure đầy đủ.

**Yêu cầu project structure:**

```
dataconv/
├── pyproject.toml
├── src/
│   └── dataconv/
│       ├── __init__.py       # version, __all__
│       ├── cli.py            # typer CLI entry point
│       ├── converters/
│       │   ├── __init__.py
│       │   ├── base.py       # Abstract BaseConverter
│       │   ├── csv_conv.py   # CSV reader/writer
│       │   └── json_conv.py  # JSON reader/writer
│       ├── core/
│       │   ├── __init__.py
│       │   ├── logging.py    # structlog setup
│       │   └── exceptions.py
│       └── models.py         # ConversionResult dataclass
└── tests/
    └── test_converters.py
```

**Starter code cho `cli.py`:**

```python
# src/dataconv/cli.py
"""
DataConv CLI Tool — Convert dữ liệu giữa CSV, JSON, YAML.

Usage:
    dataconv convert input.csv output.json
    dataconv convert data.json output.csv --pretty
    dataconv info input.csv
    dataconv validate input.json --schema schema.json
"""
import typer
from pathlib import Path
from typing import Annotated
import structlog

from .converters import get_converter, list_formats
from .core.logging import setup_logging
from .models import ConversionResult

app = typer.Typer(
    name="dataconv",
    help="Convert data between CSV, JSON, and YAML formats",
    add_completion=True,
)

logger = structlog.get_logger(__name__)


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
    log_format: Annotated[str, typer.Option(help="Log format: json or console")] = "console",
):
    """DataConv — Data format converter."""
    setup_logging(
        log_level="DEBUG" if verbose else "INFO",
        log_format=log_format,
    )


@app.command()
def convert(
    input_file: Annotated[Path, typer.Argument(help="Input file path")],
    output_file: Annotated[Path, typer.Argument(help="Output file path")],
    pretty: Annotated[bool, typer.Option("--pretty", "-p", help="Pretty print output")] = False,
    delimiter: Annotated[str, typer.Option(help="CSV delimiter")] = ",",
):
    """
    Convert input file sang format của output file.

    Format được detect tự động từ file extension.

    TODO: Implement:
    1. Detect input/output format từ file extension
    2. Validate input file tồn tại
    3. Load input file dùng appropriate converter
    4. Save sang output file dùng appropriate converter
    5. Log conversion stats (rows, columns, duration)
    """
    logger.info("Starting conversion", input=str(input_file), output=str(output_file))

    if not input_file.exists():
        typer.echo(f"Error: File not found: {input_file}", err=True)
        raise typer.Exit(1)

    # TODO: Implement conversion logic
    pass


@app.command()
def info(
    file: Annotated[Path, typer.Argument(help="File to inspect")],
):
    """Show information about a data file."""
    # TODO: Implement — show rows, columns, data types, sample data
    pass


@app.command("list-formats")
def list_formats_cmd():
    """List all supported formats."""
    formats = list_formats()
    typer.echo("Supported formats:")
    for fmt in formats:
        typer.echo(f"  - {fmt}")


# Entry point
if __name__ == "__main__":
    app()
```

**Implement các converters:**

```python
# src/dataconv/converters/base.py
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Type


class BaseConverter(ABC):
    """Abstract base converter."""

    # Registry
    _registry: ClassVar[dict[str, Type["BaseConverter"]]] = {}

    def __init_subclass__(cls, extensions: list[str] | None = None, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if extensions:
            for ext in extensions:
                BaseConverter._registry[ext.lower()] = cls

    @classmethod
    def for_extension(cls, extension: str) -> "BaseConverter":
        """Get converter for file extension."""
        ext = extension.lower().lstrip(".")
        if ext not in cls._registry:
            from dataconv.core.exceptions import UnsupportedFormatError
            raise UnsupportedFormatError(f"Unsupported format: .{ext}")
        return cls._registry[ext]()

    @abstractmethod
    def read(self, filepath: str) -> list[dict[str, Any]]:
        """Read file và return list of dicts."""
        ...

    @abstractmethod
    def write(self, data: list[dict[str, Any]], filepath: str, **kwargs) -> None:
        """Write data to file."""
        ...


# TODO: Implement CSVConverter(BaseConverter, extensions=["csv"]):
# - read(): dùng csv.DictReader
# - write(): dùng csv.DictWriter

# TODO: Implement JSONConverter(BaseConverter, extensions=["json"]):
# - read(): dùng json.load
# - write(): dùng json.dump với optional indent

# TODO: Implement YAMLConverter nếu pyyaml installed:
# try:
#     import yaml
#     class YAMLConverter(BaseConverter, extensions=["yaml", "yml"]):
#         ...
# except ImportError:
#     pass  # YAML support not available


# src/dataconv/models.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversionResult:
    input_file: str
    output_file: str
    rows_converted: int
    columns: list[str]
    duration_ms: float
    timestamp: datetime

    def summary(self) -> str:
        return (
            f"Converted {self.rows_converted} rows × {len(self.columns)} columns\n"
            f"From: {self.input_file}\n"
            f"To: {self.output_file}\n"
            f"Duration: {self.duration_ms:.1f}ms"
        )
```

**pyproject.toml cho CLI tool:**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dataconv"
version = "0.1.0"
description = "Data format converter CLI"
requires-python = ">=3.12"
dependencies = [
    "typer[all]>=0.12.3",
    "structlog>=24.1.0",
    "pyyaml>=6.0.1",
]

[project.scripts]
dataconv = "dataconv.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/dataconv"]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.10"]

[tool.uv]
default-groups = ["dev"]
```

**Smoke commands bắt buộc trước khi coi bài xong:**

```bash
uv sync
uv run dataconv --help
uv run pytest
uv run ruff check src tests
uv run mypy src
```

**Test file:**

```python
# tests/test_converters.py
import pytest
import json
import csv
import io
from pathlib import Path
import tempfile

from dataconv.converters.base import BaseConverter
from dataconv.converters.csv_conv import CSVConverter
from dataconv.converters.json_conv import JSONConverter


SAMPLE_DATA = [
    {"name": "Alice", "age": "30", "city": "Hanoi"},
    {"name": "Bob", "age": "25", "city": "HCMC"},
    {"name": "Charlie", "age": "35", "city": "Da Nang"},
]


class TestCSVConverter:
    def test_write_and_read(self, tmp_path: Path):
        filepath = str(tmp_path / "test.csv")
        converter = CSVConverter()
        converter.write(SAMPLE_DATA, filepath)
        result = converter.read(filepath)
        assert result == SAMPLE_DATA

    def test_registry(self):
        converter = BaseConverter.for_extension(".csv")
        assert isinstance(converter, CSVConverter)


class TestJSONConverter:
    def test_write_and_read(self, tmp_path: Path):
        filepath = str(tmp_path / "test.json")
        converter = JSONConverter()
        converter.write(SAMPLE_DATA, filepath, indent=2)
        result = converter.read(filepath)
        assert result == SAMPLE_DATA

    def test_registry(self):
        converter = BaseConverter.for_extension(".json")
        assert isinstance(converter, JSONConverter)


class TestConversion:
    def test_csv_to_json(self, tmp_path: Path):
        """Full conversion: CSV → JSON."""
        csv_file = str(tmp_path / "input.csv")
        json_file = str(tmp_path / "output.json")

        CSVConverter().write(SAMPLE_DATA, csv_file)
        data = CSVConverter().read(csv_file)
        JSONConverter().write(data, json_file, indent=2)

        with open(json_file) as f:
            result = json.load(f)
        assert result == SAMPLE_DATA

    def test_unsupported_format(self):
        from dataconv.core.exceptions import UnsupportedFormatError
        with pytest.raises(UnsupportedFormatError):
            BaseConverter.for_extension(".xlsx")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```
