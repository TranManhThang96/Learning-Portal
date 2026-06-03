# Day 05: Exercises - TLS Termination, HTTP/2 & Secure Edge

> **Thời lượng thực hành**: 60-90 phút
> **Yêu cầu**: Docker, Docker Compose, openssl, curl (hỗ trợ HTTP/2), h2load (tùy chọn)

---

## Chuẩn bị môi trường

### Kiểm tra tools

```bash
# Kiểm tra openssl
openssl version
# OpenSSL 3.x.x hoặc 1.1.x

# Kiểm tra curl có hỗ trợ HTTP/2
curl --version | grep -i http2
# Phải có: Features: ... HTTP2 ...

# Kiểm tra h2load (optional, từ nghttp2)
h2load --version
# Nếu chưa có: apt install nghttp2-client (Ubuntu) hoặc brew install nghttp2 (macOS)

# Kiểm tra mkcert (optional)
mkcert --version
# Nếu chưa có: https://github.com/FiloSottile/mkcert
```

### Tạo cấu trúc thư mục

```bash
mkdir -p lab-day05/{nginx/conf.d,certs,backend}
cd lab-day05
```

---

## Exercise 1: Generate Self-Signed Certificate

### 1a. Dùng openssl (không cần cài thêm)

```bash
# Generate private key và self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/api.local.key \
  -out certs/api.local.crt \
  -subj "/C=VN/ST=HCM/L=HoChiMinh/O=DevLab/CN=api.local" \
  -addext "subjectAltName=DNS:api.local,DNS:localhost,IP:127.0.0.1"

# Verify certificate
openssl x509 -in certs/api.local.crt -noout -text | grep -A2 "Subject Alternative Name"
# Phải thấy: DNS:api.local, IP Address:127.0.0.1

# Kiểm tra expiry
openssl x509 -in certs/api.local.crt -noout -dates
```

**Output mong đợi:**
```
X509v3 Subject Alternative Name:
    DNS:api.local, DNS:localhost, IP Address:127.0.0.1
notBefore=...
notAfter=... (365 ngày sau)
```

### 1b. Dùng mkcert (trusted by local browser - recommended)

```bash
# Cài mkcert CA vào system trust store
mkcert -install

# Generate cert cho api.local
mkcert -key-file certs/api.local.key \
       -cert-file certs/api.local.crt \
       api.local 127.0.0.1 localhost

# Verify
openssl x509 -in certs/api.local.crt -noout -issuer -subject
```

### 1c. Verify cert và key match

```bash
# Hai hash phải giống nhau
openssl x509 -noout -modulus -in certs/api.local.crt | md5sum
openssl rsa -noout -modulus -in certs/api.local.key | md5sum
```

---

## Exercise 2: Configure Nginx HTTPS với TLS 1.2 + TLS 1.3

### 2a. Tạo backend service

```python
# backend/app.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = json.dumps({
            "service": "backend",
            "path": self.path,
            "protocol": self.request_version
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    print("Backend running on :8080")
    server.serve_forever()
```

### 2b. Tạo Nginx config

```nginx
# nginx/conf.d/api.local.conf

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name api.local localhost;

    # Redirect tất cả HTTP sang HTTPS
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl;
    http2 on;                    # Nginx 1.25+ syntax
    # Nếu dùng Nginx < 1.25: listen 443 ssl http2;
    server_name api.local localhost;

    # Certificate files
    ssl_certificate     /etc/nginx/certs/api.local.crt;
    ssl_certificate_key /etc/nginx/certs/api.local.key;

    # TLS protocols - chỉ TLS 1.2 và 1.3
    ssl_protocols TLSv1.2 TLSv1.3;

    # Cipher suites - Mozilla Intermediate configuration
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Session resumption
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # HSTS - buộc HTTPS trong 2 năm
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to backend
    location / {
        proxy_pass http://backend:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 '{"status":"ok","tls":"enabled"}';
        add_header Content-Type application/json;
    }
}
```

### 2c. Tạo nginx.conf chính

```nginx
# nginx/nginx.conf
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'ssl_protocol=$ssl_protocol ssl_cipher=$ssl_cipher';

    access_log /var/log/nginx/access.log main;
    sendfile on;
    keepalive_timeout 65;

    include /etc/nginx/conf.d/*.conf;
}
```

### 2d. Tạo docker-compose.yml

```yaml
# docker-compose.yml
version: "3.8"

services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - backend
    networks:
      - lab

  backend:
    image: python:3.11-alpine
    command: python /app/app.py
    volumes:
      - ./backend:/app
    networks:
      - lab

networks:
  lab:
    driver: bridge
```

### 2e. Khởi động và test

```bash
# Start services
docker compose up -d

# Kiểm tra Nginx logs
docker compose logs nginx

# Test HTTP redirect
curl -v http://localhost/health
# Phải thấy: HTTP/1.1 301 Moved Permanently
# Location: https://localhost/health
```

---

## Exercise 3: Test TLS Version và Cipher Suite

### 3a. Test TLS 1.3

```bash
# Test TLS 1.3 connection
openssl s_client -connect localhost:443 -tls1_3 \
  -servername localhost </dev/null 2>&1 | grep -E "Protocol|Cipher|Session-ID"

# Output mong đợi:
# Protocol  : TLSv1.3
# Cipher    : TLS_AES_256_GCM_SHA384 (hoặc TLS_AES_128_GCM_SHA256)
```

### 3b. Test TLS 1.2

```bash
openssl s_client -connect localhost:443 -tls1_2 \
  -servername localhost </dev/null 2>&1 | grep -E "Protocol|Cipher"

# Output mong đợi:
# Protocol  : TLSv1.2
# Cipher    : ECDHE-RSA-AES256-GCM-SHA384 (hoặc tương tự)
```

### 3c. Verify TLS 1.0 và 1.1 bị từ chối

```bash
# TLS 1.0 phải bị reject
openssl s_client -connect localhost:443 -tls1 \
  -servername localhost </dev/null 2>&1 | grep -E "alert|error|Protocol"

# Output mong đợi:
# alert handshake failure
# hoặc: no protocols available
```

### 3d. Xem full certificate chain

```bash
openssl s_client -connect localhost:443 -showcerts \
  -servername localhost </dev/null 2>&1 | grep -E "subject|issuer|notAfter"
```

---

## Exercise 4: Test HTTP/2 và ALPN Negotiation

### 4a. Verify ALPN negotiation

```bash
# Xem ALPN trong TLS handshake
openssl s_client -connect localhost:443 -alpn h2 \
  -servername localhost </dev/null 2>&1 | grep -i "ALPN\|protocol"

# Output mong đợi:
# ALPN protocol: h2
```

### 4b. Test HTTP/2 với curl

```bash
# Verbose để xem ALPN và HTTP version
curl -v --http2 \
  --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/health 2>&1 | grep -E "ALPN|HTTP/2|< HTTP"

# Output mong đợi:
# * ALPN: offering h2
# * ALPN: server accepted h2
# < HTTP/2 200
```

### 4c. So sánh HTTP/1.1 vs HTTP/2

```bash
# Force HTTP/1.1
curl -v --http1.1 \
  --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/health 2>&1 | grep "< HTTP"
# Output: < HTTP/1.1 200 OK

# Force HTTP/2
curl -v --http2 \
  --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/health 2>&1 | grep "< HTTP"
# Output: < HTTP/2 200
```

### 4d. Verify HSTS header

```bash
curl -sI \
  --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/health | grep -i "strict\|x-frame\|x-content"

# Output mong đợi:
# strict-transport-security: max-age=63072000; includeSubDomains
# x-frame-options: DENY
# x-content-type-options: nosniff
```

---

## Exercise 5: Session Resumption Test

### 5a. Test session resumption với openssl

```bash
# Lần 1: Full handshake
openssl s_client -connect localhost:443 -tls1_2 \
  -servername localhost -sess_out /tmp/session.pem </dev/null 2>&1 \
  | grep -E "Session-ID|Reused"

# Lần 2: Resumption với session
openssl s_client -connect localhost:443 -tls1_2 \
  -servername localhost -sess_in /tmp/session.pem </dev/null 2>&1 \
  | grep -E "Session-ID|Reused"

# Output mong đợi lần 2:
# Reused, TLSv1.2, Cipher is ECDHE-RSA-AES256-GCM-SHA384
```

### 5b. Benchmark session resumption

```bash
# Full handshake (new sessions)
openssl s_time -connect localhost:443 -new -time 10 2>&1 | tail -5

# Session resumption
openssl s_time -connect localhost:443 -reuse -time 10 2>&1 | tail -5

# So sánh connections/second: resumption phải nhanh hơn đáng kể
```

---

## Exercise 6: Benchmark HTTP/1.1 vs HTTP/2

### 6a. Benchmark với h2load (HTTP/2 specific)

```bash
# HTTP/2 benchmark
h2load -n 10000 -c 50 -m 10 \
  -k --connect-to=127.0.0.1:443 \
  https://api.local/health

# Giải thích flags:
# -n 10000: tổng số requests
# -c 50: concurrent clients
# -m 10: max concurrent streams per client (HTTP/2 multiplexing)
```

**Output mong đợi:**
```
finished in X.XXs, YYYY req/s, ZZZ KB/s
requests: 10000 total, 10000 started, 10000 done, 10000 succeeded, 0 failed
status codes: 10000 2xx, 0 3xx, 0 4xx, 0 5xx
traffic: XXX KB (headers) + YYY KB (data) = ZZZ KB
min  max  mean  sd  +/- sd
time for request: Xms  Yms  Zms  Wms  XX%
```

### 6b. Benchmark với wrk (HTTP/1.1)

```bash
# HTTP/1.1 benchmark (wrk không hỗ trợ HTTP/2)
wrk -t4 -c50 -d30s --latency \
  --header "Host: api.local" \
  https://localhost/health

# Lưu ý: wrk dùng localhost thay vì api.local vì không có --resolve
```

### 6c. So sánh kết quả

Ghi lại kết quả vào bảng:

| Metric | HTTP/1.1 (wrk) | HTTP/2 (h2load) |
|---|---|---|
| Requests/sec | | |
| Latency p50 | | |
| Latency p99 | | |
| Error rate | | |

**Nhận xét**: HTTP/2 thường cho throughput cao hơn với nhiều concurrent requests nhỏ do multiplexing.

---

## Exercise 7: Mô phỏng Certificate Expiry Monitoring

### 7a. Kiểm tra ngày hết hạn hiện tại

```bash
# Cert local được tạo ở Exercise 1 có hạn 365 ngày
openssl x509 -in certs/api.local.crt -noout -dates
# Output:
# notBefore=...
# notAfter=... (365 ngày sau ngày tạo)
```

### 7b. Verify certificate tại một thời điểm tương lai

```bash
# Lấy epoch của thời điểm 400 ngày sau.
# Linux:
FUTURE_EPOCH=$(date -d "+400 days" +%s)

# macOS:
# FUTURE_EPOCH=$(date -v+400d +%s)

# Vì đây là self-signed cert, dùng chính cert làm trust anchor để chỉ tập trung vào expiry.
openssl verify \
  -CAfile certs/api.local.crt \
  -attime "$FUTURE_EPOCH" \
  certs/api.local.crt
```

**Output mong đợi:**
```
C = VN, ST = HCM, L = HoChiMinh, O = DevLab, CN = api.local
error 10 at 0 depth lookup: certificate has expired
error certs/api.local.crt: verification failed
```

### 7c. Kiểm tra expiry từ server đang chạy

```bash
# Lấy notAfter từ server qua TLS handshake
echo | openssl s_client -connect localhost:443 -servername localhost 2>/dev/null \
  | openssl x509 -noout -enddate

# Script cảnh báo nếu cert còn dưới 30 ngày.
EXPIRY=$(echo | openssl s_client -connect localhost:443 -servername localhost 2>/dev/null \
  | openssl x509 -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %e %T %Y %Z" "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
echo "Certificate expires in ${DAYS_LEFT} days"
```

Production nên đưa check này vào Prometheus blackbox exporter, synthetic monitoring hoặc job cảnh báo riêng. Không đợi `curl` của user báo `certificate has expired` mới phát hiện.

---

## Exercise 8: OCSP Stapling (Advanced)

> Lưu ý: OCSP stapling chỉ hoạt động với cert từ CA thật (Let's Encrypt, DigiCert, etc.), không hoạt động với self-signed cert. Bài này chỉ configure và verify config syntax.

### 8a. Configure OCSP stapling

```nginx
# Thêm vào server block trong api.local.conf
ssl_stapling on;
ssl_stapling_verify on;

# Cần trusted CA certificate để verify OCSP response
# ssl_trusted_certificate /etc/nginx/certs/ca-chain.crt;

# DNS resolver để Nginx query OCSP server
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;
```

### 8b. Verify config syntax

```bash
docker compose exec nginx nginx -t
# Output: nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 8c. Check OCSP stapling status (với cert thật)

```bash
# Với cert từ Let's Encrypt hoặc CA thật:
openssl s_client -connect yourdomain.com:443 -status \
  -servername yourdomain.com </dev/null 2>&1 | grep -A 10 "OCSP response"

# Output mong đợi với OCSP stapling hoạt động:
# OCSP Response Status: successful (0x0)
# This Update: ...
# Next Update: ...
```

---

## Exercise 9: Challenge - Nginx Version Syntax

Nginx 1.25 thay đổi cú pháp HTTP/2. Thực hành cả hai:

### Nginx < 1.25 (cú pháp cũ)

```nginx
listen 443 ssl http2;
# http2 được khai báo trong listen directive
```

### Nginx >= 1.25 (cú pháp mới)

```nginx
listen 443 ssl;
http2 on;
# http2 là directive riêng biệt
```

### Test với Nginx 1.24 (cú pháp cũ)

```bash
# Thay image trong docker-compose.yml
# image: nginx:1.24-alpine

# Dùng cú pháp cũ trong config
# listen 443 ssl http2;
# Xóa dòng: http2 on;

docker compose up -d --force-recreate nginx
curl --http2 -sk --resolve api.local:443:127.0.0.1 \
  --cacert certs/api.local.crt \
  https://api.local/health -o /dev/null -w "%{http_version}\n"
# Output: 2
```

---

## Exercise 10: Cleanup

```bash
# Dừng và xóa containers
docker compose down

# Xóa certs (optional)
rm -rf certs/

# Xóa session file
rm -f /tmp/session.pem
```

---

## Tổng kết

Sau khi hoàn thành các exercises, bạn đã thực hành:

1. Generate self-signed certificate bằng `openssl` và `mkcert`
2. Configure Nginx HTTPS với TLS 1.2 + TLS 1.3, modern cipher suite
3. Verify TLS version, cipher suite bằng `openssl s_client`
4. Bật HTTP/2 và verify ALPN negotiation bằng `curl -v`
5. Test session resumption và đo performance improvement
6. Benchmark HTTP/1.1 vs HTTP/2 với `h2load` và `wrk`
7. Mô phỏng certificate expired và observe lỗi
8. Configure OCSP stapling và HSTS
9. Phân biệt Nginx syntax cho HTTP/2 theo version
