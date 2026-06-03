# Day 35: Deployment Strategies — Exercises

## Exercise 1: Rolling Update Mastery (Easy)

### Context

Bạn đang quản lý một web application trên Kubernetes. Team muốn hiểu rõ rolling update hoạt động như thế nào: maxSurge, maxUnavailable, và rollback.

### Yêu cầu

1. Tạo kind cluster và deploy nginx:1.24 với 4 replicas.
2. Cấu hình rolling update: `maxSurge: 1`, `maxUnavailable: 0`.
3. Thực hiện rolling update lên nginx:1.25 và **quan sát từng bước** (dùng `kubectl get pods -w`).
4. Kiểm tra rollout history.
5. Rollback về version trước.
6. Thử với `maxSurge: 2`, `maxUnavailable: 1` — quan sát sự khác biệt về tốc độ.
7. Ghi lại thời gian rollout cho mỗi configuration.

### Expected Outcome

- Hiểu rõ maxSurge/maxUnavailable ảnh hưởng rollout speed.
- Rollback thành công.
- Timing comparison giữa 2 configs.

### Hints

- `kubectl get pods -w` để watch real-time.
- `kubectl rollout status deployment/<name>` để track progress.
- `kubectl rollout history deployment/<name>` để xem versions.
- `kubectl rollout undo deployment/<name>` để rollback.

### Acceptance Criteria

- [ ] Deploy v1 thành công (4 pods running).
- [ ] Rolling update to v2 quan sát được từng pod update.
- [ ] Rollback thành công.
- [ ] 2 rollout configs tested và timing recorded.
- [ ] Viết 3 observations về rolling update behavior.
- [ ] Cleanup thành công.

### Bonus Challenge

Thêm `minReadySeconds: 10` và quan sát rollout chậm lại bao nhiêu. Giải thích tại sao `minReadySeconds` quan trọng trong production.

<details>
<summary>Solution</summary>

```bash
# Setup
kind create cluster --name rolling-lab

# Deploy v1 - config 1: maxSurge=1, maxUnavailable=0 (safe)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp
  annotations:
    kubernetes.io/change-cause: "Initial deploy nginx:1.24"
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
        - name: nginx
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
EOF

kubectl rollout status deployment/webapp
echo "=== Config 1: maxSurge=1, maxUnavailable=0 ==="

# Watch pods in background
kubectl get pods -l app=webapp -w &
WATCH_PID=$!

# Rolling update - time it
START=$(date +%s)
kubectl set image deployment/webapp nginx=nginx:1.25
kubectl annotate deployment/webapp kubernetes.io/change-cause="Update to nginx:1.25" --overwrite
kubectl rollout status deployment/webapp
END=$(date +%s)
echo "Config 1 rollout time: $((END - START)) seconds"
kill $WATCH_PID 2>/dev/null

# Check history
kubectl rollout history deployment/webapp

# Rollback
kubectl rollout undo deployment/webapp
kubectl rollout status deployment/webapp
kubectl get pods -l app=webapp -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}'
# Should show nginx:1.24

# Config 2: maxSurge=2, maxUnavailable=1 (faster)
kubectl patch deployment webapp -p '{"spec":{"strategy":{"rollingUpdate":{"maxSurge":2,"maxUnavailable":1}}}}'

kubectl get pods -l app=webapp -w &
WATCH_PID=$!

START=$(date +%s)
kubectl set image deployment/webapp nginx=nginx:1.25
kubectl rollout status deployment/webapp
END=$(date +%s)
echo "Config 2 rollout time: $((END - START)) seconds"
kill $WATCH_PID 2>/dev/null

# Observations:
echo "
=== Observations ===
1. Config 1 (maxSurge=1, maxUnavailable=0): Safer but slower
   - Always maintains 4 available pods
   - Updates one pod at a time
   
2. Config 2 (maxSurge=2, maxUnavailable=1): Faster but riskier
   - Allows 1 pod to be unavailable (3 minimum)
   - Creates 2 surge pods simultaneously
   - Roughly 2x faster rollout
   
3. readinessProbe determines when a new pod is 'ready'
   - Without readinessProbe, pod is considered ready immediately
   - Could route traffic to unready pods
"

# Bonus: minReadySeconds
kubectl patch deployment webapp -p '{"spec":{"minReadySeconds":10}}'
kubectl rollout undo deployment/webapp  # Back to 1.24
START=$(date +%s)
kubectl set image deployment/webapp nginx=nginx:1.25
kubectl rollout status deployment/webapp
END=$(date +%s)
echo "With minReadySeconds=10: $((END - START)) seconds"
echo "minReadySeconds adds a 'soak time' — pod must stay healthy for 10s before considered truly ready"

# Cleanup
kind delete cluster --name rolling-lab
```

</details>

---

## Exercise 2: Blue-Green Deployment Implementation (Medium)

### Context

Team bạn cần triển khai blue-green deployment cho payment API service. Requirements: instant rollback, zero downtime, ability to test green environment trước khi switch traffic.

### Yêu cầu

1. Tạo kind cluster.
2. Deploy "blue" environment (nginx:1.24 với custom index.html "Blue v1").
3. Deploy "green" environment (nginx:1.25 với custom index.html "Green v2").
4. Tạo Service pointing to blue.
5. Verify traffic đi đến blue.
6. Switch traffic sang green (patch service selector).
7. Verify traffic đi đến green.
8. Rollback: switch lại blue.
9. Verify rollback thành công.
10. Đo thời gian switch và rollback.

### Expected Outcome

- Blue-Green deployment hoạt động.
- Switch traffic < 5 seconds.
- Rollback < 5 seconds.
- Both environments chạy đồng thời.

### Hints

- Dùng ConfigMap để tạo custom index.html cho mỗi version.
- Service selector: `version: blue` hoặc `version: green`.
- `kubectl patch service` để switch.
- Port-forward để test: `kubectl port-forward svc/webapp 8080:80`.

### Acceptance Criteria

- [ ] Blue deployment running (3 pods).
- [ ] Green deployment running (3 pods).
- [ ] Service routes to blue initially.
- [ ] Switch to green verified.
- [ ] Rollback to blue verified.
- [ ] Switch time < 5 seconds.
- [ ] Rollback time < 5 seconds.
- [ ] Cleanup thành công.

### Bonus Challenge

Thêm "test endpoint" cho green trước khi switch: tạo Service riêng `webapp-green-test` pointing to green pods. Test green qua service này trước khi switch traffic chính.

<details>
<summary>Solution</summary>

```bash
kind create cluster --name bluegreen-lab

# Blue deployment with custom page
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: blue-page
data:
  index.html: |
    <h1>Blue v1 - Production</h1>
    <p>Version: 1.24</p>
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: green-page
data:
  index.html: |
    <h1>Green v2 - New Version</h1>
    <p>Version: 1.25</p>
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webapp
      version: blue
  template:
    metadata:
      labels:
        app: webapp
        version: blue
    spec:
      containers:
        - name: nginx
          image: nginx:1.24
          ports:
            - containerPort: 80
          volumeMounts:
            - name: html
              mountPath: /usr/share/nginx/html
          readinessProbe:
            httpGet:
              path: /
              port: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
      volumes:
        - name: html
          configMap:
            name: blue-page
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webapp
      version: green
  template:
    metadata:
      labels:
        app: webapp
        version: green
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
          volumeMounts:
            - name: html
              mountPath: /usr/share/nginx/html
          readinessProbe:
            httpGet:
              path: /
              port: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
      volumes:
        - name: html
          configMap:
            name: green-page
---
apiVersion: v1
kind: Service
metadata:
  name: webapp
spec:
  selector:
    app: webapp
    version: blue
  ports:
    - port: 80
      targetPort: 80
---
# Bonus: Test service for green
apiVersion: v1
kind: Service
metadata:
  name: webapp-green-test
spec:
  selector:
    app: webapp
    version: green
  ports:
    - port: 80
      targetPort: 80
EOF

# Wait for pods
kubectl rollout status deployment/webapp-blue
kubectl rollout status deployment/webapp-green

echo "=== All pods ==="
kubectl get pods -l app=webapp --show-labels

# Verify blue is active
echo "=== Current traffic (should be Blue) ==="
kubectl run curl-test --image=curlimages/curl --rm -it --restart=Never -- curl -s webapp/
# Should show "Blue v1"

# Bonus: Test green before switch
echo "=== Testing green (pre-switch) ==="
kubectl run curl-test2 --image=curlimages/curl --rm -it --restart=Never -- curl -s webapp-green-test/
# Should show "Green v2"

# Switch to green
echo "=== Switching to GREEN ==="
START=$(date +%s%N)
kubectl patch service webapp -p '{"spec":{"selector":{"version":"green"}}}'
END=$(date +%s%N)
echo "Switch time: $(( (END - START) / 1000000 )) ms"

# Verify green
echo "=== After switch (should be Green) ==="
kubectl run curl-test3 --image=curlimages/curl --rm -it --restart=Never -- curl -s webapp/

# Rollback to blue
echo "=== Rolling back to BLUE ==="
START=$(date +%s%N)
kubectl patch service webapp -p '{"spec":{"selector":{"version":"blue"}}}'
END=$(date +%s%N)
echo "Rollback time: $(( (END - START) / 1000000 )) ms"

echo "=== After rollback (should be Blue) ==="
kubectl run curl-test4 --image=curlimages/curl --rm -it --restart=Never -- curl -s webapp/

# Cleanup
kind delete cluster --name bluegreen-lab
```

</details>

---

## Exercise 3: Deployment Strategy Design for Production (Hard)

### Context

Bạn là tech lead cho một e-commerce platform. Hệ thống gồm:

| Service | Criticality | Traffic | Database |
|---------|-----------|---------|----------|
| checkout-api | Critical | 2000 RPS | PostgreSQL (orders table) |
| product-catalog | High | 5000 RPS | PostgreSQL (products, read-heavy) |
| notification-service | Medium | 500 RPS | Redis (queue) |
| admin-dashboard | Low | 50 RPS | Shared PostgreSQL |

Team deploy 3 lần/ngày. Gần đây có 2 incidents từ bad deployments (1 database migration breaking old pods, 1 resource exhaustion).

### Yêu cầu

1. **Chọn deployment strategy cho mỗi service** với justification.
2. **Thiết kế rollback plan** cho checkout-api (most critical).
3. **Viết database migration strategy** cho checkout-api — cụ thể cho scenario: thêm column `discount_type` vào orders table.
4. **Thiết kế health check** cho mỗi service (liveness, readiness, startup probes).
5. **Viết deployment runbook** cho checkout-api bao gồm:
   - Pre-deploy checklist.
   - Deploy steps.
   - Monitoring during deploy.
   - Rollback trigger criteria.
   - Rollback steps.
   - Post-deploy verification.
6. **Thiết kế feature flag strategy** cho new checkout flow.

### Expected Outcome

- Strategy selection document với justification.
- Rollback plan cho checkout-api.
- Database migration plan (expand-contract).
- Health check YAML cho 4 services.
- Deployment runbook.
- Feature flag design.

### Hints

- checkout-api: canary (critical, high traffic, database dependency).
- product-catalog: rolling update (read-heavy, stateless).
- notification-service: rolling update (queue-based, not user-facing).
- admin-dashboard: recreate (low traffic, acceptable downtime).
- Database: expand-contract pattern (3 phases).
- Feature flag: server-side, percentage-based rollout.

### Acceptance Criteria

- [ ] Strategy cho 4 services with justification.
- [ ] Rollback plan step-by-step.
- [ ] Database migration 3-phase plan.
- [ ] Health check YAML cho 4 services.
- [ ] Deployment runbook complete.
- [ ] Feature flag design with cleanup plan.
- [ ] Trade-offs documented.

### Bonus Challenge

Thiết kế automated canary analysis cho checkout-api: metrics nào cần monitor, threshold nào trigger auto-rollback, integration với Prometheus/Grafana.

<details>
<summary>Solution</summary>

### 1. Strategy Selection

| Service | Strategy | Justification |
|---------|----------|--------------|
| checkout-api | **Canary** (10% → 30% → 100%) | Critical path, database dependency, cần validate từng bước. Auto-rollback nếu error rate > 1% |
| product-catalog | **Rolling Update** (maxSurge=1, maxUnavailable=0) | Read-heavy, stateless, backward compatible APIs |
| notification-service | **Rolling Update** (maxSurge=1, maxUnavailable=1) | Queue-based, messages retry nếu fail, không user-facing |
| admin-dashboard | **Recreate** | 50 RPS, internal only, acceptable 30s downtime, simplify deployment |

### 2. Rollback Plan: checkout-api

```markdown
# Rollback Plan: checkout-api

## Trigger Criteria (auto-rollback if any):
- Error rate > 2% for 2 minutes
- Latency p99 > 500ms for 3 minutes
- Order completion rate drops > 5%
- Health check fails 3 consecutive times

## Rollback Steps:
1. Scale canary to 0: `kubectl scale deployment checkout-canary --replicas=0`
   → Time: < 10 seconds
   → Verify: `kubectl get pods -l track=canary` returns 0 pods

2. Verify stable pods healthy: `kubectl get pods -l track=stable`
   → All pods Running, Ready

3. Check metrics (Grafana dashboard):
   - Error rate returned to baseline (< 0.5%)
   - Latency p99 returned to baseline (< 200ms)
   - Order completion rate > 99%

4. Post-rollback:
   - Create incident ticket
   - Notify team in #checkout-deploys Slack
   - Do NOT re-deploy until root cause identified
   - Schedule postmortem within 24h
```

### 3. Database Migration: Add discount_type column

```sql
-- Phase 1: EXPAND (deploy BEFORE code change)
-- Add nullable column with default
ALTER TABLE orders ADD COLUMN discount_type VARCHAR(50) DEFAULT NULL;

-- Phase 2: CODE DEPLOY (canary)
-- v2 code writes to BOTH old flow AND discount_type
-- v1 code ignores discount_type (column exists but unused)
-- Both versions work with same schema ✅

-- Phase 3: BACKFILL (after 100% on v2)
-- Background job: populate discount_type for old orders
UPDATE orders SET discount_type = 'none' WHERE discount_type IS NULL;

-- Phase 4: CONTRACT (separate deploy, after backfill complete)
-- v3: make discount_type NOT NULL, add index if needed
ALTER TABLE orders ALTER COLUMN discount_type SET NOT NULL;
ALTER TABLE orders ALTER COLUMN discount_type SET DEFAULT 'none';
CREATE INDEX idx_orders_discount_type ON orders(discount_type);
```

### 4. Health Checks

```yaml
# checkout-api (critical)
containers:
  - name: checkout-api
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      initialDelaySeconds: 15
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /health/ready  # Checks DB + Redis connectivity
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 3
    startupProbe:
      httpGet:
        path: /health/live
        port: 8080
      periodSeconds: 2
      failureThreshold: 30

---
# product-catalog (read-heavy, cache warmup needed)
containers:
  - name: product-catalog
    readinessProbe:
      httpGet:
        path: /health/ready  # Checks DB + cache loaded
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      periodSeconds: 15

---
# notification-service (queue-based)
containers:
  - name: notification
    readinessProbe:
      httpGet:
        path: /health/ready  # Checks Redis queue connection
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      periodSeconds: 30

---
# admin-dashboard (low traffic)
containers:
  - name: admin
    readinessProbe:
      httpGet:
        path: /
        port: 3000
      initialDelaySeconds: 10
      periodSeconds: 10
```

### 5. Deployment Runbook: checkout-api

```markdown
# Deployment Runbook: checkout-api

## Pre-deploy Checklist
- [ ] All CI tests passing on this commit
- [ ] Security scan: 0 CRITICAL CVEs
- [ ] Database migration reviewed and tested on staging
- [ ] Staging deploy verified (running for 1+ hour)
- [ ] On-call engineer available and notified
- [ ] Not during peak hours (avoid 11am-1pm, 7pm-10pm)
- [ ] Not Friday after 3pm
- [ ] Rollback plan reviewed

## Deploy Steps
1. Open Grafana dashboard: checkout-api overview
2. Deploy canary (10%):
   - Push to config repo: update canary image tag
   - ArgoCD auto-sync
   - Monitor for 10 minutes
3. Check metrics:
   - Error rate < 0.5%? → Continue
   - Latency p99 < 250ms? → Continue
   - Order completion rate > 99%? → Continue
4. Promote to 30%:
   - Update canary replicas
   - Monitor for 10 minutes
5. Promote to 100%:
   - Update stable image tag
   - Scale canary to 0
   - Monitor for 15 minutes

## Monitoring During Deploy
- Grafana: checkout-api dashboard (error rate, latency, RPS)
- Logs: `kubectl logs -l app=checkout -f`
- Business: order completion rate, payment success rate

## Rollback Triggers
- Error rate > 2% for 2 min → auto-rollback
- Latency p99 > 500ms for 3 min → auto-rollback
- Any P1 alert → manual rollback decision

## Post-deploy Verification
- [ ] Error rate < 0.5% for 30 minutes
- [ ] Latency p99 < 200ms
- [ ] Order completion rate > 99%
- [ ] No error logs matching new version
- [ ] Notify team: "checkout-api v2.x deployed successfully"
```

### 6. Feature Flag Design

```yaml
# Feature flag: new_checkout_flow
flag:
  name: new_checkout_flow
  type: release
  default: false
  
  rollout:
    - phase: internal
      percentage: 0%
      users: ["internal@company.com"]
      duration: 3 days
    
    - phase: beta
      percentage: 5%
      targeting: "country IN ['VN'] AND account_age > 30d"
      duration: 7 days
    
    - phase: gradual
      percentage: 25%
      duration: 3 days
    
    - phase: majority
      percentage: 75%
      duration: 3 days
    
    - phase: full
      percentage: 100%
      duration: 7 days
    
    - phase: cleanup
      action: remove flag from code
      deadline: 14 days after full rollout

  kill_switch:
    trigger: "order_error_rate > 3% OR payment_failure_rate > 2%"
    action: disable flag → fallback to old checkout
    notify: "#checkout-alerts"

  cleanup:
    owner: "checkout-team"
    deadline: "2 weeks after 100% rollout"
    pr_required: true
    tests_to_remove: "test_old_checkout_*"
```

</details>

---

## Tổng kết thời lượng

| Exercise | Thời gian | Skill level |
|----------|-----------|-------------|
| Exercise 1: Rolling Update Mastery | ~25 phút | Easy |
| Exercise 2: Blue-Green Implementation | ~35 phút | Medium |
| Exercise 3: Production Strategy Design | ~60 phút | Hard |
| **Tổng** | **~2 giờ** | |

