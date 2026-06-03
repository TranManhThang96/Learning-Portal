# Day 01 - Document: Reverse Proxy vs Forward Proxy vs Load Balancer

> Deep dive reference document. Đọc khi cần hiểu sâu hơn ngoài nội dung `lesson.md`.

---

## 1. Phân biệt chi tiết: Reverse Proxy vs Forward Proxy vs Load Balancer

### 1.1. Forward Proxy

**Vị trí**: Đứng trước client, thay mặt client gửi request ra ngoài.

```
[Client] → [Forward Proxy] → [Internet / External Server]
```

**Đặc điểm**:
- Client biết mình đang dùng proxy (phải cấu hình trong browser/OS)
- Server bên ngoài chỉ thấy IP của proxy, không thấy IP client
- Dùng để: ẩn danh tính client, bypass geo-restriction, cache outbound traffic, content filtering trong corporate network

**Ví dụ thực tế**:
- Corporate proxy: Mọi request từ máy nhân viên đều đi qua proxy để filter và log
- VPN: Một dạng forward proxy ở tầng network
- Squid Proxy: Forward proxy phổ biến trong enterprise

**Nginx làm forward proxy**: Nginx không phải forward proxy tốt. Dùng Squid hoặc Privoxy cho use case này.

---

### 1.2. Reverse Proxy

**Vị trí**: Đứng trước server, nhận request từ client và forward đến backend.

```
[Client] → [Reverse Proxy] → [Backend Server 1]
                           → [Backend Server 2]
```

**Đặc điểm**:
- Client không biết backend topology (chỉ biết địa chỉ reverse proxy)
- Backend servers không expose trực tiếp ra Internet
- Reverse proxy có thể modify request/response (thêm headers, compress, cache)

**Chức năng của reverse proxy**:

| Chức năng | Mô tả |
|---|---|
| Request routing | Route request đến đúng backend theo path, host, header |
| TLS termination | Decrypt HTTPS tại proxy, forward HTTP đến backend |
| Load balancing | Phân phối traffic đến nhiều backend instances |
| Caching | Cache response từ backend, giảm load |
| Compression | Gzip/Brotli response trước khi gửi về client |
| Header manipulation | Thêm/xóa/sửa headers |
| Rate limiting | Giới hạn request từ một IP/user |
| Authentication | Xác thực request trước khi forward đến backend |
| Logging | Tập trung log tại một điểm |

---

### 1.3. Load Balancer

**Vị trí**: Đứng trước một nhóm servers chạy cùng một service.

```
[Client] → [Load Balancer] → [Server Instance 1]
                           → [Server Instance 2]
                           → [Server Instance 3]
```

**Đặc điểm**:
- Phân phối traffic đến nhiều instances của cùng một service
- Health check để loại bỏ instance unhealthy
- Có thể hoạt động ở L4 (TCP/UDP) hoặc L7 (HTTP)

**L4 vs L7 Load Balancer**:

| | L4 Load Balancer | L7 Load Balancer |
|---|---|---|
| Hoạt động ở | Transport layer (TCP/UDP) | Application layer (HTTP/HTTPS) |
| Thấy được | IP, port, protocol | URL, headers, cookies, body |
| Routing dựa trên | IP/port | Path, host, header, cookie |
| Performance | Rất cao (ít processing) | Cao (cần parse HTTP) |
| Ví dụ | HAProxy TCP mode, AWS NLB | Nginx, HAProxy HTTP mode, AWS ALB |
| TLS termination | Không (pass-through) | Có thể |

---

### 1.4. Overlap và kết hợp

Trong thực tế, ranh giới giữa 3 khái niệm này không rõ ràng:

- **Nginx** có thể làm: reverse proxy, L7 load balancer, caching proxy, TLS termination
- **HAProxy** có thể làm: L4 load balancer, L7 load balancer, reverse proxy
- **Kong** = Nginx (reverse proxy) + Lua plugins (API Gateway features)

**Kiến trúc điển hình production**:

```
Internet
    │
    ▼
Cloud Load Balancer (L4/L7)     ← HA, public IP, DDoS protection
    │
    ▼
Nginx cluster (Reverse Proxy)   ← TLS termination, routing, rate limit cơ bản
    │
    ▼
API Gateway (Kong)              ← Auth, rate limit, plugin, governance
    │
    ▼
Microservices                   ← Business logic
```

---

## 2. Request Flow Chi Tiết

### 2.1. HTTP Request qua Nginx Reverse Proxy

```
Step 1: Client gửi request
─────────────────────────
GET /api/orders/123 HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer eyJ...

Step 2: Nginx nhận và xử lý
────────────────────────────
- Accept TCP connection
- Parse HTTP request
- Match server_name: api.example.com
- Match location: /api/orders/
- Resolve upstream: order_service → 172.18.0.3:8001

Step 3: Nginx tạo request mới đến upstream
──────────────────────────────────────────
GET /123 HTTP/1.1                    ← Path đã strip prefix
Host: api.example.com
X-Real-IP: 203.0.113.1               ← IP thật của client
X-Forwarded-For: 203.0.113.1
X-Forwarded-Proto: https
Connection:                          ← Rỗng để bật keepalive
Authorization: Bearer eyJ...         ← Giữ nguyên (Nginx không xóa)

Step 4: Upstream xử lý và trả response
────────────────────────────────────────
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 245

{"order_id": "123", "status": "pending", ...}

Step 5: Nginx forward response về client
─────────────────────────────────────────
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 245
Server: nginx                        ← Nginx thêm Server header (nếu server_tokens on)

{"order_id": "123", "status": "pending", ...}

Step 6: Nginx ghi access log
──────────────────────────────
203.0.113.1 - - [18/May/2026:10:00:00 +0000] "GET /api/orders/123 HTTP/1.1"
200 245 "-" "curl/8.0.1"
upstream=172.18.0.3:8001 upstream_time=0.003 request_time=0.003
```

### 2.2. Connection Lifecycle

```
Client                    Nginx                    Upstream
  │                         │                         │
  │──── TCP SYN ───────────►│                         │
  │◄─── TCP SYN-ACK ────────│                         │
  │──── TCP ACK ───────────►│                         │
  │                         │                         │
  │  (TCP connection established - keepalive)          │
  │                         │                         │
  │──── HTTP GET ──────────►│                         │
  │                         │──── TCP SYN ───────────►│  (nếu không có keepalive pool)
  │                         │◄─── TCP SYN-ACK ────────│
  │                         │──── TCP ACK ───────────►│
  │                         │──── HTTP GET ──────────►│
  │                         │◄─── HTTP 200 ───────────│
  │◄─── HTTP 200 ───────────│                         │
  │                         │  (connection về pool)   │
  │                         │                         │
  │──── HTTP GET ──────────►│                         │
  │                         │──── HTTP GET ──────────►│  (reuse connection từ pool)
  │                         │◄─── HTTP 200 ───────────│
  │◄─── HTTP 200 ───────────│                         │
```

**Lợi ích của upstream keepalive**:
- Tránh TCP handshake overhead cho mỗi request
- Giảm số lượng TIME_WAIT connections
- Giảm latency p95/p99 đáng kể khi traffic cao

---

## 3. Nginx Configuration Deep Dive

### 3.1. Cấu trúc config file

```
nginx.conf
├── main context          (global settings)
│   ├── worker_processes
│   ├── error_log
│   └── events {}
│       └── worker_connections
└── http {}
    ├── upstream {}       (backend server groups)
    ├── server {}         (virtual hosts)
    │   ├── listen
    │   ├── server_name
    │   └── location {}   (URL routing)
    │       └── proxy_pass
    └── include           (split config vào nhiều files)
```

### 3.2. Upstream module

```nginx
upstream order_service {
    # Load balancing algorithm (mặc định: round-robin)
    # least_conn;
    # ip_hash;

    server order-service-1:8001 weight=3;  # nhận 3x traffic
    server order-service-2:8001 weight=1;
    server order-service-3:8001 backup;    # chỉ dùng khi 2 server trên down

    keepalive 32;           # max idle connections trong pool
    keepalive_timeout 60s;  # idle connection timeout
    keepalive_requests 100; # max requests per keepalive connection
}
```

### 3.3. Proxy module quan trọng

```nginx
location /api/ {
    proxy_pass http://backend/;

    # HTTP version (bắt buộc cho keepalive)
    proxy_http_version 1.1;
    proxy_set_header Connection "";

    # Headers
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Timeouts
    proxy_connect_timeout  5s;    # Timeout kết nối TCP đến upstream
    proxy_send_timeout     30s;   # Timeout gửi request đến upstream
    proxy_read_timeout     30s;   # Timeout đọc response từ upstream

    # Buffering
    proxy_buffering    on;        # Buffer response từ upstream
    proxy_buffer_size  4k;        # Buffer cho response headers
    proxy_buffers      8 4k;      # Buffer cho response body
    proxy_busy_buffers_size 8k;

    # Retry (cẩn thận với non-idempotent requests)
    proxy_next_upstream error timeout;
    proxy_next_upstream_tries 2;
    proxy_next_upstream_timeout 10s;
}
```

### 3.4. Timeout budget

Một nguyên tắc quan trọng: timeout phải giảm dần từ client đến backend.

```
Client timeout (browser/mobile): 60s
    └── Nginx proxy_read_timeout: 30s
            └── Backend service timeout: 20s
                    └── Database query timeout: 10s
```

Nếu `proxy_read_timeout > client timeout`, client sẽ ngắt kết nối trước khi Nginx nhận được response từ upstream. Nginx vẫn tiếp tục chờ upstream nhưng không có ai nhận response → lãng phí resource.

---

## 4. So sánh Nginx vs HAProxy vs Envoy vs Kong

| | Nginx | HAProxy | Envoy | Kong |
|---|---|---|---|---|
| **Vai trò chính** | Reverse proxy, web server | L4/L7 load balancer | L7 proxy, service mesh | API Gateway |
| **Performance** | Cao | Rất cao | Cao | Trung bình-Cao |
| **Memory footprint** | Thấp | Rất thấp | Trung bình | Cao (Lua runtime) |
| **Dynamic config** | Cần reload | Runtime API | xDS API (real-time) | Admin API (real-time) |
| **Service discovery** | Không native | Không native | Native (xDS) | DNS + Admin API |
| **Plugin/extension** | Lua (Nginx Plus), C module | Không | Wasm, C++ filter | Lua plugin ecosystem |
| **Observability** | Cơ bản | Tốt | Rất tốt | Tốt (plugin) |
| **TLS** | Tốt | Tốt | Rất tốt (mTLS native) | Tốt |
| **gRPC** | Có (proxy) | Có (proxy) | Native | Có (plugin) |
| **Learning curve** | Thấp | Trung bình | Cao | Trung bình-Cao |
| **Community** | Rất lớn | Lớn | Lớn (CNCF) | Lớn |
| **License** | BSD (free) | GPL/LGPL (free) | Apache 2.0 (free) | Apache 2.0 (free) |

### Khi nào dùng gì

**Nginx**: Web server, static file serving, simple reverse proxy, TLS termination, basic rate limiting. Phù hợp khi team đã quen Nginx, không cần dynamic config.

**HAProxy**: Khi cần L4 load balancing hiệu năng cao (TCP proxy), hoặc cần health check phức tạp. Thường dùng ở tầng trước Nginx/Kong.

**Envoy**: Khi dùng service mesh (Istio, Consul Connect), cần dynamic config real-time, gRPC load balancing, circuit breaker native. Learning curve cao.

**Kong**: Khi cần API Gateway đầy đủ tính năng: auth, rate limiting, plugin ecosystem, developer portal. Overhead cao hơn pure proxy.

---

## 5. Security Considerations

### 5.1. Tại sao không expose service trực tiếp

```
Expose trực tiếp (BAD):
Internet → order-service:8001
         → payment-service:8002

Vấn đề:
- Attacker biết port và service fingerprint
- Không có centralized auth
- Không có rate limiting
- Không có audit log tập trung
- Khó rotate TLS certificate
- Khó implement IP allowlist/blocklist
```

```
Qua reverse proxy (GOOD):
Internet → Nginx:443 → order-service:8001 (internal only)
                     → payment-service:8002 (internal only)

Lợi ích:
- Chỉ expose 1 port (443) ra Internet
- Centralized TLS termination
- Centralized logging và monitoring
- Dễ implement WAF, rate limiting, IP filtering
- Backend services không cần biết về TLS
```

### 5.2. Network segmentation với Docker

```yaml
# docker-compose.yml
services:
  nginx:
    networks:
      - public    # Kết nối với "Internet" (host)
      - backend   # Kết nối với backend services

  order-service:
    networks:
      - backend   # Chỉ trong internal network

networks:
  public:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # Không có kết nối ra ngoài
```

Với `internal: true`, backend services không thể tự kết nối ra Internet, giảm attack surface.

### 5.3. Headers bảo mật

```nginx
# Thêm vào server block
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Ẩn server info
server_tokens off;
proxy_hide_header X-Powered-By;
proxy_hide_header Server;
```

---

## 6. Observability Checklist cho Reverse Proxy

Các metrics và logs cần monitor khi vận hành Nginx reverse proxy:

### Metrics quan trọng

| Metric | Ý nghĩa | Alert khi |
|---|---|---|
| `nginx_http_requests_total` | Tổng số requests | Tăng đột biến |
| `nginx_http_request_duration_seconds` (p95, p99) | Latency | p95 > SLA |
| `nginx_upstream_response_time` | Upstream latency | Tăng so với baseline |
| `nginx_connections_active` | Active connections | Gần `worker_connections` |
| `nginx_http_requests_total{status=~"5.."}` | 5xx error rate | > 1% |
| `nginx_upstream_connects_failed_total` | Upstream connection failures | > 0 |

### Log fields quan trọng

```
$remote_addr          - IP client
$request              - Method + URI + Protocol
$status               - HTTP status code
$body_bytes_sent      - Response size
$request_time         - Total request time
$upstream_addr        - Upstream server address
$upstream_response_time - Upstream response time
$upstream_status      - Upstream HTTP status
$http_user_agent      - Client user agent
```

### Lệnh debug nhanh

```bash
# Top 10 URLs có nhiều request nhất
docker compose exec nginx cat /var/log/nginx/access.log | \
  awk '{print $7}' | sort | uniq -c | sort -rn | head -10

# Top 10 IPs gửi nhiều request nhất
docker compose exec nginx cat /var/log/nginx/access.log | \
  awk '{print $1}' | sort | uniq -c | sort -rn | head -10

# Đếm 5xx errors
docker compose exec nginx cat /var/log/nginx/access.log | \
  awk '$9 ~ /^5/' | wc -l

# Average upstream response time
docker compose exec nginx cat /var/log/nginx/access.log | \
  grep -oP 'upstream_time=\K[0-9.]+' | \
  awk '{sum+=$1; count++} END {print sum/count}'
```
