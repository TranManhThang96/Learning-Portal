# Ngày 06: Modules, Packages & Project Structure

## 🎯 Mục tiêu học tập

- Hiểu Python import system: absolute vs relative imports, `__all__`, `__init__.py`
- Tổ chức code thành packages với structure rõ ràng
- Setup production project structure theo best practices
- Cấu hình `pyproject.toml` hoàn chỉnh với uv, ruff, mypy, pytest
- Implement structured logging với `structlog`

## 🧭 Lộ trình học trong 2 giờ

**Must Learn (làm trong ngày):**
- Import system cơ bản: absolute import, relative import, `__init__.py`, `__all__`
- `src/` layout cho một package nhỏ
- `pyproject.toml` tối thiểu với runtime deps, dev deps, ruff, mypy, pytest
- Smoke commands để chứng minh package import/test/lint/type-check được

**Optional Reference (đọc khi cần):**
- Dynamic imports, plugin registration, reload module
- Production layout đầy đủ cho FastAPI/database service
- `structlog` deep dive và request context
- Design patterns/DI preview ở cuối bài: scan 15-20 phút, không cố implement toàn bộ trong buổi 2 giờ

## 🔄 So sánh NodeJS vs Python

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Module file | `module.ts` (default export hoặc named) | `module.py` (tất cả top-level là public) |
| Default export | `export default class Foo` | Không có, dùng `__all__` |
| Named export | `export const foo = ...` | Mọi name ở top-level đều export được |
| Re-export | `export { Foo } from './foo'` | `from .foo import Foo` trong `__init__.py` |
| Barrel file | `index.ts` | `__init__.py` |
| Import | `import { Foo } from './foo'` | `from .foo import Foo` |
| Namespace import | `import * as utils from './utils'` | `import utils` |
| Dynamic import | `await import('./foo')` | `importlib.import_module('foo')` |
| Private symbol | Không export | Không có trong `__all__`, prefix `_` |
| Package | `package.json` + `node_modules` | `pyproject.toml` + `.venv` |
| Entry point | `"main": "dist/index.js"` | `[project.scripts]` trong pyproject.toml |
| Monorepo | Workspaces (yarn/pnpm) | uv workspaces / namespace packages |

**Điểm khác biệt quan trọng:**
- Python không có "default export" — mọi name đều export bằng cách access `module.name`
- `__init__.py` là "barrel file" — quyết định public API của package
- `__all__` control những gì được export khi dùng `from module import *`
- Python có circular import issues nếu không organize cẩn thận
- `_` prefix là convention "private", không phải hard rule

---

## 📖 Lý thuyết

### 1. Import System

**Absolute vs Relative Imports:**

```
myapp/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   └── product.py
├── services/
│   ├── __init__.py
│   └── user_service.py
└── utils/
    ├── __init__.py
    └── helpers.py
```

```python
# ===== Absolute imports — khuyến khích dùng =====
# Luôn import từ root package, rõ ràng, tránh nhầm lẫn
from myapp.models.user import User
from myapp.services.user_service import UserService
import myapp.utils.helpers as helpers

# ===== Relative imports — dùng trong internal package code =====
# Trong myapp/services/user_service.py:
from ..models.user import User          # Go up 1 level, vào models
from ..models.product import Product    # Go up 1 level, vào models
from ..utils.helpers import format_name # Go up 1 level, vào utils
from . import user_service              # Import từ cùng package

# . = current package
# .. = parent package
# ... = grandparent package

# ===== KHÔNG dùng relative imports cho cross-package =====
# BAD: Trong myapp/services/user_service.py
# from myapp.models.user import User  ← absolute OK
# from ..models.user import User      ← relative OK
# from models.user import User        ← WRONG: không rõ đây là package nào
```

**`__all__` — Explicit Public API:**

```python
# myapp/models/__init__.py

# Import nội bộ
from .user import User, UserStatus
from .product import Product, ProductCategory
from .order import Order, OrderItem

# Khai báo public API của package
# Khi ai đó làm: from myapp.models import *
# Chỉ những gì trong __all__ mới được import
__all__ = [
    "User",
    "UserStatus",
    "Product",
    "ProductCategory",
    "Order",
    "OrderItem",
]

# _BaseModel sẽ KHÔNG được import qua *
# (dù có thể access trực tiếp: from myapp.models._base import _BaseModel)
```

**`__init__.py` Patterns:**

```python
# Pattern 1: Barrel — re-export everything
# myapp/models/__init__.py
from .user import User
from .product import Product
from .order import Order

# Cho phép: from myapp.models import User
# Thay vì: from myapp.models.user import User


# Pattern 2: Lazy imports — giảm import time
# myapp/__init__.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Chỉ import khi type checking, không phải runtime
    from .models.user import User
    from .services.user_service import UserService


# Pattern 3: Version info
# myapp/__init__.py
__version__ = "1.0.0"
__author__ = "Your Name"
__all__ = ["UserService", "User"]


# Pattern 4: Plugin registration
# myapp/__init__.py
import importlib
import pkgutil

def _load_plugins():
    """Auto-load tất cả modules trong plugins/ directory."""
    import myapp.plugins
    for _, name, _ in pkgutil.iter_modules(myapp.plugins.__path__):
        importlib.import_module(f"myapp.plugins.{name}")

_load_plugins()
```

**Import tricks và `importlib`:**

```python
import importlib
import importlib.util
import sys


# Dynamic import theo string name
def load_module(module_name: str):
    """Load module theo tên."""
    return importlib.import_module(module_name)

json_module = load_module("json")
print(json_module.dumps({"key": "value"}))


# Conditional import — fallback
try:
    import ujson as json  # Faster JSON library nếu có
except ImportError:
    import json           # Fallback to stdlib


# Import từ file path
def import_from_path(module_name: str, file_path: str):
    """Load module từ absolute file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Reload module (useful khi hot-reloading)
import importlib
import myapp.config
importlib.reload(myapp.config)  # Reload config sau khi thay đổi file


# Circular import — cách giải quyết
# Vấn đề: a.py imports từ b.py, b.py imports từ a.py
# Solution 1: Move import vào function body
# Solution 2: Import module thay vì specific name
# Solution 3: TYPE_CHECKING guard
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from myapp.models.user import User  # Chỉ dùng trong type hints
```

---

### 2. Production Project Structure

**Cấu trúc đầy đủ cho FastAPI/Python service:**

```
myapp/
├── .venv/                          # Virtual environment (do uv quản lý)
├── .git/
├── .gitignore
├── .python-version                 # pyenv Python version
├── pyproject.toml                  # Project config (pip, ruff, mypy, pytest)
├── uv.lock                         # Lock file (commit to git)
├── README.md
│
├── src/                            # Source root (src layout)
│   └── myapp/
│       ├── __init__.py             # Package init, version
│       ├── main.py                 # FastAPI app entry point
│       ├── settings.py             # Pydantic Settings config
│       │
│       ├── core/                   # Core utilities
│       │   ├── __init__.py
│       │   ├── logging.py          # structlog setup
│       │   ├── exceptions.py       # Base exceptions
│       │   └── security.py         # Auth, JWT
│       │
│       ├── models/                 # SQLAlchemy ORM models
│       │   ├── __init__.py
│       │   ├── base.py             # DeclarativeBase
│       │   ├── user.py
│       │   └── product.py
│       │
│       ├── schemas/                # Pydantic schemas (request/response)
│       │   ├── __init__.py
│       │   ├── user.py             # UserCreate, UserRead, UserUpdate
│       │   └── product.py
│       │
│       ├── repositories/           # Data access layer
│       │   ├── __init__.py
│       │   ├── base.py             # Generic CRUD repository
│       │   └── user_repository.py
│       │
│       ├── services/               # Business logic
│       │   ├── __init__.py
│       │   └── user_service.py
│       │
│       └── routers/                # FastAPI route handlers
│           ├── __init__.py
│           ├── users.py
│           └── products.py
│
├── tests/
│   ├── conftest.py                 # pytest fixtures
│   ├── unit/
│   │   ├── test_user_service.py
│   │   └── test_repositories.py
│   └── integration/
│       └── test_api.py
│
├── scripts/
│   ├── seed_db.py
│   └── migrate.py
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

**Ví dụ code cho từng layer:**

```python
# src/myapp/__init__.py
"""MyApp — Production Python Service."""

__version__ = "1.0.0"
__all__ = ["create_app"]


# src/myapp/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings từ environment variables.
    Pydantic Settings tự động đọc từ .env file và environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "MyApp"
    debug: bool = False
    api_version: str = "v1"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/mydb"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "console"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()


# Sử dụng:
# settings = get_settings()
# print(settings.database_url)
```

```python
# src/myapp/models/base.py
from datetime import datetime
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class cho tất cả SQLAlchemy models."""
    pass


class TimestampMixin:
    """Mixin thêm created_at và updated_at."""
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), onupdate=func.now()
    )


# src/myapp/models/user.py
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"
```

```python
# src/myapp/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}  # Cho phép từ ORM model
```

```python
# src/myapp/repositories/base.py
from typing import Generic, TypeVar, Type, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from myapp.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository."""

    def __init__(self, model: Type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
```

---

### 3. pyproject.toml Hoàn Chỉnh

```toml
# pyproject.toml

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# ============================================================
# Project metadata
# ============================================================
[project]
name = "myapp"
version = "1.0.0"
description = "Production Python Service"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Your Name", email = "you@example.com" }]

# Runtime dependencies
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "sqlalchemy>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.1",
    "structlog>=24.1.0",
    "httpx>=0.27.0",
    "python-jose[cryptography]>=3.3.0",
]

# Dependency groups cho tooling development.
# `uv add --dev ruff mypy pytest` sẽ cập nhật group này và uv.lock.
[dependency-groups]
dev = [
    "ruff>=0.4.7",
    "mypy>=1.10.0",
    "pre-commit>=3.7.1",
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",        # Test client
    "factory-boy>=3.3.0",   # Test factories
    "faker>=25.2.0",         # Fake data
]

# CLI entry points: chỉ dùng cho command-line callable.
# ASGI app chạy bằng: uv run uvicorn myapp.main:app --reload
[project.scripts]
myapp-cli = "myapp.cli:main"

# ============================================================
# uv — Package manager config
# ============================================================
[tool.uv]
default-groups = ["dev"]

# ============================================================
# Hatchling — Build config
# ============================================================
[tool.hatch.build.targets.wheel]
packages = ["src/myapp"]

# ============================================================
# ruff — Linter và Formatter
# ============================================================
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "N",    # pep8-naming
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking (move TYPE_CHECKING imports)
    "ANN",  # flake8-annotations (type hints)
    "S",    # flake8-bandit (security)
    "RUF",  # ruff-specific rules
]
ignore = [
    "ANN101",  # Missing type annotation for self
    "ANN102",  # Missing type annotation for cls
    "S101",    # Use of assert (OK in tests)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["ANN", "S"]  # Tests không cần type annotations
"scripts/**/*.py" = ["S603"]    # Scripts có thể dùng subprocess

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"

# ============================================================
# mypy — Static type checker
# ============================================================
[tool.mypy]
python_version = "3.12"
strict = true                        # Enable tất cả strict checks
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true

# Per-module overrides
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false       # Tests ít strict hơn

[[tool.mypy.overrides]]
module = "alembic.*"
ignore_missing_imports = true       # alembic stubs không đầy đủ

# ============================================================
# pytest — Test runner
# ============================================================
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"               # Tự động handle async tests
addopts = [
    "--cov=src/myapp",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",
    "-v",
]
filterwarnings = [
    "error",                        # Treat warnings as errors
    "ignore::DeprecationWarning",   # Ignore deprecation warnings
]

# ============================================================
# coverage
# ============================================================
[tool.coverage.run]
source = ["src/myapp"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

**Smoke commands cho package vừa tạo:**

```bash
uv sync --group dev
uv run python -c "import myapp; print(myapp.__name__)"
uv run uvicorn myapp.main:app --reload
uv run pytest
uv run ruff check src tests
uv run mypy src
```

> Nếu chưa có test hoặc mypy config đầy đủ, smoke tối thiểu là `uv run python -m myapp`
> hoặc `uv run python -c "from myapp.settings import get_settings; print(get_settings().app_name)"`.

---

### 4. Logging với structlog

**WHY:** `structlog` cho phép logging có structure (JSON) thay vì plain text. Cực kỳ quan trọng cho production: dễ parse, dễ filter, tích hợp tốt với ELK Stack, Datadog, CloudWatch. NodeJS developers quen với `pino` hoặc `winston` — structlog tương đương.

**Setup structlog:**

```python
# src/myapp/core/logging.py
from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",  # "json" | "console"
) -> None:
    """
    Configure structlog cho toàn bộ application.

    Gọi một lần duy nhất khi khởi động app.
    NodeJS equivalent: logger = pino({ level: 'info', transport: ... })
    """

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Helper function lấy logger (lazy binding)
def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Lấy logger instance với optional name binding."""
    return structlog.get_logger(name)
```

**Sử dụng structlog:**

```python
import structlog

logger = structlog.get_logger(__name__)


# Basic logging
logger.info("Server started", host="0.0.0.0", port=8000)
# Output JSON:
# {"event": "Server started", "host": "0.0.0.0", "port": 8000,
#  "level": "info", "timestamp": "2024-01-15T10:30:00Z", "logger": "myapp.main"}

logger.warning("High memory usage", usage_mb=1024, threshold_mb=800)
logger.error("Database connection failed", error="timeout", retry_count=3)


# bind() — add context that persists for all subsequent logs from this logger
# Equivalent to pino's child() in NodeJS
request_logger = logger.bind(
    request_id="req-abc-123",
    user_id="user-456",
    endpoint="/api/users",
)

request_logger.info("Request received")
request_logger.info("Processing complete", duration_ms=45)
# Cả hai log đều có request_id, user_id, endpoint


# contextvars — bind context globally trong async context (per-request)
import structlog.contextvars

# Trong middleware:
def bind_request_context(request_id: str, user_id: str | None = None) -> None:
    """Bind request context — sẽ xuất hiện trong TẤT CẢ logs của request này."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        user_id=user_id,
    )


# FastAPI middleware example:
from fastapi import Request
import uuid

async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        url=str(request.url),
    )

    logger.info("Request started")
    response = await call_next(request)
    logger.info("Request completed", status_code=response.status_code)

    return response


# Exception logging
try:
    result = 1 / 0
except ZeroDivisionError:
    logger.exception("Division failed", numerator=1, denominator=0)
    # Tự động include stack trace!


# Log levels
logger.debug("Debug info", data={"key": "value"})
logger.info("Info message")
logger.warning("Warning", threshold=0.9, current=0.95)
logger.error("Error occurred", error_code=500)
logger.critical("Critical failure", service="database")
```

**Structured logging trong service class:**

```python
# src/myapp/services/user_service.py
from __future__ import annotations

import structlog
from myapp.models.user import User
from myapp.schemas.user import UserCreate, UserRead
from myapp.repositories.user_repository import UserRepository
from myapp.core.exceptions import NotFoundError, ConflictError

logger = structlog.get_logger(__name__)


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo
        self._logger = logger.bind(service="UserService")

    async def create_user(self, data: UserCreate) -> UserRead:
        log = self._logger.bind(email=data.email)
        log.info("Creating user")

        # Check duplicate
        existing = await self._repo.find_by_email(data.email)
        if existing:
            log.warning("Email already registered")
            raise ConflictError(f"Email {data.email} already exists")

        user = User(email=data.email, name=data.name)
        user = await self._repo.create(user)

        log.info("User created successfully", user_id=user.id)
        return UserRead.model_validate(user)

    async def get_user(self, user_id: int) -> UserRead:
        log = self._logger.bind(user_id=user_id)
        log.debug("Fetching user")

        user = await self._repo.get(user_id)
        if not user:
            log.warning("User not found")
            raise NotFoundError(f"User {user_id} not found")

        log.debug("User found", email=user.email)
        return UserRead.model_validate(user)
```

---

## ⚠️ Common Mistakes

| Mistake | Sai | Đúng |
|---------|-----|------|
| Relative import ngoài package | `from .models import User` trong script | Chỉ dùng relative imports bên trong package |
| Circular import | `a.py` imports `b.py`, `b.py` imports `a.py` | Refactor, hoặc dùng `TYPE_CHECKING` guard |
| Import `*` trong production | `from models import *` | `from models import User, Product` (explicit) |
| Quên `__init__.py` | Package không có `__init__.py` | Add `__init__.py` (có thể rỗng) |
| Log sensitive data | `logger.info("Login", password=pwd)` | Không log passwords, tokens, PII |
| print() thay vì logger | `print(f"Error: {e}")` | `logger.error("Operation failed", error=str(e))` |

---

## ✅ Best Practices

**Import organization:**
- Nhóm imports theo: stdlib → third-party → local (ruff/isort tự làm việc này)
- Dùng absolute imports trong production code
- Relative imports chỉ dùng trong internal package code
- Khai báo `__all__` trong tất cả public packages

**Project structure:**
- Dùng `src/` layout để tránh confuse với installed package
- Tách rõ layers: models, schemas, repositories, services, routers
- Không để business logic trong routers
- Không để database queries trong services (dùng repositories)

**Logging:**
- Setup logging một lần ở entry point (main.py)
- Dùng `structlog.contextvars` cho per-request context
- Production default là JSON logs ra stdout/stderr để container runtime thu thập; development có thể dùng console renderer
- Không log sensitive data (passwords, tokens, credit cards, raw PII); nếu cần trace user, log stable ID đã scrub/masked
- Luôn log exception bằng `logger.exception(...)` hoặc `exc_info=True` để giữ traceback
- Log cả happy path (info) và error path (error/warning)

---

## ⚖️ Trade-offs

| Approach | Pros | Cons | Khi dùng |
|----------|------|------|-----------|
| Flat structure | Đơn giản, ít boilerplate | Khó scale, coupling | Small scripts, CLIs |
| Layered architecture | Clean separation, testable | Boilerplate nhiều | Production services |
| `src/` layout | Tránh shadowing, clean | Cần config thêm | Projects distribute như package |
| Flat layout | Simpler config | Import confusion | Apps không distribute |
| JSON logs | Machine-readable, searchable | Khó đọc trong dev | Production |
| Console logs | Human-readable | Khó parse | Development |

---

## 📚 Optional Reference — Design Patterns trong Python

> **Quan trọng**: Python là first-class functions + duck typing — patterns ở đây thực hiện khác hơn TypeScript/Java!
> Không cần học hết trong Day06; phần này là preview để tra lại khi làm project lớn hoặc chuẩn bị Day12/13.

```python
# --- Singleton ---
# Python way: module-level instance (không cần class-based Singleton)
# Module chỉ được import một lần → instance tự động là singleton

# database.py
import asyncpg

_pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool("postgresql://...")
    return _pool

# Usage: from database import get_pool — cùng pool được reuse
# Tương đương NestJS: @Injectable() singleton service

# Class-based khi cần (ít phổ biến hơn trong Python):
class Config:
    _instance: "Config | None" = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

```python
# --- Factory Pattern — function-based (không cần Abstract Class) ---
# Python không cần interface/abstract class như Java/TypeScript
from typing import Protocol

class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...

class OpenAIProvider:
    def complete(self, prompt: str) -> str:
        return f"OpenAI response to: {prompt}"

class AnthropicProvider:
    def complete(self, prompt: str) -> str:
        return f"Anthropic response to: {prompt}"

# Factory = function (không cần Factory class!)
def create_llm_provider(provider: str) -> LLMProvider:
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}")
    return providers[provider]()

# So sánh TypeScript: cần abstract class LLMProvider + implements
# Python: Protocol (structural typing) + duck typing — cleaner!
```

```python
# --- Strategy Pattern — dùng functions (không cần class hierarchy) ---
from typing import Callable

def chunk_by_tokens(text: str, chunk_size: int) -> list[str]:
    """Strategy 1: chunk by token count."""
    words = text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def chunk_by_sentence(text: str, chunk_size: int) -> list[str]:
    """Strategy 2: chunk by sentences."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return sentences[:chunk_size]  # simplified

# Strategy là function — không cần Strategy class!
ChunkStrategy = Callable[[str, int], list[str]]

class DocumentProcessor:
    def __init__(self, chunk_strategy: ChunkStrategy) -> None:
        self._chunk = chunk_strategy  # Inject strategy

    def process(self, text: str) -> list[str]:
        return self._chunk(text, chunk_size=100)

# Swap strategy tại runtime
processor = DocumentProcessor(chunk_strategy=chunk_by_tokens)
# processor = DocumentProcessor(chunk_strategy=chunk_by_sentence)  # đổi strategy
```

```python
# --- Observer / Event Pattern ---
from typing import Callable, Any
from dataclasses import dataclass, field

@dataclass
class EventEmitter:
    """Simplified EventEmitter — giống NodeJS EventEmitter."""
    _handlers: dict[str, list[Callable]] = field(default_factory=dict)

    def on(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for handler in self._handlers.get(event, []):
            handler(*args, **kwargs)

emitter = EventEmitter()
emitter.on("user_created", lambda user: print(f"Send welcome email to {user['email']}"))
emitter.on("user_created", lambda user: print(f"Log: new user {user['name']}"))
emitter.emit("user_created", {"name": "Alice", "email": "alice@example.com"})
```

```python
# --- Dependency Injection — không cần framework (khác NestJS) ---
# FastAPI sử dụng Depends() — xem Ngày 13
# Trong pure Python, DI đơn giản = constructor injection

from typing import Protocol

class DatabaseProtocol(Protocol):
    def query(self, sql: str) -> list[dict]: ...

class UserRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db  # Injected!

    def find_by_id(self, user_id: int) -> dict | None:
        results = self._db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return results[0] if results else None

# Production:
# repo = UserRepository(db=PostgresDatabase(...))
# Testing:
# repo = UserRepository(db=MockDatabase())  # Inject mock!

# Repository pattern preview — sẽ dùng nhiều ở Ngày 12 (Database)
```

> **Key insight:** Python patterns thường đơn giản hơn Java/TypeScript vì:
> - First-class functions thay thế Strategy/Command class hierarchy
> - Duck typing thay thế interfaces
> - Module system xử lý Singleton tự nhiên
> - Decorator pattern built-in (`@property`, `@classmethod`, custom decorators)

## 📝 Tóm tắt

| Concept | Key Point | NodeJS Analogy |
|---------|-----------|----------------|
| `__init__.py` | Barrel file, define public API | `index.ts` |
| `__all__` | Control `from x import *` | Named exports |
| Absolute import | `from myapp.models import User` | `import { User } from '@/models'` |
| Relative import | `from ..models import User` | `import { User } from '../models'` |
| `src/` layout | Source separate từ config | Tương tự `src/` folder |
| `pyproject.toml` | All-in-one config | `package.json` + `.eslintrc` + `jest.config.js` |
| `structlog` | Structured logging, context binding | `pino` / `winston` |
| `contextvars` | Per-request context (async safe) | `AsyncLocalStorage` trong Node |
| Design Patterns | Functions > class hierarchy trong Python | Ít boilerplate hơn Java/TS |
