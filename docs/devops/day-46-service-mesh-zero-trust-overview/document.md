# Day 46: Document — Service Mesh & Zero-trust Reference

---

## 1. Service Mesh Comparison Matrix

| Tiêu chí | Istio | Linkerd | Cilium |
|----------|-------|---------|--------|
| **Proxy** | Envoy (C++) | linkerd2-proxy (Rust) | eBPF kernel + Envoy (L7) |
| **Sidecar** | Có | Có | Không (L3/L4), Có (L7) |
| **Memory per proxy** | 50-100MB | 10-20MB | ~0 (kernel programs) |
| **Latency overhead (p99)** | 3-5ms | 1-2ms | 0.1-0.5ms |
| **CPU overhead** | Medium-High | Low | Very Low |
| **mTLS** | ✅ x509 (Citadel) | ✅ x509 (Identity) | ✅ WireGuard / IPsec |
| **mTLS default** | PERMISSIVE | ENABLED | Configurable |
| **Traffic splitting** | ✅ VirtualService (%) | ✅ TrafficSplit SMI | ✅ CiliumEnvoyConfig |
| **Circuit breaker** | ✅ DestinationRule | ❌ (retry budget only) | ✅ Via Envoy |
| **Fault injection** | ✅ VirtualService | ❌ | ✅ Via Envoy |
| **Rate limiting** | ✅ EnvoyFilter | ❌ | ✅ Native |
| **Multi-cluster** | ✅ (complex setup) | ✅ Multi-cluster | ✅ ClusterMesh |
| **Authorization** | ✅ AuthorizationPolicy (L7) | ✅ Server/HTTPRoute (L7) | ✅ CiliumNetworkPolicy (L3-L7) |
| **Observability** | Kiali, Prometheus, Jaeger | Linkerd Viz, Prometheus | Hubble, Prometheus |
| **CNCF status** | Graduated | Graduated | Graduated |
| **License** | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| **Learning curve** | Steep (nhiều CRDs) | Gentle (ít CRDs) | Medium |
| **Install complexity** | `istioctl install` | `linkerd install` | Helm chart (CNI) |
| **Uninstall risk** | Medium (iptables rules) | Low | High (CNI replacement) |
| **Community size** | Rất lớn (Google-backed) | Trung bình (Buoyant) | Lớn (Isovalent/Cisco) |
| **Best for** | Enterprise, advanced features | Simplicity, low overhead | Performance, unified networking |

---

## 2. mTLS Configuration Reference

### Linkerd mTLS

```bash
# Linkerd mTLS on by default khi inject sidecar
# Verify mTLS status
linkerd viz tap deploy/<name> -n <namespace>
# Output: tls=true hoặc tls=false

# Check certificate info
linkerd identity -n <namespace>

# Check trust anchor expiry
linkerd check --proxy

# Rotate trust anchor
# Step 1: Generate new trust anchor
step certificate create root.linkerd.cluster.local ca.crt ca.key \
  --profile root-ca --no-password --insecure

# Step 2: Bundle old + new
cat ca-new.crt ca-old.crt > bundle.crt

# Step 3: Update trust anchor
linkerd upgrade --identity-trust-anchors-file=bundle.crt | kubectl apply -f -

# Step 4: After all proxies rotated, remove old cert from bundle
```

### Istio mTLS

```yaml
# Strict mTLS cho toàn bộ mesh
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT  # STRICT | PERMISSIVE | DISABLE

---
# Strict mTLS cho specific namespace
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT

---
# Per-workload override
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: legacy-service
  namespace: production
spec:
  selector:
    matchLabels:
      app: legacy-service
  mtls:
    mode: PERMISSIVE  # Legacy service chưa support mTLS
```

```bash
# Verify mTLS status (Istio)
istioctl x describe pod <pod-name> -n <namespace>

# Check if traffic is encrypted
istioctl proxy-config secret <pod-name> -n <namespace>

# Verify PeerAuthentication
kubectl get peerauthentication --all-namespaces
```

### Cilium mTLS (WireGuard)

```yaml
# Cilium Helm values để enable encryption
encryption:
  enabled: true
  type: wireguard  # hoặc ipsec
  
  # WireGuard options
  wireguard:
    userspaceFallback: false
```

```bash
# Verify Cilium encryption
cilium status --verbose | grep Encryption

# Check WireGuard interfaces
kubectl exec -n kube-system ds/cilium -- cilium encrypt status
```

---

## 3. Traffic Management Patterns

### Retry Pattern

```
Khi nào retry:
✅ GET requests (idempotent)
✅ Connection refused (server chưa ready)
✅ 503 Service Unavailable (temporary overload)
✅ Reset/disconnect (network blip)

Khi nào KHÔNG retry:
❌ POST/PUT/DELETE (non-idempotent, trừ khi app design idempotent)
❌ 400 Bad Request (client error, retry không giải quyết)
❌ 401/403 (auth error)
❌ 429 Too Many Requests (đã bị rate limit, retry làm tệ hơn)
```

**Istio retry config**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
spec:
  http:
  - route:
    - destination:
        host: my-service
    retries:
      attempts: 3           # Max retry attempts
      perTryTimeout: 2s     # Timeout per attempt
      retryOn: "5xx,reset,connect-failure,retriable-4xx"
```

**Linkerd retry config**:
```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
spec:
  routes:
  - name: "GET /api/products"
    condition:
      method: GET
      pathRegex: "/api/products.*"
    isRetryable: true
  retryBudget:
    retryRatio: 0.2         # Max 20% extra requests
    minRetriesPerSecond: 10
    ttl: 10s
```

### Timeout Pattern

```
Recommended timeouts:
┌─────────────────────┬──────────────┐
│ Service Type        │ Timeout      │
├─────────────────────┼──────────────┤
│ API Gateway → Backend│ 10-30s      │
│ Backend → Database  │ 5-10s        │
│ Backend → Cache     │ 1-3s         │
│ Backend → External  │ 15-30s       │
│ Health check        │ 2-5s         │
│ gRPC unary          │ 5-15s        │
│ gRPC streaming      │ Disable/long │
└─────────────────────┴──────────────┘

Quy tắc: timeout = p99 latency × 3-5
```

**Istio timeout**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
spec:
  http:
  - route:
    - destination:
        host: backend
    timeout: 10s
```

### Circuit Breaker Pattern

```
States:
┌────────┐  failures > threshold  ┌────────┐
│ CLOSED │ ──────────────────────→ │  OPEN  │
│(normal)│                         │(reject)│
└────────┘                         └───┬────┘
     ▲                                 │
     │ success                   timer expires
     │                                 │
┌────┴────┐                        ┌───▼──────┐
│ CLOSED  │ ←───── success ─────── │HALF-OPEN │
└─────────┘                        │(test 1)  │
                                   └──────────┘
```

**Istio circuit breaker (DestinationRule)**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: backend-cb
spec:
  host: backend
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100        # Max TCP connections
      http:
        http1MaxPendingRequests: 50  # Max pending requests
        http2MaxRequests: 100       # Max concurrent requests
        maxRequestsPerConnection: 10 # Requests per connection
        maxRetries: 3              # Max concurrent retries
    outlierDetection:
      consecutive5xxErrors: 5      # Eject after 5 consecutive 5xx
      interval: 10s               # Check interval
      baseEjectionTime: 30s       # Min ejection duration
      maxEjectionPercent: 30      # Max % endpoints ejected
```

### Traffic Splitting (Canary)

**Istio**:
```yaml
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
        subset: stable
      weight: 90
    - destination:
        host: product-service
        subset: canary
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-service
spec:
  host: product-service
  subsets:
  - name: stable
    labels:
      version: v1
  - name: canary
    labels:
      version: v2
```

**Linkerd (SMI TrafficSplit)**:
```yaml
apiVersion: split.smi-spec.io/v1alpha2
kind: TrafficSplit
metadata:
  name: product-service
spec:
  service: product-service
  backends:
  - service: product-service-stable
    weight: 900m   # 90%
  - service: product-service-canary
    weight: 100m   # 10%
```

---

## 4. Zero-trust Networking Checklist

### Foundation Layer

- [ ] **mTLS strict mode**: Tất cả service-to-service traffic encrypted
- [ ] **Service identity**: Mỗi service có unique identity (SPIFFE)
- [ ] **Certificate rotation**: Automatic, TTL < 24h
- [ ] **Trust anchor management**: Root CA secure, rotation plan documented

### Authorization Layer

- [ ] **Default deny**: Mọi traffic bị block trừ khi explicitly allowed
- [ ] **Least privilege**: Mỗi service chỉ gọi được services cần thiết
- [ ] **Method-level control**: GET vs POST vs DELETE authorization riêng
- [ ] **Path-level control**: /api/public vs /api/admin authorization riêng

### Network Layer (defense in depth)

- [ ] **NetworkPolicy**: L3/L4 isolation (backup cho mesh L7)
- [ ] **Namespace isolation**: Services trong namespace khác mặc định không giao tiếp
- [ ] **Egress control**: Kiểm soát traffic ra ngoài cluster
- [ ] **DNS policy**: Chỉ resolve internal DNS + allowlisted external

### Observability Layer

- [ ] **Access logs**: Log tất cả service calls với identity
- [ ] **Authorization deny logs**: Alert cho mọi denied requests
- [ ] **Certificate events**: Monitor cert issuance, rotation, expiry
- [ ] **Anomaly detection**: Unusual traffic patterns (new caller, high volume)

### Operational Layer

- [ ] **Cert expiry monitoring**: Alert 30 ngày trước khi root CA expire
- [ ] **Mesh upgrade plan**: Canary upgrade, rollback procedure
- [ ] **Sidecar health monitoring**: Restart count, resource usage
- [ ] **Incident response**: Playbook cho compromised service identity
- [ ] **Compliance documentation**: mTLS evidence cho SOC 2 / PCI DSS

---

## 5. Debugging Service Mesh Issues

### Quick Debug Commands

#### Linkerd

```bash
# Overall health
linkerd check
linkerd check --proxy

# Per-deployment stats
linkerd viz stat deploy -n <namespace>
linkerd viz stat deploy/<name> -n <namespace> --to deploy/<target>

# Real-time traffic
linkerd viz tap deploy/<name> -n <namespace>
linkerd viz tap deploy/<name> -n <namespace> --to deploy/<target>

# Top routes
linkerd viz routes deploy/<name> -n <namespace>

# Edges (who talks to whom)
linkerd viz edges deploy -n <namespace>

# Proxy diagnostics
linkerd diagnostics proxy-metrics <pod> -n <namespace>

# Proxy logs
kubectl logs <pod> -c linkerd-proxy -n <namespace>
```

#### Istio

```bash
# Overall health
istioctl analyze -n <namespace>

# Proxy status
istioctl proxy-status

# Proxy config dump
istioctl proxy-config all <pod> -n <namespace>
istioctl proxy-config cluster <pod> -n <namespace>
istioctl proxy-config route <pod> -n <namespace>
istioctl proxy-config listener <pod> -n <namespace>
istioctl proxy-config endpoint <pod> -n <namespace>

# Describe pod mesh status
istioctl x describe pod <pod> -n <namespace>

# Proxy logs (Envoy)
kubectl logs <pod> -c istio-proxy -n <namespace>

# Enable debug logging
istioctl proxy-config log <pod> --level debug
```

### Troubleshooting Decision Tree

```
Vấn đề: Service A không gọi được Service B
│
├── 1. Check sidecar injected?
│   ├── kubectl get pod -n <ns> → READY 2/2?
│   │   ├── 1/1 → Sidecar chưa inject
│   │   │   → kubectl annotate ns <ns> linkerd.io/inject=enabled
│   │   │   → Restart deployment
│   │   └── 2/2 → Sidecar OK, tiếp bước 2
│   │
├── 2. Check mTLS?
│   ├── linkerd viz tap → tls=true?
│   │   ├── tls=false → Check PeerAuthentication mode
│   │   │   → Có service nằm ngoài mesh? → PERMISSIVE mode
│   │   └── tls=true → mTLS OK, tiếp bước 3
│   │
├── 3. Check authorization?
│   ├── linkerd viz tap → status=403?
│   │   ├── 403 → Check ServerAuthorization rules
│   │   │   → Service caller có trong allowed list?
│   │   │   → ServiceAccount đúng chưa?
│   │   └── Không 403 → tiếp bước 4
│   │
├── 4. Check service discovery?
│   ├── kubectl exec <pod> -- nslookup <service>
│   │   ├── Fail → DNS issue (Day 12)
│   │   └── OK → tiếp bước 5
│   │
├── 5. Check endpoint health?
│   ├── kubectl get endpoints <service> -n <ns>
│   │   ├── Empty → No ready pods → Check probe
│   │   └── Has IPs → tiếp bước 6
│   │
├── 6. Check circuit breaker?
│   ├── istioctl proxy-config cluster <pod> → outlier detected?
│   │   ├── Ejected → Wait baseEjectionTime hoặc fix upstream
│   │   └── Not ejected → tiếp bước 7
│   │
└── 7. Check proxy resources
    ├── kubectl top pod <pod> -c linkerd-proxy
    │   ├── CPU throttled → Tăng CPU limit
    │   └── Memory high → Check access log config
    └── kubectl describe pod <pod> → OOMKilled?
        ├── Yes → Tăng memory limit
        └── No → Check proxy logs cho specific errors
```

### Common Error Messages

| Error | Mesh | Nguyên nhân | Fix |
|-------|------|-------------|-----|
| `upstream connect error or disconnect/reset before headers` | Istio | mTLS mismatch hoặc upstream không ready | Check PeerAuthentication mode consistency |
| `503 UC` | Istio | Upstream connection failure | Check endpoint health, connection pool |
| `tls=false` | Linkerd | Sidecar chưa inject ở một bên | Inject sidecar cho cả caller và callee |
| `RBAC: access denied` | Istio | AuthorizationPolicy deny | Check policy rules, principal names |
| `connection refused` | Both | Service không listen hoặc port sai | Check service port, container port |
| `no healthy upstream` | Istio | Tất cả endpoints bị eject (circuit breaker) | Giảm maxEjectionPercent, fix root cause |
| `request timeout` | Both | Timeout quá ngắn hoặc upstream chậm | Tăng timeout hoặc optimize upstream |

### Performance Debugging

```bash
# Linkerd: Check proxy latency overhead
linkerd viz stat deploy -n <ns> -t deploy/<target>
# So sánh "LATENCY_P99" vs direct curl latency

# Istio: Envoy stats
kubectl exec <pod> -c istio-proxy -- \
  curl -s localhost:15000/stats | grep -E "upstream_rq|upstream_cx"

# Resource usage per sidecar
kubectl top pod -n <ns> --containers | grep -E "linkerd-proxy|istio-proxy"

# Connection pool stats (Istio)
kubectl exec <pod> -c istio-proxy -- \
  curl -s localhost:15000/clusters | grep -E "cx_active|rq_pending"
```

---

## 6. Service Mesh Decision Framework

```
Cần service mesh không?

Q1: Có bao nhiêu services?
├── < 5 services → KHÔNG cần mesh
├── 5-20 services → XEM XÉT (dựa vào compliance requirements)
└── > 20 services → CÓ THỂ cần mesh

Q2: Có compliance requirements (SOC 2, PCI DSS)?
├── Có, cần mTLS everywhere → Mesh giúp đơn giản hóa
└── Không → Chỉ cần mesh nếu traffic management phức tạp

Q3: Multi-language platform?
├── Có (Go + Java + Python + Node.js) → Mesh tốt (consistent policies)
└── Mono-language → Library-based approach có thể đủ

Q4: Team size và expertise?
├── < 5 DevOps → Linkerd (simple) hoặc không dùng mesh
├── 5-15 DevOps → Linkerd hoặc Cilium
└── > 15 DevOps → Istio acceptable (có team maintain)

Q5: Performance sensitivity?
├── Ultra-low latency (< 1ms p99) → Cilium eBPF hoặc không dùng mesh
├── Low latency (< 5ms p99) → Linkerd
└── Moderate (< 10ms p99) → Istio acceptable

Chọn tool:
┌──────────────┬────────────────────────────┐
│ Nếu          │ Chọn                       │
├──────────────┼────────────────────────────┤
│ Simple + mTLS│ Linkerd                    │
│ Advanced L7  │ Istio                      │
│ Performance  │ Cilium                     │
│ Already CNI  │ Cilium (nếu đã dùng CNI)  │
│ Multi-cluster│ Istio hoặc Cilium          │
│ < 10 services│ Không dùng mesh            │
└──────────────┴────────────────────────────┘
```

---

## 7. Production Checklist

### Pre-deployment

- [ ] Chosen mesh tool matches team expertise and requirements
- [ ] Resource overhead calculated (memory × pod count)
- [ ] Latency impact acceptable for SLOs
- [ ] Exclusion list defined (databases, messaging, monitoring)
- [ ] mTLS mode decided (STRICT vs PERMISSIVE for migration)

### Deployment

- [ ] Control plane HA (≥ 2 replicas)
- [ ] Sidecar resource requests/limits set
- [ ] Certificate TTL configured (< 24h recommended)
- [ ] Trust anchor expiry monitored
- [ ] Proxy access logs configured (or disabled for cost)
- [ ] Mesh metrics scraping by Prometheus

### Post-deployment

- [ ] mTLS verified (`tap` or `proxy-config`)
- [ ] Authorization policies tested (ALLOW + DENY)
- [ ] Timeout/retry policies applied
- [ ] Dashboard created (success rate, latency, traffic)
- [ ] Alert rules for mesh health (proxy restarts, cert expiry)
- [ ] Upgrade runbook documented
- [ ] Rollback procedure tested

