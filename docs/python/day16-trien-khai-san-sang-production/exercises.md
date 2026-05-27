# Ngày 16: Bài Tập Thực Hành

**Primary lab của ngày 16:** Bài 1-3 tạo một deployment path hoàn chỉnh cho FastAPI container. Celery/ARQ và CI/CD là optional reference trong `lesson.md`, không cần làm để hoàn thành ngày này.

## Bài 1 (Cơ bản): Dockerfile Multi-Stage cho FastAPI App

### Mục tiêu

Viết Dockerfile multi-stage cho một FastAPI app, verify non-root user, và đo sự khác biệt image size so với single-stage.

### Yêu cầu

Tạo một FastAPI app đơn giản và build Dockerfile với:

1. **Stage `builder`**: dùng `uv sync` để cài packages vào `.venv`
2. **Stage `runtime`**: copy `.venv` từ builder, chạy với non-root user
3. **Verify**: container chạy với user `appuser` (UID 1000), không phải root
4. **Optimize**: sử dụng `.dockerignore` để giảm build context

### App cần build

```python
# src/myapp/__init__.py (để trống)

# src/myapp/main.py
from fastapi import FastAPI

app = FastAPI(title="Production Ready API")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "Hello from container!"}
```

```toml
# pyproject.toml
[project]
name = "myapp"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "gunicorn>=23.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Yêu cầu Dockerfile

```dockerfile
# Dockerfile
# TODO: Viết multi-stage Dockerfile với:
# Stage 1 (builder):
#   - Base: python:3.12-slim
#   - Cài uv
#   - Copy pyproject.toml và uv.lock
#   - Chạy uv sync --frozen --no-dev --no-cache

# Stage 2 (runtime):
#   - Base: python:3.12-slim
#   - Tạo user appuser với UID/GID 1000
#   - Copy .venv từ builder
#   - Copy source code với --chown=appuser:appuser
#   - Set ENV: PATH, PYTHONPATH, PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE
#   - USER appuser
#   - EXPOSE 8000
#   - HEALTHCHECK mỗi 30s
#   - CMD gunicorn với UvicornWorker
```

### .dockerignore cần tạo

```
# .dockerignore
.git
.gitignore
.env
.env.*
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
tests/
*.md
.venv/
```

### Lệnh build và verify

```bash
# 1. Tạo uv.lock (cần uv installed)
uv lock

# 2. Build image
docker build -t myapp:latest .

# 3. Kiểm tra image size
docker images myapp

# 4. Chạy container
docker run -d -p 8000:8000 --name myapp-test myapp:latest

# 5. Verify non-root user
docker exec myapp-test whoami
# Expected output: appuser

docker exec myapp-test id
# Expected: uid=1000(appuser) gid=1000(appuser)

# 6. Test health endpoint
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# 7. Kiểm tra HEALTHCHECK status
docker inspect myapp-test --format='{{.State.Health.Status}}'
# Expected: healthy (sau khoảng 30-40 giây)

# 8. So sánh single-stage vs multi-stage
# Build single-stage để so sánh:
# docker build --target builder -t myapp:builder .
# docker images myapp

# 9. Cleanup
docker stop myapp-test && docker rm myapp-test
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

RUN uv add uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache


FROM python:3.12-slim AS runtime

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["gunicorn", "myapp.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Nếu bạn thay đổi chỉ `src/myapp/main.py` (không đổi `pyproject.toml`), Docker có cần chạy lại `uv sync` không? Tại sao?
2. `--no-create-home` trong `useradd` có ý nghĩa gì? Khi nào cần `--create-home`?
3. `HEALTHCHECK` trong Dockerfile vs `healthcheck` trong docker-compose — cái nào được ưu tiên? Chúng có thể cùng tồn tại không?

---

## Bài 2 (Trung bình): pydantic-settings với Validation

### Mục tiêu

Implement `Settings` class với pydantic-settings, `.env.example`, custom validators, và test các trường hợp thiếu config.

### Yêu cầu

1. **`Settings` class** với các fields:
   - `APP_NAME: str`
   - `ENVIRONMENT: Literal["development", "staging", "production"]`
   - `DATABASE_URL: PostgresDsn` — required
   - `SECRET_KEY: str = Field(min_length=32)` — required
   - `ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, ge=1, le=1440)`
   - `ALLOWED_ORIGINS: list[str]` — parse từ comma-separated string

2. **Custom validator:**
   - Kiểm tra `SECRET_KEY` không bắt đầu bằng `"dev-"` khi `ENVIRONMENT == "production"`

3. **`.env.example`** file với tất cả variables và comments

4. **Test các scenarios:**

```python
# test_config.py
import pytest
from pydantic import ValidationError
import os

def test_missing_required_fields():
    """ValidationError khi thiếu DATABASE_URL và SECRET_KEY."""
    pass

def test_wrong_type():
    """ValidationError khi ACCESS_TOKEN_EXPIRE_MINUTES không phải int."""
    pass

def test_invalid_database_url():
    """ValidationError khi DATABASE_URL không đúng format PostgresDsn."""
    pass

def test_production_with_dev_secret():
    """ValidationError khi ENVIRONMENT=production mà SECRET_KEY bắt đầu bằng 'dev-'."""
    pass

def test_cors_origins_from_comma_string():
    """ALLOWED_ORIGINS từ 'http://a.com,http://b.com' → ['http://a.com', 'http://b.com']."""
    pass

def test_valid_settings():
    """Settings hợp lệ không raise exception."""
    pass
```

### Setup

```bash
uv add "pydantic-settings>=2.0" pytest
```

### Khung code

```python
# config.py
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "My API"

    # TODO: Thêm ENVIRONMENT với Literal["development", "staging", "production"]

    # TODO: Thêm DATABASE_URL với type PostgresDsn (required, không có default)

    # TODO: Thêm SECRET_KEY với Field(min_length=32)

    # TODO: Thêm ACCESS_TOKEN_EXPIRE_MINUTES với Field và ge/le constraints

    # TODO: Thêm ALLOWED_ORIGINS: list[str] với default ["http://localhost:3000"]

    # TODO: Thêm field_validator cho ALLOWED_ORIGINS để parse comma-separated string

    # TODO: Thêm model_validator để kiểm tra SECRET_KEY trong production


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Cách test với mock env vars

```python
# test_config.py
import pytest
from pydantic import ValidationError
from unittest.mock import patch
import os


def make_settings(**overrides):
    """Helper tạo Settings với env vars cụ thể."""
    default_env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        "SECRET_KEY": "a-very-secure-secret-key-that-is-at-least-32-characters-long",
        "ENVIRONMENT": "development",
    }
    env = {**default_env, **overrides}

    # Dùng patch để override env vars mà không cần .env file
    with patch.dict(os.environ, env, clear=False):
        # Tạo Settings instance mới (không dùng cached get_settings())
        from config import Settings
        return Settings()


def test_missing_database_url():
    """DATABASE_URL là required field."""
    with pytest.raises(ValidationError) as exc_info:
        with patch.dict(os.environ, {}, clear=True):
            from config import Settings
            Settings()

    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "DATABASE_URL" in field_names


def test_valid_settings():
    settings = make_settings()
    assert settings.APP_NAME == "My API"
    assert settings.ENVIRONMENT == "development"


# TODO: Implement test_wrong_type, test_production_with_dev_secret, v.v.
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
# config.py
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "My API"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DATABASE_URL: PostgresDsn
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.ENVIRONMENT == "production" and self.SECRET_KEY.startswith("dev-"):
            raise ValueError(
                "SECRET_KEY cannot start with 'dev-' in production environment"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# test_config.py
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError


def make_settings(**overrides):
    default_env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
        "SECRET_KEY": "a-very-secure-secret-key-that-is-at-least-32-characters-long",
        "ENVIRONMENT": "development",
    }
    # Xóa cache để test không bị ảnh hưởng bởi lần trước
    from config import get_settings
    get_settings.cache_clear()

    env = {**default_env, **overrides}
    with patch.dict(os.environ, env, clear=True):
        from config import Settings
        return Settings()


def test_missing_required_fields():
    with patch.dict(os.environ, {}, clear=True):
        from config import Settings, get_settings
        get_settings.cache_clear()
        with pytest.raises(ValidationError) as exc_info:
            Settings()
    errors = {e["loc"][0] for e in exc_info.value.errors()}
    assert "DATABASE_URL" in errors
    assert "SECRET_KEY" in errors


def test_wrong_type():
    with pytest.raises(ValidationError):
        make_settings(ACCESS_TOKEN_EXPIRE_MINUTES="not-a-number")


def test_invalid_database_url():
    with pytest.raises(ValidationError):
        make_settings(DATABASE_URL="not-a-valid-url")


def test_production_with_dev_secret():
    with pytest.raises(ValidationError, match="cannot start with 'dev-'"):
        make_settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev-secret-that-is-definitely-long-enough-to-pass-length",
        )


def test_cors_origins_from_comma_string():
    settings = make_settings(ALLOWED_ORIGINS="http://a.com,http://b.com")
    assert settings.ALLOWED_ORIGINS == ["http://a.com", "http://b.com"]


def test_valid_settings():
    settings = make_settings()
    assert settings.ENVIRONMENT == "development"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Tại sao dùng `@lru_cache` cho `get_settings()`? Nếu không có `lru_cache`, điều gì xảy ra?
2. `extra="ignore"` vs `extra="forbid"` — khi nào nên dùng mỗi loại?
3. Trong tests, tại sao cần `get_settings.cache_clear()` trước mỗi test?

---

## Bài 3 (Nâng cao): Full docker-compose Stack

### Mục tiêu

Setup đầy đủ: FastAPI app + PostgreSQL + Redis + Alembic migrations chạy khi startup, tất cả với healthchecks.

### Deployment policy cần thể hiện

- Migration chạy bằng service `migrate` riêng, app chỉ start nếu migration exit code 0.
- `GET /health` là liveness: không query dependency nặng.
- `GET /health/ready` là readiness: kiểm tra DB/Redis và trả 503 nếu dependency bắt buộc chưa sẵn sàng.
- App shutdown phải đóng DB engine và Redis client trong lifespan cleanup; Gunicorn `--graceful-timeout` phải đủ cho request đang chạy hoàn tất.

### Yêu cầu

1. **docker-compose.yml** với 4 services:
   - `postgres` — PostgreSQL 16 với healthcheck
   - `redis` — Redis 7 với healthcheck
   - `migrate` — Alembic `upgrade head`, chỉ chạy một lần, `depends_on postgres`
   - `app` — FastAPI, `depends_on migrate AND redis (healthy)`

2. **Alembic setup**:
   - `alembic init alembic` và cấu hình `alembic.ini`
   - Migration tạo bảng `users`
   - `app` service chờ `migrate` service hoàn thành

3. **App endpoints**:
   - `GET /health` — liveness
   - `GET /health/ready` — kiểm tra DB + Redis connection
   - `POST /users` — tạo user mới (lưu vào PostgreSQL)
   - `GET /users/{id}` — lấy user (với Redis cache)

4. **Verify toàn bộ flow:**

```bash
# 1. Build và start
docker compose up --build

# 2. Migrations tự chạy
docker compose logs migrate
# Expected: "Running upgrade ... -> ..., Create users table"

# 3. Test health
curl http://localhost:8000/health/ready
# Expected: {"status": "ready", "checks": {"database": {"status": "ok"}, "redis": {"status": "ok"}}}

# 4. Create user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com"}'
# Expected: {"id": 1, "username": "alice", "email": "alice@example.com"}

# 5. Get user (lần 1: cache miss, lần 2: cache hit)
curl http://localhost:8000/users/1
curl http://localhost:8000/users/1

# 6. Kiểm tra healthcheck status của tất cả services
docker compose ps
# All services: healthy
```

### Cấu trúc file

```
exercise3/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .env                    # Không commit, chỉ cho local dev
├── .env.example
├── .dockerignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_create_users.py
└── src/
    └── myapp/
        ├── __init__.py
        ├── main.py         # FastAPI app với lifespan
        ├── config.py       # pydantic-settings
        ├── database.py     # SQLAlchemy engine
        └── routers/
            ├── health.py
            └── users.py
```

### Khung code chính

```python
# src/myapp/config.py
from functools import lru_cache
from pydantic import PostgresDsn, RedisDsn, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn = "redis://redis:6379/0"
    SECRET_KEY: str = Field(min_length=32)
    DB_POOL_SIZE: int = 5

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```yaml
# docker-compose.yml (skeleton)
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      # TODO: pg_isready command

  redis:
    image: redis:7-alpine
    healthcheck:
      # TODO: redis-cli ping command

  migrate:
    build: .
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
      SECRET_KEY: "dev-secret-for-local-must-be-32-chars-here"
    depends_on:
      postgres:
        # TODO: condition: service_healthy

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
      REDIS_URL: "redis://redis:6379/0"
      SECRET_KEY: "dev-secret-for-local-must-be-32-chars-here"
    depends_on:
      migrate:
        # TODO: condition: service_completed_successfully
      redis:
        # TODO: condition: service_healthy
    healthcheck:
      # TODO: health check

volumes:
  postgres_data:
```

```python
# alembic/versions/001_create_users.py
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # TODO: Thêm index cho username


def downgrade() -> None:
    op.drop_table("users")
```

### Gợi ý xử lý Alembic với async SQLAlchemy

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from myapp.config import get_settings
from myapp.database import Base

settings = get_settings()
config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = str(settings.DATABASE_URL)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Alembic cần sync engine, nhưng ta có async URL
    # Chuyển asyncpg → psycopg2 cho Alembic
    url = str(settings.DATABASE_URL).replace("+asyncpg", "")

    from sqlalchemy import create_engine
    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem docker-compose.yml đầy đủ</summary>

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  migrate:
    build: .
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
      SECRET_KEY: "dev-secret-for-local-must-be-32-chars-here-padded"
    depends_on:
      postgres:
        condition: service_healthy
    restart: "no"

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
      REDIS_URL: "redis://redis:6379/0"
      SECRET_KEY: "dev-secret-for-local-must-be-32-chars-here-padded"
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. `condition: service_completed_successfully` vs `condition: service_healthy` — sự khác biệt là gì? Khi nào dùng loại nào?
2. Nếu migration fail (ví dụ: sai SQL), app service có start không? Behavior nào xảy ra?
3. Tại sao Alembic `env.py` cần chuyển `+asyncpg` → sync driver? Có cách nào dùng async Alembic không?
