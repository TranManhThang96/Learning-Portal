# Bài thực hành - Day 02: Quan sát Kubernetes Architecture

## Prerequisites

- Cluster `k3d-k8s-lab` từ Day 01, hoặc một cluster Kubernetes/K3s tương đương đang chạy.
- `kubectl` đã trỏ đúng context.
- Có quyền đọc object ở namespace `kube-system`.
- Nếu có metrics-server, `kubectl top` sẽ dùng được; nếu chưa có, bỏ qua phần metrics.

## Lab Scenario

Bạn nhận một cluster đã có sẵn và cần xác định kiến trúc runtime: node nào đang chạy, system components nào có mặt, workload đi qua những object nào khi deploy.

Core Path: Task 1-5 khoảng 105-115 phút. Nếu còn ít thời gian, giữ Task 4 ở mức quan sát endpoint và bỏ qua phần patch selector; selector mismatch sẽ được đào sâu lại ở Day 05.

## Task 1: Inventory control plane và node (25 phút)

### Mục tiêu

Biết cluster có bao nhiêu node, version nào, system pods nào.

### Các bước thực hiện

```bash
kubectl cluster-info
kubectl version
kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl get pods -n kube-system -o wide
```

Với K3s, kiểm tra thêm nếu có quyền shell trên node:

```bash
sudo systemctl status k3s
sudo systemctl status k3s-agent
```

### Expected output

- Node `Ready`.
- `kube-system` có DNS và các packaged/system components.
- K3s có thể không hiển thị từng control plane component như static pod riêng biệt vì nhiều component được đóng gói trong process `k3s`.

### Troubleshooting

- Không thấy `kube-system`: kiểm tra namespace và quyền RBAC.
- `kubectl version` lỗi client/server mismatch không nhất thiết nghiêm trọng, nhưng nếu quá lệch version cần lưu ý.

## Task 2: Theo dõi object chain khi tạo Deployment (30 phút)

### Mục tiêu

Quan sát `Deployment` -> `ReplicaSet` -> `Pod` -> node assignment.

### Các bước thực hiện

```bash
kubectl create deployment arch-demo --image=nginx:1.27 --replicas=2
kubectl get deploy,rs,pod -l app=arch-demo -o wide
kubectl describe deployment arch-demo
```

Lấy tên một Pod:

```bash
kubectl get pod -l app=arch-demo -o name
kubectl describe pod <pod-name>
```

Tìm các trường:

- `Controlled By`.
- `Node`.
- `Conditions`.
- `Events`.

### Verification

```bash
kubectl rollout status deployment/arch-demo
kubectl get pod -l app=arch-demo -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,PHASE:.status.phase,READY:.status.containerStatuses[0].ready
```

## Task 3: Quan sát scheduler bằng lỗi resource request (30 phút)

### Mục tiêu

Tạo `Pod` không schedule được để đọc event từ scheduler.

### Các bước thực hiện

Tạo `too-large.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: too-large
spec:
  containers:
    - name: pause
      image: registry.k8s.io/pause:3.10
      resources:
        requests:
          cpu: "1000"
          memory: "1000Gi"
```

Apply:

```bash
kubectl apply -f too-large.yaml
kubectl get pod too-large
kubectl describe pod too-large
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

`Pod` ở trạng thái `Pending`, event nói không có node đủ tài nguyên.

### Cách fix

```bash
kubectl delete pod too-large
```

Production note: nếu lỗi thật xảy ra, đừng chỉ giảm requests cho qua. Cần so sánh requests với capacity, HPA, node pool, quota và SLO.

## Task 4: Tạo Service và kiểm tra endpoint controller (25 phút)

### Mục tiêu

Hiểu `Service` không route tới `Pod` nếu selector không match hoặc Pod chưa Ready.

### Các bước thực hiện

```bash
kubectl expose deployment arch-demo --port=80 --target-port=80
kubectl get svc,endpoints,endpointslice
kubectl describe svc arch-demo
```

Tạo file `wrong-selector-patch.yaml`:

```yaml
spec:
  selector:
    app: wrong-label
```

Apply patch:

```bash
kubectl patch service arch-demo --type=merge --patch-file wrong-selector-patch.yaml
kubectl get endpoints arch-demo
```

Tạo file `correct-selector-patch.yaml`:

```yaml
spec:
  selector:
    app: arch-demo
```

Fix:

```bash
kubectl patch service arch-demo --type=merge --patch-file correct-selector-patch.yaml
kubectl get endpoints arch-demo
```

Cách dùng `--patch-file` chạy ổn hơn khi học viên dùng PowerShell/cmd hoặc copy command qua nhiều shell khác nhau. Nếu dùng Bash/WSL, JSON inline vẫn được, nhưng patch file ít lỗi quoting hơn.

### Verification

Endpoint list phải rỗng khi selector sai và có địa chỉ khi selector đúng.

## Task 5: Dọn dẹp (10 phút)

```bash
kubectl delete service arch-demo
kubectl delete deployment arch-demo
kubectl get deploy,rs,pod,svc
```

## Common Pitfalls

- Dùng `kubectl get pods` mà không thêm `-n kube-system` khi tìm system components.
- Thấy `Pod Pending` rồi đọc logs; `Pending` thường chưa có container để đọc logs.
- Quên rằng K3s đóng gói control plane nên không phải lúc nào cũng thấy `kube-apiserver` là Pod riêng.
- Patch `Service` selector sai rồi quên sửa lại.

## Stretch Goals

- Dùng `kubectl get pod <pod> -o yaml` và tìm `.metadata.ownerReferences`.
- So sánh output `kubectl api-resources` giữa K3s và một cluster managed nếu bạn có.
- Nếu có nhiều node, cordon một node rồi quan sát scheduling cho Pod mới:

```bash
kubectl cordon <node-name>
kubectl uncordon <node-name>
```
