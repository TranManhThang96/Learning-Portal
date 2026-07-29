# Day 9: Memory Optimization & Fragmentation — Reference Document

## 1. Cheat Sheet: Memory Commands

```txt
-- Memory introspection
INFO memory                        -- full memory metrics (see section 2)
MEMORY USAGE key [SAMPLES count]   -- memory used by key (accurate, include overhead)
MEMORY STATS                      -- detailed allocator + Redis memory stats
MEMORY DOCTOR                     -- analysis + recommendations
MEMORY PURGE                      -- purge allocator caches (defensive, not defrag)

-- Key introspection
OBJECT ENCODING key               -- current encoding (listpack/hashtable/intset/skiplist)
OBJECT FREQ key                   -- access frequency (LFU mode)
DEBUG OBJECT key                  -- full object internals (encoding, refcount, lru)
DEBUG SLEEP 0.5                  -- simulate latency

-- Defrag
CONFIG GET activedefrag           -- check defrag status
CONFIG SET activedefrag yes       -- enable active defrag (can be done at runtime)
CONFIG SET activedefrag no       -- disable

-- Key deletion
UNLINK key                        -- async delete (use this, not DEL)
DEL key                          -- sync delete (O(N) blocking, only for small keys)

-- Encoding threshold configs
CONFIG GET hash-max-listpack-entries
CONFIG GET hash-max-listpack-value
CONFIG GET zset-max-listpack-entries
CONFIG GET set-max-listpack-entries
CONFIG GET set-max-intset-entries
```

## 2. INFO Memory Field Reference (Complete)

```bash
redis-cli INFO memory
```

| Field | Bytes | Description |
|-------|-------|-------------|
| `used_memory` | 33,554,432 | Logical data size (keys + internal overhead) |
| `used_memory_human` | 32M | Human-readable |
| `used_memory_rss` | 58,720,256 | RSS — physical pages allocated by OS |
| `used_memory_peak` | 58,720,256 | Peak `used_memory` ever reached |
| `used_memory_dataset` | 30,000,000 | Data bytes only (exclude Redis internal overhead) |
| `used_memory_overhead` | 3,554,432 | Redis internal overhead (robj, dict, etc.) |
| `used_memory_startup` | 1,048,576 | Memory used at startup (binary + structures) |
| `mem_fragmentation_ratio` | 1.75 | RSS / used_memory |
| `mem_fragmentation_bytes` | 25,165,824 | RSS - used_memory (fragmentation bytes) |
| `mem_allocator` | jemalloc-5.3.0 | Allocator library |
| `allocator_allocated` | 33,562,600 | Logical bytes from jemalloc |
| `allocator_active` | 58,720,256 | Bytes in active jemalloc runs |
| `allocator_resident` | 58,720,256 | Bytes resident in RAM |
| `allocator_frag_ratio` | 1.75 | Internal fragmentation ratio |
| `allocator_frag_bytes` | 25,165,824 | Internal fragmentation bytes |
| `allocator_rss_ratio` | 1.00 | rss / active |
| `allocator_rss_bytes` | 0 | RSS overhead beyond allocator |
| `mem_clients_slaves` | 0 | Memory for replica output buffers |
| `mem_clients_normal` | 1,000,000 | Memory for normal client buffers |
| `mem_aof_buffer` | 0 | AOF buffer size |
| `mem_replication_backlog` | 10,485,760 | Replication backlog (if replica > 0) |
| `lazyfree_pending_objects` | 0 | Objects pending async free (UNLINK) |

**Quick triage formula**:

```bash
# Triage script
redis-cli INFO memory | awk '
/^used_memory:/ { u = $2 }
/^used_memory_rss:/ { r = $2 }
/^mem_fragmentation_ratio:/ { f = $2 }
END {
    printf "Logical: %d MB | RSS: %d MB | Ratio: %.2f\n",
           u/1024/1024, r/1024/1024, f
    if (f < 1.0) print "WARNING: Ratio < 1.0 = SWAP"
    else if (f > 2.0) print "WARNING: High fragmentation - enable defrag"
    else if (f > 1.5) print "CAUTION: Moderate fragmentation"
    else print "OK: Fragmentation within acceptable range"
}
'
```

## 3. Active Defrag Config Reference

```bash
# Enable
CONFIG SET activedefrag yes

# Threshold config
CONFIG SET active-defrag-threshold-lower 100   # default: 10
  # Start defrag when fragmentation > 1.10 for > 10s (default)
  # 100 = fragmentation > 2.00 (more conservative)

CONFIG SET active-defrag-threshold-upper 50    # default: 75
  # Aggressive defrag when ratio > 1.75 (default)
  # 50 = aggressive mode starts at ratio > 1.50

CONFIG SET active-defrag-ignore-bytes 100mb   # default: 100mb
  # Ignore fragmentation < 100MB (avoid defrag on small waste)
  # If fragmentation = 200MB and ignore-bytes = 100mb → defrag threshold met

CONFIG SET active-defrag-cycle-min 10         # default: 10
  # Min CPU time for defrag (% of 1 core)
  # 10 = slow defrag (10% of 1 core = 1.25% of 8-core server)

CONFIG SET active-defrag-cycle-max 50         # default: 75
  # Max CPU time for defrag (% of 1 core)
  # 50 = moderate aggressive (50% of 1 core = 6.25% of 8-core server)
```

**Conservative production config (high-traffic)**:

```txt
activedefrag yes
active-defrag-threshold-lower 100
active-defrag-threshold-upper 50
active-defrag-ignore-bytes 100mb
active-defrag-cycle-min 10
active-defrag-cycle-max 50
```

**Moderate config (medium traffic)**:

```txt
activedefrag yes
active-defrag-threshold-lower 50
active-defrag-threshold-upper 75
active-defrag-ignore-bytes 100mb
active-defrag-cycle-min 10
active-defrag-cycle-max 75
```

## 4. jemalloc Size Classes Reference

| Size Class (bytes) | Page Usage |
|-------------------|-----------|
| 8 | 8B × 512 = 4KB (1 page) |
| 16 | 16B × 256 = 4KB (1 page) |
| 24 | 24B × 170 = 4KB (1 page) |
| 32 | 32B × 128 = 4KB (1 page) |
| 48 | 48B × 85 = 4KB (1 page) |
| 64 | 64B × 64 = 4KB (1 page) |
| 96 | 96B × 43 = 4KB (1 page) |
| 128 | 128B × 32 = 4KB (1 page) |
| 192 | 192B × 21 + padding = 4KB (1 page) |
| 256 | 256B × 16 = 4KB (1 page) |
| 320 | 320B × 12 + 2×64B = 4KB (1 page) |
| 384 | 384B × 10 + padding = 4KB (1 page) |
| 512 | 512B × 8 = 4KB (1 page) |
| 768 | 768B × 5 + 2×128B = 4KB (1 page) |
| 1024 | 1024B × 4 = 4KB (1 page) |
| 2048 | 2048B × 2 = 4KB (1 page) |
| 4096 | 4096B = 1 page |
| 8192 | 8192B = 2 pages |

**Implication**: Nếu `MEMORY USAGE key` trả về 37 bytes → jemalloc round up to 48B → 11 bytes internal fragmentation.

## 5. Encoding Threshold Defaults (Redis 7.x)

| Data Type | Encoding | Threshold | Notes |
|-----------|----------|-----------|-------|
| Hash | listpack | fields ≤ 128 AND value ≤ 64B | Both conditions must be true |
| Hash | hashtable | fields > 128 OR value > 64B | |
| List | quicklist | always (Redis 7+) | list-max-listpack-size controls node size |
| Set | intset | all integers AND size ≤ 512 | Upgrade only, never downgrade |
| Set | listpack (7.2+) | strings, size ≤ 128 | |
| Set | hashtable | otherwise | |
| Sorted Set | listpack | entries ≤ 128 AND value ≤ 64B | |
| Sorted Set | skiplist | otherwise | |
| String | int | integer values | |
| String | raw | otherwise | |

**Threshold config**:

```bash
# hash-max-listpack-entries: default 128
# hash-max-listpack-value: default 64 bytes

# zset-max-listpack-entries: default 128
# set-max-listpack-entries: default 128
# set-max-intset-entries: default 512
```

## 6. Config Templates cho Memory-Heavy Workload

### Template 1: Session Store (optimize memory + defrag)

```txt
# redis-session-optimized.conf

# Memory
maxmemory 8gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Encoding: favor memory (write-once/read-many)
hash-max-listpack-entries 256
hash-max-listpack-value 64
zset-max-listpack-entries 128
set-max-intset-entries 512

# Active defrag: conservative
activedefrag yes
active-defrag-threshold-lower 100
active-defrag-threshold-upper 75
active-defrag-ignore-bytes 100mb
active-defrag-cycle-min 10
active-defrag-cycle-max 50

# Lazy free (prevent blocking on eviction)
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes

# Client buffers
client-output-buffer-limit normal 256mb 64mb 60
client-output-buffer-limit replica 64mb 16mb 60
```

### Template 2: Time-Series Buffer (compression priority)

```txt
# redis-timeseries.conf

maxmemory 16gb
maxmemory-policy noeviction
maxmemory-samples 5

# Compact encoding
hash-max-listpack-entries 128
hash-max-listpack-value 64
zset-max-listpack-entries 128

# No active defrag (latency-sensitive)
activedefrag no

# Lazy free
lazyfree-lazy-eviction yes
lazyfree-lazy-server-del yes

# Small client buffers
client-output-buffer-limit normal 64mb 16mb 60
```

### Template 3: Cache with High Key Churn

```txt
# redis-cache-high-churn.conf

maxmemory 32gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Optimize for many small keys
hash-max-listpack-entries 128
hash-max-listpack-value 64

# Active defrag: essential for high churn
activedefrag yes
active-defrag-threshold-lower 50
active-defrag-threshold-upper 75
active-defrag-ignore-bytes 50mb
active-defrag-cycle-min 10
active-defrag-cycle-max 50

# Prevent fragmentation from lazy free
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
```

## 7. Compression Library Snippets

### TypeScript: snappy + ioredis

```typescript
// src/compression.ts
import Redis from 'ioredis';
import snappy from 'snappy';

const redis = new Redis({ host: 'localhost', port: 6379 });

interface CacheEntry {
  userId: number;
  data: Record<string, unknown>;
  ts: number;
}

async function setCompressed(
  key: string,
  value: CacheEntry,
  ttl = 3600
): Promise<void> {
  const json = JSON.stringify(value);
  const compressed = snappy.compressSync(json); // Buffer
  await redis.set(key, compressed.toString('base64'), 'EX', ttl);
}

async function getCompressed(key: string): Promise<CacheEntry | null> {
  const raw = await redis.get(key);
  if (!raw) return null;
  const compressed = Buffer.from(raw, 'base64');
  const json = snappy.uncompressSync(compressed, { asBuffer: false }) as string;
  return JSON.parse(json) as CacheEntry;
}

// Usage
const entry = { userId: 1, data: { name: 'Thang', prefs: { theme: 'dark' } }, ts: Date.now() };
await setCompressed('user:1:profile', entry);
const cached = await getCompressed('user:1:profile');
console.log(cached);
```

**package.json snippet**:

```json
{
  "dependencies": {
    "ioredis": "^5.3.0",
    "snappy": "^7.2.0"
  }
}
```

### TypeScript: zstd (better ratio)

```typescript
// src/compression-zstd.ts
import Redis from 'ioredis';
import { compress, decompress } from 'zstd-codec';

const redis = new Redis({ host: 'localhost', port: 6379 });

async function setZstd(key: string, value: unknown, ttl = 3600): Promise<void> {
  const json = JSON.stringify(value);
  const compressed = compress(Buffer.from(json), 3); // level 3 = balanced
  await redis.set(key, compressed.toString('base64'), 'EX', ttl);
}

async function getZstd<T>(key: string): Promise<T | null> {
  const raw = await redis.get(key);
  if (!raw) return null;
  const compressed = Buffer.from(raw, 'base64');
  const decompressed = decompress(compressed);
  return JSON.parse(decompressed.toString()) as T;
}
```

### Go: snappy + go-redis

```go
// compression.go
package main

import (
    "context"
    "encoding/json"
    "fmt"

    "github.com/DataDog/sketches-go/ddsketch"
    "github.com/golang/snappy"
    "github.com/redis/go-redis/v9"
)

type Profile struct {
    UserID int64                  `json:"userId"`
    Data   map[string]interface{} `json:"data"`
    Ts     int64                  `json:"ts"`
}

func SetCompressed(ctx context.Context, rdb *redis.Client, key string, p *Profile, ttlSeconds int) error {
    jsonBytes, err := json.Marshal(p)
    if err != nil {
        return fmt.Errorf("json marshal: %w", err)
    }
    compressed := snappy.Encode(nil, jsonBytes)
    return rdb.Set(ctx, key, compressed, 0).Err()
}

func GetCompressed(ctx context.Context, rdb *redis.Client, key string) (*Profile, error) {
    data, err := rdb.Get(ctx, key).Bytes()
    if err != nil {
        return nil, err // redis.Nil or other error
    }
    decompressed, err := snappy.Decode(nil, data)
    if err != nil {
        return nil, fmt.Errorf("snappy decode: %w", err)
    }
    var p Profile
    if err := json.Unmarshal(decompressed, &p); err != nil {
        return nil, fmt.Errorf("json unmarshal: %w", err)
    }
    return &p, nil
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})

    p := &Profile{
        UserID: 12345,
        Data:   map[string]interface{}{"name": "Thang", "score": 9500},
        Ts:     1715000000,
    }

    if err := SetCompressed(ctx, rdb, "profile:12345", p, 3600); err != nil {
        panic(err)
    }

    cached, err := GetCompressed(ctx, rdb, "profile:12345")
    if err != nil {
        panic(err)
    }
    fmt.Printf("Cached profile: %+v\n", cached)
}
```

### TypeScript: built-in gzip (Node.js zlib)

```typescript
// src/compression-gzip.ts
import Redis from 'ioredis';
import { gzip, gunzip } from 'zlib';
import { promisify } from 'util';

const gzipAsync = promisify(gzip);
const gunzipAsync = promisify(gunzip);

const redis = new Redis({ host: 'localhost', port: 6379 });

async function setGzip(key: string, value: unknown, ttl = 3600): Promise<void> {
  const json = JSON.stringify(value);
  const compressed = await gzipAsync(Buffer.from(json), { level: 1 }); // level 1 = fast
  await redis.set(key, compressed.toString('base64'), 'EX', ttl);
}

async function getGzip<T>(key: string): Promise<T | null> {
  const raw = await redis.get(key);
  if (!raw) return null;
  const compressed = Buffer.from(raw, 'base64');
  const decompressed = await gunzipAsync(compressed);
  return JSON.parse(decompressed.toString()) as T;
}
```

## 8. Links & References

### Official Documentation
- https://redis.io/docs/management/optimization/memory-optimization/ — Memory optimization guide
- https://redis.io/docs/management/optimization/memory-diagnosis/ — Memory diagnosis
- https://redis.io/docs/management/optimization/fragmentation/ — Defragmentation
- https://redis.io/docs/reference/clients/redis-cli/ — redis-cli MEMORY commands

### Redis Source Code
- `src/object.c` — `MEMORY USAGE`, `OBJECT ENCODING` implementation
- `src/defrag.c` — Active defragmentation implementation
- `src/allocator_defrag.c` — jemalloc integration for defrag
- `src/dict.c` — Hashtable defrag
- `src/listpack.c` — listpack implementation
- `deps/jemalloc/` — jemalloc source

### External References
- **jemalloc paper**: Jason Evans, "jemalloc: A Memory Allocator Demystified" — https://www.facebook.com/notes/jason-evans/400392386200
- **jemalloc official docs**: https://jemalloc.net/jemalloc.3.html
- **Redis memory fragmentation**: antirez blog — http://antirez.com/post/redis-2-6-notes.html (original fragmentation discussion)
- **Twitter Engineering on Redis Memory**: https://blog.twitter.com/engineering/ — "Redis at Twitter"
- **Discord Message Cache**: https://discord.com/blog/ — case study on MessagePack + compression
- **Shopify Active Defrag**: internal case study (referenced in Redis conference talks)
- **Uber Time-Series Compression**: https://www.uber.com/blog/ — metrics infrastructure blog
- **Memory optimization at Pinterest**: engineering blog (hash-max-ziplist tuning case study)

### Monitoring Alerts
```bash
# Prometheus alerting rules (prometheus.yml format)
groups:
  - name: redis-memory
    rules:
      - alert: RedisHighFragmentation
        expr: (redis_mem_rss_memory_bytes / redis_mem_used_memory_bytes) > 1.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis fragmentation ratio > 1.8"

      - alert: RedisCriticalFragmentation
        expr: (redis_mem_rss_memory_bytes / redis_mem_used_memory_bytes) > 2.5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Redis fragmentation ratio > 2.5 — immediate action required"

      - alert: RedisMemorySwapped
        expr: (redis_mem_rss_memory_bytes / redis_mem_used_memory_bytes) < 1.0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis memory swapped — emergency scale up"
```
