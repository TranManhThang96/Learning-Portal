# Day 19: Autoscaling — HPA, VPA, Cluster Autoscaler, KEDA

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được** 4 loại autoscaler trong Kubernetes (HPA, VPA, Cluster Autoscaler, KEDA) và khi nào dùng loại nào.
2. **Cấu hình được** HPA cho service HTTP dựa trên CPU/memory metrics.
3. **Load test được** service bằng `hey` hoặc `k6` và quan sát scaling behavior.
4. **Giải thích được** vì sao autoscaling có thể gây hại và cách phòng tránh.
5. **Thiết kế được** autoscaling strategy phù hợp cho các loại workload khác nhau.

---

## 2. Bối cảnh & Động lực

### Vấn đề với manual scaling

```
Scenario: E-commerce platform

Traffic pattern:
  ├── Ngày thường: 100 RPS → 3 pods đủ
  ├── Flash sale: 5000 RPS → cần 50 pods
  ├── Đêm khuya: 10 RPS → 1 pod thừa
  └── Black Friday: 20000 RPS → cần 200 pods

Manual scaling problems:
  ├── Chậm: phải có người on-call scale lên khi traffic tăng
  ├── Lãng phí: chạy 50 pods 24/7 "phòng hờ" flash sale
  ├── Bỏ lỡ: traffic spike ngoài dự kiến → service down
  └── Khó chính xác: bao nhiêu pods là "đủ"?
```

### Chi phí thực tế

| Strategy | Monthly Cost (100 pods × $50/pod) | Availability |
|----------|----------------------------------|-------------|
| **Over-provision** (luôn 100 pods) | $5,000 | 99.99% |
| **Under-provision** (luôn 10 pods) | $500 | 95% (down khi peak) |
| **Autoscaling** (3-100 pods) | $800-$1,200 | 99.9% |

→ Autoscaling giảm 75-85% cost so với over-provisioning, vẫn giữ availability cao.

### Liên hệ với developer

- **HPA** giống auto-scaling worker pool dựa trên queue depth.
- **VPA** giống upgrading machine specs (vertical scale).
- **Cluster Autoscaler** giống thêm servers vào datacenter khi cần.
- **KEDA** giống event-driven architecture: scale based on events (queue messages, cron).

---

## 3. Kiến thức nền tảng

### Horizontal vs Vertical Scaling

```
Horizontal Scaling (HPA):          Vertical Scaling (VPA):
┌───┐ ┌───┐ ┌───┐ ┌───┐           ┌─────────────┐
│Pod│ │Pod│ │Pod│ │Pod│           │   Big Pod    │
│ 1 │ │ 2 │ │ 3 │ │ 4 │           │  More CPU    │
└───┘ └───┘ └───┘ └───┘           │  More RAM    │
  Thêm pods                       └─────────────┘
  + Không downtime                   Tăng resource per pod
  + Fault tolerant                   + Đơn giản hơn
  - Cần stateless app                - Phải restart pod
  - Thêm load balancing              - Có giới hạn (node max)
```

### Metrics Pipeline

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ kubelet  │────▶│metrics-server│────▶│   HPA        │
│ (cAdvisor)│    │  (aggregated │     │ Controller   │
└──────────┘     │   API)       │     └──────┬───────┘
                 └──────────────┘            │
                                             ▼
┌──────────┐     ┌──────────────┐     Scale Deployment
│ App      │────▶│ Prometheus   │     replicas up/down
│ (custom  │     │ Adapter      │
│  metrics)│     └──────────────┘
└──────────┘
```

---

## 4. Deep Dive

### 4.1 HPA — Horizontal Pod Autoscaler

#### Algorithm

```
desiredReplicas = ceil[currentReplicas × (currentMetricValue / desiredMetricValue)]

Ví dụ:
  currentReplicas = 3
  currentCPU = 80%
  targetCPU = 50%
  desiredReplicas = ceil[3 × (80/50)] = ceil[4.8] = 5
  → Scale từ 3 lên 5 pods
```

#### HPA Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70    # Scale khi avg CPU > 70%
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60   # Đợi 60s trước khi scale up thêm
      policies:
        - type: Pods
          value: 4                      # Max scale up 4 pods/lần
          periodSeconds: 60
        - type: Percent
          value: 100                    # Hoặc max 100% replicas/lần
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300  # Đợi 5 phút trước khi scale down
      policies:
        - type: Pods
          value: 1                      # Max scale down 1 pod/lần
          periodSeconds: 120
```

#### HPA Lifecycle

```
Check interval: 15 giây (default)

1. HPA controller query metrics API
2. Tính desiredReplicas theo algorithm
3. So sánh với current replicas
4. Kiểm tra stabilization window
5. Apply scaling policy (max pods/percent per period)
6. Update Deployment replicas
7. Đợi next check interval

Timeline ví dụ:
0s:     CPU 30% → 3 pods (stable)
60s:    CPU 75% → target 70% → scale to 4 pods
120s:   CPU 85% → scale to 5 pods (stabilization window)
180s:   CPU 60% → stable (within target)
480s:   CPU 25% → start scale down window
780s:   CPU 20% → scale down to 4 (after 300s window)
900s:   CPU 20% → scale down to 3
```

### 4.2 VPA — Vertical Pod Autoscaler

```
┌─────────────────────────────────────────────┐
│                 VPA                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │Recommender│  │ Updater  │  │ Admission │ │
│  │          │  │          │  │ Controller│ │
│  │Analyze   │  │Evict pods│  │Set new    │ │
│  │metrics   │  │with wrong│  │resources  │ │
│  │history   │  │resources │  │on create  │ │
│  └──────────┘  └──────────┘  └───────────┘ │
└─────────────────────────────────────────────┘
```

#### VPA Modes

| Mode | Behavior | Pod Restart? | Use Case |
|------|----------|-------------|----------|
| **Off** | Chỉ recommend, không apply | Không | Xem suggestion trước |
| **Initial** | Set resources khi pod tạo mới | Không (existing pods) | Safe, chỉ áp dụng cho pods mới |
| **Auto** | Evict pods và tạo lại với resources mới | **Có** | Full automation |

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  updatePolicy:
    updateMode: "Off"          # Chỉ recommend, không tự sửa
  resourcePolicy:
    containerPolicies:
      - containerName: api
        minAllowed:
          cpu: 50m
          memory: 64Mi
        maxAllowed:
          cpu: "2"
          memory: 2Gi
```

### 4.3 Cluster Autoscaler

```
Cluster Autoscaler Flow:

1. Pod Pending (Unschedulable)
   └── Node không đủ resources cho pod
       └── CA detect pending pod
           └── CA request thêm node từ cloud provider
               └── New node join cluster
                   └── Scheduler đặt pod lên new node

2. Node Underutilized (< 50% allocated)
   └── CA check: tất cả pods trên node có thể chuyển sang node khác?
       └── Yes → CA drain node → remove node
       └── No → giữ node (có pod không move được: local storage, PDB, etc.)

Timeline:
  Scale Up:  2-5 phút (request node → provision → join → ready)
  Scale Down: 10-15 phút (graceful drain → terminate)
```

### 4.4 KEDA — Kubernetes Event-Driven Autoscaling

```
┌──────────────────────────────────────────────┐
│                    KEDA                       │
│                                              │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐ │
│  │Scaler   │───▶│ Metrics  │───▶│  HPA    │ │
│  │(trigger)│    │ Adapter  │    │(native) │ │
│  └─────────┘    └──────────┘    └─────────┘ │
│                                              │
│  Triggers:                                   │
│  ├── Kafka lag                               │
│  ├── RabbitMQ queue length                   │
│  ├── Prometheus query                        │
│  ├── Cron schedule                           │
│  ├── HTTP request rate                       │
│  ├── AWS SQS queue                           │
│  └── 60+ triggers                            │
└──────────────────────────────────────────────┘
```

#### KEDA ScaledObject

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-worker
spec:
  scaleTargetRef:
    name: order-worker
  minReplicaCount: 0          # Scale to zero!
  maxReplicaCount: 50
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: order-processor
        topic: orders
        lagThreshold: "100"    # Scale khi lag > 100 messages
    - type: cron
      metadata:
        timezone: Asia/Ho_Chi_Minh
        start: "0 8 * * *"     # Scale up lúc 8h sáng
        end: "0 22 * * *"      # Scale down lúc 10h tối
        desiredReplicas: "5"
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 So sánh 4 Autoscalers

| Tiêu chí | HPA | VPA | Cluster Autoscaler | KEDA |
|-----------|-----|-----|--------------------|------|
| **Scale gì** | Số lượng pods | Resources per pod | Số lượng nodes | Pods (event-driven) |
| **Direction** | Horizontal | Vertical | Horizontal (nodes) | Horizontal |
| **Metrics** | CPU, memory, custom | CPU, memory history | Pending pods | External events |
| **Restart pods?** | Không | Có (Auto mode) | Không (drain) | Không |
| **Scale to zero** | Không (min=1) | Không áp dụng | Có (nodes) | **Có** |
| **Setup complexity** | Thấp | Trung bình | Trung bình | Thấp-Trung bình |
| **Production readiness** | Rất cao | Cao | Rất cao |Cao |

### 5.2 Khi nào dùng cái nào?

| Scenario | Autoscaler | Lý do |
|----------|-----------|-------|
| **API server, traffic thay đổi** | HPA (CPU/custom) | Scale theo load, stateless |
| **Worker xử lý queue** | KEDA (queue lag) | Scale theo queue depth, scale to zero |
| **Batch job chạy đêm** | KEDA (cron) | Scale theo schedule |
| **Không biết right-size** | VPA (Off mode) | Xem recommendation trước |
| **Cluster nodes không đủ** | Cluster Autoscaler | Thêm nodes khi pods pending |
| **Startup/Cost-sensitive** | KEDA | Scale to zero khi không có traffic |

### 5.3 Khi nào autoscaling GÂY HẠI

| Scenario | Vấn đề | Giải pháp |
|----------|--------|-----------|
| **Database** | Scale replicas = split brain, data inconsistency | Manual scale, operator-based |
| **Stateful service** | Volume không share được giữa pods | Đảm bảo stateless hoặc shared storage |
| **Warm-up time dài** (JVM) | Scale up pods → cold start → latency spike | Warm-up probes, pre-pull images |
| **Connection pool exhaustion** | 10 pods → 50 pods = 50× DB connections | Connection pooler (PgBouncer) |
| **Thundering herd** | Scale down → remaining pods overloaded → scale up lại | Conservative scale-down policy |
| **HPA + VPA cùng lúc** | Conflict: HPA tăng pods, VPA tăng resources → over-provision | Chỉ dùng một (HPA hoặc VPA), không cả hai cho cùng metric |

### 5.4 Anti-patterns

| Anti-pattern | Vấn đề | Cách đúng |
|-------------|--------|-----------|
| HPA target CPU 100% | Không còn headroom cho burst | Target 60-80% |
| minReplicas = 1 cho production | Single pod = single point of failure | minReplicas >= 2 |
| maxReplicas quá cao | Cost explosion, thundering herd | Set sensible max, alert khi gần max |
| Scale down quá nhanh | Traffic fluctuation → flapping | stabilizationWindowSeconds >= 300 |
| HPA không có resource requests | HPA không tính được utilization | Luôn set requests |
| Autoscale database replicas | Data consistency issues | Dùng database operator |

---

## 6. Performance & Scalability ⭐

### 6.1 Scaling Lag

```
Traffic spike detected → Pod ready to serve:

HPA:
  │ Metric scrape interval    │ 15s
  │ HPA check interval        │ 15s
  │ Scale decision             │ ~1s
  │ Pod scheduling             │ ~2s
  │ Image pull (cached)        │ ~5s
  │ Image pull (not cached)    │ 30-120s
  │ Container start            │ ~2s
  │ Readiness probe pass       │ 5-30s
  │ Total (cached)             │ 40-60s
  │ Total (not cached)         │ 60-180s

Cluster Autoscaler (nếu cần new node):
  │ Detect pending pod         │ 15-30s
  │ Request new node           │ ~5s
  │ Node provisioned           │ 60-300s (cloud dependent)
  │ Node join cluster          │ 30-60s
  │ + HPA timeline above       │ 40-60s
  │ Total                      │ 3-7 phút
```

### 6.2 Cold Start & Warm-up

```
Cold start impact per language:

│ Language    │ Start time │ Warm-up time │ Total ready │
│────────────│────────────│──────────────│─────────────│
│ Go         │ < 1s       │ < 1s         │ ~2s         │
│ Node.js    │ 1-3s       │ 1-5s         │ 5-8s        │
│ Python     │ 2-5s       │ 2-5s         │ 5-10s       │
│ Java/Spring│ 15-60s     │ 30-120s      │ 45-180s     │
│ .NET       │ 5-15s      │ 10-30s       │ 15-45s      │

Mitigation:
- Pre-pull images trên nodes: daemonset pull popular images
- Startup probes: cho phép warm-up time dài hơn
- PodDisruptionBudget: giữ minimum pods khi scale down
- Pod topology spread: đảm bảo pods distributed across nodes
```

### 6.3 Connection Pool Management

```
Problem:
  3 pods × 10 DB connections = 30 connections → OK
  Scale to 20 pods × 10 DB connections = 200 connections → DB overloaded!

Solutions:
  1. Connection pooler (PgBouncer, ProxySQL):
     Apps → PgBouncer (100 connections) → PostgreSQL (20 connections)

  2. Dynamic pool sizing:
     pool_size = max_db_connections / max_pods
     20 pods max, 100 DB connections max → pool_size = 5 per pod

  3. Reduce connections per pod khi scale up:
     Sidecar hoặc app-level logic giảm pool size
```

---

## 7. Security & Reliability Considerations

### Runaway Scaling Protection

```yaml
# Luôn set maxReplicas hợp lý
spec:
  maxReplicas: 20    # Safety net — cost control

# Alert khi gần max
# PromQL: kube_horizontalpodautoscaler_status_current_replicas / kube_horizontalpodautoscaler_spec_max_replicas > 0.8
```

### Cost Explosion Prevention

- Set **maxReplicas** cho mọi HPA.
- Set **budget alerts** trên cloud provider.
- Cluster Autoscaler: set **max nodes** per node group.
- KEDA: set **maxReplicaCount** cho ScaledObject.
- Review autoscaling configs trong PR review process.

### Reliability

- **minReplicas >= 2** cho production services (HA).
- **PodDisruptionBudget** để đảm bảo minimum pods khi scale down hoặc node drain.
- **Pod topology spread** để avoid tất cả pods trên cùng node.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2          # Luôn giữ ít nhất 2 pods
  selector:
    matchLabels:
      app: api-server
```

---

## 8. Hands-on Example

### Prerequisites

```bash
# Verify cluster
kind get clusters
# Nếu chưa có: kind create cluster --name devops-lab

# Cài metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
kubectl wait --namespace kube-system --for=condition=ready pod -l k8s-app=metrics-server --timeout=120s

# Cài hey (load testing tool)
# Linux
# wget https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -O hey && chmod +x hey && sudo mv hey /usr/local/bin/
# macOS
# brew install hey
# Hoặc dùng Docker:
# docker run --rm williamyeh/hey -n 1000 -c 10 http://target
```

### 8.1 Deploy Target Service

```yaml
# hpa-demo.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: php-apache
spec:
  replicas: 1
  selector:
    matchLabels:
      app: php-apache
  template:
    metadata:
      labels:
        app: php-apache
    spec:
      containers:
        - name: php-apache
          image: registry.k8s.io/hpa-example
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 200m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: php-apache
spec:
  selector:
    app: php-apache
  ports:
    - port: 80
      targetPort: 80
```

```bash
kubectl apply -f hpa-demo.yaml
kubectl wait --for=condition=ready pod -l app=php-apache --timeout=60s
```

### 8.2 Tạo HPA

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: php-apache-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  minReplicas: 1
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
```

```bash
kubectl apply -f hpa.yaml

# Verify HPA
kubectl get hpa
# NAME              REFERENCE               TARGETS   MINPODS   MAXPODS   REPLICAS
# php-apache-hpa    Deployment/php-apache    0%/50%    1         10        1
```

### 8.3 Load Test

```bash
# Terminal 1: Watch HPA
kubectl get hpa -w

# Terminal 2: Watch pods
kubectl get pods -l app=php-apache -w

# Terminal 3: Generate load
kubectl run -i --tty load-generator --rm --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while sleep 0.01; do wget -q -O- http://php-apache; done"

# Hoặc dùng hey (nếu port-forward):
# kubectl port-forward svc/php-apache 8080:80 &
# hey -z 120s -c 50 http://localhost:8080/
```

### Expected behavior

```
# Trước load:
# php-apache-hpa   Deployment/php-apache   0%/50%    1    10    1

# Sau 30-60s load:
# php-apache-hpa   Deployment/php-apache   250%/50%  1    10    1    ← CPU spike
# php-apache-hpa   Deployment/php-apache   250%/50%  1    10    5    ← Scaling up!

# Sau 2-3 phút:
# php-apache-hpa   Deployment/php-apache   48%/50%   1    10    7    ← Stabilized

# Dừng load, sau 60s (stabilization window):
# php-apache-hpa   Deployment/php-apache   0%/50%    1    10    7    ← Waiting
# php-apache-hpa   Deployment/php-apache   0%/50%    1    10    6    ← Scale down
# ... gradually back to 1
```

### 8.4 Quan sát chi tiết

```bash
# HPA events
kubectl describe hpa php-apache-hpa

# HPA status
kubectl get hpa php-apache-hpa -o yaml | grep -A 20 status

# Pod scaling history
kubectl get events --field-selector reason=SuccessfulRescale --sort-by='.lastTimestamp'
```

### Cleanup

```bash
# Dừng load generator (Ctrl+C hoặc)
kubectl delete pod load-generator --ignore-not-found

kubectl delete hpa php-apache-hpa
kubectl delete -f hpa-demo.yaml
rm -f hpa-demo.yaml hpa.yaml
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Pitfalls

| Pitfall | Triệu chứng | Fix |
|---------|-------------|-----|
| **Metrics-server not installed** | HPA shows `<unknown>/50%` | Cài metrics-server |
| **No resource requests** | HPA cannot compute utilization | Set CPU/memory requests |
| **HPA flapping** | Pods scale up/down liên tục | Tăng `stabilizationWindowSeconds` |
| **HPA + VPA conflict** | Over-provisioning, unpredictable | Không dùng cả hai cho cùng metric |
| **maxReplicas too low** | Traffic spike, pods maxed out | Tăng maxReplicas, add alert |
| **Scale up too slow** | Latency spike khi traffic tăng | Pre-scale trước traffic dự kiến |
| **Image not cached** | Scale up mất 2-3 phút thay vì 30s | DaemonSet pre-pull images |

### 9.2 Debug Commands

```bash
# HPA status
kubectl get hpa
kubectl describe hpa <name>

# Current metrics
kubectl top pods
kubectl top nodes

# Metrics API directly
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods

# HPA events
kubectl get events --field-selector involvedObject.kind=HorizontalPodAutoscaler

# Check if metrics-server working
kubectl get apiservices | grep metrics
# v1beta1.metrics.k8s.io   kube-system/metrics-server   True

# Scale manually (emergency)
kubectl scale deployment <name> --replicas=10
```

### 9.3 Production Case Study: Autoscaling Thundering Herd

#### Context
Fintech platform, payment service chạy 5 pods, HPA target CPU 50%.

#### Symptom
Lúc 9h sáng Thứ Hai, traffic tăng dần → HPA scale 5 → 20 pods trong 3 phút. Nhưng mỗi pod cần 30s warm-up → 15 pods mới responding slowly → load balancer route traffic to them → P99 tăng từ 200ms lên 5s → SLO breach.

#### Root Cause
- Scale up quá nhanh (15 pods cùng lúc).
- Pods mới chưa warm-up nhưng đã nhận traffic (readiness probe pass quá sớm).
- Database connection pool: 20 pods × 10 connections = 200 → vượt max_connections (100).

#### Fix
```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 120
    policies:
      - type: Pods
        value: 3              # Max 3 pods/lần thay vì unlimited
        periodSeconds: 60

# Plus:
# 1. Readiness probe initialDelaySeconds: 30 (chờ warm-up)
# 2. DB connection pool giảm từ 10 → 5 per pod
# 3. Pre-scale trước 9h sáng bằng KEDA cron trigger
```

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Áp dụng |
|-----|---------|
| Day 18 (Resources) | HPA cần resource requests để tính utilization |
| Day 12 (Networking) | Service load balancing giữa scaled pods |
| Day 11 (Workloads) | Deployment replicas là target của HPA |

### Bài sau sẽ mở rộng

- **Day 20 (RBAC/NetworkPolicy)**: Bảo mật autoscaled pods.
- **Day 24 (Production Checklist)**: Autoscaling configuration trong checklist.
- **Day 25 (Mini-project)**: Thêm HPA vào BookStore stack.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) — Official HPA guide.
- [HPA Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/) — Step-by-step tutorial.

### Nice-to-have

- [KEDA Documentation](https://keda.sh/docs/) — Event-driven autoscaling.
- [VPA Documentation](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) — Vertical Pod Autoscaler.
- [Cluster Autoscaler FAQ](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md) — Detailed FAQ.

### Deep-dive

- [Scaling Kubernetes to Zero (KEDA)](https://keda.sh/docs/concepts/scaling-deployments/) — Scale to zero patterns.
- [HPA Algorithm Details](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details) — Math behind HPA.
- [Autoscaling Best Practices (Google Cloud)](https://cloud.google.com/kubernetes-engine/docs/concepts/horizontalpodautoscaler) — Production recommendations.

