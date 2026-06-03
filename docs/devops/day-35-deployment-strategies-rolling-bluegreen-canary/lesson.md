# Day 35: Deployment Strategies — Rolling, Blue-Green, Canary, Feature Flag

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt rõ ràng 6 deployment strategies**: Recreate, Rolling, Blue-Green, Canary, Feature Flag, Dark Launch — và biết khi nào dùng strategy nào.
2. **Implement được Rolling Update và Canary** trên Kubernetes với YAML manifests thực tế.
3. **Thiết kế được deployment strategy cho API service** bao gồm: rollback plan, database migration compatibility, health check integration.
4. **Hiểu được mối quan hệ** giữa deployment strategy và database schema migration — vì sao đây là thách thức lớn nhất.
5. **Nhận diện được risks và trade-offs** của mỗi strategy theo: downtime, cost, complexity, rollback speed.

---

## 2. Bối cảnh & Động lực

### Vấn đề: Deploy = Risk

Mỗi lần deploy là một cơ hội để production bị phá:
- **Bad code**: Bug logic, null pointer, unhandled error.
- **Config mismatch**: Wrong env vars, expired secrets.
- **Resource issue**: Container OOM, insufficient replicas.
- **Dependency failure**: Database schema incompatible, API contract broken.

Deployment strategy giúp **kiểm soát blast radius** — nếu deploy fail, bao nhiêu users bị ảnh hưởng?

```
Recreate:    100% users affected instantly
Rolling:     Gradually affects users (old + new co-exist)
Blue-Green:  0% affected until switch, then 100%
Canary:      5% → 25% → 100% (gradual)
Feature Flag: 0% → selected users → all (code-level)
```

### Liên hệ với developer

Deployment strategies giống các patterns bạn đã biết:
- **Rolling update** = database migration sử dụng `ALTER TABLE` online (không lock).
- **Blue-Green** = swap database replicas (failover).
- **Canary** = A/B testing cho infrastructure.
- **Feature Flag** = `if (featureEnabled("new_checkout")) { ... }` trong code.
- **Kill switch** = circuit breaker cho features.

---

## 3. Kiến thức nền tảng

### 3.1 Tổng quan 6 Strategies

| Strategy | Downtime | Rollback Speed | Cost | Complexity | Blast Radius |
|----------|----------|---------------|------|-----------|-------------|
| **Recreate** | ✅ Yes | Slow (redeploy) | Low | Very Low | 100% instantly |
| **Rolling Update** | ❌ No | Medium (rollback) | Low | Low | Gradual |
| **Blue-Green** | ❌ No | ⚡ Very Fast (switch) | High (2x resources) | Medium | 100% at switch |
| **Canary** | ❌ No | ⚡ Fast (route away) | Medium | High | 5-25% initial |
| **Feature Flag** | ❌ No | ⚡ Instant (toggle) | Low | High (code) | Configurable |
| **Dark Launch** | ❌ No | ⚡ Instant | Medium | High | 0% (shadow) |

### 3.2 Recreate Deployment

```
Before:  [v1] [v1] [v1]
Step 1:  [___] [___] [___]  ← All pods terminated (DOWNTIME)
Step 2:  [v2] [v2] [v2]     ← All pods started
```

**Kubernetes config**:
```yaml
spec:
  strategy:
    type: Recreate
```

**Khi nào dùng**:
- Ứng dụng không thể chạy 2 versions đồng thời (database schema lock).
- Dev/test environments (downtime chấp nhận được).
- Batch jobs, workers không serving traffic.

**Khi nào KHÔNG dùng**: Production services có users.

### 3.3 Rolling Update (Kubernetes default)

```
Step 0:  [v1] [v1] [v1] [v1]
Step 1:  [v1] [v1] [v1] [v2]  ← 1 pod mới lên
Step 2:  [v1] [v1] [v2] [v2]  ← 2 pods mới
Step 3:  [v1] [v2] [v2] [v2]  ← 3 pods mới
Step 4:  [v2] [v2] [v2] [v2]  ← hoàn thành
```

**Kubernetes config**:
```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Tối đa thêm 1 pod (total 5)
      maxUnavailable: 0   # Không pod nào bị unavailable
```

**Key parameters**:

| Parameter | Giải thích | Production recommendation |
|-----------|-----------|-------------------------|
| `maxSurge` | Số pods thêm vượt replicas | 1 hoặc 25% |
| `maxUnavailable` | Số pods được phép unavailable | 0 (zero downtime) |
| `minReadySeconds` | Chờ bao lâu trước khi coi pod là ready | 10-30s |
| `progressDeadlineSeconds` | Timeout cho rollout | 300-600s |

**Trade-offs**:
- ✅ Zero downtime, low cost (không cần 2x resources).
- ⚠️ V1 và v2 chạy đồng thời — API phải backward compatible.
- ⚠️ Rollback mất thời gian (rolling back = rolling forward with old version).

### 3.4 Blue-Green Deployment

```mermaid
graph LR
    LB[Load Balancer] -->|100% traffic| BG{Active?}
    BG -->|Blue active| B[Blue: v1<br/>4 pods]
    BG -.->|standby| G[Green: v2<br/>4 pods]
    
    style B fill:#4fc3f7
    style G fill:#81c784
```

**Sau switch**:
```mermaid
graph LR
    LB[Load Balancer] -->|100% traffic| BG{Active?}
    BG -.->|standby| B[Blue: v1<br/>4 pods]
    BG -->|Green active| G[Green: v2<br/>4 pods]
    
    style B fill:#4fc3f7
    style G fill:#81c784
```

**Kubernetes implementation** (dùng Service selector):

```yaml
# Blue deployment (current)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
spec:
  replicas: 4
  selector:
    matchLabels:
      app: myapp
      version: blue
  template:
    metadata:
      labels:
        app: myapp
        version: blue
    spec:
      containers:
        - name: myapp
          image: myapp:v1.0.0

---
# Green deployment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 4
  selector:
    matchLabels:
      app: myapp
      version: green
  template:
    metadata:
      labels:
        app: myapp
        version: green
    spec:
      containers:
        - name: myapp
          image: myapp:v2.0.0

---
# Service — switch between blue/green
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: blue   # ← Change to "green" to switch
  ports:
    - port: 80
      targetPort: 8080
```

**Switch traffic**:
```bash
# Switch từ blue sang green
kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback: switch lại blue
kubectl patch service myapp -p '{"spec":{"selector":{"version":"blue"}}}'
```

**Trade-offs**:
- ✅ Instant rollback (switch selector).
- ✅ Full testing trên green trước khi switch.
- ⚠️ 2x resources (both deployments chạy đồng thời).
- ⚠️ Database phải compatible cả 2 versions.
- ⚠️ Stateful sessions bị mất khi switch.

### 3.5 Canary Release

```
Step 0:  LB ──→ [v1×10 pods]               (100% v1)
Step 1:  LB ──→ [v1×10 pods] + [v2×1 pod]  (91% v1, 9% v2)
Step 2:  LB ──→ [v1×7 pods] + [v2×3 pods]  (70% v1, 30% v2)
Step 3:  LB ──→ [v1×5 pods] + [v2×5 pods]  (50% v1, 50% v2)
Step 4:  LB ──→ [v2×10 pods]               (100% v2)
```

**Kubernetes implementation** (basic — dùng 2 deployments):

```yaml
# Stable deployment (v1)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-stable
spec:
  replicas: 9
  selector:
    matchLabels:
      app: myapp
      track: stable
  template:
    metadata:
      labels:
        app: myapp
        track: stable
    spec:
      containers:
        - name: myapp
          image: myapp:v1.0.0

---
# Canary deployment (v2)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-canary
spec:
  replicas: 1    # 10% traffic (1 of 10 total pods)
  selector:
    matchLabels:
      app: myapp
      track: canary
  template:
    metadata:
      labels:
        app: myapp
        track: canary
    spec:
      containers:
        - name: myapp
          image: myapp:v2.0.0

---
# Service routes to BOTH (same app label)
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp   # Matches both stable and canary
  ports:
    - port: 80
      targetPort: 8080
```

**Canary promotion**:
```bash
# Step 1: Deploy canary (10%)
kubectl scale deployment myapp-canary --replicas=1
# Monitor error rates, latency for 15 minutes

# Step 2: Increase canary (30%)
kubectl scale deployment myapp-stable --replicas=7
kubectl scale deployment myapp-canary --replicas=3

# Step 3: Full promotion (100%)
kubectl set image deployment/myapp-stable myapp=myapp:v2.0.0
kubectl scale deployment myapp-stable --replicas=10
kubectl scale deployment myapp-canary --replicas=0
```

**Limitations**: Kubernetes Service round-robin chỉ cho traffic distribution dựa trên pod count. Cho finer control (5%, 10%, etc.) → dùng **Argo Rollouts** hoặc **Istio** (sẽ học Day 36).

### 3.6 Feature Flag

```
Code-level deployment strategy:

if (featureFlags.isEnabled("new_checkout", user)) {
    return newCheckoutFlow(user);
} else {
    return oldCheckoutFlow(user);
}
```

**Feature flag types**:

| Type | Purpose | Lifetime | Example |
|------|---------|----------|---------|
| **Release flag** | Gradual rollout | Days-weeks | New UI component |
| **Experiment flag** | A/B testing | Weeks | Button color test |
| **Ops flag** | Kill switch | Permanent | Circuit breaker |
| **Permission flag** | User segmentation | Permanent | Premium features |

**Feature flag tools**:
- **LaunchDarkly** — SaaS, enterprise-grade.
- **Unleash** — open-source, self-hosted.
- **Flagsmith** — open-source + SaaS.
- **Custom** — config file, database, environment variable.

**Trade-offs**:
- ✅ Deploy code anytime, enable feature separately.
- ✅ Instant rollback (toggle off).
- ✅ Gradual rollout per user/region.
- ⚠️ Code complexity (if/else everywhere).
- ⚠️ Technical debt (old flags not cleaned up).
- ⚠️ Testing matrix explosion (2^n combinations).

### 3.7 Dark Launch

```
User Request ──→ [v1 Application] ──→ Response to user
                       │
                       └──→ [v2 Application] ──→ Response logged (not returned)
                            (shadow traffic)
```

Chạy v2 với production traffic thật nhưng **không trả response cho user**. Dùng để:
- Test performance của v2 dưới production load.
- Validate business logic (compare v1 vs v2 responses).
- Load test mà không cần synthetic traffic.

---

## 4. Deep Dive

### 4.1 Database Migration Compatibility

**Đây là thách thức lớn nhất** của deployment strategies. Khi v1 và v2 chạy đồng thời:

```
v1 expects: users(id, name, email)
v2 expects: users(id, first_name, last_name, email)

Rolling/Canary: v1 + v2 chạy cùng lúc → v1 crash vì column 'name' bị rename!
```

**Solution: Expand-and-Contract Pattern**:

```
Phase 1 (Expand): Add new columns, keep old ones
  Schema: users(id, name, first_name, last_name, email)
  Deploy v1.5: writes to BOTH name AND first_name/last_name
  
Phase 2 (Migrate): Backfill old rows
  Run data migration: populate first_name/last_name from name
  
Phase 3 (Contract): Remove old column  
  Deploy v2: reads/writes only first_name/last_name
  Schema: users(id, first_name, last_name, email)
```

**Rules**:
1. **NEVER rename a column** trong rolling/canary deploy.
2. **NEVER remove a column** while old version is still running.
3. **ALWAYS add new columns** as nullable or with defaults.
4. **ALWAYS deploy code change BEFORE schema change** (nếu code mới cần column mới).
5. **ALWAYS multi-phase** migrations: expand → migrate → contract.

### 4.2 Health Check Integration

Deployment strategy phụ thuộc vào health checks chính xác:

```yaml
spec:
  containers:
    - name: myapp
      livenessProbe:    # Pod alive? Restart nếu fail
        httpGet:
          path: /health/live
          port: 8080
        initialDelaySeconds: 10
        periodSeconds: 10
        failureThreshold: 3
      
      readinessProbe:   # Pod sẵn sàng nhận traffic? Remove khỏi Service nếu fail
        httpGet:
          path: /health/ready
          port: 8080
        initialDelaySeconds: 5
        periodSeconds: 5
        failureThreshold: 3
      
      startupProbe:     # Pod đã start xong? Chỉ check lúc startup
        httpGet:
          path: /health/live
          port: 8080
        initialDelaySeconds: 0
        periodSeconds: 2
        failureThreshold: 30  # 30 × 2s = 60s max startup time
```

**Tại sao health check quan trọng cho deployment**:
- `readinessProbe` fail → pod bị remove khỏi Service endpoints → không nhận traffic.
- Rolling update chờ readiness trước khi tiếp tục → **bad readiness = bad rollout**.
- Canary dùng readiness để detect failures → auto-rollback.

### 4.3 Deployment Strategy Decision Framework

```mermaid
graph TB
    A[Choose Strategy] --> B{Downtime OK?}
    B -->|Yes| C[Recreate]
    B -->|No| D{Need instant rollback?}
    
    D -->|Yes| E{Budget for 2x resources?}
    D -->|No| F[Rolling Update]
    
    E -->|Yes| G[Blue-Green]
    E -->|No| H{Need gradual rollout?}
    
    H -->|Yes| I[Canary]
    H -->|No| J{Per-user control?}
    
    J -->|Yes| K[Feature Flag]
    J -->|No| F
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Strategy Selection by Context

| Context | Recommended Strategy | Lý do |
|---------|---------------------|------|
| **Dev/test** | Recreate | Nhanh, đơn giản, downtime ok |
| **Internal tools** | Rolling Update | Zero downtime enough, low cost |
| **Public API** | Canary | Gradual rollout, detect issues early |
| **E-commerce checkout** | Blue-Green + Feature Flag | Instant rollback, per-user control |
| **Mobile app backend** | Canary | Multiple client versions in the wild |
| **Database migration** | Rolling + Expand-Contract | Zero downtime + schema compatibility |
| **Critical financial** | Blue-Green + manual approval | Full validation before switch |

### 5.2 Best Practices

1. **Luôn có rollback plan** trước khi deploy.
2. **Health checks phải accurate** — readinessProbe phải kiểm tra dependencies (DB, cache).
3. **`minReadySeconds`** ít nhất 10-30s — chờ service warm up.
4. **Database migrations luôn backward-compatible** — expand-contract pattern.
5. **Monitor metrics ngay sau deploy**: error rate, latency p99, business metrics.
6. **Feature flags cần cleanup schedule** — remove flags sau 2 weeks stable.
7. **Canary cần automated analysis** — manual monitoring không scale (Day 36).
8. **Never deploy Friday PM** (unless team very mature).

### 5.3 Anti-patterns

| Anti-pattern | Risk | Fix |
|-------------|------|-----|
| Deploy without health checks | Bad pods nhận traffic | Add readiness + liveness probes |
| Database migration break backward compat | Old pods crash | Expand-contract pattern |
| Canary without monitoring | Don't know if canary is failing | Automated metric analysis |
| Feature flags never cleaned up | Code spaghetti, dead branches | Flag expiry, mandatory cleanup |
| Blue-Green without traffic drain | Active connections dropped | Graceful drain (preStop hook) |
| Rollback = re-deploy forward | Slow recovery | True rollback (git revert, or keep old version ready) |

---

## 6. Performance & Scalability ⭐

### 6.1 Rollback Speed Comparison

| Strategy | Rollback Method | Time to Rollback | Data Risk |
|----------|----------------|-----------------|-----------|
| Recreate | Redeploy old version | 2-5 min | None |
| Rolling | `kubectl rollout undo` | 1-3 min | None |
| Blue-Green | Switch service selector | < 10 sec | None |
| Canary | Scale canary to 0 | < 30 sec | None |
| Feature Flag | Toggle flag off | < 1 sec | None |

### 6.2 Resource Overhead

| Strategy | Extra Resources | Cost Impact |
|----------|----------------|-------------|
| Recreate | None (downtime instead) | 0% |
| Rolling | maxSurge pods temporarily | +10-25% temporary |
| Blue-Green | Full duplicate environment | +100% permanent |
| Canary | Small canary pods | +10% temporary |
| Feature Flag | None (same deployment) | 0% |

### 6.3 Scaling Considerations

- **Rolling Update + HPA**: HPA vẫn hoạt động trong rollout. Nếu load tăng, scale up trước rồi rollout.
- **Blue-Green + auto-scaling**: Cả blue và green cần auto-scaling riêng — cost cao.
- **Canary + traffic splitting**: Dùng Istio/Argo Rollouts cho precise traffic control thay vì pod count.

---

## 7. Security & Reliability Considerations

### 7.1 Security

| Concern | Mitigation |
|---------|-----------|
| Canary exposes new code to production traffic | Canary cùng security posture với stable |
| Blue-Green: old version vẫn chạy | Shut down blue sau khi green stable |
| Feature flags can be exploited | Server-side evaluation, không trust client |
| Rollback re-exposes patched vulnerability | Flag security patches — block rollback past security fix |

### 7.2 Reliability Patterns

```yaml
# PodDisruptionBudget — đảm bảo luôn có pods available
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: myapp-pdb
spec:
  minAvailable: 2    # Luôn 2 pods chạy
  selector:
    matchLabels:
      app: myapp

---
# Graceful shutdown
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: myapp
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]
          # sleep 5 giúp Service endpoint update trước khi pod terminate
```

---

## 8. Hands-on Example

### Rolling Update trên Kubernetes

#### Bước 1: Tạo cluster và deploy v1

```bash
# Tạo cluster
kind create cluster --name deploy-lab

# Deploy v1
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
spec:
  replicas: 4
  selector:
    matchLabels:
      app: webapp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: webapp
    spec:
      containers:
        - name: webapp
          image: nginx:1.24
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 2
            periodSeconds: 3
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: webapp
spec:
  selector:
    app: webapp
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
EOF

kubectl rollout status deployment/webapp
kubectl get pods -l app=webapp
```

Expected output:
```
deployment "webapp" successfully rolled out
NAME                      READY   STATUS    RESTARTS   AGE
webapp-xxx-a1b2c          1/1     Running   0          30s
webapp-xxx-d3e4f          1/1     Running   0          30s
webapp-xxx-g5h6i          1/1     Running   0          30s
webapp-xxx-j7k8l          1/1     Running   0          30s
```

#### Bước 2: Rolling update lên v2

```bash
# Watch pods real-time (terminal 1)
kubectl get pods -l app=webapp -w &

# Update image (trigger rolling update)
kubectl set image deployment/webapp webapp=nginx:1.25

# Watch rollout progress
kubectl rollout status deployment/webapp
```

Expected output:
```
webapp-xxx-old1   1/1   Running       0   2m
webapp-xxx-old2   1/1   Running       0   2m
webapp-xxx-old3   1/1   Running       0   2m
webapp-xxx-old4   1/1   Running       0   2m
webapp-xxx-new1   0/1   Pending       0   0s     ← new pod starting
webapp-xxx-new1   1/1   Running       0   5s     ← new pod ready
webapp-xxx-old1   1/1   Terminating   0   2m     ← old pod terminating
webapp-xxx-new2   0/1   Pending       0   0s
...
webapp-xxx-new4   1/1   Running       0   15s    ← all new pods ready
```

#### Bước 3: Rollback

```bash
# Check rollout history
kubectl rollout history deployment/webapp

# Rollback to previous version
kubectl rollout undo deployment/webapp

# Verify
kubectl rollout status deployment/webapp
kubectl get pods -l app=webapp -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}'
# Should show nginx:1.24
```

#### Bước 4: Blue-Green Simulation

```bash
# Deploy "blue" (v1)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webapp-bg
      version: blue
  template:
    metadata:
      labels:
        app: webapp-bg
        version: blue
    spec:
      containers:
        - name: webapp
          image: nginx:1.24
          ports:
            - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webapp-bg
      version: green
  template:
    metadata:
      labels:
        app: webapp-bg
        version: green
    spec:
      containers:
        - name: webapp
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: webapp-bg
spec:
  selector:
    app: webapp-bg
    version: blue
  ports:
    - port: 80
      targetPort: 80
EOF

# Verify: traffic goes to blue
kubectl get endpoints webapp-bg

# Switch to green
kubectl patch service webapp-bg -p '{"spec":{"selector":{"version":"green"}}}'
echo "Switched to GREEN"

# Verify: traffic goes to green
kubectl get endpoints webapp-bg

# Rollback to blue (instant!)
kubectl patch service webapp-bg -p '{"spec":{"selector":{"version":"blue"}}}'
echo "Rolled back to BLUE"
```

#### Bước 5: Cleanup

```bash
kubectl delete deployment webapp webapp-blue webapp-green
kubectl delete service webapp webapp-bg
kind delete cluster --name deploy-lab
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Deployment Issues

| Issue | Symptom | Root Cause | Fix |
|-------|---------|-----------|-----|
| Rollout stuck | `kubectl rollout status` hangs | readinessProbe failing | Check probe, logs, image |
| 5xx during deploy | Error spike during rollout | Old/new versions incompatible | Backward-compatible APIs |
| Connection drops | TCP RST during switch | No graceful drain | Add preStop hook, terminationGracePeriodSeconds |
| Rollback fails | Old image pulled from registry fails | Image tag overwritten (mutable tag) | Use immutable tags (SHA) |
| Canary metrics wrong | Can't distinguish canary traffic | No labels/headers | Add version header, separate metrics |
| DB migration breaks v1 | Old pods crash after migration | Non-backward-compatible schema change | Expand-contract pattern |

### 9.2 Debug Commands

```bash
# Rollout status
kubectl rollout status deployment/<name>
kubectl rollout history deployment/<name>
kubectl rollout history deployment/<name> --revision=2

# Current state
kubectl get deployment <name> -o yaml | grep -A5 strategy
kubectl get replicasets -l app=<name>
kubectl describe deployment <name>

# Pod events
kubectl get events --sort-by='.lastTimestamp' | grep <name>
kubectl describe pod <pod-name>

# Rollback
kubectl rollout undo deployment/<name>
kubectl rollout undo deployment/<name> --to-revision=2

# Pause/Resume rollout
kubectl rollout pause deployment/<name>
kubectl rollout resume deployment/<name>
```

### 9.3 Production Case Study: Canary Catches Database Bug

#### Context
E-commerce platform, 15 microservices, daily deployments. Payment service v2.3 includes new "discount calculation" logic.

#### Deployment
- Canary: 10% traffic → payment-service v2.3.
- Monitoring: error rate, latency p99, business metrics (order count, revenue).

#### Symptom (caught at 10%)
- Error rate canary: 2.3% (vs stable 0.1%).
- Specific error: `ERROR: column "discount_type" does not exist`.
- Business metric: order completion rate canary 94% vs stable 99.5%.

#### Root Cause
- Migration added column `discount_type` but ran AFTER canary deployment.
- Canary pods queried `discount_type` → column not found → 500 error.
- Only 10% users affected thanks to canary.

#### Mitigation
1. Scale canary to 0 (< 30 seconds).
2. Run database migration.
3. Redeploy canary.
4. Monitor 30 minutes → metrics normal.
5. Promote to 100%.

#### Lesson Learned
1. Database migration MUST run BEFORE code deployment (if code needs new column).
2. Or, code must handle column missing gracefully (backward compatible).
3. Canary saved 90% of users from experiencing the bug.
4. Without canary: 100% users would see errors.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước

| Bài | Connection |
|-----|-----------|
| Day 11 | Kubernetes Deployment resource, update strategy |
| Day 18 | Resource requests/limits — set properly for deployment pods |
| Day 19 | HPA — autoscaling interacts with deployment strategy |
| Day 22 | Troubleshooting — debug failed deployments |
| Day 31 | GitOps — ArgoCD triggers deployments based on Git changes |
| Day 32 | CI/CD pipeline — deploy stage uses these strategies |

### Bài sau sẽ mở rộng

- **Day 36**: Progressive Delivery with Argo Rollouts / Flagger — automated canary analysis, metric-based promotion/rollback.
- **Day 37**: Artifact Registry, Image Signing — immutable artifacts used in deployments.
- **Day 46**: Service Mesh — Istio traffic splitting for fine-grained canary.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
- [Martin Fowler — Blue-Green Deployment](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Martin Fowler — Canary Release](https://martinfowler.com/bliki/CanaryRelease.html)

### Nice-to-have

- [Feature Toggles — Martin Fowler](https://martinfowler.com/articles/feature-toggles.html)
- [Database Migrations Done Right — expand-contract](https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern)
- [LaunchDarkly Feature Flag Best Practices](https://launchdarkly.com/blog/feature-flag-best-practices/)

### Deep-dive

- [Argo Rollouts Documentation](https://argoproj.github.io/argo-rollouts/) (Day 36 preview)
- [Flagger Progressive Delivery](https://flagger.app/)
- Sách: "Release It!" — Michael Nygard (deployment patterns, circuit breakers)
- Sách: "Continuous Delivery" — Jez Humble (deployment pipeline design)

