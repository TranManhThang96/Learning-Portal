# Day 15: Exercises — Canary, Blue-Green & Gateway Config Rollback

> **Yêu cầu**: Docker, Docker Compose, curl, jq, decK 1.40+
> **Kong version**: 3.7
> **Thời gian ước tính**: 90-120 phút
> **Note**: Lab setup từ Exercise 1 được dùng chung cho Exercise 2-5. Chỉ setup 1 lần.

---

## Exercise 0: Setup — Docker Compose Base (dùng chung)

**Mục tiêu**: Khởi tạo Kong DB-less + 2 backend (order-v1 và order-v2) — base cho tất cả lab tiếp theo.

### Bước 1: Tạo directory và mock config

```bash
mkdir -p ~/kong-rollout/mocks && cd ~/kong-rollout

# v1 mock — trả về JSON với version field
cat > mocks/v1-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/api/v1/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"version\":\"v1\",\"status\":\"ok\",\"order_count\":0}",
    "headers": {
      "X-Service-Version": ["v1"],
      "X-Backend": ["order-v1"]
    }
  }
}
EOF

# v2 mock — trả về JSON với version field + estimate field (breaking)
cat > mocks/v2-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/api/v1/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"version\":\"v2\",\"status\":\"ok\",\"order_count\":0,\"estimate_available\":true}",
    "headers": {
      "X-Service-Version": ["v2"],
      "X-Backend": ["order-v2"]
    }
  }
}
EOF

# v2 beta mock — cho dark launch feature flag
cat > mocks/v2beta-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/api/v2/orders/estimate" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"feature\":\"estimate\",\"status\":\"beta\",\"price_range\":\"$\"}",
    "headers": {
      "X-Service-Version": ["v2-beta"],
      "X-Backend": ["order-v2"]
    }
  }
}
EOF
```

### Bước 2: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  kong:
    image: kong:3.7
    container_name: kong-rollout
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_LOG_LEVEL: info
      KONG_PLUGINS: prometheus,rate-limiting
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml:ro
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8100:8100"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5

  order-v1:
    image: mockserver/mockserver:5.15.0
    container_name: order-v1
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/v1-expectation.json
    volumes:
      - ./mocks/v1-expectation.json:/config/v1-expectation.json:ro
    ports:
      - "8081:1080"

  order-v2:
    image: mockserver/mockserver:5.15.0
    container_name: order-v2
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/v2-expectation.json
    volumes:
      - ./mocks/v2-expectation.json:/config/v2-expectation.json:ro
    ports:
      - "8082:1080"

  order-v2-beta:
    image: mockserver/mockserver:5.15.0
    container_name: order-v2-beta
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/v2beta-expectation.json
    volumes:
      - ./mocks/v2beta-expectation.json:/config/v2beta-expectation.json:ro
    ports:
      - "8083:1080"
EOF
```

### Bước 3: Initial kong.yml (v1 only, baseline)

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF
```

### Bước 4: Start và verify

```bash
docker compose up -d
sleep 10

# Verify Kong is running
curl -sf http://localhost:8001/ | jq '{version: .version, database: .configuration.database}'

# Verify backends
curl -s http://localhost:8081/orders | jq '.version'   # "v1"
curl -s http://localhost:8082/orders | jq '.version'   # "v2"

# Verify Kong routing to v1
curl -s http://localhost:8000/api/v1/orders \
  -H "Accept: application/json" | jq '.version'  # "v1"

echo "Setup OK — v1 is active, v2 is standby"
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Kong 502 | Backend container chưa ready | `sleep 10` hoặc `docker compose ps` |
| `declarative config failed` | kong.yml syntax lỗi | `deck file lint kong.yml` |
| Mock trả về 404 | MockServer path không match | Check path trong JSON: `"path": "/api/v1/orders"` |

---

## Exercise 1: Canary qua Upstream Weight (1% → 10% → 50% → 100%)

**Mục tiêu**: Implement canary deployment bằng Kong upstream target weight. Sau mỗi bước, verify traffic split thực tế.

### Bước 1: Add v2 target với weight=1 (1% canary)

```bash
# Add v2 target vào upstream (weight = 1, tổng = 101)
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v2:1080" \
  -d weight=1 | jq '{target, weight, upstream}'

# Verify both targets
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight}'
```

**Expected output**:
```
{"target":"order-v1:1080","weight":100}
{"target":"order-v2:1080","weight":1}
```

### Bước 2: Đo traffic split thực tế (100 requests)

```bash
# Gửi 100 requests, đếm v1 vs v2
echo "=== Traffic split test (100 requests) ==="
for i in $(seq 1 100); do
  curl -s http://localhost:8000/api/v1/orders | jq -r '.version'
done | sort | uniq -c

echo "Expected: ~99 v1, ~1 v2 (với weight 100/1)"
```

**Expected**: ~99 requests đến v1, ~1 request đến v2. Với traffic thấp (100 req total), kết quả có thể lệch.

### Bước 3: Tăng weight lên 10/90 (10% canary)

```bash
# Update v2 weight: 1 → 10 bằng cách tạo target entry mới (target immutable)
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v2:1080" \
  -d weight=10 | jq '{target, weight}'

# Verify
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight}'

# Đo traffic split (1000 requests cho accuracy hơn)
echo "=== Traffic split (1000 requests) ==="
for i in $(seq 1 1000); do
  curl -s http://localhost:8000/api/v1/orders | jq -r '.version'
done | sort | uniq -c

echo "Expected: ~909 v1, ~91 v2 (với weight 100/10 ≈ 90.9%/9.1%)"
```

### Bước 4: Tăng weight lên 50/50 (50% canary)

```bash
# Update v2 weight: 10 → 100 để đạt 50/50 vì v1 đang weight=100
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v2:1080" \
  -d weight=100

echo "=== Traffic split (500 requests, 50/50) ==="
for i in $(seq 1 500); do
  curl -s http://localhost:8000/api/v1/orders | jq -r '.version'
done | sort | uniq -c

echo "Expected: ~250 v1, ~250 v2"
```

### Bước 5: Full switch — v2 weight=100, v1 weight=0

```bash
# Drain v1 (weight = 0)
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v1:1080" \
  -d weight=0

# Verify: chỉ còn v2 active
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight, healthy}'

# Test: tất cả request → v2
echo "=== After full switch (all traffic to v2) ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8000/api/v1/orders | jq -r '.version'
done | sort | uniq -c

echo "Expected: 20 v2"
```

### Bước 6: Revert về baseline (v1 only)

```bash
# Restore: v1=100, v2=0
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v1:1080" \
  -d weight=100
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d target="order-v2:1080" \
  -d weight=0

# Verify baseline
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight}'
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| v2 nhận 0 traffic dù weight > 0 | Target unhealthy (Kong passive health check) | Check target status, restart v2 container |
| Traffic split lệch nhiều | Traffic volume quá thấp | Tăng số requests test lên 1000+ |
| `weight update` không apply | Kong reload chưa hoàn tất | Wait 5s, check lại Admin API |

---

## Exercise 2: Canary qua Route-level Header Routing

**Mục tiêu**: Implement canary bằng 2 route với header matching. Canary traffic đi route có header `x-canary: true`.

### Bước 1: Cập nhật kong.yml với 2 route

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  # Route default (không có header canary) → v1
  - name: order-service-v1
    url: http://order-v1:1080
    routes:
      - name: order-route-v1
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true

  # Route canary (header x-canary: true) → v2
  - name: order-service-v2
    url: http://order-v2:1080
    routes:
      - name: order-route-v2
        paths:
          - /api/v1/orders
        strip_path: false
        headers:
          x-canary: ["true"]

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

# Sync
deck gateway sync kong.yml --kong-addr http://localhost:8001
```

### Bước 2: Test traffic mà không có header (default → v1)

```bash
echo "=== Default request (no canary header) ==="
curl -s http://localhost:8000/api/v1/orders | jq '{version}'

echo "Expected: version=v1"
```

### Bước 3: Test traffic với header canary (→ v2)

```bash
echo "=== Canary request (x-canary: true) ==="
curl -s http://localhost:8000/api/v1/orders \
  -H "x-canary: true" | jq '{version}'

echo "Expected: version=v2"
```

### Bước 4: Test với header sai (vẫn → v1)

```bash
echo "=== Non-canary header (x-canary: false) ==="
curl -s http://localhost:8000/api/v1/orders \
  -H "x-canary: false" | jq '{version}'

echo "Expected: version=v1"
```

### Bước 5: Test header không nằm trong canary

```bash
echo "=== Unknown canary header value (falls back to default route) ==="
curl -s \
  http://localhost:8000/api/v1/orders \
  -H "x-canary: maybe" | jq '{version}'

echo "Expected: version=v1"
```

### Bước 6: Khôi phục baseline

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

deck gateway sync kong.yml --kong-addr http://localhost:8001
```

**So sánh Exercise 1 vs Exercise 2**:

| Aspect | Upstream Weight (Ex1) | Route Header (Ex2) |
|---|---|---|
| Traffic split | Probabilistic (% approximate) | Deterministic (by header) |
| Client modification | Không | Có (inject header) |
| Testing v2 không cần header | Không | Có (internal QA) |
| Production user-facing | OK (Ex1) | Không (Ex2) |
| Rollback | Weight=0 v2 | Remove v2 route |

---

## Exercise 3: Blue-Green qua decK sync Service.host Switch

**Mục tiêu**: Switch toàn bộ traffic từ v1 sang v2 bằng cách thay đổi Service.host trong kong.yml.

### Bước 1: Baseline — traffic đến v1

```bash
echo "=== Current backend (should be v1) ==="
curl -s http://localhost:8000/api/v1/orders | jq '.version'
# Expected: v1
```

### Bước 2: Switch sang v2 (blue-green switch)

```bash
# Backup trước khi switch
BACKUP_FILE="backup-blue-$(date +%F-%H%M).yml"
deck gateway dump -o "${BACKUP_FILE}" --kong-addr http://localhost:8001
echo "Backup saved: ${BACKUP_FILE}"

# Tạo green config (switch sang v2)
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-v2:1080  # ← CHANGED: v1 → v2
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

# Diff để xem thay đổi
deck gateway diff kong.yml --kong-addr http://localhost:8001

# Apply switch
deck gateway sync kong.yml --kong-addr http://localhost:8001

# Verify
echo "=== After blue-green switch ==="
curl -s http://localhost:8000/api/v1/orders | jq '.version'
# Expected: v2
```

### Bước 3: Rollback về v1 (blue-green switch back)

```bash
echo "=== Rolling back to v1 ==="
deck gateway sync "${BACKUP_FILE}" --kong-addr http://localhost:8001

# Verify rollback
curl -s http://localhost:8000/api/v1/orders | jq '.version'
# Expected: v1
```

**RTT đo được**:
```bash
time deck gateway sync kong.yml --kong-addr http://localhost:8001
# real  0m3.2s  (với ~5 entities)
```

**Lỗi thường gặp**:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Switch OK nhưng vẫn ra v1 | Kong reload chưa done | Wait 5s |
| Rollback lại thành v2 | Backup file chụp sau khi switch | Backup trước switch |
| decK sync partial fail | Entity ordering | Sync theo đúng order: upstream → service → route |

---

## Exercise 4: Blue-Green Cluster với Nginx Edge Switch

**Mục tiêu**: Mô phỏng 2 Kong cluster (blue + green) với Nginx làm edge LB switch.

### Bước 1: Start Kong-BLUE (v1 active)

```bash
mkdir -p ~/kong-rollout/blue ~/kong-rollout/green

# Kong-BLUE config: v1
cat > ~/kong-rollout/blue/kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://host.docker.internal:8081
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
EOF

# Start Kong-BLUE
docker run -d \
  --name kong-blue \
  --add-host=host.docker.internal:host-gateway \
  -e KONG_DATABASE=off \
  -e KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yml \
  -e KONG_ADMIN_LISTEN="0.0.0.0:8001" \
  -e KONG_PROXY_LISTEN="0.0.0.0:8000" \
  -v ~/kong-rollout/blue/kong.yml:/kong/declarative/kong.yml:ro \
  -p 8002:8000 \
  -p 8003:8001 \
  kong:3.7

sleep 8

# Verify BLUE
curl -sf http://localhost:8003/ | jq '.version'
curl -s http://localhost:8002/api/v1/orders | jq '.version'
# Expected: v1
```

### Bước 2: Start Kong-GREEN (v2 standby)

```bash
# Kong-GREEN config: v2
cat > ~/kong-rollout/green/kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://host.docker.internal:8082
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
EOF

# Start Kong-GREEN
docker run -d \
  --name kong-green \
  --add-host=host.docker.internal:host-gateway \
  -e KONG_DATABASE=off \
  -e KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yml \
  -e KONG_ADMIN_LISTEN="0.0.0.0:8001" \
  -e KONG_PROXY_LISTEN="0.0.0.0:8000" \
  -v ~/kong-rollout/green/kong.yml:/kong/declarative/kong.yml:ro \
  -p 8004:8000 \
  -p 8005:8001 \
  kong:3.7

sleep 8

# Verify GREEN
curl -sf http://localhost:8005/ | jq '.version'
curl -s http://localhost:8004/api/v1/orders | jq '.version'
# Expected: v2
```

### Bước 3: Nginx edge switch

```bash
# Tạo Nginx config với upstream weight switch
cat > ~/kong-rollout/nginx-edge.conf << 'EOF'
upstream kong_backend {
    server host.docker.internal:8002 weight=100;  # BLUE active
    server host.docker.internal:8004 weight=0;    # GREEN standby
    keepalive 32;
}

server {
    listen 9000;
    server_name localhost;

    location / {
        proxy_pass http://kong_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }
}
EOF
cp ~/kong-rollout/nginx-edge.conf ~/kong-rollout/nginx-edge-blue.conf

# Start Nginx edge
docker run -d \
  --name nginx-edge \
  --add-host=host.docker.internal:host-gateway \
  -v ~/kong-rollout/nginx-edge.conf:/etc/nginx/conf.d/default.conf \
  -p 9000:80 \
  nginx:alpine

sleep 3

# Test via Nginx edge — traffic → BLUE (v1)
echo "=== Traffic via Nginx edge (BLUE active) ==="
curl -s http://localhost:9000/api/v1/orders | jq '.version'
# Expected: v1
```

### Bước 4: Blue-green switch (BLUE → GREEN)

```bash
# Switch: GREEN weight=100, BLUE weight=0
cat > ~/kong-rollout/nginx-edge-switched.conf << 'EOF'
upstream kong_backend {
    server host.docker.internal:8002 weight=0;    # BLUE drained
    server host.docker.internal:8004 weight=100;  # GREEN active
    keepalive 32;
}

server {
    listen 9000;
    server_name localhost;

    location / {
        proxy_pass http://kong_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }
}
EOF

# Reload Nginx (atomic switch)
cp ~/kong-rollout/nginx-edge-switched.conf ~/kong-rollout/nginx-edge.conf
docker exec nginx-edge \
  nginx -s reload

sleep 2

# Verify: traffic → GREEN (v2)
echo "=== Traffic via Nginx edge (GREEN active) ==="
curl -s http://localhost:9000/api/v1/orders | jq '.version'
# Expected: v2

echo "=== Switch time measurement ==="
time (docker exec nginx-edge nginx -s reload && sleep 1)
```

### Bước 5: Rollback (GREEN → BLUE)

```bash
# Rollback: BLUE weight=100, GREEN weight=0
cp ~/kong-rollout/nginx-edge-blue.conf ~/kong-rollout/nginx-edge.conf
docker exec nginx-edge nginx -s reload
sleep 1

echo "=== Traffic after rollback ==="
curl -s http://localhost:9000/api/v1/orders | jq '.version'
# Expected: v1
```

### Bước 6: Cleanup

```bash
docker stop kong-blue kong-green nginx-edge
docker rm kong-blue kong-green nginx-edge
```

---

## Exercise 5: Config Rollback Drill (dump → sync broken → rollback < 5 min)

**Mục tiêu**: Thực hành full rollback workflow — backup → apply broken config → rollback trong < 5 phút.

### Bước 1: Backup baseline state

```bash
cd ~/kong-rollout

# Restore baseline
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true
      - name: rate-limiting
        config:
          minute: 1000
          policy: local

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

deck gateway sync kong.yml --kong-addr http://localhost:8001

# Backup baseline
BACKUP_FILE="backups/baseline-$(date +%F-%H%M).yml"
mkdir -p backups
deck gateway dump -o "${BACKUP_FILE}" --kong-addr http://localhost:8001
echo "Baseline backup: ${BACKUP_FILE}"

# Verify
curl -s http://localhost:8000/api/v1/orders | jq '.version'
```

### Bước 2: Apply broken config (rate-limit = 1 req/min — production outage)

```bash
# "Broken" config: rate-limit = 1 req/min (giống Day 10 scenario)
cat > kong-broken.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
      - name: rate-limiting
        config:
          minute: 1    # ← BROKEN: 1 req/min thay vì 1000
          policy: local

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

deck gateway sync kong-broken.yml --kong-addr http://localhost:8001

# Verify: request thứ 2 sẽ bị 429
echo "=== First request (should be OK) ==="
curl -s -o /tmp/order-response.json -w "HTTP Status: %{http_code}\n" http://localhost:8000/api/v1/orders
jq '{version}' /tmp/order-response.json

echo "=== Second request (should be 429 - rate limited) ==="
sleep 2
curl -s -w "\nHTTP Status: %{http_code}\n" http://localhost:8000/api/v1/orders
# Expected: 429 Too Many Requests
```

### Bước 3: Rollback (RTO target < 5 phút)

```bash
START_TIME=$(date +%s)

# Step 1: Verify backup file tồn tại và valid
echo "[$(date)] Step 1: Verifying backup..."
deck file lint "${BACKUP_FILE}"
echo "Backup OK"

# Step 2: Diff để confirm thay đổi
echo "[$(date)] Step 2: Computing diff..."
deck gateway diff "${BACKUP_FILE}" --kong-addr http://localhost:8001

# Step 3: Sync rollback
echo "[$(date)] Step 3: Rolling back..."
deck gateway sync "${BACKUP_FILE}" --kong-addr http://localhost:8001

# Step 4: Verify
echo "[$(date)] Step 4: Verifying..."
curl -s -o /tmp/order-response.json -w "HTTP Status: %{http_code}\n" http://localhost:8000/api/v1/orders
jq '{version}' /tmp/order-response.json

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo ""
echo "=========================================="
echo "Rollback completed in: ${ELAPSED} seconds"
echo "RTO target: < 300 seconds (5 minutes)"
echo "Status: $([ ${ELAPSED} -lt 300 ] && echo 'PASS ✅' || echo 'FAIL ❌')"
echo "=========================================="
```

### Bước 4: Verify no rate-limit after rollback

```bash
echo "=== Verifying rate-limit removed ==="
# Gửi 5 requests nhanh
for i in $(seq 1 5); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
  echo "Request $i: HTTP $STATUS"
done
# Expected: all 200 OK
```

---

## Exercise 6: Feature Flag / Dark Launch (Consumer Targeting)

**Mục tiêu**: Dark launch endpoint `/api/v2/orders/estimate` chỉ cho consumer có tag `beta-tester`, không ảnh hưởng user khác.

### Bước 1: Cập nhật kong.yml với feature flag route

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  # Default route: tất cả user → v1
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true

  # Beta feature route: chỉ cho consumer có x-consumer-tag: beta-tester
  - name: order-service-beta
    url: http://order-v2-beta:1080
    routes:
      - name: order-route-beta
        paths:
          - /api/v2/orders/estimate
        strip_path: false
        headers:
          x-consumer-tag: ["beta-tester"]

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

deck gateway sync kong.yml --kong-addr http://localhost:8001
```

### Bước 2: Test với beta-tester header

```bash
echo "=== Beta user (x-consumer-tag: beta-tester) ==="
curl -s http://localhost:8000/api/v2/orders/estimate \
  -H "x-consumer-tag: beta-tester" | jq '{feature, status, price_range}'

echo "Expected: feature=estimate, status=beta"
```

### Bước 3: Test với non-beta user

```bash
echo "=== Non-beta user (no header) ==="
curl -s -w "\nHTTP Status: %{http_code}\n" http://localhost:8000/api/v2/orders/estimate
# Expected: HTTP 404 (không match route beta)
```

### Bước 4: Khôi phục baseline

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 100
EOF

deck gateway sync kong.yml --kong-addr http://localhost:8001
```

---

## Exercise 7: Observability — Prometheus Metric phân biệt v1/v2

**Mục tiêu**: Verify Prometheus metrics có label version để distinguish v1 vs v2 error rate.

### Bước 1: Enable Prometheus và tạo canary config

```bash
# Update kong.yml với Prometheus plugin + upstream v1/v2
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-upstream
    routes:
      - name: order-route
        paths:
          - /api/v1/orders
        strip_path: false
    plugins:
      - name: prometheus
        config:
          status_code_metrics: true
          latency_metrics: true
          bandwidth_metrics: true

upstreams:
  - name: order-upstream
    targets:
      - target: order-v1:1080
        weight: 90
      - target: order-v2:1080
        weight: 10
EOF

deck gateway sync kong.yml --kong-addr http://localhost:8001

# Verify Prometheus metrics endpoint
curl -sf http://localhost:8001/metrics | head -30
```

### Bước 2: Generate traffic và check Prometheus metrics

```bash
# Generate 200 requests để tạo metric
echo "=== Generating traffic ==="
for i in $(seq 1 200); do
  curl -s http://localhost:8000/api/v1/orders > /dev/null
done

# Check upstream metrics
echo "=== Kong upstream metrics ==="
curl -s http://localhost:8001/metrics \
  | grep "kong_upstream_target_" \
  | grep -v "^#" \
  | sort

echo ""
echo "=== Kong request count by service ==="
curl -s http://localhost:8001/metrics \
  | grep "kong_http_requests_total" \
  | grep -v "^#" \
  | head -10
```

### Bước 3: Prometheus query example (Grafana)

```promql
# Error rate per upstream target
rate(kong_upstream_target_requests_total{upstream="order-upstream", status=~"5.."}[5m])
  / rate(kong_upstream_target_requests_total{upstream="order-upstream"}[5m])

# Latency per version
histogram_quantile(0.99,
  rate(kong_upstream_target_response_duration_ms_bucket[5m])
)

# Canary progress: v2 traffic percentage
rate(kong_upstream_target_requests_total{target="order-v2:1080"}[5m])
  /
(rate(kong_upstream_target_requests_total{target="order-v1:1080"}[5m])
 + rate(kong_upstream_target_requests_total{target="order-v2:1080"}[5m]))
```

### Bước 4: Khôi phục baseline

```bash
# Remove v2 target, restore v1 only
curl -s -X DELETE \
  http://localhost:8001/upstreams/order-upstream/targets/order-v2:1080 \
  | jq '{deleted}'

# Verify v1 only
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight}'
```

---

## Cleanup

```bash
cd ~/kong-rollout

# Stop all containers
docker stop kong-rollout order-v1 order-v2 order-v2-beta 2>/dev/null
docker rm kong-rollout order-v1 order-v2 order-v2-beta 2>/dev/null
docker stop kong-blue kong-green nginx-edge 2>/dev/null
docker rm kong-blue kong-green nginx-edge 2>/dev/null

# Remove docker-compose
docker compose down -v 2>/dev/null

# Remove lab directory
cd ~ && rm -rf ~/kong-rollout

echo "Cleanup done"
```

---

## Tổng Kết Exercises

| Exercise | Kỹ thuật | RTO | Công cụ |
|---|---|---|---|
| 1 | Canary qua upstream weight | < 1 phút | Admin API PATCH |
| 2 | Canary qua route header routing | < 1 phút | kong.yml + decK |
| 3 | Blue-green qua Service.host switch | 2-5 phút | decK sync |
| 4 | Blue-green cluster + Nginx LB | < 30 giây | Nginx upstream reload |
| 5 | Config rollback drill | < 5 phút | decK dump + sync |
| 6 | Feature flag / dark launch | < 1 phút | Route header targeting |
| 7 | Prometheus metric per-version | N/A | Prometheus plugin |
