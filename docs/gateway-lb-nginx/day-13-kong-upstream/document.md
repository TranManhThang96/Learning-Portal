# Day 13: Reference Document — Kong Upstream Deep Dive

---

## 1. Kong Upstream Entity vs Service Entity

### 1.1 Service.host — Hai Loại Giá Trị

Service entity có field `host` — giá trị này quyết định cách Kong resolve backend:

```
Service.host = DNS name thuần (VD: order-backend.internal)
  → Kong resolve IP khi startup hoặc reload
  → Không có: load balancing, health check, weighted distribution
  → Tương đương: Nginx upstream block với fixed IPs

Service.host = Tên Upstream entity (VD: order-upstream)
  → Kong resolve tên Upstream → ring balancer → chọn target
  → Có: load balancing algorithm, active/passive health check,
    weighted distribution, circuit breaker
```

### 1.2 Named Upstream — "Virtual Load Balancer"

Khi Service trỏ tới Upstream entity, Kong tạo một **virtual load balancer** có tên:

```
# Kong Admin API
Service:  name=order-service
          host=order-upstream     ← tên Upstream entity
          path=/api

Upstream: name=order-upstream    ← logical load balancer name
          algorithm=round-robin
          slots=10000

Target:   target=order-1:8080, weight=100
Target:   target=order-2:8080, weight=100
Target:   target=order-3:8080, weight=0
```

**Service trỏ tới Upstream** giống như Nginx config:

```nginx
# Nginx equivalent
upstream order-upstream {
    server order-1:8080 weight=100;
    server order-2:8080 weight=100;
    server order-3:8080 weight=0;  # drain
}

server {
    location /api/ {
        proxy_pass http://order-upstream;
    }
}
```

### 1.3 Upstream Entity Fields Chi Tiết

```yaml
_format_version: "3.0"
_transform: true

upstreams:
  - name: order-upstream
    slots: 10000                    # số slot trong ring balancer
    algorithm: round-robin          # thuật toán cân bằng tải

    # Hash configuration (khi algorithm = consistent-hashing)
    hash_on: none                   # nguồn giá trị hash
    hash_fallback: none             # fallback khi hash_on không có giá trị
    hash_on_header: X-Session-ID    # header name khi hash_on=header
    hash_fallback_header: X-User-ID # header fallback
    hash_on_cookie: session_id      # cookie name khi hash_on=cookie
    hash_on_cookie_path: /         # cookie path

    # Host header gửi tới upstream target
    host_header: order-upstream     # mặc định = upstream name

    # Health check — chi tiết ở Section 3
    healthchecks:
      active:
        type: http
        http_path: /healthz
        interval: 10
        timeout: 5
        healthy:
          successes: 2
          interval: 10
        unhealthy:
          tcp_failures: 1
          http_failures: 3
          timeouts: 3
      passive:
        type: http
        healthy:
          successes: 2
        unhealthy:
          http_failures: 5
          timeouts: 3
          tcp_failures: 0

    # Client certificate cho mTLS tới upstream
    client_certificate:
```

---

## 2. 5 Load Balancing Algorithm Chi Tiết

### 2.1 Round-Robin

**Cơ chế**: Chọn target tiếp theo theo thứ tự, có tính weight.

```bash
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=round-robin"
```

**So sánh với Nginx SWRR** (Day 3):
- Nginx: Smooth Weighted Round-Robin với upstream tĩnh trong file config
- Kong: Weighted round-robin trên ring balancer in-memory, target/health state thay đổi động qua Admin API hoặc decK

**Khi nào dùng**: Backend đồng nhất về hardware và workload, stateless API.

### 2.2 Consistent Hashing

**Cơ chế**: Hash request value → map lên ring → chọn target "tiếp theo" trên ring.

```bash
# Hash theo Consumer ID (authenticated user)
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=consistent-hashing" \
  -d "hash_on=consumer" \
  -d "hash_fallback=round-robin"

# Hash theo Header X-Session-ID
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=consistent-hashing" \
  -d "hash_on=header" \
  -d "hash_on_header=X-Session-ID" \
  -d "hash_fallback=least-connections"
```

**Consistent Hash Ring — ví dụ với 3 target và 100 slot:**

```
Ring (100 slots, simplified):
  order-1 (w=50):  slots [0-49]
  order-2 (w=30):  slots [50-79]
  order-3 (w=20):  slots [80-99]

Request với hash=65 → slot 65 → order-2

Thêm order-4 (w=50):
  → Chỉ remap ~25% keys thay vì remap ~50% như simple modulo hash
  → Cache hit rate giữ được khi scale out
```

**Virtual nodes/slots**: Kong phân bổ slot theo weight ratio trên ring. `slots` càng lớn thì mapping càng mịn, đặc biệt khi có target weight rất nhỏ.

**Khi nào dùng**: Stateful service (session), cache backend (Redis/Memcached), sticky session bắt buộc.

### 2.3 Least Connections

**Cơ chế**: Chọn target có ít active connections (request đang xử lý) nhất.

```bash
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=least-connections"
```

**Khác với round-robin**: Một target đang xử lý request nặng (DB query 5s) không bị chọn trong khi request nặng đó đang chạy.

**Khi nào dùng**: Backend có response time khác nhau nhiều (ví dụ: mix API nhanh + export job nặng).

### 2.4 Latency (EWMA)

**Cơ chế**: Exponential Weighted Moving Average của latency. Target có latency EWMA thấp nhất được chọn.

```bash
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=latency"
```

**EWMA formula**:

```
EWMA(t) = α × latency_now + (1 - α) × EWMA(t-1)
α = 0.2 (default) — trọng số cho latency gần nhất

Ví dụ:
  EWMA_0 = 10ms (initial)
  Request 1: latency=5ms  → EWMA_1 = 0.2×5 + 0.8×10 = 9ms
  Request 2: latency=50ms → EWMA_2 = 0.2×50 + 0.8×9 = 17.2ms
  Request 3: latency=5ms  → EWMA_3 = 0.2×5 + 0.8×17.2 = 14.76ms
```

**So sánh với Least Connections**:

| Tiêu chí | Least Connections | Latency (EWMA) |
|---|---|---|
| Đo lường | Số lượng request đang xử lý | Thời gian response trung bình |
| Nhạy với slow request | Trung bình | Cao (exponential weight) |
| Phản ánh backend load thực | Gián tiếp | Trực tiếp |
| Complexity | Thấp | Trung bình |

**Khi nào dùng**: Microservices với mixed REST và gRPC, backend có workload không đồng đều.

### 2.5 None (DNS-Based)

**Cơ chế**: Kong không chọn target — DNS resolution tự phân phối (thường qua SRV record).

```bash
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=none"
```

**Use case**: Khi dùng Consul DNS hoặc Kubernetes headless service, DNS trả về nhiều A record với weight.

```
dig SRV order-service.service.consul
# Kết quả:
# order-1.service.consul.  300  IN  SRV 10 100 8080 order-1.service.consul.
# order-2.service.consul.  300  IN  SRV 10 100 8080 order-2.service.consul.
```

**Cảnh báo**: Nếu DNS không hỗ trợ SRV hoặc weight, dùng `algorithm=none` dẫn đến tất cả request đi vào A record đầu tiên.

---

## 3. Hash Inputs Chi Tiết

### 3.1 hash_on Sources

| `hash_on` value | Giá trị hash | Ví dụ |
|---|---|---|
| `none` | Không hash (dùng algorithm) | Default |
| `consumer` | Consumer ID từ auth credential | Consumer authenticated |
| `ip` | Client IP address | `X-Forwarded-For` hoặc direct |
| `header` | Giá trị HTTP header | Dùng với `hash_on_header` |
| `cookie` | Giá trị cookie | Dùng với `hash_on_cookie` |
| `path` | Request path | `/api/v1/orders` |
| `query_arg` | Query parameter | Dùng với `hash_on_query_arg` |

### 3.2 hash_fallback

Khi `hash_on` value không tồn tại (ví dụ: anonymous consumer, header không có), dùng `hash_fallback`:

```bash
# Anonymous user → fallback round-robin
# Authenticated user → hash theo consumer ID
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=consistent-hashing" \
  -d "hash_on=consumer" \
  -d "hash_fallback=round-robin"
```

### 3.3 Hash Input Priority

```
1. hash_on (primary source)
   ↓ (nếu không có giá trị)
2. hash_fallback (fallback algorithm/source)
   ↓ (nếu không có hash_fallback source)
3. round-robin (default)
```

### 3.4 Sticky Session với Consistent Hashing — Ví dụ

```bash
# Step 1: Tạo upstream với session affinity
curl -s -X POST http://localhost:8001/upstreams \
  -d "name=order-upstream" \
  -d "algorithm=consistent-hashing" \
  -d "hash_on=header" \
  -d "hash_on_header=X-Session-ID" \
  -d "hash_fallback=round-robin"

# Step 2: Consumer gọi API với header
curl -H "X-Session-ID: sess-abc123" http://localhost:8000/v1/orders
# → Kong hash "sess-abc123" → slot N → target order-2
# → Tất cả request với X-Session-ID=sess-abc123 → order-2

# Step 3: Anonymous user (không có X-Session-ID)
curl http://localhost:8000/v1/orders
# → hash_fallback=round-robin → distribute đều
```

---

## 4. Ring Balancer Internals — lua-resty-dns-client

### 4.1 Ring Data Structure

Kong dùng **ring balancer** với 10000 slot:

```
┌──────────────────────────────────────────────────────┐
│                    Ring (10000 slots)                  │
├──────────────────────────────────────────────────────┤
│  order-1 (weight=100) → ~2857 slots                  │
│  order-2 (weight=100) → ~2857 slots                  │
│  order-3 (weight=50)  → ~1429 slots                  │
│  order-4 (weight=100) → ~2857 slots                  │
└──────────────────────────────────────────────────────┘

Request flow:
1. New request arrives
2. Balancer chọn target theo algorithm của upstream
3. Với consistent-hashing: hash request → map vào slot trên ring
4. Với round-robin/least-connections/latency: dùng ring và state runtime để chọn target hợp lệ
5. Forward request to that target
```

### 4.2 lua-resty-dns-client Library

Kong dùng `lua-resty-dns-client` thay vì OS resolver:

```lua
-- Kong internal: ngx.balancer
-- Lua code equivalent:
local resolver = require "resty.dns.client"
resolver.init {
    servers = {"127.0.0.11"},  -- Docker DNS
    order = {"SRV", "A", "AAAA", "CNAME"},
    nttl = 30,  -- normal TTL cache
    vttl = 5,   -- negative TTL (error) cache
}

local answers = resolver:resolve("order-1.service.consul")
for _, ans in ipairs(answers) do
    print(ans.target, ans.port, ans.weight, ans.priority)
end
```

**Tại sao không dùng OS resolver?**

- OS resolver: blocking call, không control được TTL
- lua-resty-dns-client: async, respect SRV record weight, custom TTL cache, DNS-over-TCP fallback

### 4.3 DNS Resolution Trong Kong

```
DNS Request Flow (Kong 3.x):

1. Service "order-service" → host="order-upstream"
2. Kong lookup: "order-upstream" → upstream ID → targets[]
3. Mỗi target: resolve hostname → IP + port
4. Cache kết quả theo DNS TTL
5. Ring balancer: slot → target IP
6. Connect TCP → forward request

DNS Cache Behavior:

TTL = 0 (STALE_WHILE_REVALIDATE):
  → Cache ngay, probe DNS background
  → Không block request khi DNS slow
  → Dùng khi backend IP thay đổi thường xuyên

TTL > 0 (BLOCK):
  → Cache theo TTL
  → Request trong TTL dùng cached IP
  → Stale DNS khi backend IP đổi
```

### 4.4 SRV Record — Dynamic Discovery

SRV record chứa: **priority, weight, port, target**

```bash
# Kubernetes headless service SRV record
_docker._tcp.order-service.default.svc.cluster.local.
  SRV 10 50 8080 order-1.order-service.default.svc.cluster.local.
  SRV 10 50 8080 order-2.order-service.default.svc.cluster.local.
  SRV 10 50 8080 order-3.order-service.default.svc.cluster.local.

# Kong đọc SRV weight → phân phối theo weight
# → Kong upstream không cần target entity!
# → algorithm=none + SRV = DNS-based load balancing
```

---

## 5. So Sánh Kong vs HAProxy vs Nginx OSS

### 5.1 Health Check Comparison

| Tiêu chí | Kong Gateway | HAProxy | Nginx OSS |
|---|---|---|---|
| Active health check | Có (HTTP/TCP) | Có (HTTP/TCP/SQL) | Không (cần Plus) |
| Passive health check | Có (circuit breaker) | Có (HTTP/TCP/error count) | Có (max_fails) |
| Probe interval | 1s - 600s (configurable) | 1ms - 60s | N/A |
| Health threshold | Configurable | Configurable | max_fails |
| DNS-based discovery | SRV record | SRV record | resolver directive |
| Upstream slot model | Ring balancer (10000) | Least-conn tree | SWRR array |
| **Algorithm** | round-robin, consistent, EWMA, least-conn | round-robin, least-conn, first, source | round-robin, least_conn, ip_hash, hash, random |

### 5.2 HAProxy Backend Health Check

HAProxy dùng `option httpchk` hoặc `option tcp-check`:

```haproxy
# HAProxy backend health check
backend order-backend
    option httpchk GET /healthz
    http-check expect status 200
    http-check expect string "OK"
    default-server inter 5s fall 3 rise 2

    server order-1 10.0.0.1:8080 check
    server order-2 10.0.0.2:8080 check
    server order-3 10.0.0.3:8080 check
```

**Khác với Kong active health check:**
- HAProxy: chạy trong same process, synchronous probe
- Kong: chạy trong background timer worker, distributed across Kong nodes

### 5.3 Nginx OSS vs Kong — Health Check

Nginx OSS không có active health check (passive only):

```nginx
# Nginx OSS — passive health check
upstream order-backend {
    server order-1:8080 max_fails=3 fail_timeout=30s;
    server order-2:8080 max_fails=3 fail_timeout=30s;
    server order-3:8080 max_fails=3 fail_timeout=30s;
}

# Kong — active + passive health check
# Active: chủ động probe /healthz mỗi 10s
# Passive: count 5xx từ traffic thực → circuit breaker
```

**So sánh detection latency:**

```
Backend die at t=0s:

Nginx OSS passive (max_fails=3, ~1 req/s):
  → Phát hiện t=0-3s (tùy request rate)

Kong active (interval=10s, threshold=3):
  → Phát hiện t=10-30s (probe interval × threshold)

→ Nginx OSS passive phát hiện NHANH HƠN trong high-traffic scenario
→ Kong active phát hiện NHANH HƠN trong low-traffic scenario
```

---

## 6. Retry Strategy Chi Tiết

### 6.1 Kong Retry Behavior

```bash
# Service retries config
curl -s -X POST http://localhost:8001/services \
  -d "name=order-service" \
  -d "retries=3"   # default: 5
```

**Kong retry logic:**

```
Request → target-1 → FAIL (timeout/502/503)
  → Request → target-2 → FAIL
    → Request → target-3 → SUCCESS
      → Response → client

Total attempts: 3 (với retries=3)
```

**Retries không retry:**
- `CONNECT` error (cannot connect)
- `DELETE`, `PATCH`, `PUT`, `POST` body với response error (idempotency concern)
- Request đã gửi partial body

**Retries retry:**
- Timeout (read/write/connect)
- `502 Bad Gateway`, `503 Service Unavailable`
- `504 Gateway Timeout`

### 6.2 Retry Storm — Nguy Cơ Thực

```
Scenario: 3 replicas, 1 replica degrade (latency 5s)

Normal: 1000 RPS → mỗi replica ~333 RPS

Sau khi replica-3 degrade:
  → requests đến replica-3 bị timeout (5s)
  → retries=3 → 3 × 333 = 999 retry attempts
  → 333 × 4 (original + 3 retries) = 1332 RPS thực tế

Kết quả:
  → 2 replicas còn lại nhận 1332 RPS (thay vì 666 RPS)
  → 2 replicas bị overload → timeout → retry storm cascade
```

**Phòng tránh:**
1. Passive health check trip trước khi overload — target unhealthy → không gửi request
2. Retries không quá 3
3. Circuit breaker: nếu error rate > 50%, stop gửi request (không retry)
4. Timeout budget đúng: client timeout < gateway timeout < upstream timeout

---

## 7. Production Health Check Checklist

```bash
# 1. Tạo Upstream với health check đầy đủ
# 2. Verify probe path accessible từ Kong
# 3. Verify threshold phù hợp với traffic pattern
# 4. Verify passive threshold không quá thấp (false positive)
# 5. Verify DNS TTL phù hợp với deployment frequency
# 6. Verify retries không gây retry storm
# 7. Verify timeout budget: client > Kong > upstream > DB
# 8. Verify Prometheus metrics có expose health status
# 9. Verify alerting khi target unhealthy > 5 phút
# 10. Verify rolling deploy với weight=0 drain pattern
```
