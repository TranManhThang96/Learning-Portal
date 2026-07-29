# Day 8: Memory Management & Eviction — Reference Document

## 1. Cheat Sheet: Eviction Commands

```txt
-- CONFIG: maxmemory & eviction policy
CONFIG GET maxmemory
CONFIG SET maxmemory 10gb
CONFIG GET maxmemory-policy
CONFIG SET maxmemory-policy allkeys-lru
CONFIG GET maxmemory-samples
CONFIG SET maxmemory-samples 10

-- LFU specific configs
CONFIG GET lfu-log-factor
CONFIG SET lfu-log-factor 10
CONFIG GET lfu-decay-time
CONFIG SET lfu-decay-time 1

-- INFO: eviction monitoring
INFO memory | grep -E "used_memory|maxmemory|evicted_keys"
INFO stats | grep evicted_keys
INFO stats | grep expired_keys

-- Inspect LRU/LFU metadata
OBJECT FREQ keyname          -- LFU counter value (0-255)
OBJECT IDLETIME keyname      -- seconds since last access (LRU)
DEBUG OBJECT keyname         -- full object metadata including lru/lfu field

-- TTL distribution audit
TTL keyname                  -- -1 = no TTL, -2 = no key, >0 = TTL seconds
-- Sample audit:
redis-cli --scan | head -1000 | xargs -I{} redis-cli TTL {}
```

---

## 2. Config Snippets cho 4 Scenario

### API Response Cache (Pareto / LFU)

```txt
# File: redis-api-cache.conf
maxmemory 10gb
maxmemory-policy allkeys-lfu
maxmemory-samples 10
lfu-log-factor 10              # default, adjust down to 1-5 if counter too slow
lfu-decay-time 5               # counter decays every 5 minutes (default 1)

# Monitoring
# Alert: evicted_keys > 0 (eviction means cache is under pressure)
# Alert: used_memory > 8gb (80% of 10gb = scale trigger)
```

### Session Store (volatile-lru)

```txt
# File: redis-session-store.conf
maxmemory 8gb
maxmemory-policy volatile-lru
maxmemory-samples 5

# WARNING: All session keys MUST have TTL set
# Verify: redis-cli --scan | head -1000 | xargs redis-cli TTL | grep -- "-1$" | wc -l
# If > 0 keys have no TTL → switch to allkeys-lru or fix application code
```

### Idempotency Store / Counter (noeviction)

```txt
# File: redis-idempotency.conf
maxmemory 2gb
maxmemory-policy noeviction

# CRITICAL: Monitor used_memory
# Alert: used_memory > 1.6gb (80% of 2gb) → scale trigger
# Policy = noeviction means writes FAIL when full
# This is INTENTIONAL: data loss not acceptable
# Primary protection: capacity planning + scale trigger

# Complementary: PostgreSQL unique constraint for idempotency tokens
# Redis = fast path, PostgreSQL = durable path
```

### Leaderboard / Sorted Set Cache (allkeys-lru)

```txt
# File: redis-leaderboard.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Leaderboard keys don't have natural TTL
# LRU evict based on recency of ZRANGE/ZADD access
```

---

## 3. Reference Tables cho 8 Eviction Policies

### Policy Summary

| Policy | Key pool | Sort key | Best for | Risk |
|--------|----------|-----------|---------|------|
| `noeviction` | all | none (reject writes) | Idempotency, counters | Write failure under pressure |
| `allkeys-lru` | all keys | oldest LRU | Generic cache, recency pattern | May evict persistent data |
| `volatile-lru` | TTL keys only | oldest LRU | Session store | 0 evictions if no TTL keys |
| `allkeys-lfu` | all keys | lowest LFU counter | Pareto cache, frequency pattern | LFU counter tuning complexity |
| `volatile-lfu` | TTL keys only | lowest LFU counter | Cache with TTL key majority | 0 evictions if no TTL keys |
| `allkeys-random` | all keys | random | Load test, sampling cache | Non-deterministic |
| `volatile-random` | TTL keys only | random | Fallback for volatile-* when TTL keys exist | 0 evictions if no TTL keys |
| `volatile-ttl` | TTL keys only | shortest TTL first | Priority cache (low TTL = less important) | Low TTL keys evicted aggressively |

### Use Case Mapping

| Use Case | Recommended Policy | Alternatives |
|----------|-------------------|---------------|
| API response cache (Pareto) | `allkeys-lfu` | `allkeys-lru` |
| Session store (TTL-based) | `volatile-lru` | `allkeys-lru` |
| Rate limit counter | `noeviction` | `allkeys-lru` (if loss acceptable) |
| Idempotency token | `noeviction` | N/A (data loss not acceptable) |
| CDN cache | `allkeys-lfu` | `allkeys-lru` |
| Leaderboard (no TTL) | `allkeys-lru` | `allkeys-random` |
| Temporary cache (< 1h TTL) | `volatile-ttl` | `volatile-lru` |
| Load test / benchmark | `allkeys-random` | N/A |

### Policy Pros/Cons

| Policy | Pros | Cons |
|--------|------|------|
| `noeviction` | No data loss (writes fail explicitly) | Write failure under pressure, capacity planning required |
| `allkeys-lru` | Simple, works for any dataset | Not true LRU (sample-based), may evict hot keys |
| `volatile-lru` | Respects TTL (session use case ideal) | 0 evictions if no TTL keys → OOM risk |
| `allkeys-lfu` | Perfect for Pareto/frequency workloads | Counter tuning complexity, slow initial counter growth |
| `volatile-lfu` | Frequency + TTL awareness | 0 evictions if no TTL keys |
| `allkeys-random` | Fastest eviction loop, predictable memory | Non-deterministic, may evict hot keys |
| `volatile-random` | Fallback when only TTL keys should evict | 0 evictions if no TTL keys |
| `volatile-ttl` | Priority-based eviction | Aggressive on low-TTL keys, unpredictable |

---

## 4. Production Config Template

### Template: Cache-Primary Redis

```txt
# maxmemory = 70-80% of container RAM
maxmemory 10gb
maxmemory-policy allkeys-lfu
maxmemory-samples 10
lfu-log-factor 10
lfu-decay-time 5

# Active defrag (Day 9: Memory Optimization)
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10
active-defrag-threshold-upper 100
```

### Template: Session Store

```txt
maxmemory 8gb
maxmemory-policy volatile-lru
maxmemory-samples 5

# Alert rules:
# - evicted_keys > 0 → eviction happening (possible misconfiguration)
# - used_memory > 6.4gb (80%) → scale trigger
# - All session keys MUST have TTL (audit periodically)
```

### Template: Idempotency / Durable Store

```txt
maxmemory 2gb
maxmemory-policy noeviction

# Alert rules:
# - used_memory > 1.6gb (80%) → CRITICAL: scale immediately
# - evicted_keys > 0 → should NEVER happen with noeviction
#   If > 0: means eviction policy was changed, investigate immediately

# Complementary:
# - PostgreSQL unique constraint on idempotency_token
# - Redis TTL = 24h (cleanup old tokens)
# - Redis = fast path, PostgreSQL = source of truth
```

### Template: Mixed (if 1 instance required)

```txt
# When 2 instances not possible:
maxmemory 12gb
maxmemory-policy allkeys-lru   # evict ANY key, respects both session and cache
maxmemory-samples 10

# Trade-off: sessions (with TTL) and persistent cache both eligible for eviction
# Use when: cannot guarantee all session keys have TTL
```

---

## 5. INFO Memory Field Reference (Eviction-relevant)

```bash
redis-cli INFO memory
```

| Field | Description | Alert threshold |
|-------|-------------|-----------------|
| `used_memory` | Logical memory Redis allocated | > maxmemory = eviction trigger |
| `used_memory_rss` | Physical memory (RSS, includes fragmentation) | > container RAM = OOM risk |
| `used_memory_dataset` | Memory for actual dataset (overhead excluded) | Trend monitoring |
| `maxmemory` | Configured limit | N/A |
| `mem_fragmentation_ratio` | RSS / used_memory | > 1.5 = defrag needed |
| `mem_fragmentation_bytes` | Bytes of fragmentation | > 100MB = active defrag |
| `evicted_keys` | Total keys evicted due to memory pressure | > 0 = cache under pressure |
| `maxmemory_human` | maxmemory in human-readable format | N/A |

```bash
redis-cli INFO stats | grep -E "evicted_keys|expired_keys"
```

| Field | Description |
|-------|-------------|
| `evicted_keys` | Keys evicted by eviction loop (not by TTL) |
| `expired_keys` | Keys expired by TTL (lazy + active expiration) |

---

## 6. Go Code Snippets (go-redis/v9)

### Inspect Memory & Eviction Status

```go
package main

import (
    "context"
    "fmt"
    "strconv"
    "strings"

    "github.com/redis/go-redis/v9"
)

type EvictionStatus struct {
    UsedMemory    int64
    MaxMemory     int64
    UsedRSS       int64
    EvictedKeys   int64
    ExpiredKeys   int64
    Fragmentation float64
}

func GetEvictionStatus(ctx context.Context, rdb *redis.Client) (*EvictionStatus, error) {
    info, err := rdb.Do(ctx, "INFO", "memory").Text()
    if err != nil {
        return nil, err
    }

    stats, err := rdb.Do(ctx, "INFO", "stats").Text()
    if err != nil {
        return nil, err
    }

    s := &EvictionStatus{}
    for _, line := range strings.Split(info, "\n") {
        line = strings.TrimSpace(line)
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }
        parts := strings.SplitN(line, ":", 2)
        if len(parts) != 2 {
            continue
        }
        key := strings.TrimSpace(parts[0])
        val := strings.TrimSpace(parts[1])

        switch key {
        case "used_memory":
            s.UsedMemory, _ = strconv.ParseInt(val, 10, 64)
        case "maxmemory":
            s.MaxMemory, _ = strconv.ParseInt(val, 10, 64)
        case "used_memory_rss":
            s.UsedRSS, _ = strconv.ParseInt(val, 10, 64)
        case "mem_fragmentation_ratio":
            s.Fragmentation, _ = strconv.ParseFloat(val, 64)
        }
    }

    for _, line := range strings.Split(stats, "\n") {
        line = strings.TrimSpace(line)
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }
        parts := strings.SplitN(line, ":", 2)
        if len(parts) != 2 {
            continue
        }
        key := strings.TrimSpace(parts[0])
        val := strings.TrimSpace(parts[1])

        switch key {
        case "evicted_keys":
            s.EvictedKeys, _ = strconv.ParseInt(val, 10, 64)
        case "expired_keys":
            s.ExpiredKeys, _ = strconv.ParseInt(val, 10, 64)
        }
    }

    return s, nil
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    defer rdb.Close()

    status, err := GetEvictionStatus(ctx, rdb)
    if err != nil {
        panic(err)
    }

    pctUsed := float64(status.UsedMemory) / float64(status.MaxMemory) * 100
    fmt.Printf("Memory: %d/%d (%.1f%%) | RSS: %dMB | Frag: %.2f\n",
        status.UsedMemory, status.MaxMemory, pctUsed,
        status.UsedRSS/1024/1024, status.Fragmentation)
    fmt.Printf("Evicted keys: %d | Expired keys: %d\n",
        status.EvictedKeys, status.ExpiredKeys)

    if pctUsed > 80 {
        fmt.Println("WARNING: Memory > 80% - eviction likely active")
    }
    if status.Fragmentation > 1.5 {
        fmt.Println("WARNING: Fragmentation > 1.5 - consider active defrag")
    }
}
```

### Inspect LFU Counter Distribution

```go
package main

import (
    "context"
    "fmt"
    "sort"

    "github.com/redis/go-redis/v9"
)

func GetLFUDistribution(ctx context.Context, rdb *redis.Client, pattern string, sampleCount int) (map[int]int, error) {
    // SCAN for keys matching pattern
    iter := rdb.Scan(ctx, 0, pattern, int64(sampleCount)).Iterator()
    counterFreq := make(map[int]int)
    count := 0

    for iter.Next(ctx) {
        key := iter.Val()
        // OBJECT FREQ returns LFU counter
        freq, err := rdb.Do(ctx, "OBJECT", "FREQ", key).Int64()
        if err != nil {
            continue
        }
        counterFreq[int(freq)]++
        count++
    }
    if err := iter.Err(); err != nil {
        return nil, err
    }

    fmt.Printf("Sampled %d keys, %d unique counter values\n", count, len(counterFreq))
    return counterFreq, nil
}

func PrintLFUDistribution(ctx context.Context, rdb *redis.Client, pattern string) {
    dist, err := GetLFUDistribution(ctx, rdb, pattern, 1000)
    if err != nil {
        fmt.Printf("Error: %v\n", err)
        return
    }

    // Sort counters
    var counters []int
    for k := range dist {
        counters = append(counters, k)
    }
    sort.Ints(counters)

    fmt.Println("LFU Counter Distribution (counter_value: key_count):")
    for _, c := range counters {
        fmt.Printf("  freq=%d: %d keys\n", c, dist[c])
    }
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    defer rdb.Close()

    // Check hot cache keys
    PrintLFUDistribution(ctx, rdb, "cache:*")
    // Check all keys
    PrintLFUDistribution(ctx, rdb, "*")
}
```

### Configure maxmemory & Policy at Runtime

```go
package main

import (
    "context"
    "fmt"

    "github.com/redis/go-redis/v9"
)

func ConfigureEviction(ctx context.Context, rdb *redis.Client, maxmemory string, policy string, samples int) error {
    // Set maxmemory (as string: "10gb", "1gb", etc.)
    if err := rdb.ConfigSet(ctx, "maxmemory", maxmemory).Err(); err != nil {
        return fmt.Errorf("maxmemory: %w", err)
    }

    // Set eviction policy
    if err := rdb.ConfigSet(ctx, "maxmemory-policy", policy).Err(); err != nil {
        return fmt.Errorf("maxmemory-policy: %w", err)
    }

    // Set sample size
    if err := rdb.ConfigSet(ctx, "maxmemory-samples", fmt.Sprintf("%d", samples)).Err(); err != nil {
        return fmt.Errorf("maxmemory-samples: %w", err)
    }

    fmt.Printf("Configured: maxmemory=%s, policy=%s, samples=%d\n", maxmemory, policy, samples)
    return nil
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    defer rdb.Close()

    // Configure for API cache
    err := ConfigureEviction(ctx, rdb, "10gb", "allkeys-lfu", 10)
    if err != nil {
        panic(err)
    }

    // Verify
    for _, cfg := range []struct {
        key   string
        field string
    }{
        {"maxmemory", "maxmemory"},
        {"maxmemory-policy", "maxmemory-policy"},
        {"maxmemory-samples", "maxmemory-samples"},
    } {
        val, err := rdb.Do(ctx, "CONFIG", "GET", cfg.key).Text()
        if err != nil {
            panic(err)
        }
        fmt.Printf("%s: %s\n", cfg.field, val)
    }
}
```

---

## 7. TypeScript Code Snippets (ioredis)

### Monitor Eviction Metrics

```typescript
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });

async function getEvictionStatus() {
  const [memoryInfo, statsInfo] = await Promise.all([
    redis.info('memory'),
    redis.info('stats'),
  ]);

  const parseInfo = (info: string) => {
    const lines = info.split('\r\n');
    const result: Record<string, string> = {};
    for (const line of lines) {
      if (line.includes(':')) {
        const [key, val] = line.split(':');
        result[key] = val;
      }
    }
    return result;
  };

  const memory = parseInfo(memoryInfo);
  const stats = parseInfo(statsInfo);

  const usedMemory = parseInt(memory['used_memory'], 10);
  const maxMemory = parseInt(memory['maxmemory'], 10);
  const evictedKeys = parseInt(stats['evicted_keys'], 10);
  const expiredKeys = parseInt(stats['expired_keys'], 10);
  const fragRatio = parseFloat(memory['mem_fragmentation_ratio']);

  const pctUsed = (usedMemory / maxMemory) * 100;

  console.log(`Memory: ${usedMemory}/${maxMemory} (${pctUsed.toFixed(1)}%)`);
  console.log(`Evicted: ${evictedKeys} | Expired: ${expiredKeys}`);
  console.log(`Fragmentation: ${fragRatio.toFixed(2)}`);

  if (pctUsed > 80) {
    console.warn('⚠️  Memory > 80% - eviction likely active');
  }
  if (evictedKeys > 0) {
    console.warn(`⚠️  ${evictedKeys} keys evicted - cache under pressure`);
  }
  if (fragRatio > 1.5) {
    console.warn('⚠️  Fragmentation > 1.5 - consider active defrag');
  }
}

// Run every 10 seconds
setInterval(() => getEvictionStatus().catch(console.error), 10_000);
```

### Inspect LFU Counter

```typescript
async function inspectLFU(key: string) {
  // OBJECT FREQ — LFU counter value
  const freq = await redis.object('FREQ', key);
  // OBJECT IDLETIME — seconds since last access
  const idleTime = await redis.object('IDLETIME', key);
  // OBJECT ENCODING — current encoding
  const encoding = await redis.object('ENCODING', key);

  console.log(`Key: ${key}`);
  console.log(`  LFU freq: ${freq}`);
  console.log(`  Idle time: ${idleTime}s`);
  console.log(`  Encoding: ${encoding}`);

  return { freq, idleTime, encoding };
}
```

---

## 8. Docker Compose Template

```yaml
# docker-compose-eviction-lab.yml
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

  redis-noeviction:
    image: redis:7-alpine
    container_name: redis-noeviction
    command: >
      redis-server
      --maxmemory 50mb
      --maxmemory-policy noeviction
      --loglevel notice
    ports:
      - "6382:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

---

## 9. Links & References

### Official Documentation
- https://redis.io/docs/management/optimization/memory-optimization/ — Redis memory optimization guide
- https://redis.io/docs/reference/eviction/ — Eviction policies official docs
- https://redis.io/docs/management/optimization/lru/ — LRU cache in Redis

### Redis Source Code
- `src/evict.c` — Core eviction implementation (evictionPoolPopulate, freeMemoryIfNeeded)
- `src/object.c` — OBJECT FREQ, OBJECT IDLETIME, LFU counter logic
- `src/server.h` — LRU_BITS, LFU_DECAY_TIME, LFU_LOG_FACTOR definitions
- `src/redis-cli.c` — redis-cli --scan, --hotkeys, --bigkeys

### Blog & Technical Articles
- **antirez "Random notes on improving the Redis LRU algorithm"**: oldblog.antirez.com/post/redis-lru-implementation
- **Redis 4.0 LFU release notes**: github.com/redis/redis/blob/4.0/00-RELEASENOTES
- **antirez "Redis eviction policies"**: oldblog.antirez.com/post/redis-eviction-policies
- **Netflix EVCache architecture**: techblog.netflix.com (search "EVCache")
- **Twitter Redis at scale**: blog.twitter.com/engineering/ (search "Redis cache")

### Key Config Parameters Reference

| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| `maxmemory` | 0 (unlimited) | 1MB - N GB | Eviction trigger threshold |
| `maxmemory-policy` | noeviction | 8 policies | Which keys evicted |
| `maxmemory-samples` | 5 | 1 - 100 | LRU/LFU accuracy vs CPU |
| `lfu-log-factor` | 10 | 0 - 255 | LFU counter growth speed |
| `lfu-decay-time` | 1 (minute) | 0 - 60 min | LFU counter decay rate |
| `hz` | 10 | 1 - 500 | Timer frequency (affects active expiration) |

### Memory Metrics Formulas

```
Fragmentation ratio = used_memory_rss / used_memory
  - > 1.5 = significant fragmentation
  - < 1.0 = impossible (should not happen)

Memory usage % = used_memory / maxmemory × 100
  - > 80% = eviction likely
  - > 95% = severe pressure

Eviction rate = evicted_keys / uptime_seconds
  - > 100/sec = severe pressure
  - > 1000/sec = critical
```

---

## 10. Eviction Decision Flowchart

```
used_memory > maxmemory?
    │
    ├── No  → serve command normally
    │
    └── Yes → eviction loop
                │
                ▼
         Is maxmemory-policy = noeviction?
                │
                ├── Yes → return OOM error, no eviction
                │
                └── No  → check key pool
                            │
                            ▼
                    Is it volatile-* policy?
                (lru/lfu/random/ttl)
                            │
                            ├── Yes → is there ANY key with TTL?
                            │         ├── No  → 0 evictions, return OOM
                            │         └── Yes → sample TTL keys
                            │
                            └── No (allkeys-*) → sample ALL keys
                                    │
                                    ▼
                            Sample maxmemory-samples keys
                                    │
                                    ▼
                            Apply sort criteria:
                            - LRU: oldest LRU value
                            - LFU: lowest LFU counter
                            - RANDOM: random
                            - TTL: shortest TTL
                                    │
                                    ▼
                            Delete worst candidate
                                    │
                                    ▼
                            freed_bytes += key_size
                                    │
                                    ▼
                            Loop until used_memory <= maxmemory
                            (or max 16 iterations per command)
                                    │
                                    ▼
                            Serve command
```
