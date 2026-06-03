# Day 24: Production-ready Kubernetes Checklist

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Đánh giá được** mức độ production-ready của một Kubernetes deployment theo 8 checklist categories.
2. **Xác định và ưu tiên được** gaps giữa trạng thái hiện tại và production-ready, phân loại theo severity (critical/important/nice-to-have).
3. **Audit được** một microservice stack thực tế (BookStore từ Day 17) và tạo improvement plan.
4. **Thiết kế được** production checklist phù hợp với context cụ thể (startup vs enterprise).
5. **Áp dụng được** maturity model để đo lường tiến trình production-readiness theo thời gian.

---

## 2. Bối cảnh & Động lực

### "Works on my machine" vs Production

Trong development, bạn chỉ cần app chạy được. Trong production, bạn cần app:
- **Chạy ổn định** 24/7 (reliability)
- **Chịu tải** peak traffic (scalability)
- **Bảo mật** trước threats (security)
- **Quan sát được** khi có vấn đề (observability)
- **Recover được** khi failure (disaster recovery)
- **Không tốn quá nhiều tiền** (cost efficiency)

### Analogy cho Developer

Production checklist giống **code review checklist**:
- Code review: "Có unit tests? Có error handling? Có logging? Có documentation?"
- Production checklist: "Có health check? Có resource limits? Có backup? Có monitoring?"

Không ai ship code không qua review. Không nên ship workload không qua production checklist.

### Hậu quả thực tế

| Thiếu gì | Hậu quả |
|----------|---------|
| Resource limits | Noisy neighbor → service khác bị OOMKilled |
| Health probes | Traffic gửi tới pod chưa ready → 5xx errors |
| PDB | Node drain → service downtime |
| NetworkPolicy | Lateral movement sau container escape |
| Backup | Mất data → không recover được |
| Monitoring | Không biết service down cho đến khi user báo |
| Runbooks | Engineer mới on-call → panic, MTTR tăng |

---

## 3. Kiến thức nền tảng

### Production Maturity Model

```
Level 0: "It works"
  → App deploy được, chạy được trên K8s

Level 1: "It works reliably"
  → Health probes, resource limits, restart policy, PDB

Level 2: "It works securely"
  → RBAC, NetworkPolicy, PSS, admission policies, secret management

Level 3: "It's observable"
  → Metrics, logs, traces, dashboards, alerts, SLO

Level 4: "It recovers"
  → Backup, DR plan, runbooks, tested restore procedure

Level 5: "It's efficient"
  → Right-sizing, autoscaling, cost allocation, FinOps
```

### Defense in Depth

```
┌─────────────────────────────────────────────┐
│           Layer 1: Cluster Security          │
│  RBAC, PSS, Admission Control, etcd encrypt │
├─────────────────────────────────────────────┤
│         Layer 2: Network Security            │
│  NetworkPolicy, mTLS, Ingress TLS           │
├─────────────────────────────────────────────┤
│         Layer 3: Workload Security           │
│  Resource limits, probes, non-root, readonly │
├─────────────────────────────────────────────┤
│        Layer 4: Supply Chain Security        │
│  Image scanning, trusted registry, signing  │
├─────────────────────────────────────────────┤
│         Layer 5: Observability               │
│  Metrics, logs, traces, alerts, SLO         │
├─────────────────────────────────────────────┤
│         Layer 6: Reliability                 │
│  Backup, DR, PDB, upgrade plan, runbooks    │
└─────────────────────────────────────────────┘
```

---

## 4. Deep Dive — 8 Production Checklists

### 4.1 Cluster Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| C1 | HA Control Plane | 🔴 Critical | ≥ 3 control plane nodes (etcd quorum) |
| C2 | etcd Backup | 🔴 Critical | Automated backup, tested restore |
| C3 | Version Policy | 🟡 Important | N-1 hoặc N-2 (không quá cũ) |
| C4 | Node Pool Strategy | 🟡 Important | Separate pools cho workload types |
| C5 | Cluster Monitoring | 🔴 Critical | API server, etcd, node health metrics |
| C6 | Certificate Management | 🟡 Important | Auto-renewal, expiry monitoring |
| C7 | Upgrade Runbook | 🟡 Important | Documented upgrade procedure |
| C8 | Admission Controllers | 🟡 Important | Policy engine (Kyverno/Gatekeeper) |

### 4.2 Workload Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| W1 | Resource Requests | 🔴 Critical | CPU + memory requests trên mọi container |
| W2 | Resource Limits | 🔴 Critical | Memory limits bắt buộc, CPU limits tùy chọn |
| W3 | Liveness Probe | 🔴 Critical | Detect stuck process → auto-restart |
| W4 | Readiness Probe | 🔴 Critical | Chỉ nhận traffic khi ready |
| W5 | Startup Probe | 🟢 Nice-to-have | Cho slow-starting apps (JVM, .NET) |
| W6 | PodDisruptionBudget | 🟡 Important | Availability khi drain/upgrade |
| W7 | Topology Spread | 🟢 Nice-to-have | Spread pods across nodes/zones |
| W8 | Graceful Shutdown | 🟡 Important | preStop hook + SIGTERM handling |
| W9 | Replicas ≥ 2 | 🔴 Critical | Single pod = single point of failure |
| W10 | Update Strategy | 🟡 Important | RollingUpdate với maxUnavailable/maxSurge |

### 4.3 Security Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| S1 | Dedicated ServiceAccount | 🔴 Critical | Không dùng default SA |
| S2 | RBAC Least Privilege | 🔴 Critical | Chỉ cấp quyền cần thiết |
| S3 | Pod Security Standards | 🔴 Critical | Baseline hoặc Restricted |
| S4 | NetworkPolicy | 🔴 Critical | Default deny + explicit allow |
| S5 | Non-root Container | 🔴 Critical | runAsNonRoot: true |
| S6 | Read-only Filesystem | 🟡 Important | readOnlyRootFilesystem: true |
| S7 | Image Scanning | 🔴 Critical | Trivy/Grype trong CI/CD |
| S8 | Trusted Registry Only | 🟡 Important | Admission policy restrict registries |
| S9 | Secret Encryption at Rest | 🟡 Important | etcd encryption provider |
| S10 | Secret Rotation | 🟢 Nice-to-have | External Secrets + rotation |
| S11 | Admission Policies | 🟡 Important | Block privileged, require labels/limits |
| S12 | No Privileged Containers | 🔴 Critical | privileged: false |

### 4.4 Observability Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| O1 | Application Metrics | 🔴 Critical | RED metrics: Rate, Errors, Duration |
| O2 | Infrastructure Metrics | 🔴 Critical | CPU, memory, disk, network per pod/node |
| O3 | Structured Logging | 🟡 Important | JSON logs với request ID, timestamp |
| O4 | Log Aggregation | 🟡 Important | Central logging (Loki, ELK) |
| O5 | Distributed Tracing | 🟢 Nice-to-have | Cross-service trace (OpenTelemetry) |
| O6 | Dashboards | 🔴 Critical | Service-specific + cluster overview |
| O7 | Alerting | 🔴 Critical | SLO-based alerts, không alert fatigue |
| O8 | SLI/SLO Defined | 🟡 Important | Availability, latency targets |
| O9 | On-call Rotation | 🟡 Important | Defined schedule, escalation path |

### 4.5 Backup Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| B1 | etcd Backup | 🔴 Critical | Automated, ≥ daily |
| B2 | PV/Data Backup | 🔴 Critical | Database, persistent storage |
| B3 | Resource Backup | 🟡 Important | Velero namespace backup |
| B4 | Backup Verification | 🔴 Critical | Monthly restore test |
| B5 | Offsite Copy | 🟡 Important | Cross-region/cross-account |
| B6 | Retention Policy | 🟡 Important | Defined, automated rotation |
| B7 | DR Plan Documented | 🔴 Critical | RPO/RTO targets, restore procedure |
| B8 | DR Drill | 🟢 Nice-to-have | Quarterly DR exercise |

### 4.6 Cost Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| $1 | Resource Right-sizing | 🟡 Important | Requests match actual usage (P95) |
| $2 | Autoscaling | 🟡 Important | HPA/VPA/Cluster Autoscaler configured |
| $3 | Cost Allocation | 🟡 Important | Labels: team, environment, cost-center |
| $4 | Unused Resource Cleanup | 🟢 Nice-to-have | Remove idle pods, unattached PVs |
| $5 | Spot/Preemptible Nodes | 🟢 Nice-to-have | Cho non-critical workloads |
| $6 | Log/Metric Retention | 🟢 Nice-to-have | Không lưu vĩnh viễn, tiered storage |
| $7 | Cost Visibility | 🟡 Important | Dashboard chi phí per team/service |

### 4.7 Release Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| R1 | CI/CD Pipeline | 🔴 Critical | Automated build, test, scan, deploy |
| R2 | Deployment Strategy | 🔴 Critical | RollingUpdate, canary, hoặc blue-green |
| R3 | Rollback Plan | 🔴 Critical | 1-command rollback, tested |
| R4 | Smoke Tests | 🟡 Important | Post-deploy verification |
| R5 | Quality Gates | 🟡 Important | Tests, coverage, scan phải pass |
| R6 | GitOps | 🟢 Nice-to-have | Git as source of truth |
| R7 | Feature Flags | 🟢 Nice-to-have | Decouple deploy from release |

### 4.8 Runbook Checklist

| # | Item | Severity | Mô tả |
|---|------|----------|--------|
| RB1 | Service Down Runbook | 🔴 Critical | Step-by-step cho service outage |
| RB2 | High Latency Runbook | 🔴 Critical | Debug latency spike |
| RB3 | Database Issues Runbook | 🟡 Important | Connection issues, slow queries |
| RB4 | Scaling Runbook | 🟡 Important | Manual scale khi autoscaler không đủ |
| RB5 | Incident Response Process | 🔴 Critical | Severity levels, roles, communication |
| RB6 | Escalation Path | 🔴 Critical | Who to call, when to escalate |
| RB7 | Post-incident Review | 🟡 Important | Blameless postmortem process |

---

## 5. Trade-offs & Best Practices ⭐

### Startup vs Enterprise Checklist Scope

| Category | Startup (Day 1) | Growth (Series B) | Enterprise |
|----------|----------------|-------------------|-----------|
| Cluster | Single cluster, managed K8s | Multi-env, HA CP | Multi-cluster, multi-region |
| Workload | Requests/limits, probes | + PDB, topology | + Pod priority, preemption |
| Security | RBAC basic, non-root | + NetworkPolicy, PSS | + Service mesh, mTLS, zero-trust |
| Observability | Logs + basic metrics | + Dashboards, alerts | + Tracing, SLO, error budget |
| Backup | etcd backup, manual | + Velero automated | + Cross-region, DR drills |
| Cost | Right-sizing cơ bản | + Autoscaling | + FinOps, chargeback |
| Release | CI/CD basic | + Canary, quality gates | + Progressive delivery, feature flags |
| Runbooks | Top 5 failures | + Full incident process | + Automated remediation |

### Incremental Adoption Strategy

```
Week 1-2: 🔴 Critical items only
  → Resource limits, probes, RBAC, non-root, backup

Week 3-4: 🟡 Important items
  → NetworkPolicy, PDB, monitoring, alerts, runbooks

Month 2-3: 🟢 Nice-to-have items
  → Tracing, SLO, topology spread, cost optimization

Ongoing: Review & iterate
  → Monthly checklist audit, update based on incidents
```

### Anti-patterns

1. **Checklist theater**: Check items mà không hiểu tại sao → false sense of security.
2. **All-or-nothing**: Chờ hoàn thành 100% mới deploy → ship chậm. **Rollout incremental**.
3. **One checklist fits all**: Dùng enterprise checklist cho startup → over-engineering.
4. **Static checklist**: Không update sau incidents → miss new failure modes.

---

## 6. Performance & Scalability ⭐

### Performance Checklist Items

| Item | Metric cần check | Target |
|------|-----------------|--------|
| CPU right-sizing | P95 CPU usage / CPU request | 60-80% |
| Memory right-sizing | P95 memory usage / memory request | 70-85% |
| HPA responsiveness | Time from load increase to scale | < 2 minutes |
| Pod startup time | Container ready after schedule | < 30 seconds |
| Probe intervals | Liveness + readiness period | 5-15 seconds |
| DNS performance | CoreDNS latency P99 | < 10ms |
| Image pull time | Time to pull container image | < 30 seconds |

### Scaling Readiness Assessment

```
Checklist cho "Sẵn sàng chịu 10x traffic?":

□ HPA configured với proper targets (70-80% CPU)
□ Cluster autoscaler enabled (nếu cloud)
□ Pod anti-affinity spread across nodes
□ Database connection pooling configured
□ Rate limiting ở Ingress layer
□ Cache layer (Redis) có đủ capacity
□ Load test đã chạy ở 2x current peak
□ PDB cho phép scale operations
□ Graceful shutdown < 30s
□ No single point of failure
```

---

## 7. Security & Reliability Considerations

### Security Audit Quick Commands

```bash
# Check pods chạy privileged
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.containers[].securityContext.privileged==true) | "\(.metadata.namespace)/\(.metadata.name)"'

# Check pods chạy root
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.containers[].securityContext.runAsNonRoot!=true) | "\(.metadata.namespace)/\(.metadata.name)"'

# Check pods không có resource limits
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.containers[].resources.limits==null) | "\(.metadata.namespace)/\(.metadata.name)"'

# Check services không có endpoints
kubectl get endpoints -A -o json | jq -r '.items[] | select(.subsets==null) | "\(.metadata.namespace)/\(.metadata.name)"'

# Check namespaces không có NetworkPolicy
for ns in $(kubectl get ns -o name | cut -d/ -f2 | grep -v kube); do
  count=$(kubectl get networkpolicy -n $ns --no-headers 2>/dev/null | wc -l)
  if [ "$count" -eq 0 ]; then echo "NO NETPOL: $ns"; fi
done
```

---

## 8. Hands-on Example — Audit Day 17 BookStore

### Scenario

Day 17 deploy BookStore microservices: Frontend, API Gateway, Book Service, Redis. Bây giờ chúng ta audit nó bằng production checklist.

### Step 1: Recreate Day 17 Stack (simplified)

```yaml
# bookstore-base.yaml
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
        - name: frontend
          image: nginx:1.25
          ports:
            - containerPort: 80
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
          ports:
            - containerPort: 80
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
          ports:
            - containerPort: 80
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
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: frontend-svc
  namespace: bookstore
spec:
  selector:
    app: frontend
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-svc
  namespace: bookstore
spec:
  selector:
    app: api-gateway
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: book-service-svc
  namespace: bookstore
spec:
  selector:
    app: book-service
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: redis-svc
  namespace: bookstore
spec:
  selector:
    app: redis
  ports:
    - port: 6379
```

### Step 2: Audit Results

```bash
# Deploy base stack
kubectl apply -f bookstore-base.yaml
sleep 15

# Audit script
echo "=== PRODUCTION READINESS AUDIT ==="
echo ""
echo "--- WORKLOAD ---"
echo "[FAIL] W1: Resource requests missing"
kubectl get pods -n bookstore -o json | jq '[.items[].spec.containers[] | select(.resources.requests==null)] | length' 
echo "[FAIL] W2: Resource limits missing"
echo "[FAIL] W3: Liveness probe missing"
echo "[FAIL] W4: Readiness probe missing"
echo "[FAIL] W6: No PDB found"
kubectl get pdb -n bookstore 2>/dev/null || echo "  No PDB"
echo "[FAIL] W9: Single replica deployments"
kubectl get deployments -n bookstore -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.replicas
echo ""
echo "--- SECURITY ---"
echo "[FAIL] S1: Using default ServiceAccount"
echo "[FAIL] S4: No NetworkPolicy"
kubectl get networkpolicy -n bookstore 2>/dev/null || echo "  No NetworkPolicy"
echo "[FAIL] S5: Not enforcing non-root"
echo ""
echo "--- OBSERVABILITY ---"
echo "[FAIL] O1-O9: No monitoring configured"
echo ""
echo "--- SCORE: 0/30 critical items passed ---"
```

### Step 3: Improvement Plan (Priority Order)

| Priority | Item | Action | Effort |
|----------|------|--------|--------|
| P0 | Resource limits | Thêm requests/limits cho mọi container | 30 min |
| P0 | Health probes | Thêm liveness + readiness probe | 30 min |
| P0 | Replicas ≥ 2 | Tăng replicas cho frontend, API gateway, book service | 5 min |
| P1 | PDB | Tạo PDB cho mỗi deployment | 15 min |
| P1 | NetworkPolicy | Default deny + explicit allow | 30 min |
| P1 | RBAC | Dedicated ServiceAccount per service | 20 min |
| P2 | Non-root | Thêm securityContext | 15 min |
| P2 | Labels | Thêm team, environment, cost-center | 10 min |
| P3 | Monitoring | Deploy Prometheus + Grafana | 2-4 hours |

→ Day 25 mini-project sẽ thực hiện P0 + P1 improvements.

### Cleanup

```bash
kubectl delete namespace bookstore
```

---

## 9. Common Pitfalls & Debugging

### Most Commonly Missed Checklist Items

1. **Readiness probe** — 40% deployments thiếu → traffic tới pod chưa ready.
2. **PDB** — 60% deployments thiếu → downtime khi node drain.
3. **NetworkPolicy** — 70% namespaces thiếu → full lateral movement.
4. **Resource limits** — 30% containers thiếu → noisy neighbor.
5. **Non-root** — 50% containers chạy root → container escape risk.

### "False Sense of Security" Patterns

| Pattern | Vấn đề |
|---------|--------|
| Liveness probe = readiness probe | Liveness fail → restart loop thay vì chỉ remove from service |
| PDB minAvailable = replicas | Drain KHÔNG BAO GIỜ complete |
| CPU limit quá thấp | Silent throttling, latency tăng |
| NetworkPolicy chỉ ingress | Egress unrestricted → data exfiltration |
| Backup không test restore | Backup corrupt → không discover cho đến disaster |

### Case Study: Production Outage do Thiếu Readiness Probe

**Context**: SaaS platform, 10 microservices, Kubernetes trên GKE.

**Symptom**: Deploy version mới → 30% requests lỗi 502 trong 2 phút.

**Root Cause**: Service mới cần 45 giây để warm JVM heap và load cache. Không có readiness probe → Kubernetes gửi traffic ngay khi container start → 502 errors.

**Fix**: Thêm readiness probe với `initialDelaySeconds: 60`.

**Lesson**: Readiness probe = **gateway** giữa container start và nhận traffic. Không có → assume ready ngay = lỗi.

---

## 10. Kết nối với bài trước & bài sau

### Từ Phase 3 (Day 18-23)

Day 24 tổng hợp tất cả kiến thức Phase 3:
- **Day 18**: Resource limits → Workload checklist (W1, W2)
- **Day 19**: Autoscaling → Cost checklist ($2)
- **Day 20**: RBAC, PSS, NetworkPolicy → Security checklist (S1-S5)
- **Day 21**: Admission policies → Security checklist (S8, S11)
- **Day 22**: Troubleshooting → Runbook checklist (RB1-RB7)
- **Day 23**: Upgrade, backup → Backup checklist (B1-B8), Cluster checklist (C3, C7)

### Sang Day 25 (Mini-project)

Day 25 sẽ **thực hiện** checklist này trên BookStore application:
- Apply P0 items (resource limits, probes, replicas)
- Apply P1 items (PDB, NetworkPolicy, RBAC)
- Simulate incidents và viết runbooks
- Tạo before/after comparison report

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Production Best Practices (learnk8s.io)](https://learnk8s.io/production-best-practices)
- [Kubernetes Security Checklist (Official)](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [GKE Hardening Guide](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster)

### Nice-to-have

- [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [Polaris — Best Practices Validation](https://github.com/FairwindsOps/polaris)
- [Kubescape — Security Scanner](https://github.com/kubescape/kubescape)

### Deep-dive

- [CNCF Cloud Native Security Whitepaper](https://github.com/cncf/tag-security/blob/main/security-whitepaper/v2/cloud-native-security-whitepaper.md)
- [NSA/CISA Kubernetes Hardening Guide](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF)
- [SRE Book — Chapter 26: Data Integrity](https://sre.google/sre-book/data-integrity/)

