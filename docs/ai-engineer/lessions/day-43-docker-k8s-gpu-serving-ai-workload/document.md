# Document: Docker/K8s/GPU Serving Templates Và Runbook

Tài liệu này gom các template thực dụng để bạn dùng khi làm lab Day 43 hoặc nâng cấp capstone Day 40. Hãy xem đây là starting point, không phải cấu hình production universal.

## 1. Project structure đề xuất

```text
rag-serving/
  backend/
    app/
      main.py
      settings.py
      health.py
      rag_pipeline.py
    tests/
    Dockerfile
    requirements.in
    requirements.lock
    pyproject.toml
  model-server/
    app/
      model_server.py
    Dockerfile.gpu
    requirements-gpu.lock
  k8s/
    namespace.yaml
    configmap.yaml
    secret.example.yaml
    api-deployment.yaml
    api-service.yaml
    qdrant-statefulset.yaml
    qdrant-service.yaml
    model-server-deployment.yaml
    model-server-service.yaml
    pdb.yaml
  scripts/
    smoke-test.sh
    benchmark.sh
  data/
    sample_docs/
  reports/
  .dockerignore
  .env.example
  docker-compose.yml
  README.md
```

Rule ownership:

- Source code vào image.
- Runtime config vào env/config map/secret.
- Runtime data vào volume/PVC/object storage.
- Model cache lớn vào volume/PVC, không bake vào image mặc định.

## 2. Dockerfile template cho API

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

## 3. Dockerfile.gpu template

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

## 4. `.env.example` template

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

APP_IMAGE_TAG=local
MODEL_IMAGE_TAG=local
QDRANT_TAG=v1.14.1
```

## 5. Docker Compose template

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

Qdrant expose `/healthz`, `/livez` và `/readyz`, nhưng Compose healthcheck chạy bên trong container. Nếu image không có `curl`, `wget` hoặc healthcheck binary, đừng thêm healthcheck giòn; hãy để API `/ready` retry/report trạng thái Qdrant. Trong Kubernetes, `httpGet` probe không cần tool bên trong container.

## 6. Kubernetes namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rag-serving
  labels:
    name: rag-serving
```

## 7. Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rag-api-config
  namespace: rag-serving
data:
  APP_ENV: "production"
  APP_NAME: "rag-serving"
  LOG_LEVEL: "INFO"
  PORT: "8000"
  WORKERS: "2"
  REQUEST_TIMEOUT_SECONDS: "60"
  MAX_UPLOAD_MB: "25"
  MAX_CONCURRENT_REQUESTS: "32"
  LLM_MODE: "managed"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4.1-mini"
  EMBEDDING_MODEL: "text-embedding-3-small"
  EMBEDDING_DIM: "1536"
  VECTOR_DB: "qdrant"
  QDRANT_URL: "http://qdrant.rag-serving.svc.cluster.local:6333"
  QDRANT_COLLECTION: "policy_chunks"
  INDEX_VERSION: "rag-v1"
  PROMPT_VERSION: "answer-v1"
  CHUNKING_VERSION: "chunk-v1"
```

## 8. Kubernetes Secret example

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: rag-api-secret
  namespace: rag-serving
type: Opaque
stringData:
  OPENAI_API_KEY: "replace-in-secret-manager"
```

Không dùng file trên với secret thật. Trong production, ưu tiên External Secrets, Sealed Secrets, SOPS hoặc secret manager của cloud provider.

## 9. API Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
  namespace: rag-serving
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

## 10. API Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rag-api
  namespace: rag-serving
spec:
  type: ClusterIP
  selector:
    app: rag-api
  ports:
    - name: http
      port: 8000
      targetPort: http
```

## 11. Qdrant StatefulSet cho lab

Production lớn nên cân nhắc Qdrant chart/operator/managed service và backup rõ ràng. Template dưới đây chỉ đủ cho lab hoặc namespace nhỏ.

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
  namespace: rag-serving
spec:
  serviceName: qdrant
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
        - name: qdrant
          image: qdrant/qdrant:v1.14.1
          ports:
            - name: http
              containerPort: 6333
            - name: grpc
              containerPort: 6334
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
          readinessProbe:
            httpGet:
              path: /readyz
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 30
            periodSeconds: 30
          volumeMounts:
            - name: qdrant-data
              mountPath: /qdrant/storage
  volumeClaimTemplates:
    - metadata:
        name: qdrant-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 20Gi
```

## 12. Qdrant Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: qdrant
  namespace: rag-serving
spec:
  type: ClusterIP
  selector:
    app: qdrant
  ports:
    - name: http
      port: 6333
      targetPort: http
    - name: grpc
      port: 6334
      targetPort: grpc
```

## 13. GPU model server PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-cache-pvc
  namespace: rag-serving
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 100Gi
```

## 14. GPU model server Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-server
  namespace: rag-serving
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
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8001
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
          volumeMounts:
            - name: model-cache
              mountPath: /models/huggingface
      volumes:
        - name: model-cache
          persistentVolumeClaim:
            claimName: model-cache-pvc
```

## 15. GPU model server Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: model-server
  namespace: rag-serving
spec:
  type: ClusterIP
  selector:
    app: model-server
  ports:
    - name: http
      port: 8001
      targetPort: http
```

## 16. PodDisruptionBudget cho API

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: rag-api-pdb
  namespace: rag-serving
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: rag-api
```

Với GPU model server chỉ có một replica, PDB không tạo high availability thật. HA cho model server cần nhiều GPU replica, traffic routing và capacity đủ lớn.

## 17. Cài NVIDIA device plugin bằng Helm

Checklist trước:

```bash
nvidia-smi
containerd --version
kubectl get nodes
```

Xem version chart hiện có rồi pin một version đã review:

```bash
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm repo update
helm search repo nvdp/nvidia-device-plugin --versions | head

export NVDP_CHART_VERSION="<pin-reviewed-version>"
helm upgrade -i nvdp nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin \
  --create-namespace \
  --version "${NVDP_CHART_VERSION}"
```

Kiểm chứng:

```bash
kubectl get pods -n nvidia-device-plugin
GPU_NODE="${GPU_NODE:-gpu-node-1}"
kubectl describe node "${GPU_NODE}" | grep -A5 "nvidia.com/gpu"
```

Nếu GPU node có taint riêng, đảm bảo DaemonSet của device plugin có toleration tương ứng. Nếu không, plugin không chạy trên GPU node và Kubernetes sẽ không thấy `nvidia.com/gpu`.

## 18. GPU node label/taint commands

```bash
kubectl label node gpu-node-1 accelerator=nvidia-l4
kubectl label node gpu-node-1 workload=ai-inference
kubectl taint node gpu-node-1 nvidia.com/gpu=true:NoSchedule
```

Undo khi lab xong:

```bash
kubectl label node gpu-node-1 accelerator-
kubectl label node gpu-node-1 workload-
kubectl taint node gpu-node-1 nvidia.com/gpu=true:NoSchedule-
```

## 19. Helm values skeleton cho RAG API

```yaml
image:
  repository: ghcr.io/acme/rag-api
  tag: "2026.05.10-abcdef"
  pullPolicy: IfNotPresent

replicaCount: 2

config:
  APP_ENV: production
  LOG_LEVEL: INFO
  LLM_MODE: managed
  LLM_PROVIDER: openai
  LLM_MODEL: gpt-4.1-mini
  QDRANT_URL: http://qdrant.rag-serving.svc.cluster.local:6333
  QDRANT_COLLECTION: policy_chunks

secretRefs:
  enabled: true
  name: rag-api-secret

resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: "2"
    memory: 4Gi

probes:
  readiness:
    path: /ready
    initialDelaySeconds: 10
  liveness:
    path: /health
    initialDelaySeconds: 30

nodeSelector: {}
tolerations: []
affinity: {}
```

## 20. KServe skeleton

KServe nên phục vụ model endpoint, không nhất thiết chứa toàn bộ RAG orchestration.

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: embedding-model
  namespace: rag-serving
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: s3://example-bucket/models/embedding-model
      resources:
        requests:
          cpu: "1"
          memory: "2Gi"
        limits:
          cpu: "2"
          memory: "4Gi"
```

Template trên chỉ là skeleton để hiểu shape của `InferenceService`. Runtime/model format thật phụ thuộc stack bạn chọn: built-in runtime, custom runtime, Hugging Face runtime, vLLM runtime hoặc runtime nội bộ.

## 21. Ray Serve skeleton

```python
from ray import serve
from starlette.requests import Request

@serve.deployment(num_replicas=2)
class Retriever:
    async def __call__(self, query: str) -> list[dict]:
        return await search_vector_db(query)

@serve.deployment(ray_actor_options={"num_gpus": 1})
class Reranker:
    def __init__(self) -> None:
        self.model = load_reranker()

    async def __call__(self, query: str, docs: list[dict]) -> list[dict]:
        return self.model.rerank(query, docs)

@serve.deployment
class RagApp:
    def __init__(self, retriever, reranker) -> None:
        self.retriever = retriever
        self.reranker = reranker

    async def __call__(self, request: Request) -> dict:
        body = await request.json()
        docs = await self.retriever.remote(body["question"])
        ranked = await self.reranker.remote(body["question"], docs)
        return {"contexts": ranked[:5]}

app = RagApp.bind(Retriever.bind(), Reranker.bind())
```

Ray Serve hữu ích khi bạn muốn scale `Retriever`, `Reranker` và model generation như các deployment riêng trong cùng inference graph.

## 22. Smoke test script

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -fsS "${BASE_URL}/health" | jq .
curl -fsS "${BASE_URL}/ready" | jq .

curl -fsS -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Nhân viên full-time có bao nhiêu ngày nghỉ phép năm?",
    "tenant_id": "demo",
    "user_roles": ["employee"]
  }' | jq .
```

Nếu không muốn phụ thuộc `jq`, in raw response và kiểm tra status code.

## 23. Benchmark script skeleton

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
N="${N:-20}"

for i in $(seq 1 "${N}"); do
  start_ns=$(date +%s%N)
  curl -fsS -o /tmp/rag-response.json -X POST "${BASE_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{"question":"Chính sách remote work áp dụng thế nào?","tenant_id":"demo","user_roles":["employee"]}'
  end_ns=$(date +%s%N)
  ms=$(( (end_ns - start_ns) / 1000000 ))
  echo "query=${i} latency_ms=${ms}"
done
```

Metric cần ghi lại:

- p50/p95/p99 latency.
- tokens input/output.
- LLM cost nếu dùng managed provider.
- CPU/RAM của API.
- Qdrant RAM/disk.
- GPU memory/utilization nếu dùng local model.
- Error rate, timeout rate, queue depth.

## 24. Deployment note template

~~~markdown
# Deployment Note: RAG Serving

## Architecture
- API: FastAPI RAG orchestration.
- Vector DB: Qdrant.
- LLM: managed OpenAI by default, optional local model server.
- Storage: Qdrant PVC and document object storage.

## Runtime config
- ConfigMap: non-secret runtime config.
- Secret: provider API key.
- Index version: rag-v1.
- Prompt version: answer-v1.

## Local run
```bash
cp .env.example .env
docker compose up --build
scripts/smoke-test.sh
```

## Kubernetes run
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.example.yaml
kubectl apply -f k8s/
```

## Resource estimate
| Component | CPU | RAM | GPU | Notes |
|---|---:|---:|---:|---|
| API | 500m-2 CPU | 1-4Gi | 0 | Depends on concurrency |
| Qdrant | 500m-2 CPU | 1-4Gi | 0 | Depends on corpus/vector dim |
| Model server | 2-8 CPU | 12-24Gi | 1 | Depends on model size/context |

## Rollback
- Roll back API image tag.
- Roll back prompt version.
- Roll back index version or restore vector DB snapshot.
- Disable local model server and switch to managed provider if GPU path fails.

## Production readiness
Answer: not production-ready until CI build/scanning, secret management, backup/restore, monitoring/alerts, load test and security review are complete.
~~~

## 25. Production checklist

Docker:

- [ ] Base image pinned.
- [ ] Dependencies locked.
- [ ] `.dockerignore` excludes secret/data/cache/model files.
- [ ] Image runs non-root.
- [ ] Health endpoint exists.
- [ ] CI builds and scans image.
- [ ] Production uses immutable tag or digest.

Compose:

- [ ] `docker compose up --build` works from clean checkout.
- [ ] `.env.example` documents all required variables.
- [ ] Volumes are explicit.
- [ ] API healthcheck exists; vector DB readiness được kiểm tra qua API `/ready`, Kubernetes probe hoặc healthcheck chính thức của image.
- [ ] CPU path works without GPU.
- [ ] GPU path is optional profile.

Kubernetes:

- [ ] ConfigMap and Secret are separated.
- [ ] Requests/limits are set.
- [ ] Readiness/liveness probes are meaningful.
- [ ] Slow-starting model có `startupProbe`; không dựa vào `initialDelaySeconds` đoán mò.
- [ ] Rollout strategy được chọn rõ (`RollingUpdate` hoặc `Recreate`) theo availability và capacity.
- [ ] GPU rollout strategy khớp capacity: `Recreate` cho một GPU không dư, hoặc rolling update khi có GPU dự phòng.
- [ ] Termination grace period handles streaming requests.
- [ ] Service is ClusterIP behind ingress/gateway.
- [ ] PDB/HPA are considered where appropriate.

GPU:

- [ ] Host driver installed.
- [ ] NVIDIA Container Toolkit configured.
- [ ] `nvidia-device-plugin` running.
- [ ] `kubectl describe node` shows `nvidia.com/gpu`.
- [ ] GPU nodes labeled.
- [ ] GPU nodes tainted to avoid random workloads.
- [ ] GPU pods have `nodeSelector`, tolerations and `nvidia.com/gpu` limit.
- [ ] VRAM, GPU utilization and queue depth are monitored.

Security:

- [ ] No API key in image or Git.
- [ ] Authn/authz implemented.
- [ ] Tenant/ACL filter enforced server-side.
- [ ] Network policy considered.
- [ ] Upload size and file type restricted.
- [ ] Rate limiting and timeout configured.

Observability:

- [ ] Structured logs with request ID/trace ID.
- [ ] Latency metrics by stage: retrieve, rerank, generate.
- [ ] Token and cost metrics.
- [ ] Error/timeout metrics.
- [ ] Dashboards and alerts.
- [ ] Smoke test runs after deploy.

Data:

- [ ] Vector DB backup/restore tested.
- [ ] Metadata DB backup/restore tested.
- [ ] Document storage lifecycle defined.
- [ ] Index version and embedding model version recorded.
- [ ] Rollback plan for bad index release.

## 26. Nguồn tham khảo chính thức

- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Docker Compose services: https://docs.docker.com/reference/compose-file/services/
- Docker Compose startup order: https://docs.docker.com/compose/how-tos/startup-order/
- Qdrant monitoring endpoints: https://qdrant.tech/documentation/ops-monitoring/monitoring/
- Kubernetes GPU scheduling: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
- Kubernetes node selection: https://kubernetes.io/docs/concepts/configuration/assign-pod-node/
- Kubernetes taints/tolerations: https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/
- Kubernetes startup/liveness/readiness probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- NVIDIA Kubernetes device plugin: https://github.com/NVIDIA/k8s-device-plugin
- KServe overview: https://kserve.github.io/kserve/
- Ray Serve overview: https://docs.ray.io/en/latest/serve/
