# Ngày 04: Exercises — Functions Nâng Cao

## Scope & cách chạy

Trong 2 giờ, làm **Bài 1** và phần core của **Bài 2**. **Bài 3** là **Optional Reference**; đọc test cases để hiểu pattern retry, nhưng không cần hoàn thành nếu đang học đúng nhịp course.

Setup nhanh:

```bash
uv init day04-functions
cd day04-functions
uv add --dev mypy ruff
```

Mỗi bài nên đặt vào một file riêng để dễ chạy:

| Bài | File gợi ý | Command |
|-----|------------|---------|
| 1 | `validate_types.py` | `uv run python validate_types.py` |
| 2 | `sales_pipeline.py` | `uv run python sales_pipeline.py` |
| 3 optional | `retry_decorator.py` | `uv run python retry_decorator.py` |

## Bài 1: Decorator `validate_types`

**Mô tả:** Implement một decorator `validate_types` kiểm tra type annotations của function tại runtime. Decorator này sẽ inspect `__annotations__` của function và raise `TypeError` nếu argument không khớp với type hint.

**Yêu cầu:**
- Đọc `__annotations__` của function để lấy expected types
- Validate mỗi argument theo annotation tương ứng
- Raise `TypeError` với message rõ ràng khi type không khớp
- Bỏ qua `return` annotation (chỉ validate inputs)
- Hỗ trợ `Optional[T]` (cho phép `None`)
- Preserve function signature với `@functools.wraps`
- Acceptance: `uv run python validate_types.py` in đúng expected output bên dưới

**Starter code:**

```python
import functools
import inspect
from typing import get_type_hints, get_origin, get_args, Union, Optional


def validate_types(func):
    """
    Decorator kiểm tra type annotations tại runtime.

    Usage:
        @validate_types
        def add(x: int, y: int) -> int:
            return x + y

        add(1, 2)      # OK
        add(1, "2")    # TypeError: Argument 'y' expected int, got str
        add(1.5, 2)    # TypeError: Argument 'x' expected int, got float
    """
    # TODO: Implement decorator

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: Validate types
        return func(*args, **kwargs)

    return wrapper


# Test cases — tất cả phải chạy đúng:

@validate_types
def add(x: int, y: int) -> int:
    return x + y


@validate_types
def greet(name: str, times: int = 1) -> str:
    return (f"Hello, {name}!" + " ") * times


@validate_types
def process(data: list, flag: bool = False) -> None:
    pass


# Valid calls
print(add(1, 2))           # 3
print(greet("Alice"))      # "Hello, Alice! "
print(greet("Bob", 3))     # "Hello, Bob! Hello, Bob! Hello, Bob! "

# Invalid calls — phải raise TypeError
try:
    add(1, "2")
except TypeError as e:
    print(f"Caught: {e}")  # Expected: Argument 'y' expected int, got str

try:
    greet(123)
except TypeError as e:
    print(f"Caught: {e}")  # Expected: Argument 'name' expected str, got int
```

**Gợi ý:**
```python
# Lấy type hints (bao gồm cả resolved types)
hints = get_type_hints(func)

# Lấy parameter names theo thứ tự
sig = inspect.signature(func)
params = list(sig.parameters.keys())

# Kiểm tra Optional[T] = Union[T, None]
def is_optional(annotation) -> bool:
    return get_origin(annotation) is Union and type(None) in get_args(annotation)

# Kiểm tra isinstance với Union types
def get_base_type(annotation):
    if get_origin(annotation) is Union:
        return tuple(t for t in get_args(annotation) if t is not type(None))
    return (annotation,)
```

**Expected output:**
```
3
Hello, Alice!
Hello, Bob! Hello, Bob! Hello, Bob!
Caught: Argument 'y' expected <class 'int'>, got <class 'str'>
Caught: Argument 'name' expected <class 'str'>, got <class 'int'>
```

---

## Bài 2: Generator Pipeline — CSV Processing

**Mô tả:** Xây dựng một complete generator pipeline để xử lý file CSV lớn theo kiểu lazy evaluation. Pipeline sẽ: đọc CSV → parse → filter → transform → aggregate — mà không load toàn bộ file vào memory.

**Yêu cầu:**
- Mỗi bước là một generator function (lazy)
- Implement đủ 5 stages: read, parse, filter, transform, aggregate
- Core scope: chạy được pipeline từ file CSV thật và in summary
- Optional: viết `Pipeline` class để chain stages dễ dàng
- Optional: tính memory usage để chứng minh efficiency
- Acceptance: `uv run python sales_pipeline.py` tạo file test CSV, chạy pipeline, in summary có `count`, `total_usd`, `avg_usd`

**Task:** Xử lý sales data CSV với format:

```
order_id,customer_name,amount,currency,country,date
1,Alice,100.50,USD,Vietnam,2024-01-15
2,Bob,200.00,EUR,France,2024-01-16
3,Charlie,150.75,USD,Vietnam,2024-01-17
...
```

**Implement các generators:**

```python
import csv
import io
from typing import Iterator, Callable, Any
from dataclasses import dataclass
from decimal import Decimal
from datetime import date


@dataclass
class Order:
    order_id: int
    customer_name: str
    amount: Decimal
    currency: str
    country: str
    date: date


# Stage 1: Source generator
def read_csv_rows(filepath: str) -> Iterator[dict[str, str]]:
    """Đọc CSV file theo từng row, yield dict."""
    # TODO: Implement
    pass


# Stage 2: Transform generator
def parse_orders(rows: Iterator[dict[str, str]]) -> Iterator[Order]:
    """Convert raw dicts thành Order dataclass."""
    # TODO: Implement — xử lý conversion errors gracefully
    pass


# Stage 3: Filter generator
def filter_by_country(orders: Iterator[Order], country: str) -> Iterator[Order]:
    """Chỉ giữ orders từ một country cụ thể."""
    # TODO: Implement
    pass


def filter_by_min_amount(orders: Iterator[Order], min_amount: Decimal) -> Iterator[Order]:
    """Chỉ giữ orders có amount >= min_amount."""
    # TODO: Implement
    pass


# Stage 4: Transform generator
def convert_to_usd(orders: Iterator[Order], rates: dict[str, Decimal]) -> Iterator[Order]:
    """Convert amount sang USD theo exchange rates."""
    # TODO: Implement — tạo Order mới với amount đã convert
    pass


# Stage 5: Aggregation (terminates pipeline)
def calculate_summary(orders: Iterator[Order]) -> dict[str, Any]:
    """
    Aggregate toàn bộ pipeline thành summary stats.
    Đây là terminal operation — không phải generator.
    """
    # TODO: Tính total_amount, count, avg_amount, max_order, min_order
    pass


# Test với generated data
def generate_test_csv(n_rows: int = 10000) -> str:
    """Generate test CSV data in-memory."""
    import random
    import io

    countries = ["Vietnam", "USA", "France", "Germany", "Japan"]
    currencies = {"Vietnam": "VND", "USA": "USD", "France": "EUR", "Germany": "EUR", "Japan": "JPY"}
    names = ["Alice", "Bob", "Charlie", "Dave", "Eve"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_id", "customer_name", "amount", "currency", "country", "date"])

    for i in range(1, n_rows + 1):
        country = random.choice(countries)
        writer.writerow([
            i,
            random.choice(names),
            f"{random.uniform(10, 1000):.2f}",
            currencies[country],
            country,
            f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        ])

    output.seek(0)
    return output.getvalue()


# Chạy pipeline
EXCHANGE_RATES = {
    "USD": Decimal("1.0"),
    "EUR": Decimal("1.08"),
    "VND": Decimal("0.000041"),
    "JPY": Decimal("0.0067"),
}

# TODO: Viết code chạy full pipeline và print summary
# Expected output dạng:
# {
#     "count": 2847,
#     "total_usd": Decimal("145230.50"),
#     "avg_usd": Decimal("51.01"),
#     "max_order": Order(...),
#     "min_order": Order(...),
# }
```

**Runnable main gợi ý:**

```python
from pathlib import Path


def main() -> None:
    path = Path("sales.csv")
    path.write_text(generate_test_csv(1000), encoding="utf-8")

    rows = read_csv_rows(str(path))
    orders = parse_orders(rows)
    orders = filter_by_country(orders, "Vietnam")
    orders = filter_by_min_amount(orders, Decimal("100"))
    orders = convert_to_usd(orders, EXCHANGE_RATES)
    summary = calculate_summary(orders)

    print(summary)
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
```

**Advanced: Pipeline class (bonus):**

```python
class Pipeline:
    """
    Fluent interface cho generator pipeline.

    Usage:
        summary = (
            Pipeline.from_csv("sales.csv")
            .map(parse_orders)
            .filter(lambda o: o.country == "Vietnam")
            .filter(lambda o: o.amount >= Decimal("100"))
            .collect(calculate_summary)
        )
    """

    def __init__(self, source: Iterator):
        self._source = source

    @classmethod
    def from_csv(cls, filepath: str) -> "Pipeline":
        return cls(read_csv_rows(filepath))

    def map(self, transform: Callable) -> "Pipeline":
        # TODO: Apply transform generator
        pass

    def filter(self, predicate: Callable) -> "Pipeline":
        # TODO: Apply filter — có thể dùng generator expression
        pass

    def collect(self, aggregator: Callable) -> Any:
        # TODO: Terminal operation
        pass
```

---

## Bài 3: Retry Decorator với Exponential Backoff + Jitter (Optional)

**Mô tả:** Implement một production-grade `retry` decorator với exponential backoff và random jitter. Đây là pattern cực kỳ phổ biến khi làm việc với external APIs, databases, và microservices.

**Scope note:** Bài này vượt mức core của Day 04. Nếu chỉ có 2 giờ, đọc yêu cầu + test để hiểu API design, rồi quay lại sau khi đã học async/error handling.

**Yêu cầu:**
- Exponential backoff: `delay = base_delay * (2 ** attempt)`
- Jitter: thêm random noise để tránh thundering herd problem
- Configurable: max attempts, base delay, max delay, jitter factor
- Chỉ retry với specific exceptions (whitelist)
- Callback `on_retry` để hook vào retry events (cho logging)
- Support cả sync và async functions
- Type-safe với ParamSpec
- Acceptance: `uv run python retry_decorator.py` chạy demo và toàn bộ `unittest` pass

**Implement:**

```python
import asyncio
import functools
import random
import time
import logging
from typing import Callable, TypeVar, ParamSpec, Type, Awaitable
from dataclasses import dataclass, field

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration cho retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0       # giây
    max_delay: float = 60.0       # cap tối đa
    jitter_factor: float = 0.25   # ±25% random jitter
    exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )
    on_retry: Callable | None = None  # callback(attempt, exception, wait_time)


def calculate_backoff(config: RetryConfig, attempt: int) -> float:
    """
    Tính thời gian chờ với exponential backoff + jitter.

    Formula: min(base_delay * 2^attempt, max_delay) * (1 ± jitter_factor)

    Ví dụ với base_delay=1, max_delay=60, jitter_factor=0.25:
    - attempt 0: ~1.0s ± 0.25s  → [0.75, 1.25]
    - attempt 1: ~2.0s ± 0.5s   → [1.5, 2.5]
    - attempt 2: ~4.0s ± 1.0s   → [3.0, 5.0]
    - attempt 3: ~8.0s ± 2.0s   → [6.0, 10.0]
    - attempt 4: ~16.0s ± 4.0s  → [12.0, 20.0]
    """
    # TODO: Implement backoff calculation
    pass


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.25,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Retry decorator với exponential backoff + jitter.

    Usage:
        @retry(max_attempts=5, base_delay=0.5, exceptions=(ConnectionError, TimeoutError))
        def call_external_api(url: str) -> dict:
            ...

        # Với on_retry callback
        def log_retry(attempt: int, error: Exception, wait: float) -> None:
            logger.warning(f"Retry {attempt}: {error}, waiting {wait:.2f}s")

        @retry(max_attempts=3, on_retry=log_retry)
        def risky_operation() -> None:
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter_factor=jitter_factor,
        exceptions=exceptions,
        on_retry=on_retry,
    )

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # TODO: Implement sync retry logic
            pass

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # TODO: Implement async retry logic (dùng asyncio.sleep)
            pass

        # Return đúng wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper

    return decorator


# ============================================================
# Tests
# ============================================================

import unittest
from unittest.mock import Mock, patch, AsyncMock


class TestRetryDecorator(unittest.TestCase):

    def test_succeeds_on_first_try(self):
        """Function thành công ngay lần đầu — không retry."""
        mock_fn = Mock(return_value="success")

        @retry(max_attempts=3)
        def my_func():
            return mock_fn()

        result = my_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_fn.call_count, 1)

    def test_retries_on_failure(self):
        """Function thất bại 2 lần rồi thành công."""
        mock_fn = Mock(side_effect=[
            ConnectionError("timeout"),
            ConnectionError("timeout"),
            "success",
        ])

        @retry(max_attempts=3, base_delay=0, exceptions=(ConnectionError,))
        def my_func():
            return mock_fn()

        result = my_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_fn.call_count, 3)

    def test_raises_after_max_attempts(self):
        """Raise exception sau khi hết max_attempts."""
        mock_fn = Mock(side_effect=ConnectionError("always fails"))

        @retry(max_attempts=3, base_delay=0)
        def my_func():
            return mock_fn()

        with self.assertRaises(ConnectionError):
            my_func()

        self.assertEqual(mock_fn.call_count, 3)

    def test_does_not_retry_unspecified_exceptions(self):
        """Không retry exceptions không có trong whitelist."""
        mock_fn = Mock(side_effect=ValueError("validation error"))

        @retry(max_attempts=3, base_delay=0, exceptions=(ConnectionError,))
        def my_func():
            return mock_fn()

        with self.assertRaises(ValueError):
            my_func()

        self.assertEqual(mock_fn.call_count, 1)  # Chỉ gọi 1 lần, không retry

    def test_on_retry_callback(self):
        """on_retry callback được gọi đúng số lần."""
        retry_events = []

        def on_retry(attempt: int, error: Exception, wait: float) -> None:
            retry_events.append((attempt, str(error)))

        mock_fn = Mock(side_effect=[
            ConnectionError("error 1"),
            ConnectionError("error 2"),
            "success",
        ])

        @retry(max_attempts=3, base_delay=0, on_retry=on_retry)
        def my_func():
            return mock_fn()

        my_func()
        self.assertEqual(len(retry_events), 2)
        self.assertEqual(retry_events[0], (1, "error 1"))
        self.assertEqual(retry_events[1], (2, "error 2"))

    def test_backoff_calculation(self):
        """Verify backoff timing."""
        config = RetryConfig(base_delay=1.0, max_delay=60.0, jitter_factor=0)
        # Không có jitter: backoff chính xác
        self.assertAlmostEqual(calculate_backoff(config, 0), 1.0)
        self.assertAlmostEqual(calculate_backoff(config, 1), 2.0)
        self.assertAlmostEqual(calculate_backoff(config, 2), 4.0)
        self.assertAlmostEqual(calculate_backoff(config, 10), 60.0)  # Capped at max_delay

    def test_async_retry(self):
        """Async function cũng được retry đúng."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0, exceptions=(ConnectionError,))
        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("not ready")
            return "async success"

        result = asyncio.run(async_func())
        self.assertEqual(result, "async success")
        self.assertEqual(call_count, 3)


# Demo usage
def demo():
    call_count = 0

    retry_log = []
    def on_retry(attempt, error, wait_time):
        retry_log.append(f"Attempt {attempt} failed: {error}, retry in {wait_time:.3f}s")

    @retry(
        max_attempts=4,
        base_delay=0.1,
        max_delay=5.0,
        jitter_factor=0.1,
        exceptions=(ConnectionError, TimeoutError),
        on_retry=on_retry,
    )
    def unstable_service(url: str) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise ConnectionError(f"Service unavailable (attempt {call_count})")
        return {"data": "success", "attempts": call_count}

    try:
        result = unstable_service("https://api.example.com")
        print(f"Result: {result}")
        print("Retry log:")
        for entry in retry_log:
            print(f"  {entry}")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    demo()
    print("\nRunning tests...")
    unittest.main(argv=[""], exit=False, verbosity=2)
```

**Bonus challenge:** Implement `RetryBudget` — một shared budget giới hạn tổng số lần retry trên toàn hệ thống trong một khoảng thời gian:

```python
class RetryBudget:
    """
    Giới hạn tổng số lần retry để tránh cascading failures.

    Ví dụ: max 100 retries per minute trên toàn hệ thống.
    Nếu vượt quá budget, raise exception ngay thay vì retry.
    """
    def __init__(self, max_retries_per_window: int, window_seconds: float = 60.0):
        # TODO: Implement với sliding window hoặc token bucket
        pass

    def consume(self) -> bool:
        """Trả về True nếu còn budget, False nếu hết."""
        # TODO: Implement
        pass
```
