# Bài thực hành - Day 05: Control plane deep-dive

## Prerequisites

- K3s cluster từ Day 04 đang chạy.
- `kubectl` trỏ đúng context.
- Có quyền đọc namespace `kube-system`.
- Có quyền SSH/shell vào K3s server để đọc `systemd` logs.

## Lab Scenario

Bạn đang trực on-call cho cluster K3s lab. Một team báo deploy đã apply nhưng Pod không chạy. Bạn cần phân biệt lỗi nằm ở API server, scheduler, controller hay worker node.

Core Path: Task 1-6 khoảng 105-115 phút. Stretch Goals giữ các phần datastore/restore sâu hơn để không vượt khung 2 giờ.

## Task 1: Inventory control plane health (20 phút)

### Mục tiêu

Xác định API server có healthy không và control plane đang expose những component nào trong K3s.

### Các bước thực hiện

```bash
kubectl cluster-info
kubectl get --raw='/readyz?verbose'
kubectl get --raw='/livez?verbose'
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
kubectl get events -A --sort-by=.lastTimestamp
kubectl get lease -A
```

Trên K3s server:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 100 --no-pager
```

### Expected output

- `/readyz` và `/livez` trả các check `ok` hoặc thông tin đủ để biết check nào fail.
- `k3s` service active.
- Bạn xác định được Pod hệ thống nào do K3s packaged.
- Nếu có quyền, bạn thấy `Lease` cho node heartbeat hoặc leader election; nếu RBAC không cho đọc, ghi chú lại quyền thiếu.

### Troubleshooting

- Nếu `kubectl` timeout, kiểm tra kubeconfig endpoint và `systemctl status k3s`.
- Nếu `/readyz` fail, lưu lại check fail trước khi restart service.

## Task 2: Quan sát luồng Deployment -> ReplicaSet -> Pod (20 phút)

### Mục tiêu

Thấy controller tạo object mới sau khi API server nhận desired state.

### Các bước thực hiện

```bash
kubectl create namespace day05
kubectl -n day05 create deployment api-demo --image=nginx:1.27 --replicas=2
kubectl -n day05 get deploy,rs,pod -o wide
kubectl -n day05 describe deployment api-demo
kubectl -n day05 get events --sort-by=.lastTimestamp
```

Scale Deployment:

```bash
kubectl -n day05 scale deployment api-demo --replicas=4
kubectl -n day05 get deploy,rs,pod -o wide
```

### Expected output

- Deployment tạo ReplicaSet.
- ReplicaSet tạo Pod.
- Khi scale, controller tạo thêm Pod để đạt desired replicas.

### Verification

Xóa một Pod bất kỳ:

```bash
kubectl -n day05 delete pod <pod-name>
kubectl -n day05 get pods -w
```

Controller tạo Pod mới để bù lại replica bị xóa.

## Task 3: Tạo lỗi scheduler bằng nodeSelector sai (25 phút)

### Mục tiêu

Phân biệt API accepted object với scheduler không tìm được node.

### Các bước thực hiện

Tạo file `unschedulable-demo.yaml` để tránh lỗi quoting giữa Bash/PowerShell:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: unschedulable-demo
  namespace: day05
spec:
  nodeSelector:
    day05: missing-node
  containers:
    - name: nginx
      image: nginx:1.27
```

Apply và kiểm tra:

```bash
kubectl apply -f unschedulable-demo.yaml
kubectl -n day05 get pod unschedulable-demo
kubectl -n day05 describe pod unschedulable-demo
kubectl -n day05 get events --sort-by=.lastTimestamp
```

### Expected output

- Pod ở trạng thái `Pending`.
- Events có lý do liên quan `nodeSelector`/node affinity không match.

### Cách fix

Gắn label phù hợp cho một node:

```bash
kubectl label node <node-name> day05=missing-node
kubectl -n day05 get pod unschedulable-demo -w
```

Sau khi Pod chạy, dọn label:

```bash
kubectl label node <node-name> day05-
kubectl -n day05 delete pod unschedulable-demo
```

### Troubleshooting

- Nếu Pod vẫn schedule được, kiểm tra lại `nodeSelector` trong file YAML có đúng `day05: missing-node` không.
- Nếu Pod vẫn pending sau khi label, đọc lại `kubectl describe pod`.

## Task 4: Quan sát API object raw state (15 phút)

### Mục tiêu

Đọc `spec`, `status`, `metadata` để hiểu API server lưu gì.

### Các bước thực hiện

```bash
kubectl -n day05 get deployment api-demo -o yaml
kubectl -n day05 get rs -o yaml
kubectl -n day05 get pods -o yaml
```

Tập trung vào:

- `metadata.ownerReferences`
- `metadata.labels`
- `spec.replicas`
- `status.replicas`
- `status.conditions`
- `spec.nodeName` trên Pod đã schedule

### Expected output

Bạn thấy quan hệ ownership Deployment -> ReplicaSet -> Pod và thấy Pod nào đã có `spec.nodeName`.

## Task 5: Inject lỗi EndpointSlice reconciliation bằng selector mismatch an toàn (20 phút)

### Mục tiêu

Thấy `EndpointSlice controller` phụ thuộc label/selector để tạo endpoint cho `Service`. Đây là lỗi reconciliation ở lớp endpoint, không phải bằng chứng `kube-controller-manager` hỏng.

### Các bước thực hiện

Tạo Service selector sai để minh họa controller/endpoints không có backend:

```bash
kubectl -n day05 expose deployment api-demo --port=80 --target-port=80 --name=api-demo
kubectl -n day05 get svc,endpoints,endpointslice
```

Tạo file `day05-wrong-selector-patch.yaml`:

```yaml
spec:
  selector:
    app: does-not-exist
```

Apply patch:

```bash
kubectl -n day05 patch svc api-demo --type=merge --patch-file day05-wrong-selector-patch.yaml
kubectl -n day05 get svc,endpoints,endpointslice
kubectl -n day05 describe svc api-demo
```

### Symptom

- Service tồn tại.
- Endpoint rỗng hoặc không trỏ đến Pod.
- Đây không phải lỗi kube-proxy đầu tiên; selector sai làm controller không tạo endpoint đúng.

### Cách fix

Tạo file `day05-correct-selector-patch.yaml`:

```yaml
spec:
  selector:
    app: api-demo
```

Fix:

```bash
kubectl -n day05 patch svc api-demo --type=merge --patch-file day05-correct-selector-patch.yaml
kubectl -n day05 get endpoints,endpointslice
```

### Verification

Endpoint xuất hiện lại sau khi selector đúng.

## Task 6: Cleanup (5 phút)

```bash
kubectl delete namespace day05
```

## Common Pitfalls

- Nhìn Pod `Pending` rồi debug container runtime ngay; scheduler chưa gán node thì runtime chưa liên quan.
- Quên đọc events theo namespace.
- Nhầm Service có ClusterIP với Service có endpoint.
- Restart K3s quá sớm khi chỉ cần đọc scheduler/controller event.

## Stretch Goals

- Nếu K3s dùng embedded etcd, tìm hiểu command snapshot và lập kế hoạch backup/restore drill.
- Tạo Pod có `resources.requests` quá cao để sinh event `Insufficient cpu/memory`.
- So sánh output khi Deployment controller tạo Pod mới sau khi bạn xóa Pod thủ công.
- Đọc Kubernetes API object bằng `kubectl get --raw '/api/v1/namespaces/day05/pods'`.
