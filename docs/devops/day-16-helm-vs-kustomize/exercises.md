# Day 16: Bài tập — Helm vs Kustomize

---

## Bài 1: Easy — Tạo và Deploy Helm Chart cơ bản

### Context

Bạn cần đóng gói một web application đơn giản (NGINX) thành Helm chart với khả năng customize replica count, image tag, và resource limits qua `values.yaml`.

### Yêu cầu

1. Tạo Helm chart bằng `helm create`.
2. Sửa `values.yaml` với: `replicaCount: 2`, image `nginx:1.25-alpine`, resource requests `cpu: 50m, memory: 64Mi`.
3. Thêm một ConfigMap template chứa `APP_NAME` và `APP_VERSION` từ values.
4. Install chart lên cluster.
5. Upgrade chart: thay đổi `replicaCount` thành 3.
6. Rollback về revision trước.
7. Cleanup.

### Expected Outcome

- Chart install thành công, 2 pods running.
- Sau upgrade, 3 pods running.
- Sau rollback, 2 pods running.
- `helm history` hiển thị 3 revisions.

### Hint

- Dùng `helm create mywebapp` để tạo skeleton.
- Dùng `helm template` để preview trước khi install.
- Dùng `helm upgrade mywebapp . --set replicaCount=3`.

### Acceptance Criteria

- [ ] Chart tạo thành công, không có lỗi lint (`helm lint`).
- [ ] Install thành công với 2 pods.
- [ ] ConfigMap được tạo với đúng data.
- [ ] Upgrade thành công lên 3 pods.
- [ ] Rollback thành công về 2 pods.
- [ ] Cleanup không còn resource nào.

### Bonus Challenge

- Thêm Ingress template (disabled by default, enabled via values).
- Thêm `NOTES.txt` hiển thị URL truy cập service sau install.

<details>
<summary>Solution</summary>

```bash
# 1. Tạo chart
helm create mywebapp
cd mywebapp

# 2. Sửa values.yaml
cat > values.yaml << 'EOF'
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
  name: ""
configMap:
  APP_NAME: "mywebapp"
  APP_VERSION: "1.0.0"
EOF

# 3. Tạo ConfigMap template
cat > templates/configmap.yaml << 'TMPL'
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "mywebapp.fullname" . }}-config
  labels:
    {{- include "mywebapp.labels" . | nindent 4 }}
data:
  {{- range $key, $value := .Values.configMap }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
TMPL

# 4. Lint và preview
helm lint .
helm template mywebapp . --debug

# 5. Install
helm install mywebapp . --wait
kubectl get all -l app.kubernetes.io/instance=mywebapp
kubectl get cm -l app.kubernetes.io/instance=mywebapp

# 6. Upgrade
helm upgrade mywebapp . --set replicaCount=3 --wait
kubectl get pods -l app.kubernetes.io/instance=mywebapp
# Expect 3 pods

# 7. Check history
helm history mywebapp

# 8. Rollback
helm rollback mywebapp 1 --wait
kubectl get pods -l app.kubernetes.io/instance=mywebapp
# Expect 2 pods

# 9. Cleanup
helm uninstall mywebapp
cd .. && rm -rf mywebapp
```

</details>

---

## Bài 2: Medium — Kustomize Multi-environment với ConfigMap và Patches

### Context

Team bạn có một API service cần deploy trên 3 environments (dev/staging/prod). Mỗi environment khác nhau về:
- Replica count: dev=1, staging=2, prod=5
- Resource limits
- ConfigMap values (DB host, log level, cache TTL)
- Image tag

### Yêu cầu

1. Tạo Kustomize base với Deployment, Service, và ConfigMap.
2. Tạo 3 overlays: dev, staging, prod.
3. Mỗi overlay phải:
   - Thay đổi replica count phù hợp.
   - Thay đổi resource requests/limits.
   - Thay đổi ConfigMap values (DB_HOST, LOG_LEVEL, CACHE_TTL).
   - Thay đổi image tag.
   - Thêm `namePrefix` và `commonLabels` cho environment.
4. Preview và so sánh output giữa các environments.
5. Apply dev overlay lên cluster và verify.
6. Cleanup.

### Expected Outcome

- `kubectl kustomize overlays/dev` render YAML với dev- prefix, 1 replica, debug log level.
- `kubectl kustomize overlays/prod` render YAML với prod- prefix, 5 replicas, warn log level.
- Diff giữa dev và prod hiển thị rõ ràng sự khác biệt.

### Hint

- Base YAML phải là valid Kubernetes manifest.
- Dùng `patches` trong kustomization.yaml cho thay đổi phức tạp.
- Dùng `images` transformer để thay đổi image tag.
- Dùng `configMapGenerator` hoặc patch ConfigMap trực tiếp.

### Acceptance Criteria

- [ ] Base YAML valid (`kubectl apply --dry-run=client -f base/`).
- [ ] 3 overlays render khác nhau đúng yêu cầu.
- [ ] Diff giữa environments rõ ràng, dễ review.
- [ ] Apply dev overlay thành công.
- [ ] Resources có đúng prefix và labels.
- [ ] ConfigMap chứa đúng values cho environment.

### Bonus Challenge

- Thêm HPA resource chỉ cho prod overlay.
- Dùng `components` để tạo reusable monitoring sidecar có thể include ở staging và prod.

<details>
<summary>Solution</summary>

```bash
# Tạo structure
mkdir -p api-kustomize/{base,overlays/{dev,staging,prod}}

# === BASE ===
cat > api-kustomize/base/deployment.yaml << 'EOF'
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
          envFrom:
            - configMapRef:
                name: api-config
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
EOF

cat > api-kustomize/base/service.yaml << 'EOF'
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
EOF

cat > api-kustomize/base/configmap.yaml << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
data:
  DB_HOST: "localhost"
  LOG_LEVEL: "debug"
  CACHE_TTL: "60"
EOF

cat > api-kustomize/base/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - configmap.yaml
EOF

# === DEV OVERLAY ===
cat > api-kustomize/overlays/dev/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: dev-
commonLabels:
  env: dev
images:
  - name: nginx
    newTag: "1.25-alpine"
patches:
  - target:
      kind: ConfigMap
      name: api-config
    patch: |-
      - op: replace
        path: /data/DB_HOST
        value: "dev-db.internal"
      - op: replace
        path: /data/LOG_LEVEL
        value: "debug"
      - op: replace
        path: /data/CACHE_TTL
        value: "30"
EOF

# === STAGING OVERLAY ===
cat > api-kustomize/overlays/staging/deployment-patch.yaml << 'EOF'
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
EOF

cat > api-kustomize/overlays/staging/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: staging-
commonLabels:
  env: staging
images:
  - name: nginx
    newTag: "1.25"
patches:
  - path: deployment-patch.yaml
  - target:
      kind: ConfigMap
      name: api-config
    patch: |-
      - op: replace
        path: /data/DB_HOST
        value: "staging-db.internal"
      - op: replace
        path: /data/LOG_LEVEL
        value: "info"
      - op: replace
        path: /data/CACHE_TTL
        value: "120"
EOF

# === PROD OVERLAY ===
cat > api-kustomize/overlays/prod/deployment-patch.yaml << 'EOF'
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
EOF

cat > api-kustomize/overlays/prod/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: prod-
commonLabels:
  env: production
images:
  - name: nginx
    newTag: "1.25"
patches:
  - path: deployment-patch.yaml
  - target:
      kind: ConfigMap
      name: api-config
    patch: |-
      - op: replace
        path: /data/DB_HOST
        value: "prod-db.internal"
      - op: replace
        path: /data/LOG_LEVEL
        value: "warn"
      - op: replace
        path: /data/CACHE_TTL
        value: "300"
EOF

# Preview
echo "=== DEV ==="
kubectl kustomize api-kustomize/overlays/dev
echo "=== PROD ==="
kubectl kustomize api-kustomize/overlays/prod

# Diff
diff <(kubectl kustomize api-kustomize/overlays/dev) \
     <(kubectl kustomize api-kustomize/overlays/prod)

# Apply dev
kubectl apply -k api-kustomize/overlays/dev
kubectl get all -l env=dev
kubectl get cm -l env=dev -o yaml

# Verify
kubectl describe cm dev-api-config
# Expect: DB_HOST=dev-db.internal, LOG_LEVEL=debug

# Cleanup
kubectl delete -k api-kustomize/overlays/dev
rm -rf api-kustomize
```

</details>

---

## Bài 3: Hard — Helm + Kustomize Hybrid cho Production Workflow

### Context

Bạn là DevOps engineer cho một team 20 developer. Team có 5 microservices cần deploy trên 3 environments. Bạn quyết định:
- Dùng Helm chart để package application (shared template).
- Dùng Kustomize overlay để customize per environment.
- Integrate với GitOps-ready workflow.

### Yêu cầu

1. Tạo một Helm chart chung đặt tên `microservice-template` có thể dùng cho mọi service.
2. Chart phải support: Deployment, Service, ConfigMap, optional Ingress, optional HPA.
3. Render Helm chart thành base YAML cho 2 services (api-gateway, order-service).
4. Tạo Kustomize overlays cho dev và prod, mỗi overlay customize cả 2 services.
5. Viết script `deploy.sh` nhận argument environment và apply đúng overlay.
6. Implement dry-run mode trong script.
7. Verify toàn bộ bằng `--dry-run=server`.

### Expected Outcome

- Helm chart reusable cho mọi service (chỉ khác values).
- Kustomize overlay rõ ràng, dễ review diff giữa environments.
- Script deploy idempotent, có dry-run mode.
- Toàn bộ structure GitOps-ready (ArgoCD có thể sync).

### Hint

- Dùng `helm template` để render base YAML từ chart.
- Mỗi service có riêng `values-<service>.yaml`.
- Kustomize base = rendered Helm output.
- Script dùng `kubectl diff -k` cho dry-run.

### Acceptance Criteria

- [ ] Helm chart pass `helm lint`.
- [ ] Chart reusable cho nhiều services (chỉ đổi values).
- [ ] Kustomize overlays render đúng cho mỗi environment.
- [ ] Script `deploy.sh` hoạt động với `--dry-run` và `--apply`.
- [ ] Diff giữa dev và prod rõ ràng, có thể review.
- [ ] Cleanup script xóa sạch resources.

### Bonus Challenge

- Thêm `pre-deploy` validation check (lint, dry-run, policy check).
- Tạo Makefile với targets: `lint`, `template`, `diff-dev`, `diff-prod`, `deploy-dev`, `deploy-prod`, `clean`.
- Integrate helm-diff plugin để preview changes trước upgrade.

<details>
<summary>Solution</summary>

```bash
# === Project structure ===
mkdir -p helm-kustomize-hybrid/{chart/microservice-template/templates,services/{api-gateway,order-service},overlays/{dev,prod},scripts}

# === 1. Helm Chart Template ===
cat > helm-kustomize-hybrid/chart/microservice-template/Chart.yaml << 'EOF'
apiVersion: v2
name: microservice-template
description: Reusable Helm chart for microservices
version: 1.0.0
appVersion: "1.0.0"
EOF

cat > helm-kustomize-hybrid/chart/microservice-template/values.yaml << 'EOF'
name: myservice
replicaCount: 1
image:
  repository: nginx
  tag: "1.25-alpine"
service:
  port: 80
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
config: {}
ingress:
  enabled: false
hpa:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
EOF

cat > helm-kustomize-hybrid/chart/microservice-template/templates/deployment.yaml << 'TMPL'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.name }}
  labels:
    app: {{ .Values.name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Values.name }}
  template:
    metadata:
      labels:
        app: {{ .Values.name }}
    spec:
      containers:
        - name: {{ .Values.name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: {{ .Values.service.port }}
          {{- if .Values.config }}
          envFrom:
            - configMapRef:
                name: {{ .Values.name }}-config
          {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          readinessProbe:
            httpGet:
              path: /
              port: {{ .Values.service.port }}
            initialDelaySeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: {{ .Values.service.port }}
            initialDelaySeconds: 10
TMPL

cat > helm-kustomize-hybrid/chart/microservice-template/templates/service.yaml << 'TMPL'
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.name }}
spec:
  selector:
    app: {{ .Values.name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.port }}
TMPL

cat > helm-kustomize-hybrid/chart/microservice-template/templates/configmap.yaml << 'TMPL'
{{- if .Values.config }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Values.name }}-config
data:
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
TMPL

cat > helm-kustomize-hybrid/chart/microservice-template/templates/hpa.yaml << 'TMPL'
{{- if .Values.hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .Values.name }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .Values.name }}
  minReplicas: {{ .Values.hpa.minReplicas }}
  maxReplicas: {{ .Values.hpa.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.hpa.targetCPUUtilizationPercentage }}
{{- end }}
TMPL

# === 2. Service Values ===
cat > helm-kustomize-hybrid/services/api-gateway/values.yaml << 'EOF'
name: api-gateway
replicaCount: 1
image:
  repository: nginx
  tag: "1.25-alpine"
service:
  port: 80
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
config:
  SERVICE_NAME: "api-gateway"
  UPSTREAM_URL: "http://order-service"
EOF

cat > helm-kustomize-hybrid/services/order-service/values.yaml << 'EOF'
name: order-service
replicaCount: 1
image:
  repository: nginx
  tag: "1.25-alpine"
service:
  port: 80
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
config:
  SERVICE_NAME: "order-service"
  DB_HOST: "localhost"
EOF

# === 3. Render base YAML from Helm ===
cd helm-kustomize-hybrid

# Render api-gateway
helm template api-gateway chart/microservice-template \
  -f services/api-gateway/values.yaml \
  > services/api-gateway/rendered.yaml

# Render order-service
helm template order-service chart/microservice-template \
  -f services/order-service/values.yaml \
  > services/order-service/rendered.yaml

# === 4. Kustomize Base ===
cat > services/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - api-gateway/rendered.yaml
  - order-service/rendered.yaml
EOF

# === 5. Dev Overlay ===
cat > overlays/dev/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../services
namePrefix: dev-
commonLabels:
  env: dev
EOF

# === 6. Prod Overlay ===
cat > overlays/prod/deployment-patches.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api-gateway
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: order-service
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
EOF

cat > overlays/prod/kustomization.yaml << 'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../services
namePrefix: prod-
commonLabels:
  env: production
patches:
  - path: deployment-patches.yaml
EOF

# === 7. Deploy Script ===
cat > scripts/deploy.sh << 'SCRIPT'
#!/bin/bash
set -euo pipefail

ENV=${1:-}
MODE=${2:---dry-run}

if [[ -z "$ENV" ]]; then
  echo "Usage: $0 <dev|staging|prod> [--dry-run|--apply]"
  exit 1
fi

OVERLAY_DIR="overlays/${ENV}"
if [[ ! -d "$OVERLAY_DIR" ]]; then
  echo "Error: overlay directory $OVERLAY_DIR not found"
  exit 1
fi

echo "Environment: $ENV"
echo "Mode: $MODE"

if [[ "$MODE" == "--dry-run" ]]; then
  echo "--- Preview rendered output ---"
  kubectl kustomize "$OVERLAY_DIR"
  echo "--- Diff with cluster ---"
  kubectl diff -k "$OVERLAY_DIR" || true
elif [[ "$MODE" == "--apply" ]]; then
  echo "Applying $ENV overlay..."
  kubectl apply -k "$OVERLAY_DIR"
  echo "Verifying..."
  kubectl get all -l "env=$ENV"
else
  echo "Unknown mode: $MODE"
  exit 1
fi
SCRIPT
chmod +x scripts/deploy.sh

# === Test ===
# Dry-run dev
bash scripts/deploy.sh dev --dry-run

# Apply dev
bash scripts/deploy.sh dev --apply

# Verify
kubectl get all -l env=dev

# Cleanup
kubectl delete -k overlays/dev
cd ..
rm -rf helm-kustomize-hybrid
```

</details>

---

## Solution / Reference Implementation

Các reference implementation đầy đủ nằm trong từng block `<details>` của Bài 1, Bài 2 và Bài 3 ở trên. Khi tự chấm bài, ưu tiên verify bằng các lệnh sau trước khi xem lời giải:

```bash
helm lint ./myapp
helm template myapp ./myapp
kubectl kustomize k8s-kustomize/overlays/dev
kubectl apply --dry-run=server -k k8s-kustomize/overlays/dev
```

