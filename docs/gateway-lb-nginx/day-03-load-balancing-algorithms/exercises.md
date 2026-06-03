# Day 03: Exercises — Load Balancing Algorithms

> **Thời lượng ước tính**: 60-90 phút
> **Yêu cầu**: Docker, Docker Compose, curl, hey (hoặc wrk)
> Để giữ đúng khung 2 giờ/ngày: làm Lab 1, 2, 3, 5 và 7; Lab 4, 6, 8 là phần mở rộng nếu còn thời gian.

---

## Chuẩn bị môi trường

### Cài hey (HTTP load testing tool)

```bash
# macOS
brew install hey

# Linux
wget https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -O /usr/local/bin/hey
chmod +x /usr/local/bin/hey

# Windows (PowerShell)
# Tải từ https://github.com/rakyll/hey/releases
```

### Tạo thư mục lab

```bash
mkdir -p ~/lab-day03
cd ~/lab-day03
mkdir -p backend nginx
```

---

## Lab 1: Dựng môi trường Docker Compose

### 1.1 Tạo backend echo server

Tạo file `backend/app.py`:

```python
#!/usr/bin/env python3
"""Simple echo backend server."""
import os
import time
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

BACKEND_ID = os.environ.get("BACKEND_ID", "unknown")
SLOW_MODE = os.environ.get("SLOW_MODE", "false").lower() == "true"
SLOW_MIN_MS = int(os.environ.get("SLOW_MIN_MS", "0"))
SLOW_MAX_MS = int(os.environ.get("SLOW_MAX_MS", "500"))

request_count = 0

class EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global request_count
        request_count += 1

        if SLOW_MODE:
            delay_ms = random.randint(SLOW_MIN_MS, SLOW_MAX_MS)
            time.sleep(delay_ms / 1000.0)
        else:
            delay_ms = 0

        response = {
            "backend_id": BACKEND_ID,
            "path": self.path,
            "request_count": request_count,
            "delay_ms": delay_ms,
            "client_ip": self.client_address[0],
        }

        body = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Backend-ID", BACKEND_ID)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress default logging, print custom format
        print(f"[{BACKEND_ID}] {self.client_address[0]} - {args[0]}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Backend {BACKEND_ID} starting on port {port} (slow_mode={SLOW_MODE})")
    server = HTTPServer(("0.0.0.0", port), EchoHandler)
    server.serve_forever()
```

Tạo file `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python", "app.py"]
```

### 1.2 Tạo nginx.conf ban đầu (round-robin)

Tạo file `nginx/nginx.conf`:

```nginx
worker_processes 1;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 1024;
}

http {
    log_format main '$remote_addr - $upstream_addr - "$request" - $status - $request_time';
    access_log /var/log/nginx/access.log main;

    # --- THAY ĐỔI UPSTREAM Ở ĐÂY KHI TEST TỪNG ALGORITHM ---
    upstream backend {
        # round-robin (default) - không cần directive
        server backend1:8080;
        server backend2:8080;
        server backend3:8080;
        server backend4:8080;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_connect_timeout 5s;
            proxy_read_timeout 30s;
        }

        # Health check endpoint cho Nginx itself
        location /nginx-health {
            default_type text/plain;
            return 200 "OK\n";
        }
    }
}
```

### 1.3 Tạo docker-compose.yml

```yaml
services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend1
      - backend2
      - backend3
      - backend4
    networks:
      - lab-net

  backend1:
    build: ./backend
    environment:
      - BACKEND_ID=backend-1
      - PORT=8080
    networks:
      - lab-net

  backend2:
    build: ./backend
    environment:
      - BACKEND_ID=backend-2
      - PORT=8080
    networks:
      - lab-net

  backend3:
    build: ./backend
    environment:
      - BACKEND_ID=backend-3
      - PORT=8080
    networks:
      - lab-net

  backend4:
    build: ./backend
    environment:
      - BACKEND_ID=backend-4
      - PORT=8080
    networks:
      - lab-net

  # Backend chậm cho lab least_conn
  backend-slow:
    build: ./backend
    environment:
      - BACKEND_ID=backend-slow
      - PORT=8080
      - SLOW_MODE=true
      - SLOW_MIN_MS=100
      - SLOW_MAX_MS=500
    networks:
      - lab-net
    profiles:
      - slow

networks:
  lab-net:
    driver: bridge
```

### 1.4 Khởi động và kiểm tra

```bash
# Build và start
docker compose up -d --build

# Kiểm tra tất cả container đang chạy
docker compose ps

# depends_on chỉ đảm bảo thứ tự start, không đảm bảo backend đã ready.
# Retry vài lần để tránh 502 race condition ngay sau khi docker compose up.
until curl -fsS http://localhost:8080/nginx-health >/dev/null; do
    echo "waiting for nginx..."
    sleep 1
done
sleep 2

# Test thủ công
curl http://localhost:8080/
# Expected: {"backend_id": "backend-1", ...}

curl http://localhost:8080/
# Expected: {"backend_id": "backend-2", ...}

curl http://localhost:8080/
# Expected: {"backend_id": "backend-3", ...}
```

---

## Lab 2: Test Round-Robin

### 2.1 Gửi 100 requests và đếm phân phối

```bash
# Gửi 100 requests tuần tự
for i in $(seq 1 100); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done | sort | uniq -c | sort -rn
```

**Output mong đợi:**
```
 25 backend-4
 25 backend-3
 25 backend-2
 25 backend-1
```

### 2.2 Gửi concurrent requests

```bash
# 100 requests, 10 concurrent
hey -n 100 -c 10 http://localhost:8080/

# Xem phân phối trong access log
docker compose exec nginx tail -100 /var/log/nginx/access.log | \
    awk '{print $3}' | sort | uniq -c | sort -rn
```

### 2.3 Quan sát log format

```bash
# Log format: remote_addr - upstream_addr - request - status - time
docker compose exec nginx tail -f /var/log/nginx/access.log
```

**Câu hỏi để suy nghĩ:**
- Với concurrent requests, phân phối có đúng 25/25/25/25 không?
- Tại sao có thể lệch nhẹ?

---

## Lab 3: Test Least Connections

### 3.1 Cập nhật nginx.conf để dùng least_conn

Sửa file `nginx/nginx.conf`, thay upstream block:

```nginx
upstream backend {
    least_conn;
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
    server backend4:8080;
}
```

```bash
# Validate rồi reload Nginx (không restart)
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 3.2 Khởi động backend chậm

```bash
# Start backend-slow (profile slow)
docker compose --profile slow up -d backend-slow
```

Sửa nginx.conf để thêm backend-slow:

```nginx
upstream backend {
    least_conn;
    server backend1:8080;
    server backend2:8080;
    server backend-slow:8080;  # thêm dòng này
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 3.3 So sánh round-robin vs least_conn với backend chậm

```bash
# Test với least_conn (đang active)
hey -n 200 -c 20 -q 10 http://localhost:8080/ 2>&1 | grep -E "Status|Requests"

# Xem phân phối: backend-slow nên nhận ÍT request hơn
docker compose exec nginx tail -200 /var/log/nginx/access.log | \
    awk '{print $3}' | sort | uniq -c | sort -rn
```

**Output mong đợi với least_conn:**
```
 90 172.x.x.x:8080  (backend1 hoặc backend2 - nhanh)
 85 172.x.x.x:8080  (backend1 hoặc backend2 - nhanh)
 25 172.x.x.x:8080  (backend-slow - chậm, nhận ít hơn)
```

### 3.4 Đổi lại round-robin và so sánh

```nginx
upstream backend {
    # least_conn;  <- comment out
    server backend1:8080;
    server backend2:8080;
    server backend-slow:8080;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

hey -n 200 -c 20 -q 10 http://localhost:8080/ 2>&1 | grep -E "Status|Requests|Latency"
```

**Quan sát**: Với round-robin, latency p95/p99 sẽ cao hơn vì ~33% requests vào backend-slow.

---

## Lab 4: Test IP Hash

### 4.1 Configure ip_hash

```nginx
upstream backend {
    ip_hash;
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
    server backend4:8080;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 4.2 Kiểm tra sticky behavior

```bash
# Từ cùng một IP (localhost), tất cả requests phải vào cùng backend
for i in $(seq 1 10); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done
```

**Output mong đợi:**
```
backend-2
backend-2
backend-2
backend-2
backend-2
...
```

Tất cả 10 requests đều vào cùng 1 backend vì cùng IP.

### 4.3 Mô phỏng nhiều client IP khác nhau

```bash
# Dùng X-Forwarded-For để giả lập IP khác nhau
# (Nginx ip_hash dùng $remote_addr, không phải X-Forwarded-For)
# Để test thực sự, cần nhiều container client

# Tạo script test từ nhiều "client"
cat > test_iphash.sh << 'EOF'
#!/bin/bash
echo "=== Testing ip_hash sticky behavior ==="
for client_num in 1 2 3 4 5; do
    echo -n "Client $client_num (simulated): "
    # Trong thực tế, mỗi client có IP khác nhau
    # Ở đây chúng ta chỉ có thể test từ 1 IP
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done
EOF
chmod +x test_iphash.sh
./test_iphash.sh
```

### 4.4 Quan sát khi thêm backend (hash thay đổi)

```bash
# Ghi nhận backend hiện tại
echo "Before adding backend5:"
curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"

# Muốn test thật, thêm backend5 vào docker-compose.yml trước rồi chạy:
# docker compose up -d backend5
#
# Sau đó thêm backend5 vào nginx.conf
# upstream backend {
#     ip_hash;
#     server backend1:8080;
#     server backend2:8080;
#     server backend3:8080;
#     server backend4:8080;
#     server backend5:8080;  <- thêm
# }

# Sau khi reload, backend có thể thay đổi
echo "After adding backend5 (hash may change):"
# curl -s http://localhost:8080/ | ...
```

**Kết luận**: ip_hash không đảm bảo sticky khi thêm/bớt backend.

---

## Lab 5: Test Weighted Upstream

### 5.1 Configure weighted round-robin

```nginx
upstream backend {
    server backend1:8080 weight=3;
    server backend2:8080 weight=1;
    server backend3:8080 weight=1;
    server backend4:8080 weight=1;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 5.2 Kiểm tra tỉ lệ phân phối

```bash
# Gửi 600 requests (bội số của tổng weight = 6)
for i in $(seq 1 600); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done | sort | uniq -c | sort -rn
```

**Output mong đợi:**
```
300 backend-1  (weight=3, ~50%)
100 backend-2  (weight=1, ~17%)
100 backend-3  (weight=1, ~17%)
100 backend-4  (weight=1, ~17%)
```

### 5.3 Weighted least_conn

```nginx
upstream backend {
    least_conn;
    server backend1:8080 weight=3;
    server backend2:8080 weight=1;
    server backend3:8080 weight=1;
    server backend4:8080 weight=1;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

# Test với concurrent requests
hey -n 600 -c 50 http://localhost:8080/

docker compose exec nginx tail -600 /var/log/nginx/access.log | \
    awk '{print $3}' | sort | uniq -c | sort -rn
```

---

## Lab 6: Test Hash với Consistent Hashing

### 6.1 Configure hash $request_uri consistent

```nginx
upstream backend {
    hash $request_uri consistent;
    server backend1:8080;
    server backend2:8080;
    server backend3:8080;
    server backend4:8080;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 6.2 Kiểm tra sticky theo URI

```bash
# Cùng URI → cùng backend
echo "=== URI /api/users ==="
for i in $(seq 1 5); do
    curl -s http://localhost:8080/api/users | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done

echo "=== URI /api/products ==="
for i in $(seq 1 5); do
    curl -s http://localhost:8080/api/products | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done

echo "=== URI /api/orders ==="
for i in $(seq 1 5); do
    curl -s http://localhost:8080/api/orders | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done
```

**Output mong đợi**: Mỗi URI luôn vào cùng 1 backend, nhưng các URI khác nhau có thể vào backend khác nhau.

### 6.3 So sánh có và không có consistent

```bash
# Ghi nhận mapping hiện tại
echo "=== Mapping với 4 backends ==="
for uri in /api/users /api/products /api/orders /api/cart /api/checkout; do
    backend=$(curl -s http://localhost:8080$uri | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])")
    echo "$uri → $backend"
done
```

---

## Lab 7: Failover Test

### 7.1 Chuẩn bị: round-robin với backup

```nginx
upstream backend {
    server backend1:8080 max_fails=2 fail_timeout=10s;
    server backend2:8080 max_fails=2 fail_timeout=10s;
    server backend3:8080 max_fails=2 fail_timeout=10s;
    server backend4:8080 backup;
}
```

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

### 7.2 Kiểm tra trạng thái bình thường

```bash
# Gửi 20 requests, quan sát phân phối
for i in $(seq 1 20); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done | sort | uniq -c
```

**Output mong đợi**: backend-4 (backup) không xuất hiện.

### 7.3 Kill backend1 và quan sát

```bash
# Terminal 1: Theo dõi log liên tục
docker compose exec nginx tail -f /var/log/nginx/access.log &

# Terminal 2: Gửi requests liên tục
for i in $(seq 1 50); do
    result=$(curl -s -w "\n%{http_code}" http://localhost:8080/)
    echo "$result"
    sleep 0.2
done &

# Terminal 3: Kill backend1
docker compose stop backend1
echo "backend1 stopped"
```

**Quan sát:**
- Một số requests đầu tiên có thể trả về 502 (trước khi Nginx phát hiện backend chết)
- Sau max_fails lần fail, Nginx ngừng gửi request đến backend1
- Traffic tự động phân phối sang backend2, backend3

### 7.4 Kiểm tra backup server được kích hoạt

```bash
# Kill thêm backend2 và backend3
docker compose stop backend2 backend3

# Gửi requests
for i in $(seq 1 10); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done
```

**Output mong đợi**: Tất cả requests vào backend-4 (backup).

### 7.5 Khôi phục và quan sát

```bash
# Restart backend1
docker compose start backend1

# Chờ fail_timeout (10s) rồi test lại
sleep 12

for i in $(seq 1 20); do
    curl -s http://localhost:8080/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['backend_id'])"
done | sort | uniq -c
```

**Quan sát**: Sau fail_timeout, Nginx thử lại backend1. Nếu thành công, traffic quay lại phân phối bình thường.

---

## Lab 8: Challenge — Tự thiết kế upstream

### Scenario

Bạn có hệ thống với:
- 2 server mạnh (16GB RAM, 8 CPU): `strong1`, `strong2`
- 1 server yếu (4GB RAM, 2 CPU): `weak1`
- 1 server dự phòng: `standby`
- App có session lưu trong Redis (không cần sticky)
- Response time của backend không đồng đều (DB query phức tạp)

### Yêu cầu

1. Thiết kế upstream config tối ưu
2. Giải thích lý do chọn algorithm
3. Configure failover phù hợp
4. Thêm keepalive

### Gợi ý giải pháp

```nginx
upstream backend {
    # Điền algorithm phù hợp ở đây

    server strong1:8080 weight=4 max_fails=3 fail_timeout=30s;
    server strong2:8080 weight=4 max_fails=3 fail_timeout=30s;
    server weak1:8080   weight=1 max_fails=3 fail_timeout=30s;
    server standby:8080 backup;

    keepalive 32;
    keepalive_requests 1000;
    keepalive_timeout 60s;
}
```

**Câu hỏi:**
- Nên dùng `least_conn` hay round-robin? Tại sao?
- Weight 4:4:1 có hợp lý không? Khi nào cần điều chỉnh?
- fail_timeout=30s có phù hợp không? Nếu backend restart mất 60s thì sao?

---

## Dọn dẹp

```bash
# Stop tất cả containers
docker compose --profile slow down

# Xóa images đã build
docker compose down --rmi local

# Xóa thư mục lab (tùy chọn)
# rm -rf ~/lab-day03
```

---

## Tổng kết Lab

| Lab | Algorithm | Kết quả quan sát |
|---|---|---|
| Lab 2 | round-robin | Phân phối đều 25/25/25/25 |
| Lab 3 | least_conn | Backend chậm nhận ít request hơn |
| Lab 4 | ip_hash | Cùng IP → cùng backend |
| Lab 5 | weighted | Tỉ lệ theo weight (3:1:1:1) |
| Lab 6 | hash consistent | Cùng URI → cùng backend |
| Lab 7 | failover | Backup kích hoạt khi primary down |
