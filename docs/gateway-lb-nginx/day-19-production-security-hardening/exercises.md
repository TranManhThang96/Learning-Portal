# Day 19: Production Security Hardening — Hands-on Labs

> Các bài lab chi tiết cho Day 19. Chuẩn bị: Docker, Docker Compose, `openssl`, `curl`, `slowhttptest`, `nikto`, `testssl.sh`.
>
> **Lưu ý quan trọng**: Mọi certificate/key trong lab chỉ dùng cho local development. Không dùng trên production.

---

## Lab 0: Chuẩn bị môi trường

```bash
# Tạo cấu trúc thư mục
mkdir -p day19-security/{nginx/conf.d,nginx/ssl,certs,kong,tools}
cd day19-security

# Kiem tra tools can thiet
which slowhttptest nikto testssl.sh 2>/dev/null || \
  echo "Can cai dat: slowhttptest, nikto, testssl.sh"

# Docker Compose version
docker compose version
```

---

## Lab 1: Kong Admin API behind Nginx Proxy + Basic Auth + IP Allowlist

### Muc tiêu
- Kong Admin API chi accessible qua Nginx proxy on 127.0.0.1
- Basic Auth bat buoc
- IP allowlist chi cho internal CIDR

### 1.1 Tao htpasswd cho Basic Auth

```bash
# Cai dat htpasswd (co san trong httpd-tools hoac apache2-utils)
# Tren Alpine/Debian:
#   apk add apache2-utils
#   apt install apache2-utils

# Tao user: admin (mat khau: KongAdmin2024!)
htpasswd -bc nginx/.htpasswd_kong_admin admin KongAdmin2024!

# Them them user thu hai
htpasswd -b nginx/.htpasswd_kong_admin readonly ReadOnlyPass99!

# Xem noi dung (encrypted)
cat nginx/.htpasswd_kong_admin
# Output: admin:$apr1$xxxxxxx$encrypted_hash
#        readonly:$apr1$xxxxxxx$encrypted_hash
```

### 1.2 Tao self-signed cert cho Admin Proxy

```bash
# CA certificate
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout nginx/ssl/internal-ca.key \
  -out nginx/ssl/internal-ca.crt \
  -subj "/C=VN/ST=HCM/L=HCM/O=Internal/CN=Internal Root CA" \
  -addext "basicConstraints=critical,CA:TRUE"

# Server certificate cho Kong Admin Proxy
openssl req -new -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout nginx/ssl/kong-admin.key \
  -out nginx/ssl/kong-admin.csr \
  -subj "/C=VN/ST=HCM/O=Internal/CN=127.0.0.1"

openssl x509 -req -days 365 \
  -in nginx/ssl/kong-admin.csr \
  -CA nginx/ssl/internal-ca.crt \
  -CAkey nginx/ssl/internal-ca.key \
  -CAcreateserial \
  -out nginx/ssl/kong-admin.crt \
  -extfile <(printf \
    "subjectAltName=IP:127.0.0.1,DNS:localhost")

# Cleanup CSR
rm nginx/ssl/kong-admin.csr

# Verify cert
openssl verify -CAfile nginx/ssl/internal-ca.crt \
  nginx/ssl/kong-admin.crt
# Output: nginx/ssl/kong-admin.crt: OK
```

### 1.3 Nginx Admin Proxy Config

**File: `nginx/conf.d/kong-admin-proxy.conf`**

```nginx
server {
    listen 127.0.0.1:8444 ssl;
    server_name kong-admin-internal;

    ssl_certificate     /etc/nginx/ssl/kong-admin.crt;
    ssl_certificate_key /etc/nginx/ssl/kong-admin.key;

    # Optional mTLS: client cert tu internal CA
    ssl_client_certificate /etc/nginx/ssl/internal-ca.crt;
    ssl_verify_client optional;
    ssl_verify_depth 2;

    # Basic Auth bat buoc
    auth_basic "Kong Admin API — Authorized Only";
    auth_basic_user_file /etc/nginx/ssl/.htpasswd_kong_admin;

    # IP Allowlist: chi internal CIDR
    allow 127.0.0.0/8;
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 192.168.0.0/16;
    deny all;

    # Strip Kong internal headers
    proxy_hide_header Server;
    proxy_hide_header X-Kong-Admin-Latency;
    proxy_hide_header X-Kong-Response-Latency;
    proxy_hide_header X-Kong-Upstream-Latency;
    proxy_hide_header X-Kong-Proxy-Latency;
    proxy_hide_header Via;
    proxy_hide_header X-Request-Id;

    location / {
        proxy_pass         http://127.0.0.1:8001;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;
    }
}
```

### 1.4 Docker Compose

**File: `docker-compose.yml`**

```yaml
version: "3.8"

services:
  # === Kong DB-less Proxy (Data Plane mode) ===
  kong-proxy:
    image: kong:3.7
    container_name: kong-proxy
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
      - /var/run/kong:rw
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_PROXY_LISTEN: "0.0.0.0:8000,0.0.0.0:8443 ssl"
      # Admin API chi listen 127.0.0.1
      KONG_ADMIN_LISTEN: "127.0.0.1:8001,127.0.0.1:8444 ssl"
      KONG_LOG_LEVEL: "notice"
      KONG_PLUGINS: "bundled,response-transformer,key-auth,rate-limiting,acl"
    volumes:
      - ./kong/kong.yml:/kong/kong.yml:ro
      - kong-tmp:/tmp
    networks:
      - kong-net
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # === Nginx Admin Proxy (fronts Kong Admin API) ===
  nginx-admin-proxy:
    image: nginx:1.25-alpine
    container_name: nginx-admin-proxy
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=32m
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    ports:
      # Chi expose Admin Proxy port 8444
      - "127.0.0.1:8444:127.0.0.1:8444"
      # Proxy port public
      - "8000:8000"
      - "8443:8443"
    volumes:
      - ./nginx/conf.d/kong-admin-proxy.conf:/etc/nginx/conf.d/kong-admin-proxy.conf:ro
      - ./nginx/conf.d/kong-proxy.conf:/etc/nginx/conf.d/kong-proxy.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/.htpasswd_kong_admin:/etc/nginx/ssl/.htpasswd_kong_admin:ro
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    networks:
      - kong-net
    depends_on:
      - kong-proxy

volumes:
  kong-tmp:
    driver: local

networks:
  kong-net:
    driver: bridge
    internal: false
```

**File: `nginx/nginx.conf`**

```nginx
user  nginx;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format secure
        '$remote_addr - $remote_user [$time_local] '
        '"$request" $status $body_bytes_sent '
        '"$http_referer" "$http_user_agent" '
        'rt=$request_time uip=$http_x_forwarded_for';

    access_log /var/log/nginx/access.log secure;

    server_tokens off;
    sendfile    on;
    tcp_nopush  on;

    include /etc/nginx/conf.d/*.conf;
}
```

**File: `nginx/conf.d/kong-proxy.conf`**

```nginx
upstream kong_backend {
    server kong-proxy:8000;
    keepalive 64;
}

# === PUBLIC HTTPS ===
server {
    listen      8443 ssl;
    http2       on;
    server_name localhost;

    ssl_certificate     /etc/nginx/ssl/kong-admin.crt;
    ssl_certificate_key /etc/nginx/ssl/kong-admin.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    location / {
        limit_req zone=default burst=50 nodelay;
        limit_conn conn_limit 200;

        proxy_pass         http://kong_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        proxy_connect_timeout 5s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }
}

# === HTTP ===
server {
    listen 8000;
    server_name localhost;
    return 301 https://$host:8443$request_uri;
}

# === CONNECTION LIMITING ===
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
limit_req_zone $binary_remote_addr zone=default:10m rate=30r/s;
```

### 1.5 Test Lab 1

```bash
# Khoi dong
docker compose up -d
sleep 10  # Cho Kong khoi tao

# Test 1: Direct Kong Admin (tu container ben trong)
docker compose exec kong-proxy curl -s http://127.0.0.1:8001/status | jq .

# Test 2: Direct Kong Admin tu host = FAIL (127.0.0.1 chi trong container)
# Tu host: curl http://127.0.0.1:8001  --> Connection refused = DUNG

# Test 3: Access via Nginx Admin Proxy = OK ( voi Basic Auth + IP OK)
curl -s -k -u admin:KongAdmin2024! \
  https://127.0.0.1:8444/status | jq .

# Test 4: Access WITHOUT Basic Auth = 401 Unauthorized
curl -s -k \
  https://127.0.0.1:8444/status
# Output: < HTTP/1.1 401 Unauthorized

# Test 5: Access voi sai password = 401 Unauthorized
curl -s -k -u admin:wrongpassword \
  https://127.0.0.1:8444/status
# Output: < HTTP/1.1 401 Unauthorized

# Test 6: Access tu public IP (khong trong allowlist) = 403 Forbidden
# Gia lap bang curl voi X-Forwarded-For giả mạo
curl -s -k -u admin:KongAdmin2024! \
  --resolve "127.0.0.1:8444:127.0.0.1" \
  -H "X-Forwarded-For: 203.0.113.50" \
  https://127.0.0.1:8444/status
# Nginx log: access denied by rule
```

---

## Lab 2: Kong Vault Environment Reference

### Muc tiêu
- Inject API key bằng `{vault://env/...}` thay vi hardcode trong kong.yml
- Verify secret duoc resolved binh thuong

### 2.1 Tao kong.yml voi Vault reference

**File: `kong/kong.yml`**

```yaml
_format_version: "3.0"
_transform: true

# === CONSUMERS ===
consumers:
  - username: mobile-app
    keyauth_credentials:
      # Thay vi: key: "km_live_secret_key_abc123"
      # Dung: vault reference
      - key: "{vault://env/KONG_ENV_MOBILE_APP_KEY}"

  - username: partner-b2b
    keyauth_credentials:
      - key: "{vault://env/KONG_ENV_PARTNER_B2B_KEY}"

# === SERVICES ===
services:
  - name: echo-service
    url: http://httpbin.org/delay/0
    routes:
      - name: echo-route
        paths:
          - /echo
        strip_path: false
        plugins:
          - name: key-auth
            config:
              key_names:
                - X-API-Key
                - apikey
          - name: rate-limiting
            config:
              minute: 100
              policy: local

# === SECURITY HEADERS via Response Transformer ===
plugins:
  - name: response-transformer
    route: echo-route
    config:
      remove:
        headers:
          - X-Kong-Upstream-Latency
          - X-Kong-Proxy-Latency
          - X-Kong-Admin-Latency
          - X-Kong-Response-Latency
          - Server
          - Via
          - X-Request-Id
      add:
        headers:
          - X-Frame-Options:DENY
          - X-Content-Type-Options:nosniff
          - Strict-Transport-Security:max-age=63072000
          - X-XSS-Protection:1; mode=block
```

### 2.2 Chinh sua docker-compose.yml de truyen env variable

```yaml
services:
  kong-proxy:
    # ... cac truong khac giu nguyen ...
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_ADMIN_LISTEN: "127.0.0.1:8001,127.0.0.1:8444 ssl"
      KONG_PROXY_LISTEN: "0.0.0.0:8000,0.0.0.0:8443 ssl"
      KONG_LOG_LEVEL: "notice"
      KONG_PLUGINS: "bundled,response-transformer,key-auth,rate-limiting,acl"

      # === VAULT: Inject secret qua environment variable ===
      # Kong OSS chi ho tro vault://env/
      # Enterprise ho tro them aws/gcp/hcv
      KONG_ENV_MOBILE_APP_KEY: "km_mobile_prod_key_$(date +%s)"
      KONG_ENV_PARTNER_B2B_KEY: "km_partner_b2b_secret_$(date +%s)"
```

### 2.3 Test Lab 2

```bash
# Restart voi env variable
docker compose down
docker compose up -d
sleep 15

# Lay env key tu Kong Admin
curl -s -k -u admin:KongAdmin2024! \
  https://127.0.0.1:8444/consumers/mobile-app/key-auth | jq '.data[].key'

# Test API voi key
MOBILE_KEY=$(curl -s -k -u admin:KongAdmin2024! \
  https://127.0.0.1:8444/consumers/mobile-app/key-auth | \
  jq -r '.data[0].key')

echo "Mobile key: $MOBILE_KEY"

# Test: Access voi dung key = 200
curl -s -k \
  -H "X-API-Key: $MOBILE_KEY" \
  https://127.0.0.1:8443/echo/get | jq '.headers["X-API-Key"]'

# Test: Access voi sai key = 401
curl -s -k -w "\nHTTP: %{http_code}" \
  -H "X-API-Key: wrong_key" \
  https://127.0.0.1:8443/echo/get

# Test: Access khong co key = 401
curl -s -k -w "\nHTTP: %{http_code}" \
  https://127.0.0.1:8443/echo/get
```

---

## Lab 3: mTLS giữa Nginx Edge va Kong Proxy

### Muc tiêu
- Nginx edge require client certificate
- Kong proxy verify client certificate
- Chi client co cert signed boi internal CA duoc phep

### 3.1 Generate CA + Client Certificate

```bash
cd certs

# Buoc 1: Generate CA key + cert
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -sha256 -days 3650 \
  -key ca.key \
  -out ca.crt \
  -subj "/C=VN/ST=HCM/L=HCM/O=Internal CA/CN=Internal Root CA"

# Buoc 2: Generate client key + CSR
openssl genrsa -out client.key 2048
openssl req -new \
  -key client.key \
  -out client.csr \
  -subj "/C=VN/ST=HCM/O=Partner/CN=partner-service"

# Buoc 3: Sign client cert boi CA
openssl x509 -req -days 365 \
  -in client.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out client.crt \
  -extfile <(printf "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=clientAuth")

# Buoc 4: Tao client bundle (cert + key = PKCS12)
openssl pkcs12 -export \
  -in client.crt \
  -inkey client.key \
  -certfile ca.crt \
  -out client.p12 \
  -name "partner-service" \
  -password pass:changeit

# Buoc 5: Tao PEM cho Nginx
cat client.crt ca.crt > client-chain.pem

# Verify
openssl verify -CAfile ca.crt client.crt
# Output: client.crt: OK

# Cleanup CSR
rm client.csr
```

### 3.2 Nginx mTLS Config cho Kong Proxy

**File: `nginx/conf.d/kong-proxy-mtls.conf`** (them vao)

```nginx
# mTLS endpoint: chi cho phep client co cert signed boi internal CA
server {
    listen      8444 ssl;
    http2       on;
    server_name mtls.internal;

    ssl_certificate     /etc/nginx/ssl/kong-admin.crt;
    ssl_certificate_key /etc/nginx/ssl/kong-admin.key;

    # mTLS: yeu cau client certificate
    ssl_client_certificate /etc/nginx/ssl/ca.crt;
    ssl_verify_client on;
    ssl_verify_depth 2;
    ssl_trusted_certificate /etc/nginx/ssl/ca.crt;

    # Neu client cert valid -> set header
    # Neu khong co cert -> reject
    if ($ssl_client_verify != SUCCESS) {
        return 403 "Client certificate required";
    }

    # Inject consumer identity tu client cert CN
    set $client_cn $ssl_client_s_dn_cn;

    add_header X-Client-CN $client_cn always;
    add_header X-Client-Verify $ssl_client_verify always;

    location / {
        limit_req zone=default burst=100 nodelay;
        limit_conn conn_limit 200;

        proxy_pass         http://kong_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Client-CN $client_cn;
        proxy_set_header X-SSL-Client-Verify $ssl_client_verify;

        proxy_connect_timeout 5s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }
}
```

### 3.3 Test Lab 3

```bash
# Restart nginx
docker compose exec nginx-admin-proxy nginx -s reload

# Test 1: Request khong co client cert = 403
curl -s -k -w "\nHTTP: %{http_code}" \
  https://localhost:8444/echo/get
# Output: Client certificate required

# Test 2: Request voi client cert = 200
curl -s -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  https://localhost:8444/echo/get | jq .headers

# Test 3: View client CN header
curl -s -k \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  -I https://localhost:8444/echo/get | grep X-Client

# Test 4: Cert signed sai CA = 403
# Generate another CA + cert
openssl genrsa -out wrong-ca.key 2048
openssl req -x509 -new -nodes -days 365 \
  -key wrong-ca.key \
  -out wrong-ca.crt \
  -subj "/C=XX/O=Wrong CA/CN=Wrong"

openssl req -new -key client.key -out wrong-client.csr \
  -subj "/C=XX/O=Wrong/CN=attacker"
openssl x509 -req -days 365 -in wrong-client.csr \
  -CA wrong-ca.crt -CAkey wrong-ca.key \
  -CAcreateserial -out wrong-client.crt

# Test voi wrong cert
curl -s -k \
  --cert wrong-client.crt \
  --key client.key \
  --cacert wrong-ca.crt \
  https://localhost:8444/echo/get
# Output: 403 Client certificate required
```

---

## Lab 4: Security Header — Kong Response Transformer

### Muc tiêu
- Strip Kong internal headers
- Add security headers
- Verify bang curl

### 4.1 Test Security Headers

```bash
# Lay mot API response
RESP=$(curl -s -k -u admin:KongAdmin2024! \
  https://127.0.0.1:8444/services | -H "Accept: application/json")

# Check headers
curl -s -k -I https://127.0.0.1:8444/services \
  -u admin:KongAdmin2024! | grep -iE \
  "(strict-transport|x-frame|x-content-type|x-xss|server|x-kong)"

# EXPECTED OUTPUT:
# Strict-Transport-Security: max-age=63072000
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
# (Khong thay X-Kong-*, Server = PASS)

# Test API endpoint
curl -s -k \
  -H "X-API-Key: $MOBILE_KEY" \
  -I https://127.0.0.1:8443/echo/get | \
  grep -iE "(strict-transport|x-frame|x-kong|server)"

# EXPECTED: X-Kong-* headers bi strip, security headers co mat
```

---

## Lab 5: Log Masking — Khong log Authorization

### Muc tiêu
- Verify Authorization header khong xuat hien trong Nginx access log
- Verify API key khong bi log

### 5.1 Test Log Masking

```bash
# Gui request voi Authorization header
curl -s -k \
  -H "Authorization: Bearer THIS_SHOULD_NOT_APPEAR_IN_LOG" \
  -H "X-API-Key: secret_api_key_should_not_be_logged" \
  https://127.0.0.1:8443/echo/get > /dev/null

# Kiem tra Nginx access log
docker compose exec nginx-admin-proxy \
  grep -E "THIS_SHOULD_NOT|secret_api_key" \
  /var/log/nginx/access.log

# EXPECTED: Khong tim thay "THIS_SHOULD_NOT" hoac "secret_api_key" trong log = PASS

# Neu tim thay = FAIL, kiem tra log_format

# Hien thi log format hien tai
docker compose exec nginx-admin-proxy \
  nginx -T 2>&1 | grep -A 30 "log_format"

# Xem log entries
docker compose exec nginx-admin-proxy \
  tail -5 /var/log/nginx/access.log
```

---

## Lab 6: Slowloris Protection — slowhttptest

### Muc tiêu
- Verify limit_conn chan Slowloris attack
- Test voi slowhttptest

### 6.1 Setup Slowloris Test

```bash
# Cai dat slowhttptest
# macOS:
brew install slowhttptest
# Linux:
# apt install slowhttptest hoac pip install slowhttptest

# Khoi dong 1 Kong node
docker compose up -d kong-proxy
sleep 10

# Chay baseline (khong co attack)
slowhttptest -c 10 -B -i 10 -r 10 -t GET \
  -u https://127.0.0.1:8443/echo/get \
  -x 2 -p 2

# Expected: 200 OK, chan thanh cong
```

### 6.2 Slowloris Attack Simulation

```bash
# Attack: 100 slow connections, gui 1 byte moi 15 giay
# Nginx: client_header_timeout = 10s
# Kong: proxy_read_timeout = 30s

slowhttptest \
  -c 100 -H -i 15 -r 10 -t GET \
  -u https://127.0.0.1:8443/echo/get \
  -x 1 -p 3

# Expected: Connection bi reject sau 10s (client_header_timeout)
# Nginx error log: "[warn] a client connection timed out"

# Test 2: Kiem tra connections bi han che
# Mo 200 connections (vuot qua limit_conn = 200)
slowhttptest \
  -c 250 -H -i 20 -r 50 -t GET \
  -u https://127.0.0.1:8443/echo/get \
  -x 1 -p 3

# Expected: 503 Service Temporarily Unavailable (hoac 429)
# Nginx error log: "[warn] limiting connections"
```

---

## Lab 7: Security Scan — nikto va testssl.sh

### Muc tiêu
- Scan Kong Admin API = phat hien security misconfiguration
- Scan Kong Proxy = verify TLS hardening

### 7.1 nikto — Scan Kong Admin API

```bash
# Chi scan tu localhost (vi Admin API chi listen 127.0.0.1)
nikto -h https://127.0.0.1:8444/ \
  -ssl -id admin:KongAdmin2024! \
  -o nikto-admin-report.html \
  -Format html

# Expected findings:
# - /status: Kong status endpoint
# - /consumers: Consumer management
# - /plugins: Plugin management
# - (Neu Admin API public = CRITICAL: port scan finding)

# Co ban:
nikto -h http://127.0.0.1:8000/ -Tuning 1,2,3

# Tuning options:
#  1 = Interesting File / Found In Logs
#  2 = Misconfiguration / Default File
#  3 = Information Disclosure
```

### 7.2 testssl.sh — TLS Security Scan

```bash
# Install testssl.sh
git clone --depth 1 https://github.com/drwetter/testssl.sh.git
cd testssl.sh

# Scan Kong Proxy TLS config
./testssl.sh --fast --sneaky \
  https://127.0.0.1:8443/

# Scan chi headers
./testssl.sh --headers \
  https://127.0.0.1:8443/

# Scan chi vulnerabilities
./testssl.sh --vulnerabilities \
  https://127.0.0.1:8443/

# Expected output (neu da hardening):
# Rating: OK (or A/A+) on Mozilla TLS Guidelines
# - TLS 1.0/1.1: NOT available (OK)
# - TLS 1.2/1.3: available (OK)
# - Forward Secrecy: YES (OK)
# - HSTS: YES (OK)
# - Certificate transp. security: OK
```

### 7.3 Manual TLS Verification

```bash
# Test TLS version
openssl s_client -connect 127.0.0.1:8443 -tls1
# Expected: CONNECTED(00000003) hoac error (neu TLS 1.0 disabled)

openssl s_client -connect 127.0.0.1:8443 -tls1_2
# Expected: CONNECTED(00000003) + certificate info

openssl s_client -connect 127.0.0.1:8443 -tls1_3
# Expected: TLS 1.3 supported

# Test cipher
openssl s_client -connect 127.0.0.1:8443 \
  -cipher ECDHE-RSA-AES128-GCM-SHA256 \
  </dev/null 2>&1 | grep -E "Cipher is"

# Test OCSP stapling
openssl s_client -connect 127.0.0.1:8443 \
  -status </dev/null 2>&1 | grep "OCSP Response Status"
# Expected: OCSP Response Status: successful

# Verify HSTS header
curl -sI -k https://127.0.0.1:8443/ | \
  grep -i "strict-transport"
```

---

## Lab 8: Kong Hybrid Mode mTLS — CP-DP Setup

### Muc tiêu
- Hieu cach dat up Kong Control Plane + Data Plane
- Generate hybrid cert

### 8.1 Hybrid Mode Architecture

```mermaid
flowchart LR
    subgraph "Control Plane Node"
        CP["Kong CP\n8001: Admin API\n8005: CP-DP Admin\n(Kong DB-less)"]
    end

    subgraph "Data Plane Node 1"
        DP1["Kong DP\n8000: Proxy\n8006: DP-CP\n8005: mTLS listen"]
    end

    subgraph "Data Plane Node 2"
        DP2["Kong DP\n8000: Proxy\n8006: DP-CP\n8005: mTLS listen"]
    end

    subgraph "Ops / CI-CD"
        OPS["decK\n--control-plane-token"]
    end

    OPS -->|"deck gateway sync\nHTTPS 8001"| CP
    CP -->|"mTLS :8005"| DP1
    CP -->|"mTLS :8005"| DP2
```

### 8.2 Generate Hybrid Certificates

```bash
# Cai dat kong (CLI) de sinh cert
# Cách 1: dung kong container
docker run --rm -v $(pwd)/certs:/out \
  kong:3.7 kong hybrid gen_cert \
    --cert /out/kong-cp.crt \
    --key /out/kong-cp.key \
    --ca-cert /out/kong-ca.crt \
    --ca-key /out/kong-ca.key

# Verify
ls -la certs/
# Output: kong-cp.crt, kong-cp.key, kong-ca.crt, kong-ca.key

openssl x509 -in certs/kong-ca.crt -noout -text | grep -A3 "Subject:"
openssl x509 -in certs/kong-cp.crt -noout -dates
```

### 8.3 Hybrid Kong CP Config

**File: `kong/hybrid-cp.yml`**

```yaml
_format_version: "3.0"
_transform: true

# === Kong Control Plane mode ===
# data_plane_mode: true  (for DP nodes)
# Chi CP can kong.yml voi services/routes/plugins

consumers:
  - username: mobile-app
    keyauth_credentials:
      - key: "{vault://env/KONG_ENV_MOBILE_APP_KEY}"

services:
  - name: echo-service
    url: http://httpbin.org/delay/0
    routes:
      - name: echo-route
        paths:
          - /echo
        plugins:
          - name: key-auth
            config:
              key_names:
                - X-API-Key
          - name: rate-limiting
            config:
              minute: 100
              policy: local

plugins:
  - name: response-transformer
    config:
      add:
        headers:
          - Strict-Transport-Security:max-age=63072000
          - X-Content-Type-Options:nosniff
      remove:
        headers:
          - X-Kong-*
          - Server
```

---

## Challenge Lab: Rotate key-auth Credential bang decK + Vault

### Muc tiêu
- Su dung decK de rotate API key ma khong can restart Kong
- Key moi duoc resolve tu environment variable

### Buoc 1: Generate key moi

```bash
# Generate random key
NEW_KEY="km_rotated_$(openssl rand -hex 16)"
echo $NEW_KEY

# Export lam environment variable
export KONG_ENV_MOBILE_APP_KEY="$NEW_KEY"
echo "export KONG_ENV_MOBILE_APP_KEY=\"$NEW_KEY\"" >> ~/.bashrc
```

### Buoc 2: Sync bang decK

```bash
# Lay token tu htpasswd (hoac tao token rieng)
# DecK dung KONG_ADMIN_TOKEN hoac Basic Auth

# Sync config (se reload vault reference)
deck gateway sync \
  --kong-addr https://127.0.0.1:8444 \
  --tls-skip-verify \
  --headers "Authorization:Basic $(echo -n admin:KongAdmin2024! | base64)" \
  kong/kong.yml

# Verify key da duoc update
curl -s -k -u admin:KongAdmin2024! \
  https://127.0.0.1:8444/consumers/mobile-app/key-auth | \
  jq '.data[].key'
```

### Buoc 3: Verify key cu khong con hoat dong

```bash
# Test key cu
curl -s -k \
  -H "X-API-Key: km_mobile_prod_key_cu" \
  -w "\nHTTP: %{http_code}" \
  https://127.0.0.1:8443/echo/get
# Expected: HTTP 401 Unauthorized

# Test key moi
curl -s -k \
  -H "X-API-Key: $NEW_KEY" \
  -w "\nHTTP: %{http_code}" \
  https://127.0.0.1:8443/echo/get
# Expected: HTTP 200 OK
```

---

## Cleanup

```bash
# Dung tat ca container
docker compose down

# Xoa cert/key test
rm -f certs/*.crt certs/*.key certs/*.csr certs/*.p12 certs/*.srl \
      nginx/ssl/*.crt nginx/ssl/*.key

# Xoa htpasswd
rm -f nginx/.htpasswd_kong_admin

echo "Cleanup hoan tat"
```

---

## Common Errors va Fix

| Error | Cause | Fix |
|---|---|---|
| `SSL_do_handshake() failed` | Cert chain order sai | Kiem tra `ssl_certificate` + `ssl_trusted_certificate` |
| `client certificate verification error` | Client cert khong sign boi trusted CA | Them CA cert vao `ssl_client_certificate` |
| `vault reference not resolved` | Env var khong ton tai | Check env variable trong docker-compose |
| `401 Unauthorized` on Admin API | Basic Auth sai | Verify htpasswd file path |
| `403 Forbidden` on Admin API | IP khong trong allowlist | Them IP vao Nginx allow directive |
| `X-Kong-* headers van con` | Response transformer chua kich hoat | Check plugin config, order |
| `Slowloris attack thanh cong` | `client_header_timeout` qua cao | Giam `client_header_timeout` xuong 5-10s |
| `nikto: SSL negotiation error` | TLS version mismatch | Dung `tls1_2` hoac `tls1_3` flag |
| `testssl.sh: certificate chain order wrong` | Cert chain thieu intermediate | Noi intermediate + root vao `ssl_trusted_certificate` |
