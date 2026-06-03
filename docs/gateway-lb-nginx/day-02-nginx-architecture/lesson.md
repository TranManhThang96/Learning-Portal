# Day 02: Nginx Architecture - Master/Worker, Event Loop, Connection Lifecycle

> **Thời lượng**: 2 giờ
> **Độ khó**: ⭐⭐⭐
> **Prerequisites**: Day 01 - Reverse Proxy & Traffic Flow Foundation

---

## 1. Learning Objectives

Sau bài này, bạn sẽ có thể:

- Giải thích mô hình master/worker process và trách nhiệm của từng thành phần
- Mô tả event-driven, non-blocking I/O architecture và so sánh với Apache prefork
- Trace connection lifecycle từ accept đến close/keepalive
- Tune `worker_processes`, `worker_connections`, và upstream keepalive đúng cách
- Debug worker_connections exhausted và file descriptor limit
- Benchmark ảnh hưởng của keepalive on/off lên latency và CPU

---

## 2. The Problem

> Hệ thống của bạn đang chạy tốt với 500 concurrent users. Sau khi traffic tăng lên 5,000 concurrent users, Nginx bắt đầu trả về lỗi `502 Bad Gateway` và log xuất hiện `worker_connections are not enough`. Bạn tăng số lượng server lên gấp đôi nhưng vấn đề vẫn còn. Đồng nghiệp suggest "tăng worker_processes lên 16", nhưng server chỉ có 4 CPU và tình hình không cải thiện.

Pain points thực tế:

- Không hiểu tại sao Nginx dùng ít process nhưng handle được nhiều connection
- Không biết `worker_connections` và `worker_processes` liên quan nhau như thế nào
- Không biết tại sao upstream keepalive lại ảnh hưởng đến latency
- Không biết file descriptor limit (`ulimit -n`) liên quan đến connection limit

Nếu thiết kế sai:

- `worker_processes` quá cao → CPU context switch overhead, không cải thiện throughput
- `worker_connections` quá thấp → connection bị từ chối khi traffic cao
- Không bật upstream keepalive → mỗi request tạo TCP connection mới đến upstream, latency tăng
- `ulimit -n` thấp hơn `worker_connections` → Nginx không thể mở đủ file descriptor

---

## 3. Core Concepts

### 3.1 Analogy: Nhà hàng với một bếp trưởng và nhiều phụ bếp

Hãy tưởng tượng Nginx như một nhà hàng:

- **Master process** = Quản lý nhà hàng: không trực tiếp nấu ăn, chỉ quản lý nhân sự, đọc menu (config), và điều phối
- **Worker processes** = Các phụ bếp: thực sự xử lý order (request) từ khách
- **Event loop** = Mỗi phụ bếp có thể xử lý nhiều order cùng lúc bằng cách không đứng chờ từng món mà chuyển sang order khác khi đang chờ nguyên liệu (I/O)
- **Connection** = Order từ khách hàng

### 3.2 Master Process vs Worker Process

```
┌─────────────────────────────────────────────────────────┐
│                    NGINX PROCESS MODEL                   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Master Process (PID 1)              │   │
│  │  - Đọc và validate nginx.conf                    │   │
│  │  - Bind port 80/443 (privileged)                 │   │
│  │  - Spawn/manage worker processes                 │   │
│  │  - Handle signals: reload, stop, upgrade         │   │
│  │  - KHÔNG xử lý request trực tiếp                │   │
│  └──────────────────────────────────────────────────┘   │
│           │              │              │               │
│           ▼              ▼              ▼               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│  │   Worker 0   │ │   Worker 1   │ │   Worker 2   │    │
│  │  (CPU core 0)│ │  (CPU core 1)│ │  (CPU core 2)│    │
│  │              │ │              │ │              │    │
│  │  Event Loop  │ │  Event Loop  │ │  Event Loop  │    │
│  │  epoll/kqueue│ │  epoll/kqueue│ │  epoll/kqueue│    │
│  │              │ │              │ │              │    │
│  │  N conns     │ │  N conns     │ │  N conns     │    │
│  └──────────────┘ └──────────────┘ └──────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Master process** chịu trách nhiệm:
- Đọc config file và validate
- Bind các port (cần root privilege)
- Spawn worker processes
- Nhận và forward signals (`SIGHUP` = reload, `SIGTERM` = graceful stop)
- Monitor worker processes, restart nếu crash
- Zero-downtime reload: spawn worker mới trước khi kill worker cũ

**Worker process** chịu trách nhiệm:
- Accept connection từ client (thông qua shared socket)
- Xử lý HTTP request/response
- Kết nối đến upstream server
- Đọc/ghi file (static content, cache)
- Chạy event loop độc lập, không share state với worker khác

### 3.3 Event-Driven Architecture

Nginx dùng **non-blocking I/O** với **event loop** thay vì model "một thread/process per connection":

```
Apache Prefork Model (blocking):          Nginx Event-Driven Model (non-blocking):
                                          
  Request 1 → Process A (blocked)           ┌─────────────────────────────┐
  Request 2 → Process B (blocked)           │        Worker Process        │
  Request 3 → Process C (blocked)           │                             │
  Request 4 → Process D (blocked)           │  ┌─────────────────────┐   │
  ...                                        │  │     Event Loop      │   │
  Request N → Process N (blocked)           │  │                     │   │
                                            │  │  Conn1 ──► read()   │   │
  Vấn đề: N requests = N processes          │  │  Conn2 ──► write()  │   │
  Memory: N × ~8MB = rất tốn               │  │  Conn3 ──► upstream │   │
                                            │  │  Conn4 ──► keepalive│   │
                                            │  │  ...                │   │
                                            │  │  ConnN ──► accept() │   │
                                            │  └─────────────────────┘   │
                                            │                             │
                                            │  1 process, N connections   │
                                            │  Memory: ~2-4KB/connection  │
                                            └─────────────────────────────┘
```

### 3.4 Event Loop và epoll/kqueue

Nginx sử dụng OS-level event notification:

| OS | Mechanism | Mô tả |
|---|---|---|
| Linux | `epoll` | Scalable I/O event notification, O(1) per event |
| macOS/BSD | `kqueue` | Tương tự epoll trên BSD systems |
| Solaris | `/dev/poll` | Event port mechanism |
| Windows | `select` | Fallback, kém hiệu quả hơn |
| Fallback | `select`/`poll` | O(n) per call, không scale tốt |

`epoll` hoạt động theo cơ chế:
1. Worker đăng ký file descriptor (socket) với kernel
2. Kernel notify worker khi có event (data ready, connection accepted, write buffer available)
3. Worker xử lý event mà không cần polling liên tục

---

## 4. How It Works Internally

### 4.1 Connection Lifecycle

```
Client                    Nginx Worker                  Upstream
  │                           │                            │
  │──── TCP SYN ─────────────►│                            │
  │◄─── TCP SYN-ACK ──────────│                            │
  │──── TCP ACK ─────────────►│  [accept()]                │
  │                           │                            │
  │──── HTTP Request ────────►│  [read() non-blocking]     │
  │                           │  [parse headers]           │
  │                           │  [match location block]    │
  │                           │                            │
  │                           │──── TCP SYN ──────────────►│
  │                           │◄─── TCP SYN-ACK ───────────│
  │                           │──── TCP ACK ──────────────►│
  │                           │──── HTTP Request ─────────►│
  │                           │◄─── HTTP Response ─────────│
  │                           │  [buffer response]         │
  │◄─── HTTP Response ────────│  [write() to client]       │
  │                           │                            │
  │  [keepalive?]             │  [keepalive_timeout]       │
  │──── HTTP Request 2 ──────►│  [reuse upstream conn]     │
  │◄─── HTTP Response 2 ──────│                            │
  │                           │                            │
  │──── TCP FIN ─────────────►│  [close()]                 │
  │◄─── TCP FIN ──────────────│                            │
```

### 4.2 Worker Process khi nhận Reload Signal

```
Time ──────────────────────────────────────────────────────►

Master:  [running]──[SIGHUP]──[read new config]──[spawn new workers]──[signal old workers]──►
                                                        │                      │
Old Workers:  [serving]──────────────────────────────[drain]──[exit]          │
                                                                               │
New Workers:  ────────────────────────────────────[start]──[serving]──────────►
```

Zero-downtime reload: không có request nào bị drop trong quá trình reload.

### 4.3 Tính toán Max Connections

```
max_connections = worker_processes × worker_connections

Nhưng khi làm reverse proxy:
- Mỗi client connection cần 1 file descriptor
- Mỗi upstream connection cần 1 file descriptor
- Vậy: max_clients = worker_processes × worker_connections / 2

Ví dụ:
  worker_processes  4;
  worker_connections 1024;
  → max_clients = 4 × 1024 / 2 = 2048 concurrent clients
```

### 4.4 File Descriptor và ulimit

```
Nginx cần file descriptor cho:
  - Mỗi client connection: 1 fd
  - Mỗi upstream connection: 1 fd
  - Mỗi open file (static content, log): 1 fd
  - Listening socket: 1 fd per port

Công thức:
  required_fds = worker_connections × 2 + số_file_mở_khác

Nếu ulimit -n < worker_connections × 2:
  → "too many open files" error
  → worker_connections bị giới hạn bởi OS, không phải config
```

### 4.5 Upstream Keepalive

Không có upstream keepalive:
```
Request 1: Client → Nginx → [TCP handshake] → Upstream → [TCP close]
Request 2: Client → Nginx → [TCP handshake] → Upstream → [TCP close]
Request 3: Client → Nginx → [TCP handshake] → Upstream → [TCP close]
```

Có upstream keepalive:
```
Request 1: Client → Nginx → [TCP handshake] → Upstream → [keep connection]
Request 2: Client → Nginx ──────────────────► Upstream → [keep connection]
Request 3: Client → Nginx ──────────────────► Upstream → [keep connection]
```

Config upstream keepalive:
```nginx
upstream backend {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    keepalive 32;  # số connection keepalive tối đa trong pool
}

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;           # bắt buộc cho keepalive
        proxy_set_header Connection "";   # xóa Connection: close header
    }
}
```

---

## 5. Hands-on Lab

Xem chi tiết tại `exercises.md`. Tóm tắt các lab:

**Lab 1**: Inspect master/worker processes bằng `ps` và `pstree`
**Lab 2**: Observe worker reload behavior với `nginx -s reload`
**Lab 3**: Test worker_connections limit bằng `wrk`
**Lab 4**: Benchmark upstream keepalive on/off
**Lab 5**: Stress test để thấy worker_connections exhausted
**Lab 6**: Tune worker_processes auto vs fixed

### Quick Start Config

```nginx
# /etc/nginx/nginx.conf - Production-realistic base config
user nginx;
worker_processes auto;           # tự detect số CPU core
worker_rlimit_nofile 65535;      # override ulimit cho worker

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;                   # explicit trên Linux
    multi_accept on;             # accept nhiều connection cùng lúc
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Upstream với keepalive
    upstream backend {
        server app1:8080;
        server app2:8080;
        keepalive 64;            # connection pool size
        keepalive_requests 1000; # max requests per keepalive conn
        keepalive_timeout 60s;   # idle timeout
    }

    server {
        listen 80;

        location /api/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;

            # Timeout budget
            proxy_connect_timeout 5s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }
    }
}
```

---

## 6. Trade-offs Analysis

### 6.1 Apache Prefork vs Nginx Event-Driven vs Hybrid

| Tiêu chí | Apache Prefork | Nginx Event-Driven | Apache Worker/Event |
|---|---|---|---|
| Model | 1 process/request | N connections/worker | Thread pool |
| Memory/connection | ~8MB | ~2-4KB | ~256KB |
| CPU với 10K conns | Rất cao (context switch) | Thấp | Trung bình |
| Blocking I/O | Không ảnh hưởng | Chặn cả worker | Chặn 1 thread |
| Complexity | Thấp | Trung bình | Trung bình |
| PHP compatibility | Tốt (mod_php) | Cần PHP-FPM | Cần PHP-FPM |
| Khi nào dùng | Legacy PHP, đơn giản | High concurrency, proxy | Trung gian |

### 6.2 worker_processes: auto vs Fixed

| Option | Ưu điểm | Nhược điểm | Khi nào dùng |
|---|---|---|---|
| `auto` | Tự adapt theo CPU, đơn giản | Không kiểm soát được | Hầu hết trường hợp |
| Fixed (= CPU cores) | Predictable, dễ debug | Cần update khi thay hardware | Container với CPU limit cố định |
| Fixed (> CPU cores) | Không có lợi ích | Context switch overhead tăng | Không nên dùng |
| Fixed (< CPU cores) | Giảm tải CPU | Không tận dụng hết CPU | Khi muốn dành CPU cho app |

### 6.3 Upstream Keepalive: On vs Off

| Tiêu chí | Keepalive Off | Keepalive On |
|---|---|---|
| Latency | Cao hơn (TCP handshake mỗi request) | Thấp hơn |
| CPU (Nginx) | Cao hơn | Thấp hơn |
| CPU (Upstream) | Cao hơn | Thấp hơn |
| Memory | Thấp hơn | Cao hơn (connection pool) |
| Complexity | Đơn giản | Cần tune pool size |
| Khi nào dùng | Upstream không support keepalive | Hầu hết production |

**Hidden costs và pitfalls:**

- `keepalive` pool quá nhỏ → connection pool exhausted, vẫn phải tạo connection mới
- `keepalive` pool quá lớn → upstream bị overwhelm bởi idle connections
- Không set `proxy_http_version 1.1` → keepalive không hoạt động (HTTP/1.0 default close)
- Không xóa `Connection` header → upstream nhận `Connection: keep-alive` từ client, có thể gây conflict

**Anti-patterns:**

- Tăng `worker_processes` lên 16 trên server 4 CPU → không giúp ích, tăng overhead
- Set `worker_connections 65535` mà không tăng `worker_rlimit_nofile` → bị giới hạn bởi OS
- Dùng `multi_accept off` trên high-traffic server → worker chỉ accept 1 connection mỗi event loop iteration

---

## 7. Best Practices & Best Solution

### Production Config Template

```nginx
# Tuning cho high-concurrency reverse proxy
worker_processes auto;
worker_cpu_affinity auto;        # bind worker vào CPU core cụ thể
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Client keepalive
    keepalive_timeout 65s;
    keepalive_requests 1000;

    # Upstream keepalive
    upstream backend {
        server app1:8080 weight=1;
        server app2:8080 weight=1;
        keepalive 64;
        keepalive_requests 1000;
        keepalive_timeout 60s;
    }

    server {
        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";

            # Timeout budget (client timeout > gateway timeout > upstream timeout)
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
```

### Recommended Solutions theo Use Case

**Use case: High-concurrency API proxy (>10K concurrent connections)**
```
worker_processes = số CPU core
worker_connections = 4096-8192
upstream keepalive = 64-128
worker_rlimit_nofile = worker_connections × 2 + buffer
```

**Use case: Static file serving**
```
worker_processes = số CPU core
worker_connections = 1024-4096
sendfile on; tcp_nopush on;
upstream keepalive = không cần
```

**Use case: Container với CPU limit**
```
worker_processes = 1 hoặc 2 (theo CPU limit)
worker_connections = 1024
Không dùng auto (có thể detect sai số CPU)
```

### Anti-patterns cần tránh

- Không bao giờ set `worker_processes` > số CPU core vật lý
- Không để `worker_rlimit_nofile` thấp hơn `worker_connections × 2`
- Không dùng `proxy_http_version 1.0` khi bật upstream keepalive
- Không set `keepalive_timeout 0` trên high-traffic server (tắt keepalive = tăng TCP overhead)

---

## 8. Performance Considerations

### Benchmark Methodology

```
Tool: wrk
CPU: 4 vCPU
RAM: 8GB
Payload: 1KB JSON response
Duration: 60s
Connections: 200, 500, 1000, 2000
Threads: 4
TLS: Off
Keepalive: On (default với wrk)

Command:
wrk -t4 -c200 -d60s --latency http://localhost/api/health
wrk -t4 -c500 -d60s --latency http://localhost/api/health
wrk -t4 -c1000 -d60s --latency http://localhost/api/health
```

> **Lưu ý**: Số liệu benchmark chỉ dùng để tham khảo. Kết quả thực tế phụ thuộc vào hardware, kernel version, network stack, payload size, TLS, logging và upstream latency.

### Bottlenecks thường gặp

| Bottleneck | Triệu chứng | Cách detect | Cách fix |
|---|---|---|---|
| worker_connections exhausted | `worker_connections are not enough` trong error log | `nginx -V`, check config | Tăng `worker_connections` |
| File descriptor limit | `too many open files` | `ulimit -n`, `/proc/sys/fs/file-max` | Tăng `worker_rlimit_nofile` |
| CPU context switch | CPU cao, throughput không tăng khi thêm worker | `vmstat 1`, `pidstat` | Giảm `worker_processes` về = CPU core |
| Upstream connection pool | Latency cao dù CPU thấp | `netstat -an | grep TIME_WAIT` | Tăng `keepalive` pool size |
| Kernel backlog | Connection drop ở SYN queue | `ss -s`, `netstat -s | grep overflow` | Tăng `net.core.somaxconn`, `net.ipv4.tcp_max_syn_backlog` |

### Tuning Parameters quan trọng

```bash
# OS-level tuning (cần root)
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sysctl -w net.ipv4.tcp_tw_reuse=1
ulimit -n 65535

# Nginx-level
worker_processes auto;
worker_rlimit_nofile 65535;
worker_connections 4096;
```

### Capacity Planning

```
Ước tính max concurrent connections:
  max_clients = worker_processes × worker_connections / 2

Ước tính memory:
  memory ≈ worker_processes × (worker_connections × 2KB) + base_memory

Ví dụ với 4 workers, 4096 connections mỗi worker:
  max_clients = 4 × 4096 / 2 = 8192 concurrent clients
  memory ≈ 4 × (4096 × 2KB) + 50MB ≈ 82MB
```

---

## 9. Troubleshooting Checklist

- [ ] **worker_connections exhausted**: Kiểm tra `error.log` có `worker_connections are not enough`
  ```bash
  tail -f /var/log/nginx/error.log | grep "worker_connections"
  ```

- [ ] **too many open files**: Kiểm tra `ulimit -n` và `worker_rlimit_nofile`
  ```bash
  cat /proc/$(pgrep -f "nginx: worker")/limits | grep "open files"
  ulimit -n
  ```

- [ ] **High CPU với nhiều worker**: Kiểm tra context switch
  ```bash
  vmstat 1 5
  pidstat -u 1 5
  ```

- [ ] **Upstream connection chậm**: Kiểm tra TIME_WAIT connections
  ```bash
  ss -s
  netstat -an | grep TIME_WAIT | wc -l
  ```

- [ ] **Reload không graceful**: Kiểm tra worker process lifecycle
  ```bash
  watch -n1 "ps aux | grep nginx"
  nginx -s reload && ps aux | grep nginx
  ```

- [ ] **Keepalive không hoạt động**: Kiểm tra proxy_http_version và Connection header
  ```bash
  curl -v http://localhost/api/ 2>&1 | grep -E "Connection|HTTP/"
  ```

- [ ] **Kernel backlog overflow**: Kiểm tra SYN queue
  ```bash
  netstat -s | grep -i "syn\|overflow\|listen"
  ss -lnt
  ```

---

## 10. Completion Checklist

- [ ] Giải thích được sự khác biệt giữa master process và worker process
- [ ] Tính được `max_clients` từ `worker_processes` và `worker_connections`
- [ ] Biết tại sao `worker_processes > CPU cores` không cải thiện performance
- [ ] Cấu hình được upstream keepalive với đúng `proxy_http_version 1.1`
- [ ] Chạy được `wrk` benchmark và so sánh keepalive on/off
- [ ] Debug được lỗi `worker_connections are not enough` và `too many open files`
- [ ] Biết cách inspect worker processes bằng `ps` và `pstree`

---

## 11. References

- [Nginx Architecture - Official Docs](https://nginx.org/en/docs/dev/development_guide.html)
- [Inside NGINX: How We Designed for Performance & Scale - Nginx Blog](https://www.nginx.com/blog/inside-nginx-how-we-designed-for-performance-scale/)
- [The Architecture of Open Source Applications: Nginx](https://aosabook.org/en/nginx.html)
- [Nginx Worker Processes Tuning](https://nginx.org/en/docs/ngx_core_module.html#worker_processes)
- [Linux epoll man page](https://man7.org/linux/man-pages/man7/epoll.7.html)
- [Nginx Keepalive Connections to Upstream](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#keepalive)
- [Tuning Nginx for High Performance - Dropbox Engineering](https://dropbox.tech/infrastructure/optimizing-web-servers-for-high-throughput-and-low-latency)

---

## Recap

Hôm nay bạn đã hiểu tại sao Nginx có thể handle hàng nghìn concurrent connections với chỉ vài worker processes: nhờ event-driven, non-blocking I/O với epoll/kqueue. Master process quản lý lifecycle, worker process chạy event loop độc lập. Hai thông số quan trọng nhất là `worker_processes` (= số CPU core) và `worker_connections` (phải đi kèm với `worker_rlimit_nofile`). Upstream keepalive giảm đáng kể latency bằng cách tái sử dụng TCP connection đến upstream.

## Preview Day 03

**Day 03: Load Balancing Algorithms** - Bạn sẽ configure và so sánh các thuật toán round-robin, least_conn, ip_hash, và weighted upstream. Hiểu khi nào dùng thuật toán nào, và tại sao ip_hash có thể gây uneven load distribution trong thực tế.
