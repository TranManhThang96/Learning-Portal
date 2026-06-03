# Bài thực hành - Day 06: Worker node deep-dive

## Prerequisites

- K3s cluster từ Day 04 đang chạy.
- Khuyến nghị có ít nhất một worker node riêng. Nếu chỉ single-node, bỏ qua phần stop/start `k3s-agent`.
- `kubectl` trỏ đúng context.
- Có quyền shell vào node để đọc `systemd` logs.

## Lab Scenario

Một service mới deploy vào cluster nhưng không phục vụ traffic. Bạn cần xác định lỗi nằm ở runtime, readiness, Service endpoint hay node health.

## Core Path trong 2 giờ

Core path là Task 1-5, khoảng 105-110 phút. Task cordon/drain được đưa xuống `Stretch Goals` vì cần worker node riêng và có rủi ro làm gián đoạn workload khác trong lab dùng chung.

## Task 1: Inventory node state (20 phút)

### Mục tiêu

Đọc Node object, conditions, capacity và lease.

### Các bước thực hiện

```bash
kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl get lease -n kube-node-lease
kubectl top nodes
kubectl get pods -A -o wide
```

Trên K3s worker hoặc server single-node:

```bash
sudo systemctl status k3s-agent
sudo systemctl status k3s
sudo journalctl -u k3s-agent -n 100 --no-pager
sudo journalctl -u k3s -n 100 --no-pager
```

Chỉ một trong hai service có thể tồn tại tùy vai trò node.

### Expected output

Ghi lại:

- Node `Ready` hay không.
- Capacity và allocatable CPU/memory.
- Taints.
- Internal IP.
- Container runtime.
- Lease object có update gần đây.

### Troubleshooting

- Nếu `kubectl top` không chạy, metrics-server có thể chưa sẵn sàng.
- Nếu node không có `k3s-agent`, đó có thể là server node chạy service `k3s`.

## Task 2: Deploy workload và map Pod về node/runtime (20 phút)

### Mục tiêu

Thấy kubelet/runtime hiện thực hóa Pod đã được schedule.

### Các bước thực hiện

```bash
kubectl create namespace day06
kubectl -n day06 create deployment web --image=nginx:1.27 --replicas=3
kubectl -n day06 get pods -o wide
kubectl -n day06 describe pod <pod-name>
```

Trên node chứa Pod:

```bash
sudo k3s crictl ps
sudo k3s crictl images
sudo journalctl -u k3s-agent -n 100 --no-pager
```

Nếu Pod chạy trên server node single-node:

```bash
sudo journalctl -u k3s -n 100 --no-pager
sudo k3s crictl ps
```

### Expected output

- Pod có `nodeName`.
- Runtime có container tương ứng.
- Image `nginx:1.27` xuất hiện trong image list.

### Verification

```bash
kubectl -n day06 logs <pod-name>
kubectl -n day06 exec -it <pod-name> -- nginx -v
```

## Task 3: Tạo Service và kiểm tra endpoint/readiness (20 phút)

### Mục tiêu

Phân biệt Service object, endpoint và traffic thật.

### Các bước thực hiện

```bash
kubectl -n day06 expose deployment web --port=80 --target-port=80
kubectl -n day06 get svc,endpoints,endpointslice
kubectl -n day06 run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
```

Trong shell của debug Pod:

```bash
curl -v http://web.day06.svc.cluster.local
curl -v http://web
exit
```

### Expected output

- Service có ClusterIP.
- EndpointSlice có Pod IP.
- Curl trả HTML từ nginx.

### Troubleshooting

- Nếu DNS fail, kiểm tra CoreDNS.
- Nếu endpoint rỗng, kiểm tra selector và readiness.
- Nếu endpoint có nhưng curl fail, kiểm tra CNI/kube-proxy/NetworkPolicy.

## Task 4: Inject lỗi ImagePullBackOff (25 phút)

### Mục tiêu

Debug lỗi runtime/registry qua events và kubelet logs.

### Lỗi cần tạo

```bash
kubectl -n day06 create deployment bad-image --image=nginx:this-tag-should-not-exist
kubectl -n day06 get pods
kubectl -n day06 describe pod -l app=bad-image
kubectl -n day06 get events --sort-by=.lastTimestamp
```

### Symptom

- Pod vào `ErrImagePull` hoặc `ImagePullBackOff`.
- Events có thông tin pull image fail.

### Cách điều tra trên node

Tìm node của Pod:

```bash
kubectl -n day06 get pod -l app=bad-image -o wide
```

Trên node đó:

```bash
sudo journalctl -u k3s-agent -n 100 --no-pager
sudo k3s crictl images
```

### Cách fix

```bash
kubectl -n day06 set image deployment/bad-image nginx=nginx:1.27
kubectl -n day06 rollout status deployment/bad-image
kubectl -n day06 get pods -o wide
```

## Task 5: Inject lỗi Service selector sai (20 phút)

### Mục tiêu

Không nhầm lỗi Service endpoint với lỗi kube-proxy.

### Lỗi cần tạo

```bash
kubectl -n day06 patch svc web -p '{"spec":{"selector":{"app":"wrong"}}}'
kubectl -n day06 get svc,endpoints,endpointslice
kubectl -n day06 describe svc web
```

### Symptom

- Service vẫn tồn tại.
- Endpoint rỗng.
- Curl đến Service fail hoặc không có backend.

### Cách fix

```bash
kubectl -n day06 patch svc web -p '{"spec":{"selector":{"app":"web"}}}'
kubectl -n day06 get endpoints,endpointslice
```

### Verification

```bash
kubectl -n day06 run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -v http://web.day06.svc.cluster.local
```

## Cleanup

```bash
kubectl delete namespace day06
```

Nếu đã cordon mà chưa uncordon:

```bash
kubectl uncordon <worker-node-name>
```

## Common Pitfalls

- Debug `ImagePullBackOff` bằng app logs; container chưa start nên logs thường không có.
- Thấy Service có ClusterIP rồi nghĩ backend đã sẵn sàng; phải kiểm tra endpoint.
- Dùng drain trên node chứa workload stateful mà không hiểu hậu quả.
- Bỏ qua node pressure khi Pod bị evict.

## Stretch Goals

### Stretch 1: Node lifecycle - cordon/drain lab node (20 phút)

### Mục tiêu

Hiểu khác biệt giữa ngăn schedule mới và đẩy Pod ra khỏi node.

Chỉ làm nếu có worker node riêng và workload trong lab không quan trọng.

### Các bước thực hiện

```bash
kubectl cordon <worker-node-name>
kubectl get nodes
kubectl -n day06 scale deployment web --replicas=5
kubectl -n day06 get pods -o wide
```

Quan sát Pod mới không schedule vào node đã cordon.

Drain:

```bash
kubectl drain <worker-node-name> --ignore-daemonsets --delete-emptydir-data
kubectl -n day06 get pods -o wide
kubectl uncordon <worker-node-name>
```

### Troubleshooting

- Nếu drain bị chặn bởi local data hoặc DaemonSet, đọc message kỹ trước khi thêm flag.
- Production cần kiểm tra `PodDisruptionBudget` và stateful workload trước khi drain.

### Stretch khác

- Tạo Deployment có readiness probe sai để thấy Pod `Running` nhưng không vào endpoint.
- So sánh latency curl Service khi Pod ở cùng node và khác node.
- Xem `iptables` hoặc IPVS rules trên node nếu bạn muốn đào sâu kube-proxy.
- Tạo workload có `resources.requests` khác nhau và quan sát scheduling/allocatable.
