# Day 03: Document — Load Balancing Algorithms Deep Dive

> Tài liệu tham khảo bổ sung cho Day 03. Đọc sau khi hoàn thành lesson.md và exercises.md.

---

## 1. So sánh chi tiết các Algorithm

### 1.1 Bảng so sánh đầy đủ

| Tiêu chí | round-robin | least_conn | ip_hash | hash $var | hash consistent | random two |
|---|---|---|---|---|---|---|
| **Phân phối** | Đều theo weight | Theo load thực tế | Theo IP | Theo biến | Theo biến (ring) | Gần đều |
| **Stateful** | Không | Không | Pseudo | Theo biến | Theo biến | Không |
| **Cache-friendly** | Không | Không | Không | Có | Rất tốt | Không |
| **Uneven backend** | Kém | Tốt | Kém | Kém | Kém | Tốt |
| **Scale in/out** | Tốt | Tốt | Kém | Kém | Tốt | Tốt |
| **CPU overhead** | Rất thấp | Thấp | Thấp | Thấp-TB | Trung bình | Thấp |
| **Long-lived conn** | Kém | Tốt | Trung bình | Trung bình | Trung bình | Tốt |
| **Nginx OSS** | Có | Có | Có | Có | Có | Có |
| **Nginx Plus** | Có | Có | Có | Có | Có | Có |

### 1.2 Khi nào KHÔNG nên dùng từng algorithm

**round-robin — KHÔNG dùng khi:**
- Backend có response time rất khác nhau (DB-heavy vs cache-only)
- Long-lived connections (WebSocket, gRPC streaming, SSE)
- Backend có capacity khác nhau mà không dùng weight

**least_conn — KHÔNG dùng khi:**
- Backend đang trong quá trình khởi động (0 connections = "rảnh nhất" → nhận burst)
- Không có health check (backend chết có 0 connections → nhận tất cả traffic)
- Request rất ngắn (<1ms) — overhead của shared memory lock có thể đáng kể

**ip_hash — KHÔNG dùng khi:**
- Mobile clients (IP thay đổi thường xuyên)
- Clients sau NAT (nhiều user → 1 IP → 1 backend)
- IPv6 với CGNAT (prefix sharing)
- Cần sticky session thực sự (dùng hash $cookie thay thế)
- Thêm/bớt backend thường xuyên (hash thay đổi)

**hash $variable (không consistent) — KHÔNG dùng khi:**
- Backend là cache server và scale thường xuyên
- Thêm 1 backend → ~(N-1)/N keys bị remapped → cache miss hàng loạt

**hash consistent — KHÔNG dùng khi:**
- Backend không phải cache (overhead không cần thiết)
- Cần phân phối đều tuyệt đối (consistent hashing có thể không đều với ít nodes)

---

## 2. Sticky Session: Các phương pháp và so sánh

### 2.1 Tại sao cần sticky session?

Sticky session (session affinity) đảm bảo request từ cùng một user luôn đến cùng một backend. Cần thiết khi:

- Session lưu in-memory tại backend (legacy app)
- Upload file nhiều phần (multipart upload)
- WebSocket connection cần duy trì state
- Cache warming: user data đã được load vào memory của backend

### 2.2 So sánh các phương pháp sticky session

| Phương pháp | Nginx OSS | Nginx Plus | Độ tin cậy | Khi backend down |
|---|:---:|:---:|---|---|
| ip_hash | Có | Có | Thấp (NAT, mobile) | Session mất |
| hash $cookie | Có | Có | Cao | Session mất |
| sticky cookie | Không | Có | Rất cao | Có thể fallback |
| sticky route | Không | Có | Cao | Có thể fallback |
| sticky learn | Không | Có | Rất cao | Có thể fallback |
| OpenResty lua | Có (custom) | Có | Cao | Tùy implementation |

### 2.3 Implement sticky session bằng hash $cookie (Nginx OSS)

```nginx
upstream backend {
    hash $cookie_session_id consistent;
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
}
```

**Yêu cầu**: Application phải set cookie `session_id` trong response.

**Giới hạn**: Nếu backend down, request vẫn bị route đến backend đó cho đến khi max_fails bị vượt. Sau đó hash thay đổi → session mất.

### 2.4 Workaround với OpenResty (Lua)

```nginx
# Cần OpenResty hoặc nginx-lua module
upstream backend {
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
}

server {
    location / {
        access_by_lua_block {
            local session_id = ngx.var.cookie_session_id
            if session_id then
                -- Lookup session → backend mapping từ Redis
                local redis = require "resty.redis"
                local red = redis:new()
                red:connect("redis", 6379)
                local backend = red:get("session:" .. session_id)
                if backend and backend ~= ngx.null then
                    ngx.var.upstream_backend = backend
                end
            end
        }
        proxy_pass http://backend;
    }
}
```

**Đây là cách Kong và nhiều API Gateway implement sticky session thực sự.**

---

## 3. Consistent Hashing (Ketama Algorithm)

### 3.1 Vấn đề với simple hash

Với 3 backends và hash đơn giản:
```
hash(key) % 3 → backend index
```

Khi thêm backend thứ 4:
```
hash(key) % 4 → backend index khác
```

Kết quả: ~75% keys bị remapped → cache miss hàng loạt.

### 3.2 Consistent Hashing giải quyết như thế nào

```
Hash Ring (0 → 2^32):

         0
         │
    B3───┼───B1
    │    │    │
    │    │    │
    B2───┼───B1
         │
       2^32

Mỗi backend có nhiều "virtual nodes" trên ring.
Key được hash → tìm virtual node gần nhất theo chiều kim đồng hồ.
```

Khi thêm Backend D:
- D chiếm một phần của ring từ các backend khác
- Chỉ ~25% keys bị remapped (thay vì 75%)

### 3.3 Nginx implementation

Nginx dùng Ketama algorithm với 160 virtual nodes mỗi backend (mặc định).

```nginx
upstream cache_backend {
    hash $request_uri consistent;
    server cache1:11211;
    server cache2:11211;
    server cache3:11211;
}
```

**Lưu ý**: Số virtual nodes ảnh hưởng đến độ đều của phân phối. Nginx không expose tham số này trong OSS version.

---

## 4. Power-of-Two Choices (Random Two)

### 4.1 Lý thuyết

Thuật toán "Power of Two Choices" được đề xuất bởi Michael Mitzenmacher (1996):

- Thay vì chọn ngẫu nhiên 1 server (random) → có thể chọn server đang bận
- Thay vì kiểm tra tất cả servers (least_conn) → overhead O(N)
- Chọn ngẫu nhiên 2 servers, rồi chọn cái tốt hơn → overhead O(1), kết quả gần với least_conn

**Kết quả lý thuyết**: Maximum load giảm từ O(log N / log log N) (random) xuống O(log log N) (two choices).

### 4.2 Khi nào dùng random two

```
Pool nhỏ (<5 backends):   → least_conn (overhead không đáng kể)
Pool trung bình (5-20):   → least_conn hoặc random two
Pool lớn (>20 backends):  → random two (giảm coordination overhead)
```

### 4.3 Nginx configuration

```nginx
upstream backend {
    random two least_conn;  # chọn 2 random, lấy least_conn trong 2
    # hoặc
    random two;             # chọn 2 random, lấy random trong 2 (ít dùng)

    server backend1:8080;
    server backend2:8080;
    # ... nhiều backends
}
```

---

## 5. Edge Cases và Behavior đặc biệt

### 5.1 Backend với 0 active connections

**Vấn đề**: Backend mới khởi động hoặc backend vừa recover có 0 active connections → least_conn sẽ gửi tất cả traffic vào đó.

**Giải pháp**:
- Nginx Plus: `slow_start=30s` — tăng dần weight trong 30 giây
- Nginx OSS: Không có slow_start. Workaround: bắt đầu với weight thấp, tăng thủ công sau khi backend warm up

```nginx
# Nginx Plus only
upstream backend {
    least_conn;
    server backend1:8080 slow_start=30s;
    server backend2:8080;
}
```

### 5.2 Tất cả backends down

Khi tất cả backends bị đánh dấu unavailable:
- Nginx trả về 502 Bad Gateway
- Nếu có backup server → traffic chuyển sang backup
- Sau fail_timeout, Nginx thử lại từng backend

```nginx
upstream backend {
    server backend1:8080 max_fails=3 fail_timeout=30s;
    server backend2:8080 max_fails=3 fail_timeout=30s;
    server emergency:8080 backup;  # static error page hoặc maintenance page
}
```

### 5.3 Single backend trong upstream

```nginx
upstream backend {
    server backend1:8080;
    # Chỉ 1 server → không có load balancing
    # Nhưng vẫn có ích: health check, keepalive, retry
}
```

### 5.4 DNS-based upstream

```nginx
resolver 127.0.0.1 valid=30s;

upstream backend {
    server backend.service.consul resolve;  # re-resolve DNS mỗi 30s
}
```

**Lưu ý**: Nginx OSS chỉ resolve DNS khi start/reload. Để dynamic DNS resolution, cần Nginx Plus hoặc dùng `resolver` directive với `resolve` flag (chỉ trong `server` block, không phải `upstream`).

---

## 6. Nginx Plus vs OSS: Tính năng Load Balancing

| Tính năng | Nginx OSS | Nginx Plus |
|---|:---:|:---:|
| round-robin | Có | Có |
| least_conn | Có | Có |
| ip_hash | Có | Có |
| hash $var | Có | Có |
| hash consistent | Có | Có |
| random two | Có | Có |
| least_time | Không | Có |
| sticky cookie | Không | Có |
| sticky route | Không | Có |
| sticky learn | Không | Có |
| slow_start | Không | Có |
| Active health check | Không | Có |
| Dynamic reconfiguration | Không | Có (API) |
| Zone sync | Không | Có |

**least_time** (Nginx Plus only): Chọn backend có response time thấp nhất + ít connections nhất. Tốt hơn least_conn cho latency-sensitive workload.

---

## 7. HAProxy vs Nginx: Load Balancing Algorithm Comparison

| Algorithm | Nginx | HAProxy |
|---|---|---|
| Round-robin | `(default)` | `balance roundrobin` |
| Least connections | `least_conn` | `balance leastconn` |
| IP hash | `ip_hash` | `balance source` |
| URI hash | `hash $uri` | `balance uri` |
| Header hash | `hash $http_x_id` | `balance hdr(x-id)` |
| Random | `random` | `balance random` |
| Consistent hash | `hash $var consistent` | `balance uri whole` (partial) |
| Least response time | Nginx Plus only | `balance first` (khác) |

**HAProxy có thêm:**
- `balance rdp-cookie`: sticky session cho RDP
- `balance url_param`: hash theo URL parameter
- `balance first`: gửi đến server đầu tiên còn capacity

---

## 8. Timeout Budget với Load Balancing

Khi có load balancer, timeout budget phải được tính toán cẩn thận:

```
Client timeout (30s)
  └── Nginx proxy_read_timeout (25s)
        └── Backend processing (20s)
              └── Database query (15s)
```

**Quy tắc**: Mỗi layer phải có timeout ngắn hơn layer trên để tránh connection bị giữ lâu.

**Với retry:**
```
proxy_next_upstream_tries = 2
proxy_next_upstream_timeout = 10s

→ Tổng thời gian tối đa cho retry: 10s
→ Mỗi attempt: tối đa 5s (proxy_read_timeout phải ≥ 5s)
```

**Anti-pattern:**
```nginx
# SAI: retry timeout lớn hơn proxy_read_timeout
proxy_read_timeout 5s;
proxy_next_upstream_timeout 30s;  # vô nghĩa, mỗi attempt chỉ 5s
proxy_next_upstream_tries 10;     # 10 * 5s = 50s > client timeout
```

---

## 9. Monitoring Load Balancing

### 9.1 Metrics quan trọng

```
# Nginx stub_status (cơ bản)
Active connections: 291
server accepts handled requests
 16630948 16630948 31070465
Reading: 6 Writing: 179 Waiting: 106

# Nginx với prometheus-nginx-exporter
nginx_upstream_requests_total{upstream="backend", server="172.x.x.x:8080"}
nginx_upstream_active_connections{upstream="backend"}
nginx_upstream_fails_total{upstream="backend", server="172.x.x.x:8080"}
nginx_upstream_response_time_seconds{upstream="backend", quantile="0.99"}
```

### 9.2 Access log analysis

```bash
# Phân phối request theo upstream server
awk '{print $3}' /var/log/nginx/access.log | sort | uniq -c | sort -rn

# Response time p95 theo upstream
awk '{print $3, $NF}' /var/log/nginx/access.log | \
    sort -k1,1 -k2,2n | \
    awk '{times[$1][NR]=$2; count[$1]++} END {
        for (s in times) {
            n = count[s]
            p95_idx = int(n * 0.95)
            print s, times[s][p95_idx]
        }
    }'

# Số lần fail theo upstream
grep "upstream timed out\|connect() failed\|no live upstreams" \
    /var/log/nginx/error.log | \
    awk '{print $NF}' | sort | uniq -c | sort -rn
```

### 9.3 Log format khuyến nghị cho load balancing

```nginx
log_format lb_detailed
    '$remote_addr '
    '$upstream_addr '           # backend được chọn
    '$upstream_status '         # HTTP status từ backend
    '$upstream_response_time '  # thời gian backend xử lý
    '$request_time '            # tổng thời gian (bao gồm queue)
    '"$request" '
    '$status';

access_log /var/log/nginx/access.log lb_detailed;
```
