# Day 24: Document — Production-ready Kubernetes Checklist

## 1. Complete Production Checklist (Printable)

### Cluster

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| C1 | HA Control Plane (≥ 3 nodes) | 🔴 Critical | Platform | ☐ |
| C2 | etcd backup automated + tested | 🔴 Critical | Platform | ☐ |
| C3 | K8s version N-1 or newer | 🟡 Important | Platform | ☐ |
| C4 | Node pool strategy defined | 🟡 Important | Platform | ☐ |
| C5 | Cluster monitoring (API server, etcd, nodes) | 🔴 Critical | Platform | ☐ |
| C6 | Certificate auto-renewal | 🟡 Important | Platform | ☐ |
| C7 | Upgrade runbook documented | 🟡 Important | Platform | ☐ |
| C8 | Admission controller deployed | 🟡 Important | Platform | ☐ |
| C9 | Audit logging enabled | 🟡 Important | Platform | ☐ |
| C10 | etcd encryption at rest | 🟡 Important | Platform | ☐ |

### Workload

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| W1 | Resource requests (CPU + memory) | 🔴 Critical | App Team | ☐ |
| W2 | Resource limits (memory required, CPU optional) | 🔴 Critical | App Team | ☐ |
| W3 | Liveness probe | 🔴 Critical | App Team | ☐ |
| W4 | Readiness probe | 🔴 Critical | App Team | ☐ |
| W5 | Startup probe (slow-start apps) | 🟢 Nice-to-have | App Team | ☐ |
| W6 | PodDisruptionBudget | 🟡 Important | App Team | ☐ |
| W7 | Topology spread constraints | 🟢 Nice-to-have | App Team | ☐ |
| W8 | Graceful shutdown (preStop + SIGTERM) | 🟡 Important | App Team | ☐ |
| W9 | Replicas ≥ 2 | 🔴 Critical | App Team | ☐ |
| W10 | RollingUpdate strategy configured | 🟡 Important | App Team | ☐ |
| W11 | Labels: app, team, environment, version | 🟡 Important | App Team | ☐ |
| W12 | Anti-affinity (spread across nodes) | 🟢 Nice-to-have | App Team | ☐ |

### Security

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| S1 | Dedicated ServiceAccount | 🔴 Critical | App Team | ☐ |
| S2 | RBAC least privilege | 🔴 Critical | Shared | ☐ |
| S3 | Pod Security Standards (baseline+) | 🔴 Critical | Platform | ☐ |
| S4 | NetworkPolicy (default deny) | 🔴 Critical | Shared | ☐ |
| S5 | Non-root container (runAsNonRoot) | 🔴 Critical | App Team | ☐ |
| S6 | Read-only root filesystem | 🟡 Important | App Team | ☐ |
| S7 | Image scanning in CI/CD | 🔴 Critical | Shared | ☐ |
| S8 | Trusted registry only | 🟡 Important | Platform | ☐ |
| S9 | Secret encryption at rest | 🟡 Important | Platform | ☐ |
| S10 | Secret rotation strategy | 🟢 Nice-to-have | Shared | ☐ |
| S11 | Admission policies (block privileged, require limits) | 🟡 Important | Platform | ☐ |
| S12 | No privileged containers | 🔴 Critical | Platform | ☐ |
| S13 | Drop all capabilities | 🟡 Important | App Team | ☐ |
| S14 | No hostNetwork/hostPID/hostIPC | 🔴 Critical | Platform | ☐ |

### Observability

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| O1 | Application metrics (RED: Rate, Error, Duration) | 🔴 Critical | App Team | ☐ |
| O2 | Infrastructure metrics (CPU, memory, disk, network) | 🔴 Critical | Platform | ☐ |
| O3 | Structured logging (JSON) | 🟡 Important | App Team | ☐ |
| O4 | Log aggregation (Loki/ELK) | 🟡 Important | Platform | ☐ |
| O5 | Distributed tracing (OpenTelemetry) | 🟢 Nice-to-have | Shared | ☐ |
| O6 | Service dashboard | 🔴 Critical | App Team | ☐ |
| O7 | Alerting rules defined | 🔴 Critical | App Team | ☐ |
| O8 | SLI/SLO defined | 🟡 Important | Shared | ☐ |
| O9 | On-call rotation | 🟡 Important | App Team | ☐ |

### Backup & DR

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| B1 | etcd backup (≥ daily) | 🔴 Critical | Platform | ☐ |
| B2 | PV/data backup | 🔴 Critical | Shared | ☐ |
| B3 | Namespace resource backup (Velero) | 🟡 Important | Platform | ☐ |
| B4 | Backup restore tested (monthly) | 🔴 Critical | Shared | ☐ |
| B5 | Offsite backup copy | 🟡 Important | Platform | ☐ |
| B6 | Retention policy defined | 🟡 Important | Shared | ☐ |
| B7 | DR plan documented (RPO/RTO) | 🔴 Critical | Shared | ☐ |
| B8 | DR drill (quarterly) | 🟢 Nice-to-have | Shared | ☐ |

### Cost

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| $1 | Resource right-sizing (requests ≈ P95 usage) | 🟡 Important | App Team | ☐ |
| $2 | Autoscaling configured (HPA/VPA) | 🟡 Important | App Team | ☐ |
| $3 | Cost allocation labels (team, cost-center) | 🟡 Important | Shared | ☐ |
| $4 | Unused resource cleanup | 🟢 Nice-to-have | Shared | ☐ |
| $5 | Spot/preemptible for non-critical | 🟢 Nice-to-have | Platform | ☐ |
| $6 | Cost visibility dashboard | 🟡 Important | Platform | ☐ |

### Release

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| R1 | CI/CD pipeline | 🔴 Critical | App Team | ☐ |
| R2 | Deployment strategy (rolling/canary) | 🔴 Critical | App Team | ☐ |
| R3 | Rollback plan (1-command) | 🔴 Critical | App Team | ☐ |
| R4 | Post-deploy smoke tests | 🟡 Important | App Team | ☐ |
| R5 | Quality gates (tests + scans pass) | 🟡 Important | Shared | ☐ |
| R6 | GitOps workflow | 🟢 Nice-to-have | Platform | ☐ |

### Runbook

| # | Item | Severity | Owner | Status |
|---|------|----------|-------|--------|
| RB1 | Service down runbook | 🔴 Critical | App Team | ☐ |
| RB2 | High latency runbook | 🔴 Critical | App Team | ☐ |
| RB3 | Database issues runbook | 🟡 Important | App Team | ☐ |
| RB4 | Scaling runbook | 🟡 Important | App Team | ☐ |
| RB5 | Incident response process | 🔴 Critical | Shared | ☐ |
| RB6 | Escalation path defined | 🔴 Critical | Shared | ☐ |
| RB7 | Post-incident review process | 🟡 Important | Shared | ☐ |

---

## 2. Maturity Assessment Scoring Template

### Scoring Guide

| Score | Level | Description |
|-------|-------|-------------|
| 0 | Not Started | Item không tồn tại |
| 1 | Partial | Item có nhưng không đầy đủ hoặc chưa test |
| 2 | Complete | Item đầy đủ, tested, documented |
| 3 | Automated | Item automated, monitored, alerted |

### Scoring Sheet

| Category | Total Items | Score (0-3 each) | Max | % |
|----------|------------|-------------------|-----|---|
| Cluster | 10 | ___ | 30 | ___ |
| Workload | 12 | ___ | 36 | ___ |
| Security | 14 | ___ | 42 | ___ |
| Observability | 9 | ___ | 27 | ___ |
| Backup & DR | 8 | ___ | 24 | ___ |
| Cost | 6 | ___ | 18 | ___ |
| Release | 6 | ___ | 18 | ___ |
| Runbook | 7 | ___ | 21 | ___ |
| **TOTAL** | **72** | ___ | **216** | ___ |

### Maturity Levels

| Score Range | Maturity | Action |
|-------------|----------|--------|
| 0-25% | Level 0: Ad-hoc | Urgent: fix critical items |
| 25-50% | Level 1: Basic | Focus on security + reliability |
| 50-75% | Level 2: Defined | Add observability + automation |
| 75-90% | Level 3: Managed | Optimize cost + advanced features |
| 90-100% | Level 4: Optimized | Continuous improvement |

---

## 3. Gap Analysis Template

```markdown
# Gap Analysis Report

## Service: [name]
## Namespace: [namespace]
## Date: [YYYY-MM-DD]
## Auditor: [name]

## Summary
- Items audited: [N]
- Passed: [X] ([Y]%)
- Failed: [Z]
  - Critical: [A]
  - Important: [B]
  - Nice-to-have: [C]

## Critical Gaps (Must fix before production)

| # | Gap | Category | Current State | Required State | Effort |
|---|-----|----------|--------------|----------------|--------|
| 1 | No resource limits | Workload | Missing | CPU+memory set | 30 min |
| 2 | No health probes | Workload | Missing | Liveness+readiness | 30 min |
| 3 | Single replica | Workload | 1 | ≥ 2 | 5 min |
| 4 | No NetworkPolicy | Security | Open | Default deny | 45 min |
| 5 | Running as root | Security | root | non-root | 15 min |

## Important Gaps (Fix within 2 weeks)

| # | Gap | Category | Effort |
|---|-----|----------|--------|
| 6 | No PDB | Workload | 15 min |
| 7 | No labels | Workload | 10 min |
| ... | ... | ... | ... |

## Nice-to-have Gaps (Fix within 1 month)

| # | Gap | Category | Effort |
|---|-----|----------|--------|
| ... | ... | ... | ... |

## Remediation Plan

### Phase 1: Critical (Week 1)
Total effort: ~2 hours
1. Add resource requests/limits
2. Add health probes
3. Increase replicas
4. Add NetworkPolicy
5. Set non-root

### Phase 2: Important (Week 2-3)
Total effort: ~4 hours
6. Add PDB
7. Add labels
8. RBAC review
...

### Phase 3: Nice-to-have (Month 2)
...
```

---

## 4. Priority Matrix (Impact vs Effort)

```
                        LOW EFFORT              HIGH EFFORT
                    ┌──────────────────┬──────────────────┐
                    │                  │                  │
   HIGH IMPACT      │   QUICK WINS     │  MAJOR PROJECTS  │
                    │                  │                  │
                    │ • Resource limits│ • Service mesh   │
                    │ • Replicas ≥ 2   │ • Full tracing   │
                    │ • Labels         │ • GitOps setup   │
                    │ • Non-root       │ • DR drills      │
                    │                  │                  │
                    ├──────────────────┼──────────────────┤
                    │                  │                  │
   LOW IMPACT       │   FILL-INS       │     DEPRIORITIZE │
                    │                  │                  │
                    │ • Startup probe  │ • Custom metrics │
                    │ • Read-only FS   │ • Cost dashboard │
                    │ • Topology spread│ • Feature flags  │
                    │                  │                  │
                    └──────────────────┴──────────────────┘
```

---

## 5. Automated Audit Script

```bash
#!/bin/bash
# k8s-audit.sh — Audit a namespace against production checklist
# Usage: ./k8s-audit.sh <namespace>

set -euo pipefail

NS=${1:?Usage: $0 <namespace>}
PASS=0
FAIL=0
WARN=0

echo "==========================================="
echo " Kubernetes Production Readiness Audit"
echo " Namespace: $NS"
echo " Date: $(date)"
echo "==========================================="
echo ""

check() {
  local severity=$1 category=$2 item=$3 result=$4
  if [ "$result" = "PASS" ]; then
    echo "  ✅ [$severity] $category: $item"
    PASS=$((PASS+1))
  elif [ "$result" = "WARN" ]; then
    echo "  ⚠️  [$severity] $category: $item"
    WARN=$((WARN+1))
  else
    echo "  ❌ [$severity] $category: $item"
    FAIL=$((FAIL+1))
  fi
}

echo "--- WORKLOAD ---"

# W1: Resource requests
NO_REQ=$(kubectl get pods -n $NS -o json | jq '[.items[].spec.containers[] | select(.resources.requests==null or .resources.requests=={})] | length')
[ "$NO_REQ" -eq 0 ] && check "CRIT" "Workload" "Resource requests on all containers" "PASS" \
                      || check "CRIT" "Workload" "Resource requests missing on $NO_REQ containers" "FAIL"

# W2: Resource limits
NO_LIM=$(kubectl get pods -n $NS -o json | jq '[.items[].spec.containers[] | select(.resources.limits==null or .resources.limits=={})] | length')
[ "$NO_LIM" -eq 0 ] && check "CRIT" "Workload" "Resource limits on all containers" "PASS" \
                      || check "CRIT" "Workload" "Resource limits missing on $NO_LIM containers" "FAIL"

# W3: Liveness probe
NO_LIVE=$(kubectl get pods -n $NS -o json | jq '[.items[].spec.containers[] | select(.livenessProbe==null)] | length')
[ "$NO_LIVE" -eq 0 ] && check "CRIT" "Workload" "Liveness probe on all containers" "PASS" \
                       || check "CRIT" "Workload" "Liveness probe missing on $NO_LIVE containers" "FAIL"

# W4: Readiness probe
NO_READY=$(kubectl get pods -n $NS -o json | jq '[.items[].spec.containers[] | select(.readinessProbe==null)] | length')
[ "$NO_READY" -eq 0 ] && check "CRIT" "Workload" "Readiness probe on all containers" "PASS" \
                        || check "CRIT" "Workload" "Readiness probe missing on $NO_READY containers" "FAIL"

# W9: Replicas >= 2
SINGLE=$(kubectl get deployments -n $NS -o json | jq '[.items[] | select(.spec.replicas < 2)] | length')
[ "$SINGLE" -eq 0 ] && check "CRIT" "Workload" "All deployments have replicas >= 2" "PASS" \
                      || check "CRIT" "Workload" "$SINGLE deployments with single replica" "FAIL"

# W6: PDB
DEPLOYS=$(kubectl get deployments -n $NS --no-headers | wc -l)
PDBS=$(kubectl get pdb -n $NS --no-headers 2>/dev/null | wc -l)
[ "$PDBS" -ge "$DEPLOYS" ] && check "IMP" "Workload" "PDB exists for all deployments" "PASS" \
                             || check "IMP" "Workload" "PDB: $PDBS/$DEPLOYS deployments covered" "WARN"

echo ""
echo "--- SECURITY ---"

# S4: NetworkPolicy
NP=$(kubectl get networkpolicy -n $NS --no-headers 2>/dev/null | wc -l)
[ "$NP" -gt 0 ] && check "CRIT" "Security" "NetworkPolicy exists ($NP policies)" "PASS" \
                 || check "CRIT" "Security" "No NetworkPolicy in namespace" "FAIL"

# S5: Non-root
ROOT_PODS=$(kubectl get pods -n $NS -o json | jq '[.items[].spec.containers[] | select(.securityContext.runAsNonRoot!=true)] | length')
[ "$ROOT_PODS" -eq 0 ] && check "CRIT" "Security" "All containers run as non-root" "PASS" \
                         || check "CRIT" "Security" "$ROOT_PODS containers may run as root" "FAIL"

echo ""
echo "--- SERVICES ---"

# Endpoints check
EMPTY_EP=$(kubectl get endpoints -n $NS -o json | jq '[.items[] | select(.subsets==null or .subsets==[])] | length')
[ "$EMPTY_EP" -eq 0 ] && check "CRIT" "Service" "All services have endpoints" "PASS" \
                        || check "CRIT" "Service" "$EMPTY_EP services with no endpoints" "FAIL"

echo ""
echo "==========================================="
TOTAL=$((PASS+FAIL+WARN))
SCORE=$((PASS*100/(TOTAL > 0 ? TOTAL : 1)))
echo " Results: $PASS passed, $FAIL failed, $WARN warnings"
echo " Score: ${SCORE}%"
echo "==========================================="
```

---

## 6. Quick Reference — Security Context Template

```yaml
# Minimal secure container
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

## 7. Quick Reference — Probe Templates

```yaml
# HTTP service
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 3

# gRPC service
livenessProbe:
  grpc:
    port: 50051
  initialDelaySeconds: 15
  periodSeconds: 10

# TCP service (Redis, databases)
livenessProbe:
  tcpSocket:
    port: 6379
  initialDelaySeconds: 10
  periodSeconds: 10

# Command-based (custom check)
livenessProbe:
  exec:
    command: ["redis-cli", "ping"]
  initialDelaySeconds: 10
  periodSeconds: 10

# Startup probe (slow JVM apps)
startupProbe:
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
  # Total: 30 × 10 = 300s (5 min) to start
```

