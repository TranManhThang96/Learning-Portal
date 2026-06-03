# Document: Kong Architecture Deep Dive — OpenResty, Lua Hooks, Plugin Lifecycle

> Tài liệu tham khảo cho Day 08. Đọc sau khi hoàn thành lesson.md.

---

## 1. Nginx Phases × Lua Hooks — Bảng đầy đủ

OpenResty cung cấp các directive để inject Lua code vào từng phase của Nginx request lifecycle. Bảng dưới đây liệt kê đầy đủ tất cả hooks:

### 1.1 HTTP Context Hooks

| Directive | Phase | Scope | Mô tả | Kong dùng để |
|---|---|---|---|---|
| `init_by_lua_block` | Master init | http | Chạy một lần khi master process start | Load plugin code, khởi tạo shared state |
| `init_worker_by_lua_block` | Worker init | http | Chạy một lần khi mỗi worker start | Setup timer, background jobs, cluster events |
| `ssl_certificate_by_lua_block` | SSL handshake | server | Dynamic cert selection dựa trên SNI | SNI-based routing, mTLS verify |
| `ssl_session_fetch_by_lua_block` | SSL session | server | Fetch SSL session từ external store | Session resumption với Redis |
| `ssl_session_store_by_lua_block` | SSL session | server | Store SSL session vào external store | Session resumption với Redis |
| `set_by_lua_block` | Rewrite | location | Set Nginx variable từ Lua | Ít dùng trong Kong |
| `rewrite_by_lua_block` | Rewrite | location | Chạy trước access phase | pre-function plugin, URL rewrite |
| `access_by_lua_block` | Access | location | Auth, rate limit, routing | Plugin execution (auth, rate-limit, ACL) |
| `content_by_lua_block` | Content | location | Generate response | Admin API handler |
| `header_filter_by_lua_block` | Header filter | location | Modify response headers | response-transformer, CORS |
| `body_filter_by_lua_block` | Body filter | location | Modify response body | response-transformer (body) |
| `log_by_lua_block` | Log | location | Async logging sau khi response gửi | file-log, http-log, prometheus |
| `balancer_by_lua_block` | Balancer | upstream | Custom load balancing | Kong's upstream balancer |

### 1.2 Stream Context Hooks (TCP/UDP proxy)

| Directive | Phase | Mô tả |
|---|---|---|
| `init_by_lua_block` | Stream init | Khởi tạo stream context |
| `preread_by_lua_block` | Pre-read | Đọc data trước khi proxy |
| `content_by_lua_block` | Content | Handle stream content |
| `log_by_lua_block` | Log | Log sau khi stream kết thúc |

### 1.3 Thứ tự thực thi trong một request

```
1. init_by_lua_block          (master start, một lần)
2. init_worker_by_lua_block   (worker start, một lần per worker)
   --- Per request ---
3. ssl_certificate_by_lua_block  (nếu HTTPS)
4. rewrite_by_lua_block
5. access_by_lua_block
6. content_by_lua_block / proxy_pass
7. header_filter_by_lua_block
8. body_filter_by_lua_block
9. log_by_lua_block
```

**Quan trọng**: `log_by_lua_block` chạy SAU khi response đã được gửi cho client. Đây là lý do log phase không thể modify response — nhưng cũng là lý do logging không làm chậm response time.

---

## 2. Plugin Priority — Danh sách đầy đủ Built-in Plugins

Kong chạy các plugin trong cùng phase theo thứ tự priority giảm dần. Số lớn hơn = chạy trước.

### 2.1 Bảng priority đầy đủ (Kong 3.6)

| Plugin | Priority | Phase chính | Mô tả |
|---|---:|---|---|
| pre-function | 1000000 | rewrite, access | Custom Lua trước tất cả plugin |
| correlation-id | 100001 | access | Thêm unique request ID |
| zipkin | 100000 | access, header_filter, log | Distributed tracing |
| opentelemetry | 14 | access, header_filter, log | OTel tracing |
| bot-detection | 2500 | access | Detect bot traffic |
| cors | 2000 | access | CORS headers |
| session | 1900 | access | Session management |
| oauth2 | 1004 | access | OAuth2 authentication |
| jwt | 1005 | access | JWT authentication |
| key-auth | 1003 | access | API key authentication |
| key-auth-enc | 1003 | access | API key (encrypted) |
| ldap-auth | 1002 | access | LDAP authentication |
| basic-auth | 1001 | access | HTTP Basic auth |
| hmac-auth | 1000 | access | HMAC authentication |
| ip-restriction | 990 | access | IP whitelist/blacklist |
| acl | 950 | access | Access Control List |
| rate-limiting | 910 | access | Rate limiting |
| rate-limiting-advanced | 910 | access | Rate limiting (Enterprise) |
| response-ratelimiting | 900 | access | Rate limit by response header |
| request-size-limiting | 951 | access | Limit request body size |
| request-termination | 2 | access | Terminate request with custom response |
| request-transformer | 801 | access | Modify request |
| request-transformer-advanced | 800 | access | Modify request (Enterprise) |
| response-transformer | 800 | header_filter | Modify response |
| response-transformer-advanced | 800 | header_filter | Modify response (Enterprise) |
| aws-lambda | 750 | access | Invoke AWS Lambda |
| azure-functions | 749 | access | Invoke Azure Functions |
| grpc-gateway | 998 | access | gRPC-HTTP transcoding |
| grpc-web | 3 | access | gRPC-Web protocol |
| proxy-cache | 100 | access, header_filter | Response caching |
| prometheus | 13 | log | Prometheus metrics |
| datadog | 10 | log | Datadog metrics |
| statsd | 11 | log | StatsD metrics |
| file-log | 9 | log | Log to file |
| http-log | 12 | log | Log to HTTP endpoint |
| tcp-log | 7 | log | Log to TCP |
| udp-log | 8 | log | Log to UDP |
| syslog | 4 | log | Log to syslog |
| loggly | 6 | log | Log to Loggly |
| post-function | -1000 | access, log | Custom Lua sau tất cả plugin |

### 2.2 Plugin Scope Inheritance

```
Scope hierarchy (từ rộng đến hẹp):
  Global → Service → Route → Consumer

Khi có conflict, scope hẹp hơn override scope rộng hơn.

Ví dụ thực tế:
  Global rate-limiting: 100 req/min
  Service "premium-api" rate-limiting: 1000 req/min
  Route "/premium/v2" rate-limiting: 5000 req/min
  Consumer "enterprise-client" rate-limiting: 50000 req/min

  → enterprise-client gọi /premium/v2 → áp dụng 50000 req/min
  → anonymous user gọi /premium/v2 → áp dụng 5000 req/min
  → anonymous user gọi /basic/v1 → áp dụng 100 req/min
```

---

## 3. Kong 2.x vs 3.x — Breaking Changes

### 3.1 Route Path Matching

**Kong 2.x**: Path mặc định là regex nếu chứa ký tự đặc biệt.

**Kong 3.x**: Path mặc định là **plain text prefix**. Để dùng regex, phải thêm prefix `~`:

```yaml
# Kong 2.x — regex tự động
routes:
  - paths:
      - /api/v[0-9]+/users

# Kong 3.x — phải thêm ~ để dùng regex
routes:
  - paths:
      - ~/api/v[0-9]+/users

# Kong 3.x — plain text prefix (mặc định)
routes:
  - paths:
      - /api/v1/users
```

### 3.2 Expressions Router (Kong 3.0+)

Kong 3.x giới thiệu **Expressions Router** — một DSL mới cho phép viết routing rule phức tạp hơn:

```yaml
# Expressions router syntax
routes:
  - name: complex-route
    expression: >
      http.path ^= "/api/v2" &&
      http.method == "POST" &&
      http.headers["x-tenant-id"] != null
    priority: 100
```

Expressions router hỗ trợ:
- `http.path` — path matching
- `http.method` — HTTP method
- `http.headers["name"]` — header matching
- `http.host` — host matching
- `net.src.ip` — source IP
- Operators: `==`, `!=`, `^=` (prefix), `=^` (suffix), `~` (regex), `&&`, `||`, `!`

### 3.3 Các Breaking Changes khác trong Kong 3.x

| Change | Kong 2.x | Kong 3.x |
|---|---|---|
| `_format_version` | `"2.1"` | `"3.0"` |
| Route path regex | Tự động detect | Phải thêm `~` prefix |
| `service.protocol` | `http`, `https`, `grpc`, `grpcs` | Thêm `ws`, `wss` (WebSocket) |
| Plugin `run_on` | Có | Đã bỏ |
| `api` entity | Deprecated | Đã xóa hoàn toàn |
| `consumer_group` | Không có | Thêm mới (rate-limiting per group) |
| Status API | Port 8001 `/status` | Port 8100 `/status` (riêng) |
| Expressions router | Không có | Thêm mới |

### 3.4 Migration từ 2.x lên 3.x

```bash
# Bước 1: Export config từ Kong 2.x
deck dump --output-file kong-2x.yaml

# Bước 2: Convert format
deck convert --from kong-gateway-2.x --to kong-gateway-3.x   --input-file kong-2x.yaml   --output-file kong-3x.yaml

# Bước 3: Validate
deck validate --state kong-3x.yaml

# Bước 4: Diff với Kong 3.x instance
deck diff --state kong-3x.yaml

# Bước 5: Apply
deck sync --state kong-3x.yaml
```

---

## 4. Hybrid Mode — Architecture và CP/DP Communication

### 4.1 Hybrid Mode Architecture

```
+------------------------------------------------------------------+
|                    Hybrid Mode Architecture                       |
+------------------------------------------------------------------+
|                                                                   |
|  Admin/Ops Team                                                   |
|       |                                                           |
|       | Admin API (8001)                                          |
|       v                                                           |
|  +------------------+                                             |
|  |  Control Plane   |                                             |
|  |  (CP)            |                                             |
|  |  - Admin API     |                                             |
|  |  - Kong Manager  |                                             |
|  |  - PostgreSQL    |                                             |
|  +--------+---------+                                             |
|           |                                                       |
|           | mTLS (port 8005)                                      |
|           | Config push (binary protocol)                         |
|           |                                                       |
|    +------+-------+-------+                                       |
|    |               |       |                                      |
|    v               v       v                                      |
|  +------+       +------+ +------+                                 |
|  | DP 1 |       | DP 2 | | DP 3 |  <- proxy traffic only         |
|  | :8000|       | :8000| | :8000|                                 |
|  +------+       +------+ +------+                                 |
|                                                                   |
|  Traffic: Client --> DP (8000/8443) --> Upstream                  |
|  Config:  Admin API --> CP --> DP (push via 8005)                 |
|                                                                   |
+------------------------------------------------------------------+
```

### 4.2 CP-DP Communication Protocol

- **Transport**: mTLS (mutual TLS) — cả CP và DP đều verify certificate của nhau
- **Protocol**: WebSocket over TLS (port 8005)
- **Direction**: CP push config xuống DP (không phải DP pull)
- **Format**: Binary (MessagePack)
- **Frequency**: Khi có config change, CP push ngay lập tức
- **Fallback**: DP cache config local — nếu mất kết nối với CP, DP vẫn tiếp tục proxy với config cũ

### 4.3 DP Config Cache

Data Plane lưu config vào local file (`/usr/local/kong/declarative/config.json.gz`) để:
- Khởi động lại nhanh mà không cần chờ CP
- Tiếp tục hoạt động khi CP tạm thời không available

```bash
# Kiểm tra DP có kết nối với CP không
curl http://dp-host:8100/status | jq '.configuration_hash'
# Nếu hash khớp với CP -> config đã sync

# Trên CP, xem DP nào đang kết nối
curl http://cp-host:8001/clustering/data-planes | jq '.data[] | {id, ip, last_seen}'
```

### 4.4 Docker Compose cho Hybrid Mode (tham khảo)

```yaml
version: "3.8"

services:
  kong-cp:
    image: kong:3.6
    environment:
      KONG_ROLE: control_plane
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_CLUSTER_LISTEN: "0.0.0.0:8005"
    volumes:
      - ./certs:/certs
    ports:
      - "8001:8001"
      - "8005:8005"

  kong-dp:
    image: kong:3.6
    environment:
      KONG_ROLE: data_plane
      KONG_DATABASE: "off"
      KONG_CLUSTER_CONTROL_PLANE: kong-cp:8005
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
    volumes:
      - ./certs:/certs
    ports:
      - "8000:8000"
      - "8100:8100"
    depends_on:
      - kong-cp

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpass
```

---

## 5. Shared Dict — Chi tiết kỹ thuật

### 5.1 Các shared dict trong Kong

```nginx
# Được Kong generate trong nginx.conf
lua_shared_dict kong                5m;    # General Kong state
lua_shared_dict kong_db_cache       128m;  # DB entity cache
lua_shared_dict kong_db_cache_miss  12m;   # Negative cache (entity not found)
lua_shared_dict kong_locks          8m;    # Distributed locks
lua_shared_dict kong_process_events 5m;    # Inter-process events
lua_shared_dict kong_cluster_events 5m;    # Cluster-wide events
lua_shared_dict kong_rate_limiting_counters 12m;  # Rate limit counters
lua_shared_dict kong_core_db_cache  128m;  # Core entity cache
lua_shared_dict kong_core_db_cache_miss 12m;
```

### 5.2 Shared Dict API

```lua
-- Đọc/ghi shared dict từ Lua plugin
local dict = ngx.shared.kong_rate_limiting_counters

-- Set với TTL
dict:set("key", value, ttl_seconds)

-- Atomic increment
local newval, err = dict:incr("counter_key", 1, 0)  -- init=0 nếu chưa có

-- Get
local val = dict:get("key")

-- Delete
dict:delete("key")

-- Flush expired keys
dict:flush_expired()
```

### 5.3 Giới hạn và Pitfalls

- Shared dict là **per-node** — không shared giữa các Kong instance khác nhau
- Kích thước cố định khi khởi động — không thể resize mà không restart
- Nếu dict đầy, `set` sẽ fail với error `"no memory"` — cần monitor usage
- Dùng `dict:capacity()` và `dict:free_space()` để monitor

```bash
# Monitor shared dict usage qua Admin API
curl -s http://localhost:8001/status | jq '.memory.lua_shared_dicts'
```

---

## 6. decK — Declarative Kong CLI

decK (Declarative Kong) là tool chính thức để quản lý Kong config dưới dạng code.

### 6.1 Cài đặt

```bash
# macOS
brew install kong/deck/deck

# Linux
curl -sL https://github.com/kong/deck/releases/download/v1.38.0/deck_1.38.0_linux_amd64.tar.gz | tar xz
sudo mv deck /usr/local/bin/

# Verify
deck version
```

### 6.2 Workflow cơ bản

```bash
# Export config hiện tại từ Kong
deck dump --kong-addr http://localhost:8001 --output-file kong-config.yaml

# Validate file config
deck validate --state kong-config.yaml

# Xem diff giữa file và Kong đang chạy
deck diff --kong-addr http://localhost:8001 --state kong-config.yaml

# Apply config (sync)
deck sync --kong-addr http://localhost:8001 --state kong-config.yaml

# Reset Kong về trạng thái ban đầu (xóa tất cả)
deck reset --kong-addr http://localhost:8001
```

### 6.3 decK trong CI/CD

```yaml
# .github/workflows/kong-deploy.yml
name: Deploy Kong Config

on:
  push:
    branches: [main]
    paths: ['kong/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install decK
        run: |
          curl -sL https://github.com/kong/deck/releases/download/v1.38.0/deck_1.38.0_linux_amd64.tar.gz | tar xz
          sudo mv deck /usr/local/bin/

      - name: Validate config
        run: deck validate --state kong/kong-config.yaml

      - name: Diff
        run: deck diff --kong-addr ${{ secrets.KONG_ADMIN_URL }} --state kong/kong-config.yaml

      - name: Sync
        run: deck sync --kong-addr ${{ secrets.KONG_ADMIN_URL }} --state kong/kong-config.yaml
```

---

## 7. Kong OSS vs Kong Enterprise vs Kong Mesh

| Feature | Kong OSS | Kong Enterprise | Kong Mesh |
|---|---|---|---|
| **Core proxy** | Có | Có | Có (Envoy-based) |
| **Plugin ecosystem** | ~50 plugins | ~80+ plugins | Sidecar plugins |
| **Admin API** | Có | Có | Có |
| **Kong Manager (UI)** | Không | Có | Có |
| **RBAC** | Không | Có | Có |
| **Dev Portal** | Không | Có | Không |
| **Kong Vitals** | Không | Có | Không |
| **Rate limiting advanced** | Không | Có | Không |
| **OPA integration** | Không | Có | Có |
| **Service mesh** | Không | Không | Có |
| **mTLS between services** | Không | Không | Có |
| **Traffic policy** | Không | Không | Có |
| **Scope của khóa học** | **Học** | Tham khảo | Không học |

**Lưu ý**: Khóa học này tập trung hoàn toàn vào **Kong OSS** (open source). Các feature Enterprise được đề cập để học viên biết giới hạn và khi nào cần upgrade.

