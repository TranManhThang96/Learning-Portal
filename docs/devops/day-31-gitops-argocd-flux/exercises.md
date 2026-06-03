# Day 31: GitOps with ArgoCD & Flux — Exercises

## Exercise 1: ArgoCD Basics — Deploy & Observe (Easy)

### Context

Bạn vừa được giao nhiệm vụ triển khai GitOps cho team. Bước đầu tiên là làm quen với ArgoCD bằng cách deploy một application đơn giản và hiểu các concepts cơ bản: Application, Sync, Health Status.

### Yêu cầu

1. Tạo kind cluster và cài ArgoCD.
2. Deploy ArgoCD example app `guestbook` từ official repo.
3. Quan sát Application status trên UI và CLI.
4. Thực hiện manual sync và auto sync.
5. Kiểm tra Application history.

### Expected Outcome

- ArgoCD UI accessible tại `https://localhost:8080`.
- Guestbook app chạy thành công với status `Synced` + `Healthy`.
- Hiểu được difference giữa manual sync và auto sync.
- Biết cách xem sync history và rollback.

### Hints

- Dùng `argocd app create` với `--sync-policy automated` cho auto-sync.
- Dùng `argocd app get <name>` để xem detailed status.
- Dùng `argocd app history <name>` để xem deployment history.

### Acceptance Criteria

- [ ] Kind cluster running với ArgoCD installed.
- [ ] Guestbook Application created và Synced.
- [ ] Có thể access ArgoCD UI và thấy app.
- [ ] Đã thử manual sync ít nhất 1 lần.
- [ ] Đã xem được app history.
- [ ] Cleanup thành công (xóa app, xóa cluster).

### Bonus Challenge

Tạo thêm một Application từ repo khác (ví dụ: `helm-guestbook` path trong cùng argocd-example-apps repo) và quan sát cả 2 apps trên UI.

<details>
<summary>Solution</summary>

```bash
# Bước 1: Tạo cluster
kind create cluster --name gitops-ex1

# Bước 2: Cài ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=180s

# Bước 3: Get password & port-forward
ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
echo "ArgoCD Password: $ARGOCD_PWD"
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# Bước 4: Login CLI
argocd login localhost:8080 --insecure --username admin --password $ARGOCD_PWD

# Bước 5: Tạo app (manual sync)
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default

# Bước 6: Check status (OutOfSync vì chưa sync)
argocd app get guestbook
# Status: OutOfSync

# Bước 7: Manual sync
argocd app sync guestbook
# Status: Synced, Health: Healthy

# Bước 8: Check pods
kubectl get pods -n default

# Bước 9: View history
argocd app history guestbook

# Bước 10: Enable auto-sync
argocd app set guestbook --sync-policy automated

# Bước 11: Bonus - thêm helm-guestbook
argocd app create helm-guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path helm-guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default \
  --sync-policy automated

argocd app list

# Cleanup
argocd app delete guestbook --cascade -y
argocd app delete helm-guestbook --cascade -y
kubectl delete namespace argocd
kind delete cluster --name gitops-ex1
```

</details>

---

## Exercise 2: Self-Healing & Drift Detection (Medium)

### Context

Team bạn đang vận hành 3 microservices trên Kubernetes với ArgoCD. Gần đây, on-call engineer thường xuyên "hotfix" bằng cách `kubectl edit` trực tiếp trên cluster, gây ra drift giữa Git và cluster. Bạn cần demo cho team thấy self-healing hoạt động như thế nào.

### Yêu cầu

1. Tạo kind cluster, cài ArgoCD.
2. Deploy guestbook app với **auto-sync + self-heal + prune** enabled.
3. Thực hiện 4 loại drift và quan sát ArgoCD xử lý:
   - **Drift 1**: Scale replicas bằng `kubectl scale`.
   - **Drift 2**: Thêm label/annotation bằng `kubectl label`.
   - **Drift 3**: Sửa image tag bằng `kubectl set image`.
   - **Drift 4**: Tạo resource mới bằng tay trong cùng namespace (ArgoCD có prune không?).
4. Cấu hình `ignoreDifferences` cho một field cụ thể (ví dụ: annotation do controller tự thêm).
5. Ghi lại kết quả mỗi drift test.

### Expected Outcome

- Drift 1-3: ArgoCD self-heal revert về Git state trong vòng 30 giây.
- Drift 4: ArgoCD KHÔNG prune resources không thuộc Application (chỉ prune resources mà ArgoCD tạo rồi bị xóa khỏi Git).
- `ignoreDifferences` hoạt động cho field chỉ định.

### Hints

- `argocd app set guestbook --self-heal` bật self-heal.
- Dùng `kubectl get deployment -w` để watch real-time changes.
- `ignoreDifferences` cấu hình trong Application spec.
- Prune chỉ áp dụng cho resources mà ArgoCD quản lý (có label `app.kubernetes.io/instance`).

### Acceptance Criteria

- [ ] 4 drift tests thực hiện thành công.
- [ ] Self-heal hoạt động cho drift 1-3.
- [ ] Hiểu rõ prune behavior (drift 4).
- [ ] `ignoreDifferences` cấu hình thành công.
- [ ] Ghi lại timeline mỗi drift (time to detect, time to heal).
- [ ] Report ngắn gọn kết quả.

### Bonus Challenge

Cấu hình ArgoCD notification gửi message (stdout/log) mỗi khi detect OutOfSync. Kiểm tra ArgoCD Application Controller logs để thấy reconciliation events.

<details>
<summary>Solution</summary>

```bash
# Setup
kind create cluster --name gitops-ex2
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=180s

ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
argocd login localhost:8080 --insecure --username admin --password $ARGOCD_PWD

# Deploy với full auto-sync + self-heal + prune
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
      prune: true
    syncOptions:
      - CreateNamespace=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /metadata/annotations/kubectl.kubernetes.io~1last-applied-configuration
EOF

argocd app sync guestbook
argocd app wait guestbook --health

# === Drift Test 1: Scale replicas ===
echo "=== Drift Test 1: Scale replicas ==="
echo "Before:"
kubectl get deployment guestbook-ui -o jsonpath='{.spec.replicas}'
echo ""

kubectl scale deployment guestbook-ui --replicas=5
echo "After manual scale:"
kubectl get deployment guestbook-ui -o jsonpath='{.spec.replicas}'
echo ""

# Chờ self-heal (10-30 giây)
sleep 30
echo "After self-heal:"
kubectl get deployment guestbook-ui -o jsonpath='{.spec.replicas}'
echo ""

# === Drift Test 2: Add label ===
echo "=== Drift Test 2: Add label ==="
kubectl label deployment guestbook-ui drift-test=true
sleep 30
kubectl get deployment guestbook-ui --show-labels

# === Drift Test 3: Change image ===
echo "=== Drift Test 3: Change image ==="
kubectl set image deployment/guestbook-ui guestbook-ui=nginx:latest
sleep 30
kubectl get deployment guestbook-ui -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""

# === Drift Test 4: Create extra resource ===
echo "=== Drift Test 4: Create extra resource ==="
kubectl run extra-pod --image=nginx -n default
sleep 30
# extra-pod vẫn tồn tại vì ArgoCD không quản lý nó
kubectl get pod extra-pod -n default

# Check ArgoCD logs cho reconciliation events
echo "=== ArgoCD Controller Logs ==="
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=20

# Check app status
argocd app get guestbook

# Cleanup
kubectl delete pod extra-pod -n default
argocd app delete guestbook --cascade -y
kubectl delete namespace argocd
kind delete cluster --name gitops-ex2
```

**Kết quả mong đợi**:

| Drift | Action | ArgoCD Response | Time to Heal |
|-------|--------|----------------|-------------|
| 1 | Scale replicas=5 | Revert to Git value | ~10-30s |
| 2 | Add label | Revert (remove label) | ~10-30s |
| 3 | Change image | Revert to Git image | ~10-30s |
| 4 | Create extra pod | KHÔNG xóa (not managed) | N/A |

</details>

---

## Exercise 3: Production GitOps Workflow Design (Hard)

### Context

Bạn là DevOps lead tại một SaaS company với 30 engineers đang chuyển từ push-based CI/CD (Jenkins + `kubectl apply`) sang GitOps. Hệ thống gồm 8 microservices, 3 environments (dev/staging/prod), và cần:

- Secret management (database passwords, API keys).
- Multi-environment promotion (dev → staging → prod).
- RBAC: dev team chỉ deploy được vào dev namespace.
- Rollback strategy rõ ràng.
- Monitoring ArgoCD health.

### Yêu cầu

1. **Thiết kế Git repository structure** cho GitOps workflow (app repos + config repo).
2. **Viết ArgoCD Application manifests** cho 1 service trên 3 environments.
3. **Cấu hình ArgoCD Project** với RBAC phù hợp:
   - `dev-team`: sync apps trong `dev` namespace.
   - `platform-team`: sync apps trong tất cả namespaces.
4. **Thiết kế secret management flow** dùng Sealed Secrets hoặc External Secrets.
5. **Viết promotion workflow**: làm sao promote version từ dev → staging → prod.
6. **Viết rollback runbook**: step-by-step rollback khi deployment fail.
7. **Thiết kế monitoring cho ArgoCD** bao gồm metrics cần track và alerts.

### Expected Outcome

- Có architecture diagram (text/mermaid) cho GitOps workflow hoàn chỉnh.
- Có YAML manifests cho ArgoCD Application, AppProject.
- Có promotion workflow document.
- Có rollback runbook.
- Có monitoring plan.

### Hints

- Dùng Kustomize overlay cho multi-environment (base + overlays/dev|staging|prod).
- ArgoCD AppProject giới hạn destination namespaces và source repos.
- Promotion = update image tag trong config repo (PR-based).
- Consider: Sync Waves cho deploy ordering, health checks cho auto-promotion.

### Acceptance Criteria

- [ ] Repository structure document hoàn chỉnh.
- [ ] ArgoCD Application YAML cho 3 environments.
- [ ] ArgoCD AppProject với RBAC policies.
- [ ] Secret management design (1 solution chi tiết).
- [ ] Promotion workflow (step-by-step).
- [ ] Rollback runbook (step-by-step).
- [ ] Monitoring plan (metrics + alerts).
- [ ] Trade-offs được ghi rõ cho mỗi decision.

### Bonus Challenge

- Implement ApplicationSet để tự động tạo Applications cho tất cả services trên tất cả environments từ 1 template.
- Viết GitHub Actions workflow cho promotion automation (PR auto-create khi new image built).

<details>
<summary>Solution</summary>

### 1. Repository Structure

```
# App repos (mỗi service 1 repo)
payment-service/
├── src/
├── Dockerfile
├── .github/workflows/
│   └── ci.yaml          # Build, test, scan, push image
└── README.md

# Config repo (1 repo cho tất cả services)
platform-gitops/
├── apps/                 # ArgoCD Application definitions
│   ├── payment-service/
│   │   ├── dev.yaml
│   │   ├── staging.yaml
│   │   └── prod.yaml
│   ├── user-service/
│   │   └── ...
│   └── ...
├── projects/             # ArgoCD AppProject definitions
│   ├── dev-team.yaml
│   └── platform-team.yaml
├── services/             # Kustomize manifests
│   ├── payment-service/
│   │   ├── base/
│   │   │   ├── kustomization.yaml
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── hpa.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       │   ├── kustomization.yaml
│   │       │   └── patches/
│   │       ├── staging/
│   │       │   ├── kustomization.yaml
│   │       │   └── patches/
│   │       └── prod/
│   │           ├── kustomization.yaml
│   │           ├── patches/
│   │           └── sealed-secrets/
│   └── ...
├── infrastructure/       # Cluster-level resources
│   ├── namespaces/
│   ├── network-policies/
│   └── sealed-secrets-controller/
└── README.md
```

### 2. ArgoCD Application YAMLs

```yaml
# apps/payment-service/dev.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payment-service-dev
  namespace: argocd
  labels:
    team: payments
    env: dev
spec:
  project: dev-team
  source:
    repoURL: https://github.com/company/platform-gitops.git
    targetRevision: main
    path: services/payment-service/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: dev
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
      prune: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
      backoff:
        duration: 5s
        maxDuration: 3m0s
        factor: 2

---
# apps/payment-service/staging.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payment-service-staging
  namespace: argocd
spec:
  project: platform-team
  source:
    repoURL: https://github.com/company/platform-gitops.git
    targetRevision: main
    path: services/payment-service/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: staging
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
      prune: false        # Staging: không auto-prune
    syncOptions:
      - CreateNamespace=true

---
# apps/payment-service/prod.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payment-service-prod
  namespace: argocd
  annotations:
    notifications.argoproj.io/subscribe.on-sync-failed.slack: prod-alerts
spec:
  project: platform-team
  source:
    repoURL: https://github.com/company/platform-gitops.git
    targetRevision: main
    path: services/payment-service/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
      prune: false        # Prod: KHÔNG auto-prune
    syncOptions:
      - CreateNamespace=false
      - ApplyOutOfSyncOnly=true
```

### 3. ArgoCD AppProject with RBAC

```yaml
# projects/dev-team.yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: dev-team
  namespace: argocd
spec:
  description: Dev team - chỉ deploy được vào dev namespace
  sourceRepos:
    - 'https://github.com/company/platform-gitops.git'
  destinations:
    - server: https://kubernetes.default.svc
      namespace: dev
      name: in-cluster
  clusterResourceWhitelist: []    # Không cho tạo cluster-scoped resources
  namespaceResourceWhitelist:
    - group: ''
      kind: '*'
    - group: apps
      kind: '*'
    - group: autoscaling
      kind: '*'
  roles:
    - name: dev-deployer
      description: Deploy to dev namespace
      policies:
        - p, proj:dev-team:dev-deployer, applications, sync, dev-team/*, allow
        - p, proj:dev-team:dev-deployer, applications, get, dev-team/*, allow
      groups:
        - dev-team          # OIDC group mapping

---
# projects/platform-team.yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform-team
  namespace: argocd
spec:
  description: Platform team - full access
  sourceRepos:
    - '*'
  destinations:
    - server: '*'
      namespace: '*'
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
  roles:
    - name: platform-admin
      description: Full access to all applications
      policies:
        - p, proj:platform-team:platform-admin, applications, *, platform-team/*, allow
      groups:
        - platform-team
```

### 4. Secret Management (Sealed Secrets)

```bash
# Install Sealed Secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create secret locally
kubectl create secret generic db-credentials \
  --namespace=prod \
  --from-literal=DB_PASSWORD=supersecret \
  --dry-run=client -o yaml > secret.yaml

# Seal it (encrypt with cluster public key)
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# Commit sealed-secret.yaml to Git (safe!)
# services/payment-service/overlays/prod/sealed-secrets/db-credentials.yaml

# ArgoCD sẽ apply SealedSecret → controller decrypt → tạo actual Secret
```

### 5. Promotion Workflow

```
Dev → Staging → Prod Promotion:

1. CI pipeline build new image:
   - payment-service:v1.2.3

2. Auto-update dev overlay (CI bot):
   - Update services/payment-service/overlays/dev/kustomization.yaml
   - Set newTag: v1.2.3
   - Auto-commit to main branch

3. ArgoCD auto-sync dev:
   - Dev cluster gets v1.2.3 automatically
   - Run smoke tests

4. Promote to staging (manual PR):
   - Create branch: promote/payment-v1.2.3-staging
   - Update overlays/staging/kustomization.yaml: newTag: v1.2.3
   - Create PR → review → merge
   - ArgoCD auto-sync staging

5. Promote to prod (manual PR with approval):
   - Create branch: promote/payment-v1.2.3-prod
   - Update overlays/prod/kustomization.yaml: newTag: v1.2.3
   - Create PR → require 2 approvers → merge
   - ArgoCD auto-sync prod (with health check)

6. Verify:
   - Check ArgoCD status: Synced + Healthy
   - Check metrics: error rate, latency
   - Check logs: no errors
```

### 6. Rollback Runbook

```markdown
# Rollback Runbook: Payment Service

## Trigger
- Error rate > 5% after deployment
- Latency p99 > 2x baseline
- Health check failing

## Steps

### Option A: Git Revert (Recommended)
1. Identify bad commit: `git log --oneline -5` trong platform-gitops repo
2. Revert: `git revert <bad-commit-sha>`
3. Push: `git push origin main`
4. ArgoCD auto-syncs → rolls back
5. Verify: `argocd app get payment-service-prod`
6. Expected: Status=Synced, Health=Healthy

### Option B: ArgoCD Rollback (Emergency)
1. `argocd app history payment-service-prod`
2. `argocd app rollback payment-service-prod <revision>`
3. ⚠️ Ngay sau đó phải git revert để Git match cluster
4. Nếu không → next sync sẽ re-apply bad version

### Verification
- [ ] ArgoCD status: Synced + Healthy
- [ ] Error rate < 1%
- [ ] Latency p99 normal
- [ ] No error logs
- [ ] Customer reports resolved

### Post-rollback
- [ ] Create incident ticket
- [ ] Notify team in Slack
- [ ] Schedule postmortem within 48h
```

### 7. Monitoring Plan

```yaml
# ArgoCD Metrics to Track:
Metrics:
  - argocd_app_info: Tổng số apps, status
  - argocd_app_sync_status: Synced vs OutOfSync
  - argocd_app_health_status: Healthy vs Degraded vs Missing
  - argocd_app_reconcile_duration: Thời gian reconcile
  - argocd_git_request_total: Git requests (detect rate limiting)
  - argocd_redis_request_total: Redis performance

Alerts:
  - AppOutOfSync > 10 minutes: Warning
  - AppDegraded > 5 minutes: Critical
  - AppSyncFailed: Critical
  - ArgoCD component unhealthy: Critical
  - Git request failures > 5/min: Warning
  - Reconcile duration > 60s: Warning

Dashboard Panels:
  - Total apps by sync status (pie chart)
  - Total apps by health status (pie chart)
  - Sync operations over time (timeline)
  - Reconcile duration p50/p95/p99 (graph)
  - Git request rate and errors (graph)
  - Top 10 slowest apps to sync (table)
```

</details>

---

## Tổng kết thời lượng

| Exercise | Thời gian | Skill level |
|----------|-----------|-------------|
| Exercise 1: ArgoCD Basics | ~30 phút | Easy |
| Exercise 2: Self-Healing & Drift | ~40 phút | Medium |
| Exercise 3: Production GitOps Design | ~50 phút | Hard |
| **Tổng** | **~2 giờ** | |

> **Lưu ý**: Exercise 3 là design exercise, không cần chạy thật. Tập trung vào thiết kế và documentation. Có thể implement từng phần nếu có thêm thời gian.

