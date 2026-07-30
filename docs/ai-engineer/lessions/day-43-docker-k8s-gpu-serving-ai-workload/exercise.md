# Exercise: Dockerize Và Deploy RAG/LLM Service

## Mục tiêu

Bạn sẽ lấy RAG app từ Day 40 hoặc một FastAPI LLM service tương đương, rồi biến nó thành deployment package có thể review:

- Docker image cho API.
- `.dockerignore`.
- `.env.example`.
- Docker Compose chạy API + vector DB.
- Health/readiness endpoint.
- Smoke test.
- Kubernetes manifests optional.
- GPU model server manifest optional.
- Deployment note trả lời production readiness.

Thời lượng đề xuất:

- Bản tối thiểu: 90 phút.
- Bản tốt cho portfolio: 0.5-1 ngày.
- Bản gần production hơn: 1-2 ngày, thêm CI, scanning, monitoring và backup.

## 0. Acceptance criteria

Hoàn thành bài tập khi bạn có:

- [ ] `docker compose up --build` chạy được CPU path.
- [ ] `GET /health` trả `200`.
- [ ] `GET /ready` trả `200` sau khi vector DB sẵn sàng.
- [ ] `.env.example` đủ để người khác tạo `.env`.
- [ ] Docker image không chứa `.env`, raw data lớn hoặc model cache lớn.
- [ ] Compose có volume cho Qdrant/vector DB.
- [ ] Có smoke test query một câu hỏi mẫu.
- [ ] Có K8s manifests: `Deployment`, `Service`, `ConfigMap`, `Secret`.
- [ ] Có GPU manifest optional dùng `nodeSelector`, tolerations và `nvidia.com/gpu`.
- [ ] Có trade-off và production readiness answer trong README/deployment note.

## 1. Chuẩn bị app target

Nếu dùng Day 40, chọn backend FastAPI có endpoint query. Nếu chưa có app, tạo skeleton:

```text
backend/
  app/
    main.py
    health.py
    settings.py
  requirements.in
  requirements.lock
```

API tối thiểu:

```text
GET /health
GET /ready
POST /query
```

`/query` có thể gọi RAG pipeline thật hoặc mock response nếu bạn chỉ đang tập trung vào deployment. Nếu mock, README phải ghi rõ phần nào là mock.

## 2. Viết settings bằng environment variables

Tạo config contract:

```text
APP_ENV
LOG_LEVEL
LLM_MODE
LLM_PROVIDER
LLM_MODEL
OPENAI_API_KEY
MODEL_SERVER_URL
EMBEDDING_MODEL
QDRANT_URL
QDRANT_COLLECTION
INDEX_VERSION
PROMPT_VERSION
REQUEST_TIMEOUT_SECONDS
MAX_CONCURRENT_REQUESTS
```

Yêu cầu:

- Không hard-code API key.
- Không hard-code URL `localhost` trong code backend; dùng `QDRANT_URL`.
- Validate config khi app startup.
- Log config non-secret để debug.

## 3. Thêm health và readiness

`/health` kiểm tra process:

```python
@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

`/ready` kiểm tra dependency nhẹ:

```python
@router.get("/ready")
async def ready() -> JSONResponse:
    checks = {
        "qdrant": await check_qdrant(),
        "index_version": await check_index_version(),
        "llm_provider": await check_llm_provider(),
    }
    ok = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "checks": checks},
        status_code=200 if ok else 503,
    )
```

Không gọi full generation trong readiness probe. Probe chạy liên tục; gọi LLM thật có thể tốn tiền và làm service bị rate limit.

## 4. Tạo `.dockerignore`

```dockerignore
.git
.venv
__pycache__
.pytest_cache
.mypy_cache
.ruff_cache
.env
.env.*
!.env.example
data/raw
data/uploads
data/vector_store
models
model_cache
reports
*.sqlite
*.db
*.parquet
*.pt
*.safetensors
```

Kiểm tra lại:

```bash
docker build --no-cache -t rag-api:test ./backend
```

Nếu build context quá lớn, `.dockerignore` chưa đủ tốt.

## 5. Viết Dockerfile API

Tạo `backend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

RUN groupadd --system app && useradd --system --gid app --home-dir ${APP_HOME} app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.lock

COPY app ./app
RUN chown -R app:app ${APP_HOME}
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

Build:

```bash
docker build -t rag-api:local ./backend
```

Run thử:

```bash
docker run --rm --env-file .env -p 8000:8000 rag-api:local
curl -fsS http://localhost:8000/health
```

## 6. Tạo `.env.example`

```dotenv
APP_ENV=local
APP_NAME=rag-serving
LOG_LEVEL=INFO
PORT=8000
WORKERS=1
REQUEST_TIMEOUT_SECONDS=60
MAX_UPLOAD_MB=25
MAX_CONCURRENT_REQUESTS=16

LLM_MODE=managed
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=replace-me

MODEL_SERVER_URL=http://model-server:8001/v1
MODEL_ID=meta-llama/Llama-3.1-8B-Instruct
MODEL_CACHE_DIR=/models/huggingface

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

VECTOR_DB=qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=policy_chunks

INDEX_VERSION=rag-v1
PROMPT_VERSION=answer-v1
CHUNKING_VERSION=chunk-v1

OTEL_EXPORTER_OTLP_ENDPOINT=
TRACE_SAMPLE_RATE=1.0
```

Tạo `.env` local:

```bash
cp .env.example .env
```

Không commit `.env`.

## 7. Viết Docker Compose

Tạo `docker-compose.yml`:

```yaml
name: rag-serving

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: rag-serving-api:${APP_IMAGE_TAG:-local}
    env_file:
      - .env
    environment:
      QDRANT_URL: http://qdrant:6333
    ports:
      - "8000:8000"
    depends_on:
      qdrant:
        condition: service_started
    volumes:
      - ./data/sample_docs:/app/data/sample_docs:ro
      - ./reports:/app/reports
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:${QDRANT_TAG:-v1.14.1}
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  qdrant_data:
```

Lưu ý: Qdrant có endpoint `/readyz`, nhưng Compose healthcheck chạy bên trong container. Nếu image không có `curl/wget`, đừng thêm healthcheck giòn; thay vào đó `/ready` của API phải retry Qdrant và trả `503` cho đến khi dependency sẵn sàng.

Chạy:

```bash
docker compose up --build
```

Kiểm tra:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
```

## 8. Thêm optional GPU profile

Nếu bạn có local model server, thêm service:

```yaml
  model-server:
    profiles: ["gpu"]
    build:
      context: ./model-server
      dockerfile: Dockerfile.gpu
    image: rag-model-server:${MODEL_IMAGE_TAG:-local}
    env_file:
      - .env
    ports:
      - "8001:8001"
    volumes:
      - model_cache:/models/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: ["gpu"]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8001/health"]
      interval: 30s
      timeout: 5s
      retries: 10
      start_period: 120s
    restart: unless-stopped
```

Thêm volume:

```yaml
volumes:
  qdrant_data:
  model_cache:
```

Chạy:

```bash
docker compose --profile gpu up --build
```

Trước khi chạy GPU path, kiểm tra:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 9. Viết smoke test

Tạo `scripts/smoke-test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -fsS "${BASE_URL}/health"
echo
curl -fsS "${BASE_URL}/ready"
echo

curl -fsS -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?",
    "tenant_id": "demo",
    "user_roles": ["employee"]
  }'
echo
```

Chạy:

```bash
chmod +x scripts/smoke-test.sh
scripts/smoke-test.sh
```

## 10. Viết Kubernetes manifests

Tạo các file trong `k8s/`.

`configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rag-api-config
data:
  APP_ENV: "production"
  LOG_LEVEL: "INFO"
  LLM_MODE: "managed"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4.1-mini"
  EMBEDDING_MODEL: "text-embedding-3-small"
  QDRANT_URL: "http://qdrant:6333"
  QDRANT_COLLECTION: "policy_chunks"
  INDEX_VERSION: "rag-v1"
  PROMPT_VERSION: "answer-v1"
```

`secret.example.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-api-secret
type: Opaque
stringData:
  OPENAI_API_KEY: "replace-in-secret-manager"
```

`api-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
  labels:
    app: rag-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: rag-api
  template:
    metadata:
      labels:
        app: rag-api
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: api
          image: ghcr.io/your-org/rag-api:replace-with-tag
          ports:
            - name: http
              containerPort: 8000
          envFrom:
            - configMapRef:
                name: rag-api-config
            - secretRef:
                name: rag-api-secret
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
          startupProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 12
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 30
```

`api-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rag-api
spec:
  type: ClusterIP
  selector:
    app: rag-api
  ports:
    - name: http
      port: 8000
      targetPort: http
```

Validate dry-run nếu có cluster context:

```bash
kubectl apply --dry-run=client -f k8s/
```

## 11. Optional GPU Kubernetes manifest

Chuẩn bị node:

```bash
kubectl label node gpu-node-1 accelerator=nvidia-l4
kubectl label node gpu-node-1 workload=ai-inference
kubectl taint node gpu-node-1 nvidia.com/gpu=true:NoSchedule
```

`model-server-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-server
  labels:
    app: model-server
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: model-server
  template:
    metadata:
      labels:
        app: model-server
    spec:
      terminationGracePeriodSeconds: 120
      nodeSelector:
        accelerator: nvidia-l4
        workload: ai-inference
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: model-server
          image: ghcr.io/your-org/rag-model-server:replace-with-tag
          ports:
            - name: http
              containerPort: 8001
          env:
            - name: MODEL_ID
              value: "meta-llama/Llama-3.1-8B-Instruct"
          resources:
            requests:
              cpu: "2"
              memory: "12Gi"
            limits:
              cpu: "8"
              memory: "24Gi"
              nvidia.com/gpu: 1
          startupProbe:
            httpGet:
              path: /ready
              port: http
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            periodSeconds: 15
            failureThreshold: 20
          livenessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 30
```

`Recreate` là lựa chọn rõ ràng cho lab chỉ có một GPU: rollout không cố schedule hai model pods cùng lúc, đổi lại có downtime. Nếu cluster có GPU dự phòng và yêu cầu zero-downtime, đổi sang `RollingUpdate`, reserve capacity và chứng minh model mới warm up trước khi nhận traffic.

Kiểm tra GPU resource:

```bash
kubectl describe node gpu-node-1 | grep -A5 "nvidia.com/gpu"
MODEL_SERVER_POD="$(
  kubectl get pods -l app=model-server \
    -o jsonpath='{.items[0].metadata.name}'
)"
kubectl describe pod "${MODEL_SERVER_POD}"
```

## 12. Benchmark

Chạy ít nhất 10 query:

```bash
for i in $(seq 1 10); do
  time curl -fsS -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"question":"Chính sách remote work áp dụng thế nào?","tenant_id":"demo","user_roles":["employee"]}' \
    >/tmp/rag-response.json
done
```

Ghi vào `reports/deployment-benchmark.md`:

| Metric | Kết quả |
|---|---|
| p50 latency | |
| p95 latency | |
| API CPU/RAM | |
| Qdrant RAM/disk | |
| GPU memory | optional |
| Error rate | |
| Token cost/query | nếu dùng managed LLM |

## 13. Trade-off phải ghi trong README

Trả lời các câu sau:

1. Vì sao dùng managed LLM hay local model?
2. Vì sao Compose đủ cho local nhưng chưa đủ cho production?
3. Nếu deploy Kubernetes, API và model server scale khác nhau thế nào?
4. Image có nên chứa model không, hay mount model cache?
5. Vector DB tự vận hành hay dùng managed service?
6. GPU node có cần taint không, vì sao?
7. HPA theo CPU có đủ cho GPU inference không?

Gợi ý câu trả lời ngắn:

```text
Với capstone, managed LLM là lựa chọn mặc định vì giảm GPU ops và giúp reviewer chạy được nhanh.
Local GPU model chỉ bật khi có yêu cầu privacy/cost/latency rõ và đã benchmark VRAM.
Compose dùng cho local review; production cần Kubernetes hoặc platform tương đương để có rollout, secret, scaling, network policy, observability và backup.
```

## 14. Production readiness answer

Trong README hoặc deployment note, trả lời trực tiếp:

```markdown
## Dùng được trong production không?

Chưa, nếu chỉ dùng cấu hình lab. Có thể đưa vào production sau khi hoàn thành các điều kiện sau:

- CI build image, lock dependencies, scan vulnerability và tag immutable.
- Secret nằm trong secret manager, không nằm trong Git/image.
- Authn/authz và tenant/ACL filter chạy server-side.
- `/ready` kiểm tra vector DB, model provider và index version.
- Resource requests/limits được sizing bằng benchmark.
- Vector DB/document store có backup/restore test.
- Logs/metrics/traces có dashboard và alert.
- Có rate limit, timeout, upload limit và graceful shutdown.
- Có rollout/smoke test/rollback plan cho image, prompt, model và index.
- Nếu dùng GPU: node driver/toolkit/device plugin ổn định, có monitoring VRAM/GPU utilization và plan xử lý GPU OOM.
```

Nếu bạn muốn ghi "có thể dùng production", hãy ghi kèm phạm vi:

```markdown
Có thể dùng production cho internal workload traffic thấp/trung bình nếu triển khai trên Kubernetes hoặc platform tương đương, dùng managed LLM/vector DB, bật auth/ACL, có backup, monitoring, rate limit và đã pass load test theo SLO.
Chưa phù hợp cho dữ liệu nhạy cảm hoặc traffic cao nếu chưa có security review, data governance và capacity planning.
```

## 15. Submission checklist

Nộp các artifact:

- [ ] `backend/Dockerfile`.
- [ ] `.dockerignore`.
- [ ] `.env.example`.
- [ ] `docker-compose.yml`.
- [ ] `scripts/smoke-test.sh`.
- [ ] `k8s/configmap.yaml`.
- [ ] `k8s/secret.example.yaml`.
- [ ] `k8s/api-deployment.yaml`.
- [ ] `k8s/api-service.yaml`.
- [ ] Optional `k8s/model-server-deployment.yaml`.
- [ ] `reports/deployment-benchmark.md`.
- [ ] README/deployment note có trade-off và production readiness answer.

## 16. Rubric

| Hạng mục | Điểm | Tiêu chí |
|---|---:|---|
| Docker image | 20 | Build được, dependency locked, non-root, không leak secret/data |
| Compose | 20 | API + vector DB chạy được, healthcheck, volume, `.env.example` |
| Health/readiness | 15 | `/health` nhẹ, `/ready` kiểm tra dependency đúng |
| Kubernetes | 15 | Deployment/Service/ConfigMap/Secret, resource, probes |
| GPU awareness | 10 | Hiểu NVIDIA stack, có manifest nodeSelector/toleration/GPU limit |
| Smoke test/benchmark | 10 | Có script và báo cáo latency/resource |
| Trade-off/production readiness | 10 | Trả lời rõ dùng được production không và cần điều kiện gì |

## 17. Lỗi thường gặp

- Commit `.env` hoặc API key.
- Docker image copy cả `data/`, `.git`, `.venv`, model cache.
- Compose dùng `localhost` bên trong container để gọi service khác.
- `/ready` luôn trả `200` dù vector DB chết.
- Dùng `latest` cho production image.
- Kubernetes manifest không có resource requests/limits.
- Model load chậm nhưng không có `startupProbe`, dẫn đến liveness restart loop hoặc phải dùng `initialDelaySeconds` quá lớn.
- GPU pod thiếu `nvidia.com/gpu`.
- GPU deployment một replica dùng rolling update dù cluster không có GPU dự phòng.
- GPU pod có toleration nhưng không có `nodeSelector`, dẫn đến scheduling không như kỳ vọng.
- GPU node không taint, workload thường chạy vào GPU node.
- HPA chỉ nhìn CPU trong khi bottleneck thật là tokens/sec, queue depth hoặc VRAM.

## 18. Câu hỏi tự kiểm tra

1. Docker image của bạn có chạy được nếu không mount source code không?
2. Người khác có thể tạo `.env` chỉ từ `.env.example` không?
3. Nếu Qdrant chưa ready, API có nhận traffic không?
4. Nếu LLM provider timeout, request có timeout và log trace ID không?
5. Nếu rolling deploy xảy ra trong lúc streaming, graceful shutdown xử lý thế nào?
6. Nếu index version mới lỗi, rollback bằng cách nào?
7. Nếu GPU OOM, bạn nhìn metric/log nào trước?
8. Nếu traffic tăng 5 lần, bạn scale API, vector DB hay model server trước?
