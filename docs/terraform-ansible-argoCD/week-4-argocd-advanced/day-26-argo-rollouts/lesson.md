# Day 26 — Argo Rollouts, Progressive Delivery

> **Rollout CRD thay thế Deployment. Strategy canary/blue-green thay thế RollingUpdate.
> AnalysisTemplate = automated promotion/rollback dựa trên metrics.**

**Module**: ArgoCD Advanced (Week 4)
**Day**: 26 / 35
**Topic**: Argo Rollouts, Progressive Delivery
**Prerequisite**: Day 17 (ArgoCD core), Day 24 (sync waves & hooks), Day 25 (ESO/RBAC)
**Duration**: 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
**Output**: Orders app với canary deployment, AnalysisTemplate Prometheus, rollback flow

---

## 1. Muc tieu ngay hoc

- Phan biet 3 strategy deployment: RollingUpdate (Kubernetes), Blue-Green, Canary
- Cau hinh `Rollout` CRD thay the `Deployment` voi canary strategy (steps 25/50/75/100%)
- Viet `AnalysisTemplate` + `AnalysisRun` kiem tra Prometheus metrics truoc promotion
- Thuc hien abort + rollback khi version moi co van de
- Danh gia trade-off giua Deployment thuong, Argo Rollouts, va service mesh rollout

---

## 2. Boi canh thuc te

### Chuyen that xay ra khi khong co progressive delivery

```
Pain: Phat hien version moi co bug chi sau khi 100% traffic da sang
─────────────────────────────────────────────────────────────
09:00  Deploy v2.1
09:00  Kubernetes RollingUpdate: 25% pod moi -> 50% -> 100%
09:01  v2.1 co bug: /api/orders return 500
09:01  User bi 500 lien tuc (10.000 request)
09:05  Nhan vien ops phat hien
09:10  Rollback: thay doi image tag -> RollingUpdate lai lan nua
09:15  He thong on dinh

Thoi gian incident: 14 phut, 10.000 request loi
```

### Tai sao canary giai quyet van de

```
Canary = cho 1 phan nho traffic sang version moi truoc
─────────────────────────────────────────────────────────────
09:00  Deploy v2.1
09:00  Canary 5%: 1 pod v2.1, 19 pod v2.0
09:01  v2.1 co bug: chi 5% user bi 500
09:02  Alert: success-rate drop 5%
09:02  Ops abort rollout -> traffic 0% v2.1
09:03  He thong on dinh

Thoi gian incident: 3 phut, ~500 request loi
Blast radius: 5% thay vi 100%
```

### Muc tieu Day 26

Build progressive delivery cho orders app: canary 25% -> 50% -> 75% -> 100%, abort khi metrics xau, rollback nhanh.

---

## 3. Kien thuc nen tang (~30 phut)

### 3.1 3 Strategy Deployment — So sanh

```
Deployment Strategy Comparison
==============================

Strategy 1 — RollingUpdate (Kubernetes native)
─────────────────────────────────────────────
Timeline:  [v2 pod 1] [v2 pod 2] [v2 pod 3] ... [v1 pods replaced]
Traffic:   v1 100% -> v1 75% -> v1 50% -> v1 0% -> v2 100%
Rollback:  doi image tag -> RollingUpdate lai
Control:   Chỉ qua replica count, khong dung traffic
Risk:      Medium — 100% user bi impact khi co bug

Strategy 2 — Blue-Green (Argo Rollouts)
─────────────────────────────────────────────
Timeline:  [v1 active] [v2 standby] [switch] [v1 standby] [v1 active]
Traffic:   100% v1  -->  0% v1  -->  100% v2  -->  (rollback: switch back)
Rollback:  instant — chi doi selector
Control:   Full traffic switch
Risk:      Low — test full version truoc khi switch
Cost:      2x resource (v1 + v2 cung luc)

Strategy 3 — Canary (Argo Rollouts)
─────────────────────────────────────────────
Timeline:  [5% v2] [25% v2] [50% v2] [75% v2] [100% v2]
Traffic:   v1 95%  -> v1 75% -> v1 50% -> v1 25% -> v2 100%
Rollback:  abort canary -> pod v2 duoc delete
Control:   Precise traffic weight
Risk:      Low — chi 1 phan nho user bi impact
```

### 3.2 Argo Rollouts CRD

`Rollout` = superset cua `Deployment`. Thay `apiVersion: apps/v1` + `kind: Deployment` bang:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
```

**Khác biệt chính:**

| Thuộc tính | Deployment | Rollout |
|------------|-----------|---------|
| `spec.strategy` | `RollingUpdate` / `Recreate` | `canary` / `blueGreen` |
| Pause deployment | Không có | `pause: {}` step |
| Analysis | Không có | `analysis` block |
| Traffic shaping | Không | Replica-based hoặc Istio/NGINX/SMI |
| Rollback | `kubectl rollout undo` | `kubectl argo rollouts undo` |
| ArgoCD compatible | Có | Có (native) |

### 3.3 Canary Strategy — Steps + Pause + Analysis

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: orders-api
spec:
  replicas: 4
  selector:
    matchLabels:
      app: orders-api
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
        - name: orders-api
          image: orders/api:v1.0.0
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
  strategy:
    canary:
      # Tong 4 buoc canary
      steps:
        - setWeight: 25       # 25% traffic sang canary
        - pause: {}            # Dung vo thoi gian → manual approval
        - setWeight: 50        # Tang 50%
        - pause: { duration: 5m }  # Dung 5 phut → auto tiep tuc
        - setWeight: 75        # Tang 75%
        - pause: {}
        - setWeight: 100      # Full traffic
      # Replica-based canary (khong can service mesh)
      canaryService: orders-api-canary
      stableService: orders-api-stable
```

**Canary timeline diagram:**

```
Canary Progression
==================
Pod count (4 replicas):
  Step 0 (0%):  [v1][v1][v1][v1]           stable=4, canary=0
  Step 1 (25%): [v2][v1][v1][v1]           stable=3, canary=1   [PAUSE]
  Step 2 (50%): [v2][v2][v1][v1]           stable=2, canary=2
  Step 3 (75%): [v2][v2][v2][v1]           stable=1, canary=3
  Step 4 (100%):[v2][v2][v2][v2]           stable=0, canary=4

Traffic split (neu dung service mesh):
  0% → 25% → 50% → 75% → 100% v2
```

### 3.4 Blue-Green Strategy

```yaml
strategy:
  blueGreen:
    # Service active = traffic hien tai
    activeService: orders-api-active
    # Service preview = preview version (khong nhan traffic)
    previewService: orders-api-preview
    # Auto promote sau khi tat ca replicas ready
    autoPromotionEnabled: false   # Manual approval (recommended)
    # Switch traffic ngay khi ready
    scaleDownDelaySeconds: 30    # Delay truoc khi scale down v1
    # Anti-affinity tranh chay cung node
    topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: kubernetes.io/hostname
        labelSelector:
          matchLabels:
            app: orders-api
```

```
Blue-Green Timeline
===================
Phase 1 — Deploy preview:
  [v1 active] [v2 preview]
  Traffic: 100% v1, 0% v2

Phase 2 — Test preview:
  [v1 active] [v2 preview]  ← Ops test v2
  Traffic: 100% v1, 0% v2

Phase 3 — Promote:
  [v1 preview] [v2 active]
  Traffic: 0% v1, 100% v2
  Sau 30s: v1 scaledown

Rollback: doi active sang v1 → instant (khong can redeploy)
```

### 3.5 AnalysisTemplate + AnalysisRun

**AnalysisTemplate** = định nghĩa metric queries (Prometheus, Datadog, Web).

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      interval: 1m
      count: 3          # Lay 3 data points, cach nhau 1 phut
      successCondition: result[0] >= 0.95  # 95% request thanh cong
      failureLimit: 1   # Chi can 1 data point fail = AnalysisRun fail
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}",
                status!~"5.."
              }[5m]
            ))
            /
            sum(rate(
              http_requests_total{
                job="{{args.service-name}}"
              }[5m]
            ))
```

**Integration voi Rollout:**

```yaml
strategy:
  canary:
    analysis:
      templates:
        - templateName: success-rate-check
      startingStep: 1     # Bat dau analysis sau step 1 (25%)
      args:
        - name: service-name
          value: orders-api-canary.demo-orders.svc.cluster.local
    steps:
      - setWeight: 25
      - pause: {}         # Analysis chay ngam trong khi pause
      - setWeight: 50
      - pause: {}
```

**AnalysisRun states:**

```
AnalysisRun lifecycle
====================
Pending → Running → Successful
                      ↓
                  Inconclusive → (retry)
                      ↓
                  Failed → Rollout ABORT
```

- **Successful**: Tat ca metric pass → tiep tuc canary
- **Inconclusive**: Khong du data (Prometheus chua co data) → retry hoac pause
- **Failed**: Metric violation → abort rollout

### 3.6 Traffic Shaping Methods

| Method | Cap quyen | Setup | Latency | Use case |
|--------|-----------|-------|---------|----------|
| **Replica-based** (default) | ClusterIP | 0 | Medium | Khong co service mesh, lab |
| **Istio** | Very high | Complex | Low | Production enterprise |
| **NGINX Ingress** | Medium | Medium | Low | AWS ALB + NGINX |
| **SMI (Service Mesh Interface)** | Medium | Medium | Low | Multi-mesh portability |
| **AWS ALB** | Medium | Medium | Low | AWS-native |
| **Gateway API** | High | Medium | Low | Future-proof |

**Replica-based canary (lab nay dung):**

```yaml
# Service stable: chi tro den stable ReplicaSet
apiVersion: v1
kind: Service
metadata:
  name: orders-api-stable
spec:
  selector:
    app: orders-api
    # Stable selector = all replicas (Argo Rollouts patch selector)
---
# Service canary: tro den canary ReplicaSet
apiVersion: v1
kind: Service
metadata:
  name: orders-api-canary
spec:
  selector:
    app: orders-api
    # Canary selector = only canary pods
```

---

## 4. Deep Dive & Trade-offs (~30 phut)

### 4.1 3 Cach Tiep Can Progressive Delivery

```
Approach A — Kubernetes Deployment + RollingUpdate
===================================================
Cai dat:     0 (built-in)
Kiem soat:   Replica count only
Promotion:   Automatic (khi replicas ready)
Rollback:    kubectl rollout undo (redeploy)
Analysis:    Khong co
Risk:        100% user bi impact khi bug

Approach B — Argo Rollouts
===================================================
Cai dat:     Controller + CRD
Kiem soat:   Steps + pause + weight
Promotion:   Manual pause / auto / metrics-based
Rollback:    kubectl argo rollouts undo (khong redeploy)
Analysis:    AnalysisTemplate (Prometheus, Datadog, Web)
Cost:        1 controller (~50MB RAM)

Approach C — Service Mesh Native (Istio)
===================================================
Cai dat:     Istio control plane (1GB+ RAM)
Kiem soat:   VirtualService + DestinationRule
Promotion:    Envoy proxy weight routing
Rollback:     doi weight 0%
Analysis:     K8s liveness/readiness + custom metrics
Cost:        High overhead per pod (sidecar)
```

### 4.2 So sanh chi tiet

| Tieu chi | Deployment | Argo Rollouts | Service Mesh |
|----------|-----------|---------------|--------------|
| Setup complexity | None | Low | High |
| Memory overhead | 0 | ~50MB/controller | ~50MB/pod sidecar |
| Traffic control | None | Steps (weight) | Fine-grained % |
| Promotion | Auto | Manual/Auto/Metrics | Envoy weight |
| Rollback time | Redeploy (2-5 phut) | Instant (undo) | Instant (weight) |
| Analysis | External | Built-in | External |
| Multi-cluster | Via ArgoCD | Via ArgoCD | Per-cluster Istio |
| Best for | Stateless, low-risk | Production canary | Complex mesh |

### 4.3 Best Solution theo Context

| Context | Recommended | Reason |
|---------|-------------|--------|
| Ca nhan / lab local | Argo Rollouts (replica-based) | 0 cost, de setup, day la lab nay |
| Startup, 1-10 service | Argo Rollouts + Prometheus | Gia tri/cao, de operation |
| AWS-native startup | Argo Rollouts + ALB Ingress | Khong can Istio overhead |
| Enterprise 10+ service | Argo Rollouts + Istio | Fine-grained control, L7 metrics |
| Bank / regulated | Argo Rollouts + Istio + SIEM | Audit trail + compliance |

### 4.4 Pitfalls Day 26

| # | Pitfall | Hau qua | Phong ngua |
|---|---------|---------|------------|
| 1 | Cluster khong co Prometheus | AnalysisRun inconclusive forever | Cai prometheus-stack truoc lab |
| 2 | AnalysisTemplate query tra null | Inconclusive → promotion stalled | Test query tren Prometheus truoc |
| 3 | Traffic split voi ClusterIP service | Canary service tro sai pod | Dung label selector `rollouts-pod-template-hash` |
| 4 | Abort nhung khong rollback | Rollout stuck paused, v2 pod van chay | Phan biet abort (pause) vs rollback (undo) |
| 5 | Blue-green giua 2x resource | Cost double | Canary thay vi blue-green khi cost la van de |
| 6 | `startingStep` sai | Analysis chay sai thoi diem | Step 1 = sau setWeight 25% |
| 7 | Rollback = revert Git commit | Chu ky qua lau | Dung `kubectl argo rollouts undo` cho nhanh |
| 8 | `autoPromotionEnabled: true` khong co analysis | Bug production auto-promote | Recommended: `autoPromotionEnabled: false` |
| 9 | Rollout va Deployment cung app | Conflict | Remove Deployment khi chuyen sang Rollout |

### 4.5 Analogy voi Feature Flag

```
Canary deployment ≈ Feature Flag nhung o infrastructure level
─────────────────────────────────────────────────────────────
Feature Flag:
  Code: if (feature.enabled) { v2_logic } else { v1_logic }
  Operator: developer toggle
  Risk: Code complexity

Canary Deployment:
  Code: Khong co if/else — tat ca logic deu chay
  Operator: infrastructure weight routing
  Risk: Co 2 version chay dong thoi

Dung ca 2: Canary cho infrastructure risk, Feature Flag cho business logic risk
```

---

## 5. Hands-on Lab (~60 phut)

**Lab hoan toan local tren kind cluster — mien phi.**

### Pre-req

```bash
# Day 17: kind cluster + ArgoCD da cai
kind get clusters
# EXPECTED: gitops26 hoac gitops17

kubectl get pods -n argocd
# EXPECTED: argocd-server, argocd-dex-server, argocd-redis, argocd-application-controller

# Day 24: orders app da ton tai
kubectl get deployment -n demo-orders
# EXPECTED: orders-api (2 replicas)
```

Neu chua co, tao cluster moi:

```bash
kind create cluster --name gitops26
# Cai ArgoCD nhu Day 17...
# Cai orders app nhu Day 24...
```

---

### Step 1: Cai Argo Rollouts Controller + kubectl plugin (~10 phut)

**Cai controller qua Helm:**

```bash
# Them Argo Rollouts Helm repo
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Cai Argo Rollouts (sync wave -10: truoc app)
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install argo-rollouts argo/argo-rollouts \
  --namespace argo-rollouts \
  --set controller.replicas=1 \
  --set controller.image.tag=v1.8.0 \
  --wait

# Verify controller running
kubectl get pods -n argo-rollouts
# EXPECTED: argo-rollouts-... Running
```

**Cai kubectl plugin (Linux/macOS):**

```bash
# Linux
curl -sLO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
sudo mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts

# macOS
brew install argoproj/tap/kubectl-argo-rollouts

# Verify
kubectl argo rollouts version
# EXPECTED: kubectl-argo rollouts v1.8.0+...
```

**Note Windows:** Download release binary tu `https://github.com/argoproj/argo-rollouts/releases` → rename thanh `kubectl-argo-rollouts.exe`, dat trong PATH.

---

### Step 2: Cai Prometheus Stack cho AnalysisTemplate (~10 phut)

AnalysisTemplate can Prometheus. Lab dung prometheus-stack:

```bash
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=7d \
  --set prometheus.prometheusSpec.evaluationInterval=30s \
  --set grafana.enabled=false \
  --wait --timeout 5m

# Verify
kubectl get pods -n monitoring
# EXPECTED: prometheus-operator-..., prometheus-prometheus-...

# Check Prometheus endpoint
kubectl get svc -n monitoring prometheus-operated -o jsonpath='{.spec.ports[0].port}'
# EXPECTED: 9090
```

---

### Step 3: Refactor Deployment thanh Rollout (~10 phut)

**Backup Deployment hien tai:**

```bash
kubectl get deployment orders-api -n demo-orders -o yaml > /tmp/orders-deployment-backup.yaml
echo "Backup saved"
```

**File: `services/orders-app/base/030-rollout.yaml`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: orders-api
  namespace: demo-orders
spec:
  replicas: 4
  selector:
    matchLabels:
      app: orders-api
  strategy:
    canary:
      canaryService: orders-api-canary
      stableService: orders-api-stable
      steps:
        - setWeight: 25
        - pause: {}           # Manual approval
        - setWeight: 50
        - pause: { duration: 3m }
        - setWeight: 75
        - pause: {}
        - setWeight: 100
      analysis:
        templates:
          - templateName: success-rate-check
        startingStep: 1
        args:
          - name: service-name
            value: orders-api-canary.demo-orders.svc.cluster.local
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
        - name: orders-api
          # Demo image — thay bang image thuc cua orders app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
```

**Tao 2 Service (stable + canary):**

```yaml
# services/orders-app/base/040-services.yaml
---
apiVersion: v1
kind: Service
metadata:
  name: orders-api-stable
  namespace: demo-orders
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: orders-api
---
apiVersion: v1
kind: Service
metadata:
  name: orders-api-canary
  namespace: demo-orders
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: orders-api
    # Argo Rollouts patch label nay de phan biet canary vs stable
    # rollouts-pod-template-hash: <hash>
```

**Update Kustomization:**

```yaml
# services/orders-app/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - 000-namespace.yaml
  - 010-db-secret.yaml
  - 020-migration-job.yaml
  # 030-deployment.yaml  ← COMMENT OUT
  - 030-rollout.yaml
  - 040-service.yaml      # Override voi 2 service
  - 050-smoke-test.yaml

namespace: demo-orders
```

---

### Step 4: Tao AnalysisTemplate Prometheus (~5 phut)

**File: `services/orders-app/base/060-analysis-template.yaml`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
  namespace: demo-orders
spec:
  args:
    - name: service-name
      # Default: su dung service name tu Rollout args
  metrics:
    # Metric 1: Success rate (200-299)
    - name: success-rate
      interval: 30s
      count: 5
      successCondition: result[0] >= 0.95
      failureLimit: 1
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(
              http_requests_total{
                service="{{args.service-name}}",
                status!~"5.."
              }[1m]
            ))
            /
            sum(rate(
              http_requests_total{
                service="{{args.service-name}}"
              }[1m]
            ))

    # Metric 2: Error budget (cho phep 1% error)
    - name: error-budget
      interval: 1m
      count: 3
      successCondition: result[0] < 0.05
      failureLimit: 1
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(
              http_requests_total{
                service="{{args.service-name}}",
                status=~"5.."
              }[1m]
            ))
```

**Note:** Prometheus query `http_requests_total` la mock. Trong lab nay, query se tra ve `null` (metric khong ton tai). Day la bai hoc ve testing AnalysisTemplate truoc khi su dung thuc.

---

### Step 5: Commit + Deploy Rollout v1 → v2 (~10 phut)

```bash
# Commit
git add services/orders-app/base/030-rollout.yaml
git add services/orders-app/base/040-services.yaml
git add services/orders-app/base/060-analysis-template.yaml
git commit -m "day-26: migrate Deployment -> Rollout with canary strategy"
git push

# Sync ArgoCD
argocd app sync orders-app --watch
```

**Quan sat Rollout tren terminal:**

```bash
# Theo doi Rollout status
kubectl argo rollouts get rollout orders-api -n demo-orders --watch

# EXPECTED OUTPUT (step 1):
# NAME          STRATEGY   STATUS        STEP  SET-WEIGHT  READY
# orders-api    Canary     Paused        1/6   25          3/4
#   v1.0.0      └── 75%        v2.0.0  └── 25%
#
# Rollout paused at step 1 — waiting for manual approval
```

**Quan sat tren ArgoCD UI:**

```
ArgoCD UI → orders-app → Details:
  Resources: Rollout (orders-api) — status Paused
  Health: Progressing (canary paused at step 1)
```

**Promote manual qua CLI:**

```bash
# Chi dinh den step tiep theo
kubectl argo rollouts promote orders-api -n demo-orders

# Theo doi tiep
kubectl argo rollouts get rollout orders-api -n demo-orders --watch

# Step 2: 50%, auto-pause 3 phut
# Step 3: 75%, paused (manual)
```

---

### Step 6: Simulate Bad Version v3 → Abort + Rollback (~10 phut)

**Deploy v3 voi bug:**

```bash
# Chinh sua image tag thanh version loi
# File: services/orders-app/base/030-rollout.yaml
# image: nginx:1.25-alpine → image: nginx:nonexistent-tag-xyz

# Hoac dung kubectl argo rollouts set image (test nhanh)
kubectl argo rollouts set image orders-api \
  orders-api=nginx:nonexistent-tag-xyz \
  -n demo-orders

# Sync ArgoCD
argocd app sync orders-app
```

**Quan sat failure:**

```bash
kubectl argo rollouts get rollout orders-api -n demo-orders

# EXPECTED:
# NAME          STRATEGY   STATUS   STEP
# orders-api    Canary     Degraded 3/6
#   v1.0.0      └── 75%    v2.0.0  └── 25%
# Health: Degraded — ReplicaSet orders-api-<hash> is not fully available
```

**Abort rollout:**

```bash
# Hủy canary, giữ nguyên v1 stable
kubectl argo rollouts abort orders-api -n demo-orders

kubectl argo rollouts get rollout orders-api -n demo-orders

# EXPECTED:
# NAME          STRATEGY   STATUS   STEP
# orders-api    Canary     Aborted  3/6
#   v1.0.0      └── 100%  (canary scaled to 0)
```

**Rollback ve v1:**

```bash
# Undo: quay ve stable version truoc (v1)
kubectl argo rollouts undo orders-api -n demo-orders

kubectl argo rollouts get rollout orders-api -n demo-orders

# EXPECTED:
# NAME          STRATEGY   STATUS   STEP
# orders-api    Canary     Healthy  0/6
#   v1.0.0      └── 100%
```

**So sanh 3 cach rollback:**

| Method | Thoi gian | Co skip health check? | Use case |
|--------|-----------|----------------------|----------|
| `kubectl argo rollouts undo` | <5s | Khong (keep stable RS) | Day la recommended |
| `kubectl argo rollouts restart` | 2-5 phut | Co | Khi can restart |
| `git revert` + `argocd app sync` | 30s-2 phut | Co | Long-term fix |

---

### Step 7: Xem AnalysisRun States (~5 phut)

```bash
# AnalysisRun duoc tao tu Rollout
kubectl get analysisrun -n demo-orders
# EXPECTED: orders-api-<step>-<hash> (Running/Inconclusive)

# Xem chi tiet
kubectl argo rollouts analysis get orders-api -n demo-orders

# Xem log cua AnalysisRun
kubectl describe analysisrun -n demo-orders
```

**Chu y quan trong:** Neu Prometheus khong co metric `http_requests_total`, AnalysisRun se la `Inconclusive`. Day la expected behavior trong lab.

---

### Step 8: Cleanup

```bash
# Xoa Rollout (nho remove khoi Git truoc)
git checkout HEAD~1 -- services/orders-app/base/030-rollout.yaml
git add services/orders-app/base/030-rollout.yaml
git commit -m "day-26: restore Deployment"
git push

argocd app sync orders-app

# Verify rollback thanh Deployment
kubectl get rollout -n demo-orders
# EXPECTED: No resources found

kubectl get deployment -n demo-orders
# EXPECTED: orders-api (1)

# Hoac xoa hoan toan orders app
argocd app delete orders-app --cascade

# Xoa monitoring
helm uninstall prometheus -n monitoring
kubectl delete namespace monitoring
```

---

### Troubleshooting

| Van de | Check | Fix |
|--------|-------|-----|
| Rollout stuck `Progressing` | `kubectl describe rollout` | Pod chua ready — check image |
| AnalysisRun `Inconclusive` | Prometheus metric ton tai? | Test query `curl prometheus:9090/api/v1/query` |
| Canary service tro sai | Label `rollouts-pod-template-hash` ton tai? | Argo Rollouts tu patch |
| kubectl plugin loi | Version mismatch? | `kubectl argo rollouts version` |
| `autoPromotionEnabled: true` nhung paused | Analysis inconclusive? | Check Prometheus connectivity |

---

## 6. Kiem tra hieu bai

**Cau 1:** Khi nao nen dung canary? Khi nao nen dung blue-green?

> **Dap an:** Canary = khi muon test voi 1 phan nho traffic truoc (phong ngua bug), khi cost la van de (khong can 2x resource), khi muon do metric. Blue-green = khi can rollback instant (0s), khi co人来 test preview truoc khi switch, khi chap nhan 2x resource cost.

**Cau 2:** AnalysisRun bi `Inconclusive` sau 10 phut. Root cause va fix?

> **Debug checklist:** (1) Prometheus metric khong ton tai → test query tren Prometheus UI; (2) Prometheus khong accessible tu argo-rollouts namespace → check ServiceMonitor hoac NetworkPolicy; (3) `successCondition` sai format → gia tri tra ve khong phai so; (4) `interval` qua ngan so sanh voi `count` → data chua du thoi gian thu thap.

**Cau 3:** Chon approach progressive delivery cho 3 scenario:
> - a) Startup 3 service, 1 developer → Argo Rollouts replica-based (0 cost, de operate)
> - b) Enterprise 50 service tren EKS + canh bao Slack → Argo Rollouts + Istio + Prometheus + Slack notification
> - c) Bank regulated, compliance audit → Argo Rollouts + Istio + AnalysisTemplate + SIEM integration + signed commits

**Cau 4:** Refactor 5 service Deployment → Rollout. Co can phai commit tat ca cung luc khong?

> **Approach:** Commit 1 Rollout truoc, verify hoat dong, roi commit tung service con lai. Hoac dung ArgoCD ApplicationSet de deploy tat ca cung luc. Chu y: rollback tat ca 5 service neu can thi `git revert` tat ca.

**Cau 5:** Abort va Rollback khac nhau nhu the nao?

> **Phan biet:** Abort = dung canary hien tai nhung van giu version cuoi cung (stable). Traffic ve 100% stable nhung Rollout con o trang thai Aborted. Rollback (undo) = chu dong quay ve stable version truoc do, tao ReplicaSet moi tu stable.

---

## 7. Tom tat cuoi ngay

**Kien thuc da hoc:**

- **3 deployment strategy**: RollingUpdate (Kubernetes) / Blue-Green / Canary
- **Rollout CRD**: thay the Deployment, them `strategy.canary` / `strategy.blueGreen`
- **Canary steps**: `setWeight` + `pause` + `analysis` cho phep kiem soat traffic chinh xac
- **AnalysisTemplate + AnalysisRun**: automated promotion/rollback dua tren Prometheus metrics
- **Abort** = dung canary, giu stable; **Rollback (undo)** = quay ve stable ReplicaSet truoc
- **kubectl argo rollouts**: plugin CLI cho watch/promote/abort/undo/get
- **Traffic shaping**: replica-based (khong can service mesh) cho lab

**Output da tao:**

```
services/orders-app/base/
  030-rollout.yaml          ← Rollout CRD thay Deployment
  040-services.yaml         ← Stable + Canary service
  060-analysis-template.yaml ← Prometheus AnalysisTemplate
```

**Chuan bi cho Day 27:**
Day 27 = ArgoCD Observability: Prometheus metrics scrape, Grafana dashboard, notifications (Slack/email), ArgoCD backup + disaster recovery. Day 26 them metric baseline (Prometheus da cai), Day 27 se dung Prometheus nay de observe ArgoCD.

---

## 8. Tham khao

- [Argo Rollouts Documentation](https://argoproj.github.io/argo-rollouts/)
- [Argo Rollouts GitHub](https://github.com/argoproj/argo-rollouts)
- [AnalysisTemplate Reference](https://argoproj.github.io/argo-rollouts/features/analysis/)
- [Traffic Management](https://argoproj.github.io/argo-rollouts/features/traffic-management/)
- [Blue-Green Deployments](https://argoproj.github.io/argo-rollouts/features/bluegreen/)
- [Progressive Delivery with Argo Rollouts (Katacoda)](https://killercoda.com/argoproj)
