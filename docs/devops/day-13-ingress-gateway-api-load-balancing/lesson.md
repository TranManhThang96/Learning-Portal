# Day 13: Ingress, Gateway API & Load Balancing

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** vai trò của Ingress và Ingress Controller trong việc expose service ra ngoài cluster.
2. **Phân biệt được** Ingress (legacy) và Gateway API (tương lai), khi nào chọn cái nào.
3. **Cấu hình được** path-based routing và host-based routing với NGINX Ingress Controller.
4. **Thiết lập được** TLS termination với self-signed certificate trên local cluster.
5. **Mapping được** các concept Kubernetes (Ingress, LoadBalancer) sang AWS services (ALB, NLB, Route 53).

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng?

Ở Day 12, bạn đã hiểu Service types: ClusterIP (internal), NodePort (expose port trên node), LoadBalancer (cloud LB). Nhưng trong production:

- **NodePort** không phù hợp: port range giới hạn (30000-32767), không có TLS, không có routing rules.
- **LoadBalancer** tốn tiền: mỗi service = 1 cloud LB. 20 microservices = 20 load balancers = chi phí cao.

**Ingress** giải quyết vấn đề này: **1 entry point** cho nhiều services, với routing rules dựa trên path hoặc hostname.

```
KHÔNG CÓ Ingress:                    CÓ Ingress:
                                      
LB₁ → svc-A                         1 LB → Ingress Controller
LB₂ → svc-B                                   │
LB₃ → svc-C                           ┌───────┼───────┐
(3 LBs, 3 IPs, 3x cost)               svc-A  svc-B  svc-C
                                       (1 LB, 1 IP, 1x cost)
```

### Liên hệ với developer background

- **Ingress Controller** = reverse proxy (Nginx, Traefik) nhưng auto-configured bởi Kubernetes.
- **Ingress resource** = routing config trong nginx.conf, nhưng declarative YAML.
- **Gateway API** = Ingress v2, thiết kế lại với role-based config (infra team vs app team).
- **TLS termination** = SSL offloading tại reverse proxy.

### Nếu làm sai thì sao?

- **Không set TLS** → traffic HTTP plain text → dữ liệu bị sniff.
- **Routing rules sai** → request đến wrong service → data leak hoặc 404.
- **Ingress Controller không scale** → single point of failure → toàn bộ external traffic chết.
- **Không set rate limiting** → DDoS attack dễ dàng overwhelm backend.

---

## 3. Kiến thức nền tảng

### Layer 4 vs Layer 7 Load Balancing

| Feature | Layer 4 (Transport) | Layer 7 (Application) |
|---------|--------------------|-----------------------|
| **Hoạt động ở** | TCP/UDP level | HTTP/HTTPS level |
| **Routing dựa trên** | IP, Port | URL path, Host header, Headers |
| **TLS termination** | Pass-through hoặc terminate | Terminate (đọc HTTP) |
| **Performance** | Faster (ít processing) | Slower (parse HTTP) |
| **Kubernetes** | Service type LoadBalancer | Ingress / Gateway API |
| **AWS** | NLB (Network LB) | ALB (Application LB) |

### Ingress = L7 routing rule cho Kubernetes

```
Internet
    │
    ▼
┌─────────────────────────┐
│   Load Balancer (L4)    │  ← Cloud LB hoặc MetalLB
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Ingress Controller    │  ← NGINX, Traefik, HAProxy
│   (L7 reverse proxy)   │
└───────────┬─────────────┘
            │
    ┌───────┼───────┐
    │       │       │
    ▼       ▼       ▼
  svc-A   svc-B   svc-C     ← ClusterIP Services
```

**Hai thành phần cần hiểu:**

1. **Ingress Controller**: phần mềm thực sự xử lý traffic (NGINX pod chạy trong cluster).
2. **Ingress Resource**: YAML config mô tả routing rules (path, host → service).

---

## 4. Deep Dive

### 4.1 Ingress Resource

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx          # Chọn Ingress Controller
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls-secret   # TLS certificate
  rules:
    - host: app.example.com        # Host-based routing
      http:
        paths:
          - path: /api              # Path-based routing
            pathType: Prefix
            backend:
              service:
                name: api-svc
                port:
                  number: 80
          - path: /web
            pathType: Prefix
            backend:
              service:
                name: web-svc
                port:
                  number: 80
```

### Path Types

| pathType | Behavior | Ví dụ |
|----------|----------|-------|
| `Prefix` | Match prefix | `/api` matches `/api`, `/api/users`, `/api/v2` |
| `Exact` | Match chính xác | `/api` chỉ match `/api`, không match `/api/users` |
| `ImplementationSpecific` | Tuỳ Ingress Controller | Tuỳ controller |

### 4.2 Ingress Controllers phổ biến

```
┌──────────────────────────────────────────────────────┐
│                Ingress Controllers                     │
│                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │   NGINX     │  │   Traefik   │  │    HAProxy   │ │
│  │             │  │             │  │              │ │
│  │ Most popular│  │ Auto-config │  │ High perf    │ │
│  │ Battle-test │  │ Let's Encr. │  │ TCP/UDP      │ │
│  │ Rich annot. │  │ Dashboard   │  │ Enterprise   │ │
│  └─────────────┘  └─────────────┘  └──────────────┘ │
│                                                        │
│  ┌─────────────┐  ┌─────────────┐                    │
│  │ AWS ALB     │  │   Istio     │                    │
│  │ Controller  │  │   Gateway   │                    │
│  │             │  │             │                    │
│  │ Native ALB  │  │ Service mesh│                    │
│  │ AWS only    │  │ Full L7     │                    │
│  └─────────────┘  └─────────────┘                    │
└──────────────────────────────────────────────────────┘
```

| Controller | Ưu điểm | Nhược điểm | Best for |
|------------|---------|------------|----------|
| **NGINX Ingress (`kubernetes/ingress-nginx`)** | Battle-tested, rich annotations, vẫn hữu ích để học Ingress API/local lab | Kubernetes project đã retire/archived từ 03/2026; không còn security fixes | Legacy clusters, migration analysis, local lab |
| **Traefik** | Auto Let's Encrypt, dashboard built-in, middleware | Ít annotation hơn NGINX | Startup, auto TLS |
| **AWS ALB** | Native integration, no extra pod | AWS only, limited customization | EKS workloads |
| **Istio Gateway** | Full L7, mTLS, traffic management | Heavy (sidecar), phức tạp | Service mesh environments |

> **Production note (2026)**: `kubernetes/ingress-nginx` đã bị Kubernetes retire/archived sau tháng 03/2026. Hands-on trong bài vẫn dùng NGINX Ingress để học Ingress API vì local setup đơn giản, nhưng production mới nên chọn Gateway API với controller còn maintained (ví dụ Envoy Gateway, Traefik, HAProxy, Istio Gateway, F5 NGINX Ingress Controller hoặc cloud-native ALB/Gateway tùy môi trường).

### 4.3 Gateway API — tương lai của Ingress

Gateway API là spec mới thay thế Ingress, được thiết kế với:

**Separation of concerns:**

```
┌─────────────────────────────────────────────┐
│  Infra Team (cluster admin)                  │
│  ┌────────────────┐  ┌───────────────────┐  │
│  │  GatewayClass  │  │     Gateway       │  │
│  │  (như storage   │  │  (like LB config) │  │
│  │   class)       │  │  listeners, ports │  │
│  └────────────────┘  └───────────────────┘  │
├─────────────────────────────────────────────┤
│  App Team (developers)                       │
│  ┌────────────────┐  ┌───────────────────┐  │
│  │   HTTPRoute    │  │    GRPCRoute      │  │
│  │  (path/host    │  │  (gRPC routing)   │  │
│  │   routing)     │  │                   │  │
│  └────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────┘
```

```yaml
# Gateway (infra team creates)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: main-gateway
spec:
  gatewayClassName: nginx
  listeners:
    - name: http
      port: 80
      protocol: HTTP
    - name: https
      port: 443
      protocol: HTTPS
      tls:
        certificateRefs:
          - name: app-tls-secret
---
# HTTPRoute (app team creates)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  parentRefs:
    - name: main-gateway
  hostnames:
    - api.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /v1
      backendRefs:
        - name: api-v1-svc
          port: 80
    - matches:
        - path:
            type: PathPrefix
            value: /v2
      backendRefs:
        - name: api-v2-svc
          port: 80
```

### Ingress vs Gateway API

| Feature | Ingress | Gateway API |
|---------|---------|-------------|
| **Status** | Stable, widespread | GA (v1.0+), growing adoption |
| **Role separation** | Single resource | GatewayClass → Gateway → *Route |
| **Protocol** | HTTP/HTTPS only | HTTP, gRPC, TCP, UDP, TLS |
| **Config approach** | Annotations (vendor-specific) | Typed fields (portable) |
| **Traffic splitting** | Via annotations (controller-specific) | Native weight-based routing |
| **Header matching** | Via annotations | Native |
| **Recommendation** | Existing clusters, simple routing | New projects, complex routing |

### 4.4 AWS Mapping

| Kubernetes Concept | AWS Service | Khi nào dùng |
|-------------------|-------------|-------------|
| Service type: LoadBalancer | NLB (L4) | TCP/UDP direct, high performance |
| Ingress (with ALB controller) | ALB (L7) | HTTP routing, path/host-based |
| External DNS | Route 53 | DNS management |
| cert-manager | ACM | TLS certificate |
| Ingress TLS | ALB + ACM | HTTPS termination |

---

## 5. Trade-offs & Best Practices ⭐

### Chọn Ingress Controller nào?

| Scenario | Recommendation | Lý do |
|----------|---------------|-------|
| **Local lab / legacy Ingress** | NGINX Ingress | Dễ học Ingress API, nhiều ví dụ cũ; không chọn làm default production mới |
| **Startup, < 20 services** | Traefik hoặc Envoy Gateway | Maintained, setup gọn, phù hợp Gateway API/auto TLS tùy controller |
| **Need auto TLS** | Traefik | Let's Encrypt built-in |
| **AWS EKS, budget** | AWS ALB Controller | Native, no extra pods |
| **Service mesh** | Istio Gateway | Unified traffic management |
| **High perf, TCP** | HAProxy | Best raw performance |
| **Future-proof** | Gateway API compatible | Envoy Gateway, Traefik, Istio Gateway, HAProxy Gateway API |

### Architecture Patterns

**Single Ingress Controller (simple):**
```
Internet → LB → NGINX IC → all services
```
- Pros: đơn giản, ít resource.
- Cons: single point of failure, blast radius lớn.

**Multiple Ingress Controllers (production):**
```
Internet → LB₁ → NGINX IC (public)  → public services
           LB₂ → NGINX IC (internal) → internal APIs
```
- Pros: isolation, different configs per tier.
- Cons: phức tạp hơn, thêm cost.

### Anti-patterns

1. **Không set ingressClassName** → Ingress không được xử lý hoặc multiple controllers conflict.
2. **Wildcard path `/`** → catch-all route có thể swallow traffic không mong muốn.
3. **TLS secret sai namespace** → Ingress Controller không đọc được cert → HTTPS fail.
4. **Quá nhiều annotations** → khó maintain, không portable.
5. **Không set resource limits cho IC pod** → IC bị OOM khi traffic spike.
6. **Bắt đầu platform mới trên retired `kubernetes/ingress-nginx`** → nhận technical debt và security risk ngay từ ngày đầu.

---

## 6. Performance & Scalability ⭐

### Ingress Controller Scaling

- **Horizontal scaling**: chạy nhiều IC replicas + PodAntiAffinity → distribute load.
- **Connection pooling**: IC reuse connections đến backend → giảm overhead.
- **Keep-alive**: enable HTTP keep-alive giữa client-IC và IC-backend.
- **Buffer size**: tune proxy buffer cho large responses.

```yaml
# NGINX IC scaling annotations
metadata:
  annotations:
    nginx.ingress.kubernetes.io/proxy-buffer-size: "8k"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
```

### TLS Performance

- **TLS 1.3** nhanh hơn TLS 1.2 (1-RTT handshake vs 2-RTT).
- **Session resumption**: giảm TLS handshake cho returning clients.
- **ECDSA certificates** nhanh hơn RSA.
- **TLS termination tại IC** → backend nhận plain HTTP → giảm CPU trên backend pods.

### Bottleneck thường gặp

| Bottleneck | Triệu chứng | Fix |
|------------|-------------|-----|
| IC CPU saturated | Latency tăng, 502 errors | Scale IC replicas |
| Too many connections | Connection timeout | Tune worker_connections |
| Large request body | 413 Request Entity Too Large | Set proxy-body-size annotation |
| Slow backend | 504 Gateway Timeout | Tune timeout, fix backend |

---

## 7. Security & Reliability Considerations

### Security

- **Luôn enable TLS** cho production — redirect HTTP → HTTPS.
- **Rate limiting**: bảo vệ backend khỏi abuse.
- **WAF integration**: ModSecurity với NGINX Ingress.
- **IP whitelisting**: `nginx.ingress.kubernetes.io/whitelist-source-range`.
- **CORS headers**: configure đúng cho API.

```yaml
# Security annotations ví dụ
metadata:
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/limit-rps: "10"
    nginx.ingress.kubernetes.io/limit-connections: "5"
```

### Reliability

- **IC replicas ≥ 2** — tránh single point of failure.
- **PodDisruptionBudget** cho IC pods.
- **Health check endpoint** cho LB → IC.
- **Default backend** cho 404/503 pages.
- **Ingress class isolation** — separate IC cho internal vs external traffic.

---

## 8. Hands-on Example

### 8.1 Chuẩn bị: kind cluster với Ingress support

```bash
# Tạo kind cluster với port mapping cho Ingress
cat <<'EOF' | kind create cluster --name ingress-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
EOF
```

### 8.2 Cài NGINX Ingress Controller

```bash
# Install NGINX Ingress Controller cho kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Verify
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
```

### 8.3 Deploy 2 backend services

```yaml
# file: ingress-backends.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: app-v1
  template:
    metadata:
      labels:
        app: app-v1
    spec:
      containers:
        - name: app
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Hello from App V1!", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: app-v1-svc
spec:
  selector:
    app: app-v1
  ports:
    - port: 80
      targetPort: 5678
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-v2
spec:
  replicas: 2
  selector:
    matchLabels:
      app: app-v2
  template:
    metadata:
      labels:
        app: app-v2
    spec:
      containers:
        - name: app
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Hello from App V2!", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: app-v2-svc
spec:
  selector:
    app: app-v2
  ports:
    - port: 80
      targetPort: 5678
```

```bash
kubectl apply -f ingress-backends.yaml
kubectl wait --for=condition=Ready pod -l app=app-v1 --timeout=60s
kubectl wait --for=condition=Ready pod -l app=app-v2 --timeout=60s
```

### 8.4 Path-based routing

```yaml
# file: ingress-path.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-routing
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: app-v1-svc
                port:
                  number: 80
          - path: /v2
            pathType: Prefix
            backend:
              service:
                name: app-v2-svc
                port:
                  number: 80
```

```bash
kubectl apply -f ingress-path.yaml

# Test path-based routing
curl http://localhost/v1
# Expected: Hello from App V1!

curl http://localhost/v2
# Expected: Hello from App V2!

# Verify Ingress
kubectl get ingress
kubectl describe ingress path-routing
```

### 8.5 Host-based routing

```yaml
# file: ingress-host.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-routing
spec:
  ingressClassName: nginx
  rules:
    - host: v1.local.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app-v1-svc
                port:
                  number: 80
    - host: v2.local.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app-v2-svc
                port:
                  number: 80
```

```bash
kubectl apply -f ingress-host.yaml

# Test host-based routing (dùng Host header)
curl -H "Host: v1.local.dev" http://localhost
# Expected: Hello from App V1!

curl -H "Host: v2.local.dev" http://localhost
# Expected: Hello from App V2!
```

### 8.6 TLS với self-signed certificate

```bash
# Tạo self-signed certificate
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=secure.local.dev/O=DevOps Lab" \
  -addext "subjectAltName=DNS:secure.local.dev"

# Tạo Kubernetes Secret
kubectl create secret tls secure-tls --cert=tls.crt --key=tls.key
```

```yaml
# file: ingress-tls.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-routing
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - secure.local.dev
      secretName: secure-tls
  rules:
    - host: secure.local.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app-v1-svc
                port:
                  number: 80
```

```bash
kubectl apply -f ingress-tls.yaml

# Test HTTPS.
# Dùng --resolve để curl gửi đúng SNI secure.local.dev trong TLS handshake.
curl -k --resolve secure.local.dev:443:127.0.0.1 --noproxy secure.local.dev https://secure.local.dev
# Expected: Hello from App V1!

# Verify TLS
curl -kv --resolve secure.local.dev:443:127.0.0.1 --noproxy secure.local.dev https://secure.local.dev 2>&1 | grep "subject:"
# Expected: subject: CN=secure.local.dev; O=DevOps Lab
```

### Cleanup

```bash
kubectl delete -f ingress-path.yaml
kubectl delete -f ingress-host.yaml
kubectl delete -f ingress-tls.yaml
kubectl delete -f ingress-backends.yaml
kubectl delete secret secure-tls
rm -f tls.crt tls.key

# Xóa cluster (nếu muốn)
# kind delete cluster --name ingress-lab
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Ingress không routing traffic

```bash
# Debug flow:
# 1. Ingress Controller running?
kubectl get pods -n ingress-nginx

# 2. Ingress resource xem Events
kubectl describe ingress <name>

# 3. Ingress class đúng?
kubectl get ingressclass
kubectl get ingress <name> -o jsonpath='{.spec.ingressClassName}'

# 4. Backend service/endpoints exist?
kubectl get svc <backend-svc>
kubectl get endpoints <backend-svc>
```

### Pitfall 2: 502 Bad Gateway

**Nguyên nhân**: Ingress Controller không connect được đến backend.

```bash
# Check backend pods ready
kubectl get pods -l app=<backend>

# Check targetPort match
kubectl get svc <backend-svc> -o jsonpath='{.spec.ports[0].targetPort}'

# Check IC logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50
```

### Pitfall 3: TLS certificate error

```bash
# Check secret exists in same namespace as Ingress
kubectl get secret <tls-secret-name>

# Check secret type
kubectl get secret <tls-secret-name> -o jsonpath='{.type}'
# Expected: kubernetes.io/tls

# Check cert content
kubectl get secret <tls-secret-name> -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout
```

### Case Study: Ingress Controller OOM under traffic spike

**Bối cảnh**: E-commerce platform, Black Friday sale. NGINX Ingress Controller với 1 replica, 256Mi memory limit.

**Triệu chứng**: 502 errors tăng vọt, IC pod bị OOMKilled, restart mất 30 giây → downtime.

**Root cause**: Traffic spike 10x, IC buffer cho large responses hết memory.

**Fix**:
1. Scale IC replicas lên 3 với PodAntiAffinity.
2. Tăng memory limit lên 1Gi.
3. Tune `proxy-buffer-size` annotations.
4. Thêm HPA cho IC dựa trên CPU/connections.
5. Thêm PodDisruptionBudget `minAvailable: 2`.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 12: Kubernetes Networking Core)
- Đã hiểu Service types → Ingress dùng ClusterIP service làm backend.
- DNS resolution → Ingress dùng host-based routing matching domain name.
- NodePort/LoadBalancer → Ingress Controller expose qua NodePort hoặc LoadBalancer.

### Bài sau (Day 14: ConfigMap, Secret & External Secret Management)
- TLS certificate lưu trong Secret → Day 14 giải thích Secret management chi tiết.
- Ingress annotations là config → Day 14 bàn về configuration management.
- cert-manager tự động tạo/renew TLS cert → liên quan đến external secret management.

---

## 11. Tài liệu tham khảo

### Must-read
- [Ingress — Official Docs](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Ingress Controllers — Official Docs](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
- [NGINX Ingress Controller Docs](https://kubernetes.github.io/ingress-nginx/)

### Nice-to-have
- [Gateway API — Official Docs](https://gateway-api.sigs.k8s.io/)
- [Traefik Kubernetes Ingress](https://doc.traefik.io/traefik/providers/kubernetes-ingress/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Ingress NGINX retirement statement](https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/)

### Deep-dive
- [NGINX Ingress Annotations Reference](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Gateway API vs Ingress — Blog](https://gateway-api.sigs.k8s.io/concepts/migrating-from-ingress/)
- [Before You Migrate: Ingress-NGINX behaviors](https://kubernetes.io/blog/2026/02/27/ingress-nginx-before-you-migrate/)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- "Kubernetes in Action" — Chapter 5: Ingress resources

