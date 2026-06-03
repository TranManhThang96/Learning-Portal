# Day 12: Bài tập — Kubernetes Networking Core

---

## Bài 1: Easy — Service Discovery cơ bản

### Context
Bạn cần deploy 2 services (frontend và backend) và đảm bảo chúng giao tiếp được qua Kubernetes DNS.

### Yêu cầu
1. Tạo Deployment `api-server` với image `hashicorp/http-echo:0.2.3`, args: `-text=API Response OK -listen=:8080`, 2 replicas.
2. Tạo ClusterIP Service `api-svc` cho `api-server`, port 80 → targetPort 8080.
3. Tạo Deployment `web-client` với image `busybox:1.36`, command: `sleep 3600`, 1 replica.
4. Exec vào `web-client` pod và verify:
   - DNS resolution cho `api-svc`.
   - HTTP request đến `api-svc` trả về response.
   - FQDN `api-svc.default.svc.cluster.local` hoạt động.
5. Kiểm tra endpoints của `api-svc`.

### Expected Outcome
- `nslookup api-svc` trả về ClusterIP.
- `wget -qO- http://api-svc` trả về "API Response OK".
- Endpoints hiển thị 2 pod IPs.

### Hints
- Dùng `kubectl exec -it <pod> -- sh` để exec vào pod.
- Dùng `nslookup`, `wget` trong busybox.
- Dùng `kubectl get endpoints` để xem endpoint list.

### Acceptance Criteria
- [ ] Deployment và Service tạo thành công
- [ ] DNS resolution hoạt động trong cluster
- [ ] HTTP request qua service name thành công
- [ ] FQDN resolution hoạt động
- [ ] Endpoints hiển thị đúng số pod IPs

### Bonus Challenge
- Tạo thêm namespace `staging`, deploy `api-server` vào đó, và gọi cross-namespace từ `web-client` ở namespace `default`.

<details>
<summary>Solution</summary>

```yaml
# api-server.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: hashicorp/http-echo:0.2.3
          args: ["-text=API Response OK", "-listen=:8080"]
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 8080
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api-svc
spec:
  selector:
    app: api-server
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
---
# web-client.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web-client
  template:
    metadata:
      labels:
        app: web-client
    spec:
      containers:
        - name: client
          image: busybox:1.36
          command: ["sleep", "3600"]
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 25m
              memory: 32Mi
```

```bash
# Deploy
kubectl apply -f api-server.yaml
kubectl apply -f web-client.yaml
kubectl wait --for=condition=Ready pod -l app=api-server --timeout=60s
kubectl wait --for=condition=Ready pod -l app=web-client --timeout=60s

# Exec into web-client
CLIENT_POD=$(kubectl get pod -l app=web-client -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $CLIENT_POD -- sh

# Inside pod:
nslookup api-svc
wget -qO- http://api-svc
wget -qO- http://api-svc.default.svc.cluster.local
exit

# Check endpoints
kubectl get endpoints api-svc

# Bonus: cross-namespace
kubectl create namespace staging
kubectl apply -f api-server.yaml -n staging
kubectl exec -it $CLIENT_POD -- wget -qO- http://api-svc.staging

# Cleanup
kubectl delete -f api-server.yaml -f web-client.yaml
kubectl delete namespace staging
```

</details>

---

## Bài 2: Medium — Service Types và Endpoint Debugging

### Context
Bạn cần triển khai một application với nhiều loại service exposure và debug các vấn đề service routing.

### Yêu cầu
1. Deploy `web-app` (nginx:1.25, 3 replicas) với ClusterIP service.
2. Tạo thêm NodePort service cho cùng app (nodePort: 30090).
3. Tạo headless service cho cùng app và so sánh DNS response với ClusterIP service.
4. Mô phỏng lỗi: thay đổi selector label để service không match pod → debug và fix.
5. Mô phỏng lỗi: set targetPort sai → debug và fix.
6. Scale deployment xuống 0, quan sát endpoints trống, scale back lên.

### Expected Outcome
- ClusterIP service trả về 1 IP (virtual IP).
- Headless service trả về 3 IPs (pod IPs).
- NodePort accessible qua node port.
- Debug flow cho selector mismatch và port mismatch được document.

### Hints
- Headless: `clusterIP: None`.
- `nslookup` trên headless service sẽ trả về nhiều IP records.
- `kubectl describe svc` hiển thị selector.
- `kubectl get endpoints` nhìn thấy endpoints trống khi selector sai.

### Acceptance Criteria
- [ ] 3 loại service (ClusterIP, NodePort, Headless) tạo thành công
- [ ] DNS khác biệt giữa ClusterIP và Headless được verify
- [ ] NodePort accessible
- [ ] Debug selector mismatch thành công
- [ ] Debug targetPort mismatch thành công
- [ ] Endpoint behavior khi scale 0 được quan sát

### Bonus Challenge
- Dùng `externalTrafficPolicy: Local` trên NodePort service và quan sát difference.
- Xem iptables rules mà kube-proxy tạo: `kubectl exec -it <kube-proxy-pod> -n kube-system -- iptables -t nat -L KUBE-SERVICES`.

<details>
<summary>Solution</summary>

```yaml
# web-app-services.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
        - name: nginx
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: web-clusterip
spec:
  selector:
    app: web-app
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
spec:
  selector:
    app: web-app
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30090
  type: NodePort
---
apiVersion: v1
kind: Service
metadata:
  name: web-headless
spec:
  clusterIP: None
  selector:
    app: web-app
  ports:
    - port: 80
      targetPort: 80
```

```bash
# Deploy
kubectl apply -f web-app-services.yaml
kubectl wait --for=condition=Ready pod -l app=web-app --timeout=60s

# Compare DNS
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- sh -c '
echo "=== ClusterIP DNS ==="
nslookup web-clusterip
echo ""
echo "=== Headless DNS ==="
nslookup web-headless
'
# ClusterIP: 1 IP (virtual IP)
# Headless: 3 IPs (pod IPs)

# Test NodePort
docker exec devops-lab-control-plane curl -s localhost:30090

# Check endpoints
kubectl get endpoints web-clusterip web-headless web-nodeport

# Simulate selector mismatch
kubectl patch svc web-clusterip -p '{"spec":{"selector":{"app":"wrong-label"}}}'
kubectl get endpoints web-clusterip
# Expected: <none>

# Fix
kubectl patch svc web-clusterip -p '{"spec":{"selector":{"app":"web-app"}}}'
kubectl get endpoints web-clusterip

# Simulate targetPort mismatch
kubectl patch svc web-clusterip -p '{"spec":{"ports":[{"port":80,"targetPort":9999}]}}'
kubectl run curl-test --rm -it --image=curlimages/curl --restart=Never -- curl -s --max-time 3 http://web-clusterip || echo "FAILED (expected)"

# Fix
kubectl patch svc web-clusterip -p '{"spec":{"ports":[{"port":80,"targetPort":80}]}}'

# Scale to 0
kubectl scale deploy web-app --replicas=0
kubectl get endpoints web-clusterip
# ENDPOINTS: <none>

kubectl scale deploy web-app --replicas=3

# Cleanup
kubectl delete -f web-app-services.yaml
```

</details>

---

## Bài 3: Hard — Multi-Service Architecture với DNS Debugging

### Context
Bạn cần triển khai một microservice architecture gồm 3 services:
- `order-api`: nhận HTTP requests.
- `payment-svc`: xử lý payment (internal).
- `notification-svc`: gửi notification (internal).

Mỗi service gọi service khác qua DNS. Bạn cần triển khai, verify communication chain, rồi inject lỗi và debug.

### Yêu cầu
1. Deploy 3 services với ClusterIP:
   - `order-api`: nginx, 2 replicas, port 80.
   - `payment-svc`: `http-echo` với text "Payment processed", 2 replicas, port 80 → 5678.
   - `notification-svc`: `http-echo` với text "Notification sent", 1 replica, port 80 → 5678.
2. Từ `order-api` pod, verify có thể gọi được cả `payment-svc` và `notification-svc`.
3. Inject lỗi 1: Delete tất cả pods của `payment-svc` → quan sát endpoints recovery.
4. Inject lỗi 2: Tạo NetworkPolicy chặn traffic từ `order-api` đến `notification-svc` (nếu CNI hỗ trợ).
5. Inject lỗi 3: Sửa CoreDNS ConfigMap thêm custom record (optional, nâng cao).
6. Document debug process cho mỗi lỗi.

### Expected Outcome
- 3 services giao tiếp thành công qua DNS.
- Khi delete pods, endpoints tạm mất rồi recovery.
- NetworkPolicy chặn traffic thành công (nếu CNI hỗ trợ).
- Debug process được document rõ ràng.

### Hints
- Dùng `kubectl exec` từ order-api pod để test connectivity.
- `kubectl get endpoints -w` để watch real-time changes.
- NetworkPolicy cần CNI hỗ trợ (Calico, Cilium). kind dùng kindnet — không hỗ trợ NetworkPolicy mặc định.
- Để test NetworkPolicy trên kind, tạo cluster với Calico CNI.

### Acceptance Criteria
- [ ] 3 services deploy và giao tiếp thành công
- [ ] Pod deletion và recovery được quan sát
- [ ] Endpoints behavior documented
- [ ] Debug process cho mỗi lỗi scenario documented
- [ ] Cleanup script hoạt động

### Bonus Challenge
- Tạo kind cluster với Calico CNI và test NetworkPolicy thực sự.
- Dùng `tcpdump` trong debug container để capture traffic giữa services.
- Profile DNS query pattern: đếm số lần CoreDNS nhận query khi gọi service 100 lần.

<details>
<summary>Solution</summary>

```yaml
# microservices.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-api
  template:
    metadata:
      labels:
        app: order-api
        tier: frontend
    spec:
      containers:
        - name: nginx
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: order-api
spec:
  selector:
    app: order-api
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-svc
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-svc
  template:
    metadata:
      labels:
        app: payment-svc
        tier: backend
    spec:
      containers:
        - name: payment
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Payment processed", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 5678
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: payment-svc
spec:
  selector:
    app: payment-svc
  ports:
    - port: 80
      targetPort: 5678
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notification-svc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: notification-svc
  template:
    metadata:
      labels:
        app: notification-svc
        tier: backend
    spec:
      containers:
        - name: notification
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Notification sent", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 5678
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: notification-svc
spec:
  selector:
    app: notification-svc
  ports:
    - port: 80
      targetPort: 5678
```

```bash
# Deploy all
kubectl apply -f microservices.yaml
kubectl wait --for=condition=Ready pod -l tier --timeout=60s

# Verify all services
kubectl get svc
kubectl get endpoints

# Test communication from order-api
ORDER_POD=$(kubectl get pod -l app=order-api -o jsonpath='{.items[0].metadata.name}')

kubectl exec $ORDER_POD -- sh -c '
echo "=== Calling payment-svc ==="
wget -qO- http://payment-svc
echo ""
echo "=== Calling notification-svc ==="
wget -qO- http://notification-svc
echo ""
echo "=== DNS check ==="
nslookup payment-svc
nslookup notification-svc
'

# === Fault Injection 1: Delete payment pods ===
echo "--- Deleting payment pods ---"
kubectl delete pods -l app=payment-svc

# Watch recovery (in another terminal or use -w)
kubectl get endpoints payment-svc -w &
kubectl wait --for=condition=Ready pod -l app=payment-svc --timeout=60s

# Verify recovery
kubectl exec $ORDER_POD -- wget -qO- http://payment-svc

# === Fault Injection 2: NetworkPolicy (requires Calico CNI) ===
cat <<'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-order-to-notification
spec:
  podSelector:
    matchLabels:
      app: notification-svc
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: payment-svc
EOF

# Test (will timeout on Calico, pass on kindnet)
kubectl exec $ORDER_POD -- wget -qO- --timeout=3 http://notification-svc || echo "Blocked by NetworkPolicy (expected with Calico)"

# Remove NetworkPolicy
kubectl delete networkpolicy deny-order-to-notification

# Cleanup
kubectl delete -f microservices.yaml
```

</details>

