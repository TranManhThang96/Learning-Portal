# Day 09 — Kong Core Entities: Hands-on Exercises

> **Mục tiêu**: Thực hành CRUD operations cho Service, Route, Consumer, Plugin qua Admin API và chuyển đổi sang declarative `kong.yml`
> **Yêu cầu**: Hoàn thành Exercise 1-5 trong 2 giờ. Exercise 6-7 là optional.
> **Environment**: Docker Compose với Kong 3.6 DB-mode cho Admin API CRUD. DB-less chỉ dùng ở Exercise 6 khi validate/reload declarative config.

---

## Exercise 1: CRUD Service & Route bằng Admin API

### Mục tiêu
Tạo 3 Service (order, payment, tracking) và 3 Route tương ứng bằng Admin API. Verify bằng curl.

### Setup

```bash
# 1. Tạo Docker Compose network trước
mkdir -p mocks

# 2. Tạo mock service expectations
cat > mocks/order-expectation.json << 'EOF'
[
  {
    "httpRequest": { "path": "/orders", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"order\",\"path\":\"/orders\"}", "statusCode": 200 }
  },
  {
    "httpRequest": { "path": "/orders/123", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"order\",\"orderId\":\"123\"}", "statusCode": 200 }
  },
  {
    "httpRequest": { "path": "/orders/urgent", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"order\",\"type\":\"urgent\"}", "statusCode": 200 }
  }
]
EOF

cat > mocks/payment-expectation.json << 'EOF'
[
  {
    "httpRequest": { "path": "/payments", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"payment\"}", "statusCode": 200 }
  },
  {
    "httpRequest": { "path": "/payments/abc", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"payment\",\"paymentId\":\"abc\"}", "statusCode": 200 }
  }
]
EOF

cat > mocks/tracking-expectation.json << 'EOF'
[
  {
    "httpRequest": { "path": "/tracking", "method": "GET" },
    "httpResponse": { "body": "{\"service\":\"tracking\"}", "statusCode": 200 }
  }
]
EOF
```

### Bước 1: Tạo Docker Compose

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  postgres:
    image: postgres:15-alpine
    container_name: kong-day09-postgres
    environment:
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpass
      POSTGRES_DB: kong
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kong -d kong"]
      interval: 5s
      timeout: 5s
      retries: 10

  kong:
    image: kong:3.6
    container_name: kong-day09
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_PG_DATABASE: kong
      KONG_ADMIN_LISTEN: 0.0.0.0:8001
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_LOG_LEVEL: info
      KONG_PLUGINS: key-auth,rate-limiting,jwt,acl,cors
    ports:
      - "8000:8000"
      - "8443:8443"
      - "8001:8001"
      - "8444:8444"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5

  order-svc:
    image: mockserver/mockserver:5.15.0
    container_name: order-svc
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/order-expectation.json
    volumes:
      - ./mocks/order-expectation.json:/config/order-expectation.json:ro

  payment-svc:
    image: mockserver/mockserver:5.15.0
    container_name: payment-svc
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/payment-expectation.json
    volumes:
      - ./mocks/payment-expectation.json:/config/payment-expectation.json:ro

  tracking-svc:
    image: mockserver/mockserver:5.15.0
    container_name: tracking-svc
    environment:
      MOCKSERVER_INITIALIZATION_JSON_PATH: /config/tracking-expectation.json
    volumes:
      - ./mocks/tracking-expectation.json:/config/tracking-expectation.json:ro
EOF

docker compose up -d postgres order-svc payment-svc tracking-svc
docker compose run --rm kong kong migrations bootstrap
docker compose up -d kong
sleep 10

docker compose ps
```

### Bước 2: Tạo Services

```bash
# Create order-service
ORDER_SVC=$(curl -s -X POST http://localhost:8001/services \
  -d "name=order-service" \
  -d "url=http://order-svc:1080/orders" \
  -d "connect_timeout=5000" \
  -d "read_timeout=30000" \
  -d "write_timeout=30000" \
  -d "retries=3" \
  -d "tags[]=team-orders")
echo "Order service: $(echo $ORDER_SVC | jq -r '.name') id=$(echo $ORDER_SVC | jq -r '.id')"

# Create payment-service
PAYMENT_SVC=$(curl -s -X POST http://localhost:8001/services \
  -d "name=payment-service" \
  -d "url=http://payment-svc:1080/payments" \
  -d "connect_timeout=3000" \
  -d "read_timeout=10000" \
  -d "write_timeout=10000" \
  -d "retries=2" \
  -d "tags[]=team-payment")
echo "Payment service: $(echo $PAYMENT_SVC | jq -r '.name') id=$(echo $PAYMENT_SVC | jq -r '.id')"

# Create tracking-service
TRACKING_SVC=$(curl -s -X POST http://localhost:8001/services \
  -d "name=tracking-service" \
  -d "url=http://tracking-svc:1080/tracking" \
  -d "connect_timeout=5000" \
  -d "read_timeout=15000" \
  -d "write_timeout=15000" \
  -d "retries=3" \
  -d "tags[]=team-tracking")
echo "Tracking service: $(echo $TRACKING_SVC | jq -r '.name') id=$(echo $TRACKING_SVC | jq -r '.id')"
```

### Bước 3: Tạo Routes

```bash
# Order route
curl -s -X POST http://localhost:8001/services/order-service/routes \
  -d "name=order-route" \
  -d "paths[]=/v1/orders" \
  -d "strip_path=true" \
  -d "path_handling=v0" \
  -d "protocols[]=http" \
  -d "tags[]=team-orders" | jq '{name:.name, id:.id}'

# Payment route
curl -s -X POST http://localhost:8001/services/payment-service/routes \
  -d "name=payment-route" \
  -d "paths[]=/v1/payments" \
  -d "strip_path=true" \
  -d "path_handling=v0" \
  -d "protocols[]=http" \
  -d "tags[]=team-payment" | jq '{name:.name, id:.id}'

# Tracking route
curl -s -X POST http://localhost:8001/services/tracking-service/routes \
  -d "name=tracking-route" \
  -d "paths[]=/v1/tracking" \
  -d "strip_path=true" \
  -d "path_handling=v0" \
  -d "protocols[]=http" \
  -d "tags[]=team-tracking" | jq '{name:.name, id:.id}'
```

### Bước 4: Verify

```bash
echo "=== Services ==="
curl -s http://localhost:8001/services | jq '.data[] | {name, host, port, path, read_timeout}'

echo "=== Routes ==="
curl -s http://localhost:8001/routes | jq '.data[] | {name, service: .service, paths, strip_path}'

echo "=== Routing Test ==="
curl -s http://localhost:8000/v1/orders/123
echo ""
curl -s http://localhost:8000/v1/payments/abc
echo ""
curl -s http://localhost:8000/v1/tracking
echo ""
```

### Expected Output

```
=== Routing Test ===
{"service":"order","orderId":"123"}
{"service":"payment","paymentId":"abc"}
{"service":"tracking"}
```

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `{"message":"schema violation (host: required)"}` | Dùng `paths` nhưng thiếu host trong Service | Thêm `-d "host=_"` hoặc dùng `url=` shorthand |
| `{"message":"no Service found with those values"}` | Route reference sai service name | Verify bằng `GET /services` |
| `502` | Container network sai | `docker network ls`, `docker inspect kong-day09` |
| Kong chưa ready | Health check fail | Tăng `sleep 8` → `sleep 15` |

---

## Exercise 2: Consumer + Key-Auth Credential + Route-Level Plugin

### Mục tiêu
Tạo Consumer "mobile-app" với key-auth credential, apply key-auth plugin route-level để bảo vệ `/v1/payments`.

### Bước 1: Tạo Consumers

```bash
# Anonymous consumer (for optional auth fallback)
curl -s -X POST http://localhost:8001/consumers \
  -d "username=anonymous" \
  -d "tags[]=anonymous" | jq '{username:.username, id:.id}'

# Mobile app consumer
curl -s -X POST http://localhost:8001/consumers \
  -d "username=mobile-app" \
  -d "custom_id=app-ios-2.1.0" \
  -d "tags[]=team-mobile" | jq '{username:.username, id:.id}'

# Admin team consumer
curl -s -X POST http://localhost:8001/consumers \
  -d "username=admin-team" \
  -d "tags[]=team-admin" | jq '{username:.username, id:.id}'
```

### Bước 2: Tạo Key-Auth Credential

```bash
# Tạo key-auth credential cho mobile-app
KEY_RESULT=$(curl -s -X POST http://localhost:8001/consumers/mobile-app/key-auth \
  -d "key=km_mobile_$(date +%s)")
echo "Key created: $(echo $KEY_RESULT | jq -r '.key')"
echo "Key ID: $(echo $KEY_RESULT | jq -r '.id')"
```

### Bước 3: Apply key-auth Plugin route-level

```bash
# Apply key-auth lên payment-route
curl -s -X POST http://localhost:8001/routes/payment-route/plugins \
  -d "name=key-auth" \
  -d "config.key_names=apikey,X-API-Key" \
  -d "config.key_in_query=true" \
  -d "config.key_in_header=true" \
  -d "config.anonymous=anonymous" \
  -d "config.hide_credentials=true" | jq '{name:.name, enabled:.enabled, config:.config}'
```

### Bước 4: Verify

```bash
echo "=== Test WITHOUT API key (should pass as anonymous) ==="
curl -s -w "\nHTTP: %{http_code}\n" http://localhost:8000/v1/payments/abc

echo "=== Test WITH WRONG API key (should be 401) ==="
curl -s -w "\nHTTP: %{http_code}\n" "http://localhost:8000/v1/payments/abc?apikey=wrong_key_123"

echo "=== Test WITH CORRECT API key (should pass as mobile-app) ==="
MOBILE_KEY=$(curl -s http://localhost:8001/consumers/mobile-app/key-auth | jq -r '.data[0].key')
curl -s -w "\nHTTP: %{http_code}\n" "http://localhost:8000/v1/payments/abc?apikey=${MOBILE_KEY}"
```

### Expected Output

```
=== Test WITHOUT API key (should pass as anonymous) ===
{"service":"payment","paymentId":"abc"}
HTTP: 200

=== Test WITH WRONG API key (should be 401) ===
{"message":"No API key provided"}
HTTP: 401

=== Test WITH CORRECT API key (should pass as mobile-app) ===
{"service":"payment","paymentId":"abc"}
HTTP: 200
```

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `401` khi không có key (không có anonymous) | Plugin không có `config.anonymous` | Thêm `-d "config.anonymous=anonymous"` |
| Kong không start được | Plugin `key-auth` chưa được whitelisted | Thêm `KONG_PLUGINS: key-auth,rate-limiting,...` |
| Key không được gửi đến upstream | `config.hide_credentials=true` | Đổi thành `false` để upstream nhận được `apikey` |

---

## Exercise 3: Rate-Limiting Plugin — Global vs Route vs Consumer

### Mục tiêu
Áp dụng rate-limiting ở 3 scope khác nhau, observe precedence khi consumer + route cùng match.

### Bước 1: Global rate-limiting (100 req/min)

```bash
curl -s -X POST http://localhost:8001/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=100" \
  -d "config.policy=local" \
  -d "config.fault_tolerant=true" | jq '{name:.name, enabled:.enabled, config:.config}'
```

### Bước 2: Route-level cho payment-route (500 req/min)

```bash
curl -s -X POST http://localhost:8001/routes/payment-route/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=500" \
  -d "config.policy=local" | jq '{name:.name, enabled:.enabled, config:.config}'
```

### Bước 3: Consumer-level cho mobile-app (10000 req/min)

```bash
curl -s -X POST http://localhost:8001/consumers/mobile-app/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=10000" \
  -d "config.policy=local" | jq '{name:.name, enabled:.enabled, config:.config}'
```

### Bước 4: Verify Precedence

```bash
echo "=== Plugin list on payment-route ==="
curl -s "http://localhost:8001/routes/payment-route/plugins" \
  | jq '.data[] | {name, consumer, config}'

echo "=== Plugin list on mobile-app consumer ==="
curl -s "http://localhost:8001/consumers/mobile-app/plugins" \
  | jq '.data[] | {name, consumer, config}'

echo "=== Test rate-limiting: mobile-app consumer + payment-route ==="
MOBILE_KEY=$(curl -s http://localhost:8001/consumers/mobile-app/key-auth | jq -r '.data[0].key')
for i in {1..5}; do
  curl -s -o /dev/null -w "mobile-app+payment: %{http_code}\n" \
    "http://localhost:8000/v1/payments/abc?apikey=${MOBILE_KEY}"
done

echo "=== Test rate-limiting: anonymous + payment-route (global override) ==="
for i in {1..5}; do
  curl -s -o /dev/null -w "anonymous+payment: %{http_code}\n" \
    http://localhost:8000/v1/payments/abc
done

echo "=== Test rate-limiting: order-route (global only, 100/min) ==="
for i in {1..5}; do
  curl -s -o /dev/null -w "order-route: %{http_code}\n" \
    http://localhost:8000/v1/orders/123
done
```

### Expected Behavior

| Request | Scopes Matched | Expected Config | Reason |
|---|---|---|---|
| mobile-app + payment | Consumer + Route + Service | Consumer: 10000/min | Consumer wins |
| anonymous + payment | Route + Service | Route: 500/min | Route wins |
| order-route | Global only | Global: 100/min | Global |

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| Vẫn bị 429 quá sớm | local policy không share counter giữa multiple Kong workers | Dùng `policy=redis` với shared Redis |
| Consumer rate-limit không override | Auth không resolve đúng consumer | Check `curl http://localhost:8001/routes/payment-route/plugins` có key-auth không |
| 429 sau 101 request | local policy counter reset mỗi minute | Đợi 1 phút hoặc restart Kong |

---

## Exercise 4: path_handling Lab — 4 Tổ hợp

### Mục tiêu
Tạo 4 Service/Route với 4 tổ hợp khác nhau của `service.path`, `strip_path`, `path_handling`. Quan sát upstream path thay đổi.

### Setup

```bash
# Cleanup routes trước
curl -s http://localhost:8001/services/order-service/routes \
  | jq -r '.data[].id' | while read id; do
  curl -s -X DELETE "http://localhost:8001/routes/${id}"
done
```

### Bước 1: Tạo 4 tổ hợp

```bash
# Combination 1: service.path="/svc1" strip=true path_handling=v0
curl -s -X POST http://localhost:8001/services \
  -d "name=ph-svc-1" \
  -d "url=http://order-svc:1080/svc1" | jq -r '.id'
curl -s -X POST http://localhost:8001/services/ph-svc-1/routes \
  -d "name=ph-route-1" \
  -d "paths[]=/v1/test1" \
  -d "strip_path=true" \
  -d "path_handling=v0"

# Combination 2: service.path="/svc2" strip=true path_handling=v1
curl -s -X POST http://localhost:8001/services \
  -d "name=ph-svc-2" \
  -d "url=http://order-svc:1080/svc2" | jq -r '.id'
curl -s -X POST http://localhost:8001/services/ph-svc-2/routes \
  -d "name=ph-route-2" \
  -d "paths[]=/v1/test2" \
  -d "strip_path=true" \
  -d "path_handling=v1"

# Combination 3: service.path="/svc3" strip=false path_handling=v0
curl -s -X POST http://localhost:8001/services \
  -d "name=ph-svc-3" \
  -d "url=http://order-svc:1080/svc3" | jq -r '.id'
curl -s -X POST http://localhost:8001/services/ph-svc-3/routes \
  -d "name=ph-route-3" \
  -d "paths[]=/v1/test3" \
  -d "strip_path=false" \
  -d "path_handling=v0"

# Combination 4: service.path="/svc4" strip=false path_handling=v1
curl -s -X POST http://localhost:8001/services \
  -d "name=ph-svc-4" \
  -d "url=http://order-svc:1080/svc4" | jq -r '.id'
curl -s -X POST http://localhost:8001/services/ph-svc-4/routes \
  -d "name=ph-route-4" \
  -d "paths[]=/v1/test4" \
  -d "strip_path=false" \
  -d "path_handling=v1"
```

### Bước 2: Verify upstream path (bằng mock server log)

```bash
echo "=== Combination 1: strip=true, v0 → upstream=/svc1 + /extra ==="
curl -s http://localhost:8000/v1/test1/extra

echo "=== Combination 2: strip=true, v1 → legacy prefix concat; inspect log ==="
curl -s http://localhost:8000/v1/test2/extra

echo "=== Combination 3: strip=false, v0 → upstream=/svc3 + /v1/test3/extra ==="
curl -s http://localhost:8000/v1/test3/extra

echo "=== Combination 4: strip=false, v1 → legacy prefix concat; inspect log ==="
curl -s http://localhost:8000/v1/test4/extra
```

### Bước 3: Verify Kong config

```bash
echo "=== Route configs ==="
curl -s "http://localhost:8001/routes" \
  | jq -r '.data[] | select(.name | startswith("ph-")) | {name, paths, strip_path, path_handling}'
```

### Expected Results

| Route | service.path | strip_path | path_handling | Request | Kỳ vọng chính |
|---|---|---|---|---|---|
| ph-route-1 | `/svc1` | true | v0 | `/v1/test1/extra` | Path được join theo segment: `/svc1/extra` |
| ph-route-2 | `/svc2` | true | v1 | `/v1/test2/extra` | Legacy prefix concat, có thể gây path bất ngờ |
| ph-route-3 | `/svc3` | false | v0 | `/v1/test3/extra` | Path được join theo segment: `/svc3/v1/test3/extra` |
| ph-route-4 | `/svc4` | false | v1 | `/v1/test4/extra` | Legacy prefix concat, có thể gây path bất ngờ |

`path_handling=v0` là lựa chọn khuyến nghị cho route mới. `v1` không được Expressions router hỗ trợ và có thể bị loại bỏ ở phiên bản tương lai, nên bài lab chỉ dùng để nhận diện legacy behavior.

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| 404 upstream | Upstream path không match mock expectation | Kiểm tra mock server log: `docker logs order-svc 2>&1 | grep svc` |
| Cả 4 đều 200 nhưng path khác nhau | Bình thường | Kiểm tra mock log để xác nhận upstream path |

---

## Exercise 5: preserve_host — Host Header Inspection

### Mục tiêu
Thử nghiệm `preserve_host=true` vs `false`, inspect Host header upstream nhận được.

### Bước 1: Tạo mock service nhận headers

```bash
# Cập nhật mock để echo headers
cat > mocks/order-expectation.json << 'EOF'
[
  {
    "httpRequest": {"path": "/orders", "method": "GET"},
    "httpResponse": {
      "body": "{\"service\":\"order\"}",
      "statusCode": 200,
      "headers": {"X-Upstream-Host": ["$(requestedHost)"]}
    }
  },
  {
    "httpRequest": {"path": "/headers", "method": "GET"},
    "httpResponse": {
      "statusCode": 200,
      "headers": {
        "X-Forwarded-Host": ["#ifeq(#regexp('Host: (.*)\\r?\\n', request.rawbody), '', 'unknown', #regexp('Host: (.*)\\r?\\n', request.rawbody))"]
      }
    }
  }
]
EOF

docker compose restart order-svc
sleep 3
```

### Bước 2: Test preserve_host=false (default)

```bash
# Lấy route id của order-route
ROUTE_ID=$(curl -s http://localhost:8001/routes/order-route | jq -r '.id')

# PATCH preserve_host=false
curl -s -X PATCH "http://localhost:8001/routes/order-route" \
  -d "preserve_host=false" | jq '{name:.name, preserve_host:.preserve_host}'

echo "=== Test with preserve_host=false ==="
echo "Client sends: Host: api.example.com"
curl -s -H "Host: api.example.com" \
  http://localhost:8000/v1/orders/123

echo ""
echo "Upstream receives Host: order-svc:1080 (default)"
```

### Bước 3: Test preserve_host=true

```bash
curl -s -X PATCH "http://localhost:8001/routes/order-route" \
  -d "preserve_host=true" | jq '{name:.name, preserve_host:.preserve_host}'

echo "=== Test with preserve_host=true ==="
echo "Client sends: Host: api.example.com"
curl -s -H "Host: api.example.com" \
  http://localhost:8000/v1/orders/456

echo ""
echo "Upstream receives Host: api.example.com"
```

### Expected Behavior

| preserve_host | Client Host | Upstream Host |
|---|---|---|
| `false` | `api.example.com` | `order-svc:1080` (service host) |
| `true` | `api.example.com` | `api.example.com` (original) |

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| Upstream không phân biệt được tenant | preserve_host=false + multi-tenant | Set `preserve_host=true` hoặc dùng header `X-Forwarded-Host` |
| Certificate SNI mismatch | preserve_host=true + HTTPS nhưng cert không match host | Dùng SNI entity để map cert theo host |

---

## Exercise 6 (Optional): Convert toàn bộ config sang kong.yml declarative

### Mục tiêu
Export hoặc viết lại các entity đã tạo ở Exercise 1-5 sang `kong.yml`. Stack hiện tại đang chạy **DB-mode**, nên không dùng `POST /config` để reload. `POST /config` chỉ dành cho DB-less mode.

### Bước 1: Dump current config từ DB-mode

```bash
# Cách 1: inspect bằng Admin API
curl -s http://localhost:8001/services > /tmp/kong-services.json
curl -s http://localhost:8001/routes > /tmp/kong-routes.json
curl -s http://localhost:8001/consumers > /tmp/kong-consumers.json
curl -s http://localhost:8001/plugins > /tmp/kong-plugins.json

jq '.data | length' /tmp/kong-services.json /tmp/kong-routes.json /tmp/kong-consumers.json /tmp/kong-plugins.json

# Cách 2 nếu có decK:
# deck gateway dump --kong-addr http://localhost:8001 -o kong-dump.yaml
```

### Bước 2: Convert manually — viết kong.yml hoàn chỉnh

```bash
cat > kong.yml << 'KONGEOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-svc:1080/orders
    connect_timeout: 5000
    read_timeout: 30000
    write_timeout: 30000
    retries: 3
    tags: ["team-orders"]
    routes:
      - name: order-route
        paths: ["/v1/orders"]
        strip_path: true
        path_handling: v0
        protocols: ["http"]
        tags: ["team-orders"]
    plugins:
      - name: rate-limiting
        config:
          minute: 500
          policy: local
          fault_tolerant: true

  - name: payment-service
    url: http://payment-svc:1080/payments
    connect_timeout: 3000
    read_timeout: 10000
    write_timeout: 10000
    retries: 2
    tags: ["team-payment"]
    routes:
      - name: payment-route
        paths: ["/v1/payments"]
        strip_path: true
        path_handling: v0
        protocols: ["http"]
        tags: ["team-payment"]
    plugins:
      - name: key-auth
        config:
          key_names: ["apikey", "X-API-Key"]
          key_in_query: true
          key_in_header: true
          anonymous: anonymous
          hide_credentials: true
      - name: rate-limiting
        config:
          minute: 500
          policy: local

  - name: tracking-service
    url: http://tracking-svc:1080/tracking
    connect_timeout: 5000
    read_timeout: 15000
    write_timeout: 15000
    retries: 3
    tags: ["team-tracking"]
    routes:
      - name: tracking-route
        paths: ["/v1/tracking"]
        strip_path: true
        path_handling: v0
        protocols: ["http"]
        tags: ["team-tracking"]
    plugins:
      - name: rate-limiting
        config:
          minute: 200
          policy: local

consumers:
  - username: anonymous
    tags: ["anonymous"]
    plugins: []

  - username: mobile-app
    custom_id: app-ios-2.1.0
    tags: ["team-mobile"]
    keyauth_credentials:
      - key: km_mobile_app_key
    plugins:
      - name: rate-limiting
        config:
          minute: 10000
          policy: local

  - username: admin-team
    tags: ["team-admin"]
    plugins: []

plugins:
  - name: rate-limiting
    config:
      minute: 100
      policy: local
      fault_tolerant: true
KONGEOF

echo "kong.yml created:"
wc -l kong.yml
```

### Bước 3: Validate kong.yml

```bash
# Validate declarative config bằng Kong parser
docker run --rm \
  -v $(pwd):/work \
  -w /work \
  kong:3.6 \
  kong config parse kong.yml

# Expected: parse successful
```

### Bước 4: So sánh declarative file với state đang chạy

```bash
echo "=== Services ==="
curl -s http://localhost:8001/services | jq '.data[] | .name'

echo "=== Routes ==="
curl -s http://localhost:8001/routes | jq '.data[] | .name'

echo "=== Consumers ==="
curl -s http://localhost:8001/consumers | jq '.data[] | .username'

echo "=== Plugins ==="
curl -s http://localhost:8001/plugins | jq '.data[] | {name, enabled, route, service, consumer}'
```

### Bước 5: Full end-to-end test trên DB-mode hiện tại

```bash
echo "=== Auth Test ==="
curl -s -w "anonymous(no key): %{http_code}\n" http://localhost:8000/v1/payments/abc
curl -s -w "wrong key: %{http_code}\n" "http://localhost:8000/v1/payments/abc?apikey=wrong"
curl -s -w "correct key: %{http_code}\n" "http://localhost:8000/v1/payments/abc?apikey=km_mobile_app_key"

echo ""
echo "=== Rate-limit inspect headers ==="
curl -sI "http://localhost:8000/v1/orders/123?apikey=km_mobile_app_key" \
  | grep -i "ratelimit\|x-rate"
```

### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `{"message":"declarative config is invalid"}` | YAML syntax error | Chạy `yamllint kong.yml` hoặc `python3 -c "import yaml; yaml.safe_load(open('kong.yml'))"` |
| `POST /config` trả lỗi hoặc không tồn tại | Stack đang chạy DB-mode | Chỉ dùng `POST /config` trong DB-less, hoặc chuyển sang decK ở Day 10 |
| Plugin không load | Plugin chưa trong `KONG_PLUGINS` | Update docker-compose env `KONG_PLUGINS: key-auth,rate-limiting,...` |
| Consumer credential không được tạo | Nested credential cần `_transform: true` | Verify `kong.yml` có `_transform: true` |

---

## Exercise 7 (Optional): Migrate sang Expressions Router

### Mục tiêu
Chuyển từ Traditional Router sang Expressions Router, viết lại routes bằng DSL.

### Bước 1: Bật Expressions Router

```bash
# Stop current
docker compose stop kong

# Cập nhật docker-compose.yml để bật expressions trong DB-mode hiện tại
sed -i '/KONG_DATABASE: postgres/a\      KONG_ROUTER_FLAVOR: "expressions"' docker-compose.yml

# Restart
docker compose up -d
sleep 10
```

### Bước 2: Verify router flavor

```bash
curl -s http://localhost:8001/ | jq '.router_flavor'
# Expected: "expressions"
```

### Bước 3: Tạo route với Expressions DSL

```bash
# Xóa route cũ trước
curl -s http://localhost:8001/routes \
  | jq -r '.data[].id' | while read id; do
  curl -s -X DELETE "http://localhost:8001/routes/${id}"
done

# Tạo expressions-based routes
curl -s -X POST http://localhost:8001/services/order-service/routes \
  -d "name=order-expr" \
  -d 'expression=(http.path ^= "/v1/orders") && (http.method in ["GET", "POST"])' \
  -d "strip_path=true"

curl -s -X POST http://localhost:8001/services/payment-service/routes \
  -d "name=payment-expr" \
  -d 'expression=(http.path ^= "/v1/payments")' \
  -d "strip_path=true"

curl -s -X POST http://localhost:8001/services/tracking-service/routes \
  -d "name=tracking-expr" \
  -d 'expression=(http.path ^= "/v1/tracking")' \
  -d "strip_path=true"
```

### Bước 4: Test

```bash
echo "=== Expressions Router Test ==="
curl -s http://localhost:8000/v1/orders/123
echo ""
curl -s -X POST http://localhost:8000/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"customer":"C123"}'
echo ""
curl -s http://localhost:8000/v1/payments/abc
echo ""
curl -s http://localhost:8000/v1/tracking
```

### Bước 5: Convert kong.yml sang Expressions DSL

```bash
cat > kong-expressions.yml << 'KONGEOF'
_format_version: "3.0"
_transform: true

services:
  - name: order-service
    url: http://order-svc:1080/orders
    routes:
      - name: order-expr
        expression: (http.path ^= "/v1/orders") && (http.method in ["GET", "POST"])
        strip_path: true
    plugins:
      - name: rate-limiting
        config:
          minute: 500
          policy: local

  - name: payment-service
    url: http://payment-svc:1080/payments
    routes:
      - name: payment-expr
        expression: http.path ^= "/v1/payments"
        strip_path: true
    plugins:
      - name: key-auth
        config:
          key_names: ["apikey"]
          anonymous: anonymous

  - name: tracking-service
    url: http://tracking-svc:1080/tracking
    routes:
      - name: tracking-expr
        expression: http.path ^= "/v1/tracking"
        strip_path: true

consumers:
  - username: mobile-app
    keyauth_credentials:
      - key: km_mobile_app_key

plugins:
  - name: rate-limiting
    config:
      minute: 100
      policy: local
KONGEOF

docker run --rm \
  -v $(pwd):/work \
  -w /work \
  kong:3.6 \
  kong config parse kong-expressions.yml

# Nếu muốn apply file này, chạy một stack DB-less riêng hoặc dùng decK ở Day 10.
# Không POST /config vào stack DB-mode hiện tại.
```

### Expected Output

```
=== Expressions Router Test ===
{"service":"order","orderId":"123"}
{"service":"order","path":"/orders","method":"POST"}
{"service":"payment","paymentId":"abc"}
{"service":"tracking"}
```

---

## Cleanup

```bash
# Dừng và xóa container
docker compose down

# Xóa mock files
rm -f mocks/*.json

# Reset kong.yml
cat > kong.yml << 'EOF'
_format_version: "3.0"
EOF
```
