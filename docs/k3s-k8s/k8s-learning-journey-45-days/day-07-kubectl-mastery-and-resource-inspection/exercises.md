# Bài thực hành - Day 07: kubectl mastery và resource inspection

## Prerequisites

- K3s cluster từ các ngày trước đang chạy.
- `kubectl` trỏ đúng cluster.
- Có quyền tạo namespace và workload.
- Khuyến nghị có `jq`, nhưng bài lab vẫn hoàn thành được nếu không có.

## Lab Scenario

Bạn nhận một namespace có nhiều object và một service không hoạt động. Nhiệm vụ là dùng `kubectl` để điều tra theo API state: context, namespace, labels, events, Pod status, Service endpoint và rollout.

## Core Path trong 2 giờ

Core path là Task 1-6, khoảng 110-115 phút. Các phần alias, restart count report và so sánh command nâng cao nằm ở `Stretch Goals`.

## Task 1: Xác nhận context và tạo namespace lab (10 phút)

### Mục tiêu

Không thao tác nhầm cluster/namespace.

### Các bước thực hiện

```bash
kubectl config current-context
kubectl config get-contexts
kubectl cluster-info
kubectl create namespace day07
kubectl config set-context --current --namespace=day07
kubectl get ns
```

K3s alternative:

```bash
sudo k3s kubectl get nodes
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get pods -A
```

### Expected output

- Current context đúng cluster lab.
- Namespace `day07` tồn tại.
- Các lệnh sau nếu không có `-n` sẽ chạy trong namespace `day07`.

### Troubleshooting

- Nếu không tạo được namespace, kiểm tra RBAC.
- Nếu API server không phản hồi, quay lại Day 05 control plane checklist.

## Task 2: Deploy workload mẫu và inspect resource graph (20 phút)

### Mục tiêu

Đọc Deployment, ReplicaSet, Pod, labels và owner references.

### Các bước thực hiện

```bash
kubectl create deployment web --image=nginx:1.27 --replicas=2
kubectl expose deployment web --port=80 --target-port=80
kubectl get deploy,rs,pod,svc,endpoints,endpointslice -o wide
kubectl get pods --show-labels
kubectl describe deployment web
```

Lấy owner của một Pod:

```bash
kubectl get pod <pod-name> -o jsonpath='{.metadata.ownerReferences[*].kind}{" "}{.metadata.ownerReferences[*].name}{"\n"}'
```

### Expected output

- Deployment tạo một ReplicaSet.
- ReplicaSet tạo hai Pod.
- Service có ClusterIP.
- EndpointSlice có Pod IP nếu Pod ready.

### Verification

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sS http://web.day07.svc.cluster.local
```

Kết quả trả HTML nginx.

## Task 3: Luyện output formats và JSONPath (20 phút)

### Mục tiêu

Trích xuất đúng field thay vì đọc output quá rộng.

### Các bước thực hiện

```bash
kubectl get pods -o wide
kubectl get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,PHASE:.status.phase,IP:.status.podIP
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.spec.nodeName}{"\n"}{end}'
kubectl get svc web -o jsonpath='{.spec.clusterIP}{"\n"}'
kubectl get deployment web -o yaml
```

Nếu có `jq`:

```bash
kubectl get pods -o json | jq '.items[] | {name: .metadata.name, node: .spec.nodeName, phase: .status.phase}'
```

### Expected output

Bạn có bảng Pod gồm name, node, phase, IP và biết ClusterIP của Service.

### Troubleshooting

- JSONPath sai thường trả output rỗng. Đối chiếu lại với `-o yaml`.
- PowerShell có thể xử lý quote khác Bash; nếu lỗi quote, chạy trong WSL/Linux shell hoặc đổi outer quote phù hợp.
- Nếu cần output portable hơn JSONPath phức tạp, ưu tiên `custom-columns`.

## Task 4: Inject lỗi image và đọc events (20 phút)

### Mục tiêu

Không debug app logs khi container chưa start.

### Lỗi cần tạo

```bash
kubectl create deployment bad-image --image=nginx:this-tag-does-not-exist
kubectl get pods -w
```

Mở terminal khác hoặc dừng watch bằng `Ctrl+C`, rồi chạy:

```bash
kubectl get pods -o wide
kubectl describe pod -l app=bad-image
kubectl get events --sort-by=.lastTimestamp
kubectl events --types=Warning
```

### Symptom

- Pod vào `ErrImagePull` hoặc `ImagePullBackOff`.
- Events cho biết pull image fail.

### Cách fix

```bash
kubectl set image deployment/bad-image nginx=nginx:1.27
kubectl rollout status deployment/bad-image
kubectl get pods
```

## Task 5: Inject lỗi Service selector sai (20 phút)

### Mục tiêu

Phân biệt Service tồn tại với Service có backend.

### Lỗi cần tạo

```bash
kubectl patch svc web --type=merge -p '{"spec":{"selector":{"app":"wrong"}}}'
kubectl get svc,endpoints,endpointslice
kubectl describe svc web
kubectl get pods --show-labels
```

Test:

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -m 5 -v http://web.day07.svc.cluster.local
```

### Symptom

- Service vẫn có ClusterIP.
- Endpoint rỗng.
- Curl fail vì không có backend.

### Cách fix

```bash
kubectl patch svc web --type=merge -p '{"spec":{"selector":{"app":"web"}}}'
kubectl get endpoints,endpointslice
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sS http://web.day07.svc.cluster.local
```

Nếu shell làm hỏng JSON quote, tạo file `selector-web.json` rồi dùng:

```bash
kubectl patch svc web --type=merge --patch-file selector-web.json
```

## Task 6: API discovery, field selector và preflight checks (25 phút)

### Mục tiêu

Tìm field không cần Google, lọc object bằng field selector và kiểm tra thay đổi trước khi apply.

### Các bước thực hiện

```bash
kubectl api-resources --namespaced=true
kubectl explain pod.spec.containers
kubectl explain deployment.spec.strategy
kubectl explain service.spec.selector
kubectl get pods --field-selector=status.phase=Running
kubectl get events --field-selector type=Warning --sort-by=.lastTimestamp
kubectl wait --for=condition=Available deployment/web --timeout=60s
kubectl auth can-i get pods -n day07
kubectl auth can-i create deployments.apps -n day07
```

Tạo manifest nhỏ để thử `diff` và server-side dry-run:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: preflight-demo
data:
  owner: day07
```

Lưu thành `preflight-demo.yaml`, rồi chạy:

```bash
kubectl apply --dry-run=server -f preflight-demo.yaml
kubectl diff -f preflight-demo.yaml
kubectl apply -f preflight-demo.yaml
kubectl diff -f preflight-demo.yaml
```

### Expected output

- Bạn biết resource nào namespaced và đọc được mô tả field từ API schema.
- Field selector trả danh sách Pod Running và Warning events nếu có.
- `wait` thành công khi Deployment `web` Available.
- `auth can-i` trả `yes` hoặc `no` rõ ràng.
- `dry-run` hiển thị object hợp lệ nhưng không tạo thật.
- `diff` trước khi apply có thể trả exit code `1` khi có khác biệt; đó không phải lỗi lab nếu output đúng là phần sẽ thay đổi.
- Sau khi apply, `diff` không còn output khác biệt đáng kể.

### PowerShell notes

```powershell
kubectl api-resources | Select-Object -First 10
$env:KUBECONFIG='/etc/rancher/k3s/k3s.yaml'
```

## Cleanup

```bash
kubectl delete namespace day07
```

Nếu đã set namespace mặc định:

```bash
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Chạy lab trong namespace `default` rồi khó cleanup.
- Không đọc `events` khi Pod pull image lỗi.
- Nhầm Service ClusterIP với backend sẵn sàng.
- Dùng JSONPath khi chưa xem cấu trúc YAML thật.

## Stretch Goals

- Viết alias shell cho `kubectl get events -A --sort-by=.lastTimestamp`.
- Tạo custom columns liệt kê Pod restart count theo namespace.
- Dùng `kubectl wait --for=condition=Available deployment/web --timeout=60s`.
- So sánh `kubectl get events` và `kubectl events` trên version `kubectl` bạn đang dùng.
