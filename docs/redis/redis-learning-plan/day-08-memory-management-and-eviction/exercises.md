# Day 8: Memory Management & Eviction — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: Go (go-redis/v9)
**Docker images**: redis:7-alpine

---

## 1. Warm-up Exercises (15–20 phút)

### 1.1. Inspect maxmemory & Eviction Config

```bash
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy
redis-cli CONFIG GET maxmemory-samples
redis-cli CONFIG GET lfu-log-factor
redis-cli CONFIG GET lfu-decay-time
redis-cli CONFIG GET hz
```

**Expected output** (fresh Redis 7):

```
maxmemory: 0                    ← 0 = unlimited (no eviction)
maxmemory-policy: noeviction    ← default
maxmemory-samples: 5            ← default
lfu-log-factor: 10              ← default
lfu-decay-time: 1               ← default (minutes)
hz: 10                          ← timer tick every 100ms
```

### 1.2. Fill Redis to maxmemory và Observe Eviction

```bash
# Set maxmemory = 50MB (small for testing)
redis-cli CONFIG SET maxmemory 50mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Check initial memory
redis-cli INFO memory | grep -E "used_memory|maxmemory|evicted_keys"
```

```bash
# Fill with data (use redis-benchmark for speed)
redis-cli FLUSHALL
redis-cli DBSIZE

# Write 100K keys using pipeline approach
for i in $(seq 1 100000); do
  echo "SET key:$i value:$i"
done | redis-cli --pipe

# Check memory after filling
redis-cli INFO memory | grep -E "used_memory|maxmemory"
```

**Expected output**:
```
used_memory: 47124000     (~45MB used)
maxmemory: 52428800       (50MB limit)
```

### 1.3. Trigger Write Pressure và Observe Eviction

```bash
# Continue writing until eviction starts
redis-cli INFO stats | grep evicted_keys

# Write more keys (should trigger eviction)
for i in $(seq 100001 200000); do
  echo "SET key:$i value:$i"
done | redis-cli --pipe

# Check evicted_keys counter
redis-cli INFO stats | grep evicted_keys
```

**Expected output**:
```
evicted_keys: 12543    ← Redis evicted 12K+ keys to stay under 50MB
```

### 1.4. Inspect OBJECT FREQ & OBJECT IDLETIME

```bash
# Write a key and access it multiple times
redis-cli SET test:lru "hello"
redis-cli GET test:lru
redis-cli GET test:lru
redis-cli GET test:lru

# Check LRU idle time
redis-cli OBJECT IDLETIME test:lru
# Expected: 0-5 seconds (recently accessed)

# Check LFU frequency (if using LFU policy)
redis-cli CONFIG SET maxmemory-policy allkeys-lfu
redis-cli SET test:lfu "world"
for i in {1..20}; do redis-cli GET test:lfu; done

# Check LFU counter
redis-cli OBJECT FREQ test:lfu
# Expected: counter > 0 (LFU increments on access)

# Cleanup
redis-cli DEL test:lru test:lfu
```

### 1.5. Observe noeviction Behavior

```bash
# Set noeviction policy
redis-cli CONFIG SET maxmemory-policy noeviction

# Try to write when memory is full
redis-cli INFO memory | grep used_memory
# Write until OOM error (may take a while with current data)

# Alternative: set very small maxmemory
redis-cli CONFIG SET maxmemory 10mb
redis-cli SET largekey "this is a test value that should trigger OOM when over limit"
```

**Expected output** (when used_memory >= maxmemory):
```
(error) OOM command not allowed when used memory > maxmemory
```

### 1.6. Audit TTL Distribution (for volatile-* validation)

```bash
# Set volatile-lru policy
redis-cli CONFIG SET maxmemory-policy volatile-lru

# Write keys WITHOUT TTL (no TTL = -1)
redis-cli SET noroomkey "value"
redis-cli SET noroomkey2 "value2"

# Check TTL
redis-cli TTL noroomkey
# Expected: -1 (no TTL)

# Write keys WITH TTL
redis-cli SETEX hasttlkey 3600 "value"

# Check TTL
redis-cli TTL hasttlkey
# Expected: ~3600

# Verify: volatile-lru only considers keys with TTL
# (This is why volatile-lru fails when no keys have TTL)
```

---

## 2. Hands-on Lab (60–70 phút)

### Lab Goal

Viết Go program so sánh hit rate giữa `allkeys-lru` và `allkeys-lfu` trên workload có Pareto distribution (80/20 rule). Kết quả sẽ minh chứng tại sao LFU tốt hơn LRU cho Pareto cache.

### Setup: 4 Redis Containers với Different Policies

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis-lru:
    image: redis:7-alpine
    container_name: redis-lru
    command: >
      redis-server
      --maxmemory 100mb
      --maxmemory-policy allkeys-lru
      --maxmemory-samples 5
      --loglevel notice
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-lfu:
    image: redis:7-alpine
    container_name: redis-lfu
    command: >
      redis-server
      --maxmemory 100mb
      --maxmemory-policy allkeys-lfu
      --maxmemory-samples 10
      --lfu-log-factor 10
      --lfu-decay-time 1
      --loglevel notice
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-volatile-lru:
    image: redis:7-alpine
    container_name: redis-volatile-lru
    command: >
      redis-server
      --maxmemory 100mb
      --maxmemory-policy volatile-lru
      --maxmemory-samples 5
      --loglevel notice
    ports:
      - "6381:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-samples:
    image: redis:7-alpine
    container_name: redis-samples
    command: >
      redis-server
      --maxmemory 100mb
      --maxmemory-policy allkeys-lru
      --maxmemory-samples 50
      --loglevel notice
    ports:
      - "6382:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

```bash
docker compose -f docker-compose.yml up -d
sleep 3

# Verify all containers running
docker ps --filter name=redis
```

### Go Starter Code

**File**: `cmd/lab/main.go`

```go
package main

import (
    "context"
    "fmt"
    "log"
    "math/rand"
    "strconv"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

// Configuration
const (
    totalKeys       = 50_000  // total unique keys in dataset
    cacheCapacity    = 10_000  // approximate keys Redis can hold (100MB / ~10KB per key)
    valueSizeBytes   = 10 * 1024
    workloadSize    = 500_000  // total accesses in the simulation
    hotKeyFraction  = 0.20    // 20% of keys are "hot" (80/20 rule)
    hotAccessFraction = 0.80 // 80% of accesses go to hot keys
)

// Pareto distribution: 80% of accesses hit 20% of keys
func paretoAccess(r *rand.Rand, hotCount, totalCount int) string {
    if r.Float64() < hotAccessFraction {
        // Access hot key (80% probability)
        hotIdx := r.Intn(hotCount)
        return fmt.Sprintf("cache:hot:%05d", hotIdx)
    } else {
        // Access cold key (20% probability)
        coldIdx := r.Intn(totalCount - hotCount)
        return fmt.Sprintf("cache:cold:%05d", coldIdx)
    }
}

func main() {
    ctx := context.Background()
    // Connect to 4 Redis instances
    clients := map[string]*redis.Client{
        "lru":      redis.NewClient(&redis.Options{Addr: "localhost:6379"}),
        "lfu":      redis.NewClient(&redis.Options{Addr: "localhost:6380"}),
        "volatile-lru": redis.NewClient(&redis.Options{Addr: "localhost:6381"}),
        "samples-50": redis.NewClient(&redis.Options{Addr: "localhost:6382"}),
    }

    // Cleanup
    defer func() {
        for name, rdb := range clients {
            rdb.Close()
            fmt.Printf("Closed %s\n", name)
        }
    }()

    // Verify connectivity
    for name, rdb := range clients {
        if err := rdb.Ping(ctx).Err(); err != nil {
            log.Fatalf("[%s] Cannot connect: %v", name, err)
        }
        fmt.Printf("[%s] Connected OK\n", name)
    }

    // Phase 1: Fill Redis to maxmemory (with TTL for volatile-lru test)
    fmt.Println("\n=== Phase 1: Fill Redis to maxmemory ===")
    hotCount := int(float64(totalKeys) * hotKeyFraction)
    coldCount := totalKeys - hotCount

    for name, rdb := range clients {
        // For volatile-lru: set TTL on all keys
        // For others: no TTL (allkeys-*)
        hasTTL := (name == "volatile-lru")

        fillStart := time.Now()
        pipe := rdb.Pipeline()
        count := 0

        for i := 0; i < totalKeys; i++ {
            key := fmt.Sprintf("cache:hot:%05d", i)
            if i >= hotCount {
                key = fmt.Sprintf("cache:cold:%05d", i-hotCount)
            }
            prefix := fmt.Sprintf("value-%08d:", i)
            value := prefix + strings.Repeat("x", valueSizeBytes-len(prefix))

            if hasTTL {
                pipe.SetEx(ctx, key, value, 3600*time.Second)
            } else {
                pipe.Set(ctx, key, value, 0)
            }
            count++

            if count%5000 == 0 {
                _, err := pipe.Exec(ctx)
                if err != nil {
                    log.Fatalf("[%s] Fill error at %d: %v", name, i, err)
                }
                pipe = rdb.Pipeline()
            }
        }
        _, err := pipe.Exec(ctx)
        if err != nil {
            log.Fatalf("[%s] Final fill error: %v", name, err)
        }

        fillDur := time.Since(fillStart)
        info, _ := rdb.Do(ctx, "INFO", "memory").Text()
        usedMem := parseField(info, "used_memory")

        fmt.Printf("[%s] Filled %d keys in %v | used_memory: %.2fMB\n",
            name, totalKeys, fillDur, float64(usedMem)/1024/1024)
    }

    // Phase 2: Record evicted_keys count BEFORE workload
    fmt.Println("\n=== Phase 2: Baseline evicted_keys ===")
    evictedBefore := map[string]int64{}
    for name, rdb := range clients {
        info, _ := rdb.Do(ctx, "INFO", "stats").Text()
        evictedBefore[name] = parseField(info, "evicted_keys")
        fmt.Printf("[%s] evicted_keys baseline: %d\n", name, evictedBefore[name])
    }

    // Phase 3: Run Pareto workload simulation
    fmt.Println("\n=== Phase 3: Pareto Workload Simulation ===")
    fmt.Printf("Total accesses: %d | Hot: %d keys (%.0f%%) | Cold: %d keys | Approx capacity: %d keys\n",
        workloadSize, hotCount, hotKeyFraction*100, coldCount, cacheCapacity)
    fmt.Printf("Access pattern: %.0f%% accesses → %.0f%% hot keys (Pareto)\n",
        hotAccessFraction*100, hotKeyFraction*100)

    results := map[string]struct {
        hits    int64
        misses  int64
        hitRate float64
    }{}

    for name, rdb := range clients {
        clientRand := rand.New(rand.NewSource(42)) // same access pattern for each policy
        hits, misses := runParetoWorkload(ctx, rdb, clientRand, hotCount, totalKeys, workloadSize, name == "volatile-lru")
        hitRate := float64(hits) / float64(hits+misses) * 100
        results[name] = struct {
            hits    int64
            misses  int64
            hitRate float64
        }{hits, misses, hitRate}
        fmt.Printf("[%s] Hits: %d | Misses: %d | Hit Rate: %.2f%%\n",
            name, hits, misses, hitRate)
    }

    // Phase 4: Post-workload evicted_keys
    fmt.Println("\n=== Phase 4: Post-workload evicted_keys ===")
    for name, rdb := range clients {
        info, _ := rdb.Do(ctx, "INFO", "stats").Text()
        evicted := parseField(info, "evicted_keys")
        evictedThisRun := evicted - evictedBefore[name]
        fmt.Printf("[%s] evicted_keys: total=%d, this_run=%d\n",
            name, evicted, evictedThisRun)
    }

    // Phase 5: Summary
    fmt.Println("\n=== Phase 5: Summary ===")
    fmt.Printf("%-15s | %10s | %10s | %12s | %10s\n",
        "Policy", "Hits", "Misses", "Hit Rate", "Evicted")
    fmt.Println(strings.Repeat("-", 65))
    for name := range clients {
        r := results[name]
        info, _ := clients[name].Do(ctx, "INFO", "stats").Text()
        evicted := parseField(info, "evicted_keys") - evictedBefore[name]
        fmt.Printf("%-15s | %10d | %10d | %11.2f%% | %10d\n",
            name, r.hits, r.misses, r.hitRate, evicted)
    }
}

func runParetoWorkload(ctx context.Context, rdb *redis.Client, r *rand.Rand,
    hotCount, totalCount, accesses int, hasTTL bool) (int64, int64) {
    var hits, misses int64

    start := time.Now()
    for i := 0; i < accesses; i++ {
        key := paretoAccess(r, hotCount, totalCount)

        val, err := rdb.Get(ctx, key).Result()
        if err == redis.Nil {
            misses++
            prefix := fmt.Sprintf("value-reload-%08d:", i)
            value := prefix + strings.Repeat("x", valueSizeBytes-len(prefix))
            if hasTTL {
                _ = rdb.SetEx(ctx, key, value, 3600*time.Second).Err()
            } else {
                _ = rdb.Set(ctx, key, value, 0).Err()
            }
        } else if err != nil {
            // Log error but continue
        } else {
            _ = val // use value to avoid compiler warning
            hits++
        }

        if (i+1)%50000 == 0 {
            elapsed := time.Since(start)
            rate := float64(i+1) / elapsed.Seconds()
            fmt.Printf("  [%s] %d/%d accesses (%.0f ops/sec)\n",
                rdb.Options().Addr, i+1, accesses, rate)
        }
    }

    return hits, misses
}

func parseField(info, key string) int64 {
    for _, line := range strings.Split(info, "\n") {
        line = strings.TrimSpace(line)
        if strings.HasPrefix(line, key+":") {
            val := strings.TrimPrefix(line, key+":")
            v, _ := strconv.ParseInt(strings.TrimSpace(val), 10, 64)
            return v
        }
    }
    return 0
}
```

**Hint 1** (nếu gặp error): Pareto distribution tạo access pattern có 80% hits → nhưng với cache capacity = 10K và total keys = 50K, miss rate sẽ cao. Điều chỉnh `cacheCapacity` hoặc `totalKeys` để thấy rõ hit rate difference giữa LRU và LFU.

**Hint 2** (nếu hit rate tương đương): LRU và LFU cho kết quả gần nhau khi workload không đủ "Pareto". Thử tăng `hotAccessFraction` lên 0.95 (95% accesses → 20% hot keys).

**Hint 3** (nếu volatile-lru evict 0 keys): `volatile-lru` chỉ hoạt động trên keys có TTL. Trong Phase 1, keys đã được SET với TTL. Kiểm tra: `redis-cli -p 6381 TTL cache:hot:00000`.

**Expected output** (approximate):

```
=== Phase 5: Summary ===
Policy         |      Hits |     Misses |   Hit Rate |    Evicted
-----------------------------------------------------------------
lru            |    412000 |      88000 |     82.40% |     40123
lfu            |    435000 |      65000 |     87.00% |     40123
volatile-lru   |    401000 |      99000 |     80.20% |     40123
samples-50     |    415000 |      85000 |     83.00% |     40123
```

**Interpretation**:
- LFU beat LRU by ~4-5% hit rate (LFU keeps hot keys longer)
- Higher `maxmemory-samples` = slightly better LRU accuracy
- `volatile-lru` slightly worse (TTL adds overhead)
- All policies evicted similar number of keys (~40K = 50K - 10K)

### Bonus: LFU Counter Growth Observation

Thêm vào cuối `main()`:

```go
// Bonus: Observe LFU counter distribution on LFU instance
fmt.Println("\n=== Bonus: LFU Counter Distribution ===")
rdbLFU := clients["lfu"]
dist := make(map[int]int)

iter := rdbLFU.Scan(ctx, 0, "cache:hot:*", 0).Iterator()
count := 0
for iter.Next(ctx) {
    key := iter.Val()
    freq, _ := rdbLFU.Do(ctx, "OBJECT", "FREQ", key).Int64()
    dist[int(freq)]++
    count++
}
iter.Err()

var hotKeys int
var avgFreq float64
for freq, cnt := range dist {
    hotKeys += cnt
    avgFreq += float64(freq) * float64(cnt)
}
avgFreq /= float64(hotKeys)

fmt.Printf("Sampled %d hot keys on LFU instance\n", hotKeys)
fmt.Printf("Average LFU counter for hot keys: %.1f\n", avgFreq)
fmt.Println("LFU counter distribution (sample):")
for freq := 0; freq <= 20; freq++ {
    if cnt, ok := dist[freq]; ok && cnt > 0 {
        fmt.Printf("  freq=%2d: %d keys\n", freq, cnt)
    }
}
```

---

## 3. Challenge Exercise (30–40 phút)

### Challenge A: Thiết kế Eviction Policy cho 3 Use Cases

**Yêu cầu**: Đọc 3 scenarios dưới đây. Với mỗi scenario, chọn eviction policy + `maxmemory-samples` + giải thích tại sao. Viết config vào file `solutions/challenge-a.txt`.

#### Scenario 1: API Response Cache (E-commerce Product Catalog)

```
- Dataset: 2M product pages
- Traffic: 100K reads/sec, 1K writes/sec (product updates)
- Pattern: 80/20 Pareto (20% products = 80% traffic)
- Hot products: top 10,000 products (0.5% of catalog)
- Cache size limit: 5GB (can only hold 10% of catalog)
- Data loss acceptable: yes (rebuild from DB)
- Write pattern: product price/stock updates, 1K/sec
```

**Chọn eviction policy**: ?

**maxmemory-samples**: ?

**Lý do**: (viết 2-3 câu giải thích)

**Config**:
```txt
```

#### Scenario 2: User Session Store (SaaS Application)

```
- Dataset: 500K active sessions
- Traffic: 50K reads/sec, 10K writes/sec (session updates)
- Pattern: recency (recent users more likely to make requests)
- Session TTL: 30 minutes (EXPIRE set on each access)
- Mixed data: 80% session keys (TTL) + 20% user preferences (no TTL)
- Cache size limit: 8GB
- Data loss: NOT acceptable (user logged out = bad UX)
- Write pattern: session read/write on every request
```

**Chọn eviction policy**: ?

**maxmemory-samples**: ?

**Lý do**: (viết 2-3 câu giải thích)

**Config**:
```txt
```

#### Scenario 3: Distributed Rate Limiter (API Gateway)

```
- Dataset: 10M rate limit counters (key = user_id:endpoint)
- Traffic: 1M requests/sec reads, 1M requests/sec writes (increment)
- Pattern: uniform random (each user equally likely)
- No TTL on counters (counters reset via sliding window algorithm in app)
- Cache size limit: 2GB
- Data loss: NOT acceptable (rate limit fail-open = abuse)
- Write pattern: INCR on every request
```

**Chọn eviction policy**: ?

**maxmemory-samples**: ?

**Lý do**: (viết 2-3 câu giải thích)

**Config**:
```txt
```

### Challenge B: Phân tích Incident

**File**: `solutions/challenge-b.md`

Một team gặp incident sau. Phân tích root cause và đề xuất fix.

```
Incident: API cache hit rate dropped from 95% to 40% overnight.

Background:
- Redis instance: 32GB RAM, maxmemory=28GB
- Policy: allkeys-lru
- maxmemory-samples: 5
- Dataset: 5M keys, avg key size = 2KB (total ~10GB)
- Used memory: 27.5GB (98% of maxmemory)

Timeline:
- 02:00 AM: Deployment pushed (cache warmer updated)
- 02:00-04:00 AM: Cache warming, keys reloaded
- 06:00 AM: Peak traffic starts
- 06:00-08:00 AM: Hit rate drops from 95% to 40%
- 08:00 AM: Database starts overloaded (cache miss → DB query)
- 08:30 AM: Incident declared

Investigation findings:
- evicted_keys: 2.5M (2.5M keys evicted in 2 hours)
- used_memory: stable at 27.5GB (eviction keeping up with pressure)
- New cache warmer: loaded keys WITHOUT TTL
- Old cache warmer: loaded keys WITH TTL = 1 hour

Questions:
1. Tại sao eviction rate tăng đột ngột sau deployment?
2. Tại sao hit rate không recover khi eviction loop đang hoạt động?
3. Tại sao allkeys-lru evict hot keys thay vì cold keys?
4. Fix ngắn hạn (immediate) là gì?
5. Fix dài hạn (long-term) là gì?
```

### Challenge C: Tune maxmemory-samples

**File**: `solutions/challenge-c.go`

Viết benchmark đo p99 latency impact của `maxmemory-samples`. Chạy với 3 giá trị: 3, 10, 50. So sánh latency distribution.

```go
// Starter: benchmark eviction latency at different maxmemory-samples values
//
// 1. Connect to redis-samples (port 6382, already configured with samples=50)
// 2. CONFIG SET maxmemory-samples to 3, 10, 50
// 3. Flush DB, then prefill Redis close to maxmemory
// 4. Write 100K ~10KB keys (each write should trigger eviction)
// 5. Measure p50, p95, p99 latency per write
// 6. Compare across samples values

package main

import (
    "context"
    "fmt"
    "sort"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6382"})
    defer rdb.Close()

    // Test with different maxmemory-samples values
    for _, samples := range []int{3, 10, 50} {
        if err := rdb.FlushDB(ctx).Err(); err != nil {
            panic(err)
        }
        if err := rdb.ConfigSet(ctx, "maxmemory-samples", fmt.Sprintf("%d", samples)).Err(); err != nil {
            panic(err)
        }

        value := strings.Repeat("x", 10*1024)

        // Prefill enough data so Redis is already under memory pressure.
        for i := 0; i < 15_000; i++ {
            if err := rdb.Set(ctx, fmt.Sprintf("prefill:%d:%d", samples, i), value, 0).Err(); err != nil {
                panic(err)
            }
        }

        // Measure write latencies
        latencies := make([]time.Duration, 100_000)
        for i := 0; i < 100_000; i++ {
            key := fmt.Sprintf("bench:sample:%d:%d", samples, i)
            start := time.Now()
            if err := rdb.Set(ctx, key, value, 0).Err(); err != nil {
                panic(err)
            }
            latencies[i] = time.Since(start)
        }

        // Calculate percentiles
        sort.Slice(latencies, func(i, j int) bool {
            return latencies[i] < latencies[j]
        })

        p50 := latencies[len(latencies)*50/100]
        p95 := latencies[len(latencies)*95/100]
        p99 := latencies[len(latencies)*99/100]

        fmt.Printf("samples=%d: p50=%.3fms p95=%.3fms p99=%.3fms\n",
            samples, float64(p50)/1e6, float64(p95)/1e6, float64(p99)/1e6)

        // Cleanup
        if err := rdb.FlushDB(ctx).Err(); err != nil {
            panic(err)
        }
    }
}
```

---

## 4. Reflection Questions

### Question 1
**Bạn đang thiết kế Redis cache cho news feed (NganLuong/VN). Feed items có recency pattern rõ ràng: bài mới đăng = nhiều views, bài cũ 1 tuần = ít views. Tuy nhiên, bạn cũng có "evergreen content" (bài viral từ 6 tháng trước vẫn nhận 10K views/ngày). Bạn sẽ chọn LRU hay LFU? Tại sao?**

Gợi ý suy nghĩ:
- Recency pattern: bài mới → nhiều views (LRU advantage)
- Frequency pattern: evergreen viral content → được access thường xuyên (LFU advantage)
- Mixed pattern: cả 2 loại content tồn tại đồng thời

### Question 2
**`maxmemory-samples` mặc định = 5. Tại sao Redis không dùng sample size lớn hơn (VD: 50 hoặc 100) mặc định? Trade-off thực sự là gì?**

### Question 3
**Bạn phát hiện `volatile-lru` evict 0 keys trên production. Bạn có 2 lựa chọn: (A) switch sang `allkeys-lru`, (B) fix application để all session keys có TTL. Bạn chọn cái nào và tại sao?**

### Question 4
**Trong lab, bạn thấy LFU beat LRU cho Pareto workload. Tuy nhiên, trên production workload thực tế, LRU vẫn được dùng phổ biến hơn. Giải thích 2 lý do thực tế khiến LRU vẫn là lựa chọn tốt trong nhiều trường hợp.**

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết cho tất cả bài tập. Đọc sau khi đã thử làm.

### Warm-up Solutions

**1.1** — Default eviction config:
```
maxmemory: 0 (unlimited, no eviction)
maxmemory-policy: noeviction
maxmemory-samples: 5
lfu-log-factor: 10
lfu-decay-time: 1
hz: 10
```

**1.2–1.3** — Expected evicted_keys > 0 khi Redis full. Nếu `evicted_keys = 0` sau khi write > maxmemory → kiểm tra `CONFIG GET maxmemory-policy` (có thể = noeviction).

**1.4** — `OBJECT FREQ` trả về LFU counter (0-255). Counter tăng khi key được accessed. `OBJECT IDLETIME` trả về seconds since last access.

**1.5** — `noeviction` + full Redis = OOM error on writes. Read commands vẫn hoạt động.

**1.6** — `volatile-lru` chỉ evict keys có TTL. Keys without TTL (TTL = -1) bị bỏ qua trong eviction loop.

### Hands-on Lab Solutions

**Phase 1 (Fill)**: Tất cả 4 instances nên fill thành công. Redis với `maxmemory 100mb` có thể chứa ~50K small keys. Nếu fill fail → kiểm tra `used_memory` trước fill.

**Phase 3 (Pareto Workload)**:

LRU vs LFU analysis:
```
LRU weakness in Pareto workload:
  - Key accessed 1000 times/hour but not for 2 minutes → LRU says "old"
  - Key accessed 1 time 2 minutes ago → LRU says "newer"
  - LRU evict hot-but-not-recently-accessed keys

LFU strength in Pareto workload:
  - Hot key (1000 accesses/hour) → counter saturates to high value
  - Cold key (1 access/hour) → counter stays low
  - LFU keeps hot keys despite recency gaps
```

**Expected hit rate differences**:
- LFU: 85-90% hit rate (best for Pareto)
- LRU: 78-84% hit rate
- `volatile-lru`: tương đương LRU (không khác nhiều trong experiment này)
- `samples-50` (LRU with 50 samples): ~80-85% (better than samples=5)

**Phase 5 (Summary)**:
```
allkeys-lru (samples=5):  ~80-84% hit rate
allkeys-lfu:              ~85-90% hit rate (+4-6% vs LRU)
volatile-lru:             ~78-82% hit rate (similar to LRU)
allkeys-lru (samples=50): ~82-86% hit rate (+2-4% vs samples=5)
```

### Challenge Solutions

**Challenge A**:

**Scenario 1 (API Response Cache)**:
```txt
maxmemory 5gb
maxmemory-policy allkeys-lfu      # Pareto pattern: hot 20% = 80% traffic
maxmemory-samples 10               # Balance accuracy vs CPU
lfu-log-factor 10                  # Default, adjust down if counter too slow
lfu-decay-time 5                   # 5 min decay (hot products stay hot longer)
```

**Tại sao LFU**: E-commerce product catalog có 80/20 pattern rõ ràng. Top 10K products (0.5% catalog) nhận 80% traffic. LFU giữ hot products trong cache dù có gaps trong access pattern.

**Scenario 2 (Session Store)**:
```txt
maxmemory 8gb
maxmemory-policy volatile-lru      # Sessions have TTL, evict only sessions
maxmemory-samples 5
```

**Tại sao volatile-lru**: Sessions có TTL = 30 phút. Dùng `volatile-*` để chỉ evict session keys, không evict user preferences (persistent data). **Validation bắt buộc**: Kiểm tra tất cả session keys có TTL.

**Scenario 3 (Rate Limiter)**:
```txt
maxmemory 2gb
maxmemory-policy noeviction        # Rate limit data loss = abuse risk
```

**Tại sao noeviction**: Rate limiter counters không chấp nhận mất data. Nếu counter bị evict → request allowed without rate limit → abuse. **Caveat**: Cần monitor `used_memory` và scale khi > 80% capacity.

**Challenge B**:

1. **Tại sao eviction rate tăng đột ngột sau deployment?**
   - Cache warmer mới load keys **KHÔNG có TTL**
   - Old cache warmer: keys có TTL = 1 giờ → expired + evicted naturally
   - New cache warmer: keys không có TTL → tích lũy trong memory
   - 5M keys × 2KB = 10GB → eviction bắt đầu khi Redis full

2. **Tại sao hit rate không recover khi eviction đang hoạt động?**
   - `allkeys-lru` evict **bất kỳ key nào** (hot hoặc cold)
   - Hot keys được access thường xuyên → LRU luôn update → hot keys luôn "young"
   - NHƯNG: eviction loop chạy **mỗi write** và sample 5 keys ngẫu nhiên
   - Xác suất sample = 5 / 5M = 0.0001%. Mỗi eviction round chỉ check 5 keys
   - Hot key có thể 1 triệu lần access nhưng vẫn bị evict vì không được sampled
   - → Cache liên tục evict hot keys, reload → hit rate không recover

3. **Tại sao allkeys-lru evict hot keys?**
   - Sample-based LRU: chỉ check 5 keys/sample
   - Hot key accessed 1 triệu lần/giờ nhưng không được sampled → vẫn bị evict
   - True LRU sẽ giữ hot key → sample-based LRU không đảm bảo điều này

4. **Fix ngắn hạn**:
   ```bash
   # Immediate: switch to LFU
   redis-cli CONFIG SET maxmemory-policy allkeys-lfu
   redis-cli CONFIG SET lfu-log-factor 5
   ```
   Hoặc: `CONFIG SET maxmemory-samples 50` (better LRU accuracy).

5. **Fix dài hạn**:
   - Fix cache warmer: thêm TTL vào tất cả keys
   - Switch to `allkeys-lfu` permanent
   - Monitor `OBJECT FREQ` trên hot keys
   - Tune `lfu-log-factor` dựa trên workload

**Challenge C**:

Expected results:
```
samples=3:  p50=0.100ms p95=0.250ms p99=1.200ms
samples=10: p50=0.105ms p95=0.280ms p99=1.400ms
samples=50: p50=0.120ms p95=0.350ms p99=2.000ms
```

**Analysis**: Increasing samples from 3 to 50 adds ~0.1ms to p99 latency. Benefit: better eviction accuracy (less likely to evict hot keys). Cost: slightly higher per-write latency.

### Reflection Solutions

**Question 1**: Mixed workload cần hybrid approach. Pure LRU hoặc pure LFU không ideal. Options:
- Dùng `allkeys-lfu` (LFU advantage for evergreen content)
- Hoặc: 2 Redis instances (LRU instance cho new content, LFU instance cho evergreen)
- Hoặc: Tune `lfu-decay-time` dài (VD: 60 phút) để LFU counter decay chậm → hot-but-old content vẫn giữ counter cao

**Question 2**: Default = 5 vì:
- Sample size lớn hơn = eviction loop chậm hơn → event loop blocked lâu hơn
- CPU cost per eviction round: O(5) = negligible; O(100) = measurable
- 5 samples đủ accurate cho 80% use cases (cache với millions keys)
- LRU/LFU không bao giờ "perfect" → samples > 5 không cải thiện meaningful

**Question 3**: Chọn **(A) switch sang `allkeys-lru`** trước (fix ngắn hạn), sau đó (B) fix application. Lý do:
- `volatile-lru` với 0 TTL keys = 0 eviction = OOM → production down
- `allkeys-lru` evict bất kỳ key nào → writes continue → system hoạt động
- Fix application (add TTL) là đúng design nhưng cần thời gian

**Question 4**: LRU vẫn phổ biến vì:
1. **Simpler tuning**: LRU không có counter saturation issue. LFU yêu cầu tune `lfu-log-factor` và `lfu-decay-time` đúng workload. Nếu tune sai → LFU counter "stuck" → worse than LRU.
2. **Most workloads aren't pure Pareto**: Many production workloads have recency pattern (recent data accessed more) but NOT strong frequency pattern (all data accessed uniformly). LRU works well for recency, not harmful when frequency doesn't matter.
