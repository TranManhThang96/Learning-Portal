# Day 10: Capacity Planning Basics — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: Go (`github.com/redis/go-redis/v9`)
**Docker images**: redis:7-alpine

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Inspect Current Capacity State

```bash
redis-cli INFO memory | grep -E 'used_memory|maxmemory|mem_fragmentation'
redis-cli INFO clients | grep -E 'connected_clients|maxclients|rejected_connections'
redis-cli INFO stats | grep -E 'instantaneous_ops_per_sec|total_commands'
redis-cli CONFIG GET maxmemory
```

**Expected output** (fresh Redis):

```
used_memory: 857056
maxmemory: 0
mem_fragmentation_ratio: 1.22
connected_clients: 1
maxclients: 10018
rejected_connections: 0
instantaneous_ops_per_sec: 0
total_commands_processed: 7
```

**Interpret**: `maxmemory: 0` = unlimited (no eviction). `mem_fragmentation_ratio: 1.22` = 22% fragmentation — normal for fresh instance.

### 1.2. Check Replication Backlog

```bash
redis-cli INFO replication | grep -E 'repl_backlog|connected_slaves'
redis-cli CONFIG GET repl-backlog-size
```

**Expected output**:

```
repl_backlog_active: 0          # No replica connected
repl_backlog_size: 1048576      # 1MB default
repl_backlog_histlen: 0
connected_slaves: 0
```

**Interpret**: Backlog = 1MB. At 100K ops/sec × 100B avg command = 10MB/s → backlog exhausted in 0.1s. Must increase `repl-backlog-size` for production.

### 1.3. MEMORY USAGE — Per-record Sampling

```bash
# Write a few test keys
redis-cli SET warmup:key1 "value1"
redis-cli SET warmup:key2 "this is a longer value with more data"
redis-cli HSET warmup:hash1 field1 val1 field2 val2

# Measure memory
redis-cli MEMORY USAGE warmup:key1
redis-cli MEMORY USAGE warmup:key2
redis-cli MEMORY USAGE warmup:hash1
```

**Expected output** (approximate):

```
(integer) 56    # warmup:key1 "value1" — small string
(integer) 120   # warmup:key2 "this is a longer..." — medium string
(integer) 312   # warmup:hash1 — hash with 2 fields
```

**Interpret**: MEMORY USAGE = key name + robj + SDS + value overhead. Hash có overhead dictEntry (hashtable encoding for 2 fields).

### 1.4. Memory Overhead Visualization

```bash
# Check encoding. DEBUG OBJECT cần enable-debug-command yes nên không dùng trong lab mặc định.
redis-cli OBJECT ENCODING warmup:key1
redis-cli OBJECT ENCODING warmup:key2
redis-cli OBJECT ENCODING warmup:hash1
```

**Expected output**:

```
"embstr"
"raw"
"listpack"
```

**Interpret**: String ngắn thường là `embstr`, string dài hơn là `raw`, Hash nhỏ thường là `listpack`. Nếu value là chuỗi số nguyên như `"123"`, Redis có thể dùng `int` encoding.

### 1.5. Connection Count

```bash
redis-cli CLIENT LIST | wc -l
redis-cli CONFIG GET timeout
redis-cli CONFIG GET maxclients
```

**Expected output**:

```
1                              # Only the redis-cli connection
timeout: 0                    # 0 = no timeout (dangerous in prod!)
maxclients: 10018
```

**Interpret**: `timeout: 0` = connections never expire. In production, set `timeout 300` (5 minutes idle). `maxclients: 10018` = default. Realistic production needs more (see worksheet).

### 1.6. Calculate Per-record Memory Manually

Using the numbers from warm-up:

```
warmup:key1:
  MEMORY USAGE = 56 bytes
  Key: "warmup:key1" = 12 bytes
  robj: 16 bytes
  Value SDS: 6 bytes + overhead
  Total: ~56 bytes ✓

Calculation formula check:
  bytes = key_len + 27 + value_len
  56 = 12 + 27 + 6 + SDS_header(1) + SDS_free(10) ~ approximate
```

---

## 2. Hands-on Lab (60-70 phút)

**Goal**: Viết tool sampling-based memory estimator bằng Go. Tool sẽ:
1. SCAN to estimate total key count
2. Random sample N keys, call MEMORY USAGE trên mỗi
3. Extrapolate cho total dataset
4. Calculate headroom
5. Print capacity report

### Setup: Docker Compose

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis-capacity:
    image: redis:7-alpine
    container_name: redis-capacity
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-with-data:
    image: redis:7-alpine
    container_name: redis-with-data
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

volumes:
  redis-capacity-data:
```

### Go Starter Code

**File**: `cmd/estimator/main.go`

```go
package main

import (
    "context"
    "fmt"
    "log"
    "math"
    "strconv"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

// --- Config ---
const (
    redisAddr        = "localhost:6379"
    sampleSize       = 500      // Statistical minimum: 96 for ±10% at 95% CI
    headroomPercent  = 0.40     // 40% memory headroom
)

// --- Types ---
type CapacityReport struct {
    TotalKeys        int64
    SampleKeys       int
    AvgBytesPerKey   float64
    EstimatedGB      float64
    WithHeadroomGB   float64
    MinSampleSize    int
    Confidence95Pct  float64
    ErrorMarginPct   float64
}

func main() {
    ctx := context.Background()

    rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
    defer rdb.Close()

    // Verify connection
    if err := rdb.Ping(ctx).Err(); err != nil {
        log.Fatalf("Cannot connect to Redis at %s: %v", redisAddr, err)
    }

    fmt.Println("=== Capacity Planning Estimator ===")
    fmt.Println()

    // Step 1: Count total keys
    fmt.Println("Step 1: Counting keys...")
    totalKeys, err := countKeys(ctx, rdb, "*")
    if err != nil {
        log.Fatalf("countKeys: %v", err)
    }
    fmt.Printf("  Total keys: %d\n", totalKeys)
    if totalKeys == 0 {
        fmt.Println("  No keys found. Populating test data...")
        if err := populateTestData(ctx, rdb, 100_000); err != nil {
            log.Fatalf("populateTestData: %v", err)
        }
        totalKeys, _ = countKeys(ctx, rdb, "*")
        fmt.Printf("  After populate: %d keys\n", totalKeys)
    }

    // Step 2: Sample MEMORY USAGE
    fmt.Println("\nStep 2: Sampling memory usage...")
    report, err := sampleMemory(ctx, rdb, "*", sampleSize)
    if err != nil {
        log.Fatalf("sampleMemory: %v", err)
    }

    fmt.Printf("\n=== Memory Estimate ===\n")
    fmt.Printf("  Total keys:       %d\n", report.TotalKeys)
    fmt.Printf("  Sample size:      %d\n", report.SampleKeys)
    fmt.Printf("  Avg bytes/key:    %.2f B\n", report.AvgBytesPerKey)
    fmt.Printf("  Estimated memory: %.2f GB\n", report.EstimatedGB)
    fmt.Printf("  + 40%% headroom:   %.2f GB\n", report.WithHeadroomGB)
    recommended := math.Ceil(report.WithHeadroomGB/10) * 10
    if recommended < 1 {
        recommended = 1
    }
    fmt.Printf("  Recommended:       %.0f GB instance\n", recommended)

    if report.SampleKeys < report.MinSampleSize {
        fmt.Printf("\n⚠️  Warning: sample size %d < recommended %d\n",
            report.SampleKeys, report.MinSampleSize)
        fmt.Println("  Increase sample size for better accuracy.")
    }

    fmt.Printf("\n  95%% CI: ±%.1f%%\n", report.ErrorMarginPct)
    fmt.Printf("  Range: %.2f – %.2f GB\n",
        report.EstimatedGB*(1-report.ErrorMarginPct/100),
        report.EstimatedGB*(1+report.ErrorMarginPct/100))

    // Step 3: Current Redis capacity
    fmt.Println("\n=== Current Redis Capacity ===")
    printRedisCapacity(ctx, rdb)

    // Step 4: Capacity recommendation
    fmt.Println("\n=== Recommendation ===")
    printRecommendation(report)
}

// --- Functions ---

func countKeys(ctx context.Context, rdb *redis.Client, pattern string) (int64, error) {
    var count int64
    iter := rdb.Scan(ctx, 0, pattern, 1000).Iterator()
    for iter.Next(ctx) {
        count++
    }
    return count, iter.Err()
}

func sampleMemory(ctx context.Context, rdb *redis.Client, pattern string, sampleSize int) (*CapacityReport, error) {
    var (
        totalBytes    int64
        sampledCount  int
        totalKeys     int64
        sampleResults []int64
    )

    // Count total keys first
    iterCount := rdb.Scan(ctx, 0, pattern, 1000).Iterator()
    for iterCount.Next(ctx) {
        totalKeys++
    }
    if err := iterCount.Err(); err != nil {
        return nil, err
    }

    if totalKeys == 0 {
        return &CapacityReport{TotalKeys: 0}, nil
    }

    // SCAN for sampling (not RANDOMKEY, but SCAN with count hint)
    // Note: This is approximate random sampling
    iter := rdb.Scan(ctx, 0, pattern, int64(sampleSize)).Iterator()
    for iter.Next(ctx) {
        key := iter.Val()
        bytes, err := rdb.MemoryUsage(ctx, key).Result()
        if err != nil {
            // Key expired or deleted between SCAN and MEMORY USAGE
            continue
        }
        totalBytes += bytes
        sampledCount++
        sampleResults = append(sampleResults, bytes)
        if sampledCount >= sampleSize {
            break
        }
    }
    if err := iter.Err(); err != nil {
        return nil, err
    }

    if sampledCount == 0 {
        return nil, fmt.Errorf("no keys sampled successfully")
    }

    avgBytes := float64(totalBytes) / float64(sampledCount)
    estimatedTotal := avgBytes * float64(totalKeys)

    // Statistical confidence
    var mean, stddev, ci95 float64
    if len(sampleResults) >= 2 {
        sum := float64(0)
        for _, v := range sampleResults {
            sum += float64(v)
        }
        mean = sum / float64(len(sampleResults))
        var ssq float64
        for _, v := range sampleResults {
            d := float64(v) - mean
            ssq += d * d
        }
        stddev = math.Sqrt(ssq / float64(len(sampleResults)-1))
        ci95 = 1.96 * stddev / math.Sqrt(float64(len(sampleResults)))
    }

    estimatedGB := estimatedTotal / 1_073_741_824
    errorMarginPct := 0.0
    if estimatedGB > 0 {
        errorMarginPct = (ci95 / estimatedTotal) * 100
    }

    // Minimum sample size for 95% CI ±10% error (for high variance population)
    // n = (z² × σ²) / E² = (1.96² × σ²) / (0.1 × μ)²
    minSample := 96 // simplified: for most Redis key distributions, 96-500 samples sufficient
    if stddev/mean > 0.5 {
        minSample = 500 // high variance: need more samples
    }

    return &CapacityReport{
        TotalKeys:       totalKeys,
        SampleKeys:      sampledCount,
        AvgBytesPerKey:  avgBytes,
        EstimatedGB:     estimatedGB,
        WithHeadroomGB:  estimatedGB * (1 + headroomPercent),
        MinSampleSize:   minSample,
        Confidence95Pct: 95,
        ErrorMarginPct:  errorMarginPct,
    }, nil
}

func populateTestData(ctx context.Context, rdb *redis.Client, count int) error {
    pipe := rdb.Pipeline()
    for i := 0; i < count; i++ {
        key := fmt.Sprintf("test:item:%08d", i)
        val := fmt.Sprintf(`{"id":%d,"name":"product-%d","price":%d,"desc":"Lorem ipsum dolor sit amet"}`, i, i, i%1000)
        pipe.Set(ctx, key, val, 24*time.Hour)
        if i%1000 == 0 {
            _, err := pipe.Exec(ctx)
            if err != nil {
                return fmt.Errorf("pipeline at %d: %w", i, err)
            }
            pipe = rdb.Pipeline()
        }
    }
    _, err := pipe.Exec(ctx)
    return err
}

func printRedisCapacity(ctx context.Context, rdb *redis.Client) {
    info, err := rdb.Do(ctx, "INFO", "memory").Text()
    if err != nil {
        log.Printf("INFO memory: %v", err)
        return
    }

    var usedMem, maxMem int64
    var fragRatio float64
    for _, line := range strings.Split(info, "\n") {
        line = strings.TrimSpace(line)
        if strings.HasPrefix(line, "used_memory:") {
            usedMem, _ = strconv.ParseInt(strings.TrimPrefix(line, "used_memory:"), 10, 64)
        }
        if strings.HasPrefix(line, "maxmemory:") {
            maxMem, _ = strconv.ParseInt(strings.TrimPrefix(line, "maxmemory:"), 10, 64)
        }
        if strings.HasPrefix(line, "mem_fragmentation_ratio:") {
            fragRatio, _ = strconv.ParseFloat(strings.TrimPrefix(line, "mem_fragmentation_ratio:"), 64)
        }
    }

    usedGB := float64(usedMem) / 1_073_741_824
    maxGB := float64(maxMem) / 1_073_741_824
    usedPct := 0.0
    if maxMem > 0 {
        usedPct = float64(usedMem) / float64(maxMem) * 100
    }

    status := "OK"
    if usedPct > 70 {
        status = "WARNING"
    }
    if usedPct > 85 {
        status = "CRITICAL"
    }

    fmt.Printf("  Used memory:    %.2f GB / %.2f GB (%.1f%%) [%s]\n",
        usedGB, maxGB, usedPct, status)
    fmt.Printf("  Frag ratio:     %.2f (⚠️ if >1.5)\n", fragRatio)

    // Clients
    clientsInfo, _ := rdb.Do(ctx, "INFO", "clients").Text()
    var connectedClients, maxClients, rejectedConns int64
    for _, line := range strings.Split(clientsInfo, "\n") {
        line = strings.TrimSpace(line)
        if strings.HasPrefix(line, "connected_clients:") {
            connectedClients, _ = strconv.ParseInt(strings.TrimPrefix(line, "connected_clients:"), 10, 64)
        }
        if strings.HasPrefix(line, "maxclients:") {
            maxClients, _ = strconv.ParseInt(strings.TrimPrefix(line, "maxclients:"), 10, 64)
        }
        if strings.HasPrefix(line, "rejected_connections:") {
            rejectedConns, _ = strconv.ParseInt(strings.TrimPrefix(line, "rejected_connections:"), 10, 64)
        }
    }

    connPct := 0.0
    if maxClients > 0 {
        connPct = float64(connectedClients) / float64(maxClients) * 100
    }
    fmt.Printf("  Connections:    %d / %d (%.1f%%)\n", connectedClients, maxClients, connPct)
    if rejectedConns > 0 {
        fmt.Printf("  ⚠️  Rejected connections: %d (maxclients hit!)\n", rejectedConns)
    }

    // Ops/sec
    statsInfo, _ := rdb.Do(ctx, "INFO", "stats").Text()
    for _, line := range strings.Split(statsInfo, "\n") {
        line = strings.TrimSpace(line)
        if strings.HasPrefix(line, "instantaneous_ops_per_sec:") {
            ops, _ := strconv.ParseInt(strings.TrimPrefix(line, "instantaneous_ops_per_sec:"), 10, 64)
            fmt.Printf("  Ops/sec:       %d\n", ops)
        }
    }
}

func printRecommendation(report *CapacityReport) {
    // Recommend instance size
    recommended := math.Ceil(report.WithHeadroomGB/10) * 10
    if recommended < 8 {
        recommended = 8
    }

    fmt.Printf("  Based on %d keys (%.2f GB estimated):\n",
        report.TotalKeys, report.EstimatedGB)
    fmt.Printf("  Recommended Redis instance: %.0f GB RAM\n", recommended)

    // Memory utilization
    utilPct := report.EstimatedGB / report.WithHeadroomGB * 100
    fmt.Printf("  Memory utilization (with headroom): %.0f%%\n", utilPct)

    // Connection memory estimate
    // Assume 1000 connections (typical web service)
    connOverhead := float64(1000) * 17 * 1024 / 1_073_741_824
    fmt.Printf("  Connection overhead (1K connections): %.2f GB\n", connOverhead)

    // COW estimate
    cowOverhead := report.EstimatedGB * 0.20
    fmt.Printf("  COW headroom (BGSAVE): ~%.2f GB\n", cowOverhead)

    // Final recommendation
    totalNeeded := report.WithHeadroomGB + connOverhead + cowOverhead
    finalInstance := math.Ceil(totalNeeded/10) * 10
    fmt.Printf("\n  === FINAL RECOMMENDATION ===\n")
    fmt.Printf("  Instance: %.0f GB RAM minimum\n", finalInstance)
    fmt.Printf("  With ops/sec headroom: consider %.0f GB for growth\n", finalInstance*1.3)
}
```

### Expected Output

```
=== Capacity Planning Estimator ===

Step 1: Counting keys...
  Total keys: 0
  No keys found. Populating test data...
  After populate: 100000 keys

Step 2: Sampling memory usage...

=== Memory Estimate ===
  Total keys:       100000
  Sample size:      500
  Avg bytes/key:    112.34 B
  Estimated memory: 0.01 GB
  + 40% headroom:   0.02 GB
  Recommended:       1 GB instance

  95% CI: ±8.3%
  Range: 0.01 – 0.02 GB

=== Current Redis Capacity ===
  Used memory:    0.02 GB / 0.25 GB (8.0%) [OK]
  Frag ratio:     1.12 (⚠️ if >1.5)
  Connections:    1 / 10018 (0.0%)
  Ops/sec:       0

=== Recommendation ===
  Based on 100000 keys (0.01 GB estimated):
  Recommended Redis instance: 8 GB RAM
  Memory utilization (with headroom): 71%
  Connection overhead (1K connections): 0.02 GB
  COW headroom (BGSAVE): ~0.00 GB

  === FINAL RECOMMENDATION ===
  Instance: 8 GB RAM minimum
  With ops/sec headroom: consider 10 GB for growth
```

**Note**: 100K keys nhỏ chỉ tạo dataset vài chục MB. Nếu muốn thấy cảnh báo capacity, tăng `populateTestData` lên 5-10 triệu keys hoặc giảm `--maxmemory` xuống 32-64MB.

### Hint: Debugging Common Issues

**Issue**: `MEMORY USAGE` returns error for some keys.
```
Reason: Key expired between SCAN and MEMORY USAGE.
Fix: Add error check and continue (skip expired keys).
```

**Issue**: `sampleResults` has very high variance.
```
Reason: Mixed data types (string vs hash vs list).
Fix: Filter by pattern or compute separate estimates per key prefix.
       e.g., run sampleMemory(ctx, rdb, "cache:*", 500)
             run sampleMemory(ctx, rdb, "session:*", 500)
```

**Issue**: SCAN hangs on large keyspace.
```
Fix: Use COUNT hint: rdb.Scan(ctx, 0, pattern, 10000).Iterator()
     For 100M+ keys, consider using --scan or BGSAVE + RDB analysis.
```

---

## 3. Challenge Exercise (30-40 phút)

### Capacity Worksheet — E-commerce Cache System

**Scenario**: Bạn thiết kế Redis cache cho hệ thống e-commerce:

```
Requirements:
  - Peak ops/sec:        100,000
  - Cached objects:     50,000,000
  - Avg object size:     512 bytes
  - Read/write ratio:    80% read / 20% write
  - TTL:                 30% objects have 24h TTL, 70% have 7 days
  - Latency target:      p99 < 5ms
  - HA requirement:      Master crash → zero data loss window < 30s

Infrastructure:
  - Cloud: AWS (ElastiCache) or GCP Memorystore
  - Network: 1 Gbps NIC per instance
```

### Part A: Memory Calculation

```
Given:
  Keys:       50M
  Avg value:  512 bytes
  Avg key:    24 bytes

Step 1: Per-record memory
  bytes_per_record = key_len + 27 + value_bytes + encoding_overhead
  encoding_overhead for string: 0

  bytes_per_record = 24 + 27 + 512 = 563 bytes

Step 2: Dataset memory
  logical_dataset = 50M × 563B = 28.15 GB

Step 3: With fragmentation (jemalloc × 1.15)
  dataset_with_frag = 28.15 × 1.15 = 32.37 GB

Step 4: Monthly growth
  growth assumption: +500K objects/month × 563B = +0.28 GB/month
  6-month growth: +1.68 GB

Step 5: COW headroom (BGSAVE)
  Write ops: 100K × 0.20 = 20K ops/sec
  Avg write size: 563 bytes
  BGSAVE duration: ~60s (estimate for 30GB dataset)
  COW = 20K × 563 × 60 = 676 MB ≈ 0.66 GB

Step 6: Connection memory
  Expected connections: 2000 (10 services × 10 pods × 20 goroutines)
  conn_memory = 2000 × 17KB = 34 MB

Step 7: Total
  memory_needed = 32.37 + 1.68 + 0.66 + 0.03 = 34.74 GB
  headroom = (38 - 34.74) / 38 = 8.6%  ← TIGHT!

  → Recommended instance: 64 GB
  → Utilization: 34.74 / 64 = 54%  ✓
```

### Part B: Throughput Calculation

```
Benchmark ceiling (assume): 200K ops/sec (1KB payload, local)

Production target = 200K × 0.60 = 120K ops/sec
Peak target: 100K ops/sec

Payload bandwidth check:
  Read bandwidth:  80K × 536B = 42.9 MB/s = 343 Mbps
  Write bandwidth: 20K × 563B = 11.3 MB/s = 90 Mbps
  Total: 433 Mbps → 1 Gbps NIC: 43% utilized ✓

With replication (1 replica):
  Replication bandwidth = write bandwidth × 1 = 90 Mbps
  Total: 523 Mbps → 1 Gbps NIC: 52% utilized ✓

Ops/sec headroom:
  120K target - 100K peak = 20K headroom = 20% margin
  → Need more headroom OR size for 120K ops/sec target
```

### Part C: Failover Capacity

```
Normal: Master 20K writes/sec
        Replica: 80K reads/sec

After master crash, replica promoted:
  New master must handle: 20K writes + 80K reads = 100K ops/sec

Replica capacity must be: 100K ops/sec (not 80K!)
→ Replica should be same size as master for HA

With 2 replicas:
  Master: 20K writes
  Replica1: 80K reads (same size as master)
  Replica2: 0 reads (standby)

After master crash, replica1 promoted:
  replica1: 20K writes + 80K reads = 100K ops/sec (full capacity)
  replica2: still serving as replica
  → Failover safe ✓
```

### Part D: Topology Decision

```
Decision: Sentinel (3 nodes) + 2 replicas

Rationale:
  - 100K ops/sec: within Sentinel range (< 150K per instance)
  - Memory 35GB: within single instance range (< 64GB)
  - Multi-key operations needed (e-commerce: MGET product list)
  - Cluster would add complexity without benefit

Node count:
  - 1 master (64GB instance)
  - 2 replicas (64GB each, same size for HA)
  - 3 Sentinels (small, 2GB each)

Cost estimate (AWS ElastiCache):
  - 3 × cache.r6g.xlarge (16GB): ~$0.936/hr = $675/month
  - 2 × cache.r6g.2xlarge (32GB): ~$1.872/hr = $1,350/month
  - 3 × Sentinel (t3.micro): ~$0.03/hr = $22/month
  Total: ~$2,000/month
```

### Part E: Capacity Worksheet (Fill-in)

```
┌─────────────────────────────────────────────────────────┐
│           CAPACITY PLANNING WORKSHEET                   │
├─────────────────────────┬───────────────────────────────┤
│ Input                   │ Value                         │
├─────────────────────────┼───────────────────────────────┤
│ peak_ops/sec            │ 100,000                       │
│ avg_payload             │ 536 bytes                     │
│ read/write              │ 80/20                         │
│ total_keys              │ 50,000,000                    │
│ replica_count           │ 2                             │
├─────────────────────────┼───────────────────────────────┤
│ Memory                  │                               │
│ per_record_bytes        │ 563                           │
│ logical_dataset         │ 28.15 GB                      │
│ + fragmentation (15%)  │ 4.22 GB                       │
│ + growth (6mo × 0.28)  │ 1.68 GB                       │
│ + COW headroom          │ 0.66 GB                       │
│ + conn_overhead         │ 0.03 GB                       │
│ = TOTAL NEEDED          │ 34.74 GB                      │
│ utilization_pct         │ 54% (target ≤70%) → OK        │
│ recommended_instance    │ 64 GB RAM                     │
├─────────────────────────┼───────────────────────────────┤
│ Throughput              │                               │
│ benchmark_ceiling       │ 200K ops/sec                  │
│ production_target       │ 120K ops/sec (60%)            │
│ peak_vs_target          │ 100K < 120K ✓                │
├─────────────────────────┼───────────────────────────────┤
│ Bandwidth               │                               │
│ client_bandwidth        │ 433 Mbps                      │
│ replication_bandwidth   │ 90 Mbps                       │
│ total_bandwidth         │ 523 Mbps                      │
│ NIC_1Gbps_utilization   │ 52% → OK (< 70%) ✓           │
├─────────────────────────┼───────────────────────────────┤
│ Failover                │                               │
│ master_failover_load    │ 100K ops/sec                  │
│ replica_capacity        │ must be ≥ 100K ops/sec        │
│ safe?                   │ NO → size replicas = master   │
├─────────────────────────┼───────────────────────────────┤
│ Persistence              │                               │
│ RDB_size                │ ~32 GB × 0.7 = 22 GB         │
│ AOF_size (no rewrite)   │ ~32 GB × 5 = 160 GB ← DANGER │
│ recommended_disk        │ 500 GB NVMe SSD               │
└─────────────────────────┴───────────────────────────────┘
```

---

## 4. Reflection Questions

### Question 1: Tại sao capacity planning cần phải là bài toán số học, không phải "feel"?

Capacity planning là bài toán số học vì:
- Memory headroom: 30GB dataset + COW 1.2GB + connections 0.85GB = 32.05GB — nếu instance 32GB → OOM. Không có "feel" nào cover được.
- Ops/sec headroom: benchmark 200K → production 120K. Nếu plan 200K → fail at peak.
- Failover: replica size = master × 0.5 → promote = 2× overload → cascade.

**Reflection**: Bạn có bao giờ "feel" rằng hệ thống sẽ ổn, rồi incident xảy ra vì thiếu headroom không? Kinh nghiệm đó dạy gì?

### Question 2: Connection memory thường bị quên trong capacity planning. Tại sao nó nguy hiểm?

Connection memory nằm **ngoài dataset budget**. `maxmemory` không phải hard cap cho toàn bộ RSS của process; client buffers, replication/AOF buffers và fragmentation vẫn cần RAM headroom riêng. Khi connections tăng đột biến:
- `maxmemory` không trigger eviction
- Process-level OOM → Redis killed by kernel → cascade failure

**Reflection**: Trong hệ thống của bạn, connection count có được monitor không? Có alert khi connections > 70% maxclients không?

### Question 3: Scale up vs scale out — bạn sẽ chọn gì cho 100K ops/sec, 50GB dataset? Tại sao?

Một mình scale up có thể đủ cho 100K ops/sec, 50GB (Sentinel + big instance). Nhưng:
- Single instance limit: ~150K ops/sec, 64-128GB
- Hot key risk: nếu có hot key, single instance không thể isolate
- Blast radius: single point of failure lớn

Scale out (Cluster) thêm complexity nhưng:
- Hot key isolation: có thể put hot keys trên dedicated shard
- Blast radius nhỏ: 1 shard down = 1/N data affected
- Scale predictability: add shards = linear scale

**Reflection**: Trong use case thực tế của bạn, hot key có phải là concern không? Nếu có → Cluster. Nếu không → Sentinel + big instance.

### Question 4: T-shirt sizing có phù hợp cho mọi trường hợp không? Khi nào nó fail?

T-shirt sizing fail khi:
- Workload có hot key → single shard bottleneck, cluster needed
- Payload size cực lớn (100KB+) → bandwidth ceiling ngay cả với small ops/sec
- Write-heavy workload với AOF → disk I/O becomes bottleneck, không phải memory
- Multi-tenant system → mỗi tenant có different pattern, t-shirt sizing too coarse

**Reflection**: Trong hệ thống của bạn, metric nào là bottleneck đầu tiên — memory, ops/sec, bandwidth, hay disk I/O?

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1**: `maxmemory: 0` = unlimited. Default Redis không có eviction limit — production nên set `maxmemory` để prevent process-level OOM.

**1.2**: `repl_backlog_size: 1048576` = 1MB. At 100K ops/sec × 100B: 1MB / 10MB/s = 0.1s lag = instant backlog exhaustion. Production: `CONFIG SET repl-backlog-size 104857600` (100MB) for 30s lag tolerance.

**1.3**: MEMORY USAGE cho hash với 2 fields trả về ~312 bytes — cao hơn string vì hash dùng hashtable encoding (2 fields > threshold behavior varies).

**1.4**: `OBJECT ENCODING` thường trả `embstr` cho string ngắn, `raw` cho string dài hơn, `listpack` cho Hash nhỏ. `int` chỉ xuất hiện khi value là chuỗi số nguyên như `"123"`.

**1.5**: `timeout: 0` = never expire. Prod: `CONFIG SET timeout 300`. Default `maxclients` = 10018. Realistic production với microservices: 50K+ connections → phải increase `ulimit -n` và `maxclients`.

**1.6**: Formula check: `key_len + 27 + value_len` ≈ MEMORY USAGE output. Lưu ý: MEMORY USAGE = actual memory (RSS) = logical size + fragmentation.

### Hands-on Lab Solutions

**Sampling approach**: SCAN với count hint không hoàn toàn random. Redis SCAN iterates through slot space. For truly random sampling: use `RANDOMKEY` between samples (slower but accurate).

**Statistical confidence**: Sample size 500 cho population 100K keys → ±8.3% error at 95% CI. Đủ accurate cho capacity planning (target ±20%).

**MEMORY USAGE accuracy**: `SAMPLES 0` (default) = full key traversal → accurate nhưng chậm. `SAMPLES 100` = statistical sample → faster, slightly less accurate.

**Connection overhead in report**: 1000 connections × 17KB = 17MB. Với 100K connections (microservices scale): 1.7GB. Đây là phần không nằm trong `maxmemory`.

### Challenge Solutions

**Part A**: Memory needed = 34.74GB → 64GB instance (54% utilization). Headroom 46% cho growth + COW. Thêm 6-month growth (+1.68GB) và COW (+0.66GB) vào calculation.

**Part B**: Bandwidth 523 Mbps < 1Gbps × 0.7 = 700 Mbps → OK. Benchmark ceiling 200K ops/sec → production target 120K ops/sec. Peak 100K < 120K nhưng chỉ còn 20% margin, thấp hơn mục tiêu 30-40% → cần benchmark lại với payload thật hoặc chọn instance/NIC mạnh hơn.

**Part C**: Failover scenario: replica must be sized for full master load (100K ops/sec), không phải replica's normal load (80K reads). Size replica = master × 1.0.

**Part D**: Sentinel topology với 2 replicas là đúng choice cho 100K ops/sec, 50GB. Cluster overkill (thêm complexity mà không benefit rõ ràng).

**Part E — Critical findings**:
1. Memory headroom chỉ 8.6% → FAIL → cần 64GB instance
2. Ops/sec headroom chỉ 20% → TIGHT → benchmark để confirm ceiling
3. Failover replica capacity insufficient → replicas phải same size as master
4. AOF size 160GB → DANGER → set AOF rewrite schedule và monitor disk

### Reflection Solutions

**Q1**: "Feel" capacity planning fail vì production workload thay đổi (viral content, traffic spike, data growth) — những thứ không "feel" được. Số học (headroom %) cho phép buffer cho changes.

**Q2**: Connection memory dangerous vì nó invisible trong `INFO memory` và không trigger `maxmemory` eviction. Chỉ visible trong `INFO clients` và system-level memory.

**Q3**: Với 100K ops/sec, 50GB: Sentinel + big instance đủ. Chọn Sentinel nếu multi-key operations critical (MGET product list). Chọn Cluster nếu hot key exists hoặc cost optimization needed.

**Q4**: Bottleneck detection thứ tự:
1. Ops/sec > benchmark × 0.6 → ops/sec bottleneck
2. Memory > maxmemory × 0.8 → memory bottleneck
3. Bandwidth > NIC × 0.7 → bandwidth bottleneck
4. Latency spike → slow command hoặc disk I/O (AOF)
