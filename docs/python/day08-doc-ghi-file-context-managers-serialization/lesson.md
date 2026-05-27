# Ngày 08: File I/O, Context Managers & Serialization

## 🎯 Mục tiêu học tập

- Sử dụng `pathlib.Path` thay vì `os.path` cho tất cả file operations
- Viết custom context managers với class-based và `@contextmanager` decorator
- Serialize/deserialize JSON, CSV, YAML, TOML với proper error handling
- Dùng Pydantic v2 cho validation, type coercion, và serialization
- Hiểu khi nào dùng Pydantic vs dataclass vs TypedDict

## 🧭 Lộ trình học trong 2 giờ

**Must Learn:**
- `pathlib.Path`, `with`, `contextlib` cho file handling an toàn
- JSON/CSV/TOML/YAML ở mức đọc/ghi cơ bản, luôn dùng `yaml.safe_load()` cho input bên ngoài
- Pydantic v2 core: `BaseModel`, `Field`, `field_validator`, `model_validator`, `computed_field`, `model_validate()`, `model_dump()`
- Alias mapping, settings từ environment, `model_config` strict/extra ở mức nhận diện và dùng được
- Security checklist: validate extension, giới hạn file size, chặn path traversal

**Optional Reference:**
- Model inheritance và discriminated unions để chuẩn bị cho FastAPI response schemas
- Performance benchmark và các pattern serialization nâng cao

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS | Python |
|-----------|--------|--------|
| Path manipulation | `path` module, `path.join()` | `pathlib.Path`, `/` operator |
| Read file (sync) | `fs.readFileSync()` | `Path.read_text()` |
| Write file (sync) | `fs.writeFileSync()` | `Path.write_text()` |
| Read file (async) | `fs.promises.readFile()` | `await asyncio.to_thread(path.read_text)` |
| File existence | `fs.existsSync()` | `Path.exists()` |
| Directory listing | `fs.readdirSync()` | `path.iterdir()` |
| Recursive glob | `glob` package, `**/*.js` | `path.glob("**/*.py")` built-in |
| Resource cleanup | `try {} finally {}` | `with` statement |
| JSON parse | `JSON.parse()` | `json.loads()` |
| JSON stringify | `JSON.stringify(x, null, 2)` | `json.dumps(x, indent=2)` |
| Schema validation | `zod.parse()`, `class-validator` | `pydantic.BaseModel` |
| CSV | `csv-parse` package | `csv` stdlib |
| YAML | `js-yaml` package | `PyYAML` |
| TOML | `@iarna/toml` | `tomllib` (stdlib, 3.11+) |
| Path normalization | `path.resolve()` | `Path.resolve()` |
| File metadata | `fs.statSync()` | `Path.stat()` |

**Điểm khác biệt quan trọng:**
- Python `with` statement = automatic resource cleanup, không cần try/finally
- `pathlib.Path` sử dụng `/` operator để join paths (Pythonic và clean)
- Pydantic v2 là complete rewrite với Rust core — nhanh hơn v1 5-50x
- `yaml.safe_load()` PHẢI dùng thay vì `yaml.load()` (security vulnerability)
- TOML (Python 3.11+): `tomllib` chỉ đọc, để ghi cần `tomli-w` package

---

## 📖 Lý thuyết

### 1. pathlib — Modern File Paths

**WHY:** `pathlib.Path` là OOP interface cho file paths. Clean hơn `os.path`, cross-platform, và chainable. NodeJS có `path` module nhưng không elegant như pathlib.

```python
from pathlib import Path
from datetime import datetime
import shutil


# ===== Tạo và navigate paths =====

project = Path("/home/user/project")
config_file = project / "config" / "settings.json"  # / operator join paths

cwd = Path.cwd()    # Current working directory
home = Path.home()  # User home directory (~)

# Relative path
relative = Path("src/myapp/main.py")
absolute = relative.resolve()  # Convert thành absolute path


# ===== Properties =====

p = Path("/home/user/project/src/main.py")
print(p.name)       # "main.py"          — basename
print(p.stem)       # "main"             — basename without extension
print(p.suffix)     # ".py"              — extension
print(p.suffixes)   # [".py"]            — all extensions (e.g., [".tar", ".gz"])
print(p.parent)     # /home/user/project/src
print(p.parents[0]) # /home/user/project/src
print(p.parents[1]) # /home/user/project
print(p.parts)      # ('/', 'home', 'user', 'project', 'src', 'main.py')
print(p.is_absolute())  # True
print(p.is_relative_to("/home/user"))  # True (Python 3.9+)

# Thay đổi parts
new_path = p.with_name("app.py")      # /home/user/project/src/app.py
new_ext  = p.with_suffix(".txt")       # /home/user/project/src/main.txt
new_stem = p.with_stem("utils")        # /home/user/project/src/utils.py (3.9+)


# ===== Existence checks =====

config_file = Path("config.json")
print(config_file.exists())    # True/False
print(config_file.is_file())   # True nếu là regular file
print(config_file.is_dir())    # True nếu là directory
print(config_file.is_symlink()) # True nếu là symlink


# ===== Read/Write =====

# Text files
content: str = config_file.read_text(encoding="utf-8")
config_file.write_text('{"key": "value"}', encoding="utf-8")

# Binary files
data: bytes = Path("image.png").read_bytes()
Path("output.png").write_bytes(data)

# Open file handle (giống built-in open)
with config_file.open("r", encoding="utf-8") as f:
    data = json.load(f)


# ===== Directory operations =====

log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)   # mkdir -p equivalent

# Iterate directory
for item in Path("src").iterdir():
    if item.is_file():
        print(f"File: {item.name} ({item.stat().st_size} bytes)")

# Glob patterns
for py_file in Path("src").glob("**/*.py"):    # Recursive
    print(py_file)

for config in Path(".").glob("*.toml"):         # Non-recursive
    print(config)

# rglob = recursive glob (shorthand)
for py_file in Path("src").rglob("*.py"):
    print(py_file)


# ===== File operations =====

src = Path("old_name.txt")
dst = Path("new_name.txt")

src.rename(dst)               # Rename/Move (same filesystem)
shutil.move(str(src), str(dst))  # Move across filesystems

src.unlink(missing_ok=True)   # Delete file (no error if missing)
shutil.rmtree("old_dir")      # Delete directory recursively

shutil.copy2("src.txt", "dst.txt")  # Copy file (preserves metadata)
shutil.copytree("src_dir", "dst_dir")  # Copy directory recursively


# ===== File metadata =====

stat = config_file.stat()
print(f"Size: {stat.st_size:,} bytes")
print(f"Modified: {datetime.fromtimestamp(stat.st_mtime)}")
print(f"Created: {datetime.fromtimestamp(stat.st_ctime)}")


# ===== Practical example: Find all large Python files =====

def find_large_files(
    root: Path,
    pattern: str = "**/*.py",
    min_size_kb: int = 100,
) -> list[tuple[Path, int]]:
    """Tìm tất cả Python files lớn hơn min_size_kb."""
    results = []
    for filepath in root.glob(pattern):
        size_kb = filepath.stat().st_size // 1024
        if size_kb >= min_size_kb:
            results.append((filepath, size_kb))
    return sorted(results, key=lambda x: x[1], reverse=True)


# Usage
large_files = find_large_files(Path("src"), min_size_kb=50)
for path, size in large_files[:10]:
    print(f"{path.relative_to('src')}: {size}KB")
```

### 2. Context Managers

**WHY:** Context managers đảm bảo resources được cleanup dù có exception hay không. Tương đương try/finally nhưng reusable và elegant hơn. Mọi NodeJS developer quen với `try/finally`, Python `with` statement là idiom standard.

```python
import contextlib
from typing import Generator, Iterator
import time


# ===== Built-in context managers =====

# File — auto close sau with block
with open("file.txt", "r", encoding="utf-8") as f:
    content = f.read()
# f.close() được gọi tự động, dù có exception hay không

# Multiple context managers — Python 3.10+ parenthesized syntax
with (
    open("input.txt", encoding="utf-8") as infile,
    open("output.txt", "w", encoding="utf-8") as outfile,
):
    outfile.write(infile.read().upper())


# ===== Class-based context manager =====

class DatabaseConnection:
    """
    Context manager cho database connection.

    TypeScript equivalent:
    class DatabaseConnection {
        async [Symbol.asyncDispose]() { await this.close(); }
    }
    await using db = new DatabaseConnection(...);
    """

    def __init__(self, conn_string: str) -> None:
        self.conn_string = conn_string
        self._conn: object | None = None
        self._transaction_count = 0

    def __enter__(self) -> "DatabaseConnection":
        """Called khi vào with block. Return value gán cho `as` variable."""
        print(f"Connecting to {self.conn_string}")
        self._conn = {"connected": True}  # mock connection
        return self  # `as db` sẽ là instance này

    def __exit__(
        self,
        exc_type: type | None,    # Exception type nếu có exception
        exc_val: Exception | None, # Exception instance
        exc_tb: object,            # Traceback object
    ) -> bool:
        """
        Called khi rời khỏi with block (dù có exception hay không).

        Return True: suppress exception (không propagate)
        Return False/None: propagate exception
        """
        print(f"Disconnecting (exception: {exc_type})")
        self._conn = None

        if exc_type is not None:
            # Có exception xảy ra trong with block
            print(f"Rolling back due to {exc_type.__name__}")
            return False  # Propagate exception

        return False  # Không suppress

    def execute(self, query: str) -> list[dict]:
        if self._conn is None:
            raise RuntimeError("Not connected")
        return [{"result": query, "rows": 0}]

    def begin(self) -> None:
        print("BEGIN TRANSACTION")

    def commit(self) -> None:
        print("COMMIT")

    def rollback(self) -> None:
        print("ROLLBACK")


# Sử dụng
with DatabaseConnection("postgresql://localhost/mydb") as db:
    db.begin()
    results = db.execute("SELECT * FROM users")
    db.commit()
# db.close() được gọi tự động


# ===== @contextmanager — function-based (PREFERRED cho simple cases) =====

@contextlib.contextmanager
def timer(label: str = "timer") -> Generator[None, None, None]:
    """
    Context manager đo thời gian thực thi.

    Usage:
        with timer("database query"):
            results = db.query(...)
    """
    start = time.perf_counter()
    try:
        yield  # Code trong with block chạy ở đây
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"{label} FAILED after {elapsed:.4f}s: {e}")
        raise
    else:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.4f}s")


@contextlib.contextmanager
def temp_directory() -> Generator[Path, None, None]:
    """
    Tạo temporary directory, cleanup sau khi dùng.
    """
    import tempfile
    import shutil
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Cleaned up: {tmpdir}")


# Sử dụng
with temp_directory() as tmpdir:
    (tmpdir / "data.txt").write_text("hello")
    (tmpdir / "output.json").write_text("{}")
    print(f"Files: {list(tmpdir.iterdir())}")
# tmpdir và tất cả files bị xóa tự động


# ===== Async context manager =====

@contextlib.asynccontextmanager
async def async_db_session(url: str) -> "AsyncGenerator":
    """
    Async context manager cho database session.

    Usage:
        async with async_db_session(DB_URL) as session:
            await session.execute("SELECT 1")
    """
    session = None
    try:
        print(f"Opening async session: {url}")
        session = {"url": url, "active": True}  # mock
        yield session
    except Exception as e:
        print(f"Session error: {e}")
        if session:
            await asyncio.sleep(0)  # Simulate async rollback
        raise
    finally:
        if session:
            session["active"] = False
            print("Session closed")


# ===== contextlib utilities =====

# suppress — ignore specific exceptions elegantly
from contextlib import suppress

# Thay vì:
try:
    Path("tmp.txt").unlink()
except FileNotFoundError:
    pass

# Dùng suppress:
with suppress(FileNotFoundError):
    Path("tmp.txt").unlink()

# suppress multiple exceptions
with suppress(FileNotFoundError, PermissionError):
    Path("/etc/shadow").read_text()


# ExitStack — compose dynamic list of context managers
with contextlib.ExitStack() as stack:
    # Enter nhiều context managers
    files = [
        stack.enter_context(open(f"file_{i}.txt", "w"))
        for i in range(5)
    ]
    for i, f in enumerate(files):
        f.write(f"Content {i}\n")
    # Tất cả files tự đóng khi rời khỏi with block
    print(f"Wrote to {len(files)} files")


# ExitStack với callback
with contextlib.ExitStack() as stack:
    conn = stack.enter_context(DatabaseConnection("db://localhost"))
    # Register cleanup callback
    stack.callback(print, "Cleanup callback called!")
    stack.callback(lambda: print("Another cleanup"))
    # Callbacks chạy theo LIFO khi rời with block
```

### 3. Serialization — JSON, CSV, YAML, TOML

**WHY:** Python có excellent support cho các data formats thông qua stdlib và third-party libraries. Khác NodeJS cần packages như `csv-parse` và `js-yaml`, Python có `json` và `csv` built-in.

```python
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from decimal import Decimal


# ===== JSON =====

data = {
    "name": "Alice",
    "age": 25,
    "scores": [92, 88, 95],
    "metadata": {"created": "2024-01-15"},
}

# Serialize (dumps = dump to string)
json_str = json.dumps(data)                          # Compact
json_pretty = json.dumps(data, indent=2)             # Pretty print
json_sorted = json.dumps(data, indent=2, sort_keys=True)  # Sorted keys
json_unicode = json.dumps(data, ensure_ascii=False)  # UTF-8 (no \uXXXX escapes)

# Deserialize (loads = load from string)
parsed: dict = json.loads(json_str)

# File I/O
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

with open("data.json", encoding="utf-8") as f:
    loaded = json.load(f)

# pathlib shorthand
Path("data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
loaded = json.loads(Path("data.json").read_text(encoding="utf-8"))


# Custom JSON encoder — cho datetime, Decimal, custom objects
class AppJSONEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, datetime):
            return obj.isoformat()           # "2024-01-15T10:30:00"
        if isinstance(obj, Decimal):
            return float(obj)                # Hoặc str(obj) để preserve precision
        if hasattr(obj, "__dict__"):
            return obj.__dict__              # Generic object serialization
        return super().default(obj)          # Raise TypeError cho unknown types


data_with_datetime = {
    "name": "Alice",
    "created_at": datetime.now(),
    "balance": Decimal("99.99"),
}
json.dumps(data_with_datetime, cls=AppJSONEncoder)


# ===== CSV =====

rows = [
    {"name": "Alice", "age": 25, "score": 92, "city": "Hà Nội"},
    {"name": "Bob", "age": 30, "score": 78, "city": "TP.HCM"},
    {"name": "Charlie", "age": 28, "score": 85, "city": "Đà Nẵng"},
]

# Write CSV
with open("students.csv", "w", newline="", encoding="utf-8") as f:
    # QUAN TRỌNG: newline="" để tránh blank lines trên Windows
    writer = csv.DictWriter(f, fieldnames=["name", "age", "score", "city"])
    writer.writeheader()
    writer.writerows(rows)

# Read CSV
with open("students.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    students: list[dict] = list(reader)  # list of dicts

# CSV in-memory (không cần file)
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=["name", "age"])
writer.writeheader()
writer.writerows([{"name": "Alice", "age": 25}])
csv_content = output.getvalue()

# CSV với custom delimiter (TSV)
with open("data.tsv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(["name", "age"])
    writer.writerow(["Alice", 25])


# ===== YAML =====
# uv add pyyaml

import yaml

config = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "myapp",
        "pool_size": 10,
    },
    "redis": {"url": "redis://localhost:6379/0"},
    "features": ["auth", "billing", "notifications"],
}

# Serialize
yaml_str = yaml.dump(config, default_flow_style=False, allow_unicode=True)

# Deserialize — PHẢI dùng safe_load, KHÔNG dùng yaml.load()!
# yaml.load() có thể execute arbitrary Python code (CVE-2017-18342)
loaded_config = yaml.safe_load(yaml_str)

# File I/O
with open("config.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)


# ===== TOML =====
# tomllib: Python 3.11+ stdlib (read only)
# tomli: backport cho Python 3.9, 3.10 (uv add tomli)
# tomli-w: write TOML (uv add tomli-w)

import tomllib  # Python 3.11+

# Read TOML — phải mở ở binary mode ("rb")
with open("pyproject.toml", "rb") as f:
    project_config = tomllib.load(f)

# Đọc từ string
toml_str = """
[project]
name = "myapp"
version = "1.0.0"

[tool.ruff]
line-length = 100
"""
config = tomllib.loads(toml_str)
print(config["project"]["name"])  # "myapp"

# Write TOML (cần tomli-w)
# uv add tomli-w
try:
    import tomli_w
    with open("output.toml", "wb") as f:
        tomli_w.dump({"key": "value", "number": 42}, f)
except ImportError:
    print("tomli-w not installed, skip write")
```

**Security notes khi đọc file từ user/upload:**

- YAML: `yaml.safe_load()` là default cho dữ liệu không tin cậy; tránh `yaml.load()`/`unsafe_load()` vì có thể construct Python objects nguy hiểm.
- Path traversal: không ghép trực tiếp filename user gửi vào `Path("uploads") / filename` rồi đọc file. Luôn resolve path và kiểm tra nó vẫn nằm trong thư mục cho phép.
- Validate extension và content type; extension không đủ để tin rằng file thật sự là JSON/YAML/CSV.
- Giới hạn file size trước khi parse để tránh memory spike hoặc YAML/JSON quá lớn.

```python
from pathlib import Path

UPLOAD_ROOT = Path("uploads").resolve()


def safe_upload_path(filename: str) -> Path:
    candidate = (UPLOAD_ROOT / filename).resolve()
    if not candidate.is_relative_to(UPLOAD_ROOT):
        raise ValueError("Path traversal detected")
    if candidate.suffix not in {".json", ".yaml", ".yml", ".csv"}:
        raise ValueError("Unsupported file type")
    return candidate


path = safe_upload_path("reports/monthly.yaml")
content = path.read_text(encoding="utf-8")
```

### 4. Pydantic v2 — Validation & Serialization

**WHY:** Pydantic v2 là nền tảng của FastAPI. Tương đương `zod` (TypeScript) nhưng Python-native. Validate input, coerce types, serialize output. Pydantic v2 được viết lại bằng Rust (pydantic-core) — nhanh hơn v1 khoảng 5-50x.

**Pydantic v1 vs v2 — key differences (quan trọng khi đọc code cũ):**
- v1: `@validator`, `.dict()`, `.parse_obj()`, `.parse_raw()`
- v2: `@field_validator`, `.model_dump()`, `.model_validate()`, `.model_validate_json()`

```python
from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationError,
    computed_field,
)
from pydantic import EmailStr  # uv add pydantic[email]
from typing import Annotated
from datetime import datetime
from decimal import Decimal


# ===== Basic Model =====

class UserCreate(BaseModel):
    """
    Pydantic model cho user creation.

    TypeScript/zod equivalent:
        const UserCreateSchema = z.object({
            name: z.string().min(2).max(100),
            email: z.string().email(),
            age: z.number().int().min(0).max(150),
            password: z.string().min(8),
        });
    """

    # Annotated[type, Field(...)] = field với validation constraints
    name: Annotated[str, Field(min_length=2, max_length=100, description="Full name")]
    email: str  # Validated bằng @field_validator
    age: Annotated[int, Field(ge=0, le=150, description="Age in years")]
    password: Annotated[str, Field(min_length=8, exclude=True)]  # Không xuất hiện trong model_dump()
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True         # Default True

    model_config = ConfigDict(
        str_strip_whitespace=True,  # Auto strip whitespace từ strings
        validate_assignment=True,   # Validate khi assign obj.field = value
    )

    @field_validator("email")          # v2 syntax (thay @validator trong v1)
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate và normalize email."""
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[1]:
            raise ValueError("Invalid email format")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Name chỉ chứa letters, spaces, và hyphens."""
        if not all(c.isalpha() or c in " -" for c in v):
            raise ValueError("Name must contain only letters, spaces, and hyphens")
        return v.title()  # Auto capitalize

    @field_validator("tags", mode="before")
    @classmethod
    def lowercase_tags(cls, v: list[str]) -> list[str]:
        """Lowercase và deduplicate tags."""
        return list(set(tag.lower().strip() for tag in v))

    @model_validator(mode="after")
    def cross_field_validation(self) -> "UserCreate":
        """Cross-field validation sau khi tất cả fields đã validate."""
        if self.age < 13:
            raise ValueError("Users must be at least 13 years old")
        return self


# ===== Nested Models =====

class Address(BaseModel):
    street: str
    city: str
    state: str | None = None
    country: str = "Vietnam"
    postal_code: str | None = None


class UserResponse(BaseModel):
    """Response model — không có password, có thêm computed fields."""
    id: int
    name: str
    email: str
    age: int
    is_active: bool
    address: Address | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    # computed_field — không lưu trong DB, tính toán khi serialize
    @computed_field
    @property
    def display_name(self) -> str:
        return f"{self.name} <{self.email}>"

    model_config = ConfigDict(
        from_attributes=True,  # Cho phép parse từ SQLAlchemy ORM objects
        validate_by_name=True, # Chấp nhận field_name khi alias cũng tồn tại
        validate_by_alias=True,
    )


# ===== Sử dụng =====

# Validate và create
try:
    user = UserCreate(
        name="alice johnson",    # → "Alice Johnson" (auto titlecase)
        email="ALICE@EXAMPLE.COM",  # → "alice@example.com" (auto lowercase)
        age=25,
        password="securepass123",
        tags=["Python", "python", "FASTAPI"],  # → ["fastapi", "python"] (dedup + lower)
    )

    print(user.name)   # "Alice Johnson"
    print(user.email)  # "alice@example.com"
    print(user.tags)   # ["fastapi", "python"]

    # model_dump() — serialize to dict (v1: .dict())
    user_dict = user.model_dump()
    print(user_dict)
    # {"name": "Alice Johnson", "email": "alice@example.com", "age": 25, ...}
    # NOTE: password bị exclude vì Field(exclude=True)

    # model_dump_json() — serialize to JSON string
    json_str = user.model_dump_json(indent=2)

    # model_dump với options
    partial = user.model_dump(include={"name", "email"})  # Chỉ include fields này
    no_defaults = user.model_dump(exclude_defaults=True)   # Không include default values
    no_none = user.model_dump(exclude_none=True)           # Không include None values

except ValidationError as e:
    # ValidationError.errors() = list of error dicts
    for error in e.errors():
        loc = " → ".join(str(x) for x in error["loc"])  # e.g., "email"
        print(f"  [{loc}] {error['msg']} (type: {error['type']})")


# Parse từ dict (model_validate thay .parse_obj() trong v1)
user_data = {
    "name": "Bob Smith",
    "email": "bob@example.com",
    "age": 30,
    "password": "bobpassword123",
}
user = UserCreate.model_validate(user_data)

# Parse từ JSON string
user = UserCreate.model_validate_json(
    '{"name": "Charlie", "email": "charlie@example.com", "age": 28, "password": "charlie123"}'
)

# Parse từ ORM object (with from_attributes=True)
class FakeOrmUser:
    id = 1
    name = "Dave"
    email = "dave@example.com"
    age = 35
    is_active = True
    address = None
    tags = ["admin"]

orm_user = FakeOrmUser()
response = UserResponse.model_validate(orm_user)  # ORM → Pydantic
print(response.display_name)  # "Dave <dave@example.com>"
print(response.model_dump_json(indent=2))


# ===== Optional Reference: Pydantic Settings — load từ .env =====
# uv add pydantic-settings

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Application configuration từ environment variables.
    Tự động đọc từ .env file và environment.

    Equivalent NodeJS:
        const config = {
            port: parseInt(process.env.PORT || '8000'),
            databaseUrl: process.env.DATABASE_URL || '...',
        };
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,        # DATABASE_URL = database_url
        env_prefix="APP_",           # Chỉ đọc vars có prefix APP_
        extra="ignore",              # .env có biến khác không làm app fail
    )

    app_name: str = "MyApp"
    debug: bool = False
    port: int = 8000
    database_url: str = "postgresql://localhost/mydb"
    secret_key: str = Field(min_length=32)
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: list[str] = Field(default_factory=list)

    # Computed settings (không từ env)
    @computed_field
    @property
    def is_production(self) -> bool:
        return not self.debug


# .env file:
# APP_DEBUG=true
# APP_PORT=8080
# APP_DATABASE_URL=postgresql://user:pass@localhost/mydb
# APP_SECRET_KEY=my-super-secret-key-at-least-32-chars

# settings = AppSettings()
# print(settings.port)        # 8080 (từ env) hoặc 8000 (default)
# print(settings.debug)       # True (từ APP_DEBUG=true)
# print(settings.is_production)  # False
```

> Timebox Pydantic trong 25-30 phút: học validator, computed field, aliases, settings và strict/extra config ở mức đọc hiểu + chỉnh schema. Inheritance/discriminated unions là reference để dùng lại khi học FastAPI response schemas.

## ⚠️ Common Mistakes

| Mistake | Sai | Đúng |
|---------|-----|------|
| `yaml.load()` không safe | Arbitrary code execution risk | `yaml.safe_load()` LUÔN LUÔN |
| Dùng filename user gửi trực tiếp | `Path("uploads") / filename` có thể đọc `../secret` | Resolve path và check `is_relative_to(base)` |
| Quên `newline=""` khi write CSV | Extra blank lines trên Windows | `open("f.csv", "w", newline="")` |
| Pydantic v1 syntax | `@validator` deprecated | `@field_validator` (v2) |
| Không handle `ValidationError` | Unhandled exception | `except pydantic.ValidationError as e:` |
| Không specify encoding | UnicodeDecodeError trên Windows | `read_text(encoding="utf-8")` |
| TOML read ở text mode | `open("f.toml", "r")` → TypeError | `open("f.toml", "rb")` (binary mode) |
| `return True` trong `__exit__` vô tình | Suppress unexpected exceptions | Chỉ suppress exceptions bạn xử lý được |
| `model_dump()` include password | Leak sensitive data trong logs/API | `Field(exclude=True)` cho sensitive fields |

---

## ✅ Best Practices

**File I/O:**
- Luôn dùng `pathlib.Path` thay `os.path`
- Luôn specify `encoding="utf-8"` khi đọc/ghi text files
- Dùng `with` statement cho mọi file operations
- `parents=True, exist_ok=True` khi tạo directories

**Context Managers:**
- `@contextmanager` decorator cho simple context managers
- Class-based context manager khi cần state hoặc complex logic
- `contextlib.suppress()` thay try/except/pass
- `ExitStack` khi cần dynamic number of context managers

**Serialization:**
- `yaml.safe_load()` KHÔNG BAO GIỜ `yaml.load()`
- TOML file phải đọc ở binary mode (`"rb"`)
- `ensure_ascii=False` cho JSON với Unicode characters
- CSV: `newline=""` khi write

**Pydantic:**
- `@field_validator` (v2) thay `@validator` (v1)
- `model_dump()` thay `.dict()` (v1)
- `model_validate()` thay `.parse_obj()` (v1)
- `Field(exclude=True)` cho passwords, tokens
- `model_config = ConfigDict(from_attributes=True)` để parse SQLAlchemy objects

---

## ⚖️ Trade-offs

| Format | Human readable | Performance | Schema validation | Khi nào dùng |
|--------|---------------|-------------|-------------------|--------------|
| JSON | Medium | Fast (orjson: rất nhanh) | Không | API data, config, logs |
| YAML | Tốt | Chậm nhất | Không | Config files (readable) |
| TOML | Tốt | Medium | Không | Project config (pyproject.toml) |
| CSV | Tốt | Fast | Không | Tabular data, Excel exchange |
| Protobuf | Không | Cực nhanh | Có (schema) | High-perf APIs, microservices |
| MessagePack | Không | Rất nhanh | Không | Cache, inter-service |

| Library | Speed | Features | Khi dùng |
|---------|-------|----------|-----------|
| `json` (stdlib) | Medium | Basic | Default choice |
| `ujson` | 2-3x faster | Drop-in replacement | Medium perf needs |
| `orjson` | Fastest (Rust) | datetime/numpy, bytes | High-perf APIs |
| `pydantic` | Fast (Rust core v2) | Validation, schema | FastAPI, data validation |

---

## 🚀 Performance Notes

```python
import timeit
import json

# JSON performance comparison
data = {"users": [{"id": i, "name": f"User {i}"} for i in range(1000)]}

json_time = timeit.timeit(lambda: json.dumps(data), number=1000)
print(f"json: {json_time:.3f}s")

try:
    import orjson
    orjson_time = timeit.timeit(lambda: orjson.dumps(data), number=1000)
    print(f"orjson: {orjson_time:.3f}s")  # Thường nhanh hơn 3-10x
except ImportError:
    print("orjson not installed")

# Pydantic v2 performance
from pydantic import BaseModel

class Item(BaseModel):
    id: int
    name: str
    price: float

items_data = [{"id": i, "name": f"Item {i}", "price": i * 1.5} for i in range(1000)]
pydantic_time = timeit.timeit(
    lambda: [Item.model_validate(d) for d in items_data],
    number=100,
)
print(f"Pydantic v2 validate 1000 items x100: {pydantic_time:.3f}s")
```

---

## 📚 Pydantic v2 Deep Dive — Reference Có Chọn Lọc

*Đọc chọn lọc sau phần core. Đây là phần dùng nhiều trong FastAPI/config thực tế, nhưng không cần thuộc toàn bộ trong buổi 2 giờ.*

```python
from pydantic import BaseModel, ConfigDict, Field, AliasPath, AliasChoices
from pydantic import field_validator, model_validator, computed_field
from typing import Annotated, Literal
from typing import Union

# --- Serialization Aliases ---
# Vấn đề thực tế: API trả về snake_case nhưng DB dùng camelCase,
# hoặc external API dùng field names khác với code của bạn

class ExternalAPIResponse(BaseModel):
    # validation_alias: tên field khi NHẬN data (từ API, JSON)
    # serialization_alias: tên field khi XUẤT data (serialize sang JSON)
    # alias: dùng cho cả nhận và xuất

    user_name: str = Field(
        validation_alias="userName",
        serialization_alias="userName",
    )
    user_id: int = Field(
        validation_alias="userId",
        serialization_alias="userId",
    )

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

# Parse từ external API data (camelCase)
data = {"userName": "alice", "userId": 42}
user = ExternalAPIResponse.model_validate(data)
print(user.user_name)   # "alice" — access với snake_case trong code
print(user.user_id)     # 42
print(user.model_dump(by_alias=True))  # {"userName": "alice", "userId": 42}

# AliasChoices — chấp nhận NHIỀU alias khác nhau (v2 tính năng)
class FlexibleModel(BaseModel):
    user_id: int = Field(
        validation_alias=AliasChoices("userId", "user_id", "id")
    )

FlexibleModel.model_validate({"userId": 1})     # OK
FlexibleModel.model_validate({"user_id": 2})    # OK
FlexibleModel.model_validate({"id": 3})         # OK

# AliasPath — nested JSON flattening
class FlattenedAddress(BaseModel):
    city: str = Field(validation_alias=AliasPath("address", "city"))
    country: str = Field(validation_alias=AliasPath("address", "country"))

nested = {"address": {"city": "Hanoi", "country": "Vietnam"}}
addr = FlattenedAddress.model_validate(nested)
print(addr.city)     # "Hanoi" — flat access!
print(addr.country)  # "Vietnam"
```

```python
# --- Model Inheritance ---
from pydantic import BaseModel

class AnimalBase(BaseModel):
    name: str
    age: int

class Dog(AnimalBase):
    breed: str
    trained: bool = False

class Cat(AnimalBase):
    indoor: bool = True

# Inheritance hoạt động như expected — Cat/Dog kế thừa name + age
dog = Dog(name="Rex", age=3, breed="Labrador")
print(dog.model_dump())  # {'name': 'Rex', 'age': 3, 'breed': 'Labrador', 'trained': False}

# Database pattern: Base → Create → Read (chuẩn trong FastAPI)
class UserBase(BaseModel):
    email: str
    name: str

class UserCreate(UserBase):   # Request body — thêm password
    password: str

class UserRead(UserBase):     # Response — thêm id, bỏ password
    id: int
    model_config = ConfigDict(from_attributes=True)  # Đọc từ SQLAlchemy model

# UserCreate có thể validate request, UserRead có thể serialize response
# Không trùng lặp code — DRY principle
```

```python
# --- Discriminated Unions — type-safe polymorphism ---
# Vấn đề: API có thể trả về nhiều loại object khác nhau
# Tương đương: discriminated union trong TypeScript (type: "circle" | "square")

from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field

class Circle(BaseModel):
    shape_type: Literal["circle"]  # discriminator field
    radius: float

class Rectangle(BaseModel):
    shape_type: Literal["rectangle"]
    width: float
    height: float

class Triangle(BaseModel):
    shape_type: Literal["triangle"]
    base: float
    height: float

# Discriminated union — Pydantic chọn đúng model dựa trên "shape_type"
Shape = Annotated[
    Union[Circle, Rectangle, Triangle],
    Field(discriminator="shape_type")
]

class Drawing(BaseModel):
    shapes: list[Shape]

# Pydantic tự parse đúng loại shape
drawing = Drawing.model_validate({
    "shapes": [
        {"shape_type": "circle", "radius": 5.0},
        {"shape_type": "rectangle", "width": 10.0, "height": 3.0},
        {"shape_type": "triangle", "base": 4.0, "height": 6.0},
    ]
})

for shape in drawing.shapes:
    if isinstance(shape, Circle):
        print(f"Circle with radius {shape.radius}")
    elif isinstance(shape, Rectangle):
        print(f"Rectangle {shape.width}x{shape.height}")
```

```python
# --- model_config: strict mode + extra fields ---
from pydantic import BaseModel, ConfigDict

# strict=True: không coerce types — "42" sẽ fail thay vì được ép thành int
class StrictUser(BaseModel):
    model_config = ConfigDict(strict=True)
    user_id: int
    name: str

# StrictUser(user_id="42", name="Alice")  # ERROR: strict mode, "42" không phải int
StrictUser(user_id=42, name="Alice")  # OK

# extra="forbid": reject bất kỳ field nào không khai báo trong model
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    age: int

# Strict(name="Alice", age=30, unknown_field="x")  # ValidationError!

# extra="ignore" (default): silently discard extra fields
# extra="allow": chấp nhận extra fields, lưu vào __pydantic_extra__
```

## 📝 Tóm tắt

| Concept | Key Point | NodeJS Analogy |
|---------|-----------|----------------|
| `pathlib.Path` | OOP file paths, `/` operator join | `path.join()` + `.` notation |
| `Path.glob("**/*.py")` | Built-in recursive glob | `glob` package |
| `with` statement | Resource management (auto cleanup) | `try/finally` hoặc `using` (TS 5.2) |
| `@contextmanager` | Function-based context manager | Không có trực tiếp |
| `contextlib.suppress` | Ignore specific exceptions | try/catch với empty body |
| `json.dumps/loads` | JSON serialize/deserialize | `JSON.stringify/parse` |
| `yaml.safe_load()` | Safe YAML parse | `yaml.load()` trong js-yaml |
| `tomllib.load()` | TOML parse (stdlib 3.11+) | `@iarna/toml` |
| Pydantic `BaseModel` | Validation + serialization | `zod`, `class-validator` |
| `@field_validator` | Field-level validation | zod `.refine()` |
| `@model_validator` | Cross-field validation | zod `.superRefine()` |
| `model_dump()` | Serialize to dict | Không có exact equiv |
| `Field(exclude=True)` | Exclude từ serialization | Custom transform |
| `from_attributes=True` | Parse từ ORM objects | N/A |
