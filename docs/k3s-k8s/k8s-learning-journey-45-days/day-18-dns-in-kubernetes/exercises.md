# Bài thực hành - Day 18: DNS trong Kubernetes

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Nếu muốn dùng `dig`, có thể pull thêm `nicolaka/netshoot`.

## Timebox và shell notes

- Core Path: Task 1-6, khoảng 105-110 phút với các mốc đã rút gọn.
- Optional: SRV bằng `netshoot`, CoreDNS logs sâu, NodeLocal DNSCache và NetworkPolicy DNS allow.
- Các command dùng cú pháp Bash/WSL. Với PowerShell, giữ nguyên command `kubectl` nhưng tránh phụ thuộc pipeline shell; nếu cần lọc text, dùng `Select-String`.
- Phần NetworkPolicy chỉ là preview; thực hành policy đầy đủ nằm ở Day 19.

## Lab Scenario

Bạn tạo một Service nội bộ, test DNS short name và FQDN từ cùng namespace và khác namespace, tạo Headless Service để thấy DNS trả nhiều endpoint IPs, rồi inject lỗi `dnsPolicy` sai để debug.

## Task 1: Kiểm tra CoreDNS (15 phút)

### Mục tiêu

Biết CoreDNS đang chạy ở đâu và Service DNS IP là gì.

### Các bước thực hiện

```bash
kubectl -n kube-system get svc kube-dns
kubectl -n kube-system get deploy,pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system get configmap coredns -o yaml
kubectl -n kube-system logs deploy/coredns --tail=50
```

### Expected output

- Service `kube-dns` có `ClusterIP`.
- CoreDNS Pods Ready.
- Corefile có plugin `kubernetes` và thường có `forward`/`cache`.

### Troubleshooting

Nếu label `k8s-app=kube-dns` không match, chạy:

```bash
kubectl -n kube-system get pods --show-labels | grep -i dns
```

## Task 2: Tạo web Service để test DNS (20 phút)

### Mục tiêu

Tạo Service bình thường resolve về ClusterIP.

### Các bước thực hiện

```bash
kubectl create namespace day18
kubectl config set-context --current --namespace=day18
```

Tạo file `web.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          while true; do
            echo "pod=$HOSTNAME time=$(date -Iseconds)" > /www/index.html
            sleep 2
          done &
          httpd -f -p 8080 -h /www
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
  name: web
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply:

```bash
kubectl apply -f web.yaml
kubectl rollout status deployment/web
kubectl get svc,endpoints,endpointslice
```

### Expected output

- Service `web` có ClusterIP.
- EndpointSlice có 3 endpoints.

## Task 3: Test DNS từ cùng namespace (20 phút)

### Mục tiêu

Đọc `/etc/resolv.conf` và test short name.

### Các bước thực hiện

```bash
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'cat /etc/resolv.conf; echo; nslookup web; echo; wget -qO- http://web:8080'
```

Test FQDN:

```bash
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup web.day18.svc.cluster.local
```

### Expected output

- `/etc/resolv.conf` có search domain `day18.svc.cluster.local`.
- `web` resolve được vì client Pod nằm cùng namespace `day18`.
- `wget` trả về `pod=<pod-name>`.

Sample `nslookup` rút gọn:

```text
Server:    <kube-dns-cluster-ip>
Address 1: <kube-dns-cluster-ip> kube-dns.kube-system.svc.cluster.local

Name:      web
Address 1: <web-cluster-ip> web.day18.svc.cluster.local
```

Mini demo `ndots`: so sánh query short name và FQDN tuyệt đối:

```bash
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'nslookup web; echo; nslookup web.day18.svc.cluster.local.'
```

Short name dùng search domains trong `/etc/resolv.conf`; FQDN có dấu `.` cuối tránh search expansion.

## Task 4: Test từ namespace khác và sửa bằng FQDN (15 phút)

### Mục tiêu

Thấy lỗi phổ biến khi dùng short name cross-namespace.

### Các bước thực hiện

Từ namespace `default`:

```bash
kubectl run dns-client -n default --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'cat /etc/resolv.conf; echo; nslookup web || true'
```

Test đúng bằng FQDN:

```bash
kubectl run dns-client -n default --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'nslookup web.day18.svc.cluster.local; wget -qO- http://web.day18.svc.cluster.local:8080'
```

### Expected output

- `web` short name trong namespace `default` có thể fail vì không có Service `web.default`.
- FQDN `web.day18.svc.cluster.local` hoạt động.

## Task 5: Headless Service và endpoint DNS (20 phút)

### Mục tiêu

So sánh DNS của Service bình thường và Headless Service.

### Các bước thực hiện

Tạo file `web-headless.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-headless
spec:
  clusterIP: None
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply và test:

```bash
kubectl apply -f web-headless.yaml
kubectl get svc web web-headless
kubectl get endpoints web-headless
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup web-headless
```

Optional SRV check:

```bash
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup -type=SRV _http._tcp.web.day18.svc.cluster.local
```

Nếu BusyBox không hỗ trợ query SRV rõ ràng và bạn còn thời gian, dùng netshoot:

```bash
kubectl run netshoot --rm -it --restart=Never --image=nicolaka/netshoot --command -- dig SRV _http._tcp.web.day18.svc.cluster.local
```

### Expected output

- `web` resolve về ClusterIP.
- `web-headless` resolve về nhiều Pod IP endpoint.
- SRV record trả về service/port info nếu tool hỗ trợ.

Sample khác biệt:

```text
web.day18.svc.cluster.local        -> <cluster-ip>
web-headless.day18.svc.cluster.local -> <pod-ip-1>, <pod-ip-2>, <pod-ip-3>
```

## Task 6: Inject lỗi dnsPolicy sai (20 phút)

### Mục tiêu

Hiểu Pod-level DNS config có thể làm service discovery fail dù CoreDNS khỏe.

### Lỗi cần tạo

Tạo file `bad-dns-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: bad-dns
spec:
  dnsPolicy: None
  dnsConfig:
    nameservers:
    - 203.0.113.10
  containers:
  - name: busybox
    image: busybox:1.36
    command:
    - sleep
    - "3600"
```

Apply:

```bash
kubectl apply -f bad-dns-pod.yaml
kubectl wait --for=condition=Ready pod/bad-dns --timeout=60s
kubectl exec bad-dns -- cat /etc/resolv.conf
kubectl exec bad-dns -- nslookup web.day18.svc.cluster.local
```

### Symptom

- `/etc/resolv.conf` không trỏ tới CoreDNS.
- `nslookup` timeout hoặc fail.
- CoreDNS Pods vẫn Ready.

### Cách fix

Trong production, không patch Pod trực tiếp nếu nó thuộc Deployment. Sửa manifest/controller. Với Pod lab này:

```bash
kubectl delete pod bad-dns
```

Tạo file `good-dns-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: good-dns
spec:
  dnsPolicy: ClusterFirst
  containers:
  - name: busybox
    image: busybox:1.36
    command:
    - sleep
    - "3600"
```

Apply và test:

```bash
kubectl apply -f good-dns-pod.yaml
kubectl wait --for=condition=Ready pod/good-dns --timeout=60s
kubectl exec good-dns -- cat /etc/resolv.conf
kubectl exec good-dns -- nslookup web.day18.svc.cluster.local
```

## Optional Deep Dive: Đọc CoreDNS logs và phân biệt DNS vs Service lỗi (20 phút)

### Mục tiêu

Không dừng ở DNS khi connect fail.

### Các bước thực hiện

```bash
kubectl -n kube-system logs deploy/coredns --tail=100
kubectl get svc,endpoints,endpointslice
kubectl describe svc web
kubectl get pods -o wide --show-labels
```

Inject Service selector sai:

```bash
kubectl patch service web -p '{"spec":{"selector":{"app":"missing"}}}'
kubectl run dns-client --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'nslookup web; wget -T 3 -qO- http://web:8080 || true'
kubectl get endpoints,endpointslice
```

### Symptom

- DNS vẫn resolve `web`.
- HTTP fail vì Service không còn endpoints.

### Cách fix

```bash
kubectl patch service web -p '{"spec":{"selector":{"app":"web"}}}'
kubectl get endpoints,endpointslice
```

## Cleanup

```bash
kubectl delete namespace day18
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Dùng short name cross-namespace.
- Kết luận DNS lỗi trong khi Service không endpoints.
- Quên `dnsPolicy: ClusterFirstWithHostNet` cho Pod `hostNetwork`.
- Sau Day 19: chặn UDP 53 nhưng quên TCP 53 trong NetworkPolicy.
- Sửa CoreDNS Corefile thủ công và không có rollback.
- Dùng Headless Service nhưng client không xử lý nhiều IP.
- External DNS chậm do `ndots` và thiếu caching.

## Stretch Goals

- Cài NodeLocal DNSCache trong lab riêng và so sánh query path.
- Tạo NetworkPolicy default deny egress rồi allow DNS tới `kube-dns`.
- Scale CoreDNS replicas và quan sát endpoint của Service `kube-dns`.
- Dùng `dig +search` và `dig +trace` trong netshoot để quan sát search domain behavior.
