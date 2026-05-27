# Ngày 04: Functions Nâng Cao

## 🎯 Mục tiêu học tập

- Hiểu first-class functions và closures trong Python, so sánh với JavaScript closures
- Viết decorators từ cơ bản đến nâng cao (với params, stacking, type-safe)
- Sử dụng generator functions để xử lý dữ liệu lớn hiệu quả
- Thành thạo `functools` module: `partial`, `lru_cache`, `reduce`, `cached_property`
- Phân biệt khi nào dùng decorator vs higher-order function vs generator

**Scope 2 giờ cho ngày này:**
- **Must Learn:** closures + `nonlocal`, decorator cơ bản với `@functools.wraps`, generator basics, `lru_cache`/`cached_property`.
- **Skim:** decorator có parameters, stacking decorators, generator pipeline nhỏ.
- **Optional Reference:** retry/backoff decorator, `ParamSpec` type-safe decorator, `reduce`, pipeline framework/fluent interface.

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Decorator | `@decorator` (TC39 proposal, chỉ class/method) | `@decorator` (áp dụng cho mọi function) |
| Higher-order function | `const fn = (x: number) => (y: number) => x + y` | `def fn(x): return lambda y: x + y` |
| Generator | `function* gen() { yield 1; }` | `def gen(): yield 1` |
| Async generator | `async function* gen() { yield await ... }` | `async def gen(): yield await ...` |
| Partial application | `fn.bind(null, arg)` hoặc lodash `_.partial` | `functools.partial(fn, arg)` |
| Memoize | lodash `_.memoize` | `@functools.lru_cache` |
| Compose | Không có built-in, dùng `pipe` từ ramda | Không có built-in, tự implement |
| `nonlocal` | Không cần (closure tự động) | Cần `nonlocal` để gán lại biến closure |

**Điểm khác biệt quan trọng:**
- JS: closures tự động capture và modify biến outer scope
- Python: closures **đọc** được biến outer, nhưng muốn **gán lại** phải dùng `nonlocal`
- Python decorators là pure Python (không cần compiler magic), chỉ là syntactic sugar cho `fn = decorator(fn)`
- Python generators dùng `yield`, JS dùng `yield` nhưng syntax khác nhau ở cách consume

---

## 📖 Lý thuyết

### 1. First-Class Functions và Closures

**WHY:** Closures là nền tảng của decorators, factories, và functional programming trong Python. NodeJS developer đã quen với closures, nhưng Python có một số quirks khác.

**Closure cơ bản:**

```python
# JavaScript equivalent:
# function makeCounter() {
#   let count = 0;
#   return () => ++count;
# }

def make_counter(start: int = 0):
    count = start  # biến trong outer scope

    def increment() -> int:
        nonlocal count  # QUAN TRỌNG: phải khai báo nonlocal để gán lại
        count += 1
        return count

    def decrement() -> int:
        nonlocal count
        count -= 1
        return count

    def reset() -> None:
        nonlocal count
        count = start

    def get() -> int:
        return count  # chỉ đọc, không cần nonlocal

    # Trả về một "object" thông qua dict (hoặc có thể dùng class)
    return {
        "increment": increment,
        "decrement": decrement,
        "reset": reset,
        "get": get,
    }


counter = make_counter(10)
print(counter["increment"]())  # 11
print(counter["increment"]())  # 12
print(counter["decrement"]())  # 11
print(counter["get"]())        # 11
counter["reset"]()
print(counter["get"]())        # 10
```

**Closure factory — make_multiplier:**

```python
from typing import Callable

def make_multiplier(factor: float) -> Callable[[float], float]:
    """Factory tạo ra hàm nhân với factor cố định."""
    def multiplier(x: float) -> float:
        return x * factor  # chỉ đọc factor, không cần nonlocal
    return multiplier


double = make_multiplier(2)
triple = make_multiplier(3)
halve  = make_multiplier(0.5)

print(double(5))   # 10.0
print(triple(5))   # 15.0
print(halve(10))   # 5.0

# Dùng trong map/filter (functional style)
numbers = [1, 2, 3, 4, 5]
doubled = list(map(double, numbers))
print(doubled)  # [2.0, 4.0, 6.0, 8.0, 10.0]
```

**Classic closure gotcha — late binding:**

```python
# BUG: Late binding trong loop
funcs_bad = [lambda x: x * i for i in range(5)]
print([f(1) for f in funcs_bad])  # [4, 4, 4, 4, 4] ← SAI!

# FIX 1: Capture giá trị tại thời điểm tạo
funcs_good = [lambda x, i=i: x * i for i in range(5)]
print([f(1) for f in funcs_good])  # [0, 1, 2, 3, 4] ← ĐÚNG

# FIX 2: Dùng functools.partial
from functools import partial

def multiply(x: int, factor: int) -> int:
    return x * factor

funcs_partial = [partial(multiply, factor=i) for i in range(5)]
print([f(1) for f in funcs_partial])  # [0, 1, 2, 3, 4] ← ĐÚNG
```

---

### 2. Decorators

**WHY:** Decorators là một trong những pattern phổ biến nhất trong Python ecosystem. FastAPI, Flask, pytest, Celery đều dùng decorators. NodeJS developer có thể quen với TS decorators (experimental), nhưng Python decorators khác: chúng là pure functions, không cần compiler plugin.

**Cơ chế hoạt động:**

```python
# Decorator là syntactic sugar:
# @decorator
# def func(): ...
# Tương đương với: func = decorator(func)

# Ví dụ không dùng @ syntax:
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Before")
        result = func(*args, **kwargs)
        print("After")
        return result
    return wrapper

def greet(name: str) -> str:
    return f"Hello, {name}!"

greet = my_decorator(greet)  # Không dùng @
print(greet("Alice"))
# Before
# Hello, Alice!
# After
```

**Basic decorator với `@functools.wraps`:**

```python
import functools
import time
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def timer(func: Callable[P, T]) -> Callable[P, T]:
    """Đo thời gian thực thi của một function."""

    @functools.wraps(func)  # Giữ nguyên __name__, __doc__, __module__
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.perf_counter() - start
            print(f"[{func.__name__}] took {elapsed:.4f}s")

    return wrapper


@timer
def slow_function(n: int) -> int:
    """Tính tổng từ 1 đến n."""
    time.sleep(0.1)
    return sum(range(n))


result = slow_function(1000)
print(result)
# [slow_function] took 0.1002s
# 499500

# Kiểm tra functools.wraps hoạt động đúng
print(slow_function.__name__)   # "slow_function" (không phải "wrapper")
print(slow_function.__doc__)    # "Tính tổng từ 1 đến n."
```

**Decorator với parameters (skim trong 2 giờ):**

Ví dụ `retry` dưới đây là pattern production quan trọng, nhưng ở Day 04 chỉ cần hiểu shape `decorator factory -> decorator -> wrapper`. Backoff/jitter/async retry nên để sang optional lab hoặc ngày review, không cần học thuộc ngay.

```python
import functools
import time
import random
from typing import Callable, TypeVar, ParamSpec, Type

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator retry với cấu hình linh hoạt.

    Args:
        max_attempts: Số lần thử tối đa
        delay: Thời gian chờ giữa các lần thử (giây)
        exceptions: Tuple các exception types sẽ được retry

    Usage:
        @retry(max_attempts=3, delay=0.5, exceptions=(ConnectionError, TimeoutError))
        def call_api():
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = delay * (2 ** (attempt - 1))  # exponential backoff
                        print(f"Attempt {attempt}/{max_attempts} failed: {e}. "
                              f"Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"All {max_attempts} attempts failed.")

            raise last_exception  # type: ignore

        return wrapper
    return decorator


@retry(max_attempts=3, delay=0.1, exceptions=(ConnectionError,))
def unstable_api_call(url: str) -> dict:
    """Simulate một API call không ổn định."""
    if random.random() < 0.7:  # 70% chance of failure
        raise ConnectionError(f"Cannot connect to {url}")
    return {"status": "success", "url": url}


# Test
try:
    result = unstable_api_call("https://api.example.com/data")
    print(result)
except ConnectionError as e:
    print(f"Final failure: {e}")
```

**Stacking decorators:**

```python
import functools
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_calls(func):
    """Log function calls với arguments."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        result = func(*args, **kwargs)
        logger.info(f"{func.__name__} returned {result}")
        return result
    return wrapper


def validate_positive(func):
    """Validate rằng tất cả numeric arguments đều dương."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, (int, float)) and arg <= 0:
                raise ValueError(f"Expected positive number, got {arg}")
        return func(*args, **kwargs)
    return wrapper


def cache_result(func):
    """Simple cache decorator."""
    cache: dict = {}
    @functools.wraps(func)
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper


# Stacking: thứ tự áp dụng từ dưới lên (gần function nhất áp dụng trước)
# Thứ tự thực thi: log_calls → validate_positive → cache_result → func
@log_calls          # 3. Áp dụng cuối cùng (outermost)
@validate_positive  # 2. Áp dụng giữa
@cache_result       # 1. Áp dụng đầu tiên (innermost, gần func nhất)
def expensive_compute(n: int) -> int:
    """Giả lập tính toán tốn kém."""
    time.sleep(0.01)
    return n ** 2


# Lần 1: tính toán + log
result1 = expensive_compute(5)
# Lần 2: từ cache + log
result2 = expensive_compute(5)
print(result1, result2)  # 25 25
```

**Type-safe decorator với ParamSpec và TypeVar (optional deep dive):**

```python
from typing import Callable, TypeVar, ParamSpec, Concatenate
import functools

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


def add_logging(func: Callable[P, T]) -> Callable[P, T]:
    """Type-safe decorator: giữ nguyên signature của function."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"Done {func.__name__}")
        return result
    return wrapper


@add_logging
def add(x: int, y: int) -> int:
    return x + y


# mypy/pyright sẽ hiểu đúng type của result
result: int = add(1, 2)  # Type: int, không phải Any
```

---

### 3. Generator Functions

**WHY:** Generators cho phép xử lý data streams lớn mà không cần load hết vào memory. Đây là pattern cực kỳ quan trọng khi làm việc với files, database cursors, hoặc API pagination. NodeJS developer quen với `async generator` hoặc `stream`, Python generators tương tự nhưng synchronous mặc định.

**Generator cơ bản — fibonacci vô hạn:**

```python
from typing import Generator, Iterator
import itertools


def fibonacci() -> Generator[int, None, None]:
    """
    Infinite Fibonacci generator.

    Generator[YieldType, SendType, ReturnType]
    - YieldType: int (giá trị yield ra)
    - SendType: None (không nhận giá trị send)
    - ReturnType: None (không có return value)
    """
    a, b = 0, 1
    while True:  # Vô hạn! Nhưng chỉ tính khi cần
        yield a
        a, b = b, a + b


# Lấy 10 số fibonacci đầu tiên
fib = fibonacci()
first_10 = [next(fib) for _ in range(10)]
print(first_10)  # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

# Dùng itertools.islice để lấy n phần tử từ infinite generator
from itertools import islice, takewhile

first_20 = list(islice(fibonacci(), 20))
print(first_20)

# Fibonacci nhỏ hơn 100
under_100 = list(takewhile(lambda x: x < 100, fibonacci()))
print(under_100)  # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
```

**Generator cho file lớn:**

```python
from pathlib import Path
from typing import Iterator


def read_large_file(filepath: str | Path, chunk_size: int = 8192) -> Iterator[str]:
    """
    Đọc file lớn theo từng dòng — memory efficient.

    Thay vì: lines = file.readlines()  ← Load hết vào memory
    Dùng generator: chỉ giữ 1 dòng trong memory tại một thời điểm.
    """
    with open(filepath, encoding="utf-8") as f:
        for line in f:  # File object tự là iterator
            yield line.rstrip("\n")


def read_csv_chunks(filepath: str | Path, chunk_size: int = 1000) -> Iterator[list[str]]:
    """Đọc CSV theo chunks."""
    chunk: list[str] = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            chunk.append(line.rstrip("\n"))
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
    if chunk:  # Yield chunk cuối nếu còn
        yield chunk


# Ví dụ sử dụng (giả sử có file large.txt)
# for line in read_large_file("large.txt"):
#     process(line)
#
# for chunk in read_csv_chunks("large.csv", chunk_size=500):
#     bulk_insert(chunk)
```

**`yield from` — delegation:**

```python
from typing import Iterator, Iterable


def flatten(nested: Iterable) -> Iterator:
    """
    Flatten nested iterables đệ quy.
    `yield from` delegates iteration sang sub-generator.
    """
    for item in nested:
        if isinstance(item, (list, tuple, set)):
            yield from flatten(item)  # Delegate sang recursive call
        else:
            yield item


data = [1, [2, 3, [4, 5]], 6, [[7, 8], 9]]
print(list(flatten(data)))  # [1, 2, 3, 4, 5, 6, 7, 8, 9]


def chain_generators(*iterables: Iterable) -> Iterator:
    """Nối nhiều iterables lại — custom implementation của itertools.chain."""
    for iterable in iterables:
        yield from iterable  # yield from thay cho: for item in iterable: yield item


result = list(chain_generators([1, 2], [3, 4], [5, 6]))
print(result)  # [1, 2, 3, 4, 5, 6]
```

**Generator pipeline — functional data processing:**

```python
from typing import Iterator, Callable
import re


# Mỗi bước trong pipeline là một generator
def read_lines(filepath: str) -> Iterator[str]:
    """Source: đọc từ file."""
    with open(filepath, encoding="utf-8") as f:
        yield from f


def skip_comments(lines: Iterator[str]) -> Iterator[str]:
    """Filter: bỏ qua comment lines."""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield stripped


def parse_csv_line(lines: Iterator[str]) -> Iterator[list[str]]:
    """Transform: parse mỗi line thành list fields."""
    for line in lines:
        yield line.split(",")


def filter_by_column(
    rows: Iterator[list[str]],
    col_index: int,
    value: str,
) -> Iterator[list[str]]:
    """Filter: lọc theo giá trị cột."""
    for row in rows:
        if len(row) > col_index and row[col_index].strip() == value:
            yield row


def to_dict(rows: Iterator[list[str]], headers: list[str]) -> Iterator[dict[str, str]]:
    """Transform: chuyển list thành dict."""
    for row in rows:
        yield dict(zip(headers, (field.strip() for field in row)))


# Kết hợp thành pipeline — lazy evaluation, chỉ chạy khi iterate
def process_sales_csv(filepath: str) -> Iterator[dict[str, str]]:
    lines = read_lines(filepath)
    lines = skip_comments(lines)
    rows = parse_csv_line(lines)
    # Giả sử header ở dòng đầu tiên
    headers = next(rows)  # type: ignore
    # Filter chỉ lấy sales từ "Vietnam"
    filtered = filter_by_column(rows, col_index=3, value="Vietnam")
    return to_dict(filtered, headers)


# Không cần file thực để demo pipeline concept:
def demo_pipeline():
    """Demo pipeline với data in-memory."""
    data = iter([
        "name,amount,currency,country",
        "Alice,100,USD,USA",
        "# This is a comment",
        "Bob,200,USD,Vietnam",
        "Charlie,150,EUR,France",
        "Dave,300,USD,Vietnam",
    ])

    lines = skip_comments(data)
    rows = parse_csv_line(lines)
    headers = next(rows)
    vietnam_rows = filter_by_column(rows, col_index=3, value="Vietnam")
    result = list(to_dict(vietnam_rows, headers))
    print(result)
    # [{'name': 'Bob', 'amount': '200', 'currency': 'USD', 'country': 'Vietnam'},
    #  {'name': 'Dave', 'amount': '300', 'currency': 'USD', 'country': 'Vietnam'}]


demo_pipeline()
```

**Generator expression (so sánh với list comprehension):**

```python
import sys

# List comprehension: tính toán ngay, lưu hết vào memory
squares_list = [x**2 for x in range(10_000_000)]
print(f"List size: {sys.getsizeof(squares_list):,} bytes")  # ~85,176,224 bytes (~85MB)

# Generator expression: lazy, chỉ tính khi cần
squares_gen = (x**2 for x in range(10_000_000))
print(f"Generator size: {sys.getsizeof(squares_gen)} bytes")  # 104 bytes

# Cả hai cho cùng kết quả khi sum
total = sum(x**2 for x in range(1000))  # Generator expression trong function call
print(total)  # 332833500
```

---

### 4. functools Module

Trong 2 giờ, ưu tiên `partial`, `lru_cache`/`cache`, và `cached_property`. `reduce` hữu ích để đọc legacy/functional code, nhưng không cần dùng làm default style trong Python production.

**WHY:** `functools` là standard library module chứa các utilities cực kỳ hữu ích cho functional programming, caching, và function composition.

**`partial` — partial application:**

```python
from functools import partial
from typing import Callable


def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: str = "noreply@example.com",
    cc: list[str] | None = None,
) -> None:
    cc_str = ", ".join(cc) if cc else "none"
    print(f"Sending email: {from_addr} → {to}")
    print(f"  Subject: {subject}")
    print(f"  CC: {cc_str}")
    print(f"  Body: {body[:50]}...")


# Tạo specialized functions từ generic function
send_notification = partial(
    send_email,
    from_addr="notifications@example.com",
)

send_alert = partial(
    send_email,
    from_addr="alerts@example.com",
    subject="[ALERT] System notification",
)

# Sử dụng
send_notification(
    to="user@example.com",
    subject="Your order is ready",
    body="Your order #1234 has been processed.",
)

send_alert(
    to="admin@example.com",
    body="CPU usage exceeded 90%",
)

# Partial với positional args
add = lambda x, y: x + y
add_5 = partial(add, 5)  # Fix first arg = 5
print(add_5(3))   # 8
print(add_5(10))  # 15
```

**`lru_cache` và `cache` — memoization:**

```python
from functools import lru_cache, cache
import time


# @cache = @lru_cache(maxsize=None) — unlimited cache (Python 3.9+)
@cache
def fibonacci_cached(n: int) -> int:
    """Fibonacci với memoization — O(n) thay vì O(2^n)."""
    if n < 2:
        return n
    return fibonacci_cached(n - 1) + fibonacci_cached(n - 2)


# So sánh performance
def fibonacci_naive(n: int) -> int:
    if n < 2:
        return n
    return fibonacci_naive(n - 1) + fibonacci_naive(n - 2)


start = time.perf_counter()
result = fibonacci_cached(35)
print(f"Cached: {result} in {time.perf_counter() - start:.6f}s")

start = time.perf_counter()
result = fibonacci_naive(35)
print(f"Naive:  {result} in {time.perf_counter() - start:.6f}s")

# Xem cache stats
print(fibonacci_cached.cache_info())
# CacheInfo(hits=33, misses=36, maxsize=None, currsize=36)

# Clear cache nếu cần
fibonacci_cached.cache_clear()


# lru_cache với maxsize — giới hạn số entries
@lru_cache(maxsize=128)
def get_user_from_db(user_id: int) -> dict:
    """Simulate DB call với cache."""
    print(f"  [DB] Fetching user {user_id}...")
    time.sleep(0.01)  # Simulate DB latency
    return {"id": user_id, "name": f"User {user_id}"}


# Lần đầu: query DB; lần sau: từ cache
user = get_user_from_db(1)  # [DB] Fetching user 1...
user = get_user_from_db(1)  # Từ cache, không print
user = get_user_from_db(2)  # [DB] Fetching user 2...
print(get_user_from_db.cache_info())
# CacheInfo(hits=1, misses=2, maxsize=128, currsize=2)
```

**`cached_property` — lazy property:**

```python
from functools import cached_property
import statistics


class DataAnalyzer:
    """
    Class phân tích data với computed properties được cache.

    cached_property: tính toán lần đầu, cache kết quả vào instance.__dict__
    Khác với @property: không tính lại mỗi lần access
    """

    def __init__(self, data: list[float]):
        self._data = data

    @cached_property
    def mean(self) -> float:
        """Tính mean — expensive operation, cache kết quả."""
        print("  Computing mean...")
        return statistics.mean(self._data)

    @cached_property
    def std_dev(self) -> float:
        """Tính standard deviation."""
        print("  Computing std_dev...")
        return statistics.stdev(self._data)

    @cached_property
    def percentiles(self) -> dict[str, float]:
        """Tính các percentiles."""
        print("  Computing percentiles...")
        sorted_data = sorted(self._data)
        n = len(sorted_data)
        return {
            "p25": sorted_data[n // 4],
            "p50": sorted_data[n // 2],
            "p75": sorted_data[3 * n // 4],
            "p99": sorted_data[int(n * 0.99)],
        }


data = [float(i) for i in range(1, 10001)]
analyzer = DataAnalyzer(data)

print("First access:")
print(f"Mean: {analyzer.mean}")          # Computing mean... → 5000.5
print(f"Mean: {analyzer.mean}")          # Từ cache, không print
print(f"Std: {analyzer.std_dev:.2f}")    # Computing std_dev...
print(f"Percentiles: {analyzer.percentiles}")
```

**`reduce` — fold/aggregate (optional):**

```python
from functools import reduce
from typing import TypeVar, Callable

T = TypeVar("T")


# reduce(function, iterable, initial_value)
# NodeJS equivalent: array.reduce((acc, cur) => ..., initial)

numbers = [1, 2, 3, 4, 5]

# Sum (dùng reduce để illustrate — thực tế dùng sum())
total = reduce(lambda acc, x: acc + x, numbers, 0)
print(total)  # 15

# Product
product = reduce(lambda acc, x: acc * x, numbers, 1)
print(product)  # 120

# Flatten nested list
nested = [[1, 2], [3, 4], [5, 6]]
flat = reduce(lambda acc, x: acc + x, nested, [])
print(flat)  # [1, 2, 3, 4, 5, 6]

# Build dict từ list of tuples
pairs = [("a", 1), ("b", 2), ("c", 3)]
result = reduce(lambda acc, pair: {**acc, pair[0]: pair[1]}, pairs, {})
print(result)  # {'a': 1, 'b': 2, 'c': 3}

# Group by — complex reduce
from collections import defaultdict

data = [
    {"name": "Alice", "dept": "Engineering"},
    {"name": "Bob", "dept": "Marketing"},
    {"name": "Charlie", "dept": "Engineering"},
    {"name": "Dave", "dept": "Marketing"},
]

def group_by(iterable: list[dict], key: str) -> dict:
    def reducer(acc: dict, item: dict) -> dict:
        acc[item[key]].append(item)
        return acc
    return reduce(reducer, iterable, defaultdict(list))

grouped = group_by(data, "dept")
print(dict(grouped))
# {'Engineering': [{'name': 'Alice', ...}, {'name': 'Charlie', ...}],
#  'Marketing': [{'name': 'Bob', ...}, {'name': 'Dave', ...}]}
```

---

## ⚠️ Common Mistakes

| Mistake | Sai | Đúng |
|---------|-----|------|
| Quên `nonlocal` | `count += 1` trong closure → `UnboundLocalError` | `nonlocal count; count += 1` |
| Quên `@functools.wraps` | `wrapper.__name__ == "wrapper"` | Dùng `@functools.wraps(func)` |
| Mutable default arg | `def f(lst=[])` → shared state | `def f(lst=None): lst = lst or []` |
| Generator đã exhausted | `gen = gen_func(); list(gen); list(gen)` → `[]` | Tạo generator mới mỗi lần |
| `lru_cache` với mutable args | `@lru_cache def f(lst: list)` → `TypeError` | Chỉ dùng với hashable args |
| Late binding trong lambda | `[lambda: i for i in range(5)]` | `[lambda i=i: i for i in range(5)]` |

---

## ✅ Best Practices

**Decorators:**
- Luôn dùng `@functools.wraps` để preserve function metadata
- Dùng `ParamSpec` và `TypeVar` để giữ type safety
- Document behavior của decorator rõ ràng trong docstring
- Decorator nên transparent — không thay đổi behavior, chỉ thêm cross-cutting concerns

**Generators:**
- Dùng generator thay vì list khi xử lý data lớn hoặc infinite sequences
- Đặt tên generator function rõ ràng (thường dùng `iter_` prefix hoặc tên mô tả hành động)
- Xử lý cleanup trong `finally` block nếu generator có side effects

**functools:**
- Dùng `@cache` cho pure functions không cần giới hạn cache size
- Dùng `@lru_cache(maxsize=N)` khi memory là concern
- `cached_property` chỉ hoạt động với instances có `__dict__` (không dùng với `__slots__`)

---

## ⚖️ Trade-offs

| Pattern | Pros | Cons | Khi dùng |
|---------|------|------|-----------|
| Decorator | Separation of concerns, reusable, DRY | Debug khó hơn (stack trace phức tạp) | Logging, auth, retry, caching |
| Generator | Memory efficient, lazy evaluation | Cannot reuse, debug harder, no len() | Large data, streaming, pipelines |
| `lru_cache` | Fast repeated calls | Memory overhead, stale data | Pure functions, expensive computations |
| `partial` | Clean API, DRY | Less explicit | Factory functions, callback setup |
| Closure | Simple, encapsulation | State hidden, test harder | Counter, factory, config |

---

## 🚀 Performance Notes

```python
import timeit

# Generator expression vs list comprehension
gen_time = timeit.timeit(
    stmt="sum(x**2 for x in range(10000))",
    number=1000,
)
list_time = timeit.timeit(
    stmt="sum([x**2 for x in range(10000)])",
    number=1000,
)
print(f"Generator: {gen_time:.3f}s")  # Thường nhanh hơn hoặc tương đương
print(f"List:      {list_time:.3f}s")

# lru_cache speedup
def fib_no_cache(n):
    if n < 2: return n
    return fib_no_cache(n-1) + fib_no_cache(n-2)

@lru_cache(maxsize=None)
def fib_cached(n):
    if n < 2: return n
    return fib_cached(n-1) + fib_cached(n-2)

from functools import lru_cache
no_cache_time = timeit.timeit("fib_no_cache(30)", globals=globals(), number=10)
cached_time = timeit.timeit("fib_cached(30)", globals=globals(), number=10)
print(f"No cache: {no_cache_time:.4f}s")
print(f"Cached:   {cached_time:.6f}s")  # Cực kỳ nhanh sau lần đầu
```

**Khi nào NOT dùng:**
- Đừng dùng `@lru_cache` cho functions có side effects
- Đừng dùng generator khi cần random access (`gen[5]` không hoạt động)
- Đừng stack quá nhiều decorators (>3-4) — code khó debug

---

## 📝 Tóm tắt

| Concept | Key Point | NodeJS Analogy |
|---------|-----------|----------------|
| Closure + `nonlocal` | Cần khai báo `nonlocal` để gán lại biến outer scope | JS closure tự động |
| Decorator | Pure Python, syntactic sugar cho `f = d(f)` | TS decorators nhưng không cần compiler |
| `@functools.wraps` | Preserve `__name__`, `__doc__` — LUÔN dùng | Không cần trong JS |
| Generator | Lazy evaluation, memory efficient, dùng `yield` | `function*` + `yield` |
| `yield from` | Delegate sang sub-iterator/generator | `yield*` trong JS |
| `@lru_cache` | Memoization tự động, built-in | lodash `_.memoize` |
| `partial` | Fix một số arguments của function | `fn.bind(null, arg)` |
| `@cached_property` | Lazy computed property, cached vào `__dict__` | Getter với manual cache |
