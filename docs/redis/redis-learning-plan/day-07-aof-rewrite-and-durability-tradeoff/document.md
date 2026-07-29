# Day 7: AOF Rewrite & Durability Trade-off — Reference Document

## 1. Cheat Sheet: AOF Rewrite & fsync Commands

```txt
-- Trigger AOF rewrite (non-blocking)
BGREWRITEAOF                          -- preferred over rewrite for production

-- Monitor rewrite status
INFO persistence | grep aof
BGREWRITEAOF                          -- returns "Background append only file rewriting started"

-- Cancel rewrite (if running)
redis-cli SHUTDOWN ABORT              -- cancels scheduled rewrite

-- fsync policy
CONFIG SET appendfsync always         -- zero data loss (blocks main thread per write)
CONFIG SET appendfsync everysec       -- default: ~1s data loss, background fsync
CONFIG SET appendfsync no            -- OS decides: up to 30s data loss, no Redis overhead

-- AOF rewrite tuning
CONFIG GET auto-aofrewrite*           -- show current thresholds
CONFIG SET auto-aof-rewrite-percentage 100   -- default: rewrite when AOF is 2x last rewrite size
CONFIG SET auto-aof-rewrite-min-size 64mb    -- default: don't rewrite if AOF < 64MB

-- Rewrite performance
CONFIG GET no-appendfsync-on-rewrite  -- yes = skip fsync during rewrite (faster, more data loss risk)
CONFIG GET aof-use-rdb-preamble       -- yes = RDB base + AOF tail (Redis 7 default)
CONFIG GET aof-incremental-fsync      -- yes = fsync every 1MB during rewrite (Redis 7+)

-- AOF corruption check & fix
redis-check-aof /data/appendonlydir/appendonly.1.0000000000000000.aof
redis-check-aof --fix /data/appendonlydir/appendonly.1.0000000000000000.aof

-- INFO persistence fields for AOF rewrite monitoring
INFO persistence | grep -E "aof_rewrite|aof_last|aof_delayed|latest_fork"
```

## 2. fsync Policy Reference Table

| Aspect | `always` | `everysec` (default) | `no` |
|--------|----------|----------------------|------|
| **Semantics** | `fsync()` after every write | Background thread, fsync every ~1s | No `fsync()` called by Redis |
| **p50 write latency** | 1-5ms | 0.1-0.3ms | 0.1-0.2ms |
| **p95 write latency** | 5-15ms | 1-3ms | 0.5-1ms |
| **p99 write latency** | 15-50ms (spikes to 100ms) | 3-10ms | 2-5ms |
| **Throughput (SATA SSD)** | ~15-30K ops/sec | ~80-100K ops/sec | ~100K+ ops/sec |
| **Throughput (NVMe+PLP)** | ~80-120K ops/sec | ~120-150K ops/sec | ~150K+ ops/sec |
| **Data loss window** | ~0 (best-effort) | ~1s worst case | ~30s+ (OS-dependent) |
| **CPU overhead** | High (syscall per op) | Low (background thread) | Minimal |
| **Disk I/O pattern** | Sync write per op | Batch fsync (1/sec) | OS decides |
| **Blocks main thread?** | Yes (on slow disk) | No (background) | No |
| **Recommended use case** | Financial idempotency on dedicated NVMe | Most production (session, job queue, cache) | Ephemeral cache only |

**Data loss window calculation for `everysec`**:
- Worst case: fsync started at t=0, completes at t=1s, crash at t=1.1s → lose ~1s of commands
- If previous fsync still running when next cycle starts: skip this cycle (`aof_delayed_fsync` increments) → data loss window can extend to ~2s

## 3. Config Knobs Reference

### AOF Rewrite Triggers

| Config | Default | Description |
|--------|---------|-------------|
| `auto-aof-rewrite-percentage` | `100` | Rewrite when AOF size is `(100 + N)%` of last rewrite size. `100` = rewrite at 2x. `50` = rewrite at 1.5x (more aggressive). `0` = **disable auto rewrite (NEVER do this)** |
| `auto-aof-rewrite-min-size` | `64mb` | Don't rewrite if AOF file is smaller than this. Prevents unnecessary rewrites on small datasets |
| `aof-load-truncated` | `yes` | Load AOF if truncated (power loss mid-write). `yes` = skip corrupt tail, continue. `no` = fail startup |

### AOF Rewrite Performance

| Config | Default | Description |
|--------|---------|-------------|
| `no-appendfsync-on-rewrite` | `no` | `yes` = skip `fsync()` during rewrite (faster rewrite, but more data loss on crash during rewrite). Trade-off: 5-10s extra data loss window |
| `aof-use-rdb-preamble` | `yes` (Redis 7+) | Write RDB snapshot as base, then AOF commands as tail. Fast restart + compact AOF |
| `aof-incremental-fsync` | `yes` (Redis 7+) | `fsync()` every 1MB during rewrite. Reduces data loss from 32MB → 1MB on crash during rewrite |
| `aof-rewrite-incremental-fsync` | `yes` (Redis 7.2+) | Alias for above |

### Multi-Part AOF (Redis 7+)

| Config | Default | Description |
|--------|---------|-------------|
| `appendonly` | `no` | Enable AOF |
| `appenddirname` | `appendonlydir` | Directory for MP-AOF files (Redis 7+ uses directory, not single file) |
| `appendfilename` | `appendonly.aof` | Ignored when `appenddirname` is set |
| `appendfsync` | `everysec` | fsync policy |

### Rewrite Buffer (Advanced)

| Config | Default | Description |
|--------|---------|-------------|
| `client-output-buffer-limit` (normal) | `256mb 64mb 60` | Hard limit / soft limit / soft seconds for rewrite buffer. If buffer hits hard limit during rewrite → child killed → rewrite fails |
| `aof-rewrite-buffer-size` | (auto) | Rewrite buffer size, auto-tuned based on output buffer limits |

## 4. Production Config Templates

### Pure Cache (no durability, accept 100% loss on restart)

```txt
# File: redis-pure-cache.conf
save ""                           # No RDB snapshot
appendonly no                     # No AOF — durability not needed

maxmemory-policy allkeys-lru      # Evict LRU keys when memory full
maxmemory 8gb

# MUST HAVE: cache warmer running post-restart
# Data can be rebuilt from source of truth in <100ms
```

**When right**: Rate limiter, computed result cache, CDN edge cache, feature flag store.
**When wrong**: Session store, shopping cart, any user-generated state.

---

### Session Store (~1s data loss acceptable, hybrid RDB+AOF)

```txt
# File: redis-session-store.conf

# RDB: baseline snapshot every 5 minutes
save 300 1    # >= 1 change in 300s → snapshot
save 60 10000 # OR >= 10K changes in 60s

# AOF: ~1s data loss, fast restart
appendonly yes
appendfsync everysec             # Max ~1s data loss
aof-use-rdb-preamble yes         # RDB base (fast load) + AOF tail (durability)
aof-load-truncated yes           # Load partial AOF on crash (skip corrupt tail)

# Rewrite: aggressive to keep AOF small
auto-aof-rewrite-percentage 100  # Rewrite at 2x size
auto-aof-rewrite-min-size 64mb   # Don't rewrite below 64MB

# Disk: DEDICATED SSD (not shared with DB)
dir /mnt/nvme-redis-sessions

# Restart target must be measured on the same hardware and data model.
# 10GB RDB load can be ~20-120s depending on CPU, disk, encoding, and container I/O.
# If SLA is <30s: shard smaller, reduce session footprint, or rebuild from DB.
```

**When right**: User sessions, shopping carts, any state that can tolerate ~1s loss.
**When wrong**: Financial, payment idempotency, distributed locks.

---

### Financial-like Idempotency Store (near-zero data loss)

```txt
# File: redis-idempotency.conf

# HARD TRUTH: Redis is NOT a true durable store.
# Always pair with PostgreSQL unique constraint for idempotency token.
# Redis = fast path coordination. PostgreSQL = source of truth.

# RDB: backup every 15 minutes
save 900 1

# AOF: maximum durability
appendonly yes
appendfsync always               # ONLY safe on dedicated NVMe with PLP
aof-use-rdb-preamble yes         # Fast load (RDB) + AOF tail
aof-load-truncated yes           # Safety net

# AOF rewrite: conservative (fork is expensive)
auto-aof-rewrite-percentage 200  # Rewrite at 3x (less frequent)
auto-aof-rewrite-min-size 256mb  # Don't rewrite below 256MB

# Disk: DEDICATED NVMe with power-loss protection
dir /mnt/nvme-redis-idempotency

# HARD LIMIT: appendfsync always requires NVMe SSD
# On SATA SSD: p99 ~50-100ms → client timeout → cascade failure
# On NVMe + PLP: p99 ~1-3ms → acceptable

# Monitoring non-negotiable:
# aof_delayed_fsync MUST be 0 always — alert if > 0
# Alert if latest_fork_usec > 1_000_000 (1 second)
# Alert if aof_last_bgrewrite_status = error
```

## 5. TypeScript Code Snippets (ioredis)

### Monitor INFO persistence fields for AOF rewrite

```typescript
// File: src/redis-persistence.ts
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });

interface AofRewriteStatus {
  aofEnabled: boolean;
  aofRewriteInProgress: boolean;
  aofRewriteScheduled: boolean;
  aofLastRewriteTimeSec: number;
  aofCurrentRewriteTimeSec: number;
  aofLastBgrewriteStatus: string;
  aofDelayedFsync: number;
  aofLastWriteStatus: string;
  latestForkUsec: number;
}

function parsePersistenceInfo(info: string): AofRewriteStatus {
  const fields: AofRewriteStatus = {
    aofEnabled: false,
    aofRewriteInProgress: false,
    aofRewriteScheduled: false,
    aofLastRewriteTimeSec: 0,
    aofCurrentRewriteTimeSec: 0,
    aofLastBgrewriteStatus: '',
    aofDelayedFsync: 0,
    aofLastWriteStatus: '',
    latestForkUsec: 0,
  };

  for (const line of info.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const colonIdx = trimmed.indexOf(':');
    if (colonIdx === -1) continue;

    const key = trimmed.slice(0, colonIdx).trim();
    const val = trimmed.slice(colonIdx + 1).trim();

    switch (key) {
      case 'aof_enabled':           fields.aofEnabled = val === '1'; break;
      case 'aof_rewrite_in_progress': fields.aofRewriteInProgress = val === '1'; break;
      case 'aof_rewrite_scheduled':   fields.aofRewriteScheduled = val === '1'; break;
      case 'aof_last_rewrite_time_sec': fields.aofLastRewriteTimeSec = parseInt(val, 10) || 0; break;
      case 'aof_current_rewrite_time_sec': fields.aofCurrentRewriteTimeSec = parseInt(val, 10) || 0; break;
      case 'aof_last_bgrewrite_status': fields.aofLastBgrewriteStatus = val; break;
      case 'aof_delayed_fsync':      fields.aofDelayedFsync = parseInt(val, 10) || 0; break;
      case 'aof_last_write_status':  fields.aofLastWriteStatus = val; break;
      case 'latest_fork_usec':      fields.latestForkUsec = parseInt(val, 10) || 0; break;
    }
  }
  return fields;
}

async function getRewriteStatus(): Promise<AofRewriteStatus> {
  const info = await redis.info('persistence');
  return parsePersistenceInfo(info);
}

async function waitForRewriteComplete(timeoutMs = 300_000): Promise<void> {
  const start = Date.now();
  while (true) {
    const status = await getRewriteStatus();
    if (!status.aofRewriteInProgress) {
      console.log(`Rewrite complete. Total time: ${status.aofLastRewriteTimeSec}s`);
      return;
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error(`Rewrite timeout after ${timeoutMs}ms`);
    }
    await new Promise(resolve => setTimeout(resolve, 500));
    process.stdout.write(`.`);
  }
}

async function triggerAndMonitorBgrewriteaof(): Promise<void> {
  // Enable AOF if not already
  await redis.config('SET', 'appendonly', 'yes');
  await redis.config('SET', 'appendfsync', 'everysec');

  // Trigger BGREWRITEAOF
  const result = await redis.bgrewriteaof();
  console.log('BGREWRITEAOF triggered:', result);

  // Monitor until complete
  await waitForRewriteComplete();

  // Final status check
  const status = await getRewriteStatus();
  console.log('\nFinal status:');
  console.log(`  aof_last_bgrewrite_status: ${status.aofLastBgrewriteStatus}`);
  console.log(`  latest_fork_usec: ${status.latestForkUsec}μs (${(status.latestForkUsec / 1000).toFixed(1)}ms)`);
  console.log(`  aof_delayed_fsync: ${status.aofDelayedFsync}`);
  console.log(`  aof_last_write_status: ${status.aofLastWriteStatus}`);
}

triggerAndMonitorBgrewriteaof()
  .then(() => { redis.disconnect(); process.exit(0); })
  .catch(err => { console.error(err); redis.disconnect(); process.exit(1); });
```

### Benchmark write latency across fsync policies

```typescript
// File: src/benchmark-fsync.ts
import Redis from 'ioredis';

interface LatencyResult {
  policy: string;
  p50: number;
  p95: number;
  p99: number;
  opsPerSec: number;
}

function percentile(sorted: number[], p: number): number {
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

async function benchmarkFsync(
  redis: Redis,
  policy: string,
  commandCount = 10_000,
): Promise<LatencyResult> {
  await redis.config('SET', 'appendfsync', policy);

  const latencies: number[] = [];
  const value = 'x'.repeat(1024); // 1KB payload

  for (let i = 0; i < commandCount; i++) {
    const key = `bench:${policy}:${i}`;
    const start = process.hrtime.bigint();
    await redis.set(key, value);
    const end = process.hrtime.bigint();
    latencies.push(Number(end - start) / 1_000_000); // ms
  }

  latencies.sort((a, b) => a - b);

  const startTotal = process.hrtime.bigint();
  const pipe = redis.pipeline();
  for (let i = 0; i < commandCount; i++) {
    pipe.set(`bench-pipe:${policy}:${i}`, value);
  }
  await pipe.exec();
  const totalMs = Number(process.hrtime.bigint() - startTotal) / 1_000_000;

  return {
    policy,
    p50: parseFloat(percentile(latencies, 50).toFixed(3)),
    p95: parseFloat(percentile(latencies, 95).toFixed(3)),
    p99: parseFloat(percentile(latencies, 99).toFixed(3)),
    opsPerSec: Math.round((commandCount * 1000) / totalMs),
  };
}

async function main() {
  const redis = new Redis({ host: 'localhost', port: 6379, maxRetriesPerRequest: 3 });
  await redis.config('SET', 'appendonly', 'yes');

  const policies = ['no', 'everysec', 'always'];
  const results: LatencyResult[] = [];

  for (const policy of policies) {
    console.log(`\nBenchmarking appendfsync ${policy}...`);
    const result = await benchmarkFsync(redis, policy);
    results.push(result);
    console.log(`  p50: ${result.p50}ms | p95: ${result.p95}ms | p99: ${result.p99}ms | ops/sec: ${result.opsPerSec}`);
    await new Promise(r => setTimeout(r, 2000)); // Let fsync settle
  }

  console.log('\n=== Summary ===');
  console.table(results);

  await redis.config('SET', 'appendfsync', 'everysec');
  redis.disconnect();
}

main().catch(console.error);
```

## 6. Go Code Snippets (go-redis/v9)

### Monitor AOF rewrite status

```go
// File: cmd/aof-monitor/main.go
package main

import (
    "context"
    "fmt"
    "strconv"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

type AofInfo struct {
    Enabled            bool
    RewriteInProgress   bool
    RewriteScheduled    bool
    LastRewriteSec     int64
    CurrentRewriteSec  int64
    LastBgrewriteStatus string
    DelayedFsync       int64
    LastWriteStatus    string
    LatestForkUsec     int64
}

func ParseAofInfo(info string) *AofInfo {
    a := &AofInfo{}
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
        case "aof_enabled":
            a.Enabled = val == "1"
        case "aof_rewrite_in_progress":
            a.RewriteInProgress = val == "1"
        case "aof_rewrite_scheduled":
            a.RewriteScheduled = val == "1"
        case "aof_last_rewrite_time_sec":
            a.LastRewriteSec, _ = strconv.ParseInt(val, 10, 64)
        case "aof_current_rewrite_time_sec":
            a.CurrentRewriteSec, _ = strconv.ParseInt(val, 10, 64)
        case "aof_last_bgrewrite_status":
            a.LastBgrewriteStatus = val
        case "aof_delayed_fsync":
            a.DelayedFsync, _ = strconv.ParseInt(val, 10, 64)
        case "aof_last_write_status":
            a.LastWriteStatus = val
        case "latest_fork_usec":
            a.LatestForkUsec, _ = strconv.ParseInt(val, 10, 64)
        }
    }
    return a
}

func GetAofInfo(ctx context.Context, rdb *redis.Client) (*AofInfo, error) {
    text, err := rdb.Do(ctx, "INFO", "persistence").Text()
    if err != nil {
        return nil, err
    }
    return ParseAofInfo(text), nil
}

func WaitForRewrite(ctx context.Context, rdb *redis.Client, timeout time.Duration) error {
    deadline := time.Now().Add(timeout)
    for {
        if time.Now().After(deadline) {
            return fmt.Errorf("timeout waiting for AOF rewrite")
        }
        aof, err := GetAofInfo(ctx, rdb)
        if err != nil {
            return err
        }
        if !aof.RewriteInProgress {
            return nil
        }
        fmt.Printf("Rewrite in progress: %ds elapsed | fork: %dμs\n",
            aof.CurrentRewriteSec, aof.LatestForkUsec)
        time.Sleep(500 * time.Millisecond)
    }
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    defer rdb.Close()

    // Enable AOF
    if err := rdb.ConfigSet(ctx, "appendonly", "yes").Err(); err != nil {
        fmt.Printf("Note: %v\n", err)
    }
    if err := rdb.ConfigSet(ctx, "appendfsync", "everysec").Err(); err != nil {
        fmt.Printf("Note: %v\n", err)
    }

    // Trigger BGREWRITEAOF
    result, err := rdb.BgRewriteAOF(ctx).Result()
    if err != nil {
        fmt.Printf("BgRewriteAOF error: %v\n", err)
    } else {
        fmt.Printf("BGREWRITEAOF started: %s\n", result)
    }

    // Wait for completion
    if err := WaitForRewrite(ctx, rdb, 5*time.Minute); err != nil {
        fmt.Printf("Error: %v\n", err)
    } else {
        fmt.Println("Rewrite complete!")
    }

    // Final status
    aof, _ := GetAofInfo(ctx, rdb)
    fmt.Printf("Status | last_bgrewrite_status: %s | fork: %dμs | delayed_fsync: %d | last_write_status: %s\n",
        aof.LastBgrewriteStatus, aof.LatestForkUsec, aof.DelayedFsync, aof.LastWriteStatus)
}
```

## 7. Docker Compose Template for AOF Rewrite Lab

```yaml
# File: docker-compose.yml
version: "3.9"

services:
  redis-aof:
    image: redis:7-alpine
    container_name: redis-aof-day7
    command: >
      redis-server
      --save ""
      --appendonly yes
      --appendfsync everysec
      --aof-use-rdb-preamble yes
      --aof-load-truncated yes
      --auto-aof-rewrite-percentage 100
      --auto-aof-rewrite-min-size 64mb
      --aof-incremental-fsync yes
      --loglevel notice
    volumes:
      - aof-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  aof-data:
```

## 8. Links & References

### Official Documentation
- https://redis.io/docs/management/persistence/ — Redis persistence official docs
- https://redis.io/docs/management/optimization/aof/ — AOF optimization guide
- https://redis.io/docs/management/optimization/rdb/ — RDB internals
- https://redis.io/docs/management/config/ — Config directives reference

### Redis Source Code
- `src/aof.c` — AOF implementation, rewrite logic, feedAppendOnlyFile
- `src/aof.c:rewriteAppendOnlyFile()` — child process: serialize dataset to temp AOF
- `src/aof.c:aofCheckAndFixCorruption()` — redis-check-aof --fix logic
- `src/server.c:appendFsync()` — fsync policy implementation (server.aof_fsync)
- `src/server.h:server.aof_state` — AOF on/off/wait_rewrite states

### Blog Posts & Technical Articles
- **antirez "Redis Persistence Demystified"**: oldblog.antirez.com/post/redis-persistence-demystified
- **AOF rewrite deep dive**: redis.io/topics/ersistence (antirez blog archive)
- **Redis 7 Multi-Part AOF release notes**: github.com/redis/redis/releases/tag/7.0.0
- **Twitter AOF fsync contention case**: nathanmarz.com/blog/how-twitter-uses-redis (historical)
- **Linux fsync semantics**: `man 2 fsync`, `man 2 fdatasync`

### Linux Kernel Parameters
```bash
# /proc/sys/vm/dirty_writeback_centisecs  (default: 500 = 5s)
# /proc/sys/vm/dirty_expire_centisecs     (default: 3000 = 30s)
# Pages older than dirty_expire_centisecs are candidates for writeback
# Relevant when appendfsync no (OS controls flush timing)

# Always set for Redis:
vm.overcommit_memory = 1
# Disable THP:
echo never > /sys/kernel/mm/transparent_hugepage/enabled
```
