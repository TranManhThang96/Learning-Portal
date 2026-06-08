# Day 43: Docker/K8s/GPU Serving Cho AI Workload

## 1. Mục tiêu bài học

Day 43 tập trung vào deployment layer cho AI system. Sau Day 40-42, bạn đã có RAG/LLM service, streaming API và các lựa chọn serving như managed LLM, vLLM hoặc TGI. Bài này trả lời câu hỏi thực tế hơn:

```text
Làm sao đóng gói service đó thành artifact repeatable?
Làm sao reviewer chạy được bằng Docker Compose?
Nếu lên Kubernetes thì cần manifest nào?
Nếu workload cần GPU thì scheduler biết node nào có GPU bằng cách nào?
Nếu đưa vào production thì còn thiếu điều kiện gì?
```

Mục tiêu không phải học toàn bộ Kubernetes. Mục tiêu là biết đủ để deploy một AI workload có trách nhiệm:

- Docker image nhỏ, reproducible, không chứa secret.
- Runtime config đi qua environment variable hoặc secret store.
- Health/readiness endpoint phản ánh đúng trạng thái model, vector DB và dependency.
- Docker Compose chạy được local stack bằng một lệnh.
- Kubernetes manifests có resource boundary, probes, rollout strategy và secret/config separation.
- GPU pod chỉ chạy trên GPU node, request đúng `nvidia.com/gpu` và không chiếm GPU node cho workload thường.
- Có trade-off rõ giữa Compose, Kubernetes, Helm, KServe, Ray Serve, managed LLM và self-host GPU.

## 2. Mental model

AI service production không chỉ là:

```text
FastAPI app -> docker build -> docker run
```

Một deployment tốt phải quản lý cả artifact, runtime state và operational behavior:

```text
Source code
  -> locked dependencies
  -> Docker image
  -> config/secrets
  -> runtime volumes
  -> health/readiness
  -> scheduler constraints
  -> rollout/rollback
  -> logs/metrics/traces
  -> smoke test
```

Với AI workload, bạn có thêm vài constraint không thường gặp ở backend CRUD:

- Model loading có thể mất vài chục giây đến vài phút.
- VRAM là tài nguyên giới hạn hơn CPU/RAM.
- Context length và concurrency làm KV cache tăng nhanh.
- Cold start có thể làm readiness sai nếu chỉ kiểm tra process alive.
- GPU driver, CUDA runtime, PyTorch/TensorRT/vLLM version phải tương thích.
- Vector DB và index version cần backup, migration và rollback plan.
- Streaming response cần timeout, graceful shutdown và client disconnect handling.

## 3. Target architecture cho bài học

Phiên bản local bằng Docker Compose:

```text
Browser / curl
  -> api: FastAPI RAG service
      -> qdrant: vector DB
      -> optional local model server
      -> optional managed LLM API
  -> volumes: document data, vector DB data, model cache
```

Phiên bản Kubernetes:

```text
Ingress / Gateway
  -> Service api
      -> Deployment api
          -> ConfigMap: non-secret config
          -> Secret: API keys
          -> PVC: optional data/cache
      -> Service vector-db
      -> StatefulSet vector-db or managed vector DB
      -> Service model-server
      -> Deployment model-server on GPU nodes
```

Best practice trong nhiều team là tách API orchestration và model serving:

- `api`: authentication, request validation, RAG orchestration, prompt policy, citations, tracing.
- `vector-db`: Qdrant, pgvector, Milvus hoặc managed vector DB.
- `model-server`: vLLM/TGI/Triton/Ollama hoặc managed LLM provider.
- `observability`: logs, metrics, traces, dashboards, alerts.

Tách như vậy giúp scale API và GPU inference độc lập. API thường scale theo request count; GPU model server scale theo tokens/sec, queue depth, VRAM và p95 latency.

## 4. Docker image cho ML/AI

### 4.1 Nguyên tắc thiết kế image

Một Docker image dùng cho AI backend nên đạt các tiêu chí:

- Pin base image và Python version.
- Lock dependency bằng `requirements.lock`, `uv.lock`, `poetry.lock` hoặc equivalent.
- Tách layer dependency và layer source code để tận dụng build cache.
- Không copy `.env`, API key, dataset thô, vector index, model cache lớn hoặc notebook rác vào image.
- Chạy bằng non-root user nếu service không cần privilege.
- Log ra stdout/stderr.
- Có `HEALTHCHECK` hoặc ít nhất app có `/health` và `/ready`.
- Dùng image tag immutable hoặc digest khi deploy production.
- Không dùng `latest` trong production manifest.

`.dockerignore` quan trọng không kém Dockerfile:

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

Không ignore `.env.example` vì reviewer cần biết config nào phải khai báo.

### 4.2 Dockerfile CPU cho FastAPI RAG backend

Ví dụ này phù hợp với RAG API dùng managed LLM hoặc embedding API bên ngoài. Nó không cần GPU trong container.

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
COPY pyproject.toml README.md ./

RUN chown -R app:app ${APP_HOME}
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

Điểm gần production:

- Có non-root user.
- Có lock file thay vì dependency trôi nổi.
- Cài dependency trước khi copy source code.
- Có healthcheck.
- Không copy toàn bộ repo một cách mù quáng.
- Không bake secret vào image.

Nếu app cần package native như `psycopg`, `pymupdf`, `torch`, `faiss`, bạn có thể cần stage build riêng hoặc base image có đủ system library. Không chọn Alpine cho ML Python nếu dependency native làm build phức tạp; `python:slim` thường thực dụng hơn.

### 4.3 Dockerfile GPU cho local model/reranker service

GPU image chỉ cần khi container trực tiếp chạy model bằng CUDA. Nếu API chỉ gọi OpenAI/Anthropic/Azure hoặc gọi model server khác qua HTTP, API image không cần NVIDIA base image.

Ví dụ skeleton:

```dockerfile
# syntax=docker/dockerfile:1.7
ARG CUDA_IMAGE=nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
FROM ${CUDA_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    HF_HOME=/models/huggingface \
    TRANSFORMERS_CACHE=/models/huggingface

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home-dir ${APP_HOME} app

COPY requirements-gpu.lock ./requirements-gpu.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade pip \
    && python3 -m pip install -r requirements-gpu.lock

COPY app ./app
RUN mkdir -p /models/huggingface && chown -R app:app ${APP_HOME} /models
USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8001/health || exit 1

CMD ["python3", "-m", "app.model_server"]
```

Lưu ý quan trọng:

- CUDA image version phải tương thích với framework wheels bạn cài.
- Host driver phải đủ mới cho CUDA runtime trong container.
- Model cache nên mount volume/PVC, không copy model hàng chục GB vào image trừ khi bạn có lý do rõ.
- `start-period` của healthcheck GPU thường dài hơn vì model load lâu.
- Không chạy container GPU với `--privileged` chỉ để thấy GPU. Cài đúng NVIDIA runtime/toolkit.

## 5. `.env.example`

`.env.example` là contract giữa code và runtime. Nó phải đủ rõ để reviewer chạy được mà không đọc toàn bộ source.

```dotenv
# App
APP_ENV=local
APP_NAME=rag-serving
LOG_LEVEL=INFO
PORT=8000
WORKERS=1
REQUEST_TIMEOUT_SECONDS=60
MAX_UPLOAD_MB=25
MAX_CONCURRENT_REQUESTS=16

# LLM mode: managed | local
LLM_MODE=managed
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=replace-me

# Local model server, used when LLM_MODE=local
MODEL_SERVER_URL=http://model-server:8001/v1
MODEL_ID=meta-llama/Llama-3.1-8B-Instruct
MODEL_CACHE_DIR=/models/huggingface

# Embedding
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# Vector DB
VECTOR_DB=qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=policy_chunks

# Index/prompt versioning
INDEX_VERSION=rag-v1
PROMPT_VERSION=answer-v1
CHUNKING_VERSION=chunk-v1

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=
TRACE_SAMPLE_RATE=1.0
```

Production note:

- `.env.example` được commit.
- `.env` không được commit.
- Secret thật nên nằm trong secret manager, external secret controller hoặc CI/CD secret store.
- Với Kubernetes, non-secret config vào `ConfigMap`, secret vào `Secret` hoặc external secret.

## 6. Docker Compose cho RAG stack

Compose dùng để local demo, integration test và portfolio review. Compose không thay thế Kubernetes production, nhưng nó là deliverable bắt buộc vì giúp người khác chạy hệ thống nhanh.

Ví dụ Compose gần production hơn bản tối giản:

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

volumes:
  qdrant_data:
  model_cache:
```

Qdrant có các endpoint `/healthz`, `/livez`, `/readyz`, nhưng Docker healthcheck chạy bên trong container. Nếu image không có `curl`, `wget` hoặc binary healthcheck riêng, healthcheck trong Compose sẽ giòn. Cách thực dụng cho lab là để API `/ready` retry và báo dependency chưa sẵn sàng; với Kubernetes, dùng `httpGet` probe trực tiếp từ kubelet.

Chạy CPU path:

```bash
cp .env.example .env
docker compose up --build
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
```

Chạy GPU profile:

```bash
docker compose --profile gpu up --build
```

Trade-off của Compose:

- Mạnh: dễ chạy local, dễ review, ít dependency.
- Yếu: không đại diện đầy đủ cho scheduling, autoscaling, rollout, secret management, network policy.
- Best use: portfolio, integration test, demo environment, single-VM internal tool nhỏ.

## 7. Healthcheck và readiness cho AI service

Tối thiểu nên có:

```text
GET /health
  -> process còn sống
  -> event loop phản hồi
  -> không gọi dependency nặng

GET /ready
  -> app config hợp lệ
  -> vector DB reachable
  -> collection/index tồn tại
  -> model provider reachable hoặc local model loaded
  -> migration/index version đúng
```

Ví dụ FastAPI:

```python
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/ready")
async def ready() -> JSONResponse:
    checks = {
        "config": True,
        "vector_db": await check_qdrant(),
        "llm": await check_llm_provider(),
        "index_version": await check_index_version(),
    }
    http_status = status.HTTP_200_OK if all(checks.values()) else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse({"status": "ready" if http_status == 200 else "not_ready", "checks": checks}, status_code=http_status)
```

Không nên để `/ready` gọi một LLM generation đầy đủ cho mỗi probe; chi phí và latency sẽ tệ. Với managed LLM, check nhẹ bằng config/token validation hoặc endpoint metadata nếu provider hỗ trợ. Với local model, check trạng thái model loaded hoặc warmup marker nội bộ.

## 8. NVIDIA container stack

Để container dùng được NVIDIA GPU, cần phân biệt bốn lớp:

| Lớp | Vai trò |
|---|---|
| Host NVIDIA driver | Driver thật trên node/VM, giao tiếp với GPU |
| NVIDIA Container Toolkit | Cho container runtime expose GPU device/library vào container |
| Container runtime | Docker/containerd/CRI-O được cấu hình runtime NVIDIA khi cần |
| Kubernetes device plugin | Advertise GPU thành schedulable resource như `nvidia.com/gpu` |

Local Docker smoke test:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Kubernetes GPU node checklist:

```bash
nvidia-smi
kubectl get nodes
GPU_NODE="${GPU_NODE:-gpu-node-1}"
kubectl describe node "${GPU_NODE}" | grep -A5 "nvidia.com/gpu"
kubectl get pods -n nvidia-device-plugin
```

Theo Kubernetes, GPU được expose qua device plugin như custom schedulable resource. Với NVIDIA, resource phổ biến là:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

Điểm dễ sai:

- GPU phải nằm trong `limits`. Nếu khai báo cả `requests` và `limits` thì hai giá trị phải bằng nhau.
- Pod không request `nvidia.com/gpu` thì scheduler không reserve GPU cho pod.
- Taint chỉ chặn pod không phù hợp; `nodeSelector`/node affinity mới kéo pod về đúng GPU node.
- Nếu GPU node bị taint, `nvidia-device-plugin` DaemonSet cũng cần toleration phù hợp để chạy trên node đó.
- Không assume một GPU request luôn là độc quyền nếu cluster bật MIG, MPS hoặc time-slicing. Cần hiểu policy của cluster.

## 9. Kubernetes scheduling cho GPU

### 9.1 Label GPU node

Ví dụ label node có NVIDIA L4:

```bash
kubectl label node gpu-node-1 accelerator=nvidia-l4
kubectl label node gpu-node-1 workload=ai-inference
```

### 9.2 Taint GPU node

Mục tiêu là tránh workload thường chạy lên GPU node:

```bash
kubectl taint node gpu-node-1 nvidia.com/gpu=true:NoSchedule
```

### 9.3 Pod cần cả selector và toleration

```yaml
nodeSelector:
  accelerator: nvidia-l4
  workload: ai-inference
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
containers:
  - name: model-server
    resources:
      limits:
        nvidia.com/gpu: 1
```

Ý nghĩa:

- `nodeSelector`: chỉ chọn node có label phù hợp.
- `tolerations`: cho phép pod chạy trên node có taint tương ứng.
- `nvidia.com/gpu`: scheduler reserve GPU cho container.

Nếu chỉ có toleration mà không có selector, pod "được phép" chạy trên GPU node nhưng không bị bắt buộc chạy ở đó. Nếu chỉ có selector mà node có taint, pod vẫn không schedule được.

## 10. Kubernetes manifests gần production

### 10.1 ConfigMap

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
  VECTOR_DB: "qdrant"
  QDRANT_URL: "http://qdrant:6333"
  QDRANT_COLLECTION: "policy_chunks"
  INDEX_VERSION: "rag-v1"
  PROMPT_VERSION: "answer-v1"
  REQUEST_TIMEOUT_SECONDS: "60"
  MAX_CONCURRENT_REQUESTS: "32"
```

### 10.2 Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-api-secret
type: Opaque
stringData:
  OPENAI_API_KEY: "replace-in-secret-manager"
```

Production không nên commit secret manifest chứa giá trị thật. Dùng External Secrets, Sealed Secrets, SOPS hoặc secret manager của cloud provider.

### 10.3 Deployment API

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
  labels:
    app: rag-api
spec:
  replicas: 2
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app: rag-api
  template:
    metadata:
      labels:
        app: rag-api
    spec:
      terminationGracePeriodSeconds: 60
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: ghcr.io/acme/rag-api:2026.05.10-abcdef
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
              name: http
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
            timeoutSeconds: 3
            failureThreshold: 6
          livenessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 30
            timeoutSeconds: 3
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
```

### 10.4 Service

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

### 10.5 GPU model server Deployment

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
          image: ghcr.io/acme/rag-model-server:2026.05.10-abcdef
          ports:
            - containerPort: 8001
              name: http
          env:
            - name: MODEL_ID
              value: "meta-llama/Llama-3.1-8B-Instruct"
            - name: MODEL_CACHE_DIR
              value: "/models/huggingface"
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
          volumeMounts:
            - name: model-cache
              mountPath: /models/huggingface
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 20
          livenessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 5
      volumes:
        - name: model-cache
          persistentVolumeClaim:
            claimName: model-cache-pvc
```

GPU production note:

- `replicas: 1` là mặc định an toàn cho một model server khi bạn chưa có load test.
- `strategy: Recreate` tránh rollout tạo pod GPU thứ hai khi cluster chỉ có một GPU phù hợp, nhưng chấp nhận downtime. Nếu có GPU dự phòng và cần zero-downtime, dùng `RollingUpdate` với capacity đã reserve, warmup và smoke test trước khi nhận traffic.
- `startupProbe` bảo vệ model load chậm: readiness/liveness chỉ bắt đầu sau khi startup thành công. Không chỉ kéo dài `initialDelaySeconds` một cách đoán mò.
- Scale GPU theo queue depth, tokens/sec, p95 latency và VRAM, không chỉ CPU.
- Nếu model load lâu, sizing `startupProbe` theo benchmark cold start, chọn rollout strategy theo GPU capacity và warm up trước khi nhận traffic.
- Với multi-GPU hoặc tensor parallel, manifest cần thêm logic riêng của serving engine.

## 11. Helm overview

Helm là package manager cho Kubernetes. Với AI workload, Helm hữu ích khi bạn có nhiều manifest lặp lại theo environment:

```text
charts/rag-serving/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    configmap.yaml
    secret.yaml
    hpa.yaml
```

Khi nên dùng Helm:

- Có nhiều environment: dev, staging, prod.
- Cần parameterize image tag, replica, resource, node selector, secret reference.
- Team đã có GitOps/Helm workflow.
- Muốn reuse chart cho nhiều model/service.

Khi chưa nên dùng Helm:

- Bạn mới học Kubernetes và manifest còn ít.
- Team chưa có release workflow rõ.
- Chart chỉ bọc lại 2-3 file YAML nhưng làm debug khó hơn.

Best path cho bài học:

1. Viết raw manifests trước để hiểu object.
2. Sau khi manifest ổn, mới chuyển sang Helm chart.
3. Không dùng Helm để che lấp việc chưa hiểu scheduling, probes và resource.

## 12. KServe overview

KServe là một inference platform trên Kubernetes cho predictive và generative inference. Nó cung cấp abstraction như `InferenceService`, model runtime, autoscaling, protocol chuẩn và integration với model serving runtimes.

Khi KServe phù hợp:

- Platform team đã vận hành Kubernetes tốt.
- Có nhiều model cần deploy theo pattern giống nhau.
- Cần standardized inference endpoint, autoscaling, canary/rollout, model runtime.
- Muốn tách model serving platform khỏi business API.

Khi KServe có thể quá nặng:

- Chỉ có một RAG app nhỏ.
- Team chưa vận hành Kubernetes/GPU ổn định.
- Logic chính nằm ở orchestration/RAG pipeline hơn là pure model inference.

Mental model:

```text
Client/API
  -> InferenceService
      -> predictor runtime
      -> model storage/cache
      -> autoscaling
      -> standardized inference protocol
```

Với RAG, thường không đưa toàn bộ RAG orchestration vào KServe. Cách sạch hơn:

- FastAPI vẫn làm RAG orchestration.
- KServe phục vụ embedding/reranker/local LLM như model endpoint.
- API gọi KServe endpoint qua HTTP/gRPC.

## 13. Ray Serve overview

Ray Serve là framework serving online inference chạy trên Ray. Nó hợp với model composition và pipeline nhiều bước bằng Python:

```text
HTTP request
  -> Ray Serve deployment A: preprocess
  -> deployment B: retriever/reranker
  -> deployment C: model inference
  -> deployment D: postprocess
```

Khi Ray Serve phù hợp:

- Pipeline inference nhiều model, nhiều bước, cần composition rõ.
- Cần dynamic batching, streaming, multi-node hoặc multi-GPU scheduling.
- Team đã dùng Ray cho batch/distributed workload.
- Muốn scale từng deployment trong pipeline độc lập.

Khi Ray Serve có thể quá nặng:

- RAG API đơn giản, traffic thấp.
- Team chưa có kinh nghiệm vận hành Ray cluster.
- Managed LLM đã đáp ứng latency/cost.

Rule thực dụng:

- FastAPI + managed LLM: tốt cho MVP và nhiều production app vừa/nhỏ.
- FastAPI + vLLM/TGI trên GPU: tốt khi cần self-host LLM rõ ràng.
- KServe: tốt khi platform team chuẩn hóa model serving trên Kubernetes.
- Ray Serve: tốt khi inference graph phức tạp và cần scale nhiều bước bằng Ray.

## 14. Trade-off matrix

| Lựa chọn | Điểm mạnh | Điểm yếu | Khi chọn |
|---|---|---|---|
| Docker Compose | Chạy local nhanh, dễ review | Không có scheduling/rollout thật | Portfolio, demo, integration test |
| Raw K8s manifests | Rõ object, ít magic | Lặp YAML, khó quản lý nhiều env | Học, service ít, platform nhỏ |
| Helm | Template hóa release | Debug chart/values phức tạp | Nhiều env/service, GitOps |
| Managed LLM | Ít ops GPU, ship nhanh | Cost, privacy, rate limit, vendor dependency | MVP, business app, traffic vừa |
| Self-host GPU | Control model/data/latency | Cần GPU ops, capacity planning | Privacy cao, volume lớn, custom model |
| KServe | Chuẩn hóa model serving | Platform overhead | Nhiều model trên K8s |
| Ray Serve | Composition, batching, distributed | Vận hành Ray cluster | Multi-model pipeline phức tạp |
| Image chứa model | Startup nhanh hơn | Image rất lớn, rollback chậm | Edge/offline, model nhỏ, release ít |
| Mount model cache | Image nhỏ, update dễ | Cold start tải model | Dev/staging, model lớn, cache tốt |
| Scale API replicas | Rẻ và dễ | Dependency/shared state cần thiết kế | API stateless |
| Scale GPU replicas | Tăng throughput | Tốn GPU, warmup lâu | Traffic cao, queue depth cao |

## 15. Best solution theo context/performance

Không có một deployment strategy tốt nhất cho mọi AI workload. Dưới đây là lựa chọn thực dụng.

| Context | Best solution | Lý do |
|---|---|---|
| Capstone/portfolio | Docker Compose + CPU API + Qdrant + managed LLM | Reviewer chạy nhanh, ít yêu cầu phần cứng |
| Internal demo trên một VM | Docker Compose hoặc systemd + Docker, managed LLM | Đơn giản, đủ kiểm soát, chi phí ops thấp |
| Production nhỏ, traffic vừa | Kubernetes API stateless + managed vector DB + managed LLM | Tập trung vào reliability/security hơn GPU ops |
| Privacy cao, không gửi dữ liệu ra ngoài | Kubernetes + self-host embedding/reranker/LLM trên GPU | Control data egress, cần benchmark và hardening |
| Throughput LLM cao | Dedicated model server với vLLM/TGI + queue/batching + GPU autoscaling policy | Tối ưu tokens/sec và VRAM |
| Nhiều model/team cùng deploy | KServe + Helm/GitOps + shared observability | Chuẩn hóa platform, giảm drift |
| Inference pipeline nhiều bước | Ray Serve hoặc service composition rõ | Scale từng stage, batching và routing tốt hơn |

Với bài Day 43, best baseline là:

```text
Local/portfolio:
  Docker Compose
  FastAPI API
  Qdrant
  managed LLM by default
  optional GPU model-server profile

Kubernetes optional:
  Deployment + Service + ConfigMap + Secret
  resource requests/limits
  readiness/liveness probes
  GPU model-server manifest with nodeSelector/tolerations/nvidia.com/gpu
```

## 16. Production readiness answer

### Dùng được trong production không?

Có, nhưng không phải chỉ với file Dockerfile và Compose của bài học. Bộ cấu hình trong bài này là production-oriented baseline, chưa phải production hoàn chỉnh cho mọi doanh nghiệp.

### Nếu có thì cần điều kiện gì?

Cần tối thiểu các điều kiện sau:

- Image được build trong CI, dependency locked, vulnerability scan, tag immutable hoặc digest.
- Secret không nằm trong image, Git repo hoặc plain Kubernetes Secret không mã hóa ở rest ngoài chuẩn cluster.
- `/health` và `/ready` phản ánh đúng trạng thái app, vector DB, model provider và index version.
- API stateless hoặc state được đưa vào DB/object storage/vector DB có backup.
- Resource requests/limits được sizing bằng benchmark thật.
- GPU node có driver, NVIDIA Container Toolkit, device plugin và monitoring đúng.
- Rollout có smoke test, rollback plan cho image, prompt version, index version và model version.
- Observability có structured logs, metrics p50/p95/p99 latency, error rate, token usage, cost và trace ID.
- Security có authn/authz, tenant/ACL filter server-side, network policy, request size limit và rate limit.
- Data có backup/restore test cho vector DB, metadata DB và document store.
- Load test chứng minh p95 latency, throughput, VRAM và cost nằm trong SLO.
- Có incident runbook: provider outage, vector DB down, GPU OOM, model server cold start, bad index release.

Nếu thiếu các điều kiện trên, hệ thống vẫn có thể dùng cho demo, staging hoặc internal prototype, nhưng chưa nên gọi là production-ready.

## 17. Checklist cuối bài

- [ ] Có `Dockerfile` cho API.
- [ ] Có `.dockerignore`.
- [ ] Có `.env.example` đầy đủ.
- [ ] Có `docker-compose.yml` chạy được CPU path.
- [ ] Có optional GPU service/profile nếu dùng local model.
- [ ] Có `/health` và `/ready`.
- [ ] Có smoke test script.
- [ ] Có K8s `Deployment`, `Service`, `ConfigMap`, `Secret`.
- [ ] Có GPU manifest dùng `nodeSelector`, tolerations và `nvidia.com/gpu`.
- [ ] Có resource estimate CPU/RAM/VRAM.
- [ ] Có trade-off và best solution theo context.
- [ ] README/deployment note trả lời production readiness.

## 18. Nguồn tham khảo chính thức

- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Docker Compose service reference: https://docs.docker.com/reference/compose-file/services/
- Qdrant monitoring endpoints: https://qdrant.tech/documentation/ops-monitoring/monitoring/
- Kubernetes GPU scheduling: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
- Kubernetes node selection: https://kubernetes.io/docs/concepts/configuration/assign-pod-node/
- Kubernetes taints/tolerations: https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/
- Kubernetes startup/liveness/readiness probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- NVIDIA Kubernetes device plugin: https://github.com/NVIDIA/k8s-device-plugin
- KServe overview: https://kserve.github.io/kserve/
- Ray Serve overview: https://docs.ray.io/en/latest/serve/
