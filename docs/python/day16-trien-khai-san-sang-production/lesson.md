# Ngày 16: Deployment & Production Readiness

## 🎯 Mục tiêu học tập

Sau ngày 16, bạn sẽ có thể:

- Viết pydantic-settings với type validation cho tất cả environment variables
- Build Dockerfile multi-stage tối ưu với non-root user, image nhỏ
- Cấu hình Gunicorn + UvicornWorker đúng cách cho production
- Viết `docker-compose.yml` với PostgreSQL, Redis, và healthchecks
- Implement liveness/readiness health check endpoints
- Setup structured logging với structlog (JSON cho production, console cho development)
- Hiểu basics của OpenTelemetry instrumentation

### Scope trong 2 giờ

**Primary deployment lab:** deploy một FastAPI container production-ready với `pydantic-settings`, multi-stage Dockerfile, Gunicorn/Uvicorn worker, Docker Compose, healthchecks, migration-on-deploy policy, và graceful shutdown.

**Optional / reference sau giờ học:** CI/CD template, Celery, ARQ, Kubernetes, và observability mở rộng. Các phần này hữu ích cho production thật, nhưng không nằm trong acceptance criteria chính của ngày 16.

---

## 🔄 So sánh với NodeJS Deployment

| NodeJS/NestJS | Python/FastAPI | Ghi chú |
|---|---|---|
| `PM2` | `Gunicorn` | Process manager, quản lý nhiều worker processes |
| `node http.createServer` | `Uvicorn` | ASGI server (async, tương tự libuv) |
| `pm2 cluster mode` | `Gunicorn --workers 4` | Multiple processes, không phải threads |
| `dotenv` / `@nestjs/config` | `pydantic-settings` | Type-safe, validation tích hợp sẵn |
| `.env` parsing | `pydantic-settings` tự đọc `.env` | Không cần `dotenv.config()` |
| `process.env.PORT` | `settings.PORT` (typed `int`) | Pydantic tự convert string → int |
| `Winston` / `Pino` | `structlog` | Structured logging, JSON output |
| `@opentelemetry/sdk-node` | `opentelemetry-instrumentation-fastapi` | Tương tự nhau |
| `Dockerfile` multi-stage | Giống hệt | Cùng pattern, khác base image |

**Tư duy chính:** Gunicorn là process manager (như PM2 cluster mode) chạy nhiều Uvicorn worker processes. Uvicorn là ASGI server (như libuv trong Node). Bạn cần cả hai cho production.

```
Internet → Nginx → Gunicorn (port 8000)
                      ├─ UvicornWorker 1 (process)
                      ├─ UvicornWorker 2 (process)
                      ├─ UvicornWorker 3 (process)
                      └─ UvicornWorker 4 (process)
```

---

## 📖 Lý thuyết

### Section 1: pydantic-settings — Type-safe Configuration

#### Cài đặt

```bash
uv add "pydantic-settings>=2.0"
```

#### config.py đầy đủ

```python
# src/myapp/config.py
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings với type validation.

    pydantic-settings tự động:
    1. Đọc từ environment variables (case-insensitive)
    2. Đọc từ .env file (nếu tồn tại)
    3. Validate types và constraints
    4. Raise ValidationError nếu required variable thiếu hoặc sai type
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # DB__POOL_SIZE=20 cho nested settings nếu tách model
        secrets_dir="/run/secrets",  # Docker secrets default mount; không bắt buộc trong local dev
        case_sensitive=False,
        extra="ignore",  # Bỏ qua env vars không khai báo trong model
    )

    # ===================== App =====================
    APP_NAME: str = "My API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # ===================== Server =====================
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)

    # ===================== Database =====================
    # PostgresDsn validates format: postgresql://user:pass@host:port/db
    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0)
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # ===================== Redis =====================
    # RedisDsn validates format: redis://host:port/db
    REDIS_URL: RedisDsn
    REDIS_MAX_CONNECTIONS: int = 20

    # ===================== Security =====================
    SECRET_KEY: str = Field(min_length=32)  # Minimum 32 chars để đủ entropy
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)

    # ===================== CORS =====================
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated string từ env var thành list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v, info):
        """Cảnh báo nếu dùng default/weak secret key trong production."""
        # Trong thực tế, kiểm tra thêm entropy
        if v.startswith("dev-") and info.data.get("ENVIRONMENT") == "production":
            raise ValueError("Cannot use development secret key in production")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def json_logs(self) -> bool:
        """JSON logs trong production, console logs trong development."""
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    """
    Singleton settings instance.

    @lru_cache đảm bảo Settings() chỉ được tạo MỘT LẦN trong toàn bộ application lifecycle.
    Tương tự NestJS ConfigModule với isGlobal: true.

    Trong tests, có thể override:
        from unittest.mock import patch
        with patch("myapp.config.get_settings", return_value=Settings(DATABASE_URL=...)):
            ...
    """
    return Settings()
```

#### .env.example

```bash
# .env.example — commit vào git, không commit .env thật
APP_NAME=My API
DEBUG=false
ENVIRONMENT=development
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/myapp
DB_POOL_SIZE=10

REDIS_URL=redis://localhost:6379/0

# QUAN TRỌNG: Thay bằng random string trong production
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-secret-key-here-must-be-at-least-32-characters-long
ACCESS_TOKEN_EXPIRE_MINUTES=30

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

> Production note: `pydantic-settings` có thể đọc `.env`, environment variables, nested env vars với `__`, và Docker secrets trong `/run/secrets`. Trong Kubernetes/CI, ưu tiên secret manager hoặc mounted secrets; `.env` chỉ nên dùng local/dev.

**Behavior khi thiếu required variable:**

```bash
$ DATABASE_URL="" python -c "from myapp.config import get_settings; get_settings()"
pydantic_core.ValidationError: 1 validation error for Settings
DATABASE_URL
  Field required [type=missing, input_url=None, input_type=NoneType]
```

---

### Section 2: Dockerfile Multi-Stage Build

Multi-stage build giải quyết vấn đề: build tools (gcc, pip) không cần thiết trong production image.

```dockerfile
# Dockerfile

# ============================================================
# STAGE 1: builder — cài đặt dependencies
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# uv: Python package manager nhanh hơn pip 10-100x
# Cài uv trực tiếp từ official installer
RUN uv add uv

# Copy dependency files trước để tận dụng Docker layer caching
# Nếu chỉ thay đổi source code (không đổi pyproject.toml/uv.lock),
# Docker sẽ dùng cached layer cho bước uv sync
COPY pyproject.toml uv.lock ./

# --frozen: không cho phép update lock file (reproducible builds)
# --no-dev: không cài dev dependencies (pytest, black, mypy, v.v.)
# --no-cache: không lưu pip cache trong image
RUN uv sync --frozen --no-dev --no-cache

# ============================================================
# STAGE 2: runtime — image cuối cùng, không có build tools
# ============================================================
FROM python:3.12-slim AS runtime

# Tạo non-root user để tránh container chạy với root privileges
# Best practice bắt buộc trong production
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --no-create-home appuser

WORKDIR /app

# Copy virtual environment từ builder stage
# Không copy uv, pip, hay build tools
COPY --from=builder /app/.venv /app/.venv

# Copy source code với ownership của appuser
COPY --chown=appuser:appuser src/ ./src/

# Environment variables cho Python
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    # PYTHONUNBUFFERED: Không buffer stdout/stderr — logs xuất hiện ngay
    # QUAN TRỌNG: Thiếu cái này, logs có thể bị delay hoặc mất khi container crash
    PYTHONUNBUFFERED=1 \
    # PYTHONDONTWRITEBYTECODE: Không tạo .pyc files — tiết kiệm disk space
    PYTHONDONTWRITEBYTECODE=1 \
    # Tắt pip version check (không cần trong production)
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Switch sang non-root user
USER appuser

EXPOSE 8000

# Health check: container tự test mình còn sống không
# --interval=30s: check mỗi 30 giây
# --timeout=10s: timeout cho mỗi check
# --start-period=10s: chờ 10s trước khi check lần đầu (startup time)
# --retries=3: fail 3 lần liên tiếp mới mark unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Gunicorn chạy nhiều UvicornWorker processes
# --bind: lắng nghe tất cả interfaces (0.0.0.0) thay vì chỉ localhost
# --workers: số worker processes (xem gunicorn.conf.py cho công thức tính)
# --worker-class: dùng UvicornWorker cho ASGI apps
# --timeout: kill worker nếu không respond sau 60s
# --graceful-timeout: thời gian chờ worker tự shutdown khi nhận SIGTERM
# --max-requests: restart worker sau N requests (tránh memory leak)
# --max-requests-jitter: random jitter để tránh tất cả workers restart cùng lúc
CMD ["gunicorn", "myapp.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

**Tại sao multi-stage giảm image size?**

```
Single stage:  python:3.12 (1.0GB) + gcc + build tools + app = ~1.5GB
Multi-stage:   python:3.12-slim (130MB) + only .venv + source = ~200-300MB
```

---

### Section 3: docker-compose.yml

```yaml
# docker-compose.yml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime  # Build đến stage "runtime"
    ports:
      - "8000:8000"
    environment:
      # Override settings cho development
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
      REDIS_URL: "redis://redis:6379/0"
      SECRET_KEY: "dev-secret-key-change-in-production-must-be-32-chars"
      DEBUG: "false"
      ENVIRONMENT: "development"
    env_file:
      - .env  # Load thêm từ .env file nếu tồn tại
    depends_on:
      postgres:
        condition: service_healthy  # Chờ postgres healthy trước khi start app
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      # Chạy SQL scripts khi khởi tạo lần đầu
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"  # Expose để connect từ host khi develop
    healthcheck:
      # pg_isready kiểm tra PostgreSQL đã sẵn sàng nhận connections chưa
      test: ["CMD-SHELL", "pg_isready -U postgres -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save 60 1
      --loglevel warning
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Alembic migrations — chạy một lần khi startup
  # Dùng image từ app service (không build lại)
  migrate:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/myapp"
    depends_on:
      postgres:
        condition: service_healthy
    # restart: no — chỉ chạy một lần

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: myapp_network
```

#### Migration-on-deploy policy

Trong lab chính, migration chạy bằng service/process riêng `migrate`, rồi `app` chỉ start khi migration hoàn thành thành công. Không chạy Alembic trong FastAPI `startup`/`lifespan`, vì nhiều app replicas có thể chạy migration đồng thời và gây race condition.

Production policy nên rõ:
- Migration phải idempotent, review được, và có rollback plan trước khi deploy.
- Nếu migration fail, deploy fail-fast: app version mới không được nhận traffic.
- Với schema change lớn, dùng expand-and-contract migration: thêm cột/bảng mới trước, deploy app tương thích cả schema cũ/mới, backfill, rồi mới xóa field cũ.
- Readiness check chỉ trả `ready` sau khi DB, Redis, và các dependency bắt buộc sẵn sàng. Liveness check chỉ kiểm tra process còn sống, không query dependency nặng.

**Lệnh hay dùng:**

```bash
# Build và start tất cả services
docker compose up --build

# Chạy background
docker compose up -d

# Xem logs
docker compose logs -f app
docker compose logs -f --tail=50 app

# Chạy migration riêng
docker compose run --rm migrate

# Shell vào container
docker compose exec app bash

# Dừng và xóa volumes
docker compose down -v
```

---

### Section 4: gunicorn.conf.py

```python
# gunicorn.conf.py — Cấu hình Gunicorn bằng Python file (thay vì CLI flags)
import multiprocessing
import os

# ===================== Worker processes =====================
# Công thức chuẩn cho I/O-bound apps (FastAPI là I/O-bound):
#   workers = (2 * cpu_count) + 1
#
# Tuy nhiên trong container:
# - Giới hạn theo CPU limit của container, không phải host CPUs
# - Quá nhiều workers = tốn memory, ít workers hơn thường tốt hơn
#
# Thực tế với 1-2 CPUs: 2-4 workers là đủ
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# UvicornWorker: Gunicorn worker class cho ASGI apps
# Mỗi worker là một Uvicorn process với async event loop
worker_class = "uvicorn.workers.UvicornWorker"

# Số threads trong mỗi worker (chỉ cho sync workers, không dùng với UvicornWorker)
# threads = 1  # Default, bỏ comment nếu cần

# ===================== Binding =====================
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ===================== Timeouts =====================
# Timeout: kill worker nếu không respond sau N giây
# Set đủ cao cho long-running requests (uploads, reports)
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))

# Graceful timeout: thời gian worker có để finish requests khi shutdown
# Nên = timeout hoặc ít hơn
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Keepalive: giữ connection sống bao lâu (giây) giữa các requests
# Tăng nếu clients hay reconnect (e.g., 5-10 giây)
keepalive = 5

# ===================== Worker recycling =====================
# Restart worker sau N requests để tránh memory leak
# Giá trị tốt: 1000-10000 tùy app
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))

# Jitter: random thêm 0-100 vào max_requests để các workers không restart cùng lúc
# Tránh tất cả workers restart simultaneously → brief unavailability
max_requests_jitter = 100

# ===================== Logging =====================
# "-" nghĩa là stdout (để Docker logs bắt được)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Log format JSON-compatible cho production
# access_log_format = '{"time": "%(t)s", "method": "%(m)s", "path": "%(U)s", "status": %(s)s, "response_time": %(D)s}'

# ===================== Process naming =====================
proc_name = os.getenv("APP_NAME", "myapp")

# ===================== Security =====================
# Giới hạn request line size (bytes) — tránh header injection
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# ===================== Server Hooks =====================
def on_starting(server):
    """Chạy một lần khi Gunicorn master process khởi động."""
    server.log.info(f"Starting {proc_name} with {workers} workers")


def worker_init(worker):
    """Chạy trong mỗi worker process sau khi fork."""
    pass


def worker_exit(server, worker):
    """Cleanup khi worker process thoát."""
    pass
```

---

### Section 5: Health Checks

#### Liveness vs Readiness

```
Liveness (/health):
  - "App có còn sống không?" (không bị hang/deadlock)
  - Kubernetes restarts pod nếu liveness fail
  - KHÔNG check dependencies (DB, Redis) — nếu DB down, không restart app

Readiness (/health/ready):
  - "App có sẵn sàng nhận traffic không?"
  - Kubernetes không route traffic đến pod nếu readiness fail
  - CHECK dependencies — nếu DB down, stop nhận traffic

Startup (/health/startup):
  - "App đã khởi động xong chưa?" (cho apps khởi động chậm)
  - Kubernetes dùng trước liveness/readiness checks
```

```python
# src/myapp/routers/health.py
import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.cache import cache_service
from myapp.database import engine
from myapp.dependencies import get_db

logger = structlog.get_logger()
router = APIRouter(tags=["Health"])

# Thời điểm app bắt đầu (để tính uptime)
_start_time = time.time()


@router.get("/health")
async def liveness():
    """
    Liveness probe — luôn trả về 200 nếu app còn chạy.
    Kubernetes dùng endpoint này để biết có cần restart pod không.
    """
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe — kiểm tra kết nối DB và Redis.
    Kubernetes dừng route traffic đến pod nếu endpoint này fail.
    """
    checks: dict[str, Any] = {}
    all_ok = True

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))
        checks["database"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # Check Redis
    try:
        redis_ok = await cache_service.ping()
        if redis_ok:
            stats = await cache_service.get_pool_stats()
            checks["redis"] = {"status": "ok", **stats}
        else:
            checks["redis"] = {"status": "error", "detail": "ping failed"}
            all_ok = False
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        checks["redis"] = {"status": "error", "detail": str(e)}
        all_ok = False

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": time.time(),
        },
    )


@router.get("/health/startup")
async def startup_check():
    """
    Startup probe — kiểm tra app đã init xong chưa.
    Dùng cho apps có startup time dài (ví dụ: load ML model).
    """
    # Check nếu app đã init xong
    # if not app_state.initialized:
    #     return JSONResponse(status_code=503, content={"status": "initializing"})
    return {"status": "ready"}
```

#### Graceful shutdown

Trong container orchestrator, shutdown thường bắt đầu bằng `SIGTERM`. App cần ngừng nhận work mới, để request đang chạy hoàn tất trong `graceful_timeout`, đóng DB pool/Redis client, rồi exit. Không đặt cleanup dài hơn `--graceful-timeout`, nếu không worker sẽ bị kill cứng.

```python
# src/myapp/main.py
import signal
import asyncio
from contextlib import asynccontextmanager

_shutdown_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("application_starting")

    # Setup signal handlers cho graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_shutdown(sig):
        logger.info("shutdown_signal_received", signal=sig.name)
        _shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_shutdown, sig)

    logger.info("application_ready")

    yield

    # Shutdown
    logger.info("application_shutting_down")

    # Chờ in-flight requests hoàn thành (Gunicorn graceful-timeout xử lý điều này)
    await engine.dispose()
    await cache_service._client.aclose()

    logger.info("application_stopped")
```

---

### Section 6: Structured Logging với structlog

Structured logging = log dưới dạng key-value pairs thay vì plain text.

```python
# Thay vì:
logging.info(f"User {user_id} logged in from {ip} in {duration}ms")
# Output: "User 42 logged in from 192.168.1.1 in 123ms"

# Dùng:
logger.info("user_logged_in", user_id=42, ip="192.168.1.1", duration_ms=123)
# Output JSON: {"event": "user_logged_in", "user_id": 42, "ip": "192.168.1.1", "duration_ms": 123, "timestamp": "..."}
```

Tại sao tốt hơn?
- Dễ search trong Loki/Datadog/CloudWatch: `user_id=42 AND duration_ms>100`
- Dễ aggregate: tính P95 latency theo endpoint
- Không cần parse regex

```python
# src/myapp/logging_config.py
import logging
import sys

import structlog
from myapp.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Cấu hình structlog.
    - Development: ConsoleRenderer (màu sắc, dễ đọc)
    - Production: JSONRenderer (dễ parse bởi log aggregators)
    """

    # Shared processors — chạy trước renderer
    shared_processors = [
        # Merge contextvars (ví dụ: request_id được bind từ middleware)
        structlog.contextvars.merge_contextvars,
        # Thêm log level vào event dict
        structlog.stdlib.add_log_level,
        # Thêm logger name (module path)
        structlog.stdlib.add_logger_name,
        # Thêm timestamp ISO 8601
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Render exceptions đẹp hơn
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    if settings.json_logs:
        # Production: JSON output để log aggregators parse được
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: Color console output dễ đọc
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )

    # Cấu hình stdlib logging để structlog bắt được
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.LOG_LEVEL.upper()),
    )

    # Tắt noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
```

#### Sử dụng trong code

```python
# Khởi tạo logger
import structlog
logger = structlog.get_logger()

# Log đơn giản
logger.info("server_started", port=8000, environment="production")

# Bind context — tất cả logs sau đó đều có các fields này
bound_logger = logger.bind(user_id=42, request_id="abc-123")
bound_logger.info("user_action", action="login")
bound_logger.warning("rate_limit_warning", requests=95, limit=100)

# contextvars — bind cho toàn bộ async context (request lifecycle)
import structlog.contextvars

structlog.contextvars.bind_contextvars(request_id="abc-123")
# Mọi logger trong cùng async context đều có request_id tự động

# Log exception
try:
    result = 1 / 0
except ZeroDivisionError:
    logger.error("calculation_failed", exc_info=True)  # Include traceback
```

#### Tích hợp vào lifespan

```python
# src/myapp/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from myapp.logging_config import setup_logging

setup_logging()  # Gọi ngay khi module load

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = structlog.get_logger()
    logger.info("application_starting", version=settings.APP_VERSION)

    # ... startup code ...

    yield

    logger.info("application_stopped")
```

---

### Section 7: OpenTelemetry Basics

OpenTelemetry (OTel) là standard để collect traces, metrics, và logs.

```bash
uv add opentelemetry-sdk \
            opentelemetry-instrumentation-fastapi \
            opentelemetry-instrumentation-sqlalchemy \
            opentelemetry-exporter-otlp-proto-grpc  # Gửi đến Jaeger/Tempo
```

```python
# src/myapp/telemetry.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from myapp.config import get_settings

settings = get_settings()


def setup_telemetry(app=None, db_engine=None) -> None:
    """
    Setup OpenTelemetry tracing.

    Traces cho phép bạn follow một request qua toàn bộ hệ thống:
    - Bao lâu mỗi database query?
    - Bao lâu Redis lookup?
    - Endpoint nào chậm?
    """

    # Resource metadata — gắn vào tất cả traces
    resource = Resource.create({
        "service.name": settings.APP_NAME,
        "service.version": settings.APP_VERSION,
        "deployment.environment": settings.ENVIRONMENT,
    })

    # Tracer provider
    provider = TracerProvider(resource=resource)

    # Exporter — gửi traces đến collector (Jaeger, Grafana Tempo, v.v.)
    # OTLP_ENDPOINT thường là "http://jaeger:4317" hoặc "http://otel-collector:4317"
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317",  # Đọc từ settings trong production
        insecure=True,
    )

    # BatchSpanProcessor: gửi traces theo batch (không block request)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI — tự động tạo span cho mỗi request
    if app:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/health/ready",  # Không trace health checks
        )

    # Auto-instrument SQLAlchemy — tự động tạo span cho mỗi query
    if db_engine:
        SQLAlchemyInstrumentor().instrument(
            engine=db_engine.sync_engine,
            enable_commenter=True,  # Thêm OTel context vào SQL comments
        )


def get_tracer() -> trace.Tracer:
    """Lấy tracer instance để tạo custom spans."""
    return trace.get_tracer(settings.APP_NAME)
```

#### Custom spans trong code

```python
# src/myapp/users/service.py
from myapp.telemetry import get_tracer

tracer = get_tracer()


class UserService:
    async def get_by_id(self, user_id: int):
        # Tạo custom span để trace logic phức tạp
        with tracer.start_as_current_span(
            "UserService.get_by_id",
            attributes={"user.id": user_id},
        ) as span:

            # Cache lookup span
            with tracer.start_as_current_span("cache.get") as cache_span:
                cached = await self.cache.get(f"user:{user_id}")
                cache_span.set_attribute("cache.hit", cached is not None)

            if cached:
                span.set_attribute("cache.hit", True)
                return User(**json.loads(cached))

            # DB query span (SQLAlchemyInstrumentor tạo tự động)
            user = await self.repo.get_by_id(user_id)

            if user:
                span.set_attribute("user.found", True)
                span.set_attribute("user.username", user.username)
            else:
                span.set_attribute("user.found", False)

            return user
```

#### docker-compose với Jaeger (local tracing)

```yaml
# Thêm vào docker-compose.yml
jaeger:
  image: jaegertracing/all-in-one:1.51
  ports:
    - "16686:16686"  # Jaeger UI
    - "4317:4317"    # OTLP gRPC receiver
  environment:
    COLLECTOR_OTLP_ENABLED: "true"
```

Sau đó mở http://localhost:16686 để xem traces.

---

## ⚠️ Common Mistakes

| Lỗi | Vấn đề | Cách sửa |
|---|---|---|
| Chạy container với root user | Security vulnerability, có thể ghi đè system files | Thêm `useradd` và `USER appuser` trong Dockerfile |
| Worker count quá cao trong container | Container có 1 CPU nhưng 8 workers = context switch overhead | Dùng `cpu_count() * 2 + 1` nhưng giới hạn theo container CPU limit |
| Không có `--max-requests` | Memory leak trong worker tích lũy theo thời gian | Set `max_requests=1000` + `max_requests_jitter=100` |
| Thiếu `PYTHONUNBUFFERED=1` | Python buffer stdout → logs bị delay hoặc mất khi container crash | Set `PYTHONUNBUFFERED=1` trong Dockerfile ENV |
| `.pyc` files trong image | Tốn disk space không cần thiết | Set `PYTHONDONTWRITEBYTECODE=1` |
| Dùng `latest` tag cho base image | Không reproducible, có thể break | Pin version: `python:3.12-slim` |
| Copy tất cả files vào image | `.git`, `tests/`, `*.md` vào production image | Dùng `.dockerignore` |
| `COPY . .` trước khi `uv add` | Thay đổi source code invalidate layer cache uv add | COPY `pyproject.toml` trước, `uv add`, rồi mới COPY source |
| Secret trong Dockerfile hoặc env var plain text | Secrets lộ trong `docker history` | Dùng Docker secrets hoặc secret management (Vault, AWS SSM) |

---

## ✅ Best Practices

1. **`.dockerignore`** — exclude `.git`, `tests/`, `*.md`, `__pycache__`, `.env` khỏi build context

```
.git
.gitignore
.env
.env.*
tests/
docs/
*.md
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
```

2. **Health check trong Dockerfile VÀ docker-compose** — Dockerfile healthcheck chạy standalone, docker-compose healthcheck thêm `depends_on` logic

3. **Non-root user** — `useradd` với specific UID/GID (1000) để consistent với host file permissions

4. **Pin dependencies** — `uv sync --frozen` đảm bảo reproducible builds từ `uv.lock`

5. **`lru_cache` cho settings** — `get_settings()` chỉ parse env vars một lần, không phải mỗi request

6. **JSON logs trong production** — plain text logs không searchable trong log aggregators

7. **Graceful shutdown** — Gunicorn `graceful-timeout=30` cho phép in-flight requests hoàn thành

8. **Resource limits trong docker-compose** — `mem_limit`, `cpus` tránh một container eat all resources

---

## ⚖️ Trade-offs

| Quyết định | Ưu điểm | Nhược điểm |
|---|---|---|
| Gunicorn + UvicornWorker | Production-proven, graceful reload, multiple processes | Cần config đúng, thêm complexity |
| Uvicorn standalone | Đơn giản, ít overhead | Không có process management, khó scale |
| Multi-stage Dockerfile | Image nhỏ, không có build tools | Build lâu hơn, cần cache layer |
| pydantic-settings validation | Fail-fast khi thiếu config, type safety | Cần khai báo tất cả env vars |
| Structured logging (JSON) | Searchable, parseable | Khó đọc raw trong terminal (dùng `jq` để đọc) |
| OpenTelemetry | Standard, works với nhiều backends | Overhead nhỏ, cần infrastructure (collector, storage) |
| `max_requests` Gunicorn | Tránh memory leak | Workers restart gây brief latency spike (dùng jitter) |

---

## 🚀 Performance Notes

- **Gunicorn workers:** Với `python:3.12-slim` và 2 CPU cores, `4 workers` thường optimal. Đo bằng `wrk` hoặc `locust` trước khi tăng
- **`--max-requests` và `--max-requests-jitter`:** Không đặt quá thấp (100) — restart thường xuyên gây latency. 1000-5000 là range tốt
- **`pool_pre_ping=True`:** Thêm một SELECT 1 trước mỗi connection use — trade-off nhỏ về latency đổi lấy không bị `connection already closed` error
- **Docker build cache:** `COPY pyproject.toml ./` trước `uv sync` là quy tắc quan trọng nhất — tránh reinstall tất cả packages mỗi lần đổi source code
- **Image size:** Dùng `python:3.12-slim` (130MB) thay vì `python:3.12` (1GB). Không cần `alpine` (dùng musl libc, incompatible với một số packages)
- **`PYTHONOPTIMIZE=1`:** Remove assert statements và docstrings — tiết kiệm nhỏ, không cần thiết cho hầu hết apps

---

## ⚙️ Optional Reference: CI/CD Pipeline cho Python

> **Phần mở rộng, không thuộc primary deployment lab** — đọc sau khi nắm vững core deployment. Thời gian ước tính: 30 phút.

```yaml
# .github/workflows/ci.yml — GitHub Actions workflow cho Python
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]  # Test nhiều versions — dùng tox/nox nếu cần

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --frozen --dev  # --frozen: không update lock file (như npm ci)

      - name: Lint với ruff
        run: uv run ruff check . && uv run ruff format --check .

      - name: Type check với mypy
        run: uv run mypy src/

      - name: Run tests
        run: uv run pytest --cov=src --cov-report=xml -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test_db

      - name: Upload coverage
        uses: codecov/codecov-action@v4

    services:  # Spin up test dependencies
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Docker build & push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha  # GitHub Actions cache
          cache-to: type=gha,mode=max

      - name: Deploy to production
        run: |
          # SSH deploy, k8s rollout, Fly.io deploy, etc.
          echo "Deploy image: ${{ github.sha }}"
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
```

```toml
# pyproject.toml — tox configuration (alternative: nox)
# tox: chạy tests trong isolated environments với nhiều Python versions
# nox: tương tự nhưng dùng Python thay vì ini syntax

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

# Secrets trong CI/CD: NEVER hardcode trong workflow file
# Dùng GitHub Secrets: Settings → Secrets → Actions
# Access: ${{ secrets.MY_SECRET_KEY }}
# Trong Python: os.environ["MY_SECRET_KEY"]

# Pre-commit CI: https://pre-commit.ci — chạy pre-commit hooks tự động trong PRs
# Thêm .pre-commit-config.yaml → pre-commit.ci sẽ auto-fix và commit
```

> **So sánh với Node.js CI**: rất giống nhau — lint → test → build → deploy.
> Điểm khác: Python thêm `mypy` (TypeScript compiler equivalent), thường test nhiều Python versions.

---

## 📝 Tóm tắt

Ngày 16 đã hoàn thành vòng lặp từ development đến production:

- **pydantic-settings** — type-safe config, fail-fast khi thiếu env vars, tương tự `@nestjs/config` nhưng explicit hơn
- **Dockerfile multi-stage** — image nhỏ, non-root user, layer caching optimization
- **Gunicorn + UvicornWorker** — production-proven combination: Gunicorn quản lý processes, Uvicorn xử lý async I/O
- **docker-compose** với healthchecks — `depends_on: condition: service_healthy` đảm bảo startup order đúng
- **Migration-on-deploy** — chạy Alembic bằng process riêng, fail-fast nếu migration lỗi, không chạy migration trong mỗi app replica
- **Health endpoints** liveness vs readiness — critical cho Kubernetes deployment
- **Graceful shutdown** — xử lý `SIGTERM`, đóng DB/cache client, để request đang chạy hoàn tất trong timeout
- **structlog** với JSON output — structured logging cho log aggregators
- **OpenTelemetry** basics — distributed tracing để debug performance issues trong microservices

## ⚡ Optional Reference: Async Task Queues — Background Jobs

> **Phần mở rộng, không thuộc primary deployment lab** — đọc sau khi nắm vững deployment core. Thời gian ước tính: 30 phút.
> Tương đương BullMQ/Bull trong NodeJS.

```python
# --- ARQ — lightweight async task queue (khuyến nghị cho new projects) ---
# uv add arq redis
# ARQ = Async Redis Queue — native asyncio, đơn giản hơn Celery

import asyncio
from arq import create_pool, cron
from arq.connections import RedisSettings

# 1. Define tasks (functions)
async def send_email(ctx: dict, to: str, subject: str, body: str) -> dict:
    """Background task: gửi email."""
    # Thực tế: gọi SendGrid/SES API
    await asyncio.sleep(0.1)  # simulate I/O
    print(f"Email sent to {to}: {subject}")
    return {"status": "sent", "to": to}

async def process_ai_report(ctx: dict, user_id: int, data: dict) -> dict:
    """Background task: generate AI report (CPU/I/O intensive)."""
    await asyncio.sleep(2.0)  # simulate LLM call
    return {"report": f"AI report for user {user_id}", "generated": True}

# 2. Worker config
class WorkerSettings:
    functions = [send_email, process_ai_report]
    redis_settings = RedisSettings(host="localhost", port=6379)
    max_jobs = 10          # Concurrent jobs
    job_timeout = 300      # 5 phút timeout per job
    keep_result = 3600     # Giữ result 1 giờ

    # Cron jobs
    cron_jobs = [
        cron(process_ai_report, hour={9, 18}, user_id=0, data={})  # 9am, 6pm
    ]

# 3. Enqueue từ FastAPI
from fastapi import FastAPI

app = FastAPI()
redis_pool = None

@app.on_event("startup")
async def startup():
    global redis_pool
    redis_pool = await create_pool(RedisSettings())

@app.post("/users/{user_id}/report")
async def request_report(user_id: int):
    job = await redis_pool.enqueue_job(
        "process_ai_report",
        user_id=user_id,
        data={"format": "pdf"},
    )
    return {"job_id": job.job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    from arq.jobs import Job
    job = Job(job_id, redis_pool)
    status = await job.status()
    result = await job.result() if status.value == "complete" else None
    return {"job_id": job_id, "status": str(status), "result": result}

# 4. Run worker (separate process)
# arq myapp.WorkerSettings
```

```python
# --- Celery — mature, feature-rich (nếu team quen dùng) ---
# uv add celery[redis]
# Celery = non-async, nhưng mature hơn, ecosystem rộng hơn ARQ

from celery import Celery
from celery.schedules import crontab

app = Celery(
    "myapp",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)
app.config_from_object({
    "task_serializer": "json",
    "result_expires": 3600,
    "worker_concurrency": 4,
})

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to: str, subject: str):
    try:
        # Gửi email
        return {"status": "sent"}
    except Exception as exc:
        raise self.retry(exc=exc)  # Auto retry với backoff

# Enqueue từ FastAPI
from fastapi import FastAPI
web_app = FastAPI()

@web_app.post("/send-email")
async def send_email_endpoint(to: str, subject: str):
    task = send_email_task.delay(to, subject)  # Non-blocking!
    return {"task_id": task.id}

# Run worker: celery -A myapp worker --loglevel=info
```

> **So sánh với NodeJS:**
> - BullMQ → ARQ (async, Redis, simple) hoặc Celery (mature, feature-rich)
> - ARQ cho new Python projects (asyncio native)
> - Celery nếu cần: periodic tasks, routing, canvas, multi-broker support
>
> **Khi nào cần task queue:**
> - Gửi email/SMS (vài giây delay OK)
> - Generate AI reports (30s+ processing)
> - Xử lý file uploads (convert, resize)
> - Scheduled jobs (cleanup, reports, billing)

**Bạn đã hoàn thành 16 ngày học Python từ góc nhìn NodeJS developer. Tiếp theo là AI/ML Engineering (Ngày 17-35).**
