# Bài thực hành - Day 19: Network Policies

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36` và `curlimages/curl:8.10.1`.
- CNI hoặc K3s network policy controller có khả năng enforce `NetworkPolicy`.

## Timebox và shell notes

- Core Path: Task 1-4, Task 5 mini cross-namespace và Task 6 selector debug, khoảng 105-115 phút.
- Optional: dependency chain `api -> db`, `ipBlock`, Cilium L7 và smoke test script.
- Các Pod `frontend`/`debug` dùng `curlimages/curl` để test HTTP; không giả định image này có `nslookup`. Dùng `busybox:1.36` cho DNS checks.
- Các command dùng cú pháp Bash/WSL. Với PowerShell, thay `grep` bằng `Select-String` hoặc xem output thô từ `kubectl get ... --show-labels`.

## Lab Scenario

Bạn triển khai ba service mô phỏng `frontend`, `api`, `db`. Ban đầu mọi Pod gọi được nhau. Sau đó áp dụng default-deny, mở DNS, mở `frontend -> api`, thêm một allow cross-namespace nhỏ, rồi inject lỗi selector để học cách debug policy drop.

## Task 1: Kiểm tra NetworkPolicy support (10 phút)

### Mục tiêu

Không bắt đầu lab policy khi chưa biết cluster có policy engine không.

### Các bước thực hiện

```bash
kubectl api-resources | grep -i networkpolicy
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
kubectl -n kube-system get pods --show-labels | grep -i dns
kubectl get ns kube-system --show-labels
```

Nếu dùng K3s trực tiếp trên Linux node, có thể kiểm tra service logs:

```bash
sudo journalctl -u k3s -n 200 | grep -i policy
```

### Expected output

- API resource `networkpolicies` tồn tại.
- Có CNI/policy component phù hợp, ví dụ K3s network policy controller, Calico, Cilium hoặc plugin khác.
- Biết label thực tế của CoreDNS và namespace `kube-system`.

### Troubleshooting

Nếu policy không có tác dụng ở các task sau, nghi ngờ đầu tiên là CNI không enforce hoặc policy controller bị disable.

## Task 2: Tạo namespace và workloads (20 phút)

### Mục tiêu

Tạo dependency graph đơn giản: `frontend -> api -> db`.

### Các bước thực hiện

```bash
kubectl create namespace day19
kubectl config set-context --current --namespace=day19
```

Tạo file `workloads.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        tier: backend
    spec:
      containers:
      - name: api
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          while true; do
            echo "api pod=$HOSTNAME time=$(date -Iseconds)" > /www/index.html
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
  name: api
spec:
  selector:
    app: api
  ports:
  - name: http
    port: 8080
    targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: db
spec:
  replicas: 1
  selector:
    matchLabels:
      app: db
  template:
    metadata:
      labels:
        app: db
        tier: data
    spec:
      containers:
      - name: db
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          echo "db pod=$HOSTNAME" > /www/index.html
          httpd -f -p 5432 -h /www
        ports:
        - name: db-http
          containerPort: 5432
---
apiVersion: v1
kind: Service
metadata:
  name: db
spec:
  selector:
    app: db
  ports:
  - name: db-http
    port: 5432
    targetPort: db-http
---
apiVersion: v1
kind: Pod
metadata:
  name: frontend
  labels:
    role: frontend
spec:
  containers:
  - name: curl
    image: curlimages/curl:8.10.1
    command:
    - sleep
    - "3600"
---
apiVersion: v1
kind: Pod
metadata:
  name: debug
  labels:
    role: debug
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
kubectl apply -f workloads.yaml
kubectl rollout status deployment/api
kubectl rollout status deployment/db
kubectl wait --for=condition=Ready pod/frontend --timeout=90s
kubectl wait --for=condition=Ready pod/debug --timeout=90s
kubectl get pods -o wide --show-labels
kubectl get svc,endpoints,endpointslice
```

### Verification

Trước khi có policy, mọi client gọi được `api` và `db`:

```bash
kubectl exec frontend -- curl -s --max-time 3 http://api:8080
kubectl exec frontend -- curl -s --max-time 3 http://db:5432
kubectl exec debug -- curl -s --max-time 3 http://api:8080
```

## Task 3: Áp dụng default deny và mở DNS (20 phút)

### Mục tiêu

Thấy default-deny chặn traffic, sau đó mở DNS để tránh nhầm lỗi policy với lỗi service discovery.

### Các bước thực hiện

Tạo file `baseline-policies.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

Apply:

```bash
kubectl apply -f baseline-policies.yaml
kubectl get netpol
kubectl describe netpol default-deny-all
```

Test:

```bash
kubectl run dnscheck --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup api.day19.svc.cluster.local
kubectl exec frontend -- curl -s --max-time 3 http://api:8080 || echo "blocked as expected"
```

### Expected output

- DNS resolve được nếu `allow-dns` selector đúng.
- HTTP tới `api` timeout hoặc fail vì chưa có allow rule.

### Troubleshooting

Nếu `nslookup` fail, kiểm tra label CoreDNS:

```bash
kubectl -n kube-system get pods --show-labels | grep -i dns
kubectl get ns kube-system --show-labels
```

Sửa `allow-dns` để match đúng cluster của bạn.

Fallback ít chặt hơn nhưng portable hơn cho lab: nếu CoreDNS label không phải `k8s-app=kube-dns`, có thể tạm allow DNS tới toàn bộ namespace `kube-system` trên port 53:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

## Task 4: Mở `frontend -> api` nhưng vẫn chặn `frontend -> db` (25 phút)

### Mục tiêu

Tạo allow-list đúng theo dependency graph.

### Các bước thực hiện

Tạo file `frontend-api-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-ingress-from-frontend
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-egress-to-api
spec:
  podSelector:
    matchLabels:
      role: frontend
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: api
    ports:
    - protocol: TCP
      port: 8080
```

Apply và test:

```bash
kubectl apply -f frontend-api-policy.yaml
kubectl exec frontend -- curl -s --max-time 3 http://api:8080
kubectl exec frontend -- curl -s --max-time 3 http://db:5432 || echo "db blocked as expected"
kubectl exec debug -- curl -s --max-time 3 http://api:8080 || echo "debug blocked as expected"
```

### Expected output

- `frontend -> api` thành công.
- `frontend -> db` bị chặn.
- `debug -> api` bị chặn vì `debug` không có label `role=frontend`.

## Task 5: Mini cross-namespace allow (15 phút)

### Mục tiêu

Thấy `namespaceSelector` hoạt động và phân biệt AND/OR selector qua một case nhỏ.

### Các bước thực hiện

Tạo namespace và client bên ngoài namespace `day19`:

```bash
kubectl create namespace partner
kubectl label namespace partner team=partner
kubectl run partner-client -n partner --restart=Never --image=curlimages/curl:8.10.1 --labels=role=partner-client --command -- sleep 3600
kubectl wait --for=condition=Ready pod/partner-client -n partner --timeout=90s
kubectl exec -n partner partner-client -- curl -s --max-time 3 http://api.day19.svc.cluster.local:8080 || echo "partner blocked before allow"
```

Tạo file `partner-api-policy.yaml` trong namespace `day19`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-ingress-from-partner
  namespace: day19
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          team: partner
      podSelector:
        matchLabels:
          role: partner-client
    ports:
    - protocol: TCP
      port: 8080
```

Apply và test:

```bash
kubectl apply -f partner-api-policy.yaml
kubectl exec -n partner partner-client -- curl -s --max-time 3 http://api.day19.svc.cluster.local:8080
```

### Expected output

- Trước policy, `partner-client -> api` bị chặn bởi ingress isolation của `api`.
- Sau policy, Pod trong namespace có `team=partner` và label `role=partner-client` gọi được `api`.
- `namespaceSelector` và `podSelector` trong cùng một list item là điều kiện AND.

## Optional Deep Dive: Mở `api -> db` và kiểm tra từ Pod backend (20 phút)

### Mục tiêu

Thấy dependency chain `frontend -> api -> db`, không mở `frontend -> db`.

### Các bước thực hiện

Tạo file `api-db-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-db-ingress-from-api
spec:
  podSelector:
    matchLabels:
      app: db
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api
    ports:
    - protocol: TCP
      port: 5432
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-egress-to-db
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: db
    ports:
    - protocol: TCP
      port: 5432
```

Apply:

```bash
kubectl apply -f api-db-policy.yaml
API_POD=$(kubectl get pod -l app=api -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$API_POD" -- wget -qO- --timeout=3 http://db:5432
kubectl exec frontend -- curl -s --max-time 3 http://db:5432 || echo "frontend to db still blocked"
```

### Expected output

- `api -> db` thành công.
- `frontend -> db` vẫn bị chặn.

## Task 6: Inject lỗi selector và debug (20 phút)

### Mục tiêu

Tập debug lỗi phổ biến nhất: selector không match labels thật.

### Lỗi cần tạo

Patch policy để selector nguồn sai:

```bash
kubectl patch netpol allow-api-ingress-from-frontend --type=json -p='[{"op":"replace","path":"/spec/ingress/0/from/0/podSelector/matchLabels/role","value":"frontned"}]'
```

Test:

```bash
kubectl exec frontend -- curl -s --max-time 3 http://api:8080 || echo "blocked due to typo"
```

### Cách điều tra

```bash
kubectl describe netpol allow-api-ingress-from-frontend
kubectl get pods --show-labels
kubectl get svc,endpoints,endpointslice
kubectl run dnscheck --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup api.day19.svc.cluster.local
```

Bạn cần thấy:

- DNS vẫn OK.
- Service và endpoints vẫn OK.
- Label thật là `role=frontend`.
- Policy đang match `role=frontned`.

### Cách fix

```bash
kubectl patch netpol allow-api-ingress-from-frontend --type=json -p='[{"op":"replace","path":"/spec/ingress/0/from/0/podSelector/matchLabels/role","value":"frontend"}]'
kubectl exec frontend -- curl -s --max-time 3 http://api:8080
```

## Cleanup

```bash
kubectl delete namespace day19 partner --ignore-not-found
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- CNI không enforce NetworkPolicy nhưng bạn chỉ nhìn object trong API.
- Quên allow DNS khi default-deny egress.
- Namespace selector không match vì namespace thiếu label.
- Viết hai selector thành OR trong khi muốn AND.
- Dùng selector theo Service label nhưng Pod label thực tế khác.
- Chỉ mở ingress mà quên egress khi cả hai hướng đều bị isolated.
- Mong đợi HTTP 403; policy drop thường biểu hiện thành timeout.

## Stretch Goals

- Thử một egress policy bằng `ipBlock` tới một CIDR test nội bộ hoặc endpoint kiểm soát được.
- Nếu dùng Cilium, so sánh `NetworkPolicy` chuẩn với `CiliumNetworkPolicy` L7 HTTP rule trong lab riêng.
- Viết script smoke test positive/negative cases để chạy sau mỗi lần apply policy.
