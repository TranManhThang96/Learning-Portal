# Bài Tập — Ngày 02: Python Syntax Cơ Bản

## Bài 1 — FizzBuzz với nhiều cách viết (Cơ bản)

**Mô tả:** Classic FizzBuzz để luyện syntax Python theo nhiều phong cách.

**Yêu cầu:**
1. Viết `fizzbuzz_loop(n: int) -> list[str]` dùng for loop + if/elif
2. Viết `fizzbuzz_comprehension(n: int) -> list[str]` bằng list comprehension 1 dòng
3. Viết `fizzbuzz_match(n: int) -> list[str]` dùng `match/case`
4. Kiểm tra cả 3 cho cùng kết quả với n=20

**Expected output (n=15):**
```
['1', '2', 'Fizz', '4', 'Buzz', 'Fizz', '7', '8', 'Fizz', 'Buzz', '11', 'Fizz', '13', '14', 'FizzBuzz']
```

**Hint cho match version:**
```python
def fizzbuzz_match(n: int) -> list[str]:
    result = []
    for i in range(1, n + 1):
        match (i % 3 == 0, i % 5 == 0):
            case (True, True):
                result.append("FizzBuzz")
            case (True, False):
                result.append("Fizz")
            case (False, True):
                result.append("Buzz")
            case _:
                result.append(str(i))
    return result
```

---

## Bài 2 — String Processor Module (Trung bình)

**Mô tả:** Xây dựng module xử lý string để làm quen với string operations.

**Yêu cầu:** Tạo file `string_processor.py` với các functions sau (đầy đủ type hints):

```python
def word_count(text: str) -> dict[str, int]:
    """Đếm số lần xuất hiện của mỗi từ (case-insensitive)."""
    ...

def capitalize_words(text: str) -> str:
    """Viết hoa chữ cái đầu mỗi từ."""
    ...

def is_palindrome(text: str) -> bool:
    """Kiểm tra palindrome, bỏ qua spaces, case và punctuation cơ bản."""
    ...

def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Cắt ngắn text nếu quá dài."""
    ...

def snake_to_camel(name: str) -> str:
    """Convert snake_case → camelCase."""
    ...

def camel_to_snake(name: str) -> str:
    """Convert camelCase → snake_case."""
    ...
```

**Expected output:**
```python
assert word_count("hello world hello") == {"hello": 2, "world": 1}
assert is_palindrome("A man a plan a canal Panama") == True
assert snake_to_camel("hello_world_test") == "helloWorldTest"
assert camel_to_snake("helloWorldTest") == "hello_world_test"
assert truncate("Hello World", max_length=8) == "Hello..."
```

**Hint:**
- `str.split()`, `str.join()`, `str.lower()`, `str.title()`
- Dùng `re` module cho camel_to_snake: `re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()`
- Với input Unicode có dấu, normalize trước khi xử lý: `unicodedata.normalize("NFC", text)`
- Regex pattern nên dùng raw string: `r"..."`, đặc biệt với `\b`, `\d`, `\w`

---

## Bài 3 — Data Pipeline với Functions (Nâng cao)

**Mô tả:** Xây dựng mini data pipeline xử lý danh sách users.

**Dữ liệu:**
```python
users = [
    {"name": "Alice Johnson", "age": 28, "score": 92, "active": True},
    {"name": "Bob Smith", "age": 17, "score": 78, "active": True},
    {"name": "Charlie Brown", "age": 35, "score": 45, "active": False},
    {"name": "Diana Prince", "age": 22, "score": 88, "active": True},
    {"name": "Eve Wilson", "age": 16, "score": 95, "active": True},
    {"name": "Frank Miller", "age": 31, "score": 72, "active": True},
]
```

**Yêu cầu:**
```python
def filter_active_adults(users: list[dict]) -> list[dict]:
    """Lấy users active VÀ >= 18 tuổi."""
    ...

def get_top_scorers(users: list[dict], n: int = 3) -> list[dict]:
    """Lấy n users có điểm cao nhất."""
    ...

def format_leaderboard(users: list[dict]) -> str:
    """Format thành bảng xếp hạng đẹp."""
    ...

def calculate_stats(users: list[dict]) -> dict[str, float]:
    """Tính avg, min, max score."""
    ...
```

**Expected output:**
```
🏆 Leaderboard
─────────────────────────────────
#1  Alice Johnson     | Age: 28 | Score: 92
#2  Diana Prince      | Age: 22 | Score: 88
#3  Frank Miller      | Age: 31 | Score: 72
─────────────────────────────────
Stats: avg=84.0, min=72, max=92
```

**Challenge:** Thêm `pipeline(*funcs)` function nhận list functions và apply tuần tự lên data.

## 🔍 Gợi ý kiểm tra kết quả

```bash
# Chạy với assertions
python -c "
from string_processor import word_count, is_palindrome
assert word_count('hello hello world') == {'hello': 2, 'world': 1}
assert is_palindrome('racecar') == True
assert is_palindrome('hello') == False
print('All assertions passed!')
"

# Type check
uv run mypy --strict string_processor.py

# Linting
uv run ruff check string_processor.py
```
