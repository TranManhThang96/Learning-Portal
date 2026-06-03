# Day 06: Exercises — Rate Limiting, Connection Limiting & Basic Protection

> **Thời lượng thực hành**: 60-90 phút
> **Yêu cầu**: Docker, Docker Compose, curl, wrk hoặc hey (tùy chọn)

---

## Chuẩn bị môi trường

### Kiểm tra tools

```bash
# Kiểm tra Docker
docker --version
docker compose version

# Kiểm tra curl
curl --version

# Kiểm tra wrk (optional, load testing)
wrk --version
# Nếu chưa có trên Ubuntu: apt install wrk
# Nếu chưa có trên macOS: brew install wrk

# Kiểm tra hey (optional, alternative to wrk)
hey --version
# Nếu chưa có: go install github.com/rakyll/hey@latest
```

### Tạo cấu trúc thư mục

```bash
mkdir -p lab-day06/{nginx/conf.d,backend,logs}
cd lab-day06
```

---

## Exercise 1: Setup cơ bản và test rate limit

### 1a. Tạo Docker Compose

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
    def _write_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
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

        self._write_json({
            "service": "rate-limit-lab",
            "path": self.path,
            "client": self.client_address[0],
        })

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

    log_format  main  '$remote_addr - [$time_local] "$request" '
                      '$status $body_bytes_sent rt=$request_time';

    access_log  /var/log/nginx/access.log  main;
    sendfile        on;
    keepalive_timeout  65;

    include /etc/nginx/conf.d/*.conf;
}
```

**`lab-day06/nginx/conf.d/rate-limit.conf`:**

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    listen 80;
    server_name localhost;

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;
        limit_req_log_level warn;
        add_header Retry-After 5 always;
        proxy_pass http://backend/;
        proxy_set_header Host $host;
    }

    location /api/login {
        limit_req zone=login_limit burst=3 nodelay;
        limit_req_status 429;
        add_header Retry-After 60 always;
        proxy_pass http://backend/;
        proxy_set_header Host $host;
    }

    location /download/ {
        limit_conn conn_limit 5;
        limit_conn_status 429;
        limit_rate 512k;
        proxy_pass http://backend;
    }
}
```

### 1b. Khởi động và kiểm tra

```bash
cd lab-day06
docker compose up -d

# Kiểm tra Nginx đã chạy
curl -s http://localhost:8080/api/
# Output: JSON từ backend app

# Kiểm tra config hợp lệ
docker compose exec nginx nginx -t
# Output: nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**Output mong đợi:**
```json
{"service": "rate-limit-lab", "path": "/", "client": "172.x.x.x"}
```

---

## Exercise 2: Test burst behavior — có delay vs nodelay

### 2a. Test với nodelay (config hiện tại)

```bash
# Gửi 30 request song song, đo thời gian
time for i in $(seq 1 30); do
  curl -s -o /dev/null -w "Req $i: %{http_code}\n" \
    http://localhost:8080/api/ &
done
wait

# Đếm số 200 và 429
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/ &
done
wait
```

**Output mong đợi (nodelay):**
```
Req 1: 200
Req 2: 200
...
Req 21: 200   ← 21 request đầu pass (10 rate + 20 burst + 1 = 21 max)
Req 22: 429
Req 23: 429
...
Req 30: 429
```

### 2b. Chuyển sang mode có delay (bỏ nodelay)

Sửa `nginx/conf.d/rate-limit.conf`, thay dòng `limit_req`:

```nginx
# Thay:
limit_req zone=api_limit burst=20 nodelay;
# Thành:
limit_req zone=api_limit burst=20;
```

```bash
# Reload Nginx (không cần restart)
docker compose exec nginx nginx -s reload

# Gửi 25 request tuần tự và đo thời gian
time for i in $(seq 1 25); do
  curl -s -o /dev/null http://localhost:8080/api/
done
```

**Output mong đợi (có delay):**
```
real    0m2.5s   ← ~2.5 giây (25 requests / 10 req/s)
# Không có 429, nhưng request bị delay
```

### 2c. Test delay=N (N request đầu không delay)

```nginx
# Thay:
limit_req zone=api_limit burst=20;
# Thành:
limit_req zone=api_limit burst=20 delay=5;
```

```bash
docker compose exec nginx nginx -s reload

# Gửi 25 request và quan sát thời gian từng request
for i in $(seq 1 25); do
  TIME=$(curl -s -o /dev/null -w "%{time_total}" http://localhost:8080/api/)
  echo "Req $i: ${TIME}s"
done
```

**Output mong đợi (delay=5):**
```
Req 1: 0.005s   ← nhanh (delay=5, 5 request đầu không delay)
Req 2: 0.005s
Req 3: 0.005s
Req 4: 0.005s
Req 5: 0.005s
Req 6: 0.105s   ← bắt đầu delay 100ms
Req 7: 0.205s
...
Req 21: 1.505s  ← delay tích lũy
Req 22: 429     ← vượt burst=20
```

---

## Exercise 3: Brute-force protection cho login endpoint

### 3a. Test login rate limit

```bash
# Khôi phục config nodelay cho /api/
# Login limit: 5r/m = 1 request mỗi 12 giây, burst=3

# Simulate brute-force attack
echo "=== Brute-force simulation ==="
for i in $(seq 1 10); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8080/api/login \
    -d "username=admin&password=test$i")
  echo "Attempt $i: HTTP $STATUS"
done
```

**Output mong đợi:**
```
=== Brute-force simulation ===
Attempt 1: HTTP 200
Attempt 2: HTTP 200
Attempt 3: HTTP 200
Attempt 4: HTTP 429   ← burst=3 đã hết
Attempt 5: HTTP 429
...
Attempt 10: HTTP 429
```

### 3b. Kiểm tra Retry-After header

```bash
# Xem headers khi bị rate limit
curl -v -X POST http://localhost:8080/api/login \
  -d "username=admin&password=test" 2>&1 | grep -E "(HTTP|Retry|< )"
```

**Output mong đợi:**
```
< HTTP/1.1 429 Too Many Requests
< Retry-After: 60
< Server: nginx/1.25.x
```

### 3c. Đợi rate limit reset và thử lại

```bash
# Đợi 12 giây (1/5 của 60 giây = 1 token mới)
sleep 12

# Thử lại
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://localhost:8080/api/login \
  -d "username=admin&password=test"
# Output: 200 (1 token mới đã được tạo)
```

---

## Exercise 4: Connection Limiting

### 4a. Test limit_conn

```bash
# Mở 10 connections đồng thời đến /download/
# limit_conn = 5, nên 5 connections đầu pass, 5 sau bị reject

for i in $(seq 1 10); do
  curl -s -o /dev/null -w "Conn $i: %{http_code}\n" \
    --max-time 5 http://localhost:8080/download/ &
done
wait
```

**Output mong đợi:**
```
Conn 1: 200
Conn 2: 200
Conn 3: 200
Conn 4: 200
Conn 5: 200
Conn 6: 429   ← vượt limit_conn=5
Conn 7: 429
Conn 8: 429
Conn 9: 429
Conn 10: 429
```

### 4b. Quan sát log

```bash
docker compose logs nginx 2>&1 | grep -E "(limiting|429)"
# Output:
# [warn] limiting connections by zone "conn_limit", ...
```

---

## Exercise 5: Geo Whitelist

### 5a. Thêm geo whitelist vào config

Sửa `nginx/conf.d/rate-limit.conf`, thêm vào đầu file (trước server block):

```nginx
# Thêm sau các limit_conn_zone:
geo $limit_key {
    default         $binary_remote_addr;
    127.0.0.1       "";          # localhost không bị limit
    10.0.0.0/8      "";          # internal network production example
}

# Thêm zone mới dùng $limit_key
limit_req_zone $limit_key zone=geo_limit:10m rate=2r/s;
```

Thêm location mới vào server block:

```nginx
location /internal/ {
    limit_req zone=geo_limit burst=5 nodelay;
    limit_req_status 429;
    proxy_pass http://backend/;
}
```

```bash
docker compose exec nginx nginx -s reload
```

### 5b. Test từ bên ngoài (bị limit)

```bash
# Request từ host machine đi qua Docker bridge, thường KHÔNG phải 127.0.0.1
# nên vẫn bị áp rate limit.

# Gửi 10 request nhanh
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "Req $i: %{http_code}\n" \
    http://localhost:8080/internal/
done
```

**Output mong đợi:**
```
Req 1: 200
Req 2: 200
Req 3: 200
Req 4: 200
Req 5: 200
Req 6: 429   ← vượt burst=5 với rate=2r/s
...
```

### 5c. Test từ loopback bên trong Nginx container (không bị limit)

```bash
# Request vào chính Nginx qua 127.0.0.1, remote_addr = 127.0.0.1 nên được whitelist

docker compose exec nginx sh -c \
  'for i in $(seq 1 20); do wget -q -O /dev/null http://127.0.0.1/internal/ && echo "OK" || echo "FAIL"; done'
# Output: tất cả OK (không bị limit vì 127.0.0.1 trong whitelist)
```

---

## Exercise 6: Real IP khi đứng sau Proxy

### 6a. Simulate CDN/LB scenario

Thêm vào `nginx/conf.d/rate-limit.conf` (trong http context, trước server block):

```nginx
# Simulate: trust proxy IP
set_real_ip_from 172.16.0.0/12;   # Docker network (simulate LB)
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

```bash
docker compose exec nginx nginx -s reload
```

### 6b. Test với X-Forwarded-For header

```bash
# Simulate request từ client 1.2.3.4 qua CDN
# Nginx sẽ dùng 1.2.3.4 làm key cho rate limit

# Gửi 5 request với X-Forwarded-For: 1.2.3.4
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "Req $i (IP 1.2.3.4): %{http_code}\n" \
    -H "X-Forwarded-For: 1.2.3.4" \
    http://localhost:8080/api/
done

# Gửi 5 request với X-Forwarded-For: 5.6.7.8 (IP khác)
for i in $(seq 1 5); do
  curl -s -o /dev/null -w "Req $i (IP 5.6.7.8): %{http_code}\n" \
    -H "X-Forwarded-For: 5.6.7.8" \
    http://localhost:8080/api/
done
```

**Output mong đợi:**
```
Req 1 (IP 1.2.3.4): 200
...
Req 5 (IP 1.2.3.4): 200
Req 1 (IP 5.6.7.8): 200   ← IP khác, counter riêng
...
Req 5 (IP 5.6.7.8): 200
```

### 6c. Test spoofing (cảnh báo bảo mật)

```bash
# Attacker cố spoof IP whitelist
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-Forwarded-For: 127.0.0.1" \
  http://localhost:8080/api/

# Trong lab, request từ host đi qua Docker bridge nên được trust và header này đổi key thành 127.0.0.1.
# Đây là lý do production chỉ được trust subnet của LB/CDN thật, không trust subnet public hoặc "all".
# Nếu client có thể chạm trực tiếp Nginx và spoof X-Forwarded-For, rate limit có thể bị bypass.
```

---

## Exercise 7: Load Test với wrk

### 7a. Baseline — không có rate limit

```bash
# Tạm thời comment out limit_req trong /api/
# Sửa nginx/conf.d/rate-limit.conf:
# #limit_req zone=api_limit burst=20 nodelay;

docker compose exec nginx nginx -s reload

# Chạy wrk 10 giây, 4 threads, 50 connections
wrk -t4 -c50 -d10s http://localhost:8080/api/
```

**Output mong đợi (baseline):**
```
Running 10s test @ http://localhost:8080/api/
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     2.50ms    1.20ms  20.00ms   85.00%
    Req/Sec     5.00k     500.00   6.00k    75.00%
  200000 requests in 10.00s, 50.00MB read
Requests/sec:  20000.00
Transfer/sec:   5.00MB
```

### 7b. Với rate limit bật

```bash
# Bật lại limit_req
# limit_req zone=api_limit burst=20 nodelay;

docker compose exec nginx nginx -s reload

# Chạy lại wrk
wrk -t4 -c50 -d10s http://localhost:8080/api/
```

**Output mong đợi (với rate limit):**
```
Running 10s test @ http://localhost:8080/api/
  ...
  Non-2xx or 3xx responses: 195000   ← hầu hết bị 429
Requests/sec:  20000.00
# Nginx vẫn xử lý nhanh, nhưng hầu hết trả 429
```

### 7c. Phân tích kết quả

```bash
# Xem tỷ lệ 200 vs 429 trong access log đã mount ra ./logs
grep "GET /api/" logs/access.log | awk '{print $8}' | sort | uniq -c
# Output:
#   195000 429
#      120 200   ← khoảng rate * duration + burst, số thực tế phụ thuộc timing
```

---

## Cleanup

```bash
cd lab-day06
docker compose down -v

# Xóa thư mục lab (optional)
cd ..
rm -rf lab-day06
```

---

## Tổng kết

| Exercise | Kỹ năng học được |
|---|---|
| 1 | Setup Docker Compose, config limit_req cơ bản |
| 2 | Phân biệt burst, nodelay, delay=N behavior |
| 3 | Brute-force protection, Retry-After header |
| 4 | Connection limiting, Slowloris protection |
| 5 | Geo whitelist, internal network bypass |
| 6 | Real IP khi đứng sau CDN/LB, X-Forwarded-For |
| 7 | Load test với wrk, phân tích 200 vs 429 ratio |
