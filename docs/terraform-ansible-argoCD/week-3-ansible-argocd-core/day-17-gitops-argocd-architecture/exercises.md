# Day 17 - Exercises & Challenges

**Thực hành sau Day 17 — GitOps Principles & ArgoCD Architecture**
**Thời lượng:** 60-90 phút (6 challenges)
**Prerequisite:** Hoàn thành lab trong lesson.md

---

## Setup cho tất cả challenges

```bash
# Tạo kind cluster (dùng lại cho tất cả challenge)
kind create cluster --name argocd-day17 --wait 5m

# Cài ArgoCD v3.4.2 (pin patch version, không dùng HEAD/latest)
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

kubectl wait --for=condition=available deployment/argocd-server \
  -n argocd --timeout=300s

# Login CLI
ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d)
argocd login localhost:8080 \
  --username admin \
  --password "$ARGOCD_PWD" \
  --insecure

# Fork hoặc clone repo demo
# https://github.com/argoproj/argocd-example-apps
# Dùng fork của bạn để test private repo + credential
```

---

## Challenge 1: Multi-format Deployment

**Mục tiêu:** Deploy 3 ứng dụng khác nhau qua 3 cách: raw YAML manifest, Helm chart public, Kustomize. Dùng cả UI lẫn CLI.

**Deadline:** 20 phút

### Task 1.1 — Deploy guestbook (raw manifest) bằng declarative YAML

```bash
# Tạo file application cho raw manifest deployment
cat <<'EOF' > application-raw.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook-raw
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
      prune: true
      selfHeal: true
EOF

kubectl apply -f application-raw.yaml
argocd app get guestbook-raw
```

### Task 1.2 — Deploy Helm chart (public) bằng ArgoCD CLI

```bash
# Deploy Redis từ public Helm chart
argocd app create redis \
  --repo https://charts.bitnami.com/bitnami \
  --chart redis \
  --revision 17.0.0 \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace data \
  --sync-policy manual \
  --helm-set replicaCount=1

argocd app get redis
argocd app sync redis
```

Verify bằng declarative YAML (tạo file `application-redis.yaml`):

```bash
cat <<'EOF' > application-redis.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: redis-from-yaml
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://charts.bitnami.com/bitnami
    chart: redis
    targetRevision: 17.0.0
    helm:
      parameters:
        - name: replicaCount
          value: "1"
        - name: architecture
          value: standalone
  destination:
    server: https://kubernetes.default.svc
    namespace: data
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

### Task 1.3 — Deploy Kustomize overlay từ kustomize example

```bash
# Deploy một app có kustomize overlay
argocd app create kustomize-guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path kustomize/guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace kustomize-demo \
  --sync-policy manual

argocd app sync kustomize-guestbook
```

### Task 1.4 — Verify tất cả

```bash
argocd app list

# Kiểm tra từng app
for app in guestbook-raw redis-from-yaml kustomize-guestbook; do
  echo "=== $app ==="
  argocd app get $app | grep -E "Sync|Health"
done

# Xem resource trong cluster
kubectl get all -n default
kubectl get all -n data
kubectl get all -n kustomize-demo
```

**Deliverable:** Screenshots ArgoCD UI với 3 app Synced + Healthy. Commit file YAML manifests vào repo Git.

**Verification:**
- `argocd app list` → 3 app, all Synced + Healthy
- `kubectl get pods -A` → pods running ở đúng namespace
- YAML files pushed lên Git repo

---

## Challenge 2: Private GitHub Repository Configuration

**Mục tiêu:** Cấu hình ArgoCD để deploy từ private GitHub repo dùng Personal Access Token (PAT). Hiểu cách ArgoCD lưu credential.

**Deadline:** 15 phút

### Task 2.1 — Tạo GitHub Personal Access Token

1. GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
2. Generate new token (classic)
3. Scopes: `repo` (full control of private repositories)
4. Copy token (token sẽ không hiển thị lại)

### Task 2.2 — Thêm credential vào ArgoCD

```bash
# Thêm private repo qua CLI
argocd repo add https://github.com/<your-username>/<your-private-repo>.git \
  --username <your-github-username> \
  --password <your-PAT> \
  --insecure  # Dev only

# Verify
argocd repo list
# Nên thấy repo trong list
```

### Task 2.3 — Inspect credential storage (security)

```bash
# Credential được lưu trong Kubernetes Secret
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=repo-creds
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=repo-creds \
  -o jsonpath='{.items[*].metadata.name}'

# Inspect credential (encrypted trong cluster)
kubectl get secret -n argocd \
  $(kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=repo-creds \
    -o jsonpath='{.items[0].metadata.name}') \
  -o yaml

# Note: password/token stored as stringData (base64 encoded in data)
# Production: nên dùng Sealed Secrets hoặc External Secrets Operator
```

### Task 2.4 — Deploy app từ private repo

```bash
# Tạo Application trỏ vào private repo
argocd app create private-app \
  --repo https://github.com/<your-username>/<your-private-repo>.git \
  --path ./manifests \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace private-demo \
  --sync-policy manual

argocd app sync private-app
```

### Task 2.5 — Cleanup

```bash
argocd repo rm https://github.com/<your-username>/<your-private-repo>.git
argocd app delete private-app --cascade
```

**Deliverable:** Private repo deployed thành công. Giải thích bằng text: credential lưu ở đâu, cách encrypt.

**Verification:**
- `argocd app get private-app` → Synced + Healthy
- Credential secret có trong `kubectl get secret -n argocd`

**Security note (production):**
```bash
# Production: dùng GitHub App authentication thay vì PAT
# GitHub App có permission scope tinh chỉnh hơn, không expire như PAT
argocd repo add https://github.com/<org>/<repo> \
  --github-app-id <id> \
  --github-app-installation-id <inst-id> \
  --github-app-private-key-path ./github-app-private-key.pem
```

---

## Challenge 3: Drift Detection & Self-Heal Timing

**Mục tiêu:** Bật automated + selfHeal, simulate drift, đo thời gian ArgoCD reconcile.

**Deadline:** 15 phút

### Task 3.1 — Tạo Application với automated + selfHeal

```bash
# Dùng guestbook đã deploy từ Challenge 1
# Hoặc tạo mới
cat <<'EOF' > application-selfheal.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook-selfheal
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: selfheal-test
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

kubectl apply -f application-selfheal.yaml
argocd app sync guestbook-selfheal

# Verify initial state
argocd app get guestbook-selfheal
kubectl get deployment guestbook-ui -n selfheal-test
```

### Task 3.2 — Simulate drift và measure reconciliation time

```bash
# Record initial state
INITIAL_REPLICAS=$(kubectl get deployment guestbook-ui -n selfheal-test \
  -o jsonpath='{.spec.replicas}')
echo "Initial replicas: $INITIAL_REPLICAS"

# Apply drift: change replicas to 5
kubectl scale deployment guestbook-ui -n selfheal-test --replicas=5
echo "Drift applied: replicas = 5"

# Measure time until self-heal
START_TIME=$(date +%s)

# Watch replicas until restored
while true; do
  CURRENT=$(kubectl get deployment guestbook-ui -n selfheal-test \
    -o jsonpath='{.spec.replicas}' 2>/dev/null)
  echo "[$(date '+%H:%M:%S')] replicas: $CURRENT"
  if [ "$CURRENT" = "$INITIAL_REPLICAS" ]; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    echo ""
    echo "=== Self-heal complete ==="
    echo "Time to reconcile: ${ELAPSED} seconds"
    echo "(Expected: ~180 seconds default reconciliation interval)"
    break
  fi
  sleep 10
done
```

### Task 3.3 — Accelerate reconciliation (optional bonus)

```bash
# Thay đổi reconciliation interval xuống 30 giây để test nhanh hơn
# (Chỉ dùng cho dev, không production)

# Patch argocd-cm
kubectl patch configmap argocd-cm -n argocd \
  --type=merge \
  -p '{"data":{"timeout.reconciliation":"30s"}}'

# Xóa deployment để test lại với interval mới
kubectl delete deployment guestbook-ui -n selfheal-test

# ArgoCD sẽ recreate (vì selfHeal=true)
# Lần này self-heal nhanh hơn

# Verify interval changed
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.timeout\.reconciliation}'
```

### Task 3.4 — Simulate 3 loại drift khác nhau

```bash
# Drift 1: Image tag change (manual)
kubectl set image deployment/guestbook-ui \
  guestbook-ui=redis:alpine \
  -n selfheal-test

# ArgoCD sẽ self-heal về image từ Git (guestbook:v1.0.0)
# Wait ~30s hoặc ~180s (tùy reconciliation interval)

# Drift 2: Resource label change
kubectl label deployment guestbook-ui \
  -n selfheal-test \
  app=manually-edited --overwrite

# ArgoCD sẽ self-heal (bỏ label không đúng)

# Drift 3: Resource deletion
kubectl delete svc guestbook -n selfheal-test

# ArgoCD sẽ recreate service (vì selfHeal=true + automated)
```

**Deliverable:** Đo được thời gian reconcile. Giải thích: default 180s, cách accelerate cho dev.

**Verification:**
- Có số đo thời gian cụ thể (VD: 42 giây, 180 giây)
- Hiểu được retry interval

---

## Challenge 4: Debugging — Application Stuck "Progressing"

**Mục tiêu:** Debug một Application bị stuck Progressing trong 10 phút. Checklist 5 bước debug.

**Deadline:** 15 phút

### Task 4.1 — Tạo scenario gây stuck

```bash
# Tạo Application với resource không thể schedule
cat <<'EOF' > application-broken.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: broken-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: broken-namespace
  syncPolicy:
    automated: {}
EOF

# Apply nhưng namespace không có resource limit đủ
kubectl create namespace broken-namespace
# Không tạo ResourceQuota nhưng app cần resources

kubectl apply -f application-broken.yaml
argocd app sync broken-app

# Watch status
argocd app get broken-app --watch
```

### Task 4.2 — 5-step debugging checklist

```bash
# STEP 1: Check ArgoCD Application CRD status
argocd app get broken-app
# Quan sát: Sync status? Health status? Revision?

# STEP 2: Check Kubernetes events trong destination namespace
kubectl get events -n broken-namespace --sort-by='.lastTimestamp'
kubectl describe events -n broken-namespace

# STEP 3: Check resource status — pods pending/failed
kubectl get pods -n broken-namespace -o wide
kubectl describe pod -n broken-namespace <pod-name>

# STEP 4: Check ArgoCD controller logs
kubectl logs -n argocd statefulset/argocd-application-controller \
  --tail=100 --timestamps | grep -i "broken-app\|error\|failed"

# STEP 5: Check repo-server logs (manifest render issues)
kubectl logs -n argocd deploy/argocd-repo-server \
  --tail=50 --timestamps | grep -i "broken\|error\|manifest"

# BONUS: Check application-controller events
kubectl get events -n argocd --field-selector involvedObject.name=broken-app \
  --sort-by='.lastTimestamp'

# Check resource in cluster
kubectl get application broken-app -n argocd -o yaml | \
  grep -A 20 "status:"
```

### Task 4.3 — Root cause identification

```bash
# Thường root causes:
# 1. ImagePullBackOff (image không tồn tại hoặc registry không accessible)
kubectl get pod -n broken-namespace -o jsonpath='{range .items[*]}{.status.containerStatuses[*].state}{"\n"}'

# 2. CrashLoopBackOff (app startup fail)
kubectl logs -n broken-namespace <pod-name> --previous 2>/dev/null

# 3. PVC pending (storage not bound)
kubectl get pvc -n broken-namespace

# 4. RBAC issue (ServiceAccount không có quyền)
kubectl auth can-i get pods --as=system:serviceaccount:broken-namespace:default

# 5. ArgoCD health check timeout (app mất quá lâu để healthy)
```

### Task 4.4 — Fix và verify

```bash
# Fix: Apply đủ resource quota hoặc xóa resource limit
kubectl patch namespace broken-namespace \
  -p '{"metadata":{"annotations":{"kubectl.kubernetes.io/last-applied-configuration":""}}}'

# Force ArgoCD refresh
argocd app sync broken-app --force

# Verify
argocd app get broken-app
```

**Deliverable:** Viết debug report 5 bước cho scenario trên.

**Debug report template:**

```
## Debug Report: broken-app Stuck Progressing

**1. Application Status:**
- Sync status: [Synced/OutOfSync/Unknown]
- Health status: [Healthy/Progressing/Degraded]
- Revision: [commit SHA]

**2. Kubernetes Events:**
[kubectl get events output]

**3. Pod Status:**
[kubectl get pods output]

**4. Controller Logs:**
[paste relevant log lines]

**5. Repo-server Logs:**
[paste relevant log lines]

**Root Cause:** [mô tả]

**Fix Applied:** [cách fix]

**Verification:** [kết quả sau fix]
```

---

## Challenge 5: Disaster Recovery Simulation

**Mục tiêu:** Simulate mất ArgoCD namespace, restore từ Git-backed configuration.

**Deadline:** 15 phút

### Task 5.1 — Backup ArgoCD configuration

```bash
# Backup: Export tất cả Application manifests
mkdir -p /tmp/argocd-backup

kubectl get application -n argocd -o yaml > /tmp/argocd-backup/applications.yaml
kubectl get appproject -n argocd -o yaml > /tmp/argocd-backup/appprojects.yaml
kubectl get configmap -n argocd -o yaml > /tmp/argocd-backup/configmaps.yaml
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type!=repo-creds \
  -o yaml > /tmp/argocd-backup/secrets.yaml

# Ngoài ra: backup ArgoCD repo credentials (encrypted)
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=repo-creds \
  -o yaml > /tmp/argocd-backup/repo-creds.yaml

echo "Backup complete: $(ls -la /tmp/argocd-backup/)"
```

### Task 5.2 — GitOps-ify ArgoCD Configuration

```bash
# Best practice: ArgoCD config itself cũng nên được GitOps-化管理
# Tạo repo riêng cho argocd-config

# Backup có thể push lên Git:
# git init /tmp/argocd-backup
# git add .
# git commit -m "Backup $(date)"
```

### Task 5.3 — Simulate disaster

```bash
# WARNING: Xóa ArgoCD namespace (production data loss simulation)
# Trong thực tế: accidental deletion hoặc cluster crash

# Đầu tiên: xác nhận backup OK
wc -l /tmp/argocd-backup/applications.yaml

# Simulate: xóa ArgoCD namespace
kubectl delete namespace argocd
kubectl get namespace argocd  # Should be Terminating hoặc NotFound

# Verify applications gone
argocd app list 2>&1 | head -5
# Expected: error "Unauthorized" hoặc connection refused
```

### Task 5.4 — Restore from backup

```bash
# Bước 1: Recreate ArgoCD namespace
kubectl create namespace argocd

# Bước 2: Reinstall ArgoCD
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

kubectl wait --for=condition=available deployment/argocd-server \
  -n argocd --timeout=300s

# Bước 3: Login lại
ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d)
argocd login localhost:8080 \
  --username admin \
  --password "$ARGOCD_PWD" \
  --insecure

# Bước 4: Restore Applications
kubectl apply -f /tmp/argocd-backup/applications.yaml

# Verify restore
argocd app list
```

### Task 5.5 — Post-restore verification

```bash
# ArgoCD UI: verify apps hiển thị
argocd app get guestbook-raw  # tên từ Challenge 1

# ArgoCD có thể cần sync lại vì cluster state đã bị reset
# (ArgoCD namespace bị xóa = cluster credentials thay đổi)
for app in $(argocd app list -o name | xargs); do
  echo "Syncing $app..."
  argocd app sync $app --force
done

# Verify all apps healthy
argocd app list -o wide
```

**Deliverable:** Video/screenshot recovery flow. Giải thích: tại sao backup/restore cần thiết, GitOps-ify ArgoCD config như thế nào.

**Verification:**
- ArgoCD restored, app list hiển thị đúng
- Tất cả app Synced + Healthy sau recovery

**Lesson learned:**
```bash
# GitOps-ify ArgoCD configuration (production practice):
# ArgoCD nên được bootstrapped từ Git, không phải manual apply

# ArgoCD Bootstrap Pattern (Day 22-25):
# 1. Cluster init: kubectl apply argocd manifests
# 2. ArgoCD managed: argocd-apps repo chứa Application definitions
# 3. ArgoCD tự sync Application definitions từ Git
# 4. Kể cả ArgoCD config cũng nằm trong Git

# Tool: argocd-autopilot
argocd-autopilot repo init
argocd-autopilot project create <project>
argocd-autopilot app create <app>
```

---

## Challenge 6 (Advanced): Reconciliation Performance at Scale

**Mục tiêu:** So sánh latency reconciliation ở 2 interval khác nhau (3 phút vs 1 phút) trên 50 synthetic Application. Đo CPU/Memory usage của application-controller.

**Deadline:** 20 phút

### Task 6.1 — Generate 50 synthetic Applications

```bash
# Script generate 50 Application manifest
cat <<'SCRIPT' > /tmp/generate-apps.sh
#!/bin/bash
NAMESPACE="argocd"
REPO_URL="https://github.com/argoproj/argocd-example-apps.git"
REVISION="HEAD"
PATH="guestbook"

for i in $(seq 1 50); do
  cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app-$(printf "%03d" $i)
  namespace: $NAMESPACE
spec:
  project: default
  source:
    repoURL: $REPO_URL
    targetRevision: $REVISION
    path: $PATH
  destination:
    server: https://kubernetes.default.svc
    namespace: scale-test-ns
  syncPolicy:
    automated:
      prune: false
      selfHeal: false
EOF
  echo "Created app-$(printf "%03d" $i)"
done
SCRIPT

chmod +x /tmp/generate-apps.sh
bash /tmp/generate-apps.sh
```

### Task 6.2 — Measure baseline (3-minute interval)

```bash
# Đợi ArgoCD sync tất cả app
echo "Waiting for initial sync to complete..."
sleep 30

# Baseline: measure controller resource usage với 3-minute interval
kubectl top pods -n argocd 2>/dev/null || \
  echo "metrics-server not installed (skip memory/CPU metrics)"

# Count OutOfSync apps
argocd app list | grep -c OutOfSync

# Trigger manual sync all apps
for app in $(argocd app list -o name | xargs); do
  argocd app sync $app --force 2>/dev/null &
done

# Measure time cho 50 apps sync
START=$(date +%s)
sleep 10
argocd app list | grep -c OutOfSync  # check remaining
END=$(date +%s)
echo "Sync completed in $((END-START)) seconds"

# Baseline metrics
echo "=== Baseline: 3-minute reconciliation ==="
kubectl get deployment argocd-application-controller -n argocd \
  -o jsonpath='{.spec.replicas}'
kubectl get pod -n argocd -l app.kubernetes.io/component=application-controller \
  -o jsonpath='{.items[0].spec.containers[0].resources}'
```

### Task 6.3 — Change to 1-minute interval và measure

```bash
# Change reconciliation interval to 1 minute
kubectl patch configmap argocd-cm -n argocd \
  --type=merge \
  -p '{"data":{"timeout.reconciliation":"60s"}}'

# Restart controller để apply change
kubectl rollout restart statefulset argocd-application-controller -n argocd
kubectl rollout status statefulset argocd-application-controller -n argocd \
  --timeout=120s

# Verify interval changed
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.timeout\.reconciliation}'

# Wait 60 seconds, observe more frequent reconciliation
echo "Observing reconciliation for 2 minutes (should see 2 reconcile cycles)..."
sleep 120

# Compare: controller logs count
kubectl logs -n argocd statefulset/argocd-application-controller \
  --since=3m --tail=200 | grep -c "Reconciled" || echo "0"
```

### Task 6.4 — Simulate drift và measure detection time

```bash
# Apply drift to 10 apps (change replicas manually)
for i in $(seq 1 10); do
  kubectl scale deployment guestbook-ui -n scale-test-ns \
    --replicas=$((i+10)) 2>/dev/null || true
done

# Measure time until ArgoCD detects drift
START=$(date +%s)

# Watch argocd app list
while true; do
  OUT_OF_SYNC=$(argocd app list 2>/dev/null | grep -c OutOfSync || echo 0)
  echo "[$(date '+%H:%M:%S')] OutOfSync count: $OUT_OF_SYNC"
  if [ "$OUT_OF_SYNC" -ge 10 ]; then
    END=$(date +%s)
    echo ""
    echo "=== Drift detected ==="
    echo "Detection time: $((END-START)) seconds"
    echo "(Expected: <= 60 seconds with 1-min interval)"
    break
  fi
  sleep 5
done
```

### Task 6.5 — Resource comparison

```bash
# Capture metrics với cả 50 apps
echo "=== Resource usage with 50 apps ==="
kubectl describe statefulset argocd-application-controller -n argocd | \
  grep -A 5 "Limits\|Requests"

kubectl describe deployment argocd-repo-server -n argocd | \
  grep -A 5 "Limits\|Requests"

# Calculate: nếu scale lên 500 apps, cần bao nhiêu controller replicas?
echo ""
echo "=== Scale estimation ==="
echo "Current: 50 apps, 1 controller"
echo "For 500 apps: estimate 3-5 controller shards"
echo "For 1000+ apps: use consistent-hash sharding"
```

### Task 6.6 — Cleanup

```bash
# Xóa 50 synthetic apps
for i in $(seq 1 50); do
  kubectl delete application app-$(printf "%03d" $i) -n argocd 2>/dev/null || true
done

# Reset reconciliation interval
kubectl patch configmap argocd-cm -n argocd \
  --type=merge \
  -p '{"data":{"timeout.reconciliation":"180s"}}'

# Verify
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.timeout\.reconciliation}'
```

**Deliverable:**
- Bảng so sánh reconciliation latency 3 phút vs 1 phút
- Số liệu CPU/Memory controller usage
- Phân tích: khi nào nên dùng interval ngắn, khi nào dùng interval dài

**Expected results:**

```
=== Reconciliation Interval Comparison ===

| Interval | Drift Detection | API Server Load | Controller CPU |
|----------|-----------------|-----------------|----------------|
| 180s     | Up to 3 min     | Low             | ~250m CPU      |
| 60s      | Up to 1 min     | Medium          | ~500m CPU      |
| 10s      | Up to 10s       | High            | ~1 CPU         |

Recommendation:
- Production (stable apps): 180s-600s (reduce load)
- Dev environment (frequent changes): 30s-60s
- Progressive delivery / canary: 10s (near real-time)
- > 1000 apps: use sharding instead of short interval
```

---

## Bonus: Cleanup tất cả Challenge artifacts

```bash
# Xóa tất cả apps
argocd app list -o name | xargs -I {} argocd app delete {} --cascade

# Xóa namespaces tạo trong lab
kubectl delete namespace default data kustomize-demo private-demo \
  selfheal-test broken-namespace scale-test-ns \
  2>/dev/null || true

# Reset argocd-cm
kubectl patch configmap argocd-cm -n argocd \
  --type=merge \
  -p '{"data":{"timeout.reconciliation":"180s"}}'

# Xóa ArgoCD
kubectl delete -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

# Xóa kind cluster
kind delete cluster --name argocd-day17

echo "All cleanup done."
```

---

## Challenge Solutions Summary

```
Challenge 1: Multi-format Deployment
  ✅ 3 apps deployed (raw YAML, Helm, Kustomize)
  ✅ CLI + declarative YAML methods practiced

Challenge 2: Private GitHub Repo
  ✅ PAT credential added to ArgoCD
  ✅ Secret inspected (security awareness)
  ✅ Private repo deployed

Challenge 3: Drift & Self-Heal
  ✅ Drift simulated và self-heal timed
  ✅ Measured reconciliation latency (VD: ~45s hoặc ~180s)
  ✅ Interval acceleration tested

Challenge 4: Debugging Stuck Progressing
  ✅ 5-step debug checklist completed
  ✅ Root cause identified và fixed

Challenge 5: Disaster Recovery
  ✅ ArgoCD backup created
  ✅ Simulated loss và full recovery
  ✅ App state restored from YAML

Challenge 6: Performance at Scale
  ✅ 50 synthetic apps generated
  ✅ Reconciliation latency compared (3m vs 1m)
  ✅ Resource usage measured
```

---

**Sau khi hoàn thành tất cả challenges:**
- Quay lại lesson.md Section 6 (Kiểm tra hiểu bài)
- Đọc document.md để ôn tập architecture
- Chuẩn bị Day 18: ArgoCD Application CRD chi tiết + AppProject + Sync Policy
