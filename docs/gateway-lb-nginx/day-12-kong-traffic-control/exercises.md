# Day 12: Exercises — Hands-on Rate Limiting, ACL & Traffic Control

> **Yêu cầu**: Docker, Docker Compose, curl, jq, Python 3, Redis CLI (`redis-cli`), `wrk` (optional)
> **Kong version**: 3.7
> **Redis version**: 7.x
> **Thời gian ước tính**: 120-150 phút

---

## Cài đặt môi trường

### Cài redis-cli (nếu chưa có)

```bash
# macOS
brew install redis

# Ubuntu/Debian
sudo apt-get install redis-tools

# Verify
redis-cli ping
# Expected: PONG
```

---

## Exercise 1: Bootstrap Kong 3.7 DB-less + Redis + Backend Services

**Mục tiêu**: Dựng hạ tầng lab, verify Kong + Redis connectivity.

### Bước 1: Tạo cấu trúc thư mục

```bash
mkdir -p ~/kong-day12 && cd ~/kong-day12
mkdir -p mocks

cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  # ── Redis 7 — Rate Limiting backend ──
  redis:
    image: redis:7-alpine
    container_name: kong12-redis
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - lab

  # ── Kong Gateway DB-less ──
  kong:
    image: kong:3.7
    container_name: kong12-kong
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /usr/local/kong/kong.yml
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_LOG_LEVEL: info
      KONG_TRUSTED_IPS: "0.0.0.0/0,::/0"
      KONG_REAL_IP_RECURSIVE: "on"
      KONG_REAL_IP_HEADER: "X-Forwarded-For"
      KONG_PLUGINS: key-auth,rate-limiting,acl,ip-restriction,request-transformer,request-termination,request-size-limiting,prometheus
    volumes:
      - ./kong.yml:/usr/local/kong/kong.yml:ro
    ports:
      - "8000:8000"
      - "8443:8443"
      - "8001:8001"
      - "8444:8444"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - lab

  # ── Order Service (mock) ──
  order-service:
    image: mockserver/mockserver:5.15.0
    container_name: kong12-order-svc
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/order-expectation.json
    volumes:
      - ./mocks/order-expectation.json:/config/order-expectation.json:ro
    networks:
      - lab

  # ── Payment Service (mock) ──
  payment-service:
    image: mockserver/mockserver:5.15.0
    container_name: kong12-payment-svc
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/payment-expectation.json
    volumes:
      - ./mocks/payment-expectation.json:/config/payment-expectation.json:ro
    networks:
      - lab

networks:
  lab:
    driver: bridge
EOF
```

### Bước 2: Tạo mock expectation files

```bash
cat > mocks/order-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/orders" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"order\",\"status\":\"ok\",\"orders\":[]}",
    "headers": { "Content-Type": ["application/json"] }
  }
}
EOF

cat > mocks/payment-expectation.json << 'EOF'
{
  "httpRequest": { "path": "/payments" },
  "httpResponse": {
    "statusCode": 200,
    "body": "{\"service\":\"payment\",\"status\":\"ok\"}",
    "headers": { "Content-Type": ["application/json"] }
  }
}
EOF
```

### Bước 3: Tạo kong.yml tối thiểu (bootstrap)

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-service:1080/orders
    routes:
      - name: order-route
        paths: ["/v1/orders"]
        strip_path: true
        methods: ["GET", "POST"]

  - name: payment-service
    url: http://payment-service:1080/payments
    routes:
      - name: payment-route
        paths: ["/v1/payments"]
        strip_path: true
        methods: ["GET", "POST"]
EOF
```

### Bước 4: Khởi động

```bash
cd ~/kong-day12
docker compose up -d

# Chờ ready
sleep 15

# Verify Kong
curl -s http://localhost:8001/ | jq '{version: .version, mode: .configuration.database}'
# Expected: {"version": "3.7.x", "mode": "off"}

# Verify Redis
redis-cli -h localhost ping
# Expected: PONG

# Verify routing
curl -s http://localhost:8000/v1/orders
# Expected: {"service":"order","status":"ok"}

curl -s http://localhost:8000/v1/payments
# Expected: {"service":"payment","status":"ok"}
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Kong 502 | Mock service chưa ready | Tăng `sleep 15` hoặc check `docker compose ps` |
| Redis `connection refused` | Redis chưa ready | Tăng `depends_on` healthcheck |
| Kong `declarative config` fail | kong.yml syntax lỗi | `deck file lint kong.yml` |
| `real_ip` không hoạt động | `KONG_TRUSTED_IPS` chưa set | Thêm `0.0.0.0/0` vào trusted |

---

## Exercise 2: Consumer Tiers + Key Auth + Rate Limiting

**Mục tiêu**: Tạo 3 consumer tier (free/pro/enterprise), apply rate-limit riêng, verify policy `redis` hoạt động đúng.

### Bước 1: Update kong.yml với consumers và rate-limiting

```bash
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-service:1080/orders
    routes:
      - name: order-route
        paths: ["/v1/orders"]
        strip_path: true
        methods: ["GET", "POST"]
        plugins:
          - name: key-auth
            config:
              key_names: ["apikey", "X-API-Key"]
              key_in_query: true
              key_in_header: true
              anonymous: "anonymous"   # fallback consumer

          - name: rate-limiting
            config:
              minute: 1000
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: true
              hide_client_headers: false

  - name: payment-service
    url: http://payment-service:1080/payments
    routes:
      - name: payment-route
        paths: ["/v1/payments"]
        strip_path: true
        methods: ["GET", "POST"]
        plugins:
          - name: key-auth
            config:
              key_names: ["apikey", "X-API-Key"]
              key_in_query: true
              key_in_header: true
              anonymous: "anonymous"

          - name: rate-limiting
            config:
              minute: 500
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: false
              hide_client_headers: false

consumers:
  # ── Free tier (anonymous) ──
  - username: anonymous
    plugins:
      - name: rate-limiting
        config:
          minute: 100       # Free: 100 req/min
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false

  # ── Pro tier ──
  - username: pro-mobile-app
    acls:
      - group: pro
    keyauth_credentials:
      - key: "km_pro_key_2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 10000    # Pro: 10000 req/min
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false

  # ── Enterprise tier ──
  - username: enterprise-client
    acls:
      - group: enterprise
      - group: pro
    keyauth_credentials:
      - key: "km_ent_key_2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 100000   # Enterprise: 100000 req/min
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false
EOF
```

### Bước 2: Apply config

```bash
deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3
```

### Bước 3: Test — Anonymous (100 req/min quota)

```bash
echo "=== Anonymous (100 req/min) ==="
for i in $(seq 1 5); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    http://localhost:8000/v1/orders)
  REMAINING=$(curl -si http://localhost:8000/v1/orders \
    -H "apikey: invalid_key" 2>/dev/null | \
    grep -i "X-RateLimit-Remaining-Minute" | awk '{print $2}' | tr -d '\r')
  echo "Request $i: HTTP $STATUS | Remaining: $REMAINING"
done
```

### Bước 4: Test — Pro Consumer (10000 req/min quota)

```bash
echo "=== Pro Consumer (10000 req/min) ==="
for i in $(seq 1 5); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
  REMAINING=$(curl -si "http://localhost:8000/v1/orders?apikey=km_pro_key_2026" \
    2>/dev/null | grep -i "X-RateLimit-Remaining-Minute" | awk '{print $2}' | tr -d '\r')
  echo "Request $i: HTTP $STATUS | Remaining: $REMAINING"
done
```

### Bước 5: Verify Redis keys

```bash
# Xem Redis keys tạo bởi rate-limiting plugin
redis-cli KEYS "ratelimiting:*"
# Hoặc (key name có thể khác tùy Kong version)
redis-cli KEYS "*rate*"
redis-cli KEYS "*limiting*"

# Xem counter của pro consumer
redis-cli GET "$(redis-cli KEYS 'ratelimiting:*pro*' | head -1)"
```

### Bước 6: Stress test Pro consumer

```bash
echo "=== Stress Test: 20 requests rapidly ==="
for i in $(seq 1 20); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
  echo -n "$STATUS "
done
echo ""
# Expected: Tất cả 200 (pro có quota 10000 req/min >> 20 requests)
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Tất cả request 401 | Key không đúng hoặc key_names sai | Check `key_names` config và header name |
| 429 ngay ở request 1 | `anonymous` rate-limit thấp (100) | Tăng anonymous quota hoặc dùng API key |
| Redis keys không tạo | Kong không kết nối được Redis | Check `redis_host: redis` trong config |

---

## Exercise 3: ACL Plugin — Group-based Authorization

**Mục tiêu**: Configure ACL để restrict `/v1/payments` chỉ cho pro/enterprise, verify 403 khi free/anonymous.

### Bước 1: Update kong.yml thêm ACL

```bash
cat >> kong.yml << 'EOF'

plugins:
  # ── ACL: /v1/payments chỉ pro/enterprise ──
  - name: acl
    route: payment-route
    config:
      allow: [pro, enterprise]    # consumer thuộc pro HOẶC enterprise được vào
      deny: []                      # không có deny list
      hide_groups_header: false

  # ── Global: Prometheus metrics ──
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
EOF
```

### Bước 2: Sync

```bash
deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3
```

### Bước 3: Test — Pro consumer (allowed)

```bash
echo "=== Pro Consumer + ACL (should be ALLOWED) ==="
STATUS=$(curl -si "http://localhost:8000/v1/payments?apikey=km_pro_key_2026" \
  2>/dev/null | head -1)
echo "$STATUS"
# Expected: HTTP/1.1 200 OK
```

### Bước 4: Test — Anonymous (should be DENIED)

```bash
echo "=== Anonymous + ACL (should be DENIED) ==="
STATUS=$(curl -si "http://localhost:8000/v1/payments" 2>/dev/null | head -1)
BODY=$(curl -s "http://localhost:8000/v1/payments")
echo "$STATUS"
echo "Body: $BODY"
# Expected: HTTP/1.1 403 Forbidden
```

### Bước 5: Test — Enterprise consumer (allowed)

```bash
echo "=== Enterprise Consumer + ACL (should be ALLOWED) ==="
STATUS=$(curl -si "http://localhost:8000/v1/payments?apikey=km_ent_key_2026" \
  2>/dev/null | head -1)
echo "$STATUS"
# Expected: HTTP/1.1 200 OK
```

### Bước 6: Xem headers để hiểu ACL behavior

```bash
# Pro consumer — xem X-Authenticated-Groups header
curl -si "http://localhost:8000/v1/payments?apikey=km_pro_key_2026" \
  2>/dev/null | grep -i "X-Authenticated-Groups"
# Expected: X-Authenticated-Groups: pro

# Anonymous — X-Authenticated-Groups trống hoặc không có
curl -si "http://localhost:8000/v1/payments" \
  2>/dev/null | grep -i "X-Authenticated-Groups"
# Expected: X-Authenticated-Groups: (empty)
```

### Bước 7: Thử nghiệm — Anonymous bị ACL reject vì không có ACL group

```bash
# Verify consumer "anonymous" KHÔNG có ACL group
curl -s http://localhost:8001/consumers/anonymous/acls | jq '.data'
# Expected: []

# Check ACL plugin
curl -s http://localhost:8001/plugins | jq '.data[] | select(.name=="acl") | .config'
```

**Challenge**: Sửa config để anonymous vẫn được gọi `/v1/payments` nhưng rate-limit 10 req/min (không phải 100). Có 2 cách:
1. Tạo group `public`, thêm vào `allow: [pro, enterprise, public]`
2. Không enable ACL trên route mà chỉ dùng rate-limit

---

## Exercise 4: IP Restriction — Whitelist Partner B2B

**Mục tiêu**: Configure IP restriction để chỉ partner B2B IP range mới được gọi `/v1/orders` endpoint đặc biệt.

### Bước 1: Tạo thêm partner route và consumer

```bash
python3 - << 'PY'
from pathlib import Path
p = Path("kong.yml")
s = p.read_text()

partner_service = """  - name: partner-service
    url: http://order-service:1080/orders
    routes:
      - name: partner-route
        paths: ["/v1/partner"]
        strip_path: true
        methods: ["GET", "POST"]

"""
partner_consumer = """  - username: partner-b2b
    acls:
      - group: b2b
      - group: enterprise        # B2B cũng có quyền enterprise
    keyauth_credentials:
      - key: "km_b2b_key_2026"

"""
partner_plugins = """
  # ── IP Restriction: Partner B2B whitelist ──
  - name: ip-restriction
    route: partner-route
    config:
      allow:
        - 172.16.0.0/12    # Docker internal network
        - 127.0.0.1        # Localhost
      deny: []
      hide_client_header: false

  # ── ACL: Partner B2B chỉ có group b2b ──
  - name: acl
    route: partner-route
    config:
      allow: [b2b, enterprise]
      deny: []

  # ── Rate limit: Partner unlimited ──
  - name: rate-limiting
    route: partner-route
    config:
      minute: 1000000
      policy: redis
      redis_host: redis
      redis_port: 6379
      fault_tolerant: true
      hide_client_headers: false
"""

if "name: partner-route" not in s:
    s = s.replace("consumers:\n", partner_service + "consumers:\n", 1)
    s = s.replace("plugins:\n", partner_consumer + "plugins:\n", 1)
    s = s.rstrip() + "\n" + partner_plugins
    p.write_text(s)
PY
```

### Bước 2: Sync

```bash
deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3
```

### Bước 3: Test — Request từ localhost (trong whitelist)

```bash
echo "=== From localhost (172.x.x.x — whitelisted) ==="
STATUS=$(curl -si "http://localhost:8000/v1/partner?apikey=km_b2b_key_2026" \
  2>/dev/null | head -1)
echo "$STATUS"
# Expected: HTTP/1.1 200 OK
```

### Bước 4: Test — Request từ IP khác (spoofed X-Forwarded-For)

```bash
echo "=== From spoofed IP 1.2.3.4 (NOT whitelisted) ==="
STATUS=$(curl -si \
  -H "X-Forwarded-For: 1.2.3.4" \
  "http://localhost:8000/v1/partner?apikey=km_b2b_key_2026" \
  2>/dev/null | head -1)
echo "$STATUS"
# Expected: HTTP/1.1 403 Forbidden (vì Kong dùng real IP, không X-Forwarded-For spoof)
```

### Bước 5: Simulate request từ external IP (nếu có)

```bash
# Nếu máy có IP thật, test từ IP đó
EXTERNAL_IP=$(curl -s ifconfig.me)
echo "Your external IP: $EXTERNAL_IP"

# Add IP vào whitelist tạm thời trong block partner-route.
# Cách này chỉ thay đổi allow list đầu tiên có 127.0.0.1 trong file lab.
python3 - << 'PY'
import os
from pathlib import Path
p = Path("kong.yml")
s = p.read_text()
ip = os.environ["EXTERNAL_IP"]
needle = """              allow:
                - 172.16.0.0/12
                - 127.0.0.1
"""
replacement = needle + f"                - {ip}\n"
if ip not in s:
    s = s.replace(needle, replacement, 1)
    p.write_text(s)
PY

deck gateway sync kong.yml --kong-addr http://localhost:8001

# Test
curl -si "http://localhost:8000/v1/partner?apikey=km_b2b_key_2026" | head -1
```

---

## Exercise 5: request-transformer — Inject Consumer Metadata

**Mục tiêu**: Configure request-transformer để inject consumer info vào headers gửi upstream.

### Bước 1: Thêm request-transformer vào order-route

```bash
# Update kong.yml — thêm vào order-route plugins
cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-service:1080/orders
    routes:
      - name: order-route
        paths: ["/v1/orders"]
        strip_path: true
        methods: ["GET", "POST"]
        plugins:
          - name: key-auth
            config:
              key_names: ["apikey", "X-API-Key"]
              key_in_query: true
              key_in_header: true
              anonymous: "anonymous"

          - name: request-transformer
            config:
              add:
                headers:
                  - "X-Consumer-ID:$(consumer.id)"
                  - "X-Consumer-Username:$(consumer.username)"
                  - "X-Request-ID:$(request.id)"
                  - "X-Call-Source:api-gateway"

          - name: rate-limiting
            config:
              minute: 1000
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: true
              hide_client_headers: false

  - name: payment-service
    url: http://payment-service:1080/payments
    routes:
      - name: payment-route
        paths: ["/v1/payments"]
        strip_path: true
        methods: ["GET", "POST"]
        plugins:
          - name: key-auth
            config:
              key_names: ["apikey", "X-API-Key"]
              key_in_query: true
              key_in_header: true
              anonymous: "anonymous"

          - name: acl
            config:
              allow: [pro, enterprise]
              deny: []
              hide_groups_header: false

          - name: rate-limiting
            config:
              minute: 500
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: false
              hide_client_headers: false

  - name: partner-service
    url: http://order-service:1080/orders
    routes:
      - name: partner-route
        paths: ["/v1/partner"]
        strip_path: true
        methods: ["GET", "POST"]
        plugins:
          - name: key-auth
            config:
              key_names: ["apikey"]
              key_in_query: true
              key_in_header: true

          - name: ip-restriction
            config:
              allow:
                - 172.16.0.0/12
                - 127.0.0.1
              deny: []

          - name: acl
            config:
              allow: [b2b, enterprise]
              deny: []

          - name: rate-limiting
            config:
              minute: 1000000
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: true
              hide_client_headers: false

consumers:
  - username: anonymous
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false

  - username: pro-mobile-app
    acls:
      - group: pro
    keyauth_credentials:
      - key: "km_pro_key_2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 10000
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false

  - username: enterprise-client
    acls:
      - group: enterprise
      - group: pro
    keyauth_credentials:
      - key: "km_ent_key_2026"
    plugins:
      - name: rate-limiting
        config:
          minute: 100000
          policy: redis
          redis_host: redis
          redis_port: 6379
          fault_tolerant: true
          hide_client_headers: false

  - username: partner-b2b
    acls:
      - group: b2b
      - group: enterprise
    keyauth_credentials:
      - key: "km_b2b_key_2026"

plugins:
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
EOF
```

### Bước 2: Sync

```bash
deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3
```

### Bước 3: Test — Pro consumer thấy injected headers

```bash
echo "=== Pro Consumer — Injected Headers ==="
curl -si "http://localhost:8000/v1/orders?apikey=km_pro_key_2026" \
  2>/dev/null | grep -E "(X-Consumer|X-Request|X-Call)"
# Expected:
# X-Consumer-Username: pro-mobile-app
# X-Consumer-ID: <uuid>
# X-Request-ID: <uuid>
# X-Call-Source: api-gateway
```

### Bước 4: Test — Anonymous consumer

```bash
echo "=== Anonymous — Injected Headers ==="
curl -si "http://localhost:8000/v1/orders" \
  2>/dev/null | grep -E "(X-Consumer|X-Request|X-Call)"
# Expected:
# X-Consumer-Username: anonymous
# X-Consumer-ID: <uuid>
# (Consumer vẫn được inject — anonymous là consumer fallback)
```

### Bước 5: Verify upstream nhận headers

```bash
# Order mock service không echo headers, nhưng ta thấy Kong response headers
curl -si "http://localhost:8000/v1/orders?apikey=km_pro_key_2026" \
  2>/dev/null | grep -i "HTTP\|X-Consumer"
```

**Challenge nâng cao**: Thêm `X-Consumer-Groups` header. Verify nó chứa đúng groups (pro, enterprise) mà không dùng template variable — chỉ có thể bằng cách thêm consumer vào route-level plugin chứ không qua template.

---

## Exercise 6: request-termination — Maintenance Mode

**Mục tiêu**: Configure request-termination để simulate maintenance mode.

### Bước 1: Thêm maintenance-mode plugin vào `kong.yml`

```bash
# DB-less Admin API không cho POST /routes/.../plugins.
# Vì vậy thay đổi được thực hiện bằng declarative config + decK.
python3 - << 'PY'
from pathlib import Path
p = Path("kong.yml")
s = p.read_text()
needle = """          - name: request-transformer
            config:
              add:
                headers:
                  - "X-Consumer-ID:$(consumer.id)"
                  - "X-Consumer-Username:$(consumer.username)"
                  - "X-Request-ID:$(request.id)"
                  - "X-Call-Source:api-gateway"
"""
insert = needle + """
          - name: request-termination
            config:
              status_code: 503
              content_type: application/json
              body: '{"error":"maintenance","retry_after":3600}'
"""
if "name: request-termination" not in s:
    s = s.replace(needle, insert)
    p.write_text(s)
PY

deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3
```

### Bước 2: Test — Request bị terminate

```bash
echo "=== Order route — Maintenance Mode ==="
STATUS=$(curl -si "http://localhost:8000/v1/orders?apikey=km_pro_key_2026" \
  2>/dev/null | head -1)
BODY=$(curl -s "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
echo "$STATUS"
echo "Body: $BODY"
# Expected:
# HTTP/1.1 503 Service Unavailable
# {"error":"maintenance","retry_after":3600}
```

### Bước 3: Payment route vẫn hoạt động (không bị terminate)

```bash
echo "=== Payment route — Should be OK ==="
STATUS=$(curl -si "http://localhost:8000/v1/payments?apikey=km_pro_key_2026" \
  2>/dev/null | head -1)
echo "$STATUS"
# Expected: HTTP/1.1 200 OK (order-route bị terminate, payment-route không)
```

### Bước 4: Disable maintenance mode

```bash
# Xóa block request-termination khỏi kong.yml rồi sync lại.
python3 - << 'PY'
from pathlib import Path
p = Path("kong.yml")
s = p.read_text()
block = """
          - name: request-termination
            config:
              status_code: 503
              content_type: application/json
              body: '{"error":"maintenance","retry_after":3600}'
"""
p.write_text(s.replace(block, ""))
PY

deck gateway sync kong.yml --kong-addr http://localhost:8001
sleep 3

# Verify order-route hoạt động lại
curl -si "http://localhost:8000/v1/orders?apikey=km_pro_key_2026" 2>/dev/null | head -1
# Expected: HTTP/1.1 200 OK
```

---

## Exercise 7: Redis Failure — fault_tolerant Behavior

**Mục tiêu**: Test Kong behavior khi Redis down, quan sát fail-open vs fail-close.

### Bước 1: Test trước khi Redis down

```bash
echo "=== Before Redis down ==="
for i in $(seq 1 3); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
  echo "Request $i: HTTP $STATUS"
done
# Expected: 200 (với rate-limit OK)
```

### Bước 2: Stop Redis

```bash
echo "=== Stopping Redis ==="
docker compose stop redis
sleep 5

# Verify Redis down
redis-cli -h localhost ping 2>&1 || echo "Redis is down"
```

### Bước 3: Test order-route (fault_tolerant=true) — fail open

```bash
echo "=== Order route (fault_tolerant=true) — should FAIL OPEN ==="
for i in $(seq 1 3); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
  echo "Request $i: HTTP $STATUS"
done
# Expected: HTTP 200 (request được qua không rate-limit)
```

### Bước 4: Test payment-route (fault_tolerant=false) — fail close

```bash
echo "=== Payment route (fault_tolerant=false) — should FAIL CLOSE ==="
for i in $(seq 1 3); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/payments?apikey=km_pro_key_2026")
  BODY=$(curl -s "http://localhost:8000/v1/payments?apikey=km_pro_key_2026")
  echo "Request $i: HTTP $STATUS | Body: $BODY"
done
# Expected: HTTP 500 (rate-limit error)
```

### Bước 5: Restart Redis

```bash
echo "=== Restarting Redis ==="
docker compose start redis
sleep 5

redis-cli -h localhost ping
# Expected: PONG

# Verify rate-limit hoạt động lại
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
echo "After Redis restart: HTTP $STATUS"
# Expected: 200
```

### Bước 6: Quan sát Kong error log

```bash
docker compose logs kong 2>&1 | grep -i "redis\|rate-limit\|error" | tail -20
```

**Reflection questions:**
1. Tại sao order-route (Pro) dùng `fault_tolerant=true`? Phù hợp cho use case nào?
2. Tại sao payment-route dùng `fault_tolerant=false`? Production nên set gì cho payment API?
3. Nếu Redis cluster 3-node (1 master + 2 replica) bị mất master — Kong có tự reconnect không?

---

## Exercise 8 (Optional): Benchmark — local vs redis Policy

**Mục tiêu**: So sánh latency khi dùng policy `local` vs `redis`.

### Bước 1: Chuyển sang local policy tạm thời

```bash
# DB-less: đổi declarative config rồi sync, không PATCH Admin API.
cp kong.yml kong.redis.yml

python3 - << 'PY'
from pathlib import Path
p = Path("kong.yml")
s = p.read_text()
target = """          - name: rate-limiting
            config:
              minute: 1000
              policy: redis
              redis_host: redis
              redis_port: 6379
              fault_tolerant: true
              hide_client_headers: false
"""
replacement = """          - name: rate-limiting
            config:
              minute: 1000
              policy: local
              fault_tolerant: true
              hide_client_headers: false
"""
if target not in s:
    raise SystemExit("Không tìm thấy block rate-limiting của order-route")
p.write_text(s.replace(target, replacement, 1))
PY

deck gateway sync kong.yml --kong-addr http://localhost:8001

echo "Switched to local policy. Testing..."
```

### Bước 2: Benchmark local policy

```bash
# Baseline
echo "=== Benchmark: No plugin ==="
wrk -t4 -c50 -d10s http://localhost:8000/v1/orders?apikey=km_pro_key_2026 2>&1 | \
  grep -E "Requests|Latency"

# Với local policy (1 Kong node = không có distributed issue)
echo "=== Benchmark: rate-limiting local ==="
wrk -t4 -c50 -d10s http://localhost:8000/v1/orders?apikey=km_pro_key_2026 2>&1 | \
  grep -E "Requests|Latency"
```

### Bước 3: Switch sang redis policy

```bash
mv kong.redis.yml kong.yml
deck gateway sync kong.yml --kong-addr http://localhost:8001

echo "=== Benchmark: rate-limiting redis ==="
wrk -t4 -c50 -d10s http://localhost:8000/v1/orders?apikey=km_pro_key_2026 2>&1 | \
  grep -E "Requests|Latency"
```

### Bước 4: Phân tích kết quả

```
Questions:
1. p50 latency tăng bao nhiêu khi chuyển từ local → redis?
2. Throughput (RPS) giảm bao nhiêu phần trăm?
3. Có request nào bị 429 không? Tại sao / không?
```

---

## Exercise 9 (Optional): Prometheus Metrics — Rate Limit Observability

**Mục tiêu**: Query Prometheus metrics để observe rate-limit behavior.

### Bước 1: Verify Prometheus plugin

```bash
curl -s http://localhost:8001/plugins \
  | jq '.data[] | select(.name=="prometheus") | {name, enabled}'
```

### Bước 2: Query rate-limit metrics

```bash
# Prometheus metrics endpoint
curl -s http://localhost:8001/metrics | grep "^kong_" | grep -i "rate\|429" | head -20
```

### Bước 3: Simulate rate-limit exceeded

```bash
# Gửi nhiều request để trigger quota
for i in $(seq 1 200); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/v1/orders?apikey=km_pro_key_2026")
done

# Check 429 count
curl -s http://localhost:8001/metrics | grep "kong_http_status" | grep "429" | head -5
```

### Bước 4: Observe plugin latency

```bash
curl -s http://localhost:8001/metrics \
  | grep "kong_plugin_latency" | head -10
```

---

## Cleanup

```bash
# Dừng container
cd ~/kong-day12
docker compose down -v

# Xóa lab files (optional)
rm -rf ~/kong-day12
```

---

## Tổng Kết

| Exercise | Lệnh chính | Kỹ năng |
|---|---|---|
| 1 | `docker compose up -d` | Bootstrap Kong + Redis |
| 2 | Consumer + rate-limit policy | 3-tier quota với redis |
| 3 | `acl` plugin | Group-based authorization |
| 4 | `ip-restriction` | IP whitelist CIDR |
| 5 | `request-transformer` | Inject consumer metadata |
| 6 | `request-termination` | Maintenance mode short-circuit |
| 7 | Redis failure simulation | fail-open vs fail-close |
| 8 | `wrk` benchmark | local vs redis policy |
| 9 | Prometheus metrics | Rate-limit observability |
