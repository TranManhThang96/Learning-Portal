# Bài thực hành - Day 16: kube-proxy modes

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36` và `curlimages/curl:8.10.1`.
- Nếu muốn inspect node-level rules, cần quyền vào node Linux hoặc node container của k3d.

## Timebox và shell notes

- Core Path: Task 1-5, khoảng 110-115 phút gồm cả buffer debug.
- Optional: Task 6 NodePort/externalTrafficPolicy và mọi node-level inspection sâu nếu bạn thiếu quyền node.
- Các command dùng cú pháp Bash/WSL. Với PowerShell, thay `grep` bằng `Select-String` hoặc ưu tiên `kubectl` selector/output field thay vì pipeline text.
- Command `iptables-save`, `ipvsadm`, `conntrack`, `nft` không được giả định có sẵn. Nếu thiếu tool, ghi lại "không đủ quyền/tooling" và tiếp tục debug ở Kubernetes object layer.

## Lab Scenario

Bạn triển khai một HTTP service nội bộ, tạo traffic qua `ClusterIP`, quan sát `EndpointSlice`, scale backend để tạo endpoint churn, rồi detect dataplane theo capability của môi trường. Mục tiêu là phân biệt lỗi Service object với lỗi kube-proxy/dataplane mà không phụ thuộc bắt buộc vào root access.

## Task 1: Tạo workload và Service (25 phút)

### Mục tiêu

Tạo backend có nhiều replicas để thấy Service load balance.

### Các bước thực hiện

```bash
kubectl create namespace day16
kubectl config set-context --current --namespace=day16
```

Tạo file `echo-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo
spec:
  replicas: 4
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
            echo "pod=$HOSTNAME node=$NODE_NAME time=$(date -Iseconds)" > /www/index.html
            sleep 1
          done &
          httpd -f -p 8080 -h /www
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        ports:
        - name: http
          containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: http
          initialDelaySeconds: 2
          periodSeconds: 5
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: echo
spec:
  type: ClusterIP
  selector:
    app: echo
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply:

```bash
kubectl apply -f echo-deployment.yaml
kubectl rollout status deployment/echo
kubectl get pods -o wide --show-labels
kubectl get svc,endpoints,endpointslice
```

### Expected output

- 4 Pods `Running` và `Ready`.
- Service `echo` có `ClusterIP`.
- EndpointSlice có 4 endpoints.

## Task 2: Tạo traffic qua Service và quan sát load balancing (25 phút)

### Mục tiêu

Thấy client gọi `ClusterIP` nhưng response đến từ nhiều Pods.

### Các bước thực hiện

```bash
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh -c 'for i in $(seq 1 20); do curl -s http://echo:8080; echo; done'
```

So sánh với endpoint hiện tại:

```bash
kubectl get endpointslice -l kubernetes.io/service-name=echo -o wide
kubectl get pods -l app=echo -o wide
```

### Verification

- Response có nhiều `pod=<pod-name>` khác nhau.
- Danh sách Pod trong response khớp với endpoints Ready.

### Troubleshooting

Nếu chỉ thấy một Pod, có thể do connection reuse hoặc Service affinity. Chạy nhiều Pod curl riêng biệt hoặc tăng số request.

## Task 3: Kiểm tra kube-proxy/dataplane mode (25 phút)

### Mục tiêu

Xác định cách cluster hiện tại triển khai Service routing.

### Bảng detect nhanh

| Tín hiệu | Kết luận thực dụng |
|---|---|
| Có DaemonSet/ConfigMap `kube-proxy` | Upstream-style kube-proxy đang được expose như workload |
| K3s không có Pod `kube-proxy` riêng | Có thể bình thường; kube-proxy được đóng gói trong K3s process |
| `iptables-save` có `KUBE-SVC` | Dataplane iptables hoặc iptables-nft compatibility đang tham gia Service NAT |
| `ipvsadm -Ln` có virtual services | IPVS mode hoặc IPVS-backed dataplane |
| CNI như Cilium báo kube-proxy replacement | Service dataplane có thể nằm trong eBPF/CNI |

### Path A: Kubernetes upstream/kubeadm/minikube

```bash
kubectl -n kube-system get ds kube-proxy
kubectl -n kube-system get pods -l k8s-app=kube-proxy -o wide
kubectl -n kube-system get configmap kube-proxy -o yaml
kubectl -n kube-system logs -l k8s-app=kube-proxy --tail=80
```

Tìm các field hoặc log liên quan tới `mode`, `iptables`, `ipvs`, `nftables`. Nếu `mode` rỗng, nhiều kube-proxy version hiểu là default mode của cluster/version đó; không tự suy luận nếu chưa đọc logs.

### Path B: K3s/k3d

```bash
kubectl -n kube-system get pods -o wide
kubectl get nodes -o wide
```

Nếu không thấy DaemonSet `kube-proxy`, ghi chú đây là behavior có thể bình thường với K3s vì component được đóng gói trong K3s process.

Nếu bạn có quyền vào Linux node chạy K3s:

```bash
sudo journalctl -u k3s -n 200
sudo iptables -V
sudo iptables-save | grep KUBE-SVC | head
sudo nft list ruleset | grep -E 'KUBE-|kube|service' | head
```

Nếu dùng k3d và có Docker trên host:

```bash
docker ps --format '{{.Names}}' | grep k3d
docker exec -it <k3d-node-container> sh
iptables-save | grep KUBE-SVC | head
```

### Expected output

- Upstream cluster thường có ConfigMap/DaemonSet `kube-proxy`.
- K3s có thể không expose kube-proxy như Pod riêng.
- Node-level `iptables-save` có thể thấy rule `KUBE-SVC` nếu đang dùng iptables-based dataplane.
- `iptables -V` có thể báo `nf_tables`; đây là nftables backend compatibility, không phải một kube-proxy mode riêng.

## Task 4: Tạo endpoint churn và quan sát dataplane update (20 phút)

### Mục tiêu

Hiểu mỗi lần scale/rollout đều làm EndpointSlice đổi và dataplane phải sync.

### Các bước thực hiện

Mở terminal 1:

```bash
kubectl get endpointslice -l kubernetes.io/service-name=echo -w
```

Mở terminal 2:

```bash
kubectl scale deployment echo --replicas=1
kubectl rollout status deployment/echo
kubectl scale deployment echo --replicas=6
kubectl rollout status deployment/echo
kubectl get pods -o wide
```

Test lại:

```bash
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh -c 'for i in $(seq 1 20); do curl -s http://echo:8080; echo; done'
```

### Expected output

- EndpointSlice thay đổi theo số Pod Ready.
- Traffic chỉ tới Pods đang Ready.

## Task 5: Inject lỗi targetPort và phân biệt với dataplane issue (20 phút)

### Mục tiêu

Không nhầm lỗi Service config với lỗi kube-proxy.

### Lỗi cần tạo

```bash
kubectl patch service echo --type=json -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":9090}]'
kubectl describe svc echo
kubectl get endpointslice -l kubernetes.io/service-name=echo
```

Test:

```bash
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://echo:8080
```

### Symptom

- EndpointSlice vẫn có endpoints.
- Curl fail vì traffic được forward tới port 9090, trong khi app listen 8080.

### Cách fix

```bash
kubectl patch service echo --type=json -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":"http"}]'
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://echo:8080
```

## Optional Deep Dive: NodePort path và externalTrafficPolicy (25 phút)

### Mục tiêu

Thấy NodePort cũng đi qua node dataplane và policy có thể đổi traffic path.

### Các bước thực hiện

Tạo file `echo-nodeport.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: echo-nodeport
spec:
  type: NodePort
  externalTrafficPolicy: Cluster
  selector:
    app: echo
  ports:
  - name: http
    port: 8080
    targetPort: http
    nodePort: 30081
```

Apply:

```bash
kubectl apply -f echo-nodeport.yaml
kubectl get svc echo-nodeport -o wide
kubectl describe svc echo-nodeport
kubectl get nodes -o wide
```

Nếu node IP reachable:

```bash
curl http://<node-ip>:30081
```

Đổi sang `Local` và quan sát:

```bash
kubectl patch svc echo-nodeport -p '{"spec":{"externalTrafficPolicy":"Local"}}'
kubectl describe svc echo-nodeport
```

### Expected output

- `Cluster` có thể forward tới endpoint trên node khác.
- `Local` chỉ dùng local endpoints, phù hợp giữ source IP nhưng cần LB health check đúng.

## Cleanup

```bash
kubectl delete namespace day16
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Tưởng K3s lỗi vì không có Pod `kube-proxy`.
- Debug node dataplane khi Service selector hoặc `targetPort` sai.
- Kết luận sai vì node thiếu `iptables-save`, `ipvsadm`, `conntrack` hoặc đang dùng `iptables-nft`.
- Test NodePort từ host nhưng VM/k3d chưa map port hoặc firewall chặn.
- Quên rằng endpoint churn làm dataplane sync liên tục.
- Kết luận eBPF nhanh hơn mà chưa benchmark traffic pattern thật.

## Stretch Goals

- Nếu dùng kubeadm/minikube, đọc ConfigMap `kube-proxy` và xác định `mode`.
- Hoàn thành Optional Deep Dive NodePort nếu node IP/port mapping reachable.
- Nếu có quyền node, so sánh rule trước/sau khi scale Deployment.
- Cài Cilium trong cluster lab riêng và so sánh cách inspect Service bằng `cilium service list`.
- Dùng load generator để quan sát CPU node, conntrack và latency khi tăng QPS.
