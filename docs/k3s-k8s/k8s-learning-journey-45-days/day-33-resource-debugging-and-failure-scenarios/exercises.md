# Bài thực hành - Day 33: Resource Debugging và Failure Scenarios

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Metrics Server hoạt động nếu muốn dùng `kubectl top`.
- Cluster pull được image `python:3.12-alpine`, `busybox:1.36`, `registry.k8s.io/pause:3.10`.
- Không chạy lab này trên production namespace.

## Lab Scenario

Bạn sẽ tạo các lỗi resource có kiểm soát:

- Container bị `OOMKilled`.
- Container `CrashLoopBackOff` vì command/config sai, không phải resource.
- Pod `Pending` vì request quá lớn.
- Workload CPU-bound để quan sát CPU usage/throttling.
- Pod dùng nhiều ephemeral storage để hiểu eviction/disk pressure.

Mục tiêu là đọc đúng evidence, không chỉ fix bằng cách tăng limit. Core path khoảng 105-115 phút; ephemeral storage là optional vì behavior phụ thuộc kubelet/runtime.

## Core Path (105-115 phút)

- Task 1-6 và Task 8-9 là phần bắt buộc.
- Task 7 là optional vì eviction/ephemeral storage phụ thuộc kubelet, runtime và disk pressure của node.

## Task 1: Tạo namespace (5 phút)

```bash
kubectl create namespace day33
kubectl config set-context --current --namespace=day33
```

## Task 2: Tạo Pod bị OOMKilled (20 phút)

Tạo file `oom-demo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memleak
  labels:
    app: memleak
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memleak
  template:
    metadata:
      labels:
        app: memleak
    spec:
      containers:
      - name: app
        image: python:3.12-alpine
        command:
        - python
        - -c
        - |
          import time
          chunks = []
          step = 10 * 1024 * 1024
          i = 0
          while True:
              chunks.append(bytearray(step))
              i += 10
              print(f"allocated approximately {i} MiB", flush=True)
              time.sleep(1)
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
          limits:
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f oom-demo.yaml
kubectl get pod -w
```

Khi Pod restart, mở terminal khác và chạy:

```bash
kubectl get pod -l app=memleak
kubectl describe pod -l app=memleak
kubectl logs deploy/memleak --previous
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- Pod restart và Deployment có Pod mới hoặc container restart count tăng.
- `describe pod` hiển thị `Last State: Terminated`, `Reason: OOMKilled`.
- Exit code thường là `137`.
- `logs --previous` cho thấy memory tăng trước khi bị kill.

### Câu hỏi

- Đây là lỗi application leak, limit thấp hay cả hai?
- Nếu tăng memory limit lên 256Mi, app này có hết lỗi gốc không?
- Vì sao `logs --previous` quan trọng?

## Task 3: CrashLoopBackOff không phải do resource (20 phút)

Tạo file `bad-command.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-command
  labels:
    app: bad-command
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad-command
  template:
    metadata:
      labels:
        app: bad-command
    spec:
      containers:
      - name: app
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "starting"
          echo "FATAL: APP_MODE is required"
          exit 42
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
```

Apply và debug:

```bash
kubectl apply -f bad-command.yaml
kubectl get pod -l app=bad-command
kubectl describe pod -l app=bad-command
kubectl logs deploy/bad-command --previous
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- Pod vào `CrashLoopBackOff`.
- `Last State` có exit code `42`, không phải `OOMKilled`.
- Logs cho thấy lỗi app/config: `APP_MODE is required`.

### Câu hỏi

- Evidence nào chứng minh đây không phải memory limit?
- Vì sao `CrashLoopBackOff` chỉ là symptom, không phải root cause?
- Nếu lỗi do liveness probe quá sớm, evidence sẽ khác gì?

## Task 4: Kiểm tra QoS class (10 phút)

Kiểm tra QoS của Pod `memleak`:

```bash
kubectl get pod -l app=memleak -o jsonpath='{.items[0].status.qosClass}'
```

Tạo Pod `BestEffort`:

```bash
kubectl run besteffort --image=busybox:1.36 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/besteffort --timeout=120s
kubectl get pod besteffort -o jsonpath='{.status.qosClass}'
```

Tạo Pod `Guaranteed`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: guaranteed
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    resources:
      requests:
        cpu: 100m
        memory: 64Mi
      limits:
        cpu: 100m
        memory: 64Mi
```

Lưu thành `guaranteed.yaml`, apply và kiểm tra:

```bash
kubectl apply -f guaranteed.yaml
kubectl wait --for=condition=Ready pod/guaranteed --timeout=120s
kubectl get pod guaranteed -o jsonpath='{.status.qosClass}'
```

### Câu hỏi

- Khi node pressure xảy ra, vì sao `BestEffort` thường bị chọn evict trước?
- Có nên biến mọi service thành `Guaranteed` không?
- `Burstable` phù hợp với workload nào?

## Task 5: Tạo Pod Pending vì request quá lớn (15 phút)

Tạo file `pending-huge-request.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: impossible
spec:
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.10
    resources:
      requests:
        cpu: "999"
        memory: 999Gi
```

Apply và debug:

```bash
kubectl apply -f pending-huge-request.yaml
kubectl get pod impossible
kubectl describe pod impossible
kubectl get events --sort-by=.lastTimestamp
kubectl get nodes
```

### Expected output

- Pod `impossible` ở trạng thái `Pending`.
- Events có thông tin kiểu `Insufficient cpu` hoặc `Insufficient memory`.

### Câu hỏi

- Pod này đã pull image chưa?
- Lỗi nằm ở scheduler hay kubelet?
- Nếu production cần Pod request lớn hơn node hiện tại, bạn fix bằng cách giảm request hay thêm node pool phù hợp?

Cleanup Pod này:

```bash
kubectl delete pod impossible
```

## Task 6: Quan sát CPU-bound workload (20 phút)

Tạo file `cpu-burner.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cpu-burner
  labels:
    app: cpu-burner
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cpu-burner
  template:
    metadata:
      labels:
        app: cpu-burner
    spec:
      containers:
      - name: app
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          while true; do :; done
        resources:
          requests:
            cpu: 20m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f cpu-burner.yaml
kubectl rollout status deploy/cpu-burner
kubectl get pod -l app=cpu-burner
kubectl describe pod -l app=cpu-burner
kubectl top pod
```

`kubectl top pod` chỉ cho thấy CPU usage snapshot. Nó không hiển thị trực tiếp CPU throttling. Nếu có Prometheus/cAdvisor, kiểm tra throttling bằng query trong `document.md`.

### Expected output

- Pod vẫn `Running`, không restart vì CPU vượt limit thường bị throttle chứ không bị kill.
- `kubectl top pod` có thể thấy CPU usage gần limit.
- Throttling trực tiếp cần cAdvisor/Prometheus metrics hoặc node-level cgroup metrics.

### Câu hỏi

- Vì sao Pod không restart dù liên tục dùng CPU?
- `kubectl top pod` có cho bạn thấy throttling trực tiếp không?
- Với API latency-sensitive, CPU limit 50m có thể gây hậu quả gì?

## Task 7: Ephemeral storage failure có kiểm soát (optional, 25 phút)

Task này có thể tạo Pod bị evict hoặc ghi file lỗi tùy kubelet/runtime. Chỉ chạy trong lab.

Tạo file `ephemeral-storage-demo.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: disk-writer
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      i=0
      while true; do
        i=$((i+1))
        dd if=/dev/zero of=/data/blob-$i bs=1M count=10
        echo "wrote $i chunks"
        sleep 1
      done
    volumeMounts:
    - name: data
      mountPath: /data
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
        ephemeral-storage: 20Mi
      limits:
        memory: 64Mi
        ephemeral-storage: 60Mi
  volumes:
  - name: data
    emptyDir: {}
```

Apply và quan sát:

```bash
kubectl apply -f ephemeral-storage-demo.yaml
kubectl get pod disk-writer -w
```

Trong terminal khác:

```bash
kubectl describe pod disk-writer
kubectl logs disk-writer --tail=50
kubectl get events --sort-by=.lastTimestamp
```

### Câu hỏi

- Pod fail vì app write error hay bị kubelet evict?
- Events có nhắc ephemeral storage không?
- Production service nào trong hệ thống của bạn có nguy cơ ghi `/tmp` hoặc log quá nhiều?

## Task 8: Fix có kiểm soát và ghi incident note (20 phút)

Với `memleak`, thử tăng memory limit:

```bash
kubectl set resources deploy/memleak --requests=cpu=50m,memory=64Mi --limits=memory=256Mi
kubectl rollout status deploy/memleak
kubectl get pod -l app=memleak
```

Quan sát lại:

```bash
kubectl logs deploy/memleak --tail=20
kubectl describe pod -l app=memleak
```

Viết incident note:

```text
Symptom:
Scope:
Evidence:
Root cause hypothesis:
Immediate fix:
Long-term fix:
Verification:
Prevention:
```

Gợi ý:

- Immediate fix có thể là tăng limit để giảm impact.
- Long-term fix phải là sửa leak, cấu hình heap hoặc load test lại.
- Prevention là alert `OOMKilled` và review resource trước rollout.

## Task 9: Cleanup

```bash
kubectl delete namespace day33
```

## Stretch Goals

- Chạy Task 7 trên disposable node/cluster để quan sát ephemeral storage eviction.
- Nếu có Prometheus/cAdvisor, kiểm tra metrics throttling thay vì chỉ dựa vào `kubectl top`.

## Checklist hoàn thành

- [ ] Tạo và debug được `OOMKilled`.
- [ ] Tạo và debug được `CrashLoopBackOff` không phải do resource.
- [ ] Dùng được `logs --previous`.
- [ ] Phân biệt được `BestEffort`, `Burstable`, `Guaranteed`.
- [ ] Tạo và giải thích được Pod `Pending` vì request quá lớn.
- [ ] Quan sát được CPU-bound workload và hiểu giới hạn của `kubectl top` với CPU throttling.
- [ ] Hiểu ephemeral storage có thể dẫn tới eviction.
- [ ] Viết được incident note có immediate fix và long-term fix.
