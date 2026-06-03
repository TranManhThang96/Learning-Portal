# Day 19 - Cheatsheet: Helm & Kustomize trong ArgoCD

## Mục lục

1. [Helm trong ArgoCD Cheatsheet](#1-helm-trong-argocd-cheatsheet)
2. [Kustomize trong ArgoCD Cheatsheet](#2-kustomize-trong-argocd-cheatsheet)
3. [Helm Values Precedence Diagram](#3-helm-values-precedence-diagram)
4. [Comparison Matrix (15+ tiêu chí)](#4-comparison-matrix-15-tiêu-chí)
5. [Base/Overlay Anti-Patterns](#5-baseoverlay-anti-patterns)
6. [ConfigMap/Secret Rotation Patterns](#6-configmapsecret-rotation-patterns)
7. [Snippet Library](#7-snippet-library)
8. [Render-Side Caching & Performance Tips](#8-render-side-caching--performance-tips)

---

## 1. Helm trong ArgoCD Cheatsheet

### 1.1 Application spec — Helm fields đầy đủ

```yaml
spec:
  source:
    helm:
      # Tên release. ArgoCD dùng mặc định = application name
      releaseName: my-service

      # Files được merge theo thứ tự: file sau override file trước
      # Không chứa secrets plaintext — dùng SealedSecret/ExternalSecret
      valueFiles:
        - values.yaml
        - values-staging.yaml
        - values-prod.yaml

      # Inline values — override valueFiles (trừ parameters)
      # Precedence: parameters > values > valueFiles
      values: |
        replicaCount: 3
        image:
          repository: ghcr.io/acme/my-service
          tag: "v1.2.3"
        resources:
          requests:
            cpu: 500m
            memory: 512Mi

      # --set parameters — override mạnh nhất
      # Dùng cho override tạm thời hoặc từ CLI
      parameters:
        - name: image.tag
          value: "v1.2.3"
          # forceString: true  # ép string (cho type int nhưng cần string)
        - name: replicaCount
          value: "3"

      # Semver chart version. Bắt buộc nếu repo có nhiều version.
      # Khi upgrade chart, cập nhật field này → ArgoCD detect OutOfSync
      version: "1.2.0"

      # Gửi credentials đến ALL chart repository URLs
      # CẢNH BÁO: passCredentials: true gửi Git/Helm repo token
      #            đến tất cả URLs (bao gồm upstream chart URLs)
      # Chỉ bật khi THỰC SỰ cần private chart dependency
      passCredentials: false

      # Bỏ qua JSON schema validation
      # Dùng khi chart không có values.schema.json hoặc muốn override schema
      skipSchemaValidation: false

      # Extra args truyền cho helm template
      # Ví dụ: disable name release prefix
      # skipSchemaValidation: false
```

### 1.2 Helm chart reference — external / upstream

```yaml
# Deploy upstream chart (nginx-ingress, cert-manager, etc.)
spec:
  source:
    chart: ingress-nginx           # Chart name trong repo
    repoURL: https://kubernetes.github.io/ingress-nginx
    targetRevision: "4.10.0"       # Semver
    helm:
      releaseName: ingress-nginx
      valueFiles:
        - values.yaml
```

```bash
# Verify chart exists trước khi dùng
helm search repo ingress-nginx --versions | head -5

# Hoặc dùng OCI registry
helm pull oci://ghcr.io/acme/charts/api-service --version 1.0.0
```

### 1.3 Multi-source với Helm chart

```yaml
spec:
  sources:
    # Source 1: upstream chart (artifact hub)
    - repoURL: https://charts.jetstack.io
      chart: cert-manager
      targetRevision: v1.15.0
      helm:
        releaseName: cert-manager
        valueFiles:
          - $values/applications/cert-manager/values-prod.yaml

    # Source 2: team repo chứa values files
    - repoURL: https://github.com/acme/gitops-repo.git
      targetRevision: main
      ref: values                    # Alias: $values
      path: applications/cert-manager
```

### 1.4 Helm template — local verification

```bash
# Render local mà không cần ArgoCD
helm template my-release charts/api-service \
  -f values.yaml \
  -f values-prod.yaml \
  --namespace production \
  --set image.tag=v1.2.3 \
  --validate   # Helm 3.11+ check schema

# Dry-run với cluster connection (requires kubeconfig)
helm upgrade --install my-release charts/api-service \
  --dry-run=server \
  --namespace production \
  -f values-prod.yaml

# Lint chart (không render)
helm lint charts/api-service \
  -f values-prod.yaml

# Dependency update
helm dependency update charts/api-service
helm dependency build charts/api-service

# Check rendered YAML
helm template my-release charts/api-service | \
  grep -A 20 "kind: Deployment"
```

### 1.5 Helm Chart.yaml — dependency và metadata

```yaml
apiVersion: v2
name: api-service
description: Production-ready API service chart
type: application
version: "0.1.0"
appVersion: "v1.2.3"
keywords:
  - api
  - microservice
home: https://github.com/acme/api-service
sources:
  - https://github.com/acme/api-service
maintainers:
  - name: Platform Team
    email: platform@acme.com

dependencies:
  - name: common
    version: "1.x.x"
    repository: https://charts.bitnami.com
    alias: common
  - name: postgresql
    version: "12.x.x"
    repository: https://charts.bitnami.com
    condition: postgresql.enabled
```

---

## 2. Kustomize trong ArgoCD Cheatsheet

### 2.1 Application spec — Kustomize fields đầy đủ

```yaml
spec:
  source:
    kustomize:
      # Tiền tố thêm vào TẤT CẢ resource names (khuyến nghị: KHÔNG dùng)
      # Side effect: Service name đổi → DNS resolution fail
      # namePrefix: staging-

      # Hậu tố thêm vào TẤT CẢ resource names
      # nameSuffix: "-v2"

      # Nhãn thêm vào TẤT CẢ resources
      # ArgoCD dùng labels này để detect drift
      commonLabels:
        environment: staging
        team: platform
        cost-center: "platform-team"

      # Annotations thêm vào TẤT CẢ resources
      # commonAnnotations:
      #   monitoring.alerts.acme.com/team: platform

      # Override image (tag hoặc digest)
      # Format: original=override  hoặc  original:override
      images:
        - ghcr.io/acme/api-service:v1.0.0
        - ghcr.io/acme/api-service=v1.2.3
        # Hoặc chỉ override tag:
        # - ghcr.io/acme/api-service:stable

      # Override replica count trực tiếp
      # Thay thế replicas field trong Deployment
      replicas:
        - name: api-service
          count: 3
        - name: worker
          count: 2
        - name: api-service
          count: 5
          # Ghi đè entry trước cùng name

      # Label selector cho replicas (Helm template output không có label)
      # replicas:
      #   - name: api-service
      #     count: 3
      #     patchType: strategic   # default: strategic
```

### 2.2 Base kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# Namespace mặc định cho tất cả resources (trừ phi overlay override)
namespace: api-service

# Common labels cho tất cả resources
commonLabels:
  app.kubernetes.io/name: api-service
  app.kubernetes.io/managed-by: kustomize
  app.kubernetes.io/part-of: platform

# Danh sách resources (theo thứ tự load)
resources:
  - namespace.yaml
  - service-account.yaml
  - configmap.yaml
  - deployment.yaml
  - service.yaml
  - ingress.yaml
  - networkpolicy.yaml

# Generators (tạo resource tự động)
# configMapGenerator:
#   - name: app-config
#     literals:
#       - DB_HOST=localhost
#       - LOG_LEVEL=info
#     behavior: merge  # replace | merge | create

# Replicas (base không nên set cố định, để overlay override)
# replicas:
#   - name: api-service
#     count: 0   # Placeholder

# CommonAnnotations cho tất cả resources
commonAnnotations:
  commit_sha: "HEAD"
```

### 2.3 Overlay kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# Override namespace (thay vì dùng Namespace resource)
namespace: api-service-staging

# Reference base (bắt buộc trong mỗi overlay)
bases:
  - ../../base

# Hoặc dùng `resources:` với relative path:
# resources:
#   - ../../base/deployment.yaml
#   - ../../base/service.yaml

# Common labels bổ sung cho overlay (merge với base)
commonLabels:
  environment: staging

# Patches — strategic merge hoặc JSON6902
patches:
  # Strategic merge patch (đơn giản, dùng trong hầu hết trường hợp)
  - path: replicas-patch.yaml
    target:
      kind: Deployment

  # Inline strategic merge patch (cho patch nhỏ)
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: api-service
      spec:
        replicas: 3

  # JSON6902 patch (cho patch phức tạp, insert/remove array element)
  - target:
      group: apps
      version: v1
      kind: Deployment
      name: api-service
    patch: |
      - op: replace
        path: /spec/replicas
        value: 3
      - op: add
        path: /spec/template/spec/tolerations
        value:
          - key: "node-type"
            operator: "Equal"
            value: "compute"
            effect: "NoSchedule"

# Transformers (thay đổi tất cả resources)
transformers:
  - patch-configmap-prefix.yaml
```

### 2.4 Kustomize strategic merge patch

```yaml
# overlays/staging/replicas-patch.yaml
# Thay thế giá trị field cùng tên (không xóa field khác)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service   # Match theo kind + name
spec:
  replicas: 3         # Override field này
  template:
    spec:
      containers:
        - name: api-service   # Match container theo tên
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
```

### 2.5 Kustomize JSON6902 patch

```yaml
# overlays/prod/tolerations-patch.yaml
# Dùng cho: insert/remove array elements, thay đổi nested field không trùng tên
target:
  group: apps
  version: v1
  kind: Deployment
  name: api-service
  # labelSelector: "app=api-service"  # filter theo label

patch: |
  - op: add
    path: /spec/template/spec/tolerations
    value:
      - key: node-type
        operator: Equal
        value: compute
        effect: NoSchedule
  - op: replace
    path: /spec/replicas
    value: 5
  - op: remove
    path: /spec/template/metadata/annotations/sidecar.istio.io/inject
```

### 2.6 Kustomize image transformer

```yaml
# overlays/prod/image-transformer.yaml
# Dùng builtin image transformer — không cần patch thủ công
images:
  # Thay đổi image hoàn toàn (repo + tag)
  - name: ghcr.io/acme/api-service
    newName: ghcr.io/acme/api-service
    newTag: v1.2.3-prod

  # Chỉ thay tag, giữ nguyên repo
  - name: ghcr.io/acme/api-service
    newTag: v1.2.3

  # Digest thay vì tag (production-ready)
  - name: ghcr.io/acme/api-service
    digest: sha256:abc123def456...   # Pin immutable digest
```

### 2.7 Helm chart trong Kustomize (Pattern A)

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# ArgoCD configmap argocd-cm cần có:
# data:
#   kustomize.buildOptions: "--enable-helm"

helmCharts:
  - name: api-service
    repo: https://charts.bitnami.com
    version: "1.0.0"
    releaseName: api-service
    valuesFile: values.yaml
    namespace: api-service
    # includeCRDs: false
    # releaseName: api-service
    # additionalValuesFiles:
    #   - values-staging.yaml

# Sau Helm render, Kustomize tiếp tục apply transformers
commonLabels:
  environment: production
```

```bash
# Build local để verify
kustomize build overlays/prod --enable-helm > /tmp/combined.yaml
```

---

## 3. Helm Values Precedence Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    HELM VALUES PRECEDENCE (low → high)                     │
│                                                                            │
│  1. Chart.yaml (appVersion, version metadata)                               │
│     └─► LOWEST PRIORITY                                                     │
│                                                                            │
│  2. values.yaml  (chart default values)                                     │
│     └─► Overrides Chart.yaml defaults                                       │
│                                                                            │
│  3. values-{env}.yaml  (per-environment, in valueFiles[] order)            │
│     └─► File[0] có priority THẤP NHẤT trong valueFiles[]                   │
│     └─► File[n] có priority CAO NHẤT trong valueFiles[]                    │
│     └─► valueFiles[] = [a, b, c] → c override b, b override a               │
│                                                                            │
│  4. spec.source.helm.values  (inline YAML string in Application)            │
│     └─► OVERRIDE valueFiles[]                                              │
│     └─► ArgoCD render: merged sau khi valueFiles[] resolve                 │
│     └─► Debug tip: ArgoCD UI "App Details" → "Manifest" hiển thị merged     │
│                                                                            │
│  5. spec.source.helm.parameters  (--set key=value)                        │
│     └─► HIGHEST PRIORITY                                                    │
│     └─► Override tất cả trên, kể cả inline values                          │
│     └─► argocd app set --helm-set là cách nhanh nhất để override tạm      │
│                                                                            │
│  DEBUG: Xem merged values                                                   │
│  argocd app manifests <app-name> --source-name <source> | head -50          │
│  helm template <release> <chart> [flags] --debug                            │
│                                                                            │
│  PRECEDENCE TEST:                                                          │
│  values.yaml:          replicaCount: 1                                      │
│  values-staging.yaml:  replicaCount: 3                                       │
│  helm.values:          replicaCount: 5                                       │
│  parameters:           name: replicaCount, value: "10"                       │
│  → Final rendered:  replicas: 10                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Comparison Matrix (15+ tiêu chí)

| Tiêu chí | Helm-only | Kustomize-only | Helm + Kustomize |
|---|---|---|---|
| **Learning curve** | Cao (Go template, Sprig functions, flow control) | Thấp (pure YAML, patch semantics) | Cao nhất (2 paradigm) |
| **Templating power** | Mạnh (loop, condition, helpers, lượng giá trị) | Yếu (patch + replacement chỉ) | Mạnh (Helm phần) |
| **Cross-team reuse** | Xuất sắc (chart registry, Helm Hub, OCI, semver) | Yếu (folder copy hoặc git submodule) | Tốt (Helm base) |
| **Override per env** | values-{env}.yaml + --set | overlay folder | values + overlay |
| **Lint/validate** | `helm lint`, `helm template --validate` | `kustomize build` (always validates) | Cả 2 |
| **Diff readability** | Khó (template diff vs rendered diff) | Dễ (raw YAML patch, git-friendly) | Trung bình |
| **ArgoCD native fields** | `spec.source.helm.*` | `spec.source.kustomize.*` | Multi-source hoặc `--enable-helm` |
| **Chart registry** | Artifact Hub, Harbor, GCS, OCI | Không có | Phụ thuộc Helm |
| **Dependencies** | Chart dependencies (Chart.yaml) với version lock | Không có | Phụ thuộc Helm |
| **JSON6902 patch** | Không native (chỉ strategic merge trong template) | Full support | Kustomize phần |
| **Library chart (common)** | Hỗ trợ (`common` chart import) | Không có | Helm-only |
| **DRY level** | Cao (template + values) | Cao (patch only diff) | Cao nhất |
| **Git history quality** | Mixed (values files rõ ràng, template khó diff) | Tuyệt vời (tất cả YAML, git blame hiệu quả) | Phụ thuộc approach |
| **Helm template complexity** | High (Go template syntax, escaping phức tạp) | N/A | N/A |
| **Upgrade strategy** | `helm upgrade --atomic` (auto rollback) | ArgoCD sync | Phụ thuộc Helm |
| **CI validation** | `helm lint`, `helm template --dry-run=server` | `kustomize build` | Cả 2 |
| **ConfigMap/Secret generation** | Template + values | `configMapGenerator`, `secretGenerator` | Tùy approach |
| **Performance (render)** | Chậm hơn (template engine) | Nhanh (YAML merge) | Trung bình |
| **repo-server cache** | SHA-based revision cache | SHA-based revision cache | SHA-based |
| **Security (secrets)** | values + SealedSecret/Vault | overlay + SealedSecret/Vault | Tương tự Helm-only |
| **Best for** | Platform team xuất chart, upstream phức tạp | Single team, in-house, git-native | Enterprise multi-team |

---

## 5. Base/Overlay Anti-Patterns

### Anti-pattern 1: Overlay quá lớn (copy-to-patch)

```yaml
# ❌ NGU DẠI: Overlay chứa toàn bộ deployment thay vì patch
# overlays/prod/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 5                        # ← chỉ cần cái này
  selector:
    matchLabels:
      app: api-service               # ← trùng base
  template:
    metadata:
      labels:
        app: api-service             # ← trùng base
    spec:
      containers:
        - name: api-service          # ← trùng 100 field
          image: nginx:1.25          # ← chỉ cần override cái này
          ports:
            - containerPort: 80       # ← trùng base
          resources: {}              # ← trùng base
```

**Fix:** Chỉ chứa field cần thay đổi trong patch.

### Anti-pattern 2: Dùng `namePrefix` khi không cần

```yaml
# ❌ NGU DẠI: namePrefix làm đổi tên Service → DNS break
# overlays/staging/kustomization.yaml
namePrefix: staging-    # → Service: "staging-api-service" thay vì "api-service"
```

```yaml
# ✅ ĐÚNG: Không dùng namePrefix. Phân biệt bằng namespace + label.
# overlays/staging/kustomization.yaml
commonLabels:
  environment: staging
namespace: api-service-staging
```

### Anti-pattern 3: Probe path khác nhau mà không tách

```yaml
# ❌ NGU DẠI: dev dùng /health, prod dùng /api/health nhưng base chỉ có 1 probe
# base/deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live   # ← prod app có /api prefix → health check fail
```

**Fix:** Tách probe vào overlay, hoặc dùng Helm conditional:

```yaml
# base/templates/deployment.yaml (Helm)
livenessProbe:
  httpGet:
    path: {{ .Values.probePath | default "/health/live" }}
```

### Anti-pattern 4: Quên `bases` trong overlay

```yaml
# ❌ NGU DẠI: Overlay không reference base → không có manifest gì
# overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:    # ← THIẾU bases: [../../base]
  - deployment.yaml  # ← copy nguyên file vào → mất DRY
```

```yaml
# ✅ ĐÚNG
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
bases:
  - ../../base
patches:
  - path: replicas-patch.yaml
```

### Anti-pattern 5: Namespace resource trùng lặp

```yaml
# ❌ NGU DẠI: Mỗi overlay tạo Namespace riêng → conflict
# overlays/dev/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: api-service-dev
---
# overlays/staging/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: api-service-staging
```

```yaml
# ✅ ĐÚNG: Namespace được reference qua spec.destination.namespace
#          hoặc dùng 1 Namespace resource ở base level duy nhất
# base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: api-service
```

### Anti-pattern 6: Image tag trong base thay vì overlay

```yaml
# ❌ NGU DẠI: Image tag cứng trong base
# base/deployment.yaml
image: ghcr.io/acme/api-service:v1.0.0   # ← không bao giờ thay đổi được
```

**Fix:** Dùng placeholder trong base, override trong overlay:

```yaml
# base/deployment.yaml (Helm)
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"

# base/deployment.yaml (Kustomize)
image: ghcr.io/acme/api-service:VERSION  # placeholder

# overlays/prod/kustomization.yaml
images:
  - name: ghcr.io/acme/api-service
    newTag: v1.2.3
```

### Anti-pattern 7: Resource requests/limits ở overlay thay vì base

```yaml
# ❌ NGU DẠI: limits ở base, requests ở overlay → inconsistency
# base/deployment.yaml
resources:
  limits:
    cpu: 2000m
    memory: 2Gi
---
# overlays/prod/resources-patch.yaml
resources:
  requests:
    cpu: 500m   # limits đã có ở base, giờ thêm requests
```

**Fix:** Đặt cả requests và limits ở cùng 1 file (base hoặc patch).

### Anti-pattern 8: Quên strategic merge target

```yaml
# ❌ NGU DẠI: Patch không match → Kustomize tạo resource mới
# overlays/prod/kustomization.yaml
patches:
  - path: replicas-patch.yaml
    # target: {}   ← THIẾU: không match resource nào → tạo mới
```

```yaml
# ✅ ĐÚNG
patches:
  - path: replicas-patch.yaml
    target:
      kind: Deployment
      name: api-service
```

### Anti-pattern 9: Helm values chứa secrets plaintext

```yaml
# ❌ NGU DẠI: Password trong values file → git history expose
# values-prod.yaml
database:
  password: SuperSecret123!   # ← plaintext → exposed in git history FOREVER
```

```yaml
# ✅ ĐÚNG: Dùng ExternalSecret hoặc SealedSecret
# values-prod.yaml
database:
  password: ""   # placeholder
---
# ExternalSecret reference
# external-secret.yaml (base)
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
    - secretKey: password
      remoteRef:
        key: prod/database
        property: password
```

### Anti-pattern 10: Dùng JSON6902 khi strategic merge đủ

```yaml
# ❌ PHỨC TẠP KHÔNG CẦN: JSON6902 cho việc đơn giản
- target:
    kind: Deployment
    name: api-service
  patch: |
    - op: replace
      path: /spec/replicas
      value: 5
```

```yaml
# ✅ ĐƠN GIẢN HƠN: Strategic merge patch
# overlays/prod/replicas-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 5
```

---

## 6. ConfigMap/Secret Rotation Patterns

### Pattern A: ConfigMapGenerator với hash suffix (Kustomize)

```yaml
# base/kustomization.yaml
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
      - DB_HOST=localhost
    # Tự động thêm hash suffix → tên: app-config-8c6h67t9k9
    # Trigger Pod rollout khi ConfigMap thay đổi
    options:
      disableNameSuffixHash: false   # Mặc định: true = không có hash suffix
```

```yaml
# Reference trong Deployment (Kustomize tự update name)
# base/deployment.yaml
envFrom:
  - configMapRef:
      name: app-config    # Kustomize tự thay = app-config-8c6h67t9k9
```

### Pattern B: Helm checksum annotation (Helm)

```yaml
# base/templates/deployment.yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

```bash
# Khi ConfigMap thay đổi → checksum khác → Pod restart tự động
helm template my-release charts/api-service | grep checksum
# Output: checksum/config: a1b2c3d4e5f6...
```

### Pattern C: ExternalSecret (production)

```yaml
# base/external-secret.yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: api-service
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
    # deletionPolicy: Retain  # giữ Secret khi ExternalSecret bị xóa
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/database
        property: password
    - secretKey: host
      remoteRef:
        key: secret/data/database
        property: host
```

### Pattern D: SealedSecret (GitOps-safe secrets)

```yaml
# SealedSecret — encrypted bằng cluster public key
# Chỉ cluster chạy SealedSecret controller mới giải mã được
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-credentials
  namespace: api-service
spec:
  encryptedData:
    password: AgA...  # Encrypted bằng kubeseal
    host: AgB...
```

```bash
# Tạo SealedSecret từ Secret
kubectl create secret generic db-credentials \
  --from-literal=password=SuperSecret \
  --namespace=api-service \
  -o yaml | kubeseal \
    --controller-name=sealed-secrets \
    --controller-namespace=sealed-secrets \
    -o yaml > sealed-secret.yaml
```

---

## 7. Snippet Library

### 7.1 Production Deployment.yaml (Helm template) với đầy đủ fields

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api-service.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "api-service.labels" . | nindent 4 }}
    {{- with .Values.commonLabels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
  {{- if .Values.deploymentAnnotations }}
  annotations:
    {{- toYaml .Values.deploymentAnnotations | nindent 4 }}
  {{- end }}
spec:
  replicas: {{ .Values.replicaCount }}
  revisionHistoryLimit: {{ .Values.revisionHistoryLimit | default 3 }}
  selector:
    matchLabels:
      {{- include "api-service.selectorLabels" . | nindent 6 }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        {{- include "api-service.selectorLabels" . | nindent 8 }}
        {{- if .Values.podLabels }}
        {{- toYaml .Values.podLabels | nindent 8 }}
        {{- end }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        checksum/values: {{ .Values | toYaml | sha256sum }}
    spec:
      {{- with .Values.topologySpreadConstraints }}
      topologySpreadConstraints:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      terminationGracePeriodSeconds: {{ .Values.terminationGracePeriodSeconds | default 30 }}
      containers:
        - name: api-service
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            {{- range .Values.service.ports }}
            - name: {{ .name }}
              containerPort: {{ .containerPort }}
              protocol: {{ .protocol | default "TCP" }}
            {{- end }}
          envFrom:
            {{- if .Values.configMap.create }}
            - configMapRef:
                name: {{ include "api-service.fullname" . }}-config
            {{- end }}
          env:
            {{- range .Values.env }}
            - name: {{ .name }}
              {{- if .value }}
              value: {{ .value | quote }}
              {{- else if .valueFrom }}
              valueFrom:
                {{- toYaml .valueFrom | nindent 18 }}
              {{- end }}
            {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- if .Values.startupProbe.enabled }}
          startupProbe:
            {{- toYaml .Values.startupProbe | nindent 12 }}
          {{- end }}
          {{- if .Values.livenessProbe.enabled }}
          livenessProbe:
            {{- toYaml .Values.livenessProbe | nindent 12 }}
          {{- end }}
          {{- if .Values.readinessProbe.enabled }}
          readinessProbe:
            {{- toYaml .Values.readinessProbe | nindent 12 }}
          {{- end }}
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]
```

### 7.2 HPA + PDB combination

```yaml
# HPA — Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
  namespace: api-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Pods
          value: 3
          periodSeconds: 15
---
# PDB — PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-service-pdb
  namespace: api-service
spec:
  {{- if ge ($replicas | default 5) 3 }}
  minAvailable: 2
  {{- else }}
  maxUnavailable: 1
  {{- end }}
  selector:
    matchLabels:
      app.kubernetes.io/name: api-service
```

### 7.3 Kustomize JSON6902 patch — thêm và remove array elements

```yaml
# overlays/prod/network-policy-patch.yaml
# Thêm tolerations + remove istio sidecar injection
target:
  group: apps
  version: v1
  kind: Deployment
  name: api-service
patch: |
  - op: add
    path: /spec/template/spec/tolerations
    value:
      - key: node-type
        operator: Equal
        value: compute
        effect: NoSchedule
  - op: add
    path: /spec/template/spec/priorityClassName
    value: high-priority
  - op: remove
    path: /spec/template/metadata/annotations/sidecar.istio.io~1inject
  - op: replace
    path: /spec/replicas
    value: 5
```

### 7.4 Helm `_helpers.tpl` chuẩn

```yaml
{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "api-service.name" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "api-service.fullname" -}}
{{- include "api-service.name" . }}
{{- end }}

{{- define "api-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "api-service.labels" -}}
{{- include "api-service.name" . }}
app.kubernetes.io/name: {{ include "api-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ .Values.commonLabels.app.kubernetes.io/part-of | default .Release.Name }}
{{- range $k, $v := .Values.commonLabels }}
{{- if and (ne $k "app.kubernetes.io/part-of") (ne $k "cost-center") }}
{{ $k }}: {{ $v }}
{{- end }}
{{- end }}
{{- end }}

{{- define "api-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "api-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "api-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- include "api-service.fullname" . }}
{{- else }}
{{- .Values.serviceAccount.name | default "default" }}
{{- end }}
{{- end }}

{{- define "api-service.checksum" -}}
{{- $files := list "configmap.yaml" "secret.yaml" "values.yaml" }}
{{- $checksum := "" }}
{{- range $file := $files }}
{{- if $.Template.Has . }}
{{- $checksum = printf "%s-%s" $checksum (include (printf "api-service.%s" $file) $ | sha256sum) }}
{{- end }}
{{- end }}
{{- $checksum | sha256sum }}
{{- end }}
```

### 7.5 Multi-source Application — upstream chart + team values

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager-prod
  namespace: argocd
  labels:
    app: cert-manager
    owner: platform-team
spec:
  project: team-platform
  sources:
    # Upstream cert-manager chart (read-only, do vendor maintain)
    - repoURL: https://charts.jetstack.io
      chart: cert-manager
      targetRevision: v1.15.0
      helm:
        releaseName: cert-manager
        valueFiles:
          - $values/applications/cert-manager/values-prod.yaml
        parameters:
          - name: installCRDs
            value: "true"

    # Team repo — values files và overlays (team owns)
    - repoURL: https://github.com/acme/gitops-repo.git
      targetRevision: main
      ref: values
      path: applications/cert-manager
---
# applications/cert-manager/values-prod.yaml
# Trong gitops-repo
installCRDs: true
prometheus:
  enabled: true
  servicemonitor:
    enabled: true
resources:
  requests:
    cpu: 100m
    memory: 256Mi
webhook:
  replicas: 2
```

---

## 8. Render-Side Caching & Performance Tips

### 8.1 repo-server cache behavior

```
Git commit SHA abc123
    │
    ▼
repo-server clone /tmp/helmcache/<revision>/
    │
    ▼
helm dependency update (nếu có)
    │
    ▼
helm template → rendered manifests
    │
    ▼
Cache: /tmp/helmcache/<revision>/*.yaml.gz
    │
    ▼
Application controller diff
```

**Cache mất khi:**
- repo-server pod restart (pod reschedule, OOMKill, node reboot)
- ArgoCD upgrade (thường restart repo-server)
- `argocd repo rm` + `argocd repo add`

**Cache hit ratio monitor:**
```bash
kubectl exec -n argocd deploy/argocd-repo-server -- \
  argocd repo-server --metrics

# Prometheus metrics:
# argocd_repo_server_generation_count{repo="github.com/acme/app"}  # render count
# argocd_repo_server_cache_duration_seconds{repo="..."}             # cache timing
```

### 8.2 Performance optimization checklist

```bash
# 1. Giảm chart size — loại bỏ test files và documentation khỏi chart
helm package charts/api-service --sign --key mykey  # production

# 2. Dùng OCI registry cho chart lớn (Helm 3.8+)
helm push oci://ghcr.io/acme/charts/api-service:v1.0.0

# 3. Pre-generate Helm provenance (.prov file)
helm pull prometheus-community/prometheus --prov
# ArgoCD verify provenance khi dùng OCI + cosign

# 4. Kustomize: dùng --enable-alpha-plugins cho large-scale
# ArgoCD config:
# data:
#   kustomize.buildOptions: "--enable-alpha-plugins"

# 5. repo-server horizontal scaling (ArgoCD 2.8+)
kubectl scale deployment argocd-repo-server -n argocd --replicas=2

# 6. Disable dependency update cho chart không cần
# Trong Application spec:
# helm:
#   skipDependencyUpdate: true   # ArgoCD 2.4+

# 7. Chart dependencies: pin exact version
# Chart.yaml
# dependencies:
#   - name: common
#     version: "1.2.3"   # Exact version, không range "1.x"
```

### 8.3 repo-server resource sizing guide

| Cluster size | repo-server replicas | Memory limit | CPU limit |
|---|---|---|---|
| < 50 Applications | 1 (default) | 1Gi | 1 core |
| 50-200 Applications | 2 | 2Gi | 2 cores |
| 200-500 Applications | 3-4 | 4Gi | 4 cores |
| 500+ Applications | 5+ | 8Gi | 8 cores |

```yaml
# argocd-repo-server resource override
# values.yaml (ArgoCD Helm chart)
repo_server:
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
```

### 8.4 Monitor render errors

```bash
# Tìm application render errors
argocd app list -o json | jq '.[] | select(.status.health.status=="Unknown")'

# repo-server logs
kubectl logs -n argocd deploy/argocd-repo-server --tail=100 | \
  grep -E "(error|Error|ERROR|helm template|kustomize)"

# Check application sync status
argocd app get api-service --detailed

# Force refresh (clear cache + re-render)
argocd app sync api-service --force-sync --strategy apply-all
```

---

**Phụ lục: Quick Reference Commands**

```bash
# Helm
helm template <release> <chart> -f values.yaml --debug > /tmp/rendered.yaml
helm lint <chart> -f values-prod.yaml
helm dependency build <chart>

# Kustomize
kustomize build overlays/staging --enable-alpha-plugins > /tmp/rendered.yaml
kustomize edit set image ghcr.io/acme/api-service:v1.2.3

# ArgoCD
argocd app manifests <app-name>          # Xem rendered manifests
argocd app diff <app-name>               # Diff vs live
argocd app sync <app-name> --force-sync  # Force re-render
argocd app set <app-name> --helm-set image.tag=v1.2.3
argocd app unset <app-name> --helm-set image.tag
```
