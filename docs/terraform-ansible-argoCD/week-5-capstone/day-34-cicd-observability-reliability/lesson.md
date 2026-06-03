# Day 34 — CI/CD, Observability, Reliability

> **Capstone Production-Grade Phase — Ngày 34/35**
> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Hoàn thành Day 28-33 (Capstone architecture, infra, data, platform, apps)
> **Output:** GitHub Actions pipeline hoàn chỉnh + PrometheusRule + Grafana dashboard + HPA/PDB manifests

---

## 1. Mục tiêu ngày học

- Viết được GitHub Actions pipeline production-like: lint → test → build → scan → push → PR update image tag
- Hiểu OIDC-based authentication (AWS) hoặc GHCR token (local) — tránh long-lived credentials
- Cấu hình Prometheus scrape targets, viết PrometheusRule alert, import Grafana dashboard
- Triển khai readiness/liveness probe, resource requests/limits, HPA, PodDisruptionBudget đúng cách
- Tránh được các production incident phổ biến: OOMKilled, ImagePullBackOff, HPA thrashing, PDB violation

---

## 2. Bối cảnh thực tế

### Chuyện thật mà DevOps team nào cũng gặp

Sau khi deploy được 3 microservices lên cluster ngày hôm qua (Day 33), bạn sẽ gặp ngay 3 vấn đề:

**1. Không có CI/CD — deploy bằng tay = disaster**

```
Dev: "anh ơi em sửa 1 dòng, deploy giúp em"
DevOps: "ok" → kubectl set image deployment/api-service
DevOps: "xong rồi" → đi uống coffee
→ 30 phút sau: dev muốn revert, DevOps đang off
→ Không ai biết version nào đang chạy, không ai biết log ở đâu
```

**2. Không có observability — incident mà không có data**

```
3:00 AM — "hệ thống chậm"
On-call: "pod nào có vấn đề?"
→ Không dashboard, không alert, không log tập trung
→ SSH vào pod, `docker logs`, restart pod, hy vọng tự hết
→ Thực tế: OOMKilled, nhưng không ai biết vì không có metrics
```

**3. Không có reliability — deployment kill production**

```
Deploy version mới:
→ Liveness probe: startup chậm → Kubernetes kill pod
→ Không có PDB → Spot reclaim → 3/3 replica down cùng lúc
→ Không có HPA → 1 replica = 0 replica khi traffic spike
→ Downtime 15 phút, không rollback được vì không ai nhớ version cũ
```

**Ngày hôm nay:** Đóng 3 lỗ hổng này. Từ giờ trở đi, mỗi commit → CI pipeline → auto PR update image tag → ArgoCD tự sync. Mọi pod có metrics, mọi incident có alert, mọi deployment có safety net.

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 CI/CD Pipeline: Tại sao cần workflow đầy đủ?

CI/CD pipeline production-like gồm 6 stage:

```
commit → lint → test → build → scan → push → PR-update

         [CI: Build & Publish]              [CD: GitOps Update]
```

**Tại sao từng stage?**

| Stage | Câu hỏi | Nếu bỏ qua |
|---|---|---|
| `lint` | Code format đúng convention? | PR review chaos, conflict không cần thiết |
| `test` | Logic có pass unit test? | Bug lọt qua CI, CI green nhưng app crash |
| `build` | Image build được không? | Push lên registry rồi mới phát hiện fail |
| `scan` | Image có vulnerability? | CVE known → production bị exploit |
| `push` | Image lên registry? | ArgoCD không pull được → ImagePullBackOff |
| `PR-update` | GitOps repo có update image tag? | ArgoCD không detect thay đổi |

**Không nên gộp tất cả vào 1 job** vì:
- Mỗi stage chạy độc lập (test fail → không build)
- Cache được artifact giữa các stage
- Security scan chạy riêng với quyền hạn chế

### 3.2 GitHub Actions — OIDC vs Long-lived Credentials

**AWS Mode (Mode B) — Dùng OIDC:**

```yaml
# aws/config.yaml trong workflow
- name: Configure AWS credentials via OIDC
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/github-actions-ecr-push
    aws-region: ${{ vars.AWS_REGION }}
    audience: sts.amazonaws.com
```

**Ưu điểm OIDC:**
- Không cần AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
- Token có expiry tự động
- Audit được trong CloudTrail
- GitHub OIDC provider → IAM role trust policy

**Trust Policy cho GitHub Actions IAM Role (least-privilege):**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:$GITHUB_ORG/*",
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      }
    }
  }]
}
```

**GHCR Mode (Mode A) — Dùng GitHub Token:**

```yaml
- name: Login to GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

**Lưu ý GITHUB_TOKEN:**
- Mặc định có quyền ghi trong repo chạy workflow
- Không cần tạo Personal Access Token cho GHCR public
- Hết hạn sau khi workflow kết thúc
- Không dùng cho ECR (cần IAM)

### 3.3 Trivy Image Scanning — CVE trước khi production

```bash
# Scan trước khi push
trivy image --severity HIGH,CRITICAL \
  --exit-code 1 \
  --ignore-unfixed \
  ghcr.io/myorg/api-service:${{ github.sha }}

# Expected: exit-code 1 nếu có HIGH/CRITICAL CVE
# Critical CVE found: CVE-2024-1234 in libssl3 (score: 9.8)
# FAILED
```

**Trivy database update:**

```bash
trivy image --download-db-only  # ~50MB, chạy trước khi scan
# Hoặc dùng aquasecurity/trivy-action tự update
```

**Trivy policies được check:**
- OS packages (apk, deb, rpm)
- Language-specific (npm, pip, gem, go mod)
- Kubernetes manifests (deprecated API, privilege escalation)
- Dockerfile best practices (non-root user, healthcheck)

### 3.4 Auto PR Update Image Tag — GitOps Pattern

Sau khi push image thành công, pipeline tạo PR vào `apps-repo`:

```
apps-repo (GitOps repo)
  └── helm/
      └── api-service/
          └── values.yaml
              image:
                repository: ghcr.io/myorg/api-service
                tag: SHA_GITHUB_CŨ      ← cần update

PR mới:
  values.yaml: SHA_GITUB_CŨ → SHA_GITHUB_MỚI
  Title: "chore(api-service): update image to SHA abc1234"
  Body:  "Built from commit $GITHUB_SHA"
```

**Workflow cụ thể:**

```yaml
- name: Create PR to update image tag
  uses: peter-evans/create-pull-request@v6
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    commit-message: "chore(api-service): update image tag to ${{ github.sha }}"
    title: "chore(api-service): auto-update image to ${{ github.sha }}"
    body: |
      Automated image tag update by CI pipeline.
      - Image: `ghcr.io/${{ vars.GHCR_ORG }}/api-service:${{ github.sha }}`
      - Commit: ${{ github.event.head_commit.url }}
      - Actor: ${{ github.actor }}
    branch: chore/update-api-service-${{ github.sha }}
    base: main
    labels: |
      auto-update
      ci-update
    delete-branch: true
```

**Tại sao dùng PR thay vì trực tiếp push?**

- Review team trước khi ArgoCD sync
- Audit trail trong Git
- Có thể revert bằng `git revert`
- Staging environment: tự động merge sau khi test pass

### 3.5 Observability Stack — Prometheus + Grafana + Loki

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK OVERVIEW                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   scrape    ┌──────────────┐   query   ┌───────────┐ │
│  │Prometheus│◄───────────│ K8s cluster  │           │ Grafana   │ │
│  │(metrics) │            │ (api-service) │──────────►│(dashboard)│ │
│  └──────────┘            └──────────────┘           └───────────┘ │
│                                                                      │
│  ┌──────────┐   collect   ┌──────────────┐   query   ┌───────────┐ │
│  │  Loki    │◄───────────│ Promtail/     │           │ Grafana   │ │
│  │ (logs)   │            │ Fluent Bit    │           │(logs tab) │ │
│  └──────────┘            └──────────────┘           └───────────┘ │
│                                                                      │
│  ┌──────────┐   route    ┌──────────────┐   fire    ┌───────────┐ │
│  │Alertmanager│◄──────────│ Prometheus   │───────────►│ Slack/    │ │
│  │(dedup)   │           │ (alert rules)│           │ PagerDuty │ │
│  └──────────┘            └──────────────┘           └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**Prometheus metrics labels cần có cho mỗi service:**

```yaml
# Kubernetes ServiceMonitor cho api-service
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-service
  namespace: monitoring
  labels:
    release: prometheus  # required by prometheus-operator
spec:
  selector:
    matchLabels:
      app: api-service
  endpoints:
  - port: metrics        # port name trong Service
    path: /metrics
    interval: 15s
```

### 3.6 Readiness Probe vs Liveness Probe

**Readiness probe — "Pod có sẵn sàng nhận traffic không?"**

```yaml
readinessProbe:
  httpGet:
    path: /healthz/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3
  successThreshold: 1
```

- Kubernetes chỉ route traffic vào pod khi readiness pass
- Dùng cho: startup có init logic, dependency chưa sẵn sàng, graceful shutdown
- **Sai lầm phổ biến:** Readiness probe kiểm tra external dependency (Redis) → Redis down → readiness fail → traffic không vào pod nào

**Liveness probe — "Pod có đang stuck không, cần restart không?"**

```yaml
livenessProbe:
  httpGet:
    path: /healthz/live
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
  timeoutSeconds: 3
```

- Restart pod nếu liveness fail
- `initialDelaySeconds` phải > startup time thực tế
- **Sai lầm phổ biến:** `initialDelaySeconds: 0` → startup 30s → Kubernetes kill pod ngay

**Startup probe — cho application có startup lâu:**

```yaml
startupProbe:
  httpGet:
    path: /healthz/ready
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
  # Cho phép startup tối đa 30 * 10 = 300s = 5 phút
```

### 3.7 Resource Requests vs Limits

```
┌─────────────────────────────────────────────────────────────┐
│                  NODE MEMORY ALLOCATION                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Node: 4GB RAM                                               │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Pod A    │ │ Pod B    │ │ Pod C    │ │ system   │        │
│  │ req:500M │ │ req:500M │ │ req:500M │ │          │        │
│  │ limit:1G │ │ limit:1G │ │ limit:1G │ │ ~500MB   │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│                                                              │
│  Total requests: 1.5GB  →  Scheduling decisions dựa vào đây  │
│  Total limits:   3GB     →  OOMKill xảy ra nếu vượt quá      │
│                                                              │
│  Unbounded: 4GB - 1.5GB = 2.5GB → pod có thể burst          │
└─────────────────────────────────────────────────────────────┘
```

**OOMKilled — nguyên nhân số 1 của production incident:**

```yaml
resources:
  requests:
    memory: "256Mi"   # scheduling, cost reporting
    cpu: "100m"        # 0.1 CPU core
  limits:
    memory: "512Mi"    # HARD CAP → OOMKilled nếu vượt
    cpu: "500m"        # throttling nếu vượt (>100m)
```

**Best practice resource ratio:**

| Workload | Requests:Limits ratio | Lý do |
|---|---|---|
| API service | 1:1 hoặc 1:2 | CPU có thể burst, memory thường stable |
| Java/Golang | 1:1 (CPU) | GC overhead → CPU spike |
| Redis/DB | 1:1 | Không burst, predictable |
| Worker batch | 2:1 | Thường idle, burst khi process |

### 3.8 HPA — Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2          # NEVER go below 2 in production
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70   # scale up when avg CPU > 70%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0   # immediate scale up
      policies:
      - type: Percent
        value: 100                     # max x2 pod count per minute
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # wait 5 min before scale down
      policies:
      - type: Pods
        value: 1                      # remove max 1 pod per minute
        periodSeconds: 60
```

**Nguyên tắc HPA:**

- `minReplicas: 1` = có ngày bạn sẽ gặp incident vì `minReplicas: 1` + scale-to-zero không phải HPA
- Stabilization window ngăn thrashing (scale up/down liên tục)
- CPU target `70%` = đủ headroom cho spike mà không scale quá sớm

### 3.9 PodDisruptionBudget (PDB)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
spec:
  # Dùng minAvailable HOẶC maxUnavailable, KHÔNG dùng cả hai
  minAvailable: 1        # luôn giữ ít nhất 1 replica
  selector:
    matchLabels:
      app: api-service
---
# Hoặc dùng maxUnavailable (tốt hơn cho replicas >= 3)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
spec:
  maxUnavailable: 1      # không quá 1 pod unavailable cùng lúc
  selector:
    matchLabels:
      app: api-service
```

**Khi nào PDB được trigger?**

- Node drain (kubectl drain)
- Cluster upgrade ( cordon + drain)
- Spot instance reclaim
- Pod eviction do resource pressure

**PDB không ngăn:**
- Pod crash (evict không qua eviction API)
- Node failure không có drain
- OOMKilled

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 GitHub Actions vs Tekton vs ArgoCD Image Updater

| Tiêu chí | GitHub Actions | Tekton | ArgoCD Image Updater |
|---|---|---|---|
| Setup | 5 phút | 30 phút | 15 phút |
| Scope | Build + Push | Build + Push + Deploy | Auto-update image tag |
| Native GitOps | Không (cần PR) | Không (cần ArgoCD) | Có |
| PR-based update | ✅ Native | ✅ Qua ArgoCD | ❌ Direct push |
| Cost | Miễn phí (2000 phút/tháng public repo) | Self-hosted | Miễn phí |
| Security | OIDC/GITHUB_TOKEN | ServiceAccount | ArgoCD RBAC |

**Recommendation capstone:**
- Mode A: GitHub Actions + `peter-evans/create-pull-request` (PR-based, production-like)
- Mode B: GitHub Actions OIDC + ECR (same pattern, chỉ đổi registry)

### 4.2 Trivy vs Grype vs Snyk vs Checkov

| Scanner | Type | Database | Severity | CI Speed | Cost |
|---|---|---|---|---|---|
| Trivy | Container + IaC | Native (vulndb) | CVE | ~2-3 min | Miễn phí |
| Grype | Container | Grype DB | CVE | ~1-2 min | Miễn phí |
| Snyk | Container + SAST + SCA | Proprietary | CVE + Vuln | ~3-5 min | Paid |
| Checkov | IaC | Native | IaC misconfig | ~30s | Miễn phí (core) |

**Chiến lược production:**
- Trivy scan image (CI): pass → push
- Checkov scan YAML (CI): pass → commit
- Snyk monitor: post-deploy (separate from CI gate)

**Trade-off: Block hay warn?**

```yaml
# Block deployment nếu có CRITICAL CVE
- name: Scan image
  run: |
    trivy image --severity CRITICAL \
      --exit-code 1 \
      --ignore-unfixed \
      $IMAGE_URL:$IMAGE_TAG

# Warn nhưng không block (staging/dev)
- name: Scan image
  run: |
    trivy image --severity CRITICAL \
      --exit-code 0 \
      --ignore-unfixed \
      $IMAGE_URL:$IMAGE_TAG
    # Image passed scan
```

### 4.3 Prometheus Architecture: Serverless vs Persistent

**Prometheus Server (persistent, mode B AWS):**

```
Prometheus server (Deployment/StatefulSet)
  → scrape metrics từ cluster
  → local TSDB (EBS-backed cho persistence)
  → retention: 15 days default
  → Alertmanager sidecar hoặc separate deployment
```

**Prometheus Agent (serverless, mode A local):**

```
Prometheus Agent (Deployment)
  → scrape metrics
  → remote_write → Thanos/ Cortex/ Mimir (long-term storage)
  → Lightweight (~50MB vs 200MB)
```

**Trade-off:**

| Mode | Storage | Scalability | Cost | Setup |
|---|---|---|---|---|
| Prometheus server | Local TSDB (EBS) | Single Prometheus limit 100K targets | ~$10-20 EBS | Simple |
| Thanos/Mimir | Object Storage (S3) | Unlimited scale | ~$5-10 S3 | Complex |

**Capstone recommendation:**
- Mode A: Prometheus server + local TSDB (không cần Thanos, retention 15 ngày đủ cho dev)
- Mode B: Prometheus + remote_write → Thanos sidecar (Grafana Cloud hoặc self-hosted)

### 4.4 Grafana Dashboard: Import vs Build vs Provision

| Approach | Khi nào | Ưu điểm | Nhược điểm |
|---|---|---|---|
| Import dashboard JSON | Quick start | 5 phút có dashboard | Không version control |
| Build dashboard manually | Một vài panels | Full control | Tốn thời gian |
| Provision via ConfigMap/Grafana Operator | Production | Version control, GitOps | Setup phức tạp hơn |

**Capstone recommendation:**
- Provision Grafana dashboard qua ConfigMap (GitOps-compatible)
- Import community dashboard (16042, 18032) cho quick wins

### 4.5 Alert Fatigue — Chiến lược Alerting hiệu quả

```
Số alert mà team nhận mỗi ngày:
  0-5   → có thể bỏ qua, hoặc channel sai
  5-20  → healthy, team phản hồi tất cả
  20-50 → alert fatigue bắt đầu, team bỏ qua
  50+   → alerting không có giá trị
```

**Phân loại alert:**

| Severity | Response | Example | Channel |
|---|---|---|---|
| P1/Critical | 5 phút | API down, data loss | PagerDuty (wake-up) |
| P2/High | 30 phút | High error rate >5%, latency >2s | Slack #incidents |
| P3/Medium | 2 giờ | Disk >80%, CPU >90% >10min | Slack #alerts |
| P4/Low | Next business day | Certificate expiring >7 days | Ticket |

**Alert quality checklist:**

```yaml
# ✅ Alert tốt:
# - Có action rõ ràng: "restart pod" hoặc "scale up"
# - Có context: "api-service pod count = 1/2"
# - Có dashboard link
# - Không alert khi system degraded nhưng still serving

# ❌ Alert xấu:
# - "Pod CPU high" → làm gì? Restart? Scale?
# - "Disk usage > 80%" → cluster nào? Từ bao giờ?
# - "Container restart" → normal, không alert
```

### 4.6 HPA + PDB + Spot — Edge Cases

**Case 1: Spot reclaim + PDB = deadlock**

```
Node có 3 replicas api-service (minAvailable: 3)
Spot reclaim → Kubernetes cần evict 1 pod
PDB: minAvailable=3 → không pod nào được evict
→ Node termination bị block
→ Spot replacement không schedule được
```

**Fix:** `minAvailable: ceil(replicas * 0.5)` hoặc dùng `maxUnavailable: 1`

**Case 2: HPA scale-down + Spot reclaim = cascading failure**

```
Current: 5 replicas
HPA scale down → 2 replicas (stabilization: 5min)
Spot reclaim → 1 pod evicted
Chỉ còn 1 replica đang serve traffic → OOMKilled → Downtime
```

**Fix:**
- `minReplicas: 2` (never go below 2)
- PDB `minAvailable: 1` (cho phép 1 pod unavailable)
- `stabilizationWindowSeconds: 300` (5 phút chờ scale down)

**Case 3: HPA thrashing**

```
CPU spike → scale 2 → 4 → 8
Load drop → scale 8 → 4 → 2
Load spike → scale 2 → 4 → 8
→ Continuous scaling → resource pressure → crash
```

**Fix:**
```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0    # immediate
  scaleDown:
    stabilizationWindowSeconds: 300  # wait 5 min before scale down
```

### 4.7 Best Solution Per Context

```
┌────────────────────────────────────────────────────────────────┐
│ Context                   │ Recommended Setup                  │
├────────────────────────────┼───────────────────────────────────┤
│ Học tập cá nhân           │ GH Actions + GHCR + Trivy free     │
│ Startup MVP               │ GitHub Actions + ECR + Trivy       │
│ Enterprise                │ GitHub Actions + ECR + Snyk + OPA  │
│ Bank / regulated          │ Tekton + Vault + Snyk + approval   │
├────────────────────────────┼───────────────────────────────────┤
│ Observability local       │ kube-prometheus-stack + Loki       │
│ Observability production  │ Prometheus + Thanos + Grafana Cloud│
├────────────────────────────┼───────────────────────────────────┤
│ HPA + Spot (startup)     │ minReplicas:2 + PDB + stabilization │
│ HPA + Enterprise         │ Karpenter + VPA + PDB               │
└────────────────────────────┴───────────────────────────────────┘
```

### 4.8 Common Pitfalls

| Pitfall | Hậu quả | Fix |
|---|---|---|
| Không có OIDC cho AWS | Long-lived key trong GitHub secrets | `aws-actions/configure-aws-credentials@v4` + OIDC |
| `latest` tag trong production | Không rollback được, không biết version | Immutable tag = git SHA |
| Push image không scan | CVE lọt vào production | Trivy gate trước push |
| Không có `initialDelaySeconds` | Liveness kill pod chưa start xong | > startup time thực tế |
| Memory limit = request | No burst, resource waste | Limit > request (1.5-2x) |
| `minReplicas: 1` | Single point of failure | `minReplicas: 2` minimum |
| PDB `minAvailable` = replicas | Deadlock khi spot reclaim | `ceil(replicas/2)` |
| Alert cho container restart | Alert fatigue, normal event | Chỉ alert khi restart count > threshold |
| Grafana dashboard không provision | Manual setup, lost on reinstall | ConfigMap + Grafana Operator |

---

## 5. Hands-on Lab — 60 phút

### Prerequisites

**Mode A (default — $0):**
- Kind cluster đang chạy từ Day 30
- `kubectl` context: `kind-capstone-dev`
- GHCR access (GITHUB_TOKEN)
- `capstone-platform/` và `capstone-apps/` repo tồn tại

**Mode B (có cost ~$115-165/tháng):**
- EKS cluster đang chạy từ Day 30
- ECR repo đã tạo từ Day 30
- IAM OIDC role cho GitHub Actions

**Chọn mode:**

```bash
# Kiểm tra cluster đang chạy
kubectl get nodes

# Mode A → dùng GHCR
export REGISTRY="ghcr.io/$GITHUB_ORG"

# Mode B → dùng ECR
export REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

---

### Part A: GitHub Actions CI/CD Pipeline

**Step 1: Tạo GitHub Actions workflow file**

```bash
mkdir -p capstone-apps/.github/workflows
```

```yaml
# capstone-apps/.github/workflows/ci-cd.yaml
name: CI/CD - Build, Scan, and Push Image

on:
  push:
    branches:
      - main
      - 'release/**'
  pull_request:
    branches:
      - main
  workflow_dispatch:  # Manual trigger

env:
  REGISTRY: ${{ vars.ECR_REGISTRY || 'ghcr.io' }}
  IMAGE_NAME: ${{ github.event.repository.name }}
  GITHUB_SHA_SHORT: ${{ github.sha }}
  ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY || '' }}

jobs:
  # ────────────────────────────────────────────────────────────────
  # JOB 1: Lint & Test (runs in parallel với job khác nếu tách)
  # ────────────────────────────────────────────────────────────────
  lint-and-test:
    name: Lint and Unit Test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          cache: true

      - name: Run go fmt
        run: |
          go fmt ./...
          git diff --exit-code || {
            echo "ERROR: code not formatted. Run 'go fmt ./...' before committing."
            exit 1
          }

      - name: Run go vet
        run: go vet ./...

      - name: Run unit tests
        run: |
          go test -v -race -coverprofile=coverage.out ./...
          #覆盖率 ảnh hưởng PR status, không block push
          #Chỉ warn nếu coverage drop

      - name: Run Trivy config scan (IaC)
        uses: aquasecurity/trivy-action@master
        if: github.event_name == 'pull_request'
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
        continue-on-error: true  # Don't block, just report

  # ────────────────────────────────────────────────────────────────
  # JOB 2: Build, Scan, Push Image
  # ────────────────────────────────────────────────────────────────
  build-and-push:
    name: Build and Push Image
    runs-on: ubuntu-latest
    needs: lint-and-test    # Chỉ build nếu lint+test pass
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    permissions:
      id-token: write       # Required for OIDC (AWS)
      contents: read
      packages: write       # Required for GHCR

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # ── Build metadata ──
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=,suffix=,format=short
            type=ref,event=branch
            type=semver,pattern={{version}}

      # ── Mode A: GHCR Login ──
      - name: Login to GHCR
        if: env.ECR_REPOSITORY == ''
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # ── Mode B: AWS ECR Login via OIDC ──
      - name: Configure AWS credentials via OIDC
        if: env.ECR_REPOSITORY != ''
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/github-actions-ecr-push
          aws-region: ${{ vars.AWS_REGION }}
          audience: sts.amazonaws.com

      - name: Login to Amazon ECR
        if: env.ECR_REPOSITORY != ''
        uses: aws-actions/amazon-ecr-login@v2

      # ── Build image with layer cache ──
      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha          # GitHub Actions cache
          cache-to: type=gha,mode=max   # Cache all layers
          provenance: true               # SBOM / provenance
          sbom: true                    # Software Bill of Materials

      # ── Vulnerability scan (MUST pass before push) ──
      - name: Scan image with Trivy
        if: github.event_name != 'pull_request'
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'   # FAIL nếu có CRITICAL/HIGH CVE
          ignore-unfixed: true

      - name: Upload Trivy scan results to Security tab
        if: github.event_name != 'pull_request'
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

      # ── Upload image digest as artifact (for other jobs) ──
      - name: Upload image info
        if: github.event_name != 'pull_request'
        uses: actions/upload-artifact@v4
        with:
          name: image-info
          path: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          retention-days: 1

  # ────────────────────────────────────────────────────────────────
  # JOB 3: Update GitOps Repo (PR-based image tag update)
  # ────────────────────────────────────────────────────────────────
  update-gitops:
    name: Update GitOps Repo (PR)
    runs-on: ubuntu-latest
    needs: build-and-push
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout apps repo
        uses: actions/checkout@v4
        with:
          repository: ${{ vars.APPS_REPO || github.repository }}
          path: apps-repo
          token: ${{ secrets.GH_PAT }}   # Need PAT with repo scope

      - name: Determine target values file
        id: target
        run: |
          # Mode A: GHCR → values.yaml
          # Mode B: ECR → values-aws.yaml hoặc values.yaml
          TARGET_FILE="apps-repo/helm/api-service/values.yaml"
          if [ ! -f "$TARGET_FILE" ]; then
            TARGET_FILE="apps-repo/k8s/api-service/values.yaml"
          fi
          echo "file=$TARGET_FILE" >> $GITHUB_OUTPUT

      - name: Update image tag in values file
        run: |
          TARGET_FILE="${{ steps.target.outputs.file }}"
          NEW_IMAGE="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}"

          echo "Updating image tag in $TARGET_FILE"
          echo "New image: $NEW_IMAGE"

          # sed thay đổi tag (tùy format values.yaml)
          # Method 1: Dùng yq nếu có
          if command -v yq &> /dev/null; then
            yq -i ".image.tag = \"${{ github.sha }}\"" "$TARGET_FILE"
          else
            # Method 2: sed fallback
            sed -i "s|image:.*|$IMAGE_NAME|; s|tag:.*|${{ github.sha }}|" "$TARGET_FILE"
          fi

          cat "$TARGET_FILE" | grep -A2 "image:"

      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GH_PAT }}
          commit-message: "chore(${{ env.IMAGE_NAME }}): update image to ${{ github.sha }}"
          title: "chore(${{ env.IMAGE_NAME }}): auto-update image tag"
          body: |
            **Automated PR** — Image tag update by CI pipeline

            | Field | Value |
            |-------|-------|
            | Image | `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}` |
            | Tag   | `${{ github.sha }}` |
            | Commit | [${{ github.sha }}](${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}) |
            | Actor | ${{ github.actor }} |
            | Pipeline | [${{ github.run_id }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}) |

            ArgoCD will detect this PR and show OutOfSync. Merge to trigger sync.
          branch: chore/update-${{ env.IMAGE_NAME }}-${{ github.sha }}
          base: main
          labels: |
            auto-update
            ci-update
            skip-ci
          delete-branch: true
          path: apps-repo
```

**Expected output sau khi push:**

```
Run Lint and Unit Test
  ✓ go fmt (no changes needed)
  ✓ go vet (no issues)
  ✓ go test -v ./... (all passed)

Run Build and Push Image
  ✓ Set up Docker Buildx
  ✓ GHCR Login (logged in to ghcr.io)
  ✓ Build and push image
    ghcr.io/myorg/api-service:a1b2c3d → pushed
  ✓ Scan image with Trivy
    CRITICAL: 0, HIGH: 0 → PASS

Run Update GitOps Repo (PR)
  ✓ Checkout apps repo
  ✓ Update image tag in values.yaml
  ✓ Create Pull Request
    https://github.com/myorg/capstone-apps/pull/42
```

---

### Part B: PrometheusRule + Grafana Dashboard

**Step 2: Tạo PrometheusRule manifest**

```bash
mkdir -p capstone-platform/manifests/monitoring
```

```yaml
# capstone-platform/manifests/monitoring/api-service-prometheusrule.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: api-service-alerts
  namespace: monitoring
  labels:
    app: api-service
    prometheus: prometheus
    role: alert-rules
spec:
  groups:
  - name: api-service.availability
    interval: 30s
    rules:
    # ── Pod Down Alert ──────────────────────────────────────────
    - alert: APIServicePodDown
      expr: |
        kube_pod_status_phase{phase="Running", app="api-service"} == 0
      for: 2m
      labels:
        severity: critical
        team: platform
      annotations:
        summary: "api-service pod is not running"
        description: "Pod {{ $labels.namespace }}/{{ $labels.pod }} has been down for more than 2 minutes."
        runbook_url: "https://runbook.example.com/api-service-pod-down"
        dashboard_url: "{{ $labels.dashboard_url }}"

    # ── High Error Rate ─────────────────────────────────────────
    - alert: APIServiceHighErrorRate
      expr: |
        (
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m]))
        ) > 0.05
      for: 3m
      labels:
        severity: high
        team: backend
      annotations:
        summary: "api-service error rate > 5%"
        description: "API service 5xx error rate is {{ $value | humanizePercentage }} (threshold: 5%)"
        grafana_dashboard: "https://grafana.example.com/d/api-service"

    # ── High Latency ────────────────────────────────────────────
    - alert: APIServiceHighLatency
      expr: |
        histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
        > 2
      for: 5m
      labels:
        severity: medium
        team: backend
      annotations:
        summary: "api-service p95 latency > 2s"
        description: "API service p95 latency is {{ $value | humanizeDuration }} (threshold: 2s)"

    # ── Memory Pressure ─────────────────────────────────────────
    - alert: APIServiceMemoryPressure
      expr: |
        (
          kube_pod_container_resource_requests_memory_bytes{app="api-service"}
          /
          kube_pod_container_resource_limits_memory_bytes{app="api-service"}
        ) > 0.9
      for: 5m
      labels:
        severity: warning
        team: backend
      annotations:
        summary: "api-service pod memory close to limit"
        description: "Memory usage is at {{ $value | humanizePercentage }} of limit. Risk of OOMKilled."

  - name: api-service.resources
    interval: 60s
    rules:
    # ── CPU Throttling ───────────────────────────────────────────
    - alert: APIServiceCPUThrottling
      expr: |
        sum(rate(container_cpu_cfs_throttled_seconds_total{app="api-service"}[5m]))
        /
        sum(rate(container_cpu_cfs_periods_total{app="api-service"}[5m]))
        > 0.5
      for: 10m
      labels:
        severity: warning
        team: backend
      annotations:
        summary: "api-service CPU throttling > 50%"
        description: "Container CPU throttling is high. Consider increasing CPU limit."

    # ── OOMKilled History ────────────────────────────────────────
    - alert: APIServiceOOMKilledHistory
      expr: |
        increase(kube_pod_container_status_restarts_total{app="api-service", reason="OOMKilled"}[1h]) > 0
      for: 1m
      labels:
        severity: high
        team: platform
      annotations:
        summary: "api-service pod was OOMKilled in the last hour"
        description: "Pod has been OOMKilled. Current memory limit may be too low."
```

**Step 3: Apply PrometheusRule**

```bash
kubectl apply -f capstone-platform/manifests/monitoring/api-service-prometheusrule.yaml

# Expected:
# prometheusrule.monitoring.coreos.com/api-service-alerts created

# Verify
kubectl get prometheusrule -n monitoring

# Check rules loaded
kubectl describe prometheusrule api-service-alerts -n monitoring
```

**Step 4: Tạo Grafana dashboard ConfigMap**

```yaml
# capstone-platform/manifests/monitoring/grafana-dashboard-api-service.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboard-api-service
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
    app: api-service
data:
  api-service-dashboard.json: |
    {
      "title": "API Service Overview",
      "uid": "api-service-001",
      "version": 1,
      "panels": [
        {
          "id": 1,
          "title": "Request Rate (RPS)",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
          "targets": [
            {
              "expr": "sum(rate(http_requests_total{app=\"api-service\"}[1m])) by (status)",
              "legendFormat": "{{status}}"
            }
          ]
        },
        {
          "id": 2,
          "title": "Error Rate (%)",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
          "targets": [
            {
              "expr": "100 * sum(rate(http_requests_total{status=~\"5..\",app=\"api-service\"}[5m])) / sum(rate(http_requests_total{app=\"api-service\"}[5m]))",
              "legendFormat": "5xx Error Rate"
            }
          ]
        },
        {
          "id": 3,
          "title": "P95 Latency (seconds)",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
          "targets": [
            {
              "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app=\"api-service\"}[5m])) by (le))",
              "legendFormat": "P95"
            },
            {
              "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app=\"api-service\"}[5m])) by (le))",
              "legendFormat": "P99"
            }
          ]
        },
        {
          "id": 4,
          "title": "CPU Usage vs Limit",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
          "targets": [
            {
              "expr": "sum(rate(container_cpu_usage_seconds_total{app=\"api-service\"}[5m])) by (pod)",
              "legendFormat": "{{pod}} usage"
            },
            {
              "expr": "kube_pod_container_resource_limits_cpu_cores{app=\"api-service\"}",
              "legendFormat": "Limit"
            }
          ]
        },
        {
          "id": 5,
          "title": "Memory Usage vs Limit",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
          "targets": [
            {
              "expr": "sum(container_memory_working_set_bytes{app=\"api-service\"}) by (pod) / 1024 / 1024",
              "legendFormat": "{{pod}} (MiB)"
            },
            {
              "expr": "kube_pod_container_resource_limits_memory_bytes{app=\"api-service\"} / 1024 / 1024",
              "legendFormat": "Limit (MiB)"
            }
          ]
        },
        {
          "id": 6,
          "title": "Pod Replica Count",
          "type": "timeseries",
          "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
          "targets": [
            {
              "expr": "kube_deployment_spec_replicas{app=\"api-service\"}",
              "legendFormat": "Desired"
            },
            {
              "expr": "kube_deployment_status_replicas_available{app=\"api-service\"}",
              "legendFormat": "Available"
            },
            {
              "expr": "kube_pod_status_phase{app=\"api-service\",phase=\"Running\"}",
              "legendFormat": "Running"
            }
          ]
        }
      ],
      "refresh": "30s",
      "time": {"from": "now-1h", "to": "now"},
      "templating": {
        "list": [
          {
            "name": "namespace",
            "type": "constant",
            "query": "default"
          }
        ]
      }
    }
```

**Step 5: Apply Grafana dashboard**

```bash
kubectl apply -f capstone-platform/manifests/monitoring/grafana-dashboard-api-service.yaml

# Verify dashboard loaded
kubectl get configmap -n monitoring -l grafana_dashboard=1
```

---

### Part C: Reliability Manifests

**Step 6: Tạo HPA + PDB + Probes manifest**

```yaml
# capstone-platform/manifests/reliability/api-service-reliability.yaml
---
# HorizontalPodAutoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60

---
# PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
  namespace: default
spec:
  # Cho replicas=2: cho phép 1 pod unavailable (tức 50% down)
  # Cho replicas=3+: dùng maxUnavailable: 1 (bảo vệ 66% uptime)
  minAvailable: 1
  selector:
    matchLabels:
      app: api-service
---
# Updated Deployment with probes + resources
# (Thêm vào Deployment đã có từ Day 33)
# api-service deployment (fragment - merge với existing)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  namespace: default
  labels:
    app: api-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      # Pod Disruption Budget protection
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: api-service
      containers:
      - name: api-service
        # Immutable image tag from CI. Do not use latest in prod/staging.
        image: ghcr.io/myorg/api-service:a1b2c3d
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090
          protocol: TCP

        # ── Readiness Probe ─────────────────────────────────────
        readinessProbe:
          httpGet:
            path: /healthz/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 3
          successThreshold: 1
          timeoutSeconds: 3

        # ── Liveness Probe ──────────────────────────────────────
        livenessProbe:
          httpGet:
            path: /healthz/live
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
          failureThreshold: 3
          timeoutSeconds: 3

        # ── Startup Probe (nếu startup lâu) ─────────────────────
        # startupProbe:
        #   httpGet:
        #     path: /healthz/ready
        #     port: 8080
        #   failureThreshold: 30
        #   periodSeconds: 10

        # ── Resources ────────────────────────────────────────────
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi

        # ── Security context ────────────────────────────────────
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL

        # ── Container security context (additional) ─────────────
        # (add to container spec, not spec.template.spec)
        # readOnlyRootFilesystem: true → cần writable tmp mount
        volumeMounts:
        - name: tmp
          mountPath: /tmp

      volumes:
      - name: tmp
        emptyDir: {}

---
# ServiceMonitor (scraping by Prometheus)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-service
  namespace: monitoring
  labels:
    release: prometheus
    app: api-service
spec:
  selector:
    matchLabels:
      app: api-service
  endpoints:
  - port: metrics
    path: /metrics
    interval: 15s
    scrapeTimeout: 10s
```

**Step 7: Apply reliability manifests**

```bash
kubectl apply -f capstone-platform/manifests/reliability/api-service-reliability.yaml

# Expected:
# horizontalpodautoscaler.autoscaling/api-service-hpa created
# poddisruptionbudget.policy/api-service-pdb created
# deployment.apps/api-service configured
# servicemonitor.monitoring.coreos.com/api-service created

# Verify HPA
kubectl get hpa

# Expected:
# NAME              REFERENCE              TARGETS   MINPODS   MAXPODS   REPLICAS
# api-service-hpa   Deployment/api-service   5%/70%   2         10        3

# Verify PDB
kubectl get pdb

# Expected:
# NAME              MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS
# api-service-pdb    1              N/A               2

# Verify pods
kubectl get pods -l app=api-service -o wide

# Expected:
# NAME                          READY   STATUS    RESTARTS   AGE   IP
# api-service-7d8f9b-xk2p9     1/1     Running   0          2m    10.244.1.23
# api-service-7d8f9b-yz4mn     1/1     Running   0          2m    10.244.2.15
# api-service-7d8f9b-9q7rs     1/1     Running   0          2m    10.244.0.31

# Check probe status
kubectl describe pod -l app=api-service | grep -A5 "Readiness|Liveness"
```

---

### Part D: Verify End-to-End Flow

**Step 8: Verify ArgoCD auto-sync (nếu đã cài từ Day 32)**

```bash
# ArgoCD sync nếu auto-sync chưa bật
argocd app sync api-service

# Kiểm tra health
argocd app get api-service

# Expected:
# Name:               api-service
# Sync status:        Synced
# Health status:      Healthy
# Repository:         https://github.com/myorg/capstone-apps
# Revision:           abc1234 (HEAD)
```

**Step 9: Test probe failure scenario**

```bash
# Simulate readiness probe failure (test liveness)
kubectl exec -it deploy/api-service -- sh -c 'kill 1' &
sleep 20
kubectl get pods -l app=api-service

# Expected: pod restart, không downtime (replicas=3 → 2 available → 3rd pod ready)
```

---

### Troubleshooting

**Lỗi: `ERROR: NoCredentialProviders` khi push ECR**

```
Error: Cannot perform EC2 DescribeRegions operation
→ Thiếu IAM permission cho ECR push
→ Kiểm tra: IAM role có trust policy đúng cho GitHub OIDC?
```

Fix: Thêm IAM permission policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/*"
    }
  ]
}
```

**Lỗi: Trivy exit code 1 nhưng muốn ignore một số CVE**

```bash
# Tạo .trivyignore file
echo "CVE-2024-1234" > .trivyignore
echo "CVE-2024-5678" >> .trivyignore

# Sau đó scan lại
trivy image --ignore-unfixed --ignorefile .trivyignore \
  --exit-code 1 --severity CRITICAL ghcr.io/myorg/api-service:$SHA
```

**Lỗi: HPA không scale up với Spot node**

```
kubectl describe hpa api-service-hpa
→ Events: "Unable to scale: 0 pod replicas available for scale target"
→ Không có node đủ resource
→ Fix: kiểm tra node allocatable, Spot reclaim
```

**Lỗi: Grafana dashboard không load**

```bash
# Kiểm tra ConfigMap label
kubectl get configmap -n monitoring -l grafana_dashboard=1

# Nếu label đúng nhưng dashboard không hiện:
# Restart Grafana pod
kubectl rollout restart deployment/grafana -n monitoring
```

**Lỗi: PrometheusRule không apply**

```bash
# Check validation
kubectl apply -f api-service-prometheusrule.yaml --validate=true

# Check CRD exists
kubectl get crd prometheusrules.monitoring.coreos.com

# Verify rule syntax
kubectl get prometheusrule api-service-alerts -n monitoring -o yaml
```

---

### Cleanup

**Mode B (AWS) — Các resource phát sinh chi phí:**

```bash
# Xóa ECR images (nếu không cần)
aws ecr batch-delete-image \
  --repository-name capstone/api-service \
  --image-ids imageTag=sha1234,imageTag=sha5678

# ECR repository: không xóa (dùng lại Day 35)
# Prometheus/Grafana: có thể keep cho Day 35
```

**Mode A (Local):** Không có chi phí. Kind cluster giữ lại cho Day 35.

---

## 6. Kiểm tra hiểu bài

### Câu hỏi lý thuyết

**Câu 1:** Tại sao GitHub Actions pipeline nên tách job `lint-and-test` và `build-and-push`? Khi nào nên gộp?

**Câu 2:** OIDC-based authentication cho AWS có ưu điểm gì so với long-lived access key? Trust policy cần những điều kiện gì?

**Câu 3:** Phân biệt readiness probe và liveness probe. Khi nào nên dùng startup probe thay vì chỉ liveness?

**Câu 4:** Nếu memory limit = 256Mi và request = 128Mi, điều gì xảy ra khi pod dùng 200Mi? Khi nào OOMKilled xảy ra?

**Câu 5:** HPA `minReplicas: 1` có vấn đề gì trong production? Thiết kế đúng cho Spot instance environment?

### Bài tập thực hành

**Bài 1:** Sửa GitHub Actions workflow để chỉ scan image và block push nếu có CRITICAL CVE (không block HIGH).

**Bài 2:** Viết thêm alert cho worker-service: khi queue depth > 1000 messages trong 5 phút.

**Bài 3:** Thiết kế HPA + PDB cho frontend-service (stateless, replicas=5) — đảm bảo Spot reclaim không gây downtime.

**Bài 4:** Thêm `topologySpreadConstraints` vào Deployment để spread replicas ra 3 availability zones.

---

## 7. Tóm tắt cuối ngày

### 3-5 ý quan trọng nhất

1. **CI/CD pipeline phải có gate trước push** — Trivy scan CRITICAL CVE exit-code 1 → không push → không deploy
2. **OIDC thay long-lived key** — Không bao giờ lưu AWS_ACCESS_KEY trong GitHub secrets cho pipeline
3. **PR-based image tag update** — Mỗi push → PR → ArgoCD OutOfSync → merge → sync (audit trail + review)
4. **Probe + resource = reliability baseline** — Không có probe/resource → production incident không tránh được
5. **minReplicas: 2 + PDB + HPA stabilization** — Combo bắt buộc cho Spot environment

### Output đã tạo ra

- GitHub Actions workflow `ci-cd.yaml` — 3 jobs: lint+test → build+scan+push → PR update
- PrometheusRule manifest — 5 alert rules (PodDown, ErrorRate, Latency, MemoryPressure, CPUThrottling)
- Grafana dashboard ConfigMap — 6 panels (RPS, ErrorRate, Latency, CPU, Memory, Replicas)
- Reliability manifests — HPA + PDB + probes + resources + topologySpreadConstraints + ServiceMonitor

### Kiến thức chuẩn bị cho Day 35

Day 35 — Disaster Recovery, Final Demo, Runbook, Retrospective:
- Simulate mất cluster → ArgoCD restore
- Simulate bad deployment → Rollback
- Export runbook cho toàn bộ platform
- Retrospective: cái gì production-ready, cái gì simulation, next steps

---

## 8. Tham khảo thêm

- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Prometheus Operator: PrometheusRule](https://prometheus-operator.dev/)
- [Kubernetes HPA Algorithm](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Kubernetes PDB](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request)
- [ArgoCD Image Updater (alternative approach)](https://argocd-image-updater.readthedocs.io/)
