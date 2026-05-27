# Ngày 02: Python Syntax Cơ Bản

## 🎯 Mục tiêu học tập

- Nắm vững variables, types, type hints trong Python
- Thành thạo string formatting với f-strings
- Sử dụng control flow: if/elif/else, match/case (Python 3.10+)
- Viết loops hiệu quả với comprehensions
- Định nghĩa functions với args, kwargs, lambda
- Biết các regex pitfalls phổ biến: raw string, Unicode normalization, greedy matching

## 🔄 So sánh với NodeJS/TypeScript

| Khái niệm | TypeScript | Python |
|-----------|------------|--------|
| Variable declaration | `const x = 1; let y = 2` | `x = 1` (không có const/let) |
| Type annotation | `const x: number = 1` | `x: int = 1` |
| String interpolation | `` `Hello ${name}` `` | `f"Hello {name}"` |
| Null | `null` / `undefined` | `None` |
| Null check | `x !== null && x !== undefined` | `x is not None` |
| Ternary | `x > 0 ? 'pos' : 'neg'` | `'pos' if x > 0 else 'neg'` |
| Switch | `switch(x) { case 1: }` | `match x: case 1:` (3.10+) |
| For-of loop | `for (const x of arr)` | `for x in arr:` |
| Destructuring | `const [a, b] = arr` | `a, b = arr` |
| Spread | `[...arr]` | `[*arr]` |
| Default params | `function f(x = 10)` | `def f(x=10):` |
| Rest params | `function f(...args)` | `def f(*args):` |
| Named params | Object destructuring | `def f(**kwargs):` |
| Arrow function | `const f = (x) => x * 2` | `f = lambda x: x * 2` |

## 📖 Lý thuyết

### 1. Variables và Type Hints

**WHY:** Python dynamically typed nhưng type hints (3.5+) giúp IDE và mypy detect lỗi sớm. Type hints không enforce runtime (khác TypeScript compile-time check) nhưng là best practice quan trọng.

```python
# Python không cần khai báo type, nhưng NÊN dùng type hints
age: int = 25
price: float = 19.99
name: str = "Alice"
is_active: bool = True
nothing: None = None  # tương đương null trong JS

# Python 3.10+: dùng | thay vì Union
def process(value: int | str) -> str:
    return str(value)

# Optional[str] = str | None (trước 3.10)
from typing import Optional
def get_name(id: int) -> str | None:  # Python 3.10+
    return None

# Constants: Python không có const, convention là ALL_CAPS
MAX_RETRIES: int = 3
API_BASE_URL: str = "https://api.example.com"

# Type checking tại runtime (ít dùng)
print(type(age))              # <class 'int'>
print(isinstance(age, int))   # True — dùng cái này, không dùng type()
print(isinstance(age, (int, float)))  # check multiple types
```

### 2. String Formatting

**WHY:** f-strings (Python 3.6+) là cách hiện đại nhất, nhanh nhất. Tương đương template literals JS.

```python
name = "Alice"
age = 25
price = 19.99

# f-string — KHUYẾN DÙNG (giống template literals JS)
greeting = f"Hello, {name}! You are {age} years old."
formatted_price = f"Price: ${price:.2f}"  # 2 decimal places: $19.99

# Expressions trong f-string
result = f"2 + 2 = {2 + 2}"
upper_name = f"Upper: {name.upper()}"

# Debug với = (Python 3.8+) — RẤT HỮU ÍCH khi debug
x = 42
print(f"{x=}")        # Output: x=42
print(f"{name=}")     # Output: name='Alice'

# Format numbers
big_num = 1_000_000   # underscore cho dễ đọc (1000000)
print(f"{big_num:,}")    # 1,000,000
print(f"{price:.2f}")    # 19.99
print(f"{0.1234:.1%}")   # 12.3%

# Padding và alignment
print(f"{'left':<10}")   # "left      " (left align, width 10)
print(f"{'right':>10}")  # "     right" (right align)
print(f"{'center':^10}") # "  center  " (center align)

# str.format() — cách cũ, vẫn gặp trong legacy code
old = "Hello, {}! You are {} years old.".format(name, age)
named = "Hello, {name}!".format(name=name)

# % formatting — cách rất cũ, KHÔNG dùng trong code mới
very_old = "Hello, %s! Age: %d" % (name, age)
```

### 3. Control Flow

```python
# if/elif/else — không có {} nhưng indentation bắt buộc
score = 85

if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
else:
    grade = "F"

# Conditional expression (ternary)
status = "Pass" if score >= 60 else "Fail"

# Truthiness — QUAN TRỌNG
# Falsy: None, False, 0, 0.0, "", [], {}, set(), ()
# Truthy: mọi thứ còn lại
if name:               # True nếu name không rỗng
    print(f"Name: {name}")

# None check — PHẢI dùng "is", không dùng "=="
value = None
if value is None:
    print("No value")
if value is not None:
    print(f"Value: {value}")

# match/case — Python 3.10+ (structural pattern matching)
status_code = 404

match status_code:
    case 200:
        message = "OK"
    case 404:
        message = "Not Found"
    case 500 | 503:  # OR pattern
        message = "Server Error"
    case _:           # default (wildcard)
        message = f"Unknown: {status_code}"

# match với tuple destructuring — POWERFUL
point = (0, 5)
match point:
    case (0, 0):
        print("Origin")
    case (x, 0):
        print(f"On x-axis at {x}")
    case (0, y):
        print(f"On y-axis at {y}")
    case (x, y):
        print(f"At ({x}, {y})")

# match với dict pattern
command = {"action": "move", "direction": "north"}
match command:
    case {"action": "move", "direction": d}:
        print(f"Moving {d}")
    case {"action": "stop"}:
        print("Stopping")
```

### 4. Loops và Comprehensions

```python
fruits = ["apple", "banana", "cherry"]

# for loop
for fruit in fruits:
    print(fruit)

# enumerate — index + value (không dùng fruits[i])
for i, fruit in enumerate(fruits):
    print(f"{i}: {fruit}")

# range
for i in range(5):        # 0,1,2,3,4
    print(i)
for i in range(1, 6):     # 1,2,3,4,5
    print(i)
for i in range(0, 10, 2): # 0,2,4,6,8 (step=2)
    print(i)

# zip — iterate nhiều iterables cùng lúc
names = ["Alice", "Bob", "Charlie"]
ages = [25, 30, 35]
for name, age in zip(names, ages):
    print(f"{name}: {age}")

# while
count = 0
while count < 5:
    print(count)
    count += 1  # Python không có count++ hay ++count

# break, continue
for i in range(10):
    if i == 3:
        continue  # skip
    if i == 7:
        break     # exit
    print(i)

# ===== List Comprehension — PYTHONIC WAY =====
# Tương đương .map() + .filter() trong JS

# map: [expression for item in iterable]
squares = [x**2 for x in range(10)]
# JS: [0,1,...,9].map(x => x**2)

# filter: [x for x in iterable if condition]
evens = [x for x in range(20) if x % 2 == 0]
# JS: Array.from({length:20}, (_,i) => i).filter(x => x%2===0)

# map + filter kết hợp
even_squares = [x**2 for x in range(20) if x % 2 == 0]

# Dict comprehension
word_lengths = {word: len(word) for word in ["python", "java", "go"]}
# = {"python": 6, "java": 4, "go": 2}

# Set comprehension
unique_lengths = {len(w) for w in ["python", "java", "go"]}
# = {6, 4, 2}

# Generator expression (lazy — không allocate memory)
squares_gen = (x**2 for x in range(1_000_000))  # chưa tính gì
first = next(squares_gen)  # tính từng cái khi cần
```

### 5. Functions

```python
from typing import Callable

# Function cơ bản với type hints
def greet(name: str) -> str:
    return f"Hello, {name}!"

# Default parameters
def greet_with_title(name: str, title: str = "Mr") -> str:
    return f"Hello, {title}. {name}!"

# *args — positional variadic (như ...args trong JS)
def sum_all(*numbers: int) -> int:
    return sum(numbers)

result = sum_all(1, 2, 3, 4, 5)  # = 15

# **kwargs — keyword variadic (không có equivalent trực tiếp trong JS)
def create_user(**kwargs: str) -> dict[str, str]:
    return kwargs

user = create_user(name="Alice", email="alice@example.com", role="admin")

# Kết hợp tất cả
def complex_fn(
    required: str,              # positional required
    optional: int = 10,         # positional optional
    *args: str,                 # remaining positional
    keyword_only: bool = False, # keyword-only (PHẢI pass bằng keyword)
    **kwargs: str,              # remaining keyword
) -> None:
    print(f"{required=}, {optional=}, {args=}, {keyword_only=}, {kwargs=}")

# Keyword-only args (sau dấu *) — API design quan trọng
def create_connection(
    host: str,
    port: int,
    *,              # tất cả sau đây PHẢI là keyword
    timeout: float = 30.0,
    ssl: bool = False,
) -> None:
    pass

create_connection("localhost", 5432, timeout=10.0, ssl=True)  # OK
# create_connection("localhost", 5432, 10.0, True)  # ERROR!

# Lambda — single expression, giống arrow function JS
double = lambda x: x * 2
add = lambda x, y: x + y

# Dùng lambda với sorted/filter/map
users = [{"name": "Charlie", "age": 30}, {"name": "Alice", "age": 25}]
sorted_users = sorted(users, key=lambda u: u["age"])
older = list(filter(lambda u: u["age"] >= 30, users))

# Type hint cho callable
def apply(func: Callable[[int], int], value: int) -> int:
    return func(value)

result = apply(lambda x: x * 2, 5)  # = 10
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| `x == None` | `__eq__` có thể bị override | Dùng `x is None` |
| `def f(lst=[])` mutable default | lst được share giữa calls! | `def f(lst=None): lst = lst or []` |
| Không dùng type hints | IDE không hỗ trợ, khó maintain | Thêm type hints cho mọi function |
| `type(x) == int` | Không xét subclass | Dùng `isinstance(x, int)` |
| f-string với dict: `f"{d['key']}"` | SyntaxError với nested quotes | Dùng var: `v=d['key']; f"{v}"` |
| `list.sort()` khi cần list gốc | sort in-place, mất list gốc | `sorted_list = sorted(my_list)` |
| Regex không dùng raw string | `"\b"` thành backspace, `"\d"` dễ warning/khó đọc | Luôn viết pattern dạng `r"\b\d+\b"` |
| Regex `.*` quá greedy | Match qua nhiều delimiter, xóa nhầm text | Dùng `.*?` hoặc character class rõ như `[^>]+` |
| So sánh Unicode trực tiếp | `"é"` và `"e\u0301"` nhìn giống nhưng khác code points | Normalize với `unicodedata.normalize("NFC", text)` |

## ✅ Best Practices

- **Luôn dùng type hints** cho parameters và return type
- **f-strings** là cách tốt nhất — tránh `+` concatenation
- **List comprehensions** thay for + append khi tạo list mới
- **`is None`** không phải `== None`
- **Keyword-only arguments** (dùng `*`) khi function có nhiều boolean params
- **Tránh mutable default arguments** — Python gotcha phổ biến nhất
- **`match/case`** thay chuỗi if/elif khi có patterns rõ ràng
- **Regex pattern nên là raw string** (`r"..."`) và normalize Unicode trước khi so sánh/search text từ user input

## ⚖️ Trade-offs

| Approach | Readable | Performance | Khi nào dùng |
|----------|----------|-------------|--------------|
| List comprehension | ✅ Ngắn gọn | ✅ Nhanh hơn loop ~35% | Tạo list từ iterable |
| For loop + append | ✅ Dễ debug | ❌ Chậm hơn | Logic phức tạp, side effects |
| Generator expression | ✅ Ngắn gọn | ✅✅ Lazy, ít memory | Data lớn, không cần toàn bộ list |
| `map()` + `filter()` | ❌ Ít Pythonic | ~ | Khi cần lazy evaluation |

## 🚀 Performance Notes

- **List comprehension nhanh hơn for+append ~35%** — được tối ưu ở CPython bytecode
- **f-strings nhanh hơn `.format()`** và nhanh hơn `+` concatenation
- **`range()` là lazy** — không allocate memory cho toàn bộ sequence
- **Generator expression** `(x for x in range(10**6))` tiết kiệm memory so với list comprehension
- `sorted()` dùng **Timsort** — O(n log n) worst case, O(n) khi gần sorted

## 🔍 Regular Expressions

```python
import re

# re.match — chỉ match ở đầu string
# re.search — tìm match ở bất kỳ vị trí nào
# re.findall — tìm tất cả matches, trả về list
# re.sub — replace
# re.compile — compile pattern để reuse (nhanh hơn khi dùng nhiều lần)

# --- Cơ bản ---
email_pattern = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
print(bool(email_pattern.match("user@example.com")))   # True
print(bool(email_pattern.match("not-an-email")))        # False

# --- Named groups — tương đương named capture groups trong JS ---
# JS: /(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})/
log_pattern = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) "
    r"(?P<level>INFO|WARN|ERROR) (?P<message>.+)"
)
log_line = "2024-01-15 ERROR Database connection failed"
m = log_pattern.match(log_line)
if m:
    print(m.group("level"))    # "ERROR"
    print(m.group("message"))  # "Database connection failed"
    print(m.groupdict())       # {'year': '2024', 'month': '01', ...}

# --- findall + sub ---
text = "Call us at 090-123-4567 or 028-987-6543"
phones = re.findall(r"\d{3}-\d{3}-\d{4}", text)
print(phones)  # ['090-123-4567', '028-987-6543']

# Mask phone numbers — ứng dụng cho AI pipeline (PII redaction)
masked = re.sub(r"(\d{3})-\d{3}-(\d{4})", r"\1-***-\2", text)
print(masked)  # "Call us at 090-***-4567 or 028-***-6543"

# --- Lookahead / Lookbehind ---
# Giống JS (?=...) và (?<=...)
prices = "Price: $100, Discount: $20, Total: $80"
# Lấy số sau $ (positive lookbehind)
amounts = re.findall(r"(?<=\$)\d+", prices)
print(amounts)  # ['100', '20', '80']

# Lấy words chỉ khi sau đó có dấu ":" (positive lookahead)
labels = re.findall(r"\b[A-Za-z]+(?=:)", prices)
print(labels)  # ['Price', 'Discount', 'Total']

# --- Flags ---
# re.IGNORECASE (re.I) — case insensitive, giống /pattern/i trong JS
# re.MULTILINE (re.M) — ^ và $ match đầu/cuối mỗi dòng
# re.DOTALL (re.S) — . match cả \n
# re.VERBOSE (re.X) — cho phép format regex nhiều dòng + comments
# re.ASCII (re.A) — ép \w, \d, \b về ASCII behavior
text = "Hello\nWorld"
matches = re.findall(r"hello", text, re.IGNORECASE)
print(matches)  # ['Hello']

# --- Pitfall 1: raw string cho regex ---
# BAD: "\b" trong Python string là backspace, không phải word boundary
print(bool(re.search("\bword\b", "a word here")))   # False hoặc khó hiểu
# GOOD: dùng r"..." để backslash đi thẳng vào regex engine
print(bool(re.search(r"\bword\b", "a word here")))  # True

# --- Pitfall 2: greedy vs non-greedy ---
html = "<b>Hello</b><i>World</i>"
print(re.findall(r"<.*>", html))    # ['<b>Hello</b><i>World</i>'] — greedy, ăn quá nhiều
print(re.findall(r"<.*?>", html))   # ['<b>', '</b>', '<i>', '</i>'] — non-greedy
print(re.findall(r"<[^>]+>", html)) # Thường rõ intent hơn cho tags đơn giản

# --- Pitfall 3: Unicode normalization ---
import unicodedata

precomposed = "Café"          # é là 1 code point
decomposed = "Cafe\u0301"     # e + combining acute accent
print(precomposed == decomposed)  # False
print(
    unicodedata.normalize("NFC", precomposed)
    == unicodedata.normalize("NFC", decomposed)
)  # True

# Regex trong Python là Unicode-aware mặc định: \w match nhiều chữ cái ngoài ASCII.
# Nếu đang validate ID/API slug ASCII-only, dùng explicit class hoặc re.ASCII.
print(bool(re.match(r"^\w+$", "café")))             # True
print(bool(re.match(r"^\w+$", "café", re.ASCII)))   # False

# --- Ứng dụng thực tế trong AI pipeline ---
def clean_text_for_embedding(text: str) -> str:
    """Clean text trước khi tạo embeddings."""
    # Xóa HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Xóa URLs
    text = re.sub(r"https?://\S+", "[URL]", text)
    # Xóa email addresses (privacy)
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    # Chuẩn hóa whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

sample = "<p>Contact <a href='...'>us</a> at admin@company.com or visit https://company.com</p>"
print(clean_text_for_embedding(sample))
# "Contact us at [EMAIL] or visit [URL]"
```

> **So sánh Python vs JavaScript regex syntax:**
> - Gần như giống nhau! Các patterns `/regex/` trong JS viết thành `re.compile(r"regex")`
> - JS flag `g` không tồn tại trong Python; dùng `re.findall()` hoặc `re.finditer()` để lấy nhiều match
> - JS flags: `/i` → `re.IGNORECASE`, `/m` → `re.MULTILINE`, `/s` → `re.DOTALL`
> - Python có thêm flags hay gặp như `re.VERBOSE` và `re.ASCII`
> - JS `str.match()` → Python `re.findall()` hay `re.search()`
> - JS `str.replace()` với regex → Python `re.sub()`
> - Named groups: JS `(?<name>...)` → Python `(?P<name>...)`
> - Lookbehind trong Python phải có độ dài cố định; nếu pattern dynamic quá phức tạp, tách parsing thành nhiều bước rõ ràng hơn.

## 📝 Tóm tắt

- Python không có `const/let/var` — dùng ALL_CAPS convention cho constants
- `f"{variable}"` = template literals JS, support expressions và format specs
- `is None` không phải `== None` — quan trọng!
- `match/case` (Python 3.10+) mạnh hơn switch: hỗ trợ structural pattern matching
- `[f(x) for x in lst if cond]` = `.map().filter()` trong JS
- `*args` = `...args` trong JS, `**kwargs` = named variadic (không có trong JS)
- **Mutable default argument** là Python gotcha nổi tiếng nhất
- Regex trong Python gần JS, nhưng nhớ 3 điểm: raw string, Unicode mặc định, greedy quantifier
