# Bài Tập — Ngày 08: File I/O, Context Managers & Serialization

## Bài 1 — CSV → Pydantic → JSON Pipeline (Cơ bản)

**Mô tả:** Đọc CSV, validate với Pydantic, export JSON.

**File `students.csv`:**
```
name,age,email,score
Alice Johnson,28,alice@example.com,92
Bob Smith,17,invalid-email,78
Charlie Brown,35,charlie@example.com,
Diana Prince,22,diana@example.com,88
Eve,16,eve@example.com,95
```

**Yêu cầu:**
```python
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

class Student(BaseModel):
    name: Annotated[str, Field(min_length=2)]
    age: Annotated[int, Field(ge=0, le=150)]
    email: str
    score: float | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError(f"Invalid email: {v}")
        return v.lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.split()) < 2:
            raise ValueError("Name must contain first and last name")
        return v.title()

def load_students(csv_path: str) -> tuple[list[Student], list[dict]]:
    """Returns (valid_students, errors)"""
    ...

def export_valid_students(students: list[Student], output_path: str) -> None:
    """Export list of students to JSON file."""
    ...
```

**Expected:**
```
Loaded 3 valid students, 2 errors
Errors:
  - Bob Smith: Validation failed: email: Invalid email: invalid-email
  - Eve: Validation failed: name: Name must contain first and last name

Exported to students_valid.json
```

---

## Bài 2 — ConfigManager với Context Manager (Trung bình)

**Mô tả:** Xây dựng ConfigManager đọc YAML/TOML, hỗ trợ context manager.

**Yêu cầu:**
```python
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Generator

class ConfigManager:
    """
    Config manager hỗ trợ YAML và TOML.
    Có thể dùng như context manager.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] = {}
        self._dirty: bool = False

    def load(self) -> None:
        """Load config từ file (auto-detect YAML/TOML từ extension)."""
        ...

    def save(self) -> None:
        """Save config về file nếu có thay đổi (_dirty=True)."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Get value bằng dot notation: config.get('database.host')"""
        ...

    def set(self, key: str, value: Any) -> None:
        """Set value bằng dot notation, mark _dirty=True."""
        ...

    def __enter__(self) -> "ConfigManager":
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if not exc_type:  # chỉ save nếu không có exception
            self.save()
        return False
```

**Security requirements:**
- YAML phải dùng `yaml.safe_load()` khi đọc.
- Nếu config path đến từ user input, resolve path và reject file nằm ngoài base directory cho phép (`Path.resolve()` + `is_relative_to()`).
- Chỉ hỗ trợ extension `.yaml`, `.yml`, `.toml`; extension khác phải raise `ValueError`.

**Test:**
```python
# Dùng như context manager
with ConfigManager("app.yaml") as config:
    host = config.get("database.host", "localhost")
    config.set("app.version", "1.0.1")
    # Tự động save khi exit

# Dùng không có context manager
config = ConfigManager("settings.toml")
config.load()
print(config.get("server.port", 8080))
```

---

## Bài 3 — Multi-format Data Pipeline với Pydantic (Nâng cao)

**Mô tả:** Pipeline xử lý data từ nhiều nguồn, validate và transform.

**Yêu cầu:**
Viết `DataPipeline` class:
```python
from pydantic import BaseModel
from pathlib import Path
from typing import TypeVar

T = TypeVar("T", bound=BaseModel)

class DataPipeline:
    def load_json(self, path: str | Path, model: type[T]) -> list[T]: ...
    def load_csv(self, path: str | Path, model: type[T]) -> list[T]: ...
    def load_yaml(self, path: str | Path, model: type[T]) -> list[T]: ...
    def save_json(self, data: list[BaseModel], path: str | Path) -> None: ...
    def save_csv(self, data: list[BaseModel], path: str | Path) -> None: ...
    def validate_all(self, records: list[dict], model: type[T]) -> tuple[list[T], list[dict]]: ...
    def transform(self, data: list[T], transformer) -> list[T]: ...
```

**Models:**
```python
class ProductRaw(BaseModel):
    """Input: dirty data từ CSV"""
    name: str
    price: str  # string từ CSV
    category: str
    in_stock: str  # "true"/"false"/"1"/"0"

class Product(BaseModel):
    """Output: clean validated data"""
    name: str
    price: float
    category: str
    in_stock: bool

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v: str | float) -> float:
        if isinstance(v, str):
            return float(v.replace("$", "").replace(",", ""))
        return v
```

**Pipeline:**
```python
pipeline = DataPipeline()
raw = pipeline.load_csv("products.csv", ProductRaw)
products, errors = pipeline.validate_all(
    [p.model_dump() for p in raw],
    Product
)
pipeline.save_json(products, "products_clean.json")
print(f"Processed: {len(products)} valid, {len(errors)} errors")
```

## 🔍 Gợi ý kiểm tra kết quả

```bash
# Test Pydantic validation
python -c "
from pydantic import BaseModel, ValidationError, Field

class Item(BaseModel):
    name: str
    price: float = Field(gt=0)

try:
    item = Item(name='Test', price=-1)
except ValidationError as e:
    print(e.errors())

item = Item(name='Valid', price=10.0)
print(item.model_dump())
"

# Test pathlib
python -c "
from pathlib import Path
p = Path('/tmp/test_file.txt')
p.write_text('hello')
print(p.read_text())
p.unlink()
print('pathlib OK')
"
```
