# Day 46: Service Mesh & Zero-trust Overview

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích** được service mesh là gì, vì sao nó tồn tại và giải quyết vấn đề gì trong microservices architecture.
2. **Phân biệt** được Istio, Linkerd và Cilium về kiến trúc, performance overhead, và use case phù hợp.
3. **Triển khai** được Linkerd hoặc Istio basic trên local Kubernetes cluster với mTLS enabled.
4. **Thiết kế** được traffic management policies (retry, timeout, circuit breaker) cho production service.
5. **Đánh giá** được khi nào cần và khi nào KHÔNG nên dùng service mesh trong hệ thống thực tế.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Khi chuyển từ monolith sang microservices, mỗi service cần xử lý:
- **Encryption**: mã hóa traffic giữa các services (mTLS)
- **Retry/timeout**: xử lý transient failures
- **Circuit breaking**: ngắt kết nối khi downstream service lỗi
- **Load balancing**: phân tải thông minh (không chỉ round-robin)
- **Observability**: metrics, traces cho service-to-service calls
- **Access control**: service A có được gọi service B không?

Nếu mỗi service tự implement những logic này → **code duplication, inconsistency, bugs**.

### Hậu quả nếu không có giải pháp

```
Service A (Go) → retry logic v1, timeout 30s
Service B (Java) → retry logic v2, timeout 60s  
Service C (Node.js) → không có retry, không có timeout
Service D (Python) → circuit breaker nhưng config sai
```

Kết quả: **cascading failure** khi một service chậm → retry storm → toàn bộ hệ thống sập.

### Liên hệ với developer

Nếu bạn đã viết middleware/interceptor trong web framework (Express middleware, Spring AOP, Go middleware chain), service mesh là **infrastructure-level middleware** — nó inject vào network layer thay vì application layer.

---

## 3. Kiến thức nền tảng

### Service Mesh là gì?

Service mesh là một **dedicated infrastructure layer** xử lý service-to-service communication. Nó quản lý:
- Traffic routing
- Security (mTLS)
- Observability
- Resilience (retry, timeout, circuit breaker)

**Không phải** application code, mà là **network infrastructure** chạy cùng với application.

### Sidecar Pattern

```
┌─────────────────────────────┐
│           Pod               │
│  ┌──────────┐ ┌──────────┐  │
│  │   App    │ │  Proxy   │  │
│  │Container │ │ (Envoy)  │  │
│  │          │ │          │  │
│  │  :8080 ──┼─┼── :15001 │  │
│  └──────────┘ └──────────┘  │
└─────────────────────────────┘
```

- Mỗi pod có thêm một **sidecar proxy** container (thường là Envoy hoặc linkerd2-proxy)
- App gửi request → proxy intercept → apply policies → forward đến proxy của target pod → target app
- App **không biết** có proxy — transparent proxying qua iptables rules

**Analogy cho developer**: Sidecar proxy giống **reverse proxy** mà bạn đặt trước mỗi service instance. Giống NGINX đứng trước app, nhưng tự động inject và quản lý bởi control plane.

### mTLS (Mutual TLS)

Trong TLS thông thường (HTTPS):
- Client verify server certificate
- Server KHÔNG verify client

Trong mTLS:
- Client verify server certificate ✅
- Server verify client certificate ✅
- **Cả hai bên đều chứng minh danh tính**

```
Service A (client cert) ←── mTLS ──→ Service B (server cert)
         ↕                                    ↕
    "Tôi là Service A"              "Tôi là Service B"
    "Tôi tin Service B"            "Tôi tin Service A"
```

Service mesh **tự động quản lý certificates** — issue, rotate, revoke — không cần app code thay đổi.

### Zero-trust Networking

**Mô hình truyền thống (perimeter-based)**:
```
Internet ──→ [Firewall] ──→ Internal Network (tin tưởng tất cả)
```

**Zero-trust**:
```
Mọi request đều phải:
1. Authenticated (ai đang gọi?)
2. Authorized (có quyền gọi không?)
3. Encrypted (nội dung có bị đọc trộm không?)
```

**"Never trust, always verify"** — ngay cả traffic internal trong cluster cũng phải verify.

**Liên hệ developer**: Zero-trust giống JWT authentication cho mọi API call, nhưng ở tầng infrastructure thay vì application.

---

## 4. Deep Dive

### Kiến trúc Service Mesh

```mermaid
graph TB
    subgraph "Control Plane"
        CP[Control Plane<br/>Policy, Certs, Config]
    end
    
    subgraph "Data Plane"
        subgraph "Pod A"
            A[App A]
            PA[Proxy A]
        end
        subgraph "Pod B"
            B[App B]
            PB[Proxy B]
        end
        subgraph "Pod C"
            C[App C]
            PC[Proxy C]
        end
    end
    
    CP -->|config/certs| PA
    CP -->|config/certs| PB
    CP -->|config/certs| PC
    
    PA <-->|mTLS| PB
    PB <-->|mTLS| PC
    PA <-->|mTLS| PC
    
    A --> PA
    B --> PB
    C --> PC
```

**Data Plane**: Các sidecar proxies xử lý traffic thực tế.
**Control Plane**: Quản lý configuration, certificates, policies và push xuống data plane.

### Istio Architecture

```mermaid
graph TB
    subgraph "Control Plane"
        IS[istiod<br/>Pilot + Citadel + Galley]
    end
    
    subgraph "Data Plane"
        subgraph "Pod 1"
            APP1[App]
            ENV1[Envoy Proxy]
        end
        subgraph "Pod 2"
            APP2[App]
            ENV2[Envoy Proxy]
        end
    end
    
    subgraph "Addons"
        PROM[Prometheus]
        KIALI[Kiali]
        JAEGER[Jaeger]
        GRAF[Grafana]
    end
    
    IS -->|xDS API| ENV1
    IS -->|xDS API| ENV2
    ENV1 <-->|mTLS| ENV2
    ENV1 -->|metrics| PROM
    ENV2 -->|metrics| PROM
    PROM --> GRAF
    IS --> KIALI
```

- **istiod**: merged control plane (Pilot cho traffic, Citadel cho certs, Galley cho config)
- **Envoy proxy**: high-performance C++ proxy, rất feature-rich
- **xDS API**: dynamic configuration protocol (Envoy discovery services)

### Linkerd Architecture

```mermaid
graph TB
    subgraph "Control Plane"
        DEST[Destination<br/>Service Discovery]
        IDEN[Identity<br/>mTLS Certs]
        PROXY_INJ[Proxy Injector<br/>Auto-inject]
    end
    
    subgraph "Data Plane"
        subgraph "Pod 1"
            APP1[App]
            LP1[linkerd2-proxy<br/>Rust]
        end
        subgraph "Pod 2"
            APP2[App]
            LP2[linkerd2-proxy<br/>Rust]
        end
    end
    
    subgraph "Viz Extension"
        PROMV[Prometheus]
        GRAFV[Grafana]
        WEB[Web Dashboard]
    end
    
    DEST -->|config| LP1
    DEST -->|config| LP2
    IDEN -->|certs| LP1
    IDEN -->|certs| LP2
    LP1 <-->|mTLS| LP2
```

- **linkerd2-proxy**: viết bằng Rust, lightweight (~10MB RAM), low latency
- **Simpler architecture**: ít components hơn Istio
- **CNCF graduated project**

### Cilium (eBPF-based)

```mermaid
graph TB
    subgraph "Kernel Space"
        EBPF[eBPF Programs<br/>L3/L4/L7]
    end
    
    subgraph "User Space"
        AGENT[Cilium Agent]
        OP[Cilium Operator]
        HUBBLE[Hubble<br/>Observability]
    end
    
    subgraph "Pods"
        P1[Pod A]
        P2[Pod B]
    end
    
    OP --> AGENT
    AGENT --> EBPF
    P1 -->|traffic| EBPF
    EBPF -->|traffic| P2
    EBPF -->|flow data| HUBBLE
```

- **Không cần sidecar**: eBPF programs chạy trong kernel
- **Lower overhead**: không qua userspace proxy
- **L3/L4 native**: networking + security trong kernel
- **L7 vẫn cần proxy**: Envoy cho HTTP-level policies

### Traffic Management Patterns

#### Retry

```yaml
# Istio VirtualService
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-service
spec:
  hosts:
  - product-service
  http:
  - route:
    - destination:
        host: product-service
    retries:
      attempts: 3
      perTryTimeout: 2s
      retryOn: 5xx,reset,connect-failure,retriable-4xx
```

#### Timeout

```yaml
http:
- route:
  - destination:
      host: product-service
  timeout: 10s
```

#### Circuit Breaker

```yaml
# Istio DestinationRule
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-service
spec:
  host: product-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: DEFAULT
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
```

**Liên hệ developer**: Circuit breaker ở đây hoạt động giống pattern trong code (Netflix Hystrix, resilience4j), nhưng enforce ở network layer — consistent cho tất cả services bất kể ngôn ngữ.

---

## 5. Trade-offs & Best Practices ⭐

### So sánh Istio vs Linkerd vs Cilium

| Tiêu chí | Istio | Linkerd | Cilium |
|-----------|-------|---------|--------|
| **Proxy** | Envoy (C++) | linkerd2-proxy (Rust) | eBPF + Envoy (L7) |
| **Memory per pod** | ~50-100MB | ~10-20MB | ~0 (kernel) |
| **Latency overhead** | ~3-5ms p99 | ~1-2ms p99 | ~0.5ms p99 |
| **Complexity** | Cao | Thấp | Trung bình |
| **Features** | Rất nhiều | Core features | Networking + Security |
| **mTLS** | ✅ Full | ✅ On by default | ✅ WireGuard/IPsec |
| **Traffic splitting** | ✅ Advanced | ✅ Basic | ✅ Via CRDs |
| **Multi-cluster** | ✅ | ✅ | ✅ ClusterMesh |
| **CNCF Status** | Graduated | Graduated | Graduated |
| **Learning curve** | Steep | Gentle | Medium |

### Khi nào dùng gì?

#### Startup (< 20 services)

**Recommendation: Không dùng service mesh hoặc Linkerd**

```
Lý do: 
- < 10 services → NetworkPolicy + application-level retry đủ
- 10-20 services → Linkerd nếu cần mTLS compliance
- Overhead của Istio không justify cho team nhỏ
```

#### Mid-size (20-100 services)

**Recommendation: Linkerd hoặc Cilium**

```
Linkerd nếu:
- Team muốn simple setup
- Cần mTLS nhanh
- Không cần advanced traffic management

Cilium nếu:
- Đã dùng Cilium làm CNI
- Cần networking + security + mesh trong 1 tool
- Performance là critical
```

#### Enterprise (100+ services, multi-cluster)

**Recommendation: Istio hoặc Cilium**

```
Istio nếu:
- Cần advanced traffic management (fault injection, traffic mirroring)
- Có team chuyên vận hành service mesh
- Cần fine-grained authorization policies

Cilium nếu:
- Performance overhead không chấp nhận được
- Cần unified networking + security + observability
```

### Anti-patterns cần tránh

1. **"Service mesh solves everything"**: Service mesh KHÔNG thay thế application-level error handling
2. **Mesh tất cả namespaces**: Chỉ mesh services cần thiết, exclude kube-system, monitoring
3. **Bỏ qua resource overhead**: 100 pods × 50MB sidecar = 5GB RAM chỉ cho proxies
4. **Không test failover**: Sidecar crash → app có bị ảnh hưởng không?
5. **Bypass mesh cho "performance"**: Nếu bypass mTLS giữa services → mất zero-trust

### Best Practices

```
✅ Bắt đầu với strict mTLS (không PERMISSIVE mode trong production)
✅ Đặt timeout cho MỌI service call (default 30s quá dài)
✅ Retry chỉ cho idempotent operations (GET, không retry POST)
✅ Circuit breaker ejection < 50% endpoints
✅ Monitor sidecar resource usage riêng
✅ Canary deploy mesh upgrades (không upgrade toàn bộ cùng lúc)
✅ Exclude long-running connections (WebSocket, gRPC streaming)
```

---

## 6. Performance & Scalability ⭐

### Latency Overhead

```
Không có mesh:     App A ──→ App B
                   Latency: ~0.1ms (same node)

Có sidecar mesh:   App A → Proxy A → Proxy B → App B
                   Latency: +1-5ms per hop

Có eBPF mesh:      App A → [kernel eBPF] → App B
                   Latency: +0.1-0.5ms per hop
```

**Tác động thực tế**: Nếu một request đi qua 5 services:
- Không mesh: ~0.5ms network overhead
- Sidecar mesh: +5-25ms overhead (5 hops × 2 proxies mỗi hop)
- eBPF mesh: +0.5-2.5ms overhead

### Memory Overhead

```
Cluster 200 pods:
- Istio sidecar: 200 × 50MB = 10GB RAM cho proxies
- Linkerd sidecar: 200 × 15MB = 3GB RAM cho proxies
- Cilium eBPF: ~0 extra per pod (agent DaemonSet only)
```

### Bottlenecks thường gặp

1. **Control plane bottleneck**: Quá nhiều config changes → slow propagation
2. **Certificate rotation storm**: Tất cả certs expire cùng lúc → CPU spike
3. **Envoy memory leak**: Known issue với high cardinality headers
4. **Connection pool exhaustion**: Default connection limits quá thấp cho high-throughput

### Scaling Strategy

```yaml
# Istio: Horizontal Pod Autoscaler cho istiod
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: istiod
  namespace: istio-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: istiod
  minReplicas: 2
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Khi nào scale là sai giải pháp

- **Mesh chậm vì config quá phức tạp** → simplify policies trước
- **High latency do proxy** → kiểm tra CPU limits của sidecar (bị throttle)
- **Memory OOM** → kiểm tra cardinality của metrics, access logs

---

## 7. Security & Reliability Considerations

### Security Benefits

1. **mTLS everywhere**: Encrypt tất cả service-to-service traffic
2. **Service identity**: Mỗi service có SPIFFE identity (không phải IP-based)
3. **Authorization policies**: Service A chỉ được gọi GET /api/products, không được POST
4. **Certificate rotation**: Tự động rotate certificates (default 24h Istio)

### Istio Authorization Policy Example

```yaml
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: product-service-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: product-service
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/api-gateway"]
    to:
    - operation:
        methods: ["GET"]
        paths: ["/api/products*"]
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/admin-service"]
    to:
    - operation:
        methods: ["GET", "POST", "PUT", "DELETE"]
        paths: ["/api/products*"]
```

### Reliability Concerns

1. **Sidecar failure = service failure**: Health check proxy, restart policy
2. **Control plane availability**: Chạy ít nhất 2 replicas istiod/linkerd
3. **Mesh upgrade risk**: Canary upgrade, test với staging trước
4. **Fallback without mesh**: App phải hoạt động được nếu sidecar bị remove (graceful degradation)

### Attack Surface

```
Không có mesh:
- Service traffic: plaintext internal
- Authentication: app-level only

Có mesh:
- Service traffic: encrypted (mTLS) ✅
- Authentication: service identity (SPIFFE) ✅
- Nhưng: thêm attack surface cho control plane
- istiod compromise → toàn bộ mesh bị control
```

---

## 8. Hands-on Example

### Setup: Cài Linkerd trên kind cluster

#### Bước 1: Tạo cluster

```bash
# Tạo kind cluster
cat <<EOF | kind create cluster --name mesh-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF

# Verify
kubectl cluster-info --context kind-mesh-lab
```

**Expected output**:
```
Kubernetes control plane is running at https://127.0.0.1:xxxxx
```

#### Bước 2: Cài Linkerd CLI

```bash
# Install Linkerd CLI
curl -fsL https://run.linkerd.io/install | sh

# Add to PATH
export PATH=$HOME/.linkerd2/bin:$PATH

# Verify
linkerd version
```

**Expected output**:
```
Client version: stable-2.14.x
Server version: unavailable
```

#### Bước 3: Pre-check và install Linkerd

```bash
# Pre-check
linkerd check --pre

# Install CRDs
linkerd install --crds | kubectl apply -f -

# Install control plane
linkerd install | kubectl apply -f -

# Wait for ready
linkerd check
```

**Expected output** (cuối cùng):
```
Status check results are √
```

#### Bước 4: Deploy demo application

```bash
# Tạo namespace
kubectl create namespace demo

# Deploy 2 services
cat <<'EOF' | kubectl apply -n demo -f -
---
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
    targetPort: 80
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
        args:
        - "-text=Hello from backend"
        - "-listen=:5678"
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
    targetPort: 5678
EOF

# Verify pods running
kubectl get pods -n demo
```

#### Bước 5: Inject sidecar proxy

```bash
# Inject Linkerd proxy vào demo namespace
kubectl get deploy -n demo -o yaml | linkerd inject - | kubectl apply -f -

# Hoặc annotate namespace để auto-inject
kubectl annotate namespace demo linkerd.io/inject=enabled

# Verify sidecar injected (2/2 containers per pod)
kubectl get pods -n demo
```

**Expected output**:
```
NAME                        READY   STATUS    RESTARTS   AGE
backend-xxx-yyy             2/2     Running   0          30s
backend-xxx-zzz             2/2     Running   0          30s
frontend-xxx-aaa            2/2     Running   0          30s
frontend-xxx-bbb            2/2     Running   0          30s
```

`2/2` = app container + linkerd-proxy sidecar.

#### Bước 6: Verify mTLS

```bash
# Check mTLS status
linkerd viz install | kubectl apply -f -
linkerd viz check

# Xem traffic giữa services
linkerd viz tap deploy/frontend -n demo

# Trong terminal khác, gọi backend từ frontend
kubectl exec -n demo deploy/frontend -c frontend -- \
  curl -s http://backend:5678

# Quan sát output của tap - sẽ thấy tls=true
```

**Expected output** (linkerd viz tap):
```
req id=0:0 proxy=out src=10.244.1.5:xxxxx dst=10.244.2.6:5678 tls=true :method=GET :path=/
rsp id=0:0 proxy=out src=10.244.1.5:xxxxx dst=10.244.2.6:5678 tls=true :status=200 latency=1234µs
```

`tls=true` = mTLS đang hoạt động.

#### Bước 7: Xem dashboard

```bash
# Mở Linkerd dashboard
linkerd viz dashboard &
```

Browser sẽ mở tại `http://localhost:50750` — xem traffic, success rate, latency.

#### Bước 8: Test traffic policies (Linkerd Service Profiles)

```bash
cat <<'EOF' | kubectl apply -n demo -f -
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: backend.demo.svc.cluster.local
  namespace: demo
spec:
  routes:
  - name: "GET /"
    condition:
      method: GET
      pathRegex: "/"
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

#### Cleanup

```bash
# Xóa demo
kubectl delete namespace demo

# Xóa Linkerd
linkerd viz uninstall | kubectl delete -f -
linkerd uninstall | kubectl delete -f -

# Xóa cluster
kind delete cluster --name mesh-lab
```

---

## 9. Common Pitfalls & Debugging

### Lỗi thường gặp

| Lỗi | Triệu chứng | Nguyên nhân | Fix |
|------|-------------|-------------|-----|
| Sidecar not injected | 1/1 READY thay vì 2/2 | Thiếu annotation hoặc namespace label | `kubectl annotate ns <ns> linkerd.io/inject=enabled` |
| mTLS failure | Connection refused giữa services | Certificate expired hoặc identity mismatch | `linkerd check --proxy` |
| High latency | p99 tăng 10-20ms | Sidecar CPU limit quá thấp | Tăng proxy CPU request/limit |
| 503 errors | Intermittent 503 | Circuit breaker triggered hoặc endpoint not ready | Check outlier detection config |
| Memory OOM | Proxy container OOMKilled | Access log buffer, high cardinality | Disable access logs hoặc tăng memory |

### Debug Flow

```
1. kubectl get pods -n <namespace>
   → Check READY column (2/2 = sidecar injected)

2. linkerd viz stat deploy -n <namespace>
   → Check success rate, RPS, latency

3. linkerd viz tap deploy/<name> -n <namespace>
   → Real-time traffic inspection, check tls=true/false

4. kubectl logs <pod> -c linkerd-proxy -n <namespace>
   → Proxy logs for errors

5. linkerd diagnostics proxy-metrics <pod> -n <namespace>
   → Detailed proxy metrics
```

### Production Case Study 1: Retry Storm gây Cascading Failure

#### Context
E-commerce platform, 30 microservices, Istio service mesh. Flash sale event.

#### Symptom
- Product service latency tăng từ 50ms lên 5s
- Order service bắt đầu timeout
- Toàn bộ hệ thống chậm trong 15 phút

#### Investigation
```bash
# Kiểm tra Istio metrics
kubectl exec -n istio-system deploy/prometheus -- \
  promtool query instant 'http://localhost:9090' \
  'sum(rate(istio_requests_total{response_code="503"}[5m])) by (destination_service)'
```

Phát hiện: Product service có 503 rate tăng → Istio retry 3 lần → mỗi request thành 4 requests → **amplification factor 4x** → Product service càng quá tải → vòng lặp.

#### Root Cause
- Retry config mặc định 3 attempts cho mọi request
- Không có circuit breaker
- Product service database connection pool hết

#### Fix
```yaml
# Thêm circuit breaker
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-service
spec:
  host: product-service
  trafficPolicy:
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 30
    connectionPool:
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100

# Giảm retry cho non-idempotent
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-service
spec:
  hosts:
  - product-service
  http:
  - match:
    - method:
        exact: GET
    route:
    - destination:
        host: product-service
    retries:
      attempts: 2
      perTryTimeout: 1s
  - route:
    - destination:
        host: product-service
    retries:
      attempts: 0  # không retry POST/PUT/DELETE
```

#### Lesson Learned
- **Retry × upstream services = amplification** — luôn tính tổng retry budget
- Circuit breaker PHẢI đi kèm retry
- Chỉ retry idempotent operations

### Production Case Study 2: mTLS Certificate Rotation Outage

#### Context
FinTech platform, 50 services, Istio strict mTLS. Cluster đã chạy 11 tháng.

#### Symptom
- 3:00 AM: toàn bộ service-to-service calls fail
- Error: `upstream connect error or disconnect/reset before headers`
- Monitoring alert: 100% error rate trên tất cả services

#### Root Cause
- Istio root CA certificate có TTL 1 năm (default)
- Certificate expired → tất cả mTLS connections fail đồng thời
- **Big bang failure** — không phải gradual

#### Fix ngay lập tức
```bash
# Tạm chuyển sang PERMISSIVE mode
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: PERMISSIVE
EOF

# Rotate root cert
istioctl x precheck
# Follow Istio root cert rotation procedure
```

#### Prevention
```bash
# Monitor cert expiry
kubectl get secret -n istio-system istio-ca-secret -o json | \
  jq -r '.data["ca-cert.pem"]' | base64 -d | \
  openssl x509 -noout -enddate

# Set up alert khi cert còn 30 ngày
```

### Production Case Study 3: Sidecar Injection Breaks Init Container

#### Context
Platform team roll out Linkerd mesh cho namespace mới. Batch processing service dùng init container để chạy database migration.

#### Symptom
- Init container chạy database migration bị timeout
- Error: `connection refused` khi init container cố gọi database service

#### Root Cause
- Linkerd proxy chưa ready khi init container chạy
- Init container chạy TRƯỚC sidecar → không có network connectivity qua mesh
- Database service nằm trong meshed namespace → yêu cầu mTLS → init container không có cert

#### Fix
```yaml
# Cách 1: Skip proxy cho init container traffic
metadata:
  annotations:
    config.linkerd.io/skip-outbound-ports: "5432"

# Cách 2: Dùng native sidecar (K8s 1.28+)
# Linkerd 2.15+ hỗ trợ native sidecar containers
# Init containers chạy AFTER sidecar ready
```

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 45: DevSecOps

- Day 45 đề cập container scanning, SAST, DAST → service mesh bổ sung **runtime security** (mTLS, authorization policies)
- DevSecOps shift-left + service mesh runtime protection = **defense in depth**
- Image signing (Day 37) + RBAC (Day 20) + NetworkPolicy (Day 20) + service mesh mTLS = **zero-trust layers**

### Bài sau — Day 47: Database on Kubernetes vs Managed Database

- Service mesh ảnh hưởng database traffic: mTLS có thể conflict với database protocol
- Database connections thường long-lived → cần exclude khỏi sidecar hoặc config connection pool
- Stateful workloads (databases) cần đặc biệt cẩn thận khi mesh

### Kiến thức tái sử dụng

- **NetworkPolicy** (Day 20): L3/L4 security, bổ sung cho mesh L7 security
- **Observability** (Day 38-42): Service mesh cung cấp metrics/traces tự động
- **Circuit breaker** concept từ system design background
- **Deployment strategies** (Day 35-36): Canary với service mesh traffic splitting

---

## 11. Tài liệu tham khảo

### Must-read
- [Linkerd Getting Started](https://linkerd.io/2/getting-started/) — official quickstart
- [Istio Concepts](https://istio.io/latest/docs/concepts/) — architecture overview
- [The Service Mesh Manifesto](https://buoyant.io/service-mesh-manifesto) — vì sao cần mesh

### Nice-to-have
- [Cilium Service Mesh](https://cilium.io/use-cases/service-mesh/) — eBPF approach
- [SPIFFE/SPIRE](https://spiffe.io/) — service identity framework
- [Envoy Proxy Docs](https://www.envoyproxy.io/docs) — hiểu proxy bên dưới

### Deep-dive
- **Book**: "Istio in Action" (Christian Posta) — Istio chi tiết
- **Book**: "The Enterprise Path to Service Mesh Architectures" (Lee Calcote)
- [CNCF Service Mesh Landscape](https://landscape.cncf.io/guide#orchestration-management--service-mesh) — toàn cảnh ecosystem
- [Istio Performance Benchmarks](https://istio.io/latest/docs/ops/deployment/performance-and-scalability/) — official benchmarks

