# Bài Tập — Ngày 03: Data Structures

## Bài 1 — Grade Manager (Cơ bản)

**Mô tả:** Quản lý điểm học sinh với dict và list.

**Dữ liệu đầu vào:**
```python
grades_data = [
    ("Alice", "Math", 92), ("Alice", "Science", 88),
    ("Bob", "Math", 75), ("Bob", "Science", 82), ("Bob", "History", 90),
    ("Charlie", "Math", 65), ("Charlie", "Science", 70),
]
```

**Yêu cầu:**
```python
def build_grade_dict(
    data: list[tuple[str, str, int]]
) -> dict[str, dict[str, int]]:
    """Returns: {"Alice": {"Math": 92, "Science": 88}, ...}"""
    ...

def calculate_averages(
    grades: dict[str, dict[str, int]]
) -> dict[str, float]:
    """Returns: {"Alice": 90.0, "Bob": 82.33, ...}"""
    ...

def get_top_student(averages: dict[str, float]) -> tuple[str, float]:
    """Returns: ("Alice", 90.0)"""
    ...

def get_subject_ranking(
    grades: dict[str, dict[str, int]],
    subject: str
) -> list[tuple[str, int]]:
    """Xếp hạng học sinh theo môn, sorted descending."""
    ...
```

**Expected output:**
```
Top student: Alice with average 90.0
Math ranking: [('Alice', 92), ('Bob', 75), ('Charlie', 65)]
```

---

## Bài 2 — Inventory System với Dataclass (Trung bình)

**Yêu cầu:**
```python
from dataclasses import dataclass, field

@dataclass
class Product:
    id: int
    name: str
    category: str
    price: float
    quantity: int
    tags: list[str] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return self.price * self.quantity

    def is_low_stock(self, threshold: int = 10) -> bool:
        return self.quantity < threshold

@dataclass
class Inventory:
    _products: dict[int, Product] = field(default_factory=dict)

    def add_product(self, product: Product) -> None: ...
    def get_by_id(self, product_id: int) -> Product | None: ...
    def get_by_category(self, category: str) -> list[Product]: ...
    def get_low_stock(self, threshold: int = 10) -> list[Product]: ...
    def total_value(self) -> float: ...
    def search_by_tag(self, tag: str) -> list[Product]: ...
    def top_by_value(self, n: int = 3) -> list[Product]: ...
    def snapshot(self) -> dict[int, Product]: ...
```

**Mutability requirement:** `snapshot()` phải trả về copy an toàn để caller không sửa trực tiếp `_products` hoặc `tags` bên trong inventory. Có thể dùng `copy.deepcopy()` cho bài này, nhưng ghi chú trong code rằng production có thể chọn DTO/immutable model thay vì deepcopy toàn bộ.

**Test data:**
```python
inv = Inventory()
inv.add_product(Product(1, "Laptop", "Electronics", 999.99, 5, ["new", "featured"]))
inv.add_product(Product(2, "Mouse", "Electronics", 29.99, 50))
inv.add_product(Product(3, "Desk", "Furniture", 299.99, 8, ["new"]))
inv.add_product(Product(4, "Chair", "Furniture", 199.99, 3, ["sale"]))
```

**Expected:**
```
Low stock items: [Laptop (5), Chair (3)]
Total value: $9,949.34
Top 2 by value: [Laptop ($4,999.95), Mouse ($1,499.50)]
```

---

## Bài 3 — Text Analyzer với Counter và Set (Nâng cao)

**Mô tả:** Phân tích tần suất từ trong text.

**Yêu cầu:**
```python
from collections import Counter
from dataclasses import dataclass, field

STOPWORDS = {"the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and", "or", "are", "was"}

@dataclass
class TextAnalyzer:
    _word_count: Counter = field(default_factory=Counter)
    _word_positions: dict[str, list[int]] = field(default_factory=dict)

    def analyze(self, text: str) -> None:
        """Parse text, build word count và positions."""
        ...

    def top_words(self, n: int = 10) -> list[tuple[str, int]]:
        """n từ phổ biến nhất (bỏ stopwords)."""
        ...

    def unique_words(self) -> set[str]:
        """Tập hợp unique words (bỏ stopwords)."""
        ...

    def word_positions(self, word: str) -> list[int]:
        """Vị trí (word index) xuất hiện của word."""
        ...

    def sentences_with_word(self, text: str, word: str) -> list[str]:
        """Các câu chứa word."""
        ...
```

**Test:**
```python
text = """
Python is a versatile programming language. Python is used for web development,
data science, and AI. Many developers love Python because Python is easy to learn
and Python has a rich ecosystem of libraries.
"""
analyzer = TextAnalyzer()
analyzer.analyze(text)
print(analyzer.top_words(5))
# [("python", 5), ("easy", 1), ...]
print(analyzer.word_positions("python"))
# [0, 8, 18, 22, 26]  (word indices)
```

## 🔍 Gợi ý kiểm tra kết quả

```bash
# Test assertions
python -c "
from collections import Counter
# Quick Counter test
words = 'python java python go python'.split()
c = Counter(words)
assert c['python'] == 3
assert c.most_common(1) == [('python', 3)]
print('Counter OK')
"

# Run với type check
uv run mypy --strict inventory.py

# Run main exercise file nếu bạn đặt code vào inventory.py
uv run python inventory.py
```
