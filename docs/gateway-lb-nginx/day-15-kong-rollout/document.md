# Day 15: Deep Dive — Deployment Strategies, Kong Config Rollback & Traffic Splitting

---

## 1. Deployment Strategy Comparison

### 1.1 Strategy Taxonomy

Trong production microservices, có 6 chiến lược deployment chính. Mỗi chiến lược phù hợp với từng risk profile và infrastructure constraint.

#### Recreate Strategy

```
Phase: [v1 RUNNING] → [v1 TERMINATED] → [v2 BUILDING] → [v2 STARTING] → [v2 READY]
          |               ↓                ↓                ↓                ↓
       Traffic     DOWN              DOWN            DOWN            Traffic
       accepted    TIME              TIME            TIME            accepted
```

**Characteristics**:
- Downtime = v1 shutdown + v2 startup + v2 health check
- Không có mixed version trong production
- Đảm bảo schema consistency (v1 và v2 không chạy đồng thời)
- Phù hợp: database schema breaking change, library fundamental change

**Kong implementation**: Không cần weight/canary config. Swap `kong.yml` version hoặc `deck gateway sync` desired-state file.

#### Rolling Strategy

```
Instance 1: [v1] → [v1 dying] → [v2 starting] → [v2 healthy]
Instance 2: [v1] → [v1 healthy] → [v1 healthy] → [v1 dying] → [v2 starting] → ...
Instance 3: [v1] → [v1 healthy] → [v1 healthy] → [v1 healthy] → [v1 healthy] → ...
```

**Characteristics**:
- Zero downtime (nếu có đủ instances)
- Mixed version tồn tại trong cluster → potential schema mismatch
- Pod-level (Kubernetes) hoặc target-level (Kong upstream)

**Kong implementation**: Dùng upstream target weight = drain v1, add v2:
```yaml
upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:8080
        weight: 100  # → 0 → removed
      - target: order-v2:8080
        weight: 0    # → 100
```

#### Canary Strategy

```
Traffic split:  N% → v2, (100-N)% → v1

Progress:
  Day 1-2:  N=1%  (internal tester)
  Day 3:    N=10% (early adopter)
  Day 4-5:  N=50% (staged rollout)
  Day 6-7:  N=100% (full switch)
```

**Characteristics**:
- Risk isolated to N% user
- Data inconsistency risk: v2 write to shared DB, v1 read from same DB
- Requires observability: metric phân biệt v1/v2

**Kong patterns** (xem chi tiết Section 2)

#### Blue-Green Strategy

```
BLUE environment (active):     GREEN environment (standby):
  Kong-BLUE                     Kong-GREEN
  order-v1                       order-v2
  kong.yml: v1                  kong.yml: v2

Switch: Edge LB points to GREEN
Rollback: Edge LB points back to BLUE
```

**Characteristics**:
- Atomic switch (ít nhất là qua Nginx upstream reload)
- 2× resource requirement
- Instant rollback (< 1 phút)
- Phù hợp: critical service, compliance environment

**Kong patterns** (xem Section 3)

#### Shadow / Mirror Strategy

```
Client → Kong → v1 (real response to client)
             └→ mirror → v2 (response discarded)

Traffic to v2 = 100% production traffic (copy)
No user impact (response discarded)
```

**Characteristics**:
- Không ảnh hưởng user
- Dùng để: regression test, load test, performance profiling
- Cost = 2× upstream compute
- Kong: không native shadow, cần external mirror (Envoy, Nginx mirror directive)

#### Dark Launch / Feature Flag

```
/api/v2/orders/estimate
  → v2 only for ios-beta-tester (consumer targeting)
  → v1 response (empty/cached) for everyone else
```

**Characteristics**:
- User-segmented, không phải traffic-percentage split
- Không breaking change (v2 endpoint riêng)
- Rollback = remove route (instant)
- Phù hợp: new feature beta test, A/B testing at gateway layer

---

## 2. Kong Config Rollback — 4 Patterns Deep Dive

### 2.1 Pattern 1: dump-before-sync (Primary — Recommended)

**Workflow**:
```bash
# Pre-deploy: backup current Kong state
BACKUP_FILE="backups/snapshot-$(date +%s).yml"
deck gateway dump \
  --kong-addr "${KONG_ADMIN_URL}" \
  --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}" \
  -o "${BACKUP_FILE}"

# Upload backup artifact
gh api repos/:owner/:repo/actions/artifacts \
  -F name="kong-backup" \
  -F file=@"${BACKUP_FILE}"

# Deploy: diff → sync
deck gateway diff new-kong.yml \
  --kong-addr "${KONG_ADMIN_URL}"

deck gateway sync new-kong.yml \
  --kong-addr "${KONG_ADMIN_URL}" \
  --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}"

# Rollback: sync backup
deck gateway sync "${BACKUP_FILE}" \
  --kong-addr "${KONG_ADMIN_URL}" \
  --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}"
```

**RTO**: 2-5 phút (sync time + verification)
**RPO**: 0 (backup chụp trước khi sync)
**Backup retention**: 30 ngày (artifact retention)

**Script rollback tự động**:
```bash
#!/bin/bash
# rollback.sh — chạy khi Prometheus alert trigger
set -e

BACKUP_FILE="${1:?Usage: $0 <backup-file.yml>}"
KONG_ADDR="${KONG_ADMIN_URL}"
TOKEN="${KONG_ADMIN_TOKEN}"

echo "[$(date)] Starting rollback to: ${BACKUP_FILE}"

# Step 1: Verify backup file exists and is valid
deck file lint "${BACKUP_FILE}"

# Step 2: Diff to see what will change
echo "[$(date)] Computing diff..."
deck gateway diff "${BACKUP_FILE}" \
  --kong-addr "${KONG_ADDR}" \
  --headers "Kong-Admin-Token:${TOKEN}"

# Step 3: Sync (rollback)
echo "[$(date)] Syncing rollback config..."
deck gateway sync "${BACKUP_FILE}" \
  --kong-addr "${KONG_ADDR}" \
  --headers "Kong-Admin-Token:${TOKEN}"

# Step 4: Verify Kong is healthy
echo "[$(date)] Verifying Kong health..."
curl -sf "${KONG_ADDR}/status" | jq '.database'

# Step 5: Smoke test critical routes
for route in /api/v1/orders /api/v1/users; do
  curl -sf "${KONG_PROXY_URL}${route}" > /dev/null \
    && echo "OK: ${route}" \
    || (echo "FAIL: ${route}" && exit 1)
done

echo "[$(date)] Rollback completed successfully"
```

### 2.2 Pattern 2: Git Revert + Auto-Sync

**Workflow**:
```
git revert HEAD
  → git push origin main
    → GitHub Actions trigger
      → deck gateway diff (preview)
      → deck gateway sync (rollback)
```

**Pros**: Full audit trail, peer review, automatic trigger
**Cons**: RTO phụ thuộc vào CI/CD pipeline speed (thêm 3-8 phút so với pattern 1)
**Khi dùng**: Khi rollback cần change history và không cần rollback trong < 5 phút

**GitHub Actions rollback workflow**:
```yaml
# rollback.yml
name: Kong Config Rollback
on:
  workflow_dispatch:
    inputs:
      git_ref:
        description: 'Git SHA or tag to rollback to'
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.inputs.git_ref }}

      - name: Install decK
        run: |
          curl -sL https://github.com/kong/deck/releases/download/v1.40.0/deck_1.40.0_linux_amd64.tar.gz \
            | tar -xz -C /usr/local/bin deck

      - name: Rollback
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_PROD_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_PROD_ADMIN_TOKEN }}
        run: |
          deck gateway sync kong.yml \
            --kong-addr "${KONG_ADMIN_URL}" \
            --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}"
```

### 2.3 Pattern 3: Artifact Snapshot (Immutable Infrastructure)

**Workflow**:
```
CI build → push docker image: kong-config:build-123
                         → push artifact: kong-snapshot-123.yml

Rollback: pull artifact kong-snapshot:build-120
              → deck gateway sync snapshot-120.yml
```

**Khi dùng**: Immutable infrastructure policy, muốn rollback đến đúng build artifact chứ không phải timestamp.

### 2.4 Pattern 4: Blue-Green Kong Cluster

**Architecture**:
```
Edge Nginx LB (upstream switch)
  ├── Kong-BLUE  (port 8000, active)
  └── Kong-GREEN (port 8000, standby)

Kong-BLUE: kong.yml v1  → order-v1
Kong-GREEN: kong.yml v2 → order-v2
```

**Rollback**:
```bash
# Switch LB weight (atomic, < 30s)
# Trong Nginx config:
upstream kong_backend {
  server kong-blue:8000 weight=0;   # Drain BLUE
  server kong-green:8000 weight=100;  # Activate GREEN (was standby)
}

nginx -s reload  # Atomic switch
```

**RTO**: < 1 phút (Nginx reload)
**RPO**: 0 (cả 2 cluster luôn running)
**Cost**: 2× infrastructure
**Khi dùng**: Critical service cần rollback instant, có budget cho 2 cluster

---

## 3. Traffic Splitting Techniques

### 3.1 Upstream Target Weight (Kong — Recommended for Canary)

**Kong upstream config**:
```yaml
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream/api

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:8080
        weight: 90
      - target: order-v2:8080
        weight: 10
```

**Target weight update qua Admin API**:
```bash
# Update weight v2: 10 → 50 bằng cách tạo target entry mới.
# Kong Target immutable: không PATCH weight trực tiếp.
curl -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target=order-v2:8080 \
  -d weight=50

# Verify
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight}'
```

**Ring balancer behavior**:
```
Target weights:
  v1 = 90
  v2 = 10

Effective ratio:
  v1 ≈ 90%
  v2 ≈ 10%

Kong rebuilds the in-memory ring when active target set changes.
Round-robin walks the weighted ring; consistent-hashing maps request hash to ring slots.
```

### 3.2 Route Header/Query Routing

**Header-based route targeting**:
```yaml
services:
  - name: order-service-v1
    url: http://order-v1:8080
    routes:
      - name: order-route-v1
        paths: ["/api/v1/orders"]
        strip_path: false

  - name: order-service-v2
    url: http://order-v2:8080
    routes:
      - name: order-route-v2
        paths: ["/api/v1/orders"]
        strip_path: false
        headers:
          x-canary: ["true"]
```

**Query parameter routing** (alternative):
```yaml
routes:
  - name: order-route-v2
    paths: ["/api/v1/orders"]
    strip_path: false
    headers:
      x-feature-flag-estimate: ["true"]
```

**JWT claim routing**:
```yaml
routes:
  - name: order-route-beta
    paths: ["/api/v2/orders/estimate"]
    strip_path: false
    headers:
      x-consumer-tag: ["beta-tester"]
```

### 3.3 Request Transformer + Header Injection

Dùng request-transformer plugin để inject header khi canary rule match, redirect traffic đến v2 upstream:

```yaml
plugins:
  - name: request-transformer
    route: order-route-v1
    config:
      add:
        headers: ["X-Canary-Route:v2"]
    # Chỉ add header khi certain condition match
    # Kết hợp với conditional plugin (Kong Enterprise)
```

**Kong OSS alternative** (không có conditional transformer):
Dùng multiple route + header matching để achieve tương tự.

### 3.4 Nginx Mirror Directive (Shadow Traffic)

Kong base trên Nginx, có thể dùng Nginx `mirror` directive ở CP layer:

```nginx
# Không khả thi trong Kong OSS config
# Kong dùng Lua plugin, không phải raw nginx.conf

# Shadow implementation: tạo 2 service
# Service A (primary): trả response thật cho client
# Service B (shadow): gửi request đến v2, response discard
```

**Thực tế**: Shadow traffic với Kong OSS cần external component (nginx mirror upstream, Argo Rollouts).

---

## 4. Progressive Delivery: Argo Rollouts & Flagger Overview

### 4.1 Argo Rollouts

Argo Rollouts là Kubernetes controller mở rộng Deployment với advanced rollout strategy.

**Canary strategy**:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-service
spec:
  strategy:
    canary:
      steps:
        - setWeight: 1     # 1%
        - pause: {duration: 1h}
        - setWeight: 10    # 10%
        - pause: {duration: 24h}
        - setWeight: 50   # 50%
        - pause: {duration: 24h}
        - setWeight: 100   # 100%
      analysis:
        templates:
          - templateName: success-rate
        startingStep: 1
        args:
          - name: service-name
            value: order-service
```

**Integration với Kong**: Argo Rollouts quản lý Kubernetes-level traffic (pod), Kong quản lý Gateway-level traffic (route/service). Kết hợp:
- Argo Rollouts: canary pod %, Kubernetes service selector
- Kong: route-level policy (auth, rate-limit) vẫn áp dụng cho cả v1 và v2

### 4.2 Flagger (Progressive Delivery for Flux)

Flagger là progressive delivery operator cho Flux, hỗ trợ:
- Canary analysis: Prometheus metric queries
- Automated rollback: khi SLO breach
- A/B testing: header/cookie matching

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: order-service
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99
        interval: 1m
      - name: request-duration
        thresholdRange:
          max: 500
        interval: 1m
```

### 4.3 So Sánh Argo Rollouts vs Kong Native

| Aspect | Argo Rollouts | Kong Native (upstream weight) |
|---|---|---|
| Layer | Kubernetes pod level | Gateway route/upstream level |
| Traffic split | K8s Service selector | Kong upstream target weight |
| Auth/policy | Không quản lý | Có (plugin applies to both v1/v2) |
| Metric analysis | Built-in Prometheus | External (Prometheus + alert) |
| Auto-rollback | Có (native) | Cần external trigger |
| Setup complexity | Cao (Kubernetes, Prometheus) | Thấp (Kong + decK) |
| Production recommendation | K8s-native stack | Kong OSS + external CI/CD |

**Kết luận**: Với pure Kong OSS (không Kubernetes), dùng Kong native upstream weight + decK GitOps + Prometheus alert. Khi có Kubernetes, Argo Rollouts + Kong Ingress Controller là sự kết hợp mạnh nhất.

---

## 5. Comparison: Kong vs Istio VirtualService vs Envoy weighted_clusters

### 5.1 Kong Upstream Target Weight

```yaml
# Kong: Upstream chứa multiple targets với weight
upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:8080
        weight: 90
      - target: order-v2:8080
        weight: 10
```

**Đặc điểm**:
- Ring balancer với weighted target selection
- Không support header/cookie-based routing trong upstream weight
- Passive health check tự động (unhealthy target = 0 weight effective)
- Cần external Prometheus để analyze traffic split

### 5.2 Istio VirtualService

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-service
spec:
  hosts: ["order-service"]
  http:
    - route:
        - destination:
            host: order-service
            subset: v1
          weight: 90
        - destination:
            host: order-service
            subset: v2
          weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: order-service
spec:
  host: order-service
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
```

**Đặc điểm**:
- Header-based routing có thể trong VirtualService `match` rule
- Envoy-sidecar tự động distribute config
- Built-in retries, timeout, circuit breaker ở mesh level
- Metrics: Istio telemetry với Prometheus (tự động label version)

**Khác biệt chính với Kong**:
- Istio: service mesh (L4 + L7 proxy), Kong: API Gateway (L7 focus)
- Kong: better plugin ecosystem (auth, rate-limit, transform)
- Istio: better traffic management (header routing, mirror, fault injection)

### 5.3 Envoy weighted_clusters

```yaml
clusters:
  - name: order_service
    type: STRICT_DNS
    lb_policy: WEIGHTED_ROUND_ROBIN
    targets:
      - endpoint:
          address:
            socket_address:
              address: order-v1
              port_value: 8080
        weight: 90
      - endpoint:
          address:
            socket_address:
              address: order-v2
              port_value: 8080
        weight: 10
```

**Envoy weighted_clusters** là concept tương đương để traffic split theo weight. Kong không chạy trên Envoy; Kong dùng Nginx + OpenResty + Lua và ring balancer riêng.

### 5.4 Comparison Summary

| Feature | Kong Upstream Weight | Istio VirtualService | Envoy weighted_clusters |
|---|---|---|---|
| Traffic split method | Target weight | Destination subset weight | Cluster endpoint weight |
| Header-based routing | Route + headers | `match` rules | `route` + header match |
| Canary analysis | External (Prometheus) | Istio Telemetry + Prometheus | External (Prometheus) |
| Auto-rollback | External (CI/CD alert) | Flagger / Argo Rollouts | Argo Rollouts |
| Auth at gateway | Plugin (native) | EnvoyFilter / AuthorizationPolicy | Custom |
| Rate limiting | Plugin (native) | Envoy rate limit service | Envoy rate limit service |
| Service mesh | Không | Có (sidecar) | Có (sidecar hoặc front-proxy) |
| Complexity | Thấp | Cao | Cao |
| Best for | API Gateway, single cluster | Service mesh, multi-namespace | Custom proxy, edge |

---

## 6. Kong Blue-Green — Full Architecture Reference

### 6.1 Blue-Green với Single Kong Cluster + Service Host Switch

```
Kong DB-less (single cluster)
  kong.yml (blue): Service.host = http://order-v1:8080
  kong.yml (green): Service.host = http://order-v2:8080

Switch method:
  sed -i 's/order-v1:8080/order-v2:8080/' kong.yml
  deck gateway diff kong.yml
  deck gateway sync kong.yml
  # RTO: 2-5 phút
```

**Script switch**:
```bash
#!/bin/bash
# switch-blue-green.sh
ENV="${1:?Usage: $0 <blue|green>}"
KONG_YML="kong.yml"
KONG_ADDR="http://localhost:8001"

case "$ENV" in
  blue)
    sed -i 's|order-v2:8080|order-v1:8080|g' "${KONG_YML}"
    ;;
  green)
    sed -i 's|order-v1:8080|order-v2:8080|g' "${KONG_YML}"
    ;;
  *)
    echo "Unknown environment: $ENV"
    exit 1
    ;;
esac

deck gateway diff "${KONG_YML}" --kong-addr "${KONG_ADDR}"
deck gateway sync "${KONG_YML}" --kong-addr "${KONG_ADDR}"
```

### 6.2 Blue-Green với 2 Kong Clusters + Nginx Edge

```
                    Internet
                       │
              Cloud LB / Nginx
              (upstream switch)
                /          \
          Kong-BLUE     Kong-GREEN
          (port 8000)   (port 8000)
               |              |
          order-v1       order-v2
          (kong.yml)     (kong.yml)
```

**Nginx edge config**:
```nginx
upstream kong_backends {
    server kong-blue:8000 weight=100;  # ACTIVE
    server kong-green:8000 weight=0;   # STANDBY
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://kong_backends;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }
}
```

**Switch command** (< 30s):
```bash
# Atomic switch: edit nginx.conf upstream section
# OLD:
#   server kong-blue:8000 weight=100;
#   server kong-green:8000 weight=0;

# NEW:
#   server kong-blue:8000 weight=0;
#   server kong-green:8000 weight=100;

nginx -s reload  # Atomic switch, no downtime
```

**Draining old connections** (optional):
```nginx
# Nếu cần graceful drain (không interrupt in-flight request)
# Dùng drain period
upstream kong_backends {
    server kong-blue:8000 weight=0 max_fails=0 fail_timeout=0s;
    server kong-green:8000 weight=100;
    keepalive 32;
}
```

---

## 7. Production Rollout Checklist

### 7.1 Pre-Rollout Checklist

- [ ] Kong state dumped và upload artifact
- [ ] Prometheus metric với label `version` đang collect
- [ ] Alert rule: `error_rate_v2 > 0.5% in 5min → trigger rollback`
- [ ] SLO criteria: p99_v2 < p99_v1 × 1.5, throughput_v2 ≥ throughput_v1 × 0.95
- [ ] DB migration: expand-contract completed, v1 code tương thích với current schema
- [ ] Team notified: rollback plan đã rehearsed
- [ ] Rollback script tested in staging

### 7.2 During Rollout Checklist

- [ ] Monitor: error_rate_v1 vs error_rate_v2 mỗi 5 phút
- [ ] Monitor: p50/p95/p99 latency mỗi version
- [ ] Monitor: request count distribution (v1 vs v2)
- [ ] Log: Kong access log có label version (X-Service-Version header)
- [ ] Health check: order-v2 target status trong Kong Admin API

### 7.3 Post-Rollout Checklist

- [ ] v1 target removed from upstream (weight = 0 → delete)
- [ ] Kong config committed to Git với tag `deploy-v2-complete`
- [ ] Old backup artifacts cleaned up (retention policy)
- [ ] DB old columns removed (sau khi v1 decommissioned hoàn toàn)
- [ ] v1 infrastructure decommissioned (nếu dùng blue-green)

---

## 8. References

- **Google SRE Book**: Release Engineering — Canary Releases
- **Martin Fowler**: BlueGreenDeployment — https://martinfowler.com/bliki/BlueGreenDeployment.html
- **Charity Majors**: Canary in a coal mine — operational mindset for gradual rollout
- **Argo Rollouts Documentation**: https://argoproj.github.io/argo-rollouts/
- **Flagger Documentation**: https://flagger.dev/
- **Istio VirtualService**: https://istio.io/latest/docs/concepts/traffic-management/
- **Envoy weighted_clusters**: https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/cluster/v3/cluster.proto
- **Kong Upstream Load Balancing**: https://docs.konghq.com/gateway/latest/reference/configuration/
- **decK Rollback Guide**: https://docs.konghq.com/deck/latest/guides/rollback/
- **Netflix Tech Blog**: Canary Analysis — metric-driven progressive delivery
- **Terraform Deployment Strategies**: blue-green vs canary vs rolling
