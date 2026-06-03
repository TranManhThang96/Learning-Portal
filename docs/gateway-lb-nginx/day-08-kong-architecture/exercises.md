# Exercises Day 08: Kong Architecture & OpenResty Foundation

> **Thời lượng ước tính**: 120 phút
> **Yêu cầu**: Docker Desktop đang chạy, port 8000/8001/8100 chưa bị chiếm
> **Timebox**: Exercise 1-4 là phần bắt buộc trong 2 giờ. Exercise 5-6 là optional nếu còn thời gian.

---

## Exercise 1: Dựng Kong DB-less bằng Docker Compose

**Mục tiêu**: Khởi động Kong DB-less, verify Admin API và proxy hoạt động.

### Bước 1.1 — Tạo cấu trúc thư mục

```bash
mkdir -p ~/kong-day08/config
cd ~/kong-day08
```

### Bước 1.2 — Tạo `config/kong.yml`

```yaml
_format_version: "3.0"
_transform: true

services:
  - name: httpbin-service
    url: http://httpbin:80
    connect_timeout: 5000
    write_timeout: 60000
    read_timeout: 60000
    tags:
      - day08
      - lab
    routes:
      - name: httpbin-route
        paths:
          - /httpbin
        strip_path: true
        methods:
          - GET
          - POST
          - PUT
          - DELETE

  - name: echo-service
    url: http://echo:8080
    tags:
      - day08
      - lab
    routes:
      - name: echo-route
        paths:
          - /echo
        strip_path: true

plugins:
  - name: correlation-id
    config:
      header_name: X-Request-ID
      generator: uuid#counter
      echo_downstream: true
```

### Bước 1.3 — Tạo `docker-compose.yml`

```yaml
version: "3.8"

services:
  kong:
    image: kong:3.6
    container_name: kong-day08
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /usr/local/kong/declarative/kong.yml
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
      KONG_LOG_LEVEL: info
    volumes:
      - ./config:/usr/local/kong/declarative
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8100:8100"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 10s
      retries: 10
    networks:
      - kong-net

  httpbin:
    image: kennethreitz/httpbin:latest
    container_name: httpbin-day08
    networks:
      - kong-net

  echo:
    image: ealen/echo-server:latest
    container_name: echo-day08
    environment:
      PORT: 8080
    networks:
      - kong-net

networks:
  kong-net:
    driver: bridge
```

### Bước 1.4 — Validate config trước khi start

```bash
# Validate kong.yml syntax
docker run --rm   -v $(pwd)/config:/config   kong:3.6   kong config parse /config/kong.yml

# Expected output:
# parse successful
```

### Bước 1.5 — Khởi động

```bash
docker compose up -d

# Chờ Kong healthy (khoảng 15-30 giây)
docker compose ps

# Expected:
# NAME          IMAGE     STATUS              PORTS
# kong-day08    kong:3.6  Up (healthy)        0.0.0.0:8000->8000/tcp, ...
# httpbin-day08 ...       Up
# echo-day08    ...       Up
```

### Bước 1.6 — Verify

```bash
# Kong version
curl -s http://localhost:8001 | grep -o '"version":"[^"]*"'
# Expected: "version":"3.6.x"

# Status API
curl -s http://localhost:8100/status
# Expected: {"message":"Kong is healthy"}

# Test proxy httpbin
curl -s http://localhost:8000/httpbin/get | python3 -m json.tool
# Hoặc nếu không có python3:
curl -s http://localhost:8000/httpbin/get

# Expected: JSON với url, headers, origin

# Test proxy echo
curl -s http://localhost:8000/echo
# Expected: JSON với request info

# Verify X-Request-ID header
curl -I http://localhost:8000/httpbin/get 2>&1 | grep -i x-request-id
# Expected: X-Request-ID: <uuid>#1
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `kong exited with code 1` | kong.yml syntax sai | Chạy validate ở bước 1.4 |
| `502 Bad Gateway` | httpbin chưa ready | Chờ thêm 10s, kiểm tra `docker compose ps` |
| `curl: (7) Failed to connect` | Port chưa mở | Kiểm tra `docker compose ps` và port mapping |
| `{"message":"Not found"}` | Path sai | Đảm bảo dùng `/httpbin/get` không phải `/get` |

---

## Exercise 2: Khám phá Admin API

**Mục tiêu**: Làm quen với các endpoint Admin API quan trọng.

### Bước 2.1 — Node information

```bash
# Thông tin node
curl -s http://localhost:8001 | grep -E '"version"|"hostname"|"node_id"'

# Status chi tiết
curl -s http://localhost:8001/status
# Chú ý: database.reachable = true (dù DB-less, Kong vẫn báo reachable)

# Memory usage
curl -s http://localhost:8001/status | grep -A5 '"memory"'
```

### Bước 2.2 — List entities

```bash
# List services
curl -s http://localhost:8001/services
# Expected: data array với 2 services

# List routes
curl -s http://localhost:8001/routes
# Expected: data array với 2 routes

# List plugins
curl -s http://localhost:8001/plugins
# Expected: data array với 1 plugin (correlation-id)

# List upstreams (rỗng vì dùng URL trực tiếp)
curl -s http://localhost:8001/upstreams
# Expected: {"data":[],"next":null}
```

### Bước 2.3 — Chi tiết một entity

```bash
# Chi tiết service
curl -s http://localhost:8001/services/httpbin-service
# Expected: full service object với id, name, url, timeouts, ...

# Routes của một service
curl -s http://localhost:8001/services/httpbin-service/routes
# Expected: data array với httpbin-route

# Plugins của một service
curl -s http://localhost:8001/services/httpbin-service/plugins
# Expected: data array (rỗng vì correlation-id là global plugin)
```

### Bước 2.4 — Plugin information

```bash
# List tất cả plugin đã enabled (built-in)
curl -s http://localhost:8001/plugins/enabled
# Expected: {"enabled_plugins": [...]} — danh sách dài

# Đếm số plugin available
curl -s http://localhost:8001/plugins/enabled | grep -o '"[a-z-]*"' | wc -l

# Schema của một plugin
curl -s http://localhost:8001/schemas/plugins/rate-limiting
# Expected: JSON schema với tất cả config options
```

### Bước 2.5 — Config dump (DB-less)

```bash
# Dump toàn bộ config đang chạy
curl -s http://localhost:8001/config
# Expected: YAML/JSON với tất cả entities

# Chú ý: endpoint này chỉ có trong DB-less mode
# Trong DB-mode, endpoint này không tồn tại
```

**Câu hỏi tự kiểm tra:**
1. Tại sao `/upstreams` trả về rỗng dù có 2 services?
2. Sự khác biệt giữa `/status` (port 8001) và `/status` (port 8100) là gì?
3. Tại sao `/config` endpoint chỉ có trong DB-less mode?

---

## Exercise 3: DB-less Admin API read-only và quản lý bằng kong.yml

**Mục tiêu**: Hiểu đúng giới hạn của DB-less mode: Admin API dùng để đọc/inspect config, còn thay đổi entity phải đi qua declarative config (`kong.yml`) hoặc `POST /config`.

### Bước 3.1 — Chứng minh Admin API CRUD bị chặn trong DB-less

```bash
# Thử tạo service mới qua Admin API
curl -s -i -X POST http://localhost:8001/services \
  -H "Content-Type: application/json" \
  -d '{
    "name": "jsonplaceholder-service",
    "url": "https://jsonplaceholder.typicode.com",
    "connect_timeout": 5000,
    "read_timeout": 30000,
    "write_timeout": 30000,
    "tags": ["day08", "exercise3"]
  }'

# Expected:
# HTTP/1.1 405 Not Allowed
# {"message":"method not allowed"}
```

**Bài học quan trọng**: Trong DB-less mode, các endpoint CRUD như `POST /services`, `PATCH /routes`, `DELETE /plugins` là read-only. Ngoại lệ chính là `POST /config`, dùng để replace toàn bộ declarative config đang chạy.

### Bước 3.2 — Thêm service vào kong.yml

Mở `config/kong.yml` và thêm service sau vào danh sách `services`:

```yaml
  - name: jsonplaceholder-service
    url: https://jsonplaceholder.typicode.com
    connect_timeout: 5000
    read_timeout: 30000
    write_timeout: 30000
    tags:
      - day08
      - exercise3
    routes:
      - name: jsonplaceholder-route
        paths:
          - /todos
        strip_path: false
        methods:
          - GET
```

### Bước 3.3 — Validate và hot reload declarative config

```bash
# Validate trước khi apply
docker run --rm \
  -v $(pwd)/config:/config \
  kong:3.6 \
  kong config parse /config/kong.yml

# Expected: parse successful

# Replace toàn bộ config DB-less đang chạy
curl -s -X POST http://localhost:8001/config \
  -F "config=@./config/kong.yml"

# Expected: {"message":"declarative config loaded successfully"}
```

### Bước 3.4 — Verify route mới

```bash
curl -s http://localhost:8001/services/jsonplaceholder-service
# Expected: service object

curl -s http://localhost:8001/routes/jsonplaceholder-route
# Expected: route object

curl -s http://localhost:8000/todos/1
# Expected: {"userId":1,"id":1,"title":"...","completed":false}

# Verify X-Request-ID header vẫn có từ global plugin
curl -I http://localhost:8000/todos/1 2>&1 | grep -i x-request-id
```

### Bước 3.5 — Quan sát tính immutable

```bash
# Restart Kong
docker compose restart kong
sleep 15

# Route vẫn tồn tại vì đã nằm trong kong.yml, không phải state tạo tạm qua Admin API
curl -s http://localhost:8000/todos/1
# Expected: JSON từ jsonplaceholder
```

---

## Exercise 4: Bật Prometheus Plugin và xem Metrics

**Mục tiêu**: Bật Prometheus plugin, generate traffic, và đọc metrics.

### Bước 4.1 — Thêm Prometheus plugin vào kong.yml

```yaml
plugins:
  - name: correlation-id
    config:
      header_name: X-Request-ID
      generator: uuid#counter
      echo_downstream: true

  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
      upstream_health_metrics: true
```

### Bước 4.2 — Reload config

```bash
curl -s -X POST http://localhost:8001/config   -F "config=@./config/kong.yml"
# Expected: {"message":"declarative config loaded successfully"}
```

### Bước 4.3 — Generate traffic

```bash
# Gửi một số request để có data
for i in $(seq 1 20); do
  curl -s http://localhost:8000/httpbin/get > /dev/null
  curl -s http://localhost:8000/echo > /dev/null
done
echo "Done generating traffic"
```

### Bước 4.4 — Xem metrics

```bash
# Metrics endpoint (qua Admin API)
curl -s http://localhost:8001/metrics

# Lọc các metric quan trọng
curl -s http://localhost:8001/metrics | grep -E "^kong_http_requests_total|^kong_latency"

# Expected output (ví dụ):
# kong_http_requests_total{service="httpbin-service",route="httpbin-route",code="200",...} 20
# kong_latency_bucket{type="kong",service="httpbin-service",...,le="1"} 0
# kong_latency_bucket{type="kong",service="httpbin-service",...,le="5"} 15
```

### Bước 4.5 — Hiểu các metric quan trọng

```bash
# Total requests per service/route/status code
curl -s http://localhost:8001/metrics | grep "kong_http_requests_total"

# Latency histogram (Kong processing time)
curl -s http://localhost:8001/metrics | grep "kong_latency.*type="kong""

# Latency histogram (upstream response time)
curl -s http://localhost:8001/metrics | grep "kong_latency.*type="upstream""

# Bandwidth
curl -s http://localhost:8001/metrics | grep "kong_bandwidth"

# Upstream health
curl -s http://localhost:8001/metrics | grep "kong_upstream_target_health"
```

**Lưu ý**: Trong Kong 3.x, Prometheus metrics có thể được expose qua:
- `http://localhost:8001/metrics` (Admin API — chỉ dùng nội bộ)
- Hoặc cấu hình `status_listen` với dedicated port

---

## Exercise 5: Quan sát Plugin Lifecycle bằng pre-function Plugin

**Mục tiêu**: Dùng pre-function plugin để inject custom Lua code vào access phase, log request info.

### Bước 5.1 — Thêm pre-function plugin vào kong.yml

```yaml
plugins:
  - name: correlation-id
    config:
      header_name: X-Request-ID
      generator: uuid#counter
      echo_downstream: true

  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
      upstream_health_metrics: true

  - name: pre-function
    config:
      access:
        - |
          -- Custom Lua code chạy trong access phase
          local request_id = kong.request.get_header("X-Request-ID")
          local method = kong.request.get_method()
          local path = kong.request.get_path()
          local host = kong.request.get_host()

          kong.log.notice(string.format(
            "[pre-function] method=%s path=%s host=%s request_id=%s",
            method, path, host, request_id or "none"
          ))

          -- Thêm custom header vào request gửi lên upstream
          kong.service.request.set_header("X-Kong-Phase", "access")
          kong.service.request.set_header("X-Kong-Node", kong.node.get_id())
```

### Bước 5.2 — Reload và test

```bash
# Reload config
curl -s -X POST http://localhost:8001/config   -F "config=@./config/kong.yml"

# Gửi request
curl -s http://localhost:8000/httpbin/get

# Xem log Kong (tìm dòng [pre-function])
docker compose logs kong 2>&1 | grep "pre-function"

# Expected:
# kong-day08  | ... [notice] ... [pre-function] method=GET path=/get host=localhost request_id=...
```

### Bước 5.3 — Verify custom headers được gửi lên upstream

```bash
# httpbin /get trả về tất cả headers nhận được
curl -s http://localhost:8000/httpbin/get | grep -A5 '"headers"'

# Expected: thấy X-Kong-Phase và X-Kong-Node trong headers
# "X-Kong-Phase": "access",
# "X-Kong-Node": "<uuid>",
```

### Bước 5.4 — Thêm log phase hook

Cập nhật pre-function plugin trong kong.yml:

```yaml
  - name: pre-function
    config:
      access:
        - |
          local request_id = kong.request.get_header("X-Request-ID")
          local method = kong.request.get_method()
          local path = kong.request.get_path()
          kong.log.notice(string.format(
            "[pre-function:access] method=%s path=%s request_id=%s",
            method, path, request_id or "none"
          ))
          kong.service.request.set_header("X-Kong-Phase", "access")
      log:
        - |
          local status = kong.response.get_status()
          local latency = kong.ctx.shared.KONG_PROXY_LATENCY or 0
          kong.log.notice(string.format(
            "[pre-function:log] status=%d latency=%dms",
            status, latency
          ))
```

```bash
# Reload và test
curl -s -X POST http://localhost:8001/config -F "config=@./config/kong.yml"
curl -s http://localhost:8000/httpbin/get > /dev/null

# Xem log
docker compose logs kong 2>&1 | grep "pre-function"
# Expected: thấy cả access và log phase messages
```

---

## Exercise 6: Convert sang DB-mode với PostgreSQL

**Mục tiêu**: Cảm nhận sự khác biệt giữa DB-less và DB-mode.

### Bước 6.1 — Tạo `docker-compose-dbmode.yml`

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    container_name: kong-postgres
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpassword
    volumes:
      - kong-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kong"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - kong-dbmode-net

  kong-migrations:
    image: kong:3.6
    container_name: kong-migrations
    command: kong migrations bootstrap
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpassword
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - kong-dbmode-net
    restart: on-failure

  kong-dbmode:
    image: kong:3.6
    container_name: kong-dbmode
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpassword
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
      KONG_LOG_LEVEL: info
    ports:
      - "8010:8000"
      - "8011:8001"
      - "8110:8100"
    depends_on:
      postgres:
        condition: service_healthy
      kong-migrations:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 10s
      retries: 10
    networks:
      - kong-dbmode-net

  httpbin-dbmode:
    image: kennethreitz/httpbin:latest
    container_name: httpbin-dbmode
    networks:
      - kong-dbmode-net

volumes:
  kong-postgres-data:

networks:
  kong-dbmode-net:
    driver: bridge
```

### Bước 6.2 — Khởi động DB-mode

```bash
docker compose -f docker-compose-dbmode.yml up -d

# Chờ migrations xong và Kong healthy
docker compose -f docker-compose-dbmode.yml ps

# Expected:
# kong-postgres    Up (healthy)
# kong-migrations  Exited (0)   <- migrations thành công
# kong-dbmode      Up (healthy)
# httpbin-dbmode   Up
```

### Bước 6.3 — Tạo Service và Route qua Admin API (DB-mode)

```bash
# Tạo service (port 8011 = Admin API của DB-mode instance)
curl -s -X POST http://localhost:8011/services   -H "Content-Type: application/json"   -d '{
    "name": "httpbin-service",
    "url": "http://httpbin-dbmode:80"
  }'

# Tạo route
curl -s -X POST http://localhost:8011/services/httpbin-service/routes   -H "Content-Type: application/json"   -d '{
    "name": "httpbin-route",
    "paths": ["/httpbin"],
    "strip_path": true
  }'

# Test proxy (port 8010 = proxy của DB-mode instance)
curl -s http://localhost:8010/httpbin/get
# Expected: JSON từ httpbin
```

### Bước 6.4 — Verify config persist sau restart

```bash
# Restart Kong DB-mode
docker compose -f docker-compose-dbmode.yml restart kong-dbmode

# Chờ healthy
sleep 20

# Test lại — config vẫn còn vì được lưu trong PostgreSQL
curl -s http://localhost:8010/httpbin/get
# Expected: JSON từ httpbin (KHÔNG bị mất như DB-less)
```

### Bước 6.5 — So sánh DB-less vs DB-mode

```bash
# DB-less: /config endpoint có
curl -s http://localhost:8001/config | head -5
# Expected: YAML config

# DB-mode: /config endpoint không có
curl -s http://localhost:8011/config
# Expected: {"message":"declarative configuration is not available"}

# DB-less: POST /services bị chặn vì Admin API read-only
curl -s -X POST http://localhost:8001/services   -H "Content-Type: application/json"   -d '{"name":"test","url":"http://test:80"}'
# Expected: HTTP 405 / {"message":"method not allowed"}

# DB-mode: POST /services hoạt động bình thường
curl -s -X POST http://localhost:8011/services   -H "Content-Type: application/json"   -d '{"name":"test-service","url":"http://test:80"}'
# Expected: service object với id
```

### Bước 6.6 — Cleanup

```bash
# Dừng DB-mode stack
docker compose -f docker-compose-dbmode.yml down -v

# Dừng DB-less stack (nếu muốn)
docker compose down
```

---

## Tổng kết Exercises

Sau khi hoàn thành 6 exercises, bạn đã:

1. **Exercise 1**: Dựng Kong DB-less từ đầu, hiểu cấu trúc `kong.yml` với `_format_version: "3.0"`
2. **Exercise 2**: Làm quen với Admin API — list entities, xem schema, dump config
3. **Exercise 3**: Hiểu sự khác biệt giữa DB-less read-only Admin API và declarative config (`kong.yml` / `POST /config`)
4. **Exercise 4**: Bật Prometheus plugin, đọc metrics, hiểu các metric quan trọng
5. **Exercise 5**: Inject custom Lua code vào access và log phase bằng pre-function plugin
6. **Exercise 6**: Dựng DB-mode với PostgreSQL, verify config persist sau restart

**Câu hỏi ôn tập:**
- Tại sao `_format_version: "3.0"` quan trọng và không thể dùng `"2.1"` cho Kong 3.x?
- Khi nào nên dùng `POST /config` thay vì restart Kong?
- Tại sao pre-function plugin có priority 1000000 (cao nhất)?
- Sự khác biệt giữa `kong.log.notice` và `ngx.log` là gì?
- Trong DB-mode, Kong sync config mới từ PostgreSQL sau bao lâu?
