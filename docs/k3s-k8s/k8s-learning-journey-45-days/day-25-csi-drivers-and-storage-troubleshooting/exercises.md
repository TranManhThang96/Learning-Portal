# Bài thực hành - Day 25: CSI drivers và storage troubleshooting

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Không bắt buộc cài CSI driver riêng. Với K3s local-path, bạn vẫn học được phần provisioning/debug object layer.
- Command trong bài dùng Bash/WSL. Với PowerShell, thay `grep` bằng `Select-String` và `PV_NAME=$(...)` bằng `$PV_NAME = kubectl ...`.

## Lab Scenario

Bạn sẽ inventory storage stack hiện tại, map PVC/PV/StorageClass/provisioner, tạo workload dùng PVC, debug một PVC lỗi, kiểm tra VolumeAttachment nếu cluster có CSI attach flow, và viết runbook ngắn cho storage driver của cluster.

## Core Path và Stretch Goals

- Core Path: Task 1-4, khoảng 90 phút. Track này chạy được cả khi K3s chỉ có `local-path`.
- Stretch Goals: Task 5-8 dành cho real CSI attach flow, permission deep dive, capacity/inode check hoặc runbook nếu còn thời gian.

## Task 1: Inventory storage stack (20 phút)

### Mục tiêu

Biết cluster đang dùng storage driver/provisioner nào.

### Các bước thực hiện

```bash
kubectl get storageclass
kubectl get csidriver
kubectl get pv
kubectl get pvc -A
kubectl get volumeattachment
kubectl get volumesnapshotclass
kubectl get volumesnapshot -A
kubectl get pods -A -o wide | grep -Ei 'csi|storage|longhorn|openebs|rook|ceph|local-path|provisioner'
```

Nếu lệnh `csidriver`, `volumeattachment` hoặc snapshot trả về rỗng/NotFound trên K3s local-path, đây là expected output của local-path track. Ghi chú lại thay vì coi là blocker.

### Expected output

- Xác định được default StorageClass.
- Biết cluster có CSI driver registered qua `CSIDriver` hay chỉ có provisioner khác như local-path.
- Tìm được namespace chứa storage components.
- Phân loại lab hiện tại là `local-path track` hoặc `real CSI track`.

## Task 2: Tạo PVC và Pod để map object chain (30 phút)

### Mục tiêu

Đi từ Pod mount path ngược về PVC/PV/StorageClass.

### Các bước thực hiện

```bash
kubectl create namespace day25
kubectl config set-context --current --namespace=day25
```

Tạo file `storage-chain.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 256Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: app
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
        echo "pod=$HOSTNAME node=$NODE_NAME time=$(date -Iseconds)" >> /data/history.txt
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
kubectl apply -f storage-chain.yaml
kubectl wait --for=condition=Ready pod/app --timeout=120s
kubectl get pod app -o wide
kubectl get pvc data
kubectl get pv
kubectl exec app -- tail -n 5 /data/history.txt
```

Map chain:

```bash
PV_NAME=$(kubectl get pvc data -o jsonpath='{.spec.volumeName}')
SC_NAME=$(kubectl get pvc data -o jsonpath='{.spec.storageClassName}')
kubectl describe pvc data
kubectl describe pv "$PV_NAME"
kubectl describe storageclass "$SC_NAME"
```

### Expected output

- Pod ghi được vào `/data`.
- Bạn biết PVC bind PV nào và PV đến từ StorageClass nào.

## Task 3: Tìm driver logs/provisioner logs (20 phút)

### Mục tiêu

Biết đọc đúng nơi khi provisioning lỗi.

### Các bước thực hiện

Nếu dùng K3s local-path:

```bash
kubectl -n kube-system get pods | grep local-path
kubectl -n kube-system logs -l app=local-path-provisioner --tail=100
```

Nếu dùng CSI driver khác, tìm namespace/pods:

```bash
kubectl get pods -A -o wide | grep -Ei 'csi|longhorn|openebs|rook|ceph'
kubectl get csidriver
```

Sau đó đọc logs controller hoặc node plugin phù hợp:

```bash
kubectl -n <driver-namespace> logs <driver-pod> --all-containers --tail=100
```

### Expected output

- Bạn xác định được component nào xử lý provisioning.
- Logs không nhất thiết có lỗi; mục tiêu là biết đường đi khi có incident.

## Task 4: Inject lỗi provisioning bằng class sai (20 phút)

### Mục tiêu

Thực hành đọc events trước khi đoán.

### Các bước thực hiện

Tạo file `bad-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bad-data
spec:
  storageClassName: no-such-driver-class
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Apply và debug:

```bash
kubectl apply -f bad-pvc.yaml
kubectl get pvc bad-data
kubectl describe pvc bad-data
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- PVC `Pending`.
- Event chỉ ra StorageClass/provisioner issue.
- Bạn phân loại lỗi này là provisioning phase, chưa đến attach/mount phase.

## Stretch Goals

## Task 5: Optional - Inspect attach/mount state với real CSI (20 phút)

### Mục tiêu

Biết khi nào dùng `VolumeAttachment`.

### Các bước thực hiện

```bash
kubectl get volumeattachment
kubectl describe pod app
PV_NAME=$(kubectl get pvc data -o jsonpath='{.spec.volumeName}')
kubectl get volumeattachment -o yaml | grep -C 3 "$PV_NAME"
```

Nếu có VolumeAttachment liên quan, inspect:

```bash
kubectl describe volumeattachment <name>
```

Nếu không có, ghi chú:

```text
Driver/provisioner hiện tại có thể không dùng CSI attach object theo cách cloud block driver dùng.
Vẫn debug mount bằng Pod events, kubelet logs và driver node plugin logs nếu có.
```

### Expected output

- Với cloud block CSI, thường thấy VolumeAttachment.
- Với local-path hoặc một số local provisioner, có thể không có attach object liên quan.

## Task 6: Optional - Permission troubleshooting mini-lab (25 phút)

### Mục tiêu

Phân biệt storage mount OK nhưng app không ghi được do permission.

### Các bước thực hiện

Tạo file `permission-demo.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: permission-demo
spec:
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data
  initContainers:
  - name: root-writer
    image: busybox:1.36
    command: ["sh", "-c", "mkdir -p /data/locked && chmod 700 /data/locked && touch /data/locked/root-file"]
    volumeMounts:
    - name: data
      mountPath: /data
  containers:
  - name: app
    image: busybox:1.36
    securityContext:
      runAsUser: 1000
      runAsGroup: 1000
    command: ["sh", "-c", "echo test > /data/locked/app-file; sleep 3600"]
    volumeMounts:
    - name: data
      mountPath: /data
```

Apply và debug:

```bash
kubectl apply -f permission-demo.yaml
kubectl get pod permission-demo
kubectl describe pod permission-demo
kubectl logs permission-demo
```

Sửa bằng manifest `permission-demo-fixed.yaml` dùng init container điều chỉnh ownership:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: permission-demo-fixed
spec:
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data
  initContainers:
  - name: fix-permission
    image: busybox:1.36
    command: ["sh", "-c", "mkdir -p /data/app && chown -R 1000:1000 /data/app"]
    securityContext:
      runAsUser: 0
    volumeMounts:
    - name: data
      mountPath: /data
  containers:
  - name: app
    image: busybox:1.36
    securityContext:
      runAsUser: 1000
      runAsGroup: 1000
    command: ["sh", "-c", "echo test > /data/app/app-file; cat /data/app/app-file; sleep 3600"]
    volumeMounts:
    - name: data
      mountPath: /data
```

Apply và verify:

```bash
kubectl delete pod permission-demo --ignore-not-found
kubectl apply -f permission-demo-fixed.yaml
kubectl wait --for=condition=Ready pod/permission-demo-fixed --timeout=90s
kubectl logs permission-demo-fixed
```

### Expected output

- Volume mount thành công nhưng container app lỗi permission.
- Đây không phải provisioning/attach lỗi.
- Pod fixed ghi được vào `/data/app/app-file`.

## Task 7: Optional - kiểm tra capacity/inode/write path (15 phút)

### Mục tiêu

Có thói quen kiểm tra filesystem full và inode full khi app báo I/O lỗi.

### Các bước thực hiện

```bash
kubectl exec app -- df -h /data
kubectl exec app -- df -i /data
kubectl exec app -- sh -c 'time dd if=/dev/zero of=/data/write-test.bin bs=1M count=16 conv=fsync'
kubectl exec app -- rm -f /data/write-test.bin
```

### Expected output

- Biết filesystem còn bao nhiêu dung lượng và inode.
- Có một write test nhỏ có kiểm soát; không dùng benchmark này để kết luận production performance.

## Task 8: Optional - viết runbook storage 1 trang (20 phút)

### Mục tiêu

Biến kiến thức thành checklist incident.

Tạo file ghi chú `day25-storage-runbook.md`:

```text
Storage driver/provisioner:
Default StorageClass:
Provisioner namespace:
Controller pods:
Node plugin pods:
PVC Pending commands:
Pod mount failure commands:
Driver log commands:
VolumeAttachment command:
Expansion support:
Snapshot support:
Backup/restore owner:
Known caveats in this cluster:
```

### Expected output

- Có runbook cụ thể cho cluster lab, không chỉ lý thuyết chung.

## Cleanup

```bash
kubectl delete namespace day25
```

Nếu còn PV dynamic do reclaim policy không xóa, inspect kỹ trước khi xóa thủ công:

```bash
kubectl get pv
kubectl describe pv <pv>
```

## Câu hỏi tự kiểm tra

1. PVC `Bound` có đảm bảo Pod mount thành công không?
2. CSI controller plugin và node plugin khác nhau thế nào?
3. Khi nào cần xem `VolumeAttachment`?
4. Longhorn, OpenEBS local PV và Rook/Ceph khác nhau ở điểm vận hành nào?
5. Vì sao backup/restore drill quan trọng hơn việc chỉ thấy PVC/PV healthy?

## Đáp án ngắn

1. Không. `Bound` chỉ là binding; attach/mount/permission/I/O vẫn có thể lỗi.
2. Controller xử lý provision/attach/snapshot/resize; node plugin xử lý stage/publish/mount trên node.
3. Khi dùng CSI backend có attach flow, nhất là cloud block disk hoặc lỗi attach timeout.
4. Longhorn dễ dùng cho K3s/edge nhưng cần network/disk ổn; OpenEBS phụ thuộc engine; Rook/Ceph mạnh nhưng vận hành nặng.
5. Snapshot/backup vô nghĩa nếu không chứng minh được restore đúng dữ liệu trong RTO/RPO mong muốn.
