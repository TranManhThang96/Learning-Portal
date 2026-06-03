# Day 19: Bài tập — Autoscaling HPA, VPA, Cluster Autoscaler, KEDA

---

## Bài 1: Easy — Cấu hình HPA và Quan sát Scaling

### Context

Bạn cần deploy một service HTTP, cấu hình HPA dựa trên CPU, và quan sát scaling behavior khi tạo load.

### Yêu cầu

1. Deploy `php-apache` example (hoặc NGINX) với resource requests.
2. Tạo HPA với target CPU 50%, min 1, max 10.
3. Tạo load bằng `busybox` wget loop hoặc `hey`.
4. Quan sát pods scale up.
5. Dừng load, quan sát pods scale down.
6. Ghi lại timeline scaling.
7. Cleanup.

### Expected Outcome

- HPA hiển thị metrics đúng (`kubectl get hpa`).
- Pods scale up khi CPU > 50%.
- Pods scale down sau khi load dừng + stabilization window.
- Timeline rõ ràng: thời điểm scale up, stabilize, scale down.

### Hint

- Dùng image `registry.k8s.io/hpa-example` (tốn CPU khi bị request).
- Mở 3 terminals: watch hpa, watch pods, generate load.
- Dùng `kubectl get hpa -w` để watch real-time.

### Acceptance Criteria

- [ ] Metrics-server hoạt động (`kubectl top pods`).
- [ ] HPA tạo thành công, hiển thị metrics.
- [ ] Pods scale up khi load tăng.
- [ ] Pods scale down khi load giảm.
- [ ] Timeline documented.
- [ ] Cleanup sạch.

### Bonus Challenge

- Thêm memory metric vào HPA (multi-metric).
- Thử thay đổi `targetAverageUtilization` và so sánh scaling behavior.

<details>
<summary>Solution</summary>

```bash
# === 1. Deploy service ===
cat << 'EOF' | kubectl apply -f -
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
EOF

kubectl wait --for=condition=ready pod -l app=php-apache --timeout=60s

# === 2. Create HPA ===
cat << 'EOF' | kubectl apply -f -
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
EOF

# === 3. Watch (Terminal 1) ===
# kubectl get hpa -w

# === 4. Watch pods (Terminal 2) ===
# kubectl get pods -l app=php-apache -w

# === 5. Generate load (Terminal 3) ===
kubectl run -i --tty load-generator --rm --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while sleep 0.01; do wget -q -O- http://php-apache; done"
# Chạy khoảng 2-3 phút, quan sát HPA scale up

# === 6. Stop load (Ctrl+C) ===
# Đợi 60s+ để quan sát scale down

# === 7. Timeline example ===
# 0:00  - Start load, 1 pod, CPU 0%
# 0:30  - CPU 250%, HPA calculating
# 0:45  - Scale to 5 pods
# 1:30  - CPU 48%, stabilized at 7 pods
# 3:00  - Stop load
# 3:30  - CPU 0%
# 4:30  - Scale down to 6
# 5:30  - Scale down to 5
# ...
# 8:00  - Back to 1 pod

# === Cleanup ===
kubectl delete pod load-generator --ignore-not-found
kubectl delete hpa php-apache-hpa
kubectl delete deploy php-apache
kubectl delete svc php-apache
```

</details>

---

## Bài 2: Medium — HPA với Custom Behavior và Scaling Policies

### Context

Bạn cần thiết kế autoscaling cho API server production. Yêu cầu:
- Scale up nhanh khi traffic tăng.
- Scale down chậm và từng bước (tránh flapping).
- Minimum 2 pods cho HA.

### Yêu cầu

1. Deploy NGINX service với 2 replicas.
2. Tạo HPA với custom behavior:
   - Scale up: max 4 pods mỗi 60s, stabilization 30s.
   - Scale down: max 1 pod mỗi 120s, stabilization 300s.
   - Min 2, Max 15.
   - Target CPU 60%.
3. Tạo PodDisruptionBudget: minAvailable 2.
4. Load test và quan sát:
   - Ghi lại thời gian từ load start → first scale up.
   - Ghi lại thời gian từ load stop → back to min replicas.
5. So sánh với HPA mặc định (không custom behavior).

### Expected Outcome

- Scale up nhanh (30-60s sau khi detect).
- Scale down chậm và từng bước (mất 5-10 phút).
- PDB đảm bảo luôn có ít nhất 2 pods available.

### Hint

- `behavior.scaleUp.policies` và `behavior.scaleDown.policies`.
- `stabilizationWindowSeconds` quyết định bao lâu phải stable trước khi scale tiếp.
- PDB: `minAvailable: 2` hoặc `maxUnavailable: 1`.

### Acceptance Criteria

- [ ] HPA với custom behavior tạo thành công.
- [ ] Scale up nhanh (< 60s).
- [ ] Scale down chậm, từng pod (> 300s stabilization).
- [ ] PDB tạo thành công.
- [ ] So sánh behavior với và không custom policies.
- [ ] Timeline có ghi chú rõ ràng.

### Bonus Challenge

- Thêm second metric: memory utilization 80%.
- Simulate scenario: traffic spike ngắn 2 phút → verify không scale down ngay.
- Viết HPA config template cho 3 loại workload: API, worker, batch.

<details>
<summary>Solution</summary>

```bash
# === 1. Deploy ===
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: registry.k8s.io/hpa-example
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 150m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api-server
spec:
  selector:
    app: api-server
  ports:
    - port: 80
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-server
EOF

kubectl wait --for=condition=ready pod -l app=api-server --timeout=60s

# === 2. Custom HPA ===
cat << 'EOF' | kubectl apply -f -
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
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
      selectPolicy: Min
EOF

# === 3. Load test ===
echo "Start time: $(date)"
kubectl run -i --tty load-gen --rm --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while sleep 0.01; do wget -q -O- http://api-server; done"

# In another terminal:
# kubectl get hpa -w
# kubectl get pods -l app=api-server -w

# After stopping load, note scale-down timing (should be slow)

# === 4. Verify PDB ===
kubectl get pdb api-pdb
# ALLOWED DISRUPTIONS should reflect minAvailable=2

# === Cleanup ===
kubectl delete pod load-gen --ignore-not-found
kubectl delete hpa api-hpa
kubectl delete pdb api-pdb
kubectl delete deploy api-server
kubectl delete svc api-server
```

</details>

---

## Bài 3: Hard — Multi-tier Autoscaling Strategy Design

### Context

Bạn là platform engineer thiết kế autoscaling cho hệ thống gồm:
- **Frontend** (React static): traffic-driven, lightweight.
- **API Gateway**: traffic-driven, latency-sensitive.
- **Order Service**: traffic + queue-driven.
- **Notification Worker**: queue-driven, scale to zero khi idle.
- **PostgreSQL**: KHÔNG autoscale.

### Yêu cầu

1. Thiết kế autoscaling strategy cho từng component:
   - Chọn loại autoscaler (HPA/VPA/KEDA/none).
   - Chọn metrics.
   - Set min/max replicas.
   - Set scaling policies (up/down behavior).
2. Deploy frontend + API gateway + order service lên kind cluster.
3. Cấu hình HPA cho frontend và API gateway.
4. Viết KEDA ScaledObject giả lập cho notification worker (dùng cron trigger thay vì Kafka).
5. Load test API gateway và quan sát cascading scale: API gateway scale up → order service cần scale up.
6. Viết document: autoscaling decision matrix + cost analysis.

### Expected Outcome

- 3 services deployed với autoscaling configured.
- Load test trigger cascading scale.
- Decision matrix rõ ràng cho mỗi component.
- Cost analysis: so sánh static provisioning vs autoscaling.

### Hint

- Frontend: HPA CPU 70%, min 1, max 5.
- API Gateway: HPA CPU 60%, min 2, max 20.
- Order Service: HPA CPU 70%, min 2, max 15.
- Notification Worker: KEDA cron trigger (simulate queue).
- PostgreSQL: manual, nhắc dùng VPA Off mode để xem recommendation.

### Acceptance Criteria

- [ ] 4 components có autoscaling strategy rõ ràng.
- [ ] HPA configured và hoạt động cho 2+ services.
- [ ] KEDA config viết đúng (có thể không cài KEDA, chỉ viết config).
- [ ] Load test trigger scaling thành công.
- [ ] Decision matrix documented.
- [ ] Cost analysis completed.
- [ ] Cleanup sạch.

### Bonus Challenge

- Cài KEDA trên kind và test cron trigger hoạt động.
- Thêm Pod Topology Spread constraints cho scaled pods.
- Viết Grafana dashboard query (PromQL) để visualize scaling metrics.

<details>
<summary>Solution</summary>

```bash
# === Decision Matrix ===
cat << 'MATRIX'
| Component            | Autoscaler | Metric          | Min | Max | ScaleUp | ScaleDown |
|----------------------|-----------|-----------------|-----|-----|---------|-----------|
| Frontend             | HPA       | CPU 70%         | 1   | 5   | Fast    | Slow      |
| API Gateway          | HPA       | CPU 60%         | 2   | 20  | Fast    | Very Slow |
| Order Service        | HPA       | CPU 70%         | 2   | 15  | Medium  | Slow      |
| Notification Worker  | KEDA      | Queue/Cron      | 0   | 10  | Fast    | Fast      |
| PostgreSQL           | None      | VPA Off (recommend only) | 1 | 1 | Manual | Manual |
MATRIX

# === Deploy Services ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: autoscale-demo
---
# Frontend
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: autoscale-demo
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
        - name: nginx
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 32Mi
            limits:
              cpu: 200m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: autoscale-demo
spec:
  selector:
    app: frontend
  ports:
    - port: 80
---
# API Gateway
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: autoscale-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: api
          image: registry.k8s.io/hpa-example
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 150m
              memory: 64Mi
            limits:
              cpu: 500m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: autoscale-demo
spec:
  selector:
    app: api-gateway
  ports:
    - port: 80
---
# Order Service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: autoscale-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
        - name: order
          image: registry.k8s.io/hpa-example
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 400m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: autoscale-demo
spec:
  selector:
    app: order-service
  ports:
    - port: 80
---
# HPA - API Gateway
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: autoscale-demo
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
---
# HPA - Order Service
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
  namespace: autoscale-demo
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 180
---
# PDB
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: autoscale-demo
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-gateway
EOF

# === KEDA ScaledObject (config only, requires KEDA installed) ===
cat << 'KEDA'
# notification-worker-keda.yaml (NOT applied - requires KEDA installation)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: notification-worker
  namespace: autoscale-demo
spec:
  scaleTargetRef:
    name: notification-worker
  minReplicaCount: 0
  maxReplicaCount: 10
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: cron
      metadata:
        timezone: Asia/Ho_Chi_Minh
        start: "0 8 * * 1-5"
        end: "0 20 * * 1-5"
        desiredReplicas: "3"
KEDA

# === Load Test ===
kubectl wait --namespace autoscale-demo --for=condition=ready pod --all --timeout=60s

# Watch
# Terminal 1: kubectl get hpa -n autoscale-demo -w
# Terminal 2: kubectl get pods -n autoscale-demo -w

# Generate load on API gateway
kubectl run -n autoscale-demo -i --tty load-gen --rm --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while sleep 0.01; do wget -q -O- http://api-gateway; done"

# === Cost Analysis ===
cat << 'COST'
Cost Analysis: Static vs Autoscaling

Static Provisioning (always max):
  Frontend: 5 pods × $10/mo = $50
  API Gateway: 20 pods × $15/mo = $300
  Order Service: 15 pods × $12/mo = $180
  Notification: 10 pods × $8/mo = $80
  Total: $610/mo

Autoscaling (average):
  Frontend: ~1.5 pods × $10/mo = $15
  API Gateway: ~4 pods × $15/mo = $60
  Order Service: ~3 pods × $12/mo = $36
  Notification: ~2 pods × $8/mo = $16
  Total: $127/mo

Savings: $483/mo (79% reduction)
COST

# === Cleanup ===
kubectl delete namespace autoscale-demo
```

</details>

---

## Solution / Reference Implementation

Các reference implementation đầy đủ nằm trong từng block `<details>` của Bài 1, Bài 2 và Bài 3 ở trên. Khi tự chấm bài, verify tối thiểu các điểm sau:

```bash
kubectl get hpa -n autoscale-demo
kubectl describe hpa <hpa-name> -n autoscale-demo
kubectl get pods -n autoscale-demo -w
kubectl top pods -n autoscale-demo
```

