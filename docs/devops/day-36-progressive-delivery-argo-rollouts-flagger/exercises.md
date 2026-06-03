# Day 36: Exercises — Progressive Delivery with Argo Rollouts

## Bài 1: Basic Canary Rollout (Easy)

### Context
Bạn vừa join team DevOps của một startup fintech. Team đang deploy microservices bằng `kubectl apply` trực tiếp. Manager yêu cầu bạn thiết lập progressive delivery cho `user-service` — service quan trọng nhất, phục vụ 5K users.

### Yêu cầu
1. Cài Argo Rollouts trên local kind cluster.
2. Chuyển `user-service` từ Deployment sang Rollout resource.
3. Cấu hình canary strategy với 3 steps: 20% → 50% → 100%, mỗi step pause 30 giây.
4. Tạo 2 Services (`stable` và `canary`).
5. Trigger canary rollout bằng cách thay đổi image.
6. Quan sát rollout tiến trình bằng `kubectl argo rollouts get`.

### Expected Outcome
- Rollout resource chạy thành công với image ban đầu (status: Healthy).
- Khi update image, rollout tiến hành qua 3 steps tự động.
- Sau khi hoàn thành, 100% traffic đến version mới.

### Hint
- Dùng image `argoproj/rollouts-demo:blue` cho v1, `argoproj/rollouts-demo:green` cho v2.
- Đảm bảo cài kubectl argo rollouts plugin để xem status dễ hơn.
- `pause: { duration: 30s }` sẽ tự động resume sau 30 giây.

### Acceptance Criteria
- [ ] Argo Rollouts controller chạy trong cluster.
- [ ] Rollout resource deploy thành công.
- [ ] Canary rollout tiến hành qua đúng 3 steps.
- [ ] `kubectl argo rollouts get rollout user-service` hiển thị đúng weight ở mỗi step.
- [ ] Rollout kết thúc với status Healthy.

### Bonus Challenge
- Thêm Ingress với NGINX traffic routing thay vì replica-based splitting.
- Mở Argo Rollouts Dashboard và quan sát rollout trên UI.

---

## Bài 2: Automated Analysis với Prometheus (Medium)

### Context
Team bạn đã dùng Argo Rollouts canary cơ bản (Bài 1). Nhưng tuần trước, một developer promote canary version mà không kiểm tra metrics → version mới có latency p99 tăng 3x → 500 users phàn nàn trong 2 giờ trước khi team rollback.

Manager yêu cầu: "Không được promote mà không có automated analysis. Nếu error rate > 5% hoặc p99 latency > 500ms → tự động rollback."

### Yêu cầu
1. Cài Prometheus trên cluster (dùng kube-prometheus-stack Helm chart hoặc standalone).
2. Deploy một sample app expose Prometheus metrics (`/metrics` endpoint).
3. Tạo `AnalysisTemplate` với 2 metrics:
   - **success-rate**: HTTP 2xx / total requests ≥ 95%.
   - **p99-latency**: ≤ 500ms.
4. Cấu hình Rollout sử dụng AnalysisTemplate tại mỗi step.
5. Test case 1: Deploy version tốt → analysis pass → promote thành công.
6. Test case 2: Deploy version xấu (high error rate) → analysis fail → automated rollback.

### Expected Outcome
- AnalysisRun được tạo tự động ở mỗi analysis step.
- Version tốt: AnalysisRun status = Successful → rollout promoted.
- Version xấu: AnalysisRun status = Failed → rollout aborted automatically.

### Hint
- Dùng `argoproj/rollouts-demo:bad-red` cho version xấu (trả HTTP errors).
- Prometheus query cho success rate:
  ```promql
  sum(rate(http_requests_total{status=~"2.."}[2m])) /
  sum(rate(http_requests_total[2m]))
  ```
- Đặt `interval: 30s`, `count: 3`, `failureLimit: 1` cho AnalysisTemplate.
- Nếu Prometheus chưa scrape app, kiểm tra ServiceMonitor hoặc prometheus.io annotations.

### Acceptance Criteria
- [ ] Prometheus chạy và scrape metrics từ app.
- [ ] AnalysisTemplate tạo thành công với 2 metrics.
- [ ] Rollout version tốt → AnalysisRun pass → promoted.
- [ ] Rollout version xấu → AnalysisRun fail → aborted.
- [ ] `kubectl get analysisrun` hiển thị đúng status (Successful/Failed).
- [ ] Không có manual intervention trong quá trình analysis.

### Bonus Challenge
- Thêm metric thứ 3: request rate (RPS) phải > 0 để tránh promote khi không có traffic.
- Cấu hình Slack notification khi rollout abort.
- Tạo Grafana dashboard hiển thị canary vs stable metrics side-by-side.

---

## Bài 3: Production-Grade Progressive Delivery Pipeline (Hard)

### Context
Bạn là DevOps Lead tại một e-commerce platform (100K DAU, 3K RPS peak). Team có 8 microservices trên Kubernetes. CEO yêu cầu zero-downtime deployments với automated quality gates sau incident tháng trước (deploy lỗi gây outage 45 phút, mất $50K revenue).

Yêu cầu: Thiết kế và triển khai progressive delivery pipeline cho `order-service` — service xử lý đặt hàng, critical nhất.

### Yêu cầu

**Part A: Rollout Design**
1. Thiết kế Rollout strategy phù hợp cho critical service:
   - Steps: 1% → 5% → 10% → 25% → 50% → 100%.
   - Analysis tại mỗi step (trừ step đầu).
   - Pause manual approval trước khi vượt 50%.
2. Viết Rollout YAML hoàn chỉnh với:
   - Resource requests/limits.
   - Health checks (liveness + readiness).
   - Anti-affinity giữa canary và stable.
   - Revision history limit.

**Part B: Analysis Templates**
3. Tạo AnalysisTemplate đánh giá:
   - HTTP success rate ≥ 99.5% (critical service cần threshold cao hơn).
   - p99 latency ≤ 300ms.
   - Error log rate (từ Loki nếu có, hoặc Prometheus counter).
   - Business metric: order completion rate so với baseline.
4. Cấu hình `failureLimit`, `count`, `interval` phù hợp cho từng metric.

**Part C: Operational Readiness**
5. Viết runbook cho 3 scenarios:
   - Rollout bị stuck ở "Progressing".
   - Analysis fail liên tục dù version mới không có bug (false negative).
   - Rollback cần urgent (skip analysis).
6. Tạo checklist pre-deployment:
   - Database migration compatible?
   - Feature flags configured?
   - Monitoring dashboards ready?
   - On-call engineer aware?

**Part D: Implementation**
7. Deploy toàn bộ trên local kind cluster:
   - Argo Rollouts + NGINX Ingress.
   - Prometheus (scrape app metrics).
   - Sample app simulate order service.
8. Test 3 scenarios:
   - Normal deploy (pass all analysis).
   - Deploy version có latency regression (analysis detect và rollback).
   - Manual pause và approval flow.

### Expected Outcome
- Pipeline tự động: code push → image build → rollout trigger → progressive canary → automated analysis → promote/rollback.
- Runbook rõ ràng, có command cụ thể.
- Tất cả 3 test scenarios pass.

### Hint
- Dùng `pause: {}` (không duration) cho manual approval step — cần `kubectl argo rollouts promote` để tiếp tục.
- Business metric có thể fake bằng custom Prometheus counter trong sample app.
- Anti-affinity:
  ```yaml
  antiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      weight: 100
  ```
- Để test latency regression, dùng app version thêm `sleep(500ms)` trước response.

### Acceptance Criteria
- [ ] Rollout YAML đầy đủ 6 steps + analysis + manual approval.
- [ ] AnalysisTemplate có ≥ 3 metrics bao gồm business metric.
- [ ] Normal deploy: canary tiến qua tất cả steps, promote thành công.
- [ ] Bad deploy: analysis detect và abort tự động.
- [ ] Manual approval: rollout pause đúng vị trí, resume khi promote.
- [ ] Runbook có command cụ thể, không chỉ mô tả chung.
- [ ] Pre-deployment checklist cover database migration và feature flag.
- [ ] Cleanup script xóa sạch resources.

### Bonus Challenge
- Thêm A/B testing: route traffic dựa trên header `X-Canary: true` cho internal testing trước khi public canary.
- Implement multi-service rollout: khi `order-service` promote, trigger rollout cho `payment-service` (dependency).
- Tạo GitHub Actions workflow trigger Argo Rollouts khi merge to main.
- So sánh performance: replica-based splitting vs NGINX weight-based vs Istio VirtualService — measure overhead.

---

## Solutions

<details>
<summary>Solution Bài 1: Basic Canary Rollout</summary>

### Bước 1: Setup cluster và Argo Rollouts

```bash
# Tạo kind cluster
kind create cluster --name canary-demo

# Cài Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Verify
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argo-rollouts -n argo-rollouts --timeout=60s

# Cài plugin
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x ./kubectl-argo-rollouts-linux-amd64
sudo mv ./kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts
```

### Bước 2: Tạo Rollout manifest

```yaml
# user-service-rollout.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: user-service
  namespace: default
spec:
  replicas: 3
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: user-service
  strategy:
    canary:
      canaryService: user-service-canary
      stableService: user-service-stable
      steps:
        - setWeight: 20
        - pause: { duration: 30s }
        - setWeight: 50
        - pause: { duration: 30s }
        - setWeight: 100
        - pause: { duration: 10s }
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
        - name: user-service
          image: argoproj/rollouts-demo:blue
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: user-service-stable
spec:
  selector:
    app: user-service
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: user-service-canary
spec:
  selector:
    app: user-service
  ports:
    - port: 80
      targetPort: 8080
```

### Bước 3: Deploy và test

```bash
# Deploy
kubectl apply -f user-service-rollout.yaml

# Wait for healthy
kubectl argo rollouts get rollout user-service --watch

# Trigger canary
kubectl argo rollouts set image user-service user-service=argoproj/rollouts-demo:green

# Watch progression
kubectl argo rollouts get rollout user-service --watch

# Verify final state
kubectl argo rollouts get rollout user-service
```

### Cleanup

```bash
kubectl delete -f user-service-rollout.yaml
kind delete cluster --name canary-demo
```

</details>

<details>
<summary>Solution Bài 2: Automated Analysis với Prometheus</summary>

### Bước 1: Setup Prometheus

```bash
# Tạo cluster
kind create cluster --name analysis-demo

# Cài Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Cài Prometheus
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --set server.service.type=ClusterIP \
  --set alertmanager.enabled=false \
  --set pushgateway.enabled=false
```

### Bước 2: AnalysisTemplate

```yaml
# analysis-template.yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: app-health-check
spec:
  metrics:
    - name: success-rate
      interval: 30s
      count: 3
      failureLimit: 1
      successCondition: result[0] >= 0.95
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            sum(rate(
              http_requests_total{app="demo-app", status=~"2.."}[2m]
            )) /
            sum(rate(
              http_requests_total{app="demo-app"}[2m]
            ))
    - name: p99-latency
      interval: 30s
      count: 3
      failureLimit: 1
      successCondition: result[0] <= 500
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            histogram_quantile(0.99,
              sum(rate(
                http_request_duration_milliseconds_bucket{app="demo-app"}[2m]
              )) by (le)
            )
```

### Bước 3: Rollout với Analysis

```yaml
# rollout-with-analysis.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: demo-app
spec:
  replicas: 3
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: demo-app
  strategy:
    canary:
      canaryService: demo-app-canary
      stableService: demo-app-stable
      steps:
        - setWeight: 20
        - pause: { duration: 30s }
        - analysis:
            templates:
              - templateName: app-health-check
        - setWeight: 50
        - pause: { duration: 30s }
        - analysis:
            templates:
              - templateName: app-health-check
        - setWeight: 100
  template:
    metadata:
      labels:
        app: demo-app
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: demo-app
          image: argoproj/rollouts-demo:blue
          ports:
            - containerPort: 8080
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
  name: demo-app-stable
spec:
  selector:
    app: demo-app
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: demo-app-canary
spec:
  selector:
    app: demo-app
  ports:
    - port: 80
      targetPort: 8080
```

### Bước 4: Test

```bash
# Deploy
kubectl apply -f analysis-template.yaml
kubectl apply -f rollout-with-analysis.yaml

# Test good version
kubectl argo rollouts set image demo-app demo-app=argoproj/rollouts-demo:green
kubectl argo rollouts get rollout demo-app --watch
# → AnalysisRun: pass → promoted

# Test bad version
kubectl argo rollouts set image demo-app demo-app=argoproj/rollouts-demo:bad-red
kubectl argo rollouts get rollout demo-app --watch
# → AnalysisRun: fail → aborted

# Check analysis results
kubectl get analysisrun
kubectl describe analysisrun <name>
```

### Cleanup

```bash
kubectl delete -f rollout-with-analysis.yaml
kubectl delete -f analysis-template.yaml
helm uninstall prometheus -n monitoring
kind delete cluster --name analysis-demo
```

</details>

<details>
<summary>Solution Bài 3: Production-Grade Pipeline (Key Parts)</summary>

### Part A: Rollout YAML

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-service
  namespace: production
spec:
  replicas: 5
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: order-service
  strategy:
    canary:
      canaryService: order-service-canary
      stableService: order-service-stable
      trafficRouting:
        nginx:
          stableIngress: order-service-ingress
      abortScaleDownDelaySeconds: 300
      steps:
        # Phase 1: Internal testing
        - setWeight: 1
        - pause: { duration: 2m }
        
        # Phase 2: Small canary
        - setWeight: 5
        - analysis:
            templates:
              - templateName: order-service-analysis
        - setWeight: 10
        - analysis:
            templates:
              - templateName: order-service-analysis
              
        # Phase 3: Medium canary
        - setWeight: 25
        - analysis:
            templates:
              - templateName: order-service-analysis
        
        # Manual approval before going above 50%
        - pause: {}
        
        # Phase 4: Large canary
        - setWeight: 50
        - analysis:
            templates:
              - templateName: order-service-analysis
              
        # Phase 5: Full promotion
        - setWeight: 100
        
      antiAffinity:
        preferredDuringSchedulingIgnoredDuringExecution:
          weight: 100
          
  template:
    metadata:
      labels:
        app: order-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      containers:
        - name: order-service
          image: order-service:v1.0.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
          env:
            - name: LOG_LEVEL
              value: "info"
            - name: LOG_FORMAT
              value: "json"
```

### Part B: AnalysisTemplate

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: order-service-analysis
  namespace: production
spec:
  metrics:
    - name: success-rate
      interval: 1m
      count: 5
      failureLimit: 1
      successCondition: result[0] >= 0.995
      failureCondition: result[0] < 0.95
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            sum(rate(
              http_requests_total{
                app="order-service",
                status=~"[23].."
              }[5m]
            )) /
            sum(rate(
              http_requests_total{
                app="order-service"
              }[5m]
            ))
            
    - name: p99-latency
      interval: 1m
      count: 5
      failureLimit: 1
      successCondition: result[0] <= 300
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            histogram_quantile(0.99,
              sum(rate(
                http_request_duration_milliseconds_bucket{
                  app="order-service"
                }[5m]
              )) by (le)
            )
            
    - name: error-log-rate
      interval: 1m
      count: 5
      failureLimit: 2
      successCondition: result[0] <= 5
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            sum(rate(
              app_errors_total{
                app="order-service",
                severity="error"
              }[5m]
            )) * 60
            
    - name: order-completion-rate
      interval: 1m
      count: 5
      failureLimit: 1
      successCondition: result[0] >= 0.98
      provider:
        prometheus:
          address: http://prometheus-server.monitoring:80
          query: |
            sum(rate(
              orders_completed_total{app="order-service"}[5m]
            )) /
            sum(rate(
              orders_started_total{app="order-service"}[5m]
            ))
```

### Part C: Runbook

```markdown
## Runbook: Rollout stuck ở Progressing

1. Kiểm tra rollout status:
   kubectl argo rollouts get rollout order-service -n production

2. Kiểm tra canary pods:
   kubectl get pods -l app=order-service -n production
   kubectl describe pod <canary-pod> -n production

3. Nếu pod CrashLoopBackOff:
   kubectl logs <canary-pod> -n production --previous
   → Fix code, push new image, rollout sẽ restart

4. Nếu pod Pending (insufficient resources):
   kubectl describe pod <canary-pod> -n production | grep -A5 Events
   → Scale node hoặc giảm resource requests

5. Nếu analysis timeout:
   kubectl get analysisrun -n production
   kubectl describe analysisrun <name> -n production
   → Check Prometheus connectivity

6. Emergency abort:
   kubectl argo rollouts abort order-service -n production

## Runbook: Analysis false negative

1. Verify metric query trên Prometheus UI:
   kubectl port-forward svc/prometheus-server 9090:80 -n monitoring
   → Paste query từ AnalysisTemplate, check result

2. Nếu query trả NaN (no data):
   → App chưa expose metrics hoặc Prometheus chưa scrape
   → Check ServiceMonitor / annotations

3. Nếu threshold quá chặt:
   → Tạm thời tăng failureLimit
   → Manual promote: kubectl argo rollouts promote order-service -n production

4. Long-term: adjust threshold dựa trên baseline metrics (p50, p95 bình thường)

## Runbook: Emergency rollback (skip analysis)

1. Abort ngay lập tức:
   kubectl argo rollouts abort order-service -n production

2. Nếu abort không đủ nhanh, manual scale down canary:
   kubectl scale replicaset <canary-rs> --replicas=0 -n production

3. Verify traffic 100% về stable:
   kubectl argo rollouts get rollout order-service -n production

4. Notify team qua Slack/PagerDuty
5. Create incident ticket
```

### Pre-deployment Checklist

```markdown
## Pre-deployment Checklist — order-service

- [ ] Database migration backward-compatible? (old version có thể đọc new schema?)
- [ ] Feature flags configured cho new features?
- [ ] Rollback plan documented?
- [ ] Monitoring dashboard ready? (Grafana canary vs stable)
- [ ] On-call engineer aware và available?
- [ ] Load test passed cho new version?
- [ ] Security scan (SAST/SCA) passed?
- [ ] Integration test với dependent services passed?
- [ ] Changelog và release notes cập nhật?
- [ ] Deployment window phù hợp? (không deploy Friday 5PM)
```

</details>

