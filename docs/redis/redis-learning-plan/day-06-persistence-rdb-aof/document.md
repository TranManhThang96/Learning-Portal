# Day 6: Persistence RDB & AOF — Reference Document

## 1. Cheat Sheet: Persistence Commands

```txt
-- Trigger snapshot
BGSAVE                          -- non-blocking, standard production
SAVE                            -- blocking, EMERGENCY ONLY, never in prod

-- Trigger AOF rewrite (Day 7)
BGREWRITEAOF                    -- non-blocking AOF compaction

-- Check status
LASTSAVE                        -- Unix timestamp of last successful BGSAVE
DBSIZE                          -- number of keys (verify after reload)

-- Reload
DEBUG RELOAD                    -- reload RDB from disk, BLOCKING, use with care

-- Monitoring
INFO persistence                -- all persistence metrics (see section 3)
```

## 2. Config Snippets cho 3 Scenario

### Pure Cache (no durability, cold start risk accepted)

```txt
# File: redis-pure-cache.conf
save ""                         # Disable RDB
appendonly no                   # Disable AOF

# MUST HAVE: cache warmer running post-restart
# If cache miss causes DB overload → enable RDB backup + warmer
```

### Session Store (Hybrid — fast restart + ~1s data loss)

```txt
# File: redis-session-store.conf

# RDB: hourly baseline snapshot
save 3600 1   # >= 1 key change in 3600s → snapshot
save 300 100  # OR >= 100 keys in 300s
save 60 10000 # OR >= 10000 keys in 60s

# AOF: append-only log for recent changes
appendonly yes
appendfsync everysec            # Durability: ~1s data loss max
aof-use-rdb-preamble yes        # Hybrid: RDB base + AOF tail

# File locations
dir /data/redis
dbfilename dump.rdb
appendfilename appendonly.aof
appenddirname appendonlydir

# AOF rewrite (Day 7): auto-triggered when AOF > 64MB
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-load-truncated yes         # Load partial AOF on crash
```

### Idempotency / Financial-like Store (max durability)

```txt
# File: redis-idempotency.conf

# RDB: backup every 15 minutes
save 900 1

# AOF: maximum durability
appendonly yes
appendfsync always              # Near-zero data loss after ACK (best effort)
aof-use-rdb-preamble yes        # Fast load (RDB) + durability (AOF tail)

# File locations (DEDICATED disk, NOT same as DB)
dir /mnt/nvme-redis-persistence
dbfilename dump.rdb
appenddirname appendonlydir

# Safety
aof-load-truncated yes
aof-use-rdb-preamble yes

# Caveat: Redis is NOT a true durable store (see lesson pitfall #12)
# Always pair with PostgreSQL/Kafka for idempotency record
```

## 3. INFO Persistence Field Reference

```txt
INFO persistence
```

| Field | Type | Description |
|-------|------|-------------|
| `rdb_last_save_time` | Unix timestamp | Last successful BGSAVE time |
| `rdb_last_bgsave_time_sec` | Seconds | Duration of last BGSAVE |
| `rdb_changes_since_last_save` | Integer | Number of key changes since last save |
| `rdb_bgsave_in_progress` | 0/1 | Is BGSAVE currently running? |
| `rdb_current_bgsave_time_sec` | Seconds | Duration of current BGSAVE (if running) |
| `aof_enabled` | 0/1 | Is AOF enabled? |
| `aof_rewrite_in_progress` | 0/1 | Is BGREWRITEAOF running? |
| `aof_rewrite_scheduled` | 0/1 | BGREWRITEAOF queued after current BGSAVE? |
| `aof_last_rewrite_time_sec` | Seconds | Duration of last BGREWRITEAOF |
| `aof_current_rewrite_time_sec` | Seconds | Duration of current BGREWRITEAOF |
| `aof_last_bgrewrite_status` | ok/error | Last BGREWRITEAOF status |
| `aof_last_write_status` | ok/error | Last AOF write status |
| `aof_delayed_fsync` | Integer | Times fsync was delayed (everysec mode) |
| `aof_pending_bio_fsync` | Integer | Pending background fsync operations |
| `aof_last_load_duration_ms` | ms | How long AOF/RDB load took at startup |
| `loading` | 0/1 | Is Redis currently loading RDB/AOF? |
| `loading_loaded_bytes` | Bytes | Bytes loaded so far during startup |
| `loading_total_bytes` | Bytes | Total bytes to load at startup |
| `loading_loaded_perc` | % | Percentage loaded |
| `latest_fork_usec` | Microseconds | Last fork duration (alert if > 1s) |

## 4. Restart Time Table (Redis 7.x, realistic production)

| Dataset | RDB Only | AOF Only (`everysec`) | Hybrid (RDB+AOF) |
|---------|----------|------------------------|-------------------|
| 1GB | 5-10s | 30-60s | 5-15s |
| 10GB | 60-120s | 5-15 min | 60-150s |
| 50GB | 5-20 min | 30-90 min | 5-30 min |
| 100GB | 10-40 min | 60-180 min | 10-60 min |

**Factors affecting restart time**:
- AOF file thường **3-10x lớn hơn** RDB (RESP verbosity)
- AOF replay = sequential command execution = slower than binary load
- Hybrid = RDB load (fast) + AOF tail replay (small if AOF rewritten recently)
- Disk speed: NVMe SSD ~3-5x faster than SATA SSD for sequential read

## 5. Linux Kernel Configuration

```bash
# /etc/sysctl.conf or sysctl commands

# CRITICAL: Memory overcommit — allow COW without OOM on fork
vm.overcommit_memory = 1

# CRITICAL: Disable Transparent Huge Pages — THP causes fork() latency spikes
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag

# Optional: Swappiness (lower = less likely to swap under memory pressure)
vm.swappiness = 10

# Verify
cat /proc/sys/vm/overcommit_memory
cat /sys/kernel/mm/transparent_hugepage/enabled
```

**Explanation**:
- `vm.overcommit_memory=1`: Kernel allows allocating more memory than physically available. Required for COW (fork) to not trigger OOM when parent writes during BGSAVE.
- **THP**: Transparent Huge Pages cause 2-10x fork() latency increase because kernel defrag process interferes with fork. Always disable.

## 6. Go Code Snippets (go-redis/v9)

### Helper: Trigger BGSAVE và poll LASTSAVE

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

// TriggerBGSAVE triggers a background save and waits for completion.
// Returns the new LASTSAVE timestamp and duration.
func TriggerBGSAVE(ctx context.Context, rdb *redis.Client) (int64, time.Duration, error) {
    // Get baseline LASTSAVE
    before, err := rdb.LastSave(ctx).Result()
    if err != nil {
        return 0, 0, fmt.Errorf("LASTSAVE: %w", err)
    }

    // Trigger BGSAVE
    err = rdb.BgSave(ctx).Err()
    if err != nil {
        return 0, 0, fmt.Errorf("BGSAVE: %w", err)
    }

    // Poll until LASTSAVE changes (BGSAVE complete)
    start := time.Now()
    ticker := time.NewTicker(100 * time.Millisecond)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return 0, 0, ctx.Err()
        case <-ticker.C:
            after, err := rdb.LastSave(ctx).Result()
            if err != nil {
                continue
            }
            if after > before {
                return after, time.Since(start), nil
            }
        }
    }
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
        DB:   0,
    })
    defer rdb.Close()

    ts, dur, err := TriggerBGSAVE(ctx, rdb)
    if err != nil {
        log.Fatalf("BGSAVE failed: %v", err)
    }
    fmt.Printf("BGSAVE complete: LASTSAVE=%d, duration=%v\n", ts, dur)
}
```

### Helper: Parse INFO persistence fields

```go
package main

import (
    "fmt"
    "strconv"
    "strings"

    "github.com/redis/go-redis/v9"
)

type PersistenceInfo struct {
    RDBEnabled           bool
    RDBBGSaveInProgress  bool
    RDBLastSaveTime      int64
    RDBLastSaveDurationMs int64
    RDBChangesSinceLast  int64

    AOFEnabled           bool
    AOFRewriteInProgress  bool
    AOFDelayedFsync      int64
    AOFLastLoadMs        int64
    AOFLastWriteStatus   string

    LatestForkUsec       int64
    Loading              bool
}

func ParsePersistenceInfo(info string) (*PersistenceInfo, error) {
    p := &PersistenceInfo{}
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
        case "rdb_bgsave_in_progress":
            p.RDBBGSaveInProgress = val == "1"
        case "rdb_last_save_time":
            p.RDBLastSaveTime, _ = strconv.ParseInt(val, 10, 64)
        case "rdb_last_bgsave_time_sec":
            p.RDBLastSaveDurationMs, _ = strconv.ParseInt(val, 10, 64)
            p.RDBLastSaveDurationMs *= 1000
        case "rdb_changes_since_last_save":
            p.RDBChangesSinceLast, _ = strconv.ParseInt(val, 10, 64)
        case "aof_enabled":
            p.AOFEnabled = val == "1"
        case "aof_rewrite_in_progress":
            p.AOFRewriteInProgress = val == "1"
        case "aof_delayed_fsync":
            p.AOFDelayedFsync, _ = strconv.ParseInt(val, 10, 64)
        case "aof_last_load_duration_ms":
            p.AOFLastLoadMs, _ = strconv.ParseInt(val, 10, 64)
        case "aof_last_write_status":
            p.AOFLastWriteStatus = val
        case "latest_fork_usec":
            p.LatestForkUsec, _ = strconv.ParseInt(val, 10, 64)
        case "loading":
            p.Loading = val == "1"
        }
    }
    return p, nil
}

func main() {
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})

    info, err := rdb.Do(ctx, "INFO", "persistence").Text()
    if err != nil {
        panic(err)
    }

    p, err := ParsePersistenceInfo(info)
    if err != nil {
        panic(err)
    }

    fmt.Printf("BGSAVE running: %v | Latest fork: %dμs | AOF delayed fsync: %d\n",
        p.RDBBGSaveInProgress, p.LatestForkUsec, p.AOFDelayedFsync)
    fmt.Printf("AOF enabled: %v | Fork > 1s? %v\n",
        p.AOFEnabled, p.LatestForkUsec > 1_000_000)
    fmt.Printf("AOF last write status: %s | AOF last load: %dms\n",
        p.AOFLastWriteStatus, p.AOFLastLoadMs)
}
```

### Crash Simulation với Docker

```bash
# Start Redis container
docker run -d --name redis-persistence-test \
  -v redis-persistence-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --appendfsync everysec

# Write data and verify key count
docker exec redis-persistence-test redis-cli SET durable:key "value-before-crash"
docker exec redis-persistence-test redis-cli DBSIZE
# Should be 1
sleep 2   # allow appendfsync everysec to flush before the crash test

# Simulate crash: kill -9 (SIGKILL, no cleanup)
docker kill --signal=9 redis-persistence-test

# Start new container with same volume (data should survive)
docker run -d --name redis-persistence-test2 \
  --volumes-from redis-persistence-test \
  redis:7-alpine \
  redis-server --appendonly yes --appendfsync everysec

# Verify data survived
sleep 2
docker exec redis-persistence-test2 redis-cli DBSIZE
```

## 7. Docker Compose Template

```yaml
# docker-compose-persistence-lab.yml
version: "3.9"

services:
  # Redis with RDB only (pure cache config)
  redis-rdb-only:
    image: redis:7-alpine
    container_name: redis-rdb-only
    command: >
      redis-server
      --save "3600 1 300 100 60 10000"
      --appendonly no
    volumes:
      - rdb-only-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  # Redis with AOF only (durability config)
  redis-aof-only:
    image: redis:7-alpine
    container_name: redis-aof-only
    command: >
      redis-server
      --save ""
      --appendonly yes
      --appendfsync everysec
      --aof-load-truncated yes
    volumes:
      - aof-only-data:/data
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6380", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  # Redis with hybrid persistence
  redis-hybrid:
    image: redis:7-alpine
    container_name: redis-hybrid
    command: >
      redis-server
      --save "3600 1 300 100 60 10000"
      --appendonly yes
      --appendfsync everysec
      --aof-use-rdb-preamble yes
      --aof-load-truncated yes
    volumes:
      - hybrid-data:/data
    ports:
      - "6381:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6381", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

volumes:
  rdb-only-data:
  aof-only-data:
  hybrid-data:
```

## 8. Links & References

### Official Documentation
- https://redis.io/docs/management/persistence/ — Redis persistence official docs
- https://redis.io/docs/management/optimization/rdb/ — RDB internals
- https://redis.io/docs/management/optimization/aof/ — AOF optimization
- https://redis.io/docs/management/replication/ — Persistence + replication interaction

### Redis Source Code
- `src/rdb.c` — RDB save/load implementation
- `src/rdb.h` — RDB format specification
- `src/aof.c` — AOF implementation
- `src/anet.c` — Networking (fork monitoring)
- `src/server.c` — Persistence config handling

### Reading List
- **GitLab Incident Postmortem (2017)**: gitlab.com/blog/2017/03/02/gitlab-incident-report-31-jan-2017
- **antirez "Redis Persistence Demystified"**: oldblog.antirez.com/post/redis-persistence-demystified
- **Redis fork() and copy-on-write**: linux kernel docs — `man 2 fork`, `man 2 write`
- **Why fork() can be slow (Marius Eriksen, Twitter)**: tailcall.io/blog/fork-cost
- **Linux memory overcommit**: `man 5 proc` — vm.overcommit_memory
- **COW and fork**: `man 7 copy_on_write` (kernel docs)
- **AOF rewrite deep dive**: redis.io/docs/management/optimization/aof/
