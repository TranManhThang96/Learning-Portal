# Bài thực hành - Day 24: StorageClass và dynamic provisioning

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Với K3s mặc định, `local-path-provisioner` thường đã có sẵn.
- Command trong bài dùng Bash/WSL. Với PowerShell, thay `PV_NAME=$(...)` bằng `$PV_NAME = kubectl ...`.

## Lab Scenario

Bạn sẽ inspect StorageClass mặc định, tạo PVC dùng explicit class, quan sát dynamic PV được tạo, mount vào Pod consumer, so sánh behavior khi dùng class sai, và đọc `volumeBindingMode`.

## Core Path và Stretch Goals

- Core Path: Task 1-5 và cleanup, khoảng 105-115 phút.
- Stretch Goals: Task 6-7, dành cho custom StorageClass và `storageClassName: ""`.

## Task 1: Inspect StorageClass hiện tại (15 phút)

### Mục tiêu

Biết default class và provisioner thật của cluster.

### Các bước thực hiện

```bash
kubectl get storageclass
kubectl describe storageclass
kubectl -n kube-system get pods | grep -Ei 'local-path|csi|provisioner|storage'
```

Nếu thấy `local-path`, inspect:

```bash
kubectl describe storageclass local-path
```

### Expected output

- Xác định StorageClass nào là default.
- Xác định `provisioner`, `reclaimPolicy`, `volumeBindingMode`.
- Với K3s, thường thấy provisioner `rancher.io/local-path`.

## Task 2: Tạo namespace và PVC dynamic explicit class (25 phút)

### Mục tiêu

Không phụ thuộc implicit default khi học.

### Các bước thực hiện

```bash
kubectl create namespace day24
kubectl config set-context --current --namespace=day24
```

Chọn class name từ Task 1. Manifest dưới đây dùng `local-path` để chạy ngay trên K3s mặc định; với cluster khác hãy đổi sang class thực tế trước khi apply.

Tạo file `pvc-explicit.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  storageClassName: local-path
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 256Mi
```

Nếu cluster của bạn không có `local-path`, đổi `storageClassName` sang class thực tế.

Apply:

```bash
kubectl apply -f pvc-explicit.yaml
kubectl get pvc data
kubectl describe pvc data
kubectl get pv
```

### Expected output

- Nếu class dùng `Immediate`, PVC có thể Bound ngay.
- Nếu class dùng `WaitForFirstConsumer`, PVC có thể Pending cho đến khi có Pod dùng nó.

## Task 3: Tạo Pod consumer để kích hoạt binding (25 phút)

### Mục tiêu

Hiểu `WaitForFirstConsumer` bằng thực nghiệm.

### Các bước thực hiện

Tạo file `pod-consumer.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: writer
spec:
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      while true; do
        echo "node=$NODE_NAME pod=$HOSTNAME time=$(date -Iseconds)" >> /data/history.txt
        sleep 5
      done
    env:
    - name: NODE_NAME
      valueFrom:
        fieldRef:
          fieldPath: spec.nodeName
    volumeMounts:
    - name: data
      mountPath: /data
```

Apply:

```bash
kubectl apply -f pod-consumer.yaml
kubectl wait --for=condition=Ready pod/writer --timeout=120s
kubectl get pod writer -o wide
kubectl get pvc data
kubectl get pv
kubectl exec writer -- tail -n 5 /data/history.txt
```

### Expected output

- PVC chuyển Bound nếu trước đó Pending vì chờ consumer.
- PV được tạo động.
- Pod ghi được file vào volume.

## Task 4: Inspect PV được provision tự động (20 phút)

### Mục tiêu

Liên kết PVC, PV và StorageClass.

### Các bước thực hiện

```bash
PV_NAME=$(kubectl get pvc data -o jsonpath='{.spec.volumeName}')
kubectl describe pv "$PV_NAME"
kubectl get pv "$PV_NAME" -o yaml
```

Ghi lại:

```text
PV name:
StorageClass:
Reclaim policy:
Access modes:
Capacity:
Node affinity/topology nếu có:
Backend/path/volumeHandle nếu có:
```

### Expected output

- PV có `storageClassName` giống PVC.
- Reclaim policy đến từ StorageClass/provisioner.
- Với local-path, bạn có thể thấy thông tin node/path liên quan local storage.

## Task 5: Inject lỗi StorageClass sai (20 phút)

### Mục tiêu

Đọc đúng lỗi provisioning.

### Các bước thực hiện

Tạo file `bad-class-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bad-data
spec:
  storageClassName: storage-class-does-not-exist
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 128Mi
```

Apply và debug:

```bash
kubectl apply -f bad-class-pvc.yaml
kubectl get pvc bad-data
kubectl describe pvc bad-data
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- PVC `bad-data` Pending.
- Event chỉ ra class không tồn tại hoặc provisioning không thể chạy.

## Stretch Goals

## Task 6: Optional - tạo StorageClass local-path riêng cho lab (20 phút)

### Mục tiêu

Hiểu cấu trúc StorageClass mà không đổi default toàn cluster.

### Các bước thực hiện

Chỉ chạy nếu Task 1 xác nhận provisioner `rancher.io/local-path` tồn tại.

Tạo file `day24-local-path-sc.yaml`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: day24-local-path
provisioner: rancher.io/local-path
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: false
```

Apply:

```bash
kubectl apply -f day24-local-path-sc.yaml
kubectl describe storageclass day24-local-path
```

Tạo PVC dùng class này:

Tạo file `pvc-custom-class.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-custom-class
spec:
  storageClassName: day24-local-path
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 128Mi
```

Apply PVC và kiểm tra:

```bash
kubectl apply -f pvc-custom-class.yaml
kubectl get pvc data-custom-class
kubectl describe pvc data-custom-class
```

### Expected output

- StorageClass mới không phải default.
- PVC chỉ dùng class này khi khai báo explicit `storageClassName`.

## Task 7: Optional - tạo PVC không dùng dynamic provisioning (15 phút)

### Mục tiêu

Thấy `storageClassName: ""` nghĩa là chỉ bind static PV không có class, không dùng default dynamic provisioning.

### Các bước thực hiện

Tạo file `pvc-no-class.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: no-dynamic
spec:
  storageClassName: ""
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 128Mi
```

Apply và inspect:

```bash
kubectl apply -f pvc-no-class.yaml
kubectl get pvc no-dynamic
kubectl describe pvc no-dynamic
```

### Expected output

- PVC thường `Pending` nếu không có static PV phù hợp.
- Không có PV dynamic mới được tạo từ default StorageClass.

## Task 8: Cleanup và quan sát reclaim (15 phút)

### Mục tiêu

Thấy dynamic PV biến mất hoặc được xử lý theo reclaim policy.

### Các bước thực hiện

```bash
kubectl delete pod writer
kubectl delete pvc data bad-data data-custom-class no-dynamic --ignore-not-found
kubectl get pv
kubectl delete storageclass day24-local-path --ignore-not-found
kubectl delete namespace day24
```

### Expected output

- PV dynamic có reclaim policy `Delete` thường bị xóa.
- Nếu PV còn lại, inspect trước khi xóa thủ công.

## Câu hỏi tự kiểm tra

1. `StorageClass` khác `PersistentVolume` ở đâu?
2. PVC không khai báo `storageClassName` sẽ dùng class nào?
3. Khi nào cần `storageClassName: ""`?
4. `WaitForFirstConsumer` giúp tránh lỗi topology nào?
5. Vì sao thay đổi parameters của StorageClass không phải migration plan cho volume cũ?

## Đáp án ngắn

1. `StorageClass` là policy/provisioner; `PersistentVolume` là volume cụ thể đã có hoặc được tạo.
2. PVC omit field sẽ dùng default StorageClass nếu cluster có.
3. Khi muốn bind static PV không có class và không muốn dynamic provisioning.
4. Tránh tạo volume ở zone/node không thể attach cho Pod consumer.
5. Parameters áp dụng cho volume mới; volume cũ không tự đổi backend/type/IOPS.
