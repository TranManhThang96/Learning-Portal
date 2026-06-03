# Day 07: Nginx Performance Tuning & Benchmark

> **Thời lượng**: 2 giờ
> **Độ khó**: ⭐⭐⭐⭐
> **Prerequisites**: Day 1 (Reverse Proxy), Day 2 (Nginx Architecture), Day 3 (Load Balancing), Day 4 (Health Check), Day 5 (TLS/HTTP2), Day 6 (Rate Limiting)

---

## 1. Learning Objectives

Sau bài này, bạn sẽ có thể:

- Benchmark Nginx bằng `wrk`, `hey`, `vegeta` và đọc kết quả p50/p95/p99 đúng cách
- Tune các tham số Nginx-level: `worker_processes`, `worker_connections`, upstream `keepalive`, buffer
- Tune system-level: `ulimit`, `sysctl` (somaxconn, tcp_tw_reuse, ip_local_port_range)
- Phân loại bottleneck: CPU-bound, I/O-bound, connection-bound, network-bound
- Thiết kế capacity planning sơ bộ với headroom 30-50%
- Tránh anti-pattern: copy-paste config tuning mà không đo trước/sau

---

## 2. The Problem

> Hệ thống đang phục vụ **5.000 RPS** ổn định, latency p95 = 200ms. Sau khi bật feature flag mới (thêm một bước gọi internal service), lưu lượng tăng lên **8.000 RPS**, p95 nhảy lên **1.5s**, xuất hiện **2% lỗi 502**. Backend team khẳng định service của họ vẫn healthy. Bạn được giao nhiệm vụ: **tune Nginx mà không thay đổi backend**.
>
> Bạn bắt đầu từ đâu?

**Pain points thực tế:**

- Nginx đang dùng config mặc định từ lúc cài đặt, chưa bao giờ được tune
- `worker_connections 1024` — quá thấp cho 8.000 RPS với keepalive
- Upstream `keepalive` chưa bật → mỗi request tạo TCP connection mới đến backend
- `access_log` ghi mỗi request xuống disk → I/O bottleneck khi traffic cao
- `net.core.somaxconn = 128` (default kernel) → TCP backlog bị drop silently
- `ulimit -n 1024` cho user nginx → file descriptor cạn trước khi worker_connections đạt giới hạn

**Hậu quả nếu không tune đúng:**

- Tăng `worker_connections` lên 65535 nhưng quên `ulimit` → không có tác dụng
- Bật `gzip` cho mọi response → CPU spike, latency tăng với payload nhỏ
- Tắt `access_log` hoàn toàn → mất khả năng debug production incident
- Copy-paste sysctl từ blog mà không hiểu → có thể gây instability trên kernel cũ

---

## 3. Core Concepts

### 3.1 Tại sao Nginx cần tuning?

**Analogy**: Nginx mặc định giống như một chiếc xe hơi xuất xưởng với cài đặt "an toàn cho mọi người". Nó chạy được, nhưng chưa được tối ưu cho đường đua. Tuning là quá trình điều chỉnh từng thông số để phù hợp với workload cụ thể của bạn.

Nginx có 3 tầng cần tune đồng bộ:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx Tuning Layers                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 3: Nginx Config                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ worker_processes, worker_connections, keepalive,        │    │
│  │ buffers, gzip, sendfile, open_file_cache, access_log    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         ▲                                        │
│  Layer 2: OS / Kernel                                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ulimit -n, net.core.somaxconn, tcp_tw_reuse,            │    │
│  │ ip_local_port_range, fs.file-max, rmem/wmem             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         ▲                                        │
│  Layer 1: Hardware                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ CPU cores, NIC throughput, disk IOPS, RAM               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Nguyên tắc: tune từ dưới lên. Layer trên không thể vượt        │
│  giới hạn của layer dưới.                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Bottleneck Taxonomy

Trước khi tune, phải biết bottleneck nằm ở đâu. Có 5 loại chính:

| Loại | Triệu chứng | Detect bằng | Giải pháp |
|---|---|---|---|
| CPU-bound | CPU 100%, latency tăng đều | `top`, `htop` | Tắt gzip, giảm TLS overhead, thêm core |
| I/O-bound | iowait cao, disk busy | `iostat -x 1` | Tắt/buffer access_log, dùng tmpfs |
| Connection-bound | 502 tăng, TIME_WAIT nhiều | `ss -s`, `netstat` | Tăng worker_connections, ulimit, port range |
| Network-bound | NIC saturation, packet drop | `iftop`, `ethtool` | Tăng bandwidth, tune NIC queue |
| Lock contention | CPU cao nhưng throughput thấp | `perf top` | Tắt accept_mutex, dùng SO_REUSEPORT |

### 3.3 Benchmark Tools — Strengths & Weaknesses

```
┌──────────────┬──────────────────────────────┬──────────────────────────────┐
│ Tool         │ Strengths                    │ Weaknesses                   │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ wrk          │ Nhanh, nhẹ, Lua scripting    │ Không có rate control,       │
│              │ HTTP/1.1, keepalive tốt      │ không có percentile chi tiết │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ hey          │ Đơn giản, có p99, rate limit │ Single binary, ít tùy chọn   │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ vegeta       │ Rate-based (RPS cố định),    │ Cần pipe, phức tạp hơn       │
│              │ HDR histogram, tốt nhất cho  │                              │
│              │ coordinated omission         │                              │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ k6           │ JavaScript scripting, CI/CD  │ Nặng hơn, cần Node runtime   │
│              │ friendly, thresholds         │                              │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ h2load       │ HTTP/2 native, multiplexing  │ Chỉ HTTP/2, ít dùng cho HTTP │
├──────────────┼──────────────────────────────┼──────────────────────────────┤
│ ab           │ Có sẵn, đơn giản             │ Không có percentile, cũ,     │
│              │                              │ coordinated omission nặng    │
└──────────────┴──────────────────────────────┴──────────────────────────────┘
```

**Coordinated Omission Problem**: `ab` và `wrk` (ở chế độ mặc định) chỉ gửi request tiếp theo sau khi nhận response. Nếu server chậm, tool "nghỉ" theo server → latency đo được thấp hơn thực tế. `vegeta` với rate cố định tránh được vấn đề này vì nó gửi request theo lịch, không phụ thuộc response.

**Vì sao mean latency là metric tệ**: Mean bị kéo bởi outlier. Nếu 99% request trả về 10ms nhưng 1% trả về 10s, mean = ~110ms — không phản ánh trải nghiệm thực tế. Luôn dùng p95/p99.

---

## 4. How It Works Internally

### 4.1 Worker Process Model & CPU Affinity

Nginx dùng multi-process model: 1 master + N workers. Mỗi worker là single-threaded, chạy event loop (epoll trên Linux). Không có shared state giữa workers (ngoại trừ shared memory zone cho rate limiting, cache).

```
Master Process (PID 1)
├── Worker 0  ──► epoll → handle connections on CPU 0
├── Worker 1  ──► epoll → handle connections on CPU 1
├── Worker 2  ──► epoll → handle connections on CPU 2
└── Worker 3  ──► epoll → handle connections on CPU 3

worker_processes auto;          # = số CPU logical
worker_cpu_affinity auto;       # pin mỗi worker vào 1 CPU core
```

**Vì sao epoll thay vì thread?** Thread có overhead: context switch (~1-10µs), stack memory (~8MB/thread), lock contention. Epoll là I/O multiplexing: 1 thread quản lý hàng nghìn connection bằng cách chỉ xử lý connection khi có event (data ready). Với workload I/O-bound (network), epoll hiệu quả hơn thread pool nhiều lần.

### 4.2 Connection Lifecycle & worker_connections

```
Client TCP SYN
    │
    ▼
Kernel TCP backlog (net.core.somaxconn)
    │
    ▼
Nginx accept() ──► Worker nhận connection
    │
    ├── Đọc request headers (proxy_buffer_size)
    ├── Forward đến upstream (upstream keepalive pool)
    ├── Đọc response (proxy_buffers)
    └── Gửi response về client
```

**Công thức max_clients cho reverse proxy:**

```
max_clients = worker_processes × worker_connections / 2
```

Chia 2 vì mỗi proxied request cần 2 file descriptor: 1 cho client connection, 1 cho upstream connection.

**Ví dụ**: 4 workers × 4096 connections / 2 = **8192 concurrent clients**.

### 4.3 Upstream Keepalive — Tại sao quan trọng?

Không có upstream keepalive:
```
Request 1: Client → Nginx → [TCP SYN] → Backend → [TCP FIN] → Done
Request 2: Client → Nginx → [TCP SYN] → Backend → [TCP FIN] → Done
```
Mỗi request tốn 3-way handshake (~0.5-1ms trên LAN, ~10-50ms qua WAN).

Với upstream keepalive:
```
Request 1: Client → Nginx → [TCP SYN] → Backend → [giữ connection]
Request 2: Client → Nginx → [reuse connection] → Backend → Done
Request N: Client → Nginx → [reuse connection] → Backend → Done
```

```nginx
upstream backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    keepalive 32;          # giữ tối đa 32 idle connections mỗi worker
    keepalive_requests 1000;  # sau 1000 request, đóng và mở lại
    keepalive_timeout 60s;    # idle timeout
}

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;          # BẮT BUỘC cho keepalive
        proxy_set_header Connection "";  # BẮT BUỘC: xóa "Connection: close"
    }
}
```

### 4.4 Proxy Buffering — Trade-off Memory vs Latency

```
proxy_buffering on (default):
  Client ──► Nginx ──► Backend
                │
                ▼
         Buffer response vào RAM
         (proxy_buffers × proxy_buffer_size)
                │
                ▼
         Gửi về client khi buffer đầy hoặc response xong
         Backend connection được giải phóng sớm

proxy_buffering off:
  Client ──► Nginx ──► Backend
                │
                ▼ (streaming, real-time)
         Forward từng byte ngay lập tức
         Backend connection giữ đến khi client nhận xong
```

**Khi nào tắt buffering?** Streaming response (SSE, chunked transfer), WebSocket, response rất lớn (file download). Khi bật buffering với slow client (mobile 3G), backend connection được giải phóng sớm → backend không bị giữ chờ client chậm.

### 4.5 SO_REUSEPORT & accept_mutex

Trước kernel 3.9: tất cả workers cùng `accept()` trên 1 socket → lock contention → `accept_mutex on` để serialize.

Từ kernel 3.9+: `SO_REUSEPORT` cho phép mỗi worker có socket riêng → kernel phân phối connection → không cần mutex:

```nginx
listen 80 reuseport;   # kernel ≥ 3.9
# worker_processes auto;
# accept_mutex off;    # mặc định off khi dùng reuseport
```

---

## 5. Hands-on Lab

### 5.1 Setup Docker Compose

Tạo file `docker-compose.yml`:

```yaml
version: "3.9"
services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "8080:8080"  # stub_status
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend1
      - backend2
      - backend3

  backend1:
    image: python:3.11-alpine
    command: >
      sh -c "pip install flask -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(host=os.environ.get('HOSTNAME','b1'), delay=delay)
app.run(host='0.0.0.0', port=8000)
\""
    environment:
      DELAY: "0.01"

  backend2:
    image: python:3.11-alpine
    command: >
      sh -c "pip install flask -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(host=os.environ.get('HOSTNAME','b2'), delay=delay)
app.run(host='0.0.0.0', port=8000)
\""
    environment:
      DELAY: "0.01"

  backend3:
    image: python:3.11-alpine
    command: >
      sh -c "pip install flask -q &&
             python -c \"
from flask import Flask, jsonify
import time, os
app = Flask(__name__)
@app.route('/')
def hello():
    delay = float(os.environ.get('DELAY', 0))
    time.sleep(delay)
    return jsonify(host=os.environ.get('HOSTNAME','b3'), delay=delay)
app.run(host='0.0.0.0', port=8000)
\""
    environment:
      DELAY: "0.01"
```

### 5.2 Nginx Config — Baseline (chưa tune)

```nginx
# nginx.conf — BASELINE (chưa tune)
worker_processes 1;
events {
    worker_connections 1024;
}
http {
    upstream backend {
        server backend1:8000;
        server backend2:8000;
        server backend3:8000;
        # KHÔNG có keepalive
    }
    server {
        listen 80;
        access_log /var/log/nginx/access.log;  # ghi mỗi request
        location / {
            proxy_pass http://backend;
            proxy_http_version 1.0;  # HTTP/1.0 = không keepalive
        }
    }
}
```

### 5.3 Chạy Benchmark Baseline

```bash
# Khởi động
docker compose up -d

# Cài wrk (Ubuntu/Debian)
apt-get install -y wrk

# Hoặc dùng Docker image
docker run --rm --network host williamyeh/wrk \
  -t4 -c200 -d30s http://localhost/

# Baseline benchmark: 4 threads, 200 connections, 30 giây
wrk -t4 -c200 -d30s --latency http://localhost/
```

Output mẫu (baseline — chưa tune):
```
Running 30s test @ http://localhost/
  4 threads and 200 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    45.23ms   18.45ms 312.00ms   87.34%
    Req/Sec   1.12k     234.56    1.89k    72.00%
  Latency Distribution
     50%   38.12ms
     75%   52.34ms
     90%   71.23ms
     99%  145.67ms
  134,234 requests in 30.10s, 28.45MB read
Requests/sec:   4,460.93
Transfer/sec:      0.95MB
```

### 5.4 Iteration Tuning — Từng bước

**Iteration 1: Tăng worker_processes + worker_connections**

```nginx
worker_processes auto;          # = số CPU cores
worker_rlimit_nofile 65535;     # file descriptor limit cho worker

events {
    worker_connections 4096;    # tăng từ 1024
    use epoll;                  # explicit (Linux)
    multi_accept on;            # accept nhiều connection mỗi lần
}
```

Đồng thời tune OS:
```bash
# Tăng file descriptor limit
ulimit -n 65535

# Hoặc trong /etc/security/limits.conf:
# nginx soft nofile 65535
# nginx hard nofile 65535

# Tăng listen backlog
sysctl -w net.core.somaxconn=65535
sysctl -w net.core.netdev_max_backlog=65535
```

**Iteration 2: Bật upstream keepalive**

```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
    keepalive 64;              # 64 idle connections mỗi worker
    keepalive_requests 10000;
    keepalive_timeout 75s;
}

location / {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

**Iteration 3: Tắt/buffer access_log**

```nginx
# Option A: Tắt hoàn toàn (production: không khuyến nghị)
access_log off;

# Option B: Buffer (khuyến nghị — giảm I/O, vẫn có log)
access_log /var/log/nginx/access.log combined buffer=64k flush=5s;
```

**Iteration 4: Tune TCP & sendfile**

```nginx
http {
    sendfile        on;    # dùng sendfile() syscall, bypass userspace copy
    tcp_nopush      on;    # gom nhiều packet thành 1 (dùng với sendfile)
    tcp_nodelay     on;    # disable Nagle algorithm cho keepalive connection
    keepalive_timeout 65;
    keepalive_requests 10000;
}
```

**Iteration 5: Bật gzip (chỉ cho payload lớn)**

```nginx
gzip on;
gzip_comp_level 4;          # 1-9, level 4 là sweet spot CPU vs ratio
gzip_min_length 1024;       # chỉ compress response ≥ 1KB
gzip_types text/plain text/css application/json application/javascript
           text/xml application/xml application/xml+rss text/javascript;
gzip_vary on;
gzip_proxied any;
```

**Iteration 6: open_file_cache (cho static files)**

```nginx
open_file_cache max=10000 inactive=30s;
open_file_cache_valid 60s;
open_file_cache_min_uses 2;
open_file_cache_errors on;
```

### 5.5 Kết quả So sánh (mẫu tham khảo)

> **Disclaimer**: Số liệu dưới đây chỉ mang tính minh họa. Kết quả thực tế phụ thuộc vào hardware, kernel version, network topology, payload size, TLS on/off, và workload pattern.

| Iteration | RPS | p50 | p95 | p99 | Error% |
|---|---:|---:|---:|---:|---:|
| Baseline | ~4,460 | 38ms | 71ms | 146ms | 0% |
| +worker_processes auto | ~6,200 | 28ms | 55ms | 110ms | 0% |
| +upstream keepalive | ~9,800 | 18ms | 35ms | 72ms | 0% |
| +buffer access_log | ~10,500 | 17ms | 33ms | 68ms | 0% |
| +sendfile+tcp_nopush | ~10,800 | 16ms | 31ms | 65ms | 0% |

**Quan sát quan trọng**: Upstream keepalive mang lại cải thiện lớn nhất (~58% tăng RPS). Đây là tuning có ROI cao nhất cho reverse proxy workload.

### 5.6 Verify với stub_status

```nginx
server {
    listen 8080;
    location /nginx_status {
        stub_status;
        allow 127.0.0.1;
        deny all;
    }
}
```

```bash
curl http://localhost:8080/nginx_status
```

Output:
```
Active connections: 847
server accepts handled requests
 1234567 1234567 5678901
Reading: 12 Writing: 835 Waiting: 0
```

- **Active connections**: tổng connection đang mở (reading + writing + waiting)
- **accepts/handled**: nếu handled < accepts → kernel đang drop connection (backlog đầy)
- **Waiting**: keepalive idle connections
- **Reading**: đang đọc request headers
- **Writing**: đang gửi response

---

## 6. Trade-offs Analysis

### 6.1 Performance vs Observability

| Tùy chọn | RPS Impact | Observability | Khi nào dùng |
|---|---|---|---|
| `access_log off` | +5-15% | Mất hoàn toàn | Không khuyến nghị production |
| `access_log ... buffer=64k flush=5s` | +3-8% | Đầy đủ, delay 5s | Production (khuyến nghị) |
| `access_log` mặc định (sync) | Baseline | Đầy đủ, real-time | Dev/staging |
| `error_log warn` | Tốt | Chỉ warn+ | Production |
| `error_log info` | -10-20% | Rất chi tiết | Debug only — gây massive I/O |

### 6.2 Buffering vs Latency vs Memory

| Cấu hình | Latency | Memory | Backend Connection | Khi nào dùng |
|---|---|---|---|---|
| `proxy_buffering on` (default) | Thấp hơn với slow client | Cao hơn | Giải phóng sớm | API thông thường |
| `proxy_buffering off` | Thấp hơn với fast client | Thấp | Giữ đến khi client nhận xong | Streaming, SSE, WebSocket |
| Buffer lớn (`proxy_buffers 16 64k`) | Tốt với response lớn | Cao | Giải phóng rất sớm | File download, large JSON |
| Buffer nhỏ (default `8 4k`) | Tốt với response nhỏ | Thấp | Giải phóng sớm | Microservice API nhỏ |

### 6.3 Keepalive Trade-offs

| Cấu hình | Latency | Resource | Complexity | Khi nào dùng |
|---|---|---|---|---|
| Không keepalive | Cao (TCP handshake mỗi request) | Thấp | Đơn giản | Không bao giờ với reverse proxy |
| `keepalive 32` | Thấp | Trung bình | Trung bình | API gateway thông thường |
| `keepalive 256` | Rất thấp | Cao (nhiều idle socket) | Cao | High-traffic, backend ổn định |
| `keepalive_timeout` ngắn (10s) | Trung bình | Thấp | Trung bình | Backend có connection limit thấp |
| `keepalive_timeout` dài (300s) | Thấp | Cao | Trung bình | Backend ổn định, traffic đều |

### 6.4 worker_processes: auto vs fixed

| Cấu hình | Pros | Cons |
|---|---|---|
| `worker_processes auto` | Tự động theo CPU, đơn giản | Có thể dùng hết CPU nếu cùng host với app khác |
| `worker_processes 4` (fixed) | Predictable, dễ capacity plan | Phải update khi scale up server |
| `worker_cpu_affinity auto` | Giảm cache miss, tốt với NUMA | Cần kernel hỗ trợ, phức tạp hơn |

**Khuyến nghị**: Dùng `auto` + `worker_cpu_affinity auto` trên dedicated Nginx server. Dùng fixed number nếu Nginx chạy cùng host với application.

### 6.5 gzip: CPU vs Bandwidth

| Payload | gzip_comp_level | CPU Cost | Bandwidth Saving | Verdict |
|---|---|---|---|---|
| JSON < 1KB | Bất kỳ | Cao (overhead > saving) | Nhỏ | Không nên bật |
| JSON 1-10KB | 4-6 | Trung bình | 60-70% | Nên bật |
| JSON > 10KB | 4 | Thấp (relative) | 70-80% | Bật, level 4 |
| Binary/image | Bất kỳ | Cao | Gần 0% | Không bao giờ bật |

---

## 7. Best Practices & Best Solution

### 7.1 Production-Ready Nginx Config Template

```nginx
# /etc/nginx/nginx.conf — Production tuned
user nginx;
worker_processes auto;
worker_cpu_affinity auto;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
    # accept_mutex off;  # default off với reuseport
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Logging với buffer
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" $request_time $upstream_response_time';
    access_log /var/log/nginx/access.log main buffer=64k flush=5s;

    # TCP optimization
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;

    # Keepalive
    keepalive_timeout 65;
    keepalive_requests 10000;

    # Buffers
    client_body_buffer_size     128k;
    client_max_body_size        10m;
    client_header_buffer_size   1k;
    large_client_header_buffers 4 8k;

    # Proxy buffers
    proxy_buffer_size          4k;
    proxy_buffers              8 4k;
    proxy_busy_buffers_size    8k;
    proxy_temp_file_write_size 8k;
    proxy_max_temp_file_size   1024m;

    # Gzip
    gzip on;
    gzip_comp_level 4;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml text/javascript;
    gzip_vary on;
    gzip_proxied any;

    # File cache
    open_file_cache max=10000 inactive=30s;
    open_file_cache_valid 60s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;

    # Upstream
    upstream backend {
        server 10.0.0.1:8000;
        server 10.0.0.2:8000;
        server 10.0.0.3:8000;
        keepalive 64;
        keepalive_requests 10000;
        keepalive_timeout 75s;
    }

    server {
        listen 80 reuseport;
        server_name _;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_connect_timeout 5s;
            proxy_send_timeout    60s;
            proxy_read_timeout    60s;
        }

        location /nginx_status {
            stub_status;
            allow 10.0.0.0/8;
            deny all;
        }
    }
}
```

### 7.2 Anti-patterns Cần Tránh

| Anti-pattern | Vấn đề | Giải pháp |
|---|---|---|
| Copy-paste config từ blog | Không phù hợp workload, có thể gây hại | Profile trước, tune từng bước, đo sau mỗi thay đổi |
| Tăng `worker_connections` mà không tăng `ulimit` | Không có tác dụng | Luôn tune OS và Nginx đồng thời |
| `error_log info` trên production | Massive I/O, disk đầy | Dùng `warn` hoặc `error` |
| `proxy_buffering off` cho mọi endpoint | Backend connection bị giữ bởi slow client | Chỉ tắt cho streaming endpoint |
| `gzip_comp_level 9` | CPU spike, latency tăng | Level 4-6 là sweet spot |
| Không có `proxy_http_version 1.1` khi dùng upstream keepalive | Keepalive không hoạt động | Luôn set cùng `Connection ""` |
| `keepalive` quá lớn (1000+) | Giữ quá nhiều socket idle, tốn FD | 32-128 là đủ cho hầu hết use case |

### 7.3 Quy trình Tuning Đúng

```
1. Đặt baseline metrics (Prometheus/Grafana hoặc wrk output)
2. Identify bottleneck (top/htop/iostat/ss -s)
3. Thay đổi 1 tham số
4. Benchmark lại với cùng điều kiện
5. So sánh p50/p95/p99, RPS, error rate
6. Nếu cải thiện → giữ, tiếp tục bước 2
7. Nếu không cải thiện hoặc tệ hơn → revert
8. Lặp lại
```

---

## 8. Performance Considerations

### 8.1 Benchmark Methodology Đúng

Một benchmark report đầy đủ phải có:

```
Environment:
  OS: Ubuntu 22.04, kernel 5.15.0
  CPU: 4 vCPU (Intel Xeon E5-2686 v4 @ 2.30GHz)
  RAM: 8GB
  Network: Same host (loopback) / Same AZ (1Gbps)

Test Parameters:
  Tool: wrk 4.2.0
  Threads: 4
  Connections: 200
  Duration: 60s (+ 10s warmup)
  Payload: GET /, response ~512B JSON
  TLS: Off
  Keepalive: On (HTTP/1.1)
  Gzip: Off

Results:
  RPS: 9,823
  Latency p50: 18.2ms
  Latency p95: 34.7ms
  Latency p99: 71.3ms
  Latency p999: 145.2ms
  Latency max: 312.4ms
  Throughput: 4.8MB/s
  Error rate: 0%
  CPU (Nginx): 78%
  Memory (Nginx): 45MB RSS

Disclaimer: Số liệu chỉ tham khảo. Kết quả thực tế phụ thuộc vào
hardware, kernel, network topology, payload size, TLS, logging, plugin.
```

### 8.2 Các Tình huống Performance Thường Gặp

**Tình huống 1: Tăng worker_connections lên 100k nhưng connection không vượt 28k**

Nguyên nhân: `ulimit -n` của user nginx vẫn là 1024 (default). Mỗi connection cần 1 file descriptor. Nginx không thể mở quá `ulimit -n` file descriptors.

```bash
# Kiểm tra
cat /proc/$(pgrep -f "nginx: worker")/limits | grep "open files"

# Fix
worker_rlimit_nofile 65535;  # trong nginx.conf
# VÀ
ulimit -n 65535              # cho user nginx
```

**Tình huống 2: p99 nhảy 100ms khi có cron job chạy**

Nguyên nhân: Cron job chiếm CPU → Nginx worker bị preempt → request đang xử lý bị delay. Đây là "noisy neighbor" problem.

Giải pháp: `worker_cpu_affinity` để pin worker vào CPU riêng, hoặc dùng cgroup để giới hạn CPU của cron job.

**Tình huống 3: Request đầu tiên luôn chậm hơn 50-100ms**

Nguyên nhân: TLS handshake (nếu có HTTPS), DNS resolve, TCP slow start, upstream keepalive pool chưa warm.

Giải pháp: Warmup trước benchmark (10s), dùng `resolver` cache, upstream keepalive.

**Tình huống 4: Slow client (mobile 3G) làm cạn connection pool**

Nguyên nhân: Với `proxy_buffering off`, backend connection bị giữ cho đến khi client nhận xong. Mobile 3G nhận chậm → backend connection bị giữ lâu → pool cạn.

Giải pháp: Bật `proxy_buffering on` (default). Nginx buffer response, giải phóng backend connection ngay, sau đó gửi dần về client.

### 8.3 Capacity Planning Sơ bộ

```
capacity_step_1 = benchmark RPS tại điểm CPU hoặc error rate bắt đầu xấu đi
safe_capacity  = capacity_step_1 × (1 - headroom)

Ví dụ:
  Benchmark tăng tải dần: 4k → 6k → 8k → 10k RPS
  Tại 10k RPS: CPU 85%, p99 tăng gấp 3, error rate 0.5%
  Chọn practical capacity = 8k RPS

  Với headroom 40%:
  Safe operating point = 8k × 0.6 = 4.8k RPS
```

**Lưu ý**: Với Nginx event-driven, công thức CPU cores / latency thường gây hiểu nhầm vì một worker xử lý nhiều connection đồng thời. Capacity planning phải dựa trên load test tăng dần, p95/p99, error rate, CPU, memory, file descriptor và network saturation.

**Headroom rule**: Không bao giờ vận hành > 70% capacity. Giữ 30-50% headroom cho:
- Traffic spike (Black Friday, viral event)
- Background jobs (log rotation, health check)
- Graceful restart (rolling reload)

### 8.4 Detect Bottleneck Commands

```bash
# CPU usage per core
htop  # hoặc: mpstat -P ALL 1

# I/O wait
iostat -x 1 5

# Network
iftop -i eth0
# hoặc: sar -n DEV 1

# TCP connection states
ss -s
# hoặc:
netstat -an | awk '/^tcp/ {print $6}' | sort | uniq -c | sort -rn

# File descriptor usage
cat /proc/$(pgrep -f "nginx: master")/fd | wc -l

# Kernel TCP backlog drops
netstat -s | grep -i "listen"
# hoặc: dmesg | grep -i "TCP: drop open request"

# Nginx stub_status
curl http://localhost:8080/nginx_status
```

---

## 9. Troubleshooting Checklist

### Khi gặp 502/504 tăng đột biến

```
[ ] 1. nginx -T | grep -E "worker_connections|keepalive|timeout"
       → Kiểm tra config đang chạy thực tế

[ ] 2. curl http://localhost:8080/nginx_status
       → Xem Active connections, accepts vs handled

[ ] 3. tail -f /var/log/nginx/error.log
       → Tìm "upstream timed out", "no live upstreams", "connect() failed"

[ ] 4. ss -s
       → Xem TIME_WAIT count (nếu > 10k: port exhaustion)
       → Xem CLOSE_WAIT count (nếu cao: upstream không đóng connection đúng)

[ ] 5. cat /proc/sys/net/core/somaxconn
       → Nếu = 128 (default): tăng lên 65535

[ ] 6. ulimit -n (chạy với user nginx)
       → Nếu = 1024: tăng worker_rlimit_nofile và /etc/security/limits.conf

[ ] 7. dmesg | grep -i "TCP\|backlog\|drop" | tail -20
       → Tìm kernel TCP backlog drop

[ ] 8. top -p $(pgrep -d',' nginx)
       → CPU usage của từng worker

[ ] 9. iostat -x 1 5
       → iowait cao → access_log gây I/O bottleneck

[ ] 10. nginx -t && nginx -T
        → Verify config syntax và dump full config
```

### Khi latency p99 cao bất thường

```
[ ] 1. Kiểm tra upstream_response_time trong access_log
       → Nếu upstream_response_time thấp nhưng request_time cao:
         bottleneck ở Nginx (buffer, gzip, slow client)

[ ] 2. Kiểm tra proxy_buffers có đủ không
       → Nếu response lớn hơn proxy_buffers × proxy_buffer_size:
         spill to disk (proxy_temp_path)

[ ] 3. Kiểm tra gzip_comp_level
       → Level cao (7-9) với payload lớn → CPU spike → latency tăng

[ ] 4. Kiểm tra noisy neighbor
       → htop: có process khác chiếm CPU không?

[ ] 5. Kiểm tra TIME_WAIT và ephemeral port range
       → cat /proc/sys/net/ipv4/ip_local_port_range
       → Nếu range nhỏ (32768-60999): tăng lên 1024-65535
       → sysctl -w net.ipv4.tcp_tw_reuse=1
```

---

## 10. Completion Checklist

Sau bài này, bạn có thể tự đánh giá:

- [ ] Giải thích được tại sao tăng `worker_connections` mà không tăng `ulimit` thì không có tác dụng
- [ ] Configure upstream `keepalive` đúng cú pháp (bao gồm `proxy_http_version 1.1` và `Connection ""`)
- [ ] Chạy được `wrk` benchmark và đọc được p50/p95/p99 từ output `--latency`
- [ ] Phân biệt được 5 loại bottleneck và biết dùng tool nào để detect từng loại
- [ ] Giải thích được coordinated omission problem và tại sao `vegeta` tốt hơn `ab` cho latency measurement
- [ ] Configure `access_log` với buffer thay vì tắt hoàn toàn
- [ ] Đọc được `nginx_status` và giải thích ý nghĩa từng số (Active, Reading, Writing, Waiting)
- [ ] Biết khi nào nên bật/tắt `proxy_buffering`

---

## 11. References

- [Nginx Core Module — worker_processes, worker_connections](https://nginx.org/en/docs/ngx_core_module.html)
- [Nginx HTTP Upstream Module — keepalive](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#keepalive)
- [Nginx Tuning For Best Performance — nginx.com](https://www.nginx.com/blog/tuning-nginx/)
- [Linux TCP Tuning — Cloudflare Blog](https://blog.cloudflare.com/optimizing-tcp-for-high-throughput-and-low-latency/)
- [Coordinated Omission — Gil Tene (HdrHistogram)](https://www.youtube.com/watch?v=lJ8ydIuPFeU)
- [wrk — HTTP benchmarking tool](https://github.com/wg/wrk)
- [vegeta — HTTP load testing tool](https://github.com/tsenart/vegeta)
- [hey — HTTP load generator](https://github.com/rakyll/hey)
- [Nginx stub_status module](https://nginx.org/en/docs/http/ngx_http_stub_status_module.html)
- [Brendan Gregg — Systems Performance (2nd ed.)](https://www.brendangregg.com/systems-performance.html)
- [Linux sysctl tuning — Red Hat Performance Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/monitoring_and_managing_system_status_and_performance/)

---

## Tổng kết Tuần 1: 10 Nguyên tắc Nginx Production

Sau 7 ngày học Nginx, đây là 10 nguyên tắc cốt lõi bạn cần nhớ:

```
┌─────────────────────────────────────────────────────────────────┐
│           10 Nguyên tắc Nginx Production (Tuần 1)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. [Day 1] Nginx là reverse proxy, không phải application      │
│     server. Nó forward request, không xử lý business logic.     │
│                                                                  │
│  2. [Day 2] Event loop + epoll: 1 worker xử lý hàng nghìn       │
│     connection. Không dùng thread per connection.                │
│                                                                  │
│  3. [Day 3] Chọn load balancing algorithm theo workload:         │
│     least_conn cho long-lived request, round-robin cho short.    │
│                                                                  │
│  4. [Day 4] Passive health check chỉ phát hiện lỗi sau khi      │
│     request thất bại. Tune max_fails + fail_timeout cẩn thận.   │
│                                                                  │
│  5. [Day 4] Timeout budget: client > edge > gateway > upstream.  │
│     Không bao giờ để upstream timeout > client timeout.          │
│                                                                  │
│  6. [Day 5] TLS termination tại edge. Không để mỗi service       │
│     tự quản lý certificate. Dùng HSTS + OCSP stapling.          │
│                                                                  │
│  7. [Day 6] Rate limiting bằng leaky bucket (limit_req).         │
│     Luôn có burst nhỏ. Trả 429 sớm hơn là để backend chết.      │
│                                                                  │
│  8. [Day 7] Tune OS trước, Nginx sau. ulimit + sysctl phải       │
│     đồng bộ với worker_rlimit_nofile + worker_connections.       │
│                                                                  │
│  9. [Day 7] Upstream keepalive là tuning có ROI cao nhất.        │
│     Luôn bật cho reverse proxy workload.                         │
│                                                                  │
│  10. [Day 7] Đo trước, tune sau, đo lại. Không bao giờ          │
│      copy-paste config mà không hiểu và không đo.               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Recap

Bài Day 7 đã cover:

- **Benchmark methodology**: wrk/hey/vegeta, p50/p95/p99, coordinated omission, tại sao mean latency là metric tệ
- **Nginx-level tuning**: worker_processes, worker_connections, upstream keepalive, proxy buffering, gzip, open_file_cache, access_log buffering
- **System-level tuning**: ulimit, somaxconn, tcp_tw_reuse, ip_local_port_range — phải tune đồng bộ với Nginx
- **Bottleneck taxonomy**: CPU/I/O/connection/network/lock — detect bằng top/iostat/ss/iftop
- **Trade-offs**: performance vs observability, buffer vs memory, keepalive vs resource
- **Capacity planning**: headroom 30-50%, công thức ước tính RPS
- **10 nguyên tắc Nginx production** — tổng kết tuần 1

---

## Preview Day 8

**Day 8: Kong Architecture & OpenResty Foundation** — Bắt đầu Tuần 2.

Bạn sẽ học:
- Kong được xây dựng trên Nginx + OpenResty (LuaJIT). Hiểu Nginx sâu (tuần 1) là nền tảng để hiểu Kong.
- Kong architecture: Control Plane vs Data Plane, DB-mode vs DB-less mode
- Plugin lifecycle: access, header_filter, body_filter, log phase
- Dựng Kong bằng Docker Compose, tạo Service + Route + Plugin đầu tiên
- Tại sao Kong có thể làm được những gì Nginx không làm được (và ngược lại)

Tuần 2 sẽ nặng về Kong, Lua plugin, declarative config (decK), và production deployment patterns.
