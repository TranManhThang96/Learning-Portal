# Day 08: Kong Architecture & OpenResty Foundation

> **Thời lượng**: 2 giờ
> **Độ khó**: ⭐⭐⭐
> **Prerequisites**: Day 1-7 (đặc biệt Day 2 — Nginx master/worker, Day 6 — rate limiting, Day 7 — benchmark methodology)

---

## 1. Learning Objectives

Sau bài này, bạn sẽ có thể:

- Giải thích Kong được xây dựng trên OpenResty (Nginx + LuaJIT) và tại sao kiến trúc đó cho phép hot-reload plugin
- Phân biệt 3 deployment mode của Kong: Traditional (DB-mode), DB-less, Hybrid — và chọn đúng theo use case
- Dựng Kong DB-less bằng Docker Compose với declarative config `kong.yml`
- Trace request flow qua các phase của Kong: certificate → rewrite → access → balancer → header_filter → body_filter → log
- Troubleshoot các lỗi phổ biến khi khởi động Kong và khi proxy request

---

## 2. The Problem

> Bạn đang vận hành 20 microservices. Mỗi service cần: rate limiting, API key authentication, CORS, request logging, và metrics. Hiện tại bạn đang dùng Nginx thuần — mỗi lần thêm service mới phải sửa `nginx.conf`, reload, và viết lại logic auth bằng `auth_request` directive. Khi team muốn thêm JWT validation cho 5 service, bạn phải viết Lua script thủ công hoặc dùng module C bên thứ ba.

**Pain points thực tế:**

- Nginx config là file tĩnh — mỗi thay đổi cần reload (graceful nhưng vẫn có overhead)
- Không có Admin API — không thể thêm route mới mà không chạm vào file config
- Auth logic phải tự implement hoặc dùng `auth_request` sub-request tốn thêm latency
- Rate limiting trong Nginx OSS là per-instance, không shared giữa nhiều node
- Không có consumer model — không thể track "user A đã dùng bao nhiêu quota"
- Observability phải tự build: log format, metrics endpoint, tracing header

**Hậu quả nếu thiết kế sai:**

- Config drift giữa các môi trường (dev/staging/prod) vì không có single source of truth
- Security gap: một service quên bật auth vì không có enforcement layer
- Không audit trail: ai thêm route nào, lúc nào, với config gì
- Scale out Nginx node → rate limit counter không đồng bộ → bypass dễ dàng

**Câu hỏi cốt lõi**: Khi nào nên nâng cấp từ Nginx thuần lên API Gateway như Kong?

---

## 3. Core Concepts

### 3.1 OpenResty — Nền tảng của Kong

**Analogy**: Nginx là một chiếc xe tải chắc chắn. OpenResty là chiếc xe tải đó nhưng được gắn thêm một bộ lập trình PLC (Programmable Logic Controller) — bạn có thể viết logic tùy ý vào từng giai đoạn vận chuyển mà không cần thay động cơ.

OpenResty = Nginx core + LuaJIT + `ngx_http_lua_module` + nhiều thư viện `lua-resty-*`

```
+------------------------------------------------------------------+
|                        OpenResty Stack                           |
+------------------------------------------------------------------+
|                                                                  |
|  +------------------------------------------------------------+  |
|  |                    Kong Application                        |  |
|  |  (Lua code: router, plugin runner, Admin API, ...)         |  |
|  +------------------------------------------------------------+  |
|                            |                                     |
|  +------------------------------------------------------------+  |
|  |                    OpenResty Layer                         |  |
|  |  ngx_http_lua_module  |  lua-resty-core                    |  |
|  |  lua-resty-redis      |  lua-resty-http                    |  |
|  |  lua-resty-dns        |  lua-resty-lrucache                |  |
|  +------------------------------------------------------------+  |
|                            |                                     |
|  +------------------------------------------------------------+  |
|  |                    LuaJIT Runtime                          |  |
|  |  JIT compiler  |  FFI (call C libs from Lua)               |  |
|  +------------------------------------------------------------+  |
|                            |                                     |
|  +------------------------------------------------------------+  |
|  |                    Nginx Core                              |  |
|  |  Event loop  |  Worker processes  |  Connection mgmt       |  |
|  +------------------------------------------------------------+  |
|                                                                  |
+------------------------------------------------------------------+
```

**LuaJIT vs Lua thường:**

| Aspect | Lua 5.x | LuaJIT |
|---|---|---|
| Execution | Interpreter | JIT compile → native code |
| Performance | ~10-50x chậm hơn C | ~1.5-3x chậm hơn C |
| FFI | Không có | Có — gọi C function trực tiếp |
| Memory | Standard GC | Giới hạn 2GB (32-bit pointer) |
| Compatibility | Lua 5.x | Lua 5.1 + extensions |

LuaJIT cho phép Kong chạy plugin logic với overhead rất thấp — đây là lý do Kong có thể xử lý hàng chục nghìn RPS mà vẫn maintain plugin ecosystem phong phú.

### 3.2 Nginx Request Lifecycle Phases

Nginx xử lý mỗi HTTP request qua một chuỗi phase cố định. OpenResty cho phép inject Lua code vào từng phase:

```
+-------------------------------------------------------------------+
|                  Nginx Request Lifecycle                           |
+-------------------------------------------------------------------+
|                                                                    |
|  [Connection Accept]                                               |
|         |                                                          |
|  [SSL/TLS Handshake] <-- ssl_certificate_by_lua                   |
|         |                                                          |
|  [rewrite phase]     <-- rewrite_by_lua_block                     |
|         |              (URL rewrite, redirect)                     |
|  [access phase]      <-- access_by_lua_block                      |
|         |              (auth, rate limit, IP check)                |
|  [content phase]     <-- content_by_lua_block                     |
|         |              (generate response hoac proxy)              |
|  [header_filter]     <-- header_filter_by_lua_block               |
|         |              (modify response headers)                   |
|  [body_filter]       <-- body_filter_by_lua_block                 |
|         |              (modify response body)                      |
|  [log phase]         <-- log_by_lua_block                         |
|                         (async logging, metrics)                   |
|                                                                    |
+-------------------------------------------------------------------+
```

Ngoài ra còn có các hook đặc biệt:
- `init_by_lua_block` — chạy một lần khi master process khởi động (load config, warm cache)
- `init_worker_by_lua_block` — chạy một lần khi mỗi worker process khởi động (timer, background job)
- `balancer_by_lua_block` — chọn upstream target (custom load balancing logic)

### 3.3 Kong là gì?

Kong là một **application Lua** chạy trên OpenResty. Khi Kong start, nó:

1. Load `nginx.conf` được generate tự động từ Kong config
2. Khởi tạo Lua state trong `init_by_lua` (load plugin code, connect DB)
3. Mỗi request đến, Kong's Lua code chạy trong các phase tương ứng
4. Plugin system hook vào các phase này theo priority order

### 3.4 Kong Core Entities

Trước khi hiểu request flow, cần nắm 5 entity cốt lõi:

| Entity | Mô tả | Ví dụ |
|---|---|---|
| **Service** | Đại diện cho một upstream service | `user-service` → `http://users:8080` |
| **Route** | Rule để match request vào Service | `GET /api/users/*` |
| **Consumer** | Đại diện cho một client/user | `mobile-app`, `partner-api` |
| **Plugin** | Middleware gắn vào Service/Route/Consumer | `key-auth`, `rate-limiting` |
| **Upstream** | Pool các Target (load balancing) | `users-upstream` → 3 instances |

### 3.5 Kong Request Flow

```
Client
  |
  | HTTP :8000 / HTTPS :8443
  v
[certificate phase]
  ssl_certificate_by_lua -- SNI-based cert selection, mTLS verify
  |
[rewrite phase]
  rewrite_by_lua -- pre-function plugin, URL manipulation
  |
[access phase]  <-- PHASE QUAN TRONG NHAT
  access_by_lua -- Router match --> Plugin execution:
    1. correlation-id (them request ID)
    2. key-auth / jwt / oauth2 (authentication)
    3. acl (authorization)
    4. rate-limiting (quota check)
    5. ip-restriction
    6. request-transformer
  |
[balancer phase]
  balancer_by_lua -- chon Target tu Upstream (round-robin, etc.)
  |
  v
[Upstream Service]
  |
[header_filter phase]
  header_filter_by_lua -- response-transformer, CORS headers
  |
[body_filter phase]
  body_filter_by_lua -- response body modification (neu can)
  |
[log phase]
  log_by_lua -- file-log, http-log, prometheus metrics update
  |
  v
Client
```

### 3.6 Kong Deployment Modes

**Mode 1: Traditional (DB-mode)**

Tất cả Kong node kết nối vào một PostgreSQL database. Config được lưu trong DB. Khi thêm Service/Route qua Admin API, Kong ghi vào DB và broadcast cho các node khác qua polling.

**Mode 2: DB-less (Declarative)**

Không cần database. Config được khai báo trong file YAML (`kong.yml`). Mỗi node load file này khi khởi động. Thay đổi config cần restart hoặc POST lên `/config` endpoint.

**Mode 3: Hybrid**

Control Plane (CP) có DB và expose Admin API. Data Plane (DP) không có DB, pull config từ CP qua mTLS connection. DP chỉ proxy traffic, không expose Admin API.

### 3.7 Kong Ports

| Port | Protocol | Mục đích |
|---|---|---|
| **8000** | HTTP | Proxy — nhận traffic từ client |
| **8443** | HTTPS | Proxy — TLS |
| **8001** | HTTP | Admin API — quản lý config |
| **8444** | HTTPS | Admin API — TLS |
| **8100** | HTTP | Status API (Kong 3.x) — health check |
| **8005** | TCP | Cluster port — CP-DP communication (Hybrid mode) |
| **8006** | TCP | Cluster telemetry (Hybrid mode, Kong 3.x) |


---

## 4. How It Works Internally

### 4.1 Plugin Lifecycle — Hooks và Priority

Mỗi Kong plugin là một Lua module implement các handler function. Kong gọi các handler này tại đúng phase tương ứng trong Nginx lifecycle.

**Plugin handler interface:**

```lua
-- Cấu trúc cơ bản của một Kong plugin
local MyPlugin = {}

MyPlugin.PRIORITY = 1000  -- số càng lớn chạy càng sớm
MyPlugin.VERSION = "1.0.0"

function MyPlugin:init_worker()
  -- Chạy khi worker process khởi động
  -- Dùng để setup timer, background jobs
end

function MyPlugin:certificate(conf)
  -- Phase: TLS handshake
  -- Dùng để dynamic cert selection
end

function MyPlugin:rewrite(conf)
  -- Phase: rewrite
  -- Chạy trước khi Router match
end

function MyPlugin:access(conf)
  -- Phase: access (phổ biến nhất)
  -- Auth, rate limit, IP check
  -- Có thể terminate request sớm: kong.response.exit(401, {...})
end

function MyPlugin:header_filter(conf)
  -- Phase: header_filter
  -- Modify response headers
end

function MyPlugin:body_filter(conf)
  -- Phase: body_filter
  -- Modify response body (ngx.arg[1] = body chunk)
end

function MyPlugin:log(conf)
  -- Phase: log (non-blocking)
  -- Ghi log, update metrics
  -- KHÔNG được terminate request ở đây
end

return MyPlugin
```

**Plugin Priority — thứ tự thực thi:**

Trong cùng một phase, các plugin chạy theo thứ tự priority giảm dần (số lớn chạy trước):

| Plugin | Priority | Phase chính |
|---|---:|---|
| pre-function | 1000000 | rewrite, access |
| correlation-id | 100001 | access |
| jwt | 1005 | access |
| key-auth | 1003 | access |
| oauth2 | 1004 | access |
| acl | 950 | access |
| rate-limiting | 910 | access |
| ip-restriction | 990 | access |
| request-transformer | 801 | access |
| cors | 2000 | access |
| response-transformer | 800 | header_filter |
| prometheus | 13 | log |
| file-log | 9 | log |
| http-log | 12 | log |
| post-function | -1000 | access, log |

**Plugin Scope — thứ tự override:**

```
Global Plugin
  └── Service Plugin (override global)
        └── Route Plugin (override service)
              └── Consumer Plugin (override route)
```

Ví dụ: rate-limiting global = 100 req/min, nhưng route `/premium` có rate-limiting = 1000 req/min → consumer `vip-user` trên route đó có rate-limiting = 10000 req/min.

### 4.2 Shared Dict — State giữa các Worker

Nginx worker processes không share memory mặc định. OpenResty cung cấp `lua_shared_dict` — một vùng nhớ shared giữa tất cả worker trong cùng một node:

```nginx
# Trong nginx.conf được Kong generate
lua_shared_dict kong                5m;
lua_shared_dict kong_db_cache       128m;
lua_shared_dict kong_db_cache_miss  12m;
lua_shared_dict kong_locks          8m;
lua_shared_dict kong_process_events 5m;
lua_shared_dict kong_cluster_events 5m;
lua_shared_dict kong_rate_limiting_counters 12m;
```

Rate limiting plugin dùng `kong_rate_limiting_counters` để đếm request count per consumer per window. Đây là per-node counter — nếu có nhiều Kong node, cần Redis để sync counter giữa các node.

### 4.3 Coroutine và Cosocket — Non-blocking I/O từ Lua

Lua trong OpenResty chạy trong Nginx event loop. Để không block event loop khi gọi external service (Redis, DB, HTTP), OpenResty dùng cosocket — một abstraction cho phép Lua code yield khi chờ I/O:

```lua
-- Ví dụ: gọi Redis từ Lua plugin (non-blocking)
local redis = require "resty.redis"
local red = redis:new()
red:set_timeouts(1000, 1000, 1000)  -- connect, send, read timeout (ms)

local ok, err = red:connect("127.0.0.1", 6379)
if not ok then
  kong.log.err("Redis connect failed: ", err)
  return kong.response.exit(500)
end

local count, err = red:incr("rate_limit:" .. consumer_id)
-- Lua coroutine yield ở đây, Nginx event loop tiếp tục xử lý request khác
-- Khi Redis trả về, coroutine resume
```

Đây là lý do Kong có thể xử lý nhiều concurrent request mà không cần nhiều thread — mỗi request là một Lua coroutine, yield khi chờ I/O.

### 4.4 Admin API — Quản lý Config

Kong expose REST API tại port 8001. Mọi thay đổi config (thêm Service, Route, Plugin) đều qua Admin API:

```
POST /services          → tạo Service
POST /services/{id}/routes → tạo Route cho Service
POST /plugins           → tạo Plugin (global)
POST /services/{id}/plugins → tạo Plugin cho Service
GET  /status            → node status
GET  /config            → dump toàn bộ config (DB-less)
POST /config            → reload config (DB-less)
```

Trong DB-mode, Admin API ghi vào PostgreSQL. Các Kong node khác poll DB định kỳ (mặc định 5 giây) để sync config mới.

### 4.5 Kong vs Nginx — So sánh chi tiết

| Aspect | Nginx | Kong |
|---|---|---|
| Config | `nginx.conf` (file tĩnh) | Admin API / decK / declarative YAML |
| Plugin | Custom module (C, compile lại) | Lua plugin, hot-reload |
| Auth | Basic auth, `auth_request` | Built-in: key-auth, jwt, oauth2, ldap, mTLS |
| Rate limit | `limit_req` per-instance | Plugin (Redis-backed, cluster shared) |
| Routing | `location` regex | Service/Route entity, expressions router |
| Discovery | `upstream` block tĩnh | Upstream entity, DNS, Consul integration |
| Observability | `stub_status`, log format | Prometheus plugin, OTel plugin, Vitals |
| Consumer model | Không có | Consumer entity + credential |
| Config reload | `nginx -s reload` (graceful) | Admin API (zero downtime) |
| Multi-node sync | Không có | DB polling hoặc CP-DP push |
| RBAC | Không có | Enterprise feature |

---

## 5. Hands-on Lab

### Lab Setup — Kong DB-less với Docker Compose

Tạo thư mục làm việc:

```bash
mkdir -p ~/kong-lab/config
cd ~/kong-lab
```

**Bước 1: Tạo file `config/kong.yml`**

```yaml
_format_version: "3.0"
_transform: true

services:
  - name: httpbin-service
    url: http://httpbin:80
    connect_timeout: 5000
    write_timeout: 60000
    read_timeout: 60000
    routes:
      - name: httpbin-route
        paths:
          - /httpbin
        strip_path: true
        methods:
          - GET
          - POST

  - name: echo-service
    url: http://echo:8080
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

**Bước 2: Tạo file `docker-compose.yml`**

```yaml
version: "3.8"

services:
  kong:
    image: kong:3.6
    container_name: kong-dbless
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
    container_name: httpbin
    networks:
      - kong-net

  echo:
    image: ealen/echo-server:latest
    container_name: echo
    environment:
      PORT: 8080
    networks:
      - kong-net

networks:
  kong-net:
    driver: bridge
```

**Bước 3: Khởi động**

```bash
docker compose up -d

# Chờ Kong healthy
docker compose ps
# Expected: kong-dbless   Up (healthy)

# Xem log
docker compose logs -f kong
```

**Bước 4: Verify Admin API**

```bash
# Admin API alive
curl -s http://localhost:8001 | jq '.version'
# Expected: "3.6.x"

# Node status
curl -s http://localhost:8001/status | jq '{database: .database, memory: .memory}'
# Expected: {"database": {"reachable": true}, "memory": {...}}

# Status API (port 8100)
curl -s http://localhost:8100/status
# Expected: {"message":"Kong is healthy"}

# List services
curl -s http://localhost:8001/services | jq '.data[].name'
# Expected: "httpbin-service", "echo-service"

# List routes
curl -s http://localhost:8001/routes | jq '.data[] | {name: .name, paths: .paths}'

# List plugins enabled
curl -s http://localhost:8001/plugins/enabled | jq '.enabled_plugins | length'
```

**Bước 5: Test proxy**

```bash
# Test httpbin route
curl -s http://localhost:8000/httpbin/get | jq '{url: .url, headers: .headers}'
# Expected: url chứa /get, headers có X-Request-ID từ correlation-id plugin

# Test echo route
curl -s http://localhost:8000/echo
# Expected: JSON với request info

# Verify X-Request-ID header
curl -v http://localhost:8000/httpbin/get 2>&1 | grep -i x-request-id
# Expected: X-Request-ID: <uuid>#1
```

**Bước 6: Inspect config**

```bash
# Dump toàn bộ config đang chạy
curl -s http://localhost:8001/config | jq 'keys'
# Expected: ["_format_version", "_transform", "plugins", "routes", "services"]

# Xem chi tiết một service
curl -s http://localhost:8001/services/httpbin-service | jq '{name, url, connect_timeout}'
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `kong exited with code 1` | `kong.yml` syntax sai | Chạy `docker run --rm -v ./config:/config kong:3.6 kong config parse /config/kong.yml` |
| `502 Bad Gateway` | Backend container chưa ready | Kiểm tra `docker compose ps`, thêm `depends_on` |
| `Admin API không phản hồi` | `KONG_ADMIN_LISTEN` sai | Đảm bảo bind `0.0.0.0:8001` không phải `127.0.0.1:8001` |
| `declarative config is invalid` | `_format_version` sai | Dùng `"3.0"` cho Kong 3.x |


---

## 6. Trade-offs Analysis

### 6.1 Nginx vs Kong — Khi nào dùng cái nào?

| Aspect | Nginx thuần | Kong |
|---|---|---|
| **Performance** | Rất cao với proxy/static workload đơn giản | Cao, nhưng phụ thuộc số plugin, router rules, DB/cache lookup |
| **Complexity** | Thấp-Trung bình | Cao |
| **Plugin ecosystem** | Hạn chế (module C) | Phong phú (Lua, hot-reload) |
| **Config management** | File tĩnh, reload | Admin API, decK, declarative |
| **Auth** | Tự implement | Built-in: 10+ auth plugin |
| **Rate limiting** | Per-instance | Cluster-wide (Redis) |
| **Consumer model** | Không có | Có |
| **Observability** | Tự build | Prometheus, OTel built-in |
| **Learning curve** | Thấp | Cao |
| **Operational cost** | Thấp | Trung bình-Cao |
| **Khi nào dùng** | Static site, simple proxy, CDN edge | API Gateway, microservices, multi-tenant |

**Khi nào KHÔNG nên dùng Kong:**
- Chỉ cần reverse proxy đơn giản → Nginx thuần đủ
- Latency budget cực kỳ chặt (< 1ms overhead) → Nginx hoặc Envoy
- Team nhỏ, không có người vận hành Kong → overhead không xứng đáng
- Không cần auth/rate-limit/plugin → Kong là overkill

### 6.2 DB-less vs DB-mode vs Hybrid

| Aspect | DB-less | DB-mode | Hybrid |
|---|---|---|---|
| **Database** | Không cần | PostgreSQL | CP có DB, DP không |
| **Config update** | Restart hoặc POST /config | Admin API realtime | Admin API trên CP |
| **Multi-node sync** | Không tự động | DB polling (5s) | CP push xuống DP |
| **HA** | Mỗi node độc lập | DB là SPOF nếu không HA | CP là SPOF nếu không HA |
| **Phù hợp** | Dev, staging, immutable infra | Production đơn giản | Production scale lớn |
| **Admin API** | Chỉ read (GET) | Full CRUD | Chỉ trên CP |
| **Complexity** | Thấp | Trung bình | Cao |

**Hidden costs:**
- DB-mode: cần HA PostgreSQL (Patroni, RDS Multi-AZ) → tăng chi phí infra
- Hybrid: cần maintain CP cluster riêng, mTLS cert rotation
- DB-less: config drift nếu nhiều node dùng file khác nhau → cần GitOps pipeline

### 6.3 Kong vs Các API Gateway khác

| Gateway | Language | Model | Strength | Weakness |
|---|---|---|---|---|
| **Kong OSS** | Lua/OpenResty | Plugin-based | Ecosystem phong phú, mature | Enterprise features bị lock |
| **Kong Enterprise** | Lua/OpenResty | Plugin-based | RBAC, Dev Portal, Analytics | Chi phí cao |
| **APISIX** | Lua/OpenResty | Plugin-based | Performance cao hơn Kong, etcd | Ecosystem nhỏ hơn |
| **Traefik** | Go | Middleware | Kubernetes-native, auto-discovery | Plugin ecosystem hạn chế |
| **Envoy** | C++ | Filter chain | Performance cực cao, xCP | Cấu hình phức tạp (YAML dài) |
| **Istio** | Go + Envoy | Service mesh | mTLS, traffic policy | Overhead lớn, phức tạp |
| **Tyk** | Go | Plugin-based | Open source full-featured | Community nhỏ hơn |

**Anti-patterns:**
- Dùng Istio chỉ để làm API Gateway → overkill, overhead không cần thiết
- Enable mọi plugin global → mọi request đều chạy qua tất cả plugin → latency tăng
- Expose Admin API (port 8001) ra Internet → security risk nghiêm trọng
- Dùng DB-less cho production với nhiều node mà không có GitOps → config drift

---

## 7. Best Practices & Best Solution

### 7.1 Production Best Practices

**Security:**
- Bind Admin API vào `127.0.0.1:8001` hoặc internal network, KHÔNG expose ra Internet
- Dùng HTTPS cho Admin API (`KONG_ADMIN_SSL_CERT`, `KONG_ADMIN_SSL_CERT_KEY`)
- Trong Hybrid mode, dùng mTLS cho CP-DP communication
- Rotate Admin API credentials định kỳ

**Config Management:**
- Dùng decK (declarative Kong) để version control config trong Git
- CI/CD pipeline: `deck diff` → review → `deck sync`
- Validate config trước khi apply: `kong config parse kong.yml`
- Tag resources để dễ quản lý: `tags: [production, v2]`

**Deployment:**
- Dev/Staging: DB-less (đơn giản, reproducible)
- Production nhỏ: DB-mode với HA PostgreSQL
- Production lớn: Hybrid mode (CP cluster + DP auto-scale)

**Observability:**
- Bật Prometheus plugin global (nhưng chú ý overhead với high-cardinality labels)
- Structured log format: `KONG_PROXY_ACCESS_LOG` với custom format
- Health check: `/status` (port 8001) và `/status/ready` (port 8100)

**Performance:**
- Tắt plugin không dùng — mỗi plugin thêm latency dù nhỏ
- Rate limiting với Redis: đặt Redis timeout thấp (< 100ms) để tránh cascade failure
- Connection pooling: `KONG_UPSTREAM_KEEPALIVE_POOL_SIZE` (default 512)

### 7.2 Recommended Solution theo Use Case

**Use case: Public API cho mobile app**
```
Internet → Cloud LB → Kong (key-auth + rate-limiting + cors) → Internal Services
```
- Kong xử lý auth, rate limit, CORS
- Cloud LB xử lý TLS termination và HA
- Internal services không expose trực tiếp

**Use case: Internal microservices**
```
Service A → Kong (jwt + acl) → Service B
```
- Kong làm internal API Gateway
- JWT để service-to-service auth
- ACL để enforce service boundary

**Use case: Partner API**
```
Partner → Kong (oauth2 + rate-limiting + request-transformer) → Backend
```
- OAuth2 cho partner authentication
- Rate limiting per-partner (consumer-level)
- Request transformer để normalize partner request format

---

## 8. Performance Considerations

### 8.1 Kong Overhead

Kong thêm latency so với Nginx thuần do:
1. Lua code execution trong mỗi phase
2. Plugin chain execution
3. Router matching (regex hoặc expressions)
4. DB/cache lookup (DB-mode)

Không nên nhớ một con số overhead cố định cho Kong. Cùng một Kong version nhưng khác TLS, payload, số route, số plugin, Redis latency hoặc log level sẽ cho kết quả khác nhau. Với bài này, mục tiêu là đo **delta** giữa direct backend và proxy qua Kong trong cùng môi trường.

### 8.2 Benchmark Methodology

Mẫu benchmark report tối thiểu:

```text
Environment:
  Kong: 3.6 container
  CPU/RAM: 4 vCPU, 8GB RAM
  Network: Docker bridge trên cùng host
  Backend: httpbin container

Test Parameters:
  Tool: wrk 4.2.0
  Threads: 4
  Connections: 200
  Duration: 60s (+10s warmup)
  Payload: GET /httpbin/get, response ~1KB JSON
  TLS: Off
  Keepalive: On
  Plugins:
    Run A: none
    Run B: correlation-id
    Run C: key-auth + correlation-id

Metrics:
  RPS, p50, p95, p99, max latency, error rate
```

```bash
# Benchmark Kong không plugin
wrk -t4 -c200 -d60s --latency http://localhost:8000/httpbin/get

# Benchmark với key-auth plugin
wrk -t4 -c200 -d60s --latency   -H "apikey: your-api-key"   http://localhost:8000/httpbin/get

# So sánh với direct backend (không qua Kong)
wrk -t4 -c200 -d60s --latency http://localhost:80/get
```

Sample result nên trình bày theo dạng tương đối:

| Scenario | p50 | p95 | p99 | Error rate | Nhận xét |
|---|---:|---:|---:|---:|---|
| Direct backend | baseline | baseline | baseline | 0% | Không qua Kong |
| Kong no plugin | +delta | +delta | +delta | 0% | Router + proxy overhead |
| Kong + correlation-id | +delta | +delta | +delta | 0% | Plugin nhẹ |
| Kong + key-auth | +delta | +delta | +delta | 0% | Thêm credential/cache lookup |

> Chỉ so sánh các lần chạy cùng hardware, cùng payload, cùng concurrency, cùng TLS/keepalive setting. Không lấy số từ laptop để capacity plan production.

### 8.3 Tuning Parameters

```bash
# Worker processes (default: auto = số CPU)
KONG_NGINX_WORKER_PROCESSES=auto

# Upstream keepalive pool
KONG_UPSTREAM_KEEPALIVE_POOL_SIZE=512
KONG_UPSTREAM_KEEPALIVE_MAX_REQUESTS=1000
KONG_UPSTREAM_KEEPALIVE_IDLE_TIMEOUT=60

# DB cache TTL (DB-mode)
KONG_DB_CACHE_TTL=3600
KONG_DB_CACHE_NEG_TTL=300

# LuaJIT memory
KONG_MEM_CACHE_SIZE=128m

# Log level (production: warn hoặc error)
KONG_LOG_LEVEL=warn
```

### 8.4 Bottleneck Detection

```bash
# Xem Kong worker CPU usage
docker stats kong-dbless

# Xem Nginx worker status (nếu stub_status bật)
curl http://localhost:8001/nginx_status

# Xem shared dict usage
curl -s http://localhost:8001/status | jq '.memory.lua_shared_dicts'

# Xem upstream health
curl -s http://localhost:8001/upstreams/{upstream-name}/health
```

---

## 9. Troubleshooting Checklist

**Kong không start:**
- [ ] Validate config: `docker run --rm -v ./config:/config kong:3.6 kong config parse /config/kong.yml`
- [ ] Kiểm tra `_format_version: "3.0"` (không phải `"2.1"` hay `"1.1"`)
- [ ] Kiểm tra YAML indentation (dùng spaces, không dùng tabs)
- [ ] Xem log: `docker compose logs kong`

**Admin API không phản hồi:**
- [ ] Kiểm tra `KONG_ADMIN_LISTEN=0.0.0.0:8001` (không phải `127.0.0.1` khi chạy trong Docker)
- [ ] Kiểm tra port mapping trong docker-compose.yml
- [ ] Thử từ trong container: `docker exec kong-dbless curl localhost:8001`

**Proxy trả về 502:**
- [ ] Backend container có đang chạy không: `docker compose ps`
- [ ] Kong có resolve được hostname backend không: `docker exec kong-dbless nslookup httpbin`
- [ ] Kiểm tra Service URL trong config: `curl http://localhost:8001/services`
- [ ] Xem error log: `docker compose logs kong 2>&1 | grep error`

**Plugin không chạy:**
- [ ] Kiểm tra plugin scope: global, service, route, hay consumer?
- [ ] Kiểm tra plugin enabled: `curl http://localhost:8001/plugins`
- [ ] Kiểm tra plugin priority — plugin có bị override bởi plugin khác không?
- [ ] Xem Lua error: `docker compose logs kong 2>&1 | grep lua`

**Rate limiting không hoạt động đúng:**
- [ ] Nếu dùng Redis: kiểm tra Redis connection trong plugin config
- [ ] Nếu dùng local: nhớ rằng counter là per-node, không shared giữa nhiều Kong instance
- [ ] Kiểm tra consumer được identify đúng chưa (key-auth trước rate-limiting)

**Memory leak:**
- [ ] Kiểm tra shared dict size: `curl http://localhost:8001/status | jq '.memory'`
- [ ] Xem plugin nào dùng nhiều memory nhất
- [ ] Kiểm tra `lua_max_running_timers` và `lua_max_pending_timers` trong log

---

## 10. Completion Checklist

- [ ] Giải thích được tại sao Kong chạy trên OpenResty và LuaJIT mang lại lợi gì
- [ ] Dựng được Kong DB-less bằng Docker Compose, verify Admin API và proxy hoạt động
- [ ] Trace được request flow qua ít nhất 5 phase của Kong
- [ ] Phân biệt được DB-less, DB-mode, Hybrid và biết khi nào dùng cái nào
- [ ] Giải thích được plugin priority và tại sao correlation-id chạy trước key-auth
- [ ] Biết cách troubleshoot khi Kong không start hoặc proxy trả về 502
- [ ] Hiểu tại sao không nên expose Admin API (port 8001) ra Internet

---

## 11. References

- [Kong Documentation — Architecture](https://docs.konghq.com/gateway/latest/production/deployment-topologies/)
- [OpenResty Reference](https://openresty.org/en/lua-nginx-module.html)
- [Kong Plugin Development Guide](https://docs.konghq.com/gateway/latest/plugin-development/)
- [decK — Declarative Kong](https://docs.konghq.com/deck/latest/)
- [Kong 3.x Migration Guide](https://docs.konghq.com/gateway/latest/upgrade/)
- [LuaJIT Performance Guide](https://luajit.org/performance.html)
- [Kong Community Forum](https://discuss.konghq.com/)

---

## Recap

Day 8 đặt nền móng cho toàn bộ tuần 2. Điểm cốt lõi cần nhớ:

1. **Kong = OpenResty app** — không phải một sản phẩm hoàn toàn mới, mà là Lua application chạy trên Nginx + LuaJIT
2. **Plugin lifecycle** hook vào Nginx phases — access phase là nơi hầu hết auth/rate-limit xảy ra
3. **DB-less** là điểm khởi đầu tốt nhất — đơn giản, reproducible, không cần DB
4. **Admin API** là trung tâm quản lý — nhưng phải lock down, không expose ra Internet
5. **Plugin priority** quyết định thứ tự thực thi — correlation-id trước, post-function sau cùng

---

## Preview Day 9

**Day 9: Kong Core Entities — Services, Routes, Consumers, Plugins**

Bài tiếp theo sẽ deep dive vào 5 entity cốt lõi của Kong:
- Service và Route: cách Kong match request và forward đến đúng backend
- Consumer và Credential: model cho API key, JWT, OAuth2
- Plugin scoping: global vs service vs route vs consumer — khi nào dùng scope nào
- Upstream và Target: load balancing trong Kong
- Hands-on: build một API với key-auth, rate-limiting per-consumer, và ACL
