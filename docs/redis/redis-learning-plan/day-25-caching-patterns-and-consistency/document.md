# Day 25: Caching Patterns & Consistency — Reference Document

---

## 1. Command Cheat Sheet

### Cache Operations

```txt
-- Basic cache operations
SET user:100:profile '{"id":100,"name":"Alice"}' EX 300
GET user:100:profile
DEL user:100:profile

-- Cache with TTL jitter (application sets, example)
-- TTL 300s + random 0-60s jitter → 300-360s actual TTL

-- Check TTL
TTL user:100:profile
-- Return: -2 = key not exist, -1 = no TTL, N = seconds remaining

-- Set only if not exists (cache-aside lock, atomic TTL)
SET lock:product:123 "token-abc" NX EX 5

-- Negative cache sentinel
SET user:9999:__null__ "1" EX 60
-- Check: GET user:9999:__null__ → "1" means "not found"

-- Batch populate cache (cache warming)
MSET product:1:detail '{"id":1}' product:2:detail '{"id":2}' product:3:detail '{"id":3}'
EXPIRE product:1:detail 600
EXPIRE product:2:detail 600
EXPIRE product:3:detail 600

-- Pipeline for batch warming
-- Application: pipeline 100 SET + 100 EXPIRE per batch

-- Scan for cache keys
SCAN 0 MATCH "product:*" COUNT 100
SCAN 0 MATCH "user:*:__null__" COUNT 100  -- find negative cache entries

-- Delete all negative cache entries (cleanup)
SCAN 0 MATCH "*:__null__" | xargs redis-cli DEL
```

### Cache Statistics

```txt
-- Hit/miss statistics
INFO stats | grep -E "keyspace_hits|keyspace_misses"
-- hit_rate = hits / (hits + misses)

-- Memory usage
INFO memory | grep -E "used_memory_human|maxmemory_human|evicted_keys"

-- Check key encoding and TTL info
DEBUG OBJECT user:100:profile
-- Output: key_name, encoding, ttl, idle_time, refs, mem

-- Check memory usage of specific key
MEMORY USAGE user:100:profile

-- Latency histogram (Redis 7.2+)
LATENCY HISTOGRAM user:100:profile
```

### Invalidation via Pub/Sub

```txt
-- Publisher: publish invalidation event
PUBLISH cache_invalidation '{"key":"user:100:profile","action":"delete","ts":1704067200}'

-- Subscriber: subscribe and invalidate
SUBSCRIBE cache_invalidation
-- On message: DEL <key>

-- Pattern: use separate channel per namespace
PUBLISH cache_invalidation:products '{"key":"product:500","action":"delete"}'
PUBLISH cache_invalidation:users '{"key":"user:100","action":"delete"}'
```

---

## 2. Go Code Snippets

### 2.1. Cache-Aside Pattern (Go)

```go
package cache

import (
    "context"
    "database/sql"
    "encoding/json"
    "fmt"
    "log"
    "math/rand"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    UserCacheKey   = "user:%d"
    DefaultTTL     = 5 * time.Minute
    NullCacheSuffix = ":__null__"
)

// GetUser returns user from cache (cache-aside), falling back to DB.
func GetUser(ctx context.Context, rdb *redis.Client, db *sql.DB, userID int64) (*User, error) {
    cacheKey := fmt.Sprintf(UserCacheKey, userID)

    // Step 1: Try cache
    data, err := rdb.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var u User
        if json.Unmarshal(data, &u) == nil {
            return &u, nil
        }
    }
    if !errors.Is(err, redis.Nil) {
        log.Printf("Redis GET %s error: %v", cacheKey, err)
    }

    // Step 2: Cache miss — query DB
    u, err := fetchUserFromDB(ctx, db, userID)
    if err == sql.ErrNoRows {
        // Negative cache: mark "not found" for 60s
        rdb.Set(ctx, cacheKey+NullCacheSuffix, "1", 60*time.Second)
        return nil, ErrUserNotFound
    }
    if err != nil {
        return nil, err
    }

    // Step 3: Populate cache asynchronously
    go func() {
        d, _ := json.Marshal(u)
        jitter := time.Duration(rand.Intn(30)) * time.Second
        rdb.Set(ctx, cacheKey, d, DefaultTTL+jitter)
    }()

    return &u, nil
}

// UpdateUser updates user in DB and invalidates cache.
func UpdateUser(ctx context.Context, rdb *redis.Client, db *sql.DB, u *User) error {
    if err := updateUserInDB(ctx, db, u); err != nil {
        return err
    }
    cacheKey := fmt.Sprintf(UserCacheKey, u.ID)
    if err := rdb.Del(ctx, cacheKey).Err(); err != nil {
        log.Printf("Cache invalidation failed for %s: %v", cacheKey, err)
    }
    return nil
}

// InvalidateUserEvent-driven invalidation via pub/sub.
func StartCacheSubscriber(ctx context.Context, rdb *redis.Client) {
    pubsub := rdb.Subscribe(ctx, "cache_invalidation:users")
    defer pubsub.Close()

    for msg := range pubsub.Channel() {
        var ev struct {
            Key    string `json:"key"`
            Action string `json:"action"`
        }
        if json.Unmarshal([]byte(msg.Payload), &ev) == nil {
            if ev.Action == "delete" {
                rdb.Del(ctx, ev.Key)
                log.Printf("Invalidated cache: %s", ev.Key)
            }
        }
    }
}
```

### 2.2. Write-Behind Pattern (Go)

```go
package cache

import (
    "context"
    "encoding/json"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

// WriteOrderAsync appends order to Redis write buffer (not DB).
func WriteOrderAsync(ctx context.Context, rdb *redis.Client, order *Order) error {
    data, err := json.Marshal(order)
    if err != nil {
        return err
    }
    // LPUSH = prepend (newest first), RPOP = consume oldest
    return rdb.LPush(ctx, "write_buffer:orders", data).Err()
}

// FlushOrdersWorker consumes write buffer and flushes to DB in batches.
func FlushOrdersWorker(ctx context.Context, rdb *redis.Client, db *sql.DB, flushInterval time.Duration) {
    ticker := time.NewTicker(flushInterval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            // Final flush before shutdown
            flushOrders(ctx, rdb, db, 1000)
            return
        case <-ticker.C:
            flushOrders(ctx, rdb, db, 100)
        }
    }
}

func flushOrders(ctx context.Context, rdb *redis.Client, db *sql.DB, batchSize int) {
    orders := make([]Order, 0, batchSize)
    for i := 0; i < batchSize; i++ {
        data, err := rdb.RPop(ctx, "write_buffer:orders").Bytes()
        if err != nil {
            break
        }
        var o Order
        if json.Unmarshal(data, &o) == nil {
            orders = append(orders, o)
        }
    }
    if len(orders) == 0 {
        return
    }

    // Batch insert
    tx, err := db.BeginTx(ctx, nil)
    if err != nil {
        log.Printf("FlushOrders: begin tx failed: %v", err)
        return
    }
    for _, o := range orders {
        _, err := tx.ExecContext(ctx,
            `INSERT INTO orders (id, user_id, total, status, created_at)
             VALUES ($1,$2,$3,$4,$5) ON CONFLICT (id) DO NOTHING`,
            o.ID, o.UserID, o.Total, o.Status, o.CreatedAt)
        if err != nil {
            tx.Rollback()
            log.Printf("FlushOrders: insert failed: %v", err)
            return
        }
    }
    if err := tx.Commit(); err != nil {
        log.Printf("FlushOrders: commit failed: %v", err)
    } else {
        log.Printf("Flushed %d orders to DB", len(orders))
    }
}
```

### 2.3. Cache Warming (Go)

```go
package cache

import (
    "context"
    "database/sql"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

// WarmUserCache populates cache with top N most-accessed users.
func WarmUserCache(ctx context.Context, rdb *redis.Client, db *sql.DB) error {
    const batchSize = 100
    const warmTTL = 10 * time.Minute

    rows, err := db.QueryContext(ctx, `
        SELECT id, name, email FROM users
        ORDER BY last_login DESC
        LIMIT 10000
    `)
    if err != nil {
        return err
    }
    defer rows.Close()

    pipe := rdb.Pipeline()
    count := 0

    for rows.Next() {
        var u User
        if err := rows.Scan(&u.ID, &u.Name, &u.Email); err != nil {
            continue
        }
        data, _ := json.Marshal(u)
        cacheKey := fmt.Sprintf("user:%d", u.ID)
        pipe.Set(ctx, cacheKey, data, warmTTL)
        count++

        if count%batchSize == 0 {
            if _, err := pipe.Exec(ctx); err != nil {
                log.Printf("Warmup pipeline error: %v", err)
            }
            pipe = rdb.Pipeline()
        }
    }

    if _, err := pipe.Exec(ctx); err != nil {
        return err
    }

    log.Printf("Cache warmed with %d users (TTL=%v)", count, warmTTL)
    return nil
}
```

---

## 3. TTL Reference Table

| Data Type | TTL Recommended | Rationale |
|---|---|---|
| User profile (read-heavy) | 5-10 min | Read 10K RPS, update ~1/hour |
| Product catalog | 5-30 min | Price/stock updates via event |
| Session/token | 24 hours (no TTL jitter) | Must expire exactly |
| Rate limit counter | 60 seconds (sliding window) | Must reset accurately |
| Leaderboard scores | No TTL (permanent until overwritten) | ZADD overwrites, no expiry needed |
| Search results | 5-15 min | Search patterns vary, TTL jitter needed |
| Negative cache (not found) | 30-60 seconds | Short — avoid memory bloat |
| User's recent orders | 30-60 min | High value, frequent reads |
| Static config/metadata | 1-24 hours | Rarely changes |
| One-time tokens (email verify) | 24 hours | Must expire reliably |
| Distributed lock | 10-30 seconds | Must auto-expire to prevent deadlock |

---

## 4. Consistency Model Decision Matrix

| Use Case | Pattern | Write Strategy | Read Strategy | TTL | Event Invalidation |
|---|---|---|---|---|---|
| Product catalog | Cache-aside | Invalidate on write | Read from cache | 5-30 min | Yes (critical) |
| User session | Write-through | Sync to cache + DB | Read from cache | 24h | No (expires naturally) |
| Rate limit | N/A (atomic counters) | INCR on every request | GET counter | 60s | No |
| Order status | Cache-aside | Invalidate on update | Read from cache | 30-60s | Yes |
| Leaderboard | Refresh-ahead | Write-through to cache | Read from cache | No TTL | Partial |
| Search results | Cache-aside | TTL expiry only | Read from cache | 5-15 min | Optional |
| User profile | Cache-aside | Invalidate on write | Read from cache | 5-10 min | Yes |
| Config/metadata | Cache-aside | Invalidate on change | Read from cache | 1-24h | Yes |
| Payment record | Write-through | Sync to cache + DB | Read from cache | No TTL | N/A |
| Analytics counter | Write-behind | Async to DB | Read from cache | No TTL | No |

---

## 5. Production Checklist

### Pre-deployment

- [ ] TTL set on every `SET` / `SETEX` command (no TTL = infinite cache = memory leak)
- [ ] TTL jitter implemented: `baseTTL + rand(0, maxJitter)` for hot keys
- [ ] Negative cache implemented for high-cardinality existence checks
- [ ] Cache key naming convention documented (namespace:id:field)
- [ ] `maxmemory` set with `volatile-lru` or `allkeys-lru` eviction policy
- [ ] Cache warming job defined for cold-start scenarios

### Write Path

- [ ] Every DB write has corresponding cache invalidation in same function
- [ ] Write-through used for critical reads (read-after-write required)
- [ ] Write-behind ONLY used for idempotent, losable data
- [ ] Write-behind flush interval < data loss tolerance (e.g., 5s = max 5s data loss)
- [ ] Circuit breaker implemented: if DB write fails, do not confirm to client

### Read Path

- [ ] Cache-aside: always `SET` after DB read (don't leave cache empty after miss)
- [ ] Cache-aside: handle `redis.Nil` as "cache miss" (not error)
- [ ] Negative cache: sentinel value `__null__` suffix for "not found"
- [ ] Graceful degradation: if Redis unavailable, fall back to DB (with circuit breaker)

### Monitoring

- [ ] Cache hit rate monitored: alert if hit rate < 80% (read-heavy) or < 60% (mixed)
- [ ] `evicted_keys` monitored: alert if > 100/minute
- [ ] `keyspace_hits` / `keyspace_misses` exposed to Prometheus
- [ ] Latency p95/p99: alert if cache hit p99 > 1ms or cache miss p99 > 50ms
- [ ] Negative cache key count monitored (anti-pattern detection)
- [ ] Memory usage: alert if `used_memory > 80% maxmemory`

### Cache Stampede Prevention

- [ ] TTL jitter on hot keys (mandatory for any key with > 100 RPS)
- [ ] Request coalescing: `SET lock:{key} token NX EX <ttl>` before loading from DB
- [ ] Probabilistic early expiration (XFetch) for critical hot keys
- [ ] Background refresh job scheduled for hot data (refresh-ahead)
- [ ] Cache warming job runs after Redis restart or deployment

---

## 6. Docker Compose — Redis for Caching Lab

```yaml
version: "3.8"
services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-cache-lab
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save ""        # Disable RDB snapshotting for lab
      --appendonly no  # Disable AOF for lab
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  postgres:
    image: postgres:15-alpine
    container_name: postgres-cache-lab
    environment:
      POSTGRES_DB: cachedb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 3
```

```sql
-- init.sql: Setup users table for cache-aside lab
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    last_login TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (name, email)
SELECT 'User ' || i, 'user' || i || '@example.com'
FROM generate_series(1, 1000) AS i
ON CONFLICT DO NOTHING;
```

---

## 7. Lua Script: Probabilistic Early Expiration

```lua
-- XFetch-inspired: probabilistic early refresh
-- KEYS[1] = cache key
-- ARGV[1] = original TTL (seconds)
-- ARGV[2] = refresh probability threshold (0-1, e.g., 0.8 = refresh at 80% of TTL)

local key = KEYS[1]
local original_ttl = tonumber(ARGV[1])
local threshold = tonumber(ARGV[2])

local data = redis.call('GET', key)
if not data then
    return nil  -- Key doesn't exist, don't refresh (will be loaded by app)
end

local ttl = redis.call('TTL', key)

-- Calculate refresh point: if remaining TTL < (original_ttl * (1 - threshold))
local refresh_point = math.floor(original_ttl * (1 - threshold))

if ttl > 0 and ttl <= refresh_point then
    -- TTL past refresh point: return data + signal "refresh recommended"
    -- Application should spawn async refresh in background
    -- Return data + 1 (1 = needs refresh)
    redis.log(redis.LOG_WARNING, "XFetch: refresh recommended for " .. key .. ", ttl=" .. ttl)
    return {data, 1}
end

-- Data is fresh: return data + 0 (0 = no refresh needed)
return {data, 0}
```

---

## 8. Links

- [Redis Caching Patterns — Official Best Practices](https://redis.io/docs/manual patterns/)
- [Redis INFO: Keyspace Hit/Miss Statistics](https://redis.io/commands/info/)
- [TTL Pitfalls and Cache Stampede — Salesforce Engineering](https://engineering.salesforce.com/)
- [XFetch: A Promise-Based Cache-Aside Pattern](https://martinfowler.com/articles/xfetch.html)
- [Cloudflare: Negative Caching at Scale](https://blog.cloudflare.com/)
- [Stripe: Cache Invalidation at Scale](https://stripe.com/blog)
- [Redis Eviction Policies — Official Docs](https://redis.io/docs/management/optimization-memory-usage/)
- [Probabilistic Early Expiration — ACM Queue](https://queue.acm.org/detail.cfm?id=2956832)
