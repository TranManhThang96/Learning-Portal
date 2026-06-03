# Bài thực hành - Day 20: CNI deep-dive

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`, `curlimages/curl:8.10.1`; optional `nicolaka/netshoot`.
- Nếu muốn inspect node-level CNI config, cần quyền vào Linux node hoặc k3d node container.
- Multi-node cluster là cần thiết để kết luận về cross-node routing/overlay. Single-node chỉ đủ cho Track A no-root: object inspection, Service vs direct Pod IP và CNI inventory.

## Timebox và track lựa chọn

- Core Path Track A no-root: Task 1-3, khoảng 70-80 phút. Hoàn thành được trên single-node, nhưng phải ghi rõ giới hạn là chưa kiểm chứng cross-node.
- Optional Track B node/multi-node: Task 4-6 và Stretch Goals, 45-90 phút tùy quyền node/tooling.
- Các command dùng cú pháp Bash/WSL. Với PowerShell, thay `grep -E` bằng `Select-String -Pattern`.
- Không chạy command root/node-level nếu bạn không có node lab riêng hoặc quyền vận hành phù hợp.

## Lab Scenario

Bạn sẽ xác định CNI hiện tại, triển khai workload có nhiều replicas, so sánh Service traffic với direct Pod IP traffic, kiểm tra same-node/cross-node behavior nếu có multi-node, rồi chỉ đọc node routes/CNI config khi có quyền phù hợp. Policy drop được chuyển sang optional vì Day 19 đã thực hành sâu phần này.

## Task 1: Xác định CNI hiện tại (20 phút)

### Mục tiêu

Biết cluster đang dùng CNI nào thay vì đoán theo tên distro.

### Các bước thực hiện

```bash
kubectl get nodes -o wide
kubectl describe node $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
```

Tìm các Pod/DaemonSet liên quan:

```bash
kubectl -n kube-system get pods | grep -Ei 'flannel|calico|cilium|weave|canal|antrea|aws-node|azure|gke'
```

Nếu dùng K3s/k3d, bạn có thể thấy Flannel được đóng gói khác nhau tùy bản cài. Kiểm tra logs K3s nếu có quyền node:

```bash
sudo journalctl -u k3s -n 200 | grep -Ei 'flannel|cni|vxlan'
```

### Expected output

- Xác định được CNI hoặc ít nhất biết component nào đang quản Pod network.
- Ghi chú node IP, PodCIDR nếu hiển thị, và CNI Pods chạy trên node nào.

### Troubleshooting

Nếu không có DaemonSet CNI rõ ràng, đừng kết luận cluster không có CNI. Một số distro đóng gói component trong process riêng hoặc manifest managed.

## Task 2: Tạo workload để test Service và Pod IP (25 phút)

### Mục tiêu

Tạo traffic có thể kiểm tra qua Service và direct Pod IP.

### Các bước thực hiện

```bash
kubectl create namespace day20
kubectl config set-context --current --namespace=day20
```

Tạo file `echo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: echo
  template:
    metadata:
      labels:
        app: echo
    spec:
      containers:
      - name: echo
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          while true; do
            echo "pod=$HOSTNAME node=$NODE_NAME pod_ip=$POD_IP time=$(date -Iseconds)" > /www/index.html
            sleep 2
          done &
          httpd -f -p 8080 -h /www
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        ports:
        - name: http
          containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: http
          initialDelaySeconds: 2
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: echo
spec:
  selector:
    app: echo
  ports:
  - name: http
    port: 8080
    targetPort: http
---
apiVersion: v1
kind: Pod
metadata:
  name: client
  labels:
    app: client
spec:
  containers:
  - name: curl
    image: curlimages/curl:8.10.1
    command:
    - sleep
    - "3600"
```

Apply:

```bash
kubectl apply -f echo.yaml
kubectl rollout status deployment/echo
kubectl wait --for=condition=Ready pod/client --timeout=90s
kubectl get pods -o wide --show-labels
kubectl get svc,endpoints,endpointslice
```

### Verification

```bash
kubectl exec client -- curl -s --max-time 3 http://echo:8080
POD_IP=$(kubectl get pod -l app=echo -o jsonpath='{.items[0].status.podIP}')
kubectl exec client -- curl -s --max-time 3 "http://$POD_IP:8080"
```

### Expected output

- Service path hoạt động.
- Direct Pod IP path hoạt động.
- Response cho biết Pod đang nằm node nào.

## Task 3: Phân biệt same-node và cross-node (25 phút)

### Mục tiêu

Nhìn được traffic path theo node placement.

### Các bước thực hiện

```bash
kubectl get pods -o wide
kubectl get nodes -o wide
```

Nếu cluster có nhiều node nhưng Pods chưa spread, scale lên:

```bash
kubectl scale deployment echo --replicas=6
kubectl rollout status deployment/echo
kubectl get pods -o wide
```

Test từng Pod IP:

```bash
kubectl get pod -l app=echo -o custom-columns=NAME:.metadata.name,IP:.status.podIP,NODE:.spec.nodeName
```

Chọn một vài Pod IP khác node nếu có, rồi:

```bash
kubectl exec client -- curl -s --max-time 3 http://<pod-ip>:8080
kubectl exec client -- ping -c 3 <pod-ip>
```

Nếu `curlimages/curl` không có `ping`, dùng netshoot:

```bash
kubectl run netshoot --rm -it --restart=Never --image=nicolaka/netshoot --command -- bash
```

Trong netshoot:

```bash
curl -m 3 http://echo.day20.svc.cluster.local:8080
curl -m 3 http://<pod-ip>:8080
tracepath <pod-ip>
```

### Expected output

- Direct Pod IP hoạt động cả same-node và cross-node.
- Nếu cross-node fail nhưng same-node OK, nghi ngờ CNI route/overlay/firewall/MTU.
- Nếu cluster chỉ có một node, ghi lại: "Track A chỉ xác minh Pod network local-node; chưa kết luận được overlay/routed cross-node path".

## Optional Track B: Inspect CNI config và routes trên node (30 phút)

### Mục tiêu

Đọc dấu vết CNI ở node layer.

### Path A: Linux node chạy K3s

```bash
sudo ls /etc/cni/net.d
sudo cat /etc/cni/net.d/*
ip addr
ip route
ip link
```

Tìm các interface như `cni0`, `flannel.1`, `vxlan`, `cilium_host` hoặc tên khác tùy CNI.

### Path B: k3d node container

Trên host có Docker:

```bash
docker ps --format '{{.Names}}' | grep k3d
docker exec -it <k3d-node-container> sh
```

Trong node container:

```bash
ls /etc/cni/net.d
cat /etc/cni/net.d/*
ip addr
ip route
ip link
```

### Path C: Không có quyền node

Vẫn thu thập được nhiều tín hiệu bằng Kubernetes:

```bash
kubectl describe node <node>
kubectl -n kube-system describe pod <cni-pod>
kubectl -n kube-system logs <cni-pod> --tail=100
kubectl get pods -A -o wide
```

### Expected output

- Biết CNI config file nằm ở đâu nếu có quyền node.
- Thấy route/interface liên quan PodCIDR hoặc overlay.
- Có thể liên hệ Pod IP với node route hoặc CNI interface.

## Optional Deep Dive: Inject lỗi policy drop để tách policy khỏi Service/CNI routing (20 phút)

### Mục tiêu

Phân biệt "Service/Pod network hỏng" với "CNI policy engine đang drop".

### Các bước thực hiện

Tạo file `deny-client-egress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-client-egress
spec:
  podSelector:
    matchLabels:
      app: client
  policyTypes:
  - Egress
```

Apply:

```bash
kubectl apply -f deny-client-egress.yaml
kubectl get netpol
kubectl exec client -- curl -s --max-time 3 http://echo:8080 || echo "blocked by egress policy"
kubectl exec client -- curl -s --max-time 3 http://echo.day20.svc.cluster.local:8080 || echo "service DNS path also blocked"
```

### Symptom

- Client không gọi được Service.
- DNS cũng có thể fail vì egress bị deny.
- `echo` Pods và Service vẫn healthy.

### Cách điều tra

```bash
kubectl describe netpol deny-client-egress
kubectl get pods -o wide --show-labels
kubectl get svc,endpoints,endpointslice
kubectl get events --sort-by=.lastTimestamp
```

### Cách fix

Xóa policy để khôi phục:

```bash
kubectl delete netpol deny-client-egress
kubectl exec client -- curl -s --max-time 3 http://echo:8080
```

## Optional Track B: Đọc CNI logs sau khi tạo traffic (15 phút)

### Mục tiêu

Tập thói quen nhìn CNI component khi traffic có vấn đề.

### Các bước thực hiện

Tìm CNI Pod:

```bash
kubectl -n kube-system get pods -o wide | grep -Ei 'flannel|calico|cilium|antrea|weave|canal|aws-node'
```

Đọc logs tương ứng:

```bash
kubectl -n kube-system logs <cni-pod> --tail=120
kubectl -n kube-system describe pod <cni-pod>
```

Nếu dùng Cilium và có CLI:

```bash
cilium status
cilium connectivity test
```

### Expected output

- CNI Pod Ready.
- Không có lỗi IPAM, route, endpoint regeneration hoặc policy compile rõ ràng.

## Cleanup

```bash
kubectl delete namespace day20
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Chỉ test Service mà không test direct Pod IP.
- Kết luận CNI lỗi khi thật ra Service selector/EndpointSlice sai.
- Bỏ qua cross-node placement; single-node test không phát hiện overlay/routing issue.
- Không kiểm tra MTU khi overlay chạy trên VPN/cloud network.
- Cài custom CNI mà quên disable Flannel trong K3s.
- Bật default-deny egress rồi tưởng DNS/CoreDNS hỏng.
- Dùng managed Kubernetes nhưng không theo dõi IP/subnet quota.

## Stretch Goals

- Tạo k3d multi-node cluster riêng và so sánh output `ip route` giữa các node.
- Dựng cluster K3s test với `--flannel-backend=none --disable-network-policy`, sau đó cài Cilium hoặc Calico theo docs chính thức.
- Nếu dùng Cilium, bật Hubble trong lab và quan sát flow `client -> echo`.
- Test payload lớn bằng `tracepath`/`ping` để tìm MTU effective trên overlay.
- So sánh latency same-node vs cross-node bằng nhiều request ngắn.
- Gọi một endpoint ngoài cluster do bạn kiểm soát và ghi lại source IP nhìn thấy là Pod IP, node IP hay NAT/egress gateway IP.
