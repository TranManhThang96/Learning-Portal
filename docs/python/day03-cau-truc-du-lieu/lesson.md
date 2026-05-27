# Ngày 03: Data Structures

## 🎯 Mục tiêu học tập

- Hiểu sâu list, tuple, dict, set và khi nào dùng cái nào
- Thành thạo comprehensions cho tất cả data structures
- Nắm vững NamedTuple và dataclass
- Biết time complexity của các operations quan trọng
- Tránh bug do mutability, shallow copy và deep copy trong nested data

**Scope 2 giờ cho ngày này:**
- **Must Learn:** list/tuple/dict/set, comprehensions, `Counter`/`defaultdict`, time complexity cơ bản, mutability/copy pitfalls.
- **Optional Reference:** `NamedTuple` vs `dataclass`, `slots=True`, deep copy trade-offs cho nested data lớn.

## 🔄 So sánh với NodeJS/TypeScript

| Python | JavaScript/TypeScript | Ghi chú |
|--------|-----------------------|---------|
| `list` | `Array` | Ordered, mutable, O(1) append |
| `tuple` | `readonly [T1, T2]` | Ordered, immutable, hashable |
| `dict` | `object` / `Map` | Key-value, ordered (Python 3.7+) |
| `set` | `Set` | Unique values, O(1) lookup |
| `NamedTuple` | `interface` / `type` (TS) | Tuple với tên fields, immutable |
| `dataclass` | `class` (TS) | Class chứa data, auto __init__ |
| `frozenset` | Không có | Immutable set |
| `defaultdict` | `new Map()` với default | Dict tự tạo default value |
| `Counter` | Không có built-in | Dict đếm occurrences |

## 📖 Lý thuyết

### 1. List — Ordered Mutable Sequence

```python
# Tạo list
fruits: list[str] = ["apple", "banana", "cherry"]
numbers: list[int] = [1, 2, 3, 4, 5]

# Indexing — Python hỗ trợ negative indexing!
print(fruits[0])    # "apple"
print(fruits[-1])   # "cherry" — last element (không cần len-1)
print(fruits[-2])   # "banana"

# Slicing — rất powerful
print(fruits[1:3])   # ["banana", "cherry"] (không bao gồm index 3)
print(fruits[:2])    # ["apple", "banana"]
print(fruits[1:])    # ["banana", "cherry"]
print(fruits[::2])   # ["apple", "cherry"] (every 2 elements)
print(fruits[::-1])  # ["cherry", "banana", "apple"] — REVERSE

# Mutations
fruits.append("date")           # O(1) amortized
fruits.insert(1, "avocado")     # O(n) — shift elements
fruits.pop()                    # O(1) — remove last
fruits.pop(0)                   # O(n) — remove first (dùng deque thay)
fruits.remove("banana")         # O(n) — remove first occurrence
fruits.extend(["elderberry"])   # O(k) — concat

# Search
print("apple" in fruits)        # O(n) linear search
print(fruits.index("apple"))    # ValueError nếu không tìm thấy

# Sorting
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
sorted_nums = sorted(numbers)            # NEW list, không modify original
numbers.sort()                            # in-place, trả về None
numbers.sort(reverse=True)
users = [{"name": "Bob", "age": 30}, {"name": "Alice", "age": 25}]
sorted_users = sorted(users, key=lambda u: u["age"])

# List comprehension
squares = [x**2 for x in range(10)]
evens = [x for x in range(20) if x % 2 == 0]
matrix = [[i * j for j in range(5)] for i in range(5)]
```

**Time Complexity:**

| Operation | Complexity | Ghi chú |
|-----------|-----------|---------|
| `list[i]` | O(1) | Direct access |
| `list.append()` | O(1) amortized | Dynamic array |
| `list.insert(0, x)` | O(n) | Shift all elements |
| `list.pop()` | O(1) | Remove from end |
| `list.pop(0)` | O(n) | Dùng `deque` thay |
| `x in list` | O(n) | Linear search |
| `list.sort()` | O(n log n) | Timsort |

### 2. Tuple — Ordered Immutable Sequence

```python
# Tạo tuple
point: tuple[int, int] = (3, 4)
rgb: tuple[int, int, int] = (255, 128, 0)
single: tuple[int] = (42,)  # DẤU PHẨY quan trọng! (42) là int

# Unpacking — rất phổ biến
x, y = point
r, g, b = rgb

# Extended unpacking (như rest/spread trong JS)
first, *rest = (1, 2, 3, 4, 5)   # first=1, rest=[2,3,4,5]
*head, last = (1, 2, 3, 4, 5)    # head=[1,2,3,4], last=5

# Swap variables — Python idiom đặc biệt
a, b = 1, 2
a, b = b, a  # Swap không cần temp variable!

# Tuple là hashable — dùng làm dict key
locations: dict[tuple[int, int], str] = {
    (0, 0): "origin",
    (1, 0): "right",
    (0, 1): "up",
}

# Return multiple values từ function
def get_dimensions() -> tuple[int, int]:
    return 1920, 1080  # thực ra là return tuple

width, height = get_dimensions()
```

### 3. Dict — Key-Value Mapping

```python
user: dict[str, str | int] = {
    "name": "Alice",
    "age": 25,
    "email": "alice@example.com"
}

# Access
print(user["name"])                # "Alice" — KeyError nếu không có
print(user.get("phone"))           # None — an toàn
print(user.get("phone", "N/A"))    # "N/A" — với default

# Mutations
user["phone"] = "+84-123"          # add/update
del user["email"]                  # KeyError nếu không có
popped = user.pop("phone", None)   # remove + return, an toàn

# Iteration
for key in user:
    print(key)
for key, value in user.items():
    print(f"{key}: {value}")

# Merge (Python 3.9+)
defaults = {"timeout": 30, "retries": 3}
overrides = {"timeout": 60}
config = defaults | overrides  # = {"timeout": 60, "retries": 3}

# Dict comprehension
squared = {x: x**2 for x in range(5)}
inverted = {v: k for k, v in user.items()}

# defaultdict — tự tạo default khi key không tồn tại
from collections import defaultdict

groups: defaultdict[str, list[str]] = defaultdict(list)
for role, name in [("admin", "Alice"), ("user", "Bob"), ("admin", "Charlie")]:
    groups[role].append(name)
# {"admin": ["Alice", "Charlie"], "user": ["Bob"]}

# Counter — đếm occurrences
from collections import Counter
words = ["python", "java", "python", "go", "python"]
freq = Counter(words)
print(freq.most_common(2))  # [("python", 3), ("java", 1)]
```

### 4. Set — Unique Unordered Collection

```python
skills: set[str] = {"python", "javascript", "go"}
empty_set: set[int] = set()  # KHÔNG dùng {} — đó là empty dict!

# Mutations
skills.add("rust")
skills.discard("java")   # không lỗi nếu không có (safe)
skills.remove("go")      # KeyError nếu không có

# Membership test — O(1) hash-based
print("python" in skills)  # True — O(1)

# Set operations
backend = {"python", "go", "rust"}
frontend = {"javascript", "typescript", "python"}

union = backend | frontend          # tất cả
intersection = backend & frontend   # chỉ "python"
difference = backend - frontend     # backend nhưng không frontend
sym_diff = backend ^ frontend       # trong một nhưng không cả hai

# Use case: lọc duplicates
ids = [1, 2, 3, 2, 1, 4]
unique_ids = list(set(ids))  # order không đảm bảo
```

### 5. NamedTuple

```python
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
    label: str = ""  # default value

p = Point(x=3.0, y=4.0, label="origin")
print(p.x)            # 3.0 — access by name
print(p[0])           # 3.0 — access by index
print(p._asdict())    # {"x": 3.0, "y": 4.0, "label": "origin"}

# Vẫn là tuple — hashable, dùng làm dict key được
x, y, label = p  # unpack
cache: dict[Point, str] = {Point(0, 0): "origin"}
```

### 6. Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)  # KHÔNG được = []
    is_active: bool = True

# Auto-generated: __init__, __repr__, __eq__
user = User(id=1, name="Alice", email="alice@example.com")
print(user)  # User(id=1, name='Alice', ...)
user2 = User(id=1, name="Alice", email="alice@example.com")
print(user == user2)  # True — compare by VALUE (khác JS)

# frozen=True — immutable dataclass
@dataclass(frozen=True)
class Config:
    host: str
    port: int

cfg = Config(host="localhost", port=8080)
# cfg.port = 9090  # FrozenInstanceError!

# slots=True (Python 3.10+) — giảm memory ~30%
@dataclass(slots=True)
class LightweightPoint:
    x: float
    y: float
```

### 7. Mutability và Copy Semantics

**WHY:** Python và JavaScript đều dùng object references cho nested data. Khác biệt là Python có nhiều syntax tạo copy nhìn rất gọn (`list.copy()`, slicing, `dict | other`), nhưng phần lớn chỉ là **shallow copy**. Với nested list/dict/dataclass, bug thường nằm ở tầng bên trong.

```python
import copy

cart = {
    "user_id": "u1",
    "items": [
        {"sku": "book", "qty": 1},
        {"sku": "pen", "qty": 2},
    ],
}

# Assignment: không copy gì cả, chỉ thêm reference mới
same_cart = cart
same_cart["items"][0]["qty"] = 99
print(cart["items"][0]["qty"])  # 99

# Shallow copy: dict mới, nhưng nested list/dict vẫn shared
shallow = cart.copy()
shallow["user_id"] = "u2"               # OK: top-level tách biệt
shallow["items"][1]["qty"] = 100        # BUG: nested object shared
print(cart["items"][1]["qty"])          # 100

# Deep copy: copy đệ quy nested objects
safe_copy = copy.deepcopy(cart)
safe_copy["items"][0]["qty"] = 1
print(cart["items"][0]["qty"])          # vẫn 99
```

**Những chỗ hay nhầm:**

```python
# Slicing/list.copy() chỉ shallow
matrix = [[1, 2], [3, 4]]
matrix_copy = matrix[:]
matrix_copy[0].append(99)
print(matrix)  # [[1, 2, 99], [3, 4]]

# Tuple immutable ở top-level, nhưng item bên trong có thể mutable
bad_key_candidate = ([1, 2], "tags")
# hash(bad_key_candidate)  # TypeError: list bên trong không hashable

data = (["mutable"], "metadata")
data[0].append("changed")  # OK: tuple không đổi, list bên trong đổi
print(data)                # (['mutable', 'changed'], 'metadata')

# dict merge cũng shallow
defaults = {"headers": {"Accept": "application/json"}, "timeout": 30}
config = defaults | {"timeout": 10}
config["headers"]["Authorization"] = "Bearer token"
print(defaults["headers"])  # cũng bị thêm Authorization
```

**Rule of thumb:**
- Copy để sửa top-level: `lst.copy()`, `dict.copy()`, slicing là đủ.
- Copy để tránh mutate nested data từ input/API/cache: dùng `copy.deepcopy()` hoặc tự tạo object mới rõ ràng.
- Với dataclass có mutable fields, dùng `field(default_factory=list)` và cân nhắc return copy trong getters.

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| `empty_set = {}` | Tạo empty dict | `empty_set = set()` |
| `single = (42)` | Tạo int, không phải tuple | `single = (42,)` — cần dấu phẩy |
| `@dataclass` với `tags: list = []` | list shared giữa instances | `tags: list = field(default_factory=list)` |
| Dùng list cho unique + O(1) lookup | O(n) per lookup | Dùng `set` |
| Modify dict trong khi iterate | RuntimeError | Iterate `list(dict.items())` |
| `list.sort()` khi cần original | Sort in-place, mất gốc | `sorted(list)` trả về list mới |
| Shallow copy: `lst2 = lst1.copy()` | Nested objects vẫn shared | `import copy; copy.deepcopy(lst)` |
| Tin rằng `tuple` luôn "deep immutable" | Tuple có thể chứa list/dict mutable bên trong | Chỉ dùng nested immutable values nếu cần hashable/value object |

## ✅ Best Practices

- **Chọn đúng structure**: unique → set, key-value → dict, ordered → list, immutable record → NamedTuple
- **`dict.get(key, default)`** thay vì try/except KeyError
- **`defaultdict`** cho groupBy patterns
- **`Counter`** cho frequency counting
- **`field(default_factory=...)`** trong dataclass cho mutable defaults
- **`dataclass(frozen=True)`** cho value objects (coordinates, config)
- **Copy rõ intent**: shallow copy cho top-level, `deepcopy()` hoặc constructor mới cho nested mutable data

## ⚖️ Trade-offs

| Structure | Memory | Mutability | Khi nào dùng |
|-----------|--------|-----------|--------------|
| list | Medium | Mutable | Sequence có thứ tự |
| tuple | Least | Immutable | Fixed data, dict key, multi-return |
| dict | Most | Mutable | Key-value mapping |
| set | Medium | Mutable | Unique values, set operations |
| NamedTuple | Least | Immutable | Lightweight records, hashable |
| dataclass | More | Configurable | Rich objects, cần methods |

## 🚀 Performance Notes

- **`x in set`** O(1) vs **`x in list`** O(n) — convert sang set trước khi check nhiều lần
- **`deque`** từ `collections` cho O(1) append/pop ở cả hai đầu
- **Slicing** tạo copy mới — với list lớn, dùng `itertools.islice` cho lazy slicing
- Dict với **string keys** (interned strings) lookup nhanh hơn

## 📝 Tóm tắt

- **list** = JS Array: mutable, ordered, slicing rất mạnh
- **tuple** = immutable list: fixed data, dict keys, multi-return values
- **dict** = JS Map: O(1) lookup, ordered từ Python 3.7
- **set** = JS Set: unique values, O(1) membership, set operations
- `{}` là empty **dict**, `set()` là empty **set** — dễ nhầm!
- `@dataclass` tự generate `__init__`, `__repr__`, `__eq__` — như class trong TS
- Mutable default trong dataclass: dùng `field(default_factory=list)` không phải `= []`
- Assignment không copy object; shallow copy chỉ tách top-level, nested list/dict vẫn shared
- Dùng `deepcopy()` có chủ đích vì an toàn hơn cho nested data nhưng tốn CPU/memory hơn
