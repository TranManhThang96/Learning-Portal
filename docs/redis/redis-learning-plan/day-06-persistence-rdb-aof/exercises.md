# Day 6: Persistence RDB & AOF — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: Go (go-redis/v9)
**Docker images**: redis:7-alpine

---

## 1. Warm-up Exercises (15–20 phút)

### 1.1. Inspect Persistence Status

```bash
redis-cli INFO persistence
```

Đọc và giải thích các fields sau:

- `rdb_bgsave_in_progress`
- `rdb_changes_since_last_save`
- `rdb_last_save_time`
- `aof_enabled`
- `aof_delayed_fsync`
- `latest_fork_usec`

**Expected output** (trên fresh Redis):

```
rdb_last_save_time:1732500000
rdb_changes_since_last_save:0
rdb_bgsave_in_progress:0
aof_enabled:0
aof_delayed_fsync:0
latest_fork_usec:0
```

### 1.2. Check Current Persistence Config

```bash
redis-cli CONFIG GET save
redis-cli CONFIG GET appendonly
redis-cli CONFIG GET appendfsync
redis-cli CONFIG GET dir
```

**Expected output** (default Redis 7):

```
1) "save"
2) "3600 1 300 100 60 10000"

1) "appendonly"
2) "no"

1) "appendfsync"
2) "everysec"

1) "dir"
2) "/data"
```

### 1.3. Trigger BGSAVE và Measure Duration

```bash
redis-cli BGSAVE
```

Output:

```
Background saving started
```

Kiểm tra trạng thái:

```bash
# Check rdb_last_save_time trước
BEFORE=$(redis-cli LASTSAVE)

# Trigger BGSAVE
redis-cli BGSAVE

# Poll cho đến khi BGSAVE xong
while true; do
  STATUS=$(redis-cli INFO persistence | grep rdb_bgsave_in_progress | cut -d: -f2 | tr -d '\r')
  if [ "$STATUS" = "0" ]; then
    AFTER=$(redis-cli LASTSAVE)
    echo "BGSAVE done. Before=$BEFORE, After=$AFTER"
    break
  fi
  echo "BGSAVE still running..."
  sleep 1
done

# Check fork duration
redis-cli INFO persistence | grep latest_fork_usec
```

**Expected**: `latest_fork_usec` ~100-500ms (tùy system, fresh Redis dataset small).

### 1.4. DEBUG RELOAD (Blocking — Warning)

```bash
# WARNING: DEBUG RELOAD is blocking. Không chạy khi Redis đang under load.
redis-cli DEBUG RELOAD
```

Output:

```
OK
```

**Dùng để**: reload RDB file sau khi restore backup mà không restart Redis process. Trong prod: chỉ chạy khi maintenance window.

### 1.5. Verify RDB File Exists

```bash
ls -lh /data/dump.rdb 2>/dev/null || echo "RDB file not found (default /data may not be mounted)"
```

Nếu chạy trong Docker:

```bash
docker exec <container> ls -lh /data/dump.rdb
docker exec <container> stat /data/dump.rdb
```

---

## 2. Hands-on Lab (60–70 phút)

### Setup: 3 Redis Containers với 3 Configs

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis-rdb:
    image: redis:7-alpine
    container_name: redis-rdb
    command: >
      redis-server
      --save "300 1"
      --appendonly no
      --loglevel notice
    volumes:
      - rdb-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-aof:
    image: redis:7-alpine
    container_name: redis-aof
    command: >
      redis-server
      --save ""
      --appendonly yes
      --appendfsync everysec
      --aof-load-truncated yes
      --loglevel notice
    volumes:
      - aof-data:/data
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6380", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-hybrid:
    image: redis:7-alpine
    container_name: redis-hybrid
    command: >
      redis-server
      --save "300 1"
      --appendonly yes
      --appendfsync everysec
      --aof-use-rdb-preamble yes
      --aof-load-truncated yes
      --loglevel notice
    volumes:
      - hybrid-data:/data
    ports:
      - "6381:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6381", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  rdb-data:
  aof-data:
  hybrid-data:
```

### Go Starter Code

**File**: `cmd/lab/main.go`

```go
package main

import (
    "context"
    "fmt"
    "log"
    "os"
    "strconv"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

func main() {
    ctx := context.Background()

    // Connect to 3 Redis instances
    rdbRDB := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    rdbAOF := redis.NewClient(&redis.Options{Addr: "localhost:6380", DB: 1})
    rdbHybrid := redis.NewClient(&redis.Options{Addr: "localhost:6381", DB: 2})

    // Cleanup function
    defer func() {
        rdbRDB.Close()
        rdbAOF.Close()
        rdbHybrid.Close()
    }()

    // Step 0: Verify connectivity
    for name, rdb := range map[string]*redis.Client{
        "RDB":    rdbRDB,
        "AOF":    rdbAOF,
        "Hybrid": rdbHybrid,
    } {
        if err := rdb.Ping(ctx).Err(); err != nil {
            log.Fatalf("[%s] Cannot connect: %v", name, err)
        }
        fmt.Printf("[%s] Connected OK\n", name)
    }
}
```

### Step 1: Write 100K Keys với Pipeline

Thêm function sau vào `main()`:

```go
func writeKeys(ctx context.Context, rdb *redis.Client, prefix string, count int) error {
    pipe := rdb.Pipeline()
    for i := 0; i < count; i++ {
        key := fmt.Sprintf("%s:key:%08d", prefix, i)
        val := fmt.Sprintf("value-%08d-data", i)
        pipe.Set(ctx, key, val, 0)
        if i%1000 == 0 {
            _, err := pipe.Exec(ctx)
            if err != nil {
                return fmt.Errorf("pipeline exec at %d: %w", i, err)
            }
            pipe = rdb.Pipeline()
        }
    }
    _, err := pipe.Exec(ctx)
    return err
}

// In main():
const keyCount = 100_000
start := time.Now()

log.Println("Writing 100K keys to RDB-only...")
if err := writeKeys(ctx, rdbRDB, "rdb", keyCount); err != nil {
    log.Fatalf("RDB write failed: %v", err)
}
fmt.Printf("RDB write done in %v\n", time.Since(start))

start = time.Now()
log.Println("Writing 100K keys to AOF-only...")
if err := writeKeys(ctx, rdbAOF, "aof", keyCount); err != nil {
    log.Fatalf("AOF write failed: %v", err)
}
fmt.Printf("AOF write done in %v\n", time.Since(start))

start = time.Now()
log.Println("Writing 100K keys to Hybrid...")
if err := writeKeys(ctx, rdbHybrid, "hybrid", keyCount); err != nil {
    log.Fatalf("Hybrid write failed: %v", err)
}
fmt.Printf("Hybrid write done in %v\n", time.Since(start))
```

**Expected output** (tùy hardware, approximate):

```
RDB write done in 3-8s
AOF write done in 4-10s
Hybrid write done in 4-10s
```

### Step 2: Trigger BGSAVE và Measure Fork Duration

Thêm function:

```go
func measureFork(ctx context.Context, rdb *redis.Client, name string) (int64, error) {
    // Get latest_fork_usec before
    beforeInfo, err := rdb.Do(ctx, "INFO", "persistence").Text()
    if err != nil {
        return 0, err
    }
    beforeFork := parseField(beforeInfo, "latest_fork_usec")

    // Trigger BGSAVE
    err = rdb.BgSave(ctx).Err()
    if err != nil {
        return 0, fmt.Errorf("BGSAVE: %w", err)
    }

    // Poll until done
    for {
        info, err := rdb.Do(ctx, "INFO", "persistence").Text()
        if err != nil {
            return 0, err
        }
        if parseField(info, "rdb_bgsave_in_progress") == 0 {
            break
        }
        time.Sleep(200 * time.Millisecond)
    }

    // Get latest_fork_usec after BGSAVE
    afterInfo, err := rdb.Do(ctx, "INFO", "persistence").Text()
    if err != nil {
        return 0, err
    }
    afterFork := parseField(afterInfo, "latest_fork_usec")

    // Use the larger value (it's the one recorded during BGSAVE)
    forkUsec := afterFork
    if beforeFork > afterFork {
        forkUsec = beforeFork
    }
    fmt.Printf("[%s] Fork duration: %dμs (%.1fms)\n", name, forkUsec, float64(forkUsec)/1000)
    return forkUsec, nil
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

**Chạy**:

```go
// In main(), after writing keys:
fmt.Println("\n=== Step 2: BGSAVE Fork Duration ===")
rdbRDB.Forever(ctx) // keep rdb-rdb container alive for step 3

forkRDB, _ := measureFork(ctx, rdbRDB, "RDB")
forkAOF, _ := measureFork(ctx, rdbAOF, "AOF")
forkHybrid, _ := measureFork(ctx, rdbHybrid, "Hybrid")

fmt.Printf("\nFork latency summary:\n")
fmt.Printf("  RDB:    %dμs (%.1fms)\n", forkRDB, float64(forkRDB)/1000)
fmt.Printf("  AOF:    N/A (AOF-only has no BGSAVE, only AOF rewrite)\n")
fmt.Printf("  Hybrid: %dμs (%.1fms)\n", forkHybrid, float64(forkHybrid)/1000)
```

**Expected**: fork duration tăng theo dataset size. Với ~100K keys (~10-20MB dataset), fork ~50-200ms. Alert nếu > 1s.

### Step 3: Simulate Crash (kill -9)

**Dùng Docker kill -9**, không `redis-cli SHUTDOWN` (SHUTDOWN có cleanup, không phải crash thực):

```bash
# Stop containers without cleanup (kill -9 equivalent)
docker kill --signal=9 redis-rdb
docker kill --signal=9 redis-aof
docker kill --signal=9 redis-hybrid

echo "All containers killed"
```

**Đợi 5 giây rồi restart**:

```bash
sleep 5

# Restart all containers
docker compose -f docker-compose.yml up -d

echo "Containers restarted. Waiting for startup..."
sleep 5
```

### Step 4: Measure Restart Time

Thêm function đo restart time qua INFO persistence:

```go
func measureRestartTime(ctx context.Context, rdb *redis.Client, name string, containerName string) (time.Duration, error) {
    // Reconnect
    rdb.Close()
    rdb = redis.NewClient(&redis.Options{Addr: rdb.Options().Addr, DB: rdb.DB()})

    start := time.Now()

    // Poll until loading = 0 (Redis finished loading)
    for {
        info, err := rdb.Do(ctx, "INFO", "persistence").Text()
        if err != nil {
            time.Sleep(1 * time.Second)
            continue
        }
        loading := parseField(info, "loading")
        if loading == 0 {
            break
        }
        time.Sleep(500 * time.Millisecond)
    }

    elapsed := time.Since(start)

    // Get aof_last_load_duration_ms if available
    info, _ := rdb.Do(ctx, "INFO", "persistence").Text()
    loadMs := parseField(info, "aof_last_load_duration_ms")

    fmt.Printf("[%s] Restart time: %v (INFO aof_last_load_duration_ms: %dms)\n",
        name, elapsed, loadMs)
    return elapsed, nil
}
```

**Chạy**:

```go
// In main(), after restart:
fmt.Println("\n=== Step 4: Restart Time Measurement ===")

rdbRDB2 := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
rdbAOF2 := redis.NewClient(&redis.Options{Addr: "localhost:6380", DB: 1})
rdbHybrid2 := redis.NewClient(&redis.Options{Addr: "localhost:6381", DB: 2})
defer rdbRDB2.Close()
defer rdbAOF2.Close()
defer rdbHybrid2.Close()

restartRDB, _ := measureRestartTime(ctx, rdbRDB2, "RDB-only", "redis-rdb")
restartAOF, _ := measureRestartTime(ctx, rdbAOF2, "AOF-only", "redis-aof")
restartHybrid, _ := measureRestartTime(ctx, rdbHybrid2, "Hybrid", "redis-hybrid")
```

**Expected** (với ~100K keys, ~10-20MB data):

```
RDB-only restart: 1-5s
AOF-only restart: 10-30s  (replay 100K commands)
Hybrid restart:  1-8s    (RDB load fast + small AOF tail)
```

### Step 5: Count Keys Sau Restart — Data Loss Analysis

```go
func countKeys(ctx context.Context, rdb *redis.Client, name string, prefix string) (int64, error) {
    // SCAN all keys with prefix
    var count int64
    iter := rdb.Scan(ctx, 0, prefix+":key:*", 0).Iterator()
    for iter.Next(ctx) {
        count++
    }
    if err := iter.Err(); err != nil {
        return 0, err
    }
    return count, nil
}

// In main():
fmt.Println("\n=== Step 5: Data Loss Analysis ===")
const expectedKeys = 100_000

rdbRDB3 := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
rdbAOF3 := redis.NewClient(&redis.Options{Addr: "localhost:6380", DB: 1})
rdbHybrid3 := redis.NewClient(&redis.Options{Addr: "localhost:6381", DB: 2})
defer rdbRDB3.Close()
defer rdbAOF3.Close()
defer rdbHybrid3.Close()

for name, rdb, prefix := range []struct {
    name   string
    rdb    *redis.Client
    prefix string
}{
    {"RDB-only", rdbRDB3, "rdb"},
    {"AOF-only", rdbAOF3, "aof"},
    {"Hybrid", rdbHybrid3, "hybrid"},
} {
    count, err := countKeys(ctx, rdb, name, prefix)
    if err != nil {
        fmt.Printf("[%s] Error counting keys: %v\n", name, err)
        continue
    }
    lost := expectedKeys - count
    lossPct := float64(lost) / float64(expectedKeys) * 100
    fmt.Printf("[%s] Keys: %d/%d | Lost: %d (%.1f%%)\n",
        name, count, expectedKeys, lost, lossPct)
}
```

**Expected** (với `save "300 1"` và `appendfsync everysec`):

```
RDB-only:  Keys: 99000-100000/100000 | Lost: 0-1000 (0-1%)
  (Vì BGSAVE đã chạy sau step 2, nên chỉ mất changes trong 1-2 phút)

AOF-only:  Keys: ~100000/100000 | Lost: 0 đến các write trong ~1s cuối
  (AOF append-only với everysec, command đã append nhưng chưa fsync vẫn có thể mất khi crash)

Hybrid:    Keys: ~100000/100000 | Lost: 0 đến các write trong ~1s cuối
  (AOF tail chứa write sau RDB snapshot, nhưng vẫn theo appendfsync everysec)
```

### Step 6: Compare File Sizes

```bash
# RDB file size
docker exec redis-rdb ls -lh /data/dump.rdb

# AOF file size(s)
docker exec redis-aof ls -lh /data/appendonlydir/

# Hybrid file size(s)
docker exec redis-hybrid ls -lh /data/appendonlydir/
```

**Expected**:

```
RDB file:    ~10-20MB (100K keys × ~100 bytes/key ≈ 10MB)
AOF files:  ~15-30MB (RESP verbose, ~150-300 bytes per SET command)
Hybrid:     ~10-20MB base (RDB) + small AOF tail (~1-5MB)
```

Ratio: AOF thường 2-3x RDB size cho cùng dataset.

---

## 3. Challenge Exercise (30–40 phút)

### Scenario A: API Response Cache (100GB dataset, accept 1 hour data loss)

**Yêu cầu**: Thiết kế persistence config cho API response cache.

- Dataset: 100GB
- Traffic: 500K ops/sec (80% reads, 20% writes)
- Acceptable data loss: 1 giờ
- Cold start có cache warmer
- Write throughput không bị ảnh hưởng bởi persistence

**Đề xuất config**:

```txt
# File: redis-api-cache.conf
save "3600 1"           # RDB snapshot mỗi giờ (hoặc khi có thay đổi)
appendonly no           # Không cần AOF (cache loss acceptable)

# Monitoring
# Alert khi rdb_changes_since_last_save > 1000000
# (Có nghĩa > 1M thay đổi mà chưa snapshot)
```

**Giải thích**:
- RDB only vì: 1 giờ data loss acceptable, write overhead của AOF không cần thiết
- `save "3600 1"` = snapshot mỗi giờ nếu có ít nhất 1 key thay đổi
- `appendonly no` = không có AOF overhead → write latency thấp nhất
- Cần cache warmer chạy mỗi giờ sau khi RDB được tạo
- Monitoring: `rdb_changes_since_last_save`, `latest_fork_usec`

**Caveat**: Với 100GB dataset, BGSAVE chạy ~5-20 phút (disk I/O bound). Fork latency ~1-3s. COW overhead: nếu write rate 100K/sec × 100 bytes × 300s = 3GB COW peak. Instance cần 100GB + 3GB headroom = 110GB+.

### Scenario B: User Session Store (10GB, accept 1 second data loss)

**Yêu cầu**: Thiết kế persistence config cho session store.

- Dataset: 10GB
- Sessions: 5 triệu user online
- Acceptable data loss: 1 giây
- Session có user-generated state (cart, preferences)
- Restart nhanh (SLA: 30 giây max)

**Đề xuất config**:

```txt
# File: redis-session.conf
save 3600 1 300 100 60 10000
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
aof-load-truncated yes

# Restart SLA: 10GB RDB load ~60-120s
# + AOF tail replay ~10-30s (1 giây commands = vài MB)
# Total: ~90-150s < 30s? Cần tối ưu:
# → Giảm save interval: save 60 100 (snapshot mỗi phút)
# → Kết quả: AOF tail nhỏ hơn, hybrid restart ~90s
```

**Giải thích**:
- Hybrid = RDB (fast load) + AOF (durability)
- `everysec` = tối đa 1 giây data loss
- RDB preamble giúp restart nhanh
- `save 60 10000` = snapshot mỗi phút (đảm bảo AOF tail luôn nhỏ)
- Monitoring: `aof_delayed_fsync`, `latest_fork_usec`, `aof_pending_bio_fsync`

### Scenario C: Idempotency Store cho Payment API (5GB, near-zero Redis data loss, DB vẫn là source of truth)

**Yêu cầu**: Thiết kế persistence cho idempotency key storage.

- Dataset: 5GB
- Keys: idempotency tokens từ payment requests
- Không accept data loss (payment = money)
- Retry rate: 5% (payment có thể retry)
- Redis không phải primary store

**Đề xuất config**:

```txt
# File: redis-idempotency.conf
save 900 1              # RDB backup 15 phút
appendonly yes
appendfsync always       # Near-zero data loss after ACK (best effort)
aof-use-rdb-preamble yes
aof-load-truncated yes

# Caveat 1: Redis is NOT a true durable store
#   - fsync always vẫn có edge case (kernel bug, disk firmware bug)
#   - Pair với: PostgreSQL unique constraint trên idempotency_token
#   - Redis = fast path, PostgreSQL = source of truth
#
# Caveat 2: appendfsync always impact
#   - p99 write latency: +1-10ms per write
#   - Payment API: 5K TPS → p99 ~5-15ms (acceptable cho payment)
#   - Nếu p99 > 50ms → giảm rate hoặc dùng everysec + PostgreSQL lock
#
# Caveat 3: OOM risk với COW
#   - 5GB dataset → fork ~100-200ms
#   - COW overhead: 100K writes/sec × 60s × 100B = 600MB
#   - Instance cần 5GB + 600MB headroom = 6GB minimum
#   - Recommend 8GB+ instance
```

**Architecture**:
```
Payment Request (idempotency_token: "tok_abc123")
  |
  v
Redis GET idempotency_token
  |
  ├── EXISTS → return cached response (fast path)
  |
  └── NOT EXISTS → Redis SETNX idempotency_token "processing"
                    |
                    +→ Process payment
                    |
                    +→ PostgreSQL INSERT idempotency_token (durable record)
                    |
                    +→ Redis SET idempotency_token response (TTL 24h)
                    |
                    +→ Return response
```

**Hard problem**: Redis durability không phải PostgreSQL durability. Nếu:
- Redis crash + disk corruption → mất idempotency token → double charge risk
- **Mitigation**: PostgreSQL unique constraint = ultimate idempotency guarantee

**Monitoring runbook cho BGSAVE OOM**:
```bash
# Alert if:
#   latest_fork_usec > 2000000   (2s fork = too slow)
#   aof_delayed_fsync delta > 10  (fsync backlog building up)
#   mem_fragmentation_ratio > 1.8 (COW pages fragmentation)

# If OOM kill detected:
#   1. Scale up instance immediately
#   2. Check vm.overcommit_memory=1
#   3. Check if write rate can be reduced
#   4. Monitor rdb_changes_since_last_save
#   5. If OOM persists: sharding to reduce per-node memory
```

---

## 4. Reflection Questions

### Question 1: Khi nào persistence off là quyết định đúng?

Không phải lúc nào "bật persistence" cũng là đúng. Persistence off là đúng khi:

- **Redis là pure computation cache**: kết quả có thể tính lại trong <100ms từ source of truth (VD: computed aggregation, rendered template)
- **Cold start không gây cascade failure**: backend DB có capacity để serve tất cả cache miss sau restart
- **Write throughput cực kỳ cao**: persistence overhead không đáng (VD: time-series data ingestion 1M+ writes/sec)
- **Data có TTL tự nhiên**: data tự expire sau vài phút, persistence không help được gì

**Reflection**: Nếu bạn disable persistence, bạn có cache warmer chạy khi nào? Có monitoring cho cold start không?

### Question 2: Hybrid persistence vs AOF-only — khi nào hybrid không phải là lựa chọn tốt?

Hybrid có thể **không phù hợp** khi:

- **Dataset rất nhỏ** (< 1GB): RDB load nhanh, AOF tail cũng nhỏ → hybrid overhead không justify
- **Write rate cực kỳ cao**: AOF tail growth nhanh → frequent rewrite needed → hybrid benefit giảm
- **Disk space constrained**: Hybrid cần cả RDB + AOF disk space (có thể gấp đôi storage)
- **AOF rewrite overhead**: Nếu disk chậm, AOF rewrite (Day 7) gây latency spike → hybrid không giải quyết được root cause

### Question 3: Backup strategy có thể chỉ dựa vào RDB/AOF file không? Tại sao?

**Không**. RDB/AOF file trên cùng server = single point of failure.

Backup strategy production-grade cần:

```
┌─────────────────────────────────────────────────┐
│                Redis Instance                   │
│  dump.rdb + appendonly.aof                     │
└────────────┬───────────────────────────────────┘
             │
             ├─→ Local backup (rdb-backup/ container)
             │
             ├─→ Offsite S3/GCS (s3://bucket/redis-backups/)
             │
             └─→ Cross-region replica (Redis replication)
```

**Minimum**: Daily RDB backup to S3 + AOF to S3 + cross-region replica.

**Test restore monthly**: Backup không test = không có backup.

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1** — `INFO persistence` fields:

```
rdb_bgsave_in_progress:0         → No BGSAVE running
rdb_changes_since_last_save:0    → No changes since last save (fresh instance)
rdb_last_save_time:...           → Unix timestamp of last snapshot
aof_enabled:0                    → AOF disabled (default)
aof_delayed_fsync:0              → N/A (AOF disabled)
latest_fork_usec:0               → Never forked (fresh instance)
```

**1.2** — Default config:
- `save`: `"3600 1 300 100 60 10000"` — multi-directive: first match wins
- `appendonly`: `"no"` — default is off (RDB only)
- `appendfsync`: `"everysec"` — default fsync policy
- `dir`: `"/data"` — default working directory

**1.3** — Fork duration với small dataset (~10-20MB): 50-200ms. Nếu > 1s → alert.

**1.4** — `DEBUG RELOAD` là blocking, chỉ chạy trong maintenance window.

### Hands-on Lab Solutions

**Step 1** — Pipeline write throughput: ~15-50K ops/sec với pipeline batch 1000. 100K keys = 2-7 giây.

**Step 2** — Fork duration: tăng theo dataset size. Với ~20MB dataset, fork ~50-200ms. Với 10GB dataset, fork ~200-800ms.

**Step 3** — `kill -9` = SIGKILL, không có cleanup. Tương đương power loss. Khác với `redis-cli SHUTDOWN` (graceful, flush buffers, rewrite AOF).

**Step 4** — Restart times:
- RDB: ~1-5s (binary load)
- AOF: ~10-30s (replay ~100K commands)
- Hybrid: ~1-8s (RDB load fast + small AOF tail)

**Step 5** — Data loss:
- RDB: Mất changes giữa last save và crash. Với `save "300 1"` và crash sau 1-2 phút → mất vài trăm đến vài nghìn keys
- AOF: Mất tối đa 1 giây commands (~2-10 keys với write rate 100K/sec)
- Hybrid: Mất ~1 giây (AOF tail) + có RDB snapshot nhanh

**Step 6** — File size: AOF > RDB (RESP verbosity). Ratio ~2-3x.

### Challenge Solutions

**Scenario A (API Cache)**:

```txt
save "3600 1"
appendonly no
```

→ Đúng: 1 giờ data loss acceptable, no AOF overhead.
→ Monitoring: `rdb_changes_since_last_save`, `latest_fork_usec`
→ Caveat: COW với 100GB dataset → cần 110GB+ instance, monitor OOM

**Scenario B (Session Store)**:

```txt
save 3600 1 300 100 60 10000
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
```

→ Đúng: Hybrid = fast restart + durability. `everysec` = 1s loss acceptable.
→ Monitoring: `aof_delayed_fsync` (nếu > 0 = disk slow)
→ Caveat: Restart SLA 30s với 10GB → hybrid help nhưng vẫn cần tinh chỉnh

**Scenario C (Idempotency)**:

```txt
save 900 1
appendonly yes
appendfsync always
aof-use-rdb-preamble yes
```

→ Đúng: Maximum durability. PostgreSQL unique constraint = true idempotency.
→ **Hard problem**: Redis không phải durable store thực sự. Nếu bạn cần 100% guarantee cho financial transaction → dùng Redis chỉ cho coordination, PostgreSQL cho storage.

### Reflection Solutions

**Question 1**: Persistence off đúng khi data có thể rebuild nhanh và cold start không gây cascade failure. Sai khi session store hoặc bất kỳ user-generated state nào.

**Question 2**: Hybrid không tốt khi dataset nhỏ (overhead not justified), disk space constrained, hoặc write rate cực cao (AOF tail grows too fast).

**Question 3**: Không thể chỉ dựa vào RDB/AOF file. Cần: offsite backup + cross-region replica + tested restore procedure. GitLab 2017 incident = 5/5 backup mechanism đều thất bại.
