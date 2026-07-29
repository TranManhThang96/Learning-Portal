# Day 11: Pipelining & Batching — Reference Document

## 1. Cheat Sheet: Pipelining & Batching Commands

```txt
-- redis-cli pipelining mode
(echo "PING"; echo "PING"; echo "PING") | redis-cli --pipe
redis-cli --pipe-timeout 10   -- timeout 10s
redis-cli --pipe             -- read from stdin

-- Batch commands (single command, multiple arguments)
MGET key1 key2 key3 key4 key5
MSET key1 val1 key2 val2 key3 val3
HMGET hashkey field1 field2 field3
HMSET hashkey field1 val1 field2 val2
DEL key1 key2 key3 key4

-- Pipeline in redis-cli via --pipe (raw RESP format)
printf "*3\r\n\$3\r\nGET\r\n\$5\r\nkey:1\r\n*3\r\n\$3\r\nGET\r\n\$5\r\nkey:2\r\n" | redis-cli --pipe

-- Check pipeline stats
INFO commandstats | grep cmdstat_
redis-cli CONFIG GET client-output-buffer-limit
redis-cli CONFIG GET client-query-buffer-limit
```

## 2. ioredis Pipeline API (TypeScript)

```typescript
import Redis from 'ioredis';

// --- Basic Pipeline ---
const redis = new Redis({ host: 'localhost', port: 6379 });

const pipeline = redis.pipeline();
// Queue commands (không execute ngay)
pipeline.set('key:1', 'value:1');
pipeline.get('key:1');
pipeline.hset('hash:1', 'field1', 'val1');
pipeline.hget('hash:1', 'field1');
pipeline.incr('counter:1');

// Execute all queued commands in 1 RTT
const results = await pipeline.exec();
// results: Array<[Error | null, any]>

for (const [err, value] of results) {
    if (err) {
        console.error('Command error:', err);
    }
}

// --- Batch size pattern: auto-flush every N commands ---
async function pipelineBatch(redis: Redis, commands: Array<[string, ...any[]]>, batchSize = 1000) {
    let pipe = redis.pipeline();
    const allResults: Array<[Error | null, any]> = [];
    let queued = 0;

    for (const [cmd, ...args] of commands) {
        (pipe as any)[cmd](...args);
        queued++;

        if (queued >= batchSize) {
            const batch = await pipe.exec();
            if (batch) allResults.push(...batch);
            pipe = redis.pipeline();
            queued = 0;
        }
    }

    if (queued > 0) {
        const batch = await pipe.exec();
        if (batch) allResults.push(...batch);
    }

    return allResults;
}

// --- Cluster-aware pipeline (ioredis tự động split theo node) ---
import Redis from 'ioredis';

const cluster = new Redis.Cluster([
    { host: '10.0.0.1', port: 6379 },
    { host: '10.0.0.2', port: 6379 },
    { host: '10.0.0.3', port: 6379 },
]);

// ioredis tự routing theo slot/node cho command đơn-key.
// Multi-key commands như MGET vẫn cần keys cùng slot.
const pipe = cluster.pipeline();
for (const key of manyKeys) {
    pipe.get(key); // tự split theo node
}
const results = await pipe.exec(); // trả về theo đúng order

// --- TXPipeline (MULTI/EXEC shorthand) ---
const tx = redis.multi();
tx.set('a', '1');
tx.get('a');
tx.incr('counter');
const txResults = await tx.exec();
// txResults: Array<[Error | null, any]>
// Giống pipeline nhưng thêm MULTI/EXEC (2 RTT)
```

## 3. node-redis Pipeline API (@redis/client v4)

```typescript
import { createClient } from '@redis/client';

const redis = await createClient({ url: 'redis://localhost:6379' }).connect();

// --- Pipeline ---
const pipeline = redis.multi();
pipeline.set('key:1', 'value:1');
pipeline.get('key:1');
pipeline.hset('hash:1', 'field1', 'val1');
pipeline.incr('counter:1');
const results = await pipeline.execAsPipeline();
// results: Array<[Error | null, any]>

// --- MULTI/EXEC (atomic transaction) ---
const tx = redis.multi();
tx.set('key:1', 'value:1');
tx.get('key:1');
const txResults = await tx.execAsTransaction();
// txResults: Array<[Error | null, any]>

// --- Batch helper ---
async function batchGet(redis: ReturnType<typeof createClient>, keys: string[]) {
    const pipeline = redis.multi();
    for (const key of keys) {
        pipeline.get(key);
    }
    return await pipeline.execAsPipeline();
}
```

## 4. go-redis Pipeliner (Go)

```go
package main

import (
    "context"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

// --- Basic Pipeline ---
func pipelineExample(ctx context.Context, rdb *redis.Client) {
    pipe := rdb.Pipeline()

    pipe.Set(ctx, "key:1", "value:1", 0)
    get := pipe.Get(ctx, "key:1")
    hset := pipe.HSet(ctx, "hash:1", "field1", "val1")
    incr := pipe.Incr(ctx, "counter:1")

    // Exec sends all commands
    _, err := pipe.Exec(ctx)
    if err != nil {
        panic(err)
    }

    // Read results after Exec ( Exec() already sent commands )
    fmt.Println(get.Val())
    fmt.Println(hset.Val())
    fmt.Println(incr.Val())
}

// --- TxPipeline (MULTI/EXEC) ---
func txPipelineExample(ctx context.Context, rdb *redis.Client) {
    pipe := rdb.TxPipeline()

    pipe.Set(ctx, "key:1", "value:1", 0)
    pipe.Incr(ctx, "counter:1")

    cmds, err := pipe.Exec(ctx)
    if err != nil {
        panic(err)
    }

    for _, cmd := range cmds {
        fmt.Printf("Result: %s\n", cmd.String())
    }
}

// --- Chunked Pipeline for large datasets ---
func chunkedPipeline(ctx context.Context, rdb *redis.Client, keys []string, values []string, batchSize int) error {
    for i := 0; i < len(keys); i += batchSize {
        end := i + batchSize
        if end > len(keys) {
            end = len(keys)
        }

        pipe := rdb.Pipeline()
        for j := i; j < end; j++ {
            pipe.Set(ctx, keys[j], values[j], 0)
        }

        _, err := pipe.Exec(ctx)
        if err != nil {
            return fmt.Errorf("batch %d-%d: %w", i, end, err)
        }
    }
    return nil
}

// --- Benchmark helper ---
func benchmarkPipeline(ctx context.Context, rdb *redis.Client, count int, batchSize int) (time.Duration, int64) {
    var totalOps int64

    start := time.Now()

    for i := 0; i < count; i += batchSize {
        pipe := rdb.Pipeline()
        for j := 0; j < batchSize && (i+j) < count; j++ {
            key := fmt.Sprintf("bench:key:%08d", i+j)
            pipe.Set(ctx, key, fmt.Sprintf("value-%08d", i+j), 0)
            totalOps++
        }
        pipe.Exec(ctx) // ignore error for benchmark
    }

    elapsed := time.Since(start)
    opsPerSec := int64(float64(totalOps) / elapsed.Seconds())

    return elapsed, opsPerSec
}
```

## 5. redis-cli --pipe — Raw RESP Examples

```bash
# Simple pipe: PING 3 lần
(echo -e "PING\r\nPING\r\nPING\r\n") | redis-cli --pipe

# Pipe SET commands
for i in {1..1000}; do
    key="key:$i"
    printf "*3\r\n\$3\r\nSET\r\n\$%d\r\n%s\r\n\$5\r\nvalue\r\n" "${#key}" "$key"
done | redis-cli --pipe

# Time 1000 SET commands (non-pipeline vs pipeline)
time (for i in {1..1000}; do redis-cli SET "key:$i" "val:$i" > /dev/null; done)
printf "%s\n" {1..1000} | xargs -I{} redis-cli SET "key:{}" "val:{}" > /dev/null

# Measure pipelined throughput với raw RESP
{
  printf "*3\r\n\$3\r\nSET\r\n\$10\r\npipeline:1\r\n\$6\r\nvalue1\r\n"
  printf "*3\r\n\$3\r\nSET\r\n\$10\r\npipeline:2\r\n\$6\r\nvalue2\r\n"
  printf "*3\r\n\$3\r\nSET\r\n\$10\r\npipeline:3\r\n\$6\r\nvalue3\r\n"
  printf "*2\r\n\$3\r\nGET\r\n\$10\r\npipeline:1\r\n"
  printf "*2\r\n\$3\r\nGET\r\n\$10\r\npipeline:2\r\n"
  printf "*4\r\n\$4\r\nMGET\r\n\$10\r\npipeline:1\r\n\$10\r\npipeline:2\r\n\$10\r\npipeline:3\r\n"
} | redis-cli --pipe-timeout 10
```

## 6. Server Buffer Config Reference

| Config | Default | Description |
|--------|---------|-------------|
| `client-query-buffer-limit` | 1gb | Max size of per-client query buffer (input). Pipeline larger than this → killed |
| `client-output-buffer-limit` | normal 8mb 60s 2mb 30s | Max output buffer before pause. Format: `class limit soft_limit seconds` |
| `proto-max-bulk-len` | 512mb | Max size of a single bulk string in RESP protocol |
| `maxclients` | 10000 | Max simultaneous clients |

```txt
-- Kiểm tra buffer config
CONFIG GET client-query-buffer-limit
CONFIG GET client-output-buffer-limit
CONFIG GET proto-max-bulk-len
CONFIG GET maxclients

-- Tăng buffer limits (khi cần pipeline lớn)
CONFIG SET client-query-buffer-limit 4gb
CONFIG SET client-output-buffer-limit "normal 32mb 120s 8mb 60s"

-- WATCH OUT: Tăng limit có thể gây OOM nếu nhiều clients cùng gửi lớn
```

## 7. Pipeline Best Practice Cheatsheet

```txt
┌─────────────────────────────────────────────────────────────────┐
│           PIPELINE BEST PRACTICE — QUICK REFERENCE              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ ALWAYS                                                    │
│  ─────────────────────────────────────────────────────────────  │
│  • Cap batch size ≤ 100K (server input buffer 1GB limit)       │
│  • Handle error per-command: if (err) { handle }                │
│  • Use try/catch on pipeline.exec()                            │
│  • Use MGET/MSET when all keys are String                      │
│  • Use ioredis cluster → auto splits pipeline by node           │
│  • Measure p50/p95/p99, not just average                       │
│  • Monitor: redis-cli CLIENT LIST | grep obl                   │
│                                                                  │
│  ❌ NEVER                                                      │
│  ─────────────────────────────────────────────────────────────  │
│  • Never send pipeline > 1GB                                    │
│  • Never assume atomicity (use Lua/MULTI if needed)             │
│  • Never ignore errors in pipeline results array                │
│  • Never use pipeline for Pub/Sub                               │
│  • Never use Lua for bulk read (block event loop)               │
│                                                                  │
│  📊 BATCH SIZE GUIDANCE                                        │
│  ─────────────────────────────────────────────────────────────  │
│  RTT 0.1ms  (local)     → batch 50-500                         │
│  RTT 0.5ms  (same DC)   → batch 100-1,000                      │
│  RTT 5ms   (cross-DC)   → batch 1,000-5,000                    │
│  RTT 50ms  (WAN)        → batch 5,000-20,000                   │
│  RTT 500ms (satellite)  → batch 50,000-100,000                 │
│                                                                  │
│  ⚠️ WARNING                                                    │
│  ─────────────────────────────────────────────────────────────  │
│  • Pipeline does NOT bypass Cluster routing/MOVED/ASK handling   │
│  • Pipeline does NOT guarantee atomicity                         │
│  • Error in middle → subsequent commands still execute           │
│  • Large batch → p99 latency spike                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Benchmark Commands

```bash
# redis-benchmark pipelining
redis-benchmark -t set -n 100000 -P 1    # 1 pipeline depth (no pipeline)
redis-benchmark -t set -n 100000 -P 10   # pipeline depth 10
redis-benchmark -t set -n 100000 -P 100 # pipeline depth 100
redis-benchmark -t set -n 100000 -P 1000 # pipeline depth 1000

# MGET benchmark
redis-benchmark -t mget -n 10000 -r 100000 -P 1
redis-benchmark -t mget -n 10000 -r 100000 -P 100

# Pipeline raw mode
redis-cli --pipe-timeout 10 -n 100000 << 'EOF'
SET key:1 value:1
SET key:2 value:2
SET key:3 value:3
EOF

# INFO commandstats after benchmark
redis-cli INFO commandstats | grep cmdstat_
```

## 9. Links & References

### Official Documentation
- https://redis.io/docs/manual/pipelining/ — Redis pipelining official docs
- https://redis.io/docs/manual/transactions/ — MULTI/EXEC transactions
- https://redis.io/docs/data-types/hashes/ — HMGET, HGETALL
- https://redis.io/docs/reference/clients/ — Client output buffer limits

### ioredis
- https://github.com/redis/ioredis — ioredis GitHub
- https://github.com/redis/ioredis#pipelining — Pipeline documentation
- https://github.com/redis/ioredis/blob/master/lib/cluster/pipeline.ts — Cluster-aware pipeline

### go-redis
- https://github.com/redis/go-redis — go-redis GitHub
- https://redis.uptrace.dev/guide/go-pipelining.html — Pipelining guide

### node-redis
- https://github.com/redis/node-redis — @redis/client v4

### Blog & Articles
- **antirez "Redis Pipeline"** — oldblog.antirez.com/post/redis-pipelining
- **Twitter Engineering "How Twitter Uses Redis at Scale"** — pipeline patterns for bulk operations
- **Redis Labs "Redis Pipeline vs Transactions"** — when to use each
- **Discord Engineering "Pipelining in Redis"** — bulk data transfer patterns

### Redis Source Code
- `src/networking.c` — client buffer management, pipeline handling
- `src/server.h` — client-query-buffer-limit, client-output-buffer-limit
- `src/multi.c` — MULTI/EXEC transaction implementation
- `src/acl.c` — client buffer limits enforcement
