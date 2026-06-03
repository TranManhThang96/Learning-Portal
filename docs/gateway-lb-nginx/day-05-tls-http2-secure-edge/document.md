# Day 05: Document - TLS Internals, HTTP/2 Deep Dive & Reference Configurations

> Tài liệu tham khảo bổ sung cho Day 05. Đọc khi cần hiểu sâu hơn về TLS internals, HTTP/2 mechanics, hoặc tra cứu configuration.

---

## 1. TLS Handshake Deep Dive

### 1.1 TLS 1.2 Full Handshake (2-RTT)

```
Client                                          Server
  │                                               │
  │──── ClientHello ─────────────────────────────►│
  │     - TLS version: 1.2                        │
  │     - Random: client_random (32 bytes)        │
  │     - Session ID: (empty hoặc resumption ID)  │
  │     - Cipher Suites: [list]                   │
  │     - Extensions: SNI, ALPN, ...              │
  │                                               │
  │◄─── ServerHello ─────────────────────────────│
  │     - TLS version: 1.2                        │
  │     - Random: server_random (32 bytes)        │
  │     - Session ID: new_session_id              │
  │     - Cipher Suite: chosen_cipher             │
  │     - Extensions: ALPN response, ...         │
  │                                               │
  │◄─── Certificate ─────────────────────────────│
  │     - Server certificate chain                │
  │                                               │
  │◄─── ServerKeyExchange ───────────────────────│
  │     - ECDHE params (nếu dùng ECDHE)           │
  │     - Signature                               │
  │                                               │
  │◄─── ServerHelloDone ─────────────────────────│
  │                                               │
  │  [Client verify cert chain]                   │
  │  [Client generate pre-master secret]          │
  │  [Derive master secret từ pre-master + randoms]│
  │                                               │
  │──── ClientKeyExchange ───────────────────────►│
  │     - Encrypted pre-master secret (RSA)       │
  │     - hoặc ECDHE public key                   │
  │                                               │
  │──── ChangeCipherSpec ────────────────────────►│
  │──── Finished ────────────────────────────────►│
  │     - Verify data (HMAC của toàn bộ handshake)│
  │                                               │
  │◄─── ChangeCipherSpec ────────────────────────│
  │◄─── Finished ────────────────────────────────│
  │                                               │
  │════ Application Data (HTTP/2 or HTTP/1.1) ════│
  │     (encrypted với session keys)              │
```

**RTT count**: 2 round trips trước khi gửi application data.

### 1.2 TLS 1.3 Handshake (1-RTT)

```
Client                                          Server
  │                                               │
  │──── ClientHello ─────────────────────────────►│
  │     - TLS version: 1.3 (trong supported_versions extension)
  │     - Random: client_random                   │
  │     - Cipher Suites: [TLS 1.3 only]           │
  │     - key_share: ECDHE public key             │
  │     - supported_versions: [1.3, 1.2]          │
  │     - Extensions: SNI, ALPN, ...              │
  │                                               │
  │◄─── ServerHello ─────────────────────────────│
  │     - key_share: server ECDHE public key      │
  │     - supported_versions: 1.3                 │
  │                                               │
  │  [Cả hai bên derive handshake keys ngay]      │
  │                                               │
  │◄─── EncryptedExtensions ─────────────────────│  (encrypted!)
  │◄─── Certificate ─────────────────────────────│  (encrypted!)
  │◄─── CertificateVerify ───────────────────────│  (encrypted!)
  │◄─── Finished ────────────────────────────────│  (encrypted!)
  │                                               │
  │  [Client verify cert và Finished]             │
  │  [Derive application keys]                    │
  │                                               │
  │──── Finished ────────────────────────────────►│
  │                                               │
  │════ Application Data ═════════════════════════│
```

**RTT count**: 1 round trip. Server gửi cert và Finished trong cùng flight với ServerHello.

**TLS 1.3 improvements:**
- Loại bỏ RSA key exchange (chỉ còn ECDHE/DHE → forward secrecy bắt buộc)
- Loại bỏ cipher yếu: RC4, DES, 3DES, MD5, SHA-1
- Encrypt nhiều hơn trong handshake (cert, extensions)
- 0-RTT resumption (Early Data) - có trade-off về replay attack

### 1.3 TLS 1.3 0-RTT Resumption

```
Client                                          Server
  │                                               │
  │  [Client có PSK từ session trước]             │
  │                                               │
  │──── ClientHello ─────────────────────────────►│
  │     - pre_shared_key extension                │
  │     - early_data extension                    │
  │                                               │
  │──── Early Data (0-RTT) ─────────────────────►│  ← gửi ngay, không cần đợi
  │     (HTTP request)                            │
  │                                               │
  │◄─── ServerHello ─────────────────────────────│
  │◄─── ... (rest of handshake) ─────────────────│
  │◄─── EndOfEarlyData ──────────────────────────│
  │                                               │
  │════ Application Data ═════════════════════════│
```

**0-RTT trade-off**: Replay attack risk. Attacker có thể replay Early Data. Chỉ dùng cho idempotent requests (GET). Nginx không hỗ trợ 0-RTT (an toàn hơn).

---

## 2. Cipher Suite Reference

### 2.1 Anatomy of a Cipher Suite

```
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
│    │      │        │           │
│    │      │        │           └── PRF/MAC: SHA-384
│    │      │        └────────────── Bulk encryption: AES-256-GCM (AEAD)
│    │      └─────────────────────── Authentication: RSA
│    └────────────────────────────── Key exchange: ECDHE
└─────────────────────────────────── Protocol: TLS
```

### 2.2 TLS 1.3 Cipher Suites (chỉ 5 suite)

| Cipher Suite | Key Exchange | Encryption | Hash |
|---|---|---|---|
| TLS_AES_256_GCM_SHA384 | ECDHE (trong key_share) | AES-256-GCM | SHA-384 |
| TLS_CHACHA20_POLY1305_SHA256 | ECDHE | ChaCha20-Poly1305 | SHA-256 |
| TLS_AES_128_GCM_SHA256 | ECDHE | AES-128-GCM | SHA-256 |
| TLS_AES_128_CCM_SHA256 | ECDHE | AES-128-CCM | SHA-256 |
| TLS_AES_128_CCM_8_SHA256 | ECDHE | AES-128-CCM-8 | SHA-256 |

TLS 1.3 không cần specify key exchange trong cipher suite vì ECDHE là bắt buộc.

### 2.3 Mozilla SSL Config Recommendations

**Modern** (TLS 1.3 only, highest security):
```nginx
ssl_protocols TLSv1.3;
ssl_prefer_server_ciphers off;
```

**Intermediate** (TLS 1.2 + 1.3, recommended cho hầu hết):
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

**Old** (TLS 1.0+, cho legacy clients - không khuyến nghị):
```nginx
ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
# Không dùng trong production mới
```

### 2.4 Cipher Strength Ranking

```
Strongest (TLS 1.3):
  TLS_AES_256_GCM_SHA384
  TLS_CHACHA20_POLY1305_SHA256
  TLS_AES_128_GCM_SHA256

Strong (TLS 1.2, ECDHE + AEAD):
  ECDHE-ECDSA-AES256-GCM-SHA384
  ECDHE-RSA-AES256-GCM-SHA384
  ECDHE-ECDSA-CHACHA20-POLY1305
  ECDHE-RSA-CHACHA20-POLY1305
  ECDHE-ECDSA-AES128-GCM-SHA256
  ECDHE-RSA-AES128-GCM-SHA256

Acceptable (TLS 1.2, DHE + AEAD):
  DHE-RSA-AES256-GCM-SHA384
  DHE-RSA-AES128-GCM-SHA256

Weak (không dùng):
  RC4-* (stream cipher, broken)
  DES-* (56-bit key, broken)
  3DES-* (SWEET32 attack)
  *-CBC-SHA (BEAST, Lucky13)
  *-NULL-* (no encryption!)
  *-EXPORT-* (40-bit key, broken)
  *-anon-* (no authentication)
```

---

## 3. HTTP/2 Internals

### 3.1 Frame Structure

Mỗi HTTP/2 frame có format:

```
+-----------------------------------------------+
|                 Length (24)                    |
+---------------+---------------+---------------+
|   Type (8)    |   Flags (8)   |
+-+-------------+---------------+-------------------------------+
|R|                 Stream Identifier (31)                      |
+=+=============================================================+
|                   Frame Payload (0...)                      ...
+---------------------------------------------------------------+
```

- **Length**: payload size (max 16MB với SETTINGS_MAX_FRAME_SIZE)
- **Type**: HEADERS(0x1), DATA(0x0), SETTINGS(0x4), WINDOW_UPDATE(0x8), etc.
- **Flags**: END_STREAM, END_HEADERS, PADDED, PRIORITY
- **Stream ID**: 0 = connection-level, odd = client-initiated, even = server-initiated

### 3.2 HPACK Header Compression

HPACK dùng 2 kỹ thuật:

**Static Table** (61 entries được định nghĩa sẵn):
```
Index | Header Name          | Header Value
  1   | :authority           |
  2   | :method              | GET
  3   | :method              | POST
  4   | :path                | /
  5   | :path                | /index.html
  ...
 61   | www-authenticate     |
```

**Dynamic Table** (được build trong session):
- Client và server maintain cùng dynamic table
- Mỗi header mới được thêm vào table
- Subsequent requests reference bằng index thay vì gửi full header

**Ví dụ compression:**
```
Request 1: GET /api/users HTTP/2
Headers: :method GET, :path /api/users, :scheme https, host api.local
→ Gửi full headers, thêm vào dynamic table

Request 2: GET /api/orders HTTP/2
Headers: :method GET, :path /api/orders, :scheme https, host api.local
→ :method = index 2 (static table, 1 byte)
→ :scheme = index (dynamic table, 1 byte)
→ host = index (dynamic table, 1 byte)
→ :path = literal "/api/orders" (chỉ path thay đổi)
→ Tiết kiệm ~70% bandwidth cho headers
```

### 3.3 Flow Control

HTTP/2 có flow control ở 2 level:

**Connection-level**: tổng data có thể gửi trên connection
**Stream-level**: data có thể gửi trên từng stream

```
Initial window size: 65535 bytes (default)
→ Sender không thể gửi quá window size
→ Receiver gửi WINDOW_UPDATE frame để tăng window
→ Nginx: http2_recv_buffer_size, http2_chunk_size
```

### 3.4 Server Push (Deprecated)

Server push cho phép server gửi resource trước khi client hỏi:

```
Client: GET /index.html
Server: PUSH_PROMISE /style.css
Server: PUSH_PROMISE /app.js
Server: HEADERS + DATA /index.html
Server: HEADERS + DATA /style.css  (pushed)
Server: HEADERS + DATA /app.js     (pushed)
```

**Tại sao deprecated**: Browser cache không được check trước khi push → lãng phí bandwidth. Chrome đã remove support. Thay thế bằng HTTP `103 Early Hints` hoặc `Link: rel=preload` header.

---

## 4. OCSP Stapling Deep Dive

### 4.1 OCSP Protocol Flow

```
Certificate Authority (CA)
  ├── Root CA
  └── Intermediate CA
        └── Server Certificate (có OCSP URL trong AIA extension)

OCSP URL: http://ocsp.example-ca.com/

OCSP Request:
  - Certificate serial number
  - Issuer name hash
  - Issuer key hash

OCSP Response:
  - Status: good / revoked / unknown
  - This Update: timestamp
  - Next Update: timestamp (validity period)
  - Signature (signed by CA)
```

### 4.2 Nginx OCSP Stapling Configuration

```nginx
# Bật OCSP stapling
ssl_stapling on;

# Verify OCSP response signature
ssl_stapling_verify on;

# CA certificate để verify OCSP response
# Cần nếu ssl_certificate không chứa full chain
ssl_trusted_certificate /etc/nginx/certs/ca-chain.crt;

# DNS resolver để Nginx query OCSP server
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;
```

**Nginx OCSP stapling behavior:**
1. Nginx fetch OCSP response từ CA khi start (hoặc khi response expire)
2. Cache OCSP response trong memory
3. Staple response vào TLS handshake cho mỗi client
4. Refresh OCSP response trước khi expire (Next Update)

### 4.3 Verify OCSP Stapling

```bash
# Kiểm tra OCSP stapling từ server
openssl s_client -connect yourdomain.com:443 \
  -servername yourdomain.com \
  -status </dev/null 2>&1 | grep -A 20 "OCSP response"

# Output khi OCSP stapling hoạt động:
# OCSP Response Data:
#     OCSP Response Status: successful (0x0)
#     Response Type: Basic OCSP Response
#     Version: 1 (0x0)
#     Responder Id: ...
#     Produced At: ...
#     Responses:
#     Certificate ID:
#       Hash Algorithm: sha1
#       Issuer Name Hash: ...
#       Issuer Key Hash: ...
#       Serial Number: ...
#     Cert Status: good
#     This Update: ...
#     Next Update: ...
```

---

## 5. HSTS (HTTP Strict Transport Security)

### 5.1 HSTS Header

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

- **max-age**: số giây browser nhớ HSTS policy (63072000 = 2 năm)
- **includeSubDomains**: áp dụng cho tất cả subdomain
- **preload**: đăng ký vào HSTS preload list (browser built-in)

### 5.2 HSTS Preload List

HSTS preload list là danh sách domain được hardcode trong browser (Chrome, Firefox, Safari, Edge). Browser sẽ luôn dùng HTTPS cho các domain này, ngay cả lần đầu tiên truy cập.

Để đăng ký: https://hstspreload.org/

**Yêu cầu để preload:**
- Có valid HTTPS certificate
- Redirect HTTP → HTTPS
- HSTS header với max-age >= 31536000 (1 năm)
- includeSubDomains
- preload directive

**Cảnh báo**: Sau khi preload, rất khó remove. Nếu HTTPS bị lỗi, toàn bộ domain không truy cập được.

### 5.3 HSTS Bypass Attack (không có HSTS)

```
Attacker (MITM)
  │
  ├── Client gửi: http://bank.com/login
  │
  ├── Attacker intercept, forward đến: https://bank.com/login
  │
  ├── bank.com trả về: HTTPS response
  │
  ├── Attacker forward về client qua HTTP
  │
  └── Client thấy HTTP, không biết đang bị MITM
```

Với HSTS: browser tự động upgrade http:// → https:// trước khi gửi request → attacker không thể intercept.

---

## 6. SNI (Server Name Indication)

### 6.1 Vấn đề trước SNI

Trước SNI, một IP chỉ có thể serve một TLS certificate. Vì TLS handshake xảy ra trước HTTP request, server không biết client muốn truy cập domain nào để chọn đúng cert.

### 6.2 SNI Solution

SNI là TLS extension cho phép client gửi hostname trong ClientHello:

```
ClientHello:
  extensions:
    server_name: api.local    ← SNI
    ALPN: ["h2", "http/1.1"]
    ...
```

Server đọc SNI → chọn đúng certificate → handshake tiếp tục.

### 6.3 Nginx SNI Configuration

```nginx
# Virtual host 1
server {
    listen 443 ssl;
    server_name api.local;
    ssl_certificate /etc/nginx/certs/api.local.crt;
    ssl_certificate_key /etc/nginx/certs/api.local.key;
}

# Virtual host 2 (cùng IP, khác domain)
server {
    listen 443 ssl;
    server_name admin.local;
    ssl_certificate /etc/nginx/certs/admin.local.crt;
    ssl_certificate_key /etc/nginx/certs/admin.local.key;
}
```

Nginx dùng SNI để chọn đúng server block và certificate.

---

## 7. mTLS Overview (Preview Day 11)

### 7.1 mTLS vs TLS

**TLS (one-way)**: chỉ client verify server certificate
**mTLS (mutual TLS)**: cả hai bên verify certificate của nhau

```
TLS:
  Client ──verify server cert──► Server
  (client không cần cert)

mTLS:
  Client ──verify server cert──► Server
  Client ◄──verify client cert── Server
  (cả hai đều cần cert)
```

### 7.2 Khi nào dùng mTLS

- Service-to-service authentication trong microservices
- Zero-trust network (không tin tưởng internal network)
- API access cho machine clients (không phải browser)
- Compliance yêu cầu mutual authentication

### 7.3 mTLS Nginx Config (Preview)

```nginx
# Server config
ssl_client_certificate /etc/nginx/certs/client-ca.crt;
ssl_verify_client on;
ssl_verify_depth 2;

# Trong location block
if ($ssl_client_verify != SUCCESS) {
    return 403;
}
```

Chi tiết sẽ học ở Day 11.

---

## 8. Complete Nginx TLS Reference Configuration

```nginx
# /etc/nginx/conf.d/secure-api.conf

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name api.example.com;

    # ACME challenge cho Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;                          # Nginx 1.25+
    server_name api.example.com;

    # ─── Certificate ───────────────────────────────────────────
    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    # ─── Protocol & Cipher ─────────────────────────────────────
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # ─── Session Resumption ────────────────────────────────────
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # ─── OCSP Stapling ─────────────────────────────────────────
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/api.example.com/chain.pem;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # ─── Security Headers ──────────────────────────────────────
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    # ─── TLS Buffer Optimization ───────────────────────────────
    ssl_buffer_size 4k;                # Giảm TTFB (default 16k)

    # ─── Proxy ─────────────────────────────────────────────────
    location / {
        proxy_pass http://backend_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host  $host;
        proxy_set_header X-Forwarded-Port  $server_port;

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;
    }
}

upstream backend_upstream {
    keepalive 32;
    server backend1:8080;
    server backend2:8080;
}
```

---

## 9. Observability cho TLS

### 9.1 Nginx Log Variables cho TLS

```nginx
log_format tls_detail '$remote_addr - $remote_user [$time_local] '
                      '"$request" $status $body_bytes_sent '
                      'ssl_protocol=$ssl_protocol '
                      'ssl_cipher=$ssl_cipher '
                      'ssl_session_reused=$ssl_session_reused '
                      'ssl_server_name=$ssl_server_name '
                      'http2=$http2';
```

Các biến quan trọng:
- `$ssl_protocol`: TLSv1.2 hoặc TLSv1.3
- `$ssl_cipher`: cipher suite được chọn
- `$ssl_session_reused`: "r" nếu session được reuse, "." nếu full handshake
- `$ssl_server_name`: SNI hostname
- `$http2`: "h2" nếu HTTP/2, "" nếu HTTP/1.1

### 9.2 Metrics cần monitor

| Metric | Ý nghĩa | Alert khi |
|---|---|---|
| `nginx_ssl_handshakes_total` | Tổng TLS handshakes | Tăng đột biến |
| `nginx_ssl_handshakes_failed_total` | Handshake failures | > 1% |
| `nginx_ssl_session_reuses_total` | Session resumptions | Giảm đột ngột |
| Certificate expiry | Ngày hết hạn cert | < 30 ngày |
| TLS 1.0/1.1 connections | Legacy client | > 0 (nếu đã disable) |

### 9.3 Certificate Expiry Monitoring

```bash
# Script kiểm tra cert expiry
#!/bin/bash
DOMAIN="api.example.com"
DAYS_WARN=30

EXPIRY=$(echo | openssl s_client -connect $DOMAIN:443 -servername $DOMAIN 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null \
  | cut -d= -f2)

EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

if [ $DAYS_LEFT -lt $DAYS_WARN ]; then
    echo "WARNING: Certificate for $DOMAIN expires in $DAYS_LEFT days!"
    # Send alert: Slack, PagerDuty, email...
fi
```

---

## 10. Troubleshooting Reference

### 10.1 openssl s_client Cheat Sheet

```bash
# Basic connection test
openssl s_client -connect host:443 -servername host

# Test specific TLS version
openssl s_client -connect host:443 -tls1_2
openssl s_client -connect host:443 -tls1_3

# Test specific cipher
openssl s_client -connect host:443 -cipher ECDHE-RSA-AES256-GCM-SHA384

# Show OCSP stapling
openssl s_client -connect host:443 -status

# Show full cert chain
openssl s_client -connect host:443 -showcerts

# Test with ALPN
openssl s_client -connect host:443 -alpn h2

# Test session resumption
openssl s_client -connect host:443 -sess_out /tmp/sess.pem
openssl s_client -connect host:443 -sess_in /tmp/sess.pem

# Benchmark connections/second
openssl s_time -connect host:443 -new -time 10
openssl s_time -connect host:443 -reuse -time 10
```

### 10.2 curl TLS Cheat Sheet

```bash
# Verbose TLS info
curl -v https://host/

# Force TLS version
curl --tlsv1.2 https://host/
curl --tlsv1.3 https://host/

# Force HTTP/2
curl --http2 https://host/

# Skip cert verification (dev only!)
curl -k https://host/

# Use custom CA cert
curl --cacert /path/to/ca.crt https://host/

# Use custom cert + key (mTLS)
curl --cert /path/to/client.crt --key /path/to/client.key https://host/

# Show response headers only
curl -sI https://host/

# Resolve hostname manually
curl --resolve api.local:443:127.0.0.1 https://api.local/
```
