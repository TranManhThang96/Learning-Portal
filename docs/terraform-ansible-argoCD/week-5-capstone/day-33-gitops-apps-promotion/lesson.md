# Day 33 — GitOps Apps Layer & Promotion Strategy

> **Capstone Phase — Apps Deployment Layer**
> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Day 28-32 (architecture + infra + k8s + data + platform bootstrap)
> **Output:** 3 Helm charts + Kustomize overlays (dev/staging/prod-like) + ApplicationSet auto-discovery + promotion workflow + rollback playbook

---

## 1. Mục tiêu ngày học

- Thiết kế apps-repo structure chuẩn production: base Helm chart cho mỗi microservice + Kustomize overlay cho dev/staging/prod-like
- Cấu hình ApplicationSet generator tự động phát hiện service mới thông qua git directory scanner (git generator), không cần sửa ApplicationSet manifest khi thêm service
- So sánh chiến lược image tag: immutable tag (sha256), semver, git sha, và tại sao `latest` là anti-pattern trong production
- Triển khai promotion workflow hoàn chỉnh: dev auto-sync, staging qua PR, production manual approval
- Thực hiện rollback bằng Git revert và ArgoCD sync previous revision
- Deploy đầy đủ 3 microservices (api-service, worker-service, frontend-service) qua ArgoCD với 3 environment

---

## 2. Bối cảnh thực tế

### Chuyện thật mà ai cũng gặp

Sau khi có kiến trúc tổng thể (Day 28), network (Day 29), Kubernetes cluster (Day 30), data layer (Day 31), và platform bootstrap ArgoCD (Day 32), bạn bắt đầu deploy application thực sự. 3 vấn đề kinh điển xuất hiện ngay:

**1. "Helm hay Kustomize?" — team debate mãi không xong**

Team A viết Helm chart cho mọi thứ, override values bằng `-f` flag. Team B dùng Kustomize overlays, nhưng mỗi lần thêm service mới phải copy-paste 10 file. Cả hai đều không có auto-discovery — muốn deploy service thứ 4 phải sửa ApplicationSet manifest. Một tuần sau: 2 ApplicationSet conflict nhau, 3 app OutOfSync không rõ lý do.

**2. Image tag `latest` gây ra incident**

```
09:00 — Dev push code mới, CI build image với tag `latest`
09:02 — ArgoCD sync, pods restart
09:15 — Ứng dụng không chạy (feature flag mới chưa enable)
09:30 — "Rollback" = build lại image cũ, push lên `latest`
09:45 — Incident resolved
```

Không ai biết image `latest` tương ứng commit nào. Không có audit trail. Không có deterministic rollback.

**3. Promotion không có gate — code lên production tự nhiên**

Dev sync tự động, staging sync tự động, production sync tự động. Một engineer gõ `argocd app sync` sai context → production deploy lúc 22:00. Không có approval gate, không có PR review, không có audit log.

**Capstone ngày hôm nay:** Xây dựng apps layer chuẩn production từ day 1 — không phải vá lỗi sau này.

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Apps Repo Structure

Trước khi code, phải đặt câu hỏi: **"Repo structure nào giúp team scale khi có 10, 20, 50 microservices?"**

```
apps-repo/
├── .github/
│   └── workflows/
│       ├── promote-staging.yml      # PR-triggered, staging promotion
│       └── promote-production.yml    # Manual dispatch, production promotion
├── services/
│   ├── api-service/
│   │   ├── base/                   # Helm chart base
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml
│   │   │   ├── values-dev.yaml
│   │   │   ├── values-staging.yaml
│   │   │   ├── values-prod.yaml
│   │   │   └── templates/
│   │   │       ├── deployment.yaml
│   │   │       ├── service.yaml
│   │   │       ├── hpa.yaml
│   │   │       └── pdb.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       │   └── kustomization.yaml
│   │       ├── staging/
│   │       │   └── kustomization.yaml
│   │       └── prod/
│   │           └── kustomization.yaml
│   ├── worker-service/
│   │   └── ... (same structure)
│   └── frontend-service/
│       └── ... (same structure)
└── appsets/
    ├── services-generator.yaml     # ApplicationSet per service
    └── environments-generator.yaml # ApplicationSet per env
```

**Tại sao cấu trúc này?**

- `services/<name>/base/` chứa Helm chart — dùng lại cho mọi environment, versioned
- `services/<name>/overlays/<env>/` chứa Kustomize patches — chỉ override những gì khác nhau giữa các môi trường
- `appsets/` chứa ArgoCD ApplicationSet — không sửa khi thêm service mới (nhờ git generator)

**Prerequisite từ Day 20:** Cấu trúc này là mở rộng của monorepo pattern đã học. Thêm vào: Helm chart encapsulation + ApplicationSet generator-driven discovery.

### 3.2 Helm Chart cho Microservice

Mỗi microservice cần Helm chart với các resource cơ bản. Đây là base chart tối thiểu cho production:

```yaml
# services/api-service/base/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "<chart-name>.fullname" . }}
  labels:
    app.kubernetes.io/name: {{ include "<chart-name>.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "<chart-name>.name" . }}
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "<chart-name>.name" . }}
        app.kubernetes.io/instance: {{ .Release.Name }}
        app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.livenessPath }}
              port: http
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readinessPath }}
              port: http
          resources:
            requests:
              memory: {{ .Values.resources.requests.memory }}
              cpu: {{ .Values.resources.requests.cpu }}
            limits:
              memory: {{ .Values.resources.limits.memory }}
              cpu: {{ .Values.resources.limits.cpu }}
```

**Base values.yaml** — dùng chung cho mọi environment:

```yaml
# services/api-service/base/values.yaml
replicaCount: 2

image:
  repository: ghcr.io/<org>/api-service
  tag: "v1.0.0"          # Override bằng overlay
  pullPolicy: IfNotPresent

service:
  port: 8080
  type: ClusterIP

probes:
  livenessPath: /health/live
  readinessPath: /health/ready

resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

### 3.3 Kustomize Overlay cho Environment

Kustomize cho phép override values mà không sửa base chart. Đây là cách chúng ta triển khai multi-environment:

```yaml
# services/api-service/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: dev

replicas:
  - count: 1

images:
  - name: ghcr.io/<org>/api-service
    newTag: "dev-latest"   # Dev luôn dùng tag cố định

patches:
  - path: resources-patch.yaml
```

```yaml
# services/api-service/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-staging

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: staging

replicas:
  - count: 2

images:
  - name: ghcr.io/<org>/api-service
    newTag: "v1.0.1"      # Tag được update qua PR promotion
```

```yaml
# services/api-service/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-prod

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: prod

replicas:
  - count: 3

images:
  - name: ghcr.io/<org>/api-service
    newTag: "v1.0.0"      # Production: immutable tag, không latest

patches:
  - path: resources-patch.yaml
    # staging/prod đều cần resource limits cao hơn dev
```

### 3.4 ApplicationSet Auto-Detect Service

**Vấn đề:** Nếu dùng static list generator trong ApplicationSet, mỗi lần thêm service mới phải sửa manifest. Điều này vi phạm nguyên tắc GitOps: manifest chỉ thay đổi khi có commit trong Git.

**Giải pháp:** Dùng **git generator** để scan directory trong apps-repo, tự động tạo Application cho mỗi service.

```yaml
# appsets/services-generator.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: services-generator
  namespace: argocd
spec:
  generators:
    # Git generator: scan directory trong apps-repo
    - git:
        repoURL: https://github.com/<org>/apps-repo.git
        revision: HEAD
        directories:
          - path: services/*/overlays/dev
        # Kết quả: mỗi directory matching pattern tạo 1 set params

  template:
    metadata:
      name: "{{path.basenameNormalized}}-dev"
      labels:
        app-type: microservice
        environment: dev
    spec:
      project: default
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: "{{path}}/../../"   # Trỏ về base chart
        kustomize:
          # ArgoCD build Helm + Kustomize inline
          nameSuffix: -dev
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basenameNormalized}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

**Khi thêm service mới (vd: `notification-service`):**

```
services/
  notification-service/
    base/
    overlays/
      dev/
      staging/
      prod/
```

Commit và push → git generator phát hiện directory mới → ArgoCD tự động tạo Application mà không sửa manifest nào.

### 3.5 Image Tag Strategy

Image tag là cách duy nhất để ArgoCD biết version nào đang chạy. Chọn sai tag strategy = không có deterministic rollback, không có audit.

| Strategy | Ví dụ | Ưu điểm | Nhược điểm |
|---|---|---|---|
| `latest` | `api-service:latest` | Đơn giản | Không deterministic, không rollback được, CI ghi đè lẫn nhau |
| Immutable tag (semver) | `api-service:v1.2.3` | Rõ ràng, human-readable | Cần discipline để không reuse tag |
| Git SHA | `api-service:a3f8c2d` | 100% deterministic, commit-linked | Khó đọc, dài |
| Date-based | `api-service:2026-05-15-001` | Biết ngày build | Không link về code, collision có thể |

**Best practice cho production:**

```yaml
# CI pipeline push image với cả 3 tag
- docker push ghcr.io/<org>/api-service:v1.2.3        # semver (primary)
- docker push ghcr.io/<org>/api-service:a3f8c2d       # git sha (immutable)
- docker push ghcr.io/<org>/api-service:latest        # chỉ dùng cho dev
```

**ArgoCD values cho production:**

```yaml
# services/api-service/overlays/prod/values.yaml
image:
  tag: "v1.2.3"    # Immutable, không bao giờ là latest
```

### 3.6 Promotion Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                  GITOPS PROMOTION WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  dev (auto-sync)        staging (PR-gated)      prod (manual)  │
│  ┌─────────────┐        ┌─────────────┐         ┌────────────┐ │
│  │ CI: build   │        │ Dev tạo PR │         │ Staging    │ │
│  │ push        │───────▶│ update tag │───────▶ │ verified   │ │
│  │ latest/dev  │        │ → staging  │         │ → Manual   │ │
│  └─────────────┘        └──────┬──────┘         │   approval │ │
│                                │                └─────┬──────┘ │
│                                ▼                      │        │
│                         ┌─────────────┐               │        │
│                         │ CI: auto    │               │        │
│                         │ promote to  │               │        │
│                         │ staging tag │               │        │
│                         └─────────────┘               │        │
│                                                        ▼        │
│                                                 ┌─────────────┐ │
│                                                 │ argocd app  │ │
│                                                 │ sync prod   │ │
│                                                 │ (approval   │ │
│                                                 │  required)  │ │
│                                                 └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Dev — Auto-sync:** ArgoCD ApplicationSet có `spec.syncPolicy.automated` → mỗi khi có commit mới vào branch, ArgoCD tự sync. Không cần human intervention.

**Staging — PR-gated:** Khi developer muốn promote lên staging, họ tạo PR thay đổi image tag trong overlay staging. CI chạy integration test, merge approval → CI commit tag update → ArgoCD sync.

**Production — Manual approval:** ArgoCD có built-in sync policy với `spec.syncPolicy.automated.approval: required`. Production sync chỉ xảy ra khi có người approve trong ArgoCD UI/CLI.

### 3.7 Rollback

Rollback trong GitOps có 2 chiến lược bổ sung cho nhau:

**Chiến lược 1 — Git revert (preferred cho audit trail):**

```bash
# Rollback production về version cũ
git checkout main
git pull
git revert HEAD                    # Tạo commit mới, revert thay đổi trước đó
git push origin main

# ArgoCD phát hiện drift → sync về commit mới (version cũ)
argocd app sync api-service-prod
```

**Chiến lược 2 — ArgoCD sync previous revision (emergency):**

```bash
# Khi cần rollback ngay lập tức (incident)
argocd app get api-service-prod --revision 42   # Xem revision trước
argocd app sync api-service-prod --revision 42  # Sync về revision đó

# Lưu ý: ArgoCD revision vẫn tham chiếu Git commit
# Nên sau đó commit Git revert để audit trail đồng bộ
git revert HEAD
git push origin main
```

**Nguyên tắc:** Luôn dùng Git revert sau ArgoCD sync revision để đảm bảo Git state = cluster state. Nếu không, lần sync tiếp theo ArgoCD sẽ lại apply version mới.

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 Helm-only vs Kustomize-only vs Helm + Kustomize

| Tiêu chí | Helm-only | Kustomize-only | Helm + Kustomize |
|---|---|---|---|
| Override values | `-f values-dev.yaml` | `patchesStrategicMerge` | Kustomize gọi Helm |
| Template flexibility | Tuyệt đối (Go template) | Hạn chế (Kustomize transforms) | Helm bên trong, Kustomize bên ngoài |
| Learning curve | Cao (Helm template syntax) | Thấp (declarative overlays) | Trung bình |
| Phù hợp khi | Chart phức tạp, nhiều conditional logic | Nhiều env giống nhau, ít logic | Cần cả hai: Helm cho chart, Kustomize cho env |
| ArgoCD support | Native (`helm`) | Native (`kustomize`) | Native (builds inline) |
| Test locally | `helm template` / `helm install --dry-run` | `kubectl kustomize` | Cả hai |
| K8s native | Không (Helm custom logic) | Có (pure K8s manifests) | Có (Kustomize) |

**Kết luận:** Helm + Kustomize là best practice cho microservices vì:
- Helm chart đóng gói service logic (templates, helpers, dependencies)
- Kustomize overlay quản lý environment differences (replicas, resources, namespaces)
- ArgoCD hỗ trợ cả hai trong cùng 1 Application: `spec.source.helm` + `spec.source.kustomize`

### 4.2 ApplicationSet Generator Selection

| Generator | Use case | Dynamic? |
|---|---|---|
| `list` | Static list tường minh | Không |
| `git` | Scan directory trong repo | Có |
| `cluster` | Deploy đến nhiều cluster | Có |
| `matrix` | Kết hợp 2 generators | Có |
| `merge` | Merge params từ nhiều nguồn | Có |

**Trade-off: git generator vs list generator**

| Tiêu chí | List Generator | Git Generator |
|---|---|---|
| Thêm service mới | Sửa ApplicationSet manifest | Chỉ cần thêm folder mới |
| Audit trail | Manifest change = git commit | Folder change = git commit |
| Blast radius khi sửa | ApplicationSet manifest sai → ảnh hưởng tất cả app | Không, mỗi service độc lập |
| Complexity | Đơn giản | Cao hơn, cần hiểu path variables |
| CI/CD tight coupling | Cao (phải update appset trong CI) | Thấp (CI chỉ push code, appset tự phát hiện) |

**Recommendation:** Dùng git generator cho service discovery. Đây là pattern được nhiều team áp dụng khi có từ 5-10+ microservices.

### 4.3 Promotion Gate Strategy

**Pattern 1: Branch-based promotion**

```
feature → dev (auto-merge) → staging (PR) → main → production (manual)
```

- **Ưu điểm:** Rõ ràng, mỗi môi trường có branch riêng
- **Nhược điểm:** Merge conflict khi nhiều feature cùng promotion, branch proliferation

**Pattern 2: Tag-based promotion (recommended)**

```
CI push image → tag v1.2.3-rc.1 → staging → integration test → promote to prod
```

- **Ưu điểm:** Không merge conflict, deterministic version, CI-driven
- **Nhược điểm:** Cần CI pipeline phức tạp hơn

**Pattern 3: GitOps-native (file-based)**

```
Overlay staging chỉ update image tag trong values-staging.yaml
Promotion = git commit tag update → ArgoCD sync
```

- **Ưu điểm:** Simplest, GitOps purist
- **Nhược điểm:** Không có automated testing gate

**Best practice cho từng context:**

| Context | Promotion Strategy |
|---|---|
| Cá nhân / học tập | Branch-based, manual promotion |
| Small team (< 5 dev) | Tag-based, PR gate cho staging |
| Startup | Tag-based + ArgoCD approval cho prod |
| Enterprise | Tag-based + automated testing + security scan + approval |
| Bank / regulated | Full gate: scan + test + approval + audit log |

### 4.4 Performance & Operational Complexity

**ApplicationSet reconcile latency:**

- ApplicationSet controller reconcile mỗi 3 phút (mặc định)
- Git generator: thêm thời gian clone repo + scan directory
- Với 50 services × 3 envs = 150 Application, mỗi reconcile tạo ~150 API calls
- **Implication:** Thêm service mới có thể mất 3 phút để ArgoCD phát hiện

**Giảm latency:**

```yaml
# Tăng tần suất reconcile cho dev cluster
spec:
  generators:
    - git:
        repoURL: ...
        revision: HEAD
        directories:
          - path: services/*/overlays/dev
  # Thêm: refresh annotation khi push
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

**Scaling considerations:**

- ArgoCD server có thể handle 1000+ Application (production cluster)
- ApplicationSet không tạo thêm load đáng kể trừ khi generator chạy trên repo lớn
- Git generator scan toàn bộ repo → repo > 1GB sẽ chậm → dùng shallow clone

### 4.5 Security Baseline

**Bắt buộc cho production:**

```yaml
# 1. Không dùng image tag latest cho prod
image:
  tag: "v1.2.3"   # Immutable semver, không latest

# 2. Immutable tag + registry immutability cho prod.
# IfNotPresent tránh pull thừa; chỉ dùng Always khi còn floating tag ở dev.
image:
  pullPolicy: IfNotPresent

# 3. SecurityContext bắt buộc
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# 4. ServiceAccount không dùng default
serviceAccount:
  name: api-service-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456:role/api-service-role
```

---

## 5. Hands-on Lab — 60 phút

### 5.1 Mục tiêu Lab

Hôm nay bạn sẽ:
1. Tạo 3 Helm chart base (api-service, worker-service, frontend-service)
2. Tạo Kustomize overlay cho dev, staging, prod-like
3. Tạo ApplicationSet với git generator để auto-detect service
4. Triển khai cả 3 service lên 3 environment bằng ArgoCD
5. Thực hiện promotion dev → staging (tạo PR update tag)
6. Thực hiện rollback

### 5.2 Chuẩn bị

**Kiểm tra cluster và ArgoCD đã sẵn sàng:**

```bash
# Đảm bảo kind cluster đang chạy
kind get clusters
# Output mong đợi: capstone

# Kiểm tra ArgoCD đã cài (từ Day 32)
kubectl get pods -n argocd
# Output mong đợi: argocd-... (server, repo-server, application-controller đều Running)

# Kiểm tra ArgoCD credentials
argocd login --grpc-web --insecure localhost:8080 \
  --username admin \
  --password $(kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath='{.data.password}' | base64 -d)
```

**Clone apps-repo skeleton:**

```bash
# Tạo apps-repo nếu chưa có (hoặc fork từ template)
GIT_ORG="your-org"
mkdir -p ~/capstone/apps-repo
cd ~/capstone/apps-repo
git init
git remote add origin https://github.com/${GIT_ORG}/apps-repo.git

# Tạo cấu trúc folder
mkdir -p services/api-service/{base,overlays}/{dev,staging,prod}
mkdir -p services/worker-service/{base,overlays}/{dev,staging,prod}
mkdir -p services/frontend-service/{base,overlays}/{dev,staging,prod}
mkdir -p appsets
```

### 5.3 Step 1 — Tạo Helm Chart Base cho api-service

```bash
cd ~/capstone/apps-repo/services/api-service/base

# Tạo Chart.yaml
cat > Chart.yaml <<'EOF'
apiVersion: v2
name: api-service
description: API service Helm chart for capstone
type: application
version: 0.1.0
appVersion: "v1.0.0"
EOF

# Tạo values.yaml
cat > values.yaml <<'EOF'
replicaCount: 2

image:
  repository: ghcr.io/<ORG>/api-service
  tag: "v1.0.0"
  pullPolicy: IfNotPresent

service:
  port: 8080
  type: ClusterIP

probes:
  livenessPath: /health/live
  readinessPath: /health/ready

resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop:
      - ALL
EOF
```

**Tạo Deployment template:**

```bash
mkdir -p templates

cat > templates/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    app.kubernetes.io/name: {{ include "api-service.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "api-service.name" . }}
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "api-service.name" . }}
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.livenessPath }}
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readinessPath }}
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
EOF
```

**Tạo Service template:**

```bash
cat > templates/service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    app.kubernetes.io/name: {{ include "api-service.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    app.kubernetes.io/name: {{ include "api-service.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
EOF
```

**Tạo _helpers.tpl (required cho Helm):**

```bash
cat > templates/_helpers.tpl <<'EOF'
{{/*
Expand the name of the chart.
*/}}
{{- define "api-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "api-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "api-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}
EOF
```

**Tạo values riêng cho từng overlay:**

```bash
# Dev overlay values
cat > overlays/dev/values-overrides.yaml <<'EOF'
replicaCount: 1
image:
  tag: "dev-latest"
resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "256Mi"
    cpu: "250m"
EOF

# Staging overlay values
cat > overlays/staging/values-overrides.yaml <<'EOF'
replicaCount: 2
image:
  tag: "v1.0.0"
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
EOF

# Prod overlay values
cat > overlays/prod/values-overrides.yaml <<'EOF'
replicaCount: 3
image:
  tag: "v1.0.0"
  pullPolicy: Always
resources:
  requests:
    memory: "256Mi"
    cpu: "200m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
autoscaling:
  enabled: true
EOF
```

### 5.4 Step 2 — Tạo Kustomize Overlays

**Tạo kustomization.yaml cho mỗi environment:**

```bash
# Dev overlay
cat > overlays/dev/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: dev

# Merge values từ Helm chart với overrides
patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: api-service
      spec:
        replicas: 1
    target:
      kind: Deployment

images:
  - name: ghcr.io/<ORG>/api-service
    newTag: "dev-latest"
EOF

# Staging overlay
cat > overlays/staging/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-staging

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: staging

patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: api-service
      spec:
        replicas: 2
    target:
      kind: Deployment

images:
  - name: ghcr.io/<ORG>/api-service
    newTag: "v1.0.0"
EOF

# Prod overlay
cat > overlays/prod/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-prod

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: prod

patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: api-service
      spec:
        replicas: 3
    target:
      kind: Deployment

images:
  - name: ghcr.io/<ORG>/api-service
    newTag: "v1.0.0"
    # CRITICAL: Không dùng latest cho production
EOF
```

**Lặp lại Step 1 & 2 cho worker-service và frontend-service** (tương tự, chỉ thay tên service và port):

```bash
# Tạo nhanh worker-service base từ api-service
cp -r ~/capstone/apps-repo/services/api-service \
       ~/capstone/apps-repo/services/worker-service
# Sửa: Chart.yaml, values.yaml, templates, port 8081

# Tạo nhanh frontend-service base
cp -r ~/capstone/apps-repo/services/api-service \
       ~/capstone/apps-repo/services/frontend-service
# Sửa: Chart.yaml, values.yaml, templates, port 3000
```

**Verify Helm + Kustomize build locally:**

```bash
# Test Helm template
cd ~/capstone/apps-repo/services/api-service/base
helm template api-service . --debug | head -50

# Test Kustomize build
cd ~/capstone/apps-repo/services/api-service/overlays/dev
kustomize build . | head -30
# Output mong đợi: Deployment + Service manifests với namespace=api-service

cd ~/capstone/apps-repo/services/api-service/overlays/staging
kustomize build . | head -30
# Output mong đợi: Deployment + Service manifests với namespace=api-service-staging
```

### 5.5 Step 3 — Tạo ApplicationSet với Git Generator

```bash
cat > ~/capstone/apps-repo/appsets/services-generator.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-dev
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/<ORG>/apps-repo.git
        revision: HEAD
        directories:
          # Mỗi service/overlays/dev tạo ra 1 Application
          - path: services/*/overlays/dev
            exclude: false

  template:
    metadata:
      name: "{{path.basenameNormalized}}-dev"
      labels:
        apps-group: microservices
        environment: dev
      annotations:
        argocd.argoproj.io/manifest-generate-paths: "."
    spec:
      project: default
      source:
        repoURL: https://github.com/<ORG>/apps-repo.git
        targetRevision: HEAD
        # path trỏ về overlay directory
        path: "{{path}}"
        kustomize:
          # Kustomize build overlay
          commonLabels:
            app.kubernetes.io/managed-by: argocd
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basenameNormalized}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
          - ApplyOutOfSyncOnly=true
EOF
```

**Tạo staging ApplicationSet:**

```bash
cat > ~/capstone/apps-repo/appsets/services-staging.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-staging
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/<ORG>/apps-repo.git
        revision: HEAD
        directories:
          - path: services/*/overlays/staging

  template:
    metadata:
      name: "{{path.basenameNormalized}}-staging"
      labels:
        apps-group: microservices
        environment: staging
    spec:
      project: default
      source:
        repoURL: https://github.com/<ORG>/apps-repo.git
        targetRevision: HEAD
        path: "{{path}}"
        kustomize:
          commonLabels:
            app.kubernetes.io/managed-by: argocd
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basenameNormalized}}-staging"
      syncPolicy:
        # Staging: KHÔNG có automated sync
        # Chỉ sync khi có PR approval
        syncOptions:
          - CreateNamespace=true
          - ApplyOutOfSyncOnly=true
EOF
```

**Apply ApplicationSet:**

```bash
cd ~/capstone/apps-repo

# Thêm appsets folder vào git (nếu chưa có trong repo)
git add appsets/
git commit -m "feat: add ApplicationSet generators for dev and staging"
git push origin main

# Apply vào cluster
kubectl apply -f appsets/services-generator.yaml
kubectl apply -f appsets/services-staging.yaml

# Verify ApplicationSet tạo được bao nhiêu Application
argocd appset list
# Output mong đợi:
# microservices-dev      microservices-staging
# 3 apps generated       3 apps generated
```

**Kiểm tra Application tự động được tạo:**

```bash
argocd app list
# Output mong đợi:
# api-service-dev        https://...  Synced   Healthy
# worker-service-dev     https://...  Synced   Healthy
# frontend-service-dev   https://...  Synced   Healthy

# Xem chi tiết 1 app
argocd app get api-service-dev
# Output mong đợi: Deployment + Service details, sync status
```

### 5.6 Step 4 — Thực hiện Promotion dev → staging

**Promotion là quá trình update image tag trong staging overlay qua PR:**

```bash
# Checkout feature branch cho promotion
git checkout -b promote/v1.0.0-to-staging

# Update image tag trong staging overlay
# (Giả lập: CI đã test image v1.0.0 trên dev và approve)
sed -i 's/newTag: "v1.0.0"/newTag: "v1.0.0"/' \
  services/api-service/overlays/staging/kustomization.yaml

# Thêm git diff để xác nhận
git diff services/api-service/overlays/staging/kustomization.yaml
# Output mong đợi:
# - newTag: "dev-latest"
# + newTag: "v1.0.0"
# (hoặc: tag thay đổi từ phiên bản cũ → mới)

git add services/api-service/overlays/staging/
git commit -m "promote(api-service): v1.0.0 -> staging

- Image tag bumped: dev-latest -> v1.0.0
- Tested on dev environment
- CI pipeline: lint ✓ test ✓ build ✓"
git push origin promote/v1.0.0-to-staging
```

**Tạo Pull Request:**

```bash
gh pr create \
  --title "promote(api-service): v1.0.0 to staging" \
  --body "$(cat <<'EOF'
## Promotion Summary

| Service | Current Staging | Next Staging |
|---|---|---|
| api-service | dev-latest | v1.0.0 |

## CI Pipeline Status
- [x] lint
- [x] test
- [x] build
- [x] security scan (trivy)

## Rollback Plan
Nếu staging có vấn đề: revert PR này, ArgoCD sẽ sync lại version cũ.

🤖 Generated with [Claude Code](https://claude.ai)
EOF
)" \
  --base main
```

**Sau khi merge PR:**

```bash
# ArgoCD staging namespace phát hiện drift → sync
argocd app sync api-service-staging --force
# Hoặc đợi 3 phút để ArgoCD tự reconcile

# Verify sync
argocd app get api-service-staging
# Output mong đợi:
# Name:               api-service-staging
# Sync Status:        Synced
# Health Status:      Healthy
# Image:              ghcr.io/<ORG>/api-service:v1.0.0
```

### 5.7 Step 5 — Rollback (Git revert)

**Scenario: Staging deploy bị lỗi sau promotion**

```bash
# Git revert: tạo commit mới revert thay đổi promotion
git checkout main
git pull
git revert HEAD

# Verify revert commit được tạo
git log --oneline -3
# Output mong đợi:
# Revert "promote(api-service): v1.0.0 -> staging"
# promote(api-service): v1.0.0 -> staging

git push origin main

# ArgoCD phát hiện drift → tự sync về version cũ
argocd app get api-service-staging --watch
# Output mong đợi: sync thành công với tag cũ
```

**Emergency rollback bằng ArgoCD revision (khi không đợi được Git):**

```bash
# Xem revision history
argocd app history api-service-staging
# Output mong đợi:
# REVISION  STATUS    CAUSE
# 5         Synced    Promo v1.0.0
# 4         Synced    Promo dev-latest

# Sync về revision 4 (version cũ)
argocd app sync api-service-staging --revision 4

# Sau đó commit Git revert để sync audit trail
git revert HEAD
git push origin main
```

### 5.8 Troubleshooting

**ApplicationSet tạo Application trùng tên:**

```
Error: ApplicationSet ... would create application ... which already exists
```
→ Có 2 ApplicationSet cùng scan 1 path. Kiểm tra `appsets/` để không overlap giữa dev và staging generator.

**ArgoCD không thấy ApplicationSet mới:**

```bash
# Kiểm tra ApplicationSet controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=applicationset-controller --tail=50

# Refresh ApplicationSet
argocd appset get microservices-dev
argocd appset sync microservices-dev
```

**Kustomize build fail trong ArgoCD:**

```bash
# Test local trước
cd ~/capstone/apps-repo/services/api-service/overlays/dev
kustomize build .
# Error: field xxx is not allowed → sửa kustomization.yaml

# Sau khi sửa, push lên Git
git add . && git commit -m "fix: kustomization.yaml" && git push
argocd app sync api-service-dev --force
```

**Image không pull được:**

```bash
# Kiểm tra secret cho container registry
kubectl get secret -n api-service | grep image
# Nếu thiếu: tạo imagePullSecrets
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<GITHUB_USER> \
  --docker-password=<GITHUB_TOKEN> \
  -n api-service
```

**Namespace không tồn tại:**

```yaml
# ArgoCD syncPolicy có CreateNamespace=true
# Nhưng namespace phải được tạo bằng ArgoCD namespace resource hoặc:
kubectl create namespace api-service
```

---

## 6. Kiểm tra hiểu bài

### Câu 1 — Giải thích concept

Tại sao `latest` tag là anti-pattern trong production GitOps? Trình bày ít nhất 2 lý do kèm scenario cụ thể.

### Câu 2 — Chọn approach

Một team có 8 microservices, mỗi service deploy lên 4 environment. Team muốn thêm service mới mà không phải sửa ApplicationSet manifest. Hãy đề xuất cấu trúc repo và generator phù hợp, kèm justification.

### Câu 3 — Debug scenario

ArgoCD Application `api-service-prod` hiển thị **OutOfSync** nhưng khi check `kubectl get pods` thì pod đang chạy đúng version. Nguyên nhân có thể là gì? Trình bày 3 nguyên nhân và cách verify.

### Câu 4 — Thiết kế promotion workflow

Thiết kế promotion workflow cho hệ thống có:
- 3 environment: dev, staging, production
- 1 platform engineer + 3 developer
- Yêu cầu: dev auto-sync, staging qua PR + integration test, production qua manual approval

### Câu 5 — Refactor config

Cho ApplicationSet sau. Sửa để thêm environment `preview` deploy vào namespace riêng, không auto-sync:

```yaml
spec:
  generators:
    - git:
        directories:
          - path: services/*/overlays/dev
  template:
    spec:
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

---

## 7. Tóm tắt cuối ngày

### 3 ý quan trọng nhất

1. **Apps repo structure chuẩn:** Helm chart base cho service logic + Kustomize overlay cho environment differences. Mỗi component đúng 1 responsibility.
2. **ApplicationSet git generator = auto-discovery:** Thêm service mới chỉ cần thêm folder, không sửa ApplicationSet manifest. Git commit = single source of truth cho mọi thay đổi.
3. **Promotion qua Git PR, không qua ArgoCD CLI:** Image tag update trong Git → ArgoCD sync → deterministic, auditable, rollback được. ArgoCD CLI/UI chỉ dùng cho emergency.

### Output đã tạo ra

```
~/capstone/apps-repo/
├── services/
│   ├── api-service/
│   │   ├── base/
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml
│   │   │   └── templates/
│   │   │       ├── _helpers.tpl
│   │   │       ├── deployment.yaml
│   │   │       └── service.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── prod/
│   ├── worker-service/      (same structure)
│   └── frontend-service/    (same structure)
└── appsets/
    ├── services-generator.yaml  # Dev: auto-sync
    └── services-staging.yaml    # Staging: PR-gated

Cluster state (ArgoCD):
  api-service-dev        (Synced, Healthy)
  worker-service-dev     (Synced, Healthy)
  frontend-service-dev   (Synced, Healthy)
  api-service-staging    (Synced/OutOfSync sau promotion)
  worker-service-staging
  frontend-service-staging
```

### Kiến thức chuẩn bị cho Day 34

Day 34 sẽ xây CI/CD pipeline hoàn chỉnh: GitHub Actions build/test/push image, auto-bump image tag trong apps-repo qua PR, Prometheus/Grafana dashboard, alert rules. Apps layer hôm nay là nền tảng để CI pipeline update vào.

---

## 8. Tham khảo thêm

- [ArgoCD ApplicationSet Generators](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators/)
- [ArgoCD Kustomize Support](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)
- [Helm + Kustomize Best Practices](https://helm.sh/docs/topics/chart_best_practices/)
- [GitOps Engineering Blog: ApplicationSet at Scale](https://akuity.io/blog)
- [ArgoCD Sync Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/sync_policy/)
