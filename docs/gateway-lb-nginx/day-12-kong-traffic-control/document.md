# Day 12: Reference Document — Rate Limiting Policy Deep Dive, ACL Internals & Request Transformer

---

## 1. Rate Limiting Policy: local vs cluster vs redis

### 1.1 `local` Policy — In-Memory Counter

**Cơ chế hoạt động:**

Kong dùng **shared memory dictionary** (Lua shared dict) trên mỗi Kong node. Counter được lưu trong shared memory và được access bởi tất cả worker process trên cùng node.

```
Kong Node 1
  ├── Worker 1 ─┐
  ├── Worker 2 ──┼──► Shared Memory Dict (mmap)
  └── Worker 3 ──┘     ├── rate-limit:consumer-1:route-1:window → 47
                        ├── rate-limit:consumer-2:route-1:window → 12
                        └── ...

Kong Node 2 (không chia sẻ memory với Node 1)
  ├── Worker 1 ─┐
  └── Worker 2 ──┴──► Shared Memory Dict (riêng)
                        ├── rate-limit:consumer-1:route-1:window → 23  ← GIÁ TRỊ KHÁC
                        └── ...
```

**Memory model:**

```
Zone name: rate_limit_shared_dict
Default size: 5m (có thể override bằng KONG_LUA_SHRUBER_SIZE)
Mỗi entry: key (string) + value (integer) + metadata
Estimated entries: ~10,000-50,000 unique consumer/window combinations
```

**TTL behavior:**

Kong set TTL cho mỗi key khi counter reset (window expired). Redis dùng `EXPIRE`, local policy dùng **timestamp-based expiration check** trong Lua code — mỗi request kiểm tra `now - last_reset > window_size`.

**Use case:**

```yaml
# Dev/test environment
plugins:
  - name: rate-limiting
    config:
      policy: local          # Không cần Redis
      minute: 100
      second: null
      hour: null
      fault_tolerant: true
```

### 1.2 `cluster` Policy — PostgreSQL (Deprecated)

**Table schema:**

```sql
CREATE TABLE IF NOT EXISTS ratelimiting_metrics (
    identifier    TEXT,          -- consumer_id hoặc IP
    route_id     UUID,
    service_id   UUID,
    period       TEXT,           -- "minute", "hour", "day"
    period_date  TIMESTAMP,      -- start of window
    value        BIGINT,        -- counter
    ttl          TIMESTAMP,      -- expiration
    PRIMARY KEY (identifier, route_id, service_id, period, period_date)
);
```

**Điểm yếu nghiêm trọng:**

```
Mỗi request → PostgreSQL INSERT ON CONFLICT UPDATE
→ 1 network round-trip đến DB
→ Connection pool exhaust khi traffic cao
→ DB becomes bottleneck khi RPS > 1000
```

**Lý do bị deprecated:**

1. Tốc độ chậm — không đủ cho production traffic
2. Chỉ hoạt động ở DB-mode — không tương thích DB-less
3. Nhiều connection tranh chấp — DB connection pool là bottleneck
4. Redis policy giải quyết tốt hơn về performance

### 1.3 `redis` Policy — Distributed Counter

**Kiến trúc:**

```
Request A ──► Kong Node 1 ──► Redis (10.0.0.5:6379) ──► INCR key
Request B ──► Kong Node 2 ──► Redis (10.0.0.5:6379) ──► INCR key  (cùng key!)
Request C ──► Kong Node 3 ──► Redis (10.0.0.5:6379) ──► INCR key  (cùng key!)
                                     ↓
                              Atomic Lua script
                              (EVAL/EVALSHA)
```

**Redis key format:**

```
rate-limiting:{identifier}:{window_epoch}
  │
  ├── identifier = consumer.id nếu authenticated
  ├── identifier = "ip-$(remote_addr)" nếu anonymous
  └── window_epoch = floor(unix_timestamp / window_size)

Ví dụ:
  rate-limiting:consumer-abc123:1716000000  (window=60s, epoch 2024-05-18 10:00:00)
  rate-limiting:ip-192.168.1.1:286400        (window=3600s=1h, epoch 2024-05-18 08:00:00)
```

**Lua script atomic — chi tiết:**

```lua
-- Kong gửi script này qua EVALSHA
-- Redis chạy script atomic (single-threaded, không race condition)

local key = KEYS[1]                     -- rate-limiting:consumer-abc:1716000000
local limit = tonumber(ARGV[1])          -- 1000 (quota)
local window = tonumber(ARGV[2])         -- 60 (seconds)
local current

-- Atomic increment
current = redis.call('INCR', key)

-- Set TTL nếu key mới được tạo
if current == 1 then
    redis.call('EXPIRE', key, window)
end

-- Trả về remaining quota (để ghi vào header)
if current > limit then
    return {0, limit, 0}      -- {allowed, limit, remaining}
else
    return {1, limit, limit - current}  -- {allowed, limit, remaining}
end
```

**EVAL vs EVALSHA:**

| Command | Behavior | Pros | Cons |
|---|---|---|---|
| `EVAL script keys[] args[]` | Gửi full script mỗi lần | Không cần prepare | Tốn bandwidth, script compiled mỗi lần |
| `EVALSHA sha1 keys[] args[]` | Dùng pre-cached script | Nhanh hơn | Redis phải có script cached |

Kong dùng **EVALSHA** — script được load 1 lần khi plugin khởi tạo, sau đó dùng lại qua SHA-1 hash. Nếu Redis restart và flush script cache → Kong tự động re-load script.

**Redis Sentinel vs Redis Cluster:**

```
Redis Sentinel (HA):
  ┌─────────┐
  │ Master  │◄───── Sentinel ─────►  Kong
  └───┬─────┘         │
   ▲   │               ▼
   │   └──► Replica (read)   Sentinel tự động promote replica → master
   │                         Kong tự reconnect khi master thay đổi
   └── Replication (async)

Redis Cluster (Sharding):
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │Node 1   │ │Node 2   │ │Node 3   │
  │Master A │ │Master B │ │Master C │
  └───┬─────┘ └───┬─────┘ └───┬─────┘
      ▼             ▼             ▼
  Shard A       Shard B       Shard C

  Key routing: CRC16(key) mod 16384 → slot → node
  Kong gửi script đến đúng node chứa key
```

**Kong Redis connection config:**

```yaml
plugins:
  - name: rate-limiting
    config:
      policy: redis
      redis_host: 10.0.0.5
      redis_port: 6379
      redis_password: null
      redis_timeout: 2000        # ms
      redis_database: 0
      redis_ssl: false
      redis_ssl_verify: false
      redis_server_name: null    # SNI cho TLS
      redis_connection_timeout: 1000  # ms
      redis_pool_size: 10       # connections per Kong node
```

---

## 2. Fixed Window vs Sliding Window — Deep Dive

### 2.1 Fixed Window (rate-limiting plugin — OSS)

**Thuật toán:**

```
Window size = 1 giờ
Window 1: 10:00:00 → 10:59:59 → max 1000 req
Window 2: 11:00:00 → 11:59:59 → max 1000 req

Key = floor(timestamp / window_size) * window_size
Key = floor(1716000000 / 3600) * 3600 = 1716000000 (window 1)

Couter reset ngay lập tức khi window chuyển sang window 2
```

**Burst boundary problem:**

```
Tại thời điểm 10:59:58, counter = 999 (gần đạt limit 1000)
Client gửi thêm 50 requests trong 3 giây cuối
→ 49 requests OK (vì counter < 1000)
→ Counter = 1000

Window chuyển sang 11:00:00 → counter reset về 0
→ Client gửi thêm 100 requests ngay
→ Counter = 100, tất cả OK

Kết quả: 1100 requests trong 5 phút (10:58 → 11:02)
→ Quota 1000 req/h bị vượt 10% mà không có cơ chế nào ngăn
```

### 2.2 Sliding Window Counter (rate-limiting-advanced — Enterprise)

**Thuật toán:**

```
Sliding window = window trượt theo thời gian hiện tại
Window size = 1 giờ

Request tại t=10:30:00:
  → Tính weighted count = (1 - ratio) * prev_window_count + curr_window_count
  → prev_window: [09:30:00, 10:29:59] = 800 requests
  → curr_window: [10:30:00, 10:30:00] = 1 request
  → ratio = (t - window_start) / window_size = 0.5
  → weighted = (1 - 0.5) * 800 + 1 = 401
  → 401 < 1000 → ALLOW

Request tại t=10:59:58:
  → prev_window: [09:59:58, 10:58:58] = 950 requests (gần hết quota)
  → curr_window: [10:58:58, 10:59:58] = 50 requests
  → ratio = 0.999
  → weighted = (1 - 0.999) * 950 + 50 = 50.95
  → 50.95 < 1000 → ALLOW (gần đạt limit trong prev window)

→ Không có burst boundary spike
```

**Redis key cho sliding window:**

```
sliding-window-log:{identifier}:{window_id}
  → Redis sorted set (ZSET)
  → Score = timestamp
  → Member = unique request ID (UUID)

Sliding window counter:
sliding-window-counter:{identifier}:{window_epoch}
  → Integer counter, weighted calculation
```

### 2.3 Sliding Window Log (rate-limiting-advanced — Enterprise, optional)

```
Redis ZSET:
  Key: sliding-window-log:consumer-abc:1716000000
  Members:
    ZADD key 1716000001 "req-uuid-001"
    ZADD key 1716000005 "req-uuid-002"
    ZADD key 1716000010 "req-uuid-003"

Sliding window query:
  ZREMRANGEBYSCORE key -inf (now - window_size)
  ZCARD key  → số lượng request trong window
  ZREMRANGEBYSCORE key -inf (now - window_size) + ZADD new member
```

Ưu điểm: **Hoàn toàn chính xác** — đếm từng request.
Nhược điểm: Tốn memory hơn (ZSET per consumer per window), phải cleanup expired entries.

---

## 3. ACL Plugin Internals

### 3.1 Consumer Groups Storage

**DB-mode:**
```sql
CREATE TABLE acls (
    id         UUID PRIMARY KEY,
    consumer_id UUID REFERENCES consumers(id),
    group      TEXT,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_acaoc_acls_consumer ON acls(consumer_id);
```

**DB-less (in kong.yml):**
```yaml
consumers:
  - username: pro-user
    acls:
      - group: pro
      - group: premium
```

### 3.2 ACL Check Algorithm

```lua
-- Kong ACL plugin logic (Lua)
local acl = require("kong.plugins.acl.acl")

function acl.access(conf)
    local consumer = kong.client.get_consumer()  -- Lấy consumer từ auth plugin
    if not consumer then
        -- Consumer chưa được resolve → không có ACL entries → deny
        return kong.response.exit(403,
            { message = "Forbidden" },
            { ["X-Authenticated-Groups"] = "" }
        )
    end

    local groups = load_acl_groups_for_consumer(consumer.id)  -- ["pro", "premium"]

    -- Check deny list TRƯỚC
    if #conf.deny > 0 then
        for _, denied in ipairs(conf.deny) do
            for _, group in ipairs(groups) do
                if group == denied then
                    return kong.response.exit(403,
                        { message = "You cannot access this resource" }
                    )
                end
            end
        end
    end

    -- Check allow list SAU
    if #conf.allow > 0 then
        local allowed = false
        for _, allowed_group in ipairs(conf.allow) do
            for _, group in ipairs(groups) do
                if group == allowed_group then
                    allowed = true
                    break
                end
            end
            if allowed then break end
        end
        if not allowed then
            return kong.response.exit(403,
                { message = "Forbidden" }
            )
        end
    end
    -- Nếu không có allow list → cho phép tất cả (nếu không có deny)
end
```

**Deny override allow (explicit deny):**

```yaml
# Consumer thuộc cả pro và b2b
acls:
  - group: pro
  - group: b2b

# ACL plugin
allow: [pro, enterprise]
deny: [b2b]

# → b2b bị deny override pro trong allow
# → Consumer không được vào dù thuộc pro
```

### 3.3 Anonymous Consumer và ACL

```
Anonymous consumer không có ACL entries → ACL deny mọi anonymous request
→ Trừ khi ACL plugin được config với allow anonymous

Fix bằng anonymous consumer với group:
consumers:
  - username: anonymous
    acls:
      - group: public
    plugins:
      - name: acl
        config:
          allow: [public]    # anonymous được phép vào public endpoints
```

---

## 4. request-transformer — Template Syntax & Variables

### 4.1 Available Template Variables

| Variable | Phase | Description | Example |
|---|---|---|---|
| `$(consumer.id)` | access | Consumer UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `$(consumer.username)` | access | Consumer username | `mobile-app` |
| `$(request.id)` | access | Unique request ID (UUID) | `abc123-def456` |
| `$(request.uri)` | access | Original request URI | `/v1/orders/123` |
| `$(request.method)` | access | HTTP method | `POST` |
| `$(request.scheme)` | access | http/https | `https` |
| `$(request.host)` | access | Host header | `api.example.com` |
| `$(remote_addr)` | access | Client IP (sau real_ip) | `1.2.3.4` |
| `$(latency.request)` | access | Request processing latency (ms) | `0.5` |
| `$(latency.proxy)` | access | Upstream proxy latency (ms) | `45.2` |
| `$(upstream.url)` | access | Full upstream URL | `http://order-svc:8080/v1/orders` |

### 4.2 Header Injection — Consumer Metadata

```yaml
plugins:
  - name: request-transformer
    config:
      add:
        headers:
          # Inject consumer info cho upstream backend biết ai đang gọi
          - "X-Consumer-ID:$(consumer.id)"
          - "X-Consumer-Username:$(consumer.username)"
          - "X-Request-ID:$(request.id)"
          # Upstream có thể dùng X-Consumer-ID để query user data cache
          - "X-Forwarded-User:$(consumer.username)"
```

ACL groups không phải template variable của request-transformer. Nếu cần expose group cho debug, cấu hình ACL plugin với `hide_groups_header: false` để Kong emit `X-Authenticated-Groups`; với production nên cân nhắc không forward header này ra public client.

**Use case thực tế:**

```
Upstream không cần parse API key từ request
→ Kong inject X-Consumer-ID vào header
→ Upstream nhận header, query database theo consumer_id
→ Không cần trust client-side API key parsing
```

### 4.3 request-transformer vs request-transformer-advanced

| Feature | request-transformer | request-transformer-advanced |
|---|---|---|
| Add headers | Có | Có + template variable |
| Remove headers | Có | Có |
| Replace headers | Có | Có + regex |
| Add query params | Có | Có |
| Add body params | Không | Có |
| Rename keys | Không | Có |
| Remove body params | Không | Có |
| JSON template | Không | Có ( Enterprise) |
| Cost | Miễn phí (OSS) | Kong Enterprise |

**Note**: `request-transformer-advanced` là **Enterprise** plugin — không có trong Kong OSS.

---

## 5. Kong Rate Limiting vs Nginx OSS limit_req — So sánh Chi Tiết

### 5.1 Algorithm Difference

| Aspect | Nginx `limit_req` | Kong rate-limiting |
|---|---|---|
| Algorithm | Leaky bucket | Token bucket (fixed window) |
| Burst handling | Queue + delay | Hard limit (reject trên quota) |
| Distributed | Không | Có (Redis) |
| Per-request cost | ~1-5 microsecond | ~1-2 ms (Redis round-trip) |
| Counter storage | Shared memory (shm) | Redis (network) |
| Atomic operation | Mutex lock (shm) | Lua EVAL atomic |
| Accuracy | Chính xác (1 node) | Chính xác (Redis atomic) |

### 5.2 Design Decision Matrix

```
Nên dùng Kong rate-limiting khi:
  ✓ Multi-node Kong deployment
  ✓ Rate limit theo consumer (authenticated)
  ✓ Cần ACL integration (group-based)
  ✓ Cần Prometheus metrics cho rate-limit
  ✓ Cần fail-over giữa các Kong node

Nên dùng Nginx limit_req khi:
  ✓ Single Nginx instance
  ✓ Không cần consumer-level granularity
  ✓ Edge protection trước khi request vào Kong
  ✓ L4/L4 load balancing level protection
  ✓ Ultra-low latency (< 10ms requirement)
```

### 5.3 Hybrid Architecture

```
Client
  │
  ▼
Nginx Edge (limit_req per IP)
  │  ┌──────────────────────────┐
  │  │ Nginx shared memory zone │
  │  │ → Block massive flood   │
  │  │ → Auth IP-based rough   │
  │  └──────────────────────────┘
  ▼
Kong Gateway (rate-limiting per consumer + Redis)
  │  ┌──────────────────────────┐
  │  │ Redis distributed quota  │
  │  │ → Precise consumer limit │
  │  │ → Multi-node consistent  │
  │  └──────────────────────────┘
  ▼
Upstream backend
```

---

## 6. Observability — Prometheus Metrics

### 6.1 Key Metrics cho Rate Limiting

```promql
# Request bị 429 (rate limit exceeded)
sum(rate(kong_http_status{code="429"}[5m])) by (service, route, consumer)

# Rate limit plugin latency
kong_plugin_latency_ms_bucket{plugin="rate-limiting", le="10"}
kong_plugin_latency_ms_bucket{plugin="rate-limiting", le="50"}

# Redis latency (không có metric native — dùng external exporter)
redis_latency_ms_seconds_bucket{le="1"}

# Consumer quota consumption
# (Cần custom metric hoặc Prometheus Redis exporter)
```

### 6.2 Grafana Dashboard Panels

| Panel | Query | Alert threshold |
|---|---|---|
| 429 Rate/sec | `sum(rate(kong_http_status{code="429"}[5m]))` | > 10/sec |
| Rate-limit plugin latency p99 | `histogram_quantile(0.99, kong_plugin_latency_ms_bucket{plugin="rate-limiting"})` | > 50ms |
| Redis connection errors | `rate(redis_errors_total{type="connection"}[5m])` | > 0 |
| Top 429 consumers | `topk(5, sum by (consumer) (rate(kong_http_status{code="429"}[5m])))` | N/A |

---

## 7. fault_tolerant — Chi Tiết Behavior

### 7.1 Fault Tolerant = true (fail open)

```lua
-- Kong source (simplified)
function rate_limit_access(conf)
    local ok, err = redis_call("INCR", key)
    if not ok then
        -- Redis error
        if conf.fault_tolerant then
            kong.log.warn("Redis error, failing open: ", err)
            return  -- Cho request đi qua, không rate-limit
        else
            kong.response.exit(500, { message = "Rate limiting error" })
        end
    end
    -- Continue...
end
```

### 7.2 Production Recommendation

```yaml
# Critical API (billing, payment, auth)
plugins:
  - name: rate-limiting
    config:
      policy: redis
      redis_host: redis-cluster.internal
      fault_tolerant: false    # Redis down → 500, không cho qua
      error_message: '{"error":"Rate limit service unavailable","code":"RL_UNAVAILABLE"}'

# Non-critical API (analytics, reporting)
plugins:
  - name: rate-limiting
    config:
      policy: redis
      fault_tolerant: true     # Redis down → fail open, graceful degradation
```

---

## 8. Plugin Priority — Full List

| Priority | Plugin | Phase | Mục đích |
|---|---|---|---|
| 10000 | prometheus | access | Metrics collection |
| 2500 | bot-detection | access | Detect crawlers |
| 2000 | cors | access | CORS headers |
| 1500 | (custom) | access | Your custom plugin |
| 1005 | jwt | access | JWT verify |
| 1003 | key-auth | access | API key verify |
| 990 | ip-restriction | access | IP allow/deny |
| 950 | acl | access | Group authorization |
| 930 | correlation-id | access | Add request ID |
| 910 | rate-limiting | access | Quota check |
| 900 | response-ratelimiting | access | Response size quota |
| 951 | request-size-limiting | access | Body size check |
| 801 | request-transformer | access | Mutate request |
| 800 | response-transformer | header_filter | Mutate response |
| 1 | correlation-id (log) | log | Log injection |

**Key insight**: `ip-restriction` (990) chạy **trước** `key-auth` (1003) — đây là intentional design: block IP xấu trước khi tốn resource cho authentication.
