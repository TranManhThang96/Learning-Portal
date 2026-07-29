# Day 25: Caching Patterns & Consistency

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Mô tả được 5 caching pattern chính: cache-aside, read-through, write-through, write-behind, refresh-ahead — biết khi nào dùng, khi nào không.
- Phân tích được consistency model của từng pattern và ảnh hưởng lên p95/p99 latency cũng như data correctness trong production.
- So sánh được 5 cặp trade-off: cache-aside vs read-through, write-through vs write-behind, consistency vs latency, stale data vs DB overload, TTL-based vs event-based invalidation.
- Triển khai được negative caching an toàn, cache warming strategy, và stale data handling cho hệ thống production.
- Thiết kế được consistency strategy cho order service với các trade-off cụ thể về throughput, memory, và availability.

---

## 2. Vì sao cần học chủ đề này

### Scenario production giả lập 1: Payment Pricing — Stale Cache Khiến Users Bị Charge Sai Số Tiền

Một payment platform dùng Redis làm cache trước PostgreSQL cho pricing configuration. Một ngày nọ, pricing team update discount rate từ 10% lên 15%. Cache TTL = 1 giờ. Trong 58 phút tiếp theo, users được charge với discount rate 10% thay vì 15% — hệ thống undercharge hàng triệu dollars trước khi incident được phát hiện.

Root cause: Cache không được invalidated khi pricing config thay đổi. Team update database nhưng không gọi `DEL` hoặc `EXPIRE` trên cache key.

Bài học: **Cache invalidation là hardest problem in computer science** (theo Phil Karlton). TTL không đủ — bạn cần event-based invalidation khi data thay đổi ngoài band.

### Scenario production giả lập 2: Product Page — Cache Stampede Black Friday

Một e-commerce platform dùng read-through cache cho product catalog. Black Friday, một sản phẩm bestseller hết cache (TTL expired). 10.000 requests đồng thời nhận cache miss — tất cả đổ vào database cùng một lúc. Database overload → 2 phút downtime → estimated revenue loss: $1M/minute.

Root cause: Cache stampede — thundering herd effect. Khi hot key expired, tất cả concurrent requests đều miss cache và query database cùng lúc.

Bài học: **Cache warming**, probabilistic early expiration, và request coalescing là bắt buộc cho hot data. Không chỉ cần caching pattern, mà còn cần chiến lược refresh.

### Scenario production giả lập 3: CI Platform — Negative Caching Bug Gây Rate Limit Sai

Một CI platform dùng Redis để track rate limit counters. Một service bị bug trả về "user not found" (404) cho mọi request từ một IP range. Response này không được cache (vì developer nghĩ 404 là error, không cache). Nhưng downstream service đọc từ Redis: `GET rate_limit:{ip}` → nil → coi là "no limit applied" → bypass rate limit hoàn toàn. Attacker exploit để bypass rate limit, brute-force credentials.

Root cause: **Negative caching** không được implement. "Not found" không khác gì "has no limit" trong application logic.

Bài học: Negative caching (cache null/404 responses) là **bắt buộc** cho existence-check patterns. Không chỉ cache data, mà còn cache absence.

### Bottom Line

Caching không phải chỉ là "đọc từ Redis trước khi đọc từ DB". Sai một bước trong pattern hoặc invalidation strategy → data inconsistency, cache stampede, hoặc security vulnerability. Đây là bài học mà nhiều senior engineer vẫn mắc khi thiết kế cache layer lần đầu cho production system.

---

## 3. Kiến thức nền cần có

- **Day 8 Memory Management & Eviction**: TTL, eviction policies, lazy expiration. Bạn phải hiểu `EXPIRE` không xóa key ngay mà chỉ đánh dấu.
- **Day 11 Pipelining & Batching**: pipelining giúp giảm RTT khi populate cache sau miss. Bạn sẽ dùng pipelining để warm cache hiệu quả.
- **Day 14 Hot Key & Big Key**: cache stampede thường xảy ra ở hot keys. Bạn phải hiểu tại sao single key expiration gây ra hàng nghìn DB queries đồng thời.
- **Day 15 Transactions & WATCH**: optimistic locking không giải quyết được stale cache. Bạn cần hiểu khi nào WATCH đủ và khi nào cần distributed lock.

---

## 4. Lý thuyết chi tiết

### 4.1. Five Caching Patterns — Tổng Quan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FIVE CACHING PATTERNS OVERVIEW                           │
│                                                                             │
│  Pattern         Read Flow                Write Flow                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Cache-Aside     App checks cache         App writes DB, then invalidates  │
│                  → miss → read DB         cache                             │
│                                                                             │
│  Read-Through    App always reads cache   App writes DB only               │
│                  Cache auto-loads from     (cache updated on next read)     │
│                  DB on miss                                                 │
│                                                                             │
│  Write-Through   App writes to cache      App writes cache → sync to DB   │
│                  Cache syncs to DB                  (synchronous)          │
│                                                                             │
│  Write-Behind    App writes to cache      App writes cache → async to DB  │
│                  Cache async to DB                  (async, buffered)      │
│                                                                             │
│  Refresh-Ahead   Cache proactively        Same as base pattern             │
│                  refreshes before TTL     + background refresh on TTL-X   │
│                  expires                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Cache-Aside (Lazy Loading)

**Cache-aside** = application tự quản lý cache. Application code kiểm tra cache trước mỗi read, và update/invalidate cache sau mỗi write. Cache không biết gì về database.

```
Read Flow:
  Client ──GET cache──▶ Redis
                    │
                    ├── HIT  ──return value──▶ Client
                    │
                    └── MISS ──GET db──▶ MySQL/PostgreSQL
                              │
                              ├── Store in Redis (SETEX)
                              └── Return value ──▶ Client

Write Flow:
  Client ──UPDATE db──▶ MySQL/PostgreSQL
          │
          └── DEL cache ──▶ Redis  (invalidate, not update)
```

**Khi nào dùng**: Most common pattern. Phù hợp khi:
- Application có nhiều read, ít write (read-heavy workload)
- Data không cần real-time (stale data < TTL acceptable)
- Bạn muốn full control over cache lifecycle
- Multiple services truy cập cùng data (cache là shared layer)

**Code mẫu cache-aside read**:
```go
func GetUser(ctx context.Context, rdb *redis.Client, db *sql.DB, userID int64) (*User, error) {
    // Step 1: Check cache
    cacheKey := fmt.Sprintf("user:%d", userID)
    cached, err := rdb.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var user User
        if json.Unmarshal(cached, &user) == nil {
            return &user, nil
        }
    }
    if err != nil && !errors.Is(err, redis.Nil) {
        // Log Redis error, but fall through to DB
        log.Printf("Redis GET error: %v", err)
    }

    // Step 2: Cache miss — read from DB
    user, err := fetchUserFromDB(db, userID)
    if err != nil {
        return nil, err
    }

    // Step 3: Populate cache asynchronously (don't block response)
    go func() {
        data, _ := json.Marshal(user)
        // TTL = 5 min, with jitter to avoid stampede
        jitter := time.Duration(rand.Intn(30)) * time.Second
        rdb.Set(ctx, cacheKey, data, 5*time.Minute+jitter)
    }()

    return user, nil
}
```

**Code mẫu cache-aside write**:
```go
func UpdateUser(ctx context.Context, rdb *redis.Client, db *sql.DB, user *User) error {
    // Step 1: Update DB first (source of truth)
    if err := updateUserInDB(db, user); err != nil {
        return err
    }

    // Step 2: Invalidate cache (NOT update)
    // Why NOT update? Because update can race with concurrent reads
    // Invalidation: next read will repopulate with fresh data
    cacheKey := fmt.Sprintf("user:%d", user.ID)
    if err := rdb.Del(ctx, cacheKey).Err(); err != nil {
        log.Printf("Cache invalidation failed for %s: %v", cacheKey, err)
        // DON'T return error — DB write succeeded, cache will be stale
        // Next read will fix it via TTL or cache-aside logic
    }

    return nil
}
```

### 4.3. Read-Through

**Read-through** = cache layer tự động load data từ database khi miss xảy ra. Application chỉ nói chuyện với cache, không bao giờ đọc trực tiếp từ DB.

```
Read Flow:
  Client ──GET──▶ Cache Layer
                  │
                  ├── HIT: return value
                  │
                  └── MISS: Cache fetches from DB
                             ↓
                             Cache stores + returns to Client
```

**Đặc điểm**:
- Application logic đơn giản hơn (không cần check cache rồi DB)
- Cache chịu trách nhiệm load data khi miss
- Cần cache implementation đặc biệt (thường dùng cache library như Caffeine, Guava Cache, or Redis with Lua wrapper)
- Kém linh hoạt hơn cache-aside (cache và app tightly coupled)

**So sánh với cache-aside**:

| Aspect | Cache-Aside | Read-Through |
|---|---|---|
| **Cache location** | Application manages | Cache manages |
| **DB access** | Application decides | Cache triggers |
| **Code complexity** | Higher (2 code paths) | Lower (1 code path) |
| **Cache miss handling** | Explicit in app | Transparent in cache |
| **Flexibility** | High (custom logic per key) | Low (cache library fixed) |
| **Testability** | High (mock DB or cache) | Lower (need cache lib) |

**Use case phù hợp**: Khi bạn dùng một cache library có built-in read-through (ví dụ Spring Cache với `@Cacheable`, Hibernate second-level cache). Không phù hợp khi bạn cần fine-grained control hoặc khi cache và DB có different update patterns.

### 4.4. Write-Through

**Write-through** = mỗi write đi qua cache trước, rồi đồng bộ xuống database. Cache là bộ đệm ghi, không chỉ đọc.

```
Write Flow:
  Client ──SET──▶ Redis (sync) ──INSERT/UPDATE──▶ MySQL
                       │
                       └── Return OK only after DB confirms

Read Flow:
  Client ──GET──▶ Redis (always fresh, because written through)
```

**Đặc điểm**:
- Cache luôn đồng nhất với DB (strong consistency)
- Write latency cao hơn (2 round trips: cache + DB, both synchronous)
- Không có cache miss cho writes (data luôn có trong cache sau write)
- Phù hợp cho: write-heavy workload, cần read-after-write consistency

**Anti-pattern phổ biến**: Write-through không có write buffer → mỗi write tạo ra DB write ngay lập tức → DB write amplification (10.000 writes/sec → 10.000 DB writes/sec). Không có benefit của batching.

### 4.5. Write-Behind (Write-Back)

**Write-behind** = application write vào cache (immediate), cache batch/window rồi async flush xuống DB.

```
Write Flow:
  Client ──SET──▶ Redis (immediate return)
                       │
                       └── Background writer: batch → flush to DB every N seconds

Read Flow:
  Client ──GET──▶ Redis (may have unflushed writes)
```

**Đặc điểm**:
- Write latency cực thấp (chỉ Redis RTT)
- DB write được batched/buffered → throughput cao hơn
- Risk: data loss nếu Redis crash trước khi flush
- Phù hợp: write-heavy, can tolerate small data loss window

**Khi nào an toàn dùng write-behind**:
- Data có tính idempotent (write duplicate không gây vấn đề)
- Event/analytics data (tolerable loss)
- Counter/aggregation (small error acceptable)
- **Không bao giờ dùng cho**: financial transactions, inventory, user-facing mutations

**Code mẫu write-behind với Redis LIST**:
```go
// Write-behind: append to Redis list, background worker flushes to DB
func WriteOrderAsync(ctx context.Context, rdb *redis.Client, order *Order) error {
    data, _ := json.Marshal(order)
    // LPUSH to write buffer (O(1))
    if err := rdb.LPush(ctx, "write_buffer:orders", data).Err(); err != nil {
        return err
    }
    // Return immediately — DB write deferred
    return nil
}

// Background worker (runs every 5 seconds)
func flushToDB(ctx context.Context, rdb *redis.Client, db *sql.DB) {
    for {
        // RPOP in batches (oldest first)
        var orders []Order
        for i := 0; i < 100; i++ {
            data, err := rdb.RPop(ctx, "write_buffer:orders").Bytes()
            if errors.Is(err, redis.Nil) {
                break
            }
            if err != nil {
                log.Printf("RPop error: %v", err)
                break
            }
            var order Order
            if json.Unmarshal(data, &order) == nil {
                orders = append(orders, order)
            }
        }
        if len(orders) > 0 {
            // Batch INSERT to DB
            batchInsertOrders(db, orders)
            log.Printf("Flushed %d orders to DB", len(orders))
        }
        time.Sleep(5 * time.Second)
    }
}
```

### 4.6. Refresh-Ahead (Proactive Refresh)

**Refresh-ahead** = cache tự động refresh trước khi TTL expires. Goal: eliminate cache miss hoàn toàn cho hot data.

```
Timeline:
  T=0:         Cache populated, TTL = 60s
  T=50s:       TTL = 10s remaining
  T=50s:       Background refresh triggered → cache repopulated, TTL reset to 60s
  T=110s:      Next refresh at T=50+50 = 100s? No — at T=50+50*0.8 = 90s
  Result:      No cache miss, p99 latency stays low
```

**Cơ chế**: Application theo dõi TTL, hoặc dùng scheduler/background job để refresh hot keys trước khi chúng expire.

**Khi nào dùng**:
- Hot keys với predictable access pattern
- Data freshness requirement < 100% (stale-while-revalidate acceptable)
- Không dùng cho: data thay đổi không predictable

**Code mẫu refresh-ahead với Lua**:
```lua
-- Probabilistic early expiration (XFetch algorithm)
-- Key: user:{id}, TTL remaining checked on each access
-- If TTL remaining < expected TTL * refresh_threshold → refresh

local key = KEYS[1]
local refresh_threshold = 0.8  -- refresh when 80% of TTL elapsed

local data = redis.call('GET', key)
if not data then
    return nil
end

local ttl = redis.call('TTL', key)
local original_ttl = tonumber(ARGV[1])
local refresh_ttl = math.floor(original_ttl * refresh_threshold)

if ttl > 0 and ttl < refresh_ttl then
    -- Background refresh: spawn async load (in real impl, use Redis UNLINK + trigger)
    -- Here we just return current data and signal "needs refresh"
    return {data, 1}  -- 1 = "refresh recommended"
end

return {data, 0}  -- 0 = "cache fresh"
```

### 4.7. Cache Invalidation — Chiến Lược Thực Tế

Cache invalidation có 3 chiến lược chính:

```
┌─────────────────────────────────────────────────────────────┐
│  STRATEGY 1: TTL-based (Time-based)                        │
│  Cache tự hết hạn sau N giây                               │
│  PRO: Simple, no extra infrastructure                       │
│  CON: Stale data between updates and expiry                 │
│  Best for: Data with predictable freshness window           │
├─────────────────────────────────────────────────────────────┤
│  STRATEGY 2: Event-based (Event-driven)                    │
│  Write event → invalidate cache key                        │
│  PRO: Invalidation near-real-time                          │
│  CON: Needs pub/sub or message queue infrastructure        │
│  Best for: Critical data, must be consistent immediately   │
├─────────────────────────────────────────────────────────────┤
│  STRATEGY 3: Hybrid (TTL + Event)                          │
│  Event invalidates immediately + TTL as safety net          │
│  PRO: Fast + safe (TTL catches missed events)             │
│  CON: More complex implementation                          │
│  Best for: Most production systems (recommended)           │
└─────────────────────────────────────────────────────────────┘
```

**Event-based invalidation với Redis Pub/Sub**:
```go
// Publisher: invalidate cache on data change
func InvalidateCacheOnWrite(ctx context.Context, rdb *redis.Client, event *CacheInvalidationEvent) error {
    // Step 1: Invalidate in Redis directly (for same-service cache)
    cacheKey := fmt.Sprintf("user:%d", event.UserID)
    rdb.Del(ctx, cacheKey)

    // Step 2: Publish event to other services
    eventData, _ := json.Marshal(event)
    rdb.Publish(ctx, "cache_invalidation", eventData)

    return nil
}

// Subscriber: listen and invalidate shared cache
func StartCacheInvalidationSubscriber(ctx context.Context, rdb *redis.Client) {
    pubsub := rdb.Subscribe(ctx, "cache_invalidation")
    defer pubsub.Close()

    for msg := range pubsub.Channel() {
        var event CacheInvalidationEvent
        if json.Unmarshal([]byte(msg.Payload), &event) == nil {
            cacheKey := fmt.Sprintf("user:%d", event.UserID)
            rdb.Del(ctx, cacheKey)
            log.Printf("Invalidated cache for %s via event", cacheKey)
        }
    }
}
```

### 4.8. Negative Caching

**Negative caching** = cache kết quả "not found" (nil/null) với TTL ngắn. Mục đích: tránh repeated DB query cho data không tồn tại.

```
Without negative caching:
  Request 1: GET user:9999 → MISS → DB query (SELECT * FROM users WHERE id=9999) → 5ms
  Request 2: GET user:9999 → MISS → DB query (SELECT * FROM users WHERE id=9999) → 5ms
  ... (1000 requests for non-existent user)
  Total: 5000ms DB time, 1000 DB queries

With negative caching (TTL=60s):
  Request 1: GET user:9999 → MISS → DB query → result: not found
             SET user:9999:null "1" EX 60
  Request 2: GET user:9999 → HIT (cached null) → 0.1ms
  ... (1000 requests for non-existent user)
  Total: 5ms DB time, 1 DB query
```

**CẢNH BÁO**: Negative caching phải dùng key riêng cho null (vd: `user:9999:null`), không dùng `SET user:9999 ""` vì empty string khác với "not found". Hoặc dùng sentinel value (ví dụ: `"__NULL__"`).

**Security pitfall**: Negative cache poison — attacker có thể flood negative cache entries để exhaust memory (với `maxmemory` policy). Fix: negative cache TTL rất ngắn (30-60s), monitor `evicted_keys` metric.

### 4.9. Cache Warming

**Cache warming** = pre-populate cache trước khi traffic đến. Mục đích: eliminate cold start cache misses khi Redis restart hoặc khi deploy new service.

```
Scenario: Redis restart (AOF/RDB restore)
  T=0:    Redis starts, cache empty
  T=1s:   Traffic arrives → mass cache miss → DB overload
  T=60s:  Cache gradually populated, DB stabilizes

With cache warming:
  T=0:    Redis starts, cache empty
  T=0-5s: Warm-up job runs: fetch hot keys from DB → populate cache
  T=5s:   Cache warm, traffic arrives → no cache miss storm
```

**Chiến lược warming**:

1. **Startup warming**: Khi service start, chạy job đọc top-N keys từ DB và populate cache.
2. **Scheduled warming**: Chạy warming job mỗi 5-10 phút để repopulate hot keys.
3. **On-demand warming**: Khi cache miss xảy ra, populate cache nhưng đồng thời schedule background refresh cho các keys liên quan (prefetch).

**Code mẫu cache warming**:
```go
// WarmCache reads top 1000 most-accessed users and populates cache
func WarmUserCache(ctx context.Context, rdb *redis.Client, db *sql.DB) error {
    rows, err := db.QueryContext(ctx, `
        SELECT id, name, email FROM users
        ORDER BY last_login DESC
        LIMIT 1000
    `)
    if err != nil {
        return fmt.Errorf("warmup query failed: %w", err)
    }
    defer rows.Close()

    pipe := rdb.Pipeline()
    count := 0

    for rows.Next() {
        var user User
        if err := rows.Scan(&user.ID, &user.Name, &user.Email); err != nil {
            continue
        }
        data, _ := json.Marshal(user)
        cacheKey := fmt.Sprintf("user:%d", user.ID)
        pipe.Set(ctx, cacheKey, data, 10*time.Minute)  // Longer TTL for warmed keys
        count++

        // Execute pipeline every 100 items to avoid memory bloat
        if count%100 == 0 {
            if _, err := pipe.Exec(ctx); err != nil {
                log.Printf("Warmup pipeline error: %v", err)
            }
            pipe = rdb.Pipeline()
        }
    }

    if _, err := pipe.Exec(ctx); err != nil {
        return fmt.Errorf("warmup final pipeline: %w", err)
    }

    log.Printf("Cache warmed with %d users", count)
    return nil
}
```

### 4.10. Consistency Model

Cache consistency có 4 levels:

```
┌─────────────────────────────────────────────────────────────────┐
│  STRONG CONSISTENCY                                             │
│  Cache = DB always                                              │
│  Achieved by: Write-through (sync write) + no read from replica  │
│  Latency: Highest (write latency = cache RTT + DB RTT)          │
│  Use case: Financial ledgers, inventory counts                  │
├─────────────────────────────────────────────────────────────────┤
│  EVENTUAL CONSISTENCY (cache-aside)                             │
│  Cache may lag DB by up to TTL                                  │
│  Achieved by: Write invalidation + TTL                          │
│  Latency: Lowest reads (cache hit), medium writes               │
│  Use case: Most web applications, social feeds, catalogs        │
├─────────────────────────────────────────────────────────────────┤
│  CAUSAL CONSISTENCY                                             │
│  If A wrote X, subsequent reads by A see X                      │
│  Achieved by: Per-session sticky cache or read-your-writes       │
│  Latency: Medium                                                │
│  Use case: User sessions, shopping carts                        │
├─────────────────────────────────────────────────────────────────┤
│  STALE-WHILE-REVALIDATE                                         │
│  Return stale data, repopulate cache in background              │
│  Achieved by: TTL + async refresh                               │
│  Latency: Always low (serve stale, refresh async)               │
│  Use case: Analytics dashboards, leaderboards                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### Cache-Aside vs Read-Through

| Aspect | Cache-Aside | Read-Through |
|---|---|---|
| **Code complexity** | Higher (explicit cache + DB logic) | Lower (cache manages loading) |
| **Control** | Full control over cache lifecycle | Limited (cache library controls) |
| **Cache miss handling** | Application decides behavior | Cache library decides behavior |
| **Debugging** | Easier (application controls flow) | Harder (cache hidden layer) |
| **Multi-DB / polyglot** | Easy (app fetches from any source) | Hard (cache must know all sources) |
| **Cache library coupling** | Loose coupling | Tight coupling |
| **Best for** | Shared cache, microservices, mixed sources | Single-source, standardized cache library |
| **Risk** | Logic errors in app (miss updating cache) | Cache library bugs affect app |
| **TTL strategy** | Per-key, application-controlled | Often global, library-controlled |

### Write-Through vs Write-Behind

| Aspect | Write-Through | Write-Behind |
|---|---|---|
| **Write latency** | High (cache + DB, sync) | Low (cache only, async) |
| **DB throughput** | 1:1 (each write = 1 DB write) | High (batched writes) |
| **Data durability** | Strong (write confirmed in DB) | Weak (data loss window = flush interval) |
| **Consistency** | Strong (cache always = DB) | Eventual (unflushed writes in cache) |
| **Complexity** | Low (no background worker) | High (batch queue, flush logic, retry) |
| **Failure mode** | Write fails → cache and DB both fail | Redis crash → unflushed writes lost |
| **Best for** | Critical writes, read-after-write consistency | High-throughput writes, idempotent data |
| **NOT for** | High-QPS writes (amplification) | Financial, inventory, non-idempotent data |

### Consistency vs Latency

| Aspect | Strong Consistency | Eventual Consistency |
|---|---|---|
| **Read latency** | May require master node (higher latency) | Can read from replica or stale cache (lower) |
| **Write latency** | Write-through (high) | Write-behind (low) |
| **p99 latency** | Predictable but higher | Unpredictable (stale data window) |
| **Correctness** | Always correct | Correct after convergence |
| **Availability** | Lower (depends on DB + cache) | Higher (cache serves even if DB slow) |
| **Best for** | Financial, inventory, compliance | Social feeds, analytics, read-heavy apps |
| **Stale data window** | 0 (always fresh) | Up to TTL (seconds to minutes) |

### Stale Data vs DB Overload

| Aspect | Accept Stale Data | Prevent Stale Data |
|---|---|---|
| **Strategy** | Long TTL, serve stale, no DB call | Short TTL, always DB, immediate invalidation |
| **DB load** | Low (cache serves most reads) | High (every read goes to DB after TTL) |
| **Data freshness** | May be stale (up to TTL) | Always fresh |
| **Read latency** | Low (cache hit) | Variable (cache miss = DB query) |
| **Best for** | Reference data, analytics, non-critical reads | User data, financial, real-time state |
| **Risk** | Business logic may use wrong data | DB overload during cache miss storms |
| **Mitigation** | TTL tuning + monitoring hit rate | Cache stampede prevention + circuit breaker |

### TTL-based Invalidation vs Event-based Invalidation

| Aspect | TTL-based | Event-based |
|---|---|---|
| **Implementation** | Simple (`EXPIRE` or `SETEX`) | Complex (pub/sub, message queue) |
| **Consistency delay** | Up to TTL (seconds to hours) | Near-immediate (< 1s) |
| **Failure mode** | Stale data served until TTL expires | Missed events → stale data until TTL |
| **Infrastructure** | Redis only | Redis + pub/sub or message bus |
| **Scalability** | Scales linearly | Requires fan-out for many subscribers |
| **Debugging** | Simple (TTL visible in `TTL` command) | Complex (event delivery tracking) |
| **Hybrid approach** | Recommended (event + TTL safety net) | Best of both worlds |
| **Best for** | All cases (as safety net) | Critical data needing immediate consistency |

---

## 6. Best Solution & Best Practices

### Scenario 1: E-commerce Product Catalog

**Context**: 500K products, 10K ops/sec read, 100 ops/sec write. Data changes: price, stock, description.

**Recommendation**: Cache-aside + TTL 5 phút + event invalidation.

```go
// Product cache: TTL 5 min + event invalidation
const PRODUCT_CACHE_KEY = "product:%d"
const PRODUCT_TTL = 5 * time.Minute

// On product update → publish event
func UpdateProduct(ctx context.Context, rdb *redis.Client, db *sql.DB, product *Product) error {
    if err := updateProductInDB(db, product); err != nil {
        return err
    }

    // Immediate invalidation (event-based)
    cacheKey := fmt.Sprintf(PRODUCT_CACHE_KEY, product.ID)
    rdb.Del(ctx, cacheKey)

    // Publish to other instances
    event, _ := json.Marshal(CacheInvalidate{Key: cacheKey, Action: "delete"})
    rdb.Publish(ctx, "cache_events", event)

    return nil
}

// On product read → cache-aside
func GetProduct(ctx context.Context, rdb *redis.Client, db *sql.DB, productID int64) (*Product, error) {
    cacheKey := fmt.Sprintf(PRODUCT_CACHE_KEY, productID)
    data, err := rdb.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var p Product
        if json.Unmarshal(data, &p) == nil {
            return &p, nil
        }
    }

    p, err := fetchProductFromDB(db, productID)
    if err == sql.ErrNoRows {
        // Negative caching: cache "not found" for 60s
        rdb.Set(ctx, cacheKey+"__null", "1", 60*time.Second)
        return nil, ErrProductNotFound
    }
    if err != nil {
        return nil, err
    }

    data, _ = json.Marshal(p)
    rdb.Set(ctx, cacheKey, data, PRODUCT_TTL)
    return &p, nil
}
```

### Scenario 2: User Session Store

**Context**: Sessions stored in Redis. Must be read-after-write consistent (user logs in → session immediately available).

**Recommendation**: Write-through + TTL (no event invalidation needed — sessions expire naturally).

```go
// Write-through session
func SetSession(ctx context.Context, rdb *redis.Client, session *Session) error {
    data, _ := json.Marshal(session)

    // Write to Redis first (immediate)
    cacheKey := fmt.Sprintf("session:%s", session.Token)
    if err := rdb.Set(ctx, cacheKey, data, 24*time.Hour).Err(); err != nil {
        return err
    }

    // Then persist to DB (async, non-blocking for user experience)
    go func() {
        if err := persistSessionToDB(session); err != nil {
            log.Printf("Session DB persist failed: %v", err)
        }
    }()

    return nil
}
```

### Scenario 3: Leaderboard / Real-time Score

**Context**: Game leaderboard, scores update frequently (1K updates/sec). Stale data acceptable for 1-2 seconds.

**Recommendation**: Write-behind (buffer scores, flush every 5 seconds) + cache-aside for reads.

```go
// Write-behind for high-frequency score updates
func UpdateScore(ctx context.Context, rdb *redis.Client, userID, gameID string, score int64) error {
    // Immediate write to sorted set
    key := fmt.Sprintf("leaderboard:%s", gameID)
    return rdb.ZAdd(ctx, key, redis.Z{Score: float64(score), Member: userID}).Err()
    // Note: Sorted Set ZADD is already in-memory → no need for write-behind buffer
    // Redis IS the cache and the store here. For persistence, use background job.
}

// Background persistence: flush sorted set to DB every 30s
func persistLeaderboard(ctx context.Context, rdb *redis.Client, db *sql.DB, gameID string) {
    key := fmt.Sprintf("leaderboard:%s", gameID)
    scores, _ := rdb.ZRangeWithScores(ctx, key, 0, -1).Result()

    tx, _ := db.BeginTx(ctx, nil)
    for _, z := range scores {
        tx.ExecContext(ctx, `INSERT INTO scores (user_id, game_id, score)
            VALUES ($1, $2, $3) ON CONFLICT DO UPDATE SET score = $3`,
            z.Member, gameID, int64(z.Score))
    }
    tx.Commit()
}
```

---

## 7. Performance Considerations

### Latency Breakdown by Pattern

```
Pattern              | Cache Hit | Cache Miss | Write         | Notes
─────────────────────────────────────────────────────────────────────────
Cache-Aside          | 0.1-0.5ms | 1-5ms     | 1-5ms (DB)   | 1 RTT + DB
Read-Through        | 0.1-0.5ms | 2-6ms      | 1-5ms (DB)   | 1 RTT + DB
Write-Through       | 0.1-0.5ms | 0.1-0.5ms  | 2-10ms       | 2 RTT + DB
Write-Behind        | 0.1-0.5ms | 0.1-0.5ms  | 0.1-0.5ms    | 1 RTT only
Refresh-Ahead       | 0.1-0.5ms | ~0ms       | Same as base | Eliminates miss
─────────────────────────────────────────────────────────────────────────
```

**p95/p99 impact by TTL**:

| TTL  | Stale window (max) | DB load reduction | Data freshness risk |
|------|--------------------|--------------------|---------------------|
| 30s  | 30s                | Moderate           | Low risk            |
| 5m   | 5m                 | High               | Medium risk         |
| 30m  | 30m                | Very high          | High risk (pricing) |
| 1h   | 1h                 | Extreme            | Critical risk       |
| 24h  | 24h                | Minimal            | Unacceptable        |

**Memory overhead per pattern**:

```
Pattern              | Memory overhead                | Note
─────────────────────────────────────────────────────────────────────────
Cache-Aside          | Keys stored: hot keys only     | Most efficient
Read-Through         | Keys stored: accessed keys     | Similar to above
Write-Through        | Keys stored: written keys      | All writes cached
Write-Behind         | Keys stored + write buffer     | Extra: LIST overhead
Refresh-Ahead        | Keys stored: hot keys          | Plus: background refresh memory
Negative caching     | ~10% extra keys (null entries)| Destructor pattern overhead
─────────────────────────────────────────────────────────────────────────
```

**Hit rate estimation**:

```
Access pattern    | Recommended TTL | Expected hit rate | Notes
─────────────────────────────────────────────────────────────────────────
Uniform random    | N/A (no benefit)| < 10%            | Cache not useful
Power law (hot)   | 5-30m           | 80-95%           | 20% keys = 80% traffic
Read-heavy (80/20)| 5-10m           | 90-99%           | Classic Pareto
Write-heavy (50/50)| 1-5m           | 50-70%           | Many invalidations
Near-static (ref) | 1-24h           | 99%+             | Config, metadata
─────────────────────────────────────────────────────────────────────────
```

---

## 8. Production Failure Modes

### 8.1. Cache Invalidation Missed — Stale Data Served for Hours

```
Symptom: User reports data inconsistency (e.g., price not updated, profile wrong)
          Data in DB is correct, but cache returns old value
Cause:
  - Write path updates DB but forgets to invalidate cache
  - TTL not set → key lives forever → never expires
  - Multiple services: service A updates, service B doesn't see (no event bus)

Detection:
  - User complaints / data mismatch reports
  - Compare cache TTL with last DB update timestamp
  - Redis: DEBUG OBJECT key (shows encoding + TTL info)

Fix:
  - Manual: DEL cache key immediately
  - Automated: set shorter TTL as safety net (TTL as backstop for missed invalidation)
  - Preventive: event-driven invalidation + TTL always set together

Prevention:
  - Code review checklist: every DB write must invalidate cache
  - TTL always set on every cache SET
  - Event bus between microservices for cache invalidation
  - Monitor: alert when cache TTL > threshold
```

### 8.2. Cache Stampede — DB Overload on Hot Key Expiry

```
Symptom: Database CPU spikes to 100%, response time increases 10x
          Redis hit rate drops to 0% temporarily
Cause:
  - Hot key expires (TTL = 0)
  - N concurrent requests all miss cache simultaneously
  - N DB queries fired at same time
  - DB overwhelmed → cascading latency

Detection:
  - Redis: check hit rate (should be > 90%)
  - DB: monitor active connections spike
  - Application: p99 latency spike correlating with cache miss

Fix:
  - Immediate: `SET lock:{key} token NX EX 5`, only one request loads from DB
  - Short-term: increase TTL to reduce expiry frequency
  - Medium-term: implement cache warming for hot keys
  - Long-term: probabilistic early expiration (XFetch)

Prevention:
  - TTL jitter: random 0-30s added to every TTL
  - Background refresh: refresh hot keys before expiry
  - Request coalescing: only 1 DB query per key per miss window
  - Circuit breaker: if DB overload detected, serve stale cache
```

### 8.3. Negative Cache Explosion — Memory Exhausted

```
Symptom: Redis memory grows rapidly, `used_memory_human` high
          Many keys with pattern key:__null
Cause:
  - Negative cache entries accumulate faster than expiry
  - TTL on null entries too long
  - Application flooding cache with "not found" for invalid inputs

Detection:
  redis-cli --scan --pattern "*:__null" | wc -l
  # Count null keys

Fix:
  - Set shorter TTL for null entries (30-60s max)
  - Add memory limit monitoring + alert
  - Limit negative cache per user/IP

Prevention:
  - Monitor evicted_keys + null key count separately
  - Consider not caching null for high-cardinality keys
  - Use `SCAN + DEL` to clean up explosion
```

### 8.4. Write-Behind Data Loss — Redis Crash Before Flush

```
Symptom: After Redis restart, some writes are missing
          DB does not have records that application confirmed as "written"
Cause:
  - Write-behind buffer (LIST) not flushed before Redis crash
  - AOF fsync = no (or everysec) → data in OS buffer not persisted
  - Redis restart clears in-memory state

Detection:
  - Compare Redis key count vs DB record count after restart
  - Application logs show writes confirmed but missing in DB

Fix:
  - Recover from Redis backup (if AOF enabled)
  - Replay write buffer from application (if application maintains log)
  - Notify affected users (data loss acknowledged)

Prevention:
  - Use write-through for critical data (no async buffer)
  - If write-behind is needed: fsync = always + smaller flush interval
  - Persist write buffer to disk before confirming write to client
  - Idempotent design: replayed writes produce same result
```

### 8.5. Cross-Service Cache Inconsistency

```
Symptom: Service A reads fresh data, service B reads stale data
          Same key has different values in different Redis instances
Cause:
  - Service A writes and invalidates its Redis
  - Service B has its own Redis (cache-aside per service)
  - Invalidation event not propagated to service B

Detection:
  - Inconsistent state observed in application
  - Logs show different cache values per service

Fix:
  - Centralized Redis (shared cache layer) — single source of truth
  - Or: pub/sub invalidation across all service instances

Prevention:
  - Architecture decision: shared cache vs per-service cache
  - If shared cache: use Redis Cluster or Sentinel for HA
  - If per-service: implement event-driven invalidation via pub/sub
  - Monitor: cross-service cache key consistency (if feasible)
```

---

## 9. Real-world Examples

### Payment Platform — Cache Invalidation via Database Triggers

Scenario tương tự các payment/pricing systems: cache-aside cho pricing configuration. Pricing updates xảy ra qua Admin dashboard. Khi pricing updated trong PostgreSQL, database trigger hoặc outbox event publishes event → Go service receives → invalidates Redis cache for affected pricing keys.

**Số liệu**:
- 50K pricing configurations cached
- TTL = 1 giờ (safety net)
- Event invalidation = near-real-time (< 500ms)
- Hit rate: 99.2% (only 0.8% reads hit DB)

**Bài học**: TTL as safety net + event invalidation = best of both worlds.

### Twitter/X — User Timeline Cache

Twitter dùng cache-aside với write-invalidation cho user timelines. Khi user posts a tweet:
1. Tweet written to DB (source of truth).
2. Cache invalidation event published.
3. Fanout service: invalidates timeline cache for all followers.
4. Next timeline request: repopulates cache from DB.

**Số liệu**:
- Timeline cache TTL: 60-300s (varied by account size)
- Hit rate: 95% for active users
- p99 latency: 5ms (cache hit), 50ms (cache miss + DB)
- Fanout: invalidates 100-10,000 cache keys per new tweet

**Bài học**: Write-invalidation at scale requires efficient fanout. Twitter uses hybrid: push (for small follower count) + pull (for celebrities with millions of followers).

### Airbnb — Search Result Caching

Airbnb caches search results with cache-aside pattern. Search query hash → cache key. TTL = 5 minutes.

**Số liệu**:
- 80% of search queries served from cache
- p50 latency: 2ms (cache hit), 40ms (cache miss)
- Cache stampede risk: mitigated with TTL jitter (+/- 60s random)
- Negative caching: queries with 0 results cached for 60s

**Bài học**: Cache-aside scales well for read-heavy search. TTL jitter critical to prevent synchronized expiry of popular search results.

### Netflix — Refresh-Ahead for API Response Caching

Netflix dùng refresh-ahead strategy cho API response caching. Hot endpoints pre-warmed 80% through TTL. Background job polls and refreshes before expiry.

**Số liệu**:
- API cache TTL: 5 minutes
- Refresh triggered: at 80% TTL (4 minutes)
- Cache miss rate: < 0.5% (from 20% expected to < 0.5% via refresh-ahead)
- Memory overhead: ~25% extra (pre-warmed keys)

**Bài học**: Refresh-ahead reduces miss rate by 10-40× for hot data, at cost of extra memory. ROI highest when p99 latency SLA is strict.

---

## 10. Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Không invalidate cache khi update DB | Stale data served for hours | Add cache invalidation in same transaction/same function |
| Dùng TTL quá dài cho critical data | Pricing, stock stale for minutes | TTL ≤ 60s cho critical data, event invalidation primary |
| Cache hot key với TTL không có jitter | Mass cache miss khi TTL expires cùng lúc | Add random jitter: `TTL + rand(0,30)s` |
| Không negative caching cho "not found" | DB overloaded với repeated queries cho nonexistent records | Cache null/404 với TTL ngắn (30-60s) |
| Write-behind cho inventory/payment | Data loss khi Redis crash | Use write-through for critical mutations |
| Dùng same key pattern cho cache-aside và write-behind | Race condition: read cache-aside vs write-behind buffer | Use separate keys or consistent pattern |
| Cache size không có giới hạn | Redis OOM → crash | Set `maxmemory` + appropriate eviction policy |
| Refresh-ahead không có throttle | Background refresh gây DB overload | Rate-limit refresh job: max N keys/minute |
| Không phân biệt hot vs cold data | Cold data chiếm cache memory, hot data bị evict | Use `volatile-ttl` eviction, separate pools |
| Serving stale cache khi DB down | Application serve outdated data as "fallback" | Circuit breaker: if DB unhealthy, return error, don't serve stale |

---

## 11. Câu Hỏi Tự Kiểm Tra

### Câu 1: Cache-Aside vs Read-Through Trade-off

Bạn đang thiết kế cache cho microservice architecture với 5 services, mỗi service access data từ 2-3 different databases (PostgreSQL, MySQL, external APIs). Bạn chọn cache-aside hay read-through? Giải thích với 3 lý do cụ thể.

> **Đáp án**:
> Chọn **cache-aside** vì:
> 1. **Multi-source flexibility**: Cache-aside cho phép application tự quyết định fetch từ database nào. Read-through cache phải được configure cho từng data source, không hỗ trợ external API call.
> 2. **Loose coupling**: Mỗi service độc lập quản lý cache lifecycle. Read-through gắn cache behavior vào cache library, khiến việc swap cache implementation khó khăn.
> 3. **Debugging**: Khi xảy ra bug, cache-aside cho phép trace đầy đủ (cache hit? → value, miss? → which DB? → query). Read-through ẩn fetch logic trong cache layer → khó debug production issues.
>
> Read-through chỉ phù hợp khi: single data source + standardized cache library (ví dụ Spring Boot với Hibernate second-level cache).

### Câu 2: Write-Through vs Write-Behind — Khi Nào Dùng?

Một payment service cần write transaction records (500 writes/sec). Mỗi write phải persisted trong database — data loss không acceptable. Giải thích tại sao write-behind KHÔNG phù hợp và write-through là tối thiểu phải có. Nếu 500 writes/sec quá cao cho DB, đề xuất giải pháp nào?

> **Đáp án**:
> **Không dùng write-behind** vì: write-behind có data loss window (unflushed writes mất khi Redis crash). Payment transaction = financial data → zero tolerance for data loss. Write-behind chỉ acceptable cho idempotent, losable data (analytics, counters).
>
> **Write-through tối thiểu phải có** vì: write-through đảm bảo write xác nhận đã xuống DB trước khi return success. Mỗi write = 2 RTT (cache + DB), synchronous. Với 500 writes/sec → acceptable (DB phải handle 500 writes/sec anyway).
>
> **Nếu 500 writes/sec quá cao cho DB**:
> - Giải pháp 1: Batch writes (micro-batching): accumulate writes in Redis LIST (write-behind buffer), flush to DB every 100ms. Trade-off: 100ms data loss window. Only acceptable if idempotent.
> - Giải pháp 2: Write sharding: chia writes across multiple DB shards (5 shards × 100 writes/sec = acceptable).
> - Giải pháp 3: async write-through: write to Redis (synchronous), then async flush to DB (non-blocking). Trade-off: Redis confirms, DB confirm async. Risk: DB write fails → Redis has data, DB doesn't. Must have reconciliation job.

### Câu 3: Cache Stampede — Phân Tích và Fix

Một endpoint `/api/product/:id` dùng cache-aside với TTL = 5 phút. Endpoint này có 10.000 requests/second, trong đó 1 sản phẩm chiếm 3.000 RPS (hot product). Sau 5 phút, TTL expires đồng thời, 3.000 requests miss cache cùng lúc → database overload. Đề xuất 3 cách giải quyết với trade-off cụ thể.

> **Đáp án**:
> **Cách 1: TTL Jitter** — Add random 0-60s to TTL.
> - Implementation: `SET product:{id} data EX (300 + rand(0,60))`
> - Trade-off: Stale data window tăng thêm 60s max. Cache hit rate vẫn ~95%. Simple, zero infrastructure.
> - Result: Hot keys expire at different times → no synchronized stampede.
>
> **Cách 2: Probabilistic Early Expiration (XFetch)** — Refresh before TTL expires.
> - Implementation: On read, check TTL remaining. If < 20% left, trigger background refresh.
> - Trade-off: Extra CPU/memory for refresh job. Complexity higher. But eliminates miss completely for hot keys.
> - Result: Cache miss rate drops from 20% (expected) to < 0.5%.
>
> **Cách 3: Request Coalescing (Mutex Lock)** — Only 1 request loads from DB on miss.
> - Implementation: On miss, `SET lock:product:{id} token NX EX 5`. Only lock holder loads from DB. Others wait or return stale if available.
> - Trade-off: First request still slow (DB load). Subsequent requests: either wait (adds latency) or return old data if available (stale). Best for extreme hot key scenarios.
> - Result: 3.000 concurrent DB queries → 1 DB query.

### Câu 4: Negative Caching Security

Một attacker gửi 10.000 requests/second với random user IDs không tồn tại. Mỗi miss → DB query → negative cache entry. Negative cache TTL = 60s. Attack duration = 1 giờ. Phân tích:

A) Tại sao điều này nguy hiểm (2 lý do)?
B) Tính memory consumption tối đa của negative cache entries sau 1 giờ?
C) Đề xuất 2 biện pháp phòng ngừa.

> **Đáp án**:
> A) **Tại sao nguy hiểm**:
> 1. **Memory exhaustion**: 10.000 RPS × 60s TTL = 600.000 negative cache entries max in Redis. Nếu mỗi entry ~100 bytes → 60MB. Nếu attacker dùng high-cardinality (1M unique IDs) → 100MB negative cache, evicting real positive entries → cache thrashing.
> 2. **Security bypass**: Nếu application logic coi "negative cache hit" = "no rate limit applied" (bug như GitHub incident), attacker bypasses rate limiting.
>
> B) **Memory calculation**:
> - After 1 hour: negative cache entries = min(10.000 × 3.600, unique IDs tried)
> - Worst case (all unique IDs): 36M entries × ~100 bytes = 3.6GB → Redis OOM
> - With maxmemory 1GB + volatile-lru: real positive entries evicted → hit rate drops to 0% → full DB load
>
> C) **Prevention**:
> 1. **Short TTL + rate limit**: Negative cache TTL ≤ 30s. Add per-IP rate limiting on user lookup endpoint (Day 27 content).
> 2. **Don't cache negatives for high-cardinality keys**: If user ID cardinality > 10K, don't cache negatives. Only cache negatives for low-cardinality "category not found" type queries.
> 3. **Monitor `evicted_keys`**: Alert if evicted_keys > 100/minute → cache poisoning attack suspected.

### Câu 5: Hybrid Invalidation Strategy

Bạn có 1 triệu product records trong PostgreSQL. Cache TTL = 30 phút. Sản phẩm được update không thường xuyên (trung bình 1 update/product/ngày). Team muốn data freshness < 5 phút sau update. Đề xuất hybrid strategy: event-based + TTL. Phân tích trade-off và đề xuất specific TTL values.

> **Đáp án**:
> **Hybrid approach**:
> - **Event-based invalidation primary**: Khi product updated → `DEL product:{id}` (immediate, < 100ms)
> - **TTL safety net**: TTL = 5 phút (not 30!). Nếu event bị miss (network issue, service down), TTL đảm bảo data tự động refreshed sau 5 phút.
>
> **Trade-off analysis**:
> - Event invalidation alone: risk = missed events → stale data indefinitely. TTL safety net eliminates this.
> - TTL alone (5 phút): data freshest = 5 phút, but DB load = 1M / 5 min = 3.333 queries/min = 56 queries/sec (acceptable). But 30-min TTL would cause 1 triệu requests × 30 min gap = unacceptable for product updates.
> - Hybrid: event invalidation = < 100ms freshness, TTL safety net = 5 min max stale.
>
> **Specific TTL**:
> - Primary cache: 5 phút (covers missed events + natural expiry)
> - Negative cache: 60 giây (not found = short-lived)
> - Write-behind buffer flush: 5-30 giây (if using write-behind)
>
> **Additional recommendation**: Monitor event delivery success rate. If > 1% events fail, implement dead letter queue + retry mechanism.

### Câu 6: Consistency Strategy for Order Service

Thiết kế consistency strategy cho order service với:
- 1.000 orders/second
- Read operations: 10.000/second (check order status)
- Writes: order creation, status update, cancellation
- SLA: order status accuracy > 99.9%, p99 < 200ms

Đề xuất caching pattern per operation type và justify với numbers.

> **Đáp án**:
>
> **Order Creation (1.000 writes/sec)**:
> - Pattern: DB transaction first + cache populate after commit
> - Write: insert order/status trong DB transaction → commit → `SET order:{id} data EX 3600` và update `user:{id}:recent_orders`
> - Why: Order creation là user-facing mutation, không được confirm trước khi DB durable. Cache chỉ phục vụ read-after-write sau commit.
> - p99: DB write + Redis SET, thường ~20-50ms tùy DB; nếu Redis SET fail, return success nhưng enqueue cache invalidation retry vì DB là source of truth.
>
> **Order Status Read (10.000 reads/sec)**:
> - Pattern: Cache-aside + TTL 30s
> - Read: `GET order:{id}` → hit (90% of requests, ~0.2ms) → miss (10%, fetch from DB ~5ms)
> - Write-invalidation: On status update → `DEL order:{id}` (immediate)
> - Why: High read volume → cache reduces DB load. 30s TTL → max 1% stale reads acceptable.
> - Expected hit rate: 90%+ (Pareto: 20% popular orders = 80% reads)
>
> **Order Cancellation (low volume, critical)**:
> - Pattern: Write-through (synchronous, no async)
> - Write: Update DB first → DEL cache → return success only when both confirmed
> - Why: Cancellation is financial event → must be durable. No data loss acceptable.
> - p99: ~20-30ms (DB write + cache invalidation)
>
> **Caching hot user orders** (most recent 10 orders per user):
> - Pattern: Write-invalidate on order creation
> - Key: `user:{id}:recent_orders` (JSON array of last 10 orders)
> - On new order: LPUSH + LTRIM + invalidate
> - Why: User dashboard shows recent orders → high read, high value
> - TTL: 1 giờ (user likely to check within that time)

### Câu 7: Cache Warming After Redis Restart

Redis restart vì hardware maintenance. Cache cold. Traffic 50.000 RPS đổ vào. Database có 10 triệu records. Thiết kế warming strategy để:

A) Estimate DB load without warming (worst case)
B) Estimate DB load with warming (best case)
C) Đề xuất warming implementation với specific numbers

> **Đáp án**:
> A) **Without warming — worst case**:
> - 50.000 RPS × cold cache = 50.000 DB queries/second
> - DB max capacity: typically 5.000-20.000 queries/second per instance
> - Result: DB overload → 50.000 / 5.000 = 10× over capacity → DB fails completely
> - Time to first warm: depends on which keys accessed first → chaos for first few minutes
>
> B) **With warming — best case**:
> - Warm-up job reads top 10.000 hot keys from DB (assume 80% of traffic)
> - Warm-up time: 10.000 keys / 1.000 keys/sec (pipeline) = 10 seconds
> - After warm-up: 80% traffic served from cache (40.000 RPS)
> - Remaining 20%: 10.000 RPS → still high, but survivable with connection pool
>
> C) **Warming implementation**:
> ```go
> // Phase 1: Immediate (0-10s) — warm top 10K hot keys
> func warmTopKeys(ctx context.Context, rdb *redis.Client, db *sql.DB) error {
>     // Read from "hot keys" tracking table (populated by analytics)
>     rows, _ := db.Query(`SELECT id FROM products
>         ORDER BY view_count DESC LIMIT 10000`)
>
>     pipe := rdb.Pipeline()
>     for rows.Next() {
>         var id int64
>         rows.Scan(&id)
>         data, _ := fetchProduct(db, id)
>         pipe.Set(ctx, fmt.Sprintf("product:%d", id), data, 30*time.Minute)
>     }
>     pipe.Exec(ctx)
>     return nil
> }
>
> // Phase 2: Background (10-300s) — gradual warming
> // On each cache miss, warm related keys
> // If user visits product:123 → also warm product:124, product:125 (related)
> // Rate-limit: max 500 warm-up reads/sec to DB (prevent overload)
>
> // Phase 3: Circuit breaker
> // If DB CPU > 70% during warm-up: pause warm-up for 30s, resume
> ```
>
> **Numbers**:
> - Top 10K keys cover ~80% of requests
> - Warm-up: 10 seconds (fast pipeline)
> - Remaining 20% traffic (10K RPS): spreads over 5 minutes = manageable
> - Circuit breaker: protect DB during warm-up window
