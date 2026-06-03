# Day 13: Exercises — Hands-on Kong Upstream & Health Checks

> **Yêu cầu**: Docker, Docker Compose, curl, jq, wrk (optional)
> **Kong version**: 3.7
> **Thời gian ước tính**: 120-180 phút

---

## Cài đặt môi trường

```bash
# Tạo thư mục lab
mkdir -p ~/kong-lab-day13 && cd ~/kong-lab-day13

# Tạo Docker network cho lab
docker network create kong-lab-net 2>/dev/null || true
```

---

## Exercise 1: Bootstrap Kong + 4 Backend Replicas — Round-Robin Distribution

**Mục tiêu**: Khởi động Kong DB-less với 4 replicas, verify round-robin distribution.

### Bước 1: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  kong:
    image: kong:3.7
    container_name: kong-upstream
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_LOG_LEVEL: info
      KONG_UPSTREAM_KEEPALIVE_POOL_SIZE: 60
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml:ro
    ports:
      - "8000:8000"
      - "8001:8001"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - kong-net

  # 4 replicas của order-service
  order-1:
    image: python:3.11-slim
    container_name: order-1
    command: >
      python -c "
      import http.server, threading, time, json
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_GET(self):
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.send_header('X-Backend', 'order-1')
          self.end_headers()
          self.wfile.write(json.dumps({'backend': 'order-1', 'path': self.path}).encode())
      httpd = http.server.HTTPServer(('', 8080), H)
      t = threading.Thread(target=httpd.serve_forever, daemon=True)
      t.start()
      time.sleep(86400)
      "
    networks:
      - kong-net
    healthcheck:
      test: ["CMD", "python", "-c", "exit(0)"]
      interval: 5s
      timeout: 3s
      retries: 3

  order-2:
    image: python:3.11-slim
    container_name: order-2
    command: >
      python -c "
      import http.server, threading, time, json
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_GET(self):
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.send_header('X-Backend', 'order-2')
          self.end_headers()
          self.wfile.write(json.dumps({'backend': 'order-2', 'path': self.path}).encode())
      httpd = http.server.HTTPServer(('', 8080), H)
      t = threading.Thread(target=httpd.serve_forever, daemon=True)
      t.start()
      time.sleep(86400)
      "
    networks:
      - kong-net
    healthcheck:
      test: ["CMD", "python", "-c", "exit(0)"]
      interval: 5s
      timeout: 3s
      retries: 3

  order-3:
    image: python:3.11-slim
    container_name: order-3
    command: >
      python -c "
      import http.server, threading, time, json
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_GET(self):
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.send_header('X-Backend', 'order-3')
          self.end_headers()
          self.wfile.write(json.dumps({'backend': 'order-3', 'path': self.path}).encode())
      httpd = http.server.HTTPServer(('', 8080), H)
      t = threading.Thread(target=httpd.serve_forever, daemon=True)
      t.start()
      time.sleep(86400)
      "
    networks:
      - kong-net
    healthcheck:
      test: ["CMD", "python", "-c", "exit(0)"]
      interval: 5s
      timeout: 3s
      retries: 3

  order-4:
    image: python:3.11-slim
    container_name: order-4
    command: >
      python -c "
      import http.server, threading, time, json
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_GET(self):
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.send_header('X-Backend', 'order-4')
          self.end_headers()
          self.wfile.write(json.dumps({'backend': 'order-4', 'path': self.path}).encode())
      httpd = http.server.HTTPServer(('', 8080), H)
      t = threading.Thread(target=httpd.serve_forever, daemon=True)
      t.start()
      time.sleep(86400)
      "
    networks:
      - kong-net
    healthcheck:
      test: ["CMD", "python", "-c", "exit(0)"]
      interval: 5s
      timeout: 3s
      retries: 3

networks:
  kong-net:
    name: kong-upstream-net
    driver: bridge
EOF
```

### Bước 2: Tạo kong.yml tối thiểu (sẽ cập nhật ở Exercise 2)

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: order-upstream
    algorithm: round-robin
    slots: 10000
    targets: []

services:
  - name: order-service
    url: http://order-upstream/api
    routes:
      - name: order-route
        paths: ["/v1/orders"]
        strip_path: true
EOF
```

### Bước 3: Khởi động

```bash
docker compose up -d
sleep 10

# Verify Kong ready
curl -sf http://localhost:8001/ | jq '.version'
# Expected: "3.7.x"
```

### Bước 4: Thêm 4 targets vào upstream (Admin API)

```bash
for i in 1 2 3 4; do
  curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
    -d "target=order-$i:8080" \
    -d "weight=100" | jq -e '.id' > /dev/null \
    && echo "Target order-$i added"
done

# Verify targets
curl -s http://localhost:8001/upstreams/order-upstream/targets \
  | jq '.data[] | {target, weight, created_at}'
```

### Bước 5: Verify round-robin distribution

```bash
echo "=== Round-robin distribution test (50 requests) ==="
for i in $(seq 1 50); do
  curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" \
    | jq -r '.backend' 2>/dev/null
done | sort | uniq -c | sort -rn

# Expected: ~12-13 requests per backend (đều ± 10%)
# Nếu uneven → kiểm tra kong.yml slots hoặc DNS resolution
```

### Bước 6: Inspect ring balancer state

```bash
# Xem upstream health
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, weight, ip}'

# Xem upstream details
curl -s http://localhost:8001/upstreams/order-upstream \
  | jq '{name, slots, algorithm, hash_on}'
```

**Expected output:**
```
Target order-1 added
Target order-2 added
Target order-3 added
Target order-4 added

Round-robin distribution:
  order-1: ~12
  order-2: ~13
  order-3: ~12
  order-4: ~13
```

---

## Exercise 2: Compare Service Direct vs Upstream — Load Balancing

**Mục tiêu**: So sánh Service trỏ trực tiếp backend vs qua Upstream entity.

### Bước 1: Tạo service trỏ trực tiếp order-1 (không qua Upstream)

```bash
# Service trỏ trực tiếp (single backend)
curl -s -X POST http://localhost:8001/services \
  -d "name=order-direct" \
  -d "url=http://order-1:8080/api" \
  | jq '{name, host, url}'

# Route cho service direct
curl -s -X POST http://localhost:8001/services/order-direct/routes \
  -d "name=order-direct-route" \
  -d "paths[]=/direct" \
  -d "strip_path=true" \
  | jq '{name, service}'
```

### Bước 2: So sánh behavior

```bash
echo "=== Direct (no load balancing) ==="
for i in $(seq 1 5); do
  curl -s http://localhost:8000/direct/api \
    -H "Accept: application/json" | jq -r '.backend'
done

echo "=== Via Upstream (round-robin) ==="
for i in $(seq 1 5); do
  curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend'
done
```

**Phân tích:**
- `/direct` → luôn vào order-1 (không có LB, không có failover)
- `/v1/orders` → phân phối round-robin qua 4 replicas

### Bước 3: Simulate order-1 die

```bash
# Stop order-1
docker compose stop order-1

echo "=== Direct: order-1 died ==="
curl -s -w "\nHTTP: %{http_code}\n" http://localhost:8000/direct/api

echo "=== Via Upstream: order-1 died ==="
for i in $(seq 1 8); do
  RESULT=$(curl -s -w "\nHTTP: %{http_code}" http://localhost:8000/v1/orders)
  echo "$RESULT" | jq -r '.backend // .message // empty'
done

# Restore order-1
docker compose start order-1
sleep 5

# Verify
echo "=== After restore ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health}'
```

**Expected behavior:**
- `/direct` → 502 Bad Gateway (order-1 died, không có fallback)
- `/v1/orders` → phần lớn request vẫn vào order-2/3/4, nhưng có thể thấy 502 khi ring chọn order-1 vì chưa bật active/passive health check. Exercise 3 sẽ bật health check để skip target chết tự động.

---

## Exercise 3: Active Health Check — Automatic Failover

**Mục tiêu**: Configure active health check, kill 1 replica, observe automatic failover.

### Bước 1: Tạo healthz endpoint trên backend

```bash
# Tạo backend với /healthz endpoint
cat > backend-with-health.Dockerfile << 'DFEOF'
FROM python:3.11-slim
WORKDIR /app
RUN echo '#!/bin/sh\necho "healthy" > /healthz/index.html\npython -m http.server 8080' > /start.sh && chmod +x /start.sh
CMD ["/start.sh"]
DFEOF

# Cập nhật docker-compose.yml để dùng healthz endpoint
# (Trong lab này, Python server trả về 200 OK cho mọi request,
#  nên health check chỉ cần TCP check hoặc HTTP check bất kỳ path nào)
```

### Bước 2: Configure active health check trên upstream

```bash
# Update upstream với active health check
curl -s -X PATCH http://localhost:8001/upstreams/order-upstream \
  -d "healthchecks.active.type=http" \
  -d "healthchecks.active.http_path=/" \
  -d "healthchecks.active.interval=5" \
  -d "healthchecks.active.timeout=3" \
  -d "healthchecks.active.healthy.successes=2" \
  -d "healthchecks.active.unhealthy.tcp_failures=1" \
  -d "healthchecks.active.unhealthy.http_failures=3" \
  -d "healthchecks.active.unhealthy.timeouts=3" \
  | jq '{name, healthchecks}'

# Verify upstream updated
curl -s http://localhost:8001/upstreams/order-upstream \
  | jq '{algorithm, healthchecks}'
```

### Bước 3: Observe health check probe

```bash
# Bước 3a: Verify all healthy
echo "=== Health check status before kill ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, ip, weight}'

# Bước 3b: Stop order-2
docker compose stop order-2

# Bước 3c: Monitor health change (mỗi 5s trong 60s)
echo "=== Monitoring health check (30s) ==="
for i in $(seq 1 6); do
  echo "--- t=$((i*5))s ---"
  curl -s http://localhost:8001/upstreams/order-upstream/health \
    | jq '.data[] | select(.target | contains("order-2")) | {target, health}'
  sleep 5
done

# Bước 3d: Verify traffic distribution sau khi order-2 unhealthy
echo "=== Traffic distribution (order-2 should get 0) ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend'
done | sort | uniq -c | sort -rn

# Bước 3e: Restore order-2
docker compose start order-2

echo "=== Waiting for order-2 to become healthy again (30s) ==="
for i in $(seq 1 6); do
  echo "--- t=$((i*5))s ---"
  curl -s http://localhost:8001/upstreams/order-upstream/health \
    | jq '.data[] | select(.target | contains("order-2")) | {target, health}'
  sleep 5
done
```

**Expected output:**
```
t=5s:  order-2: unhealthy (1st probe fail)
t=10s: order-2: unhealthy (2nd probe fail)
t=15s: order-2: unhealthy (3rd probe fail → officially unhealthy)

Traffic: chỉ order-1, order-3, order-4 nhận request

t=30s (after restore + probe success):
order-2: healthy
```

---

## Exercise 4: Passive Health Check — Circuit Breaker

**Mục tiêu**: Configure passive health check, simulate 5xx mass errors, observe circuit breaker trip.

### Bước 1: Configure passive health check

```bash
curl -s -X PATCH http://localhost:8001/upstreams/order-upstream \
  -d "healthchecks.passive.type=http" \
  -d "healthchecks.passive.healthy.successes=2" \
  -d "healthchecks.passive.unhealthy.http_failures=5" \
  -d "healthchecks.passive.unhealthy.timeouts=3" \
  | jq '{name, healthchecks}'
```

### Bước 2: Simulate backend degrade — return 503 intermittently

```bash
# Tạo backend mới trả về 503 cho 80% request
cat > docker-compose.override.yml << 'EOF'
version: "3.8"
services:
  order-3:
    image: python:3.11-slim
    container_name: order-3
    command: >
      python -c "
      import http.server, threading, time, json, random
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_GET(self):
          if random.random() < 0.8:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{\"error\":\"degrade\"}')
          else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Backend', 'order-3')
            self.end_headers()
            self.wfile.write(json.dumps({'backend': 'order-3'}).encode())
      httpd = http.server.HTTPServer(('', 8080), H)
      t = threading.Thread(target=httpd.serve_forever, daemon=True)
      t.start()
      time.sleep(86400)
      "
EOF

# Restart order-3
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d order-3
sleep 3
```

### Bước 3: Send traffic và observe circuit breaker

```bash
echo "=== Sending 30 requests to trigger passive health check ==="
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/orders)
  echo "$STATUS"
done | sort | uniq -c

echo ""
echo "=== Check if order-3 is marked unhealthy ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health}'

echo ""
echo "=== Traffic distribution after circuit breaker trip ==="
for i in $(seq 1 20); do
  BACKEND=$(curl -s http://localhost:8000/v1/orders -H "Accept: application/json" | jq -r '.backend // "error"')
  echo "$BACKEND"
done | sort | uniq -c | sort -rn
```

**Expected behavior:**
- 30 requests → ~24 trả 503, ~6 trả 200
- Sau 5 lần http_failures → order-3 marked unhealthy (circuit breaker trip)
- Traffic distribution: order-3 = 0, order-1 + order-2 + order-4 = đều

### Bước 4: Clean up

```bash
# Restore order-3 normal
rm docker-compose.override.yml
docker compose up -d --force-recreate order-3
sleep 3
```

---

## Exercise 5: Weight=0 Drain Pattern — Rolling Deploy

**Mục tiêu**: Simulate rolling deploy bằng weight=0 để drain target trước khi terminate.

### Bước 1: Verify baseline distribution

```bash
echo "=== Baseline distribution (all 4 healthy) ==="
for i in $(seq 1 40); do
  curl -s http://localhost:8000/v1/orders -H "Accept: application/json" | jq -r '.backend'
done | sort | uniq -c | sort -rn
```

### Bước 2: Force order-3 unhealthy (drain)

```bash
# Force order-3 unhealthy via Admin API
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X PUT \
  http://localhost:8001/upstreams/order-upstream/targets/order-3:8080/unhealthy

# Verify health status
echo "=== Health status after force unhealthy ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, weight}'
```

### Bước 3: Verify order-3 receives 0 traffic

```bash
echo "=== Distribution after drain (order-3 should be 0) ==="
for i in $(seq 1 40); do
  BACKEND=$(curl -s http://localhost:8000/v1/orders -H "Accept: application/json" | jq -r '.backend')
  echo "$BACKEND"
done | sort | uniq -c | sort -rn

echo ""
echo "=== Kong upstream health ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, weight}'
```

### Bước 4: Terminate old replica (simulate deploy)

```bash
# In production: docker compose stop order-3 && deploy new version
# Trong lab: just stop
docker compose stop order-3
echo "order-3 container stopped"
```

### Bước 5: Wait và restore (simulate new replica ready)

```bash
echo "=== Creating new target for order-3 (with new version) ==="

# Tạo target mới cho order-3 (Kong không cho update target cũ, phải tạo mới)
# Trong lab này, order-3 container đang stop → tạo mới container trước
docker compose up -d order-3
sleep 5

# Add target mới với weight=0 ban đầu (slow start)
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d "target=order-3:8080" \
  -d "weight=0" \
  | jq '{target, weight, created}'

echo "=== order-3 target weight=0 (draining) ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | select(.target | contains("order-3")) | {target, health, weight, ip}'

# Verify 0 traffic
echo "=== Distribution (order-3 should get 0 traffic) ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8000/v1/orders -H "Accept: application/json" | jq -r '.backend'
done | grep -c "order-3" || echo "order-3: 0 requests"

# Bước 6: Gradually increase weight (slow start)
echo "=== Slow start: increase weight to 50 ==="
# Lấy target ID của order-3 mới
TARGET_ID=$(curl -s "http://localhost:8001/upstreams/order-upstream/targets" \
  | jq -r '.data[] | select(.target == "order-3:8080") | .id' | tail -1)
echo "New target ID: $TARGET_ID"

# Tạo target mới với weight=50 (thay vì update)
curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
  -d "target=order-3:8080" \
  -d "weight=50" \
  | jq '{target, weight, created}'

echo "=== Distribution after weight=50 ==="
for i in $(seq 1 40); do
  curl -s http://localhost:8000/v1/orders -H "Accept: application/json" | jq -r '.backend'
done | sort | uniq -c | sort -rn

echo "=== Full health status ==="
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, weight}'
```

---

## Exercise 6: Consistent Hashing + Hash Fallback — Sticky Session

**Mục tiêu**: Configure consistent-hashing với session ID header, verify sticky behavior.

### Bước 1: Tạo upstream với consistent-hashing

```bash
# Xóa upstream cũ
curl -s -X DELETE http://localhost:8001/upstreams/order-upstream

# Tạo upstream mới với consistent-hashing
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=consistent-hashing" \
  -d "slots=10000" \
  -d "hash_on=header" \
  -d "hash_on_header=X-Session-ID" \
  -d "hash_fallback=round-robin" \
  -d "healthchecks.active.type=http" \
  -d "healthchecks.active.http_path=/" \
  -d "healthchecks.active.interval=10" \
  -d "healthchecks.active.timeout=5" \
  -d "healthchecks.active.healthy.successes=2" \
  -d "healthchecks.active.unhealthy.http_failures=3" \
  -d "healthchecks.active.unhealthy.timeouts=3" \
  | jq '{name, algorithm, hash_on, hash_on_header, hash_fallback}'

# Add targets
for i in 1 2 3 4; do
  curl -s -X POST http://localhost:8001/upstreams/order-upstream/targets \
    -d "target=order-$i:8080" \
    -d "weight=100" > /dev/null \
    && echo "Target order-$i added"
done
```

### Bước 2: Verify sticky session với session ID

```bash
echo "=== Test sticky session ==="

# Session A → phải luôn vào cùng backend
SESSION_A="sess-AAAA-$(date +%s)"
echo "Session A: $SESSION_A"
for i in $(seq 1 5); do
  BACKEND=$(curl -s -H "X-Session-ID: $SESSION_A" \
    http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend')
  echo "  Request $i: $BACKEND"
done

echo ""

# Session B → phải luôn vào cùng backend (khác session A)
SESSION_B="sess-BBBB-$(date +%s)"
echo "Session B: $SESSION_B"
for i in $(seq 1 5); do
  BACKEND=$(curl -s -H "X-Session-ID: $SESSION_B" \
    http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend')
  echo "  Request $i: $BACKEND"
done

echo ""

# Anonymous (không có session ID) → round-robin (hash_fallback)
echo "=== Anonymous requests (round-robin fallback) ==="
for i in $(seq 1 5); do
  BACKEND=$(curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend')
  echo "  Request $i: $BACKEND"
done
```

**Expected:**
- Session A: cùng backend mọi request (sticky)
- Session B: cùng backend mọi request (sticky)
- Anonymous: phân phối round-robin (hash_fallback)

### Bước 3: Verify fallback khi session header không có

```bash
# Hash fallback = round-robin → anonymous user phân phối đều
echo "=== Anonymous distribution (20 requests) ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" | jq -r '.backend'
done | sort | uniq -c | sort -rn
```

---

## Exercise 7: Health Check Tuning — Threshold và Interval

**Mục tiêu**: Tune active health check parameters, measure detection latency.

### Bước 1: Baseline — interval=10s, threshold=2

```bash
# Update upstream với conservative settings
curl -s -X PATCH http://localhost:8001/upstreams/order-upstream \
  -d "healthchecks.active.interval=10" \
  -d "healthchecks.active.healthy.successes=2" \
  -d "healthchecks.active.unhealthy.http_failures=3" \
  | jq '{healthchecks}'

echo "Current config: interval=10s, successes=2, failures=3"
echo "Detection latency: 10s × 2 = 20s (healthy), 10s × 3 = 30s (unhealthy)"
```

### Bước 2: Aggressive — interval=2s, threshold=2

```bash
curl -s -X PATCH http://localhost:8001/upstreams/order-upstream \
  -d "healthchecks.active.interval=2" \
  -d "healthchecks.active.healthy.successes=2" \
  -d "healthchecks.active.unhealthy.http_failures=3" \
  | jq '{healthchecks}'

echo "Aggressive config: interval=2s, successes=2, failures=3"
echo "Detection latency: 2s × 2 = 4s (healthy), 2s × 3 = 6s (unhealthy)"
echo ""
echo "=== Monitoring order-3 health with aggressive interval ==="

# Stop order-3
docker compose stop order-3

for i in $(seq 1 8); do
  HEALTH=$(curl -s "http://localhost:8001/upstreams/order-upstream/health" \
    | jq -r '.data[] | select(.target | contains("order-3")) | .health // "unknown"')
  echo "t=$((i*2))s: $HEALTH"
  sleep 2
done

# Restore
docker compose start order-3
```

### Bước 3: Impact analysis

```bash
echo "=== Health check overhead comparison ==="
echo "interval=10s: probe overhead ≈ 0.4 RPS (4 targets × 0.1 probe/s)"
echo "interval=2s:  probe overhead ≈ 2.0 RPS (4 targets × 0.5 probe/s)"
echo ""
echo "Recommendation:"
echo "  interval=10s: low traffic service, stable backend"
echo "  interval=5s:  medium traffic, moderate change frequency"
echo "  interval=2s:  high traffic, frequent deploy, need fast failover"
echo "  interval<2s:  generally not recommended (overhead > benefit)"
```

---

## Exercise 8 (Optional): Kong Prometheus Metrics — Upstream Observability

**Mục tiêu**: Observe upstream health qua Prometheus metrics.

### Bước 1: Enable Prometheus plugin

```bash
# Apply Prometheus plugin global
curl -s -X POST http://localhost:8001/plugins \
  -d "name=prometheus" \
  -d "config.latency_metrics=true" \
  -d "config.bandwidth_metrics=true" \
  | jq '{name, enabled}'
```

### Bước 2: Query upstream metrics

```bash
# Prometheus metrics endpoint
curl -s http://localhost:8001/metrics | grep -E \
  "kong_upstream_target_health|kong_upstream" \
  | head -30

# Check specific target health
curl -s http://localhost:8001/upstreams/order-upstream/health \
  | jq '.data[] | {target, health, ip, weight}'

# Request count per target (via access log analysis)
# Dùng backend health check header
echo "=== Request distribution via X-Backend header ==="
for i in $(seq 1 20); do
  curl -s http://localhost:8000/v1/orders \
    -H "Accept: application/json" \
    -H "X-Backend-Check: true" \
    | jq -r '.backend'
done | sort | uniq -c | sort -rn
```

---

## Exercise 9 (Optional): DNS-Based Discovery — Consul SRV Pattern

**Mục tiêu**: Hiểu cách Kong hỗ trợ DNS-based discovery (không dùng target entity).

### Bước 1: Concept explanation

```bash
# Kong hỗ trợ algorithm=none → Kong không chọn target
# DNS SRV record tự phân phối weight + port

# Trong Kong:
#   Service.host = "order-service.consul"
#   Upstream.algorithm = "none"
#   Upstream.use_srv_name = true

# Kong đọc SRV record và tự resolve target
# → Không cần Target entity!
# → Target được discover tự động từ DNS
```

### Bước 2: Tạo upstream với algorithm=none

```bash
# Xóa upstream cũ
curl -s -X DELETE http://localhost:8001/upstreams/order-upstream

# Tạo upstream với algorithm=none
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream-dns" \
  -d "algorithm=none" \
  -d "healthchecks.active.type=http" \
  -d "healthchecks.active.http_path=/" \
  -d "healthchecks.active.interval=10" \
  -d "healthchecks.active.timeout=5" \
  -d "healthchecks.active.healthy.successes=2" \
  -d "healthchecks.active.unhealthy.http_failures=3" \
  | jq '{name, algorithm, slots}'

# Không add targets! Kong sẽ dùng DNS resolution

# Tạo service trỏ tới upstream mới
curl -s -X POST http://localhost:8001/services \
  -d "name=order-service-dns" \
  -d "url=http://order-upstream-dns/api" \
  | jq '{name, url}'

curl -s -X POST http://localhost:8001/services/order-service-dns/routes \
  -d "name=order-dns-route" \
  -d "paths[]=/dns" \
  -d "strip_path=true" \
  | jq '{name}'
```

### Bước 3: Test DNS-based routing

```bash
# Verify upstream không có targets
echo "=== Targets in order-upstream-dns ==="
curl -s http://localhost:8001/upstreams/order-upstream-dns/targets \
  | jq '.data'

echo ""
echo "=== DNS-based routing (algorithm=none) ==="
# Với algorithm=none và không có targets, Kong dùng host_header
# → Kong sẽ connect tới upstream name → Docker DNS
for i in $(seq 1 5); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/dns/api)
  echo "Request $i: HTTP $STATUS"
done
```

**Kết luận**: DNS-based discovery với `algorithm=none` hữu ích khi:
- Dùng Consul service mesh
- Backend IP được quản lý hoàn toàn bởi service discovery
- Không muốn quản lý target entity thủ công

---

## Cleanup

```bash
# Dừng container
docker compose -f docker-compose.yml down 2>/dev/null

# Xóa lab files
cd ~/kong-lab-day13 && rm -f docker-compose.override.yml kong.yml backend-with-health.Dockerfile

# Verify cleanup
docker ps --filter "name=kong-upstream" --filter "name=order-"
# Expected: empty
```

---

## Tổng Kết

| Exercise | Lệnh/Concept chính | Kỹ năng |
|---|---|---|
| 1 | Upstream + Target Admin API, round-robin | Bootstrap upstream entity |
| 2 | Service trực tiếp vs Upstream | Compare load balancing |
| 3 | Active health check + failover | Proactive probe |
| 4 | Passive health check + circuit breaker | Reactive error counting |
| 5 | weight=0 drain + force unhealthy | Rolling deploy |
| 6 | consistent-hashing + hash_fallback | Sticky session |
| 7 | Interval + threshold tuning | Health check latency |
| 8 | Prometheus upstream metrics | Observability |
| 9 | algorithm=none + DNS discovery | SRV-based discovery |
