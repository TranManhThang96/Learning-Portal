# Day 35: Deployment Strategies — Document

## 1. Deployment Strategy Comparison Matrix

| Tiêu chí | Recreate | Rolling Update | Blue-Green | Canary | Feature Flag |
|----------|---------|---------------|-----------|--------|-------------|
| **Downtime** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Rollback speed** | Slow (2-5 min) | Medium (1-3 min) | Instant (< 10s) | Fast (< 30s) | Instant (< 1s) |
| **Resource overhead** | 0% | +10-25% temp | +100% perm | +10% temp | 0% |
| **Complexity** | Very Low | Low | Medium | High | High (code) |
| **Blast radius** | 100% instant | Gradual | 100% at switch | 5-25% initial | Configurable |
| **Two versions co-exist** | No | Yes | Yes (briefly) | Yes | Yes |
| **DB migration compat** | Not needed | Required | Required | Required | Required |
| **Traffic control** | None | Pod-based | All-or-nothing | Weight-based | User-based |
| **Monitoring need** | Low | Medium | Medium | High | High |
| **K8s native** | ✅ | ✅ | ⚠️ Manual | ⚠️ Manual/Argo | ❌ Code-level |
| **Best for** | Dev/test | Most services | Critical with instant rollback | Gradual validation | Per-user control |

## 2. Kubernetes Deployment Strategy Cheat Sheet

### Rolling Update Configuration

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1          # Max extra pods during rollout
      maxUnavailable: 0     # Zero downtime
  minReadySeconds: 10       # Wait 10s before considering ready
  progressDeadlineSeconds: 300  # Timeout for rollout
  revisionHistoryLimit: 10   # Keep last 10 ReplicaSets for rollback
```

### Rolling Update Parameter Guide

| maxSurge | maxUnavailable | Behavior | Use case |
|----------|---------------|----------|---------|
| 1 | 0 | Safest: always maintain capacity | Production critical |
| 25% | 25% | Balanced: fast with some disruption | General services |
| 0 | 1 | No extra resources: replace one-by-one | Resource constrained |
| 100% | 0 | Fastest: double pods then drain old | Non-critical, speed priority |

### Kubectl Rollout Commands

```bash
# Status
kubectl rollout status deployment/<name>
kubectl rollout status deployment/<name> --timeout=5m

# History
kubectl rollout history deployment/<name>
kubectl rollout history deployment/<name> --revision=3

# Rollback
kubectl rollout undo deployment/<name>                    # Previous version
kubectl rollout undo deployment/<name> --to-revision=2    # Specific version

# Pause/Resume (for manual canary-like control)
kubectl rollout pause deployment/<name>
kubectl rollout resume deployment/<name>

# Restart (trigger new rollout with same image)
kubectl rollout restart deployment/<name>
```

## 3. Blue-Green Implementation Patterns

### Pattern 1: Service Selector Switch

```bash
# Deploy blue + green
# Service selector: version=blue

# Switch to green:
kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback:
kubectl patch service myapp -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Pattern 2: Ingress Path Switch

```yaml
# Switch at Ingress level
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
spec:
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp-green  # Change to myapp-blue for rollback
                port:
                  number: 80
```

### Pattern 3: DNS Switch

```bash
# External DNS change (slow — TTL dependent)
# Only use when no other option
# TTL should be low (30-60 seconds)
```

## 4. Canary Implementation Patterns

### Pattern 1: Kubernetes Native (Pod-based)

```bash
# Traffic split based on pod ratio
# 10 stable + 1 canary = ~9% canary traffic
kubectl scale deployment myapp-stable --replicas=9
kubectl scale deployment myapp-canary --replicas=1
```

### Pattern 2: Argo Rollouts (Weight-based)

```yaml
apiVersion: argoproj.github.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  strategy:
    canary:
      steps:
        - setWeight: 5
        - pause: {duration: 5m}
        - setWeight: 25
        - pause: {duration: 10m}
        - setWeight: 50
        - pause: {duration: 10m}
        - setWeight: 100
      canaryService: myapp-canary
      stableService: myapp-stable
      trafficRouting:
        nginx:
          stableIngress: myapp-ingress
```

### Pattern 3: Istio Traffic Splitting

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  http:
    - route:
        - destination:
            host: myapp
            subset: stable
          weight: 95
        - destination:
            host: myapp
            subset: canary
          weight: 5
```

## 5. Database Migration Compatibility Reference

### Expand-and-Contract Pattern

```
Phase 1: EXPAND
┌─────────────┐                ┌─────────────────────────────┐
│ Code v1     │  ──deploy──▶   │ Code v1.5                   │
│ reads: name │                │ reads: name + first_name    │
│ writes: name│                │ writes: name + first_name   │
└─────────────┘                └─────────────────────────────┘
                               Schema: name + first_name (nullable)

Phase 2: MIGRATE
- Backfill first_name from name for all rows
- Both v1 and v1.5 still work

Phase 3: CONTRACT
┌─────────────────────────────┐
│ Code v2                     │
│ reads: first_name           │
│ writes: first_name          │
└─────────────────────────────┘
Schema: first_name (NOT NULL), drop name column
```

### Safe vs Unsafe Migrations

| Operation | Safe? | Notes |
|-----------|-------|-------|
| ADD column (nullable) | ✅ | Old code ignores new column |
| ADD column (NOT NULL + default) | ✅ | Old code ignores, default fills |
| DROP column | ❌ | Old code crashes reading dropped column |
| RENAME column | ❌ | Both old and new code break |
| CHANGE column type | ⚠️ | Depends on compatibility |
| ADD index | ✅ | Use CONCURRENTLY in PostgreSQL |
| DROP index | ✅ | Old code works without index |
| ADD table | ✅ | Old code doesn't know about it |
| DROP table | ❌ | Old code crashes |

### Migration Execution Order

```
Scenario: Code needs NEW column

1. Deploy migration: ADD COLUMN (nullable)
2. Deploy new code (reads/writes new column)
3. Backfill old rows
4. (Optional) Add NOT NULL constraint

Scenario: Code REMOVES old column

1. Deploy new code (stops reading old column)
2. Verify no code reads old column
3. Deploy migration: DROP COLUMN
```

## 6. Health Check Templates

### HTTP Service

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
  successThreshold: 1

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
  successThreshold: 1

startupProbe:
  httpGet:
    path: /health/live
    port: 8080
  periodSeconds: 2
  failureThreshold: 30    # 30 × 2s = 60s max startup
```

### gRPC Service

```yaml
readinessProbe:
  grpc:
    port: 50051
  initialDelaySeconds: 5
  periodSeconds: 10

livenessProbe:
  grpc:
    port: 50051
  initialDelaySeconds: 15
  periodSeconds: 20
```

### Worker / Queue Consumer

```yaml
livenessProbe:
  exec:
    command:
      - /bin/sh
      - -c
      - "test $(( $(date +%s) - $(cat /tmp/last_heartbeat) )) -lt 60"
  periodSeconds: 30
  failureThreshold: 3
```

### Health Endpoint Design

```go
// /health/live — am I alive? (basic process check)
func liveHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "alive"})
}

// /health/ready — am I ready to serve traffic?
func readyHandler(w http.ResponseWriter, r *http.Request) {
    // Check database
    if err := db.Ping(); err != nil {
        w.WriteHeader(http.StatusServiceUnavailable)
        json.NewEncoder(w).Encode(map[string]string{
            "status": "not ready",
            "reason": "database unavailable",
        })
        return
    }
    // Check cache
    if err := redis.Ping(); err != nil {
        w.WriteHeader(http.StatusServiceUnavailable)
        return
    }
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ready"})
}
```

## 7. Deployment Runbook Template

```markdown
# Deployment Runbook: [Service Name]

## Service Info
- Service: [name]
- Strategy: [rolling/canary/blue-green]
- Criticality: [critical/high/medium/low]
- SLA: [99.9%]
- On-call contact: [name/channel]

## Pre-deploy Checklist
- [ ] CI pipeline green (all tests pass)
- [ ] Security scan: 0 CRITICAL CVEs
- [ ] Change reviewed and approved (PR merged)
- [ ] Database migration tested on staging
- [ ] Staging deployment verified (running > 1 hour)
- [ ] On-call engineer notified
- [ ] Not during: [peak hours / freeze window]
- [ ] Rollback plan reviewed
- [ ] Monitoring dashboard open

## Deploy Steps
1. [Step 1: specific command or action]
2. [Step 2: monitoring check]
3. [Step N: final verification]

## Monitoring During Deploy
Dashboard: [URL]
Key metrics:
- Error rate: < [threshold]%
- Latency p99: < [threshold]ms
- Business metric: [metric] > [threshold]

## Rollback Criteria
Auto-rollback if:
- Error rate > [X]% for [Y] minutes
- Latency p99 > [X]ms for [Y] minutes
- Health check fails [X] consecutive times

## Rollback Steps
1. [Command to rollback]
2. [Verify rollback successful]
3. [Notify team]

## Post-deploy Verification
- [ ] Metrics normal for 30 minutes
- [ ] No error logs
- [ ] Business metrics normal
- [ ] Notify team: deployment successful

## Escalation
If rollback fails:
1. Page on-call: [number/pager]
2. Incident channel: [#channel]
3. Escalation: [manager/VP Eng]
```

## 8. Feature Flag Best Practices

```
DO:
✅ Use server-side evaluation (not client-side)
✅ Set flag expiry dates
✅ Clean up flags within 2 weeks of full rollout
✅ Log flag evaluations for debugging
✅ Have a kill switch for every feature flag
✅ Test both flag states (on/off) in CI
✅ Use typed flags (boolean, string, number, JSON)

DON'T:
❌ Nest feature flags (flag inside flag)
❌ Use flags for permanent configuration (use config instead)
❌ Leave flags in code indefinitely (tech debt)
❌ Couple flags to deployment (flag ≠ deploy version)
❌ Trust client-side flag evaluation for security
❌ Create flags without an owner
❌ Skip testing the "off" path
```

