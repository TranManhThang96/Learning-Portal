# Day 24 — Sync Waves, Hooks, Dependencies

> **Sync wave la ordering mechanism co ban. Hook la transient task chay theo phase.**
> Khong co sync wave + hook, toan bo resource apply cung 1 thoi diem -> race condition.

**Thoi luong:** 2 tieng
**Prerequisite:** Hoan thanh Day 17-23 (ArgoCD, Application, Helm/Kustomize, App-of-Apps, ApplicationSet)
**Output:** Orders app voi DB migration, sync wave ordering, failure scenarios

---

## 1. Muc tieu ngay hoc

- Hieu ro tien ly sync wave (annotation `argocd.argoproj.io/sync-wave`) va phan biet voi hook (`argocd.argoproj.io/hook`)
- Cau hinh 4 loai hook: PreSync, Sync, PostSync, SyncFail + PostDelete
- Thiet ke CRD ordering khong dung hook nhung van dam bao CRD truoc CR
- Viet migration Job idempotent (re-run duoc ma khong fail)
- Debug sync failure: Application stuck = PreSync Job failed hay Sync phase failed

---

## 2. Boi canh thuc te

### Chuyen that xay ra voi moi team

**Pain Day 21-23:** Khi deploy 1 phat toan bo resources, ArgoCD apply tat ca cung luc:

```
Commit moi: cert-manager CRD + Certificate + app Deployment + ESO CRD + ExternalSecret
ArgoCD sync:
  [TU dong] CRD? Certificate? ESO CRD? ExternalSecret? App? -> race
```

**Tinh huong 1 — ESO + ExternalSecret cung commit:**
```
Deploy: ESO Helm chart + ExternalSecret CR cung commit
Hien tuong: ExternalSecret apply loi "customresourcedefinition not found"
Ly do: ESO CRD chua kip install, ExternalSecret da apply roi
```

**Tinh huong 2 — App + DB migration cung luc:**
```
Deploy: Deployment + DB schema migration cung commit
Hien tuong: App pod start, migration Job chua chay -> 5xx lien tuc
Ly do: Deployment replicas > 0, app start truoc migration
```

**Tinh huong 3 — cert-manager + Certificate cung commit:**
```
Deploy: cert-manager CRD + Certificate cung commit
Hien tuong: Certificate stuck "Pending" hoac "Unknown"
Ly do: Certificate apply truoc khi CRD ready
```

**Solution:** Sync wave + hook framework.

---

## 3. Kien thuc nen tang — 30 phut

### 3.1 ArgoCD Sync Flow — 3 Phases + Diagram

```
Sync Operation Timeline
========================

Phase:  [     PreSync     ] [      Sync      ] [   PostSync  ]
Wave:   -10  -5   0   5      -10  0   10       0   10
         |    |    |    |      |    |   |       |    |
         v    v    v    v      v    v   v       v    v
         Job  Job  Job        CRD  CR   Job     Job  Job
         Migration            ESO  App        Smoke-test
         (PreSync             (Sync         (PostSync
          wave -5)             phase)          wave 0)
```

**3 phases cua ArgoCD sync:**

| Phase | Chay khi |Hook annotation |
|-------|---------|----------------|
| PreSync | Truoc Sync phase | `argocd.argoproj.io/hook: PreSync` |
| Sync | Default — tat ca resource khong phai hook | (default) |
| PostSync | Sau khi Sync thanh cong | `argocd.argoproj.io/hook: PostSync` |
| SyncFail | Khi Sync phase fail | `argocd.argoproj.io/hook: SyncFail` |
| PostDelete | Khi Application bi xoa | `argocd.argoproj.io/hook: PostDelete` |

### 3.2 Sync Wave — Ordering ben trong 1 Phase

```yaml
# Secret: wave -10 (chay truoc)
apiVersion: v1
kind: Secret
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-10"
# ...

# CRD: wave -5
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-5"
# ...

# Operator Deployment: wave 0
apiVersion: apps/v1
kind: Deployment
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "0"
# ...

# Custom Resource (CR): wave 10
apiVersion: operator.example.com/v1
kind: MyOperator
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "10"
```

**Quy tac ordering cua ArgoCD:**
1. Phase: PreSync -> Sync -> PostSync (SyncFail chay khi Sync fail)
2. Trong 1 phase: wave tang dan ( -10 -> 0 -> 10)
3. Trong cung 1 wave: alphabetical theo kind + name

**Chu y:** Default wave = 0. Tat ca resource khong co annotation deu la wave 0.

### 3.3 Hook — Transient Resource

Hook la **transient resource** — khong ton tai sau khi chay xong.

**Doi tuong hay dung lam hook:** Job (pho bien nhat), Pod (hiem), Command (kubectl hook)

```yaml
# Hook PreSync: DB migration Job
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-db-migration
  annotations:
    argocd.argoproj.io/hook: PreSync
    # Xoa Job sau khi thanh cong (khong can thiet nua)
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: orders/migrate:1.0.0
          command: ["flyway", "migrate"]
          env:
            - name: FLYWAY_URL
              valueFrom:
                secretKeyRef:
                  name: orders-db-creds
                  key: url
```

**Hook deletion policy — 4 tuy chon:**

| Policy | Y nghia |
|--------|---------|
| `HookSucceeded` | Xoa sau khi Job thanh cong |
| `HookFailed` | Xoa sau khi Job fail |
| `BeforeHookCreation` | Xoa Job cu truoc khi tao Job moi (default) |
| `HookSucceeded,HookFailed` | Xoa sau ca thanh cong va fail |

**Default behavior:** `BeforeHookCreation` — moi lan sync, ArgoCD xoa Job cu roi tao Job moi.

### 3.4 CRD Ordering — Built-in Heuristic

ArgoCD co **built-in dependency detection** cho CRD:
- Neu Application chua CRD va CR cung resource, ArgoCD tu dong deploy CRD truoc
- Tuy nhien co **edge case** khi CRD o 1 Application, CR o Application khac

**Edge case 1 — CRD o app A, CR o app B:**
```
App A: deploy cert-manager CRD
App B: deploy Certificate (CR)
=> Certificate apply fail vi CRD chua co
=> Giai phap: them hook PreSync vao App B kiem tra CRD ton tai
```

**Edge case 2 — CRD qua lon, install mat 2 phut:**
```
ArgoCD apply tat ca CR trong Sync phase nhung CRD chua ready
=> Giai phap: sync wave + wait hook
```

### 3.5 Idempotency — Yeu cau bat buoc cua Hook Job

Vi `BeforeHookCreation` tao Job moi moi lan sync, Job phai **idempotent**:

```
# Sai — khong idempotent
INSERT INTO schema_version (version) VALUES ('001');

# Dung — idempotent (neu co roi thi ignore)
INSERT INTO schema_version (version) VALUES ('001')
ON CONFLICT DO NOTHING;

# Dung — xoa roi tao lai (neu co migration tool ho tro)
flyway migrate -flyway.locations=filesystem:/migrations/orders
# Flyway tu dong bo qua migration da apply (bang schema_version)
```

**Flyway / Liquibase:** idempotent by design — chung duoc thiet ke de re-run duoc.
**Raw SQL script:** phai dung `ON CONFLICT DO NOTHING` hoac `IF NOT EXISTS`.

### 3.6 SyncFail — Chay Khi Sync That Bai

```yaml
# Hook SyncFail: cleanup hoac notify khi sync fail
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-syncfail-notify
  annotations:
    argocd.argoproj.io/hook: SyncFail
    argocd.argoproj.io/hook-delete-policy: HookFailed
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: notify
          image: curlimages/curl:8.11.1
          command:
            - sh
            - -c
            - |
              curl -X POST $SLACK_WEBHOOK \
                -H 'Content-type: application/json' \
                --data '{"text":"Orders sync FAILED"}'
```

**Chu y quan trong:**
- SyncFail khong chay neu reconciliation chua kip goi (race voi controller restart)
- PostSync khong chay neu Sync phase fail (chi chay khi Sync thanh cong)
- SyncFail chay ngay sau khi Sync fail, truoc khi Application status = Failed

---

## 4. Deep Dive & Trade-offs — 30 phut

### 4.1 Sync Wave vs Hook — Khi nao dung cai nao?

```
Sync wave:
  + Dung khi can ordering giua cac resource declarative
  + Khong can image, chi can annotation
  + Khong bi stuck (declarative resource thi apply thoi)
  + CRD -> CR: dung wave -5 (CRD) + wave 10 (CR)

Hook:
  + Dung khi can chay 1 task transient (migration, smoke test, backup)
  + Co exit code -> success/fail
  + Co the retry, timeout
  + Dung khi can "wait for" logic ( polling, readiness check)

Khong nen dung hook khi:
  - Chinh sua declarative resource (dung sync wave thay vi hook Job tao resource)
  - Task chay moi pod startup (dung init container thay vi hook)
```

### 4.2 3 Pattern Pho Bien Nhat

**Pattern 1 — Database Migration (PreSync Hook):**

```yaml
# orders-app/000-migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-db-migration-v1
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: OnFailure
      serviceAccountName: orders-migration-sa
      containers:
        - name: flyway
          image: flyway/flyway:10.8
          args: ["migrate", "-url=jdbc:postgresql://orders-db:5432/orders", "-user=${USER}", "-password=${PASS}"]
          envFrom:
            - secretRef:
                name: orders-db-creds
```

**Pattern 2 — Wait for Dependency (PreSync polling hook):**

```yaml
# wait-for-external-secret.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: wait-for-eso-secret
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  backoffLimit: 30
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: wait
          image: bitnami/kubectl:1.29
          command:
            - sh
            - -c
            - |
              echo "Waiting for ExternalSecret orders-secret..."
              until kubectl get secret orders-secret -n orders -o name >/dev/null 2>&1; do
                echo "Secret not found, retrying in 10s..."
                sleep 10
              done
              echo "Secret ready!"
```

**Pattern 3 — Smoke Test + Notification (PostSync Hook):**

```yaml
# post-sync-smoke-test.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-smoke-test
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: test
          image: curlimages/curl:8.5
          command:
            - sh
            - -c
            - |
              ENDPOINT="http://orders-api.orders:80/healthz"
              HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" $ENDPOINT)
              if [ "$HTTP_CODE" = "200" ]; then
                echo "Health check PASS"
                exit 0
              else
                echo "Health check FAIL (HTTP $HTTP_CODE)"
                exit 1
              fi
```

### 4.3 Trade-off: Hook vs Init Container vs Job thuong

| Tieu chi | PreSync Hook | Init Container | Job thuong |
|----------|-------------|----------------|------------|
| Chay khi | Sync phase | Moi pod startup | Moi lan apply |
| Idempotent | Phai tu implement | Kho hon (chay nhieu lan) | Phu thuoc logic |
| Co exit code | Co | Khong (chay trong pod) | Co |
| Retry | ArgoCD retry | Pod restart | Manual hoac backoffLimit |
| Debug | `kubectl logs job/` | `kubectl logs pod/` | `kubectl logs job/` |
| Permission | SA cua Application | SA cua Pod | SA cua namespace |
| Owner | ArgoCD | Pod | kubectl |

**Init container cho migration — tan duong:**

```yaml
# Chay migration trong init container — VAN CAN HOOK
# Ly do: init container chi chay 1 lan khi pod tao
# Neu pod bi kill + restart, migration chay lai -> OK
# Nhung: khong trigger duoc notification, khong block sync
# Nen: dung PreSync Hook cho migration, init container chi la backup
```

### 4.4 Pitfalls Day 25-26

| # | Pitfall | Hau qua | Phong ngua |
|---|---------|---------|------------|
| 1 | Migration Job khong idempotent | Re-sync lan 2 -> fail -> stuck | ON CONFLICT DO NOTHING |
| 2 | Hook Job bi stuck Pending | Block toan bo sync | Timeout + backoffLimit |
| 3 | Mutable image tag | Migration chay image khong dung release | Pin immutable tag + registry immutability |
| 4 | BeforeHookCreation + fast re-sync | Name collision khi 2 sync gan nhau | HookSucceeded policy |
| 5 | SyncFail khong chay | Reconciler restart chua kip goi | Retry manually |
| 6 | PostSync khong chay khi Sync fail | Chi chay neu Sync thanh cong | Khong co cach |
| 7 | Wave so am + string | "−10" (unicode minus) != -10 | Dung int, khong dung unicode |
| 8 | CRD qua lon (2 phut install) | CR apply truoc CRD ready | Wave separation + wait hook |
| 9 | Hook chay voi SA cua Application | Khong co quyen can thiet | RBAC cho migration SA |
| 10 | Secret hard-code trong hook env | Secret leak | External Secret + volume mount |

### 4.5 Performance & Security

**Performance:**
- Moi wave = 1 round trip den API server
- 5 waves = 5 round trips
- Khuyen cao: max 5-7 waves, khong nen co hon 10 waves
- Sync time tang tuyen tinh voi so waves

**Security:**
- Hook Job chay voi ServiceAccount cua Application (trong `spec.destination.serviceAccount`)
- Neu khong set -> chay voi default SA cua namespace
- **Minimum RBAC:** Migration SA chi can `create/get/patch` Job, `get` Secret
- Khong bao gio hard-code secret value trong hook env
- Dung `imagePullSecrets` neu registry la private

### 4.6 Best Practice theo Context

| Context | Approach |
|---------|----------|
| Ca nhan / side project | 1 Application, wave -10 (secret), wave 0 (app), PreSync migration |
| Startup < 5 service | PreSync Hook migration, 2 waves |
| Team 5-15 service | App-of-Apps + hook migration per app, sync wave for ESO/CRD |
| Enterprise 15+ service | Dedicated migration Application + wait-for hook + Argo Rollouts (Day 26) |
| Compliance / audit | PreSync migration + PostSync smoke test + SyncFail notification + SIEM webhook |

---

## 5. Hands-on Lab — 60 phut

**Prerequisites:**
- ArgoCD installed (Day 17)
- Cluster: kind / minikube / EKS
- Git repo: `acme/platform-repo` (Day 20) hoac bare repo local
- kubectl configured

**Mode:** GitHub real repo (recommend) hoac local bare repo

---

### Step 1: Tao namespace demo `demo-orders` (wave -1)

```bash
cd platform-repo

mkdir -p services/orders-app/base
```

**File: `services/orders-app/base/000-namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: demo-orders
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
```

---

### Step 2: DB credentials Secret (wave -10)

**File: `services/orders-app/base/010-db-secret.yaml`**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: orders-db-creds
  namespace: demo-orders
  annotations:
    argocd.argoproj.io/sync-wave: "-10"
type: Opaque
stringData:
  # Chi dung cho lab. Production: dung ESO (Day 25)
  username: "orders_user"
  password: "orders_pass"
  url: "jdbc:postgresql://orders-db:5432/orders"
```

---

### Step 3: PreSync Migration Hook Job (wave 0, PreSync)

**File: `services/orders-app/base/020-migration-job.yaml`**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-db-migration
  namespace: demo-orders
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  ttlSecondsAfterFinished: 600
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: postgres:16-client
          command:
            - sh
            - -c
            - |
              echo "Running DB migration..."
              # Idempotent migration bang raw SQL
              PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d orders <<'SQL'
              CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
              );
              INSERT INTO orders (product_id, quantity, status)
                VALUES ('DEMO', 1, 'pending')
                ON CONFLICT DO NOTHING;
              SELECT 'Migration OK' AS result;
SQL
              echo "Migration completed"
          env:
            - name: DB_HOST
              value: "orders-db"
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: orders-db-creds
                  key: username
            - name: DB_PASS
              valueFrom:
                secretKeyRef:
                  name: orders-db-creds
                  key: password
```

---

### Step 4: Deployment + Service (Sync phase, wave 0)

**File: `services/orders-app/base/030-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  namespace: demo-orders
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orders-api
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
        - name: orders-api
          # Demo image nhanh
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: orders-db-creds
                  key: url
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
```

**File: `services/orders-app/base/040-service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-api
  namespace: demo-orders
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: orders-api
```

---

### Step 5: PostSync Smoke Test Hook (wave 0, PostSync)

**File: `services/orders-app/base/050-smoke-test.yaml`**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-smoke-test
  namespace: demo-orders
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: smoke
          image: curlimages/curl:8.5
          command:
            - sh
            - -c
            - |
              ENDPOINT="http://orders-api.demo-orders:80/"
              echo "Testing $ENDPOINT ..."
              HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" $ENDPOINT || echo "000")
              echo "HTTP code: $HTTP_CODE"
              if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "404" ]; then
                echo "Smoke test PASS (nginx returned HTTP $HTTP_CODE)"
                exit 0
              fi
              echo "Smoke test FAIL"
              exit 1
```

---

### Step 6: Kustomization file

**File: `services/orders-app/base/kustomization.yaml`**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - 000-namespace.yaml
  - 010-db-secret.yaml
  - 020-migration-job.yaml
  - 030-deployment.yaml
  - 040-service.yaml
  - 050-smoke-test.yaml

namespace: demo-orders
```

---

### Step 7: Commit + ArgoCD Application + Sync

```bash
# Commit
git add services/orders-app/
git commit -m "day-24: orders app with sync waves and hooks"
git push

# Tao ArgoCD Application
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: orders-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USER/platform-repo.git
    targetRevision: main
    path: services/orders-app/base
  destination:
    server: https://kubernetes.default.svc
    namespace: demo-orders
  syncPolicy:
    automated: {}
    syncOptions:
      - CreateNamespace=true
EOF

# Sync va quan sat
argocd app sync orders-app --watch
```

---

### Step 8: Quan sat ArgoCD UI — 3 pha chay dung thu tu

```
ArgoCD UI -> orders-app -> Timeline:
  [PreSync]  orders-db-migration (Job) -> Succeeded  [0:05s]
  [Sync]     Namespace + Secret + Deployment + Service -> Succeeded  [0:15s]
  [PostSync] orders-smoke-test (Job) -> Succeeded  [0:22s]

Total sync time: ~25s
```

**Verify logs:**

```bash
# Check migration ran
kubectl logs job/orders-db-migration -n demo-orders

# Check smoke test ran
kubectl logs job/orders-smoke-test -n demo-orders

# Check Deployment da tao
kubectl get deployment -n demo-orders
# EXPECTED: orders-api 2/2 Ready
```

---

### Step 9: Failure Scenario 1 — Migration Job exit 1

```bash
# Tao migration loi (exit 1)
cat > services/orders-app/base/020-migration-job.yaml <<'YAML'
apiVersion: batch/v1
kind: Job
metadata:
  name: orders-db-migration
  namespace: demo-orders
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: alpine:3.19
          command: ["sh", "-c", "echo 'FAILING MIGRATION'; exit 1"]
YAML

git add services/orders-app/base/020-migration-job.yaml
git commit -m "day-24: failing migration for test"
git push

# Sync
argocd app sync orders-app
```

**Quan sat:**
```
PreSync: orders-db-migration -> Failed (exit 1)
Sync phase: KHONG CHAY (blocked by PreSync failure)
Sync status: Failed
SyncFail hook: (chay neu co)
```

**Verify:**

```bash
argocd app get orders-app
# EXPECTED: Sync Status = Failed

kubectl describe job orders-db-migration -n demo-orders
# EXPECTED: Exit code 1, BackoffLimit reached
```

---

### Step 10: Recovery — Fix migration + re-sync

```bash
# Restore migration toi
git checkout HEAD~1 -- services/orders-app/base/020-migration-job.yaml
git add services/orders-app/base/020-migration-job.yaml
git commit -m "day-24: restore migration job"
git push

argocd app sync orders-app --watch
```

---

### Step 11: Failure Scenario 2 — imagePullBackOff

```bash
# Tao Deployment loi image
cat > services/orders-app/base/030-deployment.yaml <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  namespace: demo-orders
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orders-api
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
        - name: orders-api
          image: nginx:nonexistent-tag-xyz
          ports:
            - containerPort: 80
YAML

git add services/orders-app/base/030-deployment.yaml
git commit -m "day-24: bad image for test"
git push

argocd app sync orders-app
```

**Quan sat:**
```
PreSync: OK
Sync phase: Deployment ImagePullBackOff
Sync status: Failed
SyncFail hook: (chay neu co config)
```

**Debug:**

```bash
kubectl describe pod -n demo-orders -l app=orders-api
# EXPECTED: ErrImagePull or ImagePullBackOff

# Check SyncFail hook chay chua (neu co)
kubectl get job -n demo-orders
```

---

### Step 12: Idempotency Test — Re-sync nhieu lan

```bash
# Sync 3 lan lien tiep
for i in 1 2 3; do
  echo "=== Sync lan $i ==="
  argocd app sync orders-app
  sleep 5
  kubectl get job -n demo-orders
done
```

**Expected:** Moi lan sync, ArgoCD xoa Job cu (`BeforeHookCreation`), tao Job moi.
Khong co loi `duplicate key` hay `schema already exists`.

---

### Step 13: CRD Ordering Test

```bash
# Tao CRD + CR trong cung Application
mkdir -p services/crd-demo/base

cat > services/crd-demo/base/000-crd.yaml <<'YAML'
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: demos.example.com
  annotations:
    argocd.argoproj.io/sync-wave: "-5"
spec:
  group: example.com
  names:
    kind: Demo
    plural: demos
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
YAML

cat > services/crd-demo/base/010-cr.yaml <<'YAML'
apiVersion: example.com/v1
kind: Demo
metadata:
  name: my-demo
  namespace: default
  annotations:
    argocd.argoproj.io/sync-wave: "10"
spec:
  message: "Hello from CR"
YAML
```

**Apply va verify:**
```bash
argocd app create crd-demo \
  --repo https://github.com/YOUR_USER/platform-repo.git \
  --path services/crd-demo/base \
  --dest-server https://kubernetes.default.svc

argocd app sync crd-demo
# EXPECTED: CRD apply truoc, CR apply sau (khong loi)
```

---

### Step 14: Cleanup

```bash
# Xoa Applications
argocd app delete orders-app --cascade
argocd app delete crd-demo --cascade

# Verify resources da xoa
kubectl get all -n demo-orders
kubectl get crd | grep demo

# Neu co finalizer, xoa thu cong
kubectl delete namespace demo-orders --grace-period=0
kubectl delete crd demos.example.com
```

---

**Troubleshooting thuong gap:**

| Van de | Nguyen nhan | Fix |
|--------|-------------|-----|
| PreSync Job Pending rat lau | Image pull fail hoac RBAC | `kubectl describe job`, `kubectl logs job` |
| Sync phase khong chay sau PreSync fail | PreSync exit != 0 | Fix PreSync roi sync lai |
| Job tao nhung khong chay | `restartPolicy: Never` (sai) | Doi thanh `restartPolicy: OnFailure` |
| HookSucceeded nhung Job van ton tai | `ttlSecondsAfterFinished` chua expire | Doi thanh `HookSucceeded` deletion policy |
| SyncFail khong chay | Reconciler chua kip | Retry sync thu cong |
| CR apply fail khi CRD chua ready | Wave khong du | Them wait-for hook hoac wave separation |

---

## 6. Kiem tra hieu bai

**Cau 1:** Khi nao dung sync wave? Khi nao dung hook?

> **Dap an:** Sync wave dung de ordering giua cac resource declarative (CRD, CR, Secret, Deployment). Hook dung de chay task transient co exit code (migration, smoke test, notification). Dac biet: DB migration = PreSync hook; CRD ordering = sync wave.

**Cau 2:** PreSync Job bi stuck o trang thai Pending 2 gio. Lien he root cause nao co the xay ra?

> **Debug checklist:** (1) Image pull fail -> check `kubectl describe job` co `ErrImageNotFound`; (2) RBAC — SA khong co quyen -> check `kubectl auth can-i`; (3) Node selector khong match -> check pod scheduling; (4) PVC pending -> check storage class; (5) Webhook blocking pod creation -> check `kubectl get events --field-selector involvedObject.name=<pod>`

**Cau 3:** Migration script khong idempotent — re-run lan 2 fail voi "table already exists". Lam sao refactor?

> **Approach:** (1) Dung Flyway/Liquibase (tu dong idempotent); (2) Neu raw SQL, them `CREATE TABLE IF NOT EXISTS`; (3) Neu co `id` column, dung `ON CONFLICT DO NOTHING`; (4) Neu khong the doi migration script, them logic check trong entrypoint: `SELECT 1 FROM schema_version WHERE version='001'` -> co thi exit 0.

**Cau 4:** Migration chay trong init container hien tai (app team dang dung). Muc tieu chuyen sang ArgoCD hook. Co trade-off gi?

> **Trade-off analysis:**
> - Init container: chay trong pod, chay lai neu pod restart, khong block ArgoCD sync
> - ArgoCD hook: chay trong sync phase, co exit code, co the block sync, nhung co notification + SyncFail
> - Re nhanh: Dung ca 2 — hook PreSync cho sync blocking, init container cho redundancy

**Cau 5:** 30 services deu can migration. Co the spin-up 30 PreSync hook cung luc? Co van de gi?

> **Design:** (1) Tan de: 30 migration cung luc -> database lock neu cung 1 DB; (2) Giai phap A: sequential sync wave (service A wave -5, service B wave -4 ...) — phuc tap; (3) Giai phap B: 1 shared migration Application chay truoc, cac app khac co PreSync wait hook; (4) Giai phap C: Helm hook (pre-install) trong shared DB chart — khuyen khich

---

## 7. Tom tat cuoi ngay

**Kien thuc da hoc:**

- **Sync phase model:** PreSync -> Sync -> PostSync (+ SyncFail)
- **Sync wave:** annotation `argocd.argoproj.io/sync-wave: "<int>"`, ordering trong 1 phase
- **Hook:** transient resource chay theo phase, Job la pho bien nhat
- **Hook deletion policy:** `HookSucceeded` (recommended), `HookFailed`, `BeforeHookCreation`
- **Idempotency:** bat buoc voi Hook Job — `CREATE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`
- **CRD ordering:** built-in heuristic nhung co edge case, dung wave hoac wait hook
- **Pitfalls:** non-idempotent migration, imagePullBackOff, name collision, wave number

**Chuan bi cho Day 25:**
Day 25 = External Secrets Operator (ESO). Day 24 la preparation: ESO CRD (wave -10) -> SecretStore (wave -5) -> ExternalSecret (wave 0) -> app dung secret (wave 10). Day 26 = Argo Rollouts — Rollout CRD (wave -10) -> Rollout resource (wave 0).

---

## 8. Tham khao

- [ArgoCD Sync Waves & Hooks](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
- [ArgoCD Resource Hooks](https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/)
- [Flyway — Idempotent Migrations](https://documentation.red-gate.com/flyway)
- [Liquibase — Change Types](https://www.liquibase.com/get-started/change-types)
