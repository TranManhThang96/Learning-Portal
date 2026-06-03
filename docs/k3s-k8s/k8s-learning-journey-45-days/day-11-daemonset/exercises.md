# Bài thực hành - Day 11: DaemonSet

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Nếu có thể, dùng cluster multi-node để thấy rõ một Pod trên mỗi node. Single-node vẫn làm được lab.
- Đã hiểu labels/selectors từ các ngày trước ở mức cơ bản.

## Lab Scenario

Bạn triển khai một node reporter agent bằng `DaemonSet`. Agent in ra tên node đang chạy. Sau đó bạn giới hạn agent bằng node label, rollout version mới, inject image lỗi và debug bằng DaemonSet status, Pod events và node metadata.

Core path của lab này khoảng 100-110 phút. Phần taint, `OnDelete`, `hostPath` và so sánh rollout nhiều node nằm trong `Stretch Goals` để không vượt khung 2 giờ.

## Task 1: Inspect DaemonSet hệ thống (10 phút)

### Mục tiêu

Quan sát DaemonSet đang có trong cluster.

### Các bước thực hiện

```bash
kubectl get daemonset -A -o wide
kubectl get pods -A -o wide | grep -E 'kube-system|svclb|cni|agent'
```

Nếu command `grep` không có trên môi trường của bạn, dùng:

```bash
kubectl get pods -A -o wide
```

Chọn một DaemonSet nếu có và xem chi tiết:

```bash
kubectl describe daemonset <daemonset-name> -n <namespace>
```

### Expected output

- Cluster có thể có DaemonSet hệ thống tùy distro/addon.
- Với K3s, bạn có thể thấy các Pod liên quan `kube-system`, ServiceLB hoặc component packaged.

## Task 2: Tạo node reporter DaemonSet (25 phút)

### Mục tiêu

Chạy một Pod agent trên mỗi node đủ điều kiện.

### Các bước thực hiện

```bash
kubectl create namespace day11
kubectl config set-context --current --namespace=day11
```

Tạo file `node-reporter.yaml`:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-reporter
  labels:
    app: node-reporter
spec:
  selector:
    matchLabels:
      app: node-reporter
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  template:
    metadata:
      labels:
        app: node-reporter
    spec:
      containers:
      - name: reporter
        image: busybox:1.36
        command: ["sh", "-c"]
        args:
        - |
          while true; do
            echo "pod=$HOSTNAME node=$NODE_NAME time=$(date -Iseconds)"
            sleep 10
          done
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        resources:
          requests:
            cpu: 10m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f node-reporter.yaml
kubectl rollout status daemonset/node-reporter
kubectl get ds,pod -o wide
kubectl logs -l app=node-reporter --tail=20
```

### Expected output

- `DESIRED` bằng số node đủ điều kiện.
- Mỗi Pod nằm trên một node.
- Log in ra `node=<node-name>`.

## Task 3: Đọc DaemonSet status và owner references (15 phút)

### Mục tiêu

Hiểu controller đang quản Pod nào và status field nói gì.

### Các bước thực hiện

```bash
kubectl get ds node-reporter -o jsonpath='{.status.desiredNumberScheduled}{" desired / "}{.status.numberReady}{" ready / "}{.status.updatedNumberScheduled}{" updated\n"}'
kubectl get pod -l app=node-reporter -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,READY:.status.containerStatuses[0].ready
kubectl get pod <pod-name> -o jsonpath='{.metadata.ownerReferences[*].kind}{" "}{.metadata.ownerReferences[*].name}{"\n"}'
```

### Expected output

- Owner của Pod là `DaemonSet`.
- `desiredNumberScheduled` phản ánh số node target.

## Task 4: Giới hạn DaemonSet bằng node label (20 phút)

### Mục tiêu

Chỉ chạy agent trên node được label.

### Các bước thực hiện

Lấy tên node đầu tiên và gắn label:

```bash
kubectl get nodes
kubectl label node <node-name> day11-agent=enabled
```

Patch DaemonSet:

```bash
kubectl patch daemonset node-reporter --type='json' -p='[{"op":"add","path":"/spec/template/spec/nodeSelector","value":{"day11-agent":"enabled"}}]'
kubectl rollout status daemonset/node-reporter
kubectl get ds,pod -o wide
```

### Expected output

- `DESIRED` giảm còn số node có label `day11-agent=enabled`.
- Pod trên node không match bị xóa.

### Troubleshooting

Nếu patch báo path đã tồn tại, dùng:

```bash
kubectl patch daemonset node-reporter --type='json' -p='[{"op":"replace","path":"/spec/template/spec/nodeSelector","value":{"day11-agent":"enabled"}}]'
```

Nếu không có Pod nào chạy:

```bash
kubectl get nodes --show-labels
kubectl describe daemonset node-reporter
```

## Task 5: Rolling update DaemonSet (15 phút)

### Mục tiêu

Quan sát DaemonSet rollout version mới theo node.

### Các bước thực hiện

```bash
kubectl set image daemonset/node-reporter reporter=busybox:1.37
kubectl rollout status daemonset/node-reporter
kubectl get pods -l app=node-reporter -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,IMAGE:.spec.containers[0].image
kubectl rollout history daemonset/node-reporter
```

### Expected output

- Pod cũ được thay bằng Pod dùng image mới.
- Với nhiều node, update diễn ra theo `maxUnavailable`.

### Troubleshooting

Nếu image `busybox:1.37` không tồn tại trong registry tại thời điểm làm lab, dùng một tag busybox hiện có, ví dụ `busybox:1.36`.

## Task 6: Inject image lỗi và debug rollout (15 phút)

### Mục tiêu

Thấy DaemonSet rollout kẹt do image pull fail.

### Lỗi cần tạo

```bash
kubectl set image daemonset/node-reporter reporter=busybox:this-tag-does-not-exist
kubectl rollout status daemonset/node-reporter --timeout=60s
kubectl get ds,pod -o wide
kubectl describe daemonset node-reporter
kubectl describe pod -l app=node-reporter
kubectl get events --sort-by=.lastTimestamp
```

### Symptom

- Pod mới có thể vào `ImagePullBackOff`.
- DaemonSet không đạt updated/ready như mong muốn.

### Cách fix

```bash
kubectl set image daemonset/node-reporter reporter=busybox:1.36
kubectl rollout status daemonset/node-reporter
kubectl get ds,pod -o wide
```

## Task 7: Cleanup label và namespace (5 phút)

### Các bước thực hiện

Nếu bạn đã label node:

```bash
kubectl label node <node-name> day11-agent-
```

Cleanup:

```bash
kubectl delete namespace day11
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Quên rằng DaemonSet count phụ thuộc vào node đủ điều kiện, không phải replicas.
- Label sai node làm `DESIRED` bằng 0.
- Thiếu toleration với node có taint.
- Agent không có resource requests, gây node pressure khó đoán.
- Mount hostPath quá rộng.
- Patch nhầm DaemonSet hệ thống do K3s/cloud provider quản lý.

## Stretch Goals

- Tạo taint trên một node lab và thêm toleration cho DaemonSet.
- Chuyển `updateStrategy` sang `OnDelete`, đổi image rồi xóa từng Pod thủ công.
- Thêm `hostPath` read-only vào `/var/log` và kiểm tra mount trong container.
- Nếu có multi-node, so sánh rollout với `maxUnavailable: 1` và `maxUnavailable: 50%`.
