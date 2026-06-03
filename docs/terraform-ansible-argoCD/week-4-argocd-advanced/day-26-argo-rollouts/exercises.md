# Day 26 — Argo Rollouts, Progressive Delivery — Exercises

---

## Challenge 1: Refactor 5 Service Deployment → Rollout

**Muc tieu:** Refactor tat ca Deployment thanh Rollout voi canary strategy nhat quán.

**Scenario:**
Team co 5 microservice tren EKS, hien dang su dung Kubernetes Deployment:
- `api-gateway` (NodePort)
- `auth-service` (ClusterIP)
- `payment-service` (ClusterIP)
- `notification-service` (ClusterIP)
- `orders-api` (ClusterIP)

**Yeu cau:**

1. Thiet ke Rollout manifest cho `payment-service` voi:
   - 5 replicas
   - Canary strategy: 10% -> 30% -> 60% -> 100%
   - Pause sau moi step (manual approval)
   - Prometheus AnalysisTemplate check success-rate >= 99%
   - maxSurge: 25%, maxUnavailable: 0

2. Tao 2 Service (stable + canary) cho payment-service

3. Viet script deploy tat ca 5 service thanh Rollout (batch deploy, khong conflict)

4. Thu ke hoac giai thich: tai sao canary 10% start thay vi 25%?

**Deliverable:** 5 Rollout YAML files trong folder `services/{service}/base/rollout.yaml`

---

## Challenge 2: Thiet ke AnalysisTemplate voi 3 Metric

**Muc tieu:** Viet AnalysisTemplate phuc vu quality gate truoc promotion.

**Scenario:**
Orders service can 3 quality gate:
- **Success rate**: >= 95% (5 phut window)
- **P95 latency**: <= 500ms
- **Error budget**: < 1% errors trong 5 phut

Neu bat ky metric nao fail, rollout bi abort.

**Yeu cau:**

1. Viet AnalysisTemplate `orders-quality-gate` voi:
   - 3 metric (success-rate, p95-latency, error-budget)
   - Prometheus provider cho moi metric
   - `interval`, `count`, `successCondition`, `failureLimit` hop ly
   - 1 `args.service-name`

2. Thiet ke Rollout tich hop AnalysisTemplate:
   - Steps: 20% -> 50% -> 80% -> 100%
   - Analysis chay sau step 1 (20%) voi startingStep
   - Analysis chay sau step 2 (50%)
   - Giai thich: tai sao analysis sau step 1 va 2 nhung khong sau step 3?

3. Bonus: them metric 4 — pod restart count (metric `kube_pod_container_status_restarts`)

**Deliverable:** `analysis-template-3metric.yaml` + `rollout-with-analysis.yaml`

---

## Challenge 3: Debug AnalysisRun Stuck Inconclusive

**Muc tieu:** Debug skill — tim root cause khi AnalysisRun khong chuyen sang pass/fail.

**Scenario:**
```
Rollout: orders-api
Status: Paused at step 2 (50%)
AnalysisRun: orders-api-analysis-<hash>
Status: Inconclusive (30 phut roi)

kubectl argo rollouts analysis get orders-api -n demo-orders
OUTPUT:
  Name:     orders-api-analysis-<hash>
  Status:   Inconclusive
  MetricResults:
    1. success-rate  Inconclusive  ["null"]
```

**Yeu cau:**

1. Viet debug checklist day du (10+ step) de tim root cause Inconclusive
2. Voi moi root cause, ghi fix cu the
3. Kiem tra 3 scenario:
   - Scenario A: Prometheus khong accessible (network policy)
   - Scenario B: Metric query tra null (ten metric sai)
   - Scenario C: `successCondition` tra NaN (P99 query sai)

4. Viet command kiem tra moi scenario (test Prometheus query, check network, check metric name)

**Deliverable:** Debug runbook (Markdown, co command)

---

## Challenge 4: Blue-Green voi Database Schema Migration

**Muc tieu:** Thiet ke blue-green deployment cho app co database schema change.

**Scenario:**
`orders-api` can upgrade tu schema v1 sang v2:
- Schema v2 them column `shipping_address` (backward-compatible: co the null)
- Application code v2 doc column moi
- Neu rollback, column van ton tai (khong xoa)

**Yeu cau:**

1. Thiet ke blue-green Rollout:
   - `activeService: orders-active` (traffic v1)
   - `previewService: orders-preview` (deploy v2)
   - `autoPromotionEnabled: false` (manual)
   - `scaleDownDelaySeconds: 60` (1 phut de test)

2. Thiet ke PreSync Hook:
   - Migration job chay truoc preview deploy
   - Idempotent (neu column da ton tai thi skip)
   - Neu migration fail: preview khong duoc deploy

3. Thiet ke promotion flow:
   - Step 1: Deploy preview (migration hook PreSync)
   - Step 2: Ops team test preview service
   - Step 3: Manual promote → switch traffic
   - Step 4: Scale down v1 sau 60s

4. Thiet ke rollback flow (neu v2 co bug):
   - Step 1: Ops switch traffic ve active (v1)
   - Step 2: v1 van working (column shipping_address co the null)
   - Giai thich: tai sao khong can rollback schema?

**Deliverable:** `rollout-bluegreen-migration.yaml` + `migration-job.yaml` + promotion runbook

---

## Challenge 5: Multi-Cluster Canary

**Muc tieu:** Thiet ke canary chay tren 1 cluster truoc, promote tat ca cluster cung luc.

**Scenario:**
Team co 3 EKS cluster:
- `eks-dev` (1 cluster, 1 region)
- `eks-staging` (1 cluster, 1 region)
- `eks-prod` (2 cluster, 2 region — HA)

Yeu cau: Canary chay tren `eks-dev` truoc, neu ok 30 phut thi promote `eks-staging`, neu ok 1h thi promote `eks-prod`.

**Yeu cau:**

1. Thiet ke ArgoCD ApplicationSet:
   - Generator: cluster (cho 3 cluster)
   - Template: Rollout voi canary 25% -> 50% -> 75% -> 100%
   - Per-cluster `values`: replicas khac nhau (dev: 1, staging: 2, prod: 5)

2. Thiet ke promotion gate:
   - Day 26 khong ho tro inter-cluster promotion gate natively
   - De cuong: dung ArgoCD ApplicationSet generator ket hop `values.rolloutPhase`
   - Mo ta: dev rollouts thanh `stable` → staging rollouts bat dau → staging stable → prod rollouts bat dau

3. Viet Bash script automation:
   - Check dev cluster Rollout status
   - Neu `Healthy`, trigger staging rollout
   - Neu staging `Healthy`, trigger prod rollout
   - Neu bat ky cluster fail, alert Slack

**Deliverable:** `applicationset-rollouts.yaml` + `promotion-script.sh`

---

## Bonus Challenge: Flagger vs Argo Rollouts

**Muc tieu:** Compare Argo Rollouts voi Flagger (另一 progressive delivery tool).

**Research task:**

1. Flagger co gi khac Argo Rollouts?
   - Architecture: Flagger la operator (CRD + controller), Argo Rollouts la controller
   - Provider: Flagger ho tro nhieu service mesh (Istio, Linkerd, App Mesh, OSM)
   - Analysis: Flagger co built-in metrics (Prometheus, Datadog, CloudWatch)
   - Auto-rollback: Ca 2 deu co

2. Migrate Flagger `Canary` resource sang Argo Rollouts `Rollout`:
   - Flagger Canary: apiVersion: flagger.app/v1beta1
   - Argo Rollouts: apiVersion: argoproj.io/v1alpha1
   - So sanh field mapping

3. Tinh huong nao nen dung Flagger thay vi Argo Rollouts?

**Deliverable:** Research report (Markdown, 5-10 cau hoi Q&A)

---

## Hints & Giai thich

### Hint Challenge 1
Replica-based canary: weight 10% voi 5 replicas = 0.5 replica. Argo Rollouts lam tron len 1 pod. Neu co 5 replicas, 10% = 1 pod canary (round up).

### Hint Challenge 2
startingStep 1 = sau setWeight 25% (index 0). Step list bat dau tu 0:
- index 0: setWeight 20
- index 1: setWeight 50 (startingStep=1)
Neu `startingStep: 2`, analysis bat dau sau step index 2 (75%).

### Hint Challenge 3
`null` response tu Prometheus co nghia la:
1. Metric name khong dung (typo)
2. Prometheus chua scrape target
3. Network policy chan traffic
4. Query syntax sai

### Hint Challenge 4
Backward-compatible schema: column co default value hoac cho phep NULL. App code v1 handle NULL graceful. Neu rollback, v1 code van work vi column moi.

### Hint Challenge 5
Inter-cluster promotion gate can external orchestration (Argo Workflows / Jenkins / GitHub Actions). Argo Rollouts khong co built-in inter-cluster gate.
