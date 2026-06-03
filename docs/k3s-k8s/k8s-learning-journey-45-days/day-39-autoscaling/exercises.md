# Bài thực hành - Day 39: Autoscaling

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Metrics API hoạt động để làm HPA CPU lab:

```bash
kubectl top nodes
kubectl top pods -A
```

Nếu `kubectl top` không chạy, đọc lỗi và coi Task 2-5 là walkthrough. Một số K3s/k3d lab không có metrics-server sẵn; chỉ cài metrics-server trong cluster lab dùng một lần theo tài liệu chính thức của môi trường đó. Không cài hoặc sửa metrics-server bừa trong production/shared cluster nếu chưa hiểu setup hiện tại.

## Lab Scenario

Bạn sẽ deploy một app tạo CPU load, bật HPA, tạo traffic để scale replicas, sau đó debug các lỗi thường gặp: thiếu metrics và thiếu CPU request. Scenario Pod Pending sẽ dùng Deployment riêng không bị HPA điều khiển để kết quả deterministic hơn. Cuối bài có worksheet cho VPA, Cluster Autoscaler và KEDA.

## Core Path (105-115 phút)

- Task 1-6 và Task 9 là phần bắt buộc nếu Metrics API hoạt động.
- Nếu Metrics API không hoạt động, làm Task 2-6 như walkthrough đọc manifest/output mẫu và ghi rõ blocker.
- Task 7-8 là stretch vì phụ thuộc capacity cluster và tool autoscaling ngoài HPA.

## Task 1: Tạo namespace và kiểm tra metrics (10 phút)

```bash
kubectl create namespace day39
kubectl top nodes
kubectl top pods -A
kubectl get apiservice v1beta1.metrics.k8s.io
```

### Câu hỏi

- Nếu `kubectl top` lỗi, HPA CPU có hoạt động không?
- Metrics-server khác Prometheus ở điểm nào trong HPA resource metrics?

## Task 2: Deploy workload có CPU request (20 phút)

Tạo file `hpa-demo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: php-apache
  namespace: day39
spec:
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
            memory: 128Mi
          limits:
            memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: php-apache
  namespace: day39
spec:
  selector:
    app: php-apache
  ports:
  - port: 80
    targetPort: 80
```

Apply:

```bash
kubectl apply -f hpa-demo.yaml
kubectl wait --for=condition=Available deploy/php-apache -n day39 --timeout=180s
kubectl get deploy,svc,pod -n day39
```

### Expected output

- Deployment Ready.
- Service trỏ tới Pod.

### Câu hỏi

- Vì sao container cần CPU request để HPA CPU utilization có ý nghĩa?
- Vì sao ví dụ không đặt CPU limit?

## Task 3: Tạo HPA (15 phút)

```bash
kubectl autoscale deployment php-apache -n day39 --cpu-percent=50 --min=1 --max=10
kubectl get hpa -n day39
kubectl describe hpa php-apache -n day39
```

Nếu muốn YAML rõ hơn:

```bash
kubectl get hpa php-apache -n day39 -o yaml
```

Optional: nếu cluster hỗ trợ `autoscaling/v2`, thay HPA bằng manifest có `behavior` để scale-down ổn định hơn:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: php-apache
  namespace: day39
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
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
      - type: Pods
        value: 4
        periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
      selectPolicy: Max
```

Lưu thành `hpa-behavior.yaml` rồi apply:

```bash
kubectl apply -f hpa-behavior.yaml
kubectl describe hpa php-apache -n day39
```

### Expected output

- HPA được tạo.
- Metrics có thể mất 1-2 phút mới hiện thay vì `<unknown>`.

### Câu hỏi

- `TARGETS` trong `kubectl get hpa` đang so sánh gì?
- HPA sync không tức thì; delay đến từ đâu?

## Task 4: Tạo load và quan sát scale up (30 phút)

Tạo Pod generate load:

```bash
kubectl run -n day39 load-generator --rm -it --image=busybox:1.36 --restart=Never -- /bin/sh
```

Trong shell của Pod:

```sh
while true; do wget -q -O- http://php-apache.day39.svc.cluster.local; done
```

Ở terminal khác:

```bash
kubectl get hpa php-apache -n day39 -w
kubectl get deploy php-apache -n day39 -w
kubectl top pods -n day39
```

Dừng load generator bằng `Ctrl+C`.

### Expected output

- CPU utilization tăng.
- HPA tăng desired replicas.
- Deployment tạo thêm Pods.

### Câu hỏi

- HPA scale nhanh hay chậm so với kỳ vọng?
- Pod mới mất bao lâu để Ready?
- Nếu node không đủ capacity, HPA vẫn tăng desired replicas không?

## Task 5: Quan sát scale down (20 phút)

Sau khi dừng load:

```bash
kubectl get hpa php-apache -n day39 -w
kubectl get deploy php-apache -n day39 -w
```

Chờ vài phút để thấy scale-down.

### Câu hỏi

- Vì sao scale-down thường chậm hơn scale-up?
- Production có nên scale-down ngay khi CPU giảm không?
- Graceful shutdown ảnh hưởng scale-down thế nào?

## Task 6: Inject lỗi thiếu CPU request (20 phút)

Tạo deployment không có CPU request:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: no-request
  namespace: day39
spec:
  selector:
    matchLabels:
      app: no-request
  template:
    metadata:
      labels:
        app: no-request
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
        resources:
          limits:
            memory: 128Mi
```

Lưu thành `no-request.yaml`, apply và tạo HPA:

```bash
kubectl apply -f no-request.yaml
kubectl autoscale deployment no-request -n day39 --cpu-percent=50 --min=1 --max=5
kubectl describe hpa no-request -n day39
```

### Expected output

- HPA có thể báo không tính được CPU utilization vì thiếu request.

### Câu hỏi

- Vì sao CPU usage tuyệt đối không đủ cho target utilization?
- Nếu chart không bắt buộc CPU request, HPA có đáng tin không?

## Task 7: Pending Pods khi scale vượt capacity (optional, 20 phút)

Không dùng `php-apache` cho task này vì Deployment đó đang bị HPA quản lý. Dùng Deployment riêng không có HPA để chỉ quan sát scheduler/capacity.

Tạo file `capacity-demo.yaml` với CPU request rất cao:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: capacity-demo
  namespace: day39
spec:
  replicas: 3
  selector:
    matchLabels:
      app: capacity-demo
  template:
    metadata:
      labels:
        app: capacity-demo
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
        resources:
          requests:
            cpu: "100"
            memory: 64Mi
          limits:
            memory: 128Mi
```

Apply và debug:

```bash
kubectl apply -f capacity-demo.yaml
kubectl get pods -n day39 -l app=capacity-demo
kubectl describe pod <pending-pod> -n day39
kubectl get events -n day39 --sort-by=.lastTimestamp
```

Cleanup riêng cho scenario:

```bash
kubectl delete -f capacity-demo.yaml
```

### Expected output

- Pods của `capacity-demo` ở trạng thái `Pending`.
- Events có `Insufficient cpu` hoặc thông điệp tương tự.
- HPA của `php-apache` không can thiệp vào Deployment này.

### Câu hỏi

- HPA scale replicas có tạo được node mới không?
- Cluster Autoscaler sẽ cần điều kiện gì để can thiệp?
- Node pool max size ảnh hưởng thế nào?

## Task 8: KEDA/VPA/Cluster Autoscaler worksheet (20 phút)

Không cần cài tool. Điền cho 3 workload:

```text
Workload 1: public API
Scaling method:
Metric:
minReplicas:
maxReplicas:
Risks:

Workload 2: Kafka order worker
Scaling method:
Metric:
minReplicas:
maxReplicas:
Risks:

Workload 3: nightly batch processor
Scaling method:
Metric/schedule:
Risks:

Node scaling:
Node pool:
Headroom:
Max nodes:
Scale-up delay accepted:
```

### Câu hỏi

- Workload nào nên dùng KEDA?
- Workload nào nên chỉ dùng VPA recommendation trước?
- Downstream nào giới hạn `maxReplicas`?

## Task 9: Cleanup

```bash
kubectl delete namespace day39
```

Xóa file local nếu không cần:

```bash
Remove-Item -Force .\hpa-demo.yaml,.\no-request.yaml,.\hpa-behavior.yaml,.\capacity-demo.yaml -ErrorAction SilentlyContinue
```

Linux/macOS:

```bash
rm -f ./hpa-demo.yaml ./no-request.yaml ./hpa-behavior.yaml ./capacity-demo.yaml
```

## Stretch Goals

- Chạy Task 7 với Deployment riêng để tạo Pending Pods mà không bị HPA can thiệp.
- Render hoặc apply HPA `autoscaling/v2` có `behavior` nếu cluster hỗ trợ.
- Viết worksheet chọn HPA, VPA, KEDA hoặc Cluster Autoscaler cho 3 workload thực tế.

## Checklist hoàn thành

- [ ] Kiểm tra được metrics API.
- [ ] Deploy workload có CPU request.
- [ ] Tạo và đọc được HPA.
- [ ] Generate load và quan sát scale-up/scale-down.
- [ ] Debug được HPA thiếu CPU request.
- [ ] Hiểu Pod Pending sau scale liên quan tới capacity/node autoscaling.
- [ ] Chọn được HPA/VPA/KEDA/Cluster Autoscaler cho workload cụ thể.
