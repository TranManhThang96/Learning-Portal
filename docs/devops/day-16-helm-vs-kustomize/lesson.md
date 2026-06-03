# Day 16: Helm vs Kustomize — Package & Configuration Management cho Kubernetes

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** vì sao cần package/configuration management trong Kubernetes và vấn đề gì xảy ra khi quản lý manifest thủ công.
2. **Tạo được** một Helm chart hoàn chỉnh với `values.yaml`, template, helpers và deploy lên cluster.
3. **Thiết kế được** Kustomize overlay cho multi-environment (dev/staging/prod) từ một base chung.
4. **Phân biệt được** khi nào dùng Helm, khi nào dùng Kustomize, khi nào kết hợp cả hai — dựa trên context cụ thể.
5. **Debug được** các lỗi thường gặp khi render template, upgrade release, và merge overlay.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Khi bạn có 1 service với 1 environment, quản lý YAML thủ công vẫn ổn. Nhưng thực tế production:

- **10+ services** × **3 environments** (dev/staging/prod) = **30+ bộ manifest** gần giống nhau.
- Mỗi environment khác nhau ở: image tag, replica count, resource limits, ConfigMap values, Ingress host.
- Copy-paste YAML giữa environments → **configuration drift** → deploy sai config lên production.

```
# Không có package management:
manifests/
├── dev/
│   ├── api-deployment.yaml      # 95% giống prod
│   ├── api-service.yaml         # 99% giống prod
│   └── api-ingress.yaml         # chỉ khác host
├── staging/
│   ├── api-deployment.yaml      # copy từ dev, sửa 3 chỗ
│   └── ...
└── prod/
    ├── api-deployment.yaml      # copy từ staging, sửa 5 chỗ
    └── ...
```

### Hậu quả khi làm sai

| Vấn đề | Hậu quả |
|---------|---------|
| Copy-paste YAML giữa envs | Quên update 1 field → deploy config sai lên prod |
| Hardcode values trong manifest | Không reuse được, mỗi service viết lại từ đầu |
| Không version control config changes | Không rollback được khi config sai |
| Inline secret trong manifest | Leak credentials vào Git |

### Hai trường phái giải quyết

1. **Helm** → **Templating approach**: tạo template, inject values khác nhau cho mỗi environment.
2. **Kustomize** → **Patching approach**: giữ base YAML nguyên gốc, patch/overlay cho mỗi environment.

Cả hai đều giải quyết cùng vấn đề nhưng bằng cách tiếp cận khác nhau — giống như so sánh **code generation** vs **inheritance/composition** trong software engineering.

---

## 3. Kiến thức nền tảng

### 3.1 Helm — The Package Manager for Kubernetes

**Analogy cho developer**: Helm giống `npm`/`pip`/`go mod` cho Kubernetes. Một Helm chart giống một package chứa tất cả resource cần thiết để chạy một application.

#### Helm Chart Structure

```
my-chart/
├── Chart.yaml          # Metadata: name, version, description
├── values.yaml         # Default values (như default config)
├── charts/             # Dependencies (sub-charts)
├── templates/          # Go templates cho K8s manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── _helpers.tpl    # Template functions (DRY)
│   ├── NOTES.txt       # Post-install message
│   └── tests/
│       └── test-connection.yaml
└── .helmignore         # Files to ignore
```

#### Các concept chính

| Concept | Giải thích | Analogy |
|---------|-----------|---------|
| **Chart** | Package chứa templates + default values | npm package |
| **Release** | Một instance cụ thể của chart đang chạy trên cluster | `npm install` result |
| **Values** | Parameters để customize chart | Constructor arguments |
| **Template** | YAML với Go template syntax | Code template/generator |
| **Repository** | Nơi lưu trữ và chia sẻ charts | npm registry |
| **Hook** | Actions tại lifecycle events | Lifecycle callbacks |

#### Helm Architecture (v3)

```
┌─────────────────────────────────────────────┐
│                 helm CLI                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Template  │  │ Release  │  │ Repository │ │
│  │ Engine    │  │ Manager  │  │ Client     │ │
│  └────┬─────┘  └────┬─────┘  └──────┬─────┘ │
│       │              │               │        │
└───────┼──────────────┼───────────────┼────────┘
        │              │               │
        ▼              ▼               ▼
   Render YAML    K8s API Server   Chart Repo
                  (release stored   (OCI/HTTP)
                   as Secret)
```

> **Lưu ý**: Helm v3 không còn Tiller (server-side component). Release metadata được lưu dưới dạng Secret trong namespace.

### 3.2 Kustomize — Template-free Configuration Management

**Analogy cho developer**: Kustomize giống **inheritance + override** trong OOP. Base class chứa common config, derived class (overlay) chỉ override những gì khác.

#### Kustomize Structure

```
k8s/
├── base/                      # "Base class"
│   ├── kustomization.yaml     # Resource list
│   ├── deployment.yaml        # Original YAML
│   ├── service.yaml
│   └── configmap.yaml
└── overlays/                  # "Derived classes"
    ├── dev/
    │   ├── kustomization.yaml # Patches cho dev
    │   └── replica-patch.yaml
    ├── staging/
    │   ├── kustomization.yaml
    │   └── resource-patch.yaml
    └── prod/
        ├── kustomization.yaml
        ├── replica-patch.yaml
        └── hpa.yaml           # Thêm resource mới
```

#### Các concept chính

| Concept | Giải thích |
|---------|-----------|
| **Base** | YAML gốc, valid Kubernetes manifest (không template syntax) |
| **Overlay** | Layer chứa patches áp dụng lên base |
| **Patch** | Strategic merge patch hoặc JSON patch |
| **Transformer** | Built-in operations: namePrefix, commonLabels, images |
| **Generator** | Tạo ConfigMap/Secret từ files/literals |
| **Component** | Reusable overlay có thể include nhiều nơi |

---

## 4. Deep Dive

### 4.1 Helm Template Engine

Helm dùng Go template engine. Các tính năng chính:

#### Values injection

```yaml
# values.yaml
replicaCount: 3
image:
  repository: myapp
  tag: "1.2.0"
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "myapp.fullname" . }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "myapp.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "myapp.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

#### Control flow

```yaml
# Conditionals
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
# ...
{{- end }}

# Loops
{{- range .Values.extraEnvVars }}
- name: {{ .name }}
  value: {{ .value | quote }}
{{- end }}

# Default values
{{ .Values.nodeSelector | default dict | toYaml | nindent 8 }}
```

#### Helpers (_helpers.tpl)

```yaml
# templates/_helpers.tpl
{{- define "myapp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "myapp.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
```

#### Release Lifecycle

```
helm install  →  Release v1 (DEPLOYED)
helm upgrade  →  Release v2 (DEPLOYED), v1 (SUPERSEDED)
helm rollback →  Release v3 (DEPLOYED), v2 (SUPERSEDED)
helm uninstall → All versions removed
```

### 4.2 Kustomize Patching Mechanism

#### Strategic Merge Patch

```yaml
# base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: api
          image: myapp:1.0.0
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
```

```yaml
# overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - path: replica-patch.yaml

images:
  - name: myapp
    newTag: "1.2.0"

namePrefix: prod-

commonLabels:
  env: production

configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=warn
      - DB_HOST=prod-db.internal
```

```yaml
# overlays/prod/replica-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 5
  template:
    spec:
      containers:
        - name: api
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
```

#### JSON Patch (cho thay đổi phức tạp hơn)

```yaml
# overlays/prod/kustomization.yaml
patches:
  - target:
      kind: Deployment
      name: api
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 5
      - op: add
        path: /spec/template/spec/containers/0/env/-
        value:
          name: NEW_VAR
          value: "added-by-patch"
```

### 4.3 Luồng xử lý so sánh

```
┌─────────── Helm Flow ───────────┐     ┌─────── Kustomize Flow ──────┐
│                                  │     │                              │
│  Chart + Values                  │     │  Base YAML (valid K8s)       │
│       │                          │     │       │                      │
│       ▼                          │     │       ▼                      │
│  Go Template Engine              │     │  Strategic Merge Patch       │
│  (render {{ .Values.x }})        │     │  (overlay patches on base)   │
│       │                          │     │       │                      │
│       ▼                          │     │       ▼                      │
│  Rendered YAML                   │     │  Merged YAML                 │
│  (có thể invalid cho đến khi     │     │  (luôn valid vì base valid)  │
│   render xong)                   │     │       │                      │
│       │                          │     │       ▼                      │
│       ▼                          │     │  Transformers                │
│  K8s API Server                  │     │  (namePrefix, labels, etc.)  │
│                                  │     │       │                      │
│  Release stored as Secret        │     │       ▼                      │
│                                  │     │  Final YAML → API Server     │
└──────────────────────────────────┘     └──────────────────────────────┘
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Helm vs Kustomize Comparison

| Tiêu chí | Helm | Kustomize |
|-----------|------|-----------|
| **Approach** | Templating (generate YAML) | Patching (modify YAML) |
| **Learning curve** | Cao (Go template syntax) | Thấp (YAML thuần) |
| **Base files** | Template, không valid YAML | Valid K8s YAML |
| **Readability** | Khó đọc khi template phức tạp | Dễ đọc, YAML thuần |
| **Reusability** | Cao (chart sharing qua repo) | Trung bình (base/overlay) |
| **Ecosystem** | Lớn (ArtifactHub, Bitnami) | Nhỏ hơn |
| **Lifecycle management** | Có (install/upgrade/rollback) | Không (chỉ render) |
| **Dependency management** | Có (sub-charts) | Không trực tiếp |
| **Built-in K8s** | Không (cần cài) | Có (`kubectl -k`) |
| **Debugging** | `helm template`, `--dry-run` | `kubectl kustomize` |
| **Secret management** | Có hooks, post-renderers | ConfigMapGenerator/SecretGenerator |

### 5.2 Khi nào dùng cái nào?

#### Dùng Helm khi:

- **Distributing applications**: tạo chart cho người khác dùng (internal/external).
- **Complex parameterization**: cần conditional logic, loops, functions.
- **Lifecycle management**: cần install/upgrade/rollback tracking.
- **Third-party software**: cài Prometheus, NGINX Ingress, cert-manager — dùng chart có sẵn.
- **Dependency management**: app phụ thuộc nhiều sub-components.

#### Dùng Kustomize khi:

- **In-house applications**: team tự viết manifest, cần customize per environment.
- **Simple differences**: chỉ khác replica, image tag, resource limits giữa envs.
- **GitOps workflows**: ArgoCD/Flux native support, easy to review diffs.
- **Compliance**: cần audit được thay đổi giữa envs (diff dễ đọc).
- **Small team**: không muốn học thêm Go template syntax.

#### Kết hợp cả hai:

```
# Helm chart cho base application packaging
# Kustomize overlay cho environment customization

charts/myapp/           # Helm chart (shared)
└── ...

environments/
├── dev/
│   ├── kustomization.yaml
│   └── values-dev.yaml
├── staging/
│   ├── kustomization.yaml
│   └── values-staging.yaml
└── prod/
    ├── kustomization.yaml
    └── values-prod.yaml
```

```yaml
# environments/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

helmCharts:
  - name: myapp
    releaseName: myapp
    namespace: production
    valuesFile: values-prod.yaml
    repo: oci://registry.internal/charts
    version: 1.2.0

patches:
  - path: additional-networkpolicy.yaml
```

### 5.3 Recommendations theo scenario

| Scenario | Recommendation | Lý do |
|----------|---------------|-------|
| **Startup nhỏ** (< 5 services) | Kustomize | Đơn giản, learning curve thấp, built-in kubectl |
| **Mid-size** (5-20 services) | Helm + Kustomize | Helm cho packaging, Kustomize cho env overlay |
| **Enterprise** (20+ services) | Helm charts + GitOps | Cần chart repo, versioning, dependency management |
| **Platform team** (internal dev platform) | Helm library charts | Chuẩn hóa patterns cho dev teams |
| **Third-party deployment** | Helm | Charts có sẵn, community maintained |

### 5.4 Anti-patterns

| Anti-pattern | Vấn đề | Cách đúng |
|-------------|--------|-----------|
| Over-templating Helm | Template quá phức tạp, không ai đọc được | Giữ templates đơn giản, dùng values cho config |
| `helm install` không dùng `--atomic` | Deploy failed → cluster ở trạng thái trung gian | Luôn dùng `--atomic` hoặc `--wait` |
| Hardcode namespace trong template | Không reuse được giữa namespaces | Dùng `&#123;&#123; .Release.Namespace &#125;&#125;` |
| Không pin chart version | `helm upgrade` dùng latest → breaking change | Luôn pin version trong CI/CD |
| Kustomize quá nhiều patches | Overlay phức tạp, khó trace | Nếu patch > 50% base → viết lại base |
| Không dùng `kustomize edit` | Thủ công sửa kustomization.yaml → thiếu resource | Dùng CLI hoặc `kustomize edit` |

---

## 6. Performance & Scalability ⭐

### 6.1 Helm Performance

| Yếu tố | Impact | Mitigation |
|---------|--------|------------|
| **Chart size** | Chart lớn → render chậm | Tách sub-charts, lazy loading |
| **Release history** | Nhiều revisions → Secret lớn → API server load | `--history-max 10` |
| **Template complexity** | Nested loops/conditions → render timeout | Simplify templates, pre-compute values |
| **Repository sync** | Helm repo update chậm khi nhiều charts | Dùng OCI registry thay HTTP index |
| **Concurrent installs** | Nhiều releases cùng lúc → API server throttling | Stagger deployments, rate limit CI |

```bash
# Giới hạn release history
helm upgrade myapp ./chart --history-max 10

# Dùng OCI registry (nhanh hơn traditional repo)
helm push myapp-1.0.0.tgz oci://registry.example.com/charts
helm install myapp oci://registry.example.com/charts/myapp --version 1.0.0
```

### 6.2 Kustomize Performance

| Yếu tố | Impact | Mitigation |
|---------|--------|------------|
| **Base size** | Nhiều resources → merge chậm | Tách base theo component |
| **Patch depth** | Overlay lồng nhau nhiều cấp → confusing | Giới hạn 2-3 cấp |
| **Generator load** | ConfigMapGenerator từ large files → slow | Pre-process files |
| **kubectl apply** | Large rendered output → slow apply | Dùng server-side apply |

### 6.3 So sánh render time

```bash
# Helm: render toàn bộ chart
time helm template myapp ./chart -f values-prod.yaml
# Typical: 0.5-2s cho chart trung bình

# Kustomize: build overlay
time kubectl kustomize overlays/prod
# Typical: 0.1-0.5s cho overlay trung bình
```

---

## 7. Security & Reliability Considerations

### 7.1 Helm Security

- **Chart provenance**: verify chart integrity bằng `helm verify`.
- **Values injection**: không inject secret trực tiếp vào values file → dùng external secret management.
- **Release secrets**: Helm lưu release data dưới dạng Secret → cần RBAC restrict access.
- **Third-party charts**: audit trước khi dùng, pin version, review templates.

```bash
# Verify chart signature
helm verify myapp-1.0.0.tgz --keyring pubkeys.gpg

# Không làm thế này:
# helm install myapp ./chart --set db.password=mysecretpassword
# → password lộ trong helm get values, process list

# Thay vào đó, dùng existingSecret:
# values.yaml
db:
  existingSecret: myapp-db-credentials
  existingSecretKey: password
```

### 7.2 Kustomize Security

- **SecretGenerator**: tạo Secret từ file/literal — file secret KHÔNG commit vào Git.
- **Base integrity**: verify base không bị tamper khi reference remote base.
- **RBAC cho config**: overlay prod nên restrict ai được sửa.

```yaml
# ĐỪNG commit secret literals
secretGenerator:
  - name: db-credentials
    literals:
      - password=s3cr3t  # ❌ CẤM!

# Thay vào đó, reference file nằm ngoài Git
secretGenerator:
  - name: db-credentials
    files:
      - password=secrets/db-password.txt  # File trong .gitignore
```

### 7.3 Reliability

| Concern | Helm | Kustomize |
|---------|------|-----------|
| **Rollback** | `helm rollback` (built-in) | `git revert` + `kubectl apply` |
| **Drift detection** | `helm diff` plugin | `kubectl diff -k` |
| **Atomic deployment** | `--atomic` flag | Không built-in, dùng ArgoCD sync |
| **Dependency failure** | Sub-chart fail → partial deploy | Không có dependency concept |

---

## 8. Hands-on Example

### Prerequisites

```bash
# Đảm bảo có kind cluster đang chạy
kind get clusters
# Nếu chưa có:
kind create cluster --name devops-lab

# Cài Helm
# Linux/macOS
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
kubectl cluster-info
```

### 8.1 Hands-on 1: Tạo Helm Chart

```bash
# Tạo chart skeleton
helm create myapp
cd myapp
```

Sửa `values.yaml`:

```yaml
# values.yaml
replicaCount: 2

image:
  repository: nginx
  pullPolicy: IfNotPresent
  tag: "1.25-alpine"

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi

autoscaling:
  enabled: false

serviceAccount:
  create: true

configMap:
  enabled: true
  data:
    APP_ENV: development
    LOG_LEVEL: debug
```

Thêm ConfigMap template:

```yaml
# templates/configmap.yaml
{{- if .Values.configMap.enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "myapp.fullname" . }}-config
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
data:
  {{- range $key, $value := .Values.configMap.data }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
```

```bash
# Render template để kiểm tra
helm template myapp . --debug

# Install lên cluster
helm install myapp . --namespace default --wait

# Verify
helm list
kubectl get all -l app.kubernetes.io/instance=myapp

# Expected output:
# NAME                     READY   STATUS    RESTARTS   AGE
# pod/myapp-xxx-yyy        1/1     Running   0          30s
# NAME            TYPE        CLUSTER-IP     PORT(S)   AGE
# service/myapp   ClusterIP   10.96.xx.xx    80/TCP    30s

# Test upgrade với values khác
helm upgrade myapp . --set replicaCount=3 --wait
kubectl get pods -l app.kubernetes.io/instance=myapp
# Expect 3 pods

# Check release history
helm history myapp

# Rollback
helm rollback myapp 1 --wait
kubectl get pods -l app.kubernetes.io/instance=myapp
# Expect 2 pods

# Cleanup
helm uninstall myapp
```

### 8.2 Hands-on 2: Tạo Kustomize Multi-environment

```bash
# Tạo structure
mkdir -p k8s-kustomize/{base,overlays/{dev,staging,prod}}
```

```yaml
# k8s-kustomize/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  labels:
    app: api-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
```

```yaml
# k8s-kustomize/base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-server
spec:
  selector:
    app: api-server
  ports:
    - port: 80
      targetPort: 80
```

```yaml
# k8s-kustomize/base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
data:
  APP_ENV: "development"
  LOG_LEVEL: "debug"
  DB_HOST: "localhost"
```

```yaml
# k8s-kustomize/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml

commonLabels:
  managed-by: kustomize
```

```yaml
# k8s-kustomize/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: dev-

commonLabels:
  env: dev

patches:
  - target:
      kind: ConfigMap
      name: api-config
    patch: |-
      - op: replace
        path: /data/APP_ENV
        value: "development"
      - op: replace
        path: /data/LOG_LEVEL
        value: "debug"
      - op: replace
        path: /data/DB_HOST
        value: "dev-db.internal"
```

```yaml
# k8s-kustomize/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: staging-

commonLabels:
  env: staging

patches:
  - path: deployment-patch.yaml

images:
  - name: nginx
    newTag: "1.25-alpine"
```

```yaml
# k8s-kustomize/overlays/staging/deployment-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: api
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
```

```yaml
# k8s-kustomize/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namePrefix: prod-

commonLabels:
  env: production

patches:
  - path: deployment-patch.yaml

images:
  - name: nginx
    newTag: "1.25"
```

```yaml
# k8s-kustomize/overlays/prod/deployment-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 5
  template:
    spec:
      containers:
        - name: api
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
```

```bash
# Preview rendered output cho từng environment
kubectl kustomize k8s-kustomize/overlays/dev
kubectl kustomize k8s-kustomize/overlays/staging
kubectl kustomize k8s-kustomize/overlays/prod

# So sánh dev vs prod
diff <(kubectl kustomize k8s-kustomize/overlays/dev) \
     <(kubectl kustomize k8s-kustomize/overlays/prod)

# Apply dev overlay
kubectl apply -k k8s-kustomize/overlays/dev

# Verify
kubectl get all -l env=dev
# Expected: 1 pod (dev default), dev- prefix trên tất cả resources

# Cleanup
kubectl delete -k k8s-kustomize/overlays/dev
```

### Cleanup toàn bộ

```bash
helm uninstall myapp 2>/dev/null
kubectl delete -k k8s-kustomize/overlays/dev 2>/dev/null
rm -rf myapp k8s-kustomize
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Helm Pitfalls

| Pitfall | Triệu chứng | Cách fix |
|---------|-------------|----------|
| Template syntax error | `helm template` fail với "parse error" | Check `&#123;&#123;-` spacing, missing `end` |
| YAML indentation wrong | Resources apply nhưng không hoạt động | Dùng `nindent` thay `indent`, kiểm tra `toYaml` |
| Values type mismatch | String thay vì number/bool | Dùng `&#123;&#123; .Values.port | int &#125;&#125;`, `quote` cho strings |
| Release stuck PENDING | `helm list` shows PENDING-INSTALL | `helm uninstall --no-hooks` rồi install lại |
| Hook timeout | Pre-install hook chạy quá lâu | Set `hook-delete-policy`, tăng timeout |

```bash
# Debug template rendering
helm template myapp . --debug 2>&1 | head -50

# Dry-run against cluster
helm install myapp . --dry-run --debug

# Check what's different
helm diff upgrade myapp . -f values-prod.yaml  # cần plugin helm-diff

# Check release status
helm status myapp
helm get manifest myapp
helm get values myapp
```

### 9.2 Kustomize Pitfalls

| Pitfall | Triệu chứng | Cách fix |
|---------|-------------|----------|
| Resource not found in base | "no matches for kind" | Kiểm tra kustomization.yaml liệt kê đủ resources |
| Patch target wrong | Patch không apply | Kiểm tra name/kind match chính xác với base |
| Name prefix breaks references | Service không resolve được Deployment | Dùng `vars` hoặc đảm bảo selector match |
| Image transformer not working | Image tag không đổi | Kiểm tra `images` section, name phải match |
| Recursive kustomize | Overlay lồng nhau, confusing | Giới hạn 2-3 cấp, document rõ ràng |

```bash
# Debug: xem kết quả render
kubectl kustomize overlays/prod

# Diff với cluster hiện tại
kubectl diff -k overlays/prod

# Validate output
kubectl kustomize overlays/prod | kubectl apply --dry-run=server -f -

# Kiểm tra resource nào được include
kubectl kustomize overlays/prod | grep "^kind:"
```

### 9.3 Production Case Study: Helm Upgrade gây Downtime

#### Context
E-commerce platform, 50 microservices trên Kubernetes, dùng Helm cho deployment.

#### Symptom
Sau `helm upgrade` service payment, 100% requests fail trong 30 giây.

#### Investigation
```bash
helm history payment
# Revision 42: DEPLOYED (upgrade từ v2.1.0 lên v2.2.0)

kubectl get pods -l app=payment
# 0/3 pods Ready — tất cả đang restart

kubectl describe pod payment-xxx
# Liveness probe failed: connection refused port 8080
```

#### Root Cause
Chart mới thay đổi port từ 8080 sang 8081 trong `values.yaml`, nhưng liveness probe vẫn check port 8080. Rolling update kill old pods trước khi new pods ready.

#### Fix
```bash
# Rollback ngay
helm rollback payment 41

# Fix values.yaml
# probes.port: 8081

# Upgrade lại
helm upgrade payment ./chart -f values-fixed.yaml --atomic --timeout 5m
```

#### Lesson Learned
- Luôn dùng `--atomic` để auto-rollback khi upgrade fail.
- Luôn `helm diff` trước khi upgrade production.
- Health check port phải đồng bộ với application port trong values.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước đã dùng

| Bài | Kiến thức áp dụng |
|-----|-------------------|
| Day 11 (Workload Resources) | Deployment, StatefulSet YAML structure |
| Day 12 (Networking) | Service, ClusterIP configuration |
| Day 13 (Ingress) | Ingress resource trong Helm chart |
| Day 14 (ConfigMap/Secret) | ConfigMap/Secret management bằng Helm values và Kustomize generators |
| Day 15 (Storage) | PVC trong Helm chart cho stateful workloads |

### Bài sau sẽ mở rộng

- **Day 17 (Mini-project)**: Tổng hợp Helm/Kustomize để deploy full microservice stack — áp dụng trực tiếp kiến thức hôm nay.
- **Day 31 (GitOps)**: ArgoCD/Flux native support cho cả Helm chart và Kustomize overlay.
- **Day 35 (Deployment Strategies)**: Helm hooks cho blue-green, canary với Argo Rollouts.

---

## 11. Tài liệu tham khảo

### Must-read

- [Helm Official Documentation](https://helm.sh/docs/) — Chart development guide, best practices.
- [Kustomize Official Documentation](https://kustomize.io/) — Guides, examples, API reference.
- [Kubernetes Docs - Managing Resources](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) — Kustomize integration với kubectl.

### Nice-to-have

- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/) — Template conventions, values design, labels.
- [ArtifactHub](https://artifacthub.io/) — Repository chứa hàng nghìn Helm charts.
- [Kustomize Tutorials](https://kubectl.docs.kubernetes.io/guides/) — Step-by-step examples, components.

### Deep-dive

- [Helm vs Kustomize - Blog by Harness](https://www.harness.io/blog/helm-vs-kustomize) — Detailed comparison with real-world scenarios.
- [ArgoCD + Helm/Kustomize](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/) — GitOps integration patterns.
- [OCI Registry for Helm Charts](https://helm.sh/docs/topics/registries/) — Modern chart distribution.

