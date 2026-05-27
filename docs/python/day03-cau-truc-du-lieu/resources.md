# Tài Liệu Tham Khảo — Ngày 03: Data Structures

## 📚 Official Docs

- **Python Data Structures Tutorial** — https://docs.python.org/3/tutorial/datastructures.html
- **collections module** — https://docs.python.org/3/library/collections.html — Counter, defaultdict, deque, OrderedDict
- **dataclasses** — https://docs.python.org/3/library/dataclasses.html
- **copy module** — https://docs.python.org/3/library/copy.html — shallow copy vs `copy.deepcopy()`
- **typing.NamedTuple** — https://docs.python.org/3/library/typing.html#typing.NamedTuple

## 🎥 Video / Courses

- **"Python Data Structures"** - Corey Schafer (YouTube) — Comprehensive guide
- **"Dataclasses in Python"** - Arjan Codes (YouTube) — Best practices
- **"Python's collections Module"** - mCoding (YouTube) — Counter, defaultdict, deque

## 📝 Articles / Blog Posts

- **"Python's collections: A Buffet of Specialized Data Types"** — realpython.com
- **"The Ultimate Guide to Python Dataclasses"** — realpython.com
- **"Python List vs Tuple vs Set vs Dict"** — comparison articles on medium.com

## 🔧 Tools / Libraries

- **collections** (built-in) — Counter, defaultdict, OrderedDict, deque, namedtuple
- **dataclasses** (built-in) — @dataclass decorator
- **typing** (built-in) — NamedTuple, TypedDict
- **attrs** — github.com/python-attrs/attrs — Alternative mạnh hơn dataclass
- **pydantic** — docs.pydantic.dev — Data validation (học sâu ở Ngày 08)

## 💡 Ghi chú thêm

- **TypedDict** khi cần type hints cho dict với fixed keys:
  ```python
  from typing import TypedDict
  class UserDict(TypedDict):
      name: str
      age: int
  ```
- **`slots=True`** trong dataclass (Python 3.10+): giảm memory ~30% cho nhiều instances
- **`bisect` module**: binary search trên sorted list — O(log n)
- **`heapq` module**: priority queue — O(log n) push/pop
- **`array` module**: typed array cho homogeneous numeric data — nhỏ hơn list ~3x (nhưng numpy tốt hơn)
