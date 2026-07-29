# Day 25: Caching Patterns & Consistency — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: Go
**Redis**: 7.2+
**Database**: PostgreSQL 15+

---

## 0. Setup

```bash
# Start Redis + PostgreSQL
cd day-25-caching-patterns-and-consistency
docker compose up -d

# Wait for services to be ready
sleep 10

# Verify Redis
redis-cli PING
# Expected: PONG

# Verify PostgreSQL
docker exec postgres-cache-lab pg_isready -U postgres
# Expected: accepting connections

# Verify table exists
docker exec postgres-cache-lab psql -U postgres -d cachedb -c "SELECT COUNT(*) FROM users;"
# Expected: 1000
```

```yaml
# docker-compose.yml
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
      --save ""
      --appendonly no
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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 3
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Basic Cache Operations

```bash
# Set a user profile in Redis with TTL 300 seconds
redis-cli SET user:1:profile '{"id":1,"name":"Alice","email":"alice@example.com"}' EX 300

# Verify TTL
redis-cli TTL user:1:profile
# Expected: 300 (or slightly less, decreasing)

# Get the value back
redis-cli GET user:1:profile
# Expected: {"id":1,"name":"Alice","email":"alice@example.com"}

# Check memory usage
redis-cli DEBUG OBJECT user:1:profile
# Expected: shows encoding, ttl, memory size

# Delete the key
redis-cli DEL user:1:profile

# Verify deletion
redis-cli GET user:1:profile
# Expected: (nil)

# Set again with 60s TTL
redis-cli SET user:2:profile '{"id":2,"name":"Bob"}' EX 60
redis-cli TTL user:2:profile
# Expected: 60

# What happens to TTL when you SET again without EX?
redis-cli SET user:2:profile '{"id":2,"name":"Bobby"}'
redis-cli TTL user:2:profile
# Expected: -1 (no TTL — key won't expire!)
# THIS IS A COMMON BUG: SET without EX removes TTL
```

### 1.2. Negative Caching

```bash
# Simulate "user not found" scenario
# First: verify user 99999 does NOT exist
redis-cli EXISTS user:99999:profile
# Expected: 0

# Without negative caching — set a sentinel
redis-cli SET user:99999:__null__ "1" EX 30

# Query again
redis-cli GET user:99999:profile
# Expected: (nil)

redis-cli GET user:99999:__null__
# Expected: 1 (means "not found, don't query DB")

# Check remaining TTL on null sentinel
redis-cli TTL user:99999:__null__
# Expected: 30 (counting down)

# Question: what happens if we don't have negative caching?
# Simulate: what if DB returns ErrNoRows but we don't cache the null?
# Answer: Every subsequent request will query the DB again
```

### 1.3. Cache Hit/Miss Statistics

```bash
# Reset stats
redis-cli CONFIG RESETSTAT

# First request: cache miss
redis-cli GET user:1:profile
# Expected: (nil) — miss

# Check hit/miss stats
redis-cli INFO stats | grep keyspace
# Expected: keyspace_hits:0, keyspace_misses:1

# Now set the key
redis-cli SET user:1:profile '{"id":1}' EX 300

# Request again: cache hit
redis-cli GET user:1:profile
# Expected: {"id":1}

# Check stats again
redis-cli INFO stats | grep keyspace
# Expected: keyspace_hits:1, keyspace_misses:1
# hit_rate = 1/(1+1) = 50%

# Calculate hit rate manually
# Formula: hits / (hits + misses) * 100
# Hints: use --scan and count pattern
```

### 1.4. Cache Key Patterns & Scanning

```bash
# Insert 50 test keys
for i in $(seq 1 50); do
  redis-cli SET "product:$i:detail" "{\"id\":$i,\"price\":$((RANDOM % 1000))}" EX 600
done

# Scan all product keys
redis-cli --scan --pattern "product:*:detail" | head -10
# Expected: 10 product keys

# Count total product keys
redis-cli --scan --pattern "product:*:detail" | wc -l
# Expected: 50

# Scan for null sentinels
redis-cli SCAN 0 MATCH "user:*:__null__"
# Expected: lists negative cache entries

# Clean up
redis-cli --scan --pattern "product:*" | xargs redis-cli DEL
redis-cli DEL user:1:profile user:2:profile user:99999:__null__
# Verify clean
redis-cli DBSIZE
# Expected: 0
```

### 1.5. TTL and Memory

```bash
# Set maxmemory and eviction policy
redis-cli CONFIG GET maxmemory
# Expected: 268435456 (256MB in bytes)

redis-cli CONFIG GET maxmemory-policy
# Expected: allkeys-lru

# Fill cache to see eviction
for i in $(seq 1 1000); do
  redis-cli SET "fill:$i" "value-$i" EX 3600
done

# Check evicted keys
redis-cli INFO stats | grep evicted_keys
# Expected: > 0 (keys evicted due to maxmemory)

# Monitor memory
redis-cli INFO memory | grep used_memory_human
# Expected: close to maxmemory
```

---

## 2. Hands-on Lab (60-70 phút)

**Scenario**: Xây dựng user service với 3 caching patterns: cache-aside (read), write-through (session), write-behind (analytics events). Đo hit rate, latency p95/p99, và simulate cache stampede.

### 2.1. Project Setup

```bash
mkdir -p day25 && cd day25
go mod init day25

go get github.com/redis/go-redis/v9
go get github.com/lib/pq
go get github.com/jmoiron/sqlx
```

```go
// main.go
package main

import (
    "context"
    "database/sql"
    "encoding/json"
    "fmt"
    "log"
    "math/rand"
    "os"
    "sync"
    "time"

    "github.com/jmoiron/sqlx"
    _ "github.com/lib/pq"
    "github.com/redis/go-redis/v9"
)

// --- Models ---
type User struct {
    ID        int64     `json:"id" db:"id"`
    Name      string    `json:"name" db:"name"`
    Email     string    `json:"email" db:"email"`
    LastLogin time.Time `json:"last_login" db:"last_login"`
}

type AnalyticsEvent struct {
    UserID    int64     `json:"user_id"`
    EventType string    `json:"event_type"`
    Timestamp time.Time `json:"timestamp"`
}

type Order struct {
    ID        int64   `json:"id"`
    UserID    int64   `json:"user_id"`
    Total     float64 `json:"total"`
    Status    string  `json:"status"`
    CreatedAt time.Time `json:"created_at"`
}

// --- Globals ---
var (
    rdb *redis.Client
    db  *sqlx.DB
    ctx = context.Background()
)
```

### 2.2. Cache-Aside Implementation

```go
// cache_aside.go
package main

import (
    "context"
    "database/sql"
    "encoding/json"
    "fmt"
    "log"
    "math/rand"
    "sync"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    UserCacheKey = "user:%d"
    DefaultTTL   = 5 * time.Minute
    NullSuffix   = ":__null__"
)

// GetUser implements cache-aside: check cache first, fallback to DB.
func GetUser(ctx context.Context, rdb *redis.Client, db *sqlx.DB, userID int64) (*User, error) {
    cacheKey := fmt.Sprintf(UserCacheKey, userID)

    // Step 1: Cache lookup
    data, err := rdb.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var u User
        if json.Unmarshal(data, &u) == nil {
            return &u, nil
        }
    }
    if !errors.Is(err, redis.Nil) {
        log.Printf("Redis GET error: %v", err)
    }

    // Step 2: Cache miss — query DB
    var u User
    err = db.GetContext(ctx, &u, `SELECT id, name, email, last_login FROM users WHERE id = $1`, userID)
    if err == sql.ErrNoRows {
        // Negative cache: don't query DB again for 60s
        rdb.Set(ctx, cacheKey+NullSuffix, "1", 60*time.Second)
        return nil, fmt.Errorf("user %d not found", userID)
    }
    if err != nil {
        return nil, fmt.Errorf("db query failed: %w", err)
    }

    // Step 3: Populate cache asynchronously (background)
    go func(id int64, userData User) {
        d, _ := json.Marshal(userData)
        // Add jitter: 0-30s to prevent synchronized expiry
        jitter := time.Duration(rand.Intn(30)) * time.Second
        rdb.Set(ctx, fmt.Sprintf(UserCacheKey, id), d, DefaultTTL+jitter)
    }(userID, u)

    return &u, nil
}

// UpdateUser updates DB and invalidates cache.
func UpdateUser(ctx context.Context, rdb *redis.Client, db *sqlx.DB, userID int64, name, email string) error {
    _, err := db.ExecContext(ctx,
        `UPDATE users SET name=$1, email=$2 WHERE id=$3`,
        name, email, userID)
    if err != nil {
        return fmt.Errorf("update failed: %w", err)
    }

    cacheKey := fmt.Sprintf(UserCacheKey, userID)
    if err := rdb.Del(ctx, cacheKey).Err(); err != nil {
        log.Printf("Cache invalidation failed for %s: %v", cacheKey, err)
    }
    // Also publish event for other instances
    event, _ := json.Marshal(map[string]any{"key": cacheKey, "action": "delete"})
    rdb.Publish(ctx, "cache_invalidation:users", event)

    return nil
}
```

### 2.3. Cache Warming Implementation

```go
// cache_warming.go
package main

import (
    "context"
    "encoding/json"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

const WarmTTL = 10 * time.Minute

// WarmUserCache populates cache with top 100 most recently logged-in users.
func WarmUserCache(ctx context.Context, rdb *redis.Client, db *sqlx.DB) error {
    rows, err := db.QueryxContext(ctx, `
        SELECT id, name, email, last_login FROM users
        ORDER BY last_login DESC LIMIT 100
    `)
    if err != nil {
        return err
    }
    defer rows.Close()

    var count int
    pipe := rdb.Pipeline()

    for rows.Next() {
        var u User
        if err := rows.StructScan(&u); err != nil {
            continue
        }
        data, _ := json.Marshal(u)
        cacheKey := fmt.Sprintf(UserCacheKey, u.ID)
        pipe.Set(ctx, cacheKey, data, WarmTTL)
        count++

        if count%20 == 0 {
            if _, err := pipe.Exec(ctx); err != nil {
                log.Printf("Warm pipeline error: %v", err)
            }
            pipe = rdb.Pipeline()
        }
    }

    if _, err := pipe.Exec(ctx); err != nil {
        return err
    }

    log.Printf("Cache warmed: %d users (TTL=%v)", count, WarmTTL)
    return nil
}
```

### 2.4. Write-Behind Implementation (Analytics Events)

```go
// write_behind.go
package main

import (
    "context"
    "database/sql"
    "encoding/json"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
    "github.com/jmoiron/sqlx"
)

const eventBufferKey = "write_buffer:events"
const eventFlushInterval = 5 * time.Second
const eventBatchSize = 50

// RecordEvent appends event to Redis buffer (write-behind, not immediate DB write).
func RecordEvent(ctx context.Context, rdb *redis.Client, event *AnalyticsEvent) error {
    data, err := json.Marshal(event)
    if err != nil {
        return err
    }
    return rdb.LPush(ctx, eventBufferKey, data).Err()
}

// EventFlushWorker consumes event buffer and flushes to DB in batches.
func EventFlushWorker(ctx context.Context, rdb *redis.Client, db *sqlx.DB) {
    ticker := time.NewTicker(eventFlushInterval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            flushEvents(ctx, rdb, db, 200)
            return
        case <-ticker.C:
            flushed := flushEvents(ctx, rdb, db, eventBatchSize)
            if flushed > 0 {
                log.Printf("Flushed %d events to DB", flushed)
            }
        }
    }
}

func flushEvents(ctx context.Context, rdb *redis.Client, db *sqlx.DB, limit int) int {
    events := make([]AnalyticsEvent, 0, limit)
    for i := 0; i < limit; i++ {
        data, err := rdb.RPop(ctx, eventBufferKey).Bytes()
        if err != nil {
            break
        }
        var e AnalyticsEvent
        if json.Unmarshal(data, &e) == nil {
            events = append(events, e)
        }
    }
    if len(events) == 0 {
        return 0
    }

    tx, err := db.BeginTxx(ctx, nil)
    if err != nil {
        log.Printf("flushEvents: begin failed: %v", err)
        return 0
    }

    for _, e := range events {
        _, err := tx.ExecContext(ctx,
            `INSERT INTO analytics_events (user_id, event_type, created_at)
             VALUES ($1, $2, $3) ON CONFLICT DO NOTHING`,
            e.UserID, e.EventType, e.Timestamp)
        if err != nil {
            tx.Rollback()
            log.Printf("flushEvents: insert failed: %v", err)
            return 0
        }
    }

    if err := tx.Commit(); err != nil {
        log.Printf("flushEvents: commit failed: %v", err)
        return 0
    }
    return len(events)
}
```

### 2.5. Benchmark and Stats Collection

```go
// benchmark.go
package main

import (
    "context"
    "fmt"
    "log"
    "sort"
    "sync"
    "time"

    "github.com/redis/go-redis/v9"
)

type LatencyStats struct {
    mu       sync.Mutex
    samples   []int64
    hits      int64
    misses    int64
    errors    int64
}

func NewLatencyStats() *LatencyStats { return &LatencyStats{} }

func (s *LatencyStats) Record(latencyMs int64, hit bool, err bool) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.samples = append(s.samples, latencyMs)
    if hit {
        s.hits++
    } else if err {
        s.errors++
    } else {
        s.misses++
    }
}

func (s *LatencyStats) Percentile(p float64) int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    if len(s.samples) == 0 {
        return 0
    }
    sorted := make([]int64, len(s.samples))
    copy(sorted, s.samples)
    sort.Slice(sorted, func(i, j int) bool { return sorted[i] < sorted[j] })
    idx := int(float64(len(sorted)) * p)
    if idx >= len(sorted) {
        idx = len(sorted) - 1
    }
    return sorted[idx]
}

func (s *LatencyStats) HitRate() float64 {
    total := s.hits + s.misses
    if total == 0 {
        return 0
    }
    return float64(s.hits) / float64(total) * 100
}

func (s *LatencyStats) Report() {
    s.mu.Lock()
    defer s.mu.Unlock()
    fmt.Println("\n=== Cache Benchmark Report ===")
    fmt.Printf("Total requests:  %d\n", s.hits+s.misses+s.errors)
    fmt.Printf("Cache hits:     %d\n", s.hits)
    fmt.Printf("Cache misses:   %d\n", s.misses)
    fmt.Printf("Errors:         %d\n", s.errors)
    fmt.Printf("Hit rate:       %.2f%%\n", s.HitRate())
    fmt.Printf("p50 latency:    %d ms\n", s.Percentile(0.50))
    fmt.Printf("p95 latency:    %d ms\n", s.Percentile(0.95))
    fmt.Printf("p99 latency:    %d ms\n", s.Percentile(0.99))
    fmt.Printf("Max latency:    %d ms\n", s.Percentile(1.0))
}

// SimulateCacheLoad simulates N concurrent requests to test cache-aside.
func SimulateCacheLoad(rdb *redis.Client, db *sqlx.DB, qps int, duration time.Duration) *LatencyStats {
    stats := NewLatencyStats()
    var wg sync.WaitGroup
    ticker := time.NewTicker(time.Duration(1000000/qps) * time.Microsecond)
    defer ticker.Stop()

    endTime := time.Now().Add(duration)
    requestCount := 0

    for time.Now().Before(endTime) {
        <-ticker.C
        requestCount++
        // Access user IDs in a realistic pattern:
        // 80% of requests: top 20 users (hot)
        // 20% of requests: random users (cold)
        userID := int64(1)
        if requestCount%5 != 0 {
            userID = int64((requestCount%20)+1) // 1-20 (hot)
        } else {
            userID = int64(100 + requestCount%900) // 100-999 (cold)
        }

        wg.Add(1)
        go func(uid int64) {
            defer wg.Done()
            start := time.Now()
            _, err := GetUser(ctx, rdb, db, uid)
            latency := time.Since(start).Milliseconds()
            hit := err == nil
            stats.Record(latency, hit, err != nil)
        }(userID)
    }

    wg.Wait()
    return stats
}

// SimulateCacheStampede simulates 100 concurrent requests for the same key
// right after its TTL expires (cache stampede scenario).
func SimulateCacheStampede(rdb *redis.Client, db *sqlx.DB) {
    log.Println("=== Simulating Cache Stampede ===")

    // First: populate cache for user:999
    _, _ = GetUser(ctx, rdb, db, 999)

    // Force TTL to 1 second
    cacheKey := fmt.Sprintf(UserCacheKey, 999)
    rdb.Expire(ctx, cacheKey, 1*time.Second)
    log.Printf("Cache for user:999 set with TTL=1s")

    // Wait for TTL to expire
    time.Sleep(1100 * time.Millisecond)
    log.Println("TTL expired — now simulating 100 concurrent requests")

    start := time.Now()
    var wg sync.WaitGroup
    var mu sync.Mutex
    dbCalls := 0

    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            // Check if we get a hit or miss
            data, err := rdb.Get(ctx, cacheKey).Bytes()
            mu.Lock()
            if err != nil {
                dbCalls++ // Would trigger DB call
            }
            mu.Unlock()
            _ = data
        }()
    }
    wg.Wait()

    elapsed := time.Since(start)
    log.Printf("Stampede simulation done: %d ms elapsed, ~%d cache misses (would hit DB)", elapsed.Milliseconds(), dbCalls)
}
```

### 2.6. Main — Run All Labs

```go
// main.go continued
func main() {
    // Initialize connections
    rdb = redis.NewClient(&redis.Options{
        Addr:     "localhost:6379",
        PoolSize: 50,
    })
    defer rdb.Close()

    db = sqlx.Connect("postgres", "postgres://postgres:postgres@localhost:5432/cachedb?sslmode=disable")
    if err := db.Ping(); err != nil {
        log.Fatalf("DB connect failed: %v", err)
    }
    defer db.Close()

    // --- Lab A: Warm up cache ---
    log.Println("=== Lab A: Cache Warming ===")
    if err := WarmUserCache(ctx, rdb, db); err != nil {
        log.Printf("Warmup warning: %v", err)
    }

    // --- Lab B: Cache-Aside Benchmark ---
    log.Println("\n=== Lab B: Cache-Aside Benchmark (500 RPS, 30s) ===")
    stats := SimulateCacheLoad(rdb, db, 500, 30*time.Second)
    stats.Report()

    // --- Lab C: Simulate Update + Invalidation ---
    log.Println("\n=== Lab C: Update + Cache Invalidation ===")
    if err := UpdateUser(ctx, rdb, db, 1, "Alice Updated", "alice.updated@example.com"); err != nil {
        log.Printf("Update error: %v", err)
    } else {
        // Verify cache was invalidated
        cacheKey := fmt.Sprintf(UserCacheKey, 1)
        exists, _ := rdb.Exists(ctx, cacheKey).Result()
        log.Printf("Cache key exists after update: %v (expected: 0)", exists == 1)
    }

    // --- Lab D: Write-Behind Events ---
    log.Println("\n=== Lab D: Write-Behind Events ===")
    for i := 0; i < 100; i++ {
        event := &AnalyticsEvent{
            UserID:    int64(i%50 + 1),
            EventType: "page_view",
            Timestamp: time.Now(),
        }
        RecordEvent(ctx, rdb, event)
    }
    log.Println("100 events recorded to Redis buffer (not yet in DB)")

    // Start background flush worker
    flushCtx, cancel := context.WithCancel(ctx)
    go EventFlushWorker(flushCtx, rdb, db)

    // Wait for flush (every 5s, should trigger at least once)
    time.Sleep(7 * time.Second)
    cancel()

    // Verify events in DB
    var count int
    db.Get(&count, "SELECT COUNT(*) FROM analytics_events")
    log.Printf("Events in DB after flush: %d (expected: 100)", count)

    // --- Lab E: Cache Stampede Simulation ---
    log.Println("\n=== Lab E: Cache Stampede Simulation ===")
    SimulateCacheStampede(rdb, db)

    // --- Lab F: Negative Caching ---
    log.Println("\n=== Lab F: Negative Caching ===")
    // First query non-existent user
    _, err := GetUser(ctx, rdb, db, 99999)
    log.Printf("First query user:99999: %v", err)

    // Check null sentinel was set
    nullKey := fmt.Sprintf(UserCacheKey, 99999) + NullSuffix
    nullVal, _ := rdb.Get(ctx, nullKey).Result()
    log.Printf("Negative cache sentinel value: %s (expected: 1)", nullVal)

    // Second query — should be served from negative cache (not DB)
    start := time.Now()
    _, err = GetUser(ctx, rdb, db, 99999)
    elapsed := time.Now().Sub(start)
    log.Printf("Second query user:99999: %v (latency: %v)", err, elapsed)
    // Expected: very fast (cache hit on null sentinel), no DB query

    fmt.Println("\n=== All Labs Complete ===")
}
```

### 2.7. Expected Output

```
=== Lab A: Cache Warming ===
Cache warmed: 100 users (TTL=10m0s)

=== Lab B: Cache-Aside Benchmark (500 RPS, 30s) ===
=== Cache Benchmark Report ===
Total requests:  15000
Cache hits:     12000
Cache misses:   2998
Errors:         2
Hit rate:       80.00%
p50 latency:    0 ms        (cache hit = 0.1-0.5ms, reported as 0)
p95 latency:    2 ms
p99 latency:    5 ms
Max latency:    48 ms       (DB queries on miss)

=== Lab C: Update + Cache Invalidation ===
Cache key exists after update: false (expected: 0)

=== Lab D: Write-Behind Events ===
100 events recorded to Redis buffer (not yet in DB)
Events in DB after flush: 100 (expected: 100)

=== Lab E: Cache Stampede Simulation ===
Cache for user:999 set with TTL=1s
TTL expired — now simulating 100 concurrent requests
Stampede simulation done: ~150 ms elapsed, ~100 cache misses (would hit DB)
--- NOTE: In production, all 100 requests would trigger DB queries simultaneously

=== Lab F: Negative Caching ===
First query user:99999: user 99999 not found
Negative cache sentinel value: 1 (expected: 1)
Second query user:99999: user 99999 not found (latency: 0.3ms)
--- NOTE: Second query served from negative cache, no DB query
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge: Design Consistency Strategy for Order Service

**Scenario**: Xây dựng consistency strategy cho order service:

- 500 orders/second create
- 5.000 order status reads/second
- Order statuses: `pending`, `paid`, `shipped`, `delivered`, `cancelled`
- SLA: order status accuracy > 99.9%, p99 write < 50ms, p99 read < 10ms

**Tasks**:

A) **Design the caching pattern per operation** (create, read status, update status, cancel):

```
Fill in this table:
Operation         | Caching Pattern | TTL | Event Invalidation?
-------------------|----------------|-----|--------------------
Create order      | ???            | ??? | ???
Read order status | ???            | ??? | ???
Update status     | ???            | ??? | ???
Cancel order      | ???            | ??? | ???
```

B) **Implement the solution** in Go with:

- `CreateOrder`: DB transaction first + populate Redis after commit
- `GetOrder`: cache-aside, TTL 30s
- `UpdateOrderStatus`: invalidate cache + publish event
- `CancelOrder`: write-through (synchronous, no async)
- Measure p50/p95/p99 latency for each operation

C) **Simulate consistency failure**: After update, intentionally miss the cache invalidation. Show how long stale data is served with TTL=30s vs TTL=5s. Calculate worst-case impact on order accuracy.

**Hints**:

- For Create: commit DB first, then `SET` cache and `LPUSH` recent orders list
- For Get: cache-aside with 30s TTL
- For Update: `DEL` + publish event + set new value with TTL
- For Cancel: synchronous `SET` (no async) because financial event
- Simulate missed invalidation by commenting out the `DEL` call

---

## 4. Reflection Questions (Open-ended)

1. Bạn đang thiết kế cache cho user profile service. Một user update profile 10 lần trong 5 phút. Mỗi lần update đều invalidate cache. Cache hit rate cho profile đó sẽ rất thấp. Bạn có nên dùng cache-aside không? Đề xuất alternative approach.

2. Một service dùng Redis cho session storage với write-through pattern. Session data cần persisted cho GDPR compliance (audit trail). Write-through đảm bảo data xuống DB nhưng DB write latency = 20ms, gây p99 latency cao. Đề xuất giải pháp giảm latency mà không vi phạm compliance.

3. Negative caching có thể gây security vulnerability nếu attacker biết application logic. Mô tả attack vector và 2 cách phòng ngừa.

4. Cache stampede xảy ra khi hot key expires đồng thời. Ngoài 3 cách đã học (jitter, XFetch, mutex), bạn còn có thể dùng approach nào? (Hint: think about the difference between active and passive refresh strategies, and about the Redis command `PEXPIRE` vs `EXPIRE`).

5. Bạn có 2 options cho consistency: (A) Strong consistency: write-through + no read from replica. (B) Eventual consistency: cache-aside + TTL 5 min. Production SLA: p99 < 100ms, availability > 99.9%. Bạn chọn option nào cho shopping cart service? Giải thích với trade-off cụ thể.

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 TTL behavior**:
```
SET with EX: sets TTL
SET without EX: REMOVES existing TTL (sets to -1, no expiry)
This is a common bug: developers think SET updates key without changing TTL
Fix: always use SETEX or SET with EX when you want to preserve/update TTL
```

**1.2 Negative caching**:
```
Null sentinel key: user:99999:__null__ = "1"
Application logic: if GET returns redis.Nil:
  1. Check null sentinel: GET user:99999:__null__
  2. If sentinel exists: return "not found" immediately (no DB query)
  3. If sentinel doesn't exist: query DB
```

**1.3 Hit rate calculation**:
```
Formula: hits / (hits + misses) * 100
Example: hits=100, misses=20 → hit_rate = 100/120*100 = 83.33%
Alert threshold: < 80% = warning, < 60% = critical
```

---

### Lab Solutions

**2.1 Cache warming verification**:
```bash
# After warmup, verify hot users are cached
redis-cli --scan --pattern "user:[1-20]:profile" | head -5
# Expected: 5-10 keys found (top users 1-20)

redis-cli TTL user:1:profile
# Expected: ~600 (10 minutes)
```

**2.2 Cache-aside hit rate expected**:
```
Pattern: 80% hot (users 1-20), 20% cold (users 100-999)
With TTL=5min + jitter: hot users stay cached
Expected hit rate: 80-85% (some churn on hot due to TTL expiry)

If hit rate < 70%: check if TTL too short or if TTL jitter not implemented
If hit rate > 95%: too much cache, consider if data is stale
```

**2.3 Write-behind flush verification**:
```sql
-- After flush, verify in DB
SELECT COUNT(*), event_type FROM analytics_events
GROUP BY event_type;

-- If count < 100: some events lost or flush interval too short
-- Fix: increase flush interval or manual trigger
```

**2.4 Cache stampede expected output**:
```
Expected: 100 concurrent cache misses after TTL expires
In production without mitigation:
  - All 100 requests query DB simultaneously
  - DB load = 100 queries in ~same millisecond
  - Latency: DB queries queue up, p99 spikes

With jitter (30s): expiry spread over 30s window
  - Only ~3-5 requests miss at any given second
  - DB load: 3-5 queries/second
  - Latency: manageable
```

---

### Challenge Solutions

**A) Pattern table**:
```
Operation         | Caching Pattern | TTL | Event Invalidation?
-------------------|----------------|-----|--------------------
Create order      | DB-first + cache populate | 24h | Optional outbox repair if cache populate fails
Read order status | Cache-aside     | 30s | Yes (status changes)
Update status     | Cache-aside     | 30s | Yes (invalidate + refresh)
Cancel order      | Write-through   | N/A | Yes (sync, critical)
```

**B) Implementation**:

```go
// CreateOrder: DB transaction first, cache after commit
func CreateOrder(ctx context.Context, rdb *redis.Client, db *sqlx.DB, order *Order) error {
    // DB is source of truth. Do not confirm order creation before DB commit.
    tx, err := db.BeginTxx(ctx, nil)
    if err != nil {
        return err
    }
    _, err = tx.ExecContext(ctx, `INSERT INTO orders (id, user_id, total, status, created_at)
                 VALUES ($1,$2,$3,$4,$5) ON CONFLICT (id) DO NOTHING`,
        order.ID, order.UserID, order.Total, order.Status, order.CreatedAt)
    if err != nil {
        tx.Rollback()
        return err
    }
    if err := tx.Commit(); err != nil {
        return err
    }

    // Populate cache after commit. If this fails, DB remains correct; retry via outbox/job.
    cacheKey := fmt.Sprintf("order:%d", order.ID)
    data, _ := json.Marshal(order)
    pipe := rdb.Pipeline()
    pipe.Set(ctx, cacheKey, data, 24*time.Hour)
    pipe.LPush(ctx, fmt.Sprintf("user:%d:orders", order.UserID), data)
    pipe.LTrim(ctx, fmt.Sprintf("user:%d:orders", order.UserID), 0, 9)
    _, err = pipe.Exec(ctx)
    if err != nil {
        // Enqueue cache repair in production; do not rollback committed DB write.
        _ = err
    }
    return nil
}

// GetOrderStatus: cache-aside with TTL
func GetOrderStatus(ctx context.Context, rdb *redis.Client, db *sqlx.DB, orderID int64) (string, error) {
    cacheKey := fmt.Sprintf("order:%d", orderID)
    data, err := rdb.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var o Order
        json.Unmarshal(data, &o)
        return o.Status, nil
    }

    // Cache miss
    var status string
    err = db.Get(&status, `SELECT status FROM orders WHERE id=$1`, orderID)
    if err == sql.ErrNoRows {
        rdb.Set(ctx, cacheKey+"__null__", "1", 60*time.Second)
        return "", fmt.Errorf("order not found")
    }
    if err != nil {
        return "", err
    }

    // Repopulate cache
    var o Order
    db.Get(&o, `SELECT * FROM orders WHERE id=$1`, orderID)
    data, _ = json.Marshal(o)
    rdb.Set(ctx, cacheKey, data, 30*time.Second)
    return status, nil
}

// UpdateOrderStatus: invalidate + set new value
func UpdateOrderStatus(ctx context.Context, rdb *redis.Client, db *sqlx.DB, orderID int64, newStatus string) error {
    // Sync DB write
    _, err := db.Exec(`UPDATE orders SET status=$1 WHERE id=$2`, newStatus, orderID)
    if err != nil {
        return err
    }

    // Invalidate cache
    cacheKey := fmt.Sprintf("order:%d", orderID)
    rdb.Del(ctx, cacheKey)

    // Publish event
    event, _ := json.Marshal(map[string]any{"order_id": orderID, "new_status": newStatus})
    rdb.Publish(ctx, "order_status_update", event)

    return nil
}

// CancelOrder: write-through (synchronous)
func CancelOrder(ctx context.Context, rdb *redis.Client, db *sqlx.DB, orderID int64) error {
    // DB write first (source of truth)
    result, err := db.Exec(`UPDATE orders SET status='cancelled' WHERE id=$1 AND status NOT IN ('cancelled','delivered')`, orderID)
    if err != nil {
        return err
    }
    affected, _ := result.RowsAffected()
    if affected == 0 {
        return fmt.Errorf("order cannot be cancelled")
    }

    // Then update cache
    cacheKey := fmt.Sprintf("order:%d", orderID)
    var o Order
    db.Get(&o, `SELECT * FROM orders WHERE id=$1`, orderID)
    data, _ := json.Marshal(o)
    rdb.Set(ctx, cacheKey, data, 24*time.Hour)

    return nil
}
```

**C) Stale data impact calculation**:
```
Scenario: Cache invalidation missed

TTL = 30s:
  - Stale data window: 30 seconds
  - 5.000 reads/sec × 30s = 150.000 stale reads max
  - Stale read rate: 30s / 30s = 100% of reads in the 30s window
  - Accuracy: 99.9% over 1 hour → (3600-30)/3600 = 99.17% ← FAILS SLA

TTL = 5s:
  - Stale data window: 5 seconds
  - 5.000 reads/sec × 5s = 25.000 stale reads max
  - Accuracy: (3600-5)/3600 = 99.86% ← PASSES SLA

Conclusion: TTL must be ≤ 5s for order status to meet 99.9% accuracy SLA
Event invalidation is critical to achieve < 5s effective stale window
```

---

### Key Takeaways

1. **Cache-aside + TTL jitter**: Đơn giản nhất, hiệu quả cho hầu hết use cases. TTL jitter ngăn cache stampede.
2. **DB-first cho critical writes**: Payment, order creation và cancellation phải commit vào durable store trước khi trả success; Redis chỉ cache/read model sau commit. Chấp nhận latency cao hơn để tránh data loss.
3. **Write-behind cho high-throughput, idempotent writes**: Event analytics, click tracking, logging. Chấp nhận small data loss window.
4. **Event invalidation + TTL safety net**: Hybrid = best of both worlds. Event = near-real-time, TTL = safety net cho missed events.
5. **Negative caching bắt buộc**: Không chỉ cache data, mà còn cache absence. TTL ngắn (30-60s), monitor null key count.
6. **Cache warming**: Chiến lược quan trọng sau Redis restart. Top 100 hot keys cover ~80% traffic.
7. **p95/p99 latency**: Cache hit ~0.5ms, cache miss ~5ms, DB write ~20ms. TTL và jitter ảnh hưởng p99 nhiều hơn p50.
