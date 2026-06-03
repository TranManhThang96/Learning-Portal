# Bài thực hành - Day 23: PersistentVolume và PersistentVolumeClaim

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Nếu dùng K3s mặc định, thường có `local-path` StorageClass để làm dynamic provisioning.
- Command trong bài dùng Bash/WSL. Với PowerShell, thay `grep` bằng `Select-String` và đổi quoting cho `jsonpath`/`kubectl patch`.

## Lab Scenario

Bạn sẽ tạo static PV/PVC để thấy binding thủ công, mount PVC vào Pod và chứng minh dữ liệu sống qua Pod deletion. Sau đó tạo PVC dynamic bằng StorageClass mặc định, quan sát reclaim policy, và inject lỗi PVC `Pending`.

## Core Path và Stretch Goals

- Core Path: Task 1-5, khoảng 115 phút.
- Stretch Goals: Task 6-7, dành cho expansion/reclaim nếu còn thời gian.

## Task 1: Kiểm tra storage class hiện có (10 phút)

### Mục tiêu

Biết cluster có dynamic provisioning không.

### Các bước thực hiện

```bash
kubectl get storageclass
kubectl get pv
kubectl get pvc -A
kubectl -n kube-system get pods | grep -Ei 'local-path|csi|storage|provisioner'
kubectl get nodes -L kubernetes.io/hostname
```

### Expected output

- K3s thường có StorageClass `local-path`.
- Nếu không có StorageClass, bạn vẫn làm được static PV ở Task 2.
- Ghi lại một giá trị label `kubernetes.io/hostname` để dùng cho static `hostPath` PV ở Task 2.

## Task 2: Static PV/PVC binding (30 phút)

### Mục tiêu

Hiểu PV là cluster-scoped và PVC là namespaced.

### Các bước thực hiện

```bash
kubectl create namespace day23
kubectl config set-context --current --namespace=day23
```

Chọn một node lab từ Task 1 và thay `<node-hostname>` trong manifest dưới đây bằng giá trị label `kubernetes.io/hostname` của node đó. Static `hostPath` PV phải có `nodeAffinity` để scheduler không đặt Pod dùng volume lên node khác trong cluster multi-node.

Tạo file `static-pv-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: day23-manual-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: day23-manual
  hostPath:
    path: /tmp/day23-manual-pv
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - <node-hostname>
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  storageClassName: day23-manual
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 512Mi
```

Apply và kiểm tra:

```bash
kubectl apply -f static-pv-pvc.yaml
kubectl get pv
kubectl get pvc
kubectl describe pvc data
```

### Expected output

- PV `day23-manual-pv` chuyển sang `Bound`.
- PVC `data` chuyển sang `Bound`.
- PVC request `512Mi` có thể bind PV capacity `1Gi`.

## Task 3: Mount PVC và kiểm tra dữ liệu sau Pod deletion (30 phút)

### Mục tiêu

Thấy PVC-backed data sống lâu hơn Pod.

### Các bước thực hiện

Tạo file `pod-uses-pvc.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: writer
spec:
  nodeSelector:
    kubernetes.io/hostname: <node-hostname>
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
      echo "pod=$HOSTNAME time=$(date -Iseconds)" >> /data/history.txt
      tail -f /data/history.txt
    volumeMounts:
    - name: data
      mountPath: /data
```

Apply:

```bash
kubectl apply -f pod-uses-pvc.yaml
kubectl wait --for=condition=Ready pod/writer --timeout=90s
kubectl logs writer
kubectl exec writer -- cat /data/history.txt
```

Xóa Pod và tạo lại:

```bash
kubectl delete pod writer
kubectl apply -f pod-uses-pvc.yaml
kubectl wait --for=condition=Ready pod/writer --timeout=90s
kubectl exec writer -- cat /data/history.txt
```

### Expected output

- File `history.txt` có nhiều dòng qua các lần Pod được tạo lại.
- Data tồn tại vì PVC vẫn bind với PV.
- Trên multi-node, Pod được schedule về node khớp `nodeAffinity` của PV thay vì chạy ngẫu nhiên ở node khác.

## Task 4: Dynamic PVC với StorageClass mặc định (25 phút)

### Mục tiêu

Thấy provisioner tự tạo PV.

### Các bước thực hiện

Tạo file `dynamic-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-data
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 256Mi
```

Apply:

```bash
kubectl apply -f dynamic-pvc.yaml
kubectl get pvc dynamic-data
kubectl describe pvc dynamic-data
kubectl get pv
```

Nếu PVC Pending vì không có default StorageClass, lấy class name rồi patch manifest:

```bash
kubectl get storageclass
```

Thêm:

```yaml
storageClassName: <class-name>
```

### Expected output

- PVC được provisioner tạo PV tự động nếu default StorageClass hoạt động.
- PV mới có reclaim policy theo StorageClass/provisioner.

## Task 5: Inject lỗi PVC Pending (20 phút)

### Mục tiêu

Đọc event khi không có StorageClass phù hợp.

### Các bước thực hiện

Tạo file `pending-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pending-data
spec:
  storageClassName: class-does-not-exist
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Apply và debug:

```bash
kubectl apply -f pending-pvc.yaml
kubectl get pvc pending-data
kubectl describe pvc pending-data
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- PVC ở trạng thái `Pending`.
- Event nói storage class không tồn tại hoặc provisioning không thể xảy ra.

## Stretch Goals

## Task 6: Optional - kiểm tra expansion capability (20 phút)

### Mục tiêu

Biết kiểm tra StorageClass/driver có hỗ trợ PVC expansion không trước khi patch size.

### Các bước thực hiện

Kiểm tra class của PVC dynamic:

```bash
kubectl get pvc dynamic-data -o jsonpath='{.spec.storageClassName}{"\n"}'
kubectl get storageclass
kubectl describe storageclass <class-name>
```

Nếu StorageClass có `allowVolumeExpansion: true`, thử tăng PVC dynamic:

```bash
kubectl patch pvc dynamic-data -p '{"spec":{"resources":{"requests":{"storage":"512Mi"}}}}'
kubectl get pvc dynamic-data
kubectl describe pvc dynamic-data
```

Nếu StorageClass không hỗ trợ expansion, không patch bừa. Ghi lại expected failure mode:

```text
Class:
allowVolumeExpansion:
Driver hỗ trợ expansion:
Expected behavior nếu patch:
```

### Expected output

- Bạn biết expansion phụ thuộc StorageClass và driver.
- Nếu được hỗ trợ, PVC request size tăng lên `512Mi`.
- Nếu không hỗ trợ, đây là limitation hợp lệ của lab, không phải lỗi YAML.

## Task 7: Optional - quan sát reclaim policy (20 phút)

### Mục tiêu

Hiểu xóa PVC không phải lúc nào cũng xóa data giống nhau.

### Các bước thực hiện

Kiểm tra PV của PVC static:

```bash
kubectl get pvc data -o jsonpath='{.spec.volumeName}{"\n"}'
kubectl get pv day23-manual-pv -o yaml | grep -E 'persistentVolumeReclaimPolicy|claimRef|phase'
```

Xóa PVC static:

```bash
kubectl delete pod writer
kubectl delete pvc data
kubectl get pv day23-manual-pv
kubectl describe pv day23-manual-pv
```

### Expected output

- PV dùng `Retain` thường chuyển sang `Released`.
- Data không tự được chuẩn bị để claim lại ngay; admin phải xử lý thủ công nếu muốn reuse.

## Cleanup

```bash
kubectl delete namespace day23
kubectl delete pv day23-manual-pv
```

Nếu còn PV dynamic:

```bash
kubectl get pv
```

Chỉ xóa thủ công những PV thuộc lab và bạn hiểu reclaim policy của chúng.

## Câu hỏi tự kiểm tra

1. PVC `Pending` khác Pod `Pending` thế nào?
2. Vì sao PVC là namespaced nhưng PV là cluster-scoped?
3. `Retain` và `Delete` khác nhau ra sao khi xóa PVC?
4. Vì sao Deployment nhiều replicas dùng chung PVC `RWO` là rủi ro?
5. K3s `local-path` có phù hợp cho HA database production không?

## Đáp án ngắn

1. PVC `Pending` là chưa bind/provision storage; Pod `Pending` là chưa schedule/start được.
2. PVC thuộc namespace app; PV đại diện tài nguyên storage toàn cluster.
3. `Retain` giữ PV/backend để admin xử lý; `Delete` thường xóa PV và backend volume.
4. `RWO` thường chỉ an toàn cho một node/writer; nhiều replicas dễ attach/mount lỗi hoặc ghi hỏng data.
5. Không. `local-path` tiện cho lab nhưng node-local, không HA và không thay backup/replication.
