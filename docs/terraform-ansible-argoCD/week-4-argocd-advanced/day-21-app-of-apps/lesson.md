# Day 21 — App of Apps Pattern

> **App of Apps = 1 ArgoCD Application quản lý tất cả Applications khác. GitOps tự nhân bản từ root commit.**
>
> Build trên: Day 17 (ArgoCD architecture, reconciliation loop), Day 18 (Application CRD, sync policy), Day 19 (Helm/Kustomize integration), Day 20 (3-repo skeleton với `argocd/bootstrap/root-app.yaml`)
>
> Chuẩn bị cho: Day 22 (ApplicationSet — giải pháp cho giới hạn của App of Apps)

**Thời lượng:** 2 tiếng
**Output:** Root Application bootstrap 5 child apps, chain deployment tự động, cascade deletion

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Triển khai App of Apps pattern: root Application quản lý folder chứa child Application YAML
- Cấu hình bootstrap ordering đúng thứ tự (CRD → platform addon → workload)
- Sử dụng finalizer `resources-finalizer.argocd.argoproj.io` để cascade delete child + workload
- Phân biệt khi nào dùng App of Apps vs ApplicationSet (Day 22)
- Debug cascade deletion stuck, OutOfSync không mong muốn, finalizer loop

---

## 2. Bối cảnh thực tế

### 2.1 Vấn đề: Onboarding service mới mất 2 tiếng

Team ACME có 30 microservice. Mỗi khi thêm service mới, DevOps phải làm tay:

```
1. Tạo Application YAML cho dev     (~5 phút)
2. Tạo Application YAML cho staging  (~5 phút)
3. Tạo Application YAML cho prod    (~5 phút)
4. kubectl apply từng cái           (~2 phút)
5. Verify ArgoCD sync từng cái      (~5 phút)
6. Setup AppProject nếu cần          (~10 phút)
7. Repeat cho mỗi service × 3 envs  = 30 × 30 phút = 15 tiếng
```

**Hệ quả:**
- DevOps trở thành bottleneck — app team phải chờ DevOps tạo Application
- Onboard service mới = nhiều bước manual → dễ sót
- Không có audit trail: không biết ai tạo Application khi nào
- Quên tạo Application → code merge thành công nhưng service không deploy

### 2.2 Incident cụ thể

**Tuần 12, Sprint 8:**

```
Service: payment-gateway (microservice mới)
Team: Payment squad
Timeline:
  T+0:   PR #847 merge code payment-gateway vào main
  T+1h:  CI build image thành công
  T+2h:  Staging test chạy thành công
  T+3h:  DevOps tạo Application YAML
  T+3h5m: kubectl apply
  T+4h:   Production available

→ Total: 4 tiếng để deploy service mới CHỈ VÌ chờ DevOps tạo Application.
→ Payment squad frustrated: "Code đã sẵn sàng, sao deploy lâu thế?"
```

**Root cause:** Không có self-service cho app team. Mọi ArgoCD Application phải do DevOps tạo.

### 2.3 Giải pháp: App of Apps

Sau khi triển khai App of Apps:

```
1. App team thêm file YAML vào argocd/applications/
2. git push
3. ArgoCD root app sync → child app tự xuất hiện
4. ArgoCD child app sync → workload deploy

→ Total: 2 phút (chỉ commit file)
→ Không cần DevOps can thiệp
→ Audit trail: Git commit = who, when, what
```

---

## 3. Kiến thức nền tảng

### 3.1 App of Apps là gì?

App of Apps pattern là một ArgoCD Application (root) trỏ vào folder chứa các ArgoCD Application khác (child). Root Application không trực tiếp quản lý workload, mà quản lý lifecycle của các child Application.

```
                    ┌──────────────────────────────────────────────┐
                    │             Git Repository                   │
                    │  platform-repo/argocd/applications/           │
                    │  ├── root-app.yaml              ← root        │
                    │  ├── ingress-nginx.yaml         ← child      │
                    │  ├── cert-manager.yaml          ← child      │
                    │  ├── external-secrets.yaml      ← child      │
                    │  ├── prometheus-stack.yaml      ← child      │
                    │  └── guestbook.yaml             ← child      │
                    └──────────────────┬───────────────────────────┘
                                       │ ArgoCD reconciliation loop
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │            ArgoCD Application Controller        │
                    │                                               │
                    │  root-platform                               │
                    │    └── ingress-nginx (child app)             │
                    │         └── Deployment, Service, ConfigMap   │
                    │    └── cert-manager (child app)              │
                    │         └── Deployment, Service, CRD         │
                    │    └── external-secrets (child app)          │
                    │         └── Deployment, Service, ClusterSecret│
                    │    └── prometheus-stack (child app)          │
                    │         └── Deployment, Service, PrometheusCR│
                    │    └── guestbook (child app)                 │
                    │         └── Deployment, Service               │
                    └───────────────────────────────────────────────┘
```

**Điểm mấu chốt:**

- Root Application `kind: Application`, trỏ `path: argocd/applications/`
- Child Application cũng là `kind: Application`, trỏ vào workload manifests
- Root app **KHÔNG** trực tiếp tạo Deployment/Service — nó tạo child Application
- Child Application mới xuất hiện sau khi file YAML được commit vào Git
- Xóa file YAML → ArgoCD prune child Application + workload

### 3.2 Cấu trúc YAML root Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-platform                    # Tên root app
  namespace: argocd
  labels:
    app.kubernetes.io/name: root-platform
  finalizers:                            # Quan trọng: cascade delete
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default                       # Project của root app
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: argocd/applications             # Folder chứa child Application YAML
    directory:
      recurse: true                      # Đọc cả sub-folder
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd                    # Root app tạo trong namespace argocd
  syncPolicy:
    automated:
      prune: true                        # Xóa child app khi file bị xóa
      selfHeal: true                    # Fix drift trên child app metadata
    syncOptions:
      - CreateNamespace=true
```

**Cấu trúc child Application YAML:**

```yaml
# argocd/applications/ingress-nginx.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx                    # Child app name
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform                     # Khác project với root
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/ingress-nginx
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### 3.3 Bootstrap Ordering

Thứ tự deploy quan trọng vì một số component phụ thuộc vào component khác.

#### Dependency chain thực tế

```
Layer 1: CRD Installer (nếu cần)
  └── custom resource definitions phải tồn tại trước CR
         │
         ▼
Layer 2: Namespace & Network Foundation
  └── namespace, network policies, limit ranges
         │
         ▼
Layer 3: Certificate Management
  └── cert-manager: cấp certificate cho ingress
         │
         ▼
Layer 4: Ingress Controller
  └── ingress-nginx: dùng certificate từ cert-manager
         │
         ▼
Layer 5: Secrets Management
  └── external-secrets: inject secret vào pod
         │
         ▼
Layer 6: Observability
  └── prometheus-stack: collect metrics
         │
         ▼
Layer 7: Application Workload
  └── api-service, worker-service: dùng ingress, secrets, metrics
```

**ArgoCD không tự ordering child Application.** Muốn ordering, có 2 cách:

**Cách 1: ArgoCD Autopilot** (Day 25 học sâu hơn)

```yaml
# Thêm annotation để Autopilot hiểu thứ tự
annotations:
  argocd.argoproj.io/manifest-generate-paths: .
  # Autopilot quản lý sync wave
```

**Cách 2: Sync Waves** (Day 24 học chi tiết — hôm nay chỉ preview)

```yaml
# ingress-nginx.yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "10"   # Deploy trước
spec:
  ...

# cert-manager.yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "5"    # Deploy TRƯỚC ingress
spec:
  ...
```

**Cách 3: Tách folder theo layer** (recommended)

```
argocd/
├── bootstrap/               # Layer 1: CRD
│   └── root-app.yaml
├── layer-1-cert-manager/   # Layer 2: cert-manager
│   └── cert-manager.yaml
├── layer-2-ingress/        # Layer 3: ingress
│   └── ingress-nginx.yaml
└── layer-3-platform/       # Layer 4: platform addons
    ├── external-secrets.yaml
    └── prometheus-stack.yaml
```

**Hạn chế:** Với App of Apps thuần, ArgoCD không guarantee ordering giữa các child Application. Nếu ordering bắt buộc, dùng sync waves (Day 24) hoặc ApplicationSet (Day 22).

### 3.4 App Dependency: Chicken-and-Egg

Một số app có dependency vòng tròn:

```
cert-manager cần webhook → webhook cần certificate
external-secrets cần external-secrets CRD → CRD tạo bởi external-secrets
ArgoCD cần ingress-nginx → ingress-nginx cần certificate để expose ArgoCD
```

**Giải pháp:**

| Dependency | Approach |
|------------|----------|
| cert-manager + ArgoCD | ArgoCD dùng NodePort/LoadBalancer thay vì Ingress |
| external-secrets CRD | CRD là ClusterScoped, tạo riêng trước |
| cert-manager webhook | Self-signed CA, mounted vào cert-manager pod |

### 3.5 Finalizers: Cascade Delete

**Vấn đề:** Nếu xóa root Application, child Application có bị xóa không?

**Câu trả lời: TÙY thuộc finalizer.**

```
BằNG finalizer (resources-finalizer.argocd.argoproj.io):
──────────────────────────────────────────────────────────────
kubectl delete application root-platform
  → ArgoCD xóa root app
  → ArgoCD xóa tất cả child app
  → ArgoCD xóa workload của mỗi child app
  → Cascade: toàn bộ sạch sẽ ✓

KHÔNG có finalizer:
──────────────────────────────────────────────────────────────
kubectl delete application root-platform
  → ArgoCD xóa root app
  → Child app CÒN NGUYÊN trong cluster
  → Workload CÒN NGUYÊN trong cluster
  → Orphaned resources ✗

kubectl delete application child-app (without finalizer):
  → ArgoCD xóa child app
  → Workload CÒN NGUYÊN (prune không hoạt động nếu không có prune:true)
```

**Finalizer behavior table:**

| Root finalizer | Root prune | Child finalizer | Child prune | Delete root → | Delete child → |
|----------------|------------|-----------------|-------------|----------------|----------------|
| Có | Có | Có | Có | Xóa root + child + workload | Xóa child + workload |
| Có | Có | Không | Có | Xóa root + child | Workload orphaned |
| Không | Có | Có | Có | Chỉ xóa root | Xóa child + workload |
| Không | Không | Không | Không | Chỉ xóa root | Chỉ xóa child app |

**Khuyến nghị:** Luôn thêm `resources-finalizer.argocd.argoproj.io` vào root app và child app, với `prune: true` trong sync policy.

### 3.6 GitOps tự nhân bản

App of Apps tạo ra vòng lặp GitOps 2 cấp:

```
Git commit (thêm child app YAML)
       │
       ▼
ArgoCD root app reconciliation
       │
       ▼
Child Application được tạo trong cluster
       │
       ▼
ArgoCD child app reconciliation
       │
       ▼
Workload (Deployment, Service, ConfigMap...) deploy
```

**Sự khác biệt:**

| Level | Application trỏ vào | Quản lý resource |
|-------|---------------------|------------------|
| Root | Folder chứa child app YAML | Child Application CRD |
| Child | Folder chứa workload | Deployment, Service, ConfigMap, v.v. |

## 4. Deep Dive & Trade-offs

### 4.1 Ba cách bootstrap ArgoCD apps

#### Cách 1: Tạo Application thủ công

```bash
# Imperative: tạo từng app bằng kubectl
kubectl apply -f ingress-nginx.yaml
kubectl apply -f cert-manager.yaml
kubectl apply -f api-service-dev.yaml
kubectl apply -f api-service-prod.yaml
# ... 30+ lần
```

| Pros | Cons |
|------|------|
| Đơn giản, không cần setup | Không có audit trail |
| Nhanh cho 1-2 app | Không reproduce được (mỗi cluster phải làm lại) |
| | DevOps trở thành bottleneck |
| | Không self-service cho app team |

#### Cách 2: App of Apps (hôm nay)

```bash
# Declarative: 1 root app → tạo tất cả child app
kubectl apply -f root-app.yaml
```

| Pros | Cons |
|------|------|
| Declarative, Git-managed | Không ordering guarantee giữa child apps |
| 1 commit = bootstrap toàn cluster | Boilerplate cho mỗi child app |
| Audit trail qua Git | Khó parametrize (không có template variables) |
| Self-service cho app team | 50+ services × 3 envs = 150 file |
| Dễ hiểu | Refactor đau (đổi naming convention) |

#### Cách 3: ApplicationSet (Day 22)

```yaml
# Generator tự tạo Application cho mỗi service/env/cluster
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: api-services
spec:
  generators:
    - git:
        files:
          - path: services/**/kustomization.yaml
  template:
    spec:
      source:
        path: "{{path}}/overlays/{{metadata.labels.env}}"
```

| Pros | Cons |
|------|------|
| Template-driven, parametrize được | Phức tạp hơn App of Apps |
| Tự động tạo app khi thêm file mới | Cần hiểu generator + template |
| 1 ApplicationSet thay thế 50+ file | Overkill cho 5-15 app |

### 4.2 So sánh toàn diện

| Tiêu chí | Manual kubectl | App of Apps | ApplicationSet |
|----------|--------------|-------------|----------------|
| Setup effort | Thấp | Trung bình | Cao |
| Scale | 1-5 app | 5-30 app | 30-1000+ app |
| Template | Không | Không | Có (generator) |
| Ordering guarantee | Không | Không | Không (vẫn cần sync waves) |
| Self-service | Không | Có | Có |
| Audit trail | Không | Có (Git) | Có (Git) |
| Boilerplate | Không | Nhiều | Ít |
| Migration từ manual | Không | Dễ | Trung bình |

### 4.3 Khi nào DÙNG App of Apps

**DÙNG App of Apps khi:**

- Bootstrap cluster mới lần đầu (5-15 platform addon)
- Team nhỏ (< 10 người), ít service
- Cần đơn giản, dễ debug, dễ hiểu cho team mới
- Không có pattern đặc biệt phức tạp
- Self-service cho app team cần thiết nhưng ApplicationSet quá phức tạp

**VÍ DỤ: Platform team bootstrap production cluster**

```
platform-repo/argocd/
├── root-platform.yaml           # Root: quản lý toàn bộ
├── platform-project.yaml       # AppProject
└── applications/
    ├── 01-namespace.yaml       # namespace foundation
    ├── 02-cert-manager.yaml    # cert-manager
    ├── 03-ingress-nginx.yaml   # ingress-nginx
    ├── 04-external-secrets.yaml
    ├── 05-prometheus-stack.yaml
    ├── 06-loki.yaml
    ├── 07-guestbook.yaml       # demo app
    └── ...
```

### 4.4 Khi nào KHÔNG nên dùng

**KHÔNG DÙNG App of Apps khi:**

- 50+ Application × 3 envs = 150 file → ApplicationSet thay thế
- Multi-cluster management → ApplicationSet cluster generator
- Service auto-discovery → ApplicationSet git generator
- Nhiều environment với template khác nhau → ApplicationSet matrix generator

**Chuyển sang ApplicationSet khi:**

- Số lượng Application file > 30
- Cần parametrize: image tag, replica count, environment name
- Cần tự động tạo Application khi thêm service mới
- Quản lý nhiều cluster từ 1 control plane

### 4.5 Common Pitfalls

**1. Cascade deletion bị stuck (finalizer không resolve)**

```
Symptom: kubectl delete application root-platform
         Pod bị Terminating mãi không xóa

Root cause: Finalizer cố xóa resource đã bị orphaned trước đó

Fix:
kubectl get application root-platform -n argocd -o yaml
# Xem finalizers
kubectl patch application root-platform -n argocd \
  --type merge -p '{"metadata":{"finalizers":[]}}'
```

**2. Root app OutOfSync nhưng child app không hiển thị**

```
Root cause: Child app YAML có syntax error hoặc missing field

Debug:
argocd app get root-platform
argocd app resources root-platform        # Xem child apps
kubectl get application -n argocd         # Tất cả app trong cluster

Fix: Validate child YAML
kubectl apply --dry-run=server -f child-app.yaml
```

**3. Sync policy mismatch giữa root và child**

```
Root: automated + selfHeal: true
Child: manual sync

→ Root sẽ cố revert child về manual policy? KHÔNG.
→ Root chỉ sync child app metadata (name, labels, annotations)
→ Child workload sync behavior độc lập với root

Best practice: Đồng nhất sync policy hoặc root chỉ quản lý app metadata
```

**4. Recursive App of Apps loop**

```
Root trỏ vào folder chứa root.yaml → OUT OF SCOPE
ArgoCD detect: root.yaml → tạo root app → root app trỏ lại folder → loop

ArgoCD prevent: Không cho phép Application trỏ vào folder chứa chính nó
Fix: Tách root.yaml ra khỏi folder root trỏ vào
```

**5. Namespace creation race**

```
Child app tạo workload trong namespace chưa tồn tại
→ Sync fail

Fix:
spec:
  syncOptions:
    - CreateNamespace=true
# Thứ tự: namespace app trước → workload app sau
```

### 4.6 Best Solution theo Context

| Context | Recommendation | Reasoning |
|---------|----------------|-----------|
| Cá nhân / learning | App of Apps | Đơn giản, dễ hiểu |
| Startup (< 10 services) | App of Apps | Đủ dùng, không over-engineering |
| Growing (10-30 services) | App of Apps → ApplicationSet | Migrate khi quá 30 app |
| Scale (30+ services) | ApplicationSet | Generator-driven, less boilerplate |
| Enterprise / Bank | ApplicationSet + RBAC + Sync window | Compliance + audit |
| Multi-cluster (3+ clusters) | ApplicationSet cluster generator | 1 template → N clusters |

---

## 5. Hands-on Lab

**Mục tiêu:** Bootstrap 5 child apps (ingress-nginx, cert-manager, prometheus-stack, guestbook, external-secrets) qua root App of Apps.

### Prerequisites

- kind cluster đã cài ArgoCD (Day 17)
- kubectl context trỏ vào kind cluster
- platform-repo skeleton đã clone (từ Day 20)
- GitHub account (hoặc dùng local bare repo)

```bash
# Verify prerequisites
kubectl get pods -n argocd
# EXPECTED: argocd-server, argocd-repo-server, argocd-application-controller Running

argocd version --client
# EXPECTED: v2.x.x

# Login ArgoCD CLI
argocd login --username admin \
  --password $(kubectl get secret argocd-initial-admin-secret \
    -n argocd -o jsonpath='{.data.password}' | base64 -d) \
  --grpc-web
```

### Step 1: Tạo branch mới trong platform-repo

```bash
cd platform-repo  # hoặc clone mới
git checkout main
git pull origin main
git checkout -b day-21-app-of-apps
```

**Expected output:**
```
Switched to a new branch 'day-21-app-of-apps'
```

### Step 2: Tạo AppProject cho platform layer

**File:** `platform-repo/argocd/projects/platform-project.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
  namespace: argocd
  labels:
    app.kubernetes.io/name: platform-project
spec:
  description: Platform addons and bootstrap applications
  sourceRepos:
    - https://github.com/YOUR_USER/platform-repo.git
    - https://github.com/argoproj/argocd-example-apps.git
  destinations:
    - server: https://kubernetes.default.svc
      namespace: cert-manager
    - server: https://kubernetes.default.svc
      namespace: ingress-nginx
    - server: https://kubernetes.default.svc
      namespace: external-secrets
    - server: https://kubernetes.default.svc
      namespace: monitoring
    - server: https://kubernetes.default.svc
      namespace: guestbook
    - server: https://kubernetes.default.svc
      namespace: argocd
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  roles:
    - name: platform-admin
      description: Platform team admin
      groups:
        - platform-team
      policies:
        - p, proj:platform:platform-admin, applications, *, platform/*, allow
```

Apply AppProject:

```bash
kubectl apply -f argocd/projects/platform-project.yaml

# Verify
kubectl get appproject platform -n argocd
# EXPECTED: NAME       AGE
#           platform   10s
```

### Step 3: Tạo child Application YAML

Tạo folder `argocd/applications/` và thêm 5 child Application.

#### 3a. ingress-nginx (Helm chart)

**File:** `argocd/applications/ingress-nginx.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx
  namespace: argocd
  labels:
    layer: platform
    app.kubernetes.io/name: ingress-nginx
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/ingress-nginx
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

#### 3b. cert-manager (Helm chart)

**File:** `argocd/applications/cert-manager.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager
  namespace: argocd
  labels:
    layer: platform
    app.kubernetes.io/name: cert-manager
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/cert-manager
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: cert-manager
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### 3c. prometheus-stack (Helm chart — lightweight mode)

**File:** `argocd/applications/prometheus-stack.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prometheus-stack
  namespace: argocd
  labels:
    layer: platform
    app.kubernetes.io/name: prometheus-stack
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/prometheus-stack
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
  ignoreDifferences:
    - group: apiextensions.k8s.io
      kind: CustomResourceDefinition
      jsonPointers:
        - /spec
```

#### 3d. guestbook (Kustomize — từ argocd-example-apps)

**File:** `argocd/applications/guestbook.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
  labels:
    layer: application
    app.kubernetes.io/name: guestbook
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: kustomize-guestbook/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: guestbook
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### 3e. external-secrets (Helm chart)

**File:** `argocd/applications/external-secrets.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-secrets
  namespace: argocd
  labels:
    layer: platform
    app.kubernetes.io/name: external-secrets
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/external-secrets
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: external-secrets
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Tạo thư mục và placeholder values cho các platform service (vì root app cần Helm values tồn tại):

```bash
mkdir -p platform-services/ingress-nginx
mkdir -p platform-services/cert-manager
mkdir -p platform-services/prometheus-stack
mkdir -p platform-services/external-secrets
```

**File:** `platform-services/ingress-nginx/values.yaml`

```yaml
controller:
  replicaCount: 1
  service:
    type: ClusterIP
  metrics:
    enabled: false
  admissionWebhooks:
    enabled: false
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
```

**File:** `platform-services/cert-manager/values.yaml`

```yaml
installCRDs: true
replicaCount: 1
webhook:
  replicaCount: 1
```

**File:** `platform-services/prometheus-stack/values.yaml`

```yaml
grafana:
  enabled: false
alertmanager:
  enabled: false
prometheus:
  prometheusSpec:
    retention: 7d
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
```

**File:** `platform-services/external-secrets/values.yaml`

```yaml
secretStore:
  cas:
    enabled: true
controller:
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
```

### Step 4: Tạo root Application

**File:** `argocd/applications/root-app.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-platform
  namespace: argocd
  labels:
    app.kubernetes.io/name: root-platform
    app.kubernetes.io/part-of: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USER/platform-repo.git
    targetRevision: day-21-app-of-apps
    path: argocd/applications
    directory:
      recurse: true
      exclude: root-app.yaml   # Không include chính nó
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
```

**Giải thích `exclude: root-app.yaml`:**

Root app trỏ vào folder `argocd/applications/`. Nếu không exclude, ArgoCD sẽ thấy `root-app.yaml` và cố tạo 1 Application trỏ đến chính nó → potential loop.

### Step 5: Commit và push

```bash
git add argocd/
git add platform-services/
git commit -m "feat(day-21): bootstrap platform apps via App of Apps

- Add root-platform Application
- Add 5 child applications:
  - ingress-nginx (Helm)
  - cert-manager (Helm)
  - prometheus-stack (Helm)
  - external-secrets (Helm)
  - guestbook (Kustomize)

App of Apps pattern: root app manages child app lifecycle"

git push -u origin day-21-app-of-apps
```

### Step 6: Apply root app

```bash
# Clone fresh nếu cần (hoặc dùng repo đã có)
# IMPORTANT: Đây là bootstrap MANUAL DUY NHẤT
kubectl apply -f argocd/applications/root-app.yaml

# Verify root app tạo
kubectl get application root-platform -n argocd
# EXPECTED:
# NAME             PROJECT   SYNC STATUS   HEALTH STATUS
# root-platform    default   OutOfSync     Missing
```

### Step 7: Quan sát ArgoCD tự tạo child apps

```bash
# Watch ArgoCD sync (trong 30 giây)
argocd app list --watch

# Sau vài giây, child apps xuất hiện:
# NAME                  PROJECT   SYNC STATUS   HEALTH STATUS
# root-platform         default   Syncing       Missing
# cert-manager          platform  OutOfSync     Missing
# ingress-nginx         platform  OutOfSync     Missing
# prometheus-stack      platform  OutOfSync     Missing
# external-secrets      platform  OutOfSync     Missing
# guestbook             platform  OutOfSync     Missing
```

Hoặc kiểm tra bằng kubectl:

```bash
kubectl get application -n argocd
# EXPECTED: 6 application (1 root + 5 child)
```

### Step 8: Sync child apps

```bash
# Sync toàn bộ
argocd app sync root-platform

# Hoặc sync từng child
argocd app sync cert-manager
argocd app sync ingress-nginx
argocd app sync guestbook
```

**Expected output sau khi sync:**

```bash
argocd app list
# NAME                  PROJECT   SYNC STATUS   HEALTH STATUS
# root-platform         default   Synced        Healthy
# cert-manager          platform  Synced        Healthy
# ingress-nginx         platform  Synced        Healthy
# prometheus-stack      platform  Synced        Healthy/Degraded  # Degraded OK cho lab
# external-secrets      platform  Synced        Healthy
# guestbook             platform  Synced        Healthy
```

Verify workload:

```bash
kubectl get pods -A
# NAMESPACE           NAME                               READY
# ingress-nginx       ingress-nginx-controller-xxx       1/1
# cert-manager        cert-manager-xxx                    1/1
# cert-manager        cert-manager-webhook-xxx            1/1
# monitoring          prometheus-kube-prometheus-xxx      1/1
# guestbook           guestbook-xxx                      1/1
```

### Step 9: Test thêm app mới

Thêm 1 child Application mới:

```bash
# Tạo thêm app demo (plain manifest, không Helm/Kustomize)
mkdir -p platform-services/httpbin

cat > argocd/applications/httpbin.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: httpbin
  namespace: argocd
  labels:
    layer: application
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/YOUR_USER/platform-repo.git
    targetRevision: day-21-app-of-apps
    path: platform-services/httpbin
  destination:
    server: https://kubernetes.default.svc
    namespace: httpbin
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

# Tạo placeholder manifest
mkdir -p platform-services/httpbin
cat > platform-services/httpbin/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin
  namespace: httpbin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: httpbin
  template:
    metadata:
      labels:
        app: httpbin
    spec:
      containers:
        - name: httpbin
          image: kennethreitz/httpbin
          ports:
            - containerPort: 80
EOF

git add argocd/applications/httpbin.yaml
git add platform-services/httpbin/
git commit -m "feat(day-21): add httpbin app via App of Apps"
git push
```

ArgoCD sẽ tự detect và sync:

```bash
# Sau 1-2 phút (reconciliation loop interval)
argocd app list
# NAME      PROJECT   SYNC STATUS   HEALTH STATUS
# httpbin   platform  Synced        Healthy
```

### Step 10: Test xóa app

```bash
# Xóa file httpbin.yaml
git rm argocd/applications/httpbin.yaml
git rm -rf platform-services/httpbin/
git commit -m "chore(day-21): remove httpbin app"
git push

# ArgoCD sẽ:
# 1. Detect httpbin.yaml bị xóa
# 2. Prune httpbin Application
# 3. Prune httpbin workload (Deployment, Namespace)
```

Verify:

```bash
argocd app list
# httpbin KHÔNG còn trong danh sách

kubectl get namespace httpbin
# Error from server (NotFound): namespaces "httpbin" not found
# ArgoCD đã prune toàn bộ ✓
```

### Step 11: Test finalizer behavior

```bash
# Scenario: Xóa root app KHÔNG có finalizer

# Trước tiên: xóa finalizer khỏi root app
kubectl patch application root-platform -n argocd \
  --type merge -p '{"metadata":{"finalizers":[]}}'

# Xóa root app
kubectl delete application root-platform -n argocd

# Check: child apps có bị xóa không?
kubectl get application -n argocd
# EXPECTED: Child apps CÒN NGUYÊN (vì không có finalizer)

# Verify workload vẫn chạy
kubectl get pods -A
# EXPECTED: Tất cả pod vẫn chạy (orphaned)
```

**Bài học:** KHÔNG có finalizer → child app orphaned khi xóa root.

### Step 12: Test failure scenario

```bash
# Tạo Application với invalid YAML
cat > argocd/applications/bad-app.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bad-app
spec:
  # Thiếu required fields: project, source, destination
  project: platform
  source:
    repoURL: https://invalid-repo-url.example.com
    targetRevision: main
    path: nonexistent
EOF

git add argocd/applications/bad-app.yaml
git commit -m "chore(day-21): test failure scenario"
git push

# Observe
argocd app get root-platform
# EXPECTED: OutOfSync (vì bad-app không sync được)

argocd app get bad-app
# EXPECTED: Syncing → Error: "rpc error: code = Unknown"

# Fix
git rm argocd/applications/bad-app.yaml
git commit -m "fix(day-21): remove bad app"
git push
```

### Step 13: Cleanup toàn bộ

```bash
# XÓa root app — cascade delete tất cả child + workload
kubectl delete application root-platform -n argocd

# Verify toàn bộ bị xóa
kubectl get application -n argocd
# EXPECTED: (empty)

kubectl get pods -A
# EXPECTED: Chỉ còn system pods (argocd, kube-system)

# Verify namespace đã bị xóa
kubectl get namespaces
# EXPECTED: Không còn namespace ingress-nginx, cert-manager, monitoring, guestbook
```

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Giải thích flow sync khi root Application phát hiện file child app mới trong Git.

> **Trả lời:**
> 1. ArgoCD repo server poll hoặc webhook trigger → detect Git commit mới
> 2. Repo server clone `argocd/applications/` folder từ platform-repo
> 3. ArgoCD application controller parse tất cả YAML trong folder
> 4. Nếu file mới là valid Application CRD → tạo child Application resource trong cluster
> 5. Child Application → reconciliation loop → sync workload
> 6. Root app status: Synced, Healthy

**Câu 2:** Khi nào NÊN dùng ApplicationSet thay vì App of Apps?

> **Trả lời:** Khi số lượng Application > 30, hoặc khi cần parametrize template (image tag, replica count, environment name) cho nhiều service/env/cluster. Khi cần auto-detect service mới (thêm folder → tự tạo Application) → ApplicationSet git generator. Khi quản lý nhiều cluster từ 1 control plane → ApplicationSet cluster generator.

**Câu 3:** Debug: child app không xuất hiện sau khi commit file mới. Các bước kiểm tra?

> **Trả lời:**
> 1. `argocd app get root-platform` — root app Synced chưa?
> 2. `argocd app resources root-platform` — list child apps
> 3. `kubectl get application -n argocd` — có child app trong cluster?
> 4. `argocd app logs root-platform` — có lỗi parse YAML?
> 5. Validate child YAML: `kubectl apply --dry-run=server -f child-app.yaml`
> 6. Check `directory.recurse: true` trong root app spec
> 7. Check child app `spec.project` tồn tại trong AppProject
> 8. Check ArgoCD repo credentials cho repo URL trong child app

**Câu 4:** Team có 30 services × 3 envs đang dùng App of Apps (90 file). Có nên migrate sang ApplicationSet?

> **Trả lời:** CÓ. 90 file Application YAML là boilerplate quá nhiều, refactor đau (đổi naming convention = 90 file). ApplicationSet thay thế bằng 1 generator + 1 template. Migration: viết ApplicationSet cho 1 service × 1 env trước, test, sau đó mở rộng. Tool hỗ trợ: `argocd-importer` hoặc viết script convert Application YAML → ApplicationSet template.

**Câu 5:** Trade-off: tự sync (automated) vs manual sync cho root app?

> **Trả lời:**
> - **Automated (`automated: prune:true, selfHeal:true):** Tốt cho dev/staging, root app tự sync khi Git thay đổi. Rủi ro: nếu commit sai → ArgoCD tự apply ngay, có thể break cluster.
> - **Manual sync:** Tốt cho prod hoặc root app quản lý nhiều critical child. Team control khi nào change được apply.
> - **Hybrid:** Automated cho dev, manual cho prod. Hoặc automated với sync wave để control ordering (Day 24).
> - Recommendation: Dev = automated, Prod = manual với PR promotion.

---

## 7. Tóm tắt cuối ngày

### Điều đã học

**App of Apps Pattern:**
- Root Application trỏ vào folder chứa child Application YAML
- Git commit mới → ArgoCD tự tạo child Application → child sync workload
- Xóa file → ArgoCD prune child + workload
- Finalizer `resources-finalizer.argocd.argoproj.io` là bắt buộc cho cascade delete

**Bootstrap Ordering:**
- ArgoCD không guarantee ordering giữa child apps
- Dùng sync waves (Day 24) hoặc folder-per-layer nếu ordering bắt buộc
- CRD phải tồn tại trước CR

**Khi nào dùng:**
- Dùng: bootstrap cluster (5-15 app), platform layer, team nhỏ
- Không dùng: 30+ app, multi-cluster, cần parametrize → dùng ApplicationSet (Day 22)

**Output của ngày hôm nay:**
- 1 root Application (`root-platform.yaml`)
- 5 child Application (ingress-nginx, cert-manager, prometheus-stack, external-secrets, guestbook)
- Helm values skeleton cho 4 platform services
- Full cascade delete tested

### Chuẩn bị cho Day 22

Day 22 học **ApplicationSet** — giải pháp cho giới hạn của App of Apps:
- Generator-driven: list, git, cluster, matrix
- 1 template thay thế hàng trăm Application YAML file
- Auto-discovery: thêm service mới = thêm folder, không cần commit Application file

---

## 8. Tham khảo thêm

### Tài liệu chính thức

- [ArgoCD — App of Apps (Cluster Bootstrapping)](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)
- [ArgoCD — Declarative Setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [ArgoCD — Application Deletion & Cascading](https://argo-cd.readthedocs.io/en/stable/user-guide/app_deletion/)
- [ArgoCD — Sync Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-policy/)

### Blogs & Case Studies

- [App of Apps Pattern — Codefresh](https://codefresh.io/docs/gitops-repos/app-of-apps/)
- [ArgoCD Best Practices — Atlassian](https://www.atlassian.com/continuous-delivery/continuous-deployment/gitops-argocd)
- [Multi-Tenant GitOps with ArgoCD — Codefresh](https://codefresh.io/docs/gitops-workflows/multi-tenant/)

### ArgoCD Autopilot (related)

- [ArgoCD Autopilot](https://argocd-autopilot.readthedocs.io/) — Opinionated App of Apps installer, giới thiệu ở Day 25

<!-- APPEND_HERE -->
