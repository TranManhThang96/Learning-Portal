# Bài thực hành - Day 08: Pod lifecycle và multi-container patterns

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Đã hoàn thành Day 07 hoặc nắm các lệnh `describe`, `logs -c`, `events`.

## Lab Scenario

Bạn cần deploy một Pod có bước bootstrap, một Pod nhiều container dùng shared volume, và một workload có probes. Sau đó cố tình cấu hình sai readiness để quan sát sự khác biệt giữa `Running` và `Ready`.

## Core Path trong 2 giờ

Core path là Task 1-6, khoảng 110-115 phút. Các bài liveness restart storm, native sidecar và benchmark resource nằm ở `Stretch Goals`.

## Task 1: Tạo namespace và quan sát Pod lifecycle cơ bản (10 phút)

### Mục tiêu

Chuẩn bị namespace riêng và đọc status theo thời gian.

### Các bước thực hiện

```bash
kubectl create namespace day08
kubectl config set-context --current --namespace=day08
kubectl run simple-nginx --image=nginx:1.27 --port=80
kubectl get pods -w
```

Dừng watch bằng `Ctrl+C`, rồi chạy:

```bash
kubectl describe pod simple-nginx
kubectl get pod simple-nginx -o jsonpath='{.status.phase}{"\n"}'
kubectl get pod simple-nginx -o jsonpath='{.status.conditions}{"\n"}'
```

### Expected output

- Pod chuyển từ `Pending` sang `Running`.
- Conditions có `PodScheduled`, `Initialized`, `ContainersReady`, `Ready`.

## Task 2: Init container tạo nội dung cho app container (20 phút)

### Mục tiêu

Hiểu init container chạy trước app container và dùng shared volume.

### Các bước thực hiện

Tạo file `init-demo.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
  labels:
    app: init-demo
spec:
  volumes:
  - name: workdir
    emptyDir: {}
  initContainers:
  - name: init-page
    image: busybox:1.36
    command: ["sh", "-c", "echo 'hello from init container' > /workdir/index.html"]
    volumeMounts:
    - name: workdir
      mountPath: /workdir
  containers:
  - name: web
    image: nginx:1.27
    ports:
    - containerPort: 80
    volumeMounts:
    - name: workdir
      mountPath: /usr/share/nginx/html
```

Apply và kiểm tra:

```bash
kubectl apply -f init-demo.yaml
kubectl get pod init-demo -w
kubectl describe pod init-demo
kubectl logs init-demo -c init-page
kubectl exec -it init-demo -c web -- cat /usr/share/nginx/html/index.html
```

### Expected output

- Init container hoàn tất trước.
- App container đọc được file do init container tạo.

### Troubleshooting

- Nếu Pod kẹt `Init:*`, đọc `kubectl logs init-demo -c init-page`.
- Nếu file không có, kiểm tra `volumeMounts` và `mountPath`.

## Task 3: Multi-container sidecar đọc shared log (20 phút)

### Mục tiêu

Thấy hai container trong cùng Pod chia sẻ volume và lifecycle.

### Các bước thực hiện

Tạo file `sidecar-demo.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sidecar-demo
  labels:
    app: sidecar-demo
spec:
  volumes:
  - name: logs
    emptyDir: {}
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "i=0; while true; do echo \"event-$i\" >> /logs/app.log; i=$((i+1)); sleep 2; done"]
    volumeMounts:
    - name: logs
      mountPath: /logs
  - name: log-sidecar
    image: busybox:1.36
    command: ["sh", "-c", "tail -n+1 -F /logs/app.log"]
    volumeMounts:
    - name: logs
      mountPath: /logs
```

Apply và kiểm tra:

```bash
kubectl apply -f sidecar-demo.yaml
kubectl get pod sidecar-demo
kubectl logs sidecar-demo -c log-sidecar --tail=10
kubectl exec -it sidecar-demo -c app -- sh -c 'tail -n 5 /logs/app.log'
kubectl describe pod sidecar-demo
```

### Expected output

- Container `app` ghi log vào `/logs/app.log`.
- Container `log-sidecar` tail được log đó.

### Troubleshooting

- Nếu `kubectl logs sidecar-demo` lỗi yêu cầu chọn container, thêm `-c`.
- Nếu sidecar chưa có log ngay, chờ vài giây vì app ghi mỗi 2 giây.

## Task 4: Probes và endpoint readiness (25 phút)

### Mục tiêu

Quan sát Pod `Running` nhưng chỉ được Service route khi readiness pass.

### Các bước thực hiện

Tạo file `probe-deploy.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-probe
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-probe
  template:
    metadata:
      labels:
        app: web-probe
    spec:
      containers:
      - name: web
        image: nginx:1.27
        ports:
        - containerPort: 80
        startupProbe:
          httpGet:
            path: /
            port: 80
          failureThreshold: 30
          periodSeconds: 2
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
          timeoutSeconds: 2
        livenessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 10
          timeoutSeconds: 2
---
apiVersion: v1
kind: Service
metadata:
  name: web-probe
spec:
  selector:
    app: web-probe
  ports:
  - port: 80
    targetPort: 80
```

Apply:

```bash
kubectl apply -f probe-deploy.yaml
kubectl rollout status deployment/web-probe
kubectl get pod -l app=web-probe
kubectl get endpoints,endpointslice
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sS http://web-probe.day08.svc.cluster.local
```

### Expected output

- Deployment available.
- Endpoints có hai Pod IP.
- Curl trả HTML nginx.

## Task 5: Inject lỗi readiness probe (20 phút)

### Mục tiêu

Thấy `Running` khác `Ready` và Service endpoint rỗng khi readiness fail.

### Lỗi cần tạo

Patch readiness path sang endpoint không tồn tại:

```bash
kubectl patch deployment web-probe --type='json' -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/not-ready"}]'
kubectl rollout status deployment/web-probe --timeout=60s
kubectl get pods -l app=web-probe
kubectl describe pod -l app=web-probe
kubectl get endpoints,endpointslice
```

Nếu PowerShell hoặc shell của bạn làm hỏng quote JSON, lưu patch vào file `readiness-bad.json` rồi dùng:

```bash
kubectl patch deployment web-probe --type=json --patch-file readiness-bad.json
```

### Symptom

- Pod có thể `Running` nhưng `READY` là `0/1`.
- Deployment rollout có thể không hoàn tất trong timeout.
- Endpoint không có backend ready mới.

### Cách điều tra

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl logs deployment/web-probe -c web --tail=50
kubectl describe deployment web-probe
```

### Cách fix

```bash
kubectl patch deployment web-probe --type='json' -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/"}]'
kubectl rollout status deployment/web-probe
kubectl get endpoints,endpointslice
```

## Task 6: preStop và terminationGracePeriodSeconds (20 phút)

### Mục tiêu

Quan sát kubelet chạy `preStop`, gửi SIGTERM và giữ Pod trong grace period trước khi tạo replacement.

### Các bước thực hiện

Tạo file `termination-demo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: termination-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: termination-demo
  template:
    metadata:
      labels:
        app: termination-demo
    spec:
      terminationGracePeriodSeconds: 15
      containers:
      - name: web
        image: nginx:1.27
        ports:
        - containerPort: 80
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "echo preStop-start; sleep 10; echo preStop-done"]
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
```

Apply và xóa một Pod:

```bash
kubectl apply -f termination-demo.yaml
kubectl rollout status deployment/termination-demo
kubectl get pods -l app=termination-demo -o name
kubectl delete pod <one-termination-demo-pod-name>
kubectl get pods -l app=termination-demo -w
```

### Expected output

- Pod cũ ở trạng thái `Terminating` khoảng 10 giây do `preStop`.
- ReplicaSet tạo Pod thay thế để giữ `replicas=1`.
- Nếu app không thoát trước 15 giây, kubelet sẽ gửi SIGKILL khi hết grace period.

## Cleanup

```bash
kubectl delete namespace day08
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Quên `-c` khi xem logs Pod nhiều container.
- Dùng liveness probe quá gắt khiến app restart liên tục.
- Nghĩ Pod `Running` nghĩa là traffic đã route vào.
- Dùng init container cho migration không idempotent khi có nhiều replicas.

## Stretch Goals

- Tạo liveness probe sai để thấy restart count tăng.
- Thêm resource requests cho cả app và sidecar, quan sát `kubectl describe pod`.
- Thử native sidecar container nếu cluster version và feature support cho restartable init containers.
