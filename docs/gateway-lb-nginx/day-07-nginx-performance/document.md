# Day 07: Reference — Nginx Performance Tuning Parameters & Benchmark Report

> Tài liệu tham khảo chi tiết cho Day 07. Bao gồm: bảng tham số Nginx đầy đủ, sysctl recommendations, và benchmark report mẫu.

---

## 1. Nginx Tuning Parameters — Reference Table

### 1.1 Main Context

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `worker_processes` | 1 | `auto` | Số worker process. `auto` = số CPU logical. Dùng fixed nếu Nginx share host với app. |
| `worker_cpu_affinity` | (none) | `auto` | Pin worker vào CPU core. Giảm cache miss, tốt với NUMA. Cần kernel hỗ trợ. |
| `worker_rlimit_nofile` | (none) | `65535` | File descriptor limit cho worker. Phải ≥ `worker_connections × 2`. |
| `error_log` level | `error` | `warn` | Production: `warn`. Debug: `notice`. Không bao giờ dùng `info` trên production. |

### 1.2 Events Context

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `worker_connections` | 512 | `4096` | Số connection tối đa mỗi worker. `max_clients = workers × connections / 2` (proxy). |
| `use` | (auto) | `epoll` | I/O model. Linux: `epoll`. BSD: `kqueue`. Nginx tự chọn đúng nếu không set. |
| `multi_accept` | `off` | `on` | Accept nhiều connection mỗi lần epoll notify. Tốt với high connection rate. |
| `accept_mutex` | `off` | `off` | Serialize accept(). Không cần với `reuseport`. Chỉ bật nếu kernel < 3.9. |

### 1.3 HTTP Context — TCP & Connection

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `sendfile` | `off` | `on` | Dùng `sendfile()` syscall để gửi file. Bypass userspace copy → giảm CPU và memory copy. |
| `tcp_nopush` | `off` | `on` | Gom nhiều packet thành 1 trước khi gửi. Dùng với `sendfile on`. Giảm số syscall. |
| `tcp_nodelay` | `on` | `on` | Disable Nagle algorithm. Gửi ngay không chờ buffer đầy. Quan trọng với keepalive. |
| `keepalive_timeout` | `75s` | `65s` | Thời gian giữ idle connection với client. Giảm nếu có nhiều concurrent client. |
| `keepalive_requests` | `1000` | `10000` | Số request tối đa trên 1 keepalive connection. Tăng để giảm reconnect overhead. |
| `listen ... reuseport` | (none) | Bật | Mỗi worker có socket riêng. Kernel phân phối connection. Kernel ≥ 3.9. |

### 1.4 HTTP Context — Buffers

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `client_body_buffer_size` | `8k/16k` | `128k` | Buffer cho request body. Nếu body lớn hơn → spill to disk. |
| `client_max_body_size` | `1m` | `10m` | Giới hạn request body size. Trả 413 nếu vượt. |
| `client_header_buffer_size` | `1k` | `1k` | Buffer cho request headers. Tăng nếu có large cookie/JWT. |
| `large_client_header_buffers` | `4 8k` | `4 16k` | Buffer cho large headers (JWT, cookie). |
| `proxy_buffer_size` | `4k/8k` | `4k` | Buffer cho response headers từ upstream. |
| `proxy_buffers` | `8 4k/8k` | `8 4k` | Buffer cho response body. Tổng = `proxy_buffers × proxy_buffer_size`. |
| `proxy_busy_buffers_size` | `8k/16k` | `8k` | Buffer đang gửi về client trong khi vẫn đọc từ upstream. |
| `proxy_temp_file_write_size` | `8k/16k` | `8k` | Chunk size khi ghi temp file (khi buffer đầy). |
| `proxy_max_temp_file_size` | `1024m` | `1024m` | Giới hạn temp file size. Set 0 để disable temp file (response phải fit vào buffer). |

### 1.5 HTTP Context — Proxy

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `proxy_http_version` | `1.0` | `1.1` | BẮT BUỘC để dùng upstream keepalive. HTTP/1.0 không hỗ trợ keepalive. |
| `proxy_set_header Connection` | `""` | `""` | Xóa header `Connection: close` từ client. BẮT BUỘC với upstream keepalive. |
| `proxy_buffering` | `on` | `on` | Buffer response từ upstream. Tắt chỉ cho streaming/SSE/WebSocket. |
| `proxy_request_buffering` | `on` | `on` | Buffer request body trước khi gửi upstream. Tắt cho streaming upload. |
| `proxy_connect_timeout` | `60s` | `5s` | Timeout kết nối đến upstream. Ngắn để fail fast. |
| `proxy_send_timeout` | `60s` | `60s` | Timeout gửi request đến upstream. |
| `proxy_read_timeout` | `60s` | `60s` | Timeout đọc response từ upstream. |

### 1.6 Upstream Context

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `keepalive` | (none) | `32-64` | Số idle connection giữ lại mỗi worker. Tăng nếu traffic cao. |
| `keepalive_requests` | `1000` | `10000` | Số request tối đa trên 1 upstream keepalive connection. |
| `keepalive_timeout` | `60s` | `75s` | Idle timeout cho upstream keepalive connection. |

### 1.7 HTTP Context — Gzip

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `gzip` | `off` | `on` (có điều kiện) | Bật gzip compression. Chỉ bật nếu response ≥ 1KB và là text. |
| `gzip_comp_level` | `1` | `4` | Compression level 1-9. Level 4 là sweet spot CPU vs ratio. |
| `gzip_min_length` | `20` | `1024` | Chỉ compress response ≥ N bytes. Nhỏ hơn thì overhead > saving. |
| `gzip_types` | `text/html` | (xem bên dưới) | MIME types cần compress. Không compress image/binary. |
| `gzip_vary` | `off` | `on` | Thêm `Vary: Accept-Encoding` header. Cần cho CDN/proxy cache. |
| `gzip_proxied` | `off` | `any` | Compress response từ upstream. |
| `gzip_buffers` | `32 4k/16 8k` | (default) | Buffer cho gzip. Thường không cần thay đổi. |

```nginx
gzip_types
    text/plain
    text/css
    text/xml
    text/javascript
    application/json
    application/javascript
    application/xml
    application/xml+rss
    application/atom+xml
    image/svg+xml;
```

### 1.8 HTTP Context — Logging

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `access_log` | `/var/log/nginx/access.log` | `... buffer=64k flush=5s` | Buffer log writes. Giảm I/O syscall. Delay tối đa 5s. |
| `access_log off` | — | Không khuyến nghị | Mất hoàn toàn observability. Chỉ dùng cho benchmark. |
| `error_log` level | `error` | `warn` | Production: `warn`. Không dùng `info` (massive I/O). |

### 1.9 HTTP Context — File Cache

| Directive | Default | Recommended | Giải thích |
|---|---|---|---|
| `open_file_cache max=N inactive=T` | `off` | `max=10000 inactive=30s` | Cache file descriptor, size, mtime. Giảm stat() syscall. |
| `open_file_cache_valid` | `60s` | `60s` | Tần suất revalidate cached entry. |
| `open_file_cache_min_uses` | `1` | `2` | Số lần access tối thiểu để cache. Tránh cache file ít dùng. |
| `open_file_cache_errors` | `off` | `on` | Cache cả lỗi (file not found). Giảm stat() cho 404. |

---

## 2. System-Level Tuning — sysctl & ulimit

### 2.1 sysctl Recommendations

```bash
# /etc/sysctl.d/99-nginx-tuning.conf

# ── TCP Connection Queue ──────────────────────────────────────────
# Số connection tối đa trong listen backlog
# Default: 128 (quá thấp cho production)
net.core.somaxconn = 65535

# Backlog cho SYN queue (trước khi accept)
net.ipv4.tcp_max_syn_backlog = 65535

# NIC receive queue size
net.core.netdev_max_backlog = 65535

# ── Ephemeral Port Range ──────────────────────────────────────────
# Range port cho outbound connection (Nginx → upstream)
# Default: 32768-60999 (28231 ports)
# Tăng để tránh port exhaustion khi nhiều upstream connection
net.ipv4.ip_local_port_range = 1024 65535

# ── TIME_WAIT Handling ────────────────────────────────────────────
# Cho phép reuse TIME_WAIT socket cho new connection
# Safe với NAT. Không dùng tcp_tw_recycle (deprecated, gây bug với NAT)
net.ipv4.tcp_tw_reuse = 1

# Giảm FIN_WAIT2 timeout (default 60s)
net.ipv4.tcp_fin_timeout = 15

# ── Socket Buffer ─────────────────────────────────────────────────
# Max receive buffer size
net.core.rmem_max = 16777216
# Max send buffer size
net.core.wmem_max = 16777216

# TCP receive buffer: min, default, max
net.ipv4.tcp_rmem = 4096 87380 16777216
# TCP send buffer: min, default, max
net.ipv4.tcp_wmem = 4096 65536 16777216

# ── File Descriptor ───────────────────────────────────────────────
# Tổng file descriptor toàn hệ thống
fs.file-max = 2097152

# ── Misc ──────────────────────────────────────────────────────────
# Tắt IPv6 nếu không dùng (giảm overhead)
# net.ipv6.conf.all.disable_ipv6 = 1  # uncomment nếu cần
```

Apply ngay (không cần reboot):
```bash
sysctl -p /etc/sysctl.d/99-nginx-tuning.conf
# hoặc:
sysctl --system
```

### 2.2 ulimit — File Descriptor

```bash
# /etc/security/limits.conf
nginx   soft    nofile  65535
nginx   hard    nofile  65535
root    soft    nofile  65535
root    hard    nofile  65535

# Hoặc trong systemd service file:
# [Service]
# LimitNOFILE=65535
```

Verify:
```bash
# Kiểm tra limit của nginx worker process
cat /proc/$(pgrep -f "nginx: worker" | head -1)/limits | grep "open files"

# Kiểm tra số FD đang dùng
ls /proc/$(pgrep -f "nginx: master")/fd | wc -l
```

### 2.3 Nginx listen Backlog

```nginx
# Phải khớp với net.core.somaxconn
listen 80 backlog=65535;
listen 443 ssl backlog=65535;
```

### 2.4 Tóm tắt: Nginx vs OS Parameter Mapping

```
┌─────────────────────────────────────────────────────────────────┐
│              Nginx ↔ OS Parameter Mapping                        │
├──────────────────────────┬──────────────────────────────────────┤
│ Nginx Parameter          │ OS Parameter cần tune đồng bộ        │
├──────────────────────────┼──────────────────────────────────────┤
│ worker_connections N     │ worker_rlimit_nofile ≥ N×2           │
│                          │ ulimit -n ≥ N×2                      │
│                          │ fs.file-max ≥ workers×N×2            │
├──────────────────────────┼──────────────────────────────────────┤
│ listen 80 backlog=N      │ net.core.somaxconn ≥ N               │
│                          │ net.ipv4.tcp_max_syn_backlog ≥ N     │
├──────────────────────────┼──────────────────────────────────────┤
│ upstream keepalive N     │ net.ipv4.ip_local_port_range (rộng)  │
│                          │ net.ipv4.tcp_tw_reuse = 1            │
└──────────────────────────┴──────────────────────────────────────┘
```

---

## 3. Benchmark Report Mẫu

### 3.1 Template Benchmark Report

```markdown
# Nginx Performance Benchmark Report

## Metadata
- Date: 2024-01-15
- Tester: DevOps Team
- Purpose: Baseline + tuning validation cho production deployment

## Environment

### Hardware
- Machine: AWS EC2 c5.xlarge (4 vCPU, 8GB RAM)
- OS: Ubuntu 22.04 LTS
- Kernel: 5.15.0-1034-aws
- NIC: 10Gbps (ENA)

### Network Topology
- Client và Nginx: cùng host (loopback 127.0.0.1)
- Nginx và Backend: Docker network bridge (172.17.0.0/16)
- Ghi chú: Loopback loại bỏ network latency, kết quả tốt hơn thực tế

### Software
- Nginx: 1.25.3
- Backend: Python Flask 3.0 (3 instances)
- wrk: 4.2.0
- hey: 0.1.4

## Test Scenarios

### Scenario 1: Baseline (config mặc định)

**Config:**
- worker_processes: 1
- worker_connections: 1024
- upstream keepalive: off
- access_log: on (sync)
- gzip: off

**Command:**
```bash
wrk -t4 -c200 -d60s --latency http://127.0.0.1/
```

**Results:**
| Metric | Value |
|---|---|
| RPS | 4,460 |
| Latency p50 | 38.1ms |
| Latency p75 | 52.3ms |
| Latency p90 | 71.2ms |
| Latency p99 | 145.7ms |
| Latency p999 | 289.4ms |
| Latency max | 412.3ms |
| Throughput | 0.95 MB/s |
| Error rate | 0% |
| CPU (Nginx) | 24% (1 core) |
| Memory (Nginx) | 12MB RSS |

### Scenario 2: Sau khi tune (worker + keepalive + buffer log)

**Config:**
- worker_processes: auto (4)
- worker_connections: 4096
- upstream keepalive: 64
- access_log: buffer=64k flush=5s
- gzip: off

**Command:** (giống Scenario 1)

**Results:**
| Metric | Value | Delta vs Baseline |
|---|---|---|
| RPS | 10,823 | +143% |
| Latency p50 | 16.4ms | -57% |
| Latency p75 | 24.1ms | -54% |
| Latency p90 | 33.7ms | -53% |
| Latency p99 | 68.2ms | -53% |
| Latency p999 | 134.5ms | -54% |
| Latency max | 287.1ms | -30% |
| Throughput | 2.31 MB/s | +143% |
| Error rate | 0% | — |
| CPU (Nginx) | 71% (4 cores) | — |
| Memory (Nginx) | 48MB RSS | — |

### Scenario 3: Gzip bật (payload 5KB JSON)

**Config:** Scenario 2 + gzip on, gzip_comp_level 4

**Results:**
| Metric | Value | Delta vs Scenario 2 |
|---|---|---|
| RPS | 9,234 | -15% |
| Latency p50 | 19.2ms | +17% |
| Latency p99 | 78.4ms | +15% |
| Throughput | 1.12 MB/s | -51% (compressed) |
| CPU (Nginx) | 89% | +25% |

**Nhận xét:** Gzip giảm bandwidth 51% nhưng tăng CPU 25% và latency 15-17%.
Với payload 5KB, trade-off có lợi nếu bandwidth là bottleneck.

## Bottleneck Analysis

| Phase | Bottleneck | Evidence | Action |
|---|---|---|---|
| Baseline | Single worker | CPU 24% (1 core), 3 cores idle | worker_processes auto |
| After worker tune | Upstream reconnect | ss -s: TIME_WAIT tăng | upstream keepalive |
| After keepalive | I/O wait | iostat: iowait 8% | buffer access_log |
| After log buffer | CPU (gzip) | top: CPU 89% với gzip | Giảm gzip_comp_level |

## Disclaimer

> Số liệu trong report này chỉ mang tính tham khảo. Kết quả thực tế phụ thuộc vào:
> hardware (CPU model, NIC speed, disk IOPS), kernel version, network topology
> (loopback vs LAN vs WAN), payload size và type, TLS on/off, logging configuration,
> số lượng và loại plugin, và workload pattern (burst vs steady).
> Luôn benchmark trên môi trường gần giống production nhất có thể.
```

---

## 4. Benchmark Tool Quick Reference

### 4.1 wrk

```bash
# Cú pháp cơ bản
wrk -t<threads> -c<connections> -d<duration> --latency <url>

# Ví dụ: 4 threads, 200 connections, 60 giây
wrk -t4 -c200 -d60s --latency http://localhost/

# Với Lua script (POST request)
wrk -t4 -c200 -d60s --latency -s post.lua http://localhost/api/

# post.lua:
# wrk.method = "POST"
# wrk.body   = '{"key":"value"}'
# wrk.headers["Content-Type"] = "application/json"

# Flags:
# -t: số threads (thường = số CPU cores)
# -c: số connections (tổng, chia đều cho threads)
# -d: duration (s/m/h)
# --latency: in percentile distribution
# -H: thêm header
# -s: Lua script
```

### 4.2 hey

```bash
# Cú pháp cơ bản
hey -n <total_requests> -c <concurrency> <url>

# Ví dụ: 100,000 requests, 200 concurrent
hey -n 100000 -c 200 http://localhost/

# Với rate limit (RPS cố định)
hey -n 100000 -c 200 -q 1000 http://localhost/
# -q 1000: tối đa 1000 RPS

# POST request
hey -n 10000 -c 100 -m POST \
    -H "Content-Type: application/json" \
    -d '{"key":"value"}' \
    http://localhost/api/

# Flags:
# -n: tổng số request
# -c: concurrency
# -q: rate limit (RPS)
# -z: duration (thay cho -n)
# -m: HTTP method
# -H: header
# -d: request body
# -t: timeout per request
# -disable-keepalive: tắt keepalive
```

### 4.3 vegeta (rate-based, tránh coordinated omission)

```bash
# Cú pháp: pipe targets vào vegeta attack
echo "GET http://localhost/" | \
  vegeta attack -rate=1000 -duration=60s | \
  vegeta report

# Report với percentile
echo "GET http://localhost/" | \
  vegeta attack -rate=1000 -duration=60s | \
  vegeta report -type=text

# HDR histogram (chi tiết hơn)
echo "GET http://localhost/" | \
  vegeta attack -rate=1000 -duration=60s > results.bin
vegeta report -type=hdrplot < results.bin > histogram.txt

# Targets file (nhiều endpoint)
# targets.txt:
# GET http://localhost/api/users
# GET http://localhost/api/products
vegeta attack -targets=targets.txt -rate=500 -duration=60s | vegeta report

# Flags:
# -rate: RPS (requests per second)
# -duration: thời gian test
# -workers: số goroutine (default: min(CPUs, rate))
# -max-connections: max connections
# -keepalive: bật keepalive (default: true)
# -insecure: skip TLS verify
```

### 4.4 h2load (HTTP/2)

```bash
# HTTP/2 benchmark
h2load -n 100000 -c 100 -m 10 https://localhost/

# Flags:
# -n: tổng requests
# -c: clients (connections)
# -m: max concurrent streams per connection (HTTP/2 multiplexing)
# -t: threads
# --h1: force HTTP/1.1
```

---

## 5. Nginx stub_status — Giải thích Chi tiết

```
Active connections: 847
server accepts handled requests
 1234567 1234567 5678901
Reading: 12 Writing: 835 Waiting: 0
```

| Field | Ý nghĩa | Cảnh báo |
|---|---|---|
| Active connections | Tổng connection đang mở | Nếu gần `worker_connections × workers`: tăng limit |
| accepts | Tổng connection đã accept từ trước đến nay | — |
| handled | Tổng connection đã xử lý | Nếu handled < accepts: kernel drop (backlog đầy) |
| requests | Tổng request đã xử lý | requests/handled = avg requests per connection |
| Reading | Đang đọc request headers | Cao → slow client gửi headers chậm |
| Writing | Đang gửi response | Cao → slow client nhận chậm hoặc backend chậm |
| Waiting | Keepalive idle | Cao → nhiều idle keepalive connection |

**Công thức kiểm tra keepalive hiệu quả:**
```
requests / handled >> 1  →  keepalive đang hoạt động tốt
requests / handled ≈ 1   →  mỗi connection chỉ có 1 request (keepalive không hiệu quả)
```
