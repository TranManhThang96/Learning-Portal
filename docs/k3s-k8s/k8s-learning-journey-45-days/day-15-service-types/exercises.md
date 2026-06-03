# Bài thực hành - Day 15: Service types

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36` và `curlimages/curl:8.10.1`.
- Nếu dùng k3d và muốn test từ host, cluster cần port mapping phù hợp cho NodePort/LoadBalancer.

## Lab Scenario

Bạn triển khai một web app giả lập với nhiều Pods, expose nó bằng `ClusterIP`, `NodePort`, `LoadBalancer`, `ExternalName` và Headless Service. Sau đó bạn inject lỗi selector sai và `targetPort` sai để debug như production incident.

Core path khoảng 90-105 phút: Task 1, Task 2, Task 3, Task 4 và cleanup. `NodePort`, selector mismatch, `ExternalName` và Headless Service nằm trong Stretch Goals để lab không vượt 2 giờ.

## Task 1: Tạo namespace và web Deployment (20 phút)

### Mục tiêu

Tạo backend Pods có label rõ ràng và HTTP server đơn giản.

### Các bước thực hiện

```bash
kubectl create namespace day15
kubectl config set-context --current --namespace=day15
```

Tạo file `web-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
    component: frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
      component: frontend
  template:
    metadata:
      labels:
        app: web
        component: frontend
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
          initialDelaySeconds: 3
          periodSeconds: 5
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f web-deployment.yaml
kubectl rollout status deployment/web
kubectl get pods -l app=web -o wide --show-labels
```

### Expected output

- 3 Pods Running và Ready.
- Mỗi Pod có labels `app=web,component=frontend`.

## Task 2: Expose bằng ClusterIP và test nội bộ (25 phút)

### Mục tiêu

Tạo Service default cho internal traffic.

### Các bước thực hiện

Tạo file `web-clusterip.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  selector:
    app: web
    component: frontend
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply và inspect:

```bash
kubectl apply -f web-clusterip.yaml
kubectl get svc,endpoints,endpointslice
kubectl describe service web
```

Test từ trong cluster:

```bash
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://web:8080
```

Chạy vài lần để thấy response đến từ các Pods khác nhau:

```bash
kubectl run curl-loop --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh -c 'for i in 1 2 3 4 5; do curl -s http://web:8080; echo; done'
```

Nếu image `curl` trong cluster không có shell, dùng BusyBox fallback:

```bash
kubectl run wget-loop --rm -it --restart=Never --image=busybox:1.36 --command -- sh -c 'for i in 1 2 3 4 5; do wget -qO- http://web:8080; echo; done'
```

### Expected output

- Service có `ClusterIP`.
- Endpoints/EndpointSlice có 3 addresses.
- Curl trả về `pod=<pod-name>`.

## Stretch Goal: Inject lỗi selector sai và debug (15 phút)

### Mục tiêu

Nhận diện lỗi metadata trước khi đổ lỗi network.

### Lỗi cần tạo

```bash
kubectl patch service web -p '{"spec":{"selector":{"app":"web","component":"api"}}}'
kubectl get svc,endpoints,endpointslice
kubectl describe service web
kubectl get pods --show-labels
kubectl get pods -l app=web,component=api
```

Test lại:

```bash
kubectl run curl-selector --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- --max-time 5 http://web:8080
```

### Symptom

- Service vẫn có DNS và `ClusterIP`.
- Endpoints rỗng.
- Curl fail hoặc timeout vì không có backend.

### Cách fix

```bash
kubectl patch service web -p '{"spec":{"selector":{"app":"web","component":"frontend"}}}'
kubectl get endpoints,endpointslice
```

## Task 3: Inject lỗi targetPort sai và debug (25 phút)

### Mục tiêu

Phân biệt lỗi no endpoints với lỗi endpoints có nhưng port sai.

### Lỗi cần tạo

```bash
kubectl patch service web --type=json -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":9090}]'
kubectl describe service web
kubectl get endpoints web -o yaml
```

Test:

```bash
kubectl run curl-targetport --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- --max-time 5 http://web:8080
```

Điều tra app listen port:

```bash
kubectl get pods -l app=web
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Symptom

- Endpoints vẫn có address.
- Traffic fail vì Service forward tới port 9090, app listen 8080.

### Cách fix

```bash
kubectl patch service web --type=json -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":"http"}]'
kubectl run curl-fixed --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- http://web:8080
```

## Stretch Goal: Tạo NodePort Service (20 phút)

### Mục tiêu

Expose service qua port trên node để hiểu trade-off.

### Các bước thực hiện

Tạo file `web-nodeport.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
spec:
  type: NodePort
  selector:
    app: web
    component: frontend
  ports:
  - name: http
    port: 8080
    targetPort: http
    nodePort: 30080
```

Apply:

```bash
kubectl apply -f web-nodeport.yaml
kubectl get svc web-nodeport -o wide
kubectl describe svc web-nodeport
kubectl get nodes -o wide
```

Nếu node IP reachable từ máy bạn:

```bash
curl http://<node-ip>:30080
```

PowerShell:

```powershell
Invoke-WebRequest -UseBasicParsing http://<node-ip>:30080
```

### Expected output

- Service có `NodePort` 30080.
- Truy cập từ host phụ thuộc node IP, firewall, VM network hoặc k3d port mapping.

## Task 4: Tạo LoadBalancer và so sánh môi trường (20 phút)

### Mục tiêu

Thấy behavior `LoadBalancer` khác nhau giữa K3s, k3d, bare-metal và cloud.

### Các bước thực hiện

Tạo file `web-loadbalancer.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-lb
spec:
  type: LoadBalancer
  selector:
    app: web
    component: frontend
  ports:
  - name: http
    port: 80
    targetPort: http
```

Apply:

```bash
kubectl apply -f web-loadbalancer.yaml
kubectl get svc web-lb -w
```

Dừng watch sau 1-2 phút và inspect:

```bash
kubectl describe svc web-lb
kubectl get pods -A | grep -E 'svclb|traefik|metallb|cloud'
kubectl get events --sort-by=.lastTimestamp
```

Nếu không có `grep`, dùng:

```bash
kubectl get pods -A
```

### Expected output

- Trên K3s có ServiceLB, có thể thấy external IP hoặc pods liên quan `svclb`.
- Trên bare-metal không có LB integration, `EXTERNAL-IP` có thể `Pending`.
- Trên cloud, provider có thể tạo cloud load balancer thật và phát sinh chi phí.
- Trên k3d, truy cập từ host vẫn phụ thuộc port mapping khi tạo cluster; `EXTERNAL-IP` trong cluster không đảm bảo host truy cập được.

## Stretch Goal: ExternalName và Headless Service (20 phút)

### Mục tiêu

Tạo 2 Service type không giống load balancer mặc định.

### Các bước thực hiện

Tạo file `special-services.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-example
spec:
  type: ExternalName
  externalName: example.com
---
apiVersion: v1
kind: Service
metadata:
  name: web-headless
spec:
  clusterIP: None
  selector:
    app: web
    component: frontend
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply:

```bash
kubectl apply -f special-services.yaml
kubectl get svc external-example web-headless
kubectl get endpoints web-headless
```

Test DNS nếu image có tool phù hợp:

```bash
kubectl run dns-headless --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup web-headless
kubectl run dns-external --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup external-example
```

### Expected output

- `external-example` là `ExternalName` tới `example.com`.
- `web-headless` không có `ClusterIP`; DNS trả về backend addresses.

## Cleanup

```bash
kubectl delete namespace day15
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Service selector không match Pod labels.
- `targetPort` sai nhưng endpoints vẫn tồn tại.
- Test `NodePort` từ host khi k3d/VM chưa map port.
- Dùng `LoadBalancer` local rồi tưởng behavior giống cloud.
- Quên readiness probe làm Pod nhận traffic quá sớm hoặc quá muộn.
- Dùng `ExternalName` rồi mong có health check/load balancing.

## Stretch Goals

- Hoàn thành selector mismatch section nếu bạn bỏ qua core path.
- Hoàn thành `NodePort`, `ExternalName` và Headless Service sections nếu còn thời gian.
- Thêm `sessionAffinity: ClientIP` vào Service và quan sát response.
- Thử `externalTrafficPolicy: Local` với NodePort/LoadBalancer và đọc trade-off.
- Scale Deployment lên 10 replicas, quan sát EndpointSlice.
- Tạo Service không selector và tự tạo EndpointSlice thủ công để hiểu advanced use case.
