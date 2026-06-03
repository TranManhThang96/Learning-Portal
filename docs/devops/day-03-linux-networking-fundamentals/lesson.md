# Day 3: Linux Networking Fundamentals

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được TCP/IP stack** — từ application layer đến network layer, hiểu rõ TCP handshake, connection states và cách chúng ảnh hưởng đến service behavior.
2. **Debug được DNS resolution** — phân biệt DNS cache, recursive resolver, authoritative nameserver, và xử lý các lỗi DNS phổ biến trong production.
3. **Phân biệt được HTTP/1.1, HTTP/2, HTTP/3** và khi nào chọn protocol nào cho service.
4. **Sử dụng thành thạo Linux networking tools** — `dig`, `nslookup`, `curl`, `ss`, `tcpdump` để debug network issues.
5. **Giải thích được các load balancing algorithms** và trade-offs để chọn strategy phù hợp.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng trong production?

Networking là **lớp nền tảng** của mọi distributed system. Mọi request từ user đến service, mọi communication giữa microservices, mọi query đến database đều đi qua network. Khi network có vấn đề, **mọi thứ** đều bị ảnh hưởng.

### Hậu quả nếu làm sai

| Sai lầm | Hậu quả thực tế |
|---------|-----------------|
| Không hiểu DNS caching | Deploy service mới, cập nhật DNS record nhưng client vẫn gọi IP cũ → 50% traffic đến server đã tắt |
| Không phân biệt connection timeout vs read timeout | Set cùng 1 timeout → hoặc quá ngắn (reject request hợp lệ) hoặc quá dài (giữ connection zombie) |
| Không hiểu ephemeral port | High-traffic service → exhaustion ephemeral ports → "Cannot assign requested address" |
| Chọn sai load balancing algo | Long-lived gRPC connections + round robin → 1 server overload, còn lại idle |

### Liên hệ với kiến thức developer

- **API design**: Bạn đã design REST/gRPC APIs — giờ cần hiểu protocol layer bên dưới ảnh hưởng latency thế nào.
- **Microservices**: Service-to-service call qua network — DNS resolution, connection pooling, timeout đều critical.
- **Redis/Kafka**: Mỗi connection đến Redis = 1 TCP socket = 1 file descriptor (Day 2).

---

## 3. Kiến thức nền tảng

### 3.1. TCP/IP Model

```
┌─────────────────────────────────────────────────┐
│  Application Layer                               │
│  HTTP, gRPC, DNS, SMTP, WebSocket, Kafka protocol│
├─────────────────────────────────────────────────┤
│  Transport Layer                                 │
│  TCP (reliable, ordered) / UDP (fast, no guarantee)│
├─────────────────────────────────────────────────┤
│  Network Layer (Internet)                        │
│  IP (routing), ICMP (ping, traceroute)           │
├─────────────────────────────────────────────────┤
│  Link Layer (Network Access)                     │
│  Ethernet, WiFi, ARP                             │
└─────────────────────────────────────────────────┘
```

**Analogy cho developer**: TCP/IP layers giống middleware stack trong web framework. Mỗi layer xử lý responsibility riêng, truyền data xuống layer dưới (send) hoặc lên layer trên (receive).

### 3.2. TCP Connection Lifecycle

```
Client                          Server
  │                                │
  │─── SYN ───────────────────────>│  Step 1: Client gửi SYN
  │                                │
  │<── SYN-ACK ───────────────────│  Step 2: Server gửi SYN-ACK
  │                                │
  │─── ACK ───────────────────────>│  Step 3: Client gửi ACK
  │                                │          → Connection ESTABLISHED
  │                                │
  │←─── Data exchange ────────────→│  Gửi/nhận data
  │                                │
  │─── FIN ───────────────────────>│  Step 4: Client gửi FIN
  │<── ACK ───────────────────────│  Step 5: Server ACK
  │<── FIN ───────────────────────│  Step 6: Server gửi FIN
  │─── ACK ───────────────────────>│  Step 7: Client ACK
  │                                │          → Connection CLOSED
  │                                │
  │   TIME_WAIT (2×MSL = ~60s)    │  Client giữ state để handle late packets
```

### TCP Connection States quan trọng

| State | Mô tả | Khi nào thấy |
|-------|-------|-------------|
| `LISTEN` | Server đang chờ connection | Service đang chạy, bind port |
| `ESTABLISHED` | Connection active, đang trao đổi data | Normal operation |
| `TIME_WAIT` | Connection đã close, chờ late packets | Sau khi close, tồn tại ~60s |
| `CLOSE_WAIT` | Nhận FIN từ remote nhưng chưa close local | **Bug indicator**: app không close connection |
| `SYN_SENT` | Đã gửi SYN, chờ SYN-ACK | Connect đến server |
| `FIN_WAIT_1/2` | Đã gửi FIN, chờ ACK/FIN | Đang đóng connection |

**Quy tắc debug quan trọng**:
- Nhiều `TIME_WAIT` → bình thường nếu high-traffic, nhưng có thể cần tuning
- Nhiều `CLOSE_WAIT` → **bug trong app**: nhận disconnect nhưng không close socket → fd leak
- Nhiều `SYN_SENT` → server đích không respond → firewall, server down, DNS sai

### 3.3. DNS Resolution Flow

```
User types: api.example.com
         │
         ▼
┌─────────────────┐
│  Local DNS Cache │  ← OS cache (nscd, systemd-resolved)
│  TTL: varies     │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│ Recursive Resolver│  ← ISP DNS, 8.8.8.8, hoặc corporate DNS
│ (may cache)      │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│  Root DNS        │  ← "Ai quản lý .com?"
│  (13 root servers)│
└────────┬────────┘
         │ Referral: .com TLD
         ▼
┌─────────────────┐
│  TLD DNS (.com)  │  ← "Ai quản lý example.com?"
└────────┬────────┘
         │ Referral: ns1.example.com
         ▼
┌─────────────────────┐
│ Authoritative DNS    │  ← "api.example.com = 10.0.1.5"
│ (ns1.example.com)    │
└──────────────────────┘
         │
         ▼
    IP: 10.0.1.5
```

### 3.4. HTTP Protocol Comparison

| Feature | HTTP/1.1 | HTTP/2 | HTTP/3 |
|---------|----------|--------|--------|
| **Transport** | TCP | TCP | QUIC (UDP) |
| **Multiplexing** | Không (1 request/connection, hoặc pipelining kém) | Có (nhiều streams/connection) | Có (stream-level flow control) |
| **Header compression** | Không | HPACK | QPACK |
| **Head-of-line blocking** | TCP level + HTTP level | TCP level only | Không (UDP-based) |
| **Connection setup** | TCP handshake + TLS handshake (2-3 RTT) | Giống HTTP/1.1 | 0-1 RTT (QUIC) |
| **Server push** | Không | Có | Có |
| **Adoption** | Universal | ~50% web | ~25% web (growing) |
| **Khi nào dùng** | Legacy, simple | Default cho web/API | Mobile, lossy network |

### 3.5. Load Balancing Algorithms

| Algorithm | Cách hoạt động | Ưu điểm | Nhược điểm | Phù hợp cho |
|-----------|---------------|---------|------------|-------------|
| **Round Robin** | Lần lượt từng server | Simple, fair distribution | Không biết server load | Stateless, đồng nhất servers |
| **Weighted Round Robin** | Round robin với weight | Heterogeneous servers | Weight cần manual tuning | Servers có capacity khác nhau |
| **Least Connections** | Chọn server ít connection nhất | Load-aware | Không biết request cost | HTTP services, varying request time |
| **IP Hash** | Hash client IP → fixed server | Session persistence | Uneven nếu NAT | Legacy apps cần session affinity |
| **Random** | Chọn ngẫu nhiên | Simple, no state needed | Có thể uneven | Large fleet (>100 servers) |
| **Least Response Time** | Chọn server response nhanh nhất | Performance-aware | Cần health check active | Latency-sensitive services |

### 3.6. NAT, Port, Socket, Ephemeral Port

**Socket** = IP address + port number + protocol. Ví dụ: `TCP 10.0.1.5:8080`.

**Ephemeral port**: Khi client connect, OS tự chọn source port từ range (thường 32768-60999). Mỗi connection dùng 1 ephemeral port.

```
Client (10.0.0.1)                    Server (10.0.1.5:8080)
  :32768 ─────────────────────────── :8080  (connection 1)
  :32769 ─────────────────────────── :8080  (connection 2)
  :32770 ─────────────────────────── :8080  (connection 3)
  ...
  :60999 ─────────────────────────── :8080  (connection ~28000)
  → Hết ephemeral port → "Cannot assign requested address"
```

**Vì sao quan trọng**: High-traffic service gọi nhiều external service → mỗi connection tốn 1 ephemeral port. Cộng thêm `TIME_WAIT` giữ port 60s → dễ exhaustion.

---

## 4. Deep Dive

### 4.1. Connection Timeout vs Read Timeout vs Write Timeout

```
Client                                              Server
  │                                                    │
  │────── Connect (TCP SYN) ─────────────────────────>│
  │        ↑                                           │
  │   Connection Timeout                               │
  │   (thường 3-5s)                                    │
  │        ↓                                           │
  │<───── SYN-ACK ───────────────────────────────────│
  │                                                    │
  │────── HTTP Request ──────────────────────────────>│
  │        ↑                                           │
  │   Write Timeout                                    │  Server đang
  │   (thường 10-30s)                                  │  xử lý request...
  │        ↓                                           │
  │                                                    │
  │        ↑                                           │
  │   Read Timeout                                     │
  │   (thường 30-60s)                                  │
  │        ↓                                           │
  │<───── HTTP Response ─────────────────────────────│
  │                                                    │
```

**Quy tắc thiết lập timeout**:
- **Connection timeout** nên ngắn (3-5s) — nếu server không respond SYN-ACK trong 3s, nó có thể down.
- **Read timeout** phải dài hơn server processing time — nếu API P99 là 5s, read timeout ít nhất 10s.
- **Idle timeout** để close connection không dùng — tiết kiệm fd và memory.

### 4.2. gRPC vs REST Networking

```
REST over HTTP/1.1:
  Client ──── Connection 1 ──── Request A ──── Response A ──── Close
  Client ──── Connection 2 ──── Request B ──── Response B ──── Close
  (mỗi request = 1 TCP connection, hoặc Keep-Alive reuse)

gRPC over HTTP/2:
  Client ──── Connection 1 ──┬── Stream 1: Request A ──── Response A
                             ├── Stream 2: Request B ──── Response B
                             ├── Stream 3: Request C ──── Response C
                             └── Stream N: Request N ──── Response N
  (1 TCP connection, nhiều streams multiplexed)
```

**Implication cho load balancing**: 
- REST/HTTP/1.1 → Round robin hoạt động tốt (mỗi request = connection mới)
- gRPC/HTTP/2 → Round robin KHÔNG hoạt động (1 connection dùng lâu) → cần L7 load balancing hoặc client-side load balancing

### 4.3. DNS trong Kubernetes

```
Pod A (10.244.1.5)                                    Pod B (10.244.2.8)
  │                                                      │
  │  curl http://my-service.my-ns.svc.cluster.local:80   │
  │                                                      │
  ▼                                                      │
CoreDNS (kube-dns)                                       │
  │ Resolves: my-service.my-ns.svc.cluster.local         │
  │        → ClusterIP: 10.96.0.100                      │
  ▼                                                      │
kube-proxy (iptables/IPVS)                               │
  │ DNAT: 10.96.0.100 → 10.244.2.8 (Pod B IP)           │
  │                                                      │
  └──────────────────────────────────────────────────────→│
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1. Connection Pooling vs Connection-per-Request

| Strategy | Ưu điểm | Nhược điểm | Phù hợp cho |
|----------|---------|------------|-------------|
| Connection per request | Simple, no state, clean | TCP handshake overhead lớn | Low-traffic, simple apps |
| Connection pooling | Reuse connections, lower latency | Pool management phức tạp, stale connections | High-traffic production services |
| HTTP/2 multiplexing | 1 connection, nhiều streams | Head-of-line blocking ở TCP layer | gRPC, modern web |

**Best practice**: Connection pool cho database (PostgreSQL pool size = 2 × CPU cores + 1), Redis (pool ~10-50), và HTTP clients.

### 5.2. DNS TTL Trade-offs

| TTL | Ưu điểm | Nhược điểm | Scenario |
|-----|---------|------------|---------|
| 30s | Thay đổi IP nhanh, failover nhanh | Query DNS nhiều, latency tăng | Active-active, frequent changes |
| 300s (5 min) | Cân bằng tốt | Failover chậm hơn | Default cho hầu hết services |
| 3600s (1 hour) | Ít DNS queries, cache hiệu quả | Thay đổi IP mất 1 giờ | Static services, CDN |
| 86400s (1 day) | Cache tối đa | Không flexible | Rarely changing records |

**Best practice cho Kubernetes**: Dùng TTL thấp (30-60s) cho services vì pod IP thay đổi thường xuyên. CoreDNS default là 30s.

### 5.3. Anti-patterns

1. **Không set timeout** → Connection hang forever → thread/goroutine leak → service unresponsive
2. **DNS caching quá lâu trong app** → Java mặc định cache DNS vĩnh viễn! Phải set `-Dsun.net.inetaddr.ttl=60`
3. **Retry without backoff** → Server đang overloaded + 1000 clients retry ngay → cascading failure (retry storm)
4. **Expose database port ra internet** → Security risk, cần VPC/private network
5. **Dùng IP thay DNS** trong config → Không flexible, không failover được

---

## 6. Performance & Scalability ⭐

### 6.1. Performance Implications

| Quyết định | Latency Impact | Throughput Impact |
|-----------|---------------|-------------------|
| HTTP/1.1 → HTTP/2 | Giảm latency (multiplexing, header compression) | Tăng throughput (ít connection hơn) |
| No connection pooling → Pool | Giảm ~1-3ms per request (skip handshake) | Tăng 5-10× cho DB-heavy services |
| DNS TTL 3600s → 60s | Tăng nhẹ (DNS lookup thường xuyên hơn) | Không ảnh hưởng đáng kể |
| TCP keepalive enable | Detect dead connections sớm | Giảm stale connection leak |

### 6.2. Bottleneck thường gặp

- **Ephemeral port exhaustion**: High-traffic client → nhiều short-lived connections → hết port
  ```bash
  # Check ephemeral port range
  cat /proc/sys/net/ipv4/ip_local_port_range
  # Default: 32768 60999 (~28000 ports)
  
  # Check TIME_WAIT connections
  ss -s | grep "timewait"
  ```

- **Connection table full**: `conntrack` table full → packet drop
  ```bash
  cat /proc/sys/net/nf_conntrack_max
  sysctl net.nf_conntrack_max=262144
  ```

- **Socket backlog full**: `somaxconn` quá nhỏ → SYN drop → connection refused
  ```bash
  cat /proc/sys/net/core/somaxconn
  # Default: 128 — quá nhỏ cho production!
  sysctl net.core.somaxconn=65535
  ```

### 6.3. Network Tuning cho high-traffic

```bash
# /etc/sysctl.conf cho production server

# Tăng ephemeral port range
net.ipv4.ip_local_port_range = 10240 65535

# Reuse TIME_WAIT sockets
net.ipv4.tcp_tw_reuse = 1

# Tăng socket backlog
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# Tăng conntrack table
net.nf_conntrack_max = 262144

# TCP keepalive (detect dead connections)
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 3

# Tăng receive/send buffer
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

---

## 7. Security & Reliability Considerations

### Security

- **TLS everywhere**: Mọi communication giữa services cần TLS, kể cả internal. Zero-trust networking.
- **DNS spoofing**: Internal DNS cần DNSSEC hoặc VPC DNS (AWS Route 53 private hosted zone).
- **Port exposure**: Chỉ expose port cần thiết. Dùng NetworkPolicy trong Kubernetes.
- **Rate limiting**: Protect service khỏi DDoS và abuse tại load balancer level.

### Reliability

- **Connection draining**: Khi remove server khỏi load balancer, chờ in-flight requests hoàn thành.
- **Health checks**: Load balancer phải có health check → tự remove unhealthy server.
- **Circuit breaker**: Khi downstream service lỗi, stop gửi request → tránh cascading failure.
- **Retry budget**: Giới hạn retry percentage (e.g., 20% extra traffic) → tránh retry storm.

---

## 8. Hands-on Example

### 8.1. DNS Debugging

```bash
# 1. dig — chi tiết nhất
dig api.example.com
# Output quan trọng:
# ;; ANSWER SECTION:
# api.example.com.  300  IN  A  93.184.216.34
#                   ↑ TTL (giây)

# Query specific DNS server
dig @8.8.8.8 api.example.com

# Trace full resolution path
dig +trace api.example.com

# Chỉ lấy IP
dig +short api.example.com

# Query MX records
dig example.com MX

# Query TXT records (SPF, DKIM)
dig example.com TXT

# 2. nslookup — simple hơn
nslookup api.example.com
nslookup api.example.com 8.8.8.8

# 3. host — đơn giản nhất
host api.example.com

# 4. Kiểm tra DNS resolution time
time dig api.example.com > /dev/null
# real    0m0.025s  ← cached
# real    0m0.150s  ← not cached, đi qua resolver

# 5. Clear DNS cache (systemd-resolved, nếu máy dùng systemd)
sudo resolvectl flush-caches
resolvectl statistics  # Xem cache stats
```

**Expected output cho `dig`:**
```
; <<>> DiG 9.18.1 <<>> api.example.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; ANSWER SECTION:
api.example.com.	300	IN	A	93.184.216.34

;; Query time: 25 msec
;; SERVER: 127.0.0.53#53(127.0.0.53)
;; MSG SIZE  rcvd: 62
```

### 8.2. TCP Connection Debugging

```bash
# 1. ss — thay thế netstat, nhanh hơn
# Xem tất cả TCP connections
ss -tuanp

# Chỉ listening sockets
ss -tlnp
# Output:
# State  Recv-Q Send-Q Local Address:Port  Peer Address:Port  Process
# LISTEN 0      128    *:8080              *:*                users:(("myapp",pid=1234,fd=3))

# Xem connections đến port cụ thể
ss -tnp | grep ":5432"

# Đếm connection states
ss -s
# Output:
# TCP:   250 (estab 180, closed 20, orphaned 5, timewait 45)

# Chỉ TIME_WAIT
ss -tn state time-wait | wc -l

# Chỉ CLOSE_WAIT (potential leak!)
ss -tn state close-wait | wc -l

# Chi tiết connection với timer
ss -tnio | head -20
```

### 8.3. tcpdump — Capture và Analyze Traffic

```bash
# Capture traffic trên port 8080
sudo tcpdump -i any port 8080 -nn

# Capture với detail
sudo tcpdump -i any port 8080 -nn -vv

# Capture và save to file (analyze later với Wireshark)
sudo tcpdump -i any port 8080 -w /tmp/capture.pcap

# Chỉ capture SYN packets (new connections)
sudo tcpdump -i any 'tcp[tcpflags] & tcp-syn != 0' port 8080

# Capture DNS queries
sudo tcpdump -i any port 53 -nn

# Filter by host
sudo tcpdump -i any host 10.0.1.5

# Capture HTTP requests (basic)
sudo tcpdump -i any port 80 -A -s0 | grep -E "^(GET|POST|PUT|DELETE|HTTP)"
```

### 8.4. curl — HTTP Debugging

```bash
# Basic request
curl http://localhost:8080/

# Verbose — xem TCP handshake, TLS, headers
curl -v https://api.example.com/

# Timing breakdown
curl -o /dev/null -s -w "\
  DNS:       %{time_namelookup}s\n\
  Connect:   %{time_connect}s\n\
  TLS:       %{time_appconnect}s\n\
  Start:     %{time_starttransfer}s\n\
  Total:     %{time_total}s\n\
  HTTP Code: %{http_code}\n\
  Size:      %{size_download} bytes\n" \
  https://api.example.com/

# Expected output:
#   DNS:       0.004s
#   Connect:   0.025s     ← TCP handshake
#   TLS:       0.095s     ← TLS handshake
#   Start:     0.180s     ← First byte (TTFB)
#   Total:     0.200s
#   HTTP Code: 200
#   Size:      1234 bytes

# Set connect timeout
curl --connect-timeout 5 http://slow-server/

# Set total timeout
curl --max-time 30 http://slow-server/

# Force HTTP/2
curl --http2 https://api.example.com/

# Resolve DNS locally (bypass DNS)
curl --resolve api.example.com:443:10.0.1.5 https://api.example.com/

# Test HTTP headers
curl -I https://api.example.com/  # HEAD request, chỉ headers
```

### 8.5. Mô phỏng lỗi DNS và Connection

```bash
# 1. Mô phỏng DNS failure
# Không sửa /etc/resolv.conf. Dùng domain .invalid được reserve để luôn fail DNS.
curl -v --connect-timeout 3 http://api.example.invalid/
# Expected: "Could not resolve host: api.example.invalid"

# Hoặc test resolver timeout bằng dig tới DNS server không tồn tại.
dig @192.0.2.1 +time=1 +tries=1 api.example.com
# Expected: "no servers could be reached"

# 2. Mô phỏng connection timeout
# Connect đến port không ai listen
curl -v --connect-timeout 3 http://localhost:9999
# Expected: "Connection refused"

# Connect đến IP không route được (true timeout)
curl -v --connect-timeout 3 http://192.0.2.1:8080
# Expected: "Connection timed out after 3000 milliseconds"

# 3. Mô phỏng slow response
# Terminal 1: Create server that responds slowly
python3 -c "
import http.server, time
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(10)  # 10 second delay
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Slow response')
http.server.HTTPServer(('', 8888), Handler).serve_forever()
" &

# Terminal 2: Request with timeout
curl --max-time 3 http://localhost:8888/
# Expected: "Operation timed out after 3000 milliseconds"

# Cleanup
kill %1
```

**Verify**:

```bash
ss -tlnp | grep ':8888' || echo "slow server stopped"
curl -sS --max-time 1 http://api.example.invalid/ 2>&1 | grep -E "Could not resolve|resolve host"
```

**Expected output**:

```text
slow server stopped
curl: (6) Could not resolve host: api.example.invalid
```

### Cleanup

```bash
# Kill test servers
pkill -f "python3.*HTTPServer" 2>/dev/null || true
# Không cần restore DNS vì bài không ghi vào /etc/resolv.conf
```

---

## 9. Common Pitfalls & Debugging

### 9.1. Pitfall: Connection Refused vs Connection Timeout

| Error | Nguyên nhân | Debug |
|-------|-------------|-------|
| **Connection refused** | Port không có ai listen HOẶC firewall reject | `ss -tlnp \| grep <port>` — process có listen port đó không? |
| **Connection timeout** | Server không respond (down, firewall DROP, network unreachable) | `ping <ip>`, `traceroute <ip>`, `tcpdump` |
| **No route to host** | Network unreachable, routing table sai | `ip route`, `traceroute` |
| **Name resolution failed** | DNS không resolve được | `dig <hostname>`, check `/etc/resolv.conf` |

### 9.2. Pitfall: CLOSE_WAIT accumulation

**Dấu hiệu**: `ss -tn state close-wait | wc -l` → số lượng tăng dần theo thời gian.

**Root cause**: Application nhận FIN từ remote (peer closed connection) nhưng application code không close socket.

**Debug**:
```bash
# Xem CLOSE_WAIT connections
ss -tnp state close-wait

# Xem process nào giữ
ss -tnp state close-wait | awk '{print $6}' | sort | uniq -c | sort -rn

# Xem fd tương ứng
lsof -p <pid> | grep CLOSE_WAIT
```

**Fix**: Review code path xử lý connection — đảm bảo `close()` trong `finally`/`defer`.

### 9.3. Pitfall: DNS caching gây stale routing

**Dấu hiệu**: Deploy service mới với IP mới, update DNS record, nhưng một số requests vẫn đến IP cũ.

**Root cause**: DNS cache ở nhiều layer — OS, resolver, application (Java caches vĩnh viễn by default!).

**Debug**:
```bash
# Check DNS TTL của record hiện tại
dig +nocmd +noall +answer api.example.com
# api.example.com. 278 IN A 10.0.1.NEW

# Check local cache
resolvectl statistics  # Hit/miss ratio nếu dùng systemd-resolved

# Check từ different DNS server
dig @8.8.8.8 api.example.com
dig @1.1.1.1 api.example.com
```

### 9.4. Case Study: gRPC Load Balancing Failure

**Context**: Microservice platform, 10 services giao tiếp qua gRPC. Deploy trên Kubernetes với Service (ClusterIP).

**Symptom**: 1 pod trong gRPC server luôn nhận 90% traffic, các pod còn lại gần như idle. CPU uneven across pods.

**Investigation**:
- Kubernetes Service dùng iptables (L4 load balancing)
- gRPC dùng HTTP/2 → 1 long-lived TCP connection
- iptables chỉ load balance khi connection mới được tạo
- Client chỉ tạo 1 connection → tất cả requests đi qua 1 connection → 1 pod

**Root cause**: L4 load balancing (iptables) không hiểu HTTP/2 multiplexing → không balance giữa streams.

**Fix options**:
1. Client-side load balancing (gRPC built-in)
2. L7 load balancer (Envoy, Linkerd sidecar)
3. Periodic connection reset

**Lesson**: HTTP/2 và gRPC cần L7 load balancing, không thể dùng L4.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 2: Linux Advanced
- File descriptor (Day 2) là nền tảng cho network socket — mỗi TCP connection = 1 file descriptor.
- graceful shutdown (Day 2) liên quan connection draining — cần close connections gracefully.

### Bài sau — Day 4: Linux Performance & Debugging Tools
- Day 3 giới thiệu networking tools cơ bản (`ss`, `tcpdump`, `curl`).
- Day 4 sẽ mở rộng sang **performance analysis** — `ss` kết hợp `strace`, `perf` để debug network performance.
- Network bottleneck (Day 3) sẽ được đo bằng USE/RED method (Day 4).

---

## 11. Tài liệu tham khảo

### Must-read
- **"TCP/IP Illustrated, Vol. 1" by Kevin Fall & W. Richard Stevens** — Bible cho TCP/IP. Đọc Chapter 12-14 (TCP connection), Chapter 11 (DNS).
- **High Performance Browser Networking** (free online): https://hpbn.co/ — HTTP/2, HTTP/3, TLS optimization.
- **Kubernetes Networking** (official docs): https://kubernetes.io/docs/concepts/services-networking/ — DNS, Service, Network Policy.

### Nice-to-have
- **"Computer Networking: A Top-Down Approach" by Kurose & Ross** — Textbook chuẩn, giải thích từ application layer xuống.
- **Julia Evans' Networking Zines**: https://wizardzines.com/ — Infographics rất dễ hiểu.
- **Cloudflare Learning Center**: https://www.cloudflare.com/learning/ — DNS, DDoS, TLS explained.

### Deep-dive
- **gRPC Load Balancing**: https://grpc.io/blog/grpc-load-balancing/ — Vì sao L4 LB không đủ.
- **Linux Network Tuning**: https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/configuring_and_managing_networking/ — Red Hat docs.
- **tcpdump Tutorial**: https://danielmiessler.com/study/tcpdump/ — Practical tcpdump usage.

