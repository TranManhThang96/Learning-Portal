# Bài thực hành - Day 14: Namespace, labels, selectors và annotations

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `nginx:1.27-alpine`.
- Đã hoàn thành Day 13 hoặc nắm cơ bản `Deployment` và `Service`.

## Lab Scenario

Bạn tổ chức resource cho một service `orders-api` theo namespace và labels chuẩn. Sau đó bạn tạo Service selector đúng, inject lỗi selector sai để thấy Service mất endpoints, rồi dùng annotations để gắn metadata vận hành.

Core path khoảng 105-115 phút: Task 1-5 và cleanup. Scope inventory chi tiết, prod duplicate và NetworkPolicy nằm trong `Stretch Goals`.

## Task 1: Tạo namespaces, ResourceQuota và LimitRange (25 phút)

### Mục tiêu

Tạo boundary logic cho `dev` và `prod`, đồng thời thêm guardrail tài nguyên tối thiểu cho namespace lab.

### Các bước thực hiện

Tạo file `namespaces.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: day14-dev
  labels:
    environment: dev
    owner: platform
    cost-center: learning
---
apiVersion: v1
kind: Namespace
metadata:
  name: day14-prod
  labels:
    environment: prod
    owner: platform
    cost-center: learning
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: day14-dev-quota
  namespace: day14-dev
spec:
  hard:
    pods: "10"
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.cpu: "2"
    limits.memory: 2Gi
---
apiVersion: v1
kind: LimitRange
metadata:
  name: day14-dev-defaults
  namespace: day14-dev
spec:
  limits:
  - type: Container
    defaultRequest:
      cpu: 20m
      memory: 32Mi
    default:
      cpu: 100m
      memory: 128Mi
```

Apply:

```bash
kubectl apply -f namespaces.yaml
kubectl get namespaces --show-labels
kubectl get resourcequota,limitrange -n day14-dev
kubectl config set-context --current --namespace=day14-dev
```

### Expected output

- Có namespace `day14-dev` và `day14-prod`.
- Labels `environment`, `owner`, `cost-center` hiển thị đúng.
- `day14-dev` có `ResourceQuota` và `LimitRange` để nhắc rằng namespace production cần guardrail, không chỉ là folder logic.

## Task 2: Deploy orders-api với label taxonomy rõ ràng (25 phút)

### Mục tiêu

Tạo `Deployment` có labels dùng được cho query và selector.

### Các bước thực hiện

Tạo file `orders-api.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  namespace: day14-dev
  labels:
    app.kubernetes.io/name: orders
    app.kubernetes.io/instance: orders-dev
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: commerce
    app.kubernetes.io/managed-by: kubectl
    environment: dev
    owner: platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: orders
      app.kubernetes.io/component: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: orders
        app.kubernetes.io/instance: orders-dev
        app.kubernetes.io/component: api
        app.kubernetes.io/part-of: commerce
        environment: dev
        owner: platform
    spec:
      containers:
      - name: nginx
        image: nginx:1.27-alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
```

Apply và query:

```bash
kubectl apply -f orders-api.yaml
kubectl rollout status deployment/orders-api -n day14-dev
kubectl get pods -n day14-dev --show-labels
kubectl get pods -n day14-dev -l app.kubernetes.io/name=orders
kubectl get pods -n day14-dev -l 'environment in (dev,staging)'
```

### Expected output

- Deployment có 2 Pods running.
- Label queries trả về đúng 2 Pods.

## Task 3: Tạo Service với selector đúng (20 phút)

### Mục tiêu

Thấy selector tạo endpoints cho Service.

### Các bước thực hiện

Tạo file `orders-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-api
  namespace: day14-dev
  labels:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
  ports:
  - name: http
    port: 80
    targetPort: 80
```

Apply và kiểm tra:

```bash
kubectl apply -f orders-service.yaml
kubectl get svc,endpoints,endpointslice -n day14-dev
kubectl describe service orders-api -n day14-dev
```

### Expected output

- Service `orders-api` có endpoints trỏ tới Pod IP.
- EndpointSlice có addresses tương ứng với Pods Ready.

## Task 4: Inject lỗi selector sai và debug (25 phút)

### Mục tiêu

Tạo lỗi Service không có endpoints do selector không match labels.

### Lỗi cần tạo

Patch selector của Service sang component sai:

```bash
kubectl patch service orders-api -n day14-dev -p '{"spec":{"selector":{"app.kubernetes.io/name":"orders","app.kubernetes.io/component":"worker"}}}'
kubectl get svc,endpoints,endpointslice -n day14-dev
kubectl describe service orders-api -n day14-dev
```

Điều tra labels:

```bash
kubectl get pods -n day14-dev --show-labels
kubectl get pods -n day14-dev -l app.kubernetes.io/component=worker
kubectl get pods -n day14-dev -l app.kubernetes.io/component=api
```

### Symptom

- Service vẫn có `ClusterIP`.
- Endpoints rỗng hoặc không có address Ready.
- Pod vẫn Running nên lỗi dễ bị nhầm là network issue.

### Cách fix

```bash
kubectl patch service orders-api -n day14-dev -p '{"spec":{"selector":{"app.kubernetes.io/name":"orders","app.kubernetes.io/component":"api"}}}'
kubectl get endpoints,endpointslice -n day14-dev
```

### Production note

Trước khi đổi selector production, kiểm tra selector đó có được dùng bởi `Service`, `NetworkPolicy`, `PodDisruptionBudget`, dashboards hoặc alert rules không.

## Task 5: Dùng annotations cho metadata vận hành (15 phút)

### Mục tiêu

Gắn metadata không dùng để select object.

### Các bước thực hiện

```bash
kubectl annotate deployment orders-api -n day14-dev runbook.example.com/url=https://wiki.example.com/orders-runbook
kubectl annotate deployment orders-api -n day14-dev git.example.com/commit=abc1234
kubectl describe deployment orders-api -n day14-dev
```

Kiểm tra annotations bằng jsonpath:

```bash
kubectl get deployment orders-api -n day14-dev -o jsonpath='{.metadata.annotations}'
```

Xóa annotation:

```bash
kubectl annotate deployment orders-api -n day14-dev git.example.com/commit-
```

### Expected output

- Annotation xuất hiện trong metadata.
- Không ảnh hưởng Service endpoints vì selector dùng labels, không dùng annotations.

## Stretch Goal: Kiểm tra namespace scope và cluster scope (15 phút)

### Mục tiêu

Biết resource nào namespaced và resource nào cluster-scoped.

### Các bước thực hiện

```bash
kubectl api-resources --namespaced=true
kubectl api-resources --namespaced=false
kubectl get all -n day14-dev
kubectl get all -n day14-prod
kubectl get configmap,secret,resourcequota,limitrange,rolebinding,networkpolicy -n day14-dev
kubectl get nodes
```

### Expected output

- Workload nằm trong `day14-dev`.
- `nodes` là cluster-scoped, không thuộc namespace.
- `kubectl get all` không thật sự liệt kê mọi resource; quota/limitrange/secret/rbac/policy cần query riêng hoặc dùng `api-resources`.

## Cleanup

```bash
kubectl delete namespace day14-dev day14-prod
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Tạo Service đúng tên nhưng selector sai.
- Query thiếu `-n` nên nhìn nhầm namespace.
- Dùng namespace như security boundary duy nhất.
- Dùng label quá chung như `app=api`.
- Đổi label selector của Deployment sau khi đã chạy.
- Đặt dữ liệu nhạy cảm vào labels/annotations.

## Stretch Goals

- Tạo cùng `orders-api` ở `day14-prod` với `environment=prod`, sau đó query `kubectl get pods -A -l app.kubernetes.io/name=orders`.
- Thử sửa `Deployment.spec.selector` sau khi đã tạo và quan sát lỗi immutable selector. Không làm trên production.
- Tạo một `NetworkPolicy` ở Day 19 dùng lại label taxonomy hôm nay.
- Viết script audit các namespace thiếu label `owner`.
