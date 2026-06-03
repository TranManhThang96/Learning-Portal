# Day 24: Exercises — Production-ready Kubernetes Checklist

---

## Bài 1: Easy — Audit Single Service

### Context

Bạn vừa join team mới. Team lead giao cho bạn 1 Deployment đang chạy trên production và yêu cầu: "Audit service này theo production checklist, liệt kê gaps."

### Yêu cầu

1. Tạo kind cluster và deploy service sau (có nhiều thiếu sót):

```yaml
# audit-target.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
        - name: api
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  selector:
    app: user-service
  ports:
    - port: 80
```

2. Audit theo 4 categories: Workload, Security, Observability, Reliability.
3. Liệt kê từng gap với severity (🔴 Critical / 🟡 Important / 🟢 Nice-to-have).
4. Fix tất cả 🔴 Critical gaps.
5. Verify fix bằng commands.

### Expected Outcome

- Audit report liệt kê ≥ 10 gaps.
- Tất cả Critical gaps fixed.
- Deployment Running với probes, resources, replicas ≥ 2.

### Hint

- Check: resources? probes? replicas? PDB? labels? securityContext? NetworkPolicy?
- Dùng `kubectl describe` và `kubectl get -o yaml` để inspect.

### Acceptance Criteria

- [ ] Audit report có ≥ 10 gaps được liệt kê.
- [ ] Từng gap có severity classification.
- [ ] Tất cả 🔴 Critical fixed (resources, probes, replicas).
- [ ] Pod Running + Ready sau fix.
- [ ] Verification commands documented.

### Bonus Challenge

Viết script bash tự động audit bất kỳ Deployment nào: input = deployment name + namespace, output = gaps list.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name audit-lab

kubectl apply -f audit-target.yaml
sleep 10

echo "=== AUDIT REPORT: user-service ==="
echo ""
echo "--- WORKLOAD ---"
echo "🔴 [FAIL] W1: No resource requests"
echo "🔴 [FAIL] W2: No resource limits"
echo "🔴 [FAIL] W3: No liveness probe"
echo "🔴 [FAIL] W4: No readiness probe"
echo "🔴 [FAIL] W9: Single replica (replicas=1)"
echo "🟡 [FAIL] W6: No PDB"
echo "🟡 [FAIL] W8: No graceful shutdown config"
echo "🟡 [FAIL] W10: No update strategy specified"
echo ""
echo "--- SECURITY ---"
echo "🔴 [FAIL] S1: Using default ServiceAccount"
echo "🔴 [FAIL] S5: Not enforcing non-root"
echo "🔴 [FAIL] S4: No NetworkPolicy"
echo "🟡 [FAIL] S6: No readOnlyRootFilesystem"
echo "🟡 [FAIL] S12: No explicit privileged:false"
echo ""
echo "--- OBSERVABILITY ---"
echo "🟡 [FAIL] Labels missing: team, environment, cost-center"
echo ""
echo "--- RELIABILITY ---"
echo "🟡 [FAIL] No PDB for drain protection"
echo ""
echo "Total gaps: 15 (6 Critical, 6 Important, 3 Nice-to-have)"

# FIX CRITICAL GAPS
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  labels:
    team: backend
    environment: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: user-service
        team: backend
        environment: production
    spec:
      serviceAccountName: default
      terminationGracePeriodSeconds: 30
      containers:
        - name: api
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          securityContext:
            runAsNonRoot: false
            readOnlyRootFilesystem: false
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: user-service-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: user-service
EOF

# Verify
sleep 15
kubectl get pods
kubectl get pdb
kubectl describe deployment user-service | grep -A5 "Limits\|Liveness\|Readiness"

kind delete cluster --name audit-lab
```

**Bonus — Audit script:**

```bash
#!/bin/bash
# audit-deployment.sh <deployment-name> <namespace>
DEPLOY=${1:?Usage: $0 <deployment> <namespace>}
NS=${2:-default}
GAPS=0

echo "=== Audit: $DEPLOY (namespace: $NS) ==="

# Resources
HAS_REQ=$(kubectl get deploy $DEPLOY -n $NS -o json | jq '[.spec.template.spec.containers[] | select(.resources.requests!=null)] | length')
HAS_LIM=$(kubectl get deploy $DEPLOY -n $NS -o json | jq '[.spec.template.spec.containers[] | select(.resources.limits!=null)] | length')
TOTAL=$(kubectl get deploy $DEPLOY -n $NS -o json | jq '.spec.template.spec.containers | length')

[ "$HAS_REQ" -lt "$TOTAL" ] && echo "🔴 Missing resource requests" && GAPS=$((GAPS+1))
[ "$HAS_LIM" -lt "$TOTAL" ] && echo "🔴 Missing resource limits" && GAPS=$((GAPS+1))

# Probes
HAS_LIVE=$(kubectl get deploy $DEPLOY -n $NS -o json | jq '[.spec.template.spec.containers[] | select(.livenessProbe!=null)] | length')
HAS_READY=$(kubectl get deploy $DEPLOY -n $NS -o json | jq '[.spec.template.spec.containers[] | select(.readinessProbe!=null)] | length')
[ "$HAS_LIVE" -lt "$TOTAL" ] && echo "🔴 Missing liveness probe" && GAPS=$((GAPS+1))
[ "$HAS_READY" -lt "$TOTAL" ] && echo "🔴 Missing readiness probe" && GAPS=$((GAPS+1))

# Replicas
REPLICAS=$(kubectl get deploy $DEPLOY -n $NS -o jsonpath='{.spec.replicas}')
[ "$REPLICAS" -lt 2 ] && echo "🔴 Single replica ($REPLICAS)" && GAPS=$((GAPS+1))

# PDB
PDB=$(kubectl get pdb -n $NS -o json | jq "[.items[] | select(.spec.selector.matchLabels.app==\"$(kubectl get deploy $DEPLOY -n $NS -o jsonpath='{.spec.selector.matchLabels.app}')\")]| length")
[ "$PDB" -eq 0 ] && echo "🟡 No PDB" && GAPS=$((GAPS+1))

# NetworkPolicy
NP=$(kubectl get networkpolicy -n $NS --no-headers 2>/dev/null | wc -l)
[ "$NP" -eq 0 ] && echo "🔴 No NetworkPolicy in namespace" && GAPS=$((GAPS+1))

echo ""
echo "Total gaps: $GAPS"
```

</details>


---

## Bài 2: Medium — Full Stack Audit & Remediation Plan

### Context

Bạn là DevOps engineer cho team product. BookStore stack (Day 17) đang chạy trên staging. PM yêu cầu: "Đánh giá xem stack này có sẵn sàng go production không? Nếu chưa, estimate effort để fix."

### Yêu cầu

1. Deploy BookStore stack (4 services: frontend, api-gateway, book-service, redis) trong namespace `bookstore`.
2. Chạy audit hoàn chỉnh theo **8 categories** (cluster, workload, security, observability, backup, cost, release, runbook).
3. Tạo **gap analysis report** (markdown):
   - Liệt kê từng gap, severity, category.
   - Tính "production readiness score" (% items passed).
   - Prioritized remediation plan với effort estimate.
4. **Fix top 5 critical gaps** (code changes).
5. **Re-audit** sau fix, so sánh score trước/sau.

### Expected Outcome

- Initial score: ~15-25% (nhiều thiếu sót).
- After fix score: ~50-60% (critical gaps addressed).
- Gap analysis report ≥ 20 items.
- 5 critical fixes applied và verified.

### Hint

- 4 services × nhiều checklist items = nhiều gaps.
- Focus fix: resource limits → probes → replicas → PDB → NetworkPolicy.
- Redis cần config khác (port 6379, không cần HTTP probe).

### Acceptance Criteria

- [ ] BookStore stack deployed (4 services, 4 Services).
- [ ] Audit report có ≥ 20 gaps across 8 categories.
- [ ] Production readiness score calculated (before/after).
- [ ] Remediation plan prioritized (P0/P1/P2).
- [ ] Top 5 critical gaps fixed.
- [ ] Re-audit score improved ≥ 25 percentage points.
- [ ] Before/after comparison table.

### Bonus Challenge

Integrate [Polaris](https://github.com/FairwindsOps/polaris) hoặc [Kubescape](https://github.com/kubescape/kubescape) để auto-scan cluster và compare results với manual audit.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name audit-full

# Deploy BookStore base
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: bookstore
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: web
          image: nginx:1.25
          ports: [{containerPort: 80}]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports: [{containerPort: 80}]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-service
  template:
    metadata:
      labels:
        app: book-service
    spec:
      containers:
        - name: service
          image: nginx:1.25
          ports: [{containerPort: 80}]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports: [{containerPort: 6379}]
---
apiVersion: v1
kind: Service
metadata: {name: frontend-svc, namespace: bookstore}
spec:
  selector: {app: frontend}
  ports: [{port: 80}]
---
apiVersion: v1
kind: Service
metadata: {name: api-gateway-svc, namespace: bookstore}
spec:
  selector: {app: api-gateway}
  ports: [{port: 80}]
---
apiVersion: v1
kind: Service
metadata: {name: book-service-svc, namespace: bookstore}
spec:
  selector: {app: book-service}
  ports: [{port: 80}]
---
apiVersion: v1
kind: Service
metadata: {name: redis-svc, namespace: bookstore}
spec:
  selector: {app: redis}
  ports: [{port: 6379}]
EOF

sleep 15

# INITIAL AUDIT SCORE: ~15%
# Fix top 5: resources, probes, replicas, PDB, basic security

cat <<EOF | kubectl apply -f -
# Fixed deployments
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
  labels: {team: product, environment: staging}
spec:
  replicas: 2
  selector:
    matchLabels: {app: frontend}
  template:
    metadata:
      labels: {app: frontend, team: product}
    spec:
      containers:
        - name: web
          image: nginx:1.25
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
          livenessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
  labels: {team: product, environment: staging}
spec:
  replicas: 2
  selector:
    matchLabels: {app: api-gateway}
  template:
    metadata:
      labels: {app: api-gateway, team: product}
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
          livenessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
  labels: {team: product, environment: staging}
spec:
  replicas: 2
  selector:
    matchLabels: {app: book-service}
  template:
    metadata:
      labels: {app: book-service, team: product}
    spec:
      containers:
        - name: service
          image: nginx:1.25
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 200m, memory: 256Mi}
          livenessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bookstore
  labels: {team: product, environment: staging}
spec:
  replicas: 1
  selector:
    matchLabels: {app: redis}
  template:
    metadata:
      labels: {app: redis, team: product}
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports: [{containerPort: 6379}]
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: frontend-pdb, namespace: bookstore}
spec:
  minAvailable: 1
  selector:
    matchLabels: {app: frontend}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: api-gateway-pdb, namespace: bookstore}
spec:
  minAvailable: 1
  selector:
    matchLabels: {app: api-gateway}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: book-service-pdb, namespace: bookstore}
spec:
  minAvailable: 1
  selector:
    matchLabels: {app: book-service}
EOF

# RE-AUDIT: ~55%
sleep 15
kubectl get pods -n bookstore
kubectl get pdb -n bookstore

echo "=== SCORE COMPARISON ==="
echo "Before: 15% (4/27 items passed)"
echo "After:  55% (15/27 items passed)"
echo ""
echo "Remaining gaps: NetworkPolicy, RBAC, non-root, monitoring, backup, runbooks"

kind delete cluster --name audit-full
```

</details>

---

## Bài 3: Hard — Enterprise Multi-tenant Production Checklist

### Context

Bạn là Platform Engineer tại fintech company. CTO giao nhiệm vụ: "Thiết kế production checklist cho Kubernetes platform phục vụ 5 product teams, 30+ microservices, compliance requirements (PCI-DSS relevant)."

### Yêu cầu

1. **Thiết kế comprehensive checklist** > 50 items, organized by:
   - Platform-level (cluster team owns)
   - Workload-level (product team owns)
   - Shared responsibility items

2. **Mỗi item phải có**:
   - Description
   - Owner (platform team / product team / shared)
   - Severity (critical/important/nice-to-have)
   - Verification method (command hoặc tool)
   - Remediation guide (how to fix)
   - Compliance mapping (PCI-DSS requirement nếu applicable)

3. **Thiết kế automation**:
   - Script hoặc tool chạy automated audit
   - Output score per team, per namespace
   - Trend tracking (improve over time)

4. **Viết onboarding guide** cho product teams: "Khi team X muốn deploy service mới lên platform, họ cần đáp ứng những gì?"

### Expected Outcome

- Checklist ≥ 50 items (markdown hoặc spreadsheet format).
- Automation script chạy được.
- Onboarding guide ≤ 2 pages.
- Owner/responsibility matrix rõ ràng.

### Hint

- PCI-DSS relevant items: encryption, access control, logging, network segmentation.
- Platform team: cluster security, monitoring infra, networking, admission policies.
- Product team: app code, health checks, resource sizing, runbooks.
- Shared: incident response, cost management.

### Acceptance Criteria

- [ ] ≥ 50 checklist items documented.
- [ ] Mỗi item có 6 fields (description, owner, severity, verification, remediation, compliance).
- [ ] Owner distribution: ~40% platform, ~40% product, ~20% shared.
- [ ] Automation script scans namespace và outputs score.
- [ ] Onboarding guide có step-by-step + examples.
- [ ] Script tested trên kind cluster.

### Bonus Challenge

Deploy [Polaris](https://github.com/FairwindsOps/polaris) webhook vào cluster ở Audit mode. Compare Polaris findings với your custom checklist. Identify items Polaris misses.

<details>
<summary>Solution</summary>

Tham khảo lesson.md section 4 (8 categories) và mở rộng thêm multi-tenant items:

```markdown
# Enterprise Production Checklist — Multi-tenant Kubernetes Platform

## Platform-level (Cluster Team)

| # | Item | Severity | Verification | Compliance |
|---|------|----------|-------------|------------|
| P1 | HA Control Plane (3+ nodes) | 🔴 | kubectl get nodes -l node-role... | PCI 1.3 |
| P2 | etcd encrypted at rest | 🔴 | Check EncryptionConfiguration | PCI 3.4 |
| P3 | etcd backup automated (6h) | 🔴 | Check cron, verify backup files | PCI 10.7 |
| P4 | Admission controller deployed | 🔴 | kubectl get clusterpolicy | PCI 2.2 |
| P5 | Cluster version N-1 or newer | 🟡 | kubectl version | N/A |
| P6 | Node auto-upgrade configured | 🟡 | Cloud provider config | PCI 6.2 |
| P7 | Audit logging enabled | 🔴 | API server audit-policy-file | PCI 10.1-3 |
| P8 | mTLS for control plane | 🔴 | Certificate inspection | PCI 4.1 |
| P9 | CNI with NetworkPolicy support | 🔴 | kubectl get networkpolicy test | PCI 1.2 |
| P10 | Cluster monitoring stack | 🔴 | kubectl get pods -n monitoring | PCI 10.6 |
(... 15+ more platform items)

## Workload-level (Product Team)
(... 20+ items covering resources, probes, security context, etc.)

## Shared Responsibility
(... 15+ items covering incident response, cost, releases)
```

**Automation script — tóm tắt:**

```bash
#!/bin/bash
# audit-namespace.sh <namespace>
NS=$1
SCORE=0
TOTAL=0
# ... check each item, increment SCORE if pass, TOTAL always
echo "Score: $SCORE/$TOTAL ($((SCORE*100/TOTAL))%)"
```

**Onboarding guide tóm tắt:**

```markdown
# Deploying a New Service to Platform

1. Create namespace request (Jira ticket)
2. Platform team provisions namespace with defaults (NetworkPolicy, LimitRange, ResourceQuota)
3. Product team creates Deployment with:
   - Resource requests/limits
   - Liveness + readiness probes
   - Dedicated ServiceAccount
   - Non-root securityContext
   - Labels: team, app, environment, cost-center
4. Product team creates Service + Ingress (if external)
5. Product team creates PDB (minAvailable)
6. Run audit script: `./audit-namespace.sh <namespace>`
7. Score must be ≥ 80% to proceed
8. Platform team reviews and approves
9. Deploy to staging → production
```

</details>

---

## Solution/Reference Implementation

Các lời giải chi tiết nằm trong block `<details><summary>Solution</summary>` của từng bài để người học có thể thử trước khi mở đáp án. Reference cuối file:

- **Bài 1 — Easy**: audit một Deployment, fix resources/probes/replicas/PDB/NetworkPolicy và verify bằng script.
- **Bài 2 — Medium**: audit full stack BookStore, lập remediation plan, áp top fixes và re-audit score.
- **Bài 3 — Hard**: thiết kế checklist multi-tenant, tách platform/product responsibility và tạo onboarding workflow.

