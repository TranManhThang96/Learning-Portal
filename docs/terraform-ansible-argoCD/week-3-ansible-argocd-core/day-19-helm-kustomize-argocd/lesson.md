# Day 19 - Helm, Kustomize, Overlays với ArgoCD

**Thời lượng:** 2 tiếng (30 phút lý thuyết + 30 phút deep dive + 60 phút lab)
**Mục tiêu đầu ra:** Triển khai 1 microservice lên 3 môi trường qua Helm + 1 microservice lên 3 môi trường qua Kustomize, override resources/replicas theo env.

---

## 1. Mục tiêu ngày học

Sau ngày hôm nay, học viên sẽ:

- **Hiểu** cách ArgoCD repo-server render Helm chart và Kustomize overlay server-side, không phụ thuộc client-side tools
- ** Thiết kế** base/overlay pattern cho 1 microservice deploy đa môi trường (dev/staging/prod) với DRY principle
- **Override** Helm values qua ArgoCD Application spec bằng 3 cách: valueFiles, inline `values:`, và `--helm-set` parameters
- **Kết hợp** Helm chart (làm upstream/base) với Kustomize overlay (tinh chỉnh per-env) qua `--enable-helm` hoặc multi-source pattern
- **Phân tích** trade-off Helm-only vs Kustomize-only vs Helm+Kustomize và chọn đúng approach theo team context (size, enterprise, regulated industry)
- **Triển khai** production-ready `api-service` lên 2 env qua Helm chart và 3 env qua Kustomize overlay trong lab thực tế

---

## 2. Bối cảnh thực tế

### Câu chuyện: Khi "nhanh" trở thành "đắt"

Team bạn có microservice `api-service`. Buổi sprint planning, PO yêu cầu deploy lên 3 môi trường: dev, staging, prod.

Cách tiếp cận "ngu dại" mà nhiều team vẫn làm:

```
manifests/
├── api-service-dev/
│   ├── deployment.yaml       # image: api-service:v1.0.0, replicas: 1
│   ├── service.yaml
│   └── configmap.yaml
├── api-service-staging/
│   ├── deployment.yaml       # image: api-service:v1.0.0, replicas: 2
│   ├── service.yaml
│   └── configmap.yaml
└── api-service-prod/
    ├── deployment.yaml       # image: api-service:v1.0.0, replicas: 5
    ├── service.yaml
    └── configmap.yaml
```

3 tháng sau, team có 8 microservice. Cấu trúc thành:

```
manifests/
├── api-service-{dev,staging,prod}/
├── auth-service-{dev,staging,prod}/
├── payment-service-{dev,staging,prod}/
├── notification-service-{dev,staging,prod}/
└── ... (8 service × 3 env = 24 thư mục)
```

Các vấn đề phát sinh:
- **Drift不一致**: staging/prod deployment.yaml thiếu `readinessProbe` vì lúc tạo staging folder, deployment.yaml base chưa có probe. 3 tháng sau ai đó copy lại file cũ → prod không có probe
- **Không DRY**: 80% nội dung giống nhau, chỉ khác replicas, image tag, resource requests
- **Merge conflict đau**: merge 2 branch, mỗi branch sửa 1 file trong 1 thư mục khác nhau → conflict trên 24 file
- **Audit thất bại**: không biết ai sửa gì, vì sao prod khác staging
- **Human error**: update image tag ở dev nhưng quên update staging/prod

### Giải pháp: 1 source of truth, khác biệt qua mechanism

Thay vì copy-paste manifest, ta dùng:

1. **Helm chart**: manifest dạng Go template, khác biệt qua `values-{env}.yaml`
2. **Kustomize overlay**: manifest raw YAML, khác biệt qua strategic-merge patch

Cả 2 đều **declarative**, đều **GitOps-compatible**, đều **ArgoCD-native**.

### ArgoCD render engine: server-side, không client

```
┌─────────────────────────────────────────────────────┐
│                   ArgoCD Architecture               │
│                                                     │
│  ┌──────────────┐    ┌──────────────────────────┐  │
│  │ Git Repo     │    │ argocd-repo-server pod    │  │
│  │ (source of   │───▶│  - clone Git             │  │
│  │  truth)      │    │  - helm template /       │  │
│  └──────────────┘    │    kustomize build       │  │
│                      │  - cache by revision SHA │  │
│                      └──────────┬───────────────┘  │
│                                 │ rendered YAML   │
│                                 ▼                  │
│                      ┌──────────────────────────┐  │
│                      │ argocd-application-      │  │
│                      │ controller               │  │
│                      │  - diff vs live cluster  │  │
│                      │  - apply OutOfSync       │  │
│                      └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Điểm mấu chốt: **ArgoCD không dùng `helm install` hay `kubectl apply` client-side**. Repo-server chạy `helm template` hoặc `kustomize build` server-side, trả về manifest thuần YAML cho controller.

---

## 3. Kiến thức nền tảng

### 3.1 ArgoCD render Helm: workflow chi tiết

```
Git Repository
  │
  │ (1) argocd-repo-server clone vào /tmp/helmcache/<sha>/
  │
  ▼
  │
  │ (2) helm dependency update (nếu Chart.yaml có dependencies)
  │
  ▼
  │
  │ (3) helm template <release-name> <chart-path> \
  │       -f values.yaml \
  │       -f values-staging.yaml \
  │       --set image.tag=v1.2.3 \
  │       --namespace staging \
  │       --api-versions k8s/v1
  │
  ▼
  │
  │ (4) Trả về danh sách Kubernetes YAML manifests
  │
  ▼
  │
  │ (5) argocd-application-controller so sánh với live cluster
  │
  ▼
  │
  │ (6) Nếu OutOfSync → apply manifests
```

**Lưu ý quan trọng:**
- ArgoCD dùng **Helm template mode** (client-side render), không dùng Tiller (Helm v2 server-side)
- `helm template` không validate resource schema (khác với `helm install` có Helm SDK validate)
- ArgoCD repo-server cache manifest theo **revision SHA** của Git commit — restart pod mất cache

### 3.2 Application spec cho Helm

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-staging
  namespace: argocd
spec:
  project: team-platform
  source:
    # Git source
    repoURL: https://github.com/acme/apps-repo.git
    targetRevision: main
    path: charts/api-service

    # Helm-specific config
    helm:
      # Tên release (optional, mặc định = application name)
      releaseName: api-service

      # Danh sách values files theo thứ tự merge
      # File sau override file trước
      valueFiles:
        - values.yaml           # default values
        - values-staging.yaml   # staging overrides

      # Inline values (override valueFiles)
      # Precedence cao nhất
      values: |
        replicaCount: 3
        image:
          repository: ghcr.io/acme/api-service
          tag: "v1.2.3"

      # CLI-style --set parameters
      # Precedence cao nhất trong 3 cách
      parameters:
        - name: image.tag
          value: "v1.2.3"
        - name: replicaCount
          value: "3"
          # forceString: true  # cho giá trị cần string dù value schema int

      # Helm chart version (semver)
      version: "1.2.0"

      # Pass credentials cho private chart repos
      passCredentials: false

      # Skip schema validation (nếu chart không có values.schema.json)
      skipSchemaValidation: false

  destination:
    server: https://kubernetes.default.svc
    namespace: staging

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

**Helm values precedence (từ thấp đến cao):**

```
Chart.yaml default
  │
  ▼
values.yaml (default)
  │
  ▼
values-{env}.yaml (env-specific)
  │
  ▼
valueFiles[] trong spec.source.helm.valueFiles (theo thứ tự)
  │
  ▼
spec.source.helm.values (inline YAML string)
  │
  ▼
spec.source.helm.parameters (--set, force override)
```

### 3.3 Helm chart từ external / upstream registry

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx
  namespace: argocd
spec:
  project: team-platform
  source:
    # Không có path, chỉ có chart + repoURL
    chart: ingress-nginx
    repoURL: https://kubernetes.github.io/ingress-nginx
    targetRevision: "4.10.0"

    helm:
      releaseName: ingress-nginx
      valueFiles:
        - values.yaml

      values: |
        controller:
          service:
            type: NodePort      # dev: NodePort thay vì LoadBalancer
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
          replicaCount: 1

  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
```

**Khi nào dùng upstream chart:**
- cert-manager, nginx-ingress, prometheus, grafana, external-secrets, velero, metrics-server
- Không nên fork chart để customize nếu chỉ cần override vài values
- Dùng multi-source pattern (phần 3.5) để giữ values trong team repo

### 3.4 Multi-source Application (enterprise pattern)

Cho phép 1 Application lấy chart từ upstream repo, values từ team repo:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager-prod
  namespace: argocd
spec:
  project: team-platform
  sources:
    # Source 1: upstream Helm chart (cert-manager)
    - repoURL: https://charts.jetstack.io
      chart: cert-manager
      targetRevision: v1.15.0
      helm:
        releaseName: cert-manager
        valueFiles:
          - $values/applications/cert-manager/values-prod.yaml

    # Source 2: team repo chứa values files (ref: $values)
    - repoURL: https://github.com/acme/gitops-repo.git
      targetRevision: main
      ref: values
      path: applications/cert-manager
```

**Cấu trúc Git repo cho multi-source:**

```
gitops-repo/
├── applications/
│   └── cert-manager/
│       ├── values-prod.yaml   # team repo values
│       ├── values-staging.yaml
│       └── application.yaml
└── infra/
    └── clusters/
        └── kind/
```

`$values/applications/cert-manager/values-prod.yaml` = join source 2 (path) + file path.

### 3.5 ArgoCD render Kustomize: workflow

```
Git Repository (kustomize/api-service/)
  │
  │ (1) argocd-repo-server clone
  │
  ▼
  │
  │ (2) kustomize build overlays/staging
  │     - Load overlays/staging/kustomization.yaml
  │     - Load bases: [../base]
  │     - Apply patches (strategic merge / JSON6902)
  │     - Apply transformers (commonLabels, namePrefix, etc.)
  │     - Resolve images:
  │         ghcr.io/acme/api-service:v1.2.3
  │         → ghcr.io/acme/api-service:v1.2.4 (override)
  │
  ▼
  │
  │ (3) Trả về merged Kubernetes YAML
  │
  ▼
  │
  │ (4) ArgoCD diff và apply
```

**Application spec cho Kustomize:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-staging
  namespace: argocd
spec:
  project: team-platform
  source:
    repoURL: https://github.com/acme/apps-repo.git
    targetRevision: main
    path: kustomize/api-service/overlays/staging

    # Kustomize-specific overrides
    kustomize:
      # Tiền tố thêm vào tất cả resource names
      # CẢNH BÁO: làm đổi Service name → DNS resolution fail
      # namePrefix: staging-

      # Nhãn chung cho tất cả resources
      commonLabels:
        environment: staging
        team: platform

      # Override image tag/digest
      images:
        # Format: original=override
        - ghcr.io/acme/api-service:v1.2.3
        - ghcr.io/acme/api-service=v1.2.4
        # Hoặc chỉ override tag:
        # - ghcr.io/acme/api-service:stable

      # Override replica count trực tiếp
      replicas:
        - name: api-service
          count: 3
        - name: worker-service
          count: 2

  destination:
    server: https://kubernetes.default.svc
    namespace: staging
```

### 3.6 Base / Overlay pattern (Kustomize idiomatic)

```
services/api-service/
├── base/
│   ├── kustomization.yaml         # Định nghĩa resources + bases
│   ├── deployment.yaml            # Template: replicas: null, tag: VERSION
│   ├── service.yaml               # Template: labels: {}
│   ├── configmap.yaml             # App config (chung cho tất cả env)
│   ├── _namespace.yaml            # Namespace definition
│   └── _networkpolicy.yaml        # Baseline network policy
│
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml     # bases: [../../base]
    │   ├── replicas-patch.yaml     # replicas: 1
    │   ├── resources-patch.yaml   # requests: 100m/128Mi
    │   └── env-patch.yaml         # env: ENV=dev
    │
    ├── staging/
    │   ├── kustomization.yaml
    │   ├── replicas-patch.yaml     # replicas: 3
    │   ├── resources-patch.yaml   # requests: 250m/256Mi
    │   ├── ingress-patch.yaml     # host: api-staging.acme.com
    │   └── hpa-patch.yaml
    │
    └── prod/
        ├── kustomization.yaml
        ├── replicas-patch.yaml     # replicas: 5
        ├── resources-patch.yaml   # requests: 500m/512Mi
        ├── pdb-patch.yaml         # PodDisruptionBudget
        ├── autoscaler-patch.yaml # HPA
        ├── networkpolicy-patch.yaml
        └── tolerations-patch.yaml
```

**Nguyên tắc phân chia base vs overlay:**

| Nằm ở base | Nằm ở overlay |
|---|---|
| Probe configuration (health endpoint chung) | Replica count |
| Resource limit (không giới hạn) | Resource requests |
| Label + selector structure | Image tag |
| ConfigMap template (key name) | Ingress host, TLS |
| Service port | Environment variables |
| Network policy baseline | PDB, HPA |
| Deployment strategy (RollingUpdate) | Tolerations, nodeSelector |

### 3.7 Combine Helm + Kustomize: 3 patterns

#### Pattern A: `helmCharts` bên trong Kustomize (`--enable-helm`)

Kustomize hỗ trợ render Helm chart như một phần của kustomization.yaml:

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

helmCharts:
  - name: api-service
    repo: https://charts.bitnami.com
    version: "1.0.0"
    releaseName: api-service
    valuesFile: values.yaml
    # namespace: api
    # includeCRDs: false

# Sau khi render Helm, Kustomize áp tiếp transformers:
commonLabels:
  team: platform
  environment: production
```

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

helmCharts:
  - name: api-service
    valuesFiles:
      - values-staging.yaml
    parameters:
      - name: replicaCount
        value: "3"

# ArgoCD config cần có:
# data:
#   kustomize.buildOptions: "--enable-helm"
```

**Ưu điểm:** Helm chart từ upstream, team customize qua Kustomize overlay
**Nhược điểm:** ArgoCD cần `--enable-helm` flag, cần repo-server restart

#### Pattern B: ArgoCD multi-source (recommended cho enterprise)

Xem phần 3.4. Clean separation: upstream chart + team values.

#### Pattern C: Render Helm trước, commit manifests, Kustomize patch sau

```bash
helm template api-service charts/api-service \
  -f values.yaml -f values-staging.yaml \
  --output-dir /tmp/rendered

cd /tmp/rendered
kustomize build overlays/staging-patch > manifests.yaml
git add manifests.yaml
```

**Không recommended** vì mất reproducibility (Helm không còn là source of truth).

---

## 4. Deep Dive & Trade-offs

### 4.1 Comparison Matrix: Helm-only vs Kustomize-only vs Helm+Kustomize

| Tiêu chí | Helm-only | Kustomize-only | Helm + Kustomize |
|---|---|---|---|
| **Learning curve** | Cao (Go template, Sprig, flow control) | Thấp (pure YAML, patch) | Cao nhất |
| **Templating power** | Rất mạnh (loop, condition, functions, lượng) | Yếu (chỉ patch, replacement) | Mạnh |
| **Cross-team reuse** | Xuất sắc (chart registry, Helm Hub, version semver) | Yếu (copy folder) | Tốt |
| **Override per env** | values-{env}.yaml | overlay folder | values + overlay |
| **Lint/validate pre-apply** | `helm lint`, `helm template` | `kustomize build` | Cả 2 |
| **Diff readability** | Khó đọc (template vs rendered) | Dễ đọc (raw YAML patch) | Trung bình |
| **Secret management** | values + SealedSecret/ExternalSecret/Vault | overlay + SealedSecret | Tương tự Helm-only |
| **ArgoCD integration** | Native (helm.* fields) | Native (kustomize.* fields) | Multi-source / kustomize+helm |
| **Chart registry** | Artifact Hub, private Harbor | Không có | Phụ thuộc Helm |
| **Dependencies management** | Chart dependencies với versioning | Không có | Phụ thuộc Helm |
| **JSON6902 patch** | Không native (chỉ strategic merge) | Full support | Kustomize phần |
| **Helm library chart** | Hỗ trợ (common _helpers) | Không | Helm-only |
| **Repo size growth** | Chart nhỏ + values = fast clone | Nhiều YAML base nhưng không có binary | Trung bình |
| **IDE support** | VS Code + "Helm" extension, IntelliJ | VS Code + "Kustomize" extension | Cả 2 |
| **CI validation** | `helm lint`, `helm template --dry-run` | `kustomize build` | Cả 2 |
| **Upgrade path** | `helm upgrade --atomic`, rollback tự động | Manual hoặc ArgoCD sync | Phụ thuộc Helm |
| **DRY level** | Cao (template + values) | Cao (patch only diff) | Cao nhất |

### 4.2 Best Practice theo Context

| Context | Approach | Lý do |
|---|---|---|
| **Cá nhân / học tập** | Kustomize-only | Đơn giản, học nhanh, Git history clean |
| **Startup, small team (<5 dev)** | Kustomize-only hoặc Helm-only đơn giản | 1 ngôn ngữ duy nhất, ít cognitive load |
| **Mid-size team (5-20 dev)** | Helm chart do platform team xuất, values do app team | Phân chia ownership rõ |
| **Enterprise (20+ dev, nhiều team)** | Multi-source: upstream chart + team repo values | Platform team bảo trì chart, app team customize values |
| **Bank / regulated industry** | Helm + Kustomize + signed chart + multi-source + AppProject restriction | Audit trail, version pinning, separation of concerns, RBAC |
| **Deploy upstream chart (nginx-ingress, cert-manager, external-secrets)** | Multi-source + values overlay | Không fork chart, update upstream dễ dàng |
| **Service mesh (Istio, Linkerd)** | Helm-only (chart phức tạp) | Chart có logic phức tạp, Kustomize không đủ |
| **Monorepo đơn lẻ (all service 1 repo)** | Kustomize base/overlay | Đơn giản, tất cả trong 1 repo |

### 4.3 Performance Considerations

**Helm:**
- `helm template` chậm hơn `kustomize build` khoảng 2-3x cho chart lớn (500+ resources)
- Helm chart với `dependencies:` cần `helm dependency update` trước mỗi render → thêm 3-10s
- **Cache strategy:** ArgoCD repo-server cache rendered manifests theo Git revision SHA. Khi restart pod, toàn bộ cache mất → CPU spike
  ```bash
  # Kiểm tra repo-server cache size
  kubectl exec -n argocd deploy/argocd-repo-server -- df -h /tmp/helm?
  ```
- Helm chart với nhiều subchart (dependency tree sâu) tăng thời gian render tuyến tính

**Kustomize:**
- `kustomize build` nhanh vì chỉ là YAML merge (không template engine)
- Không có dependency resolution → cache đơn giản hơn
- Image resolution qua `imgpkg` bundle cho large-scale: giảm network call

**repo-server scaling:**
```yaml
# argocd-repo-server horizontal autoscaling (ArgoCD v2.8+)
spec:
  repo:
    replicas: 2   # Mặc định 1, tăng khi nhiều app
```

### 4.4 Security Considerations

**Helm chart từ public registry:**
- Verify provenance: chart provenance file (.prov) chứa SHA256 của chart + signatures
  ```bash
  helm pull prometheus-community/prometheus --prov
  helm verify prometheus-xxx.tgz
  ```
- Cosign verification (Sigstore):
  ```bash
  cosign verify --certificate-identity-regexp=".*@acme.com" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    ghcr.io/bitnamicontainers/bitnami/nginx:1.25
  ```

**passCredentials anti-pattern:**
```yaml
# NGU DẠI - passCredentials: true gửi Git token cho Helm chart install hook
# Chỉ dùng khi chart thực sự cần credentials (private chart repo)
helm:
  passCredentials: true   # Token bị gửi đến tất cả chart URLs
```

**Kustomize security:**
- Strategic merge patch an toàn hơn JSON6902 (không thể inject field ngoài schema)
- Không bao giờ commit secret plaintext trong overlay
- Dùng `.spec.secretGenerator` với `literals:` để generate hash-suffixed Secret (an toàn hơn literal trong manifest)

**Image security:**
- Pin image digest thay vì tag trong production:
  ```yaml
  # Thay vì:
  images:
    - ghcr.io/acme/api-service:v1.2.3
  # Dùng:
  images:
    - ghcr.io/acme/api-service@sha256:abc123...
  ```
- ArgoCD Image Updater (tách biệt) tự động update digest khi tag mới push

### 4.5 Common Pitfalls & Debugging

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `kustomization.yaml field "helmCharts" requires --enable-helm` | Kustomize buildOptions chưa có `--enable-helm` | `kubectl patch configmap argocd-cm -n argocd --type merge -p '{"data":{"kustomize.buildOptions":"--enable-helm"}}'` |
| Helm render OK local, ArgoCD lỗi | Chart version không tồn tại trên repo-server cache | `argocd repo rm <repo> && argocd repo add <repo>` |
| ArgoCD báo "rendered manifests contain a resource that already exists" | 2 Application deploy cùng 1 resource (trùng namespace/name) | Kiểm tra AppProject `destination.namespaces` và `spec.resources` |
| `images:` trong kustomize không apply | Tên image trong base không match override pattern | Debug: `kustomize build overlays/staging \| grep image` |
| namePrefix làm Service name đổi | `staging-api-service` thay vì `api-service` → DNS resolution fail | Bỏ namePrefix, dùng label/annotation để phân biệt môi trường |
| replicas drift bởi HPA | ArgoCD thấy replicas: 5 nhưng HPA scale down còn 2 → OutOfSync liên tục | Day 18 đã học: `spec.ignoreDifferences` hoặc `spec.syncPolicy.syncOptions: ServerSideApply` + `health.lua` |
| Helm valueFiles override không đúng thứ tự | valueFiles [a, b] nhưng bị ghi đè bởi `helm.values` inline | Đọc precedence: parameters > values > valueFiles |
| Probe path khác nhau giữa env mà chỉ có 1 base | Probe `/health` trên dev nhưng `/api/health` trên prod → health check fail trên prod | Tách probe ra overlay hoặc dùng Helm conditional trong template |
| `helm dependency update` fail trong ArgoCD | Chart repository không accessible từ repo-server | Check `data.repositories` trong argocd-cm, thêm `caCerts` nếu dùng self-signed registry |

---

## 5. Hands-on Lab

**Mục tiêu lab:** Deploy `api-service` microservice lên 3 môi trường (dev/staging/prod) qua 2 approach: Helm chart và Kustomize overlay.

### Pre-requisites

Kind cluster đã có ArgoCD từ Day 17/18. Verify:

```bash
kind get clusters
kubectl get pods -n argocd
# Cần thấy: argocd-server, argocd-repo-server, argocd-application-controller RUNNING

argocd version --short
kubectl version --short
helm version   # Helm 3.13+
```

Nếu cluster đã xóa, tái tạo:

```bash
kind create cluster --name argocd-lab
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl patch svc argocd-server -n argocd -p '{"spec":{"type":"LoadBalancer"}}'
# Chờ 2-3 phút cho ArgoCD pod ready
```

### Step 1: Tạo Git repository cho lab

Tạo thư mục lab với cấu trúc dual (Helm + Kustomize cùng tồn tại):

```bash
mkdir -p gitops-lab-day19
cd gitops-lab-day19

# Tạo cấu trúc thư mục
mkdir -p charts/api-service/templates
mkdir -p kustomize/api-service/base
mkdir -p kustomize/api-service/overlays/{dev,staging,prod}
mkdir -p applications/helm
mkdir -p applications/kustomize

git init
git remote add origin https://github.com/YOUR_USERNAME/gitops-lab-day19.git
```

### Step 2: Tạo Helm chart cho api-service

**`charts/api-service/Chart.yaml`:**

```yaml
apiVersion: v2
name: api-service
description: API service Helm chart for multi-environment deployment
type: application
version: "0.1.0"
appVersion: "v0.1.0"

dependencies: []
```

**`charts/api-service/values.yaml` (base/default):**

```yaml
# Default values for api-service chart

replicaCount: 1

image:
  repository: ghcr.io/acme/api-service
  pullPolicy: IfNotPresent
  # tag được override per env

service:
  type: ClusterIP
  port: 8080
  targetPort: http

ingress:
  enabled: false
  className: nginx
  annotations: {}
  # host: ""  # override per env

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi

livenessProbe:
  httpGet:
    path: /health/live
    port: http
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health/startup
    port: http
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30

env:
  LOG_LEVEL: info
  ENVIRONMENT: default
  # DB_HOST được override per env

configMap:
  CACHE_TTL: "300"
  MAX_CONNECTIONS: "100"

commonLabels:
  app.kubernetes.io/name: api-service
  app.kubernetes.io/managed-by: Helm
  app.kubernetes.io/part-of: platform
```

**`charts/api-service/values-staging.yaml`:**

```yaml
replicaCount: 3

image:
  tag: "v0.1.0-staging"

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 1Gi

ingress:
  enabled: true
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
  host: api-staging.acme.com

env:
  LOG_LEVEL: debug
  ENVIRONMENT: staging
  DB_HOST: db-staging.acme.svc

livenessProbe:
  initialDelaySeconds: 15
  periodSeconds: 15

readinessProbe:
  initialDelaySeconds: 10
```

**`charts/api-service/values-prod.yaml`:**

```yaml
replicaCount: 5

image:
  tag: "v0.1.0"

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi

ingress:
  enabled: true
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
  host: api.acme.com

env:
  LOG_LEVEL: warn
  ENVIRONMENT: production
  DB_HOST: db-prod.acme.svc

commonLabels:
  app.kubernetes.io/managed-by: Helm
  app.kubernetes.io/part-of: platform
  cost-center: "platform-team"
```

**`charts/api-service/templates/_helpers.tpl`:**

```yaml
{{/* vim: set filetype=mustache: */}}
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
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "api-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "api-service.labels" -}}
app.kubernetes.io/name: {{ include "api-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.commonLabels.app.kubernetes.io/part-of | default "platform" }}
{{- if .Values.commonLabels.cost-center }}
cost-center: {{ .Values.commonLabels.cost-center }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "api-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "api-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "api-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "api-service.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

**`charts/api-service/templates/deployment.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    {{- include "api-service.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "api-service.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "api-service.selectorLabels" . | nindent 8 }}
        {{- if .Values.podLabels }}
        {{- toYaml .Values.podLabels | nindent 8 }}
        {{- end }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        checksum/secrets: {{ include (print $.Template.BasePath "/secrets.yaml") . | sha256sum }}
    spec:
      containers:
        - name: api-service
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {{ include "api-service.fullname" . }}-config
          env:
            - name: LOG_LEVEL
              value: "{{ .Values.env.LOG_LEVEL }}"
            - name: ENVIRONMENT
              value: "{{ .Values.env.ENVIRONMENT }}"
            - name: DB_HOST
              value: "{{ .Values.env.DB_HOST }}"
            - name: CACHE_TTL
              valueFrom:
                configMapKeyRef:
                  name: {{ include "api-service.fullname" . }}-config
                  key: CACHE_TTL
            - name: MAX_CONNECTIONS
              valueFrom:
                configMapKeyRef:
                  name: {{ include "api-service.fullname" . }}-config
                  key: MAX_CONNECTIONS
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          livenessProbe:
            {{- toYaml .Values.livenessProbe | nindent 12 }}
          readinessProbe:
            {{- toYaml .Values.readinessProbe | nindent 12 }}
          startupProbe:
            {{- toYaml .Values.startupProbe | nindent 12 }}
          {{- if .Values.securityContext.enabled }}
          securityContext:
            {{- toYaml .Values.securityContext.pod | nindent 12 }}
          {{- end }}
```

**`charts/api-service/templates/service.yaml`:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    {{- include "api-service.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "api-service.selectorLabels" . | nindent 4 }}
```

**`charts/api-service/templates/configmap.yaml`:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "api-service.fullname" . }}-config
  labels:
    {{- include "api-service.labels" . | nindent 4 }}
data:
  CACHE_TTL: "{{ .Values.configMap.CACHE_TTL }}"
  MAX_CONNECTIONS: "{{ .Values.configMap.MAX_CONNECTIONS }}"
```

**`charts/api-service/templates/ingress.yaml`:**

```yaml
{{- if .Values.ingress.enabled -}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    {{- include "api-service.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "api-service.fullname" . }}
                port:
                  number: {{ .Values.service.port }}
{{- end }}
```

### Step 3: Tạo Kustomize base và overlays

**`kustomize/api-service/base/kustomization.yaml`:**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

commonLabels:
  app.kubernetes.io/name: api-service
  app.kubernetes.io/managed-by: kustomize
  app.kubernetes.io/part-of: platform

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml
  - namespace.yaml
```

**`kustomize/api-service/base/namespace.yaml`:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: api-service
  labels:
    app.kubernetes.io/name: api-service
```

**`kustomize/api-service/base/deployment.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  namespace: api-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api-service
    spec:
      containers:
        - name: api-service
          image: ghcr.io/acme/api-service:v0.1.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: LOG_LEVEL
              value: info
            - name: CACHE_TTL
              value: "300"
            - name: MAX_CONNECTIONS
              value: "100"
          livenessProbe:
            httpGet:
              path: /health/live
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          startupProbe:
            httpGet:
              path: /health/startup
              port: http
            initialDelaySeconds: 0
            periodSeconds: 5
            failureThreshold: 30
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

**`kustomize/api-service/base/service.yaml`:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: api-service
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: http
      name: http
  selector:
    app.kubernetes.io/name: api-service
```

**`kustomize/api-service/base/configmap.yaml`:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-service-config
  namespace: api-service
data:
  CACHE_TTL: "300"
  MAX_CONNECTIONS: "100"
```

**`kustomize/api-service/overlays/dev/kustomization.yaml`:**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-dev

bases:
  - ../../base

namePrefix: dev-

commonLabels:
  environment: dev

patches:
  - path: replicas-patch.yaml
    target:
      kind: Deployment
  - path: resources-patch.yaml
    target:
      kind: Deployment
```

**`kustomize/api-service/overlays/dev/replicas-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 1
```

**`kustomize/api-service/overlays/dev/resources-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: api-service
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          env:
            - name: LOG_LEVEL
              value: debug
            - name: ENVIRONMENT
              value: dev
```

**`kustomize/api-service/overlays/staging/kustomization.yaml`:**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-staging

bases:
  - ../../base

commonLabels:
  environment: staging

patches:
  - path: replicas-patch.yaml
    target:
      kind: Deployment
  - path: resources-patch.yaml
    target:
      kind: Deployment
  - path: image-patch.yaml
    target:
      kind: Deployment
```

**`kustomize/api-service/overlays/staging/replicas-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 3
```

**`kustomize/api-service/overlays/staging/resources-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: api-service
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          env:
            - name: LOG_LEVEL
              value: debug
            - name: ENVIRONMENT
              value: staging
            - name: DB_HOST
              value: db-staging.acme.svc
```

**`kustomize/api-service/overlays/staging/image-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: api-service
          image: ghcr.io/acme/api-service:v0.1.0-staging
```

**`kustomize/api-service/overlays/prod/kustomization.yaml`:**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-prod

bases:
  - ../../base

commonLabels:
  environment: production
  cost-center: platform-team

patches:
  - path: replicas-patch.yaml
    target:
      kind: Deployment
  - path: resources-patch.yaml
    target:
      kind: Deployment
  - path: image-patch.yaml
    target:
      kind: Deployment
  - path: pdb-patch.yaml
    target:
      kind: Deployment
```

**`kustomize/api-service/overlays/prod/replicas-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 5
```

**`kustomize/api-service/overlays/prod/resources-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: api-service
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 2Gi
          env:
            - name: LOG_LEVEL
              value: warn
            - name: ENVIRONMENT
              value: production
            - name: DB_HOST
              value: db-prod.acme.svc
```

**`kustomize/api-service/overlays/prod/image-patch.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: api-service
          image: ghcr.io/acme/api-service:v0.1.0
```

**`kustomize/api-service/overlays/prod/pdb-patch.yaml`:**

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
  namespace: api-service-prod
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-service
```

### Step 4: Commit và push lên Git

```bash
git add .
git commit -m "Day 19 lab: api-service Helm chart + Kustomize overlays"
git branch -M main
git push -u origin main
```

### Step 5: Lab path A - Deploy api-service qua Helm (staging + prod)

**`applications/helm/api-service-staging.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-helm-staging
  namespace: argocd
  labels:
    app: api-service
    approach: helm
    environment: staging
spec:
  project: team-platform
  source:
    repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
    targetRevision: main
    path: charts/api-service
    helm:
      releaseName: api-service
      valueFiles:
        - values.yaml
        - values-staging.yaml
      values: |
        image:
          tag: "v0.1.0"
  destination:
    server: https://kubernetes.default.svc
    namespace: api-service-staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

**`applications/helm/api-service-prod.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-helm-prod
  namespace: argocd
  labels:
    app: api-service
    approach: helm
    environment: production
spec:
  project: team-platform
  source:
    repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
    targetRevision: main
    path: charts/api-service
    helm:
      releaseName: api-service
      valueFiles:
        - values.yaml
        - values-prod.yaml
      values: |
        image:
          tag: "v0.1.0"
  destination:
    server: https://kubernetes.default.svc
    namespace: api-service-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

Apply và sync:

```bash
kubectl apply -f applications/helm/api-service-staging.yaml
kubectl apply -f applications/helm/api-service-prod.yaml

argocd app list
argocd app sync api-service-helm-staging --force-sync
argocd app sync api-service-helm-prod --force-sync

# Theo dõi sync
argocd app get api-service-helm-staging --watch
argocd app get api-service-helm-prod --watch
```

Verify Helm-rendered manifests:

```bash
argocd app manifests api-service-helm-staging | head -80
```

### Step 6: Lab path B - Deploy api-service qua Kustomize (dev + staging + prod)

**`applications/kustomize/api-service-dev.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-kustomize-dev
  namespace: argocd
spec:
  project: team-platform
  source:
    repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
    targetRevision: main
    path: kustomize/api-service/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: api-service-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

**`applications/kustomize/api-service-staging.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-kustomize-staging
  namespace: argocd
spec:
  project: team-platform
  source:
    repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
    targetRevision: main
    path: kustomize/api-service/overlays/staging
    kustomize:
      images:
        - ghcr.io/acme/api-service:v0.1.0
  destination:
    server: https://kubernetes.default.svc
    namespace: api-service-staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

Apply và sync:

```bash
kubectl apply -f applications/kustomize/api-service-dev.yaml
kubectl apply -f applications/kustomize/api-service-staging.yaml

argocd app sync api-service-kustomize-dev --force-sync
argocd app sync api-service-kustomize-staging --force-sync
```

### Step 7: So sánh diff render output 2 approach

```bash
# Render Helm output
helm template api-service charts/api-service \
  -f charts/api-service/values.yaml \
  -f charts/api-service/values-staging.yaml \
  --namespace api-service-staging \
  > /tmp/helm-staging-rendered.yaml

# Render Kustomize output
kustomize build kustomize/api-service/overlays/staging \
  > /tmp/kustomize-staging-rendered.yaml

# Diff để so sánh
diff /tmp/helm-staging-rendered.yaml /tmp/kustomize-staging-rendered.yaml || true

# Xem manifest count
echo "Helm rendered lines: $(wc -l < /tmp/helm-staging-rendered.yaml)"
echo "Kustomize rendered lines: $(wc -l < /tmp/kustomize-staging-rendered.yaml)"

# Extract resource types
echo "=== Helm resources ==="
grep "^kind:" /tmp/helm-staging-rendered.yaml | sort | uniq -c

echo "=== Kustomize resources ==="
grep "^kind:" /tmp/kustomize-staging-rendered.yaml | sort | uniq -c
```

**Phân tích kết quả:**
- Helm render có thêm `namespace` resource (vì Helm template tự động thêm namespace từ `--namespace`)
- Kustomize dùng `namespace:` field trong kustomization.yaml thay vì Namespace resource riêng
- Labels khác nhau: Helm dùng `app.kubernetes.io/managed-by: Helm`, Kustomize dùng `managed-by: kustomize`

### Step 8: Override Helm parameters qua CLI

```bash
# Override image tag không cần sửa values file
argocd app set api-service-helm-staging --helm-set image.tag=v0.2.0

# Override replica count
argocd app set api-service-helm-staging --helm-set replicaCount=5

# Sync để apply
argocd app sync api-service-helm-staging

# Verify thay đổi
argocd app manifests api-service-helm-staging | grep "replicas:"
```

### Step 9: Combine Helm + Kustomize (Pattern A)

Bật `--enable-helm` trong ArgoCD config:

```bash
kubectl patch configmap argocd-cm -n argocd \
  --type merge \
  -p '{"data":{"kustomize.buildOptions":"--enable-helm"}}'

# Restart repo-server để áp dụng config
kubectl rollout restart deployment argocd-repo-server -n argocd
kubectl rollout status deployment argocd-repo-server -n argocd
```

Tạo overlay dùng `helmCharts` field:

```yaml
# kustomize/nginx-ingress/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: ingress-nginx-dev

helmCharts:
  - name: ingress-nginx
    repo: https://kubernetes.github.io/ingress-nginx
    version: "4.10.0"
    releaseName: ingress-nginx
    namespace: ingress-nginx-dev
    valuesFile: values-dev.yaml

# values-dev.yaml
controller:
  service:
    type: NodePort   # Dev: NodePort thay vì LoadBalancer
  replicaCount: 1
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
```

Apply và verify:

```bash
argocd app create nginx-ingress-dev \
  --repo https://github.com/YOUR_USERNAME/gitops-lab-day19.git \
  --path kustomize/nginx-ingress/overlays/dev \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace ingress-nginx-dev \
  --sync-policy automated \
  --kustomize-replicas=1

argocd app sync nginx-ingress-dev --force-sync
argocd app get nginx-ingress-dev
```

### Step 10: Verify resources trên cluster

```bash
# Helm deployments
kubectl get all -n api-service-staging
kubectl get all -n api-service-prod

# Kustomize deployments
kubectl get all -n api-service-dev
kubectl get all -n api-service-staging

# Check replicas
kubectl get deployment -A -l app.kubernetes.io/name=api-service

# Check resources per env
for ns in api-service-dev api-service-staging api-service-prod; do
  echo "=== $ns ==="
  kubectl get deployment -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.replicas}{"\t"}{.spec.template.spec.containers[0].resources.requests.cpu}{"\t"}{.spec.template.spec.containers[0].resources.requests.memory}{"\n"}{end}'
done
```

**Kết quả mong đợi:**

| Environment | Approach | Replicas | CPU Request | Memory Request |
|---|---|---|---|---|
| dev | Kustomize | 1 | 100m | 128Mi |
| staging (Helm) | Helm | 3 | 250m | 256Mi |
| staging (Kustomize) | Kustomize | 3 | 250m | 256Mi |
| prod | Helm | 5 | 500m | 512Mi |

### Step 11: ApplicationSet preview (Day 22 sneak peek)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: api-service-multienv
  namespace: argocd
spec:
  generators:
    - matrix:
        generators:
          - git:
              repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
              revision: main
              paths:
                - kustomize/api-service/overlays/*
          - clusters:
              selector:
                matchLabels:
                  env: "*"
  template:
    metadata:
      name: "api-service-{{path.basename}}"
    spec:
      project: team-platform
      source:
        repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day19.git
        targetRevision: main
        path: "kustomize/api-service/overlays/{{path.basename}}"
      destination:
        server: "{{server}}"
        namespace: "api-service-{{path.basename}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: false
```

**Day 22 sẽ đi sâu vào:** generators (list, matrix, git, clusters, pull-request), progression strategy, và sync window.

### Step 12: Cleanup

```bash
# Xóa tất cả applications
argocd app delete api-service-helm-staging --cascade
argocd app delete api-service-helm-prod --cascade
argocd app delete api-service-kustomize-dev --cascade
argocd app delete api-service-kustomize-staging --cascade
argocd app delete nginx-ingress-dev --cascade 2>/dev/null || true

# Verify cleanup
argocd app list
kubectl get all -n api-service-dev -o name 2>/dev/null || echo "dev ns clean"
kubectl get all -n api-service-staging -o name 2>/dev/null || echo "staging ns clean"
kubectl get all -n api-service-prod -o name 2>/dev/null || echo "prod ns clean"
```

### Troubleshooting

| Vấn đề | Lệnh debug |
|---|---|
| Application stuck OutOfSync | `argocd app logs api-service-helm-staging` hoặc `kubectl describe app` |
| Helm render lỗi | `argocd app manifests api-service-helm-staging --source-name=api-service` |
| Kustomize build lỗi | `kustomize build kustomize/api-service/overlays/staging 2>&1` |
| Image pull fail | `kubectl describe pod -n <ns>` kiểm tra `ImagePullBackOff` |
| Health probe fail | `kubectl logs <pod> -n <ns>` + `kubectl exec <pod> -n <ns> -- curl localhost:8080/health/live` |
| namePrefix DNS issue | `kubectl get svc -n <ns>` kiểm tra service name có prefix không |
| repo-server OOM (nhiều chart) | `kubectl top pod -n argocd argocd-repo-server-xxxx` |

---

## 6. Kiểm tra hiểu bài

### Câu 1: Khi nào chọn Helm-only vs Kustomize-only vs Helm+Kustomize?

**Đáp án:**
- **Helm-only**: Platform team xuất chart cho app team dùng (internal chart registry), upstream chart phức tạp (Istio, Prometheus), chart có nhiều conditional logic, team đã có Helm expertise
- **Kustomize-only**: Single team in-house service, ưu tiên đơn giản và Git history clean, tất cả manifest trong 1 repo, không cần chart registry
- **Helm+Kustomize**: Dùng upstream chart (nginx-ingress, cert-manager) làm base, app team customize qua Kustomize overlay (multi-source pattern). Phù hợp enterprise multi-team với clear separation: platform = chart owner, app team = values/overlay owner

### Câu 2: Làm sao override image tag chỉ cho prod mà không sửa base Helm chart?

**Đáp án (3 cách):**

```yaml
# Cách 1: values-prod.yaml (recommended)
spec:
  source:
    helm:
      valueFiles:
        - values.yaml
        - values-prod.yaml    # values-prod.yaml chứa: image.tag: "v1.2.3"
```

```bash
# Cách 2: argocd app set CLI (không cần sửa YAML)
argocd app set api-service-prod --helm-set image.tag=v1.2.3
```

```yaml
# Cách 3: inline values (override mạnh nhất)
spec:
  source:
    helm:
      values: |
        image:
          tag: "v1.2.3"
```

### Câu 3: Debug - Application Helm render thành công local, nhưng ArgoCD báo "rendered manifests contain a resource that already exists"

**Đáp án:** Nguyên nhân phổ biến nhất là 2 Application cùng deploy 1 resource trùng namespace + name. Kiểm tra:

```bash
# 1. Tìm tất cả application deploy resource đó
argocd app list -o json | jq '.[] | select(.spec.source.helm.releaseName == "api-service")'

# 2. Kiểm tra resource conflict
kubectl get deployment -A | grep api-service

# 3. Check AppProject namespace restriction
argocd app get api-service-helm-prod | grep "Project:"

# 4. Nếu dùng multi-source, 2 source cùng render 1 resource
# → đổi releaseName của 1 trong 2 source
```

### Câu 4: Trade-off giữa `helm.values` inline (string) vs `valueFiles`?

**Đáp án:**

| Aspect | `valueFiles` | `helm.values` inline |
|---|---|---|
| Git review | Rõ ràng, diff được | Khó review trong YAML đa dòng |
| Precedence | Thấp nhất (bị override) | Cao (chỉ thua parameters) |
| Scalability | Tốt (tách file per env) | Kém (YAML trong spec rất dài) |
| Secret handling | Tốt hơn (file riêng, gitignore) | Risk leak vào Application spec |
| DRY | Tốt (values.yaml chung) | Kém (trùng lặp giữa các spec) |
| ArgoCD UI display | Hiển thị đầy đủ trong "App Details" | Có thể bị truncate |
| Recommendation | **Nên dùng** cho production | Chỉ dùng cho override tạm thời hoặc `--helm-set` |

### Câu 5: Refactor scenario - 5 service × 3 env hiện đang copy folder, refactor sang base/overlay pattern

**Đáp án (decision tree):**

```
1. Đánh giá service structure hiện tại:
   - Tất cả 5 service có cùng template? → Dùng Kustomize base chung
   - Mỗi service có logic Helm template phức tạp? → Dùng Helm chart

2. Migration strategy:
   a. Chọn 1 service làm pilot (vd: api-service)
   b. Tạo base/overlay structure
   c. Verify kustomize build == old manifests (diff trước/sau)
   d. Migrate từng service 1 qua ApplicationSet
   e. Cleanup old folders sau khi ApplicationSet stable

3. Folder structure đề xuất:
   services/
   ├── base/           # Deployment template chung, 1 version duy nhất
   ├── api-service/
   │   └── overlays/{dev,staging,prod}
   ├── auth-service/
   │   └── overlays/{dev,staging,prod}
   └── ...
   # Hoặc mỗi service có base riêng:
   services/
   ├── api-service/
   │   ├── base/
   │   └── overlays/{dev,staging,prod}
   └── auth-service/
       ├── base/
       └── overlays/{dev,staging,prod}
```

---

## 7. Tóm tắt cuối ngày

**Key takeaways:**

1. **ArgoCD render server-side**: repo-server chạy `helm template` hoặc `kustomize build` trong pod, không phụ thuộc client-side Tiller hay kubectl. Cache theo Git revision SHA.

2. **Helm values precedence**: parameters > `helm.values` inline > `valueFiles` (theo thứ tự trong mảng). Ghi nhớ thứ tự này để debug override không hoạt động.

3. **Kustomize base/overlay**: base chứa manifest chuẩn (probe, resource limits, labels), overlay chỉ chứa patches (replicas, image tag, resources). Strategic merge patch cho Deployment, JSON6902 cho advance cases.

4. **3 cách combine Helm + Kustomize**: `--enable-helm` flag trong kustomization.yaml (Pattern A), ArgoCD multi-source (Pattern B, recommended enterprise), Helm render rồi commit manifests (Pattern C, không recommended).

5. **ArgoCD multi-source**: tách upstream chart (upstream repo) và team values (team repo) qua `$values` reference. Pattern chuẩn cho enterprise với clear ownership.

6. **Output lab:**
   - Helm: `api-service-helm-staging` (3 replicas, 250m/256Mi) + `api-service-helm-prod` (5 replicas, 500m/512Mi)
   - Kustomize: `api-service-kustomize-dev` (1 replica) + `api-service-kustomize-staging` (3 replicas)
   - Tất cả chạy trên kind cluster, verify qua `argocd app get`

7. **Chuẩn bị Day 20**: GitOps repo structure - mono repo vs poly repo, infra/apps separation, environment promotion strategy, rollback pattern.

---

## 8. Tham khảo thêm

- [ArgoCD Helm Support](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/)
- [ArgoCD Kustomize Support](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)
- [ArgoCD Multi-Source Applications](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/)
- [ArgoCD kustomize.buildOptions](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#kustomize)
- [Kustomize Helm Charts Integration](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/helmcharts/)
- [Helm Values Precedence](https://helm.sh/docs/chart_template_guide/values_files/)
- [Kustomize Strategic Merge Patch](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches/)
- [Artifact Hub - Chart Registry](https://artifacthub.io/)
- [Bitnami Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [ArgoCD Image Updater](https://argocd-image-updater.readthedocs.io/)

---

**Prepared for Day 20: GitOps Repo Structure**
