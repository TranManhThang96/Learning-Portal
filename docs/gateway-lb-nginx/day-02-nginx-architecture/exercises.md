# Exercises: Day 02 - Nginx Architecture Hands-on Labs

> Thực hiện sau khi đọc `lesson.md`. Các lab dùng Docker Compose và shell tương thích bash.
> Để giữ đúng khung 2 giờ: làm Lab 1, 2, 4 và 7; Lab 3, 5, 6 là phần mở rộng nếu còn thời gian.

---

## Setup môi trường

```bash
# Tạo thư mục làm việc
export LAB_DIR="${LAB_DIR:-$HOME/nginx-lab/day02}"
mkdir -p "$LAB_DIR"
cd "$LAB_DIR"

# Kiểm tra Docker
docker --version
docker compose version
```

### docker-compose.yml dùng chung

Tạo các file cấu hình dưới đây trong `$LAB_DIR`.

```yaml
# $LAB_DIR/docker-compose.yml
services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
    depends_on:
      - app1
      - app2
    networks:
      - lab-net

  app1:
    image: nginx:1.25-alpine
    volumes:
      - ./app1.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - lab-net

  app2:
    image: nginx:1.25-alpine
    volumes:
      - ./app2.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - lab-net

networks:
  lab-net:
    driver: bridge
```

```nginx
# $LAB_DIR/app1.conf
server {
    listen 80;
    location / {
        default_type application/json;
        return 200 '{"server": "app1", "pid": "$pid"}\n';
    }
}
```

```nginx
# $LAB_DIR/app2.conf
server {
    listen 80;
    location / {
        default_type application/json;
        return 200 '{"server": "app2", "pid": "$pid"}\n';
    }
}
```

---

## Lab 1: Inspect Master/Worker Processes

**Mục tiêu**: Quan sát process tree của Nginx, hiểu master/worker relationship.

### Bước 1: Tạo config cơ bản

```nginx
# $LAB_DIR/nginx.conf
user nginx;
worker_processes 2;
worker_rlimit_nofile 1024;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 256;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        keepalive 16;
    }

    server {
        listen 80;
        access_log /var/log/nginx/access.log;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }
}
```

### Bước 2: Khởi động và inspect

```bash
cd "$LAB_DIR"
mkdir -p logs
cp nginx.conf nginx-base.conf

# Khởi động
docker compose up -d

# Xem process tree trong container
docker compose exec nginx ps aux

# Output mong đợi:
# PID   USER     COMMAND
# 1     root     nginx: master process nginx -g daemon off;
# 7     nginx    nginx: worker process
# 8     nginx    nginx: worker process
```

```bash
# Xem chi tiết hơn với pstree (nếu có)
docker compose exec nginx sh -c "apk add --no-cache psmisc 2>/dev/null; pstree -p"

# Xem file descriptors của master process
docker compose exec nginx sh -c "ls -la /proc/1/fd | head -20"

# Xem limits của worker process
docker compose exec nginx sh -c "cat /proc/\$(pgrep -f 'nginx: worker' | head -1)/limits"
```

### Bước 3: Kiểm tra worker_rlimit_nofile

```bash
# Xem open file limit của worker
docker compose exec nginx sh -c "
  WORKER_PID=\$(pgrep -f 'nginx: worker' | head -1)
  echo 'Worker PID:' \$WORKER_PID
  cat /proc/\$WORKER_PID/limits | grep 'open files'
"

# Output mong đợi:
# Max open files  1024  1024  files
```

**Câu hỏi**: Tại sao master process chạy với user root nhưng worker process chạy với user nginx?

**Trả lời**: Master cần bind port 80/443 (< 1024 cần root). Sau khi bind xong, worker được spawn với user nginx để giảm attack surface.

---

## Lab 2: Observe Worker Reload Behavior

**Mục tiêu**: Quan sát zero-downtime reload, thấy workers cũ và mới cùng tồn tại.

### Bước 1: Watch processes trong terminal riêng

```bash
# Terminal 1: Watch processes liên tục
docker compose exec nginx sh -c "while true; do ps aux | grep nginx; echo '---'; sleep 1; done"
```

### Bước 2: Gửi traffic liên tục

```bash
# Terminal 2: Gửi request liên tục
while true; do
  curl -s http://localhost:8080/ && sleep 0.1
done
```

### Bước 3: Trigger reload

```bash
# Terminal 3: Reload config
docker compose exec nginx nginx -s reload

# Quan sát Terminal 1: sẽ thấy momentarily có 4 worker processes
# (2 cũ đang drain + 2 mới đang serve)
```

### Bước 4: Thay đổi worker_processes và reload

```bash
# Sửa nginx.conf trên host: đổi worker_processes 2 thành worker_processes 3
sed -i.bak 's/worker_processes 2/worker_processes 3/' "$LAB_DIR/nginx.conf"

# Reload
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Kiểm tra: bây giờ phải có 3 worker processes
docker compose exec nginx ps aux | grep worker
```

### Bước 5: Test config trước khi reload

```bash
# Luôn test config trước khi reload trong production
docker compose exec nginx nginx -t

# Output mong đợi:
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

---

## Lab 3: Test worker_connections Limit

**Mục tiêu**: Thấy lỗi khi worker_connections bị exhausted.

### Bước 1: Set worker_connections rất thấp

```nginx
# Sửa nginx.conf: đặt worker_connections = 4 (rất thấp để dễ test)
# worker_processes 1;
# worker_connections 4;
```

```bash
# Tạo config với limit thấp
cat > "$LAB_DIR/nginx-low-conn.conf" << 'EOF'
user nginx;
worker_processes 1;
worker_rlimit_nofile 64;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
    }

    server {
        listen 80;
        access_log /var/log/nginx/access.log;

        location / {
            proxy_pass http://backend;
            proxy_connect_timeout 5s;
            proxy_read_timeout 5s;
        }
    }
}
EOF

cp "$LAB_DIR/nginx-low-conn.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
```

### Bước 2: Gửi nhiều concurrent requests

```bash
# Cần cài wrk hoặc dùng curl parallel
# Option 1: Dùng curl với background jobs
for i in $(seq 1 20); do
  curl -s http://localhost:8080/ &
done
wait

# Option 2: Dùng wrk (nếu có)
# wrk -t2 -c20 -d10s http://localhost:8080/
```

### Bước 3: Quan sát error log

```bash
# Xem error log
docker compose exec nginx tail -f /var/log/nginx/error.log

# Mong đợi thấy:
# [alert] ... worker_connections are not enough
# hoặc
# [error] ... accept() failed (24: Too many open files)
```

### Bước 4: Restore config bình thường

```bash
cp "$LAB_DIR/nginx-base.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -s reload
```

---

## Lab 4: Benchmark Upstream Keepalive On vs Off

**Mục tiêu**: Đo lường ảnh hưởng của upstream keepalive lên latency và throughput.

### Bước 1: Cài wrk trong container test

```bash
# Chạy wrk từ container test cùng Docker network với stack
docker run --rm \
  --network "$(basename "$LAB_DIR")_lab-net" \
  williamyeh/wrk \
  -t4 -c100 -d30s --latency http://nginx/

# Hoặc dùng hey (Go-based load tester)
# docker run --rm --network "$(basename "$LAB_DIR")_lab-net" \
#   rakyll/hey -n 10000 -c 100 http://nginx/
```

### Bước 2: Config Keepalive OFF

```nginx
# $LAB_DIR/nginx-no-keepalive.conf
user nginx;
worker_processes 2;
worker_rlimit_nofile 4096;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        # KHÔNG có keepalive directive
    }

    server {
        listen 80;
        access_log off;  # tắt log để không ảnh hưởng benchmark

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.0;  # HTTP/1.0 = no keepalive
        }
    }
}
```

```bash
cp "$LAB_DIR/nginx-no-keepalive.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Chạy benchmark (từ container wrk hoặc host)
# Nếu dùng wrk từ host (cần cài wrk):
# wrk -t4 -c100 -d30s --latency http://localhost:8080/

# Nếu dùng curl để đo thủ công:
time for i in $(seq 1 100); do curl -s http://localhost:8080/ > /dev/null; done
```

### Bước 3: Config Keepalive ON

```nginx
# $LAB_DIR/nginx-with-keepalive.conf
user nginx;
worker_processes 2;
worker_rlimit_nofile 4096;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        keepalive 32;           # connection pool
        keepalive_requests 1000;
        keepalive_timeout 60s;
    }

    server {
        listen 80;
        access_log off;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;    # bắt buộc cho keepalive
            proxy_set_header Connection "";  # xóa Connection header
        }
    }
}
```

```bash
cp "$LAB_DIR/nginx-with-keepalive.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Chạy cùng benchmark
time for i in $(seq 1 100); do curl -s http://localhost:8080/ > /dev/null; done
```

### Bước 4: So sánh kết quả

```bash
# Xem TIME_WAIT connections (nhiều = keepalive off hoặc pool nhỏ)
docker compose exec nginx sh -c "ss -s"

# Xem active connections
docker compose exec nginx sh -c "ss -tn | grep :80 | wc -l"

# Xem nginx status (nếu có stub_status)
curl http://localhost:8080/nginx_status 2>/dev/null || echo "stub_status not configured"
```

**Kết quả mong đợi**:
- Keepalive OFF: nhiều TIME_WAIT connections, latency cao hơn
- Keepalive ON: ít TIME_WAIT, latency thấp hơn, throughput cao hơn

> **Lưu ý**: Sự khác biệt rõ nhất khi upstream latency thấp (< 10ms). Khi upstream latency cao (> 100ms), overhead TCP handshake ít ảnh hưởng hơn.

---

## Lab 5: Stress Test - worker_connections Exhausted

**Mục tiêu**: Quan sát behavior khi worker_connections bị exhausted dưới load thực tế.

### Bước 1: Config với limit vừa phải

```nginx
# $LAB_DIR/nginx-stress.conf
user nginx;
worker_processes 1;
worker_rlimit_nofile 256;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 64;  # limit thấp để dễ exhaust
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        keepalive 8;
    }

    server {
        listen 80;
        access_log /var/log/nginx/access.log;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_connect_timeout 2s;
            proxy_read_timeout 2s;
        }

        # Thêm endpoint slow để giữ connection lâu hơn
        location /slow {
            proxy_pass http://backend/;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_read_timeout 30s;
        }
    }
}
```

```bash
cp "$LAB_DIR/nginx-stress.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
```

### Bước 2: Gửi concurrent requests

```bash
# Gửi 100 concurrent requests
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/ &
done
wait

# Đếm số lỗi 502/503
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/ &
done | sort | uniq -c
```

### Bước 3: Quan sát error log

```bash
# Xem errors
docker compose exec nginx tail -20 /var/log/nginx/error.log

# Mong đợi thấy:
# [alert] ... worker_connections are not enough while connecting to upstream
# [error] ... connect() failed (111: Connection refused) while connecting to upstream
```

### Bước 4: Tăng limit và so sánh

```bash
# Sửa worker_connections lên 256 trên host rồi reload
sed -i.bak \
  -e 's/worker_connections 64/worker_connections 256/' \
  -e 's/worker_rlimit_nofile 256/worker_rlimit_nofile 512/' \
  "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Chạy lại test
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/ &
done | sort | uniq -c
```

---

## Lab 6: Tune worker_processes - auto vs Fixed

**Mục tiêu**: Hiểu ảnh hưởng của worker_processes lên CPU utilization.

### Bước 1: Kiểm tra số CPU trong container

```bash
# Xem số CPU available
docker compose exec nginx nproc
docker compose exec nginx sh -c "cat /proc/cpuinfo | grep processor | wc -l"
```

### Bước 2: Test với worker_processes = 1

```bash
cat > "$LAB_DIR/nginx-1worker.conf" << 'EOF'
user nginx;
worker_processes 1;
worker_rlimit_nofile 4096;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        keepalive 32;
    }

    server {
        listen 80;
        access_log off;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }
}
EOF

cp "$LAB_DIR/nginx-1worker.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Benchmark
echo "=== 1 worker ==="
time for i in $(seq 1 200); do curl -s http://localhost:8080/ > /dev/null; done
```

### Bước 3: Test với worker_processes = auto

```bash
cat > "$LAB_DIR/nginx-auto-worker.conf" << 'EOF'
user nginx;
worker_processes auto;
worker_rlimit_nofile 4096;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    upstream backend {
        server app1:80;
        server app2:80;
        keepalive 32;
    }

    server {
        listen 80;
        access_log off;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }
}
EOF

cp "$LAB_DIR/nginx-auto-worker.conf" "$LAB_DIR/nginx.conf"
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# Xem số workers được spawn
docker compose exec nginx ps aux | grep worker | wc -l

# Benchmark
echo "=== auto workers ==="
time for i in $(seq 1 200); do curl -s http://localhost:8080/ > /dev/null; done
```

### Bước 4: Monitor CPU usage

```bash
# Terminal 1: Monitor CPU
docker stats "$(docker compose ps -q nginx)" --no-stream

# Terminal 2: Gửi load
for i in $(seq 1 500); do
  curl -s http://localhost:8080/ > /dev/null &
done
wait
```

**Quan sát**: Với sequential requests (không concurrent), 1 worker và auto worker có performance tương đương. Sự khác biệt rõ khi có nhiều concurrent requests.

---

## Lab 7: Add stub_status để Monitor

**Mục tiêu**: Bật Nginx status page để monitor active connections.

```nginx
# Thêm vào server block trong nginx.conf
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    allow 172.0.0.0/8;  # Docker network
    deny all;
}
```

```bash
# Validate và reload sau khi thêm location /nginx_status
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

# Xem status
curl http://localhost:8080/nginx_status

# Output mong đợi:
# Active connections: 3
# server accepts handled requests
#  150 150 300
# Reading: 0 Writing: 1 Waiting: 2

# Giải thích:
# Active connections: tổng connections đang active
# accepts: tổng connections đã accept
# handled: tổng connections đã xử lý (= accepts nếu không drop)
# requests: tổng HTTP requests
# Reading: đang đọc request header
# Writing: đang gửi response
# Waiting: keepalive connections đang idle
```

```bash
# Monitor liên tục
watch -n1 "curl -s http://localhost:8080/nginx_status"

# Trong terminal khác, gửi requests
for i in $(seq 1 50); do curl -s http://localhost:8080/ > /dev/null & done
```

---

## Cleanup

```bash
cd "$LAB_DIR"
docker compose down

# Xóa logs
rm -rf logs/

# Xóa config files tạm
rm -f nginx-*.conf
```

---

## Challenge: Tính toán và Verify

### Challenge 1: Tính max_clients

Cho config sau, tính max concurrent clients:
```nginx
worker_processes 4;
worker_connections 2048;
```

**Trả lời**: max_clients = 4 × 2048 / 2 = 4096 (chia 2 vì proxy cần 2 fd per client)

### Challenge 2: Tính worker_rlimit_nofile cần thiết

Cho:
- worker_connections = 4096
- Nginx mở thêm ~100 file descriptors cho log, config, etc.

**Trả lời**: worker_rlimit_nofile >= 4096 × 2 + 100 = 8292 → set 10000 để có buffer

### Challenge 3: Debug scenario

Error log có:
```
[alert] 15#15: *1 worker_connections are not enough while connecting to upstream
```

Bước debug:
1. Kiểm tra `worker_connections` trong config
2. Kiểm tra `worker_rlimit_nofile` vs `worker_connections × 2`
3. Kiểm tra `ulimit -n` trong container
4. Tính max_clients hiện tại và so với actual traffic
5. Quyết định tăng `worker_connections` hay `worker_processes`
