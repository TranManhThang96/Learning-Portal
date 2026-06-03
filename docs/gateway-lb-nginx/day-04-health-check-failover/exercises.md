# Day 4: Exercises - Health Check, Failover & Upstream Failure

> Thực hành 5 failure scenarios với Docker Compose. Mỗi scenario có mục tiêu quan sát rõ ràng.

---

## Chuẩn bị môi trường

### Bước 1: Tạo cấu trúc thư mục

```bash
mkdir -p day04-lab
cd day04-lab
mkdir -p nginx/conf.d logs
```

### Bước 2: Tạo docker-compose.yml

```yaml
# docker-compose.yml
version: "3.8"

services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
    depends_on:
      - backend1
      - backend2
      - backend3
    networks:
      - lab-net

  backend1:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, os, time, sys
      class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
          delay = float(os.environ.get('DELAY', '0'))
          if delay > 0:
            time.sleep(delay)
          status = int(os.environ.get('STATUS', '200'))
          self.send_response(status)
          self.send_header('Content-Type', 'text/plain')
          self.end_headers()
          self.wfile.write(b'backend1\n')
        def log_message(self, fmt, *args):
          sys.stderr.write('backend1: ' + fmt % args + '\n')
      http.server.HTTPServer(('', 8080), H).serve_forever()
      "
    environment:
      DELAY: "0"
      STATUS: "200"
    networks:
      - lab-net

  backend2:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, os, time, sys
      class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
          delay = float(os.environ.get('DELAY', '0'))
          if delay > 0:
            time.sleep(delay)
          status = int(os.environ.get('STATUS', '200'))
          self.send_response(status)
          self.send_header('Content-Type', 'text/plain')
          self.end_headers()
          self.wfile.write(b'backend2\n')
        def log_message(self, fmt, *args):
          sys.stderr.write('backend2: ' + fmt % args + '\n')
      http.server.HTTPServer(('', 8080), H).serve_forever()
      "
    environment:
      DELAY: "0"
      STATUS: "200"
    networks:
      - lab-net

  backend3:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, os, time, sys
      class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
          delay = float(os.environ.get('DELAY', '0'))
          if delay > 0:
            time.sleep(delay)
          status = int(os.environ.get('STATUS', '200'))
          self.send_response(status)
          self.send_header('Content-Type', 'text/plain')
          self.end_headers()
          self.wfile.write(b'backend3\n')
        def log_message(self, fmt, *args):
          sys.stderr.write('backend3: ' + fmt % args + '\n')
      http.server.HTTPServer(('', 8080), H).serve_forever()
      "
    environment:
      DELAY: "0"
      STATUS: "200"
    networks:
      - lab-net

networks:
  lab-net:
    driver: bridge
```

### Bước 3: Tạo nginx.conf

```nginx
# nginx/nginx.conf
worker_processes 1;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    log_format detailed '$remote_addr - $remote_user [$time_local] '
                        '"$request" $status $body_bytes_sent '
                        'upstream=$upstream_addr '
                        'upstream_status=$upstream_status '
                        'upstream_rt=$upstream_response_time '
                        'rt=$request_time';

    access_log /var/log/nginx/access.log detailed;

    upstream backend_pool {
        server backend1:8080 max_fails=2 fail_timeout=15s;
        server backend2:8080 max_fails=2 fail_timeout=15s;
        server backend3:8080 max_fails=2 fail_timeout=15s;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend_pool;
            proxy_connect_timeout 3s;
            proxy_send_timeout    10s;
            proxy_read_timeout    10s;

            proxy_next_upstream error timeout http_502 http_503;
            proxy_next_upstream_tries 3;
            proxy_next_upstream_timeout 15s;

            add_header X-Upstream-Addr   $upstream_addr   always;
            add_header X-Upstream-Status $upstream_status always;
        }

        # Nginx status endpoint
        location /nginx_status {
            stub_status on;
            allow 127.0.0.1;
            allow 172.0.0.0/8;
            deny all;
        }
    }
}
```

### Bước 4: Khởi động lab

```bash
docker compose up -d

# Kiểm tra tất cả container đang chạy
docker compose ps

# Test request đầu tiên
curl -v http://localhost:8080/
```

**Output mong đợi:**
```
< HTTP/1.1 200 OK
< X-Upstream-Addr: 172.x.x.x:8080
< X-Upstream-Status: 200
backend1
```

---

## Scenario 1: Kill 1 Backend - Passive Health Check

**Mục tiêu**: Quan sát passive health check hoạt động, đếm số request thất bại trước khi backend bị đánh dấu down.

### Bước 1: Gửi request liên tục

```bash
# Terminal 1: gửi request mỗi 0.3s, hiển thị upstream và status
while true; do
  result=$(curl -s -w "\n[HTTP %{http_code}] upstream=%{url_effective}" \
    -H "Accept: text/plain" \
    http://localhost:8080/ 2>&1)
  echo "$(date +%H:%M:%S) $result"
  sleep 0.3
done
```

### Bước 2: Kill backend1

```bash
# Terminal 2: dừng backend1
docker compose stop backend1
```

### Bước 3: Quan sát

**Output mong đợi sau khi kill backend1:**
```
14:30:01 backend1 [HTTP 200]
14:30:01 backend2 [HTTP 200]
14:30:02 backend3 [HTTP 200]
14:30:02 backend2 [HTTP 200] ← lần thử backend1 fail, proxy_next_upstream retry sang backend2
14:30:03 backend3 [HTTP 200] ← lần thử backend1 fail lần 2, backend1 marked DOWN
14:30:03 backend2 [HTTP 200] ← backend1 bị skip hoàn toàn
14:30:04 backend3 [HTTP 200]
```

Lưu ý: với `proxy_next_upstream error timeout ...` đang bật, client thường vẫn nhận `200` nếu retry sang backend khác thành công. Dấu hiệu backend1 fail nằm trong `error.log` và trong access log qua `upstream_status=502, 200` hoặc `upstream=backend1:8080, backend2:8080`. Client chỉ thấy `502` khi không còn backend retry thành công hoặc `proxy_next_upstream` bị tắt.

### Bước 4: Đọc error log

```bash
# Terminal 3: theo dõi error log
tail -f logs/error.log
```

**Output mong đợi:**
```
[error] connect() failed (111: Connection refused) while connecting to upstream,
        client: 172.x.x.x, server: , request: "GET / HTTP/1.1",
        upstream: "http://172.x.x.x:8080/", host: "localhost:8080"
```

### Bước 5: Khôi phục backend1

```bash
docker compose start backend1

# Sau 15s (fail_timeout), backend1 sẽ được thử lại
# Quan sát terminal 1: backend1 xuất hiện lại trong rotation
```

### Câu hỏi kiểm tra

1. Bao nhiêu upstream attempt thất bại trước khi backend1 bị đánh dấu down?
2. Nếu `proxy_next_upstream` bật, client có luôn thấy 502 không? Tại sao access log vẫn có `upstream_status=502, 200`?
3. Sau bao lâu backend1 được thử lại?

---

## Scenario 2: Backend Trả 500 - proxy_next_upstream

**Mục tiêu**: Quan sát `proxy_next_upstream http_500` behavior.

### Bước 1: Cập nhật nginx.conf để bật http_500 retry

```nginx
# Thêm http_500 vào proxy_next_upstream
proxy_next_upstream error timeout http_500 http_502 http_503;
```

```bash
docker compose exec nginx nginx -s reload
```

### Bước 2: Tạo backend trả 500

```bash
# Dừng backend2 và tạo lại với STATUS=500
docker compose stop backend2
docker run -d --name backend2_500 \
  -e STATUS=500 \
  --network day04-lab_lab-net \
  --network-alias backend2 \
  python:3.11-slim \
  python3 -c "
import http.server, os, sys
class H(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(500)
    self.send_header('Content-Type', 'text/plain')
    self.end_headers()
    self.wfile.write(b'backend2 - internal error\n')
  def log_message(self, fmt, *args):
    sys.stderr.write('backend2_500: ' + fmt % args + '\n')
http.server.HTTPServer(('', 8080), H).serve_forever()
"
```

**Cách đơn giản hơn - dùng docker compose override:**

```bash
# Tạo file docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
version: "3.8"
services:
  backend2:
    environment:
      STATUS: "500"
EOF

docker compose up -d backend2
```

### Bước 3: Gửi request và quan sát

```bash
for i in $(seq 1 10); do
  curl -s -w " [HTTP %{http_code}] upstream=%header{X-Upstream-Addr}\n" \
    http://localhost:8080/
done
```

**Output mong đợi (với proxy_next_upstream http_500):**
```
backend1 [HTTP 200] upstream=172.x.x.1:8080
backend3 [HTTP 200] upstream=172.x.x.3:8080  ← backend2 bị skip, retry sang backend3
backend1 [HTTP 200] upstream=172.x.x.1:8080
```

**Output nếu TẮT proxy_next_upstream http_500:**
```
backend1 [HTTP 200]
backend2 - internal error [HTTP 500]  ← không retry
backend3 [HTTP 200]
```

### Bước 4: Quan sát access log

```bash
tail -20 logs/access.log
```

**Chú ý**: Khi retry, `upstream_addr` trong log sẽ có nhiều địa chỉ cách nhau bởi `, `:
```
upstream=172.x.x.2:8080, 172.x.x.3:8080
upstream_status=500, 200
```

### Bước 5: Cleanup

```bash
docker rm -f backend2_500 2>/dev/null || true
rm -f docker-compose.override.yml
docker compose up -d --force-recreate backend2
```

---

## Scenario 3: Backend Slow - proxy_read_timeout và 504

**Mục tiêu**: Quan sát 504 khi backend không trả lời trong timeout.

### Bước 1: Cập nhật nginx.conf với timeout ngắn

```nginx
# Giảm proxy_read_timeout xuống 5s để dễ test
proxy_read_timeout 5s;
```

```bash
docker compose exec nginx nginx -s reload
```

### Bước 2: Tạo backend slow

```bash
# Tạo override cho backend3 với delay 30s
cat > docker-compose.override.yml << 'EOF'
version: "3.8"
services:
  backend3:
    environment:
      DELAY: "30"
EOF

docker compose up -d backend3
```

### Bước 3: Gửi request và đo thời gian

```bash
# Gửi request và đo thời gian
time curl -v http://localhost:8080/ 2>&1 | grep -E "< HTTP|upstream|real"
```

**Output mong đợi:**
```
# Request đến backend3 (slow):
< HTTP/1.1 504 Gateway Time-out
# Thời gian: ~5s (proxy_read_timeout)

# Request đến backend1 hoặc backend2 (fast):
< HTTP/1.1 200 OK
# Thời gian: <100ms
```

### Bước 4: Quan sát error log

```bash
tail -f logs/error.log
```

**Output mong đợi:**
```
[error] upstream timed out (110: Connection timed out) while reading response header
        from upstream, client: 172.x.x.x, server: ,
        request: "GET / HTTP/1.1",
        upstream: "http://172.x.x.3:8080/", host: "localhost:8080"
```

### Bước 5: Thêm timeout vào proxy_next_upstream

```nginx
# Bật retry khi timeout
proxy_next_upstream error timeout http_502 http_503;
```

Sau khi reload, request đến backend3 sẽ timeout sau 5s, rồi retry sang backend1 hoặc backend2.

**Quan sát**: Tổng thời gian request sẽ là ~5s (timeout backend3) + <100ms (backend1/2).

### Bước 6: Cleanup

```bash
rm docker-compose.override.yml
docker compose up -d backend3
docker compose exec nginx nginx -s reload  # restore proxy_read_timeout 10s
```

---

## Scenario 4: Tất Cả Backend Down - 503

**Mục tiêu**: Quan sát 503 khi không còn upstream nào available.

### Bước 1: Dừng tất cả backend

```bash
docker compose stop backend1 backend2 backend3
```

### Bước 2: Gửi request

```bash
curl -v http://localhost:8080/
```

**Output mong đợi:**
```
< HTTP/1.1 503 Service Temporarily Unavailable
<html>
<head><title>503 Service Temporarily Unavailable</title></head>
```

### Bước 3: Quan sát error log

```bash
cat logs/error.log | tail -5
```

**Output mong đợi:**
```
[error] no live upstreams while connecting to upstream,
        client: 172.x.x.x, server: ,
        request: "GET / HTTP/1.1",
        upstream: "http://backend_pool/", host: "localhost:8080"
```

### Bước 4: Thêm backup server

Cập nhật nginx.conf:

```nginx
upstream backend_pool {
    server backend1:8080 max_fails=2 fail_timeout=15s;
    server backend2:8080 max_fails=2 fail_timeout=15s;
    server backend3:8080 max_fails=2 fail_timeout=15s;
    server backend_backup:8080 backup;
}
```

Thêm backup service vào docker-compose.yml:

```yaml
  backend_backup:
    image: python:3.11-slim
    command: >
      python3 -c "
      import http.server, sys
      class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
          self.send_response(200)
          self.send_header('Content-Type', 'text/plain')
          self.end_headers()
          self.wfile.write(b'BACKUP SERVER\n')
        def log_message(self, fmt, *args):
          sys.stderr.write('backup: ' + fmt % args + '\n')
      http.server.HTTPServer(('', 8080), H).serve_forever()
      "
    networks:
      - lab-net
```

```bash
docker compose up -d backend_backup
docker compose exec nginx nginx -s reload

# Với tất cả primary down, backup sẽ nhận traffic
curl http://localhost:8080/
# Output: BACKUP SERVER
```

### Bước 5: Khôi phục primary backends

```bash
docker compose start backend1 backend2 backend3

# Sau fail_timeout, primary backends sẽ được thử lại
# Backup sẽ ngừng nhận traffic khi primary sống lại
```

---

## Scenario 5: Connection Refused - 502

**Mục tiêu**: Quan sát 502 khi port không có service nào đang listen.

### Bước 1: Thêm upstream trỏ đến port không tồn tại

Cập nhật nginx.conf:

```nginx
upstream backend_pool {
    server backend1:8080 max_fails=2 fail_timeout=15s;
    server backend2:8080 max_fails=2 fail_timeout=15s;
    server backend3:8080 max_fails=2 fail_timeout=15s;
    server backend1:9999 max_fails=2 fail_timeout=15s;  # Port không tồn tại
}
```

```bash
docker compose exec nginx nginx -s reload
```

### Bước 2: Gửi nhiều request

```bash
for i in $(seq 1 20); do
  curl -s -w "[HTTP %{http_code}] upstream=%header{X-Upstream-Addr}\n" \
    http://localhost:8080/ | tail -1
done
```

**Output mong đợi:**
```
[HTTP 200] upstream=172.x.x.1:8080
[HTTP 200] upstream=172.x.x.2:8080
[HTTP 200] upstream=172.x.x.3:8080
[HTTP 200] upstream=172.x.x.1:9999, 172.x.x.1:8080  ← retry sau ECONNREFUSED
[HTTP 200] upstream=172.x.x.2:8080
...
# Sau 2 lần thất bại, backend1:9999 bị đánh dấu down
# Không còn 502 nữa
```

### Bước 3: Quan sát error log

```bash
grep "Connection refused" logs/error.log | tail -5
```

**Output mong đợi:**
```
connect() failed (111: Connection refused) while connecting to upstream,
upstream: "http://172.x.x.1:9999/"
```

---

## Scenario 6 (Nâng cao): Phân tích max_fails/fail_timeout Effect

**Mục tiêu**: So sánh behavior với các giá trị max_fails khác nhau.

### Bước 1: Test với max_fails=1

```nginx
upstream backend_pool {
    server backend1:8080 max_fails=1 fail_timeout=30s;
    server backend2:8080 max_fails=1 fail_timeout=30s;
    server backend3:8080 max_fails=1 fail_timeout=30s;
}
```

```bash
docker compose exec nginx nginx -s reload
docker compose stop backend1

# Đếm số 502 trước khi backend1 bị đánh dấu down
for i in $(seq 1 10); do
  curl -s -w "[HTTP %{http_code}]\n" http://localhost:8080/ | tail -1
done
```

**Kết quả**: Chỉ 1 request thất bại trước khi backend1 bị đánh dấu down.

### Bước 2: Test với max_fails=5

```nginx
upstream backend_pool {
    server backend1:8080 max_fails=5 fail_timeout=30s;
    server backend2:8080 max_fails=5 fail_timeout=30s;
    server backend3:8080 max_fails=5 fail_timeout=30s;
}
```

```bash
docker compose start backend1
docker compose exec nginx nginx -s reload
docker compose stop backend1

for i in $(seq 1 20); do
  curl -s -w "[HTTP %{http_code}]\n" http://localhost:8080/ | tail -1
done
```

**Kết quả**: 5 request thất bại trước khi backend1 bị đánh dấu down.

### Bảng so sánh kết quả

| max_fails | Số request thất bại | Thời gian phát hiện | False positive risk |
|---|---|---|---|
| 1 | 1 | Rất nhanh | Cao |
| 2 | 2 | Nhanh | Trung bình |
| 3 | 3 | Trung bình | Thấp |
| 5 | 5 | Chậm | Rất thấp |

---

## Cleanup

```bash
# Dừng và xóa tất cả container
docker compose down -v

# Xóa thư mục lab (tùy chọn)
# cd .. && rm -rf day04-lab
```

---

## Tổng kết Exercises

| Scenario | HTTP Status quan sát | Nguyên nhân | Cơ chế xử lý |
|---|---|---|---|
| Kill 1 backend | 502 → 200 | ECONNREFUSED | passive health check + proxy_next_upstream |
| Backend trả 500 | 500 hoặc 200 | Application error | proxy_next_upstream http_500 |
| Backend slow | 504 | proxy_read_timeout hết | timeout + retry |
| Tất cả backend down | 503 | no live upstreams | backup server |
| Port không tồn tại | 502 → 200 | ECONNREFUSED | passive health check |
