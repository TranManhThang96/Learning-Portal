# Day 24 — Sync Waves, Hooks, Dependencies — Reference Document

---

## 1. Sync Wave + Hook Cheat Sheet

### 1.1 Annotations Quick Reference

```yaml
# Ordering: sync wave (integer, mac dinh = 0)
argocd.argoproj.io/sync-wave: "-10"   # chay truoc wave 0

# Phase: hook type
argocd.argoproj.io/hook: PreSync     # chay truoc Sync phase
argocd.argoproj.io/hook: Sync         # chay cung Sync phase (default)
argocd.argoproj.io/hook: PostSync    # chay sau Sync thanh cong
argocd.argoproj.io/hook: SyncFail    # chay khi Sync fail
argocd.argoproj.io/hook: Skip        # bo qua apply manifest
argocd.argoproj.io/hook: PreDelete    # chay truoc khi delete
argocd.argoproj.io/hook: PostDelete   # chay sau khi delete

# Cleanup: hook deletion policy
argocd.argoproj.io/hook-delete-policy: HookSucceeded       # xoa khi thanh cong
argocd.argoproj.io/hook-delete-policy: HookFailed         # xoa khi that bai
argocd.argoproj.io/hook-delete-policy: BeforeHookCreation # xoa truoc khi tao moi (default)
```

### 1.2 Phase + Wave Timeline Diagram

```
                    Sync Operation
========================|===========================
  PreSync   |   Sync phase    |   PostSync
------------|-----------------|--------------
 wave -10   |  wave -10       |  wave -10
 Secret     |  CRD            |  Notification
 wave -5    |  Operator       |  Cleanup
 CRD        |  wave 0         |
 wave 0     |  Deployment     |  wave 0
 Deployment |  Service        |  Smoke test
 (no hook)  |  wave 10        |
             |  CR             |
             |  --- SyncFail ---|
             |  Cleanup/Alert
=============|=================|===============
             | SyncFail        |
             | (khi Sync fail) |
             |=================|
```

### 1.3 Common Patterns

```yaml
# Pattern 1: DB Migration (PreSync + HookSucceeded)
annotations:
  argocd.argoproj.io/hook: PreSync
  argocd.argoproj.io/hook-delete-policy: HookSucceeded

# Pattern 2: Wait for CRD Ready (PreSync + polling)
annotations:
  argocd.argoproj.io/hook: PreSync
  argocd.argoproj.io/hook-delete-policy: HookSucceeded
# Dung kubectl wait: kubectl wait --for=condition=established crd/<name>

# Pattern 3: Smoke Test (PostSync + HookSucceeded)
annotations:
  argocd.argoproj.io/hook: PostSync
  argocd.argoproj.io/hook-delete-policy: HookSucceeded

# Pattern 4: Failure Alert (SyncFail + HookFailed)
annotations:
  argocd.argoproj.io/hook: SyncFail
  argocd.argoproj.io/hook-delete-policy: HookFailed

# Pattern 5: Backup on Delete (PreDelete)
annotations:
  argocd.argoproj.io/hook: PreDelete
  argocd.argoproj.io/hook-delete-policy: HookSucceeded
```

---

## 2. Bootstrap Order Recipe cho Platform Stack

### 2.1 Day 25 Context: ESO (External Secrets Operator)

```yaml
# Wave -10: ESO CRD (truoc)
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: externalsecrets.external-secrets.io
  annotations:
    argocd.argoproj.io/sync-wave: "-10"

# Wave -5: ESO Helm chart operator Deployment
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-secrets
  annotations:
    argocd.argoproj.io/sync-wave: "-5"
spec:
  source:
    chart: external-secrets
    # ...

# Wave 0: SecretStore CR
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend
  annotations:
    argocd.argoproj.io/sync-wave: "0"

# Wave 5: ExternalSecret CR
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: orders-secrets
  annotations:
    argocd.argoproj.io/sync-wave: "5"

# Wave 10: App (su dung secret)
# Deployment/StatefulSet — mac dinh wave 0 nhung apply sau ExternalSecret
```

### 2.2 Day 26 Context: Argo Rollouts

```yaml
# Wave -10: Argo Rollouts CRD
# Wave -5: Rollouts controller Deployment
# Wave 0: Rollout resource (thay Deployment)
```

### 2.3 Full Platform Bootstrap Order

| Wave | Component | Resource type | Ly do |
|------|-----------|--------------|-------|
| -20 | Namespace (platform-wide) | Namespace | Tao namespace truoc |
| -15 | CRD (cert-manager) | CRD | CRD install mat thoi gian |
| -10 | CRD (ESO, kyverno) | CRD | CRD nho hon |
| -5 | Operator Deployment (cert-manager) | Deployment | Operator tao CRD instance |
| -5 | Operator Deployment (ESO) | Deployment | |
| -5 | Operator Deployment (kyverno) | Deployment | |
| 0 | CR (ClusterIssuer, SecretStore, ClusterPolicy) | CR | Dac ta nguon |
| 5 | Ingress controller | Deployment/Service | Ingress class |
| 10 | Certificate CR | Certificate | Dinh nghia cert |
| 15 | ExternalSecret | ExternalSecret | Secret cho app |
| 20 | App Deployment | Deployment | App cuoi cung |

---

## 3. Idempotent Migration Playbook

### 3.1 Flyway (recommended)

```bash
# Flyway tu dong kiem tra bang schema_version
# File: migrations/V1__create_orders.sql
CREATE TABLE IF NOT EXISTS orders (
  id SERIAL PRIMARY KEY,
  product_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  status TEXT DEFAULT 'pending'
);

# File: migrations/V2__add_indexes.sql
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
```

### 3.2 Liquibase

```xml
<changeSet id="001" author="acme">
  <createTable tableName="orders">
    <column name="id" type="int" autoIncrement="true">
      <constraints primaryKey="true"/>
    </column>
    <column name="product_id" type="text"/>
  </createTable>
  <!-- runAlways: false, runOnChange: false = idempotent -->
</changeSet>
```

### 3.3 Raw SQL (neu khong dung migration tool)

```sql
-- Tao bang (idempotent)
CREATE TABLE IF NOT EXISTS orders (
  id SERIAL PRIMARY KEY,
  product_id TEXT NOT NULL
);

-- Insert (idempotent)
INSERT INTO orders (product_id)
SELECT 'DEMO' WHERE NOT EXISTS (
  SELECT 1 FROM orders WHERE product_id = 'DEMO'
);

-- Them column (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'orders' AND column_name = 'status'
  ) THEN
    ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending';
  END IF;
END $$;

-- Index (idempotent)
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
```

### 3.4 Migration Job Entry Point Check

```bash
#!/bin/sh
# Lam cho raw SQL script idempotent
set -e

MIGRATION_ID="001_create_orders"

# Kiem tra da chay chua
EXIST=$(psql -t -c "SELECT 1 FROM schema_migrations WHERE id='$MIGRATION_ID'")

if [ "$EXIST" = "1" ]; then
  echo "Migration $MIGRATION_ID da duoc apply. Bo qua."
  exit 0
fi

# Chay migration
psql -f /migrations/$MIGRATION_ID.sql

# Danh dau hoan thanh
psql -c "INSERT INTO schema_migrations (id) VALUES ('$MIGRATION_ID') ON CONFLICT DO NOTHING"

echo "Migration $MIGRATION_ID completed"
```

---

## 4. Hook Deletion Policy Decision Tree

```
Hook Job finished (PreSync/Sync/PostSync)
         |
         v
    Exit code?
    /         \
   0            != 0
    \            /
     v          v
  HookSucceeded?  HookFailed?
     |              |
    Yes             Yes
     |              |
     v              v
  Xoa Job      Xoa Job
     |
     v
  ttlSecondsAfterFinished?
     |
    Yes -> Job bi delete sau N giay
     |
    No -> Xoa ngay lap tuc
```

**Recommendation:**

| Use case | Policy |
|----------|--------|
| Migration | `HookSucceeded` (xoa sau khi thanh cong) |
| Smoke test | `HookSucceeded` |
| Wait-for hook | `HookSucceeded` |
| SyncFail alert | `HookFailed` (xoa chi khi fail) |
| PreDelete backup | `HookSucceeded` |
| Cleanup | `HookSucceeded,HookFailed` |

---

## 5. Anti-Patterns Checklist (15 items)

- [ ] Migration script khong idempotent (re-run se fail)
- [ ] PreSync Job co `restartPolicy: Never` (Job se khong bao gio retry)
- [ ] Hook Job su dung `imagePullPolicy: IfNotPresent` (image cu khong cap nhat)
- [ ] Secret value hard-code trong hook env (khong dung ESO)
- [ ] `argocd.argoproj.io/sync-wave` la string "−10" (unicode minus) thay vi int -10
- [ ] Wave gap qua lon (VD: wave 0 nhanh, wave 100 cham) -> ordering khong ro rang
- [ ] PostSync chay khi Sync fail (PostSync chi chay khi Sync thanh cong)
- [ ] SyncFail khong co Job nhung van expect notification
- [ ] 30 PreSync hook chay dong thoi -> database lock
- [ ] Hook Job chay voi default SA, khong co RBAC can thiet
- [ ] Khong co `ttlSecondsAfterFinished` -> Job ton tai vo thoi han
- [ ] `BeforeHookCreation` + fast re-sync -> Job cu chua xoa, Job moi tao trung name
- [ ] CRD qua lon (2 phut) nhung CR cung wave -> CR apply khi CRD chua ready
- [ ] Khong debug hook -> Apply roi khong hieu tai sao fail
- [ ] Dung hook cho task declarative thay vi sync wave (Job tao Deployment thay vi apply)

---

## 6. Common Errors Reference

| Error | Symptom | Cause | Fix |
|-------|---------|-------|-----|
| `customresourcedefinition not found` | CR apply fail | CRD chua install | Them wave separation (CRD wave -5, CR wave 10) |
| `Job already exists` | Hook tao that bai | `HookSucceeded` nhung Job chua xoa | Dung `BeforeHookCreation` |
| `ErrImageNotFound` | PreSync Job Pending | Image sai hoac pull fail | Verify image tag, registry path, and `imagePullSecrets` |
| `ImagePullBackOff` | Sync stuck | Private registry khong co secret | Them `imagePullSecrets` |
| `hook pod terminated: ExitCode: 1` | PreSync fail, sync stopped | Migration script exit != 0 | Fix script, test local |
| `context deadline exceeded` | Sync timeout | Job chay qua 5 phut | Tang `activeDeadlineSeconds` |
| `namespace not found` | Create resource fail | Namespace chua tao | Them wave -20 Namespace, dung `CreateNamespace=true` |
| `failed to acquire lease` | ArgoCD HA conflict | Nhieu ArgoCD instance | Dung shard assignment |
| `rendered manifest contain duplicate resource` | Kustomize build fail | Resource trung trong kustomization | Loai bo resource trung |
| `Job has reached maximum backoff limit` | Job fail nhieu lan | Migration error, retry limit | Fix root cause |

---

## 7. Helm Hook vs ArgoCD Hook Reference

### 7.1 Helm Hook Annotations

```yaml
# Helm hook annotations (nam trong chart templates)
metadata:
  annotations:
    # Hook types (co the khai bao nhieu)
    helm.sh/hook: pre-install,pre-upgrade

    # Weight (-10 den 10, default 0)
    helm.sh/hook-weight: "-5"

    # Delete policy
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
```

### 7.2 ArgoCD Hook Annotations

```yaml
# ArgoCD hook annotations (nam trong rendered manifest)
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
```

### 7.3 So sanh chi tiet

| Tieu chi | Helm hook | ArgoCD hook |
|----------|-----------|-------------|
| Scope | 1 Helm release | 1 ArgoCD Application |
| Trigger | `helm install/upgrade/rollback` | `argocd app sync` |
| Hook types | pre-install, post-install, pre-upgrade, post-upgrade, pre-rollback, post-rollback, test, crd-install | PreSync, Sync, PostSync, SyncFail, Skip, PreDelete, PostDelete |
| Weight ordering | `helm.sh/hook-weight` | Sync wave number |
| CRD handling | `crd-install` (CRD-safe) | Built-in CRD ordering |
| RBAC | Helm tiller (deprecated) / OCI | ArgoCD SA + RBAC |
| Retry | Khong co built-in | Retry khi fail (PreSync/Sync) |
| Sync wave | Khong co | Co (annotation tren resource) |

### 7.4 Neu dung ca 2 (Helm chart qua ArgoCD)

```yaml
# Trong Helm chart: dung Helm hook
# Trong ArgoCD Application: dung ArgoCD sync wave + hook

# Vi du: cert-manager qua ArgoCD + Helm
# Helm chart da co helm.sh/hook: pre-install,pre-upgrade cho CRD
# ArgoCD: sync wave -10 cho CRD Helm chart
# ArgoCD: sync wave 0 cho CR (Certificate)

# Best practice: 1 trong 2, khong dung ca 2 cho cung 1 task
# Recommendation: Dung ArgoCD hook vi co sync wave
```

---

## 8. Debug Quick Reference

```bash
# 1. Xem Application sync status + events
argocd app get orders-app
argocd app get orders-app --watch

# 2. Xem Application events
kubectl get events -n argocd --field-selector involvedObject.name=orders-app --sort-by='.lastTimestamp'

# 3. Xem hook Jobs
kubectl get jobs -n demo-orders --show-labels

# 4. Logs cua hook Job
kubectl logs job/orders-db-migration -n demo-orders
kubectl logs job/orders-smoke-test -n demo-orders

# 5. Pod logs (neu Job tao pod)
kubectl get pods -n demo-orders
kubectl logs <pod-name> -n demo-orders

# 6. Xem resource ordering trong ArgoCD
argocd app resources orders-app

# 7. Xem revision history
argocd app revision history orders-app

# 8. Manual trigger PreSync hook (test)
# PreSync hook chay tu dong khi sync, khong the goi truc tiep
# Test local: kubectl create job test-hook --image=<image> ...

# 9. SyncFail hook da chay chua?
kubectl get jobs -n demo-orders -l argocd.argoproj.io/hook-type=SyncFail

# 10. Sync wave ordering
kubectl get all -n demo-orders -o json \
  | jq '.items[] | select(.metadata.annotations["argocd.argoproj.io/sync-wave"] != null) | {name:.metadata.name, wave:.metadata.annotations["argocd.argoproj.io/sync-wave"]}' \
  | jq -s sort_by(.wave)
```
