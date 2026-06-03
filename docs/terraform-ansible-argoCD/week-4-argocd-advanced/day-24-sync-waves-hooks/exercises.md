# Day 24 — Exercises: Sync Waves, Hooks, Dependencies

**Muc tieu:** Thuc hanh 6 challenges tu production scenarios.
**Thoi gian:** 90-120 phut
**Mode:** Git repo (hoac local bare repo)

---

## Exercise 1: Bootstrap Order Design (30 phut)

**Muc tieu:** Thiet ke sync wave assignment cho 8 platform components.

**Yeu cau:**

Thiet ke file `platform-bootstrap/000-bootstrap-order.md` mo ta wave assignment cho 8 components sau:

1. `cert-manager` (Helm chart: CRD + Deployment + ClusterIssuer)
2. `ingress-nginx` (Helm chart: CRD + Deployment + IngressClass)
3. `external-secrets` (Helm chart: CRD + Deployment + ClusterSecretStore)
4. `sealed-secrets` (Helm chart: CRD + Deployment + SealedSecret)
5. `prometheus-stack` (Helm chart: CRD + Deployment + PrometheusRule)
6. `loki` (Helm chart: CRD + Deployment + ConfigMap)
7. `argo-rollouts` (Helm chart: CRD + Deployment + Rollout)
8. `kyverno` (Helm chart: CRD + Deployment + ClusterPolicy)

**Constraints:**
- CRD phai apply truoc operator (CRD wave < operator wave)
- Certificate/Issuer/ExternalSecret phai sau operator
- App Ingress phai sau IngressClass
- Dung 5 waves: -20, -10, 0, 10, 20
- Ghi ro ly do cho moi assignment

**Deliverable:**

```markdown
# Platform Bootstrap Order

| Wave | Component | Resource | Rationale |
|------|-----------|---------|-----------|
| -20  | ...       | ...     | ...       |
| ...  | ...       | ...     | ...       |
```

**Diem xu ly:**
- [ ] CRD va operator cung chart: tach thanh 2 Application hoac dung wave trong cung 1 chart
- [ ] ESO + Vault/ASM SecretStore: SecretStore sau ESO operator
- [ ] Argo Rollouts CRD truoc Rollout resource
- [ ] Certificate: sau cert-manager operator nhung truoc Ingress

---

## Exercise 2: Long-Running Migration Design (25 phut)

**Scenario:** Team co DB migration chay 15 phut (phan tich du lieu lon, rebuild index).

**Yeu cau:** Thiet ke hook configuration + monitoring + timeout cho truong hop nay.

### 2a. Hook Configuration (10 phut)

Viet file `orders-app/020-migration-job.yaml` voi:

```yaml
# PLACEHOLDER: Hoan thien hook configuration
# Yeu cau:
# - Hook type: PreSync
# - Deletion policy: ?
# - Timeout: 20 phut (de con du 5 phut buffer)
# - Retry: 1 lan (backoffLimit: 1)
# - Image: postgres:16-client (co san)
# - Command: chay migration 15 phut
# - Idempotent: co (dung Flyway hoac IF NOT EXISTS)
```

### 2b. Monitoring Integration (10 phut)

Them notification vao migration hook:

```yaml
# PLACEHOLDER:
# - Truoc khi chay: notify Slack "Migration starting"
# - Sau khi thanh cong: notify "Migration OK (15 phut)"
# - Neu fail: notify "Migration FAILED" + SyncFail hook
# - Dung curl -> Slack webhook
```

### 2c. Timeout & Backoff Analysis (5 phut)

Tra loi cac cau hoi:

1. Neu `activeDeadlineSeconds: 1200` (20 phut) nhung migration chay 25 phut — ArgoCD co hanh vi gi?
2. Neu `backoffLimit: 1` va migration fail lan 1 — co chay lan 2 khong? Tai sao?
3. Neu dung `restartPolicy: Never`, Job co retry khong?

---

## Exercise 3: Debug — Application Stuck Progressing (20 phut)

**Scenario:** Application `payment-app` bi stuck o trang thai `Progressing` 2 gio. SyncFail hook khong chay.

**Logs tra ve:**

```
$ argocd app get payment-app
Name: payment-app
Sync Status:   Progressing
Health Status: Progressing
Last Synced:   2024-01-15 10:00:00 +0700

$ kubectl get jobs -n payment
NAME                    COMPLETIONS   DURATION   AGE
payment-db-migration    0/1           119m       2h

$ kubectl describe job payment-db-migration -n payment
# ... Events ...
  Type     Reason            Age   From            Message
  ----     ------            ----  ----            -------
  Warning  BackOffLimit      119m  job-controller  Job has
  exceeded backoff limit

$ kubectl logs job/payment-db-migration -n payment
Error: could not connect to database: connection refused
```

**Yeu cau:**

### 3a. Root Cause Analysis (10 phut)

Tra loi:

1. Root cause chinh la gi?
2. Tai sao SyncFail hook khong chay?
3. Tai sao Application bi stuck Progressing 2 gio thay vi Failed?

### 3b. Fix Plan (10 phut)

Viet cac buoc fix:

```
1. [IMMEDIATE] Xoa Job hien tai de unblock sync
2. [SHORT-TERM] Fix database connection
3. [MEDIUM-TERM] Thay doi hook configuration
4. [LONG-TERM] Them PreSync wait hook cho database ready
```

Viet command cu the:

```bash
# PLACEHOLDER: cac command can thiet
```

---

## Exercise 4: Refactor — Init Container Migration -> ArgoCD Hook (20 phut)

**Current state:**

Team hien tai dung init container trong Deployment de chay DB migration:

```yaml
# CURRENT: app deployment voi init container migration
spec:
  initContainers:
    - name: db-migrate
      image: orders/migrate:1.0.0
      command: ["flyway", "migrate"]
      env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: orders-db-creds
              key: url
  containers:
    - name: orders-api
      image: orders/api:v1.2.0
```

**Yeu cau:**

Chuyen migration sang ArgoCD PreSync hook, giu init container lam backup defense-in-depth.

### 4a. Tao Hook Job (10 phut)

Viet file `services/orders-app/base/020-migration-job.yaml`:

```yaml
# PLACEHOLDER:
# Hook PreSync, HookSucceeded
# Dung flyway/flyway:10.8
# Idempotent (Flyway tu dong handle)
# RestartPolicy: OnFailure
# ServiceAccount: orders-migration-sa
```

### 4b. Thiet ke ServiceAccount + RBAC (5 phut)

Viet file `services/orders-app/base/015-migration-sa.yaml`:

```yaml
# PLACEHOLDER:
# ServiceAccount: orders-migration-sa
# Role: chi quyen can thiet
# - get/list Secret (doc db credentials)
# - create/get/patch Job (ArgoCD can)
# - get Namespace (optional)
```

### 4c. Giai thich Trade-off (5 phut)

Tra loi: Khi nao init container van can thiet dù da co hook?

---

## Exercise 5: Disaster Recovery — Non-Idempotent Migration (25 phut)

**Scenario:** Mot thanh vien nhom da deploy migration script khong idempotent, gap loi nhu sau:

```
$ kubectl logs job/orders-db-migration -n orders
Error: relation "orders" already exists
FATAL: terminating connection
```

Sau do ho ta commit fix, nhung database da o trang thai partial state:
- Bang `orders` da tao
- Mot so `orders` data da insert (từ retry 1)
- Bang `order_items` chua tao (vi migration fail truoc do)

**Yeu cau:**

### 5a. Emergency Response Checklist (10 phut)

Viet checklist theo thu tu:

```
[ ] B1: ...
[ ] B2: ...
```

### 5b. Recovery SQL Script (10 phut)

Viet script `scripts/emergency-recovery.sql`:

```sql
-- PLACEHOLDER:
-- 1. Kiem tra trang thai hien tai (cac bang, data)
-- 2. Quyet dinh: rollback hay forward (fix migration)
-- 3. Rollback: DROP TABLE (neu data khong quan trong)
-- 4. Forward: ALTER TABLE IF NOT EXISTS, INSERT ON CONFLICT
-- 5. Danh dau migration da fix
```

### 5c. Post-Incident Fix (5 phut)

Thiet ke quy trinh dam bao migration script tu nay ve sau deu idempotent:

```
Step 1: ...
Step 2: ...
Step 3: CI check: ...
```

---

## Exercise 6 (Bonus): Cross-Application Dependency (30 phut)

**Scenario:** Application `audit-service` can deploy SAU KHI `orders-service` da sync thanh cong. ArgoCD khong ho tro cross-Application dependency truc tiep.

### 6a. Problem Analysis (5 phut)

Tai sao ArgoCD khong ho tro cross-Application dependency? Co the gap race condition gi?

### 6b. Design 3 Workarounds (15 phut)

Thiet ke 3 workaround:

**Option A — App-of-Apps + Sync Wave:**

```yaml
# PLACEHOLDER:
# root-app chua ca orders-app va audit-app
# orders: wave 0
# audit: wave 10
# Giai thich: root-app la 1 ArgoCD Application, 2 app con trong cung 1 sync
```

**Option B — ArgoCD ApplicationSet + Selector:**

```yaml
# PLACEHOLDER:
# 2 ApplicationSet: 1 cho orders, 1 cho audit
# Dung annotation trigger:
#   argocd.argoproj.io/application-set: depends-on-orders
# Giai thich: Application B chi tao sau khi Application A healthy
```

**Option C — External Orchestrator:**

```yaml
# PLACEHOLDER:
# Argo Workflow / Tekton Pipeline orchestrator
# Step 1: ArgoCD CLI sync orders-app + wait healthy
# Step 2: ArgoCD CLI sync audit-app
# Giai thich: 1 Workflow thay vi 2 ArgoCD sync
```

### 6c. Recommendation (10 phut)

Tra loi:

1. Khi nao dung Option A? (team size, complexity)
2. Khi nao dung Option B?
3. Khi nao dung Option C?
4. Co ban nen tai nao? Tai sao?

---

## Submission

Clone repo, tao branch `day-24-exercises`, commit cac file da hoan thanh:

```bash
git checkout -b day-24-exercises

# Commit Exercise 1
git add platform-bootstrap/000-bootstrap-order.md
git commit -m "ex1: platform bootstrap order design"

# Commit Exercise 2
git add orders-app/020-migration-job.yaml
git commit -m "ex2: long-running migration hook design"

# ... cac exercise con lai ...

git push -u origin day-24-exercises
```

---

## Rubric

| Criteria | Points |
|----------|--------|
| Exercise 1: Wave assignment co ly do, thu tu dung | /20 |
| Exercise 2: Timeout + backoff + notification | /20 |
| Exercise 3: Root cause dung, fix plan chi tiet | /20 |
| Exercise 4: Hook + RBAC + trade-off analysis | /20 |
| Exercise 5: Recovery checklist + idempotent fix | /15 |
| Exercise 6: 3 options + recommendation | /5 |
| **Total** | **/100** |

**Passing score:** 70/100
