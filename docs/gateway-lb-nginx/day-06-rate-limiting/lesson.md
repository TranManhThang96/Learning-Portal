# Day 06: Rate Limiting, Connection Limiting & Basic Protection

> **Thời lượng**: 2 giờ
> **Độ khó**: ⭐⭐⭐
> **Prerequisites**: Day 1 (Reverse Proxy), Day 2 (Nginx Architecture), Day 3 (Load Balancing), Day 4 (Health Check & Failover), Day 5 (TLS/HTTP2)

---

## 1. Learning Objectives

Sau bài này, bạn sẽ có thể:

- Configure `limit_req_zone` + `limit_req` để giới hạn request rate theo leaky bucket algorithm
- Configure `limit_conn_zone` + `limit_conn` để giới hạn concurrent connections
- Phân biệt `burst`, `nodelay`, `delay=N` và chọn đúng theo use case
- Hiểu tại sao rate limit theo `$remote_addr` sai khi đứng sau CDN/Cloud LB và cách fix bằng `set_real_ip_from`
- Thiết kế whitelist/blacklist bằng `geo` + `map`, kết hợp với rate limit để bảo vệ API production

---

## 2. The Problem

> Hôm nay là Black Friday. 9:00 sáng, traffic tăng đột biến gấp 15 lần baseline. Nhưng đó chưa phải vấn đề lớn nhất.
>
> Lúc 9:15, một mobile client bị bug — vòng lặp retry vô hạn, gửi 800 request/giây từ một IP duy nhất vào endpoint `/api/login`. Auth service bắt đầu quá tải. Database connection pool cạn kiệt. Toàn bộ hệ thống chậm lại. Lúc 9:22, service bắt đầu trả 503 cho tất cả user — kể cả những user hoàn toàn bình thường.
>
> Bạn không có rate limiting. Bạn không có connection limiting. Bạn không có gì cả.

**Pain points thực tế:**

- Một IP duy nhất có thể làm cạn kiệt toàn bộ backend capacity
- Brute-force attack vào `/login`, `/forgot-password` không bị chặn
- Không phân biệt được legitimate burst (Black Friday) vs malicious flood
- Rate limit theo `$remote_addr` nhưng tất cả traffic đến từ IP của Cloud LB → blacklist nhầm toàn bộ user
- Shared memory zone đầy khi có hàng triệu IP unique → log lỗi, rate limit không hoạt động

**Hậu quả nếu thiết kế sai:**

- Không có rate limit → một client lỗi làm sập toàn bộ service (noisy neighbor problem)
- Rate limit quá thấp → legitimate burst bị reject, user complain
- Rate limit theo sai key → whitelist nhầm hoặc blacklist nhầm
- Không có `Retry-After` header → client retry ngay lập tức, tạo thêm tải
- Đặt rate limit sau auth → auth service vẫn bị tấn công brute-force

---

## 3. Core Concepts

### 3.1 Rate Limiting là gì?

**Analogy**: Hãy tưởng tượng một quán cà phê có một barista duy nhất. Barista chỉ pha được 10 ly/phút. Nếu 100 khách ùa vào cùng lúc, quán không thể phục vụ tất cả ngay. Có hai cách xử lý:

1. **Leaky bucket**: Có một hàng đợi (queue). Khách xếp hàng, barista phục vụ đều đặn 10 ly/phút. Nếu hàng đợi đầy → khách mới bị từ chối.
2. **Token bucket**: Mỗi phút phát 10 token. Mỗi khách cần 1 token để được phục vụ. Token tích lũy được (đến giới hạn). Burst ngắn được phép nếu còn token dự trữ.

```
Leaky Bucket (Nginx limit_req):
                                    
  Requests ──►  [Queue/Bucket]  ──► Backend (đều đặn)
  (bất kỳ rate)  capacity=burst     rate=N req/s
                                    
  Nếu bucket đầy → 503/429

Token Bucket (Kong rate-limiting plugin):
                                    
  Token refill: N tokens/s          
  ┌─────────────┐                   
  │ ○ ○ ○ ○ ○  │ ← tokens tích lũy (max=burst_size)
  └─────────────┘                   
  Mỗi request tiêu 1 token          
  Hết token → 429                   
```

### 3.2 Các thuật toán Rate Limiting

| Thuật toán | Cách hoạt động | Nginx hỗ trợ? | Đặc điểm |
|---|---|---|---|
| **Leaky bucket** | Queue request, xử lý đều đặn | Có (`limit_req`) | Smooth output, burst bị delay |
| **Token bucket** | Tích lũy token, tiêu khi request | Không native (Kong) | Cho phép burst ngắn |
| **Fixed window** | Đếm request trong window cố định | Không native | Đơn giản, có boundary spike |
| **Sliding window** | Window trượt theo thời gian thực | Không native (Redis) | Chính xác nhất, tốn memory |

**Nginx dùng leaky bucket** cho `limit_req`. Điều này có nghĩa:
- Request đến nhanh hơn rate → vào queue (nếu còn chỗ trong `burst`)
- Queue đầy → reject ngay (503 hoặc 429)
- Request trong queue được xử lý đều đặn theo `rate`

### 3.3 Request Flow với Rate Limiting

```
                    ┌─────────────────────────────────────────┐
                    │              Nginx Worker                │
                    │                                          │
  Client Request ──►│  1. Lookup key trong shared memory zone  │
                    │     (vd: $binary_remote_addr)            │
                    │                                          │
                    │  2. Tính excess = current_rate - allowed │
                    │                                          │
                    │  3a. excess <= 0 → PASS ngay             │
                    │  3b. 0 < excess <= burst → QUEUE/DELAY   │
                    │  3c. excess > burst → REJECT (503/429)   │
                    │                                          │
                    │  4. Update counter trong shared zone     │
                    └─────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Backend Service  │
                    └───────────────────┘
```

### 3.4 limit_req_zone và limit_req

```nginx
# Khai báo zone trong http block
http {
    # Syntax: limit_req_zone key zone=name:size rate=N;
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    #              ^^^^^^^^^^^^^^^^^^^       ^^^^^^^^^^^ ^^^  ^^^^^^
    #              key (per IP)              zone name   size  rate
    
    # 10m = 10 megabytes shared memory
    # 1m ≈ 16,000 entries với $binary_remote_addr (4 bytes IPv4)
    # rate=10r/s = 10 requests per second = 1 request mỗi 100ms
    # rate=60r/m = 60 requests per minute = 1 request mỗi giây
}

server {
    location /api/ {
        # Syntax: limit_req zone=name [burst=N] [nodelay|delay=N];
        limit_req zone=api_limit burst=20 nodelay;
        #                        ^^^^^^^^ ^^^^^^^
        #                        queue 20 xử lý ngay (không delay)
        
        limit_req_status 429;        # trả 429 thay vì 503 mặc định
        limit_req_log_level warn;    # log level: info|notice|warn|error
        
        proxy_pass http://backend;
    }
}
```

**Giải thích tham số `burst` và behavior:**

```
rate=10r/s, burst=20:

Scenario A: burst=20 (không nodelay)
  t=0: 30 requests đến cùng lúc
  → 10 request đầu: PASS ngay
  → 20 request tiếp: vào queue, xử lý dần (mỗi 100ms 1 request)
  → Tổng thời gian queue: 20 * 100ms = 2 giây
  → 0 request bị reject (nếu không có thêm request mới)

Scenario B: burst=20 nodelay
  t=0: 30 requests đến cùng lúc
  → 30 request đầu: PASS ngay (không delay)
  → Counter tăng lên 30
  → Các request tiếp theo trong 2 giây tới: bị reject
  → Sau 2 giây: counter drain về 0, lại accept request

Scenario C: burst=20 delay=5
  t=0: 30 requests đến cùng lúc
  → 5 request đầu: PASS ngay (delay=5)
  → 15 request tiếp: vào queue, bị delay
  → 10 request cuối: REJECT (vượt burst=20)
```

### 3.5 limit_conn_zone và limit_conn

`limit_conn` giới hạn số **concurrent connections** (kết nối đồng thời), khác với `limit_req` giới hạn **request rate**.

```nginx
http {
    # Zone cho connection limiting
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    
    server {
        location /api/ {
            limit_conn conn_limit 20;    # tối đa 20 concurrent connections per IP
            limit_conn_status 429;
            limit_conn_log_level warn;
            
            proxy_pass http://backend;
        }
    }
}
```

**Khi nào dùng limit_conn vs limit_req:**

- `limit_req`: giới hạn tốc độ request (req/s). Phù hợp cho API endpoint, login form.
- `limit_conn`: giới hạn số connection đồng thời. Phù hợp cho download endpoint, WebSocket, Slowloris protection.
- Dùng cả hai cùng nhau cho bảo vệ toàn diện.

### 3.6 Key Selection — Limit theo gì?

```nginx
http {
    # Per IP (phổ biến nhất)
    limit_req_zone $binary_remote_addr zone=per_ip:10m rate=10r/s;
    
    # Per API Key (header)
    limit_req_zone $http_x_api_key zone=per_apikey:10m rate=100r/s;
    
    # Per server name (virtual host)
    limit_req_zone $server_name zone=per_vhost:10m rate=1000r/s;
    
    # Per URI (giới hạn từng endpoint)
    limit_req_zone $request_uri zone=per_uri:10m rate=5r/s;
    
    # Kết hợp IP + URI (granular nhất)
    limit_req_zone "$binary_remote_addr$request_uri" zone=per_ip_uri:20m rate=5r/s;
}
```

**Lưu ý quan trọng về `$binary_remote_addr` vs `$remote_addr`:**
- `$remote_addr`: string IP, tốn nhiều memory hơn (7-15 bytes)
- `$binary_remote_addr`: binary IP, 4 bytes (IPv4) hoặc 16 bytes (IPv6) — **luôn dùng cái này**

---

## 4. How It Works Internally

### 4.1 Shared Memory Zone

Nginx dùng shared memory để các worker process chia sẻ counter rate limiting. Nếu không có shared memory, mỗi worker có counter riêng → rate limit không chính xác (N workers × rate = actual rate).

```
Nginx Master Process
├── Worker 1 ──┐
├── Worker 2 ──┼──► Shared Memory Zone (mmap)
├── Worker 3 ──┤    ┌─────────────────────────────┐
└── Worker 4 ──┘    │  Red-Black Tree (sorted)     │
                    │  Key: $binary_remote_addr     │
                    │  Value: {last_time, excess}   │
                    │                               │
                    │  192.168.1.1 → {t=100, e=5}  │
                    │  10.0.0.1    → {t=99,  e=0}  │
                    │  ...                          │
                    └─────────────────────────────┘
                    Mutex lock khi read/write
```

**Memory calculation:**
- `1m` (1 megabyte) ≈ 16,000 entries với `$binary_remote_addr`
- Mỗi entry: ~64 bytes (key + metadata + red-black tree node)
- `10m` ≈ 160,000 entries — đủ cho hầu hết production workload
- Khi zone đầy: Nginx dùng LRU để xóa entry cũ nhất

**Khi zone đầy, Nginx log:**
```
2024/01/15 10:23:45 [error] 1234#0: *5678 limiting requests, excess: 1.000 by zone "api_limit", client: 1.2.3.4, ...
```

### 4.2 Leaky Bucket Implementation

Nginx không dùng queue thực sự. Thay vào đó, nó dùng **virtual queue** bằng cách tính toán:

```
excess = max(0, last_excess - (now - last_time) * rate) + 1

Nếu excess > burst → reject
Nếu excess > 0 và không có nodelay → delay = excess / rate
Nếu nodelay → pass ngay, chỉ update counter
```

Đây là cách implement hiệu quả: không cần lưu queue thực, chỉ cần 2 giá trị `{last_time, excess}` per key.

### 4.3 Real IP khi đứng sau CDN/Cloud LB

**Vấn đề nghiêm trọng**: Khi Nginx đứng sau Cloud Load Balancer hoặc CDN (Cloudflare, AWS ALB, GCP LB), `$remote_addr` sẽ là IP của LB, không phải IP của client thực.

```
Client (1.2.3.4) ──► CDN/LB (10.0.0.1) ──► Nginx
                                              $remote_addr = 10.0.0.1  ← SAI!
                                              X-Forwarded-For: 1.2.3.4
```

Nếu rate limit theo `$remote_addr`, tất cả traffic đều có cùng key `10.0.0.1` → rate limit áp dụng cho toàn bộ user, không phải per-user.

**Fix bằng `real_ip` module:**

```nginx
http {
    # Khai báo IP của trusted proxy (CDN/LB)
    set_real_ip_from 10.0.0.0/8;        # internal LB
    set_real_ip_from 172.16.0.0/12;     # Docker network
    set_real_ip_from 103.21.244.0/22;   # Cloudflare IP range (ví dụ)
    
    real_ip_header X-Forwarded-For;     # hoặc X-Real-IP
    real_ip_recursive on;               # bỏ qua các IP trusted trong chain
    
    # Sau khi set, $remote_addr = IP thực của client
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
}
```

**Cảnh báo bảo mật**: Chỉ trust IP của proxy bạn kiểm soát. Nếu trust quá rộng, attacker có thể spoof `X-Forwarded-For` để bypass rate limit.

### 4.4 Bandwidth Throttling với limit_rate

```nginx
location /download/ {
    limit_rate 1m;           # 1 MB/s per connection
    limit_rate_after 10m;    # throttle sau khi đã gửi 10MB đầu tiên
    
    # Kết hợp với limit_conn để giới hạn tổng bandwidth
    limit_conn_zone $binary_remote_addr zone=download_conn:10m;
    limit_conn download_conn 3;   # tối đa 3 concurrent downloads per IP
}
```

### 4.5 Bảo vệ cơ bản với client limits

```nginx
http {
    # Giới hạn request body size (chống upload bomb)
    client_max_body_size 10m;        # mặc định 1m, 0 = unlimited
    client_body_timeout 30s;         # timeout đọc body (chống Slowloris)
    client_header_timeout 10s;       # timeout đọc header
    
    # Buffer size cho header lớn (JWT token, cookie)
    large_client_header_buffers 4 16k;
    
    # Keepalive timeout
    keepalive_timeout 65s;
    keepalive_requests 1000;
}
```

### 4.6 Geo + Map để Whitelist/Blacklist

```nginx
http {
    # Geo block: map IP → variable
    geo $limit_key {
        default         $binary_remote_addr;  # mặc định: limit theo IP
        127.0.0.1       "";                   # localhost: không limit
        10.0.0.0/8      "";                   # internal network: không limit
    }
    
    # Dùng $limit_key làm key cho zone
    # Khi $limit_key = "" → Nginx không track → không bị limit
    limit_req_zone $limit_key zone=api_limit:10m rate=10r/s;
    
    # Blacklist bằng map
    geo $blocked_ip {
        default         0;
        1.2.3.4         1;    # block IP cụ thể
        5.6.7.0/24      1;    # block subnet
    }
    
    server {
        location /api/ {
            if ($blocked_ip) {
                return 403 "Forbidden";
            }
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://backend;
        }
    }
}
```

---

## 5. Hands-on Lab

### Chuẩn bị môi trường

```bash
# Tạo cấu trúc thư mục
mkdir -p lab-day06/{nginx/conf.d,backend,logs}
cd lab-day06
```

### 5.1 Docker Compose Setup

**`lab-day06/docker-compose.yml`:**

```yaml
version: "3.8"

services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./logs:/var/log/nginx
    depends_on:
      - backend
    networks:
      - lab

  backend:
    image: python:3.11-alpine
    command: python /app/app.py
    volumes:
      - ./backend:/app:ro
    networks:
      - lab

networks:
  lab:
    driver: bridge
```

**`lab-day06/backend/app.py`:**

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time


class Handler(BaseHTTPRequestHandler):
    def _write_json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/download"):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            for _ in range(20):
                self.wfile.write(b"x" * 1024)
                self.wfile.flush()
                time.sleep(0.25)
            return
        self._write_json({"service": "rate-limit-lab", "path": self.path})

    def do_POST(self):
        self._write_json({"service": "rate-limit-lab", "path": self.path, "method": "POST"})

    def log_message(self, fmt, *args):
        return


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
```

**`lab-day06/nginx/nginx.conf`:**

```nginx
user  nginx;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" rt=$request_time';

    access_log  /var/log/nginx/access.log  main;
    sendfile        on;
    keepalive_timeout  65;

    include /etc/nginx/conf.d/*.conf;
}
```

**`lab-day06/nginx/conf.d/rate-limit.conf`:**

```nginx
# Zone definitions (phải ở http block, đặt trong conf.d sẽ được include vào http block)
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# Geo whitelist
geo $limit_key {
    default         $binary_remote_addr;
    127.0.0.1       "";
    10.0.0.0/8      "";   # internal network production example
}
limit_req_zone $limit_key zone=geo_limit:10m rate=10r/s;

server {
    listen 80;
    server_name localhost;

    # Endpoint thông thường: 10 req/s, burst 20
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;
        limit_req_log_level warn;

        add_header X-RateLimit-Zone "api_limit" always;
        proxy_pass http://backend/;
        proxy_set_header Host $host;
    }

    # Login endpoint: 5 req/phút (brute-force protection)
    location /api/login {
        limit_req zone=login_limit burst=3 nodelay;
        limit_req_status 429;

        add_header Retry-After 60 always;
        proxy_pass http://backend/;
        proxy_set_header Host $host;
    }

    # Connection limit: tối đa 5 concurrent connections per IP
    location /download/ {
        limit_conn conn_limit 5;
        limit_conn_status 429;
        limit_rate 512k;
        limit_rate_after 1m;

        proxy_pass http://backend;
    }

    # Geo whitelist: loopback/internal allowlist không bị limit
    location /internal/ {
        limit_req zone=geo_limit burst=100 nodelay;
        limit_req_status 429;

        proxy_pass http://backend/;
    }
}
```

### 5.2 Khởi động Lab

```bash
cd lab-day06
docker compose up -d

# Kiểm tra Nginx đã chạy
curl -s http://localhost:8080/api/
# Output: JSON từ backend app
```

### 5.3 Lab A: Test Rate Limiting cơ bản

```bash
# Test 1: Gửi 5 request liên tiếp (dưới rate limit)
for i in $(seq 1 5); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/)
  echo "Request $i: $STATUS"
done
# Kết quả mong đợi: tất cả 200

# Test 2: Gửi 30 request cùng lúc (vượt burst=20)
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" http://localhost:8080/api/ &
done
wait
# Kết quả mong đợi: ~20-21 request 200, ~9-10 request 429

# Xem log Nginx
docker compose logs nginx | grep "limiting requests"
# Output: [warn] limiting requests, excess: X.XXX by zone "api_limit"
```

### 5.4 Lab B: So sánh burst vs nodelay vs delay

Thay đổi config để test từng mode:

```bash
# Mode 1: burst=20 (có delay, không nodelay)
# Sửa location /api/ trong conf.d/rate-limit.conf:
#   limit_req zone=api_limit burst=20;   # bỏ nodelay

# Restart và test
docker compose restart nginx

# Gửi 25 request và đo thời gian
time for i in $(seq 1 25); do
  curl -s -o /dev/null http://localhost:8080/api/
done
# Kết quả: ~2.5 giây (25 requests / 10 req/s)
# 10 request đầu: ngay lập tức
# 15 request tiếp: delay 100ms mỗi cái

# Mode 2: burst=20 nodelay
# Sửa: limit_req zone=api_limit burst=20 nodelay;
docker compose restart nginx

time for i in $(seq 1 25); do
  curl -s -o /dev/null http://localhost:8080/api/
done
# Kết quả: ~0.1 giây (tất cả pass ngay)
# Nhưng nếu gửi thêm request trong 2 giây tiếp theo → 429
```

### 5.5 Lab C: Login Brute-Force Protection

```bash
# Login endpoint: 5 req/phút = 1 request mỗi 12 giây
# burst=3 → tối đa 3 request burst

# Test brute-force simulation
for i in $(seq 1 10); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8080/api/login \
    -d "user=admin&pass=test$i")
  echo "Attempt $i: $STATUS"
done
# Kết quả mong đợi:
# Attempt 1-3: 200 (burst=3)
# Attempt 4-10: 429 (rate limit)

# Kiểm tra Retry-After header
curl -v http://localhost:8080/api/login 2>&1 | grep -i "retry-after"
# Output: < Retry-After: 60
```

### 5.6 Lab D: Connection Limiting (Slowloris Protection)

```bash
# Cài ab (Apache Benchmark) hoặc dùng curl parallel
# Test với nhiều concurrent connections

# Dùng curl parallel để mở 10 connections đồng thời
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "Conn $i: %{http_code}\n" \
    --max-time 30 http://localhost:8080/download/ &
done
wait
# Kết quả: 5 connections đầu: 200, 5 connections sau: 429

# Nếu có ab:
ab -n 100 -c 20 http://localhost:8080/download/
# Xem "Non-2xx responses" trong output
```

### 5.7 Lab E: Geo Whitelist

```bash
# Request loopback bên trong Nginx container không bị limit
# vì remote_addr = 127.0.0.1 khớp geo whitelist

docker compose exec nginx sh -c \
  'for i in $(seq 1 50); do wget -q -O /dev/null http://127.0.0.1/internal/ && echo "OK" || echo "FAIL"; done'
# Kết quả: tất cả OK (không bị rate limit vì 127.0.0.1 trong whitelist)

# Request từ host vào localhost:8080 đi qua Docker bridge, thường vẫn bị limit.
# Đây là điểm cần phân biệt với loopback 127.0.0.1 bên trong container.
for i in $(seq 1 50); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/internal/
done
# Kết quả: sẽ có 429 nếu Docker bridge IP không nằm trong whitelist
```

### 5.8 Lab F: Custom Status Code và Headers

```bash
# Thêm Retry-After header cho rate limited response
# Sửa nginx/conf.d/rate-limit.conf, thêm vào location /api/:

# limit_req_status 429;
# add_header Retry-After 10 always;

docker compose restart nginx

# Test và xem headers
curl -v http://localhost:8080/api/ 2>&1 | grep -E "(HTTP|Retry|X-Rate)"
# Khi bị rate limit:
# < HTTP/1.1 429 Too Many Requests
# < Retry-After: 10
# < X-RateLimit-Zone: api_limit
```

### Lỗi thường gặp trong Lab

**1. "unknown directive limit_req_zone" khi start Nginx:**
```bash
# Nguyên nhân: limit_req_zone phải ở trong http block
# Nếu đặt trong server block → lỗi
# Fix: đảm bảo conf.d được include trong http block của nginx.conf
```

**2. Rate limit không có hiệu lực:**
```bash
# Kiểm tra zone name khớp giữa limit_req_zone và limit_req
# limit_req_zone ... zone=api_limit:10m ...
# limit_req zone=api_limit ...  ← phải khớp

# Kiểm tra key: nếu $limit_key = "" (geo whitelist) → không bị limit
docker compose exec nginx nginx -t
```

**3. Tất cả request đều bị 429:**
```bash
# Nguyên nhân: rate quá thấp hoặc burst quá nhỏ
# Kiểm tra: rate=10r/s với burst=20 → 30 request đầu pass, sau đó 10/s
# Nếu test script gửi nhanh hơn → tăng burst hoặc rate
```

---

### 5.9 Failure Scenarios

#### 5.9.1 Burst Legitimate Traffic bị Reject

**Scenario**: Black Friday, traffic tăng đột biến 10x. Rate limit `10r/s burst=20` quá thấp.

```
Baseline: 5 req/s per IP
Black Friday: 50 req/s per IP (10x)
Rate limit: 10r/s burst=20

Kết quả: 30 request đầu pass, sau đó 40 req/s bị reject → 80% request 429
```

**Fix**: Tăng rate và burst trước event, hoặc dùng `geo` để whitelist IP của mobile app.

#### 5.9.2 Rate Limit theo $remote_addr khi có CDN

```
Client A (1.2.3.4) ──►┐
Client B (5.6.7.8) ──►├──► CDN (10.0.0.1) ──► Nginx
Client C (9.10.11.12)─►┘                        $remote_addr = 10.0.0.1

Rate limit: 10r/s per $remote_addr
→ Tất cả client chia sẻ 1 counter
→ 10 request/s cho toàn bộ user → service bị throttle nặng
```

**Fix**: Dùng `set_real_ip_from` + `real_ip_header X-Forwarded-For`.

#### 5.9.3 Shared Memory Zone Đầy

```bash
# Khi zone đầy, Nginx log:
[error] limiting requests, excess: 1.000 by zone "api_limit", ...

# Và có thể reject request hợp lệ
# Fix: tăng zone size
limit_req_zone $binary_remote_addr zone=api_limit:50m rate=10r/s;
#                                                 ^^^
#                                                 tăng từ 10m lên 50m
```

#### 5.9.4 DDoS từ Nhiều IP

```
Attacker: 10,000 IP, mỗi IP gửi 1 req/s
Rate limit per IP: 10r/s → không có IP nào bị limit
Tổng traffic: 10,000 req/s → backend quá tải

limit_req không hiệu quả cho distributed attack
→ Cần: fail2ban, Cloudflare, AWS Shield, WAF
```

#### 5.9.5 Slowloris Attack

```
Attacker mở nhiều connection, gửi header rất chậm (1 byte/giây)
→ Nginx giữ connection mở, chờ header hoàn chỉnh
→ Worker connections cạn kiệt

Fix:
limit_conn conn_limit 10;        # giới hạn concurrent connections
client_header_timeout 10s;       # timeout nếu header không đến trong 10s
client_body_timeout 30s;         # timeout nếu body không đến trong 30s
```

---

## 6. Trade-offs Analysis

### 6.1 So sánh các phương pháp Rate Limiting

| Phương pháp | Granularity | Distributed? | Overhead | Use Case |
|---|---|---|---|---|
| `limit_req` (Nginx) | Per IP/key | Không (per instance) | Rất thấp | API protection, brute-force |
| `limit_conn` (Nginx) | Per IP | Không (per instance) | Rất thấp | Slowloris, download throttle |
| Application-level | Per user/session | Có (nếu dùng Redis) | Trung bình | Business logic rate limit |
| Kong rate-limiting | Per consumer/route | Có (Redis/cluster) | Thấp | Enterprise API gateway |
| WAF/CDN rate limit | Per IP/geo | Có (edge) | Không (offload) | DDoS, volumetric attack |

### 6.2 Nginx OSS vs Kong Rate Limiting

| Tiêu chí | Nginx OSS `limit_req` | Kong rate-limiting plugin |
|---|---|---|
| **Algorithm** | Leaky bucket | Token bucket (configurable) |
| **Distributed** | Không (per instance) | Có (Redis backend) |
| **Granularity** | IP, header, URI | Consumer, route, service, global |
| **Config** | Static (reload cần) | Dynamic (Admin API) |
| **Headers** | Thủ công | Tự động (`X-RateLimit-*`) |
| **Monitoring** | Log parsing | Prometheus metrics |
| **Cost** | Free | Free (OSS) / Enterprise |
| **Phù hợp** | Simple protection | Enterprise API management |

### 6.3 Khi nào dùng gì?

```
Nginx OSS limit_req:
  ✓ Bảo vệ cơ bản per-IP
  ✓ Brute-force protection cho login
  ✓ Không cần distributed (single instance hoặc chấp nhận per-instance limit)
  ✗ Không có distributed rate limit
  ✗ Không có dynamic config

Kong rate-limiting:
  ✓ Multi-instance deployment cần consistent rate limit
  ✓ Rate limit theo consumer (authenticated user)
  ✓ Cần thay đổi config không cần reload
  ✗ Cần Redis (thêm dependency)
  ✗ Phức tạp hơn để setup

Application-level (Redis):
  ✓ Business logic phức tạp (vd: free tier 100 req/day, paid 10000 req/day)
  ✓ Rate limit theo user account, không phải IP
  ✗ Tốn công implement
  ✗ Không bảo vệ được trước khi request vào app
```

---

## 7. Best Practices & Best Solution

### 7.1 Nguyên tắc thiết kế

**1. Đặt rate limit trước auth, không phải sau:**
```nginx
# ĐÚNG: rate limit → auth → business logic
location /api/login {
    limit_req zone=login_limit burst=3 nodelay;  # ← trước
    proxy_pass http://auth_service;
}

# SAI: auth service bị tấn công brute-force trước khi rate limit
```

**2. Không dùng rate limit thay cho auth:**
Rate limit là lớp bảo vệ bổ sung, không phải thay thế authentication. Attacker có thể dùng nhiều IP để bypass per-IP rate limit.

**3. Định lượng dựa trên baseline, không pick số bừa:**
```bash
# Đo baseline traffic trước
# p99 request rate per IP trong giờ cao điểm = X req/s
# Rate limit = 2-3x baseline để có headroom
# Burst = 5-10x rate để handle legitimate spike
```

**4. Luôn set Retry-After header:**
```nginx
limit_req_status 429;
add_header Retry-After 10 always;  # "always" để thêm cả khi 4xx/5xx
```

**5. Log request bị reject để analyze:**
```nginx
limit_req_log_level warn;  # default là error, warn ít noise hơn
# Sau đó: grep "limiting requests" /var/log/nginx/error.log | awk '{print $NF}' | sort | uniq -c | sort -rn
```

### 7.2 Production Config Template

```nginx
http {
    # Zones
    limit_req_zone $binary_remote_addr zone=global:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=api:10m    rate=20r/s;
    limit_req_zone $binary_remote_addr zone=login:10m  rate=5r/m;
    limit_conn_zone $binary_remote_addr zone=conn:10m;

    # Real IP (khi đứng sau LB/CDN)
    set_real_ip_from 10.0.0.0/8;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;

    # Geo whitelist
    geo $limit_key {
        default        $binary_remote_addr;
        127.0.0.1      "";
        10.0.0.0/8     "";
    }
    limit_req_zone $limit_key zone=api_geo:10m rate=20r/s;

    # Client protection
    client_max_body_size 10m;
    client_body_timeout 30s;
    client_header_timeout 10s;
    large_client_header_buffers 4 16k;

    server {
        # Global rate limit
        limit_req zone=global burst=200 nodelay;
        limit_conn conn 100;

        location /api/ {
            limit_req zone=api_geo burst=50 nodelay;
            limit_req_status 429;
            limit_req_log_level warn;
            add_header Retry-After 5 always;
            proxy_pass http://backend;
        }

        location /api/auth/login {
            limit_req zone=login burst=5 nodelay;
            limit_req_status 429;
            add_header Retry-After 60 always;
            proxy_pass http://auth_service;
        }
    }
}
```

### 7.3 Anti-patterns cần tránh

```nginx
# ANTI-PATTERN 1: limit theo $remote_addr mà không set real_ip
limit_req_zone $remote_addr zone=bad:10m rate=10r/s;  # SAI khi có CDN

# ANTI-PATTERN 2: rate quá thấp không có burst
limit_req zone=api;  # không có burst → mọi spike đều bị reject

# ANTI-PATTERN 3: zone size quá nhỏ
limit_req_zone $binary_remote_addr zone=tiny:1k rate=10r/s;  # 1k = ~16 entries!

# ANTI-PATTERN 4: không có Retry-After header
limit_req_status 429;
# Thiếu: add_header Retry-After ...
# → Client retry ngay lập tức → tạo thêm tải
```

---

## 8. Performance Considerations

### 8.1 Memory Overhead

```
Zone size calculation:
- $binary_remote_addr: 4 bytes (IPv4) + ~60 bytes overhead = ~64 bytes/entry
- 1m zone ≈ 1,048,576 / 64 ≈ 16,384 entries
- 10m zone ≈ 163,840 entries
- 100m zone ≈ 1,638,400 entries

Recommendation:
- Small site (<10k unique IP/hour): 10m
- Medium site (<100k unique IP/hour): 50m
- Large site (>100k unique IP/hour): 100m+
```

### 8.2 Benchmark Methodology và Latency Overhead

Rate limiting trong Nginx thêm rất ít latency:
- Shared memory lookup: ~1-5 microseconds (mutex lock + red-black tree lookup)
- Không có network call (khác với Redis-based distributed rate limit)
- Overhead thực tế: < 0.1ms trong hầu hết trường hợp

**Benchmark methodology** (theo template của khóa học):

```
Tool: wrk
CPU: 4 vCPU
RAM: 8GB
Payload: 1KB JSON response
Duration: 30s
Connections: 100
Threads: 4
TLS: Off
Keepalive: On
Rate limit mode: baseline vs limit_req với burst đủ lớn để không reject
Metrics bắt buộc ghi lại: requests/sec, p50, p95, p99, error rate, CPU usage
```

> Lưu ý: số liệu chỉ dùng để tham khảo. Kết quả thực tế phụ thuộc vào hardware, kernel, Docker networking, payload size, keepalive, logging và số lượng unique keys trong shared memory zone.

```bash
# Baseline (không có rate limit)
wrk -t4 -c100 -d30s http://localhost:8080/api/

# Với rate limit (burst đủ lớn để không reject)
wrk -t4 -c100 -d30s http://localhost:8080/api/

# So sánh p50/p95/p99 latency và Non-2xx responses
```

### 8.3 Lock Contention

Với nhiều Nginx worker, shared memory zone dùng mutex lock. Khi traffic cao:
- Nhiều worker cùng update zone → lock contention
- Giải pháp: tăng `worker_processes` không giúp nhiều nếu zone là bottleneck
- Nginx dùng spinlock (không sleep) → CPU usage tăng khi contention cao
- Thực tế: chỉ là vấn đề ở >100k req/s trên single server

---

## 9. Troubleshooting Checklist

### 9.1 "limiting requests" trong error.log

```bash
# Xem log
docker compose logs nginx 2>&1 | grep "limiting requests"
# [warn] 1234#0: *5678 limiting requests, excess: 1.500 by zone "api_limit",
#        client: 1.2.3.4, server: localhost, request: "GET /api/ HTTP/1.1"

# Phân tích: excess = số request vượt quá rate
# excess: 1.5 → vượt 1.5 request so với rate cho phép
# Nếu excess > burst → request bị reject
```

### 9.2 503/429 không rõ nguyên nhân

```bash
# Kiểm tra access log
docker compose logs nginx 2>&1 | grep " 429 "
# Xem request nào bị reject, từ IP nào

# Kiểm tra zone nào đang trigger
# Thêm header debug:
add_header X-Debug-Limit "$limit_req_status" always;
```

### 9.3 Rate Limit không có hiệu lực

```bash
# 1. Kiểm tra zone name khớp
nginx -T | grep "limit_req"
# limit_req_zone ... zone=api_limit:10m ...
# limit_req zone=api_limit ...  ← phải khớp

# 2. Kiểm tra key: nếu $limit_key = "" → không bị limit
# Thêm log để debug:
add_header X-Limit-Key "$limit_key" always;

# 3. Kiểm tra location match
# Dùng nginx -T để xem config đã được load
```

### 9.4 False Positive — IP của LB bị limit

```bash
# Triệu chứng: tất cả user bị 429 cùng lúc
# Nguyên nhân: $remote_addr = IP của LB

# Kiểm tra
curl -s http://localhost:8080/api/ -H "X-Debug: 1" -v 2>&1 | head -20
# Xem IP nào đang được dùng làm key

# Fix: thêm set_real_ip_from
set_real_ip_from <LB_IP>;
real_ip_header X-Forwarded-For;
```

### 9.5 Shared Memory Zone Full

```bash
# Log: [crit] ngx_slab_alloc() failed: no memory in "api_limit" zone
# Hoặc: could not allocate node: no memory

# Fix: tăng zone size
limit_req_zone $binary_remote_addr zone=api_limit:50m rate=10r/s;
#                                                 ^^^
# Reload Nginx (không cần restart)
nginx -s reload
```

---

## 10. Completion Checklist

- [ ] Hiểu sự khác biệt giữa `limit_req` (rate) và `limit_conn` (concurrent connections)
- [ ] Configure được `burst`, `nodelay`, `delay=N` và giải thích behavior của từng mode
- [ ] Biết tại sao phải dùng `set_real_ip_from` khi đứng sau CDN/LB
- [ ] Implement được geo whitelist để localhost/internal không bị rate limit
- [ ] Chạy được lab Docker Compose, quan sát 200 vs 429 trong access log
- [ ] Giải thích được tại sao Nginx OSS rate limit không đủ cho distributed deployment
- [ ] Biết khi nào nên dùng Kong rate-limiting plugin thay vì Nginx `limit_req`

---

## 11. References

- [Nginx `limit_req_module` official docs](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Nginx `limit_conn_module` official docs](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html)
- [Nginx `realip_module` official docs](https://nginx.org/en/docs/http/ngx_http_realip_module.html)
- [Nginx `geo_module` official docs](https://nginx.org/en/docs/http/ngx_http_geo_module.html)
- [Rate Limiting with Nginx — Nginx blog](https://www.nginx.com/blog/rate-limiting-nginx/)
- [RFC 6585 — 429 Too Many Requests](https://tools.ietf.org/html/rfc6585)
- [RFC 7231 — Retry-After header](https://tools.ietf.org/html/rfc7231#section-7.1.3)
- [Kong rate-limiting plugin docs](https://docs.konghq.com/hub/kong-inc/rate-limiting/)

---

## Recap

Trong bài này, bạn đã học:

- **`limit_req`** dùng leaky bucket algorithm: request đến nhanh hơn rate → queue (nếu còn burst) hoặc reject
- **`limit_conn`** giới hạn concurrent connections: bảo vệ khỏi Slowloris và connection exhaustion
- **`burst` + `nodelay`**: xử lý ngay nhưng counter vẫn tăng — phù hợp cho API có spike ngắn
- **`set_real_ip_from`**: bắt buộc khi đứng sau CDN/LB để rate limit đúng per-user
- **`geo` + `map`**: whitelist internal IP, blacklist known bad IP
- **Nginx OSS limitation**: rate limit per-instance, không distributed — đây là lý do Kong tốt hơn cho enterprise multi-instance deployment

---

## Preview Day 7

**Day 7: Performance Tuning & Benchmark** — Bạn sẽ học cách đo lường và tối ưu Nginx:
- `worker_processes`, `worker_connections`, `worker_rlimit_nofile`
- `sendfile`, `tcp_nopush`, `tcp_nodelay` — khi nào bật, khi nào tắt
- `keepalive_timeout`, `keepalive_requests` — trade-off giữa connection reuse và resource
- Benchmark methodology với `wrk`, `hey`, `ab` — đọc p50/p95/p99 đúng cách
- Profiling Nginx với `stub_status` module và Prometheus exporter
- Bottleneck identification: CPU-bound vs I/O-bound vs network-bound
