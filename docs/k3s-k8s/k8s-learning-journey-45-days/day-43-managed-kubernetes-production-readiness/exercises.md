# Bài thực hành - Day 43: Managed Kubernetes và Production Readiness

## Prerequisites

- Kubernetes/K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- `metrics-server` nếu muốn test HPA/top.
- Multi-node cluster là tốt nhất, nhưng single-node vẫn làm được phần manifest/checklist.

## Lab Scenario

Bạn sẽ lấy một Deployment đơn giản và nâng cấp dần thành workload production-ready hơn: resources, probes, PDB, HPA, topology spread, securityContext và NetworkPolicy. Sau đó bạn sẽ chạy một readiness review như khi chuẩn bị lên EKS/GKE/AKS.

## Core Path (105-115 phút)

- Task 1-6 và Cleanup là phần bắt buộc.
- Stretch Goals bên dưới dành cho topology spread, NetworkPolicy và quota nếu còn thời gian.

## Task 1: Deploy baseline app (15 phút)

```bash
kubectl create namespace day43
```

Tạo `api-baseline.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: day43
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
        app.kubernetes.io/part-of: logistics
    spec:
      containers:
      - name: api
        image: nginxinc/nginx-unprivileged:1.25-alpine
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: day43
spec:
  selector:
    app.kubernetes.io/name: api
  ports:
  - port: 80
    targetPort: 8080
```

Apply:

```bash
kubectl apply -f api-baseline.yaml
kubectl get deploy,pod,svc -n day43
```

### Review nhanh

Baseline thiếu gì để production-ready?

- Resources?
- Probes?
- PDB?
- Security?
- Scaling?
- Topology?
- Observability labels?

## Task 2: Thêm resources và probes (20 phút)

Tạo `api-production.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: day43
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: logistics
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
        app.kubernetes.io/part-of: logistics
    spec:
      containers:
      - name: api
        image: nginxinc/nginx-unprivileged:1.25-alpine
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          periodSeconds: 10
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            memory: 128Mi
        securityContext:
          runAsNonRoot: true
          runAsUser: 101
          runAsGroup: 101
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: day43
spec:
  selector:
    app.kubernetes.io/name: api
  ports:
  - port: 80
    targetPort: 8080
```

Apply:

```bash
kubectl apply -f api-production.yaml
kubectl rollout status deploy/api -n day43
kubectl describe deploy/api -n day43
```

Nếu bạn đã apply phiên bản cũ của lab có selector `app: api`, Kubernetes sẽ reject vì `Deployment.spec.selector` là immutable. Xóa và tạo lại Deployment trong lab:

```bash
kubectl delete deploy api -n day43
kubectl apply -f api-production.yaml
```

### Expected output

- Deployment rollout thành công.
- Pod có requests/limits và probes.

## Task 3: Thêm PDB và kiểm tra drain readiness (20 phút)

Tạo `pdb.yaml`:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api
  namespace: day43
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: api
```

Apply:

```bash
kubectl apply -f pdb.yaml
kubectl get pdb -n day43
kubectl describe pdb api -n day43
```

Nếu có multi-node, thử drain dry-run bằng cách chọn node có Pod:

```bash
kubectl get pod -n day43 -o wide
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --dry-run=server
```

### Câu hỏi

- Với `replicas: 3`, `minAvailable: 2` cho phép mất mấy Pod voluntary?
- Nếu replicas giảm còn 1 thì PDB này gây vấn đề gì?

## Task 4: Thêm HPA (20 phút)

Tạo `hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
  namespace: day43
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

Apply:

```bash
kubectl apply -f hpa.yaml
kubectl get hpa -n day43
kubectl describe hpa api -n day43
```

Nếu metrics chưa có, bạn sẽ thấy HPA không có current metric. Đây là lỗi học được, không phải lab hỏng.

### Câu hỏi

- Vì sao HPA CPU cần `requests.cpu`?
- Production có nên scale chỉ theo CPU không?

## Task 5: Inject lỗi PDB quá chặt (15 phút)

Patch PDB:

```bash
kubectl patch pdb api -n day43 --type merge -p '{"spec":{"minAvailable":3}}'
kubectl describe pdb api -n day43
```

Với `replicas: 3`, voluntary disruption allowed sẽ là 0.

Khôi phục:

```bash
kubectl patch pdb api -n day43 --type merge -p '{"spec":{"minAvailable":2}}'
```

### Câu hỏi

- Trong upgrade node pool, PDB này có thể làm gì?
- Làm sao cân bằng HA và upgrade velocity?

## Task 6: Managed Kubernetes review worksheet (25 phút)

Tạo file `managed-k8s-review.md` và trả lời:

```markdown
# Managed Kubernetes Review

## Target provider
- EKS/GKE/AKS:

## Node pools
- system:
- general:
- spot/workers:
- stateful:

## Networking
- CNI:
- Ingress controller:
- LoadBalancer type:
- DNS/cert:

## Storage
- Default StorageClass:
- Snapshot support:
- Stateful workload policy:

## Security
- Workload identity:
- RBAC:
- Pod Security:
- NetworkPolicy:

## Operations
- GitOps:
- Observability:
- Backup:
- Upgrade plan:
- Cost labels:
```

### Expected output

- Một checklist rõ ràng để dùng cho capstone hoặc production design review.

## Cleanup

```bash
kubectl delete namespace day43
```

## Common Pitfalls

- Thêm HPA nhưng quên `resources.requests`.
- PDB `minAvailable` bằng số replicas nên drain kẹt.
- Probe trỏ vào endpoint cần dependency external nên rollout fail khi dependency chậm.
- Không tách node pool system và app nên monitoring/ingress bị app chen tài nguyên.
- Dùng static cloud key trong Secret thay vì workload identity.

## Stretch Goals

- Thêm `topologySpreadConstraints` vào Deployment.
- Thêm NetworkPolicy chỉ cho phép traffic từ namespace gateway.
- Tạo `ResourceQuota` và `LimitRange` cho namespace.
- Viết upgrade runbook từ Kubernetes version N sang N+1.
