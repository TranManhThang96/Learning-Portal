# Day 46: Bài tập — Service Mesh & Zero-trust Overview

---

## Bài 1: Easy — Cài đặt Linkerd và Quan sát mTLS

### Context

Bạn là DevOps engineer mới join team. Team đang chạy 5 microservices trên Kubernetes nhưng chưa có encryption cho internal traffic. Task đầu tiên: cài Linkerd và bật mTLS cho 2 services demo.

### Yêu cầu

1. Tạo kind cluster với 2 worker nodes
2. Cài Linkerd control plane
3. Deploy 2 services đơn giản (frontend gọi backend)
4. Inject sidecar proxy cho cả 2 services
5. Verify mTLS đang hoạt động
6. Quan sát traffic metrics qua Linkerd dashboard hoặc CLI

### Expected Outcome

- Linkerd control plane healthy (`linkerd check` pass)
- Cả 2 deployments có 2/2 containers (app + sidecar)
- Traffic giữa 2 services được encrypt (tls=true trong tap output)
- Có thể xem success rate, RPS, latency qua `linkerd viz stat`

### Hint

- Dùng `linkerd inject` để thêm sidecar annotation vào YAML
- Dùng `linkerd viz tap` để xem real-time traffic
- Dùng `linkerd viz stat deploy -n <namespace>` để xem metrics

### Acceptance Criteria

- [ ] kind cluster running với 2 workers
- [ ] `linkerd check` pass hoàn toàn
- [ ] Pods hiển thị 2/2 READY
- [ ] `linkerd viz tap` hiển thị `tls=true`
- [ ] Screenshot hoặc output của `linkerd viz stat` với metrics

### Bonus Challenge

- Thử tắt mTLS bằng cách remove sidecar khỏi một service → quan sát traffic chuyển sang `tls=false`
- So sánh latency trước và sau khi inject sidecar

---

## Bài 2: Medium — Traffic Management với Service Profiles và Retry Policies

### Context

Team đã cài Linkerd cho staging environment. Backend service thỉnh thoảng trả về 500 errors (khoảng 5% requests). Bạn cần configure retry policy thông minh để giảm error rate mà không gây retry storm.

### Yêu cầu

1. Deploy 3 services: frontend → api-gateway → backend
2. Backend service simulate 10% failure rate (random 500 errors)
3. Inject Linkerd sidecar cho tất cả
4. Tạo ServiceProfile cho backend với:
   - Route definitions (GET / và POST /orders)
   - Retry budget (max 20% extra requests)
   - Timeout 5s cho mỗi route
5. Chỉ retry GET requests, KHÔNG retry POST requests
6. Load test và quan sát:
   - Success rate trước/sau retry policy
   - Total RPS (bao gồm retries)
   - Latency distribution

### Expected Outcome

- Backend actual error rate: ~10%
- Frontend observed error rate sau retry: < 2%
- Total RPS tăng không quá 20% so với original (retry budget)
- POST requests KHÔNG được retry

### Hint

- Dùng backend image có thể simulate failures (ví dụ: nginx + custom config trả random 500)
- Hoặc deploy app đơn giản bằng Go/Node.js random fail
- ServiceProfile `isRetryable: true/false` per route
- `linkerd viz stat` hiển thị actual vs effective success rate

### Acceptance Criteria

- [ ] 3 services deployed với sidecar (2/2 READY)
- [ ] ServiceProfile created với route definitions
- [ ] GET requests được retry, POST KHÔNG retry
- [ ] Success rate cải thiện từ ~90% lên >98%
- [ ] Retry budget = 20% → total traffic không vượt quá 120%
- [ ] Có output so sánh trước/sau khi áp dụng retry

### Bonus Challenge

- Thêm circuit breaker behavior: nếu backend fail liên tục 10 lần → eject endpoint 30s
- Monitor retry amplification factor qua Prometheus metrics

---

## Bài 3: Hard — Zero-trust Architecture Design và Service Mesh Authorization

### Context

Bạn là lead DevOps cho một FinTech startup đang chuẩn bị SOC 2 audit. Auditor yêu cầu:
1. Tất cả internal traffic phải encrypted
2. Mỗi service chỉ giao tiếp với services đã được authorize
3. Có audit log cho tất cả service-to-service calls
4. Certificate rotation tự động
5. Blast radius isolation nếu một service bị compromise

Platform hiện có 6 services:
- `web-frontend` → gọi `api-gateway`
- `api-gateway` → gọi `user-service`, `payment-service`, `order-service`
- `order-service` → gọi `payment-service`, `notification-service`
- `payment-service` → gọi external payment provider (ngoài cluster)

### Yêu cầu

1. Thiết kế zero-trust architecture cho platform trên
2. Deploy ít nhất 4 services đơn giản (mock) trên kind cluster
3. Implement:
   - mTLS strict mode
   - Authorization policies (mỗi service chỉ gọi được services cho phép)
   - Traffic policies (timeout, retry per route)
   - Audit logging cho service calls
4. Test authorization:
   - `web-frontend` gọi `user-service` trực tiếp → DENIED
   - `api-gateway` gọi `payment-service` → ALLOWED
   - `order-service` gọi `user-service` → DENIED
5. Viết security assessment document:
   - Trust boundaries diagram
   - Threat model cho service mesh
   - Certificate management strategy
   - Incident response nếu một service identity bị compromise

### Expected Outcome

- Tất cả traffic encrypted (mTLS strict)
- Unauthorized calls bị reject (403/connection refused)
- Audit log capture service-to-service calls với identity information
- Document hoàn chỉnh phục vụ SOC 2 audit

### Hint

- Linkerd Server/ServerAuthorization resources cho L4 authorization
- Hoặc dùng Istio AuthorizationPolicy cho L7 authorization
- Dùng `linkerd viz tap` làm basic audit log
- Trust boundaries: frontend → gateway → backend services → external

### Acceptance Criteria

- [ ] mTLS strict mode — KHÔNG có plaintext traffic internal
- [ ] Authorization policies enforce — unauthorized calls bị reject
- [ ] Ít nhất 3 authorization rules tested (2 ALLOW, 1 DENY)
- [ ] Audit log capture caller identity, destination, method, status
- [ ] Security assessment document đầy đủ (trust boundaries, threat model, cert strategy)
- [ ] Certificate TTL < 24h, rotation tự động verified
- [ ] Blast radius analysis: nếu `order-service` bị compromise, nó KHÔNG gọi được `user-service`

### Bonus Challenge

- Implement network-level isolation (NetworkPolicy) + mesh-level authorization → defense in depth
- Add rate limiting per service pair (api-gateway → payment-service: max 100 RPS)
- Set up Prometheus alerts cho authorization failures (>0 denials = potential attack)

---

## Solutions

<details>
<summary>Solution Bài 1: Cài đặt Linkerd và Quan sát mTLS</summary>

### Bước 1: Tạo cluster

```bash
cat <<EOF | kind create cluster --name mesh-easy --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF
```

### Bước 2: Cài Linkerd

```bash
curl -fsL https://run.linkerd.io/install | sh
export PATH=$HOME/.linkerd2/bin:$PATH

linkerd check --pre
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

# Install viz extension
linkerd viz install | kubectl apply -f -
linkerd viz check
```

### Bước 3: Deploy services

```bash
kubectl create namespace exercise1

cat <<'EOF' | kubectl apply -n exercise1 -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  selector:
    app: frontend
  ports:
  - port: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: hashicorp/http-echo:0.2.3
        args: ["-text=hello from backend", "-listen=:5678"]
        ports:
        - containerPort: 5678
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend
  ports:
  - port: 5678
EOF
```

### Bước 4: Inject sidecar

```bash
kubectl get deploy -n exercise1 -o yaml | linkerd inject - | kubectl apply -f -

# Wait
kubectl rollout status deploy/frontend -n exercise1
kubectl rollout status deploy/backend -n exercise1

# Verify 2/2
kubectl get pods -n exercise1
```

### Bước 5: Verify mTLS

```bash
# Generate traffic
kubectl exec -n exercise1 deploy/frontend -c frontend -- \
  sh -c 'while true; do curl -s http://backend:5678; sleep 1; done' &

# Tap traffic — check tls=true
linkerd viz tap deploy/frontend -n exercise1 --to deploy/backend

# Stats
linkerd viz stat deploy -n exercise1
```

### Cleanup

```bash
kubectl delete namespace exercise1
kind delete cluster --name mesh-easy
```

</details>

<details>
<summary>Solution Bài 2: Traffic Management với Retry Policies</summary>

### Bước 1: Deploy 3 services với failure simulation

```bash
kind create cluster --name mesh-medium
export PATH=$HOME/.linkerd2/bin:$PATH

linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd viz install | kubectl apply -f -
linkerd check

kubectl create namespace exercise2
```

### Backend với random failures (Go)

```bash
# Dùng nginx config để simulate failures
cat <<'EOF' | kubectl apply -n exercise2 -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  default.conf: |
    server {
      listen 8080;
      location / {
        if ($request_id ~* "[0-9a-f]$") {
          return 500 "Internal Server Error\n";
        }
        return 200 "OK from backend\n";
      }
      location /orders {
        if ($request_id ~* "[0-9a-f]$") {
          return 500 "Order Error\n";
        }
        return 200 "Order created\n";
      }
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: nginx:1.25-alpine
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: config
          mountPath: /etc/nginx/conf.d
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
      volumes:
      - name: config
        configMap:
          name: backend-config
---
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend
  ports:
  - port: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: gateway
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
spec:
  selector:
    app: api-gateway
  ports:
  - port: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: curlimages/curl:8.5.0
        command: ["sleep", "infinity"]
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  selector:
    app: frontend
  ports:
  - port: 80
EOF
```

### Bước 2: Inject sidecar

```bash
kubectl get deploy -n exercise2 -o yaml | linkerd inject - | kubectl apply -f -
kubectl rollout status deploy --all -n exercise2
```

### Bước 3: Measure baseline error rate

```bash
# 100 GET requests
kubectl exec -n exercise2 deploy/frontend -c frontend -- \
  sh -c 'for i in $(seq 1 100); do 
    code=$(curl -s -o /dev/null -w "%{http_code}" http://backend:8080/)
    echo $code
  done' | sort | uniq -c
```

### Bước 4: Apply ServiceProfile

```bash
cat <<'EOF' | kubectl apply -n exercise2 -f -
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: backend.exercise2.svc.cluster.local
  namespace: exercise2
spec:
  routes:
  - name: "GET /"
    condition:
      method: GET
      pathRegex: "/"
    isRetryable: true
    responseClasses:
    - condition:
        status:
          min: 500
          max: 599
      isFailure: true
  - name: "POST /orders"
    condition:
      method: POST
      pathRegex: "/orders"
    isRetryable: false
    responseClasses:
    - condition:
        status:
          min: 500
          max: 599
      isFailure: true
  retryBudget:
    retryRatio: 0.2
    minRetriesPerSecond: 10
    ttl: 10s
EOF
```

### Bước 5: Measure after retry

```bash
# Same test — success rate should improve
kubectl exec -n exercise2 deploy/frontend -c frontend -- \
  sh -c 'for i in $(seq 1 100); do 
    code=$(curl -s -o /dev/null -w "%{http_code}" http://backend:8080/)
    echo $code
  done' | sort | uniq -c

# Check stats
linkerd viz stat deploy -n exercise2
```

### Cleanup

```bash
kubectl delete namespace exercise2
kind delete cluster --name mesh-medium
```

</details>

<details>
<summary>Solution Bài 3: Zero-trust Architecture Design</summary>

### Architecture Design

```
Trust Boundaries:
┌────────────────────────────────────────────────┐
│ External Zone                                  │
│  Users ──→ [Ingress/LB]                       │
└──────────────┬─────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────┐
│ DMZ Zone                                       │
│  web-frontend (public-facing)                  │
└──────────────┬─────────────────────────────────┘
               │ mTLS
┌──────────────▼─────────────────────────────────┐
│ Gateway Zone                                   │
│  api-gateway (authentication, authorization)   │
└──────┬───────┬──────────┬──────────────────────┘
       │       │          │ mTLS
┌──────▼───────▼──────────▼──────────────────────┐
│ Service Zone                                   │
│  user-service  payment-service  order-service  │
│                                notification    │
└─────────────────────────┬──────────────────────┘
                          │ mTLS + egress control
┌─────────────────────────▼──────────────────────┐
│ External API Zone                              │
│  Payment Provider (Stripe/PayPal)              │
└────────────────────────────────────────────────┘
```

### Deploy

```bash
kind create cluster --name mesh-hard
export PATH=$HOME/.linkerd2/bin:$PATH

linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd viz install | kubectl apply -f -

kubectl create namespace fintech
kubectl annotate namespace fintech linkerd.io/inject=enabled
```

### Deploy mock services

```bash
cat <<'EOF' | kubectl apply -n fintech -f -
# web-frontend
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web-frontend
  template:
    metadata:
      labels:
        app: web-frontend
    spec:
      serviceAccountName: web-frontend
      containers:
      - name: app
        image: curlimages/curl:8.5.0
        command: ["sleep", "infinity"]
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: web-frontend
---
apiVersion: v1
kind: Service
metadata:
  name: web-frontend
spec:
  selector:
    app: web-frontend
  ports:
  - port: 80
---
# api-gateway
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      serviceAccountName: api-gateway
      containers:
      - name: app
        image: hashicorp/http-echo:0.2.3
        args: ["-text=api-gateway", "-listen=:8080"]
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
spec:
  selector:
    app: api-gateway
  ports:
  - port: 8080
---
# user-service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      serviceAccountName: user-service
      containers:
      - name: app
        image: hashicorp/http-echo:0.2.3
        args: ["-text=user-service", "-listen=:8080"]
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: user-service
---
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  selector:
    app: user-service
  ports:
  - port: 8080
---
# payment-service
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-service
  template:
    metadata:
      labels:
        app: payment-service
    spec:
      serviceAccountName: payment-service
      containers:
      - name: app
        image: hashicorp/http-echo:0.2.3
        args: ["-text=payment-service", "-listen=:8080"]
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 50m
            memory: 32Mi
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: payment-service
---
apiVersion: v1
kind: Service
metadata:
  name: payment-service
spec:
  selector:
    app: payment-service
  ports:
  - port: 8080
EOF
```

### Authorization Policies (Linkerd)

```bash
cat <<'EOF' | kubectl apply -n fintech -f -
# Server definition cho api-gateway
apiVersion: policy.linkerd.io/v1beta2
kind: Server
metadata:
  name: api-gateway-http
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  port: 8080
  proxyProtocol: HTTP/2
---
# Chỉ web-frontend được gọi api-gateway
apiVersion: policy.linkerd.io/v1alpha1
kind: ServerAuthorization
metadata:
  name: api-gateway-auth
spec:
  server:
    name: api-gateway-http
  client:
    meshTLS:
      serviceAccounts:
      - name: web-frontend

---
# Server definition cho user-service
apiVersion: policy.linkerd.io/v1beta2
kind: Server
metadata:
  name: user-service-http
spec:
  podSelector:
    matchLabels:
      app: user-service
  port: 8080
  proxyProtocol: HTTP/2
---
# Chỉ api-gateway được gọi user-service
apiVersion: policy.linkerd.io/v1alpha1
kind: ServerAuthorization
metadata:
  name: user-service-auth
spec:
  server:
    name: user-service-http
  client:
    meshTLS:
      serviceAccounts:
      - name: api-gateway

---
# Server definition cho payment-service
apiVersion: policy.linkerd.io/v1beta2
kind: Server
metadata:
  name: payment-service-http
spec:
  podSelector:
    matchLabels:
      app: payment-service
  port: 8080
  proxyProtocol: HTTP/2
---
# api-gateway + order-service được gọi payment-service
apiVersion: policy.linkerd.io/v1alpha1
kind: ServerAuthorization
metadata:
  name: payment-service-auth
spec:
  server:
    name: payment-service-http
  client:
    meshTLS:
      serviceAccounts:
      - name: api-gateway
      - name: order-service
EOF
```

### Test Authorization

```bash
# ALLOWED: web-frontend → api-gateway
kubectl exec -n fintech deploy/web-frontend -c app -- \
  curl -s http://api-gateway:8080/
# Expected: "api-gateway"

# DENIED: web-frontend → user-service (direct)
kubectl exec -n fintech deploy/web-frontend -c app -- \
  curl -s -o /dev/null -w "%{http_code}" http://user-service:8080/
# Expected: 403

# ALLOWED: api-gateway → user-service
kubectl exec -n fintech deploy/api-gateway -c app -- \
  curl -s http://user-service:8080/
# Expected: "user-service"
```

### Security Assessment Document (outline)

```markdown
# Zero-trust Security Assessment — FinTech Platform

## Trust Boundaries
- External → DMZ: TLS termination at Ingress
- DMZ → Gateway: mTLS (Linkerd)
- Gateway → Services: mTLS + ServiceAuthorization
- Services → External APIs: egress mTLS + allowlist

## Threat Model
1. Compromised service → lateral movement limited by authorization
2. Certificate theft → 24h TTL limits exposure window
3. Control plane compromise → full mesh control (mitigate: RBAC)
4. Sidecar bypass → NetworkPolicy as L3/L4 backup

## Certificate Management
- Issuer: Linkerd Identity (trust anchor)
- Leaf cert TTL: 24 hours
- Root cert TTL: 1 year (set alert at 30 days)
- Rotation: automatic by Linkerd

## Incident Response
- If service identity compromised:
  1. Remove ServerAuthorization for that service
  2. Scale down compromised deployment
  3. Rotate certificates
  4. Investigate audit logs
```

### Cleanup

```bash
kubectl delete namespace fintech
kind delete cluster --name mesh-hard
```

</details>

