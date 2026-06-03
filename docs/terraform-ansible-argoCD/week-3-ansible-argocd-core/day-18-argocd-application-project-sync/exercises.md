# Day 18 - Exercises

**Mỗi challenge hoàn thành trong 10-15 phút. Cluster: `argocd-day17` (ArgoCD pre-installed)**

---

## Challenge 1: Multi-Application với Sync Policy theo Environment

**Mục tiêu:** Tạo 3 Application (api-service, worker-service, frontend) trong project `team-platform`, mỗi app có sync policy phù hợp với môi trường.

### Phần A: Tạo Git repo manifest (nếu chưa có từ lab)

```bash
mkdir -p ~/gitops-lab-day18/services/{api,worker,frontend}
```

Tạo 3 deployment manifest đơn giản (nginx-based), mỗi cái gồm:
- Deployment với 2 replicas, readiness/liveness probe
- Service ClusterIP
- ConfigMap với biến `ENV`, `LOG_LEVEL`

### Phần B: Tạo AppProject

Tạo project `team-platform` với:
- sourceRepos: repo của bạn
- destinations: `dev`, `staging`, `production` namespaces
- 2 roles: `developer` (sync dev/staging) và `admin` (full control)

### Phần C: Tạo 3 Application

| Application | Env | Sync Policy | selfHeal | prune |
|---|---|---|---|---|
| `team-platform/api-dev` | dev | automated | true | false |
| `team-platform/api-staging` | staging | automated | true | false |
| `team-platform/api-prod` | prod | manual | false | false |

Tạo đủ 3 Application YAML và apply.

**Deliverable:**
```bash
argocd app list
# Hiển thị 3 app, status và sync policy đúng
```

**Verify:**
1. Sync dev và staging bằng automated (chờ 3 phút hoặc trigger webhook)
2. Prod phải cần manual sync: `argocd app sync team-platform/api-prod`
3. Scale dev namespace bằng kubectl → verify selfHeal hoạt động

---

## Challenge 2: AppProject cho Multi-team

**Mục tiêu:** Thiết kế AppProject cho 3 team: `platform`, `payments`, `data`. Viết RBAC policy cho 3 role: `viewer`, `deployer`, `admin`.

### Yêu cầu thiết kế

```
Platform Team:
  - repo: https://github.com/acme/platform-repo.git
  - namespaces: platform-dev, platform-staging, platform-prod
  - Resources: Deployments, Services, ConfigMaps, Ingress
  - Viewer: mọi người
  - Deployer: platform-dev group, được sync dev/staging
  - Admin: platform-team-leads, full control

Payments Team:
  - repo: https://github.com/acme/payments-repo.git
  - namespaces: payments-dev, payments-staging, payments-prod
  - Blacklist: không cho tạo Pod privileged
  - Viewer: payments-dev group
  - Deployer: payments-dev group, được sync dev/staging
  - Admin: payments-team-leads, full control

Data Team:
  - repo: https://github.com/acme/data-repo.git
  - namespaces: data-dev, data-staging, data-prod, ml-dev, ml-prod
  - Viewer: data-team group
  - Deployer: data-team group, được sync all namespace
  - Admin: data-team-leads, full control
```

### Deliverable

```yaml
# File: appproject-multi-team.yaml
# 3 AppProject objects trong 1 file (sử dụng YAML document separator)
---
# apiVersion: argoproj.io/v1alpha1
# kind: AppProject
# metadata:
#   name: team-platform
# ...
---
# apiVersion: argoproj.io/v1alpha1
# kind: AppProject
# metadata:
#   name: team-payments
# ...
---
# apiVersion: argoproj.io/v1alpha1
# kind: AppProject
# metadata:
#   name: team-data
# ...
```

**Verify:**
```bash
kubectl apply -f appproject-multi-team.yaml -n argocd
argocd proj list
# 3 projects hiển thị

# Test RBAC: tạo user payment-dev (không có quyền deploy prod)
argocd account can-i sync applications 'team-platform/api-prod' --role deployer
# Expected: no
```

---

## Challenge 3: Debug Application OutOfSync

**Mục tiêu:** Application luôn OutOfSync dù không ai sửa manifest. Debug và fix.

### Setup

```bash
# Tạo application với Deployment có 1 container đơn giản
# Apply Application → sync thành công (Synced + Healthy)
# Nhưng sau đó ArgoCD liên tục báo OutOfSync
```

### Triệu chứng

```bash
argocd app get challenge3-app
# Status: OutOfSync (liên tục)
# Diff không cho thấy gì khác biệt rõ ràng
# Hoặc diff hiển thị: creationTimestamp, managedFields, some-annotation khác nhau
```

### Nhiệm vụ

1. Sử dụng `argocd app diff challenge3-app -o json` hoểm tra diff chi tiết
2. Sử dụng `kubectl get deployment <name> -n <ns> -o yaml` để xem resource trên cluster
3. Xác định nguyên nhân (thường gặp: `managedFields`, `creationTimestamp`, annotations tự sinh)
4. Thêm `ignoreDifferences` phù hợp vào Application
5. Verify: sau khi apply patch, app chuyển sang `Synced`

### Các nguyên nhân phổ biến cần test

| # | Scenario | Expected Cause |
|---|---|---|
| 1 | Deployment được `kubectl apply` (client-side) lần đầu | `managedFields` khác nhau |
| 2 | CronJob tạo Job, Job tạo Pod → Pod có label khác | `managedFields` |
| 3 | ArgoCD tự thêm annotation `argocd.argoproj.io/reconcile-at` | Annotation |
| 4 | Pod có `securityContext` với `fsGroup` được mount tự set | Field auto-mutated |

### Deliverable

```bash
# Command để verify fix
argocd app get challenge3-app
# Status: Synced ✓
# Không còn OutOfSync liên tục
```

**Hint:** Dùng `kubectl get <resource> -o yaml | grep -E 'managedFields|creationTimestamp|annotations'` để so sánh.

---

## Challenge 4: Production Incident Simulation — Prune xóa nhầm

**Mục tiêu:** Simulate production incident khi `automated + prune` xóa resource quan trọng. Viết recovery runbook.

### Scenario

```
Engineer refactor: đổi tên file từ deployment.yaml → deployment-v2.yaml
Commit và push lên main branch
ArgoCD automated + selfHeal + prune sync:
  → ArgoCD xóa Deployment cũ (vì file không còn trong Git)
  → ArgoCD tạo Deployment mới (vì deployment-v2.yaml có trong Git)
  → Nhưng Deployment mới chưa ready → downtime 5 phút
```

### Phần A: Setup (trên staging để an toàn)

```bash
# 1. Tạo 2 deployment: api-v1 và api-v2 (chỉ 1 trong Git tại 1 thời điểm)
# Initial: chỉ có api-v1 trong Git
# 2. Apply Application với automated + selfHeal + prune
# 3. Verify Synced + Healthy
```

### Phần B: Simulate incident

```bash
# 1. Đổi tên file deployment trong Git (giả lập refactor)
mv api-v1-deployment.yaml api-v2-deployment.yaml
git add .
git commit -m "refactor: rename to v2"
git push

# 2. Observe ArgoCD behavior (trong 3 phút)
watch argocd app get challenge4-app

# 3. Sau khi ArgoCD sync:
#    - Check resource trên cluster
kubectl get all -n challenge-ns

# 4. Nếu resource mới chưa ready: observe downtime
#    - ArgoCD có thể báo Degraded (rolling update)
```

### Phần C: Write recovery runbook

Viết file `runbook-prune-incident.md`:

```markdown
# Runbook: Prune Incident Recovery

## Incident
Ngày: ...
App: ...
Người phát hiện: ...

## Root Cause
[Phân tích nguyên nhân]

## Timeline
- HH:MM - Engineer commit refactor
- HH:MM - ArgoCD sync (prune triggered)
- HH:MM - Resource bị xóa
- HH:MM - Recovery bắt đầu
- HH:MM - Recovery hoàn tất

## Recovery Steps
1. [Step]
2. [Step]
...

## Prevention
- [ ] Enable PruneLast=true trước khi bật automated+prune
- [ ] Setup ArgoCD notification (Slack/PagerDuty) cho prune event
- [ ] Review PruneProtection (nếu dùng ArgoCD v2.5+)
- [ ] Mandatory staging test trước khi bật prune trên production
```

### Deliverable

```bash
# 1. Recovery runbook file
cat runbook-prune-incident.md

# 2. Verification: sau khi recover, app Synced + Healthy
argocd app get challenge4-app
```

---

## Challenge 5: Migrate 5 Applications sang Project riêng (Zero-downtime)

**Mục tiêu:** Refactor: convert 5 Application từ `default` project sang project `team-checkout`. Migration không downtime.

### Setup

```bash
# Tạo 5 Application trong default project (migrating)
# Thay vì tạo thủ công, dùng script generate
for i in {1..5}; do
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: checkout-service-$i
  namespace: argocd
  labels:
    app: checkout-service
    tier: backend
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_REPO/checkout-repo.git
    targetRevision: main
    path: services/checkout-$i
  destination:
    server: https://kubernetes.default.svc
    namespace: checkout-staging
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
EOF
done
```

### Migration Steps

Thực hiện migration theo checklist:

```bash
# Bước 1: Tạo destination project với đầy đủ config
# File: team-checkout-project.yaml (dùng document.md Template 1)
kubectl apply -f team-checkout-project.yaml -n argocd

# Bước 2: Verify project tồn tại
argocd proj get team-checkout

# Bước 3: Verify tất cả 5 app đang Synced + Healthy
argocd app list | grep checkout-service

# Bước 4: Patch từng app (zero-downtime migration)
# Migration = thay đổi spec.project
for app in checkout-service-1 checkout-service-2 checkout-service-3 checkout-service-4 checkout-service-5; do
  kubectl patch application $app -n argocd \
    --type merge \
    -p '{"metadata":{"annotations":{"migration-timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}}}}'
  kubectl patch application $app -n argocd \
    --type merge \
    -p '{"spec":{"project":"team-checkout"}}'
done

# Bước 5: Verify tất cả app vẫn Synced + Healthy sau migration
argocd app list | grep checkout-service
argocd app get checkout-service-1  # Verify project = team-checkout

# Bước 6: Verify không có resource nào bị xóa
kubectl get all -n checkout-staging | wc -l
# Số resource phải giống trước migration
```

### Deliverable

```bash
# 1. Team-checkout project created
argocd proj get team-checkout

# 2. All 5 apps migrated, still Synced + Healthy
argocd app list | grep -E "checkout|PROJECT"

# 3. Resource count unchanged
# 4. Migration timestamp recorded in annotations
```

---

## Challenge 6 (Advanced): Sync Windows cho Production

**Mục tiêu:** Implement production sync windows:
1. Deny sync cuối tuần (Friday 18:00 → Monday 06:00)
2. Deny sync 12h-13h hằng ngày
3. Validate behavior bằng `argocd app sync`

### Phần A: Design sync windows

```yaml
# File: prod-project-with-windows.yaml
# AppProject: prod-platform với sync windows
```

Thiết kế 2 deny windows:

| Window | Schedule | Duration | Scope |
|---|---|---|---|
| Weekend block | `0 18 * * 5` (Fri 18:00) | 60h | `*prod*` |
| Lunch block | `0 12 * * 1-5` (Mon-Fri 12:00) | 1h | `*prod*` |

### Phần B: Create project + application

```bash
# 1. Apply project
kubectl apply -f prod-project-with-windows.yaml -n argocd

# 2. Tạo 1 sample Application trong project
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prod-api
  namespace: argocd
spec:
  project: prod-platform
  source:
    repoURL: https://github.com/YOUR_REPO/gitops-repo.git
    targetRevision: main
    path: apps/api/production
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated: {}    # automated để test
EOF

# 3. Verify sync window
argocd proj get prod-platform
```

### Phần C: Validate sync window behavior

Vì không thể đợi đến cuối tuần, dùng kỹ thuật sau:

```bash
# 1. Check sync windows hiện tại
argocd proj get prod-platform -o json | jq '.spec.syncWindows'

# 2. Tạo temporary deny window để test (set cho thời điểm hiện tại + 5 phút)
# Lưu ý: không nên làm trên production thật, dùng staging

# 3. Test: tạo temporary allow window (cho phép override deny)
argocd proj add-sync-window prod-platform allow \
  --schedule="$(date -u +'%M %H %d %m *')" \
  --duration=5m \
  --applications='*'

# 4. Verify: trong allow window, sync được phép
argocd app sync prod-api

# 5. Cleanup: xóa temporary window
argocd proj delete-sync-window prod-platform <window-id>
```

### Phần D: Document validation results

Viết file `sync-window-validation.md`:

```markdown
# Sync Window Validation Results

## Environment: staging (NOT production)

## Windows Configured
- Weekend: Fri 18:00 - Mon 06:00 (manual test via timestamp)
- Lunch: Mon-Fri 12:00-13:00

## Validation Tests
| Time | Expected | Actual | Pass |
|---|---|---|---|
| During deny window | Sync blocked | ? | ? |
| During allow window | Sync allowed | ? | ? |

## Notes
[Observations about sync window behavior]
```

### Deliverable

```bash
# 1. prod-platform project với 2 deny windows
argocd proj get prod-platform -o yaml | grep -A 20 syncWindows

# 2. prod-api application synced thành công (trong allow window)
argocd app get prod-api

# 3. Validation document
cat sync-window-validation.md
```

---

## Bonus: ArgoCD Plugin -实操

Nếu hoàn thành tất cả 6 challenges, thử thêm:

```bash
# ArgoCD có built-in prometheus metrics
# Query: argocd_app_info, argocd_app_sync_status, argocd_app_health_status

# Query Prometheus cho ứng dụng OutOfSync
argocd prometheus \
  'sum(argocd_app_sync_status{app_namespace="argocd",health_status="out_of_sync"})'

# Tạo Grafana dashboard panel cho:
# - Số app theo sync status
# - Số app theo health status
# - Sync frequency per app
# - Prune events count
```
