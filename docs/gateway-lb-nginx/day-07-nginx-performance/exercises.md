# Day 07: Exercises — Nginx Performance Benchmark Lab

> **Thời lượng ước tính**: 90-120 phút
> **Yêu cầu**: Docker, Docker Compose, wrk hoặc hey

---

## Lab Setup

### Cấu trúc thư mục

```
day-07-nginx-performance/
├── docker-compose.yml
├── nginx/
│   ├── nginx-baseline.conf
│   └── nginx-tuned.conf
└── scripts/
    ├── benchmark.sh
    └── sysctl-tune.sh
```

### Bước 1: Tạo Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - ./nginx/nginx-baseline.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend1
      - backend2
      - backend3
    networks:
      - bench-net

  backend1:
    image: python:3.11-alpine
    environment:
      DELAY: "0.005"
      PORT: "8000"
      HOST_ID: "backend1"
    command: >
      sh -c "pip install flask gunicorn -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
@app.route('/api/test')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(
        host=os.environ.get('HOST_ID','b1'),
        delay=delay,
        status='ok'
    )
app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8000)))
\""
    networks:
      - bench-net

  backend2:
    image: python:3.11-alpine
    environment:
      DELAY: "0.005"
      PORT: "8000"
      HOST_ID: "backend2"
    command: >
      sh -c "pip install flask -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
@app.route('/api/test')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(
        host=os.environ.get('HOST_ID','b2'),
        delay=delay,
        status='ok'
    )
app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8000)))
\""
    networks:
      - bench-net

  backend3:
    image: python:3.11-alpine
    environment:
      DELAY: "0.005"
      PORT: "8000"
      HOST_ID: "backend3"
    command: >
      sh -c "pip install flask -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
@app.route('/api/test')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(
        host=os.environ.get('HOST_ID','b3'),
        delay=delay,
        status='ok'
    )
app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8000)))
\""
    networks:
      - bench-net

networks:
  bench-net:
    driver: bridge
```

### Bước 2: Nginx Baseline Config

```nginx
# nginx/nginx-baseline.conf — CHƯA TUNE (intentionally bad)
worker_processes 1;

events {
    worker_connections 512;
}

http {
    upstream backend {
        server backend1:8000;
        server backend2:8000;
        server backend3:8000;
        # Không có keepalive
    }

    server {
        listen 80;

        # access_log sync (mặc định)
        access_log /var/log/nginx/access.log;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.0;  # HTTP/1.0 = không keepalive
        }
    }

    # stub_status để monitor
    server {
        listen 8080;
        location /nginx_status {
            stub_status;
            allow all;
        }
    }
}
```

### Bước 3: Nginx Tuned Config

```nginx
# nginx/nginx-tuned.conf — ĐÃ TUNE
worker_processes auto;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log warn;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    log_format main '$remote_addr - [$time_local] "$request" '
                    '$status $body_bytes_sent $request_time $upstream_response_time';

    # Buffer access_log thay vì sync
    access_log /var/log/nginx/access.log main buffer=64k flush=5s;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout 65;
    keepalive_requests 10000;

    # Proxy buffers
    proxy_buffer_size   4k;
    proxy_buffers       8 4k;
    proxy_busy_buffers_size 8k;

    # Gzip
    gzip on;
    gzip_comp_level 4;
    gzip_min_length 1024;
    gzip_types application/json text/plain text/css application/javascript;
    gzip_vary on;

    upstream backend {
        server backend1:8000;
        server backend2:8000;
        server backend3:8000;
        keepalive 64;
        keepalive_requests 10000;
        keepalive_timeout 75s;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_connect_timeout 5s;
            proxy_read_timeout 60s;
        }
    }

    server {
        listen 8080;
        location /nginx_status {
            stub_status;
            allow all;
        }
    }
}
```

### Bước 4: Cài wrk

```bash
# Ubuntu/Debian
apt-get update && apt-get install -y wrk

# macOS
brew install wrk

# Hoặc dùng Docker (không cần cài)
alias wrk='docker run --rm --network host williamyeh/wrk'

# Cài hey
# Linux
wget https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -O /usr/local/bin/hey
chmod +x /usr/local/bin/hey

# macOS
brew install hey
```

---

## Exercise 1: Baseline Benchmark

**Mục tiêu**: Đo performance với config mặc định, lấy baseline để so sánh.

```bash
# Khởi động với baseline config
docker compose up -d

# Chờ backend khởi động (Flask cần ~10s)
sleep 15

# Verify hoạt động
curl http://localhost/
# Expected: {"delay":0.005,"host":"backend1","status":"ok"}

# Kiểm tra stub_status
curl http://localhost:8080/nginx_status

# Warmup (10 giây)
wrk -t2 -c50 -d10s http://localhost/ > /dev/null

# Baseline benchmark: 4 threads, 200 connections, 60 giây
wrk -t4 -c200 -d60s --latency http://localhost/
```

**Ghi lại kết quả vào bảng:**

| Metric | Baseline | Iter 1 | Iter 2 | Iter 3 | Iter 4 |
|---|---|---|---|---|---|
| RPS | | | | | |
| p50 | | | | | |
| p95 | | | | | |
| p99 | | | | | |
| Error% | | | | | |

**Câu hỏi kiểm tra:**
1. `accepts` và `handled` trong stub_status có bằng nhau không? Nếu không, tại sao?
2. `Waiting` connections là bao nhiêu? Điều đó nói lên điều gì?
3. CPU usage của Nginx là bao nhiêu? (`docker stats nginx`)

---

## Exercise 2: Tune worker_processes + worker_connections

**Mục tiêu**: Hiểu tác động của multi-worker và connection limit.

```bash
# Sửa nginx-baseline.conf: thay đổi worker_processes và worker_connections
# Hoặc tạo file mới nginx-iter1.conf

# Thay đổi:
# worker_processes 1; → worker_processes auto;
# worker_connections 512; → worker_connections 4096;

# Reload Nginx (không restart, không mất connection)
docker compose exec nginx nginx -s reload

# Verify config đã apply
docker compose exec nginx nginx -T | grep -E "worker_processes|worker_connections"

# Benchmark lại (cùng điều kiện)
wrk -t4 -c200 -d60s --latency http://localhost/
```

**Quan sát:**
```bash
# Xem số worker process
docker compose exec nginx ps aux | grep nginx

# CPU usage theo từng worker
docker stats nginx --no-stream
```

**Câu hỏi:**
1. RPS tăng bao nhiêu % so với baseline?
2. Có bao nhiêu worker process đang chạy?
3. Nếu server có 4 CPU nhưng bạn set `worker_processes 8`, điều gì xảy ra?

---

## Exercise 3: Bật Upstream Keepalive

**Mục tiêu**: Đây là tuning có ROI cao nhất. Quan sát tác động.

```bash
# Thêm vào upstream block:
# keepalive 64;
# keepalive_requests 10000;
# keepalive_timeout 75s;

# Thêm vào location block:
# proxy_http_version 1.1;
# proxy_set_header Connection "";

# Reload
docker compose exec nginx nginx -s reload

# Benchmark
wrk -t4 -c200 -d60s --latency http://localhost/

# Quan sát TIME_WAIT (chạy trong khi benchmark đang chạy)
# Trong container hoặc host:
ss -s | grep -E "TIME-WAIT|ESTABLISHED"
```

**Verify keepalive đang hoạt động:**
```bash
# Trong khi benchmark chạy, xem stub_status
watch -n1 'curl -s http://localhost:8080/nginx_status'

# Tính requests/handled ratio
# Nếu ratio >> 1: keepalive đang hoạt động
```

**Câu hỏi:**
1. RPS tăng bao nhiêu % so với Exercise 2?
2. TIME_WAIT count thay đổi thế nào?
3. Nếu quên set `proxy_http_version 1.1`, keepalive có hoạt động không? Tại sao?

---

## Exercise 4: Buffer access_log

**Mục tiêu**: Giảm I/O overhead từ logging.

```bash
# Thay đổi access_log:
# access_log /var/log/nginx/access.log;
# →
# access_log /var/log/nginx/access.log main buffer=64k flush=5s;

# Reload
docker compose exec nginx nginx -s reload

# Benchmark
wrk -t4 -c200 -d60s --latency http://localhost/

# Quan sát I/O (chạy trong khi benchmark)
# Trong container:
docker compose exec nginx sh -c "while true; do cat /proc/diskstats | grep -v ' 0 0 0 0 0 0 0 0 0 0 0'; sleep 1; done"
```

**Câu hỏi:**
1. RPS thay đổi bao nhiêu?
2. Nếu Nginx crash đột ngột, log trong buffer có bị mất không?
3. Khi nào nên dùng `access_log off` thay vì buffer?

---

## Exercise 5: Tune sysctl (System-Level)

**Mục tiêu**: Hiểu tại sao OS tuning phải đi kèm Nginx tuning.

```bash
# Kiểm tra giá trị hiện tại
sysctl net.core.somaxconn
sysctl net.ipv4.ip_local_port_range
sysctl net.ipv4.tcp_tw_reuse

# Tăng listen backlog
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# Mở rộng ephemeral port range
sysctl -w net.ipv4.ip_local_port_range="1024 65535"

# Bật tcp_tw_reuse
sysctl -w net.ipv4.tcp_tw_reuse=1

# Cập nhật nginx.conf: thêm backlog vào listen
# listen 80 backlog=65535;

# Reload và benchmark
docker compose exec nginx nginx -s reload
wrk -t4 -c200 -d60s --latency http://localhost/
```

**Lưu ý**: Trong Docker container, một số sysctl cần `--privileged` hoặc `--sysctl` flag. Trên host thực, chạy trực tiếp.

**Câu hỏi:**
1. Tại sao `net.core.somaxconn` quan trọng với Nginx?
2. Nếu `ip_local_port_range` quá hẹp, triệu chứng là gì?
3. Tại sao `tcp_tw_recycle` bị deprecated và không nên dùng?

---

## Exercise 6: Test gzip Trade-off

**Mục tiêu**: Hiểu khi nào gzip có lợi và khi nào không.

```bash
# Tạo endpoint trả về payload lớn hơn
# Sửa backend để trả về 5KB JSON

# Test 1: Payload nhỏ (~200B), gzip off
wrk -t4 -c200 -d30s --latency http://localhost/

# Test 2: Payload nhỏ (~200B), gzip on (gzip_min_length 1)
# Sửa nginx.conf: gzip_min_length 1;
docker compose exec nginx nginx -s reload
wrk -t4 -c200 -d30s --latency http://localhost/

# Test 3: Payload lớn (~5KB), gzip on (gzip_min_length 1024)
# Sửa backend DELAY và thêm padding vào response
# Sửa nginx.conf: gzip_min_length 1024;
docker compose exec nginx nginx -s reload
wrk -t4 -c200 -d30s --latency http://localhost/

# Quan sát bandwidth
docker stats nginx --no-stream
```

**Câu hỏi:**
1. Với payload 200B, gzip có cải thiện RPS không? Tại sao?
2. Với payload 5KB, bandwidth giảm bao nhiêu %?
3. `gzip_comp_level 9` vs `4` — khi nào nên dùng level cao?

---

## Exercise 7: Dùng hey với Rate Control

**Mục tiêu**: Benchmark với RPS cố định để tránh coordinated omission.

```bash
# Test với rate cố định: 1000 RPS, 200 concurrent, 60 giây
hey -z 60s -c 200 -q 1000 http://localhost/

# Test với rate cao hơn: 5000 RPS
hey -z 60s -c 500 -q 5000 http://localhost/

# Test không keepalive (để thấy overhead)
hey -z 30s -c 200 -q 1000 -disable-keepalive http://localhost/

# So sánh keepalive vs no-keepalive
echo "=== With keepalive ==="
hey -z 30s -c 200 -q 2000 http://localhost/

echo "=== Without keepalive ==="
hey -z 30s -c 200 -q 2000 -disable-keepalive http://localhost/
```

**Câu hỏi:**
1. Khi rate = 1000 RPS, latency p99 là bao nhiêu?
2. Khi rate = 5000 RPS, latency p99 thay đổi thế nào?
3. Tại sao `hey` với `-q` (rate limit) cho kết quả latency khác với `wrk`?

---

## Exercise 8: Dùng Tuned Config Hoàn Chỉnh

**Mục tiêu**: Apply toàn bộ tuning và so sánh với baseline.

```bash
# Chuyển sang tuned config
docker compose down
# Sửa docker-compose.yml: đổi nginx-baseline.conf → nginx-tuned.conf
docker compose up -d

sleep 15

# Warmup
wrk -t2 -c50 -d10s http://localhost/ > /dev/null

# Final benchmark
wrk -t4 -c200 -d60s --latency http://localhost/

# Điền vào bảng so sánh từ Exercise 1
```

**Tổng kết bảng so sánh:**

| Config | RPS | p50 | p95 | p99 | Ghi chú |
|---|---|---|---|---|---|
| Baseline | | | | | worker=1, no keepalive |
| +worker auto | | | | | 4 workers |
| +upstream keepalive | | | | | keepalive 64 |
| +buffer access_log | | | | | buffer=64k |
| +sendfile+tcp_nopush | | | | | TCP optimization |
| Full tuned | | | | | Tất cả tuning |

---

## Exercise 9: Troubleshooting Scenario

**Mục tiêu**: Thực hành debug khi có vấn đề performance.

### Scenario: Simulate High TIME_WAIT

```bash
# Tắt upstream keepalive (simulate vấn đề)
# Sửa nginx-tuned.conf: comment out keepalive block trong upstream
# Và đổi proxy_http_version về 1.0

docker compose exec nginx nginx -s reload

# Chạy benchmark
wrk -t4 -c200 -d30s --latency http://localhost/ &

# Trong khi benchmark chạy, quan sát
watch -n1 'ss -s | grep -E "TIME-WAIT|estab"'

# Sau benchmark
ss -s
```

**Câu hỏi:**
1. TIME_WAIT count tăng lên bao nhiêu?
2. Nếu `ip_local_port_range` chỉ có 1000 ports và TIME_WAIT = 900, điều gì xảy ra?
3. Làm thế nào để detect vấn đề này trong production?

### Scenario: Simulate ulimit Issue

```bash
# Giả lập ulimit thấp bằng cách giảm worker_connections xuống rất thấp
# worker_connections 10;  (intentionally low)

docker compose exec nginx nginx -s reload

# Benchmark với nhiều connections
wrk -t4 -c500 -d30s --latency http://localhost/

# Quan sát error log
docker compose logs nginx | grep -E "worker_connections|no live upstreams|connect"

# Quan sát stub_status
curl http://localhost:8080/nginx_status
```

**Câu hỏi:**
1. Error rate là bao nhiêu?
2. stub_status cho thấy gì?
3. Làm thế nào để tính `worker_connections` cần thiết cho 10,000 concurrent users?

---

## Exercise 10: Challenge — Capacity Planning

**Mục tiêu**: Tính toán capacity cho production scenario.

**Bài toán:**
- Hệ thống cần phục vụ **20,000 concurrent users**
- Mỗi user gửi trung bình **2 request/giây**
- Average response time: **50ms**
- Server: 8 vCPU, 16GB RAM
- Yêu cầu: headroom 40%

**Tính toán:**

```
1. Peak RPS = 20,000 users × 2 req/s = 40,000 RPS

2. Với headroom 40%:
   Required capacity = 40,000 / 0.6 = 66,667 RPS

3. worker_connections cần thiết:
   Concurrent connections = RPS × avg_response_time
   = 40,000 × 0.05s = 2,000 concurrent connections
   
   Với headroom: 2,000 / 0.6 = 3,334 connections
   
   Per worker (8 workers): 3,334 / 8 = 417 connections/worker
   → worker_connections = 512 (round up to power of 2)

4. upstream keepalive:
   Connections to backend = concurrent_connections / backends
   = 3,334 / 3 = 1,111 per backend
   → keepalive = 128 (giữ 128 idle connections mỗi worker)

5. ulimit:
   FD per worker = worker_connections × 2 = 1,024
   → worker_rlimit_nofile = 4096 (buffer)
```

**Câu hỏi:**
1. Với 8 workers và `worker_connections 512`, max concurrent clients là bao nhiêu?
2. Nếu average response time tăng lên 200ms (backend chậm), concurrent connections cần thiết thay đổi thế nào?
3. Tại sao headroom 40% là quan trọng? Điều gì xảy ra nếu không có headroom?

---

## Kết quả Mong đợi

Sau khi hoàn thành tất cả exercises:

- [ ] Đã chạy baseline benchmark và ghi lại p50/p95/p99
- [ ] Đã tune từng bước và quan sát cải thiện
- [ ] Đã verify upstream keepalive hoạt động qua stub_status ratio
- [ ] Đã thấy tác động của gzip với payload khác nhau
- [ ] Đã simulate và debug TIME_WAIT issue
- [ ] Đã tính toán capacity planning cho production scenario
- [ ] Bảng so sánh đã được điền đầy đủ

## Ghi chú Quan trọng

> Tất cả số liệu benchmark trong lab này chạy trên Docker với loopback network. Kết quả thực tế trên production sẽ khác do: network latency thực, TLS overhead, disk I/O thực, và workload phức tạp hơn. Lab này chỉ để hiểu **tương quan** giữa các tuning parameter, không phải để lấy số liệu tuyệt đối.
