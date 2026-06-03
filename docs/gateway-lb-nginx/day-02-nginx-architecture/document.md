# Document: Nginx Internal Architecture Deep Dive

> Tài liệu này bổ sung cho `lesson.md` - Day 02. Đọc sau khi hoàn thành phần lý thuyết chính.

---

## 1. Master Process - Chi tiết hoạt động

### 1.1 Startup Sequence

```
nginx binary start
    │
    ▼
[1] Parse command line args (-c config, -p prefix, -g directives)
    │
    ▼
[2] Read & parse nginx.conf
    │
    ▼
[3] Validate config (syntax + semantic)
    │
    ▼
[4] Bind listening sockets (port 80, 443, ...)
    │  (cần root privilege hoặc CAP_NET_BIND_SERVICE)
    ▼
[5] Drop privileges (switch to nginx user nếu config user nginx)
    │
    ▼
[6] Spawn worker processes
    │
    ▼
[7] Spawn cache manager process (nếu có proxy_cache)
    │
    ▼
[8] Spawn cache loader process (nếu có proxy_cache)
    │
    ▼
[9] Master enters signal wait loop
```

### 1.2 Signal Handling

| Signal | Nginx shortcut | Hành động |
|---|---|---|
| `SIGTERM` | `nginx -s stop` | Fast shutdown - đóng tất cả connection ngay |
| `SIGQUIT` | `nginx -s quit` | Graceful shutdown - chờ request hiện tại xong |
| `SIGHUP` | `nginx -s reload` | Reload config, graceful restart workers |
| `SIGUSR1` | `nginx -s reopen` | Reopen log files (dùng sau log rotation) |
| `SIGUSR2` | (manual) | Upgrade binary in-place |
| `SIGWINCH` | (manual) | Graceful shutdown workers (dùng khi upgrade) |

### 1.3 Zero-Downtime Reload Chi tiết

```
t=0: Master nhận SIGHUP
     │
t=1: Master đọc config mới, validate
     │  Nếu config lỗi → abort, giữ nguyên workers cũ
     │
t=2: Master spawn workers mới với config mới
     │  Workers mới bắt đầu accept connection
     │
t=3: Master gửi SIGQUIT đến workers cũ
     │  Workers cũ: stop accept connection mới
     │              tiếp tục xử lý request đang có
     │
t=4: Workers cũ drain xong → exit
     │
t=5: Chỉ còn workers mới đang chạy
```

Trong khoảng t=2 đến t=4, cả workers cũ và mới đều đang chạy. Đây là lý do `ps aux | grep nginx` có thể thấy nhiều worker hơn bình thường trong lúc reload.

---

## 2. Worker Process - Event Loop Chi tiết

### 2.1 Event Loop Pseudocode

```c
// Simplified event loop trong Nginx worker
void ngx_worker_process_cycle(ngx_cycle_t *cycle) {
    // Khởi tạo epoll instance
    epoll_fd = epoll_create(MAX_EVENTS);
    
    // Đăng ký listening socket
    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, EPOLLIN);
    
    while (!ngx_quit) {
        // Chờ events (blocking call, nhưng không block request processing)
        n_events = epoll_wait(epoll_fd, events, MAX_EVENTS, timeout_ms);
        
        for (i = 0; i < n_events; i++) {
            if (events[i].fd == listen_fd) {
                // New connection
                client_fd = accept(listen_fd, ...);
                epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, EPOLLIN);
                
            } else if (events[i].events & EPOLLIN) {
                // Data available to read
                ngx_http_read_request(events[i].fd);
                
            } else if (events[i].events & EPOLLOUT) {
                // Socket ready to write
                ngx_http_write_response(events[i].fd);
            }
        }
        
        // Process timers (keepalive timeout, proxy timeout, ...)
        ngx_process_events_and_timers(cycle);
    }
}
```

### 2.2 Tại sao Non-blocking I/O quan trọng

Kịch bản: Worker đang xử lý 1000 connections, upstream của connection #500 chậm (100ms).

**Blocking model (Apache)**:
```
Process #500 blocked 100ms waiting for upstream
→ Process #500 không thể xử lý request khác
→ Cần 1000 processes để handle 1000 connections
→ 1000 × 8MB = 8GB RAM chỉ cho processes
```

**Non-blocking model (Nginx)**:
```
Worker đang chờ upstream của conn #500
→ epoll_wait() trả về event của conn #501 (data ready)
→ Worker xử lý conn #501 ngay
→ Sau 100ms, epoll_wait() trả về event của conn #500 (upstream responded)
→ Worker tiếp tục xử lý conn #500
→ 1 worker xử lý 1000 connections với ~2-4KB/connection
```

### 2.3 epoll Edge-Triggered vs Level-Triggered

Nginx dùng **edge-triggered** (`EPOLLET`) cho performance tốt hơn:

| Mode | Khi nào notify | Nginx dùng |
|---|---|---|
| Level-triggered (LT) | Mỗi lần epoll_wait() nếu data còn | Default, dễ implement |
| Edge-triggered (ET) | Chỉ khi state thay đổi (new data arrives) | Nginx dùng, ít syscall hơn |

Edge-triggered yêu cầu đọc hết data trong một lần (loop cho đến khi `EAGAIN`), nếu không sẽ miss event.

---

## 3. Connection Lifecycle - Chi tiết từng bước

### 3.1 Accept Phase

```
Listening socket (shared giữa tất cả workers)
    │
    ▼
Worker nhận EPOLLIN event trên listening socket
    │
    ▼
accept() → trả về client socket fd
    │
    ▼
Set non-blocking: fcntl(client_fd, F_SETFL, O_NONBLOCK)
    │
    ▼
Đăng ký với epoll: epoll_ctl(EPOLL_CTL_ADD, client_fd, EPOLLIN)
    │
    ▼
Allocate ngx_connection_t structure (~256 bytes)
```

**Accept mutex**: Để tránh thundering herd (tất cả workers cùng wake up khi có connection mới), Nginx dùng accept mutex. Chỉ 1 worker giữ mutex tại một thời điểm và accept connection. Khi `multi_accept on`, worker accept tất cả pending connections trước khi release mutex.

### 3.2 Read Phase

```
EPOLLIN event trên client socket
    │
    ▼
recv() → đọc data vào buffer
    │
    ▼
HTTP parser: parse request line, headers
    │
    ▼
Match server_name (virtual host)
    │
    ▼
Match location block (longest prefix match)
    │
    ▼
Execute location handler (proxy_pass, return, try_files, ...)
```

### 3.3 Upstream Phase (khi proxy_pass)

```
Cần kết nối đến upstream
    │
    ▼
Kiểm tra keepalive pool: có connection idle không?
    │
    ├── Có → reuse connection (skip TCP handshake)
    │
    └── Không → tạo connection mới
                    │
                    ▼
                connect() non-blocking → EINPROGRESS
                    │
                    ▼
                epoll_ctl(EPOLL_CTL_ADD, upstream_fd, EPOLLOUT)
                    │
                    ▼
                EPOLLOUT event → connect() hoàn thành
                    │
                    ▼
                Gửi HTTP request đến upstream
                    │
                    ▼
                EPOLLIN event → đọc response từ upstream
```

### 3.4 Response Phase

```
Đọc response từ upstream vào proxy buffer
    │
    ▼
Nếu response nhỏ (< proxy_buffer_size):
    Buffer toàn bộ response
    Gửi một lần đến client
    │
Nếu response lớn:
    Streaming: đọc từ upstream và ghi đến client đồng thời
    │
    ▼
EPOLLOUT event trên client socket → ghi response
    │
    ▼
Kiểm tra keepalive:
    ├── Client gửi Connection: keep-alive → giữ connection, chờ request tiếp
    └── Client gửi Connection: close → đóng connection
```

### 3.5 Keepalive State Machine

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
[ACCEPT] ──► [READ_REQUEST] ──► [PROCESS] ──► [SEND_RESPONSE]
                                                    │
                                    ┌───────────────┴───────────────┐
                                    │                               │
                                    ▼                               ▼
                              [KEEPALIVE]                       [CLOSE]
                              (chờ request mới)            (giải phóng fd)
                                    │
                              keepalive_timeout
                                    │
                                    ▼
                                [CLOSE]
```

---

## 4. Memory Model

### 4.1 Memory per Connection

```
Mỗi connection trong Nginx cần:
  ngx_connection_t:     ~256 bytes
  ngx_http_request_t:   ~3KB
  Read buffer:          client_header_buffer_size (default 1KB)
  Write buffer:         proxy_buffer_size (default 4KB)
  
Tổng ước tính: ~8-16KB per active connection

So sánh:
  Apache prefork: ~8MB per process (bao gồm cả idle)
  Nginx: ~8-16KB per active connection + ~2MB per worker (base)
```

### 4.2 Memory Pool

Nginx dùng memory pool (arena allocator) thay vì malloc/free cho từng object:

```
Request memory pool:
  - Tạo khi nhận request
  - Tất cả allocation trong request lifecycle dùng pool này
  - Giải phóng toàn bộ khi request kết thúc
  - Không có memory fragmentation
  - Không có memory leak per-request
```

---

## 5. CPU Affinity

### 5.1 worker_cpu_affinity

```nginx
# Tự động bind worker vào CPU core
worker_processes 4;
worker_cpu_affinity auto;

# Manual binding (4 workers, 4 cores)
worker_processes 4;
worker_cpu_affinity 0001 0010 0100 1000;

# Manual binding (2 workers, 4 cores - mỗi worker dùng 2 cores)
worker_processes 2;
worker_cpu_affinity 0101 1010;
```

### 5.2 Tại sao CPU Affinity quan trọng

Không có CPU affinity:
```
Worker 0 chạy trên Core 0 → cache warm
OS scheduler di chuyển Worker 0 sang Core 1 → cache cold → cache miss
→ Performance giảm do cache thrashing
```

Với CPU affinity:
```
Worker 0 luôn chạy trên Core 0 → CPU cache luôn warm
Worker 1 luôn chạy trên Core 1 → CPU cache luôn warm
→ Ít cache miss hơn, performance ổn định hơn
```

---

## 6. Upstream Connection Pool

### 6.1 Keepalive Pool Architecture

```
Worker Process
    │
    ├── Connection Pool (per upstream)
    │       │
    │       ├── Idle connections: [conn1, conn2, ..., connN]
    │       │   (N = keepalive directive value)
    │       │
    │       └── Active connections: [conn_a, conn_b, ...]
    │
    └── Event Loop
```

### 6.2 Pool Lifecycle

```
Request cần upstream connection:
    │
    ▼
Kiểm tra idle pool
    │
    ├── Pool có idle connection
    │       │
    │       ▼
    │   Lấy connection từ pool
    │   Gửi request
    │   Nhận response
    │   Trả connection về pool (nếu upstream gửi Connection: keep-alive)
    │
    └── Pool rỗng hoặc pool đầy (tất cả đang active)
            │
            ▼
        Tạo TCP connection mới
        Gửi request
        Nhận response
        Nếu pool chưa đầy → thêm vào pool
        Nếu pool đầy → đóng connection
```

### 6.3 Tuning keepalive Pool Size

```
Công thức ước tính:
  keepalive_pool_size = (requests_per_second × avg_upstream_latency_ms) / 1000

Ví dụ:
  RPS = 1000 req/s
  Upstream latency = 50ms
  keepalive = 1000 × 0.05 = 50 connections

Thực tế nên set cao hơn 20-30% để có buffer:
  keepalive = 64
```

---

## 7. Diagrams Tổng hợp

### 7.1 Full Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NGINX PROCESS TREE                          │
│                                                                     │
│  nginx: master process /usr/sbin/nginx -c /etc/nginx/nginx.conf     │
│  │                                                                  │
│  ├── nginx: worker process                                          │
│  │   │                                                              │
│  │   │  ┌──────────────────────────────────────────────────────┐   │
│  │   │  │                  EVENT LOOP                          │   │
│  │   │  │                                                      │   │
│  │   │  │  epoll_wait() ◄──────────────────────────────────┐  │   │
│  │   │  │       │                                          │  │   │
│  │   │  │       ▼                                          │  │   │
│  │   │  │  [client events]  [upstream events]  [timers]   │  │   │
│  │   │  │       │                  │               │       │  │   │
│  │   │  │       ▼                  ▼               ▼       │  │   │
│  │   │  │  accept/read/write  read/write      keepalive   │  │   │
│  │   │  │                                    timeout      │  │   │
│  │   │  │                                                  │  │   │
│  │   │  │  register new events ────────────────────────────┘  │   │
│  │   │  └──────────────────────────────────────────────────────┘   │
│  │   │                                                              │
│  ├── nginx: worker process                                          │
│  ├── nginx: worker process                                          │
│  └── nginx: cache manager process                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Request Flow với Upstream Keepalive

```
Client          Nginx Worker          Upstream Pool          Upstream Server
  │                  │                     │                       │
  │──HTTP Request───►│                     │                       │
  │                  │──check pool────────►│                       │
  │                  │◄─idle conn──────────│                       │
  │                  │──HTTP Request───────────────────────────────►│
  │                  │◄─HTTP Response──────────────────────────────│
  │◄─HTTP Response───│                     │                       │
  │                  │──return to pool────►│                       │
  │                  │                     │                       │
  │──HTTP Request 2─►│                     │                       │
  │                  │──check pool────────►│                       │
  │                  │◄─idle conn──────────│                       │
  │                  │──HTTP Request 2─────────────────────────────►│
  │                  │◄─HTTP Response 2────────────────────────────│
  │◄─HTTP Response 2─│                     │                       │
```

---

## 8. Kernel Parameters liên quan

```bash
# Xem current values
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_max_syn_backlog
sysctl net.ipv4.ip_local_port_range
sysctl net.ipv4.tcp_tw_reuse
sysctl fs.file-max

# Recommended values cho high-traffic server
net.core.somaxconn = 65535          # listen() backlog
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535  # ephemeral ports
net.ipv4.tcp_tw_reuse = 1           # reuse TIME_WAIT sockets
net.ipv4.tcp_fin_timeout = 15       # giảm TIME_WAIT duration
fs.file-max = 2097152               # system-wide fd limit

# Apply persistent (thêm vào /etc/sysctl.conf)
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
sysctl -p
```

---

## 9. Nginx vs Apache: Khi nào dùng cái nào

| Tiêu chí | Nginx | Apache |
|---|---|---|
| Static file serving | Tốt hơn | Tốt |
| High concurrency (>1K) | Tốt hơn nhiều | Kém hơn |
| PHP (mod_php) | Không hỗ trợ | Hỗ trợ native |
| PHP (PHP-FPM) | Tốt | Tốt |
| .htaccess | Không hỗ trợ | Hỗ trợ |
| Dynamic config reload | Tốt | Tốt |
| Module ecosystem | Nhỏ hơn | Lớn hơn |
| Memory với 10K idle conns | ~20MB | ~80GB |
| Config syntax | Đơn giản hơn | Phức tạp hơn |
| Reverse proxy | Tốt | Tốt (mod_proxy) |
| WebSocket | Tốt | Tốt (mod_proxy_wstunnel) |

**Kết luận**: Với microservices và high-concurrency API proxy, Nginx là lựa chọn tốt hơn. Apache phù hợp hơn cho legacy PHP apps dùng mod_php hoặc khi cần .htaccess per-directory config.
