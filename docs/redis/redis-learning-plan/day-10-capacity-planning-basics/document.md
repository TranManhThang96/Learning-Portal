# Day 10: Capacity Planning Basics — Reference Document

## 1. Cheat Sheet: Capacity Planning Commands

### INFO Commands

```txt
-- Memory overview
INFO memory
-- Key fields:
--   used_memory               → allocator memory Redis đang dùng, không phải RSS
--   used_memory_peak         → peak memory since start
--   used_memory_dataset       → data only, no overhead
--   maxmemory                 → configured limit
--   mem_fragmentation_ratio   → RSS / used_memory (>1.5 = bad)
--   used_memory_rss           → RSS của process Redis theo OS
--   mem_total_replication_buffers → memory used by replication buffers

-- Client/connection overview
INFO clients
-- Key fields:
--   connected_clients         → current connections
--   blocked_clients           → waiting on BLPOP, etc.
--   cluster_connections        → cluster bus connections
--   maxclients                → OS limit

-- Ops/sec overview
INFO stats
-- Key fields:
--   instantaneous_ops_per_sec → current ops/sec
--   total_commands_processed → cumulative
--   rejected_connections      → connections rejected (maxclients hit)

-- Replication overview
INFO replication
-- Key fields:
--   role                      → master / replica
--   connected_slaves          → number of replicas
--   master_repl_offset        → replication position
--   repl_backlog_active       → backlog enabled?
--   repl_backlog_size         → backlog buffer size (bytes)
--   repl_backlog_first_byte_offset → oldest command in backlog
--   repl_backlog_histlen      → current backlog used (bytes)
```

### MEMORY USAGE Sampling

```txt
-- Per-key memory (accurate, includes all overhead)
MEMORY USAGE key [SAMPLES count]

-- Example: check 100-key sample for statistical estimate
-- Run in pipeline or script for performance

-- Object metadata
OBJECT ENCODING key
OBJECT FREQ key        -- access frequency (LFU mode)
DEBUG OBJECT key       -- cần enable-debug-command yes; không bật trong production
```

### CLIENT Commands

```txt
-- Current clients
CLIENT LIST
-- Key fields per client:
--   id, addr, fd, name, age, idle, flags, cmd
--   lib-name, lib-ver (client library)
--   obuf/ibuf (output/input buffer size)

-- Count connections
CLIENT LIST | wc -l

-- Kill by pattern
CLIENT KILL ADDR ip:port
CLIENT KILL ID client-id

-- Set timeout
CLIENT SETINFO connection-type server
CONFIG SET timeout 300        -- 5 min idle timeout
```

### Redis CLI Capacity Tools

```bash
# Find big keys by memory
redis-cli --bigkeys

# Find big keys by memory (not size)
redis-cli --memkeys

# Find hot keys (requires Redis 4.0+)
redis-cli --hotkeys

# Latency baseline
redis-cli --latency

# Latency history
redis-cli --latency-history

# Latency doctor
redis-cli --latency-doctor

# Scan keys with count hint
redis-cli --scan --pattern 'cache:*' | wc -l
```

---

## 2. Capacity Planning Worksheet Template

### Section A: Input Parameters

```
Workload Parameters:
  peak_ops/sec:           ________ ops/sec
  avg_payload_bytes:      ________ bytes
  read_write_ratio:       _____ / _____ (e.g., 80/20)
  total_keys:             ________ keys
  avg_value_bytes:        ________ bytes
  avg_key_len:            ________ bytes
  avg_ttl_seconds:        ________ seconds

Topology:
  replica_count:          ____
  topology_type:           [ ] Standalone  [ ] Sentinel  [ ] Cluster
  nodes_or_shards:        ____

Growth:
  monthly_growth_rate:    ________ GB/month
  planning_horizon_months: ____
```

### Section B: Memory Calculation

```
Per-record formula:
  bytes_per_record = key_len + 27 + value_bytes + encoding_overhead

  key_len:             ______ bytes
  value_bytes:         ______ bytes
  encoding_overhead:    ______ bytes  (0 for string, +5-20 for hash/listpack)
  bytes_per_record:    ______ bytes

Dataset memory:
  logical_dataset = total_keys × bytes_per_record = ______ GB
  fragmentation_x  = 1.10 – 1.25 (jemalloc + internal)
  dataset_with_frag = logical_dataset × fragmentation_x = ______ GB

COW headroom (BGSAVE):
  write_rate = peak_ops/sec × write_ratio = ______ ops/sec
  avg_write_bytes = ______ bytes
  bgsave_duration = ______ seconds  (measure with INFO persistence)
  cow_bytes = write_rate × avg_write_bytes × bgsave_duration
  cow_gb = cow_bytes / 1_073_741_824 = ______ GB

Growth projection:
  projected_memory = dataset_with_frag + (growth_rate × horizon) = ______ GB

Total memory needed:
  memory_needed = projected_memory + cow_gb + connection_overhead_gb
  connection_overhead_gb = expected_connections × 17KB / 1_073_741_824 = ______ GB

  memory_needed: ______ GB
  recommended_instance: ______ GB  (memory_needed × 1.4)
  utilization: ______% (memory_needed / recommended_instance)
```

### Section C: Throughput Calculation

```
Benchmark ceiling (from redis-benchmark):
  benchmark_ops/sec:      ______ ops/sec

Production target:
  target_ops/sec = benchmark_ops/sec × 0.60 = ______ ops/sec

Payload bandwidth:
  read_bandwidth_mbps  = (peak_ops/sec × read_ratio)  × avg_payload_bytes × 8 / 1_000_000
  write_bandwidth_mbps = (peak_ops/sec × write_ratio) × avg_payload_bytes × 8 / 1_000_000
  total_bandwidth_mbps  = read_bandwidth_mbps + write_bandwidth_mbps

  read_bandwidth:  ______ Mbps
  write_bandwidth: ______ Mbps
  total:           ______ Mbps

  NIC check: total < NIC_speed × 0.70 = ______ Mbps OK?  [ ] Yes  [ ] No

Ops/sec capacity check:
  target_ops/sec = ______ ops/sec
  headroom_check = benchmark_ops/sec × 0.60 = ______ ops/sec
  margin: ______% (headroom_check - target_ops/sec) / target_ops/sec
  OK if margin > 30%?  [ ] Yes  [ ] No
```

### Section D: Connection Calculation

```
Expected connections:
  services:               ______
  pods_per_service:       ______
  threads_per_instance:   ______
  connections_per_thread: ______

  total_connections = services × pods × threads × connections = ______

Connection memory:
  conn_memory_gb = total_connections × 17KB / 1_073_741_824 = ______ GB

maxclients check:
  expected + headroom = total_connections × 1.30 = ______
  OS limit = ulimit - n / 3 = ______
  OK? [ ] Yes  [ ] No

  Recommended: CONFIG SET maxclients expected_with_headroom
```

### Section E: Failover Capacity

```
Normal state:
  Master ops:  peak_ops/sec × write_ratio = ______ ops/sec
  Replica ops: peak_ops/sec × read_ratio  = ______ ops/sec

After failover (1 replica promoted):
  promoted_replica_ops = master_ops + replica_ops = ______ ops/sec
  replica_capacity_check = replica_stated_capacity = ______ ops/sec
  overload_pct = (promoted_replica_ops / replica_capacity) × 100 = ______%

  If overload_pct > 100%: [ ] FAILOVER NOT SAFE
    → Solution: Size replica = master_ops × 1.2 minimum
    → Or: Use 2 replicas for read capacity during failover

With 2 replicas:
  Replica1 promoted: master_ops = ______ ops/sec
  Replica2 (still replica): replica_ops = ______ ops/sec
  Total after failover: ______ ops/sec
```

### Section F: Disk Sizing

```
RDB size:  dataset_with_frag × 0.6 × 1.2 = ______ GB
AOF size:  dataset_with_frag × AOF_multiplier × rewrite_progress
           (AOF_multiplier = 3–10×, rewrite_progress = 0.2–0.8)

  current_AOF_multiplier: ______×
  current_AOF_size: ______ GB
  AOF_headroom:  AOF_size × 1.5 = ______ GB

Backup requirement:
  RDB backups to keep:     ____
  Disk needed = RDB × backups + AOF_headroom + OS_20pct = ______ GB

  Recommended disk: ______ GB NVMe SSD
```

### Section G: Summary

```
  Recommended Instance:  ______ GB RAM
  Recommended vCPU:       ______ cores
  Ops/sec Sustainable:   ______ ops/sec (headroom: ______%)
  Ops/sec Failover Safe: ______ ops/sec
  Memory Headroom:       ______%
  NIC Check:             ______ Mbps / ______ Mbps (OK/WARNING)
  Connection Headroom:   ______%
  Disk:                  ______ GB SSD
  Topology:              [ ] Standalone  [ ] Sentinel  [ ] Cluster
                          Nodes: ______, Replicas: ______
```

---

## 3. Per-record Memory Reference Table

### String

| Encoding | Value Range | Memory Formula | Example (key=20B, val=100B) |
|----------|------------|-----------------|-----------------------------|
| int | 0 to 2^63-1 | 16B robj + 8B int | 24B total |
| raw | ≤ 44 bytes | 16B robj + (len+2)B SDS | 138B |
| raw | > 44 bytes | 16B robj + (len+9)B SDS | 145B |

### Hash (listpack)

| Fields | Value Size | Encoding | Bytes/field | Example (100 fields) |
|--------|-----------|----------|-------------|---------------------|
| ≤ 128 | ≤ 64B | listpack | ~1.5–2B | ~150–200B |
| > 128 | any | hashtable | ~24–32B | ~2.4–3.2KB |

### List (quicklist)

| Node size | Encoding | Memory overhead |
|-----------|----------|---------------|
| 8KB node | listpack | ~56B overhead per node |
| 4KB node | listpack | ~56B overhead per node |

### Set

| Encoding | Condition | Memory |
|----------|----------|--------|
| intset | all int, ≤ 512 elements | 4B header + 2/4/8B per element |
| listpack (7.2+) | strings, ≤ 128 | ~2B per element |
| hashtable | otherwise | ~24B per element + dictEntry |

### Sorted Set

| Encoding | Condition | Memory |
|----------|----------|--------|
| listpack | ≤ 128 entries, value ≤ 64B | ~1.5B per entry + 8B score |
| skiplist | otherwise | ~32B + SDS + dictEntry |

---

## 4. Bandwidth Calculator Template

```
Input:
  ops/sec:           [  ]
  avg_payload_bytes: [  ]
  read_ratio:        [  ]
  replication_factor:[  ]
  NIC_speed:         [  ] Gbps

Calculations:
  client_read_mbps   = ops/sec × read_ratio × payload × 8 / 1_000_000
  client_write_mbps  = ops/sec × (1-read_ratio) × payload × 8 / 1_000_000
  replication_mbps   = ops/sec × (1-read_ratio) × replication_factor × payload × 8 / 1_000_000
  total_mbps         = client_read + client_write + replication

  total_pct = total_mbps / (NIC_speed × 1000) × 100

Decision:
  If total_pct > 70%: → Upgrade NIC or reduce ops/sec target
  If total_pct < 50%: → OK (comfortable headroom)
```

**Example**:

```
Input:
  ops/sec: 100,000
  payload: 1,024 bytes
  read_ratio: 0.80
  replication_factor: 1
  NIC: 1 Gbps

Calculations:
  client_read_mbps   = 100K × 0.8 × 1024 × 8 / 1M = 655 Mbps
  client_write_mbps  = 100K × 0.2 × 1024 × 8 / 1M = 164 Mbps
  replication_mbps   = 100K × 0.2 × 1 × 1024 × 8 / 1M = 164 Mbps
  total_mbps         = 983 Mbps

  total_pct = 983 / 1000 × 100 = 98.3%

Decision: UPGRADE NIC (98% utilized on 1Gbps)
  → Use 10Gbps NIC: 98.3% / 10 = 9.8% (comfortable)
  → Or reduce ops/sec target to ~70K
```

---

## 5. Go Code Snippets

### Sampling-based Memory Estimator

```go
package main

import (
    "context"
    "fmt"
    "log"
    "math"
    "time"

    "github.com/redis/go-redis/v9"
)

type MemorySample struct {
    Key    string
    Bytes  int64
    Count  int64
}

// SampleKeys estimates total memory by random sampling.
// Uses SCAN to iterate keys and MEMORY USAGE per sample.
func SampleKeys(ctx context.Context, rdb *redis.Client, pattern string, sampleSize int) (*MemorySample, error) {
    var totalBytes int64
    var sampleCount int64
    var totalKeys int64

    // First: estimate total key count via SCAN (fast estimate)
    iter := rdb.Scan(ctx, 0, pattern, 1000).Iterator()
    for iter.Next(ctx) {
        totalKeys++
    }
    if err := iter.Err(); err != nil {
        return nil, fmt.Errorf("SCAN: %w", err)
    }

    if totalKeys == 0 {
        return &MemorySample{Key: pattern, Bytes: 0, Count: 0}, nil
    }

    // Second: random sample using SCAN with count hint
    // Note: Redis SCAN is not truly random, but provides uniform-ish sampling
    // For statistical accuracy, use RANDOMKEY between samples
    iter2 := rdb.Scan(ctx, 0, pattern, int64(sampleSize)).Iterator()
    for iter2.Next(ctx) {
        key := iter2.Val()
        bytes, err := rdb.MemoryUsage(ctx, key).Result()
        if err != nil {
            // Key may have expired or been deleted between SCAN and MEMORY USAGE
            log.Printf("MEMORY USAGE failed for %s: %v", key, err)
            continue
        }
        totalBytes += bytes
        sampleCount++
        if sampleCount >= int64(sampleSize) {
            break
        }
    }
    if err := iter2.Err(); err != nil {
        return nil, fmt.Errorf("SCAN sample: %w", err)
    }

    if sampleCount == 0 {
        return &MemorySample{Key: pattern, Bytes: 0, Count: totalKeys}, nil
    }

    // Extrapolate
    avgBytes := float64(totalBytes) / float64(sampleCount)
    estimatedTotal := avgBytes * float64(totalKeys)

    return &MemorySample{
        Key:   pattern,
        Bytes: int64(estimatedTotal),
        Count: totalKeys,
    }, nil
}

// StatisticalConfidence computes 95% CI for the estimate.
func StatisticalConfidence(samples []int64) (mean, stddev, ci95 float64) {
    n := float64(len(samples))
    if n < 2 {
        return 0, 0, 0
    }

    sum := float64(0)
    for _, v := range samples {
        sum += float64(v)
    }
    mean = sum / n

    // Standard deviation
    var ssq float64
    for _, v := range samples {
        d := float64(v) - mean
        ssq += d * d
    }
    stddev = math.Sqrt(ssq / (n - 1))

    // 95% CI: mean ± 1.96 × stddev / sqrt(n)
    ci95 = 1.96 * stddev / math.Sqrt(n)

    return mean, stddev, ci95
}

func main() {
    ctx := context.Background()
    rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    defer rdb.Close()

    // Ping to verify connection
    if err := rdb.Ping(ctx).Err(); err != nil {
        log.Fatalf("Cannot connect to Redis: %v", err)
    }

    pattern := "cache:*"
    sampleSize := 500 // minimum for ±10% error at 95% confidence

    fmt.Printf("Sampling %d keys matching '%s'...\n", sampleSize, pattern)
    start := time.Now()

    sample, err := SampleKeys(ctx, rdb, pattern, sampleSize)
    if err != nil {
        log.Fatalf("Sampling failed: %v", err)
    }

    fmt.Printf("\n=== Memory Estimate ===\n")
    fmt.Printf("Total keys (estimated): %d\n", sample.Count)
    fmt.Printf("Estimated memory:       %.2f GB\n", float64(sample.Bytes)/1_073_741_824)
    fmt.Printf("Sample time:            %v\n", time.Since(start))

    // Add headroom
    headroom := float64(sample.Bytes) * 0.40 // 40% headroom
    recommended := float64(sample.Bytes) + headroom
    fmt.Printf("\nWith 40%% headroom:       %.2f GB\n", recommended/1_073_741_824)
    fmt.Printf("Recommended instance:    %.0f GB\n", math.Ceil(recommended/1_073_741_824/10)*10)
}
```

### INFO Parser — Capacity-relevant fields

```go
package main

import (
    "fmt"
    "strconv"
    "strings"
)

type CapacitySnapshot struct {
    UsedMemory       int64
    MaxMemory        int64
    UsedMemoryRSS    int64
    FragRatio        float64
    ConnectedClients int64
    MaxClients       int64
    RejectedConns    int64
    OpsPerSec        int64
    TotalCommands    int64
    ReplBacklogSize  int64
    ReplBacklogUsed  int64
}

func ParseCapacityInfo(info string) (*CapacitySnapshot, error) {
    s := &CapacitySnapshot{}
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
            s.UsedMemoryRSS, _ = strconv.ParseInt(val, 10, 64)
        case "mem_fragmentation_ratio":
            s.FragRatio, _ = strconv.ParseFloat(val, 64)
        case "connected_clients":
            s.ConnectedClients, _ = strconv.ParseInt(val, 10, 64)
        case "maxclients":
            s.MaxClients, _ = strconv.ParseInt(val, 10, 64)
        case "rejected_connections":
            s.RejectedConns, _ = strconv.ParseInt(val, 10, 64)
        case "instantaneous_ops_per_sec":
            s.OpsPerSec, _ = strconv.ParseInt(val, 10, 64)
        case "total_commands_processed":
            s.TotalCommands, _ = strconv.ParseInt(val, 10, 64)
        case "repl_backlog_size":
            s.ReplBacklogSize, _ = strconv.ParseInt(val, 10, 64)
        case "repl_backlog_histlen":
            s.ReplBacklogUsed, _ = strconv.ParseInt(val, 10, 64)
        }
    }
    return s, nil
}

func (c *CapacitySnapshot) Report() string {
    var b strings.Builder

    memUsedGB := float64(c.UsedMemory) / 1_073_741_824
    memMaxGB := float64(c.MaxMemory) / 1_073_741_824
    memUsedPct := 0.0
    if c.MaxMemory > 0 {
        memUsedPct = float64(c.UsedMemory) / float64(c.MaxMemory) * 100
    }
    connPct := 0.0
    if c.MaxClients > 0 {
        connPct = float64(c.ConnectedClients) / float64(c.MaxClients) * 100
    }

    b.WriteString(fmt.Sprintf("Memory:        %.2f / %.2f GB (%.1f%%) | ⚠️ if >70%%\n", memUsedGB, memMaxGB, memUsedPct))
    b.WriteString(fmt.Sprintf("Frag ratio:    %.2f | ⚠️ if >1.5\n", c.FragRatio))
    b.WriteString(fmt.Sprintf("Connections:   %d / %d (%.1f%%) | ⚠️ if >70%%\n", c.ConnectedClients, c.MaxClients, connPct))
    b.WriteString(fmt.Sprintf("Rejected:      %d (⚠️ any > 0 = maxclients hit)\n", c.RejectedConns))
    b.WriteString(fmt.Sprintf("Ops/sec:       %d\n", c.OpsPerSec))
    b.WriteString(fmt.Sprintf("Backlog used:  %.2f / %.2f MB\n",
        float64(c.ReplBacklogUsed)/1_048_576,
        float64(c.ReplBacklogSize)/1_048_576))

    return b.String()
}
```

---

## 6. Links & References

### Official Documentation
- https://redis.io/docs/management/optimization/memory/ — Memory optimization guide
- https://redis.io/docs/management/optimization/ — Redis optimization docs
- https://redis.io/docs/management/replication/ — Replication internals
- https://redis.io/docs/reference/clients/ — Client connection management
- https://redis.io/docs/management/optimization/benchmarks/ — Benchmark guide

### Cloud Sizing Guides
- https://docs.aws.amazon.com/AmazonElastiCache/latest/Userg/WhatIs.html — ElastiCache sizing
- https://cloud.google.com/memorystore/docs/redis — GCP Memorystore sizing
- https://learn.microsoft.com/en-us/azure/cache/cache-best-practices — Azure Cache sizing

### Redis Source Code
- `src/object.c` — MEMORY USAGE implementation
- `src/server.c` — maxmemory, eviction logic
- `src/anet.c` — connection management
- `src/replication.c` — replication backlog sizing

### Reading List
- **Twitter Engineering: "Storing a Billion Social Graph"** — twitter.dev/blog — sizing large Redis graphs
- **Discord: "Using Redis as a Time Series Database"** — discord.com/blog — memory + ops/sec planning
- **Shopify: "Scaling Shopify's Redis"** — shopify.engineering — cluster + sharding lessons
- **Redis University RU101** — free course on Redis fundamentals
- **Martin Kleppmann "Designing Data-Intensive Applications"** — chapter 5: local vs distributed data
- **AWS ElastiCache Best Practices Whitepaper** — sizing formulas for production workloads
