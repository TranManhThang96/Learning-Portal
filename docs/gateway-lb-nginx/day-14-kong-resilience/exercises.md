# Day 14: Exercises — Timeout, Retry, Circuit Breaker & Backpressure

> **Yêu cầu**: Docker, Docker Compose, curl, jq, wrk hoặc hey
> **Kong version**: 3.7 (DB-less)
> **Thời gian ước tính**: 90-120 phút
> **Lab architecture**: Kong + 3 backend targets (normal, slow, fail)

---

## Cài đặt Lab Environment

### Bước 1: Tạo thư mục lab

```bash
mkdir -p ~/kong-resilience-lab && cd ~/kong-resilience-lab
```

### Bước 2: Tạo backend simulators

```bash
cat > backends.py << 'EOF'
# Backend simulators cho 3 target
# - normal: 100ms response
# - slow:   5s  response (DB slow simulation)
# - fail:   ECONNREFUSED

import http.server, time, random, socket

class NormalHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # Suppress log
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers()
            self.wfile.write(b"OK")
            return
        time.sleep(random.uniform(0.05, 0.15))  # 50-150ms
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"backend":"normal","latency_ms":100}')

class SlowHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
            return
        time.sleep(5.0)  # 5s — simulate DB lock
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"backend":"slow","latency_ms":5000}')

# Fail backend: crash immediately (ECONNREFUSED)
# Run with: python3 backends.py fail 30005
# It will fail to bind → ECONNREFUSED
EOF
```

### Bước 3: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  # === Kong Gateway ===
  kong:
    image: kong:3.7
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/declarative/kong.yml
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_LOG_LEVEL: info
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ACCESS_LOG: /dev/stdout
    volumes:
      - ./kong.yml:/kong/declarative/kong.yml:ro
    ports:
      - "8000:8000"
      - "8001:8001"
    depends_on:
      - normal-backend
      - slow-backend

  # === Normal Backend (100ms) ===
  normal-backend:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, time, random, threading
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
          time.sleep(random.uniform(0.05, 0.15))
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.end_headers()
          self.wfile.write(b'{\"backend\":\"normal\"}')
      http.server.HTTPServer(('', 3000), H).serve_forever()
      "
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 5s
      timeout: 3s
      retries: 3

  # === Slow Backend (5s) ===
  slow-backend:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, time
      class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
          time.sleep(5.0)
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.end_headers()
          self.wfile.write(b'{\"backend\":\"slow\"}')
      http.server.HTTPServer(('', 3001), H).serve_forever()
      "
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3001/health')"]
      interval: 5s
      timeout: 3s
      retries: 3

  # === Fail Backend (ECONNREFUSED simulation) ===
  # Dùng một service khác port để Kong connect refused
  fail-backend:
    image: alpine:3.18
    command: ["sh", "-c", "echo 'fail-backend ready (will not listen)' && sleep infinity"]
    # Port 3002 không listen → ECONNREFUSED khi Kong gọi

  # === Prometheus (optional — metrics) ===
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--scrape.interval=5s'
    ports:
      - "9090:9090"
EOF
```

### Bước 4: Tạo prometheus.yml (optional)

```bash
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 5s
scrape_configs:
  - job_name: "kong"
    static_configs:
      - targets: ["kong:8001"]
    metrics_path: /metrics
EOF
```

### Bước 5: Tạo kong.yml ban đầu

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: test-service
    url: http://normal-backend:3000
    # Default: retries=5, timeouts=60000ms — sẽ thay đổi trong các lab
    retries: 5
    connect_timeout: 60000
    write_timeout: 60000
    read_timeout: 60000
    routes:
      - name: test-route
        paths: ["/api/test"]
        strip_path: false

upstreams:
  - name: multi-backend
    targets:
      - target: normal-backend:3000
        weight: 100
      - target: slow-backend:3001
        weight: 100
      - target: fail-backend:3002
        weight: 100
    healthchecks:
      passive:
        healthy:
          successes: 2
        unhealthy:
          http_failures: 2
          timeouts: 2
          tcp_failures: 2
    slots: 100

plugins:
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
EOF
```

### Bước 6: Khởi động

```bash
docker compose up -d
sleep 8

# Verify
curl -s http://localhost:8001/ | jq '.version'
curl -s http://localhost:8000/api/test | jq
```

---

## Exercise 1: Timeout Budget — Kong Default vs Production Config

**Mục tiêu**: Phân biệt behavior khi dùng Kong default timeout (60s) vs production timeout (5s).

### Bước 1: Baseline — Kong default (60s timeout)

```bash
# Test trực tiếp slow backend
curl -s -m 10 http://localhost:8000/api/test -w "\nTime: %{time_total}s\n"
# Expected: ~5s response (slow backend)
# Timeout 10s > 5s → thành công
```

### Bước 2: Tune timeout xuống 3s

```bash
# Tạo kong.yml với production timeout
cat > kong-prod.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: test-service
    url: http://slow-backend:3001   # Chỉ backend slow
    retries: 2                      # Retry 2 lần
    connect_timeout: 2000          # 2s
    write_timeout: 2000
    read_timeout: 3000             # 3s
    routes:
      - name: test-route
        paths: ["/api/test"]
        strip_path: false
EOF

# Áp dụng config mới
cp kong-prod.yml kong.yml
curl -X POST http://localhost:8001/config \
  -F config=@kong.yml
sleep 3
```

### Bước 3: Verify timeout hoạt động

```bash
# Test: request đến slow backend (5s response) với 3s timeout
# Expected: HTTP 504 Gateway Timeout
curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/test -m 10

# Test normal backend với 3s timeout (normal = 100ms, OK)
# Thêm normal backend vào config
cat > kong-prod.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: normal-service
    url: http://normal-backend:3000
    retries: 2
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: normal-route
        paths: ["/api/normal"]
        strip_path: false

  - name: slow-service
    url: http://slow-backend:3001
    retries: 0                      # KHÔNG retry cho slow
    connect_timeout: 1000           # 1s
    write_timeout: 1000
    read_timeout: 3000              # 3s
    routes:
      - name: slow-route
        paths: ["/api/slow"]
        strip_path: false
EOF

cp kong-prod.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Verify normal route
curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/normal

# Verify slow route (timeout)
curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/slow -m 10
```

### Bước 4: Kiểm tra X-Kong latency header

```bash
curl -I -s http://localhost:8000/api/normal | grep -i "X-Kong"
curl -I -s http://localhost:8000/api/slow  | grep -i "X-Kong"
```

**Expected output:**
```
X-Kong-Proxy-Latency: 2       # Kong overhead ~2ms
X-Kong-Upstream-Latency: 98   # Normal backend ~100ms
```

### Kết quả mong đợi:

| Config | Backend | Timeout | Result | Time |
|---|---|---|---|---|
| Default (60s) | slow | 60s | 200 OK | 5s |
| Tuned (3s) | slow | 3s | 504 Gateway Timeout | 3s |
| Tuned (3s) | normal | 3s | 200 OK | ~100ms |

---

## Exercise 2: Retry Storm — Mô phỏng load spike khi retries=5

**Mục tiêu**: Thấy rõ retry storm xảy ra khi upstream slow và retries cao.

### Bước 1: Bật retries=5 với slow backend

```bash
cat > kong-retry-storm.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: retry-storm-service
    url: http://slow-backend:3001
    retries: 5              # ⚠️ Default = 5 — nguy hiểm!
    connect_timeout: 5000
    write_timeout: 5000
    read_timeout: 5000      # 5s = bằng backend response time
    routes:
      - name: retry-storm-route
        paths: ["/api/retry"]
        strip_path: false
EOF

cp kong-retry-storm.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Benchmark với retries=5

```bash
# Gửi 10 request đồng thời đến slow backend
# Kong sẽ retry: 10 × 5 = 50 request đến slow backend
# Nếu mỗi retry tốn 5s: tổng load = 50 × 5s = 250s CPU time

echo "=== Testing retries=5, slow backend ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/retry -m 30

# Phân tích: request này:
# - Lần 1: 5s timeout
# - Retry 1: 5s timeout
# - Retry 2: 5s timeout
# - Retry 3: 5s timeout
# - Retry 4: 5s timeout
# - Retry 5: 5s timeout
# Tổng: 6 × 5s = 30s
```

### Bước 3: Giảm retries, observe khác biệt

```bash
# Giảm retries xuống 0
cat > kong-safe.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: retry-storm-service
    url: http://slow-backend:3001
    retries: 0              # ✅ Không retry
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: retry-storm-route
        paths: ["/api/retry"]
        strip_path: false
EOF

cp kong-safe.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

echo "=== Testing retries=0, slow backend ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/retry -m 10
# Expected: 504 sau ~3s (timeout), không retry, tổng thời gian ~3s thay vì 30s
```

### Bước 4: Tính retry budget

```bash
# Gửi 100 request đến slow backend, đếm tổng upstream calls
# Với retries=5: 100 × 6 = 600 upstream calls
# Với retries=0: 100 × 1 = 100 upstream calls
# Retry budget = (600 - 100) / 100 = 500% excess!

# Metric: Kong Prometheus (nếu có prometheus)
# retry_total counter / request_total counter

# Kiểm tra bằng wrk/hey
docker run --rm \
  --network host \
  williamyeh/wrk:latest \
  -t 2 -c 5 -d 5s \
  http://localhost:8000/api/retry

# So sánh:
# retries=5: tổng upstream load = high, latency p99 ~30s
# retries=0: tổng upstream load = normal, latency p99 ~3s
```

**Kết quả mong đợi:**

| retries | Upstream calls (100 requests) | p99 latency | 504 rate |
|---|---|---|---|
| 5 | 600 | ~30s | 0% (đều timeout sau 30s) |
| 0 | 100 | ~3s | 100% (fail nhanh) |
| 2 | 300 | ~15s | 100% |

---

## Exercise 3: Retry với Exponential Backoff (Custom Lua Plugin)

**Mục tiêu**: Implement exponential backoff + jitter cho request retry ở Kong layer.

### Bước 1: Tạo custom retry plugin với backoff

```bash
mkdir -p kong/plugins/retry-backoff

cat > kong/plugins/retry-backoff/handler.lua << 'LUA'
-- kong/plugins/retry-backoff/handler.lua
-- Custom retry với exponential backoff + full jitter

local retry_backoff = {}

retry_backoff.PRIORITY = 1000  -- Chạy cuối access phase

local DEFAULT_BASE_DELAY = 1000  -- ms
local DEFAULT_CAP = 5000          -- ms
local MAX_RETRIES = 2

function retry_backoff:access(conf)
  local base = conf.base_delay_ms or DEFAULT_BASE_DELAY
  local cap  = conf.cap_delay_ms  or DEFAULT_CAP

  -- Tính delay cho attempt tiếp theo (nếu retry)
  -- Đây là placeholder — Kong không gọi Lua hook giữa các retry attempt
  -- Plugin này chỉ log/reject, không implement backoff retry thực sự
  -- Retry backoff thực sự phải ở client layer

  kong.ctx.shared.retry_backoff_base = base
  kong.ctx.shared.retry_backoff_cap  = cap
end

function retry_backoff:header_filter(conf)
  -- Gắn retry config vào response header
  kong.response.set_header("X-Retry-Backoff",
    string.format("base=%dms cap=%dms max_retries=%d",
      conf.base_delay_ms or DEFAULT_BASE_DELAY,
      conf.cap_delay_ms  or DEFAULT_CAP,
      MAX_RETRIES
    ))
end

return retry_backoff
LUA

cat > kong/plugins/retry-backoff/schema.lua << 'LUA'
-- kong/plugins/retry-backoff/schema.lua
local typedefs = require "kong.db.schema.typedefs"

return {
  name = "retry-backoff",
  fields = {
    { config = {
        type = "record",
        fields = {
          { base_delay_ms = { type = "integer", default = 1000 } },
          { cap_delay_ms  = { type = "integer", default = 5000 } },
          { enabled       = { type = "boolean", default = true } },
        },
    } },
  },
}
LUA
```

### Bước 2: Áp dụng plugin vào service

```bash
cat > kong-backoff.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: backoff-test
    url: http://slow-backend:3001
    retries: 0              # Tắt Kong retry
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: backoff-route
        paths: ["/api/backoff"]
        strip_path: false
    plugins:
      - name: retry-backoff
        config:
          base_delay_ms: 1000
          cap_delay_ms: 3000
          enabled: true

plugins:
  - name: retry-backoff
    proto: lua plugin
    path: /usr/local/kong/plugins/retry-backoff
EOF

# Áp dụng (note: custom plugin cần mount volume trong production)
cp kong-backoff.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Test
curl -s -I http://localhost:8000/api/backoff | grep -i "X-Retry"
```

**Note quan trọng**: Kong không gọi Lua hook giữa các retry attempt. Exponential backoff thực sự phải implement ở client (HTTP client SDK) hoặc Envoy sidecar. Plugin này chỉ minh hoạ concept.

---

## Exercise 4: Circuit Breaker — Passive Health Check

**Mục tiêu**: Quan sát passive health check mark target unhealthy và ngừng gửi traffic.

### Bước 1: Upstream với 3 target (round-robin)

```bash
cat > kong-cb.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: cb-upstream
    slots: 100
    healthchecks:
      passive:
        healthy:
          successes: 1           # 1 lần OK → healthy ngay
        unhealthy:
          tcp_failures: 2       # 2 TCP fail → unhealthy
          timeouts: 2            # 2 timeout → unhealthy
          http_failures: 2       # 2 5xx → unhealthy
    targets:
      - target: normal-backend:3000
        weight: 100
      - target: slow-backend:3001
        weight: 100
      - target: fail-backend:3002
        weight: 100

services:
  - name: cb-service
    url: http://cb-upstream
    retries: 2
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: cb-route
        paths: ["/api/cb"]
        strip_path: false
EOF

cp kong-cb.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Gửi request và quan sát target selection

```bash
# Gửi nhiều request để trigger round-robin
echo "=== Testing round-robin through upstream ==="
for i in {1..15}; do
  RESP=$(curl -s http://localhost:8000/api/cb)
  echo "$i: $RESP"
done
```

### Bước 3: Quan sát target health sau nhiều request

```bash
# Check upstream target health
curl -s http://localhost:8001/upstreams/cb-upstream/health \
  | jq '.data[] | {target, weight, healthy, ip, port}'

# Sau khi request đến fail-backend:3002:
# Expected: healthy=false, tcp_failures >= 2

# Request đến slow-backend:3001:
# Nếu timeout > 2 lần: healthy=false, timeouts >= 2
```

### Bước 4: Manual reset target health

```bash
# Reset fail-backend về healthy
curl -X PUT \
  http://localhost:8001/upstreams/cb-upstream/targets/fail-backend:3002/healthy

# Verify
curl -s http://localhost:8001/upstreams/cb-upstream/health \
  | jq '.data[] | {target, healthy}'
```

### Bước 5: Quan sát CB behavior với timeout threshold

```bash
# Tăng passive HC threshold để ít nhạy, observe
# (Fail nhanh hơn với tcp_failures: 1)
cat > kong-cb-sensitive.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: cb-upstream
    slots: 100
    healthchecks:
      passive:
        healthy:
          successes: 1
        unhealthy:
          tcp_failures: 1      # ⚡ Nhạy hơn: 1 fail → unhealthy
          timeouts: 1          # ⚡ 1 timeout → unhealthy
    targets:
      - target: normal-backend:3000
        weight: 100
      - target: fail-backend:3002
        weight: 100

services:
  - name: cb-service
    url: http://cb-upstream
    retries: 2
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: cb-route
        paths: ["/api/cb"]
        strip_path: false
EOF

cp kong-cb-sensitive.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Test: gửi 1 request → fail-backend → fail → unhealthy
curl -s http://localhost:8000/api/cb -m 5 -w "\nHTTP: %{http_code}\n"

# Check health
curl -s http://localhost:8001/upstreams/cb-upstream/health \
  | jq '.data[] | {target, healthy}'

# Send 2 more requests → chỉ normal-backend được gọi
echo "=== Requests after fail-backend marked unhealthy ==="
for i in {1..5}; do
  curl -s http://localhost:8000/api/cb -m 3 | jq '.backend'
done
```

**Kết quả mong đợi:**

```
# Sau 1 request đến fail-backend (ECONNREFUSED):
Target health:
- normal-backend:3000: healthy=true
- fail-backend:3002: healthy=false ← passive HC đánh dấu

# 5 request tiếp theo:
- normal-backend được gọi 5 lần
- fail-backend được skip (circuit breaker!)
```

---

## Exercise 5: Backpressure — worker_connections Exhaustion

**Mục tiêu**: Mô phỏng upstream slow gây connection backlog, phát hiện qua latency.

### Bước 1: Config cho stress test

```bash
cat > kong-backpressure.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: bp-service
    url: http://slow-backend:3001
    retries: 0              # Không retry
    connect_timeout: 10000  # 10s
    write_timeout: 10000
    read_timeout: 10000     # 10s — bằng backend response
    routes:
      - name: bp-route
        paths: ["/api/bp"]
        strip_path: false

plugins:
  - name: rate-limiting      # Giới hạn request rate đầu vào, không phải concurrency tuyệt đối
    config:
      second: 100
      policy: local
EOF

cp kong-backpressure.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Stress test với wrk

```bash
# Gửi 200 concurrent request đến slow backend
# Nếu Kong giữ connection 10s mỗi request:
# Concurrency = 200 × 10s = 2000 connections

docker run --rm --network host \
  williamyeh/wrk:latest \
  -t 4 -c 200 -d 15s \
  --latency \
  http://localhost:8000/api/bp

# Expected:
# p50: ~5s (slow backend bị queue)
# p95: ~10s (timeout boundary)
# p99: ~10s+ (timeout)
# Error rate: ~80% (timeout)
```

### Bước 3: Giảm timeout để tránh backpressure

```bash
cat > kong-bp-fixed.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: bp-service
    url: http://slow-backend:3001
    retries: 0
    connect_timeout: 2000    # 2s — ngắn!
    write_timeout: 2000
    read_timeout: 3000        # 3s — fail nhanh
    routes:
      - name: bp-route
        paths: ["/api/bp"]
        strip_path: false
EOF

cp kong-bp-fixed.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Test lại
docker run --rm --network host \
  williamyeh/wrk:latest \
  -t 4 -c 200 -d 15s \
  --latency \
  http://localhost:8000/api/bp

# Expected:
# Error rate giảm đáng kể
# p99: ~3s (timeout ngắn, fail nhanh)
# Upstream không bị backlog
```

### Bước 4: Thêm proxy-cache để giảm upstream load

```bash
# Tạo endpoint trả về cached response
cat > kong-cache.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: cached-service
    url: http://normal-backend:3000
    retries: 0
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: cached-route
        paths: ["/api/cached"]
        strip_path: false
    plugins:
      - name: proxy-cache
        config:
          response_code: [200]
          request_method: [GET]
          cache_ttl: 30
          strategy: memory

  - name: bp-service
    url: http://slow-backend:3001
    retries: 0
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: bp-route
        paths: ["/api/bp"]
        strip_path: false
EOF

cp kong-cache.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Test cache
echo "=== First request (cache miss) ==="
curl -s -w "Time: %{time_total}s\n" http://localhost:8000/api/cached

echo "=== Second request (cache hit) ==="
curl -s -w "Time: %{time_total}s\n" http://localhost:8000/api/cached

# Xem Kong cache header
curl -I -s http://localhost:8000/api/cached | grep -i "X-Cache\|X-Kong"
```

---

## Exercise 6: Cascading Failure — 1 Backend Slow

**Mục tiêu**: Mô phỏng cascading failure từ 1 backend slow vào toàn hệ thống.

### Bước 1: Tạo upstream với mixed targets

```bash
cat > kong-cascade.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: cascade-upstream
    slots: 100
    healthchecks:
      passive:
        healthy:
          successes: 1
        unhealthy:
          timeouts: 3
          tcp_failures: 3
    targets:
      - target: normal-backend:3000
        weight: 100
      - target: slow-backend:3001
        weight: 100

services:
  - name: cascade-service
    url: http://cascade-upstream
    retries: 3              # ⚠️ Retries cao = nguy hiểm!
    connect_timeout: 5000
    write_timeout: 5000
    read_timeout: 5000
    routes:
      - name: cascade-route
        paths: ["/api/cascade"]
        strip_path: false
EOF

cp kong-cascade.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Quan sát cascade khi 1 target slow

```bash
# Test đơn lẻ
echo "=== Single request (retries=3, timeout=5s each) ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/cascade -m 20

# Phân tích timeline:
# t=0s:    Request → normal-backend (100ms) → 200 OK!
# Tắt normal-backend để force request đến slow-backend:
docker compose stop normal-backend

# Test lại — tất cả request đến slow-backend (5s)
echo "=== After stopping normal-backend ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/cascade -m 30

# Test concurrent
echo "=== Concurrent requests (10 parallel) ==="
for i in {1..10}; do
  curl -s http://localhost:8000/api/cascade -m 20 -w "\nHTTP: %{http_code}\n" &
done
wait
# Expected: Tất cả request timeout sau ~20s (4 × 5s)
```

### Bước 3: Fix cascade bằng giảm retries + giảm timeout

```bash
cat > kong-cascade-fix.yml << 'EOF'
_format_version: "3.0"
_transform: true

upstreams:
  - name: cascade-upstream
    slots: 100
    healthchecks:
      passive:
        healthy:
          successes: 1
        unhealthy:
          timeouts: 1          # Nhạy hơn!
          tcp_failures: 1
    targets:
      - target: normal-backend:3000
        weight: 100
      - target: slow-backend:3001
        weight: 100

services:
  - name: cascade-service
    url: http://cascade-upstream
    retries: 0                # ✅ KHÔNG retry
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000        # ✅ 3s timeout
    routes:
      - name: cascade-route
        paths: ["/api/cascade"]
        strip_path: false
EOF

cp kong-cascade-fix.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3

# Restart normal-backend
docker compose start normal-backend
sleep 3

# Test lại
echo "=== Fixed config: retries=0, timeout=3s ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/cascade

# Test concurrent — fail nhanh thay vì cascade
echo "=== Concurrent (10 parallel) with fix ==="
time (
  for i in {1..10}; do
    curl -s http://localhost:8000/api/cascade -m 5 -w "HTTP: %{http_code}\n" &
  done
  wait
)
# Expected: ~3s total (timeout ngắn), error rate 100%
```

---

## Exercise 7: Deadline Propagation — X-Request-Deadline Header

**Mục tiêu**: Implement deadline propagation để upstream biết còn bao lâu.

### Bước 1: Tạo upstream với deadline header

```bash
cat > kong-deadline.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: deadline-service
    url: http://slow-backend:3001
    retries: 0
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: deadline-route
        paths: ["/api/deadline"]
        strip_path: false

plugins:
  - name: pre-function
    config:
      access:
        - |
          local deadline = kong.request.get_header("X-Request-Deadline")
          local default_deadline = 5000  -- 5s default
          local effective = tonumber(deadline) or default_deadline

          -- Log deadline để verify
          kong.log("Effective deadline: ", effective, "ms")

          -- Lưu vào shared context
          kong.ctx.shared.request_deadline = effective
LUA
EOF

cp kong-deadline.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Test với và không có deadline header

```bash
echo "=== Without deadline header (default 5s) ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8000/api/deadline -m 10
# Expected: Timeout ~5s (slow backend = 5s)

echo "=== With deadline 2000ms ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  -H "X-Request-Deadline: 2000" \
  http://localhost:8000/api/deadline -m 10
# Expected: Timeout ~2s (deadline propagation)

echo "=== With deadline 10000ms ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  -H "X-Request-Deadline: 10000" \
  http://localhost:8000/api/deadline -m 15
# Expected: Success ~5s (deadline đủ dài)
```

### Bước 3: Nginx edge với deadline propagation

```bash
cat > nginx-deadline.conf << 'EOF'
# nginx-deadline.conf — Edge proxy với deadline propagation
# Dùng docker-compose riêng cho phần này

server {
    listen 8888;

    location /api/ {
        # Lấy deadline từ client, mặc định 30s
        set $client_deadline 30000;

        # Trừ edge overhead (5s)
        set $kong_deadline 25000;

        # Forward deadline sang Kong
        proxy_set_header X-Request-Deadline $kong_deadline;
        proxy_set_header Host $host;
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 20s;
        proxy_connect_timeout 5s;

        add_header X-Request-Deadline-Sent $kong_deadline always;
    }
}
EOF

# Test với Nginx edge
docker run -d --name nginx-edge \
  -v $(pwd)/nginx-deadline.conf:/etc/nginx/conf.d/default.conf:ro \
  -p 8888:8888 \
  nginx:1.25-alpine

sleep 3

echo "=== Via Nginx edge (deadline = 25s) ==="
time curl -s -w "\nHTTP: %{http_code}, Time: %{time_total}s\n" \
  http://localhost:8888/api/deadline -m 15

# Cleanup
docker stop nginx-edge && docker rm nginx-edge
```

---

## Exercise 8: Debug Latency bằng Kong Metrics

**Mục tiêu**: Dùng Prometheus metrics để identify latency bottleneck.

### Bước 1: Bật Prometheus metrics

```bash
cat > kong-metrics.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: normal-service
    url: http://normal-backend:3000
    retries: 2
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: normal-route
        paths: ["/api/normal"]
        strip_path: false

  - name: slow-service
    url: http://slow-backend:3001
    retries: 0
    connect_timeout: 2000
    write_timeout: 2000
    read_timeout: 3000
    routes:
      - name: slow-route
        paths: ["/api/slow"]
        strip_path: false

plugins:
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
      upstream_health_metrics: true
EOF

cp kong-metrics.yml kong.yml
curl -X POST http://localhost:8001/config -F config=@kong.yml
sleep 3
```

### Bước 2: Generate traffic và scrape metrics

```bash
# Generate load
for i in {1..20}; do
  curl -s http://localhost:8000/api/normal -m 5 -o /dev/null
  curl -s http://localhost:8000/api/slow   -m 5 -o /dev/null
  sleep 0.5
done

# Fetch Prometheus metrics
curl -s http://localhost:8001/metrics | grep -E \
  "kong_upstream_latency|kong_proxy_latency|service.*latency"
```

### Bước 3: Phân tích latency breakdown

```bash
# Prometheus query (nếu dùng Prometheus container)
# promQL:
#   avg(kong_upstream_latency_ms{service="slow-service"})
#   avg(kong_proxy_latency_ms{service="slow-service"})

# Latency breakdown:
# Total = Proxy latency + Upstream latency
# Proxy latency = Kong Lua/plugin overhead (thường 1-5ms)
# Upstream latency = Backend response time

# Tính latency breakdown từ Kong headers
echo "=== Normal backend latency breakdown ==="
curl -I -s http://localhost:8000/api/normal \
  | grep -i "X-Kong"

# proxy_latency + upstream_latency = total processing time
# Nếu proxy_latency cao bất thường → Lua plugin overhead
# Nếu upstream_latency cao → upstream slow
```

### Bước 4: Identify p99 bottleneck

```bash
# Benchmark để collect latency data
docker run --rm --network host \
  williamyeh/wrk:latest \
  -t 2 -c 20 -d 30s \
  --latency \
  http://localhost:8000/api/normal \
  > /tmp/normal-bench.txt 2>&1 &

docker run --rm --network host \
  williamyeh/wrk:latest \
  -t 2 -c 20 -d 30s \
  --latency \
  http://localhost:8000/api/slow \
  > /tmp/slow-bench.txt 2>&1 &

wait

echo "=== Normal backend benchmark ==="
cat /tmp/normal-bench.txt

echo "=== Slow backend benchmark ==="
cat /tmp/slow-bench.txt

# Latency distribution so sánh:
# Normal: p50 ~100ms, p95 ~150ms, p99 ~200ms
# Slow:   p50 ~5s,   p95 ~5s,   p99 ~5s (vì timeout 5s)
```

---

## Cleanup

```bash
cd ~/kong-resilience-lab

# Dừng tất cả container
docker compose down

# Xóa lab files (optional)
# cd ~ && rm -rf ~/kong-resilience-lab
```

---

## Tổng Kết Exercises

| Exercise | Topic | Key Metric | Fix |
|---|---|---|---|
| 1 | Timeout budget | Response time vs timeout | Kong timeouts = 3000ms |
| 2 | Retry storm | Upstream load × (retries+1) | retries = 0 cho slow service |
| 3 | Exponential backoff | Custom Lua plugin | Backoff ở client layer |
| 4 | Circuit breaker | Passive HC target health | tcp_failures=1 threshold |
| 5 | Backpressure | Latency p99, error rate | Giảm timeout, proxy-cache |
| 6 | Cascading failure | Total time với retries | retries=0, timeout=3s |
| 7 | Deadline propagation | X-Request-Deadline header | Nginx edge propagate |
| 8 | Latency debug | Kong metrics breakdown | X-Kong-Proxy/Upstream-Latency |

---

## Bonus Challenge: Implement Retry Budget Monitoring

```bash
# Tạo script monitor retry rate
cat > monitor-retry-rate.sh << 'BASH'
#!/bin/bash
# Monitor retry rate bằng cách đếm request vs upstream calls

# Parse Kong access log cho retry pattern
# Retry = 2 request cùng request_id trong < 10s window

# Prometheus query (nếu dùng Prometheus)
# retry_rate = rate(gateway_upstream_retry_total[5m]) /
#              rate(kong_http_requests_total[5m])

# Alert threshold: > 15% = retry storm

echo "Checking retry budget..."
ACCESS_LOG=$(docker inspect kong --format '{{.LogPath}}')

if [ -f "$ACCESS_LOG" ]; then
    # Count requests vs retries (rough estimate)
    TOTAL=$(wc -l < "$ACCESS_LOG")
    RETRY_INDICATOR=$(grep -c "retry" "$ACCESS_LOG" 2>/dev/null || echo 0)
    RETRY_RATE=$(echo "scale=2; $RETRY_INDICATOR * 100 / $TOTAL" | bc 2>/dev/null || echo "N/A")
    echo "Approximate retry rate: ${RETRY_RATE}%"
    echo "Threshold: 15% — if higher, reduce retries or check upstream health"
else
    echo "Access log not found at: $ACCESS_LOG"
    echo "Enable: KONG_ACCESS_LOG=/dev/stdout in docker-compose"
fi
BASH

chmod +x monitor-retry-rate.sh
./monitor-retry-rate.sh
```
