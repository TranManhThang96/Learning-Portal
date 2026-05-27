# Ngày 16: Tài Liệu Tham Khảo

## pydantic-settings

### Tài liệu chính thức
- **pydantic-settings docs:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **BaseSettings API:** https://docs.pydantic.dev/latest/api/pydantic_settings/
- **Pydantic Field types:** https://docs.pydantic.dev/latest/api/types/

**Cài đặt:**
```bash
uv add "pydantic-settings>=2.0"
```

**Các field types hữu ích:**
```python
from pydantic import (
    PostgresDsn,    # postgresql+asyncpg://user:pass@host:port/db
    RedisDsn,       # redis://host:port/db
    AnyHttpUrl,     # http:// hoặc https://
    SecretStr,      # Masked trong logs và repr
    Field,          # Constraints và metadata
)
from pydantic import field_validator, model_validator

# SecretStr — che giấu secrets trong logs
from pydantic import SecretStr

class Settings(BaseSettings):
    DATABASE_PASSWORD: SecretStr  # Sẽ hiển thị "**********" trong repr

    def get_db_password(self) -> str:
        return self.DATABASE_PASSWORD.get_secret_value()
```

**Nested settings:**
```python
class DatabaseSettings(BaseModel):
    url: PostgresDsn
    pool_size: int = 10
    max_overflow: int = 20

class Settings(BaseSettings):
    database: DatabaseSettings
    # Đọc từ: DATABASE__URL, DATABASE__POOL_SIZE (double underscore = nested)
```

**Multiple env files:**
```python
model_config = SettingsConfigDict(
    env_file=(".env.base", ".env.local"),  # Đọc theo thứ tự, sau override trước
)
```

---

## Gunicorn

### Tài liệu chính thức
- **Gunicorn docs:** https://docs.gunicorn.org/
- **Configuration file:** https://docs.gunicorn.org/en/stable/configure.html
- **Worker types:** https://docs.gunicorn.org/en/stable/design.html#worker-types
- **Signals (graceful reload):** https://docs.gunicorn.org/en/stable/signals.html

**Worker count formula:**
```
# I/O-bound (FastAPI với database/redis)
workers = (2 * CPU_cores) + 1

# CPU-bound (heavy computation)
workers = CPU_cores

# Trong container với resource limits:
import multiprocessing, os
cpu_quota = float(os.getenv("CPU_LIMIT", multiprocessing.cpu_count()))
workers = max(2, int(cpu_quota * 2) + 1)
```

**Graceful reload (không downtime):**
```bash
# Reload workers một cách graceful (khi deploy code mới)
kill -HUP $(cat gunicorn.pid)

# Trong Docker/Kubernetes: scale down old pods, scale up new pods
# Không cần manual reload
```

**Gunicorn vs Uvicorn standalone:**
```
Uvicorn standalone:   uvicorn main:app --workers 4
  - Đơn giản hơn
  - Ít tính năng hơn (không có graceful reload, ít options)
  - Tốt cho development

Gunicorn + UvicornWorker:  gunicorn main:app --worker-class uvicorn.workers.UvicornWorker
  - Production-proven process manager
  - Graceful reload, worker recycling, hooks
  - Recommended cho production
```

---

## Docker Python Best Practices

### Tài liệu chính thức
- **Docker Python guide:** https://docs.docker.com/language/python/
- **Docker best practices:** https://docs.docker.com/build/building/best-practices/
- **Multi-stage builds:** https://docs.docker.com/build/building/multi-stage/

### uv — Fast Python Package Manager
- **uv docs:** https://docs.astral.sh/uv/
- **uv in Docker:** https://docs.astral.sh/uv/guides/integration/docker/
- **GitHub:** https://github.com/astral-sh/uv

**Tại sao uv thay vì pip:**
```
uv add -r requirements.txt:  ~30-60 giây
uv sync:                          ~2-5 giây (10-20x nhanh hơn)
```

**uv commands:**
```bash
# Tạo project mới
uv init myproject

# Add dependency
uv add fastapi
uv add "uvicorn[standard]"
uv add --dev pytest mypy black  # Dev dependencies

# Install từ lock file (reproducible)
uv sync --frozen

# Install chỉ production dependencies
uv sync --frozen --no-dev

# Run command trong venv
uv run python -m pytest
uv run uvicorn myapp.main:app --reload

# Generate lock file
uv lock

# Show dependency tree
uv tree
```

### .dockerignore quan trọng

```
# .dockerignore
.git
.gitignore
.env
.env.*
!.env.example    # Exclude .env nhưng include .env.example

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
.venv
venv/
*.egg-info/
dist/
build/

# Testing
.pytest_cache
.coverage
coverage.xml
htmlcov/
.tox/

# Type checking
.mypy_cache
.ruff_cache

# IDE
.idea
.vscode
*.swp

# Docs
docs/
*.md
!README.md    # Keep README nếu cần

# CI
.github/
.gitlab-ci.yml
```

### Image size optimization

```dockerfile
# Dùng slim variant (130MB thay vì 1GB)
FROM python:3.12-slim

# Không dùng alpine (musl libc incompatible với một số packages)
# FROM python:3.12-alpine  # Tránh dùng

# Xóa apt cache sau khi install
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Không install pip-cache
RUN uv add --no-cache-dir package-name
```

---

## OpenTelemetry

### Tài liệu chính thức
- **OpenTelemetry Python:** https://opentelemetry.io/docs/languages/python/
- **Getting started:** https://opentelemetry.io/docs/languages/python/getting-started/
- **FastAPI instrumentation:** https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- **SQLAlchemy instrumentation:** https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html

**Cài đặt:**
```bash
uv add \
    opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy \
    opentelemetry-instrumentation-redis \
    opentelemetry-exporter-otlp-proto-grpc
```

**Backends phổ biến:**
```
Jaeger:           https://www.jaegertracing.io/ (open-source, self-hosted)
Grafana Tempo:    https://grafana.com/oss/tempo/ (open-source, self-hosted)
Zipkin:           https://zipkin.io/ (open-source)
Honeycomb:        https://www.honeycomb.io/ (SaaS)
Datadog APM:      https://www.datadoghq.com/ (SaaS)
```

**Concepts:**
```
Trace:   Một request từ đầu đến cuối, có thể qua nhiều services
Span:    Một đơn vị công việc trong trace (ví dụ: DB query, HTTP call, cache lookup)
Context Propagation: Truyền trace context qua HTTP headers (W3C TraceContext)
Exporter: Component gửi traces đến backend (Jaeger, Tempo, v.v.)
```

---

## structlog

### Tài liệu chính thức
- **structlog docs:** https://www.structlog.org/en/stable/
- **Getting started:** https://www.structlog.org/en/stable/getting-started.html
- **contextvars:** https://www.structlog.org/en/stable/contextvars.html

**Cài đặt:**
```bash
uv add structlog
```

**Đọc JSON logs với jq:**
```bash
# Production logs (JSON format)
docker compose logs app | jq .

# Filter logs theo level
docker compose logs app | jq 'select(.level == "error")'

# Filter logs theo event
docker compose logs app | jq 'select(.event == "request_completed")'

# Filter slow requests
docker compose logs app | jq 'select(.duration_ms > 100)'

# Count events
docker compose logs app | jq -s '[.[].event] | group_by(.) | map({event: .[0], count: length}) | sort_by(-.count)'
```

**structlog với stdlib logging integration:**
```python
import logging
import structlog

# Cấu hình để structlog catch tất cả stdlib logging calls
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Sau đó tất cả logging.getLogger(__name__).info(...) cũng được structlog xử lý
```

---

## Kubernetes Deployment (Bonus)

Khi đã quen với Docker, bước tiếp là Kubernetes:

### Liveness và Readiness trong Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: myapp
          image: myapp:latest
          ports:
            - containerPort: 8000

          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"

          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: myapp-secrets
                  key: database-url
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: myapp-secrets
                  key: secret-key
```

**Quan trọng về worker count trong Kubernetes:**
```python
# Trong container với CPU limit 0.5 CPU:
# multiprocessing.cpu_count() trả về số CPU của HOST, không phải container
# → Cần đọc từ env var hoặc tính từ CPU quota

import os

def get_worker_count() -> int:
    # Kubernetes set GOMAXPROCS theo CPU limit (cần downwardAPI hoặc library)
    # Cách đơn giản: đọc từ env var được set trong deployment
    workers_from_env = os.getenv("GUNICORN_WORKERS")
    if workers_from_env:
        return int(workers_from_env)

    # Fallback: đọc CPU quota từ cgroups (Linux only)
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
            quota = int(f.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
            period = int(f.read().strip())
        if quota > 0:
            cpus = quota / period
            return max(2, int(cpus * 2) + 1)
    except (FileNotFoundError, ValueError):
        pass

    import multiprocessing
    return multiprocessing.cpu_count() * 2 + 1
```

---

## Công cụ hữu ích

### Load testing
```bash
# wrk
brew install wrk  # macOS
wrk -t4 -c100 -d30s http://localhost:8000/health

# Locust (Python)
uv add locust
# locustfile.py
from locust import HttpUser, task

class MyUser(HttpUser):
    @task
    def get_health(self):
        self.client.get("/health")

    @task(3)
    def get_users(self):
        self.client.get("/users")

# Chạy: locust -f locustfile.py --headless -u 100 -r 10 --host http://localhost:8000
```

### Docker debugging
```bash
# Xem layers của image
docker history myapp:latest

# Inspect image filesystem
docker run --rm -it myapp:latest sh

# Check HEALTHCHECK status
docker inspect myapp-container | jq '.[0].State.Health'

# Resource usage của containers
docker stats

# Dive — analyze image layers
brew install dive  # macOS
dive myapp:latest
```

### Security scanning
```bash
# Trivy — scan Docker image cho CVEs
brew install aquasecurity/trivy/trivy  # macOS
trivy image myapp:latest

# Docker Scout (built-in)
docker scout cves myapp:latest
```

### Alembic
- **Alembic docs:** https://alembic.sqlalchemy.org/en/latest/
- **Auto-generate migrations:** https://alembic.sqlalchemy.org/en/latest/autogenerate.html

```bash
# Tạo migration tự động từ model changes
alembic revision --autogenerate -m "add email column to users"

# Xem migration status
alembic current
alembic history

# Apply all pending migrations
alembic upgrade head

# Rollback một migration
alembic downgrade -1

# Rollback đến specific revision
alembic downgrade abc123
```
