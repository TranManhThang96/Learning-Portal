# Day 05: TLS Termination, HTTP/2 & Secure Edge

> **Thời lượng**: 2 giờ
> **Độ khó**: ⭐⭐⭐
> **Prerequisites**: Day 1 (Reverse Proxy), Day 2 (Nginx Architecture), Day 3 (Load Balancing), Day 4 (Health Check & Failover)

---

## 1. Learning Objectives

Sau bài này, bạn sẽ có thể:

- Configure Nginx với TLS termination, TLS 1.2 + TLS 1.3, modern cipher suite
- Phân biệt TLS termination tại edge vs end-to-end TLS vs mTLS và chọn đúng theo use case
- Bật HTTP/2 trên Nginx, verify ALPN negotiation bằng `curl` và `openssl s_client`
- Configure HSTS, OCSP stapling, session resumption để tăng security và performance
- Troubleshoot các lỗi TLS phổ biến: certificate expired, SNI mismatch, clock skew, mixed-content

---

## 2. The Problem

> Bạn vừa deploy xong hệ thống microservices với Nginx làm reverse proxy. Mọi thứ chạy tốt trên HTTP. Nhưng hôm nay security team gửi email: "Tất cả traffic phải chạy qua HTTPS. TLS 1.0 và 1.1 bị cấm. Phải có HSTS. Deadline: cuối tuần."
>
> Bạn bắt đầu configure HTTPS, nhưng ngay lập tức gặp hàng loạt vấn đề: certificate tự ký bị browser reject, HTTP/2 không bật được, OCSP stapling báo lỗi, và client mobile app bị lỗi SSL handshake vì dùng TLS 1.0.

**Pain points thực tế:**

- Mỗi microservice tự quản lý TLS certificate → certificate drift, expiry không đồng bộ
- TLS handshake tốn CPU, đặc biệt với RSA 2048/4096 → latency tăng ở connection đầu tiên
- Không có session resumption → mỗi connection đều full handshake → mobile app chậm
- HTTP/1.1 với nhiều request nhỏ → head-of-line blocking → latency cao
- Không có HSTS → downgrade attack có thể xảy ra
- Certificate expired không có alert → production outage lúc 3 giờ sáng

**Hậu quả nếu thiết kế sai:**

- TLS 1.0/1.1 bị khai thác qua POODLE, BEAST attack
- Weak cipher (RC4, DES) → data bị decrypt
- Không có HSTS → MITM attack qua HTTP downgrade
- Certificate expired → toàn bộ traffic bị block, không có graceful degradation
- Terminate TLS quá sâu trong stack → mất observability, khó debug

---

## 3. Core Concepts

### 3.1 TLS Termination là gì?

**Analogy**: TLS giống như phong bì niêm phong. TLS termination là hành động mở phong bì tại một điểm cụ thể trong hệ thống để đọc nội dung bên trong.

**TLS termination** là quá trình decrypt traffic HTTPS tại một điểm (thường là edge/load balancer), sau đó forward traffic dưới dạng HTTP (hoặc HTTPS nội bộ) đến backend services.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TLS Termination Models                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Model 1: Edge Termination (phổ biến nhất)                      │
│                                                                  │
│  Client ──HTTPS──► Nginx Edge ──HTTP──► Backend Services        │
│                    (terminate TLS)                               │
│                                                                  │
│  Model 2: End-to-End TLS (re-encrypt)                           │
│                                                                  │
│  Client ──HTTPS──► Nginx Edge ──HTTPS──► Backend Services       │
│                    (terminate + re-encrypt)                      │
│                                                                  │
│  Model 3: mTLS (mutual TLS)                                     │
│                                                                  │
│  Client ──mTLS──► Nginx Edge ──mTLS──► Backend Services         │
│                   (both sides verify cert)                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 TLS Handshake Flow

```
Client                          Server (Nginx)
  │                                  │
  │──── ClientHello ────────────────►│  (TLS version, cipher suites, random)
  │                                  │
  │◄─── ServerHello ────────────────│  (chosen cipher, random, session ID)
  │◄─── Certificate ────────────────│  (server cert chain)
  │◄─── ServerHelloDone ────────────│
  │                                  │
  │  [Client verifies cert]          │
  │──── ClientKeyExchange ──────────►│  (pre-master secret, encrypted)
  │──── ChangeCipherSpec ───────────►│
  │──── Finished ───────────────────►│
  │                                  │
  │◄─── ChangeCipherSpec ────────────│
  │◄─── Finished ────────────────────│
  │                                  │
  │════ Encrypted Application Data ══│  (HTTP/2 or HTTP/1.1)
```

**TLS 1.2**: 2-RTT handshake (2 round trips trước khi gửi data)
**TLS 1.3**: 1-RTT handshake, hỗ trợ 0-RTT resumption (gửi data ngay trong handshake đầu tiên)

### 3.3 ALPN - Application Layer Protocol Negotiation

ALPN là TLS extension cho phép client và server thương lượng application protocol (h2 hay http/1.1) ngay trong TLS handshake, không cần thêm round trip.

```
ClientHello:
  extensions:
    ALPN: ["h2", "http/1.1"]   ← client ưu tiên h2

ServerHello:
  extensions:
    ALPN: "h2"                  ← server chọn h2
```

Nếu server không hỗ trợ h2, ALPN trả về "http/1.1" → connection vẫn hoạt động, chỉ không có HTTP/2.

### 3.4 HTTP/2 vs HTTP/1.1

```
HTTP/1.1:
  Request 1 ──────────────────────────────► Response 1
                Request 2 ──────────────────────────────► Response 2
                              Request 3 ──────────────────────────────► Response 3
  (sequential, head-of-line blocking)

HTTP/2 (multiplexing):
  Stream 1: Request ──────────────────────► Response
  Stream 2:   Request ──────────────────────► Response
  Stream 3:     Request ──────────────────────► Response
  (parallel streams trên 1 TCP connection)
```

**HTTP/2 key features:**
- **Multiplexing**: nhiều request/response song song trên 1 TCP connection
- **Binary framing**: thay vì text-based như HTTP/1.1 → parse nhanh hơn, ít lỗi hơn
- **Header compression (HPACK)**: compress header → giảm bandwidth, đặc biệt với nhiều request nhỏ
- **Server push**: server chủ động gửi resource trước khi client hỏi (deprecated trong nhiều browser)
- **Stream prioritization**: client có thể hint priority cho từng stream

---

## 4. How It Works Internally

### 4.1 TLS Handshake trong Nginx

Khi Nginx nhận connection HTTPS, flow xử lý như sau:

1. **TCP accept**: Nginx worker accept TCP connection
2. **TLS ClientHello parse**: đọc TLS version, cipher suites, SNI extension
3. **SNI lookup**: dùng SNI hostname để chọn đúng `ssl_certificate` (nếu có nhiều virtual host)
4. **Certificate load**: load cert từ disk (hoặc từ cache nếu đã load)
5. **Cipher negotiation**: chọn cipher suite tốt nhất mà cả hai bên đều hỗ trợ
6. **Key exchange**: trao đổi key (ECDHE với TLS 1.3, hoặc RSA/ECDHE với TLS 1.2)
7. **Session ticket**: nếu client gửi session ticket hợp lệ → skip full handshake (resumption)
8. **ALPN**: negotiate h2 hay http/1.1
9. **Handshake complete**: bắt đầu nhận HTTP request

### 4.2 Session Resumption

Có 2 cơ chế session resumption:

**Session ID** (cũ, server-side state):
- Server lưu session state trong memory
- Client gửi session ID trong ClientHello
- Server lookup → nếu tìm thấy → skip full handshake
- Vấn đề: không scale tốt với nhiều Nginx worker/instance

**Session Ticket** (mới hơn, client-side state):
- Server encrypt session state → gửi cho client dưới dạng ticket
- Client lưu ticket, gửi lại trong ClientHello tiếp theo
- Server decrypt ticket → restore session state
- Scale tốt hơn, nhưng cần đồng bộ ticket encryption key giữa các worker

```nginx
# Session cache (session ID based)
ssl_session_cache    shared:SSL:10m;  # 10MB shared cache, ~40,000 sessions
ssl_session_timeout  1d;              # session valid 1 ngày

# Session tickets
ssl_session_tickets  off;  # Tắt nếu không có key rotation → security risk
```

**Security note**: `ssl_session_tickets on` mà không rotate key định kỳ → forward secrecy bị phá vỡ. Nếu attacker lấy được ticket key → decrypt tất cả session đã record.

### 4.3 OCSP Stapling

**OCSP (Online Certificate Status Protocol)**: cơ chế kiểm tra certificate có bị revoke không.

Không có OCSP stapling:
```
Client → Server: "Cho tôi cert"
Client → CA OCSP server: "Cert này còn valid không?"  ← thêm 1 round trip
CA OCSP server → Client: "Valid"
Client → Server: "OK, tiếp tục handshake"
```

Với OCSP stapling:
```
Server → CA OCSP server: "Cho tôi OCSP response" (định kỳ, background)
Client → Server: "Cho tôi cert"
Server → Client: cert + OCSP response (stapled)  ← không cần client hỏi CA
Client: verify OCSP response → handshake tiếp tục
```

OCSP stapling giảm latency handshake và giảm tải cho CA OCSP server.

### 4.4 Cipher Suite

Cipher suite là tập hợp các thuật toán mã hóa dùng trong TLS session:

```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
│    │      │        │           │
│    │      │        │           └── MAC algorithm (SHA384)
│    │      │        └────────────── Encryption (AES-256-GCM)
│    │      └─────────────────────── Authentication (RSA)
│    └────────────────────────────── Key exchange (ECDHE)
└─────────────────────────────────── Protocol (TLS)
```

**TLS 1.3 đơn giản hóa**: chỉ còn 5 cipher suite, tất cả đều dùng AEAD (Authenticated Encryption with Associated Data), loại bỏ hoàn toàn các cipher yếu.

### 4.5 HTTP/2 Binary Framing Layer

HTTP/2 chia communication thành các **frames** nhỏ:

```
┌──────────────────────────────────────────────┐
│              HTTP/2 Connection               │
│                                              │
│  Stream 1: HEADERS frame + DATA frames       │
│  Stream 3: HEADERS frame + DATA frames       │
│  Stream 5: HEADERS frame + DATA frames       │
│                                              │
│  (streams interleaved trên 1 TCP connection) │
└──────────────────────────────────────────────┘
```

Frame types quan trọng:
- `HEADERS`: HTTP headers (compressed bằng HPACK)
- `DATA`: request/response body
- `SETTINGS`: cấu hình connection parameters
- `WINDOW_UPDATE`: flow control
- `PING`: keepalive
- `GOAWAY`: graceful shutdown

---

## 5. Hands-on Lab

Xem file `exercises.md` để thực hành đầy đủ. Dưới đây là overview các bước chính.

### 5.1 Cấu trúc Lab

```
lab-day05/
├── docker-compose.yml
├── nginx/
│   ├── nginx.conf
│   └── conf.d/
│       └── api.local.conf
├── certs/
│   ├── api.local.crt
│   └── api.local.key
└── backend/
    └── app.py  (simple Flask app)
```

### 5.2 Generate Self-Signed Certificate

```bash
# Cách 1: openssl (không cần cài thêm)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/api.local.key \
  -out certs/api.local.crt \
  -subj "/CN=api.local" \
  -addext "subjectAltName=DNS:api.local,IP:127.0.0.1"

# Cách 2: mkcert (trusted by local browser, recommended cho dev)
mkcert -install
mkcert -key-file certs/api.local.key -cert-file certs/api.local.crt api.local 127.0.0.1
```

### 5.3 Nginx HTTPS Configuration

```nginx
server {
    listen 443 ssl;
    http2 on;                          # Nginx 1.25+ syntax
    server_name api.local;

    # Certificate
    ssl_certificate     /etc/nginx/certs/api.local.crt;
    ssl_certificate_key /etc/nginx/certs/api.local.key;

    # Protocol versions
    ssl_protocols TLSv1.2 TLSv1.3;

    # Cipher suites (Mozilla Intermediate config)
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;     # TLS 1.3 ignores này, TLS 1.2 dùng

    # Session resumption
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;           # Tắt để tránh security risk

    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    location / {
        proxy_pass http://backend:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name api.local;
    return 301 https://$host$request_uri;
}
```

### 5.4 Test Commands

```bash
# Test TLS 1.3
openssl s_client -connect api.local:443 -tls1_3 \
  -servername api.local </dev/null 2>&1 | grep -E "Protocol|Cipher|Session"

# Test với curl (verbose để xem ALPN)
curl -v --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/

# Test HTTP/2
curl --http2 -v --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/ 2>&1 | grep -E "ALPN|HTTP/2|h2"

# Verify HSTS header
curl -sI --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/ | grep -i strict

# Benchmark HTTP/2 với h2load
h2load -n 1000 -c 10 -m 10 \
  -k --connect-to=127.0.0.1:443 \
  https://api.local/
```

---

## 6. Trade-offs Analysis

### 6.1 TLS Termination Strategy

| Strategy | Security | Performance | Complexity | Observability | Khi nào dùng |
|---|---|---|---|---|---|
| Edge termination (Nginx/LB) | Tốt | Cao (offload CPU) | Thấp | Tốt (plaintext nội bộ) | Hầu hết use case, internal network trusted |
| End-to-end TLS (re-encrypt) | Rất tốt | Trung bình (double TLS) | Trung bình | Khó hơn | Compliance yêu cầu, zero-trust network |
| mTLS end-to-end | Xuất sắc | Thấp hơn | Cao | Khó nhất | Service mesh, high-security microservices |
| Cloud LB termination | Tốt | Rất cao (hardware) | Rất thấp | Tốt | Cloud-native, managed cert |

**Hidden costs:**
- End-to-end TLS: mỗi backend phải có cert, quản lý cert phức tạp hơn nhiều
- mTLS: cần PKI infrastructure, cert rotation automation, debugging khó
- Cloud LB: vendor lock-in, cost tăng theo traffic

### 6.2 HTTP Protocol Comparison

| Feature | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
|---|---|---|---|
| Transport | TCP | TCP | UDP (QUIC) |
| Multiplexing | Không (pipelining có nhưng broken) | Có (streams) | Có (streams) |
| Head-of-line blocking | Có (application level) | Không (application), Có (TCP level) | Không |
| Header compression | Không | HPACK | QPACK |
| Connection setup | 1-RTT | 1-RTT (TLS 1.3) | 0-RTT |
| Server push | Không | Có (deprecated) | Có |
| Nginx support | Stable | Stable | Experimental (1.25+) |
| Khi nào dùng | Legacy, simple API | API, web app, microservices | Mobile, high packet loss |

### 6.3 TLS Version Comparison

| Version | Security | Performance | Support | Recommendation |
|---|---|---|---|---|
| TLS 1.0 | Yếu (POODLE, BEAST) | Tốt | Rộng | Cấm hoàn toàn |
| TLS 1.1 | Yếu (BEAST) | Tốt | Rộng | Cấm hoàn toàn |
| TLS 1.2 | Tốt (nếu cipher đúng) | Tốt | Rất rộng | Giữ cho backward compat |
| TLS 1.3 | Xuất sắc | Tốt hơn (1-RTT) | Rộng (2018+) | Ưu tiên |

---

## 7. Best Practices & Best Solution

### 7.1 Production TLS Configuration

**Use case: Public API cho mobile và web app**

```
Internet → Cloud LB (TLS termination, cert managed) → Nginx (HTTP/2, internal) → Services
```

Hoặc nếu không có Cloud LB:

```
Internet → Nginx Edge (TLS 1.2+1.3, HSTS, OCSP) → Internal HTTP → Services
```

**Recommended Nginx TLS config (Mozilla Intermediate):**

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

Tham khảo: https://ssl-config.mozilla.org/ để generate config phù hợp với Nginx version.

### 7.2 Anti-patterns cần tránh

| Anti-pattern | Hậu quả | Fix |
|---|---|---|
| `ssl_protocols TLSv1 TLSv1.1 TLSv1.2` | Vulnerable to POODLE, BEAST | Chỉ dùng TLSv1.2 TLSv1.3 |
| `ssl_ciphers ALL` hoặc `ssl_ciphers HIGH` | Bao gồm cipher yếu | Dùng Mozilla SSL config |
| `ssl_session_tickets on` không rotate key | Forward secrecy bị phá | Tắt hoặc implement key rotation |
| Không có HSTS | HTTP downgrade attack | Bật HSTS với max-age dài |
| Certificate tự ký trên production | Browser warning, user trust issue | Dùng Let's Encrypt hoặc CA cert |
| Không monitor cert expiry | Production outage | Alert khi cert còn < 30 ngày |
| `ssl_prefer_server_ciphers on` với TLS 1.3 | TLS 1.3 ignore directive này, gây nhầm lẫn | Dùng `off` |
| Không có `ssl_stapling_verify on` | OCSP response không được verify | Bật cả hai |

### 7.3 Certificate Management

```bash
# Check cert expiry
openssl x509 -in cert.crt -noout -dates

# Check cert expiry từ remote
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | openssl x509 -noout -dates

# Let's Encrypt với certbot (production)
certbot certonly --nginx -d api.example.com
# Auto-renewal: certbot renew --dry-run
```

---

## 8. Performance Considerations

### 8.1 TLS Handshake Cost

TLS handshake tốn CPU và latency. Các yếu tố ảnh hưởng:

- **Key exchange algorithm**: ECDHE nhanh hơn RSA key exchange đáng kể
- **Certificate size**: cert chain dài → tốn bandwidth trong handshake
- **OCSP stapling**: giảm latency bằng cách tránh client phải query CA
- **Session resumption**: giảm CPU cost bằng cách skip full handshake

### 8.2 Benchmark Methodology

```markdown
Tool: h2load (HTTP/2 specific) + wrk (HTTP/1.1)
CPU: 4 vCPU
RAM: 8GB
Payload: 1KB JSON response
Duration: 60s
Connections: 100
TLS: On (TLS 1.3)
Keepalive: On

Lưu ý: số liệu chỉ dùng để tham khảo. Kết quả thực tế phụ thuộc vào
hardware, kernel, network, payload size, TLS version, cipher suite,
session resumption rate, và OCSP stapling.
```

**Sample benchmark commands:**

```bash
# HTTP/1.1 benchmark
wrk -t4 -c100 -d60s --latency \
  --header "Host: api.local" \
  https://localhost/api/v1/health

# HTTP/2 benchmark
h2load -n 10000 -c 100 -m 10 \
  -k --connect-to=127.0.0.1:443 \
  https://api.local/api/v1/health

# So sánh session resumption
# Lần 1: full handshake
openssl s_time -connect api.local:443 -new -time 10

# Lần 2: session resumption
openssl s_time -connect api.local:443 -reuse -time 10
```

### 8.3 Bottleneck Detection

```bash
# CPU usage của Nginx worker (TLS handshake intensive)
top -p $(pgrep nginx | tr '\n' ',')

# TLS handshake errors
grep "SSL_do_handshake" /var/log/nginx/error.log | tail -20

# Session cache hit rate (cần stub_status module)
curl http://localhost/nginx_status

# Nginx TLS metrics với OpenTelemetry hoặc Prometheus nginx exporter
# ssl_handshakes, ssl_handshakes_failed, ssl_session_reuses
```

### 8.4 Tuning Parameters

```nginx
# Worker processes = số CPU cores
worker_processes auto;

# Tăng worker_connections nếu nhiều TLS connections
events {
    worker_connections 4096;
}

# SSL session cache: 1MB ≈ 4000 sessions
ssl_session_cache shared:SSL:50m;  # 50MB ≈ 200,000 sessions

# Buffer size cho TLS records
ssl_buffer_size 4k;  # Default 16k, giảm xuống 4k giảm TTFB
```

---

## 9. Troubleshooting Checklist

### 9.1 TLS Handshake Failures

```bash
# Kiểm tra certificate validity
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt /etc/nginx/certs/api.local.crt

# Kiểm tra cert và key match
openssl x509 -noout -modulus -in cert.crt | md5sum
openssl rsa -noout -modulus -in cert.key | md5sum
# Hai hash phải giống nhau

# Kiểm tra SNI
openssl s_client -connect api.local:443 -servername api.local

# Kiểm tra TLS version được support
openssl s_client -connect api.local:443 -tls1_2
openssl s_client -connect api.local:443 -tls1_3

# Kiểm tra cipher suite
openssl s_client -connect api.local:443 -cipher ECDHE-RSA-AES256-GCM-SHA384
```

### 9.2 Common Errors và Fix

| Error | Nguyên nhân | Fix |
|---|---|---|
| `SSL_CTX_use_certificate_file failed` | Cert file không tồn tại hoặc sai path | Kiểm tra path, permissions |
| `no shared cipher` | Client và server không có cipher chung | Kiểm tra `ssl_ciphers`, thêm cipher tương thích |
| `certificate verify failed` | Self-signed cert hoặc CA chain thiếu | Thêm `ssl_trusted_certificate` hoặc dùng CA cert |
| `SSL handshake failed` + clock skew | Đồng hồ server/client lệch > 5 phút | Sync NTP: `ntpdate pool.ntp.org` |
| `peer closed connection in SSL handshake` | TLS version mismatch | Kiểm tra `ssl_protocols` |
| `OCSP_basic_verify() failed` | OCSP response không verify được | Thêm `ssl_trusted_certificate` với CA chain |
| HTTP/2 không hoạt động | Nginx < 1.25 dùng sai syntax | Dùng `listen 443 ssl http2` cho Nginx < 1.25 |

### 9.3 Debug Checklist

- [ ] Nginx error log: `tail -f /var/log/nginx/error.log`
- [ ] Certificate expiry: `openssl x509 -noout -dates -in cert.crt`
- [ ] Cert và key match: so sánh modulus MD5
- [ ] SNI configuration: đúng `server_name` trong config
- [ ] TLS version: `ssl_protocols` có TLSv1.2 TLSv1.3
- [ ] Cipher suite: không có cipher yếu (RC4, DES, NULL)
- [ ] OCSP stapling: `ssl_stapling on` + `resolver` configured
- [ ] HTTP/2 syntax: đúng theo Nginx version
- [ ] HSTS header: có trong response
- [ ] Clock sync: `timedatectl status` hoặc `date`

---

## 10. Completion Checklist

Sau bài này, bạn có thể tự đánh giá:

- [ ] Generate self-signed certificate bằng `openssl` hoặc `mkcert` cho local dev
- [ ] Configure Nginx với TLS 1.2 + TLS 1.3, modern cipher suite (Mozilla Intermediate)
- [ ] Verify TLS version và cipher bằng `openssl s_client`
- [ ] Bật HTTP/2 và verify ALPN negotiation bằng `curl -v`
- [ ] Configure HSTS và verify header trong response
- [ ] Configure OCSP stapling và session resumption
- [ ] Redirect HTTP → HTTPS đúng cách (301)
- [ ] Troubleshoot ít nhất 2 lỗi TLS phổ biến (cert mismatch, clock skew)
- [ ] Giải thích được trade-off giữa edge termination, end-to-end TLS và mTLS
- [ ] Biết khi nào dùng `ssl_session_tickets off` và tại sao

---

## 11. References

- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/) - Tool generate Nginx TLS config chuẩn
- [Nginx SSL Module Documentation](https://nginx.org/en/docs/http/ngx_http_ssl_module.html) - Official docs
- [Nginx HTTP/2 Module](https://nginx.org/en/docs/http/ngx_http_v2_module.html) - HTTP/2 configuration
- [TLS 1.3 RFC 8446](https://tools.ietf.org/html/rfc8446) - TLS 1.3 specification
- [ALPN RFC 7301](https://tools.ietf.org/html/rfc7301) - Application-Layer Protocol Negotiation
- [HTTP/2 RFC 7540](https://tools.ietf.org/html/rfc7540) - HTTP/2 specification
- [HPACK RFC 7541](https://tools.ietf.org/html/rfc7541) - Header Compression for HTTP/2
- [OCSP Stapling RFC 6066](https://tools.ietf.org/html/rfc6066) - TLS Extensions
- [Cloudflare: TLS 1.3 Overview](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/) - Excellent deep dive
- [High Performance Browser Networking - HTTP/2](https://hpbn.co/http2/) - Ilya Grigorik, O'Reilly
- [mkcert GitHub](https://github.com/FiloSottile/mkcert) - Local trusted cert tool

---

## Recap

Hôm nay bạn đã học:

- **TLS termination** tại edge: offload CPU từ backend, tập trung certificate management, dễ observe traffic
- **TLS 1.3** vs TLS 1.2: 1-RTT handshake, loại bỏ cipher yếu, forward secrecy bắt buộc
- **Cipher suite** recommendation: dùng Mozilla SSL config generator, tránh RC4/DES/NULL
- **Session resumption**: session cache (server-side) vs session tickets (client-side), security trade-off
- **OCSP stapling**: giảm latency handshake bằng cách server pre-fetch OCSP response
- **HSTS**: buộc browser dùng HTTPS, chống downgrade attack
- **HTTP/2**: multiplexing, binary framing, HPACK header compression → giảm latency với nhiều request nhỏ
- **ALPN**: negotiate h2 vs http/1.1 trong TLS handshake, không cần round trip thêm

## Preview Day 6

**Day 6: Rate Limiting, Connection Limiting & Basic Protection**

Ngày mai bạn sẽ học cách bảo vệ backend khỏi traffic quá tải:
- `limit_req_zone` và `limit_req`: rate limiting theo IP, URI, user
- `limit_conn_zone` và `limit_conn`: giới hạn concurrent connections
- Burst handling: `burst` parameter và `nodelay`
- Phân biệt rate limiting vs connection limiting vs circuit breaker
- Chống DDoS cơ bản tại Nginx layer
- Kết hợp với `geo` module để whitelist IP nội bộ
