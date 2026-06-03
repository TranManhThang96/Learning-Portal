# Day 21 — Exercises: App of Apps Pattern

> Làm sau khi hoàn thành lesson.md. Mỗi challenge 20-45 phút.

---

## Challenge 1: Refactor 8 Application thủ công sang App of Apps

**Độ khó:** Trung bình
**Thời gian:** 30 phút
**Context:** Team ACME có 8 Application được tạo thủ công bằng `kubectl apply`. Cần migrate sang App of Apps pattern.

### Tình huống

```
# Danh sách 8 application hiện tại:
kubectl get application -A

NAME                  PROJECT   SYNC   HEALTH
api-service-dev       default   Synced  Healthy
api-service-staging   default   Synced  Healthy
api-service-prod      default   Synced  Healthy
worker-service-dev    default   Synced  Healthy
worker-service-prod  default   Synced  Healthy
frontend-service-dev  default   Synced  Healthy
frontend-service-prod default   Synced  Healthy
payment-service-dev   default   Synced  Healthy
```

Mỗi Application được tạo bằng lệnh `kubectl apply -f api-service-dev.yaml`.

### Yêu cầu

1. Di chuyển 8 Application YAML vào folder `argocd/applications/`
2. Tạo root Application trỏ vào folder đó
3. Xóa 8 Application thủ công (sau khi apply root app)
4. Verify: ArgoCD vẫn thấy 8 Application sau khi xóa kubectl-apply file cũ
5. Thêm 1 service mới qua Git commit (không dùng kubectl)

### Constraints

- Không downtime
- Sử dụng `argocd app set` để backup sync policy trước khi migrate
- Test trên dev trước

### Solution outline

```bash
# 1. Export current app specs
kubectl get application -n argocd -o yaml > /tmp/all-apps.yaml

# 2. Tạo folder structure
mkdir -p argocd/applications/

# 3. Split YAML thành file riêng
# (script hoặc thủ công)

# 4. Tạo root app
# 5. Apply root app
# 6. Delete old apps
# 7. Verify via Git
```

---

## Challenge 2: Bootstrap Order cho 6 platform component

**Độ khó:** Trung bình
**Thời gian:** 30 phút
**Context:** Thiết kế bootstrap order cho stack phức tạp, có dependency vòng tròn.

### Stack

```
A. cert-manager
   - CRD: Certificate, ClusterIssuer
   - Phụ thuộc: webhook certificate

B. ingress-nginx
   - Phụ thuộc: Certificate từ cert-manager (Issuer)
   - Ingress resource cần certificate

C. external-secrets
   - CRD: ClusterSecretStore, ExternalSecret
   - Phụ thuộc: CRD phải tồn tại

D. prometheus-stack
   - CRD: Prometheus, ServiceMonitor, PrometheusRule
   - Phụ thuộc: Không

E. ArgoCD itself
   - Phụ thuộc: ingress-nginx (để expose UI qua HTTPS)
   - Nhưng ArgoCD tự tạo chính nó → chicken-egg

F. sealed-secrets
   - CRD: SealedSecret
   - Phụ thuộc: CRD
```

### Yêu cầu

1. Vẽ dependency graph (ASCII diagram)
2. Sắp xếp bootstrap order (sync wave annotation)
3. Giải thích chicken-egg ArgoCD + ingress-nginx
4. Cấu hình sync wave annotation cho từng component
5. Xử lý chicken-egg: ArgoCD expose bằng Ingress vs NodePort/LoadBalancer

### Solution approach

```
Wave 0:  CRD installer (cert-manager CRD, sealed-secrets CRD)
Wave 1:  Namespace tạo trước
Wave 2:  cert-manager (không dùng Ingress, dùng ClusterIssuer)
Wave 3:  ArgoCD (NodePort, không cần ingress)
Wave 4:  ingress-nginx (dùng self-signed cert tạm)
Wave 5:  IngressClass + ClusterIssuer (cập nhật cert-manager sau khi có ingress)
Wave 6:  external-secrets
Wave 7:  prometheus-stack
Wave 8:  sealed-secrets
```

---

## Challenge 3: Multi-cluster — 1 root app cho dev, 1 root app cho prod

**Độ khó:** Cao
**Thời gian:** 45 phút
**Context:** Team muốn share template giữa dev và prod cluster nhưng cấu hình khác nhau.

### Tình huống

```
Cluster dev:
  - kind-cluster-dev (localhost)
  - ArgoCD installed

Cluster prod:
  - kind-cluster-prod (localhost)
  - ArgoCD installed

Mục tiêu:
  - 1 platform-repo chứa cấu hình cho cả 2 cluster
  - 1 root app cho dev cluster
  - 1 root app cho prod cluster
  - prod có prometheus với retention 30d, dev 7d
  - prod có 3 replicas ingress-nginx, dev có 1 replica
  - Dùng chung Helm values file, override bằng environment
```

### Yêu cầu

1. Thiết kế file structure để share template giữa 2 cluster
2. Tạo 2 root Application, mỗi cái trỏ vào environment folder khác nhau
3. Demo: prometheus-stack values khác nhau dev vs prod (dùng Kustomize overlay hoặc Helm environment)
4. Giải thích: cách nào tốt hơn — per-env folder hay per-env branch?

### Architecture option

```
Option A: Per-env folder (Kustomize overlay)
──────────────────────────────────────────────
platform-repo/
├── platform-services/
│   ├── prometheus-stack/
│   │   ├── base/values.yaml
│   │   └── overlays/
│   │       ├── dev/values.yaml   # retention: 7d, replicas: 1
│   │       └── prod/values.yaml # retention: 30d, replicas: 3
│   └── ingress-nginx/
│       ├── base/values.yaml
│       └── overlays/
│           ├── dev/values.yaml
│           └── prod/values.yaml
└── argocd/
    └── applications/
        ├── root-dev.yaml    # path: overlays/dev
        └── root-prod.yaml   # path: overlays/prod

Option B: Per-env branch
──────────────────────────────────────────────
platform-repo/dev     → branch chứa dev config
platform-repo/main    → branch chứa prod config

root-dev.yaml points to platform-repo dev branch
root-prod.yaml points to platform-repo main branch
```

---

## Challenge 4: Debug — root app stuck Syncing 30 phút

**Độ khó:** Cao
**Thời gian:** 30 phút
**Context:** Production incident — root app không sync được 30 phút.

### Symptoms

```
argocd app get root-platform
Name:               root-platform
Project:            default
Server:             https://kubernetes.default.svc
Namespace:          argocd
Status:             Syncing      ← Stuck 30 phút
Health Status:      Degraded

argocd app resources root-platform
KIND        NAME                    STATUS
Application cert-manager            OutOfSync  Missing
Application ingress-nginx           OutOfSync  Missing
Application prometheus-stack        OutOfSync  Missing
Application external-secrets        OutOfSync  Missing

kubectl get application -n argocd
NAME                SYNC STATUS    HEALTH
root-platform       Syncing        Degraded
cert-manager        OutOfSync      Missing
ingress-nginx       OutOfSync      Missing
prometheus-stack    OutOfSync      Missing
external-secrets    OutOfSync      Missing
```

### Debug steps

```bash
# 1. Kiểm tra root app log
argocd app logs root-platform

# 2. Kiểm tra ArgoCD application controller
kubectl get pods -n argocd
kubectl logs -n argocd -l app.kubernetes.io/name=application-controller --tail=100

# 3. Kiểm tra repo server
kubectl logs -n argocd -l app.kubernetes.io/name=repo-server --tail=50

# 4. Kiểm tra child app chi tiết
argocd app get cert-manager
argocd app get cert-manager --watch

# 5. Kiểm tra ArgoCD app spec
kubectl get application cert-manager -n argocd -o yaml
```

### Incident scenario: 4 possible root causes

**Scenario A:** Repo credentials expired

```
Symptom: "failed to retrieve manifests" error in controller log
Fix: Refresh ArgoCD repo credential
argocd repo update REPO_NAME --username USER --password TOKEN
```

**Scenario B:** ArgoCD repo server OOM (too many repos/clones)

```
Symptom: Controller pod restart loop, "context deadline exceeded"
Fix: Tăng repo server memory:
    kubectl set env deployment/argocd-repo-server -n argocd ARGOCD_RECONCILIATION_TIMEOUT=300s
```

**Scenario C:** Invalid child YAML file in folder

```
Symptom: Root app Syncing nhưng child không xuất hiện
Fix:
kubectl get application -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
# Kiểm tra từng child YAML bằng kubectl apply --dry-run
```

**Scenario D:** Namespace webhook certificate issue (cert-manager)

```
Symptom: cert-manager webhook không start → cert-manager OutOfSync
Fix: Temporary disable webhook validation hoặc restart cert-manager pods
```

### Yêu cầu

1. Viết incident report theo format:
   - Symptom
   - Impact
   - Root cause
   - Resolution
   - Prevention
2. Viết runbook để tự động hóa debug lần sau

---

## Challenge 5: Disaster Recovery — root app bị xóa không finalizer

**Độ khó:** Cao
**Thời gian:** 45 phút
**Context:** AI đã xóa root app bằng `kubectl delete application root-platform` — không có finalizer. Child app và workload vẫn chạy, nhưng ArgoCD không quản lý.

### Tình huống

```
# Ai đó chạy lệnh:
kubectl delete application root-platform -n argocd

# Hệ quả:
kubectl get application -n argocd
# root-platform ĐÃ BỊ XÓA
# 5 child app VẪN CÒN (orphaned)

kubectl get pods -A
# Tất cả pod vẫn chạy (workload không bị xóa)

# Vấn đề:
argocd app list
# Child apps không xuất hiện trong ArgoCD
# ArgoCD không sync, không self-heal, không detect drift
# Git commit mới không tạo app mới trong folder
```

### Yêu cầu

1. Recovery plan: khôi phục root app mà không gây downtime
2. Verify child app được quản lý lại bởi ArgoCD
3. Kiểm tra drift trên workload sau khi restore
4. Policy: thêm finalizer vào tất cả existing child app
5. Automation: viết script detect orphaned applications

### Recovery steps

```bash
# Step 1: Identify orphaned child apps
kubectl get application -n argocd
# -> List 5 child apps (không có parent)

# Step 2: Identify orphaned workload namespaces
kubectl get namespaces
# -> ingress-nginx, cert-manager, monitoring, guestbook vẫn tồn tại

# Step 3: Tạo lại root app
kubectl apply -f argocd/applications/root-app.yaml

# Step 4: Verify root + children
argocd app list

# Step 5: Check for drift
argocd app diff root-platform
argocd app list --label layer=platform

# Step 6: Fix all child app finalizers
for app in cert-manager ingress-nginx prometheus-stack external-secrets guestbook; do
  kubectl patch application $app -n argocd \
    --type merge -p '{"metadata":{"finalizers":["resources-finalizer.argocd.argoproj.io"]}}'
done

# Step 7: Sync tất cả
argocd app sync root-platform
```

---

## Challenge 6 (Bonus): Self-managed ArgoCD — ArgoCD deploy chính nó

**Độ khó:** Rất cao
**Thời gian:** 45 phút
**Context:** Chicken-and-egg: ArgoCD cần ArgoCD để deploy chính nó.

### Tình huống

```
Muốn dùng App of Apps để bootstrap toàn bộ cluster.
Nhưng root-app cần ArgoCD Application Controller để sync.
Và ArgoCD cần được deploy trước.

Cách nào deploy ArgoCD mà không dùng kubectl apply?

A. ArgoCD Installer (Helm chart) — declarative nhưng không phải App of Apps
B. ArgoCD Autopilot — opinionated App of Apps cho chính ArgoCD
C. ArgoCD operator — declarative, quản lý ArgoCD như CRD
D. Manual kubectl apply cho ArgoCD + App of Apps cho phần còn lại
```

### Yêu cầu

1. Đánh giá 4 approach trên (pros/cons)
2. Thiết kế hybrid approach: ArgoCD operator quản lý chính nó + App of Apps cho platform
3. Tạo architecture diagram
4. Implement solution
5. Verify: ArgoCD tự deploy, sau đó tự quản lý qua App of Apps

### Recommended architecture

```
Phase 1: Bootstrap (imperative, 1 lần duy nhất)
─────────────────────────────────────────────────
kubectl apply -f argocd-install.yaml
# ArgoCD operator hoặc Helm install argocd

Phase 2: ArgoCD running
─────────────────────────────────────────────────
ArgoCD Application Controller
  └── root-platform (App of Apps)

Phase 3: GitOps bootstrap
─────────────────────────────────────────────────
Git: platform-repo/argocd/applications/
  ├── root-platform.yaml     ← Tự deploy qua chính ArgoCD
  ├── cert-manager.yaml
  ├── ingress-nginx.yaml
  └── ...

Root app sync:
  root-platform → ArgoCD tự tạo child apps
  → ArgoCD tự deploy chính nó? Loop!

Fix: Root app KHÔNG include argocd-install.yaml
     Chỉ quản lý phần platform sau khi ArgoCD đã chạy
```

### Key insight

```
ArgoCD bootstrap ≠ ArgoCD management

Bootstrap:  ArgoCD cần được install trước
            → Dùng: Helm, Operator, hoặc kubectl apply (1 lần)

GitOps:     Sau khi ArgoCD chạy, dùng App of Apps để quản lý
            mọi thứ (bao gồm cập nhật ArgoCD)

Cập nhật ArgoCD qua GitOps:
  Helm values thay đổi → ArgoCD detect → ArgoCD apply → ArgoCD update
  → Không loop vì Helm values ≠ ArgoCD Application definition
```

---

## Bonus: ArgoCD Autopilot Quick Intro

ArgoCD Autopilot là CLI tool tạo App of Apps opinionated cho ArgoCD.

```bash
# Cài autopilot
brew install argocd-autopilot/argocd-autopilot/argocd-autopilot

# Khởi tạo repo
argocd-autopilot repo init

# Tạo App of Apps cho ArgoCD + platform
argocd-autopilot generate app platform \
  --app github.com/YOUR_ORG/platform-repo \
  --deployment-path ./argocd/bootstrap \
  --timeout 5m

# Apply (tạo root app + bootstrap)
argocd-autopilot apply -f AppPlatform.yaml
```

ArgoCD Autopilot tự tạo folder structure, sync waves, và opinions. Day 25 sẽ học sâu hơn.

<!-- APPEND_HERE -->
