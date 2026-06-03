# Day 36: Progressive Delivery with Argo Rollouts / Flagger

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được progressive delivery vs traditional deployment** — hiểu vì sao canary thủ công (Day 35) chưa đủ cho production-grade.
2. **Triển khai được canary rollout bằng Argo Rollouts** với metric-based promotion tự động trên local Kubernetes cluster.
3. **Cấu hình được automated analysis** sử dụng Prometheus metrics để quyết định promote hay rollback.
4. **So sánh được Argo Rollouts vs Flagger** — biết khi nào chọn tool nào theo context team và stack.
5. **Debug được rollout bị stuck hoặc rollback không mong muốn** — đọc được rollout status, events và analysis results.

---

## 2. Bối cảnh & Động lực

### Vấn đề với canary thủ công

Ở Day 35, bạn đã học canary deployment bằng cách chia traffic thủ công. Trong production thực tế, approach đó có nhiều vấn đề:

- **Human bottleneck**: Ai sẽ ngồi watch metrics lúc 2 giờ sáng sau khi deploy?
- **Reaction time**: Con người mất 5-15 phút để nhận ra vấn đề → hàng ngàn users bị ảnh hưởng.
- **Inconsistency**: Dev A promote sau 10 phút, Dev B promote sau 1 giờ — không có standard.
- **Toil**: Mỗi lần deploy phải lặp lại quy trình manual — vi phạm nguyên tắc SRE.

### Progressive delivery giải quyết gì?

```
Traditional Canary (Day 35):
  Deploy → Manual watch → Manual decision → Manual promote/rollback
  
Progressive Delivery (Day 36):
  Deploy → Automated analysis → Automated promotion → Automated rollback
         ↑                                              ↓
         └──── Metrics-driven feedback loop ────────────┘
```

**Progressive delivery = canary deployment + automated analysis + automated decision making.**

### Liên hệ với developer

- **Automated analysis** giống unit test cho deployment: nếu metrics pass → promote, nếu fail → rollback. Không cần con người quyết định.
- **Argo Rollouts controller** là một Kubernetes controller chạy reconciliation loop (giống concept ở Day 10) — nó liên tục so sánh desired state (rollout spec) với actual state (pod/traffic status).
- **Metric-based promotion** giống circuit breaker pattern: nếu error rate vượt threshold → trip circuit → rollback.

### Nếu làm sai thì sao?

- **Thiếu automated rollback**: Version mới có bug, 2 giờ sau team mới biết → 50K users bị lỗi.
- **Analysis metrics sai**: Đo sai metric → promote version lỗi → full outage.
- **Rollout stuck**: Config sai → rollout treo ở 20% → service chạy 2 versions mãi → data inconsistency.

---

## 3. Kiến thức nền tảng

### 3.1 Progressive Delivery là gì?

Progressive delivery là practice triển khai phần mềm theo từng bước nhỏ, đánh giá tự động ở mỗi bước, và tự động rollback nếu phát hiện vấn đề.

```
                    ┌─────────┐
                    │  Deploy  │
                    │  (5%)    │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ Analysis │ ← Query Prometheus
                    │ (wait)   │
                    └────┬─────┘
                         │
                   ┌─────┴──────┐
                   │             │
              ┌────▼────┐  ┌────▼─────┐
              │ Promote  │  │ Rollback │
              │ (25%)    │  │ (0%)     │
              └────┬─────┘  └──────────┘
                   │
              ┌────▼─────┐
              │ Analysis  │
              │ (wait)    │
              └────┬──────┘
                   │
             ┌─────┴──────┐
             │             │
        ┌────▼────┐  ┌────▼─────┐
        │ Promote  │  │ Rollback │
        │ (100%)   │  │ (0%)     │
        └──────────┘  └──────────┘
```

### 3.2 Các thành phần chính

| Thành phần | Vai trò |
|-----------|---------|
| **Rollout Controller** | Quản lý lifecycle của rollout, điều phối traffic shifting |
| **Analysis Engine** | Chạy metric queries tại mỗi step, đánh giá pass/fail |
| **Traffic Router** | Điều hướng traffic giữa stable và canary (NGINX, Istio, ALB) |
| **Metrics Provider** | Cung cấp dữ liệu cho analysis (Prometheus, Datadog, NewRelic) |

### 3.3 Argo Rollouts vs Flagger

Đây là 2 tools phổ biến nhất cho progressive delivery trên Kubernetes:

| Tiêu chí | Argo Rollouts | Flagger |
|----------|---------------|---------|
| **Maintainer** | Argo (CNCF) | Flux (CNCF) |
| **CRD chính** | `Rollout` (thay thế Deployment) | Sử dụng `Deployment` gốc + `Canary` CRD |
| **Traffic routers** | NGINX, Istio, ALB, Traefik, SMI | Istio, Linkerd, NGINX, Contour, Gloo |
| **Analysis** | Built-in AnalysisTemplate | Built-in MetricTemplate |
| **UI** | Argo Rollouts Dashboard | Không có UI riêng (dùng Grafana) |
| **Blue-Green** | ✅ Native | ✅ Native |
| **Canary** | ✅ Native | ✅ Native |
| **A/B Testing** | ✅ (header-based) | ✅ (header-based với Istio) |
| **Integration** | Tốt nhất với Argo CD | Tốt nhất với Flux CD |
| **Learning curve** | Medium | Medium |
| **Community** | Lớn hơn | Nhỏ hơn |

---

## 4. Deep Dive

### 4.1 Argo Rollouts Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Kubernetes Cluster                    │
│                                                        │
│  ┌─────────────────┐    ┌──────────────────────┐      │
│  │  Argo Rollouts   │    │  Rollout Resource     │      │
│  │  Controller      │◄───│  (replaces Deployment)│      │
│  │                   │    │                        │      │
│  │  - Watch Rollout  │    │  spec:                 │      │
│  │  - Manage ReplicaSet   │    strategy:          │      │
│  │  - Run Analysis   │    │      canary:           │      │
│  │  - Traffic shift   │    │        steps:          │      │
│  └────────┬──────────┘    └──────────────────────┘      │
│           │                                              │
│           ▼                                              │
│  ┌────────────────┐  ┌────────────────┐                 │
│  │ Stable RS      │  │ Canary RS      │                 │
│  │ (v1 pods)      │  │ (v2 pods)      │                 │
│  │ weight: 95%    │  │ weight: 5%     │                 │
│  └───────┬────────┘  └───────┬────────┘                 │
│          │                    │                           │
│          ▼                    ▼                           │
│  ┌─────────────────────────────────┐                    │
│  │  Traffic Router (NGINX/Istio)   │                    │
│  │  - Routes based on weight       │                    │
│  └─────────────────────────────────┘                    │
│                                                          │
│  ┌─────────────────────────────────┐                    │
│  │  AnalysisRun                     │                    │
│  │  - Query Prometheus              │                    │
│  │  - Evaluate success condition    │                    │
│  │  - Report: Successful/Failed     │                    │
│  └─────────────────────────────────┘                    │
│                                                          │
│  ┌─────────────────────────────────┐                    │
│  │  Prometheus                      │                    │
│  │  - error_rate                    │                    │
│  │  - p99_latency                   │                    │
│  │  - request_rate                  │                    │
│  └─────────────────────────────────┘                    │
└──────────────────────────────────────────────────────┘
```

### 4.2 Rollout Lifecycle

```
                 Healthy
                    │
            ┌───────▼────────┐
     ┌──────│    Progressing  │──────┐
     │      └───────┬────────┘      │
     │              │               │
     │    ┌─────────▼──────────┐    │
     │    │  Analysis Running   │    │
     │    └─────────┬──────────┘    │
     │              │               │
     │     ┌────────┴────────┐      │
     │     │                 │      │
┌────▼─────▼──┐      ┌──────▼─────┐│
│  Degraded    │      │ Paused     ││
│  (rollback)  │      │ (waiting)  ││
└──────────────┘      └────────────┘│
                                     │
                            ┌────────▼──────┐
                            │   Healthy      │
                            │   (promoted)   │
                            └────────────────┘
```

### 4.3 Rollout Resource chi tiết

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: my-app
spec:
  replicas: 5
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: my-app
  strategy:
    canary:
      # Traffic routing configuration
      canaryService: my-app-canary    # Service cho canary pods
      stableService: my-app-stable    # Service cho stable pods
      
      trafficRouting:
        nginx:
          stableIngress: my-app-ingress
          
      # Canary steps
      steps:
        - setWeight: 5
        - pause: { duration: 2m }     # Chờ 2 phút thu thập metrics
        - analysis:
            templates:
              - templateName: success-rate
            args:
              - name: service-name
                value: my-app-canary
        - setWeight: 25
        - pause: { duration: 2m }
        - analysis:
            templates:
              - templateName: success-rate
        - setWeight: 50
        - pause: { duration: 5m }
        - analysis:
            templates:
              - templateName: success-rate
        - setWeight: 100
        
      # Rollback configuration
      maxSurge: 1
      maxUnavailable: 0
      
      # Anti-affinity between canary and stable
      antiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution: {}
        
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: my-app
          image: my-app:v2
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
```

### 4.4 AnalysisTemplate chi tiết

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  args:
    - name: service-name
      value: my-app-canary
  metrics:
    - name: success-rate
      # Chạy query mỗi 30 giây
      interval: 30s
      # Số lần đo tối thiểu trước khi quyết định
      count: 5
      # Số lần fail tối đa được phép
      failureLimit: 2
      # Điều kiện thành công
      successCondition: result[0] >= 0.95
      # Điều kiện thất bại (rollback ngay)
      failureCondition: result[0] < 0.80
      provider:
        prometheus:
          address: http://prometheus.monitoring:9090
          query: |
            sum(rate(
              http_requests_total{
                service="{{args.service-name}}",
                status=~"2.."
              }[2m]
            )) /
            sum(rate(
              http_requests_total{
                service="{{args.service-name}}"
              }[2m]
            ))
            
    - name: p99-latency
      interval: 30s
      count: 5
      failureLimit: 2
      successCondition: result[0] <= 500
      provider:
        prometheus:
          address: http://prometheus.monitoring:9090
          query: |
            histogram_quantile(0.99,
              sum(rate(
                http_request_duration_milliseconds_bucket{
                  service="{{args.service-name}}"
                }[2m]
              )) by (le)
            )
```

### 4.5 Flagger Architecture (so sánh)

Flagger hoạt động khác Argo Rollouts ở chỗ: nó **không thay thế Deployment**, mà wrap quanh Deployment bằng `Canary` CRD:

```
┌─────────────────────────────────────────┐
│          Flagger Controller              │
│                                          │
│  Watch: Canary CRD                       │
│  ──────────────────                      │
│  1. Detect Deployment change             │
│  2. Scale canary Deployment              │
│  3. Run metrics check                    │
│  4. Shift traffic gradually              │
│  5. Promote or rollback                  │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────┐   ┌──────────┐
│ Primary  │   │ Canary   │
│Deployment│   │Deployment│  ← Flagger tạo/quản lý
│ (stable) │   │ (new)    │
└──────────┘   └──────────┘
```

```yaml
# Flagger Canary CRD
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: my-app
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app            # Reference Deployment gốc
  service:
    port: 8080
  analysis:
    interval: 30s
    threshold: 5            # Max failed checks
    maxWeight: 50           # Max canary weight
    stepWeight: 10          # Weight increment per step
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99
        interval: 1m
      - name: request-duration
        thresholdRange:
          max: 500
        interval: 1m
```

### 4.6 Failure Modes

| Failure | Nguyên nhân | Hậu quả | Mitigation |
|---------|------------|----------|------------|
| **Analysis timeout** | Prometheus down hoặc query chậm | Rollout stuck ở canary weight | Cấu hình `failureLimit` và `timeout` |
| **False positive** | Metric query sai, threshold quá lỏng | Promote version lỗi | Test analysis template trước khi production |
| **False negative** | Threshold quá chặt, noise trong metrics | Rollback version tốt | Dùng `failureLimit > 1` để cho phép retry |
| **Traffic router failure** | NGINX/Istio misconfiguration | Traffic không shift đúng | Verify traffic routing trước khi dùng |
| **Controller crash** | OOM, bug trong controller | Rollout treo, không promote/rollback | HA deployment cho controller, resource limits |
| **Canary pod crash** | Bug trong new version | Rollout stuck ở CrashLoopBackOff | Abort rollout tự động khi pod unhealthy |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Argo Rollouts vs Flagger

| Tiêu chí | Argo Rollouts tốt hơn khi | Flagger tốt hơn khi |
|----------|---------------------------|---------------------|
| **Existing stack** | Đang dùng ArgoCD | Đang dùng FluxCD |
| **Migration effort** | Sẵn sàng thay Deployment → Rollout | Muốn giữ Deployment gốc |
| **UI cần thiết** | Cần dashboard riêng | Dùng Grafana đã đủ |
| **Service mesh** | Không bắt buộc | Dùng Istio/Linkerd |
| **Flexibility** | Cần steps phức tạp, nhiều analysis | Cần simple weighted canary |

### 5.2 Best Practices theo scenario

**Startup (< 20 engineers)**:
- Dùng Argo Rollouts với NGINX Ingress (đơn giản nhất).
- Analysis dùng 1-2 metrics cơ bản (success rate + latency).
- Không cần service mesh.
- Steps: 10% → 50% → 100%.

**Mid-size (20-100 engineers)**:
- Argo Rollouts hoặc Flagger + Prometheus.
- Analysis dùng 3-5 metrics (success rate, latency, error rate, saturation).
- Cân nhắc Istio nếu cần traffic splitting chính xác.
- Steps: 5% → 15% → 30% → 50% → 100%.

**Enterprise (100+ engineers)**:
- Argo Rollouts + Istio + comprehensive analysis.
- Custom metrics từ business domain.
- Multi-region rollout.
- Steps: 1% → 5% → 10% → 25% → 50% → 75% → 100%.
- Approval gates giữa regions.

**High-traffic system (> 10K RPS)**:
- Cần traffic splitting chính xác (Istio/Linkerd, không dùng replica-based).
- Analysis window lớn hơn (5-10 phút) để có đủ sample size.
- Nhiều metrics hơn: error rate, latency percentiles, business metrics.
- Automated rollback kèm PagerDuty/Slack notification.

### 5.3 Anti-patterns cần tránh

1. **"Deploy and pray" canary**: Chạy canary mà không có analysis → giống rolling update nhưng chậm hơn.
2. **Too few metrics**: Chỉ check health endpoint → miss latency degradation, error spike.
3. **Too short analysis window**: 30 giây không đủ → false pass khi traffic thấp.
4. **No baseline comparison**: So sánh với threshold cố định thay vì baseline → miss regression.
5. **Skip staging**: Test rollout config trực tiếp trên production → rollout stuck, traffic disrupted.
6. **Ignore database migrations**: Schema change không backward-compatible → canary đọc data sai.

---

## 6. Performance & Scalability ⭐

### 6.1 Performance Implications

| Yếu tố | Impact | Mitigation |
|--------|--------|------------|
| **Extra pods** | Canary cần thêm pods → tốn resource | Dùng `maxSurge: 1` hoặc scale down stable |
| **Analysis overhead** | Prometheus queries mỗi 30s | Dùng recording rules cho complex queries |
| **Traffic routing** | NGINX weight-based ít overhead; Istio có sidecar overhead | Chọn traffic router phù hợp performance budget |
| **Controller** | Argo Rollouts controller dùng ~100MB RAM | HA deployment, resource limits |

### 6.2 Scaling Considerations

- **Replica-based traffic splitting** (không dùng service mesh): Canary weight = canary replicas / total replicas. Với 20 replicas, bước nhỏ nhất = 5%. Không thể đạt 1%.
- **Service mesh traffic splitting**: Chính xác đến 0.1%. Không phụ thuộc số replicas. Nhưng thêm sidecar overhead (~10-20ms latency, ~50MB RAM per pod).
- **Analysis query performance**: Với cluster lớn (>100 services), Prometheus query có thể chậm → dùng recording rules hoặc Thanos/Mimir.

### 6.3 Bottleneck thường gặp

- **Prometheus cardinality**: AnalysisTemplate query high-cardinality metrics → query timeout → analysis fail → unexpected rollback.
- **Image pull time**: Canary pod cần pull new image → nếu image lớn (>1GB) → slow start → analysis window bị lãng phí.
- **Readiness probe**: Pod chưa ready → traffic không route đến → metrics trống → analysis inconclusive.

---

## 7. Security & Reliability Considerations

### 7.1 Security

- **RBAC cho Rollout**: Chỉ CI/CD service account mới được create/update Rollout. Dev không nên kubectl edit rollout trên production.
- **AnalysisTemplate immutable**: Tránh ai đó sửa analysis threshold để force promote version lỗi.
- **Prometheus access**: AnalysisRun cần query Prometheus → đảm bảo network policy cho phép.
- **Secret trong rollout**: Dùng `secretKeyRef` cho image pull secrets, không hardcode.

### 7.2 Reliability

- **Controller HA**: Deploy Argo Rollouts controller với `replicas: 2` và leader election.
- **Rollback safety**: Luôn cấu hình `abortScaleDownDelaySeconds` để có thời gian debug trước khi scale down canary.
- **Progressive rollback**: Rollback cũng nên gradual nếu traffic lớn — tránh thundering herd khi đột ngột chuyển 100% traffic.
- **Monitoring controller**: Alert khi controller OOM hoặc restart → rollout sẽ không được quản lý.

---

## 8. Hands-on Example

### 8.1 Prerequisites

```bash
# Tạo kind cluster (nếu chưa có)
kind create cluster --name progressive-delivery

# Cài Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Cài Argo Rollouts kubectl plugin
# Linux/macOS:
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x ./kubectl-argo-rollouts-linux-amd64
sudo mv ./kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts

# Verify
kubectl argo rollouts version

# Cài NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s
```

### 8.2 Deploy sample app

```bash
# Tạo namespace
kubectl create namespace demo
```

**File: `app-v1.yaml`** — Rollout resource:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: demo-app
  namespace: demo
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
      trafficRouting:
        nginx:
          stableIngress: demo-app-ingress
      steps:
        - setWeight: 20
        - pause: { duration: 30s }
        - setWeight: 50
        - pause: { duration: 30s }
        - setWeight: 80
        - pause: { duration: 30s }
  template:
    metadata:
      labels:
        app: demo-app
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
  name: demo-app-stable
  namespace: demo
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
  namespace: demo
spec:
  selector:
    app: demo-app
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: demo-app-ingress
  namespace: demo
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: demo-app.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: demo-app-stable
                port:
                  number: 80
```

```bash
# Apply
kubectl apply -f app-v1.yaml

# Kiểm tra rollout status
kubectl argo rollouts get rollout demo-app -n demo --watch

# Expected output:
# Name:            demo-app
# Namespace:       demo
# Status:          ✔ Healthy
# Strategy:        Canary
#   Step:          6/6
#   SetWeight:     100
#   ActualWeight:  100
# Images:          argoproj/rollouts-demo:blue (stable)
# Replicas:
#   Desired:       3
#   Current:       3
#   Updated:       3
#   Ready:         3
#   Available:     3
```

### 8.3 Trigger canary rollout

```bash
# Update image → trigger canary rollout
kubectl argo rollouts set image demo-app demo-app=argoproj/rollouts-demo:green -n demo

# Watch rollout tiến trình
kubectl argo rollouts get rollout demo-app -n demo --watch

# Expected output:
# Name:            demo-app
# Namespace:       demo
# Status:          ◌ Progressing
# Strategy:        Canary
#   Step:          1/6
#   SetWeight:     20
#   ActualWeight:  20
# Images:          argoproj/rollouts-demo:blue (stable)
#                  argoproj/rollouts-demo:green (canary)
# Replicas:
#   Desired:       3
#   Current:       4
#   Updated:       1
#   Ready:         4
#   Available:     4
```

### 8.4 Manual promote / abort

```bash
# Nếu muốn promote ngay (skip remaining steps)
kubectl argo rollouts promote demo-app -n demo

# Nếu muốn abort (rollback về stable)
kubectl argo rollouts abort demo-app -n demo

# Retry sau khi abort
kubectl argo rollouts retry rollout demo-app -n demo
```

### 8.5 Mô phỏng lỗi và rollback

```bash
# Deploy version "bad" (trả error)
kubectl argo rollouts set image demo-app demo-app=argoproj/rollouts-demo:bad-red -n demo

# Watch — sẽ thấy canary pods CrashLoopBackOff hoặc readiness fail
kubectl argo rollouts get rollout demo-app -n demo --watch

# Abort rollout
kubectl argo rollouts abort demo-app -n demo

# Verify rollback
kubectl argo rollouts get rollout demo-app -n demo
# Status should be: Degraded (aborted)
# All traffic goes to stable version
```

### 8.6 Dashboard (optional)

```bash
# Mở Argo Rollouts Dashboard
kubectl argo rollouts dashboard -n demo
# Truy cập: http://localhost:3100
```

### 8.7 Cleanup

```bash
kubectl delete namespace demo
kubectl delete namespace argo-rollouts
kind delete cluster --name progressive-delivery
```

### 8.8 Verify checklist

- [ ] Argo Rollouts controller chạy thành công
- [ ] Rollout ban đầu stable với image blue
- [ ] Update image → canary rollout tiến hành theo steps (20% → 50% → 80% → 100%)
- [ ] Có thể manual promote/abort
- [ ] Image bad → có thể abort và rollback

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|-----|------------|----------|
| **Rollout stuck ở "Progressing"** | Pod mới không ready (image pull fail, crash) | `kubectl describe pod <canary-pod>`, check events |
| **"Unable to find traffic router"** | Thiếu annotation hoặc service mesh config | Verify Ingress/VirtualService annotation đúng |
| **Analysis always fails** | Prometheus query trả `NaN` hoặc empty | Test query trực tiếp trên Prometheus UI trước |
| **Traffic không shift** | NGINX Ingress không support traffic weight | Verify NGINX Ingress Controller version ≥ 0.39 |
| **Rollback không hoàn thành** | `abortScaleDownDelaySeconds` chưa hết | Chờ hoặc manual scale down canary RS |

### 9.2 Debug flow

```bash
# 1. Xem rollout status tổng quan
kubectl argo rollouts get rollout <name> -n <ns>

# 2. Xem events
kubectl describe rollout <name> -n <ns>

# 3. Xem analysis results
kubectl get analysisrun -n <ns>
kubectl describe analysisrun <name> -n <ns>

# 4. Xem canary pod logs
kubectl logs -l app=<name>,rollouts-pod-template-hash=<canary-hash> -n <ns>

# 5. Kiểm tra traffic routing
kubectl describe ingress <name> -n <ns>

# 6. Force abort nếu cần
kubectl argo rollouts abort <name> -n <ns>
```

### 9.3 Production Case Study: Canary analysis false positive

**Context**: Một e-commerce platform (50K DAU) deploy payment service v2 lúc 2AM UTC.

**Symptom**: Canary analysis pass ở tất cả steps, promote lên 100%. Sau 30 phút, alert báo payment failure rate tăng 15%.

**Investigation**:
- AnalysisTemplate chỉ check HTTP 5xx rate → v2 trả HTTP 200 nhưng body chứa error code.
- Traffic lúc 2AM rất thấp (50 RPS) → sample size quá nhỏ → metric dao động lớn.
- Analysis window = 1 phút → chưa đủ thời gian phát hiện slow-burn issue.

**Root Cause**: Analysis metrics không đo đúng business outcome. HTTP status code ≠ business success.

**Mitigation**: Rollback bằng `kubectl argo rollouts undo`. MTTR = 8 phút.

**Long-term Fix**:
1. Thêm business metric: `payment_success_total` / `payment_total`.
2. Tăng analysis window lên 5 phút.
3. Thêm minimum request count threshold: chỉ evaluate khi có ≥ 100 requests.
4. Deploy lúc peak traffic (10AM-2PM) thay vì off-peak.

**Lesson Learned**: Metrics cho progressive delivery phải đo business outcome, không chỉ infrastructure health.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 35)
- Day 35 dạy deployment strategies cơ bản: rolling, blue-green, canary, feature flag.
- Day 36 nâng cấp canary thành **automated progressive delivery** — thêm analysis và automated decision.
- Concepts từ Day 35 được dùng trực tiếp: canary weight, traffic shifting, rollback.

### Bài sau (Day 37)
- Day 37 học về Artifact Registry, Image Signing & Supply Chain.
- Liên quan: image được sign và verify trước khi progressive delivery sử dụng.
- Progressive delivery + supply chain security = defense in depth cho deployment pipeline.

### Kiến thức liên quan
- **Day 10**: Kubernetes reconciliation loop → Argo Rollouts controller cũng là controller pattern.
- **Day 12-13**: Service, Ingress → traffic routing cho canary.
- **Day 18**: Resource requests/limits → canary pods cũng cần right-sizing.
- **Day 19**: HPA → cẩn thận khi dùng HPA + progressive delivery (có thể conflict).

---

## 11. Tài liệu tham khảo

### Must-read
- [Argo Rollouts - Official Documentation](https://argoproj.github.io/argo-rollouts/)
- [Progressive Delivery with Argo Rollouts - CNCF Blog](https://www.cncf.io/blog/2020/03/24/progressivedelivery-with-argo-rollouts/)
- [Argo Rollouts - Getting Started Guide](https://argoproj.github.io/argo-rollouts/getting-started/)

### Nice-to-have
- [Flagger - Official Documentation](https://docs.flagger.app/)
- [Progressive Delivery: CI/CD reinvented - James Governor](https://www.infoq.com/articles/progressive-delivery/)
- [Canary Deployments with Argo Rollouts and Prometheus](https://argoproj.github.io/argo-rollouts/analysis/prometheus/)

### Deep-dive
- [Argo Rollouts vs Flagger - Comparison](https://www.infracloud.io/blogs/argo-rollouts-vs-flagger/)
- [Automated Canary Analysis at Netflix](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69)
- [Progressive Delivery at scale - Intuit](https://www.youtube.com/watch?v=mUxLH5tvRBk)

