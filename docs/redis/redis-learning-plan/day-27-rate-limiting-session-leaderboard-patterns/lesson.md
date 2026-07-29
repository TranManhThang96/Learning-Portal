# Day 27: Rate Limiting, Session & Leaderboard Patterns

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân biệt và implement được 4 thuật toán rate limiting: fixed window, sliding window, token bucket, leaky bucket — biết khi nào dùng cái nào và trade-off cụ thể.
- Design được distributed rate limiter dùng Redis, hiểu clock skew và edge case khi nhiều node cùng access.
- Implement được session store bằng Redis với TTL, refresh token, và invalidation strategy; phân tích được khi nào Redis session tốt hơn stateless JWT và ngược lại.
- Build được leaderboard bằng Sorted Set với O(log N) update và O(log N + M) range query; xử lý được tie-breaking, pagination, và real-time score update.
- Implement được idempotency key pattern cho payment-like API dùng `SET NX PX`, đảm bảo safe retry mà không duplicate processing.

---

## 2. Vì sao cần học chủ đề này

### Scenario production giả lập 1: Fixed Window Burst — API Gateway Quá Tải 2 Lần Trong 1 Phút

Một API gateway dùng fixed window rate limit: 1000 requests/phút per user. Dev test thấy ổn. Production chạy, thấy spike 2000 requests trong 2 giây đầu của mỗi phút — người dùng đồng thời hết rate limit ở phút N, rồi ngay đầu phút N+1 lại được phép 1000 requests mới. Kết quả: backend 2000 req/s thay vì max 1000/60 ≈ 17 req/s. Nguyên nhân: fixed window không smooth traffic, cho phép burst gấp đôi tại boundary.

**Misconception phổ biến**: "Rate limit 1000/phút = 16.6 req/s đều đặn". Sai. Fixed window cho phép burst tại window boundary.

### Scenario production giả lập 2: JWT Stateless Session Bị Revoke Trễ — Tiền Bị Trừ 2 Lần

Một hệ thống payment dùng stateless JWT với `exp = now + 1h`. User click "Pay" 2 lần cách nhau 500ms. 2 requests đều có JWT hợp lệ, đều đi qua API gateway (rate limit OK), cả 2 đều gọi payment service. Backend xử lý cả 2 vì không có centralized session state. Tiền bị trừ 2 lần. Sau đó mới phát hiện và refund. Root cause: stateless JWT không có centralized revoke mechanism. Token chỉ expire theo thời gian, không theo event (ví dụ: "user logout" hoặc "payment confirmed").

**Misconception phổ biến**: "JWT không cần server-side state nên scalable". Đúng về mặt compute, nhưng sai khi cần revoke ngay lập tức.

### Scenario production giả lập 3: Leaderboard Write Stampede — Redis CPU 100% Khi Game Launch

Game mobile launch với leaderboard trên Redis Sorted Set. 50.000 người chơi cùng submit score trong 5 phút đầu. Mỗi `ZADD` = O(log N). 50K × O(log 50K) = 50K × 16 = 800K operations. Nhưng khi 500 người chơi cùng request top 100 leaderboard liên tục (polling 1s), Redis phải xử lý đồng thời read + write trên cùng key. CPU tăng từ 5% lên 100%, latency tăng từ 1ms lên 500ms+. Nguyên nhân: hot key (leaderboard key là single hot key), không có read/write separation.

**Misconception phổ biến**: "Sorted Set O(log N) là đủ nhanh". Đúng cho individual operation, nhưng không đúng khi hot key phải xử lý 50K writes + 500 × 50K reads/giây.

**Bottom line**: Rate limiting, session, leaderboard là những pattern mà design sai không kill ngay lập tức nhưng gây incident lớn khi scale — và production incidents thường là tổ hợp của nhiều pattern cùng fail.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model (Day 1) — hiểu tại sao Lua script atomic và blocking risk
- Lua scripting (Day 16) — vì tất cả rate limiter phức tạp cần Lua để atomicity
- Pipelining (Day 11) — batch operations cho session store
- Sorted Set (Day 2) — leaderboard foundation
- Key naming convention (Day 4) — session key, rate limit key, leaderboard key design
- Redis Cluster hash tags (Day 22) — khi rate limiter phải operate trên Cluster

---

## 4. Nội dung lý thuyết từ cơ bản đến chi tiết

### 4.1. Fixed Window Rate Limiting

**Concept**: Chia thời gian thành các cửa sổ cố định (window). Mỗi window có quota riêng. Counter reset khi window mới bắt đầu.

**Redis implementation đơn giản**:

```
Key: ratelimit:{user_id}:{window_timestamp}
Command: INCR + EXPIRE
```

```
WINDOW_START = timestamp / WINDOW_SIZE_SECONDS * WINDOW_SIZE_SECONDS
key = f"ratelimit:{user_id}:{WINDOW_START}"
count = INCR(key)
if count == 1:
    EXPIRE(key, WINDOW_SIZE_SECONDS * 2)  # 2x để tránh race condition
return ALLOW if count <= LIMIT else DENY
```

**Ưu điểm**: Đơn giản, 2 commands (INCR + EXPIRE lần đầu), memory O(1) per user.
**Nhược điểm**: Boundary burst — user có thể dùng LIMIT requests cuối window + LIMIT requests đầu window tiếp theo = 2x burst.

```
Timeline (60s window):
User A:  [===== 60s window =====]
         58s: 1000 req (limit reached)
         59s: 1000 req (limit reached)
         60s: window reset -> 1000 req mới -> 2000 req/s!
```

### 4.2. Sliding Window Rate Limiting

**Concept**: Quota áp dụng cho `now - window_size` tới `now`, không phải từ đầu window cố định. Smooth hơn, không có boundary burst.

**Implementation bằng Sorted Set**:

```
Key: ratelimit:{user_id}
Members: unique request IDs (timestamp:random)
Score: timestamp (epoch ms)

Mỗi request:
  1. Xóa các entry cũ: ZREMRANGEBYSCORE key 0 (now - window_ms)
  2. Đếm: ZCARD key
  3. Nếu < limit: ZADD key score unique_id + EXPIRE
```

**Implementation bằng Lua (atomic)**:

```lua
-- Sliding window log
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests in window
local current = redis.call('ZCARD', key)

if current < limit then
    redis.call('ZADD', key, now, unique_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return {1, current + 1, limit}
else
    return {0, current, limit}
end
```

**Ưu điểm**: Không burst ở boundary, smooth traffic, accurate quota.
**Nhược điểm**: Memory cao hơn (Sorted Set per user, O(window_size) entries), Lua script phức tạp hơn fixed window.

### 4.3. Token Bucket

**Concept**: Bucket chứa tokens. Mỗi request lấy 1 token. Tokens refill với rate cố định. Burst = bucket size.

```
Parameters:
  - bucket_size: số tokens tối đa (burst capacity)
  - refill_rate: tokens/giây (sustain rate)

Request:
  if tokens >= 1:
      tokens -= 1
      ALLOW
  else:
      DENY
```

**Redis implementation bằng Lua**:

```lua
local key = KEYS[1]
local now = redis.call('TIME')
now = tonumber(now[1]) + tonumber(now[2]) / 1000000

local bucket_size = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = bucket_size
    last_refill = now
end

-- Refill tokens based on elapsed time
local elapsed = now - last_refill
local refilled = elapsed * refill_rate
tokens = math.min(bucket_size, tokens + refilled)
last_refill = now

-- Consume token
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {1, tokens, bucket_size}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {0, tokens, bucket_size}
end
```

**Use case**: API burst allowance (ví dụ: cho phép burst 100 req/s nhưng sustain chỉ 10 req/s). Phù hợp khi user gửi batch requests.

### 4.4. Leaky Bucket

**Concept**: Request queue vào bucket, output ra với rate cố định. Bucket overflow = reject.

```
Parameters:
  - bucket_size: queue max (overflow threshold)
  - leak_rate: requests/giây (output rate)

Request:
  if queue_size < bucket_size:
      add_to_queue
      ALLOW
  else:
      DENY
```

**Khác với Token Bucket**: Token bucket cho phép burst vì bucket chứa tokens sẵn. Leaky bucket không cho burst — output rate cố định, queue là buffer.

**Redis implementation bằng Sorted Set**:

```lua
local key = KEYS[1]
local now_arr = redis.call('TIME')
local now = tonumber(now_arr[1]) + tonumber(now_arr[2]) / 1000000

local bucket_size = tonumber(ARGV[1])
local leak_rate = tonumber(ARGV[2])
local request_id = ARGV[3]

-- Queue capacity tương ứng với lượng request có thể chờ trong bucket_size / leak_rate giây.
local retention_window = bucket_size / leak_rate
redis.call('ZREMRANGEBYSCORE', key, 0, now - retention_window)

local size = redis.call('ZCARD', key)
if size < bucket_size then
    redis.call('ZADD', key, now, request_id)
    redis.call('EXPIRE', key, math.ceil(retention_window) + 10)
    return {1, size + 1, bucket_size}
else
    redis.call('EXPIRE', key, math.ceil(retention_window) + 10)
    return {0, size, bucket_size}
end
```

### 4.5. Distributed Rate Limiting

**Challenge**: Khi nhiều app server cùng check Redis, mỗi server phải increment atomic, không được dùng application-level counter vì race condition.

**Solution 1: Atomic Lua Script**
Mọi logic trong 1 Lua script atomic. Single Redis round-trip, atomic increment.

**Solution 2: Redis + Redisson (Jedis-based)**
Dùng `RateLimiter` từ Redisson library.

**Clock Skew Problem**:
Khi dùng local timestamp trong Lua (`redis.call('TIME')`), các app server khác nhau có thể có clock drift ±50ms. Trong distributed system, nên dùng Redis server time (`redis.call('TIME')`) thay vì application time.

**Multi-tenant Rate Limiting**:
```
ratelimit:{tenant_id}:{user_id}   -- per user
ratelimit:{tenant_id}:global       -- per tenant
ratelimit:{tenant_id}:endpoint:{path}  -- per endpoint
```

### 4.6. Session Storage

**Redis session store structure**:

```
Key: session:{session_id}
Type: Hash
Fields:
  user_id: string
  email: string
  roles: JSON string
  created_at: timestamp
  last_accessed: timestamp
  ip_address: string
  user_agent: string
TTL: 24h (sliding — refreshed on access)
```

**Session operations**:

```
-- Create session
HSET session:{id} user_id 123 email "a@b.com" created_at {ts}
EXPIRE session:{id} 86400

-- Read session
HGETALL session:{id}
-- Refresh TTL on access
EXPIRE session:{id} 86400

-- Delete session (logout)
DEL session:{id}

-- Maintain user-session index for bulk revoke
SADD session:user:{user_id} {session_id}
SMEMBERS session:user:{user_id}
```

**Refresh Token Pattern**:

```
Access token: JWT, short-lived (15 min), stateless
Refresh token: stored in Redis, long-lived (7 days), linked to user

Key: refresh:{user_id}:{device_id}
Value: hashed refresh token
TTL: 7 days
```

**Session invalidation strategies**:
- `DEL` on logout
- `SREM session:user:{user_id} {session_id}` để xóa khỏi index
- Multi-level invalidation: user-level index + session-level key

### 4.7. Leaderboard

**Sorted Set implementation**:

```
Key: leaderboard:{board_id}
Score: numeric score
Member: user_id or user_id:username

ZADD leaderboard:global {score} {user_id}
ZREVRANGE leaderboard:global 0 99 WITHSCORES  -- top 100
ZRANK leaderboard:global {user_id}           -- rank of user (0-indexed)
ZSCORE leaderboard:global {user_id}          -- score of user
ZINCRBY leaderboard:global {delta} {user_id} -- update score atomically
```

**Pagination**:

```lua
-- Page 1 (0-9): offset 0, count 10
ZREVRANGE leaderboard:global 0 9 WITHSCORES

-- Page 2 (10-19): offset 10, count 10
ZREVRANGE leaderboard:global 10 19 WITHSCORES
```

**Tie-breaking**: Khi scores bằng nhau, ZREVRANGE sort theo member name ascending. Để custom tie-breaking (ví dụ: earlier timestamp thắng), encode vào score: `score * 1e10 + (MAX_TS - timestamp)`.

**Multiple leaderboards**:

```
leaderboard:global        -- all-time
leaderboard:weekly:{week} -- weekly reset
leaderboard:daily:{date}  -- daily reset
```

**Near-real-time leaderboard (pub/sub)**:

```
Game server: ZINCRBY on score change
Redis Pub/Sub: Publish update channel
Client: Subscribe, update local state
```

### 4.8. Real-time Counters

**Simple counter**:

```
INCR counter:{metric}:{date}          -- atomic increment
GET counter:{metric}:{date}           -- read current value
EXPIRE counter:{metric}:{date} 90000  -- auto-delete after 25h
```

**HyperLogLog for unique counts**:

```
PFADD hll:dau:{date} {user_id}
PFCOUNT hll:dau:{date}
```

**Sliding window counter (distributed rate limit counter)**:

```
-- Mỗi request: INCR + EXPIRE
INCR rate:{user_id}:{current_minute}
EXPIRE rate:{user_id}:{current_minute} 120

-- Sum last 60 minutes:
SUM(INCR rate:{user_id}:{t} for t in last_60_minutes)
```

### 4.9. Idempotency Key

**Concept**: Client gửi kèm idempotency key (UUID). Server lưu key + response vào Redis. Retry với cùng key -> trả lại cached response.

**Redis implementation**:

```
Key: idempotency:{idempotency_key}
Value: JSON {state, request_hash, response, created_at}
TTL: 24h hoặc dài hơn theo business operation
```

**Lua script (atomic reserve trước khi process)**:

```lua
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local request_hash = ARGV[2]
local now = ARGV[3]

local existing = redis.call('GET', key)
if existing then
    return {0, existing}
end

local marker = cjson.encode({
    state = 'processing',
    request_hash = request_hash,
    created_at = now
})
redis.call('SET', key, marker, 'PX', ttl, 'NX')
return {1, marker}
```

**Pattern cho payment API**:

```
POST /payment
Headers: Idempotency-Key: {uuid}
Body: {amount, currency, ...}

-- Server-side:
key = "idempotency:{idempotency_key}"
reserve = redis.SET(key, processing_marker, NX, PX, 86400000)
if reserve fails:
    return cached response, 409 in_progress, or request_hash_mismatch
process payment exactly once
redis.SET(key, completed_response_json, XX, PX, 86400000)
return response
```

### 4.10. Quota Tracking

**Complex quota: multiple dimensions**:

```
quota:{user_id}:requests:daily       -- max 10000/day
quota:{user_id}:bandwidth:daily      -- max 1GB/day
quota:{user_id}:compute:daily        -- max 100h/day
quota:{user_id}:api_calls:{endpoint} -- per endpoint
```

**Lua script for multi-dimensional quota**:

```lua
local user_id = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local allowed = {}
local reasons = {}

for i, dimension in ipairs({'requests', 'bandwidth', 'compute'}) do
    local key = 'quota:' .. user_id .. ':' .. dimension .. ':daily'
    local limit = tonumber(ARGV[i + 2])
    local used = tonumber(redis.call('GET', key) or '0')
    if used >= limit then
        allowed[dimension] = false
        reasons[dimension] = 'quota_exceeded'
    else
        allowed[dimension] = true
    end
end

return {allowed, reasons}
```

---

## 5. Trade-off Analysis

### 5.1. Fixed Window vs Sliding Window

| Tiêu chí | Fixed Window | Sliding Window |
|---|---|---|
| **Implementation** | `INCR` + `EXPIRE` | Sorted Set + Lua |
| **Memory** | O(1) per user per window | O(window_size) per user |
| **Accuracy** | Có burst ở boundary (2x) | Accurate, no burst |
| **Latency** | ~0.3ms (2 commands) | ~0.5-1ms (Lua script) |
| **Complexity** | Rất đơn giản | Phức tạp hơn |
| **Use case** | Internal API, non-critical | Public API, payment, user-facing |

**Khi nào chọn Fixed Window**:
- Rate limit cho internal services không yêu cầu strict quota
- Memory budget cực kỳ hạn chế
- Chấp nhận được boundary burst (ví dụ: cron jobs run đầu giờ)

**Khi nào chọn Sliding Window**:
- Public-facing API với strict quota
- Payment/billing systems
- Khi boundary burst gây ra business impact

### 5.2. Token Bucket vs Leaky Bucket

| Tiêu chí | Token Bucket | Leaky Bucket |
|---|---|---|
| **Burst** | Cho phép burst = bucket_size | Không burst, output rate cố định |
| **Use case** | API burst allowance, batch processing | Media streaming, sustained rate limiting |
| **Traffic shape** | Spike-friendly | Smooth output |
| **Redis impl** | Lua + Hash state | Lua + Sorted Set queue |
| **Complexity** | Trung bình | Cao |

**Khi nào chọn Token Bucket**:
- Muốn cho phép burst (ví dụ: 100 req burst, sau đó sustain 10 req/s)
- Queue/Batch job rate limiting
- CDN-style rate limiting

**Khi nào chọn Leaky Bucket**:
- Muốn smooth output rate (streaming, video)
- Khi backend không handle burst được
- Priority queue systems

### 5.3. Redis Session vs Stateless JWT

| Tiêu chí | Redis Session | Stateless JWT |
|---|---|---|
| **State** | Server-side state | Client-side, no server state |
| **Revocation** | Immediate (DEL key) | Chỉ khi expire hoặc use blocklist |
| **Scalability** | Cần session store (Redis) | Horizontally scalable, stateless |
| **Latency** | Redis lookup per request (~0.3ms) | Decrypt/verify local (~0.1ms) |
| **Storage** | Redis memory | Client storage |
| **Size** | O(1) per session key | Token size grows with claims |
| **GDPR/Compliance** | Easy to invalidate/delete | Harder to revoke globally |

**Khi nào chọn Redis Session**:
- Cần immediate revocation (logout, fraud detection, password change)
- Cần server-side session data (roles, permissions, session metadata)
- Multi-service environment cần shared session
- Cần session invalidation on server-side event

**Khi nào chọn Stateless JWT**:
- Microservices cần fast auth ở edge (CDN, API Gateway)
- High-scale, stateless services
- Khi revoke không cần immediate (short-lived tokens acceptable)
- Cross-domain SSO

**Hybrid approach phổ biến**:
```
Access token: JWT (15 min, stateless)
Refresh token: Redis-stored (7 days, revocable)
```

### 5.4. Leaderboard Redis vs Database Ranking

| Tiêu chí | Redis Sorted Set | Database (SQL) |
|---|---|---|
| **Write** | O(log N) ZADD | O(log N) INSERT/UPDATE + index |
| **Read top M** | O(log N + M) ZREVRANGE | O(M) with LIMIT + ORDER BY |
| **Read rank** | O(log N) ZRANK | O(N) hoặc O(log N) với window function |
| **Memory** | Redis RAM (1M users ≈ 200MB) | Shared DB storage |
| **Persistence** | AOF/RDB | Built-in ACID |
| **Consistency** | Eventual (async replica) | Strong (transactions) |
| **Real-time** | Native pub/sub, <1ms | Polling hoặc trigger-based |
| **Tie-breaking** | Encode in score | Native with ORDER BY |

**Khi nào chọn Redis Leaderboard**:
- < 10M users (Redis Sorted Set handle tốt)
- Real-time score update cần < 5ms latency
- Frequent ZINCRBY (score update mỗi action)
- Read-heavy (top 100 queried nhiều hơn write)

**Khi nào chọn Database Ranking**:
- > 10M users, sharding required
- Cần full SQL query capability
- Audit/compliance yêu cầu ACID transaction
- Leaderboard là business-critical data (không phải display only)

### 5.5. Redis Idempotency Key vs DB Unique Constraint

| Tiêu chí | Redis Idempotency Key | DB Unique Constraint |
|---|---|---|
| **Atomicity** | Lua script atomic SET NX | DB transaction |
| **Latency** | ~0.5ms | ~5-20ms |
| **TTL** | Native (PX/EXPIRE) | Manual cleanup job |
| **Storage** | Redis RAM | DB disk |
| **Query capability** | Limited (GET only) | Full SQL |
| **Across services** | Shared Redis = easy | Distributed DB = complex |
| **Memory cost** | Per key overhead | Row per key |

**Khi nào chọn Redis Idempotency Key**:
- High-throughput API (100K+ req/s)
- Multi-service idempotency (shared Redis)
- Latency-sensitive operations
- TTL-based auto-cleanup sufficient

**Khi nào chọn DB Unique Constraint**:
- Cần audit trail
- Idempotency data cần persistent (business requirement)
- Transaction-level consistency required
- Multiple idempotency dimensions (composite key)

---

## 6. Best Solution & Best Practices

### Recommended Rate Limiting Stack

**Public API** (API Gateway layer):
- **Algorithm**: Sliding Window
- **Scope**: Per user + per endpoint + per IP
- **Implementation**: Lua script in Redis, called from API Gateway
- **Configuration**:
  ```
  endpoint:/api/users    -> 1000 req/min per user
  endpoint:/api/search   -> 100 req/min per user
  endpoint:/api/export   -> 10 req/min per user
  IP-wide               -> 10000 req/min all endpoints
  ```

**Payment/Financial API**:
- **Algorithm**: Token Bucket (per operation) + Sliding Window (per time)
- **Scope**: Per user per operation type
- **Additional**: Idempotency key bắt buộc, stored 24h in Redis

**Internal Service-to-Service**:
- **Algorithm**: Fixed Window (simple, fast)
- **Scope**: Per service (from service token)
- **Reason**: Boundary burst không gây business impact

### Recommended Session Architecture

```
┌─────────────────────────────────────────────────────┐
│  JWT Access Token (15 min, stateless)               │
│  Contains: user_id, roles[], exp                    │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│  Redis Session Store                                │
│  Key: session:{session_id}                          │
│  TTL: 24h (sliding)                                │
│  Contains: full profile, device info, permissions   │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│  Refresh Token (7 days, Redis)                      │
│  Key: refresh:{user_id}:{device_id}                 │
│  Value: hashed token, TTL: 7 days                   │
└─────────────────────────────────────────────────────┘
```

**Session invalidation rules**:
- Password change -> invalidate all user sessions (DEL pattern `session:user:{uid}:*`)
- Fraud detection -> immediate DEL session:{session_id}
- Admin action -> DEL session + notify via push

### Recommended Leaderboard Architecture

```
ZADD leaderboard:{board_id} {score} {member}
ZRANK leaderboard:{board_id} {member}   -- user's rank
ZREVRANGE leaderboard:{board_id} 0 99 WITHSCORES  -- top 100
ZSCORE leaderboard:{board_id} {member}  -- user's score

-- Daily reset:
RENAME leaderboard:weekly:{wN} leaderboard:weekly:{wN}:frozen
DEL leaderboard:weekly:{wN}  -- start fresh
```

**Hot key mitigation for leaderboard**:
- Read from replica (eventual consistent)
- Local in-memory cache with 1s TTL (for top N display)
- Sharded leaderboard: `leaderboard:{board_id}:{shard_id}` (by user_id % N shards)

---

## 7. Performance Considerations

### Rate Limiting

| Algorithm | Redis Operations | Latency (p50) | Latency (p99) | Memory/User |
|---|---|---|---|---|
| Fixed Window | INCR + EXPIRE (first) | 0.2ms | 0.5ms | ~50 bytes |
| Sliding Window (Lua) | 1 Lua script | 0.4ms | 1.0ms | ~200 bytes |
| Token Bucket (Lua) | 1 Lua script | 0.5ms | 1.2ms | ~80 bytes |
| Leaky Bucket (Lua) | 1 Lua script | 0.6ms | 1.5ms | ~500 bytes |

**Lua script overhead**: Mỗi Lua script add ~0.1-0.3ms overhead so với raw commands. Nhưng trade-off đáng giá vì atomicity.

**Throughput**: Single Redis node handle ~150K-200K rate limit checks/s (Lua script). Nếu cần hơn, dùng Redis Cluster với hash tags.

### Session Store

| Operation | Latency (p50) | Latency (p99) | Memory |
|---|---|---|---|
| HSET (create) | 0.2ms | 0.4ms | ~500 bytes/session |
| HGETALL (read) | 0.2ms | 0.4ms | — |
| EXPIRE (refresh) | 0.1ms | 0.2ms | — |
| DEL (logout) | 0.1ms | 0.2ms | — |

**Memory estimate**: 1 triệu sessions × 500 bytes = ~500MB. Manageable on 1-2GB Redis instance.

**TTL refresh strategy**: Lazy refresh (EXPIRE on read) vs proactive refresh (background job). Lazy refresh đơn giản và đủ hiệu quả.

### Leaderboard

| Operation | Complexity | Latency (p50) | Latency (p99) |
|---|---|---|---|
| ZADD | O(log N) | 0.15ms | 0.3ms |
| ZINCRBY | O(log N) | 0.15ms | 0.3ms |
| ZREVRANGE 100 | O(log N + 100) | 0.5ms | 1.0ms |
| ZRANK | O(log N) | 0.2ms | 0.4ms |
| ZSCORE | O(1) | 0.1ms | 0.2ms |

**Sorted Set memory**: 1M members × (member_name + score + overhead) ≈ 150-250MB. Để dự phòng, estimate 500MB per leaderboard với 1M users.

**Scaling leaderboard**: Shard by `user_id % 16` → mỗi shard ~62K users, operations nhanh hơn, hot key chia thành 16 keys.

### Idempotency Key

| Operation | Latency (p50) | Latency (p99) | Memory |
|---|---|---|---|
| GET (cache hit) | 0.15ms | 0.3ms | ~200 bytes/key |
| SET NX PX (miss) | 0.2ms | 0.4ms | ~200 bytes/key |
| DEL (manual cleanup) | 0.1ms | 0.2ms | — |

**TTL recommendation**: 24h minimum, 7 days for payment APIs. Key size: idempotency key UUID = 36 bytes. Value = response JSON (50-5000 bytes depending on operation).

---

## 8. Production Failure Modes

### Failure Mode 1: Rate Limiter Bypass — Redis Down

**Dấu hiệu**: Request count tăng vọt, backend CPU 100%, không có rate limit response trong logs.

**Nguyên nhân**: Rate limiter graceful degradation sai cách — khi Redis unavailable, dev set flag "rate limit passed" thay vì "rate limit failed -> reject".

**Phòng tránh**:
```go
// ANTI-PATTERN (DO NOT USE)
if redis.Err() {
    allowRequest() // BUG: bypasses rate limit
}

// CORRECT: fail closed (secure by default)
if redis.Err() {
    rejectRequest("rate_limiter_unavailable")
}
```

### Failure Mode 2: Session Store Memory Exhaustion

**Dấu hiệu**: Redis OOM, evicted keys spike, user đột nhiên logged out.

**Nguyên nhân**: Không có maxmemory policy hoặc session TTL không được set. Mỗi login tạo session mới mà không delete session cũ.

**Phòng tránh**:
- Always set TTL on session keys
- Monitor `evicted_keys` metric
- Implement session cleanup job
- Set `maxmemory` và `maxmemory-policy = allkeys-lru` như safety net

### Failure Mode 3: Leaderboard Stale Read

**Dấu hiệu**: Leaderboard hiển thị sai rank, user phàn nàn "tôi xếp hạng cao hơn mà không hiển thị".

**Nguyên nhân**: Read từ replica có replica lag (50-500ms), trong khi write đi vào primary. Khi có 500 người đồng thời update score, replica lag có thể lên đến 1-2s.

**Phòng tránh**:
- Read top-N leaderboard từ primary (critical display)
- Dùng eventual-consistent read cho non-critical display
- Monitor `replication lag` metric
- Alert khi lag > 500ms

### Failure Mode 4: Idempotency Key Collision

**Dấu hiệu**: Same idempotency key được gửi từ 2 different devices cùng user.

**Nguyên nhân**: Idempotency key không include client identifier. 2 devices submit payment với cùng key.

**Phòng tránh**:
```
idempotency_key = SHA256(user_id + operation_id + client_id + timestamp_bucket)
```
Hoặc dùng: `{user_id}:{operation}:{client_id}:{request_hash}`

### Failure Mode 5: Rate Limit Counter Overflow

**Dấu hiệu**: Rate limit không hoạt động sau vài ngày, all requests allowed.

**Nguyên nhân**: Counter dùng String (INCR) overflow 64-bit (max: 2^63-1 ≈ 9.2 × 10^18). Unlikely nhưng possible trong high-volume counters.

**Phòng tránh**: Dùng sliding window counter thay vì INCR-based counter cho long-running windows. Reset counter periodic bằng `RENAME` + `DEL`.

---

## 9. Real-world Examples

### GitHub API Rate Limiting

GitHub dùng fixed window (5000 req/giờ cho authenticated, 60 req/giờ cho unauthenticated). Khi exceed, trả về `X-RateLimit-Remaining: 0` và `Retry-After` header. Đặc biệt: GitHub không dùng pure fixed window mà có "patience window" — response vẫn trả về nhưng có `RFC 6585 429 Too Many Requests` status.

### Twitter/X Rate Limiting

Twitter dùng sliding window rate limit. Mỗi request trả về `X-Rate-Limit-Remaining` và `X-Rate-Limit-Reset` (epoch seconds). Rate limit tiers: 15-min window và 24h window. User-level và app-level rate limits khác nhau.

### Shopify: Session Store for Multi-store

Shopify dùng Redis cho session storage với sliding TTL refresh. Mỗi store có isolated session namespace. Khi merchant logout, session được revoke ngay lập tức — critical cho security.

### Discord: Real-time Leaderboard

Discord dùng Sorted Set cho activity leaderboards (server XP, voice activity). Leaderboard được partition theo server (guild). Updates được batched mỗi 5 phút thay vì real-time để giảm Redis load. Pub/sub channel notify clients khi leaderboard refresh.

### Stripe: Idempotency Key

Stripe yêu cầu idempotency key bắt buộc cho tất cả payment operations. Key TTL = 24h. Retry với same key trả về cached response. Stripe ghi log: "Idempotent replay of request X" khi key match. Đây là gold standard cho payment idempotency.

---

## 10. Common Pitfalls

### Pitfall 1: Dùng INCR mà không EXPIRE trên first request

```go
// BUG: Counter never expires -> memory leak
count := redis.Incr("ratelimit:user:1")
if count > 1000 {
    reject()
}

// FIX: EXPIRE only when count == 1
count := redis.Incr(key)
if count == 1 {
    redis.Expire(key, 60)  // set TTL only on first request
}
```

### Pitfall 2: Token Bucket dùng application time thay vì Redis time

```lua
-- BUG: Vulnerable to clock skew across app servers
local now = tonumber(ARGV[1])  -- passed from application

-- FIX: Use Redis TIME
local now = redis.call('TIME')
now = tonumber(now[1]) + tonumber(now[2]) / 1000000
```

### Pitfall 3: Session không refresh TTL trên mỗi access

```go
// BUG: Session expires while user is active
session := redis.HGetAll("session:" + sessionID)
// user is still using app...
// but TTL never refreshed -> session expires -> user logged out unexpectedly

// FIX: Refresh TTL on every access
session := redis.HGetAll("session:" + sessionID)
redis.Expire("session:"+sessionID, 86400) // refresh 24h
```

### Pitfall 4: Leaderboard không handle tie-breaking

```go
// BUG: Same score = undefined order
scores, _ := redis.ZRevRangeWithScores("leaderboard", 0, 9).Result()
// 2 users with score 1000: order is arbitrary

// FIX: Encode tie-breaker in score
// score = score * 1e10 + (max_timestamp - timestamp)
finalScore := float64(score*1e10) + float64(maxTS-timestamp)
redis.ZAdd("leaderboard", &redis.Z{Score: finalScore, Member: member})
```

### Pitfall 5: Idempotency key không include TTL cho long operations

```go
// BUG: SET NX without TTL -> key lives forever on success
redis.SetNX(ctx, "idempotency:"+key, responseJSON, 0)  // 0 = no TTL

// FIX: TTL >= operation duration
redis.SetNX(ctx, "idempotency:"+key, responseJSON, 24*time.Hour)
```

### Pitfall 6: Rate limit key không include tenant identifier

```go
// BUG: Cross-tenant rate limit bypass
key := "ratelimit:" + userID  // but what if 2 tenants have same userID?

// FIX: Include tenant in key
key := fmt.Sprintf("ratelimit:%s:%s", tenantID, userID)
```

---

## 11. Câu hỏi tự kiểm tra

### Câu 1
Một API endpoint có rate limit 1000 req/min per user. Nếu dùng fixed window, user có thể gửi bao nhiêu requests trong 2 giây tại boundary của 2 window liên tiếp? Giải thích tại sao sliding window giải quyết được vấn đề này.

### Câu 2
Bạn cần implement rate limiting cho payment API: 100 transactions/giờ per user, mỗi transaction idempotent. Thiết kế key structure và Lua script cho cả rate limiting và idempotency. Đảm bảo atomic operation cho cả 2.

### Câu 3
So sánh token bucket và leaky bucket về traffic shaping. Cho ví dụ use case cụ thể cho mỗi loại.

### Câu 4
Một game có 5 triệu người chơi, leaderboard global với real-time score update. Redis Sorted Set single key đã đủ chưa? Nếu chưa, đề xuất solution. Nếu đủ, giải thích tại sao.

### Câu 5
Khi nào nên dùng Redis session store thay vì stateless JWT? Nêu 3 scenario cụ thể và giải thích trade-off trong mỗi scenario.

### Câu 6
Design một quota tracking system: user có 3 loại quota (API calls/day, bandwidth/day, compute hours/day). Mỗi quota có limit khác nhau. Khi 1 quota hết, request bị reject. Dùng Redis, thiết kế key structure và Lua script để check tất cả 3 quotas trong 1 atomic operation.

### Câu 7
Explain failure mode khi rate limiter Redis bị failover. App server nên behavior như thế nào khi Redis unavailable? Khi nào "fail open" (allow all) có thể chấp nhận được và khi nào không?

---

### Đáp án

**Câu 1**: 2000 requests trong 2 giây tại boundary (1000 cuối window 1 + 1000 đầu window 2). Sliding window giải quyết bằng cách tính quota dựa trên `(now - window_size, now]` thay vì cửa sổ cố định — không có "reset" moment.

**Câu 2**:
```
Keys:
  ratelimit:{user_id}:{window}   -- rate limit
  idempotency:{idempotency_key}   -- idempotency

Lua script:
  1. Check idempotency key -> if exists, return cached response
  2. Check rate limit counter -> if exceeded, return 429
  3. Reserve idempotency key bằng SET processing NX PX
  4. Process transaction ngoài Redis
  5. SET completed response XX PX 86400000 (24h) rồi return response
```

**Câu 3**: Token bucket cho phép burst (bucket chứa tokens sẵn) — phù hợp CDN burst allowance, batch job. Leaky bucket smooth output rate cố định — phù hợp video streaming, API với backend không handle burst.

**Câu 4**: Chưa đủ vì single hot key với 5M members. Solution: shard leaderboard thành 16-64 shards bằng `user_id % shard_count`. Mỗi shard ~78K-312K members. Top-N global = merge top-N từ mỗi shard.

**Câu 5**:
1. Fraud detection: cần revoke session ngay lập tức khi phát hiện fraud — JWT không revoke được.
2. Password change: cần invalidate tất cả sessions — Redis DEL nhanh, JWT phải dùng blocklist hoặc đợi expire.
3. Multi-service auth: session data cần shared giữa microservices — JWT stateless nhưng mỗi service phải decode và cache roles.

**Câu 6**:
```lua
-- Keys[1] = user_id
-- ARGV[1] = current timestamp
local api_calls_key = 'quota:' .. KEYS[1] .. ':api_calls:daily'
local bandwidth_key = 'quota:' .. KEYS[1] .. ':bandwidth:daily'
local compute_key = 'quota:' .. KEYS[1] .. ':compute:daily'
local api_limit = tonumber(ARGV[2])
local bandwidth_limit = tonumber(ARGV[3])
local compute_limit = tonumber(ARGV[4])
local bandwidth_used = tonumber(ARGV[5])
local compute_used = tonumber(ARGV[6])

local api = tonumber(redis.call('GET', api_calls_key) or '0')
if api >= api_limit then return {0, 'api_quota_exceeded'} end

-- Similar for bandwidth and compute
redis.call('INCR', api_calls_key)
if api == 0 then redis.call('EXPIRE', api_calls_key, 90000) end
return {1, 'allowed'}
```

**Câu 7**: Failover behavior:
- **Không bao giờ fail open** cho payment, authentication, rate-limited public APIs — security risk.
- **Có thể fail open** cho internal non-critical services, caching layers — trade availability vs accuracy.
- Best practice: fail closed với error code rõ ràng + metric để alert + automatic recovery khi Redis back.
- Rate limiter unavailable → trả 503 Service Unavailable (không phải 429 vì 429 imply rate limit đang hoạt động).
