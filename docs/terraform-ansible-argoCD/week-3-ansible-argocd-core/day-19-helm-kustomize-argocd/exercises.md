# Day 19 - Exercises: Helm, Kustomize, Overlays với ArgoCD

**Thời gian ước tính:** 60-90 phút
**Độ khó:** Intermediate → Advanced
**Lab environment:** kind cluster với ArgoCD (từ Day 17/18), Git repo `gitops-lab-day19`

---

## Exercise 1: Refactor manifest copy-paste sang Kustomize base/overlay

**Mục tiêu:** Chuyển 3 thư mục manifest copy-paste thành base/overlay pattern

**Context:**

Team có 3 microservice (`api`, `auth`, `payment`) deploy lên 3 env (`dev`, `staging`, `prod`). Cấu trúc hiện tại:

```
manifests-legacy/
├── api/
│   ├── dev/deployment.yaml      # replicas: 1,  image: api:v1.0.0
│   ├── dev/service.yaml
│   ├── staging/deployment.yaml  # replicas: 2,  image: api:v1.0.0
│   ├── staging/service.yaml
│   ├── prod/deployment.yaml     # replicas: 5,  image: api:v1.0.0
│   └── prod/service.yaml
├── auth/
│   ├── dev/deployment.yaml      # replicas: 1,  image: auth:v2.0.0
│   ├── staging/deployment.yaml  # replicas: 2,  image: auth:v2.0.0
│   └── prod/deployment.yaml     # replicas: 3,  image: auth:v2.0.0
└── payment/
    ├── dev/deployment.yaml      # replicas: 1,  image: payment:v1.1.0
    ├── staging/deployment.yaml  # replicas: 2,  image: payment:v1.1.0
    └── prod/deployment.yaml     # replicas: 4,  image: payment:v1.1.0
```

**Tất cả deployment.yaml đều có cùng cấu trúc:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: ghcr.io/acme/api:v1.0.0
          ports:
            - containerPort: 8080
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

**Nhiệm vụ:**

1. Tạo thư mục `kustomize-refactor/` với cấu trúc base/overlay cho `api`, `auth`, `payment` service
2. Xác định field nào nên ở base, field nào ở overlay (replicas, image tag, resources)
3. Tạo `base/deployment.yaml` chuẩn với placeholder cho replicas/image/resources
4. Tạo overlay cho mỗi env/service
5. Verify bằng `kustomize build` rằng output tương đương với legacy manifests
6. Tạo ArgoCD Application cho `api-service` overlay `staging`
7. Compare diff:
   ```bash
   # Render overlay
   kustomize build kustomize-refactor/api/overlays/staging > /tmp/kustomize-api-staging.yaml

   # Render legacy
   cat manifests-legacy/api/staging/deployment.yaml > /tmp/legacy-api-staging.yaml

   diff /tmp/kustomize-api-staging.yaml /tmp/legacy-api-staging.yaml
   ```

**Deliverable:**
- Folder `kustomize-refactor/` với structure hợp lý
- Screenshot ArgoCD UI cho `api-service-staging` ở trạng thái Healthy
- Ghi chú: giải thích tại sao chọn base vs overlay cho từng field

---

## Exercise 2: Wrap external chart cert-manager bằng multi-source pattern

**Mục tiêu:** Deploy cert-manager từ upstream Jetstack chart, override resource requests cho prod, giữ values trong team repo

**Context:**

Platform team cần deploy cert-manager (upstream chart) cho 3 clusters (dev, staging, prod). Thay vì fork chart, dùng multi-source pattern:

```
gitops-repo/
├── applications/
│   └── cert-manager/
│       ├── values-dev.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       └── application-set.yaml
└── clusters/
    └── argocd-cm.yaml
```

**Yêu cầu:**

1. Tạo thư mục `applications/cert-manager/` trong Git repo
2. Tạo `values-dev.yaml`:
   - `installCRDs: false` (tiết kiệm resource dev)
   - `replicaCount: 1`
   - `resources.requests.cpu: 50m, memory: 64Mi`
   - `webhook.replicaCount: 1`
3. Tạo `values-staging.yaml`:
   - `installCRDs: true`
   - `replicaCount: 1`
   - `resources.requests.cpu: 100m, memory: 128Mi`
4. Tạo `values-prod.yaml`:
   - `installCRDs: true`
   - `replicaCount: 2` cho cainjector và webhook
   - `resources.requests.cpu: 200m, memory: 256Mi`
   - `prometheus.enabled: true`
5. Tạo Application YAML cho `cert-manager-prod` dùng multi-source pattern:
   - Source 1: `https://charts.jetstack.io` chart `cert-manager` v1.15.0
   - Source 2: values từ team repo
   - ArgoCD syncPolicy automated với `prune: true`
6. Apply lên kind cluster
7. Verify: `kubectl get pods -n cert-manager` và `argocd app get cert-manager-prod`

**Bonus:** Tạo ApplicationSet để deploy cert-manager lên tất cả 3 env tự động từ 1 template

---

## Exercise 3: Build production-ready Helm chart với helpers và schema

**Mục tiêu:** Viết Helm chart hoàn chỉnh cho `payment-service` với helpers, labels chuẩn, values schema validation

**Nhiệm vụ:**

1. Tạo chart `charts/payment-service/`:
   - `Chart.yaml` với metadata đầy đủ
   - `values.schema.json` để validate values (schema cho replicaCount, image tag format, resource limits)
   - `values.yaml` với defaults hợp lý

2. Viết `templates/_helpers.tpl` với:
   - `payment-service.name` (hỗ trợ nameOverride)
   - `payment-service.fullname` (FQDN)
   - `payment-service.labels` (chuẩn Kubernetes labels)
   - `payment-service.selectorLabels`
   - `payment-service.chart` (name-version)
   - `payment-service.commonAnnotations` (commit SHA, team)

3. Viết `templates/deployment.yaml`:
   - Sử dụng helpers trên
   - `topologySpreadConstraints` (spread across zones)
   - `podAntiAffinity` (prefer not co-located)
   - `securityContext` (non-root, read-only root filesystem)
   - `priorityClassName` (production only)
   - ConfigMap checksum annotation
   - `terminationGracePeriodSeconds: 60`
   - Lifecycle hooks (preStop: drain connections)

4. Viết `templates/service.yaml`:
   - Type: ClusterIP mặc định, có thể override thành LoadBalancer
   - Port naming convention: `http-<portname>`

5. Viết `templates/ingress.yaml`:
   - TLS support
   - Rate limiting annotation
   - Custom error page annotation

6. Viết `templates/_.tpl` hoặc `templates/env-configmap.yaml`:
   - ConfigMap từ values (key-value pairs)
   - Support per-env database host

7. Local verification:
   ```bash
   helm lint charts/payment-service
   helm template payment-release charts/payment-service -f values-prod.yaml | \
     kubectl apply --dry-run=server -f -
   ```

8. Validate schema:
   ```bash
   helm template test charts/payment-service --set replicaCount=abc 2>&1
   # Phải báo lỗi schema validation
   ```

**Deliverable:**
- Chart hoàn chỉnh, có thể `helm package`
- Output của `helm lint` và `helm template` thành công
- Values schema reject invalid input

---

## Exercise 4: Debug Kustomize overlay gây Service name drift và DNS resolution fail

**Mục tiêu:** Tìm và fix bug phổ biến khi Kustomize overlay thay đổi resource name

**Context:**

Team deploy `checkout-service` qua Kustomize overlay lên staging. Deployment chạy OK nhưng `payment-service` không thể call `checkout-service` → DNS resolution fail.

**Cấu trúc hiện tại (bị bug):**

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: checkout-staging

bases:
  - ../../base

namePrefix: checkout-
# ^^^ BUG: Service name trở thành "checkout-checkout-service"
#    Nhưng payment-service đang call "checkout-service"

commonLabels:
  environment: staging
```

```yaml
# base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: checkout-service
  namespace: checkout
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: http
  selector:
    app: checkout-service
```

```yaml
# base/deployment.yaml (trong payment-service repo)
# payment-service muốn call checkout-service
env:
  - name: CHECKOUT_SERVICE_URL
    value: "http://checkout-service:8080"   # ← SAI! Should be checkout-checkout-service
```

**Nhiệm vụ:**

1. Analyze: Giải thích chính xác tại sao DNS resolution fail
2. Fix 1 (recommended): Bỏ `namePrefix`, dùng namespace + label để phân biệt env
   - Cập nhật `overlays/staging/kustomization.yaml`
   - Cập nhật `base/service.yaml` nếu cần
3. Fix 2 (alternative): Giữ `namePrefix` nhưng update payment-service URL
   - Xác định URL đúng sau khi apply
   - Cập nhật payment-service config
4. Verify fix bằng:
   ```bash
   kustomize build overlays/staging | grep "^kind: Service$" -A 5
   # Kiểm tra Service name = "checkout-service" (không có prefix)
   ```
5. Deploy lên kind cluster và verify:
   ```bash
   kubectl run -it --rm debug --image=busybox --restart=Never -- \
     nslookup checkout-service.checkout-staging
   # Phải resolve được IP
   ```

**Deliverable:**
- File `overlays/staging/kustomization.yaml` đã fix
- Giải thích 2-3 câu: tại sao `namePrefix` trong Kustomize thường gây vấn đề
- Kết quả `kustomize build` output cho Service resource

---

## Exercise 5: Combine Helm + Kustomize — nginx-ingress multi-env

**Mục tiêu:** Deploy nginx-ingress chart qua Kustomize overlay với service type khác nhau mỗi env

**Pattern:** Pattern A (`helmCharts` trong kustomization.yaml)

**Context:**

Team cần deploy nginx-ingress (upstream chart) lên 3 môi trường:
- **dev**: NodePort (tiết kiệm, không cần LoadBalancer)
- **staging**: LoadBalancer nhưng không allocate IP cố định
- **prod**: LoadBalancer + static IP annotation + WAF annotation

**Nhiệm vụ:**

1. Cập nhật ArgoCD configmap để enable `--enable-helm`:
   ```bash
   kubectl patch configmap argocd-cm -n argocd \
     --type merge \
     -p '{"data":{"kustomize.buildOptions":"--enable-helm"}}'
   kubectl rollout restart deployment argocd-repo-server -n argocd
   ```

2. Tạo `kustomize/nginx-ingress/overlays/dev/kustomization.yaml`:
   ```yaml
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

   commonLabels:
     app.kubernetes.io/name: ingress-nginx
     environment: dev

   # Sau Helm render, Kustomize transform thêm labels
   ```

3. Tạo `kustomize/nginx-ingress/overlays/dev/values-dev.yaml`:
   - `controller.service.type: NodePort`
   - `controller.service.nodePorts.http: 30080`
   - `controller.service.nodePorts.https: 30443`
   - `controller.replicaCount: 1`
   - `controller.resources.requests.cpu: 50m, memory: 64Mi`

4. Tạo overlay cho `staging` và `prod`:
   - **staging**: LoadBalancer, replicaCount: 2, resources: 100m/128Mi
   - **prod**: LoadBalancer + annotation `loadBalancerIP` (giả lập), replicaCount: 3, resources: 200m/256Mi

5. Verify Helm chart compatibility check:
   ```bash
   helm show values ingress-nginx/ingress-nginx \
     --repo https://kubernetes.github.io/ingress-nginx \
     4.10.0 | grep -A 20 "controller.service"
   ```

6. Apply và sync:
   ```bash
   argocd app create ingress-nginx-dev \
     --repo https://github.com/YOUR_USERNAME/gitops-lab-day19.git \
     --path kustomize/nginx-ingress/overlays/dev \
     --dest-namespace ingress-nginx-dev \
     --dest-server https://kubernetes.default.svc \
     --sync-policy automated \
     --self-heal

   argocd app sync ingress-nginx-dev --force-sync
   ```

7. Verify trên cluster:
   ```bash
   kubectl get svc -n ingress-nginx-dev
   # Service type phải là NodePort
   kubectl get pods -n ingress-nginx-dev
   ```

**Deliverable:**
- 3 overlay (dev, staging, prod) cho nginx-ingress
- ArgoCD Application cho dev (healthy)
- Screenshot ArgoCD UI hoặc `argocd app get ingress-nginx-dev`

---

## Exercise 6 (Advanced): Production architecture — 8 service × 3 env

**Mục tiêu:** Thiết kế GitOps repo structure scalable cho 8 microservice × 3 env, với clear ownership và DRY principle

**Context:**

```
Team Platform — quản lý: cluster infra, shared services, chart registry
Team API — quản lý: api-service, gateway-service, auth-service
Team Payment — quản lý: payment-service, billing-service, subscription-service
Team Notification — quản lý: notification-service, email-service
```

**Yêu cầu thiết kế:**

1. **Folder structure** đề xuất cho GitOps repo (dùng mono-repo hay poly-repo? Tại sao?)
2. **Ownership model**: Ai sở hữu file nào? Platform team vs app team phân chia thế nào?
3. **Helm chart strategy**:
   - Shared library chart (`common-lib`) cho tất cả service?
   - Mỗi service có chart riêng?
   - Dùng upstream chart cho infrastructure (nginx-ingress, cert-manager, external-secrets)?
4. **Kustomize overlay strategy**:
   - 1 shared base cho tất cả service?
   - Mỗi team có base riêng?
   - Cross-team overlay (vd: team Platform thêm network policy cho tất cả service)?
5. **Multi-source pattern** cho setup:
   - cert-manager từ upstream, values từ platform team repo
   - external-secrets từ upstream, values từ platform team repo
   - Mỗi service chart riêng, values từ app team repo
6. **DRY approach**: Làm sao tránh trùng lặp giữa 8 service?
   - Shared `deployment-patch.yaml` cho production resources?
   - Helm library chart?
   - Kustomize generator?
7. **Security boundaries**:
   - AppProject phân chia quyền access
   - Secret management: SealedSecret hay ExternalSecret?
   - NetworkPolicy: shared hay per-service?
8. **ApplicationSet strategy** (Day 22 preview):
   - 1 ApplicationSet cho tất cả service × env?
   - Hay 1 ApplicationSet per team?
   - Generator nào phù hợp?

**Deliverable:**

Viết 1 document (~500-800 từ) trình bày:

```
# GitOps Architecture Design

## Repository Strategy
[mono vs poly, lý do chọn]

## Folder Structure
[ASCII tree diagram]

## Ownership Matrix
[File/folder → Team owner]

## Helm Chart Architecture
[Shared library? Per-service?]

## Kustomize Overlay Strategy
[Base/overlay cho từng team]

## Security Boundaries
[AppProject design]

## Multi-source Pattern
[Chi tiết cách kết hợp upstream chart + team values]

## ApplicationSet Design
[Generator strategy]

## Migration Plan
[Từ setup hiện tại (copy-paste) sang design mới, step by step]
```

**Deliverable file:** `D:\my-source\learning\terraform-ansible-argoCD\week-3-ansible-argocd-core\day-19-helm-kustomize-argocd\architecture-design.md`

---

## Bonus Challenges

### Bonus A: ArgoCD Image Updater Integration

Tích hợp ArgoCD Image Updater để tự động update image tag khi tag mới được push lên registry:

```bash
# Install ArgoCD Image Updater
kubectl apply -f \
  https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/v0.8.0/manifests/install.yaml

# Configure Image Updater annotation trong Application
argocd-image-updater.argoproj.io/image-list: ghcr.io/acme/api-service
argocd-image-updater.argoproj.io/api-service.update策略: latest
```

Tạo Application cho `api-service` với annotations trên, verify Image Updater auto-update image tag sau khi push image mới lên registry.

### Bonus B: Render comparison script

Viết script `scripts/render-diff.sh` so sánh Helm và Kustomize output cho cùng 1 service + env:

```bash
#!/bin/bash
# Usage: ./scripts/render-diff.sh api-service staging
SERVICE=$1
ENV=$2

helm template $SERVICE charts/$SERVICE \
  -f charts/$SERVICE/values.yaml \
  -f charts/$SERVICE/values-$ENV.yaml \
  --namespace $SERVICE-$ENV > /tmp/helm-$SERVICE-$ENV.yaml

kustomize build kustomize/$SERVICE/overlays/$ENV \
  > /tmp/kustomize-$SERVICE-$ENV.yaml

diff /tmp/helm-$SERVICE-$ENV.yaml /tmp/kustomize-$SERVICE-$ENV.yaml || true
echo "=== Resource count ==="
echo "Helm: $(grep -c '^kind:' /tmp/helm-$SERVICE-$ENV.yaml)"
echo "Kustomize: $(grep -c '^kind:' /tmp/kustomize-$SERVICE-$ENV.yaml)"
```

---

## Cleanup Instructions

Sau khi hoàn thành tất cả exercises:

```bash
# Xóa tất cả applications
for app in \
  cert-manager-prod \
  ingress-nginx-dev \
  api-service-kustomize-dev \
  api-service-kustomize-staging \
  api-service-helm-staging \
  api-service-helm-prod; do
  argocd app delete "$app" --cascade 2>/dev/null || true
done

# Xóa namespace
for ns in api-service-dev api-service-staging api-service-prod \
           api-service-staging api-service-prod \
           cert-manager cert-manager-staging \
           ingress-nginx-dev; do
  kubectl delete namespace "$ns" 2>/dev/null || true
done

# Verify
argocd app list
kubectl get ns | grep -E "(api-service|cert-manager|ingress)"
```

---

## Solutions Overview (Instructor Notes)

| Exercise | Key concept tested | Common issues |
|---|---|---|
| 1 | base/overlay analysis, Kustomize build | Nhầm strategic merge vs JSON6902 |
| 2 | Multi-source pattern, upstream chart override | $values reference path incorrect |
| 3 | Helm helpers, values schema, production best practices | `_helpers.tpl` syntax errors, missing Template reference |
| 4 | namePrefix DNS impact, Kustomize name management | Students thường dùng label thay vì fix prefix |
| 5 | `--enable-helm`, helmCharts in Kustomize | ArgoCD config chưa updated, repo-server chưa restart |
| 6 | Architecture design, trade-off analysis | Cần balance giữa DRY và team autonomy |
