# Day 4: Document - Health Check Deep Dive & Error Analysis

> Reference document cho Day 4. Chứa so sánh chi tiết, cause-effect analysis và production patterns.

---

## 1. Active vs Passive Health Check: So sánh toàn diện

### 1.1 Cơ chế hoạt động

#### Passive Health Check

```
Normal flow:
Client → Nginx → Backend (success) → Nginx ghi nhận success

Failure flow:
Client → Nginx → Backend (ECONNREFUSED) → Nginx tăng fail_count
                                         → fail_count >= max_fails?
                                           → Đánh dấu backend UNAVAILABLE
                                           → Không gửi traffic trong fail_timeout
```

**Đặc điểm:**
- Không có probe traffic riêng
- Phát hiện lỗi dựa trên request thực tế
- Có "detection lag": từ khi backend chết đến khi bị đánh dấu down = `max_fails` request thất bại
- Sau `fail_timeout`, Nginx thử 1 request để kiểm tra backend có sống lại chưa

#### Active Health Check (Nginx Plus)

```
Probe flow (chạy độc lập, không phụ thuộc request thực):
Nginx Health Checker → Backend /health endpoint
                     → 200 OK? → passes++
                     → passes >= passes_threshold? → HEALTHY
                     → Non-200? → fails++
                     → fails >= fails_threshold? → UNHEALTHY
```

**Đặc điểm:**
- Probe traffic riêng biệt, không ảnh hưởng request thực
- Phát hiện lỗi trước khi request thực bị ảnh hưởng
- Cần backend có `/health` endpoint
- Tốn thêm tài nguyên (probe requests)

### 1.2 Bảng so sánh chi tiết

| Tiêu chí | Passive | Active (Nginx Plus) | Active (External) |
|---|---|---|---|
| Nginx version | OSS + Plus | Plus only | OSS + Plus |
| Detection lag | max_fails requests | interval * fails | Tùy tool |
| Probe traffic | Không | Có | Có |
| False positive | Có thể | Ít hơn | Tùy config |
| False negative | Không | Không | Không |
| Backend /health endpoint | Không cần | Cần | Cần |
| Config complexity | Thấp | Trung bình | Cao |
| Operational overhead | Thấp | Trung bình | Cao |
| Cost | Miễn phí | Nginx Plus license | Tùy tool |
| Phù hợp với | Hầu hết use case | High-availability API | Microservices + Consul/K8s |

### 1.3 Hybrid Pattern (Production)

Trong thực tế, nhiều hệ thống dùng kết hợp:

```
Nginx OSS (passive) + External Health Checker (Consul/K8s)
                                    ↓
                    Khi backend unhealthy → Remove khỏi DNS/upstream
                    Khi backend healthy → Add lại vào DNS/upstream
                    Nginx reload config tự động (consul-template)
```

Ưu điểm:
- Không cần Nginx Plus
- Health check logic tập trung ở một nơi (Consul/K8s)
- Nginx chỉ cần passive health check làm safety net

---

## 2. Cause-Effect Analysis: 502 / 503 / 504

### 2.1 502 Bad Gateway

**Định nghĩa**: Nginx nhận được response không hợp lệ từ upstream, hoặc không thể thiết lập kết nối.

#### Nguyên nhân và Error Log tương ứng

| Nguyên nhân | Error Log Message | Giải thích |
|---|---|---|
| Backend process chết | `connect() failed (111: Connection refused)` | Port không có process nào listen |
| Backend OOM killed | `recv() failed (104: Connection reset by peer)` | Kernel kill process giữa chừng, TCP reset |
| Backend crash giữa request | `upstream prematurely closed connection` | Backend đóng connection trước khi gửi xong response |
| Backend trả response không hợp lệ | `upstream sent invalid header` | Response không đúng HTTP format |
| Backend trả status 0 | `upstream sent invalid status line` | Response rỗng hoặc không phải HTTP |
| Upstream buffer overflow | `upstream sent too big header` | Response header quá lớn |

#### Phân biệt ECONNREFUSED vs ECONNRESET

```
ECONNREFUSED (111):
- Xảy ra khi TRY KẾT NỐI
- Port không có process nào listen
- Firewall drop packet với RST
- Thường là: backend chưa start, backend crash hoàn toàn

ECONNRESET (104):
- Xảy ra khi ĐÃ CÓ KẾT NỐI, đang đọc/ghi
- Backend gửi TCP RST giữa chừng
- Thường là: OOM killer, backend crash giữa request, keepalive connection bị đóng
```

#### Xử lý 502

```bash
# Bước 1: Xác định backend nào gây lỗi
grep "502" /var/log/nginx/access.log | awk '{print $upstream_addr}' | sort | uniq -c

# Bước 2: Kiểm tra backend process
ssh backend-host "ps aux | grep <service-name>"
ssh backend-host "systemctl status <service-name>"

# Bước 3: Kiểm tra port
ssh backend-host "ss -tlnp | grep <port>"

# Bước 4: Test kết nối trực tiếp từ Nginx host
curl -v http://backend-ip:port/health

# Bước 5: Kiểm tra OOM
ssh backend-host "dmesg | grep -i 'oom\|killed'"
ssh backend-host "journalctl -u <service> | tail -50"
```

### 2.2 503 Service Unavailable

**Định nghĩa**: Nginx không có upstream nào available để gửi request.

#### Nguyên nhân

| Nguyên nhân | Điều kiện | Error Log |
|---|---|---|
| Tất cả backend down | Tất cả server vượt max_fails | `no live upstreams while connecting to upstream` |
| Tất cả backend đánh dấu `down` | Config có `server ... down;` | `no live upstreams while connecting to upstream` |
| Upstream group rỗng | Không có server nào trong upstream | `no servers are inside upstream` |

#### Phân biệt 502 vs 503

```
502: Nginx CÓ upstream để thử, nhưng upstream trả lỗi
503: Nginx KHÔNG CÓ upstream nào để thử
```

#### Xử lý 503

```bash
# Kiểm tra trạng thái upstream (Nginx Plus)
curl http://localhost/api/status | jq '.upstreams'

# Nginx OSS: kiểm tra error log để thấy khi nào backend bị đánh dấu down
grep "upstream" /var/log/nginx/error.log | grep -v "timed out" | tail -20

# Kiểm tra fail_timeout còn hiệu lực không
# Nếu fail_timeout=30s và backend down 5 phút trước → đã hết, Nginx đang thử lại
```

### 2.3 504 Gateway Timeout

**Định nghĩa**: Nginx kết nối được đến upstream nhưng upstream không trả lời trong thời gian quy định.

#### Các timeout liên quan

```nginx
proxy_connect_timeout 5s;   # Thời gian chờ TCP handshake
proxy_send_timeout    60s;  # Thời gian chờ gửi request body (giữa 2 write operations)
proxy_read_timeout    60s;  # Thời gian chờ nhận response (giữa 2 read operations)
```

**Lưu ý quan trọng**: `proxy_read_timeout` không phải là tổng thời gian của toàn bộ response. Đây là thời gian chờ giữa 2 lần đọc dữ liệu. Nếu backend đang stream data, timeout này reset sau mỗi chunk.

#### Nguyên nhân 504

| Nguyên nhân | Dấu hiệu | Xử lý |
|---|---|---|
| DB query chậm | Backend log có slow query | Optimize query, add index |
| GC pause (JVM) | Backend log có GC event | Tune JVM heap, GC settings |
| External API chậm | Backend gọi 3rd party API | Timeout cho external call, circuit breaker |
| CPU throttling | Backend CPU 100% | Scale up/out |
| Memory pressure | Backend swap | Tăng RAM, giảm memory leak |
| Network congestion | High latency giữa Nginx và backend | Kiểm tra network path |

#### Error Log cho 504

```
upstream timed out (110: Connection timed out) while reading response header from upstream
upstream timed out (110: Connection timed out) while sending request to upstream
```

---

## 3. Timeout Budget: Nguyên tắc và Ví dụ

### 3.1 Nguyên tắc cơ bản

```
Client timeout > Edge timeout > Gateway timeout > Upstream timeout > DB timeout
```

**Lý do**: Mỗi layer cần có đủ thời gian để nhận response từ layer bên dưới trước khi layer bên trên timeout.

### 3.2 Ví dụ đúng

```
Mobile app timeout:        30s
  └─ Nginx proxy_read_timeout: 25s
       └─ Kong upstream timeout: 20s
            └─ Order service timeout: 15s
                 └─ PostgreSQL statement_timeout: 10s
```

### 3.3 Ví dụ sai và hậu quả

**Sai lầm 1: Gateway timeout > Client timeout**
```
Client timeout: 10s
Nginx proxy_read_timeout: 60s  ← SAI

Hậu quả:
- Client timeout sau 10s, đóng connection
- Nginx vẫn giữ connection đến backend thêm 50s
- Backend vẫn xử lý request dù client đã bỏ
- Lãng phí: worker connection, backend CPU, DB connection
```

**Sai lầm 2: Tất cả layer cùng timeout**
```
Client timeout: 30s
Nginx timeout: 30s
Backend timeout: 30s
DB timeout: 30s  ← SAI

Hậu quả:
- DB timeout sau 30s → backend nhận exception
- Backend xử lý exception mất thêm vài ms
- Nginx timeout cùng lúc → backend đang gửi error response nhưng Nginx đã đóng connection
- Race condition, khó debug
```

**Sai lầm 3: Timeout quá cao**
```
proxy_read_timeout: 300s  ← SAI cho API thông thường

Hậu quả:
- Slow backend giữ worker connection 5 phút
- 1000 slow requests = 1000 worker connections bị giữ
- worker_connections exhausted → Nginx từ chối request mới
```

### 3.4 Timeout Budget cho các Use Case

| Use Case | Client | Edge Nginx | Gateway | Upstream | DB |
|---|---|---|---|---|---|
| REST API (read) | 10s | 8s | 6s | 4s | 2s |
| REST API (write) | 15s | 12s | 10s | 8s | 5s |
| File upload | 120s | 100s | 90s | 80s | N/A |
| WebSocket | N/A | 3600s | 3600s | 3600s | N/A |
| Background job | N/A | N/A | N/A | 300s | 60s |

---

## 4. Retry Storm: Nguyên nhân và Phòng tránh

### 4.1 Retry Storm là gì?

```
Scenario:
1. Backend A bị chậm (latency tăng từ 50ms lên 2s)
2. Client timeout sau 1s → retry
3. Nginx proxy_next_upstream → retry sang backend B
4. Backend B cũng bị chậm (do shared DB)
5. Client retry thêm lần nữa
6. Tổng load tăng gấp 3-4 lần
7. DB bị overload → tất cả backend chậm hơn
8. Vòng lặp tự khuếch đại
```

### 4.2 Điều kiện gây Retry Storm

```
Retry storm xảy ra khi:
1. Nhiều layer cùng retry (client + gateway + service)
2. Không có retry limit
3. Không có backoff (retry ngay lập tức)
4. Không có circuit breaker
5. Shared resource (DB, cache) bị overload
```

### 4.3 Phòng tránh

**Tại Nginx layer:**
```nginx
# Giới hạn số lần retry
proxy_next_upstream_tries 2;  # Tối đa 2 lần (1 lần đầu + 1 retry)

# Giới hạn tổng thời gian retry
proxy_next_upstream_timeout 10s;

# Chỉ retry với lỗi thực sự, không retry với 5xx (có thể là business error)
proxy_next_upstream error timeout http_502 http_503;
# Không thêm http_500 nếu không chắc chắn
```

**Tại Application layer:**
```
- Exponential backoff với jitter
- Circuit breaker (Hystrix, Resilience4j, Kong circuit breaker plugin)
- Bulkhead pattern (giới hạn concurrent requests đến từng service)
```

**Tại Infrastructure layer:**
```
- Rate limiting tại gateway
- Connection pool limit
- Queue với backpressure
```

---

## 5. Nginx Upstream State Machine

### 5.1 Trạng thái của một upstream server

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
              ┌──────────┐                                    │
              │  ACTIVE  │ ◄── Nhận traffic bình thường       │
              └──────────┘                                    │
                    │                                         │
                    │ fail_count >= max_fails                 │
                    ▼                                         │
           ┌─────────────────┐                               │
           │   UNAVAILABLE   │ ◄── Không nhận traffic        │
           └─────────────────┘                               │
                    │                                         │
                    │ fail_timeout hết                        │
                    ▼                                         │
           ┌─────────────────┐                               │
           │  PROBE (1 req)  │ ◄── Thử 1 request             │
           └─────────────────┘                               │
                    │                                         │
          ┌─────────┴──────────┐                             │
          │ Success            │ Failure                     │
          ▼                    ▼                             │
    ┌──────────┐      ┌─────────────────┐                   │
    │  ACTIVE  │      │   UNAVAILABLE   │ ──────────────────┘
    └──────────┘      └─────────────────┘ (reset fail_timeout)
```

### 5.2 Directives ảnh hưởng đến state

```nginx
upstream backend_pool {
    server backend1:8080;                    # ACTIVE by default
    server backend2:8080 down;              # Forced DOWN (không bao giờ nhận traffic)
    server backend3:8080 backup;            # BACKUP (chỉ active khi tất cả primary down)
    server backend4:8080 max_fails=0;       # Không bao giờ bị đánh dấu UNAVAILABLE
}
```

---

## 6. Nginx Plus vs OSS: Feature Comparison cho Health Check

| Feature | Nginx OSS | Nginx Plus |
|---|---|---|
| Passive health check | Có | Có |
| Active health check | Không | Có |
| Health check URI | N/A | Configurable |
| Health check interval | N/A | Configurable |
| passes/fails threshold | N/A | Configurable |
| Match conditions (status, body, header) | Không | Có |
| Upstream status API | Không | Có (`/api/status`) |
| Dynamic upstream management | Không | Có |
| Slow start | Không | Có |

### Nginx Plus Active Health Check Config

```nginx
# Nginx Plus only
upstream backend_pool {
    zone backend_zone 64k;  # Shared memory zone (bắt buộc cho active health check)
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
}

server {
    location /api/ {
        proxy_pass http://backend_pool;

        health_check
            interval=5s      # Probe mỗi 5s
            fails=2          # 2 lần fail → UNHEALTHY
            passes=3         # 3 lần pass → HEALTHY
            uri=/health      # Endpoint để probe
            match=api_ok;    # Match condition
    }
}

# Match condition
match api_ok {
    status 200;
    header Content-Type ~ "application/json";
    body ~ '"status":"ok"';
}
```

---

## 7. Common Production Patterns

### 7.1 Graceful Shutdown Pattern

Khi deploy backend mới, cần drain traffic trước khi stop:

```bash
# Bước 1: Đánh dấu backend sắp shutdown trong upstream
# (Nginx Plus: dynamic upstream API)
# (Nginx OSS: cần reload config)

# Bước 2: Chờ active connections drain
sleep 30  # Hoặc dùng signal handler trong application

# Bước 3: Stop backend
systemctl stop backend-service
```

**Nginx config cho graceful shutdown:**
```nginx
# Nginx Plus: dùng API để drain
curl -X PATCH http://localhost/api/upstreams/backend_pool/servers/1 \
  -d '{"drain": true}'

# Nginx OSS: đánh dấu down trong config và reload
server backend1:8080 down;
nginx -s reload
```

### 7.2 Canary Deployment với Health Check

```nginx
upstream backend_pool {
    server backend-v1:8080 weight=9;  # 90% traffic
    server backend-v2:8080 weight=1;  # 10% traffic (canary)
}
```

Nếu canary (v2) có error rate cao → passive health check sẽ đánh dấu down → traffic tự động về v1.

### 7.3 Circuit Breaker Pattern với Nginx

Nginx OSS không có circuit breaker tích hợp. Có thể mô phỏng bằng:

```nginx
# Kết hợp max_fails + fail_timeout + proxy_next_upstream
upstream backend_pool {
    server backend1:8080 max_fails=5 fail_timeout=60s;
    # Sau 5 lần fail trong 60s → backend bị "open circuit" trong 60s
}

proxy_next_upstream error timeout http_500 http_502 http_503;
proxy_next_upstream_tries 2;
```

**Hạn chế**: Đây không phải circuit breaker thực sự (không có half-open state tự động). Dùng Kong Gateway hoặc service mesh (Istio/Envoy) nếu cần circuit breaker đầy đủ.

---

## 8. Observability cho Health Check & Failover

### 8.1 Metrics cần theo dõi

| Metric | Ý nghĩa | Alert threshold |
|---|---|---|
| `nginx_upstream_peers_fails` | Số lần fail của từng upstream | > 0 trong 1 phút |
| `nginx_upstream_peers_unavailable` | Số upstream đang unavailable | > 0 |
| `nginx_http_requests_total{status="502"}` | Số 502 | > 1% của total |
| `nginx_http_requests_total{status="503"}` | Số 503 | > 0 |
| `nginx_http_requests_total{status="504"}` | Số 504 | > 0.1% của total |
| `nginx_upstream_response_time` | Latency của upstream | p99 > SLA |

### 8.2 Log Analysis

```bash
# Đếm lỗi theo loại trong 1 giờ qua
awk '$9 ~ /^5/ {print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn

# Tìm upstream nào gây nhiều lỗi nhất
grep "upstream" /var/log/nginx/error.log | \
  grep -oP 'upstream: "http://[^"]*"' | \
  sort | uniq -c | sort -rn | head -10

# Tính p95 upstream response time
awk '{print $NF}' /var/log/nginx/access.log | \
  sort -n | \
  awk 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*0.95)]}'

# Tìm request chậm nhất
sort -k$(awk 'NR==1{for(i=1;i<=NF;i++) if($i=="rt") print i}' /var/log/nginx/access.log) \
  -rn /var/log/nginx/access.log | head -10
```

### 8.3 Access Log Format cho Debug

```nginx
log_format upstream_debug
    '$remote_addr - $remote_user [$time_local] '
    '"$request" $status $body_bytes_sent '
    '"$http_referer" "$http_user_agent" '
    'upstream_addr="$upstream_addr" '
    'upstream_status="$upstream_status" '
    'upstream_response_time="$upstream_response_time" '
    'upstream_connect_time="$upstream_connect_time" '
    'upstream_header_time="$upstream_header_time" '
    'request_time="$request_time"';
```

**Giải thích các biến:**
- `$upstream_addr`: IP:port của upstream đã xử lý request (nhiều giá trị nếu có retry)
- `$upstream_status`: HTTP status từ upstream (nhiều giá trị nếu có retry)
- `$upstream_response_time`: Thời gian từ khi gửi request đến khi nhận xong response
- `$upstream_connect_time`: Thời gian thiết lập TCP connection
- `$upstream_header_time`: Thời gian từ khi gửi request đến khi nhận xong header
- `$request_time`: Tổng thời gian xử lý request (bao gồm cả thời gian đọc request body từ client)
